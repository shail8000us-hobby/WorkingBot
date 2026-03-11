"""
Options Chain Module - Market Data for Options
Created: January 17, 2026
Purpose: Fetch and serve options chain data (strikes, expiries, IV, Greeks)
Status: STUB - Returns 501 Not Implemented until full implementation
"""
from flask import Blueprint, jsonify, request
import logging

log = logging.getLogger(__name__)

options_chain_bp = Blueprint('options_chain', __name__, url_prefix='/api/options-chain')


@options_chain_bp.route('/expirations', methods=['GET'])
def get_expirations():
    """
    Get available expiration dates for an underlying
    
    Query params:
    - underlying: BTC, ETH, etc.
    """
    try:
        from routes.options.options_client import _run_async, get_unified_client

        underlying = request.args.get('underlying', 'BTC')
        log.info(f"[OPTIONS_CHAIN] Expiration request for {underlying}")

        # Fetch products from Delta Exchange using shared singleton + dedicated loop
        client = get_unified_client()

        async def fetch():
            products = await client.rest_client.get_products()
            log.info(f"[OPTIONS_CHAIN] Fetched {len(products)} products from Delta")

            expiries = set()
            for product in products:
                sym = product.get('symbol', '')
                if sym.startswith(('C-', 'P-')) and f'-{underlying}-' in sym:
                    parts = sym.split('-')
                    if len(parts) >= 4:
                        expiry_ddmmyy = parts[3]
                        if len(expiry_ddmmyy) == 6:
                            day = expiry_ddmmyy[0:2]
                            month = expiry_ddmmyy[2:4]
                            year_yy = expiry_ddmmyy[4:6]
                            expiry_ddmmyyyy = f"{day}{month}20{year_yy}"
                            expiries.add(expiry_ddmmyyyy)

            expiries_list = sorted(list(expiries))
            log.info(f"[OPTIONS_CHAIN] Found {len(expiries_list)} expiries for {underlying}")
            return expiries_list

        expiries = _run_async(fetch())
        
        return jsonify({
            "success": True,
            "expirations": expiries,
            "underlying": underlying,
            "count": len(expiries)
        })
        
    except Exception as e:
        log.error(f"[OPTIONS_CHAIN] Error getting expirations: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@options_chain_bp.route('/data', methods=['GET'])
def get_chain_data():
    """
    Get options chain data for a specific expiry
    
    Query params:
    - underlying: BTC, ETH, etc.
    - expiry: Expiration date (DDMMYYYY format, e.g., 01022026)
    """
    try:
        from routes.options.options_client import _run_async, get_unified_client

        underlying = request.args.get('underlying', 'BTC')
        expiry = request.args.get('expiry')  # DDMMYYYY format

        if not expiry:
            return jsonify({
                "success": False,
                "error": "Expiry date is required"
            }), 400

        log.info(f"[OPTIONS_CHAIN] Chain data request: {underlying} {expiry}")

        # Convert DDMMYYYY to DDMMYY for symbol matching
        if len(expiry) == 8:
            expiry_ddmmyy = expiry[0:2] + expiry[2:4] + expiry[6:8]
        else:
            expiry_ddmmyy = expiry

        log.info(f"[OPTIONS_CHAIN] Looking for symbols ending with: -{expiry_ddmmyy}")

        # Fetch products and build chain using shared singleton + dedicated loop
        client = get_unified_client()

        async def fetch():
            products = await client.rest_client.get_products()
            log.info(f"[OPTIONS_CHAIN] Fetched {len(products)} products")

            # Get current spot price
            spot_price = None
            for spot_symbol in [f'{underlying}USD', f'{underlying}USDT', 'BTCUSD']:
                spot_product = next((p for p in products if p.get('symbol') == spot_symbol), None)
                if spot_product:
                    spot_price = float(spot_product.get('spot_price') or spot_product.get('mark_price') or 0)
                    if spot_price > 0:
                        break

            log.info(f"[OPTIONS_CHAIN] Spot price: {spot_price}")

            strikes_dict = {}
            matched_count = 0

            for product in products:
                symbol = product.get('symbol', '')
                is_option = symbol.startswith(('C-', 'P-'))
                has_underlying = f'-{underlying}-' in symbol or f'-{underlying.lower()}-' in symbol
                has_expiry = symbol.endswith(f'-{expiry_ddmmyy}')

                if is_option and has_underlying and has_expiry:
                    matched_count += 1
                    parts = symbol.split('-')
                    if len(parts) >= 4:
                        option_type = 'call' if parts[0] == 'C' else 'put'
                        try:
                            strike = float(parts[2])
                        except (ValueError, IndexError):
                            continue

                        if strike not in strikes_dict:
                            strikes_dict[strike] = {'strike': strike, 'call': {}, 'put': {}}

                        greeks = product.get('greeks', {}) or {}
                        option_data = {
                            'symbol': symbol,
                            'ltp': float(product.get('mark_price') or product.get('last_price') or 0),
                            'bid': float(product.get('best_bid') or product.get('best_bid_price') or 0),
                            'ask': float(product.get('best_ask') or product.get('best_ask_price') or 0),
                            'iv': float(greeks.get('implied_volatility') or greeks.get('iv') or 0),
                            'delta': float(greeks.get('delta') or 0),
                            'gamma': float(greeks.get('gamma') or 0),
                            'theta': float(greeks.get('theta') or 0),
                            'vega': float(greeks.get('vega') or 0),
                            'oi': int(product.get('open_interest') or 0),
                            'volume': int(product.get('volume_24h') or product.get('volume') or 0),
                        }

                        strikes_dict[strike][option_type] = option_data

            log.info(f"[OPTIONS_CHAIN] Matched {matched_count} options, {len(strikes_dict)} unique strikes")

            strikes = sorted(strikes_dict.values(), key=lambda x: x['strike'])

            atm_strike = None
            if spot_price and strikes:
                atm_strike = min(strikes, key=lambda x: abs(x['strike'] - spot_price))['strike']

            return {
                'strikes': strikes,
                'spot': spot_price or 0,
                'atm': atm_strike,
                'underlying': underlying,
                'expiry': expiry,
                'count': len(strikes)
            }

        chain_data = _run_async(fetch())
        
        return jsonify({
            "success": True,
            **chain_data
        })
        
    except Exception as e:
        log.error(f"Error getting chain data: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@options_chain_bp.route('/strikes', methods=['GET'])
def get_strikes():
    """
    Get available strikes for an underlying and expiry
    
    Query params:
    - underlying: BTC, ETH, etc.
    - expiry: Expiration date
    """
    try:
        underlying = request.args.get('underlying', 'BTC')
        expiry = request.args.get('expiry')
        
        log.info(f"Strikes request: {underlying} {expiry}")
        
        # TODO: Implement strike fetching
        return jsonify({
            "success": True,
            "strikes": [],
            "message": "Strike data not yet implemented"
        })
        
    except Exception as e:
        log.error(f"Error getting strikes: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@options_chain_bp.route('/greeks/<symbol>', methods=['GET'])
def get_greeks(symbol):
    """Get Greeks (delta, gamma, theta, vega, rho) for an option"""
    try:
        log.info(f"Greeks request for {symbol}")
        
        # TODO: Implement Greeks calculation
        # - Fetch current spot price
        # - Get option details
        # - Calculate Greeks using Black-Scholes or other model
        
        return jsonify({
            "success": False,
            "error": "Greeks calculation not yet implemented",
            "status": 501
        }), 501
        
    except Exception as e:
        log.error(f"Error calculating Greeks: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@options_chain_bp.route('/iv/<symbol>', methods=['GET'])
def get_implied_volatility(symbol):
    """Get implied volatility for an option"""
    try:
        log.info(f"IV request for {symbol}")
        
        # TODO: Implement IV calculation/fetching
        return jsonify({
            "success": False,
            "error": "IV data not yet implemented",
            "status": 501
        }), 501
        
    except Exception as e:
        log.error(f"Error getting IV: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# Health check endpoint
@options_chain_bp.route('/health', methods=['GET'])
def health_check():
    """Health check for options chain module"""
    return jsonify({
        "success": True,
        "status": "ok",
        "module": "options_chain",
        "endpoints": {
            "expirations": "operational",
            "data": "operational",
            "refresh": "operational",
            "strikes": "stub",
            "greeks": "stub",
            "iv": "stub"
        }
    })


@options_chain_bp.route('/refresh', methods=['POST'])
def refresh_chain():
    """
    Refresh chain data (mainly for frontend - no server-side caching yet)
    
    Query params:
    - underlying: BTC, ETH, etc.
    - expiry: Optional expiry date
    """
    try:
        underlying = request.args.get('underlying', 'BTC')
        expiry = request.args.get('expiry')
        
        log.info(f"Refresh request: {underlying} {expiry if expiry else 'all expiries'}")
        
        # Currently no server-side caching, so this is a no-op
        # In future, could invalidate cache here
        
        return jsonify({
            "success": True,
            "message": "Refresh requested (no server-side cache to clear)",
            "underlying": underlying,
            "expiry": expiry
        })
        
    except Exception as e:
        log.error(f"Error refreshing chain: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
