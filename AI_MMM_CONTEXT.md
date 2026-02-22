# AI_MMM_CONTEXT.md — Complete MMM Algorithm Reference for AI Agents

> **Purpose:** This document provides every detail an AI agent needs to understand, debug, modify, or extend the MMM (Money Mind & Method) algorithm and its WebUI implementation.
>
> **Last Updated:** February 22, 2026
> **Status:** All phases complete. Production-ready. Verified against actual codebase. Includes all modules through February 2026.

---

## 1. WHAT IS MMM?

MMM is a **BTC 0DTE options premium selling algorithm** with automatic adjustment. It:

1. **Sells** both CE (call) and PE (put) options on BTC at OTM strikes
2. **Monitors** premiums adaptively (60s–1200s depending on trigger proximity)
3. **Adjusts** when one side's premium rises above its trigger — sells more of the opposite side to cover the loss
4. **Shifts strikes** when opposing premium is too low to provide meaningful hedge
5. **Closes positions at ≤5** premium to lock profit (dynamic threshold during wind-down)
6. **Handles reversals** by computing actual adjustment P&L before hedging
7. **Wind-down mode** gracefully closes positions in the final hours before expiry
8. **Safety mechanisms** protect against runaway losses, whipsaw, margin exhaustion
9. **Adopt mode** imports live exchange positions into MMM without manual entry
10. **Regime controls** block adjustments during IV spikes, extreme gamma, or strong price trends
11. **Margin guardian** monitors real exchange margin utilization and enforces tier-based defense
12. **Circuit breaker** isolates exchange API failures gracefully without terminating sessions

The complete calculation logic is defined in `MONEY_POWER_CALCULATION_LOGIC.md` (22 sections). The development plan is in `MMM_DEVELOPMENT_PLAN.md` (all phases complete).

---

## 2. ALGORITHM CORE LOGIC

### 2.1 Entry (Section 3)

**Mode A — Fresh:** User provides desired CE/PE premium + lots + expiry → algo scans the options chain → finds OTM strikes closest to desired premium → user confirms → positions sold.

**Mode B — Import:** User enters existing CE/PE strike, fill price, lots → algo initializes state without placing orders.

**Mode C — Adopt:** Fetches open short BTC options from Delta Exchange (`mmm_adopter.py`), user selects positions → algo maps them to active/frozen state per side and initializes without placing orders. Trigger snapshots default to current prices ("take over from NOW").

### 2.2 Heartbeat Loop (Section 4)

Every `interval` seconds (adaptive: 60–1200s, see §2.10):

