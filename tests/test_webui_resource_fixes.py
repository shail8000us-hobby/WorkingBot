#!/usr/bin/env python3
"""
WebUI Resource Fix - Test Suite

Comprehensive tests to verify all fixes are working correctly.
"""

import time
import requests
import concurrent.futures
import statistics
from typing import List, Dict
import json


BASE_URL = "http://localhost:5555"


class TestResults:
    """Store and display test results."""
    
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
    
    def add_result(self, test_name: str, passed: bool, message: str = "", details: dict = None):
        """Add a test result."""
        self.tests.append({
            'name': test_name,
            'passed': passed,
            'message': message,
            'details': details or {}
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        for test in self.tests:
            status = "✅ PASS" if test['passed'] else "❌ FAIL"
            print(f"\n{status}: {test['name']}")
            if test['message']:
                print(f"  Message: {test['message']}")
            if test['details']:
                print(f"  Details: {json.dumps(test['details'], indent=4)}")
        
        print("\n" + "=" * 80)
        print(f"Total: {len(self.tests)} tests")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {(self.passed / len(self.tests) * 100):.1f}%")
        print("=" * 80)


def test_health_endpoint_speed(results: TestResults):
    """Test that health endpoint is fast (< 10ms)."""
    print("\n📊 Test 1: Health Endpoint Speed")
    print("-" * 80)
    
    times = []
    for i in range(10):
        start = time.time()
        try:
            response = requests.get(f"{BASE_URL}/api/health", timeout=5)
            elapsed = (time.time() - start) * 1000  # Convert to ms
            times.append(elapsed)
            print(f"  Request {i+1}: {elapsed:.2f}ms - Status: {response.status_code}")
        except Exception as e:
            print(f"  Request {i+1}: ERROR - {e}")
            results.add_result(
                "Health Endpoint Speed",
                False,
                f"Request failed: {e}"
            )
            return
    
    avg_time = statistics.mean(times)
    max_time = max(times)
    min_time = min(times)
    
    passed = avg_time < 10.0  # Should be < 10ms
    results.add_result(
        "Health Endpoint Speed",
        passed,
        f"Average: {avg_time:.2f}ms (target: < 10ms)",
        {
            'avg_ms': round(avg_time, 2),
            'min_ms': round(min_time, 2),
            'max_ms': round(max_time, 2),
            'target_ms': 10.0
        }
    )


def test_concurrent_requests(results: TestResults):
    """Test handling of concurrent requests."""
    print("\n📊 Test 2: Concurrent Request Handling")
    print("-" * 80)
    
    num_requests = 50
    
    def make_request(i):
        """Make a single request."""
        try:
            start = time.time()
            response = requests.get(f"{BASE_URL}/api/health", timeout=10)
            elapsed = time.time() - start
            return {
                'success': True,
                'status_code': response.status_code,
                'time': elapsed,
                'request_num': i
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'request_num': i
            }
    
    # Fire concurrent requests
    print(f"  Firing {num_requests} concurrent requests...")
    start = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(make_request, i) for i in range(num_requests)]
        results_list = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    total_time = time.time() - start
    
    # Analyze results
    successful = sum(1 for r in results_list if r['success'])
    failed = num_requests - successful
    errors = [r for r in results_list if not r['success']]
    
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Successful: {successful}/{num_requests}")
    print(f"  Failed: {failed}/{num_requests}")
    
    if errors:
        print(f"  Errors:")
        for err in errors[:5]:  # Show first 5 errors
            print(f"    - Request {err['request_num']}: {err['error']}")
    
    # Should handle at least 90% successfully
    success_rate = successful / num_requests
    passed = success_rate >= 0.9
    
    results.add_result(
        "Concurrent Request Handling",
        passed,
        f"Success rate: {success_rate*100:.1f}% (target: >= 90%)",
        {
            'total_requests': num_requests,
            'successful': successful,
            'failed': failed,
            'success_rate': round(success_rate * 100, 1),
            'total_time_seconds': round(total_time, 2)
        }
    )


def test_connection_pool(results: TestResults):
    """Test connection pooling (no port exhaustion)."""
    print("\n📊 Test 3: Connection Pool (No Port Exhaustion)")
    print("-" * 80)
    
    num_requests = 100
    
    print(f"  Making {num_requests} sequential requests...")
    start = time.time()
    
    errors = []
    for i in range(num_requests):
        try:
            response = requests.get(f"{BASE_URL}/api/health", timeout=5)
            if i % 20 == 0:
                print(f"  Progress: {i}/{num_requests}")
        except Exception as e:
            errors.append(f"Request {i}: {e}")
    
    total_time = time.time() - start
    
    print(f"  Completed {num_requests} requests in {total_time:.2f}s")
    print(f"  Average: {(total_time / num_requests) * 1000:.2f}ms per request")
    print(f"  Errors: {len(errors)}")
    
    # Should complete without port exhaustion errors
    port_exhaustion_errors = [e for e in errors if 'INSUFFICIENT_RESOURCES' in e or 'too many open files' in e]
    
    passed = len(port_exhaustion_errors) == 0
    results.add_result(
        "Connection Pool",
        passed,
        f"No port exhaustion errors (target: 0)",
        {
            'total_requests': num_requests,
            'errors': len(errors),
            'port_exhaustion_errors': len(port_exhaustion_errors),
            'avg_time_ms': round((total_time / num_requests) * 1000, 2)
        }
    )


def test_timeout_handling(results: TestResults):
    """Test that endpoints have proper timeouts."""
    print("\n📊 Test 4: Timeout Handling")
    print("-" * 80)
    
    # Test health endpoint timeout (should respond quickly)
    print("  Testing /api/health timeout...")
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/health", timeout=2)
        elapsed = time.time() - start
        
        # Should respond in < 1 second
        health_timeout_ok = elapsed < 1.0
        print(f"  Health endpoint: {elapsed*1000:.2f}ms (target: < 1000ms)")
    except requests.Timeout:
        health_timeout_ok = False
        print(f"  Health endpoint: TIMEOUT")
    
    passed = health_timeout_ok
    results.add_result(
        "Timeout Handling",
        passed,
        "Health endpoint responds quickly",
        {
            'health_response_time_ms': round(elapsed * 1000, 2),
            'target_ms': 1000
        }
    )


def test_metrics_endpoints(results: TestResults):
    """Test that metrics endpoints are available."""
    print("\n📊 Test 5: Metrics Endpoints")
    print("-" * 80)
    
    endpoints = [
        '/api/health',
        '/api/health/detailed',
        '/api/metrics/queue',
        '/api/metrics/circuit-breakers',
        '/api/metrics/health-cache'
    ]
    
    available = []
    unavailable = []
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            if response.status_code == 200:
                available.append(endpoint)
                print(f"  ✅ {endpoint}")
            else:
                unavailable.append(endpoint)
                print(f"  ❌ {endpoint} (status: {response.status_code})")
        except Exception as e:
            unavailable.append(endpoint)
            print(f"  ❌ {endpoint} (error: {e})")
    
    # At least basic health endpoint should work
    passed = '/api/health' in available
    results.add_result(
        "Metrics Endpoints",
        passed,
        f"{len(available)}/{len(endpoints)} endpoints available",
        {
            'available': available,
            'unavailable': unavailable
        }
    )


def test_queue_metrics(results: TestResults):
    """Test queue metrics."""
    print("\n📊 Test 6: Queue Metrics")
    print("-" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/api/metrics/queue", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Active requests: {data.get('active_requests', 'N/A')}")
            print(f"  Total requests: {data.get('total_requests', 'N/A')}")
            print(f"  Rejected requests: {data.get('rejected_requests', 'N/A')}")
            print(f"  Circuit open: {data.get('circuit_open', 'N/A')}")
            
            # Should have reasonable values
            has_metrics = all(key in data for key in ['active_requests', 'total_requests'])
            passed = has_metrics
            
            results.add_result(
                "Queue Metrics",
                passed,
                "Queue metrics available",
                data
            )
        else:
            results.add_result(
                "Queue Metrics",
                False,
                f"Endpoint returned status {response.status_code}"
            )
    except Exception as e:
        results.add_result(
            "Queue Metrics",
            False,
            f"Request failed: {e}"
        )


def test_circuit_breaker_metrics(results: TestResults):
    """Test circuit breaker metrics."""
    print("\n📊 Test 7: Circuit Breaker Metrics")
    print("-" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/api/metrics/circuit-breakers", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Circuit breakers: {list(data.keys())}")
            
            for name, state in data.items():
                print(f"    - {name}: state={state.get('state', 'unknown')}, failures={state.get('failure_count', 0)}")
            
            results.add_result(
                "Circuit Breaker Metrics",
                True,
                "Circuit breaker metrics available",
                data
            )
        else:
            results.add_result(
                "Circuit Breaker Metrics",
                False,
                f"Endpoint returned status {response.status_code}"
            )
    except Exception as e:
        results.add_result(
            "Circuit Breaker Metrics",
            False,
            f"Request failed: {e}"
        )


def test_health_cache(results: TestResults):
    """Test health cache metrics."""
    print("\n📊 Test 8: Health Cache")
    print("-" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/api/metrics/health-cache", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Status: {data.get('status', 'N/A')}")
            print(f"  Bot running: {data.get('bot_running', 'N/A')}")
            print(f"  Cache age: {data.get('cache_age_seconds', 'N/A')}s")
            print(f"  Update count: {data.get('update_count', 'N/A')}")
            
            # Cache should be relatively fresh (< 10 seconds)
            cache_age = data.get('cache_age_seconds', 999)
            cache_fresh = cache_age < 10
            
            passed = cache_fresh
            results.add_result(
                "Health Cache",
                passed,
                f"Cache age: {cache_age:.1f}s (target: < 10s)",
                data
            )
        else:
            results.add_result(
                "Health Cache",
                False,
                f"Endpoint returned status {response.status_code}"
            )
    except Exception as e:
        results.add_result(
            "Health Cache",
            False,
            f"Request failed: {e}"
        )


def main():
    """Run all tests."""
    print("=" * 80)
    print("WebUI Resource Fix - Test Suite")
    print("=" * 80)
    print(f"Testing: {BASE_URL}")
    print("=" * 80)
    
    # Check if WebUI is running
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"✅ WebUI is running (status: {response.status_code})")
    except Exception as e:
        print(f"❌ WebUI is not running or not accessible: {e}")
        print("\nPlease start the WebUI first:")
        print("  python3 webui/backend/app.py")
        return
    
    results = TestResults()
    
    # Run all tests
    test_health_endpoint_speed(results)
    test_concurrent_requests(results)
    test_connection_pool(results)
    test_timeout_handling(results)
    test_metrics_endpoints(results)
    test_queue_metrics(results)
    test_circuit_breaker_metrics(results)
    test_health_cache(results)
    
    # Print summary
    results.print_summary()
    
    # Exit code
    exit(0 if results.failed == 0 else 1)


if __name__ == '__main__':
    main()
