"""
Contract tests for MMM Trigger System — T3-4

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Note: compute_adaptive_interval and compute_adaptive_interval_v2 are already
sealed in #78. This file covers the remaining unsealed functions.

Functions covered:
  evaluate_triggers(session, ce_now, pe_now) -> Dict
  check_frozen_pnl_trigger(session, fetch_fn, ce_now, pe_now) -> Dict
  apply_theta_acceleration(session, minutes_to_expiry) -> Dict
  apply_theta_acceleration_v2(session, minutes_to_expiry, total_dte_mins) -> Dict

File: webui/backend/routes/mmm/mmm_trigger.py

--- evaluate_triggers contracts ---
C-ET-1: zero trigger snapshot → OUTCOME_NONE, no false trigger
C-ET-2: premium rises above threshold → ce_triggered=True
C-ET-3: premium below threshold → outcome='none'
C-ET-4: both sides triggered → outcome='both_triggered'
C-ET-5: _effective_min_trigger_move takes priority over params.min_trigger_move
C-ET-6: dollar floor trigger fires when active dollar loss exceeds min_trigger_dollar
C-ET-7: dollar floor disabled (0) → no dollar trigger

--- check_frozen_pnl_trigger contracts ---
C-CFPT-1: min_frozen_trigger_dollar=0 → disabled, always OUTCOME_NONE
C-CFPT-2: frozen loss below threshold → OUTCOME_NONE
C-CFPT-3: frozen CE loss exceeds threshold → OUTCOME_CE
C-CFPT-4: fetch_premium_fn raises → position skipped, no crash
C-CFPT-5: _being_closed frozen position → skipped

--- apply_theta_acceleration contracts ---
C-ATA-1: minutes_to_expiry > theta_window → not accelerated
C-ATA-2: minutes_to_expiry <= 0 → not accelerated
C-ATA-3: inside window, ≤5min → interval=5
C-ATA-4: inside window, ≤15min → interval=10
C-ATA-5: inside window, ≤30min → interval=20
C-ATA-6: trigger widening: base*2 but capped at 80.0
C-ATA-7: large base_trigger_move (e.g. 60%) → capped at 80%

--- apply_theta_acceleration_v2 contracts ---
C-ATA2-1: minutes_to_expiry > theta_window (DTE-scaled) → not accelerated
C-ATA2-2: total_dte_mins=None → falls back to params.theta_acceleration_window
C-ATA2-3: last 30 min → same intervals as v1 (≤5min→5s)
C-ATA2-4: trigger widening: min(base*2, 80.0) same as v1
"""

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _session(ce_strike=90000.0, pe_strike=88000.0,
             ce_trigger=100.0, pe_trigger=80.0,
             ce_active_lots=10, pe_active_lots=10,
             params=None):
    from webui.backend.routes.mmm.mmm_constants import strike_key
    return {
        'params': params or {
            'min_trigger_move': 15.0,
            'adjustment_interval': 300,
            'theta_acceleration_window': 120,
            'min_trigger_dollar': 0.0,
        },
        'ce': {
            'active_strike': ce_strike,
            'active_lots': ce_active_lots,
            'trigger_snapshot': {strike_key(ce_strike): ce_trigger} if ce_trigger else {},
        },
        'pe': {
            'active_strike': pe_strike,
            'active_lots': pe_active_lots,
            'trigger_snapshot': {strike_key(pe_strike): pe_trigger} if pe_trigger else {},
        },
    }


# =============================================================================
# evaluate_triggers
# =============================================================================

