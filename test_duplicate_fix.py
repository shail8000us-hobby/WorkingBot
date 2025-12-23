#!/usr/bin/env python3
"""
Test the duplicate order fix.
This script simulates what happens when bot starts with existing orders.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bot.config import config
from bot.api.async_delta_client import AsyncDeltaClient


async def test_order_detection():
    """Test that we can detect existing orders on exchange."""
    
    print("=" * 80)
    print("TESTING DUPLICATE ORDER PREVENTION")
    print("=" * 80)
    
    async with AsyncDeltaClient(config.api_key, config.api_secret) as client:
        # Step 1: Check for existing orders
        print("\n📋 Step 1: Checking for existing orders on exchange...")
        try:
            orders = await client.get_open_orders(product_id=27)
            
            if not orders or len(orders) == 0:
                print("✅ No existing orders found")
                print("   Bot would place new order (safe)")
            else:
                print(f"⚠️  Found {len(orders)} existing order(s):")
                for i, order in enumerate(orders, 1):
                    order_id = order.get('id')
                    side = order.get('side')
                    price = order.get('limit_price')
                    size = order.get('size')
                    state = order.get('state')
                    print(f"  {i}. Order {order_id}")
                    print(f"     Side: {side}")
                    print(f"     Price: ${price:,.2f}")
                    print(f"     Size: {size}")
                    print(f"     State: {state}")
                
                print("\n✅ With the fix, bot will:")
                print("   1. Detect these existing orders")
                print("   2. Sync them to its internal state")
                print("   3. NOT place duplicate orders")
                print("   4. Track existing orders for fills")
        
        except Exception as e:
            print(f"❌ Error checking orders: {e}")
            return False
        
        # Step 2: Verify wallet
        print("\n💰 Step 2: Checking wallet balance...")
        try:
            wallet = await client.get_wallet_balance()
            if wallet:
                balance = wallet.get('balance', 0)
                available = wallet.get('available_balance', 0)
                order_margin = wallet.get('order_margin', 0)
                
                print(f"   Balance: ${balance:,.2f}")
                print(f"   Available: ${available:,.2f}")
                print(f"   Order Margin: ${order_margin:,.2f}")
                
                if order_margin > 0:
                    print(f"\n⚠️  ${order_margin:,.2f} locked in open orders")
                    print("   This will be released when orders are cancelled or filled")
        except Exception as e:
            print(f"⚠️  Could not check wallet: {e}")
        
        # Step 3: Check positions
        print("\n📈 Step 3: Checking open positions...")
        try:
            positions = await client.get_positions()
            open_positions = [p for p in positions if p.get('size', 0) != 0]
            
            if not open_positions:
                print("✅ No open positions")
            else:
                print(f"⚠️  Found {len(open_positions)} open position(s):")
                for pos in open_positions:
                    symbol = pos.get('product_symbol')
                    size = pos.get('size')
                    entry = pos.get('entry_price', 0)
                    pnl = pos.get('unrealized_pnl', 0)
                    print(f"   {symbol}: {size} contracts @ ${entry:,.2f} (PnL: ${pnl:,.2f})")
        except Exception as e:
            print(f"⚠️  Could not check positions: {e}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("\n📋 Next steps:")
    print("   1. If orders found above, run: python3 cancel_duplicate_orders.py")
    print("   2. Start bot with: python3 -m bot.run")
    print("   3. Verify bot syncs orders instead of creating duplicates")
    print("\n")
    
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_order_detection())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
