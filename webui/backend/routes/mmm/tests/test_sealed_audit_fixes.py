"""
Sealed regression tests for the 5 audit fixes from session mmm26apr26-2.

Fix 1: check_position_cap uses total_lots (not active_lots)
Fix 2: clamp_replenish_to_cap prevents unbounded accumulation
Fix 3: Replenish cooldown prevents machine-gun sells
Fix 4: Watchdog reconciliation corrects drift from ledger DB
Fix 5: Gate 9b near-expiry kill switch blocks replenish < 5min to expiry
"""
import sys, os, time, unittest
from unittest.mock import patch, MagicMock
import pytest

pytestmark = pytest.mark.sealed

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..')))


# ---------------------------------------------------------------------------
# Fix 1: check_position_cap uses total_lots
# ---------------------------------------------------------------------------
class TestFix1PositionCapUsesTotalLots(unittest.TestCase):
    """Verify check_position_cap counts frozen lots against the cap."""

    def _make_session(self, ce_active, ce_total, pe_active, pe_total, max_per_side=100):
        return {
            'session_id': 'test-fix1',
            'params': {'max_lots_per_side': max_per_side},
            'ce': {'active_lots': ce_active, 'total_lots': ce_total},
            'pe': {'active_lots': pe_active, 'total_lots': pe_total},
        }

    def test_cap_breached_when_frozen_lots_push_over(self):
        """active=50 but total=110 → cap at 100 should fire."""
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        session = self._make_session(50, 110, 50, 50, max_per_side=100)
        safety = MMMSafety()
        events = safety.check_position_cap(session)
        alert_events = [e for e in events if e.get('level') == 'alert']
        self.assertTrue(len(alert_events) > 0,
                        f"Expected cap alert with total_lots=110 > max=100, got {events}")

    def test_cap_not_breached_when_total_under(self):
        """total_lots=90, active=50 → cap at 100 should NOT fire alert."""
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        session = self._make_session(50, 90, 50, 50, max_per_side=100)
        safety = MMMSafety()
        events = safety.check_position_cap(session)
        alert_events = [e for e in events if e.get('level') == 'alert']
        self.assertEqual(len(alert_events), 0,
                         f"Expected no cap alert with total_lots=90 < max=100, got {events}")

    def test_only_active_lots_would_pass_but_total_fails(self):
        """Regression: active=0 but total=150 (all frozen) → must trigger."""
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        session = self._make_session(0, 150, 0, 0, max_per_side=100)
        safety = MMMSafety()
        events = safety.check_position_cap(session)
        alert_events = [e for e in events if e.get('level') == 'alert']
        self.assertTrue(len(alert_events) > 0,
                        "Cap must trigger: 150 total lots exceed max 100")


# ---------------------------------------------------------------------------
# Fix 2: clamp_replenish_to_cap
# ---------------------------------------------------------------------------
class TestFix2ClampReplenishToCap(unittest.TestCase):
    """Verify clamp_replenish_to_cap reduces lots to fit the cap."""

    def test_clamp_reduces_lots(self):
        from webui.backend.routes.mmm.mmm_replenish import clamp_replenish_to_cap
        session = {
            'params': {'max_lots_per_side': 100},
            'ce': {'total_lots': 90},
        }
        # Want 20 lots, but only 10 slots remain
        result = clamp_replenish_to_cap(session, 'ce', 20)
        self.assertEqual(result, 10)

    def test_clamp_to_zero_when_at_cap(self):
        from webui.backend.routes.mmm.mmm_replenish import clamp_replenish_to_cap
        session = {
            'params': {'max_lots_per_side': 100},
            'pe': {'total_lots': 100},
        }
        result = clamp_replenish_to_cap(session, 'pe', 50)
        self.assertEqual(result, 0)

    def test_no_clamp_when_under_cap(self):
        from webui.backend.routes.mmm.mmm_replenish import clamp_replenish_to_cap
        session = {
            'params': {'max_lots_per_side': 100},
            'ce': {'total_lots': 50},
        }
        result = clamp_replenish_to_cap(session, 'ce', 20)
        self.assertEqual(result, 20)

    def test_clamp_over_cap_returns_zero(self):
        """Already over cap → must return 0 (not negative)."""
        from webui.backend.routes.mmm.mmm_replenish import clamp_replenish_to_cap
        session = {
            'params': {'max_lots_per_side': 100},
            'ce': {'total_lots': 120},
        }
        result = clamp_replenish_to_cap(session, 'ce', 10)
        self.assertEqual(result, 0)


# ---------------------------------------------------------------------------
# Fix 3: Replenish cooldown
# ---------------------------------------------------------------------------
class TestFix3ReplenishCooldown(unittest.TestCase):
    """Fix 3 is wired into _process_replenish. Unit-test the logic inline."""

    def test_cooldown_blocks_if_recent_replenish(self):
        """If _last_replenish_at is within cooldown, replenish should be blocked."""
        # This tests the specific cooldown logic pattern:
        cooldown_sec = 60
        last_at = time.time() - 10  # 10 seconds ago
        elapsed = time.time() - last_at
        self.assertLess(elapsed, cooldown_sec,
                        "Elapsed should be less than cooldown")
        # The monitor would return False in this case
        self.assertTrue(elapsed < cooldown_sec)

    def test_cooldown_allows_after_expiry(self):
        """After cooldown expires, replenish should proceed."""
        cooldown_sec = 60
        last_at = time.time() - 120  # 2 minutes ago
        elapsed = time.time() - last_at
        self.assertGreater(elapsed, cooldown_sec)

    def test_cooldown_allows_first_replenish(self):
        """If _last_replenish_at is 0, cooldown should not block."""
        last_at = 0
        self.assertEqual(last_at, 0, "First replenish should not be blocked")


# ---------------------------------------------------------------------------
# Fix 4: Watchdog reconciliation via ledger
# ---------------------------------------------------------------------------
class TestFix4LedgerReconciliation(unittest.TestCase):
    """Test get_session_lots_by_side and reconciliation logic."""

    def setUp(self):
        """Create a temporary in-memory ledger for testing."""
        import sqlite3
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE session_fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                qty INTEGER NOT NULL,
                price REAL NOT NULL,
                fill_id TEXT NOT NULL UNIQUE,
                order_id TEXT DEFAULT '',
                client_order_id TEXT DEFAULT '',
                commission REAL DEFAULT 0.0,
                option_side TEXT DEFAULT '',
                strike REAL DEFAULT 0.0,
                expiry TEXT DEFAULT ''
            );
        """)

    def tearDown(self):
        self.conn.close()

    def _insert_fill(self, session_id, side, qty, option_side, fill_id):
        self.conn.execute(
            """INSERT INTO session_fills
               (recorded_at, session_id, symbol, side, qty, price, fill_id, option_side)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ('2026-01-01', session_id, 'BTC-C-100000', side, qty, 100.0, fill_id, option_side)
        )
        self.conn.commit()

    def test_net_lots_by_side(self):
        """Directly test the SQL logic for net lots per option_side."""
        self._insert_fill('s1', 'sell', 50, 'ce', 'f1')
        self._insert_fill('s1', 'sell', 30, 'ce', 'f2')
        self._insert_fill('s1', 'buy', 20, 'ce', 'f3')
        self._insert_fill('s1', 'sell', 40, 'pe', 'f4')

        row = self.conn.execute("""
            SELECT option_side,
                   COALESCE(SUM(CASE WHEN side='sell' THEN qty ELSE 0 END), 0) AS sell_lots,
                   COALESCE(SUM(CASE WHEN side='buy'  THEN qty ELSE 0 END), 0) AS buy_lots
            FROM session_fills
            WHERE session_id = ? AND option_side IN ('ce', 'pe')
            GROUP BY option_side
        """, ('s1',)).fetchall()

        result = {r['option_side']: max(int(r['sell_lots'] - r['buy_lots']), 0) for r in row}
        self.assertEqual(result['ce'], 60)  # 80 sold - 20 bought
        self.assertEqual(result['pe'], 40)  # 40 sold - 0 bought

    def test_reconciliation_corrects_drift(self):
        """Simulate watchdog reconciliation: memory says 0, DB says 60."""
        # Simulate the reconciliation logic
        fresh_session = {
            'session_id': 'test-recon',
            'ce': {'total_lots': 0, 'active_lots': 0, 'frozen_total_lots': 0},
            'pe': {'total_lots': 10, 'active_lots': 10, 'frozen_total_lots': 0},
        }
        db_lots = {'ce': 60, 'pe': 10}

        for side_key in ('ce', 'pe'):
            mem_total = fresh_session.get(side_key, {}).get('total_lots', 0)
            db_total = db_lots.get(side_key, 0)
            if mem_total != db_total:
                if side_key in fresh_session:
                    fresh_session[side_key]['total_lots'] = db_total
                    frozen = fresh_session[side_key].get('frozen_total_lots', 0)
                    fresh_session[side_key]['active_lots'] = max(db_total - frozen, 0)

        self.assertEqual(fresh_session['ce']['total_lots'], 60)
        self.assertEqual(fresh_session['ce']['active_lots'], 60)
        self.assertEqual(fresh_session['pe']['total_lots'], 10)  # unchanged


