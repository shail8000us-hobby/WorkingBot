"""
Options AI Advisor Routes — API-Free Copy-Paste Model
======================================================
Architecture:
  Step 1 — GET  /api/options/ai/generate-prompt
      • Runs local rules engine
      • Formats a rich prompt the user can COPY and PASTE into Claude.ai
      • Returns both the prompt text AND the local analysis (shown immediately)
      • Saves a session to memory

  Step 2 — POST /api/options/ai/submit-response
      • User pastes Claude's JSON response into the UI
      • Backend parses, validates, and stores it in the session
      • Returns structured suggestions for rendering

  Additional:
  GET  /api/options/ai/status      — engine + config info
  GET  /api/options/ai/history     — last N sessions
  POST /api/options/ai/automation  — toggle automation

No external API calls. No API keys required.
"""

import json
import time
import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

from .ai_config import AI_CONFIG
from .ai_rules_engine import analyze_portfolio
from .ai_memory import (
    save_session,
    attach_ai_response,
    get_recent_sessions,
    get_outcome_summary,
)

log = logging.getLogger(__name__)

# Unique prefix — avoids silent URL map conflicts with other /api/options blueprints
options_ai_advisor_bp = Blueprint(
    "options_ai_advisor",
    __name__,
    url_prefix="/api/options/ai",
)

# ─── Prompt template ──────────────────────────────────────────────────────────

PROMPT_TEMPLATE = """\
You are an expert BTC/ETH options portfolio advisor. Analyse the live portfolio below and respond ONLY with the JSON block shown at the end. Do not add any prose before or after the JSON.

═══════════════════════════════════════════════════
LIVE PORTFOLIO DATA — {timestamp}
═══════════════════════════════════════════════════

PORTFOLIO SUMMARY
  Total positions : {n_positions} ({n_calls}C / {n_puts}P)
  BTC Spot Price  : ${spot_price:,.0f}
  Net Delta       : {net_delta:+.2f} contracts ({net_delta_btc:+.4f} BTC equiv.)
  Net Theta       : {net_theta:+.2f} USD/day
  Net Vega        : {net_vega:+.2f} USD/vol-pt
  Net P&L today   : ${total_pnl:+,.2f}
  Margin used     : {margin_pct:.1f}%

{positions_block}

PNL ATTRIBUTION (since last baseline)
  Delta  : ${delta_pnl:+,.2f}
  Gamma  : ${gamma_pnl:+,.2f}
  Theta  : ${theta_pnl:+,.2f}
  Vega   : ${vega_pnl:+,.2f}
  Residual: ${residual_pnl:+,.2f}

RULE-BASED FLAGS TRIGGERED LOCALLY ({n_flags} flag(s)):
{flags_block}

═══════════════════════════════════════════════════
RESPOND ONLY WITH THIS JSON (fill in all fields):
═══════════════════════════════════════════════════
{{
  "summary": "<2-3 sentence plain-English assessment of the portfolio right now>",
  "risk_level": "<low | medium | high | critical>",
  "market_view": "<bullish | bearish | neutral | uncertain>",
  "confidence": <integer 0-100>,
  "suggestions": [
    {{
      "action": "<hold | hedge | reduce | close | roll | restructure>",
      "title": "<short title>",
      "detail": "<specific actionable step, mention instruments/strikes if possible>",
      "urgency": "<immediate | monitor | optional>",
      "priority": <integer 1-5, 1=highest>
    }}
  ],
  "risk_commentary": "<What is the single biggest risk in this portfolio right now and why?>",
  "theta_commentary": "<Is the theta income sustainable at this margin level?>",
  "delta_hedge_advice": "<Specific hedge recommendation or 'No hedge needed.'>",
  "watch_levels": [
    {{"label": "<e.g. Gamma strike>", "price": <number>, "reason": "<why this level matters>"}}
  ]
}}
"""


