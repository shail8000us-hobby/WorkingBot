"""
Patience Executor — card → GCD schedule → patience_loop handoff.

Called by patience_trigger when a card is TRIGGERED.
Handles:
  1. Pre-fire checks (guardian, portfolio Greeks, price freshness)
  2. Relative strike resolution (ATM offset → absolute strike)
  3. Symbol construction (option_type + strike + expiry → exchange symbol)
  4. GCD schedule computation
  5. patience_loop start + monitoring
  6. On completion: auto-group positions, arm child cards, Telegram

Created: March 14, 2026
"""

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── WebSocket reference ───────────────────────────────────────────────
_socketio = None


def init_socketio(sio):
    global _socketio
    _socketio = sio


def _emit(event: str, data: dict):
    """Emit WebSocket event if socketio is wired up. Fails silently."""
    if _socketio is not None:
        try:
            _socketio.emit(event, data, namespace='/')
        except Exception as e:
            log.debug(f"patience_executor: ws emit failed: {e}")


# Eventlet-safe real OS thread
try:
    from eventlet.patcher import original as _ep_original
    _RealThread = _ep_original('threading').Thread
except (ImportError, AttributeError):
    _RealThread = threading.Thread


# ── Guardian ──────────────────────────────────────────────────────────

GUARDIAN_PATH = Path(__file__).parent.parent / 'data' / 'guardian_signal.json'


def _check_guardian() -> str:
    """Read guardian_signal.json. Returns 'GO' if absent/unreadable (fail open)."""
    try:
        if not GUARDIAN_PATH.exists():
            return 'GO'
        data = json.loads(GUARDIAN_PATH.read_text())
        return 'STOP' if data.get('signal') == 'STOP' else 'GO'
    except Exception:
        return 'GO'  # corrupt file → fail open, don't block trading


# ── Symbol builder ────────────────────────────────────────────────────

def _leg_to_symbol(leg: dict) -> str:
    """
    Build Delta Exchange option symbol from leg fields.

    Delta Exchange format: C-BTC-75200-170326
        C/P = CE/PE
        BTC = asset (hardcoded for now)
        75200 = strike (int)
        170326 = ddmmyy from expiry_date 'YYYY-MM-DD'  (DDMMYY format confirmed by live data)
    """
    prefix = 'C' if leg.get('option_type') == 'CE' else 'P'
    strike = int(float(leg.get('strike', 0)))
    expiry_date = leg.get('expiry_date', '')   # 'YYYY-MM-DD'

    if expiry_date and len(expiry_date) >= 10:
        parts = expiry_date.split('-')
        # ddmmyy: day(2)+month(2)+year(2 last digits) — Delta Exchange DDMMYY format
        ddmmyy = parts[2].zfill(2) + parts[1].zfill(2) + parts[0][2:]
    else:
        log.error(f"patience_executor: invalid expiry_date '{expiry_date}' for leg {leg.get('leg_id')}")
        ddmmyy = 'XXXXXX'

    return f"{prefix}-BTC-{strike}-{ddmmyy}"


# ── ATM / relative strike resolution ─────────────────────────────────

async def _resolve_relative_strike(leg: dict, spot_price: float) -> float:
    """
    Resolve relative strike (ATM ± offset) to nearest valid absolute strike.

    For simplicity in Phase 1: ATM = round(spot_price / 100) * 100 (nearest 100),
    then add relative_offset. Phase 3 will refine by querying live chain.
    """
    offset = float(leg.get('relative_offset') or 0)
    atm = round(spot_price / 100) * 100
    return float(atm + offset)


async def _resolve_strikes(legs: list, spot_price: float) -> list:
    """Resolve all relative strikes in legs. Returns legs with 'strike' set."""
    resolved = []
    for leg in legs:
        if leg.get('is_relative_strike'):
            strike = await _resolve_relative_strike(leg, spot_price)
            resolved.append({**leg, 'strike': strike})
            log.info(
                f"patience_executor: resolved relative strike "
                f"ATM+{leg.get('relative_offset', 0)} = {strike} for leg {leg.get('leg_id')}"
            )
        else:
            resolved.append(leg)
    return resolved


# ── Portfolio Greeks check ────────────────────────────────────────────

MAX_PORTFOLIO_DELTA = int(os.environ.get('PATIENCE_MAX_PORTFOLIO_DELTA', '500'))


