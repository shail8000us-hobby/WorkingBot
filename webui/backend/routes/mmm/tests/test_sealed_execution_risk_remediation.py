"""
Sealed regression + adversarial tests for Priority Remediation Sprint

SEALED — v1.0.0 — April 14, 2026

Tests for each fix:
- H-1: Adjustment open-leg orphan recovery (execute_adjustment)
- H-3: Entry rollback emergency escalation (execute_entry)
- H-2: Fill-price fallback accuracy (_h2_exchange_fill_lookup)
- M-5: max_loss misconfiguration hard alert (check_max_loss)
- M-3: Zombie circuit breaker auto-pause (should_auto_pause)
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch


# ══════════════════════════════════════════════════════════════════════════════
# M-5: max_loss_amount <= 0 → CRITICAL safety event (not silent return)
# ══════════════════════════════════════════════════════════════════════════════


def _session_ml(realized=0.0, unrealized=0.0, perp_r=0.0, perp_u=0.0, max_loss=1000.0):
    return {
        'params': {'max_loss_amount': max_loss},
        'realized_pnl': realized,
        'unrealized_pnl': unrealized,
        'perp_hedge': {
            'realized_pnl': perp_r,
            'unrealized_pnl': perp_u,
        },
    }


@pytest.fixture
def safety():
    from webui.backend.routes.mmm.mmm_safety import MMMSafety
    return MMMSafety()


class TestM5MaxLossMisconfig:
    """M-5 FIX: max_loss <= 0 must emit CRITICAL event, not return silently."""

    @pytest.mark.sealed
    def test_m5_reg1_max_loss_zero_emits_critical(self, safety):
        """REG-1: max_loss=0 → CRITICAL event emitted."""
        events = safety.check_max_loss(_session_ml(unrealized=-999999.0, max_loss=0.0))
        assert len(events) == 1
        assert events[0]['type'] == 'max_loss_config'
        assert events[0]['level'] == 'critical'
        assert events[0]['action'] == 'warn'

    @pytest.mark.sealed
    def test_m5_reg2_max_loss_negative_emits_critical(self, safety):
        """REG-2: max_loss=-100 → CRITICAL event emitted."""
        events = safety.check_max_loss(_session_ml(unrealized=-999999.0, max_loss=-100.0))
        assert len(events) == 1
        assert events[0]['type'] == 'max_loss_config'
        assert events[0]['level'] == 'critical'
        assert events[0]['details']['max_loss_amount'] == -100.0

    @pytest.mark.sealed
    def test_m5_adv1_action_is_warn_not_auto_close(self, safety):
        """ADV-1: action must be 'warn' (not 'auto_close') to prevent position closure."""
        events = safety.check_max_loss(_session_ml(unrealized=-999999.0, max_loss=0.0))
        assert events[0]['action'] == 'warn'
        assert events[0]['action'] != 'auto_close'

    @pytest.mark.sealed
    def test_m5_adv2_positive_max_loss_unchanged(self, safety):
        """ADV-2: Positive max_loss still works normally (no regression)."""
        events = safety.check_max_loss(_session_ml(unrealized=-500.0, max_loss=1000.0))
        assert events == []  # -500 is within -1000 threshold


# ══════════════════════════════════════════════════════════════════════════════
# M-3: Zombie circuit breaker auto-pause
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def cb():
    from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitBreaker
    return CircuitBreaker('test-session', failure_threshold=3)


class TestM3ZombieAutoP:
    """M-3 FIX: should_auto_pause triggers after deep consecutive OPEN."""

    @pytest.mark.sealed
    def test_m3_reg1_5_consecutive_opens_auto_pause(self, cb):
        """REG-1: 5 consecutive opens → should_auto_pause=True."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import (
            CircuitState, AUTO_PAUSE_CONSECUTIVE_OPENS,
        )
        cb._state = CircuitState.OPEN
        cb._consecutive_opens = AUTO_PAUSE_CONSECUTIVE_OPENS
        assert cb.should_auto_pause is True

    @pytest.mark.sealed
    def test_m3_reg2_recovery_resets_auto_pause(self, cb):
        """REG-2: After recovery (success), should_auto_pause resets to False."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        cb._state = CircuitState.OPEN
        cb._consecutive_opens = 10
        assert cb.should_auto_pause is True
        # Simulate recovery
        cb._state = CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.should_auto_pause is False
        assert cb._consecutive_opens == 0

    @pytest.mark.sealed
    def test_m3_adv1_4_consecutive_not_yet_auto_pause(self, cb):
        """ADV-1: 4 consecutive opens → should_auto_pause=False (below threshold)."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import (
            CircuitState, AUTO_PAUSE_CONSECUTIVE_OPENS,
        )
        cb._state = CircuitState.OPEN
        cb._consecutive_opens = AUTO_PAUSE_CONSECUTIVE_OPENS - 1
        assert cb.should_auto_pause is False

    @pytest.mark.sealed
    def test_m3_adv2_closed_state_never_auto_pause(self, cb):
        """ADV-2: CLOSED state → should_auto_pause=False regardless of count."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        cb._state = CircuitState.CLOSED
        cb._consecutive_opens = 100
        assert cb.should_auto_pause is False

    @pytest.mark.sealed
    def test_m3_adv3_auto_pause_threshold_is_5(self):
        """ADV-3: The constant AUTO_PAUSE_CONSECUTIVE_OPENS == 5."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import AUTO_PAUSE_CONSECUTIVE_OPENS
        assert AUTO_PAUSE_CONSECUTIVE_OPENS == 5


