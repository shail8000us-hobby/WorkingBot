#!/usr/bin/env python3
"""
Development server with auto-reload
Watches for file changes and automatically restarts the backend
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

if __name__ == '__main__':
    # Use Flask's built-in reloader
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = '1'
    
    from app import app, socketio
    
    print("🔄 Development server with auto-reload enabled")
    print("📝 Watching for file changes...")
    print("🌐 Backend will restart automatically on code changes")
    
    # Run with reloader enabled
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True,
        log_output=True
    )
