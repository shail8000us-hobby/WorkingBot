"""
MMM Gamma Detector Engine — Portfolio Curvature Scanning.

Identifies zones where the portfolio's loss rate begins to accelerate as BTC
spot moves away from current price. Companion module to the Breakeven Engine.

- Breakeven Engine answers: "Where does the portfolio lose money?"
- Gamma Detector answers:   "Where does the portfolio start losing money faster?"

Observation-only by default. Zero trading impact until Phase 9 is enabled via
gamma_severity_multiplier_enabled=True.

Created: March 15, 2026
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from .mmm_constants import LOT_SIZE_BTC

log = logging.getLogger('mmm_gamma_detector')


class GammaDetector:
    """
    Detects portfolio curvature boundaries by scanning for kinks in the
    piecewise-linear PnL curve.

    Kinks occur at option strikes. The detector walks outward from current spot
    and reports the nearest kink in each direction (lower and upper).

    Zone classification uses distance from current spot to nearest boundary —
    identical mental model to the Breakeven Engine.

    Thread safety: per-instance lock, one cache entry per session.
    """

    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    # =========================================================================
    # Public API
    # =========================================================================

    def compute_gamma(self, session: Dict, spot_price: float,
                      be_engine=None) -> Dict:
        """
        Compute gamma boundary analysis for a session.

        Args:
            session:    Session state dict.
            spot_price: Current BTC spot price.
            be_engine:  Optional BreakevenEngine instance (avoids double lookup).

        Returns GammaResult dict. Never raises — returns safe defaults on error.
        """
        if spot_price <= 0:
            return self._empty_result(spot_price)

        params = session.get('params', {})

        if not params.get('gamma_detector_enabled', False):
            return self._empty_result(spot_price, enabled=False)

        try:
            if be_engine is None:
                from .mmm_breakeven_engine import get_breakeven_engine
                be_engine = get_breakeven_engine()

            positions = be_engine._collect_open_positions(session)
            if not positions:
                return self._empty_result(spot_price)

            pos_hash = be_engine._hash_positions(positions, session)
            session_id = session.get('session_id', '')

            with self._lock:
                cached = self._cache.get(session_id)

            if cached and cached.get('positions_hash') == pos_hash:
                lower = cached['lower_boundary']
                upper = cached['upper_boundary']
                sev_lower = cached['severity_lower']
                sev_upper = cached['severity_upper']
                from_cache = True
            else:
                step = spot_price * (params.get('gamma_step_pct', 0.5) / 100.0)
                scan_steps = int(params.get('gamma_scan_steps', 40))
                epsilon = params.get('gamma_detect_epsilon', 0.3)

                lower, upper, sev_lower, sev_upper = self._run_boundary_scan(
                    positions, session, spot_price, step, scan_steps,
                    epsilon, be_engine
                )
                with self._lock:
                    self._cache[session_id] = {
                        'positions_hash': pos_hash,
                        'lower_boundary': lower,
                        'upper_boundary': upper,
                        'severity_lower': sev_lower,
                        'severity_upper': sev_upper,
                    }
                from_cache = False

            return self._build_result(
                lower, upper, sev_lower, sev_upper,
                spot_price, session, positions, from_cache
            )

        except Exception as exc:
            log.warning(f'[gamma_detector] compute_gamma error (non-fatal): {exc}')
            return self._empty_result(spot_price)

    def invalidate_cache(self, session_id: str) -> None:
        """Invalidate cached boundary scan for a session (call on position change)."""
        with self._lock:
            self._cache.pop(session_id, None)

    # =========================================================================
    # Internal
    # =========================================================================

    def _run_boundary_scan(
        self,
        positions,
        session: Dict,
        spot: float,
        step: float,
        scan_steps: int,
        epsilon: float,
        be_engine,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        Walk outward from spot in both directions. Return the first kink found
        in each direction and its normalized severity.

        Returns: (lower_boundary, upper_boundary, sev_lower, sev_upper)
        """
        total_lots = sum(pos.get('lots', 0) for pos in positions)
        total_lot_exposure = max(total_lots * LOT_SIZE_BTC, 1e-6)

        lower_boundary = None
        sev_lower = None
        for i in range(1, scan_steps + 1):  # start at 1: scan strictly below current spot
            test_spot = spot - i * step
            if test_spot <= 0:
                break
            sd = self._compute_second_diff(positions, session, test_spot, step, be_engine)
            if sd < -epsilon:
                lower_boundary = test_spot
                sev_lower = sd / total_lot_exposure
                break

        upper_boundary = None
        sev_upper = None
        for i in range(1, scan_steps + 1):  # start at 1: scan strictly above current spot
            test_spot = spot + i * step
            sd = self._compute_second_diff(positions, session, test_spot, step, be_engine)
            if sd < -epsilon:
                upper_boundary = test_spot
                sev_upper = sd / total_lot_exposure
                break

        return lower_boundary, upper_boundary, sev_lower, sev_upper

    def _compute_second_diff(
        self,
        positions,
        session: Dict,
        test_spot: float,
        step: float,
        be_engine,
    ) -> float:
        """
        Second-difference of PnL at test_spot:
            PnL(test_spot - step) - 2 * PnL(test_spot) + PnL(test_spot + step)

        Negative value at a kink (option strike) means losses accelerate there.
        """
        pnl_left   = be_engine._compute_pnl_at_spot(positions, test_spot - step, session)
        pnl_center = be_engine._compute_pnl_at_spot(positions, test_spot,        session)
        pnl_right  = be_engine._compute_pnl_at_spot(positions, test_spot + step, session)
        return pnl_left - 2.0 * pnl_center + pnl_right

    def _classify_zone(self, nearest_distance_pct: Optional[float], params: Dict) -> str:
        """Classify zone by distance from spot to nearest gamma boundary."""
        if nearest_distance_pct is None:
            return 'SAFE'
        warning = params.get('gamma_warning_distance_pct', 3.0)
        danger  = params.get('gamma_danger_distance_pct', 1.5)
        if nearest_distance_pct > warning:
            return 'SAFE'
        elif nearest_distance_pct > danger:
            return 'WARNING'
        else:
            return 'DANGER'

    def _build_result(
        self,
        lower: Optional[float],
        upper: Optional[float],
        sev_lower: Optional[float],
        sev_upper: Optional[float],
        spot_price: float,
        session: Dict,
        positions,
        from_cache: bool,
    ) -> Dict:
        """Build the full GammaResult dict."""
        params = session.get('params', {})

        lower_distance_pct = None
        upper_distance_pct = None

        if lower is not None and spot_price > 0:
            lower_distance_pct = abs(spot_price - lower) / spot_price * 100.0
        if upper is not None and spot_price > 0:
            upper_distance_pct = abs(upper - spot_price) / spot_price * 100.0

        # Nearest boundary
        distances = [d for d in [lower_distance_pct, upper_distance_pct] if d is not None]
        nearest_distance_pct = min(distances) if distances else None

        if nearest_distance_pct is None:
            nearest_side = 'none'
        elif lower_distance_pct is not None and lower_distance_pct == nearest_distance_pct:
            nearest_side = 'lower'
        else:
            nearest_side = 'upper'

        gamma_zone = self._classify_zone(nearest_distance_pct, params)

        # BUG-C6 fix: read 'perp_hedge' (actual key), not '_perp_state' (phantom)
        perp = session.get('perp_hedge', {})
        perp_included = bool(perp and perp.get('lots', 0) != 0)

        return {
            'enabled': True,
            'spot_price': spot_price,
            'lower_gamma_boundary': lower,
            'upper_gamma_boundary': upper,
            'gamma_severity_lower': sev_lower,
            'gamma_severity_upper': sev_upper,
            'gamma_zone': gamma_zone,
            'lower_distance_pct': lower_distance_pct,
            'upper_distance_pct': upper_distance_pct,
            'nearest_distance_pct': nearest_distance_pct,
            'nearest_side': nearest_side,
            'from_cache': from_cache,
            'positions_included': len(positions),
            'perp_included': perp_included,
            'observation_only': not params.get('gamma_severity_multiplier_enabled', False),
            'computed_at': datetime.now(timezone.utc).isoformat(),
        }

    def _empty_result(self, spot_price: float, enabled: bool = True) -> Dict:
        """Return safe empty result (no positions or disabled)."""
        return {
            'enabled': enabled,
            'spot_price': spot_price,
            'lower_gamma_boundary': None,
            'upper_gamma_boundary': None,
            'gamma_severity_lower': None,
            'gamma_severity_upper': None,
            'gamma_zone': 'SAFE',
            'lower_distance_pct': None,
            'upper_distance_pct': None,
            'nearest_distance_pct': None,
            'nearest_side': 'none',
            'from_cache': False,
            'positions_included': 0,
            'perp_included': False,
            'observation_only': True,
            'computed_at': datetime.now(timezone.utc).isoformat(),
        }


# Module singleton
_gamma_detector: Optional[GammaDetector] = None
_gamma_detector_lock = threading.Lock()


def get_gamma_detector() -> GammaDetector:
    """Return the module-level GammaDetector singleton."""
    global _gamma_detector
    if _gamma_detector is None:
        with _gamma_detector_lock:
            if _gamma_detector is None:
                _gamma_detector = GammaDetector()
    return _gamma_detector
