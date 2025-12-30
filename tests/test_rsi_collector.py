"""
Unit Tests for RSI Collector (Guardian Layer 6)

Tests the improved RSI collector implementation including:
- RSI calculation (Wilder's smoothing method)
- Hysteresis logic
- Signal change tracking
- Configuration validation
- Error handling
"""

import unittest
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

# Import the RSI collector
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.guardian.collectors.rsi_collector import RSICollector


class TestRSICalculation(unittest.TestCase):
    """Test RSI calculation using Wilder's smoothing method."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_exchange = Mock()
        self.mock_config = Mock()
        
        # Setup config attributes
        self.mock_config.api = Mock()
        self.mock_config.api.live = Mock()
        self.mock_config.api.live.base_url = "https://api.india.delta.exchange"
        
        self.mock_config.bot = Mock()
        self.mock_config.bot.symbol = "BTCUSD"
        self.mock_config.bot.mode = "LONG"
        
        self.mock_config.safety = Mock()
        self.mock_config.safety.rsi = Mock()
        self.mock_config.safety.rsi.enabled = True
        self.mock_config.safety.rsi.period = 14
        self.mock_config.safety.rsi.timeframe = "1h"
        self.mock_config.safety.rsi.cache_ttl = 60
        self.mock_config.safety.rsi.long_threshold = 75.0
        self.mock_config.safety.rsi.short_threshold = 25.0
        self.mock_config.safety.rsi.hysteresis_seconds = 60
    
    def test_rsi_overbought_scenario(self):
        """Test RSI calculation with overbought prices (strong uptrend)."""
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # Simulate strong uptrend: prices increasing consistently
        prices = [
            100, 102, 104, 106, 108, 110, 112, 114, 116, 118,
            120, 122, 124, 126, 128, 130, 132, 134, 136, 138
        ]
        
        rsi = collector._calculate_rsi(prices, 14)
        
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 70)  # Should be overbought
        self.assertLessEqual(rsi, 100)
    
    def test_rsi_oversold_scenario(self):
        """Test RSI calculation with oversold prices (strong downtrend)."""
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # Simulate strong downtrend: prices decreasing consistently
        prices = [
            138, 136, 134, 132, 130, 128, 126, 124, 122, 120,
            118, 116, 114, 112, 110, 108, 106, 104, 102, 100
        ]
        
        rsi = collector._calculate_rsi(prices, 14)
        
        self.assertIsNotNone(rsi)
        self.assertLess(rsi, 30)  # Should be oversold
        self.assertGreaterEqual(rsi, 0)
    
    def test_rsi_neutral_scenario(self):
        """Test RSI calculation with neutral/ranging prices."""
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # Simulate ranging market with mixed gains/losses
        prices = [
            100, 102, 101, 103, 101, 104, 102, 103, 101, 105,
            103, 106, 104, 107, 105, 108, 106, 109, 107, 108
        ]
        
        rsi = collector._calculate_rsi(prices, 14)
        
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 30)  # Should be above oversold
        self.assertLess(rsi, 70)  # Should be below overbought
    
    def test_rsi_insufficient_data(self):
        """Test RSI with insufficient price data."""
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # Only 10 prices (need 15 for period=14)
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
        
        rsi = collector._calculate_rsi(prices, 14)
        
        self.assertIsNone(rsi)  # Should return None
    
    def test_rsi_zero_losses(self):
        """Test RSI when all price changes are gains (no losses)."""
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # All increasing prices (no losses)
        prices = [i for i in range(100, 120)]
        
        rsi = collector._calculate_rsi(prices, 14)
        
        self.assertIsNotNone(rsi)
        self.assertEqual(rsi, 100.0)  # Should be 100 when no losses
    
    def test_rsi_zero_gains(self):
        """Test RSI when all price changes are losses (no gains)."""
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # All decreasing prices (no gains)
        prices = [i for i in range(120, 100, -1)]
        
        rsi = collector._calculate_rsi(prices, 14)
        
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0)  # Should be close to 0
        self.assertLessEqual(rsi, 10)


class TestHysteresisLogic(unittest.TestCase):
    """Test hysteresis logic to prevent signal oscillation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_exchange = Mock()
        self.mock_config = Mock()
        
        # Setup config
        self.mock_config.api = Mock()
        self.mock_config.api.live = Mock()
        self.mock_config.api.live.base_url = "https://api.india.delta.exchange"
        
        self.mock_config.bot = Mock()
        self.mock_config.bot.symbol = "BTCUSD"
        self.mock_config.bot.mode = "LONG"
        
        self.mock_config.safety = Mock()
        self.mock_config.safety.rsi = Mock()
        self.mock_config.safety.rsi.enabled = True
        self.mock_config.safety.rsi.period = 14
        self.mock_config.safety.rsi.timeframe = "1h"
        self.mock_config.safety.rsi.cache_ttl = 60
        self.mock_config.safety.rsi.long_threshold = 75.0
        self.mock_config.safety.rsi.short_threshold = 25.0
        self.mock_config.safety.rsi.hysteresis_seconds = 2  # Short for testing
    
    @patch.object(RSICollector, 'get_latest_rsi')
    def test_hysteresis_in_threshold_zone(self, mock_get_rsi):
        """Test that hysteresis delays signal change in threshold zone."""
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # RSI at 74 (in threshold zone: 73-77)
        mock_get_rsi.return_value = 74.0
        
        # First call - should start hysteresis timer
        result1 = collector.should_stop_trading()
        self.assertIsNotNone(collector._hysteresis_start_time)
        
        # Immediate second call - hysteresis active, should maintain signal
        time.sleep(0.5)
        result2 = collector.should_stop_trading()
        self.assertEqual(result1, result2)  # Signal should be stable
    
    @patch.object(RSICollector, 'get_latest_rsi')
    def test_hysteresis_clears_outside_zone(self, mock_get_rsi):
        """Test that hysteresis clears when RSI moves out of threshold zone."""
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # RSI at 74 (in threshold zone)
        mock_get_rsi.return_value = 74.0
        collector.should_stop_trading()
        self.assertIsNotNone(collector._hysteresis_start_time)
        
        # RSI moves to 70 (out of threshold zone)
        mock_get_rsi.return_value = 70.0
        collector.should_stop_trading()
        self.assertIsNone(collector._hysteresis_start_time)  # Should clear


