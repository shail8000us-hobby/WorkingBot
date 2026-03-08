"""
Options AI Engine — AI Advisor

Calls Claude (Anthropic) or OpenAI GPT-4 with a structured prompt built
from live position data, market context, and past decision history.
Returns a strictly-formatted JSON response.

The AI is instructed to:
  - Prioritise capital preservation
  - Never suggest actions that breach margin limits
  - Always provide an alternative/hedge when recommending a close
  - Consider Theta decay timing (avoid closing net-Theta-positive positions 1-2 DTE)
"""

import json
import logging
from typing import Dict, List, Any, Optional

from .config_ai import AI_ENGINE_CONFIG, get_ai_api_key, is_ai_configured

log = logging.getLogger(__name__)

# ─── System Prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an institutional-grade Options Portfolio Risk Advisor AI embedded inside a live trading bot.
Your role is to analyse the trader's open options positions and provide clear, actionable, risk-aware recommendations.

STRICT RULES you must always follow:
1. CAPITAL PRESERVATION FIRST — always prioritise protecting existing capital over maximising profit.
2. NEVER suggest actions that would breach margin limits or increase net exposure beyond what the portfolio can sustain.
3. ALWAYS provide an alternative or hedge when you recommend closing a position — never leave the trader without a plan.
4. THETA AWARENESS — do not suggest closing positions with 1-2 DTE that are net Theta-positive, unless risk is critical.
5. CONFIDENCE — be honest about your confidence level (0.0–1.0). Low confidence means the trader should monitor, not act.
6. BE CONVERSATIONAL AND EDUCATIONAL — explain your reasoning clearly. No terse one-word outputs.

RESPONSE FORMAT: You MUST return a single valid JSON object with EXACTLY these keys:
{
  "summary": "<plain English overview of the current portfolio risk>",
  "risk_level": "<one of: low | medium | high | critical>",
  "suggestions": [
    {
      "position_id": "<symbol>",
      "action": "<one of: hold | reduce | close | hedge | roll>",
      "reason": "<clear explanation of why>",
      "urgency": "<one of: immediate | monitor | optional>",
      "alternative": "<what to do instead if the trader does not take this action>"
    }
  ],
  "market_view": "<AI's 1-sentence short-term directional/volatility view>",
  "portfolio_advice": "<overall portfolio-level recommendation in 2-3 sentences>",
  "confidence": <float between 0.0 and 1.0>
}

DO NOT return anything outside the JSON object. DO NOT add markdown fences."""


# ─── Prompt Builder ───────────────────────────────────────────────────────────

def build_prompt(
    positions_data: Dict,
    market_ctx: Dict,
    recent_decisions: List[Dict],
    risk_pref: str = "moderate",
) -> str:
    """
    Build the user-turn prompt from structured data.

    Args:
        positions_data: Output of position_analyzer.analyze_positions().
        market_ctx: Output of market_context.get_market_context().
        recent_decisions: Last N records from memory_store.load_recent().
        risk_pref: 'conservative' | 'moderate' | 'aggressive'

    Returns:
        Formatted prompt string.
    """
    positions = positions_data.get("positions", [])
    portfolio_greeks = positions_data.get("portfolio_greeks", {})
    total_pnl = positions_data.get("total_pnl", 0)
    flagged = positions_data.get("flagged_count", 0)

    pos_lines = []
    for p in positions:
        flags_str = ", ".join(p.get("flags", [])) or "none"
        pos_lines.append(
            f"  - {p['symbol']}: size={p['size']}, entry={p['entry_price']}, "
            f"mark={p['mark_price']}, P&L={p['unrealized_pnl']} ({p['pnl_pct']:.1f}%), "
            f"Δ={p['greeks']['delta']}, Γ={p['greeks']['gamma']}, "
            f"Θ={p['greeks']['theta']}, ν={p['greeks']['vega']}, "
            f"IV={p.get('iv', 0):.2%}, flags=[{flags_str}]"
        )
    positions_text = "\n".join(pos_lines) if pos_lines else "  No open positions."

    # Past decisions summary
    history_lines = []
    for d in recent_decisions[-5:]:  # last 5 for brevity
        verdict = d.get("verdict", "pending")
        history_lines.append(
            f"  [{d.get('timestamp', '')[:16]}] risk={d.get('risk_level')} "
            f"action_taken={d.get('action_taken')} verdict={verdict}"
        )
    history_text = "\n".join(history_lines) if history_lines else "  No prior decisions recorded."

    prompt = f"""CURRENT PORTFOLIO STATUS
