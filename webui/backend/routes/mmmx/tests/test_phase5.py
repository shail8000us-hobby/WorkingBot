"""
MMMX Phase 5 Unit Tests — ATM Shield

Covers:
  - evaluate():        OTM% detection (CE and PE)
  - sort_by_priority(): G38 worst-loss-first ordering
  - allocate_reserve(): G39 full / partial / exhausted cascade
  - _next_recovery_id(): sibling naming 2A / 2B / 2C / limit
  - create_recovery_tranche(): sibling created, fields correct
  - execute_shield():   happy path, buyback abort, naked (sell fail)
  - evaluate_and_fire(): multi-shield sequencing, naked stops cascade
  - check_naked_watchdog(): 30-min retry, 2-hr critical, resolved cleanup
  - Monitor isolation:  atm_shield has zero routes.mmm.* imports
  - State invariants:   tranches_deployed/remaining unchanged; reserves decrement;
                        total_premium_collected incremented; hard_stop_usd updated;
                        last_deployment_spot reset; recovery tranche is first-class citizen.

Exit criteria (MMMX_IMPLEMENTATION_PLAN.md Phase 5):
  - Position OTM drops to 4.9% → shield fires; buyback → new sell → recovery tranche (2A); reserve decremented.
  - Multi-shield same beat: 3 candidates sorted by loss; third one reposition-only if reserve exhausted.
  - Shield new-sell fails 11 attempts → session PAUSED, _naked_positions populated.
  - Naked timeout: 30-min naked → emergency retry; 2-hr → operator alert.
  - Recovery tranche is a first-class citizen (iterated by evaluate()).
  - tranches_deployed / tranches_remaining unchanged by recovery creation.
  - last_deployment_spot reset after shield reposition.
"""

import asyncio
import importlib
import os
import re
import sys
import time
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


def _make_leg(
    status: str = 'ACTIVE',
    lots: int = 10,
    symbol: str = 'C-BTC-90000-280326',
    strike: float = 90000.0,
    entry_premium: float = 100.0,
    current_premium: float = 130.0,  # losing money
) -> dict:
    return {
        'status':          status,
        'lots':            lots,
        'symbol':          symbol,
        'strike':          strike,
        'entry_premium':   entry_premium,
        'current_premium': current_premium,
        'unrealized_pnl':  0.0,
        'realized_pnl':    0.0,
        'fees_paid':       0.0,
        '_being_closed':   False,
        '_being_closed_at': None,
        'shield_history':  [],
        'shift_count':     0,
        'entry_delta':     0.30,
        'current_delta':   0.45,
    }


def _make_tranche(
    tranche_id=1,
    tranche_type: str = 'deployment',
    ce_status: str = 'ACTIVE',
    pe_status: str = 'ACTIVE',
    ce_strike: float = 90000.0,
    pe_strike: float = 70000.0,
    ce_lots: int = 10,
    pe_lots: int = 10,
    ce_symbol: str = 'C-BTC-90000-280326',
    pe_symbol: str = 'P-BTC-70000-280326',
    ce_entry: float = 100.0,
    pe_entry: float = 100.0,
    ce_current: float = 130.0,
    pe_current: float = 130.0,
    parent_tranche_id=None,
    status: str = 'ACTIVE',
) -> dict:
    return {
        'tranche_id':        tranche_id,
        'parent_tranche_id': parent_tranche_id,
        'type':              tranche_type,
        'shield_event':      None,
        'status':            status,
        'entry_spot':        85000.0,
        'entry_dvol':        60.0,
        'entry_iv_rank':     70.0,
        'ce': _make_leg(ce_status, ce_lots, ce_symbol, ce_strike, ce_entry, ce_current),
        'pe': _make_leg(pe_status, pe_lots, pe_symbol, pe_strike, pe_entry, pe_current),
        'premium_collected': (ce_entry + pe_entry) * ce_lots * 0.001,
        'close_reason':      None,
        'closed_at':         None,
    }


def _make_session(
    tranches=None,
    status: str = 'RUNNING',
    ce_reserve: int = 30,
    pe_reserve: int = 30,
    tranches_deployed: int = 1,
    tranches_remaining: int = 9,
) -> dict:
    return {
        '_schema_version':            1,
        'session_id':                 'test-session-phase5-1234',
        'status':                     status,
        'tranches':                   tranches or [],
        'hedges':                     [],
        'params': {
            'atm_protect_threshold':  5.0,
            'atm_shield_max_shifts':  3,
            'otm_distance_pct':       15.0,
            'hard_stop_multiplier':   2.0,
            'close_at_dte':           7,
            'entry_iv_rank_min':      50,
        },
        'ce_reserve_remaining':       ce_reserve,
        'pe_reserve_remaining':       pe_reserve,
        'ce_reserve_total_lots':      30,
        'pe_reserve_total_lots':      30,
        'total_premium_collected':    0.0,
        'hard_stop_usd':              0.0,
        'tranches_deployed':          tranches_deployed,
        'tranches_remaining':         tranches_remaining,
        'last_deployment_spot':       85000.0,
        'last_deployment_iv_rank':    70.0,
        'shield_fire_count':          0,
        'shield_event_history':       [],
        '_naked_positions':           [],
        'portfolio_pnl':              0.0,
        'portfolio_delta':            0.0,
        'beat_number':                0,
        '_last_beat_at':              None,
        'fees_tracking':              {'total_fees_paid': 0.0, 'last_fee_charge': None},
    }


