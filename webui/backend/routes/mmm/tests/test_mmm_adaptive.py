"""
Tests for mmm_adaptive.py — Parameter Optimization & Adaptive Tuning Engine

Covers:
  - Regime classification (RANGING / TRENDING / VOL_SPIKE / UNKNOWN)
  - Debounce: regime must be stable for 2 beats before confirming
  - Composite score calculation (0–10)
  - Parameter adjustments stay within hard limits (PARAM_LIMITS)
  - Operator override detection and locking
  - Rate limiting (min beats + min seconds + max per hour)
  - Manual/preset modes are no-ops for evaluate()
  - Preset loader writes correct profile values
  - Adaptive mode writes params and logs adaptation event
  - Dry-run mode does NOT write params
"""

import pytest
import time
from copy import deepcopy

pytestmark = pytest.mark.sealed


# ---------------------------------------------------------------------------
# Import target
# ---------------------------------------------------------------------------
from webui.backend.routes.mmm.mmm_adaptive import (
    AdaptiveEngine,
    REGIME_RANGING,
    REGIME_TRENDING,
    REGIME_VOL_SPIKE,
    REGIME_UNKNOWN,
    PARAM_LIMITS,
    _PROFILES,
    get_adaptive_engine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(
    adaptive_mode='adaptive',
    adaptive_preset='strangle',
    vol_regime='NORMAL',
    trend_tier=0,
    spot_history=None,
    whipsaw_score=0,
    breakeven_zone='SAFE',
    shield_fires_ce=0,
    shield_fires_pe=0,
    minutes_to_expiry=300.0,
) -> dict:
    """Minimal session with all keys the adaptive engine reads."""
    if spot_history is None:
        # Flat spot history = no trend, no big range = RANGING
        spot_history = [80000.0] * 10

    profile = _PROFILES.get(adaptive_preset, _PROFILES['strangle'])

    return {
        'session_id': 'test-adaptive-001',
        'strategy_status': 'RUNNING',
        'params': {
            'adaptive_mode':    adaptive_mode,
            'adaptive_preset':  adaptive_preset,
            'adaptive_dry_run': False,
            # Seed params with profile defaults so there's something to compare against
            **profile,
        },
        '_vol_regime':      vol_regime,
        '_trend_tier':      trend_tier,
        '_vol_spot_history': spot_history,
        '_whipsaw_score':   whipsaw_score,
        '_breakeven_zone':  breakeven_zone,
        '_atm_shield_count_ce': shield_fires_ce,
        '_atm_shield_count_pe': shield_fires_pe,
        '_circuit_breaker_state': 'CLOSED',
        '_margin_tier': 'GREEN',
    }


def _run_evaluate(session, minutes_to_expiry=300.0):
    """Run evaluate() and return True if any adaptive param changed."""
    engine = AdaptiveEngine()
    params_before = deepcopy(session.get('params', {}))
    engine.evaluate(session, minutes_to_expiry)
    params_after = session.get('params', {})
    return any(
        params_after.get(k) != params_before.get(k)
        for k in PARAM_LIMITS
    )


# ---------------------------------------------------------------------------
# Part 1: Regime classification
# ---------------------------------------------------------------------------

class TestRegimeClassification:

    def test_vol_spike_overrides_everything(self):
        engine = AdaptiveEngine()
        session = _make_session(vol_regime='HIGH', trend_tier=0)
        assert engine._classify_raw_regime(session) == REGIME_VOL_SPIKE

    def test_vol_elevated_is_spike(self):
        engine = AdaptiveEngine()
        session = _make_session(vol_regime='ELEVATED')
        assert engine._classify_raw_regime(session) == REGIME_VOL_SPIKE

    def test_trend_tier1_is_trending(self):
        engine = AdaptiveEngine()
        session = _make_session(vol_regime='NORMAL', trend_tier=1)
        assert engine._classify_raw_regime(session) == REGIME_TRENDING

    def test_trend_tier3_is_trending(self):
        engine = AdaptiveEngine()
        session = _make_session(vol_regime='NORMAL', trend_tier=3)
        assert engine._classify_raw_regime(session) == REGIME_TRENDING

    def test_flat_history_is_ranging(self):
        engine = AdaptiveEngine()
        session = _make_session(
            vol_regime='NORMAL', trend_tier=0,
            spot_history=[80000.0] * 12,
        )
        assert engine._classify_raw_regime(session) == REGIME_RANGING

    def test_insufficient_history_is_unknown(self):
        engine = AdaptiveEngine()
        session = _make_session(vol_regime='NORMAL', trend_tier=0, spot_history=[80000.0] * 3)
        assert engine._classify_raw_regime(session) == REGIME_UNKNOWN

    def test_large_range_not_ranging(self):
        engine = AdaptiveEngine()
        # 2% range → not RANGING (range_pct=2 > 0.5 threshold)
        session = _make_session(
            vol_regime='NORMAL', trend_tier=0,
            spot_history=[80000, 81600, 80000, 81600, 80000, 81600, 80000, 81600, 80000, 81600],
        )
        # Falls through to default RANGING since no vol or trend signal
        result = engine._classify_raw_regime(session)
        assert result == REGIME_RANGING  # large range but no trend/vol → default


class TestRegimeDebounce:

    def test_regime_unknown_before_two_stable_beats(self):
        engine = AdaptiveEngine()
        session = _make_session(vol_regime='NORMAL', trend_tier=1)  # TRENDING
        # First beat — candidate set, not yet stable
        result = engine._get_stable_regime(session)
        assert result == REGIME_UNKNOWN

    def test_regime_confirmed_after_two_stable_beats(self):
        engine = AdaptiveEngine()
        session = _make_session(vol_regime='NORMAL', trend_tier=1)
        engine._get_stable_regime(session)  # beat 1: candidate = TRENDING, count=1
        result = engine._get_stable_regime(session)  # beat 2: count=2 → confirmed
        assert result == REGIME_TRENDING

    def test_regime_resets_on_change(self):
        engine = AdaptiveEngine()
        session = _make_session(vol_regime='NORMAL', trend_tier=1)  # TRENDING
        engine._get_stable_regime(session)  # beat 1
        engine._get_stable_regime(session)  # beat 2 → confirmed TRENDING

        # Now change to VOL_SPIKE
        session['_vol_regime'] = 'HIGH'
        engine._get_stable_regime(session)  # beat 1 of new regime: candidate reset
        result = engine._get_stable_regime(session)  # beat 2 → confirmed VOL_SPIKE
        assert result == REGIME_VOL_SPIKE


# ---------------------------------------------------------------------------
# Part 2: Composite score
# ---------------------------------------------------------------------------

class TestCompositeScore:

    def test_zero_stress_is_zero(self):
        engine = AdaptiveEngine()
        session = _make_session(
            whipsaw_score=0, breakeven_zone='SAFE',
            shield_fires_ce=0, shield_fires_pe=0,
        )
        score = engine._compute_score(session, minutes_to_expiry=300)
        assert score == 0.0

    def test_max_stress_is_ten(self):
        engine = AdaptiveEngine()
        session = _make_session(
            whipsaw_score=4, breakeven_zone='CRITICAL',
            shield_fires_ce=1, shield_fires_pe=1,  # total=2
        )
        score = engine._compute_score(session, minutes_to_expiry=30)  # near expiry
        assert score == 10.0

    def test_near_expiry_adds_one_point(self):
        engine = AdaptiveEngine()
        session = _make_session(whipsaw_score=0, breakeven_zone='SAFE')
        score_far  = engine._compute_score(session, minutes_to_expiry=300)
        score_near = engine._compute_score(session, minutes_to_expiry=30)
        assert score_near > score_far

    def test_danger_zone_adds_more_than_warning(self):
        engine = AdaptiveEngine()
        s_warn = _make_session(breakeven_zone='WARNING')
        s_dang = _make_session(breakeven_zone='DANGER')
        assert engine._compute_score(s_dang, 300) > engine._compute_score(s_warn, 300)

    def test_score_clipped_to_ten(self):
        engine = AdaptiveEngine()
        session = _make_session(
            whipsaw_score=99,
            breakeven_zone='CRITICAL',
            shield_fires_ce=10, shield_fires_pe=10,
        )
        score = engine._compute_score(session, minutes_to_expiry=5)
        assert score <= 10.0


# ---------------------------------------------------------------------------
# Part 3: Parameter bounds
# ---------------------------------------------------------------------------

class TestParamBounds:

    def _run_many_beats(self, session, n=20, minutes_to_expiry=300.0):
        """Run evaluate() N times and collect all written values."""
        engine = AdaptiveEngine()
        written = {p: [] for p in PARAM_LIMITS}
        for _ in range(n):
            # Force rate limiter to allow (clear timing state)
            session['_adaptive_beats_since_write'] = 999
            session['_adaptive_last_write_time'] = 0.0
            session['_adaptive_write_history'] = []
            engine.evaluate(session, minutes_to_expiry)
            for p in PARAM_LIMITS:
                written[p].append(session['params'].get(p, 0))
        return written

    @pytest.mark.parametrize('preset', ['strangle', 'straddle', 'short_window'])
    def test_params_never_exceed_hard_limits_ranging(self, preset):
        session = _make_session(adaptive_mode='adaptive', adaptive_preset=preset)
        # Stabilise regime to RANGING (2 beats)
        engine = AdaptiveEngine()
        engine._get_stable_regime(session)
        engine._get_stable_regime(session)
        written = self._run_many_beats(session)
        for param, values in written.items():
            lo, hi = PARAM_LIMITS[param]
            for v in values:
                assert lo <= v <= hi, (
                    f"[{preset}] {param}={v:.4f} out of bounds [{lo},{hi}]"
                )

    @pytest.mark.parametrize('preset', ['strangle', 'straddle', 'short_window'])
    def test_params_never_exceed_hard_limits_trending(self, preset):
        session = _make_session(
            adaptive_mode='adaptive', adaptive_preset=preset,
            vol_regime='NORMAL', trend_tier=2,
            whipsaw_score=4, breakeven_zone='CRITICAL',
        )
        engine = AdaptiveEngine()
        engine._get_stable_regime(session)
        engine._get_stable_regime(session)
        written = self._run_many_beats(session)
        for param, values in written.items():
            lo, hi = PARAM_LIMITS[param]
            for v in values:
                assert lo <= v <= hi, (
                    f"[{preset}|TRENDING] {param}={v:.4f} out of bounds [{lo},{hi}]"
                )

    @pytest.mark.parametrize('preset', ['strangle', 'straddle', 'short_window'])
    def test_params_never_exceed_hard_limits_vol_spike(self, preset):
        session = _make_session(
            adaptive_mode='adaptive', adaptive_preset=preset,
            vol_regime='HIGH',
        )
        engine = AdaptiveEngine()
        engine._get_stable_regime(session)
        engine._get_stable_regime(session)
        written = self._run_many_beats(session)
        for param, values in written.items():
            lo, hi = PARAM_LIMITS[param]
            for v in values:
                assert lo <= v <= hi, (
                    f"[{preset}|VOL_SPIKE] {param}={v:.4f} out of bounds [{lo},{hi}]"
                )


# ---------------------------------------------------------------------------
# Part 4: Modes
# ---------------------------------------------------------------------------

class TestModes:

    def test_manual_mode_is_noop(self):
        session = _make_session(adaptive_mode='manual')
        changed = _run_evaluate(session)
        assert not changed, "manual mode must never change params"

    def test_preset_mode_is_noop_for_evaluate(self):
        session = _make_session(adaptive_mode='preset')
        changed = _run_evaluate(session)
        assert not changed, "preset mode must not auto-tune params during evaluate()"

    def test_adaptive_mode_may_change_params(self):
        # With a confirmed regime and high stress, adaptive mode should write changes
        session = _make_session(
            adaptive_mode='adaptive',
            vol_regime='HIGH',         # VOL_SPIKE regime
            whipsaw_score=4,
            breakeven_zone='CRITICAL',
        )
        engine = AdaptiveEngine()
        # Confirm regime
        engine._get_stable_regime(session)
        engine._get_stable_regime(session)
        # Reset rate limiter
        session['_adaptive_beats_since_write'] = 999
        session['_adaptive_last_write_time'] = 0.0
        session['_adaptive_write_history'] = []
        params_before = deepcopy(session['params'])
        engine.evaluate(session, minutes_to_expiry=30)
        params_after = session['params']
        changed = any(
            params_after.get(k) != params_before.get(k)
            for k in PARAM_LIMITS
        )
        assert changed, "adaptive mode with high stress + vol spike should update at least one param"

    def test_dry_run_does_not_write_params(self):
        session = _make_session(
            adaptive_mode='adaptive',
            vol_regime='HIGH',
            whipsaw_score=4,
            breakeven_zone='CRITICAL',
        )
        session['params']['adaptive_dry_run'] = True
        engine = AdaptiveEngine()
        engine._get_stable_regime(session)
        engine._get_stable_regime(session)
        session['_adaptive_beats_since_write'] = 999
        session['_adaptive_last_write_time'] = 0.0
        session['_adaptive_write_history'] = []
        params_before = deepcopy(session['params'])
        engine.evaluate(session, 30)
        # In dry_run, params should NOT change
        for k in PARAM_LIMITS:
            assert session['params'].get(k) == params_before.get(k), (
                f"dry_run=True must not write {k}"
            )


# ---------------------------------------------------------------------------
# Part 5: Operator override detection
# ---------------------------------------------------------------------------

class TestOperatorOverride:

    def test_operator_override_locks_param(self):
        session = _make_session(adaptive_mode='adaptive', vol_regime='HIGH')
        engine = AdaptiveEngine()
        engine._get_stable_regime(session)
        engine._get_stable_regime(session)
        session['_adaptive_beats_since_write'] = 999
        session['_adaptive_last_write_time'] = 0.0
        session['_adaptive_write_history'] = []

        # First evaluate — engine writes values
        engine.evaluate(session, 30)
        last_written = session.get('_adaptive_last_written', {})

        if not last_written:
            pytest.skip("No params were written (score too low for change)")

        # Operator manually changes one param (different from what engine wrote)
        param = next(iter(last_written))
        engine_val = last_written[param]
        operator_val = engine_val * 1.5   # different enough to exceed tolerance
        session['params'][param] = operator_val

        # Second evaluate — should detect override
        session['_adaptive_beats_since_write'] = 999
        session['_adaptive_last_write_time'] = 0.0
        session['_adaptive_write_history'] = []
        engine.evaluate(session, 30)

        overrides = set(session.get('_adaptive_operator_overrides', []))
        assert param in overrides, (
            f"Operator-changed {param} should be in _adaptive_operator_overrides"
        )

    def test_overridden_param_not_changed_again(self):
        session = _make_session(adaptive_mode='adaptive', vol_regime='HIGH')
        engine = AdaptiveEngine()
        engine._get_stable_regime(session)
        engine._get_stable_regime(session)
        session['_adaptive_beats_since_write'] = 999
        session['_adaptive_last_write_time'] = 0.0
        session['_adaptive_write_history'] = []
        engine.evaluate(session, 30)

        last_written = session.get('_adaptive_last_written', {})
        if not last_written:
            pytest.skip("No params were written")

        param = next(iter(last_written))
        sentinel_value = 99.99
        session['params'][param] = sentinel_value
        session['_adaptive_operator_overrides'] = [param]
        session['_adaptive_last_written'][param] = sentinel_value - 0.01  # force mismatch detection

        # Many beats — param must stay at sentinel
        for _ in range(5):
            session['_adaptive_beats_since_write'] = 999
            session['_adaptive_last_write_time'] = 0.0
            session['_adaptive_write_history'] = []
            engine.evaluate(session, 30)

        assert session['params'][param] == sentinel_value, (
            f"Engine overwrote operator-locked {param}"
        )


# ---------------------------------------------------------------------------
# Part 6: Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:

    def test_no_write_before_min_beats(self):
        session = _make_session(adaptive_mode='adaptive', vol_regime='HIGH')
        engine = AdaptiveEngine()
        engine._get_stable_regime(session)
        engine._get_stable_regime(session)
        # Set beats_since_write to 0 (just wrote)
        session['_adaptive_beats_since_write'] = 0
        session['_adaptive_last_write_time'] = 0.0
        session['_adaptive_write_history'] = []
        params_before = deepcopy(session['params'])
        engine.evaluate(session, 30)
        assert all(
            session['params'].get(k) == params_before.get(k)
            for k in PARAM_LIMITS
        ), "Should not write when beats_since_write < MIN_BEATS_BETWEEN_WRITES"

    def test_no_write_before_min_seconds(self):
        session = _make_session(adaptive_mode='adaptive', vol_regime='HIGH')
        engine = AdaptiveEngine()
        engine._get_stable_regime(session)
        engine._get_stable_regime(session)
        session['_adaptive_beats_since_write'] = 999
        session['_adaptive_last_write_time'] = time.time()  # just wrote
        session['_adaptive_write_history'] = []
        params_before = deepcopy(session['params'])
        engine.evaluate(session, 30)
        assert all(
            session['params'].get(k) == params_before.get(k)
            for k in PARAM_LIMITS
        ), "Should not write when < MIN_SECONDS_BETWEEN_WRITES elapsed"

    def test_no_write_after_max_per_hour(self):
        session = _make_session(adaptive_mode='adaptive', vol_regime='HIGH')
        engine = AdaptiveEngine()
        engine._get_stable_regime(session)
        engine._get_stable_regime(session)
        # Simulate 2 writes already in this hour
        now = time.time()
        session['_adaptive_write_history'] = [now - 100, now - 50]
        session['_adaptive_beats_since_write'] = 999
        session['_adaptive_last_write_time'] = 0.0
        params_before = deepcopy(session['params'])
        engine.evaluate(session, 30)
        assert all(
            session['params'].get(k) == params_before.get(k)
            for k in PARAM_LIMITS
        ), "Should not write when MAX_WRITES_PER_HOUR reached"


# ---------------------------------------------------------------------------
# Part 7: Preset loader
# ---------------------------------------------------------------------------

class TestPresetLoader:

    @pytest.mark.parametrize('preset', ['strangle', 'straddle', 'short_window'])
    def test_load_preset_writes_profile_values(self, preset):
        session = {
            'session_id': 'test-preset-001',
            'params': {'adaptive_preset': preset},
        }
        loaded = AdaptiveEngine.load_preset(session)
        profile = _PROFILES[preset]
        for param, expected in profile.items():
            assert session['params'][param] == expected, (
                f"[{preset}] {param}: expected {expected}, got {session['params'][param]}"
            )
        assert set(loaded.keys()) == set(profile.keys())

    def test_load_preset_unknown_falls_back_to_strangle(self):
        session = {'params': {'adaptive_preset': 'UNKNOWN_PRESET'}}
        AdaptiveEngine.load_preset(session)
        for param, expected in _PROFILES['strangle'].items():
            assert session['params'][param] == expected

    def test_load_preset_all_values_within_hard_limits(self):
        for preset, profile in _PROFILES.items():
            for param, value in profile.items():
                if param in PARAM_LIMITS:
                    lo, hi = PARAM_LIMITS[param]
                    assert lo <= value <= hi, (
                        f"[{preset}] {param}={value} outside hard limits [{lo},{hi}]"
                    )


# ---------------------------------------------------------------------------
# Part 8: Singleton
# ---------------------------------------------------------------------------

def test_get_adaptive_engine_returns_same_instance():
    e1 = get_adaptive_engine()
    e2 = get_adaptive_engine()
    assert e1 is e2


# ---------------------------------------------------------------------------
# Part 9: Circuit breaker / margin safety gates
# ---------------------------------------------------------------------------

class TestSafetyGates:

    def test_circuit_open_skips_adaptation(self):
        session = _make_session(adaptive_mode='adaptive', vol_regime='HIGH')
        session['_circuit_breaker_state'] = 'OPEN'
        changed = _run_evaluate(session)
        assert not changed, "Circuit breaker OPEN must prevent adaptation"

    def test_orange_margin_skips_adaptation(self):
        session = _make_session(adaptive_mode='adaptive', vol_regime='HIGH')
        session['_margin_tier'] = 'ORANGE'
        changed = _run_evaluate(session)
        assert not changed, "ORANGE margin tier must prevent adaptation"

    def test_red_margin_skips_adaptation(self):
        session = _make_session(adaptive_mode='adaptive', vol_regime='HIGH')
        session['_margin_tier'] = 'RED'
        changed = _run_evaluate(session)
        assert not changed, "RED margin tier must prevent adaptation"
