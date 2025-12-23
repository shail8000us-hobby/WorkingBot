"""
Positions Routes Blueprint

This module handles all API routes related to position retrieval and management.

Routes:
- GET  /api/positions - Get current positions with liquidation info and Greeks
- POST /api/positions/resync - Manually resync positions from reconciliation
- GET  /api/state - Get current bot runtime state

Dependencies:
- bot.api.delta_client (DeltaClient)
- bot.state.store (position/state loading)
- bot.reconciliation (resync)
- utils.response_helpers (numpy conversion)

Refactored from app.py (8,850 lines)
Date: 2025-10-31
Enhanced with circuit breaker: 2025-11-12
"""

import os
import sys
import copy
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config

def get_config_value(yaml_path: str, env_var: str = None, default: any = None):
    """Get config value from YAML using dot notation"""
    try:
        cfg = get_config()
        value = cfg
        for key in yaml_path.split('.'):
            value = getattr(value, key)
        return value
    except (AttributeError, KeyError):
        return default

try:
    from webui.backend.utils.response_helpers import convert_numpy_types
    NUMPY_CONVERSION_AVAILABLE = True
except ImportError:
    NUMPY_CONVERSION_AVAILABLE = False
    def convert_numpy_types(obj):
        return obj

# Import circuit breakers
from webui.backend.utils.circuit_breaker import delta_api_breaker, bot_file_breaker

log = logging.getLogger(__name__)

