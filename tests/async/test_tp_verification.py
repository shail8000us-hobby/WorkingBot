"""
Tests for TP Verification System.
Tests position scanning, TP validation, and emergency TP placement.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from bot.strategy.async_gridbot import AsyncGridBot


class TestTPVerificationSystem:
    """Test suite for TP verification system."""
    
    @pytest.fixture
    def bot(self):
        """Create bot instance with mocked dependencies."""
        bot = AsyncGridBot(
            api_key="test-key",
            api_secret="test-secret",
            symbol="BTCUSD",
            mode="LONG",
            testnet=True
        )
        
        # Mock dependencies
        bot.api_client = AsyncMock()
        bot.position_actor = AsyncMock()
        bot.order_actor = AsyncMock()
        bot.grid_calc = MagicMock()
        
        return bot
    
    @pytest.mark.asyncio
    async def test_no_positions_no_verification_needed(self, bot):
        """Test that verification passes when no positions exist."""
        state = {"open_tranches": []}
        exchange_orders = []
        
        bot._emergency_tp_placement = AsyncMock()
        
        await bot._verify_tp_protection(state, exchange_orders)
        
        # No emergency action needed
        bot._emergency_tp_placement.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_position_without_tp_order_id(self, bot):
        """Test detection of position missing TP order ID."""
        state = {
            "open_tranches": [
                {
                    "entry_order_id": "pos-123",
                    "entry_price": 100000,
                    "size": 1
                    # tp_order_id missing
                }
            ]
        }
        exchange_orders = []
        
        bot._emergency_tp_placement = AsyncMock()
        
        await bot._verify_tp_protection(state, exchange_orders)
        
        # Emergency TP should be placed
        bot._emergency_tp_placement.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_position_with_missing_tp_on_exchange(self, bot):
        """Test detection of TP order missing from exchange."""
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
        
        # TP order not on exchange
        exchange_orders = [
            {"id": "other-order", "state": "open"}
        ]
        
        bot._emergency_tp_placement = AsyncMock()
        
        await bot._verify_tp_protection(state, exchange_orders)
        
        # Emergency TP should be placed
        bot._emergency_tp_placement.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_all_positions_protected(self, bot):
        """Test verification passes when all positions have valid TPs."""
        state = {
            "open_tranches": [
                {
                    "entry_order_id": "pos-1",
                    "entry_price": 100000,
                    "size": 1,
                    "tp_order_id": "tp-1"
                },
                {
                    "entry_order_id": "pos-2",
                    "entry_price": 101000,
                    "size": 1,
                    "tp_order_id": "tp-2"
                }
            ]
        }
        
        exchange_orders = [
            {"id": "tp-1", "state": "open"},
            {"id": "tp-2", "state": "open"}
        ]
        
        bot._emergency_tp_placement = AsyncMock()
        
        await bot._verify_tp_protection(state, exchange_orders)
        
        # No emergency action needed
        bot._emergency_tp_placement.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_multiple_unprotected_positions(self, bot):
        """Test handling of multiple positions without TP."""
        state = {
            "open_tranches": [
                {
                    "entry_order_id": "pos-1",
                    "entry_price": 100000,
                    "size": 1,
                    "tp_order_id": "tp-1"  # Missing from exchange
                },
                {
                    "entry_order_id": "pos-2",
                    "entry_price": 101000,
                    "size": 1
                    # No TP order ID
                },
                {
                    "entry_order_id": "pos-3",
                    "entry_price": 102000,
                    "size": 1,
                    "tp_order_id": "tp-3"  # Exists on exchange
                }
            ]
        }
        
        exchange_orders = [
            {"id": "tp-3", "state": "open"}  # Only pos-3 protected
        ]
        
        bot._emergency_tp_placement = AsyncMock()
        
        await bot._verify_tp_protection(state, exchange_orders)
        
        # Emergency TP should be called twice (for pos-1 and pos-2)
        assert bot._emergency_tp_placement.call_count == 2
    
    @pytest.mark.asyncio
    async def test_emergency_tp_calculates_correct_price_long(self, bot):
        """Test emergency TP price calculation for LONG mode."""
        bot.mode = "LONG"
        bot.grid_calc.compute_tp_price = MagicMock(return_value=100500)
        bot.order_actor.ask.return_value = {"status": "ok", "order_id": "emergency-tp"}
        
        position = {
            "entry_order_id": "pos-123",
            "entry_price": 100000,
            "size": 1
        }
        
        await bot._emergency_tp_placement(position)
        
        # Verify TP price calculated correctly
        bot.grid_calc.compute_tp_price.assert_called_once_with(100000, "LONG")
    
    @pytest.mark.asyncio
    async def test_emergency_tp_calculates_correct_price_short(self, bot):
        """Test emergency TP price calculation for SHORT mode."""
        bot.mode = "SHORT"
        bot.grid_calc.compute_tp_price = MagicMock(return_value=99500)
        bot.order_actor.ask.return_value = {"status": "ok", "order_id": "emergency-tp"}
        
        position = {
            "entry_order_id": "pos-123",
            "entry_price": 100000,
            "size": 1
        }
        
        await bot._emergency_tp_placement(position)
        
        # Verify TP price calculated correctly
        bot.grid_calc.compute_tp_price.assert_called_once_with(100000, "SHORT")
    
    @pytest.mark.asyncio
    async def test_emergency_tp_uses_correct_size(self, bot):
        """Test emergency TP uses position size."""
        bot.grid_calc.compute_tp_price = MagicMock(return_value=100500)
        bot.order_actor.ask.return_value = {"status": "ok", "order_id": "emergency-tp"}
        
        position = {
            "entry_order_id": "pos-123",
            "entry_price": 100000,
            "size": 5  # Custom size
        }
        
        await bot._emergency_tp_placement(position)
        
        # Verify size matches position
        call_args = bot.order_actor.ask.call_args[0][1]
        assert call_args["size"] == 5
    
    @pytest.mark.asyncio
    async def test_emergency_tp_updates_position_state(self, bot):
        """Test that emergency TP updates position with new TP order ID."""
        bot.grid_calc.compute_tp_price = MagicMock(return_value=100500)
        bot.order_actor.ask.return_value = {"status": "ok", "order_id": "emergency-tp-123"}
        
        position = {
            "entry_order_id": "pos-123",
            "entry_price": 100000,
            "size": 1
        }
        
        await bot._emergency_tp_placement(position)
        
        # Verify position updated
        bot.position_actor.tell.assert_called_once_with(
            "UPDATE_POSITION_TP",
            {
                "position_id": "pos-123",
                "tp_order_id": "emergency-tp-123"
            }
        )
    
    @pytest.mark.asyncio
    async def test_emergency_tp_handles_placement_failure(self, bot):
        """Test handling of emergency TP placement failure."""
        bot.grid_calc.compute_tp_price = MagicMock(return_value=100500)
        bot.order_actor.ask.return_value = {"status": "error", "error": "Insufficient margin"}
        
        position = {
            "entry_order_id": "pos-123",
            "entry_price": 100000,
            "size": 1
        }
        
        # Should not raise exception (logged instead)
        await bot._emergency_tp_placement(position)
        
        # Position should not be updated on failure
        bot.position_actor.tell.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_emergency_tp_handles_missing_entry_price(self, bot):
        """Test handling of position with missing entry price."""
        position = {
            "entry_order_id": "pos-123",
            # entry_price missing
            "size": 1
        }
        
        bot.order_actor.ask = AsyncMock()
        
        await bot._emergency_tp_placement(position)
        
        # Should not attempt to place TP without entry price
        bot.order_actor.ask.assert_not_called()


class TestTPVerificationIntegration:
    """Integration tests for TP verification."""
    
    @pytest.mark.asyncio
    async def test_tp_verification_with_reconciliation(self):
        """Integration test: TP verification as part of reconciliation."""
        # Placeholder for full integration test
        pass
    
    @pytest.mark.asyncio
    async def test_tp_verification_stress_many_positions(self):
        """Stress test: verify many positions efficiently."""
        # Placeholder for stress test with 100+ positions
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
