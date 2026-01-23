"""
PM2 Routes Blueprint

This module handles all API routes related to PM2 process management.
Replaces the old tmux system with professional process management.

Routes:
- GET  /api/pm2/status - Get PM2 status and all processes
- GET  /api/pm2/process/:name - Get specific process details
- POST /api/pm2/start/:name - Start a specific process
- POST /api/pm2/stop/:name - Stop a specific process
- POST /api/pm2/restart/:name - Restart a specific process
- GET  /api/pm2/logs/:name - Get process logs
- POST /api/pm2/flush-logs - Clear all logs
- GET  /api/pm2/enabled - Check if PM2 is enabled
- POST /api/pm2/reload/:name - Zero-downtime reload
- GET  /api/pm2/describe/:name - Detailed process info

Dependencies:
- PM2 installed globally (npm install -g pm2)
- PM2 adapter module
- ecosystem.gridbot.config.js

Created: 2025-11-03
Replaces: tmux.py
"""

import os
import logging
from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

# Create blueprint
pm2_bp = Blueprint('pm2', __name__)

# Import PM2 adapter
try:
    from webui.backend.utils.pm2_adapter import get_pm2_adapter, should_use_pm2, PM2_AVAILABLE
    PM2_INTEGRATION_AVAILABLE = True
except ImportError as e:
    log.warning(f"PM2 adapter not available: {e}")
    PM2_INTEGRATION_AVAILABLE = False
    PM2_AVAILABLE = False

# ============================================================================
# Route Handlers
# ============================================================================

@pm2_bp.route('/api/pm2/enabled', methods=['GET'])
def pm2_enabled():
    """
    Check if PM2 integration is enabled
    
    Returns:
        JSON response with PM2 availability and configuration
    
    Example:
        GET /api/pm2/enabled
        Response: {
            "enabled": true,
            "available": true,
            "config_file": "/path/to/ecosystem.gridbot.config.js",
            "version": "6.0.13"
        }
    """
    try:
        if not PM2_INTEGRATION_AVAILABLE:
            return jsonify({
                'enabled': False,
                'available': False,
                'message': 'PM2 adapter not available'
            }), 200
        
        pm2 = get_pm2_adapter()
        enabled = should_use_pm2()
        
        # Get PM2 version
        version = None
        try:
            success, stdout, stderr = pm2._run_pm2_command(['--version'])
            if success:
                version = stdout.strip()
        except:
            pass
        
        return jsonify({
            'enabled': enabled,
            'available': pm2.available,
            'config_file': str(pm2.config_file),
            'version': version
        }), 200
        
    except Exception as e:
        log.error(f"Error checking PM2 status: {e}")
        return jsonify({
            'enabled': False,
            'available': False,
            'error': str(e)
        }), 500


@pm2_bp.route('/api/pm2/status', methods=['GET'])
def pm2_status():
    """
    Get PM2 status with all managed processes
    
    Returns detailed information about all PM2-managed processes including
    GridBot, Guardian, and Heartbeat.
    
    Returns:
        JSON response with PM2 process list and statistics
    
    Example:
        GET /api/pm2/status
        Response: {
            "success": true,
            "processes": [
                {
                    "name": "gridbot-live",
                    "pid": 27759,
                    "status": "online",
                    "cpu": 3.7,
                    "memory": 21.1,
                    "uptime": 300,
                    "restarts": 0,
                    "pm_id": 0
                },
                {
                    "name": "guardian-live",
                    "pid": 37189,
                    "status": "online",
                    "cpu": 1.2,
                    "memory": 68.0,
                    "uptime": 120,
                    "restarts": 0,
                    "pm_id": 1
                },
                {
                    "name": "heartbeat",
                    "pid": 37442,
                    "status": "online",
                    "cpu": 0.1,
                    "memory": 10.4,
                    "uptime": 90,
                    "restarts": 0,
                    "pm_id": 2
                }
            ],
            "total": 3,
            "online": 3,
            "stopped": 0,
            "errored": 0,
            "summary": {
                "total_cpu": 5.0,
                "total_memory": 99.5,
                "total_restarts": 0
            }
        }
    """
    try:
        if not PM2_INTEGRATION_AVAILABLE or not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 not enabled',
                'processes': []
            }), 200
        
        pm2 = get_pm2_adapter()
        processes = pm2.list_all_processes()
        
        # Calculate summary statistics
        online_count = sum(1 for p in processes if p.get('status') == 'online')
        stopped_count = sum(1 for p in processes if p.get('status') == 'stopped')
        errored_count = sum(1 for p in processes if p.get('status') in ['errored', 'stopping'])
        
        total_cpu = sum(p.get('cpu', 0) for p in processes)
        total_memory = sum(p.get('memory', 0) for p in processes)
        total_restarts = sum(p.get('restarts', 0) for p in processes)
        
        return jsonify({
            'success': True,
            'processes': processes,
            'total': len(processes),
            'online': online_count,
            'stopped': stopped_count,
            'errored': errored_count,
            'summary': {
                'total_cpu': round(total_cpu, 2),
                'total_memory': round(total_memory, 2),
                'total_restarts': total_restarts
            }
        }), 200
        
    except Exception as e:
        log.error(f"Error getting PM2 status: {e}")
        return jsonify({
            'success': False,
            'message': str(e),
            'processes': []
        }), 500


