"""
Test Suite for SHORT Mode Bug Detection

Tests the bugs identified in SHORT mode implementation:
1. TP order placement uses wrong side (always 'sell' instead of 'buy' for SHORT)
2. No side detection in safe_place_tp
3. Collision detection issues
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from bot.strategy.modules.grid_calculator import GridCalculator
from bot.strategy.modules.order_manager import OrderManager
from bot.strategy.modules.position_manager import PositionManager


class TestShortModeTPBug:
    """Test TP placement bug in SHORT mode"""
    
    def setup_method(self):
        """Setup test fixtures"""
        # Grid calculator
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # Mock API client
        self.api_client = Mock()
        self.api_client.place_order = Mock(return_value={
            'success': True,
            'result': {'id': '12345'}
        })
        
        # Mock position manager
        self.position_mgr = Mock()
        self.position_mgr.state_lock = MagicMock()
        self.position_mgr.open_tranches = []
        
        # Order manager
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
    
    def test_long_mode_tp_side_is_sell(self):
        """Test that LONG mode TP uses SELL order (correct)"""
        position = {
            'entry_price': 110000,
            'tp_price': 110500,
            'size': 1,
            'side': 'long'  # LONG position
        }
        
        # Call safe_place_tp
        self.order_mgr.safe_place_tp(position, check_collisions=False)
        
        # Verify API was called
        assert self.api_client.place_order.called
        call_kwargs = self.api_client.place_order.call_args[1]
        
        # ✅ LONG mode should use 'sell' for TP
        assert call_kwargs['side'] == 'sell', "LONG mode TP should be SELL order"
    
    def test_short_mode_tp_side_should_be_buy(self):
        """🐛 BUG TEST: SHORT mode TP should use BUY order, but uses SELL"""
        position = {
            'entry_price': 110500,
            'tp_price': 110000,
            'size': 1,
            'side': 'short'  # SHORT position
        }
        
        # Call safe_place_tp
        self.order_mgr.safe_place_tp(position, check_collisions=False)
        
        # Verify API was called
        assert self.api_client.place_order.called
        call_kwargs = self.api_client.place_order.call_args[1]
        
        # 🐛 BUG: Current code always uses 'sell', but SHORT mode should use 'buy'
        # This test will FAIL, exposing the bug
        assert call_kwargs['side'] == 'buy', \
            "🐛 BUG FOUND: SHORT mode TP should be BUY order to close the short, but code uses SELL!"
    
    def test_tp_price_for_short_mode(self):
        """Test TP price calculation for SHORT mode"""
        entry_price = 110500
        
        # SHORT mode: TP should be BELOW entry (buy back lower)
        tp_price = self.grid_calc.compute_tp_price_short(entry_price)
        
        assert tp_price == 110000, "SHORT TP should be entry - step"
        assert tp_price < entry_price, "SHORT TP must be below entry price"
    
    def test_next_sell_level_calculation(self):
        """Test next SELL level calculation for SHORT mode"""
        # No positions - should return ref + step
        result = self.grid_calc.compute_next_sell_level([])
        assert result == 110500, "First SELL should be ref + step"
        
        # With positions - should return highest entry + step
        positions = [
            {'entry_price': 110500},
            {'entry_price': 111000},
            {'entry_price': 111500}
        ]
        result = self.grid_calc.compute_next_sell_level(positions)
        assert result == 112000, "Next SELL should be highest entry + step"


class TestShortModeCollisionDetection:
    """Test collision detection in SHORT mode"""
    
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
        self.api_client.place_order = Mock(return_value={
            'success': True,
            'result': {'id': '12345'}
        })
        
        self.position_mgr = Mock()
        self.position_mgr.state_lock = MagicMock()
        
        # Existing positions
        self.position_mgr.open_tranches = [
            {'entry_price': 110500, 'tp_price': 110000, 'side': 'short'},
            {'entry_price': 111000, 'tp_price': 110500, 'side': 'short'},
        ]
        
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
    
    def test_tp_collision_with_entry_price(self):
        """🐛 BUG TEST: TP @ 111000 collides with entry @ 111000"""
        # New SHORT position @ 111500, TP @ 111000
        # But we already have a position with entry @ 111000
        # TP will collide!
        
        new_position = {
            'entry_price': 111500,
            'tp_price': 111000,  # ⚠️ Collides with existing entry!
            'size': 1,
            'side': 'short'
        }
        
        # Place TP with collision detection
        self.order_mgr.safe_place_tp(new_position, check_collisions=True)
        
        # Verify TP was offset to avoid collision
        assert new_position['tp_price'] != 111000, \
            "TP should be offset to avoid collision with existing entry"
        
        # Should be offset by tick_size (0.5)
        assert new_position['tp_price'] in [111000.5, 111001.0], \
            "TP should be offset by tick_size to find safe level"


class TestShortModeIntegration:
    """Integration tests for SHORT mode workflow"""
    
    def test_short_workflow_sequence(self):
        """Test complete SHORT mode workflow"""
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # Scenario: Start at 109946, market goes up
        
        # Step 1: First SELL order
        next_sell = grid_calc.compute_next_sell_level([])
        assert next_sell == 110500, "First SELL @ ref + step"
        
        # Step 2: SELL fills, calculate TP
        sell_entry = 110500
        tp_price = grid_calc.compute_tp_price_short(sell_entry)
        assert tp_price == 110000, "SHORT TP should be entry - step"
        
        # Step 3: Next SELL after first fill
        positions = [{'entry_price': 110500}]
        next_sell = grid_calc.compute_next_sell_level(positions)
        assert next_sell == 111000, "Next SELL @ 111000"
        
        # Step 4: Verify boundary
        positions = [{'entry_price': 115000}]
        next_sell = grid_calc.compute_next_sell_level(positions)
        assert next_sell is None, "Should not SELL above upper bound"


if __name__ == "__main__":
    pytest.main([__file__, '-v'])

