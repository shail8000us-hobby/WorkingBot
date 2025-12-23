#!/usr/bin/env python3
"""Check current exchange status - orders and positions"""

import sys
import os
sys.path.append('/Users/ssr/Projects/WorkingBot')

# Load environment first
from dotenv import load_dotenv
load_dotenv('/Users/ssr/Projects/WorkingBot/grid_config.env')

from bot.api.delta_client import DeltaClient

def main():
    client = DeltaClient()
    
    print('='*80)
    print('🔍 EXCHANGE STATUS CHECK')
    print('='*80)
    
    # Check open orders
    print('\n📋 OPEN ORDERS:')
    orders = client.list_orders(27, state='open')
    print(f'Total: {len(orders)}')
    
    buy_orders = [o for o in orders if o['side'] == 'buy']
    sell_orders = [o for o in orders if o['side'] == 'sell']
    
    print(f'\n  BUY Orders: {len(buy_orders)}')
    for o in buy_orders:
        client_id = o.get('client_order_id', 'N/A')
        print(f"    {o['id']} @ ${o['limit_price']:,.0f} | {client_id[:40]}")
    
    print(f'\n  SELL Orders: {len(sell_orders)}')
    for o in sell_orders:
        client_id = o.get('client_order_id', 'N/A')
        print(f"    {o['id']} @ ${o['limit_price']:,.0f} | {client_id[:40]}")
    
    # Check position
    print('\n📊 POSITION:')
    pos = client.get_position(27)
    size = pos.get('size', 0)
    print(f'  Size: {size}')
    if size != 0:
        print(f'  Entry: ${pos.get("entry_price", 0):,.2f}')
        print(f'  Unrealized PnL: ${pos.get("unrealized_pnl", 0):,.2f}')
    else:
        print('  No position')
    
    # Get recent filled orders
    print('\n✅ RECENT FILLED ORDERS (last 10):')
    filled = client.list_orders(27, state='filled')[:10]
    for o in filled:
        side = o['side'].upper()
        price = o['limit_price']
        size = o['size']
        created = o.get('created_at', 'N/A')[:19]
        print(f"  {created} | {side} {size} @ ${price:,.0f}")
    
    print('\n' + '='*80)

if __name__ == '__main__':
    main()
