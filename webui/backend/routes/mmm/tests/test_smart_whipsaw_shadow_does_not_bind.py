"""
Phase 6 — regression guard: Smart is primary, guard removed, shadow is explicit-only.

Tests:
  1. engine=SMART (any smart_enabled value) → primary decision is SMART's
  2. _whipsaw_* keys written by LEGACY shadow (not SMART primary)
  3. _smart_ws_* keys written by SMART primary when it runs
  4. whipsaw_engine_shadow=True + LEGACY primary → shadow result stored, primary unchanged
  5. kill-switch + shadow → kill-switch wins, LEGACY primary
  6. engine=OFF → NullEngine primary, _whipsaw_* untouched
"""

import os
import pytest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from webui.backend.routes.mmm.mmm_whipsaw import (
    WhipsawCtx,
    WhipsawDecision,
    whipsaw_decide,
    select_engine,
    WHIPSAW_ENGINE_DISPATCH,
)
from webui.backend.routes.mmm.mmm_safety import MMMSafety


def _make_session(**overrides):
    s = {
        'session_id': 'test-shadow-001',
        'params': {
            'whipsaw_window_mins': 30,
            'whipsaw_spot_move_pct': 0.3,
            'whipsaw_caution_score': 2,
            'whipsaw_restrict_score': 3,
            'whipsaw_cooldown_score': 4,
            'whipsaw_engine': 'SMART',
            'whipsaw_smart_enabled': False,   # key: smart NOT enabled
            'whipsaw_engine_shadow': False,
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


# ── Test 1: engine=SMART always → primary is SMART (guard removed in Phase 6) ──

def test_smart_not_enabled_primary_is_legacy():
    # Phase 6: whipsaw_smart_enabled no longer gates — engine=SMART always selects Smart.
    session = _make_session()  # has whipsaw_smart_enabled=False, but guard is removed
    decision = whipsaw_decide(session, _ctx())
    assert decision.engine == 'SMART', (
        f"engine=SMART must always return SMART primary (guard removed), got {decision.engine}"
    )


# ── Test 2: SMART primary writes _smart_ws_*, never _whipsaw_* ────────────────

def test_smart_shadow_does_not_write_whipsaw_keys():
    # Phase 6: Smart is primary. It must write _smart_ws_* only, never _whipsaw_*.
    now = datetime.now(timezone.utc)
    history = [
        {'aggressor': 'ce', 'timestamp': (now - timedelta(minutes=4)).isoformat(), 'spot': 70000.0},
        {'aggressor': 'pe', 'timestamp': (now - timedelta(minutes=3)).isoformat(), 'spot': 70000.0},
        {'aggressor': 'ce', 'timestamp': (now - timedelta(minutes=2)).isoformat(), 'spot': 70000.0},
        {'aggressor': 'pe', 'timestamp': (now - timedelta(minutes=1)).isoformat(), 'spot': 70000.0},
    ]
    session = _make_session()
    session['adjustment_history'] = history

    decision = whipsaw_decide(session, _ctx())

    assert decision.engine == 'SMART', f"Expected SMART primary, got {decision.engine}"
    # Smart must have written _smart_ws_score
    assert '_smart_ws_score' in session, "_smart_ws_score must be written by SMART primary"
    # Smart must NOT write legacy _whipsaw_score (state isolation)
    assert '_whipsaw_score' not in session, "_whipsaw_score must NOT be written by SMART"
    # Decision uses Smart mode labels
    assert decision.mode in ('NORMAL', 'DEFENSIVE', 'OBSERVE', 'LOCKDOWN'), (
        f"Smart mode expected, got {decision.mode}"
    )


# ── Test 3: Smart is primary, shadow=True → Legacy runs as shadow ─────────────

def test_shadow_writes_smart_ws_keys_not_whipsaw():
    # Phase 6: Smart is primary. With shadow=True, Legacy runs as shadow.
    session = _make_session()
    session['params']['whipsaw_engine'] = 'SMART'
    session['params']['whipsaw_smart_enabled'] = True
    session['params']['whipsaw_engine_shadow'] = True

    whipsaw_decide(session, _ctx())

    # Smart must have written its own state to real session
    assert '_smart_ws_score' in session, "_smart_ws_score must be in real session (Smart is primary)"
    assert '_smart_ws_mode' in session, "_smart_ws_mode must be in real session (Smart is primary)"
    # Legacy shadow result stored in _ws_legacy_shadow_last
    legacy_shadow = session.get('_ws_legacy_shadow_last')
    assert legacy_shadow is not None, "_ws_legacy_shadow_last must be populated when Smart primary + shadow=True"
    assert legacy_shadow.get('primary_engine') == 'SMART'
    assert legacy_shadow.get('shadow_engine') == 'LEGACY'
    assert isinstance(legacy_shadow.get('disagree'), bool)
    # _whipsaw_score must NOT be in real session (Legacy ran on deepcopy)
    assert '_whipsaw_score' not in session, "_whipsaw_score must not leak from Legacy shadow into real session"


# ── Test 4: shadow=True stores comparison data, primary decision unchanged ────

def test_shadow_primary_decision_not_affected_by_smart():
    # Phase 6: Smart is primary. shadow=True runs Legacy as shadow.
    # _whipsaw_score/skip_until in session are legacy state keys — Smart ignores them.
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    session = _make_session(
        _whipsaw_score=5,
        _whipsaw_skip_until=future,
    )
    session['params']['whipsaw_engine'] = 'SMART'
    session['params']['whipsaw_smart_enabled'] = True
    session['params']['whipsaw_engine_shadow'] = True

    decision = whipsaw_decide(session, _ctx())

    # Primary is SMART (ignores legacy _whipsaw_score state)
    assert decision.engine == 'SMART'
    assert decision.mode in ('NORMAL', 'DEFENSIVE', 'OBSERVE', 'LOCKDOWN')
    # Legacy shadow result stored separately
    legacy_shadow = session.get('_ws_legacy_shadow_last')
    assert legacy_shadow is not None, "_ws_legacy_shadow_last must be written when Smart primary + shadow=True"


# ── Test 5: MMM_WHIPSAW_FORCE_LEGACY kills shadow and locks to legacy ─────────

def test_kill_switch_with_shadow_enabled(monkeypatch):
    session = _make_session()
    session['params']['whipsaw_engine_shadow'] = True
    monkeypatch.setenv('MMM_WHIPSAW_FORCE_LEGACY', '1')

    engine = select_engine(session)
    assert engine.name == 'LEGACY', "Kill-switch must force LEGACY regardless of shadow param"

    decision = whipsaw_decide(session, _ctx())
    assert decision.engine == 'LEGACY'


# ── Test 6: engine=OFF → NullEngine, no _whipsaw_* state changes ─────────────

def test_engine_off_no_state_changes():
    session = _make_session()
    session['params']['whipsaw_engine'] = 'OFF'
    session['params']['whipsaw_smart_enabled'] = True  # doesn't matter for OFF
    # Pre-set a whipsaw score to confirm NullEngine doesn't touch it
    session['_whipsaw_score'] = 7

    decision = whipsaw_decide(session, _ctx())

    assert decision.engine == 'OFF'
    assert decision.block_adjustment is False
    assert decision.lot_scalar == 1.0
    assert decision.trigger_widen_factor == 1.0
    # NullEngine must not modify _whipsaw_score
    assert session.get('_whipsaw_score') == 7, (
        "NullWhipsawEngine must not change _whipsaw_score"
    )


# ── Test 7: _smart_ws_series populated regardless of engine ──────────────────

def test_spot_log_always_appended():
    session = _make_session()
    assert '_smart_ws_series' not in session

    whipsaw_decide(session, _ctx())

    series = session.get('_smart_ws_series', [])
    assert len(series) == 1, f"Spot log must be appended every beat, got {len(series)}"
    assert 'spot' in series[0]
    assert series[0]['spot'] == 70000.0


# ── Test 8: Smart mode labels appear as the primary decision (Phase 6) ────────

def test_smart_mode_labels_not_in_primary_decision():
    """Phase 6: Smart is primary, so Smart mode labels are valid primary labels."""
    session = _make_session()
    decision = whipsaw_decide(session, _ctx())
    assert decision.engine == 'SMART', f"Expected SMART primary, got {decision.engine}"
    assert decision.mode in ('NORMAL', 'DEFENSIVE', 'OBSERVE', 'LOCKDOWN'), (
        f"Smart primary must use Smart mode labels, got {decision.mode!r}"
    )
    # Legacy mode labels must NOT appear in Smart primary
    assert decision.mode not in ('CAUTION', 'RESTRICT', 'COOLDOWN')


# ── Test 9: Phase 6 — Smart primary, Legacy shadow ────────────────────────────

def test_phase6_smart_primary_legacy_in_shadow():
    """Phase 6: engine=SMART + smart_enabled=True → Smart is primary.
    With shadow_enabled=True, Legacy runs as shadow; _ws_legacy_shadow_last is written.
    """
    session = {
        'session_id': 'test-phase6-001',
        'params': {
            'whipsaw_window_mins': 30,
            'whipsaw_spot_move_pct': 0.3,
            'whipsaw_caution_score': 2,
            'whipsaw_restrict_score': 3,
            'whipsaw_cooldown_score': 4,
            'whipsaw_engine': 'SMART',
            'whipsaw_smart_enabled': True,    # Phase 6: Smart is binding
            'whipsaw_engine_shadow': True,    # Legacy runs as shadow for comparison
            'adjustment_interval': 300,
            'min_trigger_move': 10.0,
            'strategy_type': 'MMM',
        },
        'adjustment_history': [],
    }
    decision = whipsaw_decide(session, _ctx())

    # Primary decision is from Smart engine
    assert decision.engine == 'SMART', (
        f"Phase 6: engine=SMART + smart_enabled=True must return SMART primary, got {decision.engine}"
    )
    # Smart mode labels are valid
    assert decision.mode in ('NORMAL', 'DEFENSIVE', 'OBSERVE', 'LOCKDOWN'), (
        f"Smart primary decision must use Smart mode labels, got {decision.mode!r}"
    )
    # Smart writes its state keys to the real session
    assert '_smart_ws_score' in session, "_smart_ws_score must be in real session when Smart is primary"
    assert '_smart_ws_mode' in session, "_smart_ws_mode must be in real session when Smart is primary"
    # Legacy shadow stores comparison data
    legacy_shadow = session.get('_ws_legacy_shadow_last')
    assert legacy_shadow is not None, "_ws_legacy_shadow_last must be populated when shadow_enabled=True and Smart is primary"
    assert legacy_shadow.get('primary_engine') == 'SMART'
    assert legacy_shadow.get('shadow_engine') == 'LEGACY'
    assert isinstance(legacy_shadow.get('disagree'), bool)
    # Legacy shadow mode must use Legacy labels
    assert legacy_shadow.get('shadow_mode') in ('NORMAL', 'CAUTION', 'RESTRICT', 'COOLDOWN'), (
        f"Legacy shadow mode must use LEGACY labels, got {legacy_shadow.get('shadow_mode')!r}"
    )
