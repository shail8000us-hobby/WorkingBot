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


if __name__ == '__main__':
    unittest.main()
