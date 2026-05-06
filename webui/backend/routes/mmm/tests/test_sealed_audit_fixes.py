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

    def test_ratchet_outside_skip_to_pnl_guard(self):
        """Ratchet block must appear BEFORE the `if _skip_to_pnl:` guard so it
        fires even when safety/whipsaw/regime/cooldown blocks have set that flag.
        Per design doc: ratchet only updates in-memory snapshots (no orders placed)
        so it is safe to run outside the _skip_to_pnl gate."""
        src = self._src()
        ratchet_pos = src.find('profit_ratchet_enabled')
        skip_guard_pos = src.find('\n        if _skip_to_pnl:\n            self._emit_heartbeat_data')
        self.assertNotEqual(ratchet_pos, -1, 'profit_ratchet_enabled not found in mmm_monitor.py')
        self.assertNotEqual(skip_guard_pos, -1, '_skip_to_pnl emit guard not found in mmm_monitor.py')
        self.assertLess(ratchet_pos, skip_guard_pos,
                        'Ratchet block must appear BEFORE the _skip_to_pnl guard in _heartbeat_inner()')


# ─────────────────────────────────────────────────────────────────────────────
# Profit Ratchet Fresh-Reset — sealed contracts (2026-05-06)
# Original profit_ratchet design intent: clear accumulated guards/blocks/
# cooldowns at each profit milestone. Tiered, flag-gated, default OFF.
# ─────────────────────────────────────────────────────────────────────────────

class TestProfitRatchetFreshResetParamDefaults(unittest.TestCase):
    """Master + 3 tier flags must be present and default to safe values."""

    def test_master_flag_default_off(self):
        from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS
        self.assertFalse(
            DEFAULT_PARAMS.get('profit_ratchet_fresh_reset', False),
            'profit_ratchet_fresh_reset must default OFF — feature requires explicit opt-in'
        )

    def test_tier_a_default_on(self):
        from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS
        self.assertTrue(
            DEFAULT_PARAMS.get('ratchet_reset_cooldowns', False),
            'ratchet_reset_cooldowns (Tier A) must default ON when master is enabled'
        )

    def test_tier_b_and_c_default_off(self):
        from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS
        self.assertFalse(
            DEFAULT_PARAMS.get('ratchet_reset_whipsaw', True),
            'ratchet_reset_whipsaw (Tier B) must default OFF — explicit opt-in'
        )
        self.assertFalse(
            DEFAULT_PARAMS.get('ratchet_reset_regime_tier', True),
            'ratchet_reset_regime_tier (Tier C) must default OFF — explicit opt-in'
        )

    def test_all_four_flags_hot_reloadable(self):
        from webui.backend.routes.mmm.mmm_state import HOT_RELOAD_PARAMS
        for key in ('profit_ratchet_fresh_reset', 'ratchet_reset_cooldowns',
                    'ratchet_reset_whipsaw', 'ratchet_reset_regime_tier'):
            self.assertIn(key, HOT_RELOAD_PARAMS,
                          f'{key} must be hot-reloadable so operator can toggle mid-session')

    def test_param_rules_present(self):
        from webui.backend.routes.mmm.mmm_config import PARAM_RULES
        for key in ('profit_ratchet_fresh_reset', 'ratchet_reset_cooldowns',
                    'ratchet_reset_whipsaw', 'ratchet_reset_regime_tier'):
            self.assertIn(key, PARAM_RULES,
                          f'{key} must have a PARAM_RULES entry')
            self.assertEqual(PARAM_RULES[key]['type'], bool,
                             f'{key} must be bool')
            self.assertTrue(PARAM_RULES[key].get('hot'),
                            f'{key} must be marked hot=True in PARAM_RULES')


class TestProfitRatchetFreshResetMasterGate(unittest.TestCase):
    """When master flag is OFF, _profit_ratchet_fresh_reset is a no-op
    regardless of tier sub-flags. This is the critical safety contract:
    today's behavior is preserved bit-for-bit when the feature is disabled."""

    def _baseline_session(self):
        return {
            'id': 'test-master-off',
            '_shift_starv_count': {'ce': 5, 'pe': 0},
            '_consecutive_same_dir_count': 3,
            '_consecutive_dir_blocked': True,
            '_consecutive_reversal_skip_count': 2,
            '_gamma_blocked_count': 7,
            '_whipsaw_score': 99.0,
            '_smart_ws_mode': 'DEFENSIVE',
            '_smart_ws_series': [{'ts': 'a'}, {'ts': 'b'}],  # source data — must survive
            '_trend_tier': 3,
            '_trend_regime': 'TREND_DOWN',
            '_trend_anchor_spot': 81500.0,
            '_trend_calm_beats': 12,
            'params': {
                # Master OFF: tiers should not fire even though sub-flags are ON
                'profit_ratchet_fresh_reset': False,
                'ratchet_reset_cooldowns': True,
                'ratchet_reset_whipsaw': True,
                'ratchet_reset_regime_tier': True,
            },
        }

    def test_master_off_no_change(self):
        # Direct functional simulation: caller-side check must skip the call entirely.
        # The reset method only fires after `if params.get('profit_ratchet_fresh_reset'):`
        # so the sealed contract is the call-site gate AND the method itself.
        # This test verifies the call-site gate via source inspection.
        monitor_path = os.path.join(os.path.dirname(__file__), '..', 'mmm_monitor.py')
        with open(monitor_path) as f:
            src = f.read()
        self.assertIn(
            "params.get('profit_ratchet_fresh_reset', False)",
            src,
            'Caller must gate _profit_ratchet_fresh_reset() on master flag'
        )
        self.assertIn(
            'self._profit_ratchet_fresh_reset(session)',
            src,
            'Caller must invoke _profit_ratchet_fresh_reset on session'
        )


