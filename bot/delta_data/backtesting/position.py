"""
Position Tracking Module
========================

Tracks positions during backtesting including entry, exit,
P&L calculations, and trade history.

Author: WorkingBot
Date: January 2026
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import pandas as pd


class PositionSide(Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"


@dataclass
class Position:
    """
    Represents an open trading position.
    
    Attributes:
        entry_price: Entry price
        entry_time: Entry timestamp
        size: Position size (in units)
        side: LONG or SHORT
        stop_loss: Stop loss price (optional)
        take_profit: Take profit price (optional)
    """
    entry_price: float
    entry_time: pd.Timestamp
    size: float
    side: PositionSide = PositionSide.LONG
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_long(self) -> bool:
        return self.side == PositionSide.LONG
    
    @property
    def is_short(self) -> bool:
        return self.side == PositionSide.SHORT
    
    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L at current price."""
        if self.is_long:
            return (current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - current_price) * self.size
    
    def unrealized_pnl_percent(self, current_price: float) -> float:
        """Calculate unrealized P&L as percentage."""
        if self.is_long:
            return ((current_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - current_price) / self.entry_price) * 100
    
    def check_stop_loss(self, low_price: float, high_price: float) -> bool:
        """Check if stop loss was hit."""
        if self.stop_loss is None:
            return False
        
        if self.is_long:
            return low_price <= self.stop_loss
        else:
            return high_price >= self.stop_loss
    
    def check_take_profit(self, low_price: float, high_price: float) -> bool:
        """Check if take profit was hit."""
        if self.take_profit is None:
            return False
        
        if self.is_long:
            return high_price >= self.take_profit
        else:
            return low_price <= self.take_profit


@dataclass
class Trade:
    """
    Represents a completed trade (round-trip).
    
    Attributes:
        entry_price: Entry price
        exit_price: Exit price
        entry_time: Entry timestamp
        exit_time: Exit timestamp
        size: Trade size
        side: LONG or SHORT
        pnl: Profit/loss in base currency
        pnl_percent: Profit/loss as percentage
        exit_reason: Why the trade was closed
    """
    entry_price: float
    exit_price: float
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    size: float
    side: PositionSide
    pnl: float
    pnl_percent: float
    exit_reason: str = "signal"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_winner(self) -> bool:
        return self.pnl > 0
    
    @property
    def is_loser(self) -> bool:
        return self.pnl < 0
    
    @property
    def duration(self) -> pd.Timedelta:
        return self.exit_time - self.entry_time
    
    @property
    def duration_hours(self) -> float:
        return self.duration.total_seconds() / 3600


