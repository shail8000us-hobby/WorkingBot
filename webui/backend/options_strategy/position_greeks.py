"""
Per-Position Black-Scholes Greeks
==================================
Independent module — safe to import anywhere, no circular dependencies.
Computes DTE, delta, gamma, theta ($/day), vega per position.

Usage:
    from webui.backend.options_strategy.position_greeks import enrich_positions_with_greeks
    positions = enrich_positions_with_greeks(positions, spot_price=70975.0)
    # Each position now has: pos_greeks = {delta, gamma, theta, vega, dte}
"""

import math
from datetime import datetime, date
from typing import Dict, List, Optional

# BTC options on Delta Exchange: 1 contract = 0.001 BTC
# ETH options: 1 contract = 0.01 ETH
CONTRACT_MULTIPLIER = {"BTC": 0.001, "ETH": 0.01}
RISK_FREE_RATE = 0.0  # Crypto standard (same as payoffCalculator.js)


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def _norm_cdf(x: float) -> float:
    """Standard normal CDF — Abramowitz & Stegun (error < 1e-7)."""
    if x >= 0:
        k = 1.0 / (1.0 + 0.2316419 * x)
        p = (0.319381530 * k
             - 0.356563782 * k * k
             + 1.781477937 * k ** 3
             - 1.821255978 * k ** 4
             + 1.330274429 * k ** 5)
        return 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x * x) * p
    return 1.0 - _norm_cdf(-x)


def _norm_pdf(x: float) -> float:
    return (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x * x)


# ---------------------------------------------------------------------------
# Black-Scholes Greeks
# ---------------------------------------------------------------------------

def bs_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,   # "call" or "put"
) -> Dict[str, float]:
    """
    Per-contract Black-Scholes Greeks.

    Returns:
        {
          delta: float,    # unitless (0-1 for calls, -1-0 for puts)
          gamma: float,    # per $1 move in spot
          theta: float,    # $/day per contract (with multiplier baked in)
          vega:  float,    # $ per 1 vol-point change (per contract)
        }
    All values are per single contract BEFORE size scaling.
    """
    zero = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        # Intrinsic-only at expiry
        if option_type == "call":
            return {**zero, "delta": 1.0 if S > K else 0.0}
        return {**zero, "delta": -1.0 if S < K else 0.0}

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    nd1 = _norm_pdf(d1)

    if option_type == "call":
        delta = _norm_cdf(d1)
        theta_annual = (
            -(S * nd1 * sigma) / (2 * sqrt_T)
            - r * K * math.exp(-r * T) * _norm_cdf(d2)
        )
    else:
        delta = _norm_cdf(d1) - 1.0
        theta_annual = (
            -(S * nd1 * sigma) / (2 * sqrt_T)
            + r * K * math.exp(-r * T) * _norm_cdf(-d2)
        )

    gamma = nd1 / (S * sigma * sqrt_T)
    theta_per_day = theta_annual / 365.0
    vega_per_vol_point = S * nd1 * sqrt_T / 100.0  # per 1 vol pt (e.g. 0.01 change)

    return {
        "delta": round(delta, 6),
        "gamma": round(gamma, 8),
        "theta": round(theta_per_day, 6),
        "vega": round(vega_per_vol_point, 6),
    }


# ---------------------------------------------------------------------------
# Expiry / DTE parsing
# ---------------------------------------------------------------------------

def parse_expiry_date(symbol: str) -> Optional[date]:
    """
    Extract expiry date from Delta Exchange symbol.
    Format: C-BTC-72000-260313  →  expiry = 2026-03-13
            P-BTC-67500-260313  →  2026-03-13
    """
    try:
        parts = symbol.split("-")
        if len(parts) < 4:
            return None
        raw = parts[-1]  # e.g. "270326" = DDMMYY (27-Mar-2026)
        dd, mm, yy = int(raw[0:2]), int(raw[2:4]), int(raw[4:6])
        year = 2000 + yy
        return date(year, mm, dd)
    except Exception:
        return None


