"""
Contract tests for MMM Pending Orders Guard — T3-8

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

No bugs found during audit.

Functions covered:
  register_pending(session_id, side, order_id, symbol, lots, strike, adj_type) -> None
  clear_pending(session_id, side) -> None
  get_pending(session_id, side) -> Optional[Dict]
  clear_all(session_id) -> None
  check_and_resolve_pending(session_id, side, session, rest_client, record_fill_fn) -> str

File: webui/backend/routes/mmm/mmm_pending_orders.py

--- register_pending / get_pending contracts ---
C-RP-1: register then get returns the stored entry
C-RP-2: get unknown session/side → None
C-RP-3: re-registering same side overwrites previous entry
C-RP-4: CE and PE are independent (registering CE doesn't affect PE)

--- clear_pending contracts ---
C-CP-1: clear_pending clears only the requested side
C-CP-2: clear_pending on absent session_id → no crash

--- clear_all contracts ---
C-CA-1: clear_all removes all sides for session
C-CA-2: clear_all on absent session_id → no crash

--- check_and_resolve_pending contracts ---
C-CARP-1: no pending order → returns 'none' (no exchange call)
C-CARP-2: 'pending' sentinel older than 90s → returns 'stale', clears entry
C-CARP-3: real order_id older than 90s but < 900s → NOT stale (full TTL)
C-CARP-4: order state=filled + fill_price → returns 'filled', records fill
C-CARP-5: order state=filled but no fill_price → returns 'error' (treats as open)
C-CARP-6: order state=cancelled → returns 'dead', clears entry
C-CARP-7: order state=open → returns 'open'
C-CARP-8: exchange raises exception → returns 'error' (conservative)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _uid(n: str) -> str:
    """Unique session ID prefix to avoid cross-test pollution."""
    return f'test-pending-{n}'


def _make_mock_client(order_state: str, fill_price=None, raise_exc=False):
    """Build a mock rest_client with a controlled get_order response."""
    client = MagicMock()
    if raise_exc:
        client.get_order = AsyncMock(side_effect=Exception("network error"))
    else:
        resp = {'state': order_state}
        if fill_price is not None:
            resp['average_fill_price'] = fill_price
        client.get_order = AsyncMock(return_value=resp)
    return client


def _run(coro):
    """Run an async coroutine in a new event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def cleanup_registry(request):
    """Ensure unique test session IDs are cleaned up after each test."""
    yield
    from webui.backend.routes.mmm.mmm_pending_orders import clear_all
    # Clean up any test entries
    for attr in dir(request):
        pass  # just yield — tests use unique IDs per function so no cleanup needed


# =============================================================================
# register_pending / get_pending
# =============================================================================

class TestRegisterAndGet:

    @pytest.mark.sealed
    def test_c_rp_1_register_then_get_returns_entry(self):
        from webui.backend.routes.mmm.mmm_pending_orders import register_pending, get_pending, clear_all
        sid = _uid('rp1')
        try:
            register_pending(sid, 'ce', 'oid-123', 'C-BTC-90000-210326', 5, 90000.0)
            entry = get_pending(sid, 'ce')
            assert entry is not None
            assert entry['order_id'] == 'oid-123'
            assert entry['lots'] == 5
            assert entry['strike'] == 90000.0
        finally:
            clear_all(sid)

    @pytest.mark.sealed
    def test_c_rp_2_get_unknown_returns_none(self):
        from webui.backend.routes.mmm.mmm_pending_orders import get_pending
        assert get_pending('session-does-not-exist', 'ce') is None

    @pytest.mark.sealed
    def test_c_rp_3_reregister_overwrites_previous(self):
        from webui.backend.routes.mmm.mmm_pending_orders import register_pending, get_pending, clear_all
        sid = _uid('rp3')
        try:
            register_pending(sid, 'ce', 'old-oid', 'C-BTC-90000-210326', 5, 90000.0)
            register_pending(sid, 'ce', 'new-oid', 'C-BTC-91000-210326', 3, 91000.0)
            entry = get_pending(sid, 'ce')
            assert entry['order_id'] == 'new-oid'
            assert entry['strike'] == 91000.0
        finally:
            clear_all(sid)

    @pytest.mark.sealed
    def test_c_rp_4_ce_and_pe_independent(self):
        from webui.backend.routes.mmm.mmm_pending_orders import register_pending, get_pending, clear_all
        sid = _uid('rp4')
        try:
            register_pending(sid, 'ce', 'ce-oid', 'C-BTC-90000-210326', 5, 90000.0)
            # PE not registered
            assert get_pending(sid, 'pe') is None
            assert get_pending(sid, 'ce') is not None
        finally:
            clear_all(sid)


