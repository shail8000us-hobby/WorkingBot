"""
Patience API — Flask Blueprint for all Patience REST endpoints.

All routes under /api/patience/
Blueprint registered in app.py via: app.register_blueprint(patience_bp)

Created: March 14, 2026
"""

import logging
import requests
import time
from datetime import datetime
from flask import Blueprint, jsonify, request
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger(__name__)

patience_bp = Blueprint('patience', __name__, url_prefix='/api/patience')

# Thread pool for concurrent ticker fetches
_ticker_pool = ThreadPoolExecutor(max_workers=10)


# ── Helpers ───────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.utcnow().isoformat()


def _db():
    from .patience_models import get_db
    return get_db()


def _trigger():
    from webui.backend.services.patience_trigger import get_patience_trigger
    return get_patience_trigger()


def _ok(data: dict = None, **kwargs):
    return jsonify({'success': True, **(data or {}), **kwargs})


def _err(msg: str, status: int = 400):
    return jsonify({'success': False, 'error': msg}), status


# ═══════════════════════════════════════════════════════════════════════
# Engine status
# ═══════════════════════════════════════════════════════════════════════

@patience_bp.route('/status', methods=['GET'])
def engine_status():
    """GET /api/patience/status — trigger daemon status + live price."""
    try:
        status = _trigger().get_status()
        return _ok(status)
    except Exception as e:
        log.error(f"patience_api: /status error: {e}", exc_info=True)
        return _err(str(e), 500)


@patience_bp.route('/engine/status', methods=['GET'])
def engine_running():
    return _ok({'running': _trigger().is_running()})


@patience_bp.route('/engine/start', methods=['POST'])
def engine_start():
    from webui.backend.services.patience_trigger import init_patience_trigger
    init_patience_trigger()
    return _ok({'running': True})


@patience_bp.route('/engine/stop', methods=['POST'])
def engine_stop():
    _trigger().stop()
    return _ok({'running': False})


# ═══════════════════════════════════════════════════════════════════════
# Cards — CRUD
# ═══════════════════════════════════════════════════════════════════════

@patience_bp.route('/cards', methods=['GET'])
def list_cards():
    """GET /api/patience/cards?status=ARMED,WAITING"""
    db = _db()
    status_filter = request.args.get('status')
    if status_filter:
        statuses = [s.strip() for s in status_filter.split(',')]
        cards = db.get_cards_by_status(*statuses)
    else:
        cards = db.get_all_cards()

    # Enrich each card with its legs
    result = []
    for card in cards:
        card['legs'] = db.get_legs(card['card_id'])
        result.append(card)

    return _ok({'cards': result, 'count': len(result)})


@patience_bp.route('/cards', methods=['POST'])
def create_card():
    """
    POST /api/patience/cards
    Body: {card_name, trigger_price, trigger_type, trigger_tolerance?, sustain_minutes?,
           iv_percentile_min?, iv_percentile_max?, iv_lookback_days?,
           parent_card_id?, template_id?,
           legs: [{direction, option_type, expiry_date, strike?, lots, is_relative_strike?,
                   relative_offset?, post_only?, order_mode?, stop_loss?,
                   mmm_handoff_eligible?, leg_order?}],
           arm: bool (default false)}
    """
    body = request.get_json(silent=True) or {}

    if not body.get('card_name'):
        return _err('card_name is required')
    if not body.get('trigger_price'):
        return _err('trigger_price is required')
    if not body.get('trigger_type'):
        return _err('trigger_type is required (TOUCH|CROSS_UP|CROSS_DOWN|SUSTAIN)')
    if not body.get('legs'):
        return _err('legs are required (at least 1)')

    db = _db()
    try:
        card_data = {
            'card_name': body['card_name'],
            'trigger_price': float(body['trigger_price']),
            'trigger_type': body['trigger_type'].upper(),
            'trigger_tolerance': float(body.get('trigger_tolerance', 50)),
            'sustain_minutes': body.get('sustain_minutes'),
            'iv_percentile_min': body.get('iv_percentile_min'),
            'iv_percentile_max': body.get('iv_percentile_max'),
            'iv_lookback_days': int(body.get('iv_lookback_days', 30)),
            'parent_card_id': body.get('parent_card_id'),
            'template_id': body.get('template_id'),
            'use_gcd': body.get('use_gcd', True),
            'status': 'DRAFT',
        }

        card_id = db.create_card(card_data)

        # Create legs
        legs_data = body.get('legs', [])
        for i, leg in enumerate(legs_data):
            if not leg.get('direction'):
                return _err(f"Leg {i + 1}: direction is required (BUY|SELL)")
            if not leg.get('option_type'):
                return _err(f"Leg {i + 1}: option_type is required (CE|PE)")
            if not leg.get('expiry_date'):
                return _err(f"Leg {i + 1}: expiry_date is required (YYYY-MM-DD)")
            if not leg.get('lots'):
                return _err(f"Leg {i + 1}: lots is required")

            leg['leg_order'] = leg.get('leg_order', i)
            db.create_leg(leg, card_id)

        # Auto-arm if requested
        if body.get('arm'):
            _arm_card_internal(db, card_id)

        card = db.get_card(card_id)
        card['legs'] = db.get_legs(card_id)
        return jsonify({'success': True, 'card': card}), 201

    except Exception as e:
        log.error(f"patience_api: create_card error: {e}", exc_info=True)
        return _err(str(e), 500)


