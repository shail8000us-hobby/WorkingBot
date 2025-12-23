# Flask API Refactoring - Implementation Guide

**Status**: ✅ Structure Created | ⏳ Implementation In Progress  
**Date**: October 31, 2025  
**Completed**: 2/16 blueprints | 3/133 routes migrated  

---

## 🎯 WHAT'S BEEN DELIVERED

### ✅ Completed Files

1. **`routes/__init__.py`** - Blueprint export module ✅
2. **`routes/utility.py`** - Complete blueprint (3 routes) ✅
3. **`FLASK_REFACTORING_PLAN.md`** - Master strategy document ✅
4. **`FLASK_REFACTORING_IMPLEMENTATION_GUIDE.md`** - This document ✅

### 📝 Blueprints Remaining

Need to create 14 more blueprint files:
- `health.py` (3 routes)
- `docs.py` (3 routes)
- `metrics.py` (2 routes)
- `websocket_api.py` (2 routes)
- `logs.py` (3+ routes)
- `pnl.py` (multiple routes)
- `orders.py` (multiple routes)
- `positions.py` (2+ routes)
- `config.py` (5+ routes)
- `system.py` (3 routes)
- `monitor.py` (3 routes)
- `guardian.py` (3 routes)
- `tmux.py` (3 routes)
- `bot_control.py` (5+ routes)
- `robustness.py` (multiple routes)

---

## 📖 PATTERN: utility.py (REFERENCE IMPLEMENTATION)

The completed `routes/utility.py` demonstrates the blueprint pattern:

### Structure
```python
"""
[Domain] Routes Blueprint

Routes:
- [List all routes this blueprint handles]

Dependencies:
- [Key dependencies]
"""

import sys
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request

# Initialize logger
log = logging.getLogger(__name__)

# Create blueprint
[domain]_bp = Blueprint('[domain]', __name__)

# ============================================================================
# Helper Functions (private to this blueprint)
# ============================================================================

def _helper_function():
    """Private helper"""
    pass

# ============================================================================
# Route Handlers
# ============================================================================

@[domain]_bp.route('/api/path', methods=['GET'])
def route_handler():
    """
    Route description
    
    Returns:
        JSON response
    """
    try:
        # Implementation
        return jsonify({'success': True}), 200
    except Exception as e:
        log.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
```

### Key Features
1. **Clear header documentation** - Lists all routes
2. **Imports at top** - All dependencies imported
3. **Blueprint creation** - `[domain]_bp = Blueprint('[domain]', __name__)`
4. **Helper functions** - Private helpers start with `_`
5. **Route decorators** - `@[domain]_bp.route()` (not `@app.route()`)
6. **Error handling** - Try/except in every route
7. **Type hints** - Where appropriate
8. **Docstrings** - Complete documentation

---

## 🚀 HOW TO CREATE REMAINING BLUEPRINTS

### Step 1: Find Routes in app.py

For each domain, find all routes in `app.py`:

```bash
# Example: Find all health-related routes
grep -n "@app.route('/api/health" webui/backend/app.py
grep -n "@app.route('/api/version" webui/backend/app.py
```

**health.py routes** (example):
- Line 3218: `/api/health` (GET)
- Line 3287: `/api/version` (GET)
- Line 3355: `/api/health/detailed` (GET)

### Step 2: Extract Route Handler Code

Copy the entire route handler function:

