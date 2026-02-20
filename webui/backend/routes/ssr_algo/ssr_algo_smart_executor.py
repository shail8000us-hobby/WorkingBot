"""
SSR ALGO Smart Executor - Execution Quality & Slippage Optimization

Wraps the existing batch_add API with intelligent order routing:
- Low urgency: Work limit orders to capture spread
- Medium urgency: Moderate limit with quick fallback to market
- High/Critical urgency: Market orders immediately

Created: February 20, 2026
Phase 8 of SSR Algo Development Plan
"""

import logging
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional

log = logging.getLogger('ssr_algo_smart_executor')

API_BASE_URL = 'http://localhost:5555'

# Urgency levels for order routing
URGENCY_LEVELS = {
    'low': {
        'name': 'Low',
        'description': 'Regular entry — maximize fill quality',
        'market_spread_threshold': 1.0,   # Use market if spread < 1%
        'limit_wait_seconds': 30,
        'limit_fallback_seconds': 60,
        'max_attempts': 3,
    },
    'medium': {
        'name': 'Medium',
        'description': 'Delta hedge — balance speed vs quality',
        'market_spread_threshold': 2.0,
        'limit_wait_seconds': 15,
        'limit_fallback_seconds': 30,
        'max_attempts': 2,
    },
    'high': {
        'name': 'High',
        'description': 'Exit — prioritize speed',
        'market_spread_threshold': 100.0,  # Always market
        'limit_wait_seconds': 0,
        'limit_fallback_seconds': 0,
        'max_attempts': 2,
    },
    'critical': {
        'name': 'Critical',
        'description': 'Stop loss — market immediately, retry',
        'market_spread_threshold': 100.0,
        'limit_wait_seconds': 0,
        'limit_fallback_seconds': 0,
        'max_attempts': 3,
    },
}


