"""
Dashboard Service Layer

ARCH-3 FIX: Extracts data-fetching logic from Flask route handlers into plain
service functions that return dicts (not Flask response objects).

Both the unified dashboard and individual routes can use these functions,
eliminating fragile `.get_json()` parsing and tight coupling to Flask responses.

Created: February 26, 2026
"""

import time
import logging
from webui.backend.sealed import sealed

log = logging.getLogger(__name__)


def fetch_options_positions_data() -> dict:
    """
    Fetch options positions as a plain dict.
    
    Returns:
        dict: { 'success': bool, 'positions': list, 'count': int, ... }
    """
    try:
        from .options_control import get_options_positions
        response = get_options_positions()
        response = response[0] if isinstance(response, tuple) else response
        data = response.get_json() if hasattr(response, 'get_json') else response
        return data if isinstance(data, dict) else {'success': False, 'positions': [], 'error': 'Invalid response type'}
    except Exception as e:
        log.error(f"Service: fetch positions failed: {e}")
        return {'success': False, 'positions': [], 'error': str(e)}


@sealed
def fetch_pending_orders_data() -> dict:
    """
    Fetch pending orders as a plain dict.

    SEALED — v1.0.0 — March 4, 2026
    Do not modify without UNSEAL command in AI_SEAL.md

    Returns:
        dict: { 'success': bool, 'orders': list, ... }
    """
    try:
        from ..positions import get_pending_orders
        response = get_pending_orders()
        response = response[0] if isinstance(response, tuple) else response
        data = response.get_json() if hasattr(response, 'get_json') else response
        return data if isinstance(data, dict) else {'success': False, 'orders': [], 'error': 'Invalid response type'}
    except Exception as e:
        log.error(f"Service: fetch pending orders failed: {e}")
        return {'success': False, 'orders': [], 'error': str(e)}


def fetch_futures_positions_data() -> dict:
    """
    Fetch futures positions as a plain dict.
    
    Returns:
        dict: { 'success': bool, 'positions': list, ... }
    """
    try:
        from ..futures.futures_api import get_futures_positions
        response = get_futures_positions()
        response = response[0] if isinstance(response, tuple) else response
        data = response.get_json() if hasattr(response, 'get_json') else response
        return data if isinstance(data, dict) else {'success': False, 'positions': [], 'error': 'Invalid response type'}
    except Exception as e:
        log.error(f"Service: fetch futures positions failed: {e}")
        return {'success': False, 'positions': [], 'error': str(e)}


def fetch_options_status_data() -> dict:
    """
    Fetch options status as a plain dict.
    
    Returns:
        dict: { 'success': bool, 'trading_allowed': bool, ... }
    """
    try:
        from .options_control import get_options_status
        response = get_options_status()
        response = response[0] if isinstance(response, tuple) else response
        data = response.get_json() if hasattr(response, 'get_json') else response
        return data if isinstance(data, dict) else {'success': False, 'error': 'Invalid response type'}
    except Exception as e:
        log.error(f"Service: fetch options status failed: {e}")
        return {'success': False, 'error': str(e)}


def fetch_margin_data() -> dict:
    """
    Fetch margin utilization data from Delta Exchange wallet API.
    
    Returns:
        dict: { 'blocked_margin_usd': float, 'available_balance_usd': float, 'wallet_balance_usd': float }
    """
    margin_data = {'blocked_margin_usd': 0, 'available_balance_usd': 0, 'wallet_balance_usd': 0}
    try:
        from bot.api.delta_client import DeltaClient
        delta_client = DeltaClient()
        wallet_response = delta_client._req('GET', '/v2/wallet/balances')
        if wallet_response and wallet_response.get('success'):
            wallets = wallet_response.get('result', [])
            wallet_data = None
            for wallet in wallets:
                if wallet.get('asset_symbol') == 'USD':
                    wallet_data = wallet
                    break
            if not wallet_data and wallets:
                wallet_data = wallets[0]
            if wallet_data:
                blocked = float(wallet_data.get('blocked_margin', 0) or 0)
                if blocked == 0:
                    blocked = float(wallet_data.get('portfolio_margin', 0) or 0)
                if blocked == 0:
                    blocked = float(wallet_data.get('order_margin', 0) or 0) + float(wallet_data.get('position_margin', 0) or 0)
                available = float(wallet_data.get('available_balance', 0) or 0)
                balance = float(wallet_data.get('balance', 0) or 0)
                margin_data = {
                    'blocked_margin_usd': round(blocked, 2),
                    'available_balance_usd': round(available, 2),
                    'wallet_balance_usd': round(balance, 2),
                }
    except Exception as e:
        log.warning(f"Failed to fetch margin data: {e}")
    return margin_data
