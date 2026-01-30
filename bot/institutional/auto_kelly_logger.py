"""
Auto Kelly Trade Logger

Automatically records trades to Kelly sizer when positions are closed.
Integrates with options_control.py close endpoint.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from bot.institutional.kelly_position_sizer import KellyPositionSizer

log = logging.getLogger(__name__)

_kelly_sizer = None

def get_auto_kelly():
    """Get singleton Kelly sizer instance."""
    global _kelly_sizer
    if _kelly_sizer is None:
        _kelly_sizer = KellyPositionSizer(
            history_file="data/kelly_trade_history.json",
            kelly_fraction=0.25,
            min_trades=20,
            lookback_days=30
        )
        _kelly_sizer.load_history()
    return _kelly_sizer


def auto_record_trade(
    symbol: str,
    pnl: float,
    strategy_tag: str = "manual",
    entry_price: float = 0,
    exit_price: float = 0,
    size: int = 0
) -> bool:
    """
    Automatically record trade to Kelly sizer.
    
    Call this from options_control.py close endpoint after position closes.
    
    Args:
        symbol: Options symbol (e.g., "P-BTC-94000-140126")
        pnl: Realized P&L in dollars
        strategy_tag: Strategy type ("iron_condor", "straddle", "strangle", "manual")
        entry_price: Entry price (optional, for logging)
        exit_price: Exit price (optional, for logging)
        size: Position size (optional, for logging)
        
    Returns:
        bool: True if recorded successfully
    """
    try:
        kelly = get_auto_kelly()
        
        # Extract strategy from symbol or tag
        if strategy_tag == "manual":
            # Try to infer from symbol
            if "straddle" in symbol.lower():
                strategy = "straddle"
            elif "iron" in symbol.lower() or "condor" in symbol.lower():
                strategy = "iron_condor"
            elif "strangle" in symbol.lower():
                strategy = "strangle"
            elif symbol.startswith("C-") or symbol.startswith("P-"):
                strategy = "single_leg"
            else:
                strategy = "manual"
        else:
            strategy = strategy_tag
        
        # Record the trade
        kelly.add_trade(strategy, pnl, datetime.now())
        
        log.info(f"✅ Kelly auto-record: {strategy} PnL=${pnl:.2f} from {symbol}")
        return True
        
    except Exception as e:
        log.error(f"❌ Kelly auto-record failed: {e}")
        return False


def should_size_down(strategy: str, account_balance: float) -> Dict:
    """
    Check if Kelly recommends reducing position size due to losses.
    
    Call this before opening new positions to check if you're trading too large.
    
    Returns:
        {
            "should_reduce": bool,
            "current_kelly_pct": 0.08,
            "recommended_size_usd": 8000,
            "reason": "Recent win rate declining to 42%"
        }
    """
    try:
        kelly = get_auto_kelly()
        sizing = kelly.calculate_kelly_size(strategy, account_balance)
        
        # Check if Kelly dropped significantly (more than 50% reduction)
        previous_default = 0.05  # Assume 5% default
        current_kelly = sizing['kelly_percent']
        
        if current_kelly < previous_default * 0.5:
            return {
                'should_reduce': True,
                'current_kelly_pct': current_kelly,
                'recommended_size_usd': sizing['position_size_usd'],
                'reason': f"Kelly reduced to {current_kelly*100:.1f}% due to recent performance",
                'stats': sizing.get('stats', {})
            }
        
        return {
            'should_reduce': False,
            'current_kelly_pct': current_kelly,
            'recommended_size_usd': sizing['position_size_usd']
        }
        
    except Exception as e:
        log.error(f"Kelly size check failed: {e}")
        return {
            'should_reduce': False,
            'error': str(e)
        }
