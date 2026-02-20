"""
SSR ALGO Volatility Analyzer - IV Rank Entry Filter & Volatility Context

Only deploy butterflies when premium is rich (IV elevated).
Prevents entering when options are cheap and credit doesn't compensate for risk.

Uses exchange chain data for current IV and VolatilityAnalyzer for IV rank.

Created: February 20, 2026
Phase 4 of SSR Algo Development Plan
"""

import logging
import sys
import os
from typing import Dict, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from .ssr_algo_engine import normalize_expiry_format

log = logging.getLogger('ssr_algo_vol_analyzer')

# Default IV filter config
DEFAULT_IV_FILTER_CONFIG = {
    'enabled': False,
    'min_iv_rank': 20,
    'warn_iv_rank': 30,
    'ideal_iv_rank': 50,
}


class SSRVolAnalyzer:
    """
    Analyzes implied volatility context for SSR Algo entry decisions.

    Provides IV rank, skew analysis, and entry recommendations based
    on whether premium selling conditions are favorable.
    """

    def __init__(self):
        self._chain_service = None
        self._vol_analyzer = None

    @property
    def chain_service(self):
        if self._chain_service is None:
            from webui.backend.options_chain.chain_service import OptionsChainService
            self._chain_service = OptionsChainService()
        return self._chain_service

    @property
    def vol_analyzer(self):
        if self._vol_analyzer is None:
            try:
                from webui.backend.options_strategy.mv_straddle.volatility_analyzer import VolatilityAnalyzer
                self._vol_analyzer = VolatilityAnalyzer()
            except ImportError:
                log.warning("VolatilityAnalyzer not available, using fallback")
                self._vol_analyzer = None
        return self._vol_analyzer

    def get_iv_context(self, underlying: str, expiry: str) -> Dict:
        """
        Get full IV context for entry decision-making.

        Args:
            underlying: BTC or ETH
            expiry: Expiry date in DDMMYY or DDMMYYYY format

        Returns:
            {
                'current_atm_iv': float,
                'iv_rank': float (0-100),
                'iv_classification': str,
                'skew': float,
                'recommendation': str,
                'analyzed_at': str
            }
        """
        try:
            normalized_expiry = normalize_expiry_format(expiry)
            chain_data = self.chain_service.get_chain_data(underlying, normalized_expiry)
        except Exception as e:
            log.warning(f"Could not fetch chain for IV context: {e}")
            return self._default_iv_context()

        spot_price = chain_data.get('spot_price', 0)
        atm_strike = chain_data.get('atm_strike', 0)
        chain = chain_data.get('chain', [])

        # Find ATM IV
        atm_ce_iv = 0
        atm_pe_iv = 0
        for s in chain:
            if s.get('strike') == atm_strike:
                call = s.get('call', {})
                put = s.get('put', {})
                atm_ce_iv = call.get('iv', 0) if call else 0
                atm_pe_iv = put.get('iv', 0) if put else 0
                break

        current_atm_iv = (atm_ce_iv + atm_pe_iv) / 2 if (atm_ce_iv and atm_pe_iv) else max(atm_ce_iv, atm_pe_iv)

        # Calculate IV rank using VolatilityAnalyzer if available
        iv_rank = 50.0  # Default neutral
        iv_classification = 'normal'

        if self.vol_analyzer and current_atm_iv > 0:
            try:
                vol_result = self.vol_analyzer.analyze(underlying, current_atm_iv, expiry)
                if vol_result:
                    iv_rank = vol_result.get('iv_percentile', 50)
                    vol_regime = vol_result.get('volatility_regime', 'Normal')
                    if 'High' in vol_regime:
                        iv_classification = 'high'
                    elif 'Low' in vol_regime:
                        iv_classification = 'low'
                    elif 'Very High' in vol_regime or 'Extreme' in vol_regime:
                        iv_classification = 'very_high'
            except Exception as e:
                log.debug(f"VolatilityAnalyzer failed, using manual classification: {e}")

        # Manual IV classification if analyzer didn't set it
        if iv_classification == 'normal' and current_atm_iv > 0:
            if iv_rank < 20:
                iv_classification = 'very_low'
            elif iv_rank < 30:
                iv_classification = 'low'
            elif iv_rank < 50:
                iv_classification = 'normal'
            elif iv_rank < 70:
                iv_classification = 'high'
            else:
                iv_classification = 'very_high'

        # Calculate skew (put IV - call IV at ATM)
        skew = atm_pe_iv - atm_ce_iv

        return {
            'current_atm_iv': round(current_atm_iv, 2),
            'iv_rank': round(iv_rank, 1),
            'iv_classification': iv_classification,
            'skew': round(skew, 2),
            'atm_ce_iv': round(atm_ce_iv, 2),
            'atm_pe_iv': round(atm_pe_iv, 2),
            'atm_strike': atm_strike,
            'spot_price': spot_price,
            'analyzed_at': datetime.utcnow().isoformat()
        }

    def get_entry_recommendation(self, iv_context: Dict) -> Dict:
        """
        Get entry recommendation based on IV context.

        Args:
            iv_context: From get_iv_context()

        Returns:
            {
                'should_enter': bool,
                'confidence': float (0-1),
                'reason': str,
                'recommended_size_multiplier': float
            }
        """
        iv_rank = iv_context.get('iv_rank', 50)

        if iv_rank < 20:
            return {
                'should_enter': False,
                'confidence': 0.2,
                'reason': f'IV Rank {iv_rank}% — too low. Premium not sufficient for risk.',
                'recommended_size_multiplier': 0.0
            }
        elif iv_rank < 30:
            return {
                'should_enter': True,
                'confidence': 0.4,
                'reason': f'IV Rank {iv_rank}% — low. Consider reduced size.',
                'recommended_size_multiplier': 0.5
            }
        elif iv_rank < 50:
            return {
                'should_enter': True,
                'confidence': 0.6,
                'reason': f'IV Rank {iv_rank}% — normal. Standard entry.',
                'recommended_size_multiplier': 1.0
            }
        elif iv_rank < 70:
            return {
                'should_enter': True,
                'confidence': 0.8,
                'reason': f'IV Rank {iv_rank}% — elevated. Good premium environment.',
                'recommended_size_multiplier': 1.0
            }
        else:
            return {
                'should_enter': True,
                'confidence': 0.95,
                'reason': f'IV Rank {iv_rank}% — high. Ideal for premium selling.',
                'recommended_size_multiplier': 1.2
            }

    def _default_iv_context(self) -> Dict:
        return {
            'current_atm_iv': 0,
            'iv_rank': 50,
            'iv_classification': 'unknown',
            'skew': 0,
            'atm_ce_iv': 0,
            'atm_pe_iv': 0,
            'atm_strike': 0,
            'spot_price': 0,
            'analyzed_at': datetime.utcnow().isoformat()
        }


# Singleton
_vol_analyzer = None

def get_vol_analyzer() -> SSRVolAnalyzer:
    """Get singleton SSRVolAnalyzer instance."""
    global _vol_analyzer
    if _vol_analyzer is None:
        _vol_analyzer = SSRVolAnalyzer()
    return _vol_analyzer
