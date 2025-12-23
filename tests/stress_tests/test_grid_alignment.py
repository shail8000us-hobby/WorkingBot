#!/usr/bin/env python3
"""
ST-3: Grid Alignment Stress Test

Validates all order prices are grid-aligned under stress.
100% VIRTUAL - Pure math calculations, no API calls.
"""

import random
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from bot.strategy.modules.grid_calculator import GridCalculator
from bot.strategy.modules.position_manager import PositionManager


def test_grid_alignment_stress(iterations=1000):
    """
    Run N iterations of:
    1. Random position creation
    2. Calculate next buy/sell level
    3. Validate grid alignment
    
    Tests FIX #2 (PositionManager validation) and FIX #3 (GridCalculator validation)
    """
    grid_calc = GridCalculator(
        lower=90000,
        upper=110000,
        step=300,
        ref=100000,
        tick_size=0.5
    )
    
    position_mgr = PositionManager(
        max_open=10,
        grid_calculator=grid_calc,
        session_tag="GRID_TEST"
    )
    
    off_grid_count = 0
    tested_buy_prices = []
    tested_sell_prices = []
    corrupted_position_caught = 0
    
    print(f"\n{'='*80}")
    print(f"GRID ALIGNMENT STRESS TEST")
    print(f"{'='*80}")
    print(f"Iterations: {iterations}")
    print(f"Grid: ${grid_calc.lower:,.0f} - ${grid_calc.upper:,.0f}, Step: ${grid_calc.step:,.0f}")
    print(f"Testing FIX #2 (Position validation) + FIX #3 (Calculator validation)...")
    
    for i in range(iterations):
        # Test BUY level calculation
        num_positions = random.randint(0, 5)
        positions = []
        
        for _ in range(num_positions):
            # Randomly create grid-aligned OR off-grid position (to test validation)
            if random.random() < 0.9:
                # 90% grid-aligned
                entry = grid_calc.lower + (random.randint(0, 60) * grid_calc.step)
            else:
                # 10% off-grid (corrupted) - should be caught by FIX #2 and FIX #3
                entry = grid_calc.lower + (random.randint(0, 60) * grid_calc.step) + random.uniform(1, 50)
                
            positions.append({'entry_price': entry})
        
        # Calculate next buy level (tests FIX #3)
        next_buy = grid_calc.compute_next_buy_level(positions)
        
        if next_buy is not None:
            tested_buy_prices.append(next_buy)
            
            # Validate grid alignment
            is_aligned = grid_calc.is_price_grid_aligned(next_buy)
            
            if not is_aligned:
                off_grid_count += 1
                print(f"\n❌ ITERATION {i+1}: OFF-GRID BUY PRICE ${next_buy:,.2f}")
                print(f"   Positions: {[p['entry_price'] for p in positions]}")
        
        # Test SELL level calculation
        next_sell = grid_calc.compute_next_sell_level(positions)
        
        if next_sell is not None:
            tested_sell_prices.append(next_sell)
            
            is_aligned = grid_calc.is_price_grid_aligned(next_sell)
            
            if not is_aligned:
                off_grid_count += 1
                print(f"\n❌ ITERATION {i+1}: OFF-GRID SELL PRICE ${next_sell:,.2f}")
                print(f"   Positions: {[p['entry_price'] for p in positions]}")
        
        # Test position manager validation (FIX #2)
        if positions:
            for pos in positions:
                original_price = pos['entry_price']
                
                # Add position through manager (should validate)
                position_mgr.add_position(pos)
                
                # Check if price was corrected
                added_price = pos['entry_price']
                if abs(added_price - original_price) > 0.01:
                    corrupted_position_caught += 1
    
    # Summary
    print(f"\n{'='*80}")
    print(f"RESULTS")
    print(f"{'='*80}")
    print(f"Iterations: {iterations}")
    print(f"BUY Prices Tested: {len(tested_buy_prices)}")
    print(f"SELL Prices Tested: {len(tested_sell_prices)}")
    print(f"Off-Grid Detected: {off_grid_count}")
    print(f"Corrupted Positions Caught by FIX #2: {corrupted_position_caught}")
    
    if off_grid_count > 0:
        print(f"\n❌ FAILURE: {off_grid_count} OFF-GRID PRICES")
        return False
    else:
        print(f"\n✅ SUCCESS: ALL {len(tested_buy_prices) + len(tested_sell_prices)} PRICES GRID-ALIGNED")
        if corrupted_position_caught > 0:
            print(f"✅ BONUS: FIX #2 caught and corrected {corrupted_position_caught} corrupted positions")
        return True


def main():
    """Run grid alignment stress test"""
    print(f"\n{'#'*80}")
    print(f"# ST-3: GRID ALIGNMENT STRESS TEST")
    print(f"# Tests FIX #2 (Position Validation) + FIX #3 (Calculator Validation)")
    print(f"# 100% VIRTUAL - Pure math, no API calls")
    print(f"{'#'*80}")
    
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--iterations', type=int, default=1000,
                        help='Number of test iterations (default: 1000)')
    args = parser.parse_args()
    
    success = test_grid_alignment_stress(args.iterations)
    
    if success:
        print(f"\n🎉 TEST PASSED - Grid alignment validation working")
        return 0
    else:
        print(f"\n❌ TEST FAILED - Review grid validation logic")
        return 1


if __name__ == '__main__':
    exit(main())
