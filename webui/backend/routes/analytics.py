"""
Analytics API routes - comprehensive trading analytics
"""
from flask import Blueprint, jsonify, request
import sqlite3
from datetime import datetime, timedelta
import random

analytics_bp = Blueprint('analytics', __name__)

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('trading_bot.db')
    conn.row_factory = sqlite3.Row
    return conn

@analytics_bp.route('/api/analytics/summary', methods=['GET'])
def get_analytics_summary():
    """Get comprehensive analytics summary"""
    try:
        days = request.args.get('days', 30, type=int)
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get trade stats
        cursor.execute('''
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                MAX(pnl) as best_trade,
                MIN(pnl) as worst_trade
            FROM trades
            WHERE created_at >= ?
        ''', (cutoff_date,))
        trade_stats = cursor.fetchone()
        
        # Get position stats
        cursor.execute('''
            SELECT 
                COUNT(*) as open_positions,
                SUM(unrealized_pnl) as total_unrealized_pnl,
                AVG(unrealized_pnl_pct) as avg_unrealized_pct
            FROM positions
            WHERE status = 'OPEN'
        ''')
        position_stats = cursor.fetchone()
        
        # Get daily PnL trend
        cursor.execute('''
            SELECT 
                DATE(created_at) as date,
                SUM(pnl) as daily_pnl,
                COUNT(*) as trade_count
            FROM trades
            WHERE created_at >= ?
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 30
        ''', (cutoff_date,))
        daily_pnl = cursor.fetchall()
        
        conn.close()
        
        total_trades = trade_stats['total_trades'] or 0
        winning_trades = trade_stats['winning_trades'] or 0
        
        summary = {
            'period_days': days,
            'trades': {
                'total': total_trades,
                'winning': winning_trades,
                'losing': total_trades - winning_trades,
                'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0
            },
            'pnl': {
                'realized': float(trade_stats['total_pnl']) if trade_stats['total_pnl'] else 0,
                'unrealized': float(position_stats['total_unrealized_pnl']) if position_stats['total_unrealized_pnl'] else 0,
                'total': (float(trade_stats['total_pnl']) if trade_stats['total_pnl'] else 0) + 
                        (float(position_stats['total_unrealized_pnl']) if position_stats['total_unrealized_pnl'] else 0),
                'avg_per_trade': float(trade_stats['avg_pnl']) if trade_stats['avg_pnl'] else 0,
                'best_trade': float(trade_stats['best_trade']) if trade_stats['best_trade'] else 0,
                'worst_trade': float(trade_stats['worst_trade']) if trade_stats['worst_trade'] else 0
            },
            'positions': {
                'open': position_stats['open_positions'] or 0,
                'avg_unrealized_pct': float(position_stats['avg_unrealized_pct']) if position_stats['avg_unrealized_pct'] else 0
            },
            'daily_trend': [
                {
                    'date': row['date'],
                    'pnl': float(row['daily_pnl']) if row['daily_pnl'] else 0,
                    'trades': row['trade_count']
                }
                for row in daily_pnl
            ]
        }
        
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/analytics/performance', methods=['GET'])
def get_performance_metrics():
    """Get detailed performance metrics"""
    try:
        days = request.args.get('days', 30, type=int)
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all trades for calculation
        cursor.execute('''
            SELECT pnl, created_at FROM trades
            WHERE created_at >= ?
            ORDER BY created_at
        ''', (cutoff_date,))
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            return jsonify({
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'profit_factor': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'expectancy': 0
            })
        
        # Calculate metrics
        pnls = [float(t['pnl']) if t['pnl'] else 0 for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Max drawdown (simplified)
        cumulative = 0
        peak = 0
        max_dd = 0
        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        
        metrics = {
            'sharpe_ratio': 0,  # Requires volatility calculation
            'max_drawdown': max_dd,
            'max_drawdown_pct': (max_dd / peak * 100) if peak > 0 else 0,
            'profit_factor': profit_factor,
            'avg_win': sum(wins) / len(wins) if wins else 0,
            'avg_loss': sum(losses) / len(losses) if losses else 0,
            'expectancy': sum(pnls) / len(pnls) if pnls else 0,
            'total_trades': len(pnls),
            'win_rate': len(wins) / len(pnls) * 100 if pnls else 0
        }
        
        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
