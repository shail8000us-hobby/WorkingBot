#!/usr/bin/env python3
"""
Test script for Delta AI's corrected bulk cancel solution
This tests the fix WITHOUT modifying production bot code
"""

import os
import sys
import time
import json
from pathlib import Path

# Add bot directory to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Initialize Delta client (will use credentials from .env)
from bot.api.delta_client import DeltaClient

def test_corrected_bulk_cancel():
    """
    Test Delta AI's solution: Adding explicit filter parameters to bulk cancel
    """
    print("=" * 80)
    print("TESTING DELTA AI'S CORRECTED BULK CANCEL SOLUTION")
    print("=" * 80)
    
    # Initialize Delta client (will use config's credentials)
    client = DeltaClient()
    product_id = 27  # BTCUSD
    
    # Step 1: Check current open orders
    print("\n📋 Step 1: Checking current open orders...")
    try:
        orders_resp = client.list_orders(product_id=product_id, state='open')
        if orders_resp.get('success'):
            open_orders = orders_resp.get('result', [])
            buy_orders = [o for o in open_orders if o.get('side') == 'buy' and not o.get('reduce_only')]
            print(f"   Found {len(buy_orders)} open BUY orders:")
            for order in buy_orders[:5]:
                print(f"     - ID: {order.get('id')}, Price: {order.get('limit_price')}, Type: {order.get('order_type')}")
            
            if not buy_orders:
                print("   ✅ No BUY orders to cancel - test cannot proceed")
                return
        else:
            print(f"   ❌ Failed to get orders: {orders_resp}")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Step 2: Test ORIGINAL bulk cancel (for comparison)
    print("\n🔍 Step 2: Testing ORIGINAL bulk cancel (without filters)...")
    try:
        # This is what we're currently doing
        original_resp = client.cancel_all_orders(product_id=product_id)
        print(f"   API Response: success={original_resp.get('success')}")
        print(f"   Full response: {json.dumps(original_resp, indent=2)}")
        
        # Wait and verify
        time.sleep(2)
        check_resp = client.list_orders(product_id=product_id, state='open')
        if check_resp.get('success'):
            remaining = [o for o in check_resp.get('result', []) if o.get('side') == 'buy' and not o.get('reduce_only')]
            print(f"   After 2s: {len(remaining)} BUY orders still open")
            if remaining:
                print("   ❌ ORIGINAL method FAILED (as expected)")
            else:
                print("   ✅ ORIGINAL method worked (unexpected!)")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Step 3: Test CORRECTED bulk cancel (Delta AI's solution)
    print("\n🔧 Step 3: Testing CORRECTED bulk cancel (with explicit filters)...")
    print("   🔑 KEY FIX: Adding cancel_limit_orders, cancel_stop_orders, cancel_reduce_only_orders")
    
    try:
        # Check if DeltaClient has a method that accepts these parameters
        import inspect
        cancel_all_signature = inspect.signature(client.cancel_all_orders)
        print(f"   Current cancel_all_orders signature: {cancel_all_signature}")
        
        # Try to call with filter parameters
        # NOTE: This may fail if DeltaClient doesn't support these params yet
        try:
            corrected_resp = client.cancel_all_orders(
                product_id=product_id,
                cancel_limit_orders="true",
                cancel_stop_orders="true", 
                cancel_reduce_only_orders="true"
            )
            print(f"   ✅ Called with filter parameters")
            print(f"   API Response: success={corrected_resp.get('success')}")
            print(f"   Full response: {json.dumps(corrected_resp, indent=2)}")
        except TypeError as e:
            print(f"   ⚠️  DeltaClient doesn't accept filter parameters: {e}")
            print(f"   📝 Need to update DeltaClient to support these parameters")
            
            # Try manual API call to test if Delta Exchange accepts these params
            print("\n   🔬 Testing direct API call with filter parameters...")
            test_direct_api_call(client, product_id)
            return
        
        # Verify with extended polling
        print("\n   ⏳ Verifying cancellation (15s max)...")
        deadline = time.time() + 15.0
        check_count = 0
        
        while time.time() < deadline:
            check_count += 1
            time.sleep(0.5)
            
            verify_resp = client.list_orders(product_id=product_id, state='open')
            if verify_resp.get('success'):
                remaining = [o for o in verify_resp.get('result', []) if o.get('side') == 'buy' and not o.get('reduce_only')]
                
                if not remaining:
                    elapsed = time.time() - (deadline - 15.0)
                    print(f"   ✅ SUCCESS! All orders cancelled after {elapsed:.1f}s ({check_count} checks)")
                    print(f"   🎉 DELTA AI'S FIX WORKS!")
                    return
                
                if check_count % 5 == 0:
                    print(f"   🔍 Check {check_count}: {len(remaining)} orders still open")
        
        # Final check
        final_resp = client.list_orders(product_id=product_id, state='open')
        if final_resp.get('success'):
            final_remaining = [o for o in final_resp.get('result', []) if o.get('side') == 'buy' and not o.get('reduce_only')]
            if not final_remaining:
                print(f"   ✅ All orders cancelled (final check)")
                print(f"   🎉 DELTA AI'S FIX WORKS!")
            else:
                print(f"   ❌ {len(final_remaining)} orders still open after 15s")
                print(f"   ❌ DELTA AI'S FIX DID NOT WORK")
                for order in final_remaining[:3]:
                    print(f"      - Order {order.get('id')}: {order.get('state')}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_direct_api_call(client, product_id):
    """Test direct API call with filter parameters"""
    try:
        import requests
        import hmac
        import hashlib
        
        # Get credentials from client
        api_key = os.getenv('LIVE_DELTA_API_KEY')
        api_secret = os.getenv('LIVE_DELTA_API_SECRET')
        
        if not api_key or not api_secret:
            print("   ❌ API credentials not available")
            return
        
        # Prepare request
        method = 'DELETE'
        path = '/v2/orders/all'
        timestamp = str(int(time.time()))
        
        payload_data = {
            "product_id": product_id,
            "cancel_limit_orders": "true",
            "cancel_stop_orders": "true",
            "cancel_reduce_only_orders": "true"
        }
        payload = json.dumps(payload_data)
        
        # Generate signature
        signature_data = method + timestamp + path + payload
        signature = hmac.new(
            api_secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Make request
        headers = {
            'api-key': api_key,
            'timestamp': timestamp,
            'signature': signature,
            'Content-Type': 'application/json',
            'User-Agent': 'rest-client'
        }
        
        url = f'{client.base_url}{path}'
        print(f"   📡 Direct API call to: {url}")
        print(f"   📦 Payload: {payload}")
        
        response = requests.request(method, url, data=payload, headers=headers, timeout=10)
        
        print(f"   📥 Response status: {response.status_code}")
        print(f"   📥 Response body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"   ✅ Direct API call succeeded!")
                print(f"   🔍 Now verifying if orders actually cancelled...")
                
                # Verify
                time.sleep(2)
                verify_resp = client.list_orders(product_id=product_id, state='open')
                if verify_resp.get('success'):
                    remaining = [o for o in verify_resp.get('result', []) if o.get('side') == 'buy' and not o.get('reduce_only')]
                    if not remaining:
                        print(f"   🎉 CONFIRMED: Filter parameters work! Orders cancelled!")
                    else:
                        print(f"   ❌ Orders still open: {len(remaining)}")
        
    except Exception as e:
        print(f"   ❌ Direct API call failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n⚠️  WARNING: This will attempt to cancel REAL orders on LIVE exchange!")
    print("Make sure you have open BUY orders to test with.\n")
    
    response = input("Continue with test? (yes/no): ")
    if response.lower() == 'yes':
        test_corrected_bulk_cancel()
    else:
        print("Test cancelled.")