# =============================================================================
# clear_pending
# =============================================================================

class TestClearPending:

    @pytest.mark.sealed
    def test_c_cp_1_clear_pending_clears_only_requested_side(self):
        from webui.backend.routes.mmm.mmm_pending_orders import register_pending, get_pending, clear_pending, clear_all
        sid = _uid('cp1')
        try:
            register_pending(sid, 'ce', 'ce-oid', 'C-BTC-90000-210326', 5, 90000.0)
            register_pending(sid, 'pe', 'pe-oid', 'P-BTC-88000-210326', 5, 88000.0)
            clear_pending(sid, 'ce')
            assert get_pending(sid, 'ce') is None   # cleared
            assert get_pending(sid, 'pe') is not None  # unaffected
        finally:
            clear_all(sid)

    @pytest.mark.sealed
    def test_c_cp_2_clear_pending_absent_session_no_crash(self):
        from webui.backend.routes.mmm.mmm_pending_orders import clear_pending
        clear_pending('session-not-in-registry', 'ce')


# =============================================================================
# clear_all
# =============================================================================

class TestClearAll:

    @pytest.mark.sealed
    def test_c_ca_1_clear_all_removes_all_sides(self):
        from webui.backend.routes.mmm.mmm_pending_orders import register_pending, get_pending, clear_all
        sid = _uid('ca1')
        register_pending(sid, 'ce', 'ce-oid', 'C-BTC-90000-210326', 5, 90000.0)
        register_pending(sid, 'pe', 'pe-oid', 'P-BTC-88000-210326', 5, 88000.0)
        clear_all(sid)
        assert get_pending(sid, 'ce') is None
        assert get_pending(sid, 'pe') is None

    @pytest.mark.sealed
    def test_c_ca_2_clear_all_absent_session_no_crash(self):
        from webui.backend.routes.mmm.mmm_pending_orders import clear_all
        clear_all('session-not-in-registry-ca2')


# =============================================================================
# check_and_resolve_pending
# =============================================================================

