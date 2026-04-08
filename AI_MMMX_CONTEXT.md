# AI_MMMX_CONTEXT — Operational Context for MMMX (Monthly BTC Options)

> **Purpose:** Comprehensive, token-efficient context for understanding MMMX architecture, strategy, and implementation requirements.  
> **Last Updated:** 2026-04-07  
> **Status:** Final specification v10.0 — all Q1–Q50 resolved

---

## SECTION 1: STRATEGY CORE

### Philosophy
MMMX is an intelligent capital deployment system for **selling monthly BTC options (20–45 DTE)**. Unlike naive premium sellers that deploy all capital at entry and pray for stillness, MMMX:
- **Deploys in 10% tranches** — only when market confirms opportunity (move + IV)
- **Protects via ATM Shield** — repositions any position before it approaches ATM
- **Hard stop is absolute** — scales dynamically with premium collected
- **Monitors dual-stream** — 1-hour heartbeat + real-time flash-crash detection
- **Positions survive directional moves** — old tranches go deeper OTM and collect theta

### Core Objectives (Q26–Q28)
1. **Q26: Theta capture through gradual capital commitment** — not directional betting
2. **Q27: Stay OTM. Never fight the market** — reposition before threatened
3. **Q28: Protection ALWAYS wins** — hard stop, shields, and delta gates outrank deployment

### Non-Negotiable Asymmetry Rule (G28)
When BTC falls 6%, **CE goes deep OTM (profitable) while PE approaches ATM (threatened)**. High IV after a move is an OPPORTUNITY to redeploy, not a reason to close all. Correct response: book CE profit, roll PE farther OTM, collect elevated premium.

---

## SECTION 2: CAPITAL STRUCTURE

```
Per Side (CE or PE):
├── DEPLOYMENT BUDGET:     100 lots (10 tranches × 10 lots)
├── ATM SHIELD RESERVE:    30 lots  (separate protection pool)
└── TOTAL MAX EXPOSURE:    130 lots

Tranche deployment: 10% sequential, automatic on move/IV confirmation
Hard stop: 2.0× total_premium_collected (default, hot-reloadable min 1.0)
Entry gates: DTE 20–45, IV Rank ≥50, margin <80%, liquidity check
```

---

## SECTION 3: SESSION LIFECYCLE STATES

```
DRAFT (setup) → GATES_PASSED (ready) → RUNNING (live) ↔ PAUSED → COMPLETE/ERROR

Key rules:
- Restart always lands PAUSED (never auto-resume)
- PAUSED → RUNNING requires reconciliation
- Hard stop triggers COMPLETE (non-overridable)
- Status field in session dict is authoritative
```

---

## SECTION 4: CORE PROTECTION MECHANISMS

### Hard Stop (Net Session-Level Ceiling)
- **Formula:** `hard_stop_usd = hard_stop_multiplier × total_premium_collected`
- **Scope:** ALL positions (all tranches + all recovery lots)
- **Check:** Every heartbeat FIRST, before all other logic
- **Action:** `close_all_immediately()` on breach → COMPLETE status
- **Non-overridable:** Once RUNNING, hard stop is law

### ATM Shield (Per-Tranche Position Defense)
- **Trigger:** Any position's OTM buffer < 5% (hot-reloadable)
- **6-step sequence:** Calculate loss → buyback (10 reprice attempts) → sell new strike → calculate recovery lots → sell recovery → close old position
- **Recovery model:** 30% loss on CE recovery lots, 70% on PE recovery lots
- **Constraint:** Max 3 shifts per position (default, hot-reloadable)
- **Reserve:** Separate 30-lot pool per side (not deployment budget)
- **Shield fires BEFORE deployment** — protection > offense priority

### Deployment Queue (Capture Large Moves)
- **Problem:** 6% move in one beat → only 1 tranche deploys (one-per-beat rule) → wastes confirmation
- **Solution:** Populate queue when large move detected, deploy one per subsequent beat
- **Retracement clear:** If market retraces > 0.5% against queue direction → clear queue, save capital
- **Session fields:** `deployment_eligible_tranches[]`, `deployment_queue_triggered_spot`, `deployment_queue_direction`