========================
Open Positions ({len(positions)} total, {flagged} flagged):
{positions_text}

Portfolio-Level Greeks: Delta={portfolio_greeks.get('delta', 0):.3f}, Gamma={portfolio_greeks.get('gamma', 0):.5f}, Theta={portfolio_greeks.get('theta', 0):.2f}, Vega={portfolio_greeks.get('vega', 0):.2f}
Total Unrealised P&L: {total_pnl:.2f}

MARKET CONTEXT
==============
Regime: {market_ctx.get('regime')} (confidence={market_ctx.get('regime_confidence', 0):.2f})
Trend: {market_ctx.get('trend')} | Price Direction Forecast: {market_ctx.get('price_direction')}
IV Classification: {market_ctx.get('iv_classification')} | Volatility Score: {market_ctx.get('volatility_score', 0):.3f}
Momentum: {market_ctx.get('momentum', 0):.3f} | Trend Strength: {market_ctx.get('trend_strength', 0):.3f}
Current Price: {market_ctx.get('current_price', 0)}

PAST DECISIONS (Learning Context)
==================================
{history_text}

TRADER RISK PREFERENCE: {risk_pref.upper()}

Please analyse these positions considering the market context and past performance.
Return your assessment as a JSON object following the exact format specified."""
    return prompt


# ─── AI Caller ───────────────────────────────────────────────────────────────

def _call_claude(prompt: str, api_key: str) -> Dict:
    """Call Anthropic Claude and return parsed JSON response."""
    import anthropic
    model = AI_ENGINE_CONFIG["claude_model"]
    timeout = AI_ENGINE_CONFIG["ai_request_timeout_sec"]
    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    return _safe_parse_json(raw)


def _call_openai(prompt: str, api_key: str) -> Dict:
    """Call OpenAI GPT-4 and return parsed JSON response."""
    import openai
    model = AI_ENGINE_CONFIG["openai_model"]
    timeout = AI_ENGINE_CONFIG["ai_request_timeout_sec"]
    client = openai.OpenAI(api_key=api_key, timeout=timeout)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2048,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content.strip()
    return _safe_parse_json(raw)


def _safe_parse_json(raw: str) -> Dict:
    """Parse JSON, stripping any markdown fences if present."""
    # Strip ```json ... ``` fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log.error(f"[ai_advisor] JSON parse error: {e}\nRaw: {raw[:300]}")
        return {
            "summary": "AI returned malformed response — please retry.",
            "risk_level": "unknown",
            "suggestions": [],
            "market_view": "Unavailable",
            "portfolio_advice": "Could not parse AI response.",
            "confidence": 0.0,
            "parse_error": str(e),
        }


def _validate_response(response: Dict) -> Dict:
    """Fill in any missing required keys with safe defaults."""
    defaults = {
        "summary": "No summary provided.",
        "risk_level": "unknown",
        "suggestions": [],
        "market_view": "Unavailable",
        "portfolio_advice": "No advice provided.",
        "confidence": 0.0,
    }
    for k, v in defaults.items():
        if k not in response:
            response[k] = v
    # Clamp confidence
    response["confidence"] = max(0.0, min(1.0, float(response.get("confidence", 0.0))))
    return response


# ─── Public API ───────────────────────────────────────────────────────────────

def call_ai(
    positions_data: Dict,
    market_ctx: Dict,
    recent_decisions: Optional[List] = None,
    risk_pref: str = "moderate",
) -> Dict:
    """
    Build prompt and call the configured AI provider.

    Returns:
        Parsed, validated AI response dict.
        If AI is not configured, returns a placeholder response.
    """
    if recent_decisions is None:
        recent_decisions = []

    if not is_ai_configured():
        log.warning("[ai_advisor] AI API key not configured. Returning placeholder.")
        return {
            "summary": "AI Advisor not configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.",
            "risk_level": "unknown",
            "suggestions": [],
            "market_view": "Configure API key to enable AI analysis.",
            "portfolio_advice": "Please set the AI API key environment variable.",
            "confidence": 0.0,
            "error": "AI not configured",
        }

    prompt = build_prompt(positions_data, market_ctx, recent_decisions, risk_pref)
    api_key = get_ai_api_key()
    provider = AI_ENGINE_CONFIG["ai_provider"]

    try:
        if provider == "claude":
            response = _call_claude(prompt, api_key)
        else:
            response = _call_openai(prompt, api_key)
        return _validate_response(response)
    except Exception as e:
        log.error(f"[ai_advisor] API call failed: {e}")
        return {
            "summary": f"AI call failed: {str(e)[:200]}",
            "risk_level": "unknown",
            "suggestions": [],
            "market_view": "Unavailable",
            "portfolio_advice": "AI analysis temporarily unavailable.",
            "confidence": 0.0,
            "error": str(e),
        }


# ─── Standalone Test ─────────────────────────────────────────────────────────

def test():
    print("=== ai_advisor.test() ===")
    mock_positions_data = {
        "positions": [
            {
                "symbol": "C-BTC-120000-280326",
                "size": 2.0,
                "entry_price": 1500,
                "mark_price": 900,
                "unrealized_pnl": -1200,
                "pnl_pct": -40.0,
                "greeks": {"delta": 0.12, "gamma": 0.00002, "theta": -80, "vega": 120},
                "iv": 0.65,
                "flags": ["high_loss", "deeply_otm"],
            }
        ],
        "portfolio_greeks": {"delta": 0.24, "gamma": 0.00004, "theta": -160, "vega": 240},
        "total_pnl": -1200,
        "position_count": 1,
        "flagged_count": 1,
    }
    mock_market = {
        "regime": "HIGH_VOLATILITY",
        "regime_confidence": 0.8,
        "regime_description": "High volatility environment",
        "trend": "bearish",
        "momentum": -0.3,
        "volatility_score": 0.72,
        "iv_classification": "high",
        "mean_reversion_tendency": 0.2,
        "trend_strength": 0.5,
        "price_direction": "DOWN",
        "price_forecast_confidence": 0.6,
        "current_price": 84000,
        "recommendations": {},
    }

    prompt = build_prompt(mock_positions_data, mock_market, [])
    print(f"  Prompt length: {len(prompt)} chars")
    assert "C-BTC-120000" in prompt
    print("  Prompt built correctly ✅")

    if is_ai_configured():
        print("  API key found — calling AI...")
        response = call_ai(mock_positions_data, mock_market)
        print(f"  Risk level: {response.get('risk_level')}")
        print(f"  Suggestions: {len(response.get('suggestions', []))}")
        print(f"  Confidence: {response.get('confidence')}")
        required = ["summary", "risk_level", "suggestions", "market_view", "portfolio_advice", "confidence"]
        for k in required:
            assert k in response, f"Missing key: {k}"
        print("  Full AI response validates ✅")
    else:
        print("  No API key — testing placeholder response...")
        response = call_ai(mock_positions_data, mock_market)
        assert response.get("error") == "AI not configured"
        print("  Placeholder response correct ✅")

    print("  PASSED ✅")


if __name__ == "__main__":
    test()
