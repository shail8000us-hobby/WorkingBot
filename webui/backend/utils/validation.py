"""
Request Validation Decorators
Production-ready input validation using marshmallow schemas
"""

from functools import wraps
from typing import Type, Optional
from flask import request
from marshmallow import Schema, ValidationError, fields, validate

from .api_response import APIResponse


def validate_request(
    schema_class: Type[Schema],
    location: str = 'json'
) -> callable:
    """
    Decorator to validate request data using marshmallow schema
    
    Args:
        schema_class: Marshmallow schema class
        location: Where to get data from ('json', 'args', 'form')
        
    Usage:
        @app.route('/api/update', methods=['POST'])
        @validate_request(UpdateConfigSchema)
        def update_config():
            data = request.validated_data
            # data is already validated
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                schema = schema_class()
                
                # Get data based on location
                if location == 'json':
                    raw_data = request.get_json() or {}
                elif location == 'args':
                    raw_data = request.args.to_dict()
                elif location == 'form':
                    raw_data = request.form.to_dict()
                else:
                    return APIResponse.bad_request(f'Invalid location: {location}')
                
                # Validate and load data
                validated_data = schema.load(raw_data)
                
                # Attach validated data to request object
                request.validated_data = validated_data
                
                return f(*args, **kwargs)
                
            except ValidationError as e:
                return APIResponse.validation_error(e.messages)
            except Exception as e:
                return APIResponse.bad_request(str(e))
        
        return wrapper
    return decorator


def validate_query_params(schema_class: Type[Schema]) -> callable:
    """
    Decorator to validate query parameters
    
    Usage:
        @app.route('/api/data')
        @validate_query_params(DataQuerySchema)
        def get_data():
            params = request.validated_data
    """
    return validate_request(schema_class, location='args')


# Common validation schemas

class BotControlSchema(Schema):
    """Schema for bot start/stop operations"""
    with_monitor = fields.Boolean(missing=True)
    reason = fields.String(missing=None)


class ConfigUpdateSchema(Schema):
    """Schema for config updates"""
    key = fields.String(required=True, validate=validate.Length(min=1, max=200))
    value = fields.String(required=True, allow_none=True)


class EmergencyKillSchema(Schema):
    """Schema for emergency kill operations"""
    reason = fields.String(required=True, validate=validate.Length(min=1, max=500))
    confirmed = fields.Boolean(required=True, validate=validate.Equal(True))


class PaginationSchema(Schema):
    """Schema for pagination parameters"""
    page = fields.Integer(missing=1, validate=validate.Range(min=1))
    per_page = fields.Integer(missing=50, validate=validate.Range(min=1, max=1000))
    sort_by = fields.String(missing='timestamp')
    order = fields.String(missing='desc', validate=validate.OneOf(['asc', 'desc']))


class LogQuerySchema(PaginationSchema):
    """Schema for log query parameters"""
    level = fields.String(missing=None, validate=validate.OneOf([
        'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', None
    ]))
    search = fields.String(missing=None)
    start_time = fields.DateTime(missing=None)
    end_time = fields.DateTime(missing=None)


class PositionFilterSchema(Schema):
    """Schema for position filtering"""
    status = fields.String(missing=None, validate=validate.OneOf([
        'open', 'closed', 'all', None
    ]))
    symbol = fields.String(missing=None)


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitize string input by removing dangerous characters
    
    Args:
        value: Input string
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return str(value)
    
    # Truncate to max length
    value = value[:max_length]
    
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Strip leading/trailing whitespace
    value = value.strip()
    
    return value


def sanitize_dict(data: dict) -> dict:
    """
    Recursively sanitize all string values in a dictionary
    
    Args:
        data: Input dictionary
        
    Returns:
        Sanitized dictionary
    """
    if not isinstance(data, dict):
        return data
    
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_string(item) if isinstance(item, str)
                else sanitize_dict(item) if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            sanitized[key] = value
    
    return sanitized
