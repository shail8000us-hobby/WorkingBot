"""
Recovery system API endpoints - Standalone Recovery System.
Reads from recovery_state.json file.
Created: November 20, 2025
"""

from flask import Blueprint, jsonify, request
import json
from pathlib import Path
import time

bp = Blueprint('recovery', __name__, url_prefix='/api/recovery')

# State file path
RECOVERY_STATE_FILE = Path("data/recovery/recovery_state.json")


def load_recovery_state():
    """Load recovery state from file"""
    try:
        if RECOVERY_STATE_FILE.exists():
            with open(RECOVERY_STATE_FILE) as f:
                return json.load(f)
    except:
        pass
    
    return {
        'recovery_active': False,
        'recovered_grids': [],
        'timestamp': None,
        'last_recovery': None
    }


@bp.route('/health', methods=['GET'])
def get_recovery_health():
    """Get recovery system health status"""
    try:
        state = load_recovery_state()
        
        return jsonify({
            'success': True,
            'available': True,
            'health': {
                'status': 'active' if state.get('recovery_active') else 'idle',
                'last_recovery': state.get('last_recovery'),
                'recovered_grids_count': len(state.get('recovered_grids', []))
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'available': False
        }), 500


@bp.route('/combined-status', methods=['GET'])
def get_combined_status():
    """Get combined monitoring and recovery status"""
    try:
        state = load_recovery_state()
        
        return jsonify({
            'success': True,
            'monitoring': {
                'available': True,
                'status': 'operational'
            },
            'recovery': {
                'available': True,
                'active': state.get('recovery_active', False),
                'recovered_grids': state.get('recovered_grids', []),
                'last_recovery': state.get('last_recovery'),
                'timestamp': state.get('timestamp')
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/history', methods=['GET'])
def get_recovery_history():
    """Get recent recovery sessions"""
    try:
        state = load_recovery_state()
        
        sessions = []
        if state.get('last_recovery'):
            sessions.append({
                'session_id': 'latest',
                'timestamp': state.get('last_recovery'),
                'recovered_count': len(state.get('recovered_grids', [])),
                'grids': state.get('recovered_grids', []),
                'status': 'completed'
            })
        
        return jsonify({
            'success': True,
            'sessions': sessions
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/clear-state', methods=['POST'])
def clear_recovery_state():
    """Clear recovery state"""
    try:
        if RECOVERY_STATE_FILE.exists():
            RECOVERY_STATE_FILE.unlink()
        
        return jsonify({'success': True, 'message': 'Recovery state cleared'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/enable/<engine>', methods=['POST'])
def enable_recovery_engine(engine):
    """Enable a recovery engine (not applicable for standalone system)"""
    return jsonify({
        'success': False,
        'message': 'Recovery system is standalone. Run: python3 -m bot.strategy.recovery.recovery_runner'
    }), 400


@bp.route('/disable/<engine>', methods=['POST'])
def disable_recovery_engine(engine):
    """Disable a recovery engine (not applicable for standalone system)"""
    return jsonify({
        'success': False,
        'message': 'Recovery system is standalone. Cannot disable from WebUI.'
    }), 400
