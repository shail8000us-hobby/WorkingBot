"""
Backtest API routes
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import random

backtest_bp = Blueprint('backtest', __name__)

@backtest_bp.route('/api/backtest/results/latest', methods=['GET'])
def get_latest_backtest():
    """
    Get latest backtest results (mock data)
    
    v6.0: Supports per-instance backtests
    Query params:
        instance: Optional instance name (e.g., BTCUSD_LONG)
    """
    try:
        # v6.0: Extract instance parameter
        instance = request.args.get('instance')
        symbol = instance.split('_')[0] if instance else 'BTCUSD'
        
        # Mock backtest results
        results = {
            'id': 'backtest_' + datetime.now().strftime('%Y%m%d_%H%M%S'),
            'status': 'completed',
            'instance': instance,
            'config': {
                'symbol': symbol,
                'start_date': (datetime.now() - timedelta(days=30)).isoformat(),
                'end_date': datetime.now().isoformat(),
                'initial_capital': 10000,
                'grid_lower': 85000,
                'grid_upper': 95000,
                'grid_step': 500
            },
            'results': {
                'total_trades': random.randint(100, 500),
                'winning_trades': random.randint(60, 300),
                'losing_trades': random.randint(40, 200),
                'win_rate': round(random.uniform(55, 75), 2),
                'total_pnl': round(random.uniform(500, 2000), 2),
                'total_pnl_pct': round(random.uniform(5, 20), 2),
                'max_drawdown': round(random.uniform(5, 15), 2),
                'sharpe_ratio': round(random.uniform(1.5, 3.0), 2),
                'profit_factor': round(random.uniform(1.2, 2.5), 2),
                'final_capital': 10000 + random.uniform(500, 2000)
            },
            'daily_returns': [
                {
                    'date': (datetime.now() - timedelta(days=30-i)).strftime('%Y-%m-%d'),
                    'pnl': round(random.uniform(-50, 100), 2),
                    'cumulative_pnl': round(random.uniform(0, 2000), 2)
                }
                for i in range(30)
            ],
            'created_at': datetime.now().isoformat()
        }
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@backtest_bp.route('/api/backtest/run', methods=['POST'])
def run_backtest():
    """Start a new backtest"""
    try:
        config = request.get_json()
        
        # Mock response - in production, this would trigger actual backtest
        backtest_id = 'backtest_' + datetime.now().strftime('%Y%m%d_%H%M%S')
        
        return jsonify({
            'status': 'started',
            'backtest_id': backtest_id,
            'message': 'Backtest started successfully',
            'estimated_time': '5-10 minutes'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@backtest_bp.route('/api/backtest/history', methods=['GET'])
def get_backtest_history():
    """Get list of past backtests"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        # Mock historical backtests
        history = [
            {
                'id': f'backtest_{i}',
                'symbol': 'BTCUSD',
                'status': 'completed',
                'total_pnl': round(random.uniform(-500, 2000), 2),
                'win_rate': round(random.uniform(50, 75), 2),
                'trades': random.randint(50, 500),
                'created_at': (datetime.now() - timedelta(days=i)).isoformat()
            }
            for i in range(limit)
        ]
        
        return jsonify({
            'backtests': history,
            'total': limit
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