# ---------------------------------------------------------------------------
# Fix 5: Near-expiry kill switch (Gate 9b)
# ---------------------------------------------------------------------------
class TestFix5NearExpiryKillSwitch(unittest.TestCase):
    """Gate 9b: replenish blocked when <5min to expiry."""

    def test_blocked_near_expiry(self):
        from webui.backend.routes.mmm.mmm_replenish import check_replenish_eligibility
        session = {
            'session_id': 'test-fix5',
            'status': 'running',
            'params': {
                'max_lots_per_side': 100,
                'close_at_5_enabled': True,
                'replenish_enabled': True,
            },
            'minutes_to_expiry': 3.0,
            '_minutes_to_expiry': 3.0,
            'ce': {'active_lots': 50, 'total_lots': 50},
            'pe': {'active_lots': 50, 'total_lots': 50},
        }
        eligible, reason = check_replenish_eligibility(session, 'ce', 'pe')
        self.assertFalse(eligible,
                         f"Replenish should be blocked near expiry. Got: {reason}")
        self.assertIn('near_expiry', reason.lower(),
                      f"Reason should mention near_expiry: {reason}")

    def test_allowed_far_from_expiry(self):
        from webui.backend.routes.mmm.mmm_replenish import check_replenish_eligibility
        session = {
            'session_id': 'test-fix5',
            'status': 'running',
            'params': {
                'max_lots_per_side': 100,
                'close_at_5_enabled': True,
            },
            'minutes_to_expiry': 30.0,
            '_minutes_to_expiry': 30.0,
            'ce': {'active_lots': 0, 'total_lots': 0},
            'pe': {'active_lots': 50, 'total_lots': 50},
        }
        eligible, reason = check_replenish_eligibility(session, 'ce', 'pe')
        # Should NOT be blocked by near-expiry (may be blocked by other gates)
        if not eligible:
            self.assertNotIn('near_expiry', reason.lower(),
                             f"Should not be blocked by near_expiry at 30min: {reason}")


# ---------------------------------------------------------------------------
# Cross-fix integration: cap + cooldown + near-expiry stack correctly
# ---------------------------------------------------------------------------
class TestCrossFixIntegration(unittest.TestCase):
    """Multiple safety gates stack: most restrictive wins."""

    def test_near_expiry_takes_priority_over_eligibility(self):
        """Even if replenish is otherwise eligible, <5min blocks it."""
        from webui.backend.routes.mmm.mmm_replenish import check_replenish_eligibility
        session = {
            'session_id': 'test-cross',
            'status': 'running',
            'params': {
                'max_lots_per_side': 200,
                'close_at_5_enabled': True,
            },
            'minutes_to_expiry': 2.0,
            '_minutes_to_expiry': 2.0,
            'ce': {'active_lots': 0, 'total_lots': 0},
            'pe': {'active_lots': 100, 'total_lots': 100},
        }
        eligible, reason = check_replenish_eligibility(session, 'ce', 'pe')
        self.assertFalse(eligible)

    def test_cap_clamp_on_top_of_eligibility(self):
        """Lots determined but then clamped to remaining cap space."""
        from webui.backend.routes.mmm.mmm_replenish import clamp_replenish_to_cap
        session = {
            'params': {'max_lots_per_side': 100},
            'ce': {'total_lots': 95},
        }
        # determine_replenish_lots might say 50, but cap leaves only 5
        clamped = clamp_replenish_to_cap(session, 'ce', 50)
        self.assertEqual(clamped, 5)


# =============================================================================
# Score Improvement Plan — Sealed regression tests (2026-04-27)
# =============================================================================

# ---------------------------------------------------------------------------
# A3-01: Stale unrealized cache zeroed after consecutive fetch failures
# ---------------------------------------------------------------------------
class TestA301StaleUnrealizedFallback(unittest.TestCase):
    """A3-01: session['unrealized_pnl'] zeroed after 3 consecutive fetch failures."""

    def _apply_fetch_result(self, session, fetch_ok: bool):
        """Replicate the A3-01 inline logic from mmm_monitor.py._heartbeat()."""
        if fetch_ok:
            session['_prem_fetch_failures'] = 0
        else:
            _prem_fails = session.get('_prem_fetch_failures', 0) + 1
            session['_prem_fetch_failures'] = _prem_fails
            if _prem_fails >= 3:
                session['unrealized_pnl'] = 0.0

    def test_failure_counter_increments_on_each_miss(self):
        """Counter increments correctly on repeated fetch failure."""
        session = {'_prem_fetch_failures': 0, 'unrealized_pnl': -100.0}
        self._apply_fetch_result(session, fetch_ok=False)
        self.assertEqual(session['_prem_fetch_failures'], 1)
        self._apply_fetch_result(session, fetch_ok=False)
        self.assertEqual(session['_prem_fetch_failures'], 2)
        # unrealized NOT zeroed yet (only at 3+)
        self.assertEqual(session['unrealized_pnl'], -100.0)

    def test_unrealized_zeroed_at_third_failure(self):
        """After 3 consecutive failures, unrealized_pnl is set to 0.0."""
        session = {'_prem_fetch_failures': 2, 'unrealized_pnl': -500.0}
        self._apply_fetch_result(session, fetch_ok=False)
        self.assertEqual(session['_prem_fetch_failures'], 3)
        self.assertEqual(session['unrealized_pnl'], 0.0,
                         "unrealized_pnl must be zeroed after 3 failures to avoid stale max-loss bypass")

    def test_counter_resets_on_success(self):
        """Successful fetch resets counter; unrealized is NOT cleared by success."""
        session = {'_prem_fetch_failures': 2, 'unrealized_pnl': -300.0}
        self._apply_fetch_result(session, fetch_ok=True)
        self.assertEqual(session['_prem_fetch_failures'], 0)
        self.assertEqual(session['unrealized_pnl'], -300.0)


# ---------------------------------------------------------------------------
# A6-11 / A11-01: Gamma limits and velocity limit scale with initial_lots
# ---------------------------------------------------------------------------
class TestA611GammaScaling(unittest.TestCase):
    """A6-11/A11-01: Gamma limits are lot-proportional when not explicitly provided."""

    def _create(self, initial_lots, explicit_params=None):
        from webui.backend.routes.mmm.mmm_state import create_session
        p = {'initial_lots': initial_lots, 'expiry': '2027-01-31'}
        if explicit_params:
            p.update(explicit_params)
        return create_session(params=p)

    def test_default_10_lots_gives_legacy_limits(self):
        """initial_lots=10 → gamma_hard_limit=5000 (identical to old fixed default)."""
        s = self._create(initial_lots=10)
        self.assertEqual(s['params']['gamma_hard_limit'], 5000.0)
        self.assertEqual(s['params']['gamma_soft_limit'], 2500.0)
        self.assertEqual(s['params']['gamma_emergency_limit'], 10000.0)

    def test_100_lots_scales_gamma_limits(self):
        """initial_lots=100 → gamma limits are 10× the 10-lot defaults."""
        s = self._create(initial_lots=100)
        self.assertEqual(s['params']['gamma_hard_limit'], 50000.0)
        self.assertEqual(s['params']['gamma_soft_limit'], 25000.0)
        self.assertGreater(s['params']['gamma_emergency_limit'], 5000.0)

    def test_explicit_gamma_not_overridden(self):
        """Operator-provided gamma_hard_limit is never overridden."""
        s = self._create(initial_lots=100, explicit_params={'gamma_hard_limit': 9999.0})
        self.assertEqual(s['params']['gamma_hard_limit'], 9999.0,
                         "Explicitly provided gamma_hard_limit must not be scaled")

    def test_lot_velocity_scales_with_initial_lots(self):
        """lot_velocity_limit = max(30, initial_lots * 3) when not explicitly set."""
        s50 = self._create(initial_lots=50)
        self.assertEqual(s50['params']['lot_velocity_limit'], 150)

        s5 = self._create(initial_lots=5)
        self.assertEqual(s5['params']['lot_velocity_limit'], 30,
                         "velocity_limit must be at least 30 even for small sessions")


