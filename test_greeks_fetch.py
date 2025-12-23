#!/usr/bin/env python3
"""
Test script to fetch Greeks (delta, vega, theta) from Delta Exchange API
"""
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from bot.api.delta_client import DeltaClient
from config.loader import get_config

def main():
    print("=" * 80)
    print("Testing Delta Exchange API - Greeks Fetch")
    print("=" * 80)
    
    # Initialize client
    client = DeltaClient()
    
    # Test 1: /v2/positions/margined
    print("\n📊 Test 1: GET /v2/positions/margined")
    print("-" * 80)
    try:
        response = client._req('GET', '/v2/positions/margined')
        
        if response.get('success'):
            positions = response.get('result', [])
            print(f"✅ Success! Found {len(positions)} positions")
            
            for i, pos in enumerate(positions, 1):
                size = pos.get('size', 0)
                if size == 0:
                    continue
                
                print(f"\n📍 Position {i}:")
                print(f"   Symbol: {pos.get('product_symbol', 'N/A')}")
                print(f"   Product ID: {pos.get('product_id', 'N/A')}")
                print(f"   Size: {size}")
                print(f"   Entry Price: ${pos.get('entry_price', 0):,.2f}")
                print(f"   Mark Price: ${pos.get('mark_price', 0):,.2f}")
                
                # Check for Greeks
                print(f"\n   Greeks in response:")
                print(f"   - delta: {pos.get('delta', 'NOT FOUND')}")
                print(f"   - vega: {pos.get('vega', 'NOT FOUND')}")
                print(f"   - theta: {pos.get('theta', 'NOT FOUND')}")
                print(f"   - gamma: {pos.get('gamma', 'NOT FOUND')}")
                
                # Show all available keys
                print(f"\n   All available keys in position:")
                print(f"   {list(pos.keys())}")
                
                # Show full position data
                print(f"\n   Full position data:")
                print(json.dumps(pos, indent=4))
        else:
            print(f"❌ API returned unsuccessful: {response}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: /v2/positions (without margined)
    print("\n" + "=" * 80)
    print("📊 Test 2: GET /v2/positions")
    print("-" * 80)
    try:
        response = client._req('GET', '/v2/positions')
        
        if response.get('success'):
            positions = response.get('result', [])
            print(f"✅ Success! Found {len(positions)} positions")
            
            for i, pos in enumerate(positions, 1):
                size = pos.get('size', 0)
                if size == 0:
                    continue
                
                print(f"\n📍 Position {i}:")
                print(f"   Symbol: {pos.get('product_symbol', 'N/A')}")
                print(f"   Greeks: delta={pos.get('delta', 'N/A')}, vega={pos.get('vega', 'N/A')}, theta={pos.get('theta', 'N/A')}")
        else:
            print(f"❌ API returned unsuccessful: {response}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Check if we need a different endpoint for Greeks
    print("\n" + "=" * 80)
    print("📊 Test 3: Checking product details for Greeks")
    print("-" * 80)
    try:
        # Get first position's product_id
        response = client._req('GET', '/v2/positions/margined')
        if response.get('success'):
            positions = response.get('result', [])
            if positions:
                product_id = positions[0].get('product_id')
                print(f"Fetching product details for product_id: {product_id}")
                
                # Try to get product details
                product_response = client._req('GET', f'/v2/products/{product_id}')
                if product_response.get('success'):
                    product = product_response.get('result', {})
                    print(f"\n✅ Product details:")
                    print(json.dumps(product, indent=4))
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("Test Complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()
