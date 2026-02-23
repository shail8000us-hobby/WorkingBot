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


def _run_async(coro):
    """Run async coroutine without closing the event loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

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
        
        result = _run_async(handler.place_order(
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
        result = _run_async(fetch_positions())
        
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


# ============================================================================
# SSR Order Support for MV Straddle
# ============================================================================

# SSR Order tracking for MV Straddle
_mv_active_ssr_orders = {}

@mv_straddle_bp.route('/order/ssr', methods=['POST'])
def place_ssr_order():
    """
    Place SSR (Stealth Sniper Repricing) order for MV Straddle
    
    Request body:
        {
            "symbol": "MV-BTC-89400-250126",
            "side": "buy" or "sell",
            "quantity": 1,
            "ssrMode": "standard" | "aggressive" | "conservative",
            "marginPercent": 3.0  // Optional: override default margin
        }
    
    SSR Modes:
        - standard: 1 tick below 2nd best (default SSR behavior)
        - aggressive: Premium-based dynamic margin (3-8% below 2nd best)
        - conservative: 1-2% below 2nd best
    
    Response:
        {
            "success": true,
            "order": {...},
            "ssrTracking": {
                "orderId": 123456,
                "mode": "aggressive",
                "margin": 5.0
            }
        }
    """
    import threading
    
    try:
        data = request.json
        logger.info(f"🏎️ MV Straddle SSR order request: {data}")
        
        symbol = data.get('symbol')
        side = data.get('side')
        quantity = data.get('quantity', 1)
        ssr_mode = data.get('ssrMode', 'standard')
        margin_override = data.get('marginPercent')
        
        if not symbol:
            return jsonify({"success": False, "error": "Missing required parameter: symbol"}), 400
        
        if not side or side not in ['buy', 'sell']:
            return jsonify({"success": False, "error": "Invalid side (must be buy or sell)"}), 400
        
        handler = get_mv_straddle_handler()
        
        # Get current ticker for price calculation
        ticker = handler.get_ticker(symbol)
        if not ticker:
            return jsonify({"success": False, "error": f"Could not get ticker for {symbol}"}), 400
        
        quotes = ticker.get('quotes', {})
        best_bid = float(quotes.get('best_bid') or ticker.get('best_bid') or 0)
        best_ask = float(quotes.get('best_ask') or ticker.get('best_ask') or 0)
        mark_price = float(ticker.get('mark_price') or 0)
        
        # Get product info for tick size
        product = handler.get_mv_straddle_by_symbol(symbol)
        tick_size = float(product.get('tick_size', '0.1')) if product else 0.1
        
        # Initialize margin_pct for tracking (standard mode doesn't use percentage)
        margin_pct = 0
        
        # Calculate SSR price based on mode
        if side == 'buy':
            # For BUYING: Start at/below best bid to get filled
            reference_price = best_bid if best_bid > 0 else mark_price
            
            if ssr_mode == 'aggressive':
                # Premium-based aggressive pricing
                margin_pct = _calculate_aggressive_margin(mark_price, margin_override)
                ssr_price = reference_price * (1 - margin_pct / 100)
            elif ssr_mode == 'conservative':
                # 1-2% below reference
                margin_pct = margin_override if margin_override else 1.5
                ssr_price = reference_price * (1 - margin_pct / 100)
            else:  # standard
                # 2 ticks below best bid
                ssr_price = reference_price - (2 * tick_size)
        else:
            # For SELLING: Start at/above best ask to compete
            reference_price = best_ask if best_ask > 0 else mark_price
            
            if ssr_mode == 'aggressive':
                margin_pct = _calculate_aggressive_margin(mark_price, margin_override)
                ssr_price = reference_price * (1 + margin_pct / 100)
            elif ssr_mode == 'conservative':
                margin_pct = margin_override if margin_override else 1.5
                ssr_price = reference_price * (1 + margin_pct / 100)
            else:  # standard
                ssr_price = reference_price + (2 * tick_size)
        
        # Round to tick size
        ssr_price = round(ssr_price / tick_size) * tick_size
        ssr_price = max(tick_size, ssr_price)  # Ensure minimum price
        
        logger.info(f"🏎️ SSR Price Calculation: mode={ssr_mode}, ref=${reference_price:.2f} -> SSR=${ssr_price:.2f}")
        
        # Place initial limit order
        result = _run_async(handler.place_order(
            symbol=symbol,
            side=side,
            size=quantity,
            order_type="limit_order",
            limit_price=ssr_price
        ))
        
        if not result.get('success'):
            return jsonify(result), 400
        
        order = result.get('order', {})
        # Order ID can be in order.id or order.result.id depending on response format
        order_result = order.get('result', order)
        order_id = order_result.get('id')
        product_id = order_result.get('product_id')
        
        # Start SSR monitoring thread
        if order_id:
            from config.loader import get_api_credentials
            creds = get_api_credentials()
            
            # Store tracking info
            _mv_active_ssr_orders[order_id] = {
                'symbol': symbol,
                'side': side,
                'size': quantity,
                'mode': ssr_mode,
                'margin': margin_override or margin_pct,
                'initial_price': ssr_price,
                'current_price': ssr_price,
                'product_id': product_id,
                'started_at': datetime.now().isoformat(),
                'status': 'active',
                'adjustments': 0
            }
            
            # Start monitoring in background thread
            thread = threading.Thread(
                target=_run_mv_ssr_monitoring_loop,
                args=(creds, symbol, quantity, side, order_id, ssr_mode, tick_size, product_id),
                daemon=True
            )
            thread.start()
            logger.info(f"🏎️ Started SSR monitoring thread for order {order_id} (product_id={product_id})")
        
        return jsonify({
            "success": True,
            "order": order,
            "ssrTracking": {
                "orderId": order_id,
                "mode": ssr_mode,
                "initialPrice": ssr_price,
                "tickSize": tick_size
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Error in SSR order: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


def _calculate_aggressive_margin(premium: float, override: float = None) -> float:
    """
    Calculate aggressive margin based on premium level.
    
    Premium Range     | Margin (from 2nd best)
    --------------------------------------------------
    $0 - $50          | 5-8% (very aggressive)
    $50 - $200        | 3-5% (aggressive)
    $200 - $500       | 2-3% (moderate)
    $500+             | 1-2% (conservative)
    
    Args:
        premium: Current premium/price
        override: Optional override margin percent
        
    Returns:
        Margin percentage to apply
    """
    if override is not None:
        return float(override)
    
    if premium <= 50:
        return 6.5  # Very aggressive
    elif premium <= 200:
        return 4.0  # Aggressive
    elif premium <= 500:
        return 2.5  # Moderate
    else:
        return 1.5  # Conservative


def _run_mv_ssr_monitoring_loop(client_config, symbol: str, size: int, side: str,
                                 order_id: int, ssr_mode: str, tick_size: float, product_id: int):
    """
    Background thread function to monitor and adjust MV Straddle SSR orders.
    Similar to options SSR but adapted for MV Straddle products.
    """
    import time
    import asyncio
    
    print(f"[MV-SSR THREAD] Started monitoring for order {order_id} (product_id={product_id})")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        async def monitoring_loop():
            global _mv_active_ssr_orders
            from bot.api.async_delta_client import AsyncDeltaClient
            
            client = AsyncDeltaClient(
                api_key=client_config['api_key'],
                api_secret=client_config['api_secret'],
                testnet=client_config.get('testnet', False)
            )
            
            adjustments = 0
            start_time = time.time()
            current_price = _mv_active_ssr_orders.get(order_id, {}).get('initial_price', 0)
            
            while True:
                try:
                    elapsed = time.time() - start_time
                    
                    # Check if order is still active
                    if order_id not in _mv_active_ssr_orders:
                        print(f"[MV-SSR THREAD] Order {order_id} removed from tracking, stopping")
                        break
                    
                    if _mv_active_ssr_orders[order_id].get('status') == 'cancelled':
                        print(f"[MV-SSR THREAD] Order {order_id} cancelled, stopping")
                        break
                    
                    # Get order status
                    order_status = await client.get_order(str(order_id))
                    if not order_status:
                        await asyncio.sleep(2)
                        continue
                    
                    state = order_status.get('state', '') if isinstance(order_status, dict) else ''
                    
                    if state == 'filled':
                        print(f"[MV-SSR THREAD] ✅ Order {order_id} FILLED!")
                        _mv_active_ssr_orders[order_id]['status'] = 'filled'
                        break
                    elif state in ('cancelled', 'rejected'):
                        print(f"[MV-SSR THREAD] ❌ Order {order_id} {state}")
                        _mv_active_ssr_orders[order_id]['status'] = state
                        break
                    
                    # Get current orderbook
                    orderbook = await client.get_orderbook(symbol)
                    if not orderbook:
                        await asyncio.sleep(2)
                        continue
                    
                    # Calculate new SSR price
                    if side == 'buy':
                        bids = orderbook.get('buy', [])
                        if len(bids) >= 2:
                            second_best_bid = float(bids[1].get('price', 0))
                            new_price = second_best_bid - tick_size
                        else:
                            new_price = current_price
                    else:
                        asks = orderbook.get('sell', [])
                        if len(asks) >= 2:
                            second_best_ask = float(asks[1].get('price', 0))
                            new_price = second_best_ask + tick_size
                        else:
                            new_price = current_price
                    
                    # Round to tick size
                    new_price = round(new_price / tick_size) * tick_size
                    
                    # Only amend if price changed significantly
                    if abs(new_price - current_price) >= tick_size:
                        print(f"[MV-SSR THREAD] Adjusting order {order_id}: ${current_price:.2f} -> ${new_price:.2f}")
                        
                        # Use edit_order with product_id
                        edit_result = await client.edit_order(str(order_id), product_id, str(new_price))
                        if edit_result:
                            current_price = new_price
                            adjustments += 1
                            
                            _mv_active_ssr_orders[order_id].update({
                                'current_price': current_price,
                                'adjustments': adjustments,
                                'last_adjusted': datetime.now().isoformat()
                            })
                    
                    # Log status periodically
                    if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                        print(f"[MV-SSR THREAD] Order {order_id}: {elapsed:.0f}s, {adjustments} adjustments, ${current_price:.2f}")
                    
                    await asyncio.sleep(2)  # Check every 2 seconds
                    
                except Exception as e:
                    print(f"[MV-SSR THREAD] Error in loop: {e}")
                    await asyncio.sleep(5)
            
            print(f"[MV-SSR THREAD] Stopped monitoring order {order_id} after {adjustments} adjustments")
        
        loop.run_until_complete(monitoring_loop())
        
    except Exception as e:
        print(f"[MV-SSR THREAD] Fatal error: {e}")
    finally:
        pass  # Don't close loop - may be reused


@mv_straddle_bp.route('/order/ssr/<int:order_id>', methods=['GET'])
def get_ssr_order_status(order_id):
    """Get status of an SSR order"""
    if order_id in _mv_active_ssr_orders:
        return jsonify({
            "success": True,
            "order": _mv_active_ssr_orders[order_id]
        })
    else:
        return jsonify({
            "success": False,
            "error": f"SSR order {order_id} not found in tracking"
        }), 404


@mv_straddle_bp.route('/order/ssr/<int:order_id>/cancel', methods=['POST'])
def cancel_ssr_order(order_id):
    """Cancel an SSR order and stop monitoring"""
    try:
        handler = get_mv_straddle_handler()
        
        # Get product_id from tracking or by looking up the symbol
        product_id = None
        if order_id in _mv_active_ssr_orders:
            _mv_active_ssr_orders[order_id]['status'] = 'cancelled'
            # Get product info from symbol
            symbol = _mv_active_ssr_orders[order_id].get('symbol')
            if symbol:
                product = handler.get_mv_straddle_by_symbol(symbol)
                product_id = product.get('id') if product else None
        
        if not product_id:
            # Fallback: try to get from open orders
            return jsonify({
                "success": False,
                "error": f"Cannot cancel: product_id not found for order {order_id}"
            }), 400
        
        # Cancel the order on exchange
        result = _run_async(handler.api_client.cancel_order(str(order_id), product_id=product_id))
        
        return jsonify({
            "success": True,
            "message": f"SSR order {order_id} cancelled",
            "result": result
        })
        
    except Exception as e:
        logger.error(f"Error cancelling SSR order: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@mv_straddle_bp.route('/order/ssr/active', methods=['GET'])
def get_active_ssr_orders():
    """Get all active SSR orders for MV Straddle"""
    return jsonify({
        "success": True,
        "orders": _mv_active_ssr_orders,
        "count": len(_mv_active_ssr_orders)
    })


@mv_straddle_bp.route('/activity-log', methods=['GET'])
def get_activity_log():
    """
    Get comprehensive activity log for MV Straddle including:
    - SSR order tracking status
    - Recent orders placed
    - Max loss monitoring status
    - Order type breakdown
    """
    try:
        from pathlib import Path
        
        # SSR Orders Status
        ssr_orders = []
        for order_id, tracking in _mv_active_ssr_orders.items():
            ssr_orders.append({
                'orderId': order_id,
                'symbol': tracking.get('symbol', ''),
                'side': tracking.get('side', ''),
                'mode': tracking.get('mode', 'standard'),
                'initialPrice': tracking.get('initial_price', 0),
                'currentPrice': tracking.get('current_price', 0),
                'adjustments': tracking.get('adjustments', 0),
                'status': tracking.get('status', 'unknown'),
                'startedAt': tracking.get('started_at', ''),
                'lastAdjusted': tracking.get('last_adjusted', '')
            })
        
        # Get recent log entries from file
        log_file = Path(__file__).parent.parent.parent / 'logs' / 'launchagent_webui.log'
        recent_logs = []
        
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Get MV Straddle related logs
                keywords = ['MV-', 'SSR', 'mv-straddle', 'move_options', 'MV Straddle']
                for line in lines[-500:]:
                    line_stripped = line.strip()
                    if any(kw in line_stripped for kw in keywords):
                        recent_logs.append({
                            'message': line_stripped[:200],  # Truncate long lines
                            'type': 'ssr' if 'SSR' in line_stripped else 'order' if 'order' in line_stripped.lower() else 'info'
                        })
                
                recent_logs = recent_logs[-50:]  # Last 50
            except Exception as e:
                logger.error(f"Failed to read log file: {e}")
        
        return jsonify({
            "success": True,
            "ssrOrders": ssr_orders,
            "ssrCount": len(ssr_orders),
            "recentLogs": recent_logs,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting activity log: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

