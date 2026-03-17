"""
Sealed contract tests for compute_adaptive_interval + compute_adaptive_interval_v2 (#78)

Functions: compute_adaptive_interval(base_interval, hours_to_expiry, enabled=True)
           compute_adaptive_interval_v2(base_interval, hours_to_expiry, total_dte_hours, enabled=True)
Tied to param: adjustment_interval

compute_adaptive_interval — 0DTE absolute-hours tiers:
  >30h    → 1.00x
  20-30h  → 0.83x
  10-20h  → 0.50x
  5-10h   → 0.30x
  3-5h    → 0.20x
  1-3h    → 0.10x
  0.5-1h  → floor=30s (multiplier returned as 0)
  <0.5h   → floor=30s (theta zone)
  disabled/None/<=0 → base_interval, adaptive=False

compute_adaptive_interval_v2 — multi-DTE percentage-based tiers:
  >80% remaining   → 1.50x
  50-80% remaining → 1.00x
  20-50% remaining → 0.70x
  5-20% remaining  → 0.50x
  <5%  remaining   → 0.30x
  <0.5h remaining  → floor=30s (theta zone)
  total_dte_hours<=0 → fallback: total=max(hours, 24)

Both: effective_interval never below ADAPTIVE_INTERVAL_FLOOR (30s)

Confirmed working: adjustment_interval param drives heartbeat frequency on all sessions
"""

import pytest
from webui.backend.routes.mmm.mmm_trigger import (
    compute_adaptive_interval,
    compute_adaptive_interval_v2,
    ADAPTIVE_INTERVAL_FLOOR,
)

BASE = 600  # typical adjustment_interval in seconds


# =============================================================================
# compute_adaptive_interval (v1 — 0DTE, absolute hours)
# =============================================================================

# ── Disabled / invalid inputs ─────────────────────────────────────────────────

@pytest.mark.sealed
def test_v1_disabled_returns_base_interval():
    r = compute_adaptive_interval(BASE, 15.0, enabled=False)
    assert r['adaptive'] is False
    assert r['effective_interval'] == BASE
    assert r['multiplier'] == 1.0
    assert r['tier_label'] == 'manual'


@pytest.mark.sealed
def test_v1_hours_none_returns_base_interval():
    r = compute_adaptive_interval(BASE, None)
    assert r['adaptive'] is False
    assert r['effective_interval'] == BASE


@pytest.mark.sealed
def test_v1_hours_zero_returns_base_interval():
    r = compute_adaptive_interval(BASE, 0)
    assert r['adaptive'] is False
    assert r['effective_interval'] == BASE


@pytest.mark.sealed
def test_v1_hours_negative_returns_base_interval():
    r = compute_adaptive_interval(BASE, -5.0)
    assert r['adaptive'] is False
    assert r['effective_interval'] == BASE


# ── Tier correctness ──────────────────────────────────────────────────────────

@pytest.mark.sealed
def test_v1_tier_gt30h():
    r = compute_adaptive_interval(BASE, 40.0)
    assert r['adaptive'] is True
    assert r['multiplier'] == 1.00
    assert r['tier_label'] == '>30h'
    assert r['effective_interval'] == max(ADAPTIVE_INTERVAL_FLOOR, int(BASE * 1.00))


@pytest.mark.sealed
def test_v1_tier_boundary_30h_exactly():
    # 30 >= 30 and 30 < inf → '>30h' tier (not 20-30h)
    r = compute_adaptive_interval(BASE, 30.0)
    assert r['tier_label'] == '>30h'
    assert r['multiplier'] == 1.00


@pytest.mark.sealed
def test_v1_tier_20_to_30h():
    r = compute_adaptive_interval(BASE, 25.0)
    assert r['multiplier'] == pytest.approx(0.83)
    assert r['tier_label'] == '20-30h'
    assert r['effective_interval'] == max(ADAPTIVE_INTERVAL_FLOOR, int(BASE * 0.83))


@pytest.mark.sealed
def test_v1_tier_10_to_20h():
    r = compute_adaptive_interval(BASE, 15.0)
    assert r['multiplier'] == pytest.approx(0.50)
    assert r['tier_label'] == '10-20h'


@pytest.mark.sealed
def test_v1_tier_5_to_10h():
    r = compute_adaptive_interval(BASE, 7.0)
    assert r['multiplier'] == pytest.approx(0.30)
    assert r['tier_label'] == '5-10h'


@pytest.mark.sealed
def test_v1_tier_3_to_5h():
    r = compute_adaptive_interval(BASE, 4.0)
    assert r['multiplier'] == pytest.approx(0.20)
    assert r['tier_label'] == '3-5h'


@pytest.mark.sealed
def test_v1_tier_1_to_3h():
    r = compute_adaptive_interval(BASE, 2.0)
    assert r['multiplier'] == pytest.approx(0.10)
    assert r['tier_label'] == '1-3h'
    assert r['effective_interval'] == max(ADAPTIVE_INTERVAL_FLOOR, int(BASE * 0.10))


@pytest.mark.sealed
def test_v1_tier_30m_to_1h_floor():
    r = compute_adaptive_interval(BASE, 0.75)
    assert r['adaptive'] is True
    assert r['effective_interval'] == ADAPTIVE_INTERVAL_FLOOR
    assert r['multiplier'] == 0   # None → 0 in output
    assert r['tier_label'] == '30m-1h'


