"""
SSR ALGO - Automated Position Adjustment Algorithm

This module implements a fully automated algorithmic trading engine that deploys
a Modified Iron Butterfly with Protective Wings strategy.

Features:
- Automatic strike selection based on premium percentages
- Auto-loop execution with batch order placement
- Price monitoring with max loss zone detection
- Automatic adjustment triggers with 10-minute dwell time
- Backend restart resilience

Created: February 2, 2026
"""

from .ssr_algo_api import ssr_algo_bp
from .ssr_algo_payoff import SSRPayoffCalculator, get_payoff_calculator
from .ssr_algo_monitor import (
    SSRPriceMonitor,
    start_session_monitor,
    stop_session_monitor,
    pause_session_monitor,
    resume_session_monitor,
    get_session_monitor_status,
    get_all_monitor_statuses,
    restore_monitors_on_startup
)

__all__ = [
    'ssr_algo_bp',
    'SSRPayoffCalculator',
    'get_payoff_calculator',
    'SSRPriceMonitor',
    'start_session_monitor',
    'stop_session_monitor',
    'pause_session_monitor',
    'resume_session_monitor',
    'get_session_monitor_status',
    'get_all_monitor_statuses',
    'restore_monitors_on_startup'
]


def init_ssr_algo():
    """
    Initialize SSR Algo module.
    
    Call this on backend startup to restore any active monitors.
    """
    import logging
    log = logging.getLogger('ssr_algo')
    
    try:
        restored = restore_monitors_on_startup()
        log.info(f"SSR Algo initialized, {restored} monitors restored")
    except Exception as e:
        log.exception(f"SSR Algo initialization failed: {e}")