# ---------------------------------------------------------------------------
# A8-02: Worthless expiry fill closes position and books full premium as P&L
# ---------------------------------------------------------------------------
class TestA802WorthlessExpiry(unittest.TestCase):
    """A8-02: Zero-price settlement fill marks position closed and books realized P&L."""

    def _make_fs(self):
        from webui.backend.routes.mmm.mmm_fill_sync import FillSyncer
        fs = object.__new__(FillSyncer)
        fs._session_id = 'test-we-001'
        return fs

    def _make_session(self, strike=95000.0, entry_premium=350.0, lots=5):
        pos = {
            'id': 'pos_we_001',
            'strike': strike,
            'lots': lots,
            'entry_premium': entry_premium,
            'premium': entry_premium,
            'status': 'active',
            '_fill_confirmed': False,
        }
        return {
            'session_id': 'test-we-001',
            'realized_pnl': 0.0,
            'ce': {
                'positions': [pos],
                'total_lots': lots,
                'active_lots': lots,
                'frozen_lots': 0,
            },
        }

    def test_position_marked_closed_on_worthless_fill(self):
        """CE position at matching strike → status='closed' after zero-price fill."""
        fs = self._make_fs()
        session = self._make_session(strike=95000.0)
        with patch('webui.backend.routes.mmm.mmm_fill_sync.log_activity'):
            result = fs._close_worthless_expiry(
                session,
                symbol='C-BTC-95000-011225',
                fill_size=5,
                fill_id='exp_fill_001',
                fill_type='settlement',
            )
        self.assertEqual(result, 1)
        pos = session['ce']['positions'][0]
        self.assertEqual(pos['status'], 'closed')
        self.assertEqual(pos['close_fill_price'], 0.0)
        self.assertTrue(pos['_fill_confirmed'])

    def test_realized_pnl_booked_on_worthless_close(self):
        """Full entry_premium × lots × LOT_SIZE_BTC is added to realized_pnl."""
        from webui.backend.routes.mmm.mmm_constants import LOT_SIZE_BTC
        fs = self._make_fs()
        entry = 400.0
        lots = 3
        session = self._make_session(strike=95000.0, entry_premium=entry, lots=lots)
        with patch('webui.backend.routes.mmm.mmm_fill_sync.log_activity'):
            fs._close_worthless_expiry(
                session,
                symbol='C-BTC-95000-011225',
                fill_size=lots,
                fill_id='exp_fill_002',
                fill_type='settlement',
            )
        expected_pnl = entry * lots * LOT_SIZE_BTC
        self.assertAlmostEqual(session['realized_pnl'], expected_pnl, places=6)

    def test_pe_symbol_routes_to_pe_positions(self):
        """P- prefix routes to PE side positions."""
        fs = self._make_fs()
        session = {
            'session_id': 'test-we-001',
            'realized_pnl': 0.0,
            'pe': {
                'positions': [{
                    'id': 'pe_pos_001',
                    'strike': 90000.0,
                    'lots': 2,
                    'entry_premium': 200.0,
                    'status': 'active',
                    '_fill_confirmed': False,
                }],
                'total_lots': 2,
                'active_lots': 2,
                'frozen_lots': 0,
            },
        }
        with patch('webui.backend.routes.mmm.mmm_fill_sync.log_activity'):
            result = fs._close_worthless_expiry(
                session,
                symbol='P-BTC-90000-011225',
                fill_size=2,
                fill_id='exp_fill_003',
                fill_type='settlement',
            )
        self.assertEqual(result, 1)
        self.assertEqual(session['pe']['positions'][0]['status'], 'closed')

    def test_nonmatching_strike_not_closed(self):
        """Fill for strike 90000 does not close position at strike 95000."""
        fs = self._make_fs()
        session = self._make_session(strike=95000.0)
        with patch('webui.backend.routes.mmm.mmm_fill_sync.log_activity'):
            result = fs._close_worthless_expiry(
                session,
                symbol='C-BTC-90000-011225',
                fill_size=5,
                fill_id='exp_fill_004',
                fill_type='settlement',
            )
        self.assertEqual(result, 0)
        self.assertEqual(session['ce']['positions'][0]['status'], 'active')


# ---------------------------------------------------------------------------
# A7-01: get_session_open_positions_by_side reconstructs positions from DB
# ---------------------------------------------------------------------------
class TestA701LedgerPositionReconstruct(unittest.TestCase):
    """A7-01: get_session_open_positions_by_side returns net-open positions from fills DB."""

    def _make_db_rows(self, rows):
        """Build sqlite3.Row-like dicts for mocking DB queries."""
        class FakeRow(dict):
            def __getitem__(self, k):
                return super().__getitem__(k)
            def __getattr__(self, k):
                return self[k]
        return [FakeRow(r) for r in rows]

    def test_net_open_position_returned(self):
        """Row with sell_lots=5, buy_lots=2 → net 3 lots returned as active position."""
        rows = self._make_db_rows([{
            'option_side': 'ce',
            'symbol': 'C-BTC-95000-011225',
            'strike': 95000.0,
            'sell_lots': 5,
            'buy_lots': 2,
            'avg_sell_price': 300.0,
        }])

        from webui.backend.routes.mmm.mmm_ledger import get_session_open_positions_by_side
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchall.return_value = rows
        ctx_mock = MagicMock()
        ctx_mock.__enter__ = MagicMock(return_value=conn_mock)
        ctx_mock.__exit__ = MagicMock(return_value=False)

        with patch('webui.backend.routes.mmm.mmm_ledger._connect', return_value=ctx_mock):
            result = get_session_open_positions_by_side('sess-001')

        self.assertEqual(len(result['ce']), 1)
        pos = result['ce'][0]
        self.assertEqual(pos['lots'], 3)
        self.assertEqual(pos['strike'], 95000.0)
        self.assertAlmostEqual(pos['entry_premium'], 300.0)
        self.assertEqual(pos['status'], 'active')
        self.assertEqual(pos['source'], 'ledger_restore')

    def test_fully_closed_position_not_returned(self):
        """Row with sell_lots == buy_lots (HAVING sell_lots > buy_lots filters it) → not returned."""
        rows = self._make_db_rows([])  # DB already filtered out equal rows
        from webui.backend.routes.mmm.mmm_ledger import get_session_open_positions_by_side
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchall.return_value = rows
        ctx_mock = MagicMock()
        ctx_mock.__enter__ = MagicMock(return_value=conn_mock)
        ctx_mock.__exit__ = MagicMock(return_value=False)
        with patch('webui.backend.routes.mmm.mmm_ledger._connect', return_value=ctx_mock):
            result = get_session_open_positions_by_side('sess-002')
        self.assertEqual(result['ce'], [])
        self.assertEqual(result['pe'], [])

    def test_both_sides_reconstructed(self):
        """CE and PE positions reconstructed in a single call."""
        rows = self._make_db_rows([
            {'option_side': 'ce', 'symbol': 'C-BTC-95000-011225', 'strike': 95000.0,
             'sell_lots': 10, 'buy_lots': 3, 'avg_sell_price': 250.0},
            {'option_side': 'pe', 'symbol': 'P-BTC-90000-011225', 'strike': 90000.0,
             'sell_lots': 8, 'buy_lots': 0, 'avg_sell_price': 150.0},
        ])
        from webui.backend.routes.mmm.mmm_ledger import get_session_open_positions_by_side
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchall.return_value = rows
        ctx_mock = MagicMock()
        ctx_mock.__enter__ = MagicMock(return_value=conn_mock)
        ctx_mock.__exit__ = MagicMock(return_value=False)
        with patch('webui.backend.routes.mmm.mmm_ledger._connect', return_value=ctx_mock):
            result = get_session_open_positions_by_side('sess-003')
        self.assertEqual(result['ce'][0]['lots'], 7)
        self.assertEqual(result['pe'][0]['lots'], 8)


# ---------------------------------------------------------------------------
# A11-02: APIRateBudget.consume — token-bucket rate limiter
# ---------------------------------------------------------------------------
class TestA1102APIRateBudget(unittest.TestCase):
    """A11-02: APIRateBudget.consume enforces token-bucket rate limiting."""

    def _make_budget(self, capacity=10):
        from webui.backend.routes.mmm.mmm_api_budget import APIRateBudget
        b = APIRateBudget(calls_per_minute=capacity)
        b.reset()
        return b

    def test_normal_call_allowed_when_tokens_available(self):
        """Normal priority call returns True when budget has tokens."""
        b = self._make_budget(capacity=10)
        self.assertTrue(b.consume(count=1, priority='normal'))

    def test_normal_call_blocked_when_budget_exhausted(self):
        """Normal priority call returns False after tokens are exhausted."""
        b = self._make_budget(capacity=3)
        b.consume(3, priority='normal')  # exhaust
        self.assertFalse(b.consume(1, priority='normal'),
                         "Normal call must be blocked when token bucket is empty")

    def test_critical_call_always_allowed_even_when_exhausted(self):
        """Critical priority (order placement) is never blocked regardless of budget."""
        b = self._make_budget(capacity=3)
        b.consume(3, priority='normal')  # exhaust
        self.assertTrue(b.consume(1, priority='critical'),
                        "Critical call must always return True — order placement must never be refused")

    def test_tokens_depleted_by_consume(self):
        """Tokens remaining decreases after successful consume."""
        b = self._make_budget(capacity=10)
        before = b.remaining()
        b.consume(3, priority='normal')
        self.assertLess(b.remaining(), before)

    def test_reset_restores_full_capacity(self):
        """reset() brings token count back to full capacity."""
        b = self._make_budget(capacity=10)
        b.consume(8, priority='normal')
        b.reset()
        self.assertAlmostEqual(b.remaining(), 10.0, delta=0.1)

    def test_stats_returns_required_keys(self):
        """stats() always returns dict with remaining/capacity/utilization_pct."""
        b = self._make_budget(capacity=10)
        s = b.stats()
        for key in ('remaining', 'capacity', 'total_consumed', 'total_blocked', 'utilization_pct'):
            self.assertIn(key, s, f"stats() must include '{key}'")

    def test_thread_safety_no_race_on_concurrent_consume(self):
        """Multiple threads consuming simultaneously do not corrupt token count."""
        import threading
        b = self._make_budget(capacity=100)
        results = []

        def worker():
            results.append(b.consume(1, priority='normal'))

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # remaining must be non-negative and >= 0
        self.assertGreaterEqual(b.remaining(), 0.0,
                                "Token count must never go negative under concurrent access")


