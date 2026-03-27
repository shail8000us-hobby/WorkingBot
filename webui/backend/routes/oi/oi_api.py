"""
OI Aggregator — Flask Blueprint + SocketIO Namespace + Background Thread

READ-ONLY analytics module. Does NOT import or interact with:
- MMM algo (mmm_state, mmm_monitor, mmm_engine)
- IC algo
- Any trading execution logic

SocketIO namespace: /oi  (isolated from default '/')

Created: March 27, 2026
Revised: March 27, 2026 — audit fixes applied:
  - _init_lock guards _ensure_initialized() against concurrent double-init
  - config endpoint validates all inputs before applying
  - /snapshot supports ?expiries=date1,date2 (multi-expiry, backward compat)
  - oi_update emit is metadata-only (rows no longer pushed; frontend fetches via REST)
  - _prune_stale_keys moved here (once per full cycle, not per exchange merge)
"""

import logging
import threading
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

# Dedicated logger — never pollutes MMM or root logs
log = logging.getLogger('oi_aggregator')

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------
oi_bp = Blueprint('oi', __name__, url_prefix='/api/oi')

# ---------------------------------------------------------------------------
# Module state (lazy-initialized)
# ---------------------------------------------------------------------------
_socketio = None
_store = None          # OIStore instance
_fetchers = None       # list of BaseOIFetcher
_refresh_interval = 60  # seconds

_state = {
    'thread_started': False,
    'connected_clients': 0,
    'cycle_running': False,     # overlap guard
    'last_cycle_ts': None,
    'total_cycles': 0,
}
_state_lock = threading.Lock()

# Separate lock for one-time initialization — prevents double-OIStore creation
# when two SocketIO clients connect simultaneously before _store is created.
_init_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Lazy initialization
# ---------------------------------------------------------------------------

def _ensure_initialized():
    """
    Create store and fetchers on first use.
    Protected by _init_lock so concurrent callers (e.g. two simultaneous
    SocketIO connects) never create duplicate OIStore instances.
    """
    global _store, _fetchers
    # Fast path — already initialized (no lock needed for read-once check)
    if _store is not None and _fetchers is not None:
        return

    with _init_lock:
        # Re-check inside lock (double-checked locking pattern)
        if _store is None:
            from .oi_store import OIStore
            _store = OIStore()
            log.info('[OI] OIStore initialized')
        if _fetchers is None:
            from .oi_fetchers import create_fetchers
            _fetchers = create_fetchers()
            log.info('[OI] Fetchers initialized: %d exchanges', len(_fetchers))


# ---------------------------------------------------------------------------
# Background refresh loop
# ---------------------------------------------------------------------------

def _oi_refresh_loop():
    """
    Runs in a real OS thread. Fetches OI from all exchanges every interval.
    Emits metadata-only updates via SocketIO to /oi namespace.
    Frontend fetches rows via REST after receiving the metadata signal.
    """
    log.info('[OI] Background refresh thread started (interval=%ds)', _refresh_interval)
    _ensure_initialized()

    while True:
        # Overlap guard
        with _state_lock:
            if _state['cycle_running']:
                log.warning('[OI] Previous cycle still running — skipping this tick')
                time.sleep(_refresh_interval)
                continue
            _state['cycle_running'] = True

        cycle_start = time.monotonic()
        try:
            _run_single_cycle()
        except Exception as e:
            log.error('[OI] Refresh cycle error: %s', e, exc_info=True)
        finally:
            with _state_lock:
                _state['cycle_running'] = False
                _state['last_cycle_ts'] = datetime.now(timezone.utc).isoformat()
                _state['total_cycles'] += 1

        elapsed = time.monotonic() - cycle_start
        sleep_for = max(0, _refresh_interval - elapsed)
        log.debug('[OI] Cycle completed in %.1fs, sleeping %.1fs', elapsed, sleep_for)
        time.sleep(sleep_for)


def _run_single_cycle():
    """
    Fetch from all exchanges, merge into store, prune stale keys, emit metadata.
    Pruning happens ONCE here (not inside merge_snapshot per exchange).
    """
    all_spikes = []

    # Fetch from each exchange (sequential — safe, avoids eventlet hub blocking)
    for fetcher in _fetchers:
        if not fetcher.enabled:
            continue
        try:
            rows = fetcher.fetch(underlying='BTC')
            if rows:
                spikes = _store.merge_snapshot(fetcher.exchange_name, rows)
                all_spikes.extend(spikes)
        except Exception as e:
            log.warning('[OI] Fetcher %s failed: %s', fetcher.exchange_name, e)

    # Prune stale keys ONCE per full cycle (not per exchange merge)
    try:
        _store.prune_stale_keys()
    except Exception as e:
        log.warning('[OI] Prune failed: %s', e)

    # Emit metadata-only oi_update — frontend fetches rows for its selectedExpiries via REST
    if _socketio:
        try:
            metadata = _store.get_metadata_for_emit(underlying='BTC')
            _socketio.emit('oi_update', metadata, namespace='/oi')
        except Exception as e:
            log.warning('[OI] Failed to emit oi_update: %s', e)

        # Emit spikes
        for spike in all_spikes:
            try:
                _socketio.emit('oi_spike', spike, namespace='/oi')
            except Exception as e:
                log.warning('[OI] Failed to emit oi_spike: %s', e)

    log.info('[OI] Cycle done: %d total spikes detected', len(all_spikes))


