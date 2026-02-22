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
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from .mmm_state import recompute_side_lots
from .mmm_trigger import update_trigger_snapshots
from .mmm_constants import LOT_SIZE_BTC, strike_key

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

        # 1. Active strike loss (trigger-based)
        active_loss = (premium_now - trigger) * active_lots * LOT_SIZE_BTC

        log.info(
            f"Standard loss (active @ {active_strike}): "
            f"({premium_now:.2f} - {trigger:.2f}) × {active_lots} lots "
            f"× {LOT_SIZE_BTC} = ${active_loss:.4f}"
        )

        # 2. Shifted position losses — ALL positions at old strikes
        #    Every open position contributes to total loss. No exceptions.
        #    §5.2 Case A: Use entry_premium as baseline for frozen positions
        #    (lifetime loss). trigger_snapshot is only for the ACTIVE strike.
        shifted_loss = 0.0
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

                # §5.2 Case A: Use entry_premium as baseline for frozen positions.
                # The spec computes LIFETIME loss (current vs entry) for shifted
                # positions, NOT incremental loss vs trigger_snapshot.
                # trigger_snapshot is only used as baseline for the ACTIVE strike.
                # Using entry_premium ensures we only hedge when the position is
                # actually underwater vs what we sold it for.
                p_baseline = p_entry

                # Loss = (current - entry) per lot
                # Positive when premium rose past entry (seller losing)
                pos_loss = (p_current - p_baseline) * p_lots * LOT_SIZE_BTC
                if pos_loss > 0:
                    shifted_loss += pos_loss
                    log.info(
                        f"Shifted position loss @ {p_strike}: "
                        f"({p_current:.2f} - {p_baseline:.2f}) × {p_lots} lots "
                        f"= ${pos_loss:.4f} [baseline from entry_premium]"
                    )

        total_loss = max(active_loss, 0) + shifted_loss

        if shifted_loss > 0:
            log.info(
                f"TOTAL standard loss (active + shifted): "
                f"${max(active_loss, 0):.4f} + ${shifted_loss:.4f} "
                f"= ${total_loss:.4f}"
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

        return max(total_loss, 0), calculation_incomplete

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

        adjustment_pnl = 0.0

        # Check adjustment fills at active strike
        for fill in side_state.get('adjustment_fills', []):
            strike = fill.get('strike', side_state.get('active_strike', 0))
            entry_prem = fill.get('premium', 0)
            lots = fill.get('lots', 0)
            _total_positions += 1

            try:
                current = fetch_premium_fn(strike, option_type)
                # §5.2 Case B / §9: Use entry_premium as baseline — ALWAYS.
                # The reversal formula computes the ACTUAL P&L of each adjustment
                # fill: (entry_premium - current_premium). This tells us whether
                # the fill is profitable or underwater since it was opened.
                # trigger_snapshot must NOT be used here — it gets updated to
                # current price after every adjustment, making P&L appear ~0.
                fill_pnl = (entry_prem - current) * lots * LOT_SIZE_BTC
                adjustment_pnl += fill_pnl
            except Exception as e:
                _fetch_errors += 1
                log.warning(f"Failed to fetch premium for {strike}: {e} [Robust v2 Fix #2: tracked]")

        # Check frozen ADJUSTMENT positions (exclude original entry positions).
        # §9: "The original CE and PE naturally offset each other. We only
        # need to hedge the loss on the adjustment positions."
        # Frozen positions with type='original' are excluded — they have a
        # natural hedge on the opposite side and are NOT naked risk.
        for frozen in side_state.get('frozen_positions', []):
            # §9: Only include adjustment positions in reversal P&L
            if frozen.get('type') == 'original':
                continue

            strike = frozen.get('strike', 0)
            entry_prem = frozen.get('entry_premium', 0)
            lots = frozen.get('lots', 0)
            _total_positions += 1

            try:
                current = fetch_premium_fn(strike, option_type)
                # §5.2 Case B: Use entry_premium as baseline — ALWAYS.
                fill_pnl = (entry_prem - current) * lots * LOT_SIZE_BTC
                adjustment_pnl += fill_pnl
                log.debug(
                    f"Reversal frozen adj pos @ {strike}: entry={entry_prem:.2f}, "
                    f"current={current:.2f}, lots={lots}, pnl={fill_pnl:.4f}"
                )
            except Exception as e:
                _fetch_errors += 1
                log.warning(f"Failed to fetch premium for frozen {strike}: {e} [Robust v2 Fix #2: tracked]")

        log.info(
            f"Reversal P&L for {aggressor_side.upper()} adjustments: "
            f"{adjustment_pnl:.2f}"
        )

        # Robust v2 Fix #2: Flag calculation as incomplete
        calculation_incomplete = _fetch_errors > 0
        if calculation_incomplete:
            log.warning(
                f"REVERSAL CALCULATION INCOMPLETE: {_fetch_errors}/{_total_positions} "
                f"premium fetches failed. Reversal P&L may be inaccurate."
            )

        if adjustment_pnl >= 0:
            # Adjustments still in profit → DO NOTHING
            return 0.0, adjustment_pnl, calculation_incomplete
        else:
            return abs(adjustment_pnl), adjustment_pnl, calculation_incomplete

    # =========================================================================
    # §5.3-5.4: Determine strike and lots
    # =========================================================================

    def calculate_lots_to_sell(
        self,
        session: Dict,
        hedge_side: str,
        loss_to_cover: float,
        hedge_premium: float,
    ) -> Tuple[int, str]:
        """
        §5.4: Calculate lots needed, apply buffer + constraints.

        Args:
            session: Full session dict
            hedge_side: Side to sell on ('ce' or 'pe')
            loss_to_cover: Dollar amount to cover
            hedge_premium: Premium per lot at the hedge strike

        Returns:
            (lots_to_sell, constraint_message or '')
        """
        if hedge_premium <= 0:
            return 0, 'Hedge premium is zero — cannot sell'

        params = session.get('params', {})
        buffer_pct = params.get('premium_buffer_pct', 0.05)
        max_lots_per_side = params.get('max_lots_per_side', 100)

        # §14.1: Premium buffer
        # loss_to_cover is in USD, hedge_premium is USD/BTC
        # Each lot = LOT_SIZE_BTC, so lots needed = loss / (premium * LOT_SIZE_BTC)
        raw_lots = loss_to_cover / (hedge_premium * LOT_SIZE_BTC) * (1 + buffer_pct)
        lots_to_sell = max(math.ceil(raw_lots), 1)

        # §13.1: Position cap
        hedge_state = session.get(hedge_side, {})
        current_total = hedge_state.get('total_lots', 0)
        constraint_msg = ''

        if current_total + lots_to_sell > max_lots_per_side:
            lots_to_sell = max_lots_per_side - current_total
            if lots_to_sell <= 0:
                return 0, (
                    f"Position cap reached: {hedge_side.upper()} has "
                    f"{current_total}/{max_lots_per_side} lots"
                )
            constraint_msg = (
                f"Capped from {math.ceil(raw_lots)} to {lots_to_sell} "
                f"(position cap: {max_lots_per_side})"
            )

        return lots_to_sell, constraint_msg

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
            premium_collected = fill_price * lots_to_sell * LOT_SIZE_BTC

            # §6: Update state
            self._update_state_after_adjustment(
                session=session,
                hedge_side=hedge_side,
                aggressor_side=aggressor_side,
                strike=hedge_strike,
                lots=lots_to_sell,
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
                'lots_sold': lots_to_sell,
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

        # §6.1: Record the fill at the active strike
        hedge_state.setdefault('adjustment_fills', []).append({
            'lots': lots,
            'premium': fill_price,
            'strike': strike,
            'timestamp': datetime.utcnow().isoformat(),
            'type': adj_type,
        })
        recompute_side_lots(hedge_state)
        session[hedge_side] = hedge_state

        # §6.2: Update BOTH trigger snapshots (incl. frozen positions)
        update_trigger_snapshots(session, ce_now, pe_now, fetch_premium_fn=fetch_premium_fn)

        # §6.3: Update tracking
        session['last_aggressor'] = aggressor_side.upper()
        session['adjustment_count'] = session.get('adjustment_count', 0) + 1
        session['total_premium_collected'] = (
            session.get('total_premium_collected', 0) + premium_collected
        )

        session.setdefault('adjustment_history', []).append({
            'side': hedge_side.upper(),
            'aggressor': aggressor_side.upper(),
            'lots_sold': lots,
            'premium': fill_price,
            'strike': strike,
            'timestamp': datetime.utcnow().isoformat(),
            'type': adj_type,
            'premium_collected': premium_collected,
            'adjustment_number': session['adjustment_count'],
        })

        session['updated_at'] = datetime.utcnow().isoformat()

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
        total_unrealized = 0.0
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
                    total_unrealized += (orig_prem - current) * orig_lots * LOT_SIZE_BTC
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
                        total_unrealized += (prem - current) * lots * LOT_SIZE_BTC
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
                        total_unrealized += (prem - current) * lots * LOT_SIZE_BTC
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

        return total_unrealized

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
        threshold: float = 10.0,
    ) -> bool:
        """
        §14.5: Every 5 adjustments, verify tracked P&L matches computed P&L.

        Returns:
            True if reconciliation was needed (discrepancy found)
        """
        pnl = self.compute_total_pnl(session, fetch_premium_fn)
        tracked = session.get('realized_pnl', 0) + session.get('unrealized_pnl', 0)
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

_engine_instance = None


def get_engine() -> MMMEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = MMMEngine()
    return _engine_instance
