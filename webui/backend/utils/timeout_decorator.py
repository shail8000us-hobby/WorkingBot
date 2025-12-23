#!/usr/bin/env python3
"""
Timeout decorators for Flask endpoints

Prevents endpoints from hanging indefinitely and consuming resources.
"""

from functools import wraps
from flask import jsonify
import signal
from contextlib import contextmanager


class TimeoutError(Exception):
    """Raised when a function execution exceeds timeout."""
    pass


def _timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise TimeoutError("Request timed out")


@contextmanager
def time_limit(seconds: int):
    """
    Context manager to limit execution time.
    
    Usage:
        with time_limit(5):
            slow_operation()
    """
    # Set the signal handler and alarm
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        # Disable the alarm
        signal.alarm(0)


def timeout(seconds: int = 10, error_response: dict = None):
    """
    Decorator to add timeout to Flask endpoints.
    
    Args:
        seconds: Timeout in seconds (default: 10)
        error_response: Custom error response (default: 504 Gateway Timeout)
    
    Example:
        @app.route('/api/slow-endpoint')
        @timeout(seconds=5)
        def slow_endpoint():
            # This will timeout after 5 seconds
            time.sleep(10)
            return jsonify({'status': 'ok'})
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                with time_limit(seconds):
                    return func(*args, **kwargs)
            except TimeoutError:
                if error_response:
                    response = jsonify(error_response)
                else:
                    response = jsonify({
                        'success': False,
                        'error': f'Request timed out after {seconds} seconds',
                        'timeout': seconds
                    })
                response.status_code = 504  # Gateway Timeout
                return response
        return wrapper
    return decorator


def fast_timeout(seconds: int = 3):
    """
    Quick timeout decorator for fast endpoints (health checks, status queries).
    
    Example:
        @app.route('/api/health')
        @fast_timeout(seconds=1)
        def health():
            return jsonify({'status': 'healthy'})
    """
    return timeout(seconds=seconds, error_response={
        'success': False,
        'error': 'Service temporarily unavailable',
        'timeout': seconds
    })


def slow_timeout(seconds: int = 30):
    """
    Longer timeout for operations that may take time (file operations, analysis).
    
    Example:
        @app.route('/api/analyze')
        @slow_timeout(seconds=30)
        def analyze():
            # Complex analysis
            return jsonify({'result': data})
    """
    return timeout(seconds=seconds)
