"""
Standardized API Response Wrapper
Production-ready JSON response formatting for consistent API behavior
"""

from datetime import datetime
from typing import Any, Dict, Optional
from flask import jsonify, Response


class APIResponse:
    """
    Standardized API response wrapper for consistent JSON responses
    """
    
    @staticmethod
    def success(
        data: Any = None,
        message: Optional[str] = None,
        meta: Optional[Dict] = None,
        status_code: int = 200
    ) -> tuple[Response, int]:
        """
        Return a successful API response
        
        Args:
            data: The response data (can be dict, list, string, etc.)
            message: Optional success message
            meta: Optional metadata (pagination, counts, etc.)
            status_code: HTTP status code (default: 200)
            
        Returns:
            Tuple of (JSON response, status_code)
        """
        response_data = {
            'success': True,
            'data': data,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        if message:
            response_data['message'] = message
            
        if meta:
            response_data['meta'] = meta
            
        return jsonify(response_data), status_code
    
    @staticmethod
    def error(
        message: str,
        code: int = 400,
        details: Any = None,
        error_type: Optional[str] = None
    ) -> tuple[Response, int]:
        """
        Return an error API response
        
        Args:
            message: User-friendly error message
            code: HTTP status code (400, 404, 500, etc.)
            details: Additional error details (validation errors, stack traces in debug mode)
            error_type: Error type/category (e.g., 'ValidationError', 'AuthenticationError')
            
        Returns:
            Tuple of (JSON response, status_code)
        """
        error_data = {
            'success': False,
            'error': {
                'message': message,
                'code': code
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        if details:
            error_data['error']['details'] = details
            
        if error_type:
            error_data['error']['type'] = error_type
            
        return jsonify(error_data), code
    
    @staticmethod
    def created(data: Any = None, message: str = 'Resource created successfully') -> tuple[Response, int]:
        """Return a 201 Created response"""
        return APIResponse.success(data, message, status_code=201)
    
    @staticmethod
    def accepted(message: str = 'Request accepted for processing') -> tuple[Response, int]:
        """Return a 202 Accepted response (for async operations)"""
        return APIResponse.success(None, message, status_code=202)
    
    @staticmethod
    def no_content() -> tuple[Response, int]:
        """Return a 204 No Content response"""
        return jsonify({}), 204
    
    @staticmethod
    def bad_request(message: str = 'Bad request', details: Any = None) -> tuple[Response, int]:
        """Return a 400 Bad Request response"""
        return APIResponse.error(message, 400, details, 'BadRequest')
    
    @staticmethod
    def unauthorized(message: str = 'Unauthorized') -> tuple[Response, int]:
        """Return a 401 Unauthorized response"""
        return APIResponse.error(message, 401, error_type='Unauthorized')
    
    @staticmethod
    def forbidden(message: str = 'Forbidden') -> tuple[Response, int]:
        """Return a 403 Forbidden response"""
        return APIResponse.error(message, 403, error_type='Forbidden')
    
    @staticmethod
    def not_found(message: str = 'Resource not found') -> tuple[Response, int]:
        """Return a 404 Not Found response"""
        return APIResponse.error(message, 404, error_type='NotFound')
    
    @staticmethod
    def conflict(message: str = 'Conflict', details: Any = None) -> tuple[Response, int]:
        """Return a 409 Conflict response"""
        return APIResponse.error(message, 409, details, 'Conflict')
    
    @staticmethod
    def validation_error(errors: Dict) -> tuple[Response, int]:
        """Return a 422 Unprocessable Entity response for validation errors"""
        return APIResponse.error(
            'Validation failed',
            422,
            errors,
            'ValidationError'
        )
    
    @staticmethod
    def internal_error(
        message: str = 'Internal server error',
        details: Any = None,
        include_details: bool = False
    ) -> tuple[Response, int]:
        """
        Return a 500 Internal Server Error response
        
        Args:
            message: Error message
            details: Error details (only included if include_details=True)
            include_details: Whether to include details (should be False in production)
        """
        return APIResponse.error(
            message,
            500,
            details if include_details else None,
            'InternalServerError'
        )
    
    @staticmethod
    def service_unavailable(message: str = 'Service temporarily unavailable') -> tuple[Response, int]:
        """Return a 503 Service Unavailable response"""
        return APIResponse.error(message, 503, error_type='ServiceUnavailable')
    
    @staticmethod
    def rate_limited(message: str = 'Rate limit exceeded', retry_after: Optional[int] = None) -> tuple[Response, int]:
        """Return a 429 Too Many Requests response"""
        response, code = APIResponse.error(message, 429, error_type='RateLimited')
        if retry_after:
            response.headers['Retry-After'] = str(retry_after)
        return response, code
