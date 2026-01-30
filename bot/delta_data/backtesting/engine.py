"""
Backtest Engine
===============

Core engine for running backtests against historical OHLCV data.

Features:
- Event-driven backtesting
- Support for multiple timeframes
- Stop loss and take profit orders
- Comprehensive metrics calculation
- Integration with WorkingBot data infrastructure

Usage:
    from backtesting import BacktestEngine, BacktestConfig
    from backtesting.strategy import SMAcrossoverStrategy
    
    # Create engine
    config = BacktestConfig(initial_capital=10000, commission_rate=0.001)
    engine = BacktestEngine(config)
    
    # Run backtest
    strategy = SMAcrossoverStrategy(fast_period=10, slow_period=50)
    result = engine.run(strategy, data)
    
    # View results
    print(result.metrics.summary())

Author: WorkingBot
Date: January 2026
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
import pandas as pd
import numpy as np
from datetime import datetime
import logging

from .strategy import Strategy, Signal, SignalType
from .position import Position, PositionTracker, PositionSide, Trade
from .metrics import calculate_metrics, MetricsResult


logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """
    Configuration for backtesting.
    
    Attributes:
        initial_capital: Starting capital
        commission_rate: Commission per trade (0.001 = 0.1%)
        slippage_rate: Slippage per trade (0.0005 = 0.05%)
        risk_free_rate: Annual risk-free rate for Sharpe
        allow_shorting: Allow short positions
        max_position_size: Maximum position size as fraction of capital
    """
    initial_capital: float = 10000.0
    commission_rate: float = 0.001  # 0.1%
    slippage_rate: float = 0.0005   # 0.05%
    risk_free_rate: float = 0.02    # 2% annual
    allow_shorting: bool = False
    max_position_size: float = 1.0  # 100% of capital
    
    def __post_init__(self):
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive")
        if not 0 <= self.commission_rate <= 1:
            raise ValueError("Commission rate must be between 0 and 1")
        if not 0 <= self.slippage_rate <= 1:
            raise ValueError("Slippage rate must be between 0 and 1")


@dataclass
class BacktestResult:
    """
    Container for backtest results.
    
    Attributes:
        strategy_name: Name of the strategy tested
        metrics: Performance metrics
        trades: List of completed trades
        equity_curve: DataFrame with equity over time
        config: Backtest configuration used
        data_info: Information about the data used
    """
    strategy_name: str
    metrics: MetricsResult
    trades: List[Trade]
    equity_curve: pd.DataFrame
    config: BacktestConfig
    data_info: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_return(self) -> float:
        return self.metrics.total_return
    
    @property
    def total_return_percent(self) -> float:
        return self.metrics.total_return_percent
    
    @property
    def sharpe_ratio(self) -> float:
        return self.metrics.sharpe_ratio
    
    @property
    def max_drawdown_percent(self) -> float:
        return self.metrics.max_drawdown_percent
    
    @property
    def win_rate(self) -> float:
        return self.metrics.win_rate
    
    def summary(self) -> str:
        """Get formatted summary."""
        return f"""
