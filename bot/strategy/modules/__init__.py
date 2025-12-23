"""
GridBot Modules - Async Actor Architecture

Core modules for AsyncGridBot:
- event_store: SQL-based event sourcing
- grid_calculator: Grid level computation
- fill_detector: Order fill detection
- state_projector: Event replay and state reconstruction

Legacy modules (position_manager, order_manager, etc.) archived on 2025-11-14.
Functionality replaced by actors: PositionManagerActor, OrderManagerActor
"""

from .grid_calculator import GridCalculator
from .fill_detector import FillDetector
from .event_store import EventStore, Event, EventType
from .state_projector import StateProjector

__all__ = [
    'GridCalculator',
    'FillDetector',
    'EventStore',
    'Event',
    'EventType',
    'StateProjector',
]
