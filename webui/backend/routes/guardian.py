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
Updated: 2026-01-01 (v6.0 instance support)
"""

import json
import subprocess
import time
import logging
import sys
from pathlib import Path
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.process_helpers import is_guardian_running

log = logging.getLogger(__name__)

# Create blueprint
guardian_bp = Blueprint('guardian', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent


def get_instance_from_request():
    """
    Extract instance from request, supporting both v5.0 and v6.0 formats.
    
    Returns:
        tuple: (instance_name, symbol, mode)
    """
    instance = request.args.get('instance')
    if instance:
        parts = instance.rsplit('_', 1)
        if len(parts) == 2:
            return instance, parts[0], parts[1]
        return instance, instance, 'LONG'
    
    symbol = request.args.get('symbol', 'BTCUSD')
    mode = request.args.get('mode', 'LONG')
    return f"{symbol}_{mode}", symbol, mode


# ============================================================================
# Route Handlers
# ============================================================================

@guardian_bp.route('/api/guardian/status', methods=['GET'])
def guardian_status():
    """
    Get Safety Guardian status - Instance-Aware (v6.0)
    
    Query Parameters:
        instance (optional): Instance name (e.g., "BTCUSD_LONG", "BTCUSD_SHORT")
        symbol (optional): Symbol name for backward compat (e.g., "BTCUSD")
                          If omitted, returns aggregate status for ALL instances
    
    Returns:
        JSON response with Guardian status and health data
    
    Examples:
        GET /api/guardian/status
        Response: {
            "running": true,
            "global": {
                "total_loss_inr": -1500,
                "total_positions": 18,
                "risk_status": "SAFE"
            },
            "instances": {
                "BTCUSD_LONG": {"loss_inr": -800, "positions": 12, "max_loss_inr": 7000},
                "BTCUSD_SHORT": {"loss_inr": -200, "positions": 3, "max_loss_inr": 5000},
                "ETHUSD_LONG": {"loss_inr": -500, "positions": 3, "max_loss_inr": 3500}
            },
            "symbols": {...}  // backward compat
        }
        
        GET /api/guardian/status?instance=BTCUSD_LONG
        Response: {
            "running": true,
            "instance": "BTCUSD_LONG",
            "symbol": "BTCUSD",
            "mode": "LONG",
            "loss_inr": -800,
            "max_loss_inr": 7000,
            "positions": 12,
            "health": {...}
        }
    """
    try:
        from config.loader import get_config
        
        # v6.0: Get instance or fall back to symbol
        instance_name, requested_symbol, requested_mode = get_instance_from_request()
        
        # Check if specific instance was requested (not just default)
        specific_instance_requested = request.args.get('instance') is not None
        specific_symbol_requested = request.args.get('symbol') is not None
        
        if specific_instance_requested:
            requested_symbol = requested_symbol.upper()
        elif specific_symbol_requested:
            requested_symbol = request.args.get('symbol').upper()
        else:
            requested_symbol = None  # Return all
        
        running = is_guardian_running()
        health = _get_guardian_health() if running else None
        config = get_config()
        
        # Extract active status and last_check from health
        active = False
        last_check = None
        
        if health:
            active = health.get('is_healthy', False)
            timestamp = health.get('last_check') or health.get('timestamp')
            if timestamp:
                from datetime import datetime
                try:
                    # Handle both int/float timestamps and string timestamps
                    if isinstance(timestamp, str):
                        timestamp = float(timestamp)
                    last_check = datetime.fromtimestamp(timestamp).isoformat()
                except (ValueError, TypeError) as e:
                    log.warning(f"Invalid timestamp format: {timestamp} ({type(timestamp)}): {e}")
                    last_check = None
        
        # Get per-symbol data
        symbols_data = _get_symbols_guardian_data(config, health)
        
        # Calculate global totals
        total_loss_inr = sum(s.get('loss_inr', 0) for s in symbols_data.values())
        total_positions = sum(s.get('positions', 0) for s in symbols_data.values())
        
        # Determine global risk status
        if not running:
            global_risk = 'GUARDIAN_STOPPED'
        elif hasattr(config, 'capital_allocation') and hasattr(config.capital_allocation, 'total_capital_usd'):
            # Convert USD to INR
            usd_to_inr = 85.0  # Default rate
            if hasattr(config, 'guardian') and hasattr(config.guardian, 'usd_to_inr_rate'):
                usd_to_inr = float(config.guardian.usd_to_inr_rate)
            total_capital_inr = float(config.capital_allocation.total_capital_usd) * usd_to_inr
            if total_loss_inr < -total_capital_inr * 0.10:
                global_risk = 'CRITICAL'
            elif any(s.get('risk_status') == 'DANGER' for s in symbols_data.values()):
                global_risk = 'DANGER'
            elif any(s.get('risk_status') == 'WARNING' for s in symbols_data.values()):
                global_risk = 'WARNING'
            else:
                global_risk = 'SAFE'
        elif any(s.get('risk_status') == 'DANGER' for s in symbols_data.values()):
            global_risk = 'DANGER'
        elif any(s.get('risk_status') == 'WARNING' for s in symbols_data.values()):
            global_risk = 'WARNING'
        else:
            global_risk = 'SAFE'
        
        # If specific symbol requested, return symbol-specific response
        if requested_symbol:
            if requested_symbol in symbols_data:
                symbol_data = symbols_data[requested_symbol]
                return jsonify({
                    'success': True,
                    'running': running,
                    'active': active,
                    'symbol': requested_symbol,
                    **symbol_data,
                    'health': health,
                    'last_check': last_check
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': f'Symbol {requested_symbol} not found',
                    'available': list(symbols_data.keys())
                }), 404
        
        # Return aggregate response for all symbols
        total_capital_inr = 0
        if hasattr(config, 'capital_allocation') and hasattr(config.capital_allocation, 'total_capital_usd'):
            usd_to_inr = 85.0
            if hasattr(config, 'guardian') and hasattr(config.guardian, 'usd_to_inr_rate'):
                usd_to_inr = float(config.guardian.usd_to_inr_rate)
            total_capital_inr = float(config.capital_allocation.total_capital_usd) * usd_to_inr
        
        response = {
            'success': True,
            'running': running,
            'active': active,
            'last_check': last_check,
            'global': {
                'total_loss_inr': total_loss_inr,
                'total_positions': total_positions,
                'risk_status': global_risk,
                'total_capital_inr': total_capital_inr
            },
            'symbols': symbols_data,
            'health': health
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        log.error(f"Error getting guardian status: {e}")
        return jsonify({
            'success': False,
            'running': False,
            'health': None,
            'error': str(e)
        }), 500


def _get_symbols_guardian_data(config, health: dict) -> dict:
    """
    Get guardian data per symbol from monitoring files
    
    Returns:
        Dict mapping symbol name to its guardian data
    """
    import json
    from pathlib import Path
    
    symbols_data = {}
    
    if not config.symbols:
        # v4.0 fallback
        return {'BTCUSD': _get_single_symbol_guardian_data('BTCUSD', config, health)}
    
    for symbol_name, symbol_config in config.symbols.items():
        if not symbol_config.enabled:
            symbols_data[symbol_name] = {
                'enabled': False,
                'loss_inr': 0,
                'positions': 0,
                'max_loss_inr': symbol_config.safety.max_account_loss_inr,
                'risk_status': 'DISABLED'
            }
            continue
        
        # Try to read symbol-specific monitoring file
        monitoring_file = Path(f"data/monitoring_snapshot_{symbol_name}_{symbol_config.mode}.json")
        
        loss_inr = 0
        positions = 0
        unrealized_pnl = 0
        
        try:
            if monitoring_file.exists():
                with open(monitoring_file) as f:
                    data = json.load(f)
                    unrealized_pnl = float(data.get('unrealized_pnl_usd', 0) or 0)
                    # Convert to INR
                    usd_to_inr = float(config.guardian.usd_to_inr_rate) if hasattr(config, 'guardian') and config.guardian.usd_to_inr_rate else 85.0
                    loss_inr = float(unrealized_pnl * usd_to_inr)
                    positions = int(data.get('position_count', 0) or len(data.get('positions', [])))
        except Exception as e:
            log.warning(f"Could not read monitoring file for {symbol_name}: {e}")
        
        # Determine risk status for this symbol
        max_loss = float(symbol_config.safety.max_account_loss_inr) if symbol_config.safety.max_account_loss_inr else 0
        loss_inr = float(loss_inr) if loss_inr else 0
        loss_pct = abs(loss_inr) / max_loss * 100 if max_loss > 0 else 0
        
        if loss_pct >= 100:
            risk_status = 'CRITICAL'
        elif loss_pct >= 80:
            risk_status = 'DANGER'
        elif loss_pct >= 50:
            risk_status = 'WARNING'
        else:
            risk_status = 'SAFE'
        
        symbols_data[symbol_name] = {
            'enabled': True,
            'loss_inr': loss_inr,
            'unrealized_pnl_usd': unrealized_pnl,
            'positions': positions,
            'max_loss_inr': max_loss,
            'loss_pct': round(loss_pct, 1),
            'risk_status': risk_status,
            'mode': symbol_config.mode
        }
    
    return symbols_data


def _get_single_symbol_guardian_data(symbol_name: str, config, health: dict) -> dict:
    """Get guardian data for a single symbol (v4.0 compatibility)"""
    import json
    from pathlib import Path
    
    mode = config.bot.mode if config.bot else 'LONG'
    monitoring_file = Path(f"data/monitoring_snapshot_{symbol_name}_{mode}.json")
    
    loss_inr = 0
    positions = 0
    unrealized_pnl = 0
    
    try:
        if monitoring_file.exists():
            with open(monitoring_file) as f:
                data = json.load(f)
                unrealized_pnl = data.get('unrealized_pnl_usd', 0) or 0
                usd_to_inr = config.guardian.usd_to_inr_rate if hasattr(config, 'guardian') else 85
                loss_inr = unrealized_pnl * usd_to_inr
                positions = data.get('position_count', 0)
    except Exception as e:
        log.warning(f"Could not read monitoring file: {e}")
    
    max_loss = config.guardian.max_account_loss_inr if hasattr(config, 'guardian') else 7000
    loss_pct = abs(loss_inr) / max_loss * 100 if max_loss > 0 else 0
    
    return {
        'enabled': True,
        'loss_inr': loss_inr,
        'unrealized_pnl_usd': unrealized_pnl,
        'positions': positions,
        'max_loss_inr': max_loss,
        'loss_pct': round(loss_pct, 1),
        'risk_status': 'CRITICAL' if loss_pct >= 100 else 'DANGER' if loss_pct >= 80 else 'WARNING' if loss_pct >= 50 else 'SAFE',
        'mode': mode
    }


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
    Get RSI status - Multi-Symbol Aware (v5.0)
    
    Query Parameters:
        symbol (optional): Symbol name (e.g., "BTCUSD", "ETHUSD")
                          If omitted, returns RSI for ALL enabled symbols
    
    Returns:
        JSON response with current RSI value(s) and status
        
    Examples:
        GET /api/guardian/rsi/status
        Response: {
            "success": true,
            "symbols": {
                "BTCUSD": {"rsi": 42.5, "status": "GO", ...},
                "ETHUSD": {"rsi": 68.2, "status": "GO", ...}
            }
        }
        
        GET /api/guardian/rsi/status?symbol=BTCUSD
        Response: {
            "success": true,
            "data": {"rsi": 42.5, "status": "GO", "symbol": "BTCUSD", ...}
        }
    """
    try:
        from flask import request
        from config.loader import get_config
        import ccxt
        
        requested_symbol = request.args.get('symbol')
        config = get_config(reload=True)
        
        # If specific symbol requested, return single-symbol response
        if requested_symbol:
            requested_symbol = requested_symbol.upper()
            rsi_data = _get_rsi_for_symbol(requested_symbol, config)
            return jsonify({
                'success': True,
                'data': rsi_data
            })
        
        # No symbol specified - return RSI for ALL enabled symbols (v5.0+)
        if hasattr(config, 'symbols') and config.symbols:
            symbols_rsi = {}
            for symbol_name, symbol_config in config.symbols.items():
                if symbol_config.enabled:
                    try:
                        symbols_rsi[symbol_name] = _get_rsi_for_symbol(symbol_name, config)
                    except Exception as e:
                        log.warning(f"Failed to get RSI for {symbol_name}: {e}")
                        symbols_rsi[symbol_name] = {
                            'symbol': symbol_name,
                            'rsi': None,
                            'status': 'ERROR',
                            'status_text': str(e),
                            'error': str(e)
                        }
            
            return jsonify({
                'success': True,
                'symbols': symbols_rsi,
                'count': len(symbols_rsi)
            })
        else:
            # v4.0 fallback - single symbol mode
            rsi_data = _get_rsi_for_symbol(None, config)
            return jsonify({
                'success': True,
                'data': rsi_data
            })
        
    except Exception as e:
        log.error(f"Error fetching RSI status: {e}", exc_info=True)
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


