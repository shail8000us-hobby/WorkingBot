import logging
from datetime import datetime

logger = logging.getLogger("shailendra_signals")

class MarketData:
    """Standard market data pipeline packet."""
    def __init__(self, price: float, rsi: float, mmm_trend_regime: str, timestamp: datetime, index="NIFTY"):
        self.price = price
        self.rsi = rsi
        self.mmm_trend_regime = mmm_trend_regime  # e.g., 'TREND_UP', 'TREND_DOWN', 'NORMAL'
        self.timestamp = timestamp
        self.index = index

class Suggestion:
    def __init__(self, rule_name, action, description, risk_level="HIGH"):
        self.rule_name = rule_name
        self.action = action
        self.description = description
        self.risk_level = risk_level

    def __repr__(self):
        return f"[{self.risk_level} RISK] {self.action}: {self.description} (Rule: {self.rule_name})"


# =====================================================================
# THE MIND OF SHAILENDRA - ENGINE
# =====================================================================

class ShailendraEngine:
    """
    Stateful evaluation engine for Shailendra Signals.
    Records anchors and evaluates market data against codified heuristics.
    """
    def __init__(self, rsi_delta_threshold=15.0):
        # Anchor state (resets on the hour)
        from typing import Optional
        self.anchor_hour: Optional[int] = None
        self.anchor_price: Optional[float] = None
        self.anchor_rsi: Optional[float] = None
        
        # Base Parameters
        self.rsi_delta_threshold = rsi_delta_threshold  # Default delta that triggers "fast move"

    def _update_anchor(self, data: MarketData):
        current_hour = data.timestamp.hour
        
        # Capture anchor on first run or when the hour rolls over
        if self.anchor_hour is None or current_hour != self.anchor_hour:
            self.anchor_hour = current_hour
            self.anchor_price = data.price
            self.anchor_rsi = data.rsi
            logger.info(f"Hour Rollover -> Anchor Set: Hour={current_hour}, Price={data.price:.2f}, RSI={data.rsi:.2f}")
            return True
        return False

    def process(self, data: MarketData):
        """Runs live market data through all codified rules."""
        active_suggestions = []
        
        # 1. Check and lock in hourly state if time rolled over
        self._update_anchor(data)
        
        # Safety: Need an anchor to compare against
        if self.anchor_rsi is None:
            return active_suggestions

        # =====================================================================
        # CODIFIED THOUGHTS
        # =====================================================================
        
        # Rule 1: "The Insurance Trap"
        # Triggers if the MMM trend detection shows movement AND momentum (RSI)
        # has increased/decreased excessively since the hourly start.
        delta_rsi = data.rsi - self.anchor_rsi
        
        if data.mmm_trend_regime == "TREND_UP" and delta_rsi >= self.rsi_delta_threshold:
            active_suggestions.append(
                Suggestion(
                    rule_name="Insurance Trap",
                    action="AVOID SELLING CALLS",
                    description=f"Market is actively trending UP and hourly RSI jumped by +{delta_rsi:.1f}. Selling calls is providing cheap insurance.",
                    risk_level="CRITICAL"
                )
            )
        elif data.mmm_trend_regime == "TREND_DOWN" and delta_rsi <= -self.rsi_delta_threshold:
            active_suggestions.append(
                Suggestion(
                    rule_name="Insurance Trap",
                    action="AVOID SELLING PUTS",
                    description=f"Market is actively trending DOWN and hourly RSI dropped by {delta_rsi:.1f}. Selling puts is providing cheap insurance.",
                    risk_level="CRITICAL"
                )
            )
            
        return active_suggestions

# Provide a default singleton for ease of use in tests/simulations
default_engine = ShailendraEngine()
