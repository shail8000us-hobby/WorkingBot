import json
import sys
import os
from bot.api.delta_client import DeltaClient
from dotenv import load_dotenv
cat > scripts/panic_cancel_open_orders.py << 'PY'

# Load env (default to .env.live)
env_path = os.getenv("ENV_PATH", ".env.live")
load_dotenv(env_path)

# Import Delta client


def _extract_order_ids(payload):
    ids = set()
    if isinstance(payload, dict):
        # Common shapes: {"result":[...]} or {"orders":[...]} or direct list
        for key in ("result", "orders"):
            if key in payload and isinstance(payload[key], list):
                for o in payload[key]:
                    if isinstance(o, dict) and "id" in o:
                        st = str(o.get("status", "")).lower()
                        if st in ("open", "working", "live", "new", "active", "pending"):
                            ids.add(o["id"])
        # Fallback: if top-level has list-like
        if not ids and isinstance(payload.get("result"), list):
            for o in payload["result"]:
                if isinstance(o, dict) and "id" in o:
                    ids.add(o["id"])
    elif isinstance(payload, list):
        for o in payload:
            if isinstance(o, dict) and "id" in o:
                ids.add(o["id"])
    return list(ids)


def _try_list_open_orders(dc):
    # Try a few likely endpoints, be tolerant to shapes
    tries = [
        ("GET", "/v2/open_orders", None),
        ("GET", "/v2/orders/open", None),
        ("GET", "/v2/orders", {"status": "open"}),
    ]
    last_err = None
    for method, path, params in tries:
        try:
            data = dc._req(method, path, params=params)  # type: ignore
            ids = _extract_order_ids(data)
            if ids:
                return ids
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return []


def main():
    dc = DeltaClient()
    try:
        ids = _try_list_open_orders(dc)
    except Exception as e:
        print(f"[panic] Failed to list open orders: {e}")
        # Still attempt nothing-cancel path
        ids = []

    if not ids:
        print("[panic] No open orders found.")
        return

    cancelled = 0
    for oid in ids:
        try:
            dc.cancel_order(oid)
            cancelled += 1
            print(f"[panic] Cancelled order id={oid}")
        except Exception as e:
            print(f"[panic] Cancel FAILED id={oid}: {e}")

    print(
        f"[panic] Done. Requested cancel for {cancelled}/{len(ids)} open orders.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[panic] Unhandled error: {e}")
        sys.exit(1)
PY
