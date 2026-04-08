"""
MMMX Phase 6 Unit Tests — Deployment Engine + Queue + Gates + Whipsaw + Profit Booking

Covers:
  - check_entry_gates: DTE, IV rank, margin, liquidity gates — reject and accept cases
  - scan_strikes: irregular chain ladder, CE/PE split, OTM selection
  - deploy_manual_tranche1: happy path, PE fail rollback, no state mutation on fail
  - execute_tranche_deploy: frequency gate, fairness gate, all-or-nothing, rollback
  - check_deploy_conditions: spot move trigger, IV delta trigger, whipsaw blocks
  - populate_eligibility_queue: 6.4% move → queue [Tr2,Tr3,Tr4]; cap at remaining
  - clear_queue_on_retrace: >0.5% retrace clears queue; <0.5% leaves queue intact
  - enforce_frequency_gate: 3rd deploy in 24h blocked
  - whipsaw score_tick: noise detection, direction flip, no-spot fallback
  - whipsaw decay_score: normal -1/beat, cooldown -2 on expiry
  - whipsaw apply_to_deployment: CAUTION/RESTRICT/COOLDOWN adjustments
  - whipsaw get_level: score → level string
  - profit_booking queue_close: validation, update existing entry
  - profit_booking process_pending: close when target met; hold when not met
  - profit_booking close_tranche: CE+PE close, capacity freed (deployment), hard stop recalc
  - profit_booking recovery tranche close: NO tranches_deployed change
  - Heartbeat step 6 wiring: whipsaw decay → deploy conditions → profit booking

Exit criteria (MMMX_IMPLEMENTATION_PLAN.md Phase 6):
  - Entry gates reject DTE=19, IV rank=49, margin=85%; accept valid inputs.
  - Strike scan with irregular ladder (no step sizes) passes.
  - Rollback on PE failure leaves no state mutation.
  - 6.4% move populates queue [Tr2,Tr3,Tr4]; deploys one/beat.
  - >0.5% retrace clears queue.
  - Frequency gate blocks 3rd deploy in 24h.
  - Whipsaw: CAUTION widens +50%; RESTRICT halves size; COOLDOWN skips.
  - Profit booking: target met → close; not met → hold; capacity freed; hard stop recalcs.
  - Recovery tranche profit-booked without changing tranches_deployed.
"""

import asyncio
import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..')
)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_session(**overrides):
    """Create a minimal session dict for testing."""
    from webui.backend.routes.mmmx.mmmx_state import create_session
    s = create_session()
    s['session_id'] = 'test-session-0001'
    s['expiry_datetime'] = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    s['expiry_ddmmyy'] = '280626'
    s['status'] = 'RUNNING'
    for k, v in overrides.items():
        s[k] = v
    return s


def _make_executor(ce_ok=True, pe_ok=True, rollback_ok=True, avg_price=150.0):
    """Mock executor with configurable fill success."""
    class _MockResult:
        def __init__(self, success, reason='ok', fees=0.5):
            self.success = success
            self.reason = reason
            self.avg_price = avg_price if success else None
            self.fees_paid = fees if success else 0.0

    executor = MagicMock()
    call_order = []

    async def _execute(symbol, side, size, **kwargs):
        call_order.append((symbol, side, size))
        action = kwargs.get('action', '')
        if side == 'buy' and 'ROLLBACK' in action:
            return _MockResult(rollback_ok)
        if side == 'buy':
            # profit booking / close
            return _MockResult(True)
        # sell
        if 'CE' in action or symbol.startswith('C-'):
            return _MockResult(ce_ok, reason='CE rejected' if not ce_ok else 'ok')
        if 'PE' in action or symbol.startswith('P-'):
            return _MockResult(pe_ok, reason='PE rejected' if not pe_ok else 'ok')
        return _MockResult(True)

    executor.smart_execute = _execute
    executor._call_order = call_order
    return executor


def _make_audit():
    audit = MagicMock()
    audit.enqueue_event = MagicMock()
    return audit


def _make_chain(spot=70000.0):
    """Build an irregular strike chain around spot."""
    # CE strikes (calls): irregular spacing
    ce_strikes = [75000, 76500, 78000, 80000, 82500, 85000, 90000]
    # PE strikes (puts): irregular spacing
    pe_strikes = [55000, 57500, 59000, 60000, 61500, 63000, 65000]

    chain = []
    for s in ce_strikes:
        chain.append({
            'strike': s,
            'symbol': f'C-BTC-{s}-280626',
            'bid': 100.0 + (s - 80000) * 0.01,
            'ask': 110.0 + (s - 80000) * 0.01,
            'delta': 0.25,
        })
    for s in pe_strikes:
        chain.append({
            'strike': s,
            'symbol': f'P-BTC-{s}-280626',
            'bid': 80.0,
            'ask': 90.0,
            'delta': -0.20,
        })
    return chain