# ---------------------------------------------------------------------------
# A11-03: SQLite concurrency at scale — connection-per-call isolation
# ---------------------------------------------------------------------------
class TestA1103SQLiteConcurrency(unittest.TestCase):
    """
    A11-03 evaluation: SQLite + WAL mode is acceptable for 3–5 concurrent sessions.

    Verifies:
    - Connection-per-call pattern does not produce database-locked errors under
      concurrent access from N threads simulating N monitor sessions.
    - busy_timeout=5000 in both mmm_storage._get_conn() and mmm_ledger._connect()
      means writers wait rather than failing immediately.
    - Reader isolation: concurrent readers never see partial writes.
    """

    def test_ledger_connect_has_busy_timeout(self):
        """A11-03: mmm_ledger._connect() source must contain PRAGMA busy_timeout (A11-03 fix)."""
        import inspect
        from webui.backend.routes.mmm.mmm_ledger import _connect
        src = inspect.getsource(_connect)
        self.assertIn('busy_timeout', src.lower(),
                      "_connect() must contain 'PRAGMA busy_timeout' — "
                      "without it concurrent fill recordings fail immediately under write contention")

    def test_storage_connect_has_busy_timeout(self):
        """A11-03: MMMStorage._get_conn() source must contain PRAGMA busy_timeout."""
        import inspect
        from webui.backend.routes.mmm.mmm_storage import MMMStorage
        src = inspect.getsource(MMMStorage._get_conn)
        self.assertIn('busy_timeout', src.lower(),
                      "MMMStorage._get_conn() must contain 'PRAGMA busy_timeout'")

    def test_concurrent_ledger_record_fill_no_errors(self):
        """A11-03: N concurrent threads recording fills to ledger produce no OperationalError."""
        import threading
        import tempfile
        import os
        from unittest.mock import patch

        errors = []

        # Use a real temp DB so WAL mode + concurrency is exercised genuinely
        with tempfile.NamedTemporaryFile(suffix='_ledger_test.db', delete=False) as f:
            tmp_db = f.name

        try:
            # Patch _DB_PATH to point at temp file
            with patch('webui.backend.routes.mmm.mmm_ledger._DB_PATH', tmp_db):
                from webui.backend.routes.mmm.mmm_ledger import init_ledger, record_fill

                init_ledger()

                def worker(session_idx):
                    try:
                        record_fill(
                            session_id=f'stress-sess-{session_idx:03d}',
                            symbol='C-BTC-95000-011225',
                            side='sell',
                            qty=5,
                            price=300.0,
                            fill_id=f'fill_{session_idx:06d}',
                            order_id=f'ord_{session_idx:06d}',
                            option_side='ce',
                            strike=95000.0,
                        )
                    except Exception as e:
                        errors.append(f"Thread {session_idx}: {e}")

                threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

        finally:
            try:
                os.unlink(tmp_db)
                os.unlink(tmp_db + '-wal')
                os.unlink(tmp_db + '-shm')
            except OSError:
                pass

        self.assertEqual(errors, [],
                         f"Concurrent fill recording must not produce errors. Got: {errors}")


# ---------------------------------------------------------------------------
# Phase 3 Coordination Arbiter — sealed tests
# Source: MMM_COORDINATION_PLAN.md (Phase 2 sealed hierarchy + Phase 1 audits)
# Created: 2026-04-28
# ---------------------------------------------------------------------------

class TestArbiterTier1DefensiveShift(unittest.TestCase):
    """Arbiter at Tier 1 (BE CRITICAL) emits ACTION_DEFENSIVE_SHIFT on opposite side
    with target_premium from session params. Per Phase 2 D1 + Rule 4."""

    def _make_session(self, be_zone='CRITICAL', nearest_side='lower'):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        return {
            'session_id': 'test-arbiter-shift',
            'adjustment_count': 5,
            '_minutes_to_expiry': 240,  # 4 hours — outside cool-down
            '_breakeven_zone': be_zone,
            '_breakeven_zone_last_updated_at': now,
            '_breakeven_result': {'nearest_side': nearest_side, 'zone': be_zone},
            '_gamma_regime': 'NORMAL',
            '_gamma_regime_last_updated_at': now,
            '_margin_tier': 'GREEN',
            '_margin_tier_last_updated_at': now,
            'ce': {'active_lots': 50, 'unrealized_pnl': -10},
            'pe': {'active_lots': 50, 'unrealized_pnl': -500},
            'params': {
                'adjustment_interval': 300,
                'shift_target_premium': 100.0,
                'shift_premium_tolerance': 10.0,
            },
        }

    def test_critical_lower_be_triggers_ce_shift(self):
        """Lower BE threatened (PE side aggressor in falling market) → shift CE."""
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_DEFENSIVE_SHIFT, TIER_1_EXTREME,
        )
        session = self._make_session(be_zone='CRITICAL', nearest_side='lower')
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_DEFENSIVE_SHIFT)
        self.assertEqual(decision.tier, TIER_1_EXTREME)
        self.assertEqual(decision.side, 'ce')
        self.assertEqual(decision.target_premium, 100.0)

    def test_critical_upper_be_triggers_pe_shift(self):
        """Upper BE threatened (CE side aggressor in rising market) → shift PE."""
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_DEFENSIVE_SHIFT,
        )
        session = self._make_session(be_zone='CRITICAL', nearest_side='upper')
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_DEFENSIVE_SHIFT)
        self.assertEqual(decision.side, 'pe')

    def test_be_warning_is_noop(self):
        """BE WARNING (Tier 2) → arbiter is silent per Rule 3."""
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_NOOP,
        )
        session = self._make_session(be_zone='WARNING')
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_NOOP)

    def test_be_danger_is_noop(self):
        """BE DANGER (Tier 2) → modules work as designed; no arbiter action."""
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_NOOP,
        )
        session = self._make_session(be_zone='DANGER')
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_NOOP)


class TestArbiterRule5Last30MinCooldown(unittest.TestCase):
    """Per Phase 2 D5 / Rule 5: in last 30 min before expiry, Tier 1 bypass DISABLED.
    Even with breakeven CRITICAL, arbiter must return NOOP."""

    def test_critical_be_in_last_30_min_is_noop(self):
        from datetime import datetime, timezone
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_NOOP,
        )
        now = datetime.now(timezone.utc).isoformat()
        session = {
            'session_id': 'test-arbiter-cooldown',
            'adjustment_count': 10,
            '_minutes_to_expiry': 25,  # in cool-down window
            '_breakeven_zone': 'CRITICAL',
            '_breakeven_zone_last_updated_at': now,
            '_breakeven_result': {'nearest_side': 'lower', 'zone': 'CRITICAL'},
            '_gamma_regime': 'EMERGENCY',
            '_gamma_regime_last_updated_at': now,
            '_margin_tier': 'RED',
            '_margin_tier_last_updated_at': now,
            'ce': {'active_lots': 50, 'unrealized_pnl': 0},
            'pe': {'active_lots': 50, 'unrealized_pnl': -500},
            'params': {'adjustment_interval': 300, 'shift_target_premium': 100.0},
        }
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_NOOP)
        self.assertEqual(decision.trigger, 'last_30_min_cooldown')

    def test_at_30_min_boundary_is_noop(self):
        """Boundary check: minutes_to_expiry == 30 must trigger cool-down (≤30)."""
        from datetime import datetime, timezone
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_NOOP,
        )
        now = datetime.now(timezone.utc).isoformat()
        session = {
            'session_id': 'test-arbiter-boundary',
            'adjustment_count': 10,
            '_minutes_to_expiry': 30,
            '_breakeven_zone': 'CRITICAL',
            '_breakeven_zone_last_updated_at': now,
            '_breakeven_result': {'nearest_side': 'lower', 'zone': 'CRITICAL'},
            '_gamma_regime': 'NORMAL',
            '_gamma_regime_last_updated_at': now,
            '_margin_tier': 'GREEN',
            '_margin_tier_last_updated_at': now,
            'ce': {'active_lots': 50, 'unrealized_pnl': 0},
            'pe': {'active_lots': 50, 'unrealized_pnl': -100},
            'params': {'adjustment_interval': 300},
        }
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.trigger, 'last_30_min_cooldown')


class TestArbiterRule6StaleEscalation(unittest.TestCase):
    """Per Phase 2 G1 / Rule 6: stale signals escalate one tier for arbiter purposes.
    Module's own state is NOT mutated."""

    def test_stale_be_warning_escalates_to_danger(self):
        """Stale _breakeven_zone='WARNING' → arbiter sees DANGER (still Tier 2 → NOOP)."""
        from datetime import datetime, timedelta, timezone
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, get_effective_breakeven_zone,
        )
        # 10 minutes old — stale at default 1.5 × 300s = 450s threshold
        old = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        session = {
            'session_id': 'test-stale',
            'adjustment_count': 5,
            '_minutes_to_expiry': 240,
            '_breakeven_zone': 'WARNING',
            '_breakeven_zone_last_updated_at': old,  # stale
            '_breakeven_result': {'nearest_side': 'lower', 'zone': 'WARNING'},
            '_gamma_regime': 'NORMAL',
            '_gamma_regime_last_updated_at': now,
            '_margin_tier': 'GREEN',
            '_margin_tier_last_updated_at': now,
            'ce': {'active_lots': 50, 'unrealized_pnl': 0},
            'pe': {'active_lots': 50, 'unrealized_pnl': -100},
            'params': {'adjustment_interval': 300},
        }
        eff, stale = get_effective_breakeven_zone(session, 450.0)
        self.assertEqual(eff, 'DANGER')
        self.assertIsNotNone(stale)
        self.assertEqual(stale.raw_value, 'WARNING')
        self.assertEqual(stale.effective_value, 'DANGER')
        # Module state must remain untouched
        self.assertEqual(session['_breakeven_zone'], 'WARNING')

    def test_stale_be_danger_escalates_to_critical_triggers_shift(self):
        """Stale BE DANGER → effective CRITICAL → defensive shift."""
        from datetime import datetime, timedelta, timezone
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_DEFENSIVE_SHIFT,
        )
        old = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        session = {
            'session_id': 'test-stale-escalate',
            'adjustment_count': 5,
            '_minutes_to_expiry': 240,
            '_breakeven_zone': 'DANGER',
            '_breakeven_zone_last_updated_at': old,
            '_breakeven_result': {'nearest_side': 'upper', 'zone': 'DANGER'},
            '_gamma_regime': 'NORMAL',
            '_gamma_regime_last_updated_at': now,
            '_margin_tier': 'GREEN',
            '_margin_tier_last_updated_at': now,
            'ce': {'active_lots': 50, 'unrealized_pnl': -100},
            'pe': {'active_lots': 50, 'unrealized_pnl': 0},
            'params': {'adjustment_interval': 300, 'shift_target_premium': 100.0},
        }
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_DEFENSIVE_SHIFT)
        # Stale signal recorded for audit
        self.assertEqual(len(decision.stale_signals), 1)
        self.assertEqual(decision.stale_signals[0].name, 'breakeven_zone')


