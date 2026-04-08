"""
MMMX Phase 7 Unit Tests — Premium Listener + Tier-0 CBs + Heartbeat Watchdog + Hedger

Covers:
  - CB_PREMIUM_JUMP:    tick with 51% premium jump → _force_check=True
  - CB_DELTA_BLOWOUT:   portfolio_delta > 0.70 → _force_check=True
  - CB_IV_FLASH_SPIKE:  IV > 80% → _force_check=True
  - CB_NEAR_ITM:        position delta >= 0.72 → emergency_execute 50% reduce + _force_check=True
  - Stale WS (no ticks 5+ min) → force_heartbeat + Telegram WARNING
  - Stale WS AND stale monitor → Telegram CRITICAL
  - Hedge scheduling: Tr5 deployment → schedule_post_deploy appends PENDING entry
  - Tr1–Tr4 deployments do NOT produce hedges
  - hedger.tick: PENDING entry with elapsed time → smart_execute called, session['hedges'] populated
  - hedger.tick: entry not yet due → no execution
  - hedge P&L: update_hedge_pnl updates unrealised P&L from live_quotes
  - detect_displacement: repositioned parent → hedge marked ORPHANED, not CLOSED
  - Hard stop scenario: hedges remain ORPHANED (not closed) after hard stop
  - _force_check + signal_force_check: monitor._force_wake_event is set
  - All 320 prior tests must still pass (this file adds to the suite; no imports changed)

Exit criteria (MMMX_IMPLEMENTATION_PLAN.md Phase 7):
  - Each of the 4 Tier-0 CBs fires on the correct synthetic tick.
  - CB_NEAR_ITM calls emergency_execute (50% of leg lots) AND sets _force_check.
  - Stale-WS watchdog fires WARNING; combined stale fires CRITICAL.
  - Tr5 schedule entry created; Tr4 does not create one.
  - hedger.tick executes PENDING entries after delay; session['hedges'] populated.
  - detect_displacement: hedge.status == ORPHANED; displaced_from_parent_at set.
  - MMMXMonitor.signal_force_check() sets _force_wake_event.
"""

import asyncio
import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..')
)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_session(**overrides):
    from webui.backend.routes.mmmx.mmmx_state import create_session
    s = create_session()
    s['session_id'] = 'test-p7-session-0001'
    s['expiry_datetime'] = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    s['expiry_ddmmyy'] = '280626'
    s['status'] = 'RUNNING'
    s['live_quotes'] = {}
    s['_listener_force_count'] = 0
    s['_hedge_schedule'] = []
    for k, v in overrides.items():
        s[k] = v
    return s


def _make_active_tranche(
    tranche_id=1,
    ce_symbol='C-BTC-80000-280626',
    pe_symbol='P-BTC-60000-280626',
    ce_lots=10,
    pe_lots=10,
    ce_entry_premium=200.0,
    pe_entry_premium=150.0,
    ce_delta=0.25,
    pe_delta=-0.20,
    ce_current_delta=None,
    pe_current_delta=None,
):
    return {
        'tranche_id': tranche_id,
        'status': 'ACTIVE',
        'deployed_at': datetime.now(timezone.utc).isoformat(),
        'entry_spot': 70000.0,
        'entry_dvol': 60.0,
        'entry_iv_rank': 55.0,
        'premium_collected': (ce_entry_premium + pe_entry_premium) * ce_lots * 0.001,
        'ce': {
            'symbol': ce_symbol,
            'strike': 80000.0,
            'lots': ce_lots,
            'entry_premium': ce_entry_premium,
            'entry_delta': ce_delta,
            'current_premium': ce_entry_premium,
            'current_delta': ce_current_delta,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            'fees_paid': 0.0,
            'status': 'ACTIVE',
            '_being_closed': False,
        },
        'pe': {
            'symbol': pe_symbol,
            'strike': 60000.0,
            'lots': pe_lots,
            'entry_premium': pe_entry_premium,
            'entry_delta': pe_delta,
            'current_premium': pe_entry_premium,
            'current_delta': pe_current_delta,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            'fees_paid': 0.0,
            'status': 'ACTIVE',
            '_being_closed': False,
        },
        'close_reason': None,
        'closed_at': None,
        'type': 'deployment',
        'parent_tranche_id': None,
    }


def _make_executor(ce_ok=True, pe_ok=True, avg_price=100.0):
    class _MockResult:
        def __init__(self, success, reason='ok'):
            self.success = success
            self.reason = reason
            self.avg_price = avg_price if success else None
            self.fees_paid = 0.5 if success else 0.0

    executor = MagicMock()

    async def _smart_execute(symbol, side, size, **kwargs):
        if 'CE' in kwargs.get('action', '') or symbol.startswith('C-'):
            return _MockResult(ce_ok)
        if 'PE' in kwargs.get('action', '') or symbol.startswith('P-'):
            return _MockResult(pe_ok)
        return _MockResult(True)

    async def _emergency_execute(symbol, side, size, **kwargs):
        return _MockResult(True)

    executor.smart_execute = _smart_execute
    executor.emergency_execute = AsyncMock(side_effect=_emergency_execute)
    return executor


def _make_audit():
    audit = MagicMock()
    audit.enqueue_event = MagicMock()
    return audit


