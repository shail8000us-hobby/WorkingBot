# WorkingBot — Claude AI Guide

**Project:** Algorithmic Crypto Trading Bot (real money, live exchange)
**Exchange:** Delta Exchange India
**Stack:** Python 3.10+ backend, React 18 frontend
**Path:** `/Users/ssr/Projects/WorkingBot`

---

## Before Starting Any Task
- **MMM or options work**: Read `tasks/lessons.md` first — contains critical bugs already fixed with prevention rules. Real money was lost from these.
- **Any backend change**: Run `curl http://localhost:5555/api/health` to confirm backend is up before and after.
- **Ask before restarting backend** — live MMM sessions may be running.

---

## CRITICAL RULES — NEVER VIOLATE

### 1. Port 5555 = Backend ONLY
- Backend Flask API runs on port 5555 — hardcoded everywhere (LaunchAgent plist, frontend client, scripts)
- Frontend dev server runs on port 3000
- **Never change port 5555 in `webui/backend/app.py`**
- Port conflict? Kill the React dev server, NOT the backend:
  ```bash
  pkill -f react-app-rewired
  ```

### 2. USD→INR Conversion: Exactly Once
- Delta Exchange API returns **USD**. Display is **INR**. Convert **once only**.
- Conversion happens ONLY in:
  1. `webui/backend/routes/liquidation.py`
  2. `webui/backend/routes/positions.py`
- All other modules consume INR. Never convert again downstream.
- Double-conversion produces wrong values like ₹87 lac instead of ₹87k.

### 3. macOS LaunchAgent — Not systemd/pm2
```bash
kill -9 $(lsof -ti:5555)             # restart (KeepAlive auto-restarts after 30s ThrottleInterval)
launchctl start com.gridbot.production.webui  # start if not running
launchctl list | grep gridbot
```
LaunchAgent plist: `~/Library/LaunchAgents/com.gridbot.production.webui.plist`
Logs: `logs/webui_production_error.log`

> KeepAlive={SuccessfulExit:false} — launchd only auto-restarts on non-zero exit (crash/kill -9). `launchctl stop` causes clean exit (0) and does NOT auto-restart.

### 4. SocketIO Versions Must Match
- Backend: `python-socketio 5.x`, `flask-socketio 5.x`
- Frontend: `socket.io-client 4.8.x` or higher

### 5. Guardian Is Always On
- Never disable Guardian in live mode — it is the safety net for capital loss protection
- Emergency shutdown: `python3 bot/emergency_kill.py`

### 6. Never Commit Secrets
- Never commit `secrets/api_keys.env` or any `.env` file
- Never expose API keys in frontend code or logs
- Never run with `EXECUTE_ORDERS=true` without first testing in demo mode

---

## Behavior Instructions

- **Plan before acting**: Enter plan mode for any task that is 3+ steps or touches live trading logic
- **Verify before marking done**: Run `curl http://localhost:5555/api/health` after backend changes
- **Ask when unsure**: A wrong order or port change can cause real financial loss
- **Fix bugs directly**: When given a bug report, read the code and fix it — no hand-holding needed
- **No over-engineering**: Minimal changes only; do not add abstractions, helpers, or comments beyond what is needed
- **After any correction**: Update `tasks/lessons.md` with what went wrong and the prevention rule

---

## Pre-Change Checklist

```bash
# 1. Is backend running?
curl http://localhost:5555/api/health

# 2. Is data USD or INR? (Delta API = USD, our endpoints = INR — check source)

# 3. SocketIO versions compatible?
pip3 list | grep socketio
cd webui/frontend && grep socket.io-client package.json
```

---

## Pre-Deploy Checklist (run before every backend restart)

```bash
# 1. All sealed tests pass — count must not drop
python3 -m pytest webui/ bot/ -m sealed -v
# Expected: N passed, 0 failed  (N = current total, check AI_ALREADY_SEALED.md)

# 2. Backend health before touching anything
curl http://localhost:5555/api/health

# 3. Check for live MMM sessions — DO NOT restart if any session is RUNNING
# Ask user or check dashboard before proceeding

# 4. After restart: watch logs for 60s
tail -f logs/webui_production_error.log

# 5. Confirm positions still visible in options panel
curl http://localhost:5555/api/positions
```

> **Rule:** If sealed test count drops (e.g. was 363, now 360), STOP. A sealed function was deleted or broken. Find and fix before deploying.

---

## MMM Restart Protocol (backend crashed while session was live)

MMM automatically restores sessions and reconciles with exchange on restart — this is built in.
But verify manually after every unplanned restart:

