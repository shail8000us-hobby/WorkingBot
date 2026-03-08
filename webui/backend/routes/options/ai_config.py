"""
AI Advisor Configuration — API-Free Model
==========================================
No external API keys required. Analysis is done by the user pasting
a generated prompt into Claude.ai / ChatGPT / Perplexity, then pasting
the structured JSON response back into the WebUI.

Architecture:
  1. Backend runs hardcoded rules engine → local flags + risk level
  2. Backend formats a rich prompt string (copy-paste ready)
  3. User pastes prompt → Claude.ai → pastes JSON response back
  4. Backend parses & validates the JSON, stores in memory, renders in UI
"""

AI_CONFIG = {
    # ─── Memory ───────────────────────────────────────────────────────────────
    "memory_window": 10,          # Sessions shown in Memory tab
    "memory_file": "data/options_ai_memory.json",

    # ─── Outcome tracking ────────────────────────────────────────────────────
    "outcome_check_minutes": [60, 240],   # Check P&L delta at 1h and 4h

    # ─── Hardcoded risk rules ─────────────────────────────────────────────────
    #  These run locally on every analysis regardless of LLM usage.
    "risk_rules": {
        "delta_high_threshold":       100,   # BTC net delta above this = HIGH_DELTA
        "margin_warning_pct":         75,    # margin % ≥ this = MARGIN_WARNING
        "margin_critical_pct":        85,    # margin % ≥ this = MARGIN_CRITICAL
        "position_loss_flag_pct":    -20,    # unrealized PnL% below this = DEEP_LOSS
        "max_loss_to_profit_ratio":    5,    # max_loss > 5× max_profit = POOR_STRUCTURE
        "theta_bleed_dte_threshold":   3,    # DTE < this with negative theta = THETA_BLEED
        "vega_risk_iv_rank_threshold": 70,   # IV rank > this with high vega = VEGA_RISK
        "gamma_risk_pct_from_strike":  0.02, # spot within 2% of strike, DTE≤7 = GAMMA_RISK
        "delta_pnl_dominance_ratio":   0.70, # >70% PnL from delta = DELTA_DOMINATED
        "poor_rr_ratio":               5,    # max_loss / max_profit threshold
    },

    # ─── Automation (safety first) ────────────────────────────────────────────
    "automation_mode": False,     # Always starts False; user must explicitly enable
    "automation_urgency_filter": ["immediate"],  # Only auto-act on immediate flags

    # ─── Expected JSON keys from Claude response ─────────────────────────────
    "required_response_fields": [
        "summary", "risk_level", "market_view", "confidence", "suggestions"
    ],
    "valid_risk_levels": ["low", "medium", "high", "critical"],
    "valid_actions": ["hold", "hedge", "reduce", "close", "roll", "restructure"],
    "valid_urgency": ["immediate", "monitor", "optional"],
}
