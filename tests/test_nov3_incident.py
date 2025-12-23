"""
Test Case for November 3, 2025 Incident
Ensures grid alignment validation prevents misaligned orders
"""
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import pytest
import threading
from bot.strategy.modules.order_manager import OrderManager
from bot.strategy.modules.grid_calculator import GridCalculator


class MockAPIClient:
    """Mock API client for testing"""
    def place_order(self, *args, **kwargs):
        return {'success': True, 'result': {'id': 'TEST123'}}
    
    def cancel_order(self, *args, **kwargs):
        return {'success': True}
    
    def get_order(self, *args, **kwargs):
        return {'success': True, 'result': {'status': 'cancelled'}}
    
    def list_orders(self, *args, **kwargs):
        return {'success': True, 'result': []}


class MockPositionManager:
    """Mock position manager for testing"""
    def __init__(self):
        self.state_lock = threading.RLock()
        self.open_tranches = []


def test_grid_alignment_validator():
    """
    Test that non-grid prices are rejected
    
    This test reproduces the November 3 incident where orders
    were placed at 106,375.5 and 107,291.5 instead of grid levels.
    """
    print("\n" + "=" * 80)
    print("🧪 TESTING: Grid Alignment Validator (November 3 Incident)")
    print("=" * 80)
    
    # Setup grid calculator with actual production config
    grid_calc = GridCalculator(
        lower=105000,   # Actual config from Nov 3
        upper=110000,   # Actual config from Nov 3
        step=1000,      # Actual config from Nov 3
        ref=109000,     # Actual config from Nov 3
        tick_size=0.5
    )
    
    # Create order manager
    order_mgr = OrderManager(
        api_client=MockAPIClient(),
        grid_calculator=grid_calc,
        position_manager=MockPositionManager(),
        product_id=27,
        lot_size=1,
        tick_size=0.5
    )
    
    print("\n📊 Grid Configuration:")
    print(f"   Lower: 105,000")
    print(f"   Upper: 110,000")
    print(f"   Step: 1,000")
    print(f"   Valid Levels: 105k, 106k, 107k, 108k, 109k, 110k")
    
    # Test 1: Valid grid prices (should pass)
    print("\n✅ Testing VALID grid prices:")
    valid_prices = [105000.0, 106000.0, 107000.0, 108000.0, 109000.0, 110000.0]
    for price in valid_prices:
        result = order_mgr._is_price_grid_aligned(price)
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: ${price:,.0f} → {result}")
        assert result == True, f"Valid price {price} should be accepted"
    
    # Test 2: Invalid prices from Nov 3 incident (should fail)
    print("\n❌ Testing INVALID prices (Nov 3 Incident):")
    invalid_prices = [
        (106375.5, "Actual incident price #1"),
        (107291.5, "Actual incident price #2"),
        (106500.0, "Mid-grid price"),
        (107123.5, "Random market price"),
        (105250.0, "Quarter-step"),
        (108750.0, "Three-quarter step")
    ]
    
    for price, description in invalid_prices:
        result = order_mgr._is_price_grid_aligned(price)
        status = "✅ PASS" if not result else "❌ FAIL"
        print(f"   {status}: ${price:,.1f} → {result} ({description})")
        assert result == False, f"Invalid price {price} should be rejected"
    
    # Test 3: Edge cases
    print("\n🔍 Testing EDGE cases:")
    edge_cases = [
        (105000.5, "Tick size tolerance", True),   # Within tick tolerance
        (105999.5, "Tick size tolerance", True),   # Within tick tolerance
        (105500.0, "Exact mid-point", False),      # Should fail
        (0.0, "Zero price", False),                # Should fail (caught by price validation)
        (-1000.0, "Negative price", False)         # Should fail (caught by price validation)
    ]
    
    for price, description, expected in edge_cases:
        if price <= 0:
            # These are caught by price validation, not grid alignment
            print(f"   ⏭️  SKIP: ${price:,.1f} ({description}) - caught by price validation")
        else:
            result = order_mgr._is_price_grid_aligned(price)
            status = "✅ PASS" if result == expected else "❌ FAIL"
            print(f"   {status}: ${price:,.1f} → {result} (expected: {expected}) - {description}")
            assert result == expected, f"Edge case {price} failed"
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print("\n🎯 KEY FINDINGS:")
    print("   ✅ Grid alignment validator working correctly")
    print("   ✅ NOV 3 incident prices (106,375.5, 107,291.5) would be REJECTED")
    print("   ✅ All valid grid prices (105k-110k) are accepted")
    print("   ✅ All invalid prices are rejected")
    print("\n💡 This validator prevents the November 3 incident from recurring!")
    print()


def test_valid_grid_levels_list():
    """Test that get_valid_grid_levels returns correct levels"""
    print("\n" + "=" * 80)
    print("🧪 TESTING: Valid Grid Levels List")
    print("=" * 80)
    
    grid_calc = GridCalculator(
        lower=105000,
        upper=110000,
        step=1000,
        ref=109000,
        tick_size=0.5
    )
    
    order_mgr = OrderManager(
        api_client=MockAPIClient(),
        grid_calculator=grid_calc,
        position_manager=MockPositionManager(),
        product_id=27,
        lot_size=1,
        tick_size=0.5
    )
    
    levels = order_mgr._get_valid_grid_levels()
    
    print(f"\n📊 Valid Grid Levels: {levels}")
    
    expected_levels = ['$105,000', '$106,000', '$107,000', '$108,000', '$109,000', '$110,000']
    
    assert levels == expected_levels, f"Expected {expected_levels}, got {levels}"
    assert len(levels) == 6, "Should have 6 grid levels"
    
    print("✅ Valid grid levels list is correct!")
    print()


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("🔬 NOVEMBER 3 INCIDENT - REGRESSION TEST SUITE")
    print("=" * 80)
    print("\nThis test ensures the Nov 3 incident cannot happen again.")
    print("It validates that:")
    print("  1. Grid alignment validator rejects market prices")
    print("  2. Only grid-aligned prices are accepted")
    print("  3. Valid grid levels are correctly calculated")
    print()
    
    try:
        test_grid_alignment_validator()
        test_valid_grid_levels_list()
        
        print("\n" + "=" * 80)
        print("🎉 ALL NOV 3 INCIDENT TESTS PASSED!")
        print("=" * 80)
        print("\n✅ Grid alignment validator is working correctly")
        print("✅ Bot will reject orders at 106,375.5, 107,291.5, etc.")
        print("✅ Only grid-aligned orders (105k, 106k, 107k, etc.) will be accepted")
        print("\n🛡️ November 3 incident CANNOT RECUR with these fixes!")
        print()
        
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


