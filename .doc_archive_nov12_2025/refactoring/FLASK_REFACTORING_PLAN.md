# Flask API Refactoring - Complete Implementation Plan

**Date**: October 31, 2025  
**Task**: Refactor app.py (8,850 lines, 133 routes) → 15 Flask Blueprints  
**Pattern**: Proven GridBot refactoring approach (3,492 → 7 modules)  

---

## 📊 CURRENT STATE ANALYSIS

### File Statistics
- **File**: `webui/backend/app.py`
- **Lines**: 8,850 (2.5x worse than GridBot!)
- **Routes**: 133 API endpoints
- **Functions**: 233+ functions
- **Classes**: 4 classes

### Critical Issues
🔴 Unmaintainable monolith  
🔴 Every change risks breaking 133 endpoints  
🔴 Merge conflicts guaranteed  
🔴 Testing nightmare  
🔴 Security risk (shared context)  

---

## 🎯 TARGET ARCHITECTURE

### Blueprint Structure (15 Modules)

```
webui/backend/
├── app.py (<200 lines)              # Main Flask app + blueprint registration
│
└── routes/
    ├── __init__.py                  # ✅ CREATED - Blueprint exports
    │
    ├── utility.py (~300 lines)      # Frontend errors, performance logs, bot actions
    ├── health.py (~400 lines)       # Health checks, version, detailed health
    ├── docs.py (~300 lines)         # Documentation endpoints, help registry
    ├── metrics.py (~300 lines)      # Queue metrics, circuit breakers
    ├── websocket_api.py (~400 lines)# WebSocket health & stats
    ├── logs.py (~400 lines)         # Log retrieval, sync reports
    ├── pnl.py (~500 lines)          # PNL history, calculations
    ├── orders.py (~400 lines)       # Order data retrieval
    ├── positions.py (~500 lines)    # Position data, resync
    ├── config.py (~700 lines)       # Config get/set, verify, apply, diagnostics
    ├── system.py (~400 lines)       # System status, trading mode
    ├── monitor.py (~300 lines)      # Monitor control (start/stop/status)
    ├── guardian.py (~400 lines)     # Guardian control (start/stop/status)
    ├── tmux.py (~500 lines)         # Tmux session management
    ├── bot_control.py (~700 lines)  # Bot lifecycle (start/stop/restart/status)
    └── robustness.py (~500 lines)   # Gatekeeper, circuit breakers, audit
```

**Total**: 8,850 lines → 15 files (~590 lines each)

---

## 📋 ROUTE MAPPING (All 133 Routes)

### 1. utility.py (3 routes)
- `POST /api/frontend-error` - Log frontend errors
- `POST /api/performance-log` - Log performance metrics
- `GET  /api/bot-actions/recent` - Recent bot actions

### 2. health.py (3 routes)
- `GET /api/health` - Fast health check (<1ms)
- `GET /api/health/detailed` - Detailed health with circuit breakers
- `GET /api/version` - Backend version info

### 3. docs.py (3 routes)
- `GET /api/help/registry` - Help registry
- `GET /api/docs/capital-protection` - Capital protection docs
- `GET /api/docs/<path:filename>` - Documentation files

### 4. metrics.py (2 routes)
- `GET /api/metrics/queue` - Request queue metrics
- `GET /api/metrics/circuit-breakers` - Circuit breaker states

### 5. websocket_api.py (2 routes)
- `GET /api/websocket/health` - WebSocket health status
- `GET /api/websocket/stats` - Detailed WebSocket stats

### 6. logs.py (3 routes)
- `GET /api/logs` - Get recent logs
- `GET /api/logs/recent` - Recent logs (alias)
- `GET /api/sync-report` - Sync report
- `GET /api/shutdown-report` - Shutdown report

### 7. pnl.py (Multiple routes)
- `GET /api/pnl-history` - PNL history
- `GET /api/pnl-history/hourly` - Hourly PNL
- Related PNL calculation endpoints

### 8. orders.py (Multiple routes)
- `GET /api/orders` - Order data
- Related order management endpoints

### 9. positions.py (2+ routes)
- `GET /api/positions` - Position data
- `POST /api/positions/resync` - Resync positions
- `GET /api/state` - Runtime state

