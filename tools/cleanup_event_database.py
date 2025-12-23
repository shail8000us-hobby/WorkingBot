#!/usr/bin/env python3
"""
Event Database Cleanup Tool

Removes old guardian signal events to prevent database bloat and memory issues.
Keeps recent events (last 7 days) and all other event types.
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_database(db_path: Path, dry_run: bool = False, keep_days: int = 7):
    """
    Clean up old guardian signal events from the database.
    
    Args:
        db_path: Path to the event database
        dry_run: If True, only show what would be deleted
        keep_days: Number of days of guardian signals to keep
    """
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    print(f"\n{'=' * 70}")
    print(f"EVENT DATABASE CLEANUP")
    print(f"{'=' * 70}")
    print(f"Database: {db_path}")
    print(f"Size: {db_path.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"Keep last: {keep_days} days of guardian signals")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'=' * 70}\n")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Get current event counts
        cursor.execute("SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY COUNT(*) DESC")
        event_counts = cursor.fetchall()
        
        print("Current Event Counts:")
        total_events = 0
        guardian_go = 0
        guardian_stop = 0
        for event_type, count in event_counts:
            print(f"  {event_type}: {count:,}")
            total_events += count
            if event_type == 'guardian_signal_go':
                guardian_go = count
            elif event_type == 'guardian_signal_stop':
                guardian_stop = count
        
        print(f"\nTotal Events: {total_events:,}")
        
        # Calculate cutoff timestamp (keep last N days)
        cutoff_time = datetime.now() - timedelta(days=keep_days)
        cutoff_timestamp = cutoff_time.timestamp()
        
        # Count events to be deleted
        cursor.execute("""
            SELECT COUNT(*) FROM events 
            WHERE event_type IN ('guardian_signal_go', 'guardian_signal_stop')
            AND timestamp < ?
        """, (cutoff_timestamp,))
        
        to_delete = cursor.fetchone()[0]
        to_keep = total_events - to_delete
        
        print(f"\n{'=' * 70}")
        print(f"CLEANUP ANALYSIS")
        print(f"{'=' * 70}")
        print(f"Events to DELETE: {to_delete:,} (older than {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')})")
        print(f"Events to KEEP: {to_keep:,}")
        print(f"Space savings: ~{(to_delete / total_events * 100):.1f}%")
        
        if dry_run:
            print(f"\n⚠️  DRY RUN - No changes made")
            return True
        
        # Confirm deletion
        print(f"\n⚠️  This will permanently delete {to_delete:,} old guardian signal events!")
        response = input("Continue? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("❌ Cleanup cancelled")
            return False
        
        # Delete old guardian signals
        print(f"\n🗑️  Deleting old events...")
        cursor.execute("""
            DELETE FROM events 
            WHERE event_type IN ('guardian_signal_go', 'guardian_signal_stop')
            AND timestamp < ?
        """, (cutoff_timestamp,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        print(f"✅ Deleted {deleted_count:,} events")
        
        # VACUUM to reclaim space
        print(f"\n🔧 Running VACUUM to reclaim disk space...")
        cursor.execute("VACUUM")
        
        new_size = db_path.stat().st_size / 1024 / 1024
        print(f"✅ Database compacted")
        print(f"   New size: {new_size:.2f} MB")
        
        # Get final counts
        cursor.execute("SELECT COUNT(*) FROM events")
        final_count = cursor.fetchone()[0]
        
        print(f"\n{'=' * 70}")
        print(f"CLEANUP COMPLETE")
        print(f"{'=' * 70}")
        print(f"Events remaining: {final_count:,}")
        print(f"Database size: {new_size:.2f} MB")
        print(f"✅ Cleanup successful!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def main():
    # Find database
    project_root = Path(__file__).parent.parent
    db_path = project_root / 'data' / 'bot_events_LONG.db'
    
    # Parse arguments
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    keep_days = 7
    
    for i, arg in enumerate(sys.argv):
        if arg in ['--keep-days', '-k'] and i + 1 < len(sys.argv):
            keep_days = int(sys.argv[i + 1])
    
    success = cleanup_database(db_path, dry_run=dry_run, keep_days=keep_days)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
