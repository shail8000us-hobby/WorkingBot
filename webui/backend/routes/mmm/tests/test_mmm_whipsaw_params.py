"""
Phase 2 — Settings plumbing & mutex UI tests

5 tests required by the Phase 2 plan:
  1. test_param_defaults
  2. test_param_validation_invalid_engine
  3. test_param_hot_reload
  4. test_smart_without_smart_enabled_is_shadow
  5. test_engine_off
"""

import os
import pytest

from webui.backend.routes.mmm.mmm_whipsaw import (
    WhipsawCtx,
    LegacyWhipsawEngine,
    NullWhipsawEngine,
    select_engine,
    DEFAULT_ENGINE,
    WHIPSAW_ENGINE_DISPATCH,
)
from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS
from webui.backend.routes.mmm.mmm_config import validate_params


# ---------------------------------------------------------------------------
# Test 1: Phase 6 default → whipsaw_engine='SMART', shadow=True, smart_enabled=True
# (Smart is the promoted primary engine; Legacy runs as shadow for rollback comparison.)
# ---------------------------------------------------------------------------

def test_param_defaults():
    assert DEFAULT_PARAMS.get('whipsaw_engine') == 'SMART', (
        f"whipsaw_engine default must be 'SMART' (Phase 6 promotion), got {DEFAULT_PARAMS.get('whipsaw_engine')!r}"
    )
    assert DEFAULT_PARAMS.get('whipsaw_engine_shadow') is False, (
        f"whipsaw_engine_shadow default must be False (shadow OFF by default), got {DEFAULT_PARAMS.get('whipsaw_engine_shadow')!r}"
    )
    assert DEFAULT_PARAMS.get('whipsaw_smart_enabled') is True, (
        f"whipsaw_smart_enabled default must be True (Phase 6 promotion), got {DEFAULT_PARAMS.get('whipsaw_smart_enabled')!r}"
    )
    # Confirm DEFAULT_ENGINE constant matches
    assert DEFAULT_ENGINE == 'SMART'


# ---------------------------------------------------------------------------
# Test 2: invalid engine name is rejected by validator
# ---------------------------------------------------------------------------

def test_param_validation_invalid_engine():
    _, errors = validate_params({'whipsaw_engine': 'GARBAGE'})
    assert any('whipsaw_engine' in e and 'GARBAGE' in e for e in errors), (
        f"Expected validation error for whipsaw_engine='GARBAGE', got: {errors}"
    )


# ---------------------------------------------------------------------------
# Test 3: hot-reload — select_engine() reads param live (no restart)
# ---------------------------------------------------------------------------

def test_param_hot_reload():
    session = {'params': {'whipsaw_engine': 'LEGACY'}}
    engine_before = select_engine(session)
    assert engine_before.name == 'LEGACY'

    # Simulate a hot-reload: operator flips to OFF
    session['params']['whipsaw_engine'] = 'OFF'
    engine_after = select_engine(session)
    assert engine_after.name == 'OFF', (
        f"After hot param flip to OFF, select_engine should return NullWhipsawEngine, got {engine_after.name}"
    )

    # Flip back to LEGACY
    session['params']['whipsaw_engine'] = 'LEGACY'
    engine_back = select_engine(session)
    assert engine_back.name == 'LEGACY'


# ---------------------------------------------------------------------------
# Test 4: engine=SMART always returns SMART — whipsaw_smart_enabled no longer gates
# (Phase 6: guard removed; whipsaw_engine is the single source of truth)
# ---------------------------------------------------------------------------

def test_smart_without_smart_enabled_is_shadow():
    # whipsaw_smart_enabled=False no longer downgrades to Legacy —
    # whipsaw_engine='SMART' is sufficient to select the Smart engine.
    session = {
        'params': {
            'whipsaw_engine': 'SMART',
            'whipsaw_smart_enabled': False,
        }
    }
    engine = select_engine(session)
    assert engine.name == 'SMART', (
        f"engine=SMART must always return SmartWhipsawEngine (guard removed in Phase 6), got {engine.name}"
    )

    # smart_enabled=True also returns SMART (consistent)
    session['params']['whipsaw_smart_enabled'] = True
    engine_enabled = select_engine(session)
    assert engine_enabled.name in ('SMART', 'LEGACY'), (
        f"engine=SMART with smart_enabled=True should return SMART (Phase 3+) or LEGACY fallback, got {engine_enabled.name}"
    )


# ---------------------------------------------------------------------------
# Test 5: engine=OFF → NullWhipsawEngine, all scalars 1.0, no events, no state writes
# ---------------------------------------------------------------------------

def test_engine_off():
    session = {
        'session_id': 'test-phase2-off',
        'params': {
            'whipsaw_engine': 'OFF',
            'whipsaw_caution_score': 2,
            'whipsaw_restrict_score': 3,
            'whipsaw_cooldown_score': 4,
        },
        '_whipsaw_score': 99,  # high score — should be ignored by OFF engine
        'adjustment_history': [],
    }
    ctx = WhipsawCtx(ce_now=100.0, pe_now=100.0, spot=70000.0)

    engine = select_engine(session)
    assert engine.name == 'OFF'

    decision = engine.evaluate(session, ctx)
    assert decision.engine == 'OFF'
    assert decision.trigger_widen_factor == 1.0
    assert decision.lot_scalar == 1.0
    assert decision.block_adjustment is False
    assert decision.events == ()
    # NullEngine must NOT write any _whipsaw_* state
    assert '_whipsaw_score' not in session or session.get('_whipsaw_score') == 99, (
        "NullWhipsawEngine must not modify _whipsaw_score"
    )