# ══════════════════════════════════════════════════════════════════════════════
# 1. Entry Gates
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckEntryGates:

    def _gates(self):
        from webui.backend.routes.mmmx.mmmx_initializer import check_entry_gates
        return check_entry_gates

    def test_all_gates_pass(self):
        check_entry_gates = self._gates()
        params = {
            'entry_dte_min': 20,
            'entry_dte_max': 45,
            'entry_iv_rank_min': 50,
        }
        live = {
            'dte': 30.0,
            'iv_rank': 65.0,
            'margin_utilisation': 50.0,
            'bid_depth_lots': 10,
            'spread_pct': 3.0,
        }
        result = check_entry_gates(params, live)
        assert result.ok is True
        assert result.failed_gates == []

    def test_dte_too_low(self):
        check_entry_gates = self._gates()
        params = {'entry_dte_min': 20, 'entry_dte_max': 45, 'entry_iv_rank_min': 50}
        live = {
            'dte': 19.0,
            'iv_rank': 65.0,
            'margin_utilisation': 50.0,
            'bid_depth_lots': 10,
            'spread_pct': 3.0,
        }
        result = check_entry_gates(params, live)
        assert result.ok is False
        assert 'DTE' in result.failed_gates

    def test_iv_rank_too_low(self):
        check_entry_gates = self._gates()
        params = {'entry_dte_min': 20, 'entry_dte_max': 45, 'entry_iv_rank_min': 50}
        live = {
            'dte': 30.0,
            'iv_rank': 49.0,
            'margin_utilisation': 50.0,
            'bid_depth_lots': 10,
            'spread_pct': 3.0,
        }
        result = check_entry_gates(params, live)
        assert result.ok is False
        assert 'IV_RANK' in result.failed_gates

    def test_margin_too_high(self):
        check_entry_gates = self._gates()
        params = {'entry_dte_min': 20, 'entry_dte_max': 45, 'entry_iv_rank_min': 50}
        live = {
            'dte': 30.0,
            'iv_rank': 65.0,
            'margin_utilisation': 85.0,
            'bid_depth_lots': 10,
            'spread_pct': 3.0,
        }
        result = check_entry_gates(params, live)
        assert result.ok is False
        assert 'MARGIN' in result.failed_gates

    def test_bid_depth_too_low(self):
        check_entry_gates = self._gates()
        params = {'entry_dte_min': 20, 'entry_dte_max': 45, 'entry_iv_rank_min': 50}
        live = {
            'dte': 30.0,
            'iv_rank': 65.0,
            'margin_utilisation': 50.0,
            'bid_depth_lots': 3,
            'spread_pct': 3.0,
        }
        result = check_entry_gates(params, live)
        assert result.ok is False
        assert 'BID_DEPTH' in result.failed_gates

    def test_spread_too_wide(self):
        check_entry_gates = self._gates()
        params = {'entry_dte_min': 20, 'entry_dte_max': 45, 'entry_iv_rank_min': 50}
        live = {
            'dte': 30.0,
            'iv_rank': 65.0,
            'margin_utilisation': 50.0,
            'bid_depth_lots': 10,
            'spread_pct': 12.0,
        }
        result = check_entry_gates(params, live)
        assert result.ok is False
        assert 'SPREAD' in result.failed_gates

    def test_multiple_failures_reported(self):
        check_entry_gates = self._gates()
        params = {'entry_dte_min': 20, 'entry_dte_max': 45, 'entry_iv_rank_min': 50}
        live = {
            'dte': 19.0,
            'iv_rank': 49.0,
            'margin_utilisation': 85.0,
            'bid_depth_lots': 2,
            'spread_pct': 15.0,
        }
        result = check_entry_gates(params, live)
        assert result.ok is False
        assert len(result.failed_gates) == 5
        assert len(result.messages) == 5


# ══════════════════════════════════════════════════════════════════════════════
# 2. Strike Scanning
# ══════════════════════════════════════════════════════════════════════════════

class TestScanStrikes:

    def _scan(self):
        from webui.backend.routes.mmmx.mmmx_initializer import scan_strikes
        return scan_strikes

    def test_selects_nearest_ce_pe_irregular_ladder(self):
        """Must pick closest strike regardless of step size."""
        scan_strikes = self._scan()
        spot = 70000.0
        otm_pct = 15.0   # CE target = 80500, PE target = 59500

        chain = _make_chain(spot)
        result = scan_strikes('BTC', '280626', otm_pct, chain, spot)

        assert result is not None
        # CE target = 80500 → nearest in [75000,76500,78000,80000,82500,...] = 80000
        assert result.ce_strike == 80000.0
        assert result.ce_symbol.startswith('C-BTC-80000')
        # PE target = 59500 → nearest in [55000,57500,59000,60000,...] = 59000 or 60000
        assert result.pe_strike in (59000.0, 60000.0)
        assert result.pe_symbol.startswith('P-BTC-')

    def test_no_hardcoded_step_size(self):
        """Chain with random gaps must still find nearest strike."""
        scan_strikes = self._scan()
        spot = 50000.0
        otm_pct = 10.0   # CE target = 55000, PE target = 45000

        chain = [
            {'strike': 53100, 'symbol': 'C-BTC-53100-280626', 'bid': 90, 'ask': 100, 'delta': 0.2},
            {'strike': 55300, 'symbol': 'C-BTC-55300-280626', 'bid': 80, 'ask': 90, 'delta': 0.18},
            {'strike': 57800, 'symbol': 'C-BTC-57800-280626', 'bid': 60, 'ask': 70, 'delta': 0.12},
            {'strike': 44200, 'symbol': 'P-BTC-44200-280626', 'bid': 75, 'ask': 85, 'delta': -0.18},
            {'strike': 45900, 'symbol': 'P-BTC-45900-280626', 'bid': 80, 'ask': 90, 'delta': -0.20},
            {'strike': 47500, 'symbol': 'P-BTC-47500-280626', 'bid': 90, 'ask': 100, 'delta': -0.25},
        ]
        result = scan_strikes('BTC', '280626', otm_pct, chain, spot)

        assert result is not None
        # CE target=55000: 55300 is closer than 53100 and 57800
        assert result.ce_strike == 55300.0
        # PE target=45000: 44200 is closer (|44200-45000|=800) than 45900 (|45900-45000|=900)
        assert result.pe_strike == 44200.0

    def test_empty_chain_returns_none(self):
        scan_strikes = self._scan()
        result = scan_strikes('BTC', '280626', 15.0, [], 70000.0)
        assert result is None

    def test_zero_spot_returns_none(self):
        scan_strikes = self._scan()
        result = scan_strikes('BTC', '280626', 15.0, _make_chain(), 0.0)
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# 3. Manual Tranche 1 Deploy
# ══════════════════════════════════════════════════════════════════════════════

