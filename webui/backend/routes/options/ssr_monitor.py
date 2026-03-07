"""
SSR (Stealth Sniper Repricing) Order Monitor

Active SSR order registry, monitoring threads, and SSR order placement.
Extracted from options_control.py — see docs/refactoring/OPTIONS_CONTROL_REFACTOR_PLAN.md

DO NOT touch the SSR monitoring logic (which ticks, how price is calculated, when it stops).
Only the container was moved here.
"""

from __future__ import annotations

import asyncio
import threading
import time
import traceback
import logging

from .order_executor import fetch_fresh_orderbook_quotes, place_options_order

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSR Order registry — thread-safe shared state
# ---------------------------------------------------------------------------
# Format: {order_id: {'symbol': str, 'status': str, 'adjustments': int,
#                     'current_price': float, 'start_time': float}}
_active_ssr_orders: dict = {}
_ssr_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Thread-safe accessors (public API)
# ---------------------------------------------------------------------------

def get_active_ssr_orders() -> list:
    """Return a snapshot of all active SSR orders (thread-safe)."""
    with _ssr_lock:
        result = []
        for order_id, info in _active_ssr_orders.items():
            elapsed = time.time() - info.get('start_time', time.time())
            result.append({
                'order_id': order_id,
                'symbol': info.get('symbol'),
                'side': info.get('side'),
                'size': info.get('size'),
                'current_price': info.get('current_price'),
                'adjustments': info.get('adjustments', 0),
                'status': info.get('status', 'unknown'),
                'elapsed_seconds': round(elapsed, 1),
                'max_duration': info.get('max_duration', 120)
            })
    return result


def register_ssr_order(order_id, info: dict):
    """Register a new SSR order in the tracking dict."""
    with _ssr_lock:
        _active_ssr_orders[order_id] = info


def update_ssr_order(order_id, **kwargs):
    """Update fields on an existing SSR order entry."""
    with _ssr_lock:
        if order_id in _active_ssr_orders:
            _active_ssr_orders[order_id].update(kwargs)


def remove_ssr_order(order_id):
    """Remove an SSR order from tracking."""
    with _ssr_lock:
        _active_ssr_orders.pop(order_id, None)


# ---------------------------------------------------------------------------
# SSR monitoring threads
# ---------------------------------------------------------------------------

