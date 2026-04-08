"""
MMMX Telegram Alerts — Async Alert Dispatcher with Dedup

Sends Telegram notifications for critical MMMX events.
Spec: MMMX_IMPLEMENTATION_PLAN.md Section 1 (mmmx_telegram.py).

Features:
  - Dedup window: same alert type within TELEGRAM_DEDUP_TTL seconds is suppressed.
  - Falls back to MMM telegram infra (TelegramNotifier) for actual sending.
  - All messages prefixed [MMMX] to distinguish from MMM alerts.
  - No-op if Telegram not configured (test-safe).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from .mmmx_constants import TELEGRAM_TAG, TELEGRAM_DEDUP_TTL

log = logging.getLogger('mmmx_telegram')

_notifier = None
_last_sent: Dict[str, float] = {}
_dedup_lock = __import__('threading').Lock()


def _get_credentials():
    try:
        from config.loader import get_config
        cfg = get_config()
        tg = getattr(cfg, 'telegram', None)
        token = (
            getattr(tg, 'live_bot_token', None)
            or getattr(tg, 'bot_token', None)
            or ''
        )
        chat_id = (
            getattr(tg, 'live_chat_id', None)
            or getattr(tg, 'chat_id', None)
            or ''
        )
        return str(token), str(chat_id)
    except Exception:
        return '', ''


def _get_notifier():
    global _notifier
    if _notifier is not None:
        return _notifier
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        log.debug("MMMX Telegram not configured — alerts disabled")
        return None
    try:
        from webui.backend.services.notifications import TelegramNotifier
        _notifier = TelegramNotifier(token, chat_id)
        return _notifier
    except ImportError:
        try:
            from ...services.notifications import TelegramNotifier
            _notifier = TelegramNotifier(token, chat_id)
            return _notifier
        except Exception:
            return None


def _dedup_key(alert_type: str, session_id: Optional[str]) -> str:
    raw = f"{alert_type}:{session_id or 'global'}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _is_deduped(key: str, ttl: int = TELEGRAM_DEDUP_TTL) -> bool:
    with _dedup_lock:
        last = _last_sent.get(key, 0)
        if time.monotonic() - last < ttl:
            return True
        _last_sent[key] = time.monotonic()
        return False


async def send_alert_async(
    message: str,
    alert_type: str = 'info',
    session_id: Optional[str] = None,
    dedup_ttl: int = TELEGRAM_DEDUP_TTL,
) -> None:
    """
    Send a Telegram message (async). Suppressed if dedup window active.

    alert_type is used as the dedup key — same type + session won't re-fire
    within dedup_ttl seconds.
    """
    key = _dedup_key(alert_type, session_id)
    if _is_deduped(key, dedup_ttl):
        log.debug(f"MMMX Telegram deduped: {alert_type}")
        return

    notifier = _get_notifier()
    if notifier is None:
        log.debug(f"MMMX Telegram (no-op): {message[:80]}")
        return

    sid_tag = f"[{session_id[:8]}] " if session_id else ""
    full_msg = f"{TELEGRAM_TAG} {sid_tag}{message}"

    try:
        await notifier.send_message(full_msg)
    except Exception as exc:
        log.error(f"MMMX Telegram send failed: {exc}")


def send_alert(
    message: str,
    alert_type: str = 'info',
    session_id: Optional[str] = None,
    dedup_ttl: int = TELEGRAM_DEDUP_TTL,
) -> None:
    """
    Synchronous wrapper — fires the async send in a new event loop or existing one.
    Safe to call from sync monitor code.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule as a fire-and-forget coroutine
            asyncio.ensure_future(
                send_alert_async(message, alert_type, session_id, dedup_ttl)
            )
        else:
            loop.run_until_complete(
                send_alert_async(message, alert_type, session_id, dedup_ttl)
            )
    except Exception as exc:
        log.error(f"MMMX Telegram sync wrapper failed: {exc}")


# ── Typed alert helpers ────────────────────────────────────────────────────────

def alert_hard_stop(session_id: str, total_pnl: float, hard_stop_usd: float) -> None:
    send_alert(
        f"🔴 HARD STOP fired. P&L={total_pnl:.2f} USD, limit={hard_stop_usd:.2f} USD. "
        "All positions closing. Session → COMPLETE.",
        alert_type='hard_stop',
        session_id=session_id,
        dedup_ttl=300,
    )


