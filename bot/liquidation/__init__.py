"""
Liquidation Protection System - Direct Delta Exchange Integration
================================================================

Prevents account liquidation through real-time margin monitoring and alerts.
Fetches all data directly from Delta Exchange APIs without using bot memory.

Features:
- Direct Delta Exchange API integration
- Real-time monitoring with WebSocket support
- Compatible with existing WebUI backend/frontend
- No dependencies on bot memory or local state files
"""

from .integrated_monitor import IntegratedLiquidationMonitor, RealTimeLiquidationMonitor

__all__ = [
    'IntegratedLiquidationMonitor',
    'RealTimeLiquidationMonitor',  # Backward compatibility alias
]

