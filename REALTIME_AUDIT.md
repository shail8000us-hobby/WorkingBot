# REALTIME_AUDIT.md

Date: 2026-04-18  
Scope: MMM realtime update flow audit (backend emitters → websocket contracts → frontend listeners/consumers), with focus on stale UI, delayed updates, missing subscriptions, disconnect handling, and memory-leak risk.  
Constraint honored: **No code changes** (audit only).

---

## 1) What was audited

### Backend
- `webui/backend/routes/mmm/mmm_monitor.py`
- `webui/backend/routes/mmm/mmm_api.py`
- `webui/backend/routes/mmm/mmm_websocket.py`
- `webui/backend/routes/mmm/mmm_exit_all.py`
- `webui/backend/app.py` (options ticker websocket handlers/broadcaster)
- `webui/backend/services/delta_price_websocket.py`
- `webui/backend/services/_ws_subprocess_worker.py`

### Frontend
- `webui/frontend/src/components/mmm/MMMContext.js`
- `webui/frontend/src/components/mmm/hooks/useMMMWebSocket.js`
- `webui/frontend/src/components/mmm/MMMDashboard.js`
- `webui/frontend/src/components/mmm/MMMAdjustmentLog.js`
- `webui/frontend/src/components/mmm/MMMActivityFeed.js`
- `webui/frontend/src/hooks/useVisibilityAwarePolling.js`
- supporting panels where needed (status/pnl/reverse behavior)

---

## 2) Realtime architecture (as implemented)

MMM UI is a **hybrid** model:

1. **Push (WebSocket):**
   - Core stream: `mmm_heartbeat`, `mmm_price_tick`, `mmm_status_change`, `mmm_pnl_update`, etc.
2. **Pull (REST polling):**
   - Session summaries via context polling.
   - Full selected session via dashboard polling.
3. **Merge layer in UI:**
   - Summary list (`MMMContext`) and selected detail (`MMMDashboard` local `fullSession`) are separate stores.

This hybrid model is workable, but several data paths are only partially synchronized, causing stale/detail lag.

---

## 3) Event contract coverage snapshot

Programmatic event-name cross-check (MMM frontend directory only):

- Backend emits: **39** `mmm_*` events
- Frontend listens: **27** `mmm_*` events
- Emitted but not listened in MMM frontend: **12**

### Emitted but not listened (MMM frontend)
- `mmm_atm_shield`
- `mmm_breakeven`
- `mmm_gamma`
- `mmm_manual_injection`
- `mmm_manual_reduce`
- `mmm_reverse_closed`
- `mmm_reverse_disabled`
- `mmm_reverse_entry`
- `mmm_reverse_status`
- `mmm_scale_up`
- `mmm_strike_closed`
- `mmm_trigger_pin_changed`

No listened-only orphan events were found.

---

## 4) Findings (severity-ranked)

## 🔴 Finding 1 — Detail pane uses stale state store (High)

**Symptom:** Right-side detailed panel can lag status/P&L/position state despite live socket traffic.

**Why:**
- `MMMDashboard.js` keeps `fullSession` as separate local state and refreshes mostly by polling (`useVisibilityAwarePolling(fetchFullSession, 15000, 60000, ...)`).
- Only a narrow subset of events force immediate full refresh (`mmm_active_strike_changed`, `mmm_exit_*`).
- Core realtime events (`mmm_status_change`, `mmm_pnl_update`, `mmm_adjustment`, `mmm_manual_*`, etc.) do not trigger immediate `fetchFullSession()`.

**Evidence:**
- `MMMDashboard.js` full-session polling and selective refresh listeners (around lines ~4470–4585).
- `SessionDetail` derives critical display values from `session` (fullSession), not from ws event state:
  - status from `session.strategy_status || session.status` (around ~3051)
  - KPI P&L cards from `session.net_pnl / realized_pnl / unrealized_pnl` (around ~3058+)

