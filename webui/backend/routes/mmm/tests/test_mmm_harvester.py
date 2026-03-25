"""
Test MMM Harvester — M1 Profit Harvesting + M3 Asymmetry Rebalancing.

Tests:
  - get_effective_harvest_params: threshold relaxation at extreme/moderate asymmetry
  - get_effective_harvest_params: disabled rebalancing returns {}
  - get_effective_harvest_params: no boost when lots are balanced
  - scan_harvestable_positions: basic eligibility (profit_pct, age, pressure)
  - scan_harvestable_positions: harvest_enabled=False returns []
  - scan_harvestable_positions: pressure below threshold skips side
  - scan_harvestable_positions: young position skipped (harvest_min_age_mins)
  - scan_harvestable_positions: position below profit threshold skipped
  - scan_harvestable_positions: M3 override relaxes thresholds
  - scan_harvestable_positions: sorted by harvest_score descending
  - scan_harvestable_positions: _being_closed positions skipped
  - scan_harvestable_positions: zero/negative premium skipped
  - scan_harvestable_positions: both sides scanned independently

Created: March 3, 2026
"""

import sys
import os
import types
import importlib
import importlib.util
import pytest
from copy import deepcopy
from datetime import datetime, timezone, timedelta

# ─── Direct module loader (bypasses routes/__init__.py) ───────────────────────
_MMM_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _setup_mmm_package():
    if 'webui.backend.routes.mmm' in sys.modules:
        return
    for name in ['webui', 'webui.backend', 'webui.backend.routes',
                 'webui.backend.routes.mmm']:
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = []
            pkg.__package__ = name
            sys.modules[name] = pkg
    sys.modules['webui.backend.routes.mmm'].__path__ = [_MMM_PKG_DIR]