def compute_dte(symbol: str) -> int:
    """Days to expiry (integer, floored; 0 if expired)."""
    exp = parse_expiry_date(symbol)
    if exp is None:
        return 0
    today = date.today()
    return max(0, (exp - today).days)


# ---------------------------------------------------------------------------
# Main enrichment function
# ---------------------------------------------------------------------------

def enrich_positions_with_greeks(
    positions: List[Dict],
    spot_price: float,
) -> List[Dict]:
    """
    Attach per-position Greeks to each position dict (non-destructive copy).

    Adds `pos_greeks` key:
        {
          dte:   int,
          delta: float,   # position delta = per-contract * size (signed)
          gamma: float,   # position gamma = per-contract * size (signed; negative for short)
          theta: float,   # position theta $/day = per-contract * size (signed; positive for short)
          vega:  float,   # position vega = per-contract * size (signed; negative for short)
        }

    Args:
        positions:   List of position dicts from /api/options/positions
        spot_price:  Current BTC spot price in USD
    """
    result = []
    for pos in positions:
        pos = dict(pos)  # shallow copy — don't mutate caller's dict
        symbol = pos.get("product_symbol", "")
        size = float(pos.get("size", 0) or 0)
        dte = compute_dte(symbol)
        T = max(dte / 365.0, 1e-6)  # time to expiry in years

        # Determine underlying & multiplier
        parts = symbol.split("-")
        underlying = parts[1] if len(parts) >= 2 else "BTC"
        multiplier = CONTRACT_MULTIPLIER.get(underlying.upper(), 0.001)

        # Determine option type
        opt_type = "call" if parts[0].upper() == "C" else "put"

        # Strike from symbol (e.g. "72000")
        try:
            strike = float(parts[2]) if len(parts) >= 3 else 0.0
        except (ValueError, IndexError):
            strike = 0.0

        # IV from position (may come from exchange greeks or enriched data)
        iv_raw = pos.get("iv") or (pos.get("greeks") or {}).get("iv") or 0.0
        iv = float(iv_raw)
        if iv > 5:
            iv = iv / 100.0  # convert from % (e.g. 65.0) to decimal (0.65)

        pos_greeks = {"dte": dte, "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

        if strike > 0 and iv > 0 and spot_price > 0:
            cg = bs_greeks(spot_price, strike, T, RISK_FREE_RATE, iv, opt_type)

            # Scale to position: All Greeks should use signed size.
            # Short positions (size < 0) are short Delta, Gamma, and Vega, but earn Theta.
            pos_greeks = {
                "dte": dte,
                "delta": round(cg["delta"] * size * multiplier, 6),
                "gamma": round(cg["gamma"] * size * multiplier, 8),
                "theta": round(cg["theta"] * size * multiplier, 4),
                "vega": round(cg["vega"] * size * multiplier, 4),
            }

        pos["pos_greeks"] = pos_greeks
        result.append(pos)

    return result


def compute_expiry_subtotals(positions: List[Dict]) -> Dict[str, Dict]:
    """
    Aggregate pos_greeks by expiry for the subtotal rows.

    Returns:
        { "2026-03-13": {delta, gamma, theta, vega, count}, ... }
    """
    totals: Dict[str, Dict] = {}
    for pos in positions:
        symbol = pos.get("product_symbol", "")
        exp = parse_expiry_date(symbol)
        if exp is None:
            continue
        key = str(exp)
        if key not in totals:
            totals[key] = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "count": 0}
        pg = pos.get("pos_greeks") or {}
        totals[key]["delta"] += pg.get("delta", 0.0)
        totals[key]["gamma"] += pg.get("gamma", 0.0)
        totals[key]["theta"] += pg.get("theta", 0.0)
        totals[key]["vega"] += pg.get("vega", 0.0)
        totals[key]["count"] += 1
    # Round totals
    for k in totals:
        totals[k]["delta"] = round(totals[k]["delta"], 4)
        totals[k]["gamma"] = round(totals[k]["gamma"], 6)
        totals[k]["theta"] = round(totals[k]["theta"], 2)
        totals[k]["vega"] = round(totals[k]["vega"], 2)
    return totals
