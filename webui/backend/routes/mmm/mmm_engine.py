"""
MMM Engine — Core Adjustment Logic

The adjustment calculation and execution engine. This is the mathematical
heart of the MMM algorithm.

Maps to MONEY_POWER_CALCULATION_LOGIC.md:
  §5: Adjustment Calculation (Case A standard, Case B reversal)
  §6: State Update after adjustment
  §14.1: Premium buffer

Created: February 15, 2026
"""

import logging
import math
import asyncio
import threading
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from .mmm_state import recompute_side_lots
from .mmm_trigger import update_trigger_snapshots
from .mmm_constants import LOT_SIZE_BTC, strike_key
from webui.backend.sealed import sealed

# Fix #19: Decimal precision helper — converts floats/ints to Decimal
# for all internal P&L arithmetic to avoid IEEE 754 rounding accumulation.
def _D(x) -> Decimal:
    """Convert a float or int to Decimal via string to avoid float representation errors."""
    return Decimal(str(x))

_LOT = _D(LOT_SIZE_BTC)  # Decimal lot size constant

log = logging.getLogger('mmm_engine')


class MMMEngine:
    """
    Core adjustment calculation and execution engine.

    Given a trigger evaluation result, calculates:
      - Loss to cover (standard or reversal formula)
      - Which strike to sell at (active or shifted)
      - How many lots to sell (with buffer, cap constraints)
      - Executes the order via MMMExecutor
      - Updates session state
    """

    def __init__(self, executor=None, initializer=None):
        self._executor = executor
        self._initializer = initializer

    @property
    def executor(self):
        if self._executor is None:
            from .mmm_executor import get_executor
            self._executor = get_executor()
        return self._executor

    @property
    def initializer(self):
        if self._initializer is None:
            from .mmm_initializer import get_initializer
            self._initializer = get_initializer()
        return self._initializer

    # =========================================================================
    # §5 Case A: Standard Adjustment (continuation or first-ever)
    # =========================================================================

    def calculate_standard_loss(
        self,
        session: Dict,
        aggressor_side: str,
        premium_now: float,
        fetch_premium_fn=None,
    ) -> Tuple[float, bool]:
        """
        §5.2 Case A — Updated v2: Total loss across ALL open positions.

        Every open position is real risk. No position is ever excluded.
        Loss = active_strike_loss + sum(shifted_position_losses)

        See Money_power_calculation_logic_updated.md for rationale.

        Args:
            session: Full session dict
            aggressor_side: 'ce' or 'pe' — the side whose premium rose
            premium_now: Current premium of the aggressor at active strike
            fetch_premium_fn: callable(strike, option_type) → current premium
                              (needed to price shifted positions at old strikes)

        Returns:
            Tuple of (total_loss, calculation_incomplete):
            - total_loss: positive float, total loss across all open positions
            - calculation_incomplete: True if any premium fetch failed (Robust v2 Fix #2)
        """
        side_state = session.get(aggressor_side, {})
        active_strike = strike_key(side_state.get('active_strike', 0))
        trigger = side_state.get('trigger_snapshot', {}).get(active_strike, 0)
        active_lots = side_state.get('active_lots', 0)
        # Robust v2 Fix #2: Track fetch failures for calculation_incomplete flag
        _fetch_errors = 0
        _total_positions = 0

        # AUDIT FIX: If trigger is 0/missing, we cannot compute incremental loss.
        # Returning 0 loss with incomplete=True prevents massive over-hedge from
        # (premium_now - 0) producing an inflated loss value.
        if trigger <= 0:
            log.warning(
                f"Standard loss: trigger_snapshot missing/zero for {aggressor_side.upper()} "
                f"@ {active_strike} — returning 0 loss with incomplete flag"
            )
            return 0.0, True

        # 1. Active strike loss (trigger-based)
        # Fix #19: Use Decimal arithmetic to prevent rounding accumulation
        # (active_loss may be negative when aggressor premium is below trigger)
        active_loss = (
            (_D(premium_now) - _D(trigger)) * _D(active_lots) * _LOT
        )

        log.info(
            f"Standard loss (active @ {active_strike}): "
            f"({premium_now:.2f} - {trigger:.2f}) × {active_lots} lots "
            f"× {LOT_SIZE_BTC} = ${float(active_loss):.4f}"
        )

        # 2. Shifted position losses — ALL positions at old strikes
        #    Every open position contributes to total loss. No exceptions.
        #    §5.2 Case A: Use entry_premium as baseline for frozen positions
        #    (lifetime loss). trigger_snapshot is only for the ACTIVE strike.
        shifted_loss = _D(0)
        option_type = 'call' if aggressor_side == 'ce' else 'put'

        if fetch_premium_fn:
            for pos in side_state.get('frozen_positions', []):
                p_strike = pos.get('strike', 0)
                p_entry = pos.get('entry_premium', 0)
                p_lots = pos.get('lots', 0)

                if p_lots <= 0 or p_strike <= 0:
                    continue

                _total_positions += 1
                try:
                    p_current = fetch_premium_fn(p_strike, option_type)
                except Exception as e:
                    _fetch_errors += 1
                    log.warning(
                        f"Failed to fetch shifted position premium "
                        f"@ {p_strike}: {e} [Robust v2 Fix #2: tracked as incomplete]"
                    )
                    continue

                # AUDIT FIX: Handle None return from cache miss
                if p_current is None:
                    _fetch_errors += 1
                    log.warning(
                        f"Shifted position premium is None @ {p_strike} — "
                        f"tracked as incomplete"
                    )
                    continue

                # §5.2 Case A: Use entry_premium as baseline for frozen positions.
                # Fix #19: Decimal arithmetic for P&L accumulation
                pos_loss = (_D(p_current) - _D(p_entry)) * _D(p_lots) * _LOT
                if pos_loss > 0:
                    shifted_loss += pos_loss
                    log.info(
                        f"Shifted position loss @ {p_strike}: "
                        f"({p_current:.2f} - {p_entry:.2f}) × {p_lots} lots "
                        f"= ${float(pos_loss):.4f} [baseline from entry_premium]"
                    )

        zero = _D(0)
        total_loss = active_loss + shifted_loss

        if shifted_loss > zero:
            log.info(
                f"TOTAL standard loss (active + shifted): "
                f"${float(active_loss):.4f} + ${float(shifted_loss):.4f} "
                f"= ${float(total_loss):.4f}"
            )

        # Robust v2 Fix #2: Flag calculation as incomplete if any fetch failed
        calculation_incomplete = _fetch_errors > 0
        if calculation_incomplete:
            log.warning(
                f"CALCULATION INCOMPLETE: {_fetch_errors}/{_total_positions} "
                f"frozen position premium fetches failed. "
                f"Loss may be understated by missing positions."
            )
            session['_fetch_error_count'] = session.get('_fetch_error_count', 0) + _fetch_errors

        # Return float at API boundary (Fix #19: only internal arithmetic uses Decimal)
        return float(max(total_loss, zero)), calculation_incomplete

    # =========================================================================
    # §5.2 Case B + §9: First-Reversal P&L
    # =========================================================================

    def calculate_reversal_loss(
        self,
        session: Dict,
        aggressor_side: str,
        fetch_premium_fn,
    ) -> Tuple[float, float, bool]:
        """
        §5.2 Case B / §9: Calculate actual P&L of ALL adjustment positions on
        the aggressor side. If net profitable → DO NOTHING. If underwater →
        hedge the loss.

        Args:
            session: Full session dict
            aggressor_side: 'ce' or 'pe'
            fetch_premium_fn: callable(strike, option_type) → current_premium

        Returns:
            (loss_to_cover, adjustment_pnl, calculation_incomplete)
            loss_to_cover = 0 if adjustments still profitable
            adjustment_pnl = actual computed P&L of adjustment fills
            calculation_incomplete = True if any premium fetch failed (Robust v2 Fix #2)
        """
        side_state = session.get(aggressor_side, {})
        option_type = 'call' if aggressor_side == 'ce' else 'put'
        # Robust v2 Fix #2: Track fetch failures
        _fetch_errors = 0
        _total_positions = 0

        # Fix #19: Use Decimal internally for P&L accumulation
        adjustment_pnl = _D(0)

        # Check adjustment fills at active strike
        for fill in side_state.get('adjustment_fills', []):
            strike = fill.get('strike', side_state.get('active_strike', 0))
            entry_prem = fill.get('premium', 0)
            lots = fill.get('lots', 0)
            _total_positions += 1

            try:
                current = fetch_premium_fn(strike, option_type)
                # §5.2 Case B / §9: Use entry_premium as baseline — ALWAYS.
                # Fix #19: Decimal arithmetic for P&L accumulation
                fill_pnl = (_D(entry_prem) - _D(current)) * _D(lots) * _LOT
                adjustment_pnl += fill_pnl
            except Exception as e:
                _fetch_errors += 1
                log.warning(f"Failed to fetch premium for {strike}: {e} [Robust v2 Fix #2: tracked]")

        # Check frozen ADJUSTMENT positions (exclude original entry positions).
        # §9: "The original CE and PE naturally offset each other. We only
        # need to hedge the loss on the adjustment positions."
        for frozen in side_state.get('frozen_positions', []):
            if frozen.get('type') == 'original':
                continue

            strike = frozen.get('strike', 0)
            entry_prem = frozen.get('entry_premium', 0)
            lots = frozen.get('lots', 0)
            _total_positions += 1

            try:
                current = fetch_premium_fn(strike, option_type)
                # Fix #19: Decimal arithmetic
                fill_pnl = (_D(entry_prem) - _D(current)) * _D(lots) * _LOT
                adjustment_pnl += fill_pnl
                log.debug(
                    f"Reversal frozen adj pos @ {strike}: entry={entry_prem:.2f}, "
                    f"current={current:.2f}, lots={lots}, pnl={float(fill_pnl):.4f}"
                )
            except Exception as e:
                _fetch_errors += 1
                log.warning(f"Failed to fetch premium for frozen {strike}: {e} [Robust v2 Fix #2: tracked]")

        adj_pnl_float = float(adjustment_pnl)
        log.info(
            f"Reversal P&L for {aggressor_side.upper()} adjustments: "
            f"{adj_pnl_float:.2f}"
        )

        # Robust v2 Fix #2: Flag calculation as incomplete
        calculation_incomplete = _fetch_errors > 0
        if calculation_incomplete:
            log.warning(
                f"REVERSAL CALCULATION INCOMPLETE: {_fetch_errors}/{_total_positions} "
                f"premium fetches failed. Reversal P&L may be inaccurate."
            )

        # Return float at API boundary (Fix #19: Decimal was internal only)
        if adjustment_pnl >= _D(0):
            return 0.0, adj_pnl_float, calculation_incomplete
        else:
            return float(abs(adjustment_pnl)), adj_pnl_float, calculation_incomplete

    # =========================================================================
    # §5.3-5.4: Determine strike and lots
    # =========================================================================

    @sealed
    def calculate_lots_to_sell(
        self,
        session: Dict,
        hedge_side: str,
        loss_to_cover: float,
        hedge_premium: float,
    ) -> Tuple[int, str, bool]:
        """
        §5.4: Calculate lots needed, apply buffer + constraints.

        Args:
            session: Full session dict
            hedge_side: Side to sell on ('ce' or 'pe')
            loss_to_cover: Dollar amount to cover
            hedge_premium: Premium per lot at the hedge strike

        Returns:
            (lots_to_sell, constraint_message or '', is_position_cap_hit)
            
        Fix F1.6: Returns is_position_cap_hit boolean to avoid fragile string
        matching for M2 recycling trigger.
        """
        if hedge_premium <= 0:
            return 0, 'Hedge premium is zero — cannot sell', False

        # AUDIT FIX: Don't sell phantom lots when there's no loss to cover
        if loss_to_cover <= 0:
            return 0, 'No loss to cover', False

        params = session.get('params', {})
        buffer_pct = params.get('premium_buffer_pct', 0.05)
        max_lots_per_side = params.get('max_lots_per_side', 100)

        # §14.1: Premium buffer
        # loss_to_cover is in USD, hedge_premium is USD/BTC
        # Each lot = LOT_SIZE_BTC, so lots needed = loss / (premium * LOT_SIZE_BTC)
        raw_lots = loss_to_cover / (hedge_premium * LOT_SIZE_BTC) * (1 + buffer_pct)
        lots_to_sell = max(math.ceil(raw_lots), 1)

        # ── T3-2: Gamma-Aware Lot Multiplier ──────────────────────────────
        # When the aggressor premium has spiked aggressively above trigger,
        # sell proportionally more lots to cover the accelerating loss.
        # Read aggressor excess_pct from session (set by evaluate_triggers).
        constraint_msg = ''
        gamma_mult = 1.0  # initialized before T3-2 block for combined ceiling
        if params.get('gamma_aware_enabled', True):
            trigger_res = session.get('_last_trigger_result', {})
            # hedge_side is opposite to aggressor: CE hedge → PE aggressor
            aggressor_side = 'pe' if hedge_side == 'ce' else 'ce'
            aggressor_excess_pct = trigger_res.get(f'{aggressor_side}_excess_pct', 0)
            max_mult = params.get('gamma_aware_max_multiplier', 1.3)
            if aggressor_excess_pct >= 200:
                gamma_mult = min(max_mult, 1.3)
            elif aggressor_excess_pct >= 100:
                gamma_mult = min(max_mult, 1.2)
            elif aggressor_excess_pct >= 50:
                gamma_mult = min(max_mult, 1.1)
            else:
                gamma_mult = 1.0
            if gamma_mult > 1.0:
                pre_gamma = lots_to_sell
                lots_to_sell = max(math.ceil(lots_to_sell * gamma_mult), 1)
                constraint_msg = (
                    f"Gamma-aware {gamma_mult:.1f}x ({aggressor_excess_pct:.0f}% excess): "
                    f"{pre_gamma} → {lots_to_sell} lots"
                )
        # ── END T3-2 ──────────────────────────────────────────────────────

        # ── Breakeven Aggression Multiplier ──────────────────────────────
        # Non-directional: applies to ANY triggered adjustment when spot approaches
        # portfolio breakeven. Multiplier is pre-computed by BreakevenEngine and
        # stored in session by the monitor at Step 5.7.
        breakeven_mult = session.get('_breakeven_multiplier', 1.0)
        if breakeven_mult > 1.0:
            pre_be = lots_to_sell
            lots_to_sell = max(math.ceil(lots_to_sell * breakeven_mult), 1)
            be_msg = (
                f"Breakeven {breakeven_mult:.2f}x ({session.get('_breakeven_zone', 'UNKNOWN')} zone): "
                f"{pre_be} → {lots_to_sell} lots"
            )
            constraint_msg = f"{constraint_msg}; {be_msg}" if constraint_msg else be_msg
        # ── END Breakeven Multiplier ──────────────────────────────────────

        # ── IMP-2 + Trend Boost: Directional lot adjustment ──────────────
        # When a trend is detected, the dangerous side (CE in uptrend) gets
        # reduced lots, but the safe/hedge side (PE in uptrend) gets BOOSTED
        # lots when trend_boost_enabled. This aggressively collects premium
        # on the safe side while the trend confirms it's far OTM.
        trend_tier = session.get('_trend_tier', 0)
        trend_boost_enabled = params.get('trend_boost_enabled', False)
        trend_direction = session.get('_trend_direction', 'none')

        # Determine if hedge_side is the "safe" side for this trend
        # UP trend: PE is safe (far OTM), CE is dangerous (approaching ATM)
        # DOWN trend: CE is safe (far OTM), PE is dangerous (approaching ATM)
        is_safe_side = (
            (trend_direction == 'up' and hedge_side == 'pe') or
            (trend_direction == 'down' and hedge_side == 'ce')
        )

        if trend_tier >= 1 and trend_boost_enabled and is_safe_side:
            # Trend Boost: multiply lots on safe side
            if trend_tier >= 3:
                boost_mult = params.get('trend_boost_tier3_mult', 2.0)
            elif trend_tier >= 2:
                boost_mult = params.get('trend_boost_tier2_mult', 1.5)
            else:
                boost_mult = params.get('trend_boost_tier1_mult', 1.3)
            original_lots = lots_to_sell
            lots_to_sell = max(math.ceil(lots_to_sell * boost_mult), 1)
            session['_trend_boost_active'] = True
            session['_trend_boost_mult'] = boost_mult
            if lots_to_sell > original_lots:
                trend_msg = (
                    f"Trend Boost T{trend_tier} ({trend_direction.upper()}): "
                    f"{original_lots} → {lots_to_sell} ({boost_mult:.1f}x safe-side boost)"
                )
                constraint_msg = f"{constraint_msg}; {trend_msg}" if constraint_msg else trend_msg
        elif trend_tier >= 1:
            # ATM Shield override: skip T1 lot reduction — shield manages ATM risk
            shield_on = params.get('atm_shield_enabled', False)
            if shield_on:
                session['_trend_boost_active'] = False
                session['_trend_boost_mult'] = 1.0
            else:
                # Original IMP-2: reduce lots on dangerous side (or when boost disabled)
                lot_reduction = params.get('trend_tier1_lot_reduction', 0.30)
                multiplier = max(1.0 - lot_reduction, 0.1)  # Floor at 10% to avoid zero
                original_lots = lots_to_sell
                lots_to_sell = max(math.ceil(lots_to_sell * multiplier), 1)
                session['_trend_boost_active'] = False
                session['_trend_boost_mult'] = 1.0
                if lots_to_sell < original_lots:
                    trend_msg = (
                        f"Trend Tier {trend_tier} lot reduction: {original_lots} → "
                        f"{lots_to_sell} ({lot_reduction:.0%} reduction)"
                    )
                    constraint_msg = f"{constraint_msg}; {trend_msg}" if constraint_msg else trend_msg
        else:
            session['_trend_boost_active'] = False
            session['_trend_boost_mult'] = 1.0
        # ── END IMP-2 + Trend Boost ───────────────────────────────────────

        # ── Combined Multiplier Ceiling ───────────────────────────────────
        # After all multiplicative amplifiers, before hard caps and reductions.
        # Prevents gamma × breakeven × trend compound runaway.
        # Does NOT include asymmetry or OTM scaling (those are reductive, not amplifiers).
        max_combined = params.get('max_combined_lot_multiplier', 3.0)
        if max_combined > 0 and (gamma_mult > 1.0 or breakeven_mult > 1.0 or
                                  session.get('_trend_boost_active')):
            boost_mult = session.get('_trend_boost_mult', 1.0)
            combined = gamma_mult * breakeven_mult * (boost_mult if session.get('_trend_boost_active') else 1.0)
            if combined > max_combined:
                # Scale back proportionally
                overshoot = combined / max_combined
                pre_ceil = lots_to_sell
                lots_to_sell = max(math.ceil(lots_to_sell / overshoot), 1)
                if lots_to_sell < pre_ceil:
                    ceil_msg = (
                        f"Combined mult cap {max_combined:.1f}x (was {combined:.2f}x): "
                        f"{pre_ceil} → {lots_to_sell} lots"
                    )
                    constraint_msg = f"{constraint_msg}; {ceil_msg}" if constraint_msg else ceil_msg
        # ── END Combined Multiplier Ceiling ──────────────────────────────

        # §13.1: Position cap — Split Ledger: only active_lots count against cap
        hedge_state = session.get(hedge_side, {})
        current_total = hedge_state.get('active_lots', 0)

        if current_total + lots_to_sell > max_lots_per_side:
            lots_to_sell = max_lots_per_side - current_total
            if lots_to_sell <= 0:
                # Fix F1.6: Return is_position_cap=True for M2 recycling trigger
                return 0, (
                    f"Position cap reached: {hedge_side.upper()} has "
                    f"{current_total}/{max_lots_per_side} lots"
                ), True  # is_position_cap
            cap_msg = (
                f"Capped from {math.ceil(raw_lots)} to {lots_to_sell} "
                f"(position cap: {max_lots_per_side})"
            )
            # Combine with any prior constraint message (e.g. trend lot reduction)
            constraint_msg = f"{constraint_msg}; {cap_msg}" if constraint_msg else cap_msg

        # ── Split Ledger: max_total_exposure safety ceiling ───────────────────
        # active_lots cap is the primary gate. This is the ABSOLUTE ceiling on
        # combined active + frozen lots to guard against runaway accumulation.
        # IMPORTANT: error message must NOT contain "Position cap reached" —
        # that exact string triggers M2 recycling at monitor line ~2615.
        max_total_exposure = params.get('max_total_exposure', 0)
        if max_total_exposure <= 0:
            max_total_exposure = max_lots_per_side * 2
        total_exposure = hedge_state.get('total_lots', 0)
        if total_exposure + lots_to_sell > max_total_exposure:
            lots_to_sell = max(max_total_exposure - total_exposure, 0)
            if lots_to_sell <= 0:
                # Note: is_position_cap=False — this is total exposure ceiling, not position cap
                return 0, (
                    f"Total exposure ceiling: {hedge_side.upper()} has "
                    f"{total_exposure}/{max_total_exposure} lots (active+frozen)"
                ), False  # NOT position cap — don't trigger M2
            exp_msg = (
                f"Capped by total exposure: {lots_to_sell} lots "
                f"(ceiling: {max_total_exposure})"
            )
            constraint_msg = f"{constraint_msg}; {exp_msg}" if constraint_msg else exp_msg
        # ── END Split Ledger ──────────────────────────────────────────────────

        # ── IMP-3: Asymmetry 5:1 lot reduction ───────────────────────────────
        # When ratio >= 5:1, check_asymmetry sets _asymmetry_lot_reduction_pct
        # on the session. Apply it only when selling the heavy side.
        asym_reduction = session.get('_asymmetry_lot_reduction_pct', 1.0)
        asym_heavy_side = session.get('_asymmetry_heavy_side', '')
        if asym_reduction < 1.0 and hedge_side == asym_heavy_side:
            original_lots = lots_to_sell
            lots_to_sell = max(math.ceil(lots_to_sell * asym_reduction), 1)
            if lots_to_sell < original_lots:
                asym_msg = (
                    f"Asymmetry 5:1 reduction: {original_lots} → "
                    f"{lots_to_sell} ({int((1 - asym_reduction) * 100)}% reduction on heavy side)"
                )
                constraint_msg = f"{constraint_msg}; {asym_msg}" if constraint_msg else asym_msg
        # ── END IMP-3 ─────────────────────────────────────────────────────

        # ── IMP-4: Strike-shift OTM lot scaling ──────────────────────────
        # When selling after a strike shift, scale lots based on how close the
        # new strike is to spot. Stored in _strike_shift_otm_multiplier by the
        # monitor before calling calculate_lots_to_sell.
        otm_multiplier = session.get('_strike_shift_otm_multiplier', 1.0)
        if params.get('strike_shift_use_lot_scaling', False) and otm_multiplier < 1.0:
            original_lots = lots_to_sell
            lots_to_sell = max(math.ceil(lots_to_sell * otm_multiplier), 1)
            if lots_to_sell < original_lots:
                otm_msg = (
                    f"Strike-shift OTM scaling: {original_lots} → "
                    f"{lots_to_sell} (multiplier {otm_multiplier:.2f})"
                )
                constraint_msg = f"{constraint_msg}; {otm_msg}" if constraint_msg else otm_msg
        # ── END IMP-4 ─────────────────────────────────────────────────────

        return lots_to_sell, constraint_msg, False  # No cap hit if we got here

    # =========================================================================
    # §5.5: Execute adjustment order
    # =========================================================================

    async def execute_adjustment(
        self,
        session: Dict,
        hedge_side: str,
        hedge_strike: float,
        lots_to_sell: int,
        ce_now: float,
        pe_now: float,
        adj_type: str = 'standard',
        fetch_premium_fn=None,
    ) -> Dict[str, Any]:
        """
        Execute the adjustment sell order and update session state.

        Args:
            session: Full session dict (mutated in place)
            hedge_side: 'ce' or 'pe' — side to sell on
            hedge_strike: Strike to sell at
            lots_to_sell: Number of lots
            ce_now: Current CE premium (for trigger update)
            pe_now: Current PE premium (for trigger update)
            adj_type: 'standard', 'reversal', 'first_reversal'
            fetch_premium_fn: Optional callable for frozen position snapshot

        Returns:
            {success, fill_price, premium_collected, lots_sold, ...}
        """
        # Fix F2.6: Validate strike > 0 before symbol building
        if hedge_strike <= 0:
            log.error(f"Invalid strike {hedge_strike} for adjustment")
            return {
                'success': False,
                'error': f'Invalid strike price: {hedge_strike}',
            }
        
        # Build symbol
        expiry = session.get('params', {}).get('expiry', '')
        underlying = 'BTC'
        option_type = 'call' if hedge_side == 'ce' else 'put'
        symbol = self.initializer.build_symbol(
            option_type, underlying, hedge_strike, expiry
        )

        aggressor_side = 'pe' if hedge_side == 'ce' else 'ce'

        log.info(
            f"Executing adjustment: SELL {lots_to_sell} {hedge_side.upper()} "
            f"@ {hedge_strike} ({symbol}), type={adj_type}"
        )

        # ── PENDING ORDER GUARD: register before placement ───────────────────
        # The order_id is not known yet, so we register a placeholder with
        # order_id='pending'.  Once smart_execute returns, we update it with
        # the real order_id (or clear it on failure).
        session_id = session.get('session_id', '')
        order_id_for_pending = 'pending'
        if session_id:
            try:
                from .mmm_pending_orders import register_pending, clear_pending
                register_pending(
                    session_id=session_id,
                    side=hedge_side,
                    order_id='pending',
                    symbol=symbol,
                    lots=lots_to_sell,
                    strike=hedge_strike,
                    adj_type=adj_type,
                )
            except Exception as _pe:
                log.warning(f"Failed to register pending order: {_pe}")
        # ── END PRE-REGISTRATION ─────────────────────────────────────────────

        try:
            result = await self.executor.smart_execute(
                symbol=symbol,
                side='sell',
                size=lots_to_sell,
            )

            # ── UPDATE PENDING REGISTRY WITH REAL ORDER ID ───────────────────
            if session_id:
                try:
                    from .mmm_pending_orders import register_pending, clear_pending
                    real_order_id = result.get('order_id', '')
                    if real_order_id and result.get('success'):
                        # Update with real order_id — will be cleared after fill recorded below
                        register_pending(
                            session_id=session_id,
                            side=hedge_side,
                            order_id=str(real_order_id),
                            symbol=symbol,
                            lots=lots_to_sell,
                            strike=hedge_strike,
                            adj_type=adj_type,
                        )
                    elif not result.get('success'):
                        # Execution failed — clear the pending entry so next beat can retry
                        clear_pending(session_id, hedge_side)
                except Exception as _pe:
                    log.warning(f"Failed to update pending order registry: {_pe}")
            # ── END REGISTRY UPDATE ──────────────────────────────────────────

            if not result.get('success'):
                return {
                    'success': False,
                    'error': result.get('error', 'Order not filled'),
                    'result': result,
                }

            fill_price = result.get('fill_price', 0)
            # P1-D: use actual filled size, not requested size (partial fill handling)
            filled_lots = result.get('filled_size', lots_to_sell)
            if filled_lots <= 0:
                filled_lots = lots_to_sell  # fallback if executor didn't report it
            if filled_lots < lots_to_sell:
                log.warning(
                    f"PARTIAL FILL: requested {lots_to_sell} {hedge_side.upper()} lots, "
                    f"only {filled_lots} filled. Ledger updated with actual fill."
                )
            premium_collected = fill_price * filled_lots * LOT_SIZE_BTC

            # §6: Update state
            self._update_state_after_adjustment(
                session=session,
                hedge_side=hedge_side,
                aggressor_side=aggressor_side,
                strike=hedge_strike,
                lots=filled_lots,
                fill_price=fill_price,
                ce_now=ce_now,
                pe_now=pe_now,
                adj_type=adj_type,
                premium_collected=premium_collected,
                fetch_premium_fn=fetch_premium_fn,
            )

            # ── CLEAR PENDING AFTER SUCCESSFUL STATE UPDATE ──────────────────
            # Fill is now recorded in session state — guard can be cleared.
            if session_id:
                try:
                    from .mmm_pending_orders import clear_pending
                    clear_pending(session_id, hedge_side)
                except Exception as _pe:
                    log.warning(f"Failed to clear pending order: {_pe}")
            # ── END CLEAR ────────────────────────────────────────────────────

            return {
                'success': True,
                'fill_price': fill_price,
                'premium_collected': premium_collected,
                'lots_sold': filled_lots,
                'lots_requested': lots_to_sell,
                'partial_fill': filled_lots < lots_to_sell,
                'symbol': symbol,
                'adj_type': adj_type,
            }

        except Exception as e:
            log.exception(f"Adjustment execution failed: {e}")
            # Clear pending registry on exception so next heartbeat can retry
            if session_id:
                try:
                    from .mmm_pending_orders import clear_pending
                    clear_pending(session_id, hedge_side)
                except Exception:
                    pass
            return {
                'success': False,
                'error': str(e),
            }

    # =========================================================================
    # §6: State Update After Adjustment
    # =========================================================================

    def _update_state_after_adjustment(
        self,
        session: Dict,
        hedge_side: str,
        aggressor_side: str,
        strike: float,
        lots: int,
        fill_price: float,
        ce_now: float,
        pe_now: float,
        adj_type: str,
        premium_collected: float,
        fetch_premium_fn=None,
    ):
        """
        §6.1-6.4: Update session state after a successful adjustment.
        """
        hedge_state = session.get(hedge_side, {})

        # §6.1: Record the fill — Fix #23: append to positions[] (Unified Ledger)
        now = datetime.now(timezone.utc).isoformat()
        counter = hedge_state.get('_pos_counter', 0) + 1
        hedge_state['_pos_counter'] = counter
        hedge_state.setdefault('positions', []).append({
            'id': f"{hedge_side}_adj_{counter:03d}",
            'strike': strike,
            'lots': lots,
            'entry_premium': fill_price,
            'premium': fill_price,          # backward-compat alias
            'type': adj_type or 'adjustment',
            'status': 'active',
            'created_at': now,
            'shifted_at': None,
            'closed_at': None,
            'realized_pnl': None,
            'timestamp': now,               # backward-compat alias
        })
        recompute_side_lots(hedge_state)    # rebuilds adjustment_fills view
        session[hedge_side] = hedge_state

        # §6.2: Update BOTH trigger snapshots (incl. frozen positions)
        update_trigger_snapshots(session, ce_now, pe_now, fetch_premium_fn=fetch_premium_fn)

        # §6.3: Update tracking
        session['last_aggressor'] = aggressor_side.upper()
        session['adjustment_count'] = session.get('adjustment_count', 0) + 1
        session['total_premium_collected'] = (
            session.get('total_premium_collected', 0) + premium_collected
        )
        side_prem_key = 'ce_premium_collected' if hedge_side.lower() == 'ce' else 'pe_premium_collected'
        session[side_prem_key] = session.get(side_prem_key, 0) + premium_collected

        session.setdefault('adjustment_history', []).append({
            'side': hedge_side.upper(),
            'aggressor': aggressor_side.upper(),
            'lots_sold': lots,
            'premium': fill_price,
            'strike': strike,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'type': adj_type,
            'premium_collected': premium_collected,
            'adjustment_number': session['adjustment_count'],
            'spot': session.get('_regime_spot_price', 0),
        })

        session['updated_at'] = datetime.now(timezone.utc).isoformat()

        log.info(
            f"State updated: adj #{session['adjustment_count']}, "
            f"sold {lots} {hedge_side.upper()} @ {strike} for {fill_price:.2f}, "
            f"total premium: {session['total_premium_collected']:.2f}"
        )

    # =========================================================================
    # P&L Computation
    # =========================================================================

    def compute_unrealized_pnl(
        self,
        session: Dict,
        fetch_premium_fn,
    ) -> float:
        """
        Compute unrealized P&L across all open positions.

        For sold options: P&L = (entry_premium - current_premium) × lots
        (Positive = option decayed = profit for seller)

        Robust v2 Fix #2: Tracks fetch failures and stores _pnl_fetch_errors
        in session state. If >50% of positions fail, sets _pnl_calculation_incomplete.
        """
        # Fix #19: Use Decimal internally to prevent float rounding accumulation
        total_unrealized = _D(0)
        _fetch_errors = 0
        _total_positions = 0

        for side_key in ['ce', 'pe']:
            side_state = session.get(side_key, {})
            option_type = 'call' if side_key == 'ce' else 'put'

            # Original lots
            orig_lots = side_state.get('original_lots', 0)
            orig_prem = side_state.get('original_premium', 0)
            active_strike = side_state.get('active_strike', 0)

            if orig_lots > 0 and active_strike > 0:
                _total_positions += 1
                try:
                    current = fetch_premium_fn(active_strike, option_type)
                    if current is None:
                        raise ValueError(f"Premium is None for {side_key}@{active_strike}")
                    total_unrealized += (_D(orig_prem) - _D(current)) * _D(orig_lots) * _LOT
                except Exception as e:
                    _fetch_errors += 1
                    log.warning(f"Failed to fetch {side_key} premium at {active_strike}: {e}")

            # Adjustment fills at active strike
            for fill in side_state.get('adjustment_fills', []):
                lots = fill.get('lots', 0)
                prem = fill.get('premium', 0)
                strike = fill.get('strike', active_strike)
                if lots > 0:
                    _total_positions += 1
                    try:
                        current = fetch_premium_fn(strike, option_type)
                        if current is None:
                            raise ValueError(f"Premium is None for {side_key}@{strike}")
                        total_unrealized += (_D(prem) - _D(current)) * _D(lots) * _LOT
                    except Exception as e:
                        _fetch_errors += 1
                        log.warning(f"Failed to fetch {side_key} adj premium at {strike}: {e}")

            # Frozen positions
            for frozen in side_state.get('frozen_positions', []):
                lots = frozen.get('lots', 0)
                prem = frozen.get('entry_premium', 0)
                strike = frozen.get('strike', 0)
                if lots > 0 and strike > 0:
                    _total_positions += 1
                    try:
                        current = fetch_premium_fn(strike, option_type)
                        if current is None:
                            raise ValueError(f"Premium is None for {side_key}@{strike}")
                        total_unrealized += (_D(prem) - _D(current)) * _D(lots) * _LOT
                    except Exception as e:
                        _fetch_errors += 1
                        log.warning(f"Failed to fetch {side_key} frozen premium at {strike}: {e}")

        # Robust v2 Fix #2: Track incomplete calculations in session state
        session['_pnl_fetch_errors'] = _fetch_errors
        if _total_positions > 0 and _fetch_errors > (_total_positions * 0.5):
            session['_pnl_calculation_incomplete'] = True
            log.error(
                f"P&L CALCULATION INCOMPLETE: {_fetch_errors}/{_total_positions} "
                f"position premium fetches failed (>50%). P&L is unreliable."
            )
        else:
            session.pop('_pnl_calculation_incomplete', None)

        # Fix #19: Return float at API boundary (Decimal was internal only)
        return float(total_unrealized)

    def compute_total_pnl(self, session: Dict, fetch_premium_fn) -> Dict[str, float]:
        """
        Compute complete P&L breakdown.

        Returns:
            {realized, unrealized, fees, net_pnl, total_premium_collected}
        """
        realized = session.get('realized_pnl', 0)
        fees = session.get('total_fees', 0)
        unrealized = self.compute_unrealized_pnl(session, fetch_premium_fn)
        premium = session.get('total_premium_collected', 0)

        return {
            'realized': realized,
            'unrealized': round(unrealized, 2),
            'fees': fees,
            'net_pnl': round(realized + unrealized - fees, 2),
            'total_premium_collected': premium,
        }

    # =========================================================================
    # §14.5: P&L Reconciliation
    # =========================================================================

    def reconcile_pnl(
        self,
        session: Dict,
        fetch_premium_fn,
        threshold: float = None,
    ) -> bool:
        """
        §14.5: Every 5 adjustments, verify tracked P&L matches computed P&L.

        L-4 fix: threshold is now read from session params so it can be tuned
        per-session (small accounts need $1-5, large accounts may use $50+).
        Defaults to the 'pnl_reconciliation_threshold' param (default $10.0).

        Returns:
            True if reconciliation was needed (discrepancy found)
        """
        if threshold is None:
            threshold = session.get('params', {}).get('pnl_reconciliation_threshold', 10.0)

        pnl = self.compute_total_pnl(session, fetch_premium_fn)
        # AUDIT FIX: tracked must subtract fees to match actual (net_pnl includes fees)
        fees = session.get('total_fees', 0)
        tracked = session.get('realized_pnl', 0) + session.get('unrealized_pnl', 0) - fees
        actual = pnl['net_pnl']

        discrepancy = abs(actual - tracked)

        if discrepancy > threshold:
            log.warning(
                f"P&L reconciliation: tracked={tracked:.2f}, "
                f"actual={actual:.2f}, discrepancy={discrepancy:.2f}"
            )
            session['unrealized_pnl'] = pnl['unrealized']
            return True

        return False


# =============================================================================
# Singleton
# =============================================================================

# M-4 fix: double-checked locking prevents TOCTOU race on singleton creation
_engine_instance = None
_engine_lock = threading.Lock()


def get_engine() -> MMMEngine:
    global _engine_instance
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                _engine_instance = MMMEngine()
    return _engine_instance