class TestModeAwareThresholds(unittest.TestCase):
    """Test LONG/SHORT mode-specific threshold logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_exchange = Mock()
        self.mock_config = Mock()
        
        # Setup config
        self.mock_config.api = Mock()
        self.mock_config.api.live = Mock()
        self.mock_config.api.live.base_url = "https://api.india.delta.exchange"
        
        self.mock_config.bot = Mock()
        self.mock_config.bot.symbol = "BTCUSD"
        
        self.mock_config.safety = Mock()
        self.mock_config.safety.rsi = Mock()
        self.mock_config.safety.rsi.enabled = True
        self.mock_config.safety.rsi.period = 14
        self.mock_config.safety.rsi.timeframe = "1h"
        self.mock_config.safety.rsi.cache_ttl = 60
        self.mock_config.safety.rsi.long_threshold = 75.0
        self.mock_config.safety.rsi.short_threshold = 25.0
        self.mock_config.safety.rsi.hysteresis_seconds = 60
    
    @patch.object(RSICollector, 'get_latest_rsi')
    def test_long_mode_stop_on_overbought(self, mock_get_rsi):
        """Test LONG mode stops on overbought (RSI >= 75)."""
        self.mock_config.bot.mode = "LONG"
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # RSI at 80 (overbought for LONG)
        mock_get_rsi.return_value = 80.0
        
        should_stop = collector.should_stop_trading()
        self.assertTrue(should_stop)  # Should stop in LONG mode
    
    @patch.object(RSICollector, 'get_latest_rsi')
    def test_long_mode_go_on_normal(self, mock_get_rsi):
        """Test LONG mode allows trading on normal RSI."""
        self.mock_config.bot.mode = "LONG"
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # RSI at 50 (neutral)
        mock_get_rsi.return_value = 50.0
        
        should_stop = collector.should_stop_trading()
        self.assertFalse(should_stop)  # Should allow trading
    
    @patch.object(RSICollector, 'get_latest_rsi')
    def test_short_mode_stop_on_oversold(self, mock_get_rsi):
        """Test SHORT mode stops on oversold (RSI <= 25)."""
        self.mock_config.bot.mode = "SHORT"
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # RSI at 20 (oversold for SHORT)
        mock_get_rsi.return_value = 20.0
        
        should_stop = collector.should_stop_trading()
        self.assertTrue(should_stop)  # Should stop in SHORT mode
    
    @patch.object(RSICollector, 'get_latest_rsi')
    def test_short_mode_go_on_normal(self, mock_get_rsi):
        """Test SHORT mode allows trading on normal RSI."""
        self.mock_config.bot.mode = "SHORT"
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # RSI at 50 (neutral)
        mock_get_rsi.return_value = 50.0
        
        should_stop = collector.should_stop_trading()
        self.assertFalse(should_stop)  # Should allow trading


class TestConfigValidation(unittest.TestCase):
    """Test configuration validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_exchange = Mock()
        self.mock_config = Mock()
        
        # Setup minimal config
        self.mock_config.api = Mock()
        self.mock_config.api.live = Mock()
        self.mock_config.api.live.base_url = "https://api.india.delta.exchange"
        
        self.mock_config.bot = Mock()
        self.mock_config.bot.symbol = "BTCUSD"
        self.mock_config.bot.mode = "LONG"
        
        self.mock_config.safety = Mock()
        self.mock_config.safety.rsi = Mock()
        self.mock_config.safety.rsi.enabled = True
    
    def test_invalid_timeframe_defaults_to_1h(self):
        """Test invalid timeframe defaults to 1h."""
        self.mock_config.safety.rsi.timeframe = "99x"  # Invalid
        self.mock_config.safety.rsi.period = 14
        self.mock_config.safety.rsi.cache_ttl = 60
        self.mock_config.safety.rsi.long_threshold = 75.0
        self.mock_config.safety.rsi.short_threshold = 25.0
        self.mock_config.safety.rsi.hysteresis_seconds = 60
        
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        self.assertEqual(collector.timeframe, "1h")
    
    def test_invalid_period_defaults_to_14(self):
        """Test invalid period defaults to 14."""
        self.mock_config.safety.rsi.timeframe = "1h"
        self.mock_config.safety.rsi.period = 200  # Invalid (> 100)
        self.mock_config.safety.rsi.cache_ttl = 60
        self.mock_config.safety.rsi.long_threshold = 75.0
        self.mock_config.safety.rsi.short_threshold = 25.0
        self.mock_config.safety.rsi.hysteresis_seconds = 60
        
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        self.assertEqual(collector.period, 14)
    
    def test_low_cache_ttl_increases_to_minimum(self):
        """Test low cache TTL is increased to minimum."""
        self.mock_config.safety.rsi.timeframe = "1h"
        self.mock_config.safety.rsi.period = 14
        self.mock_config.safety.rsi.cache_ttl = 5  # Too low
        self.mock_config.safety.rsi.long_threshold = 75.0
        self.mock_config.safety.rsi.short_threshold = 25.0
        self.mock_config.safety.rsi.hysteresis_seconds = 60
        
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        self.assertGreaterEqual(collector.cache_ttl, 30)


