"""
Error Classifier - Enriches raw error messages with context and metadata
"""

import uuid
import os
import sys
import re
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from .schema import ErrorEvent, ErrorSource, ErrorSeverity, ErrorStatus
from .catalog import ErrorCatalog, ErrorPattern

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config


class ErrorClassifier:
    """Classifies and enriches error messages"""
    
    def __init__(self, catalog: Optional[ErrorCatalog] = None):
        self.catalog = catalog or ErrorCatalog()
    
    def classify(
        self,
        message: str,
        source: ErrorSource,
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorEvent:
        """
        Classify a raw error message into a structured ErrorEvent.
        """
        # Try to match against known patterns
        pattern = self.catalog.classify(message, source)
        
        if pattern:
            # Known error - use catalog data
            event = self._create_from_pattern(message, source, pattern, context)
        else:
            # Unknown error - use heuristics
            event = self._create_from_heuristics(message, source, context)
        
        # Enrich with runtime context
        self._enrich_context(event, context)
        
        return event
    
    def _create_from_pattern(
        self,
        message: str,
        source: ErrorSource,
        pattern: ErrorPattern,
        context: Optional[Dict[str, Any]]
    ) -> ErrorEvent:
        """Create ErrorEvent from catalog pattern"""
        return ErrorEvent(
            id=str(uuid.uuid4()),
            code=pattern.code,
            source=source,
            severity=pattern.severity,
            status=ErrorStatus.OPEN,
            message_raw=message,
            traceback=self._extract_traceback(message),
            title=pattern.title,
            explanation=pattern.explanation,
            likely_causes=pattern.likely_causes,
            suggested_actions=pattern.suggested_actions,
            can_auto_fix=pattern.can_auto_fix,
            available_fixes=pattern.available_fixes,
            context=context or {}
        )
    
    def _create_from_heuristics(
        self,
        message: str,
        source: ErrorSource,
        context: Optional[Dict[str, Any]]
    ) -> ErrorEvent:
        """Create ErrorEvent using heuristics for unknown errors"""
        
        # Determine severity from keywords
        severity = self._guess_severity(message)
        
        # Generate a generic code
        code = f"UNKNOWN_{source.value.upper()}_{self._extract_error_type(message)}"
        
        return ErrorEvent(
            id=str(uuid.uuid4()),
            code=code,
            source=source,
            severity=severity,
            status=ErrorStatus.OPEN,
            message_raw=message,
            traceback=self._extract_traceback(message),
            title=f"Unclassified {severity.value.title()} Error",
            explanation=(
                "This error hasn't been classified yet. "
                "The system detected it as potentially important but needs manual review."
            ),
            likely_causes=[
                "Unknown issue - requires investigation",
                "New error type not in catalog"
            ],
            suggested_actions=[
                "Review the full error message and logs",
                "Check if this is a known issue in documentation",
                "Report to developers if it appears to be a bug"
            ],
            can_auto_fix=False,
            available_fixes=[],
            context=context or {}
        )
    
    def _guess_severity(self, message: str) -> ErrorSeverity:
        """Guess severity from message content"""
        message_lower = message.lower()
        
        # Critical indicators
        if any(word in message_lower for word in [
            'critical', 'fatal', 'crash', 'down', 'stopped',
            'liquidation', 'bankruptcy', 'unauthorized', 'authentication'
        ]):
            return ErrorSeverity.CRITICAL
        
        # High severity indicators
        if any(word in message_lower for word in [
            'error', 'failed', 'exception', 'rejected', 'refused',
            'insufficient', 'exceeded', 'unreachable'
        ]):
            return ErrorSeverity.HIGH
        
        # Medium severity indicators
        if any(word in message_lower for word in [
            'warning', 'retry', 'timeout', 'slow'
        ]):
            return ErrorSeverity.MEDIUM
        
        return ErrorSeverity.LOW
    
    def _extract_error_type(self, message: str) -> str:
        """Extract error type for code generation"""
        # Look for common error patterns
        patterns = {
            'API': r'api|request|response|http',
            'NETWORK': r'network|connection|timeout|unreachable',
            'CONFIG': r'config|parameter|setting',
            'ORDER': r'order|trade|position',
            'AUTH': r'auth|key|token|unauthorized',
            'PARSE': r'parse|json|decode|invalid',
            'MARGIN': r'margin|balance|insufficient'
        }
        
        for error_type, pattern in patterns.items():
            if re.search(pattern, message, re.IGNORECASE):
                return error_type
        
        return 'GENERAL'
    
    def _extract_traceback(self, message: str) -> Optional[str]:
        """Extract Python traceback if present"""
        if 'Traceback' in message:
            # Try to extract full traceback
            lines = message.split('\n')
            traceback_lines = []
            in_traceback = False
            
            for line in lines:
                if 'Traceback' in line:
                    in_traceback = True
                if in_traceback:
                    traceback_lines.append(line)
                    # Stop at the actual exception line
                    if line.strip() and not line.startswith(' ') and 'Error' in line:
                        break
            
            if traceback_lines:
                return '\n'.join(traceback_lines)
        
        return None
    
    def _enrich_context(self, event: ErrorEvent, additional_context: Optional[Dict[str, Any]]):
        """Enrich event with runtime context"""
        
        # Add trading mode from YAML config
        try:
            cfg = get_config()
            event.context['trading_mode'] = cfg.safety.trading_mode
        except:
            pass
        
        # Add timestamp context
        event.context['classified_at'] = datetime.utcnow().isoformat()
        
        # Add bot status if available
        if additional_context:
            event.context.update(additional_context)
        
        # Add relevant documentation links based on error code
        event.links = self._get_relevant_links(event.code)
    
    def _get_relevant_links(self, code: str) -> list[Dict[str, str]]:
        """Get relevant documentation links for error code"""
        links = []
        
        # Map error codes to documentation
        doc_map = {
            'API_AUTH_FAILED': [
                {'title': 'API Setup Guide', 'url': '/docs/api-setup'},
                {'title': 'Troubleshooting Auth', 'url': '/docs/troubleshooting#auth'}
            ],
            'API_RATE_LIMIT': [
                {'title': 'Rate Limiting Guide', 'url': '/docs/rate-limits'},
            ],
            'INSUFFICIENT_MARGIN': [
                {'title': 'Risk Management', 'url': '/docs/risk-management'},
                {'title': 'Guardian Bot Setup', 'url': '/docs/guardian'}
            ],
            'LIQUIDATION_RISK': [
                {'title': 'Liquidation Protection', 'url': '/docs/liquidation-protection'},
                {'title': 'Emergency Procedures', 'url': '/docs/emergency'}
            ],
            'CONFIG_PARAM_DRIFT': [
                {'title': 'Parameter Sync Guide', 'url': '/docs/parameter-sync'},
                {'title': 'Hot Reload System', 'url': '/docs/hot-reload'}
            ],
            'HOT_RELOAD_FAILED': [
                {'title': 'Hot Reload System', 'url': '/docs/hot-reload'},
                {'title': 'Configuration Guide', 'url': '/docs/configuration'}
            ]
        }
        
        if code in doc_map:
            links.extend(doc_map[code])
        
        # Always add general troubleshooting link
        links.append({
            'title': 'General Troubleshooting',
            'url': '/docs/troubleshooting'
        })
        
        return links
