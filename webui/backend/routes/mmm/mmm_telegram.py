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


async def send_telegram_message(text: str, dedup_key: str = '') -> bool:
    """Send a free-form Telegram message. Public wrapper around _send_async."""
    key = dedup_key or f'manual_{hash(text) & 0xFFFF}'
    return await _send_async(text, key)


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


# ─────────────────────────────────────────────────────────────────────
# Straddle Roll Alert functions (CRITICAL FIX C-3)
# ─────────────────────────────────────────────────────────────────────

def alert_half_roll_detected(session_id: str, closed_side: str, failed_side: str, stage: str):
    """Alert user that a roll was interrupted mid-execution (sync wrapper)."""
    try:
        asyncio.create_task(_alert_half_roll_detected_async(session_id, closed_side, failed_side, stage))
    except Exception:
        pass  # fire-and-forget


async def _alert_half_roll_detected_async(session_id: str, closed_side: str, failed_side: str, stage: str):
    """Alert user that a roll was interrupted mid-execution."""
    messages = {
        'close_failed': f"🔴 *HALF-ROLL DETECTED*\n\n❌ {closed_side.upper()} closed, {failed_side.upper()} close FAILED",
        'close_partial': f"🔴 *HALF-ROLL DETECTED*\n\n⚠️ {closed_side.upper()} closed, {failed_side.upper()} partial fill",
        'reentry_ce_failed': "🔴 *ROLL RE-ENTRY FAILED*\n\n❌ Both legs closed, CE re-entry FAILED (naked position)",
        'reentry_pe_failed_naked_ce': "🚨 *NAKED CE ALERT*\n\n💥 PE re-entry FAILED after CE sold\n🚨 **CLOSE CE MANUALLY**",
    }

    base_message = messages.get(stage, f"🔴 *HALF-ROLL*: Stage {stage}")

    msg = f"""{base_message}

🤖 Session: `{session_id}`
⚠️ **Manual intervention required**
📊 Check dashboard immediately
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    await _send_async(msg, f"half_roll_{session_id}_{stage}")


def alert_half_roll_recovery_needed(session_id: str, state: str):
    """Alert on backend restart that a session needs manual recovery (sync wrapper)."""
    try:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_alert_half_roll_recovery_needed_async(session_id, state))
        except RuntimeError:
            # No running event loop — startup context; dispatch via daemon thread
            import threading
            threading.Thread(
                target=asyncio.run,
                args=(_alert_half_roll_recovery_needed_async(session_id, state),),
                daemon=True,
            ).start()
    except Exception:
        pass


async def _alert_half_roll_recovery_needed_async(session_id: str, state: str):
    """Alert on backend restart that a session needs manual recovery."""
    msg = f"""🔴 *STARTUP ALERT*

🚨 Half-roll detected: `{state}`
🛑 Session auto-STOPPED
⚠️ Review dashboard and close/reset manually

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    await _send_async(msg, f"startup_half_roll_{session_id}")


def alert_straddle_roll_executed(
    session_id: str,
    roll_number: int,
    old_strike: float,
    new_strike: float,
    lots: int,
    new_credit: float,
):
    """Alert user that a straddle roll was successfully executed (sync wrapper)."""
    try:
        asyncio.create_task(_alert_straddle_roll_executed_async(
            session_id, roll_number, old_strike, new_strike, lots, new_credit,
        ))
    except Exception:
        pass  # fire-and-forget


