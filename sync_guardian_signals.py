#!/usr/bin/env python3
"""
Guardian Signal Sync Script

Copies Guardian signals from BTCUSD database to ETHUSD database.
This allows ETHUSD bot to use the same Guardian signals as BTCUSD.

Usage: python3 sync_guardian_signals.py
"""
import sqlite3
import time
from pathlib import Path

def sync_guardian_signals():
    """Sync Guardian signals from BTCUSD to ETHUSD database"""
    
    source_db = Path("data/bot_events_BTCUSD_LONG.db")
    target_db = Path("data/bot_events_ETHUSD_LONG.db")
    
    if not source_db.exists():
        print(f"❌ Source database not found: {source_db}")
        return
    
    if not target_db.exists():
        print(f"❌ Target database not found: {target_db}")
        return
    
    # Connect to both databases
    source_conn = sqlite3.connect(str(source_db))
    target_conn = sqlite3.connect(str(target_db))
    
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
            print("⚠️  No Guardian signals found in source database")
            return
        
        event_id, event_type, timestamp, correlation_id, aggregate_id, data, metadata = latest_signal
        signal_age = time.time() - timestamp
        
        print(f"📡 Latest Guardian signal: {event_type} (age: {signal_age:.1f}s)")
        
        # Check if this signal already exists in target
        target_cursor = target_conn.cursor()
        target_cursor.execute("""
            SELECT COUNT(*) FROM events 
            WHERE event_id = ? AND event_type = ?
        """, (event_id, event_type))
        
        exists = target_cursor.fetchone()[0] > 0
        
        if exists:
            print(f"✅ Signal already synced to ETHUSD database")
        else:
            # Insert signal into target database
            target_cursor.execute("""
                INSERT INTO events (event_id, event_type, timestamp, correlation_id, aggregate_id, data, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (event_id, event_type, timestamp, correlation_id, aggregate_id, data, metadata))
            
            target_conn.commit()
            print(f"✅ Synced Guardian signal to ETHUSD database")
        
        # Show stats
        target_cursor.execute("SELECT COUNT(*) FROM events WHERE event_type='guardian_signal_go'")
        go_count = target_cursor.fetchone()[0]
        
        target_cursor.execute("SELECT COUNT(*) FROM events WHERE event_type='guardian_signal_stop'")
        stop_count = target_cursor.fetchone()[0]
        
        print(f"📊 ETHUSD database stats: {go_count} GO signals, {stop_count} STOP signals")
        
    finally:
        source_conn.close()
        target_conn.close()

if __name__ == "__main__":
    print("=" * 80)
    print("Guardian Signal Sync - BTCUSD → ETHUSD")
    print("=" * 80)
    sync_guardian_signals()
    print("=" * 80)