```
1. Fetch CE premium at active_ce_strike → CE_now
2. Fetch PE premium at active_pe_strike → PE_now
3. Run Close-at-5 on ALL positions (active + frozen)
   — if wind-down mode active, use elevated threshold (§2.11)
4. Run Safety Checks (mmm_safety.py)
5. Run Regime Checks (mmm_regime.py) — abort adjustment if regime blocks
6. If status ≠ RUNNING → skip adjustment logic
7. Run Margin Guardian check (mmm_margin_guardian.py) — block sells if YELLOW+
8. Compute excess: ce_excess = CE_now - trigger_snapshot[active_ce_strike]
9. Apply min_trigger_move filter (PERCENTAGE-BASED):
   ce_threshold = trigger_snapshot × (min_trigger_move_pct / 100)
   ce_triggered = ce_excess > ce_threshold
10. Four outcomes:
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
| `min_trigger_move_pct` | 3% | **Yes** |
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
| `adaptive_interval_enabled` | true | **Yes** |
| `adaptive_max_interval` | 1200 | **Yes** |
| `wind_down_enabled` | true | **Yes** |
| `wind_down_minutes` | 120 | **Yes** |
| `wind_down_threshold_pct` | 25 | **Yes** |
| `wind_down_floor_action` | stop_adjustments | **Yes** |
| `wind_down_on_atm` | false | **Yes** |

"Hot Reload = Yes" means the parameter can be changed via WebUI while the algo is running and takes effect on the next heartbeat interval.

### 2.10 Adaptive Heartbeat Interval (Added Feb 17, 2026)

The heartbeat interval dynamically adjusts based on trigger proximity:

| Condition | Interval | Rationale |
|-----------|----------|----------|
| ≥80% of trigger exceeded | 60s | Action imminent |
| ≥50% exceeded | 120s | Getting close |
| ≥30% exceeded | 180s | Moderate movement |
| <30% exceeded | User-set interval | Normal monitoring |
| Both premiums declining | 600–1200s | Premiums moving favorably, relax |

**Implementation:** `mmm_trigger.py` → `compute_adaptive_interval()` with `ADAPTIVE_INTERVAL_TIERS`.

### 2.11 Wind-Down Mode (Added Feb 17, 2026)

Activates when `minutes_to_expiry ≤ wind_down_minutes` (default 120 = 2 hours):

1. **Elevated close threshold**: Closes positions at premium ≤ `entry_premium × (wind_down_threshold_pct / 100)` instead of static 5
2. **LIFO order**: Closes most recently added positions first
3. **Floor action**: If positions can't be closed, executes `wind_down_floor_action` (stop_adjustments / close_all / alert)
4. **ATM auto-trigger** (`wind_down_on_atm`): When ON, wind-down is automatically activated the moment any **original** strike becomes ATM (spot within 0.5% of entry strike). This is a gentler alternative to `close_at_atm` — instead of an immediate close-all, the algo switches to gradual LIFO buyback. The session flag `_atm_wind_down_triggered` is set once and persists for the session. Checked in `is_wind_down_active()` in `mmm_wind_down.py`.

**Implementation:** `mmm_wind_down.py` + `mmm_monitor.py` (ATM detection block before `close_at_atm` check) + `mmm_config.py` + `MMMSettingsDialog.js`.

### 2.12 Regime Controls (Added Feb 20, 2026)

Three pre-adjustment controls checked every heartbeat BEFORE trigger evaluation:

**A. Volatility Regime Filter** — detects IV spikes + realized volatility. States: `NORMAL`, `ELEVATED`, `HIGH`. When HIGH, blocks new adjustments.

**B. Portfolio Gamma Cap** — enforces dollar-gamma limits. States: `NORMAL`, `SOFT`, `HARD`, `EMERGENCY`. Blocks adjustments when gamma exposure is too large.

**C. Trend Detection Guard** — detects strong directional BTC moves. States: `NORMAL`, `TREND_UP`, `TREND_DOWN`. Blocks adjustments into trending markets.

Aggregate actions: `NORMAL` (proceed), `WARN` (log), `BLOCK` (skip adjustment), `EMERGENCY` (close positions).

**Implementation:** `mmm_regime.py` + monitor heartbeat + `MMMRegimePanel.js` (frontend).

### 2.13 Margin Guardian (Added Feb 20, 2026)

Queries Delta Exchange for real margin utilization every heartbeat. Enforces tier-based defense:

| Tier | Threshold | Action |
|------|-----------|--------|
| GREEN | < green_pct | Normal operation |
| YELLOW | ≥ yellow_pct | Block new sells, log caution |
| ORANGE | ≥ orange_pct | Force auto wind-down (aggressive buyback) |
| RED | ≥ red_pct | Emergency reduce — taker orders, close all |
| CRITICAL | ≥ critical_pct | Survival mode — close all + stop session |

Formula: `utilization% = (position_margin + order_margin) / net_equity × 100`
where `net_equity = balance + unrealized_pnl`. Sends Telegram alerts on tier escalation.

**Implementation:** `mmm_margin_guardian.py` + `mmm_telegram.py` + `MMMMarginGuardianPanel.js`.

### 2.14 Circuit Breaker (Added Feb 18, 2026)

Three-state circuit breaker protecting the heartbeat loop from exchange API failures:

| State | Behavior |
|-------|----------|
| CLOSED (nominal) | All requests pass through |
| OPEN (tripped) | Fast-fail; backoff 1-3: partial beat (close-at-5 + safety only); backoff 4+: full skip |
| HALF_OPEN (probe) | One trial request; success → CLOSED; fail → OPEN |

CLOSED → OPEN after `FAILURE_THRESHOLD = 3` consecutive failures. OPEN → HALF_OPEN after `RESET_TIMEOUT = 30s`. Never terminates the session — isolates, waits, self-heals.

**Implementation:** `mmm_circuit_breaker.py` + `mmm_monitor.py`.

---

## 3. ARCHITECTURE

### 3.1 File Structure (Complete — Verified February 22, 2026)

```
webui/
├── backend/
│   └── routes/
│       └── mmm/                              ← Isolated backend module
│           ├── __init__.py                   ← Blueprint registration, init_mmm()
│           ├── mmm_api.py                    ← REST API (~3398 lines, all endpoints)
│           ├── mmm_state.py                  ← State model, session creation (~520 lines)
│           ├── mmm_config.py                 ← Parameter validation, defaults
│           ├── mmm_constants.py              ← Shared constants (LOT_SIZE_BTC = 0.001)
│           ├── mmm_storage.py                ← SQLite persistence (mmm_sessions.db, ~398 lines)
│           ├── mmm_websocket.py              ← 17 WebSocket event emitters (~240 lines)
│           ├── mmm_initializer.py            ← Strike selection, chain data, expiries (~733 lines)
│           ├── mmm_executor.py               ← Smart execution, mid-price, reprice (~1199 lines)
│           ├── mmm_trigger.py                ← Trigger evaluation, theta acceleration (~348 lines)
│           ├── mmm_engine.py                 ← Core adjustment, P&L computation (~640 lines)
│           ├── mmm_reversal.py               ← Reversal detection, cooldown, skip
│           ├── mmm_strike_shift.py           ← Freeze/find/activate strike shift (~342 lines)
│           ├── mmm_close_at_5.py             ← Position scanning, buyback, profit lock (~322 lines)
│           ├── mmm_safety.py                 ← All safety checks, trailing stop (~636 lines)
│           ├── mmm_monitor.py                ← Background heartbeat loop thread (~3838 lines)
│           ├── mmm_wind_down.py              ← Wind-down mode logic (~348 lines)
│           ├── mmm_activity.py               ← Activity log ring buffer (added Feb 15, 2026)
│           ├── mmm_adopter.py                ← Adopt exchange positions into MMM (added Feb 18, 2026)
│           ├── mmm_analytics_aggregator.py   ← Institutional analytics from SQLite (added Feb 18, 2026)
│           ├── mmm_analytics_storage.py      ← Analytics data persistence
│           ├── mmm_circuit_breaker.py        ← 3-state API fault isolation (added Feb 18, 2026)
│           ├── mmm_heartbeat_health.py       ← Beat telemetry & A–F health grades (added Feb 18, 2026)
│           ├── mmm_margin_guardian.py        ← Real-time margin monitoring (added Feb 20, 2026)
│           ├── mmm_pending_orders.py         ← Duplicate order prevention (added Feb 18, 2026)
│           ├── mmm_regime.py                 ← Regime-aware risk controls (added Feb 20, 2026)
│           ├── mmm_telegram.py               ← Telegram alert notifications (added Feb 20, 2026)
│           ├── mmm_walkthrough.py            ← Algo walkthrough generator (added Feb 16, 2026)
│           ├── mmm_watchdog.py               ← Monitor watchdog/auto-restart (added Feb 18, 2026)
│           ├── mmm_sessions.db               ← SQLite session data (replaces mmm_sessions.json)
│           └── tests/                        ← Unit tests (6 files)
│
├── frontend/
│   └── src/
│       └── components/
│           └── mmm/                          ← Isolated frontend module
│               ├── index.js                  ← Barrel exports
│               ├── MMMDashboard.js           ← Main dashboard container
│               ├── MMMConfigPanel.js         ← 3-mode config: Fresh/Manual/Import
│               ├── MMMStrikeSelector.js      ← Manual strike browser from chain
│               ├── MMMContext.js             ← React Context + WebSocket listeners
│               ├── MMMErrorBoundary.js       ← Error boundary wrapper
│               ├── mmmService.js             ← API service client (axios)
│               ├── MMMStatusBanner.js        ← Running/Paused/Stopped status bar
│               ├── MMMPositionsTable.js      ← Active + frozen positions table
│               ├── MMMTriggerGauge.js        ← Visual trigger gauges per side
│               ├── MMMAdjustmentLog.js       ← Adjustment history timeline
│               ├── MMMSessionCard.js         ← Session card with controls
│               ├── MMMStrikeMap.js           ← Strike visualization
│               ├── MMMPnLChart.js            ← P&L chart (Recharts)
│               ├── MMMBothSidesAlert.js      ← Both-sides decision modal
│               ├── MMMSafetyPanel.js         ← Safety dashboard (8 indicators)
│               ├── MMMConsolidatedPositions.js ← Grouped fills by (side, strike)
│               ├── MMMGreeksPanel.js         ← Live Greeks & IV panel
│               ├── MMMActivityFeed.js        ← Real-time background activity log
│               ├── MMMAdoptPanel.js          ← Adopt existing exchange positions UI
│               ├── MMMAlgoCalculations.js    ← Walkthrough calculation display
│               ├── MMMAnalyticsPanel.js      ← Institutional analytics dashboard
│               ├── MMMAnalyticsSummary.js    ← Analytics summary cards
│               ├── MMMAnalyticsTable.js      ← Analytics session history table
│               ├── MMMEducation.js           ← Educational tooltips and guides
│               ├── MMMMarginGuardianPanel.js ← Margin utilization & tier display
│               ├── MMMRegimePanel.js         ← Regime status (vol/gamma/trend)
│               ├── MMMSettingsDialog.js      ← Hot-reload params dialog (~448 lines)
│               ├── hooks/
│               │   ├── useMMMParams.js       ← Parameter dirty tracking
│               │   └── useMMMWebSocket.js    ← WebSocket subscription hook
│               └── utils/
│                   ├── mmmFormatters.js      ← Number/time/strike formatters
│                   └── mmmCalculations.js    ← Client-side P&L math
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
├── MMMWatchdog: supervisor thread that auto-restarts dead monitors
├── MMMStorage: SQLite persistence (data/mmm_sessions.db)
│   └── Auto-migrates legacy data/mmm_sessions.json on first run
├── CircuitBreaker: per-session API fault isolation
├── MarginGuardian: per-session real-time margin monitoring
├── SocketIO: emits mmm_* events to frontend
└── LaunchAgent: com.gridbot.webui (auto-restart)

