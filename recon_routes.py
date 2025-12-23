"""
Reconciliation Routes
Provides API endpoints for reconciliation service
"""

import logging
from flask import Blueprint, jsonify, request
from datetime import datetime

log = logging.getLogger('recon_routes')

# Global reconciliation service instance
_reconciliation_service = None

def init_reconciliation_service(service):
    """Initialize reconciliation service"""
    global _reconciliation_service
    _reconciliation_service = service

# Create blueprint
recon_bp = Blueprint('recon', __name__)

@recon_bp.route('/api/recon/status', methods=['GET'])
def get_reconciliation_status():
    """Get reconciliation service status"""
    try:
        if not _reconciliation_service:
            return jsonify({
                'status': 'error',
                'error': 'Reconciliation service not available'
            }), 503
        
        # Return flat structure that frontend expects
        return jsonify({
            'status': 'success',
            'enabled': True,
            'last_run': getattr(_reconciliation_service, 'last_run', None),
            'last_success': getattr(_reconciliation_service, 'last_success', None),
            'counters': getattr(_reconciliation_service, 'get_counters', lambda: {})(),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@recon_bp.route('/api/recon/run', methods=['POST'])
def run_reconciliation():
    """Run reconciliation manually"""
    try:
        if not _reconciliation_service:
            return jsonify({
                'success': False,
                'error': 'Reconciliation service not available'
            }), 503
        
        result = _reconciliation_service.reconcile()
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