class TestEvaluateTriggers:

    @pytest.mark.sealed
    def test_c_et_1_zero_trigger_snapshot_returns_none(self):
        from webui.backend.routes.mmm.mmm_trigger import evaluate_triggers
        # ce trigger = 0 → guard fires → OUTCOME_NONE
        sess = _session(ce_trigger=0.0, pe_trigger=80.0)
        result = evaluate_triggers(sess, ce_now=200.0, pe_now=70.0)
        assert result['outcome'] == 'none'
        assert result['ce_triggered'] is False

    @pytest.mark.sealed
    def test_c_et_2_ce_premium_above_threshold(self):
        from webui.backend.routes.mmm.mmm_trigger import evaluate_triggers
        # ce_trigger=100, ce_now=120 → excess=20, excess_pct=20 > min_trigger_move=15
        sess = _session(ce_trigger=100.0, pe_trigger=80.0)
        result = evaluate_triggers(sess, ce_now=120.0, pe_now=70.0)
        assert result['ce_triggered'] is True
        assert result['pe_triggered'] is False
        assert result['outcome'] == 'ce_triggered'

    @pytest.mark.sealed
    def test_c_et_3_neither_triggered(self):
        from webui.backend.routes.mmm.mmm_trigger import evaluate_triggers
        # ce_now=105 → excess_pct=5% < 15% → no trigger
        sess = _session(ce_trigger=100.0, pe_trigger=80.0)
        result = evaluate_triggers(sess, ce_now=105.0, pe_now=75.0)
        assert result['outcome'] == 'none'
        assert result['ce_triggered'] is False
        assert result['pe_triggered'] is False

    @pytest.mark.sealed
    def test_c_et_4_both_triggered(self):
        from webui.backend.routes.mmm.mmm_trigger import evaluate_triggers
        sess = _session(ce_trigger=100.0, pe_trigger=80.0)
        result = evaluate_triggers(sess, ce_now=120.0, pe_now=100.0)
        # ce: 20%>15% ✓; pe: 25%>15% ✓
        assert result['ce_triggered'] is True
        assert result['pe_triggered'] is True
        assert result['outcome'] == 'both_triggered'

    @pytest.mark.sealed
    def test_c_et_5_effective_trigger_move_overrides_params(self):
        """_effective_min_trigger_move in session takes priority over params."""
        from webui.backend.routes.mmm.mmm_trigger import evaluate_triggers
        # params has 15% but effective is 30% (theta-widened)
        sess = _session(ce_trigger=100.0, pe_trigger=80.0)
        sess['_effective_min_trigger_move'] = 30.0  # overrides params.min_trigger_move=15
        # ce: excess_pct=20% < 30% → NOT triggered (would fire with 15%)
        result = evaluate_triggers(sess, ce_now=120.0, pe_now=70.0)
        assert result['ce_triggered'] is False
        assert result['min_trigger_move'] == 30.0

    @pytest.mark.sealed
    def test_c_et_6_dollar_floor_trigger_fires(self):
        """min_trigger_dollar fires when active USD loss exceeds threshold."""
        from webui.backend.routes.mmm.mmm_trigger import evaluate_triggers
        # ce: excess=5.0, active_lots=10, LOT=0.001 → dollar_excess=5*10*0.001=0.05
        # min_trigger_dollar=0.04 → 0.05>0.04 → fires
        params = {
            'min_trigger_move': 50.0,      # high % threshold so % doesn't fire
            'min_trigger_dollar': 0.04,
            'adjustment_interval': 300,
        }
        sess = _session(ce_trigger=100.0, pe_trigger=80.0, params=params,
                        ce_active_lots=10, pe_active_lots=10)
        result = evaluate_triggers(sess, ce_now=105.0, pe_now=70.0)
        assert result['ce_dollar_triggered'] is True
        assert result['ce_triggered'] is True  # OR condition

    @pytest.mark.sealed
    def test_c_et_7_dollar_floor_disabled(self):
        """min_trigger_dollar=0 → dollar trigger never fires."""
        from webui.backend.routes.mmm.mmm_trigger import evaluate_triggers
        params = {
            'min_trigger_move': 50.0,
            'min_trigger_dollar': 0.0,  # disabled
            'adjustment_interval': 300,
        }
        sess = _session(ce_trigger=100.0, pe_trigger=80.0, params=params)
        result = evaluate_triggers(sess, ce_now=200.0, pe_now=70.0)
        assert result['ce_dollar_triggered'] is False


# =============================================================================
# check_frozen_pnl_trigger
# =============================================================================

