"""
Test MMM DTE Presets — Multi-expiry parameter profiles.

Tests:
  - Preset application and override semantics
  - Aggregate PnL safety check
  - Chain liquidity gate
  - DTE hours computation
  - DTE category inference
"""

import pytest
from copy import deepcopy


class TestApplyPreset:
    """DTE preset application: DEFAULT < preset < user."""

    def test_apply_0dte_preset(self):
        from webui.backend.routes.mmm.mmm_dte_presets import apply_preset, PRESET_0DTE
        params = {'expiry': '12032026'}
        result = apply_preset(params, '0DTE')
        assert result['dte_category'] == '0DTE'
        assert result['adjustment_interval'] == PRESET_0DTE['adjustment_interval']
        assert result['expiry'] == '12032026'  # User param preserved

    def test_apply_5dte_preset(self):
        from webui.backend.routes.mmm.mmm_dte_presets import apply_preset, PRESET_5DTE
        params = {'expiry': '17032026'}
        result = apply_preset(params, '5DTE')
        assert result['dte_category'] == '5DTE'
        assert result['adjustment_interval'] == PRESET_5DTE['adjustment_interval']

    def test_user_params_override_preset(self):
        from webui.backend.routes.mmm.mmm_dte_presets import apply_preset
        params = {'adjustment_interval': 600}  # User override
        result = apply_preset(params, '0DTE')
        assert result['adjustment_interval'] == 600  # User wins over preset's 300

    def test_unknown_preset_returns_params_unchanged(self):
        from webui.backend.routes.mmm.mmm_dte_presets import apply_preset
        params = {'expiry': '12032026', 'adjustment_interval': 300}
        result = apply_preset(params, 'UNKNOWN_DTE')
        assert result == params

    def test_dte_category_always_set(self):
        from webui.backend.routes.mmm.mmm_dte_presets import apply_preset
        params = {'dte_category': 'wrong'}
        result = apply_preset(params, '5DTE')
        assert result['dte_category'] == '5DTE'  # Preset category wins


class TestListPresets:
    """List available presets."""

    def test_list_presets_returns_all(self):
        from webui.backend.routes.mmm.mmm_dte_presets import list_presets
        presets = list_presets()
        names = [p['name'] for p in presets]
        assert '0DTE' in names
        assert '5DTE' in names

    def test_preset_has_required_keys(self):
        from webui.backend.routes.mmm.mmm_dte_presets import list_presets
        for p in list_presets():
            assert 'name' in p
            assert 'adjustment_interval' in p
            assert 'max_loss_amount' in p


class TestComputeTotalDTEHours:
    """Total DTE hours computation."""

    def test_future_expiry(self):
        from webui.backend.routes.mmm.mmm_dte_presets import compute_total_dte_hours
        from datetime import datetime, timezone, timedelta
        future = datetime.now(timezone.utc) + timedelta(days=5)
        expiry_str = future.strftime('%d%m%Y')
        hours = compute_total_dte_hours(expiry_str)
        assert 100 < hours < 140  # ~120 hours for 5 days, rough range

    def test_past_expiry_negative(self):
        from webui.backend.routes.mmm.mmm_dte_presets import compute_total_dte_hours
        hours = compute_total_dte_hours('01012020')
        assert hours < 0

    def test_invalid_format_returns_zero(self):
        from webui.backend.routes.mmm.mmm_dte_presets import compute_total_dte_hours
        hours = compute_total_dte_hours('INVALID')
        assert hours == 0.0


class TestInferDTECategory:
    """DTE category inference from hours."""

    def test_short_dte_infers_0dte(self):
        from webui.backend.routes.mmm.mmm_dte_presets import infer_dte_category
        assert infer_dte_category(12) == '0DTE'
        assert infer_dte_category(36) == '0DTE'  # <=1.5 days

    def test_long_dte_infers_5dte(self):
        from webui.backend.routes.mmm.mmm_dte_presets import infer_dte_category
        assert infer_dte_category(37) == '5DTE'
        assert infer_dte_category(120) == '5DTE'


