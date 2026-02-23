"""
MMM Stress Tests

Tests for system behavior under load:
- Concurrent heartbeats
- Rapid session operations
- Memory leak detection
- Circuit breaker under high error rates

Created: February 23, 2026
"""

import pytest
import asyncio
import threading
import time
import gc
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# =============================================================================
# Concurrent Access Tests
# =============================================================================

class TestConcurrentAccess:
    """Test thread-safety under concurrent access."""

    @pytest.fixture
    def circuit(self):
        """Create circuit breaker for concurrent testing."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitBreaker
        return CircuitBreaker('stress-test', failure_threshold=10)

    def test_concurrent_circuit_operations(self, circuit):
        """Test circuit breaker under concurrent access."""
        errors = []
        iterations = 100
        
        def success_worker():
            try:
                for _ in range(10):
                    circuit.record_success()
            except Exception as e:
                errors.append(e)
        
        def failure_worker():
            try:
                for _ in range(10):
                    circuit.record_failure('concurrent error')
            except Exception as e:
                errors.append(e)
        
        def query_worker():
            try:
                for _ in range(10):
                    _ = circuit.summary()
                    _ = circuit.window_stats
            except Exception as e:
                errors.append(e)
        
        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(iterations):
                futures.append(executor.submit(success_worker))
                futures.append(executor.submit(failure_worker))
                futures.append(executor.submit(query_worker))
            
            for future in as_completed(futures):
                future.result()  # Raises if exception occurred
        
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

    def test_concurrent_storage_reads(self):
        """Test storage under concurrent read access."""
        from webui.backend.routes.mmm.mmm_storage import get_storage
        
        storage = get_storage()
        errors = []
        
        def read_worker():
            try:
                for _ in range(10):
                    _ = storage.list_sessions()
            except Exception as e:
                errors.append(e)
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(read_worker) for _ in range(50)]
            for future in as_completed(futures):
                future.result()
        
        assert len(errors) == 0

    def test_concurrent_activity_log(self):
        """Test activity log under concurrent writes."""
        from webui.backend.routes.mmm.mmm_activity import get_activity_log
        
        log = get_activity_log()
        errors = []
        
        def write_worker(worker_id):
            try:
                for i in range(20):
                    log.add(
                        activity_type='stress_test',
                        message=f'Worker {worker_id} activity {i}',
                        session_id=f'stress-session-{worker_id}',
                        severity='info',
                    )
            except Exception as e:
                errors.append(e)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_worker, i) for i in range(20)]
            for future in as_completed(futures):
                future.result()
        
        assert len(errors) == 0


# =============================================================================
# Circuit Breaker Stress Tests
# =============================================================================

class TestCircuitBreakerStress:
    """Stress test circuit breaker behavior."""

    def test_rapid_state_transitions(self):
        """Test rapid state changes don't corrupt state."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitBreaker
        
        circuit = CircuitBreaker('rapid-test', failure_threshold=3)
        
        for cycle in range(100):
            # Trip the circuit
            for _ in range(3):
                circuit.record_failure('error')
            
            assert circuit.is_open
            
            # Reset
            circuit.reset()
            assert circuit.is_closed
            
            # Record some successes
            for _ in range(5):
                circuit.record_success()

    def test_window_under_high_load(self):
        """Test sliding window doesn't grow unbounded."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitBreaker
        
        circuit = CircuitBreaker('window-test', failure_threshold=100)
        
        # Record many events
        for i in range(1000):
            if i % 3 == 0:
                circuit.record_failure(f'error {i}')
            else:
                circuit.record_success()
        
        # Window should be bounded (maxlen=10)
        stats = circuit.window_stats
        assert stats['total'] <= 10


# =============================================================================
# Memory Tests
# =============================================================================

class TestMemoryBehavior:
    """Test for memory leaks and unbounded growth."""

    def test_activity_log_bounded(self):
        """Activity log should not grow unbounded."""
        from webui.backend.routes.mmm.mmm_activity import get_activity_log, MAX_ACTIVITIES
        
        log = get_activity_log()
        
        # Add many activities
        for i in range(MAX_ACTIVITIES + 100):
            log.add(
                activity_type='memory_test',
                message=f'Test activity {i}',
                session_id='memory-test',
                severity='info',
            )
        
        # Should be bounded by MAX_ACTIVITIES
        activities = log.get_recent(limit=1000)
        assert len(activities) <= MAX_ACTIVITIES

    def test_circuit_breaker_window_bounded(self):
        """Circuit breaker window should not grow unbounded."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitBreaker, SLIDING_WINDOW_SIZE
        
        circuit = CircuitBreaker('bound-test', failure_threshold=1000)
        
        # Add many events
        for i in range(1000):
            circuit.record_success()
        
        # Internal window should be bounded
        assert len(circuit._window) <= SLIDING_WINDOW_SIZE