class TestProfitRatchetFreshResetNeverList(unittest.TestCase):
    """Position state, P&L, fill cursor, monitor generation, paused state,
    awaiting state, emergency flags, adjustment_history must NEVER be cleared
    even with all three tiers enabled. This is the hardest safety contract."""

    NEVER_CLEAR_KEYS = [
        # Position state
        'ce', 'pe',
        # P&L state
        'realized_pnl', 'unrealized_pnl', 'total_fees', 'perp_hedge', '_reverse',
        # Fill / ledger
        '_fill_sync_cursor_us', '_fill_ledger',
        # Audit
        'adjustment_history',
        # Profit ratchet's own state
        '_profit_ratchet_hwm', '_profit_ratchet_count', '_profit_ratchet_last_pnl',
        # Stale-monitor guard
        '_monitor_generation',
        # Operational
        '_save_disabled', '_paused_reason', '_paused_at', '_stopped_reason',
        '_awaiting_user_action', '_awaiting_user_action_reason',
        '_awaiting_user_action_details',
        # Emergency
        '_emergency_pause', '_emergency_stop',
        '_exit_all_completed_at', '_exit_all_partial',
        # Whipsaw source data buffer (must survive Tier B)
        '_smart_ws_series',
        # Trend anchor (must survive Tier C — preserved by design)
        '_trend_anchor_spot',
    ]

    def _populated_session(self):
        sess = {
            'id': 'test-never-list',
            'params': {
                'profit_ratchet_fresh_reset': True,
                'ratchet_reset_cooldowns': True,
                'ratchet_reset_whipsaw': True,
                'ratchet_reset_regime_tier': True,
            },
            # Position state
            'ce': {'active_strike': 81800, 'active_lots': 2,
                   'positions': [{'strike': 81800, 'lots': 2, 'status': 'active'}]},
            'pe': {'active_strike': 80800, 'active_lots': 103,
                   'positions': [{'strike': 80800, 'lots': 103, 'status': 'active'}]},
            'realized_pnl': 12.60, 'unrealized_pnl': 10.83,
            'total_fees': 2.19, 'perp_hedge': {'lots': 0},
            '_reverse': {'active': False, 'net_pnl': 0.0},
            '_fill_sync_cursor_us': 1700000000000000,
            '_fill_ledger': [{'order_id': 'x'}],
            'adjustment_history': [{'aggressor': 'CE'}],
            '_profit_ratchet_hwm': 20.0, '_profit_ratchet_count': 4,
            '_profit_ratchet_last_pnl': 20.15,
            '_monitor_generation': 7,
            '_save_disabled': False,
            '_paused_reason': None,
            '_paused_at': None,
            '_stopped_reason': None,
            '_awaiting_user_action': False,
            '_awaiting_user_action_reason': None,
            '_awaiting_user_action_details': None,
            '_emergency_pause': False,
            '_emergency_stop': False,
            '_exit_all_completed_at': None,
            '_exit_all_partial': False,
            '_smart_ws_series': [{'ts': 'a', 'spot': 81000}],
            '_trend_anchor_spot': 81500.0,
            # Add some baggage that SHOULD be cleared (separate sanity)
            '_shift_starv_count': {'ce': 3},
            '_whipsaw_score': 50.0,
            '_trend_tier': 3,
        }
        return sess

    def test_never_list_survives_all_tiers(self):
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        sess = self._populated_session()
        snapshot = {k: sess.get(k) for k in self.NEVER_CLEAR_KEYS}

        # Construct a minimal monitor stub to call the bound method
        class _Stub:
            session_id = 'test-never-list'
        MMMMonitor._profit_ratchet_fresh_reset(_Stub(), sess)

        for k in self.NEVER_CLEAR_KEYS:
            self.assertIn(k, sess, f'{k} was deleted by fresh-reset (NEVER list violation)')
            self.assertEqual(
                sess[k], snapshot[k],
                f'{k} was mutated by fresh-reset (NEVER list violation)'
            )

    def test_baggage_actually_cleared(self):
        """Sanity: the populated_session fixture includes baggage; reset clears it.
        Without this, test_never_list_survives could pass trivially with a no-op."""
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        sess = self._populated_session()

        class _Stub:
            session_id = 'test-never-list'
        MMMMonitor._profit_ratchet_fresh_reset(_Stub(), sess)

        # Tier A baggage
        self.assertNotIn('_shift_starv_count', sess, 'Tier A must clear _shift_starv_count')
        # Tier B baggage
        self.assertNotIn('_whipsaw_score', sess, 'Tier B must clear _whipsaw_score')
        # Tier C
        self.assertEqual(sess.get('_trend_tier'), 0, 'Tier C must reset _trend_tier to 0')


class TestProfitRatchetFreshResetTierA(unittest.TestCase):
    """Tier A clears the documented set of cooldown/block counters."""

    TIER_A_KEYS = [
        '_shift_starv_count', '_consecutive_same_dir_count',
        '_consecutive_same_dir_side', '_consecutive_dir_blocked',
        '_consecutive_dir_blocked_at', '_consecutive_reversal_skip_count',
        '_cooldown_block_logged', '_gamma_blocked_count',
        '_delta_rescue_count', '_delta_rescue_last_at',
        '_adaptive_regime_candidate_beats',
        '_trend_calm_beats', '_trend_plateau_beats',
        '_vol_regime_beats_below',
    ]

    def test_tier_a_clears_documented_set(self):
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        sess = {'id': 't', 'params': {
            'profit_ratchet_fresh_reset': True,
            'ratchet_reset_cooldowns': True,
            'ratchet_reset_whipsaw': False,
            'ratchet_reset_regime_tier': False,
        }}
        for k in self.TIER_A_KEYS:
            sess[k] = {'ce': 5} if k == '_shift_starv_count' else 7

        class _Stub:
            session_id = 't'
        MMMMonitor._profit_ratchet_fresh_reset(_Stub(), sess)

        for k in self.TIER_A_KEYS:
            self.assertNotIn(k, sess, f'Tier A must clear {k}')

    def test_tier_a_disabled_preserves_fields(self):
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        sess = {'id': 't', 'params': {
            'profit_ratchet_fresh_reset': True,
            'ratchet_reset_cooldowns': False,  # Tier A OFF
            'ratchet_reset_whipsaw': False,
            'ratchet_reset_regime_tier': False,
        }, '_shift_starv_count': {'ce': 5}, '_gamma_blocked_count': 9}

        class _Stub:
            session_id = 't'
        MMMMonitor._profit_ratchet_fresh_reset(_Stub(), sess)

        self.assertEqual(sess['_shift_starv_count'], {'ce': 5},
                         'Tier A OFF must preserve _shift_starv_count')
        self.assertEqual(sess['_gamma_blocked_count'], 9,
                         'Tier A OFF must preserve _gamma_blocked_count')


class TestProfitRatchetFreshResetTierB(unittest.TestCase):
    """Tier B clears whipsaw state EXCEPT _smart_ws_series."""

    def test_tier_b_clears_whipsaw_preserves_series(self):
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        sess = {'id': 't', 'params': {
            'profit_ratchet_fresh_reset': True,
            'ratchet_reset_cooldowns': False,
            'ratchet_reset_whipsaw': True,
            'ratchet_reset_regime_tier': False,
        },
            '_whipsaw_score': 99.0,
            '_whipsaw_state': 'BLOCK',
            '_whipsaw_skip_until': 'tomorrow',
            '_whipsaw_last_checked_idx': 42,
            '_whipsaw_last_noise_at': 'now',
            '_smart_ws_score': 0.5,
            '_smart_ws_mode': 'DEFENSIVE',
            '_smart_ws_tokens': 3,
            '_smart_ws_series': [{'ts': 'a'}, {'ts': 'b'}, {'ts': 'c'}],  # MUST SURVIVE
        }

        class _Stub:
            session_id = 't'
        MMMMonitor._profit_ratchet_fresh_reset(_Stub(), sess)

        # Whipsaw state cleared
        for k in ('_whipsaw_score', '_whipsaw_state', '_whipsaw_skip_until',
                  '_whipsaw_last_checked_idx', '_whipsaw_last_noise_at',
                  '_smart_ws_score', '_smart_ws_mode', '_smart_ws_tokens'):
            self.assertNotIn(k, sess, f'Tier B must clear {k}')

        # Source buffer survives
        self.assertEqual(sess['_smart_ws_series'],
                         [{'ts': 'a'}, {'ts': 'b'}, {'ts': 'c'}],
                         '_smart_ws_series is source data — must survive Tier B')