```bash
# 1. Check last known activity log
tail -50 webui/backend/data/mmm_activity_log.json

# 2. Confirm session was restored (not orphaned)
curl http://localhost:5555/api/mmm/sessions

# 3. Check reconciliation ran — look for 'reconciliation_autocorrect' in logs
grep "reconciliation" logs/webui_production_error.log | tail -20
```

If positions mismatch after reconciliation: **pause the session, do NOT let it auto-trade. Reconcile manually.**

---

## Project Structure

```
WorkingBot/
├── bot/
│   ├── run.py                                      # Main entry point
│   ├── strategy/gbot_ws.py                         # ACTIVE WebSocket GridBot (1970L)
│   ├── api/delta_client.py                         # Exchange REST+WS client (587L)
│   ├── config/config_manager_core.py               # Hot-reload config (943L)
│   ├── guardian/guardian_bot.py                    # 24/7 safety monitor (682L)
│   ├── heartbeat/monitor.py                        # Dead man's switch (321L)
│   └── volatility/delta_volatility_collector.py   # IV/RV collector (893L)
│
├── webui/
│   ├── backend/
│   │   ├── app.py                                  # Flask API — DO NOT MOVE/RENAME
│   │   └── routes/                                 # 23 API blueprints — DO NOT REORGANIZE
│   │       └── mmm/                                # MMM options algo (see below)
│   └── frontend/
│       ├── src/                                    # React source (edit freely)
│       └── build/                                  # Production build — never edit manually
│
├── grid_config.env                                 # Main config (171 parameters)
├── secrets/api_keys.env                            # Credentials — never commit
├── data/volatility.db                              # SQLite IV/RV history
├── .heartbeat                                      # Written every 5s by bot
└── .guardian_health                                # Guardian status file
```

---

## Key Modules

| Module | File | Lines |
|---|---|---|
| GridBot | `bot/strategy/gbot_ws.py` | 1970 |
| Guardian | `bot/guardian/guardian_bot.py` | 682 |
| DeltaClient | `bot/api/delta_client.py` | 587 |
| ConfigManager | `bot/config/config_manager_core.py` | 943 |
| VolCollector | `bot/volatility/delta_volatility_collector.py` | 893 |
| HeartbeatMon | `bot/heartbeat/monitor.py` | 321 |
| FlaskAPI | `webui/backend/app.py` | 7973 |
| ReactApp | `webui/frontend/src/App.js` | 1385 |

---

## MMM Options Algo (`webui/backend/routes/mmm/`)

| File | Purpose |
|---|---|
| `mmm_monitor.py` | Central heartbeat orchestrator (MMMMonitor class) |
| `mmm_engine.py` | Lot calculation + order execution (MMMEngine) |
| `mmm_state.py` | Session state model, DEFAULT_PARAMS, HOT_RELOAD_PARAMS |
| `mmm_close_at_5.py` | Close positions at premium <= threshold |
| `mmm_strike_shift.py` | Shift to new strike when premium decays |
| `mmm_harvester.py` | M1 profit harvesting + M3 asymmetry rebalancing |
| `mmm_recycler.py` | M2 lot recycling emergency relief |
| `mmm_activity.py` | Activity log (ACTIVITY_TYPES, ACTIVITY_CATEGORIES) |
| `mmm_websocket.py` | WebSocket event emitters |
| `mmm_audit_log.py` | Trade Transparency System — `get_audit_log()` / `get_event_log()` singletons |
| `mmm_audit_remark.py` | Pure remark builder — `build_trade_remark()` / `build_event_remark()` |
| `mmm_audit_reconciler.py` | `reconcile_session(session_id, session)` → audit vs live state cross-check |

**Key facts:**
- LOT_SIZE_BTC = 0.001 (1 lot = 0.001 BTC on Delta Exchange)
- `close_position(executor, initializer, session, pos)` in `mmm_close_at_5.py` — reused for all position buybacks
- `engine.execute_adjustment(session, hedge_side, strike, lots, ce_now, pe_now, adj_type)` — for selling
- `engine.calculate_lots_to_sell(session, hedge_side, loss, premium)` returns `(lots, constraint_msg)`
- `session['_regime_action']` stores regime status; import `ACTION_BLOCK_ALL_SELLS` from `mmm_regime.py`
- `self._margin_guardian.last_tier` on monitor: TIER_GREEN/YELLOW/ORANGE/RED/CRITICAL
- **Trade audit:** every confirmed fill calls `get_audit_log().enqueue_trade(...)` — fire-and-forget, < 1µs. Every state change calls `get_event_log().enqueue_event(...)`. Never call before `result.get('success')`. Always wrap in `try/except: pass`.

---

## Grid Bot Trading Logic

