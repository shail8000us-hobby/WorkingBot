"""
Backtest Accounting & Metrics

Calculates performance metrics from backtest results.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime

log = logging.getLogger("backtest.metrics")


class BacktestAccountant:
    """
    Calculate backtest performance metrics.
    
    Metrics:
    - Total/realized/unrealized PnL
    - Equity curve
    - Maximum drawdown
    - Win rate
    - Number of trades (entries/exits/cycles)
    - Sharpe ratio (simplified for 1m bars)
    - Exposure metrics
    """
    
    def __init__(
        self,
        trades_df: pd.DataFrame,
        initial_balance: float = 0.0,
        symbol: str = "BTC/USD:USD"
    ):
        """
        Initialize accountant.
        
        Args:
            trades_df: Trade log DataFrame from SimExchange
            initial_balance: Starting balance
            symbol: Trading symbol
        """
        self.trades_df = trades_df
        self.initial_balance = initial_balance
        self.symbol = symbol
    
    def calculate_metrics(self) -> Dict:
        """
        Calculate all performance metrics.
        
        Returns:
            Dict with metrics
        """
        if self.trades_df.empty:
            return self._empty_metrics()
        
        # Basic trade stats
        total_trades = len(self.trades_df)
        entries = len(self.trades_df[~self.trades_df['reduce_only']])
        exits = len(self.trades_df[self.trades_df['reduce_only']])
        cycles = min(entries, exits)  # Complete round trips
        
        # PnL metrics
        total_fees = self.trades_df['fee'].sum()
        total_realized_pnl = self.trades_df['realized_pnl'].sum()
        
        # Win rate (on closed positions)
        winning_trades = self.trades_df[
            (self.trades_df['reduce_only']) & 
            (self.trades_df['realized_pnl'] > 0)
        ]
        losing_trades = self.trades_df[
            (self.trades_df['reduce_only']) & 
            (self.trades_df['realized_pnl'] < 0)
        ]
        
        win_rate = (
            len(winning_trades) / len(self.trades_df[self.trades_df['reduce_only']])
            if exits > 0
            else 0.0
        )
        
        # Average win/loss
        avg_win = winning_trades['realized_pnl'].mean() if len(winning_trades) > 0 else 0.0
        avg_loss = losing_trades['realized_pnl'].mean() if len(losing_trades) > 0 else 0.0
        
        # Profit factor
        total_wins = winning_trades['realized_pnl'].sum() if len(winning_trades) > 0 else 0.0
        total_losses = abs(losing_trades['realized_pnl'].sum()) if len(losing_trades) > 0 else 0.0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf') if total_wins > 0 else 0.0
        
        # Build equity curve
        equity_df = self._build_equity_curve()
        
        # Drawdown analysis
        max_dd, max_dd_pct, dd_duration = self._calculate_drawdown(equity_df)
        
        # Sharpe-like ratio (simplified)
        sharpe = self._calculate_sharpe(equity_df)
        
        # Exposure metrics
        max_position = self.trades_df['position_size_after'].abs().max() if 'position_size_after' in self.trades_df else 0
        
        # Time metrics
        start_time = self.trades_df['timestamp'].min()
        end_time = self.trades_df['timestamp'].max()
        duration_days = (end_time - start_time).total_seconds() / 86400
        
        # Net PnL (after fees)
        net_pnl = total_realized_pnl - total_fees
        
        # Return on initial balance
        roi = (net_pnl / self.initial_balance * 100) if self.initial_balance > 0 else 0.0
        
        return {
            # Trade counts
            'total_trades': total_trades,
            'entries': entries,
            'exits': exits,
            'cycles': cycles,
            
            # PnL
            'gross_pnl': total_realized_pnl,
            'total_fees': total_fees,
            'net_pnl': net_pnl,
            'final_equity': self.initial_balance + net_pnl,
            'roi_pct': roi,
            
            # Win/Loss
            'win_rate': win_rate,
            'wins': len(winning_trades),
            'losses': len(losing_trades),
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'largest_win': winning_trades['realized_pnl'].max() if len(winning_trades) > 0 else 0.0,
            'largest_loss': losing_trades['realized_pnl'].min() if len(losing_trades) > 0 else 0.0,
            
            # Risk metrics
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd_pct,
            'drawdown_duration_days': dd_duration,
            'sharpe_ratio': sharpe,
            
            # Exposure
            'max_position_size': max_position,
            
            # Time
            'start_time': start_time,
            'end_time': end_time,
            'duration_days': duration_days,
            'trades_per_day': total_trades / duration_days if duration_days > 0 else 0.0
        }
    
    def _empty_metrics(self) -> Dict:
        """Return empty metrics template."""
        return {
            'total_trades': 0,
            'entries': 0,
            'exits': 0,
            'cycles': 0,
            'gross_pnl': 0.0,
            'total_fees': 0.0,
            'net_pnl': 0.0,
            'final_equity': self.initial_balance,
            'roi_pct': 0.0,
            'win_rate': 0.0,
            'wins': 0,
            'losses': 0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_pct': 0.0,
            'drawdown_duration_days': 0.0,
            'sharpe_ratio': 0.0,
            'max_position_size': 0,
            'start_time': None,
            'end_time': None,
            'duration_days': 0.0,
            'trades_per_day': 0.0
        }
    
    def _build_equity_curve(self) -> pd.DataFrame:
        """
        Build equity curve from trade log.
        
        Returns:
            DataFrame with columns: timestamp, equity
        """
        if self.trades_df.empty:
            return pd.DataFrame(columns=['timestamp', 'equity'])
        
        df = self.trades_df.copy()
        df = df.sort_values('timestamp')
        
        # Calculate cumulative PnL
        df['cumulative_pnl'] = (df['realized_pnl'] - df['fee']).cumsum()
        df['equity'] = self.initial_balance + df['cumulative_pnl']
        
        return df[['timestamp', 'equity']]
    
    def _calculate_drawdown(
        self,
        equity_df: pd.DataFrame
    ) -> Tuple[float, float, float]:
        """
        Calculate maximum drawdown.
        
        Returns:
            (max_drawdown_absolute, max_drawdown_percent, duration_days)
        """
        if equity_df.empty:
            return 0.0, 0.0, 0.0
        
        equity = equity_df['equity'].values
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(equity)
        
        # Calculate drawdown
        drawdown = running_max - equity
        drawdown_pct = (drawdown / running_max) * 100
        
        # Find maximum
        max_dd = drawdown.max()
        max_dd_pct = drawdown_pct.max()
        
        # Find drawdown duration
        max_dd_idx = drawdown.argmax()
        
        # Find when drawdown started (last peak before max dd)
        peak_idx = np.where(equity[:max_dd_idx+1] == running_max[max_dd_idx])[0]
        peak_idx = peak_idx[-1] if len(peak_idx) > 0 else 0
        
        # Find when recovered (or end of data)
        recovery_idx = np.where(equity[max_dd_idx:] >= running_max[max_dd_idx])[0]
        recovery_idx = recovery_idx[0] + max_dd_idx if len(recovery_idx) > 0 else len(equity) - 1
        
        # Calculate duration
        if peak_idx < len(equity_df) and recovery_idx < len(equity_df):
            start_time = equity_df.iloc[peak_idx]['timestamp']
            end_time = equity_df.iloc[recovery_idx]['timestamp']
            duration = (end_time - start_time).total_seconds() / 86400  # days
        else:
            duration = 0.0
        
        return max_dd, max_dd_pct, duration
    
    def _calculate_sharpe(
        self,
        equity_df: pd.DataFrame,
        risk_free_rate: float = 0.0
    ) -> float:
        """
        Calculate Sharpe-like ratio.
        
        Note: Simplified for 1m bars. Not annualized properly.
        Use for relative comparison, not absolute measurement.
        """
        if len(equity_df) < 2:
            return 0.0
        
        # Calculate returns
        returns = equity_df['equity'].pct_change().dropna()
        
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        
        # Mean return
        mean_return = returns.mean()
        
        # Volatility (standard deviation)
        volatility = returns.std()
        
        # Sharpe ratio
        sharpe = (mean_return - risk_free_rate) / volatility
        
        # Annualize (very rough for 1m bars)
        # ~525,600 1m bars per year
        sharpe_annualized = sharpe * np.sqrt(525600)
        
        return sharpe_annualized
    
    def generate_report(self) -> str:
        """Generate human-readable text report."""
        metrics = self.calculate_metrics()
        
        report = f"""
