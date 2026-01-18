"""
Futures Max Loss Monitor - SEPARATE SAFETY MODULE

This is a STANDALONE safety module for per-position max loss monitoring.
Does NOT touch Guardian bot, existing risk controls, or trading logic.

Uses WebSocket for real-time position monitoring and automatic square-off.

Created: January 18, 2026
Purpose: Overnight protection - monitor positions and auto-close on max loss breach

⚠️ COMPLETE SEPARATION FROM EXISTING RISK SYSTEMS
"""

import sys
import time
import logging
import threading
import traceback
from pathlib import Path
from typing import Dict, Optional
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

log = logging.getLogger(__name__)

# Create blueprint
futures_max_loss_bp = Blueprint('futures_max_loss', __name__, url_prefix='/api/futures/max-loss')

# Global storage for max loss settings (per-position)
# Format: {product_id: {'max_loss': 100.0, 'enabled': True, 'symbol': 'BTCUSD'}}
_max_loss_settings: Dict[int, Dict] = {}

# Monitor thread
_monitor_thread: Optional[threading.Thread] = None
_monitor_running = False
_monitor_interval = 2.0  # Check every 2 seconds


def _get_delta_client():
    """Get Delta Exchange client instance"""
    try:
        from bot.api.delta_client import DeltaClient
        return DeltaClient()
    except Exception as e:
        log.error(f"Failed to initialize Delta client: {e}")
        return None


def _is_futures_position(product_symbol: str) -> bool:
    """Check if a product symbol is a futures position"""
    if not product_symbol:
        return False
    if '-C-' in product_symbol or '-P-' in product_symbol:
        return False
    futures_symbols = ['BTCUSD', 'ETHUSD', 'SOLUSD', 'BNBUSD', 'XRPUSD', 'DOGEUSD']
    return product_symbol in futures_symbols


def _monitor_loop():
    """
    Background thread that monitors positions for max loss breach.
    Runs independently, checking positions every 2 seconds.
    """
    global _monitor_running
    
    log.info("🔍 Max Loss Monitor: Started")
    
    while _monitor_running:
        try:
            # Skip if no active max loss settings
            if not _max_loss_settings:
                time.sleep(_monitor_interval)
                continue
            
            delta_client = _get_delta_client()
            if not delta_client:
                time.sleep(_monitor_interval)
                continue
            
            # Fetch current positions
            positions_response = delta_client._req('GET', '/v2/positions/margined')
            
            if not positions_response.get('success'):
                log.warning("Max Loss Monitor: Failed to fetch positions")
                time.sleep(_monitor_interval)
                continue
            
            all_positions = positions_response.get('result', [])
            
            # Check each position with max loss enabled
            for product_id, settings in list(_max_loss_settings.items()):
                if not settings.get('enabled', False):
                    continue
                
                max_loss_threshold = settings.get('max_loss', 0)
                if max_loss_threshold <= 0:
                    continue
                
                # Find matching position
                position = None
                for pos in all_positions:
                    if pos.get('product_id') == product_id:
                        position = pos
                        break
                
                if not position:
                    continue
                
                # Calculate unrealized PnL
                size = pos.get('size', 0)
                if size == 0:
                    continue
                
                entry_price = float(pos.get('entry_price') or 0)
                mark_price = float(pos.get('mark_price') or 0)
                
                CONTRACT_MULTIPLIER = 0.001
                unrealized_pnl = (mark_price - entry_price) * size * CONTRACT_MULTIPLIER
                
                # Check if loss exceeds threshold (negative PnL)
                if unrealized_pnl < 0 and abs(unrealized_pnl) >= max_loss_threshold:
                    symbol = position.get('product_symbol', 'UNKNOWN')
                    
                    log.warning(
                        f"⚠️ MAX LOSS BREACH: {symbol} "
                        f"PnL=${unrealized_pnl:.2f} "
                        f"Threshold=${max_loss_threshold:.2f}"
                    )
                    
                    # Auto-close position
                    try:
                        close_response = delta_client.close_position(product_id=product_id)
                        
                        if close_response.get('success'):
                            log.info(f"✅ Auto-closed {symbol} due to max loss breach")
                            
                            # Disable monitoring for this position after closing
                            _max_loss_settings[product_id]['enabled'] = False
                        else:
                            log.error(
                                f"❌ Failed to auto-close {symbol}: "
                                f"{close_response.get('error', 'Unknown error')}"
                            )
                    except Exception as close_error:
                        log.error(f"❌ Error auto-closing {symbol}: {close_error}")
            
            time.sleep(_monitor_interval)
            
        except Exception as e:
            log.error(f"Max Loss Monitor error: {e}")
            log.error(traceback.format_exc())
            time.sleep(_monitor_interval)
    
    log.info("🔍 Max Loss Monitor: Stopped")


def _start_monitor():
    """Start the background monitor thread"""
    global _monitor_thread, _monitor_running
    
    if _monitor_running:
        return
    
    _monitor_running = True
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()
    log.info("🔍 Max Loss Monitor: Thread started")


