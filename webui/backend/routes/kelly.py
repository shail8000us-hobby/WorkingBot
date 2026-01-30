"""
Kelly Criterion Position Sizing API

Backend endpoint to provide Kelly-based position sizing recommendations.
"""

import sys
from pathlib import Path
from flask import Blueprint, jsonify, request
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from bot.institutional.kelly_position_sizer import KellyPositionSizer
from config.loader import get_config

log = logging.getLogger(__name__)

kelly_bp = Blueprint('kelly', __name__, url_prefix='/api/kelly')

# Initialize Kelly sizer globally
_kelly_sizer = None

def get_kelly_sizer():
    """Get or create Kelly sizer instance."""
    global _kelly_sizer
    if _kelly_sizer is None:
        _kelly_sizer = KellyPositionSizer(
            history_file="data/kelly_trade_history.json",
            kelly_fraction=0.25,  # Quarter Kelly (conservative)
            min_trades=20,
            lookback_days=30
        )
        _kelly_sizer.load_history()
    return _kelly_sizer


@kelly_bp.route('/sizing/<strategy>', methods=['GET'])
def get_position_sizing(strategy):
    """
    Get Kelly Criterion position sizing recommendation for a strategy.
    
    Args:
        strategy: Strategy name (e.g., 'iron_condor', 'straddle', 'strangle')
        
    Query Params:
        account_balance: Current account balance (optional, uses config if not provided)
        
    Returns:
        {
            "success": true,
            "strategy": "iron_condor",
            "kelly_percent": 0.12,           // 12% of account
            "position_size_usd": 12000,      // Actual dollars to risk
            "confidence": "MEDIUM",          // HIGH/MEDIUM/LOW
            "stats": {
                "total_trades": 35,
                "win_rate": 0.571,           // 57.1%
                "avg_win_usd": 320,
                "avg_loss_usd": 180,
                "win_loss_ratio": 1.78,
                "expectancy": 101.40         // $101.40 per trade
            },
            "recommendation": "Risk $12,000 per iron condor trade (12% of account)"
        }
    """
    try:
        kelly = get_kelly_sizer()
        
        # Get account balance from query params or config
        account_balance = request.args.get('account_balance', type=float)
        if not account_balance:
            try:
                config = get_config()
                account_balance = float(config.starting_capital)
            except:
                account_balance = 100000  # Default fallback
        
        # Get Kelly sizing
        sizing = kelly.calculate_kelly_size(strategy, account_balance)
        
        # Build recommendation text
        if sizing['confidence'] == 'LOW':
            reason = sizing.get('reason', 'Insufficient trade history')
            recommendation = f"Need more data. {reason}. Using conservative 1% sizing."
        else:
            kelly_pct = sizing['kelly_percent'] * 100
            recommendation = f"Risk ${sizing['position_size_usd']:,.0f} per {strategy} trade ({kelly_pct:.1f}% of account)"
        
        return jsonify({
            'success': True,
            'strategy': strategy,
            'kelly_percent': sizing['kelly_percent'],
            'position_size_usd': sizing['position_size_usd'],
            'confidence': sizing['confidence'],
            'stats': sizing.get('stats', {}),
            'recommendation': recommendation,
            'account_balance': account_balance
        })
        
    except Exception as e:
        log.error(f"Kelly sizing error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@kelly_bp.route('/all-strategies', methods=['GET'])
def get_all_strategy_sizing():
    """
    Get Kelly sizing for all strategies you've traded.
    
    Query Params:
        account_balance: Current account balance (optional)
        
    Returns:
        {
            "success": true,
            "account_balance": 100000,
            "strategies": {
                "iron_condor": {...},
                "straddle": {...},
                "strangle": {...}
            }
        }
    """
    try:
        kelly = get_kelly_sizer()
        
        # Get account balance
        account_balance = request.args.get('account_balance', type=float)
        if not account_balance:
            try:
                config = get_config()
                account_balance = float(config.starting_capital)
            except:
                account_balance = 100000
        
        # Get sizing for all strategies
        all_sizing = kelly.get_all_strategies_sizing(account_balance)
        
        return jsonify({
            'success': True,
            'account_balance': account_balance,
            'strategies': all_sizing
        })
        
    except Exception as e:
        log.error(f"All strategies error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@kelly_bp.route('/record-trade', methods=['POST'])
def record_trade():
    """
    Record a completed trade for Kelly calculation.
    
    Request Body:
        {
            "strategy": "iron_condor",
            "pnl": 250.50,           // Profit/loss in dollars
            "entry_price": 1.20,
            "exit_price": 1.45,
            "size": 10,
            "timestamp": "2026-01-30T10:30:00"  // Optional
        }
        
    Returns:
        {
            "success": true,
            "message": "Trade recorded for iron_condor",
            "new_stats": {...}
        }
    """
    try:
        data = request.get_json()
        
        strategy = data.get('strategy')
        pnl = data.get('pnl')
        
        if not strategy or pnl is None:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: strategy, pnl'
            }), 400
        
        kelly = get_kelly_sizer()
        
        # Parse timestamp if provided
        timestamp = None
        if 'timestamp' in data:
            from datetime import datetime
            timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        
        # Record the trade
        kelly.add_trade(strategy, float(pnl), timestamp)
        
        # Get updated stats
        account_balance = 100000  # Dummy value for stats
        sizing = kelly.calculate_kelly_size(strategy, account_balance)
        
        return jsonify({
            'success': True,
            'message': f'Trade recorded for {strategy}',
            'pnl': pnl,
            'new_stats': sizing.get('stats', {})
        })
        
    except Exception as e:
        log.error(f"Record trade error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@kelly_bp.route('/calculate-max-contracts', methods=['POST'])
def calculate_max_contracts():
    """
    Calculate max contracts to trade based on Kelly sizing.
    
    Request Body:
        {
            "strategy": "iron_condor",
            "account_balance": 100000,
            "premium_per_contract": 1.20  // How much each contract costs
        }
        
    Returns:
        {
            "success": true,
            "strategy": "iron_condor",
            "kelly_size_usd": 12000,
            "premium_per_contract": 1.20,
            "max_contracts": 100,           // 12000 / 1.20 / 10 (BTC multiplier)
            "recommendation": "Trade up to 100 contracts"
        }
    """
    try:
        data = request.get_json()
        
        strategy = data.get('strategy')
        account_balance = data.get('account_balance')
        premium = data.get('premium_per_contract')
        
        if not all([strategy, account_balance, premium]):
            return jsonify({
                'success': False,
                'error': 'Missing fields: strategy, account_balance, premium_per_contract'
            }), 400
        
        kelly = get_kelly_sizer()
        sizing = kelly.calculate_kelly_size(strategy, float(account_balance))
        
        kelly_size_usd = sizing['position_size_usd']
        
        # BTC options have 0.1 multiplier (1 contract = 0.1 BTC)
        # So premium_per_contract is already in dollars
        # Max contracts = Kelly size / premium per contract
        max_contracts = int(kelly_size_usd / float(premium)) if premium > 0 else 0
        
        return jsonify({
            'success': True,
            'strategy': strategy,
            'kelly_size_usd': kelly_size_usd,
            'premium_per_contract': float(premium),
            'max_contracts': max_contracts,
            'confidence': sizing['confidence'],
            'recommendation': f"Trade up to {max_contracts} contracts (Kelly size: ${kelly_size_usd:,.0f})"
        })
        
    except Exception as e:
        log.error(f"Calculate contracts error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@kelly_bp.route('/health', methods=['GET'])
def health():
    """Check Kelly system health."""
    try:
        kelly = get_kelly_sizer()
        strategies = list(kelly.strategy_stats.keys())
        total_trades = sum(
            s['wins'] + s['losses'] 
            for s in kelly.strategy_stats.values()
        )
        
        return jsonify({
            'success': True,
            'status': 'operational',
            'strategies_tracked': len(strategies),
            'total_trades': total_trades,
            'strategies': strategies
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
