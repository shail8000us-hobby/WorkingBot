"""
Request/Response Middleware
Logging, request ID tracking, and security headers
"""

import time
import uuid
from flask import g, request
from datetime import datetime
from typing import Any

from .structured_logger import get_logger
from .api_response import APIResponse

logger = get_logger(__name__)


def register_middleware(app):
    """
    Register all middleware with the Flask app
    
    Args:
        app: Flask application instance
    """
    
    @app.before_request
    def before_request_handler():
        """
        Execute before each request
        - Generate request ID
        - Start timing
        - Log request details
        """
        # Generate unique request ID
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()
        
        # Log request
        logger.api_request(
            method=request.method,
            path=request.path,
            request_id=g.request_id,
            ip=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else None
        )
    
    @app.after_request
    def after_request_handler(response):
        """
        Execute after each request
        - Calculate request duration
        - Add security headers
        - Log response
        """
        # Calculate duration
        duration = time.time() - g.start_time if hasattr(g, 'start_time') else 0
        
        # Add request ID to response headers
        if hasattr(g, 'request_id'):
            response.headers['X-Request-ID'] = g.request_id
        
        # Add security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Add HSTS header for HTTPS
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Add cache control for API responses
        if request.path.startswith('/api/'):
            # Most API responses shouldn't be cached
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        # Log response
        logger.api_response(
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration=duration,
            request_id=getattr(g, 'request_id', 'unknown')
        )
        
        return response
    
    @app.errorhandler(400)
    def bad_request_handler(error):
        """Handle 400 errors"""
        return APIResponse.bad_request(str(error))
    
    @app.errorhandler(401)
    def unauthorized_handler(error):
        """Handle 401 errors"""
        return APIResponse.unauthorized('Authentication required')
    
    @app.errorhandler(403)
    def forbidden_handler(error):
        """Handle 403 errors"""
        return APIResponse.forbidden('Access denied')
    
    @app.errorhandler(404)
    def not_found_handler(error):
        """Handle 404 errors"""
        return APIResponse.not_found('Endpoint not found')
    
    @app.errorhandler(405)
    def method_not_allowed_handler(error):
        """Handle 405 errors"""
        return APIResponse.error('Method not allowed', 405)
    
    @app.errorhandler(429)
    def rate_limit_handler(error):
        """Handle rate limit errors"""
        return APIResponse.rate_limited('Too many requests, please try again later')
    
    @app.errorhandler(500)
    def internal_error_handler(error):
        """Handle 500 errors"""
        logger.exception('Internal server error', exc_info=error)
        
        # Only include details in debug mode
        include_details = app.debug
        details = str(error) if include_details else None
        
        return APIResponse.internal_error(
            'An unexpected error occurred',
            details=details,
            include_details=include_details
        )
    
    @app.errorhandler(503)
    def service_unavailable_handler(error):
        """Handle 503 errors"""
        return APIResponse.service_unavailable('Service temporarily unavailable, please try again later')
    
    @app.errorhandler(Exception)
    def unhandled_exception_handler(error):
        """Catch-all for unhandled exceptions"""
        logger.exception('Unhandled exception', exc_info=error)
        
        # Only include details in debug mode
        include_details = app.debug
        details = str(error) if include_details else None
        
        return APIResponse.internal_error(
            'An unexpected error occurred',
            details=details,
            include_details=include_details
        )


def require_json(f):
    """
    Decorator to require JSON content type
    
    Usage:
        @app.route('/api/update', methods=['POST'])
        @require_json
        def update_config():
            data = request.get_json()
    """
    from functools import wraps
    
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not request.is_json:
            return APIResponse.bad_request('Content-Type must be application/json')
        return f(*args, **kwargs)
    
    return wrapper


def add_request_context(**context):
    """
    Add context to the current request for logging
    
    Usage:
        add_request_context(user_id='123', action='update_config')
    """
    if not hasattr(g, 'context'):
        g.context = {}
    g.context.update(context)


def get_request_context() -> dict:
    """Get request context"""
    return getattr(g, 'context', {})
