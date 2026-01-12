"""
Shared utility modules for Flask blueprints

These utilities are used by multiple blueprints to avoid code duplication.

Production-Ready Imports (from OptionBot):
- rate_limiter: Thread-safe API rate limiting
- exceptions: Comprehensive exception hierarchy
- health_monitor: System health monitoring
"""

from .process_helpers import (
    is_process_running,
    read_pid_file,
    stop_process_by_pid,
    is_bot_running,
    is_guardian_running,
    is_monitor_running,
    BOT_PID_FILE,
    GUARDIAN_PID_FILE,
    MONITOR_PID_FILE
)

from .file_helpers import (
    get_recent_logs,
    read_file_safely,
    file_exists_and_readable
)

from .response_helpers import (
    convert_numpy_types
)

# Production-ready utilities (imported from OptionBot)
from .rate_limiter import (
    RateLimiter,
    DELTA_API_LIMITER,
    DELTA_ORDER_LIMITER,
    DELTA_PUBLIC_LIMITER
)

from .exceptions import (
    TradingBotError,
    APIError,
    RateLimitError,
    AuthenticationError,
    StrategyError,
    OrderError,
    PositionError,
    RiskLimitError,
    ValidationError,
    ConfigurationError,
    DataError,
    PricingError,
    ExpiryError,
    WebSocketError,
    HealthCheckError,
    handle_api_error
)

from .health_monitor import (
    SystemHealthMonitor,
    HealthStatus,
    health_monitor
)

__all__ = [
    # Process helpers
    'is_process_running',
    'read_pid_file',
    'stop_process_by_pid',
    'is_bot_running',
    'is_guardian_running',
    'is_monitor_running',
    'BOT_PID_FILE',
    'GUARDIAN_PID_FILE',
    'MONITOR_PID_FILE',
    # File helpers
    'get_recent_logs',
    'read_file_safely',
    'file_exists_and_readable',
    # Response helpers
    'convert_numpy_types',
    # Rate limiter (from OptionBot)
    'RateLimiter',
    'DELTA_API_LIMITER',
    'DELTA_ORDER_LIMITER',
    'DELTA_PUBLIC_LIMITER',
    # Exceptions (from OptionBot)
    'TradingBotError',
    'APIError',
    'RateLimitError',
    'AuthenticationError',
    'StrategyError',
    'OrderError',
    'PositionError',
    'RiskLimitError',
    'ValidationError',
    'ConfigurationError',
    'DataError',
    'PricingError',
    'ExpiryError',
    'WebSocketError',
    'HealthCheckError',
    'handle_api_error',
    # Health monitor (from OptionBot)
    'SystemHealthMonitor',
    'HealthStatus',
    'health_monitor',
]
