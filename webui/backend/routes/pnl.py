"""
PnL Routes Blueprint

This module handles all API routes related to Profit & Loss history and tracking.

Routes:
- GET /api/pnl-history - Get PnL history from CSV files
- GET /api/pnl-history/hourly - Get hourly PnL history (sampled at hourly intervals)

Dependencies:
- CSV file reading from bot/reports
- datetime for timestamp parsing

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path
from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

# Create blueprint
pnl_bp = Blueprint('pnl', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
PNL_HISTORY_DIR = BASE_DIR / "bot" / "reports"

# ============================================================================
# Route Handlers
# ============================================================================

@pnl_bp.route('/api/pnl-history', methods=['GET'])
def get_pnl_history():
    """
    Get PnL history from CSV files
    
    Returns the last 120 entries (2 hours if checking every minute) from
    today's PnL history CSV file.
    
    v6.0: Supports per-instance PnL history
    Query params:
        instance: Optional instance name (e.g., BTCUSD_LONG)
    
    Returns:
        JSON response with PnL history
    
    Example:
        GET /api/pnl-history?instance=BTCUSD_LONG
        Response: {
            "history": [
                {
                    "timestamp": "2025-10-31T14:30:00",
                    "time": "14:30:00",
                    "total_pnl": 1234.56,
                    "unrealized_pnl": 1234.56,
                    "pnl": 1234.56,
                    "position_count": 5
                },
                ...
            ]
        }
    """
    try:
        # v6.0: Extract instance parameter
        instance = request.args.get('instance')
        
        # Get today's CSV file
        today = datetime.now().strftime("%Y%m%d")
        
        if instance:
            # Per-instance PnL history
            csv_file = PNL_HISTORY_DIR / f"pnl_history_{instance}_{today}.csv"
        else:
            # Global PnL history (legacy)
            csv_file = PNL_HISTORY_DIR / f"pnl_history_{today}.csv"
        
        history = []
        if csv_file.exists():
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert string values to numbers
                    history.append({
                        'timestamp': row.get('timestamp', ''),
                        'time': row.get('time', ''),
                        'total_pnl': float(row.get('total_pnl', 0)),
                        'unrealized_pnl': float(row.get('unrealized_pnl', 0)),
                        'pnl': float(row.get('unrealized_pnl', 0)),  # Alias for frontend
                        'position_count': int(row.get('position_count', 0))
                    })
        
        # Return last 120 entries (2 hours if checking every minute)
        return jsonify({'history': history[-120:], 'instance': instance}), 200
        
    except Exception as e:
        log.error(f"Error fetching PnL history: {e}")
        return jsonify({'error': str(e)}), 500


@pnl_bp.route('/api/pnl-history/hourly', methods=['GET'])
def get_hourly_pnl_history():
    """
    Get hourly PnL history for the last 24 hours from SQL database
    
    Guardian bot stores PnL data to SQL database every 10 seconds.
    This endpoint samples at hourly intervals for the WebUI chart.
    
    v6.0: Supports per-instance PnL history
    Query params:
        instance: Optional instance name (e.g., BTCUSD_LONG)
    
    Returns:
        JSON response with hourly PnL history
    
    Example:
        GET /api/pnl-history/hourly
        Response: {
            "history": [
                {
                    "timestamp": "2025-11-17T10:00:00",
                    "time": "10:00",
                    "total_pnl": 1000.0,
                    "position_count": 5
                },
                ...
            ]
        }
    """
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = BASE_DIR / 'bot' / 'state' / 'events.db'
        
        if not db_path.exists():
            log.warning(f"SQL database not found: {db_path}")
            return jsonify({'history': [], 'meta': {'guardian_running': False}}), 200
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(hours=24)
        cutoff_str = cutoff_time.isoformat()
        
        cursor.execute('''
            SELECT 
                strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
                AVG(total_pnl_inr) as avg_pnl,
                AVG(position_count) as avg_positions,
                MAX(timestamp) as latest_timestamp
            FROM pnl_history
            WHERE timestamp >= ?
            GROUP BY hour
            ORDER BY hour ASC
        ''', (cutoff_str,))
        
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            hour_str, avg_pnl, avg_positions, latest_timestamp = row
            dt = datetime.fromisoformat(hour_str)
            
            history.append({
                'timestamp': latest_timestamp,
                'time': dt.strftime('%H:%M'),
                'total_pnl': round(avg_pnl, 2),
                'position_count': int(avg_positions)
            })
        
        if len(history) == 0:
            cursor.execute('''
                SELECT 
                    strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
                    AVG(total_pnl_inr) as avg_pnl,
                    AVG(position_count) as avg_positions,
                    MAX(timestamp) as latest_timestamp
                FROM pnl_history
                GROUP BY hour
                ORDER BY timestamp DESC
                LIMIT 24
            ''')
            
            fallback_rows = cursor.fetchall()
            for row in fallback_rows:
                hour_str, avg_pnl, avg_positions, latest_timestamp = row
                dt = datetime.fromisoformat(hour_str)
                
                history.append({
                    'timestamp': latest_timestamp,
                    'time': dt.strftime('%H:%M'),
                    'total_pnl': round(avg_pnl, 2),
                    'position_count': int(avg_positions)
                })
            
            history.reverse()
        
        cursor.execute('SELECT MAX(timestamp) FROM pnl_history')
        last_update = cursor.fetchone()[0]
        
        conn.close()
        
        meta = {
            'last_update': last_update,
            'data_points': len(history),
            'guardian_running': True if last_update and 
                (datetime.now() - datetime.fromisoformat(last_update)).total_seconds() < 300 else False
        }
        
        log.debug(f"Fetched {len(history)} hourly PnL records from SQL (last update: {last_update})")
        return jsonify({'history': history, 'meta': meta}), 200
        
    except Exception as e:
        log.error(f"Error fetching PnL history from SQL: {e}")
        # Fallback to empty history
        return jsonify({'history': []}), 200


@pnl_bp.route('/api/pnl/summary', methods=['GET'])
def get_pnl_summary():
    """
    Get current PnL summary
    
    Returns the latest PnL values from today's CSV file, including:
    - Total PnL (USD)
    - Total PnL (INR)
    - Daily PnL percentage
    - Last update timestamp
    
    v6.0: Supports per-instance PnL summary
    Query params:
        instance: Optional instance name (e.g., BTCUSD_LONG)
    
    Returns:
        JSON response with PnL summary
    
    Example:
        GET /api/pnl/summary?instance=BTCUSD_LONG
        Response: {
            "total_pnl_usd": 123.45,
            "total_pnl_inr": 10272.34,
            "daily_pnl_percent": 2.34,
            "last_updated": "2025-11-12T12:30:45Z"
        }
    """
    try:
        # v6.0: Extract instance parameter
        instance = request.args.get('instance')
        
        # Get today's CSV file
        today = datetime.now().strftime("%Y%m%d")
        
        if instance:
            # Per-instance PnL summary
            csv_file = PNL_HISTORY_DIR / f"pnl_history_{instance}_{today}.csv"
        else:
            # Global PnL summary (legacy)
            csv_file = PNL_HISTORY_DIR / f"pnl_history_{today}.csv"
        
        if not csv_file.exists():
            # Return zeros if no data yet
            return jsonify({
                'total_pnl_usd': 0,
                'total_pnl_inr': 0,
                'daily_pnl_percent': 0,
                'last_updated': None
            }), 200
        
        # Read last line (most recent entry)
        latest_entry = None
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                latest_entry = row
        
        if not latest_entry:
            return jsonify({
                'total_pnl_usd': 0,
                'total_pnl_inr': 0,
                'daily_pnl_percent': 0,
                'last_updated': None
            }), 200
        
        # Parse the data
        total_pnl_usd = float(latest_entry.get('Total PnL (USD)', 0))
        total_pnl_inr = float(latest_entry.get('Total PnL (INR)', 0))
        
        # Calculate daily PnL percentage (estimate)
        # Assuming we started with some base capital, calculate % change
        # For now, just return 0 or calculate based on available data
        daily_pnl_percent = 0
        if 'Daily PnL %' in latest_entry:
            try:
                daily_pnl_percent = float(latest_entry['Daily PnL %'])
            except (ValueError, TypeError):
                pass
        
        timestamp = latest_entry.get('Timestamp', datetime.now().isoformat())
        
        return jsonify({
            'total_pnl_usd': total_pnl_usd,
            'total_pnl_inr': total_pnl_inr,
            'daily_pnl_percent': daily_pnl_percent,
            'last_updated': timestamp
        }), 200
        
    except Exception as e:
        log.error(f"Error fetching PnL summary: {e}")
        return jsonify({
            'total_pnl_usd': 0,
            'total_pnl_inr': 0,
            'daily_pnl_percent': 0,
            'last_updated': None,
            'error': str(e)
        }), 200  # Return 200 with zeros instead of 500 to prevent circuit breaker trips
