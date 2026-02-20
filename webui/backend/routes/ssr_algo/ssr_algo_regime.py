"""
SSR ALGO Regime Adapter - Market Regime Detection Integration

Adjusts butterfly structure based on whether market is trending or range-bound.
Butterflies profit in ranges and lose in trends.

Uses existing MarketRegimeDetector from options_strategy module.

Created: February 20, 2026
Phase 7 of SSR Algo Development Plan
"""

import logging
import sys
import os
from typing import Dict, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

log = logging.getLogger('ssr_algo_regime')


class SSRRegimeAdapter:
    """
    Adapts SSR Algo behavior based on detected market regime.

    Maps regime detector output to position sizing, wing width,
    and delta threshold adjustments.
    """

    def __init__(self):
        self._regime_detector = None
        self._chain_service = None

    @property
    def regime_detector(self):
        if self._regime_detector is None:
            try:
                from webui.backend.options_strategy.regime_detector import MarketRegimeDetector
                self._regime_detector = MarketRegimeDetector()
            except ImportError:
                log.warning("MarketRegimeDetector not available")
                self._regime_detector = None
        return self._regime_detector

    @property
    def chain_service(self):
        if self._chain_service is None:
            from webui.backend.options_chain.chain_service import OptionsChainService
            self._chain_service = OptionsChainService()
        return self._chain_service

    def get_regime_adjustments(self, underlying: str, current_price: float) -> Dict:
        """
        Get position adjustments based on current market regime.

        Args:
            underlying: BTC or ETH
            current_price: Current spot price

        Returns:
            {
                'regime': str,
                'position_size_multiplier': float,
                'wing_width_multiplier': float,
                'delta_threshold_multiplier': float,
                'description': str,
                'confidence': float,
                'details': dict
            }
        """
        if not self.regime_detector:
            return self._default_adjustments()

        try:
            # Get ATM IV for regime detection
            iv = 0.60  # Default
            try:
                from .ssr_algo_engine import normalize_expiry_format
                chain_data = self.chain_service.get_chain_data(underlying, None)
                if chain_data:
                    atm_strike = chain_data.get('atm_strike', 0)
                    for s in chain_data.get('chain', []):
                        if s.get('strike') == atm_strike:
                            call_iv = s.get('call', {}).get('iv', 0)
                            put_iv = s.get('put', {}).get('iv', 0)
                            iv = (call_iv + put_iv) / 200 if (call_iv and put_iv) else 0.60
                            break
            except Exception:
                pass

            symbol = f"{underlying}USD"
            regime = self.regime_detector.detect_regime(symbol, current_price, iv)

            if not regime:
                return self._default_adjustments()

            # Map regime to adjustments
            trend = getattr(regime, 'trend', 'neutral')
            volatility = getattr(regime, 'volatility', 'normal')
            confidence = getattr(regime, 'confidence', 0.5)

            # TRENDING MARKET
            if trend in ('strong_up', 'strong_down'):
                return {
                    'regime': 'trending',
                    'position_size_multiplier': 0.5,
                    'wing_width_multiplier': 0.8,
                    'delta_threshold_multiplier': 0.7,
                    'description': f'Strong {trend.replace("_", " ")} trend — reduce size, widen wings, tighter delta',
                    'confidence': confidence,
                    'details': {
                        'trend': trend,
                        'volatility': volatility,
                        'momentum': getattr(regime, 'momentum', 'unknown')
                    }
                }

            # HIGH VOLATILITY
            if volatility in ('elevated', 'extreme'):
                return {
                    'regime': 'high_vol',
                    'position_size_multiplier': 1.2,
                    'wing_width_multiplier': 0.7,
                    'delta_threshold_multiplier': 1.0,
                    'description': f'{volatility.title()} volatility — premium rich, widen wings',
                    'confidence': confidence,
                    'details': {
                        'trend': trend,
                        'volatility': volatility,
                        'iv_percentile': getattr(regime, 'volatility_percentile', 50)
                    }
                }

            # LOW VOLATILITY
            if volatility == 'low':
                return {
                    'regime': 'low_vol',
                    'position_size_multiplier': 0.5,
                    'wing_width_multiplier': 1.2,
                    'delta_threshold_multiplier': 1.0,
                    'description': 'Low volatility — thin premium, reduce size',
                    'confidence': confidence,
                    'details': {
                        'trend': trend,
                        'volatility': volatility
                    }
                }

            # RANGING (default — normal conditions)
            return {
                'regime': 'ranging',
                'position_size_multiplier': 1.0,
                'wing_width_multiplier': 1.0,
                'delta_threshold_multiplier': 1.0,
                'description': 'Range-bound market — standard butterfly',
                'confidence': confidence,
                'details': {
                    'trend': trend,
                    'volatility': volatility
                }
            }

        except Exception as e:
            log.warning(f"Regime detection failed: {e}")
            return self._default_adjustments()

    def adjust_strike_config(self, base_config: Dict, adjustments: Dict) -> Dict:
        """
        Apply regime adjustments to strike selection config.

        Args:
            base_config: Original strike_config
            adjustments: From get_regime_adjustments()

        Returns:
            Modified strike config
        """
        wing_mult = adjustments.get('wing_width_multiplier', 1.0)

        adjusted = dict(base_config)
        adjusted['otm_buy_percent_min'] = max(20, min(60, base_config.get('otm_buy_percent_min', 45) * wing_mult))
        adjusted['otm_buy_percent_max'] = max(25, min(65, base_config.get('otm_buy_percent_max', 49) * wing_mult))
        adjusted['far_otm_percent_min'] = max(10, min(40, base_config.get('far_otm_percent_min', 20) * wing_mult))
        adjusted['far_otm_percent_max'] = max(15, min(50, base_config.get('far_otm_percent_max', 30) * wing_mult))

        return adjusted

    def _default_adjustments(self) -> Dict:
        return {
            'regime': 'ranging',
            'position_size_multiplier': 1.0,
            'wing_width_multiplier': 1.0,
            'delta_threshold_multiplier': 1.0,
            'description': 'Default — standard butterfly (regime detector unavailable)',
            'confidence': 0.0,
            'details': {}
        }


# Singleton
_regime_adapter = None

def get_regime_adapter() -> SSRRegimeAdapter:
    """Get singleton SSRRegimeAdapter instance."""
    global _regime_adapter
    if _regime_adapter is None:
        _regime_adapter = SSRRegimeAdapter()
    return _regime_adapter
