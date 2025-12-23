#!/usr/bin/env python3
"""
Cancel all duplicate orders on Delta Exchange.
Run this before starting the bot to clean up.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bot.config import config
from bot.api.async_delta_client import AsyncDeltaClient


async def main():
    print("=" * 80)
    print("CANCELLING ALL OPEN ORDERS ON DELTA EXCHANGE")
    print("=" * 80)
    
    async with AsyncDeltaClient(config.api_key, config.api_secret) as client:
        try:
            # Get open orders
            print("\n📋 Fetching open orders...")
            orders = await client.get_open_orders(product_id=27)
            
            if not orders or len(orders) == 0:
                print("✅ No open orders found - nothing to cancel")
                return
            
            print(f"\n📊 Found {len(orders)} open order(s)")
            print("\nOrder details:")
            for i, order in enumerate(orders, 1):
                order_id = order.get('id')
                side = order.get('side')
                price = order.get('limit_price')
                size = order.get('size')
                print(f"  {i}. Order {order_id}: {side} {size} @ ${price:,.2f}")
            
            # Confirm cancellation
            print(f"\n⚠️  About to cancel {len(orders)} order(s)")
            response = input("Continue? (yes/no): ").strip().lower()
            
            if response not in ['yes', 'y']:
                print("❌ Cancelled by user")
                return
            
            # Cancel all orders
            print("\n🗑️  Cancelling orders...")
            cancelled = 0
            failed = 0
            
            for order in orders:
                order_id = order.get('id')
                try:
                    result = await client.cancel_order(order_id, product_id=27)
                    if result.get('success') or result.get('result'):
                        print(f"  ✅ Cancelled order {order_id}")
                        cancelled += 1
                    else:
                        print(f"  ❌ Failed to cancel order {order_id}: {result}")
                        failed += 1
                except Exception as e:
                    print(f"  ❌ Error cancelling order {order_id}: {e}")
                    failed += 1
                
                # Small delay between cancellations
                await asyncio.sleep(0.2)
            
            print(f"\n📊 Summary:")
            print(f"  ✅ Cancelled: {cancelled}")
            print(f"  ❌ Failed: {failed}")
            print(f"  📋 Total: {len(orders)}")
            
            if cancelled > 0:
                print("\n✅ Orders cancelled successfully - safe to start bot now")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
