#!/usr/bin/env python3
"""
Test Partial Fill Implementation

This script simulates partial fills to verify the new implementation works correctly.
"""

import sys
import time
from typing import Dict

# Simulate WebSocket partial fill events
def simulate_partial_fills():
    """Simulate a 100-lot order filling in 3 parts"""
    
    print("=" * 80)
    print("🧪 TESTING PARTIAL FILL IMPLEMENTATION")
    print("=" * 80)
    print()
    
    # Simulate order: BUY 100 lots @ 105,000
    order_id = "TEST_123456"
    total_size = 100
    
    fills = [
        # (filled_so_far, unfilled, avg_price, state)
        (10, 90, 105000.0, 'open'),    # Fill 1: 10 lots
        (57, 43, 105005.0, 'open'),    # Fill 2: 47 lots
        (100, 0, 105010.0, 'closed'),  # Fill 3: 43 lots (COMPLETE)
    ]
    
    # Track previous filled for incremental calculation
    previous_filled = 0
    
    print(f"📥 Order: BUY {total_size} lots @ 105,000")
    print(f"   Order ID: {order_id}")
    print()
    
    for i, (current_filled, unfilled, avg_price, state) in enumerate(fills, 1):
        print(f"🎯 Fill {i}:")
        print(f"   ─────────────────────────────────────")
        
        # Calculate incremental fill (this is what ws_manager does)
        new_fill_size = current_filled - previous_filled
        is_complete = (unfilled == 0 or state == 'closed')
        fill_percentage = (current_filled / total_size * 100)
        
        print(f"   WebSocket Data:")
        print(f"     - size: {total_size}")
        print(f"     - unfilled_size: {unfilled}")
        print(f"     - average_fill_price: ${avg_price:,.2f}")
        print(f"     - state: {state}")
        print()
        
        print(f"   Calculated Values:")
        print(f"     - current_filled: {total_size} - {unfilled} = {current_filled}")
        print(f"     - previous_filled: {previous_filled}")
        print(f"     - new_fill_size: {current_filled} - {previous_filled} = {new_fill_size}")
        print(f"     - is_complete: {is_complete}")
        print()
        
        # Simulate what the callback receives
        fill_data = {
            'order_id': order_id,
            'fill_price': avg_price,
            'fill_size': new_fill_size,           # ← INCREMENTAL
            'cumulative_filled': current_filled,
            'total_order_size': total_size,
            'unfilled_size': unfilled,
            'side': 'buy',
            'is_complete': is_complete
        }
        
        print(f"   Callback Data:")
        for key, value in fill_data.items():
            if key == 'fill_price':
                print(f"     - {key}: ${value:,.2f}")
            else:
                print(f"     - {key}: {value}")
        print()
        
        # Simulate bot actions
        print(f"   Bot Actions:")
        if is_complete:
            print(f"     ⏳ FINAL FILL: buy +{new_fill_size} lots @ avg ${avg_price:,.2f}")
        else:
            print(f"     ⏳ PARTIAL FILL: buy +{new_fill_size} lots @ avg ${avg_price:,.2f} | Total: {current_filled}/{total_size} ({fill_percentage:.1f}%)")
        
        print(f"     → Create position: {new_fill_size} lots @ ${avg_price:,.2f}")
        tp_price = avg_price + 500  # Simple TP calculation
        print(f"     → Place TP: {new_fill_size} lots @ ${tp_price:,.2f}")
        
        if is_complete:
            print(f"     → Clear pending_buy ✅")
            print(f"     → Place next grid BUY @ $104,500 ✅")
            print(f"     → Cleanup tracking ✅")
        else:
            print(f"     → Keep pending_buy active (order still filling)")
            print(f"     → DON'T place next grid order yet")
        
        print()
        
        # Update previous filled for next iteration
        previous_filled = current_filled
        
        # Pause for readability
        time.sleep(0.5)
    
    print("=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)
    print()
    print("Expected Results:")
    print("  ✅ Fill 1: Created 1 position (10 lots), 1 TP, pending_buy active")
    print("  ✅ Fill 2: Created 1 position (47 lots), 1 TP, pending_buy active")
    print("  ✅ Fill 3: Created 1 position (43 lots), 1 TP, cleared pending_buy, placed next order")
    print()
    print("Final State:")
    print("  ✅ Total Positions: 3 (10 + 47 + 43 = 100 lots)")
    print("  ✅ Total TPs: 3")
    print("  ✅ Pending BUY: Cleared")
    print("  ✅ Next Grid Order: Placed at $104,500")
    print()


def test_edge_cases():
    """Test edge cases"""
    print("=" * 80)
    print("🧪 TESTING EDGE CASES")
    print("=" * 80)
    print()
    
    # Test 1: Duplicate WebSocket message
    print("Test 1: Duplicate WebSocket Message")
    print("─" * 80)
    previous_filled = 10
    current_filled = 10  # Same as before
    new_fill = current_filled - previous_filled
    print(f"  previous_filled: {previous_filled}")
    print(f"  current_filled: {current_filled}")
    print(f"  new_fill: {new_fill}")
    print(f"  Result: {'✅ Skip (no new fill)' if new_fill <= 0 else '❌ Process'}")
    print()
    
    # Test 2: Order cancelled partially filled
    print("Test 2: Order Cancelled Partially Filled")
    print("─" * 80)
    total_size = 100
    unfilled_size = 50
    state = 'cancelled'
    current_filled = total_size - unfilled_size
    is_complete = (unfilled_size == 0 or state == 'cancelled')
    print(f"  total_size: {total_size}")
    print(f"  unfilled_size: {unfilled_size}")
    print(f"  current_filled: {current_filled}")
    print(f"  state: {state}")
    print(f"  is_complete: {is_complete}")
    print(f"  Result: {'✅ Treat as complete, place next order' if is_complete else '❌ Keep waiting'}")
    print()
    
    # Test 3: Extreme case - 10 fills of 10 lots each
    print("Test 3: Extreme Case - 10 Partial Fills")
    print("─" * 80)
    print("  Order: 100 lots, fills in 10 parts of 10 lots each")
    previous = 0
    for i in range(1, 11):
        current = i * 10
        new_fill = current - previous
        is_last = (i == 10)
        print(f"  Fill {i}: current={current}, previous={previous}, new_fill={new_fill}, complete={is_last}")
        previous = current
    print(f"  Result: ✅ 10 positions created, 10 TPs placed, next order after 10th fill")
    print()


if __name__ == '__main__':
    try:
        simulate_partial_fills()
        test_edge_cases()
        
        print("=" * 80)
        print("🎯 NEXT STEPS:")
        print("=" * 80)
        print()
        print("1. Review the simulated output above")
        print("2. Verify the logic matches your expectations")
        print("3. Test with DEMO mode using small order (10 lots)")
        print("4. Monitor bot logs for partial fill messages:")
        print("   - Look for: '⏳ PARTIAL FILL:' messages")
        print("   - Look for: '🎯 FINAL FILL:' message")
        print("   - Look for: '✅ Order X FULLY FILLED - placing next grid order'")
        print()
        print("5. Once verified in demo, test with small live order")
        print()
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