╔═══════════════════════════════════════════════════════════╗
║              BACKTEST: {self.strategy_name:^25}  ║
╚═══════════════════════════════════════════════════════════╝
{self.metrics.summary()}
"""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'strategy_name': self.strategy_name,
            'metrics': self.metrics.to_dict(),
            'trades_count': len(self.trades),
            'config': {
                'initial_capital': self.config.initial_capital,
                'commission_rate': self.config.commission_rate,
                'slippage_rate': self.config.slippage_rate
            },
            'data_info': self.data_info
        }


class BacktestEngine:
    """
    Core backtesting engine.
    
    Runs event-driven backtests against historical OHLCV data.
    """
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        """
        Initialize backtest engine.
        
        Args:
            config: Backtest configuration
        """
        self.config = config or BacktestConfig()
        self._callbacks: Dict[str, List[Callable]] = {
            'on_bar': [],
            'on_trade': [],
            'on_signal': [],
            'on_complete': []
        }
    
    def run(
        self,
        strategy: Strategy,
        data: pd.DataFrame,
        verbose: bool = False
    ) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Args:
            strategy: Trading strategy to test
            data: OHLCV DataFrame with columns: open, high, low, close, volume
                  Index should be DatetimeIndex
            verbose: Print progress updates
            
        Returns:
            BacktestResult with metrics, trades, and equity curve
        """
        # Validate data
        required_columns = ['open', 'high', 'low', 'close']
        missing = [c for c in required_columns if c not in data.columns]
        if missing:
            raise ValueError(f"Data missing required columns: {missing}")
        
        if len(data) < 2:
            raise ValueError("Data must have at least 2 rows")
        
        # Prepare data
        df = self._prepare_data(data, strategy)
        
        if verbose:
            logger.info(f"Starting backtest: {strategy.name}")
            logger.info(f"Data: {len(df)} bars from {df.index[0]} to {df.index[-1]}")
        
        # Reset strategy and tracker
        strategy.reset()
        tracker = PositionTracker(
            initial_capital=self.config.initial_capital,
            commission_rate=self.config.commission_rate,
            slippage_rate=self.config.slippage_rate
        )
        
        # Main backtest loop
        for i in range(1, len(df)):
            timestamp = df.index[i]
            bar = df.iloc[i]
            historical_data = df.iloc[:i+1]
            
            # Check stop loss / take profit on current bar
            sl_tp_trade = tracker.process_bar(bar, timestamp)
            if sl_tp_trade:
                self._trigger_callbacks('on_trade', sl_tp_trade)
                if verbose:
                    logger.info(f"[{timestamp}] {sl_tp_trade.exit_reason.upper()}: "
                               f"Exit at ${sl_tp_trade.exit_price:.2f}, "
                               f"P&L: ${sl_tp_trade.pnl:.2f}")
            
            # Generate signal
            signal = strategy.generate_signal(
                historical_data,
                tracker.position,
                timestamp
            )
            
            self._trigger_callbacks('on_signal', signal, timestamp)
            
            # Process signal
            if signal.signal_type == SignalType.BUY:
                if tracker.position is None:
                    size = min(signal.size or 1.0, self.config.max_position_size)
                    pos = tracker.open_position(
                        price=bar['close'],
                        timestamp=timestamp,
                        size_fraction=size,
                        side=PositionSide.LONG,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        metadata=signal.metadata
                    )
                    if pos and verbose:
                        logger.info(f"[{timestamp}] BUY: Entry at ${pos.entry_price:.2f}, "
                                   f"Size: {pos.size:.6f}")
            
            elif signal.signal_type == SignalType.SELL:
                if tracker.position is not None:
                    trade = tracker.close_position(
                        price=bar['close'],
                        timestamp=timestamp,
                        reason="signal"
                    )
                    if trade:
                        self._trigger_callbacks('on_trade', trade)
                        if verbose:
                            logger.info(f"[{timestamp}] SELL: Exit at ${trade.exit_price:.2f}, "
                                       f"P&L: ${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)")
            
            elif signal.signal_type == SignalType.SHORT:
                if self.config.allow_shorting and tracker.position is None:
                    size = min(signal.size or 1.0, self.config.max_position_size)
                    pos = tracker.open_position(
                        price=bar['close'],
                        timestamp=timestamp,
                        size_fraction=size,
                        side=PositionSide.SHORT,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        metadata=signal.metadata
                    )
                    if pos and verbose:
                        logger.info(f"[{timestamp}] SHORT: Entry at ${pos.entry_price:.2f}")
            
            elif signal.signal_type == SignalType.COVER:
                if tracker.position is not None and tracker.position.is_short:
                    trade = tracker.close_position(
                        price=bar['close'],
                        timestamp=timestamp,
                        reason="signal"
                    )
                    if trade:
                        self._trigger_callbacks('on_trade', trade)
                        if verbose:
                            logger.info(f"[{timestamp}] COVER: Exit at ${trade.exit_price:.2f}, "
                                       f"P&L: ${trade.pnl:.2f}")
            
            # Record equity
            tracker.record_equity(timestamp, bar['close'])
            
            # Call bar callback
            strategy.on_bar(bar, tracker.position, timestamp)
            self._trigger_callbacks('on_bar', bar, tracker.position, timestamp)
        
        # Close any remaining position at end
        if tracker.position is not None:
            final_price = df.iloc[-1]['close']
            final_timestamp = df.index[-1]
            trade = tracker.close_position(final_price, final_timestamp, reason="backtest_end")
            if trade and verbose:
                logger.info(f"[{final_timestamp}] END: Closed position at ${trade.exit_price:.2f}, "
                           f"P&L: ${trade.pnl:.2f}")
        
        # Calculate metrics
        equity_df = tracker.get_equity_df()
        metrics = calculate_metrics(
            trades=tracker.trades,
            equity_curve=equity_df,
            initial_capital=self.config.initial_capital,
            final_capital=tracker.capital,
            total_commission=tracker.total_commission,
            total_slippage=tracker.total_slippage,
            risk_free_rate=self.config.risk_free_rate
        )
        
        # Build result
        result = BacktestResult(
            strategy_name=strategy.name,
            metrics=metrics,
            trades=tracker.trades,
            equity_curve=equity_df,
            config=self.config,
            data_info={
                'start': str(df.index[0]),
                'end': str(df.index[-1]),
                'bars': len(df),
                'symbol': data.attrs.get('symbol', 'Unknown') if hasattr(data, 'attrs') else 'Unknown'
            }
        )
        
        self._trigger_callbacks('on_complete', result)
        
        if verbose:
            logger.info(f"\n{result.summary()}")
        
        return result
    
    def _prepare_data(
        self,
        data: pd.DataFrame,
        strategy: Strategy
    ) -> pd.DataFrame:
        """Prepare data by ensuring proper index and adding indicators."""
        df = data.copy()
        
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'datetime' in df.columns:
                df = df.set_index('datetime')
            elif 'timestamp' in df.columns:
                df = df.set_index('timestamp')
                df.index = pd.to_datetime(df.index)
        
        # Sort by index
        df = df.sort_index()
        
        # Add strategy indicators
        df = strategy.prepare_data(df)
        
        return df
    
    def add_callback(self, event: str, callback: Callable) -> None:
        """
        Add a callback for an event.
        
        Events:
            on_bar: Called for each bar (bar, position, timestamp)
            on_trade: Called when trade completes (trade)
            on_signal: Called when signal generated (signal, timestamp)
            on_complete: Called when backtest completes (result)
        """
        if event not in self._callbacks:
            raise ValueError(f"Unknown event: {event}")
        self._callbacks[event].append(callback)
    
    def _trigger_callbacks(self, event: str, *args, **kwargs) -> None:
        """Trigger all callbacks for an event."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")


def run_backtest(
    strategy: Strategy,
    data: pd.DataFrame,
    initial_capital: float = 10000.0,
    commission_rate: float = 0.001,
    slippage_rate: float = 0.0005,
    verbose: bool = False
) -> BacktestResult:
    """
    Convenience function to run a backtest.
    
    Args:
        strategy: Trading strategy to test
        data: OHLCV DataFrame
        initial_capital: Starting capital
        commission_rate: Commission per trade
        slippage_rate: Slippage per trade
        verbose: Print progress
        
    Returns:
        BacktestResult
    """
    config = BacktestConfig(
        initial_capital=initial_capital,
        commission_rate=commission_rate,
        slippage_rate=slippage_rate
    )
    engine = BacktestEngine(config)
    return engine.run(strategy, data, verbose=verbose)
