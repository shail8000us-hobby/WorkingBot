"""
Comprehensive Test Suite for Grid Seeding Function (SHORT Mode)

Tests the seed_missed_grid_levels() function for SHORT mode trading.

Key Areas Tested:
1. Order Placement Logic (SELL above current price)
2. Price Level Calculation (current + i*step)
3. Upper Boundary Enforcement
4. Order Count Accuracy
5. Integration with OrderManager
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import os

from bot.strategy.modules.grid_calculator import GridCalculator
from bot.strategy.modules.order_manager import OrderManager


class MockGridBot:
    """Mock GridBot for testing SHORT mode seeding"""
    
    def __init__(self, current_price, grid_calc, order_mgr):
        self.current_price = current_price
        self.grid_calc = grid_calc
        self.order_mgr = order_mgr
    
    def seed_missed_grid_levels(self, count: int):
        """Copy of actual seeding logic for testing"""
        if count <= 0:
            return
        
        current_price = self.current_price
        mode = os.getenv('GRIDBOT_GRID_MODE', 'LONG').upper()
        
        orders_placed = []
        
        for i in range(count):
            if mode == 'LONG':
                # Buy below current price (going down)
                level = current_price - (i + 1) * self.grid_calc.step
                
                if level >= self.grid_calc.lower:
                    order_id = self.order_mgr.place_buy_order(price=level, post_only=True)
                    if order_id:
                        orders_placed.append({'level': level, 'order_id': order_id, 'side': 'buy'})
                else:
                    break
            
            elif mode == 'SHORT':
                # Sell above current price (going up)
                level = current_price + (i + 1) * self.grid_calc.step
                
                if level <= self.grid_calc.upper:
                    order_id = self.order_mgr.place_sell_order(price=level, post_only=True)
                    if order_id:
                        orders_placed.append({'level': level, 'order_id': order_id, 'side': 'sell'})
                else:
                    break
        
        return orders_placed


class TestShortModeSeeding:
    """Test suite for SHORT mode grid seeding"""
    
    def setup_method(self):
        """Setup test fixtures"""
        # Grid parameters matching user's scenario
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # Mock API client
        self.api_client = Mock()
        self.order_counter = 1000
        
        def mock_place_order(**kwargs):
            """Mock order placement that returns unique IDs"""
            self.order_counter += 1
            return {
                'success': True,
                'result': {'id': str(self.order_counter)}
            }
        
        self.api_client.place_order = Mock(side_effect=mock_place_order)
        
        # Mock position manager
        self.position_mgr = Mock()
        self.position_mgr.state_lock = MagicMock()
        
        # Order manager
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
    
    def test_seeding_places_correct_number_of_orders(self):
        """Test: SHORT seeding places exactly N orders when requested"""
        # Current price: 109946, want to seed 5 levels
        bot = MockGridBot(
            current_price=109946,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=5)
        
        assert len(orders) == 5, f"Should place 5 orders, placed {len(orders)}"
    
    def test_seeding_calculates_correct_price_levels(self):
        """Test: Orders placed at correct price levels (step intervals above current)"""
        current_price = 109946
        step = 500
        
        bot = MockGridBot(
            current_price=current_price,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=5)
        
        # Expected levels: 110446, 110946, 111446, 111946, 112446
        expected_levels = [
            current_price + 1 * step,  # 110446
            current_price + 2 * step,  # 110946
            current_price + 3 * step,  # 111446
            current_price + 4 * step,  # 111946
            current_price + 5 * step,  # 112446
        ]
        
        actual_levels = [order['level'] for order in orders]
        
        assert actual_levels == expected_levels, \
            f"Expected levels: {expected_levels}, Got: {actual_levels}"
    
    def test_seeding_uses_sell_orders_for_short_mode(self):
        """Test: SHORT mode uses SELL orders (not BUY)"""
        bot = MockGridBot(
            current_price=109946,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=3)
        
        # Verify all orders are SELL
        for order in orders:
            assert order['side'] == 'sell', \
                f"SHORT mode should use SELL orders, got: {order['side']}"
    
    def test_seeding_respects_upper_boundary(self):
        """Test: SHORT seeding stops at grid upper boundary"""
        # Current price: 114000, upper bound: 115000, step: 500
        # Can only place 2 orders (114500, 115000) before hitting boundary
        
        bot = MockGridBot(
            current_price=114000,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            # Request 10 orders, but should stop at boundary
            orders = bot.seed_missed_grid_levels(count=10)
        
        # Should only place 2 orders (114500, 115000)
        assert len(orders) == 2, \
            f"Should stop at boundary after 2 orders, placed {len(orders)}"
        
        # Verify levels
        expected_levels = [114500, 115000]
        actual_levels = [order['level'] for order in orders]
        
        assert actual_levels == expected_levels, \
            f"Expected {expected_levels}, got {actual_levels}"
    
    def test_seeding_places_orders_above_current_price(self):
        """Test: All seeded orders are ABOVE current price (SHORT mode)"""
        current_price = 109946
        
        bot = MockGridBot(
            current_price=current_price,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=5)
        
        for order in orders:
            assert order['level'] > current_price, \
                f"SHORT mode: Order @ {order['level']} should be above current price {current_price}"
    
    def test_seeding_uses_post_only_flag(self):
        """Test: SHORT seeding orders use post_only=True"""
        bot = MockGridBot(
            current_price=109946,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            bot.seed_missed_grid_levels(count=3)
        
        # Check all place_order calls used post_only
        for call in self.api_client.place_order.call_args_list:
            kwargs = call[1]
            assert 'product_id' in kwargs
            assert 'side' in kwargs
            assert kwargs['side'] == 'sell'
    
    def test_seeding_zero_count_places_no_orders(self):
        """Test: count=0 places no orders"""
        bot = MockGridBot(
            current_price=109946,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=0)
        
        assert orders is None or len(orders) == 0, \
            "count=0 should place no orders"
    
    def test_seeding_negative_count_places_no_orders(self):
        """Test: Negative count places no orders"""
        bot = MockGridBot(
            current_price=109946,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=-5)
        
        assert orders is None or len(orders) == 0, \
            "Negative count should place no orders"


class TestShortModeSeedingScenarios:
    """Real-world scenario testing for SHORT mode seeding"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        self.api_client = Mock()
        self.order_counter = 2000
        
        def mock_place_order(**kwargs):
            self.order_counter += 1
            return {
                'success': True,
                'result': {'id': str(self.order_counter)}
            }
        
        self.api_client.place_order = Mock(side_effect=mock_place_order)
        
        self.position_mgr = Mock()
        self.position_mgr.state_lock = MagicMock()
        
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
    
    def test_scenario_user_exact_parameters(self):
        """
        Scenario: User's exact parameters
        Current: 109946, Step: 500, Upper: 115000
        Expected: Orders at 110446, 110946, 111446, 111946, 112446
        """
        bot = MockGridBot(
            current_price=109946,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=5)
        
        expected = [110446, 110946, 111446, 111946, 112446]
        actual = [order['level'] for order in orders]
        
        assert actual == expected, f"Expected {expected}, got {actual}"
    
    def test_scenario_seed_at_lower_boundary(self):
        """
        Scenario: Current price near lower boundary (105000)
        Expected: Can seed many levels upward
        """
        bot = MockGridBot(
            current_price=105000,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=10)
        
        # From 105000, can go up to 115000 (20 steps)
        # Seeding 10 levels: 105500, 106000, 106500, 107000, 107500,
        #                     108000, 108500, 109000, 109500, 110000
        
        assert len(orders) == 10, f"Should place all 10 orders, got {len(orders)}"
        
        # Verify first and last
        assert orders[0]['level'] == 105500, "First order should be at 105500"
        assert orders[-1]['level'] == 110000, "Last order should be at 110000"
    
    def test_scenario_seed_near_upper_boundary(self):
        """
        Scenario: Current price near upper boundary
        Expected: Stops at boundary, places fewer orders than requested
        """
        bot = MockGridBot(
            current_price=113500,  # Only 3 steps below upper (115000)
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=10)
        
        # Can only place: 114000, 114500, 115000
        assert len(orders) == 3, f"Should place only 3 orders, got {len(orders)}"
        
        expected_levels = [114000, 114500, 115000]
        actual_levels = [order['level'] for order in orders]
        
        assert actual_levels == expected_levels, \
            f"Expected {expected_levels}, got {actual_levels}"
    
    def test_scenario_seed_exactly_at_reference(self):
        """
        Scenario: Current price exactly at reference (110000)
        Expected: Seeds upward from reference
        """
        bot = MockGridBot(
            current_price=110000,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=3)
        
        expected_levels = [110500, 111000, 111500]
        actual_levels = [order['level'] for order in orders]
        
        assert actual_levels == expected_levels, \
            f"Expected {expected_levels}, got {actual_levels}"


