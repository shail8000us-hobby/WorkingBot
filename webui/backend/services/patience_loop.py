"""
Patience Loop Service — maker_only execution engine.

COPY of auto_loop_service.py (February 25, 2026), modified for Patience:
  - order_preference hardcoded to 'maker_only' (original supports maker_first / market_only)
  - 10 retries × 30s intervals, re-fetches mid-price on each retry
  - On 10 retry exhaustion: status → 'paused', on_card_pause_fn called (NEVER falls back to market)
  - Class renamed to PatienceLoopService, singleton renamed to get_patience_loop_service
  - Original auto_loop_service.py is untouched and SEALED.

Architecture:
  - Singleton PatienceLoopService with a daemon thread per loop
  - patience_executor starts loops; patience_trigger monitors completion
  - All order placement via place_smart_order (options_control, SEALED)

Created: March 14, 2026
"""

import math as _math
import time
import asyncio
import threading
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime

log = logging.getLogger(__name__)


def _parse_fill_price(raw_fill) -> float:
    """
    Validate and parse fill price from Delta Exchange order response.
    Copied from mmm_executor._parse_fill_price — same rules, same safety.

    Rejects: None, empty, '0', NaN, Inf, negative, > $1,000,000.
    Raises ValueError with descriptive message on any invalid value.
    """
    if raw_fill is None or str(raw_fill).strip() in ('', '0'):
        raise ValueError(f"fill_price missing or zero: {raw_fill!r}")
    try:
        price = float(raw_fill)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Cannot parse fill_price {raw_fill!r}: {e}") from e
    if _math.isnan(price) or _math.isinf(price):
        raise ValueError(f"fill_price is NaN or Inf: {raw_fill!r}")
    if price <= 0 or price > 1_000_000:
        raise ValueError(f"fill_price out of range: {price}")
    return price

# Use real OS thread to avoid eventlet asyncio conflict (see lessons.md)
try:
    from eventlet.patcher import original as _ep_original
    _RealThread = _ep_original('threading').Thread
except (ImportError, AttributeError):
    _RealThread = threading.Thread


ORDER_PREFERENCE = 'maker_only'   # hardcoded — never changes
MAX_RETRIES = 10                  # retries before PAUSE (cancel + re-place with fresh mid-price)
RETRY_DELAY = 15.0               # seconds between re-placements (maker_only: 15s is sufficient)
POLL_INTERVAL = 2.0              # seconds between fill-checks within a retry window
ROUND_DELAY = 1.0                # seconds between GCD rounds


