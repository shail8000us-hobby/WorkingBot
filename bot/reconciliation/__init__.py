"""
Bulletproof Reconciliation & Provenance System

This module provides real-time reconciliation between bot orders and exchange orders,
with full provenance tracking (Bot vs Manual) and audit trail logging.

Components:
- order_logger: Real-time order tracking and audit logging
- core_engine: Main reconciliation logic (to be implemented)
- data_sources: Data source management (to be implemented)
- provenance_detector: Bot vs Manual detection (to be implemented)
- real_time_updater: WebSocket integration (to be implemented)
"""

from .order_logger import (
    BulletproofOrderLogger,
    get_order_logger,
    log_order_placed,
    log_order_update
)

from .provenance_detector import (
    BulletproofProvenanceDetector,
    get_provenance_detector,
    detect_order_provenance,
    ProvenanceResult
)

from .data_sources import (
    DataSourcesManager,
    get_data_sources_manager
)

from .core_engine import (
    BulletproofReconciliationEngine,
    get_reconciliation_engine,
    reconcile_orders,
    ReconciliationRecord,
    ReconciliationSummary
)

from .real_time_updater import (
    BulletproofRealTimeUpdater,
    get_real_time_updater,
    start_real_time_updates,
    UpdateEvent
)

from .enhanced_detection import (
    EnhancedDetectionEngine,
    get_enhanced_detection_engine,
    detect_all_issues,
    DetectedIssue,
    ProductivityMetrics
)

from .auto_heal import (
    AutoHealEngine,
    get_auto_heal_engine,
    heal_all_safe_issues,
    HealResult
)

from .historical_insights import (
    HistoricalInsightsEngine,
    get_insights_engine,
    record_issue,
    analyze_trends,
    get_performance_insights,
    IssueHistoryRecord,
    TrendAnalysis,
    PerformanceInsights
)

__all__ = [
    # Order Logger
    'BulletproofOrderLogger',
    'get_order_logger', 
    'log_order_placed',
    'log_order_update',
    
    # Provenance Detector
    'BulletproofProvenanceDetector',
    'get_provenance_detector',
    'detect_order_provenance',
    'ProvenanceResult',
    
    # Data Sources
    'DataSourcesManager',
    'get_data_sources_manager',
    
    # Core Engine
    'BulletproofReconciliationEngine',
    'get_reconciliation_engine',
    'reconcile_orders',
    'ReconciliationRecord',
    'ReconciliationSummary',
    
    # Real-time Updater
    'BulletproofRealTimeUpdater',
    'get_real_time_updater',
    'start_real_time_updates',
    'UpdateEvent',
    
    # Enhanced Detection
    'EnhancedDetectionEngine',
    'get_enhanced_detection_engine',
    'detect_all_issues',
    'DetectedIssue',
    'ProductivityMetrics',
    
    # Auto-Heal
    'AutoHealEngine',
    'get_auto_heal_engine',
    'heal_all_safe_issues',
    'HealResult',
    
    # Historical Insights
    'HistoricalInsightsEngine',
    'get_insights_engine',
    'record_issue',
    'analyze_trends',
    'get_performance_insights',
    'IssueHistoryRecord',
    'TrendAnalysis',
    'PerformanceInsights'
]