**Impact:**
- Status banners/cards can display older values for up to polling interval.
- Operator actions appear delayed in detail tabs.

---

## 🔴 Finding 2 — Manual action events are emitted but not consumed for immediate detail refresh (High)

**Symptom:** Manual reduce/inject/close-strike/pin actions may succeed backend-side, but detail UI waits for poll to reflect changes.

**Why:**
- Backend emits custom events:
  - `mmm_manual_reduce` (`mmm_api.py` ~4490)
  - `mmm_manual_injection` (`mmm_websocket.py` typed emitter; used in API)
  - `mmm_strike_closed` (`mmm_api.py` ~5595)
  - `mmm_trigger_pin_changed` (`mmm_api.py` ~5193, ~5283)
- MMM frontend has **no listeners** for these events.
- Modal success handlers in dashboard generally close dialogs but do not force `fetchFullSession()`.

**Evidence:**
- Emits in backend files above.
- Missing listeners in `MMMContext.js` + `useMMMWebSocket.js` + `MMMDashboard.js` listener blocks.
- `MMMDashboard.js` actions like `handleCloseStrikeConfirm`, `handleAdjustLotsConfirm`, reduce/inject modal flows do not force immediate full-session pull.

**Impact:**
- Post-action stale data windows exactly where operator expects immediate confirmation.

---

## 🔴 Finding 3 — Options ticker path has high-volume broadcast + unbounded client accumulation risk (High, memory/perf)

**Symptom:** Potential memory growth and UI lag from option ticker stream.

**Why (critical path):**
1. Worker subscribes to **all** options orderbooks on open:
   - `_ws_subprocess_worker.py` subscribes `l1_orderbook` for `call_options` + `put_options`.
2. Backend broadcast emits every ticker update globally:
   - `delta_price_websocket.py` `broadcast_ticker()` emits `options_ticker_update` for each symbol update.
3. Frontend listener stores incoming symbol prices without symbol-scope filter/pruning:
   - `useMMMWebSocket.js` `onOptionsTicker` + `setLivePrices` accumulate `livePrices[symbol]` entries.
4. UI “subscribe/unsubscribe options” handlers in `app.py` primarily affect a separate REST-based broadcaster flow and do not appear to constrain the main websocket flood from the all-options worker subscription.

**Evidence:**
- `_ws_subprocess_worker.py` on-open subscriptions.
- `delta_price_websocket.py` `broadcast_ticker` global emit.
- `useMMMWebSocket.js` livePrices buffer/merge logic (no TTL eviction or symbol whitelist check in handler).
- `MMMDashboard.js` emits subscribe/unsubscribe, but flood source remains broad upstream.

**Impact:**
- Frontend memory growth over long sessions.
- Event-loop/render pressure can delay genuinely important realtime updates.

---

## 🟠 Finding 4 — WebSocket disconnect detection is weak/indirect in main MMM UX (Medium-High)

**Symptom:** UI may report healthy connection while socket stream is degraded/disconnected.

**Why:**
- `MMMContext` `connectionStatus` is driven by REST fetch success/fail + browser online/offline, not direct socket connect/disconnect listeners.
- `useMMMWebSocket` has true socket `connected` state, but dashboard warning uses context `connectionStatus`, not `wsData.connected`.

**Evidence:**
- `MMMContext.js`: no `socket.on('connect'/'disconnect')` wiring for `connectionStatus`.
- `useMMMWebSocket.js`: tracks `connected`, but `MMMDashboard.js` does not consume it for the top warning chip.

**Impact:**
- Live stream can silently degrade while UI appears connected, increasing stale-risk during active trading.

---

## 🟠 Finding 5 — Adjustment timeline underuses realtime stream (Medium)

**Symptom:** `Adjustments` tab can lag or miss immediate display for some event types.

