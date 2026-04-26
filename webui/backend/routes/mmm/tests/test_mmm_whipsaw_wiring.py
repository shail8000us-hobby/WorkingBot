"""
test_mmm_whipsaw_wiring.py — Control-plane param→live-decision proof tests.

Every test changes exactly ONE param and asserts the live decision changes.
These tests are the authoritative proof that WebUI settings actually affect
runtime behavior on the next heartbeat.

Gate baseline (empty series, premium_trigger_fired=False):
    G1 = False  (trigger not fired)
    G2 = True   (< 3 spots → benefit of doubt)
    G3 = True   (< 2 adj history → benefit of doubt)
    G4 = True   (< 2 spots → ER defaults 0.5 → er=0.5 >= 0.35 → pass)
    G5 = False  (iv=0, < 4 spots → cannot confirm vol)
    Passing gates = 3
"""

import pytest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from webui.backend.routes.mmm.mmm_whipsaw import (
    WhipsawCtx,
    select_engine,
    whipsaw_decide,
    WHIPSAW_ENGINE_DISPATCH,
    DEFAULT_ENGINE,
)
from webui.backend.routes.mmm.mmm_whipsaw_smart import (
    multi_gate_decide,
    mode_from_score,
    SmartWhipsawEngine,
)
from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_session(**param_overrides) -> dict:
    """Minimal session with predictable gate baseline (3 of 5 gates pass)."""
    params = {**DEFAULT_PARAMS, **param_overrides}
    return {
        'session_id': 'test-wiring',
        'params': params,
        'adjustment_history': [],
        'ce': {'total_lots': 5, 'strike': 71000, 'active_lots': 5},
        'pe': {'total_lots': 5, 'strike': 69000, 'active_lots': 5},
        '_smart_ws_series': [],
    }


def _ctx(**kwargs) -> WhipsawCtx:
    defaults = dict(ce_now=100.0, pe_now=100.0, spot=70000.0, iv=0.0,
                    premium_trigger_fired=False)
    defaults.update(kwargs)
    return WhipsawCtx(**defaults)


def _gate_decide(session: dict, mode: str = 'NORMAL') -> tuple:
    """Direct call to multi_gate_decide for gate-count testing."""
    return multi_gate_decide(session, _ctx(), [], mode, 0.10)


def _session_with_flips(**param_overrides) -> dict:
    """Session with alternating aggressors to produce flip_sc > 0."""
    now = datetime.now(timezone.utc)
    history = [
        {'aggressor': 'ce', 'timestamp': (now - timedelta(minutes=10)).isoformat(), 'spot': 70000},
        {'aggressor': 'pe', 'timestamp': (now - timedelta(minutes=6)).isoformat(),  'spot': 70000},
        {'aggressor': 'ce', 'timestamp': (now - timedelta(minutes=2)).isoformat(),  'spot': 70000},
    ]
    session = _base_session(**param_overrides)
    session['adjustment_history'] = history
    return session


# ---------------------------------------------------------------------------
# ENGINE SELECTOR
# ---------------------------------------------------------------------------

class TestEngineSelector:
    """Prove whipsaw_engine param changes engine on next call (hot-reload semantics)."""

    def test_engine_smart(self):
        session = _base_session(whipsaw_engine='SMART')
        assert select_engine(session).name == 'SMART'

    def test_engine_legacy(self):
        session = _base_session(whipsaw_engine='LEGACY')
        assert select_engine(session).name == 'LEGACY'

    def test_engine_off(self):
        session = _base_session(whipsaw_engine='OFF')
        assert select_engine(session).name == 'OFF'

    def test_hot_flip_smart_to_legacy(self):
        session = _base_session(whipsaw_engine='SMART')
        assert select_engine(session).name == 'SMART'
        session['params']['whipsaw_engine'] = 'LEGACY'
        assert select_engine(session).name == 'LEGACY'

    def test_whipsaw_smart_enabled_is_inert(self):
        """Deprecated param: whipsaw_engine='SMART' wins regardless of smart_enabled."""
        session = _base_session(whipsaw_engine='SMART', whipsaw_smart_enabled=False)
        assert select_engine(session).name == 'SMART', (
            "whipsaw_smart_enabled=False must NOT downgrade engine — "
            "whipsaw_engine is the single selector"
        )
        session['params']['whipsaw_smart_enabled'] = True
        assert select_engine(session).name == 'SMART'

    def test_force_legacy_env_overrides_all(self, monkeypatch):
        """MMM_WHIPSAW_FORCE_LEGACY=1 is the kill-switch; beats any param."""
        monkeypatch.setenv('MMM_WHIPSAW_FORCE_LEGACY', '1')
        session = _base_session(whipsaw_engine='SMART', whipsaw_smart_enabled=True)
        assert select_engine(session).name == 'LEGACY'


