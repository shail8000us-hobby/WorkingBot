"""
Volatility Analyzer for MV Straddle
Analyzes current IV vs historical volatility and provides recommendations
"""
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VolatilityAnalyzer:
    """Analyze volatility for straddle strategies"""
    
    def __init__(self, api_client):
        self.api_client = api_client
    
    def analyze(
        self,
        underlying: str,
        current_iv: float,
        expiry: str
    ) -> Dict:
        """
        Analyze volatility conditions
        
        Args:
            underlying: BTC or ETH
            current_iv: Current implied volatility (%)
            expiry: Expiry date (DDMMYYYY or DDMMYY)
        
        Returns:
            {
                "current_iv": 65.5,
                "iv_percentile": 75,  # Current IV vs 30-day range
                "iv_rank": "High",
                "recommendation": "Consider short straddle",
                "historical_vol_30d": 58.2,
                "iv_premium": 7.3,  # IV - HV
                "days_to_expiry": 7,
                "volatility_regime": "High Volatility"
            }
        """
        try:
            # Calculate days to expiry
            dte = self._calculate_dte(expiry)
            
            # Get historical volatility (simplified - can be enhanced with real data)
            historical_vol = self._get_historical_volatility(underlying, days=30)
            
            # Calculate IV premium
            iv_premium = current_iv - historical_vol
            
            # Calculate IV percentile (simplified)
            iv_percentile = self._calculate_iv_percentile(current_iv, historical_vol)
            
            # Determine IV rank and recommendation
            if iv_percentile >= 75:
                iv_rank = "Very High"
                recommendation = "Consider SHORT straddle (sell volatility)"
            elif iv_percentile >= 50:
                iv_rank = "High"
                recommendation = "Neutral - monitor for entry"
            elif iv_percentile >= 25:
                iv_rank = "Low"
                recommendation = "Consider LONG straddle (buy volatility)"
            else:
                iv_rank = "Very Low"
                recommendation = "Strong LONG straddle opportunity"
            
            # Determine volatility regime
            volatility_regime = self._determine_regime(iv_percentile)
            
            return {
                "current_iv": round(current_iv, 2),
                "iv_percentile": round(iv_percentile, 2),
                "iv_rank": iv_rank,
                "recommendation": recommendation,
                "historical_vol_30d": round(historical_vol, 2),
                "iv_premium": round(iv_premium, 2),
                "days_to_expiry": dte,
                "volatility_regime": volatility_regime
            }
            
        except Exception as e:
            logger.error(f"Error analyzing volatility: {e}")
            return {
                "error": str(e),
                "current_iv": current_iv,
                "recommendation": "Unable to analyze - proceed with caution"
            }
    
    def _calculate_dte(self, expiry: str) -> int:
        """Calculate days to expiry"""
        try:
            if len(expiry) == 8:
                # DDMMYYYY
                expiry_date = datetime.strptime(expiry, '%d%m%Y')
            elif len(expiry) == 6:
                # DDMMYY
                expiry_date = datetime.strptime(expiry, '%d%m%y')
            else:
                return 0
            
            now = datetime.now()
            delta = expiry_date - now
            return max(0, delta.days)
        except Exception as e:
            logger.error(f"Error calculating DTE: {e}")
            return 0
    
    def _get_historical_volatility(self, underlying: str, days: int = 30) -> float:
        """
        Get historical volatility (simplified implementation)
        
        In production, this should fetch real historical price data and calculate
        realized volatility. For now, we use a simplified model.
        
        Args:
            underlying: BTC or ETH
            days: Lookback period
            
        Returns:
            Historical volatility as percentage
        """
        # Simplified: Use typical historical volatility ranges
        # BTC typically ranges 40-80%, ETH 50-100%
        # This should be replaced with real calculation from price history
        
        typical_hv = {
            'BTC': 55.0,  # Typical BTC HV
            'ETH': 65.0   # Typical ETH HV
        }
        
        base_hv = typical_hv.get(underlying.upper(), 55.0)
        
        # Add some variation (±10%)
        # In production, calculate from actual price data
        logger.info(f"Using estimated HV for {underlying}: {base_hv}%")
        
        return base_hv
    
    def _calculate_iv_percentile(self, current_iv: float, historical_vol: float) -> float:
        """
        Calculate IV percentile (simplified)
        
        In production, this should compare current IV against IV range over past 30-90 days.
        For now, we use a simplified model based on IV vs HV.
        
        Args:
            current_iv: Current implied volatility
            historical_vol: Historical volatility
            
        Returns:
            Percentile (0-100)
        """
        # Simplified model: IV premium relative to typical range
        iv_premium = current_iv - historical_vol
        
        # Typical IV premium ranges from -20% to +30%
        # Map this to 0-100 percentile
        if iv_premium <= -20:
            percentile = 0
        elif iv_premium >= 30:
            percentile = 100
        else:
            # Linear interpolation between -20 and +30
            percentile = ((iv_premium + 20) / 50) * 100
        
        return max(0, min(100, percentile))
    
    def _determine_regime(self, iv_percentile: float) -> str:
        """Determine volatility regime based on IV percentile"""
        if iv_percentile >= 75:
            return "Very High Volatility"
        elif iv_percentile >= 50:
            return "High Volatility"
        elif iv_percentile >= 25:
            return "Normal Volatility"
        else:
            return "Low Volatility"