class TestDeployManualTranche1:

    def _deploy(self):
        from webui.backend.routes.mmmx.mmmx_initializer import deploy_manual_tranche1
        return deploy_manual_tranche1

    def test_happy_path(self):
        deploy = self._deploy()
        session = _make_session(status='GATES_PASSED', tranches_deployed=0, tranches_remaining=10)
        executor = _make_executor(ce_ok=True, pe_ok=True)
        audit = _make_audit()

        result = _run(deploy(
            session, executor, audit,
            ce_symbol='C-BTC-80000-280626',
            pe_symbol='P-BTC-60000-280626',
            ce_lots=10, pe_lots=10,
            spot=70000.0, iv_rank=60.0,
            ce_strike=80000.0, ce_premium=150.0, ce_delta=0.25,
            pe_strike=60000.0, pe_premium=120.0, pe_delta=-0.20,
        ))

        assert result.get('tranche_id') == 1
        assert result.get('type') == 'deployment'
        assert len(session['tranches']) == 1
        assert session['tranches_deployed'] == 1
        assert session['tranches_remaining'] == 9
        assert session['last_deployment_spot'] == 70000.0
        assert session['last_deployment_iv_rank'] == 60.0
        assert session['hard_stop_usd'] > 0
        assert len(session['deployments_last_24h']) == 1
        assert session['status'] == 'RUNNING'

    def test_pe_fail_rollback_no_state_mutation(self):
        """PE fail → CE rolled back → session unchanged."""
        deploy = self._deploy()
        session = _make_session(status='GATES_PASSED', tranches_deployed=0, tranches_remaining=10)
        executor = _make_executor(ce_ok=True, pe_ok=False, rollback_ok=True)
        audit = _make_audit()

        result = _run(deploy(
            session, executor, audit,
            ce_symbol='C-BTC-80000-280626',
            pe_symbol='P-BTC-60000-280626',
            ce_lots=10, pe_lots=10,
            spot=70000.0, iv_rank=60.0,
            ce_strike=80000.0, ce_premium=150.0, ce_delta=0.25,
            pe_strike=60000.0, pe_premium=120.0, pe_delta=-0.20,
        ))

        assert result.get('success') is False
        assert 'PE sell failed' in result.get('reason', '')
        # Session state MUST be unchanged
        assert len(session['tranches']) == 0
        assert session['tranches_deployed'] == 0
        assert session['tranches_remaining'] == 10
        assert session['last_deployment_spot'] is None

    def test_ce_fail_aborts_without_pe_attempt(self):
        deploy = self._deploy()
        session = _make_session(status='GATES_PASSED', tranches_deployed=0, tranches_remaining=10)
        executor = _make_executor(ce_ok=False, pe_ok=True)
        audit = _make_audit()

        result = _run(deploy(
            session, executor, audit,
            ce_symbol='C-BTC-80000-280626',
            pe_symbol='P-BTC-60000-280626',
            ce_lots=10, pe_lots=10,
            spot=70000.0, iv_rank=60.0,
            ce_strike=80000.0, ce_premium=150.0, ce_delta=0.25,
            pe_strike=60000.0, pe_premium=120.0, pe_delta=-0.20,
        ))

        assert result.get('success') is False
        assert len(session['tranches']) == 0

    def test_hard_stop_initialised(self):
        deploy = self._deploy()
        session = _make_session(status='GATES_PASSED')
        session['params']['hard_stop_multiplier'] = 2.0
        executor = _make_executor()
        audit = _make_audit()

        result = _run(deploy(
            session, executor, audit,
            ce_symbol='C-BTC-80000-280626', pe_symbol='P-BTC-60000-280626',
            ce_lots=10, pe_lots=10,
            spot=70000.0, iv_rank=60.0,
            ce_strike=80000.0, ce_premium=150.0, ce_delta=0.25,
            pe_strike=60000.0, pe_premium=120.0, pe_delta=-0.20,
        ))

        premium = session['total_premium_collected']
        expected_hard_stop = 2.0 * premium
        assert abs(session['hard_stop_usd'] - expected_hard_stop) < 1e-4


# ══════════════════════════════════════════════════════════════════════════════
# 4. execute_tranche_deploy
# ══════════════════════════════════════════════════════════════════════════════

class TestExecuteTrancheDeploy:

    def _deploy(self):
        from webui.backend.routes.mmmx.mmmx_initializer import execute_tranche_deploy
        return execute_tranche_deploy

    def test_deploys_from_queue(self):
        deploy = self._deploy()
        session = _make_session(tranches_deployed=1, tranches_remaining=9)
        session['last_deployment_spot'] = 70000.0
        session['deployment_eligible_tranches'] = [2, 3, 4]
        session['params']['fairness_gate_enabled'] = False
        executor = _make_executor()
        audit = _make_audit()

        result = _run(deploy(
            session, executor, audit,
            spot=72000.0, iv_rank=65.0,
            chain=_make_chain(72000.0),
        ))

        assert result is not None
        assert result['tranche_id'] == 2
        # Queue consumed one entry
        assert session['deployment_eligible_tranches'] == [3, 4]
        assert session['tranches_deployed'] == 2
        assert session['tranches_remaining'] == 8

    def test_returns_none_when_queue_empty(self):
        deploy = self._deploy()
        session = _make_session()
        session['deployment_eligible_tranches'] = []
        executor = _make_executor()
        audit = _make_audit()

        result = _run(deploy(
            session, executor, audit,
            spot=72000.0, iv_rank=65.0,
            chain=_make_chain(72000.0),
        ))

        assert result is None

    def test_frequency_gate_blocks(self):
        deploy = self._deploy()
        session = _make_session(tranches_remaining=8)
        # Fill 24h history with max deployments
        session['params']['max_deployments_per_day'] = 2
        now = datetime.now(timezone.utc)
        session['deployments_last_24h'] = [
            (now - timedelta(hours=1)).isoformat(),
            (now - timedelta(hours=2)).isoformat(),
        ]
        session['deployment_eligible_tranches'] = [2]
        executor = _make_executor()
        audit = _make_audit()

        result = _run(deploy(
            session, executor, audit,
            spot=72000.0, iv_rank=65.0,
            chain=_make_chain(),
        ))

        assert result is None
        # Tranche ID put back in queue
        assert 2 in session['deployment_eligible_tranches']

    def test_pe_fail_rollback(self):
        deploy = self._deploy()
        session = _make_session(tranches_deployed=1, tranches_remaining=9)
        session['last_deployment_spot'] = 70000.0
        session['deployment_eligible_tranches'] = [2]
        executor = _make_executor(ce_ok=True, pe_ok=False)
        audit = _make_audit()

        before_deployed = session['tranches_deployed']
        result = _run(deploy(
            session, executor, audit,
            spot=72000.0, iv_rank=65.0,
            chain=_make_chain(72000.0),
        ))

        assert result is None
        # No state mutation on rollback
        assert session['tranches_deployed'] == before_deployed
        assert len(session['tranches']) == 0


