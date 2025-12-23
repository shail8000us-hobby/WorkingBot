"""
Institutional-Grade Predictive Analytics Package

This package provides professional-grade predictive analytics:
- Market Regime Detection (Trending/Mean-Reverting/High Volatility)
- Price Forecasting (Short-term, Medium-term)
- Grid Parameter Optimization (Kelly Criterion)
- Optimal Entry/Exit Timing

Author: GridBot Pro - Institutional AI
Version: 1.0.0
"""

from .market_regime import MarketRegimeDetector, get_market_regime_detector
from .optimizer import GridOptimizer, get_grid_optimizer

__all__ = [
    'MarketRegimeDetector',
    'get_market_regime_detector',
    'GridOptimizer',
    'get_grid_optimizer'
]

