"""
File Manager API Routes
Provides file browsing, reading, and writing capabilities for the File Editor
"""

from flask import Blueprint, request, jsonify
import os
from pathlib import Path
import mimetypes

file_manager_bp = Blueprint('file_manager', __name__)

# Base directory (project root)
BASE_DIR = Path(__file__).parent.parent.parent.parent.absolute()

# Allowed extensions for safety
ALLOWED_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.yaml', '.yml',
    '.md', '.txt', '.log', '.env', '.sh', '.cfg', '.conf', '.ini'
}

# Blocked paths for security
BLOCKED_PATHS = {
    '.git', '__pycache__', 'node_modules', '.env', 'venv', 'env',
    '.DS_Store', '*.pyc', '*.pyo', '*.so', '*.dylib'
}

def is_safe_path(path):
    """Check if path is safe to access"""
    path_parts = Path(path).parts
    
    # Block hidden files and dangerous directories
    for part in path_parts:
        if part.startswith('.') and part not in ['.', '..']:
            if part in BLOCKED_PATHS:
                return False
        if part in BLOCKED_PATHS:
            return False
    
    # Ensure path is within BASE_DIR
    full_path = (BASE_DIR / path).resolve()
    try:
        full_path.relative_to(BASE_DIR)
        return True
    except ValueError:
        return False

def get_file_type(filename):
    """Determine file type and icon"""
    ext = Path(filename).suffix.lower()
    if ext in {'.py'}:
        return 'python'
    elif ext in {'.js', '.jsx'}:
        return 'javascript'
    elif ext in {'.ts', '.tsx'}:
        return 'typescript'
    elif ext in {'.json'}:
        return 'json'
    elif ext in {'.yaml', '.yml'}:
        return 'yaml'
    elif ext in {'.md'}:
        return 'markdown'
    elif ext in {'.txt', '.log'}:
        return 'text'
    return 'unknown'

@file_manager_bp.route('/api/file-manager/list', methods=['POST'])
def list_directory():
    """List files and directories"""
    try:
        data = request.get_json() or {}
        path = data.get('path', '.')
        
        # Security check
        if not is_safe_path(path):
            return jsonify({
                'status': 'error',
                'message': 'Access denied to this path'
            }), 403
        
        full_path = BASE_DIR / path
        
        if not full_path.exists():
            return jsonify({
                'status': 'error',
                'message': 'Path does not exist'
            }), 404
        
        if not full_path.is_dir():
            return jsonify({
                'status': 'error',
                'message': 'Path is not a directory'
            }), 400
        
        items = []
        
        for item in sorted(full_path.iterdir()):
            # Skip blocked items
            if item.name in BLOCKED_PATHS or item.name.startswith('.'):
                continue
            
            item_info = {
                'name': item.name,
                'type': 'directory' if item.is_dir() else 'file',
                'path': str(item.relative_to(BASE_DIR))
            }
            
            if item.is_file():
                item_info['size'] = item.stat().st_size
                item_info['extension'] = item.suffix
                item_info['file_type'] = get_file_type(item.name)
            
            items.append(item_info)
        
        return jsonify({
            'status': 'success',
            'path': str(path),
            'items': items
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@file_manager_bp.route('/api/file-manager/read', methods=['POST'])
def read_file():
    """Read file contents"""
    try:
        data = request.get_json() or {}
        path = data.get('path', '')
        
        if not path:
            return jsonify({
                'status': 'error',
                'message': 'Path is required'
            }), 400
        
        # Security check
        if not is_safe_path(path):
            return jsonify({
                'status': 'error',
                'message': 'Access denied to this file'
            }), 403
        
        full_path = BASE_DIR / path
        
        if not full_path.exists():
            return jsonify({
                'status': 'error',
                'message': 'File does not exist'
            }), 404
        
        if not full_path.is_file():
            return jsonify({
                'status': 'error',
                'message': 'Path is not a file'
            }), 400
        
        # Check extension
        if full_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return jsonify({
                'status': 'error',
                'message': f'File type {full_path.suffix} not allowed'
            }), 403
        
        # Read file
        try:
            content = full_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Try with latin-1 for some log files
            content = full_path.read_text(encoding='latin-1')
        
        return jsonify({
            'status': 'success',
            'path': str(path),
            'content': content,
            'size': full_path.stat().st_size,
            'file_type': get_file_type(full_path.name)
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@file_manager_bp.route('/api/file-manager/save', methods=['POST'])
def save_file():
    """Save file contents"""
    try:
        data = request.get_json() or {}
        path = data.get('path', '')
        content = data.get('content', '')
        
        if not path:
            return jsonify({
                'status': 'error',
                'message': 'Path is required'
            }), 400
        
        # Security check
        if not is_safe_path(path):
            return jsonify({
                'status': 'error',
                'message': 'Access denied to this file'
            }), 403
        
        full_path = BASE_DIR / path
        
        # Check extension
        if full_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return jsonify({
                'status': 'error',
                'message': f'File type {full_path.suffix} not allowed'
            }), 403
        
        # Create backup if file exists
        if full_path.exists():
            backup_path = full_path.with_suffix(full_path.suffix + '.bak')
            full_path.rename(backup_path)
        
        # Write file
        full_path.write_text(content, encoding='utf-8')
        
        return jsonify({
            'status': 'success',
            'message': 'File saved successfully',
            'path': str(path)
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