```python
# From app.py line 3218:
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint..."""
    try:
        # ... implementation ...
        return jsonify({...})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Step 3: Convert to Blueprint

Change `@app.route` to `@[domain]_bp.route`:

```python
# In routes/health.py:
@health_bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint..."""
    try:
        # ... same implementation ...
        return jsonify({...})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Step 4: Extract Helper Functions

If the route uses helper functions, copy them too:

```python
# From app.py:
def is_bot_running():
    """Check if bot is running"""
    # ... implementation ...

# To routes/health.py (if only used by health routes):
def _is_bot_running():
    """Check if bot is running"""
    # ... implementation ...
```

**OR** if used by multiple blueprints, move to `webui/backend/utils/process_helpers.py`

### Step 5: Fix Imports

Add all necessary imports at the top:

```python
import os
import sys
import time
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request

# Add any dependencies the route needs
try:
    import psutil
except ImportError:
    psutil = None
```

### Step 6: Test Mentally

- Does the route have all its dependencies?
- Are helper functions included?
- Are decorators converted (`@app.route` → `@[domain]_bp.route`)?
- Is error handling preserved?
- Are imports complete?

---

## 📋 EXTRACTION CHECKLIST (Use This!)

For each blueprint you create, check these boxes:

```markdown
Blueprint: ____________

Discovery:
- [ ] Found all routes for this domain in app.py (line numbers noted)
- [ ] Identified all helper functions used by these routes
- [ ] Identified all dependencies (imports, external modules)

Extraction:
- [ ] Created routes/[domain].py file
- [ ] Added header docstring with route list
- [ ] Added all imports
- [ ] Created blueprint: [domain]_bp = Blueprint('[domain]', __name__)
- [ ] Copied all route handlers
- [ ] Converted @app.route to @[domain]_bp.route
- [ ] Copied all helper functions (or moved to utils/)
- [ ] Added error handling to all routes

Verification:
- [ ] No @app.route decorators (should be @[domain]_bp.route)
- [ ] All imports resolve
- [ ] No circular import issues
- [ ] Helper functions either in file or utils/
- [ ] Error responses match original format

Integration:
- [ ] Added blueprint import to routes/__init__.py
- [ ] Added to __all__ list in routes/__init__.py
- [ ] Tested import: python -c "from routes.[domain] import [domain]_bp"
```

---

## 🗺️ DETAILED BLUEPRINT ROADMAP

### 1. health.py (NEXT - Do This First!)

**Routes** (3):
- `GET /api/health` (line 3218)
- `GET /api/version` (line 3287)
- `GET /api/health/detailed` (line 3355)

**Helper Functions**:
- `is_bot_running()` → move to utils/process_helpers.py
- `is_monitor_running()` → move to utils/process_helpers.py
- `is_guardian_running()` → move to utils/process_helpers.py
- `get_telegram_health()` → keep in health.py (specific to health)

**Dependencies**:
- psutil (for process checks)
- get_health_checker() (from utils)
- time, os, sys

**Estimated Lines**: ~400

---

### 2. docs.py

**Routes** (3):
- `GET /api/help/registry` (line 3477)
- `GET /api/docs/capital-protection` (find line)
- `GET /api/docs/<path:filename>` (find line)

**Helper Functions**:
- File reading helpers
- Markdown/HTML rendering helpers

**Dependencies**:
- send_from_directory
- Path, os

**Estimated Lines**: ~300

---

### 3. metrics.py

**Routes** (2):
- `GET /api/metrics/queue` (line 3333)
- `GET /api/metrics/circuit-breakers` (line 3344)

**Helper Functions**:
- `queue_metrics_endpoint()` → keep here
- `get_all_circuit_breaker_states()` → keep here

**Dependencies**:
- Resource fix utilities (timeout decorators)
- Queue/circuit breaker utilities

**Estimated Lines**: ~300

---

### 4. websocket_api.py

**Routes** (2):
- `GET /api/websocket/health` (line 3380)
- `GET /api/websocket/stats` (line 3434)

**Helper Functions**:
- WebSocket health checking
- Stats aggregation

**Dependencies**:
- Bot process checks
- WebSocket connection state

**Estimated Lines**: ~400

---

### 5. logs.py

**Routes** (3+):
- `GET /api/logs` (line 3545)
- `GET /api/logs/recent` (line 3552)
- `GET /api/sync-report` (find line)
- `GET /api/shutdown-report` (find line)

**Helper Functions**:
- `get_recent_logs()` → keep here or utils/file_helpers.py
- Log file parsing

**Dependencies**:
- File I/O
- Log parsing utilities

**Estimated Lines**: ~400

---

### 6. pnl.py

**Routes** (multiple):
- `GET /api/pnl-history` (find line)
- `GET /api/pnl-history/hourly` (find line)
- Related PNL endpoints

**Helper Functions**:
- PNL calculation functions
- Data aggregation

**Dependencies**:
- numpy (for calculations)
- Positions/orders data

**Estimated Lines**: ~500

---

### 7. orders.py

**Routes** (multiple):
- `GET /api/orders` (find line)
- Related order endpoints

**Helper Functions**:
- Order data retrieval
- Order formatting

**Dependencies**:
- API client
- Data formatting utilities

**Estimated Lines**: ~400

---

### 8. positions.py

**Routes** (2+):
- `GET /api/positions` (find line)
- `POST /api/positions/resync` (line 780)
- `GET /api/state` (find line)

**Helper Functions**:
- `resync_positions_from_reconciliation()` → keep here
- Position loading
- State loading

**Dependencies**:
- bot.state.store
- Reconciliation engine

**Estimated Lines**: ~500

---

### 9. config.py (COMPLEX)

**Routes** (5+):
- `GET /api/config` (line 2568)
- `POST /api/config` (line 2599)
- `GET /api/config/verify` (line 2822)
- `POST /api/config/apply` (line 2859)
- `GET /api/diagnostics/config-usage` (line 2580)

**Helper Functions**:
- `get_structured_config()` → keep here
- Config validation
- Hot reload logic
- Legacy alias handling

**Dependencies**:
- dotenv
- Config utilities
- Atomic file writes

**Estimated Lines**: ~700

---

### 10. system.py

**Routes** (3):
- `GET /api/system/status` (line 2897)
- `GET /api/trading-mode` (line 3127)
- `POST /api/trading-mode` (line 3142)

**Helper Functions**:
- System health checks
- Trading mode switching

**Dependencies**:
- Process management
- Mode configuration

**Estimated Lines**: ~400

---

### 11. monitor.py

**Routes** (3):
- `GET /api/monitor/status` (line 2719)
- `POST /api/monitor/start` (line 2725)
- `POST /api/monitor/stop` (line 2732)

**Helper Functions**:
- `is_monitor_running()` → from utils/process_helpers.py
- `start_monitor()` → keep here
- `stop_monitor()` → keep here

**Dependencies**:
- Process management
- PID file handling

**Estimated Lines**: ~300

---

### 12. guardian.py

**Routes** (3):
- `GET /api/guardian/status` (line 2739)
- `POST /api/guardian/start` (line 2751)
- `POST /api/guardian/stop` (line 2780)

**Helper Functions**:
- `is_guardian_running()` → from utils/process_helpers.py
- `start_guardian()` → keep here (guardian-specific)
- `stop_guardian()` → keep here

**Dependencies**:
- Process management
- Guardian configuration

**Estimated Lines**: ~400

---

### 13. tmux.py

**Routes** (3):
- `GET /api/tmux/status` (line 578)
- `POST /api/tmux/start` (line 621)
- `POST /api/tmux/stop` (line 628)

**Helper Functions**:
- `get_tmux_path()` (line 377) → keep here
- `get_tmux_socket_path()` (line 400) → keep here
- `get_tmux_command()` (line 407) → keep here
- `is_tmux_installed()` (line 414) → keep here
- `get_tmux_session_status()` (line 423) → keep here
- `start_bots_with_tmux()` (line 479) → keep here
- `stop_tmux_session()` (line 532) → keep here

**Dependencies**:
- subprocess
- Tmux socket handling

**Estimated Lines**: ~500

---

### 14. bot_control.py (COMPLEX)

**Routes** (5+):
- `GET /api/bot/status` (line 2645)
- `POST /api/bot/start` (line 2651)
- `POST /api/bot/stop` (line 2689)
- `POST /api/bot/restart` (line 2802)
- `GET /api/bots/status` (line 2917)
- `POST /api/bots/stop` (line 3028)

**Helper Functions**:
- Bot process management
- Status checking
- Multi-bot coordination

**Dependencies**:
- Process helpers
- Rate limiting
- PID management

**Estimated Lines**: ~700

---

### 15. robustness.py

**Routes** (multiple):
- `GET /api/robustness/gatekeeper/status` (find line)
- `GET /api/robustness/loss-limits` (find line)
- `GET /api/robustness/circuit-breakers` (find line)
- `POST /api/robustness/circuit-breakers/reset` (find line)
- `GET /api/robustness/audit/report` (find line)

**Helper Functions**:
- Gatekeeper integration
- Loss limit tracking
- Circuit breaker management

**Dependencies**:
- Robustness utilities
- Circuit breaker library

**Estimated Lines**: ~500

---

## 🔧 SHARED UTILITIES TO CREATE

### utils/process_helpers.py

```python
"""
Shared process management utilities
"""

import os
import signal
from pathlib import Path
from typing import Optional

def is_process_running(pid: int) -> bool:
    """Check if process with given PID is running"""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

def read_pid_file(filepath: Path) -> Optional[int]:
    """Read PID from file, return None if doesn't exist"""
    try:
        if filepath.exists():
            with open(filepath, 'r') as f:
                return int(f.read().strip())
    except (ValueError, IOError):
        return None
    return None

