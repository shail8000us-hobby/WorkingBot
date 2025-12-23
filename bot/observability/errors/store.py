"""
Error Storage - SQLite-based persistent storage for error events
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from .schema import ErrorEvent, ErrorStatus, ErrorSeverity, ErrorSource


class ErrorStore:
    """Persistent storage for error events"""
    
    def __init__(self, db_path: str = "data/errors.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                source TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                message_raw TEXT NOT NULL,
                traceback TEXT,
                title TEXT,
                explanation TEXT,
                likely_causes TEXT,
                suggested_actions TEXT,
                can_auto_fix BOOLEAN,
                available_fixes TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                occurrence_count INTEGER DEFAULT 1,
                context TEXT,
                links TEXT,
                acknowledged_by TEXT,
                acknowledged_at TEXT,
                resolved_at TEXT,
                resolution_notes TEXT,
                signature TEXT NOT NULL
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON errors(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_severity ON errors(severity)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON errors(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signature ON errors(signature)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_last_seen ON errors(last_seen)")
        
        # Audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_id TEXT NOT NULL,
                action TEXT NOT NULL,
                user TEXT,
                timestamp TEXT NOT NULL,
                details TEXT,
                result TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save(self, error: ErrorEvent) -> None:
        """Save or update an error event"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if error already exists (by signature)
        cursor.execute("SELECT id FROM errors WHERE signature = ?", (error.get_signature(),))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing error
            cursor.execute("""
                UPDATE errors SET
                    last_seen = ?,
                    occurrence_count = occurrence_count + 1,
                    context = ?
                WHERE signature = ?
            """, (
                error.last_seen.isoformat(),
                json.dumps(error.context),
                error.get_signature()
            ))
        else:
            # Insert new error
            cursor.execute("""
                INSERT INTO errors (
                    id, code, source, severity, status, message_raw, traceback,
                    title, explanation, likely_causes, suggested_actions,
                    can_auto_fix, available_fixes, first_seen, last_seen,
                    occurrence_count, context, links, signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                error.id,
                error.code,
                error.source.value,
                error.severity.value,
                error.status.value,
                error.message_raw,
                error.traceback,
                error.title,
                error.explanation,
                json.dumps(error.likely_causes),
                json.dumps(error.suggested_actions),
                error.can_auto_fix,
                json.dumps([f.to_dict() for f in error.available_fixes]),
                error.first_seen.isoformat(),
                error.last_seen.isoformat(),
                error.occurrence_count,
                json.dumps(error.context),
                json.dumps(error.links),
                error.get_signature()
            ))
        
        conn.commit()
        conn.close()
    
    def get_by_id(self, error_id: str) -> Optional[ErrorEvent]:
        """Get error by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM errors WHERE id = ?", (error_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_error(row)
    
    def get_all(
        self,
        status: Optional[ErrorStatus] = None,
        severity: Optional[ErrorSeverity] = None,
        source: Optional[ErrorSource] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ErrorEvent]:
        """Get errors with filters"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM errors WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status.value)
        
        if severity:
            query += " AND severity = ?"
            params.append(severity.value)
        
        if source:
            query += " AND source = ?"
            params.append(source.value)
        
        query += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_error(row) for row in rows]
    
    def update_status(
        self,
        error_id: str,
        status: ErrorStatus,
        user: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """Update error status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = ["status = ?"]
        params = [status.value]
        
        if status == ErrorStatus.ACKNOWLEDGED:
            updates.append("acknowledged_by = ?")
            updates.append("acknowledged_at = ?")
            params.extend([user, datetime.utcnow().isoformat()])
        elif status == ErrorStatus.RESOLVED:
            updates.append("resolved_at = ?")
            updates.append("resolution_notes = ?")
            params.extend([datetime.utcnow().isoformat(), notes])
        
        params.append(error_id)
        
        cursor.execute(
            f"UPDATE errors SET {', '.join(updates)} WHERE id = ?",
            params
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def log_action(
        self,
        error_id: str,
        action: str,
        user: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None
    ):
        """Log an action taken on an error"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO error_audit_log (error_id, action, user, timestamp, details, result)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            error_id,
            action,
            user,
            datetime.utcnow().isoformat(),
            json.dumps(details) if details else None,
            result
        ))
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get error statistics (only active errors: open/acknowledged)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total by status (only active)
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM errors 
            WHERE status IN ('open', 'acknowledged')
            GROUP BY status
        """)
        stats['by_status'] = dict(cursor.fetchall())
        
        # Total by severity (only active)
        cursor.execute("""
            SELECT severity, COUNT(*) as count 
            FROM errors 
            WHERE status IN ('open', 'acknowledged')
            GROUP BY severity
        """)
        stats['by_severity'] = dict(cursor.fetchall())
        
        # Total by source (only active)
        cursor.execute("""
            SELECT source, COUNT(*) as count 
            FROM errors 
            WHERE status IN ('open', 'acknowledged')
            GROUP BY source
        """)
        stats['by_source'] = dict(cursor.fetchall())
        
        # Most common errors (only active)
        cursor.execute("""
            SELECT code, COUNT(*) as count 
            FROM errors 
            WHERE status IN ('open', 'acknowledged')
            GROUP BY code 
            ORDER BY count DESC 
            LIMIT 10
        """)
        stats['most_common'] = [{'code': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        conn.close()
        return stats
    
    def _row_to_error(self, row: sqlite3.Row) -> ErrorEvent:
        """Convert database row to ErrorEvent"""
        data = dict(row)
        
        # Parse JSON fields
        data['likely_causes'] = json.loads(data['likely_causes']) if data['likely_causes'] else []
        data['suggested_actions'] = json.loads(data['suggested_actions']) if data['suggested_actions'] else []
        data['available_fixes'] = json.loads(data['available_fixes']) if data['available_fixes'] else []
        data['context'] = json.loads(data['context']) if data['context'] else {}
        data['links'] = json.loads(data['links']) if data['links'] else []
        
        # Remove signature field (internal only)
        data.pop('signature', None)
        
        return ErrorEvent.from_dict(data)
