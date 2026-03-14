# PATIENCE — Scenario Card Engine

## Architecture Blueprint v2.2 FINAL

**Discretionary Position Building Engine for BTC Options**
Delta Exchange India | 30-60 DTE | Multi-Expiry

- **Author:** Shailendra + Claude
- **Date:** March 14, 2026
- **Status:** FINAL — All decisions locked, ready for implementation
- **Rating:** 7.5/10 institutional comparison (practical ceiling for solo operation)

---

## Changes from v2.1 to v2.2

- NEW: MMM handoff for naked/exposed legs (Section 4.4)
- NEW: Portfolio-level Greeks check before card execution (imports position_greeks.py)
- Updated integration map with MMM touchpoints
- Updated risk safeguards with two-engine architecture
- Updated score rationale

---

## 1. Executive summary

Patience is a scenario-card-based position building engine for BTC options on Delta Exchange India. It separates thinking time from execution time: the trader defines conditional position structures (scenario cards) during calm chart analysis, and the engine monitors the market and executes them automatically when conditions are met.

Patience is NOT an algo trading bot. It does not generate signals or make autonomous decisions. It is a disciplined execution layer for discretionary trading ideas.

### Core philosophy

- Human decides WHAT and WHEN (chart reading + market thesis)
- Machine handles HOW (maker_only limit orders, GCD-balanced batches, post_only=true)
- Every card is hand-crafted. The act of writing forces clarity on the trade thesis.
- No dry-run mode. Real money from day one with small lots.

### Two-engine architecture

Patience and MMM form a complementary system:

- **Patience** handles disciplined entry — scenario-based position building with IV gating
- **MMM** handles active risk management — when Patience's financing legs become naked/exposed, they migrate to MMM which manages delta hedging, circuit breakers, and Greeks-based exits
- Patience builds positions; MMM protects them. Neither modifies the other's code.

---

## 2. System architecture

### 2.1 Integration model

Patience registers as a Flask Blueprint in the existing Flask app, sharing the same port and React 18 frontend. Trigger engine runs as a daemon thread (same pattern as AutoLoopService).

| Layer | Technology | Location |
|-------|-----------|----------|
| Frontend | React 18 | webui/frontend/src/components/patience/ (NEW) |
| Backend API | Flask Blueprint | webui/backend/routes/patience/ (NEW) |
| Storage | SQLite | patience.db (NEW) |
| Trigger engine | Daemon thread | webui/backend/services/patience_trigger.py (NEW) |
| Execution loop | Copied from autoloop | webui/backend/services/patience_loop.py (NEW) |
| GCD utility | New shared module | webui/backend/services/gcd_batch.py (NEW) |
| IV percentile | New module | webui/backend/services/patience_iv.py (NEW) |
| Order execution | place_smart_order() | routes/options/order_executor.py (EXISTING, SEALED) |
| BTC price | WebSocket feed | services/delta_price_websocket.py (EXISTING) |
| Portfolio Greeks | position_greeks.py | options_strategy/position_greeks.py (EXISTING) |
| SL/TP | Local monitor | options_strategy/sl_tp_*.py (EXISTING) |
| Max loss | Per-card manual | options_strategy/max_loss_manager.py (EXISTING) |
| Position groups | Auto-group on complete | routes/options/groups_api.py (EXISTING) |
| Guardian | Halt signal | data/guardian_signal.json (EXISTING) |
| Telegram | Alerts only | bot/options/notifications/options_notifier.py (EXISTING) |
| Payoff graph | Existing components | payoffCalculator.js + display components (EXISTING, SEALED) |
| Option chain | Live chain | routes/options/options_control.py (EXISTING) |
| MMM handoff | Naked leg migration | bot/options/ MMM modules (EXISTING) |

### 2.2 Isolation rules

- **STRICT:** Patience cannot modify any existing function. All @sealed functions called, never modified.
- patience_loop.py is a COPY of auto_loop_service.py, modified for maker_only/post_only. Original untouched.
- Own SQLite database. If Patience has a bug, all existing systems continue unaffected.
- Single line added to app.py to register Blueprint. Only change to existing files.
- MMM handoff is a one-way operation: Patience marks legs as "handed off," MMM picks them up through existing position management. No code coupling.

### 2.3 What to build vs. what exists

**Build (NEW):**

