"""
Capital Protection API Blueprint
Handles all /api/capital/* routes for equity floor, drawdown, exposure, and budget management
"""

from flask import Blueprint, request, jsonify
import os
import json
import re
import tempfile
from pathlib import Path
import logging

capital_bp = Blueprint('capital', __name__)
log = logging.getLogger(__name__)

# Config file path
BASE_DIR = Path(__file__).parent.parent.parent.parent
CONFIG_FILE = BASE_DIR / "config.yaml"

# Import YAML config loader
from config.loader import get_config, reload_config
import yaml

# Helper function to get config values using dot notation
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


def _atomic_write_text(filepath, content):
    """Atomically write text content to a file"""
    filepath = Path(filepath)
    temp_file = None
    try:
        # Write to temp file first
        with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=filepath.parent) as f:
            temp_file = f.name
            f.write(content)
        # Atomically replace original file
        os.replace(temp_file, str(filepath))
        log.info(f"Atomically wrote {len(content)} bytes to {filepath}")
    except Exception as e:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
        raise e


@capital_bp.route('/api/capital/equity-floor/status', methods=['GET'])
def get_equity_floor_status():
    """Get equity floor status"""
    try:
        # Get floor config from YAML with fallback
        floor_inr = float(get_config_value(
            'capital_protection.equity_floor.floor_inr',
            'EQUITY_FLOOR_INR',
            0
        ))
        enabled = get_config_value(
            'capital_protection.equity_floor.enabled',
            'EQUITY_FLOOR_INR',  # enabled if > 0 in env
            floor_inr > 0
        )
        
        # Fetch current equity from Guardian health file
        current_equity = 0
        guardian_health_file = BASE_DIR / '.guardian_health'
        
        if guardian_health_file.exists():
            try:
                with open(guardian_health_file, 'r') as f:
                    health_data = json.load(f)
                    # Get total balance from liquidation margin data
                    current_equity = health_data.get('liquidation', {}).get('margin', {}).get('total_balance', 0)
            except Exception as e:
                log.warning(f"Failed to read Guardian health file: {e}")
        
        # Check breach flag
        breach_flag = BASE_DIR / '.equity_floor_breach'
        breach_flag_exists = breach_flag.exists()
        
        # Auto-clear breach flag if equity recovered above floor
        if breach_flag_exists and current_equity >= floor_inr:
            try:
                breach_flag.unlink()
                breach_flag_exists = False
                log.info(f"✅ Auto-cleared equity floor breach flag (equity ₹{current_equity:,.0f} > floor ₹{floor_inr:,})")
            except Exception as e:
                log.warning(f"Failed to clear breach flag: {e}")
        
        # Calculate buffer
        buffer_inr = max(0, current_equity - floor_inr) if current_equity > 0 else 0
        
        return jsonify({
            'success': True,
            'data': {
                'enabled': enabled,
                'floor_inr': floor_inr,
                'current_equity': current_equity,
                'buffer_inr': buffer_inr,
                'breached': breach_flag_exists,
                'check_interval_sec': int(get_config_value(
                    'capital_protection.equity_floor.check_interval',
                    'EQUITY_FLOOR_CHECK_INTERVAL',
                    60
                )),
                'require_ack': get_config_value(
                    'capital_protection.equity_floor.require_acknowledgment',
                    'EQUITY_FLOOR_REQUIRE_ACK',
                    True
                )
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@capital_bp.route('/api/capital/drawdown/status', methods=['GET'])
def get_drawdown_status():
    """Get drawdown cap status"""
    try:
        from bot.capital.equity_tracker import get_equity_tracker
        
        tracker = get_equity_tracker(BASE_DIR)
        stats = tracker.get_stats()
        
        # Override current_equity with real-time data from Guardian health file
        guardian_health_file = BASE_DIR / '.guardian_health'
        if guardian_health_file.exists():
            try:
                with open(guardian_health_file, 'r') as f:
                    health_data = json.load(f)
                    # Get total balance from liquidation margin data
                    current_equity_realtime = health_data.get('liquidation', {}).get('margin', {}).get('total_balance', 0)
                    
                    if current_equity_realtime > 0:
                        # Recalculate drawdown with real-time equity
                        peak_equity = stats.get('peak_equity', 0)
                        if peak_equity > 0:
                            drawdown_inr = max(0, peak_equity - current_equity_realtime)
                            drawdown_pct = (drawdown_inr / peak_equity) * 100
                            utilization_pct = (drawdown_pct / stats['max_drawdown_pct'] * 100) if stats['max_drawdown_pct'] > 0 else 0
                            
                            # Update stats with real-time data
                            stats['current_equity'] = current_equity_realtime
                            stats['current_drawdown_inr'] = drawdown_inr
                            stats['current_drawdown_pct'] = drawdown_pct
                            stats['utilization_pct'] = utilization_pct
                            
                            # Recalculate protective mode status based on real-time equity
                            max_drawdown = stats['max_drawdown_pct']
                            hysteresis = stats.get('hysteresis_pct', 15)
                            
                            if drawdown_pct >= max_drawdown:
                                stats['protective_mode'] = True
                            elif drawdown_pct < hysteresis:
                                stats['protective_mode'] = False
                            # else: keep current protective_mode state (in hysteresis zone)
                            
                            log.debug(f"Drawdown status: real-time equity ₹{current_equity_realtime:,.0f}, drawdown {drawdown_pct:.1f}%, protective: {stats['protective_mode']}")
            except Exception as e:
                log.warning(f"Failed to read Guardian health file for drawdown: {e}")
        
        # Add config values that aren't in stats
        stats['window_days'] = int(get_config_value('capital_protection.drawdown_cap.window_days', 'DRAWDOWN_WINDOW_DAYS', 30))
        stats['check_interval_sec'] = int(get_config_value('capital_protection.drawdown_cap.check_interval', 'DRAWDOWN_CHECK_INTERVAL', 300))
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {
                'enabled': False,
                'protective_mode': False,
                'peak_equity': 0,
                'current_equity': 0,
                'current_drawdown_pct': 0,
                'current_drawdown_inr': 0,
                'max_drawdown_pct': 20,
                'hysteresis_pct': 15,
                'snapshot_count': 0,
                'window_days': 30,
                'check_interval_sec': 300,
                'utilization_pct': 0
            }
        })


@capital_bp.route('/api/capital/exposure/status', methods=['GET'])
def get_exposure_status():
    """Get exposure growth limiter status"""
    try:
        from bot.safety.exposure_limiter import get_exposure_limiter, reload_exposure_limiter
        
        # Reload limiter to pick up latest configuration
        reload_exposure_limiter()
        limiter = get_exposure_limiter()
        stats = limiter.get_stats()
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {
                'enabled': False,
                'max_tranches_per_minute': 2,
                'max_notional_per_minute': 300000,
                'queue_enabled': True,
                'current_window': {
                    'tranches': 0,
                    'notional_inr': 0,
                    'utilization_pct': 0
                },
                'queue_depth': 0,
                'total_checks': 0,
                'total_blocks': 0,
                'total_queued': 0
            }
        })


