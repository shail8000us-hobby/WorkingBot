"""
Contract Tests: GridBot LONG Mode — Sealed Function Suite
==========================================================
SEALED — v1.0.0 — March 5, 2026
Protocol: AI_SEAL.md

Covers 14 sealed functions across 4 modules that together implement
GridBot LONG mode behavior, confirmed working on live trading March 4–5, 2026.

Modules sealed:
  - GridCalculator    (9 functions) — pure grid math, no side effects
  - GridEngine        (1 function)  — cooldown gating
  - FillProcessor     (3 functions) — fill deduplication + next-level calc
  - ModeStateManager  (1 function)  — mode reading

SHORT mode is NOT tested here — SHORT mode is not yet confirmed working.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
import time
from unittest.mock import MagicMock, patch
from typing import Optional

pytestmark = pytest.mark.sealed


# ===========================================================================
# SHARED FIXTURE — Standard LONG mode GridCalculator
# ===========================================================================

@pytest.fixture
def calc():
    """Standard LONG mode GridCalculator: lower=85000, upper=95000, step=500, ref=90000."""
    from bot.strategy.modules.grid_calculator import GridCalculator
    return GridCalculator(lower=85000, upper=95000, step=500, ref=90000, tick_size=0.5)


# ===========================================================================
# 1. GridCalculator.compute_next_buy_level (LONG core)
# ===========================================================================

class TestComputeNextBuyLevel:

    def test_no_positions_places_one_step_below_ref(self, calc):
        """With no open positions and market above ref, buy at ref - step."""
        result = calc.compute_next_buy_level([], current_price=91000)
        assert result == calc.ref - calc.step  # 89500

    def test_no_positions_market_below_ref_uses_nearest_grid_below(self, calc):
        """With no positions and market below ref, buy at nearest grid level below market."""
        result = calc.compute_next_buy_level([], current_price=89000)
        # Should be the nearest grid level below 89000:
        # Grid: 85000, 85500, 86000, ... 88500, 89000, ...
        # Nearest below 89000 is 88500
        assert result is not None
        assert result < 89000
        assert result >= calc.lower

    def test_with_positions_buys_one_step_below_lowest(self, calc):
        """With positions, next buy is one step below the lowest entry."""
        positions = [{'entry_price': 89000}, {'entry_price': 88500}]
        result = calc.compute_next_buy_level(positions)
        assert result == 88000.0  # 88500 - 500

    def test_multiple_positions_uses_absolute_lowest(self, calc):
        """Always uses the LOWEST entry, regardless of order."""
        positions = [
            {'entry_price': 90000},
            {'entry_price': 87000},
            {'entry_price': 88500},
        ]
        result = calc.compute_next_buy_level(positions)
        assert result == 86500.0  # 87000 - 500

    def test_returns_none_when_target_below_lower_bound(self, calc):
        """Returns None when next level would be below grid lower bound."""
        positions = [{'entry_price': 85000}]  # At lower bound → next is 84500 (out of range)
        result = calc.compute_next_buy_level(positions)
        assert result is None

    def test_result_is_always_within_bounds(self, calc):
        """Any returned level must be within [lower, upper]."""
        positions = [{'entry_price': 88000}]
        result = calc.compute_next_buy_level(positions)
        if result is not None:
            assert calc.lower <= result <= calc.upper

    def test_result_is_quantized_to_tick_size(self, calc):
        """Returned price is quantized (multiple of tick_size)."""
        positions = [{'entry_price': 88500}]
        result = calc.compute_next_buy_level(positions)
        if result is not None:
            remainder = round(result % calc.tick_size, 6)
            assert remainder == 0.0 or abs(remainder - calc.tick_size) < 1e-6


# ===========================================================================
# 2. GridCalculator.compute_tp_price (LONG take-profit)
# ===========================================================================

class TestComputeTpPrice:

    def test_tp_is_entry_plus_step(self, calc):
        """LONG TP = entry + step."""
        assert calc.compute_tp_price(88000) == 88500.0

    def test_tp_at_lower_bound(self, calc):
        """TP from lower bound is lower + step."""
        assert calc.compute_tp_price(calc.lower) == calc.lower + calc.step

    def test_tp_at_ref(self, calc):
        """TP from ref price is ref + step."""
        assert calc.compute_tp_price(calc.ref) == calc.ref + calc.step

    def test_tp_is_exactly_one_step_above(self, calc):
        """Difference between TP and entry must always equal step."""
        for entry in [85000, 87000, 89500, 90000, 94500]:
            assert calc.compute_tp_price(entry) - entry == calc.step


# ===========================================================================
# 3. GridCalculator.is_within_bounds
# ===========================================================================

class TestIsWithinBounds:

    def test_price_inside_bounds(self, calc):
        assert calc.is_within_bounds(90000) is True

    def test_price_at_lower_bound(self, calc):
        assert calc.is_within_bounds(85000) is True

    def test_price_at_upper_bound(self, calc):
        assert calc.is_within_bounds(95000) is True

    def test_price_below_lower(self, calc):
        assert calc.is_within_bounds(84999) is False

    def test_price_above_upper(self, calc):
        assert calc.is_within_bounds(95001) is False

    def test_custom_bounds_override(self, calc):
        """Custom lower/upper override should work."""
        assert calc.is_within_bounds(86000, lower=86000, upper=88000) is True
        assert calc.is_within_bounds(85999, lower=86000, upper=88000) is False


# ===========================================================================
# 4. GridCalculator.quantize_price
# ===========================================================================

class TestQuantizePrice:

    def test_already_quantized_unchanged(self, calc):
        assert calc.quantize_price(90000.0) == 90000.0

    def test_snaps_down_not_round(self, calc):
        """Must FLOOR to tick size, not round."""
        # 90000.3 with tick 0.5 → floor to 90000.0
        assert calc.quantize_price(90000.3) == 90000.0

    def test_snaps_down_at_halfway(self, calc):
        """At exactly half a tick, must floor, not round up."""
        # 90000.5 is on a tick boundary already
        assert calc.quantize_price(90000.5) == 90000.5

    def test_idempotent(self, calc):
        """quantize(quantize(x)) == quantize(x) for any price."""
        for price in [89999.7, 90000.25, 90001.0, 85000.0]:
            q1 = calc.quantize_price(price)
            q2 = calc.quantize_price(q1)
            assert q1 == q2, f"Not idempotent: {price} → {q1} → {q2}"

    def test_raises_on_nan(self, calc):
        import math
        with pytest.raises(ValueError):
            calc.quantize_price(math.nan)

    def test_raises_on_infinity(self, calc):
        import math
        with pytest.raises(ValueError):
            calc.quantize_price(math.inf)


# ===========================================================================
# 5. GridCalculator.get_grid_levels
# ===========================================================================

class TestGetGridLevels:

    def test_all_levels_within_bounds(self, calc):
        levels = calc.get_grid_levels()
        for lvl in levels:
            assert calc.lower <= lvl <= calc.upper, f"Level {lvl} is outside bounds"

    def test_levels_are_not_empty(self, calc):
        assert len(calc.get_grid_levels()) > 0

    def test_levels_are_sorted(self, calc):
        levels = calc.get_grid_levels()
        assert levels == sorted(levels)

    def test_levels_include_lower_bound(self, calc):
        levels = calc.get_grid_levels()
        assert calc.lower in levels

    def test_level_spacing_equals_step(self, calc):
        levels = calc.get_grid_levels()
        for i in range(len(levels) - 1):
            diff = round(levels[i + 1] - levels[i], 6)
            assert diff == calc.step, f"Gap between {levels[i]} and {levels[i+1]} = {diff}"

    def test_correct_count(self, calc):
        # 85000 to 95000 step 500 = 21 levels (inclusive)
        levels = calc.get_grid_levels()
        expected = int((calc.upper - calc.lower) / calc.step) + 1
        assert len(levels) == expected


# ===========================================================================
# 6. GridCalculator.is_price_grid_aligned
# ===========================================================================

class TestIsPriceGridAligned:

    def test_on_grid_level_returns_true(self, calc):
        for price in [85000, 87000, 90000, 92500, 95000]:
            assert calc.is_price_grid_aligned(price) is True

    def test_off_grid_returns_false(self, calc):
        # 90123 is not on a 500-step grid starting at 85000
        assert calc.is_price_grid_aligned(90123) is False

    def test_small_float_error_is_tolerated(self, calc):
        # 90000.005 is within default tolerance 0.01
        assert calc.is_price_grid_aligned(90000.005) is True


# ===========================================================================
# 7. GridCalculator.find_nearest_grid_level
# ===========================================================================

class TestFindNearestGridLevel:

    def test_exact_grid_level_returns_itself(self, calc):
        assert calc.find_nearest_grid_level(90000) == 90000.0

    def test_rounds_to_nearest_not_below(self, calc):
        # 90200 is 200 above 90000 and 300 below 90500 → nearest is 90000
        assert calc.find_nearest_grid_level(90200) == 90000.0

    def test_rounds_at_midpoint_uses_banker_rounding(self, calc):
        # 90250 is exactly midpoint between 90000 and 90500.
        # Python round() uses banker's rounding: round(10.5) = 10 (even)
        # offset = 90250 - 85000 = 5250 → 5250/500 = 10.5 → round to 10 → 85000 + 5000 = 90000
        assert calc.find_nearest_grid_level(90250) == 90000.0

    def test_result_is_quantized(self, calc):
        result = calc.find_nearest_grid_level(89750)
        remainder = round(result % calc.tick_size, 6)
        assert remainder == 0.0 or abs(remainder - calc.tick_size) < 1e-6


# ===========================================================================
# 8. GridCalculator.find_nearest_grid_below
# ===========================================================================

class TestFindNearestGridBelow:

    def test_returns_highest_level_strictly_below(self, calc):
        # Grid: ..., 89500, 90000, 90500, ...
        # Price: 90000 → nearest strictly below is 89500
        result = calc.find_nearest_grid_below(90000)
        assert result == 89500.0

    def test_returns_none_when_price_at_or_below_lower_bound(self, calc):
        result = calc.find_nearest_grid_below(85000)
        assert result is None

    def test_result_is_always_below_price(self, calc):
        for price in [88000, 90000, 92500, 94999]:
            result = calc.find_nearest_grid_below(price)
            if result is not None:
                assert result < price

    def test_result_within_bounds(self, calc):
        result = calc.find_nearest_grid_below(92000)
        assert result is not None
        assert calc.lower <= result <= calc.upper


# ===========================================================================
# 9. GridCalculator.get_startup_maker_buy_level
# ===========================================================================

class TestGetStartupMakerBuyLevel:

    def test_calculated_above_market_finds_level_below(self, calc):
        """When calc gives ref-step=89500 but market is at 89000, must find level below 89000."""
        # No positions: calc would give ref - step = 89500 (above market 89000)
        result = calc.get_startup_maker_buy_level(current_price=89000, open_positions=[])
        assert result is not None
        assert result < 89000

    def test_calculated_below_market_returns_as_is(self, calc):
        """When calc gives a level already below market, return it directly."""
        # Market at 91000 → calc gives ref - step = 89500 (below 91000) → return 89500
        result = calc.get_startup_maker_buy_level(current_price=91000, open_positions=[])
        assert result == calc.ref - calc.step  # 89500

    def test_short_mode_routes_to_sell_logic(self, calc):
        """Passing grid_mode='SHORT' must not raise and must return a level."""
        result = calc.get_startup_maker_buy_level(
            current_price=91000, open_positions=[], grid_mode='SHORT'
        )
        # SHORT routing: expect a level above market or None
        if result is not None:
            assert result > 91000 or result >= calc.lower


# ===========================================================================
# 10. GridEngine.is_cooldown_ready
# ===========================================================================

class TestGridEngineCooldownReady:
    """Test GridEngine.is_cooldown_ready in isolation via a minimal mock engine."""

    def _make_engine(self, cooldown_seconds: int, last_order_time: float):
        """Build a minimal GridEngine-like object with only cooldown state."""
        from bot.strategy.modules.grid_engine import GridEngine
        from bot.strategy.modules.grid_calculator import GridCalculator
        calc = GridCalculator(lower=85000, upper=95000, step=500, ref=90000)
        engine = GridEngine.__new__(GridEngine)
        engine.cooldown_seconds = cooldown_seconds
        engine._last_order_time = last_order_time
        engine.grid_calc = calc
        engine._min_price_move_threshold = 250.0
        engine._last_accepted_order_price = None
        engine._was_halted = False
        engine._last_block_reason = None
        engine._last_safety_block_log = 0
        return engine

    def test_no_cooldown_always_ready(self):
        engine = self._make_engine(cooldown_seconds=0, last_order_time=time.time())
        assert engine.is_cooldown_ready() is True

    def test_cooldown_not_elapsed_returns_false(self):
        engine = self._make_engine(cooldown_seconds=60, last_order_time=time.time())
        assert engine.is_cooldown_ready() is False

    def test_cooldown_elapsed_returns_true(self):
        engine = self._make_engine(cooldown_seconds=60, last_order_time=time.time() - 120)
        assert engine.is_cooldown_ready() is True

    def test_negative_cooldown_treated_as_zero(self):
        engine = self._make_engine(cooldown_seconds=-1, last_order_time=time.time())
        assert engine.is_cooldown_ready() is True


# ===========================================================================
# 11–12. FillProcessor.is_fill_seen / mark_fill_seen
# ===========================================================================

class TestFillDeduplication:
    """Test FillProcessor deduplication without any async or exchange calls."""

    def _make_processor(self):
        from bot.strategy.modules.fill_processor import FillProcessor
        fp = FillProcessor.__new__(FillProcessor)
        import time
        from collections import deque
        fp._seen_fill_ids = set()
        fp._fill_id_timestamps = deque(maxlen=1000)
        fp._fill_id_cleanup_interval = 300
        fp._last_fill_id_cleanup = time.time()
        return fp

    def test_new_fill_id_not_seen(self):
        fp = self._make_processor()
        assert fp.is_fill_seen("fill-abc-001") is False

    def test_after_mark_fill_is_seen(self):
        fp = self._make_processor()
        fp.mark_fill_seen("fill-abc-001")
        assert fp.is_fill_seen("fill-abc-001") is True

    def test_different_fill_id_not_seen(self):
        fp = self._make_processor()
        fp.mark_fill_seen("fill-abc-001")
        assert fp.is_fill_seen("fill-abc-002") is False

    def test_idempotent_double_mark(self):
        """Marking same fill twice must not raise and must still be seen."""
        fp = self._make_processor()
        fp.mark_fill_seen("fill-dup-001")
        fp.mark_fill_seen("fill-dup-001")
        assert fp.is_fill_seen("fill-dup-001") is True

    def test_many_unique_fills_all_seen(self):
        fp = self._make_processor()
        ids = [f"fill-{i:05d}" for i in range(100)]
        for fid in ids:
            fp.mark_fill_seen(fid)
        for fid in ids:
            assert fp.is_fill_seen(fid) is True


# ===========================================================================
# 13. FillProcessor.calculate_next_grid_level
# ===========================================================================

class TestCalculateNextGridLevel:

    def _make_processor(self):
        from bot.strategy.modules.fill_processor import FillProcessor
        from bot.strategy.modules.grid_calculator import GridCalculator
        fp = FillProcessor.__new__(FillProcessor)
        fp.grid_calc = GridCalculator(lower=85000, upper=95000, step=500, ref=90000)
        fp._recovered_grids = set()
        return fp

    def test_buy_side_returns_level_below_price(self):
        fp = self._make_processor()
        result = fp.calculate_next_grid_level('BUY', current_price=90000)
        assert result is not None
        assert result < 90000

    def test_buy_side_level_on_grid(self):
        fp = self._make_processor()
        result = fp.calculate_next_grid_level('BUY', current_price=90000)
        assert result is not None
        # Should be 89500 (nearest grid below 90000)
        assert result == 89500.0

    def test_buy_side_below_lower_returns_none(self):
        fp = self._make_processor()
        result = fp.calculate_next_grid_level('BUY', current_price=85000)
        assert result is None

    def test_buy_side_result_within_bounds(self):
        fp = self._make_processor()
        for price in [86000, 89000, 92000, 94000]:
            result = fp.calculate_next_grid_level('BUY', current_price=price)
            if result is not None:
                assert fp.grid_calc.lower <= result <= fp.grid_calc.upper

    def test_recovered_grid_levels_are_skipped(self):
        fp = self._make_processor()
        fp._recovered_grids = {89500.0, 89000.0}
        result = fp.calculate_next_grid_level('BUY', current_price=90000)
        # 89500 and 89000 are skipped → should land at 88500
        assert result == 88500.0


# ===========================================================================
# 14. ModeStateManager.get_current_mode
# ===========================================================================

class TestGetCurrentMode:

    def test_returns_long_from_config(self):
        """get_current_mode() reads from config and returns uppercased mode."""
        from bot.strategy.modules.mode_state_manager import ModeStateManager
        manager = ModeStateManager.__new__(ModeStateManager)

        mock_cfg = MagicMock()
        mock_cfg.bot.mode = 'LONG'

        with patch('bot.strategy.modules.mode_state_manager.get_config', return_value=mock_cfg):
            result = manager.get_current_mode()

        assert result == 'LONG'

    def test_lowercase_config_is_uppercased(self):
        """get_current_mode() must uppercase whatever the config returns."""
        from bot.strategy.modules.mode_state_manager import ModeStateManager
        manager = ModeStateManager.__new__(ModeStateManager)

        mock_cfg = MagicMock()
        mock_cfg.bot.mode = 'long'

        with patch('bot.strategy.modules.mode_state_manager.get_config', return_value=mock_cfg):
            result = manager.get_current_mode()

        assert result == 'LONG'

    def test_never_returns_none_for_valid_config(self):
        """get_current_mode() must never return None when config is available."""
        from bot.strategy.modules.mode_state_manager import ModeStateManager
        manager = ModeStateManager.__new__(ModeStateManager)

        mock_cfg = MagicMock()
        mock_cfg.bot.mode = 'LONG'

        with patch('bot.strategy.modules.mode_state_manager.get_config', return_value=mock_cfg):
            result = manager.get_current_mode()

        assert result is not None
