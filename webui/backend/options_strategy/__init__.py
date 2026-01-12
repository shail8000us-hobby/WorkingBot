"""
Options Strategy Module
=======================
Isolated module for building and executing options strategies.
(Straddle, Strangle, Iron Condor, Spreads, etc.)

Completely independent from:
- options/ (legacy options trading)
- options_chain/ (market data viewer)

Created: January 5, 2026
Author: SSR Bot System

Module Structure:
- strategy_models.py        - Data models & schemas
- strategy_definitions.py   - Pre-built strategy templates
- leg_executor.py           - Multi-leg order execution
- strategy_manager.py       - Position tracking & management
- strategy_monitor.py       - Background monitoring & auto-exit (Phase 3)
- strategy_auto_entry.py    - Auto-entry on conditions (Phase 3)
- strategy_risk.py          - Risk validation (Phase 3)
- strategy_notifications.py - Alert notifications (Phase 3)
- strategy_routes.py        - API endpoints
"""

from flask import Blueprint

# Create Blueprint for options strategy routes
options_strategy_bp = Blueprint(
    'options_strategy',
    __name__,
    url_prefix='/api/options-strategy'
)

# Import routes after blueprint creation to avoid circular imports
from . import strategy_routes

# Expose key classes and functions
from .strategy_manager import StrategyManager
from .strategy_monitor import (
    StrategyMonitor,
    get_strategy_monitor,
    start_strategy_monitor,
    stop_strategy_monitor
)
from .strategy_auto_entry import (
    StrategyAutoEntry,
    get_auto_entry_service,
    start_auto_entry,
    stop_auto_entry
)
from .strategy_risk import (
    StrategyRiskValidator,
    get_risk_validator,
    validate_strategy_risk,
    RiskLimits
)
from .strategy_notifications import (
    StrategyNotificationService,
    get_notification_service,
    send_strategy_notification
)

__all__ = [
    'options_strategy_bp',
    'StrategyManager',
    'StrategyMonitor',
    'get_strategy_monitor',
    'start_strategy_monitor', 
    'stop_strategy_monitor',
    'StrategyAutoEntry',
    'get_auto_entry_service',
    'start_auto_entry',
    'stop_auto_entry',
    'StrategyRiskValidator',
    'get_risk_validator',
    'validate_strategy_risk',
    'RiskLimits',
    'StrategyNotificationService',
    'get_notification_service',
    'send_strategy_notification'
]
