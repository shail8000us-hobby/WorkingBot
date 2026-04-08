"""
MMMX Phase 1 Unit Tests

Covers: state, config, storage, engine math.
Exit criteria per MMMX_IMPLEMENTATION_PLAN.md Section 4 (Phase 1):
  - Create session via API → DRAFT with validated params.
  - close_at_dte=6 rejected; close_at_dte=7 accepted.
  - Start/stop monitor: generation increments; stale monitor self-stops within one beat.
  - Two concurrent sessions run without colliding registries.
  - Engine unit tests: P&L, fees, hard stop recalc, BS pricing, lot imbalance, DTE.
  - MMM isolation scan: no imports from routes.mmm.*.
"""

import math
import os
import sys
import tempfile
import threading
import time
import pytest

# ── Ensure mmmx is importable ─────────────────────────────────────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstants:
    def test_lot_size_btc(self):
        from webui.backend.routes.mmmx.mmmx_constants import LOT_SIZE_BTC
        assert LOT_SIZE_BTC == 0.001

    def test_close_at_dte_hard_min(self):
        from webui.backend.routes.mmmx.mmmx_constants import CLOSE_AT_DTE_HARD_MIN
        assert CLOSE_AT_DTE_HARD_MIN == 7

    def test_schema_version(self):
        from webui.backend.routes.mmmx.mmmx_constants import SCHEMA_VERSION
        assert SCHEMA_VERSION == 1

    def test_fee_rates(self):
        from webui.backend.routes.mmmx.mmmx_constants import FEE_RATE_MAKER, FEE_RATE_TAKER
        assert FEE_RATE_MAKER == 0.0002
        assert FEE_RATE_TAKER == 0.0005

    def test_no_mmm_imports(self):
        """MMM isolation: mmmx_constants must not import from routes.mmm.*"""
        import importlib, inspect
        import webui.backend.routes.mmmx.mmmx_constants as mod
        src = inspect.getsource(mod)
        assert 'routes.mmm' not in src, "mmmx_constants imports from routes.mmm — isolation violation"