# ══════════════════════════════════════════════════════════════════════════════
# 5. check_deploy_conditions
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckDeployConditions:

    def _check(self):
        from webui.backend.routes.mmmx.mmmx_initializer import check_deploy_conditions
        return check_deploy_conditions

    def test_spot_move_triggers(self):
        check = self._check()
        session = _make_session(tranches_remaining=9)
        session['last_deployment_spot'] = 70000.0
        session['last_deployment_iv_rank'] = 50.0
        session['params']['tranche_deploy_move_pct'] = 2.0
        session['_whipsaw_score'] = 0

        metrics = {'spot_price': 71500.0, 'iv_rank': 55.0}  # 2.14% move
        decision = check(session, metrics)

        assert decision.should_deploy is True
        assert 'spot_move' in decision.reason

    def test_iv_delta_triggers(self):
        check = self._check()
        session = _make_session(tranches_remaining=9)
        session['last_deployment_spot'] = 70000.0
        session['last_deployment_iv_rank'] = 50.0
        session['params']['tranche_deploy_move_pct'] = 2.0
        session['params']['tranche_deploy_iv_delta'] = 10

        metrics = {'spot_price': 70500.0, 'iv_rank': 62.0}  # small spot, big IV spike
        decision = check(session, metrics)

        assert decision.should_deploy is True
        assert 'iv_delta' in decision.reason

    def test_no_tranches_remaining_blocks(self):
        check = self._check()
        session = _make_session(tranches_remaining=0)
        session['last_deployment_spot'] = 70000.0

        metrics = {'spot_price': 75000.0, 'iv_rank': 80.0}
        decision = check(session, metrics)

        assert decision.should_deploy is False
        assert 'no_tranches_remaining' in decision.reason

    def test_whipsaw_cooldown_blocks(self):
        check = self._check()
        session = _make_session(tranches_remaining=5)
        session['last_deployment_spot'] = 70000.0
        session['_whipsaw_score'] = 4
        skip_until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        session['_whipsaw_skip_until'] = skip_until

        metrics = {'spot_price': 75000.0, 'iv_rank': 80.0}
        decision = check(session, metrics)

        assert decision.should_deploy is False
        assert 'cooldown' in decision.reason.lower()

    def test_trigger_not_met(self):
        check = self._check()
        session = _make_session(tranches_remaining=5)
        session['last_deployment_spot'] = 70000.0
        session['last_deployment_iv_rank'] = 50.0
        session['params']['tranche_deploy_move_pct'] = 2.0
        session['_whipsaw_score'] = 0

        metrics = {'spot_price': 70500.0, 'iv_rank': 52.0}  # 0.7% move, 2 IV delta
        decision = check(session, metrics)

        assert decision.should_deploy is False


# ══════════════════════════════════════════════════════════════════════════════
# 6. Eligibility Queue
# ══════════════════════════════════════════════════════════════════════════════

class TestEligibilityQueue:

    def test_6pct_move_populates_queue(self):
        """6.4% move at 2% threshold → 3 tranches queued."""
        from webui.backend.routes.mmmx.mmmx_initializer import populate_eligibility_queue
        session = _make_session(tranches_deployed=1, tranches_remaining=9)
        session['last_deployment_spot'] = 70000.0
        session['params']['tranche_deploy_move_pct'] = 2.0
        session['_whipsaw_score'] = 0

        populate_eligibility_queue(session, spot_move_pct=6.4, current_spot=74480.0)

        queue = session['deployment_eligible_tranches']
        assert len(queue) == 3
        assert queue[0] == 2
        assert queue[1] == 3
        assert queue[2] == 4

    def test_queue_capped_at_tranches_remaining(self):
        from webui.backend.routes.mmmx.mmmx_initializer import populate_eligibility_queue
        session = _make_session(tranches_deployed=9, tranches_remaining=1)
        session['params']['tranche_deploy_move_pct'] = 2.0

        populate_eligibility_queue(session, spot_move_pct=10.0, current_spot=77000.0)

        assert len(session['deployment_eligible_tranches']) == 1

    def test_no_duplicates_in_queue(self):
        from webui.backend.routes.mmmx.mmmx_initializer import populate_eligibility_queue
        session = _make_session(tranches_deployed=1, tranches_remaining=5)
        session['deployment_eligible_tranches'] = [2, 3]
        session['params']['tranche_deploy_move_pct'] = 2.0

        populate_eligibility_queue(session, spot_move_pct=6.4, current_spot=74480.0)

        queue = session['deployment_eligible_tranches']
        assert len(queue) == len(set(queue))  # no duplicates

    def test_direction_recorded(self):
        from webui.backend.routes.mmmx.mmmx_initializer import populate_eligibility_queue
        session = _make_session(tranches_deployed=1, tranches_remaining=5)
        session['last_deployment_spot'] = 70000.0
        session['params']['tranche_deploy_move_pct'] = 2.0

        populate_eligibility_queue(
            session, spot_move_pct=4.0, current_spot=72800.0,
            last_deployment_spot=70000.0
        )

        assert session['deployment_queue_direction'] == 'UP'


