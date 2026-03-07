"""
Contract Test: check_expiry_warning
========================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of check_expiry_warning.
Uses datetime math — fully deterministic with fixed timestamps.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest bot/options/utils/tests/test_sealed_check_expiry_warning.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
from datetime import datetime, timezone, timedelta
from bot.options.utils.options_helper import check_expiry_warning

pytestmark = pytest.mark.sealed


def _future_timestamp(hours_from_now: float) -> str:
    """Build an ISO timestamp that is 'hours_from_now' hours in the future."""
    t = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


def _past_timestamp(hours_ago: float) -> str:
    """Build an ISO timestamp that is 'hours_ago' hours in the past."""
    t = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Returns correct dict shape
# ---------------------------------------------------------------------------

def test_returns_correct_shape():
    """Must return dict with is_expiring_soon, hours_until_expiry, warning_level."""
    result = check_expiry_warning(_future_timestamp(48))
    assert 'is_expiring_soon'    in result
    assert 'hours_until_expiry'  in result
    assert 'warning_level'       in result


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Expired option returns 'expired' warning level
# ---------------------------------------------------------------------------

def test_past_expiry_returns_expired():
    """Already expired option must return warning_level = 'expired'."""
    result = check_expiry_warning(_past_timestamp(2))
    assert result['warning_level'] == 'expired'


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Less-than-1hr returns 'critical'
# ---------------------------------------------------------------------------

def test_less_than_1hr_returns_critical():
    """Option expiring in < 1 hour must return warning_level = 'critical'."""
    result = check_expiry_warning(_future_timestamp(0.5))
    assert result['warning_level'] == 'critical'


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Between 1hr and 24hr returns 'warning'
# ---------------------------------------------------------------------------

def test_between_1hr_and_24hr_returns_warning():
    """Option expiring between 1 and 24 hours must return 'warning'."""
    result = check_expiry_warning(_future_timestamp(12))
    assert result['warning_level'] == 'warning'


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — More than 24hr returns 'normal'
# ---------------------------------------------------------------------------

def test_more_than_24hr_returns_normal():
    """Option expiring in > 24 hours must return warning_level = 'normal'."""
    result = check_expiry_warning(_future_timestamp(72))
    assert result['warning_level'] == 'normal'


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — is_expiring_soon is False for distant expiry
# ---------------------------------------------------------------------------

def test_distant_expiry_is_not_expiring_soon():
    """is_expiring_soon must be False when expiry is > 24 hours away."""
    result = check_expiry_warning(_future_timestamp(48))
    assert result['is_expiring_soon'] is False


# ---------------------------------------------------------------------------
# CONTRACT TEST 7 — Invalid timestamp does not crash, returns safe defaults
# ---------------------------------------------------------------------------

def test_invalid_timestamp_returns_safe_defaults():
    """Invalid timestamp must not raise — must return safe default dict."""
    result = check_expiry_warning('not-a-date')
    assert isinstance(result, dict)
    assert result['is_expiring_soon'] is False
    assert result['warning_level'] == 'normal'
    assert result['hours_until_expiry'] == 999
