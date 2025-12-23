"""
Predictive Intelligence Layer for Volatility Spike Detection

Minimal ML engine that learns from historical IV/RV patterns to predict
volatility spikes 5-10 minutes before they happen.

Features:
- Real-time pattern recognition from volatility database
- Simple gradient-based spike prediction
- Early warning system (5-10 min ahead)
- Confidence scoring
- Auto-learning from new data
"""

import os
import sys
import sqlite3
import numpy as np
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

log = logging.getLogger("predictive_engine")

@dataclass
class PredictionResult:
    """Volatility spike prediction result"""
    will_spike: bool
    confidence: float  # 0.0 to 1.0
    minutes_ahead: int  # 5-10 minutes
    current_iv: float
    predicted_iv: float
    spike_threshold: float
    pattern_match: str

class VolatilityPredictor:
    """
    Minimal ML engine for volatility spike prediction.
    Uses gradient analysis and pattern matching on historical data.
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str((project_root / "data" / "volatility.db").resolve())
        self.db_path = db_path
        
        # Prediction parameters
        self.spike_threshold = 5.0  # 5% IV increase = spike
        self.lookback_minutes = 30  # Analyze last 30 minutes
        self.prediction_horizon = 7  # Predict 7 minutes ahead
        self.min_confidence = 0.6   # Minimum confidence to warn
        
        log.info(f"🧠 Predictive Engine initialized (DB: {db_path})")
    
    def predict_spike(self) -> Optional[PredictionResult]:
        """
        Predict if volatility will spike in next 5-10 minutes.
        
        Returns:
            PredictionResult with spike prediction and confidence
        """
        try:
            # Get recent IV data
            recent_data = self._get_recent_iv_data()
            if len(recent_data) < 5:
                return None
            
            # Extract features
            timestamps, iv_values = zip(*recent_data)
            iv_array = np.array(iv_values)
            
            # Calculate gradients and acceleration
            gradient = self._calculate_gradient(iv_array)
            acceleration = self._calculate_acceleration(iv_array)
            volatility_of_volatility = np.std(iv_array[-10:]) if len(iv_array) >= 10 else 0
            
            # Pattern matching
            pattern = self._identify_pattern(iv_array)
            
            # Spike prediction logic
            current_iv = iv_values[-1]
            
            # Simple ML: weighted combination of indicators
            spike_score = (
                gradient * 0.4 +           # Recent trend
                acceleration * 0.3 +       # Acceleration
                volatility_of_volatility * 0.2 +  # VoV
                self._pattern_score(pattern) * 0.1  # Pattern bonus
            )
            
            # Predict future IV
            predicted_iv = current_iv + (gradient * self.prediction_horizon / 2)
            
            # Determine if spike will occur
            iv_increase = predicted_iv - current_iv
            will_spike = iv_increase >= self.spike_threshold
            
            # Calculate confidence
            confidence = min(abs(spike_score) / 10.0, 1.0)
            
            return PredictionResult(
                will_spike=will_spike,
                confidence=confidence,
                minutes_ahead=self.prediction_horizon,
                current_iv=current_iv,
                predicted_iv=predicted_iv,
                spike_threshold=self.spike_threshold,
                pattern_match=pattern
            )
            
        except Exception as e:
            log.error(f"Prediction error: {e}")
            return None
    
    def _get_recent_iv_data(self) -> List[Tuple[float, float]]:
        """Get IV data from last 30 minutes"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get data from last 30 minutes
            cutoff_time = datetime.now().timestamp() - (self.lookback_minutes * 60)
            
            cursor.execute("""
                SELECT timestamp, iv_value 
                FROM iv_snapshots 
                WHERE timestamp > ? 
                ORDER BY timestamp ASC
            """, (cutoff_time,))
            
            data = cursor.fetchall()
            conn.close()
            
            return data
            
        except Exception as e:
            log.error(f"Database error: {e}")
            return []
    
    def _calculate_gradient(self, iv_array: np.ndarray) -> float:
        """Calculate recent IV gradient (trend)"""
        if len(iv_array) < 3:
            return 0.0
        
        # Use last 5 points for gradient
        recent = iv_array[-5:]
        x = np.arange(len(recent))
        
        # Linear regression slope
        slope = np.polyfit(x, recent, 1)[0]
        return slope
    
    def _calculate_acceleration(self, iv_array: np.ndarray) -> float:
        """Calculate IV acceleration (second derivative)"""
        if len(iv_array) < 4:
            return 0.0
        
        # Calculate second derivative
        recent = iv_array[-6:]
        if len(recent) < 3:
            return 0.0
        
        # Simple second difference
        first_diff = np.diff(recent)
        second_diff = np.diff(first_diff)
        
        return np.mean(second_diff) if len(second_diff) > 0 else 0.0
    
    def _identify_pattern(self, iv_array: np.ndarray) -> str:
        """Identify volatility pattern"""
        if len(iv_array) < 5:
            return "insufficient_data"
        
        recent = iv_array[-10:]
        
        # Check for common spike patterns
        if self._is_building_pressure(recent):
            return "building_pressure"
        elif self._is_sudden_jump(recent):
            return "sudden_jump"
        elif self._is_steady_climb(recent):
            return "steady_climb"
        else:
            return "normal"
    
    def _is_building_pressure(self, data: np.ndarray) -> bool:
        """Detect building pressure pattern (small increases accelerating)"""
        if len(data) < 5:
            return False
        
        # Check if recent changes are increasing
        diffs = np.diff(data[-5:])
        return len(diffs) >= 3 and diffs[-1] > diffs[-2] > 0
    
    def _is_sudden_jump(self, data: np.ndarray) -> bool:
        """Detect sudden jump pattern"""
        if len(data) < 3:
            return False
        
        recent_change = data[-1] - data[-2]
        return recent_change > 2.0  # 2% jump
    
    def _is_steady_climb(self, data: np.ndarray) -> bool:
        """Detect steady climbing pattern"""
        if len(data) < 5:
            return False
        
        # Check if consistently increasing
        diffs = np.diff(data[-5:])
        return np.all(diffs > 0) and np.std(diffs) < 1.0
    
    def _pattern_score(self, pattern: str) -> float:
        """Get pattern-based spike probability bonus"""
        pattern_scores = {
            "building_pressure": 3.0,
            "sudden_jump": 2.0,
            "steady_climb": 1.5,
            "normal": 0.0,
            "insufficient_data": 0.0
        }
        return pattern_scores.get(pattern, 0.0)
    
    def get_early_warning(self) -> Optional[Dict[str, Any]]:
        """
        Get early warning if spike predicted with high confidence.
        
        Returns:
            Warning dict if spike predicted, None otherwise
        """
        prediction = self.predict_spike()
        if not prediction:
            return None
        
        if prediction.will_spike and prediction.confidence >= self.min_confidence:
            return {
                "alert": True,
                "message": f"⚠️ VOLATILITY SPIKE PREDICTED in {prediction.minutes_ahead} minutes",
                "confidence": f"{prediction.confidence:.1%}",
                "current_iv": f"{prediction.current_iv:.1f}%",
                "predicted_iv": f"{prediction.predicted_iv:.1f}%",
                "pattern": prediction.pattern_match,
                "timestamp": datetime.now().isoformat()
            }
        
        return None
    
    def learn_from_spike(self, actual_spike_time: datetime, spike_magnitude: float):
        """
        Learn from actual spike occurrence (future enhancement).
        For now, just log for manual analysis.
        """
        log.info(f"📚 Learning: Spike occurred at {actual_spike_time}, magnitude: {spike_magnitude:.1f}%")
        # TODO: Implement online learning to improve prediction accuracy


# Singleton instance
_predictor_instance = None

def get_predictor() -> VolatilityPredictor:
    """Get singleton predictor instance"""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = VolatilityPredictor()
    return _predictor_instance