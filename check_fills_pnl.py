#!/usr/bin/env python3
"""Check fills endpoint for realized PnL from Delta Exchange"""

import sys
import os

# Add project root to path FIRST
project_root = '/Users/ssr/Projects/WorkingBot'
sys.path.insert(0, project_root)

# Change to project directory
os.chdir(project_root)

import requests
import hashlib
import hmac
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load credentials from secrets
secrets_file = Path(project_root) / 'secrets' / 'api_keys.env'
if secrets_file.exists():
    load_dotenv(secrets_file, override=True)

api_key = os.getenv('LIVE_DELTA_API_KEY') or os.getenv('DELTA_API_KEY')
api_secret = os.getenv('LIVE_DELTA_API_SECRET') or os.getenv('DELTA_API_SECRET')
base_url = 'https://api.india.delta.exchange'

if not api_key or not api_secret:
    print("ERROR: API credentials not found!")
    sys.exit(1)

def make_request(method, path, payload=None):
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + path
    if payload:
        signature_data += json.dumps(payload)
    signature = hmac.new(
        api_secret.encode('utf-8'),
        signature_data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        'api-key': api_key,
        'timestamp': timestamp,
        'signature': signature,
        'Content-Type': 'application/json'
    }
    
    url = base_url + path
    if method == 'GET':
        response = requests.get(url, headers=headers)
    return response.json()

# Fetch fills with pagination
print("=== FETCHING FILLS ===")
all_fills = []
page = 1
cutoff = datetime.now() - timedelta(days=7)

while True:
    result = make_request('GET', f'/v2/fills?page_num={page}&page_size=100')
    fills = result.get('result', [])
    if not fills:
        break
    
    for fill in fills:
        created = fill.get('created_at', '')
        if created:
            try:
                fill_time = datetime.fromisoformat(created.replace('Z', '+00:00'))
                if fill_time.replace(tzinfo=None) < cutoff:
                    continue
            except:
                pass
        all_fills.append(fill)
    
    print(f"Page {page}: {len(all_fills)} fills")
    
    # Check if we have more pages
    if len(fills) < 100:
        break
    page += 1
    if page > 50:  # Safety limit
        break

print(f"\nTotal fills (last 7 days): {len(all_fills)}")

# Group by symbol and calculate PnL
symbol_pnl = {}
total_realized = 0
fill_count = 0

for fill in all_fills:
    symbol = fill.get('product_symbol', 'unknown')
    realized = float(fill.get('realized_pnl', 0) or 0)
    
    if symbol not in symbol_pnl:
        symbol_pnl[symbol] = {'pnl': 0, 'fills': 0}
    
    symbol_pnl[symbol]['pnl'] += realized
    symbol_pnl[symbol]['fills'] += 1
    total_realized += realized
    
    if realized != 0:
        fill_count += 1

print(f"\n=== FILLS WITH NON-ZERO PNL: {fill_count} ===")

# Sort by PnL
sorted_symbols = sorted(symbol_pnl.items(), key=lambda x: x[1]['pnl'], reverse=True)

print("\n=== PNL BY SYMBOL (from fills) ===")
for symbol, data in sorted_symbols:
    if data['pnl'] != 0:
        print(f"{symbol:30} | Fills: {data['fills']:3} | PnL: ${data['pnl']:8.2f}")

print(f"\n=== TOTAL REALIZED PNL ===")
print(f"From fills API: ${total_realized:.2f}")
print(f"In INR: Rs.{total_realized * 83:.0f}")

# Also show sample fill to understand structure
if all_fills:
    print("\n=== SAMPLE FILL STRUCTURE ===")
    sample = all_fills[0]
    for key in ['product_symbol', 'side', 'size', 'price', 'realized_pnl', 'created_at', 'fill_type']:
        print(f"  {key}: {sample.get(key)}")
