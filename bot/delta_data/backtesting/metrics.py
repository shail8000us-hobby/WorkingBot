"""
Backtest Metrics Calculation
============================

Calculates performance metrics for backtesting results.

Includes:
- Total return, CAGR
- Sharpe ratio, Sortino ratio
- Maximum drawdown
- Win rate, profit factor
- Average trade duration
- Risk-adjusted metrics

Author: WorkingBot
Date: January 2026
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import timedelta

from .position import Trade


@dataclass
class MetricsResult:
    """
    Container for backtest performance metrics.
    """
    # Return metrics
    total_return: float = 0.0
    total_return_percent: float = 0.0
    cagr: float = 0.0
    
    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    max_drawdown_duration_days: float = 0.0
    volatility_annual: float = 0.0
    
    # Risk-adjusted metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # Trade metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    
    # Average trade metrics
    avg_trade_pnl: float = 0.0
    avg_winning_trade: float = 0.0
    avg_losing_trade: float = 0.0
    avg_trade_duration_hours: float = 0.0
    
    # Best/worst trades
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0
    best_trade_percent: float = 0.0
    worst_trade_percent: float = 0.0
    
    # Consecutive trades
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # Exposure metrics
    time_in_market_percent: float = 0.0
    
    # Cost metrics
    total_commission: float = 0.0
    total_slippage: float = 0.0
    
    # Period info
    start_date: Optional[pd.Timestamp] = None
    end_date: Optional[pd.Timestamp] = None
    total_days: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'returns': {
                'total_return': self.total_return,
                'total_return_percent': self.total_return_percent,
                'cagr': self.cagr
            },
            'risk': {
                'max_drawdown': self.max_drawdown,
                'max_drawdown_percent': self.max_drawdown_percent,
                'max_drawdown_duration_days': self.max_drawdown_duration_days,
                'volatility_annual': self.volatility_annual
            },
            'risk_adjusted': {
                'sharpe_ratio': self.sharpe_ratio,
                'sortino_ratio': self.sortino_ratio,
                'calmar_ratio': self.calmar_ratio
            },
            'trades': {
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'win_rate': self.win_rate,
                'profit_factor': self.profit_factor,
                'avg_trade_pnl': self.avg_trade_pnl,
                'avg_winning_trade': self.avg_winning_trade,
                'avg_losing_trade': self.avg_losing_trade,
                'avg_trade_duration_hours': self.avg_trade_duration_hours,
                'best_trade_pnl': self.best_trade_pnl,
                'worst_trade_pnl': self.worst_trade_pnl,
                'max_consecutive_wins': self.max_consecutive_wins,
                'max_consecutive_losses': self.max_consecutive_losses
            },
            'exposure': {
                'time_in_market_percent': self.time_in_market_percent
            },
            'costs': {
                'total_commission': self.total_commission,
                'total_slippage': self.total_slippage
            },
            'period': {
                'start_date': str(self.start_date) if self.start_date else None,
                'end_date': str(self.end_date) if self.end_date else None,
                'total_days': self.total_days
            }
        }
    
    def summary(self) -> str:
        """Get formatted summary string."""
        return f"""
═══════════════════════════════════════════════════════════
                    BACKTEST RESULTS
═══════════════════════════════════════════════════════════

📈 RETURNS
   Total Return:       ${self.total_return:,.2f} ({self.total_return_percent:+.2f}%)
   CAGR:               {self.cagr:.2f}%

⚠️  RISK
   Max Drawdown:       ${abs(self.max_drawdown):,.2f} ({self.max_drawdown_percent:.2f}%)
   Max DD Duration:    {self.max_drawdown_duration_days:.1f} days
   Annual Volatility:  {self.volatility_annual:.2f}%

📊 RISK-ADJUSTED
   Sharpe Ratio:       {self.sharpe_ratio:.2f}
   Sortino Ratio:      {self.sortino_ratio:.2f}
   Calmar Ratio:       {self.calmar_ratio:.2f}

🎯 TRADES
   Total Trades:       {self.total_trades}
   Win Rate:           {self.win_rate:.1f}%
   Profit Factor:      {self.profit_factor:.2f}
   Avg Trade P&L:      ${self.avg_trade_pnl:,.2f}
   Best Trade:         ${self.best_trade_pnl:,.2f}
   Worst Trade:        ${self.worst_trade_pnl:,.2f}

⏱️  TIME
   Period:             {self.total_days:.0f} days
   Time in Market:     {self.time_in_market_percent:.1f}%

💰 COSTS
   Commission:         ${self.total_commission:,.2f}
   Slippage:           ${self.total_slippage:,.2f}