React Frontend (production build served by Flask)
├── MMMProvider: wraps MMMDashboard, receives socket prop from App.js
├── MMMContext: manages sessions, WebSocket listeners, state
├── MMMDashboard: session list + detail view with multiple tabs
└── CreateSessionDialog: mode selection (Fresh/Import/Adopt), expiry, params
```

### 3.4 Key Constants

```python
# mmm_constants.py
LOT_SIZE_BTC = 0.001  # 1 BTC option lot = 0.001 BTC on Delta Exchange
                       # USD value for N lots = premium_per_btc × N × LOT_SIZE_BTC
```

---

## 4. API REFERENCE

### 4.1 Session Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/health` | Health check |
| `GET` | `/api/mmm/sessions` | List all sessions |
| `GET` | `/api/mmm/session/<id>` | Get full session details |
| `POST` | `/api/mmm/session/create` | Create session (mode: fresh/import/adopt) |
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
| `GET` | `/api/mmm/chain-data` | Full options chain for manual selection |
| `POST` | `/api/mmm/validate-selection` | Validate a manually selected strike |
| `POST` | `/api/mmm/session/<id>/execute-entry` | Smart execution at mid-price |

### 4.3 Adopt Mode

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/exchange-positions` | Fetch open short BTC options from Delta Exchange |
| `POST` | `/api/mmm/session/<id>/adopt` | Map exchange positions into session state |

### 4.4 Session Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mmm/session/<id>/start` | Start monitoring |
| `POST` | `/api/mmm/session/<id>/pause` | Pause monitoring |
| `POST` | `/api/mmm/session/<id>/resume` | Resume monitoring |
| `POST` | `/api/mmm/session/<id>/stop` | Stop session |
| `POST` | `/api/mmm/session/<id>/force-heartbeat` | Trigger an immediate heartbeat |
| `POST` | `/api/mmm/session/<id>/reduce-position` | User-initiated position reduction |

### 4.5 Real-Time Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/session/<id>/state` | Full session state snapshot |
| `GET` | `/api/mmm/session/<id>/positions` | All positions (active + frozen) |
| `GET` | `/api/mmm/session/<id>/history` | Adjustment history |
| `GET` | `/api/mmm/session/<id>/pnl-timeline` | P&L over time |
| `GET` | `/api/mmm/session/<id>/triggers` | Current trigger values |
| `GET` | `/api/mmm/session/<id>/safety` | Safety status |
| `GET` | `/api/mmm/session/<id>/regime` | Regime status (vol/gamma/trend) |
| `GET` | `/api/mmm/session/<id>/greeks-iv` | Live Greeks, IV, mark price for all positions |
| `GET` | `/api/mmm/session/<id>/walkthrough` | Algo calculation walkthrough log |
| `GET` | `/api/mmm/session/<id>/beat-health` | Heartbeat health (latency percentiles, A–F grade) |
| `GET` | `/api/mmm/session/<id>/margin` | Session margin utilization from exchange |
| `GET` | `/api/mmm/session/<id>/monitor` | Monitor thread status |
| `GET` | `/api/mmm/monitors` | Status of all active monitors |

### 4.6 Parameters

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/params/info` | Descriptions for all parameters (for tooltips) |
| `GET` | `/api/mmm/session/<id>/params` | Get current parameters |
| `PATCH` | `/api/mmm/session/<id>/params` | Update hot-reload params |

### 4.7 User Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mmm/session/<id>/both_sides_decision` | Handle both-sides-up decision |
| `POST` | `/api/mmm/session/<id>/close-all` | Close all positions immediately |

### 4.8 Exchange Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/exchange/margin` | Raw exchange margin data |
| `GET` | `/api/mmm/exchange/positions` | All open exchange positions |
| `GET` | `/api/mmm/exchange/orders` | All open exchange orders |

### 4.9 Activity Log

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/activities` | Recent background activity entries (ring buffer, max 200) |

### 4.10 Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/session/<id>/analytics` | Per-session analytics |
| `GET` | `/api/mmm/analytics/history` | Analytics history (all sessions) |
| `GET` | `/api/mmm/analytics/aggregated` | Aggregated institutional analytics |