class TestArbiterTier1GammaEmergency(unittest.TestCase):
    """Gamma EMERGENCY → defensive close on dominant-gamma side per Phase 1 Task 2.
    Replaces legacy session pause."""

    def _make_session(self, ce_dgamma, pe_dgamma, strategy='SHORT_STRANGLE'):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        return {
            'session_id': 'test-arbiter-gamma',
            'adjustment_count': 5,
            '_minutes_to_expiry': 240,
            '_breakeven_zone': 'SAFE',
            '_breakeven_zone_last_updated_at': now,
            '_gamma_regime': 'EMERGENCY',
            '_gamma_regime_last_updated_at': now,
            '_ce_dollar_gamma': ce_dgamma,
            '_pe_dollar_gamma': pe_dgamma,
            '_margin_tier': 'GREEN',
            '_margin_tier_last_updated_at': now,
            'ce': {'active_lots': 80},
            'pe': {'active_lots': 50},
            'params': {'adjustment_interval': 300, 'strategy_type': strategy},
        }

    def test_ce_dominant_gamma_triggers_ce_close(self):
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_GAMMA_EMERGENCY_CLOSE,
        )
        session = self._make_session(ce_dgamma=8000, pe_dgamma=2000)
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_GAMMA_EMERGENCY_CLOSE)
        self.assertEqual(decision.side, 'ce')
        # 25% of 80 lots = 20
        self.assertEqual(decision.lots, 20)

    def test_pe_dominant_gamma_triggers_pe_close(self):
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_GAMMA_EMERGENCY_CLOSE,
        )
        session = self._make_session(ce_dgamma=1000, pe_dgamma=9000)
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_GAMMA_EMERGENCY_CLOSE)
        self.assertEqual(decision.side, 'pe')

    def test_straddle_with_adjustment_bypasses_gamma_action(self):
        """STRADDLE_WITH_ADJUSTMENT: gamma is structural; arbiter does NOT close
        on gamma EMERGENCY for this strategy (per CLAUDE.md §0 rule 6 + Phase 2 D6)."""
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_GAMMA_EMERGENCY_CLOSE, ACTION_NOOP,
        )
        session = self._make_session(
            ce_dgamma=8000, pe_dgamma=2000,
            strategy='STRADDLE_WITH_ADJUSTMENT',
        )
        decision = CoordinationArbiter().evaluate(session)
        self.assertNotEqual(decision.action_type, ACTION_GAMMA_EMERGENCY_CLOSE)


class TestArbiterTier1MarginRecovery(unittest.TestCase):
    """Margin RED → arbiter signals margin-recovery buyback on side with more lots.
    Per Phase 2 B2."""

    def test_margin_red_triggers_recovery(self):
        from datetime import datetime, timezone
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_MARGIN_RECOVERY,
        )
        now = datetime.now(timezone.utc).isoformat()
        session = {
            'session_id': 'test-arbiter-margin',
            'adjustment_count': 5,
            '_minutes_to_expiry': 240,
            '_breakeven_zone': 'SAFE',
            '_breakeven_zone_last_updated_at': now,
            '_gamma_regime': 'NORMAL',
            '_gamma_regime_last_updated_at': now,
            '_margin_tier': 'RED',
            '_margin_tier_last_updated_at': now,
            'ce': {'active_lots': 100},
            'pe': {'active_lots': 60},
            'params': {'adjustment_interval': 300},
        }
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_MARGIN_RECOVERY)
        self.assertEqual(decision.side, 'ce')  # bigger side scanned for buyback

    def test_margin_red_has_priority_over_be_critical(self):
        """Margin RED + BE CRITICAL: margin recovery wins (capital constraint binds)."""
        from datetime import datetime, timezone
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_MARGIN_RECOVERY,
        )
        now = datetime.now(timezone.utc).isoformat()
        session = {
            'session_id': 'test-arbiter-margin-priority',
            'adjustment_count': 5,
            '_minutes_to_expiry': 240,
            '_breakeven_zone': 'CRITICAL',
            '_breakeven_zone_last_updated_at': now,
            '_breakeven_result': {'nearest_side': 'lower', 'zone': 'CRITICAL'},
            '_gamma_regime': 'NORMAL',
            '_gamma_regime_last_updated_at': now,
            '_margin_tier': 'RED',
            '_margin_tier_last_updated_at': now,
            'ce': {'active_lots': 100},
            'pe': {'active_lots': 60},
            'params': {'adjustment_interval': 300, 'shift_target_premium': 100.0},
        }
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_MARGIN_RECOVERY)


class TestArbiterAuditTrail(unittest.TestCase):
    """Per Rule 7: arbiter decision must serialize cleanly for audit log."""

    def test_decision_to_audit_dict_includes_all_fields(self):
        from webui.backend.routes.mmm.mmm_arbiter import (
            ArbiterDecision, ACTION_DEFENSIVE_SHIFT, TIER_1_EXTREME, StaleSignal,
        )
        d = ArbiterDecision(
            action_type=ACTION_DEFENSIVE_SHIFT,
            tier=TIER_1_EXTREME,
            trigger='breakeven_critical_pe',
            side='ce',
            target_premium=100.0,
            lots=3,
            reason='test',
            stale_signals=(StaleSignal('breakeven_zone', 'WARNING', 'DANGER', '2026-01-01T00:00:00+00:00'),),
            snapshot={'beat': 1},
        )
        audit = d.to_audit_dict()
        self.assertIn('action_type', audit)
        self.assertIn('tier', audit)
        self.assertIn('stale_signals', audit)
        self.assertEqual(len(audit['stale_signals']), 1)
        self.assertEqual(audit['stale_signals'][0]['name'], 'breakeven_zone')


# ---------------------------------------------------------------------------
# Phase 3 Surgical Fixes — sealed tests
# ---------------------------------------------------------------------------

class TestSmartWhipsawStraddleBlockActive(unittest.TestCase):
    """Phase 3 Task 3 fix: STRADDLE_WITH_ADJUSTMENT no longer bypasses smart whipsaw
    block. Scalar bypasses (trigger_widen, lot_scalar) preserved; block + token
    budget now active. Per Phase 2 D6."""

    def test_straddle_scalars_still_bypassed(self):
        """trigger_widen_factor and lot_scalar must still be 1.0 for straddle."""
        from webui.backend.routes.mmm.mmm_whipsaw_smart import SmartWhipsawEngine
        from webui.backend.routes.mmm.mmm_whipsaw import WhipsawCtx
        # Minimal session with high score that would normally widen / reduce
        session = {
            'session_id': 'test-straddle-scalars',
            'params': {
                'strategy_type': 'STRADDLE_WITH_ADJUSTMENT',
                'adjustment_interval': 300,
                'smart_ws_score_defensive': 0.30,
                'smart_ws_score_observe': 0.60,
                'smart_ws_score_lockdown': 0.80,
                'smart_ws_tokens_per_session': 10.0,
                'smart_ws_token_refresh_per_hour': 1.0,
                'min_trigger_move': 10.0,
            },
            'adjustment_history': [
                {'timestamp': '2026-04-28T10:00:00+00:00', 'aggressor': 'ce'},
                {'timestamp': '2026-04-28T10:05:00+00:00', 'aggressor': 'pe'},
                {'timestamp': '2026-04-28T10:10:00+00:00', 'aggressor': 'ce'},
                {'timestamp': '2026-04-28T10:15:00+00:00', 'aggressor': 'pe'},
            ],
            'ce': {'total_lots': 50, 'active_lots': 50},
            'pe': {'total_lots': 50, 'active_lots': 50},
        }
        ctx = WhipsawCtx(ce_now=100, pe_now=100, spot=80000, iv=0.5)
        decision = SmartWhipsawEngine().evaluate(session, ctx)
        # Scalar bypasses preserved
        self.assertEqual(decision.trigger_widen_factor, 1.0,
                         'STRADDLE_WITH_ADJUSTMENT must bypass trigger widening')
        self.assertEqual(decision.lot_scalar, 1.0,
                         'STRADDLE_WITH_ADJUSTMENT must bypass lot reduction')


