"""
Guardian Bot - SQL-Based Risk Monitoring System

CLEAN ARCHITECTURE - Single Source of Truth:
├── collectors/     → Data gathering (NO decisions)
│   ├── position_monitor.py
│   └── health_tracker.py
│
├── engine/         → Decision making (SINGLE source of truth)
│   └── risk_decision_engine.py
│
└── core/           → Orchestration (NO risk logic)
    └── guardian_bot.py

Version: 2.0 (SQL-based)
"""

__version__ = "2.0.0"
__author__ = "GridBot Pro"

from .core import GuardianBot
from .collectors import PositionMonitor, HealthTracker
from .engine import GuardianRiskDecisionEngine

__all__ = [
    'GuardianBot',
    'PositionMonitor',
    'HealthTracker',
    'GuardianRiskDecisionEngine',
]