@patience_bp.route('/cards/<card_id>', methods=['GET'])
def get_card(card_id):
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)
    card['legs'] = db.get_legs(card_id)
    return _ok({'card': card})


@patience_bp.route('/cards/<card_id>', methods=['PUT'])
def update_card(card_id):
    """
    PUT /api/patience/cards/<card_id>
    Allowed for ARMED cards (no cancel-recreate needed).
    Body: same as POST (all fields optional, legs replaces all existing legs if provided).
    """
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)

    # Can only edit non-terminal cards
    if card.get('status') in ('COMPLETED', 'CANCELLED'):
        return _err(f"Cannot edit card in status {card['status']}")

    body = request.get_json(silent=True) or {}

    updatable = ['card_name', 'trigger_price', 'trigger_type', 'trigger_tolerance',
                 'sustain_minutes', 'iv_percentile_min', 'iv_percentile_max',
                 'iv_lookback_days', 'parent_card_id', 'use_gcd']
    updates = {}
    for field in updatable:
        if field in body:
            val = body[field]
            if field in ('trigger_price', 'trigger_tolerance',
                         'iv_percentile_min', 'iv_percentile_max') and val is not None:
                val = float(val)
            elif field in ('iv_lookback_days',) and val is not None:
                val = int(val)
            elif field == 'trigger_type' and val:
                val = val.upper()
            updates[field] = val

    if updates:
        db.update_card(card_id, **updates)

    # Replace legs if provided
    if 'legs' in body:
        legs_data = body['legs']
        for i, leg in enumerate(legs_data):
            leg['leg_order'] = leg.get('leg_order', i)
        db.replace_legs(card_id, legs_data)

    card = db.get_card(card_id)
    card['legs'] = db.get_legs(card_id)
    return _ok({'card': card})


@patience_bp.route('/cards/<card_id>/legs/<leg_id>', methods=['PATCH'])
def update_leg(card_id, leg_id):
    """
    PATCH /api/patience/cards/:card_id/legs/:leg_id

    Update individual leg fields (lots, expiry_date, order_mode).
    Only allowed when card is DRAFT or ARMED.
    """
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)

    if card.get('status') not in ('DRAFT', 'ARMED', 'PAUSED'):
        return _err(f"Cannot edit legs when card is {card['status']}. Must be DRAFT, ARMED, or PAUSED.")

    leg = db.get_leg(leg_id)
    if not leg or leg.get('card_id') != card_id:
        return _err('Leg not found in this card', 404)

    body = request.get_json(silent=True) or {}
    allowed = {'lots', 'expiry_date', 'order_mode', 'strike', 'direction', 'option_type', 'stop_loss'}
    updates = {}
    for field in allowed:
        if field in body:
            val = body[field]
            if field == 'lots' and val is not None:
                val = int(val)
                if val < 1:
                    return _err('Lots must be at least 1')
            elif field == 'strike' and val is not None:
                val = float(val)
            elif field == 'stop_loss' and val is not None:
                val = float(val) if val else None
            elif field == 'order_mode' and val:
                _valid = {'market_only', 'maker_first', 'ssr_standard', 'ssr_aggressive',
                          'ssr_conservative', 'maker_only', 'market'}  # legacy kept
                if val not in _valid:
                    return _err(f"Invalid order_mode: {val}. Valid: market_only, maker_first, ssr_standard, ssr_aggressive, ssr_conservative")
            updates[field] = val

    if not updates:
        return _err('No valid fields to update')

    db.update_leg(leg_id, **updates)
    log.info(f"patience_api: updated leg {leg_id} in card {card_id}: {updates}")

    # Return refreshed card with all legs
    card = db.get_card(card_id)
    card['legs'] = db.get_legs(card_id)
    return _ok({'card': card, 'updated_leg': leg_id, 'changes': updates})