# ═══════════════════════════════════════════════════════════════════════════════
# Config / Param Validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfig:
    def test_close_at_dte_6_rejected(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params, ConfigError
        with pytest.raises(ConfigError, match='close_at_dte'):
            validate_params({'close_at_dte': 6})

    def test_close_at_dte_7_accepted(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params
        validate_params({'close_at_dte': 7})  # should not raise

    def test_close_at_dte_0_rejected(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params, ConfigError
        with pytest.raises(ConfigError):
            validate_params({'close_at_dte': 0})

    def test_hard_stop_multiplier_range(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params, ConfigError
        validate_params({'hard_stop_multiplier': 1.0})
        validate_params({'hard_stop_multiplier': 5.0})
        with pytest.raises(ConfigError):
            validate_params({'hard_stop_multiplier': 0.5})
        with pytest.raises(ConfigError):
            validate_params({'hard_stop_multiplier': 6.0})

    def test_dte_range_cross_field(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params, ConfigError
        with pytest.raises(ConfigError, match='entry_dte_min'):
            validate_params({'entry_dte_min': 45, 'entry_dte_max': 20})

    def test_near_itm_vs_emergency_delta(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params, ConfigError
        with pytest.raises(ConfigError, match='near_itm_delta'):
            validate_params({'near_itm_delta': 0.70, 'emergency_delta': 0.70})

    def test_profit_booking_targets_valid(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params
        validate_params({'profit_booking_targets': [10, 25, 50]})

    def test_profit_booking_targets_invalid(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params, ConfigError
        with pytest.raises(ConfigError):
            validate_params({'profit_booking_targets': [0, 10]})   # 0 not in (0,100]
        with pytest.raises(ConfigError):
            validate_params({'profit_booking_targets': 'bad'})     # not a list

    def test_hot_reload_rejects_entry_gate_param(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_hot_reload_patch, ConfigError
        with pytest.raises(ConfigError, match='hot-reloadable'):
            validate_hot_reload_patch({'entry_dte_min': 15})

    def test_hot_reload_accepts_allowed_param(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_hot_reload_patch
        validate_hot_reload_patch({'close_at_dte': 7})  # should not raise

    def test_diff_params(self):
        from webui.backend.routes.mmmx.mmmx_config import diff_params
        old = {'a': 1, 'b': 2, 'c': 3}
        new = {'a': 1, 'b': 99, 'c': 3, 'd': 4}
        diff = diff_params(old, new)
        assert 'a' not in diff
        assert 'c' not in diff
        assert diff['b'] == {'old': 2, 'new': 99}
        assert diff['d'] == {'old': None, 'new': 4}


# ═══════════════════════════════════════════════════════════════════════════════
# State — Session Factory
# ═══════════════════════════════════════════════════════════════════════════════

class TestState:
    def test_create_session_defaults(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        from webui.backend.routes.mmmx.mmmx_constants import SCHEMA_VERSION, SessionStatus
        s = create_session()
        assert s['_schema_version'] == SCHEMA_VERSION
        assert s['status'] == SessionStatus.DRAFT
        assert s['tranches'] == []
        assert s['hedges'] == []
        assert s['params']['close_at_dte'] == 7

    def test_create_session_param_override(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        s = create_session(params={'close_at_dte': 10, 'hard_stop_multiplier': 3.0})
        assert s['params']['close_at_dte'] == 10
        assert s['params']['hard_stop_multiplier'] == 3.0

    def test_session_has_uuid(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        s1 = create_session()
        s2 = create_session()
        assert s1['session_id'] != s2['session_id']
        assert len(s1['session_id']) == 36  # UUID4 length

    def test_validate_schema_rejects_wrong_version(self):
        from webui.backend.routes.mmmx.mmmx_state import validate_schema, create_session
        s = create_session()
        s['_schema_version'] = 999
        with pytest.raises(ValueError, match='schema version'):
            validate_schema(s)

    def test_validate_schema_accepts_current(self):
        from webui.backend.routes.mmmx.mmmx_state import validate_schema, create_session
        validate_schema(create_session())  # should not raise

    def test_transition_status_legal(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session, transition_status
        s = create_session()
        transition_status(s, 'GATES_PASSED')
        assert s['status'] == 'GATES_PASSED'
        transition_status(s, 'RUNNING')
        assert s['status'] == 'RUNNING'
        transition_status(s, 'PAUSED')
        assert s['status'] == 'PAUSED'

    def test_transition_status_illegal_raises(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session, transition_status
        s = create_session()
        with pytest.raises(ValueError, match='Illegal'):
            transition_status(s, 'COMPLETE')  # DRAFT → COMPLETE is not legal

    def test_apply_session_defaults_idempotent(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session, apply_session_defaults
        s = create_session()
        apply_session_defaults(s)
        apply_session_defaults(s)  # calling twice must not corrupt
        assert s['_whipsaw_score'] == 0
        assert s['fees_tracking']['fee_rate_maker'] == 0.0002


# ═══════════════════════════════════════════════════════════════════════════════
# Storage
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_storage():
    """Create a fresh MMMXStorage in a temp DB file."""
    from webui.backend.routes.mmmx.mmmx_storage import MMMXStorage
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    storage = MMMXStorage(db_path=db_path)
    yield storage
    os.unlink(db_path)


class TestStorage:
    def test_save_and_load(self, tmp_storage):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        s = create_session()
        tmp_storage.save_session(s, expected_gen=None)
        loaded = tmp_storage.load_session(s['session_id'])
        assert loaded['session_id'] == s['session_id']
        assert loaded['status'] == 'DRAFT'

    def test_load_nonexistent_returns_none(self, tmp_storage):
        assert tmp_storage.load_session('nonexistent-id') is None

    def test_list_sessions(self, tmp_storage):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        s1 = create_session()
        s2 = create_session()
        tmp_storage.save_session(s1)
        tmp_storage.save_session(s2)
        sessions = tmp_storage.list_sessions()
        ids = [s['session_id'] for s in sessions]
        assert s1['session_id'] in ids
        assert s2['session_id'] in ids

    def test_bump_generation_increments(self, tmp_storage):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        s = create_session()
        tmp_storage.save_session(s)
        g1 = tmp_storage.bump_generation(s['session_id'])
        g2 = tmp_storage.bump_generation(s['session_id'])
        assert g2 == g1 + 1

    def test_save_with_correct_gen_succeeds(self, tmp_storage):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        s = create_session()
        tmp_storage.save_session(s)
        gen = tmp_storage.bump_generation(s['session_id'])
        s['beat_number'] = 1
        tmp_storage.save_session(s, expected_gen=gen)  # should not raise

    def test_save_with_wrong_gen_raises(self, tmp_storage):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        from webui.backend.routes.mmmx.mmmx_storage import GenerationConflict
        s = create_session()
        tmp_storage.save_session(s)
        tmp_storage.bump_generation(s['session_id'])  # gen is now 1
        with pytest.raises(GenerationConflict):
            tmp_storage.save_session(s, expected_gen=0)  # wrong gen

    def test_two_sessions_independent_generations(self, tmp_storage):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        s1 = create_session()
        s2 = create_session()
        tmp_storage.save_session(s1)
        tmp_storage.save_session(s2)
        tmp_storage.bump_generation(s1['session_id'])
        tmp_storage.bump_generation(s1['session_id'])
        g1 = tmp_storage.get_generation(s1['session_id'])
        g2 = tmp_storage.get_generation(s2['session_id'])
        assert g1 == 2
        assert g2 == 0  # s2 untouched

    def test_active_sessions_restore(self, tmp_storage):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        s = create_session()
        s['status'] = 'RUNNING'
        tmp_storage.save_session(s)
        active = tmp_storage.list_active_sessions()
        assert any(a['session_id'] == s['session_id'] for a in active)

    def test_param_audit_append_and_read(self, tmp_storage):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        s = create_session()
        tmp_storage.save_session(s)
        diff = {'close_at_dte': {'old': 7, 'new': 10}}
        tmp_storage.append_param_audit(s['session_id'], diff)
        history = tmp_storage.get_param_audit(s['session_id'])
        assert len(history) == 1
        assert history[0]['diff'] == diff


# ═══════════════════════════════════════════════════════════════════════════════
# Engine — Pure Math
# ═══════════════════════════════════════════════════════════════════════════════

class TestEngine:
    LOT_SIZE = 0.001

    def test_compute_position_pnl_short_profit(self):
        from webui.backend.routes.mmmx.mmmx_engine import compute_position_pnl
        # Premium decayed 100 → 60, 10 lots SHORT → profit
        pnl = compute_position_pnl(100.0, 60.0, 10, 'SHORT')
        expected = (100.0 - 60.0) * 10 * self.LOT_SIZE
        assert abs(pnl - expected) < 1e-8

    def test_compute_position_pnl_short_loss(self):
        from webui.backend.routes.mmmx.mmmx_engine import compute_position_pnl
        pnl = compute_position_pnl(100.0, 150.0, 10, 'SHORT')
        expected = (100.0 - 150.0) * 10 * self.LOT_SIZE
        assert abs(pnl - expected) < 1e-8

    def test_compute_position_pnl_long_profit(self):
        from webui.backend.routes.mmmx.mmmx_engine import compute_position_pnl
        pnl = compute_position_pnl(40.0, 80.0, 10, 'LONG')
        expected = (80.0 - 40.0) * 10 * self.LOT_SIZE
        assert abs(pnl - expected) < 1e-8

    def test_compute_position_pnl_raises_on_none(self):
        from webui.backend.routes.mmmx.mmmx_engine import compute_position_pnl, PnLIncompleteError
        with pytest.raises(PnLIncompleteError):
            compute_position_pnl(100.0, None, 10)

    def test_compute_fee_taker(self):
        from webui.backend.routes.mmmx.mmmx_engine import compute_fee
        fee = compute_fee(100.0, 10, is_taker=True)
        expected = 100.0 * 10 * self.LOT_SIZE * 0.0005
        assert abs(fee - expected) < 1e-10

    def test_compute_fee_maker(self):
        from webui.backend.routes.mmmx.mmmx_engine import compute_fee
        fee = compute_fee(100.0, 10, is_taker=False)
        expected = 100.0 * 10 * self.LOT_SIZE * 0.0002
        assert abs(fee - expected) < 1e-10

    def test_recalc_hard_stop(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        from webui.backend.routes.mmmx.mmmx_engine import recalc_hard_stop
        s = create_session()
        s['total_premium_collected'] = 500.0
        s['params']['hard_stop_multiplier'] = 2.0
        hs = recalc_hard_stop(s)
        assert abs(hs - 1000.0) < 1e-6

    def test_recalc_hard_stop_scales(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        from webui.backend.routes.mmmx.mmmx_engine import recalc_hard_stop
        s = create_session()
        s['total_premium_collected'] = 1000.0
        s['params']['hard_stop_multiplier'] = 3.0
        hs = recalc_hard_stop(s)
        assert abs(hs - 3000.0) < 1e-6

    def test_compute_dte_days_future(self):
        from webui.backend.routes.mmmx.mmmx_engine import compute_dte_days
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        dte = compute_dte_days(future)
        assert 29.9 < dte < 30.1

    def test_compute_dte_days_past(self):
        from webui.backend.routes.mmmx.mmmx_engine import compute_dte_days
        from datetime import datetime, timezone, timedelta
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        dte = compute_dte_days(past)
        assert dte == 0.0

    def test_compute_dte_days_none(self):
        from webui.backend.routes.mmmx.mmmx_engine import compute_dte_days
        assert compute_dte_days(None) == -1.0

    def test_black_scholes_call_positive(self):
        from webui.backend.routes.mmmx.mmmx_engine import black_scholes_fair_value
        # ATM call with reasonable params should have positive value
        price = black_scholes_fair_value(
            spot=70000, strike=70000,
            time_to_expiry_years=30/365,
            iv=0.80, option_type='call'
        )
        assert price > 0

    def test_black_scholes_call_otm_cheaper(self):
        from webui.backend.routes.mmmx.mmmx_engine import black_scholes_fair_value
        atm = black_scholes_fair_value(70000, 70000, 30/365, 0.80, option_type='call')
        otm = black_scholes_fair_value(70000, 80000, 30/365, 0.80, option_type='call')
        assert otm < atm  # OTM call should be cheaper

    def test_black_scholes_put_call_parity(self):
        """
        Put-call parity: C - P = S - K*e^(-rT)
        Approximate check (not exact due to rounding).
        """
        from webui.backend.routes.mmmx.mmmx_engine import black_scholes_fair_value
        import math
        S, K, T, iv, r = 70000, 70000, 30/365, 0.80, 0.05
        call = black_scholes_fair_value(S, K, T, iv, r, 'call')
        put  = black_scholes_fair_value(S, K, T, iv, r, 'put')
        pcp = call - put - (S - K * math.exp(-r * T))
        assert abs(pcp) < 5.0  # within $5 is fine given rounding

    def test_black_scholes_zero_expiry(self):
        from webui.backend.routes.mmmx.mmmx_engine import black_scholes_fair_value
        price = black_scholes_fair_value(70000, 70000, 0, 0.80)
        assert price == 0.0

    def test_compute_lot_imbalance_balanced(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        from webui.backend.routes.mmmx.mmmx_engine import compute_lot_imbalance
        s = create_session()
        s['tranches'] = [{
            'tranche_id': 1, 'type': 'deployment',
            'ce': {'status': 'ACTIVE', 'lots': 10},
            'pe': {'status': 'ACTIVE', 'lots': 10},
        }]
        result = compute_lot_imbalance(s)
        assert result['total_ce_lots'] == 10
        assert result['total_pe_lots'] == 10
        assert result['imbalance_pct'] == 0.0

    def test_compute_lot_imbalance_skewed(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        from webui.backend.routes.mmmx.mmmx_engine import compute_lot_imbalance
        s = create_session()
        s['tranches'] = [
            {'tranche_id': 1, 'type': 'deployment',
             'ce': {'status': 'ACTIVE', 'lots': 10},
             'pe': {'status': 'ACTIVE', 'lots': 10}},
            {'tranche_id': 2, 'type': 'deployment',
             'ce': {'status': 'ACTIVE', 'lots': 10},
             'pe': {'status': 'CLOSED', 'lots': 10}},
        ]
        result = compute_lot_imbalance(s)
        assert result['total_ce_lots'] == 20
        assert result['total_pe_lots'] == 10
        assert result['imbalance_pct'] == 50.0

    def test_compute_portfolio_pnl_simple(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        from webui.backend.routes.mmmx.mmmx_engine import compute_portfolio_pnl
        s = create_session()
        s['tranches'] = [{
            'tranche_id': 1, 'type': 'deployment',
            'ce': {
                'status': 'ACTIVE', 'lots': 10,
                'entry_premium': 100.0, 'current_premium': 60.0,
                'realized_pnl': 0.0, 'fees_paid': 0.0,
            },
            'pe': {
                'status': 'ACTIVE', 'lots': 10,
                'entry_premium': 80.0, 'current_premium': 50.0,
                'realized_pnl': 0.0, 'fees_paid': 0.0,
            },
        }]
        pnl = compute_portfolio_pnl(s)
        # CE: (100-60)*10*0.001 = 0.4 USD, PE: (80-50)*10*0.001 = 0.3 USD
        assert abs(pnl - 0.7) < 1e-6

    def test_compute_portfolio_pnl_raises_on_missing_premium(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        from webui.backend.routes.mmmx.mmmx_engine import compute_portfolio_pnl, PnLIncompleteError
        s = create_session()
        s['tranches'] = [{
            'tranche_id': 1, 'type': 'deployment',
            'ce': {
                'status': 'ACTIVE', 'lots': 10,
                'entry_premium': 100.0, 'current_premium': None,
                'realized_pnl': 0.0, 'fees_paid': 0.0,
            },
            'pe': {
                'status': 'ACTIVE', 'lots': 10,
                'entry_premium': 80.0, 'current_premium': 50.0,
                'realized_pnl': 0.0, 'fees_paid': 0.0,
            },
        }]
        with pytest.raises(PnLIncompleteError):
            compute_portfolio_pnl(s)

    def test_apply_whipsaw_cooldown(self):
        from webui.backend.routes.mmmx.mmmx_engine import apply_whipsaw_to_deployment
        result = apply_whipsaw_to_deployment(4, 2.0, 10)
        assert result['skip'] is True
        assert result['level'] == 'COOLDOWN'

    def test_apply_whipsaw_restrict(self):
        from webui.backend.routes.mmmx.mmmx_engine import apply_whipsaw_to_deployment
        result = apply_whipsaw_to_deployment(3, 2.0, 10)
        assert result['skip'] is False
        assert result['move_pct'] == 4.0  # 2.0 × 2.0
        assert result['lots'] == 5
        assert result['level'] == 'RESTRICT'

    def test_apply_whipsaw_caution(self):
        from webui.backend.routes.mmmx.mmmx_engine import apply_whipsaw_to_deployment
        result = apply_whipsaw_to_deployment(2, 2.0, 10)
        assert result['move_pct'] == 3.0  # 2.0 × 1.5
        assert result['lots'] == 10
        assert result['level'] == 'CAUTION'

    def test_apply_whipsaw_normal(self):
        from webui.backend.routes.mmmx.mmmx_engine import apply_whipsaw_to_deployment
        result = apply_whipsaw_to_deployment(0, 2.0, 10)
        assert result['move_pct'] == 2.0
        assert result['level'] == 'NORMAL'

    def test_compute_recovery_lots(self):
        from webui.backend.routes.mmmx.mmmx_engine import compute_recovery_lots
        ce_lots, pe_lots = compute_recovery_lots(1000.0, 100.0, 80.0)
        # ce: ceil(1000 * 0.30 / (100 * 0.001)) = ceil(300/0.1) = ceil(3000) = 3000
        # pe: ceil(1000 * 0.70 / (80 * 0.001)) = ceil(700/0.08) = ceil(8750) = 8750
        assert ce_lots == 3000
        assert pe_lots == 8750

    def test_deployment_queue_size(self):
        from webui.backend.routes.mmmx.mmmx_engine import compute_deployment_queue_size
        assert compute_deployment_queue_size(6.4, 2.0, 10) == 3  # floor(6.4/2.0)=3
        assert compute_deployment_queue_size(4.4, 2.0, 10) == 2  # floor(4.4/2.0)=2
        assert compute_deployment_queue_size(1.5, 2.0, 10) == 0  # below threshold

    def test_deployment_retracement_up_queue(self):
        from webui.backend.routes.mmmx.mmmx_engine import check_deployment_retracement
        # Queue was UP, market retraced
        clear, pct = check_deployment_retracement(69000, 70500, 'UP', 0.5)
        assert clear is True
        assert pct > 2.0

    def test_deployment_retracement_no_retrace(self):
        from webui.backend.routes.mmmx.mmmx_engine import check_deployment_retracement
        clear, pct = check_deployment_retracement(71500, 70500, 'UP', 0.5)
        assert clear is False  # market continued up

    def test_check_fairness_gate_pass(self):
        from webui.backend.routes.mmmx.mmmx_engine import check_fairness_gate
        ok, dev = check_fairness_gate(mid_price=100.0, bs_fair_value=102.0, threshold_pct=10.0)
        assert ok is True
        assert dev < 10.0

    def test_check_fairness_gate_fail(self):
        from webui.backend.routes.mmmx.mmmx_engine import check_fairness_gate
        ok, dev = check_fairness_gate(mid_price=130.0, bs_fair_value=100.0, threshold_pct=10.0)
        assert ok is False
        assert dev == 30.0


# ═══════════════════════════════════════════════════════════════════════════════
# Monitor — Generation Guard
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonitorGenerationGuard:
    """
    Tests for the 3-layer generation guard skeleton.
    Uses a temp DB to avoid touching production data.
    """

    @pytest.fixture(autouse=True)
    def _patch_storage(self, tmp_path, monkeypatch):
        """Replace the singleton storage with a temp-DB instance."""
        import webui.backend.routes.mmmx.mmmx_storage as storage_mod
        import webui.backend.routes.mmmx.mmmx_monitor as monitor_mod

        db_path = str(tmp_path / 'test_mmmx.db')
        from webui.backend.routes.mmmx.mmmx_storage import MMMXStorage
        test_storage = MMMXStorage(db_path=db_path)

        # Patch singleton
        monkeypatch.setattr(storage_mod, '_storage_instance', test_storage)
        monkeypatch.setattr(storage_mod, 'get_storage', lambda db_path=None: test_storage)

        # Clear monitors registry
        monitor_mod._mmmx_monitors.clear()

        self.storage = test_storage

    def _make_session(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        s = create_session()
        s['status'] = 'RUNNING'
        self.storage.save_session(s, expected_gen=None)
        return s

    def test_generation_increments_on_start(self):
        from webui.backend.routes.mmmx.mmmx_monitor import start_session_monitor
        s = self._make_session()
        monitor = start_session_monitor(s['session_id'])
        gen = self.storage.get_generation(s['session_id'])
        assert gen == 1
        assert monitor._my_generation == 1
        monitor.stop()

    def test_two_starts_bump_generation_twice(self):
        from webui.backend.routes.mmmx.mmmx_monitor import start_session_monitor
        s = self._make_session()
        m1 = start_session_monitor(s['session_id'])
        time.sleep(0.05)
        m2 = start_session_monitor(s['session_id'])  # stops m1, starts m2
        gen = self.storage.get_generation(s['session_id'])
        assert gen == 2
        assert m2._my_generation == 2
        m2.stop()

    def test_stale_monitor_self_stops(self):
        """
        Stale monitor (gen=1) detects stored gen=2 and self-stops.
        """
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor
        s = self._make_session()

        # Bump generation to 2 manually (simulates a second start)
        self.storage.bump_generation(s['session_id'])
        self.storage.bump_generation(s['session_id'])
        stored_gen = self.storage.get_generation(s['session_id'])
        assert stored_gen == 2

        # Create a stale monitor at gen=1
        stale = MMMXMonitor(session_id=s['session_id'], my_generation=1)
        stale.start()

        # Give it time to detect stale condition in _run_loop
        deadline = time.monotonic() + 3.0
        while stale.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)

        assert not stale._running, "Stale monitor should have self-stopped"

    def test_two_concurrent_sessions_independent(self):
        """Two sessions' monitors don't interfere with each other."""
        from webui.backend.routes.mmmx.mmmx_monitor import start_session_monitor
        from webui.backend.routes.mmmx.mmmx_state import create_session

        s1 = self._make_session()
        s2 = create_session()
        s2['status'] = 'RUNNING'
        self.storage.save_session(s2, expected_gen=None)

        m1 = start_session_monitor(s1['session_id'])
        m2 = start_session_monitor(s2['session_id'])

        assert m1.session_id != m2.session_id
        assert self.storage.get_generation(s1['session_id']) == 1
        assert self.storage.get_generation(s2['session_id']) == 1

        m1.stop()
        m2.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# Isolation Scan
# ═══════════════════════════════════════════════════════════════════════════════

class TestMMMIsolation:
    """Verify that no mmmx module imports from routes.mmm.*"""

    MMX_MODULES = [
        'mmmx_constants', 'mmmx_state', 'mmmx_config', 'mmmx_storage',
        'mmmx_activity', 'mmmx_audit_log', 'mmmx_param_audit',
        'mmmx_websocket', 'mmmx_telegram', 'mmmx_engine', 'mmmx_monitor',
        'mmmx_api',
    ]

    def test_no_mmm_imports(self):
        """Scan actual import statements only (skip docstrings and comments)."""
        import re
        import importlib
        import inspect
        violations = []
        # Match lines that are actual import statements referencing routes.mmm
        import_re = re.compile(r'^\s*(import|from)\s+.*routes\.mmm', re.MULTILINE)
        for mod_name in self.MMX_MODULES:
            full_name = f'webui.backend.routes.mmmx.{mod_name}'
            try:
                mod = importlib.import_module(full_name)
                src = inspect.getsource(mod)
                if import_re.search(src):
                    violations.append(mod_name)
            except Exception as exc:
                pytest.fail(f"Could not import {full_name}: {exc}")

        assert not violations, (
            f"MMM isolation violated in: {violations}. "
            "These modules import from routes.mmm.* which is forbidden."
        )

    def test_no_mmm_db_access(self):
        """Verify mmmx_storage only opens mmmx_sessions.db, never mmm_sessions.db."""
        import re
        import inspect
        import webui.backend.routes.mmmx.mmmx_storage as mod
        src = inspect.getsource(mod)
        # Match only code lines (not in docstrings) that reference mmm_sessions.db
        # Strip triple-quoted strings then scan
        stripped = re.sub(r'""".*?"""', '', src, flags=re.DOTALL)
        stripped = re.sub(r"'''.*?'''", '', stripped, flags=re.DOTALL)
        assert 'mmm_sessions.db' not in stripped, \
            "mmmx_storage code references mmm_sessions.db — must use mmmx_sessions.db only"

    def test_no_mmm_websocket_events(self):
        """Verify mmmx_websocket only emits mmmx_* events."""
        import inspect
        import webui.backend.routes.mmmx.mmmx_websocket as mod
        src = inspect.getsource(mod)
        # Find all _emit('mmm_ calls (without x)
        import re
        bad = re.findall(r"_emit\('mmm_[^x]", src)
        assert not bad, f"mmmx_websocket emits non-mmmx events: {bad}"