### 4.11 WebSocket Events (17 total)

| Event | When | Key Payload Fields |
|-------|------|-------------------|
| `mmm_heartbeat` | Every interval | session_id, ce_premium, pe_premium, triggers, status, adaptive_tier, wind_down_active |
| `mmm_price_tick` | Per-price update | session_id, premium_map |
| `mmm_adjustment` | On adjustment | session_id, side, lots, premium, strike, loss_covered, type |
| `mmm_reversal` | On reversal | session_id, from_side, to_side, adj_pnl, action |
| `mmm_shift` | On strike shift | session_id, side, old_strike, new_strike, frozen_lots |
| `mmm_close_at_5` | On close-at-5 | session_id, side, strike, lots, realized_pnl |
| `mmm_both_sides` | Both sides up | session_id, ce_details, pe_details |
| `mmm_safety` | Safety event | session_id, type, level, message |
| `mmm_pnl_update` | Every interval | session_id, total, realized, unrealized, fees |
| `mmm_params_changed` | On hot-reload | session_id, changed_params |
| `mmm_session_created` | New session | session_id, summary |
| `mmm_session_deleted` | Session deleted | session_id |
| `mmm_status_change` | Status change | session_id, old_status, new_status |
| `mmm_activity` | New activity log entry | activity dict (type, message, session_id, timestamp) |
| `mmm_activities_updated` | Activity log refresh | refresh: true |
| `mmm_regime` | Regime status update | session_id, regime_status (vol/gamma/trend/aggregate) |

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
    '_atm_wind_down_triggered': bool,  # Set once when ATM wind-down fires; persists session
    '_watchdog_restarts': int,      # Count of monitor auto-restarts by watchdog
}
```

---

## 6. BACKEND MODULE DETAILS

### 6.1 mmm_state.py (~520 lines)
- `create_session(mode, params)` → creates session dict with all state fields
- `initialize_side_from_entry(session, side, strike, premium, lots)` → sets per-side state
- `get_session_summary(session)` → compact summary for WebSocket/API

### 6.2 mmm_config.py
- `PARAM_RULES` dict with all 25 parameters (including adaptive + wind-down)
- `validate_params(user_params)` → validates types, ranges, returns (validated, errors)
- `get_param_info()` → returns descriptions for all params for WebUI tooltips

### 6.3 mmm_constants.py
- `LOT_SIZE_BTC = 0.001` — Delta Exchange BTC options: 1 lot = 0.001 BTC
- Imported by: `mmm_engine.py`, `mmm_adopter.py`, `mmm_walkthrough.py`, `mmm_regime.py`
- Used wherever premiums need to be converted to USD notional values

### 6.4 mmm_storage.py (~398 lines)
- `MMMStorage` class — **SQLite persistence** (migrated from JSON on Feb 17, 2026)
- DB file: `data/mmm_sessions.db`
- Schema: `mmm_sessions(session_id TEXT PRIMARY KEY, params_json TEXT, data_json TEXT)`
- `params_json` stores params separately for atomic hot-reload
- On first init, auto-migrates `data/mmm_sessions.json` → renamed to `.json.migrated`
- Methods: `save_session`, `get_session`, `get_all_sessions`, `delete_session`

### 6.5 mmm_api.py (~3398 lines)
- Flask Blueprint at `/api/mmm`
- All REST endpoints (see Section 4)
- Uses lazy-loaded singletons: `get_storage()`, `get_initializer()`, `get_monitor()`

### 6.6 mmm_initializer.py (~733 lines)
- `MMMInitializer` class
- `auto_find_strikes(desired_ce, desired_pe, expiry)` → scans chain, finds best strikes
- `preview_strikes(...)` → returns found + alternatives without executing
- `get_available_expiries(underlying)` → delegates to OptionsChainService
- `get_spot_price(underlying)` → current BTC price
- `get_full_chain(expiry)` → complete options chain for manual selection
- Uses `OptionsChainService` (lazy loaded, sync, no auth needed)

### 6.7 mmm_executor.py (~1199 lines)
- `MMMExecutor` class — smart order execution
- Mid-price placement with 60-second fill wait
- Auto-reprice cycle if not filled
- Handles both entry orders and adjustment orders

### 6.8 mmm_trigger.py (~348 lines)
- `evaluate_triggers(session, ce_now, pe_now)` → returns which sides triggered
- Percentage-based `min_trigger_move_pct` filter (3% of trigger level)
- `compute_adaptive_interval()` → dynamic interval based on trigger proximity
- Theta acceleration: widens triggers near expiry

### 6.9 mmm_engine.py (~640 lines)
- `MMMEngine.calculate_adjustment(session, aggressor, ce_now, pe_now)` → loss, lots, strike
- Standard loss formula: `active_loss + shifted_loss` (ALL positions included, Section 5 Case A)
- First-reversal P&L per-fill (Section 5 Case B)
- Lots calculation with ceiling, buffer, constraints
- `calculate_standard_loss()` accepts optional `fetch_premium_fn` to get live premiums for shifted positions

### 6.10 mmm_reversal.py
- `detect_reversal(session, current_aggressor)` → bool
- `compute_adjustment_pnl(session, side)` → float (positive=profitable, negative=underwater)
- Cooldown logic — skip 1 interval

### 6.11 mmm_strike_shift.py (~342 lines)
- `check_shift_needed(session, side, current_premium)` → bool
- `find_new_strike(session, side, expiry)` → strike info
- `execute_shift(session, side, new_strike)` → freezes old, activates new

### 6.12 mmm_close_at_5.py (~322 lines)
- `scan_closeable_positions(session, prices)` → list of positions at ≤ threshold
- `close_position(session, position)` → records realized P&L
- Handles side fully closed, both sides closed

### 6.13 mmm_safety.py (~636 lines)
- `MMMSafety` class with all 8+ safety checks
- Methods: `check_position_cap`, `check_max_adjustments`, `check_max_loss`, `check_whipsaw`, `check_asymmetry`, `check_near_expiry`, `check_trailing_profit`, `check_pnl_guardrail`

### 6.14 mmm_monitor.py (~3838 lines)
- `MMMMonitor` class — runs heartbeat in background thread per session
- `start_session_monitor(session_id)`, `stop_session_monitor(session_id)`
- `pause_session(session_id)`, `resume_session(session_id)`
- Each heartbeat: fetch prices (circuit breaker) → close-at-5 → wind-down check → regime check → margin guardian → safety → pending order guard → triggers → adjust → walkthrough log → activity log → WebSocket emit
- Adaptive interval: selects next interval based on `compute_adaptive_interval()`
- Wind-down integration: calls `_process_wind_down_buyback()` before normal adjustment logic
- Prefetches all premiums in parallel for multi-strike sessions

### 6.15 mmm_wind_down.py (~348 lines)
- `is_wind_down_active(session, minutes_to_expiry)` → bool
- `compute_wind_down_action(session, premiums, minutes_to_expiry)` → action dict
- `get_lifo_close_fills(session, side)` → positions in LIFO order for closing
- `apply_lifo_removals(session, side, fills)` → removes closed positions from state
- `get_wind_down_close_threshold(entry_premium, params)` → elevated threshold

### 6.16 mmm_websocket.py (~240 lines)
- 17 event emitter functions (see Section 4.11 for full list)
- Key emitters: `emit_heartbeat`, `emit_price_tick`, `emit_adjustment`, `emit_reversal`, `emit_strike_shift`, `emit_close_at_5`, `emit_both_sides_alert`, `emit_safety`, `emit_pnl_update`, `emit_params_changed`, `emit_session_created`, `emit_session_deleted`, `emit_status_change`, `emit_activity`, `emit_activities_updated`, `emit_regime`
- Heartbeat payload includes `adaptive_tier` and `wind_down_active` fields
- Uses Flask-SocketIO (same instance as main app)

### 6.17 __init__.py
- Exports `mmm_bp` (Blueprint) and `init_mmm()` (startup restoration)
- `init_mmm()`: checks for sessions with status=RUNNING, restores their monitors, starts MMMWatchdog supervisor thread

### 6.18 mmm_activity.py (Added Feb 15, 2026)
- In-memory + persisted ring buffer of background activity events (max 200)
- Persisted to `data/mmm_activity_log.json`
- Captures: order lifecycle (placing/filled/repricing/failed), entry, session lifecycle, heartbeat execution, adjustments, reversals, safety events
- `ACTIVITY_TYPES` dict defines all event type labels
- Used by `MMMActivityFeed.js` frontend to show real-time "what is the algo doing" feed

### 6.19 mmm_adopter.py (Added Feb 18, 2026, ~561 lines)
- `fetch_exchange_btc_options(expiry_filter)` → fetches open short BTC options from Delta Exchange
- `classify_positions(selected, session)` → maps selected positions to active/frozen per side
- `validate_adoptable(positions)` → sanity-checks before committing
- `build_adopted_session_state(...)` → produces full session state dict
- Uses `DeltaClient` (lazy loaded). Zero changes to runtime modules.
- Adopted sessions behave identically to import sessions once state is built

### 6.20 mmm_analytics_aggregator.py (Added Feb 18, 2026, ~763 lines)
- Answers three core questions from REAL historical SQLite data:
  1. Capital planning: margin reserve needed to scale to N lots/side
  2. Risk profiling: auto-close/max-loss frequency, worst-case drawdown
  3. Strategy validation: win rate, profit factor, expected value per session
- All numbers from real data — nothing simulated

### 6.21 mmm_analytics_storage.py
- Persists per-session analytics snapshots for historical analysis
- Used by `mmm_analytics_aggregator.py` and analytics API endpoints

### 6.22 mmm_circuit_breaker.py (Added Feb 18, 2026)
- `CircuitBreaker` class — three states: `CLOSED`, `OPEN`, `HALF_OPEN`
- `FAILURE_THRESHOLD = 3`, `RESET_TIMEOUT = 30.0s`
- `CONSECUTIVE_OPEN_ALERT_THRESHOLD = 3` (emits safety event after 3 successive probe failures)
- Graduated response: partial beat (close-at-5 only) on early backoff; full skip on backoff 4+
- Never terminates the session — always self-healing

### 6.23 mmm_heartbeat_health.py (Added Feb 18, 2026, ~366 lines)
- `HeartbeatHealth` class — attached to each `MMMMonitor` instance (pure observability)
- `BeatRecord` dataclass: timestamp, latency_ms, outcome (`ok`/`partial`/`miss`/`error`), premiums
- Rolling windows: 100 beats for latency percentiles, 50 for miss rate, 10 for failure count
- Health Grade A–F: A=p95 < 80% interval + miss_rate < 2% + no failures in last 10
- `seconds_since_last_beat` used by watchdog to detect stuck threads
- Accessible via `GET /api/mmm/session/<id>/beat-health`

### 6.24 mmm_margin_guardian.py (Added Feb 20, 2026, ~478 lines)
- `MarginGuardian` class — queries Delta Exchange for actual margin utilization
- 5 tiers: GREEN, YELLOW, ORANGE, RED, CRITICAL (user-configurable thresholds)
- `tier_severity(tier)` → numeric severity (0=GREEN, 4=CRITICAL)
- Triggers wind-down on ORANGE, emergency close on RED, session stop on CRITICAL
- Sends Telegram alerts on tier escalation via `mmm_telegram.py`

### 6.25 mmm_pending_orders.py (Added Feb 18, 2026)
- In-memory `_registry` of in-flight orders per session per side (thread-safe)
- Prevents duplicate adjustment orders when `smart_execute` times out
- On each adjustment: verifies state (filled/open/dead) → decides allow/skip/record
- Orders stale after `_STALE_SECONDS = 900` (15 minutes)
- Filled states: `filled`, `closed`, `completed` — Dead states: `cancelled`, `rejected`, `expired`

### 6.26 mmm_regime.py (Added Feb 20, 2026, ~737 lines)
- `RegimeEngine` class — no I/O; receives data, returns decisions
- Three controls: Volatility Regime Filter, Portfolio Gamma Cap, Trend Detection Guard
- Vol states: `NORMAL`, `ELEVATED`, `HIGH` — Gamma states: `NORMAL`, `SOFT`, `HARD`, `EMERGENCY`
- Trend states: `NORMAL`, `TREND_UP`, `TREND_DOWN`
- Aggregate actions: `ACTION_NORMAL`, `ACTION_WARN`, `ACTION_BLOCK`, `ACTION_EMERGENCY`
- Called by monitor heartbeat between safety checks and trigger evaluation

### 6.27 mmm_telegram.py (Added Feb 20, 2026)
- Sends Telegram notifications for critical margin/safety events
- Uses existing async `TelegramNotifier` infrastructure
- Dedup window: `_DEDUP_WINDOW_SECS = 30` (no repeat alerts within 30s)
- Credentials from `config.loader.get_config().telegram.*` (live_bot_token, live_chat_id)
- Disabled by default — requires valid Telegram bot token + chat ID

### 6.28 mmm_walkthrough.py (Added Feb 16, 2026, ~629 lines)
- `generate_entry_walkthrough(session)` → T=0 entry block in human-readable format
- `generate_heartbeat_walkthrough(session, ce_now, pe_now, ...)` → per-heartbeat log step
- All timestamps in IST (UTC+5:30) via `_to_ist()` / `_to_ist_short()` helpers
- Mirrors format of `MONEY_POWER_CALCULATION_LOGIC.md` Section 16
- Output consumed by `GET /api/mmm/session/<id>/walkthrough` and frontend `MMMAlgoCalculations.js`

### 6.29 mmm_watchdog.py (Added Feb 18, 2026, ~369 lines)
- External supervisor thread watching all active `MMMMonitor` instances
- Detection criteria: (1) thread death, (2) beat timeout (3× interval), (3) status inconsistency
- On detection: emits `mmm_safety` WebSocket event → logs activity → stops dead monitor → restarts fresh monitor
- Records restart in `session['_watchdog_restarts']` for audit
- Does **NOT** restart PAUSED sessions — only RUNNING sessions whose threads died
- Config: `WATCHDOG_POLL_INTERVAL`, `BEAT_TIMEOUT_MULTIPLIER = 3`

---

## 7. FRONTEND COMPONENT DETAILS

### 7.1 MMMDashboard.js (Main Container)
- **Header:** Title, BTC 0DTE badge, health indicator, connection status, New Session + Refresh buttons
- **Left Panel:** Session list with 3 tabs (Active/Idle/History), session cards with controls
- **Right Panel:** Session detail with multiple tabs (Overview/Positions/Triggers/Adjustments/P&L/Safety/Strike Map/Algo Calculations/Consolidated/Greeks & IV/Activity/Regime/Margin/Analytics)
- **Dialogs:** CreateSessionDialog (expiry dropdown, mode: Fresh/Import/Adopt), BothSidesAlert, MMMSettingsDialog
- **State:** Uses `useMMM()` from MMMContext + `useMMMWebSocket(sessionId)` for live data

### 7.2 CreateSessionDialog (inside MMMDashboard.js)
- Fetches expiries from `/api/mmm/expiries` on open → shows as Select dropdown
- Shows BTC spot price from `/api/mmm/spot-price`
- Mode dropdown: Fresh (auto-find), Import (existing positions), or Adopt (from exchange)
- Core Parameters: desired CE/PE premium, initial lots, expiry (dropdown), interval, max loss
- Creates session via `mmmService.createSession(config)`

### 7.3 MMMConfigPanel.js (~866 lines)
- Shown for IDLE/STOPPED sessions in the detail panel
- 3 modes: Auto-Find / Manual Select / Import Existing
- **Auto-Find:** Expiry dropdown + CE/PE desired premium + Find button → StrikePreviewTable → Confirm & Initialize
- **Manual Select:** MMMStrikeSelector component (browse full chain)
- **Import Existing:** CE/PE fields for Strike, Fill Price, Symbol → Import & Initialize
- Entry Summary: total premium calculation before confirm

### 7.4 MMMContext.js (~449 lines)
- `MMMProvider({ children, socket })` — wraps dashboard
- Manages: sessions array, selectedSessionId, loading, error, healthStatus, connectionStatus, paramsInfo, bothSidesAlert
- Fetches sessions on mount, auto-refreshes every 30s
- WebSocket listeners for all 17 `mmm_*` events
- `useMMM()` hook — throws if used outside MMMProvider

### 7.5 MMMActivityFeed.js
- Displays real-time ring buffer of background activity events
- Connects to `GET /api/mmm/activities` + `mmm_activity` WebSocket events
- Shows: order placement, fill waits, repricing, heartbeat execution, adjustments, safety events
- Color-coded by activity type; max 200 entries shown

### 7.6 MMMAdoptPanel.js
- UI for "Adopt" mode: fetch open exchange positions, display in table, user selects which to adopt
- Calls `GET /api/mmm/exchange-positions` → table of open short BTC options
- User selects CE/PE positions → `POST /api/mmm/session/<id>/adopt`
- Shows: symbol, strike, lots, entry price, mark price, unrealized P&L

### 7.7 MMMAlgoCalculations.js
- Displays the algo walkthrough log from `GET /api/mmm/session/<id>/walkthrough`
- Shows per-heartbeat calculation steps in human-readable format (IST timestamps)
- Dashboard "Algo Calculations" tab

### 7.8 MMMAnalyticsPanel.js + MMMAnalyticsSummary.js + MMMAnalyticsTable.js
- Three-part analytics view: summary cards + aggregated stats + historical table
- Capital planning, risk profiling, strategy validation from real historical sessions
- Data via analytics API endpoints (Section 4.10)

### 7.9 MMMMarginGuardianPanel.js
- Displays real-time margin utilization from `GET /api/mmm/session/<id>/margin`
- Tier indicator (GREEN/YELLOW/ORANGE/RED/CRITICAL) with color coding
- Shows: utilization %, position margin, order margin, net equity
- Updates via heartbeat WebSocket

### 7.10 MMMRegimePanel.js
- Displays regime status from `GET /api/mmm/session/<id>/regime`
- Three regime indicators: Volatility, Gamma, Trend
- Aggregate action badge (NORMAL / WARN / BLOCK / EMERGENCY)
- Updates via `mmm_regime` WebSocket events

### 7.11 MMMConsolidatedPositions.js
- Groups scattered individual fills by (side, strike) into consolidated rows
- Shows: Side, Strike, Total Lots, Notional BTC, Weighted Avg Entry, Current Premium, P&L
- Pure frontend aggregation — reuses `buildPositionRows()` from MMMPositionsTable

### 7.12 MMMGreeksPanel.js
- Fetches live Greeks (δ, γ, θ, ν) and IV from `/greeks-iv` endpoint
- Portfolio-weighted totals row (lots × per-contract greek)
- Color-coded: blue δ, purple γ, green θ, orange ν, red IV
- Auto-refreshes every 60s, manual refresh button with timestamp
- Greeks converted from per-1-BTC ticker values to per-lot position Greeks (× LOT_SIZE_BTC × -1 for short)

### 7.13 MMMEducation.js
- Educational tooltips, explanations, and guides embedded in the dashboard
- Explains core concepts (trigger, shift, reversal, etc.) in plain language

### 7.14 Key UI Patterns
- **Socket prop flow:** App.js `connectionManagerRef.current?.socket` → `<MMMProvider socket={socket}>` → MMMContext attaches listeners
- **Lazy loading:** `MMMDashboard` loaded via `React.lazy()` with `Suspense` fallback
- **Error isolation:** `MMMErrorBoundary` wraps everything, prevents MMM crashes from affecting main app
- **Status colors:** IDLE=gray, RUNNING=green, PAUSED=orange, BOTH_SIDES_UP=red, STOPPED=dark gray
- **Data flow:** REST API for initial load + actions, WebSocket for real-time updates

### 7.15 MMMSettingsDialog.js (~448 lines)
- 6 parameter groups: Core, Triggers, Safety, Expiry, Adaptive, Wind-Down
- Rich `PARAM_TOOLTIPS` map (28 entries) with `?` help icons for every parameter
- `DialogContent` with `maxHeight: '75vh'` + `overflowY: 'auto'` for scrollability
- Select input for `wind_down_floor_action` (close_all / stop_adjustments / alert)

### 7.16 MMMStatusBanner.js
- Adaptive tier badge (`⚡ 10-20h`) showing current heartbeat interval range
- Wind-down badge (`🌙 Wind-Down`) when wind-down mode is active
- Regime warning badge when regime action is WARN or BLOCK

---

## 8. DATA FLOW

### 8.1 Session Lifecycle

```
User clicks "+ New Session"
  → CreateSessionDialog opens
  → User selects mode (Fresh/Import/Adopt), expiry, params
  → POST /api/mmm/session/create
  → Session created with status=IDLE
  → If import/adopt mode: sides initialized immediately

