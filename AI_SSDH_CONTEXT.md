# SSDH — Short Straddle Double Hedge: AI Context

## Strategy
Sell ATM straddle (CE+PE) + buy OTM wing hedges (CE+PE). 4 legs total. Delta Exchange options on BTC.
- **Core legs (SHORT):** ATM short CE + short PE (collect premium)
- **Hedge legs (LONG):** OTM long CE + long PE (cap max loss)
- `LOT_SIZE_BTC = 0.001` (contract multiplier)

---

## File Map

### Backend (`webui/backend/routes/ssdh/`)
| File | Role |
|---|---|
| `ssdh_state.py` | Data structures, factories, P&L math, persistence |
| `ssdh_config.py` | Param validation, hot/cold classification, hot-reload |
| `ssdh_presets.py` | Default param sets |
| `ssdh_engine.py` | P&L update, adaptive interval, vega indicator |
| `ssdh_entry.py` | 4-leg atomic entry orchestration |
| `ssdh_executor.py` | Order placement + fill polling on Delta Exchange |
| `ssdh_monitor.py` | OS-thread heartbeat loop |
| `ssdh_safety.py` | All 6 exit trigger checks |
| `ssdh_integrity.py` | Structure check (all 4 legs present) |
| `ssdh_reconciler.py` | Exchange vs local state verification |
| `ssdh_kill.py` | Emergency flatten-all |
| `ssdh_activity.py` | Activity ring buffer + JSON log |
| `ssdh_websocket.py` | SocketIO emit to `/ssdh` namespace |
| `ssdh_api.py` | Flask Blueprint REST endpoints |
| `tests/` | conftest, test_sealed_ssdh_config, test_sealed_ssdh_pnl |

### Frontend (`webui/frontend/src/components/ssdh/`)
| File | Role |
|---|---|
| `SSDHDashboard.js` | Main dashboard, WS listeners, layout orchestration |
| `SSDHStatusBanner.js` | Session header: status + P&L + trailing stop bar |
| `SSDHPositionsTable.js` | Per-leg table: entry→current price, P&L bars |
| `SSDHPnLPanel.js` | P&L breakdown + 6 safety system indicators |
| `SSDHActivityLog.js` | Last N events polled every 15s |
| `SSDHSessionCreate.js` | 3-phase creation wizard (configure→chain→confirm) |
| `ssdh_service.js` | REST API calls + WS event routing singleton |
| `../pages/SSDHPage.js` | Thin wrapper rendering SSDHDashboard |

### Integration
- **Blueprint:** `app.py:580-592` — registers `ssdh_bp` at `/api/ssdh`, calls `init_ssdh_websocket(socketio)`, loads persisted activities
- **Navigation:** `navigationSections.js` — id=`ssdh`, label=`⚡ SSDH`, group=`Algorithms`

### Data Files
- `webui/backend/data/ssdh_sessions.json` — persisted sessions (atomic write)
- `webui/backend/data/ssdh_activity_log.json` — activity log (ring buffer, max 500)

---

## State Constants (`ssdh_state.py`)

```python
# Session lifecycle
SESS_IDLE | INITIALIZING | RUNNING | WIND_DOWN | CLOSED | ABORTED | EMERGENCY

# Entry states
ENTRY_IDLE | ENTRY_PLACING | ENTRY_COMPLETE | ENTRY_ABORTED

# Position
DIR_SHORT | DIR_LONG
TYPE_CORE (ATM short) | TYPE_HEDGE (OTM long)
POS_ACTIVE | POS_CLOSED

# Close reasons
TIME_EXIT | MAX_LOSS | TRAILING_STOP | STRUCTURE_BREAK | MANUAL | KILL

# Leg IDs
LEG_SHORT_CE | LEG_SHORT_PE | LEG_LONG_CE | LEG_LONG_PE
```

---

## Key Functions (`ssdh_state.py`)

| Function | Purpose |
|---|---|
| `create_session(params)` | Session dict factory |
| `create_position(leg_id, direction, pos_type, ...)` | Position dict factory with validation |
| `compute_position_pnl(pos, current_price)` | Unrealized P&L (Decimal-based) |
| `recompute_net_pnl(session)` | Atomic: realized + sum unrealized |
| `get_active_positions(session)` | Filter active |
| `get_positions_by_type(session, direction, side)` | Filter by direction+side |
| `mark_position_closed(pos, realized_pnl, reason)` | Close with realized P&L |
| `persist_session(session)` | Atomic temp→fsync→rename write |
| `load_sessions()` | Read from JSON |

---

## Config: Hot vs Cold (`ssdh_config.py`)

