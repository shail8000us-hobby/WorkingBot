"""
MV Straddle API Routes
Native implementation for Delta Exchange move_options contract type

MV Straddle is a single Delta Exchange product (contract_type: move_options)
that combines ATM Call + Put premium into one tradeable instrument.

Created: January 25, 2026
"""
from flask import Blueprint, jsonify, request
import logging
import asyncio
from datetime import datetime

# Configure logging with DEBUG level
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

logger.info('[MVStraddleRoutes] Module loading...')

# Create blueprint
mv_straddle_bp = Blueprint('mv_straddle_native', __name__, url_prefix='/api/mv-straddle')
logger.info('[MVStraddleRoutes] Blueprint created with prefix: /api/mv-straddle')


def get_mv_straddle_handler():
    """Get MV Straddle handler instance (lazy initialization)"""
    try:
        import sys
        from pathlib import Path
        
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
        
        from webui.backend.options_strategy.mv_straddle_native import MVStraddleNative
        from bot.api.unified_api_client import UnifiedAPIClient
        from config.loader import get_api_credentials
        
        # Get credentials
        creds = get_api_credentials()
        
        # Initialize API client (non-blocking)
        api_client = UnifiedAPIClient(
            api_key=creds['api_key'],
            api_secret=creds['api_secret'],
            symbol='BTCUSD',
            enable_websocket=False
        )
        
        return MVStraddleNative(api_client)
    except Exception as e:
        logger.error(f"Failed to initialize MV Straddle handler: {e}", exc_info=True)
        raise


