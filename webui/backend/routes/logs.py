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
    
    v6.0: Supports per-instance log filtering
    
    Query Parameters:
        lines (int): Number of log lines to return (default: 30)
        instance (str): Optional instance name (e.g., BTCUSD_LONG)
    
    Returns:
        JSON response with log lines
    
    Example:
        GET /api/logs?lines=50&instance=BTCUSD_LONG
        Response: {"logs": ["line 1", "line 2", ...], "instance": "BTCUSD_LONG"}
    """
    try:
        from pathlib import Path
        BASE_DIR = Path(__file__).parent.parent.parent.parent
        
        lines = request.args.get('lines', 30, type=int)
        instance = request.args.get('instance')
        
        # Cap at reasonable limit to prevent memory issues
        lines = min(lines, 10000)
        
        # v6.0: Use instance-specific log file if provided
        if instance:
            # Derive ticker from instance name (BTCUSD_LONG → btc, ETHUSD_LONG → eth)
            symbol = instance.split('_')[0]
            ticker = symbol[:3].lower()
            instance_dashed = instance.replace('_', '-')

            # PM2 ecosystem config names processes gridbot-{ticker}-live
            # Logs stored as bot/logs/pm2-gridbot-{ticker}-live-{out|error}.log
            possible_pm2_logs = [
                # Ecosystem-named PM2 logs (primary location)
                BASE_DIR / 'bot' / 'logs' / f'pm2-gridbot-{ticker}-live-out.log',
                BASE_DIR / 'bot' / 'logs' / f'pm2-gridbot-{ticker}-live-error.log',
                BASE_DIR / 'bot' / 'logs' / f'pm2-gridbot-{ticker}-live.log',
                # Instance-named PM2 logs (alternative naming)
                BASE_DIR / 'logs' / 'pm2' / f'gridbot-{instance_dashed}-error-0.log',
                BASE_DIR / 'logs' / 'pm2' / f'gridbot-{instance_dashed}-out-0.log',
                BASE_DIR / 'reports' / f'pm2-gridbot-{instance.lower().replace("_", "-")}-out.log',
            ]

            # Fallback to direct log file
            direct_log = BASE_DIR / 'bot' / 'logs' / f'gridbot_{symbol.lower()}.log'

            # Find the most recently modified log file
            log_file_found = None
            newest_mtime = 0
            for pm2_log in possible_pm2_logs:
                if pm2_log.exists() and pm2_log.stat().st_size > 0:
                    mtime = pm2_log.stat().st_mtime
                    if mtime > newest_mtime:
                        newest_mtime = mtime
                        log_file_found = str(pm2_log)

            if log_file_found:
                log_lines = get_recent_logs(lines, log_file=log_file_found)
            elif direct_log.exists():
                log_lines = get_recent_logs(lines, log_file=str(direct_log))
            else:
                log_lines = []
        else:
            log_lines = get_recent_logs(lines)
        
        return jsonify({
            'logs': log_lines,
            'count': len(log_lines),
            'instance': instance
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
    
    v6.0: Supports per-instance log filtering
    
    Query Parameters:
        lines (int): Number of log lines to return (default: 50)
        bot_type (str): Bot type ('trading', 'guardian', 'monitoring') - optional
        log_file (str): Specific log file path - optional, overrides bot_type
        instance (str): Instance name (e.g., BTCUSD_LONG) - overrides bot_type
    
    Returns:
        JSON response with success status and log lines
    
    Example:
        GET /api/logs/recent?lines=100&instance=BTCUSD_LONG
        Response: {"success": true, "logs": [...], "instance": "BTCUSD_LONG"}
    """
    try:
        from pathlib import Path
        BASE_DIR = Path(__file__).parent.parent.parent.parent
        
        lines = request.args.get('lines', 30, type=int)
        bot_type = request.args.get('bot_type', 'trading', type=str)
        log_file = request.args.get('log_file', None, type=str)
        instance = request.args.get('instance')
        
        # Cap at reasonable limit
        lines = min(lines, 10000)
        
        # v6.0: Determine log file based on instance first
        if instance:
            symbol = instance.split('_')[0]
            ticker = symbol[:3].lower()
            instance_dashed = instance.replace('_', '-')

            possible_pm2_logs = [
                BASE_DIR / 'bot' / 'logs' / f'pm2-gridbot-{ticker}-live-out.log',
                BASE_DIR / 'bot' / 'logs' / f'pm2-gridbot-{ticker}-live-error.log',
                BASE_DIR / 'bot' / 'logs' / f'pm2-gridbot-{ticker}-live.log',
                BASE_DIR / 'logs' / 'pm2' / f'gridbot-{instance_dashed}-error-0.log',
                BASE_DIR / 'logs' / 'pm2' / f'gridbot-{instance_dashed}-out-0.log',
                BASE_DIR / 'reports' / f'pm2-gridbot-{instance.lower().replace("_", "-")}-out.log',
            ]

            direct_log = BASE_DIR / 'bot' / 'logs' / f'gridbot_{symbol.lower()}.log'

            log_file = None
            newest_mtime = 0
            for pm2_log in possible_pm2_logs:
                if pm2_log.exists() and pm2_log.stat().st_size > 0:
                    mtime = pm2_log.stat().st_mtime
                    if mtime > newest_mtime:
                        newest_mtime = mtime
                        log_file = str(pm2_log)

            if not log_file and direct_log.exists():
                log_file = str(direct_log)
        
        
        # Determine log file based on bot_type if not explicitly specified
        if not log_file:
            base_path = Path(__file__).parent.parent.parent.parent
            
            log_file_map = {
                'trading': 'bot/logs/bot.log',
                'live_trading': 'bot/logs/bot.log',
                'guardian': None,  # Will check multiple paths below
                'monitoring': 'bot/logs/heartbeat_monitor.log',
                'health': 'bot/logs/heartbeat_monitor.log'
            }
            
            if bot_type == 'guardian':
                # Check multiple Guardian log locations (LaunchAgent, PM2, etc.)
                guardian_paths = [
                    'bot/logs/guardian.log',
                    'logs/webui_guardian.log',
                    'logs/guardian_monitor.log'
                ]
                for path in guardian_paths:
                    full_path = base_path / path
                    if full_path.exists():
                        log_file = path
                        break
                if not log_file:
                    log_file = 'bot/logs/guardian.log'  # Default
            else:
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
