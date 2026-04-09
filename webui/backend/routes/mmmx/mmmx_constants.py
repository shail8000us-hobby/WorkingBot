"""
MMMX Constants

Shared constants for the MMMX algorithm.
Spec: MMMX_COMPLETE.md — Section 2 (Capital Structure) + Section 4 (Engine)

Rules:
  - LOT_SIZE_BTC is NEVER inlined in formulas — always imported from here.
  - All string enums live here; no magic strings elsewhere.
  - All TTLs and fee rates sourced from here.
"""

# ── Position sizing ────────────────────────────────────────────────────────────
# Delta Exchange BTC Options: 1 lot = 0.001 BTC.
# USD value of N lots: premium_per_btc × N × LOT_SIZE_BTC
LOT_SIZE_BTC = 0.001

# ── Schema version ─────────────────────────────────────────────────────────────
SCHEMA_VERSION = 1

# ── Session lifecycle states ───────────────────────────────────────────────────
class SessionStatus:
    DRAFT        = 'DRAFT'
    GATES_PASSED = 'GATES_PASSED'
    RUNNING      = 'RUNNING'
    PAUSED       = 'PAUSED'
    COMPLETE     = 'COMPLETE'
    ERROR        = 'ERROR'

VALID_SESSION_STATUSES = {
    SessionStatus.DRAFT,
    SessionStatus.GATES_PASSED,
    SessionStatus.RUNNING,
    SessionStatus.PAUSED,
    SessionStatus.COMPLETE,
    SessionStatus.ERROR,
}

# Legal state transitions. Any other transition is a bug.
LEGAL_TRANSITIONS = {
    SessionStatus.DRAFT:        {SessionStatus.GATES_PASSED, SessionStatus.ERROR},
    SessionStatus.GATES_PASSED: {SessionStatus.RUNNING, SessionStatus.ERROR},
    SessionStatus.RUNNING:      {SessionStatus.PAUSED, SessionStatus.COMPLETE, SessionStatus.ERROR},
    SessionStatus.PAUSED:       {SessionStatus.RUNNING, SessionStatus.COMPLETE, SessionStatus.ERROR},
    SessionStatus.COMPLETE:     set(),   # terminal
    SessionStatus.ERROR:        set(),   # terminal
}

# ── Tranche / position statuses ────────────────────────────────────────────────
class TrncStatus:
    ACTIVE       = 'ACTIVE'
    CLOSED       = 'CLOSED'
    REPOSITIONED = 'REPOSITIONED'
    REDUCED      = 'REDUCED'
    PARTIAL      = 'PARTIAL'

class TrncType:
    DEPLOYMENT = 'deployment'
    RECOVERY   = 'recovery'

class HedgeStatus:
    ACTIVE     = 'ACTIVE'
    DISPLACED  = 'DISPLACED'
    ORPHANED   = 'ORPHANED'
    CLOSED     = 'CLOSED'

# ── Close reasons ──────────────────────────────────────────────────────────────
class CloseReason:
    PROFIT_BOOKING  = 'profit_booking'
    HARD_STOP       = 'hard_stop'
    DTE             = 'dte'
    SHIELD_ROLLOVER = 'shield_rollover'
    IV_CATASTROPHE  = 'iv_catastrophe'
    NEAR_ITM        = 'near_itm'
    MANUAL          = 'manual'

# ── Whipsaw levels ─────────────────────────────────────────────────────────────
class WhipsawLevel:
    NORMAL   = 'NORMAL'    # score 0–1
    CAUTION  = 'CAUTION'   # score 2
    RESTRICT = 'RESTRICT'  # score 3
    COOLDOWN = 'COOLDOWN'  # score 4+

# Whipsaw score thresholds (matches _DEFAULT_PARAMS; also importable as constants)
WHIPSAW_CAUTION_SCORE  = 2
WHIPSAW_RESTRICT_SCORE = 3
WHIPSAW_COOLDOWN_SCORE = 4

