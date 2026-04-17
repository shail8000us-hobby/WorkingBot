# PROJECT_OVERVIEW.md — WorkingBot Quick Reference

## Project

**Name:** WorkingBot  
**Branch:** `SSR` (working) → merge target: `BTEH`  
**Git user:** physicsssr

---

## Active Algos

| Algo | Description |
|------|-------------|
| **MMM** | BTC options premium selling (short strangles/straddles), Delta Exchange, 0DTE |
| **MMMX** | Next-gen MMM variant (in development) |
| **Patience** | Separate options strategy |
| **SSR** | Algo on SSR branch |
| **Zero DTE** | Zero-DTE options strategy |
| **IC Algo** | Iron Condor algo |

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python / Flask (async routes via asyncio) |
| Frontend | React (Create React App), MUI v5 |
| Process manager | PM2, tmux, launchd (macOS LaunchAgent) |
| Database | SQLite (`mmm_sessions.db`, position_audit_log, session_event_log) |
| WebSockets | Flask-SocketIO |

---

## Broker Integrations

| Broker | Products | Client |
|--------|----------|--------|
| Delta Exchange | BTC options (CE/PE), BTCUSD perpetual | `delta_rest_client.py` / `delta_ws_client.py` |
| Zerodha Kite | Indian equity/options | `kite_client.py` |

---

## Key Ports & Services

| Service | Port | Notes |
|---------|------|-------|
| WebUI backend (Flask) | **5555** | Main API + WebSocket |
| File server | **8080** | Static file serving |
| Frontend dev server | 3000 | Development only |

---

## Key Directories

```
webui/backend/routes/mmm/   — All MMM algo backend logic (~50 modules)
webui/backend/routes/       — Other algo routes
webui/frontend/src/         — React frontend
webui/backend/data/         — mmm_sessions.db, options_trades.csv, logs
bot/                        — Telegram bot, guardian processes
config/                     — Bot configuration files
scripts/                    — Utility scripts
```

---

## Real Money Rules (summary — full rules in CLAUDE.md §2)

- Never restart backend/monitor without explicit user confirmation
- Never place/cancel real orders without explicit user request
- Always confirm before `git push` or destructive operations

*For MMM-specific context: read `MMM_SLIM_CONTEXT.md` and `MMM_LAST_3_SESSIONS.md`*
