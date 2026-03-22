"""
Contract tests for MMMEngine.calculate_standard_loss and MMMEngine.calculate_reversal_loss

SEALED — v1.0.0 — March 20, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Methods:
  MMMEngine.calculate_standard_loss(session, aggressor_side, premium_now, fetch_premium_fn=None)
      → (total_loss: float, calculation_incomplete: bool)

  MMMEngine.calculate_reversal_loss(session, aggressor_side, fetch_premium_fn)
      → (loss_to_cover: float, adjustment_pnl: float, calculation_incomplete: bool)

File: webui/backend/routes/mmm/mmm_engine.py

--- calculate_standard_loss contracts ---

C-SL-1:  Basic active loss only (no frozen positions, no fetch_premium_fn)
           loss = (premium_now - trigger) × active_lots × LOT_SIZE_BTC
C-SL-2:  Active + positive frozen loss → both summed
C-SL-3:  Frozen position with GAIN is NOT counted (pos_loss <= 0 skipped)
C-SL-4:  trigger=0 or missing → (0.0, True) — prevents phantom over-hedge
C-SL-5:  fetch_premium_fn=None + frozen positions exist → (active_loss, True)
           conservative: can't price frozen, marks incomplete
C-SL-6:  fetch_premium_fn=None + no frozen positions → (active_loss, False)
           complete result — no frozen to miss
C-SL-7:  fetch_premium_fn raises exception → position skipped, incomplete=True
C-SL-8:  fetch_premium_fn returns None → position skipped, incomplete=True
C-SL-9:  premium_now < trigger (price moved down) → total_loss clamped to 0.0
C-SL-10: Frozen position uses trigger_snapshot as baseline when snapshot exists
          (not entry_premium — prevents double-counting already-hedged losses)
C-SL-11: Frozen position falls back to entry_premium when no trigger_snapshot for that strike
C-SL-12: Multiple frozen positions — losses accumulate correctly

--- calculate_reversal_loss contracts ---

C-RL-1:  All adjustment fills profitable → (0.0, positive_pnl, False) — DO NOTHING
C-RL-2:  All adjustments underwater → (|loss|, negative_pnl, False) — hedge the loss
C-RL-3:  No adjustments at all → (0.0, 0.0, False) — pnl=0 is "profitable"
C-RL-4:  Original frozen positions excluded (type='original' → skip)
C-RL-5:  Frozen adjustment positions included (type='standard' → counted)
C-RL-6:  fetch_premium_fn raises → position skipped, incomplete=True
C-RL-7:  Mixed fills: net profitable → (0.0, pnl, False)
C-RL-8:  Mixed fills: net underwater → (|loss|, pnl, False)
C-RL-9:  adj_pnl exactly 0.0 → (0.0, 0.0, False) — treated as "profitable"
C-RL-10: Active adjustment fills + frozen adjustment fills — both counted
"""

import math
import pytest
from unittest.mock import MagicMock

pytestmark = pytest.mark.sealed

LOT_SIZE_BTC = 0.001  # Mirror of mmm_constants.LOT_SIZE_BTC


def _make_engine():
    """Create MMMEngine with no live dependencies."""
    from webui.backend.routes.mmm.mmm_engine import MMMEngine
    return MMMEngine.__new__(MMMEngine)


def _side_state(
    active_strike=80000,
    trigger_value=80.0,
    active_lots=5,
    frozen_positions=None,
    adjustment_fills=None,
    extra_trigger_snapshots=None,
):
    """
    Build a per-side state dict that mimics what recompute_side_lots produces.
    trigger_snapshot keys are str(int(round(strike))) — canonical format.
    """
    ts = {str(int(active_strike)): trigger_value}
    if extra_trigger_snapshots:
        ts.update(extra_trigger_snapshots)
    return {
        'active_strike': active_strike,
        'trigger_snapshot': ts,
        'active_lots': active_lots,
        'frozen_positions': frozen_positions or [],
        'adjustment_fills': adjustment_fills or [],
    }


