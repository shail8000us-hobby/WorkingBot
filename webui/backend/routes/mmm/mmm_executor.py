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
import threading
import time
from typing import Dict, Optional, Any, Tuple
from datetime import datetime

# P2 Audit fix (#16): sys.path.insert() is guarded to be idempotent.
# This is required because mmm_executor lazily imports from 'bot.api.*' and
# 'config.loader', which live outside the webui package tree. Until the
# codebase is installed as a proper package (pip install -e .), this path
# manipulation is necessary. The guard prevents duplicate entries on module
# re-imports (Flask hot-reload, pytest collection, etc.).
# TODO: Remove when root package is installable: https://docs.python.org/3/installing/
_BOT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
if _BOT_ROOT not in sys.path:
    sys.path.insert(0, _BOT_ROOT)


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
    except Exception as e:
        # M-1 fix: log at debug instead of silently swallowing — helps diagnose
        # activity system issues without blocking execution path
        logging.debug(f"Activity log suppressed: {e}")

# Execution constants
FILL_CHECK_INTERVAL = 3       # Check fill status every 3 seconds
FILL_TIMEOUT = 60             # Wait 60 seconds before repricing
# L-3 fix: reduced from 10 to 4 (4 × 60s = 4-minute max block instead of 10-min).
# Configurable per-session via 'max_reprice_attempts' param (see mmm_config.py).
MAX_REPRICE_ATTEMPTS = 4      # Maximum total reprice attempts (4 minutes total worst case)
POST_ONLY_RETRIES = 5         # Max retries when post-only order is rejected (price crosses book)
POST_ONLY_RETRY_DELAY = 1.5   # Seconds to wait between post-only retries
INITIAL_PLACEMENT_RETRIES = 3 # Max retries for initial order placement
ORDER_STATES_FILLED = {'filled', 'closed', 'completed'}
ORDER_STATES_DEAD = {'cancelled', 'canceled', 'rejected'}

import math as _math  # Module-level — audit fix: was imported per-scope 3× inside smart/emergency_execute


