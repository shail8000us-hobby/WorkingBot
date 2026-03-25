"""
Contract tests for SSDH State module

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Functions covered:
  create_position / compute_position_pnl / recompute_net_pnl
  create_session / mark_position_closed / persist_session / load_sessions

File: webui/backend/routes/ssdh/ssdh_state.py
"""

import pytest
from unittest.mock import patch
from pytest import approx

from webui.backend.routes.ssdh.ssdh_state import (
    create_position, compute_position_pnl, recompute_net_pnl,
    create_session, mark_position_closed, persist_session, load_sessions,
    DIR_SHORT, DIR_LONG, TYPE_CORE, TYPE_HEDGE,
    POS_ACTIVE, POS_CLOSED, LOT_SIZE_BTC,
)


def _pos(direction=DIR_SHORT, side='CE', pos_type=TYPE_CORE,
         entry_premium=100.0, lots=1, strike=50000.0):
    return create_position('p1', side, direction, pos_type, strike, lots,
                           entry_premium, 'ord_1', 'ssdh_abc_cs_12345678', 'ts')


def _session():
    return create_session('ssdh_210326_abc', {
        'initial_lots': 1, 'desired_ce_premium': 200.0,
        'desired_pe_premium': 200.0, 'long_hedge_premium_target': 50.0,
        'long_hedge_lots_ratio': 2.0, 'expiry': '28032026',
        'session_window_hours': 4.0, 'max_loss_amount': 3000.0,
        'trailing_stop_pct': 0.50,
    })


# ─── create_position ──────────────────────────────────────────────────────────

@pytest.mark.sealed
def test_create_position_mandatory_fields():
    pos = _pos()
    for field in ['pos_id', 'side', 'direction', 'pos_type', 'strike', 'lots',
                  'entry_premium', 'order_id', 'client_order_id', 'fill_confirmed_at',
                  'current_premium', 'unrealized_pnl', 'status', '_being_closed']:
        assert field in pos, f"Missing: {field}"


@pytest.mark.sealed
def test_current_premium_starts_none():
    assert _pos()['current_premium'] is None


@pytest.mark.sealed
def test_being_closed_starts_false():
    assert _pos()['_being_closed'] is False


@pytest.mark.sealed
def test_invalid_direction_raises():
    with pytest.raises(ValueError, match='direction'):
        create_position('p','CE','SELL',TYPE_CORE,50000,1,100.0,'o','c','ts')


@pytest.mark.sealed
def test_invalid_side_raises():
    with pytest.raises(ValueError, match='side'):
        create_position('p','BTC',DIR_SHORT,TYPE_CORE,50000,1,100.0,'o','c','ts')


@pytest.mark.sealed
def test_lots_zero_raises():
    with pytest.raises(ValueError, match='lots'):
        create_position('p','CE',DIR_SHORT,TYPE_CORE,50000,0,100.0,'o','c','ts')


@pytest.mark.sealed
def test_zero_entry_premium_raises():
    with pytest.raises(ValueError, match='entry_premium'):
        create_position('p','CE',DIR_SHORT,TYPE_CORE,50000,1,0.0,'o','c','ts')


# ─── compute_position_pnl ─────────────────────────────────────────────────────

@pytest.mark.sealed
def test_short_pnl_profit():
    pos = _pos(direction=DIR_SHORT, entry_premium=100.0, lots=1)
    pos['current_premium'] = 40.0
    assert compute_position_pnl(pos) == approx(0.06)  # (100-40)×1×0.001


@pytest.mark.sealed
def test_short_pnl_loss():
    pos = _pos(direction=DIR_SHORT, entry_premium=100.0, lots=1)
    pos['current_premium'] = 150.0
    assert compute_position_pnl(pos) == approx(-0.05)


