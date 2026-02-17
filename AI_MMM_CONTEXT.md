# AI_MMM_CONTEXT.md — Complete MMM Algorithm Reference for AI Agents

> **Purpose:** This document provides every detail an AI agent needs to understand, debug, modify, or extend the MMM (Money Mind & Method) algorithm and its WebUI implementation.
>
> **Last Updated:** February 16, 2026
> **Status:** All 8 phases complete. Production-ready. Updated: ALL positions (active + shifted) included in loss calculations — no position is ever excluded.

---

## 1. WHAT IS MMM?

MMM is a **BTC 0DTE options premium selling algorithm** with automatic adjustment. It:

1. **Sells** both CE (call) and PE (put) options on BTC at OTM strikes
2. **Monitors** premiums every N seconds (default 300s)
3. **Adjusts** when one side's premium rises above its trigger — sells more of the opposite side to cover the loss
4. **Shifts strikes** when opposing premium is too low to provide meaningful hedge
5. **Closes positions at ≤5** premium to lock profit
6. **Handles reversals** by computing actual adjustment P&L before hedging
7. **Safety mechanisms** protect against runaway losses, whipsaw, margin exhaustion

The complete calculation logic is defined in `MONEY_POWER_CALCULATION_LOGIC.md` (21 sections, sealed). The development plan is in `MMM_DEVELOPMENT_PLAN.md` (8 phases, all complete).

---

## 2. ALGORITHM CORE LOGIC

### 2.1 Entry (Section 3)

**Mode A — Fresh:** User provides desired CE/PE premium + lots + expiry → algo scans the options chain → finds OTM strikes closest to desired premium → user confirms → positions sold.

**Mode B — Import:** User enters existing CE/PE strike, fill price, lots → algo initializes state without placing orders.

### 2.2 Heartbeat Loop (Section 4)

Every `adjustment_interval` seconds:

```
1. Fetch CE premium at active_ce_strike → CE_now
2. Fetch PE premium at active_pe_strike → PE_now
3. Run Close-at-5 on ALL positions (active + frozen)
4. Run Safety Checks
5. If status ≠ RUNNING → skip adjustment logic
6. Compute excess: ce_excess = CE_now - trigger_snapshot[active_ce_strike]
7. Apply min_trigger_move filter
8. Four outcomes:
   A) Neither triggered → DO NOTHING
   B) CE triggered only → CE is aggressor, sell PE (Section 5)
   C) PE triggered only → PE is aggressor, sell CE (Section 5)
   D) Both triggered → PAUSE, show both-sides alert (Section 8)
```

### 2.3 Adjustment Calculation (Section 5)

For **CE as aggressor** (PE mirror is identical with CE↔PE swapped):

**Step 1 — Reversal check:**
```
reversal = (last_aggressor == "PE" AND CE is now aggressor)
```

**Step 2 — Loss calculation:**

- **Standard (continuation/first-ever):**
  Compute total loss across ALL open positions on the aggressor side:
  $$L_{\text{active}} = (CE_{now} - trigger_{CE}) \times N_{active\_CE}$$
  $$L_{\text{shifted}} = \sum_{j} \max\bigl((P_{current,j} - P_{entry,j}) \times N_j, \; 0\bigr)$$
  $$L = L_{\text{active}} + L_{\text{shifted}}$$
  ALL positions at ALL strikes contribute. No position is ever excluded.

- **First reversal:** Compute actual P&L of ALL CE adjustment fills (active + shifted):
  $$L = \left|\sum_{i} (P_{entry,i} - P_{current,i}) \times N_i\right|$$
  Only triggers if sum is negative (adjustments underwater). If ≥ 0 → DO NOTHING.

**Step 3 — Strike check:**
If opposing premium < `shift_threshold` → Strike Shift (Section 10)

**Step 4 — Lots calculation:**
$$N_{sell} = \left\lceil \frac{L}{P_{hedge}} \times (1 + buffer) \right\rceil$$

**Step 5 — Execute sell, record fill, update BOTH trigger snapshots**