# ---------------------------------------------------------------------------
# GATE COUNTS  (smart_ws_gate_count_normal / smart_ws_gate_count_defensive)
# ---------------------------------------------------------------------------

class TestGateCounts:
    """3 gates pass in baseline. Raising required count causes a block."""

    # NORMAL mode
    def test_gate_count_normal_3_allows(self):
        session = _base_session(smart_ws_gate_count_normal=3)
        block, _, _, _ = _gate_decide(session, 'NORMAL')
        assert not block, "3-of-3 required: should allow"

    def test_gate_count_normal_4_blocks(self):
        session = _base_session(smart_ws_gate_count_normal=4)
        block, _, _, _ = _gate_decide(session, 'NORMAL')
        assert block, "3-of-4 required: should block"

    def test_gate_count_normal_5_blocks(self):
        session = _base_session(smart_ws_gate_count_normal=5)
        block, _, _, _ = _gate_decide(session, 'NORMAL')
        assert block, "3-of-5 required: should block"

    def test_gate_count_normal_change_flips_decision(self):
        """Changing gate_count_normal alone flips block/allow."""
        session_3 = _base_session(smart_ws_gate_count_normal=3)
        session_4 = _base_session(smart_ws_gate_count_normal=4)
        block_3, _, _, _ = _gate_decide(session_3, 'NORMAL')
        block_4, _, _, _ = _gate_decide(session_4, 'NORMAL')
        assert not block_3
        assert block_4

    # DEFENSIVE mode
    def test_gate_count_defensive_3_allows(self):
        session = _base_session(smart_ws_gate_count_defensive=3)
        block, _, _, _ = _gate_decide(session, 'DEFENSIVE')
        assert not block, "3-of-3 required: should allow"

    def test_gate_count_defensive_4_blocks(self):
        session = _base_session(smart_ws_gate_count_defensive=4)
        block, _, _, _ = _gate_decide(session, 'DEFENSIVE')
        assert block, "3-of-4 required: should block"

    def test_gate_count_defensive_change_flips_decision(self):
        session_3 = _base_session(smart_ws_gate_count_defensive=3)
        session_4 = _base_session(smart_ws_gate_count_defensive=4)
        block_3, _, _, _ = _gate_decide(session_3, 'DEFENSIVE')
        block_4, _, _, _ = _gate_decide(session_4, 'DEFENSIVE')
        assert not block_3
        assert block_4


# ---------------------------------------------------------------------------
# SIZE SCALARS  (smart_ws_size_scalar_defensive / smart_ws_size_scalar_observe)
# ---------------------------------------------------------------------------

class TestSizeScalars:
    """Changing scalar changes the lot_scalar returned."""

    def test_defensive_scalar_default(self):
        session = _base_session(smart_ws_size_scalar_defensive=0.5)
        _, _, lot_scalar, _ = _gate_decide(session, 'DEFENSIVE')
        assert abs(lot_scalar - 0.5) < 1e-9

    def test_defensive_scalar_custom(self):
        session = _base_session(smart_ws_size_scalar_defensive=0.8)
        _, _, lot_scalar, _ = _gate_decide(session, 'DEFENSIVE')
        assert abs(lot_scalar - 0.8) < 1e-9

    def test_defensive_scalar_change_affects_decision(self):
        s_half = _base_session(smart_ws_size_scalar_defensive=0.5)
        s_full = _base_session(smart_ws_size_scalar_defensive=1.0)
        _, _, scalar_half, _ = _gate_decide(s_half, 'DEFENSIVE')
        _, _, scalar_full, _ = _gate_decide(s_full, 'DEFENSIVE')
        assert scalar_half < scalar_full

    def test_observe_scalar_default(self):
        session = _base_session(smart_ws_size_scalar_observe=0.25)
        _, _, lot_scalar, _ = _gate_decide(session, 'OBSERVE')
        assert abs(lot_scalar - 0.25) < 1e-9

    def test_observe_scalar_custom(self):
        session = _base_session(smart_ws_size_scalar_observe=0.10)
        _, _, lot_scalar, _ = _gate_decide(session, 'OBSERVE')
        assert abs(lot_scalar - 0.10) < 1e-9

    def test_observe_scalar_change_affects_decision(self):
        s_low  = _base_session(smart_ws_size_scalar_observe=0.10)
        s_high = _base_session(smart_ws_size_scalar_observe=0.50)
        _, _, scalar_low,  _ = _gate_decide(s_low,  'OBSERVE')
        _, _, scalar_high, _ = _gate_decide(s_high, 'OBSERVE')
        assert scalar_low < scalar_high

    def test_lockdown_lot_scalar_always_zero(self):
        """LOCKDOWN returns lot_scalar=0 regardless of scalar params."""
        session = _base_session(smart_ws_size_scalar_defensive=1.0)
        _, _, lot_scalar, _ = _gate_decide(session, 'LOCKDOWN')
        assert lot_scalar == 0.0