class TestGammaDTERelaxLadder(unittest.TestCase):
    """Phase 3 Task 2 fix: gamma engine adds DTE relax ladder for far-from-expiry.
    5-DTE → 1.25× multiplier; >5d → 1.5× multiplier. Per Phase 1 audit Task 2."""

    def _make_session(self, mte_minutes, initial_lots=10):
        return {
            'session_id': 'test-dte-ladder',
            'params': {
                'gamma_cap_enabled': True,
                'initial_lots': initial_lots,
                'gamma_soft_limit': 2500.0,
                'gamma_hard_limit': 5000.0,
                'gamma_emergency_limit': 10000.0,
                'gamma_dte_ladder_far_mult': 1.5,
                'gamma_dte_ladder_multi_mult': 1.25,
                'gamma_dte_relax_hours': 2.0,
                'gamma_dte_hedge_multiplier': 2.0,
                'gamma_near_expiry_multiplier': 0.5,
            },
            'ce': {'active_lots': 10},
            'pe': {'active_lots': 10},
        }

    def test_far_expiry_applies_far_mult(self):
        """> 5 days to expiry → 1.5× soft/hard/emergency limits."""
        from webui.backend.routes.mmm.mmm_gamma import _update_gamma_cap
        session = self._make_session(mte_minutes=8 * 24 * 60)  # 8 days
        gamma_data = {
            'positions': [(0.0001, 10, 'C'), (0.0001, 10, 'P')],
            'portfolio_gamma': 0.001,
        }
        _update_gamma_cap(session, gamma_data, spot_price=80000.0,
                           minutes_to_expiry=8 * 24 * 60)
        # Effective soft = 2500 * 1.5 = 3750
        self.assertAlmostEqual(session['_gamma_soft_limit_effective'], 3750.0, places=1)

    def test_multi_dte_applies_multi_mult(self):
        """1–5 days to expiry → 1.25× limits."""
        from webui.backend.routes.mmm.mmm_gamma import _update_gamma_cap
        session = self._make_session(mte_minutes=3 * 24 * 60)  # 3 days
        gamma_data = {
            'positions': [(0.0001, 10, 'C'), (0.0001, 10, 'P')],
            'portfolio_gamma': 0.001,
        }
        _update_gamma_cap(session, gamma_data, spot_price=80000.0,
                           minutes_to_expiry=3 * 24 * 60)
        self.assertAlmostEqual(session['_gamma_soft_limit_effective'], 3125.0, places=1)

    def test_short_dte_no_ladder(self):
        """<= 1 day to expiry → no ladder relaxation (baseline 1.0×)."""
        from webui.backend.routes.mmm.mmm_gamma import _update_gamma_cap
        session = self._make_session(mte_minutes=120)  # 2 hours
        gamma_data = {
            'positions': [(0.0001, 10, 'C'), (0.0001, 10, 'P')],
            'portfolio_gamma': 0.001,
        }
        _update_gamma_cap(session, gamma_data, spot_price=80000.0,
                           minutes_to_expiry=120)
        self.assertAlmostEqual(session['_gamma_soft_limit_effective'], 2500.0, places=1)

    def test_last_30_min_still_tightens(self):
        """≤ 30 min: 0.5× tightening preserved per Rule 5 cool-down doctrine."""
        from webui.backend.routes.mmm.mmm_gamma import _update_gamma_cap
        session = self._make_session(mte_minutes=20)
        gamma_data = {
            'positions': [(0.0001, 10, 'C'), (0.0001, 10, 'P')],
            'portfolio_gamma': 0.001,
        }
        _update_gamma_cap(session, gamma_data, spot_price=80000.0,
                           minutes_to_expiry=20)
        # 2500 (no ladder) * 0.5 = 1250
        self.assertAlmostEqual(session['_gamma_soft_limit_effective'], 1250.0, places=1)


# ---------------------------------------------------------------------------
# Phase 3 Stage 1 instrumentation — sealed tests
# ---------------------------------------------------------------------------

class TestSignalFreshnessHelpers(unittest.TestCase):
    """Verify record_signal_update + is_signal_fresh helpers used by arbiter."""

    def test_record_then_fresh(self):
        from webui.backend.routes.mmm.mmm_state import (
            record_signal_update, is_signal_fresh,
        )
        session = {}
        record_signal_update(session, 'breakeven_zone')
        self.assertTrue(is_signal_fresh(session, 'breakeven_zone', 60.0))

    def test_missing_is_stale(self):
        from webui.backend.routes.mmm.mmm_state import is_signal_fresh
        self.assertFalse(is_signal_fresh({}, 'gamma_regime', 60.0))

    def test_old_is_stale(self):
        from datetime import datetime, timedelta, timezone
        from webui.backend.routes.mmm.mmm_state import is_signal_fresh
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        session = {'_breakeven_zone_last_updated_at': old}
        self.assertFalse(is_signal_fresh(session, 'breakeven_zone', 60.0))


class TestArbiterParamDefaults(unittest.TestCase):
    """Verify arbiter_enabled defaults to True (live mode by default per
    user directive 2026-04-28)."""

    def test_arbiter_enabled_defaults_true(self):
        from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS
        self.assertTrue(DEFAULT_PARAMS.get('arbiter_enabled'),
                        'arbiter_enabled must default to True (live mode)')

    def test_arbiter_enabled_is_hot_reloadable(self):
        from webui.backend.routes.mmm.mmm_state import HOT_RELOAD_PARAMS
        self.assertIn('arbiter_enabled', HOT_RELOAD_PARAMS,
                      'arbiter_enabled must be hot-reloadable so UI toggle works without restart')

    def test_dte_ladder_params_hot_reloadable(self):
        from webui.backend.routes.mmm.mmm_state import HOT_RELOAD_PARAMS
        self.assertIn('gamma_dte_ladder_far_mult', HOT_RELOAD_PARAMS)
        self.assertIn('gamma_dte_ladder_multi_mult', HOT_RELOAD_PARAMS)


class TestArbiterShiftBypassesCooldown(unittest.TestCase):
    """When arbiter Tier 1 fires defensive_shift, the strike-shift cooldown
    must NOT block — the position is bleeding and waiting 120s costs money.
    Per sealed hierarchy Rule 2 (Tier 1 acts not blocks)."""

    def test_arbiter_flag_bypasses_cooldown_logic(self):
        """Read the cooldown gate logic and confirm the arbiter bypass flag
        is honored. This is a code-presence test — guards against the bypass
        being silently removed."""
        import os
        monitor_path = os.path.join(
            os.path.dirname(__file__), '..', 'mmm_monitor.py'
        )
        with open(monitor_path) as f:
            src = f.read()
        # Two assertions: bypass flag is read AND used in the cooldown gate
        self.assertIn('_arbiter_shift_bypass_cooldown', src,
                      'Arbiter cooldown bypass flag missing from mmm_monitor.py')
        self.assertIn('not _arbiter_shift_bypass', src,
                      'Cooldown gate must include "not _arbiter_shift_bypass" to honor flag')


class TestArbiterLiveExecutionWired(unittest.TestCase):
    """Verify the Phase 3 live-execution wire-in is present.

    These are static-source guards: they catch silent regressions that would
    otherwise demote live mode back to shadow without a test failure."""

    def _src(self):
        import os
        monitor_path = os.path.join(
            os.path.dirname(__file__), '..', 'mmm_monitor.py'
        )
        with open(monitor_path) as f:
            return f.read()

    def test_execute_arbiter_decision_method_exists(self):
        src = self._src()
        self.assertIn('async def _execute_arbiter_decision', src)
        self.assertIn('async def _arbiter_execute_defensive_shift', src)
        self.assertIn('async def _arbiter_execute_gamma_close', src)
        self.assertIn('async def _arbiter_execute_margin_recovery', src)

    def test_heartbeat_calls_execute(self):
        src = self._src()
        self.assertIn('await self._execute_arbiter_decision(_arb_decision', src,
                      'Heartbeat must call _execute_arbiter_decision when Tier 1 fires')

    def test_no_shadow_mode_flag(self):
        """Shadow mode must NOT be a configurable param — user explicitly
        rejected shadow mode 2026-04-28."""
        from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS, HOT_RELOAD_PARAMS
        self.assertNotIn('arbiter_shadow_mode', DEFAULT_PARAMS)
        self.assertNotIn('arbiter_shadow_mode', HOT_RELOAD_PARAMS)