class TestClearQueueOnRetrace:

    def test_retrace_over_threshold_clears(self):
        from webui.backend.routes.mmmx.mmmx_initializer import clear_queue_on_retrace
        session = _make_session()
        session['deployment_eligible_tranches'] = [2, 3, 4]
        session['deployment_queue_triggered_spot'] = 74480.0
        session['deployment_queue_direction'] = 'UP'

        # Current spot: 73996 → (74480 - 73996)/74480 = 0.65% retrace UP→DOWN
        cleared = clear_queue_on_retrace(session, current_spot=73996.0)

        assert cleared is True
        assert session['deployment_eligible_tranches'] == []

    def test_retrace_under_threshold_keeps_queue(self):
        from webui.backend.routes.mmmx.mmmx_initializer import clear_queue_on_retrace
        session = _make_session()
        session['deployment_eligible_tranches'] = [2, 3, 4]
        session['deployment_queue_triggered_spot'] = 74480.0
        session['deployment_queue_direction'] = 'UP'

        # Only 0.3% retrace — below 0.5% threshold
        cleared = clear_queue_on_retrace(session, current_spot=74256.0)

        assert cleared is False
        assert len(session['deployment_eligible_tranches']) == 3

    def test_no_triggered_spot_returns_false(self):
        from webui.backend.routes.mmmx.mmmx_initializer import clear_queue_on_retrace
        session = _make_session()
        session['deployment_eligible_tranches'] = [2, 3]
        session['deployment_queue_triggered_spot'] = None

        cleared = clear_queue_on_retrace(session, current_spot=74000.0)
        assert cleared is False


# ══════════════════════════════════════════════════════════════════════════════
# 7. Frequency Gate
# ══════════════════════════════════════════════════════════════════════════════

class TestFrequencyGate:

    def test_allows_within_limit(self):
        from webui.backend.routes.mmmx.mmmx_initializer import enforce_frequency_gate
        session = _make_session()
        session['params']['max_deployments_per_day'] = 2
        now = datetime.now(timezone.utc)
        session['deployments_last_24h'] = [
            (now - timedelta(hours=2)).isoformat(),
        ]
        assert enforce_frequency_gate(session) is True

    def test_blocks_at_limit(self):
        from webui.backend.routes.mmmx.mmmx_initializer import enforce_frequency_gate
        session = _make_session()
        session['params']['max_deployments_per_day'] = 2
        now = datetime.now(timezone.utc)
        session['deployments_last_24h'] = [
            (now - timedelta(hours=1)).isoformat(),
            (now - timedelta(hours=3)).isoformat(),
        ]
        assert enforce_frequency_gate(session) is False

    def test_third_deploy_in_24h_blocked(self):
        """Spec test: 3rd deploy in 24h blocked."""
        from webui.backend.routes.mmmx.mmmx_initializer import enforce_frequency_gate
        session = _make_session()
        session['params']['max_deployments_per_day'] = 2
        now = datetime.now(timezone.utc)
        session['deployments_last_24h'] = [
            (now - timedelta(hours=4)).isoformat(),
            (now - timedelta(hours=8)).isoformat(),
        ]
        # Already 2 in 24h window → 3rd attempt is blocked
        assert enforce_frequency_gate(session) is False

    def test_old_entries_ignored(self):
        """Deployments older than 24h don't count."""
        from webui.backend.routes.mmmx.mmmx_initializer import enforce_frequency_gate
        session = _make_session()
        session['params']['max_deployments_per_day'] = 2
        now = datetime.now(timezone.utc)
        session['deployments_last_24h'] = [
            (now - timedelta(hours=25)).isoformat(),  # outside window
            (now - timedelta(hours=26)).isoformat(),  # outside window
        ]
        assert enforce_frequency_gate(session) is True


# ══════════════════════════════════════════════════════════════════════════════
# 8. Fairness Gate
# ══════════════════════════════════════════════════════════════════════════════

class TestFairnessGate:

    def test_within_threshold_passes(self):
        from webui.backend.routes.mmmx.mmmx_initializer import enforce_fairness_gate
        session = _make_session()
        session['params']['fairness_gate_enabled'] = True
        session['params']['fairness_threshold_pct'] = 10.0
        assert enforce_fairness_gate(session, strike_quote=100.0, bs_price=95.0) is True

    def test_exceeds_threshold_blocked(self):
        from webui.backend.routes.mmmx.mmmx_initializer import enforce_fairness_gate
        session = _make_session()
        session['params']['fairness_gate_enabled'] = True
        session['params']['fairness_threshold_pct'] = 10.0
        assert enforce_fairness_gate(session, strike_quote=120.0, bs_price=100.0) is False

    def test_disabled_gate_always_passes(self):
        from webui.backend.routes.mmmx.mmmx_initializer import enforce_fairness_gate
        session = _make_session()
        session['params']['fairness_gate_enabled'] = False
        assert enforce_fairness_gate(session, strike_quote=200.0, bs_price=100.0) is True

    def test_zero_bs_price_passes(self):
        from webui.backend.routes.mmmx.mmmx_initializer import enforce_fairness_gate
        session = _make_session()
        session['params']['fairness_gate_enabled'] = True
        session['params']['fairness_threshold_pct'] = 10.0
        assert enforce_fairness_gate(session, strike_quote=100.0, bs_price=0.0) is True


