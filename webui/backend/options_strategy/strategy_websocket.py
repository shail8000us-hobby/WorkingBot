"""
Strategy WebSocket Events
=========================
WebSocket/SocketIO handlers for real-time strategy updates.

Events emitted:
- strategy_created     - New strategy created
- strategy_executed    - Strategy executed
- strategy_pnl_update  - P&L changes
- strategy_closed      - Strategy closed
- strategy_warning     - Exit condition warning
- strategy_error       - Error condition
- strategy_notification - General notification

Created: January 5, 2026
Phase 3: Automation & Monitoring
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

log = logging.getLogger(__name__)


class StrategyWebSocketHandler:
    """
    WebSocket handler for strategy real-time updates
    
    Integrates with:
    - StrategyMonitor (exit condition events)
    - StrategyNotificationService (notification events)
    - StrategyManager (CRUD events)
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        
        self._socketio = None
        self._connected_clients = set()
        self._subscriptions: Dict[str, set] = {}  # strategy_id -> client sids
        
        self._initialized = True
        log.info("📡 StrategyWebSocketHandler initialized")
    
    def init_socketio(self, socketio):
        """
        Initialize with Flask-SocketIO instance
        
        Call this from app.py after creating socketio
        """
        self._socketio = socketio
        
        # Register handlers
        socketio.on_event('connect', self._on_connect, namespace='/strategy')
        socketio.on_event('disconnect', self._on_disconnect, namespace='/strategy')
        socketio.on_event('subscribe', self._on_subscribe, namespace='/strategy')
        socketio.on_event('unsubscribe', self._on_unsubscribe, namespace='/strategy')
        socketio.on_event('request_pnl', self._on_request_pnl, namespace='/strategy')
        
        # Register with services
        self._register_with_services()
        
        log.info("✅ SocketIO handlers registered for /strategy namespace")
    
    def _register_with_services(self):
        """Register as event handler with strategy services"""
        try:
            # Register with monitor
            from .strategy_monitor import get_strategy_monitor
            monitor = get_strategy_monitor()
            monitor.register_callback(self._on_monitor_event)
            log.info("  Registered with StrategyMonitor")
        except Exception as e:
            log.warning(f"  Could not register with monitor: {e}")
        
        try:
            # Register with notification service
            from .strategy_notifications import get_notification_service
            notif_service = get_notification_service()
            notif_service.register_websocket_handler(self._on_notification_event)
            log.info("  Registered with NotificationService")
        except Exception as e:
            log.warning(f"  Could not register with notifications: {e}")
    
    # ==================== Socket Event Handlers ====================
    
    def _on_connect(self):
        """Handle client connection"""
        from flask import request
        sid = request.sid
        self._connected_clients.add(sid)
        log.info(f"🔌 Strategy client connected: {sid}")
        
        # Send welcome message
        if self._socketio:
            self._socketio.emit(
                'connected',
                {'message': 'Connected to strategy updates', 'sid': sid},
                room=sid,
                namespace='/strategy'
            )
    
    def _on_disconnect(self):
        """Handle client disconnection"""
        from flask import request
        sid = request.sid
        self._connected_clients.discard(sid)
        
        # Remove from all subscriptions
        for strategy_id in list(self._subscriptions.keys()):
            self._subscriptions[strategy_id].discard(sid)
            if not self._subscriptions[strategy_id]:
                del self._subscriptions[strategy_id]
        
        log.info(f"🔌 Strategy client disconnected: {sid}")
    
    def _on_subscribe(self, data: Dict):
        """Subscribe to strategy updates"""
        from flask import request
        sid = request.sid
        strategy_id = data.get('strategy_id')
        
        if not strategy_id:
            return {'error': 'strategy_id required'}
        
        if strategy_id not in self._subscriptions:
            self._subscriptions[strategy_id] = set()
        
        self._subscriptions[strategy_id].add(sid)
        log.debug(f"Client {sid} subscribed to {strategy_id}")
        
        return {'subscribed': True, 'strategy_id': strategy_id}
    
    def _on_unsubscribe(self, data: Dict):
        """Unsubscribe from strategy updates"""
        from flask import request
        sid = request.sid
        strategy_id = data.get('strategy_id')
        
        if strategy_id and strategy_id in self._subscriptions:
            self._subscriptions[strategy_id].discard(sid)
        
        return {'unsubscribed': True, 'strategy_id': strategy_id}
    
    def _on_request_pnl(self, data: Dict):
        """Handle P&L request"""
        from flask import request
        sid = request.sid
        strategy_id = data.get('strategy_id')
        
        if not strategy_id:
            return {'error': 'strategy_id required'}
        
        try:
            from .strategy_manager import StrategyManager
            import asyncio
            
            manager = StrategyManager()
            
            # Run async in sync context
            loop = asyncio.new_event_loop()
            pnl_result = loop.run_until_complete(
                manager.calculate_strategy_pnl(strategy_id)
            )
            loop.close()
            
            return pnl_result
            
        except Exception as e:
            return {'error': str(e)}
    
    # ==================== Service Event Handlers ====================
    
    def _on_monitor_event(self, event_data: Dict):
        """Handle events from StrategyMonitor"""
        event_type = event_data.get('event')
        strategy_id = event_data.get('strategy_id')
        
        # Map monitor events to WebSocket events
        ws_event = {
            'pnl_updated': 'strategy_pnl_update',
            'exit_condition_warning': 'strategy_warning',
            'strategy_closed': 'strategy_closed',
            'strategy_error': 'strategy_error'
        }.get(event_type, 'strategy_update')
        
        self._emit_strategy_event(ws_event, strategy_id, event_data)
    
    def _on_notification_event(self, notification_data: Dict):
        """Handle events from NotificationService"""
        notification = notification_data.get('notification', {})
        strategy_id = notification.get('strategy_id')
        
        self._emit_strategy_event('strategy_notification', strategy_id, notification)
    
    # ==================== Emit Methods ====================
    
    def _emit_strategy_event(self, event: str, strategy_id: Optional[str], data: Dict):
        """Emit event to subscribed clients"""
        if not self._socketio:
            log.warning("SocketIO not initialized, cannot emit")
            return
        
        payload = {
            'event': event,
            'strategy_id': strategy_id,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        
        # Send to subscribed clients
        if strategy_id and strategy_id in self._subscriptions:
            for sid in self._subscriptions[strategy_id]:
                try:
                    self._socketio.emit(
                        event,
                        payload,
                        room=sid,
                        namespace='/strategy'
                    )
                except Exception as e:
                    log.error(f"Failed to emit to {sid}: {e}")
        
        # Also broadcast to all connected clients for general events
        if event in ('strategy_notification', 'strategy_closed'):
            try:
                self._socketio.emit(
                    event,
                    payload,
                    namespace='/strategy'
                )
            except Exception as e:
                log.error(f"Failed to broadcast {event}: {e}")
    
    def emit_strategy_created(self, strategy_id: str, strategy_data: Dict):
        """Emit strategy created event"""
        self._emit_strategy_event('strategy_created', strategy_id, strategy_data)
    
    def emit_strategy_executed(self, strategy_id: str, execution_data: Dict):
        """Emit strategy executed event"""
        self._emit_strategy_event('strategy_executed', strategy_id, execution_data)
    
    def emit_pnl_update(self, strategy_id: str, pnl_data: Dict):
        """Emit P&L update event"""
        self._emit_strategy_event('strategy_pnl_update', strategy_id, pnl_data)
    
    def emit_strategy_closed(self, strategy_id: str, close_data: Dict):
        """Emit strategy closed event"""
        self._emit_strategy_event('strategy_closed', strategy_id, close_data)
    
    def emit_warning(self, strategy_id: str, warning_data: Dict):
        """Emit warning event"""
        self._emit_strategy_event('strategy_warning', strategy_id, warning_data)
    
    def emit_error(self, strategy_id: str, error_data: Dict):
        """Emit error event"""
        self._emit_strategy_event('strategy_error', strategy_id, error_data)
    
    # ==================== Status ====================
    
    def get_status(self) -> Dict:
        """Get WebSocket handler status"""
        return {
            'initialized': self._socketio is not None,
            'connected_clients': len(self._connected_clients),
            'subscriptions': {
                strategy_id: len(sids) 
                for strategy_id, sids in self._subscriptions.items()
            }
        }


# Global instance
_websocket_handler: Optional[StrategyWebSocketHandler] = None


def get_strategy_websocket_handler() -> StrategyWebSocketHandler:
    """Get singleton WebSocket handler"""
    global _websocket_handler
    if _websocket_handler is None:
        _websocket_handler = StrategyWebSocketHandler()
    return _websocket_handler


def init_strategy_websocket(socketio):
    """Initialize strategy WebSocket handlers with SocketIO instance"""
    handler = get_strategy_websocket_handler()
    handler.init_socketio(socketio)
    return handler
