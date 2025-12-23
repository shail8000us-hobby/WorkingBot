"""
Error Intelligence System - Backend API Integration
Provides REST and WebSocket endpoints for error management.
"""

from flask import Blueprint, request, jsonify
from flask_socketio import emit
from typing import Optional
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from bot.observability.errors import (
    ErrorEvent, ErrorSeverity, ErrorStatus, ErrorSource,
    ErrorCollector, ErrorClassifier, ErrorRemediator
)
from bot.observability.errors.store import ErrorStore
from bot.observability.errors.catalog import ErrorCatalog

# Create blueprint
errors_bp = Blueprint('errors', __name__, url_prefix='/api/errors')

# Global instances (initialized by manager)
error_store: Optional[ErrorStore] = None
error_classifier: Optional[ErrorClassifier] = None
error_remediator: Optional[ErrorRemediator] = None
socketio_instance = None


def init_error_api(store: ErrorStore, classifier: ErrorClassifier, remediator: ErrorRemediator, socketio=None):
    """Initialize the error API with required instances"""
    global error_store, error_classifier, error_remediator, socketio_instance
    error_store = store
    error_classifier = classifier
    error_remediator = remediator
    socketio_instance = socketio


# ========== REST Endpoints ==========

@errors_bp.route('/', methods=['GET'])
def get_errors():
    """
    Get errors with filters
    Query params:
        - status: open|acknowledged|in_progress|resolved|ignored
        - severity: critical|high|medium|low
        - source: trading|guardian|health|system
        - limit: int (default 100)
        - offset: int (default 0)
    """
    try:
        # Parse filters
        status = request.args.get('status')
        severity = request.args.get('severity')
        source = request.args.get('source')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        # Convert to enums if provided
        status_enum = ErrorStatus(status) if status else None
        severity_enum = ErrorSeverity(severity) if severity else None
        source_enum = ErrorSource(source) if source else None
        
        # Get errors
        errors = error_store.get_all(
            status=status_enum,
            severity=severity_enum,
            source=source_enum,
            limit=limit,
            offset=offset
        )
        
        # Convert to dicts
        errors_data = [error.to_dict() for error in errors]
        
        return jsonify({
            'success': True,
            'errors': errors_data,
            'count': len(errors_data),
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@errors_bp.route('/<error_id>', methods=['GET'])
def get_error(error_id: str):
    """Get a specific error by ID"""
    try:
        error = error_store.get_by_id(error_id)
        
        if not error:
            return jsonify({
                'success': False,
                'error': 'Error not found'
            }), 404
        
        return jsonify({
            'success': True,
            'error': error.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@errors_bp.route('/acknowledge', methods=['POST'])
def acknowledge_error():
    """
    Acknowledge an error
    Body: {"error_id": "...", "user": "..."}
    """
    try:
        data = request.json
        error_id = data.get('error_id')
        user = data.get('user', 'unknown')
        
        if not error_id:
            return jsonify({
                'success': False,
                'error': 'error_id required'
            }), 400
        
        # Update status
        success = error_store.update_status(
            error_id,
            ErrorStatus.ACKNOWLEDGED,
            user=user
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Error not found or update failed'
            }), 404
        
        # Log action
        error_store.log_action(
            error_id,
            'acknowledge',
            user=user,
            result='success'
        )
        
        # Notify via WebSocket
        if socketio_instance:
            error = error_store.get_by_id(error_id)
            socketio_instance.emit('error_updated', error.to_dict(), namespace='/')
        
        return jsonify({
            'success': True,
            'message': 'Error acknowledged'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@errors_bp.route('/resolve', methods=['POST'])
def resolve_error():
    """
    Resolve an error
    Body: {"error_id": "...", "user": "...", "notes": "..."}
    """
    try:
        data = request.json
        error_id = data.get('error_id')
        user = data.get('user', 'unknown')
        notes = data.get('notes', '')
        
        if not error_id:
            return jsonify({
                'success': False,
                'error': 'error_id required'
            }), 400
        
        # Update status
        success = error_store.update_status(
            error_id,
            ErrorStatus.RESOLVED,
            user=user,
            notes=notes
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Error not found or update failed'
            }), 404
        
        # Log action
        error_store.log_action(
            error_id,
            'resolve',
            user=user,
            details={'notes': notes},
            result='success'
        )
        
        # Notify via WebSocket
        if socketio_instance:
            error = error_store.get_by_id(error_id)
            socketio_instance.emit('error_updated', error.to_dict(), namespace='/')
        
        return jsonify({
            'success': True,
            'message': 'Error resolved'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@errors_bp.route('/run_fix', methods=['POST'])
def run_fix():
    """
    Execute a remediation action
    Body: {"error_id": "...", "fix_id": "...", "dry_run": true|false, "user": "..."}
    """
    try:
        data = request.json
        error_id = data.get('error_id')
        fix_id = data.get('fix_id')
        dry_run = data.get('dry_run', True)
        user = data.get('user', 'unknown')
        
        if not error_id or not fix_id:
            return jsonify({
                'success': False,
                'error': 'error_id and fix_id required'
            }), 400
        
        # Get the error
        error = error_store.get_by_id(error_id)
        if not error:
            return jsonify({
                'success': False,
                'error': 'Error not found'
            }), 404
        
        # Update status to in_progress if not dry run
        if not dry_run:
            error_store.update_status(error_id, ErrorStatus.IN_PROGRESS, user=user)
        
        # Execute the fix
        result = error_remediator.execute_fix(
            error,
            fix_id,
            dry_run=dry_run,
            user=user
        )
        
        # Log the action
        error_store.log_action(
            error_id,
            'run_fix' if not dry_run else 'dry_run_fix',
            user=user,
            details={
                'fix_id': fix_id,
                'dry_run': dry_run,
                **result.details
            },
            result='success' if result.success else 'failed'
        )
        
        # If successful and not dry run, mark as resolved
        if result.success and not dry_run:
            error_store.update_status(
                error_id,
                ErrorStatus.RESOLVED,
                user=user,
                notes=f"Fixed by {fix_id}: {result.message}"
            )
        
        # Notify via WebSocket
        if socketio_instance:
            socketio_instance.emit('fix_result', {
                'error_id': error_id,
                'fix_id': fix_id,
                'result': result.to_dict()
            }, namespace='/')
            
            if not dry_run:
                updated_error = error_store.get_by_id(error_id)
                socketio_instance.emit('error_updated', updated_error.to_dict(), namespace='/')
        
        return jsonify({
            'success': True,
            'result': result.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@errors_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Get error statistics"""
    try:
        stats = error_store.get_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@errors_bp.route('/catalog', methods=['GET'])
def get_catalog():
    """Get all known error patterns"""
    try:
        catalog = ErrorCatalog()
        codes = catalog.get_all_codes()
        
        patterns = []
        for code in codes:
            pattern = catalog.get_pattern_by_code(code)
            if pattern:
                patterns.append({
                    'code': pattern.code,
                    'title': pattern.title,
                    'severity': pattern.severity.value,
                    'can_auto_fix': pattern.can_auto_fix
                })
        
        return jsonify({
            'success': True,
            'patterns': patterns,
            'count': len(patterns)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@errors_bp.route('/scan', methods=['POST'])
def scan_for_errors():
    """
    Manually trigger error scan from logs
    
    POST /api/errors/scan
    Returns: { "success": true, "found": 5, "message": "..." }
    """
    try:
        import subprocess
        import json
        from pathlib import Path
        
        # Run the error monitor script once
        # __file__ is in webui/backend/errors/routes.py
        # Go up 3 levels to workspace root
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        script_path = base_dir / 'services' / 'quick_error_scan.py'
        
        if not script_path.exists():
            return jsonify({
                'success': False,
                'error': 'Error monitor script not found',
                'found': 0
            }), 404
        
        # Get error count before scan
        before_stats = error_store.get_statistics() if error_store else {}
        before_count = before_stats.get('by_status', {}).get('open', 0)
        
        # Run scan
        result = subprocess.run(
            ['python3', str(script_path)],
            capture_output=True,
            text=True,
            timeout=10  # Quick scan should be fast
        )
        
        # Get error count after scan
        after_stats = error_store.get_statistics() if error_store else {}
        after_count = after_stats.get('by_status', {}).get('open', 0)
        
        found = max(0, after_count - before_count)
        
        return jsonify({
            'success': True,
            'found': found,
            'message': f'Scan completed. Found {found} new error{"s" if found != 1 else ""}',
            'output': result.stdout if result.returncode == 0 else result.stderr
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Scan timeout - took longer than 30 seconds',
            'found': 0
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'found': 0
        }), 500


@errors_bp.route('/test', methods=['POST'])
def test_error():
    """
    Inject a test error for debugging
    
    POST /api/errors/test
    Body: { "message": "error message", "source": "trading|guardian|health|system" }
    """
    try:
        data = request.json or {}
        
        # Create test error
        test_message = data.get("message", "Test error - API authentication failed")
        test_source = data.get("source", "trading")
        
        # Convert source string to enum
        try:
            source_enum = ErrorSource(test_source)
        except ValueError:
            source_enum = ErrorSource.SYSTEM
        
        # Classify the error
        if not error_classifier:
            return jsonify({
                'success': False,
                'message': 'Error classifier not available'
            }), 500
        
        error_event = error_classifier.classify(test_message, source_enum)
        
        # Store it
        if error_store:
            error_store.save(error_event)
        
        # Emit via WebSocket
        if socketio_instance:
            socketio_instance.emit('new_error', error_event.to_dict(), namespace='/')
        
        return jsonify({
            'success': True,
            'error': error_event.to_dict(),
            'message': 'Test error created successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ========== WebSocket Events ==========

def emit_new_error(error: ErrorEvent):
    """Emit a new error to all connected clients"""
    if socketio_instance:
        socketio_instance.emit('new_error', error.to_dict(), namespace='/')


def emit_error_update(error: ErrorEvent):
    """Emit an error update to all connected clients"""
    if socketio_instance:
        socketio_instance.emit('error_updated', error.to_dict(), namespace='/')