def _start_background_thread():
    """Start the refresh thread. Uses real OS thread (eventlet-safe pattern)."""
    try:
        from eventlet.patcher import original as _ep_original
        RealThread = _ep_original('threading').Thread
    except (ImportError, AttributeError):
        RealThread = threading.Thread

    t = RealThread(target=_oi_refresh_loop, daemon=True, name='oi-refresh')
    t.start()
    log.info('[OI] Background thread started (type=%s)', type(t).__name__)


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@oi_bp.route('/health', methods=['GET'])
def oi_health():
    """Health check with per-exchange status."""
    _ensure_initialized()
    health = _store.get_health() if _store else {}

    # Add fetcher health
    fetcher_health = []
    if _fetchers:
        for f in _fetchers:
            fetcher_health.append(f.get_health())

    return jsonify({
        'status': 'ok',
        'module': 'oi_aggregator',
        'thread_started': _state['thread_started'],
        'connected_clients': _state['connected_clients'],
        'total_cycles': _state['total_cycles'],
        'last_cycle_ts': _state['last_cycle_ts'],
        'refresh_interval_sec': _refresh_interval,
        'store': health,
        'fetchers': fetcher_health,
        'ts': datetime.now(timezone.utc).isoformat(),
    })


@oi_bp.route('/snapshot', methods=['GET'])
def oi_snapshot():
    """
    Aggregated OI rows per strike.

    Params:
        expiries   — comma-separated ISO dates e.g. '2026-03-30,2026-04-07' (preferred)
        expiry     — single ISO date (backward compat, ignored if expiries present)
        underlying — default 'BTC'
        window_min — OI change lookback in minutes (default 20)
    """
    _ensure_initialized()
    underlying = request.args.get('underlying', 'BTC').upper()
    window_min = request.args.get('window_min', 20, type=int)

    if not _store:
        return jsonify({'rows': [], 'message': 'Store not initialized'}), 503

    # Parse expiry list (multi-expiry support)
    expiry_list = _parse_expiry_param(underlying)

    rows = _store.get_aggregated(expiries=expiry_list, underlying=underlying,
                                 window_minutes=window_min) if expiry_list else []

    # Compute summary (total + per-expiry breakdown)
    total_call = sum(r['oi'] for r in rows if r['type'] == 'call')
    total_put = sum(r['oi'] for r in rows if r['type'] == 'put')
    pcr = total_put / total_call if total_call > 0 else 0

    by_expiry = {}
    for r in rows:
        exp = r['expiry']
        if exp not in by_expiry:
            by_expiry[exp] = {'call_oi': 0.0, 'put_oi': 0.0}
        if r['type'] == 'call':
            by_expiry[exp]['call_oi'] += r['oi']
        else:
            by_expiry[exp]['put_oi'] += r['oi']
    for exp, v in by_expiry.items():
        v['pcr'] = round(v['put_oi'] / v['call_oi'], 4) if v['call_oi'] > 0 else 0

    return jsonify({
        'expiries_requested': expiry_list,
        'underlying': underlying,
        'underlying_price': _store.get_underlying_price(underlying),
        'rows': rows,
        'summary': {
            'total_call_oi': total_call,
            'total_put_oi': total_put,
            'pcr': round(pcr, 4),
            'by_expiry': by_expiry,
        },
        'ts': datetime.now(timezone.utc).isoformat(),
    })


def _parse_expiry_param(underlying: str) -> list:
    """
    Parse ?expiries=date1,date2 or legacy ?expiry=date from request.args.
    Returns a list of ISO date strings. Falls back to nearest expiry if nothing given.
    """
    # New multi-expiry param (preferred)
    expiries_raw = request.args.get('expiries', '').strip()
    if expiries_raw:
        expiry_list = [e.strip() for e in expiries_raw.split(',') if e.strip()]
        return expiry_list[:5]  # Hard cap at 5

    # Legacy single-expiry param (backward compat)
    single = request.args.get('expiry', '').strip()
    if single:
        return [single]

    # Default: nearest expiry
    if _store:
        all_exp = _store.get_expiries(underlying)
        return [all_exp[0]] if all_exp else []
    return []