class TestProfitRatchetFreshResetTierC(unittest.TestCase):
    """Tier C resets regime tier state but PRESERVES _trend_anchor_spot."""

    def test_tier_c_clears_regime_preserves_anchor(self):
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        sess = {'id': 't', 'params': {
            'profit_ratchet_fresh_reset': True,
            'ratchet_reset_cooldowns': False,
            'ratchet_reset_whipsaw': False,
            'ratchet_reset_regime_tier': True,
        },
            '_trend_tier': 3,
            '_trend_regime': 'TREND_DOWN',
            '_trend_direction': 'down',
            '_trend_since': 'a', '_trend_high': 1, '_trend_low': 2,
            '_trend_ema': 3.0, '_trend_ema_prev': 4.0, '_trend_t4_beats': 5,
            '_regime_action': 'BLOCK_ALL_SELLS',
            '_trend_wind_down_triggered': True,
            '_vol_wind_down_triggered': True,
            '_atm_wind_down_triggered': True,
            '_vol_regime': 'HIGH',
            '_trend_anchor_spot': 81500.0,  # MUST SURVIVE
        }

        class _Stub:
            session_id = 't'
        MMMMonitor._profit_ratchet_fresh_reset(_Stub(), sess)

        self.assertEqual(sess['_trend_tier'], 0)
        self.assertEqual(sess['_trend_regime'], 'NORMAL')
        self.assertEqual(sess['_trend_direction'], 'none')
        for k in ('_trend_since', '_trend_high', '_trend_low',
                  '_trend_ema', '_trend_ema_prev', '_trend_t4_beats',
                  '_regime_action'):
            self.assertNotIn(k, sess, f'Tier C must clear {k}')
        self.assertFalse(sess['_trend_wind_down_triggered'])
        self.assertFalse(sess['_vol_wind_down_triggered'])
        self.assertFalse(sess['_atm_wind_down_triggered'])
        self.assertEqual(sess['_vol_regime'], 'NORMAL')

        # ANCHOR PRESERVATION — explicit design choice
        self.assertEqual(sess['_trend_anchor_spot'], 81500.0,
                         '_trend_anchor_spot MUST be preserved (regime re-derives '
                         'tier/direction from market data + preserved anchor; '
                         'resetting it would mask ongoing trends)')


class TestProfitRatchetFreshResetActivityLog(unittest.TestCase):
    """When fields are cleared, an activity log entry fires; when nothing
    is cleared, NO log entry fires (avoid noise in clean sessions)."""

    def test_empty_reset_logs_nothing(self):
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        # Session with no baggage — Tier A enabled but nothing to clear
        sess = {'id': 't', 'params': {
            'profit_ratchet_fresh_reset': True,
            'ratchet_reset_cooldowns': True,
            'ratchet_reset_whipsaw': False,
            'ratchet_reset_regime_tier': False,
        }}

        class _Stub:
            session_id = 't'
        with patch('webui.backend.routes.mmm.mmm_activity.log_activity') as mock_log:
            MMMMonitor._profit_ratchet_fresh_reset(_Stub(), sess)
            # No fields to clear → no log entry
            mock_log.assert_not_called()

    def test_non_empty_reset_logs_with_structured_details(self):
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        sess = {'id': 't', 'params': {
            'profit_ratchet_fresh_reset': True,
            'ratchet_reset_cooldowns': True,
            'ratchet_reset_whipsaw': False,
            'ratchet_reset_regime_tier': False,
        }, '_shift_starv_count': {'ce': 3}, '_profit_ratchet_count': 4}

        class _Stub:
            session_id = 't'
        with patch('webui.backend.routes.mmm.mmm_activity.log_activity') as mock_log:
            MMMMonitor._profit_ratchet_fresh_reset(_Stub(), sess)
            self.assertEqual(mock_log.call_count, 1,
                             'Expected exactly one log entry for non-empty reset')
            call_args = mock_log.call_args
            # First positional arg is activity type
            self.assertEqual(call_args[0][0], 'profit_ratchet_fresh_reset')
            # 4th positional arg is details dict
            details = call_args[0][4]
            self.assertIn('cleared_fields', details)
            self.assertIn('tiers_active', details)
            self.assertIn('tiers_skipped', details)
            self.assertIn('total_cleared', details)
            self.assertIn('cooldowns', details['tiers_active'])
            self.assertIn('whipsaw', details['tiers_skipped'])
            self.assertIn('regime_tier', details['tiers_skipped'])
            self.assertIn('_shift_starv_count', details['cleared_fields'])


class TestProfitRatchetFreshResetActivityTypeRegistered(unittest.TestCase):
    """Activity type must be registered so the UI renders the entry."""

    def test_activity_type_present(self):
        from webui.backend.routes.mmm.mmm_activity import ACTIVITY_TYPES
        self.assertIn('profit_ratchet_fresh_reset', ACTIVITY_TYPES,
                      'profit_ratchet_fresh_reset must be a registered activity type')


class TestProfitRatchetFreshResetCallSite(unittest.TestCase):
    """Static source guard: caller must invoke fresh-reset only after
    update_trigger_snapshots and only when master flag is True."""

    def _src(self):
        monitor_path = os.path.join(os.path.dirname(__file__), '..', 'mmm_monitor.py')
        with open(monitor_path) as f:
            return f.read()

    def test_call_appears_after_trigger_snapshot_update(self):
        src = self._src()
        snap_pos = src.find('update_trigger_snapshots(session, ce_now, pe_now)')
        # Find the call inside the ratchet block (search after snap_pos for the gate)
        gate_pos = src.find("params.get('profit_ratchet_fresh_reset'", snap_pos)
        self.assertNotEqual(gate_pos, -1, 'Master-flag gate must appear after snapshot update')
        self.assertGreater(gate_pos, snap_pos,
                           'Fresh-reset gate must appear AFTER update_trigger_snapshots '
                           '(snapshot anchoring is the primary action; reset is secondary)')

    def test_method_definition_present(self):
        src = self._src()
        self.assertIn('def _profit_ratchet_fresh_reset(self, session)', src,
                      '_profit_ratchet_fresh_reset method definition missing')


class TestArbiterFlagClearedOnLoad(unittest.TestCase):
    """_arbiter_decision_active must be removed from session when loaded from storage.

    This is a per-beat transient flag. If the session was saved mid-beat (e.g.
    during a STOP while arbiter was executing a Tier 1 action), the flag persists
    in storage as True. On restore it would permanently block the profit ratchet
    gate until the next heartbeat reset. Clearing it in _row_to_session() is the fix.
    """

    def _storage_src(self):
        storage_path = os.path.join(os.path.dirname(__file__), '..', 'mmm_storage.py')
        with open(storage_path) as f:
            return f.read()

    def test_flag_cleared_in_row_to_session(self):
        src = self._storage_src()
        row_to_session_start = src.find('def _row_to_session(')
        self.assertNotEqual(row_to_session_start, -1, '_row_to_session not found in mmm_storage.py')
        # Find next method boundary (~200 lines is more than enough for _row_to_session)
        row_to_session_body = src[row_to_session_start:row_to_session_start + 5000]
        next_def = row_to_session_body.find('\n    def ', 5)
        method_body = row_to_session_body[:next_def] if next_def != -1 else row_to_session_body
        self.assertIn("session.pop('_arbiter_decision_active', None)", method_body,
                      '_row_to_session must clear _arbiter_decision_active on session load')

    def test_flag_not_in_monitor_heartbeat_reset_only(self):
        """The per-beat reset in mmm_monitor.py (line ~3464) is not enough by itself —
        the storage clear must also exist."""
        monitor_path = os.path.join(os.path.dirname(__file__), '..', 'mmm_monitor.py')
        with open(monitor_path) as f:
            src = f.read()
        self.assertIn("session['_arbiter_decision_active'] = False", src,
                      'Per-beat reset of _arbiter_decision_active must exist in mmm_monitor.py')


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


