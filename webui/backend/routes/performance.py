"""
Performance metrics API routes
"""
from flask import Blueprint, jsonify, request
import sqlite3
from datetime import datetime, timedelta

performance_bp = Blueprint('performance', __name__)

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('trading_bot.db')
    conn.row_factory = sqlite3.Row
    return conn

@performance_bp.route('/api/performance/metrics', methods=['GET'])
def get_performance_metrics():
    """Get real-time performance metrics"""
    try:
        days = request.args.get('days', 7, type=int)
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get trade metrics
        cursor.execute('''
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl
            FROM trades
            WHERE created_at >= ?
        ''', (cutoff_date,))
        trade_metrics = cursor.fetchone()
        
        # Get position metrics
        cursor.execute('''
            SELECT 
                COUNT(*) as open_positions,
                SUM(unrealized_pnl) as unrealized_pnl
            FROM positions
            WHERE status = 'OPEN'
        ''')
        position_metrics = cursor.fetchone()
        
        # Get hourly trade counts for activity
        cursor.execute('''
            SELECT 
                strftime('%Y-%m-%d %H:00:00', created_at) as hour,
                COUNT(*) as count,
                SUM(pnl) as pnl
            FROM trades
            WHERE created_at >= ?
            GROUP BY hour
            ORDER BY hour DESC
            LIMIT 24
        ''', (cutoff_date,))
        hourly_activity = cursor.fetchall()
        
        conn.close()
        
        total_trades = trade_metrics['total_trades'] or 0
        wins = trade_metrics['wins'] or 0
        
        metrics = {
            'summary': {
                'total_trades': total_trades,
                'win_rate': (wins / total_trades * 100) if total_trades > 0 else 0,
                'total_pnl': float(trade_metrics['total_pnl']) if trade_metrics['total_pnl'] else 0,
                'avg_pnl': float(trade_metrics['avg_pnl']) if trade_metrics['avg_pnl'] else 0,
                'open_positions': position_metrics['open_positions'] or 0,
                'unrealized_pnl': float(position_metrics['unrealized_pnl']) if position_metrics['unrealized_pnl'] else 0
            },
            'activity': [
                {
                    'hour': row['hour'],
                    'trades': row['count'],
                    'pnl': float(row['pnl']) if row['pnl'] else 0
                }
                for row in hourly_activity
            ],
            'period_days': days
        }
        
        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
