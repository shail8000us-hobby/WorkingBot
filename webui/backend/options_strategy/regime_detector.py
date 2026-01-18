"""
Market Regime Detector - Phase 3 of ML Autonomous Trading Engine

Detects current market conditions (trend, volatility, momentum) to help
match opportunities to trader's style preferences.

Created: January 18, 2026
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json
import math


@dataclass
class MarketRegime:
    """Current market regime classification"""
    
    # Trend classification
    trend: str = "neutral"  # strong_up, moderate_up, neutral, moderate_down, strong_down
    trend_strength: float = 0.0  # 0-1
    
    # Volatility classification
    volatility: str = "normal"  # low, normal, elevated, extreme
    volatility_percentile: float = 50.0  # 0-100
    current_iv: float = 0.0
    
    # Momentum
    momentum: str = "steady"  # accelerating, steady, fading, reversing
    momentum_score: float = 0.0  # -1 to 1
    
    # Support/Resistance
    price_location: str = "mid_range"  # near_support, mid_range, near_resistance
    distance_to_support_pct: float = 0.0
    distance_to_resistance_pct: float = 0.0
    
    # Price data
    current_price: float = 0.0
    price_24h_change_pct: float = 0.0
    price_7d_change_pct: float = 0.0
    
    # Metadata
    symbol: str = ""
    analyzed_at: str = ""
    confidence: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def get_summary(self) -> str:
        """Get human-readable summary"""
        return f"{self.trend.replace('_', ' ').title()} trend, {self.volatility} volatility, {self.momentum} momentum"


class MarketRegimeDetector:
    """
    Detects current market regime for trading decisions.
    
    Uses:
    - Price action analysis
    - Volatility measurement
    - Momentum indicators
    - Support/resistance levels
    """
    
    def __init__(self):
        self.data_dir = Path(__file__).parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        self.regime_file = self.data_dir / 'market_regime.json'
        self._cached_regime: Optional[MarketRegime] = None
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=5)
        
        # Historical data for analysis
        self._price_history: List[Dict] = []
        self._iv_history: List[float] = []
    
    def detect_regime(
        self, 
        symbol: str = "BTC",
        current_price: float = 0,
        iv: float = 0,
        price_history: Optional[List[Dict]] = None
    ) -> MarketRegime:
        """
        Detect current market regime.
        
        Args:
            symbol: Symbol to analyze
            current_price: Current spot price
            iv: Current implied volatility
            price_history: Optional list of price candles
            
        Returns:
            MarketRegime with classifications
        """
        regime = MarketRegime(symbol=symbol, analyzed_at=datetime.now().isoformat())
        
        if current_price <= 0:
            # Try to get from cache
            cached = self.get_cached_regime(symbol)
            if cached:
                return cached
            return regime
        
        regime.current_price = current_price
        regime.current_iv = iv
        
        # Analyze trend
        if price_history:
            trend, strength = self._analyze_trend(price_history)
            regime.trend = trend
            regime.trend_strength = strength
            
            # Calculate price changes
            if len(price_history) > 0:
                first_price = price_history[0].get('close', current_price)
                regime.price_24h_change_pct = ((current_price - first_price) / first_price) * 100
        else:
            # Use simple heuristics
            regime.trend = "neutral"
            regime.trend_strength = 0.5
        
        # Analyze volatility
        vol_class, vol_pct = self._classify_volatility(iv)
        regime.volatility = vol_class
        regime.volatility_percentile = vol_pct
        
        # Analyze momentum
        if price_history:
            momentum, score = self._analyze_momentum(price_history)
            regime.momentum = momentum
            regime.momentum_score = score
        else:
            regime.momentum = "steady"
            regime.momentum_score = 0
        
        # Analyze price location (support/resistance)
        if price_history:
            location, dist_support, dist_resist = self._analyze_price_location(
                current_price, price_history
            )
            regime.price_location = location
            regime.distance_to_support_pct = dist_support
            regime.distance_to_resistance_pct = dist_resist
        
        # Calculate confidence
        regime.confidence = self._calculate_confidence(price_history)
        
        # Cache and save
        self._cached_regime = regime
        self._cache_time = datetime.now()
        self._save_regime(regime)
        
        return regime
    
    def _analyze_trend(self, price_history: List[Dict]) -> Tuple[str, float]:
        """
        Analyze price trend from history.
        
        Returns:
            Tuple of (trend classification, strength 0-1)
        """
        if len(price_history) < 3:
            return "neutral", 0.5
        
        # Calculate simple moving averages
        closes = [p.get('close', 0) for p in price_history if p.get('close')]
        if not closes:
            return "neutral", 0.5
        
        current = closes[-1]
        
        # Short-term average (last 1/3)
        short_period = max(1, len(closes) // 3)
        short_avg = sum(closes[-short_period:]) / short_period
        
        # Long-term average (all data)
        long_avg = sum(closes) / len(closes)
        
        # Calculate trend
        trend_pct = ((current - long_avg) / long_avg) * 100 if long_avg > 0 else 0
        
        if trend_pct > 5:
            return "strong_up", min(1.0, trend_pct / 10)
        elif trend_pct > 2:
            return "moderate_up", 0.6 + (trend_pct - 2) / 10
        elif trend_pct > -2:
            return "neutral", 0.5
        elif trend_pct > -5:
            return "moderate_down", 0.6 + abs(trend_pct + 2) / 10
        else:
            return "strong_down", min(1.0, abs(trend_pct) / 10)
    
    def _classify_volatility(self, iv: float) -> Tuple[str, float]:
        """
        Classify volatility level.
        
        Args:
            iv: Implied volatility percentage
            
        Returns:
            Tuple of (classification, percentile estimate)
        """
        if iv <= 0:
            return "normal", 50.0
        
        # BTC IV typical ranges (adjust based on historical data)
        if iv < 25:
            return "low", 25.0
        elif iv < 40:
            return "normal", 50.0
        elif iv < 60:
            return "elevated", 75.0
        else:
            return "extreme", 95.0
    
    def _analyze_momentum(self, price_history: List[Dict]) -> Tuple[str, float]:
        """
        Analyze price momentum.
        
        Returns:
            Tuple of (momentum classification, score -1 to 1)
        """
        if len(price_history) < 5:
            return "steady", 0.0
        
        closes = [p.get('close', 0) for p in price_history if p.get('close')]
        if len(closes) < 5:
            return "steady", 0.0
        
        # Calculate rate of change for different periods
        recent_roc = (closes[-1] - closes[-3]) / closes[-3] * 100 if closes[-3] > 0 else 0
        older_roc = (closes[-3] - closes[-5]) / closes[-5] * 100 if closes[-5] > 0 else 0
        
        # Compare momentum
        momentum_diff = recent_roc - older_roc
        
        if momentum_diff > 2:
            return "accelerating", min(1.0, momentum_diff / 5)
        elif momentum_diff > -2:
            if abs(recent_roc) < 1:
                return "steady", 0.0
            elif recent_roc > 0:
                return "steady", 0.3
            else:
                return "steady", -0.3
        elif momentum_diff > -5:
            return "fading", -0.5
        else:
            return "reversing", max(-1.0, momentum_diff / 5)
    
    def _analyze_price_location(
        self, 
        current_price: float,
        price_history: List[Dict]
    ) -> Tuple[str, float, float]:
        """
        Determine price location relative to support/resistance.
        
        Returns:
            Tuple of (location, distance_to_support_pct, distance_to_resistance_pct)
        """
        if not price_history:
            return "mid_range", 0, 0
        
        # Find high and low from history (approximate support/resistance)
        highs = [p.get('high', p.get('close', 0)) for p in price_history]
        lows = [p.get('low', p.get('close', 0)) for p in price_history]
        
        if not highs or not lows:
            return "mid_range", 0, 0
        
        resistance = max(highs)
        support = min(lows)
        
        if resistance == support:
            return "mid_range", 0, 0
        
        # Calculate distances
        range_size = resistance - support
        dist_to_support = (current_price - support) / range_size * 100
        dist_to_resistance = (resistance - current_price) / range_size * 100
        
        # Classify
        if dist_to_support < 20:
            return "near_support", dist_to_support, dist_to_resistance
        elif dist_to_resistance < 20:
            return "near_resistance", dist_to_support, dist_to_resistance
        else:
            return "mid_range", dist_to_support, dist_to_resistance
    
    def _calculate_confidence(self, price_history: Optional[List[Dict]]) -> float:
        """Calculate confidence in regime detection"""
        if not price_history:
            return 0.3
        
        # More data = higher confidence
        data_points = len(price_history)
        if data_points >= 100:
            return 0.9
        elif data_points >= 50:
            return 0.7
        elif data_points >= 20:
            return 0.5
        else:
            return 0.3
    
    def _save_regime(self, regime: MarketRegime):
        """Save regime to file"""
        try:
            with open(self.regime_file, 'w') as f:
                json.dump(regime.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error saving regime: {e}")
    
    def get_cached_regime(self, symbol: str = "BTC") -> Optional[MarketRegime]:
        """Get cached regime if still valid"""
        if (self._cached_regime and 
            self._cache_time and 
            datetime.now() - self._cache_time < self._cache_duration and
            self._cached_regime.symbol == symbol):
            return self._cached_regime
        
        # Try loading from file
        if self.regime_file.exists():
            try:
                with open(self.regime_file) as f:
                    data = json.load(f)
                regime = MarketRegime(**data)
                if regime.symbol == symbol:
                    return regime
            except Exception:
                pass
        
        return None
    
    def get_trading_conditions_score(self, style_preference: str = "neutral") -> float:
        """
        Score current conditions for trading (0-1).
        
        Args:
            style_preference: Trader's preferred condition (bullish, bearish, neutral, volatile)
            
        Returns:
            Score indicating how favorable conditions are
        """
        regime = self._cached_regime
        if not regime:
            return 0.5
        
        score = 0.5  # Base score
        
        if style_preference == "bullish":
            if regime.trend in ["strong_up", "moderate_up"]:
                score += 0.3
            if regime.momentum == "accelerating":
                score += 0.1
            if regime.price_location == "near_support":
                score += 0.1
        
        elif style_preference == "bearish":
            if regime.trend in ["strong_down", "moderate_down"]:
                score += 0.3
            if regime.momentum == "fading":
                score += 0.1
            if regime.price_location == "near_resistance":
                score += 0.1
        
        elif style_preference == "volatile":
            if regime.volatility in ["elevated", "extreme"]:
                score += 0.3
            if regime.momentum == "reversing":
                score += 0.1
        
        else:  # neutral - prefer stable conditions
            if regime.volatility == "normal":
                score += 0.2
            if regime.momentum == "steady":
                score += 0.1
            if regime.trend == "neutral":
                score += 0.1
        
        return min(1.0, score)
    
    def should_trade_now(self, style_preference: str = "neutral") -> Tuple[bool, str]:
        """
        Determine if conditions are favorable for trading.
        
        Returns:
            Tuple of (should_trade, reason)
        """
        regime = self._cached_regime
        if not regime:
            return True, "No regime data - proceed with caution"
        
        # Check for extreme conditions
        if regime.volatility == "extreme":
            return False, f"Extreme volatility ({regime.current_iv:.0f}% IV) - wait for calmer markets"
        
        if regime.momentum == "reversing":
            return False, "Market momentum reversing - wait for direction clarity"
        
        score = self.get_trading_conditions_score(style_preference)
        
        if score >= 0.6:
            return True, f"Favorable conditions for {style_preference} trading (score: {score:.2f})"
        elif score >= 0.4:
            return True, f"Neutral conditions - proceed with smaller size (score: {score:.2f})"
        else:
            return False, f"Unfavorable conditions for {style_preference} style (score: {score:.2f})"


# Singleton instance
regime_detector = MarketRegimeDetector()