class TestCheckFrozenPnlTrigger:

    @pytest.mark.sealed
    def test_c_cfpt_1_disabled_when_zero(self):
        from webui.backend.routes.mmm.mmm_trigger import check_frozen_pnl_trigger
        sess = _session()
        sess['params']['min_frozen_trigger_dollar'] = 0.0
        result = check_frozen_pnl_trigger(sess, fetch_premium_fn=lambda s, t: 200.0)
        assert result['outcome'] == 'none'
        assert result['frozen_triggered'] is False

    @pytest.mark.sealed
    def test_c_cfpt_2_loss_below_threshold(self):
        from webui.backend.routes.mmm.mmm_trigger import check_frozen_pnl_trigger
        from webui.backend.routes.mmm.mmm_constants import strike_key
        sess = _session()
        sess['params']['min_frozen_trigger_dollar'] = 100.0
        # CE frozen position: entry=100, current=110, lots=5 → loss=0.5 << 100
        sess['ce']['frozen_positions'] = [
            {'strike': 90000.0, 'lots': 5, 'entry_premium': 100.0}
        ]
        sess['ce']['trigger_snapshot'] = {strike_key(90000.0): 100.0}
        result = check_frozen_pnl_trigger(sess, fetch_premium_fn=lambda s, t: 110.0)
        assert result['outcome'] == 'none'

    @pytest.mark.sealed
    def test_c_cfpt_3_ce_frozen_loss_exceeds_threshold(self):
        from webui.backend.routes.mmm.mmm_trigger import check_frozen_pnl_trigger
        from webui.backend.routes.mmm.mmm_constants import strike_key
        sess = _session()
        sess['params']['min_frozen_trigger_dollar'] = 0.01
        # CE frozen: entry=100, current=200, lots=5 → loss=(200-100)*5*0.001=0.5 > 0.01
        sess['ce']['frozen_positions'] = [
            {'strike': 90000.0, 'lots': 5, 'entry_premium': 100.0}
        ]
        sess['ce']['trigger_snapshot'] = {strike_key(90000.0): 100.0}
        result = check_frozen_pnl_trigger(sess, fetch_premium_fn=lambda s, t: 200.0)
        assert result['ce_triggered'] is True
        assert result['outcome'] in ('ce_triggered', 'both_triggered')

    @pytest.mark.sealed
    def test_c_cfpt_4_fetch_exception_skips_position(self):
        from webui.backend.routes.mmm.mmm_trigger import check_frozen_pnl_trigger
        from webui.backend.routes.mmm.mmm_constants import strike_key
        sess = _session()
        sess['params']['min_frozen_trigger_dollar'] = 0.01
        sess['ce']['frozen_positions'] = [
            {'strike': 90000.0, 'lots': 5, 'entry_premium': 100.0}
        ]

        def bad_fetch(s, t):
            raise RuntimeError("price unavailable")

        # Should not crash, should return OUTCOME_NONE (position skipped)
        result = check_frozen_pnl_trigger(sess, fetch_premium_fn=bad_fetch)
        assert result['outcome'] == 'none'

    @pytest.mark.sealed
    def test_c_cfpt_5_being_closed_skipped(self):
        from webui.backend.routes.mmm.mmm_trigger import check_frozen_pnl_trigger
        from webui.backend.routes.mmm.mmm_constants import strike_key
        sess = _session()
        sess['params']['min_frozen_trigger_dollar'] = 0.01
        # Even with huge loss, _being_closed=True should skip this position
        sess['ce']['frozen_positions'] = [
            {'strike': 90000.0, 'lots': 5, 'entry_premium': 10.0, '_being_closed': True}
        ]
        result = check_frozen_pnl_trigger(sess, fetch_premium_fn=lambda s, t: 9999.0)
        assert result['outcome'] == 'none'


# =============================================================================
# apply_theta_acceleration
# =============================================================================

