"""
Tmux Routes Blueprint

This module handles all API routes related to tmux session management.

Routes:
- GET  /api/tmux/status - Get tmux session status
- POST /api/tmux/start - Start bots in tmux session
- POST /api/tmux/stop - Stop tmux session

Dependencies:
- Tmux installation
- Control daemon (for tmux management)
- Subprocess for tmux commands

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import os
import stat
import logging
from flask import Blueprint, jsonify

log = logging.getLogger(__name__)

# Create blueprint
tmux_bp = Blueprint('tmux', __name__)

# Try to import HTTP helpers (fallback to requests if not available)
try:
    from webui.backend.utils.connection_pool import http_get, http_post
except ImportError:
    import requests
    http_get = requests.get
    http_post = requests.post

# ============================================================================
# Route Handlers
# ============================================================================

@tmux_bp.route('/api/tmux/status', methods=['GET'])
def tmux_status():
    """
    Get tmux session status
    
    Queries control daemon for accurate session status including bot PIDs.
    Falls back to direct tmux query if daemon not available.
    
    Returns:
        JSON response with tmux installation and session status
    
    Example:
        GET /api/tmux/status
        Response: {
            "tmux_installed": true,
            "session": {
                "exists": true,
                "session_name": "gridbot",
                "socket": "/path/to/socket",
                "bot_count": 3,
                "bot_pids": [1234, 1235, 1236]
            }
        }
    """
    try:
        installed = _is_tmux_installed()
        
        if not installed:
            return jsonify({
                'tmux_installed': False,
                'session': {'exists': False}
            }), 200
        
        # Query control daemon for accurate session status
        try:
            control_token = os.environ.get("GRIDBOT_CONTROL_TOKEN", "gridbot-secure-token-2025")
            response = http_get(
                "http://127.0.0.1:5556/api/tmux/status",
                headers={"X-Auth-Token": control_token},
                timeout=2
            )
            
            if response.status_code == 200:
                daemon_status = response.json()
                return jsonify({
                    'tmux_installed': True,
                    'session': {
                        'exists': daemon_status.get('session_running', False),
                        'session_name': daemon_status.get('session_name', 'gridbot'),
                        'socket': daemon_status.get('socket_path', ''),
                        'bot_count': daemon_status.get('bot_count', 0),
                        'bot_pids': daemon_status.get('bot_pids', [])
                    }
                }), 200
        except Exception as e:
            log.debug(f"Control daemon not available, using fallback: {e}")
        
        # Fallback to direct tmux query
        session_status = _get_tmux_session_status()
        return jsonify({
            'tmux_installed': installed,
            'session': session_status
        }), 200
        
    except Exception as e:
        log.error(f"Error getting tmux status: {e}")
        return jsonify({
            'tmux_installed': False,
            'session': {'exists': False, 'error': str(e)}
        }), 500


@tmux_bp.route('/api/tmux/start', methods=['POST'])
def tmux_start():
    """
    Start all bots in tmux session
    
    Starts bots via control daemon which manages tmux sessions.
    
    Returns:
        JSON response with success status and bot PIDs
    
    Example:
        POST /api/tmux/start
        Response: {
            "success": true,
            "message": "Started successfully",
            "bot_pids": [1234, 1235],
            "bot_count": 2
        }
    """
    try:
        result = _start_bots_with_tmux()
        status_code = 200 if result.get('success') else 500
        return jsonify(result), status_code
        
    except Exception as e:
        log.error(f"Error starting tmux: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@tmux_bp.route('/api/tmux/stop', methods=['POST'])
def tmux_stop():
    """
    Stop tmux session
    
    Stops all bots running in tmux session via control daemon.
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/tmux/stop
        Response: {
            "success": true,
            "message": "Stopped successfully",
            "bots_stopped": 2,
            "pids_killed": [1234, 1235]
        }
    """
    try:
        result = _stop_tmux_session()
        status_code = 200 if result.get('success') else 500
        return jsonify(result), status_code
        
    except Exception as e:
        log.error(f"Error stopping tmux: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ============================================================================
# Helper Functions
# ============================================================================

def _get_tmux_path():
    """Get the path to tmux executable - checks common locations"""
    import shutil
    
    # Check common macOS Homebrew locations first
    tmux_paths = [
        '/opt/homebrew/bin/tmux',  # Apple Silicon Homebrew
        '/usr/local/bin/tmux',     # Intel Homebrew
        '/usr/bin/tmux'            # System tmux
    ]
    
    for tmux_path in tmux_paths:
        if os.path.isfile(tmux_path) and os.access(tmux_path, os.X_OK):
            return tmux_path
    
    # Fallback to which command
    which_result = shutil.which('tmux')
    if which_result:
        return which_result
    
    return None


def _get_tmux_socket_path():
    """Get the custom tmux socket path for daemon mode"""
    home = os.path.expanduser('~')
    socket_path = f"{home}/.tmux-gridbot/default"
    return socket_path


def _is_tmux_installed():
    """Check if tmux is installed"""
    try:
        tmux_path = _get_tmux_path()
        return tmux_path is not None
    except Exception:
        return False


def _get_tmux_session_status():
    """Get status of gridbot tmux session using custom socket"""
    try:
        tmux_path = _get_tmux_path()
        if not tmux_path:
            return {'exists': False, 'error': 'tmux not found'}
        
        socket_path = _get_tmux_socket_path()
        
        # Check if socket file exists and is a socket
        if not os.path.exists(socket_path):
            return {'exists': False}
        
        # Verify it's actually a socket file
        mode = os.stat(socket_path).st_mode
        if not stat.S_ISSOCK(mode):
            return {'exists': False, 'error': 'socket file is not a valid socket'}
        
        # Socket file exists and is valid - session is running
        try:
            # Try to get session details
            list_cmd = f"{tmux_path} -S {socket_path} list-sessions -F '#{{session_name}}:#{{session_windows}}:#{{session_created}}' 2>/dev/null"
            output = os.popen(list_cmd).read().strip()
            
            if output:
                for line in output.split('\n'):
                    if line.startswith('gridbot:'):
                        parts = line.split(':')
                        return {
                            'exists': True,
                            'session_name': 'gridbot',
                            'windows': int(parts[1]) if len(parts) > 1 else 1,
                            'created': parts[2] if len(parts) > 2 else 'unknown',
                            'socket': socket_path
                        }
        except:
            pass
        
        # Socket exists - session is running
        return {
            'exists': True,
            'session_name': 'gridbot',
            'socket': socket_path
        }
            
    except Exception as e:
        return {
            'exists': False,
            'error': str(e)
        }


def _start_bots_with_tmux():
    """Start all bots in tmux session via control daemon"""
    try:
        # Check if tmux is installed
        if not _is_tmux_installed():
            return {
                'success': False,
                'message': 'tmux is not installed. Install with: brew install tmux'
            }
        
        # Call control daemon to start tmux
        control_token = os.environ.get("GRIDBOT_CONTROL_TOKEN", "gridbot-secure-token-2025")
        
        try:
            response = http_post(
                "http://127.0.0.1:5556/api/tmux/start",
                headers={"X-Auth-Token": control_token},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': data.get('success', False),
                    'message': data.get('message', 'Started successfully'),
                    'bot_pids': data.get('bot_pids', []),
                    'bot_count': data.get('bot_count', 0)
                }
            else:
                error_msg = response.json().get('message', 'Unknown error')
                return {
                    'success': False,
                    'message': f'Failed to start: {error_msg}'
                }
                
        except Exception as e:
            if 'ConnectionError' in str(type(e)):
                return {
                    'success': False,
                    'message': 'Control daemon not running. Please check LaunchAgent: com.gridbot.tmuxcontrol'
                }
            return {
                'success': False,
                'message': f'Error communicating with control daemon: {str(e)}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'Error: {str(e)}'
        }


def _stop_tmux_session():
    """Stop the gridbot tmux session via control daemon"""
    try:
        # Call control daemon to stop tmux
        control_token = os.environ.get("GRIDBOT_CONTROL_TOKEN", "gridbot-secure-token-2025")
        
        try:
            response = http_post(
                "http://127.0.0.1:5556/api/tmux/stop",
                headers={"X-Auth-Token": control_token},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': data.get('success', False),
                    'message': data.get('message', 'Stopped successfully'),
                    'bots_stopped': data.get('bots_stopped', 0),
                    'pids_killed': data.get('pids_killed', [])
                }
            else:
                error_msg = response.json().get('message', 'Unknown error')
                return {
                    'success': False,
                    'message': f'Failed to stop: {error_msg}'
                }
                
        except Exception as e:
            if 'ConnectionError' in str(type(e)):
                return {
                    'success': False,
                    'message': 'Control daemon not running. Please check LaunchAgent: com.gridbot.tmuxcontrol'
                }
            return {
                'success': False,
                'message': f'Error communicating with control daemon: {str(e)}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'Error: {str(e)}'
        }
