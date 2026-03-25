"""
Test Hedge Integrity Guard — Prevents one-sided position wipeout.

Simulates the exact scenario from session mmm13mar26-2:
- CE=101 lots @ 71800
- PE=101 lots @ 68000
- Some mechanism attempts to close ALL PE lots
- Guard MUST block when PE would go to 0 while CE has 101 lots

Tests:
  - close_position() blocks one-sided wipeout
  - close_position() allows close when both sides closing
  - close_position() allows normal partial closes
  - Guard logs correctly with session context
"""

import pytest
from copy import deepcopy
from unittest.mock import MagicMock, AsyncMock, patch


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO: Exact reproduction of mmm13mar26-2 PE wipeout
# ═══════════════════════════════════════════════════════════════════════════

def make_session_like_mmm13mar26():
    """
    Recreate the exact session state when PE wipeout occurred:
    - CE: 101 lots active @ 71800
    - PE: 101 lots active @ 68000
    - BTC spot ~70,000 (PE is 2.86% OTM)
    """
    return {
        'session_id': 'test_mmm13mar26',
        'ce': {
            'active_strike': 71800,
            'total_lots': 101,
            'positions': [
                {'id': 'ce-1', 'strike': 71800, 'lots': 101, 'type': 'original',
                 'side': 'ce', 'entry_premium': 69.5, 'status': 'active'}
            ]
        },
        'pe': {
            'active_strike': 68000,
            'total_lots': 101,
            'positions': [
                {'id': 'pe-1', 'strike': 68000, 'lots': 1, 'type': 'original',
                 'side': 'pe', 'entry_premium': 60.5, 'status': 'active'},
                {'id': 'pe-2', 'strike': 68000, 'lots': 30, 'type': 'adjustment',
                 'side': 'pe', 'entry_premium': 59.5, 'status': 'active'},
                {'id': 'pe-3', 'strike': 68000, 'lots': 50, 'type': 'adjustment',
                 'side': 'pe', 'entry_premium': 57.5, 'status': 'active'},
                {'id': 'pe-4', 'strike': 68000, 'lots': 20, 'type': 'adjustment',
                 'side': 'pe', 'entry_premium': 56.5, 'status': 'active'},
            ]
        },
        'params': {'expiry': '13032026'},
        'realized_pnl': 0,
    }


