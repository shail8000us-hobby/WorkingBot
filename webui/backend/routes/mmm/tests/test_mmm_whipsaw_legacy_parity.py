"""
Phase 1 — Legacy Parity Tests for mmm_whipsaw.py

Verifies that the new dispatcher + LegacyWhipsawEngine produces
byte-identical session state and identical decisions to the prior
inline logic in mmm_monitor.py.

9 tests required by the Phase 1 plan:
  1. test_legacy_parity_empty_session
  2. test_legacy_parity_three_alternations_within_window
  3. test_legacy_parity_cooldown_skip
  4. test_legacy_parity_cooldown_expired
  5. test_legacy_parity_trigger_widen_at_caution_and_restrict
  6. test_legacy_parity_lot_reduction_at_restrict
  7. test_straddle_bypass
  8. test_env_kill_switch
  9. test_audit_log_field_unchanged
"""

import os
import pytest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from webui.backend.routes.mmm.mmm_whipsaw import (
    WhipsawCtx,
    WhipsawDecision,
    LegacyWhipsawEngine,
    NullWhipsawEngine,
    select_engine,
    whipsaw_decide,
    DEFAULT_ENGINE,
    WHIPSAW_ENGINE_DISPATCH,
)
from webui.backend.routes.mmm.mmm_safety import MMMSafety


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(**overrides):
    s = {
        'session_id': 'test-ws-001',
        'params': {
            'whipsaw_window_mins': 30,
            'whipsaw_spot_move_pct': 0.3,
            'whipsaw_caution_score': 2,
            'whipsaw_restrict_score': 3,
            'whipsaw_cooldown_score': 4,
            'adjustment_interval': 300,
            'min_trigger_move': 10.0,
            'strategy_type': 'MMM',
        },
        'adjustment_history': [],
    }
    s.update(overrides)
    return s


def _ctx():
    return WhipsawCtx(ce_now=100.0, pe_now=100.0, spot=70000.0)


def _alternating_history(n: int, within_mins: int = 5):
    """Build n alternating CE/PE adjustments all within `within_mins` minutes."""
    now = datetime.now(timezone.utc)
    history = []
    for i in range(n):
        ts = now - timedelta(minutes=within_mins - i * (within_mins / max(n, 1)))
        history.append({
            'aggressor': 'ce' if i % 2 == 0 else 'pe',
            'timestamp': ts.isoformat(),
            'spot': 70000.0,  # same spot → no validation pass-through
        })
    return history


# ---------------------------------------------------------------------------
# Test 1: empty session → no state writes, scalars 1.0
# ---------------------------------------------------------------------------

def test_legacy_parity_empty_session():
    session = _make_session()
    safety = MMMSafety()

    # Direct path
    s_direct = deepcopy(session)
    direct_events = safety.check_whipsaw(s_direct)

    # Dispatcher path
    s_disp = deepcopy(session)
    engine = LegacyWhipsawEngine()
    decision = engine.evaluate(s_disp, _ctx())

    # Session state must be identical
    for key in ('_whipsaw_score', '_whipsaw_state', '_whipsaw_skip_until',
                '_whipsaw_last_noise_at', '_whipsaw_last_checked_idx'):
        assert s_direct.get(key) == s_disp.get(key), f"Key {key} diverged"

    # Scalars no-op
    assert decision.trigger_widen_factor == 1.0
    assert decision.lot_scalar == 1.0
    assert decision.block_adjustment is False
    assert decision.engine == 'LEGACY'
    assert decision.mode == 'NORMAL'


# ---------------------------------------------------------------------------
# Test 2: 3 alternations within window → CAUTION / RESTRICT state parity
# ---------------------------------------------------------------------------

def test_legacy_parity_three_alternations_within_window():
    history = _alternating_history(4)  # 3 alternations from 4 records
    # Set _whipsaw_last_checked_idx=0 to simulate a running session
    # (BUG-C3 first-run sets it to len(history), skipping all past entries).
    session = _make_session(
        adjustment_history=history,
        _whipsaw_last_checked_idx=0,
    )
    safety = MMMSafety()

    s_direct = deepcopy(session)
    safety.check_whipsaw(s_direct)

    s_disp = deepcopy(session)
    engine = LegacyWhipsawEngine()
    decision = engine.evaluate(s_disp, _ctx())

    for key in ('_whipsaw_score', '_whipsaw_last_checked_idx'):
        assert s_direct.get(key) == s_disp.get(key), f"Key {key} diverged"
    # _whipsaw_last_noise_at is a 'now' timestamp; both paths set it,
    # so just assert it was set (not byte-identical — sub-second diff is ok).
    assert s_disp.get('_whipsaw_last_noise_at') is not None

    # Score should be 3 → RESTRICT
    assert s_disp.get('_whipsaw_score', 0) >= 3
    assert decision.mode in ('RESTRICT', 'COOLDOWN')
    assert decision.lot_scalar == 0.5


# ---------------------------------------------------------------------------
# Test 3: active COOLDOWN skip → block_adjustment True, events identical
# ---------------------------------------------------------------------------