### 2.4 Trigger System (Section 7)

Triggers create a **safe zone**. After each adjustment, BOTH sides' snapshots update to current prices:
```
ce_trigger_snapshot[active_ce_strike] = CE_now
pe_trigger_snapshot[active_pe_strike] = PE_now
```

The trigger means: "All losses up to this premium level are already covered."

### 2.5 Strike Shifting (Section 10)

When opposing premium is below `shift_threshold`:
1. Scan options chain for strikes with premium ≥ threshold
2. Pick strike whose premium is closest to `shift_target_premium` (default 100)
3. Move old positions to `shifted_positions` (not closed — still fully tracked and included in ALL loss calculations)
4. Set new `active_strike`, sell at new strike
5. ALL positions (active + shifted) are used in the standard adjustment formula — no position is ever excluded

**CRITICAL:** The `shift_threshold` only controls WHERE to open new positions. It never makes existing positions invisible. The internal code uses the variable name `frozen_positions` for backward compatibility, but these positions are NOT frozen — they are live risk.

### 2.6 Close-at-5 (Section 11)

Every interval, scan ALL positions. If premium ≤ `close_at_threshold`:
- Buy back at market/ask
- Record realized P&L: `(entry_premium - close_premium) × lots`
- Remove from tracking
- If ALL positions closed on both sides → strategy COMPLETE

### 2.7 Both-Sides-Up (Section 8)

When BOTH CE and PE exceed triggers simultaneously:
- Set status = `BOTH_SIDES_UP`
- Show alert modal with 4 options: ADD / REDUCE / RESUME / STOP
- Algo pauses until user decides

### 2.8 Safety Mechanisms (Sections 13-14)

| Safety | What It Does |
|--------|-------------|
| Position Cap | Max lots per side (default 100) |
| Max Adjustments | Counter limit (default 30) |
| Max Loss | Hard stop — close all if P&L < -max_loss |
| Whipsaw Detection | 3 alternating adjustments → auto-pause |
| Position Asymmetry | Warn at 3:1, alert at 5:1 ratio |
| Near-Expiry | Stop adjustments at 15min, auto-close at 5min |
| Margin Check | Verify margin before every sell |
| Trailing Profit | Protect peak P&L (stop at 50% drawdown from peak) |
| Theta Acceleration | Widen triggers near expiry (let theta work) |
| P&L Guardrail | Warn/pause/stop at loss thresholds |
| Periodic Reconciliation | True P&L check every 5 adjustments |

### 2.9 User Parameters (Section 19)

| Parameter | Default | Hot Reload? |
|-----------|---------|-------------|
| `desired_ce_premium` | User input | No |
| `desired_pe_premium` | User input | No |
| `initial_lots` | User input | No |
| `expiry` | User input | No |
| `adjustment_interval` | 300s | **Yes** |
| `min_trigger_move` | 3 | **Yes** |
| `shift_threshold` | 50 | **Yes** |
| `shift_target_premium` | 100 | **Yes** |
| `close_at_threshold` | 5 | **Yes** |
| `premium_buffer_pct` | 5% | **Yes** |
| `max_lots_per_side` | 100 | **Yes** |
| `max_adjustments` | 30 | **Yes** |
| `max_loss_amount` | User-defined | **Yes** |
| `stop_adjustment_mins` | 15 | **Yes** |
| `auto_close_mins` | 5 | **Yes** |
| `cooldown_on_reversal` | true | **Yes** |
| `whipsaw_limit` | 3 | **Yes** |
| `trailing_stop_pct` | 50% | **Yes** |

"Hot Reload = Yes" means the parameter can be changed via WebUI while the algo is running and takes effect on the next heartbeat interval.

---

## 3. ARCHITECTURE

### 3.1 File Structure

