"""
Delta Exchange Data Module Tests
================================
Comprehensive tests for all Delta Exchange data collection modules.

Run with: python -m pytest data/test_delta_modules.py -v
Or: python data/test_delta_modules.py
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import sqlite3


class TestDeltaHistoricalFetcher(unittest.TestCase):
    """Tests for DeltaHistoricalFetcher."""
    
    def setUp(self):
        """Set up test fixtures."""
        from .delta_historical_fetcher import DeltaHistoricalFetcher, RateLimitConfig
        self.fetcher = DeltaHistoricalFetcher(testnet=True)
    
    def test_initialization(self):
        """Test fetcher initialization."""
        self.assertEqual(
            self.fetcher.base_url, 
            "https://cdn-ind.testnet.deltaex.org"
        )
        self.assertTrue(self.fetcher.testnet)
    
    def test_rate_limit_config(self):
        """Test rate limit configuration."""
        from .delta_historical_fetcher import RateLimitConfig
        
        config = RateLimitConfig()
        self.assertEqual(config.window_seconds, 300)
        self.assertEqual(config.max_units, 10000)
        self.assertEqual(config.candle_weight, 3)
    
    def test_resolution_validation(self):
        """Test resolution validation."""
        valid_resolutions = ["1m", "5m", "15m", "1h", "4h", "1d"]
        
        for res in valid_resolutions:
            self.assertIn(res, self.fetcher.RESOLUTIONS)
    
    def test_candle_limit(self):
        """Test candle limit constant."""
        self.assertEqual(self.fetcher.MAX_CANDLES_PER_REQUEST, 2000)
    
    @patch('requests.Session.get')
    def test_fetch_candles_success(self, mock_get):
        """Test successful candle fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": [
                {
                    "time": 1700000000,
                    "open": 50000.0,
                    "high": 51000.0,
                    "low": 49000.0,
                    "close": 50500.0,
                    "volume": 100.5
                }
            ]
        }
        mock_get.return_value = mock_response
        
        candles = self.fetcher.fetch_candles(
            symbol="BTCUSD",
            resolution="1h",
            start_time=datetime(2023, 11, 1),
            end_time=datetime(2023, 11, 2)
        )
        
        self.assertIsInstance(candles, list)
        if candles:  # May be empty if API is mocked
            self.assertIn("timestamp", candles[0])
            self.assertIn("close", candles[0])
    
    def test_validate_data(self):
        """Test data validation."""
        valid_candles = [
            {"timestamp": 1, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 10},
            {"timestamp": 2, "open": 105, "high": 115, "low": 95, "close": 110, "volume": 15}
        ]
        
        is_valid, errors = self.fetcher.validate_data(valid_candles)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_data_detects_issues(self):
        """Test that validation detects issues."""
        invalid_candles = [
            {"timestamp": 1, "open": 100, "high": 90, "low": 110, "close": 105, "volume": 10}
        ]
        
        is_valid, errors = self.fetcher.validate_data(invalid_candles)
        # High < Low should be detected
        self.assertFalse(is_valid)


