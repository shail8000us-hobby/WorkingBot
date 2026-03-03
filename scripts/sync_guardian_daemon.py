#!/usr/bin/env python3
"""
Guardian Signal Sync Daemon

Continuously syncs Guardian signals from BTCUSD to ETHUSD database every 5 seconds.
This ensures ETHUSD bot always has fresh Guardian signals.

Usage: python3 sync_guardian_daemon.py
"""
import sqlite3
import time
from pathlib import Path
import sys

def sync_guardian_signals():
    """Sync Guardian signals from BTCUSD to ETHUSD database"""
    
    source_db = Path("data/bot_events_BTCUSD_LONG.db")
    target_db = Path("data/bot_events_ETHUSD_LONG.db")
    
    if not source_db.exists():
        print(f"❌ Source database not found: {source_db}", flush=True)
        return False
    
    if not target_db.exists():
        print(f"❌ Target database not found: {target_db}", flush=True)
        return False
    
    # Connect to both databases
    try:
        source_conn = sqlite3.connect(str(source_db))
        target_conn = sqlite3.connect(str(target_db))
    except Exception as e:
        print(f"❌ Database connection error: {e}", flush=True)
        return False
    
    try:
        # Get latest Guardian signal from source
        cursor = source_conn.cursor()
        cursor.execute("""
            SELECT event_id, event_type, timestamp, correlation_id, aggregate_id, data, metadata
            FROM events 
            WHERE event_type IN ('guardian_signal_go', 'guardian_signal_stop')
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        
        latest_signal = cursor.fetchone()
        
        if not latest_signal:
            return True  # No signal yet, but not an error
        
        event_id, event_type, timestamp, correlation_id, aggregate_id, data, metadata = latest_signal
        signal_age = time.time() - timestamp
        
        # Check if this signal already exists in target
        target_cursor = target_conn.cursor()
        target_cursor.execute("""
            SELECT COUNT(*) FROM events 
            WHERE event_id = ? AND event_type = ?
        """, (event_id, event_type))
        
        exists = target_cursor.fetchone()[0] > 0
        
        if not exists:
            # Insert signal into target database
            target_cursor.execute("""
                INSERT INTO events (event_id, event_type, timestamp, correlation_id, aggregate_id, data, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (event_id, event_type, timestamp, correlation_id, aggregate_id, data, metadata))
            
            target_conn.commit()
            print(f"✅ Synced {event_type} (age: {signal_age:.1f}s)", flush=True)
        
        return True
        
    except Exception as e:
        print(f"❌ Sync error: {e}", flush=True)
        return False
    finally:
        source_conn.close()
        target_conn.close()

def main():
    """Main daemon loop"""
    print("🔄 Guardian Signal Sync Daemon started", flush=True)
    print("   Syncing BTCUSD → ETHUSD every 5 seconds", flush=True)
    
    while True:
        try:
            sync_guardian_signals()
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n👋 Daemon stopped", flush=True)
            sys.exit(0)
        except Exception as e:
            print(f"❌ Unexpected error: {e}", flush=True)
            time.sleep(5)  # Continue after error

if __name__ == "__main__":
    main()