```
webui/
├── backend/
│   └── routes/
│       └── mmm/                          ← Isolated backend module
│           ├── __init__.py               ← Blueprint registration, init_mmm()
│           ├── mmm_api.py                ← REST API (~1700 lines, all endpoints)
│           ├── mmm_state.py              ← State model, session creation
│           ├── mmm_config.py             ← Parameter validation, defaults
│           ├── mmm_storage.py            ← JSON persistence with file locking
│           ├── mmm_websocket.py          ← 11 WebSocket event emitters
│           ├── mmm_initializer.py        ← Strike selection, chain data, expiries
│           ├── mmm_executor.py           ← Smart execution, mid-price, reprice
│           ├── mmm_trigger.py            ← Trigger evaluation, theta acceleration
│           ├── mmm_engine.py             ← Core adjustment, P&L computation
│           ├── mmm_reversal.py           ← Reversal detection, cooldown, skip
│           ├── mmm_strike_shift.py       ← Freeze/find/activate strike shift
│           ├── mmm_close_at_5.py         ← Position scanning, buyback, profit lock
│           ├── mmm_safety.py             ← All safety checks, trailing stop
│           ├── mmm_monitor.py            ← Background heartbeat loop thread
│           └── tests/                    ← Unit tests (7 files)
│
├── frontend/
│   └── src/
│       └── components/
│           └── mmm/                      ← Isolated frontend module
│               ├── index.js              ← Barrel exports
│               ├── MMMDashboard.js       ← Main dashboard container (~1000 lines)
│               ├── MMMConfigPanel.js     ← 3-mode config: Fresh/Manual/Import
│               ├── MMMStrikeSelector.js  ← Manual strike browser from chain
│               ├── MMMContext.js          ← React Context + WebSocket listeners
│               ├── MMMErrorBoundary.js   ← Error boundary wrapper
│               ├── mmmService.js         ← API service client (axios)
│               ├── MMMStatusBanner.js    ← Running/Paused/Stopped status bar
│               ├── MMMPositionsTable.js  ← Active + frozen positions table
│               ├── MMMTriggerGauge.js    ← Visual trigger gauges per side
│               ├── MMMAdjustmentLog.js   ← Adjustment history timeline
│               ├── MMMSessionCard.js     ← Session card with controls
│               ├── MMMStrikeMap.js       ← Strike visualization
│               ├── MMMPnLChart.js        ← P&L chart (Recharts)
│               ├── MMMBothSidesAlert.js  ← Both-sides decision modal
│               ├── MMMSafetyPanel.js     ← Safety dashboard (8 indicators)
│               ├── hooks/
│               │   ├── useMMMParams.js   ← Parameter dirty tracking
│               │   └── useMMMWebSocket.js← WebSocket subscription hook
│               └── utils/
│                   ├── mmmFormatters.js  ← Number/time/strike formatters
│                   └── mmmCalculations.js← Client-side P&L math
```

### 3.2 Integration Points (Only 2 Existing Files Modified)

| File | Change |
|------|--------|
| `webui/backend/app.py` | Lines 476-487: `register_blueprint(mmm_bp)` + `init_mmm()` in try/except |
| `webui/frontend/src/App.js` | Line 67: import `MMMErrorBoundary, MMMProvider`; Line 147: lazy import `MMMDashboard`; Line 594: MMM tab; Lines 1522-1530: `<MMMProvider socket={socket}>` wrapping `<MMMDashboard />` |

### 3.3 Runtime Architecture

```
Flask Backend (port 5555)
├── Blueprint: /api/mmm/*
├── MMMMonitor: background thread per session (heartbeat loop)
├── MMMStorage: JSON file persistence (mmm_sessions.json)
├── SocketIO: emits mmm_* events to frontend
└── LaunchAgent: com.gridbot.webui (auto-restart)

React Frontend (production build served by Flask)
├── MMMProvider: wraps MMMDashboard, receives socket prop from App.js
├── MMMContext: manages sessions, WebSocket listeners, state
├── MMMDashboard: session list + detail view with 7 tabs
└── CreateSessionDialog: mode selection, expiry dropdown, params, import
```

---

## 4. API REFERENCE