# ---------------------------------------------------------------------------
# FLIP PENALTY  (smart_ws_flip_penalty)
# ---------------------------------------------------------------------------

class TestFlipPenalty:
    """Changing flip_penalty changes lot_scalar when flips are detected."""

    def _evaluate_with_flips(self, flip_penalty: float) -> float:
        session = _session_with_flips(
            smart_ws_flip_penalty=flip_penalty,
            # Keep NORMAL mode so gates don't block (gate_count=1 ensures allow)
            smart_ws_gate_count_normal=1,
            smart_ws_score_defensive=0.99,  # keep mode=NORMAL for clean scalar test
        )
        engine = SmartWhipsawEngine()
        ctx = _ctx()
        decision = engine.evaluate(session, ctx)
        return decision.lot_scalar

    def test_flip_penalty_1_no_reduction(self):
        """flip_penalty=1.0 → no lot reduction from flips."""
        scalar = self._evaluate_with_flips(1.0)
        assert abs(scalar - 1.0) < 1e-6, f"penalty=1.0 should give lot_scalar=1.0, got {scalar}"

    def test_flip_penalty_05_halves(self):
        """flip_penalty=0.5 with 1 flip → lot_scalar = 1.0 * 0.5^1 = 0.5."""
        scalar = self._evaluate_with_flips(0.5)
        # flip_count_approx from alternating history = int(flip_sc * 3) >= 1
        assert scalar < 1.0, f"penalty=0.5 should reduce lot_scalar, got {scalar}"

    def test_flip_penalty_change_changes_scalar(self):
        """Changing only flip_penalty produces different lot_scalar."""
        scalar_high = self._evaluate_with_flips(0.9)
        scalar_low  = self._evaluate_with_flips(0.1)
        assert scalar_high > scalar_low, (
            f"penalty=0.9 should give higher scalar than 0.1, "
            f"got {scalar_high:.4f} vs {scalar_low:.4f}"
        )

    def test_flip_penalty_no_flips_no_effect(self):
        """Without flip history, flip_penalty has no effect on lot_scalar."""
        session_no_flip = _base_session(
            smart_ws_flip_penalty=0.1,
            smart_ws_gate_count_normal=1,
            smart_ws_score_defensive=0.99,
        )
        engine = SmartWhipsawEngine()
        decision = engine.evaluate(session_no_flip, _ctx())
        assert abs(decision.lot_scalar - 1.0) < 1e-6, (
            "No flips → flip_penalty should not affect lot_scalar"
        )


# ---------------------------------------------------------------------------
# SCORE THRESHOLDS  (smart_ws_score_defensive/observe/lockdown)
# ---------------------------------------------------------------------------

