"""
Options Dashboard API - Unified Data Endpoint

Phase 2 Optimization: Single endpoint to fetch all dashboard data in one request.
Reduces 4 round-trips to 1, dramatically improving panel load time.

Endpoint:
- GET /api/options/dashboard - Get positions, pending orders, futures, status, and portfolio Greeks

Created: February 4, 2026 (Phase 2 Optimization)
"""

import sys
import time
import logging
from pathlib import Path
from flask import Blueprint, jsonify

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config, get_api_credentials

log = logging.getLogger(__name__)

# Create blueprint
dashboard_bp = Blueprint('options_dashboard', __name__, url_prefix='/api/options')


def calculate_portfolio_greeks(positions):
    """
    Calculate aggregated portfolio Greeks from positions.
    This offloads calculation from frontend to backend for better performance.
    
    Args:
        positions: List of position dicts with greeks data
        
    Returns:
        dict: Aggregated Greeks {delta, gamma, theta, vega, btcDelta, ethDelta}
    """
    greeks = {
        'delta': 0.0,
        'gamma': 0.0,
        'theta': 0.0,
        'vega': 0.0,
        'btcDelta': 0.0,
        'ethDelta': 0.0,
        'count': 0
    }
    
    if not positions:
        return greeks
    
    for pos in positions:
        size = pos.get('size', 0)
        if not size:
            continue
            
        pos_greeks = pos.get('greeks', {})
        if not pos_greeks:
            continue
        
        # Per-contract Greeks
        per_contract_delta = float(pos_greeks.get('delta', 0))
        per_contract_gamma = float(pos_greeks.get('gamma', 0))
        per_contract_theta = float(pos_greeks.get('theta', 0))
        per_contract_vega = float(pos_greeks.get('vega', 0))
        
        # Aggregate position Greeks
        # Delta: signed by position size
        greeks['delta'] += per_contract_delta * size
        greeks['gamma'] += per_contract_gamma * abs(size)
        
        # Theta and Vega: Delta Exchange uses internal units (divide by 1000 for USD)
        # Short positions (size < 0) earn theta (option loses value = our profit)
        greeks['theta'] += (per_contract_theta / 1000) * size
        greeks['vega'] += (per_contract_vega / 1000) * abs(size)
        greeks['count'] += 1
        
        # Separate delta by underlying for futures equivalent
        symbol = pos.get('product_symbol', '')
        parts = symbol.split('-')
        if len(parts) >= 2:
            underlying = parts[1]  # BTC or ETH
            delta_contribution = per_contract_delta * size
            
            if underlying == 'BTC':
                greeks['btcDelta'] += delta_contribution
            elif underlying == 'ETH':
                greeks['ethDelta'] += delta_contribution
    
    return greeks


@dashboard_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """
    Unified dashboard endpoint - returns all data in one response.
    
    Phase 2 Optimization: Replaces 4 separate API calls with 1.
    
    Returns:
        {
            "success": true,
            "positions": [...],
            "pending_orders": [...],
            "futures_positions": [...],
            "status": {...},
            "portfolio_greeks": {...},
            "last_modified": timestamp,
            "response_time_ms": float
        }
    """
    start_time = time.time()
    
    try:
        # Reuse existing route functions - no circular deps since we call them as functions, not through routes
        from .options_control import get_options_positions, get_options_status
        from ..positions import get_pending_orders
        from ..futures.futures_api import get_futures_positions
        
        # Call the existing route handlers directly (avoids HTTP overhead)
        # These functions return (response, status_code) tuples
        positions_response = get_options_positions()
        positions_response = positions_response[0] if isinstance(positions_response, tuple) else positions_response
        positions_data = positions_response.get_json() if hasattr(positions_response, 'get_json') else positions_response
        
        pending_response = get_pending_orders()
        pending_response = pending_response[0] if isinstance(pending_response, tuple) else pending_response
        pending_data = pending_response.get_json() if hasattr(pending_response, 'get_json') else pending_response
        
        futures_response = get_futures_positions()
        futures_response = futures_response[0] if isinstance(futures_response, tuple) else futures_response
        futures_data = futures_response.get_json() if hasattr(futures_response, 'get_json') else futures_response
        
        status_response = get_options_status()
        status_response = status_response[0] if isinstance(status_response, tuple) else status_response
        status_data = status_response.get_json() if hasattr(status_response, 'get_json') else status_response
        
        # Extract positions for Greeks calculation
        positions = positions_data.get('positions', []) if isinstance(positions_data, dict) else []

        # Calculate portfolio Greeks server-side (Phase 2 optimization)
        portfolio_greeks = calculate_portfolio_greeks(positions)

        # Phase 5 Optimization: Use content-based last_modified
        # Generate a fingerprint from position symbols + sizes + prices so frontend
        # can skip re-renders when nothing actually changed
        pos_fingerprint = '|'.join(
            f"{p.get('product_symbol','')},{p.get('size',0)},{p.get('best_bid',0)},{p.get('best_ask',0)},{p.get('unrealized_pnl',0)}"
            for p in positions
        )
        pending_orders_list = pending_data.get('orders', []) if isinstance(pending_data, dict) else []
        content_hash = hash(pos_fingerprint + str(len(pending_orders_list)))

        # Response time tracking
        response_time_ms = (time.time() - start_time) * 1000

        # Build unified response
        response = {
            'success': True,
            'positions': positions,
            'pending_orders': pending_orders_list,
            'futures_positions': futures_data.get('positions', []) if isinstance(futures_data, dict) else [],
            'status': status_data if isinstance(status_data, dict) else {},
            'portfolio_greeks': portfolio_greeks,
            'last_modified': content_hash,
            'response_time_ms': round(response_time_ms, 2),
            'optimization': 'phase_5_content_hash'
        }
        
        log.info(f"Dashboard data fetched in {response_time_ms:.2f}ms")
        
        return jsonify(response), 200
        
    except Exception as e:
        log.error(f"Dashboard fetch error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'response_time_ms': (time.time() - start_time) * 1000
        }), 500
