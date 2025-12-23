#!/usr/bin/env python3
"""
Quick test of Delta AI's fix using bot's actual credentials
"""
import sys
import time
from pathlib import Path

# Use bot's path setup
sys.path.insert(0, str(Path(__file__).parent))

# Import after path setup (bot will load .env internally)
from bot.api.delta_client import DeltaClient

def test_corrected_bulk_cancel():
    print("=" * 80)
    print("TESTING DELTA AI'S CORRECTED BULK CANCEL FIX")
    print("=" * 80)
    
    # Create Delta client (will load credentials from .env)
    print("\n📋 Initializing Delta API client...")
    client = DeltaClient()
    
    product_id = 27  # BTCUSD
    
    # Check current orders
    print(f"\n🔍 Checking open orders on exchange...")
    try:
        orders_resp = client.list_orders(product_id=product_id, state='open')
        if orders_resp.get('success'):
            open_orders = orders_resp.get('result', [])
            buy_orders = [o for o in open_orders if o.get('side') == 'buy' and not o.get('reduce_only')]
            
            print(f"   Found {len(buy_orders)} open BUY orders:")
            for order in buy_orders:
                print(f"     - ID: {order['id']}, Price: ${order.get('limit_price', 'N/A')}")
            
            if not buy_orders:
                print("\n   ⚠️  No BUY orders to test with!")
                print("   Start the bot first to place an order, then run this test.")
                return
        else:
            print(f"   ❌ Failed to get orders: {orders_resp}")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Test the CORRECTED bulk cancel (with filter parameters)
    print(f"\n🔧 Testing CORRECTED bulk cancel (Delta AI's fix)...")
    print(f"   🔑 Sending filter parameters: cancel_limit_orders=true, cancel_stop_orders=true")
    
    try:
        # Call cancel_all_orders (now with filter parameters by default)
        cancel_resp = client.cancel_all_orders(product_id=product_id)
        
        print(f"\n📥 API Response:")
        print(f"   Success: {cancel_resp.get('success')}")
        print(f"   Full response: {cancel_resp}")
        
        if not cancel_resp.get('success'):
            print(f"\n❌ Bulk cancel API returned failure!")
            return
        
        # Verify orders actually cancelled (15s polling)
        print(f"\n⏳ Verifying cancellation (15s max, checking every 500ms)...")
        
        deadline = time.time() + 15.0
        check_count = 0
        
        while time.time() < deadline:
            check_count += 1
            time.sleep(0.5)
            
            verify_resp = client.list_orders(product_id=product_id, state='open')
            if verify_resp.get('success'):
                remaining = [o for o in verify_resp.get('result', []) 
                           if o.get('side') == 'buy' and not o.get('reduce_only')]
                
                if not remaining:
                    elapsed = time.time() - (deadline - 15.0)
                    print(f"\n✅ SUCCESS! All orders cancelled after {elapsed:.1f}s ({check_count} checks)")
                    print(f"\n🎉 DELTA AI'S FIX WORKS!")
                    print(f"   The filter parameters solved the issue!")
                    return
                
                if check_count % 10 == 0:
                    print(f"   Check {check_count}: {len(remaining)} orders still open...")
        
        # Final check
        final_resp = client.list_orders(product_id=product_id, state='open')
        if final_resp.get('success'):
            final_remaining = [o for o in final_resp.get('result', [])
                             if o.get('side') == 'buy' and not o.get('reduce_only')]
            
            if not final_remaining:
                print(f"\n✅ All orders cancelled (confirmed in final check)")
                print(f"🎉 DELTA AI'S FIX WORKS!")
            else:
                print(f"\n❌ DELTA AI'S FIX DID NOT WORK")
                print(f"   {len(final_remaining)} orders still open after 15s:")
                for order in final_remaining:
                    print(f"     - Order {order['id']}: {order.get('state')}")
                print(f"\n   This confirms the issue is a Delta Exchange API bug,")
                print(f"   NOT a parameter configuration problem.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n⚠️  This test will cancel REAL orders on the exchange!")
    print("Current pending order: 1016684111 @ $109,000\n")
    
    response = input("Continue? (yes/no): ")
    if response.lower() == 'yes':
        test_corrected_bulk_cancel()
    else:
        print("Test cancelled.")
