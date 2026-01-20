from typing import Any, Dict, Optional


def _pick_num(d: Dict[str, Any], keys: list[str]) -> Optional[float]:
    for k in keys:
        if k in d:
            try:
                return float(d[k])
            except Exception:
                pass
    return None


def extract_price(payload: object, symbol: object | None = None) -> Optional[float]:
    """
    Supports Delta shapes:
      - {"success": true, "result": {...ticker...}}
      - {"success": true, "result": [...tickers...]}
      - plain {...} or [...]
    Price keys tried (in order): last_price, last, price, ltp, close, mark_price, mid_price, spot_price, ask, bid
    """
    PRICE_KEYS = [
        "last_price",
        "last",
        "price",
        "ltp",
        "close",
        "mark_price",
        "mid_price",  # Delta Exchange suggestion: add mid_price for options
        "spot_price",
        "ask",
        "bid",
    ]

    # Unwrap {"success":..., "result": X} or {"data": X}
    if isinstance(payload, dict):
        if "result" in payload:
            return extract_price(payload["result"], symbol)
        if "data" in payload:
            return extract_price(payload["data"], symbol)
        # Single ticker object?
        px = _pick_num(payload, PRICE_KEYS)
        if px is not None:
            return px

    # List of tickers → find matching symbol
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            sym = item.get("symbol") or item.get("product_symbol") or item.get("instrument")
            if sym and symbol is not None and sym.upper() == str(symbol).upper():
                px = _pick_num(item, PRICE_KEYS)
                if px is not None:
                    return px
        # no exact match → try first with a price
        for item in payload:
            if isinstance(item, dict):
                px = _pick_num(item, PRICE_KEYS)
                if px is not None:
                    return px

    return None
