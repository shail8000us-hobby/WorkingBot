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
        lines (int): Number of log lines to return (default: 100)
        instance (str): Optional instance name (e.g., BTCUSD_LONG)
    
    Returns:
        JSON response with log lines
    
    Example:
        GET /api/logs?lines=50&instance=BTCUSD_LONG
        Response: {"logs": ["line 1", "line 2", ...], "instance": "BTCUSD_LONG"}
    """
    try:
        lines = request.args.get('lines', 100, type=int)
        instance = request.args.get('instance')
        
        # Cap at reasonable limit to prevent memory issues
        lines = min(lines, 10000)
        
        # v6.0: Use instance-specific log file if provided
        if instance:
            from pathlib import Path
            BASE_DIR = Path(__file__).parent.parent.parent.parent
            
            # Map instance name to PM2 process name
            # BTCUSD_LONG -> gridbot-btcusd-live
            # ETHUSD_LONG -> gridbot-ethusd-live
            # BTCUSD_SHORT -> gridbot-btcusd-short
            instance_lower = instance.lower()
            symbol = instance_lower.split('_')[0] if '_' in instance_lower else instance_lower
            mode = instance_lower.split('_')[1] if '_' in instance_lower else 'long'
            
            # PM2 process naming: gridbot-{symbol}-{live|short}
            # LONG mode uses "live", SHORT mode uses "short"
            pm2_suffix = 'live' if mode == 'long' else mode
            pm2_process = f'gridbot-{symbol}-{pm2_suffix}'
            
            # Try PM2 log file first (most common for multi-instance setup)
            pm2_log = BASE_DIR / 'reports' / f'pm2-{pm2_process}-out.log'
            
            # Fallback to direct log file
            direct_log = BASE_DIR / f'gridbot_{instance.lower()}.log'
            
            if pm2_log.exists():
                log_lines = get_recent_logs(lines, log_file=str(pm2_log))
            elif direct_log.exists():
                log_lines = get_recent_logs(lines, log_file=str(direct_log))
            else:
                log.warning(f"No log file found for instance {instance}. Tried: {pm2_log}, {direct_log}")
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
        lines = request.args.get('lines', 50, type=int)
        bot_type = request.args.get('bot_type', 'trading', type=str)
        log_file = request.args.get('log_file', None, type=str)
        instance = request.args.get('instance')
        
        # Cap at reasonable limit
        lines = min(lines, 10000)
        
        # v6.0: Determine log file based on instance first
        if instance:
            from pathlib import Path
            BASE_DIR = Path(__file__).parent.parent.parent.parent
            
            # Map instance name to PM2 process name
            instance_lower = instance.lower()
            symbol = instance_lower.split('_')[0] if '_' in instance_lower else instance_lower
            mode = instance_lower.split('_')[1] if '_' in instance_lower else 'long'
            
            # PM2 process naming: gridbot-{symbol}-{live|short}
            pm2_suffix = 'live' if mode == 'long' else mode
            pm2_process = f'gridbot-{symbol}-{pm2_suffix}'
            
            # Try PM2 log file first
            pm2_log = BASE_DIR / 'reports' / f'pm2-{pm2_process}-out.log'
            
            # Fallback to direct log file
            direct_log = BASE_DIR / f'gridbot_{instance.lower()}.log'
            
            if pm2_log.exists():
                log_file = str(pm2_log)
            elif direct_log.exists():
                log_file = str(direct_log)
            else:
                log.warning(f"No log file found for instance {instance}. Tried: {pm2_log}, {direct_log}")
                log_file = None
        
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