@pytest.mark.sealed
def test_long_pnl_profit():
    pos = _pos(direction=DIR_LONG, pos_type=TYPE_HEDGE, entry_premium=250.0, lots=1)
    pos['current_premium'] = 350.0
    assert compute_position_pnl(pos) == approx(0.10)


@pytest.mark.sealed
def test_long_pnl_loss():
    pos = _pos(direction=DIR_LONG, pos_type=TYPE_HEDGE, entry_premium=250.0, lots=1)
    pos['current_premium'] = 200.0
    assert compute_position_pnl(pos) == approx(-0.05)


@pytest.mark.sealed
def test_none_premium_returns_zero():
    pos = _pos(direction=DIR_SHORT, entry_premium=100.0)
    pos['current_premium'] = None
    assert compute_position_pnl(pos) == 0.0


@pytest.mark.sealed
def test_multilot_scaling():
    pos = _pos(direction=DIR_SHORT, entry_premium=100.0, lots=5)
    pos['current_premium'] = 60.0
    assert compute_position_pnl(pos) == approx(0.20)  # (100-60)×5×0.001


@pytest.mark.sealed
def test_zero_current_premium_is_valid():
    pos = _pos(direction=DIR_SHORT, entry_premium=100.0, lots=1)
    pos['current_premium'] = 0.0
    assert compute_position_pnl(pos) == approx(0.10)   # full decay


# ─── recompute_net_pnl ────────────────────────────────────────────────────────

@pytest.mark.sealed
def test_net_pnl_formula():
    session = _session()
    session['realized_pnl'] = 0.10
    session['total_fees']   = 0.02
    pos = _pos(direction=DIR_SHORT, entry_premium=100.0)
    pos['current_premium'] = 50.0  # unrealized = 0.05
    session['positions'].append(pos)
    result = recompute_net_pnl(session)
    assert result['unrealized_pnl'] == approx(0.05)
    assert result['net_pnl'] == approx(0.13)
    assert session['net_pnl'] == approx(0.13)


@pytest.mark.sealed
def test_stale_legs_reported():
    session = _session()
    pos = _pos()
    pos['pos_id'] = 'stale'
    pos['current_premium'] = None
    session['positions'].append(pos)
    result = recompute_net_pnl(session)
    assert 'stale' in result['stale_legs']


@pytest.mark.sealed
def test_closed_positions_excluded():
    session = _session()
    pos = _pos(direction=DIR_SHORT, entry_premium=100.0)
    pos['status'] = POS_CLOSED
    pos['current_premium'] = 10.0
    session['positions'].append(pos)
    result = recompute_net_pnl(session)
    assert result['unrealized_pnl'] == approx(0.0)


@pytest.mark.sealed
def test_four_leg_session_pnl():
    session = _session()
    p1 = create_position('sc','CE',DIR_SHORT,TYPE_CORE,50000,1,200.0,'o1','c1','ts'); p1['current_premium']=120.0
    p2 = create_position('sp','PE',DIR_SHORT,TYPE_CORE,50000,1,200.0,'o2','c2','ts'); p2['current_premium']=160.0
    p3 = create_position('lc','CE',DIR_LONG,TYPE_HEDGE,52000,2,50.0,'o3','c3','ts'); p3['current_premium']=30.0
    p4 = create_position('lp','PE',DIR_LONG,TYPE_HEDGE,48000,2,50.0,'o4','c4','ts'); p4['current_premium']=70.0
    session['positions'] = [p1,p2,p3,p4]
    result = recompute_net_pnl(session)
    # 0.08 + 0.04 - 0.04 + 0.04 = 0.12
    assert result['unrealized_pnl'] == approx(0.12)


# ─── mark_position_closed ─────────────────────────────────────────────────────

@pytest.mark.sealed
def test_mark_closed_status():
    session = _session()
    pos = _pos(direction=DIR_SHORT, entry_premium=200.0)
    session['positions'].append(pos)
    mark_position_closed(pos, 80.0, 'o', 'c', 'time_exit', session, fees=0.01)
    assert pos['status'] == POS_CLOSED


