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
from .mmm_constants import LOT_SIZE_BTC

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
    ) -> float:
        """
        §5.2 Case A: loss = (premium_now - trigger_snapshot) × active_lots

        Args:
            session: Full session dict
            aggressor_side: 'ce' or 'pe' — the side whose premium rose
            premium_now: Current premium of the aggressor

        Returns:
            Loss amount (positive value) to cover
        """
        side_state = session.get(aggressor_side, {})
        active_strike = str(int(side_state.get('active_strike', 0)))
        trigger = side_state.get('trigger_snapshot', {}).get(active_strike, 0)
        active_lots = side_state.get('active_lots', 0)

        loss = (premium_now - trigger) * active_lots * LOT_SIZE_BTC

        log.info(
            f"Standard loss: ({premium_now:.2f} - {trigger:.2f}) × "
            f"{active_lots} lots × {LOT_SIZE_BTC} = ${loss:.4f}"
        )

        return max(loss, 0)

    # =========================================================================
    # §5.2 Case B + §9: First-Reversal P&L
    # =========================================================================

    def calculate_reversal_loss(
        self,
        session: Dict,
        aggressor_side: str,
        fetch_premium_fn,
    ) -> Tuple[float, float]:
        """
        §5.2 Case B / §9: Calculate actual P&L of ALL adjustment positions on
        the aggressor side. If net profitable → DO NOTHING. If underwater →
        hedge the loss.

        Args:
            session: Full session dict
            aggressor_side: 'ce' or 'pe'
            fetch_premium_fn: callable(strike, option_type) → current_premium

        Returns:
            (loss_to_cover, adjustment_pnl)
            loss_to_cover = 0 if adjustments still profitable
            adjustment_pnl = actual computed P&L of adjustment fills
        """
        side_state = session.get(aggressor_side, {})
        option_type = 'call' if aggressor_side == 'ce' else 'put'

        adjustment_pnl = 0.0

        # Check adjustment fills at active strike
        for fill in side_state.get('adjustment_fills', []):
            strike = fill.get('strike', side_state.get('active_strike', 0))
            entry_prem = fill.get('premium', 0)
            lots = fill.get('lots', 0)

            try:
                current = fetch_premium_fn(strike, option_type)
                # Sold at entry_prem, costs current to buy back
                # P&L = (entry_prem - current) × lots × LOT_SIZE_BTC (positive = profit)
                fill_pnl = (entry_prem - current) * lots * LOT_SIZE_BTC
                adjustment_pnl += fill_pnl
            except Exception as e:
                log.warning(f"Failed to fetch premium for {strike}: {e}")

        # Check frozen positions
        for frozen in side_state.get('frozen_positions', []):
            strike = frozen.get('strike', 0)
            entry_prem = frozen.get('entry_premium', 0)
            lots = frozen.get('lots', 0)

            try:
                current = fetch_premium_fn(strike, option_type)
                fill_pnl = (entry_prem - current) * lots * LOT_SIZE_BTC
                adjustment_pnl += fill_pnl
            except Exception as e:
                log.warning(f"Failed to fetch premium for frozen {strike}: {e}")

        log.info(
            f"Reversal P&L for {aggressor_side.upper()} adjustments: "
            f"{adjustment_pnl:.2f}"
        )

        if adjustment_pnl >= 0:
            # Adjustments still in profit → DO NOTHING
            return 0.0, adjustment_pnl
        else:
            return abs(adjustment_pnl), adjustment_pnl

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

        try:
            result = await self.executor.smart_execute(
                symbol=symbol,
                side='sell',
                size=lots_to_sell,
            )

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
            )

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

        # §6.2: Update BOTH trigger snapshots
        update_trigger_snapshots(session, ce_now, pe_now)

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
        """
        total_unrealized = 0.0

        for side_key in ['ce', 'pe']:
            side_state = session.get(side_key, {})
            option_type = 'call' if side_key == 'ce' else 'put'

            # Original lots
            orig_lots = side_state.get('original_lots', 0)
            orig_prem = side_state.get('original_premium', 0)
            active_strike = side_state.get('active_strike', 0)

            if orig_lots > 0 and active_strike > 0:
                try:
                    current = fetch_premium_fn(active_strike, option_type)
                    total_unrealized += (orig_prem - current) * orig_lots * LOT_SIZE_BTC
                except Exception as e:
                    log.warning(f"Failed to fetch {side_key} premium at {active_strike}: {e}")

            # Adjustment fills at active strike
            for fill in side_state.get('adjustment_fills', []):
                lots = fill.get('lots', 0)
                prem = fill.get('premium', 0)
                strike = fill.get('strike', active_strike)
                if lots > 0:
                    try:
                        current = fetch_premium_fn(strike, option_type)
                        total_unrealized += (prem - current) * lots * LOT_SIZE_BTC
                    except Exception as e:
                        log.warning(f"Failed to fetch {side_key} adj premium at {strike}: {e}")

            # Frozen positions
            for frozen in side_state.get('frozen_positions', []):
                lots = frozen.get('lots', 0)
                prem = frozen.get('entry_premium', 0)
                strike = frozen.get('strike', 0)
                if lots > 0 and strike > 0:
                    try:
                        current = fetch_premium_fn(strike, option_type)
                        total_unrealized += (prem - current) * lots * LOT_SIZE_BTC
                    except Exception as e:
                        log.warning(f"Failed to fetch {side_key} frozen premium at {strike}: {e}")

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