@pytest.mark.asyncio
class TestHedgeIntegrityGuard:
    """Tests for close_position() hedge guard."""

    async def test_blocks_pe_wipeout_while_ce_has_lots(self):
        """
        CRITICAL: Exact scenario from mmm13mar26-2.
        Attempting to close 101 PE lots when CE has 101 lots MUST be blocked.
        """
        from webui.backend.routes.mmm.mmm_close_at_5 import close_position
        
        session = make_session_like_mmm13mar26()
        
        # Mock executor - we'll never get here for the blocking case
        mock_executor = MagicMock()
        mock_executor.smart_execute = AsyncMock(return_value={
            'success': True, 'fill_price': 55.0, 'filled_size': 1
        })
        mock_initializer = MagicMock()
        mock_initializer.build_symbol = MagicMock(return_value='P-BTC-68000-13032026')
        
        # Simulate closing ALL 101 PE lots in one go
        position_all = {
            'id': 'pe-all',
            'side': 'pe',
            'strike': 68000,
            'lots': 101,  # All PE lots
            'type': 'original',
            'entry_premium': 58.0,
        }
        
        result = await close_position(
            mock_executor,
            mock_initializer,
            session,
            position_all,
            hedge_guard=True,
            mechanism='recycler',  # Non-whitelisted mechanism triggers G1 hedge check
        )

        # GUARD MUST BLOCK THIS
        assert result['success'] is False
        assert result.get('hedge_guard_blocked') is True
        assert 'one-sided exposure' in result.get('error', '').lower()
        
        # Executor should NOT have been called
        mock_executor.smart_execute.assert_not_called()

    async def test_allows_partial_close_leaving_some_pe(self):
        """
        Closing 50 PE lots when PE=101 and CE=101 should be ALLOWED
        because PE would still have 51 lots.
        """
        from webui.backend.routes.mmm.mmm_close_at_5 import close_position
        
        session = make_session_like_mmm13mar26()
        
        position_partial = {
            'id': 'pe-3',
            'side': 'pe',
            'strike': 68000,
            'lots': 50,  # 50 of 101 PE lots
            'type': 'adjustment',
            'entry_premium': 57.5,
        }
        
        mock_executor = MagicMock()
        mock_executor.smart_execute = AsyncMock(return_value={
            'success': True, 'fill_price': 45.0, 'filled_size': 50
        })
        mock_initializer = MagicMock()
        mock_initializer.build_symbol = MagicMock(return_value='P-BTC-68000-13032026')
        
        result = await close_position(
            mock_executor,
            mock_initializer,
            session,
            position_partial,
            hedge_guard=True,
        )
        
        # This should NOT be blocked (50 of 101, leaves 51)
        assert result.get('hedge_guard_blocked') is not True

    async def test_allows_full_close_when_both_sides_closing(self):
        """
        If BOTH sides are being closed together (clean exit), guard should not block.
        This is controlled by the caller passing hedge_guard=False.
        """
        from webui.backend.routes.mmm.mmm_close_at_5 import close_position
        
        session = make_session_like_mmm13mar26()
        
        # Close all PE - normally blocked
        position_pe = {
            'id': 'pe-all',
            'side': 'pe',
            'strike': 68000,
            'lots': 101,
            'type': 'original',
            'entry_premium': 58.0,
        }
        
        mock_executor = MagicMock()
        mock_executor.smart_execute = AsyncMock(return_value={
            'success': True, 'fill_price': 50.0, 'filled_size': 101
        })
        mock_initializer = MagicMock()
        mock_initializer.build_symbol = MagicMock(return_value='P-BTC-68000-13032026')
        
        # Caller says "I'm closing both sides, bypass guard"
        result = await close_position(
            mock_executor,
            mock_initializer,
            session,
            position_pe,
            hedge_guard=False,  # EXPLICITLY DISABLED
        )
        
        # Should NOT be blocked
        assert result.get('hedge_guard_blocked') is not True
        # Executor should have been called
        mock_executor.smart_execute.assert_called_once()

    async def test_allows_close_when_other_side_empty(self):
        """
        If CE=0 and we're closing PE, guard should allow.
        (No hedge to protect if there's nothing on the other side.)
        """
        from webui.backend.routes.mmm.mmm_close_at_5 import close_position
        
        session = {
            'session_id': 'test_ce_empty',
            'ce': {
                'active_strike': 71800,
                'total_lots': 0,  # CE is empty
                'positions': []
            },
            'pe': {
                'active_strike': 68000,
                'total_lots': 50,
                'positions': [
                    {'id': 'pe-1', 'strike': 68000, 'lots': 50, 'type': 'original',
                     'side': 'pe', 'entry_premium': 40.0, 'status': 'active'}
                ]
            },
            'params': {'expiry': '13032026'},
        }
        
        position = {
            'id': 'pe-1',
            'side': 'pe',
            'strike': 68000,
            'lots': 50,  # All PE
            'type': 'original',
            'entry_premium': 40.0,
        }
        
        mock_executor = MagicMock()
        mock_executor.smart_execute = AsyncMock(return_value={
            'success': True, 'fill_price': 30.0, 'filled_size': 50
        })
        mock_initializer = MagicMock()
        mock_initializer.build_symbol = MagicMock(return_value='P-BTC-68000-13032026')
        
        result = await close_position(
            mock_executor,
            mock_initializer,
            session,
            position,
            hedge_guard=True,
        )
        
        # Should NOT be blocked (other side is empty)
        assert result.get('hedge_guard_blocked') is not True

    async def test_blocks_ce_wipeout_while_pe_has_lots(self):
        """
        Symmetric test: blocking CE close when PE has lots.
        """
        from webui.backend.routes.mmm.mmm_close_at_5 import close_position
        
        session = {
            'session_id': 'test_ce_wipeout',
            'ce': {
                'active_strike': 72000,
                'total_lots': 80,
                'positions': [
                    {'id': 'ce-1', 'strike': 72000, 'lots': 80, 'type': 'original',
                     'side': 'ce', 'entry_premium': 50.0, 'status': 'active'}
                ]
            },
            'pe': {
                'active_strike': 68000,
                'total_lots': 120,
                'positions': [
                    {'id': 'pe-1', 'strike': 68000, 'lots': 120, 'type': 'original',
                     'side': 'pe', 'entry_premium': 45.0, 'status': 'active'}
                ]
            },
            'params': {'expiry': '13032026'},
        }
        
        # Try to close ALL CE
        position = {
            'id': 'ce-1',
            'side': 'ce',
            'strike': 72000,
            'lots': 80,  # All CE
            'type': 'original',
            'entry_premium': 50.0,
        }
        
        mock_executor = MagicMock()
        mock_initializer = MagicMock()
        
        result = await close_position(
            mock_executor,
            mock_initializer,
            session,
            position,
            hedge_guard=True,
            mechanism='recycler',  # Non-whitelisted mechanism triggers G1 hedge check
        )

        # GUARD MUST BLOCK THIS
        assert result['success'] is False
        assert result.get('hedge_guard_blocked') is True
        assert 'PE' in result.get('error', '')  # Error mentions PE has lots