class TestCheckAndResolvePending:

    @pytest.mark.sealed
    def test_c_carp_1_no_pending_returns_none_no_exchange_call(self):
        from webui.backend.routes.mmm.mmm_pending_orders import check_and_resolve_pending, clear_all
        sid = _uid('carp1')
        client = MagicMock()
        client.get_order = AsyncMock()
        result = _run(check_and_resolve_pending(sid, 'ce', {}, client, MagicMock()))
        assert result == 'none'
        client.get_order.assert_not_called()

    @pytest.mark.sealed
    def test_c_carp_2_pending_sentinel_older_than_90s_is_stale(self):
        from webui.backend.routes.mmm.mmm_pending_orders import (
            register_pending, get_pending, check_and_resolve_pending, _registry, _lock, clear_all
        )
        sid = _uid('carp2')
        try:
            register_pending(sid, 'ce', 'pending', 'C-BTC-90000-210326', 5, 90000.0)
            # Backdate placed_at to 100 seconds ago (> 90s sentinel TTL)
            with _lock:
                old_time = (datetime.now(timezone.utc) - timedelta(seconds=100)).isoformat()
                _registry[sid]['ce']['placed_at'] = old_time

            client = MagicMock()
            client.get_order = AsyncMock()
            result = _run(check_and_resolve_pending(sid, 'ce', {}, client, MagicMock()))
            assert result == 'stale'
            assert get_pending(sid, 'ce') is None  # cleared
            client.get_order.assert_not_called()
        finally:
            clear_all(sid)

    @pytest.mark.sealed
    def test_c_carp_3_real_order_id_100s_not_stale(self):
        """Real order_id uses 900s TTL. At 100s it should proceed to exchange check."""
        from webui.backend.routes.mmm.mmm_pending_orders import (
            register_pending, check_and_resolve_pending, _registry, _lock, clear_all
        )
        sid = _uid('carp3')
        try:
            register_pending(sid, 'ce', 'real-oid-555', 'C-BTC-90000-210326', 5, 90000.0)
            # Backdate to 100s ago (> 90s but < 900s)
            with _lock:
                old_time = (datetime.now(timezone.utc) - timedelta(seconds=100)).isoformat()
                _registry[sid]['ce']['placed_at'] = old_time

            client = _make_mock_client('open')  # exchange returns open
            result = _run(check_and_resolve_pending(sid, 'ce', {}, client, MagicMock()))
            # NOT stale — should have queried exchange and returned 'open'
            assert result == 'open'
            client.get_order.assert_called_once()
        finally:
            clear_all(sid)

    @pytest.mark.sealed
    def test_c_carp_4_filled_order_records_fill_returns_filled(self):
        from webui.backend.routes.mmm.mmm_pending_orders import register_pending, get_pending, check_and_resolve_pending, clear_all
        sid = _uid('carp4')
        try:
            register_pending(sid, 'ce', 'oid-filled', 'C-BTC-90000-210326', 5, 90000.0)
            client = _make_mock_client('filled', fill_price=250.0)
            record_fill_fn = MagicMock()
            result = _run(check_and_resolve_pending(sid, 'ce', {}, client, record_fill_fn))
            assert result == 'filled'
            record_fill_fn.assert_called_once()
            assert get_pending(sid, 'ce') is None  # cleared after fill
        finally:
            clear_all(sid)

    @pytest.mark.sealed
    def test_c_carp_5_filled_no_fill_price_returns_error(self):
        """Filled but no average_fill_price → treat as open (exchange lag)."""
        from webui.backend.routes.mmm.mmm_pending_orders import register_pending, check_and_resolve_pending, clear_all
        sid = _uid('carp5')
        try:
            register_pending(sid, 'ce', 'oid-lag', 'C-BTC-90000-210326', 5, 90000.0)
            client = _make_mock_client('filled', fill_price=None)  # no fill_price key
            result = _run(check_and_resolve_pending(sid, 'ce', {}, client, MagicMock()))
            assert result == 'error'
        finally:
            clear_all(sid)

    @pytest.mark.sealed
    def test_c_carp_6_cancelled_order_returns_dead_and_clears(self):
        from webui.backend.routes.mmm.mmm_pending_orders import register_pending, get_pending, check_and_resolve_pending, clear_all
        sid = _uid('carp6')
        try:
            register_pending(sid, 'ce', 'oid-cancelled', 'C-BTC-90000-210326', 5, 90000.0)
            client = _make_mock_client('cancelled')
            result = _run(check_and_resolve_pending(sid, 'ce', {}, client, MagicMock()))
            assert result == 'dead'
            assert get_pending(sid, 'ce') is None  # cleared
        finally:
            clear_all(sid)

    @pytest.mark.sealed
    def test_c_carp_7_open_order_returns_open(self):
        from webui.backend.routes.mmm.mmm_pending_orders import register_pending, check_and_resolve_pending, clear_all
        sid = _uid('carp7')
        try:
            register_pending(sid, 'ce', 'oid-open', 'C-BTC-90000-210326', 5, 90000.0)
            client = _make_mock_client('open')
            result = _run(check_and_resolve_pending(sid, 'ce', {}, client, MagicMock()))
            assert result == 'open'
        finally:
            clear_all(sid)

    @pytest.mark.sealed
    def test_c_carp_8_exchange_exception_returns_error(self):
        from webui.backend.routes.mmm.mmm_pending_orders import register_pending, check_and_resolve_pending, clear_all
        sid = _uid('carp8')
        try:
            register_pending(sid, 'ce', 'oid-exc', 'C-BTC-90000-210326', 5, 90000.0)
            client = _make_mock_client(None, raise_exc=True)
            result = _run(check_and_resolve_pending(sid, 'ce', {}, client, MagicMock()))
            assert result == 'error'  # conservative: treat as open
        finally:
            clear_all(sid)
