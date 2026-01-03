"""
Frontend Error Logger
Endpoint to capture and log frontend JavaScript errors
"""

from flask import Blueprint, request, jsonify
import logging

log = logging.getLogger(__name__)

frontend_error_bp = Blueprint('frontend_error', __name__)

@frontend_error_bp.route('/api/logs/frontend-error', methods=['POST', 'OPTIONS'])
def log_frontend_error():
    """
    Log frontend errors sent via POST
    """
    if request.method == 'OPTIONS':
        # Handle CORS preflight
        return '', 200
    
    try:
        error_data = request.get_json() or {}
        
        error_msg = error_data.get('message', 'Unknown error')
        stack = error_data.get('stack', 'No stack trace')
        component_stack = error_data.get('componentStack', '')
        url = error_data.get('url', '')
        
        log.error(f"""
========================================
FRONTEND ERROR
========================================
Message: {error_msg}
URL: {url}
Stack: {stack}
Component Stack: {component_stack}
========================================
""")
        
        return jsonify({'success': True, 'logged': True}), 200
        
    except Exception as e:
        log.error(f"Error logging frontend error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