### 4.1 Session Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/health` | Health check |
| `GET` | `/api/mmm/sessions` | List all sessions |
| `GET` | `/api/mmm/session/<id>` | Get full session details |
| `POST` | `/api/mmm/session/create` | Create session (mode: fresh/import) |
| `DELETE` | `/api/mmm/session/<id>` | Delete (IDLE/STOPPED only) |

### 4.2 Initialization

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/expiries` | Available BTC expiry dates (DDMMYYYY format) |
| `GET` | `/api/mmm/spot-price` | Current BTC spot price |
| `POST` | `/api/mmm/preview-strikes` | Preview strikes for desired premiums |
| `POST` | `/api/mmm/session/<id>/init-fresh` | Initialize with confirmed strikes |
| `POST` | `/api/mmm/session/<id>/init-import` | Initialize from existing positions |
| `POST` | `/api/mmm/check-liquidity` | Bid-side liquidity check |
| `GET` | `/api/mmm/chain` | Full options chain for manual selection |
| `POST` | `/api/mmm/session/<id>/execute-entry` | Smart execution at mid-price |

### 4.3 Session Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mmm/session/<id>/start` | Start monitoring |
| `POST` | `/api/mmm/session/<id>/pause` | Pause monitoring |
| `POST` | `/api/mmm/session/<id>/resume` | Resume monitoring |
| `POST` | `/api/mmm/session/<id>/stop` | Stop session |

### 4.4 Real-Time Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/session/<id>/status` | Full status snapshot |
| `GET` | `/api/mmm/session/<id>/positions` | All positions (active + frozen) |
| `GET` | `/api/mmm/session/<id>/adjustments` | Adjustment history |
| `GET` | `/api/mmm/session/<id>/pnl` | P&L breakdown |
| `GET` | `/api/mmm/session/<id>/triggers` | Current trigger values |
| `GET` | `/api/mmm/session/<id>/safety` | Safety status |

### 4.5 Parameters

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/session/<id>/params` | Get current parameters |
| `PATCH` | `/api/mmm/session/<id>/params` | Update hot-reload params |

### 4.6 User Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mmm/session/<id>/both_sides_decision` | Handle both-sides-up decision |
| `POST` | `/api/mmm/session/<id>/manual-adjust` | User manual position change |
| `POST` | `/api/mmm/session/<id>/close-all` | Close all positions immediately |

### 4.7 WebSocket Events

| Event | When | Key Payload Fields |
|-------|------|-------------------|
| `mmm_heartbeat` | Every interval | session_id, ce_premium, pe_premium, triggers, status |
| `mmm_adjustment` | On adjustment | session_id, side, lots, premium, strike, loss_covered, type |
| `mmm_reversal` | On reversal | session_id, from_side, to_side, adj_pnl, action |
| `mmm_shift` | On strike shift | session_id, side, old_strike, new_strike, frozen_lots |
| `mmm_close_at_5` | On close-at-5 | session_id, side, strike, lots, realized_pnl |
| `mmm_both_sides` | Both sides up | session_id, ce_details, pe_details |
| `mmm_safety` | Safety event | session_id, type, level, message |
| `mmm_pnl_update` | Every interval | session_id, total, realized, unrealized, fees |
| `mmm_params_changed` | On hot-reload | session_id, changed_params |
| `mmm_session_created` | New session | session_id, summary |
| `mmm_status_change` | Status change | session_id, old_status, new_status |

---

## 5. STATE MODEL

### 5.1 Per-Side State (CE and PE each)

```python
{
    'original_lots': int,           # Lots sold at entry
    'original_premium': float,      # Premium per lot at entry
    'original_strike': float,       # Strike at entry
    'active_strike': float,         # Current monitoring strike (changes on shift)
    'adjustment_fills': [           # Fills at ACTIVE strike
        {'lots': int, 'premium': float, 'strike': float, 'timestamp': str}
    ],
    'adjustment_total_lots': int,   # Sum of lots in adjustment_fills
    'adjustment_avg': float,        # Weighted avg premium of adj fills
    'frozen_positions': [           # Old positions after strike shift
        {'strike': float, 'lots': int, 'entry_premium': float}
    ],
    'frozen_total_lots': int,       # Sum of frozen lots
    'active_lots': int,             # original_lots + adjustment_total_lots
    'total_lots': int,              # active_lots + frozen_total_lots
    'trigger_snapshot': {           # {strike: premium_at_last_update}
        'strike_value': float
    }
}
```

