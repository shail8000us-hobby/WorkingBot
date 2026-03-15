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

import time
import asyncio
import threading
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime

log = logging.getLogger(__name__)

# Use real OS thread to avoid eventlet asyncio conflict (see lessons.md)
try:
    from eventlet.patcher import original as _ep_original
    _RealThread = _ep_original('threading').Thread
except (ImportError, AttributeError):
    _RealThread = threading.Thread


ORDER_PREFERENCE = 'maker_only'   # hardcoded — never changes
MAX_RETRIES = 10                  # retries before PAUSE (cancel + re-place with fresh mid-price)
RETRY_DELAY = 30.0               # seconds between re-placements
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
        Place all orders in a round with retry logic.

        Retries up to MAX_RETRIES times:
          - Place orders (fresh mid-price each attempt via place_smart_order)
          - Poll for fills for RETRY_DELAY seconds
          - Cancel unfilled orders, retry with fresh mid-price
          - After MAX_RETRIES: signal PAUSE

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

        # Track which orders are already filled (accumulate across retries)
        filled_symbols: dict = {}   # symbol -> result
        pending_orders_all = list(orders)

        for attempt in range(1, MAX_RETRIES + 1):
            if state['stop_requested']:
                return round_progress, False

            # Only place unfilled orders
            to_place = [o for o in pending_orders_all if o['symbol'] not in filled_symbols]
            if not to_place:
                break   # all done

            modes = list({o.get('order_mode', 'maker_only') for o in to_place})
            log.info(
                f"[PATIENCE-LOOP:{loop_id}] Round {round_num} attempt {attempt}/{MAX_RETRIES}: "
                f"placing {len(to_place)} order(s) mode={modes}"
            )

            placed = self._place_batch(to_place)
            if placed is None:
                state['error'] = f"Round {round_num} attempt {attempt}: system error placing orders"
                return round_progress, False

            # Classify results
            placed_pending = []
            _MARKET_MODES = {'market', 'market_only'}
            for result in placed:
                sym = result.get('symbol')
                if not result.get('success'):
                    log.warning(
                        f"[PATIENCE-LOOP:{loop_id}] Order {sym} failed to place: {result.get('error')}"
                    )
                    round_progress[sym] = {**round_progress.get(sym, {}), 'status': 'error',
                                           'error': result.get('error')}
                    # Market orders must NEVER retry on failure — the order may have already
                    # landed on the exchange. A retry would cause a double fill.
                    if result.get('order_mode') in _MARKET_MODES:
                        state['error'] = (
                            f"Market order failed for {sym}: {result.get('error')} "
                            f"— aborting (no retry to prevent double fill)"
                        )
                        log.error(f"[PATIENCE-LOOP:{loop_id}] {state['error']}")
                        return round_progress, False
                    continue

                exec_type = result.get('execution_type', '')
                filled_types = [
                    'market', 'market_fallback', 'market_fallback_no_quotes',
                    'market_fallback_error', 'limit_filled', 'limit_filled_late',
                ]
                if exec_type in filled_types or not result.get('order_id'):
                    # Filled immediately
                    filled_symbols[sym] = result
                    round_progress[sym] = {
                        'status': 'filled', 'filled': True,
                        'size': result.get('size', 0),
                        'orderId': result.get('order_id'),
                        'fillPrice': result.get('fill_price'),
                        'leg_id': round_progress.get(sym, {}).get('leg_id'),
                    }
                    log.info(f"[PATIENCE-LOOP:{loop_id}] {sym} filled immediately @ {result.get('fill_price')}")
                else:
                    placed_pending.append(result)
                    round_progress[sym] = {
                        'status': 'pending', 'filled': False,
                        'size': result.get('size', 0),
                        'orderId': result.get('order_id'),
                        'fillPrice': None,
                        'leg_id': round_progress.get(sym, {}).get('leg_id'),
                    }

            state['progress'] = dict(round_progress)

            # ── Poll pending orders for RETRY_DELAY seconds ──
            if placed_pending:
                order_ids = [r['order_id'] for r in placed_pending if r.get('order_id')]
                deadline = time.time() + RETRY_DELAY
                newly_filled_ids: set = set()

                while time.time() < deadline and not state['stop_requested']:
                    time.sleep(POLL_INTERVAL)

                    statuses = self._check_order_statuses(order_ids)
                    if statuses is None:
                        continue

                    for os_item in statuses:
                        oid = os_item.get('order_id')
                        matching = next(
                            (p for p in placed_pending if p.get('order_id') == oid), None
                        )
                        if not matching:
                            continue

                        sym = matching['symbol']
                        order_state = os_item.get('state', '')

                        if order_state in ('filled', 'closed'):
                            newly_filled_ids.add(oid)
                            filled_symbols[sym] = {**matching, 'fill_price': os_item.get('fill_price')}
                            round_progress[sym] = {
                                'status': 'filled', 'filled': True,
                                'size': os_item.get('size', matching.get('size')),
                                'orderId': oid,
                                'fillPrice': os_item.get('fill_price'),
                                'leg_id': round_progress.get(sym, {}).get('leg_id'),
                            }
                            log.info(
                                f"[PATIENCE-LOOP:{loop_id}] {sym} filled @ {os_item.get('fill_price')}"
                            )

                    state['progress'] = dict(round_progress)

                    pending_remaining = [
                        p for p in placed_pending if p['order_id'] not in newly_filled_ids
                    ]
                    if not pending_remaining:
                        break   # all filled this attempt

                # Cancel orders that weren't filled in RETRY_DELAY window
                unfilled_orders = [
                    p for p in placed_pending if p['order_id'] not in newly_filled_ids
                ]
                if unfilled_orders:
                    unfilled_ids = [p['order_id'] for p in unfilled_orders if p.get('order_id')]
                    unfilled_syms = [p['symbol'] for p in unfilled_orders]
                    log.info(
                        f"[PATIENCE-LOOP:{loop_id}] Round {round_num} attempt {attempt}: "
                        f"{len(unfilled_orders)} unfilled after {RETRY_DELAY}s — cancelling: {unfilled_syms}"
                    )
                    self._cancel_orders(unfilled_ids)

                    if attempt < MAX_RETRIES:
                        log.info(
                            f"[PATIENCE-LOOP:{loop_id}] Will retry in 2s with fresh mid-price..."
                        )
                        time.sleep(2)  # small gap before re-placing

            # Check if all done
            if set(o['symbol'] for o in orders) == set(filled_symbols.keys()):
                break

        # Determine success
        all_filled = set(o['symbol'] for o in orders) == set(filled_symbols.keys())

        if not all_filled:
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
            fill_price = (
                result.get('fill_price')
                or result.get('limit_price')
                or result.get('average_fill_price')
            )
            exec_type = result.get('execution_type', 'unknown')
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
                'order_id': result.get('id'),
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
                            'fill_price': info.get('fill_price'),
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

    def _cancel_orders(self, order_ids: List[str]) -> None:
        """Cancel a list of orders (best effort — do not block on failure)."""
        if not order_ids:
            return

        client = self._api_client_factory()

        async def _cancel():
            from webui.backend.routes.options.order_executor import cancel_order_with_verification
            for oid in order_ids:
                try:
                    await cancel_order_with_verification(client, oid)
                    log.info(f"[PATIENCE-LOOP] Cancelled order {oid}")
                except Exception as e:
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


# ── Singleton ─────────────────────────────────────────────────────────

_patience_loop_service: Optional[PatienceLoopService] = None


def get_patience_loop_service() -> PatienceLoopService:
    global _patience_loop_service
    if _patience_loop_service is None:
        _patience_loop_service = PatienceLoopService()
    return _patience_loop_service