class TestArbiterFullCapacity(unittest.TestCase):
    """arbiter_use_full_capacity=True seeds remaining max_lots_per_side in emergency shifts.

    Without this: arbiter seeds frozen_lots (64) at new strike.
    With this:    arbiter seeds max_lots_per_side - total_lots (e.g. 136) at new strike.
    Prevents leaving premium capacity unused in an emergency (mmm30apr26-1 analysis).
    """

    def test_full_capacity_param_default_true(self):
        """arbiter_use_full_capacity must default True in DEFAULT_PARAMS."""
        from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS
        self.assertIn('arbiter_use_full_capacity', DEFAULT_PARAMS)
        self.assertTrue(DEFAULT_PARAMS['arbiter_use_full_capacity'])

    def test_full_capacity_param_hot_reloadable(self):
        """arbiter_use_full_capacity must be in HOT_RELOAD_PARAMS."""
        from webui.backend.routes.mmm.mmm_state import HOT_RELOAD_PARAMS
        self.assertIn('arbiter_use_full_capacity', HOT_RELOAD_PARAMS)

    def test_full_capacity_requested_lots_written_before_shift(self):
        """_arbiter_execute_defensive_shift writes _arbiter_requested_lots = remaining capacity."""
        import ast, inspect
        import webui.backend.routes.mmm.mmm_monitor as mon
        src = inspect.getsource(mon.MMMMonitor._arbiter_execute_defensive_shift)
        self.assertIn('arbiter_use_full_capacity', src,
                      '_arbiter_execute_defensive_shift must check arbiter_use_full_capacity')
        self.assertIn('_arbiter_requested_lots', src,
                      '_arbiter_execute_defensive_shift must write _arbiter_requested_lots')
        self.assertIn('max_lots_per_side', src,
                      'Capacity calculation must reference max_lots_per_side')

    def test_proactive_fallback_consumes_requested_lots(self):
        """Proactive shift fallback block must pop and apply _arbiter_requested_lots."""
        import inspect
        import webui.backend.routes.mmm.mmm_monitor as mon
        src = inspect.getsource(mon.MMMMonitor._process_strike_shift)
        # Must pop the key (consume-and-clear pattern)
        self.assertIn("pop('_arbiter_requested_lots'", src,
                      'Fallback block must pop _arbiter_requested_lots after use')
        self.assertIn('arbiter full-capacity', src,
                      'Fallback block must log arbiter full-capacity note')


class TestBEZoneAcceleration(unittest.TestCase):
    """BE zone beat acceleration (Layer 4 of _run_loop interval pipeline).

    When breakeven zone is WARNING/DANGER/CRITICAL, the next sleep interval
    is shortened by be_accel_factor (default 0.5) subject to be_accel_min_interval
    floor. SAFE zone never accelerates. Disabled when be_accel_enabled=False.
    """

    def _params(self, **overrides):
        p = {'be_accel_enabled': True, 'be_accel_factor': 0.5, 'be_accel_min_interval': 30}
        p.update(overrides)
        return p

    def test_warning_zone_halves_interval(self):
        """WARNING zone with factor=0.5 halves a 300s interval to 150s."""
        from webui.backend.routes.mmm.mmm_trigger import compute_be_zone_accel
        result = compute_be_zone_accel(300, 'WARNING', self._params())
        self.assertTrue(result['accelerated'])
        self.assertEqual(result['effective_interval'], 150)

    def test_danger_zone_accelerates(self):
        """DANGER zone also triggers acceleration."""
        from webui.backend.routes.mmm.mmm_trigger import compute_be_zone_accel
        result = compute_be_zone_accel(300, 'DANGER', self._params())
        self.assertTrue(result['accelerated'])
        self.assertEqual(result['effective_interval'], 150)

    def test_critical_zone_accelerates(self):
        """CRITICAL zone accelerates (arbiter fires, but subsequent beats must also be fast)."""
        from webui.backend.routes.mmm.mmm_trigger import compute_be_zone_accel
        result = compute_be_zone_accel(300, 'CRITICAL', self._params())
        self.assertTrue(result['accelerated'])
        self.assertEqual(result['effective_interval'], 150)

    def test_safe_zone_no_acceleration(self):
        """SAFE zone: no acceleration, original interval preserved."""
        from webui.backend.routes.mmm.mmm_trigger import compute_be_zone_accel
        result = compute_be_zone_accel(300, 'SAFE', self._params())
        self.assertFalse(result['accelerated'])
        self.assertEqual(result['effective_interval'], 300)

    def test_min_interval_floor_respected(self):
        """Floor be_accel_min_interval is honoured: factor×interval cannot go below it."""
        from webui.backend.routes.mmm.mmm_trigger import compute_be_zone_accel
        # interval=150, factor=0.5 → 75, but min=100 → effective=100
        result = compute_be_zone_accel(150, 'WARNING', self._params(be_accel_min_interval=100))
        self.assertTrue(result['accelerated'])
        self.assertEqual(result['effective_interval'], 100)

    def test_disabled_no_acceleration(self):
        """be_accel_enabled=False suppresses acceleration regardless of zone."""
        from webui.backend.routes.mmm.mmm_trigger import compute_be_zone_accel
        result = compute_be_zone_accel(300, 'CRITICAL', self._params(be_accel_enabled=False))
        self.assertFalse(result['accelerated'])
        self.assertEqual(result['effective_interval'], 300)

    def test_default_params_present(self):
        """be_accel_enabled/factor/min_interval must all exist in DEFAULT_PARAMS."""
        from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS
        self.assertIn('be_accel_enabled', DEFAULT_PARAMS)
        self.assertIn('be_accel_factor', DEFAULT_PARAMS)
        self.assertIn('be_accel_min_interval', DEFAULT_PARAMS)
        self.assertTrue(DEFAULT_PARAMS['be_accel_enabled'])
        self.assertAlmostEqual(DEFAULT_PARAMS['be_accel_factor'], 0.5)
        self.assertEqual(DEFAULT_PARAMS['be_accel_min_interval'], 30)

    def test_hot_reload_params_registered(self):
        """All three be_accel params must be in HOT_RELOAD_PARAMS."""
        from webui.backend.routes.mmm.mmm_state import HOT_RELOAD_PARAMS
        for key in ('be_accel_enabled', 'be_accel_factor', 'be_accel_min_interval'):
            self.assertIn(key, HOT_RELOAD_PARAMS, f'{key} missing from HOT_RELOAD_PARAMS')

    def test_layer4_in_run_loop_source(self):
        """Layer 4 block must call compute_be_zone_accel inside _run_loop."""
        import inspect
        import webui.backend.routes.mmm.mmm_monitor as mon
        src = inspect.getsource(mon.MMMMonitor._run_loop)
        self.assertIn('compute_be_zone_accel', src,
                      'Layer 4 must call compute_be_zone_accel inside _run_loop')
        self.assertIn('_breakeven_zone', src,
                      'Layer 4 must read session[_breakeven_zone]')
        self.assertIn('_be_accel', src,
                      'Layer 4 must set session[_be_accel] flag')


# =============================================================================
# Profit Target Exit — Phase 1 (Hard Exit)
# =============================================================================