**HOT_RELOAD_PARAMS** (can change mid-session):
`max_loss_amount`, `trailing_stop_pct`, `vega_exit_multiplier`, `vega_exit_auto`, `margin_yellow_pct`, `combined_margin_limit`, `circuit_breaker_threshold`, `guardian_max_beat_sec`, `adjustment_interval`, `adaptive_min_interval`, `adaptive_max_interval`

**COLD_PARAMS** (locked at creation):
`initial_lots`, `desired_ce_premium`, `desired_pe_premium`, `long_hedge_premium_target`, `expiry`, `entry_timeout_seconds`, `long_hedge_lots_ratio`, `session_window_hours`

**Key functions:** `validate_params(params, hot_only=False)`, `apply_hot_reload(session, new_params)`, `compute_intraday_max_loss(session)`

---

## Default Preset (`ssdh_presets.py`)

```python
session_window_hours: 4.0
long_hedge_lots_ratio: 2.0       # hedge lots = initial_lots × ratio
trailing_stop_pct: 0.50          # stop at 50% drawdown from peak
vega_exit_multiplier: 1.50       # exit if short premium inflates 1.5×
adjustment_interval: 30          # heartbeat seconds (slow mode)
entry_timeout_seconds: 180       # reprice if no fill after 180s
intraday_max_loss_multiplier: 1.75
```

---

## Engine (`ssdh_engine.py`)

**OPTEngine** — stateless, pure computation:
- `update_premiums(session, price_map)` — 4-layer fallback price fetch
- `compute_and_store_pnl(session)` → calls `recompute_net_pnl()`
- `compute_adaptive_interval(session)` — based on loss proximity:
  - ratio < 0.25 → slow (adjustment_interval, default 30s)
  - 0.25–0.50 → medium (base / 2)
  - ≥ 0.50 → fast (adaptive_min_interval, default 10s)
- `compute_vega_indicator(session)` — short premium inflation ratio
- `compute_time_remaining(session)` — seconds left in window

---

## Entry (`ssdh_entry.py` + `ssdh_executor.py`)

**AtomicEntryOrchestrator:**
1. IDLE → PLACING: place all 4 legs via `asyncio.gather` (parallel)
2. Any leg failure → full rollback (cancel unfilled, market-close filled)
3. Checkpoint persistence after each fill (crash recovery)
4. PLACING → COMPLETE | ABORTED

**SSDHExecutor constants:**
```python
FILL_CHECK_INTERVAL = 3s
FILL_TIMEOUT = 60s          # reprice after no fill
MAX_REPRICE_ATTEMPTS = 4    # 4×60s = 4min max per leg
ORDER_STATES_FILLED = {'filled', 'closed', 'completed'}
SHORT_CLOSE_BUFFER = 1.05   # buy back at ask×1.05
LONG_CLOSE_BUFFER = 0.97    # sell back at bid×0.97
CLIENT_ORDER_ID_FORMAT = "ssdh_{session8}_{sides}_{ts8}"  # max 32 chars
```
**CRITICAL:** Use `paid_commission` NOT `commission` for fees.

---

## Monitor (`ssdh_monitor.py`)

**OPTMonitor** — real OS thread (NOT greenlet):
```python
# CRITICAL: must use original threading for asyncio support
threading.Thread = eventlet.patcher.original('threading').Thread
```

**Heartbeat steps** (every adaptive interval):
1. Fetch premiums (4-layer fallback)
2. Update premiums on positions
3. Recompute P&L (atomic)
4. Structure integrity check
5. TTL-clear stale `_being_closed` flags (`_BEING_CLOSED_TTL = 180s`)
6. Safety checks (max_loss, margin, circuit breaker)
7. Exit condition checks (time window, trailing stop, vega)
8. Update adaptive interval
9. Emit WS state
10. Persist session

---

## Safety (`ssdh_safety.py`)

All methods return `(bool, str)`:

| Check | Trigger |
|---|---|
| `check_max_loss()` | net_pnl ≤ −max_loss_amount (Decimal) |
| `check_margin()` | uses `blocked_margin` (NOT portfolio_margin) |
| `check_trailing_stop()` | **NEVER fires when peak_net_pnl ≤ 0** |
| `check_vega_spike()` | short premium inflation ≥ vega_exit_multiplier |
| `check_time_window()` | session window exceeded |
| `check_circuit_breaker()` | consecutive API failures |
| `check_structure_integrity()` | delegates to ssdh_integrity |

---

## Integrity (`ssdh_integrity.py`)

