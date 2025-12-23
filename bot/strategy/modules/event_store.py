"""
Event Store Module - Core event sourcing implementation with SQLite backend.
Provides ACID guarantees and full audit trail for GridBot state management.
"""

import json
import logging
import sqlite3
import time
import uuid
import asyncio
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Any, Optional
from threading import Lock
from collections import deque

# Configure module logger
log = logging.getLogger("event_store")


class EventType(Enum):
    """Enumeration of all event types in the trading system."""
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"
    TP_PLACED = "tp_placed"
    TP_ORDER_PLACED = "tp_order_placed"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_FAILED = "order_failed"
    PENDING_BUY_SET = "pending_buy_set"
    PENDING_BUY_CLEARED = "pending_buy_cleared"
    PENDING_SELL_SET = "pending_sell_set"
    PENDING_SELL_CLEARED = "pending_sell_cleared"
    # Saga events (Phase 2+3)
    SAGA_STARTED = "saga_started"
    SAGA_STEP_COMPLETED = "saga_step_completed"
    SAGA_STEP_FAILED = "saga_step_failed"
    SAGA_COMPLETED = "saga_completed"
    SAGA_FAILED = "saga_failed"
    SAGA_COMPENSATING = "saga_compensating"
    SAGA_COMPENSATION_STARTED = "saga_compensation_started"
    SAGA_COMPENSATION_COMPLETED = "saga_compensation_completed"
    SAGA_STEP_COMPENSATED = "saga_step_compensated"
    SAGA_STEP_COMPENSATION_FAILED = "saga_step_compensation_failed"
    SAGA_COMPENSATION_CRITICAL = "saga_compensation_critical"
    # TP Retry events
    TP_RETRY_SCHEDULED = "tp_retry_scheduled"
    TP_RETRY_COMPLETED = "tp_retry_completed"
    TP_RETRY_EXHAUSTED = "tp_retry_exhausted"
    # Opportunistic Recovery events
    OPPORTUNISTIC_RECOVERY_STARTED = "opportunistic_recovery_started"
    OPPORTUNISTIC_POSITION_OPENED = "opportunistic_position_opened"
    OPPORTUNISTIC_CAPITAL_SAVED = "opportunistic_capital_saved"
    # Volatility Monitoring events
    VOLATILITY_HALT_TRIGGERED = "volatility_halt_triggered"
    VOLATILITY_HALT_CLEARED = "volatility_halt_cleared"
    # Guardian Signal events (Phase 1 - SQL-based signal system)
    GUARDIAN_SIGNAL_GO = "guardian_signal_go"
    GUARDIAN_SIGNAL_STOP = "guardian_signal_stop"
    GUARDIAN_CONFIG_CHANGED = "guardian_config_changed"
    # Guardian Check events (Phase 1 - Detailed monitoring)
    GUARDIAN_VOLATILITY_CHECK = "guardian_volatility_check"
    GUARDIAN_RISK_CHECK = "guardian_risk_check"
    GUARDIAN_POSITION_CHECK = "guardian_position_check"
    GUARDIAN_LIQUIDATION_CHECK = "guardian_liquidation_check"
    GUARDIAN_HEALTH_CHECK = "guardian_health_check"


@dataclass
class Event:
    """
    Immutable event record representing a state change in the trading system.
    
    Attributes:
        event_id: Unique identifier for this event (UUID)
        event_type: Type of event from EventType enum
        timestamp: Unix timestamp when event occurred
        correlation_id: Links related events in a business transaction
        aggregate_id: ID of the entity this event affects (position/order)
        data: Event-specific payload as dictionary
        metadata: Additional context (bot version, environment, etc.)
    """
    event_id: str
    event_type: EventType
    timestamp: float
    correlation_id: str
    aggregate_id: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'correlation_id': self.correlation_id,
            'aggregate_id': self.aggregate_id,
            'data': self.data,
            'metadata': self.metadata
        }