### 10. config.py (5+ routes)
- `GET  /api/config` - Get configuration
- `POST /api/config` - Update configuration
- `GET  /api/config/verify` - Verify config integrity
- `POST /api/config/apply` - Apply pending changes
- `GET  /api/diagnostics/config-usage` - Config usage stats

### 11. system.py (3 routes)
- `GET  /api/system/status` - System health status
- `GET  /api/trading-mode` - Get trading mode
- `POST /api/trading-mode` - Set trading mode

### 12. monitor.py (3 routes)
- `GET  /api/monitor/status` - Monitor status
- `POST /api/monitor/start` - Start monitor
- `POST /api/monitor/stop` - Stop monitor

### 13. guardian.py (3 routes)
- `GET  /api/guardian/status` - Guardian status
- `POST /api/guardian/start` - Start guardian
- `POST /api/guardian/stop` - Stop guardian

### 14. tmux.py (3 routes)
- `GET  /api/tmux/status` - Tmux session status
- `POST /api/tmux/start` - Start tmux session
- `POST /api/tmux/stop` - Stop tmux session

### 15. bot_control.py (5+ routes)
- `GET  /api/bot/status` - Bot status
- `POST /api/bot/start` - Start bot
- `POST /api/bot/stop` - Stop bot
- `POST /api/bot/restart` - Restart bot
- `GET  /api/bots/status` - All bots status
- `POST /api/bots/stop` - Stop bot by PID

### 16. robustness.py (Multiple routes)
- `GET  /api/robustness/gatekeeper/status` - Gatekeeper status
- `GET  /api/robustness/loss-limits` - Loss limits
- `GET  /api/robustness/circuit-breakers` - Circuit breakers
- `POST /api/robustness/circuit-breakers/reset` - Reset breakers
- `GET  /api/robustness/audit/report` - Audit report

---

## 🔧 HELPER FUNCTION MAPPING

### Shared Utilities (Move to webui/backend/utils/)

#### file_helpers.py
- `get_recent_logs()`
- `read_file_safely()`
- `atomic_write_json()`

#### process_helpers.py
- `_is_process_running()`
- `_read_pid_file()`
- `_stop_process_by_pid()`
- `get_tmux_path()`
- `get_tmux_socket_path()`

#### response_helpers.py
- `convert_numpy_types()`
- `_unauthorized_response()`

#### auth_helpers.py
- `_has_bearer_access()`
- `_has_basic_access()`
- `_request_is_authenticated()`

### Blueprint-Specific Helpers
- Keep helpers used by single blueprint in that blueprint file
- Move truly shared helpers to utils/

---

## 🚀 IMPLEMENTATION STEPS

### Phase 1: Setup (15 minutes)
```bash
# Create directory structure
mkdir -p webui/backend/routes
mkdir -p webui/backend/utils

# Already created:
# ✅ webui/backend/routes/__init__.py
```

### Phase 2: Extract Blueprints (One at a time, 3-4 hours total)

**Extraction Order** (dependency-sorted, simplest first):

1. ✅ **utility.py** - 3 simple routes, minimal dependencies
2. ⏳ **health.py** - 3 status routes, uses cached state
3. ⏳ **docs.py** - 3 documentation routes, file serving
4. ⏳ **metrics.py** - 2 metrics routes
5. ⏳ **websocket_api.py** - 2 WebSocket stat routes
6. ⏳ **logs.py** - Log file reading
7. ⏳ **pnl.py** - PNL calculations
8. ⏳ **orders.py** - Order data
9. ⏳ **positions.py** - Position data + resync
10. ⏳ **config.py** - Config management (complex)
11. ⏳ **system.py** - System status
12. ⏳ **monitor.py** - Monitor control
13. ⏳ **guardian.py** - Guardian control
14. ⏳ **tmux.py** - Tmux management
15. ⏳ **bot_control.py** - Bot lifecycle (most complex)
16. ⏳ **robustness.py** - Robustness features

### Phase 3: Refactor Main App (30 minutes)

