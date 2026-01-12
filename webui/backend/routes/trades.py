"""
Trade history API routes
"""
from flask import Blueprint, jsonify, request
import sqlite3
from datetime import datetime, timedelta

trades_bp = Blueprint('trades', __name__)

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('trading_bot.db')
    conn.row_factory = sqlite3.Row
    return conn

@trades_bp.route('/api/trades/history', methods=['GET'])
def get_trade_history():
    """
    Get trade history with optional filters
    
    v6.0: Supports per-instance trade history
    Query params:
        limit: Max trades to return (default: 50)
        symbol: Filter by symbol
        days: Filter by days back
        instance: Optional instance name (e.g., BTCUSD_LONG)
    """
    try:
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        symbol = request.args.get('symbol')
        days = request.args.get('days', type=int)
        instance = request.args.get('instance')  # v6.0: Instance parameter
        
        # v6.0: Use instance-specific database if provided
        if instance:
            db_name = f'trading_bot_{instance}.db'
        else:
            db_name = 'trading_bot.db'
        
        conn = sqlite3.connect(db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT * FROM trades WHERE 1=1'
        params = []
        
        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol)
        
        if days:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            query += ' AND created_at >= ?'
            params.append(cutoff_date)
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        trades = []
        for row in rows:
            trades.append({
                'id': row['id'],
                'symbol': row['symbol'],
                'side': row['side'],
                'mode': row['mode'],
                'price': float(row['price']) if row['price'] else 0,
                'quantity': float(row['quantity']) if row['quantity'] else 0,
                'total': float(row['total']) if row['total'] else 0,
                'pnl': float(row['pnl']) if row['pnl'] else 0,
                'pnl_pct': float(row['pnl_pct']) if row['pnl_pct'] else 0,
                'grid_level': row['grid_level'],
                'order_id': row['order_id'],
                'created_at': row['created_at'],
            })
        
        return jsonify({
            'trades': trades,
            'total': len(trades),
            'filters': {
                'symbol': symbol,
                'days': days,
                'limit': limit
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@trades_bp.route('/api/trades/summary', methods=['GET'])
def get_trade_summary():
    """Get trade summary statistics"""
    try:
        days = request.args.get('days', 7, type=int)
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get summary stats
        cursor.execute('''
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                MAX(pnl) as max_pnl,
                MIN(pnl) as min_pnl,
                SUM(total) as total_volume
            FROM trades
            WHERE created_at >= ?
        ''', (cutoff_date,))
        
        row = cursor.fetchone()
        conn.close()
        
        total_trades = row['total_trades'] or 0
        winning_trades = row['winning_trades'] or 0
        
        summary = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': row['losing_trades'] or 0,
            'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            'total_pnl': float(row['total_pnl']) if row['total_pnl'] else 0,
            'avg_pnl': float(row['avg_pnl']) if row['avg_pnl'] else 0,
            'max_pnl': float(row['max_pnl']) if row['max_pnl'] else 0,
            'min_pnl': float(row['min_pnl']) if row['min_pnl'] else 0,
            'total_volume': float(row['total_volume']) if row['total_volume'] else 0,
            'period_days': days
        }
        
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@trades_bp.route('/api/trades/by-symbol', methods=['GET'])
def get_trades_by_symbol():
    """Get trades grouped by symbol"""
    try:
        days = request.args.get('days', 7, type=int)
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                symbol,
                COUNT(*) as count,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                SUM(total) as volume
            FROM trades
            WHERE created_at >= ?
            GROUP BY symbol
            ORDER BY total_pnl DESC
        ''', (cutoff_date,))
        
        rows = cursor.fetchall()
        conn.close()
        
        by_symbol = []
        for row in rows:
            by_symbol.append({
                'symbol': row['symbol'],
                'count': row['count'],
                'total_pnl': float(row['total_pnl']) if row['total_pnl'] else 0,
                'avg_pnl': float(row['avg_pnl']) if row['avg_pnl'] else 0,
                'volume': float(row['volume']) if row['volume'] else 0
            })
        
        return jsonify({
            'by_symbol': by_symbol,
            'period_days': days
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
