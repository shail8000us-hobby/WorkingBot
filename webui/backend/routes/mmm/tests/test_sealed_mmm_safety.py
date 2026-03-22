"""
Contract tests for MMMSafety — all safety and strength-improvement checks.

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Covers T2-1 functions (MMM Audit Plan):
  check_position_cap, check_total_exposure, check_whipsaw, check_asymmetry,
  check_near_expiry, check_near_expiry_v2, check_pnl_guardrail,
  check_trailing_stop, check_margin, check_lot_velocity, check_max_adjustments,
  run_all_checks, should_block_adjustment, get_block_action, should_pause,
  update_peak_pnl, reset_peak_pnl_on_reversal

File: webui/backend/routes/mmm/mmm_safety.py

--- check_position_cap contracts ---
C-PC-1: Both sides under cap → no events
C-PC-2: CE exactly at cap → stop_adjustments for CE only
C-PC-3: CE at 80% of cap → warning (continue)
C-PC-4: CE below 80% → no events
C-PC-5: Both sides at cap → two stop_adjustments events
C-PC-6: max_lots=0 → no division by zero, no events

--- check_total_exposure contracts ---
C-TE-1: Both sides under ceiling, below 80% → no events
C-TE-2: CE at ceiling → 'warn' (NOT stop_adjustments)
C-TE-3: CE at 80% of ceiling → continue info
C-TE-4: max_total_exposure=0 defaults to max_lots_per_side × 2
C-TE-5: max_total_exposure unset → defaults to max_lots_per_side × 2

--- check_whipsaw contracts ---
C-WS-1: No history, score=0 → no events
C-WS-2: _whipsaw_skip_until active (not expired) → COOLDOWN stop_adjustments, early exit
C-WS-3: _whipsaw_skip_until expired → score reduced by 2, continues evaluation
C-WS-4: Score > 0, last noise > 1 interval ago → score decays by 1
C-WS-5: Alternating adjustments inside window, no spot data → score increments
C-WS-6: Alternating but spot moved >= spot_move_pct → NOT counted as noise
C-WS-7: Same-direction consecutive adjustments → not counted
C-WS-8: Score at caution threshold → CAUTION event (continue)
C-WS-9: Score at restrict threshold → RESTRICT event (continue)
C-WS-10: Score at cooldown threshold → COOLDOWN event (stop_adjustments), _whipsaw_skip_until set
C-WS-11: Migration: old _whipsaw_paused_at → cleared, resume event returned, early exit
C-WS-12: OPERATOR/STRADDLE_ROLL aggressors excluded from alternation scoring
C-WS-13: _whipsaw_last_checked_idx=None first run → set to history length, no alternation scored

--- check_asymmetry contracts ---
C-AS-1: Both sides 0 lots → no events, flags cleared
C-AS-2: Equal sides → no events, flags cleared
C-AS-3: ratio 3:1 → warning (continue), session flags cleared
C-AS-4: ratio 5:1 → alert (warn), _asymmetry_lot_reduction_pct/heavy_side set
C-AS-5: ratio 7:1 with hard_block_enabled=True → block_heavy_side_sells, flags cleared
C-AS-6: ratio 7:1 with hard_block_enabled=False → falls to 5:1 tier
C-AS-7: ratio < 3:1 → no event, flags cleared
C-AS-8: PE > CE → heavy_side='pe'

--- check_near_expiry contracts ---
C-NE-1: > 60 min → no events
C-NE-2: Between stop_mins and 60 → info continue
C-NE-3: Exactly at stop_mins → stop_adjustments
C-NE-4: Between close_mins and stop_mins → stop_adjustments
C-NE-5: Exactly at close_mins → auto_close
C-NE-6: Below close_mins → auto_close

--- check_near_expiry_v2 contracts ---
C-NE2-1: <= close_mins → auto_close, returns immediately
C-NE2-2: <= stop_mins → stop_adjustments, returns immediately
C-NE2-3: <= wind_down_mins → wind_down action
C-NE2-4: <= last 5% of total_dte_hours (> 36h) → info continue
C-NE2-5: Outside all thresholds → no events

--- check_pnl_guardrail contracts ---
C-PG-1: Positive P&L → no events
C-PG-2: P&L at exactly 50% → warning fires
C-PG-3: P&L at exactly 80% → alert fires (was Bug 1: 0.8 < ratio was a gap)
C-PG-4: P&L between 50% and 80% → warning
C-PG-5: P&L between 80% and 100% → alert
C-PG-6: max_loss=0 → no events (ratio=0 guard)
C-PG-7: P&L at 100% → no event from guardrail (check_max_loss handles it)
C-PG-8: Includes perp hedge P&L in total

--- check_trailing_stop contracts ---
C-TS-1: trailing_pct=0 → no events (disabled)
C-TS-2: peak_pnl=0 → no events
C-TS-3: P&L above floor → no events
C-TS-4: P&L below floor → stop_adjustments
C-TS-5: P&L exactly at floor (not below) → no events
C-TS-6: Perp hedge P&L included in current

--- check_margin contracts ---
C-MG-1: Combined lots under 150% cap → no events
C-MG-2: Combined lots over 150% cap → margin_warning (warn)

--- check_lot_velocity contracts ---
C-LV-1: lot_velocity_enabled=False → no events
C-LV-2: Lots in window under limit → no events
C-LV-3: Lots at limit → stop_adjustments
C-LV-4: Lots at 80% of limit → warning (continue)
C-LV-5: OPERATOR aggressor excluded from count
C-LV-6: Entries outside rolling window excluded

--- check_max_adjustments contracts ---
C-MA-1: Under max → no events
C-MA-2: Approaching (≥ 90%) but below max → warning (continue)
C-MA-3: Exactly at max → pause event, _max_adj_paused flag set
C-MA-4: Flag set and now below max → resume event, flag cleared
C-MA-5: Flag set and still at max → no auto-resume, pause fires again

--- run_all_checks contracts ---
C-RAC-1: minutes_to_expiry=None → no near_expiry events in output
C-RAC-2: 0DTE session with minutes_to_expiry → uses v1 (no wind_down)
C-RAC-3: Multi-DTE session (total_dte_hours > 36) → uses v2 (wind_down possible)
C-RAC-4: Healthy session → no blocking events

--- should_block_adjustment contracts ---
C-SBA-1: 'stop' action → True
C-SBA-2: 'auto_close' action → True
C-SBA-3: 'stop_adjustments' action → True
C-SBA-4: 'continue' / 'warn' / 'pause' → False
C-SBA-5: 'block_heavy_side_sells' → False (not a full block)
C-SBA-6: Empty list → False

--- get_block_action contracts ---
C-GBA-1: auto_close + stop_adjustments → returns auto_close (highest priority)
C-GBA-2: Only stop_adjustments → returns stop_adjustments
C-GBA-3: auto_close only → auto_close, tuple format correct

--- should_pause contracts ---
C-SP-1: 'pause' action → True + reason
C-SP-2: 'stop' action → False
C-SP-3: Empty list → False, empty string

--- update_peak_pnl contracts ---
C-UPP-1: P&L exceeds current peak → peak updated, timestamp set
C-UPP-2: P&L at zero, peak=0 → peak stays 0
C-UPP-3: P&L below current peak → decayed peak stored (never exceeds old peak)

--- reset_peak_pnl_on_reversal contracts ---
C-RPR-1: Positive P&L → peak set to P&L value
C-RPR-2: Negative P&L → peak set to 0
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


@pytest.fixture
def safety():
    from webui.backend.routes.mmm.mmm_safety import MMMSafety
    return MMMSafety()


def _session(**overrides):
    """Minimal healthy session."""
    s = {
        'params': {
            'max_lots_per_side': 10,
            'max_adjustments': 20,
            'max_loss_amount': 1000.0,
            'whipsaw_caution_score': 2,
            'whipsaw_restrict_score': 3,
            'whipsaw_cooldown_score': 4,
            'whipsaw_window_mins': 30,
            'whipsaw_spot_move_pct': 0.3,
            'adjustment_interval': 300,
            'stop_adjustment_mins': 15,
            'auto_close_mins': 5,
            'trailing_stop_pct': 0.5,
            'lot_velocity_enabled': True,
            'lot_velocity_limit': 10,
            'lot_velocity_window_mins': 30,
            'asymmetry_7to1_hard_block': True,
            'asymmetry_5to1_lot_reduction': 0.5,
        },
        'ce': {'active_lots': 0, 'total_lots': 0, 'frozen_total_lots': 0},
        'pe': {'active_lots': 0, 'total_lots': 0, 'frozen_total_lots': 0},
        'realized_pnl': 0.0,
        'unrealized_pnl': 0.0,
        'adjustment_count': 0,
        'adjustment_history': [],
        'peak_pnl': 0.0,
    }
    # Apply nested overrides
    for k, v in overrides.items():
        if '.' in k:
            top, sub = k.split('.', 1)
            s.setdefault(top, {})[sub] = v
        else:
            s[k] = v
    return s


def _ts(offset_secs=0):
    """ISO timestamp offset from now."""
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_secs)).isoformat()


# =============================================================================
# check_position_cap
# =============================================================================

class TestCheckPositionCap:

    @pytest.mark.sealed
    def test_c_pc_1_both_under_cap(self, safety):
        sess = _session()
        sess['ce']['active_lots'] = 5
        sess['pe']['active_lots'] = 5
        assert safety.check_position_cap(sess) == []

    @pytest.mark.sealed
    def test_c_pc_2_at_cap_stop_adjustments(self, safety):
        sess = _session()
        sess['ce']['active_lots'] = 10  # == max_lots_per_side
        events = safety.check_position_cap(sess)
        assert len(events) == 1
        assert events[0]['type'] == 'position_cap'
        assert events[0]['action'] == 'stop_adjustments'
        assert events[0]['details']['side'] == 'ce'

    @pytest.mark.sealed
    def test_c_pc_3_at_80pct_warning(self, safety):
        sess = _session()
        sess['ce']['active_lots'] = 8  # 80% of 10
        events = safety.check_position_cap(sess)
        assert len(events) == 1
        assert events[0]['action'] == 'continue'
        assert events[0]['level'] == 'warning'

    @pytest.mark.sealed
    def test_c_pc_4_below_80pct_no_events(self, safety):
        sess = _session()
        sess['ce']['active_lots'] = 7
        assert safety.check_position_cap(sess) == []

    @pytest.mark.sealed
    def test_c_pc_5_both_at_cap_two_events(self, safety):
        sess = _session()
        sess['ce']['active_lots'] = 10
        sess['pe']['active_lots'] = 10
        events = safety.check_position_cap(sess)
        assert len(events) == 2
        assert all(e['action'] == 'stop_adjustments' for e in events)

    @pytest.mark.sealed
    def test_c_pc_6_max_lots_zero_no_crash(self, safety):
        sess = _session()
        sess['params']['max_lots_per_side'] = 0
        sess['ce']['active_lots'] = 5
        # Should not divide by zero
        events = safety.check_position_cap(sess)
        assert isinstance(events, list)


# =============================================================================
# check_total_exposure
# =============================================================================

class TestCheckTotalExposure:

    @pytest.mark.sealed
    def test_c_te_1_under_ceiling(self, safety):
        sess = _session()
        sess['ce']['total_lots'] = 5
        sess['pe']['total_lots'] = 5
        assert safety.check_total_exposure(sess) == []

    @pytest.mark.sealed
    def test_c_te_2_at_ceiling_warns_not_stops(self, safety):
        sess = _session()
        sess['params']['max_total_exposure'] = 20
        sess['ce']['total_lots'] = 20
        events = safety.check_total_exposure(sess)
        assert len(events) == 1
        assert events[0]['action'] == 'warn'  # NOT stop_adjustments
        assert events[0]['type'] == 'total_exposure'

    @pytest.mark.sealed
    def test_c_te_3_at_80pct_info(self, safety):
        sess = _session()
        sess['params']['max_total_exposure'] = 20
        sess['ce']['total_lots'] = 16  # 80%
        events = safety.check_total_exposure(sess)
        assert len(events) == 1
        assert events[0]['action'] == 'continue'
        assert events[0]['level'] == 'info'

    @pytest.mark.sealed
    def test_c_te_4_max_total_zero_defaults_to_2x_side(self, safety):
        """max_total_exposure=0 → defaults to max_lots_per_side * 2 = 20"""
        sess = _session()
        sess['params']['max_total_exposure'] = 0
        sess['params']['max_lots_per_side'] = 10
        sess['ce']['total_lots'] = 20  # exactly 2x side cap
        events = safety.check_total_exposure(sess)
        assert any(e['type'] == 'total_exposure' for e in events)

    @pytest.mark.sealed
    def test_c_te_5_max_total_missing_defaults_to_2x_side(self, safety):
        sess = _session()
        sess['params'].pop('max_total_exposure', None)
        sess['params']['max_lots_per_side'] = 10
        sess['ce']['total_lots'] = 21  # over 2x default
        events = safety.check_total_exposure(sess)
        assert len(events) == 1


# =============================================================================
# check_whipsaw
# =============================================================================

class TestCheckWhipsaw:

    @pytest.mark.sealed
    def test_c_ws_1_empty_history_no_events(self, safety):
        sess = _session()
        events = safety.check_whipsaw(sess)
        assert events == []

    @pytest.mark.sealed
    def test_c_ws_2_skip_until_active_returns_cooldown(self, safety):
        sess = _session()
        sess['_whipsaw_skip_until'] = _ts(+600)  # 10 min in future
        sess['_whipsaw_score'] = 4
        events = safety.check_whipsaw(sess)
        assert len(events) == 1
        assert events[0]['action'] == 'stop_adjustments'
        assert events[0]['details']['level'] == 'COOLDOWN'

    @pytest.mark.sealed
    def test_c_ws_3_skip_until_expired_reduces_score(self, safety):
        sess = _session()
        sess['_whipsaw_skip_until'] = _ts(-60)  # expired 1 min ago
        sess['_whipsaw_score'] = 4
        safety.check_whipsaw(sess)
        # Score reduced by 2 after cooldown expiry
        assert sess['_whipsaw_score'] == 2
        assert '_whipsaw_skip_until' not in sess

    @pytest.mark.sealed
    def test_c_ws_4_score_decay_over_interval(self, safety):
        sess = _session()
        sess['params']['adjustment_interval'] = 300
        sess['_whipsaw_score'] = 3
        # Last noise was 2 intervals ago → decay by 2
        sess['_whipsaw_last_noise_at'] = _ts(-610)  # > 2 intervals
        safety.check_whipsaw(sess)
        assert sess['_whipsaw_score'] == 1  # 3 - 2 = 1

    @pytest.mark.sealed
    def test_c_ws_5_alternating_increments_score(self, safety):
        sess = _session()
        sess['_whipsaw_last_checked_idx'] = 0
        # Two alternating CE→PE adjustments, no spot data
        sess['adjustment_history'] = [
            {'aggressor': 'CE', 'timestamp': _ts(-60), 'lots_sold': 1},
            {'aggressor': 'PE', 'timestamp': _ts(-30), 'lots_sold': 1},
        ]
        safety.check_whipsaw(sess)
        assert sess['_whipsaw_score'] >= 1

    @pytest.mark.sealed
    def test_c_ws_6_large_spot_move_not_counted(self, safety):
        sess = _session()
        sess['_whipsaw_last_checked_idx'] = 0
        sess['params']['whipsaw_spot_move_pct'] = 0.3
        sess['adjustment_history'] = [
            {'aggressor': 'CE', 'timestamp': _ts(-60), 'lots_sold': 1, 'spot': 50000},
            {'aggressor': 'PE', 'timestamp': _ts(-30), 'lots_sold': 1, 'spot': 50200},  # 0.4% move
        ]
        safety.check_whipsaw(sess)
        # Spot moved ≥ 0.3% → not noise
        assert sess.get('_whipsaw_score', 0) == 0

    @pytest.mark.sealed
    def test_c_ws_7_same_direction_not_counted(self, safety):
        sess = _session()
        sess['_whipsaw_last_checked_idx'] = 0
        sess['adjustment_history'] = [
            {'aggressor': 'CE', 'timestamp': _ts(-60), 'lots_sold': 1},
            {'aggressor': 'CE', 'timestamp': _ts(-30), 'lots_sold': 1},
        ]
        safety.check_whipsaw(sess)
        assert sess.get('_whipsaw_score', 0) == 0

    @pytest.mark.sealed
    def test_c_ws_8_caution_tier(self, safety):
        sess = _session()
        sess['_whipsaw_score'] = 2  # == caution threshold
        events = safety.check_whipsaw(sess)
        caution = [e for e in events if e.get('details', {}).get('level') == 'CAUTION']
        assert caution
        assert caution[0]['action'] == 'continue'

    @pytest.mark.sealed
    def test_c_ws_9_restrict_tier(self, safety):
        sess = _session()
        sess['_whipsaw_score'] = 3  # == restrict threshold
        events = safety.check_whipsaw(sess)
        restrict = [e for e in events if e.get('details', {}).get('level') == 'RESTRICT']
        assert restrict
        assert restrict[0]['action'] == 'continue'

    @pytest.mark.sealed
    def test_c_ws_10_cooldown_tier_sets_skip_until(self, safety):
        sess = _session()
        sess['_whipsaw_score'] = 4  # == cooldown threshold
        events = safety.check_whipsaw(sess)
        cooldown = [e for e in events if e.get('action') == 'stop_adjustments']
        assert cooldown
        assert '_whipsaw_skip_until' in sess

    @pytest.mark.sealed
    def test_c_ws_11_migration_clears_old_paused_at(self, safety):
        sess = _session()
        sess['_whipsaw_paused_at'] = _ts(-3600)
        events = safety.check_whipsaw(sess)
        assert '_whipsaw_paused_at' not in sess
        resume = [e for e in events if e.get('action') == 'resume']
        assert resume

    @pytest.mark.sealed
    def test_c_ws_12_operator_aggressor_excluded(self, safety):
        sess = _session()
        sess['_whipsaw_last_checked_idx'] = 0
        sess['adjustment_history'] = [
            {'aggressor': 'CE', 'timestamp': _ts(-60), 'lots_sold': 1},
            {'aggressor': 'OPERATOR', 'timestamp': _ts(-30), 'lots_sold': 1},
        ]
        safety.check_whipsaw(sess)
        # OPERATOR is excluded from algo_history → no alternation scored
        assert sess.get('_whipsaw_score', 0) == 0

    @pytest.mark.sealed
    def test_c_ws_13_first_run_sets_idx_no_score(self, safety):
        sess = _session()
        # _whipsaw_last_checked_idx NOT set → first run
        sess['adjustment_history'] = [
            {'aggressor': 'CE', 'timestamp': _ts(-60), 'lots_sold': 1},
            {'aggressor': 'PE', 'timestamp': _ts(-30), 'lots_sold': 1},
        ]
        safety.check_whipsaw(sess)
        # Index set to current length — no alternation scored on first run
        assert sess.get('_whipsaw_last_checked_idx') == 2
        assert sess.get('_whipsaw_score', 0) == 0


# =============================================================================
# check_asymmetry
# =============================================================================

class TestCheckAsymmetry:

    @pytest.mark.sealed
    def test_c_as_1_both_zero(self, safety):
        sess = _session()
        sess['ce']['total_lots'] = 0
        sess['pe']['total_lots'] = 0
        events = safety.check_asymmetry(sess)
        assert events == []
        assert '_asymmetry_lot_reduction_pct' not in sess
        assert '_asymmetry_heavy_side' not in sess

    @pytest.mark.sealed
    def test_c_as_2_equal_sides_no_event(self, safety):
        sess = _session()
        sess['ce']['total_lots'] = 5
        sess['pe']['total_lots'] = 5
        events = safety.check_asymmetry(sess)
        assert events == []

    @pytest.mark.sealed
    def test_c_as_3_ratio_3to1_warning(self, safety):
        sess = _session()
        sess['ce']['total_lots'] = 3
        sess['pe']['total_lots'] = 1
        events = safety.check_asymmetry(sess)
        assert len(events) == 1
        assert events[0]['level'] == 'warning'
        assert events[0]['action'] == 'continue'
        # 3:1 tier clears 5:1 flags
        assert '_asymmetry_lot_reduction_pct' not in sess
        assert '_asymmetry_heavy_side' not in sess

    @pytest.mark.sealed
    def test_c_as_4_ratio_5to1_lot_reduction(self, safety):
        sess = _session()
        sess['ce']['total_lots'] = 5
        sess['pe']['total_lots'] = 1
        events = safety.check_asymmetry(sess)
        assert len(events) == 1
        assert events[0]['level'] == 'alert'
        assert sess['_asymmetry_lot_reduction_pct'] == 0.5
        assert sess['_asymmetry_heavy_side'] == 'ce'

    @pytest.mark.sealed
    def test_c_as_5_ratio_7to1_hard_block(self, safety):
        sess = _session()
        sess['ce']['total_lots'] = 7
        sess['pe']['total_lots'] = 1
        events = safety.check_asymmetry(sess)
        assert len(events) == 1
        assert events[0]['action'] == 'block_heavy_side_sells'
        assert events[0]['details']['heavy_side'] == 'ce'
        # Hard block clears 5:1 flags
        assert '_asymmetry_lot_reduction_pct' not in sess
        assert '_asymmetry_heavy_side' not in sess

    @pytest.mark.sealed
    def test_c_as_6_ratio_7to1_hard_block_disabled_falls_to_5to1(self, safety):
        sess = _session()
        sess['params']['asymmetry_7to1_hard_block'] = False
        sess['ce']['total_lots'] = 7
        sess['pe']['total_lots'] = 1
        events = safety.check_asymmetry(sess)
        assert len(events) == 1
        assert events[0]['action'] == 'warn'  # 5:1 tier
        assert '_asymmetry_lot_reduction_pct' in sess

    @pytest.mark.sealed
    def test_c_as_7_below_3to1_clears_flags(self, safety):
        sess = _session()
        sess['_asymmetry_lot_reduction_pct'] = 0.5
        sess['_asymmetry_heavy_side'] = 'ce'
        sess['ce']['total_lots'] = 2
        sess['pe']['total_lots'] = 1
        events = safety.check_asymmetry(sess)
        assert events == []
        assert '_asymmetry_lot_reduction_pct' not in sess
        assert '_asymmetry_heavy_side' not in sess

    @pytest.mark.sealed
    def test_c_as_8_pe_heavy_side(self, safety):
        sess = _session()
        sess['pe']['total_lots'] = 5
        sess['ce']['total_lots'] = 1
        events = safety.check_asymmetry(sess)
        e = events[0]
        assert e['details']['heavy_side'] == 'pe'


# =============================================================================
# check_near_expiry
# =============================================================================

class TestCheckNearExpiry:

    @pytest.mark.sealed
    def test_c_ne_1_far_away_no_events(self, safety):
        sess = _session()
        assert safety.check_near_expiry(sess, 120.0) == []

    @pytest.mark.sealed
    def test_c_ne_2_between_stop_and_60_info(self, safety):
        sess = _session()
        events = safety.check_near_expiry(sess, 30.0)
        assert len(events) == 1
        assert events[0]['action'] == 'continue'

    @pytest.mark.sealed
    def test_c_ne_3_exactly_at_stop_mins(self, safety):
        sess = _session()
        events = safety.check_near_expiry(sess, 15.0)  # == stop_adjustment_mins
        assert events[0]['action'] == 'stop_adjustments'

    @pytest.mark.sealed
    def test_c_ne_4_between_close_and_stop(self, safety):
        sess = _session()
        events = safety.check_near_expiry(sess, 10.0)
        assert events[0]['action'] == 'stop_adjustments'

    @pytest.mark.sealed
    def test_c_ne_5_exactly_at_close_mins(self, safety):
        sess = _session()
        events = safety.check_near_expiry(sess, 5.0)  # == auto_close_mins
        assert events[0]['action'] == 'auto_close'

    @pytest.mark.sealed
    def test_c_ne_6_below_close_mins(self, safety):
        sess = _session()
        events = safety.check_near_expiry(sess, 2.0)
        assert events[0]['action'] == 'auto_close'


# =============================================================================
# check_near_expiry_v2
# =============================================================================

class TestCheckNearExpiryV2:

    @pytest.mark.sealed
    def test_c_ne2_1_auto_close_returns_immediately(self, safety):
        sess = _session()
        events = safety.check_near_expiry_v2(sess, 3.0)
        assert events[0]['action'] == 'auto_close'
        assert len(events) == 1  # returns early

    @pytest.mark.sealed
    def test_c_ne2_2_stop_adjustments_returns_immediately(self, safety):
        sess = _session()
        events = safety.check_near_expiry_v2(sess, 10.0)
        assert events[0]['action'] == 'stop_adjustments'
        assert len(events) == 1

    @pytest.mark.sealed
    def test_c_ne2_3_wind_down_zone(self, safety):
        sess = _session()
        sess['params']['wind_down_hours_before_expiry'] = 2.0  # 120 min
        events = safety.check_near_expiry_v2(sess, 60.0)  # inside wind-down
        assert events[0]['action'] == 'wind_down'

    @pytest.mark.sealed
    def test_c_ne2_4_last_5pct_of_multi_dte(self, safety):
        sess = _session()
        sess['params']['total_dte_hours'] = 120  # 5 days
        sess['params']['wind_down_hours_before_expiry'] = 2.0
        # Last 5% = 120 * 0.05 = 6h = 360 min. Use 300 min to be inside 5% but outside wind-down (120 min)
        events = safety.check_near_expiry_v2(sess, 300.0)
        assert any(e['action'] == 'continue' for e in events)

    @pytest.mark.sealed
    def test_c_ne2_5_far_away_no_events(self, safety):
        sess = _session()
        sess['params']['total_dte_hours'] = 24
        events = safety.check_near_expiry_v2(sess, 1200.0)
        assert events == []


# =============================================================================
# check_pnl_guardrail
# =============================================================================

class TestCheckPnlGuardrail:

    @pytest.mark.sealed
    def test_c_pg_1_positive_pnl_no_events(self, safety):
        sess = _session()
        sess['unrealized_pnl'] = 100.0
        assert safety.check_pnl_guardrail(sess) == []

    @pytest.mark.sealed
    def test_c_pg_2_exactly_50pct_warning(self, safety):
        sess = _session()
        sess['unrealized_pnl'] = -500.0  # 50% of 1000
        events = safety.check_pnl_guardrail(sess)
        assert len(events) == 1
        assert events[0]['level'] == 'warning'

    @pytest.mark.sealed
    def test_c_pg_3_exactly_80pct_alert(self, safety):
        """Bug fix verified: ratio=0.8 must fire alert, not fall through gap."""
        sess = _session()
        sess['unrealized_pnl'] = -800.0  # exactly 80% of 1000
        events = safety.check_pnl_guardrail(sess)
        assert len(events) == 1
        assert events[0]['level'] == 'alert'
        assert events[0]['details']['ratio'] == 0.8

    @pytest.mark.sealed
    def test_c_pg_4_between_50_and_80_warning(self, safety):
        sess = _session()
        sess['unrealized_pnl'] = -650.0
        events = safety.check_pnl_guardrail(sess)
        assert events[0]['level'] == 'warning'

    @pytest.mark.sealed
    def test_c_pg_5_between_80_and_100_alert(self, safety):
        sess = _session()
        sess['unrealized_pnl'] = -900.0
        events = safety.check_pnl_guardrail(sess)
        assert events[0]['level'] == 'alert'

    @pytest.mark.sealed
    def test_c_pg_6_max_loss_zero_no_events(self, safety):
        sess = _session()
        sess['params']['max_loss_amount'] = 0
        sess['unrealized_pnl'] = -500.0
        assert safety.check_pnl_guardrail(sess) == []

    @pytest.mark.sealed
    def test_c_pg_7_at_100pct_no_guardrail_event(self, safety):
        """check_max_loss handles 100%+ — guardrail should not also fire."""
        sess = _session()
        sess['unrealized_pnl'] = -1000.0  # exactly at max_loss
        events = safety.check_pnl_guardrail(sess)
        # ratio == 1.0 → outside (0.5 <= ratio < 0.8) and (0.8 <= ratio < 1.0)
        assert events == []

    @pytest.mark.sealed
    def test_c_pg_8_includes_perp_hedge_pnl(self, safety):
        sess = _session()
        sess['unrealized_pnl'] = -400.0
        sess['perp_hedge'] = {'realized_pnl': -100.0, 'unrealized_pnl': 0.0}
        # total = -500 = 50% of 1000 → warning
        events = safety.check_pnl_guardrail(sess)
        assert len(events) == 1
        assert events[0]['level'] == 'warning'


# =============================================================================
# check_trailing_stop
# =============================================================================

class TestCheckTrailingStop:

    @pytest.mark.sealed
    def test_c_ts_1_disabled(self, safety):
        sess = _session()
        sess['params']['trailing_stop_pct'] = 0
        sess['peak_pnl'] = 100.0
        sess['unrealized_pnl'] = 50.0
        assert safety.check_trailing_stop(sess) == []

    @pytest.mark.sealed
    def test_c_ts_2_no_peak(self, safety):
        sess = _session()
        sess['peak_pnl'] = 0.0
        assert safety.check_trailing_stop(sess) == []

    @pytest.mark.sealed
    def test_c_ts_3_above_floor_no_event(self, safety):
        sess = _session()
        sess['peak_pnl'] = 100.0
        sess['unrealized_pnl'] = 60.0  # floor = 50, current = 60 > 50
        assert safety.check_trailing_stop(sess) == []

    @pytest.mark.sealed
    def test_c_ts_4_below_floor_stop_adjustments(self, safety):
        sess = _session()
        sess['peak_pnl'] = 100.0
        sess['unrealized_pnl'] = 40.0  # floor = 50, current = 40 < 50
        events = safety.check_trailing_stop(sess)
        assert len(events) == 1
        assert events[0]['action'] == 'stop_adjustments'

    @pytest.mark.sealed
    def test_c_ts_5_exactly_at_floor_no_event(self, safety):
        """current < threshold (strict) — at floor is OK."""
        sess = _session()
        sess['peak_pnl'] = 100.0
        sess['unrealized_pnl'] = 50.0  # current == floor → not below
        assert safety.check_trailing_stop(sess) == []

    @pytest.mark.sealed
    def test_c_ts_6_perp_hedge_included(self, safety):
        sess = _session()
        sess['peak_pnl'] = 100.0
        sess['unrealized_pnl'] = 60.0
        sess['perp_hedge'] = {'realized_pnl': -20.0, 'unrealized_pnl': 0.0}
        # current = 60 - 20 = 40 < floor 50 → triggers
        events = safety.check_trailing_stop(sess)
        assert events[0]['action'] == 'stop_adjustments'


# =============================================================================
# check_margin
# =============================================================================

class TestCheckMargin:

    @pytest.mark.sealed
    def test_c_mg_1_under_combined_cap(self, safety):
        sess = _session()
        sess['ce']['total_lots'] = 5
        sess['pe']['total_lots'] = 5
        # combined=10, cap=15 (10*1.5)
        assert safety.check_margin(sess) == []

    @pytest.mark.sealed
    def test_c_mg_2_over_combined_cap(self, safety):
        sess = _session()
        sess['ce']['total_lots'] = 10
        sess['pe']['total_lots'] = 6
        # combined=16 > 15
        events = safety.check_margin(sess)
        assert len(events) == 1
        assert events[0]['type'] == 'margin_warning'
        assert events[0]['action'] == 'warn'


# =============================================================================
# check_lot_velocity
# =============================================================================

class TestCheckLotVelocity:

    @pytest.mark.sealed
    def test_c_lv_1_disabled_no_events(self, safety):
        sess = _session()
        sess['params']['lot_velocity_enabled'] = False
        assert safety.check_lot_velocity(sess) == []

    @pytest.mark.sealed
    def test_c_lv_2_under_limit_no_events(self, safety):
        sess = _session()
        sess['adjustment_history'] = [
            {'aggressor': 'CE', 'timestamp': _ts(-60), 'lots_sold': 3},
        ]
        assert safety.check_lot_velocity(sess) == []

    @pytest.mark.sealed
    def test_c_lv_3_at_limit_stop_adjustments(self, safety):
        sess = _session()
        sess['adjustment_history'] = [
            {'aggressor': 'CE', 'timestamp': _ts(-60), 'lots_sold': 10},
        ]
        events = safety.check_lot_velocity(sess)
        assert events[0]['action'] == 'stop_adjustments'

    @pytest.mark.sealed
    def test_c_lv_4_at_80pct_warning(self, safety):
        sess = _session()
        sess['adjustment_history'] = [
            {'aggressor': 'CE', 'timestamp': _ts(-60), 'lots_sold': 8},
        ]
        events = safety.check_lot_velocity(sess)
        assert events[0]['action'] == 'continue'
        assert events[0]['level'] == 'warning'

    @pytest.mark.sealed
    def test_c_lv_5_operator_excluded(self, safety):
        sess = _session()
        sess['adjustment_history'] = [
            {'aggressor': 'OPERATOR', 'timestamp': _ts(-60), 'lots_sold': 10},
        ]
        # OPERATOR excluded → 0 lots counted
        assert safety.check_lot_velocity(sess) == []

    @pytest.mark.sealed
    def test_c_lv_6_outside_window_excluded(self, safety):
        sess = _session()
        sess['adjustment_history'] = [
            {'aggressor': 'CE', 'timestamp': _ts(-3600), 'lots_sold': 10},  # 1hr ago, outside 30min window
        ]
        assert safety.check_lot_velocity(sess) == []


# =============================================================================
# check_max_adjustments
# =============================================================================

class TestCheckMaxAdjustments:

    @pytest.mark.sealed
    def test_c_ma_1_under_max_no_events(self, safety):
        sess = _session()
        sess['adjustment_count'] = 5
        assert safety.check_max_adjustments(sess) == []

    @pytest.mark.sealed
    def test_c_ma_2_approaching_90pct_warning(self, safety):
        sess = _session()
        sess['adjustment_count'] = 18  # 90% of 20
        events = safety.check_max_adjustments(sess)
        assert events[0]['action'] == 'continue'
        assert events[0]['level'] == 'warning'

    @pytest.mark.sealed
    def test_c_ma_3_at_max_pause_and_flag_set(self, safety):
        sess = _session()
        sess['adjustment_count'] = 20  # == max_adjustments
        events = safety.check_max_adjustments(sess)
        assert events[0]['action'] == 'pause'
        assert sess.get('_max_adj_paused') is True

    @pytest.mark.sealed
    def test_c_ma_4_auto_resume_when_limit_raised(self, safety):
        sess = _session()
        sess['_max_adj_paused'] = True
        sess['adjustment_count'] = 20
        sess['params']['max_adjustments'] = 30  # raised via hot-reload
        events = safety.check_max_adjustments(sess)
        assert events[0]['action'] == 'resume'
        assert '_max_adj_paused' not in sess

    @pytest.mark.sealed
    def test_c_ma_5_flag_set_still_at_max_no_resume(self, safety):
        sess = _session()
        sess['_max_adj_paused'] = True
        sess['adjustment_count'] = 20  # still at max — no change
        events = safety.check_max_adjustments(sess)
        # Flag set + count >= max → not auto-resume, fires pause again
        assert events[0]['action'] == 'pause'


# =============================================================================
# run_all_checks
# =============================================================================

class TestRunAllChecks:

    @pytest.mark.sealed
    def test_c_rac_1_no_minutes_skips_near_expiry(self, safety):
        sess = _session()
        events = safety.run_all_checks(sess, minutes_to_expiry=None)
        near_expiry = [e for e in events if e['type'] == 'near_expiry']
        assert near_expiry == []

    @pytest.mark.sealed
    def test_c_rac_2_0dte_uses_v1(self, safety):
        """0DTE → v1 near-expiry (no wind_down action)."""
        sess = _session()
        sess['params']['dte_category'] = '0DTE'
        sess['params']['total_dte_hours'] = 8
        events = safety.run_all_checks(sess, minutes_to_expiry=30.0)
        near = [e for e in events if e['type'] == 'near_expiry']
        # v1 at 30 min → info continue
        assert near and near[0]['action'] == 'continue'
        assert not any(e['action'] == 'wind_down' for e in events)

    @pytest.mark.sealed
    def test_c_rac_3_multi_dte_uses_v2(self, safety):
        """Multi-DTE (> 36h) uses v2 which can return wind_down."""
        sess = _session()
        sess['params']['dte_category'] = '5DTE'
        sess['params']['total_dte_hours'] = 120
        sess['params']['wind_down_hours_before_expiry'] = 2.0  # 120 min threshold
        events = safety.run_all_checks(sess, minutes_to_expiry=60.0)
        assert any(e['action'] == 'wind_down' for e in events)

    @pytest.mark.sealed
    def test_c_rac_4_healthy_session_no_blocking(self, safety):
        sess = _session()
        events = safety.run_all_checks(sess)
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        assert not should_block_adjustment(events)


# =============================================================================
# should_block_adjustment
# =============================================================================

class TestShouldBlockAdjustment:

    @pytest.mark.sealed
    def test_c_sba_1_stop_blocks(self):
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        assert should_block_adjustment([{'action': 'stop'}]) is True

    @pytest.mark.sealed
    def test_c_sba_2_auto_close_blocks(self):
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        assert should_block_adjustment([{'action': 'auto_close'}]) is True

    @pytest.mark.sealed
    def test_c_sba_3_stop_adjustments_blocks(self):
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        assert should_block_adjustment([{'action': 'stop_adjustments'}]) is True

    @pytest.mark.sealed
    def test_c_sba_4_non_blocking_actions(self):
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        for action in ('continue', 'warn', 'pause', 'wind_down', 'resume'):
            assert should_block_adjustment([{'action': action}]) is False, action

    @pytest.mark.sealed
    def test_c_sba_5_block_heavy_side_sells_not_a_full_block(self):
        """block_heavy_side_sells is per-side — not a full adjustment block."""
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        assert should_block_adjustment([{'action': 'block_heavy_side_sells'}]) is False

    @pytest.mark.sealed
    def test_c_sba_6_empty_list(self):
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        assert should_block_adjustment([]) is False


# =============================================================================
# get_block_action
# =============================================================================

class TestGetBlockAction:

    @pytest.mark.sealed
    def test_c_gba_1_auto_close_wins_over_stop_adjustments(self):
        from webui.backend.routes.mmm.mmm_safety import get_block_action
        events = [
            {'action': 'stop_adjustments', 'message': 'low'},
            {'action': 'auto_close', 'message': 'CRITICAL'},
        ]
        msg, action_type = get_block_action(events)
        assert action_type == 'auto_close'
        assert 'CRITICAL' in msg

    @pytest.mark.sealed
    def test_c_gba_2_only_stop_adjustments(self):
        from webui.backend.routes.mmm.mmm_safety import get_block_action
        events = [{'action': 'stop_adjustments', 'message': 'blocked'}]
        msg, action_type = get_block_action(events)
        assert action_type == 'stop_adjustments'

    @pytest.mark.sealed
    def test_c_gba_3_auto_close_only(self):
        from webui.backend.routes.mmm.mmm_safety import get_block_action
        events = [{'action': 'auto_close', 'message': 'closing'}]
        msg, action_type = get_block_action(events)
        assert action_type == 'auto_close'


# =============================================================================
# should_pause
# =============================================================================

class TestShouldPause:

    @pytest.mark.sealed
    def test_c_sp_1_pause_action(self):
        from webui.backend.routes.mmm.mmm_safety import should_pause
        ok, reason = should_pause([{'action': 'pause', 'message': 'max adj reached'}])
        assert ok is True
        assert 'max adj' in reason

    @pytest.mark.sealed
    def test_c_sp_2_stop_action_not_pause(self):
        from webui.backend.routes.mmm.mmm_safety import should_pause
        ok, _ = should_pause([{'action': 'stop'}])
        assert ok is False

    @pytest.mark.sealed
    def test_c_sp_3_empty_list(self):
        from webui.backend.routes.mmm.mmm_safety import should_pause
        ok, reason = should_pause([])
        assert ok is False
        assert reason == ''


# =============================================================================
# update_peak_pnl
# =============================================================================

class TestUpdatePeakPnl:

    @pytest.mark.sealed
    def test_c_upp_1_new_high_sets_peak(self):
        from webui.backend.routes.mmm.mmm_safety import update_peak_pnl
        sess = {'peak_pnl': 50.0}
        update_peak_pnl(sess, 100.0)
        assert sess['peak_pnl'] == 100.0
        assert '_peak_pnl_set_at' in sess

    @pytest.mark.sealed
    def test_c_upp_2_zero_pnl_no_peak_change(self):
        from webui.backend.routes.mmm.mmm_safety import update_peak_pnl
        sess = {'peak_pnl': 0.0}
        update_peak_pnl(sess, 0.0)
        assert sess['peak_pnl'] == 0.0

    @pytest.mark.sealed
    def test_c_upp_3_below_peak_decays_but_stays_below_old_peak(self):
        from webui.backend.routes.mmm.mmm_safety import update_peak_pnl
        sess = {'peak_pnl': 100.0}
        update_peak_pnl(sess, 80.0)
        # Decayed peak should be <= original peak
        assert sess['peak_pnl'] <= 100.0
        assert sess['peak_pnl'] >= 0.0


# =============================================================================
# reset_peak_pnl_on_reversal
# =============================================================================

class TestResetPeakPnlOnReversal:

    @pytest.mark.sealed
    def test_c_rpr_1_positive_pnl(self):
        from webui.backend.routes.mmm.mmm_safety import reset_peak_pnl_on_reversal
        sess = {'peak_pnl': 200.0}
        reset_peak_pnl_on_reversal(sess, 50.0)
        assert sess['peak_pnl'] == 50.0

    @pytest.mark.sealed
    def test_c_rpr_2_negative_pnl_clamped_to_zero(self):
        from webui.backend.routes.mmm.mmm_safety import reset_peak_pnl_on_reversal
        sess = {'peak_pnl': 200.0}
        reset_peak_pnl_on_reversal(sess, -100.0)
        assert sess['peak_pnl'] == 0.0