def _check_greeks_ok(card: dict, legs: list, spot_price: float) -> tuple:
    """
    Check portfolio delta won't breach limit after adding this card's legs.

    Returns:
        (ok: bool, total_delta: float)
    """
    try:
        from webui.backend.options_strategy.position_greeks import enrich_positions_with_greeks
        from webui.backend.routes.options.options_control import get_cached_positions

        # Get current positions
        current = get_cached_positions(max_age=60) or []

        # Get estimated IV for synthetic positions (use DVOL as proxy)
        try:
            from webui.backend.services.patience_iv import get_patience_iv
            dvol_value = get_patience_iv().get_current_dvol()
            est_iv = float(dvol_value) if dvol_value else 70.0  # fallback 70%
        except Exception:
            est_iv = 70.0

        # Build synthetic positions for card legs.
        # enrich_positions_with_greeks reads: product_symbol, size (signed), iv
        # size: positive = long (BUY), negative = short (SELL)
        # delta already scaled inside enrich: delta * size * multiplier(0.001)
        # → do NOT double-multiply by 0.001 in aggregation below
        synthetic = []
        for leg in legs:
            direction_sign = 1 if leg.get('direction') == 'BUY' else -1
            synthetic.append({
                'product_symbol': _leg_to_symbol(leg),
                'size': direction_sign * int(leg.get('lots', 0)),
                'iv': est_iv,   # DVOL as IV proxy for pre-check estimate
            })

        all_pos = enrich_positions_with_greeks(current + synthetic, spot_price)

        # pos_greeks.delta is already fully scaled (delta * size * multiplier)
        # See position_greeks.py: delta = cg["delta"] * size * multiplier
        total_delta = sum(
            p.get('pos_greeks', {}).get('delta', 0)
            for p in all_pos
        )

        if abs(total_delta) > MAX_PORTFOLIO_DELTA:
            log.warning(
                f"patience_executor: Greeks check BLOCKED — "
                f"total_delta={total_delta:.1f} > limit={MAX_PORTFOLIO_DELTA}"
            )
            return False, total_delta

        return True, total_delta

    except Exception as e:
        log.warning(
            f"patience_executor: Greeks check failed ({e}) — proceeding (fail open)"
        )
        return True, 0.0  # fail open — advisory check


# ── Notification helper ───────────────────────────────────────────────

def _notify(msg: str):
    """Send Telegram alert (best effort — never block execution on failure)."""
    try:
        from webui.backend.routes.options.options_notifier import get_options_notifier
        get_options_notifier().send(msg)
    except Exception as e:
        log.warning(f"patience_executor: Telegram notify failed: {e}")


# ── Main execute_card ─────────────────────────────────────────────────