def _build_positions_block(positions: list) -> str:
    if not positions:
        return "  No open positions."
    lines = [
        "  {sym:<30} {side:<5} {size:>6} | strike ${strike:>8,.0f} | exp {exp} | "
        "DTE {dte:>3} | delta {delta:>+7.3f} | P&L ${pnl:>+9,.2f}".format(
            sym=p.get("product_symbol", "?")[:30],
            side=(p.get("side") or "?").upper(),
            size=int(p.get("size", 0) or 0),
            strike=float(p.get("strike_price", 0) or 0),
            exp=p.get("settlement_time", "?")[:10],
            dte=int(p.get("days_to_expiry", 0) or 0),
            delta=float((p.get("greeks") or {}).get("delta", 0)),
            pnl=float(p.get("unrealized_pnl", 0) or 0),
        )
        for p in positions
    ]
    return "\n".join(lines)


def _build_flags_block(flags: list) -> str:
    if not flags:
        return "  ✅ No rule flags triggered."
    return "\n".join(
        f"  [{f['severity'].upper():8}] {f['id']:25} — {f['message']}"
        for f in flags
    )


def _get_live_data():
    """
    Pull all live data from the dashboard cache + PnL attribution.
    Zero additional Delta Exchange API calls.
    """
    try:
        from .pnl_attribution import _get_current_state, _compute_attribution, _baseline
        from .dashboard_service import fetch_margin_data
        from .dashboard import _dashboard_cache, calculate_portfolio_greeks

        # Positions + greeks from dashboard cache
        cached = _dashboard_cache.get("data") or {}
        positions = cached.get("positions", [])
        portfolio_greeks = cached.get("portfolio_greeks") or calculate_portfolio_greeks(positions)

        # Spot price
        positions2, _, spot, iv_avg, total_pnl = _get_current_state()
        if not positions and positions2:
            positions = positions2
            portfolio_greeks = calculate_portfolio_greeks(positions)

        # PnL attribution
        attribution = {}
        if _baseline and spot > 0:
            attribution = _compute_attribution(_baseline, spot, iv_avg, total_pnl)

        # Margin
        margin_data = fetch_margin_data()
        blocked = margin_data.get("blocked_margin_usd", 0)
        wallet  = margin_data.get("wallet_balance_usd", 0)
        margin_pct = (blocked / wallet * 100) if wallet > 0 else 0.0

        return positions, portfolio_greeks, attribution, margin_pct, spot, total_pnl

    except Exception as e:
        log.error(f"[options_ai] _get_live_data failed: {e}", exc_info=True)
        return [], {}, {}, 0.0, 0.0, 0.0


# ─── Routes ───────────────────────────────────────────────────────────────────