# ══════════════════════════════════════════════════════════════════════════════
# H-2: Fill-price fallback accuracy (_h2_exchange_fill_lookup)
# ══════════════════════════════════════════════════════════════════════════════


class TestH2FillPriceFallback:
    """H-2 FIX: Exchange lookup before aggressive_price fallback."""

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_h2_reg1_exchange_lookup_succeeds(self):
        """REG-1: When exchange returns valid fill, use it instead of aggressive_price."""
        from webui.backend.routes.mmm.mmm_executor import MMMExecutor
        executor = MMMExecutor.__new__(MMMExecutor)
        # Mock _get_order_status to return valid fill price
        executor._get_order_status = AsyncMock(return_value={
            'average_fill_price': '42.50',
            'state': 'filled',
        })
        result = await executor._h2_exchange_fill_lookup(
            'order-123', 12345, MagicMock(), 50.00,
        )
        assert result == 42.50  # Exchange price, not aggressive_price

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_h2_reg2_exchange_lookup_fails_uses_aggressive(self):
        """REG-2: When exchange lookup also fails, fall back to aggressive_price."""
        from webui.backend.routes.mmm.mmm_executor import MMMExecutor
        executor = MMMExecutor.__new__(MMMExecutor)
        executor._get_order_status = AsyncMock(return_value=None)
        result = await executor._h2_exchange_fill_lookup(
            'order-123', 12345, MagicMock(), 50.00,
        )
        assert result == 50.00  # aggressive_price fallback

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_h2_adv1_exchange_returns_nan(self):
        """ADV-1: If exchange returns NaN fill, fall back to aggressive_price."""
        from webui.backend.routes.mmm.mmm_executor import MMMExecutor
        executor = MMMExecutor.__new__(MMMExecutor)
        executor._get_order_status = AsyncMock(return_value={
            'average_fill_price': 'NaN',
        })
        result = await executor._h2_exchange_fill_lookup(
            'order-123', 12345, MagicMock(), 50.00,
        )
        assert result == 50.00

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_h2_adv2_exchange_returns_zero(self):
        """ADV-2: If exchange returns 0 fill, fall back to aggressive_price."""
        from webui.backend.routes.mmm.mmm_executor import MMMExecutor
        executor = MMMExecutor.__new__(MMMExecutor)
        executor._get_order_status = AsyncMock(return_value={
            'average_fill_price': '0',
        })
        result = await executor._h2_exchange_fill_lookup(
            'order-123', 12345, MagicMock(), 50.00,
        )
        assert result == 50.00

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_h2_adv3_exchange_exception(self):
        """ADV-3: If _get_order_status raises, fall back to aggressive_price."""
        from webui.backend.routes.mmm.mmm_executor import MMMExecutor
        executor = MMMExecutor.__new__(MMMExecutor)
        executor._get_order_status = AsyncMock(side_effect=Exception("network error"))
        result = await executor._h2_exchange_fill_lookup(
            'order-123', 12345, MagicMock(), 50.00,
        )
        assert result == 50.00