def execute_card(card_id: str):
    """
    Entry point called by patience_trigger when a card is TRIGGERED.

    Runs synchronously (called from trigger daemon thread).
    Starts patience_loop in its own thread for the actual order placement.
    """
    from webui.backend.routes.patience.patience_models import get_db
    from webui.backend.services.gcd_batch import compute_gcd_schedule, schedule_summary
    from webui.backend.services.patience_loop import get_patience_loop_service
    from webui.backend.services.delta_price_websocket import get_price_websocket

    db = get_db()
    card = db.get_card(card_id)
    if not card:
        log.error(f"patience_executor: card {card_id} not found")
        return

    legs = db.get_legs(card_id)
    if not legs:
        log.error(f"patience_executor: card {card_id} has no legs")
        db.update_card(card_id, status='PAUSED')
        db.log_event(card_id, None, 'PAUSE', 'No legs found on card')
        return

    card_name = card.get('card_name', card_id)

    # ── Pre-fire check 1: Guardian ────────────────────────────────────
    if _check_guardian() != 'GO':
        db.update_card(card_id, status='PAUSED')
        db.log_event(card_id, None, 'PAUSE', 'Guardian signal is STOP')
        _notify(f"Patience: [{card_name}] blocked — Guardian signal is STOP.")
        log.warning(f"patience_executor: [{card_name}] blocked by Guardian")
        _release_execution_lock(card_id)
        return

    # ── Pre-fire check 2: Price feed ──────────────────────────────────
    spot = get_price_websocket().get_price('BTC')
    if spot is None:
        db.update_card(card_id, status='PAUSED')
        db.log_event(card_id, None, 'PAUSE', 'BTC price feed unavailable')
        _notify(f"Patience: [{card_name}] PAUSED — BTC price feed unavailable.")
        _release_execution_lock(card_id)
        return

    # ── Pre-fire check 3: Resolve relative strikes ────────────────────
    try:
        loop = asyncio.new_event_loop()
        try:
            resolved_legs = loop.run_until_complete(_resolve_strikes(legs, spot))
        finally:
            loop.close()
            # Do NOT call asyncio.set_event_loop(loop) — the loop is closed and
            # setting it would leave the thread's event loop reference pointing at
            # a closed object, breaking any subsequent asyncio usage in this thread.
    except Exception as e:
        db.update_card(card_id, status='PAUSED')
        db.log_event(card_id, None, 'PAUSE', f'Strike resolution failed: {e}')
        _notify(f"Patience: [{card_name}] PAUSED — Strike resolution error: {e}")
        _release_execution_lock(card_id)
        return

    # ── Pre-fire check 4: Portfolio Greeks ───────────────────────────
    greeks_ok, total_delta = _check_greeks_ok(card, resolved_legs, spot)
    if not greeks_ok:
        db.update_card(card_id, status='PAUSED')
        db.log_event(
            card_id, None, 'GREEKS_BLOCKED',
            f'Portfolio delta would be {total_delta:.0f} (limit {MAX_PORTFOLIO_DELTA})',
            {'total_delta': total_delta, 'limit': MAX_PORTFOLIO_DELTA}
        )
        _notify(
            f"Patience: [{card_name}] would push portfolio delta to "
            f"{total_delta:+.0f}. Paused for review."
        )
        _release_execution_lock(card_id)
        return

    # ── Compute execution schedule (GCD or flat single-round) ─────────
    use_gcd = bool(card.get('use_gcd', 1))
    if use_gcd:
        try:
            schedule = compute_gcd_schedule(resolved_legs)
        except ValueError as e:
            db.update_card(card_id, status='PAUSED')
            db.log_event(card_id, None, 'PAUSE', f'GCD schedule error: {e}')
            _notify(f"Patience: [{card_name}] PAUSED — GCD error: {e}")
            _release_execution_lock(card_id)
            return
    else:
        # Flat: execute all lots in a single round, no GCD splitting
        schedule = {
            'gcd': 1,
            'total_rounds': 1,
            'per_round': [{**leg, 'lots_this_round': leg.get('lots', 1)} for leg in resolved_legs],
        }
        log.info(f"patience_executor: [{card_name}] GCD disabled — flat single-round execution")

    summary = schedule_summary(schedule)
    total_rounds = schedule['total_rounds']
    per_round = schedule['per_round']

    # ── Build orders list for patience_loop ───────────────────────────
    # One entry per leg per round. patience_loop executes total_rounds rounds,
    # each round places per_round orders (lots_this_round per leg).
    orders = []
    for leg in per_round:
        sym = _leg_to_symbol(leg)
        side = 'buy' if leg.get('direction') == 'BUY' else 'sell'
        orders.append({
            'symbol': sym,
            'size': float(leg.get('lots_this_round', 1)),
            'side': side,
            'leg_id': leg.get('leg_id'),
            'order_mode': leg.get('order_mode', 'maker_only'),
        })

    # ── Mark as EXECUTING ─────────────────────────────────────────────
    db.update_card(card_id, status='EXECUTING', triggered_at=datetime.utcnow().isoformat())
    db.log_event(
        card_id, None, 'TRIGGER_HIT',
        f"Executing {len(resolved_legs)} legs, {total_rounds} GCD rounds. {summary}",
        {'schedule_summary': summary, 'total_rounds': total_rounds, 'spot': spot}
    )

    _notify(
        f"Patience: [{card_name}] TRIGGERED at BTC {spot:,.0f}. "
        f"Executing {len(resolved_legs)} legs, {total_rounds} GCD rounds."
    )

    log.info(f"patience_executor: [{card_name}] starting patience_loop. {summary}")

    # ── Start patience_loop ───────────────────────────────────────────
    loop_svc = get_patience_loop_service()

    def on_round_complete(loop_id, round_num, progress):
        """Called by patience_loop after each GCD round fills."""
        fills = []
        for sym, info in progress.items():
            if info.get('filled'):
                leg_id = info.get('leg_id')
                fill_price = info.get('fillPrice')
                order_id = info.get('orderId')
                fills.append(f"{sym} @ {fill_price} (order:{order_id})")

                # Update leg status in DB — only write fill_price if it's valid
                if leg_id:
                    leg_update = {
                        'status': 'ROUND_FILLED',
                        'executed_symbol': sym,
                        'order_id': order_id,
                    }
                    if fill_price is not None:
                        leg_update['fill_price'] = fill_price
                    else:
                        log.warning(
                            f"patience_executor: fill_price missing for leg {leg_id} "
                            f"({sym}, order:{order_id}) — will retry after completion"
                        )
                    db.update_leg(leg_id, **leg_update)

        db.log_event(
            card_id, None, 'ROUND_COMPLETE',
            f"Round {round_num}/{total_rounds} complete: {', '.join(fills)}",
            {'round': round_num, 'fills': fills}
        )
        _notify(f"Patience: [{card_name}] Round {round_num}/{total_rounds} done. {', '.join(fills)}")
        _emit('patience_card_update', {
            'card_id': card_id,
            'event': 'round_complete',
            'round': round_num,
            'total_rounds': total_rounds,
            'fills': fills,
        })

    def on_card_pause(loop_id, error_msg):
        """Called when patience_loop exhausts retries."""
        db.update_card(card_id, status='PAUSED')
        db.log_event(card_id, None, 'PAUSE', f"Loop paused: {error_msg}")
        _notify(
            f"⚠️ Patience: [{card_name}] leg FAILED after {10} retries. "
            f"Card PAUSED. Check Web UI. Error: {error_msg}"
        )
        log.error(f"patience_executor: [{card_name}] PAUSED — {error_msg}")
        _emit('patience_card_update', {
            'card_id': card_id,
            'event': 'paused',
            'error': error_msg,
        })
        # Release execution lock in trigger
        _release_execution_lock(card_id)

    def on_complete(loop_id):
        """Called when all GCD rounds complete successfully."""
        _on_card_completed(card_id, card_name, resolved_legs)

    loop_svc.start_loop(
        loop_id=card_id,
        orders=orders,
        total_rounds=total_rounds,
        on_round_complete=on_round_complete,
        on_card_pause=on_card_pause,
        on_complete=on_complete,
    )


