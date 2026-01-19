#!/usr/bin/env python3
"""
0DTE System - API Integration Test
==================================

Tests the newly implemented API methods:
1. get_current_price() - Spot price fetching
2. get_option_chain() - Option chain fetching
3. get_option_ticker() - Option data

Run: python3 test_zero_dte_api.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bot.api.unified_api_client import UnifiedAPIClient
from datetime import datetime, timedelta
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")


async def test_zero_dte_api():
    """Test 0DTE API integration"""
    
    print("=" * 70)
    print("0DTE SYSTEM - API INTEGRATION TEST")
    print("=" * 70)
    print()
    
    # Load credentials from config
    try:
        from config import load_config
        cfg = load_config()
        api_key = cfg.delta.api_key
        api_secret = cfg.delta.api_secret
    except Exception as e:
        print(f"❌ Failed to load credentials: {e}")
        print("Using environment variables or manual input...")
        import os
        api_key = os.getenv('DELTA_API_KEY')
        api_secret = os.getenv('DELTA_API_SECRET')
        
        if not api_key or not api_secret:
            print("\n⚠️ No credentials found!")
            print("Set DELTA_API_KEY and DELTA_API_SECRET environment variables")
            return
    
    print(f"✅ Credentials loaded")
    print()
    
    # Initialize client
    print("Initializing UnifiedAPIClient...")
    client = UnifiedAPIClient(
        api_key=api_key,
        api_secret=api_secret,
        enable_websocket=False  # Not needed for testing
    )
    print("✅ Client initialized")
    print()
    
    # Test 1: Get Current Price
    print("-" * 70)
    print("TEST 1: get_current_price()")
    print("-" * 70)
    try:
        print("Fetching BTC spot price...")
        btc_price = await client.get_current_price('BTC')
        print(f"✅ BTC Price: ${btc_price:,.2f}")
        print()
        
        print("Fetching ETH spot price...")
        eth_price = await client.get_current_price('ETH')
        print(f"✅ ETH Price: ${eth_price:,.2f}")
        print()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Get Option Chain
    print("-" * 70)
    print("TEST 2: get_option_chain()")
    print("-" * 70)
    try:
        # Try tomorrow's expiry
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"Fetching BTC option chain for {tomorrow}...")
        
        chain = await client.get_option_chain('BTC', tomorrow)
        
        print(f"✅ Option chain loaded:")
        print(f"   - Calls: {len(chain['calls'])}")
        print(f"   - Puts: {len(chain['puts'])}")
        print()
        
        # Show sample data
        if chain['calls']:
            print("Sample Call Options:")
            for i, (strike, data) in enumerate(list(chain['calls'].items())[:3]):
                print(f"   {strike}: {data['symbol']} @ ₹{data['mark_price']:.2f}")
            print()
        
        if chain['puts']:
            print("Sample Put Options:")
            for i, (strike, data) in enumerate(list(chain['puts'].items())[:3]):
                print(f"   {strike}: {data['symbol']} @ ₹{data['mark_price']:.2f}")
            print()
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("⚠️ This may fail if there are no options expiring tomorrow")
        print("   Try checking Delta Exchange for available expiry dates")
        return
    
    # Test 3: Get Option Ticker
    print("-" * 70)
    print("TEST 3: get_option_ticker()")
    print("-" * 70)
    try:
        if chain['calls']:
            first_call = list(chain['calls'].values())[0]
            symbol = first_call['symbol']
            
            print(f"Fetching ticker for {symbol}...")
            ticker = await client.get_option_ticker(symbol)
            
            print(f"✅ Ticker data:")
            print(f"   Symbol: {symbol}")
            print(f"   Mark Price: ₹{ticker.get('mark_price', 0):.2f}")
            print(f"   Spot Price: ${ticker.get('spot_price', 0):.2f}")
            print(f"   Volume: {ticker.get('volume', 0)}")
            print(f"   OI: {ticker.get('oi', 0)}")
            
            quotes = ticker.get('quotes', {})
            if quotes:
                print(f"   Best Bid: ₹{quotes.get('best_bid', 0):.2f}")
                print(f"   Best Ask: ₹{quotes.get('best_ask', 0):.2f}")
            
            greeks = ticker.get('greeks', {})
            if greeks:
                print(f"   Delta: {greeks.get('delta', 0):.4f}")
                print(f"   Gamma: {greeks.get('gamma', 0):.4f}")
            print()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print("✅ get_current_price() - WORKING")
    print("✅ get_option_chain() - WORKING")
    print("✅ get_option_ticker() - WORKING")
    print()
    print("🎉 All API integration tests passed!")
    print()
    print("Next step: Test session start with:")
    print("  curl -X POST http://localhost:5555/api/zero-dte/session/start \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"underlying\":\"BTC\",\"skip_time_check\":true,\"initial_lots\":1}'")
    print()


if __name__ == '__main__':
    try:
        asyncio.run(test_zero_dte_api())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