- patience_trigger.py — trigger engine daemon
- patience_loop.py — copied autoloop with maker_only
- patience_iv.py — DVOL IV percentile
- gcd_batch.py — GCD lot-sizing utility
- patience_api.py — Flask routes
- patience_models.py — SQLite layer
- PatienceDashboard.jsx — list + tree view
- CardBuilder.jsx — wizard + payoff preview
- CardDetail.jsx — log + positions + payoff
- IVPanel.jsx — percentile chart
- PnLDashboard.jsx — real-time capital summary
- PerformanceHistory.jsx — card win/loss tracking
- TemplateManager.jsx — save/load templates
- ChainTreeView.jsx — visual parent-child tree
- MMM handoff logic — naked leg migration trigger

**Import (EXISTING):**

- place_smart_order() — order execution (SEALED)
- delta_price_websocket.py — BTC price feed
- position_greeks.py — portfolio Greeks for pre-fire check
- sl_tp_manager.py + sl_tp_monitor.py — local SL
- max_loss_manager.py — per-card max loss
- groups_api.py — position grouping
- options_notifier.py — Telegram alerts
- payoffCalculator.js — payoff engine (SEALED)
- OptionsPayoffDiagram.js — payoff display
- Existing positions panel components
- Option chain fetcher endpoints
- MMM risk management modules (delta hedge, circuit breaker, Greeks monitoring)

---

## 3. Scenario card schema

### 3.1 Card identity + trigger

| Field | Type | Description |
|-------|------|-------------|
| card_id | UUID | Auto-generated |
| card_name | String | User label |
| status | Enum | DRAFT/WAITING/ARMED/TRIGGERED/EXECUTING/COMPLETED/PAUSED/CANCELLED |
| parent_card_id | UUID (nullable) | Chaining: arms after parent COMPLETED |
| trigger_price | Float | BTC price level |
| trigger_type | Enum | TOUCH / CROSS_UP / CROSS_DOWN / SUSTAIN |
| trigger_tolerance | Float (default 50) | Points tolerance for TOUCH |
| sustain_minutes | Int (nullable) | Hold time for SUSTAIN |
| iv_percentile_min | Float (nullable) | Min DVOL percentile (credit: set high) |
| iv_percentile_max | Float (nullable) | Max DVOL percentile (debit: set low) |
| iv_lookback_days | Int (default 30) | Percentile lookback window |
| created_at | Datetime | For priority: first created executes first |
| triggered_at | Datetime (nullable) | When conditions met |
| completed_at | Datetime (nullable) | When all legs filled |
| group_id | Text (nullable) | groups_api ID after completion |
| template_id | UUID (nullable) | If created from a template |

### 3.2 Legs

Each card has 1+ legs. Legs can span multiple expiry dates (calendar spreads). Legs execute in GCD-balanced rounds via patience_loop.py.

| Field | Type | Description |
|-------|------|-------------|
| leg_id | UUID | Auto-generated |
| card_id | UUID FK | Parent card |
| leg_order | Int | Execution sequence |
| direction | Enum | BUY / SELL |
| option_type | Enum | CE / PE |
| expiry_date | Date | Leg-level expiry (allows multi-expiry cards) |
| strike | Float | Strike price from live chain |
| lots | Int | Number of lots |
| is_relative_strike | Boolean | If true, resolved from ATM at trigger time |
| relative_offset | Float (nullable) | ATM offset (e.g., +3000) |
| post_only | Boolean (default true) | post_only=true on exchange. Override per leg. |
| order_mode | Enum (default maker_only) | maker_only / ssr / ssr_aggressive |
| stop_loss | Float (nullable) | Optional. LOCAL MONITOR ONLY. Never exchange order. |
| mmm_handoff_eligible | Boolean (default false) | If true, leg can be migrated to MMM when exposed |
| status | Enum | PENDING/EXECUTING/FILLED/FAILED/CANCELLED/HANDED_TO_MMM |
| fill_price | Float (nullable) | Actual fill from order_executor |
| filled_at | Datetime (nullable) | Fill timestamp |

> **CRITICAL: Stop loss philosophy**
>
> Per-leg stop_loss is OPTIONAL and monitored LOCALLY by sl_tp_monitor.py. NO resting stop orders placed on the exchange. Invisible to market makers. Primary risk tool is max_loss_manager per card, set MANUALLY after position verification. This prevents big sharks from hunting visible stop clusters.

### 3.3 Templates

Templates save card structures for reuse across DTE cycles. Everything is saved EXCEPT the trigger price.

| Field | Type | Description |
|-------|------|-------------|
| template_id | UUID | Auto-generated |
| template_name | String | User label (e.g., 'Bull swing layer') |
| trigger_type | Enum | Saved |
| trigger_tolerance | Float | Saved |
| iv_percentile_min | Float (nullable) | Saved |
| iv_percentile_max | Float (nullable) | Saved |
| iv_lookback_days | Int | Saved |
| legs_json | JSON | Leg structure with relative strikes, directions, lots, order modes, mmm_handoff flags |
| created_at | Datetime | Timestamp |

