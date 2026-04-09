"""
Simple Todo Routes Blueprint

This module handles API routes for the WebUI todo list.

Core fields:
- title: short task name
- work: human-language task details

Legacy compatibility:
- accepts and returns a `text` field composed as "title\nwork"
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

# Create blueprint
todos_bp = Blueprint('todos', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
TODO_FILE = BASE_DIR / 'data' / 'user_todos.json'


# ============================================================================
# Helper Functions
# ============================================================================


def _safe_str(value):
    return value.strip() if isinstance(value, str) else ''


def _split_legacy_text(text):
    """Split legacy `text` into title + work."""
    cleaned = _safe_str(text)
    if not cleaned:
        return '', ''

    lines = cleaned.splitlines()
    title = (lines[0] if lines else '').strip()
    work = '\n'.join(lines[1:]).strip()
    return title, work


def _compose_text(title, work):
    """Compose compatibility text from title + work."""
    title = _safe_str(title)
    work = _safe_str(work)

    if title and work:
        return f'{title}\n{work}'

    return title or work


def _normalize_todo(todo):
    """Normalize todo shape and ensure required keys exist."""
    source = todo if isinstance(todo, dict) else {}
    normalized = dict(source)

    legacy_title, legacy_work = _split_legacy_text(normalized.get('text'))

    title = _safe_str(normalized.get('title')) or legacy_title
    work = _safe_str(normalized.get('work')) or legacy_work

    if not title and work:
        title = work[:120]

    if not title:
        title = 'Untitled'

    created_at = normalized.get('createdAt') or datetime.now().isoformat()
    updated_at = normalized.get('updatedAt') or created_at

    normalized.update({
        'id': str(normalized.get('id') or int(time.time() * 1000)),
        'title': title,
        'work': work,
        'text': _compose_text(title, work),
        'completed': bool(normalized.get('completed', False)),
        'pinned': bool(normalized.get('pinned', False)),
        'createdAt': created_at,
        'updatedAt': updated_at,
    })

    return normalized


def _extract_payload(data, fallback_title='', fallback_work=''):
    """Extract title/work from payload with legacy text fallback."""
    title = _safe_str(data.get('title'))
    work = _safe_str(data.get('work'))

    legacy_title, legacy_work = _split_legacy_text(data.get('text'))

    if not title and legacy_title:
        title = legacy_title
    if not work and legacy_work:
        work = legacy_work

    if not title:
        title = _safe_str(fallback_title)
    if not work:
        work = _safe_str(fallback_work)

    if not title and work:
        title = work[:120]

    return title, work


def load_todos():
    """Load todos from JSON file."""
    if not TODO_FILE.exists():
        return []

    try:
        with open(TODO_FILE, 'r', encoding='utf-8') as handle:
            raw_data = json.load(handle)

        if not isinstance(raw_data, list):
            log.warning('Todos file is not a list; resetting to empty list')
            return []

        todos = [_normalize_todo(item) for item in raw_data]
        todos.sort(key=lambda todo: todo.get('updatedAt') or todo.get('createdAt') or '', reverse=True)
        return todos
    except Exception as error:
        log.error(f'Error loading todos: {error}')
        return []


def save_todos(todos):
    """Save todos to JSON file."""
    try:
        TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TODO_FILE, 'w', encoding='utf-8') as handle:
            json.dump(todos, handle, indent=2, ensure_ascii=False)
        return True
    except Exception as error:
        log.error(f'Error saving todos: {error}')
        return False


# ============================================================================
# Route Handlers
# ============================================================================


@todos_bp.route('/api/todos', methods=['GET'])
def get_todos():
    """Get all todos."""
    try:
        todos = load_todos()
        return jsonify({'success': True, 'todos': todos}), 200
    except Exception as error:
        log.error(f'Error getting todos: {error}')
        return jsonify({'success': False, 'error': str(error)}), 500


@todos_bp.route('/api/todos', methods=['POST'])
def create_todo():
    """Create a new todo."""
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'success': False, 'error': 'Invalid JSON or Content-Type'}), 400

        # Handle accidentally stringified JSON payloads.
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400

        if not isinstance(data, dict):
            return jsonify({'success': False, 'error': 'Payload must be a JSON object'}), 400

        title, work = _extract_payload(data)
        if not title and not work:
            return jsonify({'success': False, 'error': 'Please provide a title and/or text'}), 400

        now = datetime.now().isoformat()

        new_todo = _normalize_todo({
            'id': str(int(time.time() * 1000)),
            'title': title,
            'work': work,
            'completed': bool(data.get('completed', False)),
            'pinned': bool(data.get('pinned', False)),
            'createdAt': now,
            'updatedAt': now,
        })

        # Keep optional legacy metadata if clients still send it.
        for key in ('priority', 'category'):
            if key in data:
                new_todo[key] = data.get(key)

        todos = load_todos()
        todos.append(new_todo)

        if save_todos(todos):
            return jsonify({'success': True, 'todo': new_todo}), 201

        return jsonify({'success': False, 'error': 'Failed to save todo'}), 500
    except Exception as error:
        log.error(f'Exception in create_todo: {error}', exc_info=True)
        return jsonify({'success': False, 'error': str(error)}), 500


@todos_bp.route('/api/todos/<todo_id>', methods=['PUT'])
def update_todo(todo_id):
    """Update todo fields (title/work/text/completed and optional metadata)."""
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'success': False, 'error': 'Invalid JSON or Content-Type'}), 400

        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400

        if not isinstance(data, dict):
            return jsonify({'success': False, 'error': 'Payload must be a JSON object'}), 400

        todos = load_todos()
        todo_found = False

        for index, todo in enumerate(todos):
            if str(todo.get('id')) != str(todo_id):
                continue

            todo_found = True
            current = _normalize_todo(todo)

            if 'completed' in data:
                current['completed'] = bool(data.get('completed'))

            if any(field in data for field in ('title', 'work', 'text')):
                title, work = _extract_payload(
                    data,
                    fallback_title=current.get('title', ''),
                    fallback_work=current.get('work', ''),
                )
                current['title'] = title or current.get('title') or 'Untitled'
                current['work'] = work
                current['text'] = _compose_text(current['title'], current['work'])

            for key in ('priority', 'category', 'pinned'):
                if key in data:
                    current[key] = bool(data.get(key)) if key == 'pinned' else data.get(key)

            current['updatedAt'] = datetime.now().isoformat()
            todos[index] = _normalize_todo(current)
            break

        if not todo_found:
            return jsonify({'success': False, 'error': 'Todo not found'}), 404

        if save_todos(todos):
            return jsonify({'success': True, 'todos': todos}), 200

        return jsonify({'success': False, 'error': 'Failed to save todo'}), 500
    except Exception as error:
        log.error(f'Error updating todo: {error}')
        return jsonify({'success': False, 'error': str(error)}), 500


@todos_bp.route('/api/todos/<todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """Delete a todo by ID."""
    try:
        todos = load_todos()
        original_length = len(todos)
        todos = [todo for todo in todos if str(todo.get('id')) != str(todo_id)]

        if len(todos) == original_length:
            return jsonify({'success': False, 'error': 'Todo not found'}), 404

        if save_todos(todos):
            log.info(f'Deleted todo {todo_id}')
            return jsonify({'success': True, 'todos': todos}), 200

        return jsonify({'success': False, 'error': 'Failed to save todos'}), 500
    except Exception as error:
        log.error(f'Error deleting todo: {error}')
        return jsonify({'success': False, 'error': str(error)}), 500
