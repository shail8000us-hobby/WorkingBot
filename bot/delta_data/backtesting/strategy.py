"""
Strategy Base Class and Signal Types
=====================================

Defines the base class for trading strategies that can be backtested.

Usage:
    from backtesting import Strategy, SignalType
    
    class MySMAStrategy(Strategy):
        def __init__(self, fast_period=10, slow_period=20):
            super().__init__("SMA Crossover")
            self.fast_period = fast_period
            self.slow_period = slow_period
        
        def generate_signal(self, data, position):
            fast_sma = data['close'].rolling(self.fast_period).mean().iloc[-1]
            slow_sma = data['close'].rolling(self.slow_period).mean().iloc[-1]
            
            if fast_sma > slow_sma and position is None:
                return SignalType.BUY
            elif fast_sma < slow_sma and position is not None:
                return SignalType.SELL
            return SignalType.HOLD

Author: WorkingBot
Date: January 2026
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, List
import pandas as pd
from dataclasses import dataclass, field


class SignalType(Enum):
    """Trading signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    SHORT = "short"
    COVER = "cover"


@dataclass
class Signal:
    """
    Trading signal with optional parameters.
    """
    signal_type: SignalType
    price: Optional[float] = None
    size: Optional[float] = None  # Position size (1.0 = 100% of capital)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Strategy(ABC):
    """
    Base class for trading strategies.
    
    Subclass this to create your own trading strategy.
    Implement generate_signal() to define your trading logic.
    
    Attributes:
        name: Strategy name
        params: Strategy parameters
        indicators: List of required indicators
    """
    
    def __init__(
        self,
        name: str = "BaseStrategy",
        params: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize strategy.
        
        Args:
            name: Strategy name
            params: Strategy parameters
        """
        self.name = name
        self.params = params or {}
        self._indicators_cache: Dict[str, pd.Series] = {}
    
    @property
    def required_indicators(self) -> List[str]:
        """
        List of required indicators for this strategy.
        Override in subclass to specify required indicators.
        
        Returns:
            List of indicator names (e.g., ['sma_20', 'rsi_14'])
        """
        return []
    
    @abstractmethod
    def generate_signal(
        self,
        data: pd.DataFrame,
        current_position: Optional['Position'] = None,
        timestamp: Optional[pd.Timestamp] = None
    ) -> Signal:
        """
        Generate trading signal based on data.
        
        This is the main method to implement your trading logic.
        
        Args:
            data: OHLCV DataFrame with indicators up to current timestamp
            current_position: Current open position (if any)
            timestamp: Current timestamp in backtest
            
        Returns:
            Signal object with signal type and optional parameters
        """
        pass
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data by adding any required indicators.
        Override in subclass for custom data preparation.
        
        Args:
            data: Raw OHLCV DataFrame
            
        Returns:
            DataFrame with added indicators
        """
        return data
    
    def on_trade(
        self,
        trade_type: str,
        price: float,
        size: float,
        timestamp: pd.Timestamp
    ) -> None:
        """
        Called when a trade is executed.
        Override to track trade history or update internal state.
        
        Args:
            trade_type: 'open' or 'close'
            price: Execution price
            size: Trade size
            timestamp: Trade timestamp
        """
        pass
    
    def on_bar(
        self,
        bar: pd.Series,
        position: Optional['Position'],
        timestamp: pd.Timestamp
    ) -> None:
        """
        Called on each bar during backtest.
        Override for custom per-bar processing.
        
        Args:
            bar: Current OHLCV bar
            position: Current position
            timestamp: Current timestamp
        """
        pass
    
    def reset(self) -> None:
        """
        Reset strategy state.
        Called before each backtest run.
        """
        self._indicators_cache.clear()
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', params={self.params})"


# ==============================================================================
# Example Strategies
# ==============================================================================

class SMAcrossoverStrategy(Strategy):
    """
    Simple Moving Average crossover strategy.
    
    Buy when fast SMA crosses above slow SMA.
    Sell when fast SMA crosses below slow SMA.
    """
    
    def __init__(
        self,
        fast_period: int = 10,
        slow_period: int = 50,
        **kwargs
    ):
        super().__init__(
            name="SMA Crossover",
            params={'fast_period': fast_period, 'slow_period': slow_period}
        )
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    @property
    def required_indicators(self) -> List[str]:
        return [f'sma_{self.fast_period}', f'sma_{self.slow_period}']
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df[f'sma_{self.fast_period}'] = df['close'].rolling(self.fast_period).mean()
        df[f'sma_{self.slow_period}'] = df['close'].rolling(self.slow_period).mean()
        return df
    
    def generate_signal(
        self,
        data: pd.DataFrame,
        current_position: Optional['Position'] = None,
        timestamp: Optional[pd.Timestamp] = None
    ) -> Signal:
        if len(data) < self.slow_period:
            return Signal(SignalType.HOLD)
        
        fast_col = f'sma_{self.fast_period}'
        slow_col = f'sma_{self.slow_period}'
        
        fast_sma = data[fast_col].iloc[-1]
        slow_sma = data[slow_col].iloc[-1]
        
        prev_fast = data[fast_col].iloc[-2] if len(data) > 1 else fast_sma
        prev_slow = data[slow_col].iloc[-2] if len(data) > 1 else slow_sma
        
        # Bullish crossover
        if prev_fast <= prev_slow and fast_sma > slow_sma:
            if current_position is None:
                return Signal(SignalType.BUY, size=1.0)
        
        # Bearish crossover
        elif prev_fast >= prev_slow and fast_sma < slow_sma:
            if current_position is not None:
                return Signal(SignalType.SELL)
        
        return Signal(SignalType.HOLD)


class RSIStrategy(Strategy):
    """
    RSI-based mean reversion strategy.
    
    Buy when RSI is oversold (< oversold_level).
    Sell when RSI is overbought (> overbought_level).
    """
    
    def __init__(
        self,
        period: int = 14,
        oversold_level: float = 30,
        overbought_level: float = 70,
        **kwargs
    ):
        super().__init__(
            name="RSI Strategy",
            params={
                'period': period,
                'oversold_level': oversold_level,
                'overbought_level': overbought_level
            }
        )
        self.period = period
        self.oversold_level = oversold_level
        self.overbought_level = overbought_level
    
    @property
    def required_indicators(self) -> List[str]:
        return [f'rsi_{self.period}']
    
    def _calculate_rsi(self, series: pd.Series) -> pd.Series:
        """Calculate RSI."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df[f'rsi_{self.period}'] = self._calculate_rsi(df['close'])
        return df
    
    def generate_signal(
        self,
        data: pd.DataFrame,
        current_position: Optional['Position'] = None,
        timestamp: Optional[pd.Timestamp] = None
    ) -> Signal:
        if len(data) < self.period + 1:
            return Signal(SignalType.HOLD)
        
        rsi = data[f'rsi_{self.period}'].iloc[-1]
        
        if pd.isna(rsi):
            return Signal(SignalType.HOLD)
        
        # Oversold - buy signal
        if rsi < self.oversold_level:
            if current_position is None:
                return Signal(
                    SignalType.BUY,
                    size=1.0,
                    metadata={'rsi': rsi}
                )
        
        # Overbought - sell signal
        elif rsi > self.overbought_level:
            if current_position is not None:
                return Signal(
                    SignalType.SELL,
                    metadata={'rsi': rsi}
                )
        
        return Signal(SignalType.HOLD)


class MACDStrategy(Strategy):
    """
    MACD-based trend following strategy.
    
    Buy when MACD crosses above signal line.
    Sell when MACD crosses below signal line.
    """
    
    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        **kwargs
    ):
        super().__init__(
            name="MACD Strategy",
            params={
                'fast_period': fast_period,
                'slow_period': slow_period,
                'signal_period': signal_period
            }
        )
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
    
    @property
    def required_indicators(self) -> List[str]:
        return ['macd', 'macd_signal', 'macd_hist']
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        ema_fast = df['close'].ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.slow_period, adjust=False).mean()
        
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=self.signal_period, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        return df
    
    def generate_signal(
        self,
        data: pd.DataFrame,
        current_position: Optional['Position'] = None,
        timestamp: Optional[pd.Timestamp] = None
    ) -> Signal:
        if len(data) < self.slow_period + self.signal_period:
            return Signal(SignalType.HOLD)
        
        macd = data['macd'].iloc[-1]
        signal = data['macd_signal'].iloc[-1]
        prev_macd = data['macd'].iloc[-2] if len(data) > 1 else macd
        prev_signal = data['macd_signal'].iloc[-2] if len(data) > 1 else signal
        
        if pd.isna(macd) or pd.isna(signal):
            return Signal(SignalType.HOLD)
        
        # Bullish crossover
        if prev_macd <= prev_signal and macd > signal:
            if current_position is None:
                return Signal(
                    SignalType.BUY,
                    size=1.0,
                    metadata={'macd': macd, 'signal': signal}
                )
        
        # Bearish crossover
        elif prev_macd >= prev_signal and macd < signal:
            if current_position is not None:
                return Signal(
                    SignalType.SELL,
                    metadata={'macd': macd, 'signal': signal}
                )
        
        return Signal(SignalType.HOLD)
