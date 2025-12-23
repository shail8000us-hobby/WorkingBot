"""
Order Manager — orchestrates the lifecycle of grid orders:

Idle -> Entry submitted -> Filled -> Protection placed -> Exit filled
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Dict, Any

from bot.orders.executor import DeltaExecutor
from bot.orders.protection import build_reduce_only_limit_order_payload, GridConfig

log = logging.getLogger("manager")


class OrderManager:
    def __init__(self) -> None:
        self.exec = DeltaExecutor()
        self.grid = GridConfig.from_state_file()

    def place_entry(self, side: str, amount: float, order_type: str = "market") -> Optional[Dict[str, Any]]:
        """Place an entry order (buy/sell) and manage its lifecycle."""
        try:
            entry = self.exec.create_order(side=side, amount=amount, order_type=order_type)
            log.info("ENTRY_PLACED: %s %s %s", side.upper(), amount, order_type)
        except Exception as e:
            log.error("ENTRY_FAILED: %s", e)
            return None

        oid = entry.get("id")
        if not oid:
            return None

        # Poll until filled (simple blocking loop for now)
        filled_size = 0.0
        avg_fill_price = None
        for _ in range(30):  # poll up to ~30s
            try:
                o = self.exec.fetch_order(oid)
                status = o.get("status") or o.get("state")
                if status in ("closed", "filled"):
                    filled_size = float(o.get("filled") or o.get("size") or 0.0)
                    avg_fill_price = float(o.get("average") or o.get("average_fill_price") or o.get("price") or 0.0)
                    log.info("ENTRY_FILLED: %s %s @ %s", filled_size, side.upper(), avg_fill_price)
                    break
            except Exception as e:
                log.warning("FETCH_ORDER_FAILED: %s", e)
            time.sleep(1)

        if filled_size <= 0 or avg_fill_price is None:
            log.error("ENTRY_NOT_FILLED in polling window")
            return None

        # Build and place reduce-only exit
        payload = build_reduce_only_limit_order_payload(
            entry_side=side,
            avg_fill_price=avg_fill_price,
            filled_size=filled_size,
            grid=self.grid,
        )
        if not payload:
            log.warning("NO_PROTECTION: could not build exit for %s", side)
            return entry

        try:
            exit_order = self.exec.create_order(
                side=payload["side"],
                amount=payload["amount"],
                order_type=payload["order_type"],
                price=payload["price"],
                reduce_only=True,
            )
            log.info(
                "EXIT_PLACED: %s %s @ %s (reduce_only)",
                exit_order.get("side"), exit_order.get("amount"), exit_order.get("price")
            )
        except Exception as e:
            log.error("EXIT_FAILED: %s", e)

        return entry
