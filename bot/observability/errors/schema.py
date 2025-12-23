"""
Error Intelligence System - Schema Definitions
Unified error event schema for all bots.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import json


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    CRITICAL = "critical"  # System down, trading stopped, data loss
    HIGH = "high"          # Degraded functionality, needs immediate attention
    MEDIUM = "medium"      # Non-critical issues, should be addressed
    LOW = "low"            # Informational, minor issues


class ErrorStatus(str, Enum):
    """Error lifecycle status"""
    OPEN = "open"                    # New, unhandled
    ACKNOWLEDGED = "acknowledged"     # Seen by user
    IN_PROGRESS = "in_progress"      # Fix being applied
    RESOLVED = "resolved"             # Fixed
    IGNORED = "ignored"               # User chose to ignore


class ErrorSource(str, Enum):
    """Bot sources"""
    TRADING = "trading"
    GUARDIAN = "guardian"
    HEALTH = "health"
    SYSTEM = "system"


@dataclass
class ErrorAction:
    """Remediation action definition"""
    id: str
    title: str
    description: str
    requires_confirmation: bool = True
    is_destructive: bool = False
    is_dry_runnable: bool = True
    estimated_duration_sec: int = 5
    preconditions: List[str] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'requires_confirmation': self.requires_confirmation,
            'is_destructive': self.is_destructive,
            'is_dry_runnable': self.is_dry_runnable,
            'estimated_duration_sec': self.estimated_duration_sec,
            'preconditions': self.preconditions,
            'side_effects': self.side_effects
        }


@dataclass
class ErrorEvent:
    """Unified error event structure"""
    # Identity (required fields)
    id: str                           # UUID
    code: str                         # Stable error code (e.g., "API_AUTH_FAILED")
    message_raw: str                  # Original log line
    source: ErrorSource
    severity: ErrorSeverity
    
    # Optional fields with defaults
    status: ErrorStatus = ErrorStatus.OPEN
    traceback: Optional[str] = None   # Full stack trace if available
    
    # Classification
    title: str = ""                   # Human-readable title
    explanation: str = ""             # What this error means
    likely_causes: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)
    
    # Remediation
    can_auto_fix: bool = False
    available_fixes: List[ErrorAction] = field(default_factory=list)
    
    # Tracking
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    occurrence_count: int = 1
    
    # Context
    context: Dict[str, Any] = field(default_factory=dict)  # Bot state, params, etc.
    links: List[Dict[str, str]] = field(default_factory=list)  # Docs, logs, etc.
    
    # Metadata
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            'id': self.id,
            'code': self.code,
            'source': self.source.value,
            'severity': self.severity.value,
            'status': self.status.value,
            'message_raw': self.message_raw,
            'traceback': self.traceback,
            'title': self.title,
            'explanation': self.explanation,
            'likely_causes': self.likely_causes,
            'suggested_actions': self.suggested_actions,
            'can_auto_fix': self.can_auto_fix,
            'available_fixes': [f.to_dict() for f in self.available_fixes],
            'first_seen': self.first_seen.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'occurrence_count': self.occurrence_count,
            'context': self.context,
            'links': self.links,
            'acknowledged_by': self.acknowledged_by,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_notes': self.resolution_notes
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ErrorEvent':
        """Create from dict"""
        # Convert string enums back
        data['source'] = ErrorSource(data['source'])
        data['severity'] = ErrorSeverity(data['severity'])
        data['status'] = ErrorStatus(data['status'])
        
        # Convert datetime strings back
        data['first_seen'] = datetime.fromisoformat(data['first_seen'])
        data['last_seen'] = datetime.fromisoformat(data['last_seen'])
        if data.get('acknowledged_at'):
            data['acknowledged_at'] = datetime.fromisoformat(data['acknowledged_at'])
        if data.get('resolved_at'):
            data['resolved_at'] = datetime.fromisoformat(data['resolved_at'])
        
        # Convert fix dicts back to ErrorAction objects
        if 'available_fixes' in data:
            data['available_fixes'] = [
                ErrorAction(**fix) if isinstance(fix, dict) else fix
                for fix in data['available_fixes']
            ]
        
        return cls(**data)
    
    def merge_occurrence(self) -> None:
        """Update for a duplicate occurrence"""
        self.last_seen = datetime.utcnow()
        self.occurrence_count += 1
    
    def get_signature(self) -> str:
        """Get unique signature for deduplication"""
        # Combine source, code, and normalized message
        normalized_msg = self.message_raw[:100].lower().strip()
        return f"{self.source.value}:{self.code}:{hash(normalized_msg)}"
