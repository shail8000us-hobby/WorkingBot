from unittest.mock import AsyncMock, patch

import pytest

from webui.backend.routes.mmm.mmm_dte_presets import (
    STRADDLE_ROLL_CATEGORY,
    STRADDLE_WITH_ADJUSTMENT_CATEGORY,
)
from webui.backend.routes.mmm.mmm_strategy_dispatch import (
    get_strategy_handler,
    resolve_strategy_type,
    validate_session_for_strategy,
)


def _session(strategy_type: str, **overrides):
    base = {
        'strategy_type': strategy_type,
        'params': {
            '_preset_source': strategy_type,
            'straddle_roll_enabled': True,
            'total_dte_hours': 5.0,
        },
        'ce': {'active_strike': 70000, 'frozen_total_lots': 0},
        'pe': {'active_strike': 70000, 'frozen_total_lots': 0},
    }
    for key, value in overrides.items():
        base[key] = value
    return base


def test_resolve_strategy_type_uses_canonical_fallback_chain():
    session = {'params': {'_preset_source': 'SHORT_STRADDLE'}}
    assert resolve_strategy_type(session) == STRADDLE_WITH_ADJUSTMENT_CATEGORY


def test_get_strategy_handler_defaults_to_0dte_handler_for_unknown():
    handler = get_strategy_handler('not-a-real-strategy')
    assert handler.strategy_type == '0DTE'
    assert handler.should_run_adjustment is True


def test_validate_straddle_roll_catches_invariant_violations():
    session = _session(
        STRADDLE_ROLL_CATEGORY,
        ce={'active_strike': 70000, 'frozen_total_lots': 2},
        pe={'active_strike': 69900, 'frozen_total_lots': 0},
    )

    errors = validate_session_for_strategy(session, STRADDLE_ROLL_CATEGORY)

    # Unequal CE/PE strikes and frozen lots are the structural invariants.
    # _preset_source is NOT checked here — identity is already confirmed by
    # the dispatch layer (strategy_type == STRADDLE_ROLL), so checking a
    # legacy param marker would generate spurious warnings.
    assert any('equal CE/PE active strikes' in msg for msg in errors)
    assert any('must not carry frozen lots' in msg for msg in errors)
    assert not any("_preset_source" in msg for msg in errors)


def test_validate_straddle_with_adjustment_allows_unequal_strikes():
    # After a strike shift the CE/PE strikes diverge (strangle) — this is the normal
    # operating state of STRADDLE_WITH_ADJUSTMENT and must never block monitor restart.
    session = _session(
        STRADDLE_WITH_ADJUSTMENT_CATEGORY,
        ce={'active_strike': 77200, 'frozen_total_lots': 0},
        pe={'active_strike': 77600, 'frozen_total_lots': 0},
        params={'total_dte_hours': 5.0},
        entry_time='2026-04-26T10:00:00+00:00',
    )
    errors = validate_session_for_strategy(session, STRADDLE_WITH_ADJUSTMENT_CATEGORY)
    assert not any('equal CE/PE active strikes' in msg for msg in errors)


def test_validate_straddle_with_adjustment_requires_positive_dte_hours():
    # Must have entry_time: the check only fires for entered sessions (not at create time).
    session = _session(
        STRADDLE_WITH_ADJUSTMENT_CATEGORY,
        params={'total_dte_hours': 0},
        entry_time='2026-04-12T06:00:00+00:00',
    )

    errors = validate_session_for_strategy(session, STRADDLE_WITH_ADJUSTMENT_CATEGORY)

    assert any('requires positive total_dte_hours/session_window_hours' in msg for msg in errors)


def test_validate_straddle_with_adjustment_skips_dte_check_at_create_time():
    # Session has no entry_time (fresh, not yet entered) — dte_hours check must not fire
    # so that create_session_endpoint is never blocked by this validator.
    session = _session(
        STRADDLE_WITH_ADJUSTMENT_CATEGORY,
        params={'total_dte_hours': 0},
    )

    errors = validate_session_for_strategy(session, STRADDLE_WITH_ADJUSTMENT_CATEGORY)

    assert not any('requires positive total_dte_hours/session_window_hours' in msg for msg in errors)


@pytest.mark.asyncio
async def test_step_5_4_straddle_with_adjustment_runs_roll_when_enabled():
    handler = get_strategy_handler(STRADDLE_WITH_ADJUSTMENT_CATEGORY)
    session = _session(STRADDLE_WITH_ADJUSTMENT_CATEGORY)

    with patch(
        'webui.backend.routes.mmm.mmm_straddle_adjustment.execute_straddle_roll',
        new=AsyncMock(return_value=True),
    ) as mock_roll:
        skip = await handler.run_step_5_4(object(), session, 'sid-1', 55.0)

    assert skip is True
    mock_roll.assert_awaited_once()


@pytest.mark.asyncio
async def test_step_5_4_straddle_roll_always_skips_adjustment_path():
    handler = get_strategy_handler(STRADDLE_ROLL_CATEGORY)
    session = _session(STRADDLE_ROLL_CATEGORY)

    with patch(
        'webui.backend.routes.mmm.mmm_straddle_roll_pure.execute_pure_straddle_roll',
        new=AsyncMock(return_value=False),
    ) as mock_pure_roll:
        skip = await handler.run_step_5_4(object(), session, 'sid-2', 40.0)

    assert handler.should_run_adjustment is False
    assert skip is True
    mock_pure_roll.assert_awaited_once()
