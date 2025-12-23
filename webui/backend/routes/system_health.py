"""
System Health API Routes

Extended health monitoring endpoints for system resources, processes, and alerts.
"""

from flask import Blueprint, jsonify, request
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Create blueprint
system_health_bp = Blueprint('system_health', __name__, url_prefix='/api/system-health')


def get_health_service():
    """Get health monitor instance (lazy import to avoid circular dependencies)"""
    try:
        from bot.system_health import get_health_monitor
        return get_health_monitor()
    except ImportError as e:
        logger.error(f"Failed to import health monitor: {e}")
        return None


@system_health_bp.route('/metrics', methods=['GET'])
def get_system_metrics():
    """
    Get current system health metrics
    
    Returns:
        - Current CPU, memory, disk, network metrics
        - Load averages
        - Timestamp
    """
    try:
        health_monitor = get_health_service()
        if not health_monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        metrics = health_monitor.get_current_metrics()
        
        if not metrics:
            return jsonify({'error': 'No metrics available yet'}), 404
        
        return jsonify({
            'status': 'success',
            'metrics': metrics.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@system_health_bp.route('/metrics/history', methods=['GET'])
def get_system_history():
    """
    Get historical system metrics
    
    Query params:
        - minutes: Number of minutes of history (default: 60)
    
    Returns:
        - List of metric snapshots
    """
    try:
        health_monitor = get_health_service()
        if not health_monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        minutes = request.args.get('minutes', 60, type=int)
        history = health_monitor.get_metrics_history(minutes=minutes)
        
        return jsonify({
            'status': 'success',
            'history': [m.to_dict() for m in history],
            'count': len(history)
        })
        
    except Exception as e:
        logger.error(f"Error getting system history: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@system_health_bp.route('/processes', methods=['GET'])
def get_process_health():
    """
    Get health status of monitored processes
    
    Returns:
        - Dictionary of process name -> health status
        - Includes PID, CPU, memory, uptime, restart count
    """
    try:
        health_monitor = get_health_service()
        if not health_monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        processes = health_monitor.get_process_health()
        
        return jsonify({
            'status': 'success',
            'processes': {k: v.to_dict() for k, v in processes.items()},
            'count': len(processes)
        })
        
    except Exception as e:
        logger.error(f"Error getting process health: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@system_health_bp.route('/api-status', methods=['GET'])
def get_api_health():
    """
    Get API endpoint health status
    
    Returns:
        - Status of monitored API endpoints
        - Latency, status codes, last check time
    """
    try:
        health_monitor = get_health_service()
        if not health_monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        api_status = health_monitor.get_api_status()
        
        return jsonify({
            'status': 'success',
            'apis': api_status,
            'count': len(api_status)
        })
        
    except Exception as e:
        logger.error(f"Error getting API health: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@system_health_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """
    Get active alerts
    
    Returns:
        - List of active (unacknowledged) alerts
        - Alert details: severity, category, metric, message
    """
    try:
        health_monitor = get_health_service()
        if not health_monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        alerts = health_monitor.get_active_alerts()
        
        # Group by severity
        by_severity = {
            'critical': [],
            'error': [],
            'warning': [],
            'info': []
        }
        
        for alert in alerts:
            severity = alert.severity
            if severity in by_severity:
                by_severity[severity].append(alert.to_dict())
        
        return jsonify({
            'status': 'success',
            'alerts': [a.to_dict() for a in alerts],
            'by_severity': by_severity,
            'count': len(alerts)
        })
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@system_health_bp.route('/alerts/history', methods=['GET'])
def get_alert_history():
    """
    Get alert history
    
    Query params:
        - hours: Number of hours of history (default: 24)
    
    Returns:
        - List of historical alerts
    """
    try:
        health_monitor = get_health_service()
        if not health_monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        hours = request.args.get('hours', 24, type=int)
        history = health_monitor.get_alert_history(hours=hours)
        
        return jsonify({
            'status': 'success',
            'history': [a.to_dict() for a in history],
            'count': len(history)
        })
        
    except Exception as e:
        logger.error(f"Error getting alert history: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@system_health_bp.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id: str):
    """
    Acknowledge an alert
    
    Path params:
        - alert_id: Alert ID to acknowledge
    
    Returns:
        - Success status
    """
    try:
        health_monitor = get_health_service()
        if not health_monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        success = health_monitor.acknowledge_alert(alert_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Alert {alert_id} acknowledged'
            })
        else:
            return jsonify({
                'error': f'Alert {alert_id} not found'
            }), 404
        
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@system_health_bp.route('/alerts/clear', methods=['POST'])
def clear_acknowledged_alerts():
    """
    Clear all acknowledged alerts from active list
    
    Returns:
        - Success status
    """
    try:
        health_monitor = get_health_service()
        if not health_monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        health_monitor.clear_acknowledged_alerts()
        
        return jsonify({
            'status': 'success',
            'message': 'Acknowledged alerts cleared'
        })
        
    except Exception as e:
        logger.error(f"Error clearing alerts: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@system_health_bp.route('/summary', methods=['GET'])
def get_health_summary():
    """
    Get comprehensive health summary
    
    Returns:
        - Current system metrics
        - Process health summary
        - API health summary
        - Active alerts summary
        - Overall health status
    """
    try:
        health_monitor = get_health_service()
        if not health_monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        # Get current metrics
        metrics = health_monitor.get_current_metrics()
        
        # Get process health
        processes = health_monitor.get_process_health()
        running_count = sum(1 for p in processes.values() if p.status == 'running')
        crashed_count = sum(1 for p in processes.values() if p.status == 'crashed')
        
        # Get API health
        api_status = health_monitor.get_api_status()
        apis_up = sum(1 for a in api_status.values() if a.get('status') == 'up')
        apis_down = sum(1 for a in api_status.values() if a.get('status') == 'down')
        
        # Get alerts
        alerts = health_monitor.get_active_alerts()
        critical_alerts = sum(1 for a in alerts if a.severity == 'critical')
        warning_alerts = sum(1 for a in alerts if a.severity == 'warning')
        
        # Determine overall health
        overall_status = 'healthy'
        if critical_alerts > 0 or crashed_count > 0 or apis_down > 0:
            overall_status = 'critical'
        elif warning_alerts > 0:
            overall_status = 'warning'
        
        return jsonify({
            'status': 'success',
            'overall_health': overall_status,
            'summary': {
                'system': {
                    'cpu_percent': metrics.cpu_percent if metrics else 0,
                    'memory_percent': metrics.memory_percent if metrics else 0,
                    'disk_percent': metrics.disk_percent if metrics else 0,
                    'timestamp': metrics.timestamp if metrics else None
                },
                'processes': {
                    'total': len(processes),
                    'running': running_count,
                    'crashed': crashed_count
                },
                'apis': {
                    'total': len(api_status),
                    'up': apis_up,
                    'down': apis_down
                },
                'alerts': {
                    'total': len(alerts),
                    'critical': critical_alerts,
                    'warning': warning_alerts
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting health summary: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