### 5.2 Global State

```python
{
    'session_id': str,              # UUID
    'strategy_status': str,         # IDLE → RUNNING → PAUSED/BOTH_SIDES_UP → STOPPED
    'last_aggressor': str,          # 'CE' | 'PE' | 'NONE'
    'adjustment_count': int,
    'reversal_count': int,
    'shift_count': int,
    'close_at_5_count': int,
    'adjustment_history': [],       # Ordered list of all adjustments
    'realized_pnl': float,         # From close-at-5 events
    'unrealized_pnl': float,       # Current mark-to-market
    'total_premium_collected': float,
    'total_fees': float,
    'peak_pnl': float,             # High-water mark for trailing stop
    'cooldown_active': bool,
    'created_at': str,              # ISO timestamp
    'entry_time': str,              # When initialized
    'params': {},                   # All configurable parameters
}
```

---

## 6. BACKEND MODULE DETAILS

### 6.1 mmm_state.py
- `create_session(mode, params)` → creates session dict with all state fields
- `initialize_side_from_entry(session, side, strike, premium, lots)` → sets per-side state
- `get_session_summary(session)` → compact summary for WebSocket/API

### 6.2 mmm_config.py
- `DEFAULT_PARAMS` dict with all 17 parameters
- `validate_params(user_params)` → validates types, ranges, returns (validated, errors)

### 6.3 mmm_storage.py
- `MMMStorage` class — JSON file persistence with file locking
- Methods: `save_session`, `get_session`, `get_all_sessions`, `delete_session`
- File: `data/mmm_sessions.json`

### 6.4 mmm_api.py (~1700 lines)
- Flask Blueprint at `/api/mmm`
- All REST endpoints (see Section 4)
- Uses lazy-loaded singletons: `get_storage()`, `get_initializer()`, `get_monitor()`

### 6.5 mmm_initializer.py (~700 lines)
- `MMMInitializer` class
- `auto_find_strikes(desired_ce, desired_pe, expiry)` → scans chain, finds best strikes
- `preview_strikes(...)` → returns found + alternatives without executing
- `get_available_expiries(underlying)` → delegates to OptionsChainService
- `get_spot_price(underlying)` → current BTC price
- `get_full_chain(expiry)` → complete options chain for manual selection
- Uses `OptionsChainService` (lazy loaded, sync, no auth needed)

### 6.6 mmm_executor.py (~592 lines)
- `MMMExecutor` class — smart order execution
- Mid-price placement with 60-second fill wait
- Auto-reprice cycle if not filled
- Handles both entry orders and adjustment orders

### 6.7 mmm_trigger.py (~170 lines)
- `evaluate_triggers(session, ce_now, pe_now)` → returns which sides triggered
- `min_trigger_move` filter
- Theta acceleration: widens triggers near expiry

### 6.8 mmm_engine.py (~548 lines)
- `MMMEngine.calculate_adjustment(session, aggressor, ce_now, pe_now)` → loss, lots, strike
- Standard loss formula: `active_loss + shifted_loss` (ALL positions included, Section 5 Case A)
- First-reversal P&L per-fill (Section 5 Case B)
- Lots calculation with ceiling, buffer, constraints
- `calculate_standard_loss()` accepts optional `fetch_premium_fn` to get live premiums for shifted positions

### 6.9 mmm_reversal.py
- `detect_reversal(session, current_aggressor)` → bool
- `compute_adjustment_pnl(session, side)` → float (positive=profitable, negative=underwater)
- Cooldown logic — skip 1 interval

### 6.10 mmm_strike_shift.py
- `check_shift_needed(session, side, current_premium)` → bool
- `find_new_strike(session, side, expiry)` → strike info
- `execute_shift(session, side, new_strike)` → freezes old, activates new

