"""
Options AI Engine — Position Analyzer

Fetches the current options positions from the existing /api/options/positions
route and computes a structured risk summary for the AI advisor.
Does NOT make direct exchange API calls — always reuses the existing route.
"""

import logging
import requests
from typing import Dict, List, Any

from .config_ai import AI_ENGINE_CONFIG

log = logging.getLogger(__name__)

POSITIONS_URL = "http://localhost:5555/api/options/positions"


def fetch_positions() -> List[Dict]:
    """Fetch enriched positions from the existing options API route."""
    timeout = AI_ENGINE_CONFIG["positions_fetch_timeout_sec"]
    try:
        resp = requests.get(POSITIONS_URL, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return data.get("positions", [])
        log.warning(f"[position_analyzer] positions API returned failure: {data.get('error')}")
    except Exception as e:
        log.error(f"[position_analyzer] Failed to fetch positions: {e}")
    return []


def _extract_greeks(pos: Dict) -> Dict[str, float]:
    """Extract Greeks from the enriched position dict."""
    greeks = pos.get("greeks", {})
    return {
        "delta": float(greeks.get("delta", 0) or 0),
        "gamma": float(greeks.get("gamma", 0) or 0),
        "theta": float(greeks.get("theta", 0) or 0),
        "vega":  float(greeks.get("vega", 0) or 0),
    }


def _pnl_pct(entry_price: float, mark_price: float, size: float) -> float:
    """Compute unrealised P&L as a percentage of premium spent."""
    if entry_price == 0 or size == 0:
        return 0.0
    pnl = (mark_price - entry_price) * size
    cost = abs(entry_price * size)
    return (pnl / cost) * 100 if cost > 0 else 0.0


def _is_deeply_otm(pos: Dict) -> bool:
    """Return True if the position is deeply Out-of-the-Money."""
    spot = float(pos.get("spot_price", 0) or 0)
    strike = float(pos.get("strike_price", 0) or 0)
    option_type = pos.get("option_type", pos.get("contract_type", "")).upper()
    threshold = AI_ENGINE_CONFIG["deep_otm_pct"] / 100
    if spot == 0 or strike == 0:
        return False
    if "CALL" in option_type or option_type == "C":
        return (strike - spot) / spot > threshold  # call OTM when strike > spot
    if "PUT" in option_type or option_type == "P":
        return (spot - strike) / spot > threshold   # put OTM when strike < spot
    return False


def _is_deeply_itm(pos: Dict) -> bool:
    """Return True if the position is deeply In-the-Money."""
    spot = float(pos.get("spot_price", 0) or 0)
    strike = float(pos.get("strike_price", 0) or 0)
    option_type = pos.get("option_type", pos.get("contract_type", "")).upper()
    threshold = AI_ENGINE_CONFIG["deep_itm_pct"] / 100
    if spot == 0 or strike == 0:
        return False
    if "CALL" in option_type or option_type == "C":
        return (spot - strike) / spot > threshold
    if "PUT" in option_type or option_type == "P":
        return (strike - spot) / spot > threshold
    return False


def analyze_positions(raw_positions: List[Dict] = None) -> Dict[str, Any]:
    """
    Analyze all open options positions and return a structured risk summary.

    Args:
        raw_positions: Optional pre-fetched position list (for testing).
                       If None, fetches live from /api/options/positions.

    Returns:
        Dict with keys: positions, portfolio_greeks, flags, position_count,
                        total_pnl, flagged_count.
    """
    positions = raw_positions if raw_positions is not None else fetch_positions()

    analyzed = []
    portfolio_greeks = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    total_pnl = 0.0
    flagged_count = 0

    loss_threshold = AI_ENGINE_CONFIG["loss_flag_threshold_pct"]
    gamma_threshold = AI_ENGINE_CONFIG["high_gamma_threshold"]

    for pos in positions:
        size = float(pos.get("size", 0) or 0)
        if size == 0:
            continue

        entry_price = float(pos.get("entry_price", 0) or 0)
        mark_price = float(pos.get("mark_price", 0) or 0)
        unrealized_pnl = float(pos.get("unrealized_pnl", 0) or 0)
        if unrealized_pnl == 0 and entry_price and mark_price:
            unrealized_pnl = (mark_price - entry_price) * size

        pnl_pct = _pnl_pct(entry_price, mark_price, size)
        greeks = _extract_greeks(pos)

        # Accumulate portfolio-level Greeks (scaled by position size)
        for k in portfolio_greeks:
            portfolio_greeks[k] += greeks[k] * size

        total_pnl += unrealized_pnl

        # Risk flags
        flags = []
        if pnl_pct < loss_threshold:
            flags.append("high_loss")
        if abs(greeks["gamma"]) > gamma_threshold:
            flags.append("high_gamma")
        if greeks["theta"] < -50:  # losing > ₹50 theta per day
            flags.append("theta_bleeding")
        if _is_deeply_otm(pos):
            flags.append("deeply_otm")
        if _is_deeply_itm(pos):
            flags.append("deeply_itm")

        if flags:
            flagged_count += 1

        symbol = pos.get("product_symbol", pos.get("symbol", "UNKNOWN"))
        analyzed.append({
            "id": symbol,
            "symbol": symbol,
            "expiry": pos.get("expiry", pos.get("settlement_time", "")),
            "strike": float(pos.get("strike_price", 0) or 0),
            "option_type": pos.get("option_type", pos.get("contract_type", "?")),
            "size": size,
            "entry_price": round(entry_price, 4),
            "mark_price": round(mark_price, 4),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "greeks": {k: round(v, 5) for k, v in greeks.items()},
            "flags": flags,
            "iv": float(pos.get("mark_vol", 0) or 0),
        })

    return {
        "positions": analyzed,
        "portfolio_greeks": {k: round(v, 4) for k, v in portfolio_greeks.items()},
        "total_pnl": round(total_pnl, 2),
        "position_count": len(analyzed),
        "flagged_count": flagged_count,
    }


# ─── Standalone Test ─────────────────────────────────────────────────────────

def test():
    print("=== position_analyzer.test() ===")
    mock_positions = [
        {
            "product_symbol": "C-BTC-120000-280326",
            "size": 2.0,
            "entry_price": 1500,
            "mark_price": 900,
            "unrealized_pnl": -1200,
            "strike_price": 120000,
            "spot_price": 85000,
            "option_type": "C",
            "greeks": {"delta": 0.12, "gamma": 0.00002, "theta": -80, "vega": 120},
            "mark_vol": 0.65,
        },
        {
            "product_symbol": "P-BTC-80000-280326",
            "size": -1.0,
            "entry_price": 800,
            "mark_price": 300,
            "unrealized_pnl": 500,
            "strike_price": 80000,
            "spot_price": 85000,
            "option_type": "P",
            "greeks": {"delta": -0.20, "gamma": 0.00005, "theta": -60, "vega": 90},
            "mark_vol": 0.55,
        },
        {
            "product_symbol": "C-BTC-90000-280326",
            "size": 3.0,
            "entry_price": 5000,
            "mark_price": 4200,
            "unrealized_pnl": -2400,
            "strike_price": 90000,
            "spot_price": 85000,
            "option_type": "C",
            "greeks": {"delta": 0.45, "gamma": 0.04, "theta": -110, "vega": 250},
            "mark_vol": 0.70,
        },
        {
            "product_symbol": "P-BTC-75000-280326",
            "size": 1.0,
            "entry_price": 400,
            "mark_price": 100,
            "unrealized_pnl": -300,
            "strike_price": 75000,
            "spot_price": 85000,
            "option_type": "P",
            "greeks": {"delta": -0.05, "gamma": 0.00001, "theta": -20, "vega": 30},
            "mark_vol": 0.50,
        },
        {
            "product_symbol": "C-BTC-85000-280326",
            "size": 1.0,
            "entry_price": 2000,
            "mark_price": 2500,
            "unrealized_pnl": 500,
            "strike_price": 85000,
            "spot_price": 85000,
            "option_type": "C",
            "greeks": {"delta": 0.50, "gamma": 0.00008, "theta": -150, "vega": 300},
            "mark_vol": 0.60,
        },
    ]

    result = analyze_positions(mock_positions)
    print(f"  Positions analyzed: {result['position_count']}")
    print(f"  Flagged: {result['flagged_count']}")
    print(f"  Total P&L: {result['total_pnl']}")
    print(f"  Portfolio Greeks: {result['portfolio_greeks']}")
    for p in result["positions"]:
        print(f"    {p['symbol']:35s} pnl_pct={p['pnl_pct']:6.1f}%  flags={p['flags']}")
    assert result["position_count"] == 5
    assert isinstance(result["portfolio_greeks"]["delta"], float)
    print("  PASSED ✅")


if __name__ == "__main__":
    test()
