"""
Emergency API Blueprint

This module handles all API routes related to emergency controls and overrides.

Routes:
- GET  /api/emergency/overrides - Get emergency override states
- POST /api/emergency/overrides/<feature> - Set emergency override for a feature
- POST /api/emergency/overrides/reset - Reset all emergency overrides
- GET  /api/emergency/check_flag - Check if emergency stop flag exists
- POST /api/emergency/clear_flag - Clear emergency stop flag
- POST /api/emergency/reset_gatekeeper - Reset safety gatekeeper
- POST /api/emergency/force_restart - Force restart bot
- POST /api/emergency/kill-all - Emergency kill all bot processes

Dependencies:
- bot.safety.gatekeeper (gatekeeper management)
- bot.emergency_kill (emergency kill system)
"""

import os
import json
import time
import logging
import subprocess
import signal
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

# Create blueprint
emergency_bp = Blueprint('emergency', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
EMERGENCY_OVERRIDES_FILE = BASE_DIR / '.emergency_overrides.json'

# ============================================================================
# Helper Functions
# ============================================================================

def load_emergency_overrides():
    """Load emergency override states from file"""
    try:
        if EMERGENCY_OVERRIDES_FILE.exists():
            with open(EMERGENCY_OVERRIDES_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        log.error(f"Error loading emergency overrides: {e}")
    
    # Default state: all features enabled
    return {
        'monitoring': {'enabled': True, 'last_changed': None, 'changed_by': 'system'},
        'liquidity_monitor': {'enabled': True, 'last_changed': None, 'changed_by': 'system'},
        'capital_protection': {'enabled': True, 'last_changed': None, 'changed_by': 'system'},
        'risk_management': {'enabled': True, 'last_changed': None, 'changed_by': 'system'}
    }


def save_emergency_overrides(overrides):
    """Save emergency override states to file"""
    try:
        with open(EMERGENCY_OVERRIDES_FILE, 'w') as f:
            json.dump(overrides, f, indent=2)
        return True
    except Exception as e:
        log.error(f"Error saving emergency overrides: {e}")
        return False


# ============================================================================
# Emergency Override Routes
# ============================================================================

@emergency_bp.route('/api/emergency/overrides', methods=['GET'])
def get_emergency_overrides():
    """
    Get Emergency Override States
    
    Returns the current on/off state of all safety features that can be
    overridden in emergency situations.
    
    Returns:
        JSON response with override states
    """
    try:
        overrides = load_emergency_overrides()
        return jsonify({
            'success': True,
            'overrides': overrides
        }), 200
    except Exception as e:
        log.error(f"Error getting emergency overrides: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@emergency_bp.route('/api/emergency/overrides/<feature>', methods=['POST'])
def set_emergency_override(feature):
    """
    Set Emergency Override for a Feature
    
    Allows enabling/disabling critical safety features in emergency situations.
    
    WARNING: Disabling safety features increases risk. Use only when necessary.
    
    Args:
        feature: One of: monitoring, liquidity_monitor, capital_protection, risk_management
        Body: {"enabled": true/false, "reason": "optional reason"}
    """
    try:
        valid_features = ['monitoring', 'liquidity_monitor', 'capital_protection', 'risk_management']
        
        if feature not in valid_features:
            return jsonify({
                'success': False,
                'error': f'Invalid feature. Must be one of: {", ".join(valid_features)}'
            }), 400
        
        data = request.get_json()
        if not data or 'enabled' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: enabled'
            }), 400
        
        enabled = bool(data['enabled'])
        reason = data.get('reason', 'No reason provided')
        
        # Load current overrides
        overrides = load_emergency_overrides()
        
        # Update the specific feature
        overrides[feature] = {
            'enabled': enabled,
            'last_changed': datetime.now().isoformat(),
            'changed_by': 'webui_user',
            'reason': reason
        }
        
        # Save to file
        if save_emergency_overrides(overrides):
            # Log the action
            action = 'ENABLED' if enabled else 'DISABLED'
            log_msg = f"🚨 EMERGENCY OVERRIDE: {feature} {action} | Reason: {reason}"
            log.warning(log_msg)
            
            # Also write to a dedicated override log
            try:
                override_log = BASE_DIR / 'emergency_overrides.log'
                with open(override_log, 'a') as f:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"[{timestamp}] {log_msg}\n")
            except Exception as log_err:
                log.error(f"Error writing to override log: {log_err}")
            
            return jsonify({
                'success': True,
                'message': f'Feature "{feature}" has been {action.lower()}',
                'overrides': overrides
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save override state'
            }), 500
            
    except Exception as e:
        log.error(f"Error setting emergency override: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@emergency_bp.route('/api/emergency/overrides/reset', methods=['POST'])
def reset_emergency_overrides():
    """
    Reset All Emergency Overrides
    
    Re-enables all safety features that were disabled via emergency override.
    """
    try:
        overrides = {
            'monitoring': {'enabled': True, 'last_changed': datetime.now().isoformat(), 'changed_by': 'system_reset'},
            'liquidity_monitor': {'enabled': True, 'last_changed': datetime.now().isoformat(), 'changed_by': 'system_reset'},
            'capital_protection': {'enabled': True, 'last_changed': datetime.now().isoformat(), 'changed_by': 'system_reset'},
            'risk_management': {'enabled': True, 'last_changed': datetime.now().isoformat(), 'changed_by': 'system_reset'}
        }
        
        if save_emergency_overrides(overrides):
            log.info("✅ All emergency overrides have been reset - all features re-enabled")
            return jsonify({
                'success': True,
                'message': 'All emergency overrides reset - all features re-enabled',
                'overrides': overrides
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save reset state'
            }), 500
            
    except Exception as e:
        log.error(f"Error resetting emergency overrides: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Emergency Flag Routes
# ============================================================================

@emergency_bp.route('/api/emergency/check_flag', methods=['GET'])
def check_emergency_flag():
    """Check if emergency stop flag exists"""
    try:
        emergency_flag = BASE_DIR / '.guardian_emergency_stop'
        
        return jsonify({
            'success': True,
            'flag_exists': emergency_flag.exists(),
            'flag_location': str(emergency_flag.absolute()) if emergency_flag.exists() else None
        }), 200
            
    except Exception as e:
        log.error(f"Error checking emergency flag: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to check emergency flag'
        }), 500


@emergency_bp.route('/api/emergency/clear_flag', methods=['POST'])
def clear_emergency_flag():
    """
    Clear Emergency Flag
    
    Clears the emergency flag, allowing the bot to resume normal operations.
    """
    try:
        emergency_flag = BASE_DIR / '.guardian_emergency_stop'
        
        if emergency_flag.exists():
            emergency_flag.unlink()
            return jsonify({
                'success': True,
                'message': 'Emergency stop flag cleared successfully',
                'action': 'clear_emergency_flag'
            }), 200
        else:
            return jsonify({
                'success': True,
                'message': 'No emergency flag found - already clear',
                'action': 'clear_emergency_flag'
            }), 200
            
    except Exception as e:
        log.error(f"Error clearing emergency flag: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to clear emergency flag'
        }), 500


