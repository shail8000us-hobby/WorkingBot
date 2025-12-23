"""
Backfill Historical Volatility Data

This script fetches historical IV/RV data from Delta Exchange to populate
the database with past data, so charts show meaningful history immediately.

Run this once when setting up the volatility collector for the first time,
or anytime you want to refresh historical data.
"""

import os
import sys
import time
import math
import sqlite3
import requests
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger("backfill")

DB_PATH = str((project_root / "data" / "volatility.db").resolve())
API_BASE = "https://api.india.delta.exchange"
SYMBOL = "BTCUSD"


def backfill_rv_data(days_back: int = 90):
    """
    Backfill RV calculations from historical candle data.
    
    Args:
        days_back: Number of days to backfill (default 90)
    """
    log.info("=" * 70)
    log.info(f"🔄 BACKFILLING RV DATA - {days_back} DAYS")
    log.info("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get current timestamp
    now = datetime.now(timezone.utc)
    
    # Backfill for each timeframe
    timeframes = {
        '1d': {'resolution': '1h', 'window_hours': 24, 'annualize_factor': math.sqrt(365 * 24)},
        '7d': {'resolution': '1d', 'window_days': 7, 'annualize_factor': math.sqrt(365)},
        '30d': {'resolution': '1d', 'window_days': 30, 'annualize_factor': math.sqrt(365)}
    }
    
    for tf_name, config in timeframes.items():
        log.info(f"\n📊 Backfilling {tf_name} RV data...")
        
        # For better chart visualization, create daily RV snapshots
        # Each snapshot calculates RV for the trailing window
        window_days = config.get('window_days', config.get('window_hours', 24) / 24)
        
        inserted_count = 0
        
        # Create one RV snapshot per day for the lookback period
        for i in range(days_back):
            # Calculate time range for this snapshot (rolling window)
            end_time = now - timedelta(days=i)
            start_time = end_time - timedelta(days=window_days)
            
            # Fetch candles
            try:
                candles_url = f"{API_BASE}/v2/history/candles"
                params = {
                    'symbol': SYMBOL,
                    'resolution': config['resolution'],
                    'start': int(start_time.timestamp()),
                    'end': int(end_time.timestamp())
                }
                
                response = requests.get(candles_url, params=params, timeout=15)
                
                if response.status_code != 200:
                    log.warning(f"  Failed to fetch candles for day {i+1}/{days_back}: HTTP {response.status_code}")
                    continue
                
                data = response.json()
                if 'result' not in data or not data['result']:
                    continue
                
                candles = data['result']
                if len(candles) < 2:
                    continue
                
                # Extract close prices
                close_prices = [float(candle['close']) for candle in candles]
                
                # Calculate log returns
                log_returns = []
                for j in range(1, len(close_prices)):
                    if close_prices[j-1] > 0 and close_prices[j] > 0:
                        log_return = math.log(close_prices[j] / close_prices[j-1])
                        log_returns.append(log_return)
                
                if len(log_returns) < 2:
                    continue
                
                # Calculate RV
                mean_return = sum(log_returns) / len(log_returns)
                variance = sum((r - mean_return) ** 2 for r in log_returns) / (len(log_returns) - 1)
                std_dev = math.sqrt(variance)
                annualized_vol = std_dev * config['annualize_factor']
                rv_percent = annualized_vol * 100
                
                # Store in database
                timestamp = end_time.timestamp()
                dt = end_time.isoformat()
                
                cursor.execute("""
                    INSERT INTO rv_calculations 
                    (timestamp, datetime, timeframe, rv_value, num_candles, start_price, end_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, dt, tf_name, rv_percent, len(candles), close_prices[0], close_prices[-1]))
                
                inserted_count += 1
                
                if inserted_count % 10 == 0:
                    log.info(f"  Processed {inserted_count}/{days_back} days...")
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                log.error(f"  Error processing window {i+1}: {e}")
                continue
        
        conn.commit()
        log.info(f"✅ Inserted {inserted_count} {tf_name} RV records")
    
    conn.close()
    log.info("\n" + "=" * 70)
    log.info("✅ RV BACKFILL COMPLETE")
    log.info("=" * 70)


def backfill_iv_data():
    """
    Backfill IV data from current options.
    
    Note: We can only get current IV, not historical IV snapshots,
    so we'll just ensure we have at least one recent IV point.
    """
    log.info("\n📊 Checking IV data...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if we have recent IV data (within last 5 minutes)
    cursor.execute("""
        SELECT COUNT(*) FROM iv_snapshots 
        WHERE timestamp > ?
    """, (time.time() - 300,))
    
    recent_count = cursor.fetchone()[0]
    
    if recent_count > 0:
        log.info(f"✅ Found {recent_count} recent IV snapshots - no backfill needed")
        conn.close()
        return
    
    log.info("Fetching current IV snapshot...")
    
    try:
        # Get current BTC price
        ticker_url = f"{API_BASE}/v2/tickers/{SYMBOL}"
        ticker_resp = requests.get(ticker_url, timeout=10)
        
        if ticker_resp.status_code != 200:
            log.warning("Failed to fetch current ticker")
            conn.close()
            return
        
        ticker_data = ticker_resp.json()
        spot_price = float(ticker_data['result']['mark_price'])
        
        # Get option tickers
        tickers_url = f"{API_BASE}/v2/tickers"
        params = {
            'underlying_asset_symbols': 'BTC',
            'contract_types': 'call_options,put_options'
        }
        tickers_resp = requests.get(tickers_url, params=params, timeout=10)
        
        if tickers_resp.status_code != 200:
            log.warning("Failed to fetch option tickers")
            conn.close()
            return
        
        tickers_data = tickers_resp.json()
        
        # Find ATM options
        atm_options = []
        for ticker in tickers_data['result']:
            quotes = ticker.get('quotes', {})
            mark_iv = quotes.get('mark_iv')
            
            if mark_iv is None:
                bid_iv = quotes.get('bid_iv')
                ask_iv = quotes.get('ask_iv')
                if bid_iv and ask_iv:
                    mark_iv = (float(bid_iv) + float(ask_iv)) / 2
                elif bid_iv:
                    mark_iv = float(bid_iv)
                elif ask_iv:
                    mark_iv = float(ask_iv)
                else:
                    continue
            else:
                mark_iv = float(mark_iv)
            
            strike_price = ticker.get('strike_price')
            if strike_price is None:
                continue
            
            strike = float(strike_price)
            price_diff_pct = abs((strike - spot_price) / spot_price * 100)
            
            if price_diff_pct < 15:
                iv_value = mark_iv * 100
                atm_options.append({
                    'strike': strike,
                    'iv': iv_value,
                    'diff': price_diff_pct
                })
        
        if not atm_options:
            log.warning("No ATM options found")
            conn.close()
            return
        
        # Calculate weighted average IV
        total_weight = 0
        weighted_iv = 0
        for opt in atm_options:
            weight = 1 / (1 + opt['diff'])
            weighted_iv += opt['iv'] * weight
            total_weight += weight
        
        avg_iv = weighted_iv / total_weight
        
        # Store in database
        timestamp = time.time()
        dt = datetime.now(timezone.utc).isoformat()
        
        cursor.execute("""
            INSERT INTO iv_snapshots (timestamp, datetime, iv_value, source, atm_strike, num_options)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp, dt, avg_iv, 'backfill', spot_price, len(atm_options)))
        
        conn.commit()
        log.info(f"✅ Inserted current IV snapshot: {avg_iv:.2f}% (from {len(atm_options)} options)")
        
    except Exception as e:
        log.error(f"Failed to backfill IV: {e}")
    
    conn.close()


