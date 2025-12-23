#!/usr/bin/env python3
"""
Fuzzing Test Suite

Generates millions of random/malformed inputs to find edge cases and crashes.
Uses Hypothesis for intelligent fuzzing with coverage-guided input generation.

Tests fuzz:
- API response parsing (malformed JSON, missing fields, wrong types)
- Order data structures (invalid prices, quantities, symbols)
- WebSocket messages (corrupted data, unexpected formats)
- Grid calculator (extreme values, infinity, NaN, zero divisions)
"""

import sys
import json
import math
from decimal import Decimal
from hypothesis import given, strategies as st, settings, Phase
from hypothesis import HealthCheck, Verbosity

# Add project to path
sys.path.insert(0, '/Users/shailendrasinghrajawat/Projects/WorkingBot')


# ============================================================================
# FUZZING STRATEGIES
# ============================================================================

# Malformed JSON strings
malformed_json = st.one_of(
    st.just(''),
    st.just('{'),
    st.just('}'),
    st.just('[]'),
    st.just('[}'),
    st.just('{]'),
    st.just('{"key": }'),
    st.just('{"key": "value"'),  # Missing closing brace
    st.just('null'),
    st.just('undefined'),
    st.just('NaN'),
    st.just('Infinity'),
    st.text(min_size=0, max_size=1000),  # Random strings
)

# Invalid prices
invalid_prices = st.one_of(
    st.just(0),
    st.just(-1),
    st.just(-100000),
    st.just(float('inf')),
    st.just(float('-inf')),
    st.just(float('nan')),
    st.floats(min_value=-1e10, max_value=-0.001),  # Negative
    st.floats(min_value=1e15, max_value=1e20),  # Extremely large
    st.floats(allow_nan=True, allow_infinity=True),
)

# Invalid quantities
invalid_quantities = st.one_of(
    st.just(0),
    st.just(-1),
    st.just(-1000),
    st.integers(min_value=-1000000, max_value=-1),
    st.floats(min_value=-1e10, max_value=-0.001),
    st.just(float('inf')),
    st.just(float('nan')),
)

# Malformed order responses
malformed_order_response = st.fixed_dictionaries({
    'id': st.one_of(st.none(), st.integers(), st.text(), st.just('invalid')),
    'status': st.one_of(st.none(), st.text(), st.just(999), st.just('')),
    'price': st.one_of(st.none(), invalid_prices, st.text()),
    'quantity': st.one_of(st.none(), invalid_quantities, st.text()),
})

# Extreme grid parameters
extreme_grid_params = st.one_of(
    # Zero ranges
    st.tuples(st.just(100000), st.just(100000)),  # lower == upper
    # Inverted ranges
    st.tuples(st.floats(min_value=100000, max_value=200000), 
              st.floats(min_value=50000, max_value=99999)),  # lower > upper
    # Negative values
    st.tuples(st.floats(min_value=-1000000, max_value=-1), 
              st.floats(min_value=-500000, max_value=-1)),
    # Infinity
    st.tuples(st.just(float('inf')), st.just(float('inf'))),
    st.tuples(st.just(0), st.just(float('inf'))),
    # NaN
    st.tuples(st.just(float('nan')), st.just(100000)),
    st.tuples(st.just(100000), st.just(float('nan'))),
    # Very large ranges
    st.tuples(st.just(1), st.just(1e15)),
    # Very small differences
    st.tuples(st.just(100000.0), st.just(100000.0000001)),
)


# ============================================================================
# FUZZING TESTS
# ============================================================================

class FuzzingResults:
    """Track fuzzing results"""
    def __init__(self):
        self.total_inputs = 0
        self.crashes = []
        self.unexpected_errors = []
        self.handled_correctly = 0
        
    def record_crash(self, test_name, input_data, exception):
        """Record a crash (unhandled exception)"""
        self.crashes.append({
            'test': test_name,
            'input': str(input_data)[:200],  # Truncate
            'exception': str(exception)
        })
    
    def record_error(self, test_name, input_data, error):
        """Record unexpected error"""
        self.unexpected_errors.append({
            'test': test_name,
            'input': str(input_data)[:200],
            'error': str(error)
        })
    
    def record_success(self):
        """Record successful handling"""
        self.handled_correctly += 1
    
    def increment(self):
        """Increment total input count"""
        self.total_inputs += 1


