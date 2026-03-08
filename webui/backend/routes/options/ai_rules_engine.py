"""
AI Rules Engine — Hardcoded Options Risk Rules
===============================================
Runs entirely locally, zero external API calls.

Produces structured flags + suggestions that:
  1. Feed into the Claude prompt template
  2. Are rendered directly in the UI even before the user pastes any LLM response
"""

import logging

log = logging.getLogger(__name__)


# ─── Rule definitions ────────────────────────────────────────────────────────

RULES = [
    {
        "id": "HIGH_DELTA",
        "severity": "high",
        "title": "High Net Delta Exposure",
        "action": "hedge",
        "urgency": "immediate",
    },
    {
        "id": "MARGIN_CRITICAL",
        "severity": "critical",
        "title": "Critical Margin Utilization",
        "action": "reduce",
        "urgency": "immediate",
    },
    {
        "id": "MARGIN_WARNING",
        "severity": "high",
        "title": "High Margin Utilization",
        "action": "reduce",
        "urgency": "monitor",
    },
    {
        "id": "POOR_STRUCTURE",
        "severity": "medium",
        "title": "Unfavorable Risk:Reward Structure",
        "action": "restructure",
        "urgency": "monitor",
    },
    {
        "id": "GAMMA_RISK",
        "severity": "high",
        "title": "Gamma Risk Near Strike / Expiry",
        "action": "reduce",
        "urgency": "immediate",
    },
    {
        "id": "DEEP_LOSS_POSITION",
        "severity": "medium",
        "title": "Deep Loss Position(s)",
        "action": "review",
        "urgency": "monitor",
    },
    {
        "id": "THETA_BLEED",
        "severity": "medium",
        "title": "Negative Theta Near Expiry",
        "action": "close",
        "urgency": "immediate",
    },
    {
        "id": "DELTA_PNL_DOMINATED",
        "severity": "low",
        "title": "P&L Dominated by Delta (Directional Risk)",
        "action": "hedge delta",
        "urgency": "monitor",
    },
    {
        "id": "VOL_BACKWARDATION",
        "severity": "low",
        "title": "Vol Backwardation Detected",
        "action": "vega hedge",
        "urgency": "optional",
    },
]


def _flag(rule_id, message, detail, data):
    """Build a standardised flag dict."""
    rule = next((r for r in RULES if r["id"] == rule_id), {})
    return {
        "id": rule_id,
        "severity": rule.get("severity", "medium"),
        "title": rule.get("title", rule_id),
        "message": message,
        "detail": detail,
        "action": rule.get("action", "review"),
        "urgency": rule.get("urgency", "monitor"),
    }


# ─── Core analysis function ────────────────────────────────────────────────────

