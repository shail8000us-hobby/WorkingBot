"""
Utility Routes Blueprint

This module handles utility API routes for frontend logging and bot action tracking.

Routes:
- POST /api/frontend-error - Log frontend errors for debugging
- POST /api/performance-log - Log frontend performance metrics
- GET  /api/bot-actions/recent - Get recent bot actions
- GET  /api/bot-actions/next - Get next 3 predicted actions

Dependencies:
- action_stream (bot action tracking)
- datetime utilities
- JSON request handling

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import sys
import os
import logging
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from flask import Blueprint, jsonify, request

from config.loader import get_config

def get_config_value(yaml_path: str, env_var: str = None, default: any = None):
    """Get config value from YAML using dot notation"""
    try:
        cfg = get_config()
        # Navigate nested using dot notation
        value = cfg
        for key in yaml_path.split('.'):
            value = getattr(value, key)
        return value
    except (AttributeError, KeyError):
        return default

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Get BASE_DIR
BASE_DIR = Path(__file__).parent.parent.parent.parent

# Initialize logger
log = logging.getLogger(__name__)

# Create blueprint
utility_bp = Blueprint('utility', __name__)

# ============================================================================
# Action Stream Integration (for bot-actions/recent)
# ============================================================================

try:
    from bot.utils.action_stream import get_action_stream
    action_stream = get_action_stream()
    ACTION_STREAM_AVAILABLE = True
except ImportError:
    log.warning("Action stream not available - bot-actions endpoint will have limited functionality")
    ACTION_STREAM_AVAILABLE = False
    action_stream = None

# ============================================================================
# Route Handlers
# ============================================================================

@utility_bp.route('/api/frontend-error', methods=['POST'])
def log_frontend_error():
    """
    Log frontend errors for debugging
    
    Request Body:
        {
            "timestamp": "ISO timestamp",
            "error": "Error message",
            "stack": "Stack trace",
            "url": "Page URL"
        }
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/frontend-error
        Body: {"error": "TypeError: Cannot read property...", "url": "/dashboard"}
        Response: {"success": true, "message": "Error logged"}
    """
    try:
        error_data = request.get_json()
        
        if not error_data:
            return jsonify({
                'success': False,
                'message': 'No error data provided'
            }), 400
        
        timestamp = error_data.get('timestamp', datetime.now().isoformat())
        error_msg = error_data.get('error', 'Unknown error')
        stack = error_data.get('stack', '')
        url = error_data.get('url', '')
        
        # Log to console (could also log to file or error tracking service)
        print(f"🔴 FRONTEND ERROR [{timestamp}]")
        print(f"   URL: {url}")
        print(f"   Error: {error_msg}")
        if stack:
            print(f"   Stack: {stack}")
        
        # Could integrate with error tracking services here (Sentry, Rollbar, etc.)
        
        return jsonify({
            'success': True,
            'message': 'Error logged'
        }), 200
        
    except Exception as e:
        log.error(f"Failed to log frontend error: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to log error: {str(e)}'
        }), 500


@utility_bp.route('/api/performance-log', methods=['POST'])
def log_performance():
    """
    Log frontend performance metrics
    
    Request Body:
        {
            "operation": "Operation name",
            "duration": 123.45,  # milliseconds
            "metadata": {additional context}
        }
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/performance-log
        Body: {"operation": "dashboard_load", "duration": 245.5}
        Response: {"success": true, "message": "Performance logged"}
    """
    try:
        perf_data = request.get_json()
        
        if not perf_data:
            return jsonify({
                'success': False,
                'message': 'No performance data provided'
            }), 400
        
        operation = perf_data.get('operation', 'unknown')
        duration = perf_data.get('duration', 0)
        metadata = perf_data.get('metadata', {})
        
        # Log to console
        log_line = f"📊 PERFORMANCE: {operation} took {duration:.2f}ms"
        if metadata:
            log_line += f" (metadata: {metadata})"
        print(log_line)
        
        # Could integrate with monitoring services here (New Relic, Datadog, etc.)
        
        return jsonify({
            'success': True,
            'message': 'Performance logged'
        }), 200
        
    except Exception as e:
        log.error(f"Failed to log performance: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to log performance: {str(e)}'
        }), 500


@utility_bp.route('/api/bot-actions/recent', methods=['GET'])
def get_recent_bot_actions():
    """
    Get recent bot actions from action stream
    
    Query Parameters:
        limit (int): Maximum number of events to return (default: 100, max: 1000)
    
    Returns:
        JSON response with recent bot actions
    
    Example:
        GET /api/bot-actions/recent?limit=50
        Response: {
            "success": true,
            "events": [
                {"timestamp": "...", "action": "BUY", "details": {...}},
                ...
            ],
            "count": 50
        }
    """
    try:
        # Get limit from query params (default 100, max 1000)
        limit = request.args.get('limit', default=100, type=int)
        limit = min(limit, 1000)  # Cap at 1000 events to prevent memory issues
        
        if not ACTION_STREAM_AVAILABLE or not action_stream:
            return jsonify({
                'success': False,
                'error': 'Action stream not available',
                'events': [],
                'count': 0
            }), 503
        
        # Try to get events from memory first
        events = action_stream.get_recent_events(limit=limit)
        
        # If memory is empty, try to load from file
        if not events:
            try:
                events = action_stream.load_events_from_file(limit=limit)
            except Exception as file_err:
                log.warning(f"Could not load events from file: {file_err}")
                events = []
        
        return jsonify({
            'success': True,
            'events': events,
            'count': len(events)
        }), 200
        
    except Exception as e:
        log.error(f"Failed to fetch bot actions: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'events': [],
            'count': 0
        }), 500


# ============================================================================
# News API Routes
# ============================================================================

@utility_bp.route('/api/news/feed', methods=['GET'])
def get_news_feed():
    """Get market news feed"""
    try:
        from bot.news.aggregator import get_news_aggregator
        
        # Get parameters
        limit = request.args.get('limit', 10, type=int)
        priority = request.args.get('priority', 'all')  # all, critical, high, medium, low
        
        aggregator = get_news_aggregator()
        news = aggregator.get_news(limit=limit, priority=priority)
        
        return jsonify({
            'success': True,
            'news': news,
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        log.error(f"Error getting news feed: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'news': []
        }), 500


@utility_bp.route('/api/news/refresh', methods=['POST'])
def refresh_news():
    """Manually refresh news feed"""
    try:
        from bot.news.aggregator import get_news_aggregator
        
        aggregator = get_news_aggregator()
        aggregator.refresh()
        
        return jsonify({
            'success': True,
            'message': 'News feed refreshed'
        }), 200
    except Exception as e:
        log.error(f"Error refreshing news: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@utility_bp.route('/api/utility/check-log', methods=['GET'])
def check_log():
    """
    Check if bot is waiting for runtime confirmation after config change
    
    Returns:
        JSON response with startup_hold status and confirmation file hint
    
    Example:
        GET /api/utility/check-log
        Response: {
            "startup_hold": false,
            "confirm_file_hint": null
        }
    """
    try:
        import os
        import re
        
        log_file = BASE_DIR / 'bot' / 'logs' / 'bot.log'
        startup_hold = False
        confirm_file_hint = None
        
        if log_file.exists():
            with log_file.open('rb') as f:
                try:
                    f.seek(-8192, os.SEEK_END)
                except OSError:
                    f.seek(0)
                tail = f.read().decode(errors='ignore')
            
            config_change = 'CONFIG CHANGE REQUIRES CONFIRMATION' in tail
            waiting = 'Waiting for confirmation' in tail
            
            if config_change or waiting:
                startup_hold = True
                m = re.search(r"touch\s+\.(confirm_[a-f0-9]+)", tail)
                if m:
                    confirm_file_hint = m.group(1)
        
        return jsonify({
            'startup_hold': startup_hold,
            'confirm_file_hint': confirm_file_hint
        }), 200
        
    except Exception as e:
        log.error(f"Error checking log: {e}")
        return jsonify({
            'startup_hold': False,
            'confirm_file_hint': None
        }), 200  # Return 200 with default values instead of error


@utility_bp.route('/api/debug/log_check', methods=['GET'])
def debug_log_check():
    """Debug endpoint to check log reading"""
    try:
        import os
        import re
        
        log_file = BASE_DIR / 'bot' / 'logs' / 'bot.log'
        startup_hold = False
        confirm_file_hint = None
        
        if log_file.exists():
            with log_file.open('rb') as f:
                try:
                    f.seek(-8192, os.SEEK_END)
                except OSError:
                    f.seek(0)
                tail = f.read().decode(errors='ignore')
            
            config_change = 'CONFIG CHANGE REQUIRES CONFIRMATION' in tail
            waiting = 'Waiting for confirmation' in tail
            
            if config_change or waiting:
                startup_hold = True
                m = re.search(r"touch\s+\.(confirm_[a-f0-9]+)", tail)
                if m:
                    confirm_file_hint = f".{m.group(1)}"
            
            return jsonify({
                'success': True,
                'log_file_exists': log_file.exists(),
                'log_file_path': str(log_file.absolute()),
                'config_change_found': config_change,
                'waiting_found': waiting,
                'startup_hold': startup_hold,
                'confirm_file_hint': confirm_file_hint,
                'tail_length': len(tail),
                'tail_preview': tail[-500:] if len(tail) > 500 else tail
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Log file not found',
                'log_file_path': str(log_file.absolute())
            }), 404
    except Exception as e:
        log.error(f"Error checking log: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@utility_bp.route('/api/bot-actions/next', methods=['GET'])
def get_next_bot_actions():
    """
    Get next 3 predicted actions the bot will take based on current market state
    
    Returns intelligent predictions based on:
    - Current price vs grid range
    - Volatility regime (IV/RV)
    - Open positions
    - Pending orders
    - Market conditions
    
    Returns:
        JSON response with next 3 likely actions
    
    Example:
        GET /api/bot-actions/next
        Response: {
            "success": true,
            "actions": [
                {
                    "priority": 1,
                    "action": "WAIT",
                    "reason": "High volatility - IV at 52%",
                    "condition": "When IV drops below 40%",
                    "next_step": "Place BUY order at $108,000"
                },
                ...
            ]
        }
    """
    try:
        from bot.api.delta_client import DeltaClient
        
        # Get current market data
        client = DeltaClient()
        
        # Get config
        grid_lower = float(get_config_value('grid.lower', 'GRIDBOT_GRID_LOWER', 105000))
        grid_upper = float(get_config_value('grid.upper', 'GRIDBOT_GRID_UPPER', 120000))
        grid_step = float(get_config_value('grid.step', 'GRIDBOT_GRID_STEP', 1000))
        max_positions = int(get_config_value('grid.max_positions', 'GRIDBOT_MAX_POSITIONS', 3))
        
        # Get current positions (only count BTCUSD futures for grid bot)
        try:
            positions_response = client._req('GET', '/v2/positions/margined')
            # Only count BTCUSD (product_id 27) positions for the grid bot
            btcusd_positions = [
                p for p in positions_response.get('result', []) 
                if p.get('size', 0) != 0 and p.get('product_id') == 27
            ]
            open_positions = len(btcusd_positions) if positions_response.get('success') else 0
        except:
            open_positions = 0
        
        # Get current price
        try:
            ticker_response = client._req('GET', '/v2/tickers/BTCUSD')
            current_price = float(ticker_response['result']['mark_price']) if ticker_response.get('success') else 0
        except:
            current_price = 0
        
        # Get volatility data
        try:
            from bot.volatility.delta_volatility_collector import get_collector
            # v6.0: Multi-symbol support
            symbol = request.args.get('symbol', 'BTCUSD')
            collector = get_collector(symbol=symbol)
            latest = collector.get_latest_volatility()
            iv = latest.get('iv', {}).get('value', 0)
            rv = latest.get('rv', {}).get('1d', {}).get('value', 0)
        except:
            iv, rv = 0, 0
        
        # Determine next actions based on conditions
        actions = []
        
        # Action 1: Volatility check
        if iv > 40 or rv > 45:
            actions.append({
                'priority': 1,
                'action': '⏸️ WAIT (Volatility Halt)',
                'reason': f'High volatility detected - IV: {iv:.1f}%, RV: {rv:.1f}%',
                'condition': 'Waiting for IV < 40% AND RV < 45%',
                'next_step': f'Resume trading when volatility normalizes',
                'eta': '5-30 minutes (monitoring every 10s)',
                'importance': 'high'
            })
        elif current_price < grid_lower:
            actions.append({
                'priority': 1,
                'action': '⬆️ WAIT FOR PRICE TO RISE',
                'reason': f'Price ${current_price:,.0f} below grid range ${grid_lower:,.0f}-${grid_upper:,.0f}',
                'condition': f'Waiting for price to enter grid (above ${grid_lower:,.0f})',
                'next_step': f'Place first BUY order at ${grid_lower:,.0f}',
                'eta': 'When price rises to grid range',
                'importance': 'normal'
            })
        elif current_price > grid_upper:
            actions.append({
                'priority': 1,
                'action': '⬇️ WAIT FOR PRICE TO DROP',
                'reason': f'Price ${current_price:,.0f} above grid range ${grid_lower:,.0f}-${grid_upper:,.0f}',
                'condition': f'Waiting for price to enter grid (below ${grid_upper:,.0f})',
                'next_step': f'Place first BUY order at nearest grid level',
                'eta': 'When price drops into grid range',
                'importance': 'normal'
            })
        elif open_positions >= max_positions:
            actions.append({
                'priority': 1,
                'action': '🛑 MAX POSITIONS REACHED',
                'reason': f'Already holding {open_positions}/{max_positions} positions',
                'condition': 'Waiting for a position to close (TP hit)',
                'next_step': 'Resume buying when position count drops',
                'eta': 'When TP order fills',
                'importance': 'normal'
            })
        else:
            # Calculate next grid level
            next_grid_level = int((current_price // grid_step) * grid_step)
            actions.append({
                'priority': 1,
                'action': '💰 PLACE BUY ORDER',
                'reason': f'Conditions good - price in grid, volatility OK, {open_positions}/{max_positions} positions',
                'condition': 'All systems green',
                'next_step': f'Place limit BUY order at ${next_grid_level:,.0f}',
                'eta': 'Immediate (next loop iteration)',
                'importance': 'high'
            })
        
        # Action 2: Position management
        if open_positions > 0:
            tp_price = current_price + grid_step
            actions.append({
                'priority': 2,
                'action': '🎯 MONITOR TAKE-PROFIT ORDERS',
                'reason': f'{open_positions} open position(s) have TP orders active',
                'condition': f'Waiting for price to reach TP levels',
                'next_step': f'Close positions at ${tp_price:,.0f}+ levels for profit',
                'eta': 'Automatic when price rises',
                'importance': 'normal'
            })
        else:
            actions.append({
                'priority': 2,
                'action': '📊 ACCUMULATION MODE',
                'reason': 'No open positions yet',
                'condition': 'Ready to start grid strategy',
                'next_step': 'Buy first position at current grid level',
                'eta': 'When action #1 completes',
                'importance': 'normal'
            })
        
        # Action 3: Risk management
        actions.append({
            'priority': 3,
            'action': '🛡️ CONTINUOUS MONITORING',
            'reason': 'Safety systems active',
            'condition': 'Always running in background',
            'next_step': 'Monitor margin (11.2%), liquidation distance (75%), volatility',
            'eta': 'Every 10 seconds',
            'importance': 'critical'
        })
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'market_state': {
                'current_price': f'${current_price:,.0f}',
                'grid_range': f'${grid_lower:,.0f} - ${grid_upper:,.0f}',
                'open_positions': f'{open_positions}/{max_positions}',
                'iv': f'{iv:.1f}%',
                'rv': f'{rv:.1f}%',
                'status': 'HALTED' if (iv > 40 or rv > 45) else 'ACTIVE'
            },
            'actions': actions[:3],  # Return top 3 actions
            'count': len(actions[:3])
        }), 200
        
    except Exception as e:
        log.error(f"Error generating next actions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'actions': []
        }), 500


# ============================================================================
# Blueprint Configuration
# ============================================================================

def init_utility_routes(app):
    """
    Initialize utility routes with app-specific configuration
    
    Args:
        app: Flask application instance
    """
    # Any blueprint-specific initialization can go here
    log.info("✅ Utility routes initialized")
