#!/usr/bin/env python3
"""
Request Queue Manager

Prevents resource exhaustion by limiting concurrent requests.
"""

from queue import Queue, Full
from threading import Semaphore, Lock
from functools import wraps
from flask import jsonify
import time
from collections import defaultdict


class RequestQueueManager:
    """
    Manages concurrent request limits to prevent resource exhaustion.
    
    Features:
    - Global concurrent request limit
    - Per-endpoint concurrent request limit
    - Request queuing with timeout
    - Circuit breaker for overload protection
    """
    
    def __init__(self, max_concurrent_global: int = 50, max_concurrent_per_endpoint: int = 10):
        self.max_concurrent_global = max_concurrent_global
        self.max_concurrent_per_endpoint = max_concurrent_per_endpoint
        
        # Global semaphore for all requests
        self.global_semaphore = Semaphore(max_concurrent_global)
        
        # Per-endpoint semaphores
        self.endpoint_semaphores = {}
        self.endpoint_lock = Lock()
        
        # Metrics
        self.active_requests = 0
        self.total_requests = 0
        self.rejected_requests = 0
        self.metrics_lock = Lock()
        
        # Circuit breaker
        self.circuit_open = False
        self.circuit_failures = 0
        self.circuit_threshold = 100  # Open circuit after 100 failures in a row
        self.last_circuit_reset = time.time()
    
    def get_endpoint_semaphore(self, endpoint: str) -> Semaphore:
        """Get or create semaphore for specific endpoint."""
        if endpoint not in self.endpoint_semaphores:
            with self.endpoint_lock:
                if endpoint not in self.endpoint_semaphores:
                    self.endpoint_semaphores[endpoint] = Semaphore(self.max_concurrent_per_endpoint)
        return self.endpoint_semaphores[endpoint]
    
    def check_circuit_breaker(self):
        """Reset circuit breaker if enough time has passed."""
        if self.circuit_open:
            # Reset circuit after 60 seconds
            if time.time() - self.last_circuit_reset > 60:
                self.circuit_open = False
                self.circuit_failures = 0
                print("🟢 Circuit breaker reset")
    
    def record_failure(self):
        """Record a request failure for circuit breaker."""
        self.circuit_failures += 1
        if self.circuit_failures >= self.circuit_threshold:
            self.circuit_open = True
            self.last_circuit_reset = time.time()
            print(f"🔴 Circuit breaker opened after {self.circuit_failures} failures")
    
    def record_success(self):
        """Record a successful request."""
        self.circuit_failures = max(0, self.circuit_failures - 1)
    
    def get_metrics(self) -> dict:
        """Get current queue metrics."""
        with self.metrics_lock:
            return {
                'active_requests': self.active_requests,
                'total_requests': self.total_requests,
                'rejected_requests': self.rejected_requests,
                'circuit_open': self.circuit_open,
                'circuit_failures': self.circuit_failures,
                'max_concurrent_global': self.max_concurrent_global,
                'max_concurrent_per_endpoint': self.max_concurrent_per_endpoint
            }


# Global instance
_queue_manager = None


def get_queue_manager() -> RequestQueueManager:
    """Get global queue manager instance."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = RequestQueueManager()
    return _queue_manager


def limit_concurrency(endpoint_name: str = None, timeout: float = 5.0):
    """
    Decorator to limit concurrent requests to an endpoint.
    
    Args:
        endpoint_name: Name of endpoint (uses function name if None)
        timeout: How long to wait for a slot (seconds)
    
    Example:
        @app.route('/api/heavy-operation')
        @limit_concurrency(endpoint_name='heavy_operation', timeout=3.0)
        def heavy_operation():
            # Only 10 of these can run concurrently
            return jsonify({'status': 'ok'})
    """
    def decorator(func):
        nonlocal endpoint_name
        if endpoint_name is None:
            endpoint_name = func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = get_queue_manager()
            
            # Check circuit breaker
            manager.check_circuit_breaker()
            if manager.circuit_open:
                return jsonify({
                    'success': False,
                    'error': 'Service temporarily unavailable (circuit breaker open)',
                    'retry_after': 60
                }), 503
            
            # Try to acquire global semaphore
            if not manager.global_semaphore.acquire(blocking=False):
                with manager.metrics_lock:
                    manager.rejected_requests += 1
                manager.record_failure()
                return jsonify({
                    'success': False,
                    'error': 'Too many concurrent requests (global limit reached)',
                    'active_requests': manager.active_requests,
                    'max_concurrent': manager.max_concurrent_global
                }), 429
            
            # Try to acquire endpoint-specific semaphore
            endpoint_sem = manager.get_endpoint_semaphore(endpoint_name)
            if not endpoint_sem.acquire(blocking=False):
                manager.global_semaphore.release()
                with manager.metrics_lock:
                    manager.rejected_requests += 1
                manager.record_failure()
                return jsonify({
                    'success': False,
                    'error': f'Too many concurrent requests to {endpoint_name}',
                    'max_concurrent': manager.max_concurrent_per_endpoint
                }), 429
            
            # Track metrics
            with manager.metrics_lock:
                manager.active_requests += 1
                manager.total_requests += 1
            
            try:
                # Execute the endpoint
                result = func(*args, **kwargs)
                manager.record_success()
                return result
            except Exception as e:
                manager.record_failure()
                raise
            finally:
                # Release semaphores
                with manager.metrics_lock:
                    manager.active_requests -= 1
                endpoint_sem.release()
                manager.global_semaphore.release()
        
        return wrapper
    return decorator


def queue_metrics_endpoint():
    """
    Add this to your Flask app to expose queue metrics.
    
    Example:
        @app.route('/api/queue/metrics')
        def queue_metrics():
            return jsonify(queue_metrics_endpoint())
    """
    manager = get_queue_manager()
    return manager.get_metrics()
