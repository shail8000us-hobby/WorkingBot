"""
Grid Strategy Backtester

Main backtest runner that integrates data, simulation, and strategy.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backtest.data.delta_ohlcv import DeltaOHLCV
from backtest.sim.sim_exchange import SimExchange
from backtest.sim.fee_model import FeeModel
from backtest.sim.funding_model import FundingModel
from backtest.metrics.accounting import BacktestAccountant

log = logging.getLogger("backtest.runner")


class GridBacktester:
    """
    Backtest runner for grid trading strategy.
    
    Workflow:
    1. Load historical OHLCV data
    2. Create simulated exchange
    3. Initialize grid strategy with sim exchange
    4. Process each candle through strategy
    5. Calculate performance metrics
    """
    
    def __init__(
        self,
        symbol: str = "BTC/USD:USD",
        timeframe: str = "1m",
        start: datetime = None,
        end: datetime = None,
        config: Optional[Dict] = None,
        is_testnet: bool = False
    ):
        """
        Initialize backtester.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe (1m, 5m, etc.)
            start: Backtest start time
            end: Backtest end time
            config: Strategy configuration dict
            is_testnet: Use testnet data
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.start = start
        self.end = end
        self.config = config or {}
        self.is_testnet = is_testnet
        
        # Components (initialized in run())
        self.data_fetcher: Optional[DeltaOHLCV] = None
        self.sim_exchange: Optional[SimExchange] = None
        self.strategy = None
        self.ohlcv_data: Optional[pd.DataFrame] = None
        
        log.info(f"GridBacktester initialized: {symbol} {timeframe} {start} to {end}")
    
    def run(self) -> Dict:
        """
        Execute backtest.
        
        Returns:
            Dict with results: {
                'metrics': performance metrics dict,
                'trades_df': trade log DataFrame,
                'equity_df': equity curve DataFrame,
                'summary': text summary
            }
        """
        log.info("=" * 70)
        log.info("STARTING BACKTEST")
        log.info("=" * 70)
        
        # Step 1: Load data
        log.info("Step 1/5: Loading historical data...")
        self.ohlcv_data = self._load_data()
        
        if self.ohlcv_data.empty:
            log.error("No data loaded - aborting backtest")
            return self._empty_result()
        
        log.info(f"Loaded {len(self.ohlcv_data)} candles")
        
        # Step 2: Initialize simulation
        log.info("Step 2/5: Initializing simulated exchange...")
        self._init_simulation()
        
        # Step 3: Initialize strategy
        log.info("Step 3/5: Initializing grid strategy...")
        self._init_strategy()
        
        # Step 4: Run simulation
        log.info("Step 4/5: Running simulation...")
        self._run_simulation()
        
        # Step 5: Calculate metrics
        log.info("Step 5/5: Calculating performance metrics...")
        results = self._calculate_results()
        
        log.info("=" * 70)
        log.info("BACKTEST COMPLETE")
        log.info("=" * 70)
        
        return results
    
    def _load_data(self) -> pd.DataFrame:
        """Load OHLCV data from Delta Exchange."""
        self.data_fetcher = DeltaOHLCV(
            symbol=self.symbol,
            timeframe=self.timeframe,
            is_testnet=self.is_testnet
        )
        
        data = self.data_fetcher.fetch(
            since=self.start,
            until=self.end
        )
        
        return data
    
    def _init_simulation(self):
        """Initialize simulated exchange and models."""
        # Fee model
        assume_maker = self.config.get('assume_maker', True)
        fee_model = FeeModel(assume_maker=assume_maker)
        
        # Funding model
        funding_mode = self.config.get('funding_mode', 'off')
        funding_model = FundingModel(mode=funding_mode)
        
        # Sim exchange
        tick_size = float(self.config.get('tick_size', 0.5))
        same_bar_priority = self.config.get('same_bar_priority', 'tp_first')
        
        self.sim_exchange = SimExchange(
            symbol=self.symbol,
            initial_balance=0.0,  # Grid strategy is PnL-based, not balance-based
            fee_model=fee_model,
            funding_model=funding_model,
            same_bar_priority=same_bar_priority,
            tick_size=tick_size
        )
        
        log.info(f"SimExchange ready: tick_size={tick_size}, priority={same_bar_priority}")
    
    def _init_strategy(self):
        """
        Initialize grid trading strategy using adapter.
        
        Uses BacktestAdapter to avoid modifying production code.
        """
        from backtest.adapter import create_backtest_strategy
        
        self.strategy = create_backtest_strategy(
            sim_exchange=self.sim_exchange,
            config=self.config
        )
        
        log.info("Grid strategy initialized via backtest adapter")
    
    def _run_simulation(self):
        """Process each candle through the strategy."""
        total_candles = len(self.ohlcv_data)
        
        for idx, row in self.ohlcv_data.iterrows():
            # Extract candle data
            timestamp = row['timestamp']
            open_price = row['open']
            high = row['high']
            low = row['low']
            close = row['close']
            volume = row['volume']
            
            # Process candle in sim exchange (check fills)
            self.sim_exchange.process_candle(
                timestamp, open_price, high, low, close, volume
            )
            
            # Call strategy on_tick (or equivalent)
            if hasattr(self.strategy, 'on_tick'):
                self.strategy.on_tick(close, timestamp)
            elif hasattr(self.strategy, 'update'):
                self.strategy.update(close, timestamp)
            
            # Progress logging
            if (idx + 1) % 1000 == 0:
                progress = (idx + 1) / total_candles * 100
                log.info(f"Progress: {idx + 1}/{total_candles} ({progress:.1f}%)")
        
        log.info(f"Processed {total_candles} candles")
    
    def _calculate_results(self) -> Dict:
        """Calculate final metrics and prepare results."""
        # Get trade log
        trades_df = self.sim_exchange.get_trades_df()
        
        # Calculate metrics
        accountant = BacktestAccountant(
            trades_df=trades_df,
            initial_balance=0.0,
            symbol=self.symbol
        )
        
        metrics = accountant.calculate_metrics()
        equity_df = accountant._build_equity_curve()
        summary_text = accountant.generate_report()
        
        # Get sim exchange summary
        sim_summary = self.sim_exchange.get_summary()
        
        return {
            'metrics': metrics,
            'trades_df': trades_df,
            'equity_df': equity_df,
            'summary': summary_text,
            'sim_summary': sim_summary,
            'config': self.config,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'start': self.start,
            'end': self.end
        }
    
    def _empty_result(self) -> Dict:
        """Return empty result structure."""
        return {
            'metrics': {},
            'trades_df': pd.DataFrame(),
            'equity_df': pd.DataFrame(),
            'summary': "No data - backtest failed",
            'sim_summary': {},
            'config': self.config,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'start': self.start,
            'end': self.end
        }

