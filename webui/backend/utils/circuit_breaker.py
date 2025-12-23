#!/usr/bin/env python3
"""
Circuit Breaker for External Services

Prevents cascading failures when external services (Ollama, Telegram) are down.
"""

import time
import threading
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker implementation.
    
    - CLOSED: Normal operation, requests go through
    - OPEN: Service is failing, requests fail fast without calling service
    - HALF_OPEN: Testing recovery, limited requests go through
    
    Transitions:
    - CLOSED -> OPEN: After failure_threshold failures
    - OPEN -> HALF_OPEN: After recovery_timeout seconds
    - HALF_OPEN -> CLOSED: After success_threshold successes
    - HALF_OPEN -> OPEN: On any failure
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,      # Open after 5 failures
        success_threshold: int = 2,      # Close after 2 successes in half-open
        recovery_timeout: int = 60,      # Try recovery after 60 seconds
        name: str = "unnamed"
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.lock = threading.Lock()
    
    def call(self, func: Callable, *args, fallback: Any = None, **kwargs):
        """
        Call function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Arguments for function
            fallback: Value to return if circuit is open
            **kwargs: Keyword arguments for function
        
        Returns:
            Result from function, or fallback if circuit is open
        """
        with self.lock:
            # Check if we should try recovery
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    print(f"🔶 Circuit breaker '{self.name}' entering HALF_OPEN state")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    # Circuit is open, fail fast
                    return fallback
        
        # Try to execute the function
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            if fallback is not None:
                return fallback
            raise
    
    def _record_success(self):
        """Record successful call."""
        with self.lock:
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    print(f"🟢 Circuit breaker '{self.name}' recovered (CLOSED)")
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
    
    def _record_failure(self):
        """Record failed call."""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open state opens circuit again
                print(f"🔴 Circuit breaker '{self.name}' still failing (OPEN)")
                self.state = CircuitState.OPEN
                self.failure_count = 0
                self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    print(f"🔴 Circuit breaker '{self.name}' opened after {self.failure_count} failures")
                    self.state = CircuitState.OPEN
    
    def get_state(self) -> dict:
        """Get current circuit breaker state."""
        with self.lock:
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'last_failure_time': self.last_failure_time,
                'time_until_recovery': max(0, self.recovery_timeout - (time.time() - self.last_failure_time))
                    if self.state == CircuitState.OPEN else 0
            }
    
    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            print(f"🔄 Circuit breaker '{self.name}' manually reset")


def circuit_breaker(name: str, failure_threshold: int = 5, recovery_timeout: int = 60, fallback: Any = None):
    """
    Decorator to add circuit breaker to a function.
    
    Args:
        name: Name of the circuit breaker
        failure_threshold: Open circuit after this many failures
        recovery_timeout: Try recovery after this many seconds
        fallback: Value to return when circuit is open
    
    Example:
        @circuit_breaker(name='ollama', failure_threshold=3, recovery_timeout=30, fallback={'status': 'unavailable'})
        def check_ollama_health():
            response = requests.get('http://localhost:11434/api/tags', timeout=2)
            return response.json()
    """
    # Create circuit breaker instance (one per decorated function)
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        name=name
    )
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, fallback=fallback, **kwargs)
        
        # Attach circuit breaker to function for inspection
        wrapper._circuit_breaker = breaker
        return wrapper
    
    return decorator


# Global circuit breaker registry
_circuit_breakers = {}
_registry_lock = threading.Lock()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """
    Get or create a named circuit breaker.
    
    Example:
        ollama_breaker = get_circuit_breaker('ollama', failure_threshold=3)
        result = ollama_breaker.call(check_ollama, fallback={'status': 'down'})
    """
    with _registry_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
        return _circuit_breakers[name]


def get_all_circuit_breaker_states() -> dict:
    """Get state of all circuit breakers."""
    with _registry_lock:
        return {name: breaker.get_state() for name, breaker in _circuit_breakers.items()}


def reset_all_circuit_breakers():
    """Reset all circuit breakers to CLOSED state."""
    with _registry_lock:
        for breaker in _circuit_breakers.values():
            breaker.reset()


# Pre-initialized global circuit breakers for common services
delta_api_breaker = get_circuit_breaker('delta_api', failure_threshold=3, recovery_timeout=15)
bot_file_breaker = get_circuit_breaker('bot_files', failure_threshold=2, recovery_timeout=5)