def stop_process_by_pid(pid: int, timeout: int = 5) -> bool:
    """Stop process gracefully (SIGTERM), then forcefully (SIGKILL)"""
    try:
        os.kill(pid, signal.SIGTERM)
        # Wait for process to exit
        import time
        for _ in range(timeout * 10):
            if not is_process_running(pid):
                return True
            time.sleep(0.1)
        # Force kill
        os.kill(pid, signal.SIGKILL)
        return True
    except Exception:
        return False

# Constants
BOT_PID_FILE = Path("reports/bot.pid")
GUARDIAN_PID_FILE = Path("reports/guardian.pid")
MONITOR_PID_FILE = Path("reports/monitor.pid")

def is_bot_running() -> bool:
    """Check if bot is running"""
    pid = read_pid_file(BOT_PID_FILE)
    return pid is not None and is_process_running(pid)

def is_guardian_running() -> bool:
    """Check if guardian is running"""
    pid = read_pid_file(GUARDIAN_PID_FILE)
    return pid is not None and is_process_running(pid)

def is_monitor_running() -> bool:
    """Check if monitor is running"""
    pid = read_pid_file(MONITOR_PID_FILE)
    return pid is not None and is_process_running(pid)
```

### utils/file_helpers.py

```python
"""
Shared file operation utilities
"""