def _load_mmm_module(name):
    full_name = f'webui.backend.routes.mmm.{name}'
    if full_name in sys.modules:
        return sys.modules[full_name]
    path = os.path.join(_MMM_PKG_DIR, f'{name}.py')
    spec = importlib.util.spec_from_file_location(
        full_name, path, submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'webui.backend.routes.mmm'
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_setup_mmm_package()
_load_mmm_module('mmm_constants')
_harvester = _load_mmm_module('mmm_harvester')

get_effective_harvest_params = _harvester.get_effective_harvest_params
scan_harvestable_positions = _harvester.scan_harvestable_positions


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _ago_iso(minutes=60):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _make_session(
    ce_total=80, pe_total=10, max_lots=100,
    harvest_enabled=True, harvest_profit_pct=40.0,
    harvest_min_age_mins=30, harvest_max_per_beat=3,
    harvest_pressure_threshold=0.7, rebalance_enabled=True,
    rebalance_asymmetry_threshold=5.0, rebalance_pressure_threshold=0.8,
    ce_frozen=None, pe_frozen=None,
):
    """Create session with defaults geared toward harvest testing."""
    return {
        'session_id': 'test-harvest-001',
        'strategy_status': 'RUNNING',
        'params': {
            'max_lots_per_side': max_lots,
            'harvest_enabled': harvest_enabled,
            'harvest_profit_pct': harvest_profit_pct,
            'harvest_min_age_mins': harvest_min_age_mins,
            'harvest_max_per_beat': harvest_max_per_beat,
            'harvest_pressure_threshold': harvest_pressure_threshold,
            'rebalance_enabled': rebalance_enabled,
            'rebalance_asymmetry_threshold': rebalance_asymmetry_threshold,
            'rebalance_pressure_threshold': rebalance_pressure_threshold,
        },
        'ce': {
            'total_lots': ce_total,
            'active_lots': ce_total,
            'frozen_positions': ce_frozen or [],
            'positions': [],
        },
        'pe': {
            'total_lots': pe_total,
            'active_lots': pe_total,
            'frozen_positions': pe_frozen or [],
            'positions': [],
        },
    }


def _make_frozen(strike=95000, entry_premium=100.0, lots=10, type_='adjustment',
                 age_mins=60, pos_id='fp-001'):
    """Create a frozen position dict."""
    return {
        'strike': strike,
        'entry_premium': entry_premium,
        'lots': lots,
        'type': type_,
        'frozen_at': _ago_iso(age_mins),
        '_pos_id': pos_id,
    }


# =============================================================================
# Tests: get_effective_harvest_params (M3)
# =============================================================================

class TestGetEffectiveHarvestParams:
    """M3 asymmetry threshold relaxation."""

    def test_extreme_asymmetry_boosts(self):
        """When CE >> PE and near cap, extreme boost activates."""
        session = _make_session(ce_total=90, pe_total=5, max_lots=100)
        result = get_effective_harvest_params(session, 'ce')

        assert result['_boosted'] is True
        assert result['_boost_level'] == 'extreme'
        assert result['harvest_profit_pct'] < 40.0  # Relaxed from default
        assert result['harvest_max_per_beat'] == 5
        assert result['harvest_pressure_threshold'] == 0.3

    def test_moderate_asymmetry_boosts(self):
        """When CE somewhat > PE, moderate boost activates."""
        session = _make_session(ce_total=70, pe_total=15, max_lots=100)
        # asymmetry = 70/15 ≈ 4.67, threshold*0.6 = 3.0 → moderate
        # pressure = 0.7 > 0.6 → passes
        result = get_effective_harvest_params(session, 'ce')

        assert result['_boosted'] is True
        assert result['_boost_level'] == 'moderate'

    def test_balanced_lots_no_boost(self):
        """When lots are similar, no boost."""
        session = _make_session(ce_total=30, pe_total=25, max_lots=100)
        result = get_effective_harvest_params(session, 'ce')

        assert result == {}

    def test_rebalance_disabled_no_boost(self):
        """rebalance_enabled=False → always empty."""
        session = _make_session(
            ce_total=90, pe_total=5, max_lots=100,
            rebalance_enabled=False,
        )
        result = get_effective_harvest_params(session, 'ce')

        assert result == {}

    def test_pe_side_boost(self):
        """M3 works symmetrically for PE dominance."""
        session = _make_session(ce_total=5, pe_total=90, max_lots=100)
        result = get_effective_harvest_params(session, 'pe')

        assert result['_boosted'] is True

    def test_high_asymmetry_but_low_pressure(self):
        """Asymmetry alone is not enough — pressure must exceed threshold."""
        session = _make_session(ce_total=20, pe_total=2, max_lots=100)
        # asymmetry = 10 > 5 (threshold), but pressure = 0.2 < 0.8
        result = get_effective_harvest_params(session, 'ce')

        assert result == {}

    def test_zero_other_side(self):
        """other_lots=0 → asymmetry = my/1 = my (safe, no div-by-zero)."""
        session = _make_session(ce_total=90, pe_total=0, max_lots=100)
        result = get_effective_harvest_params(session, 'ce')

        assert result['_boosted'] is True

    def test_profit_pct_floor(self):
        """Extreme boost has floor of 20% even with very low base."""
        session = _make_session(
            ce_total=90, pe_total=5, max_lots=100,
            harvest_profit_pct=25.0,  # base = 25, 25*0.6 = 15 → clamped to 20
        )
        result = get_effective_harvest_params(session, 'ce')

        assert result['harvest_profit_pct'] == 20.0  # Floor applied


# =============================================================================
# Tests: scan_harvestable_positions
# =============================================================================

class TestScanHarvestablePositions:
    """M1 eligibility scan."""

    def _premium_fetcher(self, premiums_map):
        """Return a callable that maps (strike, option_type) → premium."""
        def fetch(strike, option_type):
            return premiums_map.get(strike, None)
        return fetch

    def test_basic_eligible_position(self):
        """Position with 60% profit, old enough, at pressure → harvestable."""
        frozen = _make_frozen(
            strike=95000, entry_premium=100.0, lots=10, age_mins=60,
        )
        session = _make_session(
            ce_total=80, pe_total=10, max_lots=100,
            harvest_profit_pct=40.0, harvest_pressure_threshold=0.7,
            ce_frozen=[frozen],
        )
        fetch = self._premium_fetcher({95000: 40.0})  # 60% profit

        result = scan_harvestable_positions(session, fetch)

        assert len(result) == 1
        assert result[0]['strike'] == 95000
        assert result[0]['_profit_pct'] == pytest.approx(60.0, rel=0.01)
        assert result[0]['type'] == 'frozen'
        assert result[0]['side'] == 'ce'

    def test_disabled_returns_empty(self):
        """harvest_enabled=False → always []."""
        frozen = _make_frozen(strike=95000, entry_premium=100.0)
        session = _make_session(
            ce_total=80, harvest_enabled=False, ce_frozen=[frozen],
        )
        fetch = self._premium_fetcher({95000: 10.0})

        result = scan_harvestable_positions(session, fetch)

        assert result == []

    def test_pressure_below_threshold_skips(self):
        """Low capacity pressure → side skipped entirely."""
        frozen = _make_frozen(strike=95000, entry_premium=100.0)
        session = _make_session(
            ce_total=30, max_lots=100,  # pressure=0.3 < 0.7 threshold
            harvest_pressure_threshold=0.7, ce_frozen=[frozen],
        )
        fetch = self._premium_fetcher({95000: 10.0})

        result = scan_harvestable_positions(session, fetch)

        assert result == []

    def test_young_position_skipped(self):
        """Position younger than harvest_min_age_mins is skipped."""
        frozen = _make_frozen(
            strike=95000, entry_premium=100.0, age_mins=5,  # Only 5 mins old
        )
        session = _make_session(
            ce_total=80, harvest_min_age_mins=30, ce_frozen=[frozen],
        )
        fetch = self._premium_fetcher({95000: 10.0})

        result = scan_harvestable_positions(session, fetch)

        assert result == []

    def test_profit_below_threshold_skipped(self):
        """Position not profitable enough → skipped."""
        frozen = _make_frozen(
            strike=95000, entry_premium=100.0, age_mins=60,
        )
        session = _make_session(
            ce_total=80, harvest_profit_pct=40.0, ce_frozen=[frozen],
        )
        # Only 20% profit → below 40% threshold
        fetch = self._premium_fetcher({95000: 80.0})

        result = scan_harvestable_positions(session, fetch)

        assert result == []

    def test_being_closed_skipped(self):
        """Positions with _being_closed in-flight guard are skipped."""
        frozen = _make_frozen(
            strike=95000, entry_premium=100.0, pos_id='fp-123',
        )
        session = _make_session(ce_total=80, ce_frozen=[frozen])
        # Mark as _being_closed in the positions ledger
        session['ce']['positions'] = [{'id': 'fp-123', '_being_closed': True}]
        fetch = self._premium_fetcher({95000: 10.0})

        result = scan_harvestable_positions(session, fetch)

        assert result == []

    def test_zero_premium_fetch_skipped(self):
        """Premium fetch returns 0 or None → skipped."""
        frozen = _make_frozen(strike=95000, entry_premium=100.0)
        session = _make_session(ce_total=80, ce_frozen=[frozen])
        fetch = self._premium_fetcher({95000: 0})

        result = scan_harvestable_positions(session, fetch)

        assert result == []

    def test_both_sides_scanned(self):
        """Both CE and PE frozen positions are evaluated."""
        ce_frozen = _make_frozen(
            strike=95000, entry_premium=100.0, pos_id='ce-fp',
        )
        pe_frozen = _make_frozen(
            strike=85000, entry_premium=80.0, pos_id='pe-fp',
        )
        session = _make_session(
            ce_total=80, pe_total=80, max_lots=100,
            ce_frozen=[ce_frozen], pe_frozen=[pe_frozen],
        )
        fetch = self._premium_fetcher({95000: 30.0, 85000: 20.0})

        result = scan_harvestable_positions(session, fetch)

        sides = {r['side'] for r in result}
        assert 'ce' in sides
        assert 'pe' in sides
        assert len(result) == 2

    def test_sorted_by_harvest_score_descending(self):
        """Results sorted by _harvest_score (profit_pct * lot_weight) desc."""
        frozen_a = _make_frozen(
            strike=95000, entry_premium=100.0, lots=10, pos_id='a',
        )
        frozen_b = _make_frozen(
            strike=96000, entry_premium=200.0, lots=20, pos_id='b',
        )
        session = _make_session(
            ce_total=80, max_lots=100,
            ce_frozen=[frozen_a, frozen_b],
        )
        # a: 70% profit, 10/80 weight → score = 70 * 0.125 = 8.75
        # b: 90% profit, 20/80 weight → score = 90 * 0.25  = 22.5
        fetch = self._premium_fetcher({95000: 30.0, 96000: 20.0})

        result = scan_harvestable_positions(session, fetch)

        assert len(result) == 2
        assert result[0]['_pos_id'] == 'b'  # Higher score first
        assert result[1]['_pos_id'] == 'a'

    def test_m3_override_relaxes_thresholds(self):
        """With extreme asymmetry, thresholds are relaxed to catch more."""
        frozen = _make_frozen(
            strike=95000, entry_premium=100.0, lots=10,
        )
        # 25% profit — would fail default 40% threshold
        # But with M3 extreme boost, threshold relaxes to ~24% (40 * 0.6)
        session = _make_session(
            ce_total=90, pe_total=5, max_lots=100,
            harvest_profit_pct=40.0,
            rebalance_asymmetry_threshold=5.0,
            rebalance_pressure_threshold=0.8,
            ce_frozen=[frozen],
        )
        fetch = self._premium_fetcher({95000: 75.0})  # 25% profit

        result = scan_harvestable_positions(session, fetch)

        assert len(result) == 1
        assert result[0]['_asymmetry_boosted'] is True

    def test_premium_fetch_exception_skips_gracefully(self):
        """If fetch_premium_fn raises, position is skipped (no crash)."""
        frozen = _make_frozen(strike=95000, entry_premium=100.0)
        session = _make_session(ce_total=80, ce_frozen=[frozen])

        def bad_fetch(strike, option_type):
            raise ConnectionError("Exchange down")

        result = scan_harvestable_positions(session, bad_fetch)

        assert result == []

    def test_empty_frozen_positions(self):
        """No frozen positions → empty result."""
        session = _make_session(ce_total=80, ce_frozen=[], pe_frozen=[])
        fetch = self._premium_fetcher({})

        result = scan_harvestable_positions(session, fetch)

        assert result == []

    def test_harvest_score_calculation(self):
        """Verify harvest_score = profit_pct * (lots / total_side_lots)."""
        frozen = _make_frozen(
            strike=95000, entry_premium=100.0, lots=20,
        )
        session = _make_session(ce_total=80, max_lots=100, ce_frozen=[frozen])
        # 50% profit, 20/80 weight → score = 50 * 0.25 = 12.5
        fetch = self._premium_fetcher({95000: 50.0})

        result = scan_harvestable_positions(session, fetch)

        assert len(result) == 1
        assert result[0]['_harvest_score'] == pytest.approx(12.5, rel=0.01)

    def test_profit_usd_calculation(self):
        """Verify profit field uses Decimal arithmetic: (entry - current) * lots * LOT_SIZE."""
        frozen = _make_frozen(
            strike=95000, entry_premium=100.0, lots=10,
        )
        session = _make_session(ce_total=80, max_lots=100, ce_frozen=[frozen])
        fetch = self._premium_fetcher({95000: 40.0})  # 60% profit

        result = scan_harvestable_positions(session, fetch)

        # profit = (100 - 40) * 10 * 0.001 = 60 * 0.01 = 0.6 BTC
        assert len(result) == 1
        assert result[0]['profit'] == pytest.approx(0.6, rel=0.01)

    def test_invalid_frozen_at_still_proceeds(self):
        """If frozen_at timestamp is unparseable, position still proceeds."""
        frozen = _make_frozen(strike=95000, entry_premium=100.0, lots=10)
        frozen['frozen_at'] = 'not-a-timestamp'
        session = _make_session(ce_total=80, max_lots=100, ce_frozen=[frozen])
        fetch = self._premium_fetcher({95000: 30.0})

        result = scan_harvestable_positions(session, fetch)

        assert len(result) == 1

    def test_no_frozen_at_field_still_proceeds(self):
        """If frozen_at is missing/empty, age check is skipped (proceeds)."""
        frozen = _make_frozen(strike=95000, entry_premium=100.0, lots=10)
        frozen['frozen_at'] = ''
        session = _make_session(ce_total=80, max_lots=100, ce_frozen=[frozen])
        fetch = self._premium_fetcher({95000: 30.0})

        result = scan_harvestable_positions(session, fetch)

        assert len(result) == 1