# ══════════════════════════════════════════════════════════════════════════════
# 1. CB_PREMIUM_JUMP
# ══════════════════════════════════════════════════════════════════════════════

class TestCBPremiumJump:

    def _make_listener(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        return PremiumListener('test-p7-session-0001', 1)

    def test_cb_fires_on_51pct_jump(self):
        listener = self._make_listener()
        session = _make_session()
        tranche = _make_active_tranche(ce_entry_premium=200.0)
        session['tranches'] = [tranche]

        # Tick: CE premium jumped from 200 → 305 (52.5% jump)
        tick = {
            'symbol': 'C-BTC-80000-280626',
            'mark_price': 305.0,
        }
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_PREMIUM_JUMP' in fired
        assert session['_force_check'] is True
        assert session['_listener_force_count'] == 1

    def test_cb_does_not_fire_on_49pct_jump(self):
        listener = self._make_listener()
        session = _make_session()
        tranche = _make_active_tranche(ce_entry_premium=200.0)
        session['tranches'] = [tranche]

        # 49% jump — below threshold
        tick = {
            'symbol': 'C-BTC-80000-280626',
            'mark_price': 298.0,
        }
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_PREMIUM_JUMP' not in fired
        assert session['_force_check'] is False

    def test_cb_deduped_in_single_call(self):
        """Same CB should appear only once in the returned list even if two legs match."""
        listener = self._make_listener()
        session = _make_session()
        # Two tranches with same CE symbol
        t1 = _make_active_tranche(tranche_id=1, ce_entry_premium=100.0)
        t2 = _make_active_tranche(tranche_id=2, ce_entry_premium=100.0)
        session['tranches'] = [t1, t2]

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 200.0}  # 100% jump
        fired = _run(listener.evaluate_cbs(tick, session))

        assert fired.count('CB_PREMIUM_JUMP') == 1

    def test_inactive_tranche_ignored(self):
        listener = self._make_listener()
        session = _make_session()
        tranche = _make_active_tranche(ce_entry_premium=100.0)
        tranche['status'] = 'CLOSED'
        session['tranches'] = [tranche]

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 250.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_PREMIUM_JUMP' not in fired
        assert session['_force_check'] is False


# ══════════════════════════════════════════════════════════════════════════════
# 2. CB_DELTA_BLOWOUT
# ══════════════════════════════════════════════════════════════════════════════

