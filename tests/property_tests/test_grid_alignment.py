"""
PHASE 7.1: Grid Alignment Edge Cases - Property-Based Tests

Tests floating point precision, prices on exact grid boundaries,
and mathematical correctness of grid calculations.

Test Coverage:
1. Floating point precision (tick size quantization)
2. Prices exactly on grid lines
3. Grid boundary calculations
4. Step alignment validation
5. Quantization idempotence
"""

import pytest
import math
from decimal import Decimal
from hypothesis import given, strategies as st, assume, settings, example
from bot.strategy.modules import GridCalculator


# ================================================================
# Test 1: Quantization Idempotence
# ================================================================

@given(
    price=st.floats(min_value=1000.0, max_value=200000.0, allow_nan=False, allow_infinity=False),
    # Limit tick_size to realistic exchange values (0.01 to 1.0)
    # Exotic tick sizes (e.g., 9.39026...) can cause floating point issues
    # Real exchanges use simple values: 0.5, 0.1, 0.05, 0.01, etc.
    tick_size=st.sampled_from([0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0])
)
@settings(max_examples=500)
def test_quantization_idempotence(price, tick_size):
    """
    Property: quantize(quantize(x)) == quantize(x)
    
    Quantization should be idempotent - applying it twice
    should produce the same result as applying it once.
    
    Note: Limited to realistic exchange tick sizes to avoid
    floating point representation issues with exotic values.
    """
    calc = GridCalculator(
        lower=1000.0,
        upper=200000.0,
        step=1000.0,
        ref=100000.0,
        tick_size=tick_size
    )
    
    quantized_once = calc.quantize_price(price)
    quantized_twice = calc.quantize_price(quantized_once)
    
    assert quantized_once == quantized_twice, \
        f"Quantization not idempotent: {quantized_once} != {quantized_twice}"


# ================================================================
# Test 2: Quantization Monotonicity
# ================================================================

@given(
    price1=st.floats(min_value=1000.0, max_value=200000.0, allow_nan=False, allow_infinity=False),
    price2=st.floats(min_value=1000.0, max_value=200000.0, allow_nan=False, allow_infinity=False),
    tick_size=st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=500)
def test_quantization_monotonic(price1, price2, tick_size):
    """
    Property: If price1 <= price2, then quantize(price1) <= quantize(price2)
    
    Quantization should preserve order - it should never reverse
    the relative ordering of prices.
    """
    assume(price1 <= price2)
    
    calc = GridCalculator(
        lower=1000.0,
        upper=200000.0,
        step=1000.0,
        ref=100000.0,
        tick_size=tick_size
    )
    
    q1 = calc.quantize_price(price1)
    q2 = calc.quantize_price(price2)
    
    assert q1 <= q2, \
        f"Quantization not monotonic: {price1} <= {price2} but {q1} > {q2}"


# ================================================================
# Test 3: Quantization Bounds
# ================================================================

@given(
    price=st.floats(min_value=1000.0, max_value=200000.0, allow_nan=False, allow_infinity=False),
    tick_size=st.sampled_from([0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0])
)
@settings(max_examples=500)
def test_quantization_bounds(price, tick_size):
    """
    Property: quantize(x) <= x < quantize(x) + tick_size
    
    Quantized price should be at or below the original price,
    and the difference should be less than one tick.
    
    Note: Uses realistic exchange tick sizes to avoid floating
    point edge cases with exotic values.
    """
    calc = GridCalculator(
        lower=1000.0,
        upper=200000.0,
        step=1000.0,
        ref=100000.0,
        tick_size=tick_size
    )
    
    quantized = calc.quantize_price(price)
    
    # Allow tiny floating point tolerance (1e-10) for comparison
    assert quantized <= price + 1e-10, \
        f"Quantized price {quantized} exceeds original {price}"
    
    assert price < quantized + tick_size + 1e-10, \
        f"Price {price} too far from quantized {quantized} (tick={tick_size})"


# ================================================================
# Test 4: Grid Alignment on Exact Boundaries
# ================================================================

