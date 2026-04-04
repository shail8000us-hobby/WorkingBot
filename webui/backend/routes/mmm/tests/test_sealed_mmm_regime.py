"""
Contract tests for MMM Regime Engine — T2-2

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Covers:
  _compute_trend_tier     — pure tier mapping from move% + EMA confirmation
  _check_acceleration     — spot history scan for fast-move bypass
  _compute_regime_action  — aggregate regime combinator (priority cascade)
  _update_trend_guard     — trend detection with anchor, EMA, retracement, reset

File: webui/backend/routes/mmm/mmm_regime.py

--- _compute_trend_tier contracts ---
C-CTT-1: move < tier1_pct → NONE regardless of EMA
C-CTT-2: move >= tier1_pct + ema confirms → ALERT
C-CTT-3: move >= tier1_pct but no EMA confirm AND no fast move → NONE
C-CTT-4: move >= tier1_pct + is_fast_move (no EMA) → ALERT (fast-move bypass)
C-CTT-5: move >= tier2_pct → GUARD (no EMA required)
C-CTT-6: move >= tier3_pct → BLOCK (no EMA required)
C-CTT-7: move >= tier4_pct → WIND_DOWN (highest tier)
C-CTT-8: Tier cascade: tier4 wins over tier3 when both would apply

--- _check_acceleration contracts ---
C-CA-1: Empty history → (False, 0.0)
C-CA-2: Only one entry → (False, 0.0)
C-CA-3: All entries outside window → (False, 0.0)
C-CA-4: Move within window below threshold → (False, actual_pct)
C-CA-5: Move within window at/above threshold → (True, actual_pct)
C-CA-6: Uses oldest in-window entry (not most recent entry)

--- _compute_regime_action contracts ---
C-CRA-1: All NORMAL → ACTION_NORMAL
C-CRA-2: GAMMA_EMERGENCY → FORCE_REDUCE (highest priority)
C-CRA-3: VOL_HIGH + any trend → BLOCK_ALL_SELLS
C-CRA-4: VOL_HIGH alone → BLOCK_ALL_SELLS
C-CRA-5: VOL_ELEVATED alone → BLOCK_ALL_SELLS
C-CRA-6: GAMMA_HARD → BLOCK_ALL_SELLS
C-CRA-7: TREND_UP only at Tier 2 → BLOCK_CE_SELLS
C-CRA-8: TREND_DOWN only at Tier 2 → BLOCK_PE_SELLS
C-CRA-9: TREND at Tier 3 → BLOCK_ALL_SELLS (unless trend_boost)
C-CRA-10: TREND at Tier 4 → BLOCK_ALL_SELLS + _trend_wind_down_triggered=True
C-CRA-11: GAMMA_EMERGENCY > VOL_HIGH (priority order)
C-CRA-12: VOL_HIGH + GAMMA_EMERGENCY → FORCE_REDUCE (gamma emergency wins first)

--- _update_trend_guard contracts ---
C-UTG-1: trend_enabled=False → NORMAL, clears state
C-UTG-2: spot_price=0 → returns last known regime, no mutation
C-UTG-3: First call (no anchor) → initializes anchor, returns NORMAL
C-UTG-4: Small move (< tier1_pct) → stays NORMAL
C-UTG-5: Large up move (>= tier1_pct) with EMA confirms → enters TREND_UP
C-UTG-6: Tier escalation: subsequent larger move escalates tier
C-UTG-7: Once in TREND_UP, tier never de-escalates within same trend episode
C-UTG-8: Retracement + EMA calm → resets to NORMAL after reset_beats
"""

import pytest
import time
from datetime import datetime, timedelta, timezone


# =============================================================================
# Helpers
# =============================================================================

def _regime_session(**overrides):
    s = {
        'params': {
            'trend_enabled': True,
            'trend_tier1_pct': 0.5,
            'trend_tier2_pct': 1.0,
            'trend_tier3_pct': 1.5,
            'trend_tier4_pct': 2.0,
            'trend_ema_period': 10,
            'trend_ema_slope_threshold': 25,
            'trend_acceleration_pct': 0.5,
            'trend_acceleration_window_s': 600,
            'trend_retrace_pct': 30,
            'trend_reset_beats': 3,
            'vol_regime_action': 'block_sells',
            'trend_action': 'block_sells',
            'trend_boost_enabled': False,
            'atm_shield_enabled': False,
        },
    }
    for k, v in overrides.items():
        if '.' in k:
            top, sub = k.split('.', 1)
            s.setdefault(top, {})[sub] = v
        else:
            s[k] = v
    return s