class SSRSmartExecutor:
    """
    Smart order router that optimizes execution quality based on urgency.

    Wraps the batch_add API with spread-aware routing logic.
    """

    def __init__(self, api_base_url: str = None):
        self.api_base_url = api_base_url or API_BASE_URL
        self._chain_service = None

    @property
    def chain_service(self):
        if self._chain_service is None:
            from webui.backend.options_chain.chain_service import OptionsChainService
            self._chain_service = OptionsChainService()
        return self._chain_service

    def get_spread_info(self, symbol: str) -> Dict:
        """
        Get bid/ask spread info for a symbol from chain data.

        Returns:
            {'bid': float, 'ask': float, 'mid': float, 'spread_pct': float}
        """
        try:
            from .ssr_algo_payoff import parse_symbol
            parsed = parse_symbol(symbol)
            if not parsed:
                return {'bid': 0, 'ask': 0, 'mid': 0, 'spread_pct': 100}

            underlying = parsed.get('underlying', 'BTC')
            expiry = parsed.get('expiry', '')
            strike = parsed.get('strike', 0)
            opt_type = parsed.get('type', 'C')

            from .ssr_algo_engine import normalize_expiry_format
            normalized = normalize_expiry_format(expiry)
            chain_data = self.chain_service.get_chain_data(underlying, normalized)
            chain = chain_data.get('chain', [])

            option_key = 'call' if opt_type == 'C' else 'put'

            for s in chain:
                if s.get('strike') == strike:
                    opt = s.get(option_key, {})
                    bid = opt.get('bid', 0) or 0
                    ask = opt.get('ask', 0) or 0
                    mid = (bid + ask) / 2 if (bid and ask) else opt.get('mark_price', 0)

                    if mid > 0:
                        spread_pct = ((ask - bid) / mid * 100) if (bid and ask and mid > 0) else 100
                    else:
                        spread_pct = 100

                    return {
                        'bid': bid,
                        'ask': ask,
                        'mid': mid,
                        'spread_pct': round(spread_pct, 2),
                        'mark_price': opt.get('mark_price', 0)
                    }

        except Exception as e:
            log.debug(f"Could not get spread info for {symbol}: {e}")

        return {'bid': 0, 'ask': 0, 'mid': 0, 'spread_pct': 100}

    def calculate_smart_price(self, spread_info: Dict, side: str,
                               urgency: str = 'low') -> Optional[float]:
        """
        Calculate optimal limit price based on spread and urgency.

        Args:
            spread_info: From get_spread_info()
            side: 'buy' or 'sell'
            urgency: Urgency level

        Returns:
            Limit price or None (for market order)
        """
        config = URGENCY_LEVELS.get(urgency, URGENCY_LEVELS['low'])

        bid = spread_info.get('bid', 0)
        ask = spread_info.get('ask', 0)
        mid = spread_info.get('mid', 0)
        spread_pct = spread_info.get('spread_pct', 100)

        # If spread is tight enough, use market
        if spread_pct <= config['market_spread_threshold']:
            return None  # Market order

        # If no valid quotes, use market
        if not bid or not ask or not mid:
            return None

        if side == 'buy':
            # For buys: start near bid, move toward ask
            if urgency in ('high', 'critical'):
                return None  # Market
            elif urgency == 'medium':
                return round(bid + (ask - bid) * 0.40, 2)  # 40th percentile
            else:
                return round(bid + (ask - bid) * 0.25, 2)  # 25th percentile
        else:
            # For sells: start near ask, move toward bid
            if urgency in ('high', 'critical'):
                return None  # Market
            elif urgency == 'medium':
                return round(ask - (ask - bid) * 0.40, 2)
            else:
                return round(ask - (ask - bid) * 0.25, 2)

    def execute_with_smart_routing(self, orders: List[Dict],
                                     urgency: str = 'low',
                                     session_id: str = '') -> Dict:
        """
        Execute orders with spread-aware smart routing.

        Args:
            orders: List of {'symbol': str, 'size': int, 'side': str}
            urgency: 'low' | 'medium' | 'high' | 'critical'
            session_id: For logging

        Returns:
            {'success': bool, 'results': list, 'execution_stats': dict}
        """
        config = URGENCY_LEVELS.get(urgency, URGENCY_LEVELS['low'])
        results = []
        stats = {
            'total_orders': len(orders),
            'market_orders': 0,
            'limit_orders': 0,
            'filled': 0,
            'total_slippage_pct': 0.0,
        }

        # For high/critical urgency, just fire market orders immediately
        if urgency in ('high', 'critical'):
            return self._execute_market_batch(orders, session_id, stats)

        # For low/medium urgency, check spreads and route intelligently
        market_orders = []
        limit_orders = []

        for order in orders:
            spread_info = self.get_spread_info(order['symbol'])
            smart_price = self.calculate_smart_price(
                spread_info, order['side'], urgency
            )

            if smart_price is None:
                market_orders.append(order)
                stats['market_orders'] += 1
            else:
                limit_orders.append({
                    **order,
                    'limit_price': smart_price,
                    'spread_info': spread_info
                })
                stats['limit_orders'] += 1

        # Execute market orders immediately
        if market_orders:
            market_result = self._execute_market_batch(
                market_orders, session_id, stats
            )
            results.extend(market_result.get('results', []))

        # Execute limit orders with wait+fallback
        if limit_orders:
            limit_result = self._execute_limit_with_fallback(
                limit_orders, session_id, config, stats
            )
            results.extend(limit_result.get('results', []))

        stats['avg_slippage_pct'] = (
            stats['total_slippage_pct'] / stats['filled']
            if stats['filled'] > 0 else 0
        )

        return {
            'success': stats['filled'] > 0,
            'results': results,
            'execution_stats': stats,
            'filled': stats['filled'],
            'total': stats['total_orders']
        }

    def _execute_market_batch(self, orders: List[Dict],
                               session_id: str, stats: Dict) -> Dict:
        """Execute a batch of market orders."""
        try:
            batch_payload = {
                'orders': [
                    {'symbol': o['symbol'], 'size': o['size'], 'side': o['side']}
                    for o in orders
                ],
                'order_preference': 'market',
                'confirm': True
            }

            response = requests.post(
                f"{self.api_base_url}/api/options/batch_add",
                json=batch_payload,
                timeout=60
            )

            if response.status_code != 200:
                return {'success': False, 'results': [],
                        'error': f'API returned {response.status_code}'}

            result = response.json()
            if result.get('success'):
                stats['filled'] += result.get('successful', 0)

            return {
                'success': result.get('success', False),
                'results': result.get('results', [])
            }

        except Exception as e:
            log.exception(f"[{session_id}] Market batch failed")
            return {'success': False, 'results': [], 'error': str(e)}

    def _execute_limit_with_fallback(self, limit_orders: List[Dict],
                                       session_id: str, config: Dict,
                                       stats: Dict) -> Dict:
        """
        Execute limit orders, wait for fill, then fall back to market.
        """
        results = []
        wait_seconds = config.get('limit_wait_seconds', 30)

        # Place limit orders
        batch_payload = {
            'orders': [
                {
                    'symbol': o['symbol'],
                    'size': o['size'],
                    'side': o['side'],
                    'limit_price': o.get('limit_price')
                }
                for o in limit_orders
            ],
            'order_preference': 'maker_first',
            'confirm': True
        }

        try:
            response = requests.post(
                f"{self.api_base_url}/api/options/batch_add",
                json=batch_payload,
                timeout=60
            )

            if response.status_code != 200:
                # Fall back to market
                log.warning(f"[{session_id}] Limit batch failed, falling back to market")
                return self._execute_market_batch(
                    [{'symbol': o['symbol'], 'size': o['size'], 'side': o['side']}
                     for o in limit_orders],
                    session_id, stats
                )

            result = response.json()
            if result.get('success'):
                filled_count = result.get('successful', 0)
                stats['filled'] += filled_count

                # Calculate slippage for filled orders
                for r in result.get('results', []):
                    if r.get('fill_price') and r.get('symbol'):
                        # Find the corresponding limit order
                        for lo in limit_orders:
                            if lo['symbol'] == r['symbol']:
                                mid = lo.get('spread_info', {}).get('mid', 0)
                                if mid > 0:
                                    slippage = abs(r['fill_price'] - mid) / mid * 100
                                    stats['total_slippage_pct'] += slippage
                                break

                results = result.get('results', [])

                # If not all filled, wait and then market the remainder
                if filled_count < len(limit_orders) and wait_seconds > 0:
                    log.info(f"[{session_id}] {filled_count}/{len(limit_orders)} filled, "
                             f"waiting {wait_seconds}s for remaining")
                    time.sleep(wait_seconds)

                    # Check which are still unfilled and market them
                    unfilled = [
                        {'symbol': o['symbol'], 'size': o['size'], 'side': o['side']}
                        for o in limit_orders
                        if o['symbol'] not in [r.get('symbol') for r in results if r.get('fill_price')]
                    ]

                    if unfilled:
                        fallback = self._execute_market_batch(unfilled, session_id, stats)
                        results.extend(fallback.get('results', []))

            return {'success': True, 'results': results}

        except Exception as e:
            log.exception(f"[{session_id}] Limit batch failed")
            return self._execute_market_batch(
                [{'symbol': o['symbol'], 'size': o['size'], 'side': o['side']}
                 for o in limit_orders],
                session_id, stats
            )

    def log_execution_quality(self, session_id: str, order_result: Dict,
                                intended_mid: float) -> Dict:
        """
        Calculate and log execution quality metrics.

        Args:
            session_id: Session ID
            order_result: Result from batch_add
            intended_mid: Mid price at time of order

        Returns:
            {'slippage_pct': float, 'quality': str}
        """
        fill_price = order_result.get('fill_price', 0)
        symbol = order_result.get('symbol', 'unknown')

        if not fill_price or not intended_mid:
            return {'slippage_pct': 0, 'quality': 'unknown'}

        slippage_pct = (fill_price - intended_mid) / intended_mid * 100

        if abs(slippage_pct) < 0.5:
            quality = 'excellent'
        elif abs(slippage_pct) < 1.0:
            quality = 'good'
        elif abs(slippage_pct) < 2.0:
            quality = 'fair'
        else:
            quality = 'poor'

        log.info(f"[{session_id}] Execution: {symbol} filled @ ${fill_price:.2f}, "
                 f"mid was ${intended_mid:.2f}, slippage: {slippage_pct:+.2f}% ({quality})")

        # Store in session
        try:
            from .ssr_algo_storage import get_storage
            storage = get_storage()
            session = storage.get_session(session_id)
            if session:
                exec_stats = session.get('execution_stats', {
                    'total_orders': 0,
                    'total_slippage_pct': 0.0,
                    'avg_slippage_pct': 0.0,
                    'maker_fills': 0,
                    'taker_fills': 0,
                })
                exec_stats['total_orders'] = exec_stats.get('total_orders', 0) + 1
                exec_stats['total_slippage_pct'] = exec_stats.get('total_slippage_pct', 0) + abs(slippage_pct)
                if exec_stats['total_orders'] > 0:
                    exec_stats['avg_slippage_pct'] = round(
                        exec_stats['total_slippage_pct'] / exec_stats['total_orders'], 3
                    )
                storage.update_session(session_id, {'execution_stats': exec_stats})
        except Exception as e:
            log.debug(f"Could not store execution quality: {e}")

        return {
            'slippage_pct': round(slippage_pct, 3),
            'quality': quality
        }


# Singleton
_smart_executor = None

def get_smart_executor() -> SSRSmartExecutor:
    """Get singleton SSRSmartExecutor instance."""
    global _smart_executor
    if _smart_executor is None:
        _smart_executor = SSRSmartExecutor()
    return _smart_executor