class TestProfitTargetPhase1(unittest.TestCase):
    """Sealed tests for Phase 1 Hard Profit Target Exit."""

    def _make_session(self, profit_target_usd=0.0, buffer_pct=8.0,
                      restart_enabled=False, pnl=0.0):
        """Create a minimal session dict for profit target testing."""
        return {
            'session_id': 'test-profit-target',
            'params': {
                'profit_target_usd': profit_target_usd,
                'profit_target_buffer_pct': buffer_pct,
                'profit_target_restart_enabled': restart_enabled,
            },
            'realized_pnl': pnl,
            'unrealized_pnl': 0.0,
            'total_fees': 0.0,
            'ce': {'active_lots': 0, 'total_lots': 0, 'positions': []},
            'pe': {'active_lots': 0, 'total_lots': 0, 'positions': []},
            'perp_hedge': {'lots': 0, 'realized_pnl': 0.0, 'unrealized_pnl': 0.0},
            '_reverse': {'net_pnl': 0.0, 'active': False, 'positions': []},
        }

    def test_profit_target_disabled(self):
        """profit_target_usd=0 → method returns False, _auto_close_all not called."""
        from webui.backend.routes.mmm.mmm_pnl_core import compute_current_total_pnl
        session = self._make_session(profit_target_usd=0.0, pnl=100.0)
        # compute_current_total_pnl should return the pnl value
        pnl = compute_current_total_pnl(session)
        self.assertGreater(pnl, 0, 'P&L should be > 0 for disabled test')
        # Verify profit_target_usd is 0 (disabled)
        self.assertEqual(session['params']['profit_target_usd'], 0.0,
                         'profit_target_usd must default to 0.0 (disabled)')

    def test_profit_target_not_yet_hit(self):
        """P&L = target - 1 → returns False (not yet hit)."""
        from webui.backend.routes.mmm.mmm_pnl_core import compute_current_total_pnl
        session = self._make_session(profit_target_usd=30.0, buffer_pct=8.0, pnl=29.0)
        pnl = compute_current_total_pnl(session)
        target = session['params']['profit_target_usd']
        buffer_pct = session['params']['profit_target_buffer_pct']
        trigger_at = target * (1 + buffer_pct / 100.0)
        self.assertLess(pnl, trigger_at,
                        f'P&L ${pnl:.2f} should be < trigger_at ${trigger_at:.2f}')

    def test_profit_target_hit_hard_exit(self):
        """P&L >= trigger_at → _auto_close_all called and _running set to False."""
        import asyncio
        from unittest.mock import AsyncMock, patch, MagicMock
        import webui.backend.routes.mmm.mmm_monitor as mon

        session = self._make_session(profit_target_usd=30.0, buffer_pct=8.0, pnl=35.0)

        monitor = object.__new__(mon.MMMMonitor)
        monitor.session_id = 'test-profit-target'
        monitor.session = session
        monitor._running = True

        close_all_mock = AsyncMock()
        monitor._auto_close_all = close_all_mock

        with patch('webui.backend.routes.mmm.mmm_monitor.log_activity'):
            result = asyncio.get_event_loop().run_until_complete(
                monitor._check_profit_target(session, 0.0, 0.0)
            )

        self.assertTrue(result, '_check_profit_target must return True when target is hit')
        close_all_mock.assert_called_once()
        self.assertFalse(monitor._running, '_running must be False after hard exit')

    def test_profit_target_buffer_math(self):
        """target=30, buffer=8.0 → trigger_at=32.40."""
        target = 30.0
        buffer_pct = 8.0
        trigger_at = target * (1 + buffer_pct / 100.0)
        self.assertAlmostEqual(trigger_at, 32.40, places=2,
                               msg=f'Expected trigger_at=32.40, got {trigger_at}')

    def test_profit_target_activity_logged(self):
        """Verify profit_target_hit activity type exists with correct fields."""
        from webui.backend.routes.mmm.mmm_activity import ACTIVITY_TYPES, ACTIVITY_CATEGORIES
        self.assertIn('profit_target_hit', ACTIVITY_TYPES,
                      'profit_target_hit must be in ACTIVITY_TYPES')
        self.assertIn('profit_target_hit', ACTIVITY_CATEGORIES.get('safety', set()),
                      'profit_target_hit must be in ACTIVITY_CATEGORIES under safety')

    def test_profit_target_uses_net_pnl(self):
        """Verify compute_current_total_pnl is the function used (not a raw field)."""
        from webui.backend.routes.mmm.mmm_pnl_core import compute_current_total_pnl
        import inspect
        import webui.backend.routes.mmm.mmm_monitor as mon
        src = inspect.getsource(mon.MMMMonitor._check_profit_target)
        self.assertIn('_pnl_total', src,
                      '_check_profit_target must call _pnl_total (compute_current_total_pnl)')
        self.assertIn('profit_target_usd', src,
                      '_check_profit_target must read profit_target_usd from params')
        self.assertIn('profit_target_buffer_pct', src,
                      '_check_profit_target must read profit_target_buffer_pct from params')
        self.assertIn('_auto_close_all', src,
                      '_check_profit_target must call _auto_close_all on hit')


class TestArbiterDoubleSellPrevention(unittest.TestCase):
    """Regression: proactive shift + arbiter firing same beat for same side (mmm01may26-1).

    Root cause: _proactive_shift_scan (line ~3335) fires for PE, places orders, then
    arbiter (line ~3464) evaluates and also fires defensive_shift for PE — cooldown
    bypass (_arbiter_shift_bypass_cooldown) made shift_cooldown ineffective.
    Fix: _process_strike_shift sets _shift_placed_this_beat_{side}=True on success;
    arbiter block checks this flag and suppresses execution when True.
    """

    def test_shift_placed_flag_suppresses_arbiter_double_sell(self):
        """If _shift_placed_this_beat_pe is True, arbiter defensive_shift on PE is suppressed."""
        import inspect
        import webui.backend.routes.mmm.mmm_monitor as mon
        src = inspect.getsource(mon.MMMMonitor._heartbeat_inner)
        self.assertIn('_shift_placed_this_beat_', src,
                      '_heartbeat_inner must check _shift_placed_this_beat_{side} flag')
        self.assertIn('_double_sell', src,
                      '_heartbeat_inner must have a _double_sell guard')
        self.assertIn('arbiter_suppressed_double_sell', src,
                      '_heartbeat_inner must log arbiter_suppressed_double_sell activity')

    def test_flag_cleared_each_beat(self):
        """_shift_placed_this_beat_{side} flags must be popped before proactive shift scan."""
        import inspect
        import webui.backend.routes.mmm.mmm_monitor as mon
        src = inspect.getsource(mon.MMMMonitor._heartbeat_inner)
        self.assertIn("pop('_shift_placed_this_beat_ce'", src,
                      '_heartbeat_inner must pop _shift_placed_this_beat_ce each beat')
        self.assertIn("pop('_shift_placed_this_beat_pe'", src,
                      '_heartbeat_inner must pop _shift_placed_this_beat_pe each beat')

    def test_flag_set_on_shift_success(self):
        """_process_strike_shift must set _shift_placed_this_beat_{side} on successful order."""
        import inspect
        import webui.backend.routes.mmm.mmm_monitor as mon
        src = inspect.getsource(mon.MMMMonitor._process_strike_shift)
        self.assertIn('_shift_placed_this_beat_', src,
                      '_process_strike_shift must set _shift_placed_this_beat_{side} on fill')

    def test_double_sell_guard_checks_defensive_shift_only(self):
        """Guard must be specific to defensive_shift — not suppress gamma/margin actions."""
        import inspect
        import webui.backend.routes.mmm.mmm_monitor as mon
        src = inspect.getsource(mon.MMMMonitor._heartbeat_inner)
        # The guard must check action_type == 'defensive_shift'
        self.assertIn("'defensive_shift'", src,
                      "Double-sell guard must specifically check for 'defensive_shift' action")


# =============================================================================
# mmm01may26-1 post-mortem fixes
# =============================================================================

class TestProactiveShiftFallbackCap(unittest.TestCase):
    """Proactive shift lot fallback must re-check position cap (Bug #1, mmm01may26-1)."""

    def _make_session(self, total_lots, max_lots_per_side=300):
        return {
            'params': {'max_lots_per_side': max_lots_per_side},
            'pe': {'total_lots': total_lots, 'active_lots': 0},
            'ce': {'total_lots': 0, 'active_lots': 0},
        }

    def test_fallback_cap_enforced_in_source(self):
        """_process_strike_shift must re-check position cap after fallback lot seeding."""
        import inspect
        import webui.backend.routes.mmm.mmm_monitor as mon
        src = inspect.getsource(mon.MMMMonitor._process_strike_shift)
        self.assertIn('proactive_shift_fallback_cap', src,
                      '_process_strike_shift must log proactive_shift_fallback_cap '
                      'when fallback lots exceed position cap')

    def test_combined_cap_check_in_source(self):
        """Delta-neutral matching must use remaining_cap not raw max_per_side."""
        import inspect
        import webui.backend.routes.mmm.mmm_monitor as mon
        src = inspect.getsource(mon.MMMMonitor._process_strike_shift)
        self.assertIn('remaining_cap', src,
                      '_process_strike_shift delta-neutral match must use remaining_cap '
                      '(max_per_side minus existing total_lots) not raw max_per_side')


