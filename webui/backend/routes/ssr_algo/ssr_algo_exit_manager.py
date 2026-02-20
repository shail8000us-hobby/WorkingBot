"""
SSR ALGO Exit Manager - Profit Target, Stop Loss & Time-Based Exits

Implements automated exit rules for SSR Algo sessions:
- Profit target: Close when unrealized P&L >= X% of net premium
- Stop loss: Close when unrealized loss >= X% of net premium
- DTE exit: Close when days to expiry <= threshold
- Manual exit: Force close all positions on demand

Created: February 20, 2026
Phase 2 of SSR Algo Development Plan
"""

import logging
import sys
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from .ssr_algo_payoff import parse_symbol, get_contract_multiplier, CONTRACT_MULTIPLIERS
from .ssr_algo_engine import normalize_expiry_format

log = logging.getLogger('ssr_algo_exit_manager')

IST = ZoneInfo('Asia/Kolkata')

# Default exit rules
DEFAULT_EXIT_RULES = {
    'profit_target_enabled': True,
    'profit_target_percent': 50,
    'stop_loss_enabled': True,
    'stop_loss_percent': 200,
    'dte_exit_enabled': True,
    'dte_exit_days': 3,
    'dte_exit_time': '14:00',
    'trailing_profit_enabled': False,
    'trailing_profit_percent': 20,
}

API_BASE_URL = 'http://localhost:5555'