class TestCheckAggregatePnL:
    """Aggregate PnL safety check across multiple sessions."""

    def test_no_sessions_safe(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        result = check_aggregate_pnl([], global_max_loss=50000)
        assert result['safe'] is True
        assert result['level'] == 'ok'
        assert result['combined_pnl'] == 0

    def test_profitable_sessions_safe(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        sessions = [
            {'realized_pnl': 100, 'unrealized_pnl': 200},
            {'realized_pnl': 50, 'unrealized_pnl': -30},
        ]
        result = check_aggregate_pnl(sessions, global_max_loss=50000)
        assert result['safe'] is True
        assert result['combined_pnl'] == 320

    def test_loss_at_50pct_warning(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        sessions = [
            {'realized_pnl': -15000, 'unrealized_pnl': -10000},
        ]
        result = check_aggregate_pnl(sessions, global_max_loss=50000)
        assert result['safe'] is True
        assert result['level'] == 'warning'

    def test_loss_at_80pct_critical(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        sessions = [
            {'realized_pnl': -30000, 'unrealized_pnl': -11000},
        ]
        result = check_aggregate_pnl(sessions, global_max_loss=50000)
        assert result['safe'] is True
        assert result['level'] == 'critical'

    def test_loss_at_100pct_breach(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        sessions = [
            {'realized_pnl': -30000, 'unrealized_pnl': -20000},
        ]
        result = check_aggregate_pnl(sessions, global_max_loss=50000)
        assert result['safe'] is False
        assert result['level'] == 'breach'

    def test_manual_reduction_pnl_included(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        sessions = [
            {'realized_pnl': -30000, 'unrealized_pnl': -15000, 'manual_reduction_pnl': -6000},
        ]
        result = check_aggregate_pnl(sessions, global_max_loss=50000)
        assert result['combined_pnl'] == -51000
        assert result['safe'] is False


class TestCheckChainLiquidity:
    """Chain liquidity gate."""

    def _make_chain(self, ce_count=5, pe_count=5, bid=10, bid_size=10):
        """Build a mock chain in get_full_chain nested format."""
        chain = []
        for i in range(max(ce_count, pe_count)):
            entry = {'strike': 80000 + i * 500}
            if i < ce_count:
                entry['call'] = {'bid': bid, 'bid_size': bid_size}
            else:
                entry['call'] = {'bid': 0, 'bid_size': 0}
            if i < pe_count:
                entry['put'] = {'bid': bid, 'bid_size': bid_size}
            else:
                entry['put'] = {'bid': 0, 'bid_size': 0}
            chain.append(entry)
        return chain

    def test_liquid_chain_ok(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_chain_liquidity
        chain = self._make_chain(ce_count=5, pe_count=5)
        result = check_chain_liquidity(chain)
        assert result['liquid'] is True
        assert result['ce_liquid_strikes'] == 5
        assert result['pe_liquid_strikes'] == 5

    def test_illiquid_chain_fails(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_chain_liquidity
        chain = self._make_chain(ce_count=1, pe_count=1)
        result = check_chain_liquidity(chain)
        assert result['liquid'] is False

    def test_low_bid_size_filtered(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_chain_liquidity
        chain = self._make_chain(ce_count=5, pe_count=5, bid_size=2)
        result = check_chain_liquidity(chain, min_liquidity_lots=5)
        assert result['liquid'] is False

    def test_zero_bid_filtered(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_chain_liquidity
        chain = self._make_chain(ce_count=5, pe_count=5, bid=0)
        result = check_chain_liquidity(chain)
        assert result['liquid'] is False

    def test_empty_chain(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_chain_liquidity
        result = check_chain_liquidity([])
        assert result['liquid'] is False

    def test_mixed_liquidity(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_chain_liquidity
        chain = self._make_chain(ce_count=3, pe_count=1)
        result = check_chain_liquidity(chain)
        assert result['liquid'] is False  # PE only has 1


class TestNearExpiryV2:
    """DTE-aware near-expiry safety check (v2)."""

    def _make_session(self, **param_overrides):
        params = {
            'stop_adjustment_mins': 30,
            'auto_close_mins': 10,
            'total_dte_hours': 120,  # 5 days
            'wind_down_hours_before_expiry': 12,
            'dte_category': '5DTE',
        }
        params.update(param_overrides)
        return {
            'session_id': 'test-dte-001',
            'strategy_status': 'RUNNING',
            'params': params,
        }

    def test_auto_close_at_threshold(self):
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        safety = MMMSafety()
        session = self._make_session()
        events = safety.check_near_expiry_v2(session, minutes_to_expiry=5)
        assert len(events) == 1
        assert events[0]['action'] == 'auto_close'

    def test_stop_adjustments_at_threshold(self):
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        safety = MMMSafety()
        session = self._make_session()
        events = safety.check_near_expiry_v2(session, minutes_to_expiry=20)
        assert len(events) == 1
        assert events[0]['action'] == 'stop_adjustments'

    def test_wind_down_zone(self):
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        safety = MMMSafety()
        session = self._make_session()
        # 12 hours = 720 min, test at 600 min (inside wind-down zone)
        events = safety.check_near_expiry_v2(session, minutes_to_expiry=600)
        assert len(events) == 1
        assert events[0]['action'] == 'wind_down'

    def test_percentage_warning_for_long_dte(self):
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        safety = MMMSafety()
        # 120h DTE, 5% = 360 min; wind-down is 12h=720min
        # Test at 200 min (inside 5% but also inside wind-down, so wind-down wins)
        # Need to test outside wind-down zone but inside 5% of total DTE
        # For 120h, 5% = 360min. Wind-down = 720min.
        # Since wind-down > 5%, the 5% check is always subsumed. Need bigger DTE.
        session = self._make_session(total_dte_hours=480, wind_down_hours_before_expiry=12)
        # 480h DTE, 5% = 1440 min = 24h. Wind-down = 12h = 720min.
        # Test at 1000 min (inside 5% = 1440, outside wind-down = 720)
        events = safety.check_near_expiry_v2(session, minutes_to_expiry=1000)
        assert len(events) == 1
        assert events[0]['action'] == 'continue'
        assert '5%' in events[0]['message']

    def test_far_from_expiry_no_events(self):
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        safety = MMMSafety()
        session = self._make_session()
        events = safety.check_near_expiry_v2(session, minutes_to_expiry=5000)
        assert len(events) == 0

    def test_v2_dispatched_for_multi_dte(self):
        """run_all_checks should dispatch v2 for multi-DTE sessions."""
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        safety = MMMSafety()
        session = self._make_session()
        # Add required fields for other safety checks
        session['ce'] = {'total_lots': 5, 'active_lots': 5}
        session['pe'] = {'total_lots': 5, 'active_lots': 5}
        session['adjustment_count'] = 0
        session['reversal_count'] = 0
        session['realized_pnl'] = 0
        session['unrealized_pnl'] = 0
        session['total_premium_collected'] = 0
        session['peak_pnl'] = 0
        session['adjustment_history'] = []
        session['params'].update({
            'max_lots_per_side': 50,
            'max_adjustments': 20,
            'max_loss_amount': 5000,
        })
        # inside wind-down zone
        events = safety.run_all_checks(session, minutes_to_expiry=600)
        near_expiry = [e for e in events if e['type'] == 'near_expiry']
        assert len(near_expiry) >= 1
        assert near_expiry[0]['action'] == 'wind_down'
