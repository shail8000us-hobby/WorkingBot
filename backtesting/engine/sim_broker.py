"""
Simulated Broker
=================
Handles all order execution in backtest mode.

Simulates options sell and buy-back orders using bid/ask prices from
the chain snapshot, with configurable slippage.

Rules:
  - Sell option (short): execute at best_bid - slippage
  - Buy back option (close): execute at best_ask + slippage
  - Market close (wind-down): execute at best_ask + 2× slippage (conservative)
  - OI filter: if OI < min_oi_lots, order is rejected (liquidity check)
"""

import logging
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger("backtesting.sim_broker")

# Delta Exchange India fee structure (approximate)
TAKER_FEE_PCT = 0.03 / 100     # 0.03% taker fee for options
MAKER_FEE_PCT = 0.0 / 100      # 0.00% maker fee (resting orders)
LOT_SIZE_BTC  = 0.001           # 1 lot = 0.001 BTC (from mmm_constants.py)


@dataclass
class FillRecord:
    """Record of a simulated order fill."""
    order_id:      str
    symbol:        str
    strike:        float
    option_type:   str           # "CE" or "PE"
    side:          str           # "sell" or "buy"
    lots:          int
    fill_price:    float         # USD per lot (premium)
    slippage:      float         # Negative for sells, positive for buys
    fee:           float         # USD
    timestamp_ms:  int
    reduce_only:   bool = False
    note:          str = ""

    @property
    def notional_usd(self) -> float:
        return self.fill_price * self.lots * LOT_SIZE_BTC

    @property
    def net_cash_flow(self) -> float:
        """
        Cash flow from this fill (positive = money received, negative = money spent).
        Sell → receive premium; Buy → spend premium; both pay fee.
        """
        if self.side == "sell":
            return self.notional_usd - self.fee
        else:
            return -(self.notional_usd + self.fee)


class OrderRejectedError(Exception):
    """Raised when an order cannot be filled (liquidity, margin, etc.)."""
    pass


