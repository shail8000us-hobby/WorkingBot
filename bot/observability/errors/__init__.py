"""
Error Intelligence System - Core Module
Provides unified error tracking, classification, and remediation across all bots.
"""

from .schema import ErrorEvent, ErrorSeverity, ErrorStatus, ErrorSource
from .catalog import ErrorCatalog
from .collector import ErrorCollector
from .classifier import ErrorClassifier
from .remediator import ErrorRemediator

__all__ = [
    'ErrorEvent',
    'ErrorSeverity', 
    'ErrorStatus',
    'ErrorSource',
    'ErrorCatalog',
    'ErrorCollector',
    'ErrorClassifier',
    'ErrorRemediator'
]
