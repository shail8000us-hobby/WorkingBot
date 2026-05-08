"""
Backend Auto-Loop Service

Runs auto-loop execution on the server side so it survives WebUI page refreshes.
The frontend sends orders + config, and this service executes rounds in a
background thread, tracking progress that the frontend polls.

Architecture:
- Singleton AutoLoopService with a daemon thread per loop
- Frontend calls start → polls status → calls stop / cancel-pending if needed
- All order placement goes through place_smart_order (sealed)
- Supports both "all strikes" and "per-expiry" loops

Round-firing model (v1.1.0):
- Hybrid trigger: round N+1 fires at MIN(fill_complete, interval_timer).
  - If interval_seconds is None, behavior degenerates to fill-gated (legacy).
  - If interval_seconds is set, round N+1 fires when round N is fully filled
    OR after interval_seconds elapsed since round N fired — whichever first.
- Orders from earlier rounds that haven't fully filled stay on the exchange
  and are tracked across all rounds. They are NOT auto-cancelled by the loop.
- Partial fills are tracked via filled_size on each order, not just a boolean.
- A per-leg cancel/error/timeout never aborts the whole loop — only that leg.
- After all rounds have fired, the loop transitions to status='tracking' and
  keeps polling until everything is filled or the user explicitly stops /
  cancels pending.

Created: February 25, 2026
Refactored: 2026-05-06 (v1.1.0) — UNSEAL granted by user; resealed after.
"""

import time
import asyncio
import threading
import logging
from typing import Dict, List, Optional
from datetime import datetime

log = logging.getLogger(__name__)

from webui.backend.sealed import sealed


# ─── Tunables (module-level so tests can override) ──────────────────────
POLL_INTERVAL = 2.0    # seconds between fill-status checks
ROUND_DELAY = 1.0      # minimum gap between rounds (only honored after fill-completion;
                       # interval_seconds takes precedence when set)
TRACK_INTERVAL = 3.0   # poll cadence after all rounds fired (tracking phase)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _filled_size_from_info(info: dict) -> int:
    """Extract filled size from a Delta get_order response, defensively.

    Delta India v2 returns either ``unfilled_size`` (preferred) or, in some
    response shapes, ``executed_quantity`` / ``filled_size``. Compute filled
    size from whichever is available so partial fills are visible.
    """
    if info is None:
        return 0
    # Most explicit
    for k in ("filled_size", "executed_quantity", "filled_quantity"):
        v = info.get(k)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
    # Derived: total - unfilled
    try:
        size = int(info.get("size") or 0)
        unfilled = info.get("unfilled_size")
        if unfilled is not None:
            return max(0, size - int(unfilled))
    except (TypeError, ValueError):
        pass
    return 0