class PositionTracker:
    """
    Tracks positions and trades during backtest.
    
    Handles:
    - Opening and closing positions
    - Stop loss and take profit execution
    - Trade history recording
    - P&L calculations
    """
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission_rate: float = 0.001,  # 0.1%
        slippage_rate: float = 0.0005    # 0.05%
    ):
        """
        Initialize position tracker.
        
        Args:
            initial_capital: Starting capital
            commission_rate: Commission rate per trade (0.001 = 0.1%)
            slippage_rate: Slippage rate per trade (0.0005 = 0.05%)
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        
        self.reset()
    
    def reset(self) -> None:
        """Reset tracker state."""
        self.capital = self.initial_capital
        self.position: Optional[Position] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.total_commission = 0.0
        self.total_slippage = 0.0
    
    def open_position(
        self,
        price: float,
        timestamp: pd.Timestamp,
        size_fraction: float = 1.0,
        side: PositionSide = PositionSide.LONG,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Position]:
        """
        Open a new position.
        
        Args:
            price: Entry price
            timestamp: Entry timestamp
            size_fraction: Fraction of capital to use (1.0 = 100%)
            side: LONG or SHORT
            stop_loss: Stop loss price
            take_profit: Take profit price
            metadata: Additional trade data
            
        Returns:
            Created Position or None if already has position
        """
        if self.position is not None:
            return None  # Already has a position
        
        # Apply slippage
        slippage = price * self.slippage_rate
        if side == PositionSide.LONG:
            entry_price = price + slippage
        else:
            entry_price = price - slippage
        
        # Calculate position size
        capital_to_use = self.capital * size_fraction
        commission = capital_to_use * self.commission_rate
        capital_after_commission = capital_to_use - commission
        
        size = capital_after_commission / entry_price
        
        # Track costs
        self.total_commission += commission
        self.total_slippage += slippage * size
        
        self.position = Position(
            entry_price=entry_price,
            entry_time=timestamp,
            size=size,
            side=side,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata=metadata or {}
        )
        
        return self.position
    
    def close_position(
        self,
        price: float,
        timestamp: pd.Timestamp,
        reason: str = "signal"
    ) -> Optional[Trade]:
        """
        Close current position.
        
        Args:
            price: Exit price
            timestamp: Exit timestamp
            reason: Exit reason (e.g., 'signal', 'stop_loss', 'take_profit')
            
        Returns:
            Completed Trade or None if no position
        """
        if self.position is None:
            return None
        
        pos = self.position
        
        # Apply slippage
        slippage = price * self.slippage_rate
        if pos.is_long:
            exit_price = price - slippage
        else:
            exit_price = price + slippage
        
        # Calculate P&L
        if pos.is_long:
            pnl = (exit_price - pos.entry_price) * pos.size
        else:
            pnl = (pos.entry_price - exit_price) * pos.size
        
        # Calculate commission
        trade_value = exit_price * pos.size
        commission = trade_value * self.commission_rate
        pnl -= commission
        
        # Track costs
        self.total_commission += commission
        self.total_slippage += slippage * pos.size
        
        # Calculate P&L percentage
        pnl_percent = (pnl / (pos.entry_price * pos.size)) * 100
        
        # Update capital
        self.capital += pnl
        
        # Create trade record
        trade = Trade(
            entry_price=pos.entry_price,
            exit_price=exit_price,
            entry_time=pos.entry_time,
            exit_time=timestamp,
            size=pos.size,
            side=pos.side,
            pnl=pnl,
            pnl_percent=pnl_percent,
            exit_reason=reason,
            metadata=pos.metadata.copy()
        )
        
        self.trades.append(trade)
        self.position = None
        
        return trade
    
    def process_bar(
        self,
        bar: pd.Series,
        timestamp: pd.Timestamp
    ) -> Optional[Trade]:
        """
        Process a bar and check for stop loss/take profit.
        
        Args:
            bar: OHLCV bar with 'high' and 'low' columns
            timestamp: Bar timestamp
            
        Returns:
            Trade if position was closed by SL/TP, else None
        """
        if self.position is None:
            return None
        
        high = bar['high']
        low = bar['low']
        
        # Check stop loss
        if self.position.check_stop_loss(low, high):
            sl_price = self.position.stop_loss
            return self.close_position(sl_price, timestamp, reason="stop_loss")
        
        # Check take profit
        if self.position.check_take_profit(low, high):
            tp_price = self.position.take_profit
            return self.close_position(tp_price, timestamp, reason="take_profit")
        
        return None
    
    def record_equity(self, timestamp: pd.Timestamp, price: float) -> None:
        """Record equity at a point in time."""
        equity = self.capital
        if self.position is not None:
            equity += self.position.unrealized_pnl(price)
        
        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': equity,
            'capital': self.capital,
            'has_position': self.position is not None
        })
    
    def get_equity_df(self) -> pd.DataFrame:
        """Get equity curve as DataFrame."""
        if not self.equity_curve:
            return pd.DataFrame()
        return pd.DataFrame(self.equity_curve).set_index('timestamp')
    
    @property
    def total_trades(self) -> int:
        return len(self.trades)
    
    @property
    def winning_trades(self) -> int:
        return sum(1 for t in self.trades if t.is_winner)
    
    @property
    def losing_trades(self) -> int:
        return sum(1 for t in self.trades if t.is_loser)
    
    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades * 100
    
    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)
    
    @property
    def total_return_percent(self) -> float:
        return (self.capital - self.initial_capital) / self.initial_capital * 100
