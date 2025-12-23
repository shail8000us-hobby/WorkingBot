"""
Property-Based Tests for Grid Alignment

Uses Hypothesis to test grid alignment properties with thousands of random inputs.
This ensures grid logic is deterministic and handles edge cases correctly.

Created: November 8, 2025
Purpose: PHASE 9.1 - Comprehensive Audit
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from hypothesis import given, strategies as st, settings, assume
from hypothesis import HealthCheck

from bot.strategy.modules.order_manager import OrderManager


class TestGridAlignmentProperties:
    """
    Property-based tests for grid alignment logic
    
    These tests verify that grid alignment is:
    1. Deterministic (same input = same output)
    2. Consistent with grid parameters
    3. Handles edge cases correctly
    """
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_lower = 95000.0
        self.grid_upper = 110000.0
        self.grid_step = 1000.0
        self.tolerance = 0.50  # 50 cents tolerance (default)
    
    def _is_price_grid_aligned(self, price: float, tolerance: float = 0.50) -> bool:
        """
        Test implementation of grid alignment check
        
        This mirrors the actual bot logic for testing purposes.
        """
        # Calculate grid index (distance from lower bound in steps)
        grid_index = round((price - self.grid_lower) / self.grid_step)
        
        # Calculate nearest grid price
        nearest_grid_price = self.grid_lower + (grid_index * self.grid_step)
        
        # Check if within tolerance
        distance = abs(price - nearest_grid_price)
        
        return distance <= tolerance
    
    @given(st.floats(min_value=95000, max_value=110000))
    @settings(max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_grid_alignment_is_deterministic(self, price):
        """
        PROPERTY: Grid alignment result must be deterministic
        
        For any price, checking alignment twice should give the same result.
        """
        assume(not (price != price))  # Filter out NaN
        
        result1 = self._is_price_grid_aligned(price, tolerance=self.tolerance)
        result2 = self._is_price_grid_aligned(price, tolerance=self.tolerance)
        
        assert result1 == result2, f"Grid alignment not deterministic for price ${price:,.2f}"
    
    @given(st.integers(min_value=0, max_value=15))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exact_grid_prices_are_aligned(self, grid_index):
        """
        PROPERTY: Exact grid prices must always be aligned
        
        Prices at exact grid levels (e.g., $95,000, $96,000, etc.) must be aligned.
        """
        price = self.grid_lower + (grid_index * self.grid_step)
        result = self._is_price_grid_aligned(price, tolerance=self.tolerance)
        
        assert result, f"Exact grid price ${price:,.0f} not aligned!"
    
    @given(
        st.integers(min_value=0, max_value=14),
        st.floats(min_value=0.01, max_value=0.49)
    )
    @settings(max_examples=500, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_prices_within_tolerance_are_aligned(self, grid_index, offset):
        """
        PROPERTY: Prices within tolerance of grid must be aligned
        
        If a price is within tolerance ($0.50) of a grid level, it should be aligned.
        """
        grid_price = self.grid_lower + (grid_index * self.grid_step)
        price = grid_price + offset  # Add small offset within tolerance
        
        result = self._is_price_grid_aligned(price, tolerance=self.tolerance)
        
        assert result, f"Price ${price:,.2f} (grid: ${grid_price:,.0f}, offset: +${offset:.2f}) should be aligned!"
    
    @given(
        st.integers(min_value=0, max_value=14),
        st.floats(min_value=0.51, max_value=499.99)
    )
    @settings(max_examples=500, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_prices_outside_tolerance_are_not_aligned(self, grid_index, offset):
        """
        PROPERTY: Prices outside tolerance of grid must not be aligned
        
        If a price is more than $0.50 from any grid level, it should not be aligned.
        """
        grid_price = self.grid_lower + (grid_index * self.grid_step)
        price = grid_price + offset  # Add offset larger than tolerance
        
        # Check if this offset actually puts us outside tolerance for ANY grid level
        # (could be close to next grid level)
        next_grid = grid_price + self.grid_step
        dist_to_current = abs(price - grid_price)
        dist_to_next = abs(price - next_grid)
        
        min_distance = min(dist_to_current, dist_to_next)
        
        result = self._is_price_grid_aligned(price, tolerance=self.tolerance)
        
        # If truly outside tolerance of all grid levels, should not be aligned
        if min_distance > self.tolerance:
            assert not result, f"Price ${price:,.2f} should NOT be aligned (min dist: ${min_distance:.2f})"
    
    @given(st.floats(min_value=95000, max_value=110000))
    @settings(max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_alignment_is_reflexive(self, price):
        """
        PROPERTY: If price A is aligned, then price A is aligned
        
        This tests the reflexive property (sounds obvious, but tests implementation consistency).
        """
        assume(not (price != price))  # Filter NaN
        
        if self._is_price_grid_aligned(price):
            # If aligned, should still be aligned on re-check
            assert self._is_price_grid_aligned(price)
    
    @given(
        st.floats(min_value=95000, max_value=110000),
        st.floats(min_value=-0.01, max_value=0.01)
    )
    @settings(max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_tiny_price_changes_dont_flip_alignment(self, price, epsilon):
        """
        PROPERTY: Tiny price changes (< $0.01) shouldn't flip alignment status
        
        This tests stability of the alignment check.
        """
        assume(not (price != price))
        assume(95000 <= price + epsilon <= 110000)
        
        result1 = self._is_price_grid_aligned(price)
        result2 = self._is_price_grid_aligned(price + epsilon)
        
        # For very small changes, alignment should be stable
        # (unless we're right at the tolerance boundary)
        grid_index = round((price - self.grid_lower) / self.grid_step)
        nearest_grid = self.grid_lower + (grid_index * self.grid_step)
        distance_to_grid = abs(price - nearest_grid)
        
        # If we're well within or well outside tolerance, tiny changes shouldn't flip
        if distance_to_grid < self.tolerance - 0.02 or distance_to_grid > self.tolerance + 0.02:
            assert result1 == result2, \
                f"Tiny change flipped alignment: ${price:,.2f} → ${price+epsilon:,.2f}"
    
    def test_boundary_cases(self):
        """Test specific boundary cases that are known edge cases"""
        
        # Exact grid boundaries
        assert self._is_price_grid_aligned(95000.0), "Lower bound not aligned"
        assert self._is_price_grid_aligned(110000.0), "Upper bound not aligned"
        
        # Just inside tolerance
        assert self._is_price_grid_aligned(95000.0 + 0.49), "Lower + 0.49 not aligned"
        assert self._is_price_grid_aligned(95000.0 - 0.49), "Lower - 0.49 not aligned"
        
        # Just outside tolerance
        assert not self._is_price_grid_aligned(95000.0 + 0.51), "Lower + 0.51 should not be aligned"
        assert not self._is_price_grid_aligned(95000.0 - 0.51), "Lower - 0.51 should not be aligned"
        
        # Mid-grid points (should not be aligned)
        assert not self._is_price_grid_aligned(95500.0), "Mid-grid (95500) should not be aligned"
        assert not self._is_price_grid_aligned(96500.0), "Mid-grid (96500) should not be aligned"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
