"""
Backtest Web UI - Flask Backend

Dedicated backend for backtesting interface on port 5556.
Completely separate from live trading bot UI.
"""

import os
import sys
import json
import logging
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backtest.runner.grid_backtester import GridBacktester
from backtest.data.cache import get_cache_stats, clear_old_cache

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
log = logging.getLogger("backtest_ui")

# Load environment
# Load configuration from YAML
from config.loader import get_config
cfg = get_config()

# Flask app - configure static folder
frontend_build_dir = str(Path(__file__).parent.parent / 'frontend' / 'build')
app = Flask(__name__, static_folder=frontend_build_dir, static_url_path='')
app.config['SECRET_KEY'] = 'backtest-secret-key-2025'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state
active_backtests = {}  # {backtest_id: {status, progress, result}}
backtest_counter = 0


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_next_backtest_id():
    """Generate unique backtest ID."""
    global backtest_counter
    backtest_counter += 1
    return f"BT{backtest_counter:04d}"


def parse_datetime(date_str: str) -> datetime:
    """Parse datetime string."""
    formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {date_str}")


def load_grid_config():
    """Load grid configuration from config.yaml."""
    config = {
        'symbol': os.getenv('GRIDBOT_SYMBOL', 'BTC/USD:USD'),
        'ref': float(os.getenv('GRIDBOT_REF', 112000)),
        'step': float(os.getenv('GRIDBOT_STEP', 100)),
        'lot': float(os.getenv('GRIDBOT_LOT', 1)),
        'max_open': int(os.getenv('GRIDBOT_MAX_OPEN', 10)),
        'lower': float(os.getenv('GRIDBOT_LOWER', 110000)),
        'upper': float(os.getenv('GRIDBOT_UPPER', 115000)),
        'tick_size': float(os.getenv('GRIDBOT_TICK_SIZE', 0.5))
    }
    return config


def get_backtest_results_dir():
    """Get backtests results directory."""
    return Path("reports/backtests")


def list_past_backtests():
    """List all past backtest results."""
    results_dir = get_backtest_results_dir()
    
    if not results_dir.exists():
        return []
    
    backtests = []
    
    for backtest_dir in results_dir.iterdir():
        if not backtest_dir.is_dir():
            continue
        
        # Look for summary.json
        summary_files = list(backtest_dir.glob("*_summary.json"))
        
        if not summary_files:
            continue
        
        summary_file = summary_files[0]
        
        try:
            with open(summary_file, 'r') as f:
                summary = json.load(f)
            
            backtests.append({
                'id': backtest_dir.name,
                'directory': str(backtest_dir),
                'summary': summary,
                'created': datetime.fromtimestamp(summary_file.stat().st_mtime).isoformat()
            })
        except Exception as e:
            log.warning(f"Could not load backtest {backtest_dir.name}: {e}")
    
    # Sort by creation time (newest first)
    backtests.sort(key=lambda x: x['created'], reverse=True)
    
    return backtests


# ============================================================================
# BACKGROUND BACKTEST RUNNER
# ============================================================================

