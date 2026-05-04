"""
Circuit Breaker Pattern for API Calls

Automatically stops making API calls when the exchange is having issues,
preventing rate limits and IP bans.

States:
- CLOSED: Normal operation, calls go through
- OPEN: Too many failures, block all calls
- HALF_OPEN: Testing if service recovered

Flow:
CLOSED → (N failures) → OPEN → (timeout) → HALF_OPEN
HALF_OPEN → (success) → CLOSED
HALF_OPEN → (failure) → OPEN

Benefits:
- Prevents hammering a failing API
- Avoids rate limit bans
- Automatic recovery when service is restored
- Graceful degradation

Example:
    from bot.safety.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
    
    # Create circuit breaker
    exchange_circuit = CircuitBreaker(
        name="exchange_api",
        failure_threshold=3,  # Open after 3 failures
        timeout=60            # Stay open for 60 seconds
    )
    
    # Use it to wrap API calls
    def fetch_positions_safe():
        try:
            return exchange_circuit.call(exchange.fetch_positions)
        except CircuitBreakerOpen:
            log.warning("Circuit breaker blocked call")
            return []  # Return safe default
        except Exception as e:
            log.error(f"API call failed: {e}")
            return []
"""

import time
import logging
from typing import Any, Callable, Dict, Optional
from enum import Enum