class AutoLoopService:
    """Server-side auto-loop execution that survives page refreshes."""

    POLL_INTERVAL = POLL_INTERVAL
    ROUND_DELAY = ROUND_DELAY

    def __init__(self):
        self._loops: Dict[str, dict] = {}   # loop_id -> state
        self._lock = threading.Lock()
        self._threads: Dict[str, threading.Thread] = {}
        self._api_client_factory = None       # callable returning UnifiedAPIClient
        self._check_guardian_fn = None         # callable -> str ('GO' / 'STOP')
        log.info("AutoLoopService: initialized (v1.1.0 hybrid-trigger)")

    # ── Dependency injection ──────────────────────────────────────────

    def set_dependencies(self, api_client_factory, check_guardian_fn):
        """
        Args:
            api_client_factory: callable() -> UnifiedAPIClient
            check_guardian_fn: callable() -> str ('GO')
        """
        self._api_client_factory = api_client_factory
        self._check_guardian_fn = check_guardian_fn

    # ── Start a loop ──────────────────────────────────────────────────

    @sealed
    def start_loop(self, loop_id: str, orders: List[dict],
                   total_rounds: int, order_preference: str = "maker_first",
                   interval_seconds: Optional[float] = None) -> dict:
        """
        Start a new auto-loop.

        SEALED — v1.1.0 — May 6, 2026
        Original v1.0.0 sealed Mar 4, 2026.
        UNSEAL granted by user 2026-05-06 to add hybrid-trigger model;
        resealed at v1.1.0 after rework.

        Args:
            loop_id: Unique identifier (e.g. 'main' or expiry code like '280226')
            orders: [{symbol, size, side}, ...] — template applied to each round
            total_rounds: Number of rounds to fire
            order_preference: 'maker_first' | 'maker_only' | 'market_only' | 'ssr_*'
            interval_seconds: If set, round N+1 fires at min(fill_complete,
                              this many seconds after round N fired). If None,
                              behavior degenerates to legacy fill-gated.

        Returns:
            Loop state dict.
        """
        with self._lock:
            existing = self._loops.get(loop_id)
            if existing and existing["status"] == "running":
                # Check if the thread is actually still alive
                thread = self._threads.get(loop_id)
                if thread and thread.is_alive():
                    raise ValueError(f"Loop '{loop_id}' is already running")
                else:
                    # Thread is dead but state was never updated (crash, restart, etc.)
                    log.warning(f"AutoLoopService: loop '{loop_id}' marked running but thread is dead — cleaning up stale state")
                    existing["status"] = "error"
                    existing["error"] = "Stale loop (thread died). Restarting."
                    existing["completed_at"] = _now_iso()

        # Normalize/validate interval
        norm_interval: Optional[float] = None
        if interval_seconds is not None:
            try:
                v = float(interval_seconds)
                if v > 0:
                    norm_interval = v
            except (TypeError, ValueError):
                norm_interval = None

        state = {
            # ── Backward-compatible fields (v1.0.0 contract) ──
            "loop_id": loop_id,
            "orders": orders,
            "total_rounds": total_rounds,
            "order_preference": order_preference,
            "status": "running",              # running | stopping | tracking | completed | error | stopped
            "current_round": 0,
            "rounds_completed": 0,
            "progress": {},                   # current-round flat view, kept for legacy frontend
            "error": None,
            "started_at": _now_iso(),
            "completed_at": None,
            "stop_requested": False,

            # ── New v1.1.0 fields ──
            "interval_seconds": norm_interval,
            "next_fire_at": None,             # ISO timestamp; null when fill-gated
            "rounds": [],                     # list of {round_num, fired_at, orders: [{...}]}
            "cancel_pending_requested": False,
            "last_poll_at": None,
            "version": "1.1.0",
        }

        with self._lock:
            self._loops[loop_id] = state

        t = threading.Thread(
            target=self._run_loop,
            args=(loop_id,),
            daemon=True,
            name=f"auto-loop-{loop_id}",
        )
        self._threads[loop_id] = t
        t.start()

        log.info(
            f"AutoLoopService: started loop '{loop_id}' — "
            f"{total_rounds} rounds × {len(orders)} orders ({order_preference}) "
            f"interval={norm_interval if norm_interval is not None else 'fill-gated'}"
        )
        return state

    # ── Stop / Control ────────────────────────────────────────────────

    @sealed
    def stop_loop(self, loop_id: str) -> bool:
        """
        Request a running loop to stop firing future rounds.

        SEALED — v1.1.0 — May 6, 2026
        Original v1.0.0 sealed Mar 4, 2026.

        Stop semantics: signals the loop to exit gracefully. Pending orders
        from already-fired rounds are LEFT ON THE EXCHANGE. To also cancel
        them, call cancel_pending() instead.

        Returns:
            True if stop was requested, False if loop not found or not running.
        """
        with self._lock:
            state = self._loops.get(loop_id)
            if not state:
                return False
            if state["status"] not in ("running", "tracking"):
                return False
            state["stop_requested"] = True
            state["status"] = "stopping"
            log.info(f"AutoLoopService: stop requested for loop '{loop_id}'")
            return True

    def cancel_pending(self, loop_id: str) -> dict:
        """Cancel every still-open order across all rounds and stop the loop.

        Real-money safety: this is the explicit "cancel everything" button.

        Returns:
            {"requested": bool, "stopped": bool} — requested=False if loop unknown.
        """
        with self._lock:
            state = self._loops.get(loop_id)
            if not state:
                return {"requested": False, "stopped": False}
            state["cancel_pending_requested"] = True
            state["stop_requested"] = True
            if state["status"] in ("running", "tracking"):
                state["status"] = "stopping"
            log.info(f"AutoLoopService: cancel-pending requested for loop '{loop_id}'")
            return {"requested": True, "stopped": True}

    @sealed
    def get_status(self, loop_id: str = None) -> dict:
        """
        Get status of one loop or all loops.

        SEALED — v1.1.0 — May 6, 2026
        Original v1.0.0 sealed Mar 4, 2026.

        Returns:
            Single state dict (or {"exists": False}) when loop_id given;
            {loop_id: state, ...} mapping when loop_id is None.
        """
        with self._lock:
            if loop_id:
                state = self._loops.get(loop_id)
                if not state:
                    return {"exists": False}
                return dict(state)
            else:
                return {lid: dict(s) for lid, s in self._loops.items()}

    @sealed
    def clear_finished(self) -> int:
        """
        Remove completed/stopped/error loops.

        SEALED — v1.1.0 — May 6, 2026
        Original v1.0.0 sealed Mar 4, 2026.

        Returns:
            Count of loops removed.
        """
        with self._lock:
            to_remove = [lid for lid, s in self._loops.items()
                         if s["status"] in ("completed", "stopped", "error")]
            for lid in to_remove:
                del self._loops[lid]
                self._threads.pop(lid, None)
            return len(to_remove)

    def force_clear(self, loop_id: str = None) -> int:
        """Force-stop and remove loops regardless of status.

        If loop_id is given, only that loop is cleared; otherwise all loops.
        Running loops are signalled to stop before removal so their threads
        exit cleanly. Pending orders are NOT auto-cancelled here — call
        cancel_pending() first if you want that.
        """
        with self._lock:
            targets = ([loop_id] if loop_id and loop_id in self._loops
                       else list(self._loops.keys()))
            for lid in targets:
                state = self._loops.pop(lid, None)
                if state:
                    if state["status"] in ("running", "stopping", "tracking"):
                        state["stop_requested"] = True
                        state["status"] = "stopped"
                        log.warning(f"AutoLoopService: force-cleared running loop '{lid}'")
                    else:
                        log.info(f"AutoLoopService: force-cleared loop '{lid}' (was {state['status']})")
                self._threads.pop(lid, None)
            return len(targets)

    # ── Main loop execution (runs in thread) ──────────────────────────

    def _run_loop(self, loop_id: str):
        """Execute the auto-loop rounds in a background thread.

        Phases:
          1. Firing — for each round_num in 1..total_rounds: place orders,
             then wait until either round is fully filled, the interval timer
             expires (if set), stop is requested, or cancel-pending is requested.
          2. Tracking — after all rounds fired (or stop_firing-style exit),
             keep polling until every order across every round is in a terminal
             state, or the user stops / cancels.
        """
        state = self._loops.get(loop_id)
        if not state:
            return

        order_preference = state["order_preference"]
        total_rounds = state["total_rounds"]
        template_orders = state["orders"]
        interval = state.get("interval_seconds")

        log.info(
            f"[AUTO-LOOP:{loop_id}] Thread started — "
            f"{total_rounds} rounds, {len(template_orders)} orders, interval={interval}"
        )

        try:
            # ─── PHASE 1: Firing ─────────────────────────────────────
            for round_num in range(1, total_rounds + 1):
                if state["stop_requested"]:
                    state["error"] = state.get("error") or f"Stopped by user before round {round_num}/{total_rounds}"
                    break

                # Guardian gate (only blocks new fires, never cancels existing pending)
                if self._check_guardian_fn:
                    signal = self._check_guardian_fn()
                    if signal != "GO":
                        state["error"] = f"Guardian signal is {signal} — round {round_num}/{total_rounds} blocked"
                        log.warning(f"[AUTO-LOOP:{loop_id}] Guardian blocked round {round_num}: {signal}")
                        break

                # ── Fire this round ──
                state["current_round"] = round_num
                fired_at = time.time()
                fired_at_iso = _now_iso()
                log.info(f"[AUTO-LOOP:{loop_id}] Firing round {round_num}/{total_rounds}")

                placed_results = self._place_batch(template_orders, order_preference)
                round_record = self._build_round_record(round_num, fired_at_iso, template_orders, placed_results)
                state["rounds"].append(round_record)

                # Legacy 'progress' dict (current round, symbol-keyed) for old frontend code paths
                state["progress"] = self._legacy_progress_view(round_record)

                # Schedule next fire-by time (interval cap)
                if interval is not None and round_num < total_rounds:
                    state["next_fire_at"] = datetime.fromtimestamp(fired_at + interval).isoformat()
                else:
                    state["next_fire_at"] = None

                # ── Wait until: round fully filled OR interval expires OR stop ──
                while True:
                    if state["stop_requested"]:
                        break
                    if state.get("cancel_pending_requested"):
                        break

                    # Check interval cap BEFORE sleeping so we exit promptly
                    # without overshooting by a full poll cycle.
                    if interval is not None and (time.time() - fired_at) >= interval:
                        log.info(
                            f"[AUTO-LOOP:{loop_id}] Round {round_num} interval ({interval}s) "
                            f"expired — advancing to next round (orders stay on exchange)"
                        )
                        break

                    time.sleep(self.POLL_INTERVAL)
                    self._poll_and_update_all_rounds(state)
                    state["progress"] = self._legacy_progress_view(state["rounds"][-1])

                    # Round done if every order has filled_size >= target_size or terminal-failed
                    if self._round_complete(round_record):
                        state["rounds_completed"] = round_num
                        log.info(f"[AUTO-LOOP:{loop_id}] Round {round_num} complete ✅")
                        break

                    # Interval cap — also check after the poll (poll may have taken time)
                    if interval is not None and (time.time() - fired_at) >= interval:
                        log.info(
                            f"[AUTO-LOOP:{loop_id}] Round {round_num} interval ({interval}s) "
                            f"expired with pending — advancing to next round (orders stay on exchange)"
                        )
                        break

                # Brief floor between rounds when fill-gated and interval not set
                if interval is None and round_num < total_rounds and not state["stop_requested"]:
                    time.sleep(self.ROUND_DELAY)

            # ─── PHASE 2: Tracking after all rounds fired ─────────────
            state["next_fire_at"] = None
            if state["stop_requested"]:
                # Skip tracking; we're going straight to terminal status
                pass
            else:
                state["status"] = "tracking"
                while not state["stop_requested"] and not state.get("cancel_pending_requested"):
                    if not self._any_pending_anywhere(state):
                        break
                    time.sleep(TRACK_INTERVAL)
                    self._poll_and_update_all_rounds(state)
                    if state["rounds"]:
                        state["progress"] = self._legacy_progress_view(state["rounds"][-1])

            # ─── Cancel-pending phase, if requested ──────────────────
            if state.get("cancel_pending_requested"):
                self._cancel_all_pending(state)

            # ─── Terminal status ─────────────────────────────────────
            if state.get("cancel_pending_requested") or state["stop_requested"]:
                state["status"] = "stopped" if not state.get("error") else "error"
            else:
                state["status"] = "completed"
            state["completed_at"] = _now_iso()
            log.info(
                f"[AUTO-LOOP:{loop_id}] Terminal status: {state['status']} "
                f"(rounds_completed={state['rounds_completed']}/{state['total_rounds']})"
            )

        except Exception as e:
            log.error(f"[AUTO-LOOP:{loop_id}] Error: {e}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["completed_at"] = _now_iso()

    # ── Round building / status helpers ───────────────────────────────

    def _build_round_record(self, round_num: int, fired_at_iso: str,
                             template_orders: List[dict], placed_results: Optional[List[dict]]) -> dict:
        """Convert a list of place-order results into a structured round record."""
        record = {
            "round_num": round_num,
            "fired_at": fired_at_iso,
            "orders": [],
        }

        # If batch placement itself failed entirely, mark every leg errored
        if placed_results is None:
            for o in template_orders:
                record["orders"].append({
                    "symbol": o.get("symbol"),
                    "side": o.get("side"),
                    "target_size": int(o.get("size") or 0),
                    "filled_size": 0,
                    "order_id": None,
                    "product_id": None,
                    "state": "error",
                    "placed_price": None,
                    "fill_price": None,
                    "exec_type": None,
                    "error": "batch placement failed",
                    "last_poll_error": None,
                })
            return record

        for r in placed_results:
            symbol = r.get("symbol")
            target = int(r.get("size") or 0)
            success = r.get("success", False)
            exec_type = r.get("execution_type") or ""
            order_id = r.get("order_id")
            placed_price = r.get("placed_price") or r.get("limit_price") or r.get("mid_price")
            fill_price = r.get("fill_price")

            # Treat market/fallback/limit_filled types as filled-immediately
            filled_immediately_types = {
                "market", "market_fallback", "market_fallback_no_quotes",
                "market_fallback_error", "limit_filled", "limit_filled_late",
            }
            if not success:
                rec_state = "error"
                filled_size = 0
            elif exec_type in filled_immediately_types or not order_id:
                rec_state = "filled"
                filled_size = target
            else:
                rec_state = "pending"
                filled_size = 0

            record["orders"].append({
                "symbol": symbol,
                "side": r.get("side"),
                "target_size": target,
                "filled_size": filled_size,
                "order_id": order_id,
                "product_id": r.get("product_id"),
                "state": rec_state,
                "placed_price": placed_price,
                "fill_price": fill_price,
                "exec_type": exec_type,
                "error": r.get("error"),
                "last_poll_error": None,
            })
        return record

    @staticmethod
    def _legacy_progress_view(round_record: dict) -> dict:
        """Project a round record into the legacy ``{symbol: {filled, status, ...}}`` shape.

        This keeps the v1.0.0 frontend chip rendering working until the new
        per-round display is wired in.
        """
        out = {}
        for o in round_record.get("orders", []):
            sym = o["symbol"]
            target = o.get("target_size") or 0
            filled = o.get("filled_size") or 0
            st = o.get("state", "pending")
            chip_status = "filled" if filled >= target and target > 0 else (
                "error" if st in ("error", "cancelled") else (
                    "pending" if st in ("pending", "partially_filled", "placing") else st
                )
            )
            out[sym] = {
                "status": chip_status,
                "filled": chip_status == "filled",
                "size": target,
                "filled_size": filled,
                "orderId": o.get("order_id"),
                "fillPrice": o.get("fill_price"),
                "placedPrice": o.get("placed_price"),
                "lastPollError": o.get("last_poll_error"),
                "error": o.get("error"),
            }
        return out

    @staticmethod
    def _round_complete(round_record: dict) -> bool:
        """A round is complete when every leg is fully filled OR terminally failed."""
        for o in round_record.get("orders", []):
            target = o.get("target_size") or 0
            filled = o.get("filled_size") or 0
            st = o.get("state")
            if st in ("error", "cancelled"):
                continue  # terminal — don't block round completion
            if filled < target:
                return False
        return True

    @staticmethod
    def _any_pending_anywhere(state: dict) -> bool:
        """True if any order in any round is still working on the exchange."""
        for rd in state.get("rounds", []):
            for o in rd.get("orders", []):
                if o.get("state") in ("pending", "partially_filled", "placing"):
                    target = o.get("target_size") or 0
                    if (o.get("filled_size") or 0) < target:
                        return True
        return False

    # ── Polling: cross-round fill update ──────────────────────────────

    # Hard ceiling on a single poll pass so sequential API latency / retry
    # storms never block the interval-cap check in _run_loop.
    _POLL_TIMEOUT = 30.0  # seconds — covers up to ~10 concurrent get_order calls
    _GET_ORDER_TIMEOUT = 8.0  # per-call timeout (Delta retries up to 3×10s by default)

    def _poll_and_update_all_rounds(self, state: dict):
        """Poll Delta for every still-pending order across every round and
        update filled_size / state in-place.

        Per-leg errors / cancellations are recorded on the leg only — they
        never abort the loop. Transient poll errors are surfaced via
        ``last_poll_error`` so the UI can show a stale-data indicator.

        Calls are made concurrently (asyncio.gather) with a per-call timeout
        so a slow or hung API response never blocks the firing loop.
        """
        order_ids: List[tuple] = []  # (round_idx, order_idx, order_id)
        for ri, rd in enumerate(state.get("rounds", [])):
            for oi, o in enumerate(rd.get("orders", [])):
                if o.get("state") in ("pending", "partially_filled", "placing"):
                    if o.get("order_id"):
                        order_ids.append((ri, oi, o["order_id"]))

        if not order_ids:
            state["last_poll_at"] = _now_iso()
            return

        client = self._api_client_factory()

        async def _fetch_one(ri, oi, oid):
            try:
                info = await asyncio.wait_for(
                    client.get_order(str(oid)),
                    timeout=self._GET_ORDER_TIMEOUT,
                )
                return (ri, oi, oid, info, None)
            except asyncio.TimeoutError:
                return (ri, oi, oid, None, f"poll timeout after {self._GET_ORDER_TIMEOUT}s")
            except Exception as e:
                return (ri, oi, oid, None, str(e))

        async def _fetch_all():
            # Concurrent: all get_order calls run in parallel so N orders take
            # ~1× latency instead of N× latency.
            return await asyncio.gather(*[_fetch_one(ri, oi, oid) for ri, oi, oid in order_ids])

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    asyncio.wait_for(_fetch_all(), timeout=self._POLL_TIMEOUT)
                )
            finally:
                loop.close()
        except asyncio.TimeoutError:
            log.warning(f"[AUTO-LOOP] Poll pass timed out after {self._POLL_TIMEOUT}s — skipping update")
            return
        except Exception as e:
            log.warning(f"[AUTO-LOOP] Cross-round poll error: {e}")
            return

        rounds = state["rounds"]
        for ri, oi, oid, info, err in results:
            try:
                leg = rounds[ri]["orders"][oi]
            except (IndexError, KeyError):
                continue

            if err is not None or info is None:
                # Surface to UI but don't change order state
                leg["last_poll_error"] = err or "not_found"
                continue

            leg["last_poll_error"] = None
            order_state = (info.get("state") or "").lower()
            filled = _filled_size_from_info(info)
            target = leg.get("target_size") or 0
            fill_price = info.get("fill_price") or info.get("average_fill_price")

            if fill_price is not None:
                leg["fill_price"] = fill_price

            # Map Delta order states → our internal state
            if order_state in ("filled", "closed"):
                leg["filled_size"] = max(filled, target)  # closed = fully filled
                leg["state"] = "filled"
            elif order_state in ("cancelled", "rejected"):
                leg["filled_size"] = filled
                leg["state"] = "cancelled"
                leg["error"] = leg.get("error") or f"order {order_state}"
            elif order_state == "partially_filled":
                leg["filled_size"] = filled
                leg["state"] = "partially_filled"
            elif order_state in ("open", "pending", ""):
                leg["filled_size"] = filled
                # If we already have any fill, surface that — otherwise keep pending
                if filled > 0 and filled < target:
                    leg["state"] = "partially_filled"
                else:
                    leg["state"] = "pending"
            else:
                # Unknown state — leave as is, expose via last_poll_error so UI shows it
                leg["last_poll_error"] = f"unknown state '{order_state}'"

        state["last_poll_at"] = _now_iso()

    # ── Cancel pending orders ─────────────────────────────────────────

    def _cancel_all_pending(self, state: dict):
        """Cancel every still-open order across all rounds. Per-leg errors logged."""
        targets: List[tuple] = []  # (round_idx, order_idx, order_id, product_id)
        for ri, rd in enumerate(state.get("rounds", [])):
            for oi, o in enumerate(rd.get("orders", [])):
                if o.get("state") in ("pending", "partially_filled", "placing"):
                    oid = o.get("order_id")
                    pid = o.get("product_id")
                    if oid and pid:
                        targets.append((ri, oi, oid, pid))

        if not targets:
            log.info(f"[AUTO-LOOP:{state['loop_id']}] cancel-pending: nothing to cancel")
            return

        client = self._api_client_factory()

        async def _cancel_all():
            results = []
            for ri, oi, oid, pid in targets:
                try:
                    await client.cancel_order(str(oid), int(pid))
                    results.append((ri, oi, True, None))
                except Exception as e:
                    results.append((ri, oi, False, str(e)))
            return results

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                cancel_results = loop.run_until_complete(_cancel_all())
            finally:
                loop.close()
        except Exception as e:
            log.error(f"[AUTO-LOOP:{state['loop_id']}] cancel-pending error: {e}")
            return

        rounds = state["rounds"]
        success = 0
        for ri, oi, ok, err in cancel_results:
            try:
                leg = rounds[ri]["orders"][oi]
            except (IndexError, KeyError):
                continue
            if ok:
                leg["state"] = "cancelled"
                leg["error"] = leg.get("error") or "cancelled by user"
                success += 1
            else:
                leg["last_poll_error"] = f"cancel failed: {err}"

        log.info(
            f"[AUTO-LOOP:{state['loop_id']}] cancel-pending: "
            f"{success}/{len(targets)} cancelled"
        )

    # ── Order placement helpers (unchanged from v1.0.0) ───────────────

    def _place_batch(self, orders: List[dict], order_preference: str) -> Optional[List[dict]]:
        """Place a batch of orders using the same logic as batch_add_endpoint."""
        client = self._api_client_factory()

        async def _exec():
            tasks = []
            for i, order in enumerate(orders):
                tasks.append(self._execute_single(client, order, order_preference, i))
            return await asyncio.gather(*tasks, return_exceptions=False)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(_exec())
                return list(results)
            finally:
                loop.close()
        except Exception as e:
            log.error(f"[AUTO-LOOP] Batch placement error: {e}", exc_info=True)
            return None

    @staticmethod
    async def _execute_single(client, order_data: dict, order_preference: str, index: int) -> dict:
        """Execute a single order (mirrors batch_add_endpoint.execute_single_order)."""
        from webui.backend.routes.options.options_control import place_smart_order, with_timeout, validate_order_size

        symbol = order_data["symbol"]
        size = float(order_data["size"])
        side = order_data["side"]

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
            execution_type = result.get("execution_type", "unknown")
            placed_price = (
                result.get("limit_price")
                or result.get("mid_price")
            )
            fill_price = (
                result.get("fill_price")
                or result.get("average_fill_price")
            )
            log.info(f"✅ AutoLoop order {index + 1}: {symbol} {side} {size} — {execution_type} @ {placed_price or fill_price}")
            return {
                "success": True,
                "symbol": symbol,
                "size": size,
                "side": side,
                "execution_type": execution_type,
                "placed_price": placed_price,
                "fill_price": fill_price,
                "order_id": result.get("id"),
                "product_id": result.get("product_id"),
                "index": index,
            }
        except Exception as e:
            log.error(f"❌ AutoLoop order {index + 1} failed: {symbol} {side} {size} — {e}")
            return {
                "success": False,
                "symbol": symbol,
                "size": size,
                "side": side,
                "error": str(e),
                "index": index,
            }


# ── Singleton ─────────────────────────────────────────────────────────

_auto_loop_service: Optional[AutoLoopService] = None


def get_auto_loop_service() -> AutoLoopService:
    global _auto_loop_service
    if _auto_loop_service is None:
        _auto_loop_service = AutoLoopService()
    return _auto_loop_service
