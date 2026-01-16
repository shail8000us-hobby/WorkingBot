#!/usr/bin/env python3
"""Test script to debug the API and sync."""

import sys
sys.path.insert(0, '.')

from webui.backend.options_strategy.real_trade_sync import get_real_trade_sync
import requests
import time
from datetime import datetime

sync = get_real_trade_sync()

print("=" * 60)
print("Testing Delta Exchange API")
print("=" * 60)

# Test 1: Without time filters
print("\n1. Fetching orders WITHOUT time filters...")
path = '/v2/orders/history'
params = {'page_size': '100'}
query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
headers = sync._generate_signature('GET', path, f'?{query_string}')

response = requests.get(f'{sync.base_url}{path}?{query_string}', headers=headers, timeout=30)
data = response.json()

print(f"   Total count: {data.get('meta', {}).get('total_count', 0)}")
print(f"   Results: {len(data.get('result', []))}")

results = data.get('result', [])
if results:
    # Filter options
    options = [o for o in results if o.get('product_symbol', '').startswith(('C-', 'P-'))]
    print(f"   Options orders: {len(options)}")
    
    print("\n   Recent options orders:")
    for o in options[:10]:
        created = o.get('created_at', '')[:19]
        print(f"     {created} - {o.get('product_symbol')} - {o.get('side')} {o.get('size')} @ {o.get('average_fill_price')} - {o.get('state')}")

# Test 2: Run the full sync without time filter
print("\n" + "=" * 60)
print("2. Running full sync (fetching all pages)...")
print("=" * 60)

# Modify fetch to not use time filters
all_orders = []
after_cursor = None
max_pages = 20

for page in range(max_pages):
    params = {'page_size': '100'}
    if after_cursor:
        params['after'] = after_cursor
    
    query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
    headers = sync._generate_signature('GET', path, f'?{query_string}')
    
    response = requests.get(f'{sync.base_url}{path}?{query_string}', headers=headers, timeout=30)
    data = response.json()
    
    results = data.get('result', [])
    if not results:
        break
    
    all_orders.extend(results)
    after_cursor = data.get('meta', {}).get('after')
    
    if not after_cursor:
        break
    
    print(f"   Page {page + 1}: {len(results)} orders, total: {len(all_orders)}")
    time.sleep(0.1)

print(f"\n   Total orders fetched: {len(all_orders)}")

# Filter for options
options_orders = [o for o in all_orders if o.get('product_symbol', '').startswith(('C-', 'P-')) and o.get('state') == 'closed']
print(f"   Closed options orders: {len(options_orders)}")

# Calculate PnL
print("\n" + "=" * 60)
print("3. Calculating PnL...")
print("=" * 60)

pnl_data = sync.calculate_pnl_by_symbol(options_orders)

# Summary
summary = sync.get_summary(pnl_data)
print(f"\n   Summary:")
for key, value in summary.items():
    print(f"     {key}: {value}")

# Save to file
print("\n" + "=" * 60)
print("4. Saving trades to CSV...")
print("=" * 60)
sync.save_trades_to_csv(pnl_data)

print("\nDone!")
