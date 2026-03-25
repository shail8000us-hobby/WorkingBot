"""
Contract tests for SSDH Config + Presets + Reconciler utilities

SEALED — v1.0.0 — March 21, 2026

Functions covered:
  validate_params / apply_hot_reload / compute_intraday_max_loss  (ssdh_config)
  get_preset / apply_preset_to_params                             (ssdh_presets)
  expiry_to_symbol_suffix / _has_recent_fill                      (ssdh_reconciler)
  check_structure_integrity                                        (ssdh_integrity)
"""

import pytest
from pytest import approx
from datetime import datetime, timezone, timedelta

from webui.backend.routes.ssdh.ssdh_config import (
    validate_params, apply_hot_reload, compute_intraday_max_loss,
)
from webui.backend.routes.ssdh.ssdh_presets import (
    get_preset, apply_preset_to_params, list_presets,
)
from webui.backend.routes.ssdh.ssdh_reconciler import (
    expiry_to_symbol_suffix, _has_recent_fill,
)
from webui.backend.routes.ssdh.ssdh_integrity import check_structure_integrity
from webui.backend.routes.ssdh.ssdh_state import (
    create_position, create_session, DIR_SHORT, DIR_LONG,
    TYPE_CORE, TYPE_HEDGE, ENTRY_COMPLETE, ENTRY_PLACING,
)


# ─── validate_params ──────────────────────────────────────────────────────────

@pytest.mark.sealed
def test_validate_params_valid():
    params = {'initial_lots': 1, 'max_loss_amount': 1000.0, 'trailing_stop_pct': 0.5,
              'expiry': '28032026', 'session_window_hours': 4.0}
    validated, errors = validate_params(params)
    assert not errors
    assert validated['initial_lots'] == 1
    assert validated['trailing_stop_pct'] == approx(0.5)


@pytest.mark.sealed
def test_validate_params_coerce_string_int():
    params = {'initial_lots': '5'}
    validated, errors = validate_params(params)
    assert not errors
    assert validated['initial_lots'] == 5
    assert isinstance(validated['initial_lots'], int)


@pytest.mark.sealed
def test_validate_params_coerce_string_bool():
    params = {'vega_exit_auto': 'true'}
    validated, errors = validate_params(params)
    assert not errors
    assert validated['vega_exit_auto'] is True


@pytest.mark.sealed
def test_validate_params_out_of_range():
    _, errors = validate_params({'initial_lots': 999})
    assert any('initial_lots' in e for e in errors)


@pytest.mark.sealed
def test_validate_params_expiry_pattern():
    _, errors = validate_params({'expiry': '21-03-2026'})
    assert any('expiry' in e for e in errors)


@pytest.mark.sealed
def test_validate_params_hot_only():
    # Cold params should not raise errors in hot_only mode
    params = {'max_loss_amount': 500.0, 'initial_lots': 999}  # lots=999 normally invalid
    validated, errors = validate_params(params, hot_only=True)
    assert not errors
    assert 'max_loss_amount' in validated
    assert 'initial_lots' not in validated  # not in HOT_RELOAD_PARAMS


@pytest.mark.sealed
def test_apply_hot_reload_cold_param_ignored():
    session = {'params': {'initial_lots': 1, 'max_loss_amount': 1000.0}}
    ok, errors = apply_hot_reload(session, {'initial_lots': 99, 'max_loss_amount': 1500.0})
    assert ok
    assert session['params']['initial_lots'] == 1         # unchanged
    assert session['params']['max_loss_amount'] == approx(1500.0)  # updated


@pytest.mark.sealed
def test_compute_intraday_max_loss():
    result = compute_intraday_max_loss(1000.0, 1.75)
    assert result == approx(1750.0)


# ─── presets ──────────────────────────────────────────────────────────────────

@pytest.mark.sealed
def test_get_preset_returns_copy():
    p1 = get_preset('ssdh')
    p2 = get_preset('ssdh')
    p1['long_hedge_lots_ratio'] = 99
    assert p2['long_hedge_lots_ratio'] == 2.0   # not mutated


