"""
Sealed contract tests for mmm_replenish — Auto-Replenish Leg.

Functions sealed:
  - check_replenish_eligibility(session, closed_side, open_side) → (bool, str)
  - determine_replenish_lots(session, closed_side, open_side) → int

These are pure decision functions with no I/O.  The monitor's
_process_replenish() method (async, I/O) is not sealed here.

25 contracts total.
"""

import time
import pytest
from copy import deepcopy
from datetime import datetime, timezone, timedelta

from webui.backend.routes.mmm.mmm_replenish import (
    check_replenish_eligibility,
    determine_replenish_lots,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _far_future_expiry():
    """Return an expiry string far in the future so near-expiry gate never fires."""
    return '20301231'


def _base_session(
    replenish_enabled=True,
    strategy_status='RUNNING',
    max_per_session=3,
    cooldown_sec=300,
    min_premium=30.0,
    lot_mode='match_active',
    initial_lots=10,
    max_lots=100,
    stop_adj_mins=15,
    open_active_lots=10,
    open_total_lots=15,
):
    """Build a healthy session that passes all replenish eligibility gates."""
    return {
        'session_id': 'test-replenish-sealed',
        'strategy_status': strategy_status,
        'params': {
            'replenish_enabled': replenish_enabled,
            'replenish_lot_mode': lot_mode,
            'replenish_max_per_session': max_per_session,
            'replenish_cooldown_sec': cooldown_sec,
            'replenish_min_premium': min_premium,
            'initial_lots': initial_lots,
            'max_lots_per_side': max_lots,
            'expiry': _far_future_expiry(),
            'stop_adjustment_mins': stop_adj_mins,
            'wind_down_enabled': False,
            'wind_down_hours_before_expiry': 2.0,
        },
        '_replenish_count': 0,
        '_last_replenish_at': 0,
        '_atm_wind_down_triggered': False,
        '_vol_wind_down_triggered': False,
        '_trend_wind_down_triggered': False,
        '_margin_block_sells': False,
        '_margin_wind_down': False,
        '_regime_action': 'NORMAL',
        'ce': {
            'active_lots': 0,
            'total_lots': 0,
            'positions': [],
        },
        'pe': {
            'active_lots': open_active_lots,
            'total_lots': open_total_lots,
            'positions': [
                {'id': 'pe_orig', 'lots': open_active_lots, 'status': 'active'},
            ],
        },
    }


# ─── check_replenish_eligibility ─────────────────────────────────────────────

class TestCheckReplenishEligibility:
    """Sealed tests for check_replenish_eligibility."""

    @pytest.mark.sealed
    def test_eligible_healthy_session(self):
        """All gates pass → eligible."""
        s = _base_session()
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True
        assert reason == 'eligible'

    @pytest.mark.sealed
    def test_blocked_when_disabled(self):
        """Gate 1: replenish_enabled=False → blocked."""
        s = _base_session(replenish_enabled=False)
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'replenish_enabled' in reason

    @pytest.mark.sealed
    def test_blocked_when_paused(self):
        """Gate 2: session status PAUSED (no OCS recovery flag) → blocked."""
        s = _base_session(strategy_status='PAUSED')
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'status' in reason

    @pytest.mark.sealed
    def test_eligible_when_paused_and_ocs_recovery_active(self):
        """Gate 2 OCS exception: PAUSED + _replenish_ocs_active=True → eligible.
        The OCS watchdog sets this flag so it can retry replenish even after a
        PAUSE was issued.  Stopping an unhedged session is worse than pausing it."""
        s = _base_session(strategy_status='PAUSED')
        s['_replenish_ocs_active'] = True
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"PAUSED+OCS recovery must be eligible; got reason={reason!r}"

    @pytest.mark.sealed
    def test_blocked_when_stopped_even_with_ocs_recovery(self):
        """Gate 2: STOPPED is always blocked — OCS recovery does not override STOPPED.
        STOPPED means the monitor has halted; there is no heartbeat to run replenish."""
        s = _base_session(strategy_status='STOPPED')
        s['_replenish_ocs_active'] = True
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'status' in reason

    @pytest.mark.sealed
    def test_blocked_when_stopped(self):
        """Gate 2: session status STOPPED → blocked."""
        s = _base_session(strategy_status='STOPPED')
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'status' in reason

    @pytest.mark.sealed
    def test_eligible_despite_atm_wind_down(self):
        """Gate 4 REMOVED (hedge restoration principle): ATM wind-down must NOT block replenish.
        Replenish is a defensive hedge-restoration action; wind-down guards apply to
        offensive adjustment sells only.  The caller resets wind-down state after success."""
        s = _base_session()
        s['_atm_wind_down_triggered'] = True
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"ATM wind-down must not block replenish; got reason={reason!r}"

    @pytest.mark.sealed
    def test_eligible_despite_vol_wind_down(self):
        """Gate 3 REMOVED (hedge restoration principle): vol wind-down must NOT block replenish."""
        s = _base_session()
        s['_vol_wind_down_triggered'] = True
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"Vol wind-down must not block replenish; got reason={reason!r}"

    @pytest.mark.sealed
    def test_eligible_despite_trend_wind_down(self):
        """Gate 3 REMOVED (hedge restoration principle): trend wind-down must NOT block replenish."""
        s = _base_session()
        s['_trend_wind_down_triggered'] = True
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"Trend wind-down must not block replenish; got reason={reason!r}"

    @pytest.mark.sealed
    def test_blocked_when_margin_block_sells(self):
        """Gate 5: margin blocks sells → blocked."""
        s = _base_session()
        s['_margin_block_sells'] = True
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'margin_block' in reason

    @pytest.mark.sealed
    def test_blocked_when_margin_wind_down(self):
        """Gate 5: margin wind-down → blocked."""
        s = _base_session()
        s['_margin_wind_down'] = True
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'margin_wind_down' in reason

    @pytest.mark.sealed
    def test_eligible_despite_regime_block_all_sells(self):
        """Gate 6 REMOVED (hedge restoration principle): BLOCK_ALL_SELLS must NOT block replenish.
        Regime blocks are for offensive adjustment sells.  Replenish restores the hedge and
        must not be gated by regime state.  Caller resets regime state after success."""
        s = _base_session()
        s['_regime_action'] = 'BLOCK_ALL_SELLS'
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"BLOCK_ALL_SELLS must not block replenish; got reason={reason!r}"

    @pytest.mark.sealed
    def test_blocked_when_max_count_reached(self):
        """Gate 7: replenish count >= max → blocked."""
        s = _base_session(max_per_session=3)
        s['_replenish_count'] = 3
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'max_count' in reason

    @pytest.mark.sealed
    def test_blocked_when_cooldown_not_elapsed(self):
        """Gate 8: cooldown not yet expired → blocked."""
        s = _base_session(cooldown_sec=300)
        s['_last_replenish_at'] = time.time() - 100  # only 100s ago
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'cooldown' in reason

    @pytest.mark.sealed
    def test_eligible_when_cooldown_exactly_expired(self):
        """Gate 8 boundary: cooldown exactly expired → eligible."""
        s = _base_session(cooldown_sec=300)
        s['_last_replenish_at'] = time.time() - 301
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True

    @pytest.mark.sealed
    def test_eligible_when_never_replenished(self):
        """Gate 8: _last_replenish_at=0 (never) → no cooldown."""
        s = _base_session()
        s['_last_replenish_at'] = 0
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True

    @pytest.mark.sealed
    def test_blocked_when_open_side_empty(self):
        """Gate 10: open side also has 0 lots → blocked."""
        s = _base_session()
        s['pe']['total_lots'] = 0
        s['pe']['active_lots'] = 0
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'open_side_has_no_lots' in reason


# ─── determine_replenish_lots ─────────────────────────────────────────────────

class TestDetermineReplenishLots:
    """Sealed tests for determine_replenish_lots."""

    @pytest.mark.sealed
    def test_match_active_mode(self):
        """match_active returns open side's active_lots."""
        s = _base_session(lot_mode='match_active', open_active_lots=12)
        lots = determine_replenish_lots(s, 'ce', 'pe')
        assert lots == 12

    @pytest.mark.sealed
    def test_initial_mode(self):
        """initial mode returns initial_lots param."""
        s = _base_session(lot_mode='initial', initial_lots=8)
        lots = determine_replenish_lots(s, 'ce', 'pe')
        assert lots == 8

    @pytest.mark.sealed
    def test_clamped_to_max_lots(self):
        """Result clamped to max_lots_per_side."""
        s = _base_session(lot_mode='match_active', max_lots=5, open_active_lots=20)
        lots = determine_replenish_lots(s, 'ce', 'pe')
        assert lots == 5

    @pytest.mark.sealed
    def test_floor_at_one(self):
        """Result floored at 1 even when open side has 0 active."""
        s = _base_session(lot_mode='match_active', open_active_lots=0)
        lots = determine_replenish_lots(s, 'ce', 'pe')
        assert lots == 1

    @pytest.mark.sealed
    def test_initial_mode_clamped(self):
        """initial mode also clamped to max_lots."""
        s = _base_session(lot_mode='initial', initial_lots=50, max_lots=10)
        lots = determine_replenish_lots(s, 'ce', 'pe')
        assert lots == 10

    @pytest.mark.sealed
    def test_reversed_sides(self):
        """Works when PE is closed and CE is open."""
        s = _base_session(lot_mode='match_active', open_active_lots=7)
        # Swap: PE is now closed, CE is open
        s['ce'] = {
            'active_lots': 7,
            'total_lots': 10,
            'positions': [{'id': 'ce_orig', 'lots': 7, 'status': 'active'}],
        }
        s['pe'] = {
            'active_lots': 0,
            'total_lots': 0,
            'positions': [],
        }
        lots = determine_replenish_lots(s, 'pe', 'ce')
        assert lots == 7

    @pytest.mark.sealed
    def test_default_mode_is_match_active(self):
        """When lot_mode is unset, defaults to match_active."""
        s = _base_session(open_active_lots=9)
        s['params'].pop('replenish_lot_mode', None)
        lots = determine_replenish_lots(s, 'ce', 'pe')
        assert lots == 9

    @pytest.mark.sealed
    def test_match_active_uses_active_not_total(self):
        """match_active uses active_lots, not total_lots (excludes frozen)."""
        s = _base_session(lot_mode='match_active', open_active_lots=5, open_total_lots=20)
        lots = determine_replenish_lots(s, 'ce', 'pe')
        assert lots == 5