╔══════════════════════════════════════════════════════════════════╗
║                    BACKTEST PERFORMANCE REPORT                   ║
╚══════════════════════════════════════════════════════════════════╝

Symbol: {self.symbol}
Period: {metrics['start_time']} to {metrics['end_time']}
Duration: {metrics['duration_days']:.1f} days

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRADES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Trades:        {metrics['total_trades']:>6}
Entries (BUY):       {metrics['entries']:>6}
Exits (TP):          {metrics['exits']:>6}
Complete Cycles:     {metrics['cycles']:>6}
Trades/Day:          {metrics['trades_per_day']:>6.1f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PNL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Gross PnL:           ${metrics['gross_pnl']:>10.2f}
Total Fees:          ${metrics['total_fees']:>10.2f}
Net PnL:             ${metrics['net_pnl']:>10.2f}
Initial Balance:     ${self.initial_balance:>10.2f}
Final Equity:        ${metrics['final_equity']:>10.2f}
ROI:                 {metrics['roi_pct']:>10.2f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WIN/LOSS ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Win Rate:            {metrics['win_rate']*100:>10.2f}%
Wins:                {metrics['wins']:>6}  (Avg: ${metrics['avg_win']:.2f})
Losses:              {metrics['losses']:>6}  (Avg: ${metrics['avg_loss']:.2f})
Profit Factor:       {metrics['profit_factor']:>10.2f}
Largest Win:         ${metrics['largest_win']:>10.2f}
Largest Loss:        ${metrics['largest_loss']:>10.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RISK METRICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Max Drawdown:        ${metrics['max_drawdown']:>10.2f}  ({metrics['max_drawdown_pct']:.2f}%)
DD Duration:         {metrics['drawdown_duration_days']:>10.1f} days
Sharpe Ratio:        {metrics['sharpe_ratio']:>10.2f}
Max Position:        {metrics['max_position_size']:>6.0f} contracts

╚══════════════════════════════════════════════════════════════════╝
"""
        return report

