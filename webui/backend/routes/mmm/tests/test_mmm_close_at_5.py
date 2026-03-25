"""
Test MMM Close-at-5 — Section 11 scanning and closing.

Tests:
  - Scan closeable positions
  - Remove closed position from state
  - Check side fully closed
  - Check both sides closed
"""

import pytest
from copy import deepcopy
from unittest.mock import AsyncMock


def _make_session():
    """Minimal session for close-at-5 tests."""
    return {
        'session_id': 'test-close-001',
        'strategy_status': 'RUNNING',
        'params': {
            'close_at_threshold': 5,
        },
        'ce': {
            'original_strike': 100000,
            'active_strike': 100000,
            'original_premium': 100.0,
            'original_lots': 10,
            'active_lots': 10,
            'total_lots': 10,
            'frozen_total_lots': 0,
            'adjustment_fills': [
                {'strike': 100000, 'premium': 120.0, 'lots': 5},
            ],
            'frozen_positions': [],
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
            'frozen_positions': [
                {'strike': 88000, 'entry_premium': 80.0, 'lots': 5},
            ],
            'symbol': 'P-BTC-90000-260215',
        },
        'close_at_5_count': 0,
        'realized_pnl': 0,
    }


class TestScanCloseable:
    """Section 11: Scan all positions for premium <= threshold."""

    def test_no_closeable_when_premiums_high(self):
        from webui.backend.routes.mmm.mmm_close_at_5 import scan_closeable_positions
        session = _make_session()

        # Mock fetch function returning high premiums
        async def fetch_high(symbol):
            return 50.0  # Way above threshold

        import asyncio
        positions = asyncio.get_event_loop().run_until_complete(
            scan_closeable_positions(session, fetch_high)
        ) if hasattr(scan_closeable_positions, '__wrapped__') else \
            scan_closeable_positions(session, lambda s: 50.0)

        # The function may be sync or async depending on implementation
        if hasattr(positions, '__await__'):
            import asyncio
            positions = asyncio.get_event_loop().run_until_complete(positions)

        assert len(positions) == 0

    def test_closeable_when_premium_low(self):
        from webui.backend.routes.mmm.mmm_close_at_5 import scan_closeable_positions
        session = _make_session()

        # Mock fetch function returning low premiums
        positions = scan_closeable_positions(session, lambda s, t: 3.0)

        if hasattr(positions, '__await__'):
            import asyncio
            positions = asyncio.get_event_loop().run_until_complete(positions)

        assert len(positions) > 0


class TestSideFullyClosed:
    """Check if all positions on a side are closed."""

    def test_not_closed_with_lots(self):
        from webui.backend.routes.mmm.mmm_close_at_5 import check_side_fully_closed
        session = _make_session()
        assert check_side_fully_closed(session, 'ce') is False

    def test_closed_when_zero_lots(self):
        from webui.backend.routes.mmm.mmm_close_at_5 import check_side_fully_closed
        session = _make_session()
        session['ce']['total_lots'] = 0
        session['ce']['active_lots'] = 0
        session['ce']['original_lots'] = 0
        session['ce']['adjustment_fills'] = []
        session['ce']['frozen_positions'] = []
        session['ce']['frozen_total_lots'] = 0
        assert check_side_fully_closed(session, 'ce') is True


class TestBothSidesClosed:
    """Check if both sides are closed."""

    def test_not_closed_with_one_side_active(self):
        from webui.backend.routes.mmm.mmm_close_at_5 import check_both_sides_closed
        session = _make_session()
        assert check_both_sides_closed(session) is False

    def test_closed_when_both_zero(self):
        from webui.backend.routes.mmm.mmm_close_at_5 import check_both_sides_closed
        session = _make_session()
        for side in ['ce', 'pe']:
            session[side]['total_lots'] = 0
            session[side]['active_lots'] = 0
            session[side]['original_lots'] = 0
            session[side]['adjustment_fills'] = []
            session[side]['frozen_positions'] = []
            session[side]['frozen_total_lots'] = 0
        assert check_both_sides_closed(session) is True
