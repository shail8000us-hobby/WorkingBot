"""
Test MMM Engine — Section 5 adjustment logic, P&L computation.

Tests:
  - Standard loss calculation
  - Reversal P&L calculation
  - Lots-to-sell calculation with buffer
  - State update after adjustment
  - Unrealized + total P&L computation
  - Reconciliation
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from copy import deepcopy

# ---------------------------------------------------------------------------
# Minimal session fixture
# ---------------------------------------------------------------------------

def _make_session():
    """Create a minimal session dict for testing."""
    return {
        'session_id': 'test-001',
        'strategy_status': 'RUNNING',
        'params': {
            'desired_ce_premium': 100,
            'desired_pe_premium': 100,
            'initial_lots': 10,
            'buffer_pct': 0.05,
            'max_lots_per_side': 100,
            'max_adjustments': 30,
            'max_loss_amount': 5000,
            'min_trigger_move': 3,
            'close_at_threshold': 5,
            'adjustment_interval': 300,
        },
        'ce': {
            'original_strike': 100000,
            'active_strike': 100000,
            'original_premium': 100.0,
            'original_lots': 10,
            'active_lots': 10,
            'total_lots': 10,
            'frozen_total_lots': 0,
            'adjustment_fills': [],
            'frozen_positions': [],
            'adjustment_avg': 0,
            'symbol': 'C-BTC-100000-260215',
        },
        'pe': {
            'original_strike': 90000,
            'active_strike': 90000,
            'original_premium': 100.0,
            'original_lots': 10,
            'active_lots': 10,
            'total_lots': 10,
            'frozen_total_lots': 0,
            'adjustment_fills': [],
            'frozen_positions': [],
            'adjustment_avg': 0,
            'symbol': 'P-BTC-90000-260215',
        },
        'trigger_snapshots': {
            'ce': {'100000': 100.0},
            'pe': {'90000': 100.0},
        },
        'adjustment_count': 0,
        'reversal_count': 0,
        'shift_count': 0,
        'close_at_5_count': 0,
        'last_aggressor': None,
        'cooldown_active': False,
        'realized_pnl': 0,
        'unrealized_pnl': 0,
        'total_fees': 0,
        'total_premium_collected': 2000.0,
        'peak_pnl': 0,
        'adjustment_history': [],
        'pnl_timeline': [],
    }


# ---------------------------------------------------------------------------
# Tests: calculate_standard_loss
# ---------------------------------------------------------------------------

class TestStandardLoss:
    """Section 5 Case A: standard_loss = (premium_now − trigger) × active_lots"""

    def test_basic_calculation(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()

        # Premium went from 100 to 150, with 10 lots
        loss, incomplete = engine.calculate_standard_loss(session, 'ce', 150.0)
        assert loss == (150.0 - 100.0) * 10  # 500
        assert incomplete is False

    def test_no_loss_when_premium_below_trigger(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()

        loss, incomplete = engine.calculate_standard_loss(session, 'ce', 80.0)
        # Even negative, it's computed; the trigger check happens elsewhere
        assert loss == (80.0 - 100.0) * 10  # -200

    def test_zero_active_lots(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()
        session['ce']['active_lots'] = 0

        loss, incomplete = engine.calculate_standard_loss(session, 'ce', 150.0)
        assert loss == 0


# ---------------------------------------------------------------------------
# Tests: calculate_lots_to_sell
# ---------------------------------------------------------------------------

class TestLotsToSell:
    """Section 5: lots = ceil(loss / hedge_premium × (1 + buffer))"""

    def test_basic_calculation(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()

        import math
        loss = 500
        hedge_premium = 100.0
        buffer = session['params']['buffer_pct']
        expected = math.ceil((loss / hedge_premium) * (1 + buffer))

        lots = engine.calculate_lots_to_sell(session, loss, hedge_premium)
        assert lots == expected

    def test_zero_hedge_premium(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()

        lots = engine.calculate_lots_to_sell(session, 500, 0)
        assert lots == 0

    def test_respects_max_lots(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()
        session['params']['max_lots_per_side'] = 15  # Already have 10

        lots = engine.calculate_lots_to_sell(session, 10000, 10.0)
        # Should be capped to max_lots - current
        assert lots <= 15 - 10  # max 5 more


# ---------------------------------------------------------------------------
# Tests: compute_unrealized_pnl
# ---------------------------------------------------------------------------

class TestUnrealizedPnl:
    """P&L computation for open positions."""

    def test_premiums_decreased_means_profit(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()

        # We sold at 100, now at 50 → profit
        pnl = engine.compute_unrealized_pnl(session, ce_now=50.0, pe_now=50.0)
        expected = (100 - 50) * 10 + (100 - 50) * 10  # 500 + 500
        assert pnl == expected

    def test_premiums_increased_means_loss(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()

        pnl = engine.compute_unrealized_pnl(session, ce_now=150.0, pe_now=150.0)
        expected = (100 - 150) * 10 + (100 - 150) * 10  # -500 + -500
        assert pnl == expected


# ---------------------------------------------------------------------------
# Tests: compute_total_pnl
# ---------------------------------------------------------------------------

class TestTotalPnl:
    """Total P&L = realized + unrealized - fees."""

    def test_total_pnl_calculation(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()
        session['realized_pnl'] = 200
        session['unrealized_pnl'] = 300
        session['total_fees'] = 50

        total = engine.compute_total_pnl(session)
        assert total == 200 + 300 - 50