def analyze_portfolio(
    positions: list,
    portfolio_greeks: dict,
    pnl_attribution: dict,
    margin_pct: float,
    spot_price: float,
    config: dict,
) -> dict:
    """
    Run all hardcoded rules against live portfolio data.

    Returns:
        {
            "risk_level":  "low" | "medium" | "high" | "critical",
            "flags":       [ { id, severity, title, message, detail, action, urgency }, ... ],
            "suggestions": [ { action, title, detail, urgency }, ... ],
            "summary":     "One-sentence plain-English summary",
        }
    """
    flags = []
    rules = config.get("risk_rules", {})

    net_delta = float(portfolio_greeks.get("delta", 0))
    net_theta = float(portfolio_greeks.get("theta", 0))
    net_vega  = float(portfolio_greeks.get("vega", 0))

    total_pnl = sum(
        float(p.get("unrealized_pnl", 0) or 0) for p in positions
    )
    n_calls = sum(1 for p in positions if "C" in str(p.get("product_symbol", "")))
    n_puts  = sum(1 for p in positions if "P" in str(p.get("product_symbol", "")))

    # Attribution data
    delta_pnl = float(pnl_attribution.get("delta_pnl", 0))

    # ── HIGH_DELTA ────────────────────────────────────────────────────────────
    delta_threshold = rules.get("delta_high_threshold", 100)
    if abs(net_delta) > delta_threshold:
        delta_usd = abs(net_delta) * spot_price * 0.001  # 1 lot = 0.001 BTC
        flags.append(_flag(
            "HIGH_DELTA",
            f"Net delta {net_delta:+.1f} BTC contracts (≈${delta_usd:,.0f} directional exposure).",
            "Sell a short-dated ATM call (if long delta) or buy a put to reduce delta below "
            f"{delta_threshold} contracts.",
            {},
        ))

    # ── MARGIN_CRITICAL ───────────────────────────────────────────────────────
    if margin_pct >= rules.get("margin_critical_pct", 85):
        flags.append(_flag(
            "MARGIN_CRITICAL",
            f"Margin utilization is {margin_pct:.1f}% — CRITICAL. Forced liquidation risk.",
            "Close 3–5 positions immediately to bring margin below 75%. Prioritise smallest losers.",
            {},
        ))
    elif margin_pct >= rules.get("margin_warning_pct", 75):
        flags.append(_flag(
            "MARGIN_WARNING",
            f"Margin utilization is {margin_pct:.1f}% — limited buffer for adverse moves.",
            "Close 1–2 low-conviction positions to free 10–15% margin headroom.",
            {},
        ))

    # ── POOR_STRUCTURE (max_loss / max_profit) ────────────────────────────────
    max_profit = float(portfolio_greeks.get("max_profit", 0) or 0)
    max_loss   = abs(float(portfolio_greeks.get("max_loss",   0) or 0))
    rr_ratio   = rules.get("poor_rr_ratio", 5)
    if max_profit > 0 and max_loss > rr_ratio * max_profit:
        ratio = max_loss / max_profit
        flags.append(_flag(
            "POOR_STRUCTURE",
            f"Max loss (${max_loss:,.0f}) is {ratio:.1f}× max profit (${max_profit:,.0f}). R:R < 1:{rr_ratio}.",
            "Add protective long options or close short legs with the worst R:R to improve structure.",
            {},
        ))

    # ── GAMMA_RISK ────────────────────────────────────────────────────────────
    gamma_pct = rules.get("gamma_risk_pct_from_strike", 0.02)
    for pos in positions:
        try:
            greeks = pos.get("greeks") or {}
            s = float(greeks.get("spot", spot_price) or spot_price)
            k = float(pos.get("strike_price", 0) or 0)
            dte = int(pos.get("days_to_expiry", 99) or 99)
            if k > 0 and s > 0 and abs(s - k) / s < gamma_pct and dte <= 7:
                sym = pos.get("product_symbol", "")
                flags.append(_flag(
                    "GAMMA_RISK",
                    f"{sym}: spot ${s:,.0f} is within {gamma_pct*100:.0f}% of strike ${k:,.0f} "
                    f"with {dte} DTE — high gamma exposure.",
                    "Close or reduce this near-ATM position. Do NOT hold through expiry at current levels.",
                    {},
                ))
                break   # one flag is enough
        except Exception:
            continue

    # ── DEEP_LOSS_POSITION ────────────────────────────────────────────────────
    loss_threshold = rules.get("position_loss_flag_pct", -20)
    losing_pos = []
    for pos in positions:
        try:
            entry  = float(pos.get("avg_entry_price", 0) or 0)
            mark   = float(pos.get("mark_price", 0) or 0)
            side   = pos.get("side", "buy").lower()
            if entry > 0 and mark > 0:
                pnl_pct = ((mark - entry) / entry * 100) * (1 if side == "buy" else -1)
                if pnl_pct < loss_threshold:
                    losing_pos.append(pos.get("product_symbol", "?"))
        except Exception:
            continue

    if losing_pos:
        flags.append(_flag(
            "DEEP_LOSS_POSITION",
            f"{len(losing_pos)} position(s) with >{abs(loss_threshold)}% loss: {', '.join(losing_pos[:3])}.",
            "If theta is positive and DTE > 7, consider holding. If theta is negative, close now.",
            {},
        ))

    # ── THETA_BLEED ───────────────────────────────────────────────────────────
    dte_threshold = rules.get("theta_bleed_dte_threshold", 3)
    theta_bleed = [
        p.get("product_symbol", "?")
        for p in positions
        if float(p.get("theta", 0) or (p.get("greeks") or {}).get("theta", 0) or 0) < 0
        and int(p.get("days_to_expiry", 99) or 99) < dte_threshold
    ]
    if theta_bleed:
        flags.append(_flag(
            "THETA_BLEED",
            f"Long position(s) expiring in <{dte_threshold} days with negative theta: "
            f"{', '.join(theta_bleed[:3])}.",
            "Close long positions expiring <3 DTE unless deep ITM. Time decay accelerates near expiry.",
            {},
        ))

    # ── DELTA_PNL_DOMINATED ───────────────────────────────────────────────────
    dominance = rules.get("delta_pnl_dominance_ratio", 0.70)
    if abs(total_pnl) > 1 and abs(delta_pnl) > dominance * abs(total_pnl):
        pct = abs(delta_pnl) / abs(total_pnl) * 100
        flags.append(_flag(
            "DELTA_PNL_DOMINATED",
            f"{pct:.0f}% of today's P&L (${delta_pnl:+,.0f}) is from directional price movement.",
            "Portfolio is behaving like a directional BTC trade. Consider delta-neutral hedging "
            "to isolate Greek income.",
            {},
        ))

    # ── Determine overall risk level ──────────────────────────────────────────
    sev_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    if any(f["severity"] == "critical" for f in flags):
        risk_level = "critical"
    elif any(f["severity"] == "high" for f in flags):
        risk_level = "high"
    elif any(f["severity"] == "medium" for f in flags):
        risk_level = "medium"
    elif flags:
        risk_level = "low"
    else:
        risk_level = "low"

    # ── Build suggestions list ──────────────────────────────────────────────
    suggestions = [
        {
            "action":   f["action"],
            "title":    f["title"],
            "detail":   f["detail"],
            "urgency":  f["urgency"],
            "flag_id":  f["id"],
        }
        for f in sorted(flags, key=lambda x: sev_order.get(x["severity"], 0), reverse=True)
    ]

    # ── Plain-English summary ──────────────────────────────────────────────
    if not flags:
        summary = (
            f"Portfolio of {len(positions)} positions ({n_calls}C/{n_puts}P) appears stable. "
            f"Net delta {net_delta:+.1f}, margin {margin_pct:.0f}%, total P&L ${total_pnl:+,.0f}."
        )
    else:
        top = flags[0]
        summary = (
            f"{len(flags)} risk flag(s) detected. Most urgent: {top['title']} ({top['severity']}). "
            f"Net delta {net_delta:+.1f}, margin {margin_pct:.0f}%, P&L ${total_pnl:+,.0f}."
        )

    return {
        "risk_level":  risk_level,
        "flags":       flags,
        "suggestions": suggestions,
        "summary":     summary,
        "meta": {
            "n_positions": len(positions),
            "n_calls":     n_calls,
            "n_puts":      n_puts,
            "net_delta":   round(net_delta, 3),
            "net_theta":   round(net_theta, 3),
            "net_vega":    round(net_vega, 3),
            "total_pnl":   round(total_pnl, 2),
            "margin_pct":  round(margin_pct, 1),
            "spot_price":  round(spot_price, 0),
        },
    }