### 6.11 mmm_close_at_5.py
- `scan_closeable_positions(session, prices)` → list of positions at ≤ threshold
- `close_position(session, position)` → records realized P&L
- Handles side fully closed, both sides closed

### 6.12 mmm_safety.py
- `MMMSafety` class with all 8+ safety checks
- Methods: `check_position_cap`, `check_max_adjustments`, `check_max_loss`, `check_whipsaw`, `check_asymmetry`, `check_near_expiry`, `check_trailing_profit`, `check_pnl_guardrail`

### 6.13 mmm_monitor.py (~470 lines)
- `MMMMonitor` class — runs heartbeat in background thread per session
- `start_session_monitor(session_id)`, `stop_session_monitor(session_id)`
- `pause_session(session_id)`, `resume_session(session_id)`
- Each heartbeat: fetch prices → close-at-5 → safety → triggers → adjust → update → emit

### 6.14 mmm_websocket.py (~191 lines)
- 11 event emitter functions: `emit_heartbeat`, `emit_adjustment`, `emit_reversal`, `emit_shift`, `emit_close_at_5`, `emit_both_sides`, `emit_safety`, `emit_pnl_update`, `emit_params_changed`, `emit_session_created`, `emit_status_change`
- Uses Flask-SocketIO (same instance as main app)

### 6.15 __init__.py
- Exports `mmm_bp` (Blueprint) and `init_mmm()` (startup restoration)
- `init_mmm()` checks for sessions with status=RUNNING and restores their monitors

---

## 7. FRONTEND COMPONENT DETAILS

### 7.1 MMMDashboard.js (Main Container)
- **Header:** Title, BTC 0DTE badge, health indicator, connection status, New Session + Refresh buttons
- **Left Panel:** Session list with 3 tabs (Active/Idle/History), session cards with controls
- **Right Panel:** Session detail with 7 tabs (Overview/Positions/Triggers/Adjustments/P&L/Safety/Strike Map)
- **Dialogs:** CreateSessionDialog (expiry dropdown, mode selection, import fields), BothSidesAlert
- **State:** Uses `useMMM()` from MMMContext + `useMMMWebSocket(sessionId)` for live data

### 7.2 CreateSessionDialog (inside MMMDashboard.js)
- Fetches expiries from `/api/mmm/expiries` on open → shows as Select dropdown
- Shows BTC spot price from `/api/mmm/spot-price`
- Mode dropdown: Fresh (auto-find) or Import (existing positions)
- Core Parameters: desired CE/PE premium, initial lots, expiry (dropdown), interval, max loss
- Import mode: CE and PE sections with Strike Price, Fill Price ($), Lots — with placeholders
- Creates session via `mmmService.createSession(config)`
- For Fresh mode, shows info alert: "After creating, use Config Panel to auto-find strikes"

### 7.3 MMMConfigPanel.js (~866 lines)
- Shown for IDLE/STOPPED sessions in the detail panel
- 3 modes: Auto-Find / Manual Select / Import Existing
- **Auto-Find:** Expiry dropdown + CE/PE desired premium + Find button → StrikePreviewTable with alternatives → Confirm & Initialize
- **Manual Select:** MMMStrikeSelector component (browse full chain)
- **Import Existing:** CE/PE fields for Strike, Fill Price, Symbol → Import & Initialize
- StrikePreviewTable: shows best strike + expandable alternatives with "Use" button
- Entry Summary: total premium calculation before confirm

### 7.4 MMMContext.js (~449 lines)
- `MMMProvider({ children, socket })` — wraps dashboard
- Manages: sessions array, selectedSessionId, loading, error, healthStatus, connectionStatus, paramsInfo, bothSidesAlert
- Fetches sessions on mount, auto-refreshes every 30s
- WebSocket listeners for all 11 mmm_* events
- `useMMM()` hook — throws if used outside MMMProvider

