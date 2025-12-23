"""
✅ FIX NOV 7 2025 (BUG #4): Smart Circuit Breaker with Error Classification

Circuit breaker that protects against API failures while allowing normal trading.

Key Features:
- Error categorization (EXPECTED, USER_ERROR, NETWORK_ERROR, API_ERROR)
- Excludes 404/409 errors from failure count (expected errors)
- Adaptive timeout based on market volatility
- Increased failure threshold (5 instead of 3)
- Per-endpoint failure tracking

This prevents the circuit breaker from triggering on expected errors
like 404 (order not found) or 409 (order already cancelled).
"""

import time
import logging
from enum import Enum
from typing import Optional, Dict, Any
from collections import defaultdict, deque

log = logging.getLogger("runner")


class ErrorCategory(Enum):
    """Error categories for circuit breaker"""
    EXPECTED = "expected"  # 404, 409 (don't count)
    USER_ERROR = "user_error"  # 400, 401, 403 (log but don't count)
    NETWORK_ERROR = "network"  # Timeout, connection reset (count)
    API_ERROR = "api_error"  # 500, 502, 503 (count)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit tripped, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Smart circuit breaker with error classification
    
    Prevents cascading failures while allowing normal trading.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 30.0,
        half_open_max_calls: int = 3,
        volatility_threshold: float = 0.02
    ):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Number of consecutive API errors to trigger (default: 5)
            timeout: Seconds to wait before moving to HALF_OPEN (default: 30s)
            half_open_max_calls: Max test calls in HALF_OPEN state (default: 3)
            volatility_threshold: Volatility % to reduce timeout (default: 0.02 = 2%)
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        self.volatility_threshold = volatility_threshold
        
        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.open_time: Optional[float] = None
        
        # Per-endpoint tracking
        self.endpoint_failures: Dict[str, int] = defaultdict(int)
        self.endpoint_last_error: Dict[str, float] = {}
        
        # Error history for monitoring
        self.error_history = deque(maxlen=100)
        
        # Current volatility (updated externally)
        self.current_volatility: float = 0.0
        
        log.info(f"🛡️ Circuit breaker initialized (threshold={failure_threshold}, timeout={timeout}s)")
    
    def call(self, func, endpoint: str = "unknown", *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Function to execute
            endpoint: API endpoint name (for tracking)
            *args: Arguments to pass to function
            **kwargs: Keyword arguments to pass to function
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is OPEN
            Original exception: If call fails
        """
        # Check if circuit is OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                log.info("🔄 Circuit breaker moving to HALF_OPEN (testing recovery)")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN (cooling down). "
                    f"Will reset in {self._time_until_reset():.0f}s"
                )
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            self._record_success(endpoint)
            return result
        
        except Exception as e:
            self._record_failure(e, endpoint)
            raise
    
    def _record_success(self, endpoint: str):
        """Record successful call"""
        self.success_count += 1
        
        # Reset endpoint failure count
        if endpoint in self.endpoint_failures:
            self.endpoint_failures[endpoint] = 0
        
        # If in HALF_OPEN, check if we should close
        if self.state == CircuitState.HALF_OPEN:
            if self.success_count >= self.half_open_max_calls:
                log.info("✅ Circuit breaker CLOSED (service recovered)")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        
        # If in CLOSED, reset failure count on success
        elif self.state == CircuitState.CLOSED:
            if self.failure_count > 0:
                log.debug(f"Resetting failure count (was {self.failure_count})")
                self.failure_count = 0
    
    def _record_failure(self, error: Exception, endpoint: str):
        """Record failed call"""
        # Categorize error
        category = self._categorize_error(error)
        
        # Log error with category
        self.error_history.append({
            'time': time.time(),
            'error': str(error),
            'category': category.value,
            'endpoint': endpoint
        })
        
        # Don't count expected errors
        if category == ErrorCategory.EXPECTED:
            log.debug(f"Expected error (404/409) on {endpoint} - not counted: {error}")
            return
        
        # Don't count user errors (bad request)
        if category == ErrorCategory.USER_ERROR:
            log.warning(f"User error (400/401/403) on {endpoint} - not counted: {error}")
            return
        
        # Count network and API errors
        self.failure_count += 1
        self.endpoint_failures[endpoint] += 1
        self.endpoint_last_error[endpoint] = time.time()
        self.last_failure_time = time.time()
        
        log.warning(
            f"⚠️ Circuit breaker failure #{self.failure_count}/{self.failure_threshold} "
            f"({category.value}) on {endpoint}: {error}"
        )
        
        # Check if threshold exceeded
        if self.failure_count >= self.failure_threshold:
            self._trip_circuit()
        
        # If in HALF_OPEN, trip immediately on failure
        elif self.state == CircuitState.HALF_OPEN:
            log.warning("❌ Circuit breaker test failed - returning to OPEN")
            self._trip_circuit()
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """
        Categorize error type
        
        Args:
            error: Exception to categorize
            
        Returns:
            ErrorCategory
        """
        error_str = str(error).lower()
        
        # Check for HTTP status codes in error message
        if '404' in error_str or 'not found' in error_str:
            return ErrorCategory.EXPECTED
        
        if '409' in error_str or 'already cancelled' in error_str or 'already processed' in error_str:
            return ErrorCategory.EXPECTED
        
        if any(code in error_str for code in ['400', '401', '403']):
            return ErrorCategory.USER_ERROR
        
        if any(code in error_str for code in ['500', '502', '503', '504']):
            return ErrorCategory.API_ERROR
        
        if any(keyword in error_str for keyword in ['timeout', 'connection', 'reset', 'refused']):
            return ErrorCategory.NETWORK_ERROR
        
        # Check exception type
        error_type = type(error).__name__.lower()
        
        if 'timeout' in error_type or 'connection' in error_type:
            return ErrorCategory.NETWORK_ERROR
        
        # Default to API error for unknown errors
        return ErrorCategory.API_ERROR
    
    def _trip_circuit(self):
        """Trip the circuit breaker to OPEN state"""
        self.state = CircuitState.OPEN
        self.open_time = time.time()
        
        # Adapt timeout based on volatility
        timeout = self._get_adaptive_timeout()
        
        log.critical("=" * 80)
        log.critical(f"🚨 CIRCUIT BREAKER OPEN - Cooling down for {timeout:.0f}s")
        log.critical(f"   Reason: {self.failure_count} consecutive API/network errors")
        log.critical(f"   Failure threshold: {self.failure_threshold}")
        log.critical(f"   Current volatility: {self.current_volatility:.2%}")
        log.critical("=" * 80)
    
    def _get_adaptive_timeout(self) -> float:
        """
        Get adaptive timeout based on volatility
        
        High volatility = shorter timeout (need to recover faster)
        Normal volatility = normal timeout
        
        Returns:
            Timeout in seconds
        """
        if self.current_volatility > self.volatility_threshold:
            # High volatility: reduce timeout to 15s
            return min(self.timeout, 15.0)
        else:
            # Normal volatility: use configured timeout
            return self.timeout
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if not self.open_time:
            return True
        
        timeout = self._get_adaptive_timeout()
        elapsed = time.time() - self.open_time
        return elapsed >= timeout
    
    def _time_until_reset(self) -> float:
        """Calculate time remaining until reset attempt"""
        if not self.open_time:
            return 0.0
        
        timeout = self._get_adaptive_timeout()
        elapsed = time.time() - self.open_time
        return max(0, timeout - elapsed)
    
    def update_volatility(self, volatility: float):
        """
        Update current volatility (for adaptive timeout)
        
        Args:
            volatility: Market volatility (0.0 - 1.0+)
        """
        self.current_volatility = volatility
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get circuit breaker status
        
        Returns:
            Status dictionary
        """
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'failure_threshold': self.failure_threshold,
            'timeout': self._get_adaptive_timeout(),
            'time_until_reset': self._time_until_reset() if self.state == CircuitState.OPEN else None,
            'endpoint_failures': dict(self.endpoint_failures),
            'current_volatility': self.current_volatility,
            'recent_errors': list(self.error_history)[-10:]  # Last 10 errors
        }
    
    def reset(self):
        """Manually reset circuit breaker"""
        log.info("🔄 Circuit breaker manually reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.open_time = None
        self.endpoint_failures.clear()


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN and blocking requests"""
    pass
