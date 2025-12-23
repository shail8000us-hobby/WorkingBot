"""
Error Intelligence System - Backend Module
"""

from .manager import ErrorIntelligenceManager
from .routes import errors_bp

__all__ = ['ErrorIntelligenceManager', 'errors_bp']