class TestSignalTracking(unittest.TestCase):
    """Test signal change tracking."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_exchange = Mock()
        self.mock_config = Mock()
        
        # Setup config
        self.mock_config.api = Mock()
        self.mock_config.api.live = Mock()
        self.mock_config.api.live.base_url = "https://api.india.delta.exchange"
        
        self.mock_config.bot = Mock()
        self.mock_config.bot.symbol = "BTCUSD"
        self.mock_config.bot.mode = "LONG"
        
        self.mock_config.safety = Mock()
        self.mock_config.safety.rsi = Mock()
        self.mock_config.safety.rsi.enabled = True
        self.mock_config.safety.rsi.period = 14
        self.mock_config.safety.rsi.timeframe = "1h"
        self.mock_config.safety.rsi.cache_ttl = 60
        self.mock_config.safety.rsi.long_threshold = 75.0
        self.mock_config.safety.rsi.short_threshold = 25.0
        self.mock_config.safety.rsi.hysteresis_seconds = 60
    
    def test_signal_change_tracked(self):
        """Test that signal changes are tracked."""
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # Simulate signal change
        collector._track_signal_change('GO', 'STOP', 80.0)
        
        history = collector.get_signal_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['old_signal'], 'GO')
        self.assertEqual(history[0]['new_signal'], 'STOP')
        self.assertEqual(history[0]['rsi'], 80.0)
    
    def test_signal_history_limited_to_50(self):
        """Test that signal history is limited to last 50 changes."""
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        # Add 60 signal changes
        for i in range(60):
            collector._track_signal_change('GO', 'STOP', 75.0 + i)
        
        history = collector.get_signal_history()
        self.assertEqual(len(history), 50)  # Should keep only last 50


class TestErrorHandling(unittest.TestCase):
    """Test error handling and fail-safe behavior."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_exchange = Mock()
        self.mock_config = Mock()
        
        # Setup config
        self.mock_config.api = Mock()
        self.mock_config.api.live = Mock()
        self.mock_config.api.live.base_url = "https://api.india.delta.exchange"
        
        self.mock_config.bot = Mock()
        self.mock_config.bot.symbol = "BTCUSD"
        self.mock_config.bot.mode = "LONG"
        
        self.mock_config.safety = Mock()
        self.mock_config.safety.rsi = Mock()
        self.mock_config.safety.rsi.enabled = True
        self.mock_config.safety.rsi.period = 14
        self.mock_config.safety.rsi.timeframe = "1h"
        self.mock_config.safety.rsi.cache_ttl = 60
        self.mock_config.safety.rsi.long_threshold = 75.0
        self.mock_config.safety.rsi.short_threshold = 25.0
        self.mock_config.safety.rsi.hysteresis_seconds = 60
    
    @patch.object(RSICollector, 'get_latest_rsi')
    def test_none_rsi_returns_false(self, mock_get_rsi):
        """Test that None RSI returns False (fail-safe)."""
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        mock_get_rsi.return_value = None
        
        should_stop = collector.should_stop_trading()
        self.assertFalse(should_stop)  # Fail-safe: don't block trading
    
    def test_disabled_collector_returns_none(self):
        """Test that disabled collector returns None."""
        self.mock_config.safety.rsi.enabled = False
        collector = RSICollector(self.mock_exchange, self.mock_config)
        
        rsi = collector.get_latest_rsi()
        self.assertIsNone(rsi)


if __name__ == '__main__':
    unittest.main()