When loading a template, trader only needs to set the trigger price and select expiry. All structure pre-populated.

---

## 4. Execution engine

### 4.1 patience_loop.py (copied from auto_loop_service.py)

A copy of auto_loop_service.py modified to enforce maker_only orders and post_only=true by default. The original auto_loop_service.py remains untouched and SEALED.

**Key differences from original autoloop:**

- order_preference hardcoded to `maker_only` (original supports maker_first / market_only)
- post_only=true on all orders by default (overridable per leg)
- Smart mid-price execution: fetches fresh orderbook, places at (bid+ask)/2
- 10 retries with 30s intervals, re-fetches mid-price each retry
- On failure after 10 retries: card PAUSES (never falls back to market order)

**Why copy instead of UNSEAL:**

- auto_loop_service.start_loop() is SEALED v1.0.0 (March 4, 2026)
- Only accepts `maker_first` or `market_only` — no `maker_only` option
- Signature: `start_loop(self, loop_id, orders, total_rounds, order_preference)`
- Copying ensures zero risk to MMM and existing bot operations

### 4.2 GCD lot-sizing (gcd_batch.py)

New shared utility. GCD calculation exists only in frontend JavaScript (OptionsPanel.js `calculateGCD()` + `getPositionsGCD()`). Backend has no GCD logic. This is a new build.

**Algorithm:**

1. Collect leg lots: [20, 20, 10, 10]
2. Compute GCD: GCD(20,20,10,10) = 10
3. Compute ratios: [2, 2, 1, 1]
4. Total rounds = max(lots)/GCD = 2
5. Per round: execute ratio units for each leg
6. Max unhedged exposure = 1 round of lots

**Why GCD matters on thin markets:**

Delta Exchange India 30 DTE options have thin order books (2-3 lots on the bid). GCD + autoloop drip-feeds 1-lot balanced rounds with maker_only orders that sit and wait. This IS the execution intelligence for illiquid markets — better than aggressive algorithms that would eat through the book and move the market against you.

### 4.3 Execution flow

1. Card triggers → status EXECUTING
2. Guardian signal checked (data/guardian_signal.json)
3. **Portfolio Greeks check via position_greeks.py** — verify total account delta/gamma won't breach safe limits after this card's positions are added
4. Relative strikes resolved from current ATM via option chain
5. GCD schedule computed via gcd_batch.compute_gcd_schedule(legs)
6. patience_loop starts with orders + total_rounds
7. Per round: all legs fire proportionally with maker_only + post_only
8. 10 retries per order, 30s intervals, fresh mid-price each retry
9. On leg fill: fill_price recorded, SL activated via sl_tp_monitor if set
10. On leg fail after retries: card PAUSES, Telegram alert, trader decides
11. On all legs complete: card COMPLETED, positions auto-grouped via groups_api
12. Trader verifies positions, sets max_loss manually, then closes card

### 4.4 MMM handoff for naked/exposed legs

This is the two-engine architecture that raises Patience from 6.5 to 7.5 institutional score.

**The problem:** Patience's financing legs (selling OTM CE/PE to fund debit spreads) are naked positions. If the market moves against them, they need active risk management — delta hedging, dynamic exits, Greeks monitoring. Patience only handles entry, not active position management.

**The solution:** When financing legs become exposed (counterpart spread leg is closed, or market moves significantly), the trader can migrate those legs from Patience to MMM. MMM already has delta hedging, circuit breakers, IV monitoring, and Greeks-based management.

**How it works:**

1. During card creation, trader marks financing legs as `mmm_handoff_eligible = true`
2. After card completes, these legs appear with a "Hand to MMM" action button in the positions panel
3. Trader decides when to hand off (manual decision, not automatic)
4. On handoff: leg status changes to HANDED_TO_MMM, Patience stops tracking it, MMM picks it up through its existing position monitoring
5. Telegram alert: "Patience: Leg [SELL 10 CE 80000] handed to MMM for active management"
6. The leg's P&L is recorded in Patience's performance history at the handoff price

**What MMM does with the handed-off position:**

- Monitors Greeks (delta, gamma, theta) continuously
- Applies circuit breaker logic if position moves against
- Can delta hedge if configured
- Manages exit based on its own strategy rules
- Reports back P&L via existing Telegram alerts

**What Patience does NOT do:**

- Does not auto-handoff. Trader explicitly triggers it.
- Does not modify MMM code. Uses existing MMM position detection.
- Does not track the position after handoff (MMM owns it).

