"""
MMM Adaptive Tuning Engine — Parameter Optimization per Market Regime

Plugs into the heartbeat at Step 5.3 (after cooldown, before ATM Shield).
Classifies market regime and adjusts Tier-3 (adaptive) parameters within
preset-profile bounds based on a composite score.

Modes (controlled by session['params']['adaptive_mode']):
  'manual'   — operator sets everything, this engine is a no-op
  'preset'   — preset values loaded at session start, engine does NOT run
  'adaptive' — engine runs every beat, auto-tunes within profile bounds

Design principles:
  - Deterministic: every parameter change traces to a regime + score
  - Auditable: every write is logged to activity log
  - Non-breaking: off by default (adaptive_mode='manual')
  - Operator-safe: params manually changed by operator are locked from engine
  - Rate-limited: max 2 writes per hour, min 3 beats between changes

See tasks/MMM_ADAPTIVE_TUNING_PLAN.md for full design.
"""

import logging
import math
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

log = logging.getLogger('mmm_adaptive')

# ─────────────────────────────────────────────────────────────────────────────
# Regime labels
# ─────────────────────────────────────────────────────────────────────────────
REGIME_RANGING   = 'RANGING'
REGIME_TRENDING  = 'TRENDING'
REGIME_VOL_SPIKE = 'VOL_SPIKE'
REGIME_UNKNOWN   = 'UNKNOWN'   # < 2 stable beats — no adaptation yet

# Minimum consecutive beats a regime must be stable before we adapt
REGIME_DEBOUNCE_BEATS = 2

# ─────────────────────────────────────────────────────────────────────────────
# Hard parameter bounds — adaptive engine NEVER exceeds these
# ─────────────────────────────────────────────────────────────────────────────
PARAM_LIMITS: Dict[str, Tuple[float, float]] = {
    'atm_shield_proximity_pct':  (0.2,  3.0),
    'atm_shield_target_otm_pct': (0.5,  3.0),
    'atm_shield_cooldown_mins':  (3.0, 30.0),
    'premium_buffer_pct':        (0.03, 0.10),
}

# Parameters managed by this engine (all are in HOT_RELOAD_PARAMS)
ADAPTIVE_PARAMS = set(PARAM_LIMITS.keys())

# Rate limits
MIN_BEATS_BETWEEN_WRITES = 3
MIN_SECONDS_BETWEEN_WRITES = 60
MAX_WRITES_PER_HOUR = 2

# ─────────────────────────────────────────────────────────────────────────────
# Preset profiles — base values per strategy type
# ─────────────────────────────────────────────────────────────────────────────
# premium_buffer_pct stored as fraction (0.06 = 6%)
_PROFILES: Dict[str, Dict[str, float]] = {
    'strangle': {
        'atm_shield_proximity_pct':  0.7,
        'atm_shield_target_otm_pct': 1.2,
        'atm_shield_cooldown_mins':  12.0,
        'premium_buffer_pct':         0.06,
    },
    'straddle': {
        'atm_shield_proximity_pct':  0.3,
        'atm_shield_target_otm_pct': 0.8,
        'atm_shield_cooldown_mins':   7.0,
        'premium_buffer_pct':         0.04,
    },
    'short_window': {
        'atm_shield_proximity_pct':  1.0,
        'atm_shield_target_otm_pct': 1.5,
        'atm_shield_cooldown_mins':   5.0,
        'premium_buffer_pct':         0.05,
    },
}