class TestApplyThetaAcceleration:

    def _sess(self, theta_window=120, min_trigger=15.0, interval=300):
        return {'params': {
            'theta_acceleration_window': theta_window,
            'min_trigger_move': min_trigger,
            'adjustment_interval': interval,
        }}

    @pytest.mark.sealed
    def test_c_ata_1_outside_window_not_accelerated(self):
        from webui.backend.routes.mmm.mmm_trigger import apply_theta_acceleration
        result = apply_theta_acceleration(self._sess(theta_window=120), minutes_to_expiry=200)
        assert result['accelerated'] is False
        assert result['effective_interval'] == 300

    @pytest.mark.sealed
    def test_c_ata_2_zero_or_negative_not_accelerated(self):
        from webui.backend.routes.mmm.mmm_trigger import apply_theta_acceleration
        result = apply_theta_acceleration(self._sess(), minutes_to_expiry=0)
        assert result['accelerated'] is False
        result2 = apply_theta_acceleration(self._sess(), minutes_to_expiry=-1)
        assert result2['accelerated'] is False

    @pytest.mark.sealed
    def test_c_ata_3_within_5min_interval_5(self):
        from webui.backend.routes.mmm.mmm_trigger import apply_theta_acceleration
        result = apply_theta_acceleration(self._sess(), minutes_to_expiry=3)
        assert result['accelerated'] is True
        assert result['effective_interval'] == 5

    @pytest.mark.sealed
    def test_c_ata_4_within_15min_interval_10(self):
        from webui.backend.routes.mmm.mmm_trigger import apply_theta_acceleration
        result = apply_theta_acceleration(self._sess(), minutes_to_expiry=10)
        assert result['accelerated'] is True
        assert result['effective_interval'] == 10

    @pytest.mark.sealed
    def test_c_ata_5_within_30min_interval_20(self):
        from webui.backend.routes.mmm.mmm_trigger import apply_theta_acceleration
        result = apply_theta_acceleration(self._sess(), minutes_to_expiry=20)
        assert result['accelerated'] is True
        assert result['effective_interval'] == 20

    @pytest.mark.sealed
    def test_c_ata_6_trigger_widening_doubles_capped_at_80(self):
        from webui.backend.routes.mmm.mmm_trigger import apply_theta_acceleration
        result = apply_theta_acceleration(self._sess(min_trigger=15.0), minutes_to_expiry=10)
        assert result['effective_min_trigger_move'] == 30.0  # 15*2 = 30

    @pytest.mark.sealed
    def test_c_ata_7_trigger_widening_capped_at_80(self):
        from webui.backend.routes.mmm.mmm_trigger import apply_theta_acceleration
        # base=60, doubled=120 → capped at 80
        result = apply_theta_acceleration(self._sess(min_trigger=60.0), minutes_to_expiry=10)
        assert result['effective_min_trigger_move'] == 80.0


# =============================================================================
# apply_theta_acceleration_v2
# =============================================================================

class TestApplyThetaAccelerationV2:

    def _sess(self, theta_window=120, min_trigger=15.0, interval=300):
        return {'params': {
            'theta_acceleration_window': theta_window,
            'min_trigger_move': min_trigger,
            'adjustment_interval': interval,
        }}

    @pytest.mark.sealed
    def test_c_ata2_1_outside_window_not_accelerated(self):
        from webui.backend.routes.mmm.mmm_trigger import apply_theta_acceleration_v2
        # total_dte_mins=1440 (1 day), theta_window=max(30,1440*0.02)=max(30,28.8)=30
        # minutes_to_expiry=100 > 30 → not accelerated
        result = apply_theta_acceleration_v2(self._sess(), minutes_to_expiry=100,
                                              total_dte_mins=1440)
        assert result['accelerated'] is False

    @pytest.mark.sealed
    def test_c_ata2_2_fallback_to_params_when_no_total(self):
        from webui.backend.routes.mmm.mmm_trigger import apply_theta_acceleration_v2
        # total_dte_mins=None → falls back to params.theta_acceleration_window=120
        # minutes_to_expiry=200 > 120 → not accelerated
        result = apply_theta_acceleration_v2(self._sess(theta_window=120),
                                              minutes_to_expiry=200,
                                              total_dte_mins=None)
        assert result['accelerated'] is False

    @pytest.mark.sealed
    def test_c_ata2_3_last_5min_same_interval_as_v1(self):
        from webui.backend.routes.mmm.mmm_trigger import apply_theta_acceleration_v2
        result = apply_theta_acceleration_v2(self._sess(), minutes_to_expiry=3,
                                              total_dte_mins=1440)
        assert result['accelerated'] is True
        assert result['effective_interval'] == 5

    @pytest.mark.sealed
    def test_c_ata2_4_trigger_widening_capped_at_80(self):
        from webui.backend.routes.mmm.mmm_trigger import apply_theta_acceleration_v2
        result = apply_theta_acceleration_v2(self._sess(min_trigger=60.0),
                                              minutes_to_expiry=3, total_dte_mins=1440)
        assert result['effective_min_trigger_move'] == 80.0