from pathlib import Path
from typing import List, Optional

def get_recent_logs(lines: int = 100) -> List[str]:
    """Get recent log lines from bot log file"""
    log_file = Path("logs/gridbot.log")
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
    except Exception as e:
        return [f"Error reading logs: {e}"]

def read_file_safely(filepath: Path, default: Optional[str] = None) -> Optional[str]:
    """Read file with error handling"""
    try:
        if filepath.exists():
            with open(filepath, 'r') as f:
                return f.read()
    except Exception:
        pass
    return default
```

### utils/response_helpers.py

```python
"""
Shared response formatting utilities
"""

import numpy as np
from typing import Any

def convert_numpy_types(obj: Any) -> Any:
    """Recursively convert numpy types to native Python types for JSON"""
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj
```

---

## 📝 FINAL APP.PY STRUCTURE

After all blueprints are created, replace `app.py` with:

```python
#!/usr/bin/env python3
"""
GridBot Web UI - Backend Server
Flask + SocketIO server (Refactored Architecture)

BEFORE: 8,850 lines, 133 routes, 233 functions
AFTER:  ~150 lines + 15 blueprint modules

Refactored: 2025-10-31
"""

import os
import sys
from pathlib import Path

# Setup paths and environment (keep existing setup code)
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load environment (keep existing env loading)
from dotenv import load_dotenv
# ... (keep all env loading code)

# Flask imports
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_compress import Compress

# Import all blueprints
from routes import (
    utility_bp, health_bp, docs_bp, metrics_bp, websocket_api_bp,
    logs_bp, pnl_bp, orders_bp, positions_bp, config_bp,
    system_bp, monitor_bp, guardian_bp, tmux_bp, bot_control_bp,
    robustness_bp
)

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

# CORS configuration (keep existing CORS setup)
CORS(app, origins=FLASK_CORS_ORIGINS, supports_credentials=True)

# Compression
Compress(app)

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

