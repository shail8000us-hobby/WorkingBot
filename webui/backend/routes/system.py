"""
System Routes Blueprint

This module handles all API routes related to system status and configuration.

Routes:
- GET  /api/system/status - Overall system health status
- GET  /api/trading-mode - Get current trading mode (demo/live)
- POST /api/trading-mode - Switch trading mode

Dependencies:
- utils.process_helpers (bot status checks)
- bot.utils.env_loader (mode management)
- File writing utilities

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import os
import logging
import sys
from pathlib import Path
from datetime import datetime
import time
from flask import Blueprint, jsonify, request, current_app

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.process_helpers import is_bot_running, is_guardian_running, is_monitor_running
from config.loader import get_config

def get_config_value(yaml_path: str, env_var: str = None, default: any = None):
    """Get config value from YAML using dot notation"""
    try:
        cfg = get_config()
        value = cfg
        for key in yaml_path.split('.'):
            value = getattr(value, key)
        return value
    except (AttributeError, KeyError):
        return default

log = logging.getLogger(__name__)

# Create blueprint
system_bp = Blueprint('system', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
CONFIG_FILE = BASE_DIR / "config.yaml"

# Import YAML config loader
from config.loader import get_config, reload_config
import yaml

# ============================================================================
# Route Handlers
# ============================================================================

@system_bp.route('/api/flags', methods=['GET'])
def get_flags():
    """
    Get feature flags for frontend
    
    Returns feature flags that control UI functionality including
    error intelligence, reconciliation, telegram, and demo mode.
    
    Returns:
        JSON response with feature flags
    
    Example:
        GET /api/flags
        Response: {
            "success": true,
            "flags": {
                "error_intelligence": true,
                "reconciliation": true,
                "telegram": false,
                "demo_mode": true
            }
        }
    """
    try:
        # Check if error intelligence is available
        error_intelligence_available = False
        try:
            from webui.backend.error_intelligence import error_manager
            error_intelligence_available = error_manager is not None
        except:
            pass
        
        flags = {
            'error_intelligence': error_intelligence_available,
            'reconciliation': True,  # Bulletproof system always available
            'telegram': get_config_value('notifications.telegram.enabled', 'TELEGRAM_ENABLED', True),
            'demo_mode': get_config_value('trading.mode', 'MODE', 'demo') == 'demo'
        }
        
        return jsonify({
            'success': True,
            'flags': flags
        }), 200
        
    except Exception as e:
        log.error(f"Error getting flags: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@system_bp.route('/api/system/status', methods=['GET'])
def get_system_status():
    """
    Get overall system health status
    
    Returns the status of all major system components including bot,
    guardian, monitor, and system uptime.
    
    Returns:
        JSON response with system status
    
    Example:
        GET /api/system/status
        Response: {
            "success": true,
            "bot_running": true,
            "guardian_running": false,
            "monitor_running": true,
            "timestamp": "2025-10-31T17:30:00",
            "uptime_seconds": 3600
        }
    """
    try:
        start_time = current_app.config.get('_start_time', time.time())
        
        return jsonify({
            'success': True,
            'bot_running': is_bot_running(),
            'guardian_running': is_guardian_running(),
            'monitor_running': is_monitor_running(),
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': int(time.time() - start_time)
        }), 200
        
    except Exception as e:
        log.error(f"Error getting system status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@system_bp.route('/api/trading-mode', methods=['GET'])
def get_trading_mode():
    """
    Get current trading mode (demo/live)
    
    Returns:
        JSON response with current trading mode
    
    Example:
        GET /api/trading-mode
        Response: {
            "mode": "demo",
            "display": {
                "name": "Demo Mode",
                "color": "blue",
                "description": "..."
            }
        }
    """
    try:
        from bot.utils.env_loader import get_current_mode, get_mode_display_info
        
        mode = get_current_mode()
        mode_info = get_mode_display_info()
        
        return jsonify({
            'mode': mode,
            'display': mode_info
        }), 200
        
    except Exception as e:
        log.error(f"Error getting trading mode: {e}")
        return jsonify({'error': str(e)}), 500


@system_bp.route('/api/trading-mode', methods=['POST'])
def set_trading_mode():
    """
    Switch trading mode between demo and live
    
    IMPORTANT: This requires bot restart to take effect!
    The mode is saved to config.yaml and will be used on next bot start.
    
    Request Body:
        {
            "mode": "demo" | "live",
            "confirmed": true  # Required for live mode
        }
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/trading-mode
        Body: {"mode": "demo"}
        Response: {
            "success": true,
            "mode": "demo",
            "message": "Trading mode set to demo. Please restart bot...",
            "restart_required": true
        }
    """
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        new_mode = data.get('mode', '').lower().strip()
        
        # Validate mode
        if new_mode not in ['demo', 'live']:
            return jsonify({
                'error': 'Invalid mode. Must be "demo" or "live"'
            }), 400
        
        # Safety confirmation for live mode
        if new_mode == 'live':
            confirmed = data.get('confirmed', False)
            if not confirmed:
                return jsonify({
                    'error': 'Switching to LIVE mode requires confirmation',
                    'require_confirmation': True,
                    'warning': (
                        'You are about to switch to LIVE TRADING mode. '
                        'This will use REAL MONEY. '
                        'Please ensure:\n'
                        '1. You have tested thoroughly on demo\n'
                        '2. All safety limits are configured correctly\n'
                        '3. You understand the risks involved\n\n'
                        'Send the request again with "confirmed": true to proceed.'
                    )
                }), 403
        
        # Update config.yaml
        if not CONFIG_FILE.exists():
            return jsonify({'error': 'config.yaml not found'}), 500
        
        with open(CONFIG_FILE, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Update trading mode
        if 'trading_mode' not in config_data:
            config_data['trading_mode'] = {}
        
        config_data['trading_mode']['value'] = new_mode
        
        # Write back to YAML
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        
        # Reload config
        reload_config()
        
        # Log the change
        log.warning(f"TRADING MODE CHANGED: {new_mode.upper()}")
        log.warning("Bot restart required for change to take effect!")
        print(f"⚠️  TRADING MODE CHANGED: {new_mode.upper()}")
        print(f"⚠️  Bot restart required for change to take effect!")
        
        return jsonify({
            'success': True,
            'mode': new_mode,
            'message': f'Trading mode set to {new_mode}. Please restart bot for changes to take effect.',
            'restart_required': True
        }), 200
    
    except Exception as e:
        log.error(f"Failed to set trading mode: {e}")
        return jsonify({
            'error': 'Failed to set trading mode',
            'details': str(e)
        }), 500


# ============================================================================
# Version and Reports Routes
# ============================================================================

@system_bp.route('/api/version', methods=['GET'])
def get_version():
    """Get backend version and build info for cache validation"""
    try:
        import psutil
        import time
        import json
        import re
        
        # Get backend start time
        current_process = psutil.Process(os.getpid()) if psutil else None
        started_at = current_process.create_time() if current_process else time.time()
        
        # Try to get UI build hash from build manifest
        ui_build_hash = 'unknown'
        try:
            # Look for frontend build manifest
            frontend_build = BASE_DIR / 'webui' / 'frontend' / 'build'
            build_manifest = frontend_build / 'asset-manifest.json'
            if build_manifest.exists():
                with open(build_manifest, 'r') as f:
                    manifest = json.load(f)
                    # Use main.js hash as build identifier
                    main_js = manifest.get('files', {}).get('main.js', '')
                    if main_js:
                        # Extract hash from filename like /static/js/main.abc123.js
                        match = re.search(r'main\.([a-f0-9]+)\.js', main_js)
                        if match:
                            ui_build_hash = match.group(1)[:8]  # First 8 chars
        except Exception as e:
            log.debug(f"Could not read build manifest: {e}")
        
        response = jsonify({
            'backend_version': '1.0.0',
            'ui_build_hash': ui_build_hash,
            'started_at': started_at,
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'pid': os.getpid()
        })
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    except Exception as e:
        log.error(f"Error getting version: {e}")
        return jsonify({
            'error': str(e),
            'backend_version': '1.0.0',
            'ui_build_hash': 'unknown',
            'started_at': time.time()
        }), 500


@system_bp.route('/api/shutdown-report', methods=['GET'])
def get_shutdown_report():
    """Get the latest graceful shutdown report"""
    try:
        import json
        shutdown_file = BASE_DIR / 'shutdown_report.json'
        
        if not shutdown_file.exists():
            return jsonify({
                'exists': False,
                'message': 'No shutdown report available yet. Stop the bot to generate one.'
            }), 200
        
        with open(shutdown_file, 'r') as f:
            shutdown_data = json.load(f)
        
        # Convert numpy types if any
        try:
            from webui.backend.utils.response_helpers import convert_numpy_types
            shutdown_data = convert_numpy_types(shutdown_data)
        except ImportError:
            pass
        
        return jsonify({
            'exists': True,
            'data': shutdown_data
        }), 200
        
    except Exception as e:
        log.error(f"Error reading shutdown report: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@system_bp.route('/api/sync-report', methods=['GET'])
def get_sync_report():
    """Get the latest sync & reconciliation report"""
    try:
        import json
        sync_file = BASE_DIR / 'sync_report.json'
        
        if not sync_file.exists():
            return jsonify({
                'exists': False,
                'message': 'No sync report available yet. Start the bot to generate one.'
            }), 200
        
        with open(sync_file, 'r') as f:
            sync_data = json.load(f)
        
        # Convert numpy types if any
        try:
            from webui.backend.utils.response_helpers import convert_numpy_types
            sync_data = convert_numpy_types(sync_data)
        except ImportError:
            pass
        
        return jsonify({
            'exists': True,
            'data': sync_data
        }), 200
        
    except Exception as e:
        log.error(f"Error reading sync report: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@system_bp.route('/api/process/supervise', methods=['POST'])
def supervise_processes():
    """Ensure trading bot and guardian bot are running. Start if not."""
    try:
        import subprocess
        workspace = str(BASE_DIR)
        started = []

        # Check trading bot using unified detection
        from webui.backend.utils.process_helpers import is_bot_running
        bot_running = is_bot_running()

        if not bot_running:
            # Use UNIFIED LAUNCHER
            subprocess.run(['python3', 'bot_launcher.py', '--daemon'], cwd=workspace)
            started.append('trading_bot')

        # Check guardian bot
        guardian_running = False
        try:
            out = subprocess.check_output(
                ['bash', '-lc', "ps aux | grep -E 'python(3)? +-m +bot\\.guardian\\.core\\.guardian_bot' | grep -v grep || true"]
            ).decode().strip()
            guardian_running = len(out) > 0
        except Exception:
            guardian_running = False

        if not guardian_running:
            subprocess.Popen(['python3', '-m', 'bot.guardian.core.guardian_bot'], cwd=workspace)
            started.append('guardian_bot')

        return jsonify({'success': True, 'started': started}), 200
    except Exception as e:
        log.error(f"Error supervising processes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Helper Functions
# ============================================================================

def _atomic_write_text(filepath: Path, content: str):
    """
    Write text to file atomically
    
    Args:
        filepath: Path to file
        content: Text content to write
    """
    import tempfile
    import shutil
    
    # Write to temporary file first
    temp_file = filepath.with_suffix(filepath.suffix + '.tmp')
    try:
        with open(temp_file, 'w') as f:
            f.write(content)
        # Atomic move
        shutil.move(str(temp_file), str(filepath))
    except Exception:
        # Clean up temp file if it exists
        if temp_file.exists():
            temp_file.unlink()
        raise