log = logging.getLogger("circuit_breaker")


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "CLOSED"       # Normal operation
    OPEN = "OPEN"           # Blocking calls
    HALF_OPEN = "HALF_OPEN" # Testing recovery


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and blocking calls"""
    pass


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.
    
    ✅ FIX NOV 6: Added IGNORED_ERRORS for expected API states
    
    Automatically opens (blocks calls) after N consecutive failures,
    then tests recovery after a timeout period.
    """
    
    # ✅ FIX NOV 6: Expected API errors that should NOT trigger circuit breaker
    # ✅ FIX JAN 20 2026: Added more expected errors per Delta Exchange recommendation
    IGNORED_ERRORS = [
        'order_not_found',
        'order_already_cancelled',
        'order_already_filled',
        'order_expired',  # 410 Gone - order expired
        'insufficient_margin',
        'invalid_price',
        'invalid_contract',  # 422 - invalid parameters
        'position_not_found',
        'position_already_closed',
        '410',  # HTTP 410 Gone
        '422',  # HTTP 422 Unprocessable Entity
    ]
    
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,  # ✅ FIX NOV 6: Increased from 3 to 5
        timeout: int = 30,             # ✅ FIX NOV 6: Reduced from 60s to 30s
        half_open_max_calls: int = 2
    ):
        """
        🛡️ FIX NOV 9 PHASE 2: Enhanced 3-state circuit breaker
        
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name (for logging)
            failure_threshold: Number of failures before opening (default: 5)
            timeout: Seconds to wait before testing recovery (default: 30s)
            half_open_max_calls: Number of successful calls needed to close
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        
        # State
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change: float = time.time()
        
        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.total_blocks = 0
        self.total_ignored_errors = 0  # ✅ FIX NOV 6: Track ignored errors
        self.times_opened = 0  # 🛡️ FIX NOV 9 PHASE 2: Track open count
        
        log.info(
            f"🛡️ Circuit breaker '{name}' initialized (3-state): "
            f"threshold={failure_threshold}, timeout={timeout}s, "
            f"half_open_calls={half_open_max_calls}"
        )
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to call
            *args, **kwargs: Arguments to pass to function
        
        Returns:
            Function result
        
        Raises:
            CircuitBreakerOpen: If circuit is open
            Exception: Original exception if call fails
        """
        self.total_calls += 1
        
        # Check current state
        if self.state == CircuitState.OPEN:
            # Check if timeout expired
            if time.time() - self.last_failure_time >= self.timeout:
                self._transition_to_half_open()
            else:
                # Still in timeout
                self.total_blocks += 1
                remaining = self.timeout - (time.time() - self.last_failure_time)
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Retry in {remaining:.0f}s"
                )
        
        # Try the call
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise
    
    def _on_success(self):
        """Handle successful call"""
        self.total_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            # Success in HALF_OPEN state
            self.success_count += 1
            
            log.info(
                f"Circuit breaker '{self.name}': Success in HALF_OPEN "
                f"({self.success_count}/{self.half_open_max_calls})"
            )
            
            if self.success_count >= self.half_open_max_calls:
                # Enough successes = recovered
                self._transition_to_closed()
        
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            if self.failure_count > 0:
                log.debug(
                    f"Circuit breaker '{self.name}': "
                    f"Success, resetting failure count ({self.failure_count} → 0)"
                )
                self.failure_count = 0
    
    def _on_failure(self, error: Exception):
        """Handle failed call"""
        # ✅ FIX NOV 6: Check if error should be ignored
        error_str = str(error).lower()
        is_ignored = any(ignored in error_str for ignored in self.IGNORED_ERRORS)

        if is_ignored:
            # Expected API state - don't count as failure
            self.total_ignored_errors += 1
            log.debug(
                f"Circuit breaker '{self.name}': Ignored expected error - {error}"
            )
            return  # Don't increment failure count

        # Real failure - count it
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()

        log.warning(
            f"Circuit breaker '{self.name}': Call failed "
            f"({self.failure_count}/{self.failure_threshold}) - {error}"
        )

        if self.state == CircuitState.HALF_OPEN:
            # Failure in HALF_OPEN = back to OPEN
            self._transition_to_open("Service still down")

        elif self.state == CircuitState.CLOSED:
            # Check if we should open
            if self.failure_count >= self.failure_threshold:
                self._transition_to_open(
                    f"{self.failure_count} consecutive failures"
                )
    
    def _transition_to_open(self, reason: str):
        """🛡️ FIX NOV 9 PHASE 2: Enhanced OPEN transition with alerting"""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.success_count = 0
        self.last_state_change = time.time()
        self.times_opened += 1  # 🛡️ FIX NOV 9 PHASE 2
        
        log.critical("=" * 80)
        log.critical(
            f"🚨 Circuit breaker '{self.name}': {old_state.value} → OPEN "
            f"({reason})"
        )
        log.critical(f"   Blocking all calls for {self.timeout}s")
        log.critical(f"   Times opened: {self.times_opened}")
        log.critical("=" * 80)
        
        # 🛡️ FIX NOV 9 PHASE 2: Send Telegram alert
        try:
            from bot.utils.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            notifier.send(
                f"🚨 Circuit Breaker Opened\n\n"
                f"Service: {self.name}\n"
                f"Reason: {reason}\n"
                f"Recovery in: {self.timeout}s\n"
                f"Times opened: {self.times_opened}"
            )
        except Exception:
            pass
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.failure_count = 0
        self.last_state_change = time.time()

        log.info(
            f"Circuit breaker '{self.name}': {old_state.value} → HALF_OPEN "
            f"(timeout expired, testing recovery)"
        )
    
    def _transition_to_closed(self):
        """🛡️ FIX NOV 9 PHASE 2: Enhanced CLOSED transition with alerting"""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = time.time()
        
        log.info("=" * 80)
        log.info(
            f"✅ Circuit breaker '{self.name}': {old_state.value} → CLOSED "
            f"(service recovered)"
        )
        log.info("=" * 80)
        
        # 🛡️ FIX NOV 9 PHASE 2: Send Telegram alert on recovery
        try:
            from bot.utils.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            notifier.send(
                f"✅ Circuit Breaker Recovered\n\n"
                f"Service: {self.name}\n"
                f"Status: Normal operation restored"
            )
        except Exception:
            pass
    
    def reset(self):
        """Reset circuit breaker to CLOSED state (for testing/manual intervention)"""
        log.info(f"Circuit breaker '{self.name}': Manual reset to CLOSED")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = time.time()
    
    def get_stats(self) -> Dict[str, Any]:
        """🛡️ FIX NOV 9 PHASE 2: Enhanced statistics"""
        uptime = time.time() - self.last_state_change
        
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'total_calls': self.total_calls,
            'total_failures': self.total_failures,
            'total_successes': self.total_successes,
            'total_blocks': self.total_blocks,
            'total_ignored_errors': self.total_ignored_errors,
            'times_opened': self.times_opened,  # 🛡️ FIX NOV 9 PHASE 2
            'failure_rate': self.total_failures / max(self.total_calls, 1),
            'uptime_seconds': uptime,
            'last_failure_time': self.last_failure_time,
            'time_in_current_state': uptime  # 🛡️ FIX NOV 9 PHASE 2
        }
    
    def __str__(self) -> str:
        """String representation"""
        return (
            f"CircuitBreaker(name={self.name}, state={self.state.value}, "
            f"failures={self.failure_count}/{self.failure_threshold})"
        )
    
    def __repr__(self) -> str:
        return self.__str__()


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    
    Useful for tracking circuit breakers for different APIs or services.
    """
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 3,
        timeout: int = 60,
        half_open_max_calls: int = 2
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                timeout=timeout,
                half_open_max_calls=half_open_max_calls
            )
        return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self._breakers.get(name)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers"""
        return {
            name: breaker.get_stats()
            for name, breaker in self._breakers.items()
        }
    
    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self._breakers.values():
            breaker.reset()


# Global registry
_registry = CircuitBreakerRegistry()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 3,
    timeout: int = 60,
    half_open_max_calls: int = 2
) -> CircuitBreaker:
    """
    Get or create a circuit breaker from the global registry.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Number of failures before opening
        timeout: Seconds to wait before testing recovery
        half_open_max_calls: Number of successful calls needed to close
    
    Returns:
        CircuitBreaker instance
    
    Example:
        from bot.safety.circuit_breaker import get_circuit_breaker
        
        # Get circuit breaker for exchange API
        cb = get_circuit_breaker("exchange_api", failure_threshold=3, timeout=60)
        
        # Use it
        try:
            result = cb.call(exchange.fetch_positions)
        except CircuitBreakerOpen:
            log.warning("API temporarily unavailable")
            result = []
    """
    return _registry.get_or_create(
        name=name,
        failure_threshold=failure_threshold,
        timeout=timeout,
        half_open_max_calls=half_open_max_calls
    )


def get_all_circuit_breaker_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all circuit breakers"""
    return _registry.get_all_stats()


def reset_all_circuit_breakers():
    """Reset all circuit breakers (for testing/manual intervention)"""
    _registry.reset_all()

