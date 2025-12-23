"""
Tests for GridCalculator Module

Tests pure grid calculation logic extracted from GridBot.
"""

import pytest
from bot.strategy.modules.grid_calculator import GridCalculator


class TestGridCalculator:
    """Test suite for GridCalculator pure logic module"""
    
    def test_initialization_valid_params(self):
        """Test calculator initializes with valid parameters"""
        calc = GridCalculator(
            lower=105000,
            upper=120000,
            step=1000,
            ref=110000,
            tick_size=0.5
        )
        assert calc.lower == 105000
        assert calc.upper == 120000
        assert calc.step == 1000
        assert calc.ref == 110000
        assert calc.tick_size == 0.5
    
    def test_initialization_invalid_step(self):
        """Test calculator rejects invalid step"""
        with pytest.raises(ValueError, match="Step must be positive"):
            GridCalculator(lower=105000, upper=120000, step=0, ref=110000)
        
        with pytest.raises(ValueError, match="Step must be positive"):
            GridCalculator(lower=105000, upper=120000, step=-1000, ref=110000)
    
    def test_initialization_invalid_bounds(self):
        """Test calculator rejects invalid bounds"""
        with pytest.raises(ValueError, match="Lower bound must be less than upper"):
            GridCalculator(lower=120000, upper=105000, step=1000, ref=110000)
    
    def test_initialization_ref_outside_bounds(self):
        """Test calculator rejects ref outside bounds"""
        with pytest.raises(ValueError, match="Reference must be within grid bounds"):
            GridCalculator(lower=105000, upper=120000, step=1000, ref=125000)
        
        with pytest.raises(ValueError, match="Reference must be within grid bounds"):
            GridCalculator(lower=105000, upper=120000, step=1000, ref=100000)
    
    def test_compute_next_buy_no_positions(self):
        """Test next BUY with no open positions"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        result = calc.compute_next_buy_level([])
        assert result == 109000  # ref - step
    
    def test_compute_next_buy_with_positions(self):
        """Test next BUY with existing positions"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        positions = [
            {'entry_price': 110000},
            {'entry_price': 109000},
            {'entry_price': 108000}
        ]
        result = calc.compute_next_buy_level(positions)
        assert result == 107000  # lowest (108000) - step
    
    def test_compute_next_buy_outside_lower_bound(self):
        """Test next BUY returns None when below lower bound"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        positions = [{'entry_price': 105500}]
        result = calc.compute_next_buy_level(positions)
        assert result is None  # 104500 < 105000 (lower bound)
    
    def test_compute_next_buy_outside_upper_bound(self):
        """Test next BUY when position is above upper bound"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        # Edge case: position above grid returns next valid level (upper bound)
        positions = [{'entry_price': 121000}]
        result = calc.compute_next_buy_level(positions)
        assert result == 120000  # 121000 - 1000 = 120000 (at upper bound, still valid)
    
    def test_compute_tp_price(self):
        """Test TP price calculation"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        assert calc.compute_tp_price(108000) == 109000
        assert calc.compute_tp_price(110000) == 111000
        assert calc.compute_tp_price(105000) == 106000
    
    def test_compute_next_level_down(self):
        """Test next level down calculation"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        assert calc.compute_next_level_down(110000) == 109000
        assert calc.compute_next_level_down(108000) == 107000
    
    def test_quantize_price(self):
        """Test price quantization to tick size"""
        calc = GridCalculator(105000, 120000, 1000, 110000, tick_size=0.5)
        assert calc.quantize_price(108000.7) == 108000.5
        assert calc.quantize_price(108000.2) == 108000.0
        assert calc.quantize_price(108000.0) == 108000.0
        assert calc.quantize_price(108000.9) == 108000.5
    
    def test_quantize_price_tick_size_1(self):
        """Test quantization with tick size = 1"""
        calc = GridCalculator(105000, 120000, 1000, 110000, tick_size=1.0)
        assert calc.quantize_price(108000.7) == 108000.0
        assert calc.quantize_price(108000.2) == 108000.0
    
    def test_is_within_bounds(self):
        """Test bounds checking"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        assert calc.is_within_bounds(110000) is True
        assert calc.is_within_bounds(105000) is True
        assert calc.is_within_bounds(120000) is True
        assert calc.is_within_bounds(104999) is False
        assert calc.is_within_bounds(120001) is False
        assert calc.is_within_bounds(107500) is True
    
    def test_is_within_bounds_custom_range(self):
        """Test bounds checking with custom range"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        assert calc.is_within_bounds(108000, lower=107000, upper=109000) is True
        assert calc.is_within_bounds(106000, lower=107000, upper=109000) is False
        assert calc.is_within_bounds(110000, lower=107000, upper=109000) is False
    
    def test_get_grid_levels(self):
        """Test grid level generation"""
        calc = GridCalculator(105000, 108000, 1000, 106000)
        levels = calc.get_grid_levels()
        assert levels == [105000, 106000, 107000, 108000]
    
    def test_get_grid_levels_large_range(self):
        """Test grid level generation with larger range"""
        calc = GridCalculator(105000, 110000, 1000, 107000)
        levels = calc.get_grid_levels()
        assert len(levels) == 6  # 105, 106, 107, 108, 109, 110
        assert levels[0] == 105000
        assert levels[-1] == 110000
    
    def test_find_nearest_grid_level(self):
        """Test grid alignment (for recovery)"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        assert calc.find_nearest_grid_level(107287.5) == 107000
        assert calc.find_nearest_grid_level(107600) == 108000
        assert calc.find_nearest_grid_level(107500) == 108000  # Rounds up
        assert calc.find_nearest_grid_level(107400) == 107000  # Rounds down
    
    def test_find_nearest_grid_level_exact_match(self):
        """Test grid alignment when already on grid"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        assert calc.find_nearest_grid_level(107000) == 107000
        assert calc.find_nearest_grid_level(110000) == 110000