> **Two-engine split:**
> Patience = disciplined entry engine (scenario cards, IV gating, GCD execution)
> MMM = active risk management engine (delta hedging, circuit breakers, Greeks exits)
> Together they cover the full lifecycle: plan → enter → manage → exit

---

## 5. Trigger engine (patience_trigger.py)

### 5.1 Architecture

Daemon thread in Flask process. Same pattern as AutoLoopService singleton. Monitors armed cards against live price + IV conditions.

### 5.2 Monitoring loop

- Runs every 1 second
- Reads BTC price from delta_price_websocket.py (bid/ask midpoint)
- Reads IV percentile from patience_iv.py
- Checks WAITING cards: if parent completed, transition to ARMED
- Evaluates all ARMED cards against trigger conditions
- If all conditions met: transition to TRIGGERED, queue for execution
- Sequential execution: only one card at a time, priority by created_at (earliest first)

### 5.3 Trigger type definitions

| Type | Condition |
|------|-----------|
| TOUCH | abs(current_price - trigger_price) <= trigger_tolerance |
| CROSS_UP | previous_price < trigger_price AND current_price >= trigger_price |
| CROSS_DOWN | previous_price > trigger_price AND current_price <= trigger_price |
| SUSTAIN | Price holds beyond trigger_price for sustain_minutes continuously (resets if reverts) |

### 5.4 IV percentile gate

- Debit spreads: iv_percentile_max = 35 → only buy when IV is cheap (lower 35th percentile)
- Credit spreads: iv_percentile_min = 60 → only sell when IV is expensive (upper 40th)
- If price trigger fires but IV gate blocks: card stays ARMED, Telegram alert sent
- Alert: "Card [name] price hit but IV at 42%, waiting for <= 35%"

### 5.5 Price feed disconnect handling

- If delta_price_websocket returns stale data (>30s old): PAUSE all monitoring
- Telegram alert: "Price feed disconnected. Monitoring paused."
- Auto-resume when feed recovers. No cards cancelled.
- All armed cards remain armed, just not evaluated until feed is live.

### 5.6 Pre-fire checks (TRIGGERED → EXECUTING)

1. Guardian signal (data/guardian_signal.json) — halt = no execution
2. **Portfolio Greeks check** — import position_greeks.py, calculate total account delta/gamma including the card's planned positions. If total delta exceeds configured limit, PAUSE card and alert: "Card [name] would push portfolio delta to X. Paused for review."
3. Price feed freshness — stale > 30s = pause
4. Execution lock — one card at a time, priority by created_at
5. Strike validity — relative strikes resolved and verified in chain
6. Existing guards apply: @rate_limit, @prevent_duplicate, circuit breaker

### 5.7 Telegram alerts (via options_notifier.py)

Alerts only. No Telegram control commands. All control via Web UI.

- ARMED: "Patience: [name] armed. Trigger: BTC >= 73000 (cross up) + IV <= 35%"
- IV BLOCKED: "Patience: [name] price hit but IV at 42%, waiting for <= 35%"
- GREEKS BLOCKED: "Patience: [name] would push delta to +450. Paused for review."
- TRIGGERED: "Patience: [name] TRIGGERED at BTC 73,042. Executing 4 legs, 2 GCD rounds"
- ROUND COMPLETE: "Patience: Round 1/2 done. BUY 10 PE 70000 @ $1,240"
- PAUSED: "ALERT: [name] leg 3 FAILED after 10 retries. Card paused. Check Web UI."
- COMPLETED: "Patience: [name] COMPLETED. 4/4 legs filled. Grouped. Verify in UI."
- MMM HANDOFF: "Patience: Leg [SELL 10 CE 80000] handed to MMM for active management."
- FEED DOWN: "Patience: Price feed disconnected. Monitoring paused."
- FEED RECOVERED: "Patience: Price feed recovered. Monitoring resumed."

---

## 6. IV percentile module (patience_iv.py)

- **Source:** Deribit DVOL index (30-day BTC IV benchmark). Public API, no auth.
- **Polling:** Every 15 minutes. Stores in patience.db dvol_history table.
- **Calculation:** percentile = (count of values < current) / total * 100
- **Bootstrap:** First run backfills from Deribit historical endpoint.
- **Lookback:** Default 30 days, configurable per card.

---

## 7. Card lifecycle

### 7.1 State machine

