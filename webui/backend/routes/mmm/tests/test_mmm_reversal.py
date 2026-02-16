"""
Test MMM Reversal — Section 9 detection, cooldown, skip logic.

Tests:
  - Reversal detection (aggressor change)
  - First adjustment is never a reversal
  - Cooldown activation and checking
  - Cooldown idempotency (Recommendation #4 fix)
  - Skip reversal when P&L >= 0
  - Record reversal tracking
  - Record reversal deduplication
  - handle_reversal_skip_transition (critical bug fix)

Uses importlib to load mmm_reversal directly without triggering
the routes/__init__.py package chain.
"""

import sys
import os
import importlib
import importlib.util
import types
import pytest
from copy import deepcopy
from datetime import datetime, timedelta

# ─── Direct module import (bypasses routes/__init__.py) ───────────────────────
_MMM_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _setup_mmm_package():
    """
    Register a minimal fake package hierarchy so that relative imports
    within MMM modules (e.g. `from .mmm_trigger import ...`) resolve
    correctly without triggering the full routes/__init__.py chain.
    """
    if 'webui.backend.routes.mmm' in sys.modules:
        return  # Already set up

    # Create fake package entries
    for name in ['webui', 'webui.backend', 'webui.backend.routes',
                 'webui.backend.routes.mmm']:
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = []
            pkg.__package__ = name
            sys.modules[name] = pkg

    # Point the mmm package to the actual directory
    mmm_pkg = sys.modules['webui.backend.routes.mmm']
    mmm_pkg.__path__ = [_MMM_PKG_DIR]


