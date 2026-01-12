"""
Custom Exceptions for WorkingBot Trading System
===============================================
Comprehensive exception hierarchy for better error handling and debugging.

Imported from OptionBot project with adaptations.
Original: options_trading_bot/core/exceptions.py

Usage:
    from webui.backend.utils.exceptions import OrderError, ValidationError
    
    try:
        execute_order(order)
    except OrderError as e:
        logger.error(f"Order failed: {e}")
        # Handle specifically
    except TradingBotError as e:
        # Catch all trading errors
        pass
"""


class TradingBotError(Exception):
    """
    Base exception for all trading bot errors.
    
    All custom exceptions inherit from this, allowing:
    - Catch-all for trading-related errors
    - Distinguish from Python built-in exceptions
    - Add common attributes (error_code, details, etc.)
    
    Attributes:
        message: Human-readable error description
        error_code: Optional machine-readable error code
        details: Optional dictionary with extra context
    """
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses."""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details
        }


# ============================================================================
# API-Related Exceptions
# ============================================================================

class APIError(TradingBotError):
    """
    API-related errors (network, response parsing, unexpected status codes).
    
    Examples:
        - HTTP 500 from Delta Exchange
        - JSON parsing failures
        - Timeout errors
    """
    pass


class RateLimitError(APIError):
    """
    Rate limit exceeded (HTTP 429).
    
    Contains information about when the limit resets.
    """
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: float = None):
        super().__init__(message, error_code="RATE_LIMIT_EXCEEDED")
        self.retry_after = retry_after
        if retry_after:
            self.details['retry_after_seconds'] = retry_after


class AuthenticationError(APIError):
    """
    Authentication failed (HTTP 401/403).
    
    Indicates invalid API keys or insufficient permissions.
    """
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, error_code="AUTH_FAILED")


class ConnectionError(APIError):
    """
    Network connection errors.
    
    Examples:
        - DNS resolution failed
        - Connection timeout
        - SSL/TLS errors
    """
    pass


# ============================================================================
# Trading/Strategy Exceptions
# ============================================================================

class StrategyError(TradingBotError):
    """
    Strategy execution or configuration errors.
    
    Examples:
        - Invalid strategy parameters
        - Strategy validation failed
        - Strategy state transition error
    """
    pass


class OrderError(TradingBotError):
    """
    Order execution errors.
    
    Examples:
        - Insufficient margin
        - Invalid symbol
        - Order rejected by exchange
    """
    
    def __init__(self, message: str, order_id: str = None, rejection_reason: str = None):
        super().__init__(message, error_code="ORDER_ERROR")
        self.order_id = order_id
        self.rejection_reason = rejection_reason
        if order_id:
            self.details['order_id'] = order_id
        if rejection_reason:
            self.details['rejection_reason'] = rejection_reason


class PositionError(TradingBotError):
    """
    Position management errors.
    
    Examples:
        - Position not found
        - Cannot close position (no orders filled)
        - Position size mismatch
    """
    pass


class RiskLimitError(TradingBotError):
    """
    Risk limit violation.
    
    Examples:
        - Maximum position size exceeded
        - Daily loss limit reached
        - Portfolio delta limit exceeded
    """
    
    def __init__(self, message: str, limit_type: str = None, current_value: float = None, limit_value: float = None):
        super().__init__(message, error_code="RISK_LIMIT_EXCEEDED")
        self.limit_type = limit_type
        if limit_type:
            self.details['limit_type'] = limit_type
        if current_value is not None:
            self.details['current_value'] = current_value
        if limit_value is not None:
            self.details['limit_value'] = limit_value


# ============================================================================
# Validation Exceptions
# ============================================================================

class ValidationError(TradingBotError):
    """
    Data validation errors.
    
    Examples:
        - Invalid strike price
        - Expiry date in the past
        - Invalid option type
    """
    
    def __init__(self, message: str, field: str = None, value=None):
        super().__init__(message, error_code="VALIDATION_ERROR")
        self.field = field
        self.value = value
        if field:
            self.details['field'] = field
        if value is not None:
            self.details['invalid_value'] = str(value)


class ConfigurationError(TradingBotError):
    """
    Configuration errors.
    
    Examples:
        - Missing required config key
        - Invalid config value
        - Config file not found
    """
    pass


# ============================================================================
# Data/Pricing Exceptions
# ============================================================================

class DataError(TradingBotError):
    """
    Data retrieval or processing errors.
    
    Examples:
        - Market data unavailable
        - Stale data detected
        - Data parsing failed
    """
    pass


class PricingError(TradingBotError):
    """
    Option pricing related errors.
    
    Examples:
        - Cannot calculate IV (no solution)
        - Invalid pricing inputs
        - Greeks calculation failed
    """
    pass


class ExpiryError(TradingBotError):
    """
    Expiry-related errors.
    
    Examples:
        - Option already expired
        - Invalid expiry date format
        - Expiry processing failed
    """
    pass


# ============================================================================
# WebSocket Exceptions
# ============================================================================

class WebSocketError(TradingBotError):
    """
    WebSocket-related errors.
    
    Examples:
        - Connection lost
        - Subscription failed
        - Message parsing error
    """
    pass


# ============================================================================
# System Exceptions
# ============================================================================

class SystemError(TradingBotError):
    """
    System-level errors (not trading related).
    
    Examples:
        - Database connection failed
        - File system error
        - Memory allocation failed
    """
    pass


class HealthCheckError(TradingBotError):
    """
    Health check failures.
    
    Examples:
        - API connectivity lost
        - Database unreachable
        - Critical service down
    """
    pass


# ============================================================================
# Helper Functions
# ============================================================================

def handle_api_error(response_code: int, response_body: dict) -> TradingBotError:
    """
    Convert API response to appropriate exception.
    
    Args:
        response_code: HTTP status code
        response_body: Parsed JSON response body
        
    Returns:
        Appropriate TradingBotError subclass
    """
    message = response_body.get('message', response_body.get('error', 'Unknown error'))
    
    if response_code == 429:
        retry_after = response_body.get('retry_after')
        return RateLimitError(message, retry_after=retry_after)
    
    if response_code == 401:
        return AuthenticationError(message)
    
    if response_code == 403:
        return AuthenticationError(f"Permission denied: {message}")
    
    if response_code == 400:
        # Check for specific order errors
        error_code = response_body.get('error', '').lower()
        if 'margin' in error_code or 'insufficient' in error_code:
            return OrderError(message, rejection_reason='insufficient_margin')
        if 'invalid' in error_code:
            return ValidationError(message)
        return OrderError(message)
    
    if response_code >= 500:
        return APIError(f"Server error ({response_code}): {message}")
    
    return APIError(f"API error ({response_code}): {message}")