def _parse_fill_price(raw_fill) -> float:
    """
    Audit fix: Deduplicated fill-price parser (was copy-pasted 4× in smart_execute
    and emergency_execute with slight variations that could diverge on future edits).

    Validates and converts the raw average_fill_price from the Delta API:
      - Must not be None, empty string, or '0'
      - Must be a valid finite float
      - Must be > 0 and < $1,000,000 (sanity check)

    Raises ValueError with a descriptive message on any invalid value.
    Returns the parsed float fill price on success.
    """
    if raw_fill is None or str(raw_fill).strip() in ('', '0'):
        raise ValueError(f"average_fill_price is missing or zero: {raw_fill!r}")
    try:
        price = float(raw_fill)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Cannot parse average_fill_price {raw_fill!r}: {e}") from e
    if _math.isnan(price) or _math.isinf(price):
        raise ValueError(f"average_fill_price is NaN or Inf: {raw_fill!r}")
    if price <= 0 or price > 1_000_000:
        raise ValueError(f"average_fill_price out of range: {price}")
    return price





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
        max_reprice_attempts: int = None,  # Override default MAX_REPRICE_ATTEMPTS
        use_bid_entry: bool = False,       # Start BUY orders at best_bid (maker, cheaper)
        client_order_id: str = None,       # Optional override; auto-generated if None
        max_buy_price: float = None,       # Hard price cap for BUY orders — abort reprice if exceeded
    ) -> Dict[str, Any]:
        """
        Place order at mid-price (or bid for buys when use_bid_entry=True),
        wait 60s for fill, reprice if needed.

        max_buy_price: When set (side='buy'), the reprice loop will NOT amend/replace
        the order at a price above this cap. Instead, the order is cancelled and
        smart_execute returns failure. Used by close_at_threshold to prevent
        buying back a position at a premium above the configured threshold.

        This is the main entry point for all MMM order execution.

        Args:
            symbol: Options symbol (e.g., 'C-BTC-100000-150226')
            side: 'buy' or 'sell'
            size: Number of lots (contracts)
            reduce_only: If True, only reduces position
            session_id: Session ID for activity logging
            max_reprice_attempts: Override global MAX_REPRICE_ATTEMPTS (default=4)
            use_bid_entry: If True and side=='buy', start at best_bid instead of mid.
                           Use for close_at_5 buybacks — pays less, maker order.

        Repricing strategy:
            - First half of attempts: limit order at mid-price (best fill)
            - Second half of attempts: limit order at best_bid (more aggressive,
              guaranteed queue priority for sells)

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
        _max_attempts = max_reprice_attempts if max_reprice_attempts is not None else MAX_REPRICE_ATTEMPTS
        _aggressive_from = (_max_attempts // 2) + 1  # Switch to best_bid after halfway

        # Generate a unique client_order_id for this order if not provided.
        # Format: mmm_{session8}_{side1}_{ts10} — max 32 chars.
        # This lets us identify exactly which fills belong to this session on Delta Exchange,
        # independent of other algos or manual trades at the same strike on the same account.
        if not client_order_id:
            _sess_tag = ''.join(
                c for c in (session_id or 'x').replace('mmm', '').replace('-', '')
            )[:8]
            _side_tag = 'b' if side.lower() == 'buy' else 's'
            _ts_tag = str(int(time.time()))[-8:]
            # Include first char of symbol ('c'=CE, 'p'=PE) so concurrent entry
            # orders on the same session get distinct client_order_ids.
            # Without this, asyncio.gather fires CE+PE at the same timestamp →
            # identical IDs → exchange rejects second order with duplicate_client_order_id.
            _opt_tag = (symbol[0].lower() if symbol else 'x')[:1]
            client_order_id = f"mmm_{_sess_tag}_{_side_tag}{_opt_tag}_{_ts_tag}"[:32]

        log.info(f"📊 MMM Smart Execute: {side.upper()} {size} {symbol} coid={client_order_id}")

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

        # For close_at_5 buybacks (use_bid_entry=True), start at best_bid — pays less,
        # still a passive maker order. For all other orders, start at mid-price.
        if use_bid_entry and side.lower() == 'buy':
            mid_price = quotes.get('best_bid', 0)
            if mid_price <= 0:
                mid_price = self._calculate_mid_price(quotes)
            tick = quotes.get('tick_size', 0.01)
            if tick > 0:
                mid_price = round(round(mid_price / tick) * tick, 2)
        else:
            mid_price = self._calculate_mid_price(quotes)

        # max_buy_price cap: reject even the initial placement if premium has already
        # bounced above the threshold between scan time and execution time.
        if max_buy_price is not None and side.lower() == 'buy' and mid_price > max_buy_price:
            log.warning(
                f"⛔ Initial placement aborted: mid_price ${mid_price:.2f} > max_buy_price "
                f"${max_buy_price:.2f} for {symbol}. Premium bounced above threshold before order placed."
            )
            _log_activity('order_cancelled',
                f"Initial placement aborted — premium ${mid_price:.2f} > cap ${max_buy_price:.2f} (threshold guard)",
                session_id=session_id, severity='warning',
                details={'symbol': symbol, 'mid_price': mid_price, 'max_buy_price': max_buy_price})
            return self._failure(
                f'Initial placement aborted: premium ${mid_price:.2f} already above close_at_threshold cap ${max_buy_price:.2f}',
                symbol, side, size,
            )

        if mid_price <= 0:
            _log_activity('order_failed',
                f"{side.upper()} {symbol}: Invalid mid-price (bid={quotes.get('best_bid', 0)}, ask={quotes.get('best_ask', 0)})",
                session_id=session_id, severity='error', details={'symbol': symbol, 'quotes': quotes})
            return self._failure('Invalid mid-price (no bid/ask)', symbol, side, size)

        # Place initial limit order at bid/mid-price — with retry on failure
        order_result = None
        last_error = 'Order placement failed'
        for placement_try in range(1, INITIAL_PLACEMENT_RETRIES + 1):
            order_result = await self._place_limit_order(
                symbol, side, size, mid_price, reduce_only, rest_client,
                client_order_id=client_order_id,
            )
            if order_result and order_result.get('id'):
                break  # Success

            last_error = order_result.get('error', 'Order placement failed') if order_result else 'Order placement failed'

            # Defensive: duplicate_client_order_id means the first placement landed on
            # the exchange but the response was lost (network drop between server and us).
            # Retrying with the same client_order_id will always fail — instead look up
            # the already-placed open order and continue monitoring it.
            if 'duplicate_client_order_id' in str(last_error).lower():
                log.warning(
                    f"⚠️ {symbol}: duplicate_client_order_id — order already exists on exchange. "
                    f"Searching open orders for client_order_id={client_order_id}..."
                )
                try:
                    open_orders = await rest_client.get_open_orders_by_symbol(symbol)
                    matched = next(
                        (o for o in open_orders if str(o.get('client_order_id', '')) == str(client_order_id)),
                        None
                    )
                    if matched and matched.get('id'):
                        log.info(
                            f"✅ Found existing order {matched['id']} via client_order_id lookup — resuming monitor"
                        )
                        _log_activity('order_placing',
                            f"{side.upper()} {symbol}: Found existing order {matched['id']} via client_order_id lookup",
                            session_id=session_id, severity='info',
                            details={'order_id': matched['id'], 'client_order_id': client_order_id})
                        order_result = matched
                        break
                except Exception as _dup_e:
                    log.warning(f"Could not look up duplicate order: {_dup_e}")

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

        # Feature 10: Durable pre-fill execution intent — written once per order placement.
        # Survives backend crash. Used by orphan check on EXITING restore.
        try:
            from .mmm_audit_log import get_event_log as _get_el
            _get_el().enqueue_event(
                session_id=session_id or '',
                event_category='EXECUTION_INTENT',
                event_type='ORDER_INTENT',
                remark=f'{side.upper()} {size} lots {symbol} @ ${mid_price:.2f}',
                severity='INFO',
                details={'order_id': order_id, 'client_order_id': client_order_id,
                         'symbol': symbol, 'side': side, 'size': size, 'mid_price': mid_price},
            )
        except Exception:
            pass

        # Step 2: Wait + Reprice loop
        while attempts < _max_attempts:
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

                # Audit fix: using _parse_fill_price() helper (deduplicates 4 copies of this logic)
                try:
                    fill_price = _parse_fill_price(raw_fill)
                except ValueError as _parse_err:
                    log.error(
                        f"❌ Order {order_id} fill price invalid: {_parse_err}. "
                        f"Order data: state={final_order_data.get('state')}, "
                        f"raw_fill={raw_fill!r}"
                    )
                    return self._failure(
                        f"Invalid fill_price: {_parse_err}",
                        symbol, side, size,
                        order_id=order_id, attempts=attempts,
                        total_time=round(elapsed, 2),
                    )
                
                raw_unfilled = final_order_data.get('unfilled_size')
                if raw_unfilled is not None:
                    try:
                        unfilled_int = int(raw_unfilled)
                    except (ValueError, TypeError):
                        log.error(
                            f"❌ Order {order_id} has unparseable unfilled_size: {raw_unfilled!r}"
                        )
                        return self._failure(
                            f"Cannot parse unfilled_size: {raw_unfilled}",
                            symbol, side, size,
                            order_id=order_id, attempts=attempts,
                            total_time=round(elapsed, 2),
                        )
                    filled_size = size - unfilled_int
                    if filled_size <= 0:
                        log.error(
                            f"❌ Order {order_id} marked filled but filled_size={filled_size} "
                            f"(size={size}, unfilled={unfilled_int})"
                        )
                        return self._failure(
                            f"Order filled but computed filled_size={filled_size}",
                            symbol, side, size,
                            order_id=order_id, attempts=attempts,
                            total_time=round(elapsed, 2),
                        )
                else:
                    # Robust v2 Fix #3: Missing unfilled_size means we cannot
                    # verify fill quantity. Log error and treat as failure to
                    # prevent phantom positions corrupting P&L calculations.
                    log.error(
                        f"❌ Order {order_id} filled but unfilled_size field MISSING "
                        f"from response. Cannot verify fill quantity. "
                        f"Order data keys: {list(final_order_data.keys())}"
                    )
                    return self._failure(
                        f"Order filled but unfilled_size missing — cannot verify fill quantity",
                        symbol, side, size,
                        order_id=order_id, attempts=attempts,
                        total_time=round(elapsed, 2),
                    )

                log.info(
                    f"✅ Order {order_id} FILLED at ${fill_price:.2f} "
                    f"after {elapsed:.1f}s ({attempts} attempt(s))"
                )

                _log_activity('order_filled',
                    f"✅ {side.upper()} {symbol} FILLED @ ${fill_price:.2f} in {elapsed:.1f}s",
                    session_id=session_id, severity='success',
                    details={'order_id': order_id, 'fill_price': fill_price,
                             'elapsed': round(elapsed, 1), 'attempts': attempts})

                # Feature 10: Confirm the execution intent — links to ORDER_INTENT via order_id.
                try:
                    from .mmm_audit_log import get_event_log as _get_el
                    _get_el().enqueue_event(
                        session_id=session_id or '',
                        event_category='EXECUTION_INTENT',
                        event_type='ORDER_CONFIRMED',
                        remark=f'{side.upper()} {filled_size} lots @ ${fill_price:.2f}',
                        severity='INFO',
                        details={'order_id': order_id, 'fill_price': fill_price,
                                 'filled_size': filled_size},
                    )
                except Exception:
                    pass

                return {
                    'success': True,
                    'order_id': order_id,
                    'client_order_id': client_order_id,
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
            log.info(f"⏰ Order {order_id} not filled after {FILL_TIMEOUT}s, repricing (attempt {attempts}/{_max_attempts})")

            _log_activity('order_repricing',
                f"Order {order_id} not filled after {FILL_TIMEOUT}s, repricing (attempt {attempts}/{_max_attempts})",
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

            # max_buy_price cap: abort if market has moved above the allowed ceiling.
            # This prevents close_at_threshold from buying back at a price > threshold
            # after a premium bounce during the reprice window.
            if max_buy_price is not None and side.lower() == 'buy' and new_mid > max_buy_price:
                log.warning(
                    f"⛔ Reprice aborted: new_mid ${new_mid:.2f} > max_buy_price ${max_buy_price:.2f} "
                    f"for {symbol}. Cancelling order {order_id} — premium rose above threshold."
                )
                _log_activity('order_cancelled',
                    f"Reprice cancelled — premium ${new_mid:.2f} > cap ${max_buy_price:.2f} (threshold guard)",
                    session_id=session_id, severity='warning',
                    details={'order_id': order_id, 'new_mid': new_mid, 'max_buy_price': max_buy_price})
                await self._cancel_order(order_id, product_id, rest_client)
                elapsed = time.time() - start_time
                return self._failure(
                    f'Reprice aborted: premium ${new_mid:.2f} rose above close_at_threshold cap ${max_buy_price:.2f}',
                    symbol, side, size,
                    order_id=order_id, attempts=attempts,
                    total_time=round(elapsed, 2),
                )

            # After halfway through attempts: switch to best_bid for sells (more aggressive)
            # This widens our chances of a fill when mid-price is not attracting buyers
            if side == 'sell' and attempts >= _aggressive_from:
                best_bid = new_quotes.get('best_bid', 0)
                if best_bid > 0 and abs(best_bid - mid_price) >= 0.01:
                    log.info(
                        f"🎯 Switching to aggressive fill: using best_bid ${best_bid:.2f} "
                        f"instead of mid ${new_mid:.2f} (attempt {attempts}/{_max_attempts})"
                    )
                    _log_activity('order_repricing_aggressive',
                        f"Switching to best_bid ${best_bid:.2f} for better fill odds "
                        f"(attempt {attempts}/{_max_attempts})",
                        session_id=session_id, severity='warning',
                        details={'order_id': order_id, 'best_bid': best_bid, 'mid': new_mid})
                    new_mid = best_bid

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
                        # Audit fix BUG-3: use _parse_fill_price() (same as main fill path)
                        # instead of the old inline validation which omitted the range check
                        # (price > 0 and < 1_000_000) that _parse_fill_price() provides.
                        raw_fill = status.get('average_fill_price')
                        _cancel_fill_ok = False
                        try:
                            fill_price = _parse_fill_price(raw_fill)
                            _cancel_fill_ok = True
                        except ValueError as _cp_err:
                            log.error(f"❌ Order {order_id} cancel-path invalid fill_price: {_cp_err}")
                        if _cancel_fill_ok:
                            # Robust v2 Fix #3 (cancel-during-reprice): Check unfilled_size
                            _cancel_raw_uf = status.get('unfilled_size')
                            if _cancel_raw_uf is not None:
                                try:
                                    _cancel_filled = size - int(_cancel_raw_uf)
                                    if _cancel_filled > 0:
                                        _cancel_fill_size = _cancel_filled
                                    else:
                                        # unfilled_size == size means nothing was actually
                                        # filled despite the order showing 'filled' state.
                                        # This is an exchange data race on reduce_only orders
                                        # (e.g. position already closed by a concurrent order).
                                        # Do NOT return success — treat as failed and continue.
                                        log.error(
                                            f"❌ Order {order_id} shows state=filled but "
                                            f"unfilled_size={_cancel_raw_uf} == size={size} "
                                            f"(0 lots actually filled). Treating as failed."
                                        )
                                        break  # exit reprice loop → fall through to _failure()
                                except (ValueError, TypeError):
                                    _cancel_fill_size = size
                            else:
                                _cancel_fill_size = size
                            elapsed = time.time() - start_time
                            log.info(f"✅ Order {order_id} filled during cancel attempt at ${fill_price:.2f} ({_cancel_fill_size}/{size})")
                            return {
                                'success': True,
                                'order_id': order_id,
                                'fill_price': fill_price,
                                'filled_size': _cancel_fill_size,
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

                # Place fresh order (same client_order_id — replacement for same intent)
                order_result = await self._place_limit_order(
                    symbol, side, size, new_mid, reduce_only, rest_client,
                    client_order_id=client_order_id,
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
        log.error(f"❌ Max reprice attempts ({_max_attempts}) exhausted for {symbol} after {elapsed:.0f}s")
        _log_activity('order_failed',
            f"❌ {side.upper()} {symbol} NOT FILLED after {_max_attempts} attempts ({elapsed:.0f}s)",
            session_id=session_id, severity='error',
            details={'order_id': order_id, 'attempts': _max_attempts, 'elapsed': round(elapsed, 1)})

        return self._failure(
            f'Max reprice attempts exhausted after {elapsed:.0f}s',
            symbol, side, size,
            order_id=order_id, attempts=attempts,
            total_time=round(elapsed, 2),
        )

    # =========================================================================
    # Emergency Execute — Taker fills for crash/margin-breach scenarios
    # =========================================================================

    # Emergency execution constants
    EMERGENCY_FILL_TIMEOUT = 10       # Max 10 seconds per attempt
    EMERGENCY_MAX_ATTEMPTS = 2        # At most 2 tries
    EMERGENCY_SLIPPAGE_TICKS = 5      # Extra ticks beyond best bid/ask

    async def emergency_execute(
        self,
        symbol: str,
        side: str,
        size: int,
        reduce_only: bool = True,
        session_id: str = None,
        max_slippage_pct: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Emergency order execution — designed for crash/margin-breach scenarios.

        Key differences from smart_execute:
        - Uses IOC (Immediate-or-Cancel) limit orders at aggressive prices
        - Allows taker fills (post_only=False) for instant execution
        - Single 10-second timeout (not 60s × 10 reprices)
        - Max 2 attempts total (~20s worst case vs 10 min)
        - Accepts slippage to guarantee fills in fast-moving markets

        Args:
            symbol: Options symbol (e.g., 'C-BTC-100000-150226')
            side: 'buy' or 'sell'
            size: Number of lots (contracts)
            reduce_only: If True, only reduces position (default True for emergency)
            session_id: Session ID for activity logging
            max_slippage_pct: Maximum slippage % from mid-price to accept

        Returns:
            Same shape as smart_execute for compatibility.
        """
        start_time = time.time()

        log.critical(
            f"🚨 EMERGENCY EXECUTE: {side.upper()} {size} {symbol} "
            f"(slippage cap: {max_slippage_pct}%)"
        )

        _log_activity('emergency_order',
            f"🚨 EMERGENCY {side.upper()} {size} {symbol} — crash protocol active",
            session_id=session_id, severity='critical',
            details={'symbol': symbol, 'side': side, 'size': size,
                     'max_slippage_pct': max_slippage_pct})

        rest_client = self._create_rest_client()

        for attempt in range(1, self.EMERGENCY_MAX_ATTEMPTS + 1):
            try:
                # Fetch fresh quotes
                quotes = await self._fetch_quotes(symbol, rest_client)
                if not quotes or quotes.get('best_bid', 0) <= 0 or quotes.get('best_ask', 0) <= 0:
                    log.error(f"🚨 Emergency attempt {attempt}: no valid quotes for {symbol}")
                    if attempt < self.EMERGENCY_MAX_ATTEMPTS:
                        await asyncio.sleep(1)
                        continue
                    return self._failure('No valid quotes in emergency mode',
                                         symbol, side, size,
                                         total_time=round(time.time() - start_time, 2))

                bid = quotes['best_bid']
                ask = quotes['best_ask']
                tick = quotes.get('tick_size', 0.5)

                # Calculate aggressive price that will fill as taker
                if side.lower() == 'buy':
                    # Buy at ask + slippage (overpay to guarantee fill)
                    slippage_amount = ask * (max_slippage_pct / 100.0)
                    aggressive_price = ask + slippage_amount
                else:
                    # Sell at bid - slippage (accept less to guarantee fill)
                    slippage_amount = bid * (max_slippage_pct / 100.0)
                    aggressive_price = max(bid - slippage_amount, tick)  # Floor at 1 tick

                # Round to tick size
                if tick > 0:
                    aggressive_price = round(aggressive_price / tick) * tick
                aggressive_price = round(aggressive_price, 2)

                log.info(
                    f"🚨 Emergency attempt {attempt}: {side.upper()} {size} {symbol} "
                    f"@ ${aggressive_price:.2f} (bid=${bid:.2f}, ask=${ask:.2f}, "
                    f"slippage={max_slippage_pct}%)"
                )

                _log_activity('emergency_placing',
                    f"🚨 Emergency placing: {side.upper()} {size} {symbol} "
                    f"@ ${aggressive_price:.2f} (IOC, taker allowed)",
                    session_id=session_id, severity='critical',
                    details={'price': aggressive_price, 'bid': bid, 'ask': ask,
                             'attempt': attempt})

                # Place IOC limit order — taker fill allowed (post_only=False)
                response = await rest_client.place_order_by_symbol(
                    symbol=symbol,
                    side=side,
                    price=aggressive_price,
                    size=int(size),
                    order_type="limit_order",
                    time_in_force="ioc",      # Immediate-or-Cancel
                    post_only=False,           # Allow taker fills
                    reduce_only=reduce_only,
                )

                result = response.get('result', response)
                order_id = str(result.get('id', ''))

                if not order_id:
                    log.error(f"🚨 Emergency order placement failed: {response}")
                    if attempt < self.EMERGENCY_MAX_ATTEMPTS:
                        await asyncio.sleep(1)
                        continue
                    return self._failure(
                        f"Emergency order placement failed: {response}",
                        symbol, side, size,
                        total_time=round(time.time() - start_time, 2))

                # IOC fills instantly or cancels — wait briefly then check
                await asyncio.sleep(2)

                product_id = result.get('product_id')
                order_data = await self._get_order_status(order_id, product_id, rest_client)

                if not order_data:
                    log.warning(f"🚨 Cannot fetch order {order_id} status, using placement data")
                    order_data = result

                state = str(order_data.get('state', '')).lower()

                if state in ORDER_STATES_FILLED:
                    raw_fill = order_data.get('average_fill_price')
                    # Robust v2 Fix #22 (emergency path): Guard fill_price parsing
                    import math as _math_e  # noqa
                    if raw_fill and str(raw_fill).strip() not in ('', '0'):
                        try:
                            fill_price = float(raw_fill)
                            if _math_e.isnan(fill_price) or _math_e.isinf(fill_price):
                                raise ValueError(f"Invalid numeric value: {raw_fill}")
                        except (ValueError, TypeError) as _ep:
                            log.error(f"❌ Emergency order {order_id} unparseable fill_price: {raw_fill!r} ({_ep})")
                            fill_price = aggressive_price  # Emergency: use aggressive_price as fallback
                    else:
                        # C4 NOTE: average_fill_price is missing despite state=filled.
                        # This is an exchange data-lag edge case on IOC orders.
                        # We fall back to aggressive_price (the IOC limit, worst-case floor)
                        # rather than returning failure — a failure return here would cause
                        # the next heartbeat to re-attempt a buyback that already executed,
                        # risking a double-close. Conservative understatement of fill price
                        # is safer than a double-execution. Log at error level so operators
                        # can reconcile manually if needed.
                        log.error(
                            f"❌ Emergency order {order_id} state=filled but "
                            f"average_fill_price missing — using aggressive_price "
                            f"({aggressive_price:.2f}) as conservative fallback. "
                            f"Manual reconciliation may be needed."
                        )
                        fill_price = aggressive_price

                    # Audit fix BUG-1: Guard unfilled_size parsing.
                    # When state='filled' but unfilled_size==size, nothing was actually
                    # filled (exchange data race on reduce_only orders — same scenario
                    # as smart_execute lines 432-457 which returns _failure() here).
                    # Returning success=True in this case would falsely mark the position
                    # closed on exchange while it remains open, silently bypassing max-loss.
                    raw_unfilled = order_data.get('unfilled_size')
                    if raw_unfilled is not None:
                        try:
                            unfilled_int = int(raw_unfilled)
                            filled_size = size - unfilled_int
                            if filled_size <= 0:
                                log.error(
                                    f"❌ Emergency order {order_id} state=filled but "
                                    f"unfilled_size={unfilled_int} == size={size} "
                                    f"(0 lots actually filled). Returning failure — "
                                    f"position NOT closed on exchange."
                                )
                                return self._failure(
                                    f"Emergency order filled but computed filled_size={filled_size} "
                                    f"(unfilled_size={unfilled_int} == size={size})",
                                    symbol, side, size,
                                    order_id=order_id, attempts=attempt,
                                    total_time=round(time.time() - start_time, 2),
                                )
                        except (ValueError, TypeError):
                            log.error(f"❌ Emergency order {order_id} unparseable unfilled_size: {raw_unfilled!r}")
                            filled_size = size  # Emergency: assume full fill as last resort
                    else:
                        log.warning(f"⚠️ Emergency order {order_id} unfilled_size missing, assuming full fill")
                        filled_size = size

                    elapsed = time.time() - start_time

                    log.critical(
                        f"🚨 EMERGENCY FILL: {side.upper()} {filled_size} {symbol} "
                        f"@ ${fill_price:.2f} in {elapsed:.1f}s"
                    )

                    _log_activity('emergency_filled',
                        f"🚨 EMERGENCY FILLED: {side.upper()} {symbol} "
                        f"@ ${fill_price:.2f} in {elapsed:.1f}s",
                        session_id=session_id, severity='critical',
                        details={'order_id': order_id, 'fill_price': fill_price,
                                 'filled_size': filled_size, 'elapsed': round(elapsed, 1)})

                    return {
                        'success': True,
                        'order_id': order_id,
                        'fill_price': fill_price,
                        'filled_size': filled_size,
                        'execution_type': 'emergency_ioc',
                        'attempts': attempt,
                        'total_time': round(elapsed, 2),
                        'error': None,
                        'symbol': symbol,
                        'side': side,
                        'size': size,
                        'order_details': order_data,
                    }

                elif state in ORDER_STATES_DEAD or state == 'open':
                    # IOC was cancelled (no fill) or partially
                    unfilled = order_data.get('unfilled_size', size)
                    log.warning(
                        f"🚨 Emergency IOC {state}: {symbol} — "
                        f"unfilled={unfilled}/{size}. "
                        f"{'Retrying with more aggression...' if attempt < self.EMERGENCY_MAX_ATTEMPTS else 'Giving up.'}"
                    )
                    # Try more aggressive price on next attempt
                    max_slippage_pct = min(max_slippage_pct * 2, 20.0)

                    if attempt < self.EMERGENCY_MAX_ATTEMPTS:
                        continue

                    # Check for partial fill
                    # Robust v2 Fix #3/#22 (emergency partial path): Guard parsing
                    raw_fill = order_data.get('average_fill_price')
                    raw_unfilled = order_data.get('unfilled_size')
                    _partial_ok = False
                    if raw_unfilled is not None:
                        try:
                            _uf = int(raw_unfilled)
                            if _uf < size and (size - _uf) > 0:
                                filled_size = size - _uf
                                _partial_ok = True
                        except (ValueError, TypeError):
                            log.error(f"❌ Emergency partial: unparseable unfilled_size: {raw_unfilled!r}")
                    if _partial_ok:
                        import math as _math_ep  # noqa
                        try:
                            fill_price = float(raw_fill) if raw_fill else aggressive_price
                            if _math_ep.isnan(fill_price) or _math_ep.isinf(fill_price):
                                fill_price = aggressive_price
                        except (ValueError, TypeError):
                            fill_price = aggressive_price
                        elapsed = time.time() - start_time
                        log.warning(
                            f"🚨 Emergency PARTIAL fill: {filled_size}/{size} @ ${fill_price:.2f}"
                        )
                        return {
                            'success': True,  # Partial is better than nothing in emergency
                            'order_id': order_id,
                            'fill_price': fill_price,
                            'filled_size': filled_size,
                            'execution_type': 'emergency_partial',
                            'attempts': attempt,
                            'total_time': round(time.time() - start_time, 2),
                            'error': f'Partial fill: {filled_size}/{size}',
                            'symbol': symbol,
                            'side': side,
                            'size': size,
                        }

                    return self._failure(
                        f"Emergency IOC not filled after {attempt} attempts (state={state})",
                        symbol, side, size, order_id=order_id,
                        attempts=attempt,
                        total_time=round(time.time() - start_time, 2))
                else:
                    # Unknown state — unexpected
                    log.error(f"🚨 Emergency: unexpected order state '{state}' for {order_id}")
                    if attempt < self.EMERGENCY_MAX_ATTEMPTS:
                        continue
                    return self._failure(
                        f"Emergency: unexpected order state '{state}'",
                        symbol, side, size, order_id=order_id,
                        attempts=attempt,
                        total_time=round(time.time() - start_time, 2))

            except Exception as e:
                log.exception(f"🚨 Emergency execute attempt {attempt} crashed: {e}")
                _log_activity('emergency_error',
                    f"🚨 EMERGENCY ERROR: {str(e)}",
                    session_id=session_id, severity='critical',
                    details={'error': str(e), 'attempt': attempt})
                if attempt < self.EMERGENCY_MAX_ATTEMPTS:
                    await asyncio.sleep(1)
                    continue
                return self._failure(
                    f"Emergency execute crashed: {str(e)}",
                    symbol, side, size,
                    total_time=round(time.time() - start_time, 2))

        # Should not reach here, but safety net
        return self._failure(
            'Emergency execute exhausted all attempts',
            symbol, side, size,
            total_time=round(time.time() - start_time, 2))

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

        # Execute both legs concurrently.
        # Use 8 reprice attempts (8×60s = 8 min max) for entry — more patient than
        # adjustments (which use the default 4) because entry orders run concurrently
        # and we don't want to trigger rollback due to one leg being slightly slower.
        # After attempt 5 (halfway), pricing switches to best_bid for more aggressive fills.
        ENTRY_REPRICE_ATTEMPTS = 8
        ce_task = self.smart_execute(
            ce_symbol, 'sell', lots,
            session_id=session_id,
            max_reprice_attempts=ENTRY_REPRICE_ATTEMPTS,
        )
        pe_task = self.smart_execute(
            pe_symbol, 'sell', lots,
            session_id=session_id,
            max_reprice_attempts=ENTRY_REPRICE_ATTEMPTS,
        )

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

            # Bug #5 fix: rollback successful leg if the other failed
            rollback_ok = False  # Track whether orphan position was cleaned up
            if ce_result.get('success') and not pe_result.get('success'):
                log.warning("⚠️ Rolling back CE leg (PE failed)")
                _log_activity('entry_rollback',
                    f"Rolling back CE leg: buying back {lots} {ce_symbol}",
                    session_id=session_id, severity='warning')
                try:
                    rollback = await self.smart_execute(
                        ce_symbol, 'buy', lots, reduce_only=True,
                        session_id=session_id,
                    )
                    if rollback.get('success'):
                        rollback_ok = True
                        log.info("✅ CE rollback successful — positions flat")
                        _log_activity('entry_rollback_ok',
                            f"CE rollback OK @ ${rollback.get('fill_price', 0):.2f} — no open positions",
                            session_id=session_id, severity='success')
                    else:
                        log.error(f"❌ CE rollback FAILED: {rollback.get('error')}")
                        _log_activity('entry_rollback_failed',
                            f"CE rollback FAILED — ORPHAN POSITION: {ce_symbol}. Close manually!",
                            session_id=session_id, severity='error')
                except Exception as e:
                    log.error(f"CE rollback exception: {e}")

            elif pe_result.get('success') and not ce_result.get('success'):
                log.warning("⚠️ Rolling back PE leg (CE failed)")
                _log_activity('entry_rollback',
                    f"Rolling back PE leg: buying back {lots} {pe_symbol}",
                    session_id=session_id, severity='warning')
                try:
                    rollback = await self.smart_execute(
                        pe_symbol, 'buy', lots, reduce_only=True,
                        session_id=session_id,
                    )
                    if rollback.get('success'):
                        rollback_ok = True
                        log.info("✅ PE rollback successful — positions flat")
                        _log_activity('entry_rollback_ok',
                            f"PE rollback OK @ ${rollback.get('fill_price', 0):.2f} — no open positions",
                            session_id=session_id, severity='success')
                    else:
                        log.error(f"❌ PE rollback FAILED: {rollback.get('error')}")
                        _log_activity('entry_rollback_failed',
                            f"PE rollback FAILED — ORPHAN POSITION: {pe_symbol}. Close manually!",
                            session_id=session_id, severity='error')
                except Exception as e:
                    log.error(f"PE rollback exception: {e}")
            else:
                rollback_ok = False  # Both failed — nothing to roll back

        return {
            'success': all_success,
            'ce': ce_result,
            'pe': pe_result,
            'total_premium': round(total_premium, 2),
            'rollback_ok': rollback_ok if not all_success else False,
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
        session_id: str = None,  # Audit fix BUG-2: was missing — activity logs had no session context
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
            session_id: Session ID for activity logging

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
            close_symbol, 'buy', close_lots, reduce_only=True,
            session_id=session_id,
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
            open_symbol, 'sell', open_lots,
            session_id=session_id,
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

    async def get_mid_price(self, symbol: str) -> float:
        """Fetch quotes for a symbol and return the mid-price."""
        quotes = await self._fetch_quotes(symbol)
        if not quotes:
            return 0.0
        return self._calculate_mid_price(quotes)

    # =========================================================================
    # Internal: Order Operations
    # =========================================================================

    async def _place_limit_order(
        self, symbol: str, side: str, size: int,
        price: float, reduce_only: bool = False,
        rest_client=None, client_order_id: str = None,
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
                    client_order_id=client_order_id,
                )

                result = response.get('result', response)
                log.info(f"✅ Order placed: {result.get('id', 'unknown')} @ ${current_price:.2f}")
                return result

            except Exception as e:
                err_str = str(e)

                # Immediately fail on "no position" errors — retrying is pointless
                if 'no_position_for_reduce_only' in err_str.lower() or 'no position' in err_str.lower():
                    log.warning(f"⚠️ No position exists for reduce_only {side} {symbol} — aborting immediately")
                    return {'error': err_str}

                is_post_only_reject = (
                    'post-only' in err_str.lower()
                    or 'post_only' in err_str.lower()
                    or 'immediate_execution' in err_str.lower()
                    or 'would have matched' in err_str.lower()
                )

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
# Singleton (M-4 fix: double-checked locking prevents TOCTOU race)
# =============================================================================

_executor_instance = None
_executor_lock = threading.Lock()


def get_executor() -> MMMExecutor:
    """Get or create the singleton MMM executor."""
    global _executor_instance
    if _executor_instance is None:
        with _executor_lock:
            if _executor_instance is None:
                _executor_instance = MMMExecutor()
    return _executor_instance
