"""
Multi-Symbol Support API

Provides symbol management endpoints for v5.0 multi-symbol configuration

Routes:
- GET /api/symbols - List all configured symbols
- GET /api/symbols/<symbol> - Get details for specific symbol

Date: December 28, 2025
"""

import logging
from pathlib import Path
from flask import Blueprint, jsonify, request

# Import YAML config helper
from config.loader import get_config

log = logging.getLogger(__name__)

# Create blueprint
symbols_bp = Blueprint('symbols', __name__)


@symbols_bp.route('/api/symbols', methods=['GET'])
def list_symbols():
    """
    List all configured symbols from config.yaml
    
    Returns both enabled and disabled symbols with their configuration.
    Frontend can filter by enabled status.
    
    Example Response:
    {
        "symbols": [
            {
                "name": "BTCUSD",
                "enabled": true,
                "product_id": 139,
                "mode": "LONG",
                "grid": {
                    "lower": 85000,
                    "upper": 95000,
                    "step": 500,
                    "reference": 88500
                },
                "limits": {
                    "max_open_positions": 50,
                    "lot_size": 5
                },
                "monitoring_file": "data/monitoring_snapshot_BTCUSD_LONG.json",
                "database_file": "data/bot_events_BTCUSD_LONG.db"
            },
            {
                "name": "ETHUSD",
                "enabled": false,
                "product_id": 3136,
                "mode": "LONG",
                ...
            }
        ],
        "config_version": "5.0",
        "total": 2,
        "enabled_count": 1
    }
    """
    try:
        config = get_config()
        
        # Check if v5.0 multi-symbol config
        if not config.symbols:
            return jsonify({
                'error': 'Multi-symbol not configured',
                'message': 'Config is v4.0 (single-symbol). Run migration script to upgrade.',
                'config_version': config.version,
                'symbols': []
            }), 200  # Not an error, just informational
        
        # Build symbol list
        symbols = []
        enabled_count = 0
        
        for symbol_name, symbol_config in config.symbols.items():
            symbol_info = {
                'name': symbol_name,
                'enabled': symbol_config.enabled,
                'product_id': symbol_config.product_id,
                'mode': symbol_config.mode,
                'grid': {
                    'lower': symbol_config.grid.geometry.lower,
                    'upper': symbol_config.grid.geometry.upper,
                    'step': symbol_config.grid.geometry.step,
                    'reference': symbol_config.grid.geometry.reference
                },
                'limits': {
                    'max_open_positions': symbol_config.grid.limits.max_open_positions,
                    'lot_size': symbol_config.grid.limits.lot_size,
                    'max_qty_per_order': symbol_config.grid.limits.max_qty_per_order
                },
                'safety': {
                    'max_account_loss_inr': symbol_config.safety.max_account_loss_inr,
                    'min_liquidation_distance_pct': symbol_config.safety.min_liquidation_distance_pct
                },
                'monitoring_file': f"data/monitoring_snapshot_{symbol_name}_{symbol_config.mode}.json",
                'database_file': f"data/bot_events_{symbol_name}_{symbol_config.mode}.db",
                'recovery_file': f"data/recovery/recovery_state_{symbol_name}_{symbol_config.mode}.json"
            }
            
            symbols.append(symbol_info)
            
            if symbol_config.enabled:
                enabled_count += 1
        
        return jsonify({
            'symbols': symbols,
            'config_version': config.version,
            'total': len(symbols),
            'enabled_count': enabled_count,
            'trading_mode': config.trading_mode
        })
        
    except Exception as e:
        log.error(f"Error listing symbols: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to list symbols',
            'message': str(e)
        }), 500


@symbols_bp.route('/api/symbols/<symbol_name>', methods=['GET'])
def get_symbol_details(symbol_name):
    """
    Get detailed configuration for a specific symbol
    
    Args:
        symbol_name: Symbol key (e.g., 'BTCUSD', 'ETHUSD')
    
    Example Response:
    {
        "name": "BTCUSD",
        "enabled": true,
        "product_id": 139,
        "mode": "LONG",
        "grid": { ... },
        "limits": { ... },
        "safety": { ... },
        "monitoring_file": "data/monitoring_snapshot_BTCUSD_LONG.json",
        "status": "active"  // or "disabled", "not_found"
    }
    """
    try:
        config = get_config()
        
        # Check if v5.0 multi-symbol config
        if not config.symbols:
            return jsonify({
                'error': 'Multi-symbol not configured',
                'message': 'Config is v4.0 (single-symbol)',
                'config_version': config.version
            }), 400
        
        # Check if symbol exists
        symbol_name = symbol_name.upper()
        if symbol_name not in config.symbols:
            available = list(config.symbols.keys())
            return jsonify({
                'error': 'Symbol not found',
                'message': f"Symbol '{symbol_name}' not configured",
                'available_symbols': available
            }), 404
        
        symbol_config = config.symbols[symbol_name]
        
        # Check monitoring file exists
        from pathlib import Path
        monitoring_file = Path(f"data/monitoring_snapshot_{symbol_name}_{symbol_config.mode}.json")
        monitoring_exists = monitoring_file.exists()
        
        # Determine status
        if not symbol_config.enabled:
            status = 'disabled'
        elif monitoring_exists:
            # Check if monitoring file is fresh (< 30s)
            import json
            from datetime import datetime
            try:
                with open(monitoring_file) as f:
                    data = json.load(f)
                timestamp = datetime.fromisoformat(data.get('timestamp', '2000-01-01'))
                age = (datetime.now() - timestamp).total_seconds()
                status = 'active' if age < 30 else 'stale'
            except:
                status = 'unknown'
        else:
            status = 'not_running'
        
        return jsonify({
            'name': symbol_name,
            'enabled': symbol_config.enabled,
            'product_id': symbol_config.product_id,
            'mode': symbol_config.mode,
            'grid': {
                'lower': symbol_config.grid.geometry.lower,
                'upper': symbol_config.grid.geometry.upper,
                'step': symbol_config.grid.geometry.step,
                'reference': symbol_config.grid.geometry.reference
            },
            'limits': {
                'max_open_positions': symbol_config.grid.limits.max_open_positions,
                'lot_size': symbol_config.grid.limits.lot_size,
                'max_qty_per_order': symbol_config.grid.limits.max_qty_per_order
            },
            'safety': {
                'max_account_loss_inr': symbol_config.safety.max_account_loss_inr,
                'min_liquidation_distance_pct': symbol_config.safety.min_liquidation_distance_pct
            },
            'monitoring_file': str(monitoring_file),
            'monitoring_exists': monitoring_exists,
            'database_file': f"data/bot_events_{symbol_name}_{symbol_config.mode}.db",
            'recovery_file': f"data/recovery/recovery_state_{symbol_name}_{symbol_config.mode}.json",
            'status': status,
            'config_version': config.version
        })
        
    except Exception as e:
        log.error(f"Error getting symbol details: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to get symbol details',
            'message': str(e)
        }), 500
