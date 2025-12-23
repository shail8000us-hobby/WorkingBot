"""
Machine Learning Prediction Module
Uses ML models for price prediction and pattern recognition
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


class MLPredictor:
    """
    Machine Learning predictor for trading signals
    
    Features:
    - Price movement prediction
    - Win probability estimation
    - Pattern recognition
    - Optimal entry/exit timing
    """
    
    def __init__(self, lookback_period: int = 50):
        """
        Initialize ML predictor
        
        Args:
            lookback_period: Number of historical data points to consider
        """
        self.lookback_period = lookback_period
        self.price_history = deque(maxlen=lookback_period)
        self.volume_history = deque(maxlen=lookback_period)
        self.trade_history = []
        
        logger.info(f"MLPredictor initialized with lookback={lookback_period}")
    
    def update_market_data(self, price: float, volume: float = 0):
        """
        Update market data for predictions
        
        Args:
            price: Current market price
            volume: Trading volume (optional)
        """
        self.price_history.append(price)
        self.volume_history.append(volume)
    
    def predict_price_movement(self, horizon: int = 5) -> Dict[str, any]:
        """
        Predict future price movement using trend analysis
        
        Args:
            horizon: Number of periods to predict ahead
            
        Returns:
            Dictionary with prediction results
        """
        if len(self.price_history) < 10:
            return {
                "direction": "UNKNOWN",
                "confidence": 0.0,
                "predicted_prices": [],
                "error": "Insufficient data"
            }
        
        prices = np.array(list(self.price_history))
        
        # Calculate features
        returns = np.diff(prices) / prices[:-1]
        momentum = self._calculate_momentum(prices)
        volatility = np.std(returns) if len(returns) > 0 else 0
        trend_strength = self._calculate_trend_strength(prices)
        
        # Simple linear regression for prediction
        x = np.arange(len(prices))
        coeffs = np.polyfit(x, prices, 1)
        slope = coeffs[0]
        
        # Predict future prices
        future_x = np.arange(len(prices), len(prices) + horizon)
        predicted_prices = np.polyval(coeffs, future_x)
        
        # Determine direction and confidence
        if slope > 0:
            direction = "UP"
            confidence = min(0.95, abs(trend_strength) * 0.8)
        elif slope < 0:
            direction = "DOWN"
            confidence = min(0.95, abs(trend_strength) * 0.8)
        else:
            direction = "SIDEWAYS"
            confidence = 0.5
        
        # Adjust confidence based on volatility
        if volatility > 0.02:  # High volatility
            confidence *= 0.7
        
        return {
            "direction": direction,
            "confidence": float(confidence),
            "predicted_prices": [float(p) for p in predicted_prices],
            "current_price": float(prices[-1]),
            "slope": float(slope),
            "momentum": float(momentum),
            "volatility": float(volatility),
            "trend_strength": float(trend_strength)
        }
    
    def estimate_win_probability(
        self,
        entry_price: float,
        target_price: float,
        stop_loss: float
    ) -> Dict[str, float]:
        """
        Estimate probability of hitting target before stop loss
        
        Args:
            entry_price: Entry price
            target_price: Target price
            stop_loss: Stop loss price
            
        Returns:
            Dictionary with win probability and metrics
        """
        if len(self.price_history) < 20:
            return {
                "win_probability": 0.5,
                "risk_reward_ratio": 0.0,
                "expected_value": 0.0,
                "confidence": 0.0
            }
        
        prices = np.array(list(self.price_history))
        
        # Calculate historical metrics
        returns = np.diff(prices) / prices[:-1]
        avg_return = np.mean(returns)
        volatility = np.std(returns)
        
        # Calculate risk/reward
        target_distance = abs(target_price - entry_price)
        stop_distance = abs(entry_price - stop_loss)
        risk_reward = target_distance / stop_distance if stop_distance > 0 else 0
        
        # Estimate win probability using historical data
        # This is a simplified model - in production, use more sophisticated ML
        if entry_price < target_price:  # Long position
            favorable_moves = np.sum(returns > 0)
        else:  # Short position
            favorable_moves = np.sum(returns < 0)
        
        base_win_prob = favorable_moves / len(returns) if len(returns) > 0 else 0.5
        
        # Adjust based on trend
        trend = self._calculate_trend_strength(prices)
        if (entry_price < target_price and trend > 0) or (entry_price > target_price and trend < 0):
            win_prob = min(0.95, base_win_prob * 1.2)
        else:
            win_prob = max(0.05, base_win_prob * 0.8)
        
        # Calculate expected value
        expected_value = (win_prob * target_distance) - ((1 - win_prob) * stop_distance)
        
        return {
            "win_probability": float(win_prob),
            "risk_reward_ratio": float(risk_reward),
            "expected_value": float(expected_value),
            "confidence": float(min(0.9, len(self.price_history) / self.lookback_period))
        }
    
    def detect_patterns(self) -> List[Dict[str, any]]:
        """
        Detect trading patterns in price history
        
        Returns:
            List of detected patterns
        """
        if len(self.price_history) < 20:
            return []
        
        prices = np.array(list(self.price_history))
        patterns = []
        
        # Detect support/resistance levels
        support_resistance = self._detect_support_resistance(prices)
        if support_resistance:
            patterns.append(support_resistance)
        
        # Detect trend
        trend = self._detect_trend(prices)
        if trend:
            patterns.append(trend)
        
        # Detect volatility regime
        volatility_regime = self._detect_volatility_regime(prices)
        if volatility_regime:
            patterns.append(volatility_regime)
        
        # Detect reversal signals
        reversal = self._detect_reversal(prices)
        if reversal:
            patterns.append(reversal)
        
        return patterns
    
    def suggest_entry_exit(self, current_price: float) -> Dict[str, any]:
        """
        Suggest optimal entry/exit points
        
        Args:
            current_price: Current market price
            
        Returns:
            Dictionary with entry/exit suggestions
        """
        if len(self.price_history) < 20:
            return {
                "action": "WAIT",
                "reason": "Insufficient data",
                "confidence": 0.0
            }
        
        prices = np.array(list(self.price_history))
        
        # Calculate indicators
        momentum = self._calculate_momentum(prices)
        trend = self._calculate_trend_strength(prices)
        volatility = np.std(np.diff(prices) / prices[:-1])
        
        # Detect patterns
        patterns = self.detect_patterns()
        
        # Decision logic
        if momentum > 0.02 and trend > 0.5:
            action = "BUY"
            reason = "Strong upward momentum and trend"
            confidence = 0.75
        elif momentum < -0.02 and trend < -0.5:
            action = "SELL"
            reason = "Strong downward momentum and trend"
            confidence = 0.75
        elif volatility > 0.03:
            action = "WAIT"
            reason = "High volatility - wait for stability"
            confidence = 0.8
        else:
            action = "HOLD"
            reason = "No clear signal"
            confidence = 0.5
        
        # Adjust based on patterns
        for pattern in patterns:
            if pattern.get("type") == "reversal":
                if action == "BUY":
                    action = "WAIT"
                    reason = "Potential reversal detected"
                    confidence = 0.6
        
        return {
            "action": action,
            "reason": reason,
            "confidence": float(confidence),
            "current_price": float(current_price),
            "momentum": float(momentum),
            "trend": float(trend),
            "volatility": float(volatility),
            "patterns_detected": len(patterns)
        }
    
    def _calculate_momentum(self, prices: np.ndarray, period: int = 10) -> float:
        """Calculate price momentum"""
        if len(prices) < period:
            return 0.0
        return (prices[-1] - prices[-period]) / prices[-period]
    
    def _calculate_trend_strength(self, prices: np.ndarray) -> float:
        """Calculate trend strength (-1 to 1)"""
        if len(prices) < 10:
            return 0.0
        
        x = np.arange(len(prices))
        coeffs = np.polyfit(x, prices, 1)
        slope = coeffs[0]
        
        # Normalize slope
        avg_price = np.mean(prices)
        normalized_slope = slope / avg_price if avg_price > 0 else 0
        
        # Calculate R-squared for trend strength
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((prices - y_pred) ** 2)
        ss_tot = np.sum((prices - np.mean(prices)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Combine slope direction with R-squared
        return np.sign(normalized_slope) * r_squared
    
    def _detect_support_resistance(self, prices: np.ndarray) -> Optional[Dict]:
        """Detect support and resistance levels"""
        if len(prices) < 20:
            return None
        
        # Find local maxima and minima
        window = 5
        resistance_levels = []
        support_levels = []
        
        for i in range(window, len(prices) - window):
            if prices[i] == np.max(prices[i-window:i+window+1]):
                resistance_levels.append(prices[i])
            elif prices[i] == np.min(prices[i-window:i+window+1]):
                support_levels.append(prices[i])
        
        if not resistance_levels and not support_levels:
            return None
        
        return {
            "type": "support_resistance",
            "resistance": float(np.mean(resistance_levels)) if resistance_levels else None,
            "support": float(np.mean(support_levels)) if support_levels else None,
            "confidence": 0.7
        }
    
    def _detect_trend(self, prices: np.ndarray) -> Optional[Dict]:
        """Detect trend pattern"""
        trend_strength = self._calculate_trend_strength(prices)
        
        if abs(trend_strength) < 0.3:
            return None
        
        return {
            "type": "trend",
            "direction": "UP" if trend_strength > 0 else "DOWN",
            "strength": float(abs(trend_strength)),
            "confidence": float(abs(trend_strength))
        }
    
    def _detect_volatility_regime(self, prices: np.ndarray) -> Optional[Dict]:
        """Detect volatility regime"""
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns)
        
        if volatility > 0.03:
            regime = "HIGH"
        elif volatility < 0.01:
            regime = "LOW"
        else:
            regime = "NORMAL"
        
        return {
            "type": "volatility_regime",
            "regime": regime,
            "volatility": float(volatility),
            "confidence": 0.8
        }
    
    def _detect_reversal(self, prices: np.ndarray) -> Optional[Dict]:
        """Detect potential reversal patterns"""
        if len(prices) < 10:
            return None
        
        # Simple reversal detection: check if recent trend opposes longer trend
        short_trend = self._calculate_trend_strength(prices[-5:])
        long_trend = self._calculate_trend_strength(prices)
        
        if abs(short_trend) > 0.5 and np.sign(short_trend) != np.sign(long_trend):
            return {
                "type": "reversal",
                "direction": "UP" if short_trend > 0 else "DOWN",
                "confidence": 0.6
            }
        
        return None


# Singleton instance
_ml_predictor = None


def get_ml_predictor(lookback_period: int = 50) -> MLPredictor:
    """Get singleton ML predictor instance"""
    global _ml_predictor
    if _ml_predictor is None:
        _ml_predictor = MLPredictor(lookback_period)
    return _ml_predictor

