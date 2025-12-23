"""
Event Retention Policy

Automatically cleans up old guardian signal events to prevent database bloat.
Runs periodically to maintain a healthy database size.
"""
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class EventRetentionPolicy:
    """
    Manages automatic cleanup of old events to prevent database bloat.
    
    Guardian signals are generated every 5 seconds, leading to ~17,280 events/day.
    Without cleanup, this causes memory exhaustion.
    
    Retention Policy:
    - Guardian signals: Keep last 2 days (48 hours) to prevent disk bloat
    - Other events: Keep all (they are rare)
    """
    
    def __init__(self, db_path: str, retention_days: int = 2):
        """
        Initialize retention policy.
        
        Args:
            db_path: Path to SQLite event database
            retention_days: Number of days to keep guardian signals (default: 2 days / 48 hours)
        """
        self.db_path = db_path
        self.retention_days = retention_days
        self.last_cleanup_time = 0
        self.cleanup_interval = 3600  # Run cleanup every hour
        
        log.info(f"Event retention policy initialized: keep last {retention_days} days (48 hours auto-cleanup)")
    
    def should_cleanup(self) -> bool:
        """Check if it's time to run cleanup."""
        return (time.time() - self.last_cleanup_time) >= self.cleanup_interval
    
    def cleanup_old_events(self) -> Optional[dict]:
        """
        Remove old guardian signal events.
        
        Returns:
            Dict with cleanup stats or None if cleanup failed
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=self.retention_days)
            cutoff_timestamp = cutoff_time.timestamp()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Count events before cleanup
            cursor.execute("SELECT COUNT(*) FROM events")
            before_count = cursor.fetchone()[0]
            
            # Delete old guardian signals
            cursor.execute("""
                DELETE FROM events 
                WHERE event_type IN ('guardian_signal_go', 'guardian_signal_stop')
                AND timestamp < ?
            """, (cutoff_timestamp,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            # Get file size before VACUUM
            db_size_before = Path(self.db_path).stat().st_size / 1024 / 1024
            
            # Run VACUUM to reclaim space (but only if significant deletion)
            if deleted_count > 1000:
                log.info(f"Running VACUUM to reclaim space ({deleted_count:,} events deleted)...")
                cursor.execute("VACUUM")
                log.info("VACUUM complete")
            
            # Get final counts
            cursor.execute("SELECT COUNT(*) FROM events")
            after_count = cursor.fetchone()[0]
            
            conn.close()
            
            db_size_after = Path(self.db_path).stat().st_size / 1024 / 1024
            
            self.last_cleanup_time = time.time()
            
            stats = {
                'deleted_count': deleted_count,
                'before_count': before_count,
                'after_count': after_count,
                'db_size_before_mb': db_size_before,
                'db_size_after_mb': db_size_after,
                'cutoff_time': cutoff_time.isoformat()
            }
            
            if deleted_count > 0:
                log.info(
                    f"Event retention cleanup: deleted {deleted_count:,} old events "
                    f"(kept {after_count:,}, DB: {db_size_after:.1f}MB)"
                )
            
            return stats
            
        except Exception as e:
            log.error(f"Event retention cleanup failed: {e}", exc_info=True)
            return None
    
    def auto_cleanup_if_needed(self) -> Optional[dict]:
        """
        Automatically run cleanup if interval has elapsed.
        
        Returns:
            Cleanup stats dict if cleanup ran, None otherwise
        """
        if self.should_cleanup():
            return self.cleanup_old_events()
        return None
