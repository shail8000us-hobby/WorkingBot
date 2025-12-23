#!/usr/bin/env python3
"""
Simple Error Auto-Resolver
Automatically resolves old errors that haven't occurred recently
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "errors.db"

def clear_test_errors():
    """Remove test errors"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE errors 
        SET status = 'resolved', 
            resolved_at = ?,
            resolution_notes = 'Auto-resolved: Test error cleared'
        WHERE message_raw LIKE '%Test error%' 
        AND status != 'resolved'
    """, (datetime.now().isoformat(),))
    
    count = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"✅ Cleared {count} test error(s)")
    return count

def auto_resolve_old_errors(hours=24):
    """Auto-resolve errors not seen in X hours"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    cursor.execute("""
        UPDATE errors 
        SET status = 'resolved',
            resolved_at = ?,
            resolution_notes = ?
        WHERE status IN ('open', 'acknowledged')
        AND last_seen < ?
    """, (
        datetime.now().isoformat(),
        f'Auto-resolved: No occurrence in {hours} hours',
        cutoff
    ))
    
    count = cursor.rowcount
    conn.commit()
    conn.close()
    
    if count > 0:
        print(f"✅ Auto-resolved {count} old error(s) (not seen in {hours}h)")
    else:
        print(f"ℹ️  No old errors to resolve")
    
    return count

def show_current_errors():
    """Display current open/acknowledged errors"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT code, message_raw, severity, status, occurrence_count, last_seen
        FROM errors
        WHERE status IN ('open', 'acknowledged')
        ORDER BY severity DESC, last_seen DESC
    """)
    
    errors = cursor.fetchall()
    conn.close()
    
    if errors:
        print(f"\n📊 Current Active Errors ({len(errors)}):")
        print("-" * 80)
        for code, msg, sev, status, count, last_seen in errors:
            print(f"  [{sev.upper()}] {code}")
            print(f"    Message: {msg[:60]}...")
            print(f"    Status: {status} | Count: {count} | Last seen: {last_seen}")
            print()
    else:
        print("\n✅ No active errors")
    
    return len(errors)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Error Auto-Resolver')
    parser.add_argument('--clear-test', action='store_true', help='Clear test errors')
    parser.add_argument('--resolve-old', type=int, metavar='HOURS', 
                        help='Auto-resolve errors not seen in X hours')
    parser.add_argument('--show', action='store_true', help='Show current errors')
    
    args = parser.parse_args()
    
    if args.clear_test:
        clear_test_errors()
    
    if args.resolve_old:
        auto_resolve_old_errors(hours=args.resolve_old)
    
    if args.show or not (args.clear_test or args.resolve_old):
        show_current_errors()
