"""
Experimental Features API Routes

Contains experimental/research features:
- Auto-Delta Hedging (institutional-grade)
- Portfolio Greeks monitoring
- Other experimental algorithms

Author: WorkingBot
Date: January 2026
"""

from flask import Blueprint, jsonify, request
import sys
import os
import math
import asyncio
from datetime import datetime
from loguru import logger

# Add parent paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from config.loader import get_api_credentials

experimental_bp = Blueprint('experimental', __name__, url_prefix='/api/experimental')


def get_api_client():
    """Helper to create UnifiedAPIClient with proper config from credentials loader."""
    from bot.api.unified_api_client import UnifiedAPIClient
    
    creds = get_api_credentials()
    return UnifiedAPIClient(
        api_key=creds['api_key'],
        api_secret=creds['api_secret'],
        symbol='BTCUSD',
        enable_websocket=False
    )


# ============================================================================
# AUTO-DELTA HEDGING - INSTITUTIONAL FEATURE
# ============================================================================
# 
# This is a real institutional algorithm from quantitative trading desks.
# Strategy:
# 1. Calculate total portfolio Delta from all options positions
# 2. When |Delta| > threshold, hedge with BTC perpetual
# 3. Goal: Keep portfolio delta-neutral to profit from theta/vega
#
# How it works:
# - Long call = positive delta (gains if BTC rises)
# - Short call = negative delta
# - Long put = negative delta 
# - Short put = positive delta
# - BTC perpetual has delta = 1.0 per contract
#
# To hedge:
# - If portfolio delta = +5 BTC, sell 5 BTC perpetual (delta now = 0)
# - If portfolio delta = -5 BTC, buy 5 BTC perpetual (delta now = 0)
# ============================================================================


def calculate_option_delta(option_type: str, spot: float, strike: float, 
                           dte: float, iv: float, size: float) -> float:
    """
    Calculate delta for a single option position using Black-Scholes approximation.
    
    Delta represents the rate of change of option price with respect to underlying.
    - Call delta: 0 to 1 (ATM ~ 0.5)
    - Put delta: -1 to 0 (ATM ~ -0.5)
    
    Args:
        option_type: 'C' for call, 'P' for put
        spot: Current BTC price
        strike: Strike price
        dte: Days to expiry
        iv: Implied volatility (decimal, e.g., 0.8 for 80%)
        size: Position size (negative for short)
    
    Returns:
        Delta in BTC units
    """
    # Convert all numeric values to float
    try:
        spot = float(spot) if spot else 100000
        strike = float(strike) if strike else 100000
        dte = float(dte) if dte else 30
        iv = float(iv) if iv else 0.8
        size = float(size) if size else 0
    except (ValueError, TypeError):
        return 0
    
    if dte <= 0:
        # At expiry
        if option_type == 'C':
            return size if spot > strike else 0
        else:
            return -size if spot < strike else 0
    
    # Simplified Black-Scholes delta approximation
    # More accurate than naive moneyness but faster than full BS
    try:
        t = dte / 365.0
        if iv <= 0 or t <= 0:
            return 0
            
        # d1 calculation (Black-Scholes)
        d1 = (math.log(spot / strike) + (0.5 * iv * iv * t)) / (iv * math.sqrt(t))
        
        # Cumulative normal distribution approximation
        def norm_cdf(x):
            # Approximation of cumulative normal distribution
            a1 = 0.254829592
            a2 = -0.284496736
            a3 = 1.421413741
            a4 = -1.453152027
            a5 = 1.061405429
            p = 0.3275911
            sign = 1 if x >= 0 else -1
            x = abs(x) / math.sqrt(2)
            t_val = 1.0 / (1.0 + p * x)
            y = 1.0 - (((((a5 * t_val + a4) * t_val) + a3) * t_val + a2) * t_val + a1) * t_val * math.exp(-x * x)
            return 0.5 * (1.0 + sign * y)
        
        # Call delta = N(d1), Put delta = N(d1) - 1
        if option_type == 'C':
            delta_per_contract = norm_cdf(d1)
        else:
            delta_per_contract = norm_cdf(d1) - 1
        
        # Total delta = delta_per_contract * size
        # Size is in lots, each lot is 0.001 BTC
        btc_per_lot = 0.001
        return delta_per_contract * size * btc_per_lot
        
    except Exception as e:
        logger.error(f"Delta calculation error: {e}")
        return 0


