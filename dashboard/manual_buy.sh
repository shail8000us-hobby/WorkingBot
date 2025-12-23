#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .venv/bin/activate ] && source .venv/bin/activate

python3 - <<'PY'
import os, json, sys
from dotenv import load_dotenv

# Load env
env_path = os.getenv("ENV_PATH", ".env.live")
load_dotenv(env_path)

# Use your existing signed client
try:
    from bot.api.delta_client import DeltaClient
except Exception as e:
    print("✖ Could not import DeltaClient:", e)
    sys.exit(1)

dc = DeltaClient()

symbol = os.getenv("DELTA_SYMBOL", "BTCUSD")
try:
    product_id = dc.resolve_product_id(symbol)
except Exception as e:
    print("✖ Could not resolve product id for", symbol, ":", e)
    sys.exit(1)

size = 1  # one lot
print(f"Placing LIVE MARKET BUY: symbol={symbol} product_id={product_id} size={size}")

try:
    # Most Delta clients accept POST /v2/orders with these fields:
    payload = {
        "product_id": product_id,
        "size": size,
        "side": "buy",
        "order_type": "market"
    }
    # DeltaClient._req signs/handles auth internally
    resp = dc._req("POST", "/v2/orders", params=payload)
    print("✅ Order response:")
    print(json.dumps(resp, indent=2))
except Exception as e:
    print("❌ Order failed:", e)
    # Common causes for 401:
    # - API key missing Trading / Read permissions
    # - IP not whitelisted for this key
    # - Using testnet key on production base URL
    # - System clock skew (rare)
    sys.exit(1)
PY
