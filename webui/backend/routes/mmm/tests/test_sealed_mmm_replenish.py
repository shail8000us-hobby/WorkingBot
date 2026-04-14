"""
Sealed contract tests for mmm_replenish — Auto-Replenish Leg.

Functions sealed:
  - check_replenish_eligibility(session, closed_side, open_side,
                                 ocs_emergency=False) → (bool, str)
  - determine_replenish_lots(session, closed_side, open_side) → int

These are pure decision functions with no I/O.  The monitor's
_process_replenish() method (async, I/O) is not sealed here.

Surviving gates (all others removed — hedge restoration principle):
  G1   replenish_enabled=False   (bypassed in OCS emergency)
  G2   STOPPED only              (PAUSED always allowed)
  G5   margin_block / wind_down
  G10  open side has no active lots

Removed gates (rate-limiting; hedging takes priority):
  G7   max replenish count — no cap on hedge restores
  G8   cooldown             — unhedged cannot wait for a timer
  G9   near expiry          — staying unhedged near expiry is always worse
  G11  lot velocity         — velocity limits must not block hedge restoration
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
    """Return an expiry string far in the future so near-expiry gate never fires.
    Format: DDMMYYYY (bot convention, e.g. 31122030 = 31 Dec 2030)."""
    return '31122030'


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
    def test_eligible_when_paused(self):
        """Gate 2: PAUSED is always allowed — an unhedged position while paused
        is more dangerous than the pause intent.  No _replenish_ocs_active flag
        required."""
        s = _base_session(strategy_status='PAUSED')
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"PAUSED must always allow replenish; got reason={reason!r}"

    @pytest.mark.sealed
    def test_blocked_when_stopped(self):
        """Gate 2: STOPPED blocks — user will handle manually."""
        s = _base_session(strategy_status='STOPPED')
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'STOPPED' in reason

    @pytest.mark.sealed
    def test_blocked_when_stopped_even_with_ocs_recovery(self):
        """Gate 2: STOPPED is always blocked — even _replenish_ocs_active=True
        does not override it.  The monitor has halted; there is no heartbeat."""
        s = _base_session(strategy_status='STOPPED')
        s['_replenish_ocs_active'] = True
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'STOPPED' in reason

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
    def test_eligible_when_max_count_exceeded(self):
        """G7 REMOVED: no cap on hedge restores.  Even at 1000 replenishes,
        an empty side must be replenished."""
        s = _base_session(max_per_session=3)
        s['_replenish_count'] = 1000
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"Max count must not block replenish; got: {reason!r}"

    @pytest.mark.sealed
    def test_eligible_during_active_cooldown(self):
        """G8 REMOVED: no cooldown on replenish.  An unhedged position cannot
        wait for a timer to expire."""
        s = _base_session(cooldown_sec=300)
        s['_last_replenish_at'] = time.time() - 5  # 5s into a 300s cooldown
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"Cooldown must not block replenish; got: {reason!r}"

    @pytest.mark.sealed
    def test_blocked_when_open_side_empty(self):
        """Gate 10: open side also has 0 lots → blocked."""
        s = _base_session()
        s['pe']['total_lots'] = 0
        s['pe']['active_lots'] = 0
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is False
        assert 'open_side_has_no_lots' in reason

    @pytest.mark.sealed
    def test_eligible_when_lot_velocity_exceeded(self):
        """G11 REMOVED: velocity limits must not block hedge restoration.
        Even if 1000 lots were sold this minute, an empty side must still
        be replenished."""
        s = _base_session()
        s['params']['lot_velocity_enabled'] = True
        s['params']['lot_velocity_limit'] = 10
        s['params']['lot_velocity_window_mins'] = 30
        ts_recent = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        s['adjustment_history'] = [
            {'aggressor': 'SHIFT', 'lots_sold': 1000, 'side': 'CE', 'timestamp': ts_recent},
        ]
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"Lot velocity must not block replenish; got: {reason!r}"


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
        """Result floored at 1 when both active AND total are 0."""
        s = _base_session(lot_mode='match_active', open_active_lots=0, open_total_lots=0)
        lots = determine_replenish_lots(s, 'ce', 'pe')
        assert lots == 1

    @pytest.mark.sealed
    def test_match_active_falls_back_to_total_when_active_zero(self):
        """match_active falls back to total_lots when active_lots=0 (frozen exposure).
        Frozen lots are real open positions — the hedge size must reflect total exposure."""
        s = _base_session(lot_mode='match_active', open_active_lots=0, open_total_lots=100)
        lots = determine_replenish_lots(s, 'ce', 'pe')
        assert lots == 100

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


# ─── Bug fixes added 2026-04-12 ───────────────────────────────────────────────

class TestAuditFixes20260412:
    """
    Regression contracts for design decisions made in the 2026-04-12 replenish session.

    G7/G8/G9/G11 have been REMOVED from the eligibility check (hedge restoration
    principle — hedging always beats rate-limiting).  These tests document the
    current contracts: those gates must never block replenish.
    """

    # G11 REMOVED: Gate 11 (velocity) no longer exists in replenish path
    @pytest.mark.sealed
    def test_velocity_never_blocks_replenish(self):
        """G11 REMOVED: Even with massive same-side velocity, replenish is allowed.
        _process_replenish writes history with uppercase 'CE'/'PE' — velocity
        entries are present but must not block (gate is gone)."""
        s = _base_session()
        s['params']['lot_velocity_enabled'] = True
        s['params']['lot_velocity_limit'] = 1      # strictest possible
        s['params']['lot_velocity_window_mins'] = 30
        ts_recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        s['adjustment_history'] = [
            {'aggressor': 'REPLENISH', 'lots_sold': 9999, 'side': 'CE', 'timestamp': ts_recent},
        ]
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"Velocity must not block replenish; got: {reason!r}"

    # G7/G8 REMOVED: max-count and cooldown no longer gate replenish
    @pytest.mark.sealed
    def test_max_count_and_cooldown_never_block_replenish(self):
        """G7+G8 REMOVED: max count exhausted AND active cooldown — still eligible."""
        s = _base_session(max_per_session=1, cooldown_sec=3600)
        s['_replenish_count'] = 9999
        s['_last_replenish_at'] = time.time() - 1   # 1s ago in a 1hr cooldown
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"Max count + cooldown must not block replenish; got: {reason!r}"

    # G9 REMOVED: near-expiry no longer gates replenish
    @pytest.mark.sealed
    def test_near_expiry_never_blocks_replenish(self):
        """G9 REMOVED: even 1 minute to expiry, replenish must proceed.
        Staying unhedged through expiry is always worse than near-expiry sell."""
        s = _base_session()
        # Expiry 1 minute from now — far inside the old stop_adjustment_mins=15 gate
        near_expiry = datetime.now(timezone.utc) + timedelta(minutes=1)
        s['params']['expiry'] = near_expiry.strftime('%d%m%Y')
        s['params']['stop_adjustment_mins'] = 15
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"Near-expiry must not block replenish; got: {reason!r}"

    @pytest.mark.sealed
    def test_malformed_expiry_never_blocks_replenish(self):
        """G9 REMOVED: even a completely unparseable expiry string must not block.
        Gate 9 existed to prevent near-expiry sells — since the gate is removed,
        a parse error has no meaning for eligibility."""
        s = _base_session()
        s['params']['expiry'] = 'NOTANEXPIRY'
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe')
        assert ok is True, f"Malformed expiry must not block replenish; got: {reason!r}"


class TestOCSEmergencyBypass20260412:
    """
    OCS Emergency bypass — ocs_emergency=True additionally bypasses Gate 1
    (master switch) so hedge is restored even if replenish_enabled=False.

    Since G7/G8/G9/G11 are removed from the normal path, the only meaningful
    difference between normal and OCS emergency is the G1 bypass.
    STOPPED is still respected in both paths.
    """

    @pytest.mark.sealed
    def test_ocs_emergency_bypasses_master_switch(self):
        """OCS emergency must proceed even when replenish_enabled=False."""
        s = _base_session(replenish_enabled=False)
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe', ocs_emergency=True)
        assert ok is True, f"OCS emergency must bypass master switch; got: {reason!r}"
        assert 'ocs_emergency' in reason

    @pytest.mark.sealed
    def test_ocs_emergency_still_blocked_by_stopped(self):
        """OCS emergency must NOT proceed when session is STOPPED.
        User has explicitly stopped the session and will handle manually."""
        s = _base_session(strategy_status='STOPPED')
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe', ocs_emergency=True)
        assert ok is False, "STOPPED must block even in OCS emergency"
        assert 'STOPPED' in reason

    @pytest.mark.sealed
    def test_ocs_emergency_still_blocked_by_margin_block(self):
        """OCS emergency must NOT proceed when margin_block_sells is set.
        Margin liquidation risk is worse than being temporarily unhedged."""
        s = _base_session()
        s['_margin_block_sells'] = True
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe', ocs_emergency=True)
        assert ok is False, "Margin block must survive OCS emergency"
        assert 'margin' in reason

    @pytest.mark.sealed
    def test_ocs_emergency_still_blocked_by_margin_wind_down(self):
        """OCS emergency must NOT proceed when margin_wind_down is set."""
        s = _base_session()
        s['_margin_wind_down'] = True
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe', ocs_emergency=True)
        assert ok is False, "Margin wind-down must survive OCS emergency"
        assert 'margin' in reason

    @pytest.mark.sealed
    def test_ocs_emergency_still_blocked_when_open_side_truly_empty(self):
        """OCS emergency must NOT proceed when open side has 0 total lots.
        No active lots AND no frozen lots = nothing to hedge."""
        s = _base_session(open_active_lots=0, open_total_lots=0)
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe', ocs_emergency=True)
        assert ok is False, "Truly empty open side must block even in OCS emergency"
        assert 'open_side_has_no_lots' in reason

    @pytest.mark.sealed
    def test_ocs_emergency_eligible_when_open_side_has_frozen_lots(self):
        """OCS emergency must allow replenish when open side has frozen (non-active) lots.
        Frozen lots are real open positions that still need hedging.
        This is the 'CE: 0 active + 100 frozen, PE: 0' scenario."""
        s = _base_session(open_active_lots=0, open_total_lots=100)
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe', ocs_emergency=True)
        assert ok is True, f"Frozen lots must allow OCS emergency replenish; got: {reason!r}"
        assert 'ocs_emergency' in reason

    @pytest.mark.sealed
    def test_non_ocs_emergency_blocked_when_only_frozen_lots(self):
        """Normal (non-OCS-emergency) path is still blocked when active_lots=0,
        even if frozen lots exist.  Gate 10 is only relaxed in OCS emergency."""
        s = _base_session(open_active_lots=0, open_total_lots=100)
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe', ocs_emergency=False)
        assert ok is False, "Non-OCS-emergency must still require active lots"
        assert 'open_side_has_no_lots' in reason

    @pytest.mark.sealed
    def test_non_ocs_emergency_still_blocked_by_master_switch(self):
        """Regression: without ocs_emergency, master switch must still block."""
        s = _base_session(replenish_enabled=False)
        ok, reason = check_replenish_eligibility(s, 'ce', 'pe', ocs_emergency=False)
        assert ok is False, "Normal path must still respect master switch"
        assert 'replenish_enabled' in reason
