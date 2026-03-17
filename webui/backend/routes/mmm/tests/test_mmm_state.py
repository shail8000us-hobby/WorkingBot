"""
Test MMM State — Unified Position Ledger migration + recompute_side_lots.

Tests:
  - _migrate_side_to_positions: legacy format → positions[]
  - Migration crash-safety: two-phase flag (_positions_migrating → _positions_migrated)
  - Migration idempotency (already migrated → no-op)
  - create_side_state: correct initial structure
  - recompute_side_lots: derives adjustment_fills, frozen_positions, scalar lots
  - recompute_side_lots: auto-migrates old sessions on first call

P2 Audit: Previously no tests for the migration path or recompute function —
both are critical to position integrity.
"""

import sys
import os
import types
import importlib
import importlib.util
import pytest
from copy import deepcopy
from datetime import datetime, timezone

# ─── Direct module loader ─────────────────────────────────────────────────────
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
_constants = _load_mmm_module('mmm_constants')
_state = _load_mmm_module('mmm_state')

_migrate = _state._migrate_side_to_positions
_create_side = _state.create_side_state
_recompute = _state.recompute_side_lots

_NOW = datetime.now(timezone.utc).isoformat()


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _old_format_side(
    side='CE',
    original_lots=5,
    original_premium=150.0,
    original_strike=100000.0,
    adj_fills=None,
    frozen=None,
):
    """Simulate a legacy session side — no 'positions' key."""
    return {
        'side': side,
        'original_lots': original_lots,
        'original_premium': original_premium,
        'original_strike': original_strike,
        'active_strike': original_strike,
        'adjustment_fills': adj_fills or [],
        'frozen_positions': frozen or [],
    }


# ─── _migrate_side_to_positions tests ────────────────────────────────────────

class TestMigrateSideToPositions:
    """Legacy 3-array format → Unified Position Ledger."""

    def test_migrates_original_lots_to_positions(self):
        side = _old_format_side(original_lots=5)
        _migrate(side)
        assert 'positions' in side
        orig = next((p for p in side['positions'] if p['type'] == 'original'), None)
        assert orig is not None
        assert orig['lots'] == 5
        assert orig['status'] == 'active'

    def test_migrates_adjustment_fills(self):
        fills = [
            {'lots': 2, 'premium': 120.0, 'strike': 102000, 'timestamp': _NOW},
            {'lots': 1, 'premium': 130.0, 'strike': 103000, 'timestamp': _NOW},
        ]
        side = _old_format_side(adj_fills=fills)
        _migrate(side)
        adj_positions = [p for p in side['positions'] if p['type'] == 'adjustment']
        assert len(adj_positions) == 2
        total_lots = sum(p['lots'] for p in adj_positions)
        assert total_lots == 3

    def test_migrates_frozen_positions(self):
        frozen = [
            {'lots': 3, 'entry_premium': 90.0, 'strike': 98000, 'frozen_at': _NOW},
        ]
        side = _old_format_side(frozen=frozen)
        _migrate(side)
        shifted = [p for p in side['positions'] if p['status'] == 'shifted']
        assert len(shifted) == 1
        assert shifted[0]['lots'] == 3

    def test_sets_migrated_flag(self):
        side = _old_format_side()
        _migrate(side)
        assert side.get('_positions_migrated') is True
        assert '_positions_migrating' not in side

    def test_idempotent_when_already_migrated(self):
        """Second call with _positions_migrated=True → no-op, positions unchanged."""
        side = _old_format_side(original_lots=5)
        _migrate(side)
        positions_after_first = deepcopy(side['positions'])

        # Second call — should be a no-op
        _migrate(side)
        assert side['positions'] == positions_after_first

    def test_zero_lot_fills_skipped(self):
        """Fills with lots=0 should NOT be migrated (they're already closed)."""
        fills = [
            {'lots': 0, 'premium': 100.0, 'strike': 101000},
            {'lots': 2, 'premium': 120.0, 'strike': 102000},
        ]
        side = _old_format_side(adj_fills=fills)
        _migrate(side)
        adj_positions = [p for p in side['positions'] if p['type'] == 'adjustment']
        assert len(adj_positions) == 1  # Only the non-zero lots fill

    def test_no_original_lots_ok(self):
        """CE/PE side with zero original_lots (already closed) → empty original."""
        side = _old_format_side(original_lots=0)
        _migrate(side)
        orig = next((p for p in side['positions'] if p['type'] == 'original'), None)
        assert orig is None  # No original position created for 0 lots

    def test_crash_recovery_flag(self):
        """If _positions_migrating is set from a prior crash → logs warning, re-runs."""
        side = _old_format_side(original_lots=5)
        side['_positions_migrating'] = True   # Simulate crash mid-migration
        # Should NOT raise — should log warning and proceed
        _migrate(side)
        assert side.get('_positions_migrated') is True
        assert '_positions_migrating' not in side

    def test_positions_include_pos_ids(self):
        """All migrated positions must have a unique 'id' field."""
        fills = [
            {'lots': 2, 'premium': 120.0, 'strike': 102000},
        ]
        side = _old_format_side(original_lots=5, adj_fills=fills)
        _migrate(side)
        for pos in side['positions']:
            assert 'id' in pos and pos['id'], f"Position missing id: {pos}"

    def test_all_positions_have_required_fields(self):
        """Every migrated position must have the full lifecycle schema."""
        required = {'id', 'strike', 'lots', 'entry_premium', 'type', 'status',
                    'created_at', 'shifted_at', 'closed_at'}
        fills = [{'lots': 2, 'premium': 100.0, 'strike': 102000}]
        side = _old_format_side(original_lots=5, adj_fills=fills)
        _migrate(side)
        for pos in side['positions']:
            missing = required - pos.keys()
            assert not missing, f"Position {pos['id']} missing fields: {missing}"


