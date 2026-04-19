"""
Phase 3 — SmartWhipsawEngine detector unit tests.

7 detectors × 3–5 scenarios each:
  - flip_counter_score
  - efficiency_ratio_score
  - oscillation_score
  - premium_symmetry_score
  - adjustment_outcome_score
  - rv_iv_divergence_score
  - gamma_zone_score
"""

import math
import pytest
from datetime import datetime, timedelta, timezone

from webui.backend.routes.mmm.mmm_whipsaw_smart import (
    flip_counter_score,
    efficiency_ratio_score,
    oscillation_score,
    premium_symmetry_score,
    adjustment_outcome_score,
    rv_iv_divergence_score,
    gamma_zone_score,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_history(*aggressors, base_mins_ago=20):
    """Build adjustment_history with given aggressor sequence."""
    now = datetime.now(timezone.utc)
    return [
        {
            'aggressor': a,
            'timestamp': (now - timedelta(minutes=base_mins_ago - i * 2)).isoformat(),
            'spot': 70000.0,
        }
        for i, a in enumerate(aggressors)
    ]


# ── flip_counter_score ───────────────────────────────────────────────────────

def test_flip_no_history():
    assert flip_counter_score({'adjustment_history': []}) == 0.0


def test_flip_no_flips_same_side():
    s = {'adjustment_history': _make_history('ce', 'ce', 'ce')}
    score = flip_counter_score(s)
    assert score == 0.0, f"No flips → score 0, got {score}"


def test_flip_two_flips():
    # 3 flips from 4 entries; flips are 14-18 min ago so decay reduces score
    s = {'adjustment_history': _make_history('ce', 'pe', 'ce', 'pe')}
    score = flip_counter_score(s)
    assert 0.1 < score < 0.9, f"2-3 flips → non-zero mid-range, got {score}"
    assert score > 0.0, "Any flips must produce score > 0"


def test_flip_three_flips_high_score():
    # 5 flips; older flips decay; normalised over /3 → ~0.43 at 10-18 min age
    s = {'adjustment_history': _make_history('ce', 'pe', 'ce', 'pe', 'ce', 'pe')}
    score = flip_counter_score(s)
    assert score >= 0.3, f"5 flips → significantly elevated score, got {score}"


def test_flip_outside_window_ignored():
    now = datetime.now(timezone.utc)
    old_history = [
        {'aggressor': 'ce', 'timestamp': (now - timedelta(minutes=60)).isoformat(), 'spot': 70000.0},
        {'aggressor': 'pe', 'timestamp': (now - timedelta(minutes=59)).isoformat(), 'spot': 70000.0},
    ]
    s = {'adjustment_history': old_history}
    score = flip_counter_score(s, window_mins=30.0)
    assert score == 0.0, f"Flips outside window should not count, got {score}"


# ── efficiency_ratio_score ───────────────────────────────────────────────────

def test_er_insufficient_data():
    assert efficiency_ratio_score([]) == 0.5
    assert efficiency_ratio_score([70000.0]) == 0.5


def test_er_pure_trend():
    # Monotonically rising → ER = 1 → whipsaw score = 0
    spots = [70000.0 + i * 100 for i in range(20)]
    score = efficiency_ratio_score(spots)
    assert score < 0.05, f"Pure trend → ER~1 → score~0, got {score}"


def test_er_pure_chop():
    # Alternating oscillation → ER near 0 → whipsaw score near 1
    spots = [70000.0 + (100 if i % 2 == 0 else -100) for i in range(20)]
    score = efficiency_ratio_score(spots)
    assert score > 0.7, f"Pure chop → ER~0 → score~1, got {score}"


def test_er_no_movement():
    spots = [70000.0] * 10
    score = efficiency_ratio_score(spots)
    assert score == 0.0, f"No movement → score 0 (not ranging), got {score}"


def test_er_mixed():
    spots = [70000, 70100, 69900, 70200, 69800, 70500]
    score = efficiency_ratio_score(spots)
    assert 0.2 < score < 0.8, f"Mixed market → mid-range score, got {score}"


# ── oscillation_score ────────────────────────────────────────────────────────

def test_osc_insufficient():
    assert oscillation_score([]) == 0.0
    assert oscillation_score([70000.0, 70100.0]) == 0.0


def test_osc_no_reversals():
    spots = [70000.0 + i * 50 for i in range(10)]
    assert oscillation_score(spots) == 0.0


def test_osc_many_extrema():
    spots = [70000, 70300, 69800, 70200, 69700, 70100, 69600, 70000]
    score = oscillation_score(spots, sensitivity_pct=0.15)
    assert score > 0.5, f"Many extrema → high score, got {score}"


def test_osc_sensitivity_filter():
    # Tiny oscillations below sensitivity threshold should not count
    spots = [70000.0 + (0.5 if i % 2 == 0 else -0.5) for i in range(10)]
    score = oscillation_score(spots, sensitivity_pct=0.15)
    assert score == 0.0, f"Sub-threshold oscillations → score 0, got {score}"


# ── premium_symmetry_score ───────────────────────────────────────────────────

def test_sym_no_data():
    assert premium_symmetry_score([], []) == 0.0
    assert premium_symmetry_score([100.0], [90.0]) == 0.0  # need >= 2


def test_sym_no_sign_changes():
    # CE always dominant
    ces = [100.0, 110.0, 120.0, 130.0]
    pes = [80.0,  85.0,  90.0,  95.0]
    assert premium_symmetry_score(ces, pes) == 0.0


def test_sym_four_sign_changes():
    # Dominance alternates → max score
    ces = [100, 80, 110, 75, 120]
    pes = [90, 100, 80, 110, 70]
    score = premium_symmetry_score(ces, pes)
    assert score >= 1.0, f"4+ sign changes → score 1.0, got {score}"


def test_sym_three_sign_changes():
    # dominance alternates: +, -, +, - → 3 sign-changes → score = 3/4 = 0.75
    ces = [100, 80, 110, 75]
    pes = [90, 100, 80, 110]
    score = premium_symmetry_score(ces, pes)
    assert abs(score - 0.75) < 0.01, f"3 sign changes → score 0.75, got {score}"


# ── adjustment_outcome_score ─────────────────────────────────────────────────

def test_outcome_no_history():
    assert adjustment_outcome_score({'adjustment_history': []}) == 0.0


def test_outcome_all_same_side():
    s = {'adjustment_history': _make_history('ce', 'ce', 'ce')}
    assert adjustment_outcome_score(s) == 0.0


def test_outcome_fully_alternating():
    s = {'adjustment_history': _make_history('ce', 'pe', 'ce')}
    score = adjustment_outcome_score(s, k=3)
    assert score == 1.0, f"Fully alternating → score 1.0, got {score}"


def test_outcome_partial_alternation():
    s = {'adjustment_history': _make_history('ce', 'ce', 'pe', 'ce')}
    score = adjustment_outcome_score(s, k=4)
    assert 0.2 < score < 0.8, f"Partial alternation → mid score, got {score}"


# ── rv_iv_divergence_score ───────────────────────────────────────────────────

def test_rviv_no_data():
    assert rv_iv_divergence_score([], iv_now=0.5) == 0.0
    assert rv_iv_divergence_score([70000.0], iv_now=0.5) == 0.0


def test_rviv_no_iv():
    spots = [70000.0 + i * 10 for i in range(10)]
    assert rv_iv_divergence_score(spots, iv_now=0.0) == 0.0


def test_rviv_high_rv_no_divergence():
    # Large VARYING spot moves → high std of log returns → RV >> low IV → score 0.
    # Uses alternating ±1500 so log returns are large and varied (not constant).
    spots = [70000.0 + (1500 if i % 2 == 0 else -1500) for i in range(20)]
    score = rv_iv_divergence_score(spots, iv_now=0.05, interval_mins=5.0)
    assert score == 0.0, f"High RV relative to low IV → score 0, got {score}"


def test_rviv_low_rv_high_divergence():
    # Flat spot → RV near 0, IV high → vol divergence present
    spots = [70000.0 + (0.1 if i % 2 == 0 else -0.1) for i in range(20)]
    score = rv_iv_divergence_score(spots, iv_now=0.5, interval_mins=5.0, rv_iv_floor=0.6)
    assert score > 0.5, f"Low RV relative to IV → high score, got {score}"


# ── gamma_zone_score ─────────────────────────────────────────────────────────

def test_gamma_no_strikes():
    session = {}
    score = gamma_zone_score(session, spot=70000.0, osc_score=0.8)
    assert score == 0.4, f"No strikes → osc * 0.5 = 0.4, got {score}"


def test_gamma_far_from_strike():
    # Strike 2% away → low proximity → low score
    session = {'ce': {'strike': 71400}, 'pe': {'strike': 68600}}
    score = gamma_zone_score(session, spot=70000.0, osc_score=1.0, proximity_band_pct=0.3)
    assert score < 0.3, f"Strike 2% away → low gamma score, got {score}"


def test_gamma_near_strike():
    # Strike 0.1% away, band=0.3% → proximity = (1 - 0.1/0.3) = 0.667
    # score = 0.667 * 0.9 = 0.600 exactly
    session = {'ce': {'strike': 70070}, 'pe': {'strike': 69930}}
    score = gamma_zone_score(session, spot=70000.0, osc_score=0.9, proximity_band_pct=0.3)
    assert score >= 0.6, f"Strike near → score >= 0.6, got {score}"


def test_gamma_at_strike():
    # Strike exactly at spot → proximity = 1.0 → score = osc_score
    session = {'ce': {'strike': 70000}, 'pe': {'strike': 70000}}
    osc = 0.7
    score = gamma_zone_score(session, spot=70000.0, osc_score=osc, proximity_band_pct=0.3)
    assert abs(score - osc) < 0.01, f"At strike → score ~ osc_score {osc}, got {score}"