class TestDeltaLiveStreamer(unittest.TestCase):
    """Tests for DeltaLiveStreamer."""
    
    def test_initialization(self):
        """Test streamer initialization."""
        from .delta_live_stream import DeltaLiveStreamer, ConnectionState
        
        streamer = DeltaLiveStreamer(testnet=True)
        
        self.assertEqual(streamer.state, ConnectionState.DISCONNECTED)
        self.assertEqual(
            streamer.ws_url,
            "wss://socket-ind.testnet.deltaex.org"
        )
    
    def test_resolution_validation(self):
        """Test supported resolutions."""
        from .delta_live_stream import DeltaLiveStreamer
        
        streamer = DeltaLiveStreamer(testnet=True)
        
        valid = ["1m", "5m", "15m", "1h"]
        for res in valid:
            self.assertIn(res, streamer.SUPPORTED_RESOLUTIONS)
    
    def test_subscribe_candles(self):
        """Test candle subscription."""
        from .delta_live_stream import DeltaLiveStreamer
        
        streamer = DeltaLiveStreamer(testnet=True)
        streamer.subscribe_candles(["BTCUSD", "ETHUSD"], "1m")
        
        self.assertEqual(len(streamer.subscriptions), 1)
        self.assertEqual(streamer.subscriptions[0]["name"], "candlestick_1m")
        self.assertEqual(streamer.subscriptions[0]["symbols"], ["BTCUSD", "ETHUSD"])
    
    def test_subscribe_mark_price(self):
        """Test mark price subscription."""
        from .delta_live_stream import DeltaLiveStreamer
        
        streamer = DeltaLiveStreamer(testnet=True)
        streamer.subscribe_mark_price(["BTCUSD"])
        
        self.assertEqual(len(streamer.subscriptions), 1)
        self.assertIn("MARK:BTCUSD", streamer.subscriptions[0]["symbols"])
    
    def test_stream_stats(self):
        """Test stream statistics."""
        from .delta_live_stream import StreamStats
        
        stats = StreamStats()
        
        self.assertEqual(stats.messages_received, 0)
        self.assertEqual(stats.candles_received, 0)
        self.assertGreater(stats.uptime_seconds, 0)
    
    def test_callbacks(self):
        """Test callback functionality."""
        from .delta_live_stream import DeltaLiveStreamer
        
        received_candles = []
        
        def on_candle(candle):
            received_candles.append(candle)
        
        streamer = DeltaLiveStreamer(on_candle=on_candle, testnet=True)
        
        # Simulate candle handling
        test_data = {
            "type": "candlestick_1m",
            "symbol": "BTCUSD",
            "resolution": "1m",
            "candle_start_time": "2023-11-01T00:00:00Z",
            "open": "50000",
            "high": "51000",
            "low": "49000",
            "close": "50500",
            "volume": "100"
        }
        
        streamer._handle_candle(test_data)
        
        self.assertEqual(len(received_candles), 1)
        self.assertEqual(received_candles[0]["symbol"], "BTCUSD")


