"""
Backtesting Engine Module
=========================

A professional backtesting framework for testing trading strategies
against historical OHLCV data.

Components:
- BacktestEngine: Core engine for running backtests
- Strategy: Base class for trading strategies
- BacktestResult: Results container with metrics
- PositionTracker: Tracks positions during backtest

Author: WorkingBot
Date: January 2026
"""

from .engine import BacktestEngine, BacktestConfig, BacktestResult
from .strategy import Strategy, SignalType
from .position import Position, PositionTracker
from .metrics import calculate_metrics, MetricsResult

__all__ = [
    'BacktestEngine',
    'BacktestConfig', 
    'BacktestResult',
    'Strategy',
    'SignalType',
    'Position',
    'PositionTracker',
    'calculate_metrics',
    'MetricsResult'
]
