"""
Metrics Routes Blueprint

This module handles all API routes related to system metrics and monitoring.

Routes:
- GET /api/metrics/queue - Request queue and concurrency metrics
- GET /api/metrics/circuit-breakers - Circuit breaker states

Dependencies:
- webui.backend.utils.request_queue (queue_metrics_endpoint)
- webui.backend.utils.circuit_breaker (get_all_circuit_breaker_states)
- Timeout decorators (fast_timeout)

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import os
import logging
from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

# Get BASE_DIR
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create blueprint
metrics_bp = Blueprint('metrics', __name__)

# Try to import metrics functions
try:
    from webui.backend.utils.request_queue import queue_metrics_endpoint
    from webui.backend.utils.circuit_breaker import get_all_circuit_breaker_states
    from webui.backend.utils.timeout_decorator import fast_timeout
    METRICS_AVAILABLE = True
except ImportError as e:
    log.warning(f"Metrics utilities not available: {e}")
    METRICS_AVAILABLE = False
    # Create placeholder decorator
    def fast_timeout(seconds=1):
        def decorator(f):
            return f
        return decorator

# ============================================================================
# Route Handlers
# ============================================================================

@metrics_bp.route('/api/errors/statistics', methods=['GET'])
def get_error_statistics():
    """
    Get error statistics from Error Intelligence System
    
    Returns statistics about errors including counts by severity and status.
    Used by Health Check Dashboard and Error Intelligence panels.
    
    Returns:
        JSON response with error statistics
    
    Example:
        GET /api/errors/statistics
        Response: {
            "success": true,
            "statistics": {
                "by_severity": {"critical": 0, "high": 1, "medium": 3, "low": 5},
                "by_status": {"open": 2, "acknowledged": 3, "resolved": 4},
                "total": 9
            }
        }
    """
    try:
        # Try to import error manager
        try:
            from webui.backend.error_intelligence import error_manager
            
            if not error_manager:
                raise ImportError("Error manager not initialized")
                
            stats = error_manager.get_statistics()
            return jsonify({
                'success': True,
                'statistics': stats
            }), 200
            
        except ImportError:
            # Error intelligence not available - return empty stats
            return jsonify({
                'success': True,
                'statistics': {
                    'by_severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0},
                    'by_status': {'open': 0, 'acknowledged': 0, 'resolved': 0},
                    'total': 0
                }
            }), 200
        
    except Exception as e:
        log.error(f"Error getting error statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'statistics': {}
        }), 500


@metrics_bp.route('/api/metrics/queue', methods=['GET'])
@fast_timeout(seconds=1)
def get_queue_metrics():
    """
    Get request queue and concurrency metrics
    
    Returns metrics about the request queue including pending requests,
    active workers, and concurrency limits.
    
    Returns:
        JSON response with queue metrics
    
    Example:
        GET /api/metrics/queue
        Response: {
            "pending_requests": 0,
            "active_workers": 2,
            "max_workers": 10,
            "queue_utilization": 0.2
        }
    """
    try:
        if not METRICS_AVAILABLE:
            return jsonify({
                'error': 'Metrics utilities not available',
                'pending_requests': 0,
                'active_workers': 0
            }), 503
        
        metrics = queue_metrics_endpoint()
        return jsonify(metrics), 200
        
    except Exception as e:
        log.error(f"Error getting queue metrics: {e}")
        return jsonify({'error': str(e)}), 500


@metrics_bp.route('/api/metrics/circuit-breakers', methods=['GET'])
def get_circuit_breaker_states_route():
    """
    Get all circuit breaker states for monitoring
    
    Returns the current state of all registered circuit breakers including
    trip counts, failure rates, and current status (open/closed/half-open).
    
    Returns:
        JSON response with circuit breaker states
    
    Example:
        GET /api/metrics/circuit-breakers
        Response: {
            "delta_api": {
                "state": "closed",
                "failures": 0,
                ...
            },
            ...
        }
    """
    try:
        # Try dynamic import if global import failed
        try:
            from webui.backend.utils.circuit_breaker import get_all_circuit_breaker_states as get_states
        except ImportError as ie:
            log.error(f"Import error: {ie}")
            return jsonify({
                'error': 'Circuit breaker utilities not available',
                'breakers': {}
            }), 503
        
        states = get_states()
        return jsonify(states), 200
        
    except Exception as e:
        log.error(f"Error getting circuit breaker states: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500


# ============================================================================
# Error Management Routes
# ============================================================================

@metrics_bp.route('/api/errors/', methods=['GET'])
def get_errors_filtered():
    """Get filtered errors from Error Intelligence System"""
    try:
        try:
            from webui.backend.error_intelligence import error_manager
            ERROR_AVAILABLE = error_manager is not None
        except ImportError:
            ERROR_AVAILABLE = False
        
        if not ERROR_AVAILABLE:
            return jsonify({
                'success': True,
                'errors': []
            }), 200
        
        # Get query parameters
        status_filters = request.args.getlist('status')
        
        # Get all errors and filter by status
        all_errors = error_manager.get_all_errors() if hasattr(error_manager, 'get_all_errors') else []
        
        if status_filters:
            filtered_errors = [e for e in all_errors if isinstance(e, dict) and e.get('status') in status_filters]
        else:
            filtered_errors = all_errors
        
        return jsonify({
            'success': True,
            'errors': filtered_errors
        }), 200
    except Exception as e:
        log.error(f"Error getting filtered errors: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'errors': []
        }), 500


@metrics_bp.route('/api/errors/live', methods=['GET'])
def get_live_errors():
    """
    Get real-time errors from bot logs
    Production-grade endpoint for live error monitoring
    """
    try:
        from datetime import datetime
        
        # Import the log parser
        from webui.backend.log_parser import get_parser
        
        # Get query parameters
        max_errors = int(request.args.get('limit', 50))
        severity_filter = request.args.get('severity', 'All')
        lines = int(request.args.get('lines', 500))
        
        # Validate parameters
        max_errors = min(max(1, max_errors), 200)  # Between 1 and 200
        lines = min(max(100, lines), 2000)  # Between 100 and 2000
        
        # Get the log parser
        parser = get_parser(BASE_DIR)
        
        # Parse latest errors
        result = parser.get_latest_errors(
            max_errors=max_errors,
            severity_filter=severity_filter if severity_filter != 'All' else None
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        log.error(f"Error in /api/errors/live: {e}")
        import traceback
        log.error(traceback.format_exc())
        
        return jsonify({
            'success': False,
            'error': str(e),
            'errors': [],
            'total_count': 0,
            'severity_counts': {'Critical': 0, 'Warning': 0, 'Info': 0},
            'category_counts': {},
            'log_file': str(BASE_DIR / 'bot_live.log'),
            'log_exists': False,
            'timestamp': datetime.now().isoformat(),
        }), 500


@metrics_bp.route('/api/errors/scan', methods=['POST'])
def scan_for_errors():
    """
    Stub endpoint for old Error Intelligence system
    Returns success to prevent error dialogs
    """
    return jsonify({
        'success': True,
        'found': 0,
        'message': 'Error scanning disabled. Use Live Error Monitor instead.'
    }), 200


@metrics_bp.route('/api/metrics/recent', methods=['GET'])
def get_recent_metrics():
    """
    Get recent metrics for Guardian Dashboard charting
    
    Query params:
    - metric_type: Filter by metric type (optional)
    - hours: Number of hours to look back (default: 24)
    - limit: Maximum records to return (default: 1000)
    
    Returns:
        JSON with metrics data and summaries
    
    Example:
        GET /api/metrics/recent?metric_type=api_latency&hours=24
        Response: {
            "success": true,
            "metrics": [
                {"timestamp": "2025-11-12T10:30:00", "name": "/api/positions", "value": 45.2, "status": "ok"},
                ...
            ],
            "summary": {
                "avg": 50.5,
                "min": 12.3,
                "max": 234.5,
                "count": 1234
            }
        }
    """
    try:
        from webui.backend.utils.metrics_logger import metrics_logger
        
        # Get query params
        metric_type = request.args.get('metric_type', None)
        hours = int(request.args.get('hours', 24))
        limit = int(request.args.get('limit', 1000))
        
        # Get metrics
        raw_metrics = metrics_logger.get_recent_metrics(
            metric_type=metric_type,
            hours=hours,
            limit=limit
        )
        
        # Format for response
        metrics = []
        for row in raw_metrics:
            metrics.append({
                'timestamp': row[0],
                'type': row[1],
                'name': row[2],
                'value': row[3],
                'status': row[4],
                'metadata': row[5] if len(row) > 5 else None
            })
        
        # Get summary if specific metric requested
        summary = None
        if metric_type and metrics:
            # Group by metric name and get summary
            metric_names = set(m['name'] for m in metrics)
            summaries = {}
            for name in metric_names:
                summaries[name] = metrics_logger.get_metric_summary(
                    metric_type=metric_type,
                    metric_name=name,
                    hours=hours
                )
            summary = summaries
        
        return jsonify({
            'success': True,
            'metrics': metrics,
            'summary': summary,
            'count': len(metrics),
            'metric_type': metric_type,
            'hours': hours
        }), 200
        
    except Exception as e:
        log.error(f"Error fetching recent metrics: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'metrics': [],
            'count': 0
        }), 500