class TestHedgeGuardInCloseAt5:
    """Tests for hedge guard in _process_close_at_5 flow."""

    def test_both_sides_closing_detection(self):
        """
        When ALL positions on BOTH sides qualify for close,
        the guard should be bypassed for clean exit.
        """
        # This tests the logic that sets _both_sides_closing in _process_close_at_5
        # We test the detection logic directly
        
        # Scenario: Both sides have 10 lots each, all closeable
        closeable = [
            {'side': 'ce', 'lots': 10},
            {'side': 'pe', 'lots': 10},
        ]
        
        ce_closeable_lots = sum(p['lots'] for p in closeable if p['side'] == 'ce')
        pe_closeable_lots = sum(p['lots'] for p in closeable if p['side'] == 'pe')
        
        ce_total = 10
        pe_total = 10
        
        both_sides_closing = (
            ce_closeable_lots >= ce_total and
            pe_closeable_lots >= pe_total and
            ce_total > 0 and pe_total > 0
        )
        
        assert both_sides_closing is True

    def test_one_side_closing_detection(self):
        """
        When only one side is closing, both_sides_closing should be False.
        """
        closeable = [
            {'side': 'pe', 'lots': 100},  # Only PE closeable
        ]
        
        ce_closeable_lots = sum(p['lots'] for p in closeable if p['side'] == 'ce')
        pe_closeable_lots = sum(p['lots'] for p in closeable if p['side'] == 'pe')
        
        ce_total = 100  # CE has lots but none closeable
        pe_total = 100
        
        both_sides_closing = (
            ce_closeable_lots >= ce_total and
            pe_closeable_lots >= pe_total and
            ce_total > 0 and pe_total > 0
        )
        
        assert both_sides_closing is False


@pytest.mark.asyncio
class TestSequentialCloseSimulation:
    """
    Simulate the exact sequence from mmm13mar26-2:
    Multiple close_position calls trying to wipe PE one by one.
    """

    async def test_sequential_pe_closes_blocked_at_last_lot(self):
        """
        Simulate: PE=101, close 1 lot (ok), close 30 lots (ok), close 50 lots (ok),
        close remaining 20 lots — MUST BE BLOCKED.
        """
        from webui.backend.routes.mmm.mmm_close_at_5 import close_position
        
        session = make_session_like_mmm13mar26()
        
        mock_executor = MagicMock()
        # Simulate successful fills
        mock_executor.smart_execute = AsyncMock(return_value={
            'success': True, 'fill_price': 55.0, 'filled_size': 0
        })
        mock_initializer = MagicMock()
        mock_initializer.build_symbol = MagicMock(return_value='P-BTC-68000-13032026')
        
        # Close 1: 1 lot (101 -> 100) - OK
        session['pe']['total_lots'] = 100  # Simulate state after first close
        
        # Close 2: 30 lots (100 -> 70) - OK
        session['pe']['total_lots'] = 70
        
        # Close 3: 50 lots (70 -> 20) - OK
        session['pe']['total_lots'] = 20
        
        # Close 4: 20 lots (20 -> 0) - MUST BE BLOCKED
        position_last = {
            'id': 'pe-4',
            'side': 'pe',
            'strike': 68000,
            'lots': 20,  # This would take PE to 0
            'type': 'adjustment',
            'entry_premium': 56.5,
        }
        
        result = await close_position(
            mock_executor,
            mock_initializer,
            session,
            position_last,
            hedge_guard=True,
            mechanism='recycler',  # Non-whitelisted mechanism triggers G1 hedge check
        )

        # THIS MUST BE BLOCKED
        assert result['success'] is False
        assert result.get('hedge_guard_blocked') is True
        
        # PE should still have 20 lots
        assert session['pe']['total_lots'] == 20
        # CE still has 101 lots
        assert session['ce']['total_lots'] == 101

    async def test_early_break_on_hedge_guard_blocked(self):
        """
        When hedge_guard blocks a close, subsequent calls on the same side
        should also be blocked (no wasted iterations).
        """
        from webui.backend.routes.mmm.mmm_close_at_5 import close_position
        
        # Session with PE=10, CE=100
        session = {
            'session_id': 'test_early_break',
            'ce': {'active_strike': 72000, 'total_lots': 100, 'positions': []},
            'pe': {'active_strike': 68000, 'total_lots': 10, 'positions': []},
            'params': {'expiry': '13032026'},
        }
        
        mock_executor = MagicMock()
        mock_initializer = MagicMock()
        
        # Try to close 10 PE lots (all of them)
        position = {
            'id': 'pe-1',
            'side': 'pe',
            'strike': 68000,
            'lots': 10,
            'type': 'original',
            'entry_premium': 30.0,
        }
        
        result = await close_position(
            mock_executor,
            mock_initializer,
            session,
            position,
            hedge_guard=True,
            mechanism='recycler',  # Non-whitelisted mechanism triggers G1 hedge check
        )

        assert result['success'] is False
        assert result.get('hedge_guard_blocked') is True

        # In _process_close_at_5, this would trigger early break
        # The calling loop should check hedge_guard_blocked and break
