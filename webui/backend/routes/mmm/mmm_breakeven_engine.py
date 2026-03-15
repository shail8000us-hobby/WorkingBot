"""
MMM Breakeven Engine — Real-time portfolio breakeven awareness.

Calculates the lower and upper BTC spot prices where total portfolio P&L = 0,
tracks distance to breakeven boundaries, classifies risk zones, and provides
an aggression multiplier for lot calculation.

Design: Intrinsic-only P&L model (no live premium fetches, no time value),
position-change caching (~50-100x frequency reduction), dynamic scan range
that auto-expands to cover distant frozen strikes.

Created: March 15, 2026
"""

import hashlib
import json
import logging
import math
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from .mmm_constants import LOT_SIZE_BTC

log = logging.getLogger('mmm_breakeven_engine')


class BreakevenEngine:
    """
    Computes portfolio breakeven prices and provides aggression multipliers.

    Public methods:
        compute_breakeven(session, spot_price) → BreakevenResult dict
        get_aggression_multiplier(result) → float
        invalidate_cache(session_id) → None

    Thread safety: Uses per-instance lock. Safe for concurrent heartbeats
    across multiple sessions (each session has its own cache entry).
    """

    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    # =========================================================================
    # Public API
    # =========================================================================

    def compute_breakeven(self, session: Dict, spot_price: float) -> Dict:
        """
        Compute portfolio breakeven analysis for a session.

        If positions haven't changed since last computation, reuses cached
        breakeven prices (~0.01ms). On position change, runs full scan+bisection
        (~1ms).

        Returns BreakevenResult dict. Never raises — returns safe defaults on error.
        """
        if spot_price <= 0:
            return self._empty_result(spot_price)

        session_id = session.get('session_id', '')
        params = session.get('params', {})

        if not params.get('breakeven_control_enabled', False):
            return self._empty_result(spot_price, enabled=False)

        try:
            positions = self._collect_open_positions(session)
            if not positions:
                return self._empty_result(spot_price)

            pos_hash = self._hash_positions(positions, session)

            with self._lock:
                cached = self._cache.get(session_id)

            if cached and cached.get('positions_hash') == pos_hash:
                lower = cached['lower_breakeven']
                upper = cached['upper_breakeven']
                prev_band_width_pct = cached.get('band_width_pct')
                from_cache = True
            else:
                # Full scan+bisection (~1ms)
                scan_range = self._compute_scan_range(spot_price, positions, params)
                lower = self._find_breakeven(positions, spot_price, session, 'lower', scan_range)
                upper = self._find_breakeven(positions, spot_price, session, 'upper', scan_range)
                prev_band_width_pct = None
                if cached:
                    prev_band_width_pct = cached.get('band_width_pct')

                # Compute band width before caching
                band_width_pct = self._compute_band_width_pct(lower, upper, spot_price)

                with self._lock:
                    self._cache[session_id] = {
                        'lower_breakeven': lower,
                        'upper_breakeven': upper,
                        'positions_hash': pos_hash,
                        'band_width_pct': band_width_pct,
                        'computed_at': datetime.now(timezone.utc).isoformat(),
                    }
                from_cache = False

            return self._build_result(
                lower, upper, spot_price, session, positions,
                from_cache=from_cache,
                prev_band_width_pct=prev_band_width_pct,
            )

        except Exception as e:
            log.error(f"[{session_id}] Breakeven compute error: {e}", exc_info=True)
            return self._empty_result(spot_price)

    def get_aggression_multiplier(self, result: Optional[Dict]) -> float:
        """
        Returns the lot aggression multiplier for the current breakeven zone.

        Non-directional: applies to ANY triggered adjustment regardless of side.
        Returns 1.0 when disabled, no positions, or zone is SAFE.
        """
        if not result or not result.get('enabled', True):
            return 1.0
        zone = result.get('zone', 'SAFE')
        if zone == 'SAFE':
            return 1.0
        return result.get('multiplier', 1.0)

    def invalidate_cache(self, session_id: str) -> None:
        """
        Invalidate cached breakeven prices for a session.

        Called by the monitor after any position-changing event:
        adjustment fill, strike shift, close-at-5, M1 harvest, M2 recycle,
        operator inject, adopt, perp fill.

        After invalidation, the next heartbeat triggers a full scan+bisection.
        """
        with self._lock:
            self._cache.pop(session_id, None)

    # =========================================================================
    # Position Collection
    # =========================================================================

    def _collect_open_positions(self, session: Dict) -> list:
        """
        Gather all open positions (active + frozen) from both CE and PE sides.

        Returns list of dicts with keys: strike, lots, entry_premium, side, type
        """
        positions = []

        for side_key in ('ce', 'pe'):
            side_state = session.get(side_key, {})
            option_type = 'call' if side_key == 'ce' else 'put'

            # Active strike: original + adjustment fills
            active_strike = side_state.get('active_strike', 0)
            if active_strike and active_strike > 0:
                # Original lots at active strike
                original_lots = side_state.get('original_lots', 0)
                original_prem = side_state.get('original_premium', 0)
                if original_lots > 0:
                    positions.append({
                        'strike': float(active_strike),
                        'lots': original_lots,
                        'entry_premium': float(original_prem),
                        'option_type': option_type,
                        'pos_type': 'original',
                    })

                # Adjustment fills at active strike
                for fill in side_state.get('adjustment_fills', []):
                    fill_lots = fill.get('lots', 0)
                    fill_strike = fill.get('strike', active_strike)
                    fill_prem = fill.get('premium', 0)
                    if fill_lots > 0 and fill_strike > 0:
                        positions.append({
                            'strike': float(fill_strike),
                            'lots': fill_lots,
                            'entry_premium': float(fill_prem),
                            'option_type': option_type,
                            'pos_type': 'adjustment',
                        })

            # Frozen positions at old strikes
            for frozen in side_state.get('frozen_positions', []):
                f_lots = frozen.get('lots', 0)
                f_strike = frozen.get('strike', 0)
                f_prem = frozen.get('entry_premium', 0)
                if f_lots > 0 and f_strike > 0:
                    positions.append({
                        'strike': float(f_strike),
                        'lots': f_lots,
                        'entry_premium': float(f_prem),
                        'option_type': option_type,
                        'pos_type': 'frozen',
                    })

        return positions

    # =========================================================================
    # P&L Computation (Intrinsic-Only)
    # =========================================================================

    def _compute_pnl_at_spot(
        self,
        positions: list,
        spot_h: float,
        session: Dict,
    ) -> float:
        """
        Portfolio P&L at hypothetical spot price (intrinsic-only model).

        For short call at strike K, entry_premium P, lots N:
            intrinsic = max(spot_h - K, 0)
            pnl = (P - intrinsic) * N * LOT_SIZE_BTC

        For short put at strike K, entry_premium P, lots N:
            intrinsic = max(K - spot_h, 0)
            pnl = (P - intrinsic) * N * LOT_SIZE_BTC

        For perp hedge with lots L (signed: positive=long) at avg_entry E:
            pnl = (spot_h - E) * L * LOT_SIZE_BTC

        Conservative bias: ignores remaining extrinsic → narrows breakeven band
        → early warnings. Correct direction for a risk tool.
        """
        total_pnl = 0.0

        for pos in positions:
            strike = pos['strike']
            lots = pos['lots']
            entry_prem = pos['entry_premium']
            opt_type = pos['option_type']

            if opt_type == 'call':
                intrinsic = max(spot_h - strike, 0.0)
            else:
                intrinsic = max(strike - spot_h, 0.0)

            pos_pnl = (entry_prem - intrinsic) * lots * LOT_SIZE_BTC
            total_pnl += pos_pnl

        # Add realized P&L (vertical shift of the curve)
        total_pnl += session.get('realized_pnl', 0.0)

        # Add perp hedge P&L (linear in spot)
        perp_state = session.get('_perp_state', {})
        if perp_state:
            perp_lots = perp_state.get('lots', 0)
            perp_avg_entry = perp_state.get('avg_entry', 0.0)
            perp_direction = perp_state.get('direction', 'long')
            if perp_lots != 0 and perp_avg_entry > 0:
                # Signed lots: positive=long, negative=short
                signed_lots = perp_lots if perp_direction == 'long' else -perp_lots
                perp_pnl = (spot_h - perp_avg_entry) * signed_lots * LOT_SIZE_BTC
                total_pnl += perp_pnl

        return total_pnl

    # =========================================================================
    # Scan Range (Dynamic)
    # =========================================================================

    def _compute_scan_range(
        self,
        spot: float,
        positions: list,
        params: Dict,
    ) -> float:
        """
        Compute the scan range from spot.

        Dynamic: auto-expands to 120% beyond the furthest open strike.
        breakeven_scan_range_pct acts as a minimum floor.
        """
        min_range_from_param = spot * (params.get('breakeven_scan_range_pct', 5.0) / 100.0)

        if not positions:
            return min_range_from_param

        furthest = max(abs(spot - p['strike']) for p in positions)
        min_range_from_strikes = furthest * 1.2  # 20% beyond furthest strike

        return max(min_range_from_strikes, min_range_from_param)

    # =========================================================================
    # Breakeven Finding (Coarse Scan + Binary Search)
    # =========================================================================

    def _find_breakeven(
        self,
        positions: list,
        spot: float,
        session: Dict,
        direction: str,
        scan_range: float,
    ) -> Optional[float]:
        """
        Find breakeven price in the given direction ('lower' or 'upper').

        Pass 1 — Coarse scan: ~80 sample points, detect sign change in PnL.
        Pass 2 — Binary search: converge to within $10 (max 20 iterations).

        Returns None if no breakeven found (portfolio profitable in that direction).
        """
        # Coarse scan step: ~0.2% of spot → ~80 points over scan_range
        step = spot * 0.002
        if step <= 0:
            step = 100.0
        n_steps = max(int(scan_range / step), 80)
        step = scan_range / n_steps

        if direction == 'lower':
            # Walk from spot downward
            bracket_hi = spot
            bracket_lo = None
            for i in range(1, n_steps + 1):
                test_spot = spot - i * step
                if test_spot <= 0:
                    break
                pnl = self._compute_pnl_at_spot(positions, test_spot, session)
                if pnl <= 0:
                    bracket_lo = test_spot
                    bracket_hi = spot - (i - 1) * step
                    break
        else:
            # Walk from spot upward
            bracket_lo = spot
            bracket_hi = None
            for i in range(1, n_steps + 1):
                test_spot = spot + i * step
                pnl = self._compute_pnl_at_spot(positions, test_spot, session)
                if pnl <= 0:
                    bracket_hi = test_spot
                    bracket_lo = spot + (i - 1) * step
                    break

        if bracket_lo is None or bracket_hi is None:
            return None  # No breakeven found — portfolio profitable in this direction

        # Pass 2: Binary search to within $10 precision
        for _ in range(20):
            mid = (bracket_lo + bracket_hi) / 2.0
            pnl_mid = self._compute_pnl_at_spot(positions, mid, session)
            if abs(bracket_hi - bracket_lo) < 10.0:
                return mid
            if pnl_mid > 0:
                # Still profitable — push boundary toward the breakeven
                if direction == 'lower':
                    bracket_hi = mid
                else:
                    bracket_lo = mid
            else:
                # Past breakeven — pull back
                if direction == 'lower':
                    bracket_lo = mid
                else:
                    bracket_hi = mid

        return (bracket_lo + bracket_hi) / 2.0

    # =========================================================================
    # Zone Classification & Multiplier
    # =========================================================================

    def _classify_zone(
        self,
        nearest_distance_pct: Optional[float],
        params: Dict,
    ) -> str:
        """Classify risk zone based on distance to nearest breakeven."""
        if nearest_distance_pct is None:
            return 'SAFE'

        warning_pct = params.get('breakeven_warning_pct', 2.0)
        danger_pct = params.get('breakeven_danger_pct', 1.0)
        critical_pct = params.get('breakeven_critical_pct', 0.5)

        if nearest_distance_pct > warning_pct:
            return 'SAFE'
        elif nearest_distance_pct > danger_pct:
            return 'WARNING'
        elif nearest_distance_pct > critical_pct:
            return 'DANGER'
        else:
            return 'CRITICAL'

    def _compute_multiplier(
        self,
        zone: str,
        nearest_distance_pct: Optional[float],
        params: Dict,
    ) -> float:
        """
        Continuous aggression multiplier ramp based on zone and distance.

        Non-directional: applies to ANY triggered adjustment (no hedge_side filter).
        Ranges: SAFE=1.0, WARNING=1.0-1.3, DANGER=1.3-2.0, CRITICAL=2.0-max_mult.
        Linear interpolation prevents lot-count flip-flops at zone boundaries.
        """
        if zone == 'SAFE' or nearest_distance_pct is None:
            return 1.0

        warning_pct = params.get('breakeven_warning_pct', 2.0)
        danger_pct = params.get('breakeven_danger_pct', 1.0)
        critical_pct = params.get('breakeven_critical_pct', 0.5)
        max_mult = params.get('breakeven_aggression_max', 3.0)

        if zone == 'WARNING':
            denom = warning_pct - danger_pct
            progress = (warning_pct - nearest_distance_pct) / denom if denom > 0 else 0.0
            return 1.0 + min(progress, 1.0) * 0.3

        elif zone == 'DANGER':
            denom = danger_pct - critical_pct
            progress = (danger_pct - nearest_distance_pct) / denom if denom > 0 else 0.0
            return 1.3 + min(progress, 1.0) * 0.7

        elif zone == 'CRITICAL':
            progress = min(1.0, (critical_pct - nearest_distance_pct) / critical_pct) if critical_pct > 0 else 1.0
            return 2.0 + min(max(progress, 0.0), 1.0) * (max_mult - 2.0)

        return 1.0

    # =========================================================================
    # Result Building
    # =========================================================================

    def _build_result(
        self,
        lower: Optional[float],
        upper: Optional[float],
        spot_price: float,
        session: Dict,
        positions: list,
        from_cache: bool,
        prev_band_width_pct: Optional[float],
    ) -> Dict:
        """Assemble the full BreakevenResult dict."""
        params = session.get('params', {})

        # Distances
        distance_lower_pct = None
        distance_upper_pct = None

        if lower is not None and lower < spot_price:
            distance_lower_pct = (spot_price - lower) / spot_price * 100.0
        elif lower is not None:
            distance_lower_pct = 0.0  # already past lower breakeven

        if upper is not None and upper > spot_price:
            distance_upper_pct = (upper - spot_price) / spot_price * 100.0
        elif upper is not None:
            distance_upper_pct = 0.0  # already past upper breakeven

        # Nearest breakeven
        nearest_distance_pct = None
        nearest_side = 'none'
        if distance_lower_pct is not None and distance_upper_pct is not None:
            if distance_lower_pct <= distance_upper_pct:
                nearest_distance_pct = distance_lower_pct
                nearest_side = 'lower'
            else:
                nearest_distance_pct = distance_upper_pct
                nearest_side = 'upper'
        elif distance_lower_pct is not None:
            nearest_distance_pct = distance_lower_pct
            nearest_side = 'lower'
        elif distance_upper_pct is not None:
            nearest_distance_pct = distance_upper_pct
            nearest_side = 'upper'

        zone = self._classify_zone(nearest_distance_pct, params)
        multiplier = self._compute_multiplier(zone, nearest_distance_pct, params)

        # Band width
        band_width_pct = self._compute_band_width_pct(lower, upper, spot_price)

        # Band contracting: shrunk >30% since last recompute
        band_contracting = False
        if prev_band_width_pct is not None and band_width_pct is not None:
            if prev_band_width_pct > 0 and band_width_pct < prev_band_width_pct * 0.70:
                band_contracting = True

        # Narrow band warning
        narrow_threshold = params.get('breakeven_narrow_band_threshold', 5.0)
        is_narrow_band = (
            band_width_pct is not None and band_width_pct < narrow_threshold
        )

        # P&L at current spot
        pnl_at_spot = self._compute_pnl_at_spot(positions, spot_price, session)

        # Perp included?
        perp_state = session.get('_perp_state', {})
        perp_included = bool(perp_state and perp_state.get('lots', 0) != 0)

        # Count positions
        positions_included = len(positions)

        return {
            'enabled': True,
            'lower_breakeven': lower,
            'upper_breakeven': upper,
            'spot_price': spot_price,
            'distance_lower_pct': round(distance_lower_pct, 4) if distance_lower_pct is not None else None,
            'distance_upper_pct': round(distance_upper_pct, 4) if distance_upper_pct is not None else None,
            'nearest_distance_pct': round(nearest_distance_pct, 4) if nearest_distance_pct is not None else None,
            'nearest_side': nearest_side,
            'zone': zone,
            'multiplier': round(multiplier, 4),
            'pnl_at_spot': round(pnl_at_spot, 4),
            'band_width_pct': round(band_width_pct, 4) if band_width_pct is not None else None,
            'band_width_prev_pct': round(prev_band_width_pct, 4) if prev_band_width_pct is not None else None,
            'band_contracting': band_contracting,
            'is_narrow_band': is_narrow_band,
            'computed_at': datetime.now(timezone.utc).isoformat(),
            'positions_included': positions_included,
            'perp_included': perp_included,
            'from_cache': from_cache,
        }

    def _empty_result(self, spot_price: float, enabled: bool = True) -> Dict:
        """Return a safe empty result when computation is skipped."""
        return {
            'enabled': enabled,
            'lower_breakeven': None,
            'upper_breakeven': None,
            'spot_price': spot_price,
            'distance_lower_pct': None,
            'distance_upper_pct': None,
            'nearest_distance_pct': None,
            'nearest_side': 'none',
            'zone': 'SAFE',
            'multiplier': 1.0,
            'pnl_at_spot': None,
            'band_width_pct': None,
            'band_width_prev_pct': None,
            'band_contracting': False,
            'is_narrow_band': False,
            'computed_at': datetime.now(timezone.utc).isoformat(),
            'positions_included': 0,
            'perp_included': False,
            'from_cache': False,
        }

    # =========================================================================
    # Helpers
    # =========================================================================

    def _compute_band_width_pct(
        self,
        lower: Optional[float],
        upper: Optional[float],
        spot: float,
    ) -> Optional[float]:
        """Band width as percentage of spot. None if only one side exists."""
        if lower is None or upper is None:
            return None
        return (upper - lower) / spot * 100.0

    def _hash_positions(self, positions: list, session: Dict) -> str:
        """
        Hash all factors that affect breakeven location.

        Changes: strike, lots, entry_premium (positions), realized_pnl,
        perp avg_entry, perp lots, perp direction.
        """
        key_parts = []

        for pos in sorted(positions, key=lambda p: (p['option_type'], p['strike'], p['pos_type'])):
            key_parts.append(f"{pos['option_type']}:{pos['strike']}:{pos['lots']}:{pos['entry_premium']}")

        key_parts.append(f"realized:{session.get('realized_pnl', 0)}")

        perp = session.get('_perp_state', {})
        if perp:
            key_parts.append(
                f"perp:{perp.get('lots', 0)}:{perp.get('avg_entry', 0)}:{perp.get('direction', 'long')}"
            )

        raw = '|'.join(key_parts)
        return hashlib.md5(raw.encode()).hexdigest()


# =============================================================================
# Singleton
# =============================================================================

_engine_instance: Optional[BreakevenEngine] = None
_engine_lock = threading.Lock()


def get_breakeven_engine() -> BreakevenEngine:
    """Get singleton BreakevenEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                _engine_instance = BreakevenEngine()
    return _engine_instance
