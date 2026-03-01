"""
Options Groups Storage — Server-Side Persistent Storage

Thread-safe SQLite-based persistence for position groups, notes, and ordering.
Groups are stored per expiry key and NEVER disappear unless explicitly deleted.

Created: March 1, 2026
"""

import json
import os
import sqlite3
import logging
import threading
from typing import Dict, Any, Optional

log = logging.getLogger('options_groups_storage')

# Storage path — always relative to this file's location, regardless of cwd
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(os.path.dirname(_THIS_DIR))  # routes/options -> routes -> backend
DATA_DIR = os.path.join(_BACKEND_DIR, 'data')
DB_FILE = os.path.join(DATA_DIR, 'options_groups.db')

# Thread-local connections
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, 'conn') or _local.conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_FILE, timeout=10)
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def _init_db():
    """Initialize the database schema."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS expiry_groups (
            expiry_key TEXT NOT NULL,
            group_id TEXT NOT NULL,
            name TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#7c3aed',
            note TEXT DEFAULT '',
            symbols TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (expiry_key, group_id)
        );

        CREATE TABLE IF NOT EXISTS expiry_meta (
            expiry_key TEXT PRIMARY KEY,
            collapsed TEXT DEFAULT '{}',
            position_order TEXT DEFAULT '[]',
            group_order TEXT DEFAULT '[]',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    log.info(f"Options groups DB initialized at {DB_FILE}")


# Initialize on module load
try:
    _init_db()
except Exception as e:
    log.error(f"Failed to initialize groups DB: {e}")


class GroupsStorage:
    """Thread-safe persistent storage for options position groups."""

    def get_all(self) -> Dict[str, Any]:
        """
        Get all group data for all expiry keys.
        Returns the same structure as the old localStorage format:
        {
            "EXPIRY_KEY": {
                "groups": { "id": { "name": ..., "color": ..., "symbols": [...], "note": ... } },
                "collapsed": { "id": true/false },
                "order": [...],
                "groupOrder": [...]
            }
        }
        """
        conn = _get_conn()
        result = {}

        # Load all groups
        rows = conn.execute("SELECT * FROM expiry_groups ORDER BY created_at").fetchall()
        for row in rows:
            key = row['expiry_key']
            if key not in result:
                result[key] = {'groups': {}, 'collapsed': {}, 'order': [], 'groupOrder': []}
            result[key]['groups'][row['group_id']] = {
                'name': row['name'],
                'color': row['color'],
                'note': row['note'] or '',
                'symbols': json.loads(row['symbols'] or '[]'),
            }

        # Load metadata (collapsed, order, groupOrder)
        meta_rows = conn.execute("SELECT * FROM expiry_meta").fetchall()
        for row in meta_rows:
            key = row['expiry_key']
            if key not in result:
                result[key] = {'groups': {}, 'collapsed': {}, 'order': [], 'groupOrder': []}
            result[key]['collapsed'] = json.loads(row['collapsed'] or '{}')
            result[key]['order'] = json.loads(row['position_order'] or '[]')
            result[key]['groupOrder'] = json.loads(row['group_order'] or '[]')

        return result

    def get_expiry(self, expiry_key: str) -> Dict[str, Any]:
        """Get group data for a specific expiry key."""
        conn = _get_conn()
        data = {'groups': {}, 'collapsed': {}, 'order': [], 'groupOrder': []}

        rows = conn.execute(
            "SELECT * FROM expiry_groups WHERE expiry_key = ? ORDER BY created_at",
            (expiry_key,)
        ).fetchall()
        for row in rows:
            data['groups'][row['group_id']] = {
                'name': row['name'],
                'color': row['color'],
                'note': row['note'] or '',
                'symbols': json.loads(row['symbols'] or '[]'),
            }

        meta = conn.execute(
            "SELECT * FROM expiry_meta WHERE expiry_key = ?",
            (expiry_key,)
        ).fetchone()
        if meta:
            data['collapsed'] = json.loads(meta['collapsed'] or '{}')
            data['order'] = json.loads(meta['position_order'] or '[]')
            data['groupOrder'] = json.loads(meta['group_order'] or '[]')

        return data

    def save_all(self, data: Dict[str, Any]):
        """
        Bulk save/replace all group data (used for migration from localStorage).
        Overwrites everything.
        """
        conn = _get_conn()
        try:
            conn.execute("DELETE FROM expiry_groups")
            conn.execute("DELETE FROM expiry_meta")

            for expiry_key, expiry_data in data.items():
                groups = expiry_data.get('groups', {})
                for gid, grp in groups.items():
                    conn.execute(
                        """INSERT INTO expiry_groups (expiry_key, group_id, name, color, note, symbols)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (expiry_key, gid, grp.get('name', ''), grp.get('color', '#7c3aed'),
                         grp.get('note', ''), json.dumps(grp.get('symbols', [])))
                    )

                conn.execute(
                    """INSERT OR REPLACE INTO expiry_meta (expiry_key, collapsed, position_order, group_order)
                       VALUES (?, ?, ?, ?)""",
                    (expiry_key,
                     json.dumps(expiry_data.get('collapsed', {})),
                     json.dumps(expiry_data.get('order', [])),
                     json.dumps(expiry_data.get('groupOrder', [])))
                )

            conn.commit()
            log.info(f"Bulk saved groups for {len(data)} expiry keys")
        except Exception as e:
            conn.rollback()
            log.error(f"Failed to bulk save groups: {e}")
            raise

    def create_group(self, expiry_key: str, group_id: str, name: str, color: str) -> Dict[str, Any]:
        """Create a new group."""
        conn = _get_conn()
        try:
            conn.execute(
                """INSERT INTO expiry_groups (expiry_key, group_id, name, color, symbols)
                   VALUES (?, ?, ?, ?, '[]')""",
                (expiry_key, group_id, name, color)
            )
            # Append to group_order in meta
            meta = conn.execute(
                "SELECT group_order FROM expiry_meta WHERE expiry_key = ?",
                (expiry_key,)
            ).fetchone()
            if meta:
                order = json.loads(meta['group_order'] or '[]')
                order.append(group_id)
                conn.execute(
                    "UPDATE expiry_meta SET group_order = ?, updated_at = CURRENT_TIMESTAMP WHERE expiry_key = ?",
                    (json.dumps(order), expiry_key)
                )
            else:
                conn.execute(
                    """INSERT INTO expiry_meta (expiry_key, group_order) VALUES (?, ?)""",
                    (expiry_key, json.dumps([group_id]))
                )
            conn.commit()
            log.info(f"Created group '{name}' ({group_id}) for expiry {expiry_key}")
            return {'name': name, 'color': color, 'note': '', 'symbols': []}
        except Exception as e:
            conn.rollback()
            log.error(f"Failed to create group: {e}")
            raise

    def delete_group(self, expiry_key: str, group_id: str):
        """Delete a group."""
        conn = _get_conn()
        try:
            conn.execute(
                "DELETE FROM expiry_groups WHERE expiry_key = ? AND group_id = ?",
                (expiry_key, group_id)
            )
            # Remove from group_order
            meta = conn.execute(
                "SELECT group_order FROM expiry_meta WHERE expiry_key = ?",
                (expiry_key,)
            ).fetchone()
            if meta:
                order = json.loads(meta['group_order'] or '[]')
                order = [gid for gid in order if gid != group_id]
                conn.execute(
                    "UPDATE expiry_meta SET group_order = ?, updated_at = CURRENT_TIMESTAMP WHERE expiry_key = ?",
                    (json.dumps(order), expiry_key)
                )
            conn.commit()
            log.info(f"Deleted group {group_id} from expiry {expiry_key}")
        except Exception as e:
            conn.rollback()
            log.error(f"Failed to delete group: {e}")
            raise

    def update_group(self, expiry_key: str, group_id: str, updates: Dict[str, Any]):
        """Update group fields (name, color, note, symbols)."""
        conn = _get_conn()
        try:
            # Build SET clause dynamically
            allowed = {'name', 'color', 'note', 'symbols'}
            sets = []
            params = []
            for field, value in updates.items():
                if field in allowed:
                    if field == 'symbols':
                        sets.append(f"{field} = ?")
                        params.append(json.dumps(value))
                    else:
                        sets.append(f"{field} = ?")
                        params.append(value)

            if not sets:
                return

            sets.append("updated_at = CURRENT_TIMESTAMP")
            params.extend([expiry_key, group_id])

            conn.execute(
                f"UPDATE expiry_groups SET {', '.join(sets)} WHERE expiry_key = ? AND group_id = ?",
                params
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            log.error(f"Failed to update group: {e}")
            raise

    def assign_symbol(self, expiry_key: str, symbol: str, target_group_id: Optional[str]):
        """Assign a symbol to a group, removing it from any other group first."""
        conn = _get_conn()
        try:
            # Remove symbol from all groups in this expiry
            rows = conn.execute(
                "SELECT group_id, symbols FROM expiry_groups WHERE expiry_key = ?",
                (expiry_key,)
            ).fetchall()
            for row in rows:
                syms = json.loads(row['symbols'] or '[]')
                if symbol in syms:
                    syms.remove(symbol)
                    conn.execute(
                        "UPDATE expiry_groups SET symbols = ?, updated_at = CURRENT_TIMESTAMP WHERE expiry_key = ? AND group_id = ?",
                        (json.dumps(syms), expiry_key, row['group_id'])
                    )

            # Add to target group
            if target_group_id:
                target = conn.execute(
                    "SELECT symbols FROM expiry_groups WHERE expiry_key = ? AND group_id = ?",
                    (expiry_key, target_group_id)
                ).fetchone()
                if target:
                    syms = json.loads(target['symbols'] or '[]')
                    syms.append(symbol)
                    conn.execute(
                        "UPDATE expiry_groups SET symbols = ?, updated_at = CURRENT_TIMESTAMP WHERE expiry_key = ? AND group_id = ?",
                        (json.dumps(syms), expiry_key, target_group_id)
                    )

            conn.commit()
        except Exception as e:
            conn.rollback()
            log.error(f"Failed to assign symbol: {e}")
            raise

    def update_meta(self, expiry_key: str, collapsed=None, order=None, group_order=None):
        """Update metadata (collapsed states, position order, group order)."""
        conn = _get_conn()
        try:
            meta = conn.execute(
                "SELECT * FROM expiry_meta WHERE expiry_key = ?",
                (expiry_key,)
            ).fetchone()

            if meta:
                sets = ["updated_at = CURRENT_TIMESTAMP"]
                params = []
                if collapsed is not None:
                    sets.append("collapsed = ?")
                    params.append(json.dumps(collapsed))
                if order is not None:
                    sets.append("position_order = ?")
                    params.append(json.dumps(order))
                if group_order is not None:
                    sets.append("group_order = ?")
                    params.append(json.dumps(group_order))

                params.append(expiry_key)
                conn.execute(
                    f"UPDATE expiry_meta SET {', '.join(sets)} WHERE expiry_key = ?",
                    params
                )
            else:
                conn.execute(
                    """INSERT INTO expiry_meta (expiry_key, collapsed, position_order, group_order)
                       VALUES (?, ?, ?, ?)""",
                    (expiry_key,
                     json.dumps(collapsed or {}),
                     json.dumps(order or []),
                     json.dumps(group_order or []))
                )

            conn.commit()
        except Exception as e:
            conn.rollback()
            log.error(f"Failed to update meta: {e}")
            raise


# Singleton
_instance = None
_instance_lock = threading.Lock()


def get_groups_storage() -> GroupsStorage:
    """Get or create the singleton GroupsStorage instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = GroupsStorage()
    return _instance
