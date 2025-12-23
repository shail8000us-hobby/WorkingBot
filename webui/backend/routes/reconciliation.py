"""
Reconciliation system API endpoints - Standalone Reconciliation Engine.
Reads from reconciliation state and action queue files.
Created: November 20, 2025
"""

from flask import Blueprint, jsonify, request
import json
from pathlib import Path
import time

bp = Blueprint('reconciliation', __name__, url_prefix='/api/reconciliation')

# State files
RECONCILIATION_STATE_FILE = Path("data/reconciliation/state.json")
ACTION_QUEUE_FILE = Path("data/reconciliation/action_queue.json")


def load_reconciliation_state():
    """Load reconciliation state from file"""
    try:
        if RECONCILIATION_STATE_FILE.exists():
            with open(RECONCILIATION_STATE_FILE) as f:
                return json.load(f)
    except:
        pass
    
    return {
        'last_check_time': None,
        'checks_performed': 0,
        'discrepancies_found': 0,
        'actions_generated': 0,
        'status': 'not_running'
    }


def load_action_queue():
    """Load action queue from file"""
    try:
        if ACTION_QUEUE_FILE.exists():
            with open(ACTION_QUEUE_FILE) as f:
                data = json.load(f)
                return data.get('actions', [])
    except:
        pass
    
    return []


@bp.route('/status', methods=['GET'])
def get_reconciliation_status():
    """Get reconciliation engine status"""
    try:
        state = load_reconciliation_state()
        actions = load_action_queue()
        
        # Calculate statistics
        pending_actions = [a for a in actions if a.get('status') == 'pending']
        completed_actions = [a for a in actions if a.get('status') == 'completed']
        failed_actions = [a for a in actions if a.get('status') == 'failed']
        
        # Check if engine is running (last check within 10 minutes)
        last_check = state.get('last_check_time')
        is_running = False
        if last_check:
            time_since_check = time.time() - last_check
            is_running = time_since_check < 600  # 10 minutes
        
        return jsonify({
            'success': True,
            'available': True,
            'engine_running': is_running,
            'last_check': last_check,
            'checks_performed': state.get('checks_performed', 0),
            'discrepancies_found': state.get('discrepancies_found', 0),
            'actions_generated': state.get('actions_generated', 0),
            'status': state.get('status', 'unknown'),
            'action_queue': {
                'total': len(actions),
                'pending': len(pending_actions),
                'completed': len(completed_actions),
                'failed': len(failed_actions)
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'available': False
        }), 500


@bp.route('/actions', methods=['GET'])
def get_actions():
    """Get action queue"""
    try:
        actions = load_action_queue()
        
        # Filter by status if requested
        status_filter = request.args.get('status')
        if status_filter:
            actions = [a for a in actions if a.get('status') == status_filter]
        
        # Limit results
        limit = request.args.get('limit', 50, type=int)
        actions = actions[-limit:]  # Get most recent
        
        return jsonify({
            'success': True,
            'actions': actions,
            'count': len(actions)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/clear-completed', methods=['POST'])
def clear_completed_actions():
    """Clear completed actions from queue"""
    try:
        if not ACTION_QUEUE_FILE.exists():
            return jsonify({'success': True, 'message': 'No action queue found'})
        
        # Load current queue
        with open(ACTION_QUEUE_FILE) as f:
            data = json.load(f)
            actions = data.get('actions', [])
        
        # Keep only pending and failed actions
        filtered_actions = [a for a in actions if a.get('status') in ['pending', 'failed']]
        
        # Write back
        data['actions'] = filtered_actions
        data['updated_at'] = time.time()
        
        temp_file = ACTION_QUEUE_FILE.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        temp_file.replace(ACTION_QUEUE_FILE)
        
        removed_count = len(actions) - len(filtered_actions)
        
        return jsonify({
            'success': True,
            'message': f'Cleared {removed_count} completed action(s)',
            'removed': removed_count,
            'remaining': len(filtered_actions)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/history', methods=['GET'])
def get_reconciliation_history():
    """Get recent reconciliation history"""
    try:
        state = load_reconciliation_state()
        
        return jsonify({
            'success': True,
            'history': {
                'last_check': state.get('last_check_time'),
                'total_checks': state.get('checks_performed', 0),
                'total_discrepancies': state.get('discrepancies_found', 0),
                'total_actions': state.get('actions_generated', 0),
                'last_discrepancies': state.get('last_discrepancies', 0),
                'last_actions': state.get('last_actions', 0)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