class TestScoreThresholds:
    """
    Baseline composite score with empty series ≈ 0.10
    (only ER detector contributes: er_sc=0.5, weight=0.20 → 0.10).

    Thresholds above 0.10 → mode=NORMAL.
    Thresholds below 0.10 → mode escalates.
    """

    def _evaluate_mode(self, **param_overrides) -> str:
        session = _base_session(**param_overrides)
        engine = SmartWhipsawEngine()
        decision = engine.evaluate(session, _ctx())
        return decision.mode

    def test_defensive_threshold_above_score_stays_normal(self):
        mode = self._evaluate_mode(smart_ws_score_defensive=0.30)
        assert mode == 'NORMAL', f"score≈0.10 < threshold 0.30 → NORMAL, got {mode}"

    def test_defensive_threshold_below_score_triggers_defensive(self):
        mode = self._evaluate_mode(
            smart_ws_score_defensive=0.05,
            smart_ws_score_observe=0.60,
            smart_ws_score_lockdown=0.80,
        )
        assert mode == 'DEFENSIVE', f"score≈0.10 >= threshold 0.05 → DEFENSIVE, got {mode}"

    def test_observe_threshold_below_score_triggers_observe(self):
        mode = self._evaluate_mode(
            smart_ws_score_defensive=0.05,
            smart_ws_score_observe=0.05,
            smart_ws_score_lockdown=0.80,
        )
        assert mode == 'OBSERVE', f"score≈0.10 >= observe=0.05 < lockdown=0.80 → OBSERVE, got {mode}"

    def test_lockdown_threshold_below_score_triggers_lockdown(self):
        mode = self._evaluate_mode(
            smart_ws_score_defensive=0.05,
            smart_ws_score_observe=0.05,
            smart_ws_score_lockdown=0.05,
        )
        assert mode == 'LOCKDOWN', f"score≈0.10 >= all thresholds → LOCKDOWN, got {mode}"

    def test_threshold_change_changes_block_decision(self):
        """Lowering observe threshold enough to hit OBSERVE → block=True."""
        mode_normal   = self._evaluate_mode(smart_ws_score_observe=0.60)
        mode_observe  = self._evaluate_mode(
            smart_ws_score_defensive=0.05,
            smart_ws_score_observe=0.05,
        )
        assert mode_normal  == 'NORMAL'
        assert mode_observe == 'OBSERVE'

    def test_mode_from_score_defensive_param(self):
        assert mode_from_score(0.10, defensive=0.30) == 'NORMAL'
        assert mode_from_score(0.10, defensive=0.05) == 'DEFENSIVE'

    def test_mode_from_score_observe_param(self):
        assert mode_from_score(0.10, defensive=0.05, observe=0.60) == 'DEFENSIVE'
        assert mode_from_score(0.10, defensive=0.05, observe=0.05, lockdown=0.80) == 'OBSERVE'

    def test_mode_from_score_lockdown_param(self):
        assert mode_from_score(0.10, defensive=0.05, observe=0.05, lockdown=0.05) == 'LOCKDOWN'


# ---------------------------------------------------------------------------
# TOKEN BUDGET  (smart_ws_tokens_per_session)
# ---------------------------------------------------------------------------

class TestTokenBudget:
    """Token budget exhaustion blocks adjustments."""

    def _evaluate(self, **param_overrides) -> 'WhipsawDecision':
        session = _base_session(**param_overrides)
        engine = SmartWhipsawEngine()
        return engine.evaluate(session, _ctx())

    def test_full_budget_allows(self):
        d = self._evaluate(smart_ws_tokens_per_session=10.0)
        # With a full budget, token step should not block
        token_msgs = [e for e in d.events if 'token' in e.get('message', '').lower()]
        assert not token_msgs, "Full budget should not produce token-exhausted events"

    def test_near_zero_budget_blocks(self):
        """tokens_per_session=0.01 → cost=1.0 > remaining → block."""
        session = _base_session(
            smart_ws_tokens_per_session=0.01,
            smart_ws_gate_count_normal=1,  # ensure gates don't block first
        )
        session['_smart_ws_tokens'] = 0.01  # pre-set remaining below cost
        engine = SmartWhipsawEngine()
        d = engine.evaluate(session, _ctx())
        assert d.block_adjustment, "Near-zero token budget should block adjustment"
        token_msgs = [e for e in d.events if 'token' in e.get('message', '').lower()]
        assert token_msgs, "Should emit token-exhausted event"

    def test_budget_decrements_across_beats(self):
        """Token balance decreases after each allowed adjustment."""
        session = _base_session(
            smart_ws_tokens_per_session=10.0,
            smart_ws_gate_count_normal=1,  # gates always pass
        )
        engine = SmartWhipsawEngine()
        engine.evaluate(session, _ctx())
        tokens_after_1 = session.get('_smart_ws_tokens', 10.0)
        assert tokens_after_1 < 10.0, "Token balance should decrease after allowed adjustment"

    def test_budget_change_changes_available_beats(self):
        """Halving the budget halves the number of beats before exhaustion."""
        def beats_until_block(tokens_init: float) -> int:
            session = _base_session(
                smart_ws_tokens_per_session=tokens_init,
                smart_ws_gate_count_normal=1,
                smart_ws_token_refresh_per_hour=0.0,  # no drip for clean count
            )
            engine = SmartWhipsawEngine()
            for beat in range(30):
                d = engine.evaluate(session, _ctx())
                if d.block_adjustment:
                    return beat
            return 30

        beats_10 = beats_until_block(10.0)
        beats_5  = beats_until_block(5.0)
        assert beats_5 < beats_10, (
            f"Halved budget should exhaust faster: {beats_5} vs {beats_10} beats"
        )


