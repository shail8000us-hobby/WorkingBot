"""
MMM Mock Client
================
Replaces the production delta REST client in backtest mode.

All calls that production MMM code makes to Delta Exchange India are
intercepted here and routed to the SimChain / SimBroker.

The production code (mmm_engine.py, mmm_trigger.py, etc.) calls these
functions via the "rest_client" or "options_client" dependency that
mmm_heartbeat_bridge.py injects.

Key replacements:
  get_option_mark_price(symbol)     → SimChain.get_premium(strike, side, ts)
  get_option_chain(expiry)          → SimChain.get_chain_at(ts)
  get_margin()                      → MarginState.to_dict()
  get_spot_price()                  → SimChain.get_spot_at(ts)
  place_order(...)                  → SimBroker.sell/buy_option(...)
"""

import logging
from typing import Optional, Any, Dict

log = logging.getLogger("backtesting.mmm_mock_client")


class MMMockClient:
    """
    Drop-in replacement for the Delta Exchange REST client used by MMM modules.

    Usage by heartbeat_bridge:
        client = MMMockClient(sim_chain, sim_broker, sim_margin, ts_ms)
        # Inject into mmm_monitor's rest_client slot
    """

    def __init__(self, sim_chain, sim_broker, sim_margin, ts_ms_ref: list):
        """
        Args:
            sim_chain:   SimChain instance
            sim_broker:  SimBroker instance
            sim_margin:  MarginState instance
            ts_ms_ref:   Mutable list [current_ts_ms] — heartbeat bridge updates this each tick
        """
        self._chain   = sim_chain
        self._broker  = sim_broker
        self._margin  = sim_margin
        self._ts_ref  = ts_ms_ref   # [ts_ms] — updated by bridge
        self._fills   = []          # Track fills placed via this client

    @property
    def _ts_ms(self) -> int:
        return self._ts_ref[0]

    # ── Option price queries ───────────────────────────────────────────────────

    def get_option_mark_price(self, symbol: str, strike: float = None, option_type: str = None) -> Optional[float]:
        """
        Get the mark price (close price from candle) for a strike.

        MMM calls this to get current premium for:
          - Trigger evaluation (CE_now, PE_now)
          - P&L calculation
          - Close-at-5 scan
        """
        if strike is None or option_type is None:
            # Try to parse strike and option_type from symbol
            strike, option_type = _parse_symbol(symbol)

        price = self._chain.get_premium(float(strike), option_type, self._ts_ms)
        if price is None:
            log.warning(f"No mark price for {symbol} at ts={self._ts_ms}")
        return price

    def get_option_bid(self, symbol: str, strike: float = None, option_type: str = None) -> Optional[float]:
        """Get best bid for execution."""
        if strike is None or option_type is None:
            strike, option_type = _parse_symbol(symbol)
        return self._chain.get_bid(float(strike), option_type, self._ts_ms)

    def get_option_ask(self, symbol: str, strike: float = None, option_type: str = None) -> Optional[float]:
        """Get best ask for execution."""
        if strike is None or option_type is None:
            strike, option_type = _parse_symbol(symbol)
        return self._chain.get_ask(float(strike), option_type, self._ts_ms)

    # ── Chain queries ──────────────────────────────────────────────────────────

    def get_option_chain(self, expiry_date: str, underlying: str = "BTC") -> list:
        """
        Get the full options chain at the current simulation timestamp.

        Returns a list of option dicts compatible with how mmm_initializer uses chain data.
        """
        chain_dict = self._chain.get_chain_at(self._ts_ms)
        # Convert to list format expected by mmm_initializer
        result = []
        for (strike, opt_type), data in chain_dict.items():
            result.append({
                "strike_price":  strike,
                "contract_type": "call_options" if opt_type == "CE" else "put_options",
                "symbol":        data.get("symbol", ""),
                "mark_price":    data.get("close"),
                "best_bid":      data.get("best_bid"),
                "best_ask":      data.get("best_ask"),
                "oi":            data.get("oi", 0),
                "greeks": {
                    "delta": data.get("delta"),
                    "gamma": data.get("gamma"),
                    "theta": data.get("theta"),
                    "vega":  data.get("vega"),
                },
                "quotes": {
                    "ask_iv": data.get("iv"),
                },
            })
        return result

    def scan_chain_for_premium(
        self,
        side: str,
        target_premium: float,
        min_oi: float = 50,
    ) -> list:
        """
        Find strikes with premium closest to target_premium.

        Returns sorted list of (strike, premium) tuples.
        """
        return self._chain.scan_chain(
            option_type=side,
            target_premium=target_premium,
            ts_ms=self._ts_ms,
            min_oi=min_oi,
        )

    # ── Margin queries ─────────────────────────────────────────────────────────

    def get_margin(self) -> dict:
        """Return simulated margin state dict (compatible with production margin format)."""
        state = self._margin.to_dict()
        # Map to the format production code expects
        return {
            "result": {
                "available_balance":   state["available_margin_usd"],
                "position_margin":     state["position_margin_usd"],
                "order_margin":        state["order_margin_usd"],
                "balance":             state["net_equity_usd"],
                "unrealized_pnl":      state["unrealized_pnl"],
                "net_equity":          state["net_equity_usd"],
            }
        }

    def get_portfolio_margin_utilization(self) -> float:
        """Return margin utilization percentage (0–100)."""
        return self._margin.utilization_pct

    # ── Spot price ─────────────────────────────────────────────────────────────

    def get_spot_price(self, underlying: str = "BTC") -> Optional[float]:
        """Get BTC/ETH spot price at the current simulation timestamp."""
        return self._chain.get_spot_at(self._ts_ms)

    # ── Order execution (routed to SimBroker) ──────────────────────────────────

    def place_order(
        self,
        symbol: str,
        side: str,         # "sell" or "buy"
        lots: int,
        strike: float = None,
        option_type: str = None,
        reduce_only: bool = False,
        note: str = "",
    ) -> dict:
        """
        Place an order via the simulated broker.

        Returns a dict mimicking the production Delta Exchange order response.
        """
        if strike is None or option_type is None:
            strike, option_type = _parse_symbol(symbol)

        try:
            if side == "sell":
                fill = self._broker.sell_option(
                    self._chain, float(strike), option_type, lots, self._ts_ms, note=note
                )
            else:
                fill = self._broker.buy_option(
                    self._chain, float(strike), option_type, lots, self._ts_ms,
                    market_close=reduce_only, note=note
                )
        except Exception as e:
            log.warning(f"Order rejected: {symbol} {side} {lots}L: {e}")
            return {"success": False, "error": str(e)}

        self._fills.append(fill)
        log.debug(f"Order filled: {side} {lots}L {symbol} @ {fill.fill_price:.2f}")

        return {
            "success":    True,
            "order_id":   fill.order_id,
            "fill_price": fill.fill_price,
            "lots":       fill.lots,
            "side":       fill.side,
            "fee":        fill.fee,
        }

    # ── No-ops for production calls we don't need in backtest ─────────────────

    def cancel_order(self, order_id: str) -> dict:
        return {"success": True}

    def get_open_orders(self) -> list:
        return []

    def get_positions(self) -> list:
        return []

    def send_telegram(self, message: str) -> None:
        log.debug(f"[Telegram suppressed] {message}")

    def emit_socket(self, event: str, data: dict) -> None:
        log.debug(f"[WebSocket suppressed] {event}")


# ── Helper ──────────────────────────────────────────────────────────────────────

def _parse_symbol(symbol: str):
    """
    Attempt to extract strike and option_type from a Delta Exchange symbol.

    Format: "C-BTC-95000-260310" or "P-BTC-95000-260310"
    Returns: (strike_float, "CE" or "PE")
    """
    try:
        parts = symbol.split("-")
        side_map = {"C": "CE", "P": "PE"}
        opt_type = side_map.get(parts[0].upper(), "CE")
        strike   = float(parts[2])
        return strike, opt_type
    except Exception:
        log.warning(f"Could not parse symbol: {symbol}")
        return 0.0, "CE"
