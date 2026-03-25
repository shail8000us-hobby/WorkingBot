"""
SSDH State Management — Short Straddle Double Hedge

Single source of truth for all data structures.
Every other SSDH module imports constants and functions from here.

Created: March 21, 2026
"""

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

log = logging.getLogger('ssdh_state')

# =============================================================================
# Constants
# =============================================================================

LOT_SIZE_BTC = 0.001          # 1 lot = 0.001 BTC on Delta Exchange

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'data'
)
SSDH_STATE_FILE = os.path.join(DATA_DIR, 'ssdh_sessions.json')

# Session lifecycle states
STATUS_IDLE         = 'IDLE'
STATUS_INITIALIZING = 'INITIALIZING'
STATUS_RUNNING      = 'RUNNING'
STATUS_WIND_DOWN    = 'WIND_DOWN'
STATUS_CLOSED       = 'CLOSED'
STATUS_ABORTED      = 'ABORTED'
STATUS_EMERGENCY    = 'EMERGENCY'

# Entry states (for atomic entry crash recovery)
ENTRY_IDLE     = 'ENTRY_IDLE'
ENTRY_PLACING  = 'ENTRY_PLACING'
ENTRY_COMPLETE = 'ENTRY_COMPLETE'
ENTRY_ABORTED  = 'ENTRY_ABORTED'

# Position directions
DIR_SHORT = 'short'
DIR_LONG  = 'long'

# Position types
TYPE_CORE  = 'core'    # short ATM legs
TYPE_HEDGE = 'hedge'   # long OTM legs

# Position status
POS_ACTIVE = 'active'
POS_CLOSED = 'closed'

# Close reasons
CLOSE_TIME      = 'time_exit'
CLOSE_MAX_LOSS  = 'max_loss'
CLOSE_TRAILING  = 'trailing_stop'
CLOSE_STRUCTURE = 'structure_break'
CLOSE_MANUAL    = 'manual'
CLOSE_KILL      = 'kill_switch'

# Entry checkpoint leg IDs (the 4 SSDH legs)
LEG_SHORT_CE = 'short_ce'
LEG_SHORT_PE = 'short_pe'
LEG_LONG_CE  = 'long_ce'
LEG_LONG_PE  = 'long_pe'

SSDH_LEG_IDS = [LEG_SHORT_CE, LEG_SHORT_PE, LEG_LONG_CE, LEG_LONG_PE]


# =============================================================================
# Decimal helper
# =============================================================================

