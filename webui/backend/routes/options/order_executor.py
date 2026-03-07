"""
Order Execution Engine

Order type constants and all order placement/management functions.
Extracted from options_control.py — see docs/refactoring/OPTIONS_CONTROL_REFACTOR_PLAN.md

SEALED functions: cancel_order_with_verification, place_smart_order
Do NOT modify without UNSEAL command in AI_SEAL.md
"""

from __future__ import annotations

import asyncio
import logging

from webui.backend.sealed import sealed

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Order type constants
# ---------------------------------------------------------------------------
ORDER_TYPE_MAKER_FIRST = 'maker_first'    # Try limit at mid, fallback to market
ORDER_TYPE_MAKER_ONLY = 'maker_only'      # Only limit orders
ORDER_TYPE_MARKET_ONLY = 'market_only'    # Only market orders (fastest)
ORDER_TYPE_SSR = 'ssr'                    # SSR Order: Competitive pricing (2 ticks below best ask)

# Valid order types set for validation
VALID_ORDER_TYPES = {
    ORDER_TYPE_MAKER_FIRST, ORDER_TYPE_MAKER_ONLY, ORDER_TYPE_MARKET_ONLY, ORDER_TYPE_SSR,
    'ssr_standard', 'ssr_aggressive', 'ssr_conservative',  # Frontend SSR mode variants
}


# ---------------------------------------------------------------------------
# Order helpers
# ---------------------------------------------------------------------------