class SSRExitManager:
    """
    Manages exit rules and execution for SSR Algo sessions.

    Checks profit target, stop loss, and DTE conditions every monitor cycle.
    When triggered, closes all open positions via market orders.
    """

    def __init__(self, api_base_url: str = None):
        self.api_base_url = api_base_url or API_BASE_URL

    def calculate_dte(self, expiry: str) -> float:
        """
        Calculate fractional days to expiry.

        Args:
            expiry: Expiry date in DDMMYYYY or DDMMYY format

        Returns:
            Fractional days to expiry (e.g., 3.5)
        """
        try:
            normalized = normalize_expiry_format(expiry)
            expiry_dt = datetime.strptime(normalized, '%d%m%Y')
            # Expiry at 5:30 PM IST
            expiry_dt = expiry_dt.replace(hour=17, minute=30, tzinfo=IST)
            now = datetime.now(IST)
            diff = expiry_dt - now
            return max(diff.total_seconds() / 86400, 0.0)
        except Exception as e:
            log.warning(f"Could not calculate DTE for {expiry}: {e}")
            return 999.0  # Safe fallback — don't trigger DTE exit on error

    def check_exit_conditions(self, session: Dict) -> Dict:
        """
        Check all exit rules in priority order.

        Priority:
        1. DTE EXIT (highest — gamma risk near expiry)
        2. STOP LOSS (prevent catastrophic loss)
        3. PROFIT TARGET (take profits)

        Args:
            session: SSR Algo session data with live_pnl populated

        Returns:
            {
                'should_exit': bool,
                'reason': str or None,
                'details': dict
            }
        """
        exit_rules = session.get('exit_rules', DEFAULT_EXIT_RULES)
        expiry = session.get('expiry', '')
        live_pnl = session.get('live_pnl', {})
        net_premium = session.get('net_premium', 0)

        # 1. DTE EXIT — highest priority
        if exit_rules.get('dte_exit_enabled', True):
            dte = self.calculate_dte(expiry)
            dte_threshold = exit_rules.get('dte_exit_days', 3)

            if dte <= dte_threshold:
                # Check time condition if specified
                dte_exit_time = exit_rules.get('dte_exit_time', '14:00')
                now_ist = datetime.now(IST)
                try:
                    exit_hour, exit_min = map(int, dte_exit_time.split(':'))
                    exit_time_today = now_ist.replace(hour=exit_hour, minute=exit_min,
                                                       second=0, microsecond=0)
                    # On the threshold day, only exit after the configured time
                    # On days closer to expiry, exit immediately
                    if dte < dte_threshold or now_ist >= exit_time_today:
                        return {
                            'should_exit': True,
                            'reason': 'DTE_EXIT',
                            'details': {
                                'dte': round(dte, 2),
                                'threshold': dte_threshold,
                                'message': f'DTE {dte:.1f} <= {dte_threshold} day threshold'
                            }
                        }
                except (ValueError, AttributeError):
                    # If time parsing fails, still exit based on DTE alone
                    return {
                        'should_exit': True,
                        'reason': 'DTE_EXIT',
                        'details': {
                            'dte': round(dte, 2),
                            'threshold': dte_threshold,
                            'message': f'DTE {dte:.1f} <= {dte_threshold} day threshold'
                        }
                    }

        # Need valid P&L data for remaining checks
        unrealized_pnl = live_pnl.get('unrealized_pnl')
        if unrealized_pnl is None or net_premium == 0:
            return {'should_exit': False, 'reason': None, 'details': {}}

        # 2. STOP LOSS
        if exit_rules.get('stop_loss_enabled', True):
            stop_loss_pct = exit_rules.get('stop_loss_percent', 200)
            stop_loss_threshold = net_premium * stop_loss_pct / 100

            if unrealized_pnl < 0 and abs(unrealized_pnl) >= stop_loss_threshold:
                return {
                    'should_exit': True,
                    'reason': 'STOP_LOSS',
                    'details': {
                        'unrealized_pnl': round(unrealized_pnl, 4),
                        'net_premium': round(net_premium, 4),
                        'stop_loss_percent': stop_loss_pct,
                        'threshold': round(stop_loss_threshold, 4),
                        'message': f'Loss ${abs(unrealized_pnl):.2f} >= {stop_loss_pct}% of premium ${net_premium:.2f}'
                    }
                }

        # 3. PROFIT TARGET
        if exit_rules.get('profit_target_enabled', True):
            profit_target_pct = exit_rules.get('profit_target_percent', 50)
            profit_threshold = net_premium * profit_target_pct / 100

            if unrealized_pnl > 0 and unrealized_pnl >= profit_threshold:
                return {
                    'should_exit': True,
                    'reason': 'PROFIT_TARGET',
                    'details': {
                        'unrealized_pnl': round(unrealized_pnl, 4),
                        'net_premium': round(net_premium, 4),
                        'profit_target_percent': profit_target_pct,
                        'threshold': round(profit_threshold, 4),
                        'message': f'Profit ${unrealized_pnl:.2f} >= {profit_target_pct}% of premium ${net_premium:.2f}'
                    }
                }

        return {'should_exit': False, 'reason': None, 'details': {}}

    def execute_full_exit(self, session_id: str, reason: str) -> Dict:
        """
        Close ALL open positions for a session.

        For each open leg:
        - Short positions (size < 0): place BUY market order
        - Long positions (size > 0): place SELL market order

        Args:
            session_id: Session ID
            reason: Exit reason (PROFIT_TARGET, STOP_LOSS, DTE_EXIT, MANUAL_EXIT)

        Returns:
            {
                'success': bool,
                'orders_placed': int,
                'exit_orders': list,
                'error': str (if failed)
            }
        """
        from .ssr_algo_storage import get_storage

        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return {'success': False, 'error': f'Session not found: {session_id}', 'orders_placed': 0}

        positions = session.get('positions', [])
        if not positions:
            return {'success': True, 'orders_placed': 0, 'exit_orders': [], 'message': 'No positions to close'}

        # Collect all open legs that need closing
        exit_orders = []
        leg_keys = ['atm_ce', 'atm_pe', 'otm_ce_buy', 'otm_pe_buy', 'far_otm_ce', 'far_otm_pe']

        for position_group in positions:
            for leg_key in leg_keys:
                leg = position_group.get(leg_key)
                if not leg or not isinstance(leg, dict):
                    continue

                symbol = leg.get('symbol')
                size = leg.get('size', 0)

                if not symbol or size == 0:
                    continue

                # Skip already closed legs
                if leg.get('closed', False):
                    continue

                # Determine exit side
                if size < 0:
                    exit_side = 'buy'
                    exit_size = abs(size)
                else:
                    exit_side = 'sell'
                    exit_size = abs(size)

                exit_orders.append({
                    'symbol': symbol,
                    'size': exit_size,
                    'side': exit_side,
                    'leg_key': leg_key,
                    'original_size': size,
                    'trigger_id': position_group.get('trigger_id', 0)
                })

        if not exit_orders:
            return {'success': True, 'orders_placed': 0, 'exit_orders': [], 'message': 'No open legs to close'}

        # Place exit orders via batch_add with market preference
        try:
            batch_payload = {
                'orders': [
                    {
                        'symbol': o['symbol'],
                        'size': o['size'],
                        'side': o['side']
                    }
                    for o in exit_orders
                ],
                'order_preference': 'market_only',
                'confirm': True
            }

            log.info(f"[{session_id}] Placing {len(exit_orders)} exit orders (reason: {reason})")

            response = requests.post(
                f"{self.api_base_url}/api/options/batch_add",
                json=batch_payload,
                timeout=60
            )

            if response.status_code != 200:
                error_msg = f"Exit order API returned {response.status_code}: {response.text[:200]}"
                log.error(f"[{session_id}] {error_msg}")
                return {'success': False, 'error': error_msg, 'orders_placed': 0}

            result = response.json()

            if not result.get('success'):
                error_msg = result.get('error', 'Unknown batch_add error')
                log.error(f"[{session_id}] Exit orders failed: {error_msg}")
                return {'success': False, 'error': error_msg, 'orders_placed': 0}

            orders_placed = result.get('successful', 0)

            # Update session status
            storage.update_session(session_id, {
                'status': 'STOPPED',
                'stopped_at': datetime.utcnow().isoformat(),
                'stop_reason': f'Exit: {reason}',
                'exit_details': {
                    'reason': reason,
                    'orders_placed': orders_placed,
                    'exit_time': datetime.utcnow().isoformat(),
                    'live_pnl_at_exit': session.get('live_pnl', {}),
                    'live_greeks_at_exit': session.get('live_greeks', {})
                }
            })

            # Stop the monitor
            try:
                from .ssr_algo_monitor import stop_session_monitor
                stop_session_monitor(session_id)
            except Exception as e:
                log.warning(f"[{session_id}] Could not stop monitor after exit: {e}")

            log.info(f"[{session_id}] Exit complete: {orders_placed} orders placed, reason: {reason}")

            return {
                'success': True,
                'orders_placed': orders_placed,
                'exit_orders': exit_orders,
                'reason': reason,
                'batch_result': result
            }

        except requests.exceptions.Timeout:
            error_msg = 'Exit order request timed out (60s)'
            log.error(f"[{session_id}] {error_msg}")
            return {'success': False, 'error': error_msg, 'orders_placed': 0}
        except Exception as e:
            log.exception(f"[{session_id}] Exit execution error")
            return {'success': False, 'error': str(e), 'orders_placed': 0}

    def execute_roll(self, session_id: str, next_expiry: str) -> Dict:
        """
        Roll current session to next expiry cycle.

        When DTE <= 7 and session is profitable, close all current positions
        and auto-create + start a new session at the next expiry.

        Args:
            session_id: Current session ID
            next_expiry: Next expiry date in DDMMYYYY or DDMMYY format

        Returns:
            {
                'success': bool,
                'new_session_id': str or None,
                'realized_pnl': float,
                'error': str (if failed)
            }
        """
        from .ssr_algo_storage import get_storage

        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return {'success': False, 'error': f'Session not found: {session_id}'}

        # Step 1: Close all current positions
        log.info(f"[{session_id}] Rolling to next expiry {next_expiry} — closing positions...")
        exit_result = self.execute_full_exit(session_id, 'ROLL_TO_NEXT')

        if not exit_result.get('success'):
            return {
                'success': False,
                'error': f"Failed to close positions: {exit_result.get('error')}",
                'new_session_id': None
            }

        # Capture realized P&L
        live_pnl = session.get('live_pnl', {})
        realized_pnl = live_pnl.get('total_pnl', 0)

        # Step 2: Create new session with same config but new expiry
        try:
            new_session = storage.create_session(
                underlying=session.get('underlying', 'BTC'),
                expiry=next_expiry,
                strike_config=session.get('strike_config', {}),
                auto_loop_rounds=session.get('auto_loop_rounds', 2),
                dwell_time_minutes=session.get('dwell_time_minutes', 10),
                price_tolerance=session.get('price_tolerance', 500),
                start_time=session.get('start_time'),
                end_time=session.get('end_time'),
                exit_rules=session.get('exit_rules'),
                delta_hedge_config=session.get('delta_hedge_config'),
                iv_filter_config=session.get('iv_filter_config'),
            )
            new_session_id = new_session.get('session_id')
        except Exception as e:
            log.exception(f"[{session_id}] Failed to create rolled session")
            return {
                'success': False,
                'error': f'Failed to create new session: {e}',
                'new_session_id': None,
                'realized_pnl': realized_pnl
            }

        # Step 3: Link sessions
        storage.update_session(session_id, {'rolled_to': new_session_id})
        storage.update_session(new_session_id, {
            'rolled_from': session_id,
            'cumulative_realized_pnl': (
                session.get('cumulative_realized_pnl', 0) + realized_pnl
            )
        })

        log.info(f"[{session_id}] Roll complete → new session {new_session_id} at expiry {next_expiry}")

        return {
            'success': True,
            'new_session_id': new_session_id,
            'realized_pnl': realized_pnl,
            'old_session_id': session_id,
            'next_expiry': next_expiry
        }


# Singleton instance
_exit_manager = None

def get_exit_manager() -> SSRExitManager:
    """Get singleton SSRExitManager instance."""
    global _exit_manager
    if _exit_manager is None:
        _exit_manager = SSRExitManager()
    return _exit_manager