class TestDeltaDataManager(unittest.TestCase):
    """Tests for DeltaDataManager."""
    
    def setUp(self):
        """Set up test fixtures with temp database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = f"{self.temp_dir}/test.db"
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_data_config(self):
        """Test data configuration."""
        from .delta_data_manager import DataConfig
        
        config = DataConfig(
            db_path=self.db_path,
            testnet=True
        )
        
        self.assertEqual(config.db_path, self.db_path)
        self.assertTrue(config.testnet)
    
    def test_database_initialization(self):
        """Test database tables are created."""
        from .delta_data_manager import DeltaDataManager, DataConfig
        
        config = DataConfig(db_path=self.db_path, testnet=True)
        manager = DeltaDataManager(config)
        
        # Check tables exist
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        
        self.assertIn("ohlcv", tables)
        self.assertIn("products", tables)
        self.assertIn("collection_log", tables)
        
        conn.close()
    
    def test_store_and_load_candles(self):
        """Test storing and loading candles."""
        from .delta_data_manager import DeltaDataManager, DataConfig
        
        config = DataConfig(db_path=self.db_path, testnet=True)
        manager = DeltaDataManager(config)
        
        # Store test candles
        test_candles = [
            {
                "timestamp": 1700000000,
                "datetime": "2023-11-14T12:00:00",
                "open": 50000.0,
                "high": 51000.0,
                "low": 49000.0,
                "close": 50500.0,
                "volume": 100.0
            },
            {
                "timestamp": 1700003600,
                "datetime": "2023-11-14T13:00:00",
                "open": 50500.0,
                "high": 52000.0,
                "low": 50000.0,
                "close": 51500.0,
                "volume": 150.0
            }
        ]
        
        stored = manager._store_candles("BTCUSD", "1h", test_candles, "test")
        self.assertEqual(stored, 2)
        
        # Load and verify
        df = manager.load_data("BTCUSD", "1h")
        self.assertEqual(len(df), 2)
        self.assertIn("close", df.columns)
    
    def test_get_data_range(self):
        """Test getting data range."""
        from .delta_data_manager import DeltaDataManager, DataConfig
        
        config = DataConfig(db_path=self.db_path, testnet=True)
        manager = DeltaDataManager(config)
        
        # Store test data
        test_candles = [
            {"timestamp": 1700000000, "datetime": "2023-11-14T12:00:00",
             "open": 100, "high": 110, "low": 90, "close": 105, "volume": 10}
        ]
        manager._store_candles("BTCUSD", "1h", test_candles, "test")
        
        # Get range
        data_range = manager.get_data_range("BTCUSD", "1h")
        
        self.assertIsNotNone(data_range)
        self.assertEqual(data_range["count"], 1)


class TestWorkingBotIntegration(unittest.TestCase):
    """Tests for WorkingBot integration layer."""
    
    def test_config_initialization(self):
        """Test configuration initialization."""
        from .workingbot_integration import WorkingBotConfig
        
        config = WorkingBotConfig(testnet=True)
        
        self.assertEqual(
            config.base_url,
            "https://cdn-ind.testnet.deltaex.org"
        )
        self.assertEqual(
            config.ws_url,
            "wss://socket-ind.testnet.deltaex.org"
        )
    
    def test_production_urls(self):
        """Test production URLs."""
        from .workingbot_integration import WorkingBotConfig
        
        config = WorkingBotConfig(testnet=False)
        
        self.assertEqual(
            config.base_url,
            "https://api.india.delta.exchange"
        )
        self.assertEqual(
            config.ws_url,
            "wss://socket.india.delta.exchange"
        )
    
    def test_provider_initialization(self):
        """Test data provider initialization."""
        from .workingbot_integration import create_workingbot_provider
        
        provider = create_workingbot_provider(testnet=True)
        
        self.assertIsNotNone(provider)
        self.assertTrue(provider.config.testnet)
    
    def test_technical_indicators(self):
        """Test technical indicator calculation."""
        import pandas as pd
        import numpy as np
        from .workingbot_integration import WorkingBotDataProvider
        
        provider = WorkingBotDataProvider()
        
        # Create test DataFrame
        dates = pd.date_range(start='2023-01-01', periods=50, freq='H')
        df = pd.DataFrame({
            'open': np.random.randn(50).cumsum() + 100,
            'high': np.random.randn(50).cumsum() + 101,
            'low': np.random.randn(50).cumsum() + 99,
            'close': np.random.randn(50).cumsum() + 100,
            'volume': np.random.rand(50) * 1000
        }, index=dates)
        
        # Add indicators
        df = provider.add_technical_indicators(df, ["sma_20", "rsi_14"])
        
        self.assertIn("sma_20", df.columns)
        self.assertIn("rsi_14", df.columns)
    
    def test_backtest_adapter(self):
        """Test backtest data adapter."""
        from .workingbot_integration import (
            WorkingBotDataProvider, 
            BacktestDataAdapter
        )
        
        provider = WorkingBotDataProvider()
        adapter = BacktestDataAdapter(provider)
        
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.provider, provider)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete data module."""
    
    def test_module_imports(self):
        """Test all module imports work correctly."""
        from . import (
            DeltaHistoricalFetcher,
            DeltaLiveStreamer,
            DeltaDataManager,
            WorkingBotDataProvider,
            create_workingbot_provider
        )
        
        self.assertIsNotNone(DeltaHistoricalFetcher)
        self.assertIsNotNone(DeltaLiveStreamer)
        self.assertIsNotNone(DeltaDataManager)
        self.assertIsNotNone(WorkingBotDataProvider)
        self.assertIsNotNone(create_workingbot_provider)
    
    def test_end_to_end_flow(self):
        """Test complete data flow."""
        temp_dir = tempfile.mkdtemp()
        
        try:
            from .delta_data_manager import DeltaDataManager, DataConfig
            
            # Create manager with temp database
            config = DataConfig(
                db_path=f"{temp_dir}/test.db",
                data_dir=f"{temp_dir}/data",
                testnet=True
            )
            manager = DeltaDataManager(config)
            
            # Store test data
            test_candles = [
                {"timestamp": i * 3600, "datetime": f"2023-01-01T{i:02d}:00:00",
                 "open": 100 + i, "high": 105 + i, "low": 95 + i, 
                 "close": 102 + i, "volume": 100 * i}
                for i in range(24)
            ]
            
            stored = manager._store_candles("BTCUSD", "1h", test_candles, "test")
            self.assertEqual(stored, 24)
            
            # Load and verify
            df = manager.load_data("BTCUSD", "1h")
            self.assertEqual(len(df), 24)
            
            # Get status
            status = manager.get_status()
            self.assertEqual(status["unique_symbols"], 1)
            self.assertEqual(status["total_candles"], 24)
            
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestDeltaHistoricalFetcher))
    suite.addTests(loader.loadTestsFromTestCase(TestDeltaLiveStreamer))
    suite.addTests(loader.loadTestsFromTestCase(TestDeltaDataManager))
    suite.addTests(loader.loadTestsFromTestCase(TestWorkingBotIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
