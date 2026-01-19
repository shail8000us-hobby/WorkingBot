#!/usr/bin/env python3
"""Debug script to see what products are available"""
import asyncio
import os
from collections import Counter

async def debug_products():
    from bot.api.unified_api_client import UnifiedAPIClient
    
    api_key = os.getenv('DELTA_API_KEY')
    api_secret = os.getenv('DELTA_API_SECRET')
    
    client = UnifiedAPIClient(
        api_key=api_key,
        api_secret=api_secret,
        testnet=False,
        enable_websocket=False
    )
    
    products = await client.rest_client.get_products()
    
    print(f"Total products: {len(products)}\n")
    
    # Count by type
    types = Counter(p.get('product_type') for p in products)
    print("Product types:")
    for ptype, count in types.most_common():
        print(f"  {ptype}: {count}")
    
    print("\n" + "=" * 70)
    
    # Show sample option products
    print("\nSample call_options products:")
    for i, p in enumerate([p for p in products if p.get('product_type') == 'call_options'][:5], 1):
        print(f"\n{i}. {p.get('symbol')}")
        print(f"   Underlying: {p.get('underlying_asset')}")
        print(f"   Strike: {p.get('strike_price')}")
        print(f"   Settlement: {p.get('settlement_time')}")
    
    # Check underlying assets
    print("\n" + "=" * 70)
    print("\nUnique underlying assets in options:")
    underlyings = set()
    for p in products:
        if 'options' in str(p.get('product_type', '')):
            ua = p.get('underlying_asset')
            if isinstance(ua, dict):
                underlyings.add(ua.get('symbol', str(ua)))
            else:
                underlyings.add(str(ua))
    
    for u in sorted(underlyings):
        print(f"  - {u}")

if __name__ == '__main__':
    asyncio.run(debug_products())
