"""
Options AI Engine — Orchestration Engine

Ties together all sub-modules:
  position_analyzer → market_context → ai_advisor → action_executor → memory_store

Provides:
  - analyze() — one-shot full analysis cycle
  - start_background_loop() — auto-refresh thread
  - get_engine() — singleton accessor
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional

from .config_ai import AI_ENGINE_CONFIG
from . import position_analyzer, market_context, ai_advisor, action_executor, memory_store

log = logging.getLogger(__name__)


class OptionsAIEngine:
    """
    Orchestrates the full Options AI analysis pipeline.
    Singleton — use get_engine() instead of instantiating directly.
    """

    def __init__(self):
        self._last_result: Optional[Dict] = None
        self._last_run_time: Optional[str] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ─── Core Analysis ───────────────────────────────────────────────────────

    def analyze(self, risk_pref: str = "moderate") -> Dict[str, Any]:
        """
        Run one full AI analysis cycle.

        Steps:
          1. Fetch and analyse open options positions.
          2. Get current market context.
          3. Load recent memory (last N decisions).
          4. Build prompt and call AI advisor.
          5. Process suggestions (dry-run unless automation_mode=True).
          6. Save decision to memory store.

        Returns:
            Full analysis result dict including AI response and execution results.
        """
        started_at = datetime.now().isoformat()
        log.info("[engine] Starting AI analysis cycle...")

        # Step 1: Positions
        try:
            pos_data = position_analyzer.analyze_positions()
            log.info(f"[engine] {pos_data['position_count']} positions analysed, "
                     f"{pos_data['flagged_count']} flagged")
        except Exception as e:
            log.error(f"[engine] position_analyzer failed: {e}")
            pos_data = {"positions": [], "portfolio_greeks": {}, "total_pnl": 0,
                        "position_count": 0, "flagged_count": 0}

        # Step 2: Market context
        try:
            mkt_ctx = market_context.get_market_context()
        except Exception as e:
            log.error(f"[engine] market_context failed: {e}")
            mkt_ctx = market_context._fallback_context()

        # Step 3: Memory
        recent = memory_store.load_recent()

        # Step 4: AI call
        ai_response = ai_advisor.call_ai(pos_data, mkt_ctx, recent, risk_pref)

        # Step 5: Execute / dry-run
        exec_result = action_executor.process_suggestions(
            ai_response, pos_data.get("positions", [])
        )

        # Step 6: Save to memory
        action_taken = "executed" if exec_result.get("executed_count", 0) > 0 else "suggested"
        automated = exec_result.get("mode") == "automation" and exec_result.get("executed_count", 0) > 0
        decision_id = memory_store.save_decision(
            pos_data.get("positions", []),
            ai_response,
            action_taken=action_taken,
            automated=automated,
        )

        result = {
            "decision_id": decision_id,
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(),
            "position_summary": {
                "count": pos_data["position_count"],
                "flagged": pos_data["flagged_count"],
                "total_pnl": pos_data["total_pnl"],
            },
            "market_context": mkt_ctx,
            "ai_response": ai_response,
            "execution": exec_result,
            "automation_mode": AI_ENGINE_CONFIG["automation_mode"],
        }

        with self._lock:
            self._last_result = result
            self._last_run_time = result["completed_at"]

        log.info(f"[engine] Analysis complete. Risk={ai_response.get('risk_level')} "
                 f"Confidence={ai_response.get('confidence', 0):.2f} "
                 f"DecisionID={decision_id}")
        return result

    # ─── Status ──────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Return current engine status (lightweight — no API calls)."""
        with self._lock:
            last = self._last_result
        return {
            "running": self._running,
            "automation_mode": AI_ENGINE_CONFIG["automation_mode"],
            "analysis_interval_minutes": AI_ENGINE_CONFIG["analysis_interval_minutes"],
            "last_run_time": self._last_run_time,
            "last_risk_level": (last or {}).get("ai_response", {}).get("risk_level", "unknown"),
            "last_confidence": (last or {}).get("ai_response", {}).get("confidence", 0.0),
            "last_position_count": (last or {}).get("position_summary", {}).get("count", 0),
            "ai_configured": ai_advisor.is_ai_configured(),
            "ai_provider": AI_ENGINE_CONFIG["ai_provider"],
        }

    def get_last_result(self) -> Optional[Dict]:
        """Return the last full analysis result."""
        with self._lock:
            return self._last_result

    # ─── Automation Toggle ────────────────────────────────────────────────────

    def toggle_automation(self, enabled: bool) -> Dict[str, Any]:
        """
        Enable or disable automation mode at runtime.
        Note: Also updates the in-memory config flag.
        The change is NOT persisted to disk — restart resets to config default.
        """
        AI_ENGINE_CONFIG["automation_mode"] = enabled
        log.info(f"[engine] Automation mode {'ENABLED ⚡' if enabled else 'DISABLED 🔒'}")
        return {
            "automation_mode": enabled,
            "message": (
                "⚡ Automation mode ENABLED — AI will auto-execute critical urgent suggestions."
                if enabled
                else "🔒 Automation mode DISABLED — AI will only suggest, not execute."
            ),
        }

    # ─── Background Loop ─────────────────────────────────────────────────────

    def start_background_loop(self):
        """Start the auto-refresh background thread (idempotent)."""
        if self._running:
            log.debug("[engine] Background loop already running")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="options-ai-engine"
        )
        self._thread.start()
        log.info("[engine] Background analysis loop started")

    def stop_background_loop(self):
        """Stop the background thread."""
        self._running = False
        log.info("[engine] Background analysis loop stopped")

    def _loop(self):
        """Background thread: sleep → analyze → repeat."""
        interval = AI_ENGINE_CONFIG["analysis_interval_minutes"] * 60
        while self._running:
            try:
                self.analyze()
            except Exception as e:
                log.error(f"[engine] Background analysis error: {e}")
            # Sleep in 5-second increments so we can stop quickly
            elapsed = 0
            while self._running and elapsed < interval:
                time.sleep(5)
                elapsed += 5


# ─── Singleton ────────────────────────────────────────────────────────────────

_engine_instance: Optional[OptionsAIEngine] = None
_engine_lock = threading.Lock()


def get_engine() -> OptionsAIEngine:
    """Get or create the singleton OptionsAIEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                _engine_instance = OptionsAIEngine()
                log.info("[engine] Singleton created")
    return _engine_instance