async def _alert_straddle_roll_executed_async(
    session_id: str,
    roll_number: int,
    old_strike: float,
    new_strike: float,
    lots: int,
    new_credit: float,
):
    """Alert user that a straddle roll was successfully executed."""
    direction = '📈' if new_strike > old_strike else '📉'
    msg = f"""{direction} *STRADDLE ROLL #{roll_number} EXECUTED*

🔄 Strike: *{old_strike:.0f} → {new_strike:.0f}*
📦 Lots: *{lots}*
💰 New credit: *${new_credit:.3f}*

🤖 Session: `{session_id}`
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    await _send_async(msg, f"straddle_roll_{session_id}_{roll_number}")


# ─────────────────────────────────────────────────────────────────────
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


async def alert_guardian_violation(
    session_id: str,
    violations: list,
) -> bool:
    """Alert when guardian detects invariant violations and pauses the session."""
    bullet_list = '\n'.join(f'• `{v}`' for v in violations)
    msg = (
        f"⚠️ *GUARDIAN VIOLATION — SESSION PAUSED* — `{session_id}`\n\n"
        f"The Guardian detected *{len(violations)} invariant(s) breached*:\n\n"
        f"{bullet_list}\n\n"
        f"Session has been *auto-paused*. No new orders will be placed.\n"
        f"The system will *auto-heal* if positions are restored.\n\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"
    )
    return await _send_async(msg, key=f'guardian_violation_{session_id}')


async def alert_guardian_healed(
    session_id: str,
    pause_reason: str,
) -> bool:
    """Alert when guardian violation is resolved and session auto-resumes."""
    msg = (
        f"✅ *GUARDIAN HEALED — AUTO-RESUMED* — `{session_id}`\n\n"
        f"Guardian violation has resolved. Both sides have positions.\n"
        f"Was paused: `{pause_reason}`\n\n"
        f"Session has been *auto-resumed* and will continue trading.\n\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"
    )
    return await _send_async(msg, key=f'guardian_healed_{session_id}')


async def alert_stale_monitor(
    session_id: str,
    my_gen: int,
    stored_gen: int,
    context: str = 'pre-heartbeat',
) -> bool:
    """CRITICAL: Alert when a stale monitor is detected placing phantom orders.

    A stale monitor is an old bot instance that is still running after a newer
    instance has taken over. It places SELL orders on the exchange but cannot
    persist state — creating ghost positions the bot has no record of.
    Max loss, lot limits, and position tracking are ALL blind to these.
    """
    msg = (
        f"🚨 *STALE MONITOR — GHOST ORDERS PLACED* — session `{session_id}`\n\n"
        f"A stale bot instance (gen=*{my_gen}*) was running while a newer instance "
        f"(gen=*{stored_gen}*) had already taken over.\n\n"
        f"The stale monitor placed SELL orders on the exchange that it could NOT persist — "
        f"creating phantom (untracked) positions.\n\n"
        f"Context: `{context}`\n"
        f"⛔ Stale monitor has been *automatically stopped*.\n\n"
        f"⚠️ *IMMEDIATE ACTION REQUIRED*: Check exchange positions vs bot dashboard. "
        f"Ghost positions are NOT tracked by max loss or lot limits.\n\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"
    )
    return await _send_async(msg, key=f'stale_monitor_{session_id}_{my_gen}')


async def alert_ghost_positions_growing(
    session_id: str,
    side: str,
    strike: float,
    lots: float,
) -> bool:
    """Alert when reconciler detects growing untracked positions on the exchange.

    Ghost positions are NOT tracked by the bot — max loss and lot limits are
    blind to them. Growing lot count means a stale monitor or external algo is
    actively adding shorts that the session cannot account for.
    """
    msg = (
        f"🚨 *GHOST POSITIONS GROWING* — session `{session_id}`\n\n"
        f"Exchange now has *{int(lots)} lots* of {side} @ {int(strike)} strike "
        f"that this session has NO record of.\n\n"
        f"⚠️ *These positions are NOT tracked* — max loss, lot limits, and P&L "
        f"calculations are all BLIND to them.\n\n"
        f"Possible causes:\n"
        f"• Stale bot instance still running\n"
        f"• External algo or manual trade\n\n"
        f"*MANUAL REVIEW REQUIRED* — Check exchange positions immediately.\n\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"
    )
    return await _send_async(msg, key=f'ghost_positions_{session_id}_{side}_{int(strike)}')


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


async def alert_both_sides_closed_awake(
    session_id: str,
    pnl: float,
) -> bool:
    """Alert when both CE and PE reach 0 lots during user awake hours (8AM-11PM IST).
    Session is kept running — no auto-stop during awake hours."""
    msg = f"""🔔 *MMM ALL POSITIONS CLOSED — ACTION NEEDED*

🤖 Session: `{session_id}`
✅ Both CE and PE sides are now at *0 lots*.

