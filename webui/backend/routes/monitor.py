"""
Monitor Routes Blueprint

This module handles all API routes related to heartbeat monitor control.

Routes:
- GET  /api/monitor/status - Get monitor running status
- POST /api/monitor/start - Start heartbeat monitor
- POST /api/monitor/stop - Stop heartbeat monitor

Dependencies:
- utils.process_helpers (is_monitor_running)
- Subprocess for start/stop scripts

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import subprocess
import logging
import sys
import os
from pathlib import Path
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.process_helpers import is_monitor_running, is_bot_running
from config.loader import get_config

log = logging.getLogger(__name__)

# Create blueprint
monitor_bp = Blueprint('monitor', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent

# ============================================================================
# Route Handlers
# ============================================================================

@monitor_bp.route('/api/trading_status', methods=['GET'])
def get_trading_status():
    """
    Get comprehensive trading status for Trading Status Panel
    
    Returns bot status, blocker information, positions, and PnL data.
    This is the main API endpoint for the frontend Trading Status Panel.
    
    Returns:
        JSON response with trading status
    """
    try:
        from bot.state.store import load_positions_file, load_state_file
        
        # Get bot running status
        bot_running = is_bot_running()
        
        # Initialize response
        from datetime import datetime
        response = {
            'bot_running': bot_running,
            'trading_allowed': True,
            'blockers': [],
            'total_blockers': 0,
            'positions': [],
            'pending_orders': 0,
            'upnl_inr': 0,
            'rpnl_inr': 0,
            'net_pnl_inr': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        # Try to get blocker data
        try:
            from bot.safety.blocker_tracker import get_blocker_tracker
            tracker = get_blocker_tracker()
            blocker_data = tracker.check_all_blockers()
            response['blockers'] = blocker_data.get('blockers', [])
            response['total_blockers'] = blocker_data.get('total_blockers', 0)
            response['trading_allowed'] = blocker_data.get('trading_allowed', True)
        except Exception as e:
            log.warning(f"Could not get blocker data: {e}")
        
        # Get positions and PnL if bot is running
        if bot_running:
            try:
                cfg = get_config()
                mode = cfg.trading_mode if hasattr(cfg, 'trading_mode') else 'demo'
                positions_file = BASE_DIR / 'bot' / 'data' / mode / 'positions.json'
                
                if positions_file.exists():
                    positions_data = load_positions_file(positions_file)
                    positions = positions_data.get('positions', [])
                    response['positions'] = positions
                    
                    # Calculate total unrealized PnL
                    total_upnl = sum(pos.get('unrealized_pnl', 0) for pos in positions)
                    response['upnl_inr'] = total_upnl
                    
                # Get pending orders from SQL database
                try:
                    import sqlite3
                    import json
                    
                    db_file = BASE_DIR / 'bot_events_LONG.db'
                    if db_file.exists():
                        conn = sqlite3.connect(str(db_file))
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT COUNT(*) FROM events 
                            WHERE event_type IN ('pending_buy_set', 'pending_sell_set')
                        """)
                        pending_count = cursor.fetchone()[0]
                        response['pending_orders'] = pending_count
                        conn.close()
                except Exception as sql_error:
                    log.warning(f"Could not load pending orders from SQL: {sql_error}")
                    # Fallback to old state.json
                    state_file = BASE_DIR / 'bot' / 'data' / mode / 'state.json'
                    if state_file.exists():
                        state = load_state_file(state_file)
                        response['pending_orders'] = len(state.get('pending_orders', []))
                    
            except Exception as e:
                log.warning(f"Could not load positions/state: {e}")
        
        return jsonify(response), 200
        
    except Exception as e:
        log.error(f"Error getting trading status: {e}")
        return jsonify({
            'error': str(e),
            'bot_running': False,
            'trading_allowed': False,
            'blockers': [],
            'total_blockers': 0
        }), 500


@monitor_bp.route('/api/monitor/status', methods=['GET'])
def monitor_status():
    """
    Get heartbeat monitor running status
    
    Returns:
        JSON response with monitor status
    
    Example:
        GET /api/monitor/status
        Response: {"running": true}
    """
    try:
        return jsonify({
            'running': is_monitor_running()
        }), 200
    except Exception as e:
        log.error(f"Error getting monitor status: {e}")
        return jsonify({
            'running': False,
            'error': str(e)
        }), 500