@pytest.mark.sealed
def test_get_preset_unknown_raises():
    with pytest.raises(ValueError, match='Unknown preset'):
        get_preset('nonexistent')


@pytest.mark.sealed
def test_apply_preset_user_overrides():
    merged = apply_preset_to_params({'session_window_hours': 6.0}, 'ssdh')
    assert merged['session_window_hours'] == approx(6.0)  # user wins
    assert merged['trailing_stop_pct'] == approx(0.50)    # preset default


@pytest.mark.sealed
def test_list_presets_returns_ssdh():
    presets = list_presets()
    names = [p['name'] for p in presets]
    assert 'ssdh' in names


# ─── expiry_to_symbol_suffix ──────────────────────────────────────────────────

@pytest.mark.sealed
def test_expiry_suffix_conversion():
    assert expiry_to_symbol_suffix('11032026') == '110326'


@pytest.mark.sealed
def test_expiry_suffix_end_of_year():
    assert expiry_to_symbol_suffix('31122026') == '311226'


@pytest.mark.sealed
def test_expiry_suffix_invalid_raises():
    with pytest.raises(ValueError):
        expiry_to_symbol_suffix('2026-03-11')  # wrong format


# ─── _has_recent_fill ─────────────────────────────────────────────────────────

@pytest.mark.sealed
def test_has_recent_fill_fresh():
    pos = {'fill_confirmed_at': datetime.now(timezone.utc).isoformat()}
    assert _has_recent_fill(pos, window_seconds=120) is True


@pytest.mark.sealed
def test_has_recent_fill_old():
    old = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()
    pos = {'fill_confirmed_at': old}
    assert _has_recent_fill(pos, window_seconds=120) is False


@pytest.mark.sealed
def test_has_recent_fill_missing():
    assert _has_recent_fill({}, window_seconds=120) is False


# ─── check_structure_integrity ────────────────────────────────────────────────

@pytest.mark.sealed
def test_integrity_all_legs_present():
    session = create_session('s1', {'structure_integrity_check': True})
    session['entry_state'] = ENTRY_COMPLETE
    for side, direction, ptype in [
        ('CE', DIR_SHORT, TYPE_CORE), ('PE', DIR_SHORT, TYPE_CORE),
        ('CE', DIR_LONG,  TYPE_HEDGE),('PE', DIR_LONG,  TYPE_HEDGE),
    ]:
        session['positions'].append(
            create_position(f'{direction}_{side}', side, direction, ptype, 50000, 1, 100.0, 'o','c','ts')
        )
    ok, reason = check_structure_integrity(session)
    assert ok, reason


@pytest.mark.sealed
def test_integrity_missing_short_ce():
    session = create_session('s1', {'structure_integrity_check': True})
    session['entry_state'] = ENTRY_COMPLETE
    # Only add 3 legs, skip short CE
    for side, direction, ptype in [
        ('PE', DIR_SHORT, TYPE_CORE),
        ('CE', DIR_LONG,  TYPE_HEDGE),('PE', DIR_LONG,  TYPE_HEDGE),
    ]:
        session['positions'].append(
            create_position(f'{direction}_{side}', side, direction, ptype, 50000, 1, 100.0, 'o','c','ts')
        )
    ok, reason = check_structure_integrity(session)
    assert not ok
    assert 'CE short' in reason


@pytest.mark.sealed
def test_integrity_skip_during_entry():
    session = create_session('s1', {'structure_integrity_check': True})
    session['entry_state'] = ENTRY_PLACING  # not ENTRY_COMPLETE
    ok, reason = check_structure_integrity(session)
    assert ok   # always True during entry


@pytest.mark.sealed
def test_integrity_disabled_by_param():
    session = create_session('s1', {'structure_integrity_check': False})
    session['entry_state'] = ENTRY_COMPLETE
    # No positions — but check is disabled
    ok, reason = check_structure_integrity(session)
    assert ok