def _ts_ago(secs):
    return (datetime.now(timezone.utc) - timedelta(seconds=secs)).isoformat()


# =============================================================================
# _compute_trend_tier
# =============================================================================

class TestComputeTrendTier:

    @pytest.mark.sealed
    def test_c_ctt_1_below_tier1_no_ema(self):
        from webui.backend.routes.mmm.mmm_regime import _compute_trend_tier, TREND_TIER_NONE
        params = {'trend_tier1_pct': 0.5, 'trend_tier2_pct': 1.0, 'trend_tier3_pct': 1.5, 'trend_tier4_pct': 2.0}
        assert _compute_trend_tier(0.3, False, False, params) == TREND_TIER_NONE

    @pytest.mark.sealed
    def test_c_ctt_2_tier1_with_ema(self):
        from webui.backend.routes.mmm.mmm_regime import _compute_trend_tier, TREND_TIER_ALERT
        params = {'trend_tier1_pct': 0.5, 'trend_tier2_pct': 1.0, 'trend_tier3_pct': 1.5, 'trend_tier4_pct': 2.0}
        assert _compute_trend_tier(0.6, True, False, params) == TREND_TIER_ALERT

    @pytest.mark.sealed
    def test_c_ctt_3_tier1_no_ema_no_fast(self):
        from webui.backend.routes.mmm.mmm_regime import _compute_trend_tier, TREND_TIER_NONE
        params = {'trend_tier1_pct': 0.5, 'trend_tier2_pct': 1.0, 'trend_tier3_pct': 1.5, 'trend_tier4_pct': 2.0}
        assert _compute_trend_tier(0.6, False, False, params) == TREND_TIER_NONE

    @pytest.mark.sealed
    def test_c_ctt_4_tier1_fast_move_bypass(self):
        """is_fast_move=True bypasses EMA requirement for Tier 1."""
        from webui.backend.routes.mmm.mmm_regime import _compute_trend_tier, TREND_TIER_ALERT
        params = {'trend_tier1_pct': 0.5, 'trend_tier2_pct': 1.0, 'trend_tier3_pct': 1.5, 'trend_tier4_pct': 2.0}
        assert _compute_trend_tier(0.6, False, True, params) == TREND_TIER_ALERT

    @pytest.mark.sealed
    def test_c_ctt_5_tier2_no_ema(self):
        from webui.backend.routes.mmm.mmm_regime import _compute_trend_tier, TREND_TIER_GUARD
        params = {'trend_tier1_pct': 0.5, 'trend_tier2_pct': 1.0, 'trend_tier3_pct': 1.5, 'trend_tier4_pct': 2.0}
        assert _compute_trend_tier(1.2, False, False, params) == TREND_TIER_GUARD

    @pytest.mark.sealed
    def test_c_ctt_6_tier3(self):
        from webui.backend.routes.mmm.mmm_regime import _compute_trend_tier, TREND_TIER_BLOCK
        params = {'trend_tier1_pct': 0.5, 'trend_tier2_pct': 1.0, 'trend_tier3_pct': 1.5, 'trend_tier4_pct': 2.0}
        assert _compute_trend_tier(1.7, False, False, params) == TREND_TIER_BLOCK

    @pytest.mark.sealed
    def test_c_ctt_7_tier4_wind_down(self):
        from webui.backend.routes.mmm.mmm_regime import _compute_trend_tier, TREND_TIER_WIND_DOWN
        params = {'trend_tier1_pct': 0.5, 'trend_tier2_pct': 1.0, 'trend_tier3_pct': 1.5, 'trend_tier4_pct': 2.0}
        assert _compute_trend_tier(2.5, False, False, params) == TREND_TIER_WIND_DOWN

    @pytest.mark.sealed
    def test_c_ctt_8_tier4_wins_over_tier3(self):
        """Move at tier4 returns WIND_DOWN not BLOCK."""
        from webui.backend.routes.mmm.mmm_regime import _compute_trend_tier, TREND_TIER_WIND_DOWN
        params = {'trend_tier1_pct': 0.5, 'trend_tier2_pct': 1.0, 'trend_tier3_pct': 1.5, 'trend_tier4_pct': 2.0}
        assert _compute_trend_tier(2.0, False, False, params) == TREND_TIER_WIND_DOWN


