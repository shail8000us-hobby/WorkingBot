"""
Multi-Symbol/Instance Support API

V6.0 MULTI-INSTANCE ARCHITECTURE:
Instance = Symbol + Mode (e.g., BTCUSD_LONG, BTCUSD_SHORT)

Provides instance and symbol management endpoints:
- GET /api/instances - List all configured instances (v6.0)
- GET /api/symbols - List all configured symbols (v5.0, backward compat)
- GET /api/symbols/<symbol> - Get details for specific symbol

Date: January 2026
"""

import logging
from pathlib import Path
from flask import Blueprint, jsonify, request

# Import YAML config helper
from config.loader import get_config, get_all_instances, get_instance_config

log = logging.getLogger(__name__)

# Create blueprint
symbols_bp = Blueprint('symbols', __name__)


def instance_to_pm2_name(instance_name: str) -> str:
    """Convert instance name (BTCUSD_LONG) to PM2 process name (gridbot-BTCUSD-LONG)"""
    # Replace underscore with dash for PM2 naming
    return f"gridbot-{instance_name.replace('_', '-')}"


def resolve_pm2_bot_process(symbol_name: str, mode: str) -> str:
    """
    Resolve the actual PM2 process name for a symbol by querying pm2 jlist first.

    PM2 ecosystem names follow the pattern: gridbot-{ticker}-{mode}
    where ticker = first 3 chars of symbol in lowercase.
    e.g.  BTCUSD + live  ->  gridbot-btc-live
          ETHUSD + demo  ->  gridbot-eth-live

    Falls back to querying pm2 jlist for any running gridbot-* process whose
    name contains the symbol ticker or the full symbol (case-insensitive),
    and finally falls back to the generated name if no live process is found.
    """
    import subprocess
    import json as _json

    ticker = symbol_name[:3].lower()                   # btcusd[:3] = 'btc'
    generated = f"gridbot-{ticker}-{mode}"            # gridbot-btc-live (preferred)

    try:
        result = subprocess.run(
            ['pm2', 'jlist'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            procs = _json.loads(result.stdout)
            # Prefer exact match for generated name; then any gridbot-* containing ticker or symbol
            candidates = [
                p['name'] for p in procs
                if p.get('name', '').startswith('gridbot-')
                and (
                    ticker in p['name'].lower()
                    or symbol_name.lower() in p['name'].lower()
                )
            ]
            if generated in candidates:
                return generated
            if candidates:
                return candidates[0]
    except Exception:
        pass

    return generated


@symbols_bp.route('/api/instances', methods=['GET'])
def list_instances():
    """
    V6.0 API: List all configured instances (Instance = Symbol + Mode)
    
    Example Response:
    {
        "instances": [
            {
                "name": "BTCUSD_LONG",
                "symbol": "BTCUSD",
                "mode": "LONG",
                "enabled": true,
                "product_id": 139,
                "grid": {...},
                "safety": {...},
                "rsi": {
                    "stop_threshold": 30.0,
                    "resume_threshold": 40.0
                },
                "database_file": "data/bot_events_BTCUSD_LONG.db"
            },
            ...
        ],
        "config_version": "6.0",
        "total": 3,
        "enabled_count": 1
    }
    """
    try:
        config = get_config()
        
        # Get all instances (enabled and disabled)
        all_instances = get_all_instances(enabled_only=False)
        
        if not all_instances:
            return jsonify({
                'error': 'No instances configured',
                'message': 'Config must have instances section (v6.0). Check config.yaml.',
                'config_version': config.version,
                'instances': []
            }), 200
        
        # Build instance list
        instances = []
        enabled_count = 0
        
        for instance_name, inst_config in all_instances.items():
            rsi_config = inst_config.get_rsi_config()
            
            instance_info = {
                'name': instance_name,
                'symbol': inst_config.symbol,
                'mode': inst_config.mode.value,
                'enabled': inst_config.enabled,
                'product_id': inst_config.product_id,
                'grid': {
                    'lower': inst_config.grid.geometry.lower,
                    'upper': inst_config.grid.geometry.upper,
                    'step': inst_config.grid.geometry.step,
                    'reference': inst_config.grid.geometry.reference
                },
                'limits': {
                    'max_open_positions': inst_config.grid.limits.max_open_positions,
                    'lot_size': inst_config.grid.limits.lot_size,
                    'max_qty_per_order': inst_config.grid.limits.max_qty_per_order
                },
                'safety': {
                    'max_account_loss_inr': inst_config.safety.max_account_loss_inr,
                    'min_liquidation_distance_pct': inst_config.safety.min_liquidation_distance_pct
                },
                'rsi': {
                    'enabled': rsi_config.enabled,
                    'stop_threshold': rsi_config.stop_threshold,
                    'resume_threshold': rsi_config.resume_threshold,
                    'period': rsi_config.period,
                    'timeframe': rsi_config.timeframe
                },
                'database_file': f"data/bot_events_{instance_name}.db",
                'monitoring_file': f"data/monitoring_snapshot_{instance_name}.json",
                'recovery_file': f"data/recovery/recovery_state_{instance_name}.json"
            }
            
            instances.append(instance_info)
            
            if inst_config.enabled:
                enabled_count += 1
        
        return jsonify({
            'instances': instances,
            'config_version': config.version,
            'total': len(instances),
            'enabled_count': enabled_count,
            'trading_mode': config.trading_mode
        })
        
    except Exception as e:
        log.error(f"Error listing instances: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to list instances',
            'message': str(e)
        }), 500


@symbols_bp.route('/api/symbols', methods=['GET'])
def list_symbols():
    """
    List all configured symbols from config.yaml (v5.0 backward compat)
    
    V6.0: Also returns instances grouped by symbol.
    
    Returns both enabled and disabled symbols with their configuration.
    Frontend can filter by enabled status.
    """
    try:
        config = get_config()
        
        # V6.0: If instances section exists, build from instances
        if config.instances:
            all_instances = get_all_instances(enabled_only=False)
            
            # Group instances by symbol
            symbols_map = {}
            for instance_name, inst_config in all_instances.items():
                symbol = inst_config.symbol
                if symbol not in symbols_map:
                    symbols_map[symbol] = {
                        'name': symbol,
                        'enabled': False,  # Will be True if any instance is enabled
                        'product_id': inst_config.product_id,
                        'instances': [],
                        'modes': []
                    }
                
                symbols_map[symbol]['instances'].append(instance_name)
                symbols_map[symbol]['modes'].append(inst_config.mode.value)
                
                if inst_config.enabled:
                    symbols_map[symbol]['enabled'] = True
                    # Use the first enabled instance's grid for display
                    if 'grid' not in symbols_map[symbol]:
                        symbols_map[symbol]['grid'] = {
                            'lower': inst_config.grid.geometry.lower,
                            'upper': inst_config.grid.geometry.upper,
                            'step': inst_config.grid.geometry.step,
                            'reference': inst_config.grid.geometry.reference
                        }
                        symbols_map[symbol]['limits'] = {
                            'max_open_positions': inst_config.grid.limits.max_open_positions,
                            'lot_size': inst_config.grid.limits.lot_size,
                            'max_qty_per_order': inst_config.grid.limits.max_qty_per_order
                        }
                        symbols_map[symbol]['safety'] = {
                            'max_account_loss_inr': inst_config.safety.max_account_loss_inr,
                            'min_liquidation_distance_pct': inst_config.safety.min_liquidation_distance_pct
                        }
            
            symbols = list(symbols_map.values())
            enabled_count = sum(1 for s in symbols if s['enabled'])
            
            return jsonify({
                'symbols': symbols,
                'config_version': config.version,
                'total': len(symbols),
                'enabled_count': enabled_count,
                'trading_mode': config.trading_mode,
                'is_v6': True,  # Flag for frontend to use instances API
                'instance_count': len(all_instances)
            })
        
        # V5.0 fallback: Check if multi-symbol config
        if not config.symbols:
            return jsonify({
                'error': 'Multi-symbol not configured',
                'message': 'Config is v4.0 (single-symbol). Run migration script to upgrade.',
                'config_version': config.version,
                'symbols': []
            }), 200
        
        # Build symbol list from v5.0 config
        symbols = []
        enabled_count = 0
        
        for symbol_name, symbol_config in config.symbols.items():
            symbol_info = {
                'name': symbol_name,
                'enabled': symbol_config.enabled,
                'product_id': symbol_config.product_id,
                'mode': symbol_config.mode.value,
                'grid': {
                    'lower': symbol_config.grid.geometry.lower,
                    'upper': symbol_config.grid.geometry.upper,
                    'step': symbol_config.grid.geometry.step,
                    'reference': symbol_config.grid.geometry.reference
                },
                'limits': {
                    'max_open_positions': symbol_config.grid.limits.max_open_positions,
                    'lot_size': symbol_config.grid.limits.lot_size,
                    'max_qty_per_order': symbol_config.grid.limits.max_qty_per_order
                },
                'safety': {
                    'max_account_loss_inr': symbol_config.safety.max_account_loss_inr,
                    'min_liquidation_distance_pct': symbol_config.safety.min_liquidation_distance_pct
                },
                'monitoring_file': f"data/monitoring_snapshot_{symbol_name}_{symbol_config.mode.value}.json",
                'database_file': f"data/bot_events_{symbol_name}_{symbol_config.mode.value}.db",
                'recovery_file': f"data/recovery/recovery_state_{symbol_name}_{symbol_config.mode.value}.json"
            }
            
            symbols.append(symbol_info)
            
            if symbol_config.enabled:
                enabled_count += 1
        
        return jsonify({
            'symbols': symbols,
            'config_version': config.version,
            'total': len(symbols),
            'enabled_count': enabled_count,
            'trading_mode': config.trading_mode
        })
        
    except Exception as e:
        log.error(f"Error listing symbols: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to list symbols',
            'message': str(e)
        }), 500


