"""
Conditional Exit Monitor

Background service that monitors BTC spot price and triggers partial position
exits when user-defined price levels are breached.

Features:
- Lower trigger: If BTC drops TO or BELOW a price → exit X% of selected positions
- Upper trigger: If BTC rises TO or ABOVE a price → exit X% of selected positions
- Gradual execution: Exits 1 lot per position per round (like Fixed mode auto-loop)
- Configurable via WebUI REST API
- Persists rules in memory (resets on server restart)
- Execution via batch_add endpoint logic (uses place_smart_order)

Architecture:
- Singleton ConditionalExitMonitor runs a daemon thread
- Checks BTC price every 3 seconds via the market price WebSocket/API
- When a trigger fires, it calculates the lots to close and executes them
- Each trigger fires ONCE per rule; user must re-arm or create new rules

Created: February 25, 2026
"""

import time
import json
import uuid
import asyncio
import threading
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

# ─── Rule Schema ──────────────────────────────────────────────────────
# {
#   "id": "uuid",
#   "name": "Emergency Exit at 60k",          # user label (optional)
#   "trigger_type": "lower" | "upper",
#   "trigger_price": 60000.0,                 # BTC spot price
#   "exit_pct": 50,                           # percentage of each position to close (1-100)
#   "exit_mode": "fixed" | "proportional",    # fixed = 1 lot/round, proportional = all at once
#   "symbols": ["C-BTC-66000-...", ...],      # specific symbols, empty = ALL positions
#   "status": "armed" | "triggered" | "executing" | "completed" | "cancelled",
#   "created_at": "ISO datetime",
#   "triggered_at": null | "ISO datetime",
#   "completed_at": null | "ISO datetime",
#   "execution_log": [],                      # per-order results
#   "lots_closed": 0,
#   "lots_target": 0,
#   "rounds_completed": 0,
#   "order_preference": "maker_first",
# }