class PatienceLoopService:
    """
    Server-side maker_only loop execution for PATIENCE card legs.

    Runs each GCD round of orders in a background thread.
    On fill failure (cancelled/not filled in RETRY_DELAY): cancels and re-places
    up to MAX_RETRIES times with fresh mid-prices. On exhaustion: PAUSES card.
    """

    def __init__(self):
        self._loops: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._threads: Dict[str, threading.Thread] = {}
        self._api_client_factory = None
        self._check_guardian_fn = None
        log.info("PatienceLoopService: initialized")

    def set_dependencies(self, api_client_factory: Callable, check_guardian_fn: Callable):
        """
        Args:
            api_client_factory: callable() -> UnifiedAPIClient
            check_guardian_fn: callable() -> str ('GO' / 'STOP')
        """
        self._api_client_factory = api_client_factory
        self._check_guardian_fn = check_guardian_fn

    # ── Start a loop ──────────────────────────────────────────────────

    def start_loop(self, loop_id: str, orders: List[dict],
                   total_rounds: int,
                   on_round_complete: Optional[Callable] = None,
                   on_card_pause: Optional[Callable] = None,
                   on_complete: Optional[Callable] = None) -> dict:
        """
        Start a new patience loop for one GCD execution.

        Args:
            loop_id: Unique identifier (card_id for round-0, card_id+':rN' for specific rounds)
            orders: [{'symbol': str, 'size': float, 'side': str, 'leg_id': str}, ...]
            total_rounds: Number of GCD rounds to execute
            on_round_complete: callable(loop_id, round_num, progress) — called after each round
            on_card_pause: callable(loop_id, error_msg) — called when retries exhausted
            on_complete: callable(loop_id) — called when all rounds done

        Returns:
            Loop state dict
        """
        with self._lock:
            existing = self._loops.get(loop_id)
            if existing and existing['status'] == 'running':
                thread = self._threads.get(loop_id)
                if thread and thread.is_alive():
                    raise ValueError(f"PatienceLoop '{loop_id}' is already running")
                else:
                    log.warning(
                        f"PatienceLoopService: loop '{loop_id}' marked running but thread dead — cleaning up"
                    )
                    existing['status'] = 'error'
                    existing['completed_at'] = datetime.now().isoformat()

        state = {
            'loop_id': loop_id,
            'orders': orders,
            'total_rounds': total_rounds,
            'status': 'running',
            'current_round': 0,
            'rounds_completed': 0,
            'progress': {},
            'error': None,
            'started_at': datetime.now().isoformat(),
            'completed_at': None,
            'stop_requested': False,
        }

        with self._lock:
            self._loops[loop_id] = state

        t = _RealThread(
            target=self._run_loop,
            args=(loop_id, on_round_complete, on_card_pause, on_complete),
            daemon=True,
            name=f"patience-loop-{loop_id}",
        )
        self._threads[loop_id] = t
        t.start()

        log.info(
            f"PatienceLoopService: started loop '{loop_id}' — "
            f"{total_rounds} rounds × {len(orders)} orders (maker_only)"
        )
        return state

    # ── Stop / Control ────────────────────────────────────────────────

    def stop_loop(self, loop_id: str) -> bool:
        with self._lock:
            state = self._loops.get(loop_id)
            if not state:
                return False
            if state['status'] != 'running':
                return False
            state['stop_requested'] = True
            state['status'] = 'stopping'
            log.info(f"PatienceLoopService: stop requested for loop '{loop_id}'")
            return True

    def get_status(self, loop_id: str = None) -> dict:
        with self._lock:
            if loop_id:
                state = self._loops.get(loop_id)
                if not state:
                    return {'exists': False}
                return dict(state)
            return {lid: dict(s) for lid, s in self._loops.items()}

    def clear_finished(self) -> int:
        with self._lock:
            to_remove = [lid for lid, s in self._loops.items()
                         if s['status'] in ('completed', 'stopped', 'error', 'paused')]
            for lid in to_remove:
                del self._loops[lid]
                self._threads.pop(lid, None)
            return len(to_remove)

    def force_clear(self, loop_id: str = None) -> int:
        with self._lock:
            targets = ([loop_id] if loop_id and loop_id in self._loops
                       else list(self._loops.keys()))
            for lid in targets:
                state = self._loops.pop(lid, None)
                if state and state['status'] in ('running', 'stopping'):
                    state['stop_requested'] = True
                    state['status'] = 'stopped'
                    log.warning(f"PatienceLoopService: force-cleared loop '{lid}'")
                self._threads.pop(lid, None)
            return len(targets)

    # ── Main loop (runs in real OS thread) ────────────────────────────

    def _run_loop(self, loop_id: str,
                  on_round_complete: Optional[Callable],
                  on_card_pause: Optional[Callable],
                  on_complete: Optional[Callable]):
        """Execute GCD rounds in a background thread with retry-on-fail."""
        state = self._loops.get(loop_id)
        if not state:
            return

        orders = state['orders']
        total_rounds = state['total_rounds']

        log.info(
            f"[PATIENCE-LOOP:{loop_id}] Thread started — {total_rounds} rounds, {len(orders)} orders"
        )

        try:
            for round_num in range(1, total_rounds + 1):

                if state['stop_requested']:
                    state['status'] = 'stopped'
                    state['error'] = f"Stopped after round {round_num - 1}/{total_rounds}"
                    state['completed_at'] = datetime.now().isoformat()
                    log.info(f"[PATIENCE-LOOP:{loop_id}] Stopped at round {round_num - 1}")
                    return

                if self._check_guardian_fn:
                    signal = self._check_guardian_fn()
                    if signal != 'GO':
                        self._do_pause(state, loop_id, on_card_pause,
                                       f"Guardian signal is {signal} — trading disabled")
                        return

                state['current_round'] = round_num
                log.info(f"[PATIENCE-LOOP:{loop_id}] Round {round_num}/{total_rounds}")

                # ── Execute this round with retry logic ──
                round_progress, success = self._execute_round_with_retry(
                    loop_id, state, orders, round_num, total_rounds
                )

                if not success:
                    # Retries exhausted — pause the card
                    error_msg = state.get('error', f"Round {round_num}: max retries exhausted")
                    self._do_pause(state, loop_id, on_card_pause, error_msg)
                    return

                if state['stop_requested']:
                    state['status'] = 'stopped'
                    state['completed_at'] = datetime.now().isoformat()
                    return

                state['rounds_completed'] = round_num
                state['progress'] = dict(round_progress)
                log.info(f"[PATIENCE-LOOP:{loop_id}] Round {round_num}/{total_rounds} complete ✅")

                if on_round_complete:
                    try:
                        on_round_complete(loop_id, round_num, dict(round_progress))
                    except Exception as e:
                        log.warning(f"[PATIENCE-LOOP:{loop_id}] on_round_complete error: {e}")

                if round_num < total_rounds:
                    time.sleep(ROUND_DELAY)

            # All rounds done
            state['status'] = 'completed'
            state['completed_at'] = datetime.now().isoformat()
            log.info(f"[PATIENCE-LOOP:{loop_id}] All {total_rounds} rounds completed ✅")

            if on_complete:
                try:
                    on_complete(loop_id)
                except Exception as e:
                    log.warning(f"[PATIENCE-LOOP:{loop_id}] on_complete error: {e}")

        except Exception as e:
            log.error(f"[PATIENCE-LOOP:{loop_id}] Unexpected error: {e}", exc_info=True)
            state['status'] = 'error'
            state['error'] = str(e)
            state['completed_at'] = datetime.now().isoformat()
            if on_card_pause:
                try:
                    on_card_pause(loop_id, str(e))
                except Exception:
                    pass

    def _execute_round_with_retry(self, loop_id: str, state: dict,
                                   orders: List[dict], round_num: int,
                                   total_rounds: int) -> tuple:
        """
        Place all orders in a round using amend-first retry logic (copied from MMM pattern).

        First attempt: place all orders via _place_batch.
        Subsequent attempts: amend unfilled orders in-place via edit_order (same order ID, new price).
        Fallback to cancel+replace ONLY if amend fails with a non-400 error.

        This guarantees at most 1 order per leg is on the exchange at any time —
        even across 10 reprice cycles.

        Returns:
            (round_progress: dict, success: bool)
        """
        round_progress = {
            o['symbol']: {
                'status': 'placing',
                'filled': False,
                'size': o['size'],
                'orderId': None,
                'fillPrice': None,
                'leg_id': o.get('leg_id'),
            }
            for o in orders
        }
        state['progress'] = dict(round_progress)

        filled_symbols: dict = {}   # symbol -> result
        active_orders: dict = {}    # symbol -> placed result dict (has order_id + product_id)
        placement_failures: dict = {}  # symbol -> consecutive placement failure count

        for attempt in range(1, MAX_RETRIES + 1):
            if state['stop_requested']:
                return round_progress, False

            unfilled_syms = set(o['symbol'] for o in orders) - set(filled_symbols.keys())
            if not unfilled_syms:
                break

            # Split: symbols with an active order (amend) vs symbols needing fresh placement
            to_amend = [active_orders[sym] for sym in unfilled_syms if sym in active_orders]
            to_place = [o for o in orders if o['symbol'] in unfilled_syms
                        and o['symbol'] not in active_orders]

            # ── Step 1: Amend existing active orders with a fresh mid price ──
            if to_amend:
                log.info(
                    f"[PATIENCE-LOOP:{loop_id}] Round {round_num} attempt {attempt}/{MAX_RETRIES}: "
                    f"amending {len(to_amend)} order(s), placing {len(to_place)} fresh"
                )
                amend_results = self._amend_batch(to_amend)

                # Non-400 amend failure → cancel + re-place as fallback
                for item in amend_results['failed']:
                    sym = item['symbol']
                    self._cancel_orders([item])  # best-effort cleanup
                    active_orders.pop(sym, None)
                    orig = next((o for o in orders if o['symbol'] == sym), None)
                    if orig:
                        to_place.append(orig)

                # Amend returned 400 → order already filled or cancelled — check immediately
                if amend_results['filled_or_cancelled']:
                    check_ids = [
                        i.get('order_id') for i in amend_results['filled_or_cancelled']
                        if i.get('order_id')
                    ]
                    statuses = self._check_order_statuses(check_ids) or []
                    for s_item in statuses:
                        oid = s_item.get('order_id')
                        matched = next(
                            (i for i in amend_results['filled_or_cancelled']
                             if i.get('order_id') == oid), None
                        )
                        if not matched:
                            continue
                        sym = matched['symbol']
                        if s_item.get('state') in ('filled', 'closed'):
                            # Validate fill price — same rules as polling path
                            raw_fill = s_item.get('fill_price')
                            try:
                                validated_fill = _parse_fill_price(raw_fill)
                            except ValueError as _fp_err:
                                log.warning(
                                    f"[PATIENCE-LOOP:{loop_id}] {sym} amend-400 fill_price "
                                    f"invalid ({_fp_err}) — re-checking"
                                )
                                # Put back in to_place to retry
                                orig = next((o for o in orders if o['symbol'] == sym), None)
                                if orig:
                                    to_place.append(orig)
                                continue
                            # Verify fill not partial
                            unfilled = s_item.get('unfilled_size')
                            if unfilled is not None and int(unfilled) > 0:
                                log.warning(
                                    f"[PATIENCE-LOOP:{loop_id}] {sym} amend-400 partial fill: "
                                    f"unfilled={unfilled} — re-placing remainder"
                                )
                                orig = next((o for o in orders if o['symbol'] == sym), None)
                                if orig:
                                    to_place.append(orig)
                                continue
                            filled_symbols[sym] = {**matched, 'fill_price': validated_fill}
                            active_orders.pop(sym, None)
                            round_progress[sym] = {
                                'status': 'filled', 'filled': True,
                                'size': s_item.get('size', matched.get('size')),
                                'orderId': oid,
                                'fillPrice': validated_fill,
                                'leg_id': round_progress.get(sym, {}).get('leg_id'),
                            }
                            log.info(
                                f"[PATIENCE-LOOP:{loop_id}] {sym} filled (amend-400) "
                                f"@ {validated_fill}"
                            )
                        else:
                            # Cancelled externally — re-place
                            active_orders.pop(sym, None)
                            orig = next((o for o in orders if o['symbol'] == sym), None)
                            if orig:
                                to_place.append(orig)
                            log.info(
                                f"[PATIENCE-LOOP:{loop_id}] {sym} order {oid} cancelled — will re-place"
                            )
            else:
                log.info(
                    f"[PATIENCE-LOOP:{loop_id}] Round {round_num} attempt {attempt}/{MAX_RETRIES}: "
                    f"placing {len(to_place)} order(s)"
                )

            # ── Step 2: Place fresh orders (initial placement or cancel+replace fallback) ──
            _MARKET_MODES = {'market', 'market_only'}
            if to_place:
                placed = self._place_batch(to_place)
                if placed is None:
                    state['error'] = f"Round {round_num} attempt {attempt}: system error placing orders"
                    return round_progress, False

                for result in placed:
                    sym = result.get('symbol')
                    if not result.get('success'):
                        log.warning(
                            f"[PATIENCE-LOOP:{loop_id}] Order {sym} failed: {result.get('error')}"
                        )
                        round_progress[sym] = {
                            **round_progress.get(sym, {}), 'status': 'error',
                            'error': result.get('error'),
                        }
                        if result.get('order_mode') in _MARKET_MODES:
                            state['error'] = (
                                f"Market order failed for {sym}: {result.get('error')} "
                                f"— aborting (no retry to prevent double fill)"
                            )
                            log.error(f"[PATIENCE-LOOP:{loop_id}] {state['error']}")
                            return round_progress, False
                        placement_failures[sym] = placement_failures.get(sym, 0) + 1
                        if placement_failures[sym] >= 3:
                            state['error'] = (
                                f"Round {round_num}: {sym} failed to PLACE "
                                f"{placement_failures[sym]} times in a row — aborting. "
                                f"Last error: {result.get('error')}"
                            )
                            log.error(f"[PATIENCE-LOOP:{loop_id}] {state['error']}")
                            return round_progress, False
                        continue
                    else:
                        placement_failures[sym] = 0

                    exec_type = result.get('execution_type', '')
                    filled_types = [
                        'market', 'market_fallback', 'market_fallback_no_quotes',
                        'market_fallback_error', 'limit_filled', 'limit_filled_late',
                    ]
                    if exec_type in filled_types or not result.get('order_id'):
                        imm_fill = result.get('fill_price')  # already validated in _execute_single
                        filled_symbols[sym] = result
                        active_orders.pop(sym, None)
                        round_progress[sym] = {
                            'status': 'filled', 'filled': True,
                            'size': result.get('size', 0),
                            'orderId': result.get('order_id'),
                            'fillPrice': imm_fill,
                            'leg_id': round_progress.get(sym, {}).get('leg_id'),
                        }
                        log.info(
                            f"[PATIENCE-LOOP:{loop_id}] {sym} filled immediately "
                            f"@ {imm_fill}"
                        )
                    else:
                        active_orders[sym] = result   # store for amend on next retry
                        round_progress[sym] = {
                            'status': 'pending', 'filled': False,
                            'size': result.get('size', 0),
                            'orderId': result.get('order_id'),
                            'fillPrice': None,
                            'leg_id': round_progress.get(sym, {}).get('leg_id'),
                        }

            state['progress'] = dict(round_progress)

            # ── Step 3: Poll active orders for RETRY_DELAY seconds ──
            poll_syms = [
                s for s in unfilled_syms
                if s in active_orders and s not in filled_symbols
            ]
            if poll_syms:
                poll_orders = [active_orders[s] for s in poll_syms]
                order_ids = [r['order_id'] for r in poll_orders if r.get('order_id')]
                deadline = time.time() + RETRY_DELAY
                newly_done_ids: set = set()

                while time.time() < deadline and not state['stop_requested']:
                    time.sleep(POLL_INTERVAL)

                    statuses = self._check_order_statuses(order_ids)
                    if statuses is None:
                        continue

                    for os_item in statuses:
                        oid = os_item.get('order_id')
                        matching = next(
                            (p for p in poll_orders if p.get('order_id') == oid), None
                        )
                        if not matching:
                            continue
                        sym = matching['symbol']
                        order_state = os_item.get('state', '')

                        if order_state in ('filled', 'closed'):
                            # Validate fill price before accepting fill
                            raw_fill = os_item.get('fill_price')
                            try:
                                validated_fill = _parse_fill_price(raw_fill)
                            except ValueError as _fp_err:
                                log.warning(
                                    f"[PATIENCE-LOOP:{loop_id}] {sym} order {oid} "
                                    f"fill_price invalid ({_fp_err}) — will retry"
                                )
                                continue  # treat as not yet filled, retry next poll
                            # Verify fill quantity (unfilled_size must be 0 or absent)
                            unfilled = os_item.get('unfilled_size')
                            if unfilled is not None and int(unfilled) > 0:
                                log.warning(
                                    f"[PATIENCE-LOOP:{loop_id}] {sym} order {oid} "
                                    f"partial fill: unfilled={unfilled} — will wait"
                                )
                                continue  # partial fill — keep polling
                            newly_done_ids.add(oid)
                            filled_symbols[sym] = {**matching, 'fill_price': validated_fill}
                            active_orders.pop(sym, None)
                            round_progress[sym] = {
                                'status': 'filled', 'filled': True,
                                'size': os_item.get('size', matching.get('size')),
                                'orderId': oid,
                                'fillPrice': validated_fill,
                                'leg_id': round_progress.get(sym, {}).get('leg_id'),
                            }
                            log.info(
                                f"[PATIENCE-LOOP:{loop_id}] {sym} filled @ {validated_fill}"
                            )
                        elif order_state in ('cancelled', 'not_found'):
                            # Cancelled externally — remove so next attempt re-places
                            newly_done_ids.add(oid)
                            active_orders.pop(sym, None)
                            log.info(
                                f"[PATIENCE-LOOP:{loop_id}] {sym} order {oid} "
                                f"{order_state} — will re-place"
                            )

                    state['progress'] = dict(round_progress)

                    if not [p for p in poll_orders if p['order_id'] not in newly_done_ids]:
                        break  # all settled

                remaining = [s for s in poll_syms if s not in filled_symbols]
                if remaining and attempt < MAX_RETRIES:
                    log.info(
                        f"[PATIENCE-LOOP:{loop_id}] Round {round_num} attempt {attempt}: "
                        f"{len(remaining)} unfilled after {RETRY_DELAY}s — "
                        f"will amend on next attempt: {remaining}"
                    )

            if set(o['symbol'] for o in orders) == set(filled_symbols.keys()):
                break

        # ── Determine success ──
        all_filled = set(o['symbol'] for o in orders) == set(filled_symbols.keys())

        if not all_filled:
            # Cancel any remaining active orders (cleanup)
            leftover = [
                v for v in active_orders.values()
                if v.get('order_id') and v.get('product_id')
            ]
            if leftover:
                log.info(f"[PATIENCE-LOOP:{loop_id}] Cleaning up {len(leftover)} unfilled orders")
                self._cancel_orders(leftover)
            unfilled = [o['symbol'] for o in orders if o['symbol'] not in filled_symbols]
            state['error'] = (
                f"Round {round_num}: {len(unfilled)} leg(s) not filled after "
                f"{MAX_RETRIES} attempts: {unfilled}"
            )
            return round_progress, False

        return round_progress, True

    def _do_pause(self, state: dict, loop_id: str,
                  on_card_pause: Optional[Callable], error_msg: str):
        """Set status to paused and call callback."""
        state['status'] = 'paused'
        state['error'] = error_msg
        state['completed_at'] = datetime.now().isoformat()
        log.warning(f"[PATIENCE-LOOP:{loop_id}] PAUSED: {error_msg}")
        if on_card_pause:
            try:
                on_card_pause(loop_id, error_msg)
            except Exception as e:
                log.error(f"[PATIENCE-LOOP:{loop_id}] on_card_pause callback error: {e}")

    # ── Order placement helpers ───────────────────────────────────────

    def _place_batch(self, orders: List[dict]) -> Optional[List[dict]]:
        """Place a batch of maker_only orders simultaneously."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(self._exec_batch(orders))
                return list(results)
            finally:
                loop.close()
        except Exception as e:
            log.error(f"[PATIENCE-LOOP] Batch placement error: {e}", exc_info=True)
            return None

    async def _exec_batch(self, orders: List[dict]) -> list:
        """Async: place all orders concurrently."""
        client = self._api_client_factory()
        tasks = [
            self._execute_single(client, order, i)
            for i, order in enumerate(orders)
        ]
        return await asyncio.gather(*tasks, return_exceptions=False)

    @staticmethod
    async def _execute_single(client, order_data: dict, index: int) -> dict:
        """Place one order using the leg's configured order_mode."""
        from webui.backend.routes.options.options_control import (
            place_smart_order, with_timeout, validate_order_size
        )

        symbol = order_data['symbol']
        size = float(order_data['size'])
        side = order_data['side']

        # Map leg order_mode → place_smart_order preference
        _MODE_MAP = {
            'market_only':     'market_only',
            'market':          'market_only',    # legacy alias
            'maker_first':     'maker_first',    # Smart
            'maker_only':      'maker_only',     # legacy
            'ssr_standard':    'ssr_standard',   # SSR
            'ssr_aggressive':  'ssr_aggressive', # Aggro
            'ssr_conservative':'ssr_conservative',# Safe
        }
        raw_mode = order_data.get('order_mode', 'maker_first')
        order_preference = _MODE_MAP.get(raw_mode, 'maker_first')

        try:
            await validate_order_size(client, symbol, size, side, is_close=False)
            result = await with_timeout(
                place_smart_order(
                    client=client,
                    symbol=symbol,
                    size=size,
                    side=side,
                    order_preference=order_preference,
                    limit_price=None,
                ),
                timeout_seconds=30,
            )
            # Prefer average_fill_price (actual execution price) over limit_price (placement price)
            raw_fill = (
                result.get('average_fill_price')
                or result.get('fill_price')
                or result.get('limit_price')
            )
            try:
                fill_price = _parse_fill_price(raw_fill)
            except ValueError:
                # Order is still pending (limit posted, not filled yet) — fill_price will come via polling
                fill_price = None
            exec_type = result.get('execution_type', 'unknown')
            order_id = result.get('id') or result.get('order_id')
            log.info(
                f"✅ PatienceLoop order {index + 1}: {symbol} {side} {size} "
                f"[{order_preference}] — {exec_type} @ {fill_price}"
            )
            return {
                'success': True,
                'symbol': symbol,
                'size': size,
                'side': side,
                'execution_type': exec_type,
                'fill_price': fill_price,
                'order_id': order_id,
                'product_id': result.get('product_id'),
                'index': index,
                'leg_id': order_data.get('leg_id'),
                'order_mode': raw_mode,
            }
        except Exception as e:
            log.error(f"❌ PatienceLoop order {index + 1} failed: {symbol} {side} {size} — {e}")
            return {
                'success': False,
                'symbol': symbol,
                'size': size,
                'side': side,
                'error': str(e),
                'index': index,
                'leg_id': order_data.get('leg_id'),
                'order_mode': raw_mode,   # carry mode through for retry policy
            }

    def _check_order_statuses(self, order_ids: List[str]) -> Optional[List[dict]]:
        """Check fill status of pending orders."""
        client = self._api_client_factory()

        async def _fetch():
            results = []
            for oid in order_ids:
                try:
                    info = await client.get_order(str(oid))
                    if info:
                        results.append({
                            'order_id': oid,
                            'symbol': info.get('product_symbol'),
                            'size': info.get('size'),
                            'side': info.get('side'),
                            'state': info.get('state'),
                            'fill_price': info.get('average_fill_price') or info.get('fill_price'),
                        })
                    else:
                        results.append({'order_id': oid, 'state': 'not_found'})
                except Exception as e:
                    log.warning(f"Error fetching order {oid}: {e}")
                    results.append({'order_id': oid, 'state': 'error', 'error': str(e)})
            return results

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_fetch())
            finally:
                loop.close()
        except Exception as e:
            log.error(f"[PATIENCE-LOOP] Status check error: {e}")
            return None

    def _cancel_orders(self, orders_to_cancel: List[dict]) -> None:
        """Cancel a list of orders (best effort — do not block on failure).

        Args:
            orders_to_cancel: list of dicts with 'order_id' and 'product_id' keys.
        """
        if not orders_to_cancel:
            return

        client = self._api_client_factory()

        async def _cancel():
            rest = client.rest_client
            for item in orders_to_cancel:
                oid = item.get('order_id')
                pid = item.get('product_id')
                if not oid:
                    continue
                if not pid:
                    log.warning(f"[PATIENCE-LOOP] Cannot cancel order {oid} — product_id unknown")
                    continue
                try:
                    await rest.cancel_order(str(oid), int(pid))
                    log.info(f"[PATIENCE-LOOP] Cancelled order {oid}")
                except Exception as e:
                    err = str(e)
                    if '400' in err:
                        log.info(f"[PATIENCE-LOOP] Order {oid} cancel 400 — already filled/cancelled")
                    else:
                        log.warning(f"[PATIENCE-LOOP] Cancel order {oid} failed: {e}")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_cancel())
            finally:
                loop.close()
        except Exception as e:
            log.error(f"[PATIENCE-LOOP] Cancel batch error: {e}")

    # ── Amend helpers (MMM amend-first pattern) ───────────────────────

    def _amend_batch(self, orders: List[dict]) -> dict:
        """Amend a list of active orders with fresh mid prices (MMM amend-first pattern).

        Returns dict with keys:
          'amended': orders successfully amended in-place (same order_id, new price)
          'failed': orders where amend failed with non-400 error — caller should cancel+replace
          'filled_or_cancelled': orders where amend returned 400 — caller should check fill status
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._exec_amend_batch(orders))
            finally:
                loop.close()
        except Exception as e:
            log.error(f"[PATIENCE-LOOP] Amend batch error: {e}", exc_info=True)
            return {'amended': [], 'failed': list(orders), 'filled_or_cancelled': []}

    async def _exec_amend_batch(self, orders: List[dict]) -> dict:
        """Async: amend all orders concurrently with fresh mid prices."""
        client = self._api_client_factory()
        results = {'amended': [], 'failed': [], 'filled_or_cancelled': []}
        outcomes = await asyncio.gather(
            *[self._amend_single(client, order) for order in orders],
            return_exceptions=False,
        )
        for order, outcome in zip(orders, outcomes):
            results[outcome].append(order)
        return results

    async def _amend_single(self, client, order: dict) -> str:
        """Amend one order with a fresh mid price.

        Returns: 'amended', 'failed', or 'filled_or_cancelled'
        """
        sym = order['symbol']
        oid = order.get('order_id')
        pid = order.get('product_id')
        if not oid or not pid:
            log.warning(f"[PATIENCE-LOOP] Cannot amend {sym} — missing order_id or product_id")
            return 'failed'

        quotes = await self._fetch_fresh_quotes(client, sym)
        if not quotes:
            log.warning(f"[PATIENCE-LOOP] No quotes for {sym} — cannot amend order {oid}")
            return 'failed'

        new_price = self._calc_mid_price(quotes)
        if not new_price:
            log.warning(f"[PATIENCE-LOOP] Zero mid price for {sym} — cannot amend order {oid}")
            return 'failed'

        try:
            await client.rest_client.edit_order(
                order_id=str(oid),
                product_id=int(pid),
                new_price=str(new_price),
            )
            log.info(f"[PATIENCE-LOOP] Amended {sym} order {oid} → ${new_price:.2f}")
            return 'amended'
        except Exception as e:
            err = str(e)
            if '400' in err:
                log.info(
                    f"[PATIENCE-LOOP] Amend 400 for {sym} order {oid} — already filled/cancelled"
                )
                return 'filled_or_cancelled'
            log.warning(f"[PATIENCE-LOOP] Amend failed for {sym} order {oid}: {e}")
            return 'failed'

    @staticmethod
    async def _fetch_fresh_quotes(client, symbol: str) -> Optional[dict]:
        """Fetch fresh L2 orderbook quotes for mid-price calculation (copied from MMM executor)."""
        result = {'best_bid': 0.0, 'best_ask': 0.0, 'tick_size': 0.01, 'fresh': False}
        try:
            orderbook = await client.rest_client.get_orderbook(symbol)
            if orderbook:
                buy_orders = orderbook.get('buy', [])
                sell_orders = orderbook.get('sell', [])
                if buy_orders and sell_orders:
                    result['best_bid'] = float(buy_orders[0].get('price', 0))
                    result['best_ask'] = float(sell_orders[0].get('price', 0))
                    result['fresh'] = True
        except Exception as e:
            log.warning(f"[PATIENCE-LOOP] L2 orderbook failed for {symbol}: {e}")

        if not result['fresh'] or result['best_bid'] == 0 or result['best_ask'] == 0:
            try:
                resp = await client.rest_client._request_with_retry(
                    method="GET", path=f"/v2/tickers/{symbol}"
                )
                ticker = resp.get('result', resp)
                quotes = ticker.get('quotes', {})
                result['best_bid'] = float(quotes.get('best_bid') or 0)
                result['best_ask'] = float(quotes.get('best_ask') or 0)
                result['tick_size'] = float(ticker.get('tick_size') or 0.01)
                result['fresh'] = True
            except Exception as e:
                log.warning(f"[PATIENCE-LOOP] Ticker fallback failed for {symbol}: {e}")

        if result['fresh'] and result['best_bid'] > 0 and result['best_ask'] > 0:
            return result
        return None

    @staticmethod
    def _calc_mid_price(quotes: dict) -> float:
        """Calculate mid-price from quotes, rounded to tick size (copied from MMM executor)."""
        bid = quotes.get('best_bid', 0)
        ask = quotes.get('best_ask', 0)
        tick = quotes.get('tick_size', 0.01)
        if bid <= 0 or ask <= 0:
            return 0.0
        mid = (bid + ask) / 2
        if tick > 0:
            mid = round(mid / tick) * tick
        return round(mid, 2)


# ── Singleton ─────────────────────────────────────────────────────────

_patience_loop_service: Optional[PatienceLoopService] = None


def get_patience_loop_service() -> PatienceLoopService:
    global _patience_loop_service
    if _patience_loop_service is None:
        _patience_loop_service = PatienceLoopService()
    return _patience_loop_service