### 7.5 Key UI Patterns
- **Socket prop flow:** App.js `connectionManagerRef.current?.socket` → `<MMMProvider socket={socket}>` → MMMContext attaches listeners
- **Lazy loading:** `MMMDashboard` loaded via `React.lazy()` with `Suspense` fallback
- **Error isolation:** `MMMErrorBoundary` wraps everything, prevents MMM crashes from affecting main app
- **Status colors:** IDLE=gray, RUNNING=green, PAUSED=orange, BOTH_SIDES_UP=red, STOPPED=dark gray
- **Data flow:** REST API for initial load + actions, WebSocket for real-time updates

---

## 8. DATA FLOW

### 8.1 Session Lifecycle

```
User clicks "+ New Session"
  → CreateSessionDialog opens
  → User selects mode, expiry, params
  → POST /api/mmm/session/create
  → Session created with status=IDLE
  → If import mode: sides initialized immediately

User selects session (IDLE) → ConfigPanel shown
  → Auto-Find: preview strikes → confirm → init-fresh
  → Manual: browse chain → select → init-fresh
  → Import: enter data → init-import

User clicks Start
  → POST /api/mmm/session/<id>/start
  → MMMMonitor starts background thread
  → status = RUNNING
  → Heartbeat loop begins

Running → every interval:
  → Monitor fetches prices
  → Runs close-at-5, safety, triggers
  → If adjustment needed → executes, updates state
  → Emits WebSocket events → frontend updates in real-time

User can: Pause/Resume/Stop/Change params
```

### 8.2 Options Chain Data

MMM uses `OptionsChainService` (existing codebase) to fetch:
- Available expiry dates
- BTC spot price
- Full options chain (strikes, bids, asks, greeks)

This is the same service used by the Options Chain Panel in the main WebUI. MMM lazy-loads it to avoid circular imports.

---

## 9. OPERATIONS & DEPLOYMENT

### 9.1 Backend

- **Flask app:** `webui/backend/app.py` on port 5555
- **LaunchAgent:** `com.gridbot.webui` (auto-restart on crash)
- **Restart:** `launchctl stop com.gridbot.webui && sleep 3 && launchctl start com.gridbot.webui`
- **Blueprint registration:** Lines 476-487 in app.py (try/except isolated)
- **Session data:** Persisted to `data/mmm_sessions.json`
- **Logs:** Standard Python logging, prefix `[MMM]`

### 9.2 Frontend

- **Build:** `cd webui/frontend && npm run build` (react-app-rewired)
- **Served:** Flask serves production build from `webui/frontend/build/`
- **Dev mode:** `npm start` on port 3000 with proxy to 5555
- **After code changes:** Must rebuild and restart backend for production

### 9.3 Verification Commands

```bash
# Health check
curl -s http://localhost:5555/api/mmm/health | python3 -m json.tool

# List expiries
curl -s http://localhost:5555/api/mmm/expiries | python3 -m json.tool

# List sessions
curl -s http://localhost:5555/api/mmm/sessions | python3 -m json.tool

# BTC spot price
curl -s http://localhost:5555/api/mmm/spot-price | python3 -m json.tool

# Import test
python3 -c "from webui.backend.routes.mmm import mmm_bp, init_mmm; print('OK')"
```

---

## 10. COMMON ISSUES & FIXES

### 10.1 "MMM tab doesn't appear"
- Check `App.js` has lazy import, tab definition, and sectionContent for 'mmm'
- Ensure `<MMMProvider socket={socket}>` wraps `<MMMDashboard />`
- Rebuild frontend: `cd webui/frontend && npm run build`
- Restart backend: `launchctl stop/start com.gridbot.webui`

### 10.2 "API returns 404 for /api/mmm/*"
- Backend hasn't been restarted since MMM code was added
- Check `app.py` has blueprint registration
- Run import test: `python3 -c "from webui.backend.routes.mmm import mmm_bp"`

### 10.3 "Expiry dropdown empty"
- API `/api/mmm/expiries` must return data from OptionsChainService
- Check if exchange API (Delta/Deribit) is reachable
- Verify `mmm_initializer.py` can access `OptionsChainService`

