"""
MMM Margin Guardian — Real-time Margin Monitoring & Auto-Defense

Queries the exchange for actual margin utilization every heartbeat and
enforces tier-based defensive actions:

  GREEN    (< green_pct):    Normal operation
  YELLOW   (>= yellow_pct):  Block new sells, log caution
  ORANGE   (>= orange_pct):  Force auto wind-down (aggressive buyback),
                              regardless of time-to-expiry
  RED      (>= red_pct):     Emergency reduce — taker orders, close all
  CRITICAL (>= critical_pct): Survival mode — close all + stop session

All thresholds are user-configurable per session via WebUI.

Margin utilization formula:
  utilization% = (position_margin + order_margin) / net_equity * 100

Where net_equity = balance + unrealized_pnl (from exchange meta).

If net_equity is zero or negative (liquidation territory),
utilization is forced to 100%.

Created: February 20, 2026
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Any, Optional, List

log = logging.getLogger('mmm_margin_guardian')


# ─────────────────────────────────────────────────────────────────────
# Tier names (ordered by severity)
# ─────────────────────────────────────────────────────────────────────
TIER_GREEN    = 'GREEN'
TIER_YELLOW   = 'YELLOW'
TIER_ORANGE   = 'ORANGE'
TIER_RED      = 'RED'
TIER_CRITICAL = 'CRITICAL'

# Ordered list for comparison
_TIER_ORDER = [TIER_GREEN, TIER_YELLOW, TIER_ORANGE, TIER_RED, TIER_CRITICAL]


def tier_severity(tier: str) -> int:
    """Return numeric severity (0=GREEN, 4=CRITICAL). Unknown → -1."""
    try:
        return _TIER_ORDER.index(tier)
    except ValueError:
        return -1


# ─────────────────────────────────────────────────────────────────────
# Default thresholds (user overrideable via session params)
# ─────────────────────────────────────────────────────────────────────

MARGIN_PARAM_DEFAULTS: Dict[str, Any] = {
    'margin_monitor_enabled': False,       # Disabled until user opts in
    'margin_green_pct':       50.0,        # Below this = fully normal
    'margin_yellow_pct':      60.0,        # Caution — block new sells
    'margin_orange_pct':      75.0,        # Auto wind-down (aggressive buyback)
    'margin_red_pct':         85.0,        # Emergency reduce (taker orders)
    'margin_critical_pct':    90.0,        # Survival — close ALL, stop session
    'margin_target_pct':      50.0,        # Target to wind down TO
    'margin_check_interval_beats': 1,      # Check every N heartbeats
}


def get_margin_param_defaults() -> Dict[str, Any]:
    """Return a copy of the default margin params for session creation."""
    return dict(MARGIN_PARAM_DEFAULTS)


# ─────────────────────────────────────────────────────────────────────
# Fetch margin from exchange
# ─────────────────────────────────────────────────────────────────────

async def fetch_margin_utilization(rest_client) -> Dict[str, Any]:
    """
    Query Delta Exchange wallet endpoint to compute actual margin utilization.

    Args:
        rest_client: An AsyncDeltaClient instance bound to the current event loop.

    Returns:
        {
            'success': True/False,
            'utilization_pct': float,     # 0-100+ (can exceed 100 in liquidation)
            'position_margin': float,
            'order_margin': float,
            'available_balance': float,
            'balance': float,
            'net_equity': float,
            'blocked_margin': float,
            'portfolio_margin': float,
            'timestamp': float,           # time.time()
            'error': str | None,
        }
    """
    result = {
        'success': False,
        'utilization_pct': 0.0,
        'position_margin': 0.0,
        'order_margin': 0.0,
        'available_balance': 0.0,
        'balance': 0.0,
        'net_equity': 0.0,
        'blocked_margin': 0.0,
        'portfolio_margin': 0.0,
        'timestamp': time.time(),
        'error': None,
    }

    try:
        # Use get_wallet_balances_full to get meta (net_equity) along with wallets
        if hasattr(rest_client, 'get_wallet_balances_full'):
            wallet_response = await rest_client.get_wallet_balances_full()
        else:
            wallet_response = await rest_client.get_wallet_balances()

        # The response can be:
        #  - A list of wallets directly (result already extracted by client)
        #  - A dict with 'result' key
        wallets = []
        meta = {}

        if isinstance(wallet_response, list):
            wallets = wallet_response
        elif isinstance(wallet_response, dict):
            if wallet_response.get('success') is False:
                result['error'] = f"API error: {wallet_response}"
                return result
            wallets = wallet_response.get('result', [])
            meta = wallet_response.get('meta', {})
            # If wallets is itself a dict (single wallet), wrap it
            if isinstance(wallets, dict):
                wallets = [wallets]

        if not wallets:
            result['error'] = 'No wallets returned'
            return result

        # Find the active wallet (USD/USDT — the one with non-zero balance)
        # Delta Exchange India uses USD wallet for trading margin.
        # wallets[0] is often ETH with all zeros — must find the right one.
        wallet = None
        for w in wallets:
            sym = (w.get('asset_symbol') or '').upper()
            if sym in ('USD', 'USDT'):
                wallet = w
                break
        if wallet is None:
            # Fallback: pick the wallet with largest balance
            wallet = max(wallets, key=lambda w: float(w.get('balance', 0) or 0))

        balance = float(wallet.get('balance', 0) or 0)
        available = float(wallet.get('available_balance', 0) or 0)
        pos_margin = float(wallet.get('position_margin', 0) or 0)
        order_margin = float(wallet.get('order_margin', 0) or 0)
        blocked = float(wallet.get('blocked_margin', 0) or 0)
        portfolio = float(wallet.get('portfolio_margin', 0) or 0)
        # Cross-margin fields (used in portfolio margin mode)
        cross_pos = float(wallet.get('cross_position_margin', 0) or 0)
        cross_order = float(wallet.get('cross_order_margin', 0) or 0)

        # Net equity from meta (more accurate — includes unrealized P&L)
        net_equity = float(meta.get('net_equity', 0) or 0)
        if net_equity <= 0:
            # Fallback: use balance (less accurate but non-zero)
            net_equity = balance

        # Compute total margin used.
        # In portfolio margin mode, position_margin and order_margin may be 0.
        # The real margin is in blocked_margin / portfolio_margin.
        # Use whichever is non-zero: portfolio > blocked > (pos + order + cross).
        if portfolio > 0:
            total_used = portfolio
        elif blocked > 0:
            total_used = blocked
        else:
            total_used = pos_margin + order_margin + cross_pos + cross_order

        # Compute utilization
        if net_equity > 0:
            utilization = (total_used / net_equity) * 100.0
        else:
            # Net equity zero or negative = liquidation territory
            utilization = 100.0

        result.update({
            'success': True,
            'utilization_pct': round(utilization, 2),
            'position_margin': pos_margin,
            'order_margin': order_margin,
            'available_balance': available,
            'balance': balance,
            'net_equity': net_equity,
            'blocked_margin': blocked,
            'portfolio_margin': portfolio,
            'cross_position_margin': cross_pos,
            'cross_order_margin': cross_order,
            'total_margin_used': round(total_used, 6),
            'asset_symbol': wallet.get('asset_symbol', 'USD'),
        })

        return result

    except Exception as e:
        log.error(f"Margin fetch failed: {e}")
        result['error'] = str(e)
        return result


# ─────────────────────────────────────────────────────────────────────
# Tier evaluation
# ─────────────────────────────────────────────────────────────────────

def evaluate_margin_tier(
    utilization_pct: float,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Determine the current margin tier and required actions.

    Args:
        utilization_pct: Current margin utilization (0-100+)
        params: Session params dict containing margin thresholds

    Returns:
        {
            'tier': 'GREEN' | 'YELLOW' | 'ORANGE' | 'RED' | 'CRITICAL',
            'utilization_pct': float,
            'actions': List[str],
                Possible actions:
                  'normal'           — no intervention
                  'block_sells'      — prevent new sell orders
                  'auto_wind_down'   — force aggressive buyback
                  'emergency_reduce' — use taker orders to close positions
                  'survival_close_all'— close ALL positions, stop session
            'threshold_crossed': float,  # The threshold value that was crossed
            'next_threshold': float | None,  # Next higher threshold
            'headroom_pct': float,      # % remaining before next tier
        }
    """
    # Read thresholds with defaults
    green   = params.get('margin_green_pct',    MARGIN_PARAM_DEFAULTS['margin_green_pct'])
    yellow  = params.get('margin_yellow_pct',   MARGIN_PARAM_DEFAULTS['margin_yellow_pct'])
    orange  = params.get('margin_orange_pct',   MARGIN_PARAM_DEFAULTS['margin_orange_pct'])
    red     = params.get('margin_red_pct',      MARGIN_PARAM_DEFAULTS['margin_red_pct'])
    critical = params.get('margin_critical_pct', MARGIN_PARAM_DEFAULTS['margin_critical_pct'])

    u = utilization_pct

    if u >= critical:
        tier = TIER_CRITICAL
        actions = ['survival_close_all']
        threshold = critical
        next_t = None
        headroom = 0.0
    elif u >= red:
        tier = TIER_RED
        actions = ['emergency_reduce']
        threshold = red
        next_t = critical
        headroom = critical - u
    elif u >= orange:
        tier = TIER_ORANGE
        actions = ['block_sells', 'auto_wind_down']
        threshold = orange
        next_t = red
        headroom = red - u
    elif u >= yellow:
        tier = TIER_YELLOW
        actions = ['block_sells']
        threshold = yellow
        next_t = orange
        headroom = orange - u
    else:
        tier = TIER_GREEN
        actions = ['normal']
        threshold = green
        next_t = yellow
        headroom = yellow - u

    return {
        'tier': tier,
        'utilization_pct': round(u, 2),
        'actions': actions,
        'threshold_crossed': threshold,
        'next_threshold': next_t,
        'headroom_pct': round(max(headroom, 0), 2),
    }


