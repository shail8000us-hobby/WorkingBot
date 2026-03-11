"""
MMM Strategy Adapter
=====================
Main entry point for running MMM backtests.

Implements BaseAlgoAdapter. The session_runner calls:
  1. setup()         — initialize MMM session, find entry strikes, place initial shorts
  2. on_heartbeat()  — execute one MMM beat via MMMHeartbeatBridge
  3. is_done()       — check STOPPED / COMPLETE / expiry
  4. get_session_result() — return complete session result dict
"""

import logging
import time
from typing import Dict, Any, Optional, List

from backtesting.engine.base_algo_adapter import BaseAlgoAdapter
from backtesting.engine.sim_broker import OrderRejectedError
from .mmm_state_factory import create_fresh_session, create_import_session
from .mmm_mock_client import MMMockClient
from .mmm_heartbeat_bridge import MMMHeartbeatBridge

log = logging.getLogger("backtesting.mmm_adapter")


class MMMAdapter(BaseAlgoAdapter):
    """
    MMM strategy adapter — plugs MMM into the backtesting session runner.

    Supports three session modes (matching production):
      - "fresh":  Scan chain for entry strikes matching desired CE/PE premiums
      - "import": Start from user-specified strikes and entry premiums
      - "adopt":  (future) Map existing exchange positions
    """

    def __init__(self, mode: str = "fresh"):
        """
        Args:
            mode: "fresh" | "import"
        """
        self.mode   = mode
        self._chain  = None
        self._broker = None
        self._margin = None
        self._session: Optional[Dict] = None
        self._client: Optional[MMMockClient] = None
        self._bridge: Optional[MMMHeartbeatBridge] = None

        # Track simulation timestamps
        self._ts_ref: List[int] = [0]    # mutable reference for mock client
        self._entry_ts_ms: int = 0
        self._last_ts_ms:  int = 0
        self._start_wall:  float = 0.0

        # Beat history for analytics
        self._beats: List[Dict] = []
        self._peak_pnl: float = 0.0
        self._max_drawdown: float = 0.0

    def get_algo_name(self) -> str:
        return f"MMM ({self.mode})"

    # ── BaseAlgoAdapter interface ──────────────────────────────────────────────

    def setup(self, params, sim_chain, sim_broker, sim_margin, entry_ts_ms: int):
        """Initialize MMM session and place entry shorts."""
        self._chain  = sim_chain
        self._broker = sim_broker
        self._margin = sim_margin
        self._ts_ref[0] = entry_ts_ms
        self._entry_ts_ms = entry_ts_ms
        self._start_wall  = time.monotonic()

        expiry_date = params.get("expiry_date", "")

        # ── Create session state ────────────────────────────────────────────
        if self.mode == "import":
            self._session = create_import_session(
                ce_strike        = params["ce_strike"],
                ce_lots          = params["initial_lots"],
                ce_entry_premium = params["ce_entry_premium"],
                pe_strike        = params["pe_strike"],
                pe_lots          = params["initial_lots"],
                pe_entry_premium = params["pe_entry_premium"],
                params           = params,
                expiry_date      = expiry_date,
            )
        else:
            # Fresh mode — scan chain for entry strikes
            self._session = create_fresh_session(params, expiry_date=expiry_date)

        # ── Create mock client ──────────────────────────────────────────────
        self._client = MMMockClient(sim_chain, sim_broker, sim_margin, self._ts_ref)

        # ── For fresh mode: find and sell entry strikes ──────────────────────
        if self.mode == "fresh":
            self._run_entry(params, entry_ts_ms)

        # ── Create heartbeat bridge ─────────────────────────────────────────
        self._bridge = MMMHeartbeatBridge(self._client, self._session)
        self._session["strategy_status"] = "RUNNING"

        log.info(
            f"MMM setup complete: {expiry_date}, "
            f"CE@{self._session['ce']['active_strike']}, "
            f"PE@{self._session['pe']['active_strike']}"
        )

    def _run_entry(self, params: Dict, ts_ms: int):
        """Scan chain for entry strikes and place initial shorts."""
        desired_ce = params.get("desired_ce_premium", 150.0)
        desired_pe = params.get("desired_pe_premium", 150.0)
        initial_lots = params.get("initial_lots", 10)

        # Find CE strike
        ce_candidates = self._client.scan_chain_for_premium("CE", desired_ce)
        pe_candidates = self._client.scan_chain_for_premium("PE", desired_pe)

        if not ce_candidates or not pe_candidates:
            log.error("No valid entry strikes found on chain")
            self._session["strategy_status"] = "STOPPED"
            return

        ce_strike, ce_premium = ce_candidates[0]
        pe_strike, pe_premium = pe_candidates[0]

        log.info(
            f"Entry: CE {ce_strike} p={ce_premium:.1f}, "
            f"PE {pe_strike} p={pe_premium:.1f}, {initial_lots}L each"
        )

        # Place initial shorts
        try:
            ce_fill = self._broker.sell_option(
                self._chain, ce_strike, "CE", initial_lots, ts_ms, note="entry_CE"
            )
            pe_fill = self._broker.sell_option(
                self._chain, pe_strike, "PE", initial_lots, ts_ms, note="entry_PE"
            )
        except OrderRejectedError as e:
            log.error(f"Entry order rejected: {e}")
            self._session["strategy_status"] = "STOPPED"
            return

        # Update session state
        ses = self._session
        ses["ce"]["original_lots"]     = initial_lots
        ses["ce"]["original_premium"]  = ce_fill.fill_price
        ses["ce"]["original_strike"]   = ce_strike
        ses["ce"]["active_strike"]     = ce_strike
        ses["ce"]["active_lots"]       = initial_lots
        ses["ce"]["total_lots"]        = initial_lots
        ses["ce"]["trigger_snapshot"]  = {str(int(ce_strike)): ce_fill.fill_price}
        ses["pe"]["original_lots"]     = initial_lots
        ses["pe"]["original_premium"]  = pe_fill.fill_price
        ses["pe"]["original_strike"]   = pe_strike
        ses["pe"]["active_strike"]     = pe_strike
        ses["pe"]["active_lots"]       = initial_lots
        ses["pe"]["total_lots"]        = initial_lots
        ses["pe"]["trigger_snapshot"]  = {str(int(pe_strike)): pe_fill.fill_price}
        ses["total_premium_collected"] = (
            ce_fill.fill_price * initial_lots + pe_fill.fill_price * initial_lots
        ) * 0.001   # × LOT_SIZE_BTC

    def on_heartbeat(self, ts_ms: int, chain) -> None:
        """Execute one MMM heartbeat at ts_ms."""
        self._ts_ref[0] = ts_ms
        self._last_ts_ms = ts_ms

        if not self._bridge:
            return

        beat = self._bridge.run_beat(ts_ms)
        self._beats.append(beat)

        # Update P&L tracking
        self._update_pnl(ts_ms, beat)

    def _update_pnl(self, ts_ms: int, beat: Dict):
        """Compute current unrealized P&L and track peak / drawdown."""
        ses = self._session
        total_fills = self._broker.fills

        # Compute P&L from fills
        realized = sum(f.net_cash_flow for f in total_fills)
        # Unrealized: mark current positions at close price
        unrealized = self._compute_unrealized_pnl(ts_ms)

        total_pnl = realized + unrealized
        ses["realized_pnl"]   = realized
        ses["unrealized_pnl"] = unrealized

        # Peak / drawdown tracking
        if total_pnl > self._peak_pnl:
            self._peak_pnl = total_pnl
        drawdown = self._peak_pnl - total_pnl
        if drawdown > self._max_drawdown:
            self._max_drawdown = drawdown

    def _compute_unrealized_pnl(self, ts_ms: int) -> float:
        """Compute mark-to-market P&L for all open short positions."""
        if not self._session or not self._chain:
            return 0.0

        pnl = 0.0
        for side_key in ("ce", "pe"):
            side = self._session.get(side_key, {})
            opt_type = "CE" if side_key == "ce" else "PE"

            def pnl_for_position(strike, entry_premium, lots):
                mark = self._chain.get_premium(strike, opt_type, ts_ms)
                if mark is None:
                    return 0.0
                return (entry_premium - mark) * lots * 0.001   # × LOT_SIZE_BTC

            # Original position
            orig_strike  = side.get("original_strike")
            orig_premium = side.get("original_premium")
            orig_lots    = side.get("original_lots", 0)
            if orig_strike and orig_premium and orig_lots:
                pnl += pnl_for_position(orig_strike, orig_premium, orig_lots)

            # Adjustment fills
            for fill in side.get("adjustment_fills", []):
                pnl += pnl_for_position(fill["strike"], fill["premium"], fill["lots"])

            # Frozen positions
            for fp in side.get("frozen_positions", []):
                pnl += pnl_for_position(fp["strike"], fp["entry_premium"], fp["lots"])

        return pnl

    def is_done(self) -> bool:
        """Return True when the session should end."""
        if not self._session:
            return False
        status = self._session.get("strategy_status", "IDLE")
        return status in ("STOPPED", "COMPLETE", "ERROR")

    def get_heartbeat_interval_sec(self) -> int:
        """Return current adaptive interval from heartbeat bridge."""
        if self._bridge:
            return self._bridge.get_adaptive_interval()
        return 300  # Default 5 minutes

    def on_session_end(self):
        """Mark session as complete if RUNNING (reached expiry naturally)."""
        if self._session and self._session.get("strategy_status") == "RUNNING":
            self._session["strategy_status"] = "COMPLETE"
            log.info(f"Session ended at expiry: {self._session.get('expiry_date')}")

    def get_session_result(self) -> Dict[str, Any]:
        """Return the comprehensive session result dict."""
        ses = self._session or {}
        params = ses.get("params", {})

        realized    = ses.get("realized_pnl", 0.0)
        unrealized  = ses.get("unrealized_pnl", 0.0)
        total_pnl   = realized + unrealized
        total_fees  = self._broker.total_fees_usd if self._broker else 0.0
        net_pnl     = total_pnl - total_fees

        return {
            # Identification
            "session_id":        ses.get("session_id", ""),
            "expiry_date":       ses.get("expiry_date", ""),
            "algo":              "MMM",
            "mode":              self.mode,
            "strategy_status":   ses.get("strategy_status", "UNKNOWN"),
            "params":            params,
            # P&L
            "realized_pnl":      realized,
            "unrealized_pnl":    unrealized,
            "total_pnl":         total_pnl,
            "total_fees":        total_fees,
            "net_pnl":           net_pnl,
            # Stats
            "adjustment_count":  ses.get("adjustment_count", 0),
            "reversal_count":    ses.get("reversal_count", 0),
            "shift_count":       ses.get("shift_count", 0),
            "close_at_5_count":  ses.get("close_at_5_count", 0),
            "harvest_count":     ses.get("harvest_count", 0),
            "recycle_count":     ses.get("recycle_count", 0),
            # Risk
            "peak_pnl":          self._peak_pnl,
            "max_drawdown":      self._max_drawdown,
            # Session metadata
            "start_ts_ms":       self._entry_ts_ms,
            "end_ts_ms":         self._last_ts_ms,
            "total_beats":       len(self._beats),
            "wall_clock_sec":    round(time.monotonic() - self._start_wall, 2) if self._start_wall else 0,
            # Positions at end
            "ce": ses.get("ce", {}),
            "pe": ses.get("pe", {}),
            "adjustment_history": ses.get("adjustment_history", []),
        }
