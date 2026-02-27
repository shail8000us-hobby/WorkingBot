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
import hashlib
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
        # ARCH-3 FIX: use service layer functions that return plain dicts
        # instead of calling Flask route handlers and parsing their response objects.
        from .dashboard_service import (
            fetch_options_positions_data,
            fetch_pending_orders_data,
            fetch_futures_positions_data,
            fetch_options_status_data,
            fetch_margin_data,
        )
        
        positions_data = fetch_options_positions_data()
        pending_data = fetch_pending_orders_data()
        futures_data = fetch_futures_positions_data()
        status_data = fetch_options_status_data()
        margin_data = fetch_margin_data()
        
        # Extract positions for Greeks calculation
        positions = positions_data.get('positions', [])

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
        # ARCH-4 FIX: use md5 hex digest — deterministic across restarts, safe JS integer range
        content_hash = hashlib.md5(
            (pos_fingerprint + str(len(pending_orders_list))).encode()
        ).hexdigest()

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
            'margin': margin_data,
            'last_modified': content_hash,
            'server_timestamp': int(time.time() * 1000),
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
