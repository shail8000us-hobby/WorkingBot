"""
MMM Telegram Alerts — Money Mind & Method

Sends Telegram notifications for critical margin/safety events.
Uses the existing async TelegramNotifier infrastructure.

Events that trigger Telegram alerts:
  - Margin tier changes (YELLOW→ORANGE, etc.)
  - Emergency close activation (RED/CRITICAL)
  - Rapid-check mode activation
  - Session auto-stop (CRITICAL tier or max-loss)
  - Margin utilization threshold crossed

Disabled by default — requires Telegram bot token + chat ID in config.

Created: February 20, 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional

log = logging.getLogger('mmm_telegram')

# Dedup window: don't send same alert type within this many seconds
_DEDUP_WINDOW_SECS = 30

# Module-level singleton
_notifier_instance = None
_last_sent: Dict[str, float] = {}


def _get_telegram_credentials() -> tuple:
    """Load Telegram credentials from config."""
    try:
        from config.loader import get_config
        cfg = get_config()
        # Try MMM-specific first, then fall back to live, then generic
        token = (
            getattr(getattr(cfg, 'telegram', None), 'live_bot_token', None)
            or getattr(getattr(cfg, 'telegram', None), 'bot_token', None)
            or ''
        )
        chat_id = (
            getattr(getattr(cfg, 'telegram', None), 'live_chat_id', None)
            or getattr(getattr(cfg, 'telegram', None), 'chat_id', None)
            or ''
        )
        return str(token), str(chat_id)
    except Exception as e:
        log.debug(f"Failed to load Telegram config: {e}")
        return '', ''


def _get_notifier():
    """Get or create the async TelegramNotifier singleton."""
    global _notifier_instance
    if _notifier_instance is not None:
        return _notifier_instance

    token, chat_id = _get_telegram_credentials()
    if not token or not chat_id:
        log.debug("Telegram not configured — alerts disabled")
        return None

    try:
        from webui.backend.services.notifications import TelegramNotifier
        _notifier_instance = TelegramNotifier(token, chat_id)
        return _notifier_instance
    except ImportError:
        # Fallback: try relative import
        try:
            from ...services.notifications import TelegramNotifier
            _notifier_instance = TelegramNotifier(token, chat_id)
            return _notifier_instance
        except Exception:
            log.debug("TelegramNotifier not available")
            return None


def _should_send(key: str) -> bool:
    """Dedup check — returns True if this alert type can be sent now."""
    now = time.time()
    last = _last_sent.get(key, 0)
    if now - last < _DEDUP_WINDOW_SECS:
        return False
    _last_sent[key] = now
    return True


async def _send_async(text: str, key: str) -> bool:
    """Send a Telegram message asynchronously with dedup."""
    if not _should_send(key):
        log.debug(f"Telegram alert deduped: {key}")
        return False

    notifier = _get_notifier()
    if not notifier:
        return False

    try:
        success = await notifier._send_message(text, parse_mode='Markdown')
        if success:
            log.info(f"Telegram alert sent: {key}")
        else:
            log.warning(f"Telegram alert failed: {key}")
        return success
    except Exception as e:
        log.warning(f"Telegram send error: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────
# Alert functions (called from mmm_monitor.py)
# ─────────────────────────────────────────────────────────────────────

async def alert_margin_tier_change(
    session_id: str,
    prev_tier: str,
    new_tier: str,
    utilization_pct: float,
    net_equity: float = 0,
    position_margin: float = 0,
) -> bool:
    """Alert on margin tier transition."""
    tier_emoji = {
        'GREEN': '🟢', 'YELLOW': '🟡', 'ORANGE': '🟠',
        'RED': '🔴', 'CRITICAL': '🚨',
    }

    severity = '⚠️' if new_tier in ('YELLOW', 'ORANGE') else '🚨'

    msg = f"""{severity} *MMM MARGIN ALERT*

📊 Tier: *{tier_emoji.get(prev_tier, '?')} {prev_tier} → {tier_emoji.get(new_tier, '?')} {new_tier}*
📈 Utilization: *{utilization_pct:.1f}%*
💰 Net Equity: *${net_equity:,.2f}*
🔒 Position Margin: *${position_margin:,.2f}*

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    return await _send_async(msg, f"tier_change_{session_id}_{new_tier}")


async def alert_emergency_close(
    session_id: str,
    reason: str,
    tier: str = '',
    utilization_pct: float = 0,
) -> bool:
    """Alert when emergency close is triggered."""
    msg = f"""🚨 *MMM EMERGENCY CLOSE*

⚡ *All positions being closed!*
📋 Reason: {reason}
{"📊 Margin: " + f"*{utilization_pct:.1f}%* ({tier})" if tier else ""}

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC

_Using taker orders for fastest execution._"""

    return await _send_async(msg, f"emergency_close_{session_id}")


async def alert_session_stopped(
    session_id: str,
    reason: str,
) -> bool:
    """Alert when session is auto-stopped by safety system."""
    msg = f"""🛑 *MMM SESSION STOPPED*

🤖 Session: `{session_id}`
📋 Reason: {reason}

_Session requires manual restart._

⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    return await _send_async(msg, f"session_stop_{session_id}")


async def alert_rapid_check_activated(
    session_id: str,
    trigger_reason: str,
    utilization_pct: float = 0,
) -> bool:
    """Alert when rapid-check mode (15s heartbeat) activates."""
    msg = f"""⚡ *MMM RAPID-CHECK MODE*

🏃 Heartbeat interval: *15 seconds*
📋 Trigger: {trigger_reason}
{"📊 Margin: *" + f"{utilization_pct:.1f}%" + "*" if utilization_pct else ""}

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    return await _send_async(msg, f"rapid_check_{session_id}")


async def alert_max_loss_breach(
    session_id: str,
    total_pnl: float,
    max_loss: float,
) -> bool:
    """Alert when max loss is breached."""
    msg = f"""🚨 *MMM MAX LOSS BREACHED*

💸 P&L: *${total_pnl:+,.2f}*
🛑 Limit: *-${abs(max_loss):,.2f}*

⚡ *Emergency closing all positions*

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    return await _send_async(msg, f"max_loss_{session_id}")


async def alert_both_sides_up(
    session_id: str,
    ce_now: float,
    pe_now: float,
    ce_trigger: float,
    pe_trigger: float,
) -> bool:
    """IMP-12: Alert when both CE and PE are above their triggers simultaneously."""
    msg = f"""🚨 *MMM BOTH SIDES UP — MANUAL DECISION REQUIRED*

📈 CE Premium: *${ce_now:,.2f}* (trigger: ${ce_trigger:,.2f})
📉 PE Premium: *${pe_now:,.2f}* (trigger: ${pe_trigger:,.2f})

⏸️ *Session paused. Both sides triggered simultaneously.*
This requires human judgement. Log in and decide:
• Continue by deciding which side to hedge
• Close all positions
• Wait for one side to drop below trigger

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    return await _send_async(msg, f"both_sides_up_{session_id}")
