"""
Sealed infrastructure contract tests for MaxLossMonitor (Type 2 seals)
#infra-1 through #infra-4

These tests verify the CALLING CHAIN — not the breach logic itself (that is covered
by test_sealed_check_max_loss.py in the MMM module).

Root cause March 18 2026: the breach logic was correct but these four infrastructure
contracts were broken, causing the monitor to silently do nothing:

  infra-1  Stale cache → monitor must fetch directly, not skip
  infra-2  Single API miss → must NOT remove the max-loss limit
  infra-3  Three consecutive misses → limit IS removed
  infra-4  Close retry cooldown is ≤15s (not the old 60s)

MOCK OR LIVE: MOCK
CONFIRMED WORKING ON: 2026-03-18
"""

import time
import tempfile
import os
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_monitor(test_mode=True):
    """Return a MaxLossMonitor wired to a real MaxLossManager backed by a temp-file DB.

    Note: cannot use ':memory:' — each sqlite3.connect(':memory:') opens a separate
    empty database, so tables created in _init_database() vanish on the next connection.
    """
    from webui.backend.options_strategy.max_loss_manager import (
        MaxLossMonitor, MaxLossManager,
    )
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()
    manager = MaxLossManager(db_path=tf.name)
    monitor = MaxLossMonitor(
        api_client=None,
        manager=manager,
        check_interval=5.0,
    )
    monitor.test_mode = test_mode
    return monitor, manager


def _pos(symbol, unrealized_pnl, size=-1):
    return {
        "product_symbol": symbol,
        "unrealized_pnl": unrealized_pnl,
        "size": size,
        "entry_price": 100.0,
        "mark_price": 100.0 + abs(unrealized_pnl),
    }


# ---------------------------------------------------------------------------
# infra-1  Stale cache → must fetch directly, not skip
# ---------------------------------------------------------------------------

@pytest.mark.sealed
def test_stale_cache_triggers_direct_fetch_not_skip():
    """
    When get_cached_positions returns None (cache stale / frontend not polling),
    _check_max_loss must call _fetch_positions_direct — it must NOT silently return.

    Failure means: monitor does nothing while browser tab is closed.
    """
    monitor, manager = _make_monitor(test_mode=False)
    manager.set_strike_max_loss("P-BTC-74000-190326", 40.0)

    fresh_positions = [_pos("P-BTC-74000-190326", unrealized_pnl=-50.0)]

    with patch(
        "webui.backend.routes.options.options_control.get_cached_positions",
        return_value=None,                       # simulate stale cache
    ), patch.object(
        monitor, "_fetch_positions_direct",
        return_value=fresh_positions,            # direct fetch succeeds
    ) as mock_fetch, patch.object(
        monitor, "_close_position_with_retry",
        return_value=True,
    ):
        monitor._check_max_loss()

    mock_fetch.assert_called_once(), (
        "_fetch_positions_direct was NOT called — monitor silently skipped on stale cache"
    )


@pytest.mark.sealed
def test_stale_cache_and_direct_fetch_fails_increments_skipped_stale():
    """
    When both cache AND direct fetch fail, _skipped_stale must increment and
    the function must return without crashing.
    """
    monitor, manager = _make_monitor(test_mode=False)
    manager.set_strike_max_loss("P-BTC-74000-190326", 40.0)

    with patch(
        "webui.backend.routes.options.options_control.get_cached_positions",
        return_value=None,
    ), patch.object(
        monitor, "_fetch_positions_direct",
        return_value=None,
    ):
        monitor._check_max_loss()

    assert monitor._skipped_stale == 1, (
        f"Expected _skipped_stale=1, got {monitor._skipped_stale}"
    )


@pytest.mark.sealed
def test_fresh_cache_increments_eval_count():
    """
    When fresh positions are available, _eval_count must increment so the UI
    can show meaningful 'Evaluations' instead of the misleading 'Checks' loop counter.
    """
    monitor, manager = _make_monitor(test_mode=False)
    manager.set_strike_max_loss("P-BTC-74000-190326", 40.0)

    positions = [_pos("P-BTC-74000-190326", unrealized_pnl=-5.0)]  # below threshold

    with patch(
        "webui.backend.routes.options.options_control.get_cached_positions",
        return_value=positions,
    ):
        monitor._check_max_loss()

    assert monitor._eval_count == 1, (
        f"Expected _eval_count=1 after successful check, got {monitor._eval_count}"
    )


# ---------------------------------------------------------------------------
# infra-2  Single API miss must NOT remove the max-loss limit
# ---------------------------------------------------------------------------

@pytest.mark.sealed
def test_single_miss_does_not_remove_limit():
    """
    When a symbol is absent from the positions cache for ONE cycle, its max-loss
    limit must remain in the database.

    Failure means: one partial API response permanently disables max-loss protection.
    """
    monitor, manager = _make_monitor(test_mode=False)
    manager.set_strike_max_loss("P-BTC-74000-190326", 40.0)

    # Positions list is empty — symbol absent once
    with patch(
        "webui.backend.routes.options.options_control.get_cached_positions",
        return_value=[],
    ):
        monitor._check_max_loss()

    limit = manager.get_strike_max_loss("P-BTC-74000-190326")
    assert limit is not None, (
        "Max-loss limit was removed after a single miss — protection disabled by one API hiccup"
    )
    assert limit["enabled"], "Limit was disabled after a single miss"


