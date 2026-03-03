#!/usr/bin/env python3
"""
Guardian Signal Broadcaster - Continuous Sync

Runs continuously, copying Guardian signals from BTCUSD to all other symbol databases.
This allows all symbols to share the same Guardian protection.

Run with PM2: pm2 start sync_guardian_continuous.py --name guardian-sync
"""
import sqlite3
import time
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

SOURCE_DB = Path("data/bot_events_BTCUSD_LONG.db")
TARGET_DBS = [
    Path("data/bot_events_ETHUSD_LONG.db"),
    # Add more symbol databases here as needed
]

SYNC_INTERVAL = 5  # seconds

def sync_signal_to_db(source_conn, target_db_path, last_synced_timestamp):
    """Sync latest Guardian signal to target database"""
    
    if not target_db_path.exists():
        return last_synced_timestamp
    
    try:
        # Get latest Guardian signal from source (after last_synced_timestamp)
        cursor = source_conn.cursor()
        cursor.execute("""
            SELECT event_id, event_type, timestamp, correlation_id, aggregate_id, data, metadata
            FROM events 
            WHERE event_type IN ('guardian_signal_go', 'guardian_signal_stop')
                AND timestamp > ?
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (last_synced_timestamp,))
        
        latest_signal = cursor.fetchone()
        
        if not latest_signal:
            return last_synced_timestamp  # No new signals
        
        event_id, event_type, timestamp, correlation_id, aggregate_id, data, metadata = latest_signal
        
        # Connect to target database
        target_conn = sqlite3.connect(str(target_db_path))
        target_cursor = target_conn.cursor()
        
        try:
            # Check if this signal already exists
            target_cursor.execute("""
                SELECT COUNT(*) FROM events 
                WHERE event_id = ?
            """, (event_id,))
            
            if target_cursor.fetchone()[0] == 0:
                # Insert new signal
                target_cursor.execute("""
                    INSERT INTO events (event_id, event_type, timestamp, correlation_id, aggregate_id, data, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (event_id, event_type, timestamp, correlation_id, aggregate_id, data, metadata))
                
                target_conn.commit()
                log.info(f"✅ Synced {event_type} to {target_db_path.name} (age: {time.time() - timestamp:.1f}s)")
            
            return timestamp
            
        finally:
            target_conn.close()
            
    except Exception as e:
        log.error(f"❌ Error syncing to {target_db_path.name}: {e}")
        return last_synced_timestamp

def run_continuous_sync():
    """Run continuous Guardian signal sync"""
    
    log.info("=" * 80)
    log.info("Guardian Signal Broadcaster - Starting")
    log.info(f"Source: {SOURCE_DB.name}")
    log.info(f"Targets: {', '.join(db.name for db in TARGET_DBS)}")
    log.info(f"Sync interval: {SYNC_INTERVAL}s")
    log.info("=" * 80)
    
    if not SOURCE_DB.exists():
        log.error(f"❌ Source database not found: {SOURCE_DB}")
        return
    
    # Track last synced timestamp for each target
    last_synced = {db: 0.0 for db in TARGET_DBS}
    
    # Connect to source database (keep connection open)
    source_conn = sqlite3.connect(str(SOURCE_DB))
    
    try:
        while True:
            for target_db in TARGET_DBS:
                last_synced[target_db] = sync_signal_to_db(
                    source_conn, 
                    target_db, 
                    last_synced[target_db]
                )
            
            time.sleep(SYNC_INTERVAL)
            
    except KeyboardInterrupt:
        log.info("🛑 Shutting down Guardian Signal Broadcaster...")
    finally:
        source_conn.close()

if __name__ == "__main__":
    run_continuous_sync()