@sealed
async def cancel_order_with_verification(client, order_id, max_retries=3):
    """
    Cancel order with verification to prevent race conditions.

    SEALED — v1.0.0 — March 4, 2026
    Do not modify without UNSEAL command in AI_SEAL.md

    Returns:
        dict: {'state': 'cancelled'|'filled'|'unknown', 'safe_to_place_market': bool}
    """
    for attempt in range(max_retries):
        try:
            # Check current state first
            status = await client.rest_client.get_order(order_id)
            current_state = status.get('state', '')

            if current_state == 'filled':
                log.info(f"✅ Order {order_id} already filled")
                return {'state': 'filled', 'safe_to_place_market': False}

            if current_state == 'cancelled':
                log.info(f"✅ Order {order_id} already cancelled")
                return {'state': 'cancelled', 'safe_to_place_market': True}

            # Attempt cancellation
            await client.rest_client.cancel_order(order_id)
            await asyncio.sleep(0.3)

            # Verify cancellation
            verify_status = await client.rest_client.get_order(order_id)
            verify_state = verify_status.get('state', '')

            if verify_state == 'cancelled':
                log.info(f"✅ Order {order_id} successfully cancelled")
                return {'state': 'cancelled', 'safe_to_place_market': True}
            elif verify_state == 'filled':
                log.info(f"✅ Order {order_id} filled during cancellation")
                return {'state': 'filled', 'safe_to_place_market': False}

            # Still open, retry
            log.warning(f"⚠️ Order {order_id} still {verify_state}, retry {attempt + 1}/{max_retries}")

        except Exception as e:
            log.error(f"Cancel attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                # Last attempt failed - assume unsafe to place market order
                log.error(f"❌ All cancel attempts failed for {order_id}")
                return {'state': 'unknown', 'safe_to_place_market': False}

    # If we get here, cancellation uncertain - DO NOT place market order
    log.warning(f"⚠️ Cannot confirm cancellation of {order_id}, NOT safe for market order")
    return {'state': 'unknown', 'safe_to_place_market': False}


async def validate_order_size(client, symbol, requested_size, side, is_close=False):
    """
    Validate order size against position and exchange limits.

    Raises:
        ValueError: If order size is invalid
    """
    if requested_size <= 0:
        raise ValueError(f"Order size must be positive, got {requested_size}")

    if requested_size > 10000:
        raise ValueError(f"Order size {requested_size} exceeds maximum (10000)")

    if is_close:
        # Verify we have a position to close
        positions = await client.get_all_positions_with_options()
        position = next((p for p in positions.get('options', [])
                        if p.get('product_symbol') == symbol), None)

        if not position:
            raise ValueError(f"Cannot close non-existent position: {symbol}")

        position_size = abs(float(position.get('size', 0)))
        if requested_size > position_size:
            raise ValueError(
                f"Close size {requested_size} exceeds position size {position_size}"
            )

    return True


async def place_options_order(client, product_symbol: str, size: int, side: str,
                              order_type: str = 'limit_order', limit_price: float = None,
                              reduce_only: bool = False, post_only: bool = True,
                              mmp_level: str = None):
    """
    Place order on options contract using product_symbol.

    Delta Exchange API supports product_symbol for options contracts.
    This bypasses the need for product_id lookup.

    Args:
        client: UnifiedAPIClient instance (for rate limiting)
        product_symbol: Options symbol (e.g., C-BTC-113000-300126)
        size: Order size (positive integer)
        side: 'buy' or 'sell'
        order_type: 'limit_order' or 'market_order'
        limit_price: Price for limit orders
        reduce_only: If True, only reduces position
        post_only: If True, order will be maker-only (default True for fee rebates)
        mmp_level: Market Maker Protection level (mmp1-mmp5). If set, uses MMP tagging
                   instead of gtc time_in_force. Only for approved market makers.

    Returns:
        dict: Order response
    """
    # Build order data using product_symbol (works for options)
    data = {
        "product_symbol": product_symbol,
        "side": side,
        "order_type": order_type,
        "size": int(size)
    }

    # Market orders don't use limit_price, post_only, or time_in_force
    if order_type == 'market_order':
        if reduce_only:
            data["reduce_only"] = "true"
    else:
        # Limit order
        if limit_price is not None:
            data["limit_price"] = str(limit_price)

        # Use MMP tagging if specified, otherwise use gtc
        if mmp_level and mmp_level in ['mmp1', 'mmp2', 'mmp3', 'mmp4', 'mmp5']:
            data["time_in_force"] = mmp_level  # Market Maker Protection
            data["post_only"] = "true"  # MMP orders should always be post_only
            log.info(f"🏦 Using MMP level: {mmp_level}")
        else:
            data["time_in_force"] = "gtc"
            data["post_only"] = "true" if post_only else "false"

        if reduce_only:
            data["reduce_only"] = "true"

    log.info(f"📊 Placing {order_type}: {side} {size} {product_symbol} @ {limit_price or 'market'} (post_only={post_only}, mmp={mmp_level})")

    # Make direct API call
    response = await client.rest_client._request_with_retry(
        method="POST",
        path="/v2/orders",
        data=data
    )

    result = response.get('result', response)
    log.info(f"✅ Order placed: {result.get('id', 'unknown')}")
    return result


async def modify_order_price(client, order_id: str, product_id: int,
                            symbol: str, new_price: float, size: float,
                            side: str, reduce_only: bool = False) -> dict:
    """
    Atomically modify order price by cancelling and immediately placing new order.

    Optimized for speed - no delay between cancel and place to minimize gap.
    Returns new order details or raises exception.
    """
    rest_client = client.rest_client

    # Cancel old order
    await rest_client.cancel_order(order_id, product_id)

    # Immediately place new order (no sleep - minimize gap)
    new_order = await place_options_order(
        client, symbol, size, side,
        order_type='limit_order',
        limit_price=new_price,
        reduce_only=reduce_only,
        post_only=True
    )

    return new_order


async def fetch_fresh_orderbook_quotes(client, symbol: str) -> dict:
    """
    Fetch FRESH bid/ask from exchange L2 orderbook at order time.

    This queries the exchange directly for instantaneous prices instead of
    using potentially stale cached/websocket data (which refreshes every ~5s).

    Benefits:
    - Real-time accurate bid/ask for precise mid-price calculation
    - post_only=True orders won't get rejected due to stale prices
    - Better execution chances with current market conditions

    Returns:
        dict with: best_bid, best_ask, bid_size, ask_size, tick_size, fresh (bool)
    """
    result = {
        'best_bid': 0,
        'best_ask': 0,
        'bid_size': 0,
        'ask_size': 0,
        'tick_size': 0.01,
        'fresh': False,
        'source': 'none'
    }

    try:
        # METHOD 1: Try L2 orderbook for freshest prices (direct REST call)
        log.debug(f"🔍 Fetching fresh L2 orderbook for {symbol}")
        orderbook = await client.rest_client.get_orderbook(symbol)

        if orderbook:
            buy_orders = orderbook.get('buy', [])  # Bids
            sell_orders = orderbook.get('sell', [])  # Asks

            if buy_orders and sell_orders:
                # Top of book = freshest best bid/ask
                best_bid_entry = buy_orders[0] if buy_orders else {}
                best_ask_entry = sell_orders[0] if sell_orders else {}

                result['best_bid'] = float(best_bid_entry.get('price', 0))
                result['best_ask'] = float(best_ask_entry.get('price', 0))
                result['bid_size'] = float(best_bid_entry.get('size', 0))
                result['ask_size'] = float(best_ask_entry.get('size', 0))
                result['fresh'] = True
                result['source'] = 'l2_orderbook'
                log.info(f"📖 Fresh L2 orderbook: bid ${result['best_bid']:.2f} x {result['bid_size']}, ask ${result['best_ask']:.2f} x {result['ask_size']}")
    except Exception as e:
        log.warning(f"L2 orderbook fetch failed for {symbol}: {e}")

    # METHOD 2: Fallback to ticker if orderbook failed
    if not result['fresh'] or result['best_bid'] == 0 or result['best_ask'] == 0:
        try:
            log.debug(f"🔍 Falling back to ticker for {symbol}")
            ticker = await client.get_option_ticker(symbol)
            quotes = ticker.get('quotes', {})
            if not quotes and 'raw' in ticker:
                quotes = ticker.get('raw', {}).get('quotes', {})

            result['best_bid'] = float(quotes.get('best_bid') or 0)
            result['best_ask'] = float(quotes.get('best_ask') or 0)
            result['bid_size'] = float(quotes.get('best_bid_size') or 0)
            result['ask_size'] = float(quotes.get('best_ask_size') or 0)
            result['tick_size'] = float(ticker.get('tick_size') or ticker.get('raw', {}).get('tick_size') or 0.01)
            result['fresh'] = True
            result['source'] = 'ticker'
            log.info(f"📊 Ticker quotes: bid ${result['best_bid']:.2f}, ask ${result['best_ask']:.2f}")
        except Exception as e:
            log.warning(f"Ticker fetch also failed for {symbol}: {e}")

    return result


@sealed
async def place_smart_order(client, symbol: str, size: float, side: str,
                           order_preference: str = ORDER_TYPE_MAKER_FIRST,
                           reduce_only: bool = False,
                           limit_price: float = None):
    """
    Place order with smart execution strategy using FRESH orderbook prices.

    SEALED — v1.0.0 — March 4, 2026
    Do not modify without UNSEAL command in AI_SEAL.md

    Smart (Maker First): Post-only limit at mid-price (half of bid + ask), waits infinitely for fill
    Maker Only: Only post-only limit orders (may not fill, but guarantees fee rebates)
    Market Only: Immediate market order (highest fees)

    For SMART orders:
    - Fetches FRESH bid/ask directly from exchange L2 orderbook at order time
    - Price is set at midpoint: (best_bid + best_ask) / 2
    - Post-only order that never crosses the spread
    - Waits infinitely until filled (no market fallback)
    - Fresh prices prevent post_only rejection from stale data

    Args:
        client: UnifiedAPIClient instance
        symbol: Options symbol (e.g., C-BTC-113000-300126)
        size: Order size (positive number)
        side: 'buy' or 'sell'
        order_preference: ORDER_TYPE_MAKER_FIRST, ORDER_TYPE_MAKER_ONLY, ORDER_TYPE_MARKET_ONLY, ORDER_TYPE_SSR
        reduce_only: If True, only reduces position
        limit_price: Optional custom limit price (if None, calculates mid-price)

    Returns:
        dict: Order result with execution details
    """
    size = int(abs(float(size)))

    # Market only - fastest execution
    if order_preference == ORDER_TYPE_MARKET_ONLY:
        log.info(f"📊 MARKET order: {side} {size} {symbol}")
        order = await place_options_order(
            client, symbol, size, side,
            order_type='market_order',
            reduce_only=reduce_only,
            post_only=False
        )
        order['execution_type'] = 'market'
        return order

    # SSR order - competitive pricing with monitoring
    # Handle both legacy 'ssr' and the three frontend SSR sub-modes
    if order_preference == ORDER_TYPE_SSR or order_preference == 'ssr_standard':
        from webui.backend.routes.options.ssr_monitor import place_ssr_order as _place_ssr_order
        return await _place_ssr_order(
            client, symbol, size, side,
            reduce_only=reduce_only,
            tick_offset=2
        )

    if order_preference == 'ssr_aggressive':
        from webui.backend.routes.options.ssr_monitor import place_ssr_order_with_margin as _place_ssr_order_with_margin
        return await _place_ssr_order_with_margin(
            client, symbol, size, side,
            margin_percent=5.0,
            ssr_mode='aggressive',
            reduce_only=reduce_only
        )

    if order_preference == 'ssr_conservative':
        from webui.backend.routes.options.ssr_monitor import place_ssr_order_with_margin as _place_ssr_order_with_margin
        return await _place_ssr_order_with_margin(
            client, symbol, size, side,
            margin_percent=1.5,
            ssr_mode='conservative',
            reduce_only=reduce_only
        )

    # Fetch FRESH orderbook prices directly from exchange
    try:
        quotes = await fetch_fresh_orderbook_quotes(client, symbol)
        best_bid = quotes['best_bid']
        best_ask = quotes['best_ask']
        tick_size = quotes['tick_size']
        price_source = quotes['source']

        if best_bid == 0 or best_ask == 0:
            log.warning(f"No quotes for {symbol} (source: {price_source}), using market order")
            order = await place_options_order(
                client, symbol, size, side,
                order_type='market_order',
                reduce_only=reduce_only,
                post_only=False
            )
            order['execution_type'] = 'market_fallback_no_quotes'
            return order

        # Calculate price
        if limit_price is not None:
            # Use custom limit price but round to tick size
            price = round(float(limit_price) / tick_size) * tick_size
            log.info(f"📊 SMART order at custom ${price:.2f} (fresh bid: ${best_bid:.2f}, ask: ${best_ask:.2f}) [source: {price_source}]")
        else:
            # Calculate mid-price (half between bid and ask)
            mid_price = (best_bid + best_ask) / 2
            price = round(mid_price / tick_size) * tick_size
            log.info(f"📊 SMART order at mid-price ${price:.2f} (fresh bid: ${best_bid:.2f}, ask: ${best_ask:.2f}) [source: {price_source}]")

        # Place post-only limit order at mid-price - waits infinitely for fill (no market fallback)
        limit_order = await place_options_order(
            client, symbol, size, side,
            order_type='limit_order',
            limit_price=price,
            reduce_only=reduce_only,
            post_only=True  # Post-only at mid-price, never crosses spread
        )

        order_id = limit_order.get('id')

        # Both MAKER_FIRST and MAKER_ONLY: Return immediately, order waits infinitely for fill
        limit_order['execution_type'] = 'limit_at_mid'
        limit_order['limit_price'] = price
        limit_order['mid_price'] = price
        limit_order['best_bid'] = best_bid
        limit_order['best_ask'] = best_ask
        limit_order['price_source'] = price_source
        limit_order['bid_size'] = quotes.get('bid_size', 0)
        limit_order['ask_size'] = quotes.get('ask_size', 0)
        log.info(f"✅ SMART post-only order placed at mid-price ${price:.2f} - waiting for fill (fresh prices from {price_source})")
        return limit_order

    except Exception as e:
        log.exception(f"Smart order failed, falling back to market")  # Full traceback
        order = await place_options_order(
            client, symbol, size, side,
            order_type='market_order',
            reduce_only=reduce_only
        )
        order['execution_type'] = 'market_fallback_error'
        order['error'] = str(e)
        return order
