"""
Grid Calculations API Routes

Provides endpoints for real-time grid calculation previews using GridCalculator.
Used by WebUI to show BUY/SELL sequences, TP levels, and grid visualizations.

Routes:
    GET /api/grid/calculations - Get grid calculation preview
"""

import logging
import sys
from pathlib import Path
from flask import Blueprint, jsonify, request
from typing import Dict, List, Any, Optional

# Add bot directory to path for imports
BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from bot.strategy.modules.grid_calculator import GridCalculator

log = logging.getLogger(__name__)

# Create blueprint
grid_calculations_bp = Blueprint('grid_calculations', __name__)


def _get_reason(
    order_num: int,
    open_positions: List[Dict],
    ref: float,
    step: float,
    mode: str
) -> str:
    """Generate human-readable reason for order placement"""
    if order_num == 0 and len(open_positions) == 0:
        if mode == 'LONG':
            return f"Starting from reference level (REF - STEP = ${ref:,.0f} - ${step:,.0f})"
        else:
            return f"Starting from reference level (REF + STEP = ${ref:,.0f} + ${step:,.0f})"
    elif order_num == 0:
        return "First order from reference"
    elif len(open_positions) == 0:
        return "No open positions, using reference"
    else:
        if mode == 'LONG':
            return f"One step below lowest position (${open_positions[-1]['entry_price']:,.0f} - ${step:,.0f})"
        else:
            return f"One step above highest position (${open_positions[-1]['entry_price']:,.0f} + ${step:,.0f})"


def _classify_level(price: float, lower: float, upper: float, ref: float) -> str:
    """Classify a grid level for visualization"""
    if abs(price - lower) < 0.01:
        return "lower_bound"
    elif abs(price - upper) < 0.01:
        return "upper_bound"
    elif abs(price - ref) < 0.01:
        return "reference"
    else:
        return "grid_level"


