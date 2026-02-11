# Backend & Frontend Documentation

**Last Updated:** February 10, 2026

## Port Configuration

### Production Setup

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| **Backend (Flask API)** | `5555` | REST API, WebSocket, Data endpoints | ✅ ACTIVE |
| **Frontend (Production)** | `5555` | Served by Flask backend | ✅ ACTIVE |
| **Frontend (Dev)** | `3000` | Development server (optional) | Use for UI development |

**Production Mode:**
- Backend runs on port 5555 via LaunchAgent
- Frontend production build served from `webui/frontend/build/`
- Single port architecture

---

## Development Workflows

### UI Development (Hot Reload)
```bash
# Terminal 1: Start Backend
launchctl start com.gridbot.webui

# Terminal 2: Start Frontend Dev Server
cd webui/frontend
npm start
# Access at: http://localhost:3000
```

### Backend Development (Production Build)
```bash
# Build frontend once
cd webui/frontend
npm run build

# Start backend only
launchctl start com.gridbot.webui
# Access at: http://localhost:5555
```

---

## Configuration Files

### Backend
**File:** `webui/backend/app.py`
```python
socketio.run(app, host='0.0.0.0', port=5555, debug=False)
```

**LaunchAgent:** `~/Library/LaunchAgents/com.gridbot.webui.plist`

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
launchctl start com.gridbot.webui

# Stop
launchctl stop com.gridbot.webui

# Restart
launchctl stop com.gridbot.webui && sleep 2 && launchctl start com.gridbot.webui

# Status
launchctl list | grep gridbot.webui

# Logs
tail -f logs/launchagent_webui_error.log
```

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

# Check LaunchAgent
launchctl list | grep gridbot.webui

# View logs
tail -f ~/Projects/WorkingBot/logs/launchagent_webui_error.log
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


