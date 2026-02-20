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
from .ssr_algo_greeks import SSRGreeksFetcher, get_greeks_fetcher
from .ssr_algo_exit_manager import SSRExitManager, get_exit_manager
from .ssr_algo_delta_hedger import SSRDeltaHedger, get_delta_hedger
from .ssr_algo_vol_analyzer import SSRVolAnalyzer, get_vol_analyzer
from .ssr_algo_dte_manager import SSRDTEManager, get_dte_manager
from .ssr_algo_regime import SSRRegimeAdapter, get_regime_adapter
from .ssr_algo_smart_executor import SSRSmartExecutor, get_smart_executor
from .ssr_algo_rv_tracker import SSRRVTracker, get_rv_tracker
from .ssr_algo_analytics import SSRAnalytics, get_analytics
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
    'SSRGreeksFetcher',
    'get_greeks_fetcher',
    'SSRExitManager',
    'get_exit_manager',
    'SSRDeltaHedger',
    'get_delta_hedger',
    'SSRVolAnalyzer',
    'get_vol_analyzer',
    'SSRDTEManager',
    'get_dte_manager',
    'SSRRegimeAdapter',
    'get_regime_adapter',
    'SSRSmartExecutor',
    'get_smart_executor',
    'SSRRVTracker',
    'get_rv_tracker',
    'SSRAnalytics',
    'get_analytics',
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
