"""
MMM Executor — Smart Execution Engine

Places trades using Smart Execution:
1. Fetch fresh L2 orderbook for real-time bid/ask
2. Place limit order at mid-price (half of bid + ask)
3. Wait up to 60 seconds for fill confirmation
4. If not filled, re-fetch fresh prices and amend the order
5. Repeat until filled or max attempts reached

Uses existing infrastructure:
- place_options_order() from options_control.py for order placement
- fetch_fresh_orderbook_quotes() for L2 orderbook access
- edit_order() for in-place price amendment (no cancel+replace)
- UnifiedAPIClient for authenticated API access

References:
- MONEY_POWER_CALCULATION_LOGIC.md §3: Order execution at entry
- §15.5: Use bid for selling, mark for monitoring, ask for buying

Created: February 15, 2026
"""

import asyncio
import logging
import sys
import os
import time
from typing import Dict, Optional, Any, Tuple
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))

# Configure logger to output to stderr (picked up by LaunchAgent)
log = logging.getLogger('mmm_executor')
if not log.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    log.addHandler(_handler)
    log.setLevel(logging.DEBUG)
    log.propagate = False

# Activity logging helper (fire-and-forget, never blocks execution)
def _log_activity(activity_type, message, session_id=None, severity='info', details=None):
    try:
        from .mmm_activity import log_activity
        log_activity(activity_type, message, session_id, severity, details)
    except Exception:
        pass  # Never let logging interfere with execution

# Execution constants
FILL_CHECK_INTERVAL = 3       # Check fill status every 3 seconds
FILL_TIMEOUT = 60             # Wait 60 seconds before repricing
MAX_REPRICE_ATTEMPTS = 10     # Maximum total reprice attempts (10 minutes total worst case)
POST_ONLY_RETRIES = 5         # Max retries when post-only order is rejected (price crosses book)
POST_ONLY_RETRY_DELAY = 1.5   # Seconds to wait between post-only retries
INITIAL_PLACEMENT_RETRIES = 3 # Max retries for initial order placement
ORDER_STATES_FILLED = {'filled', 'closed', 'completed'}
ORDER_STATES_DEAD = {'cancelled', 'canceled', 'rejected'}