@patience_bp.route('/cards/<card_id>/clone', methods=['POST'])
def clone_card(card_id):
    """
    POST /api/patience/cards/<card_id>/clone

    Duplicate a card (any status) as a fresh DRAFT.
    Optional body fields override the clone:
      - card_name      (default: "<original name> (copy)")
      - trigger_price
      - trigger_type
      - trigger_tolerance
      - arm            (bool, default false) — auto-arm the clone
    Legs are copied verbatim (strike, lots, expiry, mode) with execution
    state (fill_price, order_id, executed_symbol, filled_at) cleared.
    """
    db = _db()
    src = db.get_card(card_id)
    if not src:
        return _err('Card not found', 404)
    src_legs = db.get_legs(card_id)

    body = request.get_json(silent=True) or {}

    try:
        card_data = {
            'card_name':         body.get('card_name', src['card_name'] + ' (copy)'),
            'trigger_price':     float(body.get('trigger_price', src['trigger_price'])),
            'trigger_type':      body.get('trigger_type', src['trigger_type']).upper(),
            'trigger_tolerance': float(body.get('trigger_tolerance', src.get('trigger_tolerance', 50))),
            'sustain_minutes':   src.get('sustain_minutes'),
            'iv_percentile_min': src.get('iv_percentile_min'),
            'iv_percentile_max': src.get('iv_percentile_max'),
            'iv_lookback_days':  src.get('iv_lookback_days', 30),
            'use_gcd':           src.get('use_gcd', True),
            'parent_card_id':    None,
            'template_id':       src.get('template_id'),
            'status':            'DRAFT',
        }

        new_id = db.create_card(card_data)

        for i, leg in enumerate(src_legs):
            leg_data = {
                'direction':           leg['direction'],
                'option_type':         leg['option_type'],
                'expiry_date':         leg['expiry_date'],
                'strike':              leg.get('strike'),
                'lots':                leg['lots'],
                'is_relative_strike':  leg.get('is_relative_strike', 0),
                'relative_offset':     leg.get('relative_offset'),
                'post_only':           leg.get('post_only', 1),
                'order_mode':          leg.get('order_mode', 'maker_only'),
                'stop_loss':           leg.get('stop_loss'),
                'mmm_handoff_eligible': leg.get('mmm_handoff_eligible', 0),
                'leg_order':           leg.get('leg_order', i),
            }
            db.create_leg(leg_data, new_id)

        if body.get('arm'):
            _arm_card_internal(db, new_id)

        new_card = db.get_card(new_id)
        new_card['legs'] = db.get_legs(new_id)
        log.info(f"patience_api: cloned card {card_id} → {new_id} ({new_card['card_name']})")
        return jsonify({'success': True, 'card': new_card}), 201

    except Exception as e:
        log.error(f"patience_api: clone_card error: {e}", exc_info=True)
        return _err(str(e), 500)


@patience_bp.route('/cards/<card_id>', methods=['DELETE'])
def delete_card(card_id):
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)
    if card.get('status') in ('EXECUTING',):
        return _err('Cannot delete a card that is currently executing')
    db.delete_card(card_id)
    return _ok({'deleted': card_id})


# ═══════════════════════════════════════════════════════════════════════
# Card lifecycle
# ═══════════════════════════════════════════════════════════════════════

def _arm_card_internal(db, card_id: str):
    """Internal: set card to ARMED or WAITING (depending on parent)."""
    card = db.get_card(card_id)
    parent_id = card.get('parent_card_id')
    if parent_id:
        parent = db.get_card(parent_id)
        if parent and parent.get('status') != 'COMPLETED':
            db.update_card(card_id, status='WAITING')
            return 'WAITING'
    db.update_card(card_id, status='ARMED')
    return 'ARMED'


@patience_bp.route('/cards/<card_id>/arm', methods=['POST'])
def arm_card(card_id):
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)
    if card.get('status') not in ('DRAFT', 'PAUSED', 'WAITING'):
        return _err(f"Cannot arm card in status {card['status']}")

    new_status = _arm_card_internal(db, card_id)
    card = db.get_card(card_id)
    card['legs'] = db.get_legs(card_id)

    # Telegram alert
    try:
        from webui.backend.routes.options.options_notifier import get_options_notifier
        t_price = card.get('trigger_price', 0)
        t_type = card.get('trigger_type', '')
        iv_max = card.get('iv_percentile_max')
        iv_str = f" + IV ≤ {iv_max}%" if iv_max else ""
        get_options_notifier().send(
            f"Patience: [{card.get('card_name')}] {new_status}. "
            f"Trigger: BTC {t_type} {t_price:,.0f}{iv_str}"
        )
    except Exception:
        pass

    return _ok({'card': card, 'status': new_status})


