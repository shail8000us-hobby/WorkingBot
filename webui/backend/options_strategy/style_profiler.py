"""
Trading Style Profiler - Phase 2 of ML Autonomous Trading Engine

Analyzes trader's historical trades to build a complete profile of their trading style.
This is the foundation for the AI to "clone" the trader's decision-making process.

Created: January 17, 2026
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import json
import importlib.util
import sys

def _import_direct(name, path):
    """Import a module directly from file path without triggering __init__.py"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Import trade logger directly to avoid circular import issues
_trade_logger_module = _import_direct(
    'trade_logger_for_style_profiler',
    Path(__file__).parent / 'trade_logger.py'
)
trade_logger = _trade_logger_module.trade_logger


@dataclass
class TradingStyleDNA:
    """Complete profile of trader's style - the 'DNA' of their trading personality"""
    
    # Risk Profile (0-1 scale where applicable)
    risk_appetite: float = 0.5  # 0=conservative, 1=aggressive
    risk_consistency: float = 0.5  # How consistent is risk-taking
    max_loss_tolerance: float = 0.0  # Historical max single loss (absolute)
    drawdown_tolerance: float = 0.0  # Historical max drawdown accepted (percentage)
    
    # Timing Preferences
    preferred_entry_hours: List[int] = field(default_factory=list)  # Hours of day (0-23)
    preferred_days: List[int] = field(default_factory=list)  # Days of week (0=Mon, 6=Sun)
    avg_hold_duration_hours: float = 0.0
    patience_factor: float = 0.5  # 0=reactive, 1=patient
    
    # Market Condition Preferences
    volatility_preference: str = "medium"  # "low", "medium", "high"
    trend_preference: str = "neutral"  # "bullish", "neutral", "bearish", "both"
    
    # Position Management Style
    scaling_behavior: str = "all_in"  # "all_in", "scale_in", "scale_out"
    profit_taking_style: str = "mixed"  # "quick_profit", "let_it_run", "mixed"
    loss_cutting_speed: str = "moderate"  # "fast_cut", "moderate", "give_room"
    avg_position_size: float = 0.0
    
    # Strategy Preferences
    call_preference: float = 0.5  # 0=puts only, 0.5=balanced, 1=calls only
    buy_preference: float = 0.5  # 0=sell only, 0.5=balanced, 1=buy only
    preferred_strikes: List[str] = field(default_factory=list)  # "ITM", "ATM", "OTM"
    
    # Performance Metrics
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    
    # Behavioral Patterns
    trades_after_win: float = 0.0  # Avg trades per day after a win
    trades_after_loss: float = 0.0  # Avg trades per day after a loss
    revenge_trading_tendency: float = 0.0  # 0=none, 1=high
    
    # Confidence score for this profile
    confidence: float = 0.0  # 0=low data, 1=high confidence
    
    # Metadata
    total_trades_analyzed: int = 0
    analysis_date: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TradingStyleDNA':
        """Create from dictionary"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class StyleProfiler:
    """
    Analyzes historical trades to build a comprehensive trading style profile.
    
    The profile captures:
    - Risk tolerance and consistency
    - Timing preferences (when they trade best)
    - Market condition preferences
    - Position management style
    - Strategy preferences
    - Behavioral patterns
    """
    
    def __init__(self):
        self.data_dir = Path(__file__).parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        self.profile_file = self.data_dir / 'style_profile.json'
        self._cached_profile: Optional[TradingStyleDNA] = None
    
    def analyze_trading_style(self, min_trades: int = 10) -> TradingStyleDNA:
        """
        Comprehensive style analysis from trade history.
        
        Args:
            min_trades: Minimum trades required for analysis
            
        Returns:
            TradingStyleDNA object with complete profile
        """
        # Get all trades
        trades_df = trade_logger.get_all_trades()
        
        if len(trades_df) < min_trades:
            # Return default profile with low confidence
            return TradingStyleDNA(
                confidence=0.0,
                total_trades_analyzed=len(trades_df),
                analysis_date=datetime.now().isoformat()
            )
        
        profile = TradingStyleDNA()
        profile.total_trades_analyzed = len(trades_df)
        profile.analysis_date = datetime.now().isoformat()
        
        # Analyze each dimension
        profile.risk_appetite = self._analyze_risk_appetite(trades_df)
        profile.risk_consistency = self._analyze_risk_consistency(trades_df)
        profile.max_loss_tolerance, profile.drawdown_tolerance = self._analyze_loss_tolerance(trades_df)
        
        profile.preferred_entry_hours = self._find_preferred_hours(trades_df)
        profile.preferred_days = self._find_preferred_days(trades_df)
        profile.avg_hold_duration_hours = self._calculate_avg_hold_duration(trades_df)
        profile.patience_factor = self._analyze_patience(trades_df)
        
        profile.volatility_preference = self._analyze_volatility_preference(trades_df)
        profile.trend_preference = self._analyze_trend_preference(trades_df)
        
        profile.scaling_behavior = self._detect_scaling_behavior(trades_df)
        profile.profit_taking_style = self._analyze_profit_taking(trades_df)
        profile.loss_cutting_speed = self._analyze_loss_cutting(trades_df)
        profile.avg_position_size = self._calculate_avg_position_size(trades_df)
        
        profile.call_preference = self._calculate_call_preference(trades_df)
        profile.buy_preference = self._calculate_buy_preference(trades_df)
        profile.preferred_strikes = self._find_preferred_strikes(trades_df)
        
        profile.win_rate, profile.avg_win, profile.avg_loss, profile.profit_factor = self._calculate_performance(trades_df)
        
        profile.trades_after_win, profile.trades_after_loss = self._analyze_post_trade_behavior(trades_df)
        profile.revenge_trading_tendency = self._detect_revenge_trading(trades_df)
        
        # Calculate confidence based on data quality
        profile.confidence = self._calculate_confidence(trades_df)
        
        # Cache and save
        self._cached_profile = profile
        self._save_profile(profile)
        
        return profile
    
    def get_cached_profile(self) -> Optional[TradingStyleDNA]:
        """Get cached profile or load from file"""
        if self._cached_profile:
            return self._cached_profile
            
        if self.profile_file.exists():
            try:
                with open(self.profile_file) as f:
                    data = json.load(f)
                self._cached_profile = TradingStyleDNA.from_dict(data)
                return self._cached_profile
            except Exception:
                pass
        
        return None
    
    def _save_profile(self, profile: TradingStyleDNA):
        """Save profile to file"""
        with open(self.profile_file, 'w') as f:
            json.dump(profile.to_dict(), f, indent=2)
    
    # =====================================================================
    # ANALYSIS METHODS
    # =====================================================================
    
    def _analyze_risk_appetite(self, df: pd.DataFrame) -> float:
        """
        Calculate risk appetite (0-1).
        Based on position sizes relative to account, strike selection, etc.
        """
        if 'quantity' not in df.columns:
            return 0.5
            
        # Use position size variability as proxy for risk appetite
        quantities = df['quantity'].astype(float)
        if quantities.std() == 0:
            return 0.5
            
        # Normalize: higher coefficient of variation = higher risk appetite
        cv = quantities.std() / quantities.mean() if quantities.mean() > 0 else 0
        return min(1.0, cv)  # Cap at 1.0
    
    def _analyze_risk_consistency(self, df: pd.DataFrame) -> float:
        """
        Calculate risk consistency (0-1).
        1.0 = very consistent position sizing, 0.0 = highly variable
        """
        if 'quantity' not in df.columns:
            return 0.5
            
        quantities = df['quantity'].astype(float)
        if quantities.mean() == 0:
            return 0.5
            
        cv = quantities.std() / quantities.mean()
        # Invert: low CV = high consistency
        return max(0.0, 1.0 - cv)
    
    def _analyze_loss_tolerance(self, df: pd.DataFrame) -> tuple:
        """Calculate max loss tolerance and drawdown tolerance"""
        max_loss = 0.0
        drawdown = 0.0
        
        if 'outcome_pnl' in df.columns:
            pnls = df['outcome_pnl'].dropna().astype(float)
            if len(pnls) > 0:
                max_loss = abs(pnls.min()) if pnls.min() < 0 else 0
                
                # Calculate drawdown
                cumulative = pnls.cumsum()
                peak = cumulative.expanding().max()
                drawdowns = (cumulative - peak)
                drawdown = abs(drawdowns.min()) if len(drawdowns) > 0 else 0
        
        return max_loss, drawdown
    
    def _find_preferred_hours(self, df: pd.DataFrame) -> List[int]:
        """Find hours when trader is most active"""
        if 'timestamp' not in df.columns:
            return []
            
        try:
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            hour_counts = df['hour'].value_counts()
            
            # Get top 3 hours
            top_hours = hour_counts.nlargest(3).index.tolist()
            return sorted(top_hours)
        except Exception:
            return []
    
    def _find_preferred_days(self, df: pd.DataFrame) -> List[int]:
        """Find days when trader is most active"""
        if 'timestamp' not in df.columns:
            return []
            
        try:
            df['day'] = pd.to_datetime(df['timestamp']).dt.dayofweek
            day_counts = df['day'].value_counts()
            
            # Get days with above-average activity
            avg_activity = day_counts.mean()
            active_days = day_counts[day_counts >= avg_activity].index.tolist()
            return sorted(active_days)
        except Exception:
            return []
    
    def _calculate_avg_hold_duration(self, df: pd.DataFrame) -> float:
        """Calculate average hold duration in hours"""
        if 'duration_hours' in df.columns:
            durations = df['duration_hours'].dropna().astype(float)
            return durations.mean() if len(durations) > 0 else 0.0
        return 0.0
    
    def _analyze_patience(self, df: pd.DataFrame) -> float:
        """
        Analyze patience factor (0=reactive, 1=patient).
        Based on time between trades and hold duration.
        """
        if 'timestamp' not in df.columns:
            return 0.5
            
        try:
            timestamps = pd.to_datetime(df['timestamp']).sort_values()
            if len(timestamps) < 2:
                return 0.5
                
            # Calculate time between trades
            gaps = timestamps.diff().dropna()
            avg_gap_hours = gaps.mean().total_seconds() / 3600
            
            # Longer gaps = more patient
            # Normalize: 24 hours gap = 1.0 patience
            return min(1.0, avg_gap_hours / 24)
        except Exception:
            return 0.5
    
    def _analyze_volatility_preference(self, df: pd.DataFrame) -> str:
        """Determine volatility preference based on IV at trade time"""
        if 'iv' not in df.columns and 'market_iv' not in df.columns:
            return "medium"
            
        iv_col = 'iv' if 'iv' in df.columns else 'market_iv'
        ivs = df[iv_col].dropna().astype(float)
        
        if len(ivs) == 0:
            return "medium"
            
        avg_iv = ivs.mean()
        
        if avg_iv < 25:
            return "low"
        elif avg_iv > 50:
            return "high"
        return "medium"
    
    def _analyze_trend_preference(self, df: pd.DataFrame) -> str:
        """Determine trend preference based on trade directions"""
        call_pref = self._calculate_call_preference(df)
        
        if call_pref > 0.65:
            return "bullish"
        elif call_pref < 0.35:
            return "bearish"
        return "neutral"
    
    def _detect_scaling_behavior(self, df: pd.DataFrame) -> str:
        """Detect if trader scales in/out or goes all-in"""
        if 'symbol' not in df.columns:
            return "all_in"
            
        # Group by symbol and count trades
        symbol_trades = df.groupby('symbol').size()
        
        if len(symbol_trades) == 0:
            return "all_in"
            
        avg_trades_per_symbol = symbol_trades.mean()
        
        if avg_trades_per_symbol > 2.5:
            return "scale_in"
        elif avg_trades_per_symbol < 1.5:
            return "all_in"
        return "scale_out"
    
    def _analyze_profit_taking(self, df: pd.DataFrame) -> str:
        """Analyze profit-taking style"""
        if 'outcome_pnl' not in df.columns or 'duration_hours' not in df.columns:
            return "mixed"
            
        winners = df[df['outcome_pnl'].astype(float) > 0]
        if len(winners) == 0:
            return "mixed"
            
        avg_winner_duration = winners['duration_hours'].astype(float).mean()
        
        if avg_winner_duration < 2:
            return "quick_profit"
        elif avg_winner_duration > 24:
            return "let_it_run"
        return "mixed"
    
    def _analyze_loss_cutting(self, df: pd.DataFrame) -> str:
        """Analyze how quickly losses are cut"""
        if 'outcome_pnl' not in df.columns or 'duration_hours' not in df.columns:
            return "moderate"
            
        losers = df[df['outcome_pnl'].astype(float) < 0]
        if len(losers) == 0:
            return "moderate"
            
        avg_loser_duration = losers['duration_hours'].astype(float).mean()
        
        if avg_loser_duration < 1:
            return "fast_cut"
        elif avg_loser_duration > 12:
            return "give_room"
        return "moderate"
    
    def _calculate_avg_position_size(self, df: pd.DataFrame) -> float:
        """Calculate average position size"""
        if 'quantity' not in df.columns:
            return 0.0
        return df['quantity'].astype(float).mean()
    
    def _calculate_call_preference(self, df: pd.DataFrame) -> float:
        """
        Calculate preference for calls vs puts.
        0 = only puts, 0.5 = balanced, 1 = only calls
        """
        if 'option_type' not in df.columns:
            return 0.5
            
        total = len(df)
        if total == 0:
            return 0.5
            
        calls = len(df[df['option_type'].str.upper() == 'CALL'])
        return calls / total
    
    def _calculate_buy_preference(self, df: pd.DataFrame) -> float:
        """
        Calculate preference for buying vs selling.
        0 = only sell, 0.5 = balanced, 1 = only buy
        """
        if 'action' not in df.columns:
            return 0.5
            
        total = len(df)
        if total == 0:
            return 0.5
            
        buys = len(df[df['action'].str.upper() == 'BUY'])
        return buys / total
    
    def _find_preferred_strikes(self, df: pd.DataFrame) -> List[str]:
        """Find preferred strike types (ITM, ATM, OTM)"""
        # For now, return default - this would need spot price comparison
        return ["ATM"]
    
    def _calculate_performance(self, df: pd.DataFrame) -> tuple:
        """Calculate performance metrics"""
        if 'outcome_pnl' not in df.columns:
            return 0.0, 0.0, 0.0, 0.0
            
        pnls = df['outcome_pnl'].dropna().astype(float)
        
        if len(pnls) == 0:
            return 0.0, 0.0, 0.0, 0.0
            
        winners = pnls[pnls > 0]
        losers = pnls[pnls < 0]
        
        win_rate = len(winners) / len(pnls) if len(pnls) > 0 else 0
        avg_win = winners.mean() if len(winners) > 0 else 0
        avg_loss = abs(losers.mean()) if len(losers) > 0 else 0
        profit_factor = (winners.sum() / abs(losers.sum())) if len(losers) > 0 and losers.sum() != 0 else 0
        
        return win_rate, avg_win, avg_loss, profit_factor
    
    def _analyze_post_trade_behavior(self, df: pd.DataFrame) -> tuple:
        """Analyze trading behavior after wins/losses"""
        if 'timestamp' not in df.columns or 'outcome_pnl' not in df.columns:
            return 0.0, 0.0
            
        # This is a simplified version - could be expanded
        return 1.0, 1.0  # Default: same behavior after wins/losses
    
    def _detect_revenge_trading(self, df: pd.DataFrame) -> float:
        """
        Detect revenge trading tendency.
        0 = no revenge trading, 1 = strong tendency
        """
        if 'timestamp' not in df.columns or 'outcome_pnl' not in df.columns:
            return 0.0
            
        try:
            df = df.sort_values('timestamp')
            
            # Look for pattern: loss followed quickly by another trade
            revenge_count = 0
            total_losses = 0
            
            for i in range(len(df) - 1):
                pnl = float(df.iloc[i].get('outcome_pnl', 0) or 0)
                if pnl < 0:
                    total_losses += 1
                    # Check if next trade was within 1 hour
                    current_time = pd.to_datetime(df.iloc[i]['timestamp'])
                    next_time = pd.to_datetime(df.iloc[i + 1]['timestamp'])
                    gap = (next_time - current_time).total_seconds() / 3600
                    
                    if gap < 1:
                        revenge_count += 1
            
            return revenge_count / total_losses if total_losses > 0 else 0.0
        except Exception:
            return 0.0
    
    def _calculate_confidence(self, df: pd.DataFrame) -> float:
        """
        Calculate confidence in the profile based on data quality.
        """
        factors = []
        
        # Trade count factor
        trade_count = len(df)
        if trade_count >= 100:
            factors.append(1.0)
        elif trade_count >= 50:
            factors.append(0.8)
        elif trade_count >= 20:
            factors.append(0.5)
        else:
            factors.append(0.2)
        
        # Closed trades factor
        if 'outcome_pnl' in df.columns:
            closed = df['outcome_pnl'].notna().sum()
            closed_ratio = closed / trade_count if trade_count > 0 else 0
            factors.append(closed_ratio)
        else:
            factors.append(0.3)
        
        # Time span factor
        if 'timestamp' in df.columns:
            try:
                timestamps = pd.to_datetime(df['timestamp'])
                days = (timestamps.max() - timestamps.min()).days
                if days >= 30:
                    factors.append(1.0)
                elif days >= 14:
                    factors.append(0.7)
                else:
                    factors.append(0.4)
            except Exception:
                factors.append(0.3)
        else:
            factors.append(0.3)
        
        return sum(factors) / len(factors) if factors else 0.0
    
    def get_style_summary(self) -> Dict[str, Any]:
        """Get a human-readable summary of trading style"""
        profile = self.get_cached_profile()
        
        if not profile or profile.confidence < 0.2:
            return {
                'status': 'insufficient_data',
                'message': 'Need more trades to analyze style',
                'trades_analyzed': profile.total_trades_analyzed if profile else 0
            }
        
        return {
            'status': 'analyzed',
            'confidence': profile.confidence,
            'summary': {
                'risk_profile': 'Aggressive' if profile.risk_appetite > 0.6 else 'Conservative' if profile.risk_appetite < 0.4 else 'Moderate',
                'trading_times': f"Most active hours: {profile.preferred_entry_hours}",
                'style': profile.scaling_behavior.replace('_', ' ').title(),
                'bias': profile.trend_preference.title(),
                'win_rate': f"{profile.win_rate * 100:.1f}%",
                'avg_hold': f"{profile.avg_hold_duration_hours:.1f} hours",
            },
            'strengths': self._identify_strengths(profile),
            'areas_to_improve': self._identify_improvements(profile),
            'profile': profile.to_dict()
        }
    
    def _identify_strengths(self, profile: TradingStyleDNA) -> List[str]:
        """Identify trading strengths"""
        strengths = []
        
        if profile.win_rate > 0.5:
            strengths.append(f"Above-average win rate ({profile.win_rate * 100:.0f}%)")
        
        if profile.profit_factor > 1.5:
            strengths.append(f"Strong profit factor ({profile.profit_factor:.2f})")
        
        if profile.risk_consistency > 0.7:
            strengths.append("Consistent position sizing")
        
        if profile.loss_cutting_speed == "fast_cut":
            strengths.append("Quick to cut losses")
        
        if profile.revenge_trading_tendency < 0.2:
            strengths.append("Disciplined (no revenge trading)")
        
        return strengths if strengths else ["Keep trading to identify strengths"]
    
    def _identify_improvements(self, profile: TradingStyleDNA) -> List[str]:
        """Identify areas for improvement"""
        improvements = []
        
        if profile.win_rate < 0.45:
            improvements.append("Win rate below average - consider tighter entry criteria")
        
        if profile.profit_factor < 1.0 and profile.profit_factor > 0:
            improvements.append("Profit factor below 1 - losses exceed gains")
        
        if profile.revenge_trading_tendency > 0.5:
            improvements.append("High revenge trading tendency - consider taking breaks after losses")
        
        if profile.loss_cutting_speed == "give_room":
            improvements.append("Slow to cut losses - consider tighter stop losses")
        
        if profile.risk_consistency < 0.4:
            improvements.append("Inconsistent position sizing - consider standardizing")
        
        return improvements if improvements else ["Keep trading to identify improvements"]


# Singleton instance
style_profiler = StyleProfiler()