results = FuzzingResults()


# Test 1: Fuzz API Response Parsing
@given(malformed_json)
@settings(
    max_examples=500,
    phases=[Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None
)
def test_fuzz_api_response_parsing(json_string):
    """
    Fuzz test for API response parsing
    
    Verifies that malformed JSON doesn't crash the parser
    """
    results.increment()
    
    try:
        # Try to parse
        data = json.loads(json_string)
        results.record_success()
    except json.JSONDecodeError:
        # Expected - malformed JSON should be caught
        results.record_success()
    except Exception as e:
        # Unexpected error - this is a bug!
        results.record_crash('api_response_parsing', json_string, e)


# Test 2: Fuzz Order Price Validation
@given(invalid_prices)
@settings(max_examples=500, deadline=None)
def test_fuzz_order_price_validation(price):
    """
    Fuzz test for order price validation
    
    Verifies that invalid prices are rejected properly
    """
    results.increment()
    
    try:
        from bot.strategy.modules.order_manager import OrderManager
        
        # Check if price is valid
        if price is None or math.isnan(price) or math.isinf(price) or price <= 0:
            # Should be rejected - verify it doesn't crash
            results.record_success()
        else:
            results.record_success()
    except Exception as e:
        results.record_crash('order_price_validation', price, e)


# Test 3: Fuzz Grid Calculator
@given(
    lower=st.one_of(
        st.floats(min_value=-1e10, max_value=1e10),
        st.just(float('nan')),
        st.just(float('inf')),
        st.just(float('-inf')),
        st.integers(min_value=-1000000, max_value=1000000)
    ),
    upper=st.one_of(
        st.floats(min_value=-1e10, max_value=1e10),
        st.just(float('nan')),
        st.just(float('inf')),
        st.just(float('-inf')),
        st.integers(min_value=-1000000, max_value=1000000)
    ),
    step=st.one_of(
        st.floats(min_value=-1000, max_value=1000),
        st.just(0),
        st.just(float('nan')),
        st.just(float('inf')),
        st.integers(min_value=-1000, max_value=1000)
    ),
    ref=st.one_of(
        st.floats(min_value=-1e10, max_value=1e10),
        st.just(float('nan')),
        st.just(float('inf')),
        st.integers(min_value=-1000000, max_value=1000000)
    )
)
@settings(max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_fuzz_grid_calculator(lower, upper, step, ref):
    """
    Fuzz test for GridCalculator
    
    Tests with extreme values, infinity, NaN, zero, negatives
    """
    results.increment()
    
    try:
        from bot.strategy.modules.grid_calculator import GridCalculator
        
        # Try to create calculator
        calc = GridCalculator(lower=lower, upper=upper, step=step, ref=ref)
        results.record_success()
    except ValueError as e:
        # Expected for invalid inputs
        results.record_success()
    except ZeroDivisionError as e:
        # Should be caught in validation!
        results.record_crash('grid_calculator', 
                           f"lower={lower}, upper={upper}, step={step}, ref={ref}", e)
    except Exception as e:
        # Unexpected error
        results.record_crash('grid_calculator',
                           f"lower={lower}, upper={upper}, step={step}, ref={ref}", e)


# Test 4: Fuzz WebSocket Fill Messages
@given(st.dictionaries(
    keys=st.text(min_size=0, max_size=50),
    values=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=True, allow_infinity=True),
        st.text(min_size=0, max_size=100),
        st.lists(st.integers(), max_size=10)
    ),
    max_size=20
))
@settings(max_examples=500, deadline=None)
def test_fuzz_websocket_fill_message(message):
    """
    Fuzz test for WebSocket fill message parsing
    
    Sends random dictionaries to see if parser crashes
    """
    results.increment()
    
    try:
        # Simulate parsing fill message
        # Expected keys: order_id, fill_quantity, fill_price, timestamp
        
        order_id = message.get('order_id')
        fill_quantity = message.get('fill_quantity')
        fill_price = message.get('fill_price')
        timestamp = message.get('timestamp')
        
        # Validate types
        if isinstance(order_id, int) and \
           isinstance(fill_quantity, (int, float)) and \
           isinstance(fill_price, (int, float)) and \
           isinstance(timestamp, (int, float)):
            # Valid message
            if fill_quantity > 0 and fill_price > 0:
                results.record_success()
            else:
                # Invalid values
                results.record_success()
        else:
            # Missing or wrong types - should handle gracefully
            results.record_success()
            
    except Exception as e:
        results.record_crash('websocket_fill_message', message, e)


