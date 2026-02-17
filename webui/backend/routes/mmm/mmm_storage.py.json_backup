"""
MMM Storage — Money Mind & Method

Thread-safe JSON file-based persistence for MMM sessions.
Follows the same pattern as SSR Algo Storage.

Created: February 15, 2026
"""

import json
import os
import fcntl
import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

log = logging.getLogger('mmm_storage')

# Storage file path
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
STORAGE_FILE = os.path.join(DATA_DIR, 'mmm_sessions.json')

# Singleton instance
_storage_instance = None


class MMMStorage:
    """
    Thread-safe JSON storage for MMM sessions.

    Storage format:
    {
        "sessions": {
            "session_id": { ... session data ... }
        },
        "active_session_ids": ["session_id1"],
        "version": 1
    }
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or STORAGE_FILE
        self._ensure_storage_exists()

    def _ensure_storage_exists(self):
        """Create storage file and directory if they don't exist."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

        if not os.path.exists(self.storage_path):
            initial_data = {
                'sessions': {},
                'active_session_ids': [],
                'version': 1,
                'created_at': datetime.utcnow().isoformat(),
            }
            self._write_data(initial_data)
            log.info(f"Created new MMM storage file: {self.storage_path}")

    def _read_data(self) -> Dict:
        """Read storage file with shared lock."""
        try:
            with open(self.storage_path, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return data
        except json.JSONDecodeError as e:
            log.error(f"JSON decode error in MMM storage: {e}")
            return {'sessions': {}, 'active_session_ids': [], 'version': 1}
        except Exception as e:
            log.error(f"Error reading MMM storage: {e}")
            return {'sessions': {}, 'active_session_ids': [], 'version': 1}

    def _write_data(self, data: Dict):
        """Write to storage file with exclusive lock."""
        try:
            with open(self.storage_path, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2, default=str)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception as e:
            log.error(f"Error writing MMM storage: {e}")
            raise

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def save_session(self, session: Dict) -> str:
        """
        Save or update a session.

        Args:
            session: Complete session dictionary (must have 'session_id')

        Returns:
            session_id
        """
        session_id = session.get('session_id')
        if not session_id:
            raise ValueError("Session must have a session_id")

        session['updated_at'] = datetime.utcnow().isoformat()

        data = self._read_data()
        data['sessions'][session_id] = session

        # Track active sessions
        status = session.get('strategy_status', 'IDLE')
        if status in ('RUNNING', 'PAUSED', 'BOTH_SIDES_UP'):
            if session_id not in data['active_session_ids']:
                data['active_session_ids'].append(session_id)
        else:
            if session_id in data['active_session_ids']:
                data['active_session_ids'].remove(session_id)

        self._write_data(data)
        log.debug(f"Saved MMM session {session_id} (status: {status})")
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session dictionary or None
        """
        data = self._read_data()
        return data.get('sessions', {}).get(session_id)

    def list_sessions(self, active_only: bool = False) -> List[Dict]:
        """
        List all sessions, optionally filtered to active only.

        Args:
            active_only: If True, only return active sessions

        Returns:
            List of session dictionaries
        """
        data = self._read_data()
        sessions = list(data.get('sessions', {}).values())

        if active_only:
            active_ids = set(data.get('active_session_ids', []))
            sessions = [s for s in sessions if s.get('session_id') in active_ids]

        # Sort by creation time descending (newest first)
        sessions.sort(key=lambda s: s.get('created_at', ''), reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        data = self._read_data()

        if session_id not in data.get('sessions', {}):
            return False

        del data['sessions'][session_id]
        if session_id in data.get('active_session_ids', []):
            data['active_session_ids'].remove(session_id)

        self._write_data(data)
        log.info(f"Deleted MMM session {session_id}")
        return True

    def update_session(self, session_id: str, updates: Dict) -> Optional[Dict]:
        """
        Partially update a session with the given fields.

        Args:
            session_id: Session ID
            updates: Dictionary of fields to update

        Returns:
            Updated session or None if not found
        """
        data = self._read_data()
        session = data.get('sessions', {}).get(session_id)

        if not session:
            return None

        # Deep merge for nested dicts (ce, pe, params)
        for key, value in updates.items():
            if key in ('ce', 'pe', 'params') and isinstance(value, dict) and isinstance(session.get(key), dict):
                session[key].update(value)
            else:
                session[key] = value

        session['updated_at'] = datetime.utcnow().isoformat()

        # Update active tracking
        status = session.get('strategy_status', 'IDLE')
        if status in ('RUNNING', 'PAUSED', 'BOTH_SIDES_UP'):
            if session_id not in data['active_session_ids']:
                data['active_session_ids'].append(session_id)
        else:
            if session_id in data.get('active_session_ids', []):
                data['active_session_ids'].remove(session_id)

        data['sessions'][session_id] = session
        self._write_data(data)
        return session

    def get_active_session_ids(self) -> List[str]:
        """Get list of active session IDs."""
        data = self._read_data()
        return data.get('active_session_ids', [])

    def get_session_count(self) -> int:
        """Get total number of sessions."""
        data = self._read_data()
        return len(data.get('sessions', {}))


def get_storage(storage_path: str = None) -> MMMStorage:
    """
    Get singleton storage instance.

    Args:
        storage_path: Optional custom path

    Returns:
        MMMStorage singleton
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = MMMStorage(storage_path)
    return _storage_instance