@pytest.mark.sealed
def test_single_miss_increments_miss_counter():
    """After one miss the internal counter must be 1 (not 0, not ≥ threshold)."""
    monitor, manager = _make_monitor(test_mode=False)
    manager.set_strike_max_loss("P-BTC-74000-190326", 40.0)

    with patch(
        "webui.backend.routes.options.options_control.get_cached_positions",
        return_value=[],
    ):
        monitor._check_max_loss()

    assert monitor._symbol_miss_count.get("P-BTC-74000-190326", 0) == 1


@pytest.mark.sealed
def test_position_present_resets_miss_counter():
    """When the position reappears, the miss counter must reset to 0."""
    monitor, manager = _make_monitor(test_mode=False)
    manager.set_strike_max_loss("P-BTC-74000-190326", 40.0)
    monitor._symbol_miss_count["P-BTC-74000-190326"] = 2   # pre-load two misses

    positions = [_pos("P-BTC-74000-190326", unrealized_pnl=-5.0)]

    with patch(
        "webui.backend.routes.options.options_control.get_cached_positions",
        return_value=positions,
    ):
        monitor._check_max_loss()

    assert "P-BTC-74000-190326" not in monitor._symbol_miss_count, (
        "Miss counter was not reset after position reappeared"
    )


# ---------------------------------------------------------------------------
# infra-3  Three consecutive misses → limit IS removed
# ---------------------------------------------------------------------------

@pytest.mark.sealed
def test_three_consecutive_misses_removes_limit():
    """
    After _CLEANUP_MISS_THRESHOLD consecutive cycles with the symbol absent,
    the limit must be removed (position is genuinely gone).
    """
    monitor, manager = _make_monitor(test_mode=False)
    manager.set_strike_max_loss("P-BTC-74000-190326", 40.0)

    with patch(
        "webui.backend.routes.options.options_control.get_cached_positions",
        return_value=[],
    ):
        for _ in range(monitor._CLEANUP_MISS_THRESHOLD):
            monitor._check_max_loss()

    limit = manager.get_strike_max_loss("P-BTC-74000-190326")
    assert limit is None, (
        f"Limit still present after {monitor._CLEANUP_MISS_THRESHOLD} consecutive misses — "
        "stale limits will accumulate forever"
    )


@pytest.mark.sealed
def test_two_misses_then_reappear_does_not_remove():
    """Two misses followed by the position returning must not remove the limit."""
    monitor, manager = _make_monitor(test_mode=False)
    manager.set_strike_max_loss("P-BTC-74000-190326", 40.0)

    with patch(
        "webui.backend.routes.options.options_control.get_cached_positions",
        return_value=[],
    ):
        for _ in range(2):
            monitor._check_max_loss()

    # Position reappears
    positions = [_pos("P-BTC-74000-190326", unrealized_pnl=-5.0)]
    with patch(
        "webui.backend.routes.options.options_control.get_cached_positions",
        return_value=positions,
    ):
        monitor._check_max_loss()

    limit = manager.get_strike_max_loss("P-BTC-74000-190326")
    assert limit is not None, "Limit was removed even though position reappeared after 2 misses"


# ---------------------------------------------------------------------------
# infra-4  Close retry cooldown is ≤15s
# ---------------------------------------------------------------------------

@pytest.mark.sealed
def test_close_attempt_cooldown_is_at_most_15s():
    """
    After a failed close, the retry cooldown must be ≤15 seconds.
    The old value was 60s — one minute of unprotected exposure after a failed close.
    """
    monitor, _ = _make_monitor()
    assert monitor._close_attempt_cooldown <= 15, (
        f"_close_attempt_cooldown is {monitor._close_attempt_cooldown}s — "
        f"must be ≤15s for safety-critical retries (was 60s before March 18 fix)"
    )


@pytest.mark.sealed
def test_breach_fires_when_cooldown_elapsed():
    """
    After a failed close, once the cooldown has elapsed a second breach check
    must attempt the close again — not skip it.
    """
    monitor, manager = _make_monitor(test_mode=False)
    manager.set_strike_max_loss("P-BTC-74000-190326", 40.0)

    symbol = "P-BTC-74000-190326"
    # Simulate: first attempt was made 20s ago (beyond 15s cooldown)
    with monitor._close_attempts_lock:
        monitor._close_attempted[symbol] = time.time() - 20

    positions = [_pos(symbol, unrealized_pnl=-50.0)]  # breach: loss $50 > limit $40

    with patch(
        "webui.backend.routes.options.options_control.get_cached_positions",
        return_value=positions,
    ), patch.object(
        monitor, "_close_position_with_retry",
        return_value=True,
    ) as mock_close:
        monitor._check_max_loss()

    mock_close.assert_called_once(), (
        "Close was not retried after cooldown elapsed — position left open"
    )


@pytest.mark.sealed
def test_breach_blocked_when_within_cooldown():
    """Within the cooldown window, a second close attempt must be suppressed."""
    monitor, manager = _make_monitor(test_mode=False)
    manager.set_strike_max_loss("P-BTC-74000-190326", 40.0)

    symbol = "P-BTC-74000-190326"
    # Simulate: first attempt was made 5s ago (within 15s cooldown)
    with monitor._close_attempts_lock:
        monitor._close_attempted[symbol] = time.time() - 5

    positions = [_pos(symbol, unrealized_pnl=-50.0)]

    with patch(
        "webui.backend.routes.options.options_control.get_cached_positions",
        return_value=positions,
    ), patch.object(
        monitor, "_close_position_with_retry",
        return_value=True,
    ) as mock_close:
        monitor._check_max_loss()

    mock_close.assert_not_called(), (
        "Close was attempted within cooldown window — this causes API spam"
    )