@patience_bp.route('/cards/<card_id>/disarm', methods=['POST'])
def disarm_card(card_id):
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)
    if card.get('status') not in ('ARMED', 'WAITING', 'TRIGGERED'):
        return _err(f"Cannot disarm card in status {card['status']}")
    db.update_card(card_id, status='DRAFT')
    card = db.get_card(card_id)
    return _ok({'card': card})


@patience_bp.route('/cards/<card_id>/pause', methods=['POST'])
def pause_card(card_id):
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)
    db.update_card(card_id, status='PAUSED')
    db.log_event(card_id, None, 'PAUSE', 'Manually paused by user')
    # Stop any running execution loop to prevent further orders
    try:
        from webui.backend.services.patience_loop import get_patience_loop_service
        get_patience_loop_service().stop_loop(card_id)
    except Exception as e:
        log.warning(f"pause_card: could not stop loop for {card_id}: {e}")
    return _ok({'card': db.get_card(card_id)})


@patience_bp.route('/cards/<card_id>/resume', methods=['POST'])
def resume_card(card_id):
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)
    if card.get('status') != 'PAUSED':
        return _err(f"Card is not PAUSED (status: {card['status']})")
    new_status = _arm_card_internal(db, card_id)
    return _ok({'card': db.get_card(card_id), 'status': new_status})


@patience_bp.route('/cards/<card_id>/cancel', methods=['POST'])
def cancel_card(card_id):
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)
    if card.get('status') in ('COMPLETED', 'CANCELLED'):
        return _err(f"Card already in terminal status {card['status']}")
    db.update_card(card_id, status='CANCELLED')
    db.log_event(card_id, None, 'PAUSE', 'Manually cancelled by user')
    # Stop any running execution loop immediately to prevent further orders
    try:
        from webui.backend.services.patience_loop import get_patience_loop_service
        get_patience_loop_service().stop_loop(card_id)
    except Exception as e:
        log.warning(f"cancel_card: could not stop loop for {card_id}: {e}")
    return _ok({'cancelled': card_id})


@patience_bp.route('/cards/<card_id>/execute-now', methods=['POST'])
def execute_now(card_id):
    """
    Execute card immediately, bypassing trigger conditions.
    Still runs guardian + Greeks checks for safety.
    Card must be DRAFT, ARMED, or PAUSED.
    """
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)

    status = card.get('status')
    if status not in ('DRAFT', 'ARMED', 'PAUSED'):
        return _err(f"Can only execute NOW from DRAFT/ARMED/PAUSED status (current: {status})")

    # Mark as TRIGGERED and queue directly (bypasses price/IV gate checks)
    db.update_card(card_id, status='TRIGGERED')
    db.log_event(
        card_id, None, 'TRIGGER_HIT',
        'Manual immediate execution requested (bypassed trigger conditions)'
    )

    # Queue for execution via trigger
    try:
        trigger = _trigger()
        card_name = card.get('card_name', card_id)

        with trigger._exec_lock:
            if trigger._executing_card_id is None:
                # Nothing executing — start immediately
                trigger._executing_card_id = card_id
                log.info(f"patience_api: execute-now [{card_name}] starting immediately")
                trigger._start_execution_thread(card_id)
            else:
                # Queue it
                trigger._execution_queue.append(card)
                trigger._execution_queue.sort(key=lambda c: c.get('created_at', ''))
                log.info(
                    f"patience_api: execute-now [{card_name}] queued "
                    f"(position {len(trigger._execution_queue)})"
                )

        return _ok({
            'card_id': card_id,
            'status': 'TRIGGERED',
            'message': 'Execution started' if trigger._executing_card_id == card_id else 'Queued for execution'
        })
    except Exception as e:
        log.error(f"patience_api: execute-now error: {e}", exc_info=True)
        return _err(str(e), 500)


@patience_bp.route('/cards/<card_id>/close', methods=['POST'])
def close_card(card_id):
    """
    Close a COMPLETED card — record performance history, remove from active monitoring.
    Body (optional): {exit_value: float, card_type: str}
    """
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)
    if card.get('status') not in ('COMPLETED', 'PAUSED'):
        return _err(f"Can only close COMPLETED or PAUSED cards (status: {card['status']})")

    body = request.get_json(silent=True) or {}
    legs = db.get_legs(card_id)

    # Calculate entry premium from fills
    entry_premium = 0.0
    for leg in legs:
        fill = float(leg.get('fill_price') or 0)
        lots = int(leg.get('lots') or 0)
        sign = 1 if leg.get('direction') == 'SELL' else -1   # received premium if SELL
        entry_premium += sign * fill * lots

    # Legs handed to MMM
    mmm_count = sum(1 for l in legs if l.get('status') == 'HANDED_TO_MMM')

    created_at = card.get('created_at', _now())
    completed_at = card.get('completed_at', _now())
    try:
        from datetime import datetime as dt
        duration = (
            dt.fromisoformat(completed_at) - dt.fromisoformat(created_at)
        ).total_seconds() / 3600
    except Exception:
        duration = 0.0

    exit_value = float(body.get('exit_value', 0))
    pnl = exit_value - entry_premium if exit_value else None

    db.save_performance({
        'card_id': card_id,
        'card_name': card.get('card_name'),
        'entry_premium': entry_premium,
        'exit_value': exit_value,
        'pnl': pnl,
        'duration_hours': round(duration, 2),
        'card_type': body.get('card_type', 'unknown'),
        'legs_handed_to_mmm': mmm_count,
        'handoff_pnl': body.get('handoff_pnl'),
    })

    db.update_card(card_id, status='CANCELLED')  # remove from active monitoring
    return _ok({'closed': card_id, 'entry_premium': entry_premium, 'pnl': pnl})