def _session(aggressor_side='ce', **side_kwargs):
    """Wrap side_state in a minimal session dict."""
    return {
        aggressor_side: _side_state(**side_kwargs),
        'params': {},
    }


# =============================================================================
# calculate_standard_loss
# =============================================================================

class TestCalculateStandardLoss:

    def _run(self, session, aggressor_side='ce', premium_now=100.0, fetch_fn=None):
        engine = _make_engine()
        return engine.calculate_standard_loss(session, aggressor_side, premium_now, fetch_fn)

    # C-SL-1: Basic active loss only
    def test_sl_c1_active_loss_only(self):
        """loss = (100 - 80) × 5 × 0.001 = 0.10"""
        sess = _session('ce', active_strike=80000, trigger_value=80.0, active_lots=5)
        loss, incomplete = self._run(sess, 'ce', premium_now=100.0, fetch_fn=None)
        expected = (100.0 - 80.0) * 5 * LOT_SIZE_BTC
        assert abs(loss - expected) < 1e-9
        assert incomplete is False

    # C-SL-2: Active + positive frozen loss
    def test_sl_c2_active_plus_frozen_loss(self):
        """
        active: (100-80)×5×0.001 = 0.10
        frozen: (180-150)×3×0.001 = 0.09 (trigger_snapshot=150, current=180)
        total = 0.19
        """
        frozen = [{'strike': 78000, 'lots': 3, 'entry_premium': 200.0}]
        sess = _session(
            'ce',
            active_strike=80000,
            trigger_value=80.0,
            active_lots=5,
            frozen_positions=frozen,
            extra_trigger_snapshots={'78000': 150.0},
        )

        def fetch_fn(strike, option_type):
            if int(strike) == 78000:
                return 180.0
            raise ValueError(f"Unexpected strike {strike}")

        loss, incomplete = self._run(sess, 'ce', premium_now=100.0, fetch_fn=fetch_fn)
        expected = (100.0 - 80.0) * 5 * LOT_SIZE_BTC + (180.0 - 150.0) * 3 * LOT_SIZE_BTC
        assert abs(loss - expected) < 1e-9
        assert incomplete is False

    # C-SL-3: Frozen gain NOT counted
    def test_sl_c3_frozen_gain_not_counted(self):
        """
        active: (100-80)×5×0.001 = 0.10
        frozen: current=100 < baseline=150 → pos_loss=-0.15 → skipped
        total = 0.10
        """
        frozen = [{'strike': 78000, 'lots': 3, 'entry_premium': 200.0}]
        sess = _session(
            'ce',
            active_strike=80000,
            trigger_value=80.0,
            active_lots=5,
            frozen_positions=frozen,
            extra_trigger_snapshots={'78000': 150.0},
        )

        def fetch_fn(strike, option_type):
            return 100.0  # current < baseline → gain for short → not counted

        loss, incomplete = self._run(sess, 'ce', premium_now=100.0, fetch_fn=fetch_fn)
        expected = (100.0 - 80.0) * 5 * LOT_SIZE_BTC
        assert abs(loss - expected) < 1e-9
        assert incomplete is False

    # C-SL-4: trigger=0 → (0.0, True)
    def test_sl_c4_trigger_zero_returns_incomplete(self):
        """trigger_snapshot missing or zero → (0.0, True) to prevent over-hedge."""
        # Case A: trigger_snapshot exists but value is 0
        sess = _session('ce', active_strike=80000, trigger_value=0.0, active_lots=5)
        loss, incomplete = self._run(sess, 'ce', premium_now=100.0)
        assert loss == 0.0
        assert incomplete is True

    def test_sl_c4b_trigger_missing_returns_incomplete(self):
        """trigger_snapshot dict has no entry for active_strike → default 0 → (0.0, True)."""
        sess = {
            'ce': {
                'active_strike': 80000,
                'trigger_snapshot': {},  # empty — no entry for 80000
                'active_lots': 5,
                'frozen_positions': [],
            },
            'params': {},
        }
        loss, incomplete = self._run(sess, 'ce', premium_now=100.0)
        assert loss == 0.0
        assert incomplete is True

    # C-SL-5: fetch_premium_fn=None + frozen positions → (active_loss, True)
    def test_sl_c5_no_fetch_fn_with_frozen_returns_incomplete(self):
        """Cannot price frozen positions without fetch_fn → conservative: active_loss + incomplete."""
        frozen = [{'strike': 78000, 'lots': 3, 'entry_premium': 150.0}]
        sess = _session('ce', active_strike=80000, trigger_value=80.0, active_lots=5,
                        frozen_positions=frozen)
        loss, incomplete = self._run(sess, 'ce', premium_now=100.0, fetch_fn=None)
        expected_active = (100.0 - 80.0) * 5 * LOT_SIZE_BTC
        assert abs(loss - expected_active) < 1e-9
        assert incomplete is True

    # C-SL-6: fetch_premium_fn=None + no frozen → (active_loss, False)
    def test_sl_c6_no_fetch_fn_no_frozen_complete(self):
        """No frozen positions → fetch_fn not needed → complete result."""
        sess = _session('ce', active_strike=80000, trigger_value=80.0, active_lots=5)
        loss, incomplete = self._run(sess, 'ce', premium_now=100.0, fetch_fn=None)
        expected = (100.0 - 80.0) * 5 * LOT_SIZE_BTC
        assert abs(loss - expected) < 1e-9
        assert incomplete is False

    # C-SL-7: fetch_premium_fn raises → position skipped, incomplete=True
    def test_sl_c7_fetch_raises_marks_incomplete(self):
        """Exception in fetch → frozen position skipped, incomplete=True, active_loss returned."""
        frozen = [{'strike': 78000, 'lots': 3, 'entry_premium': 150.0}]
        sess = _session('ce', active_strike=80000, trigger_value=80.0, active_lots=5,
                        frozen_positions=frozen)

        def fetch_fn(strike, option_type):
            raise ConnectionError("Exchange timeout")

        loss, incomplete = self._run(sess, 'ce', premium_now=100.0, fetch_fn=fetch_fn)
        # Active loss still returned, frozen skipped
        expected_active = (100.0 - 80.0) * 5 * LOT_SIZE_BTC
        assert abs(loss - expected_active) < 1e-9
        assert incomplete is True

    # C-SL-8: fetch_premium_fn returns None → position skipped, incomplete=True
    def test_sl_c8_fetch_returns_none_marks_incomplete(self):
        """None return from fetch → frozen position skipped, incomplete=True."""
        frozen = [{'strike': 78000, 'lots': 3, 'entry_premium': 150.0}]
        sess = _session('ce', active_strike=80000, trigger_value=80.0, active_lots=5,
                        frozen_positions=frozen)

        def fetch_fn(strike, option_type):
            return None

        loss, incomplete = self._run(sess, 'ce', premium_now=100.0, fetch_fn=fetch_fn)
        expected_active = (100.0 - 80.0) * 5 * LOT_SIZE_BTC
        assert abs(loss - expected_active) < 1e-9
        assert incomplete is True

    # C-SL-9: premium < trigger → active_loss negative → clamped to 0.0
    def test_sl_c9_premium_below_trigger_clamped_to_zero(self):
        """premium_now < trigger → active_loss < 0 → return 0.0 (no loss to cover)."""
        sess = _session('ce', active_strike=80000, trigger_value=100.0, active_lots=5)
        loss, incomplete = self._run(sess, 'ce', premium_now=80.0)
        assert loss == 0.0
        assert incomplete is False

    # C-SL-10: Frozen uses trigger_snapshot as baseline (not entry_premium)
    def test_sl_c10_frozen_uses_trigger_snapshot_baseline(self):
        """
        Frozen: entry_premium=200, trigger_snapshot=150, current=180
        pos_loss = (180-150)×3×0.001 = 0.09 (uses 150, NOT 200)
        If it used entry_premium: (180-200)×3×0.001 = -0.06 (negative → skipped)
        """
        frozen = [{'strike': 78000, 'lots': 3, 'entry_premium': 200.0}]
        sess = _session(
            'ce',
            active_strike=80000,
            trigger_value=80.0,
            active_lots=5,
            frozen_positions=frozen,
            extra_trigger_snapshots={'78000': 150.0},  # snapshot exists → use 150
        )

        def fetch_fn(strike, option_type):
            return 180.0

        loss, incomplete = self._run(sess, 'ce', premium_now=100.0, fetch_fn=fetch_fn)
        active_loss = (100.0 - 80.0) * 5 * LOT_SIZE_BTC
        frozen_loss = (180.0 - 150.0) * 3 * LOT_SIZE_BTC  # baseline=150 (snapshot)
        assert abs(loss - (active_loss + frozen_loss)) < 1e-9
        assert incomplete is False

    # C-SL-11: Frozen falls back to entry_premium when no trigger_snapshot for that strike
    def test_sl_c11_frozen_fallback_to_entry_premium(self):
        """
        Frozen: entry_premium=150, NO trigger_snapshot for 78000, current=180
        pos_loss = (180-150)×3×0.001 = 0.09 (uses entry_premium as baseline)
        """
        frozen = [{'strike': 78000, 'lots': 3, 'entry_premium': 150.0}]
        sess = _session(
            'ce',
            active_strike=80000,
            trigger_value=80.0,
            active_lots=5,
            frozen_positions=frozen,
            # No extra_trigger_snapshots for 78000 → fallback to entry_premium
        )

        def fetch_fn(strike, option_type):
            return 180.0

        loss, incomplete = self._run(sess, 'ce', premium_now=100.0, fetch_fn=fetch_fn)
        active_loss = (100.0 - 80.0) * 5 * LOT_SIZE_BTC
        frozen_loss = (180.0 - 150.0) * 3 * LOT_SIZE_BTC  # baseline=150 (entry_premium)
        assert abs(loss - (active_loss + frozen_loss)) < 1e-9
        assert incomplete is False

    # C-SL-12: Multiple frozen positions accumulate correctly
    def test_sl_c12_multiple_frozen_accumulate(self):
        """Two frozen positions with losses — both counted and summed."""
        frozen = [
            {'strike': 78000, 'lots': 3, 'entry_premium': 150.0},
            {'strike': 76000, 'lots': 2, 'entry_premium': 120.0},
        ]
        sess = _session(
            'ce',
            active_strike=80000,
            trigger_value=80.0,
            active_lots=5,
            frozen_positions=frozen,
            extra_trigger_snapshots={
                '78000': 150.0,
                '76000': 120.0,
            },
        )

        def fetch_fn(strike, option_type):
            if int(strike) == 78000:
                return 180.0
            if int(strike) == 76000:
                return 150.0
            raise ValueError(f"Unexpected {strike}")

        loss, incomplete = self._run(sess, 'ce', premium_now=100.0, fetch_fn=fetch_fn)
        active_loss = (100.0 - 80.0) * 5 * LOT_SIZE_BTC
        frozen_loss_1 = (180.0 - 150.0) * 3 * LOT_SIZE_BTC
        frozen_loss_2 = (150.0 - 120.0) * 2 * LOT_SIZE_BTC
        expected = active_loss + frozen_loss_1 + frozen_loss_2
        assert abs(loss - expected) < 1e-9
        assert incomplete is False


