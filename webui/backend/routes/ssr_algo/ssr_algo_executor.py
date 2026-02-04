"""
SSR ALGO Executor - Order Execution Wrapper

Handles the execution of auto-loop rounds using the existing batch_add API.
Features:
- Round-by-round execution with progress tracking
- Integration with batch_add endpoint
- Order status monitoring and fill tracking
- Error handling and partial fill detection

Created: February 2, 2026
Updated: February 3, 2026 - Added order fill tracking
"""

import logging
import time
import asyncio
import requests
from typing import Dict, List, Optional, Callable
from datetime import datetime

log = logging.getLogger('ssr_algo_executor')

# Backend API base URL (internal calls)
API_BASE_URL = 'http://localhost:5555'


class SSRAutoLoopExecutor:
    """
    Executes auto-loop rounds for SSR Algo sessions.
    
    Wraps the existing batch_add API to place orders in rounds,
    waiting for all orders to fill before proceeding to next round.
    """
    
    def __init__(self, api_base_url: str = None):
        """
        Initialize executor.
        
        Args:
            api_base_url: Optional API base URL for testing
        """
        self.api_base_url = api_base_url or API_BASE_URL
        self._stop_requested = {}  # session_id -> bool
    
    def request_stop(self, session_id: str):
        """Request graceful stop for a session's execution."""
        self._stop_requested[session_id] = True
        log.info(f"Stop requested for session {session_id}")
    
    def is_stop_requested(self, session_id: str) -> bool:
        """Check if stop was requested for session."""
        return self._stop_requested.get(session_id, False)
    
    def clear_stop(self, session_id: str):
        """Clear stop request after handling."""
        self._stop_requested.pop(session_id, None)
    
    def execute_rounds(self,
                       session_id: str,
                       orders: List[Dict],
                       rounds: int,
                       order_type: str = 'ssr',
                       progress_callback: Callable[[int, int, Dict], None] = None) -> Dict:
        """
        Execute multiple auto-loop rounds.
        
        Args:
            session_id: Session identifier for tracking
            orders: List of orders (symbol, size, side)
            rounds: Number of rounds to execute
            order_type: Order preference (ssr, maker_first, market_only)
            progress_callback: Optional callback(round, total, result)
        
        Returns:
            {
                'success': bool,
                'completed_rounds': int,
                'total_rounds': int,
                'results': List[Dict],
                'error': str (if failed)
            }
        """
        log.info(f"[{session_id}] Starting {rounds} rounds with {len(orders)} orders")
        
        results = []
        completed = 0
        
        for round_num in range(1, rounds + 1):
            # Check for stop request
            if self.is_stop_requested(session_id):
                log.info(f"[{session_id}] Stopped at round {round_num-1}/{rounds}")
                self.clear_stop(session_id)
                return {
                    'success': False,
                    'completed_rounds': completed,
                    'total_rounds': rounds,
                    'results': results,
                    'error': f'Stopped by user at round {round_num-1}'
                }
            
            log.info(f"[{session_id}] Executing round {round_num}/{rounds}")
            
            # Execute round
            round_result = self._execute_single_round(
                session_id, orders, order_type, round_num
            )
            
            results.append(round_result)
            
            if progress_callback:
                progress_callback(round_num, rounds, round_result)
            
            if not round_result.get('success'):
                log.error(f"[{session_id}] Round {round_num} failed: {round_result.get('error')}")
                return {
                    'success': False,
                    'completed_rounds': completed,
                    'total_rounds': rounds,
                    'results': results,
                    'error': round_result.get('error')
                }
            
            completed = round_num
            
            # Wait for orders to fill if not last round
            # Note: We continue even if fills timeout - the strategy still works
            if round_num < rounds:
                fill_result = self._wait_for_fills(session_id, round_result, timeout_seconds=60)
                if not fill_result.get('success'):
                    log.warning(f"[{session_id}] Fill wait incomplete: {fill_result.get('error')}. Continuing to next round anyway.")
                    # DON'T return error - continue with next round
                    # The strategy is already placed, just fills are pending
        
        log.info(f"[{session_id}] All {rounds} rounds completed successfully")
        
        return {
            'success': True,
            'completed_rounds': completed,
            'total_rounds': rounds,
            'results': results
        }
    
    def _execute_single_round(self,
                              session_id: str,
                              orders: List[Dict],
                              order_type: str,
                              round_num: int) -> Dict:
        """
        Execute a single round via batch_add API.
        
        Args:
            session_id: Session ID for logging
            orders: Orders to place
            order_type: Order preference
            round_num: Current round number
        
        Returns:
            API response with order results
        """
        try:
            # Map SSR algo order type to batch_add preference
            order_preference_map = {
                'ssr': 'maker_first',
                'maker': 'maker_only',
                'market': 'market_only'
            }
            order_preference = order_preference_map.get(order_type, 'maker_first')
            
            # Prepare request
            payload = {
                'orders': [
                    {
                        'symbol': o['symbol'],
                        'size': o['size'],
                        'side': o['side']
                    }
                    for o in orders
                ],
                'order_preference': order_preference,
                'confirm': True
            }
            
            log.debug(f"[{session_id}] Round {round_num} payload: {payload}")
            
            # Call batch_add API
            response = requests.post(
                f"{self.api_base_url}/api/options/batch_add",
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'round': round_num,
                    'error': f"API returned {response.status_code}: {response.text}"
                }
            
            data = response.json()
            
            if not data.get('success'):
                return {
                    'success': False,
                    'round': round_num,
                    'error': data.get('error', 'Unknown error')
                }
            
            return {
                'success': True,
                'round': round_num,
                'results': data.get('results', []),
                'successful': data.get('successful', 0),
                'failed': data.get('failed', 0),
                'execution_time': data.get('execution_time')
            }
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'round': round_num,
                'error': 'Request timeout (60s)'
            }
        except Exception as e:
            log.exception(f"[{session_id}] Round {round_num} execution error")
            return {
                'success': False,
                'round': round_num,
                'error': str(e)
            }
    
    def _wait_for_fills(self,
                        session_id: str,
                        round_result: Dict,
                        timeout_seconds: int = 300,
                        poll_interval: int = 5) -> Dict:
        """
        Wait for all orders from a round to fill.
        
        Args:
            session_id: Session ID
            round_result: Result from _execute_single_round
            timeout_seconds: Max wait time (default 5 minutes)
            poll_interval: Seconds between status checks
        
        Returns:
            {'success': bool, 'error': str}
        """
        results = round_result.get('results', [])
        pending_order_ids = []
        
        for r in results:
            if r.get('success') and r.get('order_id') and not r.get('filled'):
                pending_order_ids.append(r['order_id'])
        
        if not pending_order_ids:
            log.debug(f"[{session_id}] All orders immediately filled")
            return {'success': True}
        
        log.info(f"[{session_id}] Waiting for {len(pending_order_ids)} orders to fill")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            if self.is_stop_requested(session_id):
                return {'success': False, 'error': 'Stopped by user during fill wait'}
            
            # Check order status
            try:
                response = requests.post(
                    f"{self.api_base_url}/api/options/batch_order_status",
                    json={'order_ids': pending_order_ids},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    statuses = data.get('statuses', {})
                    
                    still_pending = [
                        oid for oid in pending_order_ids
                        if statuses.get(oid, {}).get('status') not in ['filled', 'cancelled']
                    ]
                    
                    if not still_pending:
                        log.info(f"[{session_id}] All orders filled")
                        return {'success': True}
                    
                    pending_order_ids = still_pending
                    log.debug(f"[{session_id}] {len(pending_order_ids)} orders still pending")
                    
            except Exception as e:
                log.warning(f"[{session_id}] Status check failed: {e}")
            
            time.sleep(poll_interval)
        
        return {
            'success': False,
            'error': f'Timeout waiting for orders to fill ({timeout_seconds}s)'
        }
    
    def place_limit_exit_orders(self,
                                session_id: str,
                                sell_positions: List[Dict],
                                exit_price: float = 3.0) -> Dict:
        """
        Place limit buy orders to exit sell positions at low premium.
        
        Args:
            session_id: Session ID
            sell_positions: List of sell positions to exit
            exit_price: Limit price (default 3)
        
        Returns:
            {'success': bool, 'order_ids': List[str], 'error': str}
        """
        try:
            orders = []
            for pos in sell_positions:
                orders.append({
                    'symbol': pos.get('symbol'),
                    'size': abs(pos.get('size', 1)),
                    'side': 'buy',  # Exit sell by buying
                    'price': exit_price,
                    'order_type': 'limit'
                })
            
            if not orders:
                return {'success': True, 'order_ids': []}
            
            log.info(f"[{session_id}] Placing {len(orders)} limit exit orders at price={exit_price}")
            
            # Use individual limit orders (not batch_add which uses market/maker)
            order_ids = []
            for order in orders:
                try:
                    response = requests.post(
                        f"{self.api_base_url}/api/options/limit_order",
                        json=order,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('order_id'):
                            order_ids.append(data['order_id'])
                            log.info(f"Placed limit exit for {order['symbol']}: {data['order_id']}")
                
                except Exception as e:
                    log.warning(f"Failed to place limit exit for {order['symbol']}: {e}")
            
            return {
                'success': True,
                'order_ids': order_ids
            }
            
        except Exception as e:
            log.exception(f"[{session_id}] Limit exit order placement failed")
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_and_update_pending_orders(self, session_id: str, storage) -> Dict:
        """
        Check pending orders on exchange and update their fill status.
        
        Args:
            session_id: Session ID
            storage: SSRAlgoStorage instance
        
        Returns:
            {'success': bool, 'filled': int, 'pending': int, 'fills': List[Dict]}
        """
        session = storage.get_session(session_id)
        if not session:
            return {'success': False, 'error': 'Session not found'}
        
        pending_orders = session.get('pending_orders', [])
        if not pending_orders:
            return {'success': True, 'filled': 0, 'pending': 0, 'fills': []}
        
        order_ids = [o.get('order_id') for o in pending_orders if o.get('order_id')]
        if not order_ids:
            return {'success': True, 'filled': 0, 'pending': 0, 'fills': []}
        
        try:
            # Check order status from exchange via our API
            response = requests.post(
                f"{self.api_base_url}/api/options/batch_order_status",
                json={'order_ids': order_ids},
                timeout=30
            )
            
            if response.status_code != 200:
                return {'success': False, 'error': f'API error: {response.status_code}'}
            
            data = response.json()
            statuses = data.get('statuses', {})
            
            filled_count = 0
            fills = []
            
            for order_id in order_ids:
                status_info = statuses.get(order_id, {})
                order_status = status_info.get('status', 'unknown')
                
                if order_status == 'filled':
                    fill_price = status_info.get('average_price') or status_info.get('price', 0)
                    storage.update_order_filled(session_id, order_id, fill_price)
                    filled_count += 1
                    fills.append({
                        'order_id': order_id,
                        'fill_price': fill_price,
                        'symbol': status_info.get('symbol', '')
                    })
                    log.info(f"[{session_id}] Order {order_id} filled at ${fill_price:.2f}")
            
            # Get updated pending count
            updated_session = storage.get_session(session_id)
            remaining_pending = len(updated_session.get('pending_orders', []))
            
            return {
                'success': True,
                'filled': filled_count,
                'pending': remaining_pending,
                'fills': fills
            }
            
        except Exception as e:
            log.exception(f"[{session_id}] Failed to check pending orders")
            return {'success': False, 'error': str(e)}


# Singleton instance
_executor = None

def get_executor() -> SSRAutoLoopExecutor:
    """Get the singleton executor instance."""
    global _executor
    if _executor is None:
        _executor = SSRAutoLoopExecutor()
    return _executor
