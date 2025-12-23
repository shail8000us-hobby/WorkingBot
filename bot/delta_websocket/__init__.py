"""
Delta Exchange WebSocket Integration
Real-time market data and trading notifications

NOTE: This module was renamed from 'websocket' to 'delta_websocket' 
to avoid name collision with the external 'websocket-client' library.
"""

from .delta_ws import DeltaWebSocket
from .ws_manager import WebSocketManager

__all__ = ['DeltaWebSocket', 'WebSocketManager']

