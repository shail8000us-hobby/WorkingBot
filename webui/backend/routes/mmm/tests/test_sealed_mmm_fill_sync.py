"""
Sealed contract tests for FillSyncer._process_close_fill + _parse_ts_us (#81)

FillSyncer._process_close_fill is synchronous — @sealed decorator applied to
the method is not feasible (it's on a class with an async parent sync() method
that swallows exceptions). Contract tests serve as the formal specification.

FillSyncer.sync / _sync_inner are async — @sealed not applicable.
_parse_ts_us is a pure sync utility — tested as-is.

Functions covered:
  FillSyncer._process_close_fill(session, symbol, fill_price, fill_size, fill_id,
                                  order_id, commission, fill_type, expiry) -> int
  _parse_ts_us(ts_raw) -> int

File: webui/backend/routes/mmm/mmm_fill_sync.py

--- _process_close_fill deduplication contracts ---
C-FS-1: No matching close_order_id → returns 0 (not our close)
C-FS-2: Matching position, all lots filled → returns 1; _fill_confirmed=True; status='closed'
C-FS-3: entry_premium=0 → returns 0 (phantom P&L guard)
C-FS-4: _fill_confirmed=True on position → position skipped in search; returns 0 (dedup)
C-FS-5: Partial sub-fill (lots_filled < pos_lots) → returns 1; _fill_confirmed=False; lots reduced
C-FS-6: Second sub-fill reaching full total → returns 1; _fill_confirmed=True; position marked closed

--- _parse_ts_us contracts ---
C-FS-7: ISO datetime string → correct microseconds since epoch
C-FS-8: Integer already in microsecond range → returned as-is
C-FS-9: Integer in seconds range → multiplied by 1_000_000
C-FS-10: None / empty string → returns 0
C-FS-11: Malformed string → returns 0 (never raises)

--- Bug notes from audit (2026-04-17) ---
  - _process_close_fill: if pos_lots=0 AND entry_premium>0, lots_closed=fill_size
    (last branch of the ternary at line 315). Computed P&L would be based on fill_size,
    not 0. Unreachable in practice (entry_premium>0 implies a real position was created).
  - _pending_orders.py: malformed placed_at silently skips stale check — documented there.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_syncer():
    """FillSyncer with a stub monitor (never used in _process_close_fill)."""
    from webui.backend.routes.mmm.mmm_fill_sync import FillSyncer
    monitor_stub = MagicMock()
    monitor_stub.initializer = None  # _get_session_symbols gracefully handles None
    return FillSyncer(monitor_stub)


def _make_session(
    pos_lots=5,
    entry_premium=100.0,
    close_order_id='close-oid-001',
    _fill_confirmed=False,
    cumulative_lots=0.0,
):
    pos = {
        'id': 'pos-001',
        'lots': pos_lots,
        'entry_premium': entry_premium,
        'strike': 90000.0,
        'type': 'original',
        'symbol': 'C-BTC-90000-170426',
        'close_order_id': close_order_id,
        '_fill_confirmed': _fill_confirmed,
        '_cumulative_lots_filled': cumulative_lots,
    }
    return {
        'session_id': 'test-fs-001',
        'ce': {'positions': [pos], 'active_lots': pos_lots, 'total_lots': pos_lots},
        'pe': {'positions': []},
    }


def _call_process(syncer, session, fill_size=5, order_id='close-oid-001',
                  fill_price=50.0, fill_id='fill-001'):
    """Invoke _process_close_fill with all required parameters."""
    with (
        patch('webui.backend.routes.mmm.mmm_fill_sync._pnl_confirm', return_value=None),
        patch('webui.backend.routes.mmm.mmm_fill_sync._pnl_record', return_value=None),
        patch('webui.backend.routes.mmm.mmm_fill_sync.recompute_side_lots', return_value=None),
        patch('webui.backend.routes.mmm.mmm_fill_sync.log_activity', return_value=None),
    ):
        return syncer._process_close_fill(
            session=session,
            symbol='C-BTC-90000-170426',
            fill_price=fill_price,
            fill_size=fill_size,
            fill_id=fill_id,
            order_id=order_id,
            commission=0.01,
            fill_type='normal',
            expiry='170426',
        )


# =============================================================================
# _process_close_fill — deduplication and state contracts
# =============================================================================

class TestProcessCloseFill:

    @pytest.mark.sealed
    def test_c_fs_1_no_matching_order_returns_0(self):
        """Fill with no matching close_order_id in any position → returns 0 (not our close)."""
        syncer = _make_syncer()
        session = _make_session(close_order_id='close-oid-001')
        result = _call_process(syncer, session, order_id='totally-different-oid')
        assert result == 0

    @pytest.mark.sealed
    def test_c_fs_2_full_fill_marks_confirmed_and_closed(self):
        """Full fill (fill_size == pos_lots) → returns 1, position marked closed,
        _fill_confirmed=True."""
        syncer = _make_syncer()
        session = _make_session(pos_lots=5)
        result = _call_process(syncer, session, fill_size=5, order_id='close-oid-001')
        assert result == 1
        pos = session['ce']['positions'][0]
        assert pos['_fill_confirmed'] is True
        assert pos['status'] == 'closed'
        assert 'closed_at' in pos

    @pytest.mark.sealed
    def test_c_fs_3_zero_entry_premium_returns_0(self):
        """entry_premium=0 → returns 0 (phantom P&L guard — cannot compute P&L)."""
        syncer = _make_syncer()
        session = _make_session(entry_premium=0.0)
        result = _call_process(syncer, session, order_id='close-oid-001')
        assert result == 0
        # Position must NOT be modified
        pos = session['ce']['positions'][0]
        assert not pos.get('_fill_confirmed')

    @pytest.mark.sealed
    def test_c_fs_4_already_confirmed_skips_returns_0(self):
        """_fill_confirmed=True → position skipped in search; returns 0 (deduplication)."""
        syncer = _make_syncer()
        session = _make_session(_fill_confirmed=True)
        result = _call_process(syncer, session, order_id='close-oid-001')
        assert result == 0

    @pytest.mark.sealed
    def test_c_fs_5_partial_sub_fill_reduces_lots_not_confirmed(self):
        """Partial sub-fill (fill_size < pos_lots) → returns 1, _fill_confirmed=False,
        remaining lots reduced, _cumulative_lots_filled updated."""
        syncer = _make_syncer()
        session = _make_session(pos_lots=10)
        result = _call_process(syncer, session, fill_size=4, order_id='close-oid-001')
        assert result == 1
        pos = session['ce']['positions'][0]
        assert pos['_fill_confirmed'] is False  # NOT fully confirmed yet
        assert pos['lots'] == 6                 # 10 - 4 remaining
        assert pos['_cumulative_lots_filled'] == 4.0

    @pytest.mark.sealed
    def test_c_fs_6_second_sub_fill_completes_position(self):
        """Two sub-fills summing to pos_lots → second call sets _fill_confirmed=True."""
        syncer = _make_syncer()
        # First sub-fill: 4 of 10 lots
        session = _make_session(pos_lots=10)
        _call_process(syncer, session, fill_size=4, fill_id='fill-001',
                      order_id='close-oid-001')
        # Second sub-fill: remaining 6 lots — using the modified session from first call
        result = _call_process(syncer, session, fill_size=6, fill_id='fill-002',
                               order_id='close-oid-001')
        assert result == 1
        pos = session['ce']['positions'][0]
        assert pos['_fill_confirmed'] is True
        assert pos['status'] == 'closed'


# =============================================================================
# _parse_ts_us
# =============================================================================

class TestParseTs:

    @pytest.mark.sealed
    def test_c_fs_7_iso_string_returns_microseconds(self):
        """ISO datetime string → correct microseconds since epoch."""
        from webui.backend.routes.mmm.mmm_fill_sync import _parse_ts_us
        dt = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)
        iso = dt.isoformat()
        result = _parse_ts_us(iso)
        expected = int(dt.timestamp() * 1_000_000)
        assert result == expected

    @pytest.mark.sealed
    def test_c_fs_8_integer_microsecond_range_returned_as_is(self):
        """Integer already in microsecond range (> 1e13) → returned unchanged."""
        from webui.backend.routes.mmm.mmm_fill_sync import _parse_ts_us
        us = 1_745_000_000_000_000  # ~2025, in µs range
        assert _parse_ts_us(us) == us

    @pytest.mark.sealed
    def test_c_fs_9_integer_seconds_range_multiplied(self):
        """Integer in seconds range (< 1e13) → multiplied by 1_000_000."""
        from webui.backend.routes.mmm.mmm_fill_sync import _parse_ts_us
        secs = 1_745_000_000  # ~2025, in seconds
        result = _parse_ts_us(secs)
        assert result == secs * 1_000_000

    @pytest.mark.sealed
    def test_c_fs_10_none_returns_0(self):
        """None → returns 0."""
        from webui.backend.routes.mmm.mmm_fill_sync import _parse_ts_us
        assert _parse_ts_us(None) == 0
        assert _parse_ts_us('') == 0

    @pytest.mark.sealed
    def test_c_fs_11_malformed_string_returns_0_no_raise(self):
        """Malformed / garbage string → returns 0, never raises."""
        from webui.backend.routes.mmm.mmm_fill_sync import _parse_ts_us
        assert _parse_ts_us('not-a-timestamp') == 0
        assert _parse_ts_us('2026-99-99T99:99:99') == 0
