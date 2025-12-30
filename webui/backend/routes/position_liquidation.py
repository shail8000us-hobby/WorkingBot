"""
Position & Liquidation Metrics API
===================================

Exposes comprehensive position and liquidation data from PositionMonitor
including the new Delta Exchange India improvements:
- Multi-position minimum liquidation distance
- Bankruptcy distance tracking
- Detailed per-position liquidation info
- Critical/Warning flags

Author: Senior Developer
Date: December 28, 2025
"""

import logging
import sys
from pathlib import Path
from flask import Blueprint, jsonify

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.loader import get_config

log = logging.getLogger(__name__)

# Create blueprint
position_liquidation_bp = Blueprint('position_liquidation', __name__)

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent.parent

# Global reference to Guardian bot instance
_guardian_bot = None


def set_guardian_bot(guardian_bot):
    """
    Set reference to Guardian bot instance
    
    Called by app.py during startup
    
    Args:
        guardian_bot: GuardianBot instance
    """
    global _guardian_bot
    _guardian_bot = guardian_bot
    log.info("Guardian bot reference set in position_liquidation routes")


@position_liquidation_bp.route('/api/positions/liquidation-metrics', methods=['GET'])
def get_liquidation_metrics():
    """
    Get comprehensive liquidation metrics from Guardian health file
    
    Returns all new Delta Exchange India improvements:
    - liquidation_distance: Minimum across all positions
    - liquidation_details: Per-position breakdown
    - liquidation_critical: Boolean (< 1%)
    - liquidation_warning: Boolean (< 5%)
    - bankruptcy_distance: Minimum bankruptcy distance
    
    Example Response:
    {
        "success": true,
        "timestamp": "2025-12-28T10:30:00",
        "current_price": 80000.0,
        "liquidation_distance": 5.2,
        "bankruptcy_distance": 6.1,
        "liquidation_critical": false,
        "liquidation_warning": true,
        "liquidation_details": [
            {
                "symbol": "BTC/USD:USD",
                "side": "LONG",
                "size": 100,
                "entry_price": 78500.0,
                "current_price": 80000.0,
                "liquidation_price": 76000.0,
                "bankruptcy_price": 75500.0,
                "liquidation_distance_pct": 5.0,
                "bankruptcy_distance_pct": 5.625,
                "margin": 800.0,
                "is_critical": false,
                "is_warning": true
            }
        ],
        "positions_count": 1
    }
    """
    try:
        # Read liquidation metrics from Guardian health file
        import json
        from datetime import datetime
        
        health_file = BASE_DIR / '.guardian_health'
        
        if not health_file.exists():
            return jsonify({
                'success': False,
                'error': 'Guardian health file not found',
                'message': 'Start Guardian bot to enable position monitoring'
            }), 503
        
        # Load health data
        try:
            with open(health_file, 'r') as f:
                health_data = json.load(f)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': 'Failed to read Guardian health file',
                'message': str(e)
            }), 500
        
        # Extract liquidation and position metrics
        positions = health_data.get('positions', {})
        liquidation = health_data.get('liquidation', {})
        
        if not liquidation:
            return jsonify({
                'success': False,
                'error': 'No liquidation data available',
                'message': 'Guardian has not yet collected position data'
            }), 503
        
        # Build response with all metrics from health file
        response = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'guardian_version': health_data.get('guardian_version', 'Unknown'),
            'current_price': positions.get('current_price'),
            
            # Primary liquidation metrics
            'liquidation_distance': liquidation.get('distance', 100.0),
            'liquidation_critical': liquidation.get('critical', False),
            'liquidation_warning': liquidation.get('warning', False),
            
            # Bankruptcy distance (additional safety layer)
            'bankruptcy_distance': liquidation.get('bankruptcy_distance', 100.0),
            
            # Position summary
            'positions_count': positions.get('count', 0),
            'total_pnl_inr': positions.get('total_pnl_inr', 0),
            
            # Note: Detailed per-position breakdown requires direct PositionMonitor access
            # (not stored in health file to keep it small)
            'liquidation_details_available': liquidation.get('details_count', 0) > 0,
            'liquidation_details_count': liquidation.get('details_count', 0),
            
            # Risk zones
            'risk_zone': _calculate_risk_zone(
                liquidation.get('distance', 100.0),
                liquidation.get('critical', False),
                liquidation.get('warning', False)
            )
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        log.error(f"Error fetching liquidation metrics: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Internal server error'
        }), 500


@position_liquidation_bp.route('/api/positions/monitor-cycle', methods=['GET'])
def get_monitor_cycle():
    """
    Get full monitor_cycle output from PositionMonitor
    
    Returns limited monitoring data from Guardian health file:
    - Guardian status
    - Position count  
    - Current price
    - Total PnL
    - Liquidation metrics (distance, critical, warning flags)
    
    Note: For full position details, Guardian must expose them to health file
    or WebUI needs direct database access.
    """
    try:
        import json
        from datetime import datetime
        
        health_file = BASE_DIR / '.guardian_health'
        
        if not health_file.exists():
            return jsonify({
                'success': False,
                'error': 'Guardian health file not found'
            }), 503
        
        # Load health data
        try:
            with open(health_file, 'r') as f:
                health_data = json.load(f)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to read Guardian health file: {e}'
            }), 500
        
        # Build monitor_cycle compatible response from health data
        response = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'guardian_version': health_data.get('guardian_version'),
            'signal': health_data.get('signal'),
            'reason': health_data.get('reason'),
            
            # Position data
            'positions_count': health_data.get('positions', {}).get('count', 0),
            'current_price': health_data.get('positions', {}).get('current_price'),
            'total_pnl_inr': health_data.get('positions', {}).get('total_pnl_inr', 0),
            
            # Liquidation metrics (Delta Exchange India improvements)
            'liquidation_distance': health_data.get('liquidation', {}).get('distance', 100.0),
            'liquidation_critical': health_data.get('liquidation', {}).get('critical', False),
            'liquidation_warning': health_data.get('liquidation', {}).get('warning', False),
            'bankruptcy_distance': health_data.get('liquidation', {}).get('bankruptcy_distance', 100.0),
            'liquidation_details_count': health_data.get('liquidation', {}).get('details_count', 0),
            
            # Note: Full position details not available via health file
            # Health file is lightweight for quick status checks
            'note': 'Full position details require direct Guardian access or database query'
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        log.error(f"Error in monitor_cycle: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _calculate_risk_zone(liquidation_distance, is_critical, is_warning):
    """
    Calculate risk zone based on liquidation distance
    
    Args:
        liquidation_distance: Distance to liquidation in %
        is_critical: Boolean, distance < 1%
        is_warning: Boolean, distance < 5%
    
    Returns:
        str: 'CRITICAL', 'WARNING', 'CAUTION', or 'SAFE'
    """
    if is_critical or liquidation_distance < 1.0:
        return 'CRITICAL'
    elif is_warning or liquidation_distance < 5.0:
        return 'WARNING'
    elif liquidation_distance < 10.0:
        return 'CAUTION'
    else:
        return 'SAFE'


# Import datetime at top
from datetime import datetime