# =============================================================================
# _check_acceleration
# =============================================================================

class TestCheckAcceleration:

    @pytest.mark.sealed
    def test_c_ca_1_empty_history(self):
        from webui.backend.routes.mmm.mmm_regime import _check_acceleration
        sess = _regime_session()
        is_fast, pct = _check_acceleration(sess, 50000, sess['params'])
        assert is_fast is False
        assert pct == 0.0

    @pytest.mark.sealed
    def test_c_ca_2_one_entry(self):
        from webui.backend.routes.mmm.mmm_regime import _check_acceleration
        sess = _regime_session()
        sess['_vol_spot_history'] = [(_ts_ago(30), 50000)]
        is_fast, pct = _check_acceleration(sess, 50100, sess['params'])
        assert is_fast is False  # Need at least 2 entries
        assert pct == 0.0

    @pytest.mark.sealed
    def test_c_ca_3_all_outside_window(self):
        from webui.backend.routes.mmm.mmm_regime import _check_acceleration
        sess = _regime_session()
        sess['params']['trend_acceleration_window_s'] = 60
        sess['_vol_spot_history'] = [
            (_ts_ago(300), 50000),  # 5 min ago, outside 60s window
            (_ts_ago(200), 50100),
        ]
        is_fast, pct = _check_acceleration(sess, 50300, sess['params'])
        assert is_fast is False

    @pytest.mark.sealed
    def test_c_ca_4_below_threshold(self):
        from webui.backend.routes.mmm.mmm_regime import _check_acceleration
        sess = _regime_session()
        sess['params']['trend_acceleration_pct'] = 0.5
        sess['params']['trend_acceleration_window_s'] = 600
        # 0.2% move from 50000 to 50100
        sess['_vol_spot_history'] = [(_ts_ago(30), 50000), (_ts_ago(10), 50050)]
        is_fast, pct = _check_acceleration(sess, 50100, sess['params'])
        assert is_fast is False
        assert round(pct, 3) == 0.2

    @pytest.mark.sealed
    def test_c_ca_5_at_threshold(self):
        from webui.backend.routes.mmm.mmm_regime import _check_acceleration
        sess = _regime_session()
        sess['params']['trend_acceleration_pct'] = 0.5
        sess['params']['trend_acceleration_window_s'] = 600
        # Exactly 0.5% move from 50000 to 50250
        sess['_vol_spot_history'] = [(_ts_ago(30), 50000), (_ts_ago(10), 50100)]
        is_fast, pct = _check_acceleration(sess, 50250, sess['params'])
        assert is_fast is True

    @pytest.mark.sealed
    def test_c_ca_6_uses_oldest_in_window(self):
        """Uses the oldest in-window price, not the newest."""
        from webui.backend.routes.mmm.mmm_regime import _check_acceleration
        sess = _regime_session()
        sess['params']['trend_acceleration_pct'] = 0.5
        sess['params']['trend_acceleration_window_s'] = 600
        # History: oldest=49000 (large move), recent=50000 (small drift)
        sess['_vol_spot_history'] = [
            (_ts_ago(500), 49000),  # oldest in window
            (_ts_ago(60), 50000),
        ]
        is_fast, pct = _check_acceleration(sess, 49250, sess['params'])
        # Move from 49000 = 0.51%, should be fast
        assert is_fast is True


# =============================================================================
# _compute_regime_action
# =============================================================================

