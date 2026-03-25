"""
User Preferences — lightweight key/value store for UI preferences.

Stores to data/user_preferences.json on the backend so preferences
survive page refreshes, npm builds, and browser cache clears.

Endpoints:
    GET  /api/user/preferences        → returns full preferences dict
    POST /api/user/preferences        → merges posted keys into preferences

Created: March 21, 2026
"""

import json
import logging
import os

from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

user_preferences_bp = Blueprint('user_preferences', __name__)

_PREFS_FILE = os.path.join(
    os.path.dirname(__file__), '..', 'data', 'user_preferences.json'
)


def _load() -> dict:
    try:
        if os.path.exists(_PREFS_FILE):
            with open(_PREFS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        log.warning(f'Failed to read user preferences: {e}')
    return {}


def _save(data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_PREFS_FILE), exist_ok=True)
        with open(_PREFS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error(f'Failed to write user preferences: {e}')


@user_preferences_bp.route('/api/user/preferences', methods=['GET'])
def get_preferences():
    return jsonify(_load())


@user_preferences_bp.route('/api/user/preferences', methods=['POST'])
def update_preferences():
    body = request.get_json(silent=True) or {}
    prefs = _load()
    prefs.update(body)
    _save(prefs)
    return jsonify({'success': True, 'preferences': prefs})