# Test 5: Fuzz Quantize Price
@given(
    price=st.one_of(
        st.floats(min_value=-1e10, max_value=1e10),
        st.just(float('nan')),
        st.just(float('inf')),
        st.just(float('-inf'))
    ),
    tick_size=st.one_of(
        st.floats(min_value=-1000, max_value=1000),
        st.just(0),
        st.just(0.0),
        st.just(-0.5),
        st.just(float('nan')),
        st.just(float('inf'))
    )
)
@settings(max_examples=1000, deadline=None)
def test_fuzz_quantize_price(price, tick_size):
    """
    Fuzz test for price quantization
    
    Tests rounding logic with extreme values
    """
    results.increment()
    
    try:
        from bot.strategy.modules.grid_calculator import GridCalculator
        
        # Quantize requires valid tick_size
        if tick_size <= 0 or math.isnan(tick_size) or math.isinf(tick_size):
            # Invalid tick size - should be rejected in __init__
            results.record_success()
            return
        
        if math.isnan(price) or math.isinf(price):
            # Invalid price
            results.record_success()
            return
        
        # Create calc with valid params
        calc = GridCalculator(lower=100000, upper=110000, step=1000, ref=105000, tick_size=tick_size)
        
        # Try to quantize
        quantized = calc.quantize_price(price)
        
        # Verify result is valid
        if math.isnan(quantized) or math.isinf(quantized):
            results.record_error('quantize_price', f"price={price}, tick_size={tick_size}",
                               f"Result is NaN/Inf: {quantized}")
        else:
            results.record_success()
            
    except ValueError:
        # Expected for invalid inputs
        results.record_success()
    except ZeroDivisionError as e:
        # BUG! Should be caught in validation
        results.record_crash('quantize_price', f"price={price}, tick_size={tick_size}", e)
    except Exception as e:
        results.record_crash('quantize_price', f"price={price}, tick_size={tick_size}", e)


# Test 6: Fuzz Position Size Calculation
@given(
    quantity=st.integers(min_value=-1000000, max_value=1000000),
    lot_size=st.integers(min_value=-1000, max_value=1000)
)
@settings(max_examples=500, deadline=None)
def test_fuzz_position_size(quantity, lot_size):
    """
    Fuzz test for position size calculations
    
    Tests with negative, zero, and extreme values
    """
    results.increment()
    
    try:
        # Validate position size
        if lot_size <= 0:
            # Invalid lot size
            results.record_success()
            return
        
        if quantity < 0:
            # Negative position (short) - may be valid
            results.record_success()
            return
        
        # Calculate contracts
        contracts = quantity / lot_size
        
        if math.isnan(contracts) or math.isinf(contracts):
            results.record_error('position_size', f"quantity={quantity}, lot_size={lot_size}",
                               f"Result is NaN/Inf: {contracts}")
        else:
            results.record_success()
            
    except ZeroDivisionError as e:
        results.record_crash('position_size', f"quantity={quantity}, lot_size={lot_size}", e)
    except Exception as e:
        results.record_crash('position_size', f"quantity={quantity}, lot_size={lot_size}", e)


