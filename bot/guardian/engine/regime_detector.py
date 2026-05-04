"""
RegimeDetector — Determines active trading regime for RANGE (dual-zone) mode.

In RANGE mode the anchor price divides the grid into two zones:
  LONG zone  : [lower, anchor)   — bot buys dips, sells bounces
  SHORT zone : (anchor, upper]   — bot sells rallies, buys drops
  OOB        : outside [lower, upper] — both instances stop

Hysteresis prevents rapid flipping at the anchor:
  LONG → SHORT : only when LTP > anchor + hysteresis
  SHORT → LONG : only when LTP < anchor - hysteresis
  OOB  → zone  : re-entry uses anchor as divider (no extra hysteresis)

This class is stateful. Both LONG and SHORT Guardian instances instantiate it
independently, but because they observe the same LTP stream and start from the
same initial-regime rule they will always compute the same current regime.
"""

import logging

log = logging.getLogger("guardian.regime_detector")

REGIME_LONG = "LONG"
REGIME_SHORT = "SHORT"
REGIME_OOB = "OOB"


class RegimeDetector:
    def __init__(self, anchor: float, lower: float, upper: float, hysteresis: float):
        if lower >= anchor or anchor >= upper:
            raise ValueError(
                f"RANGE config invalid: lower({lower}) < anchor({anchor}) < upper({upper}) required"
            )
        self.anchor = anchor
        self.lower = lower
        self.upper = upper
        self.hysteresis = hysteresis
        self._current_regime: str | None = None

    @property
    def current_regime(self) -> str:
        return self._current_regime or REGIME_OOB

    def update(self, ltp: float) -> str:
        new_regime = self._compute(ltp)
        if new_regime != self._current_regime:
            log.info(
                f"RANGE regime: {self._current_regime} → {new_regime} "
                f"(LTP={ltp:.0f}, anchor={self.anchor:.0f}, H={self.hysteresis:.0f})"
            )
            self._current_regime = new_regime
        return self._current_regime

    def _compute(self, ltp: float) -> str:
        # Hard OOB boundaries (no hysteresis — price is outside the total range)
        if ltp < self.lower or ltp > self.upper:
            return REGIME_OOB

        # First observation — determine regime purely from price vs anchor
        if self._current_regime is None:
            return REGIME_SHORT if ltp > self.anchor else REGIME_LONG

        # Transitions with hysteresis
        if self._current_regime == REGIME_LONG:
            if ltp > self.anchor + self.hysteresis:
                return REGIME_SHORT

        elif self._current_regime == REGIME_SHORT:
            if ltp < self.anchor - self.hysteresis:
                return REGIME_LONG

        elif self._current_regime == REGIME_OOB:
            # Re-entering from OOB — no extra hysteresis, use anchor as divider
            return REGIME_SHORT if ltp > self.anchor else REGIME_LONG

        return self._current_regime  # No change