# =============================================================================
# Timeout Tests
# =============================================================================

class TestTimeouts:
    """Test timeout behavior."""

    def test_storage_operations_complete_quickly(self):
        """Storage operations should complete within timeout."""
        from webui.backend.routes.mmm.mmm_storage import get_storage
        
        storage = get_storage()
        
        start = time.monotonic()
        for _ in range(10):
            _ = storage.list_sessions()
        elapsed = time.monotonic() - start
        
        # Should complete in under 5 seconds
        assert elapsed < 5.0, f"Storage operations took {elapsed:.2f}s"

    def test_activity_log_operations_complete_quickly(self):
        """Activity log operations should complete within timeout."""
        from webui.backend.routes.mmm.mmm_activity import get_activity_log
        
        log = get_activity_log()
        
        start = time.monotonic()
        for _ in range(100):
            log.add(
                activity_type='timeout_test',
                message='Speed test',
                session_id='speed-test',
                severity='info',
            )
        elapsed = time.monotonic() - start
        
        # Should complete in under 2 seconds
        assert elapsed < 2.0, f"Activity log operations took {elapsed:.2f}s"


# =============================================================================
# Watchdog Stress Tests
# =============================================================================

class TestWatchdogStress:
    """Stress test watchdog behavior."""

    def test_watchdog_status_under_load(self):
        """Watchdog status should be consistent under load."""
        from webui.backend.routes.mmm.mmm_watchdog import MMMWatchdog
        
        watchdog = MMMWatchdog.get_instance()
        errors = []
        
        def status_worker():
            try:
                for _ in range(50):
                    status = watchdog.status()
                    assert 'running' in status
                    assert 'monitored_sessions' in status
            except Exception as e:
                errors.append(e)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(status_worker) for _ in range(20)]
            for future in as_completed(futures):
                future.result()
        
        assert len(errors) == 0


# =============================================================================
# Error Rate Tests
# =============================================================================

class TestErrorRates:
    """Test behavior under high error rates."""

    def test_circuit_high_error_rate(self):
        """Circuit should trip under high error rate."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitBreaker
        
        circuit = CircuitBreaker('error-rate-test', failure_threshold=5)
        
        # 100% error rate
        for _ in range(5):
            circuit.record_failure('error')
        
        assert circuit.is_open
        
        # Window should show 0% success rate
        stats = circuit.window_stats
        assert stats['success_rate'] == 0.0

    def test_circuit_mixed_error_rate(self):
        """Circuit should track mixed success/failure rates."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitBreaker
        
        circuit = CircuitBreaker('mixed-rate-test', failure_threshold=10)
        
        # 50% error rate (5 success, 5 failure)
        for i in range(10):
            if i % 2 == 0:
                circuit.record_success()
            else:
                circuit.record_failure('error')
        
        stats = circuit.window_stats
        assert stats['success_rate'] == pytest.approx(0.5)


# =============================================================================
# Recovery Tests
# =============================================================================

class TestRecoveryBehavior:
    """Test system recovery behavior."""

    def test_circuit_recovery_cycle(self):
        """Circuit should survive multiple trip/recover cycles."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitBreaker
        
        circuit = CircuitBreaker('recovery-cycle-test', failure_threshold=3)
        
        for cycle in range(50):
            # Trip it
            for _ in range(3):
                circuit.record_failure(f'cycle {cycle} error')
            
            # Reset it
            circuit.reset()
            
            # Use it
            for _ in range(5):
                circuit.record_success()
        
        # Should still be in valid state
        summary = circuit.summary()
        assert summary['state'] == 'CLOSED'
        assert summary['total_trips'] == 50


# =============================================================================
# Run tests
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-x'])