class TestCBDeltaBlowout:

    def _make_listener(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        return PremiumListener('test-p7-session-0001', 1)

    def test_cb_fires_above_emergency_delta(self):
        listener = self._make_listener()
        session = _make_session(portfolio_delta=0.71)
        session['params']['emergency_delta'] = 0.70

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 100.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_DELTA_BLOWOUT' in fired
        assert session['_force_check'] is True

    def test_cb_fires_negative_delta(self):
        listener = self._make_listener()
        session = _make_session(portfolio_delta=-0.75)
        session['params']['emergency_delta'] = 0.70

        tick = {'symbol': 'X', 'mark_price': 10.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_DELTA_BLOWOUT' in fired

    def test_cb_does_not_fire_below_threshold(self):
        listener = self._make_listener()
        session = _make_session(portfolio_delta=0.65)
        session['params']['emergency_delta'] = 0.70

        tick = {'symbol': 'X', 'mark_price': 10.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_DELTA_BLOWOUT' not in fired
        assert session['_force_check'] is False

    def test_default_emergency_delta_used_when_param_missing(self):
        listener = self._make_listener()
        session = _make_session(portfolio_delta=0.71)
        # No emergency_delta in params — should default to 0.70
        session['params'].pop('emergency_delta', None)

        tick = {'symbol': 'X', 'mark_price': 10.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_DELTA_BLOWOUT' in fired


# ══════════════════════════════════════════════════════════════════════════════
# 3. CB_IV_FLASH_SPIKE
# ══════════════════════════════════════════════════════════════════════════════

class TestCBIVFlashSpike:

    def _make_listener(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        return PremiumListener('test-p7-session-0001', 1)

    def test_cb_fires_above_iv_catastrophe(self):
        listener = self._make_listener()
        session = _make_session()
        session['params']['iv_catastrophe_pct'] = 80.0

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 100.0, 'iv': 85.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_IV_FLASH_SPIKE' in fired
        assert session['_force_check'] is True

    def test_cb_uses_iv_rank_field(self):
        listener = self._make_listener()
        session = _make_session()
        session['params']['iv_catastrophe_pct'] = 80.0

        tick = {'symbol': 'X', 'mark_price': 10.0, 'iv_rank': 91.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_IV_FLASH_SPIKE' in fired

    def test_cb_does_not_fire_below_threshold(self):
        listener = self._make_listener()
        session = _make_session()
        session['params']['iv_catastrophe_pct'] = 80.0

        tick = {'symbol': 'X', 'mark_price': 10.0, 'iv': 79.9}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_IV_FLASH_SPIKE' not in fired

    def test_no_iv_in_tick_does_not_fire(self):
        listener = self._make_listener()
        session = _make_session()

        tick = {'symbol': 'X', 'mark_price': 10.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_IV_FLASH_SPIKE' not in fired


# ══════════════════════════════════════════════════════════════════════════════
# 4. CB_NEAR_ITM
# ══════════════════════════════════════════════════════════════════════════════

class TestCBNearITM:

    def _make_listener(self, executor=None):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        listener = PremiumListener('test-p7-session-0001', 1, executor=executor)
        return listener

    def test_cb_fires_on_ce_delta_above_threshold(self):
        executor = _make_executor()
        listener = self._make_listener(executor=executor)
        session = _make_session()
        tranche = _make_active_tranche(ce_lots=10, ce_current_delta=0.73)
        session['tranches'] = [tranche]

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 300.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_NEAR_ITM' in fired
        assert session['_force_check'] is True
        assert session['_listener_force_count'] >= 1

    def test_cb_fires_on_pe_delta_above_threshold(self):
        executor = _make_executor()
        listener = self._make_listener(executor=executor)
        session = _make_session()
        tranche = _make_active_tranche(pe_lots=10, pe_current_delta=-0.74)
        session['tranches'] = [tranche]

        tick = {'symbol': 'P-BTC-60000-280626', 'mark_price': 250.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_NEAR_ITM' in fired
        assert session['_force_check'] is True

    def test_cb_calls_emergency_execute_50pct_reduce(self):
        mock_executor = MagicMock()
        mock_result = MagicMock(success=True, avg_price=300.0, fees_paid=0.5)
        mock_executor.emergency_execute = AsyncMock(return_value=mock_result)

        listener = self._make_listener(executor=mock_executor)
        session = _make_session()
        # CE with 10 lots and delta >= 0.72
        tranche = _make_active_tranche(ce_lots=10, ce_current_delta=0.75)
        session['tranches'] = [tranche]

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 400.0}
        _run(listener.evaluate_cbs(tick, session))

        mock_executor.emergency_execute.assert_called_once()
        call_kwargs = mock_executor.emergency_execute.call_args
        # 50% of 10 lots = 5 lots
        assert call_kwargs.kwargs.get('size') == 5 or call_kwargs.args[2] == 5

    def test_cb_reduces_to_minimum_1_lot(self):
        mock_executor = MagicMock()
        mock_result = MagicMock(success=True, avg_price=100.0, fees_paid=0.0)
        mock_executor.emergency_execute = AsyncMock(return_value=mock_result)

        listener = self._make_listener(executor=mock_executor)
        session = _make_session()
        # CE with only 1 lot → 50% = 0.5 → max(1, 0) = 1
        tranche = _make_active_tranche(ce_lots=1, ce_current_delta=0.80)
        session['tranches'] = [tranche]

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 400.0}
        _run(listener.evaluate_cbs(tick, session))

        mock_executor.emergency_execute.assert_called_once()
        call_kwargs = mock_executor.emergency_execute.call_args
        reduce_lots = call_kwargs.kwargs.get('size') or call_kwargs.args[2]
        assert reduce_lots >= 1

    def test_cb_no_executor_still_sets_force_check(self):
        listener = self._make_listener(executor=None)
        session = _make_session()
        tranche = _make_active_tranche(ce_lots=10, ce_current_delta=0.73)
        session['tranches'] = [tranche]

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 300.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_NEAR_ITM' in fired
        assert session['_force_check'] is True

    def test_cb_does_not_fire_below_threshold(self):
        executor = _make_executor()
        listener = self._make_listener(executor=executor)
        session = _make_session()
        tranche = _make_active_tranche(ce_current_delta=0.71)
        session['tranches'] = [tranche]

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 200.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_NEAR_ITM' not in fired

    def test_cb_fires_at_exact_threshold(self):
        executor = _make_executor()
        listener = self._make_listener(executor=executor)
        session = _make_session()
        tranche = _make_active_tranche(ce_current_delta=0.72)
        session['tranches'] = [tranche]

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 200.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_NEAR_ITM' in fired

    def test_closed_tranche_not_evaluated(self):
        executor = _make_executor()
        listener = self._make_listener(executor=executor)
        session = _make_session()
        tranche = _make_active_tranche(ce_current_delta=0.80)
        tranche['status'] = 'CLOSED'
        session['tranches'] = [tranche]

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 400.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_NEAR_ITM' not in fired


# ══════════════════════════════════════════════════════════════════════════════
# 5. on_tick updates live_quotes
# ══════════════════════════════════════════════════════════════════════════════

class TestOnTick:

    def test_on_tick_updates_live_quotes(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        listener = PremiumListener('test-p7-session-0001', 1)
        session = _make_session()

        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 150.0}
        _run(listener.on_tick(tick, session))

        assert 'C-BTC-80000-280626' in session['live_quotes']
        assert session['live_quotes']['C-BTC-80000-280626']['mark_price'] == 150.0

    def test_on_tick_sets_last_tick_at(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        listener = PremiumListener('test-p7-session-0001', 1)
        session = _make_session()

        assert listener._last_tick_at is None
        tick = {'symbol': 'X', 'mark_price': 100.0}
        _run(listener.on_tick(tick, session))

        assert listener._last_tick_at is not None


# ══════════════════════════════════════════════════════════════════════════════
# 6. Stale WS watchdog
# ══════════════════════════════════════════════════════════════════════════════

class TestStaleWSWatchdog:

    def _make_listener(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        return PremiumListener('test-p7-session-0001', 1)

    def test_no_check_if_never_received_tick(self):
        listener = self._make_listener()
        session = _make_session()
        # Should not raise or fire force_heartbeat
        listener.check_stale_ws(session)
        assert session['_force_check'] is False

    def test_no_check_if_recent_tick(self):
        listener = self._make_listener()
        session = _make_session()
        # Tick received 30 seconds ago — not stale
        listener._last_tick_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        listener.check_stale_ws(session)
        assert session['_force_check'] is False

    def test_ws_stale_fires_force_heartbeat(self):
        listener = self._make_listener()
        session = _make_session()
        # Tick received 6 minutes ago — stale
        listener._last_tick_at = datetime.now(timezone.utc) - timedelta(minutes=6)

        with patch('webui.backend.routes.mmmx.mmmx_telegram.send_alert') as mock_tg:
            listener.check_stale_ws(session)

        assert session['_force_check'] is True
        assert session['_listener_force_count'] >= 1
        mock_tg.assert_called_once()
        # Should be a WARNING (not CRITICAL)
        call_msg = mock_tg.call_args[0][0]
        assert 'WARNING' in call_msg or '⚠️' in call_msg

    def test_ws_and_monitor_stale_sends_critical(self):
        listener = self._make_listener()
        session = _make_session()
        # Both WS and monitor are stale
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        listener._last_tick_at = stale_time
        session['_last_beat_at'] = stale_time.isoformat()

        with patch('webui.backend.routes.mmmx.mmmx_telegram.send_alert') as mock_tg:
            listener.check_stale_ws(session)

        mock_tg.assert_called_once()
        call_msg = mock_tg.call_args[0][0]
        assert 'CRITICAL' in call_msg or '🚨' in call_msg

    def test_ws_stale_but_monitor_fresh_sends_warning_not_critical(self):
        listener = self._make_listener()
        session = _make_session()
        listener._last_tick_at = datetime.now(timezone.utc) - timedelta(minutes=6)
        # Monitor had a recent beat
        session['_last_beat_at'] = datetime.now(timezone.utc).isoformat()

        with patch('webui.backend.routes.mmmx.mmmx_telegram.send_alert') as mock_tg:
            listener.check_stale_ws(session)

        call_msg = mock_tg.call_args[0][0]
        assert 'CRITICAL' not in call_msg
        assert 'WARNING' in call_msg or '⚠️' in call_msg


# ══════════════════════════════════════════════════════════════════════════════
# 7. force_heartbeat and subscribe
# ══════════════════════════════════════════════════════════════════════════════

class TestForceHeartbeat:

    def test_force_heartbeat_sets_force_check(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        listener = PremiumListener('test-p7-session-0001', 1)
        session = _make_session()

        listener.force_heartbeat(session, 'test_reason')

        assert session['_force_check'] is True
        assert session['_listener_force_count'] == 1

    def test_force_heartbeat_increments_counter(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        listener = PremiumListener('test-p7-session-0001', 1)
        session = _make_session()

        listener.force_heartbeat(session, 'r1')
        listener.force_heartbeat(session, 'r2')
        listener.force_heartbeat(session, 'r3')

        assert session['_listener_force_count'] == 3

    def test_subscribe_initialises_session_fields(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        listener = PremiumListener('test-p7-session-0001', 1)
        session = _make_session()
        del session['live_quotes']
        del session['_listener_force_count']

        tranche = _make_active_tranche()
        session['tranches'] = [tranche]
        listener.subscribe(session)

        assert 'live_quotes' in session
        assert '_listener_force_count' in session

    def test_subscribe_collects_active_symbols(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        listener = PremiumListener('test-p7-session-0001', 1)
        session = _make_session()
        t1 = _make_active_tranche(tranche_id=1, ce_symbol='C-A', pe_symbol='P-A')
        t2 = _make_active_tranche(tranche_id=2, ce_symbol='C-B', pe_symbol='P-B')
        session['tranches'] = [t1, t2]

        listener.subscribe(session)

        assert set(listener._subscribed_symbols) == {'C-A', 'P-A', 'C-B', 'P-B'}

    def test_subscribe_excludes_inactive_tranches(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        listener = PremiumListener('test-p7-session-0001', 1)
        session = _make_session()
        t1 = _make_active_tranche(tranche_id=1, ce_symbol='C-A', pe_symbol='P-A')
        t2 = _make_active_tranche(tranche_id=2, ce_symbol='C-B', pe_symbol='P-B')
        t2['status'] = 'CLOSED'
        session['tranches'] = [t1, t2]

        listener.subscribe(session)

        assert 'C-B' not in listener._subscribed_symbols
        assert 'P-B' not in listener._subscribed_symbols


# ══════════════════════════════════════════════════════════════════════════════
# 8. MMMXMonitor signal_force_check
# ══════════════════════════════════════════════════════════════════════════════

class TestSignalForceCheck:

    def test_signal_force_check_sets_event(self):
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor
        monitor = MMMXMonitor('test-p7-signal-0001', 1)
        monitor._force_wake_event.clear()

        monitor.signal_force_check()

        assert monitor._force_wake_event.is_set()

    def test_stop_also_sets_force_wake_event(self):
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor
        monitor = MMMXMonitor('test-p7-signal-0002', 1)
        monitor._force_wake_event.clear()

        monitor.stop(reason='test')

        assert monitor._force_wake_event.is_set()


# ══════════════════════════════════════════════════════════════════════════════
# 9. Hedge scheduling
# ══════════════════════════════════════════════════════════════════════════════

class TestHedgeScheduling:

    def test_tr5_creates_schedule_entry(self):
        from webui.backend.routes.mmmx.mmmx_hedger import schedule_post_deploy
        session = _make_session(tranches_deployed=5)
        t5 = _make_active_tranche(tranche_id=5, ce_lots=10)
        session['tranches'] = [t5]
        deployed_at = datetime.now(timezone.utc).isoformat()

        entry = schedule_post_deploy(session, 5, deployed_at)

        assert entry is not None
        assert entry['tranche_id'] == 5
        assert entry['status'] == 'PENDING'
        assert entry['lots'] == 10
        assert len(session['_hedge_schedule']) == 1

    def test_tr4_does_not_create_schedule_entry(self):
        from webui.backend.routes.mmmx.mmmx_hedger import schedule_post_deploy
        session = _make_session(tranches_deployed=4)
        deployed_at = datetime.now(timezone.utc).isoformat()

        entry = schedule_post_deploy(session, 4, deployed_at)

        assert entry is None
        assert session.get('_hedge_schedule', []) == []

    def test_tr1_to_tr4_all_skip(self):
        from webui.backend.routes.mmmx.mmmx_hedger import schedule_post_deploy
        for td in range(1, 5):
            session = _make_session(tranches_deployed=td)
            deployed_at = datetime.now(timezone.utc).isoformat()
            entry = schedule_post_deploy(session, td, deployed_at)
            assert entry is None, f"Tr{td} should not create a hedge schedule"

    def test_tr6_also_creates_entry(self):
        from webui.backend.routes.mmmx.mmmx_hedger import schedule_post_deploy
        session = _make_session(tranches_deployed=6)
        t6 = _make_active_tranche(tranche_id=6, ce_lots=10)
        session['tranches'] = [t6]
        deployed_at = datetime.now(timezone.utc).isoformat()

        entry = schedule_post_deploy(session, 6, deployed_at)

        assert entry is not None

    def test_execute_after_uses_delay_minutes(self):
        from webui.backend.routes.mmmx.mmmx_hedger import schedule_post_deploy
        session = _make_session(tranches_deployed=5)
        t5 = _make_active_tranche(tranche_id=5, ce_lots=10)
        session['tranches'] = [t5]
        session['params']['hedge_execution_delay_minutes'] = 15

        deployed_at = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc).isoformat()
        entry = schedule_post_deploy(session, 5, deployed_at)

        expected_after = datetime(2026, 4, 6, 12, 15, 0, tzinfo=timezone.utc).isoformat()
        assert entry['execute_after'] == expected_after

    def test_hedging_disabled_skips_schedule(self):
        from webui.backend.routes.mmmx.mmmx_hedger import schedule_post_deploy
        session = _make_session(tranches_deployed=5)
        session['params']['hedging_enabled'] = False
        deployed_at = datetime.now(timezone.utc).isoformat()

        entry = schedule_post_deploy(session, 5, deployed_at)

        assert entry is None

    def test_multiple_deploys_multiple_entries(self):
        from webui.backend.routes.mmmx.mmmx_hedger import schedule_post_deploy
        session = _make_session(tranches_deployed=5)
        t5 = _make_active_tranche(tranche_id=5, ce_lots=10)
        t6 = _make_active_tranche(tranche_id=6, ce_lots=10)
        session['tranches'] = [t5, t6]
        dt = datetime.now(timezone.utc).isoformat()

        schedule_post_deploy(session, 5, dt)
        session['tranches_deployed'] = 6
        schedule_post_deploy(session, 6, dt)

        assert len(session['_hedge_schedule']) == 2


# ══════════════════════════════════════════════════════════════════════════════
# 10. Hedger tick
# ══════════════════════════════════════════════════════════════════════════════

class TestHedgerTick:

    def test_tick_executes_pending_due_entry(self):
        from webui.backend.routes.mmmx.mmmx_hedger import tick
        executor = _make_executor()
        audit = _make_audit()

        session = _make_session(tranches_deployed=5)
        t5 = _make_active_tranche(tranche_id=5, ce_lots=10, pe_lots=10)
        session['tranches'] = [t5]
        # Entry is due (in the past)
        past = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        session['_hedge_schedule'] = [{
            'tranche_id': 5,
            'execute_after': past,
            'lots': 10,
            'status': 'PENDING',
        }]

        executed = _run(tick(session, executor, audit))

        assert len(executed) == 1
        assert executed[0]['parent_tranche_id'] == 5
        assert len(session['hedges']) == 1
        assert session['hedges'][0]['status'] == 'ACTIVE'
        assert session['_hedge_schedule'][0]['status'] == 'EXECUTED'
        assert session['active_hedges'] == 1

    def test_tick_skips_entry_not_yet_due(self):
        from webui.backend.routes.mmmx.mmmx_hedger import tick
        executor = _make_executor()
        audit = _make_audit()

        session = _make_session(tranches_deployed=5)
        t5 = _make_active_tranche(tranche_id=5)
        session['tranches'] = [t5]
        future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        session['_hedge_schedule'] = [{
            'tranche_id': 5,
            'execute_after': future,
            'lots': 10,
            'status': 'PENDING',
        }]

        executed = _run(tick(session, executor, audit))

        assert executed == []
        assert session.get('hedges', []) == []
        assert session['_hedge_schedule'][0]['status'] == 'PENDING'

    def test_tick_skips_already_executed_entry(self):
        from webui.backend.routes.mmmx.mmmx_hedger import tick
        executor = _make_executor()
        audit = _make_audit()

        session = _make_session(tranches_deployed=5)
        t5 = _make_active_tranche(tranche_id=5)
        session['tranches'] = [t5]
        past = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        session['_hedge_schedule'] = [{
            'tranche_id': 5,
            'execute_after': past,
            'lots': 10,
            'status': 'EXECUTED',    # already done
        }]

        executed = _run(tick(session, executor, audit))

        assert executed == []

    def test_tick_marks_failed_on_executor_failure(self):
        from webui.backend.routes.mmmx.mmmx_hedger import tick
        executor = _make_executor(ce_ok=False)  # CE buy fails
        audit = _make_audit()

        session = _make_session(tranches_deployed=5)
        t5 = _make_active_tranche(tranche_id=5)
        session['tranches'] = [t5]
        past = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        session['_hedge_schedule'] = [{
            'tranche_id': 5,
            'execute_after': past,
            'lots': 10,
            'status': 'PENDING',
        }]

        executed = _run(tick(session, executor, audit))

        assert executed == []
        assert session.get('hedges', []) == []
        assert session['_hedge_schedule'][0]['status'] == 'FAILED'

    def test_tick_no_schedule_returns_empty(self):
        from webui.backend.routes.mmmx.mmmx_hedger import tick
        executor = _make_executor()
        audit = _make_audit()
        session = _make_session(tranches_deployed=5)
        session['_hedge_schedule'] = []

        executed = _run(tick(session, executor, audit))

        assert executed == []

    def test_tick_increments_total_hedge_cost(self):
        from webui.backend.routes.mmmx.mmmx_hedger import tick
        executor = _make_executor(avg_price=100.0)
        audit = _make_audit()

        session = _make_session(tranches_deployed=5)
        t5 = _make_active_tranche(tranche_id=5, ce_lots=10)
        session['tranches'] = [t5]
        past = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        session['_hedge_schedule'] = [{
            'tranche_id': 5, 'execute_after': past, 'lots': 10, 'status': 'PENDING'
        }]

        _run(tick(session, executor, audit))

        # hedge_premium_paid = (ce_premium + pe_premium) * lots * LOT_SIZE_BTC
        # = (100 + 100) * 10 * 0.001 = 2.0
        assert session['total_hedge_cost_paid'] == pytest.approx(2.0)

    def test_tick_populates_hedges_by_parent(self):
        from webui.backend.routes.mmmx.mmmx_hedger import tick
        executor = _make_executor()
        audit = _make_audit()

        session = _make_session(tranches_deployed=5)
        t5 = _make_active_tranche(tranche_id=5)
        session['tranches'] = [t5]
        past = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        session['_hedge_schedule'] = [{
            'tranche_id': 5, 'execute_after': past, 'lots': 10, 'status': 'PENDING'
        }]

        _run(tick(session, executor, audit))

        assert '5' in session['hedges_by_parent']

    def test_tick_skips_when_parent_tranche_not_found(self):
        from webui.backend.routes.mmmx.mmmx_hedger import tick
        executor = _make_executor()
        audit = _make_audit()

        session = _make_session(tranches_deployed=5)
        session['tranches'] = []  # no tranches
        past = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        session['_hedge_schedule'] = [{
            'tranche_id': 99, 'execute_after': past, 'lots': 10, 'status': 'PENDING'
        }]

        executed = _run(tick(session, executor, audit))

        assert executed == []
        assert session['_hedge_schedule'][0]['status'] == 'SKIPPED'


# ══════════════════════════════════════════════════════════════════════════════
# 11. Hedge P&L update
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdateHedgePnl:

    def _make_active_hedge(self, tranche_id=1, ce_lots=10, pe_lots=10,
                            ce_premium=100.0, pe_premium=80.0,
                            ce_symbol='C-BTC-80000-280626',
                            pe_symbol='P-BTC-60000-280626'):
        from webui.backend.routes.mmmx.mmmx_state import make_hedge
        return make_hedge(
            parent_tranche_id=tranche_id,
            entry_spot=70000.0,
            hedge_distance_pct=20.0,
            ce_symbol=ce_symbol,
            ce_strike=80000.0,
            ce_lots=ce_lots,
            ce_premium=ce_premium,
            ce_delta=0.20,
            pe_symbol=pe_symbol,
            pe_strike=60000.0,
            pe_lots=pe_lots,
            pe_premium=pe_premium,
            pe_delta=-0.20,
            ce_spread_width=0.0,
            pe_spread_width=0.0,
        )

    def test_update_pnl_with_live_quotes(self):
        from webui.backend.routes.mmmx.mmmx_hedger import update_hedge_pnl

        session = _make_session()
        hedge = self._make_active_hedge(ce_lots=10, ce_premium=100.0)
        session['hedges'] = [hedge]

        live_quotes = {
            'C-BTC-80000-280626': {'mark_price': 120.0},
            'P-BTC-60000-280626': {'mark_price': 90.0},
        }
        update_hedge_pnl(session, live_quotes)

        # LONG CE: (120 - 100) * 10 * 0.001 = 0.2
        assert session['hedges'][0]['ce']['unrealized_pnl'] == pytest.approx(0.2)
        # LONG PE: (90 - 80) * 10 * 0.001 = 0.1
        assert session['hedges'][0]['pe']['unrealized_pnl'] == pytest.approx(0.1)

    def test_update_pnl_negative(self):
        from webui.backend.routes.mmmx.mmmx_hedger import update_hedge_pnl

        session = _make_session()
        hedge = self._make_active_hedge(ce_lots=10, ce_premium=100.0)
        session['hedges'] = [hedge]

        live_quotes = {
            'C-BTC-80000-280626': {'mark_price': 80.0},  # price dropped
            'P-BTC-60000-280626': {'mark_price': 70.0},
        }
        update_hedge_pnl(session, live_quotes)

        # (80 - 100) * 10 * 0.001 = -0.2
        assert session['hedges'][0]['ce']['unrealized_pnl'] == pytest.approx(-0.2)

    def test_orphaned_hedge_skipped(self):
        from webui.backend.routes.mmmx.mmmx_hedger import update_hedge_pnl
        from webui.backend.routes.mmmx.mmmx_constants import HedgeStatus

        session = _make_session()
        hedge = self._make_active_hedge(ce_lots=10, ce_premium=100.0)
        hedge['status'] = HedgeStatus.ORPHANED
        session['hedges'] = [hedge]

        live_quotes = {'C-BTC-80000-280626': {'mark_price': 200.0}}
        update_hedge_pnl(session, live_quotes)

        # ORPHANED hedge should not be updated
        assert session['hedges'][0]['ce']['unrealized_pnl'] == 0.0

    def test_uses_bid_ask_mid_fallback(self):
        from webui.backend.routes.mmmx.mmmx_hedger import update_hedge_pnl

        session = _make_session()
        hedge = self._make_active_hedge(ce_lots=10, ce_premium=100.0)
        session['hedges'] = [hedge]

        live_quotes = {
            'C-BTC-80000-280626': {'bid': 110.0, 'ask': 130.0},  # no mark_price
            'P-BTC-60000-280626': {'mark_price': 85.0},
        }
        update_hedge_pnl(session, live_quotes)

        # mid = (110 + 130) / 2 = 120; pnl = (120 - 100) * 10 * 0.001 = 0.2
        assert session['hedges'][0]['ce']['unrealized_pnl'] == pytest.approx(0.2)

    def test_missing_quote_leaves_pnl_unchanged(self):
        from webui.backend.routes.mmmx.mmmx_hedger import update_hedge_pnl

        session = _make_session()
        hedge = self._make_active_hedge(ce_lots=10, ce_premium=100.0)
        hedge['ce']['unrealized_pnl'] = 0.5  # existing value
        session['hedges'] = [hedge]

        update_hedge_pnl(session, {})  # no quotes available

        assert session['hedges'][0]['ce']['unrealized_pnl'] == 0.5  # unchanged


# ══════════════════════════════════════════════════════════════════════════════
# 12. detect_displacement
# ══════════════════════════════════════════════════════════════════════════════

class TestDetectDisplacement:

    def _make_active_hedge(self, tranche_id=1):
        from webui.backend.routes.mmmx.mmmx_state import make_hedge
        return make_hedge(
            parent_tranche_id=tranche_id,
            entry_spot=70000.0,
            hedge_distance_pct=20.0,
            ce_symbol='C-BTC-80000-280626',
            ce_strike=80000.0,
            ce_lots=10,
            ce_premium=100.0,
            ce_delta=0.20,
            pe_symbol='P-BTC-60000-280626',
            pe_strike=60000.0,
            pe_lots=10,
            pe_premium=80.0,
            pe_delta=-0.20,
            ce_spread_width=0.0,
            pe_spread_width=0.0,
        )

    def test_hedge_marked_orphaned_on_parent_reposition(self):
        from webui.backend.routes.mmmx.mmmx_hedger import detect_displacement
        from webui.backend.routes.mmmx.mmmx_constants import HedgeStatus

        session = _make_session()
        hedge = self._make_active_hedge(tranche_id=1)
        session['hedges'] = [hedge]
        session['active_hedges'] = 1

        result = detect_displacement(session, repositioned_parent_id=1)

        assert result is not None
        assert result['status'] == HedgeStatus.ORPHANED
        assert result['displaced_from_parent_at'] is not None
        assert session['active_hedges'] == 0

    def test_hedge_not_closed_only_orphaned(self):
        from webui.backend.routes.mmmx.mmmx_hedger import detect_displacement
        from webui.backend.routes.mmmx.mmmx_constants import HedgeStatus

        session = _make_session()
        hedge = self._make_active_hedge(tranche_id=2)
        session['hedges'] = [hedge]
        session['active_hedges'] = 1

        detect_displacement(session, repositioned_parent_id=2)

        # ORPHANED, not CLOSED
        assert session['hedges'][0]['status'] == HedgeStatus.ORPHANED
        assert session['hedges'][0]['status'] != HedgeStatus.CLOSED

    def test_no_hedge_for_parent_returns_none(self):
        from webui.backend.routes.mmmx.mmmx_hedger import detect_displacement

        session = _make_session()
        session['hedges'] = []

        result = detect_displacement(session, repositioned_parent_id=99)

        assert result is None

    def test_wrong_parent_id_not_affected(self):
        from webui.backend.routes.mmmx.mmmx_hedger import detect_displacement
        from webui.backend.routes.mmmx.mmmx_constants import HedgeStatus

        session = _make_session()
        hedge = self._make_active_hedge(tranche_id=1)
        session['hedges'] = [hedge]
        session['active_hedges'] = 1

        detect_displacement(session, repositioned_parent_id=2)  # different parent

        assert session['hedges'][0]['status'] == HedgeStatus.ACTIVE
        assert session['active_hedges'] == 1

    def test_already_orphaned_hedge_not_double_counted(self):
        from webui.backend.routes.mmmx.mmmx_hedger import detect_displacement
        from webui.backend.routes.mmmx.mmmx_constants import HedgeStatus

        session = _make_session()
        hedge = self._make_active_hedge(tranche_id=3)
        hedge['status'] = HedgeStatus.ORPHANED
        session['hedges'] = [hedge]
        session['active_hedges'] = 0

        result = detect_displacement(session, repositioned_parent_id=3)

        # Already ORPHANED — should not be touched again (active_hedges stays 0)
        assert result is None
        assert session['active_hedges'] == 0

    def test_hedge_remains_after_hard_stop(self):
        """
        Hard stop scenario: hedges are marked ORPHANED, NOT closed.
        This simulates what should happen during a hard-stop close-all:
        detect_displacement marks them ORPHANED, close_all does NOT touch them.
        """
        from webui.backend.routes.mmmx.mmmx_hedger import detect_displacement
        from webui.backend.routes.mmmx.mmmx_constants import HedgeStatus

        session = _make_session()
        h1 = self._make_active_hedge(tranche_id=1)
        h2 = self._make_active_hedge(tranche_id=2)
        h2['parent_tranche_id'] = 2
        h2['hedge_id'] = 'H-Tr2'
        session['hedges'] = [h1, h2]
        session['active_hedges'] = 2

        # Hard stop: reposition/orphan all hedges
        detect_displacement(session, 1)
        detect_displacement(session, 2)

        # Both should be ORPHANED, NOT CLOSED
        for h in session['hedges']:
            assert h['status'] == HedgeStatus.ORPHANED
            assert h['status'] != HedgeStatus.CLOSED


# ══════════════════════════════════════════════════════════════════════════════
# 13. Multiple CBs fire on same tick
# ══════════════════════════════════════════════════════════════════════════════

class TestMultipleCBsSameTick:

    def test_premium_jump_and_delta_blowout_both_fire(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        listener = PremiumListener('test-p7-multi-0001', 1)
        session = _make_session(portfolio_delta=0.75)  # triggers CB_DELTA_BLOWOUT
        session['params']['emergency_delta'] = 0.70
        tranche = _make_active_tranche(ce_entry_premium=100.0)
        session['tranches'] = [tranche]

        # Tick also has a 60% premium jump
        tick = {'symbol': 'C-BTC-80000-280626', 'mark_price': 160.0}
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_PREMIUM_JUMP' in fired
        assert 'CB_DELTA_BLOWOUT' in fired
        assert session['_force_check'] is True

    def test_force_count_increments_for_each_cb(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import PremiumListener
        listener = PremiumListener('test-p7-multi-0002', 1)
        session = _make_session(portfolio_delta=0.75)
        session['params']['emergency_delta'] = 0.70
        session['params']['iv_catastrophe_pct'] = 80.0
        tranche = _make_active_tranche(ce_entry_premium=100.0)
        session['tranches'] = [tranche]

        # Tick triggers PREMIUM_JUMP, DELTA_BLOWOUT, IV_FLASH_SPIKE
        tick = {
            'symbol': 'C-BTC-80000-280626',
            'mark_price': 160.0,
            'iv': 90.0,
        }
        fired = _run(listener.evaluate_cbs(tick, session))

        assert 'CB_PREMIUM_JUMP' in fired
        assert 'CB_DELTA_BLOWOUT' in fired
        assert 'CB_IV_FLASH_SPIKE' in fired
        # force_heartbeat called once per CB — count should be >= 3
        assert session['_listener_force_count'] >= 3


# ══════════════════════════════════════════════════════════════════════════════
# 14. Registry functions
# ══════════════════════════════════════════════════════════════════════════════

class TestListenerRegistry:

    def test_get_listener_returns_none_when_not_registered(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import get_listener
        assert get_listener('no-such-session') is None

    def test_start_stop_listener(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import (
            start_session_listener, stop_session_listener, get_listener
        )
        session_id = 'test-p7-reg-001'
        listener = start_session_listener(session_id, my_generation=1)

        assert get_listener(session_id) is listener
        assert listener.is_alive()

        stop_session_listener(session_id)
        # After stop, removed from registry
        assert get_listener(session_id) is None

    def test_start_replaces_existing_listener(self):
        from webui.backend.routes.mmmx.mmmx_premium_listener import (
            start_session_listener, get_listener, stop_session_listener
        )
        session_id = 'test-p7-reg-002'
        l1 = start_session_listener(session_id, my_generation=1)
        l2 = start_session_listener(session_id, my_generation=2)

        assert get_listener(session_id) is l2
        assert l2._my_generation == 2

        stop_session_listener(session_id)
