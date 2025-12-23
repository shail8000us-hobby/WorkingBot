"""
Safety Module - Comprehensive Trading Safety Features

This module provides critical safety features for the GridBot:
- Gatekeeper: Single checkpoint for all order placement
- Loss Limits Validator: Ensures Guardian and Trader limits are consistent
- Circuit Breaker: Prevents API bans during exchange outages
"""

from bot.safety.gatekeeper import can_place_orders, get_gatekeeper_stats, reset_gatekeeper_stats
from bot.safety.loss_limits import validate_loss_limits, get_loss_limits_config
from bot.safety.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

__all__ = [
    'can_place_orders',
    'get_gatekeeper_stats',
    'reset_gatekeeper_stats',
    'validate_loss_limits',
    'get_loss_limits_config',
    'CircuitBreaker',
    'CircuitBreakerOpen',
]

