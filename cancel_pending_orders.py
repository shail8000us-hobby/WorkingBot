#!/usr/bin/env python3
"""
Cancel all pending BUY orders from Delta Exchange
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.utils.env_loader import load_trading_mode_config
from bot.api.delta_client import DeltaClient

def main():
    print("=" * 70)
    print("🔍 Checking for pending orders on Delta Exchange")
    print("=" * 70)
    
    # Load configuration
    api_key, api_secret, product_id, api_url, ws_url = load_trading_mode_config()
    
    print(f"\n📍 API URL: {api_url}")
    print(f"📦 Product ID: {product_id}")
    
    # Initialize client
    client = DeltaClient(api_key, api_secret, api_url, ws_url)
    
    # Get all open orders
    print("\n🔍 Fetching open orders...")
    try:
        response = client.get_active_orders(product_id=product_id)
        
        if not response.get('success'):
            print(f"❌ Failed to fetch orders: {response}")
            return 1
        
        all_orders = response.get('result', [])
        print(f"✅ Found {len(all_orders)} total open orders")
        
        if not all_orders:
            print("\n✅ No pending orders - all clean!")
            return 0
        
        # Categorize orders
        buy_orders = []
        tp_orders = []
        
        for order in all_orders:
            side = order.get('side', '').lower()
            order_id = order.get('id')
            state = order.get('state', '').lower()
            price = order.get('limit_price', 0)
            size = order.get('size', 0)
            
            # Skip non-pending orders
            if state in ['filled', 'cancelled', 'rejected']:
                continue
            
            # Check if it's a TP order
            is_reduce_only = order.get('close_on_trigger', False) or order.get('reduce_only', False)
            
            if side == 'buy' and not is_reduce_only:
                buy_orders.append(order)
                print(f"  • BUY @ ${price:,.2f}, Size={size}, ID={order_id}")
            else:
                tp_orders.append(order)
                print(f"  • TP/SELL @ ${price:,.2f}, Size={size}, ID={order_id} (protected)")
        
        if buy_orders:
            print(f"\n🔥 Cancelling {len(buy_orders)} pending BUY order(s)...")
            cancelled = 0
            failed = 0
            
            for order in buy_orders:
                order_id = order.get('id')
                price = order.get('limit_price', 0)
                
                print(f"   Cancelling {order_id} @ ${price:,.2f}...", end=" ")
                
                try:
                    cancel_response = client.cancel_order(order_id)
                    if cancel_response.get('success'):
                        print("✅")
                        cancelled += 1
                    else:
                        print(f"❌ {cancel_response.get('error', {}).get('message', 'Unknown error')}")
                        failed += 1
                except Exception as e:
                    print(f"❌ {e}")
                    failed += 1
            
            print(f"\n📊 Results:")
            print(f"   ✅ Cancelled: {cancelled}")
            print(f"   ❌ Failed: {failed}")
            print(f"   🛡️ Preserved TP orders: {len(tp_orders)}")
        else:
            print(f"\n✅ No pending BUY orders to cancel")
            print(f"🛡️ {len(tp_orders)} TP order(s) preserved")
        
        print("\n✅ Done!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
