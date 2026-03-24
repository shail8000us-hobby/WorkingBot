"""
IC Constants — Iron Condor

Shared constants for the Iron Condor algorithm.
Reuses LOT_SIZE_BTC and strike_key from MMM where appropriate.

Created: 2026-03-24
"""

from decimal import Decimal

# Delta Exchange BTC Options: 1 BTC = 1000 lots, so 1 lot = 0.001 BTC
# Premiums are quoted in USD per BTC. To get USD value for N lots:
#   usd_value = premium_per_btc * N * LOT_SIZE_BTC
LOT_SIZE_BTC = 0.001


def _D(x) -> Decimal:
    """Decimal precision helper for financial calculations."""
    return Decimal(str(x))


_LOT = _D(LOT_SIZE_BTC)


def strike_key(strike: float) -> str:
    """
    Canonical strike key for consistent dictionary lookups.

    Converts any strike representation to a consistent string key.
    Returns str(int(round(strike))).
    """
    try:
        return str(int(round(float(strike))))
    except (ValueError, TypeError, OverflowError):
        return str(strike)


# Leg identifiers
LEG_SP = 'SP'  # Short Put
LEG_LP = 'LP'  # Long Put (wing)
LEG_SC = 'SC'  # Short Call
LEG_LC = 'LC'  # Long Call (wing)
ALL_LEGS = (LEG_SP, LEG_LP, LEG_SC, LEG_LC)

# Session statuses
STATUS_IDLE = 'IDLE'
STATUS_RUNNING = 'RUNNING'
STATUS_PAUSED = 'PAUSED'
STATUS_STOPPED = 'STOPPED'

# Strategy statuses (in-cycle lifecycle)
STRATEGY_IDLE = 'IDLE'
STRATEGY_ENTRY_PENDING = 'ENTRY_PENDING'
STRATEGY_ENTRY_PARTIAL = 'ENTRY_PARTIAL'
STRATEGY_ENTRY_FAILED = 'ENTRY_FAILED'
STRATEGY_ACTIVE = 'ACTIVE'
STRATEGY_ADJUSTING = 'ADJUSTING'
STRATEGY_ROLL_PARTIAL = 'ROLL_PARTIAL'
STRATEGY_EXIT_PENDING = 'EXIT_PENDING'
STRATEGY_EXITED = 'EXITED'
STRATEGY_CYCLING = 'CYCLING'

# Exit reasons
EXIT_PROFIT_TARGET = 'profit_target'
EXIT_MAX_LOSS = 'max_loss'
EXIT_DTE_CLOSE = 'dte_close'
EXIT_MANUAL = 'manual'
EXIT_EMERGENCY = 'emergency_close'
EXIT_EXPIRED = 'expired'
EXIT_ROLLED = 'rolled'

# Adjustment types
ADJ_ROLL_CALL_UP = 'roll_call_up'
ADJ_ROLL_PUT_DOWN = 'roll_put_down'
ADJ_ROLL_BOTH = 'roll_both'
ADJ_EMERGENCY_CLOSE = 'emergency_close'

# Safety event levels
SAFETY_INFO = 'info'
SAFETY_WARNING = 'warning'
SAFETY_ALERT = 'alert'
SAFETY_CRITICAL = 'critical'

# Safety actions
SAFETY_ACTION_CONTINUE = 'continue'
SAFETY_ACTION_WARN = 'warn'
SAFETY_ACTION_PAUSE = 'pause'
SAFETY_ACTION_STOP = 'stop'

# Leg statuses
LEG_OPEN = 'open'
LEG_CLOSED = 'closed'
LEG_ROLLED = 'rolled'
LEG_EXPIRED = 'expired'

# Fill statuses
FILL_PENDING = 'pending'
FILL_FILLED = 'filled'
FILL_CANCELLED = 'cancelled'
FILL_FAILED = 'failed'