# ─── create_side_state tests ───────────────────────────────────────────────────

class TestCreateSideState:
    """Initial side state has correct structure."""

    def test_creates_positions_list(self):
        state = _create_side('CE', original_lots=5, original_premium=150.0, original_strike=100000)
        assert isinstance(state['positions'], list)
        assert len(state['positions']) == 1

    def test_original_position_has_correct_fields(self):
        state = _create_side('CE', original_lots=5, original_premium=150.0, original_strike=100000)
        pos = state['positions'][0]
        assert pos['lots'] == 5
        assert pos['entry_premium'] == 150.0
        assert pos['strike'] == 100000
        assert pos['type'] == 'original'
        assert pos['status'] == 'active'
        assert pos['id'] == 'ce_orig'

    def test_empty_state_with_zero_lots(self):
        state = _create_side('PE', original_lots=0)
        assert state['positions'] == []
        assert state['original_lots'] == 0

    def test_derived_scalar_lots_correct(self):
        state = _create_side('CE', original_lots=5, original_premium=150.0, original_strike=100000)
        assert state['active_lots'] == 5
        assert state['total_lots'] == 5
        assert state['adjustment_fills'] == []


# ─── recompute_side_lots tests ────────────────────────────────────────────────

class TestRecomputeSideLots:
    """Derives scalar lots and backward-compat views from positions[]."""

    def _make_side_with_positions(self):
        """Side with 1 original active + 1 adjustment active + 1 shifted."""
        return {
            'side': 'CE',
            'active_strike': 105000,
            'original_strike': 100000,
            '_positions_migrated': True,
            'positions': [
                {
                    'id': 'ce_orig', 'strike': 105000, 'lots': 5,
                    'entry_premium': 150.0, 'premium': 150.0,
                    'type': 'original', 'status': 'active',
                    'created_at': _NOW, 'shifted_at': None, 'closed_at': None,
                },
                {
                    'id': 'ce_adj_001', 'strike': 105000, 'lots': 2,
                    'entry_premium': 120.0, 'premium': 120.0,
                    'type': 'adjustment', 'status': 'active',
                    'created_at': _NOW, 'shifted_at': None, 'closed_at': None,
                },
                {
                    'id': 'ce_frozen_001', 'strike': 102000, 'lots': 3,
                    'entry_premium': 90.0, 'premium': 90.0,
                    'type': 'adjustment', 'status': 'shifted',
                    'created_at': _NOW, 'shifted_at': _NOW, 'closed_at': None,
                },
            ],
        }

    def test_original_lots_derived(self):
        side = self._make_side_with_positions()
        _recompute(side)
        assert side['original_lots'] == 5

    def test_active_lots_is_sum_of_active_positions(self):
        """active_lots = original(5) + adjustment(2) = 7."""
        side = self._make_side_with_positions()
        _recompute(side)
        assert side['active_lots'] == 7

    def test_total_lots_includes_frozen(self):
        """total_lots = active(7) + frozen(3) = 10."""
        side = self._make_side_with_positions()
        _recompute(side)
        assert side['total_lots'] == 10

    def test_adjustment_fills_rebuilt(self):
        """adjustment_fills is rebuilt from active non-original positions."""
        side = self._make_side_with_positions()
        _recompute(side)
        assert len(side['adjustment_fills']) == 1
        adj = side['adjustment_fills'][0]
        assert adj['lots'] == 2
        assert adj['strike'] == 105000
        # _pos_id must be carried for O(1) removal
        assert adj['_pos_id'] == 'ce_adj_001'

    def test_frozen_positions_rebuilt(self):
        """frozen_positions is rebuilt from shifted positions."""
        side = self._make_side_with_positions()
        _recompute(side)
        assert len(side['frozen_positions']) == 1
        frz = side['frozen_positions'][0]
        assert frz['lots'] == 3
        assert frz['_pos_id'] == 'ce_frozen_001'

    def test_closed_positions_excluded_from_counts(self):
        """Closed positions (status='closed') are not counted in any lot field."""
        side = self._make_side_with_positions()
        side['positions'].append({
            'id': 'ce_closed_001', 'strike': 100000, 'lots': 5,
            'entry_premium': 150.0, 'premium': 150.0,
            'type': 'original', 'status': 'closed',
            'created_at': _NOW, 'shifted_at': None, 'closed_at': _NOW,
        })
        _recompute(side)
        # Closed positions should not inflate total_lots
        assert side['total_lots'] == 10   # same as before adding closed

    def test_auto_migrates_old_format(self):
        """Old session without positions[] key auto-migrates on first recompute."""
        side = {
            'side': 'CE',
            'original_lots': 4,
            'original_premium': 120.0,
            'original_strike': 100000,
            'active_strike': 100000,
            'adjustment_fills': [],
            'frozen_positions': [],
        }
        # No 'positions' key → should auto-migrate
        _recompute(side)
        assert 'positions' in side
        assert side['original_lots'] == 4

    def test_invalid_positions_type_reset(self):
        """If positions is not a list (corrupted data), resets to [] without crash."""
        side = self._make_side_with_positions()
        side['positions'] = 'corrupted_string'
        _recompute(side)
        assert side['positions'] == []
        assert side['active_lots'] == 0
