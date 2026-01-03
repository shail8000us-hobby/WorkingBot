#!/usr/bin/env python3
"""
GridBot Web UI - DEVELOPMENT Backend Server
Port: 5557
Environment: Development/Testing for v5.0 Multi-Symbol

⚠️  DO NOT USE IN PRODUCTION - This is for development only
✅  Production backend runs on port 5556 (managed by launchagent)
"""

import os
import sys

# Development environment marker
os.environ['WEBUI_ENV'] = 'development'
os.environ['FLASK_ENV'] = 'development'

# Force port 5557 for development
sys.argv = ['app_dev.py', '5557']

print("\n" + "="*70)
print("🔧 DEVELOPMENT WEBUI BACKEND")
print("="*70)
print(f"   Environment: DEVELOPMENT")
print(f"   Port: 5557")
print(f"   Debug: Enabled")
print(f"   CORS: Enabled for http://localhost:3001")
print(f"   Purpose: Testing v5.0 Multi-Symbol Features")
print("="*70)
print(f"⚠️  Production backend (5556) remains UNTOUCHED\n")

# Import and run the main app (it will use port from sys.argv)
if __name__ == '__main__':
    # Import app and socketio AFTER setting sys.argv to ensure port 5557 is used
    from app import app, socketio
    
    # Get port from sys.argv (we set it to 5557 above)
    WEBUI_PORT = int(sys.argv[1])
    
    # Verify port is correct
    print(f"✅ Development backend configured for port: {WEBUI_PORT}")
    
    if WEBUI_PORT != 5557:
        print(f"❌ ERROR: Port mismatch! Expected 5557, got {WEBUI_PORT}")
        sys.exit(1)
    
    # Start development server
    print(f"\n🚀 Starting development backend on port {WEBUI_PORT}...")
    print(f"📍 Access at: http://localhost:{WEBUI_PORT}")
    print(f"📍 Frontend dev server should use: http://localhost:3001\n")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=WEBUI_PORT,
        debug=True,  # Enable debug for development
        use_reloader=False,  # Disable reloader to avoid port conflicts
        allow_unsafe_werkzeug=True
    )


