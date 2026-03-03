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

# Import cache
try:
    from webui.backend.cache import cache, CACHE_TIMEOUTS
except ImportError:
    from cache import cache, CACHE_TIMEOUTS

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

@liquidation_bp.route('/api/liquidation/debug', methods=['GET'])
def get_liquidation_debug():
    """Debug endpoint to check if Delta API is accessible"""
    import os
    from bot.api.delta_client import DeltaClient
    
    try:
        delta_client = DeltaClient()
        wallet_response = delta_client._req('GET', '/v2/wallet/balances')
        
        return jsonify({
            'success': True,
            'delta_api_key_set': bool(os.getenv('DELTA_API_KEY') or os.getenv('LIVE_DELTA_API_KEY')),
            'wallet_api_success': wallet_response.get('success'),
            'wallet_count': len(wallet_response.get('result', [])),
            'raw_response': wallet_response
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'delta_api_key_set': bool(os.getenv('DELTA_API_KEY') or os.getenv('LIVE_DELTA_API_KEY'))
        }), 500


@liquidation_bp.route('/api/liquidation/status', methods=['GET'])
@cache.cached(timeout=CACHE_TIMEOUTS['positions'])
def get_liquidation_status():
    """Get comprehensive liquidation protection status"""
    try:
        # Check trading mode
        cfg = get_config()
        trading_mode = cfg.trading_mode.lower()
        log.info(f"🔍 Liquidation endpoint called - trading_mode={trading_mode}")
        
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
        
        # ALWAYS try to fetch real data in live mode
        if trading_mode == 'live' and guardian_health_file.exists():
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
        
        # 3. Get REAL DATA from Delta Exchange API (ALWAYS in live mode)
        # PRIORITY: Use positions_upl from portfolio_margins (WebSocket/Guardian)
        # FALLBACK: Calculate from positions endpoint
        if trading_mode == 'live':
            try:
                from bot.api.delta_client import DeltaClient
                
                delta_client = DeltaClient()
                usd_to_inr_rate = float(get_config_value('risk_limits.usd_to_inr_rate', 'USD_TO_INR_RATE', 85.0))
                
                log.info("🔄 Fetching real data from Delta Exchange API...")
                
                # Only calculate manually if WebSocket data not available
                if mtm_status['current_mtm_inr'] == 0:
                    try:
                        positions_response = delta_client._req('GET', '/v2/positions/margined')
                        
                        if positions_response.get('success'):
                            pos_list = positions_response.get('result', [])
                            total_pnl_usd = 0
                            
                            for pos_data in pos_list:
                                size = int(pos_data.get('size', 0))
                                if size == 0:
                                    continue
                                
                                # ⚠️ FALLBACK CALCULATION (less accurate than positions_upl)
                                # Calculate PnL: (Mark - Entry) × Size × Contract Value
                                # Contract sizes per Delta Exchange India:
                                # - BTC: 1 lot = 0.001 BTC (multiplier = 0.001)
                                # - ETH: 1 lot = 0.01 ETH (multiplier = 0.01)
                                entry_price = float(pos_data.get('entry_price', 0))
                                mark_price = float(pos_data.get('mark_price', 0))
                                product_symbol = pos_data.get('product_symbol', '')
                                if 'ETH' in product_symbol.upper():
                                    CONTRACT_MULTIPLIER = 0.01
                                else:
                                    CONTRACT_MULTIPLIER = 0.001  # BTC and other assets
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
                            
                            log.debug(f"[FALLBACK] MTM calculated: ${total_pnl_usd:.2f} USD = ₹{total_pnl_inr:.2f} INR")
                                
                    except Exception as e:
                        log.debug(f"Could not fetch positions: {e}")
                wallet_response = delta_client._req('GET', '/v2/wallet/balances')
                
                # ✅ STEP 2: Try to get portfolio_margins data from WebSocket/REST
                # This contains: mm_w_ucf, im_w_ucf, positions_upl, liquidation_risk
                portfolio_margins_data = None
                try:
                    # Check if WebSocket data is available in Guardian health file
                    if guardian_health_file.exists():
                        with open(guardian_health_file, 'r') as f:
                            health = json.load(f)
                            portfolio_margins_data = health.get('portfolio_margins', {})
                except Exception as e:
                    log.debug(f"No WebSocket portfolio_margins data: {e}")
                
                if wallet_response.get('success'):
                    result = wallet_response.get('result', [])
                    # Find USD wallet (not BTC/ETH)
                    wallet_data = None
                    for wallet in result:
                        if wallet.get('asset_symbol') == 'USD':
                            wallet_data = wallet
                            break
                    
                    if not wallet_data and result:
                        # Fallback to first wallet if USD not found
                        wallet_data = result[0]
                    
                    if wallet_data:
                        balance_usd = float(wallet_data.get('balance', 0))
                        available_balance_usd = float(wallet_data.get('available_balance', 0))
                        blocked_margin_usd = float(wallet_data.get('blocked_margin', 0))
                        
                        if balance_usd > 0:
                            # Convert USD to INR
                            balance = balance_usd * usd_to_inr_rate
                            available_balance = available_balance_usd * usd_to_inr_rate
                            blocked_margin = blocked_margin_usd * usd_to_inr_rate
                            
                            margin_status['total_balance'] = round(balance, 2)
                            margin_status['available_balance'] = round(available_balance, 2)
                            margin_status['blocked_margin'] = round(blocked_margin, 2)
                            
                            # ✅ DELTA EXCHANGE CORRECT FORMULAS (Portfolio Margin Mode)
                            
                            # Get Initial Margin and Maintenance Margin from portfolio_margins
                            if portfolio_margins_data:
                                im_w_ucf_usd = float(portfolio_margins_data.get('im_w_ucf', blocked_margin_usd))
                                mm_w_ucf_usd = float(portfolio_margins_data.get('mm_w_ucf', blocked_margin_usd * 0.8))
                                positions_upl_usd = float(portfolio_margins_data.get('positions_upl', 0))
                                api_liquidation_risk = portfolio_margins_data.get('liquidation_risk', False)
                                api_under_liquidation = portfolio_margins_data.get('under_liquidation', False)
                                margin_shortfall_usd = float(portfolio_margins_data.get('margin_shortfall', 0))
                            else:
                                # Fallback estimates (80% rule for MM)
                                im_w_ucf_usd = blocked_margin_usd
                                mm_w_ucf_usd = blocked_margin_usd * 0.8
                                positions_upl_usd = 0
                                api_liquidation_risk = False
                                api_under_liquidation = False
                                margin_shortfall_usd = 0
                            
                            im_w_ucf = im_w_ucf_usd * usd_to_inr_rate
                            mm_w_ucf = mm_w_ucf_usd * usd_to_inr_rate
                            
                            # ✅ MARGIN UTILIZATION (CORRECT FORMULA)
                            # Formula: (Initial Margin / Balance) × 100
                            utilization = (im_w_ucf / balance) * 100
                            margin_status['utilization'] = round(utilization, 1)
                            
                            # ✅ LIQUIDATION DISTANCE (CORRECT FORMULA)
                            # Formula: ((Balance - MM) / MM) × 100
                            if mm_w_ucf > 0:
                                liquidation_distance = ((balance - mm_w_ucf) / mm_w_ucf) * 100
                                distance_status['distance'] = round(liquidation_distance, 1)
                                distance_status['maintenance_margin'] = round(mm_w_ucf, 2)
                                
                                # ✅ DELTA EXCHANGE RISK ZONES (Recommended Thresholds)
                                if api_under_liquidation or liquidation_distance < 5:
                                    distance_status['zone'] = 'CRITICAL'
                                    distance_status['liquidation_risk'] = True
                                elif api_liquidation_risk or liquidation_distance < 20:
                                    distance_status['zone'] = 'DANGER'
                                    distance_status['liquidation_risk'] = True
                                elif liquidation_distance < 50:
                                    distance_status['zone'] = 'WARNING'
                                    distance_status['liquidation_risk'] = False
                                else:
                                    distance_status['zone'] = 'SAFE'
                                    distance_status['liquidation_risk'] = False
                                
                                # Add Delta Exchange flags
                                distance_status['api_liquidation_risk'] = api_liquidation_risk
                                distance_status['under_liquidation'] = api_under_liquidation
                                if margin_shortfall_usd > 0:
                                    distance_status['margin_shortfall'] = round(margin_shortfall_usd * usd_to_inr_rate, 2)
                                
                                log.debug(f"✅ DELTA EXCHANGE FORMULA: Liquidation Distance = ((₹{balance:.2f} - ₹{mm_w_ucf:.2f}) / ₹{mm_w_ucf:.2f}) × 100 = {liquidation_distance:.1f}%")
                            
                            # Update unrealized PnL if WebSocket data available
                            if portfolio_margins_data and positions_upl_usd != 0:
                                positions_upl_inr = positions_upl_usd * usd_to_inr_rate
                                mtm_status['current_mtm_inr'] = round(positions_upl_inr, 2)
                                margin_status['unrealized_pnl'] = round(positions_upl_inr, 2)
                                log.debug(f"✅ Using WebSocket positions_upl: ${positions_upl_usd:.2f} = ₹{positions_upl_inr:.2f}")
                            
                            log.debug(f"Wallet: ${balance_usd:.2f} USD = ₹{balance:.2f} INR")
                            log.debug(f"IM (w/ UCF): ${im_w_ucf_usd:.2f} USD = ₹{im_w_ucf:.2f} INR")
                            log.debug(f"MM (w/ UCF): ${mm_w_ucf_usd:.2f} USD = ₹{mm_w_ucf:.2f} INR")
                            
                            # ✅ MARGIN UTILIZATION ZONES (Delta Exchange Thresholds)
                            if utilization >= 100:
                                margin_status['zone'] = 'RED'
                                margin_status['can_open_positions'] = False
                            elif utilization >= 80:
                                margin_status['zone'] = 'ORANGE'
                                margin_status['can_open_positions'] = False
                            elif utilization >= 60:
                                margin_status['zone'] = 'YELLOW'
                                margin_status['can_open_positions'] = True
                            else:
                                margin_status['zone'] = 'GREEN'
                                margin_status['can_open_positions'] = True
                            
                            log.debug(f"Margin Utilization: {utilization:.1f}% (IM/Balance)")
                        
            except Exception as e:
                log.warning(f"Could not fetch wallet balance: {e}")
                        
                log.error(f"Error fetching Delta Exchange data: {e}", exc_info=True)
        else:
            log.info("Demo mode - using placeholder values")
        
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
@cache.cached(timeout=CACHE_TIMEOUTS['positions'])
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