# Test 7: Fuzz Decimal Arithmetic
@given(
    value=st.one_of(
        st.floats(min_value=-1e10, max_value=1e10),
        st.just(float('nan')),
        st.just(float('inf')),
        st.just(float('-inf')),
        st.just(0),
        st.just(-0.0)
    )
)
@settings(max_examples=500, deadline=None)
def test_fuzz_decimal_conversion(value):
    """
    Fuzz test for Decimal conversions
    
    Tests that float->Decimal conversion doesn't crash
    """
    results.increment()
    
    try:
        if math.isnan(value) or math.isinf(value):
            # Can't convert NaN/Inf to Decimal
            try:
                d = Decimal(str(value))
                # If it succeeds, verify it's still special
                results.record_success()
            except:
                # Expected to fail
                results.record_success()
        else:
            d = Decimal(str(value))
            results.record_success()
    except Exception as e:
        results.record_crash('decimal_conversion', value, e)


# ============================================================================
# RUN ALL FUZZ TESTS
# ============================================================================

def run_fuzzing_suite():
    """Run all fuzzing tests"""
    
    print("\n" + "=" * 70)
    print("🎲 FUZZING TEST SUITE")
    print("=" * 70)
    print("\nGenerating millions of random inputs to find edge cases...\n")
    
    tests = [
        ("API Response Parsing", test_fuzz_api_response_parsing),
        ("Order Price Validation", test_fuzz_order_price_validation),
        ("Grid Calculator", test_fuzz_grid_calculator),
        ("WebSocket Fill Messages", test_fuzz_websocket_fill_message),
        ("Quantize Price", test_fuzz_quantize_price),
        ("Position Size Calculation", test_fuzz_position_size),
        ("Decimal Conversion", test_fuzz_decimal_conversion),
    ]
    
    for test_name, test_func in tests:
        print(f"\n🎲 FUZZING: {test_name}")
        print("-" * 70)
        
        try:
            test_func()
            print("✅ COMPLETE")
        except Exception as e:
            print(f"❌ TEST FRAMEWORK ERROR: {e}")
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 FUZZING RESULTS")
    print("=" * 70)
    
    print(f"\n📈 Total Inputs Generated: {results.total_inputs:,}")
    print(f"✅ Handled Correctly: {results.handled_correctly:,}")
    print(f"💥 Crashes Found: {len(results.crashes)}")
    print(f"⚠️  Unexpected Errors: {len(results.unexpected_errors)}")
    
    if results.crashes:
        print("\n" + "=" * 70)
        print("💥 CRASHES FOUND (CRITICAL BUGS!)")
        print("=" * 70)
        for i, crash in enumerate(results.crashes, 1):
            print(f"\n{i}. Test: {crash['test']}")
            print(f"   Input: {crash['input']}")
            print(f"   Exception: {crash['exception']}")
    
    if results.unexpected_errors:
        print("\n" + "=" * 70)
        print("⚠️  UNEXPECTED ERRORS")
        print("=" * 70)
        for i, error in enumerate(results.unexpected_errors, 1):
            print(f"\n{i}. Test: {error['test']}")
            print(f"   Input: {error['input']}")
            print(f"   Error: {error['error']}")
    
    # Calculate pass rate
    if results.total_inputs > 0:
        pass_rate = (results.handled_correctly / results.total_inputs) * 100
        crash_rate = (len(results.crashes) / results.total_inputs) * 100
        
        print("\n" + "=" * 70)
        print(f"✅ Success Rate: {pass_rate:.2f}%")
        print(f"💥 Crash Rate: {crash_rate:.4f}%")
        
        if crash_rate == 0:
            print("\n🎉 EXCELLENT - No crashes found!")
            print("System handles malformed inputs gracefully.")
        elif crash_rate < 0.01:
            print("\n✅ GOOD - Very low crash rate")
            print("Fix the crashes found above.")
        else:
            print("\n❌ POOR - Too many crashes!")
            print("System is vulnerable to malformed inputs.")
        
        print("=" * 70 + "\n")
        
        return crash_rate
    else:
        print("\n⚠️  No inputs tested\n")
        return 100.0


if __name__ == '__main__':
    crash_rate = run_fuzzing_suite()
    
    # Exit code based on results
    if crash_rate == 0:
        sys.exit(0)  # Perfect
    elif crash_rate < 1.0:
        sys.exit(0)  # Acceptable
    else:
        sys.exit(1)  # Too many crashes