**Why:**
- `MMMAdjustmentLog.js` timeline is built from `session.adjustment_history` + ws `shifts` + ws `closeEvents`.
- ws `adjustments` and `reversals` props are passed in but effectively not used in timeline assembly.
- `session.adjustment_history` depends on full-session refresh cadence.

**Evidence:**
- `MMMAdjustmentLog.js` `useMemo` timeline composition block.
- `MMMDashboard.js` passes `adjustments={wsData.adjustments}` and `reversals={wsData.reversals}`, but component merge logic doesn’t include them in final timeline.

**Impact:**
- Operator sees delayed adjustment/reversal chronology in the exact monitoring tab intended for live decisions.

---

## 🟡 Finding 6 — Reverse-mode dedicated events are emitted but unused in panel (Medium)

**Symptom:** Reverse tab relies mostly on heartbeat/session fallback; dedicated reverse events are not consumed.

**Why:**
- Backend emits `mmm_reverse_entry/closed/status/disabled`.
- `MMMReverseModePanel.js` reads `heartbeat?._reverse || session?._reverse`; no reverse-event listeners.

**Impact:**
- Reverse tab updates may lag when `_reverse` is not present in heartbeat payload or when action occurs between fetch cycles.

---

## 🟡 Finding 7 — Dead/unsurfaced telemetry channels (Low-Medium)

Events like `mmm_scale_up`, `mmm_atm_shield`, `mmm_breakeven`, `mmm_gamma` are emitted but not directly subscribed by MMM frontend.

This is not always a bug (may be intentional), but it indicates contract drift: backend is producing signals with no direct UI consumer.

---

## 5) Delay/staleness windows observed

- Selected detail session refresh polling: **15s active / 60s after hidden-tab return path**.
- Session summary polling in context: **30s active / 120s hidden-tab profile**.
- If websocket events are not bridged into `fullSession`, visible staleness windows are bounded by those polling intervals.

---

## 6) What is working well

- Core websocket listener lifecycle cleanup is generally correct (`on`/`off` pairs present).
- 5-second price tick channel exists (`mmm_price_tick`) and is merged into heartbeat premium map for selected session.
- Backend websocket health counters (`get_ws_health`) and stale detection infrastructure exist.
- Exit-all progress events are properly wired end-to-end (`mmm_exit_progress/completed/partial`).

---

## 7) Recommended remediation order (no code applied in this audit)

1. **Unify selected session realtime state path**
   - Either update `fullSession` from key ws events, or force immediate full-session fetch on key events.
2. **Wire manual action events (`mmm_manual_*`, `mmm_strike_closed`, `mmm_trigger_pin_changed`)**
   - Trigger immediate detail refresh.
3. **Fix options ticker fanout + client symbol filtering/eviction**
   - Ensure only subscribed symbols are forwarded to clients and add TTL/LRU eviction in `livePrices` map.
4. **Use actual socket connectivity for connection banner**
   - Drive visible warning from real socket status.
5. **Fix adjustment log merge**
   - Include ws adjustments/reversals directly in timeline.
6. **Decide fate of unsurfaced telemetry events**
   - Either wire them to UI or remove/deprecate to reduce contract drift.

---

## 8) Regression checklist for future validation

- Manual reduce/inject/close-strike updates visible in detail pane within <1s.
- Status transitions (`STARTING→RUNNING`, `RUNNING→PAUSED`, etc.) reflected immediately in right pane.
- Adjustment log shows new adjustment/reversal instantly without waiting for polling.
- Socket disconnect while REST remains healthy still shows realtime warning.
- Long-run memory profile stable during options ticker traffic.
- Reverse-mode tab reflects reverse entry/close/disable transitions in realtime.

---

## 9) Final audit verdict

The realtime pipeline is **partially robust** but currently has a **state synchronization gap** between summary state and detailed state, plus a **high-risk ticker fanout/memory-pressure design**. These two areas are the primary drivers of stale/laggy operator UX and should be treated as the top-priority fixes.
