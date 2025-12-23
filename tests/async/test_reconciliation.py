"""
Tests for Exchange Reconciliation System.
Tests missed fill detection, order verification, and emergency TP placement.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from bot.strategy.async_gridbot import AsyncGridBot
from bot.strategy.modules.event_store import EventStore


class TestReconciliationSystem:
    """Test suite for exchange reconciliation system."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Mock AsyncDeltaClient."""
        client = AsyncMock()
        client.list_orders = AsyncMock(return_value=[])
        client.get_order = AsyncMock(return_value={})
        return client
    
    @pytest.fixture
    def mock_position_actor(self):
        """Mock PositionManagerActor."""
        actor = AsyncMock()
        actor.ask = AsyncMock(return_value={
            "open_tranches": [],
            "pending_buy": None,
            "pending_sell": None
        })
        actor.tell = AsyncMock()
        return actor
    
    @pytest.fixture
    def mock_order_actor(self):
        """Mock OrderManagerActor."""
        actor = AsyncMock()
        actor.ask = AsyncMock(return_value={"status": "ok", "order_id": "test-tp-123"})
        return actor
    
    @pytest.fixture
    def bot(self, mock_api_client, mock_position_actor, mock_order_actor):
        """Create bot instance with mocked dependencies."""
        bot = AsyncGridBot(
            api_key="test-key",
            api_secret="test-secret",
            symbol="BTCUSD",
            mode="LONG",
            testnet=True
        )
        
        # Replace with mocks
        bot.api_client = mock_api_client
        bot.position_actor = mock_position_actor
        bot.order_actor = mock_order_actor
        
        return bot
    
    @pytest.mark.asyncio
    async def test_reconciliation_detects_missing_order(self, bot):
        """Test that reconciliation detects orders missing from exchange."""
        # Setup: Bot thinks it has an order, but exchange doesn't
        bot.position_actor.ask.return_value = {
            "open_tranches": [],
            "pending_buy": {"order_id": "order-123", "price": 100000},
            "pending_sell": None
        }
        
        # Exchange has no open orders
        bot.api_client.list_orders.return_value = []
        
        # Execute reconciliation
        await bot._perform_reconciliation()
        
        # Verify: Should investigate the missing order
        bot.api_client.get_order.assert_called_once_with("order-123")
    
    @pytest.mark.asyncio
    async def test_reconciliation_detects_missed_fill(self, bot):
        """Test that reconciliation detects and processes missed fills."""
        # Setup: Bot has pending order
        bot.position_actor.ask.return_value = {
            "open_tranches": [],
            "pending_buy": {"order_id": "order-123", "price": 100000},
            "pending_sell": None
        }
        
        # Exchange shows order as filled
        bot.api_client.list_orders.return_value = []
        bot.api_client.get_order.return_value = {
            "id": "order-123",
            "state": "filled",
            "side": "buy",
            "average_fill_price": 100000.0,
            "size": 1
        }
        
        # Mock _process_fill to track call
        bot._process_fill = AsyncMock()
        
        # Execute reconciliation
        await bot._perform_reconciliation()
        
        # Verify: Should process the missed fill
        bot._process_fill.assert_called_once()
        call_args = bot._process_fill.call_args[0][0]
        assert call_args["order_id"] == "order-123"
        assert call_args["side"] == "buy"
        assert call_args["fill_price"] == 100000.0
        assert call_args["_detected_via"] == "reconciliation_recovery"
    
    @pytest.mark.asyncio
    async def test_reconciliation_verifies_orders_exist(self, bot):
        """Test that reconciliation verifies pending orders exist on exchange."""
        # Setup: Bot has pending orders
        bot.position_actor.ask.return_value = {
            "open_tranches": [],
            "pending_buy": {"order_id": "buy-123", "price": 100000},
            "pending_sell": {"order_id": "sell-456", "price": 101000}
        }
        
        # Exchange has both orders
        bot.api_client.list_orders.return_value = [
            {"id": "buy-123", "state": "open"},
            {"id": "sell-456", "state": "open"}
        ]
        
        # Execute reconciliation
        await bot._perform_reconciliation()
        
        # Verify: No investigation needed (orders exist)
        bot.api_client.get_order.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_tp_verification_detects_missing_tp(self, bot):
        """Test that TP verification detects positions without TP protection."""
        # Setup: Position without TP
        state = {
            "open_tranches": [
                {
                    "entry_order_id": "pos-123",
                    "entry_price": 100000,
                    "size": 1,
                    "tp_order_id": "tp-999"  # TP order ID exists
                }
            ]
        }
        
        # Exchange orders (TP missing)
        exchange_orders = []  # No TP order on exchange
        
        # Mock emergency TP placement
        bot._emergency_tp_placement = AsyncMock()
        
        # Execute TP verification
        await bot._verify_tp_protection(state, exchange_orders)
        
        # Verify: Emergency TP should be placed
        bot._emergency_tp_placement.assert_called_once()
        call_args = bot._emergency_tp_placement.call_args[0][0]
        assert call_args["entry_order_id"] == "pos-123"
    
    @pytest.mark.asyncio
    async def test_tp_verification_accepts_valid_tp(self, bot):
        """Test that TP verification accepts positions with valid TP."""
        # Setup: Position with TP
        state = {
            "open_tranches": [
                {
                    "entry_order_id": "pos-123",
                    "entry_price": 100000,
                    "size": 1,
                    "tp_order_id": "tp-999"
                }
            ]
        }
        
        # Exchange has TP order
        exchange_orders = [
            {"id": "tp-999", "state": "open", "order_type": "limit_order"}
        ]
        
        # Mock emergency TP placement
        bot._emergency_tp_placement = AsyncMock()
        
        # Execute TP verification
        await bot._verify_tp_protection(state, exchange_orders)
        
        # Verify: No emergency TP needed
        bot._emergency_tp_placement.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_emergency_tp_placement(self, bot):
        """Test emergency TP placement for unprotected position."""
        # Setup position
        position = {
            "entry_order_id": "pos-123",
            "entry_price": 100000,
            "size": 1
        }
        
        # Mock grid calculator
        bot.grid_calc = MagicMock()
        bot.grid_calc.compute_tp_price = MagicMock(return_value=100500)
        
        # Execute emergency TP placement
        await bot._emergency_tp_placement(position)
        
        # Verify: TP order placed via order actor
        bot.order_actor.ask.assert_called_once()
        call_args = bot.order_actor.ask.call_args[0]
        assert call_args[0] == "PLACE_TP"
        assert call_args[1]["price"] == 100500
        assert call_args[1]["size"] == 1
        
        # Verify: Position updated with TP
        bot.position_actor.tell.assert_called_once_with(
            "UPDATE_POSITION_TP",
            {
                "position_id": "pos-123",
                "tp_order_id": "test-tp-123"
            }
        )
    
    @pytest.mark.asyncio
    async def test_reconciliation_handles_cancelled_order(self, bot):
        """Test that reconciliation handles cancelled orders."""
        # Setup: Bot has pending order
        bot.position_actor.ask.return_value = {
            "open_tranches": [],
            "pending_buy": {"order_id": "order-123", "price": 100000},
            "pending_sell": None
        }
        
        # Exchange shows order as cancelled
        bot.api_client.list_orders.return_value = []
        bot.api_client.get_order.return_value = {
            "id": "order-123",
            "state": "cancelled",
            "side": "buy"
        }
        
        # Execute reconciliation
        await bot._perform_reconciliation()
        
        # Verify: Should clear pending order (check that tell was called with CLEAR_PENDING_BUY)
        # Note: tell() is called with message type and payload dict
        calls = [call for call in bot.position_actor.tell.call_args_list 
                 if call[0][0] == "CLEAR_PENDING_BUY"]
        assert len(calls) > 0, "CLEAR_PENDING_BUY should have been called"
    
    @pytest.mark.asyncio
    async def test_reconciliation_loop_runs_periodically(self, bot):
        """Test that reconciliation loop runs at configured interval."""
        bot._running = True
        bot._reconciliation_interval = 0.1  # 100ms for test
        bot._reconciliation_initial_delay = 0  # No initial delay for test
        
        call_count = 0
        
        # Mock the perform method to track calls
        async def mock_perform():
            nonlocal call_count
            call_count += 1
            # Stop after 2 successful calls
            if call_count >= 2:
                bot._running = False
        
        # Replace the method
        bot._perform_reconciliation = mock_perform
        
        # Run loop in background
        task = asyncio.create_task(bot._reconciliation_loop())
        
        # Wait for at least 2 cycles (0.1s per cycle + overhead)
        await asyncio.sleep(0.5)
        
        # Ensure stopped
        bot._running = False
        
        # Wait a bit for the task to finish
        await asyncio.sleep(0.2)
        
        # Cancel task gracefully
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Verify: Multiple reconciliation cycles executed
        assert call_count >= 2, f"Expected at least 2 calls, got {call_count}"


class TestReconciliationIntegration:
    """Integration tests for reconciliation system."""
    
    @pytest.mark.asyncio
    async def test_full_missed_fill_recovery(self):
        """Integration test: missed fill detected and recovered."""
        # This would require more complex setup with real EventStore
        # and full bot initialization. Placeholder for now.
        pass
    
    @pytest.mark.asyncio
    async def test_multiple_unprotected_positions(self):
        """Integration test: multiple positions missing TP."""
        # Placeholder for comprehensive multi-position test
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
