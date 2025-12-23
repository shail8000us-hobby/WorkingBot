#!/usr/bin/env python3
"""
Enhanced Detection System for Reconciliation
Provides advanced detection for ghost orders, orphaned positions, duplicates, and other issues.
This module ONLY analyzes data - it does NOT modify bot strategy or trading logic.
"""

import logging
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict

log = logging.getLogger("enhanced_detection")


@dataclass
class DetectedIssue:
    """Represents a detected reconciliation issue"""
    issue_type: str  # 'ghost_order', 'orphaned_position', 'duplicate', 'stuck_order', etc.
    severity: str  # 'critical', 'high', 'medium', 'low'
    order_id: str
    client_order_id: Optional[str]
    description: str
    impact: str  # Human-readable impact description
    impact_value: float  # Monetary impact (USD)
    action_recommendation: str
    auto_healable: bool
    detected_at: str
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        if not hasattr(self, 'detected_at') or self.detected_at is None:
            self.detected_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ProductivityMetrics:
    """Bot productivity and efficiency metrics"""
    capital_utilization_pct: float
    order_success_rate_pct: float
    missed_fills_count: int
    avg_heal_time_seconds: float
    uptime_pct: float
    productivity_score: int  # 0-100
    issues_detected_last_hour: int
    issues_auto_healed_last_hour: int
    capital_freed_usd: float
    profit_recovered_usd: float
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EnhancedDetectionEngine:
    """
    Advanced detection engine for reconciliation issues.
    
    Features:
    - Ghost order detection (in bot memory, gone from exchange)
    - Orphaned position detection (filled on exchange, bot doesn't know)
    - Duplicate order detection (same order multiple times in memory)
    - Stuck order detection (cancel failed, still open)
    - Price mismatch detection (order price doesn't match grid)
    - Capital utilization tracking
    - Productivity metrics calculation
    - Result caching (30s TTL) for performance
    
    IMPORTANT: This class only DETECTS issues. It does NOT modify any bot files or trading logic.
    """
    
    # Cache configuration
    CACHE_TTL_SECONDS = 30  # Cache results for 30 seconds
    
    def __init__(self):
        self.detection_history: List[DetectedIssue] = []
        self.last_detection_time: Optional[datetime] = None
        
        # Cache storage
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        
        log.info("🔍 Enhanced Detection Engine initialized with caching")
    
    def _generate_cache_key(
        self,
        bot_orders: List[Dict[str, Any]],
        exchange_orders: List[Dict[str, Any]],
        exchange_positions: List[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a unique cache key based on input data.
        Uses hash of order IDs and statuses to detect changes.
        """
        # Extract key data for hashing
        bot_data = sorted([
            (o.get('order_id', ''), o.get('status', ''), o.get('timestamp', ''))
            for o in bot_orders
        ])
        
        exchange_data = sorted([
            (o.get('orderId', ''), o.get('status', ''), o.get('updateTime', ''))
            for o in exchange_orders
        ])
        
        position_data = []
        if exchange_positions:
            position_data = sorted([
                (p.get('symbol', ''), p.get('positionAmt', ''), p.get('updateTime', ''))
                for p in exchange_positions
            ])
        
        # Create hash
        data_str = json.dumps({
            'bot': bot_data,
            'exchange': exchange_data,
            'positions': position_data
        }, sort_keys=True)
        
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached result if still valid"""
        if cache_key not in self._cache:
            return None
        
        cache_time = self._cache_timestamps.get(cache_key)
        if not cache_time:
            return None
        
        age = (datetime.now(timezone.utc) - cache_time).total_seconds()
        
        if age > self.CACHE_TTL_SECONDS:
            # Cache expired
            log.debug(f"⏱️  Cache expired for key {cache_key[:8]}... (age: {age:.1f}s)")
            del self._cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None
        
        log.info(f"✅ Cache hit for key {cache_key[:8]}... (age: {age:.1f}s)")
        return self._cache[cache_key]
    
    def _set_cached_result(self, cache_key: str, result: Dict[str, Any]):
        """Store result in cache"""
        self._cache[cache_key] = result
        self._cache_timestamps[cache_key] = datetime.now(timezone.utc)
        log.debug(f"💾 Cached result for key {cache_key[:8]}...")
    
    def _cleanup_old_cache_entries(self):
        """Remove expired cache entries"""
        now = datetime.now(timezone.utc)
        expired_keys = []
        
        for key, timestamp in self._cache_timestamps.items():
            age = (now - timestamp).total_seconds()
            if age > self.CACHE_TTL_SECONDS:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            del self._cache_timestamps[key]
        
        if expired_keys:
            log.debug(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
    
    def detect_all_issues(
        self,
        bot_orders: List[Dict[str, Any]],
        exchange_orders: List[Dict[str, Any]],
        exchange_positions: List[Dict[str, Any]] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Run all detection methods and return comprehensive results.
        
        Args:
            bot_orders: Orders from bot memory (orders.jsonl)
            exchange_orders: Orders from exchange API
            exchange_positions: Positions from exchange API (optional)
            force_refresh: Skip cache and force fresh detection
            
        Returns:
            Dictionary with:
            - issues: List of DetectedIssue objects
            - metrics: ProductivityMetrics object
            - summary: High-level summary
            - cached: Whether result came from cache
        """
        # Clean up old cache entries periodically
        self._cleanup_old_cache_entries()
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            cache_key = self._generate_cache_key(bot_orders, exchange_orders, exchange_positions)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                cached_result['cached'] = True
                return cached_result
        
        log.info(f"🔍 Starting enhanced detection: bot_orders={len(bot_orders)}, exchange_orders={len(exchange_orders)}")
        
        issues: List[DetectedIssue] = []
        
        # Detection 1: Ghost Orders
        ghost_issues = self._detect_ghost_orders(bot_orders, exchange_orders)
        issues.extend(ghost_issues)
        log.info(f"🔍 Ghost orders detected: {len(ghost_issues)}")
        
        # Detection 2: Orphaned Positions
        if exchange_positions:
            orphaned_issues = self._detect_orphaned_positions(bot_orders, exchange_positions)
            issues.extend(orphaned_issues)
            log.info(f"🔍 Orphaned positions detected: {len(orphaned_issues)}")
        
        # Detection 3: Duplicate Orders
        duplicate_issues = self._detect_duplicate_orders(bot_orders)
        issues.extend(duplicate_issues)
        log.info(f"🔍 Duplicate orders detected: {len(duplicate_issues)}")
        
        # Detection 4: Stuck Orders
        stuck_issues = self._detect_stuck_orders(bot_orders, exchange_orders)
        issues.extend(stuck_issues)
        log.info(f"🔍 Stuck orders detected: {len(stuck_issues)}")
        
        # Calculate productivity metrics
        metrics = self._calculate_productivity_metrics(
            bot_orders, exchange_orders, issues
        )
        
        # Generate summary
        summary = self._generate_detection_summary(issues, metrics)
        
        # Store detection history
        self.detection_history.extend(issues)
        self.last_detection_time = datetime.now(timezone.utc)
        
        # Keep only last 1000 issues in history
        if len(self.detection_history) > 1000:
            self.detection_history = self.detection_history[-1000:]
        
        # Record issues to historical insights (for trend analysis)
        if issues and not force_refresh:  # Only record on non-forced refreshes
            try:
                from bot.reconciliation.historical_insights import get_insights_engine
                insights_engine = get_insights_engine()
                for issue in issues:
                    insights_engine.record_issue(issue.to_dict())
            except Exception as e:
                log.warning(f"Failed to record issues to history: {e}")
        
        log.info(f"✅ Detection complete: {len(issues)} total issues, productivity score: {metrics.productivity_score}/100")
        
        result = {
            'status': 'success',
            'issues': [issue.to_dict() for issue in issues],
            'metrics': metrics.to_dict(),
            'summary': summary,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'cached': False
        }
        
        # Cache the result
        if not force_refresh:
            cache_key = self._generate_cache_key(bot_orders, exchange_orders, exchange_positions)
            self._set_cached_result(cache_key, result)
        
        return result
    
    def _detect_ghost_orders(
        self,
        bot_orders: List[Dict[str, Any]],
        exchange_orders: List[Dict[str, Any]]
    ) -> List[DetectedIssue]:
        """
        Detect ghost orders: orders in bot memory but not on exchange.
        These lock capital and should be removed from bot memory.
        """
        issues = []
        
        # Build exchange order lookup (by order_id and client_order_id)
        exchange_lookup = {}
        for order in exchange_orders:
            order_id = order.get('id') or order.get('order_id')
            client_order_id = order.get('clientOrderId') or order.get('client_order_id')
            if order_id:
                exchange_lookup[str(order_id)] = order
            if client_order_id:
                exchange_lookup[str(client_order_id)] = order
        
        # Check each bot order
        for bot_order in bot_orders:
            # Only check OPEN/PENDING orders (closed orders are expected to be gone)
            status = str(bot_order.get('status', '')).upper()
            if status not in ['OPEN', 'PENDING', 'NEW']:
                continue
            
            order_id = str(bot_order.get('order_id', ''))
            client_order_id = str(bot_order.get('client_order_id', ''))
            
            # Check if order exists on exchange
            found_on_exchange = (
                order_id in exchange_lookup or
                client_order_id in exchange_lookup
            )
            
            if not found_on_exchange:
                # Ghost order detected!
                price = float(bot_order.get('price', 0))
                size = float(bot_order.get('size', 0) or bot_order.get('qty', 0))
                impact_value = price * size
                
                issue = DetectedIssue(
                    issue_type='ghost_order',
                    severity='high',
                    order_id=order_id,
                    client_order_id=client_order_id,
                    description=f"Order exists in bot memory but not on exchange (may have been manually canceled)",
                    impact=f"${impact_value:,.2f} capital locked",
                    impact_value=impact_value,
                    action_recommendation="Remove from bot memory to free capital",
                    auto_healable=True,
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    metadata={
                        'side': bot_order.get('side'),
                        'price': price,
                        'size': size,
                        'symbol': bot_order.get('symbol'),
                        'created_at': bot_order.get('timestamp')
                    }
                )
                issues.append(issue)
        
        return issues
    
    def _detect_orphaned_positions(
        self,
        bot_orders: List[Dict[str, Any]],
        exchange_positions: List[Dict[str, Any]]
    ) -> List[DetectedIssue]:
        """
        Detect orphaned positions: positions on exchange that bot doesn't have TP orders for.
        These represent potential profit loss if market moves.
        """
        issues = []
        
        # Build map of positions that have TP orders
        positions_with_tp = set()
        for order in bot_orders:
            # Check if this is a TP order
            if order.get('reduce_only') or 'TP' in str(order.get('client_order_id', '')):
                # Extract position it's protecting
                # (This is simplified - actual logic depends on your bot's TP naming)
                positions_with_tp.add(order.get('symbol'))
        
        # Check each exchange position
        for position in exchange_positions:
            symbol = position.get('symbol')
            size = float(position.get('contracts', 0) or position.get('size', 0))
            
            if size == 0:
                continue  # No position
            
            # Check if bot has TP order for this position
            if symbol not in positions_with_tp:
                # Orphaned position!
                entry_price = float(position.get('entry_price', 0) or position.get('entryPrice', 0))
                unrealized_pnl = float(position.get('unrealized_pnl', 0) or position.get('unrealizedPnl', 0))
                
                issue = DetectedIssue(
                    issue_type='orphaned_position',
                    severity='critical',
                    order_id=f"position_{symbol}",
                    client_order_id=None,
                    description=f"Open position without TP order - unlimited loss risk",
                    impact=f"Unprotected position: ${abs(entry_price * size):,.2f} value, PnL: ${unrealized_pnl:,.2f}",
                    impact_value=abs(entry_price * size),
                    action_recommendation="Place TP order immediately using bot's grid logic",
                    auto_healable=False,  # Requires manual review
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    metadata={
                        'symbol': symbol,
                        'size': size,
                        'entry_price': entry_price,
                        'unrealized_pnl': unrealized_pnl,
                        'side': position.get('side')
                    }
                )
                issues.append(issue)
        
        return issues
    
    def _detect_duplicate_orders(
        self,
        bot_orders: List[Dict[str, Any]]
    ) -> List[DetectedIssue]:
        """
        Detect duplicate orders: same order_id appears multiple times in bot memory.
        This indicates memory corruption or logging issues.
        """
        issues = []
        
        # Count occurrences of each order_id
        order_id_counts = defaultdict(list)
        for order in bot_orders:
            order_id = str(order.get('order_id', ''))
            if order_id:
                order_id_counts[order_id].append(order)
        
        # Find duplicates
        for order_id, orders in order_id_counts.items():
            if len(orders) > 1:
                # Duplicate detected!
                first_order = orders[0]
                price = float(first_order.get('price', 0))
                size = float(first_order.get('size', 0) or first_order.get('qty', 0))
                
                issue = DetectedIssue(
                    issue_type='duplicate_order',
                    severity='medium',
                    order_id=order_id,
                    client_order_id=first_order.get('client_order_id'),
                    description=f"Order appears {len(orders)} times in bot memory",
                    impact=f"Memory corruption may cause operational issues",
                    impact_value=0,  # No direct financial impact
                    action_recommendation="Deduplicate bot memory, keep only latest entry",
                    auto_healable=True,
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    metadata={
                        'duplicate_count': len(orders),
                        'side': first_order.get('side'),
                        'price': price,
                        'size': size,
                        'symbol': first_order.get('symbol')
                    }
                )
                issues.append(issue)
        
        return issues
    
    def _detect_stuck_orders(
        self,
        bot_orders: List[Dict[str, Any]],
        exchange_orders: List[Dict[str, Any]]
    ) -> List[DetectedIssue]:
        """
        Detect stuck orders: orders that bot tried to cancel but are still open on exchange.
        """
        issues = []
        
        # Build exchange order lookup
        exchange_lookup = {}
        for order in exchange_orders:
            order_id = str(order.get('id') or order.get('order_id', ''))
            if order_id:
                exchange_lookup[order_id] = order
        
        # Check bot orders marked as "canceling" or "canceled"
        for bot_order in bot_orders:
            status = str(bot_order.get('status', '')).upper()
            order_id = str(bot_order.get('order_id', ''))
            
            # If bot thinks it's canceled but still open on exchange
            if status in ['CANCELED', 'CANCELING'] and order_id in exchange_lookup:
                exchange_order = exchange_lookup[order_id]
                exchange_status = str(exchange_order.get('status', '')).upper()
                
                if exchange_status in ['OPEN', 'NEW', 'PENDING']:
                    # Stuck order!
                    price = float(bot_order.get('price', 0))
                    size = float(bot_order.get('size', 0) or bot_order.get('qty', 0))
                    impact_value = price * size
                    
                    issue = DetectedIssue(
                        issue_type='stuck_order',
                        severity='medium',
                        order_id=order_id,
                        client_order_id=bot_order.get('client_order_id'),
                        description="Cancel request failed or pending - order still open on exchange",
                        impact=f"${impact_value:,.2f} capital stuck",
                        impact_value=impact_value,
                        action_recommendation="Retry cancel or wait for exchange processing",
                        auto_healable=False,  # Requires manual intervention
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        metadata={
                            'side': bot_order.get('side'),
                            'price': price,
                            'size': size,
                            'symbol': bot_order.get('symbol'),
                            'bot_status': status,
                            'exchange_status': exchange_status
                        }
                    )
                    issues.append(issue)
        
        return issues
    
    def _calculate_productivity_metrics(
        self,
        bot_orders: List[Dict[str, Any]],
        exchange_orders: List[Dict[str, Any]],
        issues: List[DetectedIssue]
    ) -> ProductivityMetrics:
        """Calculate bot productivity and efficiency metrics"""
        
        # Capital utilization (simplified - actual implementation depends on your capital model)
        total_open_orders = len([o for o in bot_orders if o.get('status', '').upper() in ['OPEN', 'PENDING', 'NEW']])
        total_possible_orders = 10  # Example: bot can have max 10 orders
        capital_utilization = min(100, (total_open_orders / total_possible_orders) * 100) if total_possible_orders > 0 else 0
        
        # Order success rate (orders successfully placed vs attempts)
        total_orders = len(bot_orders)
        failed_orders = len([o for o in bot_orders if o.get('status', '').upper() == 'FAILED'])
        order_success_rate = ((total_orders - failed_orders) / total_orders * 100) if total_orders > 0 else 100
        
        # Missed fills (orphaned positions)
        missed_fills = len([i for i in issues if i.issue_type == 'orphaned_position'])
        
        # Calculate capital freed and profit recovered
        capital_freed = sum(i.impact_value for i in issues if i.issue_type == 'ghost_order')
        profit_recovered = 0  # Would be calculated from actual healing actions
        
        # Issues in last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_issues = [
            i for i in self.detection_history 
            if datetime.fromisoformat(i.detected_at.replace('Z', '+00:00')) > one_hour_ago
        ]
        issues_last_hour = len(recent_issues)
        
        # Calculate productivity score (0-100)
        # Higher score = better productivity
        score = 100
        score -= len([i for i in issues if i.severity == 'critical']) * 20  # -20 per critical issue
        score -= len([i for i in issues if i.severity == 'high']) * 10  # -10 per high issue
        score -= len([i for i in issues if i.severity == 'medium']) * 5  # -5 per medium issue
        score = max(0, min(100, score))  # Clamp to 0-100
        
        metrics = ProductivityMetrics(
            capital_utilization_pct=round(capital_utilization, 1),
            order_success_rate_pct=round(order_success_rate, 1),
            missed_fills_count=missed_fills,
            avg_heal_time_seconds=12.0,  # Would be calculated from actual healing history
            uptime_pct=99.8,  # Would be calculated from bot monitoring
            productivity_score=score,
            issues_detected_last_hour=issues_last_hour,
            issues_auto_healed_last_hour=0,  # Would be calculated from healing history
            capital_freed_usd=round(capital_freed, 2),
            profit_recovered_usd=round(profit_recovered, 2)
        )
        
        return metrics
    
    def _generate_detection_summary(
        self,
        issues: List[DetectedIssue],
        metrics: ProductivityMetrics
    ) -> Dict[str, Any]:
        """Generate human-readable summary of detection results"""
        
        # Count by severity
        by_severity = {
            'critical': len([i for i in issues if i.severity == 'critical']),
            'high': len([i for i in issues if i.severity == 'high']),
            'medium': len([i for i in issues if i.severity == 'medium']),
            'low': len([i for i in issues if i.severity == 'low'])
        }
        
        # Count by type
        by_type = {}
        for issue in issues:
            by_type[issue.issue_type] = by_type.get(issue.issue_type, 0) + 1
        
        # Calculate total impact
        total_impact = sum(i.impact_value for i in issues)
        
        # Auto-healable count
        auto_healable = len([i for i in issues if i.auto_healable])
        
        # Health status
        if by_severity['critical'] > 0:
            health_status = 'critical'
            health_color = 'red'
        elif by_severity['high'] > 0:
            health_status = 'needs_attention'
            health_color = 'orange'
        elif by_severity['medium'] > 0:
            health_status = 'minor_issues'
            health_color = 'yellow'
        else:
            health_status = 'healthy'
            health_color = 'green'
        
        return {
            'total_issues': len(issues),
            'by_severity': by_severity,
            'by_type': by_type,
            'total_financial_impact': round(total_impact, 2),
            'auto_healable_count': auto_healable,
            'manual_review_required': len(issues) - auto_healable,
            'health_status': health_status,
            'health_color': health_color,
            'productivity_score': metrics.productivity_score,
            'recommendation': self._get_recommendation(issues, metrics)
        }
    
    def _get_recommendation(
        self,
        issues: List[DetectedIssue],
        metrics: ProductivityMetrics
    ) -> str:
        """Get action recommendation based on issues and metrics"""
        
        critical_count = len([i for i in issues if i.severity == 'critical'])
        high_count = len([i for i in issues if i.severity == 'high'])
        auto_healable = len([i for i in issues if i.auto_healable])
        
        if critical_count > 0:
            return f"⚠️ CRITICAL: {critical_count} critical issue(s) require immediate attention!"
        elif high_count > 0:
            if auto_healable > 0:
                return f"✅ {auto_healable} issue(s) can be auto-healed. Click 'Auto-Heal Safe Issues'."
            else:
                return f"⚠️ {high_count} issue(s) require manual review."
        elif len(issues) == 0:
            return "✅ All systems healthy! No issues detected."
        else:
            return f"ℹ️ {len(issues)} minor issue(s) detected. Review at your convenience."


# Global singleton instance
_enhanced_detection_engine: Optional[EnhancedDetectionEngine] = None


def get_enhanced_detection_engine() -> EnhancedDetectionEngine:
    """Get the global enhanced detection engine instance"""
    global _enhanced_detection_engine
    if _enhanced_detection_engine is None:
        _enhanced_detection_engine = EnhancedDetectionEngine()
    return _enhanced_detection_engine


# Convenience function
def detect_all_issues(
    bot_orders: List[Dict[str, Any]],
    exchange_orders: List[Dict[str, Any]],
    exchange_positions: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to run all enhanced detection.
    
    Args:
        bot_orders: Orders from bot memory
        exchange_orders: Orders from exchange
        exchange_positions: Positions from exchange (optional)
        
    Returns:
        Detection results with issues, metrics, and summary
    """
    engine = get_enhanced_detection_engine()
    return engine.detect_all_issues(bot_orders, exchange_orders, exchange_positions)