⏳ *Session is STILL RUNNING* — you are in active hours (8AM–11PM IST).

📋 *Next steps (manual action required):*
  • Enter fresh positions to start a new round, OR
  • Stop the session manually from the dashboard.

💰 Net P\\&L: *${pnl:+.2f}*

⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    return await _send_async(msg, f"both_sides_closed_awake_{session_id}")


async def alert_offhours_unhedged_stop(
    session_id: str,
    closed_side: str,
    open_side: str,
    open_lots: int,
    pnl: float,
) -> bool:
    """Alert when session auto-stops after 11PM IST: one side eliminated,
    replenish failed — unhedged exposure with user asleep is unsafe."""
    msg = f"""🛑 *MMM AUTO-STOPPED — OFF-HOURS UNHEDGED EXPOSURE*

🤖 Session: `{session_id}`
⚠️ *{closed_side.upper()}* fully closed (0 lots).
📊 *{open_side.upper()}* has *{open_lots} lot(s)* — unhedged.
🔄 Auto-replenish failed — cannot restore hedged exposure.

⏰ *Outside active hours (8AM–11PM IST): session stopped automatically.*

💰 Net P\\&L at stop: *${pnl:+.2f}*

_Session requires manual restart._
⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    return await _send_async(msg, f"offhours_unhedged_stop_{session_id}")


async def alert_active_hours_unhedged_pause(
    session_id: str,
    closed_side: str,
    open_side: str,
    open_lots: int,
    pnl: float,
    details: dict = None,
) -> bool:
    """HIGH-PRIORITY alert: one leg wiped during active hours (8AM-11PM IST).
    Session is PAUSED — human decision required. No auto-stop was triggered."""
    details = details or {}
    open_strike = details.get('open_strike', 0)
    detected_at = details.get('detected_at_ist', datetime.now(timezone.utc).strftime('%H:%M UTC'))

    strike_line = f'\n📍 Open strike: *{open_strike}*' if open_strike else ''
    pnl_color = '🟢' if pnl >= 0 else '🔴'

    msg = f"""🚨 *HUMAN ACTION REQUIRED — SESSION PAUSED* 🚨

🤖 Session: `{session_id}`
⏰ Detected: *{detected_at}* (active hours)

❌ *{closed_side.upper()}* fully closed — *0 lots remaining*
⚠️ *{open_side.upper()}* has *{open_lots} lot(s)* — UNHEDGED exposure{strike_line}
🔄 Auto-replenish failed — hedge not restored

{pnl_color} P\\&L at pause: *${pnl:+.2f}*

*No auto-stop — you are in active hours.*
Bot is PAUSED. No new trades will execute.

📋 *Action required (choose one):*
  • Close {open_side.upper()} positions manually, OR
  • Re-enter {closed_side.upper()} at a new strike to restore hedge, OR
  • Stop the session from the dashboard.

⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"""

    return await _send_async(msg, f"activehours_unhedged_pause_{session_id}")


async def alert_god_correction(
    session_id: str,
    aggressor: str,
    pnl_drift: float,
    minutes_inactive: float,
) -> bool:
    """Alert when the God Layer fires a corrective adjustment.

    God fires when PNL has drifted significantly AND the algo has been inactive
    (no executed adjustments) — indicating soft guards were blocking the hedge.
    This is an informational alert, not an emergency — God is self-correcting.
    """
    drift_color = '🔴' if pnl_drift < -100 else '🟡'
    msg = (
        f"🌐 *GOD LAYER CORRECTION* — `{session_id}`\n\n"
        f"Strategic drift detected — soft guards blocked the hedge for too long.\n\n"
        f"📊 *Aggressor*: `{aggressor.upper()}`\n"
        f"{drift_color} *PNL drift*: `${pnl_drift:+.2f}` over window\n"
        f"⏱ *Inactive for*: `{minutes_inactive:.0f} min` (no executed adjustments)\n\n"
        f"God layer placed a corrective hedge in *god\\_mode* (bypassed soft guards).\n"
        f"Session is *continuing normally* — no action required.\n\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M:%S')} UTC"
    )
    return await _send_async(msg, key=f'god_correction_{session_id}')
