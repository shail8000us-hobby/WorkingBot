"""
Capital management module for GridBot.

Handles:
- Equity tracking and snapshots
- Drawdown calculation and monitoring
- Capital protection features

Capital Protection Module

Tracks account equity, manages drawdown limits, and enforces hard floors.

Features:
- Equity Floor Monitor: Hard stop on minimum equity breach
- Drawdown Cap: 30-day rolling window protection
- Pending Budget: Limits capital at risk in open orders
- Exposure Limiter: Available in bot.safety.exposure_limiter
- Config Guard: Two-man rule for risky config changes (in bot.safety.config_guard)
"""

from .equity_tracker import EquityTracker, get_equity_tracker
from .equity_floor import EquityFloorMonitor, get_equity_floor_monitor
from .pending_budget import PendingBudgetControl, get_pending_budget_control

__all__ = [
    'EquityTracker', 
    'get_equity_tracker',
    'EquityFloorMonitor',
    'get_equity_floor_monitor',
    'PendingBudgetControl',
    'get_pending_budget_control'
]