# =============================================================================
# calculate_reversal_loss
# =============================================================================

class TestCalculateReversalLoss:

    def _run(self, session, aggressor_side='ce', fetch_fn=None):
        engine = _make_engine()
        if fetch_fn is None:
            fetch_fn = lambda strike, opt_type: 100.0
        return engine.calculate_reversal_loss(session, aggressor_side, fetch_fn)

    def _make_session(self, aggressor_side='ce', adjustment_fills=None, frozen_positions=None):
        return {
            aggressor_side: {
                'active_strike': 80000,
                'adjustment_fills': adjustment_fills or [],
                'frozen_positions': frozen_positions or [],
            },
            'params': {},
        }

    # C-RL-1: All profitable → (0.0, pnl, False)
    def test_rl_c1_profitable_fills_do_nothing(self):
        """entry=100, current=80 → fill_pnl=(100-80)×5×0.001=0.10 > 0 → DO NOTHING."""
        sess = self._make_session(
            adjustment_fills=[{'strike': 80000, 'premium': 100.0, 'lots': 5}],
        )
        loss, pnl, incomplete = self._run(sess, 'ce', fetch_fn=lambda s, t: 80.0)
        assert loss == 0.0
        assert abs(pnl - 0.10) < 1e-9
        assert incomplete is False

    # C-RL-2: All underwater → (|loss|, pnl, False)
    def test_rl_c2_underwater_fills_hedge_loss(self):
        """entry=100, current=130 → fill_pnl=(100-130)×5×0.001=-0.15 < 0 → hedge."""
        sess = self._make_session(
            adjustment_fills=[{'strike': 80000, 'premium': 100.0, 'lots': 5}],
        )
        loss, pnl, incomplete = self._run(sess, 'ce', fetch_fn=lambda s, t: 130.0)
        assert abs(loss - 0.15) < 1e-9
        assert abs(pnl - (-0.15)) < 1e-9
        assert incomplete is False

    # C-RL-3: No adjustments → (0.0, 0.0, False)
    def test_rl_c3_no_adjustments_do_nothing(self):
        """No fills, no frozen → pnl=0 → treated as profitable → DO NOTHING."""
        sess = self._make_session()
        loss, pnl, incomplete = self._run(sess, 'ce')
        assert loss == 0.0
        assert pnl == 0.0
        assert incomplete is False

    # C-RL-4: Original frozen positions excluded
    def test_rl_c4_original_frozen_excluded(self):
        """type='original' in frozen_positions → skipped even though current > entry."""
        sess = self._make_session(
            frozen_positions=[{
                'type': 'original', 'strike': 79000,
                'entry_premium': 100.0, 'lots': 5,
            }],
        )
        # fetch would return 150 if called — original should be skipped
        loss, pnl, incomplete = self._run(sess, 'ce', fetch_fn=lambda s, t: 150.0)
        assert loss == 0.0
        assert pnl == 0.0
        assert incomplete is False

    # C-RL-5: Frozen adjustment positions included
    def test_rl_c5_frozen_adjustment_included(self):
        """type='standard' frozen → counted. entry=100, current=130 → -0.09."""
        sess = self._make_session(
            frozen_positions=[{
                'type': 'standard', 'strike': 78000,
                'entry_premium': 100.0, 'lots': 3,
            }],
        )
        loss, pnl, incomplete = self._run(sess, 'ce', fetch_fn=lambda s, t: 130.0)
        expected_pnl = (100.0 - 130.0) * 3 * LOT_SIZE_BTC  # -0.09
        assert abs(loss - 0.09) < 1e-9
        assert abs(pnl - expected_pnl) < 1e-9
        assert incomplete is False

    # C-RL-6: fetch raises → incomplete=True
    def test_rl_c6_fetch_raises_marks_incomplete(self):
        """Exchange error on fetch → position skipped, pnl=0, incomplete=True."""
        sess = self._make_session(
            adjustment_fills=[{'strike': 80000, 'premium': 100.0, 'lots': 5}],
        )

        def bad_fetch(strike, opt_type):
            raise RuntimeError("Exchange timeout")

        loss, pnl, incomplete = self._run(sess, 'ce', fetch_fn=bad_fetch)
        assert loss == 0.0  # all fetches failed → pnl=0 → "profitable"
        assert pnl == 0.0
        assert incomplete is True

    # C-RL-7: Mixed — net profitable
    def test_rl_c7_mixed_net_profitable(self):
        """
        active fill: (100-80)×5×0.001 = +0.10
        frozen:      (100-130)×3×0.001 = -0.09
        net = +0.01 → DO NOTHING
        """
        sess = self._make_session(
            adjustment_fills=[{'strike': 80000, 'premium': 100.0, 'lots': 5}],
            frozen_positions=[{
                'type': 'standard', 'strike': 78000,
                'entry_premium': 100.0, 'lots': 3,
            }],
        )

        def fetch_fn(strike, opt_type):
            if int(strike) == 80000:
                return 80.0
            return 130.0

        loss, pnl, incomplete = self._run(sess, 'ce', fetch_fn=fetch_fn)
        expected_pnl = (100.0 - 80.0) * 5 * LOT_SIZE_BTC + (100.0 - 130.0) * 3 * LOT_SIZE_BTC
        assert loss == 0.0
        assert abs(pnl - expected_pnl) < 1e-9
        assert incomplete is False

    # C-RL-8: Mixed — net underwater
    def test_rl_c8_mixed_net_underwater(self):
        """
        active fill: (100-80)×5×0.001 = +0.10
        frozen:      (100-150)×30×0.001 = -1.50
        net = -1.40 → hedge 1.40
        """
        sess = self._make_session(
            adjustment_fills=[{'strike': 80000, 'premium': 100.0, 'lots': 5}],
            frozen_positions=[{
                'type': 'standard', 'strike': 78000,
                'entry_premium': 100.0, 'lots': 30,
            }],
        )

        def fetch_fn(strike, opt_type):
            if int(strike) == 80000:
                return 80.0
            return 150.0

        loss, pnl, incomplete = self._run(sess, 'ce', fetch_fn=fetch_fn)
        expected_pnl = (100.0 - 80.0) * 5 * LOT_SIZE_BTC + (100.0 - 150.0) * 30 * LOT_SIZE_BTC
        assert abs(loss - abs(expected_pnl)) < 1e-9
        assert abs(pnl - expected_pnl) < 1e-9
        assert incomplete is False

    # C-RL-9: adj_pnl exactly 0.0 → treated as "profitable" → (0.0, 0.0, False)
    def test_rl_c9_pnl_zero_treated_as_profitable(self):
        """entry=current → pnl=0.0 → 0 >= 0 → return (0.0, 0.0, False)."""
        sess = self._make_session(
            adjustment_fills=[{'strike': 80000, 'premium': 100.0, 'lots': 5}],
        )
        loss, pnl, incomplete = self._run(sess, 'ce', fetch_fn=lambda s, t: 100.0)
        assert loss == 0.0
        assert pnl == 0.0
        assert incomplete is False

    # C-RL-10: Active fills + frozen adjustment — both counted
    def test_rl_c10_active_and_frozen_both_counted(self):
        """Active fill and frozen adjustment — both contribute to reversal pnl."""
        sess = self._make_session(
            adjustment_fills=[{'strike': 80000, 'premium': 100.0, 'lots': 5}],
            frozen_positions=[
                {'type': 'reversal', 'strike': 78000, 'entry_premium': 90.0, 'lots': 4},
            ],
        )

        def fetch_fn(strike, opt_type):
            # both underwater
            return 130.0

        loss, pnl, incomplete = self._run(sess, 'ce', fetch_fn=fetch_fn)
        expected_pnl = (
            (100.0 - 130.0) * 5 * LOT_SIZE_BTC +
            (90.0 - 130.0) * 4 * LOT_SIZE_BTC
        )
        assert abs(loss - abs(expected_pnl)) < 1e-9
        assert abs(pnl - expected_pnl) < 1e-9
        assert incomplete is False
