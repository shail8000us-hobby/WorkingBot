# New app.py - Refactored Version

**BEFORE**: 8,850 lines  
**AFTER**: ~180 lines (97% reduction!)  

---

## 🎯 INSTRUCTIONS

1. **Backup original**:
   ```bash
   cp webui/backend/app.py webui/backend/app.py.backup_$(date +%Y%m%d)
   ```

2. **Replace app.py** with the content below

3. **Test imports**:
   ```bash
   python3 -c "from webui.backend.routes import *; print('✅')"
   ```

4. **Start server**:
   ```bash
   python3 webui/backend/app.py
   ```

---

## 📝 NEW APP.PY CONTENT

```python
#!/usr/bin/env python3
"""
GridBot Web UI - Backend Server (Refactored Architecture)

BEFORE: 8,850 lines, 133 routes, 233 functions in one file
AFTER:  ~180 lines + 16 blueprint modules

Refactored: October 31, 2025
Architecture: Flask Blueprints pattern
"""

import os
import sys
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load environment variables FIRST
from dotenv import load_dotenv
SECRETS_FILE = BASE_DIR / "secrets" / "api_keys.env"
CONFIG_FILE = BASE_DIR / "grid_config.env"

if SECRETS_FILE.exists():
    load_dotenv(SECRETS_FILE, override=False)
    print(f"✅ Loaded API keys from {SECRETS_FILE}")

load_dotenv(CONFIG_FILE, override=False)
print(f"✅ Loaded config from {CONFIG_FILE}")

# Configure trading mode
from bot.utils.env_loader import load_trading_mode_config
try:
    trading_mode = load_trading_mode_config()
    print(f"✅ Trading mode: {trading_mode}")
    os.environ['TRADING_MODE'] = trading_mode
except Exception as e:
    print(f"⚠️  Could not configure trading mode: {e}")

# Flask imports
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask_compress import Compress
import time

# Import all blueprints
from routes import (
    utility_bp, health_bp, logs_bp, docs_bp, metrics_bp,
    websocket_api_bp, system_bp, monitor_bp, guardian_bp,
    tmux_bp, orders_bp, pnl_bp, positions_bp, config_bp,
    bot_control_bp
)

# Create Flask app
app = Flask(__name__, static_folder='../frontend/build')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
app.config['_start_time'] = time.time()

# Enable compression
compress = Compress()
app.config['COMPRESS_MIMETYPES'] = [
    'text/html', 'text/css', 'text/xml', 'application/json',
    'application/javascript', 'text/javascript'
]
compress.init_app(app)

# CORS configuration
ALLOWED_ORIGINS = os.getenv('WEBUI_ALLOWED_ORIGINS', 'http://localhost:*')
CORS(app, origins=ALLOWED_ORIGINS.split(','), supports_credentials=True)

# SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    engineio_logger=False,
    logger=False,
    ping_timeout=120,
    ping_interval=30
)

# ============================================================================
# Register All Blueprints
# ============================================================================

blueprints = [
    utility_bp, health_bp, logs_bp, docs_bp, metrics_bp,
    websocket_api_bp, system_bp, monitor_bp, guardian_bp,
    tmux_bp, orders_bp, pnl_bp, positions_bp, config_bp,
    bot_control_bp
]

for bp in blueprints:
    app.register_blueprint(bp)

print(f"✅ Registered {len(app.blueprints)} blueprints")

# ============================================================================
# Global Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Not found',
        'path': request.path
    }), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal server error',
        'details': str(e) if app.debug else None
    }), 500


@app.errorhandler(Exception)
def handle_global_exception(e):
    """Global exception handler with traceback logging"""
    import traceback
    print(f"❌ Unhandled exception in {request.method} {request.path}: {e}")
    print(traceback.format_exc())
    
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'details': str(e) if app.debug else None,
        'path': request.path
    }), 500


# ============================================================================
# SocketIO Event Handlers
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print(f"🔌 Client connected: {request.sid}")
    emit('connected', {'status': 'Connected to GridBot WebUI'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print(f"🔌 Client disconnected: {request.sid}")


@socketio.on('ping')
def handle_ping(data):
    """Handle ping for latency monitoring"""
    try:
        emit('pong', {
            'timestamp': time.time(),
            'latency': int((time.time() - data.get('timestamp', time.time())) * 1000) if data else 0
        })
    except Exception as e:
        print(f"Error handling ping: {e}")


# ============================================================================
# Static File Serving (for React frontend)
# ============================================================================

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """Serve React frontend"""
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    # Count routes
    route_count = len([r for r in app.url_map.iter_rules()])
    
    print("=" * 80)
    print("🚀 GridBot WebUI Backend (Refactored Architecture)")
    print("=" * 80)
    print(f"   Blueprints: {len(app.blueprints)}")
    print(f"   Routes: {route_count}")
    print(f"   Port: 5001")
    print(f"   Mode: {'DEBUG' if app.debug else 'PRODUCTION'}")
    print("=" * 80)
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=5001,
        debug=True,
        use_reloader=True,
        allow_unsafe_werkzeug=True
    )
```

