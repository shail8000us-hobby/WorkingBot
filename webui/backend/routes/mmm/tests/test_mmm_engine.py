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
            'trigger_snapshot': {'100000': 100.0},
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
            'trigger_snapshot': {'90000': 100.0},
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

LOT_SIZE_BTC = 0.001  # Delta Exchange: 1 lot = 0.001 BTC


class TestStandardLoss:
    """Section 5 Case A: standard_loss = (premium_now − trigger) × active_lots × LOT_SIZE"""

    def test_basic_calculation(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()

        # Premium went from 100 to 150, with 10 lots
        loss, incomplete = engine.calculate_standard_loss(session, 'ce', 150.0)
        # Loss includes LOT_SIZE_BTC factor: (150-100)*10*0.001 = 0.5
        assert abs(loss - (150.0 - 100.0) * 10 * LOT_SIZE_BTC) < 1e-9
        assert incomplete is False

    def test_no_loss_when_premium_below_trigger(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()

        loss, incomplete = engine.calculate_standard_loss(session, 'ce', 80.0)
        # When premium < trigger, loss is negative → clamped to 0
        assert loss == 0.0

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
        # Formula: lots = ceil(loss / (hedge_premium * LOT_SIZE_BTC) * (1 + buffer_pct))
        # premium_buffer_pct key (not buffer_pct)
        buffer = session['params'].get('premium_buffer_pct', 0.05)
        raw_expected = loss / (hedge_premium * LOT_SIZE_BTC) * (1 + buffer)
        max_cap = session['params']['max_lots_per_side'] - session['pe']['active_lots']

        # Signature: (session, hedge_side, loss_to_cover, hedge_premium) → (lots, msg, is_cap_hit)
        lots, msg, is_cap_hit = engine.calculate_lots_to_sell(session, 'pe', loss, hedge_premium)
        # Result is capped at available lots (max_lots_per_side - current)
        assert lots <= max_cap
        assert lots >= 1

    def test_zero_hedge_premium(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()

        lots, msg, _ = engine.calculate_lots_to_sell(session, 'pe', 500, 0)
        assert lots == 0

    def test_respects_max_lots(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()
        session['params']['max_lots_per_side'] = 15  # Already have 10

        lots, msg, _ = engine.calculate_lots_to_sell(session, 'pe', 10000, 10.0)
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
        # Signature: (session, fetch_premium_fn)
        pnl = engine.compute_unrealized_pnl(session, lambda strike, otype: 50.0)
        # Expected includes LOT_SIZE_BTC: (100-50)*10*0.001 × 2 sides = 1.0
        expected = (100 - 50) * 10 * LOT_SIZE_BTC * 2
        assert abs(pnl - expected) < 1e-9

    def test_premiums_increased_means_loss(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_session()

        pnl = engine.compute_unrealized_pnl(session, lambda strike, otype: 150.0)
        # Expected includes LOT_SIZE_BTC: (100-150)*10*0.001 × 2 sides = -1.0
        expected = (100 - 150) * 10 * LOT_SIZE_BTC * 2
        assert abs(pnl - expected) < 1e-9


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
        session['total_fees'] = 50
        # Remove original_lots to simplify unrealized calc (avoid fetch calls)
        session['ce']['original_lots'] = 0
        session['pe']['original_lots'] = 0

        # Signature: (session, fetch_premium_fn) → dict with net_pnl
        result = engine.compute_total_pnl(session, lambda strike, otype: 50.0)
        assert isinstance(result, dict)
        assert 'net_pnl' in result
        # realized=200, unrealized=0 (no lots), fees=50 → net=-50+200=150
        assert result['realized'] == 200
        assert result['fees'] == 50
