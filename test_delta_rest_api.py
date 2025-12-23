#!/usr/bin/env python3
"""
Test Delta Exchange REST API Methods

Tests the exact methods used in gridbot.py REST fallback:
1. get_ticker_by_product_id() - for price polling
2. get_order() - for order status checking

Run: python test_delta_rest_api.py
"""

import sys
import os
import time
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv('secrets/api_keys.env')

# Set DELTA_API keys from LIVE_ prefixed versions
if 'LIVE_DELTA_API_KEY' in os.environ and 'DELTA_API_KEY' not in os.environ:
    os.environ['DELTA_API_KEY'] = os.environ['LIVE_DELTA_API_KEY']
    os.environ['DELTA_API_SECRET'] = os.environ['LIVE_DELTA_API_SECRET']

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

from api.delta_client import DeltaClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

def test_get_ticker_by_product_id():
    """Test get_ticker_by_product_id() method"""
    print("\n" + "="*80)
    print("TEST 1: get_ticker_by_product_id()")
    print("="*80)
    
    try:
        # Initialize client (uses config.ini credentials)
        client = DeltaClient()
        
        # Test with BTCUSD (product_id = 27)
        product_id = 27
        symbol = "BTCUSD"
        
        print(f"\n📊 Testing: get_ticker_by_product_id({product_id}) for {symbol}")
        
        start_time = time.time()
        ticker = client.get_ticker_by_product_id(product_id)
        elapsed = (time.time() - start_time) * 1000
        
        if ticker:
            print(f"✅ SUCCESS - Received ticker in {elapsed:.0f}ms")
            print(f"\nTicker Data:")
            print(f"  - Symbol: {ticker.get('symbol', 'N/A')}")
            print(f"  - Mark Price: ${ticker.get('mark_price', 'N/A')}")
            print(f"  - Close Price: ${ticker.get('close', 'N/A')}")
            print(f"  - Volume: {ticker.get('volume', 'N/A')}")
            print(f"  - High: ${ticker.get('high', 'N/A')}")
            print(f"  - Low: ${ticker.get('low', 'N/A')}")
            
            # Check required fields for gridbot
            if 'close' in ticker:
                print(f"\n✅ Required field 'close' present: ${ticker['close']}")
            else:
                print(f"\n❌ ERROR: Required field 'close' missing!")
                return False
                
            return True
        else:
            print(f"❌ FAILED - No ticker data returned")
            return False
            
    except AttributeError as e:
        print(f"❌ METHOD ERROR: {e}")
        print("   This method may not exist in DeltaClient")
        return False
    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
        return False


def test_get_order():
    """Test get_order() method with correct signature"""
    print("\n" + "="*80)
    print("TEST 2: get_order(order_id)")
    print("="*80)
    
    try:
        client = DeltaClient()
        
        # We need a real order_id to test, let's get open orders first
        print(f"\n📋 Getting open orders to test with...")
        
        # Get open orders for BTCUSD
        response = client.list_orders(product_id=27, state='open')
        orders = response.get('result', []) if isinstance(response, dict) else []
        
        if orders and len(orders) > 0:
            test_order = orders[0]
            order_id = test_order.get('id')
            
            print(f"✅ Found test order: {order_id}")
            print(f"   - Symbol: {test_order.get('product_symbol', 'N/A')}")
            print(f"   - Side: {test_order.get('side', 'N/A')}")
            print(f"   - Price: ${test_order.get('limit_price', 'N/A')}")
            
            # Now test get_order with ONLY order_id (no product_id)
            print(f"\n🔍 Testing: get_order({order_id})")
            
            start_time = time.time()
            order = client.get_order(order_id)
            elapsed = (time.time() - start_time) * 1000
            
            if order:
                print(f"✅ SUCCESS - Retrieved order in {elapsed:.0f}ms")
                print(f"\nOrder Data:")
                print(f"  - Order ID: {order.get('id', 'N/A')}")
                print(f"  - State: {order.get('state', 'N/A')}")
                print(f"  - Side: {order.get('side', 'N/A')}")
                print(f"  - Size: {order.get('size', 'N/A')}")
                print(f"  - Unfilled: {order.get('unfilled_size', 'N/A')}")
                
                # Check required fields
                required_fields = ['state', 'size', 'average_fill_price', 'limit_price']
                all_present = True
                for field in required_fields:
                    if field in order:
                        print(f"  ✅ Field '{field}': {order[field]}")
                    else:
                        print(f"  ⚠️  Field '{field}': Not present (optional)")
                
                return True
            else:
                print(f"❌ FAILED - No order data returned")
                return False
        else:
            print(f"⚠️  No open orders found to test with")
            print(f"   This is OK - testing with mock order_id")
            
            # Test with fake order_id to see method signature
            print(f"\n🔍 Testing: get_order(999999999) [fake ID]")
            try:
                order = client.get_order(999999999)
                print(f"   Response: {order}")
                return True
            except TypeError as e:
                if "positional argument" in str(e):
                    print(f"❌ SIGNATURE ERROR: {e}")
                    print(f"   The method signature is WRONG in our code!")
                    return False
                raise
            
    except AttributeError as e:
        print(f"❌ METHOD ERROR: {e}")
        return False
    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_old_methods():
    """Test the OLD incorrect methods to confirm they don't exist"""
    print("\n" + "="*80)
    print("TEST 3: Verify OLD methods don't exist")
    print("="*80)
    
    client = DeltaClient()
    
    # Test 1: get_ticker(symbol) - OLD WRONG METHOD
    print(f"\n🔍 Testing: get_ticker('BTCUSD') [OLD METHOD]")
    if hasattr(client, 'get_ticker'):
        print(f"⚠️  WARNING: get_ticker() method exists!")
        try:
            result = client.get_ticker('BTCUSD')
            print(f"   Unexpected success: {result}")
        except Exception as e:
            print(f"   Raises: {type(e).__name__}: {e}")
    else:
        print(f"✅ CORRECT: get_ticker() method does not exist")
    
    # Test 2: Check if get_order takes 2 arguments
    print(f"\n🔍 Checking: get_order() signature")
    import inspect
    sig = inspect.signature(client.get_order)
    params = list(sig.parameters.keys())
    print(f"   Parameters: {params}")
    if len(params) == 1 or (len(params) == 2 and params[1] == 'self'):
        print(f"✅ CORRECT: get_order() takes 1 argument (order_id)")
    else:
        print(f"⚠️  WARNING: get_order() takes {len(params)} arguments: {params}")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("DELTA EXCHANGE REST API TEST SUITE")
    print("="*80)
    print("Testing methods used in gridbot.py REST fallback")
    
    results = {}
    
    # Test 1: Ticker
    results['ticker'] = test_get_ticker_by_product_id()
    
    # Test 2: Orders
    results['orders'] = test_get_order()
    
    # Test 3: Old methods
    test_old_methods()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED - REST API methods are correct!")
        print("   The fixes in gridbot.py should work.")
    else:
        print("\n❌ SOME TESTS FAILED - Review the errors above")
        print("   May need to adjust the fixes.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