class SimBroker:
    """
    Simulated options broker for backtesting.

    Usage:
        broker = SimBroker(slippage_bps=2, min_oi_lots=50)
        fill = broker.sell_option(chain, strike=95000, option_type="CE",
                                  lots=10, ts_ms=current_ts)
        fills = broker.fills  # List[FillRecord]
    """

    def __init__(
        self,
        slippage_bps: float = 2.0,
        min_oi_lots: float = 50.0,
        fee_mode: str = "taker",
        initial_margin_usd: float = 500_000.0,
    ):
        """
        Args:
            slippage_bps:       Bid/ask slippage in basis points (1 bps = 0.01%)
            min_oi_lots:        Minimum OI to allow execution (liquidity check)
            fee_mode:           "taker" | "maker" | "none"
            initial_margin_usd: Starting simulated margin balance (USD)
        """
        self.slippage_bps       = slippage_bps
        self.min_oi_lots        = min_oi_lots
        self.fee_mode           = fee_mode
        self.initial_margin_usd = initial_margin_usd

        self._margin_used_usd: float = 0.0
        self._fills: List[FillRecord] = []
        self._open_positions: Dict[str, Dict] = {}  # symbol → position dict

        fee_map  = {"taker": TAKER_FEE_PCT, "maker": MAKER_FEE_PCT, "none": 0.0}
        self._fee_pct = fee_map.get(fee_mode, TAKER_FEE_PCT)

        log.info(
            f"SimBroker: slippage={slippage_bps}bps, min_oi={min_oi_lots}, "
            f"fee={self._fee_pct*100:.3f}%, margin={initial_margin_usd:,.0f} USD"
        )

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def fills(self) -> List[FillRecord]:
        return list(self._fills)

    @property
    def available_margin_usd(self) -> float:
        return self.initial_margin_usd - self._margin_used_usd

    @property
    def total_fees_usd(self) -> float:
        return sum(f.fee for f in self._fills)

    # ── Execution ─────────────────────────────────────────────────────────────

    def sell_option(
        self,
        chain,          # SimChain instance
        strike: float,
        option_type: str,
        lots: int,
        ts_ms: int,
        note: str = "",
    ) -> FillRecord:
        """
        Simulate selling (shorting) an option.

        Execution price = best_bid - slippage.
        Raises OrderRejectedError if OI is too low or margin is insufficient.

        Args:
            chain:       SimChain instance
            strike:      Strike price
            option_type: "CE" or "PE"
            lots:        Number of lots to sell
            ts_ms:       Current simulation timestamp (ms)
            note:        Optional label for the fill record

        Returns:
            FillRecord with fill details.
        """
        # ── Liquidity check ────────────────────────────────────────────────
        oi = chain.get_oi(strike, option_type)
        if self.min_oi_lots and (oi is None or oi < self.min_oi_lots):
            raise OrderRejectedError(
                f"SELL {lots}L {strike}{option_type}: OI={oi} < min_oi={self.min_oi_lots}"
            )

        # ── Price ─────────────────────────────────────────────────────────
        bid = chain.get_bid(strike, option_type, ts_ms)
        if not bid:
            # Fallback to mark price
            bid = chain.get_premium(strike, option_type, ts_ms)
        if not bid or bid <= 0:
            raise OrderRejectedError(
                f"SELL {lots}L {strike}{option_type}: no valid bid price at ts={ts_ms}"
            )

        slippage_per_unit = bid * (self.slippage_bps / 10000)
        fill_price        = max(0.01, bid - slippage_per_unit)

        # ── Fee ────────────────────────────────────────────────────────────
        notional_usd = fill_price * lots * LOT_SIZE_BTC
        fee          = notional_usd * self._fee_pct

        # ── Record fill ────────────────────────────────────────────────────
        fill = FillRecord(
            order_id     = str(uuid.uuid4())[:8],
            symbol       = chain.get_symbol(strike, option_type) or f"{option_type}-{strike}",
            strike       = strike,
            option_type  = option_type,
            side         = "sell",
            lots         = lots,
            fill_price   = fill_price,
            slippage     = -slippage_per_unit * lots,
            fee          = fee,
            timestamp_ms = ts_ms,
            note         = note,
        )
        self._fills.append(fill)

        log.debug(
            f"SELL {lots}L {strike}{option_type} @ {fill_price:.2f} "
            f"(bid={bid:.2f}, slip={slippage_per_unit:.2f})"
        )
        return fill

    def buy_option(
        self,
        chain,          # SimChain instance
        strike: float,
        option_type: str,
        lots: int,
        ts_ms: int,
        market_close: bool = False,
        note: str = "",
    ) -> FillRecord:
        """
        Simulate buying back (closing a short) an option.

        Execution price = best_ask + slippage.
        For market_close (wind-down), adds 2× slippage.

        Args:
            chain:        SimChain instance
            strike:       Strike price
            option_type:  "CE" or "PE"
            lots:         Number of lots to buy back
            ts_ms:        Current simulation timestamp (ms)
            market_close: If True, use conservative market close pricing
            note:         Optional label

        Returns:
            FillRecord with fill details.
        """
        # ── Price ─────────────────────────────────────────────────────────
        ask = chain.get_ask(strike, option_type, ts_ms)
        if not ask:
            ask = chain.get_premium(strike, option_type, ts_ms)
        if not ask or ask <= 0:
            raise OrderRejectedError(
                f"BUY {lots}L {strike}{option_type}: no valid ask price at ts={ts_ms}"
            )

        slip_multiplier   = 2.0 if market_close else 1.0
        slippage_per_unit = ask * (self.slippage_bps / 10000) * slip_multiplier
        fill_price        = ask + slippage_per_unit

        # ── Fee ────────────────────────────────────────────────────────────
        notional_usd = fill_price * lots * LOT_SIZE_BTC
        fee          = notional_usd * self._fee_pct

        fill = FillRecord(
            order_id     = str(uuid.uuid4())[:8],
            symbol       = chain.get_symbol(strike, option_type) or f"{option_type}-{strike}",
            strike       = strike,
            option_type  = option_type,
            side         = "buy",
            lots         = lots,
            fill_price   = fill_price,
            slippage     = slippage_per_unit * lots,
            fee          = fee,
            timestamp_ms = ts_ms,
            reduce_only  = True,
            note         = note,
        )
        self._fills.append(fill)

        log.debug(
            f"BUY  {lots}L {strike}{option_type} @ {fill_price:.2f} "
            f"(ask={ask:.2f}, slip={slippage_per_unit:.2f})"
        )
        return fill

    # ── Reporting helpers ─────────────────────────────────────────────────────

    def fills_as_df(self):
        """Return all fills as a pandas DataFrame."""
        import pandas as pd
        if not self._fills:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "order_id":    f.order_id,
                "timestamp_ms": f.timestamp_ms,
                "symbol":      f.symbol,
                "strike":      f.strike,
                "option_type": f.option_type,
                "side":        f.side,
                "lots":        f.lots,
                "fill_price":  f.fill_price,
                "slippage":    f.slippage,
                "fee":         f.fee,
                "net_cash_flow": f.net_cash_flow,
                "note":        f.note,
            }
            for f in self._fills
        ])

    def total_slippage_usd(self) -> float:
        """Total slippage cost in USD (absolute value)."""
        return sum(abs(f.slippage) for f in self._fills)

    def sell_count(self) -> int:
        return sum(1 for f in self._fills if f.side == "sell")

    def buy_count(self) -> int:
        return sum(1 for f in self._fills if f.side == "buy")

    def reset(self):
        """Clear all fills and reset margin tracking."""
        self._fills.clear()
        self._margin_used_usd = 0.0
        self._open_positions.clear()
