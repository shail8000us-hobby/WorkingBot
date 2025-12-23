#!/usr/bin/env python3
"""
Test script for Priority 1 enhancements (Rate Limiting + 5xx Retry)

Tests:
1. Normal API call (should work as before)
2. Simulated 429 rate limit (mocked)
3. Simulated 5xx server error (mocked)
4. Circuit breaker interaction (verify it still works)

Run: python3 test_priority1_enhancements.py
"""

import sys
import os
import logging
from unittest.mock import Mock, patch, MagicMock
import requests

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

def test_normal_api_call():
    """Test that normal API calls still work"""
    log.info("\n" + "="*80)
    log.info("TEST 1: Normal API Call (should work as before)")
    log.info("="*80)
    
    from api.delta_client import DeltaClient
    
    # Mock environment
    with patch.dict(os.environ, {
        'DELTA_API_KEY': 'test_key',
        'DELTA_API_SECRET': 'test_secret',
        'DELTA_BASE_URL': 'https://api.test.delta.exchange'
    }):
        client = DeltaClient()
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {'success': True, 'result': {'balance': '1000'}}
        
        with patch.object(client.session, 'request', return_value=mock_response):
            result = client._make_api_request('GET', '/v2/wallet/balances')
            
            assert result['success'] == True
            log.info("✅ PASS: Normal API call works correctly")
            return True

def test_rate_limit_retry():
    """Test that 429 errors trigger Retry-After logic"""
    log.info("\n" + "="*80)
    log.info("TEST 2: Rate Limit (429) with Retry-After Header")
    log.info("="*80)
    
    from api.delta_client import DeltaClient
    
    with patch.dict(os.environ, {
        'DELTA_API_KEY': 'test_key',
        'DELTA_API_SECRET': 'test_secret',
        'DELTA_BASE_URL': 'https://api.test.delta.exchange'
    }):
        client = DeltaClient()
        
        # Mock 429 response (rate limited)
        mock_429 = Mock()
        mock_429.status_code = 429
        mock_429.ok = False
        mock_429.headers = {'Retry-After': '2'}  # 2 second wait
        mock_429.raise_for_status = Mock(side_effect=requests.exceptions.HTTPError("429 Rate Limited"))
        
        # Mock success response after retry
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.ok = True
        mock_success.json.return_value = {'success': True, 'result': []}
        
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                log.info(f"   Call {call_count}: Returning 429 (rate limited)")
                return mock_429
            else:
                log.info(f"   Call {call_count}: Returning 200 (success after retry)")
                return mock_success
        
        with patch.object(client.session, 'request', side_effect=side_effect):
            # Mock time.sleep to speed up test
            with patch('time.sleep') as mock_sleep:
                result = client._make_api_request('GET', '/v2/orders')
                
                assert call_count == 2, f"Expected 2 calls, got {call_count}"
                assert mock_sleep.called, "time.sleep should be called for retry delay"
                
                # Verify it waited 2 seconds (from Retry-After header)
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert 2 in sleep_calls, f"Should wait 2s (Retry-After), got {sleep_calls}"
                
                log.info("✅ PASS: Rate limit retry with Retry-After header works")
                return True

def test_server_error_exponential_backoff():
    """Test that 5xx errors trigger exponential backoff"""
    log.info("\n" + "="*80)
    log.info("TEST 3: Server Error (5xx) with Exponential Backoff")
    log.info("="*80)
    
    from api.delta_client import DeltaClient
    
    with patch.dict(os.environ, {
        'DELTA_API_KEY': 'test_key',
        'DELTA_API_SECRET': 'test_secret',
        'DELTA_BASE_URL': 'https://api.test.delta.exchange'
    }):
        client = DeltaClient()
        
        # Mock 503 response (server error)
        mock_503 = Mock()
        mock_503.status_code = 503
        mock_503.ok = False
        mock_503.text = "Service Unavailable"
        mock_503.raise_for_status = Mock(side_effect=requests.exceptions.HTTPError("503 Server Error"))
        
        # Mock success response after retries
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.ok = True
        mock_success.json.return_value = {'success': True, 'result': []}
        
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                log.info(f"   Call {call_count}: Returning 503 (server error)")
                return mock_503
            else:
                log.info(f"   Call {call_count}: Returning 200 (success after retry)")
                return mock_success
        
        with patch.object(client.session, 'request', side_effect=side_effect):
            # Mock time.sleep to speed up test
            with patch('time.sleep') as mock_sleep:
                result = client._make_api_request('GET', '/v2/positions')
                
                assert call_count == 3, f"Expected 3 calls, got {call_count}"
                assert mock_sleep.called, "time.sleep should be called for backoff"
                
                # Verify exponential backoff: 1s, 2s
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                log.info(f"   Sleep durations: {sleep_calls}")
                assert sleep_calls[0] == 1, f"First retry should wait 1s, got {sleep_calls[0]}"
                assert sleep_calls[1] == 2, f"Second retry should wait 2s, got {sleep_calls[1]}"
                
                log.info("✅ PASS: Exponential backoff works correctly (1s, 2s, 4s...)")
                return True

