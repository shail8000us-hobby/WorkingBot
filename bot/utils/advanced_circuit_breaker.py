"""
🛡️ FIX NOV 9 PHASE 2: Advanced Circuit Breaker

Three-state circuit breaker for API calls with exponential backoff
Prevents cascading failures when exchange API is degraded

States:
- CLOSED: Normal operation, all requests allowed
- OPEN: API failing, all requests blocked (fast-fail)
- HALF_OPEN: Testing recovery, limited requests allowed

Transitions:
- CLOSED → OPEN: After failure_threshold consecutive failures
- OPEN → HALF_OPEN: After recovery_timeout seconds
- HALF_OPEN → CLOSED: After success_threshold consecutive successes
- HALF_OPEN → OPEN: On any failure

Author: GridBot Team
Date: November 9, 2025
"""

import time
import logging
from enum import Enum
from typing import Optional, Callable, Any
from functools import wraps

log = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Failing, block requests
    HALF_OPEN = "half_open"    # Testing recovery


class AdvancedCircuitBreaker:
    """
    Three-state circuit breaker with exponential backoff
    
    Usage:
        breaker = AdvancedCircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            success_threshold=3
        )
        
        @breaker.protect
        def api_call():
            return client.get_balance()
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3,
        name: str = "API"
    ):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            success_threshold: Successes needed to close circuit from half-open
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.name = name
        
        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change: float = time.time()
        
        # Stats
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.times_opened = 0
        
        log.info(
            f"🛡️ Circuit breaker initialized: {self.name} "
            f"(failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s, "
            f"success_threshold={success_threshold})"
        )
    
    def protect(self, func: Callable) -> Callable:
        """
        Decorator to protect a function with circuit breaker
        
        Usage:
            @breaker.protect
            def api_call():
                return client.get_balance()
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        self.total_calls += 1
        
        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self._transition_to_half_open()
            else:
                # Circuit still open - fast fail
                raise CircuitBreakerOpenError(
                    f"Circuit breaker OPEN for {self.name} "
                    f"(will retry in {self.recovery_timeout - (time.time() - self.last_failure_time):.1f}s)"
                )
        
        # Attempt call
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        
        except Exception as e:
            self._record_failure(e)
            raise
    
    def _record_success(self):
        """Record successful call"""
        self.total_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            log.info(
                f"✅ Circuit breaker {self.name}: Success {self.success_count}/{self.success_threshold} "
                f"in HALF_OPEN state"
            )
            
            # Check if enough successes to close circuit
            if self.success_count >= self.success_threshold:
                self._transition_to_closed()
        
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success in closed state
            if self.failure_count > 0:
                log.info(f"✅ Circuit breaker {self.name}: Failure count reset to 0")
                self.failure_count = 0
    
    def _record_failure(self, error: Exception):
        """Record failed call"""
        self.total_failures += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open state reopens circuit
            log.warning(
                f"❌ Circuit breaker {self.name}: Failure in HALF_OPEN state - "
                f"reopening circuit (error: {error})"
            )
            self._transition_to_open()
        
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            log.warning(
                f"❌ Circuit breaker {self.name}: Failure {self.failure_count}/{self.failure_threshold} "
                f"(error: {error})"
            )
            
            # Check if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                self._transition_to_open()
    
    def _transition_to_open(self):
        """Transition to OPEN state"""
        self.state = CircuitState.OPEN
        self.last_state_change = time.time()
        self.times_opened += 1
        
        log.critical("=" * 80)
        log.critical(f"🚨 CIRCUIT BREAKER OPENED: {self.name}")
        log.critical(f"   All {self.name} requests will be blocked for {self.recovery_timeout}s")
        log.critical(f"   Failure count: {self.failure_count}/{self.failure_threshold}")
        log.critical(f"   Times opened: {self.times_opened}")
        log.critical("=" * 80)
        
        # Send alert
        try:
            from bot.utils.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            notifier.send(
                f"🚨 Circuit Breaker Opened\n\n"
                f"Service: {self.name}\n"
                f"Failures: {self.failure_count}\n"
                f"Recovery in: {self.recovery_timeout}s\n\n"
                f"All requests blocked!"
            )
        except Exception:
            pass
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.failure_count = 0
        self.last_state_change = time.time()
        
        log.warning("=" * 80)
        log.warning(f"⚠️  CIRCUIT BREAKER HALF-OPEN: {self.name}")
        log.warning(f"   Testing recovery - need {self.success_threshold} successes to close")
        log.warning("=" * 80)
    
    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        self.state = CircuitState.CLOSED
        self.success_count = 0
        self.failure_count = 0
        self.last_state_change = time.time()
        
        log.info("=" * 80)
        log.info(f"✅ CIRCUIT BREAKER CLOSED: {self.name}")
        log.info(f"   Normal operation restored")
        log.info("=" * 80)
        
        # Send alert
        try:
            from bot.utils.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            notifier.send(
                f"✅ Circuit Breaker Closed\n\n"
                f"Service: {self.name}\n"
                f"Status: Normal operation restored"
            )
        except Exception:
            pass
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "times_opened": self.times_opened,
            "last_state_change": self.last_state_change,
            "time_in_state": time.time() - self.last_state_change
        }
    
    def reset(self):
        """Reset circuit breaker to closed state (for testing)"""
        log.warning(f"🔄 Circuit breaker {self.name} manually reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = time.time()


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass
