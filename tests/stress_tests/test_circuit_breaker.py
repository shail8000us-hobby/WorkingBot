#!/usr/bin/env python3
"""
ST-5: Circuit Breaker Resilience Test

Validates circuit breaker behavior with expected vs real errors.
100% VIRTUAL - Mock exceptions, no real API calls.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from bot.safety.circuit_breaker import CircuitBreaker, CircuitBreakerOpen


def test_circuit_breaker_ignores_404():
    """Test that 404 errors don't trigger circuit breaker (FIX #5)"""
    print(f"\n{'='*80}")
    print(f"TEST 1: Circuit Breaker Ignores 404 Errors")
    print(f"{'='*80}")
    print(f"Testing FIX #5 (IGNORED_ERRORS list)...")
    
    cb = CircuitBreaker(name="test_404", failure_threshold=5, timeout=30)
    
    # Simulate 10 consecutive 404 errors (should be ignored)
    ignored_errors = [
        'order_not_found',
        'order_already_cancelled',
        'order_already_filled',
        'insufficient_margin',
        'invalid_price',
        'position_not_found',
        'position_already_closed',
    ]
    
    for i in range(10):
        error_msg = ignored_errors[i % len(ignored_errors)]
        try:
            # Simulate function that raises ignored error
            def failing_func():
                raise Exception(error_msg)
            
            cb.call(failing_func)
        except Exception:
            pass  # Expected to fail, but shouldn't trigger circuit breaker
    
    # Check state
    print(f"\nAfter 10 ignored errors:")
    print(f"Circuit Breaker State: {cb.state.value}")
    print(f"Failure Count: {cb.failure_count}")
    print(f"Ignored Error Count: {cb.total_ignored_errors}")
    
    if cb.state.value == 'CLOSED':
        print(f"\n✅ SUCCESS: Circuit breaker still CLOSED (ignores 404s)")
        return True
    else:
        print(f"\n❌ FAILURE: Circuit breaker opened on ignored errors")
        return False


def test_circuit_breaker_triggers_on_real_failures():
    """Test that real API failures trigger circuit breaker"""
    print(f"\n{'='*80}")
    print(f"TEST 2: Circuit Breaker Triggers on Real Failures")
    print(f"{'='*80}")
    
    cb = CircuitBreaker(name="test_real", failure_threshold=5, timeout=30)
    
    # Simulate 5 real API failures (should trigger)
    real_errors = [
        'Connection timeout',
        'API rate limit exceeded',
        'Internal server error 500',
        'Network unreachable',
        'SSL handshake failed'
    ]
    
    triggered = False
    
    for i in range(5):
        error_msg = real_errors[i % len(real_errors)]
        try:
            def failing_func():
                raise Exception(error_msg)
            
            cb.call(failing_func)
        except CircuitBreakerOpen:
            triggered = True
            print(f"Circuit breaker OPENED after {i+1} failures")
            break
        except Exception:
            pass  # Continue
    
    print(f"\nAfter real failures:")
    print(f"Circuit Breaker State: {cb.state.value}")
    print(f"Failure Count: {cb.failure_count}")
    
    if cb.state.value == 'OPEN' or triggered:
        print(f"\n✅ SUCCESS: Circuit breaker opened on real failures")
        return True
    else:
        print(f"\n❌ FAILURE: Circuit breaker didn't open after 5 failures")
        return False


def test_circuit_breaker_threshold_increased():
    """Test that threshold is increased from 3 to 5 (FIX #5)"""
    print(f"\n{'='*80}")
    print(f"TEST 3: Circuit Breaker Threshold Increased")
    print(f"{'='*80}")
    
    cb = CircuitBreaker(name="test_threshold")
    
    print(f"Default Failure Threshold: {cb.failure_threshold}")
    print(f"Default Timeout: {cb.timeout}s")
    
    if cb.failure_threshold == 5 and cb.timeout == 30:
        print(f"\n✅ SUCCESS: Threshold=5, Timeout=30s (FIX #5 applied)")
        return True
    else:
        print(f"\n⚠️  WARNING: Expected threshold=5, timeout=30s")
        print(f"   Got threshold={cb.failure_threshold}, timeout={cb.timeout}s")
        return False


def test_mixed_errors():
    """Test circuit breaker with mix of ignored and real errors"""
    print(f"\n{'='*80}")
    print(f"TEST 4: Mixed Ignored + Real Errors")
    print(f"{'='*80}")
    
    cb = CircuitBreaker(name="test_mixed", failure_threshold=5, timeout=30)
    
    # Simulate mix: 10 ignored errors + 3 real errors
    # Should NOT trigger (only 3 real errors < threshold 5)
    
    errors = [
        'order_not_found',  # ignored
        'Connection timeout',  # real
        'order_already_cancelled',  # ignored
        'API rate limit',  # real
        'invalid_price',  # ignored
        'Network error',  # real
        'order_not_found',  # ignored
    ]
    
    for error in errors:
        try:
            def failing_func():
                raise Exception(error)
            cb.call(failing_func)
        except CircuitBreakerOpen:
            print(f"Circuit breaker opened prematurely!")
            return False
        except Exception:
            pass
    
    print(f"\nAfter 7 mixed errors (3 real, 4 ignored):")
    print(f"Circuit Breaker State: {cb.state.value}")
    print(f"Failure Count: {cb.failure_count}")
    print(f"Ignored Error Count: {cb.total_ignored_errors}")
    
    if cb.state.value == 'CLOSED' and cb.failure_count == 3:
        print(f"\n✅ SUCCESS: Only real errors counted (3/5), circuit still CLOSED")
        return True
    else:
        print(f"\n❌ FAILURE: Unexpected state or failure count")
        return False


def main():
    """Run all circuit breaker tests"""
    print(f"\n{'#'*80}")
    print(f"# ST-5: CIRCUIT BREAKER RESILIENCE TEST")
    print(f"# Tests FIX #5 (IGNORED_ERRORS, Increased Threshold)")
    print(f"# 100% VIRTUAL - Mock errors, no real API")
    print(f"{'#'*80}")
    
    test1_pass = test_circuit_breaker_ignores_404()
    test2_pass = test_circuit_breaker_triggers_on_real_failures()
    test3_pass = test_circuit_breaker_threshold_increased()
    test4_pass = test_mixed_errors()
    
    # Summary
    print(f"\n{'='*80}")
    print(f"TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Test 1 (Ignores 404s): {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"Test 2 (Triggers on Real): {'✅ PASS' if test2_pass else '❌ FAIL'}")
    print(f"Test 3 (Threshold=5): {'✅ PASS' if test3_pass else '❌ FAIL'}")
    print(f"Test 4 (Mixed Errors): {'✅ PASS' if test4_pass else '❌ FAIL'}")
    
    all_pass = test1_pass and test2_pass and test3_pass and test4_pass
    
    if all_pass:
        print(f"\n🎉 ALL TESTS PASSED - FIX #5 Working Correctly")
        return 0
    else:
        print(f"\n❌ SOME TESTS FAILED - Review Implementation")
        return 1


if __name__ == '__main__':
    exit(main())
