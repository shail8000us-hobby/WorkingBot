"""
Institutional-Grade Performance Analytics Module

This module provides professional-grade performance metrics used by top trading firms:
- Risk-adjusted returns (Sharpe, Sortino, Calmar, Information Ratios)
- Win/Loss statistics (Win Rate, Profit Factor, Expectancy)
- Drawdown analysis (Max DD, Average DD, Recovery Time)
- Trade quality metrics

Author: GridBot Pro - Institutional AI
Version: 1.0.0
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from bot.state.store import load_state_file
from typing import Dict, List, Any, Optional, Tuple, Iterator
import json
from pathlib import Path


def _iter_orders_jsonl(file_path: Path) -> Iterator[Dict[str, Any]]:
    """Iterate over JSON objects in a newline-delimited file, skipping empty sentinels."""
    if not file_path.exists():
        return
    try:
        with file_path.open('r', encoding='utf-8', errors='replace') as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict):
                            yield item
                    continue
                if isinstance(payload, dict):
                    yield payload
    except Exception:
        return


class PerformanceAnalytics:
    """
    Professional-grade performance analytics engine
    """
    
    def __init__(self, base_dir: str = None):
        """Initialize the performance analytics engine"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent.parent.parent
        self.cache = {}
        self.cache_ttl = 60  # Cache for 60 seconds
        self.last_cache_time = None
    
    # =========================================================================
    # RISK-ADJUSTED RETURNS
    # =========================================================================
    
    def calculate_sharpe_ratio(
        self, 
        returns: np.ndarray, 
        risk_free_rate: float = 0.05,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Sharpe Ratio - most widely used risk-adjusted return metric
        
        Formula: (Mean Return - Risk Free Rate) / Std Dev of Returns
        Annualized by multiplying by sqrt(periods per year)
        
        Args:
            returns: Array of returns
            risk_free_rate: Annual risk-free rate (default 5%)
            periods_per_year: Trading periods per year (252 for daily, 365*24 for hourly)
        
        Returns:
            Sharpe Ratio (higher is better, >2.0 is excellent)
        """
        if len(returns) == 0:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / periods_per_year)
        
        if np.std(excess_returns) == 0:
            return 0.0
        
        sharpe = np.mean(excess_returns) / np.std(excess_returns)
        annualized_sharpe = sharpe * np.sqrt(periods_per_year)
        
        return round(annualized_sharpe, 2)
    
    def calculate_sortino_ratio(
        self,
        returns: np.ndarray,
        risk_free_rate: float = 0.05,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Sortino Ratio - like Sharpe but only penalizes downside volatility
        
        Formula: (Mean Return - Risk Free Rate) / Downside Deviation
        
        Args:
            returns: Array of returns
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year
        
        Returns:
            Sortino Ratio (higher is better, >2.0 is excellent)
        """
        if len(returns) == 0:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / periods_per_year)
        
        # Only consider negative returns for downside deviation
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0 or np.std(downside_returns) == 0:
            return 0.0
        
        downside_std = np.std(downside_returns)
        sortino = np.mean(excess_returns) / downside_std
        annualized_sortino = sortino * np.sqrt(periods_per_year)
        
        return round(annualized_sortino, 2)
    
    def calculate_calmar_ratio(
        self,
        returns: np.ndarray,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Calmar Ratio - annual return divided by maximum drawdown
        
        Formula: Annualized Return / |Maximum Drawdown|
        
        Args:
            returns: Array of returns
            periods_per_year: Trading periods per year
        
        Returns:
            Calmar Ratio (higher is better, >1.0 is good)
        """
        if len(returns) == 0:
            return 0.0
        
        # Calculate annualized return
        total_return = np.prod(1 + returns) - 1
        num_periods = len(returns)
        annualized_return = (1 + total_return) ** (periods_per_year / num_periods) - 1
        
        # Calculate max drawdown
        cumulative_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = abs(np.min(drawdown))
        
        if max_drawdown == 0:
            return 0.0
        
        calmar = annualized_return / max_drawdown
        
        return round(calmar, 2)
    
    def calculate_information_ratio(
        self,
        returns: np.ndarray,
        benchmark_returns: Optional[np.ndarray] = None
    ) -> float:
        """
        Calculate Information Ratio - active return per unit of active risk
        
        Formula: (Portfolio Return - Benchmark Return) / Tracking Error
        
        Args:
            returns: Array of portfolio returns
            benchmark_returns: Array of benchmark returns (if None, uses 0)
        
        Returns:
            Information Ratio (higher is better, >0.5 is good)
        """
        if len(returns) == 0:
            return 0.0
        
        if benchmark_returns is None:
            benchmark_returns = np.zeros_like(returns)
        
        active_returns = returns - benchmark_returns
        tracking_error = np.std(active_returns)
        
        if tracking_error == 0:
            return 0.0
        
        information_ratio = np.mean(active_returns) / tracking_error
        
        return round(information_ratio, 2)
    
    # =========================================================================
    # WIN/LOSS STATISTICS
    # =========================================================================
    
    def calculate_win_rate(self, trades: List[Dict[str, Any]]) -> float:
        """
        Calculate win rate - percentage of profitable trades
        
        Args:
            trades: List of trade dictionaries with 'pnl' field
        
        Returns:
            Win rate as percentage (0-100)
        """
        if not trades:
            return 0.0
        
        winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        win_rate = (winning_trades / len(trades)) * 100
        
        return round(win_rate, 2)
    
    def calculate_profit_factor(self, trades: List[Dict[str, Any]]) -> float:
        """
        Calculate profit factor - ratio of gross profit to gross loss
        
        Formula: Sum(Winning Trades) / |Sum(Losing Trades)|
        
        Args:
            trades: List of trade dictionaries with 'pnl' field
        
        Returns:
            Profit factor (>1.0 is profitable, >1.5 is good, >2.0 is excellent)
        """
        if not trades:
            return 0.0
        
        gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
        
        if gross_loss == 0:
            # Return 0 instead of Infinity to avoid JSON serialization issues
            return 0.0 if gross_profit == 0 else 999.99
        
        profit_factor = gross_profit / gross_loss
        
        return round(profit_factor, 2)
    
    def calculate_expectancy(self, trades: List[Dict[str, Any]]) -> float:
        """
        Calculate expectancy - average expected profit per trade
        
        Formula: (Win% × Avg Win) - (Loss% × Avg Loss)
        
        Args:
            trades: List of trade dictionaries with 'pnl' field
        
        Returns:
            Expected profit per trade in INR
        """
        if not trades:
            return 0.0
        
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
        
        win_rate = len(winning_trades) / len(trades) if trades else 0
        loss_rate = len(losing_trades) / len(trades) if trades else 0
        
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = abs(np.mean([t['pnl'] for t in losing_trades])) if losing_trades else 0
        
        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
        
        return round(expectancy, 2)
    
    def calculate_avg_win_loss(self, trades: List[Dict[str, Any]]) -> Tuple[float, float]:
        """
        Calculate average win and average loss
        
        Args:
            trades: List of trade dictionaries with 'pnl' field
        
        Returns:
            Tuple of (avg_win, avg_loss) in INR
        """
        if not trades:
            return (0.0, 0.0)
        
        winning_trades = [t['pnl'] for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [abs(t['pnl']) for t in trades if t.get('pnl', 0) < 0]
        
        avg_win = np.mean(winning_trades) if winning_trades else 0.0
        avg_loss = np.mean(losing_trades) if losing_trades else 0.0
        
        return (round(avg_win, 2), round(avg_loss, 2))
    
    def calculate_risk_reward_ratio(self, trades: List[Dict[str, Any]]) -> float:
        """
        Calculate risk/reward ratio
        
        Formula: Average Win / Average Loss
        
        Args:
            trades: List of trade dictionaries with 'pnl' field
        
        Returns:
            Risk/Reward ratio (>1.0 means avg win > avg loss)
        """
        avg_win, avg_loss = self.calculate_avg_win_loss(trades)
        
        if avg_loss == 0:
            return 0.0
        
        risk_reward = avg_win / avg_loss
        
        return round(risk_reward, 2)
    
    # =========================================================================
    # DRAWDOWN ANALYSIS
    # =========================================================================
    
    def calculate_max_drawdown(self, equity_curve: np.ndarray) -> Dict[str, Any]:
        """
        Calculate maximum drawdown and related metrics
        
        Args:
            equity_curve: Array of equity values over time
        
        Returns:
            Dictionary with max_dd, max_dd_pct, start_idx, end_idx, recovery_idx
        """
        if len(equity_curve) == 0:
            return {
                'max_dd': 0.0,
                'max_dd_pct': 0.0,
                'start_idx': None,
                'end_idx': None,
                'recovery_idx': None,
                'duration_days': 0,
                'recovery_days': 0
            }
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(equity_curve)
        
        # Calculate drawdown at each point
        drawdown = equity_curve - running_max
        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            drawdown_pct = np.where(running_max != 0, (drawdown / running_max) * 100, 0.0)
        
        # Find maximum drawdown
        max_dd_idx = np.argmin(drawdown)
        max_dd = drawdown[max_dd_idx]
        max_dd_pct = drawdown_pct[max_dd_idx] if not np.isnan(drawdown_pct[max_dd_idx]) else 0.0
        
        # Find start of max drawdown (last peak before max dd)
        start_idx = np.where(equity_curve[:max_dd_idx] == running_max[max_dd_idx])[0]
        start_idx = start_idx[-1] if len(start_idx) > 0 else 0
        
        # Find recovery point (when equity exceeds previous peak)
        recovery_idx = None
        if max_dd_idx < len(equity_curve) - 1:
            recovery_points = np.where(equity_curve[max_dd_idx:] >= running_max[max_dd_idx])[0]
            if len(recovery_points) > 0:
                recovery_idx = max_dd_idx + recovery_points[0]
        
        duration_days = max_dd_idx - start_idx
        recovery_days = (recovery_idx - max_dd_idx) if recovery_idx else None
        
        return {
            'max_dd': round(max_dd, 2),
            'max_dd_pct': round(max_dd_pct, 2),
            'start_idx': int(start_idx),
            'end_idx': int(max_dd_idx),
            'recovery_idx': int(recovery_idx) if recovery_idx else None,
            'duration_days': int(duration_days),
            'recovery_days': int(recovery_days) if recovery_days else None
        }
    
    def calculate_average_drawdown(self, equity_curve: np.ndarray) -> float:
        """
        Calculate average drawdown
        
        Args:
            equity_curve: Array of equity values over time
        
        Returns:
            Average drawdown as percentage
        """
        if len(equity_curve) == 0:
            return 0.0
        
        running_max = np.maximum.accumulate(equity_curve)
        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            drawdown_pct = np.where(running_max != 0, ((equity_curve - running_max) / running_max) * 100, 0.0)
        
        # Only consider periods in drawdown (negative values)
        drawdowns = drawdown_pct[drawdown_pct < 0]
        
        if len(drawdowns) == 0:
            return 0.0
        
        avg_dd = np.mean(drawdowns)
        
        return round(avg_dd, 2)
    
    def calculate_current_drawdown(self, equity_curve: np.ndarray) -> float:
        """
        Calculate current drawdown from peak
        
        Args:
            equity_curve: Array of equity values over time
        
        Returns:
            Current drawdown as percentage
        """
        if len(equity_curve) == 0:
            return 0.0
        
        peak = np.max(equity_curve)
        current = equity_curve[-1]
        
        # Avoid division by zero
        if peak == 0:
            return 0.0
        
        current_dd_pct = ((current - peak) / peak) * 100
        
        return round(current_dd_pct, 2)
    
    # =========================================================================
    # DATA LOADING & CACHING
    # =========================================================================
    
    def _load_trades(self, lookback_days: int = 30) -> List[Dict[str, Any]]:
        """
        Load trade history from bot event store (REAL DATA)
        
        Args:
            lookback_days: Number of days to look back
        
        Returns:
            List of trade dictionaries with real PnL data
        """
        from .data_loader import get_data_loader
        
        # Get real trading data from event store
        data_loader = get_data_loader()
        pnl_data = data_loader.calculate_pnl_from_positions()
        
        # Convert to expected format
        trades = []
        for trade in pnl_data.get('trades', []):
            trades.append({
                'timestamp': trade['exit_time'].isoformat(),
                'entry_time': trade['entry_time'],
                'entry_price': trade['entry_price'],
                'exit_price': trade['exit_price'],
                'size': trade['size'],
                'pnl': trade['pnl'],
                'duration': trade['duration_seconds']
            })
        
        return trades
    
    def _load_equity_curve(self, lookback_days: int = 30) -> np.ndarray:
        """
        Load equity curve from real trade history (REAL DATA)
        
        Args:
            lookback_days: Number of days to look back
        
        Returns:
            Array of equity values calculated from real trades
        """
        from .data_loader import get_data_loader
        
        # Get real trading data
        data_loader = get_data_loader()
        pnl_data = data_loader.calculate_pnl_from_positions()
        
        # Get current balance from exchange
        balance_data = data_loader.get_account_balance()
        current_balance = balance_data.get('total_balance', 100000)
        
        # Build equity curve from trades
        trades = pnl_data.get('trades', [])
        if not trades:
            # No trades yet, return initial balance
            return np.array([current_balance])
        
        # Sort trades by time
        trades_sorted = sorted(trades, key=lambda t: t['entry_time'])
        
        # Calculate cumulative equity
        # Start with current balance minus total PnL to get initial balance
        total_pnl = sum(t['pnl'] for t in trades_sorted)
        initial_balance = current_balance - total_pnl
        
        equity_curve = [initial_balance]
        cumulative_pnl = 0
        
        for trade in trades_sorted:
            cumulative_pnl += trade['pnl']
            equity_curve.append(initial_balance + cumulative_pnl)
        
        return np.array(equity_curve)
    
    def _calculate_returns(self, equity_curve: np.ndarray) -> np.ndarray:
        """
        Calculate returns from equity curve
        
        Args:
            equity_curve: Array of equity values
        
        Returns:
            Array of returns
        """
        if len(equity_curve) < 2:
            return np.array([])
        
        returns = np.diff(equity_curve) / equity_curve[:-1]
        
        return returns
    
    # =========================================================================
    # COMPREHENSIVE ANALYSIS
    # =========================================================================
    
    def calculate_all_metrics(
        self,
        lookback_days: int = 30,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate all performance metrics
        
        Args:
            lookback_days: Number of days to analyze
            force_refresh: Force recalculation (ignore cache)
        
        Returns:
            Dictionary with all performance metrics
        """
        # Check cache
        if not force_refresh and self.last_cache_time:
            if (datetime.now() - self.last_cache_time).total_seconds() < self.cache_ttl:
                return self.cache
        
        # Load data
        trades = self._load_trades(lookback_days)
        equity_curve = self._load_equity_curve(lookback_days)
        returns = self._calculate_returns(equity_curve)
        
        # Calculate all metrics
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'lookback_days': lookback_days,
            'data_points': len(equity_curve),
            'total_trades': len(trades),
            
            # Risk-Adjusted Returns
            'risk_adjusted_returns': {
                'sharpe_ratio': self.calculate_sharpe_ratio(returns),
                'sortino_ratio': self.calculate_sortino_ratio(returns),
                'calmar_ratio': self.calculate_calmar_ratio(returns),
                'information_ratio': self.calculate_information_ratio(returns)
            },
            
            # Win/Loss Statistics
            'win_loss_stats': {
                'total_trades': len(trades),
                'wins': len([t for t in trades if t.get('pnl', 0) > 0]),
                'losses': len([t for t in trades if t.get('pnl', 0) < 0]),
                'win_rate': self.calculate_win_rate(trades),
                'profit_factor': self.calculate_profit_factor(trades),
                'expectancy': self.calculate_expectancy(trades),
                'avg_win': self.calculate_avg_win_loss(trades)[0],
                'avg_loss': self.calculate_avg_win_loss(trades)[1],
                'risk_reward_ratio': self.calculate_risk_reward_ratio(trades)
            },
            
            # Drawdown Analysis
            'drawdown_analysis': {
                'max_drawdown': self.calculate_max_drawdown(equity_curve),
                'avg_drawdown': self.calculate_average_drawdown(equity_curve),
                'current_drawdown': self.calculate_current_drawdown(equity_curve)
            },
            
            # Overall Performance
            'overall_performance': {
                'total_return': round(((equity_curve[-1] / equity_curve[0]) - 1) * 100, 2) if len(equity_curve) > 0 else 0.0,
                'total_pnl': round(sum(t.get('pnl', 0) for t in trades), 2),
                'winning_trades': len([t for t in trades if t.get('pnl', 0) > 0]),
                'losing_trades': len([t for t in trades if t.get('pnl', 0) < 0])
            }
        }
        
        # Update cache
        self.cache = metrics
        self.last_cache_time = datetime.now()
        
        return metrics
    
    def get_performance_grade(self, metrics: Dict[str, Any]) -> Dict[str, str]:
        """
        Assign grades to performance metrics
        
        Args:
            metrics: Dictionary of performance metrics
        
        Returns:
            Dictionary with grades (⭐ Excellent, ✓ Good, ⚠️ Fair, 🔴 Poor)
        """
        grades = {}
        
        # Sharpe Ratio
        sharpe = metrics['risk_adjusted_returns']['sharpe_ratio']
        if sharpe >= 2.0:
            grades['sharpe'] = '⭐'
        elif sharpe >= 1.0:
            grades['sharpe'] = '✓'
        elif sharpe >= 0.5:
            grades['sharpe'] = '⚠️'
        else:
            grades['sharpe'] = '🔴'
        
        # Win Rate
        win_rate = metrics['win_loss_stats']['win_rate']
        if win_rate >= 65:
            grades['win_rate'] = '⭐'
        elif win_rate >= 55:
            grades['win_rate'] = '✓'
        elif win_rate >= 45:
            grades['win_rate'] = '⚠️'
        else:
            grades['win_rate'] = '🔴'
        
        # Profit Factor
        pf = metrics['win_loss_stats']['profit_factor']
        if pf >= 2.0:
            grades['profit_factor'] = '⭐'
        elif pf >= 1.5:
            grades['profit_factor'] = '✓'
        elif pf >= 1.0:
            grades['profit_factor'] = '⚠️'
        else:
            grades['profit_factor'] = '🔴'
        
        # Max Drawdown
        max_dd = abs(metrics['drawdown_analysis']['max_drawdown']['max_dd_pct'])
        if max_dd <= 10:
            grades['max_dd'] = '⭐'
        elif max_dd <= 20:
            grades['max_dd'] = '✓'
        elif max_dd <= 30:
            grades['max_dd'] = '⚠️'
        else:
            grades['max_dd'] = '🔴'
        
        return grades


# Singleton accessor
_performance_analytics_instance = None

def get_performance_analytics() -> PerformanceAnalytics:
    """Get singleton instance of PerformanceAnalytics"""
    global _performance_analytics_instance
    if _performance_analytics_instance is None:
        _performance_analytics_instance = PerformanceAnalytics()
    return _performance_analytics_instance