def run_backtest_background(backtest_id, params):
    """Run backtest in background thread with progress updates."""
    try:
        log.info(f"Starting backtest {backtest_id}")
        
        # Update status
        active_backtests[backtest_id]['status'] = 'running'
        socketio.emit('backtest_status', {
            'backtest_id': backtest_id,
            'status': 'running',
            'progress': 0
        })
        
        # Parse dates
        start = parse_datetime(params['start'])
        end = parse_datetime(params['end'])
        
        # Load config
        config = load_grid_config()
        
        # Override with params
        if 'symbol' in params and params['symbol']:
            config['symbol'] = params['symbol']
        if 'ref' in params and params['ref']:
            config['ref'] = float(params['ref'])
        if 'step' in params and params['step']:
            config['step'] = float(params['step'])
        if 'lot' in params and params['lot']:
            config['lot'] = float(params['lot'])
        if 'max_open' in params and params['max_open']:
            config['max_open'] = int(params['max_open'])
        
        # Backtest settings
        config['assume_maker'] = params.get('assume_maker', True)
        config['funding_mode'] = params.get('funding_mode', 'off')
        config['same_bar_priority'] = params.get('same_bar_priority', 'tp_first')
        
        # Create backtester
        backtester = GridBacktester(
            symbol=config['symbol'],
            timeframe=params.get('timeframe', '1m'),
            start=start,
            end=end,
            config=config,
            is_testnet=params.get('is_testnet', False)
        )
        
        # Run backtest
        results = backtester.run()
        
        # Save results
        symbol_safe = config['symbol'].replace('/', '_').replace(':', '_')
        start_str = start.strftime('%Y%m%d')
        end_str = end.strftime('%Y%m%d')
        output_dir = get_backtest_results_dir() / f"{symbol_safe}_{start_str}_{end_str}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save files
        prefix = f"{symbol_safe}_{start_str}_{end_str}"
        
        if not results['trades_df'].empty:
            results['trades_df'].to_csv(output_dir / f"{prefix}_trades.csv", index=False)
        
        if not results['equity_df'].empty:
            results['equity_df'].to_csv(output_dir / f"{prefix}_equity.csv", index=False)
        
        # Save summary
        summary = {
            'symbol': results['symbol'],
            'timeframe': results['timeframe'],
            'start': results['start'].isoformat() if results['start'] else None,
            'end': results['end'].isoformat() if results['end'] else None,
            'metrics': _serialize_metrics(results['metrics']),
            'sim_summary': results['sim_summary'],
            'config': results['config']
        }
        
        with open(output_dir / f"{prefix}_summary.json", 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Update status
        active_backtests[backtest_id]['status'] = 'completed'
        active_backtests[backtest_id]['progress'] = 100
        active_backtests[backtest_id]['result'] = summary
        active_backtests[backtest_id]['output_dir'] = str(output_dir)
        
        socketio.emit('backtest_status', {
            'backtest_id': backtest_id,
            'status': 'completed',
            'progress': 100,
            'result': summary
        })
        
        log.info(f"Backtest {backtest_id} completed successfully")
        
    except Exception as e:
        log.error(f"Backtest {backtest_id} failed: {e}", exc_info=True)
        
        active_backtests[backtest_id]['status'] = 'failed'
        active_backtests[backtest_id]['error'] = str(e)
        
        socketio.emit('backtest_status', {
            'backtest_id': backtest_id,
            'status': 'failed',
            'error': str(e)
        })


def _serialize_metrics(metrics):
    """Convert metrics to JSON-serializable format."""
    serialized = {}
    for key, value in metrics.items():
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
        elif isinstance(value, (int, float, str, bool, type(None))):
            serialized[key] = value
        else:
            serialized[key] = str(value)
    return serialized


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'backtest_ui',
        'port': 5556,
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current grid configuration."""
    try:
        config = load_grid_config()
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/run', methods=['POST'])
def run_backtest():
    """Start a new backtest."""
    try:
        params = request.json
        
        # Validate required params
        if 'start' not in params or 'end' not in params:
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: start, end'
            }), 400
        
        # Generate backtest ID
        backtest_id = get_next_backtest_id()
        
        # Initialize tracking
        active_backtests[backtest_id] = {
            'status': 'queued',
            'progress': 0,
            'params': params,
            'created': datetime.utcnow().isoformat()
        }
        
        # Start background thread
        thread = threading.Thread(
            target=run_backtest_background,
            args=(backtest_id, params)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'backtest_id': backtest_id,
            'message': 'Backtest started'
        })
        
    except Exception as e:
        log.error(f"Failed to start backtest: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/<backtest_id>/status', methods=['GET'])
def get_backtest_status(backtest_id):
    """Get status of a running backtest."""
    if backtest_id not in active_backtests:
        return jsonify({
            'success': False,
            'error': 'Backtest not found'
        }), 404
    
    return jsonify({
        'success': True,
        'backtest': active_backtests[backtest_id]
    })


@app.route('/api/backtest/<backtest_id>/result', methods=['GET'])
def get_backtest_result(backtest_id):
    """Get result of a completed backtest."""
    if backtest_id not in active_backtests:
        return jsonify({
            'success': False,
            'error': 'Backtest not found'
        }), 404
    
    backtest = active_backtests[backtest_id]
    
    if backtest['status'] != 'completed':
        return jsonify({
            'success': False,
            'error': f"Backtest is {backtest['status']}"
        }), 400
    
    return jsonify({
        'success': True,
        'result': backtest.get('result', {})
    })


@app.route('/api/backtest/history', methods=['GET'])
def get_backtest_history():
    """Get list of all past backtests."""
    try:
        backtests = list_past_backtests()
        return jsonify({
            'success': True,
            'backtests': backtests,
            'count': len(backtests)
        })
    except Exception as e:
        log.error(f"Failed to load backtest history: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/history/<path:backtest_dir>', methods=['GET'])
def get_historical_backtest(backtest_dir):
    """Get details of a specific historical backtest."""
    try:
        results_dir = get_backtest_results_dir() / backtest_dir
        
        if not results_dir.exists():
            return jsonify({
                'success': False,
                'error': 'Backtest not found'
            }), 404
        
        # Load summary
        summary_files = list(results_dir.glob("*_summary.json"))
        if not summary_files:
            return jsonify({
                'success': False,
                'error': 'Summary file not found'
            }), 404
        
        with open(summary_files[0], 'r') as f:
            summary = json.load(f)
        
        # Load trades
        trades_files = list(results_dir.glob("*_trades.csv"))
        trades = []
        if trades_files:
            import pandas as pd
            trades_df = pd.read_csv(trades_files[0])
            trades = trades_df.to_dict('records')
        
        # Load equity
        equity_files = list(results_dir.glob("*_equity.csv"))
        equity = []
        if equity_files:
            import pandas as pd
            equity_df = pd.read_csv(equity_files[0])
            equity = equity_df.to_dict('records')
        
        return jsonify({
            'success': True,
            'summary': summary,
            'trades': trades,
            'equity': equity
        })
        
    except Exception as e:
        log.error(f"Failed to load historical backtest: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/cache/stats', methods=['GET'])
def get_cache_stats_endpoint():
    """Get cache statistics."""
    try:
        stats = get_cache_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/cache/clear', methods=['POST'])
def clear_cache_endpoint():
    """Clear old cache files."""
    try:
        days = request.json.get('days_old', 30)
        removed = clear_old_cache(days_old=days)
        return jsonify({
            'success': True,
            'removed': removed
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    log.info("Client connected to backtest UI")
    emit('connected', {'message': 'Connected to backtest server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    log.info("Client disconnected from backtest UI")


# ============================================================================
# SERVE REACT FRONTEND
# ============================================================================

@app.route('/')
def serve_index():
    """Serve React index.html."""
    return send_from_directory(frontend_build_dir, 'index.html')


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    log.info("=" * 70)
    log.info("GRIDBOT PRO - BACKTEST WEB UI")
    log.info("=" * 70)
    log.info(f"Starting server on http://localhost:5556")
    log.info("Press Ctrl+C to stop")
    log.info("=" * 70)
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=5556,
        debug=False,
        allow_unsafe_werkzeug=True
    )