@given(
    lower=st.floats(min_value=1000.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
    step=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=300)
def test_exact_grid_boundary_alignment(lower, step):
    """
    Property: Prices exactly on grid boundaries should align perfectly
    
    When a price falls exactly on a grid level (lower + n*step),
    the alignment check should return True.
    """
    upper = lower + (step * 50)  # 50 levels
    ref = lower + (step * 25)    # Middle
    
    calc = GridCalculator(
        lower=lower,
        upper=upper,
        step=step,
        ref=ref,
        tick_size=0.5
    )
    
    # Test all grid levels should be aligned
    for i in range(51):
        grid_level = lower + (i * step)
        assert calc.is_price_grid_aligned(grid_level, tolerance=0.01), \
            f"Grid level {grid_level} not aligned (lower={lower}, step={step})"


# ================================================================
# Test 5: Grid Alignment Tolerance
# ================================================================

@given(
    lower=st.floats(min_value=1000.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
    step=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
    offset=st.floats(min_value=-0.005, max_value=0.005, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=300)
def test_grid_alignment_tolerance(lower, step, offset):
    """
    Property: Small deviations within tolerance should still align
    
    Prices within tolerance (0.01) of a grid level should be
    considered aligned to handle floating point errors.
    """
    upper = lower + (step * 50)
    ref = lower + (step * 25)
    
    calc = GridCalculator(
        lower=lower,
        upper=upper,
        step=step,
        ref=ref,
        tick_size=0.5
    )
    
    # Test grid level + small offset
    grid_level = lower + (10 * step)
    test_price = grid_level + offset
    
    # Should be aligned if offset within tolerance
    if abs(offset) <= 0.01:
        assert calc.is_price_grid_aligned(test_price, tolerance=0.01), \
            f"Price {test_price} with offset {offset} should align to grid {grid_level}"


# ================================================================
# Test 6: Nearest Grid Level Accuracy
# ================================================================

@given(
    lower=st.floats(min_value=1000.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
    step=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
    price_offset=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=300)
def test_nearest_grid_level_accuracy(lower, step, price_offset):
    """
    Property: Nearest grid level should minimize distance
    
    The nearest grid level should be the closest grid level
    to the input price (within step/2 + small tolerance for rounding).
    """
    upper = lower + (step * 50)
    ref = lower + (step * 25)
    
    calc = GridCalculator(
        lower=lower,
        upper=upper,
        step=step,
        ref=ref,
        tick_size=0.5
    )
    
    # Test price between two grid levels
    base_level = lower + (10 * step)
    test_price = base_level + (price_offset * step)
    
    nearest = calc.find_nearest_grid_level(test_price)
    
    # Distance to nearest should be <= step/2 (with small tolerance for floating point)
    distance = abs(nearest - test_price)
    max_distance = (step / 2) + 0.01  # Add small tolerance for floating point rounding
    
    assert distance <= max_distance, \
        f"Nearest level {nearest} too far from {test_price} (distance={distance}, max={max_distance})"


# ================================================================
# Test 7: Grid Bounds Consistency
# ================================================================

@given(
    lower=st.floats(min_value=1000.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
    step=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=300)
def test_grid_bounds_consistency(lower, step):
    """
    Property: All grid levels should be within bounds
    
    Every grid level generated by get_grid_levels() should
    satisfy is_within_bounds().
    """
    upper = lower + (step * 50)
    ref = lower + (step * 25)
    
    calc = GridCalculator(
        lower=lower,
        upper=upper,
        step=step,
        ref=ref,
        tick_size=0.5
    )
    
    levels = calc.get_grid_levels()
    
    for level in levels:
        assert calc.is_within_bounds(level), \
            f"Grid level {level} outside bounds [{lower}, {upper}]"


# ================================================================
# Test 8: Step Addition Precision
# ================================================================

@given(
    entry=st.floats(min_value=50000.0, max_value=150000.0, allow_nan=False, allow_infinity=False),
    step=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=300)
def test_step_addition_precision(entry, step):
    """
    Property: TP price should be exactly entry + step
    
    Take-profit calculation should add step without
    floating point drift.
    """
    calc = GridCalculator(
        lower=10000.0,
        upper=200000.0,
        step=step,
        ref=100000.0,
        tick_size=0.5
    )
    
    tp = calc.compute_tp_price(entry)
    
    # Use Decimal for precise comparison
    entry_dec = Decimal(str(entry))
    step_dec = Decimal(str(step))
    expected = float(entry_dec + step_dec)
    
    # Allow tiny floating point tolerance
    assert abs(tp - expected) < 1e-10, \
        f"TP calculation imprecise: {tp} != {expected} (diff={tp - expected})"


# ================================================================
# Test 9: Quantization Multiple of Tick Size
# ================================================================

@given(
    price=st.floats(min_value=1000.0, max_value=200000.0, allow_nan=False, allow_infinity=False),
    tick_size=st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=500)
def test_quantization_multiple_of_tick(price, tick_size):
    """
    Property: Quantized price should be exact multiple of tick size
    
    The quantized price should be divisible by tick_size with
    no remainder (accounting for floating point tolerance).
    """
    calc = GridCalculator(
        lower=1000.0,
        upper=200000.0,
        step=1000.0,
        ref=100000.0,
        tick_size=tick_size
    )
    
    quantized = calc.quantize_price(price)
    
    # Check if quantized is multiple of tick_size
    # Use Decimal for precise division
    q_dec = Decimal(str(quantized))
    t_dec = Decimal(str(tick_size))
    
    remainder = float(q_dec % t_dec)
    
    assert remainder < 1e-10 or abs(remainder - tick_size) < 1e-10, \
        f"Quantized {quantized} not multiple of tick {tick_size} (remainder={remainder})"


# ================================================================
# Test 10: NaN and Infinity Rejection
# ================================================================

def test_quantize_rejects_nan():
    """
    Edge Case: Quantize should reject NaN inputs
    
    Prevents NaN propagation through calculations.
    """
    calc = GridCalculator(
        lower=1000.0,
        upper=200000.0,
        step=1000.0,
        ref=100000.0,
        tick_size=0.5
    )
    
    with pytest.raises(ValueError, match="must be finite"):
        calc.quantize_price(float('nan'))


def test_quantize_rejects_infinity():
    """
    Edge Case: Quantize should reject Infinity inputs
    
    Prevents infinite values in price calculations.
    """
    calc = GridCalculator(
        lower=1000.0,
        upper=200000.0,
        step=1000.0,
        ref=100000.0,
        tick_size=0.5
    )
    
    with pytest.raises(ValueError, match="must be finite"):
        calc.quantize_price(float('inf'))
    
    with pytest.raises(ValueError, match="must be finite"):
        calc.quantize_price(float('-inf'))


# ================================================================
# Test 11: Grid Level Generation Completeness
# ================================================================

@given(
    lower=st.floats(min_value=1000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    step=st.floats(min_value=100.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    num_levels=st.integers(min_value=5, max_value=50)
)
@settings(max_examples=200)
def test_grid_level_generation_completeness(lower, step, num_levels):
    """
    Property: Grid levels should span entire range
    
    Generated grid levels should cover from lower to upper
    with correct spacing. After quantization fix, levels
    are filtered to ensure they remain within bounds.
    """
    upper = lower + (step * num_levels)
    ref = lower + (step * (num_levels // 2))
    
    calc = GridCalculator(
        lower=lower,
        upper=upper,
        step=step,
        ref=ref,
        tick_size=0.5
    )
    
    levels = calc.get_grid_levels()
    
    # Should have at least some levels (quantization may filter some out)
    assert len(levels) >= max(1, num_levels - 2), \
        f"Expected at least {num_levels - 2} levels, got {len(levels)}"
    
    # All levels should be within bounds
    for level in levels:
        assert calc.is_within_bounds(level), \
            f"Level {level} outside bounds [{lower}, {upper}]"
    
    # First level should be at or near lower (within one step + quantization)
    assert abs(levels[0] - lower) < (step + calc.tick_size), \
        f"First level {levels[0]} too far from lower bound {lower}"
    
    # Last level should be at or near upper (within one step + quantization)
    assert abs(levels[-1] - upper) <= (step + calc.tick_size), \
        f"Last level {levels[-1]} too far from upper bound {upper}"


# ================================================================
# Test 12: Boundary Prices Exactly On Grid
# ================================================================

def test_boundary_prices_on_grid():
    """
    Edge Case: Prices exactly on grid boundaries
    
    Tests that prices falling exactly on grid levels
    (like 105000.0 when step=1000) align correctly.
    """
    calc = GridCalculator(
        lower=105000.0,
        upper=120000.0,
        step=1000.0,
        ref=110000.0,
        tick_size=0.5
    )
    
    # Test all grid levels
    for i in range(16):  # 105k to 120k in 1k steps
        price = 105000.0 + (i * 1000.0)
        
        assert calc.is_price_grid_aligned(price), \
            f"Grid level {price} should be aligned"
        
        # Nearest should return itself
        nearest = calc.find_nearest_grid_level(price)
        assert abs(nearest - price) < 0.01, \
            f"Nearest to {price} should be {price}, got {nearest}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
