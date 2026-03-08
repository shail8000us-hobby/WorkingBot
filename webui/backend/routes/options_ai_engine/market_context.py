"""
Options AI Engine — Market Context

Wraps the existing MarketRegimeDetector and packages its output
into a compact dict suitable for injection into an AI prompt.
Never re-implements market analysis — always delegates to the existing module.
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any

log = logging.getLogger(__name__)

# Ensure project root is on sys.path so bot.* imports resolve
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def get_market_context() -> Dict[str, Any]:
    """
    Fetch current market regime and price forecast from the existing
    MarketRegimeDetector singleton. Returns a structured dict for the AI prompt.

    Falls back gracefully if the detector is unavailable (e.g., during testing).
    """
    try:
        from bot.ai.predictive.market_regime import get_market_regime_detector
        detector = get_market_regime_detector()
        analysis = detector.analyze_market()

        regime_data = analysis.get("regime", {})
        forecast_data = analysis.get("forecast", {})
        metrics = regime_data.get("metrics", {})

        # Derive a simple IV classification from the volatility metric
        volatility_score = float(metrics.get("volatility", 0))
        if volatility_score < 0.3:
            iv_classification = "low"
        elif volatility_score < 0.6:
            iv_classification = "medium"
        else:
            iv_classification = "high"

        return {
            "regime": regime_data.get("regime", "UNKNOWN"),
            "regime_confidence": regime_data.get("confidence", 0.0),
            "regime_description": regime_data.get("description", ""),
            "trend": "bullish" if float(metrics.get("momentum", 0)) > 0.2
                     else "bearish" if float(metrics.get("momentum", 0)) < -0.2
                     else "sideways",
            "momentum": float(metrics.get("momentum", 0)),
            "volatility_score": round(volatility_score, 3),
            "iv_classification": iv_classification,
            "mean_reversion_tendency": float(metrics.get("mean_reversion", 0)),
            "trend_strength": float(metrics.get("trend_strength", 0)),
            "price_direction": forecast_data.get("direction", "UNKNOWN"),
            "price_forecast_confidence": float(forecast_data.get("confidence", 0)),
            "current_price": float(analysis.get("current_price", 0)),
            "recommendations": regime_data.get("recommendations", {}),
        }

    except ImportError as e:
        log.warning(f"[market_context] MarketRegimeDetector not available: {e}")
        return _fallback_context()
    except Exception as e:
        log.error(f"[market_context] Error getting market context: {e}")
        return _fallback_context()


def _fallback_context() -> Dict[str, Any]:
    """Return a safe default when market data is unavailable."""
    return {
        "regime": "UNKNOWN",
        "regime_confidence": 0.0,
        "regime_description": "Market data unavailable",
        "trend": "sideways",
        "momentum": 0.0,
        "volatility_score": 0.5,
        "iv_classification": "medium",
        "mean_reversion_tendency": 0.5,
        "trend_strength": 0.0,
        "price_direction": "UNKNOWN",
        "price_forecast_confidence": 0.0,
        "current_price": 0.0,
        "recommendations": {},
    }


# ─── Standalone Test ─────────────────────────────────────────────────────────

def test():
    print("=== market_context.test() ===")
    ctx = get_market_context()
    print(f"  Regime: {ctx['regime']} (confidence={ctx['regime_confidence']})")
    print(f"  Trend: {ctx['trend']}  IV: {ctx['iv_classification']}")
    print(f"  Direction: {ctx['price_direction']}")
    # Validate expected keys regardless of live data availability
    required_keys = [
        "regime", "trend", "iv_classification", "volatility_score",
        "momentum", "current_price", "price_direction"
    ]
    for k in required_keys:
        assert k in ctx, f"Missing key: {k}"
    print("  PASSED ✅")


if __name__ == "__main__":
    test()