User selects session (IDLE) → ConfigPanel shown
  → Auto-Find: preview strikes → confirm → init-fresh
  → Manual: browse chain → select → init-fresh
  → Import: enter data → init-import
  → Adopt: browse exchange positions → confirm → adopt

User clicks Start
  → POST /api/mmm/session/<id>/start
  → MMMMonitor starts background thread
  → MMMWatchdog supervises the monitor thread
  → status = RUNNING
  → Heartbeat loop begins

Running → every interval:
  → Monitor fetches prices (via circuit breaker)
  → Runs close-at-5, wind-down, regime, margin guardian, safety
  → Pending order guard checks in-flight orders
  → Evaluates triggers
  → If adjustment needed → executes, updates state, records walkthrough + activity
  → Emits WebSocket events → frontend updates in real-time
  → Heartbeat health tracker records beat outcome

User can: Pause/Resume/Stop/Change params/Force heartbeat/Reduce position
```

### 8.2 Options Chain Data

MMM uses `OptionsChainService` (existing codebase) to fetch:
- Available expiry dates
- BTC spot price
- Full options chain (strikes, bids, asks, greeks)

This is the same service used by the Options Chain Panel in the main WebUI. MMM lazy-loads it to avoid circular imports.

### 8.3 Adopt Flow

```
User opens Adopt UI (MMMAdoptPanel.js)
  → GET /api/mmm/exchange-positions
  → mmm_adopter.fetch_exchange_btc_options()
  → DeltaClient fetches open short BTC option positions
  → User selects CE/PE positions from table
  → POST /api/mmm/session/<id>/adopt
  → mmm_adopter.build_adopted_session_state()
  → Session initialized; trigger snapshots = current prices
  → Behaves identically to imported session going forward