def _load_mmm_module(name):
    """Load an MMM submodule directly by file path."""
    full_name = f'webui.backend.routes.mmm.{name}'
    if full_name in sys.modules:
        return sys.modules[full_name]

    path = os.path.join(_MMM_PKG_DIR, f'{name}.py')
    spec = importlib.util.spec_from_file_location(
        full_name, path,
        submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'webui.backend.routes.mmm'
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Set up the fake package hierarchy
_setup_mmm_package()

# Load dependent modules in order (respecting import chain)
_constants = _load_mmm_module('mmm_constants')
_state = _load_mmm_module('mmm_state')
_trigger = _load_mmm_module('mmm_trigger')
_reversal = _load_mmm_module('mmm_reversal')


# ─── Test session fixture ────────────────────────────────────────────────────

def _make_session():
    """Minimal session for reversal tests."""
    return {
        'session_id': 'test-rev-001',
        'strategy_status': 'RUNNING',
        'params': {
            'cooldown_interval': 300,
            'adjustment_interval': 300,
        },
        'last_aggressor': None,
        'cooldown_active': False,
        'cooldown_until': None,
        'reversal_count': 0,
        'reversal_history': [],
        'adjustment_count': 0,
        'ce': {
            'active_strike': 105000,
            'trigger_snapshot': {'105000': 100.0},
            'original_lots': 5,
            'original_premium': 100.0,
            'adjustment_fills': [],
            'total_lots': 5,
            'active_lots': 5,
        },
        'pe': {
            'active_strike': 95000,
            'trigger_snapshot': {'95000': 90.0},
            'original_lots': 5,
            'original_premium': 90.0,
            'adjustment_fills': [],
            'total_lots': 5,
            'active_lots': 5,
        },
    }


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestDetectReversal:
    """Section 9: Reversal = last_aggressor changes."""

    def test_first_adjustment_not_reversal(self):
        session = _make_session()
        session['last_aggressor'] = None
        assert _reversal.detect_reversal(session, 'ce') is False

    def test_first_adjustment_none_string_not_reversal(self):
        session = _make_session()
        session['last_aggressor'] = 'NONE'
        assert _reversal.detect_reversal(session, 'ce') is False

    def test_same_side_not_reversal(self):
        session = _make_session()
        session['last_aggressor'] = 'CE'
        assert _reversal.detect_reversal(session, 'ce') is False

    def test_different_side_is_reversal(self):
        session = _make_session()
        session['last_aggressor'] = 'CE'
        assert _reversal.detect_reversal(session, 'pe') is True

    def test_reversal_pe_to_ce(self):
        session = _make_session()
        session['last_aggressor'] = 'PE'
        assert _reversal.detect_reversal(session, 'ce') is True


class TestCooldown:
    """Cooldown activation and checking."""

    def test_activate_cooldown(self):
        session = _make_session()
        session['params']['adjustment_interval'] = 300

        _reversal.activate_cooldown(session)
        assert session['cooldown_active'] is True
        assert session['cooldown_until'] is not None

    def test_is_cooldown_active_when_not_expired(self):
        session = _make_session()
        session['params']['adjustment_interval'] = 3600  # 1 hour

        _reversal.activate_cooldown(session)
        assert _reversal.is_cooldown_active(session) is True

    def test_is_cooldown_inactive_when_expired(self):
        session = _make_session()
        session['cooldown_active'] = True
        session['cooldown_until'] = (datetime.utcnow() - timedelta(seconds=10)).isoformat()

        assert _reversal.is_cooldown_active(session) is False
        assert session['cooldown_active'] is False  # Should auto-clear

    def test_no_cooldown_when_not_set(self):
        session = _make_session()
        assert _reversal.is_cooldown_active(session) is False

    def test_cooldown_idempotent(self):
        """Recommendation #4: activate_cooldown should NOT re-activate if already active."""
        session = _make_session()
        session['params']['adjustment_interval'] = 300

        _reversal.activate_cooldown(session)
        first_until = session['cooldown_until']

        _reversal.activate_cooldown(session)
        second_until = session['cooldown_until']

        assert first_until == second_until, "Cooldown should not re-activate when already active"


class TestSkipReversal:
    """Section 9: Skip reversal adjustment if P&L >= 0."""

    def test_skip_when_profitable(self):
        session = _make_session()
        should_skip, reason = _reversal.should_skip_reversal_adjustment(session, 50.0)
        assert should_skip is True
        assert 'profitable' in reason.lower() or 'skip' in reason.lower()

    def test_skip_when_breakeven(self):
        session = _make_session()
        should_skip, _ = _reversal.should_skip_reversal_adjustment(session, 0.0)
        assert should_skip is True

    def test_dont_skip_when_loss(self):
        session = _make_session()
        should_skip, _ = _reversal.should_skip_reversal_adjustment(session, -100.0)
        assert should_skip is False


class TestRecordReversal:
    """Recording reversal events."""

    def test_record_increments_count(self):
        session = _make_session()
        _reversal.record_reversal(session, 'ce', 'pe')
        assert session['reversal_count'] == 1

    def test_record_appends_history(self):
        session = _make_session()
        _reversal.record_reversal(session, 'ce', 'pe')
        assert len(session['reversal_history']) == 1
        entry = session['reversal_history'][0]
        assert entry['from'] == 'CE'
        assert entry['to'] == 'PE'

    def test_duplicate_record_suppressed(self):
        """Same direction change at same adj_count should not duplicate."""
        session = _make_session()
        _reversal.record_reversal(session, 'ce', 'pe')
        _reversal.record_reversal(session, 'ce', 'pe')  # Duplicate
        assert session['reversal_count'] == 1
        assert len(session['reversal_history']) == 1

    def test_different_adj_count_not_duplicate(self):
        """Same direction but different adj_count = new reversal event."""
        session = _make_session()
        _reversal.record_reversal(session, 'ce', 'pe')
        session['adjustment_count'] = 3
        _reversal.record_reversal(session, 'ce', 'pe')
        assert session['reversal_count'] == 2
        assert len(session['reversal_history']) == 2


class TestHandleReversalSkipTransition:
    """
    Critical fix: handle_reversal_skip_transition prevents infinite
    reversal detection loops when a reversal is skipped.
    """

    def test_updates_last_aggressor(self):
        """After skip, last_aggressor must match the new direction."""
        session = _make_session()
        session['last_aggressor'] = 'CE'

        _reversal.handle_reversal_skip_transition(session, 'pe', 120.0, 80.0)
        assert session['last_aggressor'] == 'PE'

    def test_updates_trigger_snapshots(self):
        """After skip, trigger snapshots must reflect current premiums."""
        session = _make_session()
        session['last_aggressor'] = 'CE'

        _reversal.handle_reversal_skip_transition(session, 'pe', 120.0, 80.0)

        ce_trigger = session['ce']['trigger_snapshot']['105000']
        pe_trigger = session['pe']['trigger_snapshot']['95000']
        assert ce_trigger == 120.0
        assert pe_trigger == 80.0

    def test_prevents_infinite_loop(self):
        """
        Simulate the infinite loop scenario:
        1. CE was aggressor (adjust_count=2)
        2. PE triggers → reversal detected
        3. Adjustment P&L ≥ 0 → skip
        4. Without fix: last_aggressor stays CE, PE triggers again → infinite reversal
        5. With fix: last_aggressor → PE, next cycle uses standard formula
        """
        session = _make_session()
        session['last_aggressor'] = 'CE'
        session['adjustment_count'] = 2

        # Step 1: Reversal detected (CE→PE)
        assert _reversal.detect_reversal(session, 'pe') is True

        # Step 2: P&L is positive → skip
        should_skip, _ = _reversal.should_skip_reversal_adjustment(session, 25.0)
        assert should_skip is True

        # Step 3: Apply the transition fix
        _reversal.handle_reversal_skip_transition(session, 'pe', 120.0, 80.0)

        # Step 4: VERIFY — next cycle should NOT detect reversal
        assert _reversal.detect_reversal(session, 'pe') is False

    def test_transition_preserves_session_structure(self):
        """Transition shouldn't corrupt session state."""
        session = _make_session()
        session['last_aggressor'] = 'CE'
        session['adjustment_count'] = 5
        session['reversal_count'] = 1

        _reversal.handle_reversal_skip_transition(session, 'pe', 130.0, 70.0)

        assert session['adjustment_count'] == 5
        assert session['reversal_count'] == 1
        assert 'ce' in session
        assert 'pe' in session
        assert 'params' in session

    def test_multiple_skip_transitions(self):
        """Multiple sequential reversals should all transition correctly."""
        session = _make_session()
        session['last_aggressor'] = 'CE'

        # First reversal skip: CE → PE
        _reversal.handle_reversal_skip_transition(session, 'pe', 120.0, 80.0)
        assert session['last_aggressor'] == 'PE'
        assert _reversal.detect_reversal(session, 'pe') is False

        # Second reversal skip: PE → CE
        _reversal.handle_reversal_skip_transition(session, 'ce', 130.0, 70.0)
        assert session['last_aggressor'] == 'CE'
        assert _reversal.detect_reversal(session, 'ce') is False
