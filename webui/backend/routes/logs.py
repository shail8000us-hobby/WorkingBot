"""
Logs Routes Blueprint

This module handles all API routes related to log retrieval and viewing.

Routes:
- GET /api/logs - Get recent logs with configurable line count
- GET /api/logs/recent - Get recent logs (alias for frontend compatibility)

Dependencies:
- utils.file_helpers (get_recent_logs)

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import logging
from flask import Blueprint, jsonify, request

# Import shared utilities
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.file_helpers import get_recent_logs

log = logging.getLogger(__name__)

# Create blueprint
logs_bp = Blueprint('logs', __name__)

# ============================================================================
# Route Handlers
# ============================================================================

@logs_bp.route('/api/logs', methods=['GET'])
def get_logs():
    """
    Get recent logs from bot log file
    
    Query Parameters:
        lines (int): Number of log lines to return (default: 100)
    
    Returns:
        JSON response with log lines
    
    Example:
        GET /api/logs?lines=50
        Response: {"logs": ["line 1", "line 2", ...]}
    """
    try:
        lines = request.args.get('lines', 100, type=int)
        
        # Cap at reasonable limit to prevent memory issues
        lines = min(lines, 10000)
        
        log_lines = get_recent_logs(lines)
        
        return jsonify({
            'logs': log_lines,
            'count': len(log_lines)
        }), 200
        
    except Exception as e:
        log.error(f"Error getting logs: {e}")
        return jsonify({
            'error': str(e),
            'logs': []
        }), 500


@logs_bp.route('/api/logs/recent', methods=['GET'])
def get_logs_recent():
    """
    Get recent logs (alias endpoint for frontend compatibility)
    
    This endpoint supports bot-specific log file selection.
    
    Query Parameters:
        lines (int): Number of log lines to return (default: 50)
        bot_type (str): Bot type ('trading', 'guardian', 'monitoring') - optional
        log_file (str): Specific log file path - optional, overrides bot_type
    
    Returns:
        JSON response with success status and log lines
    
    Example:
        GET /api/logs/recent?lines=100&bot_type=guardian
        Response: {"success": true, "logs": [...], "bot_type": "guardian"}
    """
    try:
        lines = request.args.get('lines', 50, type=int)
        bot_type = request.args.get('bot_type', 'trading', type=str)
        log_file = request.args.get('log_file', None, type=str)
        
        # Cap at reasonable limit
        lines = min(lines, 10000)
        
        # Determine log file based on bot_type if not explicitly specified
        if not log_file:
            log_file_map = {
                'trading': 'bot/logs/bot.log',
                'live_trading': 'bot/logs/bot.log',
                'guardian': 'bot/logs/guardian.log',
                'monitoring': 'bot/logs/heartbeat_monitor.log',
                'health': 'bot/logs/heartbeat_monitor.log'
            }
            log_file = log_file_map.get(bot_type, 'bot/logs/bot.log')
        
        log.debug(f"Fetching logs from {log_file} for bot_type={bot_type}")
        log_lines = get_recent_logs(lines, log_file)
        
        return jsonify({
            'success': True,
            'logs': log_lines,
            'count': len(log_lines),
            'bot_type': bot_type,
            'log_file': log_file
        }), 200
        
    except Exception as e:
        log.error(f"Error getting recent logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': []
        }), 500