@pytest.mark.sealed
def test_mark_closed_realized_pnl():
    session = _session()
    pos = _pos(direction=DIR_SHORT, entry_premium=200.0, lots=1)
    session['positions'].append(pos)
    realized = mark_position_closed(pos, 80.0, 'o', 'c', 'time_exit', session, fees=0.0)
    assert realized == approx(0.12)
    assert session['realized_pnl'] == approx(0.12)


@pytest.mark.sealed
def test_mark_closed_fees():
    session = _session()
    pos = _pos(direction=DIR_SHORT, entry_premium=200.0)
    session['positions'].append(pos)
    mark_position_closed(pos, 80.0, 'o', 'c', 'time_exit', session, fees=0.0414)
    assert session['total_fees'] == approx(0.0414)


@pytest.mark.sealed
def test_mark_closed_atomic_refresh():
    session = _session()
    pos_a = _pos(direction=DIR_SHORT, entry_premium=200.0); pos_a['pos_id'] = 'a'
    pos_b = _pos(direction=DIR_SHORT, entry_premium=100.0); pos_b['pos_id'] = 'b'; pos_b['current_premium'] = 50.0
    session['positions'] = [pos_a, pos_b]
    mark_position_closed(pos_a, 80.0, 'o', 'c', 'time_exit', session)
    assert session['unrealized_pnl'] == approx(0.05)


@pytest.mark.sealed
def test_mark_closed_net_pnl():
    session = _session()
    pos = _pos(direction=DIR_SHORT, entry_premium=200.0)
    session['positions'].append(pos)
    mark_position_closed(pos, 80.0, 'o', 'c', 'time_exit', session, fees=0.01)
    assert session['net_pnl'] == approx(0.11)


@pytest.mark.sealed
def test_mark_closed_clears_being_closed():
    session = _session()
    pos = _pos(); pos['_being_closed'] = True
    session['positions'].append(pos)
    mark_position_closed(pos, 80.0, 'o', 'c', 'time_exit', session)
    assert pos['_being_closed'] is False


@pytest.mark.sealed
def test_multiple_fees_accumulated():
    session = _session()
    for i in range(4):
        p = create_position(f'p{i}','CE',DIR_SHORT,TYPE_CORE,50000,1,200.0,f'o{i}',f'c{i}','ts')
        session['positions'].append(p)
        mark_position_closed(p,100.0,'oc','cc','time_exit',session,fees=0.04)
    assert session['total_fees'] == approx(0.16)


# ─── persist / load ───────────────────────────────────────────────────────────

@pytest.mark.sealed
def test_persist_load_roundtrip(tmp_path):
    state_file = str(tmp_path / 'ssdh_sessions.json')
    with patch('webui.backend.routes.ssdh.ssdh_state.SSDH_STATE_FILE', state_file), \
         patch('webui.backend.routes.ssdh.ssdh_state.DATA_DIR', str(tmp_path)):
        session = _session()
        session['realized_pnl'] = 0.42
        persist_session(session)
        loaded = load_sessions()
        sid = session['session_id']
        assert sid in loaded
        assert loaded[sid]['realized_pnl'] == approx(0.42)
        assert loaded[sid]['strategy'] == 'ssdh'


@pytest.mark.sealed
def test_load_sessions_missing_file(tmp_path):
    with patch('webui.backend.routes.ssdh.ssdh_state.SSDH_STATE_FILE', str(tmp_path / 'none.json')):
        assert load_sessions() == {}


@pytest.mark.sealed
def test_load_sessions_corrupt_json(tmp_path):
    bad = tmp_path / 'ssdh_sessions.json'
    bad.write_text('{{bad}}')
    with patch('webui.backend.routes.ssdh.ssdh_state.SSDH_STATE_FILE', str(bad)):
        assert load_sessions() == {}