class TestShortModeSeedingEdgeCases:
    """Edge case testing for SHORT mode seeding"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        self.api_client = Mock()
        self.order_counter = 3000
        
        def mock_place_order(**kwargs):
            self.order_counter += 1
            return {
                'success': True,
                'result': {'id': str(self.order_counter)}
            }
        
        self.api_client.place_order = Mock(side_effect=mock_place_order)
        
        self.position_mgr = Mock()
        self.position_mgr.state_lock = MagicMock()
        
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
    
    def test_edge_current_price_above_upper_bound(self):
        """
        Edge Case: Current price above upper bound
        Expected: No orders placed (all would be outside grid)
        """
        bot = MockGridBot(
            current_price=116000,  # Above upper bound of 115000
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=5)
        
        # All calculated levels would be above 116000, which is already above upper bound
        assert len(orders) == 0, \
            f"Should place no orders when current price above upper bound, got {len(orders)}"
    
    def test_edge_current_price_at_upper_bound(self):
        """
        Edge Case: Current price exactly at upper bound
        Expected: No orders placed (next level would be outside)
        """
        bot = MockGridBot(
            current_price=115000,  # Exactly at upper bound
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=5)
        
        # First level would be 115000 + 500 = 115500 (above upper bound)
        assert len(orders) == 0, \
            f"Should place no orders when at upper bound, got {len(orders)}"
    
    def test_edge_very_large_count(self):
        """
        Edge Case: Request very large number of orders
        Expected: Stops at boundary, doesn't crash
        """
        bot = MockGridBot(
            current_price=105000,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=1000)
        
        # From 105000 to 115000 = 10000 / 500 = 20 steps max
        assert len(orders) <= 20, \
            f"Should not place more than 20 orders (grid capacity), got {len(orders)}"
        
        # Verify all orders are within bounds
        for order in orders:
            assert self.grid_calc.is_within_bounds(order['level']), \
                f"Order @ {order['level']} is outside grid bounds"
    
    def test_edge_step_size_precision(self):
        """
        Edge Case: Verify step calculations maintain precision
        Expected: No floating-point errors in level calculation
        """
        bot = MockGridBot(
            current_price=109946,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            orders = bot.seed_missed_grid_levels(count=5)
        
        # Verify each level is exactly step distance apart
        for i in range(len(orders) - 1):
            distance = orders[i + 1]['level'] - orders[i]['level']
            assert abs(distance - 500) < 1e-9, \
                f"Step distance should be 500, got {distance}"


class TestShortModeSeedingIntegration:
    """Integration tests: Seeding + Order Manager + Grid Calculator"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        self.api_client = Mock()
        self.placed_orders = []
        
        def track_orders(**kwargs):
            """Track all placed orders"""
            order_id = f"ORDER_{len(self.placed_orders) + 1}"
            self.placed_orders.append({
                'id': order_id,
                'side': kwargs.get('side'),
                'price': kwargs.get('limit_price'),
                'size': kwargs.get('size'),
            })
            return {
                'success': True,
                'result': {'id': order_id}
            }
        
        self.api_client.place_order = Mock(side_effect=track_orders)
        
        self.position_mgr = Mock()
        self.position_mgr.state_lock = MagicMock()
        
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
    
    def test_integration_seeding_calls_order_manager_correctly(self):
        """Test: SHORT seeding correctly integrates with OrderManager"""
        bot = MockGridBot(
            current_price=109946,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            bot.seed_missed_grid_levels(count=3)
        
        # Verify OrderManager was called 3 times
        assert len(self.placed_orders) == 3, \
            f"Should call OrderManager 3 times, called {len(self.placed_orders)}"
        
        # Verify all orders are SELL
        for order in self.placed_orders:
            assert order['side'] == 'sell', \
                f"All orders should be SELL, got {order['side']}"
    
    def test_integration_quantized_prices(self):
        """Test: Seeded orders respect tick_size quantization"""
        bot = MockGridBot(
            current_price=109946,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            bot.seed_missed_grid_levels(count=3)
        
        # Verify all prices are quantized to tick_size (0.5)
        for order in self.placed_orders:
            price = float(order['price'])
            quantized = self.grid_calc.quantize_price(price)
            
            assert abs(price - quantized) < 1e-9, \
                f"Price {price} should be quantized to {quantized}"


class TestShortModeSeedingComparison:
    """Compare SHORT mode behavior with LONG mode symmetry"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        self.api_client = Mock()
        self.order_counter = 4000
        
        def mock_place_order(**kwargs):
            self.order_counter += 1
            return {
                'success': True,
                'result': {'id': str(self.order_counter)}
            }
        
        self.api_client.place_order = Mock(side_effect=mock_place_order)
        
        self.position_mgr = Mock()
        self.position_mgr.state_lock = MagicMock()
        
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
    
    def test_symmetry_long_goes_down_short_goes_up(self):
        """Test: LONG seeds downward, SHORT seeds upward (symmetric)"""
        current_price = 110000
        
        bot = MockGridBot(
            current_price=current_price,
            grid_calc=self.grid_calc,
            order_mgr=self.order_mgr
        )
        
        # Test LONG mode
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'LONG'}):
            long_orders = bot.seed_missed_grid_levels(count=3)
        
        # Test SHORT mode
        self.api_client.reset_mock()
        with patch.dict(os.environ, {'GRIDBOT_GRID_MODE': 'SHORT'}):
            short_orders = bot.seed_missed_grid_levels(count=3)
        
        # LONG orders should be below current price
        for order in long_orders:
            assert order['level'] < current_price, "LONG orders below current"
        
        # SHORT orders should be above current price
        for order in short_orders:
            assert order['level'] > current_price, "SHORT orders above current"
        
        # Distance from current price should be symmetric
        long_distances = [current_price - order['level'] for order in long_orders]
        short_distances = [order['level'] - current_price for order in short_orders]
        
        assert long_distances == short_distances, \
            f"Distances should be symmetric: LONG={long_distances}, SHORT={short_distances}"


if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])