# ═══════════════════════════════════════════════════════════════════════
# MMM Handoff
# ═══════════════════════════════════════════════════════════════════════

@patience_bp.route('/cards/<card_id>/legs/<leg_id>/handoff', methods=['POST'])
def handoff_leg(card_id, leg_id):
    """
    Mark a leg as HANDED_TO_MMM.
    Patience stops tracking it. MMM picks it up through its own position scanning.
    """
    db = _db()
    leg = db.get_leg(leg_id)
    if not leg or leg.get('card_id') != card_id:
        return _err('Leg not found on this card', 404)
    if not leg.get('mmm_handoff_eligible'):
        return _err('Leg is not marked as MMM handoff eligible')
    if leg.get('status') == 'HANDED_TO_MMM':
        return _err('Leg already handed to MMM')
    if leg.get('status') != 'FILLED':
        return _err(f"Can only hand off FILLED legs (status: {leg['status']})")

    card = db.get_card(card_id)

    # Get current fill price as handoff price (P&L recorded at this price)
    handoff_price = leg.get('fill_price')

    db.update_leg(leg_id, status='HANDED_TO_MMM')
    db.log_event(
        card_id, leg_id, 'MMM_HANDOFF',
        f"Leg handed to MMM at price {handoff_price}",
        {'handoff_price': handoff_price, 'symbol': _build_symbol_from_leg(leg)}
    )

    symbol = _build_symbol_from_leg(leg)
    try:
        from webui.backend.routes.options.options_notifier import get_options_notifier
        get_options_notifier().send(
            f"Patience: Leg [{leg.get('direction')} {leg.get('lots')} "
            f"{leg.get('option_type')} {leg.get('strike')}] "
            f"handed to MMM for active management. Card: [{card.get('card_name', card_id)}]"
        )
    except Exception:
        pass

    return _ok({
        'leg_id': leg_id,
        'status': 'HANDED_TO_MMM',
        'handoff_price': handoff_price,
        'symbol': symbol,
    })


def _build_symbol_from_leg(leg: dict) -> str:
    """Build exchange symbol string from leg dict."""
    prefix = 'C' if leg.get('option_type') == 'CE' else 'P'
    strike = int(float(leg.get('strike') or 0))
    expiry_date = leg.get('expiry_date', '')
    if expiry_date and len(expiry_date) >= 10:
        parts = expiry_date.split('-')
        ddmmyy = parts[2] + parts[1] + parts[0][2:]
    else:
        ddmmyy = 'XXXXXX'
    return f"{prefix}-BTC-{strike}-{ddmmyy}"


# ═══════════════════════════════════════════════════════════════════════
# Execution log
# ═══════════════════════════════════════════════════════════════════════

@patience_bp.route('/cards/<card_id>/log', methods=['GET'])
def get_execution_log(card_id):
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)
    events = db.get_log(card_id)
    return _ok({'card_id': card_id, 'events': events, 'count': len(events)})


# ═══════════════════════════════════════════════════════════════════════
# Templates
# ═══════════════════════════════════════════════════════════════════════

@patience_bp.route('/templates', methods=['GET'])
def list_templates():
    db = _db()
    return _ok({'templates': db.get_templates()})


@patience_bp.route('/templates', methods=['POST'])
def save_template():
    """
    POST /api/patience/templates
    Body: {template_name, trigger_type, trigger_tolerance?, iv_percentile_min?,
           iv_percentile_max?, iv_lookback_days?,
           legs: [{direction, option_type, lots, order_mode, mmm_handoff_eligible,
                   is_relative_strike, relative_offset?, stop_loss?}]}
    Note: trigger_price and expiry_date NOT saved (set fresh each cycle).
    """
    body = request.get_json(silent=True) or {}
    if not body.get('template_name'):
        return _err('template_name is required')
    if not body.get('legs'):
        return _err('legs are required')

    db = _db()
    template_id = db.save_template(body)
    tpl = db.get_template(template_id)
    return jsonify({'success': True, 'template': tpl}), 201


