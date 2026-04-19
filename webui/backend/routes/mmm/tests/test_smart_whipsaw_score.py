"""
Phase 3 — composite score + mode boundary tests.
"""

import pytest
from webui.backend.routes.mmm.mmm_whipsaw_smart import compute_composite, mode_from_score


# ── compute_composite ────────────────────────────────────────────────────────

def test_composite_all_zero():
    assert compute_composite({}) == 0.0


def test_composite_all_one():
    scores = {
        'flip': 1.0, 'er': 1.0, 'oscillation': 1.0,
        'symmetry': 1.0, 'outcome': 1.0, 'rviv': 1.0, 'gamma': 1.0,
    }
    result = compute_composite(scores)
    assert abs(result - 1.0) < 1e-5, f"All-1 scores → composite 1.0, got {result}"


def test_composite_weights_sum_to_one():
    # weights: 0.30+0.20+0.10+0.10+0.15+0.10+0.05 = 1.00
    from webui.backend.routes.mmm.mmm_whipsaw_smart import (
        _W_FLIP, _W_ER, _W_OSCILLATION, _W_SYMMETRY, _W_OUTCOME, _W_RVIV, _W_GAMMA,
    )
    total = _W_FLIP + _W_ER + _W_OSCILLATION + _W_SYMMETRY + _W_OUTCOME + _W_RVIV + _W_GAMMA
    assert abs(total - 1.0) < 1e-9, f"Weights must sum to 1.0, got {total}"


def test_composite_flip_dominated():
    # Only flip active at weight 0.30
    scores = {'flip': 1.0}
    result = compute_composite(scores)
    assert abs(result - 0.30) < 1e-5, f"flip=1, rest=0 → 0.30, got {result}"


def test_composite_partial():
    scores = {'flip': 0.5, 'er': 0.8, 'outcome': 0.6}
    expected = 0.30 * 0.5 + 0.20 * 0.8 + 0.15 * 0.6
    result = compute_composite(scores)
    assert abs(result - expected) < 1e-5, f"Partial score mismatch: {result} vs {expected}"


def test_composite_bounded():
    # Clamped to [0, 1]
    scores = {'flip': 2.0, 'er': 3.0}  # absurd inputs
    assert compute_composite(scores) <= 1.0


# ── mode_from_score ──────────────────────────────────────────────────────────

@pytest.mark.parametrize('score,expected', [
    (0.0,   'NORMAL'),
    (0.29,  'NORMAL'),
    (0.30,  'DEFENSIVE'),
    (0.59,  'DEFENSIVE'),
    (0.60,  'OBSERVE'),
    (0.79,  'OBSERVE'),
    (0.80,  'LOCKDOWN'),
    (1.0,   'LOCKDOWN'),
])
def test_mode_boundary(score, expected):
    result = mode_from_score(score)
    assert result == expected, f"score={score} → expected {expected}, got {result}"


def test_mode_expiry_tightening_within_5min():
    # Within 5 min: defensive floor drops to 0.20, observe floor drops to 0.40
    result = mode_from_score(0.22, minutes_to_expiry=4)
    assert result == 'DEFENSIVE', f"score=0.22 with 4min expiry → DEFENSIVE, got {result}"

    result2 = mode_from_score(0.42, minutes_to_expiry=4)
    assert result2 == 'OBSERVE', f"score=0.42 with 4min expiry → OBSERVE, got {result2}"


def test_mode_expiry_tightening_within_30min():
    # Within 30 min: defensive floor drops to 0.20 (not observe)
    result = mode_from_score(0.25, minutes_to_expiry=20)
    assert result == 'DEFENSIVE', f"score=0.25 with 20min expiry → DEFENSIVE, got {result}"
    # observe threshold unchanged at 0.60
    result2 = mode_from_score(0.55, minutes_to_expiry=20)
    assert result2 == 'DEFENSIVE', f"score=0.55 with 20min expiry → still DEFENSIVE, got {result2}"
