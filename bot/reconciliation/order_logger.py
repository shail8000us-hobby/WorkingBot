#!/usr/bin/env python3
"""
Bulletproof Order Logger - Real-time Order Tracking
Logs every order placed by bot with full audit trail and provenance detection.
"""

import json
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import logging

log = logging.getLogger("order_logger")


@dataclass
class OrderRecord:
    """Structured order record for audit trail"""
    timestamp: str
    order_id: str
    client_order_id: str
    side: str
    price: float
    size: float
    symbol: str
    status: str
    provenance: str
    strategy: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class BulletproofOrderLogger:
    """
    Thread-safe, bulletproof order logger for real-time order tracking.
    
    Features:
    - Thread-safe logging
    - Atomic writes to JSONL
    - Automatic provenance detection
    - Rich metadata tracking
    - Error recovery
    """
    
    def __init__(self, audit_dir: Path):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        
        self.orders_file = self.audit_dir / "orders.jsonl"
        self.audit_file = self.audit_dir / "reconciliation_audit.jsonl"
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Initialize files
        self._ensure_files_exist()
        
        log.info(f"🔒 Bulletproof Order Logger initialized: {self.audit_dir}")
    
    def _ensure_files_exist(self):
        """Ensure audit files exist with proper headers"""
        if not self.orders_file.exists():
            with open(self.orders_file, 'w') as f:
                f.write("# Bot Order Audit Trail - JSONL Format\n")
                f.write("# Each line is a JSON object representing one order\n")
            log.info(f"📝 Created orders audit file: {self.orders_file}")
        
        if not self.audit_file.exists():
            with open(self.audit_file, 'w') as f:
                f.write("# Reconciliation Audit Trail - JSONL Format\n")
                f.write("# Each line is a JSON object representing one reconciliation event\n")
            log.info(f"📝 Created reconciliation audit file: {self.audit_file}")
    
    def _detect_provenance(self, client_order_id: str) -> str:
        """
        Detect if order is Bot or Manual based on client_order_id patterns.
        
        Bot patterns:
        - BOT-* (planned format)
        - GBOT_* (legacy format)
        - BUY{timestamp} (current format)
        - TP{timestamp} (current format)
        """
        if not client_order_id:
            return "manual"
        
        client_id = str(client_order_id).strip()
        
        # Bot patterns (in order of priority)
        if client_id.startswith("BOT-"):
            return "bot"
        if client_id.startswith("GBOT_"):
            return "bot"
        if client_id.startswith("BUY") and len(client_id) > 10:
            return "bot"  # Current bot format: BUY{timestamp}
        if client_id.startswith("TP") and len(client_id) > 10:
            return "bot"  # Current bot format: TP{timestamp}
        
        return "manual"
    
    def _extract_strategy(self, client_order_id: str) -> str:
        """Extract strategy from client_order_id"""
        if not client_order_id:
            return "unknown"
        
        client_id = str(client_order_id).strip()
        
        if client_id.startswith("BOT-"):
            parts = client_id.split("-")
            if len(parts) >= 2:
                return parts[1]  # BOT-grid-123 -> grid
        elif client_id.startswith("GBOT_"):
            return "grid"  # Legacy grid bot
        elif client_id.startswith("BUY") or client_id.startswith("TP"):
            return "grid"  # Current grid bot
        
        return "unknown"
    
    def log_order_placed(
        self,
        order_id: str,
        client_order_id: str,
        side: str,
        price: float,
        size: float,
        symbol: str,
        status: str = "open",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log order placement with full audit trail.
        
        Args:
            order_id: Exchange order ID
            client_order_id: Client order ID
            side: buy/sell
            price: Order price
            size: Order size
            symbol: Trading symbol
            status: Order status (open, filled, cancelled)
            metadata: Additional metadata
            
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            with self._lock:
                # Detect provenance and strategy
                provenance = self._detect_provenance(client_order_id)
                strategy = self._extract_strategy(client_order_id)
                
                # Create order record
                record = OrderRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    order_id=str(order_id),
                    client_order_id=str(client_order_id),
                    side=side,
                    price=float(price),
                    size=float(size),
                    symbol=str(symbol),
                    status=status,
                    provenance=provenance,
                    strategy=strategy,
                    metadata=metadata or {}
                )
                
                # Atomic write to JSONL
                with open(self.orders_file, 'a') as f:
                    f.write(json.dumps(record.to_dict()) + '\n')
                
                # Log to console
                log.info(
                    f"📝 Order logged: {provenance.upper()}/{strategy} "
                    f"{side.upper()} @ {price} size={size} "
                    f"(ID: {order_id}, Client: {client_order_id})"
                )
                
                return True
                
        except Exception as e:
            log.error(f"❌ Failed to log order: {e}")
            return False
    
    def log_order_update(
        self,
        order_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log order status update (filled, cancelled, etc.).
        
        Args:
            order_id: Exchange order ID
            status: New status
            metadata: Additional metadata
            
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            with self._lock:
                update_record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "order_update",
                    "order_id": str(order_id),
                    "status": status,
                    "metadata": metadata or {}
                }
                
                # Atomic write to audit file
                with open(self.audit_file, 'a') as f:
                    f.write(json.dumps(update_record) + '\n')
                
                log.info(f"📝 Order update logged: {order_id} -> {status}")
                return True
                
        except Exception as e:
            log.error(f"❌ Failed to log order update: {e}")
            return False
    
    def log_reconciliation_event(
        self,
        event_type: str,
        details: Dict[str, Any]
    ) -> bool:
        """
        Log reconciliation events for audit trail.
        
        Args:
            event_type: Type of reconciliation event
            details: Event details
            
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            with self._lock:
                event_record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "reconciliation",
                    "event_type": event_type,
                    "details": details
                }
                
                # Atomic write to audit file
                with open(self.audit_file, 'a') as f:
                    f.write(json.dumps(event_record) + '\n')
                
                log.info(f"📝 Reconciliation event logged: {event_type}")
                return True
                
        except Exception as e:
            log.error(f"❌ Failed to log reconciliation event: {e}")
            return False
    
    def get_recent_orders(self, limit: int = 100) -> list:
        """Get recent orders from audit trail"""
        try:
            with self._lock:
                orders = []
                with open(self.orders_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            try:
                                order = json.loads(line)
                                orders.append(order)
                            except json.JSONDecodeError:
                                continue
                
                # Return most recent orders
                return orders[-limit:] if limit else orders
                
        except Exception as e:
            log.error(f"❌ Failed to get recent orders: {e}")
            return []
    
    def get_orders_by_provenance(self, provenance: str) -> list:
        """Get orders by provenance (bot/manual)"""
        try:
            with self._lock:
                orders = []
                with open(self.orders_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            try:
                                order = json.loads(line)
                                if order.get('provenance') == provenance:
                                    orders.append(order)
                            except json.JSONDecodeError:
                                continue
                
                return orders
                
        except Exception as e:
            log.error(f"❌ Failed to get orders by provenance: {e}")
            return []


# Global instance
_order_logger = None


def get_order_logger() -> BulletproofOrderLogger:
    """Get global order logger instance"""
    global _order_logger
    if _order_logger is None:
        audit_dir = Path(__file__).parent.parent / "audit"
        _order_logger = BulletproofOrderLogger(audit_dir)
    return _order_logger


def log_order_placed(
    order_id: str,
    client_order_id: str,
    side: str,
    price: float,
    size: float,
    symbol: str,
    status: str = "open",
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Convenience function to log order placement"""
    logger = get_order_logger()
    return logger.log_order_placed(
        order_id, client_order_id, side, price, size, symbol, status, metadata
    )


def log_order_update(
    order_id: str,
    status: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Convenience function to log order update"""
    logger = get_order_logger()
    return logger.log_order_update(order_id, status, metadata)


if __name__ == "__main__":
    # Test the order logger
    logger = get_order_logger()
    
    # Test order logging
    logger.log_order_placed(
        order_id="123456789",
        client_order_id="BOT-grid-1729012345-a7f3-buy",
        side="buy",
        price=50000.0,
        size=1.0,
        symbol="BTCUSD",
        metadata={"test": True}
    )
    
    # Test order update
    logger.log_order_update("123456789", "filled")
    
    print("✅ Order logger test completed")