@capital_bp.route('/api/capital/budget/status', methods=['GET'])
def get_budget_status():
    """Get pending order budget status"""
    try:
        max_pending = float(get_config_value('capital_protection.pending_budget.max_notional_inr', 'MAX_PENDING_NOTIONAL_INR', 500000))
        buffer_pct = float(get_config_value('capital_protection.pending_budget.buffer_pct', 'PENDING_BUDGET_BUFFER_PCT', 10))
        
        # Try to fetch real orders, but fallback gracefully
        total_pending = 0
        pending_buy_orders = []
        
        try:
            from bot.api.exchange_ops import get_exchange_ops
            exchange_ops = get_exchange_ops()
            open_orders = exchange_ops.fetch_open_orders()
            pending_buy_orders = [o for o in open_orders if o.get('side') == 'buy' and not o.get('reduceOnly')]
            total_pending = sum(float(o.get('price', 0)) * float(o.get('amount', 0)) for o in pending_buy_orders)
        except Exception as fetch_error:
            # Fallback: return default values if can't fetch from exchange
            log.warning(f"Could not fetch orders from exchange: {fetch_error}")
        
        utilization_pct = (total_pending / max_pending * 100) if max_pending > 0 else 0
        budget_exceeded = total_pending >= max_pending if max_pending > 0 else False
        
        return jsonify({
            'success': True,
            'data': {
                'enabled': max_pending > 0,
                'current_pending': total_pending,
                'max_budget': max_pending,  # Frontend expects 'max_budget'
                'max_pending': max_pending,  # Keep for backward compatibility
                'utilization_pct': utilization_pct,
                'open_orders': len(pending_buy_orders),  # Frontend expects 'open_orders'
                'pending_orders_count': len(pending_buy_orders),  # Keep for backward compatibility
                'budget_exceeded': budget_exceeded,  # Add budget_exceeded flag
                'buffer_pct': buffer_pct,
                'alert_threshold': max_pending * (1 - buffer_pct / 100)
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {
                'enabled': False,
                'current_pending': 0,
                'max_pending': 500000,
                'utilization_pct': 0,
                'pending_orders_count': 0,
                'buffer_pct': 10,
                'alert_threshold': 450000
            }
        })


@capital_bp.route('/api/capital/config-guard/status', methods=['GET'])
def get_config_guard_status():
    """Get Two-Man Rule config guard status"""
    try:
        from bot.safety.config_guard import get_config_guard
        
        guard = get_config_guard(BASE_DIR)
        stats = guard.get_stats()
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {
                'enabled': False,
                'has_pending_change': False,
                'timeout_sec': 600,
                'auto_revert': True,
                'pending_change': None
            }
        })


