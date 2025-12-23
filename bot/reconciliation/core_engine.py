#!/usr/bin/env python3
"""
Bulletproof Core Reconciliation Engine
Main reconciliation logic with order matching, discrepancy detection, and audit logging.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
import threading

from .provenance_detector import get_provenance_detector, ProvenanceResult
from .data_sources import get_data_sources_manager
from .order_logger import get_order_logger

log = logging.getLogger("core_engine")


@dataclass
class ReconciliationRecord:
    """Single reconciliation record"""
    order_id: str
    client_order_id: str
    side: str
    price: float
    size: float
    symbol: str
    status: str
    provenance: str
    strategy: str
    confidence: float
    source: str  # 'bot', 'exchange', 'both'
    discrepancy: Optional[str] = None
    discrepancy_details: Optional[Dict[str, Any]] = None
    timestamp: str = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class ReconciliationSummary:
    """Reconciliation summary statistics"""
    total_orders: int
    bot_orders: int
    manual_orders: int
    unknown_orders: int
    matched_orders: int
    mismatched_orders: int
    exchange_only_orders: int
    bot_only_orders: int
    discrepancies: List[str]
    strategies: Dict[str, int]
    confidence_distribution: Dict[str, int]
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class BulletproofReconciliationEngine:
    """
    Bulletproof reconciliation engine with comprehensive order matching and discrepancy detection.
    
    Features:
    - Multi-method order matching (ID, client ID, heuristic)
    - Provenance detection and classification
    - Discrepancy detection and analysis
    - Comprehensive audit logging
    - Thread-safe operations
    - Performance optimization
    """
    
    def __init__(self, base_dir: str = None, delta_client_factory=None):
        self.base_dir = base_dir
        self.delta_client_factory = delta_client_factory
        
        # Initialize components
        self.provenance_detector = get_provenance_detector()
        self.data_sources = get_data_sources_manager(base_dir, delta_client_factory)
        self.order_logger = get_order_logger()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Configuration
        self.matching_tolerance = 0.01  # Price tolerance for matching
        self.time_tolerance = 300  # 5 minutes in seconds
        
        log.info("🔒 Bulletproof Reconciliation Engine initialized")
    
    def reconcile(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Perform complete reconciliation between bot and exchange data.
        
        Args:
            force_refresh: Force refresh of all data sources
            
        Returns:
            Reconciliation results with records and summary
        """
        try:
            with self._lock:
                log.info("🔄 Starting reconciliation process...")
                
                # Load all data
                data = self.data_sources.get_all_data(force_refresh)
                if 'error' in data:
                    log.error(f"❌ Data loading error: {data['error']}")
                    return {
                        'status': 'error',
                        'error': data['error'],
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                
                # Log data counts
                log.info(f"📊 Data loaded: bot_orders={len(data.get('bot_orders', []))}, exchange_orders={len(data.get('exchange_orders', []))}")
                
                # Perform reconciliation
                records = self._reconcile_orders(data)
                log.info(f"📊 Reconciliation created {len(records)} records")
                
                summary = self._generate_summary(records)
                log.info(f"📊 Summary: total={summary.total_orders}, bot={summary.bot_orders}, manual={summary.manual_orders}, matched={summary.matched_orders}")
                
                # Log reconciliation event
                self.order_logger.log_reconciliation_event(
                    'reconciliation_completed',
                    {
                        'total_orders': summary.total_orders,
                        'bot_orders': summary.bot_orders,
                        'manual_orders': summary.manual_orders,
                        'mismatched_orders': summary.mismatched_orders,
                        'discrepancies': summary.discrepancies
                    }
                )
                
                result = {
                    'status': 'success',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'records': [record.to_dict() for record in records],
                    'summary': asdict(summary),
                    'data_sources': {
                        'bot_orders_count': len(data['bot_orders']),
                        'exchange_orders_count': len(data['exchange_orders']),
                        'last_update': data['timestamp']
                    }
                }
                
                log.info(f"✅ Reconciliation completed: {summary.total_orders} orders, {summary.mismatched_orders} mismatches")
                return result
                
        except Exception as e:
            log.error(f"❌ Reconciliation failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def _reconcile_orders(self, data: Dict[str, Any]) -> List[ReconciliationRecord]:
        """Reconcile orders between bot and exchange"""
        bot_orders = data['bot_orders']
        exchange_orders = data['exchange_orders']
        
        records = []
        matched_exchange_ids = set()
        matched_bot_ids = set()
        
        # Process exchange orders
        for ex_order in exchange_orders:
            record = self._process_exchange_order(ex_order, bot_orders, matched_bot_ids)
            records.append(record)
            if record.source in ['both', 'exchange']:
                matched_exchange_ids.add(record.order_id)
        
        # Process unmatched bot orders
        for bot_order in bot_orders:
            bot_id = bot_order.get('order_id', '')
            if bot_id not in matched_bot_ids:
                record = self._process_bot_only_order(bot_order)
                records.append(record)
        
        return records
    
    def _process_exchange_order(
        self,
        ex_order: Dict[str, Any],
        bot_orders: List[Dict[str, Any]],
        matched_bot_ids: set
    ) -> ReconciliationRecord:
        """Process a single exchange order"""
        order_id = str(ex_order.get('id', ''))
        client_order_id = ex_order.get('client_order_id', '')
        
        # Detect provenance
        provenance_result = self.provenance_detector.detect_provenance(
            client_order_id,
            ex_order.get('metadata', {})
        )
        
        # Try to match with bot orders
        matched_bot_order = self._find_matching_bot_order(ex_order, bot_orders)
        
        if matched_bot_order:
            matched_bot_ids.add(matched_bot_order.get('order_id', ''))
            return self._create_matched_record(ex_order, matched_bot_order, provenance_result)
        else:
            return self._create_exchange_only_record(ex_order, provenance_result)
    
    def _process_bot_only_order(self, bot_order: Dict[str, Any]) -> ReconciliationRecord:
        """Process a bot-only order (not found on exchange)"""
        provenance_result = self.provenance_detector.detect_provenance(
            bot_order.get('client_order_id', ''),
            bot_order.get('metadata', {})
        )
        
        return ReconciliationRecord(
            order_id=bot_order.get('order_id', ''),
            client_order_id=bot_order.get('client_order_id', ''),
            side=bot_order.get('side', ''),
            price=bot_order.get('price', 0.0),
            size=bot_order.get('size', 0.0),
            symbol=bot_order.get('symbol', ''),
            status=bot_order.get('status', ''),
            provenance=provenance_result.provenance,
            strategy=provenance_result.strategy,
            confidence=provenance_result.confidence,
            source='bot',
            discrepancy='missing_on_exchange',
            discrepancy_details={
                'reason': 'Order exists in bot memory but not on exchange',
                'severity': 'critical'
            },
            metadata=bot_order.get('metadata', {})
        )
    
    def _find_matching_bot_order(
        self,
        ex_order: Dict[str, Any],
        bot_orders: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Find matching bot order using multiple methods"""
        ex_id = str(ex_order.get('id', ''))
        ex_client_id = ex_order.get('client_order_id', '')
        
        # Method 1: Direct order ID match
        for bot_order in bot_orders:
            if str(bot_order.get('order_id', '')) == ex_id:
                return bot_order
        
        # Method 2: Client order ID match
        if ex_client_id:
            for bot_order in bot_orders:
                if bot_order.get('client_order_id', '') == ex_client_id:
                    return bot_order
        
        # Method 3: Heuristic match (price, side, size, time)
        ex_price = float(ex_order.get('price', 0))
        ex_side = ex_order.get('side', '')
        ex_size = float(ex_order.get('size', 0))
        ex_time = ex_order.get('created_at', '')
        
        for bot_order in bot_orders:
            bot_price = float(bot_order.get('price', 0))
            bot_side = bot_order.get('side', '')
            bot_size = float(bot_order.get('size', 0))
            bot_time = bot_order.get('timestamp', '')
            
            # Check if orders match heuristically
            if (bot_side == ex_side and
                abs(bot_price - ex_price) <= self.matching_tolerance and
                abs(bot_size - ex_size) <= 0.001 and
                self._is_time_match(bot_time, ex_time)):
                return bot_order
        
        return None
    
    def _is_time_match(self, time1: str, time2: str) -> bool:
        """Check if two timestamps are within tolerance"""
        try:
            if not time1 or not time2:
                return False
            
            # Parse timestamps (handle different formats)
            dt1 = datetime.fromisoformat(time1.replace('Z', '+00:00'))
            dt2 = datetime.fromisoformat(time2.replace('Z', '+00:00'))
            
            # Check if within tolerance
            diff = abs((dt1 - dt2).total_seconds())
            return diff <= self.time_tolerance
            
        except Exception:
            return False
    
    def _create_matched_record(
        self,
        ex_order: Dict[str, Any],
        bot_order: Dict[str, Any],
        provenance_result: ProvenanceResult
    ) -> ReconciliationRecord:
        """Create record for matched orders"""
        # Check for discrepancies
        discrepancies = self._detect_discrepancies(ex_order, bot_order)
        
        return ReconciliationRecord(
            order_id=str(ex_order.get('id', '')),
            client_order_id=ex_order.get('client_order_id', ''),
            side=ex_order.get('side', ''),
            price=float(ex_order.get('price', 0)),
            size=float(ex_order.get('size', 0)),
            symbol=ex_order.get('product_symbol', ''),
            status=ex_order.get('status', ''),
            provenance=provenance_result.provenance,
            strategy=provenance_result.strategy,
            confidence=provenance_result.confidence,
            source='both',
            discrepancy=discrepancies[0] if discrepancies else None,
            discrepancy_details={
                'discrepancies': discrepancies,
                'severity': 'warning' if discrepancies else 'none'
            } if discrepancies else None,
            metadata={
                'exchange_data': ex_order,
                'bot_data': bot_order,
                'provenance_evidence': provenance_result.evidence
            }
        )
    
    def _create_exchange_only_record(
        self,
        ex_order: Dict[str, Any],
        provenance_result: ProvenanceResult
    ) -> ReconciliationRecord:
        """Create record for exchange-only orders"""
        return ReconciliationRecord(
            order_id=str(ex_order.get('id', '')),
            client_order_id=ex_order.get('client_order_id', ''),
            side=ex_order.get('side', ''),
            price=float(ex_order.get('price', 0)),
            size=float(ex_order.get('size', 0)),
            symbol=ex_order.get('product_symbol', ''),
            status=ex_order.get('status', ''),
            provenance=provenance_result.provenance,
            strategy=provenance_result.strategy,
            confidence=provenance_result.confidence,
            source='exchange',
            discrepancy='missing_in_bot',
            discrepancy_details={
                'reason': 'Order exists on exchange but not in bot memory',
                'severity': 'warning'
            },
            metadata={
                'exchange_data': ex_order,
                'provenance_evidence': provenance_result.evidence
            }
        )
    
    def _detect_discrepancies(
        self,
        ex_order: Dict[str, Any],
        bot_order: Dict[str, Any]
    ) -> List[str]:
        """Detect discrepancies between exchange and bot orders"""
        discrepancies = []
        
        # Price discrepancy
        ex_price = float(ex_order.get('price', 0))
        bot_price = float(bot_order.get('price', 0))
        if abs(ex_price - bot_price) > self.matching_tolerance:
            discrepancies.append(f"price_mismatch: {bot_price} vs {ex_price}")
        
        # Size discrepancy
        ex_size = float(ex_order.get('size', 0))
        bot_size = float(bot_order.get('size', 0))
        if abs(ex_size - bot_size) > 0.001:
            discrepancies.append(f"size_mismatch: {bot_size} vs {ex_size}")
        
        # Status discrepancy
        ex_status = ex_order.get('status', '')
        bot_status = bot_order.get('status', '')
        if ex_status != bot_status:
            discrepancies.append(f"status_mismatch: {bot_status} vs {ex_status}")
        
        # Side discrepancy
        ex_side = ex_order.get('side', '')
        bot_side = bot_order.get('side', '')
        if ex_side != bot_side:
            discrepancies.append(f"side_mismatch: {bot_side} vs {ex_side}")
        
        return discrepancies
    
    def _generate_summary(self, records: List[ReconciliationRecord]) -> ReconciliationSummary:
        """Generate reconciliation summary"""
        total_orders = len(records)
        bot_orders = sum(1 for r in records if r.provenance == 'bot')
        manual_orders = sum(1 for r in records if r.provenance == 'manual')
        unknown_orders = sum(1 for r in records if r.provenance == 'unknown')
        matched_orders = sum(1 for r in records if r.source == 'both')
        mismatched_orders = sum(1 for r in records if r.discrepancy is not None)
        exchange_only_orders = sum(1 for r in records if r.source == 'exchange')
        bot_only_orders = sum(1 for r in records if r.source == 'bot')
        
        # Collect discrepancies
        discrepancies = []
        for record in records:
            if record.discrepancy:
                discrepancies.append(record.discrepancy)
        
        # Count strategies
        strategies = {}
        for record in records:
            strategy = record.strategy
            if strategy not in strategies:
                strategies[strategy] = 0
            strategies[strategy] += 1
        
        # Count confidence distribution
        confidence_distribution = {'high': 0, 'medium': 0, 'low': 0}
        for record in records:
            if record.confidence >= 0.8:
                confidence_distribution['high'] += 1
            elif record.confidence >= 0.5:
                confidence_distribution['medium'] += 1
            else:
                confidence_distribution['low'] += 1
        
        return ReconciliationSummary(
            total_orders=total_orders,
            bot_orders=bot_orders,
            manual_orders=manual_orders,
            unknown_orders=unknown_orders,
            matched_orders=matched_orders,
            mismatched_orders=mismatched_orders,
            exchange_only_orders=exchange_only_orders,
            bot_only_orders=bot_only_orders,
            discrepancies=discrepancies,
            strategies=strategies,
            confidence_distribution=confidence_distribution
        )


# Global instance
_reconciliation_engine = None


def get_reconciliation_engine(base_dir: str = None, delta_client_factory=None) -> BulletproofReconciliationEngine:
    """Get global reconciliation engine instance"""
    global _reconciliation_engine
    if _reconciliation_engine is None:
        _reconciliation_engine = BulletproofReconciliationEngine(base_dir, delta_client_factory)
    return _reconciliation_engine


def reconcile_orders(base_dir: str = None, delta_client_factory=None, force_refresh: bool = False) -> Dict[str, Any]:
    """Convenience function to reconcile orders"""
    engine = get_reconciliation_engine(base_dir, delta_client_factory)
    return engine.reconcile(force_refresh)


if __name__ == "__main__":
    # Test the reconciliation engine
    engine = get_reconciliation_engine()
    
    print("🧪 Testing Reconciliation Engine:")
    
    # Test reconciliation
    result = engine.reconcile(force_refresh=True)
    
    if result['status'] == 'success':
        summary = result['summary']
        print(f"✅ Reconciliation successful:")
        print(f"   Total orders: {summary['total_orders']}")
        print(f"   Bot orders: {summary['bot_orders']}")
        print(f"   Manual orders: {summary['manual_orders']}")
        print(f"   Mismatched: {summary['mismatched_orders']}")
    else:
        print(f"❌ Reconciliation failed: {result.get('error', 'Unknown error')}")
    
    print("\n✅ Reconciliation engine test completed")