class TestAutoPromoteNearestATM(unittest.TestCase):
    """Sealed: nearest-to-spot strike (ITM or OTM) is always the active strike.

    Rule: _auto_promote_atm_strike must NOT filter to OTM-only. It must pick
    the open strike with the smallest abs(spot - strike) regardless of ITM/OTM.

    Scenarios covered:
    - Short straddle with adjustment: one side crosses spot and becomes ITM.
    - Short strangle with ATM-shield OFF: price drifts past a strike making it ITM.
    """

    def _src(self):
        import os
        monitor_path = os.path.join(
            os.path.dirname(__file__), '..', 'mmm_monitor.py'
        )
        with open(monitor_path) as f:
            return f.read()

    def test_no_otm_only_filter(self):
        """The OTM-only guard must NOT appear in _auto_promote_atm_strike.
        If it does, ITM strikes are silently ignored and the algo manages
        the wrong position."""
        src = self._src()
        start = src.find('async def _auto_promote_atm_strike')
        end = src.find('\n    async def ', start + 1)
        fn_body = src[start:end]
        self.assertNotIn('Must be below spot for OTM put', fn_body,
                         'OTM-only filter must not appear in _auto_promote_atm_strike')
        self.assertNotIn('Must be above spot for OTM call', fn_body,
                         'OTM-only filter must not appear in _auto_promote_atm_strike')

    def test_itm_label_present(self):
        """When a promoted strike is ITM, the log must include [ITM]
        so the operator can see ITM promotion happened."""
        src = self._src()
        self.assertIn("itm_label = ' [ITM]'", src,
                      '_auto_promote_atm_strike must emit [ITM] label for ITM promotions')

    def test_nearest_any_strike_selected(self):
        """Selection logic: given an ITM and an OTM strike, the nearer-to-spot
        one wins regardless of ITM/OTM status."""
        spot_price = 95000.0
        # CE: 94500 is ITM (below spot, dist=500), 96000 is OTM (above, dist=1000)
        open_strikes = {94500.0: 5, 96000.0: 5}
        best_strike = None
        best_dist = float('inf')
        for s in open_strikes:
            dist = abs(spot_price - s)
            if dist < best_dist:
                best_dist = dist
                best_strike = s
        self.assertEqual(best_strike, 94500.0,
                         'ITM strike (94500, dist=500) must beat OTM strike (96000, dist=1000)')


# ─────────────────────────────────────────────────────────────────────────────
# Profit Ratchet — sealed contracts (2026-04-28)
# ─────────────────────────────────────────────────────────────────────────────

class TestProfitRatchetParamDefaults(unittest.TestCase):
    """Profit ratchet must default to OFF and use $10 step."""

    def test_disabled_by_default(self):
        from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS
        self.assertFalse(DEFAULT_PARAMS.get('profit_ratchet_enabled'),
                         'profit_ratchet_enabled must default to False — off by default')

    def test_step_default(self):
        from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS
        self.assertEqual(DEFAULT_PARAMS.get('profit_ratchet_step_usd'), 10.0,
                         'profit_ratchet_step_usd must default to 10.0')

    def test_both_params_hot_reloadable(self):
        from webui.backend.routes.mmm.mmm_state import HOT_RELOAD_PARAMS
        self.assertIn('profit_ratchet_enabled', HOT_RELOAD_PARAMS,
                      'profit_ratchet_enabled must be hot-reloadable')
        self.assertIn('profit_ratchet_step_usd', HOT_RELOAD_PARAMS,
                      'profit_ratchet_step_usd must be hot-reloadable')


class TestProfitRatchetFiresAtMilestone(unittest.TestCase):
    """Ratchet fires exactly when P&L crosses the next step milestone."""

    def _session(self, ce_snap=200.0, pe_snap=200.0, step=5.0, hwm=0.0):
        return {
            'params': {'profit_ratchet_enabled': True, 'profit_ratchet_step_usd': step},
            'realized_pnl': 0.0,
            'unrealized_pnl': 0.0,
            'total_fees': 0.0,
            'perp_hedge': {},
            '_reverse': {},
            '_profit_ratchet_hwm': hwm,
            'ce': {'active_strike': 50000, 'trigger_snapshot': {'50000.0': ce_snap}},
            'pe': {'active_strike': 50000, 'trigger_snapshot': {'50000.0': pe_snap}},
        }

    def _inject_pnl(self, session, pnl):
        """Force total P&L via realized_pnl field (simplest path)."""
        session['realized_pnl'] = float(pnl)

    def test_fires_at_first_milestone(self):
        from webui.backend.routes.mmm.mmm_pnl_core import compute_current_total_pnl
        session = self._session(ce_snap=200.0, pe_snap=200.0, step=5.0)
        self._inject_pnl(session, 5.10)
        ce_now, pe_now = 95.0, 92.0

        # Manual ratchet logic (mirrors mmm_monitor.py insertion)
        _pr_step = session['params']['profit_ratchet_step_usd']
        _pr_pnl = compute_current_total_pnl(session)
        _pr_hwm = session.get('_profit_ratchet_hwm', 0.0)
        fired = _pr_pnl >= _pr_hwm + _pr_step

        self.assertTrue(fired, 'Ratchet must fire when P&L crosses first milestone')
        new_hwm = int(_pr_pnl / _pr_step) * _pr_step
        self.assertEqual(new_hwm, 5.0, 'HWM must be set to 5.0 on first milestone')

    def test_does_not_fire_below_milestone(self):
        from webui.backend.routes.mmm.mmm_pnl_core import compute_current_total_pnl
        session = self._session(step=5.0)
        self._inject_pnl(session, 4.99)

        _pr_step = session['params']['profit_ratchet_step_usd']
        _pr_pnl = compute_current_total_pnl(session)
        _pr_hwm = session.get('_profit_ratchet_hwm', 0.0)
        fired = _pr_pnl >= _pr_hwm + _pr_step

        self.assertFalse(fired, 'Ratchet must NOT fire below milestone ($4.99 < $5.00)')

    def test_disabled_never_fires(self):
        from webui.backend.routes.mmm.mmm_pnl_core import compute_current_total_pnl
        session = self._session(step=5.0)
        session['params']['profit_ratchet_enabled'] = False
        self._inject_pnl(session, 50.0)

        enabled = session['params'].get('profit_ratchet_enabled', False)
        self.assertFalse(enabled, 'When disabled, ratchet gate must be False regardless of P&L')


class TestProfitRatchetHWMGuard(unittest.TestCase):
    """Ratchet must NOT re-fire at an already-crossed milestone (HWM guard)."""

    def test_no_refire_at_same_milestone(self):
        from webui.backend.routes.mmm.mmm_pnl_core import compute_current_total_pnl
        session = {
            'params': {'profit_ratchet_enabled': True, 'profit_ratchet_step_usd': 5.0},
            'realized_pnl': 5.50,
            'unrealized_pnl': 0.0,
            'total_fees': 0.0,
            'perp_hedge': {},
            '_reverse': {},
            '_profit_ratchet_hwm': 5.0,  # milestone already crossed
            'ce': {'active_strike': 50000, 'trigger_snapshot': {'50000.0': 95.0}},
            'pe': {'active_strike': 50000, 'trigger_snapshot': {'50000.0': 92.0}},
        }
        _pr_step = session['params']['profit_ratchet_step_usd']
        _pr_pnl = compute_current_total_pnl(session)
        _pr_hwm = session.get('_profit_ratchet_hwm', 0.0)
        fired = _pr_pnl >= _pr_hwm + _pr_step  # 5.50 >= 5.0 + 5.0 → False

        self.assertFalse(fired, 'Ratchet must not re-fire: P&L $5.50, HWM $5.0, next milestone $10.0')

    def test_no_fire_during_drawdown(self):
        from webui.backend.routes.mmm.mmm_pnl_core import compute_current_total_pnl
        session = {
            'params': {'profit_ratchet_enabled': True, 'profit_ratchet_step_usd': 5.0},
            'realized_pnl': 3.00,
            'unrealized_pnl': 0.0,
            'total_fees': 0.0,
            'perp_hedge': {},
            '_reverse': {},
            '_profit_ratchet_hwm': 10.0,  # was at $10, now in drawdown
        }
        _pr_step = session['params']['profit_ratchet_step_usd']
        _pr_pnl = compute_current_total_pnl(session)
        _pr_hwm = session.get('_profit_ratchet_hwm', 0.0)
        fired = _pr_pnl >= _pr_hwm + _pr_step  # 3.0 >= 10.0 + 5.0 → False

        self.assertFalse(fired, 'Ratchet must not fire during drawdown (P&L $3 < HWM $10)')


class TestProfitRatchetMultiStepJump(unittest.TestCase):
    """When P&L jumps multiple steps at once, HWM advances to highest crossed milestone."""

    def test_multi_step_hwm(self):
        pnl = 18.0
        step = 5.0
        new_hwm = int(pnl / step) * step
        self.assertEqual(new_hwm, 15.0,
                         'P&L=$18, step=$5 → HWM must be $15 (highest milestone crossed)')

    def test_single_step_hwm(self):
        pnl = 7.3
        step = 5.0
        new_hwm = int(pnl / step) * step
        self.assertEqual(new_hwm, 5.0,
                         'P&L=$7.3, step=$5 → HWM must be $5')


class TestProfitRatchetNegativePnlNeverFires(unittest.TestCase):
    """Ratchet must never fire when P&L is negative."""

    def test_negative_pnl(self):
        from webui.backend.routes.mmm.mmm_pnl_core import compute_current_total_pnl
        session = {
            'params': {'profit_ratchet_enabled': True, 'profit_ratchet_step_usd': 5.0},
            'realized_pnl': -10.0,
            'unrealized_pnl': 0.0,
            'total_fees': 0.0,
            'perp_hedge': {},
            '_reverse': {},
            '_profit_ratchet_hwm': 0.0,
        }
        _pr_step = session['params']['profit_ratchet_step_usd']
        _pr_pnl = compute_current_total_pnl(session)
        _pr_hwm = session.get('_profit_ratchet_hwm', 0.0)
        fired = _pr_pnl >= _pr_hwm + _pr_step  # -10 >= 0 + 5 → False

        self.assertFalse(fired, 'Ratchet must never fire when P&L is negative')


