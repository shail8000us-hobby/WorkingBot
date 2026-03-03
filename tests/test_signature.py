#!/usr/bin/env python3
"""Test signature generation for Delta Exchange API"""

import hmac
import hashlib
import time
import json
import os
from dotenv import load_dotenv

# Load environment
load_dotenv("secrets/api_keys.env")

api_key = os.getenv("LIVE_DELTA_API_KEY")
api_secret = os.getenv("LIVE_DELTA_API_SECRET")

print(f"API Key: {api_key[:10]}...")
print(f"API Secret: {api_secret[:10]}...")

# Test order data
product_id = 27
data = {
    "product_id": product_id,
    "side": "buy",
    "order_type": "limit_order",
    "limit_price": "99000.0",
    "size": 1,
    "time_in_force": "gtc",
    "post_only": True,
    "reduce_only": False
}

# Generate signature
method = "POST"
path = "/v2/orders"
timestamp = str(int(time.time()))
payload = json.dumps(data)

print(f"\nTimestamp: {timestamp}")
print(f"Method: {method}")
print(f"Path: {path}")
print(f"Payload: {payload}")

signature_data = method + timestamp + path + payload
print(f"\nSignature Data: {signature_data}")

signature = hmac.new(
    api_secret.encode('utf-8'),
    signature_data.encode('utf-8'),
    hashlib.sha256
).hexdigest()

print(f"\nSignature: {signature}")

print("\nHeaders:")
print(f"  api-key: {api_key}")
print(f"  signature: {signature}")
print(f"  timestamp: {timestamp}")
