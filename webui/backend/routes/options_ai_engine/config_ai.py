"""
Options AI Engine — Configuration

All thresholds, API settings, and feature flags live here.
API keys are read from environment variables — never hardcoded.
"""

import os

AI_ENGINE_CONFIG = {
    # ── AI Provider ─────────────────────────────────────────────────────────
    "ai_provider": "claude",                     # "claude" | "openai"
    "claude_model": "claude-3-5-sonnet-20241022",
    "openai_model": "gpt-4o",
    "api_key_env_var": "ANTHROPIC_API_KEY",      # env var name for Claude
    "openai_key_env_var": "OPENAI_API_KEY",

    # ── Analysis Schedule ───────────────────────────────────────────────────
    "analysis_interval_minutes": 5,              # auto-refresh interval
    "outcome_check_after_minutes": 60,           # P&L outcome tracking delay

    # ── Automation Safety ───────────────────────────────────────────────────
    "automation_mode": False,                    # MUST be explicitly enabled
    "urgency_threshold_for_auto": "immediate",   # only act on "immediate" urgency
    "risk_threshold_for_auto": "critical",       # only act when risk is "critical"
    "max_auto_loss_pct": 2.0,                   # daily auto-loss circuit breaker

    # ── Position Flagging ───────────────────────────────────────────────────
    "loss_flag_threshold_pct": -5.0,            # flag if unrealised loss > 5%
    "high_gamma_threshold": 0.05,               # flag if abs(gamma) > this
    "deep_otm_pct": 30.0,                       # flag if >30% OTM
    "deep_itm_pct": 20.0,                       # flag if >20% ITM (intrinsic risk)

    # ── Memory / Learning ──────────────────────────────────────────────────
    "memory_window": 10,                         # last N decisions in AI prompt
    "memory_file": "data/options_ai_memory.json",

    # ── Request Timeout ────────────────────────────────────────────────────
    "ai_request_timeout_sec": 45,
    "positions_fetch_timeout_sec": 10,
}


def get_ai_api_key() -> str:
    """Return the active AI provider's API key from environment."""
    provider = AI_ENGINE_CONFIG["ai_provider"]
    if provider == "claude":
        return os.environ.get(AI_ENGINE_CONFIG["api_key_env_var"], "")
    return os.environ.get(AI_ENGINE_CONFIG["openai_key_env_var"], "")


def is_ai_configured() -> bool:
    """Return True if the AI API key is present in the environment."""
    return bool(get_ai_api_key())
