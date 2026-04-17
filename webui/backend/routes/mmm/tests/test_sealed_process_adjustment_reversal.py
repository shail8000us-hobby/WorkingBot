"""
Sealed regression tests for _process_adjustment() — reversal path UnboundLocalError
(2026-04-17 P0 incident)

SEALED — v1.0.0 — 2026-04-17
Do not modify without UNSEAL command in AI_SEAL.md

--- Incident summary ---

Sessions mmm17apr26-7 and mmm17apr26-8 (STRADDLE_WITH_ADJUSTMENT) stopped
with "Unrecoverable error: UnboundLocalError" immediately after an order fill.

Root cause: In _process_adjustment(), _pre_adj_trigger was only assigned in
the else (standard/continuation) branch.  The if-is_reversal: path (which
sets adj_type='first_reversal') never assigned it.  Both branches fall through
to self._hb_wt['adjustment'] ~line 5054 where _pre_adj_trigger is referenced.
Python 3.12+ raises UnboundLocalError for this — caught by the unrecoverable-
error guard → session stopped → live positions left unmonitored.

Fix: _pre_adj_trigger = 0 initialized before the if is_reversal: block.
The else branch still overwrites it with the real snapshot value.

--- Contracts ---

  C-PA-REV-1: first_reversal path (is_reversal=True, skip=False, successful fill)
              completes without raising any exception
  C-PA-REV-2: _hb_wt['adjustment']['adj_type'] == 'first_reversal'
  C-PA-REV-3: _hb_wt['adjustment']['pre_adj_trigger'] == 0 (safe default for reversal)
  C-PA-REV-4: _hb_wt['adjustment']['lots'] == 48 (from mocked calculate_lots_to_sell)
  C-PA-REV-5: standard path still gets the real pre_adj_trigger value from
              trigger_snapshot, not the 0 default (else branch not broken by the fix)
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
from webui.backend.routes.mmm.mmm_dte_presets import STRADDLE_WITH_ADJUSTMENT_CATEGORY


# =============================================================================
# Helpers
# =============================================================================

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_session(last_aggressor='ce'):
    """Minimal STRADDLE_WITH_ADJUSTMENT session for _process_adjustment tests."""
    return {
        'session_id': 'test-pa-rev-001',
        'strategy_status': 'RUNNING',
        'params': {
            '_preset_source': 'STRADDLE_WITH_ADJUSTMENT',
            'dangerous_mode': False,
            'cooldown_on_reversal': False,
            'reversal_skip_force_through': 3,
            'whipsaw_restrict_score': 3,
        },
        'last_aggressor': last_aggressor,
        'adjustment_count': 2,
        '_consecutive_reversal_skip_count': 0,
        '_last_adjustment_loss': 0.0,
        'analytics': {},
        'ce': {
            'active_strike': 74400,
            'active_lots': 60,
            'positions': [],
            'trigger_snapshot': {'74400': 250.0},  # used by standard path
        },
        'pe': {
            'active_strike': 74400,
            'active_lots': 190,
            'positions': [],
            'trigger_snapshot': {'74400': 300.0},
        },
    }


def _make_monitor(session):
    """Minimal mock monitor with all attributes _process_adjustment reads."""
    m = MagicMock()
    m.session_id = 'test-pa-rev-001'
    m.session = session
    m._hb_wt = {}

    # Engine
    m._engine.calculate_reversal_loss = MagicMock(
        return_value=(200.0, -150.0, -200.0, False)
    )
    m._engine.calculate_standard_loss = MagicMock(
        return_value=(180.0, False)
    )
    m._engine.calculate_lots_to_sell = MagicMock(
        return_value=(48, '', False)
    )
    m._engine.execute_adjustment = AsyncMock(return_value={
        'success': True,
        'fill_price': 115.0,
        'order_id': 'test-ord-001',
    })

    # Price / premium fetching
    m._fetch_spot_price = AsyncMock(return_value=74300.0)
    m._fetch_premiums = AsyncMock(return_value=(130.0, 120.0))
    m._make_fetch_fn = MagicMock(return_value=MagicMock())

    # Regime engine (gamma check is inside try/except — failure is safe)
    m._regime_engine.check_projected_gamma = MagicMock(return_value=(False, 5000))

    # Pending order guard
    m._create_heartbeat_rest_client = MagicMock(return_value=MagicMock())

    # Dedup warning helper
    m._should_emit_warning = MagicMock(return_value=True)

    # Symbol builder (used inside gamma check try/except)
    m.initializer.build_symbol = MagicMock(return_value='P-BTC-74400-170426')

    return m


def _run_with_patches(monitor, is_reversal, aggressor='pe', hedge='ce'):
    """Execute _process_adjustment inside a stack of patches."""
    with patch('webui.backend.routes.mmm.mmm_monitor.check_and_resolve_pending',
               new=AsyncMock(return_value='none')), \
         patch('webui.backend.routes.mmm.mmm_monitor.detect_reversal',
               return_value=is_reversal), \
         patch('webui.backend.routes.mmm.mmm_monitor.record_reversal'), \
         patch('webui.backend.routes.mmm.mmm_monitor.reset_peak_pnl_on_reversal'), \
         patch('webui.backend.routes.mmm.mmm_monitor.should_skip_reversal_adjustment',
               return_value=(False, '')), \
         patch('webui.backend.routes.mmm.mmm_monitor.emit_reversal'), \
         patch('webui.backend.routes.mmm.mmm_monitor.activate_cooldown'), \
         patch('webui.backend.routes.mmm.mmm_monitor.check_shift_needed',
               return_value=False), \
         patch('webui.backend.routes.mmm.mmm_monitor._session_strategy_type',
               return_value=STRADDLE_WITH_ADJUSTMENT_CATEGORY), \
         patch('webui.backend.routes.mmm.mmm_monitor.log_activity'), \
         patch('webui.backend.routes.mmm.mmm_monitor.emit_safety'), \
         patch('webui.backend.routes.mmm.mmm_monitor.emit_adjustment'), \
         patch('webui.backend.routes.mmm.mmm_monitor.update_trigger_snapshots'), \
         patch('webui.backend.routes.mmm.mmm_monitor.get_breakeven_engine'), \
         patch('webui.backend.routes.mmm.mmm_monitor.get_gamma_detector'), \
         patch('webui.backend.routes.mmm.mmm_monitor.update_peak_pnl'):
        _run(MMMMonitor._process_adjustment(
            monitor,
            aggressor=aggressor,
            hedge=hedge,
            premium_now=300.0,
            hedge_premium=130.0,
            ce_now=130.0,
            pe_now=300.0,
        ))


# =============================================================================
# C-PA-REV-1 through C-PA-REV-4: first_reversal path — no crash, correct state
# =============================================================================

class TestProcessAdjustmentFirstReversal:
    """
    Regression tests for the 2026-04-17 P0 crash:
    _pre_adj_trigger unbound on first_reversal path.
    """

    @pytest.mark.sealed
    def test_c_pa_rev_1_first_reversal_completes_without_exception(self):
        """
        C-PA-REV-1: _process_adjustment with is_reversal=True (first_reversal path)
        and a successful fill must complete without raising any exception.

        Before the fix: UnboundLocalError: cannot access local variable '_pre_adj_trigger'
        where it is not associated with a value.
        """
        session = _make_session(last_aggressor='ce')  # PE is new aggressor → reversal
        monitor = _make_monitor(session)

        # Must not raise
        _run_with_patches(monitor, is_reversal=True, aggressor='pe', hedge='ce')

    @pytest.mark.sealed
    def test_c_pa_rev_2_first_reversal_adj_type_in_walkthrough(self):
        """
        C-PA-REV-2: After first_reversal execution, _hb_wt['adjustment']['adj_type']
        must be 'first_reversal'.
        """
        session = _make_session(last_aggressor='ce')
        monitor = _make_monitor(session)

        _run_with_patches(monitor, is_reversal=True, aggressor='pe', hedge='ce')

        adj = monitor._hb_wt.get('adjustment', {})
        assert adj.get('adj_type') == 'first_reversal', (
            f"Expected adj_type='first_reversal', got {adj.get('adj_type')!r}"
        )

    @pytest.mark.sealed
    def test_c_pa_rev_3_first_reversal_pre_adj_trigger_is_zero_default(self):
        """
        C-PA-REV-3: On the first_reversal path, _pre_adj_trigger must be 0
        (the safe default — no pre-adjustment trigger concept for reversals).
        """
        session = _make_session(last_aggressor='ce')
        monitor = _make_monitor(session)

        _run_with_patches(monitor, is_reversal=True, aggressor='pe', hedge='ce')

        adj = monitor._hb_wt.get('adjustment', {})
        assert adj.get('pre_adj_trigger') == 0, (
            f"Expected pre_adj_trigger=0 on reversal path, got {adj.get('pre_adj_trigger')!r}"
        )

    @pytest.mark.sealed
    def test_c_pa_rev_4_first_reversal_lots_populated_in_walkthrough(self):
        """
        C-PA-REV-4: _hb_wt['adjustment']['lots'] must equal the value from
        calculate_lots_to_sell (48 in our mock), confirming the fill completed.
        """
        session = _make_session(last_aggressor='ce')
        monitor = _make_monitor(session)

        _run_with_patches(monitor, is_reversal=True, aggressor='pe', hedge='ce')

        adj = monitor._hb_wt.get('adjustment', {})
        assert adj.get('lots') == 48, (
            f"Expected lots=48, got {adj.get('lots')!r}"
        )


# =============================================================================
# C-PA-REV-5: standard path — else branch still gets real trigger value
# =============================================================================

class TestProcessAdjustmentStandardPath:
    """
    Verify the else (standard) branch was not broken by the fix.
    The initialization _pre_adj_trigger=0 must be overwritten by the real
    trigger_snapshot value in the else branch.
    """

    @pytest.mark.sealed
    def test_c_pa_rev_5_standard_path_pre_adj_trigger_from_snapshot(self):
        """
        C-PA-REV-5: On the standard (non-reversal) path, _pre_adj_trigger must
        be read from session[aggressor]['trigger_snapshot'][active_strike].

        Session has CE trigger_snapshot = {'74400': 250.0}.
        Aggressor=CE → _pre_adj_trigger must be 250.0, not 0.
        """
        session = _make_session(last_aggressor='ce')  # CE is aggressor (continuation)
        # Ensure trigger_snapshot has a value to read
        session['ce']['trigger_snapshot'] = {'74400': 250.0}
        monitor = _make_monitor(session)

        _run_with_patches(monitor, is_reversal=False, aggressor='ce', hedge='pe')

        adj = monitor._hb_wt.get('adjustment', {})
        assert adj.get('pre_adj_trigger') == 250.0, (
            f"Expected pre_adj_trigger=250.0 on standard path, got {adj.get('pre_adj_trigger')!r}. "
            f"The fix must not have broken the else branch."
        )
        assert adj.get('adj_type') == 'standard', (
            f"Expected adj_type='standard', got {adj.get('adj_type')!r}"
        )
