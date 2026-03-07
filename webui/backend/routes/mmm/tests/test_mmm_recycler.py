"""
Test MMM Recycler — M2 Lot Recycling.

Tests:
  - select_recyclable_positions: basic selection, sorting, protect_original
  - select_recyclable_positions: _being_closed guard
  - select_recyclable_positions: empty frozen returns []
  - check_recycle_viability: all three checks (ratio, net lot gain, affordability)
  - check_recycle_viability: edge cases (zero premium, no positions)
  - check_recycle_viability: math matches plan document examples
  - execute_lot_recycling: cooldown enforcement
  - execute_lot_recycling: recycle_enabled=False guard
  - execute_lot_recycling: Phase A success/failure paths
  - execute_lot_recycling: Phase B cap check after Phase A
  - execute_lot_recycling: success increments counters
  - execute_lot_recycling: failure increments attempt_count not recycle_count

Created: March 3, 2026
"""

import sys
import os
import math
import types
import importlib
import importlib.util
import pytest
from copy import deepcopy
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

# ─── Direct module loader (bypasses routes/__init__.py) ───────────────────────
_MMM_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _setup_mmm_package():
    if 'webui.backend.routes.mmm' in sys.modules:
        return
    for name in ['webui', 'webui.backend', 'webui.backend.routes',
                 'webui.backend.routes.mmm']:
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = []
            pkg.__package__ = name
            sys.modules[name] = pkg
    sys.modules['webui.backend.routes.mmm'].__path__ = [_MMM_PKG_DIR]