| State | Description | Transitions |
|-------|-------------|-------------|
| DRAFT | Being built in wizard | ARMED, CANCELLED |
| WAITING | Parent hasn't completed | ARMED (parent completes) |
| ARMED | Trigger engine monitoring | TRIGGERED, CANCELLED |
| TRIGGERED | Conditions met, queued | EXECUTING |
| EXECUTING | patience_loop filling legs | COMPLETED, PAUSED |
| COMPLETED | All filled, verify + set max loss | Closed (removed) |
| PAUSED | Leg failed OR Greeks check blocked | EXECUTING (resume), CANCELLED |
| CANCELLED | Manual cancel | Terminal |

### 7.2 Armed card editing

Armed cards are fully editable: trigger price, trigger type, IV gate, tolerance, AND legs (add/remove/modify). Editing does not require cancel-and-recreate.

### 7.3 Card chaining

- parent_card_id creates dependency. Child stays WAITING until parent COMPLETED.
- Multiple children can share a parent (branching scenario trees).
- Engine does NOT auto-cancel siblings. Trader reviews after each trigger.
- Priority on simultaneous triggers: earliest created_at executes first.

---

## 8. Web UI screens

React 18 components in webui/frontend/src/components/patience/. New tab in existing nav.

### 8.1 Dashboard

- Two view modes: flat list (status filters) + visual chain tree (parent-child relationships). Toggle between views.
- Each card tile: name, trigger level + type, IV gate, leg count, distance from trigger, status color, mmm_handoff indicator
- Live BTC price + current IV percentile prominently displayed
- Master controls: ARM ALL / DISARM ALL / KILL SWITCH (Web UI only, not Telegram)
- From template button for quick card creation

### 8.2 Card builder wizard

1. **Select expiry:** Dropdown from live chain. Multi-expiry supported per card (calendar spreads).
2. **Set trigger:** Price, type, tolerance, sustain duration
3. **Set IV gate:** Min and/or max percentile, shows current for reference
4. **Build legs:** Live chain table, click to add. Direction, lots, order mode, post_only toggle, optional SL (local only), MMM handoff eligible flag. Fixed or relative strikes.
5. **Set chain:** Optional parent card. Load from template option.
6. **Payoff preview:** LIVE projected payoff graph using existing payoff components. Shows max profit, max loss, breakeven, Greeks, R:R, PoP.
7. **Review & arm:** GCD schedule preview, net debit/credit estimate, portfolio Greeks impact estimate, margin estimate. Confirm to arm.

### 8.3 Card detail (after completion)

Three stacked sections:

1. **Execution log:** Per-round, per-leg fill details with timestamps and slippage
2. **Open positions panel:** Existing positions panel embedded, filtered to card's group. All existing functions (SL/TP, max loss, roll, P+, C+, batch bar with GCD/Smart/SSR modes, auto-loop). Plus "Hand to MMM" button on eligible legs.
3. **Payoff graph:** Live payoff of actual filled positions. Toggle between per-card view and combined view across all Patience positions.

### 8.4 P&L summary dashboard

- Real-time updates every few seconds with live mark prices
- Total premium deployed across all active Patience cards
- Current value of all positions
- Unrealized P&L across all Patience positions
- Positions handed to MMM shown separately with "managed by MMM" label

### 8.5 IV percentile panel

- Current DVOL value and percentile number
- Historical chart from dvol_history
- Distribution indicator

### 8.6 Performance history (v1 feature)

- Track every completed card: entry premium, exit value, P&L, duration
- Win rate (profitable cards / total cards)
- Average P&L per card
- P&L by card type (debit spreads vs credit vs mixed)
- Performance over time chart
- Separate tracking for legs handed to MMM (P&L recorded at handoff price)

---

## 9. SQLite schema (patience.db)

### scenario_cards

See Section 3.1 for full field list. Key additions: template_id, group_id.

### card_legs

See Section 3.2 for full field list. Key additions: expiry_date per leg, post_only, order_mode, mmm_handoff_eligible, HANDED_TO_MMM status.

### card_templates

See Section 3.3 for full field list. legs_json stores structure as JSON including mmm_handoff flags.

### dvol_history

| Column | Type |
|--------|------|
| id | INT PK AUTOINCREMENT |
| timestamp | TEXT NOT NULL |
| dvol_value | REAL NOT NULL |

### execution_log

| Column | Type |
|--------|------|
| id | INT PK AUTOINCREMENT |
| card_id | TEXT FK |
| leg_id | TEXT (nullable) |
| event_type | TEXT NOT NULL (TRIGGER_HIT / IV_BLOCKED / GREEKS_BLOCKED / ROUND_START / LEG_FILL / LEG_FAIL / COMPLETE / PAUSE / MMM_HANDOFF) |
| message | TEXT |
| data_json | TEXT (nullable) — JSON with prices, IV, fill details, Greeks snapshot, GCD round |
| created_at | TEXT NOT NULL |