def _D(value) -> Decimal:
    """Convert value to Decimal. Returns Decimal('0') on failure."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


# =============================================================================
# Position factory
# =============================================================================

def create_position(
    pos_id: str,
    side: str,           # 'CE' | 'PE'
    direction: str,      # DIR_SHORT | DIR_LONG
    pos_type: str,       # TYPE_CORE | TYPE_HEDGE
    strike: float,
    lots: int,
    entry_premium: float,
    order_id: str,
    client_order_id: str,
    fill_confirmed_at: str,   # ISO UTC
    symbol: str = '',         # Delta Exchange symbol e.g. 'C-BTC-100000-210326'
) -> dict:
    """
    The ONLY way to create a position dict.

    Enforces presence of order_id, client_order_id, fill_confirmed_at on every
    position — these are required for reconciliation and anti-duplication.

    current_premium starts as None (never 0) — price not yet fetched.
    _being_closed starts as False.
    """
    if direction not in (DIR_SHORT, DIR_LONG):
        raise ValueError(f"direction must be '{DIR_SHORT}' or '{DIR_LONG}', got: {direction!r}")
    if pos_type not in (TYPE_CORE, TYPE_HEDGE):
        raise ValueError(f"pos_type must be '{TYPE_CORE}' or '{TYPE_HEDGE}', got: {pos_type!r}")
    if side not in ('CE', 'PE'):
        raise ValueError(f"side must be 'CE' or 'PE', got: {side!r}")
    if lots < 1:
        raise ValueError(f"lots must be >= 1, got: {lots}")
    if entry_premium <= 0:
        raise ValueError(f"entry_premium must be > 0, got: {entry_premium}")

    return {
        # Identity
        'pos_id':              pos_id,
        'side':                side,
        'direction':           direction,
        'pos_type':            pos_type,
        'strike':              float(strike),
        'lots':                int(lots),
        'symbol':              symbol,   # Delta Exchange symbol for price lookup

        # Entry data
        'entry_premium':       float(entry_premium),
        'order_id':            order_id,
        'client_order_id':     client_order_id,
        'fill_confirmed_at':   fill_confirmed_at,

        # Live price (None = not yet fetched; NEVER use 0 as fallback for None)
        'current_premium':     None,

        # P&L (computed; never stored as non-zero when premium is None)
        'unrealized_pnl':      0.0,
        'realized_pnl':        None,   # set on close

        # Lifecycle
        'status':              POS_ACTIVE,
        '_being_closed':       False,
        '_being_closed_at':    None,

        # Close data (all None until closed)
        'close_premium':              None,
        'close_order_id':             None,
        'close_client_order_id':      None,
        'close_reason':               None,
        'closed_at':                  None,
        'close_fees':                 None,

        'created_at': datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# P&L computation
# =============================================================================

def compute_position_pnl(position: dict) -> float:
    """
    Returns unrealized P&L for ONE position.

    short: (entry_premium - current_premium) × lots × LOT_SIZE_BTC
    long:  (current_premium - entry_premium) × lots × LOT_SIZE_BTC

    Returns 0.0 if current_premium is None.
    NEVER phantom P&L — 0 is a valid price (nearly worthless option).
    None means fetch failed; treat them differently.

    Uses Decimal internally. Returns float.
    """
    current = position.get('current_premium')
    if current is None:
        log.debug("compute_position_pnl: current_premium is None for %s — skipping", position.get('pos_id'))
        return 0.0

    entry    = _D(position['entry_premium'])
    cur      = _D(current)
    lots     = _D(position['lots'])
    lot_size = _D(LOT_SIZE_BTC)

    if position['direction'] == DIR_SHORT:
        pnl = (entry - cur) * lots * lot_size
    else:
        pnl = (cur - entry) * lots * lot_size

    return float(pnl)


def recompute_net_pnl(session: dict) -> dict:
    """
    Recomputes unrealized_pnl for all active positions.
    Updates session['unrealized_pnl'] and session['net_pnl'].
    Does NOT touch session['realized_pnl'] or session['total_fees'].

    Rule: realized_pnl and unrealized_pnl are an atomic pair.
    Any caller that updates realized_pnl MUST call this immediately after.

    Returns dict: {'unrealized_pnl': float, 'net_pnl': float, 'stale_legs': [pos_ids]}
    """
    total_unrealized = _D('0')
    stale_legs = []

    for pos in session.get('positions', []):
        if pos.get('status') != POS_ACTIVE:
            continue

        if pos.get('current_premium') is None:
            stale_legs.append(pos['pos_id'])
            total_unrealized += _D(pos.get('unrealized_pnl', 0))
            continue

        pnl = compute_position_pnl(pos)
        pos['unrealized_pnl'] = pnl
        total_unrealized += _D(pnl)

    unrealized = float(total_unrealized)
    realized   = float(session.get('realized_pnl', 0.0))
    fees       = float(session.get('total_fees', 0.0))
    net        = realized + unrealized - fees

    session['unrealized_pnl'] = unrealized
    session['net_pnl']        = net

    if net > session.get('peak_net_pnl', 0.0):
        session['peak_net_pnl'] = net

    return {'unrealized_pnl': unrealized, 'net_pnl': net, 'stale_legs': stale_legs}


# =============================================================================
# Session factory
# =============================================================================

def create_session(session_id: str, params: dict) -> dict:
    """
    Returns a new session dict in IDLE status.
    params should already be validated by ssdh_config.validate_params().
    """
    now = datetime.now(timezone.utc).isoformat()
    return {
        'session_id':       session_id,
        'strategy':         'ssdh',
        'status':           STATUS_IDLE,
        'entry_state':      ENTRY_IDLE,
        'params':           dict(params),

        'positions':        [],

        'realized_pnl':     0.0,
        'unrealized_pnl':   0.0,
        'total_fees':       0.0,
        'net_pnl':          0.0,
        'peak_net_pnl':     0.0,

        # Phase 2+ — always 0 in Phase 1
        'roll_count':       0,

        'created_at':       now,
        'started_at':       None,
        'closed_at':        None,
        'close_reason':     None,
        'entry_started_at': None,
        'session_end_time': None,  # computed at entry: started_at + session_window_hours

        # Entry checkpoint: {leg_id: fill_result}
        'entry_fills':      {},
        'close_metadata':   {},

        # Spot price at entry time — used by vega spike detector
        'spot_at_entry':    None,
    }


# =============================================================================
# Position queries
# =============================================================================

def get_active_positions(session: dict) -> list:
    """Returns positions where status == 'active'."""
    return [p for p in session.get('positions', []) if p.get('status') == POS_ACTIVE]


def get_positions_by_type(session: dict, direction: str, side: str) -> list:
    """
    Returns active positions filtered by direction and side.
    e.g., get_positions_by_type(session, DIR_SHORT, 'CE') → [short CE position]
    """
    return [
        p for p in get_active_positions(session)
        if p.get('direction') == direction and p.get('side') == side
    ]


def get_position_by_id(session: dict, pos_id: str) -> Optional[dict]:
    """Returns position dict by pos_id, or None if not found."""
    for p in session.get('positions', []):
        if p.get('pos_id') == pos_id:
            return p
    return None


# =============================================================================
# Position close
# =============================================================================

def mark_position_closed(
    position: dict,
    close_premium: float,
    close_order_id: str,
    close_client_order_id: str,
    close_reason: str,
    session: dict,
    fees: float = 0.0,
) -> float:
    """
    Marks position as closed. Computes and returns realized_pnl.

    Updates session['realized_pnl'] += realized_pnl.
    Updates session['total_fees'] += fees.
    Calls recompute_net_pnl(session) — MANDATORY atomic pair refresh.

    Returns realized_pnl (float).
    """
    now = datetime.now(timezone.utc).isoformat()

    entry = _D(position['entry_premium'])
    close = _D(close_premium)
    lots  = _D(position['lots'])
    lot_size = _D(LOT_SIZE_BTC)

    if position['direction'] == DIR_SHORT:
        realized = float((entry - close) * lots * lot_size)
    else:
        realized = float((close - entry) * lots * lot_size)

    position['status']                = POS_CLOSED
    position['close_premium']         = float(close_premium)
    position['close_order_id']        = close_order_id
    position['close_client_order_id'] = close_client_order_id
    position['close_reason']          = close_reason
    position['closed_at']             = now
    position['close_fees']            = float(fees)
    position['realized_pnl']          = realized
    position['unrealized_pnl']        = 0.0
    position['_being_closed']         = False
    position['_being_closed_at']      = None

    session['realized_pnl'] = float(_D(session.get('realized_pnl', 0.0)) + _D(realized))
    session['total_fees']   = float(_D(session.get('total_fees', 0.0)) + _D(fees))

    # MANDATORY: refresh unrealized_pnl immediately (atomic pair rule)
    recompute_net_pnl(session)

    return realized


# =============================================================================
# Persistence
# =============================================================================

def persist_session(session: dict) -> None:
    """
    Atomic write of a single session into SSDH_STATE_FILE.
    Pattern: load all → update one → write temp → fsync → rename.
    Never corrupts the file on crash.
    """
    all_sessions = load_sessions()
    all_sessions[session['session_id']] = session

    os.makedirs(DATA_DIR, exist_ok=True)

    tmp_path = SSDH_STATE_FILE + '.tmp'
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(all_sessions, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, SSDH_STATE_FILE)
    except Exception as e:
        log.error("persist_session: failed to write %s: %s", SSDH_STATE_FILE, e)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def load_sessions() -> dict:
    """
    Loads all sessions from SSDH_STATE_FILE.
    Returns {} if file missing or corrupt.
    """
    if not os.path.exists(SSDH_STATE_FILE):
        return {}
    try:
        with open(SSDH_STATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            log.warning("load_sessions: expected dict, got %s — returning {}", type(data))
            return {}
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.error("load_sessions: failed to read %s: %s", SSDH_STATE_FILE, e)
        return {}
