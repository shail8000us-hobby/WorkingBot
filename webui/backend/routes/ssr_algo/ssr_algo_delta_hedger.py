"""
SSR ALGO Delta Hedger - Continuous Delta-Based Hedging Engine

Replaces the blunt "payoff zone + dwell time" trigger with intelligent,
continuous delta-based hedging. Three tiers:
- Micro hedge (|delta| > 0.20): Roll untested side far OTM (~$50-100)
- Standard hedge (|delta| > 0.40): Roll tested side ATM (~$100-200)
- Emergency hedge (|delta| > 0.80): Surgical adjustment ($200-400)

Created: February 20, 2026
Phase 3 of SSR Algo Development Plan
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

log = logging.getLogger('ssr_algo_delta_hedger')

IST = ZoneInfo('Asia/Kolkata')

API_BASE_URL = 'http://localhost:5555'

# Default delta hedge configuration
DEFAULT_DELTA_HEDGE_CONFIG = {
    'enabled': True,
    'micro_hedge_threshold': 0.20,
    'standard_hedge_threshold': 0.40,
    'emergency_hedge_threshold': 0.80,
    'hedge_cooldown_minutes': 5,
    'max_hedges_per_day': 15,
    'hedge_method': 'roll_leg',
}


class SSRDeltaHedger:
    """
    Manages continuous delta-based hedging for SSR Algo positions.

    Monitors portfolio delta and triggers appropriate hedge actions:
    - Micro: Roll untested side far OTM closer to collect premium
    - Standard: Roll tested side ATM to fresh strikes
    - Emergency: Surgical adjustment of the troubled side
    """

    def __init__(self, api_base_url: str = None):
        self.api_base_url = api_base_url or API_BASE_URL
        self._chain_service = None
        self._strike_selector = None

    @property
    def chain_service(self):
        if self._chain_service is None:
            from webui.backend.options_chain.chain_service import OptionsChainService
            self._chain_service = OptionsChainService()
        return self._chain_service

    @property
    def strike_selector(self):
        if self._strike_selector is None:
            from .ssr_algo_engine import get_strike_selector
            self._strike_selector = get_strike_selector()
        return self._strike_selector

    def check_delta_hedge_needed(self, session: Dict,
                                  override_threshold: float = None) -> Dict:
        """
        Check if a delta hedge is needed based on current portfolio delta.

        Args:
            session: SSR Algo session data with live_greeks populated
            override_threshold: Optional DTE-adjusted threshold override

        Returns:
            {
                'hedge_needed': bool,
                'hedge_type': 'micro' | 'standard' | 'emergency' | None,
                'current_delta': float,
                'threshold_breached': float,
                'direction': 'bullish' | 'bearish'
            }
        """
        config = session.get('delta_hedge_config', DEFAULT_DELTA_HEDGE_CONFIG)

        if not config.get('enabled', False):
            return {'hedge_needed': False, 'hedge_type': None}

        live_greeks = session.get('live_greeks', {})
        net_delta = live_greeks.get('net_delta', 0)
        abs_delta = abs(net_delta)

        # Determine direction
        direction = 'bullish' if net_delta > 0 else 'bearish'

        # Check cooldown
        last_hedge = session.get('last_hedge_time')
        if last_hedge:
            try:
                last_dt = datetime.fromisoformat(last_hedge)
                cooldown_min = config.get('hedge_cooldown_minutes', 5)
                if datetime.now() - last_dt < timedelta(minutes=cooldown_min):
                    return {'hedge_needed': False, 'hedge_type': None,
                            'reason': 'cooldown', 'current_delta': net_delta}
            except (ValueError, TypeError):
                pass

        # Check daily hedge count
        daily_count = session.get('daily_hedge_count', 0)
        max_daily = config.get('max_hedges_per_day', 15)
        if daily_count >= max_daily:
            return {'hedge_needed': False, 'hedge_type': None,
                    'reason': 'max_daily_reached', 'current_delta': net_delta}

        # Get thresholds (with optional DTE override)
        micro_threshold = override_threshold or config.get('micro_hedge_threshold', 0.20)
        standard_threshold = config.get('standard_hedge_threshold', 0.40)
        emergency_threshold = config.get('emergency_hedge_threshold', 0.80)

        # If override provided, scale standard/emergency proportionally
        if override_threshold:
            base_micro = config.get('micro_hedge_threshold', 0.20)
            if base_micro > 0:
                scale = override_threshold / base_micro
                standard_threshold = config.get('standard_hedge_threshold', 0.40) * scale
                emergency_threshold = config.get('emergency_hedge_threshold', 0.80) * scale

        # Check thresholds in descending priority
        if abs_delta >= emergency_threshold:
            return {
                'hedge_needed': True,
                'hedge_type': 'emergency',
                'current_delta': round(net_delta, 6),
                'threshold_breached': emergency_threshold,
                'direction': direction
            }
        elif abs_delta >= standard_threshold:
            return {
                'hedge_needed': True,
                'hedge_type': 'standard',
                'current_delta': round(net_delta, 6),
                'threshold_breached': standard_threshold,
                'direction': direction
            }
        elif abs_delta >= micro_threshold:
            return {
                'hedge_needed': True,
                'hedge_type': 'micro',
                'current_delta': round(net_delta, 6),
                'threshold_breached': micro_threshold,
                'direction': direction
            }

        return {
            'hedge_needed': False,
            'hedge_type': None,
            'current_delta': round(net_delta, 6),
            'direction': direction
        }

    def execute_micro_hedge(self, session: Dict, direction: str) -> Dict:
        """
        Execute a micro hedge — roll the untested side far OTM closer.

        If bullish (delta positive, price rallied):
            - Buy back far OTM PE sell (cheap, nearly worthless)
            - Sell new PE closer to ATM (captures more premium, reduces delta)
        If bearish (delta negative, price dropped):
            - Buy back far OTM CE sell
            - Sell new CE closer to ATM

        Args:
            session: Session data
            direction: 'bullish' or 'bearish'

        Returns:
            {'success': bool, 'orders_placed': int, 'cost': float, 'error': str}
        """
        session_id = session.get('session_id', '')
        underlying = session.get('underlying', 'BTC')
        expiry = session.get('expiry', '')

        # Find the leg to roll
        positions = session.get('positions', [])
        if not positions:
            return {'success': False, 'error': 'No positions', 'orders_placed': 0, 'cost': 0}

        # Use the latest position group
        latest_group = positions[-1]

        if direction == 'bullish':
            # Roll the far OTM PE sell closer
            target_leg_key = 'far_otm_pe'
            roll_direction = 'pe'
        else:
            # Roll the far OTM CE sell closer
            target_leg_key = 'far_otm_ce'
            roll_direction = 'ce'

        target_leg = latest_group.get(target_leg_key)
        if not target_leg or not target_leg.get('symbol'):
            return {'success': False, 'error': f'No {target_leg_key} leg found', 'orders_placed': 0, 'cost': 0}

        if target_leg.get('closed', False):
            return {'success': False, 'error': f'{target_leg_key} already closed', 'orders_placed': 0, 'cost': 0}

        # Get current chain to find new strike
        try:
            normalized_expiry = normalize_expiry_format(expiry)
            chain_data = self.chain_service.get_chain_data(underlying, normalized_expiry)
        except Exception as e:
            return {'success': False, 'error': f'Chain fetch failed: {e}', 'orders_placed': 0, 'cost': 0}

        spot_price = chain_data.get('spot_price', 0)
        chain = chain_data.get('chain', [])

        # Find ATM at current price
        atm_result = self.strike_selector.find_atm_strike(chain, spot_price)
        if not atm_result:
            return {'success': False, 'error': 'Could not find ATM', 'orders_placed': 0, 'cost': 0}

        current_atm = atm_result['strike']

        # For micro hedge, find a new far OTM at ~30-40% of ATM premium
        option_key = 'call' if roll_direction == 'ce' else 'put'
        atm_premium = atm_result.get(f'{option_key[0]}e_premium',
                                      atm_result.get('ce_premium', 0) if roll_direction == 'ce'
                                      else atm_result.get('pe_premium', 0))

        target_min = atm_premium * 0.25
        target_max = atm_premium * 0.40
        target_range = {'min': target_min, 'max': target_max}

        new_strike = self.strike_selector.find_otm_strike(
            chain, current_atm, target_range, roll_direction
        )

        if not new_strike:
            return {'success': False, 'error': f'Could not find new {roll_direction.upper()} strike',
                    'orders_placed': 0, 'cost': 0}

        # Place roll orders: close old + open new
        result = self._place_roll_orders(
            session_id=session_id,
            close_symbol=target_leg['symbol'],
            close_size=abs(target_leg['size']),
            close_side='buy',  # Buying back a short position
            new_symbol=new_strike['symbol'],
            new_size=abs(target_leg['size']),
            new_side='sell'
        )

        if result.get('success'):
            # Record hedge in session
            self._record_hedge(session_id, 'micro', direction, {
                'closed_leg': target_leg['symbol'],
                'new_leg': new_strike['symbol'],
                'new_strike': new_strike['strike'],
                'estimated_cost': new_strike.get('premium', 0) - (target_leg.get('entry_price', 0) * 0.1)
            })

        result['cost'] = new_strike.get('premium', 0) * 0.1  # Rough cost estimate
        return result

    def execute_standard_hedge(self, session: Dict, direction: str) -> Dict:
        """
        Execute a standard hedge — roll the tested side ATM leg.

        If bullish (CE side tested):
            - Buy back ATM CE sell
            - Sell new CE at current ATM (higher strike)
        If bearish (PE side tested):
            - Buy back ATM PE sell
            - Sell new PE at current ATM (lower strike)

        Args:
            session: Session data
            direction: 'bullish' or 'bearish'

        Returns:
            {'success': bool, 'orders_placed': int, 'cost': float, 'error': str}
        """
        session_id = session.get('session_id', '')
        underlying = session.get('underlying', 'BTC')
        expiry = session.get('expiry', '')

        positions = session.get('positions', [])
        if not positions:
            return {'success': False, 'error': 'No positions', 'orders_placed': 0, 'cost': 0}

        latest_group = positions[-1]

        if direction == 'bullish':
            target_leg_key = 'atm_ce'  # CE side is losing
        else:
            target_leg_key = 'atm_pe'  # PE side is losing

        target_leg = latest_group.get(target_leg_key)
        if not target_leg or not target_leg.get('symbol'):
            return {'success': False, 'error': f'No {target_leg_key} leg found', 'orders_placed': 0, 'cost': 0}

        if target_leg.get('closed', False):
            return {'success': False, 'error': f'{target_leg_key} already closed', 'orders_placed': 0, 'cost': 0}

        # Get current chain
        try:
            normalized_expiry = normalize_expiry_format(expiry)
            chain_data = self.chain_service.get_chain_data(underlying, normalized_expiry)
        except Exception as e:
            return {'success': False, 'error': f'Chain fetch failed: {e}', 'orders_placed': 0, 'cost': 0}

        spot_price = chain_data.get('spot_price', 0)
        chain = chain_data.get('chain', [])

        atm_result = self.strike_selector.find_atm_strike(chain, spot_price)
        if not atm_result:
            return {'success': False, 'error': 'Could not find ATM', 'orders_placed': 0, 'cost': 0}

        # New ATM option
        if direction == 'bullish':
            new_symbol = atm_result.get('ce_symbol')
            if not new_symbol:
                # Find CE at the new ATM strike
                for s in chain:
                    if s.get('strike') == atm_result['strike'] and s.get('call', {}).get('symbol'):
                        new_symbol = s['call']['symbol']
                        break
        else:
            new_symbol = atm_result.get('pe_symbol')
            if not new_symbol:
                for s in chain:
                    if s.get('strike') == atm_result['strike'] and s.get('put', {}).get('symbol'):
                        new_symbol = s['put']['symbol']
                        break

        if not new_symbol:
            return {'success': False, 'error': 'Could not find new ATM symbol', 'orders_placed': 0, 'cost': 0}

        # Don't roll if it's the same strike
        if new_symbol == target_leg['symbol']:
            return {'success': False, 'error': 'New ATM is same as current — no roll needed',
                    'orders_placed': 0, 'cost': 0}

        result = self._place_roll_orders(
            session_id=session_id,
            close_symbol=target_leg['symbol'],
            close_size=abs(target_leg['size']),
            close_side='buy',
            new_symbol=new_symbol,
            new_size=abs(target_leg['size']),
            new_side='sell'
        )

        if result.get('success'):
            self._record_hedge(session_id, 'standard', direction, {
                'closed_leg': target_leg['symbol'],
                'new_leg': new_symbol,
                'new_strike': atm_result['strike']
            })

        return result

    def execute_emergency_hedge(self, session: Dict, direction: str) -> Dict:
        """
        Execute an emergency hedge — delegates to surgical adjustment (Phase 5).

        Args:
            session: Session data
            direction: 'bullish' or 'bearish'

        Returns:
            {'success': bool, 'orders_placed': int, 'cost': float, 'error': str}
        """
        return self.execute_surgical_adjustment(session, direction)

    def execute_surgical_adjustment(self, session: Dict, direction: str) -> Dict:
        """
        Execute a surgical adjustment — Phase 5 enhanced version of emergency hedge.

        Only adjusts the troubled side:
        - Closes ATM sell + far OTM sell on the tested side
        - Opens new legs at current ATM for that side only
        - Updates position storage with closed/new leg data
        - Leaves the untested side completely alone

        This replaces the full-butterfly adjustment ($600-1000) with a
        half-butterfly surgical roll ($200-400).

        Args:
            session: Session data
            direction: 'bullish' or 'bearish'

        Returns:
            {'success': bool, 'orders_placed': int, 'cost': float, 'legs_closed': list, 'legs_opened': list}
        """
        session_id = session.get('session_id', '')
        underlying = session.get('underlying', 'BTC')
        expiry = session.get('expiry', '')

        positions = session.get('positions', [])
        if not positions:
            return {'success': False, 'error': 'No positions', 'orders_placed': 0, 'cost': 0}

        latest_group = positions[-1]
        trigger_id = latest_group.get('trigger_id', 0)

        # Identify legs to close (the troubled side)
        if direction == 'bullish':
            legs_to_close_keys = ['atm_ce', 'far_otm_ce']
            roll_type = 'ce'
        else:
            legs_to_close_keys = ['atm_pe', 'far_otm_pe']
            roll_type = 'pe'

        # Collect close orders with current prices for P&L
        close_orders = []
        for leg_key in legs_to_close_keys:
            leg = latest_group.get(leg_key)
            if not leg or not leg.get('symbol') or leg.get('closed', False):
                continue
            close_orders.append({
                'symbol': leg['symbol'],
                'size': abs(leg['size']),
                'side': 'buy' if leg['size'] < 0 else 'sell',
                'leg_key': leg_key,
                'entry_price': leg.get('entry_price', 0)
            })

        if not close_orders:
            return {'success': False, 'error': 'No legs to close on troubled side',
                    'orders_placed': 0, 'cost': 0}

        # Get current chain for new strike selection
        try:
            normalized_expiry = normalize_expiry_format(expiry)
            chain_data = self.chain_service.get_chain_data(underlying, normalized_expiry)
        except Exception as e:
            return {'success': False, 'error': f'Chain fetch failed: {e}', 'orders_placed': 0, 'cost': 0}

        spot_price = chain_data.get('spot_price', 0)
        chain = chain_data.get('chain', [])
        strike_config = session.get('strike_config', {})

        atm_result = self.strike_selector.find_atm_strike(chain, spot_price)
        if not atm_result:
            return {'success': False, 'error': 'Could not find new ATM', 'orders_placed': 0, 'cost': 0}

        current_atm = atm_result['strike']

        # Find new legs for the troubled side
        premium_ranges = self.strike_selector.calculate_premium_ranges(
            atm_result['ce_premium'], atm_result['pe_premium'], strike_config
        )

        new_orders = []
        option_key = 'call' if roll_type == 'ce' else 'put'

        # New ATM sell leg
        for s in chain:
            if s.get('strike') == current_atm and s.get(option_key, {}).get('symbol'):
                opt_data = s[option_key]
                new_orders.append({
                    'symbol': opt_data['symbol'],
                    'size': abs(close_orders[0]['size']) if close_orders else 1,
                    'side': 'sell',
                    'leg_key': f'atm_{roll_type}',
                    'entry_price': opt_data.get('mark_price', opt_data.get('bid', 0))
                })
                break

        # New far OTM sell leg
        far_otm_range = premium_ranges.get(f'far_otm_{roll_type}', {'min': 0, 'max': 0})
        if far_otm_range.get('min', 0) > 0:
            new_far = self.strike_selector.find_far_otm_strike(
                chain, current_atm,
                current_atm + 1000 if roll_type == 'ce' else current_atm - 1000,
                far_otm_range, roll_type
            )
            if new_far:
                far_leg_size = 1
                for co in close_orders:
                    if 'far_otm' in co['leg_key']:
                        far_leg_size = co['size']
                        break
                new_orders.append({
                    'symbol': new_far['symbol'],
                    'size': far_leg_size,
                    'side': 'sell',
                    'leg_key': f'far_otm_{roll_type}',
                    'entry_price': new_far.get('premium', 0)
                })

        if not new_orders:
            return {'success': False, 'error': 'Could not find replacement strikes',
                    'orders_placed': 0, 'cost': 0}

        # Execute: close old + open new in single batch
        all_batch_orders = close_orders + new_orders

        try:
            batch_payload = {
                'orders': [
                    {'symbol': o['symbol'], 'size': o['size'], 'side': o['side']}
                    for o in all_batch_orders
                ],
                'order_preference': 'maker_first',
                'confirm': True
            }

            log.info(f"[{session_id}] Surgical adjustment ({direction}): "
                     f"{len(close_orders)} close + {len(new_orders)} open")

            response = requests.post(
                f"{self.api_base_url}/api/options/batch_add",
                json=batch_payload,
                timeout=60
            )

            if response.status_code != 200:
                return {'success': False, 'error': f'API returned {response.status_code}',
                        'orders_placed': 0, 'cost': 0}

            result = response.json()

            if result.get('success'):
                # Update position storage — mark closed legs and add new legs
                try:
                    from .ssr_algo_storage import get_storage
                    storage = get_storage()

                    for co in close_orders:
                        storage.close_position_leg(
                            session_id, trigger_id, co['leg_key'],
                            close_price=co.get('entry_price', 0),
                            realized_pnl=0  # Actual P&L calculated from fill prices
                        )

                    for no in new_orders:
                        storage.update_position_leg(
                            session_id, trigger_id, no['leg_key'],
                            {
                                'symbol': no['symbol'],
                                'size': -no['size'],  # Sells are negative
                                'filled': False,
                                'entry_price': no.get('entry_price', 0),
                                'rolled_at': datetime.utcnow().isoformat()
                            }
                        )
                except Exception as e:
                    log.warning(f"[{session_id}] Could not update position storage after surgical: {e}")

                self._record_hedge(session_id, 'surgical', direction, {
                    'closed_legs': [o['symbol'] for o in close_orders],
                    'new_legs': [o['symbol'] for o in new_orders],
                    'new_atm': current_atm
                })

                return {
                    'success': True,
                    'orders_placed': result.get('successful', 0),
                    'cost': 0,
                    'legs_closed': [o['leg_key'] for o in close_orders],
                    'legs_opened': [o['leg_key'] for o in new_orders]
                }
            else:
                return {'success': False, 'error': result.get('error', 'Unknown'),
                        'orders_placed': 0, 'cost': 0}

        except Exception as e:
            log.exception(f"[{session_id}] Surgical adjustment failed")
            return {'success': False, 'error': str(e), 'orders_placed': 0, 'cost': 0}

    def _place_roll_orders(self, session_id: str,
                            close_symbol: str, close_size: int, close_side: str,
                            new_symbol: str, new_size: int, new_side: str) -> Dict:
        """
        Place a pair of orders to roll a leg: close old + open new.

        Args:
            session_id: Session ID for logging
            close_symbol: Symbol to close
            close_size: Size to close
            close_side: 'buy' or 'sell' (to close)
            new_symbol: New symbol to open
            new_size: Size to open
            new_side: 'buy' or 'sell' (new position)

        Returns:
            {'success': bool, 'orders_placed': int, 'error': str}
        """
        try:
            batch_payload = {
                'orders': [
                    {'symbol': close_symbol, 'size': close_size, 'side': close_side},
                    {'symbol': new_symbol, 'size': new_size, 'side': new_side}
                ],
                'order_preference': 'maker_first',
                'confirm': True
            }

            log.info(f"[{session_id}] Roll: close {close_symbol} ({close_side}), open {new_symbol} ({new_side})")

            response = requests.post(
                f"{self.api_base_url}/api/options/batch_add",
                json=batch_payload,
                timeout=60
            )

            if response.status_code != 200:
                return {'success': False, 'error': f'API returned {response.status_code}', 'orders_placed': 0}

            result = response.json()

            if result.get('success'):
                return {
                    'success': True,
                    'orders_placed': result.get('successful', 0),
                    'batch_result': result
                }
            else:
                return {'success': False, 'error': result.get('error', 'Unknown'), 'orders_placed': 0}

        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Request timed out', 'orders_placed': 0}
        except Exception as e:
            log.exception(f"[{session_id}] Roll order failed")
            return {'success': False, 'error': str(e), 'orders_placed': 0}

    def _record_hedge(self, session_id: str, hedge_type: str,
                       direction: str, details: Dict):
        """Record a hedge event in session storage."""
        try:
            from .ssr_algo_storage import get_storage
            storage = get_storage()

            session = storage.get_session(session_id)
            if not session:
                return

            hedge_history = session.get('hedge_history', [])
            hedge_history.append({
                'type': hedge_type,
                'direction': direction,
                'timestamp': datetime.utcnow().isoformat(),
                'details': details
            })

            # Keep last 50 hedges
            if len(hedge_history) > 50:
                hedge_history = hedge_history[-50:]

            storage.update_session(session_id, {
                'hedge_history': hedge_history,
                'last_hedge_time': datetime.now().isoformat(),
                'daily_hedge_count': session.get('daily_hedge_count', 0) + 1
            })

            from .ssr_algo_monitor import add_session_log
            add_session_log(session_id,
                f"Delta {hedge_type} hedge ({direction}): {details}",
                'info')

        except Exception as e:
            log.warning(f"[{session_id}] Could not record hedge: {e}")


# Singleton instance
_delta_hedger = None

def get_delta_hedger() -> SSRDeltaHedger:
    """Get singleton SSRDeltaHedger instance."""
    global _delta_hedger
    if _delta_hedger is None:
        _delta_hedger = SSRDeltaHedger()
    return _delta_hedger
