#!/usr/bin/env python3
"""
Enhanced Metrics Collector - Adapted for WorkingBot Data Structure
This collector reads from your actual data files and extracts real metrics.
"""

import json
import time
from pathlib import Path
from observability.metrics.collectors import MetricsCollector
from observability.metrics.definitions import *

BASE_DIR = Path("/Users/ssr/Projects/WorkingBot")

def collect_real_trading_metrics():
    """Collect trading metrics from monitoring snapshots"""
    try:
        # Process all monitoring snapshot files
        snapshot_files = [
            BASE_DIR / 'data' / 'monitoring_snapshot_BTCUSD_LONG.json',
            BASE_DIR / 'data' / 'monitoring_snapshot_ETHUSD_LONG.json',
            BASE_DIR / 'data' / 'monitoring_snapshot.json',
        ]
        
        for snapshot_file in snapshot_files:
            if not snapshot_file.exists():
                continue
                
            with open(snapshot_file) as f:
                data = json.load(f)
            
            # Extract identifiers
            mode = data.get('mode', 'UNKNOWN')
            symbol = data.get('symbol', 'UNKNOWN')
            instance = f"{symbol}_{mode}"
            
            # Current price from state or metrics
            state = data.get('state', {})
            metrics = data.get('metrics', {})
            
            # Price from pending orders
            pending_buy = state.get('pending_buy')
            if pending_buy and 'price' in pending_buy:
                price = pending_buy['price']
                current_price_usd.labels(symbol=symbol).set(price)
            
            # Positions
            positions_data = metrics.get('positions', {})
            open_count = positions_data.get('open_count', 0)
            open_positions_count.labels(
                symbol=symbol, instance=instance, side='all'
            ).set(open_count)
            
            # Orders
            orders_data = metrics.get('orders', {})
            total_placed = orders_data.get('total_placed', 0)
            total_cancelled = orders_data.get('total_cancelled', 0)
            total_failures = orders_data.get('total_failures', 0)
            
            if total_placed > 0:
                orders_placed_total.labels(
                    symbol=symbol, instance=instance, order_type='all'
                ).inc(0)  # Set gauge to current value
                orders_placed_total.labels(
                    symbol=symbol, instance=instance, order_type='all'
                )._value.set(total_placed)
            
            if total_cancelled > 0:
                orders_cancelled_total.labels(
                    symbol=symbol, instance=instance, order_type='all'
                )._value.set(total_cancelled)
            
            if total_failures > 0:
                orders_failed_total.labels(
                    symbol=symbol, instance=instance, order_type='all'
                )._value.set(total_failures)
            
            # P&L from metrics
            pnl_data = metrics.get('pnl', {})
            if pnl_data:
                realized = pnl_data.get('total_realized_pnl', 0)
                unrealized = pnl_data.get('total_unrealized_pnl', 0)
                daily = pnl_data.get('daily_pnl', 0)
                
                if realized:
                    realized_pnl_usd.labels(symbol=symbol, instance=instance).inc(0)
                    realized_pnl_usd.labels(symbol=symbol, instance=instance)._value.set(realized)
                if unrealized:
                    unrealized_pnl_usd.labels(symbol=symbol, instance=instance).set(unrealized)
                if daily:
                    daily_pnl_usd.labels(symbol=symbol, instance=instance).set(daily)
            
            # Bot uptime
            uptime = data.get('uptime', 0)
            if uptime:
                bot_uptime_seconds.labels(symbol=symbol, instance=instance).set(uptime)
            
    except Exception as e:
        print(f"Error collecting trading metrics: {e}")