app.register_blueprint(utility_bp)
app.register_blueprint(health_bp)
app.register_blueprint(docs_bp)
app.register_blueprint(metrics_bp)
app.register_blueprint(websocket_api_bp)
app.register_blueprint(logs_bp)
app.register_blueprint(pnl_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(positions_bp)
app.register_blueprint(config_bp)
app.register_blueprint(system_bp)
app.register_blueprint(monitor_bp)
app.register_blueprint(guardian_bp)
app.register_blueprint(tmux_bp)
app.register_blueprint(bot_control_bp)
app.register_blueprint(robustness_bp)

print(f"✅ Registered {len(app.blueprints)} blueprints")

# ============================================================================
# Global Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found', 'path': request.path}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

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
# SocketIO Events (keep existing SocketIO handlers)
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print(f"🔌 Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print(f"🔌 Client disconnected: {request.sid}")

# ... (keep other SocketIO handlers)

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    print("=" * 80)
    print("🚀 GridBot WebUI Backend (Refactored)")
    print("=" * 80)
    print(f"   Blueprints: {len(app.blueprints)}")
    print(f"   Routes: {len([r for r in app.url_map.iter_rules()])}")
    print(f"   Port: 5001")
    print("=" * 80)
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=5001,
        debug=True,
        use_reloader=True
    )
```

---

## ✅ VERIFICATION STEPS

After completing all blueprints:

### 1. Check All Imports Work
```bash
cd webui/backend
python -c "from routes import *; print('✅ All blueprints import successfully')"
```

### 2. Count Routes
```python
from app import app
routes = [str(rule) for rule in app.url_map.iter_rules()]
print(f"Total routes: {len(routes)}")
# Should be 133+
```

### 3. Test Sample Endpoints
```bash
# Start server
python app.py

# In another terminal:
curl http://localhost:5001/api/health
curl http://localhost:5001/api/version
curl http://localhost:5001/api/bot/status
```

### 4. Check File Sizes
```bash
wc -l webui/backend/app.py
# Should be <200 lines

wc -l webui/backend/routes/*.py
# Each should be 300-700 lines
```

---

## 📊 PROGRESS TRACKER

```
Blueprint Progress: [██░░░░░░░░░░░░░░] 2/16 (12.5%)
Route Migration: [░░░░░░░░░░░░░░░░░░] 3/133 (2.3%)
```

### Completed ✅
- [x] routes/__init__.py
- [x] routes/utility.py (3 routes)

### In Progress ⏳
- [ ] routes/health.py (3 routes) ← DO THIS NEXT
- [ ] routes/docs.py (3 routes)
- [ ] routes/metrics.py (2 routes)
- [ ] routes/websocket_api.py (2 routes)
- [ ] routes/logs.py (3+ routes)
- [ ] routes/pnl.py (multiple routes)
- [ ] routes/orders.py (multiple routes)
- [ ] routes/positions.py (2+ routes)
- [ ] routes/config.py (5+ routes)
- [ ] routes/system.py (3 routes)
- [ ] routes/monitor.py (3 routes)
- [ ] routes/guardian.py (3 routes)
- [ ] routes/tmux.py (3 routes)
- [ ] routes/bot_control.py (5+ routes)
- [ ] routes/robustness.py (multiple routes)

### Not Started ⏳
- [ ] webui/backend/utils/process_helpers.py
- [ ] webui/backend/utils/file_helpers.py
- [ ] webui/backend/utils/response_helpers.py
- [ ] New app.py (<200 lines)

---

## 🎯 IMMEDIATE NEXT STEPS

1. **Create health.py** - Use utility.py as template
2. **Extract routes from app.py** (lines 3218, 3287, 3355)
3. **Move shared helpers to utils/**
4. **Test import**: `python -c "from routes.health import health_bp"`
5. **Repeat for remaining 13 blueprints**

---

## 📚 REFERENCE

- **Original file**: `webui/backend/app.py` (8,850 lines) - DO NOT DELETE
- **Pattern reference**: `webui/backend/routes/utility.py`
- **Master plan**: `FLASK_REFACTORING_PLAN.md`
- **This guide**: `FLASK_REFACTORING_IMPLEMENTATION_GUIDE.md`

---

**Status**: Ready to continue implementation  
**Next Action**: Create `routes/health.py` following utility.py pattern  
**Estimated Time Remaining**: 4-5 hours  
**Confidence**: HIGH (proven pattern, clear roadmap)  

🚀 **Let's continue refactoring!**