@capital_bp.route('/api/capital/update-config', methods=['POST'])
def update_capital_config():
    """Update capital protection configuration in config.yaml"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Check if this is a confirmed request
        confirmed = data.get('confirmed', False)
        
        # ALWAYS require confirmation unless explicitly confirmed
        if not confirmed:
            # Build a simple changes summary
            changes_summary = {
                'total_changes': len([k for k in data.keys() if k != 'confirmed']),
                'changes': [{'parameter': k, 'new_value': v} for k, v in data.items() if k != 'confirmed'],
                'has_errors': False,
                'requires_confirmation': False,
                'critical_changes': [],
                'impact_summary': {},
                'warnings': []
            }
            
            log.warning(f"Capital protection config save requires confirmation. Changes: {changes_summary['total_changes']}")
            return jsonify({
                'success': False,
                'require_confirmation': True,
                'changes_summary': changes_summary,
                'message': 'Please review and confirm your configuration changes'
            }), 200  # 200 OK but requires confirmation
        
        # Remove 'confirmed' from data before processing
        data_to_save = {k: v for k, v in data.items() if k != 'confirmed'}
        
        # Read current config file
        with open(CONFIG_FILE, 'r') as f:
            config_content = f.read()
        
        # Update each provided setting
        updated_count = 0
        for key, value in data_to_save.items():
            # Convert frontend keys to backend keys if needed
            key_mapping = {
                # Equity Floor
                'equity_floor': 'EQUITY_FLOOR_INR',
                'equity_floor_check_interval': 'EQUITY_FLOOR_CHECK_INTERVAL',
                'equity_floor_require_ack': 'EQUITY_FLOOR_REQUIRE_ACK',
                # Drawdown Cap
                'drawdown_max_pct': 'DRAWDOWN_MAX_PCT',
                'drawdown_window_days': 'DRAWDOWN_WINDOW_DAYS',
                'drawdown_hysteresis_pct': 'DRAWDOWN_HYSTERESIS_PCT',
                'drawdown_check_interval': 'DRAWDOWN_CHECK_INTERVAL',
                # Exposure Growth
                'max_tranches_per_minute': 'MAX_NEW_TRANCHES_PER_MINUTE',
                'max_notional_per_minute': 'MAX_NOTIONAL_INR_PER_MINUTE',
                # Pending Budget
                'max_pending_budget': 'MAX_PENDING_NOTIONAL_INR',
                'pending_budget_buffer_pct': 'PENDING_BUDGET_BUFFER_PCT',
                # Two-Man Rule
                'two_man_rule_timeout': 'TWO_MAN_RULE_TIMEOUT_SEC',
            }
            
            config_key = key_mapping.get(key, key.upper())
            
            # Convert boolean values to lowercase strings for config file
            if isinstance(value, bool):
                value = 'true' if value else 'false'
            
            # Find and replace the line with this key
            pattern = rf'^({config_key}\s*=\s*)(.+?)(\s*#.*)?$'
            replacement = rf'\g<1>{value}\3'
            
            new_content, count = re.subn(pattern, replacement, config_content, flags=re.MULTILINE)
            if count > 0:
                config_content = new_content
                updated_count += count
        
        if updated_count == 0:
            return jsonify({
                'success': False,
                'error': 'No matching configuration keys found'
            }), 400
        
        # Write updated config back atomically
        _atomic_write_text(CONFIG_FILE, config_content)
        
        return jsonify({
            'success': True,
            'message': f'✅ Configuration changes applied successfully! Updated {updated_count} parameter(s).',
            'updated_count': updated_count
        })
        
    except Exception as e:
        log.error(f"Failed to update capital config: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
