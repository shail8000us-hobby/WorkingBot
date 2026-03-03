#!/usr/bin/env python3
"""
Test Strict Grid Implementation

This script verifies that the new strict grid functions work correctly.
"""

import sys
sys.path.insert(0, '/Users/ssr/Projects/WorkingBot')

from bot.strategy.modules.grid_calculator import GridCalculator

def test_find_nearest_grid_below():
    """Test find_nearest_grid_below function"""
    print("=" * 80)
    print("TEST 1: find_nearest_grid_below() and find_nearest_grid_above()")
    print("=" * 80)
    
    # Test case from documentation
    calc = GridCalculator(
        lower=800,
        upper=1500,
        step=10,
        ref=1000,
        tick_size=0.5
    )
    
    # Test BELOW (for LONG mode)
    result = calc.find_nearest_grid_below(960)
    print(f"Grid: 800-1500, Step: 10")
    print(f"find_nearest_grid_below(960) = {result}")
    print(f"Expected: 950")
    print(f"✅ PASS" if result == 950 else f"❌ FAIL")
    print()
    
    # Test edge case: price below grid
    result = calc.find_nearest_grid_below(790)
    print(f"find_nearest_grid_below(790) = {result}")
    print(f"Expected: None (price below grid)")
    print(f"✅ PASS" if result is None else f"❌ FAIL")
    print()
    
    # Test ABOVE (for SHORT mode)
    result = calc.find_nearest_grid_above(960)
    print(f"find_nearest_grid_above(960) = {result}")
    print(f"Expected: 970")
    print(f"✅ PASS" if result == 970 else f"❌ FAIL")
    print()
    
    # Test edge case: price above grid
    result = calc.find_nearest_grid_above(1510)
    print(f"find_nearest_grid_above(1510) = {result}")
    print(f"Expected: None (price above grid)")
    print(f"✅ PASS" if result is None else f"❌ FAIL")
    print()

def test_get_startup_maker_buy_level():
    """Test get_startup_maker_buy_level function (both LONG and SHORT modes)"""
    print("=" * 80)
    print("TEST 2: get_startup_maker_buy_level() - LONG & SHORT modes")
    print("=" * 80)
    
    # Test case from documentation
    calc = GridCalculator(
        lower=800,
        upper=1500,
        step=10,
        ref=1000,
        tick_size=0.5
    )
    
    print("--- LONG MODE TESTS ---")
    # Scenario: Market at 960, no positions, LONG mode
    current_price = 960
    positions = []
    
    result = calc.get_startup_maker_buy_level(current_price, positions, grid_mode='LONG')
    print(f"Grid: 800-1500, Step: 10, Ref: 1000")
    print(f"Market: {current_price}, No positions, Mode: LONG")
    print(f"Normal calculation would be: 1000 - 10 = 990")
    print(f"get_startup_maker_buy_level() = {result}")
    print(f"Expected: 950 (nearest grid level below market)")
    print(f"✅ PASS" if result == 950 else f"❌ FAIL")
    print()
    
    # Scenario: Calculated target already below market
    current_price = 1100
    result = calc.get_startup_maker_buy_level(current_price, positions, grid_mode='LONG')
    print(f"Market: {current_price}, No positions, Mode: LONG")
    print(f"Normal calculation: 1000 - 10 = 990")
    print(f"get_startup_maker_buy_level() = {result}")
    print(f"Expected: 990 (already below market, no adjustment)")
    print(f"✅ PASS" if result == 990 else f"❌ FAIL")
    print()
    
    print("--- SHORT MODE TESTS ---")
    # Scenario: Market at 1040, no positions, SHORT mode
    current_price = 1040
    result = calc.get_startup_maker_buy_level(current_price, positions, grid_mode='SHORT')
    print(f"Market: {current_price}, No positions, Mode: SHORT")
    print(f"Normal calculation: 1000 + 10 = 1010")
    print(f"get_startup_maker_buy_level() = {result}")
    print(f"Expected: 1050 (nearest grid level above market)")
    print(f"✅ PASS" if result == 1050 else f"❌ FAIL")
    print()
    
    # Scenario: Calculated target already above market
    current_price = 900
    result = calc.get_startup_maker_buy_level(current_price, positions, grid_mode='SHORT')
    print(f"Market: {current_price}, No positions, Mode: SHORT")
    print(f"Normal calculation: 1000 + 10 = 1010")
    print(f"get_startup_maker_buy_level() = {result}")
    print(f"Expected: 1010 (already above market, no adjustment)")
    print(f"✅ PASS" if result == 1010 else f"❌ FAIL")
    print()

