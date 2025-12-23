"""
Volatility Safety Module

Real-time IV (Implied Volatility) and RV (Realized Volatility) tracking
to prevent trading during extreme market conditions.
"""

from bot.volatility.iv_rv_tracker import VolatilityTracker, get_volatility_tracker

__all__ = ['VolatilityTracker', 'get_volatility_tracker']

