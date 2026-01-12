"""
Risk Management API Blueprint
Handles all /api/risk/* routes including volatility monitoring, VaR calculations, and circuit breakers
"""

from flask import Blueprint, request, jsonify
import os
import json
import traceback
from pathlib import Path
from datetime import datetime
import logging

from config.loader import get_config

def get_config_value(yaml_path: str, env_var: str = None, default: any = None):
    """Get config value from YAML using dot notation"""
    try:
        cfg = get_config()
        value = cfg
        for key in yaml_path.split('.'):
            value = getattr(value, key)
        return value
    except (AttributeError, KeyError):
        return default

log = logging.getLogger(__name__)

risk_bp = Blueprint('risk', __name__)

# Get BASE_DIR
BASE_DIR = Path(__file__).parent.parent.parent.parent


@risk_bp.route('/api/risk/analytics', methods=['GET'])
def get_risk_analytics():
    """
    Get comprehensive risk analytics including VaR, CVaR, volatility, and stress tests.
    Returns professional-grade risk metrics used by institutional traders.
    
    v6.0: Supports per-instance risk analytics
    Query params:
        lookback_days: Lookback period (default: 30)
        force_refresh: Force recalculation (true/false)
        instance: Optional instance name (e.g., BTCUSD_LONG)
    """
    try:
        # v6.0: Extract instance parameter
        instance = request.args.get('instance')
        
        from bot.ai.analytics.risk import get_risk_analytics
        
        # Get risk analytics engine (with instance if provided)
        analytics = get_risk_analytics(instance=instance) if instance else get_risk_analytics()
        
        # Get lookback period from query params (default 30 days)
        lookback_days = int(request.args.get('lookback_days', 30))
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        # Calculate all risk metrics
        metrics = analytics.calculate_all_metrics(
            lookback_days=lookback_days,
            force_refresh=force_refresh
        )
        
        # Add risk grades
        grades = analytics.get_risk_grade(metrics)
        
        return jsonify({
            'success': True,
            'data': {
                **metrics,
                'grades': grades
            }
        })
    except Exception as e:
        print(f"❌ Risk analytics error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        }), 500


@risk_bp.route('/api/risk/var', methods=['GET'])
def get_value_at_risk():
    """
    Get Value at Risk (VaR) calculations - the maximum expected loss at a confidence level.
    Supports multiple VaR calculation methods: Historical, Parametric, and Monte Carlo.
    """
    try:
        from bot.ai.analytics.risk import get_risk_analytics
        
        analytics = get_risk_analytics()
        
        # Get parameters
        confidence = float(request.args.get('confidence', 0.95))
        lookback_days = int(request.args.get('lookback_days', 30))
        
        # Load returns
        returns = analytics._load_returns(lookback_days)
        portfolio_data = analytics._load_current_portfolio_data()
        portfolio_value = portfolio_data['total_balance']
        
        # Calculate VaR using different methods
        var_data = {
            'confidence_level': confidence,
            'portfolio_value': portfolio_value,
            'historical_var': analytics.calculate_historical_var(returns, confidence, portfolio_value),
            'parametric_var': analytics.calculate_parametric_var(returns, confidence, portfolio_value),
            'monte_carlo_var': analytics.calculate_monte_carlo_var(returns, confidence, portfolio_value),
            'cvar': analytics.calculate_cvar(returns, confidence, portfolio_value)
        }
        
        # Calculate as percentage of portfolio
        for key in ['historical_var', 'parametric_var', 'monte_carlo_var', 'cvar']:
            var_inr = abs(var_data[key])
            var_data[f'{key}_pct'] = round((var_inr / portfolio_value) * 100, 2) if portfolio_value > 0 else 0
        
        return jsonify({
            'success': True,
            'data': var_data
        })
    except Exception as e:
        print(f"❌ VaR calculation error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        }), 500


@risk_bp.route('/api/risk/stress_test', methods=['POST'])
def run_stress_test():
    """
    Run stress test scenarios on the portfolio.
    Tests portfolio resilience against various market shocks.
    """
    try:
        from bot.ai.analytics.risk import get_risk_analytics
        
        analytics = get_risk_analytics()
        portfolio_data = analytics._load_current_portfolio_data()
        
        # Get custom scenarios from request or use defaults
        data = request.get_json() or {}
        scenarios = data.get('scenarios')
        
        # Run stress test
        stress_results = analytics.stress_test_portfolio(
            current_equity=portfolio_data['total_balance'],
            positions=portfolio_data['positions'],
            scenarios=scenarios
        )
        
        return jsonify({
            'success': True,
            'data': stress_results
        })
    except Exception as e:
        print(f"❌ Stress test error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        }), 500


@risk_bp.route('/api/risk/status', methods=['GET'])
def get_risk_status():
    """
    Get overall risk management system status.
    Shows which risk features are active and operational.
    """
    try:
        # Get circuit breaker status
        circuit_breaker_status = 'unknown'
        try:
            from bot.api.delta_client import DeltaClient
            client = DeltaClient()
            cb_stats = client.get_circuit_breaker_stats()
            circuit_breaker_status = cb_stats['state']
        except Exception:
            pass
        
        # Get loss limits validation status
        loss_limits_valid = False
        try:
            from bot.safety.loss_limits import get_loss_limits_config
            loss_config = get_loss_limits_config()
            loss_limits_valid = loss_config.get('is_valid', False)
        except Exception:
            pass
        
        return jsonify({
            'success': True,
            'data': {
                'circuit_breaker': {
                    'status': circuit_breaker_status,
                    'active': circuit_breaker_status == 'CLOSED',
                    'description': 'API call protection against rate limits and failures'
                },
                'volatility_safety': {
                    'status': 'pending_migration',
                    'active': False,
                    'description': 'IV/RV monitoring (WebSocket migration in progress)'
                },
                'order_confirmation': {
                    'status': 'active',
                    'active': True,
                    'description': 'Fill tracking and order confirmation guard'
                },
                'loss_limits': {
                    'status': 'active' if loss_limits_valid else 'misconfigured',
                    'active': loss_limits_valid,
                    'description': 'Guardian and Trader loss limit validation'
                },
                'risk_analytics': {
                    'status': 'active',
                    'active': True,
                    'description': 'VaR, CVaR, and professional risk metrics'
                },
                'liquidation_protection': {
                    'status': 'active',
                    'active': get_config_value('safety.liquidation_protection_enabled', 'LIQUIDATION_PROTECTION_ENABLED', True),
                    'description': 'Real-time liquidation monitoring and alerts'
                }
            }
        })
    except Exception as e:
        print(f"❌ Risk status error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        }), 500


@risk_bp.route('/api/risk/circuit_breaker', methods=['GET'])
def get_circuit_breaker_status():
    """Get circuit breaker statistics and status"""
    try:
        from bot.api.delta_client import DeltaClient
        
        client = DeltaClient()
        stats = client.get_circuit_breaker_stats()
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        }), 500


@risk_bp.route('/api/risk/circuit_breaker/reset', methods=['POST'])
def reset_circuit_breaker():
    """Manually reset circuit breaker (admin action)"""
    try:
        from bot.api.delta_client import DeltaClient
        
        client = DeltaClient()
        client.reset_circuit_breaker()
        
        return jsonify({
            'success': True,
            'message': 'Circuit breaker reset successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@risk_bp.route('/api/risk/volatility', methods=['GET'])
def get_risk_volatility_status():
    """Get real-time volatility monitoring status"""
    try:
        from bot.safety.volatility_monitor import get_volatility_monitor
        
        monitor = get_volatility_monitor()
        status = monitor.get_status()
        
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        print(f"❌ Volatility status error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        }), 500


@risk_bp.route('/api/risk/volatility/history', methods=['GET'])
def get_risk_volatility_history():
    """Get historical volatility data"""
    try:
        from bot.volatility.delta_volatility_collector import get_collector

        try:
            periods = int(request.args.get('periods', 100) or 100)
        except (TypeError, ValueError):
            return jsonify({
                'success': False,
                'error': 'Invalid periods value'
            }), 400

        # Get timeframe from query parameter (hourly, daily, weekly, monthly)
        timeframe = request.args.get('timeframe', 'daily')
        if timeframe not in ['hourly', 'daily', 'weekly', 'monthly']:
            timeframe = 'daily'

        # v6.0: Multi-symbol support
        symbol = request.args.get('symbol', 'BTCUSD')
        collector = get_collector(symbol=symbol)
        data = collector.get_historical_data(timeframe=timeframe, limit=periods)

        merged = {}
        for entry in data.get('iv', []):
            ts = entry.get('timestamp')
            if ts is None:
                continue
            merged.setdefault(ts, {'timestamp': ts})['iv'] = entry.get('value')
        for entry in data.get('rv', []):
            ts = entry.get('timestamp')
            if ts is None:
                continue
            merged.setdefault(ts, {'timestamp': ts})['rv'] = entry.get('value')

        history = sorted(merged.values(), key=lambda item: item['timestamp'])[-periods:]
        
        return jsonify({
            'success': True,
            'data': {
                'history': history,
                'count': len(history)
            }
        })
    except Exception as e:
        print(f"❌ Volatility history error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {'history': [], 'count': 0}
        }), 500


@risk_bp.route('/api/risk/volatility/update', methods=['POST'])
def update_volatility_price():
    """Update volatility monitor with new price (for testing or manual updates)"""
    try:
        from bot.safety.volatility_monitor import get_volatility_monitor
        
        data = request.get_json()
        price = float(data.get('price'))
        timestamp = data.get('timestamp')  # Optional
        
        monitor = get_volatility_monitor()
        monitor.add_price(price, timestamp)
        
        return jsonify({
            'success': True,
            'message': 'Price updated',
            'status': monitor.get_status()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@risk_bp.route('/api/risk/volatility/historical', methods=['GET'])
def get_risk_volatility_historical():
    """
    Get historical IV/RV data for volatility chart.
    
    Query Parameters:
        timeframe: 'daily', 'weekly', or 'monthly' (default: 'daily')
        limit: Number of data points to return (default: 100)
    
    Returns:
        JSON with {success, data: {iv: [...], rv: [...]}}
    """
    try:
        from bot.volatility.delta_volatility_collector import get_collector
        
        timeframe = request.args.get('timeframe', 'daily')
        try:
            # For hourly with 30s data collection over 24h, we need ~2880 points
            # Use higher default for hourly to show full day
            default_limit = 3000 if timeframe == 'hourly' else 100
            limit = int(request.args.get('limit', default_limit))
        except (TypeError, ValueError):
            limit = 3000 if timeframe == 'hourly' else 100
        
        # Validate timeframe
        if timeframe not in ['hourly', 'daily', 'weekly', 'monthly']:
            return jsonify({
                'success': False,
                'error': f'Invalid timeframe: {timeframe}. Must be hourly, daily, weekly, or monthly.'
            }), 400
        
        # v6.0: Multi-symbol support
        symbol = request.args.get('symbol', 'BTCUSD')
        collector = get_collector(symbol=symbol)
        data = collector.get_historical_data(timeframe=timeframe, limit=limit)
        
        # Fallback: If hourly data is empty, try daily data
        if timeframe == 'hourly' and (not data.get('iv') or len(data.get('iv', [])) == 0):
            log.debug("Hourly data empty, falling back to daily timeframe")
            data = collector.get_historical_data(timeframe='daily', limit=limit)
            data['fallback_timeframe'] = 'daily'
        
        return jsonify({
            'success': True,
            'data': data,
            'timeframe': timeframe
        })
    except Exception as e:
        print(f"❌ Volatility historical data error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {'iv': [], 'rv': []}
        }), 500


@risk_bp.route('/api/risk/metrics', methods=['GET'])
def get_risk_metrics():
    """
    Get risk metrics for the RiskMetricsPanel component.
    Returns exposure, VaR, drawdown, and other key risk indicators.
    """
    try:
        # Try to get from risk analytics if available
        try:
            from bot.ai.analytics.risk import get_risk_analytics
            
            analytics = get_risk_analytics()
            portfolio_data = analytics._load_current_portfolio_data()
            
            # Get current exposure and calculate metrics
            current_exposure = portfolio_data.get('total_exposure', 0)
            total_balance = portfolio_data.get('total_balance', 1)
            max_exposure = total_balance * 10  # Default to 10x balance as max
            
            # Calculate exposure percentage
            exposure_percentage = (current_exposure / max_exposure * 100) if max_exposure > 0 else 0
            
            # Try to get VaR and CVaR
            try:
                returns = analytics._load_returns(30)
                var_95 = abs(analytics.calculate_historical_var(returns, 0.95, total_balance))
                cvar_95 = abs(analytics.calculate_cvar(returns, 0.95, total_balance))
            except:
                var_95 = total_balance * 0.05  # 5% default
                cvar_95 = total_balance * 0.07  # 7% default
            
            # Get drawdown info
            try:
                current_drawdown = portfolio_data.get('current_drawdown', 0)
                max_drawdown = portfolio_data.get('max_drawdown', 0)
            except:
                current_drawdown = 0
                max_drawdown = 0
            
            # Calculate position risk (percentage of portfolio in positions)
            position_risk = (current_exposure / total_balance * 100) if total_balance > 0 else 0
            
            # Calculate margin utilization
            try:
                margin_used = portfolio_data.get('margin_used', 0)
                margin_available = portfolio_data.get('margin_available', total_balance)
                margin_utilization = (margin_used / (margin_used + margin_available) * 100) if (margin_used + margin_available) > 0 else 0
            except:
                margin_utilization = 0
            
            # Calculate leverage
            leverage = (current_exposure / total_balance) if total_balance > 0 else 1.0
            
            # Calculate risk-reward ratio (simplified)
            risk_reward_ratio = 1.5  # Default value
            
            metrics = {
                'current_exposure': current_exposure,
                'max_exposure': max_exposure,
                'exposure_percentage': exposure_percentage,
                'position_risk': position_risk,
                'var_95': var_95,
                'cvar_95': cvar_95,
                'current_drawdown': current_drawdown,
                'max_drawdown': max_drawdown,
                'risk_reward_ratio': risk_reward_ratio,
                'margin_utilization': margin_utilization,
                'leverage': leverage,
            }
            
            return jsonify({
                'data': metrics,
                'status': 'live'
            }), 200
            
        except Exception as e:
            log.warning(f"Risk analytics not available, using defaults: {e}")
            # Fallback to default values
            metrics = {
                'current_exposure': 0,
                'max_exposure': 0,
                'exposure_percentage': 0,
                'position_risk': 0,
                'var_95': 0,
                'cvar_95': 0,
                'current_drawdown': 0,
                'max_drawdown': 0,
                'risk_reward_ratio': 0,
                'margin_utilization': 0,
                'leverage': 1.0,
            }
            
            return jsonify({
                'data': metrics,
                'status': 'stale',
                'error': 'Risk analytics not available'
            }), 200
            
    except Exception as e:
        log.error(f"Error getting risk metrics: {e}")
        print(traceback.format_exc())
        return jsonify({
            'data': {
                'current_exposure': 0,
                'max_exposure': 0,
                'exposure_percentage': 0,
                'position_risk': 0,
                'var_95': 0,
                'cvar_95': 0,
                'current_drawdown': 0,
                'max_drawdown': 0,
                'risk_reward_ratio': 0,
                'margin_utilization': 0,
                'leverage': 1.0,
            },
            'status': 'error',
            'error': str(e)
        }), 500


@risk_bp.route('/api/risk/volatility/latest', methods=['GET'])
def get_risk_volatility_latest():
    """
    Get latest IV and RV values for all timeframes.
    
    Returns:
        JSON with {success, data: {iv: {value, timestamp}, rv: {1d: {...}, 7d: {...}, 30d: {...}}}}
    """
    try:
        from bot.volatility.delta_volatility_collector import get_collector
        
        # v6.0: Multi-symbol support
        symbol = request.args.get('symbol', 'BTCUSD')
        collector = get_collector(symbol=symbol)
        data = collector.get_latest_values()
        
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        print(f"❌ Volatility latest values error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {'iv': None, 'rv': {}}
        }), 500


@risk_bp.route('/api/risk/volatility/stats', methods=['GET'])
def get_risk_volatility_stats():
    """
    Get volatility statistics and safety status - SINGLE SOURCE OF TRUTH.
    Uses DeltaVolatilityCollector for all IV/RV data and config.yaml for thresholds.
    
    Returns:
        JSON with safety limits from config.yaml, current IV/RV values, and violation status
    """
    try:
        from bot.volatility.delta_volatility_collector import get_collector
        from config.loader import get_config
        
        # v6.0: Multi-symbol support
        symbol = request.args.get('symbol', 'BTCUSD')
        
        # Get latest IV/RV from DeltaVolatilityCollector (SINGLE SOURCE)
        collector = get_collector(symbol=symbol)
        latest = collector.get_latest_values()
        
        # Get safety limits from config.yaml (SINGLE SOURCE)
        cfg = get_config()
        max_iv = float(cfg.safety.volatility.max_iv)
        max_rv = float(cfg.safety.volatility.max_rv)
        max_spread = float(cfg.safety.volatility.max_spread)
        check_interval = getattr(cfg.safety.volatility, 'check_interval', 300)
        
        # Extract current values
        current_iv = latest['iv']['value'] if latest.get('iv') else 0
        current_rv = latest['rv'].get('1d', {}).get('value', 0) if latest.get('rv') else 0
        
        # Calculate spread
        iv_rv_spread = abs(current_iv - current_rv) if (current_iv > 0 and current_rv > 0) else 0
        
        # Check safety (same logic as Guardian)
        is_safe = True
        violation_reason = None
        
        if current_iv > max_iv:
            is_safe = False
            violation_reason = f"IV too high: {current_iv:.1f}% > {max_iv}%"
        elif current_rv > max_rv:
            is_safe = False
            violation_reason = f"RV too high: {current_rv:.1f}% > {max_rv}%"
        elif iv_rv_spread > max_spread:
            is_safe = False
            violation_reason = f"IV-RV spread too wide: {iv_rv_spread:.1f}% > {max_spread}%"
        
        return jsonify({
            'success': True,
            'data': {
                'current': {
                    'iv': current_iv,
                    'rv': current_rv,
                    'spread': iv_rv_spread
                },
                'limits': {
                    'max_iv': max_iv,
                    'max_rv': max_rv,
                    'max_spread': max_spread
                },
                'thresholds': {
                    'max_iv': max_iv,
                    'max_rv': max_rv,
                    'max_spread': max_spread,
                    'check_interval': check_interval
                },
                'latest': latest,  # Full data with all timeframes
                'safety': {
                    'is_safe': is_safe,
                    'status': 'Trading Allowed' if is_safe else 'Trading Blocked',
                    'violation_reason': violation_reason
                },
                'last_update': latest.get('iv', {}).get('timestamp') if latest.get('iv') else None,
                'data_source': 'delta_volatility_collector'
            }
        })
    except Exception as e:
        print(f"❌ Volatility stats error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        }), 500


@risk_bp.route('/api/risk/volatility/thresholds', methods=['POST'])
def update_volatility_thresholds():
    """
    Update volatility safety thresholds in config.yaml.
    
    Request body:
        {
            "max_iv": 55.0,
            "max_rv": 60.0,
            "max_spread": 15.0,
            "check_interval": 300
        }
    
    Returns:
        JSON with success status and updated values
    """
    try:
        import yaml
        from pathlib import Path
        
        data = request.get_json()
        
        # Validate input
        max_iv = float(data.get('max_iv', 0))
        max_rv = float(data.get('max_rv', 0))
        max_spread = float(data.get('max_spread', 0))
        check_interval = int(data.get('check_interval', 300))
        
        if max_iv <= 0 or max_rv <= 0:
            return jsonify({
                'success': False,
                'error': 'Invalid thresholds. IV and RV must be greater than 0.'
            }), 400
        
        # Load config.yaml
        config_file = Path(__file__).parent.parent.parent.parent / 'config.yaml'
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Update volatility thresholds
        if 'safety' not in config:
            config['safety'] = {}
        if 'volatility' not in config['safety']:
            config['safety']['volatility'] = {}
        
        config['safety']['volatility']['max_iv'] = max_iv
        config['safety']['volatility']['max_rv'] = max_rv
        config['safety']['volatility']['max_spread'] = max_spread
        config['safety']['volatility']['check_interval'] = check_interval
        
        # Write back to config.yaml
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        log.info(f"✅ Updated volatility thresholds: IV={max_iv}%, RV={max_rv}%, Spread={max_spread}%")
        
        return jsonify({
            'success': True,
            'message': 'Volatility thresholds updated successfully',
            'updated': {
                'max_iv': max_iv,
                'max_rv': max_rv,
                'max_spread': max_spread,
                'check_interval': check_interval
            }
        })
        
    except Exception as e:
        log.error(f"Failed to update volatility thresholds: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@risk_bp.route('/api/risk/volatility/btc-price', methods=['GET'])
def get_btc_live_price():
    """
    Get live BTC perpetual price from Delta Exchange.
    
    Returns:
        JSON with current BTC price, 24h change, volume, etc.
    """
    try:
        import requests
        
        api_base = "https://api.india.delta.exchange"
        ticker_url = f"{api_base}/v2/tickers/BTCUSD"
        
        response = requests.get(ticker_url, timeout=5)
        
        if response.status_code != 200:
            raise Exception(f"Delta API returned HTTP {response.status_code}")
        
        data = response.json()
        if 'result' not in data:
            raise Exception("Invalid response from Delta Exchange")
        
        ticker = data['result']
        
        return jsonify({
            'success': True,
            'data': {
                'symbol': ticker.get('symbol', 'BTCUSD'),
                'price': float(ticker.get('mark_price', 0)),
                'last_price': float(ticker.get('close', 0)),
                'open': float(ticker.get('open', 0)),
                'high': float(ticker.get('high', 0)),
                'low': float(ticker.get('low', 0)),
                'volume': float(ticker.get('volume', 0)),
                'turnover': float(ticker.get('turnover', 0)),
                'change_24h': float(ticker.get('price_change_24h', 0)),
                'change_24h_percent': float(ticker.get('price_change_24h_percent', 0)),
                'timestamp': ticker.get('timestamp')
            }
        })
    except Exception as e:
        print(f"❌ BTC price fetch error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        }), 500


@risk_bp.route('/api/volatility/signal', methods=['GET'])
def get_market_signal():
    """
    Get comprehensive market signal including volatility, regime, grid suitability, and position risk.
    Uses robust delta_volatility_collector for accurate IV/RV data.
    
    Query Parameters:
        symbol (optional): Symbol name (e.g., "BTCUSD", "ETHUSD"). Default: "BTCUSD"
    
    Returns:
        - Volatility Signal (NEUTRAL/IV_HIGH/IV_LOW)
        - Market Regime (LOW_VOL/NORMAL/HIGH_VOL/EXTREME)
        - Grid Suitability (Score 0-10 with rating)
        - Position Risk (Liq Distance, Margin, MTM)
        - Overall Risk Status
    """
    try:
        import json
        from bot.volatility.delta_volatility_collector import get_collector
        
        # v6.0: Get symbol from query parameter
        symbol = request.args.get('symbol', 'BTCUSD')
        
        # Get IV/RV data from robust collector (symbol-aware)
        collector = get_collector(symbol=symbol)
        latest = collector.get_latest_values()
        
        # Extract IV and RV values
        iv = latest.get('iv', {}).get('value') if latest.get('iv') else None
        rv_1d = latest.get('rv', {}).get('1d', {}).get('value') if latest.get('rv') else None
        
        # Use daily RV as primary
        rv = rv_1d
        spread = (iv - rv) if (iv and rv) else None
        
        # For calculations, use safe defaults (0 won't trigger any penalties)
        rv_for_calc = rv if rv else 0
        iv_for_calc = iv if iv else 0
        
        # Calculate Volatility Signal
        if iv and rv:
            if iv > rv * 1.1:
                vol_signal = "IV_HIGH"
                vol_color = "red"
            elif iv < rv * 0.9:
                vol_signal = "IV_LOW"
                vol_color = "yellow"
            else:
                vol_signal = "NEUTRAL"
                vol_color = "green"
        else:
            vol_signal = "NO_DATA"
            vol_color = "gray"
        
        # Calculate Market Regime
        if not rv:
            regime = "NO_DATA"
            regime_color = "gray"
            regime_risk = "UNKNOWN"
        elif rv_for_calc < 30:
            regime = "LOW_VOL"
            regime_color = "green"
            regime_risk = "LOW"
        elif rv_for_calc < 50:
            regime = "NORMAL"
            regime_color = "green"
            regime_risk = "LOW"
        elif rv_for_calc < 70:
            regime = "HIGH_VOL"
            regime_color = "yellow"
            regime_risk = "ELEVATED"
        else:
            regime = "EXTREME"
            regime_color = "red"
            regime_risk = "EXTREME"
        
        # Get Position Risk Data from Guardian Bot (filtered by symbol if multi-symbol)
        liq_distance = None
        margin_utilized = None
        total_pnl = 0
        num_positions = 0
        
        try:
            # PRIMARY: Fetch from Guardian health file (most accurate)
            guardian_health_file = BASE_DIR / '.guardian_health.json'
            if guardian_health_file.exists():
                with open(guardian_health_file, 'r') as f:
                    health_data = json.load(f)
                    
                    # Extract liquidation data
                    liq_data = health_data.get('liquidation', {})
                    
                    # Get margin utilization
                    margin_data = liq_data.get('margin', {})
                    margin_utilized = margin_data.get('utilization', None)
                    
                    # Get liquidation distance
                    distance_data = liq_data.get('distance', {})
                    liq_distance = distance_data.get('distance', None)
                    
                    # Get MTM
                    mtm_data = liq_data.get('mtm', {})
                    total_pnl = mtm_data.get('current_mtm_inr', 0)
                    
                    # Get position count
                    monitoring_data = health_data.get('monitoring', {})
                    num_positions = monitoring_data.get('position_count', 0)
                    
                    log.info(f"Guardian data loaded: Liq={liq_distance}%, Margin={margin_utilized}%, MTM=₹{total_pnl}, Positions={num_positions}")
        except Exception as e:
            log.warning(f"Error fetching Guardian/position data: {e}")
        
        # Calculate Grid Suitability Score (0-10)
        score = 10
        
        # Penalty for high volatility
        if rv_for_calc > 70:
            score -= 5
        elif rv_for_calc > 60:
            score -= 3
        elif rv_for_calc > 50:
            score -= 2
        elif rv_for_calc > 40:
            score -= 1
        
        # Penalty for IV-RV mismatch
        if iv and rv:
            abs_spread = abs(iv - rv)
            if abs_spread > 20:
                score -= 3
            elif abs_spread > 15:
                score -= 2
            elif abs_spread > 10:
                score -= 1
        
        # Penalty for high margin usage
        if margin_utilized and margin_utilized > 80:
            score -= 2
        elif margin_utilized and margin_utilized > 70:
            score -= 1
        
        # Penalty for close to liquidation
        if liq_distance and liq_distance < 20:
            score -= 3
        elif liq_distance and liq_distance < 30:
            score -= 2
        elif liq_distance and liq_distance < 40:
            score -= 1
        
        # Convert score to rating
        if score >= 9:
            suitability_rating = "EXCELLENT"
            suitability_color = "green"
        elif score >= 7:
            suitability_rating = "GOOD"
            suitability_color = "green"
        elif score >= 5:
            suitability_rating = "FAIR"
            suitability_color = "yellow"
        elif score >= 3:
            suitability_rating = "POOR"
            suitability_color = "red"
        else:
            suitability_rating = "HALT"
            suitability_color = "red"
        
        # Overall Risk Score (0-12)
        risk_score = 0
        
        if liq_distance and liq_distance < 20:
            risk_score += 3
        elif liq_distance and liq_distance < 30:
            risk_score += 2
        elif liq_distance and liq_distance < 40:
            risk_score += 1
        
        if margin_utilized and margin_utilized > 80:
            risk_score += 3
        elif margin_utilized and margin_utilized > 70:
            risk_score += 2
        elif margin_utilized and margin_utilized > 60:
            risk_score += 1
        
        if rv_for_calc > 70:
            risk_score += 3
        elif rv_for_calc > 60:
            risk_score += 2
        elif rv_for_calc > 50:
            risk_score += 1
        
        if total_pnl < -15000:
            risk_score += 3
        elif total_pnl < -10000:
            risk_score += 2
        elif total_pnl < -5000:
            risk_score += 1
        
        # Final status
        if risk_score >= 6:
            overall_risk_status = "EXTREME_DANGER"
            overall_color = "red"
        elif risk_score >= 4:
            overall_risk_status = "HIGH_RISK"
            overall_color = "orange"
        elif risk_score >= 2:
            overall_risk_status = "MODERATE"
            overall_color = "yellow"
        else:
            overall_risk_status = "LOW"
            overall_color = "green"
        
        return jsonify({
            'success': True,
            'data': {
                'volatility_signal': {
                    'value': vol_signal,
                    'color': vol_color,
                    'iv': iv,
                    'rv': rv,
                    'spread': spread
                },
                'market_regime': {
                    'value': regime,
                    'color': regime_color,
                    'risk': regime_risk,
                    'rv': rv_for_calc
                },
                'grid_suitability': {
                    'rating': suitability_rating,
                    'color': suitability_color,
                    'score': score,
                    'score_max': 10
                },
                'position_risk': {
                    'liquidation_distance': liq_distance,
                    'margin_utilized': margin_utilized,
                    'mtm': total_pnl,
                    'num_positions': num_positions
                },
                'overall_risk_status': {
                    'value': overall_risk_status,
                    'color': overall_color,
                    'score': risk_score
                },
                'last_update': latest.get('timestamp')
            }
        })
        
    except Exception as e:
        log.error(f"Market signal error: {e}")
        log.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        }), 500


# ============================================================================
# Volatility Route Aliases (for frontend compatibility)
# Frontend expects /api/volatility/* but we also support /api/risk/volatility/*
# ============================================================================

@risk_bp.route('/api/volatility/historical', methods=['GET'])
def get_volatility_historical_alias():
    """Alias for /api/risk/volatility/historical"""
    return get_risk_volatility_historical()


@risk_bp.route('/api/volatility/latest', methods=['GET'])
def get_volatility_latest_alias():
    """Alias for /api/risk/volatility/latest"""
    return get_risk_volatility_latest()


@risk_bp.route('/api/volatility/stats', methods=['GET'])
def get_volatility_stats_alias():
    """Alias for /api/risk/volatility/stats"""
    return get_risk_volatility_stats()


def get_risk_volatility_signal():
    """Get volatility trading signal (BUY/SELL/HOLD based on IV/RV)"""
    try:
        from bot.volatility.delta_volatility_collector import get_collector
        # v6.0: Multi-symbol support
        symbol = request.args.get('symbol', 'BTCUSD')
        collector = get_collector(symbol=symbol)
        latest = collector.get_latest_values()
        
        # Simple signal logic: High IV = potential reversal
        signal = "HOLD"
        if latest.get('iv') and latest['iv']['value'] > 40:
            signal = "SELL"  # High volatility, caution
        elif latest.get('iv') and latest['iv']['value'] < 20:
            signal = "BUY"   # Low volatility, opportunity
            
        return jsonify({
            'success': True,
            'signal': signal,
            'iv': latest.get('iv', {}).get('value'),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        log.error(f"Error getting volatility signal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def get_risk_volatility_btc_price():
    """Get current BTC price from Delta Exchange"""
    try:
        from bot.api.delta_client import DeltaClient
        client = DeltaClient()
        ticker = client.get_ticker('BTCUSD')
        
        return jsonify({
            'success': True,
            'price': ticker.get('close'),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        log.error(f"Error getting BTC price: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@risk_bp.route('/api/volatility/signal', methods=['GET'])
def get_volatility_signal_alias():
    """Alias for /api/risk/volatility/signal"""
    return get_risk_volatility_signal()


@risk_bp.route('/api/volatility/btc-price', methods=['GET'])
def get_btc_price_alias():
    """Alias for /api/risk/volatility/btc-price"""
    return get_risk_volatility_btc_price()
