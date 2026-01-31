#!/usr/bin/env python
"""Test order states from Delta Exchange API"""
import asyncio
import sys
import yaml
sys.path.insert(0, '.')

# Load config directly
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

api_key = config.get('delta', {}).get('api_key', '')
api_secret = config.get('delta', {}).get('api_secret', '')

from bot.api.async_delta_client import AsyncDeltaClient

async def test():
    client = AsyncDeltaClient(api_key=api_key, api_secret=api_secret)
    
    # List recent closed/filled orders to see what state values look like
    print('=== Testing order states ===')
    orders = await client.list_orders(states='closed', page_size=5)
    print(f'\n=== CLOSED/FILLED orders (found {len(orders)}) ===')
    for o in orders[:3]:
        print(f'Order ID: {o.get("id")}')
        print(f'  Symbol: {o.get("product_symbol")}')
        print(f'  State: {o.get("state")}')
        print(f'  Size: {o.get("size")} / Filled: {o.get("filled_size")}')
        print(f'  Unfilled: {o.get("unfilled_size")}')
        print()
    
    # Also test getting a specific order to see what get_order returns
    if orders:
        order_id = str(orders[0].get('id'))
        print(f'=== Testing get_order({order_id}) ===')
        order_detail = await client.get_order(order_id)
        print(f'State: {order_detail.get("state")}')
        print(f'Full response: {order_detail}')
    
    await client.close()

asyncio.run(test())
