"""
Flask Blueprint Exports

This module exports all route blueprints for registration in the main Flask app.

Refactored from app.py (8,850 lines → 16 modular blueprints)
Date: 2025-10-31
"""

from .utility import utility_bp
from .health import health_bp
from .docs import docs_bp
from .metrics import metrics_bp
from .websocket_api import websocket_api_bp
from .logs import logs_bp
from .pnl import pnl_bp
from .orders import orders_bp
from .positions import positions_bp
# from .config import config_bp  # NOV 15: DISABLED - Migrated to yaml_config_api
from .system import system_bp
from .monitor import monitor_bp
from .guardian import guardian_bp
from .pm2 import pm2_bp
from .bot_control import bot_control_bp
from .todos import todos_bp
from .risk import risk_bp
from .capital import capital_bp
from .recon import recon_bp
from .robustness import robustness_bp
from .emergency import emergency_bp
from .liquidation import liquidation_bp
from .strategy import strategy_bp
from .dynamic_brain import dynamic_brain_bp
from .grid_mode import grid_mode_bp
from .unified_safety import unified_safety_bp
from .resolved_state import resolved_state_bp

__all__ = [
    'utility_bp',
    'health_bp',
    'docs_bp',
    'metrics_bp',
    'websocket_api_bp',
    'logs_bp',
    'pnl_bp',
    'orders_bp',
    'positions_bp',
    # 'config_bp',  # NOV 15: DISABLED - Migrated to yaml_config_api
    'system_bp',
    'monitor_bp',
    'guardian_bp',
    'pm2_bp',
    'bot_control_bp',
    'todos_bp',
    'risk_bp',
    'capital_bp',
    'recon_bp',
    'robustness_bp',
    'emergency_bp',
    'liquidation_bp',
    'strategy_bp',
    'dynamic_brain_bp',
    'grid_mode_bp',
    'unified_safety_bp',
    'resolved_state_bp',
]