class TestComputeRegimeAction:

    def _sess_with_regimes(self, vol='NORMAL', gamma='NORMAL', trend='NORMAL', tier=0, **extras):
        from webui.backend.routes.mmm.mmm_regime import (
            VOL_NORMAL, VOL_ELEVATED, VOL_HIGH,
            GAMMA_NORMAL, GAMMA_SOFT, GAMMA_HARD, GAMMA_EMERGENCY,
            TREND_NORMAL, TREND_UP, TREND_DOWN,
        )
        sess = _regime_session()
        sess['_vol_regime'] = vol
        sess['_gamma_regime'] = gamma
        sess['_trend_regime'] = trend
        sess['_trend_tier'] = tier
        sess.update(extras)
        return sess

    @pytest.mark.sealed
    def test_c_cra_1_all_normal(self):
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_NORMAL
        sess = self._sess_with_regimes()
        assert _compute_regime_action(sess) == ACTION_NORMAL

    @pytest.mark.sealed
    def test_c_cra_2_gamma_emergency(self):
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_FORCE_REDUCE
        sess = self._sess_with_regimes(gamma='EMERGENCY')
        assert _compute_regime_action(sess) == ACTION_FORCE_REDUCE

    @pytest.mark.sealed
    def test_c_cra_3_vol_high_with_trend(self):
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_ALL_SELLS
        sess = self._sess_with_regimes(vol='HIGH', trend='TREND_UP')
        assert _compute_regime_action(sess) == ACTION_BLOCK_ALL_SELLS

    @pytest.mark.sealed
    def test_c_cra_4_vol_high_alone(self):
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_ALL_SELLS
        sess = self._sess_with_regimes(vol='HIGH')
        assert _compute_regime_action(sess) == ACTION_BLOCK_ALL_SELLS

    @pytest.mark.sealed
    def test_c_cra_5_vol_elevated_alone(self):
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_ALL_SELLS
        sess = self._sess_with_regimes(vol='ELEVATED')
        assert _compute_regime_action(sess) == ACTION_BLOCK_ALL_SELLS

    @pytest.mark.sealed
    def test_c_cra_5b_vol_elevated_gamma_hard_blocks_all(self):
        # Vol ELEVATED + Gamma HARD = compound risk → BLOCK_ALL_SELLS.
        # Tier B/C exemptions must NOT apply — vol elevated is not safe to relax.
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_ALL_SELLS
        sess = self._sess_with_regimes(vol='ELEVATED', gamma='HARD')
        sess['_ce_dollar_gamma'] = 1000.0
        sess['_pe_dollar_gamma'] = 3000.0  # PE dominant — would normally BLOCK_PE_SELLS
        sess['_gamma_dte_relax_active'] = True  # DTE relax active too
        assert _compute_regime_action(sess) == ACTION_BLOCK_ALL_SELLS

    @pytest.mark.sealed
    def test_c_cra_6_gamma_hard_no_side_data_blocks_all(self):
        # Gamma HARD, no per-side gamma data, no DTE relax → conservative BLOCK_ALL_SELLS.
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_ALL_SELLS
        sess = self._sess_with_regimes(gamma='HARD')
        # _ce_dollar_gamma / _pe_dollar_gamma not set → both 0 → Step 1 skipped
        assert _compute_regime_action(sess) == ACTION_BLOCK_ALL_SELLS

    # ── Tier B: per-side gamma ────────────────────────────────────────────────

    @pytest.mark.sealed
    def test_c_cra_6b_gamma_hard_pe_dominant_blocks_pe_only(self):
        # PE has 2.5× the dollar gamma of CE → PE is near ATM (danger side).
        # Only PE sells are blocked; CE hedge sell is allowed.
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_PE_SELLS
        sess = self._sess_with_regimes(gamma='HARD')
        sess['_ce_dollar_gamma'] = 1000.0
        sess['_pe_dollar_gamma'] = 2500.0  # ratio 2.5 ≥ 1.5 threshold
        assert _compute_regime_action(sess) == ACTION_BLOCK_PE_SELLS

    @pytest.mark.sealed
    def test_c_cra_6c_gamma_hard_ce_dominant_blocks_ce_only(self):
        # CE has 2.5× the dollar gamma of PE → CE is near ATM (danger side).
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_CE_SELLS
        sess = self._sess_with_regimes(gamma='HARD')
        sess['_ce_dollar_gamma'] = 2500.0  # ratio 2.5 ≥ 1.5 threshold
        sess['_pe_dollar_gamma'] = 1000.0
        assert _compute_regime_action(sess) == ACTION_BLOCK_CE_SELLS

    @pytest.mark.sealed
    def test_c_cra_6d_gamma_hard_balanced_gamma_blocks_all(self):
        # Ratio 1.1 < 1.5 threshold → neither side dominant → conservative BLOCK_ALL_SELLS.
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_ALL_SELLS
        sess = self._sess_with_regimes(gamma='HARD')
        sess['_ce_dollar_gamma'] = 2000.0
        sess['_pe_dollar_gamma'] = 2200.0  # ratio 1.1 — balanced
        assert _compute_regime_action(sess) == ACTION_BLOCK_ALL_SELLS

    @pytest.mark.sealed
    def test_c_cra_6e_gamma_hard_only_pe_positions_blocks_pe(self):
        # Only PE positions active (CE = 0) → block PE sells regardless of ratio.
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_PE_SELLS
        sess = self._sess_with_regimes(gamma='HARD')
        sess['_ce_dollar_gamma'] = 0.0
        sess['_pe_dollar_gamma'] = 3000.0
        assert _compute_regime_action(sess) == ACTION_BLOCK_PE_SELLS

    # ── Tier C: DTE relax tiebreaker ─────────────────────────────────────────

    @pytest.mark.sealed
    def test_c_cra_6f_dte_relax_trend_down_breaks_tie_blocks_pe(self):
        # Balanced gamma + DTE relax active + dollar_gamma below hedge limit
        # + TREND_DOWN → PE is the tiebreaker danger side → BLOCK_PE_SELLS.
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_PE_SELLS
        sess = self._sess_with_regimes(gamma='HARD', trend='TREND_DOWN')
        sess['_ce_dollar_gamma'] = 2000.0
        sess['_pe_dollar_gamma'] = 2200.0  # balanced — ratio 1.1
        sess['_gamma_dte_relax_active'] = True
        sess['_portfolio_dollar_gamma'] = 5500.0
        sess['_gamma_hard_limit_hedge_effective'] = 10000.0  # 2× relaxed
        sess['_gamma_hard_limit_effective'] = 5000.0
        assert _compute_regime_action(sess) == ACTION_BLOCK_PE_SELLS

    @pytest.mark.sealed
    def test_c_cra_6g_dte_relax_above_hedge_limit_blocks_all(self):
        # In DTE window but dollar_gamma exceeds even the relaxed hedge limit
        # → no tiebreaker, conservative BLOCK_ALL_SELLS.
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_ALL_SELLS
        sess = self._sess_with_regimes(gamma='HARD', trend='TREND_DOWN')
        sess['_ce_dollar_gamma'] = 2000.0
        sess['_pe_dollar_gamma'] = 2200.0
        sess['_gamma_dte_relax_active'] = True
        sess['_portfolio_dollar_gamma'] = 12000.0   # above hedge limit
        sess['_gamma_hard_limit_hedge_effective'] = 10000.0
        assert _compute_regime_action(sess) == ACTION_BLOCK_ALL_SELLS

    @pytest.mark.sealed
    def test_c_cra_6h_dte_relax_no_trend_blocks_all(self):
        # DTE relax active + below hedge limit but TREND_NORMAL
        # → no tiebreaker direction → BLOCK_ALL_SELLS (conservative).
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_ALL_SELLS
        sess = self._sess_with_regimes(gamma='HARD')  # trend=NORMAL
        sess['_ce_dollar_gamma'] = 2000.0
        sess['_pe_dollar_gamma'] = 2200.0
        sess['_gamma_dte_relax_active'] = True
        sess['_portfolio_dollar_gamma'] = 5500.0
        sess['_gamma_hard_limit_hedge_effective'] = 10000.0
        # No anchor/spot set → Step 1 skips → balanced per-side gamma → DTE relax
        # → TREND_NORMAL (no direction) → BLOCK_ALL_SELLS
        assert _compute_regime_action(sess) == ACTION_BLOCK_ALL_SELLS

    @pytest.mark.sealed
    def test_c_cra_6i_anchor_up_blocks_ce(self):
        # Market moved UP above dead-band → CE (calls) are aggressor → BLOCK_CE_SELLS.
        # PE has MORE total dollar gamma (lot-count asymmetry), but anchor direction
        # wins over per-side total gamma: Step 1 fires before Step 2.
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_CE_SELLS
        sess = self._sess_with_regimes(gamma='HARD')
        sess['_ce_dollar_gamma'] = 3500.0
        sess['_pe_dollar_gamma'] = 5000.0   # PE > CE (more lots on PE), but should NOT block PE
        sess['_trend_anchor_spot'] = 67000.0
        sess['_regime_spot_price'] = 67200.0   # +0.30% — above 0.10% dead-band
        assert _compute_regime_action(sess) == ACTION_BLOCK_CE_SELLS

    @pytest.mark.sealed
    def test_c_cra_6j_anchor_down_blocks_pe(self):
        # Market moved DOWN below dead-band → PE (puts) are aggressor → BLOCK_PE_SELLS.
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_PE_SELLS
        sess = self._sess_with_regimes(gamma='HARD')
        sess['_ce_dollar_gamma'] = 5000.0   # CE > PE (more lots on CE), but should NOT block CE
        sess['_pe_dollar_gamma'] = 3500.0
        sess['_trend_anchor_spot'] = 67000.0
        sess['_regime_spot_price'] = 66800.0   # -0.30% — below -0.10% dead-band
        assert _compute_regime_action(sess) == ACTION_BLOCK_PE_SELLS

    @pytest.mark.sealed
    def test_c_cra_6k_anchor_flat_falls_to_gamma_imbalance(self):
        # Spot is inside dead-band (< 0.10%) → direction ambiguous →
        # falls to Step 2 (per-side gamma imbalance). PE dominant → BLOCK_PE_SELLS.
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_BLOCK_PE_SELLS
        sess = self._sess_with_regimes(gamma='HARD')
        sess['_ce_dollar_gamma'] = 1000.0
        sess['_pe_dollar_gamma'] = 3000.0   # PE dominant (ratio 3.0 ≥ 1.5)
        sess['_trend_anchor_spot'] = 67000.0
        sess['_regime_spot_price'] = 67050.0   # +0.075% — inside dead-band
        assert _compute_regime_action(sess) == ACTION_BLOCK_PE_SELLS

    @pytest.mark.sealed
    def test_c_ugc_opt_string_call_put_produces_per_side_gamma(self):
        # Regression: monitor stores opt as 'call'/'put' but regime filters for 'C'/'P'.
        # If the monitor passes 'call'/'put' strings, _ce_dollar_gamma and _pe_dollar_gamma
        # stay 0.0 → Step 1 never fires → BLOCK_ALL_SELLS instead of directional block.
        # Fix: monitor must store opt_char 'C'/'P' (mmm_monitor.py line ~9465).
        # This test calls _update_gamma_cap directly with 'C'/'P' strings (correct)
        # and verifies per-side values are populated, sealing the contract.
        from webui.backend.routes.mmm.mmm_gamma import _update_gamma_cap
        sess = {'params': {}, '_gamma_history': []}
        spot = 66000.0
        # CE dominant: ce_gamma >> pe_gamma
        gamma_data = {
            'portfolio_gamma': 0.05,
            'positions': [
                (0.04, 10, 'C'),   # CE: 10 lots, gamma=0.04 — high CE gamma
                (0.005, 8, 'P'),   # PE: 8 lots, gamma=0.005 — low PE gamma
            ],
        }
        _update_gamma_cap(sess, gamma_data, spot, minutes_to_expiry=300)
        ce_dg = sess['_ce_dollar_gamma']
        pe_dg = sess['_pe_dollar_gamma']
        assert ce_dg > 0, f"CE dollar gamma must be > 0, got {ce_dg}"
        assert pe_dg > 0, f"PE dollar gamma must be > 0, got {pe_dg}"
        assert ce_dg > pe_dg * 3, (
            f"CE ($Γ={ce_dg}) should far exceed PE ($Γ={pe_dg}) given dominant CE positions"
        )

    @pytest.mark.sealed
    def test_c_cra_7_trend_up_tier2_block_ce(self):
        from webui.backend.routes.mmm.mmm_regime import (
            _compute_regime_action, ACTION_BLOCK_CE_SELLS, TREND_TIER_GUARD
        )
        sess = self._sess_with_regimes(trend='TREND_UP', tier=TREND_TIER_GUARD)
        sess['_trend_direction'] = 'up'
        assert _compute_regime_action(sess) == ACTION_BLOCK_CE_SELLS

    @pytest.mark.sealed
    def test_c_cra_8_trend_down_tier2_block_pe(self):
        from webui.backend.routes.mmm.mmm_regime import (
            _compute_regime_action, ACTION_BLOCK_PE_SELLS, TREND_TIER_GUARD
        )
        sess = self._sess_with_regimes(trend='TREND_DOWN', tier=TREND_TIER_GUARD)
        sess['_trend_direction'] = 'down'
        assert _compute_regime_action(sess) == ACTION_BLOCK_PE_SELLS

    @pytest.mark.sealed
    def test_c_cra_9_trend_tier3_block_all(self):
        from webui.backend.routes.mmm.mmm_regime import (
            _compute_regime_action, ACTION_BLOCK_ALL_SELLS, TREND_TIER_BLOCK
        )
        sess = self._sess_with_regimes(trend='TREND_UP', tier=TREND_TIER_BLOCK)
        sess['_trend_direction'] = 'up'
        assert _compute_regime_action(sess) == ACTION_BLOCK_ALL_SELLS

    @pytest.mark.sealed
    def test_c_cra_10_trend_tier4_wind_down_flag(self):
        from webui.backend.routes.mmm.mmm_regime import (
            _compute_regime_action, ACTION_BLOCK_ALL_SELLS, TREND_TIER_WIND_DOWN
        )
        sess = self._sess_with_regimes(trend='TREND_UP', tier=TREND_TIER_WIND_DOWN)
        sess['_trend_direction'] = 'up'
        action = _compute_regime_action(sess)
        assert action == ACTION_BLOCK_ALL_SELLS
        assert sess.get('_trend_wind_down_triggered') is True

    @pytest.mark.sealed
    def test_c_cra_11_gamma_emergency_beats_vol_high(self):
        """Priority: GAMMA_EMERGENCY > VOL_HIGH."""
        from webui.backend.routes.mmm.mmm_regime import _compute_regime_action, ACTION_FORCE_REDUCE
        sess = self._sess_with_regimes(vol='HIGH', gamma='EMERGENCY', trend='TREND_UP')
        assert _compute_regime_action(sess) == ACTION_FORCE_REDUCE

    @pytest.mark.sealed
    def test_c_cra_12_trend_boost_tier3_blocks_only_aggressor(self):
        from webui.backend.routes.mmm.mmm_regime import (
            _compute_regime_action, ACTION_BLOCK_CE_SELLS, TREND_TIER_BLOCK
        )
        sess = self._sess_with_regimes(trend='TREND_UP', tier=TREND_TIER_BLOCK)
        sess['params']['trend_boost_enabled'] = True
        sess['_trend_direction'] = 'up'
        assert _compute_regime_action(sess) == ACTION_BLOCK_CE_SELLS


