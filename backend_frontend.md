# Backend & Frontend Documentation

**Last Updated:** March 11, 2026

## Port Configuration

### Production Setup

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| **Backend (Flask API)** | `5555` | REST API, WebSocket, Data endpoints | ✅ ACTIVE |
| **Frontend (Production)** | `5555` | Served by Flask backend | ✅ ACTIVE |
| **Frontend (Dev)** | `3000` | Development server (optional) | Use for UI development |

**Production Mode:**
- Backend runs on port 5555 via LaunchAgent (`python3 webui/backend/app.py` directly — no Gunicorn)
- Frontend production build served from `webui/frontend/build/`
- Single port architecture

> ⚠️ **DO NOT introduce Gunicorn.** It was tried and caused random crashes every few hours due to worker recycling (`max_requests`). Flask-SocketIO + `socketio.run()` is the correct stack for this single-user local dashboard.

> ⚠️ **CRITICAL FOR AI AGENTS:** The user accesses the app at **http://localhost:5555** (production mode only). Any change to a frontend source file under `webui/frontend/src/` is **invisible at :5555 until you run `npm run build` AND restart the backend**. Never assume a source edit is live — always rebuild and restart. Hot reload at :3000 is NOT used by this user.

---

## Development Workflows

### After Any Frontend Source Change (REQUIRED to see changes at :5555)
```bash
# Step 1: Build
cd webui/frontend && npm run build

# Step 2: Restart backend
launchctl stop com.gridbot.production.webui && sleep 2 && launchctl start com.gridbot.production.webui
# Access at: http://localhost:5555
```

### UI Development (Hot Reload) — only if user explicitly wants :3000
```bash
# Terminal 1: Start Backend
launchctl start com.gridbot.production.webui

# Terminal 2: Start Frontend Dev Server
cd webui/frontend
npm start
# Access at: http://localhost:3000
```

---

## Configuration Files

### Backend
**File:** `webui/backend/app.py`
```python
socketio.run(app, host='0.0.0.0', port=5555, debug=False)
```

**LaunchAgent service name:** `com.gridbot.production.webui`  
**LaunchAgent plist:** `~/Library/LaunchAgents/com.gridbot.production.webui.plist`

### Frontend
**File:** `webui/frontend/package.json`
```json
{
  "proxy": "http://localhost:5555",
  "scripts": {
    "start": "react-app-rewired start",
    "build": "react-app-rewired build"
  }
}
```

---

## Quick Reference

### Backend Management
```bash
# Start
launchctl start com.gridbot.production.webui

# Stop
launchctl stop com.gridbot.production.webui

# Restart
launchctl stop com.gridbot.production.webui && sleep 2 && launchctl start com.gridbot.production.webui

# Status
launchctl list | grep gridbot

# Logs (primary)
tail -f ~/Projects/WorkingBot/logs/webui_production.log

# Logs (errors)
tail -f ~/Projects/WorkingBot/logs/webui_production_error.log
```

### LaunchAgent plist
`~/Library/LaunchAgents/com.gridbot.production.webui.plist`

Runs: `.venv/bin/python3 webui/backend/app.py` — Flask-SocketIO's `socketio.run()` with `threading` async mode.

### Frontend Management
```bash
# Development
cd webui/frontend
npm start

# Production Build
cd webui/frontend
npm run build

# Kill Dev Server
pkill -f react-app-rewired
```

---

## Troubleshooting

### Backend Won't Start
```bash
# Check port usage
lsof -ti:5555

# Check LaunchAgent (correct service name)
launchctl list | grep gridbot

# View logs
tail -f ~/Projects/WorkingBot/logs/launchagent_webui_error.log
```

### Frontend Changes Not Showing at :5555
This is almost always because the production build wasn't rebuilt after source edits.
```bash
cd webui/frontend && npm run build
launchctl stop com.gridbot.production.webui && sleep 2 && launchctl start com.gridbot.production.webui
```

### Port 5555 Conflict
```bash
# Kill processes using port
lsof -ti:5555 | xargs kill -9

# Restart backend
launchctl start com.gridbot.webui
```

---

## API Structure

All backend API endpoints use `/api/` prefix:
- `/api/health`
- `/api/positions`
- `/api/config`
- etc.

Frontend automatically proxies these calls in development mode.