def _run_ssr_monitoring_loop(client_config, symbol: str, size: int, side: str,
                              order_id: str, initial_price: float, tick_size: float,
                              reduce_only: bool = False,
                              max_duration: int = 120,
                              check_interval: float = 2.0,
                              tick_offset: int = 2):
    """
    Background thread function to monitor and adjust SSR orders.
    Runs in a separate thread with its own event loop.

    CRITICAL: Must create httpx.AsyncClient INSIDE the async context
    to avoid "Event loop is closed" or "attached to different loop" errors.
    """
    print(f"[SSR THREAD] _run_ssr_monitoring_loop STARTED for order {order_id}")
    from config.loader import get_api_credentials

    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    print(f"[SSR THREAD] Created new event loop for order {order_id}")

    async def monitoring_loop():
        nonlocal order_id

        print(f"[SSR THREAD] monitoring_loop async function started for {order_id}")

        # CRITICAL FIX: Create AsyncDeltaClient DIRECTLY here, inside the async context
        # The httpx.AsyncClient MUST be created in the same event loop it will be used in
        # Using UnifiedAPIClient failed because httpx client was bound to wrong loop
        from bot.api.async_delta_client import AsyncDeltaClient
        creds = get_api_credentials()

        # Determine testnet setting (default to False for production)
        testnet = creds.get('testnet', False)
        if testnet is None:
            testnet = False

        print(f"[SSR THREAD] Creating AsyncDeltaClient for {order_id}, testnet={testnet}")

        # Create fresh REST client in THIS event loop
        rest_client = AsyncDeltaClient(
            api_key=creds.get('api_key', ''),
            api_secret=creds.get('api_secret', ''),
            testnet=testnet
        )

        print(f"[SSR THREAD] AsyncDeltaClient created successfully for {order_id}")
        log.info(f"🔧 SSR Monitor: Created fresh AsyncDeltaClient (testnet={testnet})")

        current_price = initial_price
        adjustments = 0
        start_time = time.time()

        # NO TIMEOUT - runs until filled or cancelled for low liquidity far-expiry options
        log.info(f"🏎️ SSR MONITOR STARTED: {order_id} at ${current_price:.2f} - will chase INDEFINITELY until filled/cancelled")

        try:
            while True:
                elapsed = time.time() - start_time
                print(f"[SSR THREAD] Loop iteration: order {order_id}, elapsed={elapsed:.1f}s, adjustments={adjustments}")

                # Update tracking
                with _ssr_lock:
                    if order_id in _active_ssr_orders:
                        _active_ssr_orders[order_id].update({
                            'current_price': current_price,
                            'adjustments': adjustments,
                            'elapsed': round(elapsed, 1),
                            'status': 'monitoring'
                        })

                # NO TIMEOUT - continue until filled/cancelled
                # Log progress every 60 seconds
                if adjustments > 0 and elapsed % 60 < check_interval:
                    log.info(f"🔄 SSR still active: {order_id} at ${current_price:.2f} ({elapsed:.0f}s, {adjustments} adjustments)")

                # Wait before next check
                await asyncio.sleep(check_interval)

                # Check order status
                try:
                    print(f"[SSR THREAD] Checking order status for {order_id}...")
                    order_status = await rest_client.get_order(order_id)
                    print(f"[SSR THREAD] Order status response: {order_status}")

                    # Handle empty/failed response - keep monitoring
                    if not order_status:
                        log.warning(f"SSR: Empty order status response for {order_id}, continuing...")
                        print(f"[SSR THREAD] Empty response, continuing...")
                        continue

                    state = order_status.get('state', '')
                    print(f"[SSR THREAD] Order state: '{state}'")

                    # Handle empty state - could be API issue, keep monitoring
                    if not state:
                        log.warning(f"SSR: Empty state for order {order_id}, response: {order_status}, continuing...")
                        print(f"[SSR THREAD] Empty state, continuing...")
                        continue

                    if state == 'filled':
                        log.info(f"🎉 SSR FILLED: {order_id} at ${current_price:.2f} after {elapsed:.1f}s, {adjustments} adjustments")
                        with _ssr_lock:
                            if order_id in _active_ssr_orders:
                                _active_ssr_orders[order_id]['status'] = 'filled'
                        return

                    if state == 'cancelled':
                        log.warning(f"⚠️ SSR cancelled externally: {order_id}")
                        with _ssr_lock:
                            if order_id in _active_ssr_orders:
                                _active_ssr_orders[order_id]['status'] = 'cancelled'
                        return

                    if state not in ('open', 'pending'):
                        log.warning(f"⚠️ SSR order state: {state} - stopping (full response: {order_status})")
                        break

                    # Update current_price and tick_size from order status (authoritative source)
                    actual_limit_price = order_status.get('limit_price')
                    if actual_limit_price:
                        current_price = float(actual_limit_price)

                    # Get tick_size and product_id from product data in order status
                    product_data = order_status.get('product', {})
                    product_tick = product_data.get('tick_size')
                    if product_tick:
                        tick_size = float(product_tick)
                        print(f"[SSR THREAD] Updated from order: current_price=${current_price}, tick_size=${tick_size}")

                    # Get product_id for cancel operation
                    product_id = order_status.get('product_id')

                except Exception as e:
                    log.error(f"Error checking SSR order status: {e}")
                    continue

                # Fetch fresh orderbook and check if we need to adjust
                try:
                    print(f"[SSR THREAD] Fetching L2 orderbook for {symbol}...")
                    # Get full L2 orderbook to find second-best price
                    orderbook_data = await rest_client.get_orderbook(symbol, depth=20)
                    buy_orders = orderbook_data.get('buy', [])
                    sell_orders = orderbook_data.get('sell', [])
                    new_tick = tick_size

                    print(f"[SSR THREAD] Orderbook depth: {len(buy_orders)} bids, {len(sell_orders)} asks, tick=${new_tick}")

                    if not buy_orders or not sell_orders:
                        print(f"[SSR THREAD] Empty orderbook, skipping...")
                        continue

                    # Re-derive best bid / ask from fresh orderbook
                    # Strategy (consistent with initial placement):
                    #   SELL: target = best_ask - (tick_offset * tick_size)  → most competitive ask
                    #   BUY:  target = best_bid + (tick_offset * tick_size)  → most competitive bid
                    # This guarantees we are always tick_offset ticks inside the spread,
                    # matching the initial placement logic and the user's design requirement.

                    best_bid_now = float(buy_orders[0]['price']) if buy_orders else 0
                    best_ask_now = float(sell_orders[0]['price']) if sell_orders else 0

                    if best_bid_now == 0 or best_ask_now == 0:
                        print(f"[SSR THREAD] Could not read best bid/ask from orderbook, skipping...")
                        continue

                    if side == 'sell':
                        new_target = best_ask_now - (tick_offset * new_tick)
                        new_target = max(new_target, best_bid_now + new_tick)  # Never cross the spread
                        print(f"[SSR THREAD] SELL: best_ask=${best_ask_now}, target=${new_target} ({tick_offset} ticks inside), current=${current_price}")
                    else:  # buy
                        new_target = best_bid_now + (tick_offset * new_tick)
                        new_target = min(new_target, best_ask_now - new_tick)  # Never cross the spread
                        print(f"[SSR THREAD] BUY: best_bid=${best_bid_now}, target=${new_target} ({tick_offset} ticks inside), current=${current_price}")

                    new_price = round(new_target / new_tick) * new_tick

                    print(f"[SSR THREAD] Price calc: current=${current_price}, target=${new_target}, new_price=${new_price}")

                    # Check if adjustment needed - adjust if price differs by at least 1 tick
                    price_diff = abs(new_price - current_price)

                    print(f"[SSR THREAD] Price diff: ${price_diff:.2f}, tick=${new_tick}, needs_adjust={price_diff >= new_tick}")

                    # Adjust if price differs by at least 1 tick in EITHER direction
                    if price_diff >= new_tick:
                        print(f"[SSR THREAD] WILL ADJUST: ${current_price:.2f} → ${new_price:.2f}")
                        log.info(f"🔄 SSR PRICE UPDATE: ${current_price:.2f} → ${new_price:.2f} [staying 1 tick ahead of competition]")

                        # Directly edit order price (no cancellation - just price modification)
                        try:
                            print(f"[SSR THREAD] Editing order {order_id} price: ${current_price} → ${new_price}")
                            edited_order = await rest_client.edit_order(
                                order_id,
                                product_id,
                                str(new_price)
                            )

                            # Order ID stays the same when editing
                            current_price = new_price
                            adjustments += 1
                            log.info(f"✅ SSR price adjusted #{adjustments}: {order_id} now at ${current_price:.2f}")
                            print(f"[SSR THREAD] Price updated successfully - same order ID {order_id}")

                            # Update tracking (order_id unchanged)
                            with _ssr_lock:
                                if order_id in _active_ssr_orders:
                                    _active_ssr_orders[order_id]['current_price'] = current_price
                                    _active_ssr_orders[order_id]['adjustments'] = adjustments
                                    _active_ssr_orders[order_id]['elapsed'] = round(elapsed, 1)

                        except Exception as e:
                            log.error(f"Failed to edit order price: {e}")
                            print(f"[SSR THREAD] ERROR editing order price: {e}")
                            continue  # Try again next iteration instead of breaking

                    else:
                        print(f"[SSR THREAD] No adjustment needed (diff ${price_diff:.2f} < tick ${new_tick})")

                except Exception as e:
                    log.error(f"Error in SSR monitoring: {e}")
                    print(f"[SSR THREAD] ERROR in orderbook/price calc: {e}")
                    traceback.print_exc()
                    continue

            # Monitoring ended
            log.info(f"📊 SSR monitor ended: {order_id} at ${current_price:.2f} ({adjustments} adjustments)")
            with _ssr_lock:
                if order_id in _active_ssr_orders:
                    _active_ssr_orders[order_id]['status'] = 'ended'

        except Exception as e:
            log.exception(f"SSR monitor error: {e}")
            with _ssr_lock:
                if order_id in _active_ssr_orders:
                    _active_ssr_orders[order_id]['status'] = 'error'
        finally:
            # Close the REST client to clean up connections
            try:
                await rest_client.close()
                log.debug(f"🔧 SSR Monitor: Closed AsyncDeltaClient for {order_id}")
            except Exception as e:
                log.debug(f"Error closing rest_client: {e}")

            # Clean up old entries after a delay
            await asyncio.sleep(60)
            with _ssr_lock:
                if order_id in _active_ssr_orders:
                    del _active_ssr_orders[order_id]

    loop.run_until_complete(monitoring_loop())