def test_legacy_parity_cooldown_skip():
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    session = _make_session(
        _whipsaw_score=4,
        _whipsaw_skip_until=future,
    )
    safety = MMMSafety()

    s_direct = deepcopy(session)
    direct_events = safety.check_whipsaw(s_direct)

    s_disp = deepcopy(session)
    decision = LegacyWhipsawEngine().evaluate(s_disp, _ctx())

    assert decision.block_adjustment is True
    assert any(e.get('action') == 'stop_adjustments' for e in direct_events)
    assert s_direct.get('_whipsaw_skip_until') == s_disp.get('_whipsaw_skip_until')


# ---------------------------------------------------------------------------
# Test 4: expired COOLDOWN → score decays by 2, parity
# ---------------------------------------------------------------------------

def test_legacy_parity_cooldown_expired():
    past = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    session = _make_session(
        _whipsaw_score=4,
        _whipsaw_skip_until=past,
    )
    safety = MMMSafety()

    s_direct = deepcopy(session)
    safety.check_whipsaw(s_direct)

    s_disp = deepcopy(session)
    decision = LegacyWhipsawEngine().evaluate(s_disp, _ctx())

    # Score reduced by 2 on both paths
    assert s_direct.get('_whipsaw_score') == s_disp.get('_whipsaw_score')
    assert s_direct.get('_whipsaw_score') == 2
    assert decision.block_adjustment is False


# ---------------------------------------------------------------------------
# Test 5: trigger widen factors at CAUTION (1.5×) and RESTRICT (2.0×)
# ---------------------------------------------------------------------------

def test_legacy_parity_trigger_widen_at_caution_and_restrict():
    for score, expected_factor in [(2, 1.5), (3, 2.0)]:
        session = _make_session(_whipsaw_score=score)
        decision = LegacyWhipsawEngine().evaluate(session, _ctx())
        assert decision.trigger_widen_factor == expected_factor, (
            f"score={score} expected factor={expected_factor} got {decision.trigger_widen_factor}"
        )
        assert session.get('_whipsaw_trigger_widened') is None  # monitor sets this, not engine


# ---------------------------------------------------------------------------
# Test 6: lot reduction at RESTRICT → lot_scalar = 0.5
# ---------------------------------------------------------------------------

def test_legacy_parity_lot_reduction_at_restrict():
    session = _make_session(_whipsaw_score=3)
    decision = LegacyWhipsawEngine().evaluate(session, _ctx())

    assert decision.lot_scalar == 0.5
    # Application: 10 lots at RESTRICT
    lots = 10
    reduced = max(1, int(lots * decision.lot_scalar))
    assert reduced == 5


# ---------------------------------------------------------------------------
# Test 7: STRADDLE_WITH_ADJUSTMENT — both scalars remain 1.0 regardless of score
# ---------------------------------------------------------------------------

def test_straddle_bypass():
    session = _make_session(_whipsaw_score=10)
    session['params']['strategy_type'] = 'STRADDLE_WITH_ADJUSTMENT'

    decision = LegacyWhipsawEngine().evaluate(session, _ctx())

    assert decision.trigger_widen_factor == 1.0, (
        f"Expected no trigger widening for STRADDLE_WITH_ADJUSTMENT, got {decision.trigger_widen_factor}"
    )
    assert decision.lot_scalar == 1.0, (
        f"Expected no lot reduction for STRADDLE_WITH_ADJUSTMENT, got {decision.lot_scalar}"
    )


# ---------------------------------------------------------------------------
# Test 8: env kill-switch forces LEGACY even when engine param is overridden
# ---------------------------------------------------------------------------

def test_env_kill_switch(monkeypatch):
    session = _make_session()
    # Simulate a future where params contains a non-LEGACY engine
    session['params']['whipsaw_engine'] = 'OFF'

    monkeypatch.setenv('MMM_WHIPSAW_FORCE_LEGACY', '1')
    engine = select_engine(session)
    assert engine.name == 'LEGACY', (
        f"Kill-switch should force LEGACY, got {engine.name}"
    )

    monkeypatch.delenv('MMM_WHIPSAW_FORCE_LEGACY', raising=False)
    engine_off = select_engine(session)
    # Without kill-switch, OFF should resolve to NullWhipsawEngine
    # (OFF key not in dispatch yet in Phase 1 returns LEGACY as fallback)
    # OFF is in WHIPSAW_ENGINE_DISPATCH so it should return NullWhipsawEngine
    assert engine_off.name == 'OFF'


# ---------------------------------------------------------------------------
# Test 9: audit log field — check_whipsaw still writes _whipsaw_score to session
#         (the field mmm_audit_log.py reads as whipsaw_state)
# ---------------------------------------------------------------------------

def test_audit_log_field_unchanged():
    history = _alternating_history(4)
    session = _make_session(adjustment_history=history)

    LegacyWhipsawEngine().evaluate(session, _ctx())

    # After evaluate, session must carry the standard legacy keys that
    # mmm_audit_log.py reads: _whipsaw_state is set by check_whipsaw
    # indirectly via _whipsaw_score → mode derivation.
    # check_whipsaw itself doesn't write _whipsaw_state; the monitor's
    # banner reads _whipsaw_score and derives state — so verify _whipsaw_score.
    score = session.get('_whipsaw_score', 0)
    assert isinstance(score, int)
    assert score >= 0