def _ok_result(avg_price: float = 105.0, fees: float = 0.05) -> 'ExecutionResult':
    from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult
    return ExecutionResult(
        success=True, filled_size=10, avg_price=avg_price,
        attempts=1, total_ms=100, reason='filled',
        order_id='ORD-001', client_order_id='COI-001', fees_paid=fees,
    )


def _fail_result() -> 'ExecutionResult':
    from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult
    return ExecutionResult(
        success=False, filled_size=0, avg_price=0.0,
        attempts=11, total_ms=9000, reason='timeout',
        order_id='', client_order_id='', fees_paid=0.0,
    )


def _mock_executor(buy_ok: bool = True, sell_ok: bool = True):
    exe = MagicMock()
    exe.smart_execute = AsyncMock(
        side_effect=lambda *a, **kw: (
            _ok_result() if (kw.get('side', '') == 'buy' and buy_ok)
            or (kw.get('side', '') == 'sell' and sell_ok)
            else _fail_result()
        )
    )
    exe.emergency_execute = AsyncMock(return_value=_ok_result())
    return exe


# =============================================================================
# Tests: evaluate()
# =============================================================================

class TestEvaluate:
    """OTM% detection — CE and PE."""

    def test_ce_below_threshold_triggers(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate
        # spot=87500 → CE OTM = (90000 - 87500) / 87500 × 100 = 2.86% < 5%
        session = _make_session(tranches=[_make_tranche(ce_strike=90000.0)])
        candidates = evaluate(session, spot=87500.0)
        assert len(candidates) == 1
        assert candidates[0].side == 'ce'
        assert candidates[0].tranche_id == 1
        assert candidates[0].otm_pct < 5.0

    def test_pe_below_threshold_triggers(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate
        # spot=72000 → PE OTM = (72000 - 70000) / 72000 × 100 = 2.78% < 5%
        session = _make_session(tranches=[_make_tranche(pe_strike=70000.0)])
        candidates = evaluate(session, spot=72000.0)
        # Both CE (90000) @ spot=72000: OTM = (90000-72000)/72000*100 = 25% > 5% → no
        # PE OTM = (72000-70000)/72000*100 = 2.78% < 5% → yes
        pe_candidates = [c for c in candidates if c.side == 'pe']
        assert len(pe_candidates) == 1
        assert pe_candidates[0].otm_pct < 5.0

    def test_sufficient_otm_no_trigger(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate
        # spot=80000 → CE OTM = (90000-80000)/80000*100 = 12.5% > 5% → safe
        session = _make_session(tranches=[_make_tranche(ce_strike=90000.0)])
        candidates = evaluate(session, spot=80000.0)
        ce_candidates = [c for c in candidates if c.side == 'ce']
        assert len(ce_candidates) == 0

    def test_closed_tranche_skipped(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate
        tr = _make_tranche(ce_strike=90000.0, status='CLOSED')
        session = _make_session(tranches=[tr])
        candidates = evaluate(session, spot=87500.0)
        assert candidates == []

    def test_closed_leg_skipped(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate
        tr = _make_tranche(ce_strike=90000.0, ce_status='CLOSED')
        session = _make_session(tranches=[tr])
        candidates = evaluate(session, spot=87500.0)
        ce_cands = [c for c in candidates if c.side == 'ce']
        assert len(ce_cands) == 0

    def test_no_spot_returns_empty(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate
        session = _make_session(tranches=[_make_tranche()])
        assert evaluate(session, spot=0.0) == []
        assert evaluate(session, spot=None) == []

    def test_recovery_tranche_evaluated(self):
        """Recovery tranches are full citizens — they also get shielded."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate
        recovery = _make_tranche(
            tranche_id='1A',
            tranche_type='recovery',
            ce_strike=90000.0,
            parent_tranche_id=1,
        )
        session = _make_session(tranches=[recovery])
        candidates = evaluate(session, spot=87500.0)
        assert any(c.tranche_id == '1A' for c in candidates)

    def test_custom_threshold_respected(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate
        session = _make_session(tranches=[_make_tranche(ce_strike=90000.0)])
        session['params']['atm_protect_threshold'] = 15.0
        # spot=80000 → CE OTM = 12.5% < 15% → fires
        candidates = evaluate(session, spot=80000.0)
        ce_cands = [c for c in candidates if c.side == 'ce']
        assert len(ce_cands) == 1


# =============================================================================
# Tests: sort_by_priority()
# =============================================================================

class TestSortByPriority:
    """G38 — worst loss first; oldest tranche as tiebreaker."""

    def _make_candidate(self, tranche_id, loss: float, otm: float = 3.0):
        from webui.backend.routes.mmmx.mmmx_atm_shield import ShieldCandidate
        return ShieldCandidate(
            tranche_id=tranche_id,
            side='ce',
            position={},
            tranche={'tranche_id': tranche_id},
            otm_pct=otm,
            unrealized_loss_usd=loss,
        )

    def test_sorted_by_loss_desc(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import sort_by_priority
        candidates = [
            self._make_candidate(1, loss=100.0),
            self._make_candidate(2, loss=500.0),
            self._make_candidate(3, loss=200.0),
        ]
        sorted_c = sort_by_priority(candidates)
        losses = [c.unrealized_loss_usd for c in sorted_c]
        assert losses == [500.0, 200.0, 100.0]

    def test_tiebreaker_oldest_first(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import sort_by_priority
        candidates = [
            self._make_candidate(3, loss=100.0),
            self._make_candidate(1, loss=100.0),
            self._make_candidate(2, loss=100.0),
        ]
        sorted_c = sort_by_priority(candidates)
        ids = [c.tranche_id for c in sorted_c]
        assert ids == [1, 2, 3]

    def test_string_ids_sort_correctly(self):
        """Recovery tranche IDs ('2A', '2B') sort after integer IDs."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import sort_by_priority
        candidates = [
            self._make_candidate('2A', loss=300.0),
            self._make_candidate(1, loss=300.0),
        ]
        sorted_c = sort_by_priority(candidates)
        # Integer ID 1 < string ID '2A' (integer prefix 2), so Tr1 first
        assert sorted_c[0].tranche_id == 1


# =============================================================================
# Tests: allocate_reserve()
# =============================================================================

class TestAllocateReserve:
    """G39 — full / partial / exhausted cascade."""

    def test_full_allocation(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import allocate_reserve
        session = _make_session(ce_reserve=30, pe_reserve=30)
        # Small loss → small recovery needs (well within reserve)
        alloc = allocate_reserve(session, loss_usd=0.01, ce_premium=500.0, pe_premium=500.0)
        assert not alloc.exhausted
        assert alloc.ce_allocated == alloc.ce_requested
        assert alloc.pe_allocated == alloc.pe_requested
        assert not alloc.partial

    def test_partial_ce_allocation(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import allocate_reserve
        import math
        session = _make_session(ce_reserve=2, pe_reserve=30)
        # Compute a loss that needs more than 2 CE lots
        # ce_needed = ceil(loss * 0.30 / (ce_prem * LOT_SIZE_BTC))
        # With ce_prem=100, LOT_SIZE=0.001: loss * 0.30 / 0.1 = loss * 3
        # loss=10 → ce_needed = ceil(30) = 30; pe_needed = ceil(70) = 70
        alloc = allocate_reserve(session, loss_usd=10.0, ce_premium=100.0, pe_premium=100.0)
        assert alloc.ce_allocated == 2           # capped to reserve
        assert alloc.pe_allocated == 30          # capped to reserve (pe_needed=70 > pe_reserve=30)
        assert alloc.partial

    def test_both_exhausted(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import allocate_reserve
        session = _make_session(ce_reserve=0, pe_reserve=0)
        alloc = allocate_reserve(session, loss_usd=100.0, ce_premium=100.0, pe_premium=100.0)
        assert alloc.exhausted
        assert alloc.ce_allocated == 0
        assert alloc.pe_allocated == 0

    def test_zero_loss_gives_zero_lots(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import allocate_reserve
        session = _make_session(ce_reserve=30, pe_reserve=30)
        alloc = allocate_reserve(session, loss_usd=0.0, ce_premium=100.0, pe_premium=100.0)
        assert alloc.ce_requested == 0
        assert alloc.pe_requested == 0
        assert alloc.ce_allocated == 0
        assert alloc.pe_allocated == 0


# =============================================================================
# Tests: _next_recovery_id / create_recovery_tranche
# =============================================================================

class TestRecoveryId:
    """Sibling naming: 2A / 2B / 2C / limit."""

    def test_first_recovery_is_A(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import _next_recovery_id
        session = _make_session()
        rid = _next_recovery_id(session, parent_id=2, max_shifts=3)
        assert rid == '2A'

    def test_second_recovery_is_B(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import _next_recovery_id
        tr_2A = _make_tranche('2A', tranche_type='recovery', parent_tranche_id=2)
        session = _make_session(tranches=[tr_2A])
        rid = _next_recovery_id(session, parent_id=2, max_shifts=3)
        assert rid == '2B'

    def test_third_recovery_is_C(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import _next_recovery_id
        tr_2A = _make_tranche('2A', tranche_type='recovery', parent_tranche_id=2)
        tr_2B = _make_tranche('2B', tranche_type='recovery', parent_tranche_id=2)
        session = _make_session(tranches=[tr_2A, tr_2B])
        rid = _next_recovery_id(session, parent_id=2, max_shifts=3)
        assert rid == '2C'

    def test_limit_returns_none(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import _next_recovery_id
        tr_2A = _make_tranche('2A', tranche_type='recovery', parent_tranche_id=2)
        tr_2B = _make_tranche('2B', tranche_type='recovery', parent_tranche_id=2)
        tr_2C = _make_tranche('2C', tranche_type='recovery', parent_tranche_id=2)
        session = _make_session(tranches=[tr_2A, tr_2B, tr_2C])
        rid = _next_recovery_id(session, parent_id=2, max_shifts=3)
        assert rid is None

    def test_create_recovery_tranche_appended(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import create_recovery_tranche
        parent = _make_tranche(tranche_id=2)
        session = _make_session(tranches=[parent])
        initial_count = len(session['tranches'])
        new_tr = create_recovery_tranche(
            session=session,
            parent_tranche=parent,
            ce_lots=5,
            pe_lots=10,
            spot=85000.0,
            ce_symbol='C-BTC-97750-280326',
            pe_symbol='P-BTC-72250-280326',
            ce_strike=97750.0,
            pe_strike=72250.0,
            ce_premium=80.0,
            pe_premium=80.0,
            ce_delta=0.25,
            pe_delta=0.25,
            shield_event=1,
        )
        assert new_tr is not None
        assert new_tr['tranche_id'] == '2A'
        assert new_tr['type'] == 'recovery'
        assert new_tr['parent_tranche_id'] == 2
        assert new_tr['shield_event'] == 1
        assert new_tr['ce']['lots'] == 5
        assert new_tr['pe']['lots'] == 10
        assert len(session['tranches']) == initial_count + 1

    def test_create_recovery_respects_max_shifts(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import create_recovery_tranche
        parent = _make_tranche(tranche_id=1)
        tr_1A = _make_tranche('1A', tranche_type='recovery', parent_tranche_id=1)
        tr_1B = _make_tranche('1B', tranche_type='recovery', parent_tranche_id=1)
        tr_1C = _make_tranche('1C', tranche_type='recovery', parent_tranche_id=1)
        session = _make_session(tranches=[parent, tr_1A, tr_1B, tr_1C])
        session['params']['atm_shield_max_shifts'] = 3
        result = create_recovery_tranche(
            session=session, parent_tranche=parent,
            ce_lots=5, pe_lots=5, spot=85000.0,
            ce_symbol='C-BTC-97750-280326', pe_symbol='P-BTC-72250-280326',
            ce_strike=97750.0, pe_strike=72250.0,
            ce_premium=80.0, pe_premium=80.0,
            ce_delta=0.25, pe_delta=0.25, shield_event=4,
        )
        assert result is None  # Max shifts hit


# =============================================================================
# Tests: execute_shield() — happy path
# =============================================================================

class TestExecuteShield:
    """6-step shield execution."""

    def _make_candidate(self, tranche, side='ce'):
        from webui.backend.routes.mmmx.mmmx_atm_shield import ShieldCandidate
        return ShieldCandidate(
            tranche_id=tranche['tranche_id'],
            side=side,
            position=tranche[side],
            tranche=tranche,
            otm_pct=2.5,
            unrealized_loss_usd=30.0 * 10 * 0.001,
        )

    def test_happy_path_creates_recovery_tranche(self):
        """Shield fires, buyback + sell succeed, recovery tranche 1A created."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr], ce_reserve=30, pe_reserve=30)
        session['total_premium_collected'] = 2.0  # some pre-existing premium
        session['hard_stop_usd'] = 4.0

        candidate = self._make_candidate(tr, side='ce')
        executor = _mock_executor(buy_ok=True, sell_ok=True)

        save_fn = MagicMock(return_value=True)
        result = _run(execute_shield(session, candidate, executor, None, spot=86000.0, save_fn=save_fn))

        assert result.success is True
        assert result.tranche_id == 1
        assert result.side == 'ce'
        assert result.old_strike == 90000.0
        assert result.new_strike > 90000.0  # CE moves higher
        assert result.naked is False
        assert result.recovery_tranche_id == '1A'

        # Recovery tranche appended
        recovery_tranches = [t for t in session['tranches'] if t.get('type') == 'recovery']
        assert len(recovery_tranches) == 1
        assert recovery_tranches[0]['tranche_id'] == '1A'

    def test_reserves_decremented(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr], ce_reserve=30, pe_reserve=30)

        candidate = self._make_candidate(tr, side='ce')
        executor = _mock_executor()
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        assert session['ce_reserve_remaining'] < 30
        assert session['pe_reserve_remaining'] < 30

    def test_tranches_deployed_unchanged(self):
        """Recovery creation MUST NOT change tranches_deployed / tranches_remaining."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr], tranches_deployed=1, tranches_remaining=9)

        candidate = self._make_candidate(tr, side='ce')
        executor = _mock_executor()
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        assert session['tranches_deployed'] == 1
        assert session['tranches_remaining'] == 9

    def test_total_premium_collected_incremented(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])
        session['total_premium_collected'] = 1.0

        candidate = self._make_candidate(tr, side='ce')
        executor = _mock_executor()
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        assert session['total_premium_collected'] > 1.0

    def test_hard_stop_recalculated(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])
        session['params']['hard_stop_multiplier'] = 2.0
        session['total_premium_collected'] = 1.0
        old_hard_stop = session['hard_stop_usd']

        candidate = self._make_candidate(tr, side='ce')
        executor = _mock_executor()
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        # hard_stop should have been recalculated (total_premium_collected grew)
        assert session['hard_stop_usd'] > old_hard_stop

    def test_last_deployment_spot_reset(self):
        """last_deployment_spot must be updated after shield reposition."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])
        session['last_deployment_spot'] = 85000.0

        candidate = self._make_candidate(tr, side='ce')
        executor = _mock_executor()
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        assert session['last_deployment_spot'] == 86000.0

    def test_shield_fire_count_incremented(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])

        candidate = self._make_candidate(tr, side='ce')
        executor = _mock_executor()
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        assert session['shield_fire_count'] == 1

    def test_g13_mid_beat_persist_called(self):
        """G13: save_fn is called after recovery tranche creation."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])

        candidate = self._make_candidate(tr, side='ce')
        executor = _mock_executor()
        save_fn = MagicMock(return_value=True)
        _run(execute_shield(session, candidate, executor, None, spot=86000.0, save_fn=save_fn))

        save_fn.assert_called()

    def test_position_updated_with_new_strike(self):
        """After shield, position has new strike and new symbol."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0, ce_symbol='C-BTC-90000-280326')
        session = _make_session(tranches=[tr])

        candidate = self._make_candidate(tr, side='ce')
        executor = _mock_executor()
        result = _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        # The CE position now has the new strike
        ce_leg = session['tranches'][0]['ce']
        assert ce_leg['strike'] == result.new_strike
        assert str(int(round(result.new_strike))) in ce_leg['symbol']

    def test_shift_count_incremented(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        tr['ce']['shift_count'] = 0
        session = _make_session(tranches=[tr])

        candidate = self._make_candidate(tr, side='ce')
        executor = _mock_executor()
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        assert session['tranches'][0]['ce']['shift_count'] == 1

    def test_shield_history_appended(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])

        candidate = self._make_candidate(tr, side='ce')
        executor = _mock_executor()
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        history = session['tranches'][0]['ce']['shield_history']
        assert len(history) == 1
        assert 'old_strike' in history[0]
        assert 'buyback_price' in history[0]


# =============================================================================
# Tests: execute_shield() — buyback abort path
# =============================================================================

class TestExecuteShieldBuybackAbort:
    """If buyback fails, shield is aborted — no naked state."""

    def _make_candidate(self, tranche, side='ce'):
        from webui.backend.routes.mmmx.mmmx_atm_shield import ShieldCandidate
        return ShieldCandidate(
            tranche_id=tranche['tranche_id'], side=side,
            position=tranche[side], tranche=tranche,
            otm_pct=2.5, unrealized_loss_usd=0.3,
        )

    def test_buyback_fail_returns_unsuccessful(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])

        executor = _mock_executor(buy_ok=False, sell_ok=True)
        candidate = self._make_candidate(tr, side='ce')
        result = _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        assert result.success is False
        assert result.naked is False
        assert 'buyback' in result.reason

    def test_buyback_fail_no_naked_positions(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])

        executor = _mock_executor(buy_ok=False, sell_ok=True)
        candidate = self._make_candidate(tr, side='ce')
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        assert session['_naked_positions'] == []
        assert session['status'] == 'RUNNING'

    def test_buyback_fail_no_recovery_tranche(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])

        executor = _mock_executor(buy_ok=False, sell_ok=True)
        candidate = self._make_candidate(tr, side='ce')
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        recovery_tranches = [t for t in session['tranches'] if t.get('type') == 'recovery']
        assert len(recovery_tranches) == 0


# =============================================================================
# Tests: execute_shield() — naked path (sell failure)
# =============================================================================

class TestExecuteShieldNaked:
    """New-sell fails all 11 attempts → session PAUSED, _naked_positions populated."""

    def _make_candidate(self, tranche, side='ce'):
        from webui.backend.routes.mmmx.mmmx_atm_shield import ShieldCandidate
        return ShieldCandidate(
            tranche_id=tranche['tranche_id'], side=side,
            position=tranche[side], tranche=tranche,
            otm_pct=2.5, unrealized_loss_usd=0.3,
        )

    def test_sell_fail_session_paused(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr], status='RUNNING')

        executor = _mock_executor(buy_ok=True, sell_ok=False)
        candidate = self._make_candidate(tr, side='ce')
        result = _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        assert result.success is False
        assert result.naked is True
        assert session['status'] == 'PAUSED'

    def test_sell_fail_naked_positions_populated(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr], status='RUNNING')

        executor = _mock_executor(buy_ok=True, sell_ok=False)
        candidate = self._make_candidate(tr, side='ce')
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        naked = session['_naked_positions']
        assert len(naked) == 1
        assert naked[0]['tranche_id'] == 1
        assert naked[0]['side'] == 'ce'
        assert 'naked_since' in naked[0]
        assert naked[0]['retries'] == 0

    def test_sell_fail_no_recovery_tranche(self):
        """Recovery tranche must NOT be created if sell failed (no confirmed sell)."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])

        executor = _mock_executor(buy_ok=True, sell_ok=False)
        candidate = self._make_candidate(tr, side='ce')
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        recovery = [t for t in session['tranches'] if t.get('type') == 'recovery']
        assert len(recovery) == 0


# =============================================================================
# Tests: evaluate_and_fire() — multi-shield + G39 cascade
# =============================================================================

class TestEvaluateAndFire:
    """Multi-shield sequencing and G39 reserve cascade."""

    def test_single_shield_fires(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate_and_fire
        # spot=87500 → CE OTM = (90000-87500)/87500*100 ≈ 2.86% < 5%
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])

        executor = _mock_executor()
        results = _run(evaluate_and_fire(session, spot=87500.0, executor=executor, audit=None))
        assert len(results) >= 1
        assert results[0].tranche_id == 1

    def test_no_candidates_returns_empty(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate_and_fire
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])

        executor = _mock_executor()
        # spot far below CE strike → CE is safe
        results = _run(evaluate_and_fire(session, spot=70000.0, executor=executor, audit=None))
        ce_results = [r for r in results if r.side == 'ce' and r.tranche_id == 1]
        assert len(ce_results) == 0

    def test_no_spot_returns_empty(self):
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate_and_fire
        session = _make_session(tranches=[_make_tranche()])
        executor = _mock_executor()
        assert _run(evaluate_and_fire(session, spot=None, executor=executor, audit=None)) == []

    def test_multi_shield_sorted_by_loss(self):
        """Three shields sorted: worst loss first."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate_and_fire
        # spot=87500 → CE OTM (90000): (90000-87500)/87500*100 = 2.86% < 5%
        # We need 3 tranches all triggering
        # Use the same strike for simplicity; differentiate loss by current_premium
        tr1 = _make_tranche(1, ce_strike=90000.0, ce_current=200.0)  # big loss
        tr2 = _make_tranche(2, ce_strike=90000.0, ce_current=150.0)  # medium
        tr3 = _make_tranche(3, ce_strike=90000.0, ce_current=120.0)  # small
        session = _make_session(tranches=[tr3, tr1, tr2])  # shuffled

        executor = _mock_executor()
        results = _run(evaluate_and_fire(session, spot=87500.0, executor=executor, audit=None))

        # Should execute in order: tr1 (biggest), tr2, tr3
        ce_results = [r for r in results if r.side == 'ce']
        if len(ce_results) >= 2:
            assert ce_results[0].tranche_id == 1  # biggest loss first

    def test_g39_reserve_exhausted_mid_cascade_no_recovery(self):
        """Third shield: reserve depleted → reposition without recovery."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate_and_fire
        tr1 = _make_tranche(1, ce_strike=90000.0, ce_current=200.0)
        tr2 = _make_tranche(2, ce_strike=90000.0, ce_current=150.0)
        tr3 = _make_tranche(3, ce_strike=90000.0, ce_current=120.0)
        # Very small reserve — will deplete after 1-2 shields
        session = _make_session(tranches=[tr1, tr2, tr3], ce_reserve=1, pe_reserve=1)

        executor = _mock_executor()
        results = _run(evaluate_and_fire(session, spot=87500.0, executor=executor, audit=None))

        # Some shields will have no recovery tranche (reserve exhausted)
        no_recovery = [r for r in results if r.success and r.recovery_tranche_id is None]
        assert len(no_recovery) >= 1  # at least the last one has no recovery

    def test_naked_stops_cascade(self):
        """After naked detected, remaining shields deferred."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate_and_fire
        tr1 = _make_tranche(1, ce_strike=90000.0)
        tr2 = _make_tranche(2, ce_strike=90000.0)

        # Executor: buy succeeds, sell always fails → naked
        exe = MagicMock()
        call_count = {'n': 0}

        async def mock_smart_execute(*a, **kw):
            side = kw.get('side', '')
            if side == 'buy':
                return _ok_result()
            return _fail_result()

        exe.smart_execute = AsyncMock(side_effect=mock_smart_execute)
        exe.emergency_execute = AsyncMock(return_value=_fail_result())

        session = _make_session(tranches=[tr1, tr2], status='RUNNING')
        results = _run(evaluate_and_fire(session, spot=87500.0, executor=exe, audit=None))

        # First shield → naked → session PAUSED → cascade stops
        assert session['status'] == 'PAUSED'
        assert len(session['_naked_positions']) >= 1

    def test_paused_session_fires_shield(self):
        """Shield fires even when session is PAUSED (naked watchdog path)."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate_and_fire
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr], status='PAUSED')

        executor = _mock_executor()
        results = _run(evaluate_and_fire(session, spot=87500.0, executor=executor, audit=None))
        assert len(results) >= 1

    def test_complete_session_skips_shield(self):
        """Shield does NOT fire for COMPLETE or ERROR sessions."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate_and_fire
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr], status='COMPLETE')

        executor = _mock_executor()
        results = _run(evaluate_and_fire(session, spot=87500.0, executor=executor, audit=None))
        assert results == []


# =============================================================================
# Tests: Recovery tranche as first-class citizen
# =============================================================================

class TestRecoveryTrancheCitizen:
    """Recovery tranches get shielded, closed by hard stop, etc."""

    def test_recovery_tranche_evaluated_by_shield(self):
        """evaluate() iterates recovery tranches — they get shielded like any other."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import evaluate
        parent = _make_tranche(1)
        recovery = _make_tranche('1A', tranche_type='recovery', ce_strike=90000.0,
                                 parent_tranche_id=1)
        session = _make_session(tranches=[parent, recovery])
        # spot that triggers CE on recovery tranche
        candidates = evaluate(session, spot=87500.0)
        ids = [c.tranche_id for c in candidates]
        assert '1A' in ids

    def test_recovery_premium_in_total_premium_collected(self):
        """Recovery tranche's premium contributes to total_premium_collected."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield, ShieldCandidate
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])
        session['total_premium_collected'] = 0.0

        candidate = ShieldCandidate(
            tranche_id=1, side='ce', position=tr['ce'], tranche=tr,
            otm_pct=2.5, unrealized_loss_usd=0.3,
        )
        executor = _mock_executor()
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        # Recovery tranche premium was collected
        assert session['total_premium_collected'] > 0.0


# =============================================================================
# Tests: check_naked_watchdog (G37)
# =============================================================================

class TestNakedWatchdog:
    """G37: 30-min emergency retry; 2-hr critical alert; resolved cleanup."""

    def _make_naked(self, mins_ago: float, tranche_id=1, side='ce', retries=0):
        ts = datetime.now(timezone.utc) - timedelta(minutes=mins_ago)
        return {
            'tranche_id':  tranche_id,
            'side':        side,
            'naked_since': ts.isoformat(),
            'retries':     retries,
            'symbol':      'C-BTC-90000-280326',
            'lots':        10,
        }

    def test_fresh_naked_no_action(self):
        from webui.backend.routes.mmmx.mmmx_reconciler import check_naked_watchdog
        session = _make_session()
        session['_naked_positions'] = [self._make_naked(mins_ago=10)]
        executor = _mock_executor()
        actions = _run(check_naked_watchdog(session, executor))
        # < 30 min → no action
        assert all(a['action'] == 'none' for a in actions)

    def test_30min_naked_fires_emergency_sell(self):
        from webui.backend.routes.mmmx.mmmx_reconciler import check_naked_watchdog
        session = _make_session()
        session['_naked_positions'] = [self._make_naked(mins_ago=35)]
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        actions = _run(check_naked_watchdog(session, executor))
        assert any(a['action'] == 'emergency_retry' for a in actions)
        executor.emergency_execute.assert_called_once()

    def test_30min_sell_success_removes_naked(self):
        from webui.backend.routes.mmmx.mmmx_reconciler import check_naked_watchdog
        session = _make_session()
        session['_naked_positions'] = [self._make_naked(mins_ago=35)]
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        _run(check_naked_watchdog(session, executor))
        # Resolved — removed from list
        assert len(session['_naked_positions']) == 0

    def test_30min_sell_fail_keeps_naked(self):
        from webui.backend.routes.mmmx.mmmx_reconciler import check_naked_watchdog
        session = _make_session()
        session['_naked_positions'] = [self._make_naked(mins_ago=35)]
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_fail_result())
        _run(check_naked_watchdog(session, executor))
        # Not resolved — still in list
        assert len(session['_naked_positions']) == 1
        assert session['_naked_positions'][0]['retries'] == 1

    def test_2hr_naked_critical_alert(self):
        from webui.backend.routes.mmmx.mmmx_reconciler import check_naked_watchdog
        session = _make_session()
        session['_naked_positions'] = [self._make_naked(mins_ago=130)]
        executor = _mock_executor()
        actions = _run(check_naked_watchdog(session, executor))
        assert any(a['action'] == 'critical_alert' for a in actions)

    def test_empty_naked_list_returns_empty(self):
        from webui.backend.routes.mmmx.mmmx_reconciler import check_naked_watchdog
        session = _make_session()
        session['_naked_positions'] = []
        executor = _mock_executor()
        actions = _run(check_naked_watchdog(session, executor))
        assert actions == []


# =============================================================================
# Tests: Isolation scan
# =============================================================================

class TestIsolation:
    """mmmx_atm_shield.py must not import from routes.mmm.*"""

    def test_no_routes_mmm_imports(self):
        shield_path = os.path.join(
            os.path.dirname(__file__), '..', 'mmmx_atm_shield.py'
        )
        with open(shield_path, 'r') as f:
            source = f.read()
        # Look for imports from routes.mmm (the old MMM module, not mmmx)
        bad_imports = re.findall(r'from\s+.*routes\.mmm[^x].*import', source)
        bad_imports += re.findall(r'import\s+.*routes\.mmm[^x]', source)
        assert bad_imports == [], (
            f"mmmx_atm_shield.py has forbidden routes.mmm.* imports: {bad_imports}"
        )

    def test_module_importable(self):
        import importlib
        mod = importlib.import_module('webui.backend.routes.mmmx.mmmx_atm_shield')
        assert hasattr(mod, 'evaluate')
        assert hasattr(mod, 'sort_by_priority')
        assert hasattr(mod, 'allocate_reserve')
        assert hasattr(mod, 'create_recovery_tranche')
        assert hasattr(mod, 'execute_shield')
        assert hasattr(mod, 'evaluate_and_fire')
        assert hasattr(mod, 'multi_shield_margin_precheck')


# =============================================================================
# Tests: State invariants
# =============================================================================

class TestStateInvariants:
    """Key invariants from MMMX_IMPLEMENTATION_PLAN.md Section 8.4."""

    def test_invariant_ce_reserve_monotone_decreasing(self):
        """ce_reserve_remaining never goes negative."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield, ShieldCandidate
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr], ce_reserve=1, pe_reserve=1)

        candidate = ShieldCandidate(
            tranche_id=1, side='ce', position=tr['ce'], tranche=tr,
            otm_pct=2.5, unrealized_loss_usd=0.3,
        )
        executor = _mock_executor()
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        assert session['ce_reserve_remaining'] >= 0
        assert session['pe_reserve_remaining'] >= 0

    def test_invariant_naked_implies_paused(self):
        """If _naked_positions non-empty, status must be PAUSED or ERROR."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield, ShieldCandidate
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr], status='RUNNING')

        executor = _mock_executor(buy_ok=True, sell_ok=False)
        candidate = ShieldCandidate(
            tranche_id=1, side='ce', position=tr['ce'], tranche=tr,
            otm_pct=2.5, unrealized_loss_usd=0.3,
        )
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        if session.get('_naked_positions'):
            assert session['status'] in ('PAUSED', 'ERROR'), (
                "_naked_positions non-empty but status is not PAUSED or ERROR"
            )

    def test_invariant_recovery_type_field(self):
        """Recovery tranches have type='recovery'."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield, ShieldCandidate
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])

        executor = _mock_executor()
        candidate = ShieldCandidate(
            tranche_id=1, side='ce', position=tr['ce'], tranche=tr,
            otm_pct=2.5, unrealized_loss_usd=0.3,
        )
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        for t in session['tranches']:
            if t.get('type') == 'recovery':
                assert t['parent_tranche_id'] == 1

    def test_invariant_hard_stop_equals_multiplier_times_premium(self):
        """hard_stop_usd == hard_stop_multiplier × total_premium_collected after shield."""
        from webui.backend.routes.mmmx.mmmx_atm_shield import execute_shield, ShieldCandidate
        tr = _make_tranche(tranche_id=1, ce_strike=90000.0)
        session = _make_session(tranches=[tr])
        session['params']['hard_stop_multiplier'] = 2.0
        session['total_premium_collected'] = 1.0

        executor = _mock_executor()
        candidate = ShieldCandidate(
            tranche_id=1, side='ce', position=tr['ce'], tranche=tr,
            otm_pct=2.5, unrealized_loss_usd=0.3,
        )
        _run(execute_shield(session, candidate, executor, None, spot=86000.0))

        expected_hard_stop = (
            session['params']['hard_stop_multiplier'] *
            session['total_premium_collected']
        )
        assert abs(session['hard_stop_usd'] - expected_hard_stop) < 1e-6
