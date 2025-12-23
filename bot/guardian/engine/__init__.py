"""
Guardian Decision Engine

SINGLE source of truth for all risk decisions.
Reads data from collectors and publishes GO/STOP signals to SQL database.
"""

from .risk_decision_engine import GuardianRiskDecisionEngine

__all__ = [
    'GuardianRiskDecisionEngine',
]