@oi_bp.route('/expiries', methods=['GET'])
def oi_expiries():
    """Available expiry dates with metadata (is_weekly, days_to_expiry)."""
    _ensure_initialized()
    underlying = request.args.get('underlying', 'BTC').upper()

    if not _store:
        return jsonify({'expiries': []}), 503

    expiries = _store.get_expiries_with_metadata(underlying)
    return jsonify({'expiries': expiries, 'underlying': underlying})


@oi_bp.route('/spikes', methods=['GET'])
def oi_spikes():
    """Recent spike events."""
    _ensure_initialized()
    last_n = request.args.get('last_n', 50, type=int)

    if not _store:
        return jsonify({'spikes': []}), 503

    spikes = _store.get_spike_log(last_n=last_n)
    return jsonify({'spikes': spikes})


@oi_bp.route('/config', methods=['GET'])
def oi_config_get():
    """Current spike detection thresholds."""
    _ensure_initialized()
    config = _store.spike_detector.get_config() if _store else {}
    config['refresh_interval_sec'] = _refresh_interval
    return jsonify(config)


@oi_bp.route('/config', methods=['POST'])
def oi_config_set():
    """
    Update spike detection thresholds.
    All numeric fields are validated before applying.
    """
    global _refresh_interval
    _ensure_initialized()

    data = request.get_json(silent=True) or {}
    errors = []

    # Validate and apply refresh_interval_sec
    if 'refresh_interval_sec' in data:
        try:
            val = int(data['refresh_interval_sec'])
            if not (30 <= val <= 300):
                errors.append('refresh_interval_sec must be 30–300')
            else:
                _refresh_interval = val
                log.info('[OI] Refresh interval updated to %ds', _refresh_interval)
        except (TypeError, ValueError):
            errors.append('refresh_interval_sec must be an integer')

    # Validated numeric config fields with allowed ranges
    numeric_fields = {
        'threshold_pct':      (1.0, 100.0),
        'window_minutes':     (1, 60),
        'min_oi_usd':         (0, 100_000_000),
        'min_oi_change_usd':  (0, 100_000_000),
        'cooldown_minutes':   (1, 1440),
    }

    validated = {}
    for field, (lo, hi) in numeric_fields.items():
        if field not in data:
            continue
        try:
            val = float(data[field])
            if not (lo <= val <= hi):
                errors.append(f'{field} must be {lo}–{hi}')
            else:
                validated[field] = val
        except (TypeError, ValueError):
            errors.append(f'{field} must be numeric')

    if errors:
        return jsonify({'status': 'error', 'errors': errors}), 400

    if _store and validated:
        _store.spike_detector.update_config(**validated)

    return jsonify({
        'status': 'updated',
        'config': _store.spike_detector.get_config() if _store else {},
    })


# ---------------------------------------------------------------------------
# SocketIO Namespace: /oi
# ---------------------------------------------------------------------------

def init_oi_websocket(socketio):
    """Register /oi namespace handlers. Called once from app.py startup."""
    global _socketio
    _socketio = socketio

    @socketio.on('connect', namespace='/oi')
    def handle_oi_connect():
        with _state_lock:
            _state['connected_clients'] += 1
            client_count = _state['connected_clients']
        log.info('[OI] Client connected to /oi namespace (total: %d)', client_count)

        # Lazy init: start background thread on first connection.
        # _state_lock ensures only one thread starts even with concurrent connects.
        with _state_lock:
            if not _state['thread_started']:
                _state['thread_started'] = True
                log.info('[OI] First client connected — starting background refresh thread')
                _start_background_thread()

        # Ensure store + fetchers exist (guarded by _init_lock inside)
        _ensure_initialized()

        # Send initial metadata so the frontend knows what expiries are available.
        # The frontend will then fetch rows for its default expiry via REST.
        if _store:
            try:
                metadata = _store.get_metadata_for_emit(underlying='BTC')
                socketio.emit('oi_update', metadata, namespace='/oi')
            except Exception as e:
                log.warning('[OI] Failed to send initial metadata: %s', e)

    @socketio.on('disconnect', namespace='/oi')
    def handle_oi_disconnect():
        with _state_lock:
            _state['connected_clients'] = max(0, _state['connected_clients'] - 1)
            client_count = _state['connected_clients']
        log.info('[OI] Client disconnected from /oi namespace (total: %d)', client_count)

    @socketio.on('request_snapshot', namespace='/oi')
    def handle_request_snapshot(data=None):
        """Client can request a fresh metadata update for a specific underlying."""
        _ensure_initialized()
        if not _store:
            return
        underlying = (data or {}).get('underlying', 'BTC')
        metadata = _store.get_metadata_for_emit(underlying=underlying)
        socketio.emit('oi_update', metadata, namespace='/oi')

    log.info('[OI] SocketIO namespace /oi registered')
