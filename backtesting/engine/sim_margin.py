"""
Margin Simulator
=================
Replicates Delta Exchange India's options margin formula for short positions.

Used to gate new sell orders when margin falls below threshold.
"""

import logging
from typing import Dict, Optional

log = logging.getLogger("backtesting.sim_margin")

# Delta Exchange India option margin parameters (approximate)
# Short naked options: Initial margin = mark_price × lots × lot_size × margin_factor
SHORT_OPTION_MARGIN_FACTOR = 0.15   # 15% of notional for short options (conservative)
LOT_SIZE_BTC = 0.001                # 1 lot = 0.001 BTC


class MarginState:
    """Tracks margin utilization for a simulated session."""

    TIER_GREEN    = "GREEN"
    TIER_YELLOW   = "YELLOW"
    TIER_ORANGE   = "ORANGE"
    TIER_RED      = "RED"
    TIER_CRITICAL = "CRITICAL"

    # Default tier thresholds (pct of net equity)
    DEFAULT_THRESHOLDS = {
        TIER_YELLOW:   50.0,
        TIER_ORANGE:   70.0,
        TIER_RED:      85.0,
        TIER_CRITICAL: 95.0,
    }

    def __init__(
        self,
        initial_balance_usd: float = 500_000.0,
        thresholds: Optional[Dict] = None,
    ):
        self.initial_balance_usd  = initial_balance_usd
        self.net_equity_usd       = initial_balance_usd
        self.position_margin_usd  = 0.0
        self.order_margin_usd     = 0.0
        self.unrealized_pnl_usd   = 0.0
        self.thresholds           = thresholds or self.DEFAULT_THRESHOLDS
        self._positions: Dict[str, Dict] = {}  # (strike, option_type) → {lots, mark_price}

    # ── Margin calculation ────────────────────────────────────────────────────

    def update_position(self, strike: float, option_type: str, lots: int, mark_price: float):
        """
        Update the margin for a short position.

        Args:
            strike:       Strike price
            option_type:  "CE" or "PE"
            lots:         Positive = short lots held
            mark_price:   Current mark price (USD)
        """
        key = f"{strike}_{option_type}"
        if lots <= 0:
            self._positions.pop(key, None)
        else:
            self._positions[key] = {
                "strike":      strike,
                "option_type": option_type,
                "lots":        lots,
                "mark_price":  mark_price,
            }
        self._recalculate()

    def update_pnl(self, unrealized_pnl: float):
        """Update unrealized P&L which affects net equity."""
        self.unrealized_pnl_usd = unrealized_pnl
        self.net_equity_usd = self.initial_balance_usd + unrealized_pnl
        self._recalculate()

    def _recalculate(self):
        """Recalculate total position margin from all open positions."""
        total_margin = 0.0
        for pos in self._positions.values():
            notional = pos["mark_price"] * pos["lots"] * LOT_SIZE_BTC
            total_margin += notional * SHORT_OPTION_MARGIN_FACTOR

        self.position_margin_usd = total_margin

    # ── Queries ────────────────────────────────────────────────────────────────

    @property
    def utilization_pct(self) -> float:
        """Margin utilization as percentage of net equity."""
        equity = max(self.net_equity_usd, 1.0)
        used = self.position_margin_usd + self.order_margin_usd
        return (used / equity) * 100.0

    @property
    def available_margin_usd(self) -> float:
        """Available margin for new positions."""
        used = self.position_margin_usd + self.order_margin_usd
        return max(0.0, self.net_equity_usd - used)

    @property
    def tier(self) -> str:
        """Current margin tier based on utilization."""
        util = self.utilization_pct
        if util >= self.thresholds[self.TIER_CRITICAL]:
            return self.TIER_CRITICAL
        elif util >= self.thresholds[self.TIER_RED]:
            return self.TIER_RED
        elif util >= self.thresholds[self.TIER_ORANGE]:
            return self.TIER_ORANGE
        elif util >= self.thresholds[self.TIER_YELLOW]:
            return self.TIER_YELLOW
        return self.TIER_GREEN

    def can_sell(self, lots: int, mark_price: float) -> bool:
        """
        Check if there is sufficient margin to sell additional lots.

        Args:
            lots:       Number of lots to sell
            mark_price: Current mark price

        Returns:
            True if margin is available, False otherwise.
        """
        additional_margin = lots * mark_price * LOT_SIZE_BTC * SHORT_OPTION_MARGIN_FACTOR
        return self.available_margin_usd >= additional_margin

    def required_margin_for_sell(self, lots: int, mark_price: float) -> float:
        """Return the margin required to sell the specified lots."""
        return lots * mark_price * LOT_SIZE_BTC * SHORT_OPTION_MARGIN_FACTOR

    def to_dict(self) -> Dict:
        """Serialize current margin state."""
        return {
            "net_equity_usd":      self.net_equity_usd,
            "position_margin_usd": self.position_margin_usd,
            "order_margin_usd":    self.order_margin_usd,
            "available_margin_usd": self.available_margin_usd,
            "utilization_pct":     round(self.utilization_pct, 2),
            "tier":                self.tier,
            "unrealized_pnl":      self.unrealized_pnl_usd,
        }
