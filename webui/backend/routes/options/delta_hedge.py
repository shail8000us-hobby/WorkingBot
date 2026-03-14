"""
Delta Hedge Module

Auto-hedge config, timer loop, and hedge route handlers.
Extracted from options_control.py — see docs/refactoring/OPTIONS_CONTROL_REFACTOR_PLAN.md

Routes are registered on the Blueprint by calling register_delta_hedge_routes(bp).

IMPORTANT: The module-level auto-start at the bottom is intentional —
it restores the timer state after a restart if hedge was enabled.
"""

from __future__ import annotations

import json as _json
import logging
import threading
import time
from pathlib import Path

from flask import Blueprint, jsonify, request

from .options_client import _run_async, get_unified_client

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Delta Hedge — module globals
# ---------------------------------------------------------------------------
_hedge_events: list = []           # ring buffer, max 100 entries
_hedge_events_lock = threading.Lock()
_last_hedge_time: float = 0.0

_auto_hedge_config: dict = {
    'enabled': False,
    'threshold': 5.0,
    'order_type': 'market',
    'smart_offset_pct': 0.05,
    'cooldown_seconds': 300,
    'max_perp_size_btc': 20.0,
    'log_events': True,
}
_auto_hedge_config_lock = threading.Lock()

_auto_hedge_timer = None
_auto_hedge_timer_lock = threading.Lock()
AUTO_HEDGE_INTERVAL_SECONDS = 30


def _auto_hedge_config_path() -> Path:
    cfg_dir = Path(__file__).parent.parent.parent / 'data'
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / 'auto_hedge_config.json'


def _load_auto_hedge_config_from_disk():
    """Called once at import time — loads saved config from JSON."""
    global _auto_hedge_config
    try:
        p = _auto_hedge_config_path()
        if p.exists():
            with open(p) as f:
                saved = _json.load(f)
            with _auto_hedge_config_lock:
                _auto_hedge_config.update(saved)
    except Exception as e:
        log.warning(f'auto-hedge config not loaded from disk: {e}')


_load_auto_hedge_config_from_disk()


# ---------------------------------------------------------------------------
# Hedge helpers
# ---------------------------------------------------------------------------

def _get_portfolio_btc_delta() -> float:
    """
    Compute net BTC-equivalent delta from current options positions.
    Uses get_cached_positions() — no Flask app context required (safe for background threads).
    """
    from .options_control import get_cached_positions
    from .dashboard import calculate_portfolio_greeks
    positions = get_cached_positions(max_age=60) or []
    greeks = calculate_portfolio_greeks(positions)
    return float(greeks.get('btcDelta', 0.0))


async def _place_perp_order_async(client, side: str, size: float,
                                   order_type: str, smart_offset_pct: float) -> dict:
    """
    Place a BTC-PERP order on Delta Exchange.
    product_symbol 'BTCUSD' is the BTC perpetual contract.
    """
    data: dict = {
        'product_symbol': 'BTCUSD',
        'side': side,
        'size': size,
        'order_type': 'market_order',
    }

    if order_type == 'smart':
        try:
            ticker_resp = await client.rest_client._request_with_retry(
                'GET', '/v2/tickers/BTCUSD'
            )
            mark_price = float(
                (ticker_resp.get('result') or {}).get('mark_price') or 0
            )
            if mark_price > 0:
                offset = mark_price * (smart_offset_pct / 100.0)
                limit_price = (
                    mark_price - offset if side == 'buy'
                    else mark_price + offset
                )
                data['order_type'] = 'limit_order'
                data['limit_price'] = str(round(limit_price, 1))
                data['time_in_force'] = 'gtc'
                data['post_only'] = 'true'
        except Exception as e:
            log.warning(f'Smart hedge: mark price fetch failed ({e}), falling back to market')

    response = await client.rest_client._request_with_retry(
        method='POST', path='/v2/orders', data=data
    )
    return response.get('result', response)


# ---------------------------------------------------------------------------
# Auto-hedge background loop (threading.Timer re-arming, fires every 30s)
# ---------------------------------------------------------------------------

