"""
Structured Logging Utility
Production-ready logging with JSON formatting and context tracking
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add custom fields from extra
        if hasattr(record, 'context'):
            log_data['context'] = record.context
        
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
            
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        
        return json.dumps(log_data)


class StructuredLogger:
    """
    Structured logger wrapper for production-ready logging
    """
    
    def __init__(self, name: str, log_file: Optional[Path] = None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Console handler with JSON format
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(file_handler)
    
    def log(self, level: str, message: str, **context):
        """
        Log a message with structured context
        
        Args:
            level: Log level (debug, info, warning, error, critical)
            message: Log message
            **context: Additional context fields
        """
        extra = {'context': context} if context else {}
        getattr(self.logger, level.lower())(message, extra=extra)
    
    def debug(self, message: str, **context):
        """Log debug message"""
        self.log('debug', message, **context)
    
    def info(self, message: str, **context):
        """Log info message"""
        self.log('info', message, **context)
    
    def warning(self, message: str, **context):
        """Log warning message"""
        self.log('warning', message, **context)
    
    def error(self, message: str, **context):
        """Log error message"""
        self.log('error', message, **context)
    
    def critical(self, message: str, **context):
        """Log critical message"""
        self.log('critical', message, **context)
    
    def api_request(self, method: str, path: str, **context):
        """Log API request"""
        self.info(f'API Request: {method} {path}', **context)
    
    def api_response(self, method: str, path: str, status: int, duration: float, **context):
        """Log API response"""
        self.info(
            f'API Response: {method} {path} - {status}',
            duration_ms=round(duration * 1000, 2),
            **context
        )
    
    def exception(self, message: str, exc_info=True, **context):
        """Log exception with traceback"""
        self.logger.exception(message, extra={'context': context}, exc_info=exc_info)


# Global logger instance
webui_logger = StructuredLogger('webui', log_file=Path('logs/webui_structured.log'))


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)
