"""
SSR ALGO DTE Manager - DTE Lifecycle Management & Theta Schedule

Makes the algo time-aware — different DTE ranges require different behavior:
- EARLY LIFE (>21 DTE): Build position, tight risk management
- PEAK THETA (7-21 DTE): Relax delta, let theta work
- GAMMA DANGER (3-7 DTE): Tighten everything, prepare for exit
- EXIT ZONE (<3 DTE): Force exit via exit manager

Created: February 20, 2026
Phase 6 of SSR Algo Development Plan
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from .ssr_algo_engine import normalize_expiry_format

log = logging.getLogger('ssr_algo_dte_manager')

IST = ZoneInfo('Asia/Kolkata')

# DTE phase definitions
DTE_PHASES = {
    'EARLY_LIFE': {
        'name': 'Early Life',
        'min_dte': 21,
        'delta_threshold_multiplier': 0.75,   # Tighter
        'profit_target_multiplier': 1.0,
        'description': 'Build position, tight risk management. Theta is minimal.'
    },
    'PEAK_THETA': {
        'name': 'Peak Theta',
        'min_dte': 7,
        'delta_threshold_multiplier': 1.5,    # Relaxed — let theta work
        'profit_target_multiplier': 0.8,      # Lower target — take money sooner
        'description': 'Relax delta band, let theta decay work for you.'
    },
    'GAMMA_DANGER': {
        'name': 'Gamma Danger',
        'min_dte': 3,
        'delta_threshold_multiplier': 0.5,    # Very tight
        'profit_target_multiplier': 0.5,      # Take any profit
        'description': 'Gamma dominates. Tighten everything, prepare for exit.'
    },
    'EXIT_ZONE': {
        'name': 'Exit Zone',
        'min_dte': 0,
        'delta_threshold_multiplier': 0.25,
        'profit_target_multiplier': 0.25,
        'description': 'Too close to expiry. Force exit.'
    }
}


class SSRDTEManager:
    """
    Manages DTE lifecycle phases for SSR Algo sessions.

    Dynamically adjusts delta hedge thresholds and profit targets
    based on how many days remain until expiry.
    """

    def calculate_dte(self, expiry: str) -> float:
        """
        Calculate fractional days to expiry.

        Args:
            expiry: Expiry date in DDMMYYYY or DDMMYY format

        Returns:
            Fractional days to expiry
        """
        try:
            normalized = normalize_expiry_format(expiry)
            expiry_dt = datetime.strptime(normalized, '%d%m%Y')
            expiry_dt = expiry_dt.replace(hour=17, minute=30, tzinfo=IST)
            now = datetime.now(IST)
            diff = expiry_dt - now
            return max(diff.total_seconds() / 86400, 0.0)
        except Exception as e:
            log.warning(f"Could not calculate DTE for {expiry}: {e}")
            return 999.0

    def get_dte_phase(self, session: Dict) -> Dict:
        """
        Determine current DTE phase for a session.

        Args:
            session: SSR Algo session data

        Returns:
            {
                'dte': float,
                'phase': str,
                'phase_name': str,
                'recommended_delta_threshold': float,
                'recommended_profit_target_multiplier': float,
                'description': str
            }
        """
        expiry = session.get('expiry', '')
        dte = self.calculate_dte(expiry)

        if dte > 21:
            phase_key = 'EARLY_LIFE'
        elif dte > 7:
            phase_key = 'PEAK_THETA'
        elif dte > 3:
            phase_key = 'GAMMA_DANGER'
        else:
            phase_key = 'EXIT_ZONE'

        phase = DTE_PHASES[phase_key]

        # Calculate recommended delta threshold
        base_config = session.get('delta_hedge_config', {})
        base_micro = base_config.get('micro_hedge_threshold', 0.20)
        recommended_delta = base_micro * phase['delta_threshold_multiplier']

        return {
            'dte': round(dte, 2),
            'phase': phase_key,
            'phase_name': phase['name'],
            'delta_threshold_multiplier': phase['delta_threshold_multiplier'],
            'recommended_delta_threshold': round(recommended_delta, 4),
            'recommended_profit_target_multiplier': phase['profit_target_multiplier'],
            'description': phase['description']
        }

    def apply_dte_adjustments(self, session: Dict, dte_phase: Dict) -> Dict:
        """
        Return adjusted config for the current DTE phase.

        These adjustments are per-cycle (not persisted) — they override
        the static config for this monitoring cycle only.

        Args:
            session: SSR Algo session data
            dte_phase: From get_dte_phase()

        Returns:
            {
                'delta_threshold': float,
                'profit_target_multiplier': float,
                'phase': str
            }
        """
        return {
            'delta_threshold': dte_phase.get('recommended_delta_threshold'),
            'profit_target_multiplier': dte_phase.get('recommended_profit_target_multiplier', 1.0),
            'phase': dte_phase.get('phase', 'UNKNOWN')
        }

    def should_close_far_otm_near_expiry(self, session: Dict) -> list:
        """
        Check if far OTM sell legs should be closed near expiry.

        If DTE < 5 and far OTM legs have very low premium, recommend
        buying them back to eliminate gamma risk.

        Args:
            session: SSR Algo session data

        Returns:
            List of leg dicts that should be closed
        """
        expiry = session.get('expiry', '')
        dte = self.calculate_dte(expiry)

        if dte >= 5:
            return []

        legs_to_close = []
        live_pnl = session.get('live_pnl', {})
        per_leg = live_pnl.get('per_leg_pnl', [])

        for leg in per_leg:
            leg_key = leg.get('leg_key', '')
            if 'far_otm' in leg_key:
                current_price = leg.get('current_price', 0)
                if current_price < 5:
                    legs_to_close.append({
                        'symbol': leg.get('symbol'),
                        'leg_key': leg_key,
                        'current_price': current_price,
                        'reason': f'Far OTM premium ${current_price:.2f} < $5 with DTE {dte:.1f}'
                    })

        return legs_to_close


# Singleton
_dte_manager = None

def get_dte_manager() -> SSRDTEManager:
    """Get singleton SSRDTEManager instance."""
    global _dte_manager
    if _dte_manager is None:
        _dte_manager = SSRDTEManager()
    return _dte_manager