# ── Circuit breaker states ─────────────────────────────────────────────────────
class CBState:
    CLOSED    = 'CLOSED'
    HALF_OPEN = 'HALF_OPEN'
    OPEN      = 'OPEN'

# ── Trigger names ──────────────────────────────────────────────────────────────
class TriggerName:
    DTE_CLOSE       = 'DTE_CLOSE'
    HARD_STOP       = 'HARD_STOP'
    IV_CATASTROPHE  = 'IV_CATASTROPHE'
    NEAR_ITM        = 'NEAR_ITM'
    DEPLOY_TRANCHE  = 'DEPLOY_TRANCHE'
    IV_SPIKE        = 'IV_SPIKE'
    REPOSITION      = 'REPOSITION'
    PORTFOLIO_DELTA = 'PORTFOLIO_DELTA'
    DELTA_DRIFT     = 'DELTA_DRIFT'

# ── Fee rates (from spec Section 4) ───────────────────────────────────────────
FEE_RATE_MAKER = 0.0002   # 0.02%
FEE_RATE_TAKER = 0.0005   # 0.05%

# ── Hard limits (non-negotiable) ───────────────────────────────────────────────
CLOSE_AT_DTE_HARD_MIN = 7           # close_at_dte cannot be set below this
TOTAL_BUDGET_LOTS     = 100         # per-side tranche budget
RESERVE_LOTS_DEFAULT  = 30          # per-side ATM shield reserve
TRANCHE_COUNT         = 10          # 10 tranches × 10 lots = 100 lots

# ── Deployment queue ───────────────────────────────────────────────────────────
DEPLOYMENT_RETRACEMENT_THRESHOLD_PCT = 0.5   # clear queue if move retraces > 0.5%
MAX_DEPLOYMENTS_PER_24H              = 2

# ── Hedge thresholds ───────────────────────────────────────────────────────────
HEDGE_CAPACITY_THRESHOLD_LOTS = 50  # Tr5+ (>=50 lots deployed) triggers hedging

# ── Execution defaults ─────────────────────────────────────────────────────────
SMART_EXECUTE_REPRICE_ATTEMPTS   = 4
SHIELD_BUYBACK_REPRICE_ATTEMPTS  = 10
SHIELD_SELL_REPRICE_ATTEMPTS     = 10
FILL_TIMEOUT_SECS                = 30    # used by ATM shield (urgent, fast reprice)
# Tranche deployment fill timeout — 50 DTE monthly options are illiquid; allow
# the limit order to sit at mid for 8.5 minutes per reprice attempt.
# 4 attempts × 510 s = ~34 minutes total patience before market fallback.
TRANCHE_FILL_TIMEOUT_SECS        = 510
BEING_CLOSED_TTL_SECS            = 180

# ── Naked position watchdog ────────────────────────────────────────────────────
NAKED_WATCHDOG_WARN_MINS         = 30
NAKED_WATCHDOG_CRITICAL_MINS     = 120

# ── WebSocket / Telegram prefixes ──────────────────────────────────────────────
WS_EVENT_PREFIX    = 'mmmx_'
TELEGRAM_TAG       = '[MMMX]'
TELEGRAM_DEDUP_TTL = 30     # seconds

# ── Activity log ───────────────────────────────────────────────────────────────
MAX_ACTIVITY_ENTRIES = 500

# ── DB path helpers ────────────────────────────────────────────────────────────
import os as _os
_BACKEND_DATA_DIR = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))), 'data'
)
DB_FILE           = _os.path.join(_BACKEND_DATA_DIR, 'mmmx_sessions.db')
ACTIVITY_LOG_FILE = _os.path.join(_BACKEND_DATA_DIR, 'mmmx_activity_log.json')
AUDIT_LOG_FILE    = _os.path.join(_BACKEND_DATA_DIR, 'mmmx_audit_log.jsonl')
