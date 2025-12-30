"""
Guardian Routes Blueprint

This module handles all API routes related to Safety Guardian control.

Routes:
- GET  /api/guardian/status - Get Guardian running status and health
- POST /api/guardian/start - Start Safety Guardian
- POST /api/guardian/stop - Stop Safety Guardian
- POST /api/guardian/restart - Restart Safety Guardian (✅ NEW)

Dependencies:
- utils.process_helpers (is_guardian_running)
- Subprocess for start/stop scripts
- Guardian health file reading

Refactored from app.py (8,850 lines)
Date: 2025-10-31
Updated: 2025-12-30 (Added restart endpoint)
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


@guardian_bp.route('/api/guardian/restart', methods=['POST'])
def guardian_restart():
    """
    Restart Safety Guardian
    
    Stops and restarts the Safety Guardian monitoring process.
    This is useful for applying configuration changes or recovering from errors.
    
    Effects:
    - Stops Guardian if running
    - Waits 2 seconds for clean shutdown
    - Starts Guardian with fresh configuration
    - Reloads all monitoring thresholds
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/guardian/restart
        Response: {
            "success": true,
            "message": "Guardian restarted successfully"
        }
    """
    try:
        # Stop Guardian if running
        if is_guardian_running():
            log.info("Stopping Guardian for restart...")
            stop_result = _stop_guardian()
            
            if not stop_result.get('success'):
                return jsonify({
                    'success': False,
                    'message': f"Failed to stop Guardian: {stop_result.get('message')}"
                }), 500
            
            # Wait for clean shutdown
            time.sleep(2)
        
        # Start Guardian
        log.info("Starting Guardian after restart...")
        start_result = _start_guardian()
        
        if start_result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Guardian restarted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': f"Failed to start Guardian: {start_result.get('message')}"
            }), 500
        
    except Exception as e:
        log.error(f"Error restarting Guardian: {e}")
        return jsonify({
            'success': False,
            'message': f'Error restarting Guardian: {str(e)}'
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
    """Start the Guardian bot via LaunchAgent"""
    try:
        # Use launchctl to start Guardian (managed by LaunchAgent)
        result = subprocess.run(
            ['launchctl', 'start', 'com.gridbot.webui.guardian'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # Wait a moment for Guardian to start
            time.sleep(1)
            return {'success': True, 'message': 'Guardian started successfully'}
        else:
            # LaunchAgent might not be loaded, try loading it first
            load_result = subprocess.run(
                ['launchctl', 'load', str(Path.home() / 'Library/LaunchAgents/com.gridbot.webui.guardian.plist')],
                capture_output=True,
                text=True
            )
            if load_result.returncode == 0:
                return {'success': True, 'message': 'Guardian started successfully'}
            else:
                return {'success': False, 'message': f'Failed to start Guardian: {result.stderr}'}
            
    except subprocess.TimeoutExpired:
        return {'success': False, 'message': 'Guardian start timeout'}
    except Exception as e:
        return {'success': False, 'message': f'Error starting Guardian: {str(e)}'}


def _stop_guardian():
    """Stop the Guardian bot via LaunchAgent"""
    try:
        # Use launchctl to stop Guardian
        result = subprocess.run(
            ['launchctl', 'stop', 'com.gridbot.webui.guardian'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return {'success': True, 'message': 'Guardian stopped successfully'}
        else:
            # Try to kill the process directly if launchctl fails
            try:
                kill_result = subprocess.run(
                    ['pkill', '-f', 'guardian_bot.py'],
                    capture_output=True,
                    text=True
                )
                return {'success': True, 'message': 'Guardian stopped successfully'}
            except Exception:
                return {'success': False, 'message': f'Failed to stop Guardian: {result.stderr}'}
            
    except subprocess.TimeoutExpired:
        return {'success': False, 'message': 'Guardian stop timeout'}
    except Exception as e:
        return {'success': False, 'message': f'Error stopping Guardian: {str(e)}'}


@guardian_bp.route('/api/guardian/rsi/status', methods=['GET'])
def rsi_status():
    """
    Get RSI status directly from RSI collector
    
    Returns:
        JSON response with current RSI value and status
    """
    try:
        log.info("RSI status endpoint called")
        from config.loader import get_config
        import ccxt
        from bot.guardian.collectors.rsi_collector import RSICollector
        
        # Get config and create exchange instance
        log.info("Loading config...")
        config = get_config(reload=True)  # HOT RELOAD: Always get fresh config for RSI thresholds
        log.info("Config loaded, creating exchange...")
        exchange = ccxt.delta({'enableRateLimit': True})
        log.info("Exchange created, initializing RSI collector...")
        
        # Create RSI collector instance
        rsi_collector = RSICollector(exchange, config)
        log.info("RSI collector initialized")
        
        # Get current RSI value
        log.info("Fetching RSI from collector...")
        current_rsi = rsi_collector.get_latest_rsi()
        log.info(f"RSI fetched: {current_rsi} (type: {type(current_rsi)})")
        should_stop = rsi_collector.should_stop_trading()
        log.info(f"Should stop: {should_stop}")
        
        # Get configuration values - NO HARDCODED DEFAULTS
        if not (config.safety and hasattr(config.safety, 'rsi')):
            raise ValueError("RSI configuration missing in config.yaml under safety.rsi")
        
        rsi_config = config.safety.rsi
        long_threshold = rsi_config.long_threshold
        short_threshold = rsi_config.short_threshold
        hysteresis_seconds = rsi_config.hysteresis_seconds
        
        # Get bot mode
        bot_mode = config.bot.mode if config.bot and hasattr(config.bot, 'mode') else 'LONG'
        
        # Determine status
        if current_rsi is None:
            status = 'UNAVAILABLE'
            status_text = 'No RSI data available yet'
        elif should_stop:
            if bot_mode == 'LONG':
                status = 'STOP'
                status_text = f'Oversold (RSI <= {long_threshold})'
            else:
                status = 'STOP'
                status_text = f'Overbought (RSI >= {short_threshold})'
        else:
            status = 'GO'
            status_text = 'Trading allowed'
        
        # Check hysteresis (simplified - we'd need access to internal state for exact timing)
        hysteresis_active = False
        if current_rsi is not None:
            if bot_mode == 'LONG' and current_rsi == long_threshold:
                hysteresis_active = True
            elif bot_mode == 'SHORT' and current_rsi == short_threshold:
                hysteresis_active = True
        
        return jsonify({
            'success': True,
            'data': {
                'rsi': current_rsi,
                'status': status,
                'status_text': status_text,
                'bot_mode': bot_mode,
                'long_threshold': long_threshold,
                'short_threshold': short_threshold,
                'hysteresis_active': hysteresis_active,
                'hysteresis_seconds': hysteresis_seconds,
                'should_stop': should_stop,
                'timestamp': time.time()
            }
        })
        
    except Exception as e:
        log.error(f"Error fetching RSI status: {e}", exc_info=True)
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500
