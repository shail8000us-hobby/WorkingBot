"""
INSTITUTIONAL FEATURE: Kelly Criterion Position Sizing
=======================================================

What hedge funds use to size positions optimally.
This ACTUALLY WORKS - not educational bullshit.

The Kelly Formula:
    Position Size = (Win% × Avg_Win - Loss% × Avg_Loss) / Avg_Win

Example:
    - 55% win rate
    - Avg win: $300
    - Avg loss: $150
    
    Kelly% = (0.55 × 300 - 0.45 × 150) / 300
          = (165 - 67.5) / 300
          = 32.5% of capital
          
But we use FRACTIONAL KELLY (safer):
    - Half Kelly: 16.25%
    - Quarter Kelly: 8.12%
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class KellyPositionSizer:
    """
    Calculates optimal position size using Kelly Criterion.
    
    Used by: Renaissance Technologies, Citadel, DE Shaw
    """
    
    def __init__(self, 
                 history_file: str = "data/trade_history.json",
                 kelly_fraction: float = 0.25,  # Quarter Kelly (conservative)
                 min_trades: int = 20,          # Need sample size
                 lookback_days: int = 30):      # Recent performance matters
        
        self.history_file = history_file
        self.kelly_fraction = kelly_fraction
        self.min_trades = min_trades
        self.lookback_days = lookback_days
        
        # Track by strategy type
        self.strategy_stats = defaultdict(lambda: {
            'wins': 0,
            'losses': 0,
            'total_win_amount': 0.0,
            'total_loss_amount': 0.0,
            'trades': []
        })
    
    def add_trade(self, 
                  strategy: str,
                  pnl: float,
                  timestamp: Optional[datetime] = None) -> None:
        """
        Record a completed trade.
        
        Args:
            strategy: Strategy name (e.g., "iron_condor", "straddle")
            pnl: Profit/loss in dollars
            timestamp: When trade closed (default: now)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        stats = self.strategy_stats[strategy]
        
        trade = {
            'pnl': pnl,
            'timestamp': timestamp.isoformat()
        }
        
        stats['trades'].append(trade)
        
        if pnl > 0:
            stats['wins'] += 1
            stats['total_win_amount'] += pnl
        else:
            stats['losses'] += 1
            stats['total_loss_amount'] += abs(pnl)
        
        # Persist to disk
        self._save_history()
    
    def calculate_kelly_size(self, 
                            strategy: str,
                            account_balance: float) -> Dict:
        """
        Calculate optimal position size using Kelly Criterion.
        
        Returns:
            {
                'kelly_percent': 0.15,          # 15% of account
                'position_size_usd': 15000,     # Actual dollar amount
                'max_contracts': 3,              # If each costs $5000
                'confidence': 'HIGH',            # HIGH/MEDIUM/LOW
                'stats': {...}                   # Win rate, avg win/loss
            }
        """
        stats = self._get_recent_stats(strategy)
        
        # Need minimum sample size
        total_trades = stats['wins'] + stats['losses']
        if total_trades < self.min_trades:
            return {
                'kelly_percent': 0.01,  # 1% default (very conservative)
                'position_size_usd': account_balance * 0.01,
                'max_contracts': 0,
                'confidence': 'LOW',
                'reason': f'Only {total_trades} trades, need {self.min_trades}',
                'stats': stats
            }
        
        # Calculate win rate
        win_rate = stats['wins'] / total_trades
        loss_rate = 1 - win_rate
        
        # Average win/loss per trade
        avg_win = stats['total_win_amount'] / stats['wins'] if stats['wins'] > 0 else 0
        avg_loss = stats['total_loss_amount'] / stats['losses'] if stats['losses'] > 0 else 1
        
        # Kelly Formula
        if avg_win <= 0 or avg_loss <= 0:
            kelly_percent = 0.01
        else:
            kelly_percent = (win_rate * avg_win - loss_rate * avg_loss) / avg_win
        
        # Apply fractional Kelly (safety margin)
        kelly_percent *= self.kelly_fraction
        
        # Cap at reasonable limits
        kelly_percent = max(0.0, min(kelly_percent, 0.25))  # 0-25% max
        
        # Determine confidence level
        if total_trades >= 50 and win_rate >= 0.50:
            confidence = 'HIGH'
        elif total_trades >= 30 and win_rate >= 0.45:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'
        
        position_size_usd = account_balance * kelly_percent
        
        return {
            'kelly_percent': round(kelly_percent, 4),
            'position_size_usd': round(position_size_usd, 2),
            'max_contracts': 0,  # Caller calculates based on premium
            'confidence': confidence,
            'stats': {
                'total_trades': total_trades,
                'win_rate': round(win_rate, 3),
                'avg_win_usd': round(avg_win, 2),
                'avg_loss_usd': round(avg_loss, 2),
                'win_loss_ratio': round(avg_win / avg_loss, 2) if avg_loss > 0 else 0,
                'expectancy': round(win_rate * avg_win - loss_rate * avg_loss, 2)
            }
        }
    
    def _get_recent_stats(self, strategy: str) -> Dict:
        """Get stats for recent trades only (respects lookback window)."""
        stats = self.strategy_stats[strategy]
        cutoff = datetime.now() - timedelta(days=self.lookback_days)
        
        recent_trades = [
            t for t in stats['trades']
            if datetime.fromisoformat(t['timestamp']) >= cutoff
        ]
        
        result = {
            'wins': 0,
            'losses': 0,
            'total_win_amount': 0.0,
            'total_loss_amount': 0.0
        }
        
        for trade in recent_trades:
            pnl = trade['pnl']
            if pnl > 0:
                result['wins'] += 1
                result['total_win_amount'] += pnl
            else:
                result['losses'] += 1
                result['total_loss_amount'] += abs(pnl)
        
        return result
    
    def get_all_strategies_sizing(self, account_balance: float) -> Dict[str, Dict]:
        """Get Kelly sizing for all strategies you're trading."""
        results = {}
        for strategy in self.strategy_stats.keys():
            results[strategy] = self.calculate_kelly_size(strategy, account_balance)
        return results
    
    def _save_history(self) -> None:
        """Persist trade history to disk."""
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        
        # Convert defaultdict to regular dict for JSON
        data = {k: dict(v) for k, v in self.strategy_stats.items()}
        
        with open(self.history_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_history(self) -> None:
        """Load trade history from disk."""
        if not os.path.exists(self.history_file):
            return
        
        try:
            with open(self.history_file, 'r') as f:
                data = json.load(f)
            
            for strategy, stats in data.items():
                self.strategy_stats[strategy] = stats
        except Exception as e:
            print(f"Warning: Could not load history: {e}")


# ============================================================================
# USAGE EXAMPLE (Copy this to your bot)
# ============================================================================

def example_usage():
    """How to use Kelly sizer in your bot."""
    
    # Initialize
    kelly = KellyPositionSizer(
        history_file="data/kelly_history.json",
        kelly_fraction=0.25,  # Quarter Kelly (conservative)
        min_trades=20,
        lookback_days=30
    )
    
    # Load existing history
    kelly.load_history()
    
    # Record trades as they close
    kelly.add_trade("iron_condor", pnl=250)    # Win
    kelly.add_trade("iron_condor", pnl=-180)   # Loss
    kelly.add_trade("straddle", pnl=420)       # Win
    kelly.add_trade("straddle", pnl=-310)      # Loss
    
    # Get optimal position size
    account_balance = 100000  # $100k account
    
    sizing = kelly.calculate_kelly_size("iron_condor", account_balance)
    
    print(f"""
    KELLY POSITION SIZER RESULT
    ===========================
    
    Strategy: Iron Condor
    Account: ${account_balance:,.0f}
    
    RECOMMENDATION:
    → Risk per trade: {sizing['kelly_percent']*100:.1f}% of account
    → Position size: ${sizing['position_size_usd']:,.0f}
    → Confidence: {sizing['confidence']}
    """)
    
    if 'stats' in sizing:
        stats = sizing['stats']
        print(f"""
    STATISTICS:
    → Total trades: {stats.get('total_trades', 0)}
    → Win rate: {stats.get('win_rate', 0)*100:.1f}%
    → Avg win: ${stats.get('avg_win_usd', 0):,.0f}
    → Avg loss: ${stats.get('avg_loss_usd', 0):,.0f}
    → Win/Loss ratio: {stats.get('win_loss_ratio', 0):.2f}x
    → Expectancy: ${stats.get('expectancy', 0):,.0f} per trade
    """)
    
    if 'reason' in sizing:
        print(f"    NOTE: {sizing['reason']}")
    
    # Get sizing for all your strategies
    all_sizing = kelly.get_all_strategies_sizing(account_balance)
    for strategy, data in all_sizing.items():
        print(f"{strategy}: Risk {data['kelly_percent']*100:.1f}% → ${data['position_size_usd']:,.0f}")


if __name__ == "__main__":
    example_usage()
