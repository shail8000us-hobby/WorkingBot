"""
Protection builder (Single Responsibility):
Given a filled ENTRY and current grid config/state, compute the correct
reduce-only EXIT order to rest on the exchange immediately.

- For BUY entries  -> place a SELL reduce-only at the next HIGHER grid level.
- For SELL entries -> place a BUY  reduce-only at the next LOWER  grid level.

No exchange calls here — pure logic. The caller (manager) passes the
result to the execution layer (executor.create_order).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from bot.config.aliases import upgrade_mapping
from bot.state.store import StateStore


# ---------- Grid config helpers ----------

@dataclass
class GridConfig:
    lower: float
    upper: float
    step: float
    reference: Optional[float] = None
    lot: Optional[float] = None

    @staticmethod
    def from_state_file(path: str = "state.json") -> "GridConfig":
        store = StateStore(Path(path), default={})
        d = store.locked_read()
        upgrade_mapping(d, record=False)
        return GridConfig(
            lower=float(d["GRIDBOT_LOWER"]),
            upper=float(d["GRIDBOT_UPPER"]),
            step=float(d["GRIDBOT_STEP"]),
            reference=float(d.get("GRIDBOT_REF")) if d.get("GRIDBOT_REF") is not None else None,
            lot=float(d.get("GRIDBOT_LOT")) if d.get("GRIDBOT_LOT") is not None else None,
        )

    def levels(self, max_levels: int = 10_000) -> List[float]:
        if self.step <= 0 or self.upper < self.lower:
            return []
        n = int(round((self.upper - self.lower) / self.step)) + 1
        n = min(max_levels, max(1, n))
        return [self.lower + i * self.step for i in range(n)]


# ---------- Protection logic ----------

def _next_higher(levels: List[float], px: float) -> Optional[float]:
    for lv in levels:
        if lv > px:
            return lv
    return None

def _next_lower(levels: List[float], px: float) -> Optional[float]:
    for lv in reversed(levels):
        if lv < px:
            return lv
    return None

def compute_reduce_only_exit(
    *,
    entry_side: str,
    fill_price: float,
    fill_size: float,
    grid: GridConfig,
) -> Optional[Tuple[str, float, float]]:
    """
    Returns (exit_side, exit_price, exit_size) or None if no valid level.

    entry_side: "buy" or "sell"
    fill_price: average fill price of the entry
    fill_size : contracts filled (positive number)

    For BUY:  exit_side='sell', exit_price=next higher grid level
    For SELL: exit_side='buy',  exit_price=next lower  grid level
    """
    levels = grid.levels()
    if not levels:
        return None

    side = entry_side.lower().strip()
    if side not in ("buy", "sell"):
        raise ValueError("entry_side must be 'buy' or 'sell'")

    if side == "buy":
        target = _next_higher(levels, fill_price)
        if target is None:
            return None
        return ("sell", float(target), float(fill_size))

    # side == "sell"
    target = _next_lower(levels, fill_price)
    if target is None:
        return None
    return ("buy", float(target), float(fill_size))


# ---------- Public builder API ----------

def build_reduce_only_limit_order_payload(
    *,
    entry_side: str,
    avg_fill_price: float,
    filled_size: float,
    grid: GridConfig | None = None,
) -> Optional[dict]:
    """
    Produce a payload suitable for executor.create_order(..., order_type='limit', reduce_only=True)

    Returns dict like:
        {
          "side": "sell",
          "order_type": "limit",
          "price": 113100.0,
          "amount": 1.0,
          "reduce_only": True
        }
    or None if no valid grid level is available (e.g., fill happened at the boundary).
    """
    if grid is None:
        grid = GridConfig.from_state_file()

    res = compute_reduce_only_exit(
        entry_side=entry_side,
        fill_price=avg_fill_price,
        fill_size=filled_size,
        grid=grid,
    )
    if res is None:
        return None

    exit_side, exit_price, exit_amount = res
    return {
        "side": exit_side,
        "order_type": "limit",
        "price": exit_price,
        "amount": exit_amount,
        "reduce_only": True,
    }