def _get_rsi_for_symbol(symbol_name: str, config) -> dict:
    """
    Calculate RSI for a specific symbol
    
    Args:
        symbol_name: Symbol key (e.g., 'BTCUSD') or None for v4.0 default
        config: Config object from get_config()
    
    Returns:
        Dict with RSI data for the symbol
    """
    import ccxt
    from bot.guardian.collectors.rsi_collector import RSICollector
    
    # Create exchange instance
    exchange = ccxt.delta({'enableRateLimit': True})
    
    # Get symbol-specific config (v5.0) or fallback to global (v4.0)
    if symbol_name and hasattr(config, 'symbols') and config.symbols and symbol_name in config.symbols:
        symbol_config = config.symbols[symbol_name]
        bot_mode = symbol_config.mode
        product_symbol = symbol_name
        
        # Get RSI thresholds from symbol-specific safety or global
        if hasattr(symbol_config, 'safety') and hasattr(symbol_config.safety, 'rsi'):
            long_threshold = symbol_config.safety.rsi.long_threshold
            short_threshold = symbol_config.safety.rsi.short_threshold
            hysteresis_seconds = getattr(symbol_config.safety.rsi, 'hysteresis_seconds', 60)
        else:
            # Fallback to global RSI config
            rsi_config = config.safety.rsi if hasattr(config, 'safety') and hasattr(config.safety, 'rsi') else None
            if rsi_config:
                long_threshold = rsi_config.long_threshold
                short_threshold = rsi_config.short_threshold
                hysteresis_seconds = rsi_config.hysteresis_seconds
            else:
                # Defaults if no RSI config available
                long_threshold = 25
                short_threshold = 75
                hysteresis_seconds = 60
    else:
        # v4.0 single-symbol mode or fallback
        product_symbol = symbol_name if symbol_name else (config.bot.symbol if config.bot and hasattr(config.bot, 'symbol') else 'BTCUSD')
        bot_mode = config.bot.mode if config.bot and hasattr(config.bot, 'mode') else 'LONG'
        
        # Get RSI config with fallback
        rsi_config = config.safety.rsi if hasattr(config, 'safety') and hasattr(config.safety, 'rsi') else None
        if rsi_config:
            long_threshold = rsi_config.long_threshold
            short_threshold = rsi_config.short_threshold
            hysteresis_seconds = rsi_config.hysteresis_seconds
        else:
            # Defaults if no RSI config available
            long_threshold = 25
            short_threshold = 75
            hysteresis_seconds = 60
    
    # Create RSI collector with symbol-aware config (v5.0 native support)
    rsi_collector = RSICollector(exchange, config, symbol_name=symbol_name)
    
    # Get current RSI value
    current_rsi = rsi_collector.get_latest_rsi()
    should_stop = rsi_collector.should_stop_trading()
    
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
    
    # Check hysteresis
    hysteresis_active = False
    if current_rsi is not None:
        if bot_mode == 'LONG' and current_rsi == long_threshold:
            hysteresis_active = True
        elif bot_mode == 'SHORT' and current_rsi == short_threshold:
            hysteresis_active = True
    
    return {
        'symbol': product_symbol,
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