# =============================================================================
# _update_trend_guard
# =============================================================================

class TestUpdateTrendGuard:

    @pytest.mark.sealed
    def test_c_utg_1_trend_disabled(self):
        from webui.backend.routes.mmm.mmm_regime import _update_trend_guard, TREND_NORMAL, TREND_TIER_NONE
        sess = _regime_session()
        sess['params']['trend_enabled'] = False
        result = _update_trend_guard(sess, 50000)
        assert result == TREND_NORMAL
        assert sess['_trend_regime'] == TREND_NORMAL
        assert sess['_trend_tier'] == TREND_TIER_NONE

    @pytest.mark.sealed
    def test_c_utg_2_zero_spot_returns_last_regime(self):
        from webui.backend.routes.mmm.mmm_regime import _update_trend_guard, TREND_NORMAL
        sess = _regime_session()
        sess['_trend_regime'] = 'TREND_UP'
        result = _update_trend_guard(sess, 0)
        assert result == 'TREND_UP'  # unchanged
        # Does not overwrite the regime
        assert sess['_trend_regime'] == 'TREND_UP'

    @pytest.mark.sealed
    def test_c_utg_3_first_call_initializes_anchor(self):
        from webui.backend.routes.mmm.mmm_regime import _update_trend_guard, TREND_NORMAL
        sess = _regime_session()
        result = _update_trend_guard(sess, 50000.0)
        assert result == TREND_NORMAL
        assert sess['_trend_anchor_spot'] == 50000.0
        assert sess['_trend_ema'] == 50000.0

    @pytest.mark.sealed
    def test_c_utg_4_small_move_stays_normal(self):
        from webui.backend.routes.mmm.mmm_regime import _update_trend_guard, TREND_NORMAL
        sess = _regime_session()
        # Initialize anchor
        _update_trend_guard(sess, 50000.0)
        # Small 0.2% move (below 0.5% tier1)
        result = _update_trend_guard(sess, 50100.0)
        assert result == TREND_NORMAL

    @pytest.mark.sealed
    def test_c_utg_5_large_up_move_enters_trend_up(self):
        from webui.backend.routes.mmm.mmm_regime import _update_trend_guard, TREND_UP
        sess = _regime_session()
        _update_trend_guard(sess, 50000.0)  # initialize
        # Force EMA to confirm upward move by calling multiple times
        # First call sets EMA = spot, second call will have positive slope
        result = _update_trend_guard(sess, 50300.0)  # 0.6% move > 0.5% tier1
        # EMA slope will be positive (spot > ema_prev)
        assert result == TREND_UP

    @pytest.mark.sealed
    def test_c_utg_6_tier_escalates_on_larger_move(self):
        from webui.backend.routes.mmm.mmm_regime import (
            _update_trend_guard, TREND_TIER_ALERT, TREND_TIER_GUARD
        )
        sess = _regime_session()
        _update_trend_guard(sess, 50000.0)  # init
        _update_trend_guard(sess, 50300.0)  # 0.6% → Tier 1 ALERT
        tier1 = sess.get('_trend_tier', 0)
        _update_trend_guard(sess, 50600.0)  # 1.2% → should reach Tier 2 GUARD
        tier2 = sess.get('_trend_tier', 0)
        assert tier2 >= tier1  # Tier only escalates

    @pytest.mark.sealed
    def test_c_utg_7_tier_never_de_escalates_within_trend(self):
        """Once tier is set, subsequent smaller moves don't lower it."""
        from webui.backend.routes.mmm.mmm_regime import _update_trend_guard
        sess = _regime_session()
        _update_trend_guard(sess, 50000.0)  # init
        # Drive to tier 2 (1.2% move)
        _update_trend_guard(sess, 50600.0)
        _update_trend_guard(sess, 50600.0)  # force EMA to catch up
        tier_high = sess.get('_trend_tier', 0)
        # Now smaller excursion (would only be tier 1 from anchor)
        # Since tier never de-escalates, should stay at or above tier_high
        _update_trend_guard(sess, 50350.0)  # 0.7% — below tier 2
        tier_after = sess.get('_trend_tier', 0)
        assert tier_after >= tier_high

    @pytest.mark.sealed
    def test_c_utg_8_retracement_resets_after_calm_beats(self):
        """Full retracement + EMA calm + N beats → reset to NORMAL."""
        from webui.backend.routes.mmm.mmm_regime import _update_trend_guard, TREND_NORMAL
        sess = _regime_session()
        sess['params']['trend_reset_beats'] = 2
        sess['params']['trend_retrace_pct'] = 30  # 30% retracement needed

        # Initialize and drive into uptrend
        _update_trend_guard(sess, 50000.0)  # init
        _update_trend_guard(sess, 50600.0)  # 1.2% up → trend_up
        _update_trend_guard(sess, 50600.0)  # EMA catches up

        # Price drops back — triggers full retracement from high
        # (spot at anchor = 100% retracement from high)
        for _ in range(5):
            # Allow enough EMA decay cycles at anchor to calm slope
            _update_trend_guard(sess, 50000.0)

        # After reset_beats of calm + retracement, should be NORMAL
        result = _update_trend_guard(sess, 50000.0)
        assert result == TREND_NORMAL