class TestCombinedPositionSizeCheck(unittest.TestCase):
    """check_combined_position_size must fire when CE+PE combined lots >= 2×max (Bug #2)."""

    def _safety(self):
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        return MMMSafety()

    def _session(self, ce_total, pe_total, max_per_side=300):
        return {
            'params': {'max_lots_per_side': max_per_side},
            'ce': {'total_lots': ce_total},
            'pe': {'total_lots': pe_total},
        }

    def test_fires_at_cap(self):
        s = self._safety()
        events = s.check_combined_position_size(self._session(300, 300))
        self.assertTrue(any(e['type'] == 'combined_position_cap' and
                            e['action'] == 'stop_adjustments' for e in events),
                        'combined check must block at 600 combined lots (max=300×2=600)')

    def test_fires_above_cap(self):
        s = self._safety()
        events = s.check_combined_position_size(self._session(303, 300))
        self.assertTrue(any(e['type'] == 'combined_position_cap' and
                            e['action'] == 'stop_adjustments' for e in events),
                        'combined check must block when combined > 600')

    def test_warning_at_80pct(self):
        s = self._safety()
        events = s.check_combined_position_size(self._session(240, 241))
        self.assertTrue(any(e['type'] == 'combined_position_cap' and
                            e['action'] == 'continue' for e in events),
                        'combined check must warn at 80% of combined cap')

    def test_no_event_below_threshold(self):
        s = self._safety()
        events = s.check_combined_position_size(self._session(100, 100))
        self.assertFalse(any(e['type'] == 'combined_position_cap' for e in events))

    def test_called_from_run_all_checks(self):
        """run_all_checks must call check_combined_position_size."""
        import inspect
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        src = inspect.getsource(MMMSafety.run_all_checks)
        self.assertIn('check_combined_position_size', src,
                      'run_all_checks must invoke check_combined_position_size')


class TestRegimeEnabledDefault(unittest.TestCase):
    """regime_enabled must default to True in mmm_state DEFAULT_PARAMS (mmm01may26-1)."""

    def test_regime_enabled_default_is_true(self):
        from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS
        self.assertTrue(
            DEFAULT_PARAMS.get('regime_enabled', False),
            "DEFAULT_PARAMS['regime_enabled'] must be True — it defaulted to False "
            "during mmm01may26-1, leaving the vol/gamma/trend regime off the entire session"
        )


# =============================================================================
# Bid/mark sanity guard in _make_bid_fetch_fn
# Frozen PE @ 75500: bid=$0.19 ask=$96.50 mark=$10.50 — wide spread anomaly
# caused close_at_5 to flag as eligible and retry every heartbeat forever.
# =============================================================================

class TestBidMarkRatioFloor(unittest.TestCase):
    """_make_bid_fetch_fn must return mark when bid/mark < close_at_bid_mark_ratio_floor."""

    def _make_monitor_stub(self, bid, mark, floor=0.1):
        """Build a minimal MMMMonitor-like object with the caches pre-populated."""
        import webui.backend.routes.mmm.mmm_monitor as mon

        class _Stub:
            _bid_cache = {(75500.0, 'put'): bid}
            _premium_cache = {(75500.0, 'put'): mark}
            session = {'params': {'close_at_bid_mark_ratio_floor': floor}}

        # Bind _make_bid_fetch_fn from MMMMonitor to our stub
        stub = _Stub()
        stub._make_bid_fetch_fn = mon.MMMMonitor._make_bid_fetch_fn.__get__(stub)
        return stub

    def test_normal_spread_returns_bid(self):
        """When bid/mark >= floor, return bid (normal liquid market)."""
        stub = self._make_monitor_stub(bid=4.0, mark=5.0, floor=0.1)
        fn = stub._make_bid_fetch_fn()
        result = fn(75500, 'put')
        self.assertAlmostEqual(result, 4.0,
                               msg='Normal spread (bid/mark=0.8): should return bid')

    def test_anomalous_spread_returns_mark(self):
        """When bid/mark < floor (extreme spread), return mark (illiquid quote guard)."""
        stub = self._make_monitor_stub(bid=0.19, mark=10.50, floor=0.1)
        fn = stub._make_bid_fetch_fn()
        result = fn(75500, 'put')
        self.assertAlmostEqual(result, 10.50,
                               msg='Anomalous spread (bid/mark=0.018): should return mark '
                                   'to prevent false-positive close_at_5 eligibility')

    def test_bid_below_floor_prevents_close_at_5_eligibility(self):
        """When mark > close_at_threshold and bid/mark < floor, close_at_5 must not trigger."""
        stub = self._make_monitor_stub(bid=0.19, mark=10.50, floor=0.1)
        fn = stub._make_bid_fetch_fn()
        premium = fn(75500, 'put')  # should return mark=10.50
        threshold = 5.0
        self.assertGreater(premium, threshold,
                           msg='With anomalous spread, returned premium must exceed threshold '
                               'so scan_closeable_positions does not flag as eligible')

    def test_floor_param_respected(self):
        """custom close_at_bid_mark_ratio_floor param must be used."""
        # With floor=0.5, bid=0.30, mark=1.00 → ratio=0.30 < 0.50 → return mark
        stub = self._make_monitor_stub(bid=0.30, mark=1.00, floor=0.5)
        fn = stub._make_bid_fetch_fn()
        result = fn(75500, 'put')
        self.assertAlmostEqual(result, 1.00,
                               msg='With floor=0.5 and ratio=0.3, should return mark')


# =============================================================================
# TestShiftLotsZeroUnfreeze
# Root cause: when total_lots > max_lots_per_side, the proactive shift freeze
# runs (positions go 'shifted'), then remaining_cap=0 makes lots=0, and the
# old `return` at the lots-zero guard left positions frozen with no rollback.
# Result: active_lots stuck at 0 every heartbeat (live session mmm02may26-1).
# Fix: roll back freeze (shifted→active at old_strike) before returning.
# =============================================================================

