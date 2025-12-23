"""
Code Explainer API Routes
Provides endpoints for explaining Python code in human language.
Integrates with narrator_core.py for AST analysis and explanation generation.
"""

from flask import Blueprint, request, jsonify
import sys
import os
from pathlib import Path
from typing import Optional

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import narrator core
try:
    from bot.utils.narrator_core import NarratorCore, ExplanationMode, CodeAnalysis
    NARRATOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Warning: Could not import narrator_core: {e}")
    NARRATOR_AVAILABLE = False

code_explainer_bp = Blueprint('code_explainer', __name__)


@code_explainer_bp.route('/explain', methods=['POST'])
def explain_code():
    """
    Explain Python code in human language.
    
    Request Body:
    {
        "file_path": "path/to/file.py",  # Required - relative path from project root
        "mode": "simple",                # Optional - simple/trader/tech (default: trader)
        "code": "print('hello')"         # Optional - direct code string (overrides file_path)
    }
    
    Response:
    {
        "status": "success",
        "explanation": "...",
        "statistics": {...},
        "functions": [...],
        "classes": [...],
        "issues": [...],
        "mode": "trader"
    }
    """
    if not NARRATOR_AVAILABLE:
        return jsonify({
            "status": "error",
            "message": "Code explanation feature is not available. Missing narrator_core module."
        }), 500
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "Request body is required"
            }), 400
        
        # Get parameters
        file_path = data.get('file_path')
        code_string = data.get('code')
        mode_str = data.get('mode', 'trader').lower()
        
        # Validate mode
        mode_map = {
            'simple': ExplanationMode.SIMPLE,
            'trader': ExplanationMode.TRADER,
            'tech': ExplanationMode.TECH
        }
        
        if mode_str not in mode_map:
            return jsonify({
                "status": "error",
                "message": f"Invalid mode. Choose from: simple, trader, tech"
            }), 400
        
        mode = mode_map[mode_str]
        
        # Initialize narrator
        narrator = NarratorCore(mode=mode)
        
        # Analyze code
        if code_string:
            # Direct code string analysis - write to temp file
            import tempfile
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code_string)
                    temp_path = f.name
                
                analysis = narrator.analyze_file(temp_path)
                
                # Clean up temp file
                os.unlink(temp_path)
            except Exception as e:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.unlink(temp_path)
                return jsonify({
                    "status": "error",
                    "message": f"Failed to analyze code: {str(e)}"
                }), 400
        elif file_path:
            # File path analysis
            # Resolve path relative to project root
            full_path = os.path.join(project_root, file_path)
            
            if not os.path.exists(full_path):
                return jsonify({
                    "status": "error",
                    "message": f"File not found: {file_path}"
                }), 404
            
            if not full_path.endswith('.py'):
                return jsonify({
                    "status": "error",
                    "message": "Only Python (.py) files can be explained"
                }), 400
            
            try:
                analysis = narrator.analyze_file(full_path)
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": f"Failed to analyze file: {str(e)}"
                }), 400
        else:
            return jsonify({
                "status": "error",
                "message": "Either 'file_path' or 'code' must be provided"
            }), 400
        
        # Generate explanation
        explanation = narrator.generate_file_summary(analysis)
        
        # Build response
        response = {
            "status": "success",
            "mode": mode_str,
            "explanation": explanation,
            "statistics": {
                "total_lines": analysis.total_lines,
                "functions_count": len(analysis.functions),
                "classes_count": len(analysis.classes),
                "imports_count": len(analysis.imports),
                "complexity_score": analysis.complexity_score,
                "issues_count": len(analysis.issues)
            },
            "functions": [
                {
                    "name": f.name,
                    "async": f.is_async,
                    "args": f.args,
                    "returns": f.returns,
                    "complexity": f.complexity,
                    "line_start": f.line_start,
                    "line_end": f.line_end,
                    "docstring": f.docstring
                }
                for f in analysis.functions
            ],
            "classes": [
                {
                    "name": c.name,
                    "bases": c.bases,
                    "methods_count": len(c.methods),
                    "methods": [m.name for m in c.methods],
                    "line_start": c.line_start,
                    "line_end": c.line_end,
                    "docstring": c.docstring
                }
                for c in analysis.classes
            ],
            "issues": [
                {
                    "type": issue[0].value,
                    "description": issue[1],
                    "line": issue[2]
                }
                for issue in analysis.issues
            ],
            "imports": analysis.imports
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        print(f"❌ Code explainer error: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500


@code_explainer_bp.route('/modes', methods=['GET'])
def get_modes():
    """
    Get available explanation modes.
    
    Response:
    {
        "status": "success",
        "modes": [
            {
                "id": "simple",
                "name": "Simple",
                "description": "For beginners and non-coders. Uses everyday language."
            },
            ...
        ]
    }
    """
    modes = [
        {
            "id": "simple",
            "name": "Simple",
            "description": "For beginners and non-coders. Uses everyday language, no technical jargon.",
            "icon": "🎓"
        },
        {
            "id": "trader",
            "name": "Trader",
            "description": "For traders and business users. Focuses on what the code does in trading context.",
            "icon": "📊"
        },
        {
            "id": "tech",
            "name": "Technical",
            "description": "For developers. Detailed technical analysis with code patterns and best practices.",
            "icon": "⚙️"
        }
    ]
    
    return jsonify({
        "status": "success",
        "modes": modes,
        "available": NARRATOR_AVAILABLE
    }), 200


@code_explainer_bp.route('/health', methods=['GET'])
def health_check():
    """Check if code explainer is available."""
    return jsonify({
        "status": "success",
        "available": NARRATOR_AVAILABLE,
        "message": "Code explainer is ready" if NARRATOR_AVAILABLE else "Narrator module not available"
    }), 200