@mv_straddle_bp.route('/products', methods=['GET'])
def get_products():
    """
    Get available MV Straddle products
    
    Query params:
        underlying: BTC or ETH (default: BTC)
        state: live, upcoming, expired (default: live)
    
    Response:
        {
            "success": true,
            "products": [...],
            "count": 5
        }
    """
    try:
        underlying = request.args.get('underlying', 'BTC')
        state = request.args.get('state', 'live')
        
        handler = get_mv_straddle_handler()
        products = handler.get_available_mv_straddles(underlying, state)
        
        return jsonify({
            "success": True,
            "products": products,
            "count": len(products)
        })
        
    except Exception as e:
        logger.error(f"Error in get_products: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@mv_straddle_bp.route('/expirations', methods=['GET'])
def get_expirations():
    """
    Get available expiration dates for MV Straddle
    
    Query params:
        underlying: BTC or ETH (default: BTC)
    
    Response:
        {
            "success": true,
            "expirations": [
                {
                    "expiry": "250126",
                    "expiry_date": "2026-01-25",
                    "settlement_time": "2026-01-25T12:00:00Z",
                    "days_to_expiry": 0,
                    "label": "25 Jan 2026 (Today)"
                }
            ],
            "count": 7
        }
    """
    try:
        underlying = request.args.get('underlying', 'BTC')
        
        handler = get_mv_straddle_handler()
        expirations = handler.get_expirations(underlying)
        
        return jsonify({
            "success": True,
            "expirations": expirations,
            "count": len(expirations)
        })
        
    except Exception as e:
        logger.error(f"Error in get_expirations: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@mv_straddle_bp.route('/strikes', methods=['GET'])
def get_strikes():
    """
    Get available strikes for specific expiry
    
    Query params:
        underlying: BTC or ETH (required)
        expiry: DDMMYY format (required)
    
    Response:
        {
            "success": true,
            "strikes": [
                {
                    "strike": 89400,
                    "symbol": "MV-BTC-89400-250126",
                    "product_id": 118230,
                    "is_atm": true,
                    "distance_from_spot": -668.4
                }
            ],
            "atm_strike": 89400,
            "count": 20
        }
    """
    try:
        underlying = request.args.get('underlying', 'BTC')
        expiry = request.args.get('expiry')
        
        if not expiry:
            return jsonify({"success": False, "error": "Missing required parameter: expiry"}), 400
        
        handler = get_mv_straddle_handler()
        strikes = handler.get_strikes_for_expiry(underlying, expiry)
        
        # Get ATM strike
        atm_strike = handler.get_atm_strike(underlying, expiry)
        
        return jsonify({
            "success": True,
            "strikes": strikes,
            "atm_strike": atm_strike,
            "count": len(strikes)
        })
        
    except Exception as e:
        logger.error(f"Error in get_strikes: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@mv_straddle_bp.route('/ticker/<symbol>', methods=['GET'])
def get_ticker(symbol):
    """
    Get ticker for specific MV Straddle
    
    Path params:
        symbol: MV Straddle symbol (e.g., MV-BTC-89400-250126)
    
    Response:
        {
            "success": true,
            "ticker": {
                "symbol": "MV-BTC-89400-250126",
                "mark_price": 674.43,
                "spot_price": 88731.6,
                "strike_price": "89400",
                "quotes": {...},
                "greeks": {...},
                "volume": 70.402,
                "oi": "9.8750"
            }
        }
    """
    try:
        handler = get_mv_straddle_handler()
        ticker = handler.get_ticker(symbol)
        
        if ticker:
            return jsonify({"success": True, "ticker": ticker})
        else:
            return jsonify({"success": False, "error": "Ticker not found"}), 404
            
    except Exception as e:
        logger.error(f"Error in get_ticker: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@mv_straddle_bp.route('/preview', methods=['POST'])
def preview_order():
    """
    Preview MV Straddle order before placement
    
    Request body:
        {
            "underlying": "BTC",
            "expiry": "250126",
            "strike": 89400,  // Optional if autoStrike=true
            "side": "buy",
            "quantity": 1,
            "autoStrike": true,
            "orderType": "limit_order"
        }
    
    Response:
        {
            "success": true,
            "preview": {
                "symbol": "MV-BTC-89400-250126",
                "product_id": 118230,
                "strike": 89400,
                "side": "buy",
                "quantity": 1,
                "mark_price": 674.43,
                "estimated_cost": 674.43,
                "ticker": {...},
                "greeks": {...},
                "iv": 0.18134344,
                "spot_price": 88731.6
            }
        }
    """
    try:
        data = request.json
        logger.info(f"📊 MV Straddle preview request: {data}")
        
        underlying = data.get('underlying', 'BTC')
        expiry = data.get('expiry')
        strike = data.get('strike')
        side = data.get('side', 'buy')
        quantity = data.get('quantity', 1)
        auto_strike = data.get('autoStrike', True)
        
        if not expiry:
            return jsonify({"success": False, "error": "Missing required parameter: expiry"}), 400
        
        handler = get_mv_straddle_handler()
        
        # Get strike (auto or manual)
        if auto_strike or not strike:
            strike = handler.get_atm_strike(underlying, expiry)
            if not strike:
                return jsonify({"success": False, "error": "Could not determine ATM strike"}), 400
        
        # Build symbol
        symbol = f"MV-{underlying}-{strike}-{expiry}"
        
        # Get ticker
        ticker = handler.get_ticker(symbol)
        if not ticker:
            return jsonify({"success": False, "error": f"No ticker data for {symbol}"}), 404
        
        # Get product details
        product = handler.get_mv_straddle_by_symbol(symbol)
        if not product:
            return jsonify({"success": False, "error": f"Product not found: {symbol}"}), 404
        
        # Calculate estimated cost
        mark_price = float(ticker.get('mark_price', 0))
        estimated_cost = mark_price * quantity
        
        # Extract bid/ask from quotes
        quotes = ticker.get('quotes', {})
        best_bid = float(quotes.get('best_bid', 0)) if quotes.get('best_bid') else None
        best_ask = float(quotes.get('best_ask', 0)) if quotes.get('best_ask') else None
        last_price = float(ticker.get('close', mark_price))
        
        # Build preview
        preview = {
            "symbol": symbol,
            "product_id": product.get('id'),
            "strike": strike,
            "side": side,
            "quantity": quantity,
            "mark_price": mark_price,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "last_price": last_price,
            "estimated_cost": round(estimated_cost, 2),
            "ticker": ticker,
            "greeks": ticker.get('greeks', {}),
            "iv": ticker.get('quotes', {}).get('mark_iv', 0),
            "spot_price": ticker.get('spot_price', 0),
            "contract_value": product.get('contract_value', 0.001),
            "settlement_time": product.get('settlement_time')
        }
        
        logger.info(f"✅ Preview generated for {symbol}")
        return jsonify({"success": True, "preview": preview})
        
    except Exception as e:
        logger.error(f"❌ Error in preview_order: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@mv_straddle_bp.route('/order', methods=['POST'])
def place_order():
    """
    Place MV Straddle order
    
    Request body:
        {
            "symbol": "MV-BTC-89400-250126",
            "side": "buy",
            "quantity": 1,
            "orderType": "limit_order",
            "limitPrice": 674.5
        }
    
    Response:
        {
            "success": true,
            "order": {
                "id": 123456789,
                "product_symbol": "MV-BTC-89400-250126",
                "size": 1,
                "side": "buy",
                "limit_price": "674.5",
                "state": "open",
                "order_type": "limit_order"
            }
        }
    """
    try:
        data = request.json
        logger.info(f"🚀 MV Straddle order request: {data}")
        
        symbol = data.get('symbol')
        side = data.get('side')
        quantity = data.get('quantity', 1)
        order_type = data.get('orderType', 'limit_order')
        limit_price = data.get('limitPrice')
        
        if not symbol:
            return jsonify({"success": False, "error": "Missing required parameter: symbol"}), 400
        
        if not side or side not in ['buy', 'sell']:
            return jsonify({"success": False, "error": "Invalid side (must be buy or sell)"}), 400
        
        if order_type == 'limit_order' and not limit_price:
            return jsonify({"success": False, "error": "Limit price required for limit orders"}), 400
        
        handler = get_mv_straddle_handler()
        
        result = asyncio.run(handler.place_order(
            symbol=symbol,
            side=side,
            size=quantity,
            order_type=order_type,
            limit_price=limit_price
        ))
        
        if result.get('success'):
            logger.info(f"✅ Order placed successfully: {result.get('order', {}).get('id')}")
            return jsonify(result)
        else:
            logger.error(f"❌ Order failed: {result.get('error')}")
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"❌ Error in place_order: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@mv_straddle_bp.route('/pnl', methods=['POST'])
def calculate_pnl():
    """
    Calculate P&L for MV Straddle position
    
    Request body:
        {
            "symbol": "MV-BTC-89400-250126",
            "entry_price": 674.5,
            "size": 10,
            "side": "buy"
        }
    
    Response:
        {
            "success": true,
            "pnl": {
                "pnl": 0.255,
                "pnl_usd": 22500.0,
                "pnl_pct": 3.79,
                "unrealized_pnl": 0.255
            }
        }
    """
    try:
        data = request.json
        
        symbol = data.get('symbol')
        entry_price = data.get('entry_price')
        size = data.get('size')
        side = data.get('side')
        
        if not all([symbol, entry_price, size, side]):
            return jsonify({"success": False, "error": "Missing required parameters"}), 400
        
        handler = get_mv_straddle_handler()
        
        # Get current ticker
        ticker = handler.get_ticker(symbol)
        if not ticker:
            return jsonify({"success": False, "error": "Could not fetch current price"}), 404
        
        current_price = float(ticker.get('mark_price', 0))
        
        # Calculate P&L
        pnl = handler.calculate_pnl(
            entry_price=entry_price,
            current_price=current_price,
            size=size,
            side=side
        )
        
        return jsonify({"success": True, "pnl": pnl})
        
    except Exception as e:
        logger.error(f"Error in calculate_pnl: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@mv_straddle_bp.route('/positions', methods=['GET'])
def get_positions():
    """
    Get MV Straddle positions from Delta Exchange
    
    Response:
        {
            "success": true,
            "positions": [...],
            "count": 2
        }
    """
    try:
        # Get handler which has the API client
        handler = get_mv_straddle_handler()
        
        # Get all positions via the API client
        async def fetch_positions():
            return await handler.api_client.get_all_positions_with_options()
        
        # Run async function
        result = asyncio.run(fetch_positions())
        
        # MV positions are classified as "futures" by the API client
        # because they don't start with C- or P-
        all_positions = result.get('futures', []) + result.get('options', [])
        
        # Filter for MV Straddle positions (symbol starts with 'MV-')
        mv_positions = []
        for pos in all_positions:
            if isinstance(pos, dict):
                symbol = pos.get('product_symbol', '') or pos.get('symbol', '')
                if isinstance(symbol, str) and symbol.startswith('MV-'):
                    # Enrich position with current ticker data
                    ticker = handler.get_ticker(symbol)
                    if ticker:
                        pos['mark_price'] = ticker.get('mark_price')
                        # best_bid and best_ask are nested inside 'quotes' in Delta Exchange API
                        quotes = ticker.get('quotes', {})
                        pos['best_bid'] = quotes.get('best_bid') or ticker.get('best_bid')
                        pos['best_ask'] = quotes.get('best_ask') or ticker.get('best_ask')
                        # Also add IV for display
                        pos['iv'] = quotes.get('mark_iv') or ticker.get('iv')
                    mv_positions.append(pos)
        
        logger.info(f"Found {len(mv_positions)} MV Straddle positions out of {len(all_positions)} total")
        
        return jsonify({
            "success": True,
            "positions": mv_positions,
            "count": len(mv_positions)
        })
        
    except Exception as e:
        logger.error(f"Error fetching MV positions: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e), "positions": [], "count": 0}), 200


@mv_straddle_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "success": True,
        "service": "MV Straddle Native",
        "timestamp": datetime.now().isoformat(),
        "status": "operational"
    })
