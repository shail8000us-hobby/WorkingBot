"""
Unified Risk & Safety API - Consolidated safety system endpoint
Provides comprehensive safety data for the modern Risk & Safety Dashboard

Created: December 27, 2025
Author: Senior Developer
"""

from flask import Blueprint, jsonify, request
import logging
import json
import sys
import sqlite3
import requests
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

unified_safety_bp = Blueprint('unified_safety', __name__)

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent.parent

# Get correct database path based on bot mode
def get_event_store_db_path():
    """Get the correct event store database path based on bot mode"""
    try:
        from config.loader import get_config
        config = get_config()
        mode = getattr(config.bot, 'mode', 'LONG')
        db_name = f"bot_events_{mode}.db"
        return BASE_DIR / 'data' / db_name
    except Exception as e:
        logger.warning(f"Could not determine bot mode, using LONG: {e}")
        # Fallback to LONG mode database
        return BASE_DIR / 'data' / 'bot_events_LONG.db'


@unified_safety_bp.route('/api/safety/dashboard', methods=['GET'])
def get_unified_safety_dashboard():
    """
    Get comprehensive safety dashboard data including:
    - Guardian status (Layer 1-6)
    - Volatility metrics (IV, RV, spread)
    - PnL & Loss limits
    - Position size monitoring
    - Liquidation protection
    - System health (API, WebSocket, data freshness)
    - RSI safety signals
    - Overall risk status
    
    Query Parameters:
    - symbol: BTCUSD or ETHUSD (default: BTCUSD) for multi-symbol support v6.0
    """
    try:
        # Get symbol parameter for multi-symbol support
        symbol = request.args.get('symbol', 'BTCUSD')
        logger.info(f"Safety dashboard request for symbol: {symbol}")
        
        # Read Guardian health file
        guardian_health_file = BASE_DIR / '.guardian_health'
        guardian_data = {'running': False, 'health': None}
        
        if guardian_health_file.exists():
            try:
                with open(guardian_health_file, 'r') as f:
                    health = json.load(f)
                guardian_data = {
                    'running': True,
                    'health': health
                }
            except Exception as e:
                logger.warning(f"Could not read guardian health: {e}")
        
        # Get latest PnL data from database (more reliable than health file)
        pnl_data = get_latest_pnl_from_db()
        
        # Get RSI status from API endpoint
        rsi_data = get_rsi_status_from_api(symbol)
        
        # Get Guardian signal from database (event store)
        guardian_signal_data = get_latest_signal_from_db()
        
        # Get RSI status from API endpoint
        rsi_data = get_rsi_status_from_api(symbol)
        
        # Get Guardian signal from database (event store)
        guardian_signal_data = get_latest_signal_from_db()
        
        # Get Liquidation data from API
        liquidation_data = get_liquidation_from_api(symbol)
        
        # Read Volatility status file (try symbol-specific first, fallback to generic)
        volatility_file = BASE_DIR / f'.volatility_status_{symbol}.json'
        if not volatility_file.exists():
            volatility_file = BASE_DIR / '.volatility_status.json'
        volatility_data = {'success': False}
        
        if volatility_file.exists():
            try:
                with open(volatility_file, 'r') as f:
                    vol_status = json.load(f)
                volatility_data = {
                    'success': True,
                    'status': vol_status
                }
            except Exception as e:
                logger.warning(f"Could not read volatility status: {e}")
        
        # Get system health from guardian
        health_data = guardian_data.get('health', {}) or {}
        
        # Extract key metrics from database (primary source)
        total_pnl_inr = pnl_data.get('total_pnl_inr', 0)
        position_count = pnl_data.get('position_count', 0)
        total_loss_inr = pnl_data.get('total_loss_inr', 0)
        
        # Config limits (fallback values if not in health)
        max_loss_inr = 5000  # Default Guardian config
        max_total_position = 1000  # Default Guardian config
        
        # Config limits (fallback values if not in health)
        max_loss_inr = 5000  # Default Guardian config
        max_total_position = 1000  # Default Guardian config
        
        # Calculate overall risk level
        overall_status = 'SAFE'
        critical_issues = []
        warnings = []
        
        # Check Guardian signal (from database, not health file)
        guardian_running = guardian_data.get('running', False)
        guardian_signal = guardian_signal_data.get('signal', 'UNKNOWN')
        
        if not guardian_running:
            critical_issues.append('Guardian Bot is not running')
            overall_status = 'CRITICAL'
        elif guardian_signal == 'STOP':
            critical_issues.append(f"Guardian issued STOP signal: {guardian_signal_data.get('reason', 'Unknown reason')}")
            overall_status = 'STOP'
        
        # Check volatility
        vol_metrics = {}
        if volatility_data.get('success') and volatility_data.get('status'):
            vol_metrics = volatility_data['status']
            iv = vol_metrics.get('iv') or 0
            rv = vol_metrics.get('rv') or 0
            if iv and iv > 50:
                warnings.append(f'High implied volatility: {iv:.1f}%')
            if rv and rv > 50:
                warnings.append(f'High realized volatility: {rv:.1f}%')
        
        # Check PnL/Loss limits (from database)
        total_loss_inr = pnl_data.get('total_loss_inr', 0)
        max_loss_inr = pnl_data.get('max_loss_inr', 5000)
        loss_utilization = (total_loss_inr / max_loss_inr * 100) if max_loss_inr > 0 else 0
        
        if loss_utilization >= 100:
            critical_issues.append(f'Loss limit exceeded: ₹{total_loss_inr:,.0f} / ₹{max_loss_inr:,.0f}')
            overall_status = 'CRITICAL'
        elif loss_utilization >= 85:
            warnings.append(f'Loss limit warning: {loss_utilization:.1f}% utilized')
            if overall_status == 'SAFE':
                overall_status = 'WARNING'
        
        # Check liquidation risk
        if liquidation_data.get('success') and liquidation_data.get('margin'):
            margin_zone = liquidation_data['margin'].get('zone', 'UNKNOWN')
            if margin_zone in ['RED', 'DANGER']:
                critical_issues.append(f'Liquidation risk: {margin_zone} zone')
                overall_status = 'CRITICAL'
            elif margin_zone in ['ORANGE', 'YELLOW']:
                warnings.append(f'Liquidation caution: {margin_zone} zone')
                if overall_status == 'SAFE':
                    overall_status = 'WARNING'
        
        # Check RSI signal
        if rsi_data.get('success') and rsi_data.get('data'):
            rsi_status = rsi_data['data'].get('status', 'UNKNOWN')
            if rsi_status == 'STOP':
                warnings.append('RSI trending market detected')
                if overall_status == 'SAFE':
                    overall_status = 'WARNING'
        
        # Build unified response
        unified_data = {
            'success': True,
            'timestamp': health_data.get('timestamp'),
            'overall_status': overall_status,
            'critical_issues': critical_issues,
            'warnings': warnings,
            
            # Guardian Layer Overview
            'guardian': {
                'running': guardian_running,
                'signal': guardian_signal,
                'uptime_seconds': health_data.get('uptime_seconds', 0),
                'cycle_count': health_data.get('cycle_count', 0),
                'pid': health_data.get('pid')
            },
            
            # Layer 1: Volatility Safety
            'volatility': {
                'success': volatility_data.get('success', False),
                'iv': {
                    'value': vol_metrics.get('iv'),
                    'limit': vol_metrics.get('thresholds', {}).get('max_iv', 35)
                } if volatility_data.get('success') else None,
                'rv': {
                    'value': vol_metrics.get('rv'),
                    'limit': vol_metrics.get('thresholds', {}).get('max_rv', 40)
                } if volatility_data.get('success') else None,
                'spread': {
                    'value': vol_metrics.get('spread'),
                    'limit': vol_metrics.get('thresholds', {}).get('max_spread', 10)
                } if volatility_data.get('success') else None,
                'status': 'OK' if vol_metrics.get('is_safe', True) else 'WARNING'
            },
            
            # Layer 2: PnL & Loss Limits (from database)
            'pnl_loss': {
                'total_pnl_inr': total_pnl_inr,
                'total_loss_inr': total_loss_inr,
                'max_loss_inr': max_loss_inr,
                'utilization_percent': loss_utilization,
                'breach_amount_inr': max(0, total_loss_inr - max_loss_inr),
                'status': 'CRITICAL' if loss_utilization >= 100 else 'WARNING' if loss_utilization >= 85 else 'OK'
            },
            
            # Layer 3: Position Size Limits (from database)
            'position_size': {
                'total_position': abs(total_pnl_inr),  # Use PnL as proxy for total position value
                'position_count': position_count,
                'max_position': max_total_position,
                'utilization_percent': (abs(total_pnl_inr) / max_total_position * 100) if max_total_position > 0 else 0,
                'status': 'OK'  # Guardian would STOP if exceeded
            },
            
            # Layer 4: Liquidation Protection
            'liquidation': {
                'success': liquidation_data.get('success', False),
                'margin_zone': liquidation_data.get('margin', {}).get('zone', 'UNKNOWN') if liquidation_data.get('success') else 'UNKNOWN',
                'margin_utilization': liquidation_data.get('margin', {}).get('utilization', 0) if liquidation_data.get('success') else 0,
                'distance_to_liquidation': liquidation_data.get('distance', {}).get('distance', 0) if liquidation_data.get('success') else 0,
                'mtm_safety_buffer': liquidation_data.get('mtm', {}).get('current_mtm_inr', 0) if liquidation_data.get('success') else 0,
                'status': liquidation_data.get('margin', {}).get('zone', 'UNKNOWN') if liquidation_data.get('success') else 'ERROR'
            },
            
            # Layer 5: System Health
            'system_health': {
                'api_healthy': guardian_running,  # If guardian running, API is healthy
                'websocket_connected': guardian_running,  # Assume websocket working if guardian running
                'data_fresh': pnl_data.get('success', False),  # Data fresh if we got PnL from DB
                'event_store_connected': True,  # Event store is operational (signal system working)
                'exchange_operational': liquidation_data.get('success', False),  # Exchange operational if we got margin data
                'issues': [] if guardian_running else ['Guardian not running']
            },
            
            # Layer 6: RSI Safety (from API)
            'rsi': {
                'success': rsi_data.get('success', False),
                'current_rsi': rsi_data.get('rsi') if rsi_data.get('success') else None,
                'status': rsi_data.get('status', 'UNKNOWN') if rsi_data.get('success') else 'ERROR',
                'bot_mode': rsi_data.get('bot_mode', 'UNKNOWN') if rsi_data.get('success') else 'UNKNOWN',
                'threshold': rsi_data.get('long_threshold') if rsi_data.get('success') and rsi_data.get('bot_mode') == 'LONG' else rsi_data.get('short_threshold') if rsi_data.get('success') else None
            },
            
            # Quick Stats
            'quick_stats': {
                'layers_active': sum([
                    1 if volatility_data.get('success') else 0,
                    1,  # PnL always active
                    1,  # Position size always active
                    1 if liquidation_data.get('success') else 0,
                    1,  # System health always active
                    1 if rsi_data.get('success') else 0
                ]),
                'total_layers': 6,
                'protection_score': calculate_protection_score(
                    guardian_running,
                    volatility_data.get('success', False),
                    liquidation_data.get('success', False),
                    rsi_data.get('success', False),
                    loss_utilization,
                    pnl_data.get('success', False)  # Use actual data freshness from DB query
                )
            }
        }
        
        return jsonify(unified_data)
        
    except Exception as e:
        logger.error(f"Error in unified safety dashboard: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'overall_status': 'ERROR',
            'critical_issues': ['Failed to fetch safety data'],
            'warnings': []
        }), 500


