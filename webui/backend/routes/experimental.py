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
    Get aggregate Greeks for entire portfolio from Delta Exchange API.
    Uses same data source as Options Panel for consistency.
    
    Returns:
        dict: {delta, gamma, vega, theta, positions_count, options_delta, futures_delta}
    """
    try:
        from bot.api.delta_client import DeltaClient
        
        delta_client = DeltaClient()
        
        # Fetch all positions from Delta Exchange (same as positions.py)
        response = delta_client._req('GET', '/v2/positions/margined')
        
        if not response or not response.get('success'):
            logger.error("Failed to fetch positions from Delta Exchange")
            return {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'positions_count': 0}
        
        pos_list = response.get('result', [])
        
        total_options_delta = 0.0
        total_futures_delta = 0.0
        total_gamma = 0.0
        total_vega = 0.0
        total_theta = 0.0
        options_count = 0
        btc_price = 100000.0
        
        for pos_data in pos_list:
            size = int(pos_data.get('size', 0))
            if size == 0:
                continue
            
            product_symbol = pos_data.get('product_symbol', '')
            mark_price = float(pos_data.get('mark_price', 0))
            
            # Determine if option or future
            is_option = any(x in product_symbol for x in ['C-', 'P-'])
            
            if not is_option:
                # FUTURES: delta = size (positive for long, negative for short)
                # This matches positions.py line 398-399
                if 'BTC' in product_symbol:
                    btc_price = mark_price
                    total_futures_delta += float(size)
            else:
                # OPTIONS: Get Greeks from ticker endpoint (same as positions.py)
                options_count += 1
                try:
                    ticker_response = delta_client._req('GET', f'/v2/tickers/{product_symbol}')
                    if ticker_response.get('success'):
                        ticker_data = ticker_response.get('result', {})
                        greeks = ticker_data.get('greeks', {})
                        if greeks:
                            # Per-contract Greeks from API
                            delta = float(greeks.get('delta', 0))
                            vega = float(greeks.get('vega', 0))
                            theta = float(greeks.get('theta', 0))
                            gamma = float(greeks.get('gamma', 0))
                            
                            # Position Greeks = per-contract * size
                            # (same logic as positions.py line 440-443)
                            pos_delta = delta * size
                            pos_gamma = gamma * abs(size)
                            pos_theta = theta * abs(size)
                            pos_vega = vega * abs(size)
                            
                            total_options_delta += pos_delta
                            total_gamma += pos_gamma
                            total_theta += pos_theta
                            total_vega += pos_vega
                except Exception as e:
                    logger.debug(f"Could not fetch Greeks for {product_symbol}: {e}")
        
        # Total delta = options delta + futures delta
        total_delta = total_options_delta + total_futures_delta
        
        logger.info(f"Portfolio Greeks: options_delta={total_options_delta:.2f}, futures_delta={total_futures_delta:.2f}, total={total_delta:.2f}")
        
        return {
            'delta': round(total_delta, 4),
            'options_delta': round(total_options_delta, 4),
            'futures_delta': round(total_futures_delta, 4),
            'gamma': round(total_gamma, 4),
            'vega': round(total_vega, 4),
            'theta': round(total_theta, 4),
            'positions_count': options_count,
            'btc_price': btc_price,
        }
        
    except Exception as e:
        logger.error(f"Error calculating portfolio Greeks: {e}")
        import traceback
        traceback.print_exc()
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
        'features': ['auto-delta-hedging', 'portfolio-greeks', 'gamma-scalping'],
        'timestamp': datetime.now().isoformat(),
    })


# ============================================================================
# GAMMA SCALPING - MARKET MAKER STRATEGY
# ============================================================================
#
# Classic market maker strategy:
# 1. When you own options (long gamma), you profit from price movement
# 2. But you must delta-hedge to "lock in" that gamma profit
# 3. Each time price moves by threshold, hedge the delta change
#
# Math: Gamma P&L = 0.5 × Γ × (ΔPrice)²
#
# Example:
# - You have +0.1 gamma, price moves $1000
# - Gamma profit = 0.5 × 0.1 × 1000² = $50,000
# - But you need to hedge to lock it in before price reverses!
#
# ============================================================================

@experimental_bp.route('/gamma-scalp', methods=['POST'])
def execute_gamma_scalp():
    """
    Execute a gamma scalp trade.
    
    When price moves by threshold, the options delta changes due to gamma.
    We hedge that delta change to "lock in" the gamma profit.
    
    Request body:
        price_diff: How much price moved since last scalp
        current_delta: Current options delta
        current_price: Current BTC price
        threshold: Price threshold that triggered this scalp
    
    Returns:
        Scalp execution details
    """
    try:
        data = request.get_json() or {}
        
        price_diff = float(data.get('price_diff', 0))
        current_delta = float(data.get('current_delta', 0))
        current_price = float(data.get('current_price', 0))
        threshold = float(data.get('threshold', 500))
        
        # Get current gamma from portfolio Greeks
        greeks = get_portfolio_greeks()
        gamma = greeks.get('gamma', 0)
        
        # Calculate delta change from gamma
        # Δdelta = gamma × ΔPrice (approximately)
        delta_change = gamma * price_diff
        
        # The hedge size is the delta change we need to offset
        # If price went UP and we're long gamma, delta increased → SELL to hedge
        # If price went DOWN and we're long gamma, delta decreased → BUY to hedge
        hedge_size = -delta_change  # Opposite sign to offset
        
        # Calculate estimated P&L from this gamma scalp
        # Gamma P&L = 0.5 × Γ × (ΔPrice)²
        estimated_pnl = 0.5 * abs(gamma) * (price_diff ** 2)
        
        # Determine direction
        if hedge_size > 0:
            direction = 'BUY'
        elif hedge_size < 0:
            direction = 'SELL'
        else:
            # No hedge needed
            return jsonify({
                'success': True,
                'scalp': {
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'direction': 'NONE',
                    'price_diff': round(price_diff, 2),
                    'size': 0,
                    'estimated_pnl': 0,
                    'gamma': round(gamma, 6),
                    'status': 'no_hedge_needed',
                },
            })
        
        logger.info(f"[GAMMA-SCALP] Price moved ${price_diff:.2f}, gamma={gamma:.6f}, hedge_size={hedge_size:.4f}")
        
        # Try to execute the hedge order
        try:
            from bot.api.delta_client import DeltaClient
            delta_client = DeltaClient()
            
            # Place market order to hedge
            order_size = int(abs(hedge_size))
            if order_size < 1:
                order_size = 1  # Minimum 1 lot
            
            side = 'buy' if hedge_size > 0 else 'sell'
            
            order_payload = {
                'product_id': 139,  # BTCUSD perpetual
                'size': order_size,
                'side': side,
                'order_type': 'market_order',
            }
            
            logger.info(f"[GAMMA-SCALP] Placing order: {order_payload}")
            order_result = delta_client._req('POST', '/v2/orders', data=order_payload)
            
            order_status = 'executed' if order_result.get('success') else 'failed'
            fill_price = order_result.get('result', {}).get('average_fill_price', current_price)
            
            scalp_record = {
                'time': datetime.now().strftime('%H:%M:%S'),
                'direction': direction,
                'price_diff': round(price_diff, 2),
                'size': round(hedge_size, 4),
                'estimated_pnl': round(estimated_pnl, 2),
                'gamma': round(gamma, 6),
                'fill_price': fill_price,
                'status': order_status,
                'order_id': order_result.get('result', {}).get('id'),
            }
            
            logger.info(f"[GAMMA-SCALP] Completed: {scalp_record}")
            
            return jsonify({
                'success': True,
                'scalp': scalp_record,
            })
            
        except Exception as order_error:
            logger.warning(f"[GAMMA-SCALP] Order execution failed: {order_error}")
            
            # Return simulated result for testing/demo
            scalp_record = {
                'time': datetime.now().strftime('%H:%M:%S'),
                'direction': direction,
                'price_diff': round(price_diff, 2),
                'size': round(hedge_size, 4),
                'estimated_pnl': round(estimated_pnl, 2),
                'gamma': round(gamma, 6),
                'fill_price': current_price,
                'status': 'simulated',
                'note': str(order_error),
            }
            
            return jsonify({
                'success': True,
                'scalp': scalp_record,
                'simulated': True,
            })
        
    except Exception as e:
        logger.error(f"Error in execute_gamma_scalp: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500
