#!/usr/bin/env python3
"""
Real-time Error Monitoring Service
Scans bot logs, detects errors, and auto-resolves fixed issues
"""

import sys
import time
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import json
import os

# Add parent directory to path for imports
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from bot.observability.errors import ErrorClassifier
from bot.observability.errors.catalog import ErrorCatalog

class ErrorMonitor:
    """
    Monitors bot logs in real-time and updates Error Intelligence database
    """
    
    def __init__(self, db_path: str, log_dir: str = None):
        self.db_path = db_path
        self.log_dir = Path(log_dir) if log_dir else BASE_DIR / "logs"
        
        # Initialize classifier
        catalog = ErrorCatalog()
        self.classifier = ErrorClassifier(catalog)
        
        # Error patterns to detect in logs
        self.error_patterns = [
            # API errors
            (r'(?i)api.*auth.*failed|authentication.*failed', 'API_AUTH_FAILED', 'trading', 'critical'),
            (r'(?i)api.*rate.*limit|too many requests', 'API_RATE_LIMIT', 'trading', 'high'),
            (r'(?i)connection.*refused|connection.*timeout', 'CONNECTION_FAILED', 'trading', 'high'),
            (r'(?i)insufficient.*balance|not enough balance', 'INSUFFICIENT_BALANCE', 'trading', 'high'),
            
            # Grid errors
            (r'(?i)grid.*spacing.*invalid|invalid.*grid', 'INVALID_GRID_CONFIG', 'trading', 'critical'),
            (r'(?i)order.*failed|failed.*to.*place.*order', 'ORDER_PLACEMENT_FAILED', 'trading', 'high'),
            (r'(?i)order.*not.*found|unknown.*order', 'ORDER_NOT_FOUND', 'trading', 'medium'),
            
            # Health errors
            (r'(?i)guardian.*stopped|guardian.*failed', 'GUARDIAN_FAILURE', 'health', 'critical'),
            (r'(?i)heartbeat.*missed|heartbeat.*timeout', 'HEARTBEAT_TIMEOUT', 'health', 'high'),
            
            # System errors
            (r'(?i)database.*error|sqlite.*error', 'DATABASE_ERROR', 'trading', 'high'),
            (r'(?i)file.*not.*found|no such file', 'FILE_NOT_FOUND', 'trading', 'medium'),
        ]
        
        # Track file positions for tail-like reading
        self.file_positions: Dict[str, int] = {}
        
    def clear_test_errors(self):
        """Remove test errors from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE errors 
            SET status = 'resolved', 
                resolved_at = ?,
                resolution_notes = 'Auto-resolved: Test error cleared'
            WHERE message_raw LIKE '%Test error%' 
            AND status != 'resolved'
        """, (datetime.now().isoformat(),))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"✅ Cleared {deleted} test errors")
        return deleted
    
    def auto_resolve_old_errors(self, hours: int = 24):
        """
        Auto-resolve errors that haven't occurred recently
        If an error hasn't been seen in X hours, it's likely fixed
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
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
            cutoff_time
        ))
        
        resolved = cursor.rowcount
        conn.commit()
        conn.close()
        
        if resolved > 0:
            print(f"✅ Auto-resolved {resolved} old errors (not seen in {hours}h)")
        
        return resolved
    
    def scan_log_file(self, log_path: Path) -> List[Dict]:
        """
        Scan a log file for new errors since last position
        """
        if not log_path.exists():
            return []
        
        errors_found = []
        
        # Get last read position
        file_key = str(log_path)
        last_pos = self.file_positions.get(file_key, 0)
        
        try:
            with open(log_path, 'r') as f:
                # Seek to last position
                f.seek(last_pos)
                
                # Read new lines
                for line in f:
                    # Check each error pattern
                    for pattern, code, source, severity in self.error_patterns:
                        if re.search(pattern, line):
                            errors_found.append({
                                'code': code,
                                'source': source,
                                'severity': severity,
                                'message': line.strip(),
                                'log_file': log_path.name,
                                'timestamp': datetime.now().isoformat()
                            })
                            break  # One error per line
                
                # Save new position
                self.file_positions[file_key] = f.tell()
        
        except Exception as e:
            print(f"❌ Error reading {log_path}: {e}")
        
        return errors_found
    
    def report_error(self, error_data: Dict):
        """
        Report an error to Error Intelligence system
        """
        try:
            classified = self.classifier.classify_error(
                error_code=error_data['code'],
                error_message=error_data['message'],
                source=error_data['source'],
                severity=error_data['severity'],
                context={
                    'log_file': error_data.get('log_file', 'unknown'),
                    'detected_at': error_data['timestamp']
                }
            )
            
            # Insert or update in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if this error exists (by signature)
            signature = f"{classified['source']}:{classified['code']}:{hash(classified['message_raw'])}"
            
            cursor.execute("SELECT id, occurrence_count FROM errors WHERE signature = ?", (signature,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing error
                error_id, count = existing
                cursor.execute("""
                    UPDATE errors 
                    SET last_seen = ?,
                        occurrence_count = occurrence_count + 1,
                        status = CASE WHEN status = 'resolved' THEN 'open' ELSE status END
                    WHERE id = ?
                """, (datetime.now().isoformat(), error_id))
                print(f"🔄 Updated existing error: {classified['code']} (count: {count + 1})")
            else:
                # Insert new error
                cursor.execute("""
                    INSERT INTO errors (
                        id, code, source, severity, status, message_raw,
                        title, explanation, likely_causes, suggested_actions,
                        can_auto_fix, available_fixes, first_seen, last_seen,
                        occurrence_count, context, links, signature
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    classified['id'],
                    classified['code'],
                    classified['source'],
                    classified['severity'],
                    'open',
                    classified['message_raw'],
                    classified.get('title', classified['code']),
                    classified.get('explanation', ''),
                    json.dumps(classified.get('likely_causes', [])),
                    json.dumps(classified.get('suggested_actions', [])),
                    classified.get('can_auto_fix', False),
                    json.dumps(classified.get('available_fixes', [])),
                    classified['first_seen'],
                    classified['last_seen'],
                    1,
                    json.dumps(classified.get('context', {})),
                    json.dumps(classified.get('links', [])),
                    signature
                ))
                print(f"🆕 New error detected: {classified['code']}")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"❌ Failed to report error: {e}")
    
    def scan_all_logs(self):
        """
        Scan all log files for new errors
        """
        log_files = [
            self.log_dir / "guardian.log",
            self.log_dir / "health.log",
            BASE_DIR / "bot_run.log",
            BASE_DIR / "guardian_debug.log",
            BASE_DIR / "webui_error_intelligence.log",
        ]
        
        total_errors = 0
        for log_file in log_files:
            if log_file.exists():
                errors = self.scan_log_file(log_file)
                for error in errors:
                    self.report_error(error)
                total_errors += len(errors)
        
        return total_errors
    
    def run_once(self):
        """
        Run one monitoring cycle
        """
        print(f"\n🔍 [{datetime.now().strftime('%H:%M:%S')}] Scanning for errors...")
        
        # Auto-resolve old errors (not seen in 24 hours)
        self.auto_resolve_old_errors(hours=24)
        
        # Scan logs for new errors
        new_errors = self.scan_all_logs()
        
        if new_errors > 0:
            print(f"⚠️  Detected {new_errors} new error(s)")
        else:
            print(f"✅ No new errors detected")
    
    def run_continuous(self, interval: int = 10):
        """
        Run continuous monitoring
        """
        print(f"🚀 Starting Error Monitor (scanning every {interval}s)")
        print(f"📂 Log directory: {self.log_dir}")
        print(f"💾 Database: {self.db_path}")
        
        # Clear test errors on startup
        self.clear_test_errors()
        
        try:
            while True:
                self.run_once()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n⏹️  Error Monitor stopped")

def main():
    """
    Main entry point
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-time Error Monitoring Service')
    parser.add_argument('--db', default=str(BASE_DIR / 'data' / 'errors.db'),
                        help='Path to errors database')
    parser.add_argument('--logs', default=str(BASE_DIR / 'logs'),
                        help='Path to logs directory')
    parser.add_argument('--interval', type=int, default=10,
                        help='Scan interval in seconds')
    parser.add_argument('--once', action='store_true',
                        help='Run once and exit (no continuous monitoring)')
    parser.add_argument('--clear-test', action='store_true',
                        help='Clear test errors and exit')
    
    args = parser.parse_args()
    
    monitor = ErrorMonitor(db_path=args.db, log_dir=args.logs)
    
    if args.clear_test:
        monitor.clear_test_errors()
    elif args.once:
        monitor.run_once()
    else:
        monitor.run_continuous(interval=args.interval)

if __name__ == '__main__':
    main()