def _auto_hedge_tick():
    """Called every AUTO_HEDGE_INTERVAL_SECONDS. Re-arms itself when enabled."""
    global _last_hedge_time
    import datetime as _dt

    try:
        with _auto_hedge_config_lock:
            cfg = dict(_auto_hedge_config)

        if not cfg.get('enabled', False):
            return  # Don't re-arm if disabled

        portfolio_delta = _get_portfolio_btc_delta()

        if abs(portfolio_delta) < float(cfg.get('threshold', 5.0)):
            log.debug(f'auto-hedge: \u0394={portfolio_delta:.4f} within threshold, skip')
            return

        cooldown = float(cfg.get('cooldown_seconds', 300))
        if time.time() - _last_hedge_time < cooldown:
            log.debug('auto-hedge: cooldown active, skip')
            return

        max_size = float(cfg.get('max_perp_size_btc', 20.0))
        hedge_size = min(abs(portfolio_delta), max_size)
        side = 'sell' if portfolio_delta > 0 else 'buy'
        order_type = cfg.get('order_type', 'market')
        smart_offset = float(cfg.get('smart_offset_pct', 0.05))

        client = get_unified_client()
        result = _run_async(
            _place_perp_order_async(client, side, hedge_size, order_type, smart_offset)
        )
        order_id = str(result.get('id', 'unknown'))
        _last_hedge_time = time.time()

        if cfg.get('log_events', True):
            entry = {
                'trigger': 'auto',
                'side': side,
                'size': hedge_size,
                'pre_delta': portfolio_delta,
                'post_delta': round(
                    portfolio_delta + (hedge_size if side == 'buy' else -hedge_size), 4
                ),
                'order_id': order_id,
                'order_type': order_type,
                'timestamp': _dt.datetime.now().strftime('%d %b %Y, %I:%M %p'),
            }
            with _hedge_events_lock:
                _hedge_events.append(entry)
                if len(_hedge_events) > 100:
                    _hedge_events[:] = _hedge_events[-100:]

        log.info(
            f'\u26a1 AUTO-HEDGE FIRED: {side} {hedge_size} BTCUSD | '
            f'pre-\u0394={portfolio_delta} | order={order_id}'
        )

    except Exception as e:
        log.error(f'auto-hedge tick error: {e}')

    finally:
        # Re-arm only if still enabled
        with _auto_hedge_config_lock:
            still_enabled = _auto_hedge_config.get('enabled', False)
        if still_enabled:
            _schedule_next_auto_hedge_tick()


def _schedule_next_auto_hedge_tick():
    global _auto_hedge_timer
    with _auto_hedge_timer_lock:
        _auto_hedge_timer = threading.Timer(
            AUTO_HEDGE_INTERVAL_SECONDS, _auto_hedge_tick
        )
        _auto_hedge_timer.daemon = True
        _auto_hedge_timer.start()


def _ensure_auto_hedge_running():
    """Start the auto-hedge timer loop if not already running."""
    with _auto_hedge_timer_lock:
        already_running = (
            _auto_hedge_timer is not None and _auto_hedge_timer.is_alive()
        )
    if not already_running:
        _schedule_next_auto_hedge_tick()
        log.info('\u26a1 Auto-hedge timer started')


# ---------------------------------------------------------------------------
# Public accessors (used by options_control.py for the activity log route)
# ---------------------------------------------------------------------------