# ─────────────────────────────────────────────────────────────────────
# Lots-to-close calculator for margin reduction
# ─────────────────────────────────────────────────────────────────────

def estimate_lots_to_close(
    session: Dict,
    current_util: float,
    target_util: float,
) -> Dict[str, int]:
    """
    Estimate how many lots to close per side to reach target utilization.

    Uses a proportional approach:
      reduction_ratio = (current - target) / current
      lots_to_close_per_side = ceil(active_lots * reduction_ratio)

    Returns:
        {'ce': int, 'pe': int}  — lots to close on each side
    """
    import math

    if current_util <= target_util or current_util <= 0:
        return {'ce': 0, 'pe': 0}

    reduction_ratio = (current_util - target_util) / current_util
    # Apply at least a small minimum to ensure progress
    reduction_ratio = max(reduction_ratio, 0.1)

    result = {}
    for side in ['ce', 'pe']:
        active = session.get(side, {}).get('active_lots', 0)
        frozen_lots = sum(
            f.get('lots', 0)
            for f in session.get(side, {}).get('frozen_positions', [])
        )
        total = active + frozen_lots
        lots_to_close = math.ceil(total * reduction_ratio)
        result[side] = min(lots_to_close, total)  # Never close more than we have

    return result


# ─────────────────────────────────────────────────────────────────────
# Main heartbeat integration — called from MMMMonitor
# ─────────────────────────────────────────────────────────────────────