def show_summary():
    """Display summary of stored data"""
    log.info("\n" + "=" * 70)
    log.info("📊 DATABASE SUMMARY")
    log.info("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # IV summary
    cursor.execute('SELECT COUNT(*), MIN(datetime), MAX(datetime) FROM iv_snapshots')
    iv_stats = cursor.fetchone()
    log.info(f"\n📈 IV Snapshots: {iv_stats[0]} records")
    if iv_stats[0] > 0:
        log.info(f"   Range: {iv_stats[1]} to {iv_stats[2]}")
    
    # RV summary
    for tf in ['1d', '7d', '30d']:
        cursor.execute(
            f"SELECT COUNT(*), MIN(datetime), MAX(datetime) FROM rv_calculations WHERE timeframe = '{tf}'"
        )
        rv_stats = cursor.fetchone()
        log.info(f"\n📊 RV ({tf}): {rv_stats[0]} records")
        if rv_stats[0] > 0:
            log.info(f"   Range: {rv_stats[1]} to {rv_stats[2]}")
    
    conn.close()
    log.info("\n" + "=" * 70)


def main():
    """Main backfill routine"""
    log.info("=" * 70)
    log.info("🚀 VOLATILITY DATA BACKFILL UTILITY")
    log.info("=" * 70)
    log.info(f"Database: {DB_PATH}")
    log.info(f"API Base: {API_BASE}")
    log.info("=" * 70)
    
    # Ensure database exists
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    
    # Backfill RV data (90 days)
    backfill_rv_data(days_back=90)
    
    # Backfill current IV
    backfill_iv_data()
    
    # Show summary
    show_summary()
    
    log.info("\n✅ Backfill complete! The volatility chart should now show historical data.")
    log.info("💡 The collector will continue to add new data points every 30 seconds.\n")


if __name__ == "__main__":
    main()