Create new slim `app.py` (~150-200 lines):
```python
#!/usr/bin/env python3
"""
GridBot Web UI - Backend Server
Flask + SocketIO server (Refactored Architecture)

BEFORE: 8,850 lines, 133 routes, 233 functions
AFTER:  ~150 lines + 15 blueprint modules

Refactored: 2025-10-31
"""

from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO

# Import all blueprints
from routes import (
    utility_bp, health_bp, docs_bp, metrics_bp, websocket_api_bp,
    logs_bp, pnl_bp, orders_bp, positions_bp, config_bp,
    system_bp, monitor_bp, guardian_bp, tmux_bp, bot_control_bp,
    robustness_bp
)

# Flask app setup
app = Flask(__name__)
CORS(app, origins=FLASK_CORS_ORIGINS)  # From config
socketio = SocketIO(app, cors_allowed_origins="*")

# Register all blueprints
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

# Global error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(Exception)
def handle_global_exception(e):
    """Global exception handler"""
    import traceback
    print(f"❌ Unhandled exception: {e}")
    print(traceback.format_exc())
    return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
```

### Phase 4: Create Shared Utilities (1 hour)

Extract truly shared functions to `webui/backend/utils/`:

**utils/file_helpers.py**
```python
"""Shared file operation utilities"""

def get_recent_logs(lines=100):
    """Get recent log lines"""
    # Implementation from app.py
    pass

def read_file_safely(filepath, default=None):
    """Read file with error handling"""
    # Implementation
    pass
```

**utils/process_helpers.py**
```python
"""Shared process management utilities"""

import os
import signal
from pathlib import Path
from typing import Optional

def is_process_running(pid: int) -> bool:
    """Check if process is running"""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

def read_pid_file(filepath: Path) -> Optional[int]:
    """Read PID from file"""
    try:
        if filepath.exists():
            with open(filepath, 'r') as f:
                return int(f.read().strip())
    except (ValueError, IOError):
        return None
    return None
```

---

## 📝 BLUEPRINT TEMPLATE

Use this template for each blueprint file:

```python
"""
[Domain Name] Routes Blueprint

This module handles all API routes related to [domain description].

Routes:
- [METHOD] [PATH] - [Description]
- [METHOD] [PATH] - [Description]

Dependencies:
- [List key dependencies]

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from flask import Blueprint, jsonify, request

# Initialize logger
log = logging.getLogger(__name__)

# Create blueprint
[domain]_bp = Blueprint('[domain]', __name__)

# ============================================================================
# Helper Functions (private to this blueprint)
# ============================================================================

def _helper_function_1():
    """Helper function description"""
    pass

# ============================================================================
# Route Handlers
# ============================================================================

@[domain]_bp.route('/api/[path]', methods=['GET'])
def route_handler_1():
    """
    Route description
    
    Returns:
        JSON response
    
    Example:
        GET /api/[path]
        Response: {"status": "ok"}
    """
    try:
        # Implementation
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        log.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
```

---

## ✅ VERIFICATION CHECKLIST

### After Each Blueprint
- [ ] All routes from domain included
- [ ] All helper functions copied
- [ ] Imports correct (no circular deps)
- [ ] Error handling preserved
- [ ] Docstrings complete

### Final Verification
- [ ] All 133 routes accounted for
- [ ] No duplicate routes
- [ ] All imports resolve
- [ ] Main app.py <200 lines
- [ ] Each blueprint 300-700 lines
- [ ] Tests pass (if any exist)

---

## 🎯 SUCCESS METRICS

### Quantitative
- **File count**: 1 → 16 files
- **Lines per file**: 8,850 → ~550 avg
- **Main app size**: 8,850 → <200 lines (97% reduction!)
- **Circular deps**: 0
- **Backward compat**: 100%

### Qualitative
- 10x easier to find routes
- 10x easier to test
- 95% reduction in merge conflicts
- Clear domain boundaries
- Easy to onboard new developers

---

## 📖 NEXT STEPS

1. **Review this plan** - Understand the structure
2. **Create utils/** - Extract shared utilities first
3. **Extract blueprints** - One at a time, following order above
4. **Refactor app.py** - Create slim orchestrator
5. **Test** - Verify all routes work
6. **Deploy** - Backup old app.py, deploy new structure

---

## 🔗 REFERENCE FILES

- **Original**: `webui/backend/app.py` (8,850 lines) - DO NOT DELETE (backup)
- **New structure**: `webui/backend/routes/` (15 blueprints)
- **Shared utils**: `webui/backend/utils/` (helper functions)
- **Main app**: `webui/backend/app.py` (new, <200 lines)

---

**Status**: Ready to implement  
**Estimated Time**: 4-6 hours total  
**Risk**: LOW (old code remains as backup)  
**Confidence**: HIGH (proven GridBot pattern)  

🚀 **Let's refactor!**
