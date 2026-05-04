"""
Options Groups API — Server-Side Persistent Groups

REST API for managing position groups, notes, and ordering.
Groups are stored in SQLite and NEVER disappear unless user deletes them.

Routes:
  GET    /api/options/groups              — Get all group data
  GET    /api/options/groups/<expiry_key> — Get groups for one expiry
  POST   /api/options/groups/bulk         — Bulk import (migration from localStorage)
  POST   /api/options/groups/create       — Create a new group
  DELETE /api/options/groups/delete       — Delete a group
  PUT    /api/options/groups/update       — Update group fields
  PUT    /api/options/groups/assign       — Assign symbol to group
  PUT    /api/options/groups/meta         — Update metadata (collapsed, order)

Created: March 1, 2026
"""

import logging
import importlib.util
import os
from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

# Load groups_storage directly by file path to avoid __init__.py import chains
_storage_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'groups_storage.py')
_spec = importlib.util.spec_from_file_location('groups_storage', _storage_path)
_storage_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_storage_mod)
get_groups_storage = _storage_mod.get_groups_storage

groups_bp = Blueprint('options_groups', __name__, url_prefix='/api/options/groups')


def _validate_expiry_key(key: str):
    """
    Reject UI-only synthetic keys that must never be stored in the DB.
    'ALL' and composite keys (containing '|') are frontend view constructs only.
    Storing them corrupts the activeExpiryData merge logic and makes real groups invisible.
    Raises ValueError if the key is invalid.
    """
    if not key:
        raise ValueError("expiry_key is empty")
    if key == 'ALL':
        raise ValueError("'ALL' is a UI-only key and cannot be stored server-side")
    if '|' in key:
        raise ValueError(f"Composite key '{key}' is a UI-only key and cannot be stored server-side")


@groups_bp.route('/', methods=['GET'])
def get_all_groups():
    """Get all group data for all expiry keys."""
    try:
        storage = get_groups_storage()
        data = storage.get_all()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        log.error(f"Failed to get all groups: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@groups_bp.route('/<path:expiry_key>', methods=['GET'])
def get_expiry_groups(expiry_key):
    """Get group data for a specific expiry key."""
    try:
        storage = get_groups_storage()
        data = storage.get_expiry(expiry_key)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        log.error(f"Failed to get groups for {expiry_key}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@groups_bp.route('/bulk', methods=['POST'])
def bulk_import():
    """Bulk import groups (for migration from localStorage)."""
    try:
        body = request.get_json()
        if not body or 'data' not in body:
            return jsonify({'success': False, 'error': 'Missing data field'}), 400

        storage = get_groups_storage()
        storage.save_all(body['data'])
        return jsonify({'success': True, 'message': 'Groups imported successfully'})
    except Exception as e:
        log.error(f"Failed to bulk import groups: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@groups_bp.route('/create', methods=['POST'])
def create_group():
    """Create a new group."""
    try:
        body = request.get_json()
        if not body:
            return jsonify({'success': False, 'error': 'Missing request body'}), 400

        expiry_key = body.get('expiry_key')
        group_id = body.get('group_id')
        name = body.get('name', '').strip()
        color = body.get('color', '#7c3aed')

        if not expiry_key or not group_id or not name:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        try:
            _validate_expiry_key(expiry_key)
        except ValueError as ve:
            log.warning(f"Rejected create_group for bad expiry_key {expiry_key!r}: {ve}")
            return jsonify({'success': False, 'error': str(ve)}), 400

        storage = get_groups_storage()
        group = storage.create_group(expiry_key, group_id, name, color)
        return jsonify({'success': True, 'group': group})
    except Exception as e:
        log.error(f"Failed to create group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@groups_bp.route('/delete', methods=['DELETE'])
def delete_group():
    """Delete a group."""
    try:
        body = request.get_json()
        if not body:
            return jsonify({'success': False, 'error': 'Missing request body'}), 400

        expiry_key = body.get('expiry_key')
        group_id = body.get('group_id')

        if not expiry_key or not group_id:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        try:
            _validate_expiry_key(expiry_key)
        except ValueError as ve:
            log.warning(f"Rejected delete_group for bad expiry_key {expiry_key!r}: {ve}")
            return jsonify({'success': False, 'error': str(ve)}), 400

        storage = get_groups_storage()
        storage.delete_group(expiry_key, group_id)
        return jsonify({'success': True})
    except Exception as e:
        log.error(f"Failed to delete group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@groups_bp.route('/update', methods=['PUT'])
def update_group():
    """Update group fields (name, color, note, symbols)."""
    try:
        body = request.get_json()
        if not body:
            return jsonify({'success': False, 'error': 'Missing request body'}), 400

        expiry_key = body.get('expiry_key')
        group_id = body.get('group_id')
        updates = body.get('updates', {})

        if not expiry_key or not group_id:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        try:
            _validate_expiry_key(expiry_key)
        except ValueError as ve:
            log.warning(f"Rejected update_group for bad expiry_key {expiry_key!r}: {ve}")
            return jsonify({'success': False, 'error': str(ve)}), 400

        storage = get_groups_storage()
        storage.update_group(expiry_key, group_id, updates)
        return jsonify({'success': True})
    except Exception as e:
        log.error(f"Failed to update group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@groups_bp.route('/assign', methods=['PUT'])
def assign_symbol():
    """Assign a symbol to a group (or remove from all groups if target is null)."""
    try:
        body = request.get_json()
        if not body:
            return jsonify({'success': False, 'error': 'Missing request body'}), 400

        expiry_key = body.get('expiry_key')
        symbol = body.get('symbol')
        target_group_id = body.get('target_group_id')  # null = unassign

        if not expiry_key or not symbol:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        try:
            _validate_expiry_key(expiry_key)
        except ValueError as ve:
            log.warning(f"Rejected assign_symbol for bad expiry_key {expiry_key!r}: {ve}")
            return jsonify({'success': False, 'error': str(ve)}), 400

        storage = get_groups_storage()
        storage.assign_symbol(expiry_key, symbol, target_group_id)
        return jsonify({'success': True})
    except Exception as e:
        log.error(f"Failed to assign symbol: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@groups_bp.route('/meta', methods=['PUT'])
def update_meta():
    """Update metadata (collapsed states, position order, group order)."""
    try:
        body = request.get_json()
        if not body:
            return jsonify({'success': False, 'error': 'Missing request body'}), 400

        expiry_key = body.get('expiry_key')
        if not expiry_key:
            return jsonify({'success': False, 'error': 'Missing expiry_key'}), 400

        try:
            _validate_expiry_key(expiry_key)
        except ValueError as ve:
            log.warning(f"Rejected update_meta for bad expiry_key {expiry_key!r}: {ve}")
            return jsonify({'success': False, 'error': str(ve)}), 400

        storage = get_groups_storage()
        storage.update_meta(
            expiry_key,
            collapsed=body.get('collapsed'),
            order=body.get('order'),
            group_order=body.get('group_order'),
        )
        return jsonify({'success': True})
    except Exception as e:
        log.error(f"Failed to update meta: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
