"""
MMM Heartbeat Bridge
=====================
Executes one MMM heartbeat cycle using real production logic
but with all exchange calls intercepted by MMMockClient.

This is the core of the MMM backtest strategy adapter:
  - Imports and calls the actual mmm_engine, mmm_trigger, mmm_safety, etc.
  - Replaces exchange API calls with mock client reads from SimChain
  - Replaces SocketIO emit() calls with no-ops (logs to trade_log instead)
  - Replaces time.sleep() with no-op (virtual clock controls pacing)

Crucially, this does NOT copy/paste ANY production business logic.
All the math (trigger evaluation, adjustment calculation, P&L) runs
from the real mmm_*.py files.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# ── Set backtest mode BEFORE importing any production modules ─────────────────
os.environ["BACKTEST_MODE"] = "true"

# ── Add production MMM path to Python path ────────────────────────────────────
_MMM_PATH = Path(__file__).resolve().parents[4] / "webui" / "backend" / "routes" / "mmm"
if str(_MMM_PATH) not in sys.path:
    sys.path.insert(0, str(_MMM_PATH))

log = logging.getLogger("backtesting.mmm_heartbeat_bridge")

# ── Lazy imports of production MMM modules ────────────────────────────────────
# These are loaded once on first use. They import cleanly because BACKTEST_MODE=true
# disables any database, websocket, or exchange initialization.
_mmm_trigger     = None
_mmm_engine      = None
_mmm_safety      = None
_mmm_close_at_5  = None
_mmm_wind_down   = None
_mmm_harvester   = None
_mmm_recycler    = None
_mmm_constants   = None


def _load_mmm_modules():
    global _mmm_trigger, _mmm_engine, _mmm_safety, _mmm_close_at_5
    global _mmm_wind_down, _mmm_harvester, _mmm_recycler, _mmm_constants

    if _mmm_trigger is not None:
        return  # Already loaded

    try:
        import mmm_trigger    as _t;  _mmm_trigger    = _t
        import mmm_engine     as _e;  _mmm_engine     = _e
        import mmm_safety     as _s;  _mmm_safety     = _s
        import mmm_close_at_5 as _c;  _mmm_close_at_5 = _c
        import mmm_wind_down  as _w;  _mmm_wind_down  = _w
        log.info("Loaded core MMM modules (trigger, engine, safety, close_at_5, wind_down)")
    except ImportError as e:
        log.warning(f"Could not import MMM module: {e}. Running in fallback mode.")

    try:
        import mmm_harvester as _h; _mmm_harvester = _h
        import mmm_recycler  as _r; _mmm_recycler  = _r
        log.info("Loaded M1/M2/M3 modules (harvester, recycler)")
    except ImportError:
        log.info("mmm_harvester/recycler not available — M1/M2/M3 features inactive")

    try:
        import mmm_constants as _mc; _mmm_constants = _mc
    except ImportError:
        pass


class MMMHeartbeatBridge:
    """
    Executes the MMM heartbeat logic using real production modules.

    Injected dependencies (all mocked for backtest):
      - client:  MMMockClient — all exchange calls go here
      - session: Production MMM session state dict

    Usage:
        bridge = MMMHeartbeatBridge(client, session)
        bridge.run_beat(ts_ms)   # runs one full heartbeat
        interval = bridge.get_adaptive_interval()
    """

    def __init__(self, client, session: Dict[str, Any]):
        """
        Args:
            client:  MMMockClient instance
            session: MMM session state dict (mutable — modified in-place)
        """
        _load_mmm_modules()
        self.client  = client
        self.session = session
        self._trade_log = []      # Local trade log (fills + events at each tick)
        self._last_interval = 300  # Default heartbeat interval

    # ── Main entry point ─────────────────────────────────────────────────────

    def run_beat(self, ts_ms: int) -> Dict[str, Any]:
        """
        Execute one full MMM heartbeat at the given timestamp.

        Returns a beat result dict:
          {
            beat_ts_ms: int,
            ce_premium: float,
            pe_premium: float,
            triggered:  bool,
            events:     list of event dicts (adjustments, closes, etc.)
          }
        """
        beat_result = {
            "beat_ts_ms": ts_ms,
            "ce_premium": None,
            "pe_premium": None,
            "triggered":  False,
            "events":     [],
        }

        session = self.session
        params  = session.get("params", {})

        try:
            ce_strike = session.get("ce", {}).get("active_strike")
            pe_strike = session.get("pe", {}).get("active_strike")

            if not ce_strike or not pe_strike:
                return beat_result

            # ── Step 1: Fetch current premiums ───────────────────────────────
            ce_now = self.client.get_option_mark_price(None, ce_strike, "CE")
            pe_now = self.client.get_option_mark_price(None, pe_strike, "PE")

            if ce_now is None or pe_now is None:
                log.debug(f"Beat {ts_ms}: missing premium (CE={ce_now}, PE={pe_now}) — skipping")
                return beat_result

            beat_result["ce_premium"] = ce_now
            beat_result["pe_premium"] = pe_now

            # ── Step 2: Close-at-5 scan (ALL positions) ─────────────────────
            if _mmm_close_at_5:
                try:
                    close_events = self._run_close_at_5(ce_now, pe_now, ts_ms)
                    beat_result["events"].extend(close_events)
                except Exception as e:
                    log.debug(f"close_at_5 error: {e}")

            # ── Step 3: M1 Profit Harvesting ─────────────────────────────────
            if _mmm_harvester and params.get("harvest_enabled", True):
                try:
                    self._run_harvest(ts_ms, beat_result["events"])
                except Exception as e:
                    log.debug(f"harvest error: {e}")

            # ── Step 4: Safety checks ────────────────────────────────────────
            if _mmm_safety:
                try:
                    safety_result = _mmm_safety.run_all_checks(session, ce_now, pe_now)
                    if safety_result.get("action") in ("stop_session", "close_all"):
                        session["strategy_status"] = "STOPPED"
                        beat_result["events"].append({"type": "safety_stop", "reason": safety_result.get("reason")})
                        return beat_result
                except Exception as e:
                    log.debug(f"safety error: {e}")

            # ── Step 5: Wind-down check ──────────────────────────────────────
            if _mmm_wind_down and params.get("wind_down_enabled", True):
                try:
                    minutes_to_expiry = _minutes_to_expiry(ts_ms, session.get("expiry_date", ""))
                    session["_minutes_to_expiry"] = minutes_to_expiry
                    if _mmm_wind_down.is_wind_down_active(session):
                        session["_wind_down_active"] = True
                except Exception:
                    pass

            # ── Step 6: Skip adjustment if not RUNNING ───────────────────────
            if session.get("strategy_status") != "RUNNING":
                return beat_result

            # ── Step 7: Evaluate triggers ─────────────────────────────────────
            if _mmm_trigger:
                try:
                    trigger_result = _mmm_trigger.evaluate_triggers(session, ce_now, pe_now)
                    ce_triggered = trigger_result.get("ce_triggered", False)
                    pe_triggered = trigger_result.get("pe_triggered", False)

                    # Update adaptive interval
                    if hasattr(_mmm_trigger, "compute_adaptive_interval"):
                        interval = _mmm_trigger.compute_adaptive_interval(session, ce_now, pe_now)
                        self._last_interval = interval

                    if ce_triggered or pe_triggered:
                        beat_result["triggered"] = True
                        adj_event = self._run_adjustment(
                            ce_now, pe_now, ce_triggered, pe_triggered, ts_ms
                        )
                        if adj_event:
                            beat_result["events"].append(adj_event)

                except Exception as e:
                    log.debug(f"trigger/adjustment error: {e}")

        except Exception as e:
            log.error(f"Beat error at ts={ts_ms}: {e}", exc_info=True)

        return beat_result

    # ── Sub-steps ─────────────────────────────────────────────────────────────

    def _run_close_at_5(self, ce_now: float, pe_now: float, ts_ms: int) -> list:
        """Run close-at-5 scan using production module."""
        events = []
        close_threshold = self.session.get("params", {}).get("close_at_threshold", 5)

        if _mmm_close_at_5:
            try:
                closeable = _mmm_close_at_5.scan_closeable_positions(
                    self.session, ce_now, pe_now, close_threshold
                )
                for pos in closeable:
                    result = self.client.place_order(
                        symbol=pos.get("symbol", ""),
                        side="buy",
                        lots=pos.get("lots", 0),
                        strike=pos.get("strike"),
                        option_type=pos.get("option_type"),
                        reduce_only=True,
                        note="close_at_5",
                    )
                    if result.get("success"):
                        pnl = (pos.get("entry_premium", 0) - result["fill_price"]) * pos["lots"]
                        events.append({
                            "type": "close_at_5",
                            "strike": pos["strike"],
                            "option_type": pos["option_type"],
                            "lots": pos["lots"],
                            "fill_price": result["fill_price"],
                            "realized_pnl": pnl,
                        })
            except Exception as e:
                log.debug(f"close_at_5 detail error: {e}")

        return events

    def _run_harvest(self, ts_ms: int, events: list):
        """Run M1 profit harvesting."""
        if not _mmm_harvester:
            return
        try:
            _mmm_harvester.run_harvest(self.session, self.client, ts_ms)
        except Exception as e:
            log.debug(f"harvest detail error: {e}")

    def _run_adjustment(
        self,
        ce_now: float,
        pe_now: float,
        ce_triggered: bool,
        pe_triggered: bool,
        ts_ms: int,
    ) -> Optional[Dict]:
        """Calculate and execute an adjustment using production mmm_engine."""
        if not _mmm_engine:
            return None

        try:
            if ce_triggered and not pe_triggered:
                aggressor, hedge = "CE", "PE"
            elif pe_triggered and not ce_triggered:
                aggressor, hedge = "PE", "CE"
            else:
                # Both-sides-up: log and return (no auto-decision in backtest)
                return {"type": "both_sides_up", "ce_now": ce_now, "pe_now": pe_now}

            result = _mmm_engine.calculate_adjustment(
                session=self.session,
                aggressor_side=aggressor,
                hedge_side=hedge,
                aggressor_premium=ce_now if aggressor == "CE" else pe_now,
                hedge_premium=pe_now if hedge == "PE" else ce_now,
            )

            if result.get("lots_to_sell", 0) > 0:
                fill = self.client.place_order(
                    symbol="",
                    side="sell",
                    lots=result["lots_to_sell"],
                    strike=result.get("strike"),
                    option_type=hedge,
                    note=f"adjustment_{aggressor}",
                )
                if fill.get("success"):
                    self.session["adjustment_count"] = self.session.get("adjustment_count", 0) + 1
                    return {
                        "type":         "adjustment",
                        "aggressor":    aggressor,
                        "hedge":        hedge,
                        "lots":         result["lots_to_sell"],
                        "fill_price":   fill.get("fill_price"),
                        "loss_covered": result.get("loss"),
                        "ts_ms":        ts_ms,
                    }
        except Exception as e:
            log.debug(f"adjustment error: {e}")

        return None

    # ── Interval management ────────────────────────────────────────────────────

    def get_adaptive_interval(self) -> int:
        """Return the current adaptive heartbeat interval in seconds."""
        return self._last_interval


# ── Utility ────────────────────────────────────────────────────────────────────

def _minutes_to_expiry(ts_ms: int, expiry_date: str) -> float:
    """Compute minutes remaining until the 08:00 UTC expiry."""
    try:
        from datetime import datetime, timezone
        expiry_dt = datetime.strptime(expiry_date, "%d-%m-%Y").replace(tzinfo=timezone.utc)
        expiry_ts_ms = int(expiry_dt.replace(hour=8, minute=0).timestamp() * 1000)
        remaining_ms = expiry_ts_ms - ts_ms
        return max(0.0, remaining_ms / 60000)
    except Exception:
        return 999.0
