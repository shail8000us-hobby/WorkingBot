#!/usr/bin/env python3
"""Cancel all open orders on Delta Exchange (for cleaning up test orders)"""

import asyncio
import os
from dotenv import load_dotenv
from bot.api.async_delta_client import AsyncDeltaClient

async def main():
    # Load API credentials
    load_dotenv("secrets/api_keys.env")
    load_dotenv(".env")
    
    api_key = os.getenv("DELTA_API_KEY")
    api_secret = os.getenv("DELTA_API_SECRET")
    product_id = int(os.getenv("DELTA_PRODUCT_ID", "27"))
    
    print(f"🔧 Connecting to Delta Exchange...")
    print(f"   Product ID: {product_id}")
    
    async with AsyncDeltaClient(
        api_key=api_key,
        api_secret=api_secret,
        base_url="https://api.india.delta.exchange"
    ) as client:
        # Get all open orders
        print(f"\n📋 Fetching open orders...")
        orders_response = await client.get_open_orders(product_id=product_id)
        orders = orders_response.get("result", [])
        
        if not orders:
            print("✅ No open orders found!")
            return
        
        print(f"   Found {len(orders)} open orders")
        
        # Cancel each order
        cancelled = 0
        for order in orders:
            order_id = order.get("id")
            side = order.get("side")
            price = order.get("limit_price")
            size = order.get("size")
            
            print(f"\n🗑️  Cancelling order {order_id}")
            print(f"   Side: {side}, Price: {price}, Size: {size}")
            
            try:
                await client.cancel_order(order_id)
                cancelled += 1
                print(f"   ✅ Cancelled!")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        print(f"\n✅ Done! Cancelled {cancelled}/{len(orders)} orders")

if __name__ == "__main__":
    asyncio.run(main())
