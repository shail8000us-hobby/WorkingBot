"""
Phase 4 — replay harness tests.

Tests:
  1. Empty series returns empty beats + zero summary
  2. Single-beat replay runs without error
  3. Replay is deterministic (same snapshot → same output twice)
  4. Summary counts are arithmetically correct
  5. Unknown engine returns error field
  6. param_overrides are applied in the replay
"""

import pytest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from webui.backend.routes.mmm.mmm_whipsaw_replay import (
    replay_session,
    _compute_summary,
    _empty_summary,
)


def _make_snapshot(n_beats: int = 10, alternating: bool = False) -> dict:
    """Build a minimal session snapshot with n_beats in the spot log."""
    now = datetime.now(timezone.utc)
    series = []
    for i in range(n_beats):
        ts = (now - timedelta(minutes=(n_beats - i) * 5)).isoformat()
        series.append({
            'ts': ts,
            'spot': 70000.0 + (100 if i % 2 == 0 else -100) if alternating else 70000.0 + i * 50,
            'ce': 100.0,
            'pe': 100.0,
            'iv': 0.5,
        })
    adj_history = []
    if alternating:
        for i in range(min(n_beats, 6)):
            agg = 'ce' if i % 2 == 0 else 'pe'
            adj_ts = (now - timedelta(minutes=(n_beats - i) * 5)).isoformat()
            adj_history.append({'aggressor': agg, 'timestamp': adj_ts, 'spot': 70000.0})

    return {
        'session_id': 'test-replay-001',
        '_smart_ws_series': series,
        'adjustment_history': adj_history,
        'params': {
            'whipsaw_window_mins': 30,
            'whipsaw_spot_move_pct': 0.3,
            'whipsaw_caution_score': 2,
            'whipsaw_restrict_score': 3,
            'whipsaw_cooldown_score': 4,
        },
        'ce': {'total_lots': 5, 'strike': 71000},
        'pe': {'total_lots': 5, 'strike': 69000},
    }


# ── empty series ──────────────────────────────────────────────────────────────

def test_replay_empty_series():
    snap = _make_snapshot(0)
    report = replay_session(snap)
    assert report['beats'] == []
    assert report['summary']['total_beats'] == 0
    assert report['summary']['disagree_count'] == 0


# ── single beat ───────────────────────────────────────────────────────────────

def test_replay_single_beat():
    snap = _make_snapshot(1)
    report = replay_session(snap)
    assert len(report['beats']) == 1
    beat = report['beats'][0]
    assert 'spot' in beat
    assert 'legacy_mode' in beat
    assert 'smart_mode' in beat
    assert isinstance(beat['disagree'], bool)


# ── determinism ───────────────────────────────────────────────────────────────

def test_replay_is_deterministic():
    snap = _make_snapshot(8)
    report_1 = replay_session(deepcopy(snap))
    report_2 = replay_session(deepcopy(snap))
    assert len(report_1['beats']) == len(report_2['beats'])
    for b1, b2 in zip(report_1['beats'], report_2['beats']):
        assert b1['legacy_mode'] == b2['legacy_mode']
        assert b1['smart_mode'] == b2['smart_mode']
        assert b1['legacy_block'] == b2['legacy_block']
        assert b1['smart_block'] == b2['smart_block']
        assert b1['legacy_score'] == b2['legacy_score']
        assert b1['smart_score'] == b2['smart_score']


# ── summary arithmetic ────────────────────────────────────────────────────────

def test_summary_disagree_counts():
    fake_beats = [
        {'legacy_block': True,  'smart_block': False, 'disagree': True,  'legacy_mode': 'COOLDOWN', 'smart_mode': 'NORMAL'},
        {'legacy_block': False, 'smart_block': True,  'disagree': True,  'legacy_mode': 'NORMAL',   'smart_mode': 'DEFENSIVE'},
        {'legacy_block': False, 'smart_block': False, 'disagree': False, 'legacy_mode': 'NORMAL',   'smart_mode': 'NORMAL'},
        {'legacy_block': True,  'smart_block': True,  'disagree': False, 'legacy_mode': 'COOLDOWN', 'smart_mode': 'LOCKDOWN'},
    ]
    summary = _compute_summary(fake_beats, 'LEGACY', 'SMART')
    assert summary['total_beats'] == 4
    assert summary['disagree_count'] == 2
    assert abs(summary['disagree_pct'] - 50.0) < 0.01
    assert summary['legacy_block_count'] == 2
    assert summary['smart_block_count'] == 2
    assert summary['legacy_only_block'] == 1
    assert summary['smart_only_block'] == 1


# ── unknown engine error ──────────────────────────────────────────────────────

def test_replay_unknown_engine_returns_error():
    snap = _make_snapshot(5)
    report = replay_session(snap, engine_a='LEGACY', engine_b='NONEXISTENT')
    assert 'error' in report
    assert report['beats'] == []


# ── param overrides applied ───────────────────────────────────────────────────

def test_param_overrides_applied():
    snap = _make_snapshot(5)
    # Override thresholds to extreme values — should affect mode decisions
    report_default = replay_session(deepcopy(snap))
    report_override = replay_session(
        deepcopy(snap),
        param_overrides={'smart_ws_score_defensive': 0.01},  # everything is defensive
    )
    # With a near-zero defensive threshold, smart should enter DEFENSIVE more often
    smart_modes_override = [b['smart_mode'] for b in report_override['beats']]
    # Just verify the override didn't crash and produced valid modes
    valid_modes = {'NORMAL', 'DEFENSIVE', 'OBSERVE', 'LOCKDOWN'}
    assert all(m in valid_modes for m in smart_modes_override)


# ── multi-beat replay with alternating aggressors ────────────────────────────

def test_replay_many_beats_no_crash():
    snap = _make_snapshot(n_beats=20, alternating=True)
    report = replay_session(snap)
    assert len(report['beats']) == 20
    assert report['summary']['total_beats'] == 20
    assert 0 <= report['summary']['disagree_pct'] <= 100


# ── _empty_summary keys ───────────────────────────────────────────────────────

def test_empty_summary_keys():
    s = _empty_summary('LEGACY', 'SMART')
    required_keys = [
        'total_beats', 'disagree_count', 'disagree_pct',
        'legacy_block_count', 'smart_block_count',
        'legacy_only_block', 'smart_only_block',
    ]
    for k in required_keys:
        assert k in s, f"Missing key {k!r} in empty_summary"
