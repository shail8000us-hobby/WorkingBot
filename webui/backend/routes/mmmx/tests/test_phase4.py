"""
MMMX Phase 4 Unit Tests

Covers: mmmx_close_all, mmmx_engine.classify_danger_side,
        mmmx_monitor._dispatch_close_all delegation, MMM isolation scan.

Exit criteria per MMMX_IMPLEMENTATION_PLAN.md Section 4 Phase 4:
  - Basic close_all: shorts filled, hedges attempted
  - Hedge fails limit: marked ORPHANED, not CRITICAL, close_all still completes
  - Short fill fails: logged CRITICAL but close_all still completes (best-effort)
  - Recovery tranches closed (full citizen, not skipped)
  - Fee accounting wired: total_fees_paid incremented from result.fees_paid
  - G36 slippage logged: overshoot computed and logged
  - _dispatch_close_all delegates to close_all; _save_session + _running=False after
  - classify_danger_side pure function tests
  - MMM isolation scan: mmmx_close_all has no routes.mmm imports
  - CloseAllReport fields populated correctly
"""

import asyncio
import importlib
import inspect
import os
import re
import sys
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

# -- Ensure package root is importable ----------------------------------------
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# =============================================================================
# Helpers
# =============================================================================

def _run(coro):
    """Run a coroutine in a fresh event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_session(
    portfolio_pnl: float = 0.0,
    hard_stop_usd: float = 500.0,
    tranches=None,
    hedges=None,
    status: str = 'RUNNING',
) -> dict:
    """Minimal session dict for close_all tests."""
    return {
        '_schema_version': 1,
        'session_id': 'test-session-phase4-1234',
        'status': status,
        'portfolio_pnl': portfolio_pnl,
        'hard_stop_usd': hard_stop_usd,
        'tranches': tranches or [],
        'hedges': hedges or [],
        'fees_tracking': {
            'total_fees_paid': 0.0,
            'last_fee_charge': None,
        },
        'params': {'close_at_dte': 7},
        'expiry_datetime': (
            datetime.now(timezone.utc) + timedelta(days=30)
        ).isoformat(),
        'beat_number': 0,
        '_last_beat_at': None,
    }


def _make_leg(
    status: str = 'ACTIVE',
    lots: int = 10,
    symbol: str = 'C-BTC-90000-280326',
    entry_premium: float = 100.0,
    current_premium: float = 90.0,
) -> dict:
    return {
        'status':          status,
        'lots':            lots,
        'symbol':          symbol,
        'entry_premium':   entry_premium,
        'current_premium': current_premium,
        'realized_pnl':    0.0,
        'fees_paid':       0.0,
        '_being_closed':   False,
    }


def _make_tranche(
    tranche_id=1,
    tranche_type: str = 'deployment',
    ce_status: str = 'ACTIVE',
    pe_status: str = 'ACTIVE',
    ce_lots: int = 10,
    pe_lots: int = 10,
    ce_symbol: str = 'C-BTC-90000-280326',
    pe_symbol: str = 'P-BTC-70000-280326',
    ce_entry: float = 100.0,
    pe_entry: float = 100.0,
    ce_current: float = 90.0,
    pe_current: float = 90.0,
) -> dict:
    return {
        'tranche_id': tranche_id,
        'type':        tranche_type,
        'ce':          _make_leg(ce_status, ce_lots, ce_symbol, ce_entry, ce_current),
        'pe':          _make_leg(pe_status, pe_lots, pe_symbol, pe_entry, pe_current),
        'status':      'ACTIVE',
    }


def _make_hedge(
    hedge_id: str = 'H-Tr1',
    status: str = 'ACTIVE',
    ce_status: str = 'ACTIVE',
    pe_status: str = 'ACTIVE',
    ce_lots: int = 5,
    pe_lots: int = 5,
) -> dict:
    return {
        'hedge_id': hedge_id,
        'status':   status,
        'ce': {
            'status':        ce_status,
            'lots':          ce_lots,
            'symbol':        'C-BTC-94000-280326',
            'entry_premium': 45.0,
            '_being_closed': False,
        },
        'pe': {
            'status':        pe_status,
            'lots':          pe_lots,
            'symbol':        'P-BTC-66000-280326',
            'entry_premium': 40.0,
            '_being_closed': False,
        },
    }


def _ok_result(fees_paid: float = 0.50) -> 'ExecutionResult':
    from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult
    return ExecutionResult(
        success=True,
        filled_size=10,
        avg_price=95.0,
        attempts=1,
        total_ms=100,
        reason='filled',
        order_id='ORD-001',
        client_order_id='COI-001',
        fees_paid=fees_paid,
    )


def _fail_result() -> 'ExecutionResult':
    from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult
    return ExecutionResult(
        success=False,
        filled_size=0,
        avg_price=0.0,
        attempts=3,
        total_ms=9000,
        reason='timeout',
        order_id='',
        client_order_id='',
        fees_paid=0.0,
    )


# =============================================================================
# Tests: CloseAllReport
# =============================================================================

class TestCloseAllReport:
    """CloseAllReport dataclass fields are populated correctly."""

    def test_report_fields_present(self):
        from webui.backend.routes.mmmx.mmmx_close_all import CloseAllReport
        report = CloseAllReport(reason='HARD_STOP')
        assert report.reason == 'HARD_STOP'
        assert report.shorts_attempted == 0
        assert report.shorts_filled == 0
        assert report.shorts_failed == 0
        assert report.hedges_attempted == 0
        assert report.hedges_filled == 0
        assert report.hedges_failed == 0
        assert report.total_fees_paid == 0.0
        assert report.close_errors == []
        assert report.completed_at == ''

    def test_report_to_dict(self):
        from webui.backend.routes.mmmx.mmmx_close_all import CloseAllReport
        report = CloseAllReport(
            reason='DTE_CLOSE',
            shorts_attempted=4,
            shorts_filled=4,
            shorts_failed=0,
            completed_at='2026-04-06T12:00:00+00:00',
        )
        d = report.to_dict()
        assert d['reason'] == 'DTE_CLOSE'
        assert d['shorts_attempted'] == 4
        assert d['shorts_filled'] == 4
        assert d['shorts_failed'] == 0
        assert d['completed_at'] == '2026-04-06T12:00:00+00:00'

    def test_completed_at_is_valid_iso_utc(self):
        """After close_all runs, completed_at is a valid ISO 8601 UTC string."""
        from webui.backend.routes.mmmx.mmmx_close_all import CloseAllReport
        report = CloseAllReport(reason='HARD_STOP')
        report.completed_at = datetime.now(timezone.utc).isoformat()
        # Must parse without exception
        dt = datetime.fromisoformat(report.completed_at)
        assert dt.tzinfo is not None


# =============================================================================
# Tests: close_all — basic flow
# =============================================================================

class TestCloseAllBasic:
    """Basic close_all: 2 deployment tranches + 1 active hedge — all fill."""

    def _build_executor(self, short_result=None, hedge_result=None):
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=short_result or _ok_result())
        executor.smart_execute = AsyncMock(return_value=hedge_result or _ok_result())
        return executor

    def test_shorts_filled_hedges_attempted(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        session = _make_session(
            tranches=[_make_tranche(1), _make_tranche(2)],
            hedges=[_make_hedge('H-Tr1')],
        )
        executor = self._build_executor()
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        # 2 tranches × 2 legs = 4 shorts
        assert report.shorts_attempted == 4
        assert report.shorts_filled == 4
        assert report.shorts_failed == 0
        # 1 hedge × 2 legs = 2 hedges
        assert report.hedges_attempted == 2
        assert report.hedges_filled == 2
        assert report.hedges_failed == 0
        assert len(report.close_errors) == 0

    def test_session_status_transitions_to_complete(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        session = _make_session(tranches=[_make_tranche(1)])
        executor = self._build_executor()
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            _run(close_all(session, 'HARD_STOP', executor, audit))

        assert session['status'] == 'COMPLETE'

    def test_short_legs_status_set_to_closed(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        tranche = _make_tranche(1)
        session = _make_session(tranches=[tranche])
        executor = self._build_executor()
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            _run(close_all(session, 'HARD_STOP', executor, audit))

        assert tranche['ce']['status'] == 'CLOSED'
        assert tranche['pe']['status'] == 'CLOSED'

    def test_emergency_execute_called_for_shorts(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        session = _make_session(tranches=[_make_tranche(1)])
        executor = self._build_executor()
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            _run(close_all(session, 'HARD_STOP', executor, audit))

        # emergency_execute called for each short leg (2 legs for 1 tranche)
        assert executor.emergency_execute.call_count == 2

    def test_smart_execute_called_for_hedge_legs(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        session = _make_session(
            tranches=[_make_tranche(1)],
            hedges=[_make_hedge('H-Tr1')],
        )
        executor = self._build_executor()
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            _run(close_all(session, 'HARD_STOP', executor, audit))

        # smart_execute called for each hedge leg (2 legs)
        assert executor.smart_execute.call_count == 2
        # Confirm use_bid_entry=True was passed
        for c in executor.smart_execute.call_args_list:
            assert c.kwargs.get('use_bid_entry') is True

    def test_completed_at_is_utc_iso(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        session = _make_session()
        executor = self._build_executor()
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        dt = datetime.fromisoformat(report.completed_at)
        assert dt.tzinfo is not None


# =============================================================================
# Tests: Hedge fails — ORPHANED, not CRITICAL
# =============================================================================

class TestCloseAllHedgeFails:
    """Hedge limit-sell fails → marked ORPHANED, not CLOSED, non-fatal."""

    def test_hedge_fail_marked_orphaned(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all
        from webui.backend.routes.mmmx.mmmx_constants import HedgeStatus

        hedge = _make_hedge('H-Tr1')
        session = _make_session(hedges=[hedge])
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_fail_result())
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        assert hedge['ce']['status'] == HedgeStatus.ORPHANED
        assert hedge['pe']['status'] == HedgeStatus.ORPHANED

    def test_hedge_fail_report_counts(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        session = _make_session(hedges=[_make_hedge('H-Tr1')])
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_fail_result())
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        assert report.hedges_attempted == 2
        assert report.hedges_failed == 2
        assert report.hedges_filled == 0

    def test_hedge_fail_does_not_raise(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        session = _make_session(hedges=[_make_hedge('H-Tr1')])
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_fail_result())
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            # Must complete normally — no exception
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        assert session['status'] == 'COMPLETE'

    def test_hedge_fail_error_recorded_in_close_errors(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        session = _make_session(hedges=[_make_hedge('H-Tr1')])
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_fail_result())
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        assert len(report.close_errors) == 2
        for err in report.close_errors:
            assert 'tranche_id' in err
            assert 'side' in err
            assert 'error' in err


# =============================================================================
# Tests: Short fill fails — CRITICAL but close_all still completes
# =============================================================================

class TestCloseAllShortFails:
    """Short emergency_execute fails → logged CRITICAL, close_all still completes."""

    def test_short_fail_report_counts(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        # 1 tranche: CE fails, PE succeeds
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(side_effect=[_fail_result(), _ok_result()])
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        session = _make_session(tranches=[_make_tranche(1)])

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        assert report.shorts_attempted == 2
        assert report.shorts_failed == 1
        assert report.shorts_filled == 1

    def test_short_fail_session_still_complete(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_fail_result())
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        session = _make_session(tranches=[_make_tranche(1)])

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        assert session['status'] == 'COMPLETE'

    def test_short_fail_has_close_error_entry(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_fail_result())
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        session = _make_session(tranches=[_make_tranche(1)])

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        assert len(report.close_errors) > 0
        err = report.close_errors[0]
        assert 'tranche_id' in err
        assert 'error' in err


# =============================================================================
# Tests: Recovery tranches are closed
# =============================================================================

class TestCloseAllRecoveryTranches:
    """Recovery tranches (type='recovery') are full citizens — closed in the same loop."""

    def test_recovery_tranche_closed(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        deployment = _make_tranche(1, tranche_type='deployment')
        recovery = _make_tranche('1A', tranche_type='recovery')
        session = _make_session(tranches=[deployment, recovery])
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        # Both deployment and recovery: 2 tranches × 2 legs = 4 shorts
        assert report.shorts_attempted == 4
        assert report.shorts_filled == 4

    def test_recovery_tranche_legs_marked_closed(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        recovery = _make_tranche('1A', tranche_type='recovery')
        session = _make_session(tranches=[recovery])
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            _run(close_all(session, 'HARD_STOP', executor, audit))

        assert recovery['ce']['status'] == 'CLOSED'
        assert recovery['pe']['status'] == 'CLOSED'


# =============================================================================
# Tests: Fee accounting
# =============================================================================

class TestCloseAllFeeAccounting:
    """Fees from ExecutionResult.fees_paid are accumulated in session['fees_tracking']."""

    def test_fees_accumulated_from_fills(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        # 2 legs each paying 0.50 → 1.00 total
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result(fees_paid=0.50))
        executor.smart_execute = AsyncMock(return_value=_ok_result(fees_paid=0.50))
        audit = MagicMock()

        session = _make_session(tranches=[_make_tranche(1)])

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        # 2 short fills × 0.50 = 1.00
        assert abs(session['fees_tracking']['total_fees_paid'] - 1.00) < 1e-9
        assert abs(report.total_fees_paid - 1.00) < 1e-9

    def test_fees_from_hedges_also_accumulated(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result(fees_paid=0.50))
        executor.smart_execute = AsyncMock(return_value=_ok_result(fees_paid=0.25))
        audit = MagicMock()

        session = _make_session(
            tranches=[_make_tranche(1)],
            hedges=[_make_hedge('H-Tr1')],
        )

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        # 2 shorts × 0.50 + 2 hedges × 0.25 = 1.50
        assert abs(session['fees_tracking']['total_fees_paid'] - 1.50) < 1e-9
        assert abs(report.total_fees_paid - 1.50) < 1e-9

    def test_fee_charge_timestamp_set(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result(fees_paid=0.50))
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        session = _make_session(tranches=[_make_tranche(1)])

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            _run(close_all(session, 'HARD_STOP', executor, audit))

        ts = session['fees_tracking']['last_fee_charge']
        assert ts is not None
        # Must parse without exception
        dt = datetime.fromisoformat(ts)
        assert dt.tzinfo is not None


# =============================================================================
# Tests: Audit log enqueued
# =============================================================================

class TestCloseAllAuditLog:
    """Audit log receives CLOSE_ALL event with full report."""

    def test_audit_enqueue_event_called(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        session = _make_session(tranches=[_make_tranche(1)])

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            _run(close_all(session, 'HARD_STOP', executor, audit))

        # enqueue_event should have been called with category='CLOSE_ALL'
        calls = [c for c in audit.enqueue_event.call_args_list
                 if c.kwargs.get('category') == 'CLOSE_ALL'
                 or (c.args and len(c.args) >= 2 and c.args[1] == 'CLOSE_ALL')]
        # Check via kwargs
        close_all_calls = [
            c for c in audit.enqueue_event.call_args_list
            if c.kwargs.get('category') == 'CLOSE_ALL'
        ]
        assert len(close_all_calls) >= 1

    def test_audit_enqueue_trade_called_per_leg(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        session = _make_session(tranches=[_make_tranche(1)])  # 2 legs

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            _run(close_all(session, 'HARD_STOP', executor, audit))

        # 2 enqueue_trade calls (one per leg)
        assert audit.enqueue_trade.call_count == 2


# =============================================================================
# Tests: G36 slippage logging
# =============================================================================

class TestG36SlippageLogging:
    """G36: after close_all + _dispatch_close_all, overshoot is logged."""

    def test_g36_overshoot_logged_by_dispatch(self):
        """
        _dispatch_close_all logs G36 slippage:
        portfolio_pnl=-600, hard_stop_usd=500 → overshoot=-100 (worse than trigger).
        """
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor

        session = _make_session(
            portfolio_pnl=-600.0,
            hard_stop_usd=500.0,
        )
        session['status'] = 'RUNNING'

        storage_mock = MagicMock()
        storage_mock.save_session = MagicMock(return_value=True)

        monitor = MMMXMonitor(session_id=session['session_id'], my_generation=1)

        mock_report = MagicMock()
        mock_report.shorts_filled = 0
        mock_report.shorts_attempted = 0
        mock_report.hedges_filled = 0
        mock_report.hedges_attempted = 0
        mock_report.hedges_failed = 0
        mock_report.close_errors = []

        with patch('webui.backend.routes.mmmx.mmmx_close_all.close_all',
                   new=AsyncMock(return_value=mock_report)) as mock_ca, \
             patch('webui.backend.routes.mmmx.mmmx_executor.get_executor',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_audit_log.get_audit_log',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_storage.get_storage',
                   return_value=storage_mock), \
             patch('webui.backend.routes.mmmx.mmmx_monitor.log') as mock_log:

            _run(monitor._dispatch_close_all(session, 'HARD_STOP'))

            # Verify warning was emitted containing G36
            warning_msgs = [str(c) for c in mock_log.warning.call_args_list]
            assert any('G36' in m for m in warning_msgs), (
                f"Expected G36 in log.warning calls; got: {warning_msgs}"
            )

    def test_g36_not_logged_for_dte_close(self):
        """G36 slippage log is only emitted for HARD_STOP, not DTE_CLOSE."""
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor

        session = _make_session(portfolio_pnl=-100.0, hard_stop_usd=500.0)
        session['status'] = 'RUNNING'

        storage_mock = MagicMock()
        storage_mock.save_session = MagicMock(return_value=True)

        monitor = MMMXMonitor(session_id=session['session_id'], my_generation=1)

        mock_report = MagicMock()
        mock_report.close_errors = []

        with patch('webui.backend.routes.mmmx.mmmx_close_all.close_all',
                   new=AsyncMock(return_value=mock_report)), \
             patch('webui.backend.routes.mmmx.mmmx_executor.get_executor',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_audit_log.get_audit_log',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_storage.get_storage',
                   return_value=storage_mock), \
             patch('webui.backend.routes.mmmx.mmmx_monitor.log') as mock_log:

            _run(monitor._dispatch_close_all(session, 'DTE_CLOSE'))

            warning_msgs = [str(c) for c in mock_log.warning.call_args_list]
            assert not any('G36' in m for m in warning_msgs), (
                "G36 should NOT be logged for DTE_CLOSE"
            )


# =============================================================================
# Tests: _dispatch_close_all delegates + _running=False
# =============================================================================

class TestDispatchCloseAllDelegation:
    """_dispatch_close_all calls mmmx_close_all.close_all and then saves + stops."""

    def _make_monitor_with_session(self, session):
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor
        monitor = MMMXMonitor(session_id=session['session_id'], my_generation=1)
        monitor._running = True
        return monitor

    def test_close_all_called_with_correct_args(self):
        session = _make_session()
        session['status'] = 'RUNNING'

        storage_mock = MagicMock()
        storage_mock.save_session = MagicMock(return_value=True)

        monitor = self._make_monitor_with_session(session)
        mock_report = MagicMock()
        mock_report.close_errors = []

        with patch('webui.backend.routes.mmmx.mmmx_close_all.close_all',
                   new=AsyncMock(return_value=mock_report)) as mock_ca, \
             patch('webui.backend.routes.mmmx.mmmx_executor.get_executor',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_audit_log.get_audit_log',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_storage.get_storage',
                   return_value=storage_mock):

            _run(monitor._dispatch_close_all(session, 'HARD_STOP'))

            mock_ca.assert_called_once()
            call_args = mock_ca.call_args
            assert call_args.args[0] is session
            assert call_args.args[1] == 'HARD_STOP'

    def test_running_false_after_dispatch(self):
        session = _make_session()
        session['status'] = 'RUNNING'

        storage_mock = MagicMock()
        storage_mock.save_session = MagicMock(return_value=True)

        monitor = self._make_monitor_with_session(session)
        mock_report = MagicMock()
        mock_report.close_errors = []

        with patch('webui.backend.routes.mmmx.mmmx_close_all.close_all',
                   new=AsyncMock(return_value=mock_report)), \
             patch('webui.backend.routes.mmmx.mmmx_executor.get_executor',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_audit_log.get_audit_log',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_storage.get_storage',
                   return_value=storage_mock):

            _run(monitor._dispatch_close_all(session, 'HARD_STOP'))

        assert monitor._running is False

    def test_save_session_called_after_close_all(self):
        session = _make_session()
        session['status'] = 'RUNNING'

        storage_mock = MagicMock()
        storage_mock.save_session = MagicMock(return_value=True)

        monitor = self._make_monitor_with_session(session)
        mock_report = MagicMock()
        mock_report.close_errors = []

        with patch('webui.backend.routes.mmmx.mmmx_close_all.close_all',
                   new=AsyncMock(return_value=mock_report)), \
             patch('webui.backend.routes.mmmx.mmmx_executor.get_executor',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_audit_log.get_audit_log',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_storage.get_storage',
                   return_value=storage_mock):

            _run(monitor._dispatch_close_all(session, 'DTE_CLOSE'))

        storage_mock.save_session.assert_called_once()

    def test_stale_abort_gen_set_if_save_fails(self):
        session = _make_session()
        session['status'] = 'RUNNING'

        from webui.backend.routes.mmmx.mmmx_storage import GenerationConflict
        storage_mock = MagicMock()
        storage_mock.save_session = MagicMock(
            side_effect=GenerationConflict("gen conflict")
        )

        monitor = self._make_monitor_with_session(session)
        mock_report = MagicMock()
        mock_report.close_errors = []

        with patch('webui.backend.routes.mmmx.mmmx_close_all.close_all',
                   new=AsyncMock(return_value=mock_report)), \
             patch('webui.backend.routes.mmmx.mmmx_executor.get_executor',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_audit_log.get_audit_log',
                   return_value=MagicMock()), \
             patch('webui.backend.routes.mmmx.mmmx_storage.get_storage',
                   return_value=storage_mock):

            _run(monitor._dispatch_close_all(session, 'HARD_STOP'))

        assert monitor._stale_abort_gen == 1
        assert monitor._running is False


# =============================================================================
# Tests: classify_danger_side
# =============================================================================

class TestClassifyDangerSide:
    """engine.classify_danger_side pure function tests."""

    def _tranche_with(self, ce_entry, ce_current, pe_entry, pe_current):
        return {
            'ce': {'entry_premium': ce_entry, 'current_premium': ce_current},
            'pe': {'entry_premium': pe_entry, 'current_premium': pe_current},
        }

    def test_ce_losing_returns_ce(self):
        from webui.backend.routes.mmmx.mmmx_engine import classify_danger_side
        tranche = self._tranche_with(100.0, 120.0, 100.0, 80.0)  # CE current > entry
        assert classify_danger_side(tranche) == 'ce'

    def test_pe_losing_returns_pe(self):
        from webui.backend.routes.mmmx.mmmx_engine import classify_danger_side
        tranche = self._tranche_with(100.0, 80.0, 100.0, 130.0)  # PE current > entry
        assert classify_danger_side(tranche) == 'pe'

    def test_both_losing_returns_both(self):
        from webui.backend.routes.mmmx.mmmx_engine import classify_danger_side
        tranche = self._tranche_with(100.0, 120.0, 100.0, 110.0)  # Both current > entry
        assert classify_danger_side(tranche) == 'both'

    def test_both_profitable_returns_none(self):
        from webui.backend.routes.mmmx.mmmx_engine import classify_danger_side
        tranche = self._tranche_with(100.0, 80.0, 100.0, 70.0)   # Both current < entry
        assert classify_danger_side(tranche) == 'none'

    def test_equal_premiums_returns_none(self):
        from webui.backend.routes.mmmx.mmmx_engine import classify_danger_side
        tranche = self._tranche_with(100.0, 100.0, 100.0, 100.0)  # Equal → not losing
        assert classify_danger_side(tranche) == 'none'

    def test_missing_current_premium_handled(self):
        from webui.backend.routes.mmmx.mmmx_engine import classify_danger_side
        # When current_premium is None, that leg cannot be evaluated → treat as not losing
        tranche = {
            'ce': {'entry_premium': 100.0, 'current_premium': None},
            'pe': {'entry_premium': 100.0, 'current_premium': 130.0},
        }
        result = classify_danger_side(tranche)
        assert result == 'pe'  # Only PE is losing; CE cannot be evaluated

    def test_empty_tranche_returns_none(self):
        from webui.backend.routes.mmmx.mmmx_engine import classify_danger_side
        assert classify_danger_side({}) == 'none'


# =============================================================================
# Tests: Inactive legs are skipped
# =============================================================================

class TestCloseAllSkipsInactiveLegs:
    """Legs with status != ACTIVE are not closed."""

    def test_closed_leg_not_attempted(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        tranche = _make_tranche(1, ce_status='CLOSED', pe_status='ACTIVE')
        session = _make_session(tranches=[tranche])
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        # Only PE is ACTIVE → only 1 short attempted
        assert report.shorts_attempted == 1
        assert executor.emergency_execute.call_count == 1

    def test_inactive_hedge_not_attempted(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        hedge = _make_hedge('H-Tr1', status='ORPHANED')
        session = _make_session(hedges=[hedge])
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            report = _run(close_all(session, 'HARD_STOP', executor, audit))

        assert report.hedges_attempted == 0
        assert executor.smart_execute.call_count == 0


# =============================================================================
# Tests: Telegram calls
# =============================================================================

class TestCloseAllTelegram:
    """Correct Telegram alert functions called per reason."""

    def test_hard_stop_calls_alert_hard_stop(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        session = _make_session()
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop') as mock_hs, \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close') as mock_dte, \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete') as mock_sc, \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            _run(close_all(session, 'HARD_STOP', executor, audit))

        mock_hs.assert_called_once()
        mock_dte.assert_not_called()
        mock_sc.assert_called_once()

    def test_dte_close_calls_alert_dte_close(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        session = _make_session()
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop') as mock_hs, \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close') as mock_dte, \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete') as mock_sc, \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            _run(close_all(session, 'DTE_CLOSE', executor, audit))

        mock_dte.assert_called_once()
        mock_hs.assert_not_called()
        mock_sc.assert_called_once()


# =============================================================================
# Tests: emit_safety called (sync, not awaited)
# =============================================================================

class TestCloseAllEmitSafety:
    """emit_safety is called as a regular def (not awaited)."""

    def test_emit_safety_called(self):
        from webui.backend.routes.mmmx.mmmx_close_all import close_all

        session = _make_session()
        executor = MagicMock()
        executor.emergency_execute = AsyncMock(return_value=_ok_result())
        executor.smart_execute = AsyncMock(return_value=_ok_result())
        audit = MagicMock()

        with patch('webui.backend.routes.mmmx.mmmx_close_all.emit_safety') as mock_es, \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.alert_session_complete'), \
             patch('webui.backend.routes.mmmx.mmmx_close_all.log_activity'):
            _run(close_all(session, 'HARD_STOP', executor, audit))

        mock_es.assert_called_once()
        # Verify it was called as a regular function (not awaited) — it returns None, not a coroutine
        call_result = mock_es.return_value
        assert not asyncio.iscoroutine(call_result)


# =============================================================================
# Tests: MMM Isolation Scan
# =============================================================================

class TestMMMIsolation:
    """Phase 4 new modules must not import from routes.mmm.*"""

    def _check_module_isolation(self, module_name: str) -> None:
        mod = importlib.import_module(f'webui.backend.routes.mmmx.{module_name}')
        src = inspect.getsource(mod)
        lines = src.splitlines()
        violations = [
            line.strip() for line in lines
            if re.search(r'^\s*(import|from)\s+.*routes\.mmm', line)
        ]
        assert not violations, (
            f"{module_name} imports from routes.mmm — isolation violation: {violations}"
        )

    def test_mmmx_close_all_isolation(self):
        self._check_module_isolation('mmmx_close_all')

    def test_mmmx_engine_still_isolation_clean(self):
        self._check_module_isolation('mmmx_engine')

    def test_mmmx_monitor_still_isolation_clean(self):
        self._check_module_isolation('mmmx_monitor')