@grid_calculations_bp.route('/api/grid/calculations', methods=['GET'])
def get_grid_calculations():
    """
    Calculate grid sequences using GridCalculator
    
    Query Parameters:
        mode (str): 'LONG' or 'SHORT' (default: LONG)
        lower (float): Grid lower bound (default: 99000)
        upper (float): Grid upper bound (default: 110000)
        step (float): Grid step size (default: 500)
        ref (float): Reference level (default: 103800)
        tick_size (float): Exchange tick size (default: 0.5)
        max_open (int): Max open positions (default: 5)
        current_price (float): Optional market price for strict grid logic
    
    Returns:
        JSON response with:
        - mode: LONG or SHORT
        - grid_config: Grid parameters and metadata
        - buy_sequence: List of entry orders (BUY for LONG, SELL for SHORT)
        - tp_sequence: List of take-profit targets
        - next_after_tp: Next order after first TP fills
        - grid_levels: All grid levels for visualization
        - validation: Bounds checking results
    
    Example:
        GET /api/grid/calculations?mode=LONG&lower=99000&upper=110000&step=500&ref=103800
    """
    try:
        # Get parameters from query string
        mode = request.args.get('mode', 'LONG').upper()
        lower = float(request.args.get('lower', 99000))
        upper = float(request.args.get('upper', 110000))
        step = float(request.args.get('step', 500))
        ref = float(request.args.get('ref', 103800))
        tick_size = float(request.args.get('tick_size', 0.5))
        max_open = int(request.args.get('max_open', 5))
        current_price = request.args.get('current_price')
        
        if current_price:
            current_price = float(current_price)
        else:
            current_price = ref  # Default to reference if not provided
        
        # Validate mode
        if mode not in ['LONG', 'SHORT']:
            return jsonify({
                'success': False,
                'error': f"Invalid mode '{mode}'. Must be 'LONG' or 'SHORT'"
            }), 400
        
        # Initialize GridCalculator
        try:
            calc = GridCalculator(
                lower=lower,
                upper=upper,
                step=step,
                ref=ref,
                tick_size=tick_size
            )
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f"Invalid grid parameters: {str(e)}"
            }), 400
        
        # Calculate entry sequence (BUY for LONG, SELL for SHORT)
        entry_sequence = []
        open_positions = []
        
        for i in range(max_open):
            if mode == 'LONG':
                next_price = calc.compute_next_buy_level(
                    open_positions=open_positions,
                    current_price=current_price
                )
            else:  # SHORT
                next_price = calc.compute_next_sell_level(
                    open_positions=open_positions,
                    current_price=current_price
                )
            
            if next_price is None:
                # Out of bounds, can't place more orders
                break
            
            entry_sequence.append({
                'order_num': i + 1,
                'price': round(next_price, 2),
                'reason': _get_reason(i, open_positions, ref, step, mode),
                'within_bounds': calc.is_within_bounds(next_price)
            })
            
            # Simulate position opening
            open_positions.append({'entry_price': next_price, 'qty': 1})
        
        # Calculate TP sequence
        tp_sequence = []
        for i, pos in enumerate(open_positions):
            if mode == 'LONG':
                tp = calc.compute_tp_price(pos['entry_price'])
            else:  # SHORT
                tp = calc.compute_tp_price_short(pos['entry_price'])
            
            profit = abs(tp - pos['entry_price'])
            
            tp_sequence.append({
                'position_num': i + 1,
                'entry': round(pos['entry_price'], 2),
                'tp': round(tp, 2),
                'profit': round(profit, 2),
                'within_bounds': calc.is_within_bounds(tp)
            })
        
        # Calculate next entry after first TP fills
        remaining_positions = open_positions[1:] if len(open_positions) > 1 else []
        
        if remaining_positions:
            if mode == 'LONG':
                next_after_tp = calc.compute_next_buy_level(
                    open_positions=remaining_positions,
                    current_price=current_price
                )
            else:  # SHORT
                next_after_tp = calc.compute_next_sell_level(
                    open_positions=remaining_positions,
                    current_price=current_price
                )
        else:
            # All positions closed, use strict grid logic
            if mode == 'LONG':
                next_after_tp = calc.find_nearest_grid_below(current_price)
            else:
                next_after_tp = calc.find_nearest_grid_above(current_price)
        
        # Get all grid levels
        grid_levels = calc.get_grid_levels()
        
        # Calculate total potential profit
        total_profit = sum(t['profit'] for t in tp_sequence)
        
        # Build next_after_tp info
        next_after_tp_info = {
            'scenario': 'After first TP fills' if remaining_positions else 'All positions closed',
            'remaining_positions': len(remaining_positions),
            'price': round(next_after_tp, 2) if next_after_tp is not None else None
        }
        
        # Build response
        response = {
            'success': True,
            'mode': mode,
            'entry_sequence': entry_sequence,
            'tp_sequence': tp_sequence,
            'next_after_tp': next_after_tp_info,
            'grid_levels': grid_levels,
            'grid_config': {
                'lower': lower,
                'upper': upper,
                'ref': ref,
                'step': step,
                'tick_size': tick_size,
                'max_open': max_open,
                'total_levels': len(grid_levels),
                'grid_span': upper - lower
            },
            'validation': {
                'all_entries_within_bounds': all(e['within_bounds'] for e in entry_sequence),
                'all_tps_within_bounds': all(t['within_bounds'] for t in tp_sequence),
                'total_potential_profit': round(total_profit, 2),
                'max_capital_required': round(max_open * current_price, 2)  # Rough estimate
            },
            'current_market_price': current_price
        }
        
        log.info(f"Grid calculations: mode={mode}, entries={len(entry_sequence)}, "
                f"profit=${total_profit:,.0f}, levels={len(grid_levels)}")
        
        return jsonify(response), 200
        
        log.info(f"Grid calculations: mode={mode}, entries={len(entry_sequence)}, "
                f"profit=${total_profit:,.0f}, levels={len(grid_levels)}")
        
        return jsonify(response), 200
        
    except ValueError as e:
        log.error(f"Invalid parameter: {e}")
        return jsonify({
            'success': False,
            'error': f"Invalid parameter: {str(e)}"
        }), 400
    except Exception as e:
        log.error(f"Error calculating grid: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Calculation error: {str(e)}"
        }), 500


# Register routes
def register_routes(app):
    """Register grid calculations routes with Flask app"""
    app.register_blueprint(grid_calculations_bp)
    log.info("Grid calculations routes registered")
