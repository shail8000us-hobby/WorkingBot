"""
Error Intelligence System - Core Module
Provides error collection, analysis, and management capabilities
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

log = logging.getLogger('error_intelligence')


class ErrorIntelligenceManager:
    """
    Core Error Intelligence System Manager
    
    Features:
    - Error collection from multiple sources
    - Real-time error analysis
    - Error statistics and reporting
    - Integration with WebSocket notifications
    """
    
    def __init__(self, config: Dict[str, Any], socketio=None):
        """Initialize Error Intelligence Manager"""
        self.config = config
        self.socketio = socketio
        self.db_path = config.get('db_path', 'data/errors.db')
        self.log_paths = config.get('log_paths', {})
        
        # Initialize database
        self._init_database()
        
        # Statistics cache
        self._stats_cache = {}
        self._cache_time = None
        
        log.info("✅ Error Intelligence Manager initialized")
    
    def start(self):
        """Start the error intelligence system"""
        log.info("🚀 Error Intelligence System started")
        return True
    
    def _init_database(self):
        """Initialize SQLite database for error storage"""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS errors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        source TEXT NOT NULL,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        details TEXT,
                        resolved BOOLEAN DEFAULT FALSE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
        except Exception as e:
            log.error(f"Failed to initialize error database: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get error statistics"""
        try:
            # Check cache first
            if self._stats_cache and self._cache_time:
                if datetime.now() - self._cache_time < timedelta(minutes=1):
                    return self._stats_cache
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get total errors
                cursor.execute("SELECT COUNT(*) FROM errors")
                total_errors = cursor.fetchone()[0]
                
                # Get errors by level
                cursor.execute("""
                    SELECT level, COUNT(*) 
                    FROM errors 
                    WHERE created_at > datetime('now', '-24 hours')
                    GROUP BY level
                """)
                errors_by_level = dict(cursor.fetchall())
                
                # Get errors by source
                cursor.execute("""
                    SELECT source, COUNT(*) 
                    FROM errors 
                    WHERE created_at > datetime('now', '-24 hours')
                    GROUP BY source
                """)
                errors_by_source = dict(cursor.fetchall())
                
                # Get recent errors
                cursor.execute("""
                    SELECT timestamp, source, level, message
                    FROM errors 
                    WHERE created_at > datetime('now', '-1 hour')
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                recent_errors = [
                    {
                        'timestamp': row[0],
                        'source': row[1],
                        'level': row[2],
                        'message': row[3]
                    }
                    for row in cursor.fetchall()
                ]
                
                stats = {
                    'total_errors': total_errors,
                    'errors_by_level': errors_by_level,
                    'errors_by_source': errors_by_source,
                    'recent_errors': recent_errors,
                    'last_updated': datetime.now().isoformat()
                }
                
                # Cache the results
                self._stats_cache = stats
                self._cache_time = datetime.now()
                
                return stats
                
        except Exception as e:
            log.error(f"Failed to get error statistics: {e}")
            return {
                'total_errors': 0,
                'errors_by_level': {},
                'errors_by_source': {},
                'recent_errors': [],
                'last_updated': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def log_error(self, source: str, level: str, message: str, details: str = None):
        """Log an error to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO errors (timestamp, source, level, message, details)
                    VALUES (?, ?, ?, ?, ?)
                ''', (datetime.now().isoformat(), source, level, message, details))
                conn.commit()
                
                # Emit WebSocket notification if available
                if self.socketio:
                    self.socketio.emit('error_logged', {
                        'source': source,
                        'level': level,
                        'message': message,
                        'timestamp': datetime.now().isoformat()
                    })
                    
        except Exception as e:
            log.error(f"Failed to log error: {e}")
    
    def get_errors(self, status: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get errors with optional filtering"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM errors"
                params = []
                
                if status == 'open':
                    query += " WHERE resolved = FALSE"
                elif status == 'acknowledged':
                    query += " WHERE resolved = TRUE"
                
                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                columns = [description[0] for description in cursor.description]
                
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
                
        except Exception as e:
            log.error(f"Failed to get errors: {e}")
            return []
    
    def resolve_error(self, error_id: int) -> bool:
        """Mark an error as resolved"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("UPDATE errors SET resolved = TRUE WHERE id = ?", (error_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            log.error(f"Failed to resolve error: {e}")
            return False


# Blueprint for Flask routes
from flask import Blueprint, jsonify, request

errors_bp = Blueprint('errors', __name__)

@errors_bp.route('/api/errors', methods=['GET'])
def get_errors_endpoint():
    """Get errors with optional filtering"""
    try:
        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))
        
        # Get error manager from app context
        error_manager = getattr(request, 'error_manager', None)
        if not error_manager:
            return jsonify({'error': 'Error Intelligence System not available'}), 503
        
        errors = error_manager.get_errors(status=status, limit=limit)
        return jsonify({'errors': errors, 'count': len(errors)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@errors_bp.route('/api/errors/<int:error_id>/resolve', methods=['POST'])
def resolve_error_endpoint(error_id):
    """Resolve an error"""
    try:
        error_manager = getattr(request, 'error_manager', None)
        if not error_manager:
            return jsonify({'error': 'Error Intelligence System not available'}), 503
        
        success = error_manager.resolve_error(error_id)
        if success:
            return jsonify({'success': True, 'message': 'Error resolved'})
        else:
            return jsonify({'success': False, 'message': 'Error not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