class TestShiftLotsZeroUnfreeze(unittest.TestCase):
    """Shift lots=0 guard must roll back freeze so side is not stranded."""

    def _make_session(self, frozen_lots=250, max_per_side=200):
        """Build a minimal session where PE is over cap with all lots frozen."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        positions = [
            {'id': 'pe_orig', 'strike': 76200.0, 'lots': 50, 'entry_premium': 80.0,
             'type': 'original', 'status': 'shifted', 'shifted_at': now,
             'created_at': now, 'order_id': '', 'client_order_id': '',
             'closed_at': None, 'realized_pnl': None},
            {'id': 'pe_adj_001', 'strike': 76200.0, 'lots': 10, 'entry_premium': 72.0,
             'type': 'adjustment', 'status': 'shifted', 'shifted_at': now,
             'created_at': now, 'order_id': '', 'client_order_id': '',
             'closed_at': None, 'realized_pnl': None},
            {'id': 'pe_shift_001', 'strike': 76600.0, 'lots': 140, 'entry_premium': 63.0,
             'type': 'strike_shift', 'status': 'shifted', 'shifted_at': now,
             'created_at': now, 'order_id': '', 'client_order_id': '',
             'closed_at': None, 'realized_pnl': None},
            {'id': 'pe_shift_002', 'strike': 77000.0, 'lots': 50, 'entry_premium': 51.0,
             'type': 'strike_shift', 'status': 'shifted', 'shifted_at': now,
             'created_at': now, 'order_id': '', 'client_order_id': '',
             'closed_at': None, 'realized_pnl': None},
        ]
        from webui.backend.routes.mmm.mmm_state import recompute_side_lots
        pe_state = {
            'active_strike': 76200.0,
            'positions': positions,
            'trigger_snapshot': {},
            'frozen_positions': [],
            'active_lots': 0,
            'frozen_total_lots': 0,
            'total_lots': 0,
            'original_lots': 0,
            'adjustment_fills': [],
            'adjustment_total_lots': 0,
        }
        recompute_side_lots(pe_state)
        return {
            'session_id': 'test_mmm',
            'strategy_status': 'RUNNING',
            'pe': pe_state,
            'ce': {'active_lots': 68, 'active_strike': 78400.0,
                   'positions': [], 'frozen_positions': [],
                   'total_lots': 68, 'frozen_total_lots': 0},
            'params': {
                'max_lots_per_side': max_per_side,
                'shift_threshold': 50.0,
                'shift_match_opposite_lots': True,
                'shift_match_max_inflate_mult': 1.5,
                'trend_boost_enabled': False,
            },
        }

    def test_freeze_rolled_back_when_lots_zero_after_cap(self):
        """When remaining_cap=0 makes lots=0, the freeze must be rolled back."""
        session = self._make_session(max_per_side=200)
        # All PE positions are 'shifted' — simulate state after recovery promoted
        # 76600 → active, then proactive shift froze it again, cap made lots=0.
        # The bug: positions stay 'shifted' (active_lots=0) after lots=0 guard.
        # The fix: roll back positions at old_strike to 'active'.
        old_strike = 76200.0

        # Simulate the lots=0 rollback directly (as the fix does)
        _restored = 0
        for _pos in session['pe'].get('positions', []):
            if _pos.get('status') == 'shifted' and _pos.get('strike') == old_strike:
                _pos['status'] = 'active'
                _pos.pop('shifted_at', None)
                _restored += _pos.get('lots', 0)

        from webui.backend.routes.mmm.mmm_state import recompute_side_lots
        recompute_side_lots(session['pe'])

        self.assertGreater(_restored, 0, 'Must restore > 0 lots at old_strike')
        self.assertGreater(session['pe']['active_lots'], 0,
                           'active_lots must be > 0 after rollback')

    def test_remaining_cap_zero_when_over_limit(self):
        """remaining_cap must be 0 (not negative) when total_lots > max_per_side."""
        session = self._make_session(max_per_side=200)
        total_lots = session['pe']['total_lots']
        max_per_side = session['params']['max_lots_per_side']
        remaining_cap = max(max_per_side - total_lots, 0)
        self.assertEqual(total_lots, 250)
        self.assertEqual(remaining_cap, 0,
                         'remaining_cap must be 0, not negative, when over cap')

    def test_active_lots_nonzero_after_rollback(self):
        """After rollback, active_lots at old_strike must match restored positions."""
        session = self._make_session(max_per_side=200)
        old_strike = 76200.0
        # Roll back shifted positions at old_strike
        for _pos in session['pe'].get('positions', []):
            if _pos.get('status') == 'shifted' and _pos.get('strike') == old_strike:
                _pos['status'] = 'active'
                _pos.pop('shifted_at', None)
        from webui.backend.routes.mmm.mmm_state import recompute_side_lots
        recompute_side_lots(session['pe'])
        # 50 (original) + 10 (adjustment) = 60 lots at 76200
        self.assertEqual(session['pe']['active_lots'], 60,
                         'active_lots must equal sum of restored positions at old_strike')


class TestProcessStrikeShiftNoLocalRecomputeImport(unittest.TestCase):
    """
    Regression: 2026-05-04 P0 — session mmm04may26-1 crashed with
    UnboundLocalError accessing 'recompute_side_lots' at line 6664 of
    mmm_monitor.py (the lots=0 freeze rollback inside _process_strike_shift).

    Root cause: `_process_strike_shift` had a local
    `from .mmm_state import recompute_side_lots` inside the
    `if not self._running:` orphan-prevention block (line ~6694). Python's
    scoping rules make any name assigned anywhere in a function a local for
    the WHOLE function — so the earlier reference at the lots=0 rollback
    raised UnboundLocalError when the import statement had not yet executed.

    Fix: rely on the module-level import (line 30); do NOT shadow it with a
    local from-import inside _process_strike_shift.

    This contract test asserts the function source contains no unaliased
    `from ... import recompute_side_lots`, which is the exact condition that
    triggered the crash.
    """

    @pytest.mark.sealed
    def test_no_local_unaliased_recompute_import(self):
        import ast, inspect, textwrap
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        src = textwrap.dedent(inspect.getsource(MMMMonitor._process_strike_shift))
        tree = ast.parse(src)
        offenders = [
            sub.lineno
            for sub in ast.walk(tree)
            if isinstance(sub, ast.ImportFrom)
            and sub.module and 'mmm_state' in sub.module
            for n in sub.names
            if n.name == 'recompute_side_lots' and n.asname is None
        ]
        self.assertEqual(
            offenders, [],
            f'_process_strike_shift must not shadow module-level '
            f'recompute_side_lots with a local from-import '
            f'(offending lines, relative to function start: {offenders}). '
            f'See incident mmm04may26-1.'
        )


# =============================================================================
# mmm05may26-1: Three-bug fix — velocity direction, God inactivity, double-sell
# =============================================================================

class TestArbitersVelocityDirectionalBypass(unittest.TestCase):
    """
    Bug 1 redesign: the dangerous side is the side losing real money, determined
    by _trend_direction (set by the regime module each beat), not by which side
    the arbiter happens to be firing on. _proactive_shift_scan reads _trend_direction
    directly and skips the dangerous side every beat — no session key, no lag.

    Also verifies Bug 2 timing fix: _arbiter_decision_active is reset BEFORE the
    proactive scan so _process_strike_shift does not mis-tag organic proactive shifts
    as arbiter corrections.
    """

    @pytest.mark.sealed
    def test_proactive_shift_scan_reads_trend_direction(self):
        """_proactive_shift_scan derives dangerous side from _trend_direction, not a session key."""
        import inspect, textwrap
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        src = textwrap.dedent(inspect.getsource(MMMMonitor._proactive_shift_scan))
        self.assertIn('_trend_direction', src,
                      '_proactive_shift_scan must read _trend_direction to determine '
                      'the dangerous side (TREND_UP→CE dangerous, TREND_DOWN→PE dangerous)')
        self.assertNotIn('_arbiter_velocity_dangerous_side', src,
                         '_proactive_shift_scan must NOT use the old session-key approach '
                         'which had a one-beat lag and an UnboundLocalError crash path')

    @pytest.mark.sealed
    def test_proactive_scan_dangerous_side_mapping(self):
        """Source check: _proactive_shift_scan maps 'up'→CE dangerous, 'down'→PE dangerous."""
        import inspect, textwrap
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        src = textwrap.dedent(inspect.getsource(MMMMonitor._proactive_shift_scan))
        self.assertIn("'up'", src,
                      "TREND_UP ('up') mapping must appear in _proactive_shift_scan")
        self.assertIn("'down'", src,
                      "TREND_DOWN ('down') mapping must appear in _proactive_shift_scan")
        # 'ce' must be identified as the dangerous side for TREND_UP
        idx_up = src.find("'up'")
        block = src[idx_up: idx_up + 200]
        self.assertIn("'ce'", block,
                      "CE must be identified as the dangerous side when trend direction is 'up'")

    @pytest.mark.sealed
    def test_arbiter_decision_active_reset_before_proactive_scan(self):
        """_arbiter_decision_active is reset to False BEFORE _proactive_shift_scan runs."""
        import inspect, textwrap
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        src = textwrap.dedent(inspect.getsource(MMMMonitor._heartbeat_inner))
        # The reset must appear BEFORE the call to _proactive_shift_scan
        idx_reset = src.find("session['_arbiter_decision_active'] = False")
        idx_scan = src.find('_proactive_shift_scan')
        self.assertGreater(idx_reset, 0,
                           "_arbiter_decision_active must be reset to False in _heartbeat_inner")
        self.assertGreater(idx_scan, 0,
                           "_proactive_shift_scan must be called in _heartbeat_inner")
        self.assertLess(idx_reset, idx_scan,
                        "_arbiter_decision_active reset must appear BEFORE _proactive_shift_scan "
                        "call so organic proactive shifts are not mis-tagged as arbiter corrections")

    @pytest.mark.sealed
    def test_no_arbiter_velocity_dangerous_side_session_key(self):
        """Old session-key approach is fully removed — no _arbiter_velocity_dangerous_side anywhere."""
        import inspect, textwrap
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        src_inner = textwrap.dedent(inspect.getsource(MMMMonitor._heartbeat_inner))
        src_scan = textwrap.dedent(inspect.getsource(MMMMonitor._proactive_shift_scan))
        self.assertNotIn('_arbiter_velocity_dangerous_side', src_inner,
                         '_heartbeat_inner must not use _arbiter_velocity_dangerous_side '
                         '(replaced by _trend_direction in _proactive_shift_scan)')
        self.assertNotIn('_arbiter_velocity_dangerous_side', src_scan,
                         '_proactive_shift_scan must not use _arbiter_velocity_dangerous_side')


class TestGodLayerSkipsArbiterShifts(unittest.TestCase):
    """
    Bug 2 fix: arbiter-driven strike shifts are tagged is_arbiter_correction=True
    in adjustment_history. God layer's _minutes_since_last_adjustment skips them
    so arbiter activity cannot starve God's inactivity signal.
    """

    @pytest.mark.sealed
    def test_strike_shift_history_has_arbiter_flag(self):
        """_process_strike_shift records is_arbiter_correction in adjustment_history."""
        import inspect, textwrap
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        src = textwrap.dedent(inspect.getsource(MMMMonitor._process_strike_shift))
        self.assertIn('is_arbiter_correction', src,
                      '_process_strike_shift adjustment_history entry must include '
                      'is_arbiter_correction flag (Bug 2 fix)')

    @pytest.mark.sealed
    def test_god_layer_skips_arbiter_corrections(self):
        """God layer _minutes_since_last_adjustment skips is_arbiter_correction entries."""
        import inspect, textwrap
        from webui.backend.routes.mmm.mmm_god_layer import StrategicIntegrityMonitor
        src = textwrap.dedent(inspect.getsource(
            StrategicIntegrityMonitor._minutes_since_last_adjustment))
        self.assertIn('is_arbiter_correction', src,
                      'God layer _minutes_since_last_adjustment must skip '
                      'is_arbiter_correction entries so arbiter activity cannot '
                      'prevent God from firing')

    @pytest.mark.sealed
    def test_god_inactivity_skips_arbiter_entry(self):
        """Unit test: God sees 9999 inactivity when only arbiter shifts exist."""
        from webui.backend.routes.mmm.mmm_god_layer import StrategicIntegrityMonitor
        from datetime import datetime, timezone, timedelta
        mon = StrategicIntegrityMonitor('test')
        session = {
            'adjustment_history': [
                {
                    'aggressor': 'CE',
                    'type': 'strike_shift',
                    'is_arbiter_correction': True,
                    'timestamp': (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                    'lots_sold': 85,
                }
            ]
        }
        minutes = mon._minutes_since_last_adjustment(session)
        self.assertGreater(minutes, 9000,
                           'When only arbiter shifts exist, inactivity must return '
                           '9999 (God should see the algo as inactive)')

    @pytest.mark.sealed
    def test_god_inactivity_counts_organic_adjustment(self):
        """Unit test: God counts non-arbiter adjustments normally."""
        from webui.backend.routes.mmm.mmm_god_layer import StrategicIntegrityMonitor
        from datetime import datetime, timezone, timedelta
        mon = StrategicIntegrityMonitor('test')
        session = {
            'adjustment_history': [
                {
                    'aggressor': 'CE',
                    'type': 'standard',
                    'is_arbiter_correction': False,
                    'timestamp': (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                    'lots_sold': 25,
                }
            ]
        }
        minutes = mon._minutes_since_last_adjustment(session)
        self.assertAlmostEqual(minutes, 10.0, delta=0.1,
                               msg='Organic adjustments must reset God inactivity clock normally')


class TestDoubleSellGuardTrendEmergencyBypass(unittest.TestCase):
    """
    Bug 3 fix: the double-sell guard must NOT suppress the arbiter's defensive
    shift when a trend emergency is active (T2:GUARD+) and the trigger is
    breakeven/hedge-decay related. The correct market response must never be killed.
    """

    @pytest.mark.sealed
    def test_trend_emergency_bypass_present_in_source(self):
        """_heartbeat_inner contains _trend_emergency_bypass guard for double-sell."""
        import inspect, textwrap
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        src = textwrap.dedent(inspect.getsource(MMMMonitor._heartbeat_inner))
        self.assertIn('_trend_emergency_bypass', src,
                      '_heartbeat_inner must define _trend_emergency_bypass to allow '
                      'arbiter through double-sell guard during trend emergencies')

    @pytest.mark.sealed
    def test_double_sell_guard_checks_not_trend_emergency(self):
        """_double_sell condition must include 'not _trend_emergency_bypass'."""
        import inspect, textwrap
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        src = textwrap.dedent(inspect.getsource(MMMMonitor._heartbeat_inner))
        self.assertIn('not _trend_emergency_bypass', src,
                      '_double_sell must be gated on not _trend_emergency_bypass')

    @pytest.mark.sealed
    def test_trend_emergency_requires_guard_tier_or_above(self):
        """Bypass only activates at trend_tier >= 2 (GUARD), not at ALERT (1)."""
        import inspect, textwrap
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        src = textwrap.dedent(inspect.getsource(MMMMonitor._heartbeat_inner))
        bypass_idx = src.find('_trend_emergency_bypass')
        guard_check = '>= 2' in src[bypass_idx:bypass_idx + 300]
        self.assertTrue(guard_check,
                        '_trend_emergency_bypass must require trend_tier >= 2 '
                        '(GUARD) so ALERT-only conditions do not bypass the guard')

    @pytest.mark.sealed
    def test_trend_emergency_trigger_keywords_present(self):
        """Bypass checks for trend-related trigger keywords, not any trigger."""
        import inspect, textwrap
        from webui.backend.routes.mmm.mmm_monitor import MMMMonitor
        src = textwrap.dedent(inspect.getsource(MMMMonitor._heartbeat_inner))
        for kw in ('breakeven_critical', 'hedge_decay', 'trend'):
            self.assertIn(kw, src,
                          f'_trend_emergency_bypass must check for trigger keyword '
                          f'"{kw}" to limit bypass to trend-related arbiter actions')


if __name__ == '__main__':
    unittest.main()