```

---

## 9. OPERATIONS & DEPLOYMENT

### 9.1 Backend

- **Flask app:** `webui/backend/app.py` on port 5555
- **LaunchAgent:** `com.gridbot.webui` (auto-restart on crash)
- **Restart:** `launchctl stop com.gridbot.webui && sleep 3 && launchctl start com.gridbot.webui`
- **Blueprint registration:** Lines 476-487 in app.py (try/except isolated)
- **Session data:** Persisted to `data/mmm_sessions.db` (SQLite)
  - Legacy `data/mmm_sessions.json` auto-migrated to `.json.migrated` on first run
- **Activity log:** `data/mmm_activity_log.json` (ring buffer, max 200)
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

# Activity log
curl -s http://localhost:5555/api/mmm/activities | python3 -m json.tool

# Exchange positions (for adopt)
curl -s http://localhost:5555/api/mmm/exchange-positions | python3 -m json.tool

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
- Check if Delta Exchange API is reachable
- Verify `mmm_initializer.py` can access `OptionsChainService`

### 10.4 "WebSocket events not arriving"
- Ensure `MMMProvider` receives the socket prop from App.js
- Socket is `connectionManagerRef.current?.socket` (check App.js for exact line)
- Check browser console for socket.io connection errors

### 10.5 "ConfigPanel not showing for IDLE session"
- Dashboard condition checks `fullSession.strategy_status || fullSession.status`
- ConfigPanel checks `sessionStatus` against 'IDLE', 'STOPPED' (case-insensitive)
- Backend uses uppercase status values (IDLE, RUNNING, etc.)

### 10.6 "Session won't start"
- Session must be initialized first (init-fresh, init-import, or adopt)
- Check that CE and PE sides have strike/premium/lots set
- Verify MMMMonitor can start a background thread

### 10.7 "Sessions disappeared after backend restart"
- Sessions are in `data/mmm_sessions.db` (SQLite). Check if file exists and is not corrupted.
- If `data/mmm_sessions.json.migrated` exists, migration already ran (that's correct).
- Running sessions are auto-restored by `init_mmm()` on startup.

### 10.8 "Monitor died and session appears stuck (RUNNING but no heartbeat)"
- MMMWatchdog should auto-restart within `WATCHDOG_POLL_INTERVAL` seconds
- Check `session['_watchdog_restarts']` counter — if > 0, watchdog restarted it
- Check `GET /api/mmm/session/<id>/beat-health` for last beat timestamp and health grade
- If watchdog not running, check `__init__.py` → `init_mmm()` for watchdog start

### 10.9 "Circuit breaker tripped — algo seems paused"
- Check `GET /api/mmm/session/<id>/beat-health` for consecutive failure count
- Circuit breaker OPEN = partial-beat mode (close-at-5 + safety only with cached prices)
- It self-heals after 30s when exchange API recovers
- Check exchange connectivity; circuit breaker never terminates the session

### 10.10 "Margin CRITICAL — session auto-stopped"
- `mmm_margin_guardian.py` stopped session due to CRITICAL margin tier
- Check `GET /api/mmm/exchange/margin` for current utilization
- Reduce exchange positions before restarting
- Tier thresholds are configurable in session params (margin settings)

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

### 11.5 Adding a New Parameter
1. Add to `PARAM_RULES` in `mmm_config.py` (type, default, range, hot_reload flag)
2. Add to `create_session()` in `mmm_state.py` default params dict
3. Add to `MMMSettingsDialog.js` in the appropriate parameter group + tooltip
4. Use `session['params']['your_param']` in the relevant module

### 11.6 Adding a New Activity Type
1. Add to `ACTIVITY_TYPES` dict in `mmm_activity.py`
2. Log events via the activity module's log function from any module
3. The event appears automatically in `MMMActivityFeed.js`

---

## 12. KEY DESIGN DECISIONS

1. **Complete isolation:** MMM has zero imports from/to existing codebase (except App.js integration and OptionsChainService). Failures in MMM never crash the main app.

2. **Per-fill P&L on reversal:** Unlike averaging, each adjustment fill's P&L is computed at its actual strike's current premium. Accurate across multiple strikes and shifts.

3. **Both-sides-up requires human judgment:** The algo pauses and waits. No automatic action in the most dangerous scenario.

4. **Triggers update on BOTH sides:** After every adjustment, both CE and PE snapshots reset. This ensures the "safe zone" expands correctly.

5. **ALL positions always included in loss calculations:** Active positions AND shifted positions at old strikes are ALL evaluated at their live premiums in the standard adjustment formula. No position is ever excluded. The `shift_threshold` only controls where to open NEW positions.

6. **Close-at-5 runs on ALL positions:** Active, adjustment, and shifted — across all strikes. Any position at ≤5 gets closed for profit.

7. **Ceiling rounding + buffer:** Lots calculation always rounds up (ceil) and adds buffer%. Never under-hedged.

8. **Socket prop from App.js:** MMMProvider doesn't create its own socket connection — it receives the app's existing socket, avoiding duplicate connections.

9. **SQLite over JSON:** Session state persisted in SQLite for atomic hot-reload (`params_json` and `data_json` stored separately). Legacy JSON auto-migrated on first run.

10. **Circuit breaker never kills sessions:** API failures trigger graduated partial-beat or full-skip. The session survives and self-heals. Only margin guardian (CRITICAL tier) and safety checks (max loss, near-expiry) terminate sessions.

11. **Watchdog is external:** Runs as a separate supervisor thread, not inside the monitor. Can detect and restart a completely dead monitor thread from the outside.

12. **Adopt = import from exchange:** Adopted sessions are state-equivalent to imported sessions. All runtime modules treat them identically. The only difference is HOW initial state was constructed.

13. **Regime controls are pre-adjustment only:** They block NEW adjustments but do NOT force close existing positions (that is the margin guardian's job). Close-at-5 and wind-down run regardless of regime state.

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

Run: `cd webui/backend && python -m pytest routes/mmm/tests/ -v`

---

## 14. MODULE DEPENDENCY MAP

```
mmm_monitor.py (orchestrator — 3838 lines)
  ├── mmm_trigger.py             evaluate triggers + adaptive interval
  ├── mmm_engine.py              core adjustment math
  │     └── mmm_reversal.py        reversal detection
  ├── mmm_strike_shift.py        freeze/shift strikes
  ├── mmm_close_at_5.py          position buyback
  ├── mmm_safety.py              all safety checks
  ├── mmm_wind_down.py           LIFO wind-down
  ├── mmm_regime.py              vol/gamma/trend controls
  ├── mmm_circuit_breaker.py     wraps exchange API calls
  ├── mmm_pending_orders.py      guards before executor
  ├── mmm_executor.py            order placement
  ├── mmm_walkthrough.py         logs calculation steps
  ├── mmm_activity.py            logs background events
  ├── mmm_websocket.py           emits all 17 events
  ├── mmm_heartbeat_health.py    beat telemetry (pure observability)
  └── mmm_margin_guardian.py     tier-based margin enforcement
        └── mmm_telegram.py        alert notifications

mmm_api.py (REST layer — 3398 lines)
  ├── mmm_storage.py (SQLite)
  ├── mmm_initializer.py
  ├── mmm_executor.py
  ├── mmm_adopter.py
  ├── mmm_analytics_aggregator.py
  ├── mmm_analytics_storage.py
  └── mmm_activity.py

mmm_watchdog.py (supervisor thread, started by __init__.py)
  └── monitors all MMMMonitor instances; restarts on death/timeout/inconsistency

mmm_constants.py ← imported by: engine, adopter, walkthrough, regime
mmm_state.py     ← imported by: api, monitor, initializer
mmm_config.py    ← imported by: api, state, engine
```

---

*This document is the single source of truth for any AI agent working on the MMM algorithm. All file paths, module names, API endpoints, WebSocket events, and state fields above have been verified against the actual codebase as of February 22, 2026. Reference `MONEY_POWER_CALCULATION_LOGIC.md` for the sealed mathematical logic.*