@options_ai_advisor_bp.route("/generate-prompt", methods=["GET"])
def advisor_generate_prompt():
    """
    Step 1: Gather live data → run rules engine → format Claude prompt.

    Response:
    {
      "success": true,
      "session_id": "uuid",
      "prompt_text": "<full text to paste into Claude>",
      "rule_analysis": { risk_level, flags, suggestions, summary, meta },
      "snapshot": { positions, greeks, margin_pct, spot }
    }
    """
    try:
        positions, portfolio_greeks, attribution, margin_pct, spot, total_pnl = _get_live_data()

        # Run local rules engine
        rule_analysis = analyze_portfolio(
            positions=positions,
            portfolio_greeks=portfolio_greeks,
            pnl_attribution=attribution,
            margin_pct=margin_pct,
            spot_price=spot,
            config=AI_CONFIG,
        )

        # Build snapshot for memory
        snapshot = {
            "positions_count": len(positions),
            "portfolio_greeks": portfolio_greeks,
            "margin_pct": round(margin_pct, 1),
            "spot_price": round(spot, 0),
            "total_pnl": round(total_pnl, 2),
            "attribution": attribution,
        }

        # Save session immediately (ai_response=None; added later on submit)
        session_id = save_session(
            rule_analysis=rule_analysis,
            snapshot=snapshot,
            ai_response=None,
        )

        # Build prompt text
        meta = rule_analysis.get("meta", {})
        prompt_text = PROMPT_TEMPLATE.format(
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            n_positions=meta.get("n_positions", len(positions)),
            n_calls=meta.get("n_calls", 0),
            n_puts=meta.get("n_puts", 0),
            spot_price=spot,
            net_delta=meta.get("net_delta", 0),
            net_delta_btc=meta.get("net_delta", 0) * 0.001,
            net_theta=meta.get("net_theta", 0),
            net_vega=meta.get("net_vega", 0),
            total_pnl=total_pnl,
            margin_pct=margin_pct,
            positions_block=_build_positions_block(positions),
            delta_pnl=attribution.get("delta_pnl", 0),
            gamma_pnl=attribution.get("gamma_pnl", 0),
            theta_pnl=attribution.get("theta_pnl", 0),
            vega_pnl=attribution.get("vega_pnl", 0),
            residual_pnl=attribution.get("residual_pnl", 0),
            n_flags=len(rule_analysis.get("flags", [])),
            flags_block=_build_flags_block(rule_analysis.get("flags", [])),
        )

        return jsonify({
            "success":       True,
            "session_id":    session_id,
            "prompt_text":   prompt_text,
            "rule_analysis": rule_analysis,
            "snapshot":      snapshot,
        })

    except Exception as e:
        log.error(f"[options_ai] generate_ai_prompt error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_ai_advisor_bp.route("/submit-response", methods=["POST"])
def advisor_submit_response():
    """
    Step 2: User pastes Claude's JSON response.

    Body: { "session_id": "uuid", "response_text": "{ ... }" }

    Response:
    {
      "success": true,
      "session_id": "uuid",
      "parsed": { summary, risk_level, suggestions, ... }
    }
    """
    try:
        body = request.get_json() or {}
        session_id    = body.get("session_id", "")
        response_text = body.get("response_text", "").strip()

        if not response_text:
            return jsonify({"success": False, "error": "response_text is required"}), 400

        # Strip markdown code fences if user pasted from Claude
        if response_text.startswith("```"):
            lines = response_text.splitlines()
            inner = []
            in_block = False
            for line in lines:
                if line.startswith("```"):
                    in_block = not in_block
                    continue
                if in_block or not line.startswith("```"):
                    inner.append(line)
            response_text = "\n".join(inner).strip()

        # Parse JSON
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as je:
            return jsonify({
                "success": False,
                "error": f"Invalid JSON: {je}. Please paste the raw JSON block from Claude.",
            }), 400

        # Validate required fields
        required = AI_CONFIG.get("required_response_fields", [])
        missing = [f for f in required if f not in parsed]
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required fields in Claude response: {missing}",
                "received_keys": list(parsed.keys()),
            }), 400

        # Validate risk_level
        valid_risks = AI_CONFIG.get("valid_risk_levels", ["low", "medium", "high", "critical"])
        if parsed.get("risk_level") not in valid_risks:
            parsed["risk_level"] = "medium"  # safe default

        # Normalise suggestions
        suggestions = parsed.get("suggestions", [])
        valid_actions  = AI_CONFIG.get("valid_actions", [])
        valid_urgency  = AI_CONFIG.get("valid_urgency", ["immediate", "monitor", "optional"])
        for s in suggestions:
            if valid_actions and s.get("action") not in valid_actions:
                s["action"] = "review"
            if s.get("urgency") not in valid_urgency:
                s["urgency"] = "monitor"

        # Attach to session
        ai_response = {
            **parsed,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        found = attach_ai_response(session_id, ai_response)
        if not found:
            log.warning(f"[options_ai] session {session_id} not found — saving response without session link")

        return jsonify({
            "success":    True,
            "session_id": session_id,
            "parsed":     ai_response,
        })

    except Exception as e:
        log.error(f"[options_ai] submit_ai_response error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_ai_advisor_bp.route("/status", methods=["GET"])
def advisor_status():
    """
    Returns engine status and configuration info.
    """
    try:
        recent = get_recent_sessions(1)
        last = recent[0] if recent else None

        return jsonify({
            "success": True,
            "data": {
                "engine":            "api_free_rules_engine",
                "automation_mode":   AI_CONFIG.get("automation_mode", False),
                "rules_count":       8,
                "memory_window":     AI_CONFIG.get("memory_window", 10),
                "last_session_id":   last["session_id"] if last else None,
                "last_run_time":     last["timestamp"] if last else None,
                "last_risk_level":   last["rule_analysis"]["risk_level"] if last else None,
                "has_ai_response":   bool(last and last.get("ai_response")) if last else False,
                "outcome_summary":   get_outcome_summary(),
            },
        })
    except Exception as e:
        log.error(f"[options_ai] status error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_ai_advisor_bp.route("/history", methods=["GET"])
def advisor_history():
    """
    Returns last N sessions from memory (for Memory tab display).
    """
    try:
        n = min(int(request.args.get("n", 10)), 50)
        sessions = get_recent_sessions(n)

        # Strip bulky snapshot/positions to keep response small
        slim = []
        for s in sessions:
            slim.append({
                "session_id":   s["session_id"],
                "timestamp":    s["timestamp"],
                "risk_level":   s["rule_analysis"].get("risk_level"),
                "summary":      s["rule_analysis"].get("summary"),
                "n_flags":      len(s["rule_analysis"].get("flags", [])),
                "has_ai":       bool(s.get("ai_response")),
                "ai_summary":   (s.get("ai_response") or {}).get("summary"),
                "outcome_1h":   s.get("outcome_1h"),
                "outcome_4h":   s.get("outcome_4h"),
                "margin_pct":   s.get("snapshot", {}).get("margin_pct"),
                "spot_price":   s.get("snapshot", {}).get("spot_price"),
            })

        return jsonify({
            "success":  True,
            "sessions": slim,
            "total":    len(slim),
        })
    except Exception as e:
        log.error(f"[options_ai] history error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_ai_advisor_bp.route("/automation", methods=["POST"])
def advisor_toggle_automation():
    """
    Toggle automation mode (stored in-process only).
    Body: { "enabled": true | false }

    SAFETY: Only acts on 'immediate' urgency suggestions.
    Automation calls existing /api/options close/reduce routes — no new trading logic.
    """
    try:
        body = request.get_json() or {}
        enabled = bool(body.get("enabled", False))
        AI_CONFIG["automation_mode"] = enabled
        log.info(f"[options_ai] Automation mode set to: {enabled}")
        return jsonify({
            "success": True,
            "automation_mode": enabled,
            "message": (
                "⚡ Automation ENABLED — will act on immediate-urgency suggestions."
                if enabled else
                "🔒 Automation DISABLED — suggestions only, no auto-action."
            ),
        })
    except Exception as e:
        log.error(f"[options_ai] toggle_automation error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Direct registration helper ───────────────────────────────────────────────
# Flask Blueprint registration sometimes has silent issues with Flask-SocketIO.
# This function registers routes directly on the Flask app object as a fallback.

def register_ai_routes(app):
    """
    Register all Options AI Advisor routes directly on the Flask app.
    Call this from app.py if app.register_blueprint() silently fails.

    Final URLs:
      GET  /api/options/ai/generate-prompt
      POST /api/options/ai/submit-response
      GET  /api/options/ai/status
      GET  /api/options/ai/history
      POST /api/options/ai/automation
    """
    BASE = "/api/options/ai"
    routes = [
        (f"{BASE}/generate-prompt", "opt_ai_generate",  advisor_generate_prompt, ["GET"]),
        (f"{BASE}/submit-response",  "opt_ai_submit",    advisor_submit_response, ["POST"]),
        (f"{BASE}/status",           "opt_ai_status",    advisor_status,          ["GET"]),
        (f"{BASE}/history",          "opt_ai_history",   advisor_history,         ["GET"]),
        (f"{BASE}/automation",       "opt_ai_automation",advisor_toggle_automation,["POST"]),
    ]
    registered = []
    for url, endpoint, view_func, methods in routes:
        try:
            app.add_url_rule(url, endpoint=endpoint, view_func=view_func, methods=methods)
            registered.append(url)
        except AssertionError as ae:
            log.warning(f"[options_ai] Route {url} already registered: {ae}")
        except Exception as e:
            log.error(f"[options_ai] Failed to register {url}: {e}")
    print(f"✅ options_ai direct routes registered: {len(registered)}/5 routes")
    return len(registered)