@pm2_bp.route('/api/pm2/process/<name>', methods=['GET'])
def pm2_process_details(name):
    """
    Get detailed information about a specific PM2 process
    
    Args:
        name: Process name (gridbot-live, guardian-live, heartbeat, etc.)
    
    Returns:
        JSON response with detailed process information
    
    Example:
        GET /api/pm2/process/gridbot-live
        Response: {
            "success": true,
            "process": {
                "name": "gridbot-live",
                "pid": 27759,
                "status": "online",
                "cpu": 3.7,
                "memory": 21.1,
                "uptime": 300,
                "restarts": 0,
                "script": "bot/run.py",
                "interpreter": "python3",
                "exec_mode": "fork",
                "watching": false,
                "created_at": 1730612345000,
                "env": {
                    "TRADING_MODE": "live",
                    "PYTHONPATH": "..."
                }
            }
        }
    """
    try:
        if not PM2_INTEGRATION_AVAILABLE or not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 not enabled'
            }), 200
        
        pm2 = get_pm2_adapter()
        process_info = pm2.describe_process(name)
        
        if not process_info:
            return jsonify({
                'success': False,
                'message': f'Process {name} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'process': process_info
        }), 200
        
    except Exception as e:
        log.error(f"Error getting process details for {name}: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@pm2_bp.route('/api/pm2/start/<name>', methods=['POST'])
def pm2_start_process(name):
    """
    Start a specific PM2 process
    
    Args:
        name: Process name or 'all' to start all processes
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/pm2/start/gridbot-live
        Response: {
            "success": true,
            "message": "gridbot-live started successfully",
            "pid": 27759
        }
    """
    try:
        if not PM2_INTEGRATION_AVAILABLE or not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 not enabled'
            }), 400
        
        pm2 = get_pm2_adapter()
        
        if name == 'all':
            # Start all processes
            success, message = pm2.start_all()
        else:
            # Convert common names
            if name == 'live':
                name = 'gridbot-live'
            elif name == 'demo':
                name = 'gridbot-demo'
            
            # Start specific process
            success, message = pm2.start_process(name)
        
        if success:
            # Get process info to return PID
            process_info = pm2.describe_process(name) if name != 'all' else None
            pid = process_info.get('pid') if process_info else None
            
            return jsonify({
                'success': True,
                'message': message,
                'pid': pid
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
        
    except Exception as e:
        log.error(f"Error starting PM2 process {name}: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@pm2_bp.route('/api/pm2/stop/<name>', methods=['POST'])
def pm2_stop_process(name):
    """
    Stop a specific PM2 process (graceful shutdown)
    
    Args:
        name: Process name or 'all' to stop all processes
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/pm2/stop/gridbot-live
        Response: {
            "success": true,
            "message": "gridbot-live stopped successfully (graceful shutdown)"
        }
    """
    try:
        if not PM2_INTEGRATION_AVAILABLE or not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 not enabled'
            }), 400
        
        pm2 = get_pm2_adapter()
        
        if name == 'all':
            success, message = pm2.stop_all()
        else:
            # Convert common names
            if name == 'live':
                name = 'gridbot-live'
            elif name == 'demo':
                name = 'gridbot-demo'
            
            success, message = pm2.stop_process(name)
        
        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 400
        
    except Exception as e:
        log.error(f"Error stopping PM2 process {name}: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@pm2_bp.route('/api/pm2/restart/<name>', methods=['POST'])
def pm2_restart_process(name):
    """
    Restart a specific PM2 process
    
    Args:
        name: Process name or 'all' to restart all processes
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/pm2/restart/gridbot-live
        Response: {
            "success": true,
            "message": "gridbot-live restarted successfully"
        }
    """
    try:
        if not PM2_INTEGRATION_AVAILABLE or not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 not enabled'
            }), 400
        
        pm2 = get_pm2_adapter()
        
        if name == 'all':
            success, message = pm2.restart_all()
        else:
            # Convert common names
            if name == 'live':
                name = 'gridbot-live'
            elif name == 'demo':
                name = 'gridbot-demo'
            
            success, message = pm2.restart_process(name)
        
        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 400
        
    except Exception as e:
        log.error(f"Error restarting PM2 process {name}: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@pm2_bp.route('/api/pm2/logs/<name>', methods=['GET'])
def pm2_get_logs(name):
    """
    Get logs for a specific PM2 process
    
    Args:
        name: Process name
    
    Query params:
        lines: Number of lines to return (default: 100)
        type: 'out', 'err', or 'all' (default: 'all')
    
    Returns:
        JSON response with log lines
    
    Example:
        GET /api/pm2/logs/gridbot-live?lines=50&type=err
        Response: {
            "success": true,
            "logs": {
                "out": ["line1", "line2", ...],
                "err": ["error1", "error2", ...]
            },
            "lines": 50
        }
    """
    try:
        if not PM2_INTEGRATION_AVAILABLE or not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 not enabled'
            }), 400
        
        lines = int(request.args.get('lines', 30))
        log_type = request.args.get('type', 'all')
        
        pm2 = get_pm2_adapter()
        logs = pm2.get_logs(name, lines=lines, log_type=log_type)
        
        return jsonify({
            'success': True,
            'logs': logs,
            'lines': lines,
            'type': log_type
        }), 200
        
    except Exception as e:
        log.error(f"Error getting logs for {name}: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@pm2_bp.route('/api/pm2/flush-logs', methods=['POST'])
def pm2_flush_logs():
    """
    Clear all PM2 logs
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/pm2/flush-logs
        Response: {
            "success": true,
            "message": "All PM2 logs cleared"
        }
    """
    try:
        if not PM2_INTEGRATION_AVAILABLE or not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 not enabled'
            }), 400
        
        pm2 = get_pm2_adapter()
        success, message = pm2.flush_logs()
        
        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 400
        
    except Exception as e:
        log.error(f"Error flushing logs: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@pm2_bp.route('/api/pm2/reload/<name>', methods=['POST'])
def pm2_reload_process(name):
    """
    Zero-downtime reload of a PM2 process
    
    Args:
        name: Process name
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/pm2/reload/gridbot-live
        Response: {
            "success": true,
            "message": "gridbot-live reloaded successfully (zero-downtime)"
        }
    """
    try:
        if not PM2_INTEGRATION_AVAILABLE or not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 not enabled'
            }), 400
        
        pm2 = get_pm2_adapter()
        
        # Convert common names
        if name == 'live':
            name = 'gridbot-live'
        elif name == 'demo':
            name = 'gridbot-demo'
        
        success, message = pm2.reload_process(name)
        
        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 400
        
    except Exception as e:
        log.error(f"Error reloading PM2 process {name}: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@pm2_bp.route('/api/pm2/describe/<name>', methods=['GET'])
def pm2_describe_process(name):
    """
    Get comprehensive details about a PM2 process
    
    Args:
        name: Process name
    
    Returns:
        JSON response with detailed process information including
        environment variables, paths, monitoring data, etc.
    
    Example:
        GET /api/pm2/describe/gridbot-live
        Response: {
            "success": true,
            "process": {
                "name": "gridbot-live",
                "pid": 27759,
                "status": "online",
                "monit": {
                    "cpu": 3.7,
                    "memory": 22118400
                },
                "pm2_env": {
                    "restart_time": 0,
                    "unstable_restarts": 0,
                    "created_at": 1730612345000,
                    "pm_uptime": 1730612345000,
                    "status": "online",
                    "env": {...}
                },
                ...
            }
        }
    """
    try:
        if not PM2_INTEGRATION_AVAILABLE or not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 not enabled'
            }), 400
        
        pm2 = get_pm2_adapter()
        
        # Convert common names
        if name == 'live':
            name = 'gridbot-live'
        elif name == 'demo':
            name = 'gridbot-demo'
        
        process_info = pm2.describe_process(name)
        
        if not process_info:
            return jsonify({
                'success': False,
                'message': f'Process {name} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'process': process_info
        }), 200
        
    except Exception as e:
        log.error(f"Error describing PM2 process {name}: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@pm2_bp.route('/api/pm2/save', methods=['POST'])
def pm2_save():
    """
    Save current PM2 process list (for auto-restart on reboot)
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/pm2/save
        Response: {
            "success": true,
            "message": "PM2 process list saved"
        }
    """
    try:
        if not PM2_INTEGRATION_AVAILABLE or not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 not enabled'
            }), 400
        
        pm2 = get_pm2_adapter()
        success, message = pm2.save_process_list()
        
        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 400
        
    except Exception as e:
        log.error(f"Error saving PM2 process list: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