def test_current_bot_config():
    """Test with current bot configuration (both LONG and SHORT modes)"""
    print("=" * 80)
    print("TEST 3: Current Bot Configuration - LONG & SHORT modes")
    print("=" * 80)
    
    # Current config from grid_config.env
    calc = GridCalculator(
        lower=95000,
        upper=110000,
        step=1000,
        ref=101000,
        tick_size=0.5
    )
    
    # Check if GRIDBOT_REF is aligned
    offset = (101000 - 95000) % 1000
    print(f"GRIDBOT_REF: 101000")
    print(f"GRIDBOT_LOWER: 95000")
    print(f"GRIDBOT_STEP: 1000")
    print(f"Offset: {offset}")
    print(f"✅ ALIGNED" if offset == 0 else f"❌ NOT ALIGNED")
    print()
    
    print("--- LONG MODE SCENARIOS ---")
    # Scenario: Market at 103,000
    current_price = 103000
    positions = []
    
    result = calc.get_startup_maker_buy_level(current_price, positions, grid_mode='LONG')
    print(f"Scenario: Market at ${current_price:,}, Mode: LONG")
    print(f"Normal calculation: 101000 - 1000 = 100000")
    print(f"Strict Grid result: ${result:,.0f}" if result else "None")
    print(f"Expected: $100,000 (already below market)")
    print(f"✅ PASS" if result == 100000 else f"❌ FAIL")
    print()
    
    # Scenario: Market at 99,500 (below ref)
    current_price = 99500
    result = calc.get_startup_maker_buy_level(current_price, positions, grid_mode='LONG')
    print(f"Scenario: Market at ${current_price:,}, Mode: LONG")
    print(f"Normal calculation: 101000 - 1000 = 100000")
    print(f"Strict Grid result: ${result:,.0f}" if result else "None")
    print(f"Expected: $99,000 (nearest grid below market)")
    print(f"✅ PASS" if result == 99000 else f"❌ FAIL")
    print()
    
    print("--- SHORT MODE SCENARIOS ---")
    # Scenario: Market at 99,500 (below ref)
    current_price = 99500
    result = calc.get_startup_maker_buy_level(current_price, positions, grid_mode='SHORT')
    print(f"Scenario: Market at ${current_price:,}, Mode: SHORT")
    print(f"Normal calculation: 101000 + 1000 = 102000")
    print(f"Strict Grid result: ${result:,.0f}" if result else "None")
    print(f"Expected: $102,000 (already above market)")
    print(f"✅ PASS" if result == 102000 else f"❌ FAIL")
    print()
    
    # Scenario: Market at 103,000 (above ref)
    current_price = 103000
    result = calc.get_startup_maker_buy_level(current_price, positions, grid_mode='SHORT')
    print(f"Scenario: Market at ${current_price:,}, Mode: SHORT")
    print(f"Normal calculation: 101000 + 1000 = 102000")
    print(f"Strict Grid result: ${result:,.0f}" if result else "None")
    print(f"Expected: $104,000 (nearest grid above market)")
    print(f"✅ PASS" if result == 104000 else f"❌ FAIL")
    print()

if __name__ == "__main__":
    test_find_nearest_grid_below()
    test_get_startup_maker_buy_level()
    test_current_bot_config()
    
    print("=" * 80)
    print("🎯 ALL TESTS COMPLETED")
    print("=" * 80)