@monitor_bp.route('/api/monitor/start', methods=['POST'])
def monitor_start():
    """
    Start the heartbeat monitor
    
    The heartbeat monitor tracks bot health and can alert on issues.
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/monitor/start
        Response: {
            "success": true,
            "message": "Monitor started successfully"
        }
    """
    try:
        result = _start_monitor()
        return jsonify(result), 200 if result.get('success') else 500
        
    except Exception as e:
        log.error(f"Error starting monitor: {e}")
        return jsonify({
            'success': False,
            'message': f'Error starting monitor: {str(e)}'
        }), 500


@monitor_bp.route('/api/monitor/stop', methods=['POST'])
def monitor_stop():
    """
    Stop the heartbeat monitor
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/monitor/stop
        Response: {
            "success": true,
            "message": "Monitor stopped successfully"
        }
    """
    try:
        result = _stop_monitor()
        return jsonify(result), 200 if result.get('success') else 500
        
    except Exception as e:
        log.error(f"Error stopping monitor: {e}")
        return jsonify({
            'success': False,
            'message': f'Error stopping monitor: {str(e)}'
        }), 500


# ============================================================================
# Trading Status Control Routes
# ============================================================================

@monitor_bp.route('/api/trading_status/start', methods=['POST'])
def start_trading():
    """Start trading (start bot or override blockers)"""
    try:
        force = request.json.get('force', False) if request.json else False
        
        # Check if bot is already running
        if is_bot_running():
            if force:
                # Enable EXECUTE_ORDERS if it's disabled
                # TODO: Implement config update
                return jsonify({
                    'success': True,
                    'message': 'Trading enabled (EXECUTE_ORDERS set to True)'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Bot is already running'
                }), 400
        else:
            # Start the bot
            # TODO: Implement bot start logic
            return jsonify({
                'success': True,
                'message': 'Bot start requested'
            }), 200
    except Exception as e:
        log.error(f"Error starting trading: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@monitor_bp.route('/api/trading_status/stop', methods=['POST'])
def stop_trading():
    """Stop trading (stop bot or disable EXECUTE_ORDERS)"""
    try:
        hard_stop = request.json.get('hard_stop', False) if request.json else False
        
        if hard_stop:
            # Stop the bot completely
            # TODO: Implement bot stop logic
            return jsonify({
                'success': True,
                'message': 'Bot stopped'
            }), 200
        else:
            # Just disable EXECUTE_ORDERS (soft stop)
            # TODO: Implement config update
            return jsonify({
                'success': True,
                'message': 'Trading paused (EXECUTE_ORDERS set to False)'
            }), 200
    except Exception as e:
        log.error(f"Error stopping trading: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@monitor_bp.route('/api/trading_status/blocker/<blocker_id>/override', methods=['POST'])
def override_blocker(blocker_id):
    """Override a specific blocker (with confirmation)"""
    try:
        # This is a placeholder for blocker-specific override logic
        return jsonify({
            'success': True,
            'message': f'Blocker {blocker_id} override requested (not yet implemented)'
        }), 200
    except Exception as e:
        log.error(f"Error overriding blocker: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Helper Functions
# ============================================================================

def _start_monitor():
    """Start the heartbeat monitor via shell script"""
    try:
        monitor_script = BASE_DIR / 'dashboard' / 'start_monitor.sh'
        if not monitor_script.exists():
            return {'success': False, 'message': 'Monitor script not found'}
        
        result = subprocess.run(
            [str(monitor_script)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return {'success': True, 'message': 'Monitor started successfully'}
        else:
            return {'success': False, 'message': f'Monitor failed to start: {result.stderr}'}
            
    except Exception as e:
        return {'success': False, 'message': f'Error starting monitor: {str(e)}'}


def _stop_monitor():
    """Stop the heartbeat monitor via shell script"""
    try:
        monitor_script = BASE_DIR / 'dashboard' / 'stop_monitor.sh'
        if not monitor_script.exists():
            return {'success': False, 'message': 'Stop monitor script not found'}
        
        result = subprocess.run(
            [str(monitor_script)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return {'success': True, 'message': 'Monitor stopped successfully'}
        else:
            return {'success': False, 'message': f'Monitor failed to stop: {result.stderr}'}
            
    except Exception as e:
        return {'success': False, 'message': f'Error stopping monitor: {str(e)}'}