### card_performance

| Column | Type |
|--------|------|
| id | INT PK AUTOINCREMENT |
| card_id | TEXT FK |
| entry_premium | REAL |
| exit_value | REAL |
| pnl | REAL |
| duration_hours | REAL |
| card_type | TEXT |
| legs_handed_to_mmm | INT (count) |
| handoff_pnl | REAL (P&L at handoff price for MMM legs) |
| closed_at | TEXT |

---

## 10. Risk safeguards

### 10.1 Two-engine risk architecture

```
PATIENCE                           MMM
(entry engine)                     (risk engine)
                                   
Scenario cards ──→ GCD execution   Delta hedging
IV gating      ──→ Maker-only     Circuit breakers
Card chaining  ──→ Post-only      Greeks monitoring
                                   Active exits
        │                              ▲
        │    Hand off naked legs       │
        └──────────────────────────────┘
```

### 10.2 Pre-fire checks

1. Guardian signal (data/guardian_signal.json) — halt = no execution
2. **Portfolio Greeks check** — position_greeks.py calculates total delta/gamma. If adding this card's positions would breach limits, PAUSE and alert.
3. Price feed freshness — stale > 30s = pause monitoring
4. Execution lock — one card at a time, created_at priority
5. Strike validity — relative strikes resolved, verified in chain
6. Existing guards: @rate_limit, @prevent_duplicate, circuit breaker

### 10.3 Active position risk

- **Per-card max loss:** Set MANUALLY via max_loss_manager after trader verifies positions. Not auto-set.
- **Per-leg SL:** Optional. LOCAL MONITOR ONLY (sl_tp_monitor polls, fires close order on breach). Never visible on exchange.
- **Position grouping:** Auto-grouped via groups_api on card completion.
- **GCD protection:** Max unhedged exposure = 1 round of lots during execution.
- **MMM handoff:** Naked/financing legs marked as eligible can be migrated to MMM for active management. Manual trigger by trader.
- **Portfolio Greeks monitoring:** position_greeks.py provides ongoing visibility into total account exposure.

### 10.4 Kill switch