def test_max_retries_exceeded():
    """Test that max retries is respected"""
    log.info("\n" + "="*80)
    log.info("TEST 4: Max Retries Exceeded (should fail after 3 attempts)")
    log.info("="*80)
    
    from api.delta_client import DeltaClient
    
    with patch.dict(os.environ, {
        'DELTA_API_KEY': 'test_key',
        'DELTA_API_SECRET': 'test_secret',
        'DELTA_BASE_URL': 'https://api.test.delta.exchange'
    }):
        client = DeltaClient()
        
        # Mock persistent 503 response
        mock_503 = Mock()
        mock_503.status_code = 503
        mock_503.ok = False
        mock_503.text = "Service Unavailable"
        mock_503.raise_for_status = Mock(side_effect=requests.exceptions.HTTPError("503 Server Error"))
        
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            log.info(f"   Call {call_count}: Returning 503 (persistent error)")
            return mock_503
        
        with patch.object(client.session, 'request', side_effect=side_effect):
            with patch('time.sleep'):
                try:
                    result = client._make_api_request('GET', '/v2/orders')
                    log.error("❌ FAIL: Should have raised HTTPError after max retries")
                    return False
                except requests.exceptions.HTTPError as e:
                    assert call_count == 3, f"Should try 3 times, got {call_count}"
                    log.info(f"✅ PASS: Failed after {call_count} attempts (as expected)")
                    return True

def test_circuit_breaker_still_works():
    """Test that circuit breaker integration still works"""
    log.info("\n" + "="*80)
    log.info("TEST 5: Circuit Breaker Integration (verify it still works)")
    log.info("="*80)
    
    from api.delta_client import DeltaClient
    
    with patch.dict(os.environ, {
        'DELTA_API_KEY': 'test_key',
        'DELTA_API_SECRET': 'test_secret',
        'DELTA_BASE_URL': 'https://api.test.delta.exchange'
    }):
        client = DeltaClient()
        
        # Verify circuit breaker is initialized
        assert hasattr(client, 'circuit_breaker'), "Circuit breaker should exist"
        assert client.circuit_breaker is not None, "Circuit breaker should be initialized"
        
        log.info("✅ PASS: Circuit breaker is properly initialized")
        
        # Test that _req() wraps _make_api_request() with circuit breaker
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {'success': True, 'result': []}
        
        with patch.object(client.session, 'request', return_value=mock_response):
            result = client._req('GET', '/v2/products')
            assert result['success'] == True
            
        log.info("✅ PASS: Circuit breaker wrapper still works")
        return True

def main():
    """Run all tests"""
    log.info("\n" + "="*80)
    log.info("PRIORITY 1 ENHANCEMENTS TEST SUITE")
    log.info("Testing: Rate Limiting + Exponential Backoff for 5xx")
    log.info("="*80)
    
    tests = [
        ("Normal API Call", test_normal_api_call),
        ("Rate Limit Retry", test_rate_limit_retry),
        ("Server Error Backoff", test_server_error_exponential_backoff),
        ("Max Retries", test_max_retries_exceeded),
        ("Circuit Breaker", test_circuit_breaker_still_works),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            log.error(f"❌ TEST FAILED: {name}")
            log.error(f"   Error: {e}")
            import traceback
            log.error(traceback.format_exc())
            results.append((name, False))
    
    # Summary
    log.info("\n" + "="*80)
    log.info("TEST SUMMARY")
    log.info("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        log.info(f"{status}: {name}")
    
    log.info("="*80)
    log.info(f"RESULTS: {passed}/{total} tests passed")
    log.info("="*80)
    
    if passed == total:
        log.info("\n🎉 ALL TESTS PASSED! Priority 1 enhancements are working correctly.")
        log.info("\nNext steps:")
        log.info("1. ✅ Deploy to production")
        log.info("2. Monitor logs for 429/5xx occurrences")
        log.info("3. Verify circuit breaker stats after 1 week")
        return 0
    else:
        log.error("\n⚠️  SOME TESTS FAILED. Review errors above before deploying.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