class MarginGuardian:
    """
    Per-session margin guardian, integrated into the heartbeat loop.

    Usage in MMMMonitor:
        self._margin_guardian = MarginGuardian(session_id)

        # At start of each heartbeat:
        result = await self._margin_guardian.check(
            session, rest_client, heartbeat_number
        )
        if result['require_action']:
            # Handle based on result['tier']
    """

    def __init__(self, session_id: str):
        self._sid = session_id
        self._last_tier = TIER_GREEN
        self._last_util = 0.0
        self._last_check_beat = 0
        self._consecutive_critical = 0

    async def check(
        self,
        session: Dict,
        rest_client,
        heartbeat_number: int,
    ) -> Dict[str, Any]:
        """
        Perform a margin check. Called from the heartbeat loop.

        Returns:
            {
                'checked': bool,         # False if skipped (not enabled, or not due)
                'require_action': bool,   # True if tier requires intervention
                'tier': str,
                'prev_tier': str,
                'tier_changed': bool,
                'utilization_pct': float,
                'actions': List[str],
                'margin_data': Dict,      # Raw exchange data
                'lots_to_close': Dict,    # {'ce': int, 'pe': int} if reduction needed
                'error': str | None,
            }
        """
        params = session.get('params', {})

        # Skip if disabled
        if not params.get('margin_monitor_enabled', False):
            return {'checked': False, 'require_action': False, 'tier': TIER_GREEN,
                    'prev_tier': TIER_GREEN, 'tier_changed': False,
                    'utilization_pct': 0, 'actions': ['normal'],
                    'margin_data': {}, 'lots_to_close': {'ce': 0, 'pe': 0},
                    'error': None}

        # Check interval (some users may want less frequent checks)
        interval = params.get('margin_check_interval_beats', 1)
        if interval > 1 and (heartbeat_number - self._last_check_beat) < interval:
            return {'checked': False, 'require_action': False, 'tier': self._last_tier,
                    'prev_tier': self._last_tier, 'tier_changed': False,
                    'utilization_pct': self._last_util, 'actions': ['normal'],
                    'margin_data': {}, 'lots_to_close': {'ce': 0, 'pe': 0},
                    'error': None}

        self._last_check_beat = heartbeat_number

        # Fetch from exchange
        margin_data = await fetch_margin_utilization(rest_client)

        if not margin_data['success']:
            log.warning(
                f"[{self._sid}] Margin fetch failed: {margin_data.get('error')} "
                f"— keeping last tier {self._last_tier}"
            )
            return {'checked': True, 'require_action': False, 'tier': self._last_tier,
                    'prev_tier': self._last_tier, 'tier_changed': False,
                    'utilization_pct': self._last_util, 'actions': ['normal'],
                    'margin_data': margin_data,
                    'lots_to_close': {'ce': 0, 'pe': 0},
                    'error': margin_data.get('error')}

        util_pct = margin_data['utilization_pct']
        tier_result = evaluate_margin_tier(util_pct, params)
        tier = tier_result['tier']

        prev_tier = self._last_tier
        tier_changed = tier != prev_tier
        self._last_tier = tier
        self._last_util = util_pct

        # Track consecutive critical beats
        if tier == TIER_CRITICAL:
            self._consecutive_critical += 1
        else:
            self._consecutive_critical = 0

        # T1-3: After N consecutive CRITICAL beats, escalate to force_stop_session
        consecutive_critical_threshold = params.get('consecutive_critical_threshold', 3)
        force_stop = False
        if self._consecutive_critical >= consecutive_critical_threshold:
            force_stop = True
            log.error(
                f"[{self._sid}] MARGIN CONSECUTIVE CRITICAL: {self._consecutive_critical} beats "
                f"at CRITICAL tier — escalating to force_stop_session"
            )

        # Compute lots to close if in reduction tiers
        lots_to_close = {'ce': 0, 'pe': 0}
        target_pct = params.get('margin_target_pct', MARGIN_PARAM_DEFAULTS['margin_target_pct'])

        if tier in (TIER_ORANGE, TIER_RED, TIER_CRITICAL):
            lots_to_close = estimate_lots_to_close(session, util_pct, target_pct)

        require_action = tier != TIER_GREEN

        if tier_changed:
            log.warning(
                f"[{self._sid}] MARGIN TIER CHANGE: {prev_tier} → {tier} "
                f"(utilization: {util_pct:.1f}%, "
                f"equity: ${margin_data['net_equity']:.2f}, "
                f"pos_margin: ${margin_data['position_margin']:.2f})"
            )

        actions = list(tier_result['actions'])
        if force_stop and 'force_stop_session' not in actions:
            actions.append('force_stop_session')

        return {
            'checked': True,
            'require_action': require_action,
            'tier': tier,
            'prev_tier': prev_tier,
            'tier_changed': tier_changed,
            'utilization_pct': util_pct,
            'actions': actions,
            'margin_data': margin_data,
            'lots_to_close': lots_to_close,
            'headroom_pct': tier_result['headroom_pct'],
            'consecutive_critical': self._consecutive_critical,
            'error': None,
        }

    @property
    def last_tier(self) -> str:
        return self._last_tier

    @property
    def last_utilization(self) -> float:
        return self._last_util
