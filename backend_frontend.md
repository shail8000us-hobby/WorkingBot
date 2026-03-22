# Backend & Frontend — Operations Guide

**Last Updated:** March 22, 2026

---

## TL;DR — One-Command Deployment

| Scenario | Command |
|---|---|
| **Backend Python change** | `./scripts/restart_webui.sh` |
| **Frontend src/ change** | `./scripts/deploy_webui.sh` |

> Both scripts wait for health check and print "✅ Live" when ready. No guessing.

---

## Port Configuration

| Service | Port | Purpose |
|---|---|---|
| **Backend (Flask API + WebSocket)** | `5555` | REST API, SocketIO, serves production build |
| **Frontend (Production)** | `5555` | Served by Flask from `webui/frontend/build/` |
| **Frontend (Dev server)** | `3000` | Hot-reload dev only — user does NOT use this |

**User accesses:** `http://localhost:5555` — production mode only.
Any edit to `webui/frontend/src/` is **invisible at :5555 until `deploy_webui.sh` runs.**

---

## Scripts

### `./scripts/restart_webui.sh` — backend restart only
Use after any Python change. No rebuild. Takes ~5-8s.
```bash
./scripts/restart_webui.sh
```
What it does:
1. `launchctl stop com.gridbot.production.webui` (synchronous — waits for process death)
2. `launchctl start com.gridbot.production.webui`
3. Polls `/api/health` every 1s, prints ✅ when ready

### `./scripts/deploy_webui.sh` — build frontend + restart
Use after any `webui/frontend/src/` change. Incremental build ~20-40s, prints ✅ when live.
```bash
./scripts/deploy_webui.sh
```
What it does:
1. `npm run build` (with cache — do NOT delete node_modules/.cache, it saves ~40s)
2. Stop + start backend
3. Polls health, prints ✅ when ready

---

## LaunchAgent Details

**Service name:** `com.gridbot.production.webui`
**Plist:** `~/Library/LaunchAgents/com.gridbot.production.webui.plist`
**Run command:** `.venv/bin/python3 webui/backend/app.py`
**KeepAlive:** `{SuccessfulExit: false}` — only restarts on crash/kill, NOT on clean stop
**ThrottleInterval:** 30s — minimum time between crash-auto-restarts

### Restart behaviour
| Method | What happens |
|---|---|
| `launchctl stop` | Clean exit (code 0) — **does NOT auto-restart** — must `launchctl start` manually |
| `kill -9 $(lsof -ti:5555)` | Crash exit — KeepAlive auto-restarts after ThrottleInterval (30s) |
| `restart_webui.sh` | Clean stop + immediate start — fastest, ~5-8s |

**Do NOT use `sleep 2` between stop and start** — `launchctl stop` is synchronous and waits for process death before returning.

---

## Logs

```bash
# Live error log (most useful)
tail -f logs/webui_production_error.log

# Full stdout log
tail -f logs/webui_production.log

# LaunchAgent own errors
tail -f logs/launchagent_webui_error.log
```

---

## Stack Constraints

> **Never introduce Gunicorn.** It was tried and caused random crashes every few hours due to worker recycling. Flask-SocketIO + `socketio.run()` with `threading` async mode is the correct stack.

> **Never delete `node_modules/.cache`** before a build. The cache makes incremental builds 40-70% faster. Only clear it if you get a corrupt build (rare).

---

## Manual Commands (if scripts unavailable)

```bash
# Backend restart only
launchctl stop com.gridbot.production.webui && launchctl start com.gridbot.production.webui

# Build + restart
cd webui/frontend && npm run build && cd ../.. && launchctl stop com.gridbot.production.webui && launchctl start com.gridbot.production.webui

# Health check
curl http://localhost:5555/api/health

# Check service
launchctl list | grep gridbot

# Kill and let KeepAlive restart (takes 30s)
kill -9 $(lsof -ti:5555)
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Changes not showing at :5555 | Run `./scripts/deploy_webui.sh` — source edit alone is never live |
| Port 5555 conflict from dev server | `pkill -f react-app-rewired` |
| Backend won't start | `tail -f logs/webui_production_error.log` |
| `launchctl start` says already loaded | `launchctl stop` first, then start |
| SocketIO connection error | Version mismatch — check `flask-socketio` and `socket.io-client` versions |