def _on_card_completed(card_id: str, card_name: str, resolved_legs: list):
    """
    Post-completion: mark COMPLETED, update legs, auto-group, arm children.
    Called from patience_loop's on_complete callback (inside real OS thread).
    """
    from webui.backend.routes.patience.patience_models import get_db

    db = get_db()

    # Mark all legs FILLED (loop already captured fill prices via on_round_complete)
    for leg in resolved_legs:
        leg_id = leg.get('leg_id')
        if leg_id:
            leg_data = db.get_leg(leg_id)
            if leg_data and leg_data.get('status') != 'HANDED_TO_MMM':
                if not leg_data.get('fill_price'):
                    log.error(
                        f"patience_executor: [{card_name}] leg {leg_id} "
                        f"({leg_data.get('executed_symbol', 'unknown')}) "
                        f"has NULL fill_price — NOT marking FILLED, leaving in ROUND_FILLED for manual review. "
                        f"Check exchange order {leg_data.get('order_id', 'unknown')}"
                    )
                    continue  # skip — don't mark FILLED without a fill price
                db.update_leg(
                    leg_id,
                    status='FILLED',
                    filled_at=datetime.utcnow().isoformat(),
                )

    # Mark card COMPLETED
    completed_at = datetime.utcnow().isoformat()
    db.update_card(card_id, status='COMPLETED', completed_at=completed_at)
    db.log_event(
        card_id, None, 'COMPLETE',
        f"All legs filled. Card completed at {completed_at}"
    )

    # Auto-write performance record (entry_premium only; pnl/exit_value set on explicit close)
    try:
        entry_premium = 0.0
        for leg in resolved_legs:
            leg_id = leg.get('leg_id')
            if leg_id:
                leg_data = db.get_leg(leg_id)
                if leg_data:
                    fill = float(leg_data.get('fill_price') or 0)
                    lots = int(leg_data.get('lots') or 0)
                    sign = 1 if leg_data.get('direction') == 'SELL' else -1
                    # Apply 0.001 BTC multiplier (1 lot = 0.001 BTC)
                    entry_premium += sign * fill * lots * 0.001
        if not db.get_performance_for_card(card_id):
            db.save_performance({
                'card_id':          card_id,
                'card_name':        card_name,
                'entry_premium':    round(entry_premium, 2),
                'exit_value':       None,
                'pnl':              None,
                'duration_hours':   None,
                'card_type':        'options',
                'legs_handed_to_mmm': 0,
                'handoff_pnl':      None,
                'closed_at':        None,
            })
    except Exception as _perf_err:
        log.warning(f"patience_executor: auto-performance write failed for {card_name}: {_perf_err}")

    # Auto-group via groups storage (direct import — no HTTP)
    group_id = _auto_group(card_id, card_name, resolved_legs)
    if group_id:
        db.update_card(card_id, group_id=group_id)

    # NOTE: Child card arming is handled by PatienceTrigger's main loop (WAITING → ARMED check)

    _notify(
        f"Patience: [{card_name}] COMPLETED ✅ All legs filled. "
        f"{'Grouped as ' + group_id + '. ' if group_id else ''}"
        f"Verify positions in UI, then set max loss manually."
    )

    log.info(f"patience_executor: [{card_name}] COMPLETED. group_id={group_id}")
    _emit('patience_card_update', {
        'card_id': card_id,
        'event': 'completed',
        'group_id': group_id,
    })

    # Release execution lock
    _release_execution_lock(card_id)