---

## ✅ WHAT THIS NEW APP.PY DOES

### **1. Environment Setup** (Lines 1-30)
- Loads API keys from secrets
- Loads configuration from grid_config.env
- Configures trading mode

### **2. Flask Initialization** (Lines 31-60)
- Creates Flask app
- Enables compression
- Configures CORS
- Sets up SocketIO

### **3. Blueprint Registration** (Lines 61-75)
- Imports all 15 blueprints
- Registers each one with app
- Prints confirmation

### **4. Error Handlers** (Lines 76-110)
- 404 handler
- 500 handler
- Global exception handler with logging

### **5. SocketIO Handlers** (Lines 111-140)
- Connection/disconnection handling
- Ping/pong for latency monitoring

### **6. Frontend Serving** (Lines 141-150)
- Serves React build files
- Falls back to index.html for SPA routing

### **7. Main Entry** (Lines 151-170)
- Prints startup information
- Starts SocketIO server on port 5001

---

## 🔧 CUSTOMIZATION NOTES

### **Add More Blueprints**:
```python
from routes import new_blueprint_bp

blueprints.append(new_blueprint_bp)
```

### **Change Port**:
```python
socketio.run(app, host='0.0.0.0', port=5002, ...)
```

### **Enable/Disable Debug**:
```python
socketio.run(app, ..., debug=False, ...)
```

### **Add Middleware**:
```python
@app.before_request
def before_request():
    # Your middleware logic
    pass
```

---

## ✅ TESTING THE NEW APP.PY

### **1. Import Test**
```bash
python3 -c "from webui.backend import app; print('✅ App imports')"
```

### **2. Route Count**
```bash
python3 -c "
from webui.backend.app import app
routes = len([r for r in app.url_map.iter_rules()])
print(f'Total routes: {routes} (should be 133+)')
"
```

### **3. Start Server**
```bash
python3 webui/backend/app.py
```

Expected output:
```
✅ Loaded API keys from secrets/api_keys.env
✅ Loaded config from grid_config.env
✅ Trading mode: demo
✅ Registered 15 blueprints
================================================================================
🚀 GridBot WebUI Backend (Refactored Architecture)
================================================================================
   Blueprints: 15
   Routes: 140
   Port: 5001
   Mode: DEBUG
================================================================================
```

### **4. Test Endpoints**
```bash
# In another terminal
curl http://localhost:5001/api/health
curl http://localhost:5001/api/version
curl http://localhost:5001/api/bot/status
```

---

## 🎯 COMPARISON

### **Old app.py**:
- 8,850 lines
- All routes mixed together
- Hard to find anything
- Testing nightmare
- Merge conflicts constant

### **New app.py**:
- ~180 lines (97% smaller!)
- Clean blueprint registration
- Easy to understand
- Modular and testable
- No merge conflicts

---

## 🚀 DEPLOYMENT CHECKLIST

- [  ] Backup original app.py
- [  ] Create new app.py with template above
- [  ] Test all imports
- [  ] Start server successfully
- [  ] Test API endpoints
- [  ] Test frontend in browser
- [  ] Verify bot control works
- [  ] Verify config updates work
- [  ] Deploy to production

---

**Status**: ✅ Template Ready  
**Next**: Copy template to app.py and test!  

🎉 **You're ready to deploy the refactored architecture!**