class ConditionalExitMonitor:
    """Background monitor for BTC-price-triggered partial exits."""

    CHECK_INTERVAL = 3  # seconds between BTC price checks
    ROUND_DELAY = 2     # seconds between execution rounds (for gradual exit)

    def __init__(self):
        self.rules: Dict[str, dict] = {}  # rule_id -> rule
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_btc_price: Optional[float] = None
        self._last_check: Optional[datetime] = None
        self._api_client = None
        self._get_btc_price_fn = None  # callable that returns float BTC price

    # ── Dependency injection ──────────────────────────────────────────

    def set_dependencies(self, api_client, get_btc_price_fn):
        """
        Args:
            api_client: UnifiedAPIClient (for executing orders)
            get_btc_price_fn: callable() -> float  (returns current BTC spot price)
        """
        self._api_client = api_client
        self._get_btc_price_fn = get_btc_price_fn
        log.info("ConditionalExitMonitor: dependencies set")

    # ── Start / Stop ──────────────────────────────────────────────────

    def start(self) -> bool:
        if self._running:
            return False
        if not self._get_btc_price_fn:
            log.error("ConditionalExitMonitor: cannot start without price function")
            return False
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="cond-exit-monitor")
        self._thread.start()
        log.info("ConditionalExitMonitor: started")
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        log.info("ConditionalExitMonitor: stopped")

    @property
    def running(self):
        return self._running

    # ── CRUD for rules ────────────────────────────────────────────────

    def add_rule(self, trigger_type: str, trigger_price: float,
                 exit_pct: int = 100, exit_mode: str = "fixed",
                 symbols: List[str] = None, name: str = "",
                 order_preference: str = "maker_first") -> dict:
        """Create a new conditional exit rule (returns the rule dict)."""
        if trigger_type not in ("lower", "upper"):
            raise ValueError("trigger_type must be 'lower' or 'upper'")
        if not (1 <= exit_pct <= 100):
            raise ValueError("exit_pct must be 1-100")
        if trigger_price <= 0:
            raise ValueError("trigger_price must be positive")

        rule = {
            "id": str(uuid.uuid4())[:8],
            "name": name or f"{'Lower' if trigger_type == 'lower' else 'Upper'} @ ${trigger_price:,.0f}",
            "trigger_type": trigger_type,
            "trigger_price": float(trigger_price),
            "exit_pct": int(exit_pct),
            "exit_mode": exit_mode,
            "symbols": list(symbols or []),
            "status": "armed",
            "created_at": datetime.now().isoformat(),
            "triggered_at": None,
            "completed_at": None,
            "execution_log": [],
            "lots_closed": 0,
            "lots_target": 0,
            "rounds_completed": 0,
            "order_preference": order_preference,
        }
        with self._lock:
            self.rules[rule["id"]] = rule
        log.info(f"ConditionalExitMonitor: rule added — {rule['name']} (id={rule['id']})")
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        with self._lock:
            rule = self.rules.get(rule_id)
            if not rule:
                return False
            if rule["status"] == "executing":
                rule["status"] = "cancelled"  # will stop on next round
            else:
                del self.rules[rule_id]
            return True

    def cancel_rule(self, rule_id: str) -> bool:
        """Cancel a rule (stops execution if running)."""
        with self._lock:
            rule = self.rules.get(rule_id)
            if not rule:
                return False
            rule["status"] = "cancelled"
            return True

    def get_rule(self, rule_id: str) -> Optional[dict]:
        return self.rules.get(rule_id)

    def get_all_rules(self) -> List[dict]:
        return list(self.rules.values())

    def get_status(self) -> dict:
        armed = sum(1 for r in self.rules.values() if r["status"] == "armed")
        executing = sum(1 for r in self.rules.values() if r["status"] == "executing")
        return {
            "running": self._running,
            "last_btc_price": self._last_btc_price,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "total_rules": len(self.rules),
            "armed_rules": armed,
            "executing_rules": executing,
        }

    def clear_completed(self):
        """Remove all completed/cancelled rules."""
        with self._lock:
            to_remove = [rid for rid, r in self.rules.items()
                         if r["status"] in ("completed", "cancelled", "triggered")]
            for rid in to_remove:
                del self.rules[rid]
            return len(to_remove)

    # ── Main monitor loop ─────────────────────────────────────────────

    def _monitor_loop(self):
        log.info("ConditionalExitMonitor: monitor loop started")
        while self._running:
            try:
                btc_price = self._fetch_btc_price()
                if btc_price and btc_price > 0:
                    self._last_btc_price = btc_price
                    self._last_check = datetime.now()
                    self._evaluate_rules(btc_price)
            except Exception as e:
                log.error(f"ConditionalExitMonitor: error in loop — {e}", exc_info=True)
            time.sleep(self.CHECK_INTERVAL)
        log.info("ConditionalExitMonitor: monitor loop ended")

    def _fetch_btc_price(self) -> Optional[float]:
        """Get current BTC spot price from injected function."""
        try:
            price = self._get_btc_price_fn()
            return float(price) if price else None
        except Exception as e:
            log.warning(f"ConditionalExitMonitor: price fetch error — {e}")
            return None

    def _evaluate_rules(self, btc_price: float):
        """Check all armed rules against current BTC price."""
        with self._lock:
            rules_to_trigger = []
            for rule in self.rules.values():
                if rule["status"] != "armed":
                    continue
                triggered = False
                if rule["trigger_type"] == "lower" and btc_price <= rule["trigger_price"]:
                    triggered = True
                elif rule["trigger_type"] == "upper" and btc_price >= rule["trigger_price"]:
                    triggered = True
                if triggered:
                    rule["status"] = "triggered"
                    rule["triggered_at"] = datetime.now().isoformat()
                    rules_to_trigger.append(rule)
                    log.warning(
                        f"🚨 CONDITIONAL EXIT TRIGGERED: {rule['name']} "
                        f"(BTC=${btc_price:,.2f} {'<=' if rule['trigger_type'] == 'lower' else '>='} "
                        f"${rule['trigger_price']:,.0f})"
                    )

        # Execute triggered rules OUTSIDE the lock
        for rule in rules_to_trigger:
            self._execute_rule(rule, btc_price)

    # ── Execution ─────────────────────────────────────────────────────

    def _execute_rule(self, rule: dict, trigger_price: float):
        """Execute a triggered rule — close exit_pct% of targeted positions."""
        rule["status"] = "executing"
        try:
            # 1. Fetch current positions
            positions = self._get_positions()
            if not positions:
                rule["status"] = "completed"
                rule["completed_at"] = datetime.now().isoformat()
                rule["execution_log"].append({"error": "No positions found"})
                log.warning(f"ConditionalExitMonitor: {rule['name']} — no positions found")
                return

            # 2. Filter to selected symbols (or all)
            if rule["symbols"]:
                target_positions = [p for p in positions if p.get("product_symbol") in rule["symbols"]]
            else:
                target_positions = positions

            if not target_positions:
                rule["status"] = "completed"
                rule["completed_at"] = datetime.now().isoformat()
                rule["execution_log"].append({"error": "No matching positions"})
                return

            # 3. Calculate lots to close for each position
            orders = []
            for pos in target_positions:
                symbol = pos.get("product_symbol")
                current_size = pos.get("size", 0)
                abs_size = abs(current_size)
                if abs_size == 0:
                    continue

                # Calculate close quantity based on exit_pct
                lots_to_close = max(1, round(abs_size * rule["exit_pct"] / 100))
                lots_to_close = min(lots_to_close, abs_size)  # cap at full position

                # Determine side (opposite to position for closing)
                close_side = "sell" if current_size > 0 else "buy"

                orders.append({
                    "symbol": symbol,
                    "size": lots_to_close,
                    "side": close_side,
                    "original_size": current_size,
                })

            if not orders:
                rule["status"] = "completed"
                rule["completed_at"] = datetime.now().isoformat()
                return

            rule["lots_target"] = sum(o["size"] for o in orders)

            # 4. Execute based on mode
            if rule["exit_mode"] == "fixed":
                # Gradual: 1 lot per position per round
                self._execute_gradual(rule, orders, trigger_price)
            else:
                # Proportional: all at once
                self._execute_batch(rule, orders, trigger_price)

        except Exception as e:
            log.error(f"ConditionalExitMonitor: execution error — {e}", exc_info=True)
            rule["status"] = "completed"
            rule["completed_at"] = datetime.now().isoformat()
            rule["execution_log"].append({"error": str(e)})

    def _execute_gradual(self, rule: dict, orders: List[dict], trigger_price: float):
        """Execute gradually: 1 lot per position per round until target reached."""
        remaining = {o["symbol"]: o["size"] for o in orders}
        sides = {o["symbol"]: o["side"] for o in orders}
        total_closed = 0
        round_num = 0

        log.info(f"ConditionalExitMonitor: gradual exit — {len(orders)} positions, "
                 f"{sum(remaining.values())} total lots")

        while any(v > 0 for v in remaining.values()) and rule["status"] == "executing":
            round_num += 1
            round_orders = []
            for sym, lots_left in remaining.items():
                if lots_left > 0:
                    round_orders.append({
                        "symbol": sym,
                        "size": 1,  # 1 lot at a time
                        "side": sides[sym],
                    })

            if not round_orders:
                break

            log.info(f"ConditionalExitMonitor: round {round_num} — "
                     f"{len(round_orders)} orders of 1 lot each")

            results = self._execute_orders(round_orders, rule["order_preference"])
            for res in results:
                if res.get("success"):
                    sym = res["symbol"]
                    remaining[sym] = max(0, remaining[sym] - 1)
                    total_closed += 1
                rule["execution_log"].append(res)

            rule["lots_closed"] = total_closed
            rule["rounds_completed"] = round_num

            # Pause between rounds
            if any(v > 0 for v in remaining.values()) and rule["status"] == "executing":
                time.sleep(self.ROUND_DELAY)

        rule["lots_closed"] = total_closed
        rule["status"] = "completed" if rule["status"] != "cancelled" else "cancelled"
        rule["completed_at"] = datetime.now().isoformat()
        log.info(f"ConditionalExitMonitor: {rule['name']} — completed: "
                 f"{total_closed}/{rule['lots_target']} lots in {round_num} rounds")

    def _execute_batch(self, rule: dict, orders: List[dict], trigger_price: float):
        """Execute all lots at once (proportional mode)."""
        log.info(f"ConditionalExitMonitor: batch exit — {len(orders)} positions, "
                 f"{sum(o['size'] for o in orders)} total lots")

        results = self._execute_orders(orders, rule["order_preference"])
        total_closed = 0
        for res in results:
            if res.get("success"):
                total_closed += int(res.get("size", 0))
            rule["execution_log"].append(res)

        rule["lots_closed"] = total_closed
        rule["rounds_completed"] = 1
        rule["status"] = "completed"
        rule["completed_at"] = datetime.now().isoformat()
        log.info(f"ConditionalExitMonitor: {rule['name']} — completed: "
                 f"{total_closed}/{rule['lots_target']} lots in 1 batch")

    # ── Low-level order helpers ───────────────────────────────────────

    def _get_positions(self) -> List[dict]:
        """Fetch current options positions."""
        try:
            loop = self._get_or_create_loop()
            async def _fetch():
                resp = await self._api_client.get_all_positions_with_options()
                return resp.get("options", []) if resp else []
            return loop.run_until_complete(_fetch())
        except Exception as e:
            log.error(f"ConditionalExitMonitor: position fetch error — {e}")
            return []

    def _execute_orders(self, orders: List[dict], order_preference: str) -> List[dict]:
        """Execute a list of orders via place_smart_order."""
        from webui.backend.routes.options.options_control import place_smart_order, with_timeout

        loop = self._get_or_create_loop()

        async def _run():
            tasks = []
            for i, order in enumerate(orders):
                coro = with_timeout(
                    place_smart_order(
                        client=self._api_client,
                        symbol=order["symbol"],
                        size=float(order["size"]),
                        side=order["side"],
                        order_preference=order_preference,
                        limit_price=None,
                    ),
                    timeout_seconds=30,
                )
                tasks.append(self._wrap_order(coro, order, i))
            return await asyncio.gather(*tasks, return_exceptions=False)

        try:
            return loop.run_until_complete(_run())
        except Exception as e:
            log.error(f"ConditionalExitMonitor: batch execution error — {e}")
            return [{"success": False, "error": str(e)}]

    async def _wrap_order(self, coro, order: dict, idx: int) -> dict:
        """Wrap a single order execution with error handling."""
        try:
            result = await coro
            fill_price = (result.get("fill_price") or result.get("limit_price")
                          or result.get("average_fill_price"))
            log.info(f"✅ CondExit order {idx+1}: {order['symbol']} {order['side']} "
                     f"{order['size']} — {result.get('execution_type')} @ {fill_price}")
            return {
                "success": True,
                "symbol": order["symbol"],
                "size": order["size"],
                "side": order["side"],
                "fill_price": fill_price,
                "order_id": result.get("id"),
                "execution_type": result.get("execution_type"),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            log.error(f"❌ CondExit order {idx+1}: {order['symbol']} — {e}")
            return {
                "success": False,
                "symbol": order["symbol"],
                "size": order["size"],
                "side": order["side"],
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _get_or_create_loop(self):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop


# ── Singleton ─────────────────────────────────────────────────────────

_monitor: Optional[ConditionalExitMonitor] = None


def get_conditional_exit_monitor() -> ConditionalExitMonitor:
    """Get the singleton ConditionalExitMonitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = ConditionalExitMonitor()
    return _monitor
