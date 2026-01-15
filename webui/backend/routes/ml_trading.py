"""
ML Trading API Endpoints

Provides REST API for:
- Viewing trade history
- Training ML model
- Getting predictions
- Generating automation rules

Created: January 14, 2026
"""

import sys
from pathlib import Path
from flask import Blueprint, request, jsonify
from datetime import datetime
import pandas as pd

# Add backend directory to path for direct file imports
_backend_dir = str(Path(__file__).parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Add project root for config imports
_project_root = str(Path(__file__).parent.parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import ML components directly (bypass options_strategy/__init__.py)
# This avoids the circular import chain
import importlib.util

def _import_direct(name, path):
    """Import a module directly from file path without triggering __init__.py"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Import trade_logger directly
_trade_logger_module = _import_direct(
    'trade_logger_direct',
    Path(__file__).parent.parent / 'options_strategy' / 'trade_logger.py'
)
trade_logger = _trade_logger_module.trade_logger

# Import ml_model directly
_ml_model_module = _import_direct(
    'ml_model_direct', 
    Path(__file__).parent.parent / 'options_strategy' / 'ml_model.py'
)
options_ml_model = _ml_model_module.options_ml_model

ml_trading_bp = Blueprint('ml_trading', __name__)


# ============================================================
# TRADE HISTORY ENDPOINTS
# ============================================================

@ml_trading_bp.route('/api/ml/trades', methods=['GET'])
def get_trades():
    """Get all trades with optional filtering."""
    try:
        days = request.args.get('days', type=int)
        symbol = request.args.get('symbol')
        
        if symbol:
            df = trade_logger.get_trades_by_symbol(symbol)
        elif days:
            df = trade_logger.get_recent_trades(days)
        else:
            df = trade_logger.get_all_trades()
        
        # Convert to list of dicts
        trades = df.to_dict('records') if len(df) > 0 else []
        
        return jsonify({
            'success': True,
            'trades': trades,
            'count': len(trades),
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/trades/stats', methods=['GET'])
def get_trade_stats():
    """Get trade statistics."""
    try:
        stats = trade_logger.get_trade_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats,
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/trades/log', methods=['POST'])
def log_trade():
    """Manually log a trade (for testing or manual entry)."""
    try:
        data = request.json
        
        required = ['symbol', 'action', 'quantity', 'price']
        for field in required:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}',
                }), 400
        
        trade_id = trade_logger.log_trade(
            symbol=data['symbol'],
            action=data['action'],
            quantity=data['quantity'],
            price=data['price'],
            side=data.get('side', 'OPEN'),
            position_before=data.get('position_before'),
            market_data=data.get('market_data'),
            greeks=data.get('greeks'),
            strategy_tag=data.get('strategy_tag', ''),
            automation_rule=data.get('automation_rule', ''),
            user_notes=data.get('user_notes', ''),
        )
        
        return jsonify({
            'success': True,
            'trade_id': trade_id,
            'message': f'Trade logged successfully',
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/trades/<trade_id>/outcome', methods=['PUT'])
def update_trade_outcome(trade_id):
    """Update trade outcome when position is closed."""
    try:
        data = request.json
        
        trade_logger.update_trade_outcome(
            trade_id=trade_id,
            pnl=data.get('pnl', 0),
            pnl_pct=data.get('pnl_pct', 0),
            duration_hours=data.get('duration_hours', 0),
            max_profit=data.get('max_profit', 0),
            max_loss=data.get('max_loss', 0),
            status=data.get('status', 'closed'),
        )
        
        return jsonify({
            'success': True,
            'message': f'Trade {trade_id} outcome updated',
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/trades/export', methods=['GET'])
def export_trades():
    """Export trades for ML training."""
    try:
        output_file = trade_logger.export_for_ml()
        
        return jsonify({
            'success': True,
            'file': output_file,
            'message': 'Trades exported successfully',
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# ML MODEL ENDPOINTS
# ============================================================

@ml_trading_bp.route('/api/ml/model/status', methods=['GET'])
def get_model_status():
    """Get ML model status and metrics."""
    try:
        status = options_ml_model.get_model_status()
        
        return jsonify({
            'success': True,
            **status,
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/model/train', methods=['POST'])
def train_model():
    """Train or retrain the ML model."""
    try:
        force = request.json.get('force', False) if request.json else False
        
        result = options_ml_model.train(force=force)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/model/predict', methods=['POST'])
def predict_trade():
    """Get prediction for a potential trade."""
    try:
        trade_params = request.json
        
        if not trade_params:
            return jsonify({
                'success': False,
                'error': 'Trade parameters required',
            }), 400
        
        result = options_ml_model.predict(trade_params)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# PATTERN ANALYSIS ENDPOINTS
# ============================================================

@ml_trading_bp.route('/api/ml/patterns', methods=['GET'])
def analyze_patterns():
    """Analyze trading patterns from historical data."""
    try:
        result = options_ml_model.analyze_patterns()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/automation-rules', methods=['GET'])
def get_automation_rules():
    """Generate automation rule suggestions."""
    try:
        result = options_ml_model.generate_automation_rules()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/suggestion', methods=['POST'])
def get_trade_suggestion():
    """Get trade suggestion based on current market conditions."""
    try:
        market_conditions = request.json or {}
        
        result = options_ml_model.get_trade_suggestion(market_conditions)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# DASHBOARD SUMMARY
# ============================================================

@ml_trading_bp.route('/api/ml/dashboard', methods=['GET'])
def get_ml_dashboard():
    """Get comprehensive ML dashboard data."""
    try:
        # Model status
        model_status = options_ml_model.get_model_status()
        
        # Trade statistics
        trade_stats = trade_logger.get_trade_statistics()
        
        # Recent trades
        recent_trades = trade_logger.get_recent_trades(days=7)
        recent_count = len(recent_trades)
        
        # Pattern analysis (if enough data)
        patterns = None
        if trade_stats.get('closed_trades', 0) >= 10:
            patterns_result = options_ml_model.analyze_patterns()
            if patterns_result.get('success'):
                patterns = patterns_result.get('patterns')
        
        # Automation rules (if model trained)
        automation_rules = None
        if model_status.get('is_trained'):
            rules_result = options_ml_model.generate_automation_rules()
            if rules_result.get('success'):
                automation_rules = rules_result.get('rules')
        
        return jsonify({
            'success': True,
            'model': model_status,
            'statistics': trade_stats,
            'recent_trades_count': recent_count,
            'patterns': patterns,
            'automation_rules': automation_rules,
            'readiness': {
                'can_train': model_status.get('can_train', False),
                'is_trained': model_status.get('is_trained', False),
                'trades_needed': max(0, 30 - trade_stats.get('total_trades', 0)),
                'closed_trades_needed': max(0, 20 - trade_stats.get('closed_trades', 0)),
            },
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500