def _stop_monitor():
    """Stop the background monitor thread"""
    global _monitor_running
    
    if not _monitor_running:
        return
    
    _monitor_running = False
    log.info("🔍 Max Loss Monitor: Stopping...")


@futures_max_loss_bp.route('/set', methods=['POST'])
def set_max_loss():
    """
    Set max loss threshold for a specific position.
    
    Request Body:
        {
            "product_id": 139,
            "symbol": "BTCUSD",
            "max_loss": 50.0,
            "enabled": true
        }
    
    Returns:
        JSON response confirming the setting
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['product_id', 'symbol', 'max_loss']
        for field in required:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        product_id = int(data['product_id'])
        symbol = data['symbol']
        max_loss = float(data['max_loss'])
        enabled = data.get('enabled', True)
        
        # Validate max_loss
        if max_loss < 0:
            return jsonify({
                'success': False,
                'error': 'Max loss must be a positive value'
            }), 400
        
        # Store setting
        _max_loss_settings[product_id] = {
            'max_loss': max_loss,
            'enabled': enabled,
            'symbol': symbol,
            'set_at': time.time()
        }
        
        # Start monitor if not already running
        if enabled:
            _start_monitor()
        
        log.info(
            f"✅ Max Loss set: {symbol} (product_id={product_id}) "
            f"threshold=${max_loss:.2f} enabled={enabled}"
        )
        
        return jsonify({
            'success': True,
            'message': f'Max loss set for {symbol}',
            'product_id': product_id,
            'max_loss': max_loss,
            'enabled': enabled
        })
        
    except Exception as e:
        log.error(f"Error setting max loss: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@futures_max_loss_bp.route('/get/<int:product_id>', methods=['GET'])
def get_max_loss(product_id: int):
    """
    Get max loss setting for a specific position.
    
    Args:
        product_id: Delta Exchange product ID
    
    Returns:
        JSON response with max loss setting
    """
    try:
        setting = _max_loss_settings.get(product_id)
        
        if not setting:
            return jsonify({
                'success': True,
                'has_setting': False,
                'product_id': product_id
            })
        
        return jsonify({
            'success': True,
            'has_setting': True,
            'product_id': product_id,
            'max_loss': setting.get('max_loss', 0),
            'enabled': setting.get('enabled', False),
            'symbol': setting.get('symbol', ''),
            'set_at': setting.get('set_at', 0)
        })
        
    except Exception as e:
        log.error(f"Error getting max loss: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@futures_max_loss_bp.route('/get-all', methods=['GET'])
def get_all_max_loss():
    """
    Get all max loss settings.
    
    Returns:
        JSON response with all settings
    """
    try:
        settings_list = []
        
        for product_id, setting in _max_loss_settings.items():
            settings_list.append({
                'product_id': product_id,
                'symbol': setting.get('symbol', ''),
                'max_loss': setting.get('max_loss', 0),
                'enabled': setting.get('enabled', False),
                'set_at': setting.get('set_at', 0)
            })
        
        return jsonify({
            'success': True,
            'count': len(settings_list),
            'settings': settings_list,
            'monitor_running': _monitor_running
        })
        
    except Exception as e:
        log.error(f"Error getting all max loss settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@futures_max_loss_bp.route('/disable/<int:product_id>', methods=['POST'])
def disable_max_loss(product_id: int):
    """
    Disable max loss monitoring for a specific position.
    
    Args:
        product_id: Delta Exchange product ID
    
    Returns:
        JSON response confirming disable
    """
    try:
        if product_id in _max_loss_settings:
            _max_loss_settings[product_id]['enabled'] = False
            symbol = _max_loss_settings[product_id].get('symbol', 'UNKNOWN')
            log.info(f"✅ Max Loss disabled: {symbol} (product_id={product_id})")
        
        return jsonify({
            'success': True,
            'message': f'Max loss monitoring disabled for product_id {product_id}'
        })
        
    except Exception as e:
        log.error(f"Error disabling max loss: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@futures_max_loss_bp.route('/clear-all', methods=['POST'])
def clear_all_max_loss():
    """
    Clear all max loss settings and stop monitoring.
    
    Returns:
        JSON response confirming clear
    """
    try:
        global _max_loss_settings
        
        count = len(_max_loss_settings)
        _max_loss_settings.clear()
        
        # Stop monitor if no settings remain
        if _monitor_running and not _max_loss_settings:
            _stop_monitor()
        
        log.info(f"✅ All max loss settings cleared ({count} settings)")
        
        return jsonify({
            'success': True,
            'message': f'Cleared {count} max loss settings'
        })
        
    except Exception as e:
        log.error(f"Error clearing max loss settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@futures_max_loss_bp.route('/status', methods=['GET'])
def monitor_status():
    """
    Get status of the max loss monitor.
    
    Returns:
        JSON response with monitor status
    """
    try:
        return jsonify({
            'success': True,
            'monitor_running': _monitor_running,
            'active_settings_count': len([s for s in _max_loss_settings.values() if s.get('enabled', False)]),
            'total_settings_count': len(_max_loss_settings),
            'monitor_interval': _monitor_interval
        })
        
    except Exception as e:
        log.error(f"Error getting monitor status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