def collect_real_guardian_metrics():
    """Collect Guardian metrics from webui_guardian_stats.json"""
    try:
        guardian_file = BASE_DIR / 'data' / 'webui_guardian_stats.json'
        if not guardian_file.exists():
            return
        
        with open(guardian_file) as f:
            data = json.load(f)
        
        symbol = data.get('symbol', 'BTCUSD')
        instance = data.get('instance', 'MAIN')
        
        # Guardian signal
        signal = data.get('signal', data.get('status', 'GO'))
        guardian_signal.labels(symbol=symbol, instance=instance).set(
            1 if signal.upper() == 'GO' else 0
        )
        
        # Risk level
        risk = data.get('risk_level', 0)
        if isinstance(risk, str):
            risk_map = {'LOW': 25, 'MEDIUM': 50, 'HIGH': 75, 'CRITICAL': 100}
            risk = risk_map.get(risk.upper(), 0)
        guardian_risk_level.labels(symbol=symbol, instance=instance).set(risk)
        
        # Loss metrics
        loss = data.get('total_loss', data.get('total_loss_inr', 0))
        total_loss_inr.labels(symbol=symbol, instance=instance).set(abs(loss))
        
        daily = data.get('daily_loss', data.get('daily_loss_inr', 0))
        daily_loss_inr.labels(symbol=symbol, instance=instance).set(abs(daily))
        
        # Liquidation distance
        liq_dist = data.get('liquidation_distance', 100)
        liquidation_distance_percent.labels(symbol=symbol, instance=instance).set(liq_dist)
        
        # RSI
        rsi = data.get('rsi', {})
        if rsi:
            rsi_val = rsi.get('value', rsi.get('current', 0))
            if rsi_val:
                rsi_value.labels(symbol=symbol, timeframe='1h').set(rsi_val)
                rsi_trading_allowed.labels(symbol=symbol, instance=instance).set(
                    1 if rsi.get('trading_allowed', True) else 0
                )
        
        # Uptime
        start_time = data.get('start_time', data.get('start_timestamp', 0))
        if start_time:
            if isinstance(start_time, str):
                from datetime import datetime
                try:
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    start_time = dt.timestamp()
                except:
                    start_time = 0
            
            if start_time:
                uptime = time.time() - start_time
                guardian_uptime_seconds.labels(symbol=symbol, instance=instance).set(uptime)
        
        # Interventions
        interventions = data.get('interventions', data.get('total_interventions', 0))
        if interventions:
            guardian_interventions_total.labels(
                symbol=symbol, instance=instance, reason='all'
            ).inc(interventions)
            
    except Exception as e:
        print(f"Error collecting guardian metrics: {e}")


def collect_real_options_metrics():
    """Collect options trading metrics from database and CSV"""
    try:
        import sqlite3
        import csv
        
        # Collect from options database
        db_path = BASE_DIR / 'data' / 'options_sl_tp.db'
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Count active options contracts by type
            cursor.execute("SELECT COUNT(*) FROM sl_tp_settings WHERE status='active'")
            active_count = cursor.fetchone()[0]
            
            # Track active strategies with proper labels
            if active_count > 0:
                options_strategies_active.labels(
                    strategy_type='sl_tp',
                    symbol='BTC'
                ).set(active_count)
            
            # Get contract details for position tracking
            cursor.execute("SELECT contract_name FROM sl_tp_settings WHERE status='active'")
            call_count = 0
            put_count = 0
            
            for row in cursor.fetchall():
                contract_name = row[0] or ''
                if contract_name.startswith('C-'):
                    call_count += 1
                elif contract_name.startswith('P-'):
                    put_count += 1
            
            # Track configured positions (not yet opened)
            if call_count > 0:
                options_positions_count.labels(
                    symbol='BTC',
                    option_type='call',
                    strategy='sl_tp'
                ).set(call_count)
            
            if put_count > 0:
                options_positions_count.labels(
                    symbol='BTC',
                    option_type='put',
                    strategy='sl_tp'
                ).set(put_count)
            
            conn.close()
        
        # Collect from options trades CSV (when it exists)
        trades_file = BASE_DIR / 'data' / 'options_trades.csv'
        if trades_file.exists():
            with open(trades_file, 'r') as f:
                reader = csv.DictReader(f)
                trades = list(reader)
                
                if len(trades) > 0:
                    # Count total trades
                    options_orders_total.labels(
                        symbol='BTC',
                        option_type='all',
                        action='buy'
                    ).inc(len(trades))
                    
                    # Calculate P&L from completed trades
                    total_pnl = 0
                    for trade in trades:
                        pnl = float(trade.get('pnl', 0))
                        total_pnl += pnl
                    
                    if total_pnl != 0:
                        options_unrealized_pnl_usd.labels(symbol='BTC').set(total_pnl)
        
    except Exception as e:
        print(f"Error collecting options metrics: {e}")


def collect_enhanced_metrics():
    """Enhanced collection using real data files"""
    collect_real_trading_metrics()
    collect_real_guardian_metrics()
    collect_real_options_metrics()
    
    # Still collect system metrics (working)
    MetricsCollector.collect_system_metrics()
    MetricsCollector.collect_pm2_metrics()


if __name__ == '__main__':
    print("Testing enhanced metrics collection...")
    collect_enhanced_metrics()
    print("✅ Done")
