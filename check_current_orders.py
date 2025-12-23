#!/usr/bin/env python3
"""
Check current open orders on Delta Exchange
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
    print("CHECKING CURRENT ORDERS ON DELTA EXCHANGE")
    print("=" * 80)
    
    async with AsyncDeltaClient(config.api_key, config.api_secret) as client:
        try:
            # Get open orders
            print("\n📋 Fetching open orders...")
            orders = await client.get_open_orders(product_id=27)
            
            if not orders:
                print("✅ No open orders found")
                return
            
            print(f"\n📊 Found {len(orders)} open order(s):\n")
            
            for i, order in enumerate(orders, 1):
                print(f"Order #{i}:")
                print(f"  ID: {order.get('id')}")
                print(f"  Side: {order.get('side')}")
                print(f"  Price: ${order.get('limit_price'):,.2f}")
                print(f"  Size: {order.get('size')}")
                print(f"  Unfilled: {order.get('unfilled_size')}")
                print(f"  State: {order.get('state')}")
                print(f"  Created: {order.get('created_at')}")
                print()
            
            # Get wallet balance
            print("\n💰 Fetching wallet balance...")
            wallet = await client.get_wallet_balance()
            if wallet:
                print(f"  Balance: ${wallet.get('balance', 0):,.2f}")
                print(f"  Available: ${wallet.get('available_balance', 0):,.2f}")
                print(f"  Position Margin: ${wallet.get('position_margin', 0):,.2f}")
                print(f"  Order Margin: ${wallet.get('order_margin', 0):,.2f}")
            
            # Get positions
            print("\n📈 Fetching positions...")
            positions = await client.get_positions()
            if positions:
                for pos in positions:
                    if pos.get('size', 0) != 0:
                        print(f"  Product: {pos.get('product_symbol')}")
                        print(f"  Size: {pos.get('size')}")
                        print(f"  Entry: ${pos.get('entry_price', 0):,.2f}")
                        print(f"  Unrealized PnL: ${pos.get('unrealized_pnl', 0):,.2f}")
            else:
                print("  No open positions")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
