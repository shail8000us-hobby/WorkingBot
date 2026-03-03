#!/usr/bin/env python3
"""Test Delta Exchange REST API ticker endpoint"""

import os
import sys

# Add bot directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.api.delta_client import DeltaClient

def main():
    print("=== DELTA EXCHANGE REST API TEST ===\n")
    
    client = DeltaClient()
    
    print("Fetching BTCUSD ticker (product_id=27)...")
    ticker = client.get_ticker_by_product_id(27)
    
    if not ticker:
        print("❌ Failed to get ticker data")
        return
    
    print("\n📊 Ticker Data:")
    print(f"  mark_price: {ticker.get('mark_price')}")
    print(f"  close: {ticker.get('close')}")
    print(f"  spot_price: {ticker.get('spot_price')}")
    print(f"  last_price: {ticker.get('last_price')}")
    print(f"  open: {ticker.get('open')}")
    print(f"  high: {ticker.get('high')}")
    print(f"  low: {ticker.get('low')}")
    
    print("\n✅ Full response:")
    import json
    print(json.dumps(ticker, indent=2))

if __name__ == "__main__":
    main()