═══════════════════════════════════════════════════════════
"""


def calculate_metrics(
    trades: List[Trade],
    equity_curve: pd.DataFrame,
    initial_capital: float,
    final_capital: float,
    total_commission: float = 0.0,
    total_slippage: float = 0.0,
    risk_free_rate: float = 0.02,  # 2% annual
    trading_days_per_year: int = 365  # Crypto trades 24/7
) -> MetricsResult:
    """
    Calculate comprehensive backtest metrics.
    
    Args:
        trades: List of completed trades
        equity_curve: DataFrame with 'equity' column indexed by timestamp
        initial_capital: Starting capital
        final_capital: Ending capital
        total_commission: Total commission paid
        total_slippage: Total slippage paid
        risk_free_rate: Annual risk-free rate for Sharpe calculation
        trading_days_per_year: Trading days per year (365 for crypto)
        
    Returns:
        MetricsResult with all calculated metrics
    """
    metrics = MetricsResult()
    
    # Basic return metrics
    metrics.total_return = final_capital - initial_capital
    metrics.total_return_percent = (final_capital / initial_capital - 1) * 100
    metrics.total_commission = total_commission
    metrics.total_slippage = total_slippage
    
    # Period metrics
    if not equity_curve.empty:
        metrics.start_date = equity_curve.index[0]
        metrics.end_date = equity_curve.index[-1]
        metrics.total_days = (metrics.end_date - metrics.start_date).days
        
        if metrics.total_days > 0:
            # CAGR
            years = metrics.total_days / 365.0
            if years > 0 and final_capital > 0 and initial_capital > 0:
                metrics.cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
    
    # Calculate drawdown
    if not equity_curve.empty and 'equity' in equity_curve.columns:
        equity = equity_curve['equity']
        cummax = equity.cummax()
        drawdown = equity - cummax
        drawdown_pct = (drawdown / cummax) * 100
        
        metrics.max_drawdown = drawdown.min()
        metrics.max_drawdown_percent = drawdown_pct.min()
        
        # Calculate max drawdown duration
        is_in_drawdown = drawdown < 0
        if is_in_drawdown.any():
            drawdown_groups = (~is_in_drawdown).cumsum()
            dd_lengths = is_in_drawdown.groupby(drawdown_groups).sum()
            if len(dd_lengths) > 0:
                # Convert to days (assuming hourly data)
                max_dd_periods = dd_lengths.max()
                # Estimate time per period from equity curve
                if len(equity_curve) > 1:
                    avg_period_hours = (equity_curve.index[-1] - equity_curve.index[0]).total_seconds() / 3600 / len(equity_curve)
                    metrics.max_drawdown_duration_days = max_dd_periods * avg_period_hours / 24
    
    # Calculate volatility and risk-adjusted returns
    if not equity_curve.empty and 'equity' in equity_curve.columns:
        equity = equity_curve['equity']
        returns = equity.pct_change().dropna()
        
        if len(returns) > 1:
            # Annualized volatility
            daily_vol = returns.std()
            # Assume hourly data if timestamps suggest it
            if len(equity_curve) > 1:
                hours_per_bar = (equity_curve.index[-1] - equity_curve.index[0]).total_seconds() / 3600 / len(equity_curve)
                bars_per_year = (365 * 24) / max(hours_per_bar, 1)
            else:
                bars_per_year = 365 * 24
            
            metrics.volatility_annual = daily_vol * np.sqrt(bars_per_year) * 100
            
            # Sharpe Ratio
            risk_free_per_bar = risk_free_rate / bars_per_year
            excess_return = returns.mean() - risk_free_per_bar
            if daily_vol > 0:
                metrics.sharpe_ratio = (excess_return / daily_vol) * np.sqrt(bars_per_year)
            
            # Sortino Ratio (using downside deviation)
            downside_returns = returns[returns < 0]
            if len(downside_returns) > 0:
                downside_vol = downside_returns.std()
                if downside_vol > 0:
                    metrics.sortino_ratio = (excess_return / downside_vol) * np.sqrt(bars_per_year)
    
    # Calmar Ratio
    if metrics.max_drawdown_percent < 0 and metrics.cagr != 0:
        metrics.calmar_ratio = metrics.cagr / abs(metrics.max_drawdown_percent)
    
    # Trade metrics
    metrics.total_trades = len(trades)
    if trades:
        metrics.winning_trades = sum(1 for t in trades if t.pnl > 0)
        metrics.losing_trades = sum(1 for t in trades if t.pnl < 0)
        metrics.win_rate = (metrics.winning_trades / metrics.total_trades) * 100
        
        # Average trade metrics
        metrics.avg_trade_pnl = sum(t.pnl for t in trades) / metrics.total_trades
        metrics.avg_trade_duration_hours = sum(t.duration_hours for t in trades) / metrics.total_trades
        
        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl < 0]
        
        if winners:
            metrics.avg_winning_trade = sum(t.pnl for t in winners) / len(winners)
            metrics.best_trade_pnl = max(t.pnl for t in winners)
            metrics.best_trade_percent = max(t.pnl_percent for t in winners)
        
        if losers:
            metrics.avg_losing_trade = sum(t.pnl for t in losers) / len(losers)
            metrics.worst_trade_pnl = min(t.pnl for t in losers)
            metrics.worst_trade_percent = min(t.pnl_percent for t in losers)
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winners)
        gross_loss = abs(sum(t.pnl for t in losers))
        if gross_loss > 0:
            metrics.profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            metrics.profit_factor = float('inf')
        
        # Consecutive wins/losses
        metrics.max_consecutive_wins = _max_consecutive(trades, is_winner=True)
        metrics.max_consecutive_losses = _max_consecutive(trades, is_winner=False)
    
    # Time in market
    if not equity_curve.empty and 'has_position' in equity_curve.columns:
        metrics.time_in_market_percent = equity_curve['has_position'].mean() * 100
    
    return metrics


def _max_consecutive(trades: List[Trade], is_winner: bool) -> int:
    """Calculate max consecutive wins or losses."""
    max_streak = 0
    current_streak = 0
    
    for trade in trades:
        if (trade.pnl > 0) == is_winner:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
    
    return max_streak
