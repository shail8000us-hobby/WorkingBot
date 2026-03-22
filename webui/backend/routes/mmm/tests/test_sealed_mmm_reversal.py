"""
Sealed contract tests for mmm_reversal (#85)

Functions sealed:
  - detect_reversal(session, current_aggressor) → bool
  - is_cooldown_active(session) → bool
  - activate_cooldown(session) → None
  - should_skip_reversal_adjustment(session, adjustment_pnl) → (bool, str)
  - record_reversal(session, from_side, to_side) → None
  - handle_reversal_skip_transition(session, aggressor, ce_now, pe_now, fetch_premium_fn) → None

File: webui/backend/routes/mmm/mmm_reversal.py

Audit outcome (2026-03-20):
  - No bugs found.
  - compute_adjustment_pnl referenced in audit plan does not exist; replaced by
    calculate_reversal_loss in mmm_engine.py (already sealed #83).
  - should_skip_reversal_adjustment accepts session but doesn't use it — harmless.

Contracts:

  [detect_reversal — 8 contracts]
  D1.  last_aggressor absent/None → False (no prior adjustment = not a reversal)
  D2.  last_aggressor='NONE' (uppercase) → False
  D3.  last_aggressor='none' (lowercase) → False (case-insensitive)
  D4.  CE → PE transition → True (reversal)
  D5.  PE → CE transition → True (reversal)
  D6.  CE → CE (same direction) → False (continuation)
  D7.  case-insensitive same-side match → False ('ce' == 'CE')
  D8.  wind-down active → False (suppresses reversal detection)

  [is_cooldown_active — 6 contracts]
  I1.  cooldown_active=False → False immediately
  I2.  cooldown_active=True, cooldown_until=None → False, clears cooldown
  I3.  cooldown_active=True, until in future → True
  I4.  cooldown_active=True, until in past → False, clears cooldown fields
  I5.  naive timestamp (no tzinfo) → treated as UTC, handled correctly
  I6.  malformed timestamp (ValueError) → False, clears cooldown

  [activate_cooldown — 4 contracts]
  A1.  reversal_cooldown_seconds > 0 → uses that value, sets cooldown_until
  A2.  reversal_cooldown_seconds = 0 → falls back to adjustment_interval
  A3.  already in cooldown → no-op (does not re-activate)
  A4.  cooldown_until is timezone-aware UTC ISO string

  [should_skip_reversal_adjustment — 3 contracts]
  S1.  adjustment_pnl > 0 (profitable) → (True, non-empty reason)
  S2.  adjustment_pnl = 0 (break-even) → (True, non-empty reason)
  S3.  adjustment_pnl < 0 (underwater) → (False, '')

  [record_reversal — 5 contracts]
  R1.  empty history → records event, increments reversal_count to 1
  R2.  same from→to + same adj_count → deduped, count not incremented again
  R3.  same from→to + different adj_count → new record added
  R4.  different from→to direction → new record added
  R5.  history > 50 entries → capped to most recent 50

  [handle_reversal_skip_transition — 4 contracts]
  H1.  last_aggressor updated to new aggressor direction
  H2.  appends entry with type='reversal_skip' to adjustment_history
  H3.  adjustment_history capped at 200 entries
  H4.  update_trigger_snapshots called with session, ce_now, pe_now
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.sealed

from webui.backend.routes.mmm.mmm_reversal import (
    detect_reversal,
    is_cooldown_active,
    activate_cooldown,
    should_skip_reversal_adjustment,
    record_reversal,
    handle_reversal_skip_transition,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

def _session(**kwargs):
    base = {
        'params': {'adjustment_interval': 300, 'reversal_cooldown_seconds': 0},
        'adjustment_count': 0,
    }
    base.update(kwargs)
    return base


def _future_iso(seconds=600):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _past_iso(seconds=600):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


# ─── D1–D8: detect_reversal ────────────────────────────────────────────────────

def test_d1_no_last_aggressor_returns_false():
    session = _session()  # no last_aggressor key
    assert detect_reversal(session, 'ce') is False


def test_d1b_last_aggressor_none_returns_false():
    session = _session(last_aggressor=None)
    assert detect_reversal(session, 'pe') is False


def test_d2_last_aggressor_none_uppercase_returns_false():
    session = _session(last_aggressor='NONE')
    assert detect_reversal(session, 'ce') is False


def test_d3_last_aggressor_none_lowercase_returns_false():
    session = _session(last_aggressor='none')
    assert detect_reversal(session, 'pe') is False


def test_d4_ce_to_pe_is_reversal():
    session = _session(last_aggressor='CE')
    assert detect_reversal(session, 'pe') is True


def test_d5_pe_to_ce_is_reversal():
    session = _session(last_aggressor='PE')
    assert detect_reversal(session, 'ce') is True


def test_d6_same_side_is_not_reversal():
    session = _session(last_aggressor='CE')
    assert detect_reversal(session, 'ce') is False


def test_d7_case_insensitive_same_side_not_reversal():
    session = _session(last_aggressor='ce')
    assert detect_reversal(session, 'CE') is False


def test_d8_wind_down_active_suppresses_reversal():
    session = _session(last_aggressor='CE')
    with patch('webui.backend.routes.mmm.mmm_wind_down.is_wind_down_active',
               return_value=True):
        result = detect_reversal(session, 'pe')
    assert result is False


# ─── I1–I6: is_cooldown_active ─────────────────────────────────────────────────

def test_i1_cooldown_inactive_returns_false():
    session = _session(cooldown_active=False)
    assert is_cooldown_active(session) is False


def test_i2_cooldown_active_but_until_none_returns_false():
    session = _session(cooldown_active=True, cooldown_until=None)
    result = is_cooldown_active(session)
    assert result is False


def test_i3_cooldown_active_future_returns_true():
    session = _session(cooldown_active=True, cooldown_until=_future_iso(600))
    assert is_cooldown_active(session) is True


def test_i4_cooldown_active_past_returns_false_and_clears():
    session = _session(cooldown_active=True, cooldown_until=_past_iso(600))
    result = is_cooldown_active(session)
    assert result is False
    assert session['cooldown_active'] is False
    assert session['cooldown_until'] is None


def test_i5_naive_timestamp_treated_as_utc():
    # Naive ISO (no +00:00) — should still work correctly
    future_naive = (datetime.utcnow() + timedelta(seconds=600)).isoformat()
    session = _session(cooldown_active=True, cooldown_until=future_naive)
    assert is_cooldown_active(session) is True


def test_i6_malformed_timestamp_clears_cooldown():
    session = _session(cooldown_active=True, cooldown_until='not-a-date')
    result = is_cooldown_active(session)
    assert result is False
    assert session['cooldown_active'] is False


# ─── A1–A4: activate_cooldown ──────────────────────────────────────────────────

def test_a1_uses_reversal_cooldown_seconds_when_set():
    session = _session()
    session['params']['reversal_cooldown_seconds'] = 120
    activate_cooldown(session)
    assert session['cooldown_active'] is True
    until = datetime.fromisoformat(session['cooldown_until'])
    expected = datetime.now(timezone.utc) + timedelta(seconds=120)
    assert abs((until - expected).total_seconds()) < 2


def test_a2_zero_cooldown_seconds_falls_back_to_interval():
    session = _session()
    session['params']['reversal_cooldown_seconds'] = 0
    session['params']['adjustment_interval'] = 300
    activate_cooldown(session)
    assert session['cooldown_active'] is True
    until = datetime.fromisoformat(session['cooldown_until'])
    expected = datetime.now(timezone.utc) + timedelta(seconds=300)
    assert abs((until - expected).total_seconds()) < 2


def test_a3_already_in_cooldown_no_op():
    future = _future_iso(600)
    session = _session(cooldown_active=True, cooldown_until=future)
    activate_cooldown(session)
    # cooldown_until must not be changed
    assert session['cooldown_until'] == future


def test_a4_cooldown_until_is_timezone_aware_utc():
    session = _session()
    activate_cooldown(session)
    until = datetime.fromisoformat(session['cooldown_until'])
    assert until.tzinfo is not None


# ─── S1–S3: should_skip_reversal_adjustment ────────────────────────────────────

def test_s1_positive_pnl_returns_skip_true():
    skip, reason = should_skip_reversal_adjustment(_session(), 10.0)
    assert skip is True
    assert reason  # non-empty explanation


def test_s2_zero_pnl_returns_skip_true():
    skip, reason = should_skip_reversal_adjustment(_session(), 0.0)
    assert skip is True
    assert reason


def test_s3_negative_pnl_returns_skip_false():
    skip, reason = should_skip_reversal_adjustment(_session(), -5.0)
    assert skip is False
    assert reason == ''


# ─── R1–R5: record_reversal ────────────────────────────────────────────────────

def test_r1_empty_history_records_and_increments_count():
    session = _session()
    record_reversal(session, 'ce', 'pe')
    assert session['reversal_count'] == 1
    assert len(session['reversal_history']) == 1
    entry = session['reversal_history'][0]
    assert entry['from'] == 'CE'
    assert entry['to'] == 'PE'


def test_r2_same_direction_same_adj_count_deduped():
    session = _session(adjustment_count=5)
    record_reversal(session, 'ce', 'pe')
    record_reversal(session, 'ce', 'pe')  # duplicate
    assert session['reversal_count'] == 1
    assert len(session['reversal_history']) == 1


def test_r3_same_direction_different_adj_count_new_record():
    session = _session(adjustment_count=5)
    record_reversal(session, 'ce', 'pe')
    session['adjustment_count'] = 6  # new adjustment happened
    record_reversal(session, 'ce', 'pe')
    assert session['reversal_count'] == 2
    assert len(session['reversal_history']) == 2


def test_r4_different_direction_new_record():
    session = _session(adjustment_count=5)
    record_reversal(session, 'ce', 'pe')
    record_reversal(session, 'pe', 'ce')  # opposite direction
    assert session['reversal_count'] == 2
    assert len(session['reversal_history']) == 2


def test_r5_history_capped_at_50():
    session = _session()
    # Record 60 reversals alternating direction with different adj counts
    for i in range(60):
        session['adjustment_count'] = i
        from_side = 'ce' if i % 2 == 0 else 'pe'
        to_side = 'pe' if i % 2 == 0 else 'ce'
        record_reversal(session, from_side, to_side)
    assert len(session['reversal_history']) == 50
    # reversal_count still tracks total (not capped)
    assert session['reversal_count'] == 60


# ─── H1–H4: handle_reversal_skip_transition ────────────────────────────────────

def test_h1_last_aggressor_updated_to_new_direction():
    session = _session(last_aggressor='CE')
    with patch('webui.backend.routes.mmm.mmm_reversal.update_trigger_snapshots'):
        handle_reversal_skip_transition(session, 'pe', 50.0, 45.0)
    assert session['last_aggressor'] == 'PE'


def test_h2_appends_reversal_skip_to_adjustment_history():
    session = _session()
    with patch('webui.backend.routes.mmm.mmm_reversal.update_trigger_snapshots'):
        handle_reversal_skip_transition(session, 'ce', 50.0, 45.0)
    history = session.get('adjustment_history', [])
    assert len(history) == 1
    assert history[0]['type'] == 'reversal_skip'
    assert history[0]['aggressor'] == 'CE'


def test_h3_adjustment_history_capped_at_200():
    session = _session(adjustment_history=[{'type': 'x'}] * 200)
    with patch('webui.backend.routes.mmm.mmm_reversal.update_trigger_snapshots'):
        handle_reversal_skip_transition(session, 'pe', 50.0, 45.0)
    assert len(session['adjustment_history']) == 200  # new entry replaces oldest


def test_h4_calls_update_trigger_snapshots_with_prices():
    session = _session()
    mock_fn = MagicMock()
    with patch('webui.backend.routes.mmm.mmm_reversal.update_trigger_snapshots') as mock_uts:
        handle_reversal_skip_transition(session, 'ce', 52.0, 48.0,
                                        fetch_premium_fn=mock_fn)
    mock_uts.assert_called_once_with(session, 52.0, 48.0, fetch_premium_fn=mock_fn)