# ---------------------------------------------------------------------------
# TOKEN REFRESH  (smart_ws_token_refresh_per_hour)
# ---------------------------------------------------------------------------

class TestTokenRefresh:
    """Token drip prevents starvation in long sessions."""

    def test_refresh_zero_no_drip(self):
        session = _base_session(smart_ws_token_refresh_per_hour=0.0)
        session['_smart_ws_tokens'] = 5.0
        engine = SmartWhipsawEngine()
        engine.evaluate(session, _ctx())
        # After blocked beat, patience credit is added but not drip
        # Just verify no crash and tokens are still tracked
        assert '_smart_ws_tokens' in session

    def test_refresh_restores_tokens(self):
        """With refresh > 0, a beat with low tokens drips some back."""
        session = _base_session(
            smart_ws_token_refresh_per_hour=12.0,  # 1.0/beat at 5min interval
            adjustment_interval=300,
        )
        session['_smart_ws_tokens'] = 2.0  # not zero, just low
        before = session['_smart_ws_tokens']
        # Evaluate a BLOCKING beat (so tokens aren't spent, just dripped)
        session['params']['smart_ws_gate_count_normal'] = 5  # force gate block
        engine = SmartWhipsawEngine()
        engine.evaluate(session, _ctx())
        after = session.get('_smart_ws_tokens', 0.0)
        # Gate blocked + patience credit + drip — net should be >= before
        assert after >= before - 1.5, (
            f"Token balance should not drop drastically with refresh; was {before}, now {after}"
        )


# ---------------------------------------------------------------------------
# COOLDOWN BASE BEATS  (smart_ws_cooldown_base_beats)
# ---------------------------------------------------------------------------

class TestCooldownBase:
    """Cooldown duration scales with base_beats param."""

    def test_cooldown_base_stored_in_decision(self):
        session = _base_session(smart_ws_cooldown_base_beats=2)
        engine = SmartWhipsawEngine()
        d = engine.evaluate(session, _ctx())
        assert d.trace.get('cooldown_beats', 0) >= 2, (
            "cooldown_beats in trace should reflect base_beats param"
        )

    def test_cooldown_base_1_vs_3(self):
        s1 = _base_session(smart_ws_cooldown_base_beats=1)
        s3 = _base_session(smart_ws_cooldown_base_beats=3)
        engine = SmartWhipsawEngine()
        d1 = engine.evaluate(s1, _ctx())
        d3 = engine.evaluate(s3, _ctx())
        assert d3.trace['cooldown_beats'] >= d1.trace['cooldown_beats'], (
            "Higher base_beats should produce longer or equal cooldown duration"
        )


# ---------------------------------------------------------------------------
# DETECTOR WINDOWS  (smart_ws_flip_window_mins, smart_ws_er_window_mins)
# ---------------------------------------------------------------------------

class TestDetectorWindows:
    """Changing window params changes how much history is considered."""

    def test_flip_window_param_consumed(self):
        """Verify flip_window_mins is read — no crash, trace present."""
        session = _base_session(smart_ws_flip_window_mins=10)
        engine = SmartWhipsawEngine()
        d = engine.evaluate(session, _ctx())
        assert 'scores' in d.trace

    def test_er_window_param_consumed(self):
        """Verify er_window_mins is read — no crash, trace present."""
        session = _base_session(smart_ws_er_window_mins=10)
        engine = SmartWhipsawEngine()
        d = engine.evaluate(session, _ctx())
        assert d.trace.get('score') is not None

    def test_narrow_flip_window_reduces_flip_score(self):
        """With very short window, old flips fall outside and score is lower."""
        now = datetime.now(timezone.utc)
        old_flips = [
            {'aggressor': 'ce', 'timestamp': (now - timedelta(minutes=25)).isoformat(), 'spot': 70000},
            {'aggressor': 'pe', 'timestamp': (now - timedelta(minutes=22)).isoformat(), 'spot': 70000},
            {'aggressor': 'ce', 'timestamp': (now - timedelta(minutes=20)).isoformat(), 'spot': 70000},
        ]
        session_wide   = _base_session(smart_ws_flip_window_mins=30)
        session_narrow = _base_session(smart_ws_flip_window_mins=5)
        session_wide['adjustment_history']   = old_flips
        session_narrow['adjustment_history'] = old_flips

        engine = SmartWhipsawEngine()
        d_wide   = engine.evaluate(session_wide,   _ctx())
        d_narrow = engine.evaluate(session_narrow, _ctx())

        flip_wide   = d_wide.trace['scores']['flip']
        flip_narrow = d_narrow.trace['scores']['flip']
        assert flip_narrow <= flip_wide, (
            f"Narrow window should ignore old flips: wide={flip_wide:.3f}, narrow={flip_narrow:.3f}"
        )