# Per-regime score multipliers applied to each param's base value
# Positive = increase as score rises, Negative = decrease as score rises
# Formula: new = base × (1 + multiplier × composite_score)
_REGIME_SCORE_MULT: Dict[str, Dict[str, float]] = {
    REGIME_RANGING: {
        # Ranging: fire shield LESS eagerly (price will bounce),
        # longer cooldown, slightly reduce hedge size
        'atm_shield_proximity_pct':  -0.04,   # tighten proximity (fire closer to ATM)
        'atm_shield_target_otm_pct':  0.00,   # retreat distance unchanged
        'atm_shield_cooldown_mins':  +0.12,   # extend cooldown (avoid whipsaw fires)
        'premium_buffer_pct':        -0.02,   # slightly less aggressive buffer
    },
    REGIME_TRENDING: {
        # Trending: fire shield EARLIER (trend will push through ATM),
        # shorter cooldown, more aggressive sizing
        'atm_shield_proximity_pct':  +0.08,   # widen proximity (fire sooner)
        'atm_shield_target_otm_pct': +0.06,   # retreat farther (trend will follow)
        'atm_shield_cooldown_mins':  -0.04,   # shorten cooldown (may need re-fire)
        'premium_buffer_pct':        +0.03,   # more hedge buffer for trending market
    },
    REGIME_VOL_SPIKE: {
        # Vol spike: fire very early, retreat far, keep cooldown stable
        'atm_shield_proximity_pct':  +0.10,   # widest proximity
        'atm_shield_target_otm_pct': +0.08,   # farthest retreat
        'atm_shield_cooldown_mins':   0.00,   # cooldown unchanged (don't drain budget)
        'premium_buffer_pct':        +0.05,   # most aggressive buffer in vol spike
    },
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round2(value: float) -> float:
    return round(value, 2)


# ─────────────────────────────────────────────────────────────────────────────
# AdaptiveEngine
# ─────────────────────────────────────────────────────────────────────────────
class AdaptiveEngine:
    """Stateless logic engine — all state lives in session dict."""

    # ── Regime classification ─────────────────────────────────────────────

    def _classify_raw_regime(self, session: dict) -> str:
        """
        Classify current market regime from session state written by regime engine.
        Returns one of: RANGING / TRENDING / VOL_SPIKE
        Falls back to UNKNOWN if insufficient data.
        """
        vol_regime  = session.get('_vol_regime', 'NORMAL')
        trend_tier  = session.get('_trend_tier', 0)
        spot_history = session.get('_vol_spot_history', [])

        # VOL_SPIKE: elevated/high vol dominates all other signals
        if vol_regime in ('ELEVATED', 'HIGH'):
            return REGIME_VOL_SPIKE

        # TRENDING: any confirmed trend tier (Tier 1 = ALERT and above)
        if trend_tier >= 1:
            return REGIME_TRENDING

        # RANGING: need at least 5 spot history points to confirm
        if len(spot_history) < 5:
            return REGIME_UNKNOWN

        recent = spot_history[-10:]   # last 10 beats
        span = max(recent) - min(recent)
        mid  = (max(recent) + min(recent)) / 2 if (max(recent) + min(recent)) > 0 else 1
        range_pct = (span / mid) * 100 if mid > 0 else 0.0

        if range_pct < 0.5:
            return REGIME_RANGING

        # Inconclusive: neither vol spike, nor trend, nor tight range
        # Treat as RANGING (neutral — least disruptive default)
        return REGIME_RANGING

    def _get_stable_regime(self, session: dict) -> str:
        """
        Apply debounce: regime must be stable for REGIME_DEBOUNCE_BEATS consecutive
        beats before we consider it confirmed. Returns UNKNOWN while stabilising.
        """
        raw = self._classify_raw_regime(session)

        candidate        = session.get('_adaptive_regime_candidate', raw)
        candidate_beats  = session.get('_adaptive_regime_candidate_beats', 0)
        current_stable   = session.get('_adaptive_regime', REGIME_UNKNOWN)

        if raw == candidate:
            candidate_beats += 1
        else:
            candidate       = raw
            candidate_beats = 1

        session['_adaptive_regime_candidate']       = candidate
        session['_adaptive_regime_candidate_beats'] = candidate_beats

        if candidate_beats >= REGIME_DEBOUNCE_BEATS:
            session['_adaptive_regime'] = candidate
            return candidate

        return current_stable   # not yet confirmed → hold previous

    # ── Composite score ───────────────────────────────────────────────────

    def _compute_score(self, session: dict, minutes_to_expiry: float) -> float:
        """
        Composite score 0–10. Higher = more stressed conditions.
        Inputs: whipsaw score, breakeven zone, shield fires, near-expiry.
        """
        whipsaw_score = min(4, session.get('_whipsaw_score', 0))

        zone_pts = {'SAFE': 0, 'WARNING': 1, 'DANGER': 2, 'CRITICAL': 3}
        be_zone = session.get('_breakeven_zone', 'SAFE')
        zone_score = zone_pts.get(be_zone, 0)

        fires_ce = session.get('_atm_shield_count_ce', 0)
        fires_pe = session.get('_atm_shield_count_pe', 0)
        fires_total = fires_ce + fires_pe
        fire_score = min(2, fires_total)

        expiry_score = 1 if (0 < minutes_to_expiry < 60) else 0

        raw = whipsaw_score + zone_score + fire_score + expiry_score
        # Normalise to 0–10
        max_raw = 4 + 3 + 2 + 1
        return _round2((raw / max_raw) * 10)

    # ── Operator override detection ───────────────────────────────────────

    def _detect_and_lock_overrides(self, session: dict) -> None:
        """
        Compare current params vs what the engine last wrote.
        Any divergence means the operator changed the param → lock it.
        """
        last_written = session.get('_adaptive_last_written', {})
        if not last_written:
            return

        overrides = set(session.get('_adaptive_operator_overrides', []))
        params = session.get('params', {})

        for param, written_val in last_written.items():
            if param in overrides:
                continue
            current_val = params.get(param)
            if current_val is None:
                continue
            # Allow 0.1% float tolerance
            tol = abs(written_val) * 0.001 + 1e-9
            if abs(current_val - written_val) > tol:
                overrides.add(param)
                log.info(
                    "[%s] Adaptive: operator manually changed '%s' "
                    "(was %.4f, now %.4f) — locking from auto-tune",
                    session.get('session_id', '?'), param, written_val, current_val
                )

        session['_adaptive_operator_overrides'] = list(overrides)

    # ── Rate limit check ──────────────────────────────────────────────────

    def _can_write(self, session: dict) -> bool:
        """Check rate limits before writing any parameter changes."""
        now = time.time()

        # Min beats between writes
        beats_since = session.get('_adaptive_beats_since_write', MIN_BEATS_BETWEEN_WRITES + 1)
        if beats_since < MIN_BEATS_BETWEEN_WRITES:
            return False

        # Min seconds between writes
        last_write = session.get('_adaptive_last_write_time', 0.0)
        if (now - last_write) < MIN_SECONDS_BETWEEN_WRITES:
            return False

        # Max writes per hour
        write_times = session.get('_adaptive_write_history', [])
        write_times = [t for t in write_times if (now - t) < 3600]
        if len(write_times) >= MAX_WRITES_PER_HOUR:
            return False

        return True

    def _record_write(self, session: dict) -> None:
        now = time.time()
        session['_adaptive_beats_since_write'] = 0
        session['_adaptive_last_write_time'] = now
        history = session.get('_adaptive_write_history', [])
        history = [t for t in history if (now - t) < 3600]
        history.append(now)
        session['_adaptive_write_history'] = history

    def _increment_beat(self, session: dict) -> None:
        beats = session.get('_adaptive_beats_since_write', 0)
        session['_adaptive_beats_since_write'] = beats + 1

    # ── Preset loader (called at session start) ───────────────────────────

    @staticmethod
    def load_preset(session: dict) -> Dict[str, float]:
        """
        Load a preset profile into session['params'].
        Called at session start when adaptive_mode='preset' or 'adaptive'.
        Returns dict of param → value that was loaded.
        """
        preset_name = session.get('params', {}).get('adaptive_preset', 'strangle')
        profile = _PROFILES.get(preset_name, _PROFILES['strangle'])
        params = session.setdefault('params', {})
        loaded = {}
        for param, value in profile.items():
            params[param] = value
            loaded[param] = value
        log.info("[%s] Adaptive: loaded preset '%s': %s",
                 session.get('session_id', '?'), preset_name, loaded)
        return loaded

    # ── Main entry point ──────────────────────────────────────────────────

    def evaluate(self, session: dict, minutes_to_expiry: float) -> None:
        """
        Called every heartbeat at Step 5.3.
        Reads session state, classifies regime, applies parameter adjustments.
        """
        params = session.get('params', {})
        sid = session.get('session_id', '?')

        # Only run in adaptive mode
        if params.get('adaptive_mode', 'manual') != 'adaptive':
            self._increment_beat(session)
            return

        # Safety: circuit breaker open or margin in survival → hold last-known-good
        circuit_open = session.get('_circuit_breaker_state', 'CLOSED') == 'OPEN'
        margin_tier  = session.get('_margin_tier', 'GREEN')
        if circuit_open or margin_tier in ('ORANGE', 'RED', 'CRITICAL'):
            self._increment_beat(session)
            return

        # Detect operator overrides before computing new values
        self._detect_and_lock_overrides(session)
        overrides = set(session.get('_adaptive_operator_overrides', []))

        # Classify regime (debounced)
        regime = self._get_stable_regime(session)
        if regime == REGIME_UNKNOWN:
            self._increment_beat(session)
            return   # not enough data yet

        # Compute composite score
        score = self._compute_score(session, minutes_to_expiry)

        # Get profile for this preset
        preset_name = params.get('adaptive_preset', 'strangle')
        profile = _PROFILES.get(preset_name, _PROFILES['strangle'])
        regime_mult = _REGIME_SCORE_MULT.get(regime, _REGIME_SCORE_MULT[REGIME_RANGING])

        # Compute desired values
        desired: Dict[str, float] = {}
        for param, base in profile.items():
            if param in overrides:
                continue   # operator owns this param
            mult = regime_mult.get(param, 0.0)
            raw  = base * (1 + mult * (score / 10))
            lo, hi = PARAM_LIMITS[param]
            desired[param] = _clamp(_round2(raw), lo, hi)

        if not desired:
            self._increment_beat(session)
            return   # all params locked by operator

        # Check if any value actually changed (avoid spurious writes)
        changed: Dict[str, Tuple[float, float]] = {}   # param → (old, new)
        for param, new_val in desired.items():
            old_val = params.get(param)
            if old_val is None:
                continue
            tol = abs(old_val) * 0.001 + 1e-9
            if abs(new_val - old_val) > tol:
                changed[param] = (old_val, new_val)

        if not changed:
            self._increment_beat(session)
            return   # nothing to write

        # Rate limit: may not write yet
        if not self._can_write(session):
            self._increment_beat(session)
            return

        # Dry-run: log what would change but do NOT write params
        dry_run = params.get('adaptive_dry_run', False)
        if dry_run:
            try:
                from .mmm_activity import log_activity
                changes_str = ', '.join(
                    f"{p}: {o:.4f}→{n:.4f} (dry)" for p, (o, n) in changed.items()
                )
                log_activity(
                    'param_adapted',
                    f"Adaptive DRY-RUN [{regime}] score={score:.1f} | {changes_str}",
                    sid, 'info',
                    {'dry_run': True, 'regime': regime, 'score': score,
                     'changes': {p: {'from': o, 'to': n} for p, (o, n) in changed.items()}},
                )
            except Exception:
                pass
            self._increment_beat(session)
            return

        # Write changes
        last_written = {}
        for param, (old_val, new_val) in changed.items():
            params[param] = new_val
            last_written[param] = new_val

        # Persist what we wrote (for override detection next beat)
        session['_adaptive_last_written'] = {**session.get('_adaptive_last_written', {}), **last_written}
        self._record_write(session)

        # Update metrics
        session['_adaptive_last_regime'] = regime
        session['_adaptive_last_score']  = score

        # Log to activity log (non-blocking; never throws)
        try:
            from .mmm_activity import log_activity
            changes_str = ', '.join(
                f"{p}: {o:.4f}→{n:.4f}" for p, (o, n) in changed.items()
            )
            log_activity(
                'param_adapted',
                f"Adaptive [{regime}] score={score:.1f} | {changes_str}",
                sid, 'info',
                {
                    'regime':  regime,
                    'score':   score,
                    'preset':  preset_name,
                    'changes': {p: {'from': o, 'to': n} for p, (o, n) in changed.items()},
                },
            )
        except Exception:
            pass

        log.info(
            "[%s] Adaptive: regime=%s score=%.1f preset=%s | %s",
            sid, regime, score, preset_name,
            ', '.join(f"{p}={n:.4f}" for p, (_, n) in changed.items())
        )


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────
_adaptive_engine: Optional[AdaptiveEngine] = None


def get_adaptive_engine() -> AdaptiveEngine:
    global _adaptive_engine
    if _adaptive_engine is None:
        _adaptive_engine = AdaptiveEngine()
    return _adaptive_engine