class MMMExecutor:
    """
    Smart execution engine for MMM.

    Places orders at mid-price and monitors for fills.
    If not filled within 60 seconds, re-fetches fresh prices
    and amends the order in-place (no cancel+replace).

    CRITICAL: httpx.AsyncClient binds to the event loop where it's first used.
    We must create a FRESH AsyncDeltaClient per async context (per asyncio.run()
    or per background thread loop) to avoid 'Future attached to a different loop'.
    This matches the proven pattern from options_control.py.
    """

    def __init__(self):
        self._client = None
        # NOTE: No self._rest_client — each method creates its own
        # local client to avoid race conditions in concurrent execution

    @property
    def client(self):
        """Lazy-load UnifiedAPIClient (used for place_options_order compatibility)."""
        if self._client is None:
            try:
                from bot.api.unified_api_client import UnifiedAPIClient
                from config.loader import get_api_credentials

                creds = get_api_credentials()
                self._client = UnifiedAPIClient(
                    api_key=creds['api_key'],
                    api_secret=creds['api_secret'],
                    symbol='BTCUSD',
                    enable_websocket=False,
                )
                log.info("MMM Executor: UnifiedAPIClient initialized")
            except Exception as e:
                log.error(f"Failed to initialize API client: {e}")
                raise
        return self._client

    def _create_rest_client(self):
        """
        Create a FRESH AsyncDeltaClient bound to the CURRENT event loop.

        CRITICAL: httpx.AsyncClient binds its transport to the event loop
        where it's first used. Using a cached client from a different loop
        causes 'Future attached to a different loop' errors.
        Must create fresh per asyncio.run() / per thread event loop.
        """
        from bot.api.async_delta_client import AsyncDeltaClient
        from config.loader import get_api_credentials

        creds = get_api_credentials()
        testnet = creds.get('testnet', False) or False

        client = AsyncDeltaClient(
            api_key=creds.get('api_key', ''),
            api_secret=creds.get('api_secret', ''),
            testnet=testnet,
        )
        log.debug("MMM Executor: Created fresh AsyncDeltaClient for current event loop")
        return client

    # =========================================================================
    # Core: Smart Order with 60s Wait + Reprice
    # =========================================================================

    async def smart_execute(
        self,
        symbol: str,
        side: str,
        size: int,
        reduce_only: bool = False,
        session_id: str = None,
    ) -> Dict[str, Any]:
        """
        Place order at mid-price, wait 60s for fill, reprice if needed.

        This is the main entry point for all MMM order execution.

        Args:
            symbol: Options symbol (e.g., 'C-BTC-100000-150226')
            side: 'buy' or 'sell'
            size: Number of lots (contracts)
            reduce_only: If True, only reduces position
            session_id: Session ID for activity logging

        Returns:
            {
                success: bool,
                order_id: str,
                fill_price: float,
                filled_size: int,
                execution_type: str,
                attempts: int,
                total_time: float,
                error: str (if failed),
                order_details: dict,
            }
        """
        start_time = time.time()
        attempts = 0

        log.info(f"📊 MMM Smart Execute: {side.upper()} {size} {symbol}")

        _log_activity('order_placing',
            f"{side.upper()} {size} lot(s) {symbol} — fetching prices...",
            session_id=session_id, severity='progress',
            details={'symbol': symbol, 'side': side, 'size': size})

        # Create a FRESH REST client LOCAL to this call
        # (httpx.AsyncClient binds to the event loop where first used)
        # Each concurrent smart_execute gets its OWN client — no shared state
        rest_client = self._create_rest_client()

        # Step 1: Fetch fresh prices and place initial order
        quotes = await self._fetch_quotes(symbol, rest_client)
        if not quotes:
            _log_activity('order_failed', f"{side.upper()} {symbol}: Cannot fetch orderbook",
                session_id=session_id, severity='error', details={'symbol': symbol})
            return self._failure('Cannot fetch orderbook quotes', symbol, side, size)

        mid_price = self._calculate_mid_price(quotes)
        if mid_price <= 0:
            _log_activity('order_failed',
                f"{side.upper()} {symbol}: Invalid mid-price (bid={quotes.get('best_bid', 0)}, ask={quotes.get('best_ask', 0)})",
                session_id=session_id, severity='error', details={'symbol': symbol, 'quotes': quotes})
            return self._failure('Invalid mid-price (no bid/ask)', symbol, side, size)

        # Place initial limit order at mid-price — with retry on failure
        order_result = None
        last_error = 'Order placement failed'
        for placement_try in range(1, INITIAL_PLACEMENT_RETRIES + 1):
            order_result = await self._place_limit_order(
                symbol, side, size, mid_price, reduce_only, rest_client
            )
            if order_result and order_result.get('id'):
                break  # Success

            last_error = order_result.get('error', 'Order placement failed') if order_result else 'Order placement failed'
            if placement_try < INITIAL_PLACEMENT_RETRIES:
                log.warning(
                    f"⚠️ Initial placement attempt {placement_try}/{INITIAL_PLACEMENT_RETRIES} failed: {last_error}. "
                    f"Re-fetching quotes and retrying..."
                )
                _log_activity('order_retrying',
                    f"{side.upper()} {symbol}: Placement failed ({last_error}), retrying ({placement_try}/{INITIAL_PLACEMENT_RETRIES})...",
                    session_id=session_id, severity='warning',
                    details={'symbol': symbol, 'error': last_error, 'attempt': placement_try})

                await asyncio.sleep(POST_ONLY_RETRY_DELAY)
                # Re-fetch fresh quotes for retry
                quotes = await self._fetch_quotes(symbol, rest_client)
                if quotes:
                    new_mid = self._calculate_mid_price(quotes)
                    if new_mid > 0:
                        mid_price = new_mid
                        log.info(f"📊 Refreshed mid-price: ${mid_price:.2f} (bid=${quotes['best_bid']:.2f}, ask=${quotes['best_ask']:.2f})")

        if not order_result or not order_result.get('id'):
            _log_activity('order_failed',
                f"{side.upper()} {symbol}: All {INITIAL_PLACEMENT_RETRIES} placement attempts failed — {last_error}",
                session_id=session_id, severity='error', details={'symbol': symbol, 'error': last_error})
            return self._failure(last_error, symbol, side, size)

        order_id = str(order_result['id'])
        product_id = order_result.get('product_id')

        log.info(
            f"📋 Order {order_id} placed at mid-price ${mid_price:.2f} "
            f"(bid=${quotes['best_bid']:.2f}, ask=${quotes['best_ask']:.2f})"
        )

        _log_activity('order_placed',
            f"{side.upper()} {size} {symbol} @ ${mid_price:.2f} (bid=${quotes['best_bid']:.2f}, ask=${quotes['best_ask']:.2f})",
            session_id=session_id, severity='info',
            details={'order_id': order_id, 'mid_price': mid_price,
                     'bid': quotes['best_bid'], 'ask': quotes['best_ask']})

        # Step 2: Wait + Reprice loop
        while attempts < MAX_REPRICE_ATTEMPTS:
            attempts += 1

            # Wait up to 60 seconds, checking fill status every 3 seconds
            filled, fill_data = await self._wait_for_fill(
                order_id, product_id, timeout=FILL_TIMEOUT,
                rest_client=rest_client,
            )

            if filled:
                # CRITICAL FIX: Re-fetch order details to ensure we have ACTUAL fill price
                # Delta API sometimes returns state='filled' before average_fill_price is populated
                await asyncio.sleep(0.5)  # Brief delay for exchange to finalize fill data
                final_order_data = await self._get_order_status(order_id, product_id, rest_client)
                
                if not final_order_data:
                    log.warning(f"Cannot re-fetch order {order_id} after fill detection, using cached data")
                    final_order_data = fill_data
                
                elapsed = time.time() - start_time
                
                # CRITICAL: Extract ONLY actual fill price, never limit price
                raw_fill = final_order_data.get('average_fill_price')
                
                if not raw_fill or str(raw_fill).strip() == '' or str(raw_fill) == '0':
                    # NEVER fall back to limit price - that's the ORDER price, not FILL price
                    log.error(
                        f"❌ Order {order_id} marked as filled but average_fill_price is missing/zero! "
                        f"Order data: state={final_order_data.get('state')}, "
                        f"avg_fill={raw_fill}, price={final_order_data.get('price')}"
                    )
                    return self._failure(
                        f"Order filled but average_fill_price is invalid ({raw_fill})",
                        symbol, side, size,
                        order_id=order_id, attempts=attempts,
                        total_time=round(elapsed, 2),
                    )
                
                # API returns prices as STRINGS — must cast to float
                fill_price = float(raw_fill)
                
                # Sanity check: fill price should be reasonable
                if fill_price <= 0 or fill_price > 1000000:
                    log.error(f"❌ Order {order_id} has invalid fill_price: {fill_price}")
                    return self._failure(
                        f"Invalid fill_price: {fill_price}",
                        symbol, side, size,
                        order_id=order_id, attempts=attempts,
                        total_time=round(elapsed, 2),
                    )
                
                raw_unfilled = final_order_data.get('unfilled_size')
                if raw_unfilled is not None:
                    filled_size = size - int(raw_unfilled)
                else:
                    filled_size = size

                log.info(
                    f"✅ Order {order_id} FILLED at ${fill_price:.2f} "
                    f"after {elapsed:.1f}s ({attempts} attempt(s))"
                )

                _log_activity('order_filled',
                    f"✅ {side.upper()} {symbol} FILLED @ ${fill_price:.2f} in {elapsed:.1f}s",
                    session_id=session_id, severity='success',
                    details={'order_id': order_id, 'fill_price': fill_price,
                             'elapsed': round(elapsed, 1), 'attempts': attempts})

                return {
                    'success': True,
                    'order_id': order_id,
                    'fill_price': fill_price,
                    'filled_size': filled_size,
                    'execution_type': 'smart_mid_price',
                    'attempts': attempts,
                    'total_time': round(elapsed, 2),
                    'order_details': final_order_data,
                }

            # Not filled — check if order is dead (cancelled/rejected)
            if fill_data and fill_data.get('_dead'):
                elapsed = time.time() - start_time
                log.warning(f"❌ Order {order_id} is dead ({fill_data.get('state', '?')})")
                return self._failure(
                    f"Order {fill_data.get('state', 'dead')}",
                    symbol, side, size,
                    order_id=order_id, attempts=attempts,
                    total_time=round(elapsed, 2),
                )

            # Still open — reprice with fresh quotes
            log.info(f"⏰ Order {order_id} not filled after {FILL_TIMEOUT}s, repricing (attempt {attempts}/{MAX_REPRICE_ATTEMPTS})")

            _log_activity('order_repricing',
                f"Order {order_id} not filled after {FILL_TIMEOUT}s, repricing (attempt {attempts}/{MAX_REPRICE_ATTEMPTS})",
                session_id=session_id, severity='warning',
                details={'order_id': order_id, 'attempt': attempts})

            new_quotes = await self._fetch_quotes(symbol, rest_client)
            if not new_quotes:
                log.warning("Cannot fetch fresh quotes for reprice, keeping current price")
                continue

            new_mid = self._calculate_mid_price(new_quotes)
            if new_mid <= 0:
                log.warning("Invalid new mid-price, keeping current price")
                continue

            if abs(new_mid - mid_price) < 0.01:
                log.info(f"Mid-price unchanged (${new_mid:.2f}), skipping amend")
                continue

            # Amend order in-place (no cancel+replace)
            amended = await self._amend_order(order_id, product_id, new_mid, rest_client)
            if amended:
                log.info(
                    f"📝 Order {order_id} amended: ${mid_price:.2f} → ${new_mid:.2f} "
                    f"(bid=${new_quotes['best_bid']:.2f}, ask=${new_quotes['best_ask']:.2f})"
                )
                mid_price = new_mid
            else:
                log.warning(f"Amend failed for {order_id}, trying cancel+replace")

                # Fallback: cancel and replace
                cancelled = await self._cancel_order(order_id, product_id, rest_client)
                if not cancelled:
                    # May have filled while trying to cancel — check status
                    status = await self._get_order_status(order_id, product_id, rest_client)
                    if status and self._is_filled(status):
                        # CRITICAL: Validate fill price before accepting
                        raw_fill = status.get('average_fill_price')
                        if raw_fill and str(raw_fill).strip() != '' and str(raw_fill) != '0':
                            fill_price = float(raw_fill)
                            elapsed = time.time() - start_time
                            log.info(f"✅ Order {order_id} filled during cancel attempt at ${fill_price:.2f}")
                            return {
                                'success': True,
                                'order_id': order_id,
                                'fill_price': fill_price,
                                'filled_size': size,
                                'execution_type': 'smart_mid_price_filled_during_cancel',
                                'attempts': attempts,
                                'total_time': round(elapsed, 2),
                                'order_details': status,
                            }
                        else:
                            log.warning(
                                f"Order {order_id} state=filled but average_fill_price invalid ({raw_fill}), "
                                f"treating as still open"
                            )
                    continue

                # Place fresh order
                order_result = await self._place_limit_order(
                    symbol, side, size, new_mid, reduce_only, rest_client
                )
                if order_result and order_result.get('id'):
                    order_id = str(order_result['id'])
                    product_id = order_result.get('product_id')
                    mid_price = new_mid
                    log.info(f"📋 Replacement order {order_id} placed at ${new_mid:.2f}")
                else:
                    log.error("Failed to place replacement order")
                    break

        # Exhausted all attempts
        elapsed = time.time() - start_time
        # Cancel any remaining order
        await self._cancel_order(order_id, product_id)
        log.error(f"❌ Max reprice attempts ({MAX_REPRICE_ATTEMPTS}) exhausted for {symbol}")

        return self._failure(
            f'Max reprice attempts exhausted after {elapsed:.0f}s',
            symbol, side, size,
            order_id=order_id, attempts=attempts,
            total_time=round(elapsed, 2),
        )

    # =========================================================================
    # Execute a sell straddle entry (CE + PE)
    # =========================================================================

    async def execute_entry(
        self,
        ce_symbol: str,
        pe_symbol: str,
        lots: int,
        session_id: str = None,
    ) -> Dict[str, Any]:
        """
        Execute a full MMM entry: sell CE + sell PE using smart execution.

        Both legs execute concurrently for speed.

        Args:
            ce_symbol: CE option symbol
            pe_symbol: PE option symbol
            lots: Number of lots per side
            session_id: Session ID for activity logging

        Returns:
            {
                success: bool,
                ce: { smart_execute result },
                pe: { smart_execute result },
                total_premium: float,
                error: str (if failed),
            }
        """
        log.info(f"🚀 MMM Entry: SELL {lots} {ce_symbol} + SELL {lots} {pe_symbol}")

        _log_activity('entry_starting',
            f"Selling {lots} lot(s) CE ({ce_symbol}) + PE ({pe_symbol}) concurrently...",
            session_id=session_id, severity='progress',
            details={'ce_symbol': ce_symbol, 'pe_symbol': pe_symbol, 'lots': lots})

        # Execute both legs concurrently
        ce_task = self.smart_execute(ce_symbol, 'sell', lots, session_id=session_id)
        pe_task = self.smart_execute(pe_symbol, 'sell', lots, session_id=session_id)

        ce_result, pe_result = await asyncio.gather(ce_task, pe_task, return_exceptions=True)

        # Handle exceptions
        if isinstance(ce_result, Exception):
            ce_result = self._failure(str(ce_result), ce_symbol, 'sell', lots)
        if isinstance(pe_result, Exception):
            pe_result = self._failure(str(pe_result), pe_symbol, 'sell', lots)

        total_premium = 0
        if ce_result.get('success'):
            total_premium += ce_result['fill_price'] * ce_result.get('filled_size', lots)
        if pe_result.get('success'):
            total_premium += pe_result['fill_price'] * pe_result.get('filled_size', lots)

        all_success = ce_result.get('success') and pe_result.get('success')

        if all_success:
            log.info(
                f"✅ MMM Entry complete: CE@${ce_result['fill_price']:.2f} + "
                f"PE@${pe_result['fill_price']:.2f} = ${total_premium:.2f} total"
            )
            _log_activity('entry_complete',
                f"✅ Entry filled: CE@${ce_result['fill_price']:.2f} + PE@${pe_result['fill_price']:.2f} = ${total_premium:.2f} total premium",
                session_id=session_id, severity='success',
                details={'ce_fill': ce_result.get('fill_price'), 'pe_fill': pe_result.get('fill_price'),
                         'total_premium': total_premium})
        else:
            ce_status = 'OK' if ce_result.get('success') else 'FAIL'
            pe_status = 'OK' if pe_result.get('success') else 'FAIL'
            log.warning(
                f"⚠️ MMM Entry partial: CE={ce_status}, PE={pe_status}"
            )
            _log_activity('entry_failed',
                f"Entry issue: CE={ce_status}, PE={pe_status}. {ce_result.get('error', '')} {pe_result.get('error', '')}",
                session_id=session_id, severity='error',
                details={'ce_result': ce_result, 'pe_result': pe_result})

        return {
            'success': all_success,
            'ce': ce_result,
            'pe': pe_result,
            'total_premium': round(total_premium, 2),
            'error': None if all_success else 'One or both legs failed',
        }

    # =========================================================================
    # Execute a single leg replacement (for adjustments, shifts, etc.)
    # =========================================================================

    async def execute_adjustment(
        self,
        close_symbol: str,
        close_lots: int,
        open_symbol: str,
        open_lots: int,
    ) -> Dict[str, Any]:
        """
        Execute an adjustment: buy-to-close old + sell-to-open new.

        Sequential execution: close first, then open.
        This ensures we don't overcommit margin.

        Args:
            close_symbol: Symbol to buy back (close)
            close_lots: Lots to close
            open_symbol: Symbol to sell (open)
            open_lots: Lots to open

        Returns:
            {
                success: bool,
                close: { smart_execute result },
                open: { smart_execute result },
                net_cost: float,
            }
        """
        log.info(
            f"🔄 MMM Adjustment: BUY {close_lots} {close_symbol} → SELL {open_lots} {open_symbol}"
        )

        # Step 1: Close existing position
        close_result = await self.smart_execute(
            close_symbol, 'buy', close_lots, reduce_only=True
        )

        if not close_result.get('success'):
            log.error(f"Failed to close {close_symbol}: {close_result.get('error')}")
            return {
                'success': False,
                'close': close_result,
                'open': None,
                'net_cost': 0,
                'error': f'Close leg failed: {close_result.get("error")}',
            }

        # Step 2: Open new position
        open_result = await self.smart_execute(
            open_symbol, 'sell', open_lots
        )

        close_cost = close_result['fill_price'] * close_result.get('filled_size', close_lots)
        open_credit = open_result['fill_price'] * open_result.get('filled_size', open_lots) if open_result.get('success') else 0
        net_cost = close_cost - open_credit

        return {
            'success': open_result.get('success', False),
            'close': close_result,
            'open': open_result,
            'net_cost': round(net_cost, 2),
            'error': None if open_result.get('success') else f'Open leg failed: {open_result.get("error")}',
        }

    # =========================================================================
    # Internal: Quote Fetching
    # =========================================================================

    async def _fetch_quotes(self, symbol: str, rest_client=None) -> Optional[Dict]:
        """Fetch fresh L2 orderbook quotes using the provided REST client."""
        result = {
            'best_bid': 0,
            'best_ask': 0,
            'bid_size': 0,
            'ask_size': 0,
            'tick_size': 0.01,
            'fresh': False,
            'source': 'none',
        }

        rest = rest_client or self._create_rest_client()

        try:
            # L2 orderbook for freshest prices
            orderbook = await rest.get_orderbook(symbol)
            if orderbook:
                buy_orders = orderbook.get('buy', [])
                sell_orders = orderbook.get('sell', [])
                if buy_orders and sell_orders:
                    result['best_bid'] = float(buy_orders[0].get('price', 0))
                    result['best_ask'] = float(sell_orders[0].get('price', 0))
                    result['bid_size'] = float(buy_orders[0].get('size', 0))
                    result['ask_size'] = float(sell_orders[0].get('size', 0))
                    result['fresh'] = True
                    result['source'] = 'l2_orderbook'
                    log.info(
                        f"📖 Fresh L2: bid ${result['best_bid']:.2f} x {result['bid_size']}, "
                        f"ask ${result['best_ask']:.2f} x {result['ask_size']}"
                    )
        except Exception as e:
            log.warning(f"L2 orderbook fetch failed for {symbol}: {e}")

        # Fallback to ticker
        if not result['fresh'] or result['best_bid'] == 0 or result['best_ask'] == 0:
            try:
                resp = await rest._request_with_retry(
                    method="GET",
                    path=f"/v2/tickers/{symbol}",
                )
                ticker = resp.get('result', resp)
                quotes = ticker.get('quotes', {})
                result['best_bid'] = float(quotes.get('best_bid') or 0)
                result['best_ask'] = float(quotes.get('best_ask') or 0)
                result['tick_size'] = float(ticker.get('tick_size') or 0.01)
                result['fresh'] = True
                result['source'] = 'ticker'
                log.info(f"📊 Ticker: bid ${result['best_bid']:.2f}, ask ${result['best_ask']:.2f}")
            except Exception as e:
                log.warning(f"Ticker fetch also failed for {symbol}: {e}")

        if not result['fresh']:
            return None
        return result

    def _calculate_mid_price(self, quotes: Dict) -> float:
        """Calculate mid-price from quotes, rounded to tick size."""
        bid = quotes.get('best_bid', 0)
        ask = quotes.get('best_ask', 0)
        tick = quotes.get('tick_size', 0.01)

        if bid <= 0 or ask <= 0:
            return 0

        mid = (bid + ask) / 2
        # Round to tick size
        if tick > 0:
            mid = round(mid / tick) * tick
        return round(mid, 2)

    # =========================================================================
    # Internal: Order Operations
    # =========================================================================

    async def _place_limit_order(
        self, symbol: str, side: str, size: int,
        price: float, reduce_only: bool = False,
        rest_client=None,
    ) -> Optional[Dict]:
        """Place a limit post-only order. On post-only rejection (price would cross
        the book), re-fetch quotes, adjust price to best_bid (for sells) or
        best_ask (for buys), and retry — always post_only=True.

        Retries up to POST_ONLY_RETRIES times with POST_ONLY_RETRY_DELAY between.
        Never falls back to taker (post_only=False) to avoid unexpected fills at bad prices."""
        rest = rest_client or self._create_rest_client()
        current_price = price

        for attempt in range(1, POST_ONLY_RETRIES + 1):
            try:
                log.info(f"📊 Placing limit (post_only, attempt {attempt}/{POST_ONLY_RETRIES}): "
                         f"{side} {size} {symbol} @ ${current_price:.2f}")

                response = await rest.place_order_by_symbol(
                    symbol=symbol,
                    side=side,
                    price=current_price,
                    size=int(size),
                    order_type="limit_order",
                    time_in_force="gtc",
                    post_only=True,
                    reduce_only=reduce_only,
                )

                result = response.get('result', response)
                log.info(f"✅ Order placed: {result.get('id', 'unknown')} @ ${current_price:.2f}")
                return result

            except Exception as e:
                err_str = str(e)
                is_post_only_reject = ('400' in err_str and
                    ('post-only' in err_str.lower() or 'post_only' in err_str.lower()
                     or 'would have matched' in err_str.lower() or '400' in err_str))

                if is_post_only_reject and attempt < POST_ONLY_RETRIES:
                    log.warning(
                        f"⚠️ Post-only rejected (attempt {attempt}/{POST_ONLY_RETRIES}): "
                        f"price ${current_price:.2f} would cross the book. "
                        f"Waiting {POST_ONLY_RETRY_DELAY}s then re-fetching quotes..."
                    )
                    await asyncio.sleep(POST_ONLY_RETRY_DELAY)

                    # Re-fetch fresh orderbook to get updated bid/ask
                    fresh_quotes = await self._fetch_quotes(symbol, rest)
                    if fresh_quotes:
                        bid = fresh_quotes.get('best_bid', 0)
                        ask = fresh_quotes.get('best_ask', 0)
                        tick = fresh_quotes.get('tick_size', 0.5)

                        if side.lower() == 'sell' and bid > 0:
                            # For sells: place at best_bid (guaranteed to be passive)
                            current_price = round(bid, 2)
                        elif side.lower() == 'buy' and ask > 0:
                            # For buys: place at best_ask (guaranteed to be passive)
                            current_price = round(ask, 2)
                        else:
                            # Fallback: recalculate mid
                            mid = self._calculate_mid_price(fresh_quotes)
                            if mid > 0:
                                current_price = mid

                        log.info(f"📊 Updated price for retry: ${current_price:.2f} "
                                 f"(bid=${bid:.2f}, ask=${ask:.2f})")
                    else:
                        log.warning("Cannot fetch fresh quotes for retry, using same price")
                    continue
                else:
                    log.error(f"Limit order placement failed (attempt {attempt}): {e}")
                    return {'error': str(e)}

        log.error(f"All {POST_ONLY_RETRIES} post-only attempts exhausted for {symbol}")
        return {'error': f'Post-only rejected {POST_ONLY_RETRIES} times — price keeps crossing book'}

    async def _amend_order(
        self, order_id: str, product_id: int, new_price: float,
        rest_client=None,
    ) -> bool:
        """Amend order price in-place (no cancel+replace).
        Only amends OUR order by specific ID + product_id."""
        try:
            rest = rest_client or self._create_rest_client()
            if not product_id:
                log.warning(f"Cannot amend order {order_id} — no product_id")
                return False
            await rest.edit_order(
                order_id=str(order_id),
                product_id=int(product_id),
                new_price=str(new_price),
            )
            return True
        except Exception as e:
            err_str = str(e)
            if '400' in err_str:
                log.info(f"Order {order_id} amend returned 400 — likely already filled")
            else:
                log.warning(f"Order amend failed for {order_id}: {e}")
            return False

    async def _cancel_order(self, order_id: str, product_id: int, rest_client=None) -> bool:
        """Cancel an order. Only cancels OUR order by specific ID."""
        try:
            rest = rest_client or self._create_rest_client()
            if not product_id:
                log.warning(f"Cannot cancel order {order_id} — no product_id")
                return False
            await rest.cancel_order(str(order_id), int(product_id))
            return True
        except Exception as e:
            err_str = str(e)
            # 400 typically means order already filled or cancelled — not an error
            if '400' in err_str:
                log.info(f"Order {order_id} cancel returned 400 — likely already filled/cancelled")
            else:
                log.warning(f"Order cancel failed for {order_id}: {e}")
            return False

    async def _get_order_status(
        self, order_id: str, product_id: int = None,
        rest_client=None,
    ) -> Optional[Dict]:
        """Get a SPECIFIC order by ID from the exchange.

        CRITICAL: Uses GET /v2/orders/{order_id} (single-order endpoint)
        NOT GET /v2/orders (list endpoint which returns unrelated orders).
        This prevents interference with orders from other algos/manual trades.
        """
        try:
            rest = rest_client or self._create_rest_client()
            # Use the dedicated single-order endpoint
            result = await rest.get_order(str(order_id))
            return result if result else None
        except Exception as e:
            log.warning(f"Order status fetch failed for {order_id}: {e}")
            return None

    def _is_filled(self, order_data: Dict) -> bool:
        """Check if order data indicates a fill."""
        state = (
            order_data.get('state', '')
            or order_data.get('status', '')
        ).lower()
        return state in ORDER_STATES_FILLED

    # =========================================================================
    # Internal: Fill Monitoring
    # =========================================================================

    async def _wait_for_fill(
        self,
        order_id: str,
        product_id: int,
        timeout: int = FILL_TIMEOUT,
        rest_client=None,
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Wait for order to be filled, checking every FILL_CHECK_INTERVAL seconds.

        Args:
            order_id: Order ID to monitor
            product_id: Product ID
            timeout: Max seconds to wait

        Returns:
            (filled: bool, order_data: dict or None)
        """
        deadline = time.time() + timeout
        check_count = 0

        while time.time() < deadline:
            check_count += 1
            await asyncio.sleep(FILL_CHECK_INTERVAL)

            status = await self._get_order_status(order_id, product_id, rest_client)
            if not status:
                continue

            state = (
                status.get('state', '')
                or status.get('status', '')
            ).lower()

            if state in ORDER_STATES_FILLED:
                return True, status

            if state in ORDER_STATES_DEAD:
                status['_dead'] = True
                return False, status

            # Log progress
            unfilled = status.get('unfilled_size', '?')
            if check_count % 5 == 0:
                log.debug(
                    f"Order {order_id} still open "
                    f"(unfilled={unfilled}, check #{check_count})"
                )

        # Timed out
        return False, None

    # =========================================================================
    # Internal: Helpers
    # =========================================================================

    def _failure(
        self, error: str, symbol: str, side: str, size: int,
        order_id: str = None, attempts: int = 0, total_time: float = 0,
    ) -> Dict[str, Any]:
        """Build a standardized failure response."""
        return {
            'success': False,
            'order_id': order_id,
            'fill_price': 0,
            'filled_size': 0,
            'execution_type': 'failed',
            'attempts': attempts,
            'total_time': total_time,
            'error': error,
            'symbol': symbol,
            'side': side,
            'size': size,
        }


# =============================================================================
# Singleton
# =============================================================================

_executor_instance = None


def get_executor() -> MMMExecutor:
    """Get or create the singleton MMM executor."""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = MMMExecutor()
    return _executor_instance