Places BUY orders below price, SELL TP orders above entry price.

State machine: `IDLE → WAITING → FILLED → HOLDING → HALTED (on volatility spike) → WAITING/HOLDING`

Fill detection:
- Primary: WebSocket `_on_fill_detected()` — 0.05s response
- Backup: REST polling every 20s
- Deduplication: `self._processed_fills = set()`

---

## Safety Systems

**Guardian Bot** (checks every 5s):
- 0–79% loss: OK
- 80–89%: WARNING (Telegram alert)
- 90–99%: CRITICAL (Telegram + review)
- 100%+: EMERGENCY (auto-stop + close all)
Config: `GUARDIAN_MAX_ACCOUNT_LOSS_INR` in `grid_config.env`

**Volatility Halt:**
- `VOLATILITY_MAX_IV=45` — halt if IV > 45%
- `VOLATILITY_MAX_RV=55` — halt if RV > 55%
- `VOLATILITY_MAX_SPREAD=10` — halt if IV-RV spread > 10%

**Heartbeat:** Bot writes `.heartbeat` every 5s. `monitor.py` cancels all orders if it goes stale.

---

## Configuration

**File:** `grid_config.env` (171 parameters)

Hot reload: Config watcher checks mtime every 5s. Save the file to apply changes within 5 seconds.

- Hot-reloadable: grid params, safety limits, most trading behavior
- NOT hot-reloadable: `API_KEY`, `TRADING_MODE`, database settings

---

## API Reference

Base URL: `http://localhost:5555/api`

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/bot/status` | GET | Bot running status |
| `/api/bot/start` | POST | Start bot (mode: live/demo) |
| `/api/bot/stop` | POST | Stop bot |
| `/api/positions` | GET | Open positions + uPnL |
| `/api/config/flat` | GET | All 171 config params |
| `/api/config` | POST | Update config (triggers hot reload) |
| `/api/liquidation/status` | GET | Balance, margin, liquidation |
| `/api/risk/volatility/latest` | GET | Current IV/RV |
| `/api/logs` | GET | Log viewer |
| `/api/claude/chat` | POST | Claude AI integration |

WebSocket: `ws://localhost:5555/socket.io`
Events: `state_snapshot` (2s), `config_updated`, `bot_status`, `log_entry`, `volatility_update`

---

## Development Workflow

```bash
# UI changes (hot reload)
launchctl start com.gridbot.production.webui  # Backend on 5555
cd webui/frontend && npm start                # Dev server on 3000

# Backend changes (production build)
cd webui/frontend && npm run build
kill -9 $(lsof -ti:5555)  # launchd auto-restarts after ~30s (KeepAlive)

# Tests
pytest tests/test_refactored_code.py -v
pytest tests/ --cov=bot --cov-report=html

# Logs
tail -f logs/launchagent_webui_error.log
grep "FILL\|Fill detected" bot_live.log
```

---

## Common Mistakes

| Symptom | Cause | Fix |
|---|---|---|
| Port 5555 conflict | React dev server on 5555 | `pkill -f react-app-rewired` |
| Balance shows ₹87 lac | Double USD→INR conversion | Remove downstream conversion |
| SocketIO connection error | Version mismatch | `npm install socket.io-client@latest` |
| Config not reloading | File not saved | Re-save `grid_config.env` |
| Orders not placing | `EXECUTE_ORDERS=false` | Check `grid_config.env` |
| NameError after refactor | Missing `import logging` | Add `log = logging.getLogger(__name__)` |

---

## MMM Canary → Live Promotion Criteria

MMM currently runs on canary account. Promote to live when ALL of these hold:

| Criteria | What it means |
|---|---|
| All Tier 1 + Tier 2 MMM functions sealed | Core math and safety rules have contract tests |
| Zero sealed test failures for 7 days | No regression in a week of active development |
| 3+ complete canary sessions without manual intervention | Bot managed itself start-to-close without human fix |
| All safety checks verified against real session data | Fixtures use real captured session state, not synthetic |
| Reconciliation verified after at least 1 planned restart | Manual restart test while session was live |

> This list lives here so promotion is a deliberate decision, not gradual drift.

---

## Reference Files

| File | Contents |
|---|---|
| `AI_CONTEXT.md` | Full project context |
| `AI_MMM_CONTEXT.md` | MMM/options module context |
| `AI_Options_context.md` | Options trading context |
| `AI_PATIENCE_CONTEXT.md` | Patience scenario card engine context |
| `tasks/todo.md` | Current task list |
| `tasks/lessons.md` | Accumulated lessons — update after every correction |
| `grid_config.env` | All 171 configuration parameters |
