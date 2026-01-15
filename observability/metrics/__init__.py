"""
Prometheus Metrics Package

Contains metric definitions, collectors, and exporters.
"""

from .definitions import (
    # Trading metrics
    orders_placed_total,
    orders_filled_total,
    orders_cancelled_total,
    orders_failed_total,
    open_positions_count,
    position_value_usd,
    unrealized_pnl_usd,
    realized_pnl_usd,
    
    # System metrics
    system_cpu_percent,
    system_memory_percent,
    system_disk_percent,
    bot_memory_mb,
    bot_uptime_seconds,
    
    # Guardian metrics
    guardian_signal,
    guardian_risk_level,
    guardian_interventions_total,
    total_loss_inr,
    liquidation_distance_percent,
    
    # API metrics
    api_call_duration_seconds,
    api_rate_limit_hits,
    api_429_errors,
    
    # Registry
    REGISTRY
)

from .collectors import MetricsCollector
from .exporters import generate_metrics, get_content_type

__all__ = [
    'MetricsCollector',
    'generate_metrics',
    'get_content_type',
    'REGISTRY'
]