class EventStore:
    """
    SQLite-backed event store with Write-Ahead Logging for concurrent access.
    Provides append-only event storage with ACID guarantees.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = Lock()
        self._is_memory = (db_path == ":memory:")
        self._memory_conn = None
        self._initialize_database()
        
        self._write_queue = deque()
        self._write_lock = Lock()
        self._batch_size = 50
        self._batch_timeout = 0.5
        self._last_flush = time.time()
        
        log.info(f"EventStore initialized with database: {db_path}")
    
    def _initialize_database(self) -> None:
        """Create tables and indexes if they don't exist."""
        with self._connection() as conn:
            cursor = conn.cursor()
            
            # Enable WAL mode for concurrent reads
            cursor.execute("PRAGMA journal_mode=WAL")
            
            # Optimize for performance (safe with WAL)
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # Create events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    correlation_id TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for common query patterns
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON events(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_correlation 
                ON events(correlation_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_aggregate 
                ON events(aggregate_id)
            """)
            
            conn.commit()
            log.info("Database schema initialized successfully")
    
    @contextmanager
    def _connection(self):
        """
        Context manager for database connections with automatic cleanup.
        For :memory: databases, returns the persistent connection.
        
        Yields:
            sqlite3.Connection: Database connection
        """
        if self._is_memory:
            # For :memory: databases, use persistent connection
            # (new connections create separate databases)
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(
                    self.db_path, 
                    check_same_thread=False,  # Allow multi-threaded access
                    timeout=10.0
                )
                self._memory_conn.row_factory = sqlite3.Row
            yield self._memory_conn
        else:
            # For file-based databases, create new connection each time
            conn = None
            try:
                conn = sqlite3.connect(self.db_path, timeout=10.0)
                conn.row_factory = sqlite3.Row  # Enable column access by name
                yield conn
            except sqlite3.Error as e:
                if conn:
                    conn.rollback()
                log.error(f"Database error: {e}")
                raise
            finally:
                if conn:
                    conn.close()
    
    def _flush_write_queue(self) -> None:
        with self._write_lock:
            if not self._write_queue:
                return
            
            events_to_write = []
            while self._write_queue and len(events_to_write) < self._batch_size:
                events_to_write.append(self._write_queue.popleft())
            
            if not events_to_write:
                return
        
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                
                for event in events_to_write:
                    cursor.execute("""
                        INSERT INTO events (
                            event_id, event_type, timestamp, correlation_id,
                            aggregate_id, data, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event.event_id,
                        event.event_type.value,
                        event.timestamp,
                        event.correlation_id,
                        event.aggregate_id,
                        json.dumps(event.data),
                        json.dumps(event.metadata)
                    ))
                
                conn.commit()
        
        self._last_flush = time.time()
    
    def _should_flush(self) -> bool:
        if len(self._write_queue) >= self._batch_size:
            return True
        
        if time.time() - self._last_flush >= self._batch_timeout:
            return True
        
        return False
    
    def append_event(self, event: Event) -> None:
        with self._write_lock:
            self._write_queue.append(event)
        
        if self._should_flush():
            self._flush_write_queue()
    
    def flush(self) -> None:
        self._flush_write_queue()
    
    def get_events_since(self, timestamp: float) -> List[Event]:
        """
        Retrieve all events after a specific timestamp.
        
        Args:
            timestamp: Unix timestamp to query from
            
        Returns:
            List of events ordered by timestamp ascending
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM events 
                WHERE timestamp > ? 
                ORDER BY timestamp ASC
            """, (timestamp,))
            
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
    
    def get_events_by_correlation(self, correlation_id: str) -> List[Event]:
        """
        Retrieve all events with a specific correlation ID.
        
        Args:
            correlation_id: Correlation ID to filter by
            
        Returns:
            List of related events ordered by timestamp
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM events 
                WHERE correlation_id = ? 
                ORDER BY timestamp ASC
            """, (correlation_id,))
            
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
    
    def get_events_by_aggregate(self, aggregate_id: str) -> List[Event]:
        """
        Retrieve all events for a specific entity (position/order).
        
        Args:
            aggregate_id: Entity ID to get history for
            
        Returns:
            List of events for the entity ordered by timestamp
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM events 
                WHERE aggregate_id = ? 
                ORDER BY timestamp ASC
            """, (aggregate_id,))
            
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
    
    def get_events_by_type(self, event_types, limit: int = None) -> List[Event]:
        """
        Retrieve events by type(s), optionally limited.
        
        Args:
            event_types: Single EventType enum or list of EventType enums to filter by
            limit: Maximum number of events to return (most recent first)
            
        Returns:
            List of matching events ordered by timestamp descending
            
        Examples:
            # Single type
            events = store.get_events_by_type(EventType.GUARDIAN_SIGNAL_GO, limit=10)
            
            # Multiple types (for Guardian GO/STOP signals)
            events = store.get_events_by_type(
                [EventType.GUARDIAN_SIGNAL_GO, EventType.GUARDIAN_SIGNAL_STOP],
                limit=1
            )
        """
        # Convert to list if single EventType provided
        if isinstance(event_types, EventType):
            event_types = [event_types]
        elif isinstance(event_types, str):
            # Legacy support for string event types
            event_types = [event_types]
        
        # Convert EventType enums to string values
        type_values = []
        for et in event_types:
            if isinstance(et, EventType):
                type_values.append(et.value)
            else:
                type_values.append(et)  # Already a string
        
        with self._connection() as conn:
            cursor = conn.cursor()
            
            # Build query with IN clause for multiple types
            placeholders = ','.join('?' * len(type_values))
            
            if limit:
                query = f"""
                    SELECT * FROM events 
                    WHERE event_type IN ({placeholders})
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                cursor.execute(query, type_values + [limit])
            else:
                query = f"""
                    SELECT * FROM events 
                    WHERE event_type IN ({placeholders})
                    ORDER BY timestamp DESC
                """
                cursor.execute(query, type_values)
            
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
    
    def get_all_events(self) -> List[Event]:
        """
        Retrieve all events from the store.
        
        Returns:
            List of all events ordered by timestamp
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM events 
                ORDER BY timestamp ASC
            """)
            
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
    
    def _row_to_event(self, row: sqlite3.Row) -> Event:
        """
        Deserialize a database row to an Event object.
        
        Args:
            row: SQLite row object
            
        Returns:
            Reconstructed Event object
        """
        try:
            # Parse JSON fields
            data = json.loads(row['data'])
            metadata = json.loads(row['metadata'])
            
            # Reconstruct Event object
            return Event(
                event_id=row['event_id'],
                event_type=EventType(row['event_type']),
                timestamp=row['timestamp'],
                correlation_id=row['correlation_id'],
                aggregate_id=row['aggregate_id'],
                data=data,
                metadata=metadata
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            log.error(f"Failed to deserialize event {row['event_id']}: {e}")
            # Return a minimal event to prevent crash
            return Event(
                event_id=row['event_id'],
                event_type=EventType.ORDER_CANCELLED,  # Safe default
                timestamp=row['timestamp'],
                correlation_id=row['correlation_id'],
                aggregate_id=row['aggregate_id'],
                data={},
                metadata={"error": str(e)}
            )
    
    def get_event_count(self) -> int:
        """
        Get total number of events in the store.
        
        Returns:
            Total event count
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM events")
            return cursor.fetchone()[0]
    
    def get_latest_event_timestamp(self) -> Optional[float]:
        """
        Get timestamp of the most recent event.
        
        Returns:
            Unix timestamp of latest event or None if no events
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(timestamp) FROM events")
            result = cursor.fetchone()[0]
            return result if result else None
    
    def verify_wal_mode(self) -> bool:
        """
        Verify that WAL mode is enabled.
        
        Returns:
            True if WAL mode is active
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            return mode.lower() == 'wal'
