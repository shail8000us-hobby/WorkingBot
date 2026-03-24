"""
IC Telegram Alerts — Iron Condor

Telegram notifications for critical IC events.
Uses the same async TelegramNotifier infrastructure as MMM.

Events:
  - Cycle opened / closed
  - Adjustment triggers (roll events)
  - Emergency close
  - Daily loss limit hit
  - Circuit breaker activated
  - Max adjustments reached

From IC_ALGO_PLAN.md §C.12.

Created: 2026-03-24
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional

log = logging.getLogger('ic_telegram')

# Dedup window
_DEDUP_WINDOW_SECS = 30
_last_sent: Dict[str, float] = {}
_notifier_instance = None


def _get_telegram_credentials() -> tuple:
    """Load Telegram credentials from config."""
    try:
        from config.loader import get_config
        cfg = get_config()
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
        log.debug("Telegram not configured — IC alerts disabled")
        return None

    try:
        from webui.backend.services.notifications import TelegramNotifier
        _notifier_instance = TelegramNotifier(token, chat_id)
        return _notifier_instance
    except ImportError:
        try:
            from ...services.notifications import TelegramNotifier
            _notifier_instance = TelegramNotifier(token, chat_id)
            return _notifier_instance
        except Exception:
            log.debug("TelegramNotifier not available")
            return None


def _should_send(key: str) -> bool:
    """Dedup check."""
    now = time.time()
    last = _last_sent.get(key, 0)
    if now - last < _DEDUP_WINDOW_SECS:
        return False
    _last_sent[key] = now
    return True


async def _send_async(text: str, key: str) -> bool:
    """Send a Telegram message with dedup."""
    if not _should_send(key):
        return False

    notifier = _get_notifier()
    if not notifier:
        return False

    try:
        success = await notifier._send_message(text, parse_mode='Markdown')
        if success:
            log.info(f"IC Telegram alert sent: {key}")
        return success
    except Exception as e:
        log.warning(f"IC Telegram send error: {e}")
        return False


def _send_sync(text: str, key: str):
    """Fire-and-forget sync wrapper for alert functions."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_send_async(text, key))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    except Exception:
        pass  # fire-and-forget


# ─── IC Alert Functions ──────────────────────────────────────────────────────

def alert_cycle_opened(
    session_id: str,
    cycle_number: int,
    sp_strike: float,
    sc_strike: float,
    net_credit: float,
    max_loss: float,
    expiry: str,
):
    """Alert when a new IC cycle is opened."""
    msg = f"""📊 *IC CYCLE OPENED* (#{cycle_number})

🔵 Short Put: *${sp_strike:,.0f}*
🔴 Short Call: *${sc_strike:,.0f}*
💰 Net Credit: *${net_credit:.2f}/BTC*
⚠️ Max Loss: *${abs(max_loss):.2f}*
📅 Expiry: `{expiry}`

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    _send_sync(msg, f"cycle_opened_{session_id}_{cycle_number}")


def alert_cycle_closed(
    session_id: str,
    cycle_number: int,
    exit_reason: str,
    realized_pnl: float,
    total_realized: float,
):
    """Alert when a cycle is closed."""
    pnl_emoji = '✅' if realized_pnl >= 0 else '❌'
    msg = f"""{pnl_emoji} *IC CYCLE CLOSED* (#{cycle_number})

📋 Reason: *{exit_reason}*
💰 Cycle P&L: *${realized_pnl:+.6f}*
📊 Total P&L: *${total_realized:+.6f}*

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    _send_sync(msg, f"cycle_closed_{session_id}_{cycle_number}")


def alert_adjustment(
    session_id: str,
    adj_type: str,
    old_strikes: Dict,
    new_strikes: Dict,
    roll_credit: float,
    adjustment_count: int,
    max_adjustments: int,
):
    """Alert on roll adjustment."""
    credit_emoji = '✅' if roll_credit >= 0 else '⚠️'
    msg = f"""🔄 *IC ADJUSTMENT* ({adj_type})

📊 Old: {old_strikes}
📊 New: {new_strikes}
{credit_emoji} Roll Credit: *${roll_credit:+.4f}/BTC*
🔢 Adjustments: *{adjustment_count}/{max_adjustments}*

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    _send_sync(msg, f"adjustment_{session_id}_{adjustment_count}")


def alert_emergency_close(session_id: str, reason: str):
    """Alert on emergency close."""
    msg = f"""🚨 *IC EMERGENCY CLOSE*

⚡ *All positions being closed!*
📋 Reason: {reason}

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    _send_sync(msg, f"emergency_{session_id}")


def alert_daily_loss_limit(session_id: str, loss: float, limit: float):
    """Alert when daily loss limit is hit."""
    msg = f"""🛑 *IC DAILY LOSS LIMIT*

💸 Daily loss: *${loss:.2f}*
🛑 Limit: *${limit:.2f}*
⚡ *No new cycles until tomorrow*

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    _send_sync(msg, f"daily_loss_{session_id}")


def alert_circuit_breaker(session_id: str, adjustments_in_hour: int):
    """Alert when circuit breaker activates."""
    msg = f"""⚡ *IC CIRCUIT BREAKER*

🔌 {adjustments_in_hour} adjustments in 60 minutes
⏳ Pausing for 30 minutes
⚠️ Market too volatile for mechanical adjustments

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    _send_sync(msg, f"circuit_breaker_{session_id}")
