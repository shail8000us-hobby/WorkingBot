"""
Todos Routes Blueprint

This module handles all API routes related to user improvement todos/tasks.

Routes:
- GET  /api/todos - Get all todos
- POST /api/todos - Create a new todo
- PUT  /api/todos/:id - Update a todo (toggle completed or edit text)
- DELETE /api/todos/:id - Delete a todo

Dependencies:
- JSON file storage (data/user_todos.json)

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime
from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

# Create blueprint
todos_bp = Blueprint('todos', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
TODO_FILE = BASE_DIR / "data" / "user_todos.json"

# ============================================================================
# Helper Functions
# ============================================================================

def load_todos():
    """Load todos from JSON file"""
    if TODO_FILE.exists():
        try:
            with open(TODO_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Error loading todos: {e}")
            return []
    return []

def save_todos(todos):
    """Save todos to JSON file"""
    try:
        TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TODO_FILE, 'w') as f:
            json.dump(todos, f, indent=2)
        return True
    except Exception as e:
        log.error(f"Error saving todos: {e}")
        return False

# ============================================================================
# Route Handlers
# ============================================================================

@todos_bp.route('/api/todos', methods=['GET'])
def get_todos():
    """
    Get all todos
    
    Returns:
        JSON response with todos list
    
    Example:
        GET /api/todos
        Response: {
            "success": true,
            "todos": [
                {
                    "id": "1698765432000",
                    "text": "Improve order execution speed",
                    "completed": false,
                    "createdAt": "2025-10-31T15:30:32",
                    "updatedAt": "2025-10-31T15:30:32"
                }
            ]
        }
    """
    try:
        todos = load_todos()
        return jsonify({'success': True, 'todos': todos}), 200
    except Exception as e:
        log.error(f"Error getting todos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@todos_bp.route('/api/todos', methods=['POST'])
def create_todo():
    """
    Create a new todo
    
    Request Body:
        {
            "text": "Todo description"
        }
    
    Returns:
        JSON response with created todo
    
    Example:
        POST /api/todos
        Body: {"text": "Implement stop-loss"}
        Response: {
            "success": true,
            "todo": {
                "id": "1698765432000",
                "text": "Implement stop-loss",
                "completed": false,
                "createdAt": "2025-10-31T15:30:32",
                "updatedAt": "2025-10-31T15:30:32"
            }
        }
    """
    try:
        data = request.get_json()
        if data is None:
            log.error("request.get_json() returned None")
            return jsonify({'success': False, 'error': 'Invalid JSON or Content-Type'}), 400
        
        # Handle double-encoded JSON (when frontend sends string instead of object)
        if isinstance(data, str):
            log.warning("Received string instead of object, parsing...")
            data = json.loads(data)
        
        text = data.get('text', '').strip()
        log.info(f"Creating todo with text: '{text}'")
        
        if not text:
            log.error("Empty text provided")
            return jsonify({'success': False, 'error': 'Todo text is required'}), 400
        
        todos = load_todos()
        log.info(f"Loaded {len(todos)} existing todos")
        
        new_todo = {
            'id': str(int(time.time() * 1000)),  # Unix timestamp in milliseconds
            'text': text,
            'completed': False,
            'createdAt': datetime.now().isoformat(),
            'updatedAt': datetime.now().isoformat()
        }
        todos.append(new_todo)
        log.info(f"Created new todo with ID: {new_todo['id']}")
        
        if save_todos(todos):
            log.info(f"Successfully saved {len(todos)} todos to disk")
            return jsonify({'success': True, 'todo': new_todo}), 201
        else:
            log.error("Failed to save todos to disk")
            return jsonify({'success': False, 'error': 'Failed to save todo'}), 500
            
    except Exception as e:
        log.error(f"Exception in create_todo: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@todos_bp.route('/api/todos/<todo_id>', methods=['PUT'])
def update_todo(todo_id):
    """
    Update a todo (toggle completed or edit text)
    
    Request Body:
        {
            "completed": true,  # Optional: toggle completion
            "text": "Updated text"  # Optional: update text
        }
    
    Returns:
        JSON response with all todos
    
    Example:
        PUT /api/todos/1698765432000
        Body: {"completed": true}
        Response: {
            "success": true,
            "todos": [...]
        }
    """
    try:
        data = request.get_json()
        todos = load_todos()
        
        todo_found = False
        for todo in todos:
            if todo['id'] == todo_id:
                todo_found = True
                if 'completed' in data:
                    todo['completed'] = data['completed']
                if 'text' in data:
                    todo['text'] = data['text'].strip()
                todo['updatedAt'] = datetime.now().isoformat()
                break
        
        if not todo_found:
            return jsonify({'success': False, 'error': 'Todo not found'}), 404
        
        if save_todos(todos):
            return jsonify({'success': True, 'todos': todos}), 200
        else:
            return jsonify({'success': False, 'error': 'Failed to save todo'}), 500
            
    except Exception as e:
        log.error(f"Error updating todo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@todos_bp.route('/api/todos/<todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """
    Delete a todo
    
    Returns:
        JSON response with remaining todos
    
    Example:
        DELETE /api/todos/1698765432000
        Response: {
            "success": true,
            "todos": [...]
        }
    """
    try:
        todos = load_todos()
        original_length = len(todos)
        todos = [todo for todo in todos if todo['id'] != todo_id]
        
        if len(todos) == original_length:
            return jsonify({'success': False, 'error': 'Todo not found'}), 404
        
        if save_todos(todos):
            log.info(f"Deleted todo {todo_id}")
            return jsonify({'success': True, 'todos': todos}), 200
        else:
            return jsonify({'success': False, 'error': 'Failed to save todos'}), 500
            
    except Exception as e:
        log.error(f"Error deleting todo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
