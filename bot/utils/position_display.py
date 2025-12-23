# bot/utils/position_display.py
"""
Console Display for Position Tracking
Beautiful formatted tables showing positions, PnL, and liquidation risk
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal

log = logging.getLogger("runner")

# Try to import colors
try:
    from bot.utils.colors import green, red, orange, cyan, bold, purple
except Exception:
    # Fallback if colors not available
    def green(s): return s
    def red(s): return s
    def orange(s): return s
    def cyan(s): return s
    def bold(s): return s
    def purple(s): return s


def format_currency(value: float, currency: str = "₹") -> str:
    """Format currency with commas and symbol"""
    return f"{currency}{value:,.2f}"


def format_pnl(value: float, show_sign: bool = True) -> str:
    """Format PnL with color coding"""
    if value >= 0:
        sign = "+" if show_sign else ""
        return green(f"{sign}${value:.2f}")
    else:
        return red(f"-${abs(value):.2f}")


def format_pnl_inr(value: float, show_sign: bool = True) -> str:
    """Format PnL in INR with color coding"""
    if value >= 0:
        sign = "+" if show_sign else ""
        return green(f"{sign}₹{value:,.2f}")
    else:
        return red(f"-₹{abs(value):,.2f}")


def get_risk_emoji(risk_level: str) -> str:
    """Get emoji for risk level"""
    risk_emojis = {
        "safe": "🟢",
        "warning": "🟡",
        "danger": "🟠",
        "critical": "🔴",
    }
    return risk_emojis.get(risk_level, "⚪")


def get_risk_color(risk_level: str, text: str) -> str:
    """Apply color based on risk level"""
    risk_colors = {
        "safe": green,
        "warning": orange,
        "danger": orange,
        "critical": red,
    }
    color_fn = risk_colors.get(risk_level, lambda x: x)
    return color_fn(text)


def format_position_table(positions: List[Any], summary: Dict[str, Any]) -> str:
    """
    Create a beautiful formatted table of positions
    
    Args:
        positions: List of Position objects
        summary: Summary dictionary from PositionTracker
    
    Returns:
        Formatted string with position table
    """
    if not positions:
        return format_empty_positions()
    
    lines = []
    
    # Header
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(bold(f"  OPEN POSITIONS ({len(positions)})"))
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Position rows
    for idx, pos in enumerate(positions, 1):
        lines.append("")
        
        # Position header
        risk_emoji = get_risk_emoji(pos.liquidation.risk_level)
        risk_text = get_risk_color(pos.liquidation.risk_level, pos.liquidation.risk_level.upper())
        
        lines.append(f"  #{idx}  Entry: {format_currency(pos.entry_price)}  →  Now: {format_currency(pos.current_price)}")
        
        # Liquidation info
        liq_price = format_currency(pos.liquidation.liquidation_price)
        dist_pct = pos.liquidation.distance_to_liq_percent
        dist_color = green if dist_pct > 5 else (orange if dist_pct > 2 else red)
        dist_text = dist_color(f"{dist_pct:.2f}%")
        
        lines.append(f"      Size: {pos.size}  |  Liq: {liq_price}  |  Distance: {dist_text}")
        
        # PnL and margin
        pnl_text = format_pnl(pos.pnl_usd, show_sign=True)
        pnl_inr_text = format_pnl_inr(pos.pnl_inr, show_sign=True)
        margin_pct = pos.margin.margin_ratio * 100
        margin_color = green if margin_pct > 80 else (orange if margin_pct > 50 else red)
        margin_text = margin_color(f"{margin_pct:.0f}%")
        
        lines.append(f"      PnL: {pnl_text} / {pnl_inr_text}  |  Margin: {margin_text}  |  {risk_emoji} {risk_text}")
        
        # Auto top-up status
        if pos.liquidation.auto_topup_count > 0:
            topup_text = orange(f"⚠️  AUTO TOP-UP: {pos.liquidation.auto_topup_count} times")
            lines.append(f"      {topup_text}")
    
    # Summary section
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Total PnL
    total_pnl_usd = summary.get("total_pnl_usd", 0)
    total_pnl_inr = summary.get("total_pnl_inr", 0)
    pnl_text = format_pnl(total_pnl_usd, show_sign=True)
    pnl_inr_text = format_pnl_inr(total_pnl_inr, show_sign=True)
    
    lines.append(f"  TOTAL PNL: {pnl_text} / {pnl_inr_text}")
    
    # Risk status
    risk_pct = summary.get("risk_percent", 0)
    if risk_pct < 50:
        risk_status = green(f"✅ SAFE ({risk_pct:.1f}% of limit)")
    elif risk_pct < 75:
        risk_status = orange(f"⚠️  WARNING ({risk_pct:.1f}% of limit)")
    elif risk_pct < 90:
        risk_status = orange(f"🔸 DANGER ({risk_pct:.1f}% of limit)")
    else:
        risk_status = red(f"🚨 CRITICAL ({risk_pct:.1f}% of limit)")
    
    lines.append(f"  Risk Status: {risk_status}")
    
    # Liquidation risk
    overall_liq_risk = summary.get("overall_liq_risk", "low")
    positions_at_risk = summary.get("positions_at_risk", 0)
    
    if overall_liq_risk == "low":
        liq_text = green("🟢 ALL POSITIONS SAFE")
    elif overall_liq_risk == "medium":
        liq_text = orange(f"🟡 {positions_at_risk} POSITION(S) AT RISK")
    elif overall_liq_risk == "high":
        liq_text = orange(f"🟠 {positions_at_risk} POSITION(S) IN DANGER")
    else:  # critical
        liq_text = red(f"🔴 {positions_at_risk} POSITION(S) CRITICAL")
    
    lines.append(f"  Liquidation Risk: {liq_text}")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    
    return "\n".join(lines)


def format_empty_positions() -> str:
    """Format display when no positions are open"""
    lines = []
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(cyan("  NO OPEN POSITIONS"))
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    return "\n".join(lines)


def format_compact_summary(summary: Dict[str, Any]) -> str:
    """
    Create a compact one-line summary for heartbeat logs
    
    Args:
        summary: Summary dictionary from PositionTracker
    
    Returns:
        Compact formatted string
    """
    if summary.get("total_positions", 0) == 0:
        return ""
    
    total_pnl_inr = summary.get("total_pnl_inr", 0)
    risk_pct = summary.get("risk_percent", 0)
    min_margin = summary.get("min_margin_ratio", 0) * 100
    
    # Format PnL
    if total_pnl_inr >= 0:
        pnl_text = green(f"+₹{total_pnl_inr:,.0f}")
    else:
        pnl_text = red(f"-₹{abs(total_pnl_inr):,.0f}")
    
    # Format risk
    if risk_pct < 50:
        risk_text = green(f"{risk_pct:.0f}%")
    elif risk_pct < 75:
        risk_text = orange(f"{risk_pct:.0f}%")
    else:
        risk_text = red(f"{risk_pct:.0f}%")
    
    # Format margin
    if min_margin > 80:
        margin_text = green(f"{min_margin:.0f}%")
    elif min_margin > 50:
        margin_text = orange(f"{min_margin:.0f}%")
    else:
        margin_text = red(f"{min_margin:.0f}%")
    
    return f"PnL:{pnl_text} Risk:{risk_text} MinMargin:{margin_text}"


def display_positions(position_tracker) -> None:
    """
    Display full position table in logs
    
    Args:
        position_tracker: PositionTracker instance
    """
    try:
        positions = position_tracker.get_all_positions()
        summary = position_tracker.get_summary()
        
        table = format_position_table(positions, summary)
        log.info(table)
        
    except Exception as e:
        log.warning(f"Failed to display positions: {e}")


def display_compact_summary(position_tracker) -> str:
    """
    Get compact summary for heartbeat
    
    Args:
        position_tracker: PositionTracker instance
    
    Returns:
        Compact summary string
    """
    try:
        summary = position_tracker.get_summary()
        return format_compact_summary(summary)
    except Exception as e:
        log.debug(f"Failed to get compact summary: {e}")
        return ""

