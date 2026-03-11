"""
Chain Collector
================
Fetches the expired options chain snapshot for a given expiry date.

Returns all strikes (CE + PE) with:
  - Greeks (delta, gamma, theta, vega)
  - IV (implied volatility)
  - OI (open interest)
  - Bid/ask prices from the snapshot
"""

import logging
from typing import List, Dict, Optional

from .delta_client import DeltaClient, DeltaClientError
from .rate_limiter import get_default_limiter

log = logging.getLogger("backtesting.chain_collector")


def fetch_chain_snapshot(
    expiry_date: str,
    underlying: str = "BTC",
    client: Optional[DeltaClient] = None,
) -> List[Dict]:
    """
    Fetch the full options chain snapshot for a past 0DTE expiry.

    Calls the /v2/tickers endpoint for both call_options and put_options,
    then merges into a unified list.

    Args:
        expiry_date: "DD-MM-YYYY" format
        underlying:  "BTC" or "ETH"
        client:      DeltaClient instance (creates a default one if not provided)

    Returns:
        List of option dicts, each containing:
          symbol, strike, option_type (CE/PE), best_bid, best_ask,
          mark_price, oi, greeks (delta/gamma/theta/vega), iv
    """
    if client is None:
        client = DeltaClient()

    limiter = get_default_limiter()
    chain = []

    for contract_type, side_label in [("call_options", "CE"), ("put_options", "PE")]:
        limiter.wait()
        try:
            tickers = client.get_tickers(
                contract_type=contract_type,
                underlying=underlying,
                expiry_date=expiry_date,
                states="live,expired",
            )
        except DeltaClientError as e:
            log.error(f"Failed to fetch {side_label} chain for {expiry_date}: {e}")
            tickers = []

        for t in tickers:
            greeks = t.get("greeks") or {}
            quotes = t.get("quotes") or {}

            chain.append({
                "symbol":       t.get("symbol", ""),
                "strike":       _safe_float(t.get("strike_price")),
                "option_type":  side_label,
                "underlying":   underlying,
                "expiry_date":  expiry_date,
                "mark_price":   _safe_float(t.get("mark_price")),
                "best_bid":     _safe_float(t.get("best_bid")),
                "best_ask":     _safe_float(t.get("best_ask")),
                "oi":           _safe_float(t.get("oi")),
                "volume":       _safe_float(t.get("volume")),
                "delta":        _safe_float(greeks.get("delta")),
                "gamma":        _safe_float(greeks.get("gamma")),
                "theta":        _safe_float(greeks.get("theta")),
                "vega":         _safe_float(greeks.get("vega")),
                "iv":           _safe_float(quotes.get("ask_iv") or t.get("annualized_funding") or t.get("implied_volatility")),
                "product_id":   t.get("product_id"),
                "contract_type_raw": contract_type,
            })

        log.info(f"Fetched {len(tickers)} {side_label} strikes for {expiry_date}")

    log.info(f"Chain snapshot for {expiry_date}: {len(chain)} total options")
    return chain


def build_chain_index(chain: List[Dict]) -> Dict:
    """
    Build a lookup dict: (strike, option_type) → option_dict.

    Used by sim_chain.py for fast lookups.
    """
    index = {}
    for opt in chain:
        key = (opt["strike"], opt["option_type"])
        index[key] = opt
    return index


def _safe_float(value) -> Optional[float]:
    """Convert value to float, return None if not parseable."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