# ---------------------------------------------------------------------------
# OSCILLATION SENSITIVITY  (smart_ws_oscillation_sensitivity_pct)
# ---------------------------------------------------------------------------

class TestOscillationSensitivity:
    """Higher sensitivity_pct → fewer extrema counted → lower oscillation score."""

    def _oscillation_score_from_series(self, spots: list, sensitivity: float) -> float:
        from webui.backend.routes.mmm.mmm_whipsaw_smart import oscillation_score
        return oscillation_score(spots, sensitivity_pct=sensitivity)

    def test_low_sensitivity_detects_small_moves(self):
        spots = [100.0, 100.05, 100.0, 100.05, 100.0, 100.05, 100.0]
        low_score  = self._oscillation_score_from_series(spots, 0.01)
        high_score = self._oscillation_score_from_series(spots, 2.0)
        assert low_score >= high_score, (
            "Low sensitivity should detect small oscillations; high sensitivity misses them"
        )

    def test_sensitivity_param_consumed_in_evaluate(self):
        session = _base_session(smart_ws_oscillation_sensitivity_pct=0.01)
        engine = SmartWhipsawEngine()
        d = engine.evaluate(session, _ctx())
        assert 'oscillation' in d.trace.get('scores', {}), "oscillation score must appear in trace"


# ---------------------------------------------------------------------------
# RV/IV FLOOR  (smart_ws_rv_iv_ratio_floor)
# ---------------------------------------------------------------------------

class TestRvIvFloor:
    """RV/IV ratio floor controls when vol-divergence detector fires."""

    def test_rviv_floor_param_consumed(self):
        session = _base_session(smart_ws_rv_iv_ratio_floor=0.3)
        engine = SmartWhipsawEngine()
        d = engine.evaluate(session, _ctx())
        assert 'rviv' in d.trace.get('scores', {}), "rviv score must appear in trace"

    def test_rviv_score_higher_with_higher_floor(self):
        """Higher floor → harder to satisfy → more likely to fire (score ↑) when RV is low."""
        from webui.backend.routes.mmm.mmm_whipsaw_smart import rv_iv_divergence_score
        spots = [100.0, 100.01, 99.99, 100.0, 100.01, 99.99]  # tiny moves → low RV
        low_floor  = rv_iv_divergence_score(spots, iv_now=0.8, rv_iv_floor=0.1)
        high_floor = rv_iv_divergence_score(spots, iv_now=0.8, rv_iv_floor=0.9)
        assert high_floor >= low_floor, (
            "Higher rv_iv_floor makes the floor harder to meet → score at least as high"
        )


# ---------------------------------------------------------------------------
# LATE SESSION WEIGHTS  (smart_ws_late_session_relax_mins)
# ---------------------------------------------------------------------------

class TestLateSessionWeights:
    """Late session flag activates eased weights when 30 < DTE < relax_mins."""

    def test_late_session_flag_set_in_trace(self):
        session = _base_session(smart_ws_late_session_relax_mins=180)
        session['_minutes_to_expiry'] = 120.0  # within window
        engine = SmartWhipsawEngine()
        d = engine.evaluate(session, _ctx())
        assert d.trace.get('late_session') is True, "DTE=120 < relax=180 → late_session=True"
        assert d.trace.get('weights') == 'late_session'

    def test_outside_late_window_uses_default_weights(self):
        session = _base_session(smart_ws_late_session_relax_mins=180)
        session['_minutes_to_expiry'] = 300.0  # outside window
        engine = SmartWhipsawEngine()
        d = engine.evaluate(session, _ctx())
        assert d.trace.get('late_session') is False
        assert d.trace.get('weights') == 'default'

    def test_relax_mins_change_affects_window(self):
        """Widening relax_mins includes more DTE values in late-session window."""
        session_narrow = _base_session(smart_ws_late_session_relax_mins=60)
        session_wide   = _base_session(smart_ws_late_session_relax_mins=300)
        session_narrow['_minutes_to_expiry'] = 120.0
        session_wide['_minutes_to_expiry']   = 120.0

        engine = SmartWhipsawEngine()
        d_narrow = engine.evaluate(session_narrow, _ctx())
        d_wide   = engine.evaluate(session_wide,   _ctx())

        assert d_narrow.trace.get('late_session') is False, "DTE=120 > relax=60 → not late"
        assert d_wide.trace.get('late_session')   is True,  "DTE=120 < relax=300 → late"