@emergency_bp.route('/api/emergency/reset_gatekeeper', methods=['POST'])
def reset_gatekeeper():
    """
    Reset Gatekeeper
    
    Resets the Gatekeeper safety mechanism that blocks trading after errors or violations.
    """
    try:
        # Import and reset gatekeeper
        from bot.safety.gatekeeper import _gatekeeper
        
        # Reset gatekeeper stats
        _gatekeeper.reset_stats()
        
        return jsonify({
            'success': True,
            'message': 'Safety Gatekeeper reset successfully',
            'action': 'reset_gatekeeper'
        }), 200
        
    except Exception as e:
        log.error(f"Error resetting gatekeeper: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to reset Safety Gatekeeper'
        }), 500


# ============================================================================
# Emergency Control Routes
# ============================================================================

@emergency_bp.route('/api/emergency/force_restart', methods=['POST'])
def force_restart():
    """
    Force Restart Bot
    
    Forcefully restarts the trading bot by killing existing process and starting a new one.
    """
    try:
        # Get current bot PID
        bot_pid = None
        bot_pid_file = BASE_DIR / 'bot.pid'
        try:
            if bot_pid_file.exists():
                with open(bot_pid_file, 'r') as f:
                    bot_pid = int(f.read().strip())
        except Exception as e:
            log.warning(f"Could not read bot PID: {e}")
        
        # Kill existing bot process
        if bot_pid:
            try:
                log.info(f"Sending SIGTERM to bot (PID {bot_pid})...")
                os.kill(bot_pid, signal.SIGTERM)
                
                # Wait up to 30 seconds for graceful shutdown
                log.info("Waiting for graceful shutdown (max 30s)...")
                for i in range(60):  # 30 seconds
                    try:
                        os.kill(bot_pid, 0)  # Check if still alive
                        time.sleep(0.5)
                    except ProcessLookupError:
                        log.info(f"Bot stopped gracefully after {i * 0.5:.1f}s")
                        break
                else:
                    # Force kill if still running after 30s
                    log.warning("Bot did not stop gracefully, sending SIGKILL...")
                    try:
                        os.kill(bot_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            except ProcessLookupError:
                log.info("Bot process already stopped")
            except Exception as e:
                log.error(f"Error stopping bot: {e}")
        
        # Start new bot process using UNIFIED LAUNCHER
        subprocess.run([
            'python3', 'bot_launcher.py', '--daemon'
        ], cwd=str(BASE_DIR))
        
        return jsonify({
            'success': True,
            'message': 'Bot restart initiated successfully',
            'action': 'force_restart'
        }), 200
        
    except Exception as e:
        log.error(f"Error force restarting bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to restart bot'
        }), 500


@emergency_bp.route('/api/emergency/kill-all', methods=['POST'])
def api_emergency_kill_all():
    """
    Emergency Kill All Bots - BULLETPROOF VERSION
    
    Uses the centralized EmergencyKillSystem for maximum reliability.
    This is a hard kill that bypasses graceful shutdown.
    
    WARNING: This is a destructive action that will immediately stop all trading!
    Use only in genuine emergency situations.
    """
    try:
        log.warning(f"{'='*80}")
        log.warning(f"[EMERGENCY KILL] API endpoint called!")
        log.warning(f"[EMERGENCY KILL] Request from: {request.remote_addr}")
        log.warning(f"{'='*80}")
        
        # Import the centralized emergency kill system
        try:
            from bot.emergency_kill import emergency_kill_all
            log.info("[EMERGENCY KILL] Module imported successfully!")
            log.info("[EMERGENCY KILL] Executing emergency_kill_all()...")
            result = emergency_kill_all()
            
            log.info(f"[EMERGENCY KILL] Result: {result}")
            
            return jsonify({
                'success': True,
                'message': 'Emergency kill executed',
                'result': result
            }), 200
            
        except ImportError as e:
            log.error(f"[EMERGENCY KILL] Failed to import emergency_kill module: {e}")
            return jsonify({
                'success': False,
                'error': f'Emergency kill module not found: {str(e)}'
            }), 500
        
    except Exception as e:
        log.error(f"[EMERGENCY KILL] Error: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
