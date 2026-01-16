#!/usr/bin/env python3
"""Check actual realized PnL from Delta Exchange order history."""

import sys
sys.path.insert(0, '.')
sys.path.insert(0, './webui/backend')

from webui.backend.options_strategy.order_history_sync import get_order_sync
import requests
from collections import defaultdict

sync = get_order_sync()

# Get recent orders
path = '/v2/orders/history'
params = {'page_size': '100'}
query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
headers = sync._generate_signature('GET', path, f'?{query_string}')
response = requests.get(f'{sync.base_url}/v2/orders/history?{query_string}', headers=headers, timeout=30)
data = response.json()

# Filter options only
options_orders = [o for o in data.get('result', []) if o.get('product_symbol', '').startswith(('C-', 'P-'))]

print(f"Recent options orders: {len(options_orders)}")
print("\nSample orders (most recent 15):")
for o in options_orders[:15]:
    size = float(o.get('size', 0))
    price = float(o.get('average_fill_price', 0) or 0)
    value = size * price
    print(f"  {o['product_symbol']}: {o['side']} {size} @ ${price:.2f} = ${value:.2f}")

# Group by symbol
by_symbol = defaultdict(lambda: {'buys': [], 'sells': []})
for o in options_orders:
    symbol = o['product_symbol']
    size = float(o.get('size', 0))
    price = float(o.get('average_fill_price', 0) or 0)
    if o['side'] == 'buy':
        by_symbol[symbol]['buys'].append({'size': size, 'price': price})
    else:
        by_symbol[symbol]['sells'].append({'size': size, 'price': price})

print("\n" + "="*60)
print("CLOSED POSITIONS (where buy qty = sell qty):")
print("="*60)
total_realized_pnl = 0
closed_count = 0
for symbol, d in sorted(by_symbol.items()):
    buy_qty = sum(b['size'] for b in d['buys'])
    sell_qty = sum(s['size'] for s in d['sells'])
    
    if abs(buy_qty - sell_qty) < 0.01 and (buy_qty > 0 or sell_qty > 0):
        buy_value = sum(b['size'] * b['price'] for b in d['buys'])
        sell_value = sum(s['size'] * s['price'] for s in d['sells'])
        pnl = sell_value - buy_value
        total_realized_pnl += pnl
        closed_count += 1
        print(f"  {symbol}: sold ${sell_value:.2f}, bought ${buy_value:.2f} => PnL: ${pnl:.2f}")

print(f"\nClosed positions: {closed_count}")
print(f"==> Total REALIZED PnL: ${total_realized_pnl:.2f}")

print("\n" + "="*60)
print("OPEN POSITIONS (net exposure):")
print("="*60)
total_unrealized = 0
for symbol, d in sorted(by_symbol.items()):
    buy_qty = sum(b['size'] for b in d['buys'])
    sell_qty = sum(s['size'] for s in d['sells'])
    net = sell_qty - buy_qty  # Positive = net short
    
    if abs(net) > 0.01:
        buy_value = sum(b['size'] * b['price'] for b in d['buys'])
        sell_value = sum(s['size'] * s['price'] for s in d['sells'])
        # For open positions, unrealized = premium received so far
        unrealized = sell_value - buy_value
        total_unrealized += unrealized
        direction = "SHORT" if net > 0 else "LONG"
        print(f"  {symbol}: {direction} {abs(net):.0f} contracts, unrealized: ${unrealized:.2f}")

print(f"\n==> Total UNREALIZED (open positions): ${total_unrealized:.2f}")
print(f"\n==> COMBINED (realized + unrealized): ${total_realized_pnl + total_unrealized:.2f}")