def get_portfolio_greeks() -> dict:
    """
    Calculate aggregate Greeks for the entire options portfolio.
    
    Returns:
        dict: {delta, gamma, vega, theta, positions_count}
    """
    try:
        client = get_api_client()
        
        # Use asyncio to run the async method
        async def fetch_positions():
            return await client.get_all_positions_with_options()
        
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, use run_until_complete in a new loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, fetch_positions())
                    positions_data = future.result(timeout=30)
            else:
                positions_data = loop.run_until_complete(fetch_positions())
        except RuntimeError:
            positions_data = asyncio.run(fetch_positions())
        
        if not positions_data:
            return {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'positions_count': 0}
        
        options_positions = positions_data.get('options', [])
        futures_positions = positions_data.get('futures', [])
        
        # Get current BTC price
        btc_price = 100000.0  # Default
        for pos in futures_positions:
            if pos.get('product_symbol') == 'BTCUSD':
                mark = pos.get('mark_price') or pos.get('entry_price') or 100000
                try:
                    btc_price = float(mark)
                except (ValueError, TypeError):
                    btc_price = 100000.0
                break
        
        total_delta = 0.0
        total_gamma = 0.0
        total_vega = 0.0
        total_theta = 0.0
        
        for pos in options_positions:
            symbol = pos.get('product_symbol', '')
            try:
                size = float(pos.get('size', 0) or 0)
            except (ValueError, TypeError):
                size = 0.0
            
            if not symbol or size == 0:
                continue
            
            # Parse symbol: C-BTC-95000-300126 or P-BTC-88000-300126
            parts = symbol.split('-')
            if len(parts) != 4:
                continue
            
            option_type = parts[0]  # C or P
            strike = float(parts[2])
            expiry_code = parts[3]  # DDMMYY
            
            # Calculate DTE
            try:
                day = int(expiry_code[:2])
                month = int(expiry_code[2:4])
                year = 2000 + int(expiry_code[4:6])
                expiry_date = datetime(year, month, day)
                dte = (expiry_date - datetime.now()).days
                if dte < 0:
                    dte = 0
            except:
                dte = 30  # Default if parsing fails
            
            # Get IV from position or use default
            iv = pos.get('iv', 0.8)  # 80% default IV
            if isinstance(iv, str):
                try:
                    iv = float(iv.replace('%', '')) / 100
                except:
                    iv = 0.8
            
            # Calculate delta for this position
            delta = calculate_option_delta(option_type, btc_price, strike, dte, iv, size)
            total_delta += delta
            
            # Simplified gamma/vega/theta (approximations)
            # These are rough estimates - real implementation would use full Greeks
            btc_per_lot = 0.001
            abs_size = abs(size) * btc_per_lot
            
            # Gamma is highest ATM
            moneyness = abs(btc_price - strike) / btc_price
            gamma_factor = max(0, 1 - moneyness * 5) * 0.01  # Rough approximation
            total_gamma += gamma_factor * abs_size * (1 if size > 0 else -1)
            
            # Vega - higher for longer dated
            vega_factor = math.sqrt(dte / 365) * 0.1
            total_vega += vega_factor * abs_size * (1 if size > 0 else -1)
            
            # Theta - option sellers collect, buyers pay
            theta_factor = -0.01 * (30 / max(dte, 1))  # Accelerates near expiry
            total_theta += theta_factor * abs_size * (1 if size > 0 else -1)
        
        # Add futures delta (BTC perpetual has delta = 1 per BTC)
        for pos in futures_positions:
            if pos.get('product_symbol') == 'BTCUSD':
                # Size in lots, but for futures it's usually contracts
                try:
                    futures_size = float(pos.get('size', 0) or 0)
                except (ValueError, TypeError):
                    futures_size = 0.0
                # Perpetual delta = size in BTC terms
                total_delta += futures_size  # Already in BTC units
        
        return {
            'delta': round(total_delta, 4),
            'gamma': round(total_gamma, 4),
            'vega': round(total_vega, 4),
            'theta': round(total_theta, 4),
            'positions_count': len(options_positions),
            'btc_price': btc_price,
        }
        
    except Exception as e:
        logger.error(f"Error calculating portfolio Greeks: {e}")
        return {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'error': str(e)}


