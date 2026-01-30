"""
Health Check and System Status Endpoints
Production-ready health checks for monitoring and orchestration
"""

from flask import Blueprint, jsonify
from datetime import datetime, timedelta
import psutil
import os
from pathlib import Path

from webui.backend.utils.api_response import APIResponse

health_bp = Blueprint('health', __name__)


def get_uptime():
    """Calculate WebUI uptime"""
    try:
        # Try to get process start time
        process = psutil.Process(os.getpid())
        start_time = datetime.fromtimestamp(process.create_time())
        uptime = datetime.now() - start_time
        
        return {
            'seconds': int(uptime.total_seconds()),
            'formatted': str(uptime).split('.')[0]
        }
    except:
        return {'seconds': 0, 'formatted': 'unknown'}


def check_bot_running():
    """Check if trading bot is running"""
    try:
        # Try PM2 first
        from webui.backend.utils.pm2_adapter import PM2Adapter, should_use_pm2
        if should_use_pm2():
            pm2 = PM2Adapter()
            status = pm2.get_bot_status('live')
            if status:
                return status.get('status') == 'online'
        
        # Fallback to PID file check
        from webui.backend.utils.process_helpers import is_bot_running
        return is_bot_running()
    except Exception as e:
        # If all checks fail, return False
        return False


def check_guardian_running():
    """Check if guardian is running"""
    try:
        # Check if guardian process is running
        from webui.backend.utils.process_helpers import read_pid_file, is_process_running, GUARDIAN_PID_FILE
        pid = read_pid_file(GUARDIAN_PID_FILE)
        return pid is not None and is_process_running(pid)
    except Exception as e:
        return False


def check_disk_space():
    """Check available disk space"""
    try:
        usage = psutil.disk_usage('/')
        return {
            'total_gb': round(usage.total / (1024**3), 2),
            'used_gb': round(usage.used / (1024**3), 2),
            'free_gb': round(usage.free / (1024**3), 2),
            'percent_used': usage.percent,
            'healthy': usage.percent < 90
        }
    except:
        return {'healthy': True, 'error': 'Unable to check disk space'}


def check_memory():
    """Check memory usage"""
    try:
        memory = psutil.virtual_memory()
        return {
            'total_gb': round(memory.total / (1024**3), 2),
            'used_gb': round(memory.used / (1024**3), 2),
            'available_gb': round(memory.available / (1024**3), 2),
            'percent_used': memory.percent,
            'healthy': memory.percent < 90
        }
    except:
        return {'healthy': True, 'error': 'Unable to check memory'}


def check_cpu():
    """Check CPU usage"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        return {
            'percent': cpu_percent,
            'cores': psutil.cpu_count(),
            'healthy': cpu_percent < 90
        }
    except:
        return {'healthy': True, 'error': 'Unable to check CPU'}


def check_config_file():
    """Check if config file exists and is readable"""
    try:
        # Config file is in project root, not backend directory
        project_root = Path(__file__).parent.parent.parent.parent  # health.py -> routes -> backend -> webui -> WorkingBot
        config_file = project_root / 'config.yaml'
        return {
            'exists': config_file.exists(),
            'readable': config_file.exists() and os.access(config_file, os.R_OK),
            'size_kb': round(config_file.stat().st_size / 1024, 2) if config_file.exists() else 0,
            'healthy': config_file.exists() and os.access(config_file, os.R_OK)
        }
    except:
        return {'healthy': False, 'error': 'Unable to check config file'}


def check_log_directory():
    """Check if logs directory is writable"""
    try:
        # Logs directory is in project root, not backend directory
        project_root = Path(__file__).parent.parent.parent.parent  # health.py -> routes -> backend -> webui -> WorkingBot
        log_dir = project_root / 'logs'
        log_dir.mkdir(exist_ok=True)
        test_file = log_dir / '.health_check_test'
        
        # Try to write a test file
        test_file.write_text('test')
        test_file.unlink()
        
        return {
            'exists': True,
            'writable': True,
            'healthy': True
        }
    except:
        return {
            'exists': log_dir.exists() if 'log_dir' in locals() else False,
            'writable': False,
            'healthy': False
        }


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Basic health check endpoint
    Returns 200 if service is running
    """
    # Return raw status for health check (not wrapped in APIResponse)
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }), 200


@health_bp.route('/health/detailed', methods=['GET'])
def detailed_health_check():
    """
    Detailed health check with system metrics and circuit breaker states
    Includes bot status, resources, dependencies, and circuit breakers
    """
    bot_running = check_bot_running()
    guardian_running = check_guardian_running()
    disk = check_disk_space()
    memory = check_memory()
    cpu = check_cpu()
    config = check_config_file()
    logs = check_log_directory()
    uptime = get_uptime()
    
    # Get circuit breaker states
    circuit_breakers = {}
    try:
        from webui.backend.utils.circuit_breaker import get_all_circuit_breaker_states
        circuit_breakers = get_all_circuit_breaker_states()
    except Exception as e:
        pass  # Circuit breaker states are optional
    
    # Overall health determination
    is_healthy = all([
        disk.get('healthy', True),
        memory.get('healthy', True),
        cpu.get('healthy', True),
        config.get('healthy', True),
        logs.get('healthy', True)
    ])
    
    data = {
        'status': 'healthy' if is_healthy else 'degraded',
        'uptime': uptime,
        'version': '2.0',
        'services': {
            'trading_bot': {
                'status': 'running' if bot_running else 'stopped',
                'healthy': bot_running
            },
            'guardian_bot': {
                'status': 'running' if guardian_running else 'stopped',
                'healthy': True  # Guardian is optional
            }
        },
        'resources': {
            'disk': disk,
            'memory': memory,
            'cpu': cpu
        },
        'dependencies': {
            'config_file': config,
            'log_directory': logs
        },
        'circuit_breakers': circuit_breakers
    }
    
    # Return 503 if unhealthy (for load balancers/orchestrators)
    if not is_healthy:
        return APIResponse.service_unavailable('System is degraded')
    
    return APIResponse.success(data)


@health_bp.route('/health/ready', methods=['GET'])
def readiness_check():
    """
    Kubernetes-style readiness probe
    Returns 200 if service is ready to accept traffic
    """
    config = check_config_file()
    logs = check_log_directory()
    
    is_ready = config.get('healthy', False) and logs.get('healthy', False)
    
    if is_ready:
        return APIResponse.success({'status': 'ready'})
    else:
        return APIResponse.service_unavailable('Service not ready')


@health_bp.route('/health/live', methods=['GET'])
def liveness_check():
    """
    Kubernetes-style liveness probe
    Returns 200 if service is alive (even if not healthy)
    """
    return APIResponse.success({'status': 'alive'})


@health_bp.route('/version', methods=['GET'])
def version_info():
    """Get version information"""
    return APIResponse.success({
        'version': '2.0',
        'name': 'GridBot WebUI',
        'build_date': '2025-10-28',
        'python_version': os.sys.version,
        'platform': os.sys.platform
    })