`check_structure_integrity(session)` — only runs after ENTRY_COMPLETE. Checks all 4 legs:
- ≥1 active short CE (TYPE_CORE, DIR_SHORT, side='CE')
- ≥1 active short PE (TYPE_CORE, DIR_SHORT, side='PE')
- ≥1 active long CE (TYPE_HEDGE, DIR_LONG, side='CE')
- ≥1 active long PE (TYPE_HEDGE, DIR_LONG, side='PE')

---

## Reconciler (`ssdh_reconciler.py`)

**CRITICAL RULES:**
- NEVER auto-correct positions with `fill_confirmed_at` within **120s** (Delta REST API lag up to 60s)
- SIZE_MISMATCH → log warning only (may be manual trade same strike)
- MISSING_ON_EXCHANGE → verify via `get_order(order_id)` first
- Expiry format: `ddmmyyyy` → symbol suffix `ddmmyy` (e.g. `'11032026'` → `'110326'`)

Runs on monitor startup + every 10 heartbeats.

---

## Kill Switch (`ssdh_kill.py`)

**RULE:** Kill does NOT check `_being_closed` flags — overrides all.
Steps: EMERGENCY status → emit kill event → close ALL active positions at market (parallel) → exchange verify → CLOSED + reason=KILL → persist.

---

## Activity Log (`ssdh_activity.py`)

- In-memory ring buffer + `ssdh_activity_log.json`
- MAX_ACTIVITIES = 500
- `log_activity()` — fire-and-forget, never raises
- Activity types: order lifecycle, entry, session lifecycle, heartbeat, exit, safety, kill, reconciliation

---

## WebSocket (`ssdh_websocket.py`)

Namespace: `/ssdh` (separate from MMM's default namespace)

Events emitted:
- `ssdh_state_update` — periodic heartbeat state
- `ssdh_leg_entry` / `ssdh_leg_close`
- `ssdh_wind_down` / `ssdh_session_closed`
- `ssdh_structure_break` / `ssdh_vega_spike` / `ssdh_kill_switch`

Stale flag after 10 consecutive failures. `init_websocket(socketio)` called at app startup.

---

## REST API (`ssdh_api.py`)

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/api/ssdh/sessions` | List all |
| GET | `/api/ssdh/sessions/<id>` | Get session state |
| POST | `/api/ssdh/sessions/start` | `confirm=false` → preview; `confirm=true` → execute |
| POST | `/api/ssdh/sessions/<id>/stop` | Graceful wind-down |
| POST | `/api/ssdh/sessions/<id>/kill` | Emergency kill |
| GET | `/api/ssdh/presets` | List presets |
| GET | `/api/ssdh/health` | Engine health |
| GET | `/api/ssdh/sessions/<id>/activity` | Activity log |

Two-phase start: preview checks conflicts (including MMM cross-engine conflict), returns financials; confirm=true executes.

---

## Frontend Data Flow

```
SSDHDashboard
  ├── polls GET /api/ssdh/sessions every 10s
  ├── WS listeners: state_update, structure_break, vega_spike, session_closed, kill_switch
  ├── SSDHStatusBanner   — status badge, running time, net P&L, trailing stop bar
  ├── SSDHPositionsTable — per-leg: entry→current, P&L bars (core first, then hedge)
  ├── SSDHPnLPanel       — P&L breakdown + 6 safety indicators
  └── SSDHActivityLog    — polls GET activity every 15s
```

**Session creation (SSDHSessionCreate.js):**
1. Configure: lots, window_hours, trailing_stop_pct, max_loss_btc
2. Chain: expiry picker → live option chain → leg picker → payoff SVG graph
3. Confirm: leg table + financials (gross_credit, gross_debit, net_credit, max_loss, breakevens) → execute

**ssdh_service.js** — REST singleton + WS singleton connecting to `/ssdh` namespace.

---

## Critical Rules Summary

1. **Trailing stop never fires at peak ≤ 0** (would punish sessions that never profit)
2. **Kill overrides `_being_closed` flags** — total emergency, no guards
3. **Use `paid_commission` not `commission`** for fees from order responses
4. **Use `blocked_margin` not `portfolio_margin`** for margin checks
5. **Reconciler grace period = 120s** after fill_confirmed_at (REST API settlement lag)
6. **Entry is atomic** — any leg failure rolls back all 4 legs
7. **Monitor must run in real OS thread** (not greenlet) for asyncio compatibility
8. **Expiry format:** stored as `ddmmyyyy`, Delta symbol suffix is `ddmmyy` (drop century)
9. **_being_closed TTL = 180s** (cleared by monitor to prevent stale stuck positions)
10. **Cross-engine conflict check** — SSDH start API checks if MMM is running same instrument
