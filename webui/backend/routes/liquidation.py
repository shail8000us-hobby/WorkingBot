"""
Liquidation Protection API Blueprint

This module handles all API routes related to liquidation protection monitoring.

Routes:
- GET  /api/liquidation/status - Get comprehensive liquidation protection status
- GET  /api/liquidation/realtime-status - Get real-time monitoring status
- GET  /api/liquidation/margin-history - Get historical margin utilization
- POST /api/liquidation/emergency-action - Trigger emergency position closure
- GET/POST /api/liquidation/config - Get or update liquidation config

Dependencies:
- bot.safety.liquidation_monitor (liquidation monitoring)

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request

# Import config helper
from config.loader import get_config

log = logging.getLogger(__name__)

# Create blueprint
liquidation_bp = Blueprint('liquidation', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent


def get_config_value(yaml_path: str, env_var: str, default):
    """
    Helper to get config value from YAML or environment
    
    Args:
        yaml_path: Dot-separated path in YAML (e.g., 'risk_limits.usd_to_inr_rate')
        env_var: Environment variable name (fallback, deprecated)
        default: Default value if not found
    
    Returns:
        Config value or default
    """
    try:
        cfg = get_config()
        # Navigate YAML path
        keys = yaml_path.split('.')
        value = cfg
        for key in keys:
            value = getattr(value, key, None)
            if value is None:
                break
        
        if value is not None:
            return value
        
        # Fallback to environment variable
        env_value = os.getenv(env_var)
        if env_value is not None:
            return env_value
        
        return default
    except Exception:
        return default

# Try to import liquidation monitor
try:
    from bot.safety.liquidation_monitor import get_liquidation_monitor
    liquidation_monitor = get_liquidation_monitor()
    MONITOR_AVAILABLE = True
except ImportError:
    log.warning("Liquidation monitor not available")
    MONITOR_AVAILABLE = False
    liquidation_monitor = None

# ============================================================================
# Liquidation Status Routes
# ============================================================================

@liquidation_bp.route('/api/liquidation/status', methods=['GET'])
def get_liquidation_status():
    """Get comprehensive liquidation protection status"""
    try:
        # Check trading mode
        cfg = get_config()
        trading_mode = cfg.trading_mode.lower()
        
        # Default safe values
        margin_status = {
            'utilization': 5,
            'zone': 'GREEN',
            'can_open_positions': True,
            'total_balance': 100000,
            'available_balance': 95000,
            'blocked_margin': 5000,
            'unrealized_pnl': 0
        }
        
        distance_status = {
            'distance': 75,
            'zone': 'SAFE',
            'maintenance_margin': 25000,
            'liquidation_risk': False
        }
        
        mtm_status = {
            'current_mtm_inr': 0,
            'trend': 'STABLE'
        }
        
        # Try to get real data from multiple sources
        # 1. PRIORITY: Try Guardian health file (Delta Exchange India improvements)
        import json
        from pathlib import Path
        
        guardian_health_file = Path(__file__).parent.parent.parent.parent / '.guardian_health'
        guardian_data_used = False
        
        if guardian_health_file.exists() and trading_mode == 'live':
            try:
                with open(guardian_health_file, 'r') as f:
                    health_data = json.load(f)
                
                # Get liquidation metrics from Guardian (Delta Exchange India calculations)
                liquidation = health_data.get('liquidation', {})
                positions = health_data.get('positions', {})
                
                if liquidation:
                    # Use price-based liquidation distance from PositionMonitor
                    liq_distance = liquidation.get('distance', 100.0)
                    is_critical = liquidation.get('critical', False)
                    is_warning = liquidation.get('warning', False)
                    
                    # Map to existing zone names
                    if is_critical:
                        zone = 'CRITICAL'
                        liquidation_risk = True
                    elif is_warning:
                        zone = 'DANGER'
                        liquidation_risk = True
                    elif liq_distance < 10.0:
                        zone = 'WARNING'
                        liquidation_risk = False
                    else:
                        zone = 'SAFE'
                        liquidation_risk = False
                    
                    distance_status.update({
                        'distance': round(liq_distance, 1),
                        'zone': zone,
                        'liquidation_risk': liquidation_risk,
                        'bankruptcy_distance': round(liquidation.get('bankruptcy_distance', 100.0), 1)
                    })
                    guardian_data_used = True
                    log.debug(f"Using Guardian liquidation distance: {liq_distance:.1f}% (price-based)")
                
                # Get position PnL from Guardian
                if positions:
                    mtm_status['current_mtm_inr'] = round(positions.get('total_pnl_inr', 0), 2)
                    margin_status['unrealized_pnl'] = round(positions.get('total_pnl_inr', 0), 2)
                    
            except Exception as e:
                log.warning(f"Could not read Guardian health file: {e}")
        
        # 2. Fallback: Try liquidation monitor
        if not guardian_data_used and MONITOR_AVAILABLE and liquidation_monitor and trading_mode == 'live':
            try:
                real_time_status = liquidation_monitor.get_status()
                if 'total_balance' in real_time_status and real_time_status.get('total_balance', 0) > 0:
                    margin_status.update({
                        'utilization': real_time_status.get('margin_utilization', 0),
                        'zone': real_time_status.get('margin_zone', 'SAFE'),
                        'can_open_positions': real_time_status.get('margin_utilization', 0) < 80,
                        'total_balance': real_time_status.get('total_balance', 0),
                        'available_balance': real_time_status.get('available_balance', 0),
                        'blocked_margin': real_time_status.get('blocked_balance', 0),
                        'unrealized_pnl': real_time_status.get('total_unrealized_pnl', 0)
                    })
            except Exception as e:
                log.warning(f"Could not get liquidation monitor data: {e}")
        
        # 2. Fallback: Get MTM from Delta Exchange API (same as positions blueprint)
        try:
            from bot.api.delta_client import DeltaClient
            
            delta_client = DeltaClient()
            usd_to_inr_rate = float(get_config_value('risk_limits.usd_to_inr_rate', 'USD_TO_INR_RATE', 85.0))
            
            # Get positions for MTM
            try:
                positions_response = delta_client._req('GET', '/v2/positions/margined')
                
                if positions_response.get('success'):
                    pos_list = positions_response.get('result', [])
                    total_pnl_usd = 0
                    
                    for pos_data in pos_list:
                        size = int(pos_data.get('size', 0))
                        if size == 0:
                            continue
                        
                        # Calculate PnL same way as positions endpoint: (Mark - Entry) × Size × 0.001
                        entry_price = float(pos_data.get('entry_price', 0))
                        mark_price = float(pos_data.get('mark_price', 0))
                        CONTRACT_MULTIPLIER = 0.001
                        unrealized_pnl_usd = (mark_price - entry_price) * size * CONTRACT_MULTIPLIER
                        total_pnl_usd += unrealized_pnl_usd
                    
                    # Convert to INR
                    total_pnl_inr = total_pnl_usd * usd_to_inr_rate
                    
                    mtm_status['current_mtm_inr'] = round(total_pnl_inr, 2)
                    margin_status['unrealized_pnl'] = round(total_pnl_inr, 2)
                    
                    # Determine trend
                    if total_pnl_inr > 1000:
                        mtm_status['trend'] = 'UP'
                    elif total_pnl_inr < -1000:
                        mtm_status['trend'] = 'DOWN'
                    else:
                        mtm_status['trend'] = 'STABLE'
                    
                    log.debug(f"MTM: ${total_pnl_usd:.2f} USD = ₹{total_pnl_inr:.2f} INR")
                        
            except Exception as e:
                log.debug(f"Could not fetch positions: {e}")
            
            # Get wallet balance for margin utilization
            try:
                wallet_response = delta_client._req('GET', '/v2/wallet/balances')
                
                if wallet_response.get('success'):
                    result = wallet_response.get('result', [])
                    if result and len(result) > 0:
                        wallet_data = result[0]
                        
                        balance_usd = float(wallet_data.get('balance', 0))
                        available_balance_usd = float(wallet_data.get('available_balance', 0))
                        portfolio_margin_usd = float(wallet_data.get('portfolio_margin', 0))
                        
                        if balance_usd > 0:
                            # Convert USD to INR
                            balance = balance_usd * usd_to_inr_rate
                            available_balance = available_balance_usd * usd_to_inr_rate
                            maintenance_margin = portfolio_margin_usd * usd_to_inr_rate
                            
                            margin_status['total_balance'] = round(balance, 2)
                            margin_status['available_balance'] = round(available_balance, 2)
                            
                            # Calculate utilization (percentage is same in USD or INR)
                            used = balance - available_balance
                            margin_status['blocked_margin'] = round(used, 2)
                            utilization = (used / balance) * 100
                            margin_status['utilization'] = round(utilization, 1)
                            
                            # Only calculate margin-based distance if Guardian didn't provide price-based distance
                            if not guardian_data_used and maintenance_margin > 0:
                                # OLD FORMULA (margin-based): Only used as fallback
                                # Note: This is DIFFERENT from Delta Exchange India price-based calculation
                                liquidation_distance = ((available_balance / maintenance_margin) - 1) * 100
                                distance_status['distance'] = round(liquidation_distance, 1)
                                distance_status['maintenance_margin'] = round(maintenance_margin, 2)
                                
                                # Determine zone based on margin distance (different thresholds)
                                if liquidation_distance < 20:
                                    distance_status['zone'] = 'CRITICAL'
                                    distance_status['liquidation_risk'] = True
                                elif liquidation_distance < 40:
                                    distance_status['zone'] = 'DANGER'
                                    distance_status['liquidation_risk'] = True
                                elif liquidation_distance < 60:
                                    distance_status['zone'] = 'WARNING'
                                    distance_status['liquidation_risk'] = False
                                else:
                                    distance_status['zone'] = 'SAFE'
                                    distance_status['liquidation_risk'] = False
                                
                                log.debug(f"[FALLBACK] Margin-based liquidation distance: {liquidation_distance:.1f}% (Available: ₹{available_balance:.2f} / MM: ₹{maintenance_margin:.2f})")
                            else:
                                distance_status['maintenance_margin'] = round(maintenance_margin, 2)
                            
                            log.debug(f"Wallet balance: ${balance_usd:.2f} USD = ₹{balance:.2f} INR")
                            
                            # Determine zone
                            if utilization >= 80:
                                margin_status['zone'] = 'RED'
                            elif utilization >= 70:
                                margin_status['zone'] = 'ORANGE'
                            elif utilization >= 60:
                                margin_status['zone'] = 'YELLOW'
                            else:
                                margin_status['zone'] = 'GREEN'
                            
                            margin_status['can_open_positions'] = utilization < 80
                            
                            log.debug(f"Fetched margin: {utilization:.1f}% utilization")
                        
            except Exception as e:
                log.debug(f"Could not fetch wallet balance: {e}")
                
        except Exception as e:
            log.warning(f"Error fetching Delta Exchange data: {e}")
        
        return jsonify({
            'success': True,
            'margin': margin_status,
            'distance': distance_status,
            'mtm': mtm_status,
            'config': {
                'enabled': True,
                'margin_utilization_max': float(get_config_value('liquidation_protection.margin_utilization_max', 'MARGIN_UTILIZATION_MAX', 40)),
                'margin_warning_1': float(get_config_value('liquidation_protection.margin_utilization_warning_1', 'MARGIN_UTILIZATION_WARNING_1', 50)),
                'margin_warning_2': float(get_config_value('liquidation_protection.margin_utilization_warning_2', 'MARGIN_UTILIZATION_WARNING_2', 70)),
                'liquidation_distance_min': float(get_config_value('liquidation_protection.liquidation_distance_min', 'LIQUIDATION_DISTANCE_MIN', 60)),
                'liquidation_distance_target': float(get_config_value('liquidation_protection.liquidation_distance_target', 'LIQUIDATION_DISTANCE_TARGET', 70))
            },
            'testnet_mode': trading_mode == 'demo'
        }), 200
        
    except Exception as e:
        log.error(f"Error getting liquidation status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@liquidation_bp.route('/api/liquidation/realtime-status', methods=['GET'])
def get_realtime_liquidation_status():
    """Get real-time liquidation monitoring status"""
    try:
        if MONITOR_AVAILABLE and liquidation_monitor and liquidation_monitor.is_running():
            status = liquidation_monitor.get_status()
            detailed = liquidation_monitor.get_detailed_status()
            
            return jsonify({
                'success': True,
                'status': status,
                'detailed': detailed,
                'connection': {
                    'status': 'connected',
                    'data_source': 'delta_exchange_api',
                    'last_update': status.get('last_update', datetime.now().isoformat())
                },
                'monitoring_active': True
            }), 200
        else:
            # Return simulated safe status for demo mode
            return jsonify({
                'success': True,
                'status': {
                    'timestamp': datetime.utcnow().isoformat(),
                    'margin_utilization': 5.0,
                    'margin_zone': 'GREEN',
                    'liquidation_distance': 75.0,
                    'distance_zone': 'SAFE',
                    'mtm_inr': 0.0,
                    'mtm_trend': 'STABLE',
                    'last_update': datetime.utcnow().isoformat()
                },
                'detailed': {
                    'monitoring_active': False,
                    'simulation': True
                },
                'connection': {
                    'connected': False,
                    'simulation': True
                },
                'monitoring_active': False
            }), 200
            
    except Exception as e:
        log.error(f"Error getting realtime liquidation status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@liquidation_bp.route('/api/liquidation/margin-history', methods=['GET'])
def get_margin_history():
    """Get historical margin utilization data"""
    try:
        # TODO: Read from log file when available
        return jsonify({
            'success': True,
            'history': []
        }), 200
    except Exception as e:
        log.error(f"Error getting margin history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@liquidation_bp.route('/api/liquidation/emergency-action', methods=['POST'])
def trigger_emergency_action():
    """Trigger emergency liquidation action (close all positions)"""
    try:
        if not MONITOR_AVAILABLE or not liquidation_monitor:
            return jsonify({
                'success': False,
                'error': 'Liquidation monitor not available'
            }), 503
        
        # Trigger emergency action
        liquidation_monitor.force_emergency_action()
        
        return jsonify({
            'success': True,
            'message': 'Emergency action triggered - all positions closed',
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        log.error(f"Error triggering emergency action: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@liquidation_bp.route('/api/liquidation/config', methods=['GET', 'POST'])
def liquidation_config():
    """Get or update liquidation protection configuration"""
    if request.method == 'GET':
        try:
            config = {
                # Core Settings
                'LIQUIDATION_PROTECTION_ENABLED': str(get_config_value('safety.liquidation_protection_enabled', 'LIQUIDATION_PROTECTION_ENABLED', True)),
                'LIQUIDATION_LOG_LEVEL': get_config_value('logging.level', 'LIQUIDATION_LOG_LEVEL', 'INFO'),
                
                # Margin Utilization Monitoring
                'MARGIN_UTILIZATION_MAX': str(get_config_value('liquidation_protection.margin.max_utilization', 'MARGIN_UTILIZATION_MAX', 40)),
                'MARGIN_UTILIZATION_WARNING_1': str(get_config_value('liquidation_protection.margin.warning_level_1', 'MARGIN_UTILIZATION_WARNING_1', 50)),
                'MARGIN_UTILIZATION_WARNING_2': str(get_config_value('liquidation_protection.margin.warning_level_2', 'MARGIN_UTILIZATION_WARNING_2', 70)),
                'MARGIN_EMERGENCY_RESERVE': str(get_config_value('liquidation_protection.margin.emergency_reserve', 'MARGIN_EMERGENCY_RESERVE', 60)),
                
                # Liquidation Distance Monitoring
                'LIQUIDATION_DISTANCE_MIN': str(get_config_value('liquidation_protection.distance.minimum', 'LIQUIDATION_DISTANCE_MIN', 60)),
                'LIQUIDATION_DISTANCE_TARGET': str(get_config_value('liquidation_protection.distance.target', 'LIQUIDATION_DISTANCE_TARGET', 70)),
                'LIQUIDATION_DISTANCE_CRITICAL': str(get_config_value('liquidation_protection.distance.critical', 'LIQUIDATION_DISTANCE_CRITICAL', 40)),
                
                # MTM Monitoring
                'MTM_MONITORING_ENABLED': str(get_config_value('liquidation_protection.mtm.enabled', 'MTM_MONITORING_ENABLED', True)),
                'MTM_DRAWDOWN_THRESHOLD': str(get_config_value('liquidation_protection.mtm.drawdown_threshold', 'MTM_DRAWDOWN_THRESHOLD', -20000)),
                
                # Monitoring Intervals
                'LIQUIDATION_CHECK_INTERVAL': str(get_config_value('liquidation_protection.check_interval', 'LIQUIDATION_CHECK_INTERVAL', 5)),
                'LIQUIDATION_ALERT_THROTTLE': str(get_config_value('liquidation_protection.alert_throttle', 'LIQUIDATION_ALERT_THROTTLE', 60))
            }
            
            return jsonify({
                'success': True,
                'config': config
            }), 200
            
        except Exception as e:
            log.error(f"Error getting liquidation config: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    else:  # POST
        try:
            # TODO: Implement config update logic
            updates = request.json
            if not updates:
                return jsonify({
                    'success': False,
                    'error': 'No configuration updates provided'
                }), 400
            
            # For now, return success
            return jsonify({
                'success': True,
                'message': 'Configuration update not yet implemented',
                'updates': updates
            }), 200
            
        except Exception as e:
            log.error(f"Error updating liquidation config: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
