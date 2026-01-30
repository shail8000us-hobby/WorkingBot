"""
Delta Exchange Data Module
==========================
Complete data collection infrastructure for WorkingBot.

Modules:
- delta_historical_fetcher: Historical OHLCV data with pagination
- delta_live_stream: WebSocket real-time streaming
- delta_data_manager: Unified data management with SQLite
- workingbot_integration: Integration layer for WorkingBot

Usage:
    from data import (
        DeltaHistoricalFetcher,
        DeltaLiveStreamer,
        DeltaDataManager,
        WorkingBotDataProvider,
        create_workingbot_provider
    )
    
    # Quick start
    provider = create_workingbot_provider(testnet=True)
    df = provider.get_ohlcv("BTCUSD", "1h", days=30)
"""

from .delta_historical_fetcher import (
    DeltaHistoricalFetcher,
    RateLimitConfig,
    FetchStats
)

from .delta_live_stream import (
    DeltaLiveStreamer,
    ConnectionState,
    StreamStats
)

from .delta_data_manager import (
    DeltaDataManager,
    DataConfig
)

from .workingbot_integration import (
    WorkingBotDataProvider,
    WorkingBotConfig,
    BacktestDataAdapter,
    LiveDataAdapter,
    create_workingbot_provider
)

# Backtesting module (optional import)
try:
    from .backtesting import (
        BacktestEngine,
        BacktestConfig,
        BacktestResult,
        Strategy,
        SignalType,
        Position,
        PositionTracker,
        calculate_metrics,
        MetricsResult
    )
    _backtesting_available = True
except ImportError:
    _backtesting_available = False

__all__ = [
    # Historical Fetcher
    "DeltaHistoricalFetcher",
    "RateLimitConfig",
    "FetchStats",
    
    # Live Streamer
    "DeltaLiveStreamer",
    "ConnectionState",
    "StreamStats",
    
    # Data Manager
    "DeltaDataManager",
    "DataConfig",
    
    # WorkingBot Integration
    "WorkingBotDataProvider",
    "WorkingBotConfig",
    "BacktestDataAdapter",
    "LiveDataAdapter",
    "create_workingbot_provider",
    
    # Backtesting
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "Strategy",
    "SignalType",
]

__version__ = "1.0.0"
__author__ = "WorkingBot"
