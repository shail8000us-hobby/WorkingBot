"""
SQLite-based Metrics Logger
Logs WebUI metrics for historic trend analysis in Guardian Dashboard.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock
import logging

log = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent / 'metrics.db'


class MetricsLogger:
    """
    Log WebUI metrics to SQLite for trending and analysis.
    
    Metrics tracked:
    - API latencies (response times for all endpoints)
    - Error counts (by endpoint and error type)
    - Circuit breaker states (open/closed transitions)
    - Resource usage (if needed)
    
    Usage:
        metrics_logger.log_metric('api_latency', '/api/positions', 45.2, 'ok')
        metrics_logger.log_metric('error_count', '/api/orders', 1, 'error')
        metrics_logger.log_metric('circuit_state', 'delta_api', 0, 'open')
    """
    
    def __init__(self):
        self.db_path = DB_PATH
        self.lock = Lock()
        self._conn = None  # Persistent connection — avoids per-call open/close on large DB
        self._init_db()
        self.cleanup_old_metrics(days=30)  # Prune on startup to keep file size bounded
        log.info(f"Metrics logger initialized: {self.db_path}")
    
    def _get_conn(self) -> sqlite3.Connection:
        """Return the persistent connection, creating it if needed."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute('PRAGMA journal_mode=WAL')
            self._conn.execute('PRAGMA synchronous=NORMAL')
        return self._conn

    def _init_db(self):
        """Initialize SQLite database and tables"""
        try:
            conn = self._get_conn()
            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    status TEXT,
                    metadata TEXT
                )
            ''')

            # Create indexes for faster queries
            conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON metrics(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_type ON metrics(metric_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_name ON metrics(metric_name)')

            conn.commit()
            log.info("Metrics database initialized successfully")
        except Exception as e:
            log.error(f"Failed to initialize metrics database: {e}")
    
    def log_metric(self, metric_type: str, metric_name: str, value: float, status: str = 'ok', metadata: str = None):
        """
        Log a metric data point.
        
        Args:
            metric_type: Type of metric (e.g., 'api_latency', 'error_count', 'circuit_state')
            metric_name: Name/identifier (e.g., endpoint path, service name)
            value: Numeric value to log
            status: Status indicator ('ok', 'error', 'warning', 'open', 'closed')
            metadata: Optional JSON string with additional context
        """
        with self.lock:
            try:
                conn = self._get_conn()
                conn.execute(
                    'INSERT INTO metrics (timestamp, metric_type, metric_name, value, status, metadata) VALUES (?, ?, ?, ?, ?, ?)',
                    (datetime.now().isoformat(), metric_type, metric_name, value, status, metadata)
                )
                conn.commit()
            except Exception as e:
                log.error(f"Failed to log metric: {e}")
    
    def get_recent_metrics(self, metric_type: str = None, hours: int = 24, limit: int = 1000):
        """
        Get recent metrics for charting/analysis.
        
        Args:
            metric_type: Filter by metric type (None = all types)
            hours: Number of hours to look back
            limit: Maximum number of records to return
            
        Returns:
            List of tuples: (timestamp, metric_type, metric_name, value, status)
        """
        with self.lock:
            try:
                conn = self._get_conn()
                if metric_type:
                    cursor = conn.execute(
                        '''SELECT timestamp, metric_type, metric_name, value, status, metadata
                           FROM metrics
                           WHERE metric_type = ?
                           AND timestamp > datetime('now', '-' || ? || ' hours')
                           ORDER BY timestamp DESC
                           LIMIT ?''',
                        (metric_type, hours, limit)
                    )
                else:
                    cursor = conn.execute(
                        '''SELECT timestamp, metric_type, metric_name, value, status, metadata
                           FROM metrics
                           WHERE timestamp > datetime('now', '-' || ? || ' hours')
                           ORDER BY timestamp DESC
                           LIMIT ?''',
                        (hours, limit)
                    )
                return cursor.fetchall()
            except Exception as e:
                log.error(f"Failed to get recent metrics: {e}")
                return []
    
    def get_metric_summary(self, metric_type: str, metric_name: str, hours: int = 24):
        """
        Get statistical summary of a specific metric.
        
        Args:
            metric_type: Type of metric
            metric_name: Name of metric
            hours: Number of hours to analyze
            
        Returns:
            dict with avg, min, max, count
        """
        with self.lock:
            try:
                conn = self._get_conn()
                cursor = conn.execute(
                    '''SELECT
                        AVG(value) as avg,
                        MIN(value) as min,
                        MAX(value) as max,
                        COUNT(*) as count
                       FROM metrics
                       WHERE metric_type = ?
                       AND metric_name = ?
                       AND timestamp > datetime('now', '-' || ? || ' hours')''',
                    (metric_type, metric_name, hours)
                )
                row = cursor.fetchone()

            except Exception as e:
                log.error(f"Failed to get metric summary: {e}")
                return {'avg': 0, 'min': 0, 'max': 0, 'count': 0, 'error': str(e)}

        if row and row[3] > 0:  # count > 0
            return {
                'avg': round(row[0], 2) if row[0] else 0,
                'min': round(row[1], 2) if row[1] else 0,
                'max': round(row[2], 2) if row[2] else 0,
                'count': row[3]
            }
        return {'avg': 0, 'min': 0, 'max': 0, 'count': 0}
    
    def cleanup_old_metrics(self, days: int = 7):
        """
        Delete metrics older than specified days.
        
        Args:
            days: Delete metrics older than this many days
            
        Returns:
            Number of records deleted
        """
        with self.lock:
            try:
                conn = self._get_conn()
                cursor = conn.execute(
                    '''DELETE FROM metrics
                       WHERE timestamp < datetime('now', '-' || ? || ' days')''',
                    (days,)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                if deleted_count > 0:
                    conn.execute('VACUUM')
                    conn.commit()
                log.info(f"Cleaned up {deleted_count} old metrics (older than {days} days)")
                return deleted_count
            except Exception as e:
                log.error(f"Failed to cleanup old metrics: {e}")
                return 0


# Global singleton instance
metrics_logger = MetricsLogger()