@patience_bp.route('/templates/<template_id>', methods=['GET'])
def get_template(template_id):
    db = _db()
    tpl = db.get_template(template_id)
    if not tpl:
        return _err('Template not found', 404)
    return _ok({'template': tpl})


@patience_bp.route('/templates/<template_id>', methods=['DELETE'])
def delete_template(template_id):
    db = _db()
    tpl = db.get_template(template_id)
    if not tpl:
        return _err('Template not found', 404)
    db.delete_template(template_id)
    return _ok({'deleted': template_id})


# ═══════════════════════════════════════════════════════════════════════
# IV Percentile (Phase 1 stubs — real data in Phase 2)
# ═══════════════════════════════════════════════════════════════════════

@patience_bp.route('/iv/current', methods=['GET'])
def iv_current():
    """Phase 1 stub. Phase 2: returns real DVOL percentile from Deribit."""
    try:
        from webui.backend.services.patience_iv import get_patience_iv
        iv_svc = get_patience_iv()
        percentile = iv_svc.get_current_percentile()
        dvol = iv_svc.get_current_dvol()
        return _ok({'percentile': percentile, 'dvol': dvol, 'source': 'deribit_dvol'})
    except ImportError:
        return _ok({
            'percentile': None,
            'dvol': None,
            'note': 'IV module not built yet (Phase 2)',
        })
    except Exception as e:
        return _ok({'percentile': None, 'dvol': None, 'error': str(e)})


@patience_bp.route('/iv/history', methods=['GET'])
def iv_history():
    """Phase 1 stub. Phase 2: returns DVOL history for chart."""
    try:
        days = int(request.args.get('days', 30))
        from webui.backend.services.patience_iv import get_patience_iv
        history = get_patience_iv().get_history(days)
        return _ok({'history': history, 'days': days})
    except ImportError:
        return _ok({'history': [], 'note': 'IV module not built yet (Phase 2)'})
    except Exception as e:
        return _ok({'history': [], 'error': str(e)})


# ═══════════════════════════════════════════════════════════════════════
# P&L Dashboard
# ═══════════════════════════════════════════════════════════════════════

@patience_bp.route('/pnl', methods=['GET'])
def pnl_summary():
    """Real-time P&L across all active Patience cards."""
    db = _db()
    cards = db.get_cards_by_status('EXECUTING', 'COMPLETED', 'ARMED')
    result = []

    for card in cards:
        legs = db.get_legs(card['card_id'])
        filled_legs = [l for l in legs if l.get('status') in ('FILLED', 'HANDED_TO_MMM')]

        entry_premium = 0.0
        for leg in filled_legs:
            fill = float(leg.get('fill_price') or 0)
            lots = int(leg.get('lots') or 0)
            sign = 1 if leg.get('direction') == 'SELL' else -1
            entry_premium += sign * fill * lots

        # Current mark value: Phase 1 stub (Phase 3 fetches live marks)
        result.append({
            'card_id': card['card_id'],
            'card_name': card.get('card_name'),
            'status': card.get('status'),
            'entry_premium': round(entry_premium, 2),
            'current_value': None,   # Phase 3: fetch live marks
            'unrealized_pnl': None,  # Phase 3: current_value - entry_premium
            'legs_count': len(legs),
            'filled_count': len(filled_legs),
            'mmm_legs': sum(1 for l in legs if l.get('status') == 'HANDED_TO_MMM'),
        })

    return _ok({'cards': result, 'total_cards': len(result)})


# ═══════════════════════════════════════════════════════════════════════
# Performance History
# ═══════════════════════════════════════════════════════════════════════

@patience_bp.route('/performance', methods=['GET'])
def performance_history():
    db = _db()
    perf = db.get_performance()

    # Summary stats
    closed = [p for p in perf if p.get('pnl') is not None]
    wins = [p for p in closed if p.get('pnl', 0) > 0]
    losses = [p for p in closed if p.get('pnl', 0) <= 0]
    total_pnl = sum(p.get('pnl', 0) for p in closed)
    avg_pnl = total_pnl / len(closed) if closed else 0

    return _ok({
        'records': perf,
        'summary': {
            'total_cards': len(closed),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(len(wins) / len(closed) * 100, 1) if closed else 0,
            'total_pnl': round(total_pnl, 2),
            'avg_pnl': round(avg_pnl, 2),
        }
    })


# ═══════════════════════════════════════════════════════════════════════
# Bid/Ask Prices for Card Legs
# ═══════════════════════════════════════════════════════════════════════