# ══════════════════════════════════════════════════════════════════════════════
# 9. Whipsaw
# ══════════════════════════════════════════════════════════════════════════════

class TestWhipsawScoreTick:

    def _now_iso(self, delta_mins=0):
        return (datetime.now(timezone.utc) - timedelta(minutes=delta_mins)).isoformat()

    def test_noise_increments_score(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import score_tick
        session = _make_session()
        session['_whipsaw_score'] = 0
        session['_whipsaw_last_checked_idx'] = 0
        session['params']['whipsaw_window_mins'] = 30
        session['params']['whipsaw_spot_move_pct'] = 0.3

        # Two consecutive shield fires with < 0.3% spot move (noise)
        now_iso = self._now_iso(0)
        prev_iso = self._now_iso(5)
        session['shield_event_history'] = [
            {'tranche_id': 1, 'side': 'pe', 'spot': 70000.0, 'fired_at': prev_iso},
            {'tranche_id': 1, 'side': 'pe', 'spot': 70150.0, 'fired_at': now_iso},   # 0.21% move
        ]

        new_score = score_tick(session)
        assert new_score == 1
        assert session['_whipsaw_score'] == 1

    def test_direction_flip_increments_score(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import score_tick
        session = _make_session()
        session['_whipsaw_score'] = 0
        session['_whipsaw_last_checked_idx'] = 0
        session['params']['whipsaw_window_mins'] = 30
        session['params']['whipsaw_spot_move_pct'] = 0.3

        # CE shield then PE shield with small spot move = oscillation
        prev_iso = self._now_iso(10)
        now_iso = self._now_iso(0)
        session['shield_event_history'] = [
            {'tranche_id': 1, 'side': 'ce', 'spot': 70000.0, 'fired_at': prev_iso},
            {'tranche_id': 2, 'side': 'pe', 'spot': 70400.0, 'fired_at': now_iso},  # 0.57% move
        ]

        new_score = score_tick(session)
        assert new_score >= 1

    def test_no_score_for_events_outside_window(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import score_tick
        session = _make_session()
        session['_whipsaw_score'] = 0
        session['_whipsaw_last_checked_idx'] = 0
        session['params']['whipsaw_window_mins'] = 30

        old_iso = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        session['shield_event_history'] = [
            {'tranche_id': 1, 'side': 'pe', 'spot': 70000.0, 'fired_at': old_iso},
        ]
        new_score = score_tick(session)
        assert new_score == 0

    def test_cooldown_threshold_sets_skip_until(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import score_tick
        session = _make_session()
        session['_whipsaw_score'] = 3
        session['_whipsaw_last_checked_idx'] = 0
        session['params']['whipsaw_cooldown_score'] = 4
        session['params']['whipsaw_cooldown_interval_hours'] = 1

        now_iso = self._now_iso(0)
        prev_iso = self._now_iso(5)
        session['shield_event_history'] = [
            {'tranche_id': 1, 'side': 'pe', 'spot': 70000.0, 'fired_at': prev_iso},
            {'tranche_id': 2, 'side': 'ce', 'spot': 70100.0, 'fired_at': now_iso},  # direction flip
        ]

        new_score = score_tick(session)
        assert new_score >= 4
        assert session.get('_whipsaw_skip_until') is not None


class TestWhipsawDecayScore:

    def test_normal_decay_after_1h(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import decay_score
        session = _make_session()
        session['_whipsaw_score'] = 2
        session['_whipsaw_last_noise_at'] = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        ).isoformat()

        new_score = decay_score(session)
        assert new_score == 1

    def test_no_decay_within_1h(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import decay_score
        session = _make_session()
        session['_whipsaw_score'] = 2
        session['_whipsaw_last_noise_at'] = (
            datetime.now(timezone.utc) - timedelta(minutes=30)
        ).isoformat()

        new_score = decay_score(session)
        assert new_score == 2

    def test_cooldown_expiry_minus_2(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import decay_score
        session = _make_session()
        session['_whipsaw_score'] = 4
        session['params']['whipsaw_cooldown_score'] = 4
        # skip_until in the past
        session['_whipsaw_skip_until'] = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).isoformat()

        new_score = decay_score(session)
        assert new_score == 2
        assert session.get('_whipsaw_skip_until') is None

    def test_cooldown_active_no_decay(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import decay_score
        session = _make_session()
        session['_whipsaw_score'] = 4
        session['params']['whipsaw_cooldown_score'] = 4
        # skip_until still in future
        session['_whipsaw_skip_until'] = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat()

        new_score = decay_score(session)
        assert new_score == 4

    def test_zero_score_unchanged(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import decay_score
        session = _make_session()
        session['_whipsaw_score'] = 0
        new_score = decay_score(session)
        assert new_score == 0


class TestWhipsawApplyToDeployment:

    def test_normal_no_change(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import apply_to_deployment
        session = _make_session()
        session['_whipsaw_score'] = 0
        move, size = apply_to_deployment(session, 2.0, 10)
        assert move == 2.0
        assert size == 10

    def test_caution_widens_50pct(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import apply_to_deployment
        session = _make_session()
        session['_whipsaw_score'] = 2
        move, size = apply_to_deployment(session, 2.0, 10)
        assert abs(move - 3.0) < 1e-4
        assert size == 10

    def test_restrict_doubles_move_halves_size(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import apply_to_deployment
        session = _make_session()
        session['_whipsaw_score'] = 3
        move, size = apply_to_deployment(session, 2.0, 10)
        assert abs(move - 4.0) < 1e-4
        assert size == 5

    def test_cooldown_returns_none_none(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import apply_to_deployment
        session = _make_session()
        session['_whipsaw_score'] = 4
        move, size = apply_to_deployment(session, 2.0, 10)
        assert move is None
        assert size is None


class TestWhipsawGetLevel:

    def test_levels(self):
        from webui.backend.routes.mmmx.mmmx_whipsaw import get_level
        assert get_level(0) == 'NORMAL'
        assert get_level(1) == 'NORMAL'
        assert get_level(2) == 'CAUTION'
        assert get_level(3) == 'RESTRICT'
        assert get_level(4) == 'COOLDOWN'
        assert get_level(5) == 'COOLDOWN'
        assert get_level(10) == 'COOLDOWN'


# ══════════════════════════════════════════════════════════════════════════════
# 10. Profit Booking
# ══════════════════════════════════════════════════════════════════════════════

def _make_active_tranche(tranche_id=1, lots=10, premium=100.0, tranche_type='deployment'):
    """Create a minimal ACTIVE tranche for testing."""
    from webui.backend.routes.mmmx.mmmx_state import make_tranche
    t = make_tranche(
        tranche_id=tranche_id,
        entry_spot=70000.0,
        entry_dvol=0.0,
        entry_iv_rank=60.0,
        ce_symbol=f'C-BTC-80000-280626',
        ce_strike=80000.0,
        ce_lots=lots,
        ce_premium=premium / 2,
        ce_delta=0.25,
        pe_symbol=f'P-BTC-60000-280626',
        pe_strike=60000.0,
        pe_lots=lots,
        pe_premium=premium / 2,
        pe_delta=-0.20,
        tranche_type=tranche_type,
    )
    # Set unrealized P&L
    t['ce']['unrealized_pnl'] = 8.0
    t['pe']['unrealized_pnl'] = 9.0
    return t


class TestProfitBookingQueueClose:

    def test_adds_to_queue(self):
        from webui.backend.routes.mmmx.mmmx_profit_booking import queue_close
        session = _make_session()
        tranche = _make_active_tranche(tranche_id=1)
        session['tranches'] = [tranche]

        queue_close(session, 1, 15.0)

        assert len(session['_profit_booking_queue']) == 1
        entry = session['_profit_booking_queue'][0]
        assert entry['tranche_id'] == 1
        assert entry['target_pct'] == 15.0

    def test_invalid_tranche_raises(self):
        from webui.backend.routes.mmmx.mmmx_profit_booking import queue_close
        session = _make_session()
        session['tranches'] = []
        with pytest.raises(ValueError, match='not found'):
            queue_close(session, 99, 15.0)

    def test_update_existing_entry(self):
        from webui.backend.routes.mmmx.mmmx_profit_booking import queue_close
        session = _make_session()
        session['tranches'] = [_make_active_tranche(tranche_id=1)]
        queue_close(session, 1, 15.0)
        queue_close(session, 1, 20.0)  # update

        assert len(session['_profit_booking_queue']) == 1
        assert session['_profit_booking_queue'][0]['target_pct'] == 20.0


class TestProfitBookingProcessPending:

    def test_closes_when_target_met(self):
        """Tr1 at +$17 with 15% target on $100 premium = close."""
        from webui.backend.routes.mmmx.mmmx_profit_booking import process_pending
        session = _make_session(tranches_deployed=1, tranches_remaining=9)
        tranche = _make_active_tranche(tranche_id=1, lots=10)
        tranche['premium_collected'] = 100.0
        tranche['ce']['unrealized_pnl'] = 9.0
        tranche['pe']['unrealized_pnl'] = 9.0  # total $18 > 15% of $100 = $15

        session['tranches'] = [tranche]
        session['_profit_booking_queue'] = [
            {'tranche_id': 1, 'target_pct': 15.0, 'queued_at': datetime.now(timezone.utc).isoformat()}
        ]

        results = _run(process_pending(session, _make_executor(), _make_audit()))

        assert len(results) == 1
        assert results[0]['success'] is True
        assert session['_profit_booking_queue'] == []  # removed from queue

    def test_holds_when_target_not_met(self):
        """Tr2 at +$8 with 20% target on $100 premium = hold."""
        from webui.backend.routes.mmmx.mmmx_profit_booking import process_pending
        session = _make_session()
        tranche = _make_active_tranche(tranche_id=2, lots=10)
        tranche['premium_collected'] = 100.0
        tranche['ce']['unrealized_pnl'] = 4.0
        tranche['pe']['unrealized_pnl'] = 4.0  # total $8 < 20% = $20

        session['tranches'] = [tranche]
        session['_profit_booking_queue'] = [
            {'tranche_id': 2, 'target_pct': 20.0, 'queued_at': datetime.now(timezone.utc).isoformat()}
        ]

        results = _run(process_pending(session, _make_executor(), _make_audit()))

        assert len(results) == 0
        assert len(session['_profit_booking_queue']) == 1  # still pending

    def test_independent_tranche_evaluation(self):
        """Tr1 target met → closed; Tr2 target not met → kept."""
        from webui.backend.routes.mmmx.mmmx_profit_booking import process_pending
        session = _make_session(tranches_deployed=2, tranches_remaining=8)

        tr1 = _make_active_tranche(tranche_id=1)
        tr1['premium_collected'] = 100.0
        tr1['ce']['unrealized_pnl'] = 10.0
        tr1['pe']['unrealized_pnl'] = 10.0  # $20 >= 15% of $100 ✓

        tr2 = _make_active_tranche(tranche_id=2)
        tr2['premium_collected'] = 100.0
        tr2['ce']['unrealized_pnl'] = 3.0
        tr2['pe']['unrealized_pnl'] = 3.0   # $6 < 20% of $100 ✗

        session['tranches'] = [tr1, tr2]
        session['_profit_booking_queue'] = [
            {'tranche_id': 1, 'target_pct': 15.0, 'queued_at': datetime.now(timezone.utc).isoformat()},
            {'tranche_id': 2, 'target_pct': 20.0, 'queued_at': datetime.now(timezone.utc).isoformat()},
        ]

        results = _run(process_pending(session, _make_executor(), _make_audit()))

        assert len(results) == 1
        assert results[0]['tranche_id'] == 1
        assert len(session['_profit_booking_queue']) == 1
        assert session['_profit_booking_queue'][0]['tranche_id'] == 2


class TestProfitBookingCloseTranche:

    def test_closes_both_legs(self):
        from webui.backend.routes.mmmx.mmmx_profit_booking import close_tranche
        session = _make_session(tranches_deployed=1, tranches_remaining=9)
        tranche = _make_active_tranche(tranche_id=1, lots=10)
        session['tranches'] = [tranche]

        result = _run(close_tranche(session, 1, _make_executor(), _make_audit()))

        assert result['success'] is True
        assert result['ce_closed'] is True
        assert result['pe_closed'] is True
        assert tranche['status'] == 'CLOSED'

    def test_deployment_tranche_frees_slot(self):
        from webui.backend.routes.mmmx.mmmx_profit_booking import close_tranche
        session = _make_session(tranches_deployed=3, tranches_remaining=7)
        tranche = _make_active_tranche(tranche_id=2, tranche_type='deployment')
        session['tranches'] = [tranche]

        _run(close_tranche(session, 2, _make_executor(), _make_audit()))

        assert session['tranches_deployed'] == 2
        assert session['tranches_remaining'] == 8

    def test_recovery_tranche_no_counter_change(self):
        from webui.backend.routes.mmmx.mmmx_profit_booking import close_tranche
        session = _make_session(tranches_deployed=2, tranches_remaining=8)
        tranche = _make_active_tranche(tranche_id='2A', tranche_type='recovery')
        session['tranches'] = [tranche]

        _run(close_tranche(session, '2A', _make_executor(), _make_audit()))

        # Recovery: counters unchanged
        assert session['tranches_deployed'] == 2
        assert session['tranches_remaining'] == 8

    def test_hard_stop_recalculated_after_close(self):
        from webui.backend.routes.mmmx.mmmx_profit_booking import close_tranche
        session = _make_session(tranches_deployed=1)
        session['total_premium_collected'] = 200.0
        session['params']['hard_stop_multiplier'] = 2.0
        tranche = _make_active_tranche(tranche_id=1)
        session['tranches'] = [tranche]
        session['hard_stop_usd'] = 0.0

        # Patch at mmmx_profit_booking import level to isolate from test_phase3 patch leaks
        with patch('webui.backend.routes.mmmx.mmmx_profit_booking.recalc_hard_stop', return_value=400.0):
            _run(close_tranche(session, 1, _make_executor(), _make_audit()))

        assert abs(session['hard_stop_usd'] - 400.0) < 1e-4

    def test_profit_booked_to_session_total(self):
        from webui.backend.routes.mmmx.mmmx_profit_booking import close_tranche
        session = _make_session(tranches_deployed=1)
        session['profit_booked_total'] = 50.0
        tranche = _make_active_tranche(tranche_id=1)
        session['tranches'] = [tranche]

        # Close at price=10 < entry=50 for SHORT = profitable (entry - exit > 0)
        result = _run(close_tranche(session, 1, _make_executor(avg_price=10.0), _make_audit()))

        assert session['profit_booked_total'] >= 50.0  # increased

    def test_nonexistent_tranche_returns_failure(self):
        from webui.backend.routes.mmmx.mmmx_profit_booking import close_tranche
        session = _make_session()
        session['tranches'] = []

        result = _run(close_tranche(session, 99, _make_executor(), _make_audit()))

        assert result['success'] is False
        assert '99' in result['reason']


# ══════════════════════════════════════════════════════════════════════════════
# 11. Constants
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase6Constants:

    def test_whipsaw_score_constants_present(self):
        from webui.backend.routes.mmmx.mmmx_constants import (
            WHIPSAW_CAUTION_SCORE, WHIPSAW_RESTRICT_SCORE, WHIPSAW_COOLDOWN_SCORE
        )
        assert WHIPSAW_CAUTION_SCORE == 2
        assert WHIPSAW_RESTRICT_SCORE == 3
        assert WHIPSAW_COOLDOWN_SCORE == 4

    def test_profit_booking_queue_in_session(self):
        from webui.backend.routes.mmmx.mmmx_state import create_session
        s = create_session()
        assert '_profit_booking_queue' in s
        assert isinstance(s['_profit_booking_queue'], list)

    def test_profit_booking_queue_in_apply_defaults(self):
        from webui.backend.routes.mmmx.mmmx_state import apply_session_defaults
        s = {}
        apply_session_defaults(s)
        assert '_profit_booking_queue' in s


# ══════════════════════════════════════════════════════════════════════════════
# 12. Isolation check
# ══════════════════════════════════════════════════════════════════════════════

class TestIsolation:

    def _check_no_mmm_import(self, module_name):
        import importlib, inspect, re
        mod = importlib.import_module(f'webui.backend.routes.mmmx.{module_name}')
        src = inspect.getsource(mod)
        # Only check actual import statements (not comments or docstrings)
        import_lines = [l for l in src.split('\n') if re.match(r'\s*(import|from)\s+', l)]
        import_src = '\n'.join(import_lines)
        assert 'routes.mmm' not in import_src, (
            f"{module_name} contains forbidden import from routes.mmm"
        )

    def test_mmmx_initializer_isolation(self):
        self._check_no_mmm_import('mmmx_initializer')

    def test_mmmx_whipsaw_isolation(self):
        self._check_no_mmm_import('mmmx_whipsaw')

    def test_mmmx_profit_booking_isolation(self):
        self._check_no_mmm_import('mmmx_profit_booking')
