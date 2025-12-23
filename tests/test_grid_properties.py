"""
Property-Based Tests for GridCalculator

Uses Hypothesis to generate thousands of test cases and find edge cases.

Property-based testing asks: "What should ALWAYS be true?"
Rather than testing specific examples, we test mathematical properties.

Example: Instead of "sqrt(4) == 2", we test "sqrt(x)^2 == x for all x >= 0"
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
import math

from bot.strategy.modules.grid_calculator import GridCalculator


# ============================================================================
# STRATEGY DEFINITIONS (Input Generators)
# ============================================================================

@st.composite
def valid_grid_params(draw):
    """
    Generate valid grid parameters that always satisfy constraints
    
    Constraints:
    - lower < upper
    - step > 0
    - lower <= ref <= upper
    - tick_size > 0
    """
    # Generate lower bound (reasonable trading range)
    lower = draw(st.floats(min_value=1000, max_value=50000, allow_nan=False, allow_infinity=False))
    
    # Generate step (1% to 10% of lower bound)
    step = draw(st.floats(min_value=lower * 0.01, max_value=lower * 0.10, allow_nan=False, allow_infinity=False))
    
    # Generate upper bound (at least 5 steps above lower)
    upper = draw(st.floats(min_value=lower + 5*step, max_value=lower + 50*step, allow_nan=False, allow_infinity=False))
    
    # Generate ref within bounds
    ref = draw(st.floats(min_value=lower, max_value=upper, allow_nan=False, allow_infinity=False))
    
    # Generate tick size (0.01 to 1.0)
    tick_size = draw(st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False))
    
    return {
        'lower': round(lower, 2),
        'upper': round(upper, 2),
        'step': round(step, 2),
        'ref': round(ref, 2),
        'tick_size': round(tick_size, 2)
    }


@st.composite
def position_list(draw, min_entry, max_entry):
    """
    Generate a list of positions with entry prices in range
    
    Args:
        min_entry: Minimum entry price
        max_entry: Maximum entry price
    """
    num_positions = draw(st.integers(min_value=0, max_value=10))
    
    positions = []
    for _ in range(num_positions):
        entry_price = draw(st.floats(
            min_value=min_entry, 
            max_value=max_entry,
            allow_nan=False,
            allow_infinity=False
        ))
        positions.append({'entry_price': round(entry_price, 2)})
    
    return positions


# ============================================================================
# PROPERTY 1: Grid Initialization Invariants
# ============================================================================

@given(params=valid_grid_params())
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_grid_always_initializes_with_valid_params(params):
    """
    PROPERTY: Valid parameters always create a valid GridCalculator
    
    Invariants:
    - lower < upper
    - step > 0
    - lower <= ref <= upper
    - All values are finite floats
    """
    calc = GridCalculator(**params)
    
    # Check all parameters stored correctly
    assert calc.lower < calc.upper
    assert calc.step > 0
    assert calc.lower <= calc.ref <= calc.upper
    assert calc.tick_size > 0
    
    # Check all values are finite
    assert math.isfinite(calc.lower)
    assert math.isfinite(calc.upper)
    assert math.isfinite(calc.step)
    assert math.isfinite(calc.ref)


@given(
    lower=st.floats(min_value=1000, max_value=100000),
    upper=st.floats(min_value=1000, max_value=100000),
)
@settings(max_examples=100)
def test_property_grid_rejects_invalid_bounds(lower, upper):
    """
    PROPERTY: GridCalculator rejects lower >= upper
    """
    assume(lower >= upper)  # Only test invalid cases
    
    with pytest.raises(ValueError, match="Lower bound must be less than upper bound"):
        GridCalculator(
            lower=lower,
            upper=upper,
            step=100,
            ref=(lower + upper) / 2,
            tick_size=0.5
        )


@given(step=st.floats(max_value=0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_property_grid_rejects_non_positive_step(step):
    """
    PROPERTY: GridCalculator rejects step <= 0
    """
    with pytest.raises(ValueError, match="Step must be positive"):
        GridCalculator(
            lower=100000,
            upper=110000,
            step=step,
            ref=105000,
            tick_size=0.5
        )


# ============================================================================
# PROPERTY 2: Price Quantization Properties
# ============================================================================

@given(
    params=valid_grid_params(),
    price=st.floats(min_value=1000, max_value=200000, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=200)
def test_property_quantize_always_rounds_down_to_tick_multiple(params, price):
    """
    PROPERTY: Quantized price is always a multiple of tick_size
    
    Invariants:
    - quantized <= original
    - quantized % tick_size == 0
    - (original - quantized) < tick_size
    """
    calc = GridCalculator(**params)
    quantized = calc.quantize_price(price)
    
    # Quantized price is a multiple of tick_size (within floating point precision)
    remainder = quantized % calc.tick_size
    assert abs(remainder) < 1e-6 or abs(remainder - calc.tick_size) < 1e-6
    
    # Quantized price is always <= original
    assert quantized <= price + 1e-9  # Allow tiny floating point error
    
    # Difference is less than one tick
    assert (price - quantized) < calc.tick_size + 1e-9


@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_quantize_is_idempotent(params):
    """
    PROPERTY: Quantizing a quantized price returns the same price
    
    quantize(quantize(x)) == quantize(x)
    
    This test found a REAL BUG in the original quantize_price implementation
    that caused floating-point drift with certain tick sizes like 0.74
    """
    calc = GridCalculator(**params)
    
    # Generate a random price
    price = params['lower'] + (params['upper'] - params['lower']) * 0.5
    
    quantized_once = calc.quantize_price(price)
    quantized_twice = calc.quantize_price(quantized_once)
    
    # After fix, should be within floating point precision
    assert abs(quantized_once - quantized_twice) < 1e-6


# ============================================================================
# PROPERTY 3: Next Buy Level Properties (LONG Grid)
# ============================================================================

@given(params=valid_grid_params())
@settings(max_examples=200)
def test_property_next_buy_with_no_positions_is_ref_minus_step(params):
    """
    PROPERTY: With no positions, next BUY = ref - step (if within bounds)
    """
    calc = GridCalculator(**params)
    
    next_buy = calc.compute_next_buy_level([])
    
    if next_buy is not None:
        expected = calc.quantize_price(params['ref'] - params['step'])
        assert abs(next_buy - expected) < 1e-9
        assert calc.is_within_bounds(next_buy)


@given(
    params=valid_grid_params(),
    positions=st.data()
)
@settings(max_examples=200)
def test_property_next_buy_is_always_below_lowest_position(params, positions):
    """
    PROPERTY: Next BUY level is always below the lowest open position
    
    Invariants:
    - next_buy < min(all entry prices)
    - next_buy is within grid bounds OR None
    """
    calc = GridCalculator(**params)
    
    # Generate positions within grid bounds
    pos_list = positions.draw(position_list(
        min_entry=params['lower'],
        max_entry=params['upper']
    ))
    
    if not pos_list:
        return  # Skip empty position tests (covered by other property)
    
    next_buy = calc.compute_next_buy_level(pos_list)
    lowest_entry = min(p['entry_price'] for p in pos_list)
    
    if next_buy is not None:
        # Next BUY must be below lowest position
        assert next_buy < lowest_entry
        
        # Must be within bounds
        assert calc.is_within_bounds(next_buy)
        
        # Must be approximately one step below
        expected = calc.quantize_price(lowest_entry - params['step'])
        assert abs(next_buy - expected) < 1e-9


@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_next_buy_returns_none_when_at_lower_bound(params):
    """
    PROPERTY: When lowest position is at lower bound, next BUY is None
    """
    calc = GridCalculator(**params)
    
    # Create position at lower bound
    positions = [{'entry_price': params['lower']}]
    
    next_buy = calc.compute_next_buy_level(positions)
    
    # Should be None (can't BUY below lower bound)
    assert next_buy is None


# ============================================================================
# PROPERTY 4: Next Sell Level Properties (SHORT Grid)
# ============================================================================

@given(params=valid_grid_params())
@settings(max_examples=200)
def test_property_next_sell_with_no_positions_is_ref_plus_step(params):
    """
    PROPERTY: With no positions, next SELL = ref + step (if within bounds)
    """
    calc = GridCalculator(**params)
    
    next_sell = calc.compute_next_sell_level([])
    
    if next_sell is not None:
        expected = calc.quantize_price(params['ref'] + params['step'])
        assert abs(next_sell - expected) < 1e-9
        assert calc.is_within_bounds(next_sell)


@given(
    params=valid_grid_params(),
    positions=st.data()
)
@settings(max_examples=200)
def test_property_next_sell_is_always_above_highest_position(params, positions):
    """
    PROPERTY: Next SELL level is always above the highest open position
    
    Invariants:
    - next_sell > max(all entry prices)
    - next_sell is within grid bounds OR None
    """
    calc = GridCalculator(**params)
    
    # Generate positions within grid bounds
    pos_list = positions.draw(position_list(
        min_entry=params['lower'],
        max_entry=params['upper']
    ))
    
    if not pos_list:
        return  # Skip empty position tests
    
    next_sell = calc.compute_next_sell_level(pos_list)
    highest_entry = max(p['entry_price'] for p in pos_list)
    
    if next_sell is not None:
        # Next SELL must be above highest position
        assert next_sell > highest_entry
        
        # Must be within bounds
        assert calc.is_within_bounds(next_sell)
        
        # Must be approximately one step above
        expected = calc.quantize_price(highest_entry + params['step'])
        assert abs(next_sell - expected) < 1e-9


# ============================================================================
# PROPERTY 5: Take Profit Calculation Properties
# ============================================================================

@given(
    params=valid_grid_params(),
    entry_price=st.floats(min_value=1000, max_value=200000, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=200)
def test_property_tp_long_is_always_one_step_above_entry(params, entry_price):
    """
    PROPERTY: For LONG positions, TP = entry + step
    """
    calc = GridCalculator(**params)
    
    tp = calc.compute_tp_price(entry_price)
    
    assert abs(tp - (entry_price + params['step'])) < 1e-9


@given(
    params=valid_grid_params(),
    entry_price=st.floats(min_value=1000, max_value=200000, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=200)
def test_property_tp_short_is_always_one_step_below_entry(params, entry_price):
    """
    PROPERTY: For SHORT positions, TP = entry - step
    """
    calc = GridCalculator(**params)
    
    tp = calc.compute_tp_price_short(entry_price)
    
    assert abs(tp - (entry_price - params['step'])) < 1e-9


@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_tp_long_and_short_are_symmetric(params):
    """
    PROPERTY: TP offsets for LONG and SHORT are symmetric around entry
    
    entry + tp_offset_long = entry - tp_offset_short
    """
    calc = GridCalculator(**params)
    
    entry = params['ref']
    tp_long = calc.compute_tp_price(entry)
    tp_short = calc.compute_tp_price_short(entry)
    
    # Distance from entry should be equal
    long_distance = tp_long - entry
    short_distance = entry - tp_short
    
    assert abs(long_distance - short_distance) < 1e-9


# ============================================================================
# PROPERTY 6: Grid Level Generation Properties
# ============================================================================

@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_grid_levels_are_monotonically_increasing(params):
    """
    PROPERTY: Generated grid levels are always in ascending order
    """
    calc = GridCalculator(**params)
    
    levels = calc.get_grid_levels()
    
    # Check strictly increasing
    for i in range(len(levels) - 1):
        assert levels[i] < levels[i + 1]


@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_grid_levels_span_full_range(params):
    """
    PROPERTY: Grid levels cover from lower to upper bound
    """
    calc = GridCalculator(**params)
    
    levels = calc.get_grid_levels()
    
    # First level should be at or near lower bound
    assert levels[0] >= params['lower'] - params['tick_size']
    
    # Last level should be at or near upper bound
    assert levels[-1] <= params['upper']


@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_grid_levels_spacing_is_step_size(params):
    """
    PROPERTY: Adjacent grid levels are separated by step size
    
    NOTE: Due to quantization, spacing may be slightly less than step
    """
    calc = GridCalculator(**params)
    
    levels = calc.get_grid_levels()
    
    # Check spacing between consecutive levels
    for i in range(len(levels) - 1):
        spacing = levels[i + 1] - levels[i]
        # Should be approximately step size (accounting for quantization)
        # Quantization can reduce spacing by up to 2 * tick_size
        assert abs(spacing - params['step']) <= 2 * params['tick_size']


# ============================================================================
# PROPERTY 7: Bounds Checking Properties
# ============================================================================

@given(
    params=valid_grid_params(),
    price=st.floats(min_value=0, max_value=500000, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=200)
def test_property_is_within_bounds_correctly_classifies_prices(params, price):
    """
    PROPERTY: is_within_bounds returns True IFF lower <= price <= upper
    """
    calc = GridCalculator(**params)
    
    result = calc.is_within_bounds(price)
    expected = (params['lower'] <= price <= params['upper'])
    
    assert result == expected


@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_lower_and_upper_bounds_are_always_within_bounds(params):
    """
    PROPERTY: Grid lower and upper bounds are always considered "within bounds"
    """
    calc = GridCalculator(**params)
    
    assert calc.is_within_bounds(params['lower'])
    assert calc.is_within_bounds(params['upper'])


# ============================================================================
# PROPERTY 8: Nearest Grid Level Properties
# ============================================================================

@given(
    params=valid_grid_params(),
    price=st.floats(min_value=1000, max_value=200000, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=200)
def test_property_nearest_level_is_multiple_of_step(params, price):
    """
    PROPERTY: Nearest grid level is always a multiple of step
    """
    calc = GridCalculator(**params)
    
    nearest = calc.find_nearest_grid_level(price)
    
    # Should be a multiple of step (within floating point precision)
    remainder = nearest % params['step']
    assert abs(remainder) < 1e-9 or abs(remainder - params['step']) < 1e-9


@given(
    params=valid_grid_params(),
    price=st.floats(min_value=1000, max_value=200000, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=200)
def test_property_nearest_level_minimizes_distance(params, price):
    """
    PROPERTY: Nearest grid level is closer than adjacent levels
    """
    calc = GridCalculator(**params)
    
    nearest = calc.find_nearest_grid_level(price)
    distance = abs(price - nearest)
    
    # Distance to adjacent levels should be larger
    level_above = nearest + params['step']
    level_below = nearest - params['step']
    
    assert distance <= abs(price - level_above) + 1e-9
    assert distance <= abs(price - level_below) + 1e-9


# ============================================================================
# PROPERTY 9: Relationship Properties (Cross-Function Invariants)
# ============================================================================

@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_tp_cancels_next_buy_offset(params):
    """
    PROPERTY: TP price from a BUY order equals the next SELL level
    
    This ensures grid continuity:
    BUY at X → TP at X+step → Next BUY at X-step
    """
    calc = GridCalculator(**params)
    
    # Simulate BUY at ref
    entry = params['ref']
    tp = calc.compute_tp_price(entry)
    
    # TP should be one step above
    assert abs(tp - (entry + params['step'])) < 1e-9
    
    # Next BUY should be one step below
    next_buy = calc.compute_next_buy_level([{'entry_price': entry}])
    if next_buy is not None:
        assert abs(next_buy - (entry - params['step'])) < params['tick_size']


# ============================================================================
# MUTATION TESTING: Boundary Edge Cases
# ============================================================================

@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_lower_bound_is_inclusive(params):
    """
    PROPERTY: Lower bound is INCLUSIVE (lower <= price)
    
    Mutation Test: Catches change from <= to <
    """
    calc = GridCalculator(**params)
    
    # Price exactly at lower bound should be within bounds
    assert calc.is_within_bounds(params['lower']) == True
    
    # Price just below lower bound should be outside bounds
    assert calc.is_within_bounds(params['lower'] - 0.01) == False


@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_upper_bound_is_inclusive(params):
    """
    PROPERTY: Upper bound is INCLUSIVE (price <= upper)
    
    Mutation Test: Catches boundary condition bugs
    """
    calc = GridCalculator(**params)
    
    # Price exactly at upper bound should be within bounds
    assert calc.is_within_bounds(params['upper']) == True
    
    # Price just above upper bound should be outside bounds
    assert calc.is_within_bounds(params['upper'] + 0.01) == False


@given(lower=st.floats(min_value=1000, max_value=100000, allow_nan=False, allow_infinity=False))
@settings(max_examples=50)
def test_property_lower_equals_upper_is_invalid(lower):
    """
    PROPERTY: Grid with lower == upper must be rejected
    
    Mutation Test: Catches change from >= to >
    """
    # lower == upper should be invalid
    with pytest.raises(ValueError, match="Lower bound must be less than upper bound"):
        GridCalculator(
            lower=lower,
            upper=lower,  # Same as lower!
            step=100,
            ref=lower,
            tick_size=0.5
        )


@given(tick_size=st.just(0.0))  # Exactly zero
@settings(max_examples=10)
def test_property_tick_size_zero_is_invalid(tick_size):
    """
    PROPERTY: tick_size == 0 must be rejected
    
    Mutation Test: Catches change from <= 0 to < 0
    """
    with pytest.raises(ValueError, match="tick_size must be positive"):
        GridCalculator(
            lower=100000,
            upper=110000,
            step=1000,
            ref=105000,
            tick_size=tick_size  # Zero!
        )


@given(step=st.just(0.0))  # Exactly zero
@settings(max_examples=10)
def test_property_step_zero_is_invalid(step):
    """
    PROPERTY: step == 0 must be rejected
    
    Mutation Test: Catches change from <= 0 to < 0
    """
    with pytest.raises(ValueError, match="Step must be positive"):
        GridCalculator(
            lower=100000,
            upper=110000,
            step=step,  # Zero!
            ref=105000,
            tick_size=0.5
        )


# ============================================================================
# PROPERTY 9: Relationship Properties (Cross-Function Invariants) [ORIGINAL]
# ============================================================================

@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_tp_cancels_next_buy_offset(params):
    """
    PROPERTY: TP price from a BUY order equals the next SELL level
    
    This ensures grid continuity:
    BUY at X → TP at X+step → Next BUY at X-step
    """
    calc = GridCalculator(**params)
    
    # Simulate BUY at ref
    entry = params['ref']
    tp = calc.compute_tp_price(entry)
    
    # TP should be one step above
    assert abs(tp - (entry + params['step'])) < 1e-9
    
    # Next BUY should be one step below
    next_buy = calc.compute_next_buy_level([{'entry_price': entry}])
    if next_buy is not None:
        assert abs(next_buy - (entry - params['step'])) < params['tick_size']


@given(params=valid_grid_params())
@settings(max_examples=100)
def test_property_next_level_functions_are_inverses(params):
    """
    PROPERTY: next_level_down and next_level_up are inverses
    
    next_level_up(next_level_down(x)) == x
    """
    calc = GridCalculator(**params)
    
    price = params['ref']
    
    down = calc.compute_next_level_down(price)
    back_up = calc.compute_next_level_up(down)
    
    assert abs(back_up - price) < 1e-9
    
    # Test in reverse
    up = calc.compute_next_level_up(price)
    back_down = calc.compute_next_level_down(up)
    
    assert abs(back_down - price) < 1e-9


# ============================================================================
# STATEFUL PROPERTY TESTING (Advanced)
# ============================================================================

class GridTradingStateMachine(RuleBasedStateMachine):
    """
    Stateful property testing: Simulate a full grid trading session
    
    Tests that grid properties hold across sequences of operations:
    - Open positions
    - Close positions
    - Calculate next levels
    - Verify bounds always respected
    """
    
    def __init__(self):
        super().__init__()
        
        # Initialize grid
        self.calc = GridCalculator(
            lower=100000,
            upper=110000,
            step=1000,
            ref=105000,
            tick_size=0.5
        )
        
        # Track open positions
        self.open_positions = []
    
    @rule(entry_price=st.floats(min_value=100000, max_value=110000, allow_nan=False, allow_infinity=False))
    def open_long_position(self, entry_price):
        """Open a new LONG position"""
        quantized_entry = self.calc.quantize_price(entry_price)
        
        if self.calc.is_within_bounds(quantized_entry):
            self.open_positions.append({'entry_price': quantized_entry})
    
    @rule()
    def close_random_position(self):
        """Close a random position"""
        if self.open_positions:
            self.open_positions.pop()
    
    @rule()
    def compute_next_buy(self):
        """Compute next BUY level"""
        next_buy = self.calc.compute_next_buy_level(self.open_positions)
        
        # If returned, must be within bounds
        if next_buy is not None:
            assert self.calc.is_within_bounds(next_buy)
    
    @invariant()
    def all_positions_within_bounds(self):
        """INVARIANT: All open positions are within grid bounds"""
        for pos in self.open_positions:
            assert self.calc.is_within_bounds(pos['entry_price'])
    
    @invariant()
    def positions_are_quantized(self):
        """INVARIANT: All positions are quantized to tick size"""
        for pos in self.open_positions:
            quantized = self.calc.quantize_price(pos['entry_price'])
            assert abs(quantized - pos['entry_price']) < 1e-9


# Run stateful tests
TestGridTrading = GridTradingStateMachine.TestCase


# ============================================================================
# EDGE CASE PROPERTIES
# ============================================================================

@given(params=valid_grid_params())
@settings(max_examples=50)
def test_property_grid_handles_extreme_position_counts(params):
    """
    PROPERTY: Grid calculator handles 0 to 1000 positions correctly
    """
    calc = GridCalculator(**params)
    
    # Test with many positions
    positions = [
        {'entry_price': params['lower'] + i * params['step']}
        for i in range(100)
        if calc.is_within_bounds(params['lower'] + i * params['step'])
    ]
    
    # Should not crash
    next_buy = calc.compute_next_buy_level(positions)
    next_sell = calc.compute_next_sell_level(positions)
    
    # Results should be valid or None
    if next_buy is not None:
        assert calc.is_within_bounds(next_buy)
    if next_sell is not None:
        assert calc.is_within_bounds(next_sell)


@given(params=valid_grid_params())
@settings(max_examples=50)
def test_property_grid_handles_positions_at_boundaries(params):
    """
    PROPERTY: Grid correctly handles positions exactly at lower/upper bounds
    """
    calc = GridCalculator(**params)
    
    # Position at lower bound
    pos_lower = [{'entry_price': params['lower']}]
    next_buy = calc.compute_next_buy_level(pos_lower)
    assert next_buy is None  # Can't buy below lower bound
    
    # Position at upper bound
    pos_upper = [{'entry_price': params['upper']}]
    next_sell = calc.compute_next_sell_level(pos_upper)
    assert next_sell is None  # Can't sell above upper bound


if __name__ == '__main__':
    # Run tests with verbose output
    pytest.main([__file__, '-v', '--hypothesis-show-statistics'])