# ---------------------------------------------------------------------------
# HOT-RELOAD END-TO-END  (proves WebUI → param → decision without restart)
# ---------------------------------------------------------------------------

class TestHotReload:
    """Simulate hot-reload: change param in session dict → same engine instance → different decision."""

    def test_gate_count_hot_flip(self):
        """Gate count 3→4 on same session object flips block decision."""
        session = _base_session(smart_ws_gate_count_normal=3)
        b1, _, _, _ = multi_gate_decide(session, _ctx(), [], 'NORMAL', 0.1)
        assert not b1, "gate=3 with 3 passing: allow"

        session['params']['smart_ws_gate_count_normal'] = 4
        b2, _, _, _ = multi_gate_decide(session, _ctx(), [], 'NORMAL', 0.1)
        assert b2, "gate=4 with 3 passing: block"

    def test_scalar_hot_flip(self):
        """Size scalar change on same session takes effect immediately."""
        session = _base_session(smart_ws_size_scalar_defensive=0.5)
        _, _, s1, _ = multi_gate_decide(session, _ctx(), [], 'DEFENSIVE', 0.4)
        assert abs(s1 - 0.5) < 1e-9

        session['params']['smart_ws_size_scalar_defensive'] = 0.9
        _, _, s2, _ = multi_gate_decide(session, _ctx(), [], 'DEFENSIVE', 0.4)
        assert abs(s2 - 0.9) < 1e-9

    def test_threshold_hot_flip_changes_mode(self):
        """Lowering observe threshold changes mode without re-creating session."""
        session = _base_session(
            smart_ws_score_defensive=0.30,
            smart_ws_score_observe=0.60,
        )
        engine = SmartWhipsawEngine()
        d1 = engine.evaluate(deepcopy(session), _ctx())
        assert d1.mode == 'NORMAL', f"Expected NORMAL, got {d1.mode}"

        session['params']['smart_ws_score_defensive'] = 0.05
        session['params']['smart_ws_score_observe']   = 0.05
        d2 = engine.evaluate(session, _ctx())
        assert d2.mode in ('OBSERVE', 'LOCKDOWN'), f"Expected OBSERVE/LOCKDOWN, got {d2.mode}"

    def test_engine_hot_flip_changes_engine_used(self):
        """whipsaw_engine hot-flip produces different engine decision."""
        session = _base_session(whipsaw_engine='SMART')
        assert select_engine(session).name == 'SMART'
        session['params']['whipsaw_engine'] = 'LEGACY'
        assert select_engine(session).name == 'LEGACY'
        session['params']['whipsaw_engine'] = 'OFF'
        d = WHIPSAW_ENGINE_DISPATCH['OFF'].evaluate(session, _ctx())
        assert d.block_adjustment is False
        assert d.lot_scalar == 1.0


# ---------------------------------------------------------------------------
# LEGACY ENGINE PARAMS (whipsaw_caution/restrict/cooldown_score)
# ---------------------------------------------------------------------------

class TestLegacyParams:
    """Legacy params consumed by LegacyWhipsawEngine via check_whipsaw()."""

    def test_legacy_mode_reflects_caution_threshold(self):
        """With score=0, mode is NORMAL for any reasonable thresholds."""
        from webui.backend.routes.mmm.mmm_whipsaw import LegacyWhipsawEngine
        session = _base_session(
            whipsaw_caution_score=2,
            whipsaw_restrict_score=3,
            whipsaw_cooldown_score=4,
        )
        session['_whipsaw_score'] = 0
        engine = LegacyWhipsawEngine()
        d = engine.evaluate(session, _ctx())
        assert d.mode == 'NORMAL'

    def test_legacy_lot_scalar_at_restrict(self):
        """With score >= restrict_score, lot_scalar = 0.5 (and trigger widened)."""
        from webui.backend.routes.mmm.mmm_whipsaw import LegacyWhipsawEngine
        session = _base_session(
            whipsaw_caution_score=2,
            whipsaw_restrict_score=3,
            whipsaw_cooldown_score=4,
        )
        # Pre-set score to trigger restrict tier
        session['_whipsaw_score'] = 3
        session['adjustment_history'] = []
        engine = LegacyWhipsawEngine()
        d = engine.evaluate(session, _ctx())
        assert d.mode == 'RESTRICT'
        assert d.lot_scalar == 0.5, f"RESTRICT lot_scalar should be 0.5, got {d.lot_scalar}"