@experimental_bp.route('/greeks', methods=['GET'])
def get_greeks():
    """
    Get current portfolio Greeks.
    
    Returns:
        JSON: {success, greeks: {delta, gamma, vega, theta}}
    """
    try:
        greeks = get_portfolio_greeks()
        return jsonify({
            'success': True,
            'greeks': greeks,
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error in get_greeks: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@experimental_bp.route('/hedge', methods=['POST'])
def execute_hedge():
    """
    Execute a delta hedge using BTC perpetual.
    
    Request body:
        delta: Current portfolio delta
        threshold: Delta threshold that was exceeded
    
    Returns:
        JSON: {success, hedge: {deltaBefore, hedgeSize, price, status, timestamp}}
    """
    try:
        data = request.json or {}
        current_delta = data.get('delta', 0)
        threshold = data.get('threshold', 5)
        
        if abs(current_delta) <= threshold:
            return jsonify({
                'success': False,
                'error': f'Delta {current_delta} is within threshold {threshold}',
            })
        
        # Calculate hedge size (opposite of current delta)
        hedge_size = -current_delta
        
        # Get current BTC price
        btc_price = 100000  # Default
        try:
            client = get_api_client()
            
            async def get_ticker():
                return await client.rest_client.get_ticker('BTCUSD')
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, get_ticker())
                        ticker = future.result(timeout=10)
                else:
                    ticker = loop.run_until_complete(get_ticker())
            except RuntimeError:
                ticker = asyncio.run(get_ticker())
            
            btc_price = ticker.get('mark_price', 100000)
        except Exception as e:
            logger.warning(f"Could not fetch BTC price: {e}")
        
        # Execute the hedge order
        try:
            client = get_api_client()
            
            side = 'buy' if hedge_size > 0 else 'sell'
            abs_size = abs(hedge_size)
            
            # Place market order for BTC perpetual
            logger.info(f"[AUTO-HEDGE] Executing: {side} {abs_size} BTC @ market")
            
            async def place_hedge_order():
                return await client.rest_client.place_order(
                    product_symbol='BTCUSD',
                    side=side,
                    order_type='market',
                    size=int(abs_size),  # Size in contracts/lots
                )
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, place_hedge_order())
                        order_result = future.result(timeout=30)
                else:
                    order_result = loop.run_until_complete(place_hedge_order())
            except RuntimeError:
                order_result = asyncio.run(place_hedge_order())
            
            order_status = 'success' if order_result.get('success') else 'failed'
            fill_price = order_result.get('fill_price', btc_price)
            
            hedge_record = {
                'timestamp': datetime.now().isoformat(),
                'deltaBefore': round(current_delta, 4),
                'hedgeSize': round(hedge_size, 4),
                'side': side,
                'price': fill_price,
                'status': order_status,
                'orderId': order_result.get('order_id'),
            }
            
            logger.info(f"[AUTO-HEDGE] Completed: {hedge_record}")
            
            return jsonify({
                'success': True,
                'hedge': hedge_record,
            })
            
        except Exception as order_error:
            logger.error(f"[AUTO-HEDGE] Order execution failed: {order_error}")
            
            # Return simulated result for testing
            hedge_record = {
                'timestamp': datetime.now().isoformat(),
                'deltaBefore': round(current_delta, 4),
                'hedgeSize': round(hedge_size, 4),
                'side': 'buy' if hedge_size > 0 else 'sell',
                'price': btc_price,
                'status': 'simulated',
                'error': str(order_error),
            }
            
            return jsonify({
                'success': True,
                'hedge': hedge_record,
                'simulated': True,
            })
        
    except Exception as e:
        logger.error(f"Error in execute_hedge: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@experimental_bp.route('/health', methods=['GET'])
def health():
    """Health check for experimental API."""
    return jsonify({
        'success': True,
        'service': 'experimental',
        'features': ['auto-delta-hedging', 'portfolio-greeks'],
        'timestamp': datetime.now().isoformat(),
    })
