"""
Help Action Mappings - Frontend to Backend Route Mapping

This file provides explicit mappings for frontend action IDs to backend API routes.
Used when frontend action names don't exactly match backend route patterns.
"""

ACTION_MAPPINGS = {
    # Capital Protection Panel
    "capital.equity-floor.save": "/api/capital/update-config",
    "capital.drawdown-cap.save": "/api/capital/update-config",
    "capital.exposure-limiter.save": "/api/capital/update-config",
    "capital.pending-budget.save": "/api/capital/update-config",
    "capital.two-man-rule.save": "/api/capital/update-config",
    
    # Liquidation Protection
    "liquidation.save-settings": "/api/liquidation/config",
    
    # Monitoring Panel
    "monitoring.save-safety-limits": "/api/config",
    
    # Reconciliation
    "reconciliation.resync": "/api/reconciliation/resync",
    "reconciliation.acknowledge": "/api/reconciliation/acknowledge",
    "reconciliation.ignore": "/api/reconciliation/ignore",
    
    # Robustness Panel
    "robustness.save-loss-limits": "/api/config",
    "robustness.reset-volatility": "/api/robustness/reset-volatility",
    
    # Emergency Actions (already have routes, just mapping for clarity)
    "emergency.clear-flag": "/api/emergency/clear_flag",
    "emergency.reset-gatekeeper": "/api/emergency/reset_gatekeeper",
    "emergency.force-restart": "/api/emergency/force_restart",
}
