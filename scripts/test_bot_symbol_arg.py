#!/usr/bin/env python3
"""
Test AsyncGridBot symbol argument parsing (v5.0)
"""

import sys
sys.path.insert(0, '/Users/ssr/Projects/WorkingBot')

from config.loader import get_config
from config.models import RootConfig

def test_symbol_argument():
    """Test that symbol argument validation works."""
    
    # Test 1: Load config
    print("=" * 60)
    print("TEST 1: Load config")
    print("=" * 60)
    
    config = get_config()
    print(f"✅ Config loaded")
    print(f"   Config version: {config.version}")
    print(f"   Trading mode: {config.trading_mode}")
    
    if config.symbols:
        print(f"   Symbols available: {list(config.symbols.keys())}")
        for symbol_name, symbol_config in config.symbols.items():
            print(f"      {symbol_name}: enabled={symbol_config.enabled}, product_id={symbol_config.product_id}")
    else:
        print(f"   ⚠️  No symbols section (v4.0 config)")
    
    # Test 2: Validate symbol exists
    print("\n" + "=" * 60)
    print("TEST 2: Validate symbol argument")
    print("=" * 60)
    
    test_symbols = ['BTCUSD', 'ETHUSD', 'INVALID']
    
    for symbol_name in test_symbols:
        if not config.symbols:
            print(f"   ❌ {symbol_name}: No symbols section in config")
            continue
        
        if symbol_name not in config.symbols:
            available = list(config.symbols.keys())
            print(f"   ❌ {symbol_name}: Not found in config")
            print(f"      Available: {available}")
            continue
        
        symbol_config = config.symbols[symbol_name]
        
        if not symbol_config.enabled:
            print(f"   ⚠️  {symbol_name}: Found but disabled")
            continue
        
        print(f"   ✅ {symbol_name}: Valid and enabled")
        print(f"      Product ID: {symbol_config.product_id}")
        print(f"      Mode: {symbol_config.mode}")
    
    # Test 3: Constructor parameter preview
    print("\n" + "=" * 60)
    print("TEST 3: Constructor parameter preview")
    print("=" * 60)
    
    if config.symbols and 'BTCUSD' in config.symbols:
        symbol_config = config.symbols['BTCUSD']
        print(f"   Symbol: BTCUSD")
        print(f"   Product ID: {symbol_config.product_id}")
        print(f"   Mode: {symbol_config.mode}")
        print(f"   Lower: {symbol_config.grid.geometry.lower}")
        print(f"   Upper: {symbol_config.grid.geometry.upper}")
        print(f"   Step: {symbol_config.grid.geometry.step}")
        print(f"   Reference: {symbol_config.grid.geometry.reference}")
        print(f"   Max positions: {symbol_config.grid.limits.max_open_positions}")
        print(f"   Lot size: {symbol_config.grid.limits.lot_size}")
        print(f"   Strict grid: {symbol_config.grid.behavior.strict_grid}")
        print(f"   Database: data/bot_events_BTCUSD_{symbol_config.mode}.db")
    
    print("\n" + "=" * 60)
    print("✅ All tests completed")
    print("=" * 60)


if __name__ == "__main__":
    test_symbol_argument()