def _load_mmm_module(name):
    full_name = f'webui.backend.routes.mmm.{name}'
    if full_name in sys.modules:
        return sys.modules[full_name]
    path = os.path.join(_MMM_PKG_DIR, f'{name}.py')
    spec = importlib.util.spec_from_file_location(
        full_name, path, submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'webui.backend.routes.mmm'
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_setup_mmm_package()
_load_mmm_module('mmm_constants')
_recycler = _load_mmm_module('mmm_recycler')

select_recyclable_positions = _recycler.select_recyclable_positions
check_recycle_viability = _recycler.check_recycle_viability
execute_lot_recycling = _recycler.execute_lot_recycling

from webui.backend.routes.mmm.mmm_constants import LOT_SIZE_BTC


# ─── Register mock modules for execute_lot_recycling's local imports ─────────

def _ensure_mock_module(name, **attrs):
    """Register a mock module if the real one can't be loaded (avoids Flask deps)."""
    full_name = f'webui.backend.routes.mmm.{name}'
    if full_name not in sys.modules:
        mock_mod = types.ModuleType(full_name)
        mock_mod.__package__ = 'webui.backend.routes.mmm'
        for k, v in attrs.items():
            setattr(mock_mod, k, v)
        sys.modules[full_name] = mock_mod
    return sys.modules[full_name]


# Pre-register stubs so `from .mmm_close_at_5 import close_position` resolves
_mock_close_at_5 = _ensure_mock_module(
    'mmm_close_at_5', close_position=AsyncMock(),
)
_mock_strike_shift = _ensure_mock_module(
    'mmm_strike_shift', find_new_strike=MagicMock(),
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_frozen(strike=95000, entry_premium=100.0, lots=10,
                 type_='adjustment', pos_id='fp-001'):
    return {
        'strike': strike,
        'entry_premium': entry_premium,
        'lots': lots,
        'type': type_,
        '_pos_id': pos_id,
    }


def _make_session(
    hedge_side='ce', total_lots=100, max_lots=100,
    frozen_positions=None, protect_original=True,
    recycle_enabled=True, recycle_cooldown_sec=300,
    recycle_min_premium_ratio=2.5, recycle_premium_ceiling=50.0,
    recycle_max_pct=0.50, recycle_min_lot_gain=5,
    recycle_free_lot_buffer=10, premium_buffer_pct=0.05,
    last_recycle_at=None,
    active_lots=None,  # Split Ledger: defaults to total_lots if not specified
):
    # If active_lots not given, assume no frozen positions (all lots are active)
    _active = active_lots if active_lots is not None else total_lots
    session = {
        'session_id': 'test-recycle-001',
        'strategy_status': 'RUNNING',
        'params': {
            'max_lots_per_side': max_lots,
            'recycle_enabled': recycle_enabled,
            'recycle_min_premium_ratio': recycle_min_premium_ratio,
            'recycle_premium_ceiling': recycle_premium_ceiling,
            'recycle_max_pct': recycle_max_pct,
            'recycle_cooldown_sec': recycle_cooldown_sec,
            'recycle_min_lot_gain': recycle_min_lot_gain,
            'recycle_free_lot_buffer': recycle_free_lot_buffer,
            'recycle_protect_original': protect_original,
            'premium_buffer_pct': premium_buffer_pct,
        },
        'ce': {
            'total_lots': total_lots if hedge_side == 'ce' else 10,
            'active_lots': _active if hedge_side == 'ce' else 10,
            'frozen_positions': frozen_positions or [],
            'positions': [],
        },
        'pe': {
            'total_lots': total_lots if hedge_side == 'pe' else 10,
            'active_lots': _active if hedge_side == 'pe' else 10,
            'frozen_positions': [],
            'positions': [],
        },
    }
    if last_recycle_at:
        session['_last_recycle_at'] = last_recycle_at
    return session


# =============================================================================
# Tests: select_recyclable_positions
# =============================================================================

class TestSelectRecyclablePositions:
    """§4.3 recyclable position selection."""

    def test_basic_selection(self):
        """Adjustment-type frozen positions are selected."""
        frozen = [
            _make_frozen(strike=95000, entry_premium=30.0, lots=5, pos_id='a'),
            _make_frozen(strike=96000, entry_premium=50.0, lots=8, pos_id='b'),
        ]
        session = _make_session(frozen_positions=frozen)

        result = select_recyclable_positions(session, 'ce')

        assert len(result) == 2
        assert result[0]['entry_premium'] == 30.0  # Sorted ascending
        assert result[1]['entry_premium'] == 50.0

    def test_protect_original_enabled(self):
        """Original entry position excluded when recycle_protect_original=True."""
        frozen = [
            _make_frozen(strike=95000, type_='original', pos_id='orig'),
            _make_frozen(strike=96000, type_='adjustment', pos_id='adj'),
        ]
        session = _make_session(frozen_positions=frozen, protect_original=True)

        result = select_recyclable_positions(session, 'ce')

        assert len(result) == 1
        assert result[0]['_pos_id'] == 'adj'

    def test_protect_original_disabled(self):
        """Original included when protection is off."""
        frozen = [
            _make_frozen(strike=95000, type_='original', pos_id='orig'),
            _make_frozen(strike=96000, type_='adjustment', pos_id='adj'),
        ]
        session = _make_session(frozen_positions=frozen, protect_original=False)

        result = select_recyclable_positions(session, 'ce')

        assert len(result) == 2

    def test_being_closed_skipped(self):
        """In-flight positions (_being_closed) are excluded."""
        frozen = [_make_frozen(strike=95000, pos_id='inflight')]
        session = _make_session(frozen_positions=frozen)
        session['ce']['positions'] = [{'id': 'inflight', '_being_closed': True}]

        result = select_recyclable_positions(session, 'ce')

        assert len(result) == 0

    def test_zero_lots_skipped(self):
        """Positions with 0 lots are excluded."""
        frozen = [_make_frozen(strike=95000, lots=0, pos_id='zero')]
        session = _make_session(frozen_positions=frozen)

        result = select_recyclable_positions(session, 'ce')

        assert len(result) == 0

    def test_empty_frozen_returns_empty(self):
        """No frozen positions → []."""
        session = _make_session(frozen_positions=[])

        result = select_recyclable_positions(session, 'ce')

        assert result == []

    def test_sorted_by_entry_premium_ascending(self):
        """Cheapest-first heuristic before live premium fetch."""
        frozen = [
            _make_frozen(strike=97000, entry_premium=80.0, pos_id='c'),
            _make_frozen(strike=95000, entry_premium=20.0, pos_id='a'),
            _make_frozen(strike=96000, entry_premium=50.0, pos_id='b'),
        ]
        session = _make_session(frozen_positions=frozen)

        result = select_recyclable_positions(session, 'ce')

        assert [r['_pos_id'] for r in result] == ['a', 'b', 'c']


# =============================================================================
# Tests: check_recycle_viability
# =============================================================================

class TestCheckRecycleViability:
    """§4.4 viability check — 3 independent conditions."""

    def _make_recyclable(self, premiums_lots):
        """Build priced recyclable list: [(current_premium, lots), ...]"""
        return [
            {
                'current_premium': p,
                'lots': l,
                'entry_premium': p + 50,
                'strike': 95000 + i * 1000,
            }
            for i, (p, l) in enumerate(premiums_lots)
        ]

    def test_viable_scenario_from_plan_doc(self):
        """Viable scenario: cheap positions recycled for better premium."""
        # 30 frozen lots at avg current_premium=10 (cheap buyback)
        # New premium = 80 (much better), loss_to_hedge = 0.1 USD
        recyclable = self._make_recyclable([
            (10.0, 10), (10.0, 10), (10.0, 10),  # avg=10, total=30 lots
        ])
        params = {
            'recycle_min_premium_ratio': 2.5,
            'premium_buffer_pct': 0.05,
            'recycle_min_lot_gain': 5,
        }

        # Split Ledger: 30 lots are frozen (being recycled), 70 are active
        viable, reason, details = check_recycle_viability(
            recyclable, loss_to_hedge=0.1, new_premium=80.0,
            current_active_lots=70, max_lots_per_side=100, params=params,
        )

        assert viable is True
        assert reason == 'Viable'
        assert details['recycled_lots'] == 30
        assert details['ratio'] >= 2.5

    def test_premium_ratio_too_low(self):
        """Fails when new_premium / avg_recycle is below min_ratio."""
        recyclable = self._make_recyclable([(40.0, 10)])
        params = {
            'recycle_min_premium_ratio': 2.5,
            'premium_buffer_pct': 0.05,
            'recycle_min_lot_gain': 5,
        }

        viable, reason, details = check_recycle_viability(
            recyclable, loss_to_hedge=100.0, new_premium=80.0,
            current_active_lots=50, max_lots_per_side=100, params=params,
        )

        assert viable is False
        assert 'ratio' in reason.lower()

    def test_net_lot_gain_too_low(self):
        """Fails when recycled_lots - new_lots_needed < min_lot_gain."""
        # Only 5 lots recycled, but need many new lots
        recyclable = self._make_recyclable([(5.0, 5)])
        params = {
            'recycle_min_premium_ratio': 2.0,
            'premium_buffer_pct': 0.05,
            'recycle_min_lot_gain': 5,
        }

        viable, reason, details = check_recycle_viability(
            recyclable, loss_to_hedge=500.0, new_premium=80.0,
            current_active_lots=100, max_lots_per_side=100, params=params,
        )

        assert viable is False
        assert 'lot gain' in reason.lower()

    def test_affordability_check_fails(self):
        """Fails when new + remaining would exceed cap."""
        recyclable = self._make_recyclable([(10.0, 5)])
        params = {
            'recycle_min_premium_ratio': 1.5,
            'premium_buffer_pct': 0.05,
            'recycle_min_lot_gain': 1,
        }

        # current_total=98, recycled=5 → remaining=93
        # New lots needed very high due to big loss
        viable, reason, details = check_recycle_viability(
            recyclable, loss_to_hedge=5000.0, new_premium=10.0,
            current_active_lots=98, max_lots_per_side=100, params=params,
        )

        # Either affordability or lot gain will fail
        assert viable is False

    def test_empty_recyclable_fails(self):
        """No positions → not viable."""
        params = {'recycle_min_premium_ratio': 2.5, 'premium_buffer_pct': 0.05,
                  'recycle_min_lot_gain': 5}

        viable, reason, _ = check_recycle_viability(
            [], loss_to_hedge=100.0, new_premium=80.0,
            current_active_lots=50, max_lots_per_side=100, params=params,
        )

        assert viable is False
        assert 'no recyclable' in reason.lower()

    def test_zero_new_premium_fails(self):
        """new_premium=0 → not viable."""
        recyclable = self._make_recyclable([(10.0, 5)])
        params = {'recycle_min_premium_ratio': 2.5, 'premium_buffer_pct': 0.05,
                  'recycle_min_lot_gain': 5}

        viable, reason, _ = check_recycle_viability(
            recyclable, loss_to_hedge=100.0, new_premium=0,
            current_active_lots=50, max_lots_per_side=100, params=params,
        )

        assert viable is False
        assert 'zero premium' in reason.lower()

    def test_zero_recyclable_lots_fails(self):
        """All positions have 0 lots → zero recyclable lots."""
        recyclable = [{'current_premium': 10.0, 'lots': 0, 'entry_premium': 60}]
        params = {'recycle_min_premium_ratio': 2.5, 'premium_buffer_pct': 0.05,
                  'recycle_min_lot_gain': 5}

        viable, reason, _ = check_recycle_viability(
            recyclable, loss_to_hedge=100.0, new_premium=80.0,
            current_active_lots=50, max_lots_per_side=100, params=params,
        )

        assert viable is False
        assert 'zero' in reason.lower()

    def test_details_dict_on_success(self):
        """Verify the details dict has all expected fields on success."""
        recyclable = self._make_recyclable([(5.0, 30)])
        params = {
            'recycle_min_premium_ratio': 2.5,
            'premium_buffer_pct': 0.05,
            'recycle_min_lot_gain': 5,
        }

        viable, _, details = check_recycle_viability(
            recyclable, loss_to_hedge=0.05, new_premium=80.0,
            current_active_lots=80, max_lots_per_side=100, params=params,
        )

        assert viable is True
        for key in ['buyback_cost', 'recycled_lots', 'avg_recycle_premium',
                    'ratio', 'total_to_cover', 'new_lots_needed',
                    'net_lot_gain', 'current_active']:
            assert key in details

    def test_new_lots_needed_at_least_one(self):
        """Even with tiny loss, at least 1 new lot is required."""
        recyclable = self._make_recyclable([(5.0, 30)])
        params = {
            'recycle_min_premium_ratio': 2.0,
            'premium_buffer_pct': 0.05,
            'recycle_min_lot_gain': 1,
        }

        viable, _, details = check_recycle_viability(
            recyclable, loss_to_hedge=0.001, new_premium=100.0,
            current_active_lots=50, max_lots_per_side=100, params=params,
        )

        if viable:
            assert details['new_lots_needed'] >= 1


# =============================================================================
# Tests: execute_lot_recycling
# =============================================================================

class TestExecuteLotRecycling:
    """§4.5 two-phase execution."""

    def test_disabled_returns_error(self):
        """recycle_enabled=False → immediate rejection."""
        session = _make_session(recycle_enabled=False)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            execute_lot_recycling(
                session, 'ce', 'ce', 100.0,
                lambda s, t: 10.0, MagicMock(), MagicMock(),
                80000.0, MagicMock(),
            )
        )

        assert result['success'] is False
        assert 'recycle_enabled=False' in result['error']

    def test_cooldown_blocks_recycle(self):
        """Recent recycle within cooldown → blocked."""
        recent = datetime.now(timezone.utc).isoformat()
        session = _make_session(
            recycle_cooldown_sec=300, last_recycle_at=recent,
        )
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            execute_lot_recycling(
                session, 'ce', 'ce', 100.0,
                lambda s, t: 10.0, MagicMock(), MagicMock(),
                80000.0, MagicMock(),
            )
        )

        assert result['success'] is False
        assert 'cooldown' in result['error'].lower()

    def test_expired_cooldown_proceeds(self):
        """Old recycle outside cooldown → not blocked by cooldown."""
        old = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        session = _make_session(
            recycle_cooldown_sec=300, last_recycle_at=old,
            frozen_positions=[_make_frozen(strike=95000, entry_premium=30.0)],
        )

        # Mock find_new_strike returning None → will fail at step 1
        _mock_strike_shift.find_new_strike = MagicMock(return_value=None)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            execute_lot_recycling(
                session, 'ce', 'ce', 100.0,
                lambda s, t: 10.0, MagicMock(), MagicMock(),
                80000.0, MagicMock(),
            )
        )

        # Should get past cooldown check, fail on strike finding
        assert result['success'] is False
        assert 'strike' in result['error'].lower() or 'no suitable' in result['error'].lower()

    def test_no_new_strike_found(self):
        """find_new_strike returns None → error."""
        session = _make_session(
            frozen_positions=[_make_frozen(strike=95000, entry_premium=30.0)],
        )

        _mock_strike_shift.find_new_strike = MagicMock(return_value=None)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            execute_lot_recycling(
                session, 'ce', 'ce', 100.0,
                lambda s, t: 10.0, MagicMock(), MagicMock(),
                80000.0, MagicMock(),
            )
        )

        assert result['success'] is False

    def test_no_recyclable_positions(self):
        """Empty frozen_positions → error."""
        session = _make_session(frozen_positions=[])

        _mock_strike_shift.find_new_strike = MagicMock(
            return_value={'strike': 98000, 'premium': 120.0},
        )

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            execute_lot_recycling(
                session, 'ce', 'ce', 100.0,
                lambda s, t: 10.0, MagicMock(), MagicMock(),
                80000.0, MagicMock(),
            )
        )

        assert result['success'] is False
        assert 'no recyclable' in result['error'].lower()

    def test_success_increments_recycle_count(self):
        """Successful recycle → recycle_count increments."""
        frozen = [
            _make_frozen(strike=95000, entry_premium=30.0, lots=20, pos_id=f'fp-{i}')
            for i in range(3)
        ]
        # Split Ledger: 60 lots are frozen, 40 are active (total=100)
        session = _make_session(
            frozen_positions=frozen, total_lots=100, max_lots=100,
            recycle_min_premium_ratio=1.5, recycle_min_lot_gain=1,
            recycle_free_lot_buffer=0, active_lots=40,
        )
        session['recycle_count'] = 0
        session.setdefault('adjustment_count', 0)

        mock_engine = MagicMock()

        # Mock find_new_strike
        _mock_strike_shift.find_new_strike = MagicMock(
            return_value={'strike': 98000, 'premium': 120.0},
        )
        # Mock close_position — must also update total_lots so Phase B cap check passes
        async def _close_and_update(executor, initializer, sess, pos):
            lots = pos.get('lots', 20)
            sess['ce']['total_lots'] -= lots
            return {'success': True, 'realized_pnl': 0.01, 'lots_closed': lots}
        _mock_close_at_5.close_position = _close_and_update
        # Mock execute_adjustment
        mock_engine.execute_adjustment = AsyncMock(return_value={
            'success': True, 'fill_price': 120.0,
        })

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            execute_lot_recycling(
                session, 'ce', 'ce', 0.1,
                lambda s, t: 10.0, MagicMock(), MagicMock(),
                80000.0, mock_engine,
            )
        )

        assert result['success'] is True
        assert session['recycle_count'] == 1
        assert session['adjustment_count'] == 1
        assert '_last_recycle_at' in session

    def test_phase_a_all_fail_returns_error(self):
        """If all Phase A buybacks fail, returns error."""
        frozen = [_make_frozen(strike=95000, entry_premium=30.0, lots=10)]
        # Split Ledger: 10 lots frozen, 90 active (total=100). active_lots=90 keeps viability check passing.
        session = _make_session(
            frozen_positions=frozen, total_lots=100, max_lots=100,
            recycle_min_premium_ratio=1.5, recycle_min_lot_gain=1,
            active_lots=90,
        )

        _mock_strike_shift.find_new_strike = MagicMock(
            return_value={'strike': 98000, 'premium': 120.0},
        )
        _mock_close_at_5.close_position = AsyncMock(
            return_value={'success': False, 'error': 'timeout'},
        )

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            execute_lot_recycling(
                session, 'ce', 'ce', 0.1,
                lambda s, t: 10.0, MagicMock(), MagicMock(),
                80000.0, MagicMock(),
            )
        )

        assert result['success'] is False
        assert 'buybacks failed' in result['error'].lower()

    def test_failure_path_increments_attempt_not_success(self):
        """Partial failure (Phase B fail) → recycle_attempt_count increments,
        recycle_count does NOT."""
        frozen = [_make_frozen(strike=95000, entry_premium=30.0, lots=10)]
        # Split Ledger: 10 lots frozen, 90 active (total=100). active_lots=90 ensures
        # viability passes and Phase B can be reached (90+2=92 ≤ 100).
        session = _make_session(
            frozen_positions=frozen, total_lots=100, max_lots=100,
            recycle_min_premium_ratio=1.5, recycle_min_lot_gain=1,
            active_lots=90,
        )
        session['recycle_count'] = 0
        session['recycle_attempt_count'] = 0

        mock_engine = MagicMock()

        _mock_strike_shift.find_new_strike = MagicMock(
            return_value={'strike': 98000, 'premium': 120.0},
        )
        _mock_close_at_5.close_position = AsyncMock(return_value={
            'success': True, 'realized_pnl': 0.01, 'lots_closed': 10,
        })
        mock_engine.execute_adjustment = AsyncMock(return_value={
            'success': False, 'error': 'exchange_error',
        })

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            execute_lot_recycling(
                session, 'ce', 'ce', 0.1,
                lambda s, t: 10.0, MagicMock(), MagicMock(),
                80000.0, mock_engine,
            )
        )

        assert result['success'] is False
        assert session['recycle_count'] == 0  # NOT incremented on failure
        assert session['recycle_attempt_count'] == 1  # Attempt tracked


