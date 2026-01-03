"""
Strategy comparison API routes
"""
from flask import Blueprint, jsonify, request
import random
from datetime import datetime, timedelta

strategies_bp = Blueprint('strategies', __name__)

@strategies_bp.route('/api/strategies/comparison', methods=['GET'])
def get_strategy_comparison():
    """Get comparison of different strategies"""
    try:
        days = request.args.get('days', 30, type=int)
        
        # Mock strategy comparison data
        strategies = [
            {
                'name': 'Grid Trading',
                'type': 'grid',
                'performance': {
                    'total_pnl': round(random.uniform(800, 1500), 2),
                    'total_pnl_pct': round(random.uniform(8, 15), 2),
                    'win_rate': round(random.uniform(65, 75), 2),
                    'trades': random.randint(200, 400),
                    'sharpe_ratio': round(random.uniform(1.8, 2.5), 2),
                    'max_drawdown': round(random.uniform(5, 10), 2)
                },
                'status': 'active'
            },
            {
                'name': 'DCA (Dollar Cost Average)',
                'type': 'dca',
                'performance': {
                    'total_pnl': round(random.uniform(500, 1000), 2),
                    'total_pnl_pct': round(random.uniform(5, 10), 2),
                    'win_rate': round(random.uniform(60, 70), 2),
                    'trades': random.randint(50, 150),
                    'sharpe_ratio': round(random.uniform(1.5, 2.0), 2),
                    'max_drawdown': round(random.uniform(3, 8), 2)
                },
                'status': 'active'
            },
            {
                'name': 'Momentum',
                'type': 'momentum',
                'performance': {
                    'total_pnl': round(random.uniform(300, 800), 2),
                    'total_pnl_pct': round(random.uniform(3, 8), 2),
                    'win_rate': round(random.uniform(55, 65), 2),
                    'trades': random.randint(100, 250),
                    'sharpe_ratio': round(random.uniform(1.2, 1.8), 2),
                    'max_drawdown': round(random.uniform(8, 15), 2)
                },
                'status': 'testing'
            },
            {
                'name': 'Mean Reversion',
                'type': 'mean_reversion',
                'performance': {
                    'total_pnl': round(random.uniform(400, 900), 2),
                    'total_pnl_pct': round(random.uniform(4, 9), 2),
                    'win_rate': round(random.uniform(58, 68), 2),
                    'trades': random.randint(150, 300),
                    'sharpe_ratio': round(random.uniform(1.4, 2.2), 2),
                    'max_drawdown': round(random.uniform(6, 12), 2)
                },
                'status': 'inactive'
            }
        ]
        
        # Add daily performance for each strategy
        for strategy in strategies:
            strategy['daily_performance'] = [
                {
                    'date': (datetime.now() - timedelta(days=days-i)).strftime('%Y-%m-%d'),
                    'pnl': round(random.uniform(-20, 50), 2)
                }
                for i in range(min(days, 30))
            ]
        
        return jsonify({
            'strategies': strategies,
            'period_days': days,
            'best_performer': max(strategies, key=lambda x: x['performance']['total_pnl'])['name'],
            'most_consistent': max(strategies, key=lambda x: x['performance']['sharpe_ratio'])['name']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@strategies_bp.route('/api/strategies/<strategy_name>', methods=['GET'])
def get_strategy_details(strategy_name):
    """Get detailed information about a specific strategy"""
    try:
        # Mock detailed strategy data
        details = {
            'name': strategy_name,
            'description': f'{strategy_name} trading strategy with optimized parameters',
            'parameters': {
                'grid_lower': 85000,
                'grid_upper': 95000,
                'grid_step': 500,
                'max_positions': 50,
                'position_size': 0.02
            },
            'performance': {
                'total_pnl': round(random.uniform(500, 2000), 2),
                'win_rate': round(random.uniform(60, 75), 2),
                'trades': random.randint(100, 500),
                'avg_trade_duration': f'{random.randint(1, 24)} hours'
            },
            'risk_metrics': {
                'sharpe_ratio': round(random.uniform(1.5, 3.0), 2),
                'max_drawdown': round(random.uniform(5, 15), 2),
                'volatility': round(random.uniform(10, 25), 2)
            }
        }
        
        return jsonify(details)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
