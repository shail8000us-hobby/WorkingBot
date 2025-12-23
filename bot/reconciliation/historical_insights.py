#!/usr/bin/env python3
"""
Historical Insights & Trend Analysis for Reconciliation
Tracks issues over time, analyzes patterns, and provides actionable insights.

Features:
- Issue history tracking (persistent storage)
- Trend analysis (frequency, patterns, timing)
- MTTR (Mean Time To Resolution) tracking
- Recurring issue detection
- Peak issue time analysis
- Resolution rate metrics

IMPORTANT: This module only ANALYZES historical data. 
It does NOT modify bot strategy or trading logic.
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter

log = logging.getLogger("historical_insights")


@dataclass
class IssueHistoryRecord:
    """Single historical issue record"""
    issue_id: str  # Unique ID for tracking
    issue_type: str
    severity: str
    order_id: str
    detected_at: str
    resolved_at: Optional[str] = None
    resolution_method: Optional[str] = None  # 'auto_heal', 'manual', 'timeout'
    resolution_time_seconds: Optional[float] = None
    recurrence_count: int = 1
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrendAnalysis:
    """Trend analysis results"""
    period: str  # 'last_hour', 'last_24h', 'last_7d', 'last_30d'
    total_issues: int
    issues_by_type: Dict[str, int]
    issues_by_severity: Dict[str, int]
    resolution_rate_pct: float
    avg_resolution_time_seconds: float
    peak_issue_hours: List[int]  # Hours of day with most issues
    recurring_issues: List[Dict[str, Any]]
    trend_direction: str  # 'improving', 'stable', 'degrading'
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceInsights:
    """Performance insights and recommendations"""
    health_score: int  # 0-100
    issues_prevented_count: int
    capital_protected_usd: float
    system_reliability_pct: float
    top_improvements: List[str]
    areas_needing_attention: List[str]
    recommendations: List[str]
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HistoricalInsightsEngine:
    """
    Historical insights and trend analysis engine.
    
    Features:
    - Persistent issue history storage
    - Trend analysis across time periods
    - Recurring issue detection
    - MTTR (Mean Time To Resolution) calculation
    - Peak issue time identification
    - Performance insights and recommendations
    
    Storage: JSON file (simple, no database required)
    """
    
    def __init__(self, base_dir: str = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(__file__).parent.parent.parent
        
        self.history_file = self.base_dir / "bot" / "audit" / "issue_history.jsonl"
        
        # Ensure directory exists
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for recent issues
        self._recent_issues: List[IssueHistoryRecord] = []
        self._load_recent_issues()
        
        log.info(f"📊 Historical Insights Engine initialized (history: {self.history_file})")
    
    def _load_recent_issues(self):
        """Load last 1000 issues into memory for fast access"""
        if not self.history_file.exists():
            return
        
        issues = []
        with open(self.history_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    data = json.loads(line)
                    issues.append(IssueHistoryRecord(**data))
                except Exception as e:
                    log.error(f"Failed to parse history record: {e}")
        
        # Keep only last 1000
        self._recent_issues = issues[-1000:]
        log.info(f"📊 Loaded {len(self._recent_issues)} recent issues from history")
    
    def record_issue(self, issue: Dict[str, Any]) -> str:
        """
        Record a detected issue to history.
        
        Args:
            issue: Issue dict from enhanced detection
            
        Returns:
            issue_id: Unique ID for this issue
        """
        # Generate unique ID
        issue_id = f"{issue.get('issue_type')}_{issue.get('order_id')}_{int(datetime.now(timezone.utc).timestamp())}"
        
        record = IssueHistoryRecord(
            issue_id=issue_id,
            issue_type=issue.get('issue_type', 'unknown'),
            severity=issue.get('severity', 'low'),
            order_id=issue.get('order_id', 'unknown'),
            detected_at=issue.get('detected_at') or datetime.now(timezone.utc).isoformat(),
            metadata=issue.get('metadata', {})
        )
        
        # Append to file
        with open(self.history_file, 'a') as f:
            f.write(json.dumps(record.to_dict()) + '\n')
        
        # Add to memory cache
        self._recent_issues.append(record)
        if len(self._recent_issues) > 1000:
            self._recent_issues = self._recent_issues[-1000:]
        
        log.debug(f"📝 Recorded issue {issue_id}")
        return issue_id
    
    def record_resolution(
        self,
        issue_id: str,
        resolution_method: str,
        resolution_time_seconds: float
    ):
        """
        Record resolution of an issue.
        
        Args:
            issue_id: ID from record_issue
            resolution_method: 'auto_heal', 'manual', 'timeout'
            resolution_time_seconds: Time taken to resolve
        """
        # Find issue in memory cache
        for issue in self._recent_issues:
            if issue.issue_id == issue_id:
                issue.resolved_at = datetime.now(timezone.utc).isoformat()
                issue.resolution_method = resolution_method
                issue.resolution_time_seconds = resolution_time_seconds
                log.info(f"✅ Resolved issue {issue_id} via {resolution_method} in {resolution_time_seconds:.1f}s")
                break
        
        # Rewrite file (simple approach, works for moderate volumes)
        self._save_issues_to_file()
    
    def _save_issues_to_file(self):
        """Save all recent issues back to file"""
        with open(self.history_file, 'w') as f:
            f.write(f"# Issue History - Last Updated: {datetime.now(timezone.utc).isoformat()}\n")
            for issue in self._recent_issues:
                f.write(json.dumps(issue.to_dict()) + '\n')
    
    def analyze_trends(self, period: str = 'last_24h') -> TrendAnalysis:
        """
        Analyze trends over a time period.
        
        Args:
            period: 'last_hour', 'last_24h', 'last_7d', 'last_30d'
            
        Returns:
            TrendAnalysis object
        """
        # Calculate time window
        now = datetime.now(timezone.utc)
        if period == 'last_hour':
            start_time = now - timedelta(hours=1)
        elif period == 'last_24h':
            start_time = now - timedelta(days=1)
        elif period == 'last_7d':
            start_time = now - timedelta(days=7)
        elif period == 'last_30d':
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(days=1)  # Default to 24h
        
        # Filter issues in period
        issues_in_period = [
            issue for issue in self._recent_issues
            if datetime.fromisoformat(issue.detected_at.replace('Z', '+00:00')) >= start_time
        ]
        
        if not issues_in_period:
            return TrendAnalysis(
                period=period,
                total_issues=0,
                issues_by_type={},
                issues_by_severity={},
                resolution_rate_pct=0.0,
                avg_resolution_time_seconds=0.0,
                peak_issue_hours=[],
                recurring_issues=[],
                trend_direction='stable'
            )
        
        # Count by type
        issues_by_type = Counter(issue.issue_type for issue in issues_in_period)
        
        # Count by severity
        issues_by_severity = Counter(issue.severity for issue in issues_in_period)
        
        # Resolution metrics
        resolved_issues = [i for i in issues_in_period if i.resolved_at]
        resolution_rate = (len(resolved_issues) / len(issues_in_period) * 100) if issues_in_period else 0.0
        
        resolution_times = [i.resolution_time_seconds for i in resolved_issues if i.resolution_time_seconds]
        avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0
        
        # Peak issue hours
        issue_hours = [
            datetime.fromisoformat(issue.detected_at.replace('Z', '+00:00')).hour
            for issue in issues_in_period
        ]
        peak_hours = Counter(issue_hours).most_common(3)
        peak_issue_hours = [hour for hour, _ in peak_hours]
        
        # Recurring issues (same type + order appears multiple times)
        issue_signatures = Counter(
            f"{issue.issue_type}_{issue.order_id}"
            for issue in issues_in_period
        )
        recurring = [
            {
                'signature': sig,
                'count': count,
                'issue_type': sig.split('_')[0],
                'order_id': '_'.join(sig.split('_')[1:])
            }
            for sig, count in issue_signatures.items()
            if count > 1
        ]
        
        # Trend direction (compare to previous period)
        prev_start = start_time - (now - start_time)
        prev_issues = [
            issue for issue in self._recent_issues
            if prev_start <= datetime.fromisoformat(issue.detected_at.replace('Z', '+00:00')) < start_time
        ]
        
        if len(prev_issues) > 0:
            if len(issues_in_period) < len(prev_issues) * 0.8:
                trend_direction = 'improving'
            elif len(issues_in_period) > len(prev_issues) * 1.2:
                trend_direction = 'degrading'
            else:
                trend_direction = 'stable'
        else:
            trend_direction = 'stable'
        
        return TrendAnalysis(
            period=period,
            total_issues=len(issues_in_period),
            issues_by_type=dict(issues_by_type),
            issues_by_severity=dict(issues_by_severity),
            resolution_rate_pct=resolution_rate,
            avg_resolution_time_seconds=avg_resolution_time,
            peak_issue_hours=peak_issue_hours,
            recurring_issues=recurring,
            trend_direction=trend_direction
        )
    
    def get_performance_insights(self) -> PerformanceInsights:
        """
        Generate performance insights and recommendations.
        
        Returns:
            PerformanceInsights object
        """
        # Analyze last 24h
        trends_24h = self.analyze_trends('last_24h')
        trends_7d = self.analyze_trends('last_7d')
        
        # Calculate health score (0-100)
        health_score = 100
        
        # Deduct for unresolved issues
        if trends_24h.total_issues > 0:
            unresolved_rate = 100 - trends_24h.resolution_rate_pct
            health_score -= unresolved_rate * 0.3  # Max -30 points
        
        # Deduct for recurring issues
        recurring_count = len(trends_24h.recurring_issues)
        health_score -= min(recurring_count * 5, 20)  # Max -20 points
        
        # Deduct for degrading trend
        if trends_24h.trend_direction == 'degrading':
            health_score -= 15
        
        health_score = max(0, min(100, int(health_score)))
        
        # Count auto-healed issues
        auto_healed = sum(
            1 for issue in self._recent_issues[-100:]
            if issue.resolution_method == 'auto_heal'
        )
        
        # Estimate capital protected (based on ghost orders resolved)
        capital_protected = sum(
            issue.metadata.get('impact_value', 0)
            for issue in self._recent_issues[-100:]
            if issue.issue_type == 'ghost_order' and issue.resolved_at
        )
        
        # System reliability
        all_issues_7d = trends_7d.total_issues
        resolved_7d = all_issues_7d * (trends_7d.resolution_rate_pct / 100)
        reliability = (resolved_7d / all_issues_7d * 100) if all_issues_7d > 0 else 100.0
        
        # Top improvements
        improvements = []
        if trends_24h.resolution_rate_pct > 90:
            improvements.append("✅ Excellent issue resolution rate (>90%)")
        if trends_24h.avg_resolution_time_seconds < 60:
            improvements.append("✅ Fast issue resolution (<60s average)")
        if trends_24h.trend_direction == 'improving':
            improvements.append("✅ Issue count trending down")
        if auto_healed > 5:
            improvements.append(f"✅ Auto-heal working well ({auto_healed} issues resolved)")
        
        # Areas needing attention
        attention = []
        if trends_24h.resolution_rate_pct < 70:
            attention.append("⚠️ Low resolution rate - many issues unresolved")
        if len(trends_24h.recurring_issues) > 3:
            attention.append("⚠️ Multiple recurring issues detected")
        if trends_24h.trend_direction == 'degrading':
            attention.append("⚠️ Issue count increasing")
        if 'critical' in trends_24h.issues_by_severity and trends_24h.issues_by_severity['critical'] > 0:
            attention.append(f"⚠️ {trends_24h.issues_by_severity['critical']} critical issues detected")
        
        # Recommendations
        recommendations = []
        if trends_24h.resolution_rate_pct < 80:
            recommendations.append("Enable auto-heal for more issue types")
        if len(trends_24h.recurring_issues) > 2:
            recommendations.append("Investigate recurring issues - may indicate deeper problem")
        if trends_24h.avg_resolution_time_seconds > 120:
            recommendations.append("Consider optimizing resolution process")
        if not improvements:
            recommendations.append("Monitor system closely - performance below optimal")
        
        return PerformanceInsights(
            health_score=health_score,
            issues_prevented_count=auto_healed,
            capital_protected_usd=capital_protected,
            system_reliability_pct=reliability,
            top_improvements=improvements or ["No major improvements detected"],
            areas_needing_attention=attention or ["No major issues detected"],
            recommendations=recommendations or ["System performing well, maintain current approach"]
        )
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent issue history"""
        return [issue.to_dict() for issue in self._recent_issues[-limit:]]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        total_issues = len(self._recent_issues)
        resolved_issues = sum(1 for i in self._recent_issues if i.resolved_at)
        
        return {
            'total_issues_tracked': total_issues,
            'resolved_issues': resolved_issues,
            'resolution_rate_pct': (resolved_issues / total_issues * 100) if total_issues > 0 else 0.0,
            'history_file_path': str(self.history_file),
            'history_file_exists': self.history_file.exists()
        }


# Global singleton
_insights_engine: Optional[HistoricalInsightsEngine] = None


def get_insights_engine() -> HistoricalInsightsEngine:
    """Get global insights engine instance"""
    global _insights_engine
    if _insights_engine is None:
        _insights_engine = HistoricalInsightsEngine()
    return _insights_engine


def record_issue(issue: Dict[str, Any]) -> str:
    """Convenience function to record issue"""
    engine = get_insights_engine()
    return engine.record_issue(issue)


def analyze_trends(period: str = 'last_24h') -> TrendAnalysis:
    """Convenience function to analyze trends"""
    engine = get_insights_engine()
    return engine.analyze_trends(period)


def get_performance_insights() -> PerformanceInsights:
    """Convenience function to get insights"""
    engine = get_insights_engine()
    return engine.get_performance_insights()
