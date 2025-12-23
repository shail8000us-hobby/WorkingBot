"""
Institutional-Grade Market Regime Detection Module

This module detects the current market regime to adapt trading strategy:
- TRENDING: High momentum, directional movement
- MEAN_REVERTING: Price oscillates around mean
- HIGH_VOLATILITY: Rapid, unpredictable price changes
- LOW_LIQUIDITY: Wide spreads, low volume

Author: GridBot Pro - Institutional AI
Version: 1.0.0
"""

import sys
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config


class MarketRegimeDetector:
    """
    Professional-grade market regime detection engine
    """
    
    def __init__(self, base_dir: str = None):
        """Initialize the market regime detector"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent.parent.parent
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_cache_time = None
    
    # =========================================================================
    # REGIME DETECTION
    # =========================================================================
    
    def detect_regime(
        self,
        price_data: np.ndarray,
        volume_data: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Detect current market regime
        
        Args:
            price_data: Array of recent prices
            volume_data: Array of recent volumes (optional)
        
        Returns:
            Dictionary with regime classification and metrics
        """
        if len(price_data) < 20:
            return {
                'regime': 'INSUFFICIENT_DATA',
                'confidence': 0.0,
                'description': 'Not enough data for regime detection',
                'metrics': {}
            }
        
        # Calculate key metrics
        momentum = self._calculate_momentum(price_data)
        volatility = self._calculate_volatility(price_data)
        mean_reversion = self._calculate_mean_reversion(price_data)
        trend_strength = self._calculate_trend_strength(price_data)
        
        # Classify regime
        regime_scores = {
            'TRENDING': 0.0,
            'MEAN_REVERTING': 0.0,
            'HIGH_VOLATILITY': 0.0,
            'LOW_LIQUIDITY': 0.0
        }
        
        # Trending regime indicators
        if abs(momentum) > 0.6 and volatility < 0.4 and trend_strength > 0.7:
            regime_scores['TRENDING'] += 0.8
        
        # Mean-reverting regime indicators
        if abs(momentum) < 0.3 and mean_reversion > 0.6 and volatility < 0.5:
            regime_scores['MEAN_REVERTING'] += 0.8
        
        # High volatility regime indicators
        if volatility > 0.6:
            regime_scores['HIGH_VOLATILITY'] += 0.9
        
        # Low liquidity indicators (if volume data available)
        if volume_data is not None and len(volume_data) > 0:
            volume_volatility = np.std(volume_data) / np.mean(volume_data) if np.mean(volume_data) > 0 else 0
            if volume_volatility > 0.5:
                regime_scores['LOW_LIQUIDITY'] += 0.7
        
        # Determine primary regime
        primary_regime = max(regime_scores, key=regime_scores.get)
        confidence = regime_scores[primary_regime]
        
        # If no clear regime, default to MIXED
        if confidence < 0.5:
            primary_regime = 'MIXED'
            confidence = 0.5
        
        return {
            'regime': primary_regime,
            'confidence': round(confidence, 2),
            'description': self._get_regime_description(primary_regime),
            'metrics': {
                'momentum': round(momentum, 2),
                'volatility': round(volatility, 2),
                'mean_reversion': round(mean_reversion, 2),
                'trend_strength': round(trend_strength, 2)
            },
            'regime_scores': {k: round(v, 2) for k, v in regime_scores.items()},
            'recommendations': self._get_regime_recommendations(primary_regime)
        }
    
    def _calculate_momentum(self, price_data: np.ndarray) -> float:
        """
        Calculate momentum indicator
        
        Returns:
            Momentum score (-1 to +1, where +1 is strong uptrend)
        """
        if len(price_data) < 2:
            return 0.0
        
        # Calculate returns
        returns = np.diff(price_data) / price_data[:-1]
        
        # Calculate momentum as mean return normalized by volatility
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        momentum = mean_return / std_return
        
        # Normalize to -1 to +1 range
        momentum = np.tanh(momentum)
        
        return momentum
    
    def _calculate_volatility(self, price_data: np.ndarray) -> float:
        """
        Calculate volatility indicator
        
        Returns:
            Volatility score (0 to 1, where 1 is very high volatility)
        """
        if len(price_data) < 2:
            return 0.0
        
        # Calculate returns
        returns = np.diff(price_data) / price_data[:-1]
        
        # Calculate volatility as standard deviation
        volatility = np.std(returns)
        
        # Normalize to 0-1 range (assuming max volatility of 0.05 = 5%)
        normalized_vol = min(volatility / 0.05, 1.0)
        
        return normalized_vol
    
    def _calculate_mean_reversion(self, price_data: np.ndarray) -> float:
        """
        Calculate mean reversion tendency
        
        Returns:
            Mean reversion score (0 to 1, where 1 is strong mean reversion)
        """
        if len(price_data) < 10:
            return 0.0
        
        # Calculate deviations from moving average
        ma = np.mean(price_data)
        deviations = price_data - ma
        
        # Count how many times price crosses the mean
        crosses = 0
        for i in range(1, len(deviations)):
            if (deviations[i-1] > 0 and deviations[i] < 0) or (deviations[i-1] < 0 and deviations[i] > 0):
                crosses += 1
        
        # Normalize by number of possible crosses
        mean_reversion_score = crosses / (len(price_data) - 1)
        
        return mean_reversion_score
    
    def _calculate_trend_strength(self, price_data: np.ndarray) -> float:
        """
        Calculate trend strength using linear regression
        
        Returns:
            Trend strength score (0 to 1, where 1 is very strong trend)
        """
        if len(price_data) < 10:
            return 0.0
        
        # Fit linear regression
        x = np.arange(len(price_data))
        
        # Calculate correlation coefficient (R-squared)
        correlation = np.corrcoef(x, price_data)[0, 1]
        r_squared = correlation ** 2
        
        return r_squared
    
    def _get_regime_description(self, regime: str) -> str:
        """Get human-readable description of regime"""
        descriptions = {
            'TRENDING': 'Market is trending with strong directional movement',
            'MEAN_REVERTING': 'Market is range-bound with mean-reverting behavior',
            'HIGH_VOLATILITY': 'Market is experiencing high volatility and rapid price changes',
            'LOW_LIQUIDITY': 'Market has low liquidity with wide spreads',
            'MIXED': 'Market regime is unclear or transitioning',
            'INSUFFICIENT_DATA': 'Not enough data to determine market regime'
        }
        
        return descriptions.get(regime, 'Unknown market regime')
    
    def _get_regime_recommendations(self, regime: str) -> Dict[str, Any]:
        """
        Get trading recommendations based on regime
        
        Args:
            regime: Current market regime
        
        Returns:
            Dictionary with recommendations
        """
        recommendations = {
            'TRENDING': {
                'strategy': 'Trend Following',
                'grid_adjustment': 'Widen grid step by 20-30%',
                'position_sizing': 'Reduce size to avoid whipsaws',
                'stop_loss': 'Use wider stops',
                'take_profit': 'Trail profits with trend',
                'expected_win_rate': '45-55%',
                'expected_profit_factor': '1.5-2.0'
            },
            'MEAN_REVERTING': {
                'strategy': 'Grid Trading (Optimal)',
                'grid_adjustment': 'Tighten grid step by 10-20%',
                'position_sizing': 'Standard size',
                'stop_loss': 'Use tight stops',
                'take_profit': 'Quick exits at grid levels',
                'expected_win_rate': '65-75%',
                'expected_profit_factor': '1.8-2.5'
            },
            'HIGH_VOLATILITY': {
                'strategy': 'Reduced Activity',
                'grid_adjustment': 'Widen grid step significantly (30-50%)',
                'position_sizing': 'Reduce size by 50%',
                'stop_loss': 'Use very wide stops or avoid trading',
                'take_profit': 'Take profits quickly',
                'expected_win_rate': '40-50%',
                'expected_profit_factor': '1.2-1.5'
            },
            'LOW_LIQUIDITY': {
                'strategy': 'Cautious Trading',
                'grid_adjustment': 'Widen grid step',
                'position_sizing': 'Reduce size',
                'stop_loss': 'Account for wider spreads',
                'take_profit': 'Be patient',
                'expected_win_rate': '50-60%',
                'expected_profit_factor': '1.3-1.7'
            },
            'MIXED': {
                'strategy': 'Standard Grid Trading',
                'grid_adjustment': 'Keep current settings',
                'position_sizing': 'Standard size',
                'stop_loss': 'Standard stops',
                'take_profit': 'Standard targets',
                'expected_win_rate': '55-65%',
                'expected_profit_factor': '1.5-2.0'
            }
        }
        
        return recommendations.get(regime, recommendations['MIXED'])
    
    # =========================================================================
    # PRICE FORECASTING
    # =========================================================================
    
    def forecast_price(
        self,
        price_data: np.ndarray,
        horizon: int = 5
    ) -> Dict[str, Any]:
        """
        Forecast future price movement
        
        Args:
            price_data: Array of recent prices
            horizon: Number of periods to forecast
        
        Returns:
            Dictionary with price forecast
        """
        if len(price_data) < 20:
            return {
                'forecast': [],
                'confidence': 0.0,
                'direction': 'UNKNOWN'
            }
        
        # Simple momentum-based forecast
        recent_momentum = self._calculate_momentum(price_data[-20:])
        recent_volatility = self._calculate_volatility(price_data[-20:])
        
        current_price = price_data[-1]
        
        # Generate forecast
        forecast_prices = []
        for i in range(1, horizon + 1):
            # Forecast based on momentum, decaying over time
            decay_factor = 0.9 ** i
            expected_return = recent_momentum * recent_volatility * decay_factor
            forecast_price = current_price * (1 + expected_return)
            forecast_prices.append(round(forecast_price, 2))
        
        # Determine direction
        if forecast_prices[-1] > current_price * 1.01:
            direction = 'UP'
        elif forecast_prices[-1] < current_price * 0.99:
            direction = 'DOWN'
        else:
            direction = 'SIDEWAYS'
        
        # Calculate confidence based on trend strength
        trend_strength = self._calculate_trend_strength(price_data[-20:])
        confidence = trend_strength
        
        return {
            'forecast': forecast_prices,
            'current_price': round(current_price, 2),
            'direction': direction,
            'confidence': round(confidence, 2),
            'horizon': horizon
        }
    
    # =========================================================================
    # DATA LOADING
    # =========================================================================
    
    def _load_recent_price_data(self, lookback_periods: int = 100) -> np.ndarray:
        """
        Load recent price data from Delta Exchange
        
        Args:
            lookback_periods: Number of periods to load
        
        Returns:
            Array of prices
        """
        try:
            # Import here to avoid circular dependency
            import requests
            from datetime import datetime, timedelta
            import time
            
            # Get trading mode and API configuration from YAML
            cfg = get_config()
            trading_mode = cfg.safety.trading_mode
            
            if trading_mode == 'demo':
                base_url = cfg.api.demo.public_url
            else:
                base_url = cfg.api.live.public_url
            
            # Get symbol from config
            symbol = cfg.trading.symbol
            
            # Calculate time range (lookback_periods hours ago to now)
            end_time = int(time.time())
            start_time = end_time - (lookback_periods * 3600)  # 3600 seconds per hour
            
            # Fetch OHLC data (1 hour candles)
            url = f'{base_url}/v2/history/candles'
            params = {
                'symbol': symbol,
                'resolution': '1h',  # 1 hour (not '60')
                'start': start_time,
                'end': end_time
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'result' in data:
                    candles = data['result']
                    # Extract close prices
                    prices = [float(candle['close']) for candle in candles]
                    # Return most recent prices
                    return np.array(prices[-lookback_periods:]) if prices else np.array([])
        
        except Exception as e:
            # Log error but don't crash
            import logging
            logging.getLogger('market_regime').warning(f"Failed to fetch price data: {e}")
        
        # Return empty array if fetch fails
        return np.array([])
    
    # =========================================================================
    # COMPREHENSIVE ANALYSIS
    # =========================================================================
    
    def analyze_market(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Perform comprehensive market analysis
        
        Args:
            force_refresh: Force recalculation (ignore cache)
        
        Returns:
            Dictionary with complete market analysis
        """
        # Check cache
        if not force_refresh and self.last_cache_time:
            if (datetime.now() - self.last_cache_time).total_seconds() < self.cache_ttl:
                return self.cache
        
        # Load price data
        price_data = self._load_recent_price_data()
        
        if len(price_data) == 0:
            return {
                'timestamp': datetime.now().isoformat(),
                'regime': {
                    'regime': 'INSUFFICIENT_DATA',
                    'confidence': 0.0,
                    'description': 'No price data available'
                },
                'forecast': {
                    'forecast': [],
                    'direction': 'UNKNOWN',
                    'confidence': 0.0
                }
            }
        
        # Detect regime
        regime = self.detect_regime(price_data)
        
        # Forecast price
        forecast = self.forecast_price(price_data)
        
        # Compile analysis
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'regime': regime,
            'forecast': forecast,
            'current_price': price_data[-1] if len(price_data) > 0 else 0
        }
        
        # Update cache
        self.cache = analysis
        self.last_cache_time = datetime.now()
        
        return analysis


# Singleton accessor
_market_regime_detector_instance = None

def get_market_regime_detector() -> MarketRegimeDetector:
    """Get singleton instance of MarketRegimeDetector"""
    global _market_regime_detector_instance
    if _market_regime_detector_instance is None:
        _market_regime_detector_instance = MarketRegimeDetector()
    return _market_regime_detector_instance

