"""
Guardian Routes Blueprint

This module handles all API routes related to Safety Guardian control.

Routes:
- GET  /api/guardian/status - Get Guardian running status and health
- POST /api/guardian/start - Start Safety Guardian
- POST /api/guardian/stop - Stop Safety Guardian

Dependencies:
- utils.process_helpers (is_guardian_running)
- Subprocess for start/stop scripts
- Guardian health file reading

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import json
import subprocess
import time
import logging
import sys
from pathlib import Path
from flask import Blueprint, jsonify

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.process_helpers import is_guardian_running

log = logging.getLogger(__name__)

# Create blueprint
guardian_bp = Blueprint('guardian', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent

# ============================================================================
# Route Handlers
# ============================================================================

@guardian_bp.route('/api/guardian/status', methods=['GET'])
def guardian_status():
    """
    Get Safety Guardian running status and health information
    
    Returns:
        JSON response with Guardian status and health data
    
    Example:
        GET /api/guardian/status
        Response: {
            "running": true,
            "active": true,
            "last_check": "2025-11-15T17:16:00",
            "health": {
                "status": "ok",
                "timestamp": 1698765432.0,
                "seconds_since_check": 5,
                "is_healthy": true,
                "monitoring": {...}
            }
        }
    """
    try:
        running = is_guardian_running()
        health = _get_guardian_health() if running else None
        
        # Extract active status and last_check from health
        active = False
        last_check = None
        
        if health:
            active = health.get('is_healthy', False)
            timestamp = health.get('last_check') or health.get('timestamp')
            if timestamp:
                from datetime import datetime
                last_check = datetime.fromtimestamp(timestamp).isoformat()
        
        return jsonify({
            'running': running,
            'active': active,
            'last_check': last_check,
            'health': health
        }), 200
        
    except Exception as e:
        log.error(f"Error getting guardian status: {e}")
        return jsonify({
            'running': False,
            'health': None,
            'error': str(e)
        }), 500


@guardian_bp.route('/api/guardian/start', methods=['POST'])
def guardian_start():
    """
    Start Safety Guardian
    
    Launches the Safety Guardian monitoring process that enforces risk limits
    and protects your account from excessive losses.
    
    Effects:
    - Monitors account balance and P&L continuously
    - Enforces MAX_ACCOUNT_LOSS_INR limit
    - Auto-stops trading bot if loss threshold breached
    - Tracks position sizes and margin usage
    - Sends alerts via Telegram if configured
    - Writes guardian.pid file
    
    Risks:
    - Guardian requires bot to be running to be effective
    - Check GUARDIAN_ENABLED=true in config
    - Verify MAX_ACCOUNT_LOSS_INR is set appropriately
    
    Related Config:
    GUARDIAN_ENABLED, MAX_ACCOUNT_LOSS_INR, GUARDIAN_CHECK_INTERVAL,
    GUARDIAN_HYSTERESIS_*, TELEGRAM_ENABLED
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/guardian/start
        Response: {
            "success": true,
            "message": "Guardian started successfully"
        }
    """
    try:
        result = _start_guardian()
        return jsonify(result), 200 if result.get('success') else 500
        
    except Exception as e:
        log.error(f"Error starting guardian: {e}")
        return jsonify({
            'success': False,
            'message': f'Error starting Guardian: {str(e)}'
        }), 500


@guardian_bp.route('/api/guardian/stop', methods=['POST'])
def guardian_stop_route():
    """
    Stop Safety Guardian
    
    Stops the Safety Guardian monitoring process.
    WARNING: Stopping Guardian removes automatic protection against excessive losses.
    
    Effects:
    - Terminates guardian process
    - Removes guardian.pid file
    - Disables automatic loss limit enforcement
    
    Risks:
    - Bot will continue running without loss protection
    - You will not receive Guardian alerts
    - Consider stopping bot if Guardian is not running
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/guardian/stop
        Response: {
            "success": true,
            "message": "Guardian stopped successfully"
        }
    """
    try:
        result = _stop_guardian()
        return jsonify(result), 200 if result.get('success') else 500
        
    except Exception as e:
        log.error(f"Error stopping guardian: {e}")
        return jsonify({
            'success': False,
            'message': f'Error stopping Guardian: {str(e)}'
        }), 500


# ============================================================================
# Helper Functions
# ============================================================================

def _get_guardian_health():
    """
    Get Guardian health information from health file
    
    Returns:
        Dict with health information or None if not available
    """
    try:
        # Accept either legacy or JSON health files
        health_file = BASE_DIR / '.guardian_health'
        health_file_json = BASE_DIR / '.guardian_health.json'
        
        if not health_file.exists():
            if not health_file_json.exists():
                return None
            with open(health_file_json, 'r') as f:
                health = json.load(f)
        else:
            with open(health_file, 'r') as f:
                health = json.load(f)
        
        # Add time since last check
        current_time = time.time()
        timestamp = health.get('timestamp', 0)
        health['seconds_since_check'] = int(current_time - timestamp)
        health['is_healthy'] = health['seconds_since_check'] < 30  # Healthy if checked within 30s
        
        return health
        
    except Exception as e:
        log.error(f"Error reading guardian health: {e}")
        return None


def _start_guardian():
    """Start the Guardian bot via shell script"""
    try:
        guardian_script = BASE_DIR / 'dashboard' / 'start_guardian.sh'
        if not guardian_script.exists():
            return {'success': False, 'message': 'Guardian script not found'}
        
        result = subprocess.run(
            [str(guardian_script)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return {'success': True, 'message': 'Guardian started successfully'}
        else:
            return {'success': False, 'message': f'Guardian failed to start: {result.stderr}'}
            
    except Exception as e:
        return {'success': False, 'message': f'Error starting Guardian: {str(e)}'}


def _stop_guardian():
    """Stop the Guardian bot via shell script"""
    try:
        guardian_script = BASE_DIR / 'dashboard' / 'stop_guardian.sh'
        if not guardian_script.exists():
            return {'success': False, 'message': 'Stop Guardian script not found'}
        
        result = subprocess.run(
            [str(guardian_script)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return {'success': True, 'message': 'Guardian stopped successfully'}
        else:
            return {'success': False, 'message': f'Guardian failed to stop: {result.stderr}'}
            
    except Exception as e:
        return {'success': False, 'message': f'Error stopping Guardian: {str(e)}'}