def _build_symbol(leg):
    """Build Delta Exchange symbol from leg data."""
    prefix = 'C' if leg.get('option_type') == 'CE' else 'P'
    strike = int(leg.get('strike') or 0)
    expiry_date = leg.get('expiry_date', '')  # YYYY-MM-DD

    if len(expiry_date) >= 10:
        parts = expiry_date.split('-')
        ddmmyy = parts[2] + parts[1] + parts[0][2:]  # DDMMYY — Delta Exchange format (e.g. 170326 = 2026-03-17)
        return f"{prefix}-BTC-{strike}-{ddmmyy}"
    return None


def _fetch_ticker_for_leg(leg):
    """Fetch ticker data for a single leg from Delta Exchange API."""
    symbol = _build_symbol(leg)
    if not symbol:
        return {
            'leg_id': leg.get('leg_id'),
            'symbol': None,
            'bid': None,
            'ask': None,
            'mark_price': None,
            'error': 'Cannot build symbol (missing strike or expiry)'
        }

    if symbol.endswith('-0-') or '-0-' in symbol:
        return {
            'leg_id': leg.get('leg_id'),
            'symbol': symbol,
            'bid': None,
            'ask': None,
            'mark_price': None,
            'error': 'Strike is 0 (relative strike not yet resolved)'
        }

    try:
        api_url = f"https://api.india.delta.exchange/v2/tickers/{symbol}"
        log.info(f"[Patience] Fetching ticker: {api_url}")
        response = requests.get(api_url, timeout=5)

        if response.status_code != 200:
            log.warning(f"[Patience] Ticker {symbol}: HTTP {response.status_code}")
            return {
                'leg_id': leg.get('leg_id'),
                'symbol': symbol,
                'bid': None,
                'ask': None,
                'mark_price': None,
                'error': f'HTTP {response.status_code}'
            }

        data = response.json()
        if not data.get('success'):
            log.warning(f"[Patience] Ticker {symbol}: API error: {data}")
            return {
                'leg_id': leg.get('leg_id'),
                'symbol': symbol,
                'bid': None,
                'ask': None,
                'mark_price': None,
                'error': data.get('error', 'API error')
            }

        result = data.get('result', {})
        quotes = result.get('quotes', {})
        bid = float(quotes.get('best_bid', 0) or 0)
        ask = float(quotes.get('best_ask', 0) or 0)
        mark = float(result.get('mark_price', 0) or 0)

        log.info(f"[Patience] Ticker {symbol}: bid={bid}, ask={ask}, mark={mark}")

        return {
            'leg_id': leg.get('leg_id'),
            'symbol': symbol,
            'bid': bid if bid > 0 else None,
            'ask': ask if ask > 0 else None,
            'mark_price': mark if mark > 0 else None,
            'error': None
        }

    except Exception as e:
        log.warning(f"[Patience] Failed to fetch ticker for {symbol}: {e}")
        return {
            'leg_id': leg.get('leg_id'),
            'symbol': symbol,
            'bid': None,
            'ask': None,
            'mark_price': None,
            'error': str(e)
        }


@patience_bp.route('/cards/<card_id>/prices', methods=['GET'])
def get_card_prices(card_id):
    """
    GET /api/patience/cards/:id/prices

    Fetches real-time bid/ask/mark prices for all legs of a card.
    Uses concurrent requests to Delta Exchange API for fast response.

    Returns: {
        success: true,
        prices: [
            {leg_id, symbol, bid, ask, mark_price, error},
            ...
        ],
        count: N
    }
    """
    db = _db()
    card = db.get_card(card_id)
    if not card:
        return _err('Card not found', 404)

    legs = db.get_legs(card_id)
    if not legs:
        return _ok({'prices': [], 'count': 0})

    # Fetch all tickers concurrently
    prices = []
    futures = {}

    for leg in legs:
        future = _ticker_pool.submit(_fetch_ticker_for_leg, leg)
        futures[future] = leg

    for future in as_completed(futures):
        try:
            price_data = future.result(timeout=5)
            prices.append(price_data)
        except Exception as e:
            leg = futures[future]
            log.error(f"Timeout fetching ticker for leg {leg.get('leg_id')}: {e}")
            prices.append({
                'leg_id': leg.get('leg_id'),
                'symbol': _build_symbol(leg),
                'bid': None,
                'ask': None,
                'mark_price': None,
                'error': 'Timeout'
            })

    # Sort by leg_id to maintain order
    prices.sort(key=lambda p: p.get('leg_id', ''))

    return _ok({'prices': prices, 'count': len(prices)})


# ═══════════════════════════════════════════════════════════════════════
# Live Execution Status (real-time loop state from PatienceLoopService)
# ═══════════════════════════════════════════════════════════════════════

