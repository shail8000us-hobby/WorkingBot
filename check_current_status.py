#!/usr/bin/env python3
"""Check current exchange status - modified from test script"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('secrets/api_keys.env')

# Set DELTA_API keys from LIVE_ prefixed versions
if 'LIVE_DELTA_API_KEY' in os.environ and 'DELTA_API_KEY' not in os.environ:
    os.environ['DELTA_API_KEY'] = os.environ['LIVE_DELTA_API_KEY']
    os.environ['DELTA_API_SECRET'] = os.environ['LIVE_DELTA_API_SECRET']

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

from api.delta_client import DeltaClient

def main():
    client = DeltaClient()
    
    print('='*80)
    print('🔍 CURRENT EXCHANGE STATUS')
    print('='*80)
    
    # Check open orders
    print('\n📋 OPEN ORDERS:')
    response = client.list_orders(product_id=27, state='open')
    orders = response.get('result', []) if isinstance(response, dict) else []
    
    print(f'Total open orders: {len(orders)}')
    
    buy_orders = [o for o in orders if o.get('side') == 'buy']
    sell_orders = [o for o in orders if o.get('side') == 'sell']
    
    print(f'\n  📈 BUY Orders: {len(buy_orders)}')
    for o in buy_orders:
        order_id = o.get('id')
        price = o.get('limit_price')
        size = o.get('size')
        client_id = o.get('client_order_id', 'N/A')[:45]
        print(f"    ID: {order_id} | ${price:,.0f} | Size: {size} | {client_id}")
    
    print(f'\n  📉 SELL (TP) Orders: {len(sell_orders)}')
    for o in sell_orders:
        order_id = o.get('id')
        price = o.get('limit_price')
        size = o.get('size')
        client_id = o.get('client_order_id', 'N/A')[:45]
        print(f"    ID: {order_id} | ${price:,.0f} | Size: {size} | {client_id}")
    
    # Check position
    print('\n📊 CURRENT POSITION:')
    pos = client.get_position(27)
    size = pos.get('size', 0)
    print(f'  Position size: {size}')
    
    if size != 0:
        entry = float(pos.get('entry_price', 0))
        pnl = float(pos.get('unrealized_pnl', 0))
        print(f'  Entry price: ${entry:,.2f}')
        print(f'  Unrealized PnL: ${pnl:,.2f}')
    else:
        print('  ✅ No open position (flat)')
    
    # Get recent filled orders
    print('\n✅ RECENT FILLED ORDERS (last 10):')
    response = client.list_orders(product_id=27, state='filled')
    filled = response.get('result', [])[:10] if isinstance(response, dict) else []
    
    for o in filled:
        side = o.get('side', '').upper()
        price = o.get('limit_price', 0)
        size = o.get('size', 0)
        created = o.get('created_at', 'N/A')[:19]
        client_id = o.get('client_order_id', '')
        
        # Identify order type
        order_type = 'BUY' if side == 'BUY' else 'TP' if 'tp' in client_id.lower() else 'SELL'
        print(f"  {created} | {order_type:4} | {size} @ ${price:,.0f}")
    
    print('\n' + '='*80)
    
    # Analysis
    print('\n📝 ANALYSIS:')
    if len(buy_orders) == 0 and size == 0:
        print('  ⚠️  WARNING: No BUY orders and no position!')
        print('      Bot should place a BUY order')
    elif size > 0 and len(sell_orders) == 0:
        print('  ⚠️  CRITICAL: Position open but NO TP SELL order!')
        print('      This is the TP order failure issue!')
    elif size > 0 and len(sell_orders) > 0:
        print(f'  ✅ Good: {size} position(s) with {len(sell_orders)} TP order(s)')
    else:
        print('  ✅ State looks normal')
    
    print('='*80)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