def get_hedge_events_snapshot(n: int = 20) -> list:
    """Return the last n hedge events (most recent first)."""
    with _hedge_events_lock:
        return list(reversed(_hedge_events[-n:]))


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_delta_hedge_routes(bp: Blueprint):
    """Register all delta-hedge routes on the given Blueprint."""

    @bp.route('/hedge-delta', methods=['POST'])
    def hedge_delta():
        """
        Place a BTC-PERP order to neutralise portfolio delta.

        JSON body:
            portfolio_delta  : float  — pre-computed BTC delta (optional)
            order_type       : str    — 'market' (default) | 'smart'
            smart_offset_pct : float  — offset % for smart orders (default 0.05)
            trigger          : str    — 'manual' (default) | 'auto'
        """
        global _last_hedge_time
        import datetime as _dt
        data = request.get_json() or {}

        order_type       = data.get('order_type', 'market')
        smart_offset_pct = float(data.get('smart_offset_pct', 0.05))
        trigger          = data.get('trigger', 'manual')

        try:
            if 'portfolio_delta' in data:
                portfolio_delta = float(data['portfolio_delta'])
            else:
                portfolio_delta = _get_portfolio_btc_delta()

            if abs(portfolio_delta) < 0.05:
                return jsonify({
                    'status': 'no_action',
                    'message': f'Delta already neutral (|\u0394|={abs(portfolio_delta):.4f} < 0.05)'
                })

            side = 'sell' if portfolio_delta > 0 else 'buy'
            size = round(abs(portfolio_delta), 4)

            client = get_unified_client()
            result = _run_async(
                _place_perp_order_async(client, side, size, order_type, smart_offset_pct)
            )
            order_id = str(result.get('id', 'unknown'))

            _last_hedge_time = time.time()
            ts = _dt.datetime.now().strftime('%d %b %Y, %I:%M %p')
            entry = {
                'trigger': trigger,
                'side': side,
                'size': size,
                'pre_delta': portfolio_delta,
                'post_delta': round(
                    portfolio_delta + (size if side == 'buy' else -size), 4
                ),
                'order_id': order_id,
                'order_type': order_type,
                'timestamp': ts,
            }
            with _hedge_events_lock:
                _hedge_events.append(entry)
                if len(_hedge_events) > 100:
                    _hedge_events[:] = _hedge_events[-100:]

            log.info(
                f'\u26a1 HEDGE ({trigger}): {side} {size} BTCUSD | '
                f'pre-\u0394={portfolio_delta} | order={order_id}'
            )

            return jsonify({
                'status': 'success',
                'order_id': order_id,
                'side': side,
                'size': size,
                'pre_hedge_delta': portfolio_delta,
                'post_hedge_delta': entry['post_delta'],
                'order_type': order_type,
            })

        except Exception as e:
            log.exception('\u274c hedge_delta route failed')
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @bp.route('/auto-hedge-config', methods=['GET'])
    def get_auto_hedge_config():
        with _auto_hedge_config_lock:
            cfg = dict(_auto_hedge_config)
        return jsonify({'success': True, 'config': cfg})

    @bp.route('/auto-hedge-config', methods=['POST'])
    def save_auto_hedge_config():
        global _auto_hedge_config
        data = request.get_json() or {}

        allowed = {
            'enabled', 'threshold', 'order_type', 'smart_offset_pct',
            'cooldown_seconds', 'max_perp_size_btc', 'log_events'
        }
        with _auto_hedge_config_lock:
            for k, v in data.items():
                if k in allowed:
                    _auto_hedge_config[k] = v
            cfg_snapshot = dict(_auto_hedge_config)

        try:
            with open(_auto_hedge_config_path(), 'w') as f:
                _json.dump(cfg_snapshot, f, indent=2)
        except Exception as e:
            log.warning(f'auto-hedge config save failed: {e}')

        if cfg_snapshot.get('enabled'):
            _ensure_auto_hedge_running()

        return jsonify({'success': True, 'config': cfg_snapshot})

    @bp.route('/auto-hedge-status', methods=['GET'])
    def get_auto_hedge_status():
        import datetime as _dt
        with _auto_hedge_config_lock:
            enabled = _auto_hedge_config.get('enabled', False)
        last_ts = (
            _dt.datetime.fromtimestamp(_last_hedge_time).strftime('%d %b %Y, %I:%M %p')
            if _last_hedge_time > 0 else 'Never'
        )
        with _hedge_events_lock:
            recent = list(reversed(_hedge_events[-5:]))
        return jsonify({
            'success': True,
            'enabled': enabled,
            'last_hedge_time': _last_hedge_time,
            'last_hedge_display': last_ts,
            'recent_events': recent,
        })


# ---------------------------------------------------------------------------
# Auto-start if config loaded from disk already has enabled=True
# (intentional module-level side effect — restores timer state after restart)
# ---------------------------------------------------------------------------
if _auto_hedge_config.get('enabled', False):
    _ensure_auto_hedge_running()
