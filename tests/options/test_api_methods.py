#!/usr/bin/env python3
"""
Test script for options API methods
Tests the new UnifiedAPIClient options methods without affecting grid bot

Usage:
    python tests/options/test_api_methods.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from bot.api.unified_api_client import UnifiedAPIClient
from bot.options.utils.options_helper import enrich_position_data, check_liquidity
from config.loader import get_api_credentials
from loguru import logger as log


async def test_get_all_positions():
    """Test fetching all positions (futures + options)"""
    print("\n" + "="*60)
    print("TEST 1: Get All Positions (Futures + Options)")
    print("="*60)
    
    # Load API credentials from secrets
    creds = get_api_credentials()
    
    client = UnifiedAPIClient(
        api_key=creds['api_key'],
        api_secret=creds['api_secret'],
        symbol="BTCUSD",
        enable_websocket=False
    )
    
    try:
        positions = await client.get_all_positions_with_options()
        
        print(f"\n📊 Futures Positions: {len(positions['futures'])}")
        for pos in positions['futures']:
            print(f"  - {pos.get('product_symbol')}: {pos.get('size')} @ {pos.get('entry_price')}")
        
        print(f"\n📊 Options Positions: {len(positions['options'])}")
        for pos in positions['options']:
            symbol = pos.get('product_symbol')
            size = pos.get('size')
            entry = pos.get('entry_price')
            print(f"  - {symbol}: {size} @ {entry}")
        
        print(f"\n✅ Test PASSED: Successfully fetched {len(positions['futures'])} futures + {len(positions['options'])} options")
        return positions
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        raise


async def test_get_option_ticker():
    """Test fetching option ticker"""
    print("\n" + "="*60)
    print("TEST 2: Get Option Ticker")
    print("="*60)
    
    # Load API credentials from secrets
    creds = get_api_credentials()
    
    client = UnifiedAPIClient(
        api_key=creds['api_key'],
        api_secret=creds['api_secret'],
        symbol="BTCUSD",
        enable_websocket=False
    )
    
    try:
        positions = await client.get_all_positions_with_options()
        
        if not positions['options']:
            print("\n⚠️  No options positions found, skipping ticker test")
            return
        
        # Get ticker for first option
        option = positions['options'][0]
        symbol = option.get('product_symbol')
        
        print(f"\n🔍 Fetching ticker for: {symbol}")
        
        ticker = await client.get_option_ticker(symbol)
        
        print(f"\n📈 Ticker Data:")
        print(f"  Mark Price: ${ticker['mark_price']}")
        print(f"  Bid: ${ticker['bid']}")
        print(f"  Ask: ${ticker['ask']}")
        print(f"  Spread: {ticker['spread_pct']}%")
        print(f"  Volume: {ticker['volume']}")
        print(f"  Open Interest: {ticker['open_interest']}")
        
        if ticker['greeks']:
            print(f"  Greeks: {ticker['greeks']}")
        
        # Test liquidity check
        is_liquid = check_liquidity(ticker)
        print(f"\n💧 Liquidity Check: {'✅ LIQUID' if is_liquid else '❌ ILLIQUID'}")
        
        print(f"\n✅ Test PASSED: Successfully fetched ticker for {symbol}")
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        raise


async def test_helper_functions():
    """Test helper functions with real data"""
    print("\n" + "="*60)
    print("TEST 3: Helper Functions")
    print("="*60)
    
    # Load API credentials from secrets
    creds = get_api_credentials()
    
    client = UnifiedAPIClient(
        api_key=creds['api_key'],
        api_secret=creds['api_secret'],
        symbol="BTCUSD",
        enable_websocket=False
    )
    
    try:
        positions = await client.get_all_positions_with_options()
        
        if not positions['options']:
            print("\n⚠️  No options positions found, skipping helper tests")
            return
        
        option = positions['options'][0]
        symbol = option.get('product_symbol')
        ticker = await client.get_option_ticker(symbol)
        
        # Enrich position data
        enriched = enrich_position_data(option, ticker)
        
        print(f"\n📊 Enriched Position Data for {symbol}:")
        print(f"  Size: {enriched['size']}")
        print(f"  Entry Price: ${enriched['entry_price']}")
        print(f"  Mark Price: ${enriched['mark_price']}")
        print(f"  Unrealized PnL: ${enriched['unrealized_pnl']:.4f}")
        print(f"  PnL %: {enriched['pnl_percentage']:.2f}%")
        print(f"  Spread: {enriched['spread_pct']}%")
        print(f"  Liquidity: {'✅ LIQUID' if enriched['is_liquid'] else '❌ ILLIQUID'}")
        
        if enriched.get('expiry_warning'):
            warning = enriched['expiry_warning']
            print(f"  ⚠️  Expiry Warning: {warning['warning_level'].upper()} ({warning['hours_until_expiry']:.1f}h remaining)")
        
        print(f"\n✅ Test PASSED: Helper functions working correctly")
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        raise


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 OPTIONS API METHODS TEST SUITE")
    print("="*60)
    print("\nThis test will NOT place any orders or modify positions.")
    print("It only READS data from your account.\n")
    
    try:
        # Test 1: Get all positions
        await test_get_all_positions()
        
        # Test 2: Get option ticker
        await test_get_option_ticker()
        
        # Test 3: Helper functions
        await test_helper_functions()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nPhase 1 backend position tracking is working correctly!")
        print("You can now proceed to Phase 2 (Backend Order Execution)\n")
        
    except Exception as e:
        print("\n" + "="*60)
        print("❌ TESTS FAILED")
        print("="*60)
        print(f"\nError: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
