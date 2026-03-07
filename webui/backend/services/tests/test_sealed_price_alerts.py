"""
Contract tests for Price Alerts system

SEALED — v1.0.0 — March 5, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Functions sealed in this file:
  1. AlertsDB.create_alert        — webui/backend/db/alerts_db.py
  2. AlertsDB.get_all_alerts      — webui/backend/db/alerts_db.py
  3. AlertsDB.delete_alert        — webui/backend/db/alerts_db.py
  4. AlertsDB.trigger_alert       — webui/backend/db/alerts_db.py
  5. PriceAlertMonitor._is_in_cooldown    — webui/backend/services/price_alert_monitor.py
  6. PriceAlertMonitor._format_alert_message — webui/backend/services/price_alert_monitor.py

All DB tests use a real in-memory SQLite DB (no mocks needed —
it's fast, isolated and deterministic). Monitor tests mock nothing external.

RUN:
    python3 -m pytest webui/backend/services/tests/test_sealed_price_alerts.py -v
    # or all sealed at once:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
import sys
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.sealed

# ─── path setup ──────────────────────────────────────────────────────────────
BACKEND = os.path.join(os.path.dirname(__file__), '..', '..', '..')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from webui.backend.db.alerts_db import AlertsDB, init_alerts_db, get_db_connection
from webui.backend.services.price_alert_monitor import PriceAlertMonitor


# ─── fixture: fresh isolated DB per test ─────────────────────────────────────
@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """
    Each test gets its own blank SQLite DB.
    Patches the DB_PATH used by alerts_db module so no real file is touched.
    """
    db_file = str(tmp_path / "test_alerts.db")
    import webui.backend.db.alerts_db as alerts_mod
    monkeypatch.setattr(alerts_mod, "DB_PATH", db_file)
    init_alerts_db()
    yield db_file


# =============================================================================
# 1. AlertsDB.create_alert
# =============================================================================

class TestCreateAlert:
    """@sealed AlertsDB.create_alert — CONTRACT TESTS"""

    def test_returns_dict_with_required_keys(self):
        alert = AlertsDB.create_alert(target_price=74000.0, direction='above')
        assert isinstance(alert, dict)
        for key in ('id', 'target_price', 'direction', 'status', 'symbol'):
            assert key in alert, f"Missing key: {key}"

    def test_default_status_is_active(self):
        alert = AlertsDB.create_alert(target_price=70000.0, direction='below')
        assert alert['status'] == 'active'

    def test_default_symbol_is_btcusd(self):
        alert = AlertsDB.create_alert(target_price=70000.0, direction='above')
        assert alert['symbol'] == 'BTCUSD'

    def test_direction_stored_correctly(self):
        for direction in ('above', 'below', 'cross'):
            alert = AlertsDB.create_alert(target_price=50000.0, direction=direction)
            assert alert['direction'] == direction

    def test_optional_fields_stored(self):
        alert = AlertsDB.create_alert(
            target_price=80000.0,
            direction='above',
            note='my note',
            expected_pnl_expiry=500.0,
            expiry_date='Mar 13'
        )
        assert alert['note'] == 'my note'
        assert alert['expected_pnl_expiry'] == 500.0
        assert alert['expiry_date'] == 'Mar 13'

    def test_id_is_short_string(self):
        alert = AlertsDB.create_alert(target_price=70000.0, direction='above')
        assert isinstance(alert['id'], str)
        assert len(alert['id']) == 8

    def test_two_alerts_get_different_ids(self):
        a1 = AlertsDB.create_alert(target_price=70000.0, direction='above')
        a2 = AlertsDB.create_alert(target_price=75000.0, direction='below')
        assert a1['id'] != a2['id']

    def test_target_price_stored_as_float(self):
        alert = AlertsDB.create_alert(target_price=74857.0, direction='above')
        assert float(alert['target_price']) == 74857.0


# =============================================================================
# 2. AlertsDB.get_all_alerts
# =============================================================================

class TestGetAllAlerts:
    """@sealed AlertsDB.get_all_alerts — CONTRACT TESTS"""

    def test_returns_list(self):
        result = AlertsDB.get_all_alerts()
        assert isinstance(result, list)

    def test_empty_db_returns_empty_list(self):
        assert AlertsDB.get_all_alerts() == []

    def test_returns_all_alerts_when_no_filter(self):
        AlertsDB.create_alert(target_price=70000.0, direction='above')
        AlertsDB.create_alert(target_price=65000.0, direction='below')
        result = AlertsDB.get_all_alerts()
        assert len(result) == 2

    def test_status_filter_returns_only_matching(self):
        AlertsDB.create_alert(target_price=70000.0, direction='above')
        a2 = AlertsDB.create_alert(target_price=65000.0, direction='below')
        AlertsDB.cancel_alert(a2['id'])

        active_only = AlertsDB.get_all_alerts(status='active')
        assert len(active_only) == 1
        assert active_only[0]['status'] == 'active'

    def test_expiry_filter_returns_only_matching(self):
        AlertsDB.create_alert(target_price=70000.0, direction='above', expiry_date='Mar 13')
        AlertsDB.create_alert(target_price=75000.0, direction='below', expiry_date='Mar 27')

        march13_only = AlertsDB.get_all_alerts(expiry_date='Mar 13')
        assert len(march13_only) == 1
        assert march13_only[0]['expiry_date'] == 'Mar 13'

    def test_combined_status_and_expiry_filter(self):
        AlertsDB.create_alert(target_price=70000.0, direction='above', expiry_date='Mar 13')
        a2 = AlertsDB.create_alert(target_price=75000.0, direction='below', expiry_date='Mar 13')
        AlertsDB.cancel_alert(a2['id'])

        result = AlertsDB.get_all_alerts(status='active', expiry_date='Mar 13')
        assert len(result) == 1
        assert result[0]['status'] == 'active'

    def test_each_result_is_dict(self):
        AlertsDB.create_alert(target_price=70000.0, direction='above')
        results = AlertsDB.get_all_alerts()
        assert all(isinstance(r, dict) for r in results)


# =============================================================================
# 3. AlertsDB.delete_alert
# =============================================================================

class TestDeleteAlert:
    """@sealed AlertsDB.delete_alert — CONTRACT TESTS"""

    def test_returns_true_on_existing_alert(self):
        alert = AlertsDB.create_alert(target_price=70000.0, direction='above')
        result = AlertsDB.delete_alert(alert['id'])
        assert result is True

    def test_alert_is_gone_after_delete(self):
        alert = AlertsDB.create_alert(target_price=70000.0, direction='above')
        AlertsDB.delete_alert(alert['id'])
        assert AlertsDB.get_alert(alert['id']) is None

    def test_returns_false_for_nonexistent_id(self):
        result = AlertsDB.delete_alert('doesnotexist')
        assert result is False

    def test_delete_one_leaves_others_intact(self):
        a1 = AlertsDB.create_alert(target_price=70000.0, direction='above')
        a2 = AlertsDB.create_alert(target_price=75000.0, direction='below')
        AlertsDB.delete_alert(a1['id'])
        remaining = AlertsDB.get_all_alerts()
        assert len(remaining) == 1
        assert remaining[0]['id'] == a2['id']


# =============================================================================
# 4. AlertsDB.trigger_alert
# =============================================================================

class TestTriggerAlert:
    """@sealed AlertsDB.trigger_alert — CONTRACT TESTS"""

    def test_one_time_alert_becomes_triggered(self):
        alert = AlertsDB.create_alert(target_price=70000.0, direction='above', is_repeating=False)
        updated = AlertsDB.trigger_alert(alert['id'], price_at_trigger=71000.0)
        assert updated['status'] == 'triggered'

    def test_triggered_at_is_set(self):
        alert = AlertsDB.create_alert(target_price=70000.0, direction='above', is_repeating=False)
        updated = AlertsDB.trigger_alert(alert['id'], price_at_trigger=71000.0)
        assert updated['triggered_at'] is not None

    def test_trigger_count_increments(self):
        alert = AlertsDB.create_alert(target_price=70000.0, direction='above', is_repeating=False)
        updated = AlertsDB.trigger_alert(alert['id'], price_at_trigger=71000.0)
        assert updated['trigger_count'] == 1

    def test_repeating_alert_stays_active(self):
        alert = AlertsDB.create_alert(target_price=70000.0, direction='above', is_repeating=True)
        updated = AlertsDB.trigger_alert(alert['id'], price_at_trigger=71000.0)
        assert updated['status'] == 'active'

    def test_repeating_alert_increments_trigger_count(self):
        alert = AlertsDB.create_alert(target_price=70000.0, direction='above', is_repeating=True)
        AlertsDB.trigger_alert(alert['id'], price_at_trigger=71000.0)
        updated = AlertsDB.trigger_alert(alert['id'], price_at_trigger=72000.0)
        assert updated['trigger_count'] == 2

    def test_returns_none_for_missing_id(self):
        result = AlertsDB.trigger_alert('doesnotexist', price_at_trigger=70000.0)
        assert result is None


# =============================================================================
# 5. PriceAlertMonitor._is_in_cooldown
# =============================================================================

class TestIsInCooldown:
    """@sealed PriceAlertMonitor._is_in_cooldown — CONTRACT TESTS"""

    def _monitor(self):
        """Create a monitor without starting any thread."""
        with patch('webui.backend.services.price_alert_monitor.AlertsDB.get_settings', return_value={}), \
             patch('webui.backend.services.price_alert_monitor.NotificationService'):
            m = PriceAlertMonitor.__new__(PriceAlertMonitor)
            m.check_interval = 5
            m._running = False
            m._thread = None
            m._current_price = None
            m._last_check = None
            from unittest.mock import MagicMock
            m._notification_service = MagicMock()
            return m

    def test_no_last_triggered_is_not_in_cooldown(self):
        m = self._monitor()
        alert = {'last_triggered_at': None, 'cooldown_minutes': 60}
        assert m._is_in_cooldown(alert) is False

    def test_triggered_recently_is_in_cooldown(self):
        m = self._monitor()
        recent = (datetime.now() - timedelta(minutes=5)).isoformat()
        alert = {'last_triggered_at': recent, 'cooldown_minutes': 60}
        assert m._is_in_cooldown(alert) is True

    def test_triggered_long_ago_is_not_in_cooldown(self):
        m = self._monitor()
        old = (datetime.now() - timedelta(minutes=120)).isoformat()
        alert = {'last_triggered_at': old, 'cooldown_minutes': 60}
        assert m._is_in_cooldown(alert) is False

    def test_bad_timestamp_returns_false_never_raises(self):
        m = self._monitor()
        alert = {'last_triggered_at': 'not-a-date', 'cooldown_minutes': 60}
        result = m._is_in_cooldown(alert)
        assert result is False

    def test_zero_cooldown_minutes_is_never_in_cooldown(self):
        m = self._monitor()
        recent = (datetime.now() - timedelta(seconds=1)).isoformat()
        alert = {'last_triggered_at': recent, 'cooldown_minutes': 0}
        # cooldown_end = last_time + 0 minutes = last_time, which is in the past
        assert m._is_in_cooldown(alert) is False


# =============================================================================
# 6. PriceAlertMonitor._format_alert_message
# =============================================================================

class TestFormatAlertMessage:
    """@sealed PriceAlertMonitor._format_alert_message — CONTRACT TESTS"""

    def _monitor(self, current_price=71000.0):
        with patch('webui.backend.services.price_alert_monitor.AlertsDB.get_settings', return_value={}), \
             patch('webui.backend.services.price_alert_monitor.NotificationService'):
            m = PriceAlertMonitor.__new__(PriceAlertMonitor)
            m._current_price = current_price
            m._notification_service = MagicMock()
            return m

    def test_returns_string(self):
        m = self._monitor()
        alert = {'target_price': 70000.0, 'direction': 'above', 'note': '', 'expiry_date': None, 'expected_pnl_expiry': None}
        assert isinstance(m._format_alert_message(alert), str)

    def test_contains_target_price(self):
        m = self._monitor()
        alert = {'target_price': 74857.0, 'direction': 'above', 'note': '', 'expiry_date': None, 'expected_pnl_expiry': None}
        msg = m._format_alert_message(alert)
        assert '74,857' in msg or '74857' in msg

    def test_contains_above_for_above_direction(self):
        m = self._monitor()
        alert = {'target_price': 70000.0, 'direction': 'above', 'note': '', 'expiry_date': None, 'expected_pnl_expiry': None}
        msg = m._format_alert_message(alert)
        assert 'above' in msg

    def test_contains_below_for_below_direction(self):
        m = self._monitor()
        alert = {'target_price': 70000.0, 'direction': 'below', 'note': '', 'expiry_date': None, 'expected_pnl_expiry': None}
        msg = m._format_alert_message(alert)
        assert 'below' in msg

    def test_includes_expiry_date_when_present(self):
        m = self._monitor()
        alert = {'target_price': 70000.0, 'direction': 'above', 'note': '', 'expiry_date': 'Mar 13', 'expected_pnl_expiry': None}
        msg = m._format_alert_message(alert)
        assert 'Mar 13' in msg

    def test_includes_pnl_when_present(self):
        m = self._monitor()
        alert = {'target_price': 70000.0, 'direction': 'above', 'note': '', 'expiry_date': None, 'expected_pnl_expiry': 1023.57}
        msg = m._format_alert_message(alert)
        assert '1023' in msg or '1,023' in msg

    def test_includes_note_when_present(self):
        m = self._monitor()
        alert = {'target_price': 70000.0, 'direction': 'above', 'note': 'hedge expires', 'expiry_date': None, 'expected_pnl_expiry': None}
        msg = m._format_alert_message(alert)
        assert 'hedge expires' in msg

    def test_no_crash_on_minimal_alert(self):
        m = self._monitor()
        alert = {'target_price': 70000.0, 'direction': 'above', 'note': None, 'expiry_date': None, 'expected_pnl_expiry': None}
        # Should not raise
        m._format_alert_message(alert)
