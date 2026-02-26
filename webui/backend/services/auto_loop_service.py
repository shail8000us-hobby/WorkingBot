"""
Backend Auto-Loop Service

Runs auto-loop execution on the server side so it survives WebUI page refreshes.
The frontend sends orders + config, and this service executes rounds in a
background thread, tracking progress that the frontend polls.

Architecture:
- Singleton AutoLoopService with a daemon thread per loop
- Frontend calls start → polls status → calls stop if needed
- All order placement goes through the existing batch_add logic
- Supports both "all strikes" and "per-expiry" loops

Created: February 25, 2026
"""

import time
import asyncio
import threading
import logging
from typing import Dict, List, Optional
from datetime import datetime

log = logging.getLogger(__name__)


class AutoLoopService:
    """Server-side auto-loop execution that survives page refreshes."""

    POLL_INTERVAL = 2.0   # seconds between fill-checks
    ROUND_DELAY = 1.0     # seconds between rounds

    def __init__(self):
        self._loops: Dict[str, dict] = {}   # loop_id -> state
        self._lock = threading.Lock()
        self._threads: Dict[str, threading.Thread] = {}
        self._api_client_factory = None       # callable returning UnifiedAPIClient
        self._check_guardian_fn = None         # callable -> str ('GO' / 'STOP')
        log.info("AutoLoopService: initialized")

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

    def start_loop(self, loop_id: str, orders: List[dict],
                   total_rounds: int, order_preference: str = "maker_first") -> dict:
        """
        Start a new auto-loop.

        Args:
            loop_id: Unique identifier (e.g. 'main' or expiry code like '280226')
            orders: [{symbol, size, side}, ...]
            total_rounds: Number of rounds to execute
            order_preference: 'maker_first' or 'market_only'

        Returns:
            Loop state dict
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
                    # Clean up the stale state and allow restart
                    log.warning(f"AutoLoopService: loop '{loop_id}' marked running but thread is dead — cleaning up stale state")
                    existing["status"] = "error"
                    existing["error"] = "Stale loop (thread died). Restarting."
                    existing["completed_at"] = datetime.now().isoformat()

        state = {
            "loop_id": loop_id,
            "orders": orders,
            "total_rounds": total_rounds,
            "order_preference": order_preference,
            "status": "running",              # running | stopping | completed | error | stopped
            "current_round": 0,
            "rounds_completed": 0,
            "progress": {},                   # symbol -> {status, filled, size, fillPrice, orderId}
            "error": None,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "stop_requested": False,
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

        log.info(f"AutoLoopService: started loop '{loop_id}' — {total_rounds} rounds × {len(orders)} orders ({order_preference})")
        return state

    # ── Stop / Control ────────────────────────────────────────────────

    def stop_loop(self, loop_id: str) -> bool:
        with self._lock:
            state = self._loops.get(loop_id)
            if not state:
                return False
            if state["status"] != "running":
                return False
            state["stop_requested"] = True
            state["status"] = "stopping"
            log.info(f"AutoLoopService: stop requested for loop '{loop_id}'")
            return True

    def get_status(self, loop_id: str = None) -> dict:
        """Get status of one loop or all loops."""
        with self._lock:
            if loop_id:
                state = self._loops.get(loop_id)
                if not state:
                    return {"exists": False}
                return dict(state)
            else:
                return {lid: dict(s) for lid, s in self._loops.items()}

    def clear_finished(self) -> int:
        """Remove completed/stopped/error loops."""
        with self._lock:
            to_remove = [lid for lid, s in self._loops.items()
                         if s["status"] in ("completed", "stopped", "error")]
            for lid in to_remove:
                del self._loops[lid]
                self._threads.pop(lid, None)
            return len(to_remove)

    # ── Main loop execution (runs in thread) ──────────────────────────

    def _run_loop(self, loop_id: str):
        """Execute the auto-loop rounds in a background thread."""
        state = self._loops.get(loop_id)
        if not state:
            return

        orders = state["orders"]
        total_rounds = state["total_rounds"]
        order_preference = state["order_preference"]

        log.info(f"[AUTO-LOOP:{loop_id}] Thread started — {total_rounds} rounds, {len(orders)} orders")

        try:
            for round_num in range(1, total_rounds + 1):
                # ── Check stop ──
                if state["stop_requested"]:
                    state["status"] = "stopped"
                    state["error"] = f"Stopped by user after round {round_num - 1}/{total_rounds}"
                    state["completed_at"] = datetime.now().isoformat()
                    log.info(f"[AUTO-LOOP:{loop_id}] Stopped by user at round {round_num - 1}")
                    return

                # ── Check guardian ──
                if self._check_guardian_fn:
                    signal = self._check_guardian_fn()
                    if signal != "GO":
                        state["status"] = "error"
                        state["error"] = f"Guardian signal is {signal} — trading disabled"
                        state["completed_at"] = datetime.now().isoformat()
                        log.warning(f"[AUTO-LOOP:{loop_id}] Guardian blocked: {signal}")
                        return

                state["current_round"] = round_num
                log.info(f"[AUTO-LOOP:{loop_id}] Round {round_num}/{total_rounds}")

                # ── Reset progress for this round ──
                round_progress = {}
                for o in orders:
                    round_progress[o["symbol"]] = {
                        "status": "placing",
                        "filled": False,
                        "size": o["size"],
                        "orderId": None,
                        "fillPrice": None,
                    }
                state["progress"] = round_progress

                # ── Step 1: Place all orders ──
                placed_results = self._place_batch(orders, order_preference)

                if placed_results is None:
                    state["status"] = "error"
                    state["error"] = f"Failed to place orders in round {round_num}"
                    state["completed_at"] = datetime.now().isoformat()
                    return

                # Separate filled vs pending
                filled_immediately = []
                pending_orders = []
                failed_orders = []

                for result in placed_results:
                    symbol = result.get("symbol")
                    if not result.get("success"):
                        failed_orders.append(result)
                        round_progress[symbol] = {
                            "status": "error",
                            "filled": False,
                            "size": result.get("size", 0),
                            "orderId": None,
                            "fillPrice": None,
                            "error": result.get("error", "Failed"),
                        }
                        continue

                    exec_type = result.get("execution_type", "")
                    filled_types = [
                        "market", "market_fallback", "market_fallback_no_quotes",
                        "market_fallback_error", "limit_filled", "limit_filled_late",
                    ]
                    if exec_type in filled_types or not result.get("order_id"):
                        filled_immediately.append(result)
                        round_progress[symbol] = {
                            "status": "filled",
                            "filled": True,
                            "size": result.get("size", 0),
                            "orderId": result.get("order_id"),
                            "fillPrice": result.get("fill_price"),
                        }
                    else:
                        pending_orders.append(result)
                        round_progress[symbol] = {
                            "status": "pending",
                            "filled": False,
                            "size": result.get("size", 0),
                            "orderId": result.get("order_id"),
                            "fillPrice": None,
                        }

                state["progress"] = dict(round_progress)

                if failed_orders:
                    symbols_str = ", ".join(f.get("symbol", "?") for f in failed_orders)
                    state["status"] = "error"
                    state["error"] = f"Round {round_num}: {len(failed_orders)} order(s) failed ({symbols_str})"
                    state["completed_at"] = datetime.now().isoformat()
                    log.error(f"[AUTO-LOOP:{loop_id}] Order failures: {symbols_str}")
                    return

                log.info(
                    f"[AUTO-LOOP:{loop_id}] Round {round_num}: "
                    f"{len(filled_immediately)} filled, {len(pending_orders)} pending"
                )

                # ── Step 2: Poll for pending orders ──
                if pending_orders:
                    order_ids = [r["order_id"] for r in pending_orders if r.get("order_id")]
                    poll_count = 0

                    while not state["stop_requested"]:
                        poll_count += 1
                        time.sleep(self.POLL_INTERVAL)

                        # Fetch order statuses
                        statuses = self._check_order_statuses(order_ids)
                        if statuses is None:
                            log.warning(f"[AUTO-LOOP:{loop_id}] Status check failed (poll {poll_count}), retrying...")
                            continue

                        for os_item in statuses:
                            matching = next(
                                (p for p in pending_orders if p.get("order_id") == os_item.get("order_id")),
                                None,
                            )
                            if not matching:
                                continue

                            sym = matching["symbol"]
                            order_state = os_item.get("state", "")
                            is_filled = order_state in ("filled", "closed")
                            is_cancelled = order_state in ("cancelled", "rejected")

                            if is_cancelled:
                                state["status"] = "error"
                                state["error"] = f"Round {round_num}: Order {sym} was {order_state}"
                                state["completed_at"] = datetime.now().isoformat()
                                log.error(f"[AUTO-LOOP:{loop_id}] Order {sym} was {order_state}")
                                return

                            if is_filled:
                                round_progress[sym] = {
                                    "status": "filled",
                                    "filled": True,
                                    "size": os_item.get("size", matching.get("size")),
                                    "orderId": os_item.get("order_id"),
                                    "fillPrice": os_item.get("fill_price"),
                                }

                        state["progress"] = dict(round_progress)

                        filled_count = sum(1 for p in round_progress.values() if p.get("filled"))
                        total_count = len(orders)
                        log.debug(
                            f"[AUTO-LOOP:{loop_id}] Round {round_num} poll {poll_count}: "
                            f"{filled_count}/{total_count} filled"
                        )

                        if filled_count >= total_count:
                            break

                # ── Check stop during polling ──
                if state["stop_requested"]:
                    state["status"] = "stopped"
                    state["error"] = f"Stopped by user during round {round_num}/{total_rounds}"
                    state["completed_at"] = datetime.now().isoformat()
                    log.info(f"[AUTO-LOOP:{loop_id}] Stopped during polling at round {round_num}")
                    return

                # ── Round complete ──
                state["rounds_completed"] = round_num
                log.info(f"[AUTO-LOOP:{loop_id}] Round {round_num}/{total_rounds} complete ✅")

                # Mark all filled for the progress display
                for sym in round_progress:
                    round_progress[sym]["status"] = "filled"
                    round_progress[sym]["filled"] = True
                state["progress"] = dict(round_progress)

                # Delay between rounds
                if round_num < total_rounds:
                    time.sleep(self.ROUND_DELAY)

            # ── All rounds complete ──
            state["status"] = "completed"
            state["completed_at"] = datetime.now().isoformat()
            log.info(f"[AUTO-LOOP:{loop_id}] All {total_rounds} rounds completed successfully ✅")

        except Exception as e:
            log.error(f"[AUTO-LOOP:{loop_id}] Error: {e}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["completed_at"] = datetime.now().isoformat()

    # ── Order placement helpers ───────────────────────────────────────

    def _place_batch(self, orders: List[dict], order_preference: str) -> Optional[List[dict]]:
        """Place a batch of orders using the same logic as batch_add_endpoint."""
        from webui.backend.routes.options.options_control import place_smart_order, with_timeout, validate_order_size

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
            fill_price = (
                result.get("fill_price")
                or result.get("limit_price")
                or result.get("average_fill_price")
            )
            log.info(f"✅ AutoLoop order {index + 1}: {symbol} {side} {size} — {execution_type} @ {fill_price}")
            return {
                "success": True,
                "symbol": symbol,
                "size": size,
                "side": side,
                "execution_type": execution_type,
                "fill_price": fill_price,
                "order_id": result.get("id"),
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

    def _check_order_statuses(self, order_ids: List[str]) -> Optional[List[dict]]:
        """Check statuses of pending orders."""
        client = self._api_client_factory()

        async def _fetch():
            results = []
            for oid in order_ids:
                try:
                    info = await client.get_order(str(oid))
                    if info:
                        results.append({
                            "order_id": oid,
                            "symbol": info.get("product_symbol"),
                            "size": info.get("size"),
                            "side": info.get("side"),
                            "state": info.get("state"),
                            "fill_price": info.get("fill_price"),
                        })
                    else:
                        results.append({"order_id": oid, "state": "not_found"})
                except Exception as e:
                    log.warning(f"Error fetching order {oid}: {e}")
                    results.append({"order_id": oid, "state": "error", "error": str(e)})
            return results

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_fetch())
            finally:
                loop.close()
        except Exception as e:
            log.error(f"[AUTO-LOOP] Status check error: {e}")
            return None


# ── Singleton ─────────────────────────────────────────────────────────

_auto_loop_service: Optional[AutoLoopService] = None


def get_auto_loop_service() -> AutoLoopService:
    global _auto_loop_service
    if _auto_loop_service is None:
        _auto_loop_service = AutoLoopService()
    return _auto_loop_service