@pytest.mark.sealed
def test_v1_tier_under_30m_floor():
    r = compute_adaptive_interval(BASE, 0.25)
    assert r['adaptive'] is True
    assert r['effective_interval'] == ADAPTIVE_INTERVAL_FLOOR
    assert r['multiplier'] == 0


# ── Floor guarantee ───────────────────────────────────────────────────────────

@pytest.mark.sealed
def test_v1_floor_applies_when_base_too_small():
    # base=10s, 2h tier (0.10x) → int(10*0.10)=1 → floor=30
    r = compute_adaptive_interval(10, 2.0)
    assert r['effective_interval'] == ADAPTIVE_INTERVAL_FLOOR


@pytest.mark.sealed
def test_v1_effective_never_below_floor():
    for hours in [40, 25, 15, 7, 4, 2, 0.75, 0.25]:
        r = compute_adaptive_interval(5, float(hours))
        assert r['effective_interval'] >= ADAPTIVE_INTERVAL_FLOOR, \
            f"Floor violated at {hours}h"


# =============================================================================
# compute_adaptive_interval_v2 (multi-DTE, percentage-based)
# =============================================================================

# ── Disabled / invalid inputs ─────────────────────────────────────────────────

@pytest.mark.sealed
def test_v2_disabled_returns_base_interval():
    r = compute_adaptive_interval_v2(BASE, 20.0, total_dte_hours=120.0, enabled=False)
    assert r['adaptive'] is False
    assert r['effective_interval'] == BASE
    assert r['multiplier'] == 1.0


@pytest.mark.sealed
def test_v2_hours_zero_returns_base_interval():
    r = compute_adaptive_interval_v2(BASE, 0, total_dte_hours=120.0)
    assert r['adaptive'] is False
    assert r['effective_interval'] == BASE


@pytest.mark.sealed
def test_v2_hours_negative_returns_base_interval():
    r = compute_adaptive_interval_v2(BASE, -1.0, total_dte_hours=120.0)
    assert r['adaptive'] is False


# ── Tier correctness (120h total DTE = 5DTE) ─────────────────────────────────

@pytest.mark.sealed
def test_v2_tier_gt80pct():
    # 100h / 120h = 83% → >80% tier, 1.50x
    r = compute_adaptive_interval_v2(BASE, 100.0, total_dte_hours=120.0)
    assert r['adaptive'] is True
    assert r['multiplier'] == pytest.approx(1.50)
    assert r['tier_label'] == '>80% remaining'
    assert r['effective_interval'] == max(ADAPTIVE_INTERVAL_FLOOR, int(BASE * 1.50))


@pytest.mark.sealed
def test_v2_tier_50_to_80pct():
    # 72h / 120h = 60% → 50-80% tier, 1.00x
    r = compute_adaptive_interval_v2(BASE, 72.0, total_dte_hours=120.0)
    assert r['multiplier'] == pytest.approx(1.00)
    assert r['tier_label'] == '50-80% remaining'


@pytest.mark.sealed
def test_v2_tier_20_to_50pct():
    # 36h / 120h = 30% → 20-50% tier, 0.70x
    r = compute_adaptive_interval_v2(BASE, 36.0, total_dte_hours=120.0)
    assert r['multiplier'] == pytest.approx(0.70)
    assert r['tier_label'] == '20-50% remaining'


@pytest.mark.sealed
def test_v2_tier_5_to_20pct():
    # 12h / 120h = 10% → 5-20% tier, 0.50x
    r = compute_adaptive_interval_v2(BASE, 12.0, total_dte_hours=120.0)
    assert r['multiplier'] == pytest.approx(0.50)
    assert r['tier_label'] == '5-20% remaining'


@pytest.mark.sealed
def test_v2_tier_lt5pct():
    # 3h / 120h = 2.5% → <5% tier, 0.30x
    r = compute_adaptive_interval_v2(BASE, 3.0, total_dte_hours=120.0)
    assert r['multiplier'] == pytest.approx(0.30)
    assert r['tier_label'] == '<5% remaining'


@pytest.mark.sealed
def test_v2_theta_zone_under_30min():
    # < 0.5h → theta zone floor
    r = compute_adaptive_interval_v2(BASE, 0.25, total_dte_hours=120.0)
    assert r['adaptive'] is True
    assert r['effective_interval'] == ADAPTIVE_INTERVAL_FLOOR
    assert r['multiplier'] == 0


# ── total_dte_hours guard ─────────────────────────────────────────────────────

@pytest.mark.sealed
def test_v2_zero_total_dte_uses_fallback():
    # total_dte_hours=0 → fallback to max(hours, 24.0)
    # 10h / max(10, 24) = 10/24 ≈ 41.7% → 20-50% tier, 0.70x
    r = compute_adaptive_interval_v2(BASE, 10.0, total_dte_hours=0)
    assert r['adaptive'] is True
    assert r['multiplier'] == pytest.approx(0.70)


# ── Floor guarantee ───────────────────────────────────────────────────────────

@pytest.mark.sealed
def test_v2_effective_never_below_floor():
    for pct_h in [100, 72, 36, 12, 3]:
        r = compute_adaptive_interval_v2(5, float(pct_h), total_dte_hours=120.0)
        assert r['effective_interval'] >= ADAPTIVE_INTERVAL_FLOOR, \
            f"Floor violated at {pct_h}h"