@symbols_bp.route('/api/symbols/<symbol_name>', methods=['GET'])
def get_symbol_details(symbol_name):
    """
    Get detailed configuration for a specific symbol
    
    Args:
        symbol_name: Symbol key (e.g., 'BTCUSD', 'ETHUSD')
    
    Example Response:
    {
        "name": "BTCUSD",
        "enabled": true,
        "product_id": 139,
        "mode": "LONG",
        "grid": { ... },
        "limits": { ... },
        "safety": { ... },
        "monitoring_file": "data/monitoring_snapshot_BTCUSD_LONG.json",
        "status": "active"  // or "disabled", "not_found"
    }
    """
    try:
        config = get_config()
        
        # Check if v5.0 multi-symbol config
        if not config.symbols:
            return jsonify({
                'error': 'Multi-symbol not configured',
                'message': 'Config is v4.0 (single-symbol)',
                'config_version': config.version
            }), 400
        
        # Check if symbol exists
        symbol_name = symbol_name.upper()
        if symbol_name not in config.symbols:
            available = list(config.symbols.keys())
            return jsonify({
                'error': 'Symbol not found',
                'message': f"Symbol '{symbol_name}' not configured",
                'available_symbols': available
            }), 404
        
        symbol_config = config.symbols[symbol_name]
        
        # Check monitoring file exists
        from pathlib import Path
        monitoring_file = Path(f"data/monitoring_snapshot_{symbol_name}_{symbol_config.mode}.json")
        monitoring_exists = monitoring_file.exists()
        
        # Determine status
        if not symbol_config.enabled:
            status = 'disabled'
        elif monitoring_exists:
            # Check if monitoring file is fresh (< 30s)
            import json
            from datetime import datetime
            try:
                with open(monitoring_file) as f:
                    data = json.load(f)
                timestamp = datetime.fromisoformat(data.get('timestamp', '2000-01-01'))
                age = (datetime.now() - timestamp).total_seconds()
                status = 'active' if age < 30 else 'stale'
            except:
                status = 'unknown'
        else:
            status = 'not_running'
        
        return jsonify({
            'name': symbol_name,
            'enabled': symbol_config.enabled,
            'product_id': symbol_config.product_id,
            'mode': symbol_config.mode,
            'grid': {
                'lower': symbol_config.grid.geometry.lower,
                'upper': symbol_config.grid.geometry.upper,
                'step': symbol_config.grid.geometry.step,
                'reference': symbol_config.grid.geometry.reference
            },
            'limits': {
                'max_open_positions': symbol_config.grid.limits.max_open_positions,
                'lot_size': symbol_config.grid.limits.lot_size,
                'max_qty_per_order': symbol_config.grid.limits.max_qty_per_order
            },
            'safety': {
                'max_account_loss_inr': symbol_config.safety.max_account_loss_inr,
                'min_liquidation_distance_pct': symbol_config.safety.min_liquidation_distance_pct
            },
            'monitoring_file': str(monitoring_file),
            'monitoring_exists': monitoring_exists,
            'database_file': f"data/bot_events_{symbol_name}_{symbol_config.mode}.db",
            'recovery_file': f"data/recovery/recovery_state_{symbol_name}_{symbol_config.mode}.json",
            'status': status,
            'config_version': config.version
        })
        
    except Exception as e:
        log.error(f"Error getting symbol details: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to get symbol details',
            'message': str(e)
        }), 500