def _auto_group(card_id: str, card_name: str, resolved_legs: list) -> Optional[str]:
    """Create a position group for this card's legs and assign leg symbols. Returns group_id or None."""
    try:
        from webui.backend.routes.options.groups_api import get_groups_storage

        # Get primary expiry from first leg — convert to DDMMYY (matches Delta Exchange symbol suffix)
        expiry_date = resolved_legs[0].get('expiry_date', '') if resolved_legs else ''
        if expiry_date:  # 'YYYY-MM-DD' → 'DDMMYY' (e.g. 2026-03-17 → '170326')
            parts = expiry_date.split('-')
            expiry_key = parts[2].zfill(2) + parts[1].zfill(2) + parts[0][2:] if len(parts) == 3 else 'unknown'
        else:
            expiry_key = 'unknown'

        group_id = f"patience_{card_id[:8]}"
        storage = get_groups_storage()
        storage.create_group(
            expiry_key=expiry_key,
            group_id=group_id,
            name=f"Patience: {card_name}",
            color='#7c3aed',
        )

        # Assign each leg's symbol to the group
        for leg in resolved_legs:
            sym = _leg_to_symbol(leg)
            if 'XXXXXX' not in sym:
                leg_expiry_date = leg.get('expiry_date', expiry_date)
                if leg_expiry_date:
                    leg_parts = leg_expiry_date.split('-')
                    leg_expiry_key = leg_parts[2].zfill(2) + leg_parts[1].zfill(2) + leg_parts[0][2:] if len(leg_parts) == 3 else expiry_key
                else:
                    leg_expiry_key = expiry_key
                try:
                    storage.assign_symbol(leg_expiry_key, sym, group_id)
                except Exception as ae:
                    log.warning(f"patience_executor: assign_symbol failed for {sym}: {ae}")

        log.info(f"patience_executor: auto-grouped card {card_id} → group {group_id} (expiry_key={expiry_key})")
        return group_id
    except Exception as e:
        log.warning(f"patience_executor: auto-group failed: {e}")
        return None


# ── Execution lock (managed by trigger) ──────────────────────────────

_execution_lock_card_id: Optional[str] = None
_execution_lock_cb: Optional[callable] = None


def register_execution_lock_callback(cb):
    """Called by patience_trigger to register the 'advance queue' callback."""
    global _execution_lock_cb
    _execution_lock_cb = cb


def _release_execution_lock(card_id: str):
    """Notify trigger that this card's execution is done, advance queue."""
    global _execution_lock_card_id
    _execution_lock_card_id = None
    if _execution_lock_cb:
        try:
            _execution_lock_cb(card_id)
        except Exception as e:
            log.warning(f"patience_executor: execution lock callback error: {e}")