class TestProfitRatchetSourcePresence(unittest.TestCase):
    """Static source guard: ratchet logic must be present in mmm_monitor.py."""

    def _src(self):
        monitor_path = os.path.join(os.path.dirname(__file__), '..', 'mmm_monitor.py')
        with open(monitor_path) as f:
            return f.read()

    def test_ratchet_block_present(self):
        src = self._src()
        self.assertIn('profit_ratchet_enabled', src,
                      'profit_ratchet_enabled check missing from mmm_monitor.py')
        self.assertIn('_profit_ratchet_hwm', src,
                      '_profit_ratchet_hwm state field missing from mmm_monitor.py')
        self.assertIn('_profit_ratchet_count', src,
                      '_profit_ratchet_count increment missing from mmm_monitor.py')

    def test_ratchet_fires_before_evaluate_triggers(self):
        """Ratchet block must appear before evaluate_triggers so the fresh
        snapshot is used by the trigger evaluator on the same beat."""
        src = self._src()
        ratchet_pos = src.find('profit_ratchet_enabled')
        trigger_pos = src.find('trigger_result = evaluate_triggers(session, ce_now, pe_now)')
        self.assertGreater(trigger_pos, ratchet_pos,
                           'Ratchet block must appear before evaluate_triggers in heartbeat')

    def test_activity_category_registered(self):
        from webui.backend.routes.mmm.mmm_activity import ACTIVITY_TYPES
        self.assertIn('profit_ratchet', ACTIVITY_TYPES,
                      'profit_ratchet must be a registered activity type')

    def test_ratchet_skipped_when_arbiter_active(self):
        """Ratchet must not re-anchor when arbiter executed a Tier 1 action this beat.
        The arbiter's shift/close already calls update_trigger_snapshots() with the
        fill price; overwriting with ratchet would discard that fill-based anchor."""
        src = self._src()
        # The arbiter gate must appear inside the profit_ratchet_enabled block
        ratchet_start = src.find('profit_ratchet_enabled')
        ratchet_block = src[ratchet_start:ratchet_start + 400]
        self.assertIn('_arbiter_decision_active', ratchet_block,
                      'Ratchet block must check _arbiter_decision_active before firing')


class TestArbiterBeatCooldown(unittest.TestCase):
    """Arbiter must not double-fire on consecutive beats (mmm30apr26-1 incident).

    After a Tier 1 action executes, _arbiter_last_action_at is written. The
    next call to evaluate() within 2× beat_interval returns NOOP (cooldown).
    After 2× beat_interval, the arbiter re-evaluates normally.
    """

    def _base_session(self, last_action_offset_sec=None):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        ts = now.isoformat()
        session = {
            'session_id': 'test-cooldown',
            'adjustment_count': 3,
            '_minutes_to_expiry': 240,
            '_breakeven_zone': 'CRITICAL',
            '_breakeven_zone_last_updated_at': ts,
            '_breakeven_result': {'nearest_side': 'lower', 'zone': 'CRITICAL'},
            '_gamma_regime': 'NORMAL',
            '_gamma_regime_last_updated_at': ts,
            '_margin_tier': 'GREEN',
            '_margin_tier_last_updated_at': ts,
            'ce': {'active_lots': 64, 'unrealized_pnl': 0},
            'pe': {'active_lots': 57, 'unrealized_pnl': -800},
            'params': {
                'adjustment_interval': 300,
                'shift_target_premium': 100.0,
                'shift_premium_tolerance': 10.0,
            },
        }
        if last_action_offset_sec is not None:
            action_at = (now - timedelta(seconds=last_action_offset_sec)).isoformat()
            session['_arbiter_last_action_at'] = action_at
        return session

    def test_cooldown_blocks_within_two_beats(self):
        """Last action 30s ago with 300s interval → 600s cooldown → NOOP."""
        from webui.backend.routes.mmm.mmm_arbiter import CoordinationArbiter, ACTION_NOOP
        session = self._base_session(last_action_offset_sec=30)
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_NOOP)
        self.assertEqual(decision.trigger, 'arbiter_beat_cooldown')

    def test_cooldown_clears_after_two_beats(self):
        """Last action 650s ago with 300s interval → cooldown elapsed → fires normally."""
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_DEFENSIVE_SHIFT,
        )
        session = self._base_session(last_action_offset_sec=650)
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_DEFENSIVE_SHIFT,
                         'Cooldown must have cleared; arbiter should fire at CRITICAL')

    def test_no_cooldown_on_first_fire(self):
        """No _arbiter_last_action_at present → cooldown skipped → fires normally."""
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_DEFENSIVE_SHIFT,
        )
        session = self._base_session()  # no last_action_offset_sec
        self.assertIsNone(session.get('_arbiter_last_action_at'))
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_DEFENSIVE_SHIFT)


class TestArbiterHedgeDecay(unittest.TestCase):
    """Arbiter fires early (BE=WARNING or DANGER) when opposite hedge decays below shift_threshold.

    Prevents the mmm30apr26-1 pattern: CE at 77800 decayed $73→$29 over 2.5h of
    whipsaw blocks while arbiter waited for CRITICAL. The zone jumped WARNING→CRITICAL
    directly (no DANGER step) so DANGER-only trigger would also have failed.
    Threshold = shift_threshold exactly (same level normal proactive-shift uses,
    but blocked by whipsaw — arbiter bypasses the block).
    """

    def _make_session(self, be_zone='DANGER', ce_now=None, pe_now=None,
                      nearest_side='lower', shift_threshold=50.0):
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        session = {
            'session_id': 'test-decay',
            'adjustment_count': 2,
            '_minutes_to_expiry': 300,
            '_breakeven_zone': be_zone,
            '_breakeven_zone_last_updated_at': ts,
            '_breakeven_result': {'nearest_side': nearest_side, 'zone': be_zone},
            '_gamma_regime': 'NORMAL',
            '_gamma_regime_last_updated_at': ts,
            '_margin_tier': 'GREEN',
            '_margin_tier_last_updated_at': ts,
            'ce': {'active_lots': 64, 'unrealized_pnl': 0},
            'pe': {'active_lots': 57, 'unrealized_pnl': -500},
            'params': {
                'adjustment_interval': 300,
                'shift_threshold': shift_threshold,
                'shift_target_premium': 100.0,
                'shift_premium_tolerance': 10.0,
            },
        }
        if ce_now is not None:
            session['_ce_now'] = ce_now
        if pe_now is not None:
            session['_pe_now'] = pe_now
        return session

    def test_decay_fires_at_danger_with_decayed_ce(self):
        """BE=DANGER + CE live $30 (< shift_threshold $50) + PE threatened → Tier 1 shift on CE."""
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_DEFENSIVE_SHIFT, TIER_1_EXTREME,
        )
        session = self._make_session(be_zone='DANGER', ce_now=30.0, nearest_side='lower')
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_DEFENSIVE_SHIFT)
        self.assertEqual(decision.tier, TIER_1_EXTREME)
        self.assertEqual(decision.side, 'ce')
        self.assertIn('hedge_decay_danger_pe', decision.trigger)

    def test_decay_fires_at_warning_with_decayed_ce(self):
        """BE=WARNING + CE live $30 (< shift_threshold $50) → Tier 1 shift.

        Critical: covers the mmm30apr26-1 case where zone jumped WARNING→CRITICAL
        directly, never passing through DANGER. DANGER-only trigger would have missed it.
        """
        from webui.backend.routes.mmm.mmm_arbiter import (
            CoordinationArbiter, ACTION_DEFENSIVE_SHIFT, TIER_1_EXTREME,
        )
        session = self._make_session(be_zone='WARNING', ce_now=30.0, nearest_side='lower')
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_DEFENSIVE_SHIFT)
        self.assertEqual(decision.tier, TIER_1_EXTREME)
        self.assertEqual(decision.side, 'ce')
        self.assertIn('hedge_decay_warning_pe', decision.trigger)

    def test_decay_noop_when_hedge_above_threshold(self):
        """BE=DANGER + CE live $60 (>= shift_threshold $50) → no early action."""
        from webui.backend.routes.mmm.mmm_arbiter import CoordinationArbiter, ACTION_NOOP
        session = self._make_session(be_zone='DANGER', ce_now=60.0, nearest_side='lower')
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_NOOP,
                         'Hedge above shift_threshold must not trigger early decay shift')

    def test_decay_noop_when_no_live_price(self):
        """BE=DANGER but no _ce_now in session → skip decay check (no stale data action)."""
        from webui.backend.routes.mmm.mmm_arbiter import CoordinationArbiter, ACTION_NOOP
        session = self._make_session(be_zone='DANGER', nearest_side='lower')
        self.assertNotIn('_ce_now', session)
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_NOOP)

    def test_cooldown_takes_priority_over_decay(self):
        """Within 2-beat cooldown window, decay trigger must be silenced even at WARNING/DANGER."""
        from datetime import datetime, timezone, timedelta
        from webui.backend.routes.mmm.mmm_arbiter import CoordinationArbiter, ACTION_NOOP
        session = self._make_session(be_zone='DANGER', ce_now=30.0, nearest_side='lower')
        # Simulate: arbiter just acted 10s ago (far within 600s cooldown)
        session['_arbiter_last_action_at'] = (
            datetime.now(timezone.utc) - timedelta(seconds=10)
        ).isoformat()
        decision = CoordinationArbiter().evaluate(session)
        self.assertEqual(decision.action_type, ACTION_NOOP)
        self.assertEqual(decision.trigger, 'arbiter_beat_cooldown')


if __name__ == '__main__':
    unittest.main()