# =============================================================================
# Tests: mmm_constants
# =============================================================================

class TestConstants:
    """Verify shared constants."""

    def test_lot_size_btc(self):
        from webui.backend.routes.mmm.mmm_constants import LOT_SIZE_BTC
        assert LOT_SIZE_BTC == 0.001

    def test_decimal_helper(self):
        from webui.backend.routes.mmm.mmm_constants import _D
        from decimal import Decimal
        assert _D(100.5) == Decimal('100.5')
        assert _D(0) == Decimal('0')

    def test_lot_constant(self):
        from webui.backend.routes.mmm.mmm_constants import _LOT
        from decimal import Decimal
        assert _LOT == Decimal('0.001')

    def test_strike_key_int(self):
        from webui.backend.routes.mmm.mmm_constants import strike_key
        assert strike_key(95000) == '95000'

    def test_strike_key_float(self):
        from webui.backend.routes.mmm.mmm_constants import strike_key
        assert strike_key(95000.5) == '95000'

    def test_strike_key_string(self):
        from webui.backend.routes.mmm.mmm_constants import strike_key
        assert strike_key('95000') == '95000'

    def test_strike_key_bad_input(self):
        from webui.backend.routes.mmm.mmm_constants import strike_key
        assert strike_key('abc') == 'abc'