@patience_bp.route('/cards/<card_id>/execution-status', methods=['GET'])
def get_execution_status(card_id):
    """
    GET /api/patience/cards/<card_id>/execution-status

    Returns live in-memory loop state from PatienceLoopService.
    Poll every 1s from the frontend when card is EXECUTING.

    Response includes per-symbol progress (status, orderId, fillPrice, attempts),
    current_round, rounds_completed, and elapsed time.
    """
    try:
        from webui.backend.services.patience_loop import get_patience_loop_service
        loop_svc = get_patience_loop_service()
        state = loop_svc.get_status(card_id)

        if not state.get('exists', True) or state.get('exists') is False:
            # No active loop — return DB leg statuses so frontend stays up to date
            db = _db()
            legs = db.get_legs(card_id)
            return _ok({
                'active': False,
                'legs': [
                    {
                        'leg_id': l['leg_id'],
                        'status': l['status'],
                        'fill_price': l.get('fill_price'),
                        'order_id': l.get('order_id'),
                        'executed_symbol': l.get('executed_symbol'),
                    }
                    for l in legs
                ],
            })

        # Compute elapsed time
        started_at = state.get('started_at')
        elapsed = None
        if started_at:
            try:
                from datetime import datetime as _dt
                started = _dt.fromisoformat(started_at)
                elapsed = round(((_dt.now() - started).total_seconds()), 1)
            except Exception:
                pass

        # Build per-symbol progress list (enriched with leg DB data for leg_id lookup)
        progress_raw = state.get('progress', {})
        db = _db()
        legs = db.get_legs(card_id)
        leg_map = {l['leg_id']: l for l in legs}

        progress_list = []
        for sym, info in progress_raw.items():
            leg_id = info.get('leg_id')
            leg_db = leg_map.get(leg_id, {})
            progress_list.append({
                'symbol': sym,
                'leg_id': leg_id,
                'direction': leg_db.get('direction'),
                'option_type': leg_db.get('option_type'),
                'lots': info.get('size'),
                'status': info.get('status', 'placing'),
                'filled': info.get('filled', False),
                'order_id': info.get('orderId'),
                'fill_price': info.get('fillPrice'),
                'error': info.get('error'),
                # If already persisted to DB, use DB values as authoritative
                'db_fill_price': leg_db.get('fill_price'),
                'db_order_id': leg_db.get('order_id'),
            })

        return _ok({
            'active': True,
            'loop_status': state.get('status'),
            'current_round': state.get('current_round', 0),
            'total_rounds': state.get('total_rounds', 0),
            'rounds_completed': state.get('rounds_completed', 0),
            'started_at': started_at,
            'elapsed_seconds': elapsed,
            'error': state.get('error'),
            'stop_requested': state.get('stop_requested', False),
            'progress': progress_list,
        })

    except Exception as e:
        log.error(f"patience_api: execution-status error: {e}", exc_info=True)
        return _err(str(e), 500)


# ═══════════════════════════════════════════════════════════════════════
# Bulk engine controls
# ═══════════════════════════════════════════════════════════════════════

@patience_bp.route('/arm-all', methods=['POST'])
def arm_all():
    """Arm all DRAFT cards."""
    db = _db()
    draft = db.get_cards_by_status('DRAFT')
    armed = 0
    for card in draft:
        new_status = _arm_card_internal(db, card['card_id'])
        if new_status in ('ARMED', 'WAITING'):
            armed += 1
    return _ok({'armed': armed, 'total': len(draft)})


@patience_bp.route('/disarm-all', methods=['POST'])
def disarm_all():
    """Disarm all ARMED + WAITING cards → DRAFT."""
    db = _db()
    armed = db.get_cards_by_status('ARMED', 'WAITING')
    for card in armed:
        db.update_card(card['card_id'], status='DRAFT')
    return _ok({'disarmed': len(armed)})


@patience_bp.route('/kill-switch', methods=['POST'])
def kill_switch():
    """Cancel all ARMED + WAITING + TRIGGERED + EXECUTING cards. Does NOT close positions."""
    cancelled = _trigger().kill_switch()
    # Also stop all currently running loops
    try:
        from webui.backend.services.patience_loop import get_patience_loop_service
        svc = get_patience_loop_service()
        all_loops = svc.get_status()
        stopped = 0
        for loop_id, state in all_loops.items():
            if state.get('status') == 'running':
                svc.stop_loop(loop_id)
                stopped += 1
        if stopped:
            log.info(f"kill_switch: stopped {stopped} running loop(s)")
    except Exception as e:
        log.warning(f"kill_switch: could not stop loops: {e}")
    return _ok({'cancelled': cancelled})
