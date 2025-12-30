#!/usr/bin/env python3
"""
ETH Product ID Verification Script
Queries Delta Exchange India API to verify ETHUSD product ID
"""

import requests
import json
import sys

def get_eth_product_id():
    """Query Delta Exchange API for ETHUSD product ID"""
    print("🔍 Querying Delta Exchange India API for ETH products...\n")
    
    url = "https://api.india.delta.exchange/v2/products"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        products = response.json()['result']
        
        # Find ETH products
        eth_products = [
            p for p in products 
            if 'ETH' in p['symbol'].upper() and 'USD' in p['symbol'].upper()
        ]
        
        if not eth_products:
            print("❌ No ETH products found!")
            return None
        
        print("📊 ETH Products on Delta Exchange India:")
        print("-" * 80)
        for p in eth_products:
            contract_type = p.get('contract_type', 'N/A')
            tick_size = p.get('tick_size', 'N/A')
            print(f"  Symbol: {p['symbol']:20} | ID: {str(p['id']):5} | Type: {contract_type:20} | Tick: {tick_size}")
        
        # Find perpetual futures
        eth_perp = next(
            (p for p in eth_products if p.get('contract_type') == 'perpetual_futures'),
            None
        )
        
        if eth_perp:
            print("\n" + "=" * 80)
            print(f"✅ ETHUSD Perpetual Found:")
            print(f"   Product ID: {eth_perp['id']}")
            print(f"   Symbol: {eth_perp['symbol']}")
            print(f"   Contract Type: {eth_perp['contract_type']}")
            print(f"   Tick Size: {eth_perp.get('tick_size', 'N/A')}")
            print(f"   Quote Currency: {eth_perp.get('quoting_asset', {}).get('symbol', 'N/A')}")
            print("=" * 80)
            print(f"\n⚠️  UPDATE config.yaml with: product_id: {eth_perp['id']}")
            print(f"   And tick_size: {eth_perp.get('tick_size', 'N/A')}")
            return eth_perp
        else:
            print("\n❌ ETHUSD perpetual futures not found!")
            print("   Available contract types:", set(p.get('contract_type') for p in eth_products))
            print("   Check Delta Exchange India product list manually.")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error querying API: {e}")
        print("   Check internet connection or try again later.")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        print(f"\n❌ Error parsing API response: {e}")
        return None

if __name__ == "__main__":
    print("=" * 80)
    print("ETH Product ID Verification for Delta Exchange India")
    print("=" * 80)
    print()
    
    eth_product = get_eth_product_id()
    
    if eth_product:
        print(f"\n✅ Success! Use product_id: {eth_product['id']} in config.yaml")
        print("\nNext steps:")
        print("  1. Update config.yaml symbols.ETHUSD.product_id")
        print(f"  2. Update config.yaml symbols.ETHUSD.grid.behavior.tick_size: {eth_product.get('tick_size', '0.05')}")
        print("  3. Proceed with Phase 1A configuration changes")
        sys.exit(0)
    else:
        print("\n❌ Failed to verify ETH product ID. Check manually at:")
        print("   https://www.delta.exchange/app/products")
        print("   Or contact Delta Exchange support.")
        sys.exit(1)