- Web UI button only (no Telegram control)
- Cancels all ARMED + WAITING cards instantly
- Does NOT close positions (use existing SL/max-loss/MMM/manual for that)
- Does NOT recall positions from MMM (those are MMM's responsibility now)

---

## 11. File structure (new files)

| File | Purpose |
|------|---------|
| webui/backend/routes/patience/__init__.py | Flask Blueprint |
| webui/backend/routes/patience/patience_api.py | Card CRUD + engine control + IV + templates + performance + MMM handoff |
| webui/backend/routes/patience/patience_models.py | SQLite data access |
| webui/backend/services/patience_trigger.py | Trigger engine daemon with Greeks pre-check |
| webui/backend/services/patience_loop.py | Copied autoloop with maker_only/post_only |
| webui/backend/services/patience_executor.py | Card → GCD → loop handoff |
| webui/backend/services/patience_iv.py | DVOL collector + percentile calc |
| webui/backend/services/gcd_batch.py | GCD utility (shared) |
| webui/frontend/src/components/patience/PatienceDashboard.jsx | List + tree view, live ticker, controls |
| webui/frontend/src/components/patience/CardBuilder.jsx | Wizard + live payoff preview + Greeks impact |
| webui/frontend/src/components/patience/CardDetail.jsx | Log + positions + payoff + MMM handoff button |
| webui/frontend/src/components/patience/IVPanel.jsx | Percentile chart |
| webui/frontend/src/components/patience/PnLDashboard.jsx | Real-time P&L summary |
| webui/frontend/src/components/patience/PerformanceHistory.jsx | Win/loss tracking |
| webui/frontend/src/components/patience/TemplateManager.jsx | Save/load card templates |
| webui/frontend/src/components/patience/ChainTreeView.jsx | Visual parent-child tree |

**Single modification to existing code:**

- app.py: `app.register_blueprint(patience_bp, url_prefix='/api/patience')`
- React router/nav: add Patience tab

---

## 12. Integration map

### Patience → Existing modules

| Patience needs to... | Calls | File |
|----------------------|-------|------|
| Place maker_only order | place_smart_order(mode='maker_only') | order_executor.py (SEALED) |
| Cancel order | cancel_order_with_verification() | order_executor.py (SEALED) |
| Get BTC price | WebSocket subscription | delta_price_websocket.py |
| Get option chain | GET /api/options/ticker/\<symbol\> | options_control.py |
| Check portfolio Greeks | position_greeks.py functions | options_strategy/position_greeks.py |
| Set local SL | sl_tp_manager.set_sl_tp() | sl_tp_manager.py |
| Create group | groups_api.create_group() | groups_api.py |
| Set max loss | max_loss_manager (manual via UI) | max_loss_manager.py |
| Check guardian | Read guardian_signal.json | data/guardian_signal.json |
| Send alert | options_notifier.send_notification() | options_notifier.py |
| Calculate payoff | payoffCalculator.js functions | payoffCalculator.js (SEALED) |
| Display payoff | Existing payoff components | OptionsPayoffDiagram.js etc |
| Show positions | Existing positions panel | OptionsPanel.js components |

### Patience → MMM (handoff only)

| Action | Mechanism |
|--------|-----------|
| Mark leg for handoff | Update leg status to HANDED_TO_MMM in patience.db |
| MMM detects position | MMM's existing position scanning picks up the leg |
| Patience stops tracking | Leg removed from Patience P&L, recorded at handoff price |
| MMM manages actively | Delta hedge, circuit breaker, Greeks exits — all existing |

---

## 13. Implementation phases

### Phase 1: Core engine (3-4 days)

**Goal:** Cards trigger and execute via patience_loop with GCD rounds.

- Project structure + SQLite schema + models
- Card CRUD API with multi-expiry leg support
- gcd_batch.py utility
- patience_loop.py (copy + modify for maker_only/post_only)
- patience_trigger.py daemon (price triggers, feed disconnect handling)
- patience_executor.py (GCD → loop handoff)
- Telegram lifecycle alerts
- **Test:** Create card via API, arm, trigger, verify GCD execution with real 1-lot orders.

### Phase 2: IV gate + Greeks check + templates (2-3 days)

**Goal:** IV percentile gating, portfolio Greeks pre-check, template system.

- patience_iv.py (DVOL collector, bootstrap, percentile calc)
- IV gate in trigger engine
- Portfolio Greeks pre-fire check via position_greeks.py import
- Template save/load API + storage
- **Test:** Card with IV max 35 blocks when IV high, fires when low. Greeks check blocks when portfolio delta too high. Save and reload template.

### Phase 3: Web UI (4-5 days)

**Goal:** Complete card builder with payoff preview + dashboard.

- PatienceDashboard (list + tree toggle, live ticker, controls)
- CardBuilder wizard (chain, live chain, payoff preview, Greeks impact preview, GCD preview, templates, MMM handoff flag per leg)
- CardDetail (execution log + positions panel + payoff graph with per-card/combined toggle + MMM handoff button)
- IVPanel (percentile chart)
- PnLDashboard (real-time capital summary, MMM-handed positions shown separately)
- Armed card editing
- Navigation tab in existing app
- **Test:** Full cycle: build card from template, arm, execute, verify, set max loss, hand financing leg to MMM, close.

### Phase 4: Hardening + history (2-3 days)

**Goal:** Production reliability + performance tracking.

- State recovery on restart
- Execution lock (one card at a time, created_at priority)
- Auto-grouping via groups_api on completion
- SL auto-activation via sl_tp_monitor
- PerformanceHistory (card tracking, win rate, P&L, MMM handoff tracking)
- Kill switch
- Edge case testing: simultaneous triggers, chain dependencies, feed disconnect, multi-expiry, Greeks blocking, MMM handoff
- **Test:** Full 30-day cycle simulation with 5 chained cards across BTC swings.

**Total estimated build time: 11-15 days** (per trader assessment of own build speed)

---

## 14. Example scenario walkthrough

### Setup: BTC at 70,000 | IV percentile: 28 | 30 DTE

**Card 1: Initial structure (from template "Double debit")**

- Trigger: Manual | IV max 40 | maker_only + post_only
- Leg 1: BUY 20 CE 75000 (30 DTE)
- Leg 2: SELL 20 CE 80000 (30 DTE)
- Leg 3: BUY 20 PE 65000 (30 DTE)
- Leg 4: SELL 20 PE 60000 (30 DTE)
- GCD(20,20,20,20)=20. Ratio 1:1:1:1. 20 rounds. Max unhedged = 1 lot.

**Card 2: Bullish swing (chains to Card 1)**

- Trigger: CROSS_UP 72000 | IV max 40
- Leg 1: BUY 20 PE 70000 (30 DTE)
- Leg 2: SELL 20 PE 67000 (30 DTE)
- Leg 3: SELL 10 CE 80000 (30 DTE, financing, **mmm_handoff_eligible=true**, optional SL local only)
- GCD(20,20,10)=10. Ratio 2:2:1. 10 rounds. Financing leg proportional.

**Card 3: Calendar spread (chains to Card 1)**

- Trigger: SUSTAIN above 73000 for 60 min | IV min 50
- Leg 1: BUY 10 PE 72000 (30 DTE)
- Leg 2: SELL 10 PE 72000 (60 DTE) — different expiry, calendar spread
- Multi-expiry card. Each leg specifies its own expiry_date.

**Card 4: Reversal (chains to Card 1, independent of 2/3)**

- Trigger: CROSS_DOWN 68000 | IV max 40
- Leg 1: BUY 20 CE 69000 (30 DTE)
- Leg 2: SELL 20 CE 73000 (30 DTE)
- Leg 3: SELL 10 PE 62000 (30 DTE, financing, **mmm_handoff_eligible=true**, SL local only)

### After execution

1. Positions auto-grouped per card via groups_api
2. Trader verifies fills in Card Detail: execution log → positions panel → payoff graph
3. Trader sets max_loss manually via max_loss_manager in the positions panel
4. Payoff graph: toggle between Card 1 only, Card 2 only, or ALL combined
5. P&L dashboard shows real-time premium deployed + unrealized P&L
6. If Card 2's financing leg (SELL 10 CE 80000) becomes exposed → trader clicks "Hand to MMM" → MMM manages it actively
7. Card saved to performance history after closing

---

## 15. Open questions (for coding AI)

These are implementation-level questions for the coding AI to resolve by inspecting the codebase:

| Question | Action |
|----------|--------|
| Which payoff component to embed? | Inspect payoffCalculator.js + 6 display components, pick best fit |
| delta_price_websocket data format | Inspect how other consumers read the price feed |
| React navigation structure | Inspect App.js / router to add Patience tab |
| Frontend polling vs websocket | Match existing pattern (how AutoLoopBanner gets status) |
| guardian_signal.json format | Inspect file to read halt flag |
| groups_api.create_group() signature | Inspect to auto-group card legs |
| Flask vs FastAPI for some endpoints | Inspect app.py to confirm all routes are Flask |
| options_notifier.py interface | Inspect send function signature |
| position_greeks.py interface | Inspect to call portfolio-level Greeks calculation |
| MMM position detection mechanism | Inspect how MMM discovers new positions to manage |
| Autoloop execution chain | Inspect auto_loop_service → batch_add → order_executor call path for patience_loop.py copy |

---

## 16. Success criteria

1. Card creation with live chain + payoff preview in under 2 minutes
2. All 4 trigger types fire reliably
3. IV percentile gate blocks/allows correctly
4. Portfolio Greeks pre-check blocks when total delta/gamma too high
5. GCD-balanced rounds: max unhedged = 1 round of lots
6. maker_only + post_only=true on all orders (per-leg override available)
7. Card chaining: children auto-arm on parent completion
8. Failed legs pause card + Telegram alert within 5 seconds
9. Completed cards: positions panel + payoff graph (per-card/combined toggle)
10. MMM handoff works: financing leg migrated, Patience stops tracking, MMM picks up
11. Templates: save and reload card structures across cycles
12. P&L dashboard: real-time premium + unrealized P&L across all cards
13. Performance history: win rate + P&L from day one
14. Armed card editing (trigger, IV, legs) without cancel-recreate
15. Price feed disconnect: pause + alert + auto-resume
16. Kill switch cancels all armed cards within 1 second
17. State recovery from SQLite on restart
18. Zero impact on existing systems (all @sealed functions untouched)

---

## 17. Institutional comparison score: 7.5/10

| Category | Score | Notes |
|----------|-------|-------|
| Concept & philosophy | 9/10 | Identical to institutional scenario engines |
| Execution architecture | 7/10 | GCD + autoloop is the right answer for thin BTC options markets |
| Risk management | 7/10 | Portfolio Greeks check + MMM handoff for naked legs |
| IV gating | 8/10 | Better than most retail, comparable to small institutional |
| Post-entry management | 7/10 | MMM handles exposed legs actively, not left manual |
| Technology | 7/10 | Solid for solo. Mac Mini is the weak point. |
| Monitoring | 6/10 | Single-person dependent |
| Market microstructure | 6/10 | GCD IS the liquidity solution for thin books |

**Gap to 9/10:** Infrastructure redundancy (servers, failover) and multi-person monitoring. Both irrelevant for a solo trader. 7.5 is the practical ceiling for a one-person operation.

---

*PATIENCE v2.2 FINAL — All decisions locked. Ready for implementation.*
*No code until this document is approved by Shailendra.*