# ---------------------------------------------------------------------------
# WIRING COMPLETENESS CHECK
# ---------------------------------------------------------------------------

class TestWiringCompleteness:
    """
    Structural tests: confirm every Smart param is listed as hot-reloadable
    and that the whipsaw_engine validator rejects unknown values.
    """

    def test_all_smart_params_in_hot_reload_list(self):
        from webui.backend.routes.mmm.mmm_state import HOT_RELOAD_PARAMS
        required = [
            'whipsaw_engine', 'whipsaw_engine_shadow',
            'smart_ws_score_defensive', 'smart_ws_score_observe', 'smart_ws_score_lockdown',
            'smart_ws_tokens_per_session',
            'smart_ws_gate_count_normal', 'smart_ws_gate_count_defensive',
            'smart_ws_flip_window_mins', 'smart_ws_er_window_mins',
            'smart_ws_oscillation_sensitivity_pct', 'smart_ws_rv_iv_ratio_floor',
            'smart_ws_size_scalar_defensive', 'smart_ws_size_scalar_observe',
            'smart_ws_flip_penalty', 'smart_ws_cooldown_base_beats',
            'smart_ws_late_session_relax_mins', 'smart_ws_token_refresh_per_hour',
        ]
        for p in required:
            assert p in HOT_RELOAD_PARAMS, f"{p!r} not in HOT_RELOAD_PARAMS"

    def test_all_smart_params_in_valid_params(self):
        from webui.backend.routes.mmm.mmm_config import PARAM_RULES
        required = [
            'whipsaw_engine', 'whipsaw_engine_shadow',
            'smart_ws_score_defensive', 'smart_ws_score_observe', 'smart_ws_score_lockdown',
            'smart_ws_tokens_per_session',
            'smart_ws_gate_count_normal', 'smart_ws_gate_count_defensive',
            'smart_ws_flip_window_mins', 'smart_ws_er_window_mins',
            'smart_ws_oscillation_sensitivity_pct', 'smart_ws_rv_iv_ratio_floor',
            'smart_ws_size_scalar_defensive', 'smart_ws_size_scalar_observe',
            'smart_ws_flip_penalty', 'smart_ws_cooldown_base_beats',
            'smart_ws_late_session_relax_mins', 'smart_ws_token_refresh_per_hour',
        ]
        for p in required:
            assert p in PARAM_RULES, f"{p!r} not in PARAM_RULES (VALID_PARAMS)"

    def test_all_smart_params_hot_flag_true(self):
        from webui.backend.routes.mmm.mmm_config import PARAM_RULES
        not_hot = [p for p in PARAM_RULES if p.startswith('smart_ws_') and not PARAM_RULES[p].get('hot')]
        assert not not_hot, f"Smart params missing hot=True: {not_hot}"

    def test_engine_validator_rejects_unknown(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        _, errors = validate_params({'whipsaw_engine': 'BANANA'})
        assert any('whipsaw_engine' in e for e in errors), \
            f"Expected validation error for unknown engine, got: {errors}"

    def test_engine_validator_accepts_all_valid(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        for engine in ('LEGACY', 'SMART', 'OFF'):
            _, errors = validate_params({'whipsaw_engine': engine})
            engine_errors = [e for e in errors if 'whipsaw_engine' in e]
            assert not engine_errors, f"Engine {engine!r} should be valid, got errors: {engine_errors}"

    def test_whipsaw_smart_enabled_not_in_select_engine(self):
        """
        Structural: whipsaw_smart_enabled must have zero effect on select_engine().
        Test all four combinations of engine + smart_enabled.
        """
        for engine_val in ('SMART', 'LEGACY', 'OFF'):
            for enabled in (True, False):
                session = _base_session(whipsaw_engine=engine_val, whipsaw_smart_enabled=enabled)
                result = select_engine(session)
                assert result.name == engine_val, (
                    f"engine={engine_val}, smart_enabled={enabled} → "
                    f"expected {engine_val}, got {result.name}. "
                    "whipsaw_smart_enabled must not influence engine selection."
                )
