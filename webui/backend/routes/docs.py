"""
Documentation Routes Blueprint

This module handles all API routes related to documentation and help systems.

Routes:
- GET /api/help/registry - Get help registry with action metadata

Dependencies:
- JSON file reading
- Help registry file

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import json
import logging
from pathlib import Path
from flask import Blueprint, jsonify

log = logging.getLogger(__name__)

# Create blueprint
docs_bp = Blueprint('docs', __name__)

# Constants
BASE_DIR = Path(__file__).parent.parent.parent.parent
HELP_REGISTRY_FILE = BASE_DIR / "webui" / "backend" / "help" / "help_registry.json"

# ============================================================================
# Route Handlers
# ============================================================================

@docs_bp.route('/api/help/registry', methods=['GET'])
def get_help_registry():
    """
    Get the help registry with all action metadata
    
    Returns help information for all UI actions with secrets automatically filtered.
    No authentication required.
    
    Returns:
        JSON response with help registry data
    
    Example:
        GET /api/help/registry
        Response: {
            "success": true,
            "actions": [
                {
                    "action_id": "bot.start",
                    "title": "Start Trading Bot",
                    "summary": "...",
                    "related_config": [...]
                },
                ...
            ],
            "count": 50,
            "generated_at": 1698765432.0
        }
    """
    try:
        if not HELP_REGISTRY_FILE.exists():
            return jsonify({
                'success': False,
                'message': 'Help registry not found. Run: python3 tools/help/extract_help_metadata.py',
                'actions': []
            }), 404
        
        # Load registry from JSON file
        with open(HELP_REGISTRY_FILE, 'r') as f:
            registry = json.load(f)
        
        # Filter out any secrets from related_config
        for action in registry:
            if 'related_config' in action:
                # Handle both formats: list of dicts (auto-generated) and list of strings (synthetic)
                filtered_config = []
                for config in action['related_config']:
                    if isinstance(config, dict):
                        # Auto-generated format: {"key": "CONFIG_KEY", "value": "val", "source": "file"}
                        if config.get('key') and not _is_secret_key(config['key']):
                            filtered_config.append(config)
                    elif isinstance(config, str):
                        # Synthetic format: just the key name as a string
                        if not _is_secret_key(config):
                            filtered_config.append(config)
                action['related_config'] = filtered_config
        
        return jsonify({
            'success': True,
            'actions': registry,
            'count': len(registry),
            'generated_at': HELP_REGISTRY_FILE.stat().st_mtime if HELP_REGISTRY_FILE.exists() else None
        }), 200
        
    except json.JSONDecodeError as e:
        log.error(f"Help registry JSON parse error: {e}")
        return jsonify({
            'success': False,
            'error': 'Invalid help registry format',
            'actions': []
        }), 500
        
    except Exception as e:
        log.error(f"Help registry fetch failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'actions': []
        }), 500


# ============================================================================
# Helper Functions
# ============================================================================

def _is_secret_key(key_name: str) -> bool:
    """
    Check if a config key name represents a secret that should be filtered
    
    Args:
        key_name: Configuration key name to check
        
    Returns:
        True if key represents a secret, False otherwise
    """
    secret_indicators = ['KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'CREDENTIALS']
    return any(secret in key_name.upper() for secret in secret_indicators)


# ============================================================================
# Documentation File Serving
# ============================================================================

@docs_bp.route('/api/docs/capital-protection', methods=['GET'])
def get_capital_protection_docs():
    """Get Capital Protection documentation"""
    try:
        doc_path = BASE_DIR / 'CAPITAL_PROTECTION_WEBUI_GUIDE.md'
        
        if not doc_path.exists():
            return jsonify({
                'success': False,
                'error': 'Capital Protection documentation not found'
            }), 404
        
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'content': content,
            'title': 'Capital Protection System - WebUI Documentation',
            'last_updated': doc_path.stat().st_mtime
        }), 200
    
    except Exception as e:
        log.error(f"Error getting capital protection docs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@docs_bp.route('/api/docs/<path:filename>')
def serve_docs(filename):
    """Serve markdown documentation files"""
    try:
        from flask import Response
        
        # Security: only allow .md files
        if not filename.endswith('.md'):
            return jsonify({'error': 'Only markdown files allowed'}), 403
        
        # Get the project root directory
        project_root = BASE_DIR
        doc_path = project_root / filename
        
        # Security: ensure the file is within project root
        if not str(doc_path.resolve()).startswith(str(project_root.resolve())):
            return jsonify({'error': 'Access denied'}), 403
        
        # Check if file exists
        if not doc_path.exists():
            return jsonify({'error': f'Documentation file not found: {filename}'}), 404
        
        # Read and return the file content
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Return as plain text with proper content type
        return Response(content, mimetype='text/markdown')
    
    except Exception as e:
        log.error(f"Error serving documentation: {e}")
        return jsonify({'error': str(e)}), 500
