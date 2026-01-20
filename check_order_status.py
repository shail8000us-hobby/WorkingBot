#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, '.')
from bot.api.unified_api_client import UnifiedAPIClient
import yaml

async def main():
    with open('config.yaml') as f:
        config = yaml.safe_load(f)
    
    client = UnifiedAPIClient(config, 'BTCUSD', 'LONG')
    await client.initialize()
    
    # Get order by ID
    try:
        order = await client.get_order_by_id('1130290549')
        print('Order 1130290549:')
        print(f'  State: {order.get("state")}')
        print(f'  Price: {order.get("limit_price")}')
        print(f'  Size: {order.get("size")}')
        print(f'  Unfilled: {order.get("unfilled_size")}')
        print(f'  Created: {order.get("created_at")}')
    except Exception as e:
        print(f'Error getting order: {e}')
    
    # Get all open orders
    print('\nAll open BTCUSD orders:')
    open_orders = await client.get_open_orders()
    for o in open_orders:
        print(f'  ID: {o["id"]}, Side: {o["side"]}, Price: {o["limit_price"]}, Size: {o["size"]}')
    
    # Get all positions
    print('\nBTCUSD positions:')
    positions = await client.get_positions()
    for p in positions:
        if p.get('size', 0) != 0:
            print(f'  Entry: ${p.get("entry_price")}, Size: {p.get("size")}, UPnL: ${p.get("unrealized_pnl", 0)}')
    
    await client.close()

if __name__ == '__main__':
    asyncio.run(main())
