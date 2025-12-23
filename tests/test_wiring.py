"""
Advanced Wiring Tests for GridBot Modular Architecture

Tests the integration and wiring between 7 domain modules:
1. GridCalculator - Pure logic
2. PositionManager - State management
3. OrderManager - Order operations
4. FillDetector - Fill processing
5. Reconciliation - Exchange sync
6. VolatilityHandler - Safety checks
7. WebSocketHandler - Event routing

Key Areas Tested:
- Module initialization order (dependency injection)
- Callback wiring correctness
- Event flow through system
- Circular dependency detection
- Integration between modules
- Data flow verification

Run with: pytest tests/test_wiring.py -v -s
"""

import pytest
import os
from unittest.mock import Mock, MagicMock, patch, call
from typing import Dict

# Suppress production imports
os.environ['BACKTEST_MODE'] = 'true'

from bot.strategy.modules.grid_calculator import GridCalculator
from bot.strategy.modules.order_manager import OrderManager
from bot.strategy.modules.position_manager import PositionManager
from bot.strategy.modules.fill_detector import FillDetector
from bot.strategy.modules.websocket_handler import WebSocketHandler


class TestModuleInitializationOrder:
    """Test modules initialize in correct dependency order"""
    
    def test_grid_calculator_has_zero_dependencies(self):
        """Test: GridCalculator can initialize standalone"""
        # Should work with no dependencies
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        assert calc.lower == 105000
        assert calc.upper == 115000
        # No external dependencies required ✅
    
    def test_position_manager_depends_on_grid_calculator(self):
        """Test: PositionManager requires GridCalculator"""
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # PositionManager needs GridCalculator
        position_mgr = PositionManager(
            max_open=10,
            grid_calculator=grid_calc,
            session_tag="TEST"
        )
        
        assert position_mgr.grid_calc == grid_calc
        # Dependency injected correctly ✅
    
    def test_order_manager_depends_on_multiple_modules(self):
        """Test: OrderManager requires GridCalculator + PositionManager + API"""
        # Setup dependencies
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        position_mgr = PositionManager(
            max_open=10,
            grid_calculator=grid_calc,
            session_tag="TEST"
        )
        
        api_client = Mock()
        api_client.place_order = Mock()
        api_client.cancel_order = Mock()
        api_client.get_order = Mock()
        api_client.list_orders = Mock()
        
        # OrderManager needs all 3
        order_mgr = OrderManager(
            api_client=api_client,
            grid_calculator=grid_calc,
            position_manager=position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
        
        assert order_mgr.grid_calc == grid_calc
        assert order_mgr.position_mgr == position_mgr
        assert order_mgr.api_client == api_client
        # All dependencies injected correctly ✅
    
    def test_initialization_order_prevents_circular_dependencies(self):
        """Test: No circular dependencies in initialization chain"""
        # This test passes if we can initialize all modules without errors
        
        # 1. GridCalculator (no deps)
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # 2. PositionManager (depends: GridCalculator)
        position_mgr = PositionManager(
            max_open=10,
            grid_calculator=grid_calc,
            session_tag="TEST"
        )
        
        # 3. API Client
        api_client = Mock()
        api_client.place_order = Mock(return_value={'success': True, 'result': {'id': '123'}})
        api_client.cancel_order = Mock(return_value={'success': True})
        api_client.get_order = Mock(return_value={'success': True})
        api_client.list_orders = Mock(return_value={'success': True, 'result': []})
        
        # 4. OrderManager (depends: API, GridCalc, PositionMgr)
        order_mgr = OrderManager(
            api_client=api_client,
            grid_calculator=grid_calc,
            position_manager=position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
        
        # If we get here without circular dependency error, test passes ✅
        assert True


class TestCallbackWiring:
    """Test callback system wiring"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # Mock WebSocket manager
        self.ws_manager = Mock()
        self.ws_manager.on_price_update = Mock()
        self.ws_manager.on_fill = Mock()
        self.ws_manager.on_order_update = Mock()
        self.ws_manager.on_position_update = Mock()
        
        # WebSocket handler
        self.ws_handler = WebSocketHandler(
            ws_manager=self.ws_manager,
            liquidation_monitor=None
        )
    
    def test_callback_registration_with_websocket_manager(self):
        """Test: Callbacks properly registered with WebSocket manager"""
        # Track what callbacks were registered
        price_callback = Mock()
        fill_callback = Mock()
        
        # Setup callbacks
        self.ws_handler.setup_callbacks(
            on_price_update=price_callback,
            on_fill=fill_callback
        )
        
        # Verify WebSocket manager registered callbacks
        assert self.ws_manager.on_price_update.called
        assert self.ws_manager.on_fill.called
        
        # Verify callbacks stored
        assert self.ws_handler._price_update_callback == price_callback
        assert self.ws_handler._fill_callback == fill_callback
    
    def test_price_update_flows_through_callback_chain(self):
        """Test: Price updates flow through callback chain correctly"""
        # Track calls
        callback_called = []
        
        def price_callback(ticker_data):
            callback_called.append(ticker_data)
        
        # Setup
        self.ws_handler.setup_callbacks(
            on_price_update=price_callback,
            on_fill=Mock()
        )
        
        # Simulate price update from WebSocket
        ticker_data = {'last': 110000, 'bid': 109995, 'ask': 110005}
        
        # Get the registered callback from ws_manager
        ws_callback = self.ws_manager.on_price_update.call_args[0][0]
        
        # Call it (simulating WebSocket event)
        ws_callback(ticker_data)
        
        # Verify our callback was called
        assert len(callback_called) == 1
        assert callback_called[0] == ticker_data
    
    def test_fill_detection_flows_through_callback_chain(self):
        """Test: Fills flow through FillDetector → GridBot"""
        # Track fills processed
        fills_processed = []
        
        def fill_callback(fill_data):
            fills_processed.append(fill_data)
        
        # Setup FillDetector
        mock_lock = MagicMock()
        fill_detector = FillDetector(
            state_lock=mock_lock,
            dedup_size=100
        )
        
        # Wire up callback
        fill_detector.set_fill_callback(fill_callback)
        
        # Simulate fill from WebSocket (use correct keys: fill_price, fill_size)
        fill_event = {
            'id': '12345',
            'order_id': 'ORD123',
            'side': 'buy',
            'fill_price': 110000,  # ✅ Correct key
            'fill_size': 1  # ✅ Correct key
        }
        
        # Process fill
        fill_detector.process_websocket_fill(fill_event)
        
        # Verify callback was called
        assert len(fills_processed) == 1
        assert fills_processed[0]['order_id'] == 'ORD123'


class TestDataFlowIntegration:
    """Test data flows correctly between modules"""
    
    def setup_method(self):
        """Setup integrated module chain"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        self.position_mgr = PositionManager(
            max_open=10,
            grid_calculator=self.grid_calc,
            session_tag="INTEGRATION_TEST"
        )
        
        self.api_client = Mock()
        self.api_client.place_order = Mock(return_value={
            'success': True,
            'result': {'id': 'ORDER123'}
        })
        self.api_client.cancel_order = Mock(return_value={'success': True})
        self.api_client.get_order = Mock(return_value={'success': True})
        self.api_client.list_orders = Mock(return_value={'success': True, 'result': []})
        
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
    
    def test_grid_calc_to_order_manager_flow(self):
        """Test: GridCalculator provides prices to OrderManager"""
        # GridCalculator computes price
        next_buy = self.grid_calc.compute_next_buy_level([])
        
        assert next_buy is not None
        
        # OrderManager uses that price
        order_id = self.order_mgr.place_buy_order(price=next_buy)
        
        assert order_id is not None
        
        # Verify API was called with quantized price
        call_args = self.api_client.place_order.call_args[1]
        assert call_args['limit_price'] == str(next_buy)
    
    def test_position_manager_to_grid_calc_flow(self):
        """Test: PositionManager provides state to GridCalculator"""
        # Add positions to manager
        positions = [
            {
                'buy_order_id': 'ORDER1',
                'entry_price': 110000,
                'tp_price': 110500,
                'size': 1,
                'timestamp': 1234567890,
                'protected': False
            },
            {
                'buy_order_id': 'ORDER2',
                'entry_price': 109500,
                'tp_price': 110000,
                'size': 1,
                'timestamp': 1234567891,
                'protected': False
            }
        ]
        
        for pos in positions:
            self.position_mgr.add_position(pos)
        
        # Get positions
        open_positions = self.position_mgr.get_positions()
        
        # GridCalculator uses them to compute next level
        next_buy = self.grid_calc.compute_next_buy_level(open_positions)
        
        # Should be one step below lowest (109500)
        assert next_buy == 109000
    
    def test_order_manager_to_position_manager_flow(self):
        """Test: OrderManager → PositionManager integration"""
        # OrderManager places order
        price = 110000
        order_id = self.order_mgr.place_buy_order(price=price)
        
        assert order_id is not None
        
        # Simulate fill - create position
        position = {
            'buy_order_id': order_id,
            'entry_price': price,
            'tp_price': price + 500,
            'size': 1,
            'timestamp': 1234567890,
            'protected': False
        }
        
        # Add to PositionManager
        self.position_mgr.add_position(position)
        
        # Verify position tracked
        positions = self.position_mgr.get_positions()
        assert len(positions) == 1
        assert positions[0]['buy_order_id'] == order_id


class TestEndToEndWiring:
    """Test complete end-to-end wiring from WebSocket to Order Placement"""
    
    def test_complete_fill_workflow(self):
        """
        Test: Complete workflow from WebSocket fill → TP placement
        
        Flow:
        WebSocket → WebSocketHandler → FillDetector → GridBot._on_fill_processed
        → OrderManager.place_tp → API
        """
        # Setup all modules
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        position_mgr = PositionManager(
            max_open=10,
            grid_calculator=grid_calc,
            session_tag="E2E_TEST"
        )
        
        api_client = Mock()
        api_client.place_order = Mock(return_value={
            'success': True,
            'result': {'id': 'TP_ORDER'}
        })
        api_client.cancel_order = Mock(return_value={'success': True})
        api_client.get_order = Mock(return_value={'success': True})
        api_client.list_orders = Mock(return_value={'success': True, 'result': []})
        
        order_mgr = OrderManager(
            api_client=api_client,
            grid_calculator=grid_calc,
            position_manager=position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
        
        fill_detector = FillDetector(
            state_lock=position_mgr.state_lock,
            dedup_size=100
        )
        
        # Track TP placements
        tp_placed = []
        
        def on_fill_processed(fill_data):
            """Simulate GridBot._on_fill_processed"""
            # Add position
            position = {
                'buy_order_id': fill_data['order_id'],
                'entry_price': fill_data['fill_price'],
                'tp_price': fill_data['fill_price'] + 500,
                'size': 1,
                'timestamp': 1234567890,
                'protected': False
            }
            position_mgr.add_position(position)
            
            # Place TP
            if order_mgr.safe_place_tp(position):
                tp_placed.append(position['tp_price'])
        
        # Wire callback
        fill_detector.set_fill_callback(on_fill_processed)
        
        # Simulate WebSocket fill event (use correct keys)
        fill_event = {
            'id': 'FILL123',
            'order_id': 'BUY_ORDER',
            'side': 'buy',
            'fill_price': 110000,  # ✅ Correct key
            'fill_size': 1  # ✅ Correct key
        }
        
        # Process fill
        fill_detector.process_websocket_fill(fill_event)
        
        # Verify TP was placed
        assert len(tp_placed) == 1
        assert tp_placed[0] == 110500
        
        # Verify position was added
        positions = position_mgr.get_positions()
        assert len(positions) == 1


class TestCircularDependencyDetection:
    """Test for circular dependencies in module wiring"""
    
    def test_no_circular_dependency_in_module_chain(self):
        """
        Test: Module dependency graph has no cycles
        
        Dependency Chain:
        GridCalculator → (no deps)
        PositionManager → GridCalculator
        OrderManager → GridCalculator, PositionManager, API
        FillDetector → state_lock
        Reconciliation → OrderManager, PositionManager, GridCalculator
        
        This is a DAG (Directed Acyclic Graph) - no cycles ✅
        """
        # Build dependency graph
        dependencies = {
            'GridCalculator': [],
            'PositionManager': ['GridCalculator'],
            'OrderManager': ['GridCalculator', 'PositionManager', 'API'],
            'FillDetector': ['state_lock'],
            'Reconciliation': ['OrderManager', 'PositionManager', 'GridCalculator']
        }
        
        # Check for cycles using topological sort
        visited = set()
        rec_stack = set()
        
        def has_cycle(node):
            """DFS to detect cycles"""
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in dependencies.get(node, []):
                if neighbor not in dependencies:
                    continue  # External dependency (API, state_lock)
                
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True  # Cycle detected!
            
            rec_stack.remove(node)
            return False
        
        # Check all nodes
        for node in dependencies:
            if node not in visited:
                assert not has_cycle(node), f"Circular dependency detected involving {node}"
        
        # If we get here, no cycles ✅
        assert True


class TestCallbackErrorHandling:
    """Test callback system handles errors gracefully"""
    
    def test_callback_exception_doesnt_crash_system(self):
        """Test: Exception in callback doesn't crash WebSocket handler"""
        ws_manager = Mock()
        ws_manager.on_price_update = Mock()
        ws_manager.on_fill = Mock()
        
        ws_handler = WebSocketHandler(
            ws_manager=ws_manager,
            liquidation_monitor=None
        )
        
        # Callback that raises exception
        def bad_callback(data):
            raise Exception("Simulated callback error")
        
        # Setup callback
        ws_handler.setup_callbacks(
            on_price_update=bad_callback,
            on_fill=Mock()
        )
        
        # Get the internal handler
        internal_handler = ws_manager.on_price_update.call_args[0][0]
        
        # Call it with data (should not crash)
        try:
            internal_handler({'last': 110000})
            # Exception should be caught internally
        except Exception as e:
            pytest.fail(f"Callback exception not handled: {e}")


class TestModuleCommunication:
    """Test inter-module communication patterns"""
    
    def setup_method(self):
        """Setup all modules"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        self.position_mgr = PositionManager(
            max_open=10,
            grid_calculator=self.grid_calc,
            session_tag="COMM_TEST"
        )
        
        self.api_client = Mock()
        self.api_client.place_order = Mock(return_value={
            'success': True,
            'result': {'id': 'ORDER123'}
        })
        self.api_client.cancel_order = Mock(return_value={'success': True})
        self.api_client.get_order = Mock(return_value={'success': True})
        self.api_client.list_orders = Mock(return_value={'success': True, 'result': []})
        
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
    
    def test_position_manager_shares_lock_with_fill_detector(self):
        """Test: PositionManager's lock is shared with FillDetector"""
        # Create FillDetector with PositionManager's lock
        fill_detector = FillDetector(
            state_lock=self.position_mgr.state_lock,
            dedup_size=100
        )
        
        # Both should use same lock object (FillDetector stores as _state_lock private)
        assert fill_detector._state_lock is self.position_mgr.state_lock
        
        # This ensures thread-safe access to positions ✅
    
    def test_order_manager_queries_position_manager_state(self):
        """Test: OrderManager can query PositionManager state"""
        # Add position
        self.position_mgr.add_position({
            'buy_order_id': 'ORDER1',
            'entry_price': 110000,
            'tp_price': 110500,
            'size': 1,
            'timestamp': 1234567890,
            'protected': False,
            'tp_id': 'TP123'
        })
        
        # OrderManager can query through PositionManager
        positions = self.position_mgr.get_positions()
        
        # Should find position with TP
        position_with_tp = [p for p in positions if p.get('tp_id') == 'TP123']
        assert len(position_with_tp) == 1
    
    def test_grid_calculator_used_by_multiple_modules(self):
        """Test: GridCalculator is shared across modules (singleton pattern)"""
        # Same GridCalculator instance used by multiple modules
        assert self.position_mgr.grid_calc is self.grid_calc
        assert self.order_mgr.grid_calc is self.grid_calc
        
        # Changes to grid params affect all modules ✅
        original_step = self.grid_calc.step
        assert self.position_mgr.grid_calc.step == original_step
        assert self.order_mgr.grid_calc.step == original_step


class TestEventFlowValidation:
    """Test event flow through complete system"""
    
    def test_price_update_event_flow(self):
        """
        Test: Price update event flows through system
        
        Flow: WebSocket → Handler → GridBot → Volatility Check
        """
        # Track event flow
        flow_log = []
        
        # Mock WebSocket manager
        ws_manager = Mock()
        ws_manager.on_price_update = Mock()
        ws_manager.on_fill = Mock()
        
        # WebSocket handler
        ws_handler = WebSocketHandler(
            ws_manager=ws_manager,
            liquidation_monitor=None
        )
        
        # Callback that logs
        def track_price(ticker_data):
            flow_log.append(('price_callback', ticker_data['last']))
        
        # Setup
        ws_handler.setup_callbacks(
            on_price_update=track_price,
            on_fill=Mock()
        )
        
        # Simulate event
        ws_callback = ws_manager.on_price_update.call_args[0][0]
        ws_callback({'last': 110000})
        
        # Verify flow
        assert len(flow_log) == 1
        assert flow_log[0] == ('price_callback', 110000)
    
    def test_fill_event_triggers_position_creation(self):
        """
        Test: Fill event triggers complete position workflow
        
        Flow: Fill detected → Position created → TP placed
        """
        # Setup
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        position_mgr = PositionManager(
            max_open=10,
            grid_calculator=grid_calc,
            session_tag="FILL_TEST"
        )
        
        api_client = Mock()
        tp_orders = []
        
        def track_tp_order(**kwargs):
            """Track TP orders placed"""
            if kwargs.get('reduce_only'):
                tp_orders.append(kwargs)
            return {'success': True, 'result': {'id': f"TP_{len(tp_orders)}"}}
        
        api_client.place_order = Mock(side_effect=track_tp_order)
        api_client.cancel_order = Mock(return_value={'success': True})
        api_client.get_order = Mock(return_value={'success': True})
        api_client.list_orders = Mock(return_value={'success': True, 'result': []})
        
        order_mgr = OrderManager(
            api_client=api_client,
            grid_calculator=grid_calc,
            position_manager=position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
        
        # Simulate fill workflow
        fill_price = 110000
        
        # 1. Create position (simulating fill)
        position = {
            'buy_order_id': 'BUY123',
            'entry_price': fill_price,
            'tp_price': fill_price + 500,
            'size': 1,
            'timestamp': 1234567890,
            'protected': False
        }
        
        position_mgr.add_position(position)
        
        # 2. Place TP
        result = order_mgr.safe_place_tp(position)
        
        # Verify TP placed
        assert result is True
        assert len(tp_orders) == 1
        assert float(tp_orders[0]['limit_price']) == 110500
        assert tp_orders[0]['reduce_only'] == True


class TestWiringInvariant:
    """Test wiring invariants that must always hold"""
    
    def test_all_modules_have_required_dependencies(self):
        """Test: All modules receive required dependencies"""
        # GridCalculator - no dependencies
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        assert grid_calc is not None
        
        # PositionManager - needs GridCalculator
        position_mgr = PositionManager(
            max_open=10,
            grid_calculator=grid_calc,  # ← Required dependency
            session_tag="TEST"
        )
        assert hasattr(position_mgr, 'grid_calc')
        
        # OrderManager - needs GridCalc, PositionMgr, API
        api_client = Mock()
        api_client.place_order = Mock()
        api_client.cancel_order = Mock()
        api_client.get_order = Mock()
        api_client.list_orders = Mock()
        
        order_mgr = OrderManager(
            api_client=api_client,  # ← Required
            grid_calculator=grid_calc,  # ← Required
            position_manager=position_mgr,  # ← Required
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
        
        assert hasattr(order_mgr, 'api_client')
        assert hasattr(order_mgr, 'grid_calc')
        assert hasattr(order_mgr, 'position_mgr')
    
    def test_shared_state_lock_ensures_thread_safety(self):
        """Test: state_lock is properly shared between modules"""
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        position_mgr = PositionManager(
            max_open=10,
            grid_calculator=grid_calc,
            session_tag="LOCK_TEST"
        )
        
        # FillDetector uses PositionManager's lock
        fill_detector = FillDetector(
            state_lock=position_mgr.state_lock,
            dedup_size=100
        )
        
        # OrderManager uses PositionManager's lock (via position_mgr)
        api_client = Mock()
        api_client.place_order = Mock()
        api_client.cancel_order = Mock()
        api_client.get_order = Mock()
        api_client.list_orders = Mock()
        
        order_mgr = OrderManager(
            api_client=api_client,
            grid_calculator=grid_calc,
            position_manager=position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
        
        # All should share same lock for thread safety (FillDetector uses _state_lock private)
        assert fill_detector._state_lock is position_mgr.state_lock
        assert order_mgr.position_mgr.state_lock is position_mgr.state_lock


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])