### Delta Gates & CB (Circuit Breaker)
- **Portfolio delta threshold:** 0.15 (aggregate across all positions)
- **Drift threshold:** 0.35 (single position trigger)
- **Near-ITM:** 0.55 (reduce 50%)
- **Emergency delta:** 0.70 (hard stop fires)
- **CB_NEAR_ITM:** Real-time listener detects delta ≥ 0.55 → reduce immediately (don't wait for heartbeat)
- **CB prevents:** Gamma ramp surprise in final weeks

---

## SECTION 5: DEPLOYMENT MECHANICS

### Tranche 1 (Manual Trigger)
1. Operator clicks "Scan strikes" → system shows nearest strikes at otm_distance_pct
2. Operator reviews premiums, deltas, bid depth
3. Operator clicks "Deploy Tranche 1" → sells 10 lots CE + 10 lots PE
4. Session → RUNNING, monitor + listener threads start

### Tranches 2–10 (Automatic, Heartbeat-Triggered Every 1 Hour)
```
DEPLOY IF:
  (spot_moved >= tranche_deploy_move_pct from last_deployment_spot)
   OR
  (IV_rank_delta >= tranche_deploy_iv_delta)
  AND tranches_remaining > 0
  AND margin < 80%
  AND ATM Shield did NOT fire this beat
  AND whipsaw_score < 4 (cooldown blocks all)

Default thresholds (hot-reloadable):
  - tranche_deploy_move_pct = 2%
  - tranche_deploy_iv_delta = 10 points
  - otm_distance_pct = 15%

Whipsaw adjustments:
  - Score 0–1: NORMAL (base thresholds)
  - Score 2: CAUTION (widen 50%, move 2% → 3%)
  - Score 3: RESTRICT (widen 100%, tranche size 5 lots)
  - Score 4: COOLDOWN (skip deployments for 1 hour)
  - Decay: -2 per hour, if not shield-fired
```

### Strike Selection (Live API)
- **Do NOT hardcode step sizes** — Delta adjusts strikes by price level and DTE
- **Query live:** `GET /v2/tickers?contract_types=options&underlying=BTC&expiry=DD-MM-YYYY`
- **Snap to nearest:** `nearest_strike = min(available, key=|s - raw_target|)`
- **Symbol format:** `C-BTC-{strike}-{DDMMYY}` or `P-BTC-{strike}-{DDMMYY}`

### After Deployment (State Update)
```python
last_deployment_spot = current_spot  # MANDATORY for next move calc
last_deployment_iv_rank = current_iv_rank
total_premium_collected += new_premium
hard_stop_usd = hard_stop_multiplier × total_premium_collected
tranches_deployed += 1
tranches_remaining -= 1
```

---

## SECTION 6: TRANCHE & POSITION MODEL

### Tranche Structure
```python
tranche = {
    'tranche_id': 1..10,              # deployment tranches
    'parent_tranche_id': None,        # only for recovery tranches
    'type': 'deployment' | 'recovery',
    'deployed_at': '<ISO UTC>',
    'entry_spot': 67500.0,
    'entry_dvol': 52.0,
    'entry_iv_rank': 65,
    'ce': {
        '_pos_id': 'hex8',            # atomic removal key
        'symbol': 'C-BTC-77625-280326',
        'strike': 77625,
        'lots': 10,
        'entry_premium': 140.0,
        'entry_delta': 0.20,
        'current_premium': None,
        'current_delta': None,
        'unrealized_pnl': 0.0,
        'realized_pnl': 0.0,
        'fees_paid': 0.0,
        'status': 'ACTIVE',           # ACTIVE | CLOSED | REPOSITIONED | REDUCED
        'shift_count': 0,             # ATM shield shifts on this position
        'shield_history': [],         # [{old_strike, new_strike, loss, timestamp}]
        '_being_closed': False,       # In-flight guard (180s TTL)
    },
    'pe': { ... },                    # same as ce
    'premium_collected': 275.0,
    'status': 'ACTIVE' | 'PARTIAL' | 'CLOSED',
}
```

### Recovery Tranches (ATM Shield Output)
- IDs: `"{parent_id}{A|B|C}"` — e.g., `"2A"`, `"2B"`, `"2C"`
- Live in session['tranches'] as separate entries with parent_tranche_id pointer
- Used ONLY for loss offset from ATM shield execution

### Position ID (_pos_id)
- 8-char hex, generated once at creation, never reused
- Enables atomic removal without index bugs

---

## SECTION 7: HEDGING (G43 — Scheduled Post-Deploy)

### Hedge Timing
- Deployed 15 minutes after parent tranche deployment
- Hedge on both CE and PE (bought calls/puts, **LONG units**, separate from short positions)
- Distance: `hedge_distance_pct` (default 20% OTM from entry spot)

### Hedge Schema
```python
hedge = {
    'hedge_id': 'H-Tr5',
    'parent_tranche_id': 5,
    'deployed_at': '...',             # parent tranche deploy time
    'hedge_executed_at': '...',       # 15 min later
    'ce': {'strike': 84000, 'lots': 10, 'position_type': 'LONG', ...},
    'pe': {'strike': 51000, 'lots': 10, 'position_type': 'LONG', ...},
    'hedge_premium_paid': 85.0,
    'max_loss_if_spreads_hit': 400.0,
    'status': 'ACTIVE' | 'DISPLACED' | 'ORPHANED' | 'CLOSED',
}
```

### Reserve Capacity
- Hedge capacity: 50 lots total
- Can hedge up to 5 tranches (5 × 10 lots = 50)
- If capacity exhausted: hedging disabled for remaining tranches

---

## SECTION 8: BACKEND MODULE MAP (27 Files)

| Module | Responsibility | Scope |
|---|---|---|
| `mmmx_constants.py` | `LOT_SIZE_BTC=0.001`, enums, shared constants | sync |
| `mmmx_state.py` | Session schema, defaults, init helpers | sync |
| `mmmx_config.py` | Param validation, `close_at_dte >= 7` enforce, hot-reload allowlist | sync |
| `mmmx_storage.py` | SQLite `mmmx_sessions.db`, CRUD, generation writes | sync |
| `mmmx_activity.py` | Ring buffer activity log | sync |
| `mmmx_audit_log.py` | Append-only JSONL trade/order journal | sync |
| `mmmx_param_audit.py` | Per-change audit log of hot-reload updates | sync |
| `mmmx_websocket.py` | FireSocket `mmmx_*` event emitters | sync |
| `mmmx_telegram.py` | Alert dispatcher with dedup + TTL | async |
| `mmmx_engine.py` | P&L, portfolio delta, IV change, lot imbalance, BS fair value, fees | sync |
| `mmmx_trigger.py` | 10-trigger priority evaluator | sync |
| `mmmx_safety.py` | DTE sanity, generation guard, P&L completeness | sync |
| `mmmx_executor.py` | Smart execution (reprice, partial-fill, dedup, margin checks) | async |
| `mmmx_atm_shield.py` | OTM monitoring, 6-step shield, reserve cascade | async |
| `mmmx_hedger.py` | Scheduled hedge buys, displacement tracking, P&L updates | async |
| `mmmx_whipsaw.py` | Score accumulation, decay, cooldown gate | sync |
| `mmmx_profit_booking.py` | Per-tranche close requests | async |
| `mmmx_circuit_breaker.py` | 3-state API fault isolation (CLOSED/HALF_OPEN/OPEN) | sync |
| `mmmx_premium_listener.py` | WebSocket real-time listener + CB Tier-0 triggers | async |
| `mmmx_monitor.py` | Heartbeat thread, 3-layer stale guard, beat orchestration | async + thread |
| `mmmx_watchdog.py` | Monitor/listener supervisor, detects dead threads | sync (thread) |
| `mmmx_initializer.py` | Entry gates, strike scanning, liquidity validation, Tr1 deploy | async |
| `mmmx_reconciler.py` | Partial-fill tracking, exchange-vs-DB diff, reconcile_with_exchange | async |
| `mmmx_margin_guardian.py` | Adapter over MMM's `MarginGuardian` for MMMX | sync |
| `mmmx_api.py` | Flask Blueprint `/api/mmmx/*` routes | sync (async via executor) |
| `__init__.py` | Blueprint registration, startup session restore | sync |
| `tests/` | Unit + integration suites | — |

### Key Design Principle
- **No MMM runtime imports** — read-only adapters only (`OptionsChainService`, `patience_iv.py`, `MarginGuardian`)
- **Isolated storage** — separate `mmmx_sessions.db`, separate monitor registry
- **Generation tracking** — monotonic counter DB-persisted to detect stale monitors (prevents P0 incident)

---

## SECTION 9: EXECUTOR CONTRACT (Order Lifecycle)

### Smart Execute Flow
```
1. Build order intent (symbol, side, size)
2. Compute deterministic client_order_id = hash(session_id|tranche_id|side|action|minute)
3. Dedup check: fetch open orders by client_order_id → if exists, return
4. Margin preflight: if util > 80% AND SELL → BLOCKED
5. Set _being_closed guard on position
6. Generation re-verify: if stale → ABORT
7. Place limit order at mid-price
8. Reprice loop (max_reprice_attempts, default 4; shield uses 10):
   - Wait 30s (configurable FILL_TIMEOUT)
   - If filled → goto 10
   - Margin recheck: if util ≥ 95% → abort; if util ≥ 85% → break → market fallback
   - Cancel, refetch bid/ask, reprice (mid → bid/ask aggression)
9. Market fallback (IOC, emergency_execute)
10. Record fill: fees, P&L, audit log
11. Clear _being_closed
12. Return ExecutionResult
```

### Hard-Stop Execution (Market on Danger, Limit on Safe)
```python
# When close_all_immediately fires:
for position in all_positions:
    if position.side == 'SHORT':
        execute(MARKET, side='BUY')  # Danger side — stop bleed immediately
    else:  # LONG hedges
        execute(LIMIT, bid_price)    # Safe side — accept patient fill
```

---

## SECTION 10: GENERATION GUARD (Stale Monitor Prevention — G5)

**Three-layer guard to prevent P0 incident (stale monitor placing orders):**

1. **`start_session_monitor()` — `thread.join(15s)`:** After old monitor stops, waits 15s for thread exit before spawning new one (prevents stale instance overlap)

2. **`_run_loop` primary guard:** At top of loop cycle, after fresh_session load, checks `stored_gen > self._my_generation`. If stale: set `_running = False`, fire Telegram + emit_safety(), break

3. **Guardian G5 in `_heartbeat()`:** After `pre_beat_snapshot()`, calls `_guardian.check_generation_integrity()`. If stale: call `handle_stale_monitor()` (STOP not pause), return

**Critical notes:**
- `emit_safety()` is regular `def` (sync), call directly (never `run_until_complete`)
- `handle_stale_monitor()` uses STOP (`_running=False`), not pause
- `_save_session()` returns bool; callers must check return value
- Monitor restart always increments generation counter BEFORE thread spawn

---

## SECTION 11: WHIPSAW GUARD (G44 — Oscillation Control)

```
Shield fires → OSC score +1
Score decays -2 per 1 hour
Deployment triggers adjusted by score:

Score 0–1: NORMAL (base 2% move, 10-lot tranche)
Score 2: CAUTION (3% move, 10-lot)
Score 3: RESTRICT (4% move, 5-lot)
Score 4: COOLDOWN (skip all deployments for 1h)

After cooldown expires, score resets to 2 (grace period)
```

---

## SECTION 12: MARGIN CHECKS (G6, G40)

### Executor Constraints
- **Preflight (SELL only):** if utilization > 80% → BLOCKED
- **Reprice loop:** margin recheck every 30s
  - if util ≥ 95% → abort attempt chain
  - if util ≥ 85% → break limit loop → market fallback
- **Continuous recheck (G40):** During execution, recheck margin before every reprice

### Cross-Account Awareness
- MMMX and MMM share one exchange margin account
- MMMX never reads/writes MMM session state, but margin guardian is shared
- New margin adapter: `mmmx_margin_guardian.py` wraps MMM's MarginGuardian

---

## SECTION 13: PREMIUM LISTENER (Real-Time CB Tier-0 — G27)

### Purpose
Detect intraday flash crashes between 1-hour heartbeats. A 7% BTC move in 90 seconds would be invisible unless WebSocket listens.

### Tier-0 Circuit Breakers (Real-Time)
```
CB_NEAR_ITM: any active position delta ≥ 0.55 → reduce by 50% immediately
CB_IV_SPIKE: DVOL spike > iv_catastrophe_pct + any delta ≥ 0.70 → close_all
CB_MARGIN: utilization ≥ 95% + any delta ≥ 0.55 → reduce top-risk positions
```

### Listener Watchdog
- If WebSocket stale > threshold (default 5 min) → wake heartbeat + force reconcile attempt

---

## SECTION 14: REVERSE MODE ISOLATION (DO NOT BREAK)

MMMX has **NO reverse mode**. Reverse mode is MMM-only (implemented 2026-03-26).

### Why Isolation Matters
- MMMX positions are on standard exchange margin account
- MMMX never touches `session['_reverse']` or reverse-related logic
- All MMMX code is blind to reverse state

---

## SECTION 15: TIMESTAMPS & DTE (UTC-Only Mandate)

```python
# Always use timezone-aware
from datetime import datetime, timezone

created_at = datetime.now(timezone.utc)  # ISO 8601 with +00:00
dte_remaining = (expiry_datetime - datetime.now(timezone.utc)).total_seconds() / 86400

# Never use naive utcnow()
# dumb: datetime.utcnow()  ← BANNED
```

### DTE Safety Rule
- **Hard minimum:** `close_at_dte >= 7` days (enforced in config)
- **Session auto-close:** when DTE ≤ close_at_dte → trigger COMPLETE
- **Gamma ramp:** final week gamma explosion controlled by mandatory exit

---

## SECTION 16: PARAMETER HOT-RELOAD ALLOWLIST

These can be reloaded while session RUNNING (all others locked):

```
Deployment:   otm_distance_pct, tranche_deploy_move_pct, tranche_deploy_iv_delta, 
              hard_stop_multiplier, adjustment_interval_hours

Protection:   delta_drift_threshold, near_itm_delta, emergency_delta,
              atm_protect_threshold, atm_shield_max_shifts

IV:           iv_spike_threshold_pct, iv_catastrophe_pct

Hedging:      hedge_distance_pct, hedge_execution_delay_minutes

Exit:         close_at_dte (min 7), profit_target_pct, profit_target_enabled

Whipsaw:      whipsaw_window_mins, whipsaw_spot_move_pct, 
              whipsaw_caution_score, whipsaw_restrict_score, whipsaw_cooldown_score
```

---

## SECTION 17: FAILURE MODES & ESCALATION

### Naked Position (ATM Shield Sell Failure)
- Buyback succeeds → sell new position fails
- **Action:** Session PAUSED, naked alert to operator + Telegram CRITICAL
- **Watchdog escalation:** no retry for 30 min, then every 2 hours
- **Resolution:** operator manual reposition or session STOP

### Partial Fill
- Residual tracked in `pending_residuals` table
- Retried at beat start with smart_execute on remaining size
- Escalates to emergency_execute if blocked > threshold
- Residual never expires — tracked until filled or position gone

### API Unavailable (Circuit Breaker OPEN)
- Monitor pauses session, listener stays active (CB Tier-0 still runs)
- Retry API each beat
- WebSocket events still process

### DTE Breach
- Session auto-closes when remaining DTE ≤ close_at_dte
- Immovable rule — no hot-reload override

---

## SECTION 18: FRONTEND OVERVIEW (40+ Components)

### Key Panels
| Panel | Purpose |
|---|---|
| `MMMXHardStopMeter` | Large gauge: current P&L vs -hard_stop_usd with color bands |
| `MMMXTranchesTable` | Main table: all tranches, deployment + recovery, OTM%, shield history |
| `MMMXDeploymentQueuePanel` | Queue state, trigger spot, retracement distance, deploy eligibility |
| `MMMXHedgeLedger` | All hedges with status (ACTIVE/DISPLACED/ORPHANED), max loss |
| `MMMXWhipsawPanel` | Score, level badge, decay/cooldown timers, shield event history |
| `MMMXSafetyPanel` | 4 cards: hard stop, ATM shield, hedging, whipsaw status |
| `MMMXNakedAlert` | Full-screen red overlay on naked position detection |
| `MMMXReconcilePanel` | DB vs exchange diff on restart, operator disposition per divergence |
| `MMMXStatusBanner` | Top bar: RUNNING/PAUSED, Tr x/10, reserve remaining, hard stop headroom % |
| `MMMXStrikeScanner` | Live chain scan for Tr1 manual deploy, shows premiums + bid depth |

### WebSocket Events (27 total)
All prefixed `mmmx_`:
```
Lifecycle: heartbeat, status_change, session_created, session_stopped
Risk: pnl_update, price_tick, margin_warning
Protection: shield_fire, shield_abort, hard_stop, reserve_update, whipsaw_level
Execution: deployment, deployment_queue, tranche_closed, profit_booked
Hedging: hedge_scheduled, hedge_executed, hedge_displaced
Config: params_updated, trigger_fired, cb_tier0
Incidents: naked_detected, naked_resolved, reconcile_needed, api_failure, api_recovered, watchdog_restart
Activity: activity (ring buffer)
```

### ~70 REST Endpoints
Primary groups:
- Session lifecycle (create, check gates, deploy, pause/resume/stop)
- Parameters (get, hot-reload, history)
- Tranches & positions (list, detail, consolidated view)
- Hedges (list, detail, close)
- Deployment queue (state, triggers, preview)
- ATM Shield (status, history, candidates)
- Profit booking (queue, cancel)
- P&L / Greeks / Risk (full data)
- Reconciliation (run, confirm)
- Health & diagnostics (monitor/listener health, formula values)

---

## SECTION 19: MISSING SPECS (Flagged Blockers)

| Item | Status | Note |
|---|---|---|
| Order lifecycle fine-grain events | BLOCKED | `mmmx_*_progress` events not defined; execution pipeline uncertain state undefined |
| Kill switch command schema | BLOCKED | Command ack/progress events not in `mmmx_websocket.py` |
| Trigger evaluation payload | BLOCKED | Full trigger ladder snapshot not defined; winner explanation only |
| Beat snapshot versioning | MISSING | `_schema_version` defined on session, not per-beat snapshot |
| Multi-operator concurrency | NOT DEFINED | No role/permission model or command arbitration rules |
| Incident acknowledgement SLA | NOT DEFINED | Escalation timings policy undefined |
| Alert modality | NOT DEFINED | Visual-only vs audible/push policy undefined |

---

## SECTION 20: CRITICAL DEPENDENCIES & SHARED MODULES

### Read-Only Shared Modules (NEVER modify)
- `webui/backend/options_chain/chain_service.py` — OptionsChainService, strike ladder fetch
- `webui/backend/services/patience_iv.py` — DVOL history, IV rank computation
- `bot/api/async_delta_client.py` — REST API client (fresh per event loop)
- `bot/api/unified_api_client.py` — Order placement (lazy-load per executor)
- `bot/volatility/iv_rv_tracker.py` — Historical IV data if needed

### Isolation Rules
- **ZERO runtime imports from `routes/mmm/`** in MMMX hotpath — adapters only
- **Separate DB file** — `mmmx_sessions.db` never touches MMM database
- **Separate registry** — `_mmmx_monitors` dict distinct from MMM's
- **WebSocket namespace** — all MMMX events prefixed `mmmx_`, never `mmm_`
- **Generation counter** — per-session, DB-persisted, prevents stale monitor P0 incident

### Reverse Mode (ENFORCEMENT)
- MMMX has no reverse mode
- Never check/modify `session['_reverse']` in MMMX code
- Reverse P&L is separate from MMMX P&L in portfolio aggregates

---

## SECTION 21: QUICK REFERENCE — KEY FORMULAS

```python
# Hard Stop
hard_stop_usd = hard_stop_multiplier × total_premium_collected

# OTM Buffer (per side)
CE_otm_pct = (position['strike'] - current_spot) / current_spot × 100
PE_otm_pct = (current_spot - position['strike']) / current_spot × 100

# Move Trigger
spot_move_pct = abs(current_spot - last_deployment_spot) / last_deployment_spot × 100
ready_to_deploy = spot_move_pct >= tranche_deploy_move_pct OR iv_rank_delta >= tranche_deploy_iv_delta

# DTE Remaining
dte = (expiry_datetime - datetime.now(timezone.utc)).total_seconds() / 86400

# Strike Snap (LIVE API ONLY)
raw_target = current_spot × (1 ± otm_distance_pct / 100)
selected_strike = min(available_strikes, key=lambda s: abs(s - raw_target))

# Recovery Lots (30/70 split)
ce_recovery_usd = loss_usd × 0.30
pe_recovery_usd = loss_usd × 0.70
```

---

## SECTION 22: OPERATION HANDBOOK

### Pre-Live Checklist
1. ✓ Create session (DRAFT state)
2. ✓ Set expiry, validate gates
3. ✓ Scan strikes, review liquidity
4. ✓ Deploy Tranche 1 manually (confirm premiums)
5. ✓ Confirm transition to RUNNING

### Live Management Flow
1. Monitor status bar + incident queue
2. Confirm trigger engine winner (priority enforced)
3. Execute required controls if triggered
4. Verify command completion via event stream
5. Record intervention rationale in audit

### Failure Handling
1. Acknowledge incident
2. Run prescribed mitigation (e.g., reconcile, manual close)
3. Verify outcome via events
4. Return to protected steady state
5. Post-mortem: review audit log + parameters

### Fundamental Truths
- **Hard stop is law** — no override once RUNNING
- **Protection always wins** — shields outrank deployment
- **Margins are tight** — 80% utilization caps new sells
- **Old positions go deeper OTM** — this is correct, not a risk
- **Market retraces confirm we're right** — deployment queue clears on retracement
- **Whipsaw is a real cost** — high oscillation forces wider deposit/lower deposit thresholds
- **Reconcile after restart** — DB may diverge from exchange; operator disposition required

---

## SECTION 23: KNOWN LIMITATIONS (MVP v1)

- No regime controls (deferred v2)
- No perp hedge (deferred v2)
- No multi-operator concurrency (deferred v2)
- No role-based permissions (deferred v2)
- CI/CD isolation checks not yet implemented (planned)

---

## SECTION 24: WORK LOG REQUIREMENT (MANDATORY)

**Every session that touches ANY MMM file must:**
1. **READ:** `mmm_workdone_march.md` before starting
2. **ADD entry at end** when done: `## YYYY-MM-DD — <short title>`

This applies to:
- `webui/backend/routes/mmmx/`
- `webui/frontend/src/components/mmmx/`
- Any file containing `mmmx` in name

**Why:** MMMX has 50+ interdependencies. Work log prevents duplicate effort and re-introduced bugs.

---

**Last Updated:** 2026-04-07  
**Version:** AI Context v1.0 (tokens ~4,200 for full strategic + architectural scope)  
**Use Case:** AI context reading for development, debugging, and operational understanding without token bloat