def alert_dte_close(session_id: str, dte: float) -> None:
    send_alert(
        f"⏰ DTE CLOSE: {dte:.1f} days remaining. Closing all shorts.",
        alert_type='dte_close',
        session_id=session_id,
        dedup_ttl=300,
    )


def alert_atm_shield(session_id: str, side: str, old_strike: float, new_strike: float) -> None:
    send_alert(
        f"🛡️ ATM Shield fired ({side.upper()}): {old_strike} → {new_strike}.",
        alert_type=f'atm_shield_{side}',
        session_id=session_id,
        dedup_ttl=60,
    )


def alert_atm_shield_aborted(session_id: str, side: str, reason: str) -> None:
    send_alert(
        f"🚨 CRITICAL: ATM Shield ABORTED ({side.upper()}). Position remains. Reason: {reason}",
        alert_type=f'atm_shield_abort_{side}',
        session_id=session_id,
        dedup_ttl=60,
    )


def alert_naked_position(session_id: str, tranche_id, side: str, since: str, retries: int) -> None:
    send_alert(
        f"🚨 CRITICAL: Naked position Tr{tranche_id}/{side.upper()} since {since} "
        f"(retries={retries}). Session PAUSED.",
        alert_type=f'naked_{tranche_id}_{side}',
        session_id=session_id,
        dedup_ttl=120,
    )


def alert_stale_monitor(session_id: str, my_gen: int, stored_gen: int) -> None:
    send_alert(
        f"⚠️ Stale monitor self-stopped: my_gen={my_gen}, stored_gen={stored_gen}.",
        alert_type='stale_monitor',
        session_id=session_id,
        dedup_ttl=60,
    )


def alert_tranche_deployed(session_id: str, tranche_id, total_lots: int) -> None:
    send_alert(
        f"✅ Tr{tranche_id} deployed. Total lots: {total_lots}.",
        alert_type=f'tranche_deploy_{tranche_id}',
        session_id=session_id,
        dedup_ttl=10,
    )


def alert_deployment_queue(session_id: str, queue_size: int, move_pct: float) -> None:
    send_alert(
        f"📋 Deployment queue: {queue_size} tranches eligible ({move_pct:.1f}% move detected).",
        alert_type='deployment_queue',
        session_id=session_id,
        dedup_ttl=60,
    )


def alert_circuit_breaker_open(session_id: str) -> None:
    send_alert(
        "🔌 Circuit breaker OPEN. Exchange API unreachable. Session PAUSED, listener active.",
        alert_type='circuit_breaker_open',
        session_id=session_id,
        dedup_ttl=120,
    )


def alert_session_complete(session_id: str, reason: str, final_pnl: float) -> None:
    send_alert(
        f"✅ Session COMPLETE. Reason: {reason}. Final P&L: {final_pnl:.2f} USD.",
        alert_type='session_complete',
        session_id=session_id,
        dedup_ttl=300,
    )


def alert_whipsaw(session_id: str, level: str, score: int) -> None:
    messages = {
        'CAUTION':  f"⚠️ Whipsaw CAUTION (score {score}): market oscillating. "
                    "Deployment triggers widened +50%.",
        'RESTRICT': f"⚠️ Whipsaw RESTRICT (score {score}): repeated oscillation. "
                    "Triggers widened +100%, lot size halved.",
        'COOLDOWN': f"🛑 Whipsaw COOLDOWN (score {score}): pausing new deployments "
                    "for 1 hour to let noise settle.",
        'NORMAL':   f"✅ Whipsaw score decayed to {score}. "
                    "Resuming normal deployment.",
    }
    msg = messages.get(level, f"Whipsaw level={level}, score={score}")
    send_alert(
        msg,
        alert_type=f'whipsaw_{level.lower()}',
        session_id=session_id,
        dedup_ttl=300,
    )


def alert_profit_booking(session_id: str, tranche_id, pnl_usd: float) -> None:
    send_alert(
        f"💰 Profit booking: Tr{tranche_id} closed at +${pnl_usd:.2f} USD.",
        alert_type=f'profit_booking_{tranche_id}',
        session_id=session_id,
        dedup_ttl=60,
    )


def alert_queue_retrace(session_id: str, retrace_pct: float, queue_size: int) -> None:
    send_alert(
        f"🔄 Deployment queue cleared: retracement {retrace_pct:.2f}% detected "
        f"({queue_size} tranches removed).",
        alert_type='queue_retrace',
        session_id=session_id,
        dedup_ttl=120,
    )
