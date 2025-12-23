from __future__ import annotations

from typing import Any, Dict, List, Optional


def _pick_float(d: Dict[str, Any], keys: List[str]) -> Optional[float]:
    for k in keys:
        if k in d:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                return None
    return None


def _to_order(d: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    oid = d.get("order_id") or d.get("id")
    sym = d.get("symbol") or d.get("product_symbol") or d.get("instrument")
    status = (d.get("status") or "").lower() or "open"

    price = _pick_float(
        d, ["price", "limit_price", "avg_price", "execution_price"])
    size = _pick_float(d, ["size", "qty", "quantity", "order_qty"])

    if not oid or not sym:
        return None

    return {
        "order_id": str(oid),
        "symbol": sym,
        "price": price,
        "size": size,
        "status": status,
    }


def normalize_open_orders(payload: Any, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """Normalize various API payload shapes into a list of order dicts."""
    data = payload
    if isinstance(payload, dict):
        if "result" in payload:
            data = payload["result"]
        elif "data" in payload:
            data = payload["data"]

    out: List[Dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                o = _to_order(item)
                if o:
                    out.append(o)
    elif isinstance(data, dict):
        o = _to_order(data)
        if o:
            out.append(o)

    if symbol:
        out = [o for o in out if (
            o.get("symbol") or "").upper() == symbol.upper()]
    return out
