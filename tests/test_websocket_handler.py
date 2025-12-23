"""
Tests for WebSocketHandler Module

Tests WebSocket event routing logic extracted from GridBot.
"""

import pytest
from unittest.mock import Mock, MagicMock
from bot.strategy.modules.websocket_handler import WebSocketHandler


class TestWebSocketHandler:
    """Test suite for WebSocketHandler event routing module"""
    
    def test_initialization(self):
        """Test handler initializes correctly"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        assert handler.ws_manager is ws_manager
        assert handler.liquidation_monitor is None
    
    def test_initialization_with_liquidation_monitor(self):
        """Test handler initializes with liquidation monitor"""
        ws_manager = Mock()
        liq_monitor = Mock()
        handler = WebSocketHandler(ws_manager, liquidation_monitor=liq_monitor)
        assert handler.liquidation_monitor is liq_monitor
    
    def test_setup_callbacks(self):
        """Test callback registration"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        
        # Create mock callbacks
        price_cb = Mock()
        fill_cb = Mock()
        
        # Setup callbacks
        handler.setup_callbacks(
            on_price_update=price_cb,
            on_fill=fill_cb
        )
        
        # Verify WebSocket manager methods called
        ws_manager.on_price_update.assert_called_once()
        ws_manager.on_fill.assert_called_once()
    
    def test_setup_callbacks_with_optional(self):
        """Test callback registration with optional callbacks"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        
        # Create mock callbacks
        price_cb = Mock()
        fill_cb = Mock()
        order_cb = Mock()
        position_cb = Mock()
        
        # Setup callbacks with optional ones
        handler.setup_callbacks(
            on_price_update=price_cb,
            on_fill=fill_cb,
            on_order_update=order_cb,
            on_position_update=position_cb
        )
        
        # Verify all callbacks registered
        ws_manager.on_price_update.assert_called_once()
        ws_manager.on_fill.assert_called_once()
        ws_manager.on_order_update.assert_called_once()
        ws_manager.on_position_update.assert_called_once()
    
    def test_price_update_routing(self):
        """Test price update events are routed correctly"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        
        # Create mock callback
        price_cb = Mock()
        handler.setup_callbacks(on_price_update=price_cb, on_fill=Mock())
        
        # Simulate price update
        ticker_data = {'last': 110000, 'bid': 109999, 'ask': 110001}
        handler._handle_price_update(ticker_data)
        
        # Verify callback was called with correct data
        price_cb.assert_called_once_with(ticker_data)
    
    def test_fill_routing(self):
        """Test fill events are routed correctly"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        
        # Create mock callback
        fill_cb = Mock()
        handler.setup_callbacks(on_price_update=Mock(), on_fill=fill_cb)
        
        # Simulate fill
        fill_data = {
            'order_id': '12345',
            'fill_price': 110000,
            'fill_size': 1,
            'side': 'buy'
        }
        handler._handle_fill(fill_data)
        
        # Verify callback was called with correct data
        fill_cb.assert_called_once_with(fill_data)
    
    def test_order_update_routing(self):
        """Test order update events are routed correctly"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        
        # Create mock callback
        order_cb = Mock()
        handler.setup_callbacks(
            on_price_update=Mock(),
            on_fill=Mock(),
            on_order_update=order_cb
        )
        
        # Simulate order update
        order_data = {'id': '12345', 'state': 'filled', 'side': 'buy'}
        handler._handle_order_update(order_data)
        
        # Verify callback was called
        order_cb.assert_called_once_with(order_data)
    
    def test_position_update_routing(self):
        """Test position update events are routed correctly"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        
        # Create mock callback
        position_cb = Mock()
        handler.setup_callbacks(
            on_price_update=Mock(),
            on_fill=Mock(),
            on_position_update=position_cb
        )
        
        # Simulate position update
        position_data = {
            'symbol': 'BTCUSD',
            'size': 1,
            'entry_price': 110000,
            'unrealized_pnl': 500
        }
        handler._handle_position_update(position_data)
        
        # Verify callback was called
        position_cb.assert_called_once_with(position_data)
    
    def test_liquidation_alert_with_callback(self):
        """Test liquidation alert routing with registered callback"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        
        # Create mock callback
        liq_cb = Mock()
        handler.setup_callbacks(
            on_price_update=Mock(),
            on_fill=Mock(),
            on_liquidation=liq_cb
        )
        
        # Simulate liquidation alert
        handler.handle_liquidation_alert(
            'CRITICAL',
            'Liquidation risk high',
            {'margin_util': 85}
        )
        
        # Verify callback was called
        liq_cb.assert_called_once_with(
            'CRITICAL',
            'Liquidation risk high',
            {'margin_util': 85}
        )
    
    def test_liquidation_alert_without_callback(self):
        """Test liquidation alert default handling (logging)"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        
        # No liquidation callback registered
        handler.setup_callbacks(on_price_update=Mock(), on_fill=Mock())
        
        # Should not raise exception (logs by default)
        handler.handle_liquidation_alert('WARNING', 'Test warning', {})
    
    def test_emergency_alert_with_callback(self):
        """Test emergency alert routing with registered callback"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        
        # Create mock callback
        emergency_cb = Mock()
        handler.setup_callbacks(
            on_price_update=Mock(),
            on_fill=Mock(),
            on_emergency=emergency_cb
        )
        
        # Simulate emergency alert
        handler.handle_emergency_alert('Emergency!', {'critical': True})
        
        # Verify callback was called
        emergency_cb.assert_called_once_with('Emergency!', {'critical': True})
    
    def test_price_update_error_handling(self):
        """Test error handling in price update callback"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        
        # Create callback that raises exception
        price_cb = Mock(side_effect=Exception("Test error"))
        handler.setup_callbacks(on_price_update=price_cb, on_fill=Mock())
        
        # Should not raise exception (error logged)
        handler._handle_price_update({'last': 110000})
    
    def test_fill_error_handling(self):
        """Test error handling in fill callback"""
        ws_manager = Mock()
        handler = WebSocketHandler(ws_manager)
        
        # Create callback that raises exception
        fill_cb = Mock(side_effect=Exception("Test error"))
        handler.setup_callbacks(on_price_update=Mock(), on_fill=fill_cb)
        
        # Should not raise exception (error logged)
        handler._handle_fill({'order_id': '123', 'fill_price': 110000})