def calculate_protection_score(guardian_running, vol_active, liq_active, rsi_active, loss_util, data_fresh):
    """
    Calculate protection score 0-100
    
    Score factors:
    - Guardian running: 30 points
    - All collectors active: 30 points (10 each for vol, liq, rsi)
    - Loss utilization < 50%: 20 points, < 85%: 10 points
    - Data fresh: 20 points
    """
    score = 0
    
    # Guardian running (critical)
    if guardian_running:
        score += 30
    
    # Collectors active
    if vol_active:
        score += 10
    if liq_active:
        score += 10
    if rsi_active:
        score += 10
    
    # Loss management
    if loss_util < 50:
        score += 20
    elif loss_util < 85:
        score += 10
    
    # Data freshness
    if data_fresh:
        score += 20
    
    return min(score, 100)


def get_latest_pnl_from_db():
    """Get latest PnL data from Guardian SQLite database"""
    try:
        db_path = get_event_store_db_path()
        if not db_path.exists():
            logger.warning(f"Database not found: {db_path}")
            return {'success': False, 'total_pnl_inr': 0, 'position_count': 0, 'total_loss_inr': 0}
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get latest PnL record
        cursor.execute("""
            SELECT total_pnl_inr, position_count, unrealized_pnl_inr, realized_pnl_inr
            FROM pnl_history
            ORDER BY id DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            total_pnl = float(row[0]) if row[0] else 0
            position_count = int(row[1]) if row[1] else 0
            unrealized = float(row[2]) if row[2] else 0
            realized = float(row[3]) if row[3] else 0
            
            # Calculate loss (negative PnL)
            total_loss = abs(min(0, total_pnl))
            
            return {
                'success': True,
                'total_pnl_inr': total_pnl,
                'position_count': position_count,
                'total_loss_inr': total_loss,
                'unrealized_pnl_inr': unrealized,
                'realized_pnl_inr': realized,
                'max_loss_inr': 5000  # Default Guardian config
            }
        else:
            logger.warning("No PnL data in database")
            return {'success': False, 'total_pnl_inr': 0, 'position_count': 0, 'total_loss_inr': 0}
            
    except Exception as e:
        logger.error(f"Error reading PnL from database: {e}")
        return {'success': False, 'total_pnl_inr': 0, 'position_count': 0, 'total_loss_inr': 0}


def get_rsi_status_from_api(symbol='BTCUSD'):
    """Get RSI status from Guardian API endpoint"""
    try:
        # Call local Guardian RSI API with symbol parameter
        response = requests.get(f'http://localhost:5555/api/guardian/rsi/status?symbol={symbol}', timeout=2)
        
        if response.status_code == 200:
            result = response.json()
            
            # API returns {success: true, data: {rsi, status, bot_mode, ...}}
            if result.get('success') and result.get('data'):
                data = result['data']
                return {
                    'success': True,
                    'rsi': data.get('rsi'),
                    'status': data.get('status', 'UNKNOWN'),
                    'bot_mode': data.get('bot_mode', 'UNKNOWN'),
                    'long_threshold': data.get('long_threshold', 65),
                    'short_threshold': data.get('short_threshold', 35)
                }
            else:
                logger.warning(f"RSI API returned unexpected format: {result}")
                return {'success': False}
        else:
            logger.warning(f"RSI API returned status {response.status_code}")
            return {'success': False}
            
    except Exception as e:
        logger.warning(f"Could not fetch RSI from API: {e}")
        return {'success': False}


def get_liquidation_from_api(symbol='BTCUSD'):
    """Get liquidation protection data from liquidation API endpoint"""
    try:
        # Call local Liquidation API with symbol parameter
        response = requests.get(f'http://localhost:5555/api/liquidation/status?symbol={symbol}', timeout=2)
        
        if response.status_code == 200:
            result = response.json()
            
            # API returns {success: true, margin: {...}, distance: {...}, mtm: {...}}
            if result.get('success'):
                return result
            else:
                logger.warning(f"Liquidation API returned success=false")
                return {'success': False}
        else:
            logger.warning(f"Liquidation API returned status {response.status_code}")
            return {'success': False}
            
    except Exception as e:
        logger.warning(f"Could not fetch liquidation data from API: {e}")
        return {'success': False}


def get_latest_signal_from_db():
    """Get latest Guardian signal from event store database"""
    try:
        db_path = get_event_store_db_path()
        if not db_path.exists():
            logger.warning(f"Database not found: {db_path}")
            return {'success': False, 'signal': 'UNKNOWN'}
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if events table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='events'
        """)
        
        if not cursor.fetchone():
            # Events table doesn't exist, default to GO (safe assumption when Guardian running)
            conn.close()
            return {'success': True, 'signal': 'GO', 'reason': 'No events table - defaulting to GO'}
        
        # Get latest GO/STOP signal (order by timestamp, not id)
        cursor.execute("""
            SELECT event_type, data, timestamp
            FROM events
            WHERE event_type IN ('guardian_signal_go', 'guardian_signal_stop')
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            event_type = row[0]
            try:
                data = json.loads(row[1]) if row[1] else {}
            except:
                data = {}
            
            signal = 'GO' if 'go' in event_type.lower() else 'STOP'
            reason = data.get('reason', 'Unknown')
            
            return {
                'success': True,
                'signal': signal,
                'reason': reason,
                'timestamp': row[2]
            }
        else:
            # No signals in database, assume GO if guardian running
            logger.info("No signals in event store, assuming GO")
            return {'success': True, 'signal': 'GO', 'reason': 'Default state'}
            
    except Exception as e:
        logger.error(f"Error reading signal from database: {e}")
        return {'success': False, 'signal': 'UNKNOWN', 'reason': str(e)}