# ============================================================================
# SYMBOL PROCESS CONTROL ENDPOINTS (v5.0)
# ============================================================================

@symbols_bp.route('/api/symbols/<symbol_name>/process/start', methods=['POST'])
def start_symbol_trading(symbol_name):
    """
    Start trading for a specific symbol
    
    This starts the gridbot and guardian processes for the specified symbol.
    Uses PM2 for process management if available.
    
    Args:
        symbol_name: Symbol key (e.g., 'BTCUSD', 'ETHUSD')
    
    Request Body (optional):
        {
            "start_guardian": true  // Whether to also start guardian (default: true)
        }
    
    Returns:
        JSON response with process status
    """
    import subprocess
    
    try:
        symbol_name = symbol_name.upper()
        config = get_config()
        
        # V6.0: Validate symbol by checking if any instances exist for it
        all_instances = get_all_instances(enabled_only=False)
        symbol_exists = any(inst.symbol == symbol_name for inst in all_instances.values())
        
        if not symbol_exists:
            return jsonify({
                'success': False,
                'error': f"Symbol '{symbol_name}' not found"
            }), 404
        
        # Handle request body - may be empty, None, or JSON
        try:
            data = request.get_json(silent=True) or {}
        except Exception:
            data = {}
        start_guardian = data.get('start_guardian', True)
        
        # V6.0 Multi-Instance Architecture
        # Find all enabled instances for this symbol (e.g., BTCUSD_LONG, BTCUSD_SHORT)
        symbol_instances = []
        for inst_name, inst_config in all_instances.items():
            if inst_config.symbol == symbol_name and inst_config.enabled:
                symbol_instances.append((inst_name, inst_config))
        
        if not symbol_instances:
            return jsonify({
                'success': False,
                'error': f"No enabled instances found for symbol '{symbol_name}'"
            }), 400
        
        results = {}
        mode = 'live' if config.trading_mode == 'live' else 'demo'
        guardian_process = f"guardian-{mode}"  # Guardian shared across symbols
        
        # Try PM2 first
        try:
            # Start all instances for this symbol
            for instance_name, inst_config in symbol_instances:
                # Resolve actual PM2 process name (e.g. gridbot-btc-live, not gridbot-BTCUSD-LONG)
                bot_process = resolve_pm2_bot_process(symbol_name, mode)
                
                pm2_result = subprocess.run(
                    ['pm2', 'start', bot_process],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                results[instance_name] = {
                    'success': pm2_result.returncode == 0,
                    'process': bot_process,
                    'method': 'pm2',
                    'error': pm2_result.stderr if pm2_result.returncode != 0 else None
                }
            
            # Start guardian if requested
            if start_guardian:
                guardian_result = subprocess.run(
                    ['pm2', 'start', guardian_process],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                results['guardian'] = {
                    'success': guardian_result.returncode == 0,
                    'process': guardian_process,
                    'method': 'pm2'
                }
                
        except FileNotFoundError:
            # PM2 not available - fallback to direct Python execution
            results['error'] = 'PM2 not available. Install PM2 or use launchctl.'
        
        # Calculate overall success - at least one instance started successfully
        successful_count = sum(1 for key, val in results.items() 
                              if isinstance(val, dict) and val.get('success', False))
        overall_success = successful_count > 0
        
        return jsonify({
            'success': overall_success,
            'symbol': symbol_name,
            'results': results,
            'message': f"Started trading for {symbol_name}" if overall_success else f"Failed to start {symbol_name}"
        })
        
    except Exception as e:
        log.error(f"Error starting trading for {symbol_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@symbols_bp.route('/api/symbols/<symbol_name>/process/stop', methods=['POST'])
def stop_symbol_trading(symbol_name):
    """
    Stop trading for a specific symbol (all instances)
    
    V6.0: Stops all instances for this symbol (e.g., BTCUSD_LONG and BTCUSD_SHORT).
    The bot will have 30 seconds to cancel pending orders before force stop.
    
    Args:
        symbol_name: Symbol key (e.g., 'BTCUSD', 'ETHUSD')
    
    Request Body (optional):
        {
            "stop_guardian": true,  // Whether to also stop guardian (default: false)
            "force": false          // Force immediate stop without graceful shutdown
        }
    
    Returns:
        JSON response with process status
    """
    import subprocess
    
    try:
        symbol_name = symbol_name.upper()
        config = get_config()
        
        # Handle request body - may be empty, None, or JSON
        try:
            data = request.get_json(silent=True) or {}
        except Exception:
            data = {}
        stop_guardian = data.get('stop_guardian', False)  # Changed default to false
        force = data.get('force', False)
        
        # V6.0 Multi-Instance Architecture
        # Find all instances for this symbol
        instances = get_all_instances(enabled_only=False)  # Get all including disabled
        symbol_instances = []
        for inst_name, inst_config in instances.items():
            if inst_config.symbol == symbol_name:
                symbol_instances.append((inst_name, inst_config))
        
        if not symbol_instances:
            return jsonify({
                'success': False,
                'error': f"No instances found for symbol '{symbol_name}'"
            }), 404
        
        results = {}
        mode = 'live' if config.trading_mode == 'live' else 'demo'
        guardian_process = f"guardian-{mode}"
        
        try:
            # Stop all instances for this symbol
            for instance_name, inst_config in symbol_instances:
                # Resolve actual PM2 process name (e.g. gridbot-btc-live, not gridbot-BTCUSD-LONG)
                bot_process = resolve_pm2_bot_process(symbol_name, mode)
                
                stop_cmd = ['pm2', 'stop', bot_process]
                if force:
                    stop_cmd = ['pm2', 'delete', bot_process]
                
                pm2_result = subprocess.run(
                    stop_cmd,
                    capture_output=True,
                    text=True,
                    timeout=35  # Allow 30s for graceful shutdown + 5s buffer
                )
                
                results[instance_name] = {
                    'success': pm2_result.returncode == 0,
                    'process': bot_process,
                    'method': 'pm2',
                    'error': pm2_result.stderr if pm2_result.returncode != 0 else None
                }
            
            # Stop guardian if requested
            if stop_guardian:
                guardian_cmd = ['pm2', 'stop', guardian_process] if not force else ['pm2', 'delete', guardian_process]
                guardian_result = subprocess.run(
                    guardian_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                results['guardian'] = {
                    'success': guardian_result.returncode == 0,
                    'process': guardian_process,
                    'method': 'pm2'
                }
                
        except FileNotFoundError:
            results['error'] = 'PM2 not available'
        
        # Calculate overall success - at least one instance stopped successfully
        successful_count = sum(1 for key, val in results.items() 
                              if isinstance(val, dict) and val.get('success', False))
        overall_success = successful_count > 0
        
        return jsonify({
            'success': overall_success,
            'symbol': symbol_name,
            'results': results,
            'message': f"Stopped trading for {symbol_name}" if overall_success else f"Failed to stop {symbol_name}"
        })
        
    except Exception as e:
        log.error(f"Error stopping trading for {symbol_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@symbols_bp.route('/api/symbols/<symbol_name>/process/status', methods=['GET'])
def get_symbol_process_status(symbol_name):
    """
    Get process status for a specific symbol
    
    Returns:
        JSON response with bot and guardian process status
    """
    import subprocess
    
    try:
        symbol_name = symbol_name.upper()
        config = get_config()
        
        # V6.0: Symbol-specific processes (gridbot-btcusd-live, gridbot-ethusd-live)
        # Fallback: Single-process mode (gridbot-live) for backward compatibility
        mode = 'live' if config.trading_mode == 'live' else 'demo'
        bot_process = f"gridbot-{symbol_name.lower()}-{mode}"  # e.g., gridbot-btcusd-live
        guardian_process = f"guardian-{mode}"  # Guardian shared across symbols
        
        processes = {}
        
        try:
            # Get PM2 process list as JSON
            result = subprocess.run(
                ['pm2', 'jlist'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                import json
                pm2_list = json.loads(result.stdout)
                
                for proc in pm2_list:
                    name = proc.get('name', '')
                    if name == bot_process:
                        processes['bot'] = {
                            'name': name,
                            'status': proc.get('pm2_env', {}).get('status', 'unknown'),
                            'pid': proc.get('pid'),
                            'uptime': proc.get('pm2_env', {}).get('pm_uptime'),
                            'cpu': proc.get('monit', {}).get('cpu'),
                            'memory': proc.get('monit', {}).get('memory'),
                            'restarts': proc.get('pm2_env', {}).get('restart_time', 0)
                        }
                    elif name == guardian_process:
                        processes['guardian'] = {
                            'name': name,
                            'status': proc.get('pm2_env', {}).get('status', 'unknown'),
                            'pid': proc.get('pid'),
                            'uptime': proc.get('pm2_env', {}).get('pm_uptime'),
                            'cpu': proc.get('monit', {}).get('cpu'),
                            'memory': proc.get('monit', {}).get('memory'),
                            'restarts': proc.get('pm2_env', {}).get('restart_time', 0)
                        }
                
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            log.warning(f"PM2 not available: {e}")
        
        # Determine overall status
        bot_running = processes.get('bot', {}).get('status') == 'online'
        guardian_running = processes.get('guardian', {}).get('status') == 'online'
        
        if bot_running and guardian_running:
            overall = 'running'
        elif bot_running or guardian_running:
            overall = 'partial'
        else:
            overall = 'stopped'
        
        return jsonify({
            'success': True,
            'symbol': symbol_name,
            'overall_status': overall,
            'processes': processes,
            'bot_running': bot_running,
            'guardian_running': guardian_running
        })
        
    except Exception as e:
        log.error(f"Error getting process status for {symbol_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@symbols_bp.route('/api/symbols/all/start', methods=['POST'])
def start_all_symbols():
    """
    Start trading for ALL enabled symbols
    """
    try:
        # V6.0: Start all enabled instances
        import subprocess
        
        instances = get_all_instances(enabled_only=True)  # Only enabled instances
        
        if not instances:
            return jsonify({
                'success': False,
                'error': 'No enabled instances found'
            }), 400
        
        results = {}
        for instance_name, inst_config in instances.items():
            bot_process = instance_to_pm2_name(instance_name)  # e.g., gridbot-BTCUSD-LONG
            try:
                result = subprocess.run(
                    ['pm2', 'start', bot_process],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                results[instance_name] = {
                    'success': result.returncode == 0,
                    'process': bot_process,
                    'error': result.stderr if result.returncode != 0 else None
                }
            except Exception as e:
                results[instance_name] = {'success': False, 'error': str(e)}
        
        successful = sum(1 for r in results.values() if r.get('success'))
        
        return jsonify({
            'success': successful > 0,
            'message': f"Started {successful}/{len(results)} symbols",
            'results': results
        })
        
    except Exception as e:
        log.error(f"Error starting all symbols: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@symbols_bp.route('/api/symbols/all/stop', methods=['POST'])
def stop_all_symbols():
    """
    Stop trading for ALL symbols
    """
    try:
        # V6.0: Stop all instances
        import subprocess
        
        instances = get_all_instances(enabled_only=False)  # Get all instances
        
        results = {}
        for instance_name, inst_config in instances.items():
            bot_process = instance_to_pm2_name(instance_name)  # e.g., gridbot-BTCUSD-LONG
            try:
                result = subprocess.run(
                    ['pm2', 'stop', bot_process],
                    capture_output=True,
                    text=True,
                    timeout=35
                )
                results[instance_name] = {
                    'success': result.returncode == 0 or 'not found' not in result.stderr.lower(),
                    'process': bot_process,
                    'error': result.stderr if result.returncode != 0 else None
                }
            except Exception as e:
                results[instance_name] = {'success': False, 'error': str(e)}
        
        successful = sum(1 for r in results.values() if r.get('success'))
        
        return jsonify({
            'success': True,
            'message': f"Stopped {successful}/{len(results)} symbols",
            'results': results
        })
        
    except Exception as e:
        log.error(f"Error stopping all symbols: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@symbols_bp.route('/api/symbols/<symbol_name>/status', methods=['GET'])
def get_symbol_status(symbol_name):
    """
    Get market status for a specific symbol
    
    Returns:
        JSON with market price and bot status
    """
    try:
        symbol_name = symbol_name.upper()
        
        # Get all instances for this symbol
        all_instances = get_all_instances(enabled_only=False)
        symbol_instances = {
            inst_name: inst_config 
            for inst_name, inst_config in all_instances.items() 
            if inst_config.symbol == symbol_name
        }
        
        if not symbol_instances:
            return jsonify({
                'success': False,
                'error': f"Symbol '{symbol_name}' not found"
            }), 404
        
        # Try to get market price from bot's market data file
        market_price = None
        try:
            import json
            market_data_file = Path(__file__).parent.parent.parent / 'data' / 'market_data.json'
            if market_data_file.exists():
                with open(market_data_file, 'r') as f:
                    market_data = json.load(f)
                    market_price = market_data.get(symbol_name, {}).get('price')
        except Exception as e:
            log.warning(f"Could not load market data: {e}")
        
        # If no market data file, try to get from live bot status
        if not market_price:
            try:
                from bot.utils.file_manager import get_bot_status
                bot_status = get_bot_status()
                if bot_status and 'market_price' in bot_status:
                    market_price = bot_status['market_price']
            except Exception:
                pass
        
        return jsonify({
            'success': True,
            'symbol': symbol_name,
            'market_price': market_price,
            'instances': list(symbol_instances.keys()),
            'timestamp': __import__('datetime').datetime.now().isoformat()
        })
        
    except Exception as e:
        log.error(f"Error getting symbol status for {symbol_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500