### 10.4 "WebSocket events not arriving"
- Ensure `MMMProvider` receives the socket prop from App.js
- Socket is `connectionManagerRef.current?.socket` (line 686 in App.js)
- Check console for socket.io connection errors

### 10.5 "ConfigPanel not showing for IDLE session"
- Dashboard condition checks `fullSession.strategy_status || fullSession.status`
- ConfigPanel checks `sessionStatus` against 'IDLE', 'STOPPED' (case-insensitive)
- Backend uses uppercase status values (IDLE, RUNNING, etc.)

### 10.6 "Session won't start"
- Session must be initialized first (init-fresh or init-import)
- Check that CE and PE sides have strike/premium/lots set
- Verify MMMMonitor can start a background thread

---

## 11. EXTENSION GUIDE

### 11.1 Adding a New Safety Check
1. Add method in `mmm_safety.py` following existing pattern
2. Call it from `mmm_monitor.py` heartbeat loop (step 4)
3. Add WebSocket emission via `emit_safety()`
4. Add indicator in `MMMSafetyPanel.js`

### 11.2 Adding a New API Endpoint
1. Add route in `mmm_api.py` under appropriate section
2. Add service method in `mmmService.js`
3. Call from appropriate frontend component

### 11.3 Adding a New WebSocket Event
1. Add emitter function in `mmm_websocket.py`
2. Add listener in `MMMContext.js` (useEffect socket.on)
3. Pass data through context to consuming component

### 11.4 Modifying Adjustment Logic
- Core math is in `mmm_engine.py`
- Reversal logic is in `mmm_reversal.py`
- Trigger evaluation is in `mmm_trigger.py`
- All formulas reference sections in `MONEY_POWER_CALCULATION_LOGIC.md`

---

## 12. KEY DESIGN DECISIONS

1. **Complete isolation:** MMM has zero imports from/to existing codebase (except App.js integration and OptionsChainService). Failures in MMM never crash the main app.

2. **Per-fill P&L on reversal:** Unlike averaging, each adjustment fill's P&L is computed at its actual strike's current premium. Accurate across multiple strikes and shifts.

3. **Both-sides-up requires human judgment:** The algo pauses and waits. No automatic action in the most dangerous scenario.

4. **Triggers update on BOTH sides:** After every adjustment, both CE and PE snapshots reset. This ensures the "safe zone" expands correctly.

5. **ALL positions always included in loss calculations:** Active positions AND shifted positions at old strikes are ALL evaluated at their live premiums in the standard adjustment formula. No position is ever excluded. The `shift_threshold` only controls where to open NEW positions. (Updated Feb 16, 2026 — previously positions at old strikes were excluded, causing invisible loss accumulation.)

6. **Close-at-5 runs on ALL positions:** Active, adjustment, and shifted — across all strikes. Any position at ≤5 gets closed for profit.

7. **Ceiling rounding + buffer:** Lots calculation always rounds up (ceil) and adds buffer%. Never under-hedged.

8. **Socket prop from App.js:** MMMProvider doesn't create its own socket connection — it receives the app's existing socket, avoiding duplicate connections.

---

## 13. TESTING

Test files in `webui/backend/routes/mmm/tests/`:

| File | What It Tests |
|------|--------------|
| `test_mmm_engine.py` | Loss calc, lots, ceiling, buffer, P&L |
| `test_mmm_reversal.py` | Detection, cooldown, skip, multi-cycle |
| `test_mmm_strike_shift.py` | Shift detection, freeze, new strike |
| `test_mmm_close_at_5.py` | Scan, close, side closed, both closed |
| `test_mmm_safety.py` | All safety mechanisms |
| `test_mmm_integration.py` | State, config, triggers, storage |
| `test_mmm_initializer.py` | Strike finding, chain parsing |

Run: `cd webui/backend && python -m pytest routes/mmm/tests/ -v`

---

*This document is the single source of truth for any AI agent working on the MMM algorithm. Reference `MONEY_POWER_CALCULATION_LOGIC.md` for the sealed mathematical logic and `MMM_DEVELOPMENT_PLAN.md` for the development history.*