def _run_ssr_margin_monitoring_loop(client_config, symbol: str, size: int, side: str,
                                    order_id: int, initial_price: float, tick_size: float,
                                    reduce_only: bool = False,
                                    check_interval: float = 2.0,
                                    margin_percent: float = 5.0,
                                    ssr_mode: str = 'aggressive'):
    """
    Background thread function to monitor and adjust SSR orders with margin-based pricing.
    """
    print(f"[SSR {ssr_mode.upper()} THREAD] Started for order {order_id}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        async def monitoring_loop():
            from bot.api.async_delta_client import AsyncDeltaClient
            from config.loader import get_api_credentials

            creds = get_api_credentials()
            testnet = client_config.get('testnet', creds.get('testnet', False))
            if testnet is None:
                testnet = False
            async_client = AsyncDeltaClient(
                api_key=creds.get('api_key', ''),
                api_secret=creds.get('api_secret', ''),
                testnet=testnet
            )

            adjustments = 0
            current_price = initial_price

            log.info(f"🏎️ SSR {ssr_mode} MONITOR STARTED: {order_id} at ${current_price:.2f}")

            while True:
                try:
                    # Check if order is still active
                    order_info = await async_client.get_order(order_id)
                    order_state = order_info.get('state', 'unknown')

                    if order_state in ['closed', 'cancelled', 'filled']:
                        log.info(f"✅ SSR {ssr_mode} order {order_id} completed: {order_state}")
                        with _ssr_lock:
                            if order_id in _active_ssr_orders:
                                _active_ssr_orders[order_id]['status'] = order_state
                        break

                    # Fetch fresh orderbook
                    quotes = await fetch_fresh_orderbook_quotes(async_client, symbol)
                    best_bid = quotes['best_bid']
                    best_ask = quotes['best_ask']

                    # Recalculate target price
                    if side == 'sell':
                        reference_price = best_ask
                        new_target = reference_price * (1 - margin_percent / 100)
                        new_target = max(new_target, best_bid + tick_size)  # Don't cross spread
                    else:
                        reference_price = best_bid
                        new_target = reference_price * (1 + margin_percent / 100)
                        new_target = min(new_target, best_ask - tick_size)  # Don't cross spread

                    new_price = round(new_target / tick_size) * tick_size

                    # Check if adjustment needed
                    if abs(new_price - current_price) > tick_size:
                        log.info(f"🔄 SSR {ssr_mode} adjusting: ${current_price:.2f} → ${new_price:.2f}")

                        # Edit the order
                        result = await async_client.edit_order(
                            order_id=order_id,
                            limit_price=new_price
                        )

                        if result:
                            adjustments += 1
                            current_price = new_price

                            with _ssr_lock:
                                if order_id in _active_ssr_orders:
                                    _active_ssr_orders[order_id]['current_price'] = current_price
                                    _active_ssr_orders[order_id]['adjustments'] = adjustments
                                    _active_ssr_orders[order_id]['status'] = 'monitoring'

                    await asyncio.sleep(check_interval)

                except Exception as e:
                    log.warning(f"SSR {ssr_mode} monitor error: {e}")
                    await asyncio.sleep(check_interval)

            # Cleanup
            with _ssr_lock:
                if order_id in _active_ssr_orders:
                    del _active_ssr_orders[order_id]

        loop.run_until_complete(monitoring_loop())

    finally:
        pass  # Don't close loop - may be reused


# ---------------------------------------------------------------------------
# SSR order placement (public API)
# ---------------------------------------------------------------------------

async def place_ssr_order(client, symbol: str, size: float, side: str,
                         reduce_only: bool = False,
                         max_duration: int = 0,  # 0 = indefinite (until filled/cancelled)
                         check_interval: float = 2.0,
                         tick_offset: int = 2):
    """
    Place SSR Order: Competitive pricing that chases the market INDEFINITELY.

    Designed for Delta Exchange far-expiry options with low liquidity.
    Places order 2 ticks below best ask (for sells) / 2 ticks above best bid (for buys).
    Starts background monitoring that checks every 2 seconds and adjusts price if needed.
    RUNS FOREVER until the order is filled or manually cancelled.
    Always post_only=True - never crosses spread, guarantees maker status.

    Strategy:
    - Initial: Place at best_ask - (tick_offset * tick_size) for sells
    - Background: Monitor orderbook every check_interval seconds
    - Adjust: If market moves, cancel and replace at new competitive price
    - NO TIMEOUT: Continues until filled or cancelled

    Args:
        client: UnifiedAPIClient instance
        symbol: Options symbol (e.g., C-BTC-113000-300126)
        size: Order size (positive number)
        side: 'buy' or 'sell'
        reduce_only: If True, only reduces position
        max_duration: Ignored - always runs indefinitely (kept for API compatibility)
        check_interval: Seconds between orderbook checks (default: 2s)
        tick_offset: Number of ticks below ask/above bid (default: 2)

    Returns:
        dict: Order result with initial placement details (monitoring continues in background)
    """
    size = int(abs(float(size)))

    log.info(f"🏎️ SSR ORDER: {side} {size} {symbol} - competitive pricing with background monitoring")

    try:
        # Fetch fresh orderbook
        quotes = await fetch_fresh_orderbook_quotes(client, symbol)
        best_bid = quotes['best_bid']
        best_ask = quotes['best_ask']
        tick_size = quotes['tick_size']
        price_source = quotes['source']

        if best_bid == 0 or best_ask == 0:
            log.warning(f"No quotes for {symbol}, using market order")
            order = await place_options_order(
                client, symbol, size, side,
                order_type='market_order',
                reduce_only=reduce_only,
                post_only=False
            )
            order['execution_type'] = 'market_fallback_no_quotes'
            return order

        # Calculate initial competitive price
        if side == 'sell':
            # Sell: 2 ticks BELOW best ask (more competitive)
            target_price = best_ask - (tick_offset * tick_size)
            target_price = max(target_price, best_bid + tick_size)  # Don't cross spread
        else:  # buy
            # Buy: 2 ticks ABOVE best bid (more competitive)
            target_price = best_bid + (tick_offset * tick_size)
            target_price = min(target_price, best_ask - tick_size)  # Don't cross spread

        initial_price = round(target_price / tick_size) * tick_size

        log.info(f"📊 SSR initial price: ${initial_price:.2f} ({tick_offset} ticks competitive) [bid:${best_bid:.2f} ask:${best_ask:.2f}]")

        # Place initial order
        initial_order = await place_options_order(
            client, symbol, size, side,
            order_type='limit_order',
            limit_price=initial_price,
            reduce_only=reduce_only,
            post_only=True
        )

        order_id = initial_order.get('id')
        if not order_id:
            log.error("❌ Failed to get order ID from initial SSR order")
            return initial_order

        log.info(f"✅ SSR order placed: {order_id} at ${initial_price:.2f} - starting background monitor")

        # Track this SSR order
        with _ssr_lock:
            _active_ssr_orders[order_id] = {
                'symbol': symbol,
                'side': side,
                'size': size,
                'status': 'starting',
                'current_price': initial_price,
                'adjustments': 0,
                'start_time': time.time(),
                'max_duration': 'indefinite'  # No timeout for low liquidity options
            }

        # Get client config for background thread (will create new client there)
        client_config = {
            'api_key': client.api_key if hasattr(client, 'api_key') else '',
            'api_secret': client.api_secret if hasattr(client, 'api_secret') else '',
            'testnet': client.testnet if hasattr(client, 'testnet') else True
        }

        # Start background monitoring thread
        monitor_thread = threading.Thread(
            target=_run_ssr_monitoring_loop,
            args=(client_config, symbol, size, side, order_id, initial_price, tick_size),
            kwargs={
                'reduce_only': reduce_only,
                'max_duration': max_duration,
                'check_interval': check_interval,
                'tick_offset': tick_offset
            },
            daemon=True  # Thread will exit when main process exits
        )
        monitor_thread.start()
        log.info(f"🏎️ SSR background monitor started - will chase INDEFINITELY until filled/cancelled")

        # Return immediately with order info
        initial_order['execution_type'] = 'ssr_monitoring_started'
        initial_order['limit_price'] = initial_price
        initial_order['ssr_info'] = {
            'order_id': order_id,
            'initial_price': initial_price,
            'tick_offset': tick_offset,
            'max_duration': 'indefinite',
            'check_interval': check_interval,
            'status': 'background_monitoring_active_indefinitely'
        }
        return initial_order

    except Exception as e:
        log.exception(f"SSR order failed: {e}")
        # Fallback to market order
        order = await place_options_order(
            client, symbol, size, side,
            order_type='market_order',
            reduce_only=reduce_only
        )
        order['execution_type'] = 'market_fallback_error'
        order['error'] = str(e)
        return order


async def place_ssr_order_with_margin(client, symbol: str, size: float, side: str,
                                     margin_percent: float = 5.0,
                                     ssr_mode: str = 'aggressive',
                                     reduce_only: bool = False,
                                     check_interval: float = 2.0):
    """
    Place SSR Order with percentage-based margin pricing (for aggressive/conservative modes).

    Unlike tick-based SSR, this uses a percentage margin from the reference price.

    Args:
        client: UnifiedAPIClient instance
        symbol: Options symbol (e.g., C-BTC-113000-300126)
        size: Order size (positive number)
        side: 'buy' or 'sell'
        margin_percent: Percentage margin from reference price
        ssr_mode: 'aggressive' or 'conservative' for logging
        reduce_only: If True, only reduces position
        check_interval: Seconds between orderbook checks (default: 2s)

    Returns:
        dict: Order result with initial placement details (monitoring continues in background)
    """
    size = int(abs(float(size)))

    log.info(f"🏎️ SSR {ssr_mode.upper()} ORDER: {side} {size} {symbol} - {margin_percent}% margin pricing")

    try:
        # Fetch fresh orderbook
        quotes = await fetch_fresh_orderbook_quotes(client, symbol)
        best_bid = quotes['best_bid']
        best_ask = quotes['best_ask']
        tick_size = quotes['tick_size']

        if best_bid == 0 or best_ask == 0:
            log.warning(f"No quotes for {symbol}, using market order")
            order = await place_options_order(
                client, symbol, size, side,
                order_type='market_order',
                reduce_only=reduce_only,
                post_only=False
            )
            order['execution_type'] = 'market_fallback_no_quotes'
            return order

        # Calculate price based on percentage margin
        if side == 'sell':
            # Sell: margin% BELOW best ask (more competitive - lower limit sell gets filled first)
            reference_price = best_ask
            target_price = reference_price * (1 - margin_percent / 100)
        else:  # buy
            # Buy: margin% ABOVE best bid (more competitive - higher limit buy gets filled first)
            reference_price = best_bid
            target_price = reference_price * (1 + margin_percent / 100)

        # Round to tick size
        initial_price = round(target_price / tick_size) * tick_size

        # Ensure we don't cross the spread
        if side == 'sell':
            initial_price = max(initial_price, best_bid + tick_size)  # Don't go below bid
        else:
            initial_price = min(initial_price, best_ask - tick_size)  # Don't go above ask

        log.info(f"📊 SSR {ssr_mode} initial price: ${initial_price:.2f} ({margin_percent}% margin) [bid:${best_bid:.2f} ask:${best_ask:.2f}]")

        # Place initial order
        initial_order = await place_options_order(
            client, symbol, size, side,
            order_type='limit_order',
            limit_price=initial_price,
            reduce_only=reduce_only,
            post_only=True
        )

        order_id = initial_order.get('id')
        if not order_id:
            log.error("❌ Failed to get order ID from initial SSR order")
            return initial_order

        log.info(f"✅ SSR {ssr_mode} order placed: {order_id} at ${initial_price:.2f} - starting background monitor")

        # Track this SSR order
        with _ssr_lock:
            _active_ssr_orders[order_id] = {
                'symbol': symbol,
                'side': side,
                'size': size,
                'status': 'starting',
                'current_price': initial_price,
                'adjustments': 0,
                'start_time': time.time(),
                'max_duration': 'indefinite',
                'ssr_mode': ssr_mode,
                'margin_percent': margin_percent
            }

        # Get client config for background thread
        client_config = {
            'api_key': client.api_key if hasattr(client, 'api_key') else '',
            'api_secret': client.api_secret if hasattr(client, 'api_secret') else '',
            'testnet': client.testnet if hasattr(client, 'testnet') else True
        }

        # Start background monitoring thread
        monitor_thread = threading.Thread(
            target=_run_ssr_margin_monitoring_loop,
            args=(client_config, symbol, size, side, order_id, initial_price, tick_size),
            kwargs={
                'reduce_only': reduce_only,
                'check_interval': check_interval,
                'margin_percent': margin_percent,
                'ssr_mode': ssr_mode
            },
            daemon=True
        )
        monitor_thread.start()
        log.info(f"🏎️ SSR {ssr_mode} background monitor started - will chase until filled/cancelled")

        # Return immediately with order info
        initial_order['execution_type'] = f'ssr_{ssr_mode}_monitoring_started'
        initial_order['limit_price'] = initial_price
        initial_order['ssr_info'] = {
            'order_id': order_id,
            'initial_price': initial_price,
            'margin_percent': margin_percent,
            'ssr_mode': ssr_mode,
            'check_interval': check_interval,
            'status': f'background_monitoring_{ssr_mode}_active'
        }
        return initial_order

    except Exception as e:
        log.exception(f"SSR {ssr_mode} order failed: {e}")
        order = await place_options_order(
            client, symbol, size, side,
            order_type='market_order',
            reduce_only=reduce_only
        )
        order['execution_type'] = 'market_fallback_error'
        order['error'] = str(e)
        return order
