"""
Order Audit and Metadata Tracking

Tags every order with rich metadata about its origin and context.
Makes debugging and auditing trivial.

Benefits:
- Know exactly where each order came from
- Debug issues in minutes instead of hours
- Generate audit reports
- Track recovery vs. normal orders

Example:
    from bot.orders.audit import create_order_with_audit
    
    # Place order with audit trail
    order = create_order_with_audit(
        executor=executor,
        order_type='BUY',
        price=111000,
        size=1,
        origin='smart_gap_fill',
        metadata={
            'missing_level': 111500,
            'gap_count': 1,
            'market_price': 111000
        }
    )
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from config.loader import get_config

log = logging.getLogger("audit")


@dataclass
class OrderMetadata:
    """Metadata for an order"""
    # Core identification
    order_id: str
    client_id: str
    timestamp: str
    
    # Order details
    order_type: str  # 'BUY' or 'TP'
    price: float
    size: float
    symbol: str
    
    # Origin tracking
    origin: str  # 'normal', 'recovery', 'smart_gap_fill', 'manual'
    bot_version: str
    trading_mode: str
    
    # Additional context
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class OrderAuditLogger:
    """Logs order metadata for auditing"""
    
    def __init__(self, audit_file: str = "bot/audit/orders.jsonl"):
        """
        Initialize audit logger.
        
        Args:
            audit_file: Path to JSONL audit file
        """
        self.audit_file = Path(audit_file)
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure file exists
        if not self.audit_file.exists():
            self.audit_file.touch()
        
        log.info(f"Order audit logger initialized: {self.audit_file}")
    
    def _iter_audit_entries(self):
        """Yield individual audit entries from the JSONL file, skipping empty sentinels."""
        try:
            with open(self.audit_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(payload, list):
                        for item in payload:
                            if isinstance(item, dict):
                                yield item
                        continue
                    if isinstance(payload, dict):
                        yield payload
        except FileNotFoundError:
            return
    
    def log_order(self, metadata: OrderMetadata):
        """
        Log order metadata to audit file.
        
        Args:
            metadata: Order metadata to log
        """
        try:
            with open(self.audit_file, 'a') as f:
                f.write(json.dumps(metadata.to_dict()) + '\n')
            
            log.debug(
                f"Audit: {metadata.origin}/{metadata.order_type} "
                f"@ {metadata.price} (id: {metadata.order_id})"
            )
        except Exception as e:
            log.error(f"Failed to write audit log: {e}")
    
    def get_orders_by_origin(
        self,
        origin: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get orders by origin.
        
        Args:
            origin: Order origin (e.g., 'recovery', 'smart_gap_fill')
            start_time: Filter by start time
            end_time: Filter by end time
        
        Returns:
            List of order metadata dicts
        """
        orders = []
        
        for order in self._iter_audit_entries():
            try:
                if order.get('origin') != origin:
                    continue
                if start_time or end_time:
                    order_time = datetime.fromisoformat(order['timestamp'])
                    if start_time and order_time < start_time:
                        continue
                    if end_time and order_time > end_time:
                        continue
                orders.append(order)
            except Exception as e:
                log.debug(f"Failed to parse audit line: {e}")
                continue
        
        return orders
    
    def generate_report(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate audit report.
        
        Args:
            start_time: Report start time
            end_time: Report end time
        
        Returns:
            Report dict with statistics
        """
        orders = []
        
        for order in self._iter_audit_entries():
            try:
                if start_time or end_time:
                    order_time = datetime.fromisoformat(order['timestamp'])
                    if start_time and order_time < start_time:
                        continue
                    if end_time and order_time > end_time:
                        continue
                orders.append(order)
            except Exception:
                continue
        
        # Group by origin
        by_origin = {}
        for order in orders:
            origin = order.get('origin', 'unknown')
            by_origin.setdefault(origin, []).append(order)
        
        # Generate statistics
        report = {
            'total_orders': len(orders),
            'start_time': start_time.isoformat() if start_time else None,
            'end_time': end_time.isoformat() if end_time else None,
            'by_origin': {}
        }
        
        for origin, origin_orders in by_origin.items():
            buy_orders = [o for o in origin_orders if o.get('order_type') == 'BUY']
            tp_orders = [o for o in origin_orders if o.get('order_type') == 'TP']
            
            report['by_origin'][origin] = {
                'total': len(origin_orders),
                'buy': len(buy_orders),
                'tp': len(tp_orders)
            }
        
        return report


# Global audit logger
_audit_logger: Optional[OrderAuditLogger] = None


def get_audit_logger() -> OrderAuditLogger:
    """Get or create global audit logger"""
    global _audit_logger
    if _audit_logger is None:
        # Use mode-specific audit file
        cfg = get_config()
        trading_mode = cfg.trading_mode.value.lower()  # trading_mode is at root level
        audit_file = f"bot/audit/orders_{trading_mode}.jsonl"
        _audit_logger = OrderAuditLogger(audit_file)
    return _audit_logger


def create_order_with_audit(
    executor: Any,
    order_type: str,
    price: float,
    size: float,
    origin: str = 'normal',
    symbol: Optional[str] = None,
    reduce_only: bool = False,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create order with full audit trail.
    
    Args:
        executor: DeltaExecutor instance
        order_type: 'BUY' or 'TP'
        price: Order price
        size: Order size
        origin: Order origin ('normal', 'recovery', 'smart_gap_fill', 'manual')
        symbol: Trading symbol (default from env)
        reduce_only: Whether order is reduce-only
        metadata: Additional metadata dict
    
    Returns:
        Order dict from exchange
    
    Example:
        order = create_order_with_audit(
            executor=executor,
            order_type='BUY',
            price=111000,
            size=1,
            origin='smart_gap_fill',
            metadata={
                'missing_level': 111500,
                'gap_count': 1,
                'market_price': 111000
            }
        )
    """
    # Generate client order ID with origin prefix
    timestamp = int(time.time())
    client_id = f"{origin.upper()}_{order_type}_{timestamp}"
    
    # Get symbol
    if symbol is None:
        cfg = get_config()
        symbol = cfg.trading.symbol
    
    # Determine side and reduce_only
    if order_type == 'BUY':
        side = 'buy'
        reduce_only = False
    elif order_type == 'TP':
        side = 'sell'
        reduce_only = True
    else:
        raise ValueError(f"Invalid order_type: {order_type}")
    
    # Log order placement intent
    log.info(
        f"Placing order: {origin}/{order_type} @ {price} size={size} "
        f"(client_id: {client_id})"
    )
    
    # Place order
    try:
        order = executor.create_order(
            side=side,
            amount=size,
            order_type='limit',
            symbol=symbol,
            price=price,
            reduce_only=reduce_only,
            client_id=client_id
        )
    except Exception as e:
        log.error(f"Order placement failed: {e}")
        raise
    
    # Create metadata
    order_metadata = OrderMetadata(
        order_id=order.get('id', 'unknown'),
        client_id=client_id,
        timestamp=datetime.utcnow().isoformat(),
        order_type=order_type,
        price=price,
        size=size,
        symbol=symbol,
        origin=origin,
        bot_version=cfg.bot.version,
        trading_mode=cfg.safety.trading_mode,
        metadata=metadata or {}
    )
    
    # Log to audit file
    audit_logger = get_audit_logger()
    audit_logger.log_order(order_metadata)
    
    # Log success
    log.info(
        f"✅ Order placed: {origin}/{order_type} @ {price} "
        f"(id: {order_metadata.order_id})"
    )
    
    return order


def get_orders_by_origin(
    origin: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Get orders by origin from audit log.
    
    Args:
        origin: Order origin
        start_time: Filter start time
        end_time: Filter end time
    
    Returns:
        List of order metadata dicts
    """
    audit_logger = get_audit_logger()
    return audit_logger.get_orders_by_origin(origin, start_time, end_time)


def generate_audit_report(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Generate audit report.
    
    Args:
        start_time: Report start time
        end_time: Report end time
    
    Returns:
        Report dict with statistics
    """
    audit_logger = get_audit_logger()
    return audit_logger.generate_report(start_time, end_time)


def print_audit_report(report: Dict[str, Any]):
    """
    Print audit report in human-readable format.
    
    Args:
        report: Report dict from generate_audit_report()
    """
    print("=" * 70)
    print("ORDER AUDIT REPORT")
    print("=" * 70)
    
    if report['start_time']:
        print(f"Period: {report['start_time']} to {report['end_time']}")
    else:
        print("Period: All time")
    
    print(f"Total Orders: {report['total_orders']}")
    print()
    
    for origin, stats in report['by_origin'].items():
        print(f"{origin.upper()}: {stats['total']} orders")
        print(f"  BUY: {stats['buy']}")
        print(f"  TP:  {stats['tp']}")
        print()
    
    print("=" * 70)
