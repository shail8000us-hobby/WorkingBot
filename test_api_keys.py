#!/usr/bin/env python3
"""Test if API keys are valid by making a simple authenticated request"""

import os
import sys
import hmac
import hashlib
import time
import requests
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv("secrets/api_keys.env")
load_dotenv(".env")

# Get API credentials (defaults to LIVE)
api_key = os.getenv("LIVE_DELTA_API_KEY") or os.getenv("DELTA_API_KEY")
api_secret = os.getenv("LIVE_DELTA_API_SECRET") or os.getenv("DELTA_API_SECRET")
base_url = "https://api.india.delta.exchange"

print(f"\n🔑 Testing API Keys:")
print(f"   Key: {api_key[:10]}... (hidden)")
print(f"   URL: {base_url}\n")

# Generate signature
method = "GET"
timestamp = str(int(time.time()))
path = "/v2/wallet/balances"
signature_data = method + timestamp + path

signature = hmac.new(
    api_secret.encode('utf-8'),
    signature_data.encode('utf-8'),
    hashlib.sha256
).hexdigest()

# Make authenticated request
headers = {
    'api-key': api_key,
    'signature': signature,
    'timestamp': timestamp,
    'User-Agent': 'python-delta-rest-client'
}

print("📡 Testing API connection...")
try:
    response = requests.get(f"{base_url}{path}", headers=headers, timeout=10)
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        print("   ✅ API Keys are VALID!")
        data = response.json()
        if 'result' in data:
            print(f"\n💰 Wallet Balances:")
            for balance in data['result'][:3]:  # Show first 3 balances
                print(f"   {balance.get('asset_symbol', 'N/A')}: {balance.get('balance', 0)}")
    elif response.status_code == 401:
        print("   ❌ API Keys are INVALID or EXPIRED!")
        print(f"   Response: {response.text}")
    else:
        print(f"   ⚠️  Unexpected response: {response.text}")
        
except Exception as e:
    print(f"   ❌ Connection failed: {e}")

print()