# Create blueprint
positions_bp = Blueprint('positions', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
POSITIONS_FILE = BASE_DIR / "bot" / "reports" / "positions.json"
STATE_FILE = BASE_DIR / "bot" / "reports" / "state.json"

# ============================================================================
# Route Handlers
# ============================================================================

@positions_bp.route('/api/positions', methods=['GET'])
def get_positions():
    """
    Get current positions with liquidation info and Greeks
    
    Tries multiple strategies:
    1. Delta Exchange API (real-time with Greeks)
    2. Positions file (if bot is running)
    3. Guardian data (fallback)
    
    Returns:
        JSON response with positions and summary
    
    Example:
        GET /api/positions
        Response: {
            "positions": [
                {
                    "symbol": "BTCUSD",
                    "product_id": 27,
                    "type": "FUTURE",
                    "size": 10,
                    "side": "long",
                    "entry_price": 50000.0,
                    "current_price": 51000.0,
                    "unrealized_pnl": 10.0,
                    "delta": 0.5,
                    "vega": 0.01,
                    "theta": -0.05,
                    "notional_deployed": 425000.0
                },
                ...
            ],
            "summary": {
                "total_positions": 5,
                "total_pnl": 1234.56,
                "portfolio_delta": 2.5,
                "portfolio_vega": 0.05,
                "portfolio_theta": -0.25,
                "total_notional_deployed": 2125000.0,
                "data_source": "delta_exchange"
            }
        }
    """
    try:
        # Strategy 1: Try Delta Exchange API
        positions_data = _get_positions_from_delta()
        if positions_data:
            return jsonify(positions_data), 200
        
        # Strategy 2: Try positions file
        positions_data = _get_positions_from_file()
        if positions_data:
            return jsonify(positions_data), 200
        
        # Strategy 3: Try guardian
        positions_data = _get_positions_from_guardian()
        if positions_data:
            return jsonify(positions_data), 200
        
        # No positions found
        return jsonify({
            'positions': [],
            'summary': {
                'total_positions': 0,
                'total_pnl_usd': 0,
                'total_pnl_inr': 0,
                'risk_percent': 0,
                'total_notional_deployed': 0
            }
        }), 200
        
    except Exception as e:
        log.error(f"Error fetching positions: {e}")
        return jsonify({'error': str(e)}), 500


@positions_bp.route('/api/positions/resync', methods=['POST'])
def api_resync_positions():
    """
    Manually resync positions from reconciliation engine
    
    Forces a refresh of position data from the exchange.
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/positions/resync
        Response: {"success": true, "message": "Positions resynced successfully"}
    """
    try:
        ok, msg = _resync_positions_from_reconciliation()
        status = 200 if ok else 500
        return jsonify({
            'success': ok,
            'message': msg
        }), status
        
    except Exception as e:
        log.error(f"Error resyncing positions: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@positions_bp.route('/api/state', methods=['GET'])
def get_state():
    """
    Get current bot runtime state
    
    Returns the bot's current runtime state including open positions,
    pending orders, and internal state.
    
    Returns:
        JSON response with bot state
    
    Example:
        GET /api/state
        Response: {
            "open_positions": [...],
            "pending_buy": {...},
            "last_update": "2025-10-31T14:30:00"
        }
    """
    try:
        data = _load_state_data()
        return jsonify(data or {}), 200
        
    except Exception as e:
        log.error(f"Error getting state: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Helper Functions - Position Data Sources
# ============================================================================

def _get_positions_from_delta():
    """
    Get positions directly from Delta Exchange API (with circuit breaker protection)
    
    Returns position data with Greeks (delta, vega, theta) and PnL.
    Greeks are fetched from ticker endpoint as they're not available in positions endpoint.
    """
    try:
        from bot.api.delta_client import DeltaClient
        
        def _fetch_from_delta():
            """Inner function wrapped by circuit breaker"""
            delta_client = DeltaClient()
            response = delta_client._req('GET', '/v2/positions/margined')
            
            if not response.get('success'):
                raise Exception("Delta API returned unsuccessful response")
            
            return response
        
        # Call through circuit breaker (fail fast if Delta API is down)
        response = delta_api_breaker.call(_fetch_from_delta, fallback=None)
        
        if not response:
            return None
        
        positions_data = []
        total_pnl = 0
        total_delta = 0
        total_vega = 0
        total_theta = 0
        total_notional_deployed = 0
        usd_to_inr_rate = float(get_config_value('market.usd_to_inr_rate', 'USD_TO_INR_RATE', 85))
        
        pos_list = response.get('result', [])
        
        # Initialize Delta client for ticker requests
        delta_client = DeltaClient()
        
        for pos_data in pos_list:
            size = int(pos_data.get('size', 0))
            if size == 0:
                continue
            
            entry_price = float(pos_data.get('entry_price', 0))
            mark_price = float(pos_data.get('mark_price', 0))
            product_symbol = pos_data.get('product_symbol', 'UNKNOWN')
            product_id = int(pos_data.get('product_id', 0))
            
            # Calculate PnL: (Mark - Entry) × Size × 0.001
            CONTRACT_MULTIPLIER = 0.001
            unrealized_pnl = (mark_price - entry_price) * size * CONTRACT_MULTIPLIER
            
            # Determine type
            position_type = "OPTION" if any(x in product_symbol for x in ['C-', 'P-']) else "FUTURE"
            
            # Initialize Greeks
            delta = 0
            vega = 0
            theta = 0
            gamma = 0
            
            if position_type == "FUTURE":
                # Futures always have delta = +1 (long) or -1 (short)
                # Position delta = size (positive for long, negative for short)
                delta = float(size)
                # Futures have no vega, theta, gamma
                vega = 0
                theta = 0
                gamma = 0
            else:
                # Fetch Greeks from ticker endpoint for options
                try:
                    ticker_response = delta_client._req('GET', f'/v2/tickers/{product_symbol}')
                    if ticker_response.get('success'):
                        ticker_data = ticker_response.get('result', {})
                        greeks = ticker_data.get('greeks', {})
                        if greeks:
                            # Get per-contract Greeks
                            delta_per_contract = float(greeks.get('delta', 0))
                            vega_per_contract = float(greeks.get('vega', 0))
                            theta_per_contract = float(greeks.get('theta', 0))
                            gamma_per_contract = float(greeks.get('gamma', 0))
                            
                            # Calculate position Greeks (Greeks × Size)
                            delta = delta_per_contract * size
                            vega = vega_per_contract * abs(size)
                            theta = theta_per_contract * abs(size)
                            gamma = gamma_per_contract * abs(size)
                            
                            log.debug(f"Greeks for {product_symbol}: delta={delta:.4f}, vega={vega:.4f}, theta={theta:.4f}")
                except Exception as e:
                    log.debug(f"Could not fetch Greeks for {product_symbol}: {e}")
            
            # Notional
            notional_usd = abs(size * mark_price * CONTRACT_MULTIPLIER)
            notional_deployed = notional_usd * usd_to_inr_rate
            
            positions_data.append({
                'symbol': product_symbol,
                'product_id': product_id,
                'type': position_type,
                'size': size,
                'side': 'long' if size > 0 else 'short',
                'entry_price': entry_price,
                'current_price': mark_price,
                'unrealized_pnl': unrealized_pnl,
                'delta': delta,
                'vega': vega,
                'theta': theta,
                'gamma': gamma,
                'notional_deployed': round(notional_deployed, 2),
                'exchange': 'delta_exchange'
            })
            
            total_pnl += unrealized_pnl
            total_delta += delta
            total_vega += vega
            total_theta += theta
            total_notional_deployed += notional_deployed
        
        return {
            'positions': positions_data,
            'summary': {
                'total_positions': len(positions_data),
                'total_pnl': round(total_pnl, 2),
                'total_pnl_usd': round(total_pnl, 2),
                'total_pnl_inr': round(total_pnl * usd_to_inr_rate, 2),
                'portfolio_delta': round(total_delta, 2),
                'portfolio_vega': round(total_vega, 2),
                'portfolio_theta': round(total_theta, 2),
                'total_notional_deployed': round(total_notional_deployed, 2),
                'data_source': 'delta_exchange'
            }
        }
        
    except Exception as e:
        log.debug(f"Delta API positions fetch failed: {e}")
        return None


def _get_positions_from_file():
    """Get positions from bot's positions file"""
    try:
        from webui.backend.utils.process_helpers import is_bot_running
        
        # Only use file if bot is running
        if not is_bot_running():
            return None
        
        if not POSITIONS_FILE.exists():
            return None
        
        import json
        with open(POSITIONS_FILE, 'r') as f:
            raw_positions = json.load(f)
        
        if not raw_positions or not raw_positions.get('positions'):
            return None
        
        data = copy.deepcopy(raw_positions)
        usd_to_inr_rate = float(get_config_value('market.usd_to_inr_rate', 'USD_TO_INR_RATE', 85))
        total_notional_deployed = 0
        
        for position in data['positions']:
            notional_slab = position.get('notional', 0)
            notional_deployed = notional_slab * usd_to_inr_rate
            position['notional_deployed'] = round(notional_deployed, 2)
            total_notional_deployed += notional_deployed
            
            # Add default Greek values if not present
            if 'delta' not in position:
                position['delta'] = 0
            if 'vega' not in position:
                position['vega'] = 0
            if 'theta' not in position:
                position['theta'] = 0
        
        if 'summary' not in data:
            data['summary'] = {}
        
        data['summary']['total_notional_deployed'] = round(total_notional_deployed, 2)
        data['summary']['portfolio_delta'] = sum(p.get('delta', 0) for p in data['positions'])
        data['summary']['portfolio_vega'] = sum(p.get('vega', 0) for p in data['positions'])
        data['summary']['portfolio_theta'] = sum(p.get('theta', 0) for p in data['positions'])
        data['summary']['data_source'] = 'positions_file'
        
        return data
        
    except Exception as e:
        log.debug(f"Positions file read failed: {e}")
        return None


def _get_positions_from_guardian():
    """Get positions from Guardian health data (fallback)"""
    try:
        from webui.backend.utils.process_helpers import is_bot_running
        
        if not is_bot_running():
            return None
        
        # Try to get guardian health
        health_file = BASE_DIR / '.guardian_health.json'
        if not health_file.exists():
            return None
        
        import json
        with open(health_file, 'r') as f:
            health = json.load(f)
        
        if health.get('status') != 'ok':
            return None
        
        monitoring = health.get('monitoring', {})
        position_count = monitoring.get('position_count', 0)
        
        if position_count == 0:
            return None
        
        total_pnl_inr = monitoring.get('total_pnl_inr', 0.0)
        total_pnl_usd = monitoring.get('total_pnl_usd', 0.0)
        usd_to_inr_rate = float(get_config_value('market.usd_to_inr_rate', 'USD_TO_INR_RATE', 85))
        notional_slab = monitoring.get('total_notional_usd', 0)
        notional_deployed = notional_slab * usd_to_inr_rate
        
        return {
            'positions': [{
                'id': 'guardian_monitored',
                'size': position_count,
                'entry_price': 0,
                'current_price': monitoring.get('last_price', 0),
                'pnl_inr': total_pnl_inr,
                'pnl_usd': total_pnl_usd,
                'notional': notional_slab,
                'notional_deployed': round(notional_deployed, 2)
            }],
            'summary': {
                'total_positions': position_count,
                'total_pnl_usd': total_pnl_usd,
                'total_pnl_inr': total_pnl_inr,
                'total_notional_deployed': round(notional_deployed, 2),
                'data_source': 'guardian'
            },
            'source': 'guardian'
        }
        
    except Exception as e:
        log.debug(f"Guardian positions fetch failed: {e}")
        return None


def _load_state_data():
    """Load bot runtime state from state file"""
    try:
        if not STATE_FILE.exists():
            return {}
        
        import json
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
            
    except Exception as e:
        log.error(f"Error loading state: {e}")
        return {}


def _resync_positions_from_reconciliation():
    """Resync positions from reconciliation engine"""
    try:
        from bot.reconciliation import get_reconciliation_engine
        
        engine = get_reconciliation_engine()
        if not engine:
            return False, "Reconciliation engine not available"
        
        # Get latest open positions from exchange
        open_positions = engine.get_open_positions()
        
        # Save to positions file
        import json
        positions_data = {
            'positions': open_positions,
            'last_update': str(datetime.utcnow()),
            'source': 'reconciliation'
        }
        
        with open(POSITIONS_FILE, 'w') as f:
            json.dump(positions_data, f, indent=2)
        
        return True, f"Resynced {len(open_positions)} positions successfully"
        
    except Exception as e:
        log.error(f"Resync failed: {e}")
        return False, str(e)
