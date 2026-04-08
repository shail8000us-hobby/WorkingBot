## MMMX Implementation Plan — Monthly BTC Options (20–45 DTE)

> Status: Final planning document — v6 (institutional reuse + gap map)
>
> Goal: Keep the approved MMMX isolation architecture, but implement **true monthly options logic** rather than a 0DTE adaptation.
>
> Last updated: 2026-04-05 — v6: MMM reuse matrix added (§23), remaining gap roadmap (§24), ATM Shield promoted from deferred to core (§3.4, §4), deployment conditions corrected to OR logic, session state updated with ATM shield fields, build order updated.

---

## 0) Critical Gaps Found in v1 Plan (Addressed Below)

The following were **missing or underspecified** in v1. Each is now resolved in the relevant section:

| # | Gap | Severity | Resolution |
|---|-----|----------|------------|
| G1 | **No executor module** — plan puts order execution in engine, but MMM separated this for smart execution (mid-price, reprice, fill wait) | P0 | New file `mmmx_executor.py` added (§4) |
| G2 | **No circuit breaker** — exchange API failures will crash the monitor | P0 | New file `mmmx_circuit_breaker.py` added (§4) |
| G3 | **No session restore on backend restart** — monthly positions run for weeks; backend WILL restart | P0 | Restore logic added to `__init__.py` contract (§4, §18) |
| G4 | **No watchdog** — if monitor thread dies silently at 24h cadence, nobody notices for days | P0 | New file `mmmx_watchdog.py` added (§4) |
| G5 | **No generation guard / stale monitor protection** — MMM had a P0 incident from this exact gap | P0 | Generation tracking added to monitor contract (§9) |
| G6 | **No margin awareness** — rolling into new strikes without margin check can blow up the account | P1 | Margin check added to execution gates (§8, §10) |
| G7 | **No telegram/alert integration** — naked positions, failures, and triggers need operator notification | P1 | `mmmx_telegram.py` added (§4) |
| G8 | **No pending order dedup** — retry during network issues can place duplicate orders | P1 | Dedup logic added to executor contract (§8) |
| G9 | **No exchange reconciliation** — after restart, state may diverge from exchange | P1 | Reconciliation added to initializer contract (§10, §18) |
| G10 | **No constants file** — LOT_SIZE_BTC used in formulas but not defined; can't import from MMM | P1 | New file `mmmx_constants.py` added (§4) |
| G11 | **No options chain service reference** — plan doesn't say how to scan strikes | P2 | Shared `OptionsChainService` (read-only) documented (§19) |
| G12 | **No DVOL/IV history source** — `compute_iv_rank()` needs data but source unspecified | P2 | `patience_iv.py` service documented as read-only source (§19) |
| G13 | **No naked position recovery path** — plan says "mark naked CE risk" but not what happens next | P2 | Recovery protocol specified (§10) |
| G14 | **Position model too simple** — single CE/PE entry doesn't survive rolls; need position list with IDs | P2 | Position model upgraded (§5) |
| G15 | **No audit trail** — monthly positions need full event log for post-mortem | P2 | `mmmx_audit_log.py` added (§4) |
| G16 | **No health grading** — 24h cadence means stale data is invisible without telemetry | P2 | Health tracking added to monitor contract (§9) |
| G17 | **No cross-system margin awareness** — MMM + MMMX share one exchange account | P2 | Cross-margin check documented (§19) |
| G18 | **No liquidity validation criteria** — "validate liquidity" undefined | P2 | Liquidity gate specified (§6, §10) |
| G19 | **Timezone handling unspecified** — DTE computation, expiry comparison | P2 | UTC-only mandate added (§5) |
| G20 | **No frontend build step** — production build artifacts need updating | P3 | Added to build order (§14) |
| G21 | **Activity types/categories unspecified** | P3 | Taxonomy defined (§4 activity section) |
| G22 | **No observer pattern for cross-cutting concerns** | P3 | Deferred to v2 (not MVP) |
| G23 | **No analytics/aggregator** | P3 | Deferred to v2 (not MVP) |
| G24 | **DTE computation source unspecified** | P3 | Explicit formula added (§6) |
| G25 | **No heartbeat health grading** | P3 | Added to monitor (§9) |
| G26 | **No stale-data guard on P&L** — if premium fetch fails, P&L is stale | P1 | P&L incomplete guard added (§9) |
| G27 | **24h heartbeat cannot detect intraday flash crashes** — a 7% BTC move in 90 seconds would go undetected until next scheduled beat (hours away) | P0 | New file `mmmx_premium_listener.py` added (§9b); circuit breaker tier-0 triggers added to `mmmx_trigger.py` |
| G29 | **Single entry at full size** — deploying all lots at entry is the worst options practice. A Day 1 move immediately endangers the entire position. Correct model: deploy 10% tranches dynamically as market moves + IV spikes confirm deployment opportunity. Old positions stay open (deeper OTM = faster theta). Hard stop scales with premium collected. Heartbeat must be 1h (not 24h) to catch move confirmations. | P0 | Full tranche deployment model added (§3, §5, §6, §7, §8, §11); heartbeat changed to 1h base |
| G28 | **Wrong assumption: "close all" on large directional moves** — in reality, when market falls, CE goes deep OTM (profitable) while PE is threatened. The correct action is REPOSITION (roll profitable side forward, roll threatened side farther OTM), NOT close all. Close all is only justified when threatened side delta >= 0.70 (near ITM). High IV after a move is an OPPORTUNITY to collect premium, not a reason to exit. | P0 | Trigger logic overhauled (§7, §9b, §9c); new `DIRECTIONAL_REPOSITION` and `NEAR_ITM` triggers; CB now wakes heartbeat instead of closing; `execute_reposition()` added to engine (§8) |

---

## 1) Locked Architecture Decisions (Do Not Change)

These are final and must be implemented exactly:

- Package path: `webui/backend/routes/mmmx/`
- Separate DB file: `mmmx_sessions.db` (MMMX never reads/writes `mmm_sessions.db`)
- WebSocket namespace: all MMMX events must be prefixed `mmmx_`
- No `mmm_*` runtime imports inside MMMX runtime paths
- Separate monitor registry dict (MMM and MMMX registries must be disjoint)
- MVP scope first: core entry/hold/adjust/exit only
- No regime/perp/harvest/recycler in v1
- Frontend scope: MVP dashboard only
- **DTE safety rule is hard-enforced**: close when DTE reaches `close_at_dte` (default 7), and `close_at_dte` cannot be set below 7.

**NEW — Shared infrastructure that MMMX MAY use (read-only, no modification):**

| Shared Module | What MMMX Uses | Constraint |
|---|---|---|
| `bot/api/async_delta_client.py` | REST API calls to Delta Exchange | Read-only. Create fresh instance per event loop. |
| `bot/api/unified_api_client.py` | Order placement | Read-only. Lazy-load per executor instance. |
| `config/loader.py` | `get_api_credentials()` | Read-only. |
| `webui/backend/options_chain/chain_service.py` | `OptionsChainService` for strike scanning, chain data | Read-only. Lazy-load. |
| `webui/backend/services/patience_iv.py` | `get_current_dvol()`, DVOL history for IV rank | Read-only. |
| `bot/volatility/iv_rv_tracker.py` | Historical IV data if needed | Read-only. |

**These modules must NEVER be modified by MMMX work.** If MMMX needs different behavior, wrap/extend in MMMX's own module.

---

## 2) Core Strategy Corrections (Monthly, Not 0DTE)

The prior plan is superseded on strategy behavior. MMMX must follow these monthly-specific principles:

1. **No strike-shift module** in v1 (`mmmx_strike_shift.py` removed from plan)
2. **No close-at-5 style module** in v1 (`mmmx_close_at_threshold.py` removed from plan)
3. Trigger model is **delta drift + IV expansion + risk thresholds**, not premium % movement from snapshot
4. Adjustment model is **roll / reduce / close-all**, never repetitive lot-adding loops like intraday MMM patterns
5. Final-week gamma risk is hard-controlled by mandatory DTE exit policy (`close_at_dte >= 7`)

### Key Behavioral Differences from MMM

| Aspect | MMM (0DTE) | MMMX (Monthly) |
|--------|-----------|----------------|
| Time horizon | Hours | Weeks |
| Heartbeat | 60s–1200s adaptive | 24h base, 1h post-trigger, immediate on CB |
| Primary risk | Premium explosion (gamma) | IV expansion (vega), then delta drift |
| Adjustment | Sell more of opposite side | Reposition (roll both), reduce, close-all (last resort) |
| Position model | Many lots accumulated via adjustments | Small initial position, maintained via repositions |
| Strike selection | Premium-based (desired premium) | Sigma-based (delta target at DTE) |
| Exit | Close-at-5 (premium decay) | DTE-based mandatory exit |
| Safety net | Whipsaw guard, regime blocks | Delta threshold gates, IV catastrophe, max session loss |
| Large directional move | Triggers adjustment (sell opposite) | Triggers REPOSITION — book OTM profit, roll threatened side farther |
| IV spike | Regime blocks / pauses | OPPORTUNITY — collect elevated premium on repositioned strikes |

### Fundamental Options Dynamics (Non-Negotiable Principle — G28)

**When market moves significantly in one direction, the two legs behave ASYMMETRICALLY:**

| Market Direction | Call (CE) | Put (PE) |
|-----------------|-----------|----------|
| Market FALLS sharply | Goes DEEP OTM → delta collapses → premium DECAYS (delta + gamma overwhelm IV) → **profitable** | Moves TOWARD ATM → delta explodes → gamma blast + IV spike ALL push premium UP → **threatened** |
| Market RISES sharply | Moves TOWARD ATM → delta explodes → gamma blast + IV spike ALL push premium UP → **threatened** | Goes DEEP OTM → delta collapses → premium DECAYS (delta + gamma overwhelm IV) → **profitable** |

**IV spike alone CANNOT overcome delta collapse on the deep OTM side.** This is the key insight that separates experienced traders from naive models. A 42% IV spike adds vega premium, but a 7% directional move on a 1.28σ OTM strike pushes that side so far OTM that delta and gamma collapse dominates.

**Implication for MMMX:** High IV after a directional move is an OPPORTUNITY, not just a threat. The correct response is:
1. **Book profit** on the deep OTM side (cheap to buy back)
2. **Roll it forward** to a new ATM-adjacent strike and collect fat premium at elevated IV
3. **Roll threatened side farther OTM** (reduce delta exposure)
4. **Close all only when threatened side delta ≥ 0.70** (near ITM — gamma becomes infinite, unmanageable)

---

## 3) Monthly Strategy Operating Model

### Core Philosophy: Dynamic Tranche Deployment (G29)

**Never deploy full capital at entry.** The market will move — that is certain. The question is whether you have capital left to respond intelligently. MMMX deploys capital in 10% tranches, using market moves and IV spikes as deployment signals.

```
Total budget: N lots per side (operator sets, e.g. 100)
Initial deployment: 10% (10 lots) at session start
OTM distance: operator-defined % from current ATM (default 15%, hot-reloadable)
Subsequent tranches: 10% each, deployed when move + IV confirms
Max tranches: 10 (= 100% budget)
Old positions: NEVER closed on directional moves — left to collect theta as they go deeper OTM
```

### Tranche Deployment Logic

Every 1-hour heartbeat evaluates:

```
Deploy next tranche IF:
  (CONDITION A: spot moved >= tranche_deploy_move_pct from LAST DEPLOYMENT spot (e.g. 2%)
   OR
   CONDITION B: IV rank increased >= tranche_deploy_iv_delta since last deployment (e.g. 10 points))
  AND tranches_remaining > 0
  AND margin utilization < 80%
  AND ATM Shield did NOT fire this beat  ← shield takes priority (see §3.4)

New tranche strikes = current_spot × (1 ± otm_distance_pct/100)
  (NOT original entry spot — recalculated from CURRENT ATM)

Old positions remain open at original strikes (now deeper OTM = more theta, less delta risk)

OR logic: either a spot move OR an IV spike alone is sufficient to deploy.
  A 2% spot move without IV change = market is trending → collect premium at new ATM
  An IV spike without a move = vol event (news, event) → elevated premium to sell
  Both together = strongest signal
Maximum one tranche per beat even if both conditions fire.
```

**Why 1 hour?** A market move within 1 hour either:
- **Retraces** → move was noise, IV subsides → do NOT deploy (saved capital)
- **Holds / continues** → IV remains elevated → deploy next tranche at new ATM ± OTM distance → collect elevated premium on fresh strikes

### Capital Deployment Example

```
Session start (BTC $67,500, DVOL 52%):
  Tranche 1: 10 lots CE @ 77,625 (15% OTM), 10 lots PE @ 57,375 (15% OTM)
  Premium collected: $550
  Hard stop: $1,100 (2× $550)
  Deployed: 10%, Available: 90%

Hour 2 (BTC $70,500, DVOL 61%, moved +4.4%, IV rank +8):
  Tranche 2: 10 lots CE @ 81,075 (15% from $70,500), 10 lots PE @ 59,925
  Old CE @ 77,625: now 10.1% OTM from new spot → deeper OTM, collecting theta, no action
  New premium: +$620
  Hard stop: $2,340 (2× $1,170 total)
  Deployed: 20%, Available: 80%

Hour 3 (BTC $72,500, DVOL 66%, moved +2.8%):
  Move < 3% threshold → NO deployment, wait
  Hard stop unchanged

Hour 5 (BTC $74,000, DVOL 70%, moved +2.1% from $72,500):
  Cumulative from last deployment: $74,000 - $70,500 = +$3,500 (+4.9%) ✓
  IV rank increased by 7 ✓
  Tranche 3: 10 lots CE @ 85,100, 10 lots PE @ 62,900
  Premium: +$700
  Hard stop: $4,740 (2× $2,370 total)
  Deployed: 30%, Available: 70%
```

### Hard Stop (Dynamic — Scales With Premium Collected)

```python
hard_stop_usd = hard_stop_multiplier × total_premium_collected_usd
# Default: hard_stop_multiplier = 2.0

# Recalculated after every new tranche deployment
# If total P&L <= -hard_stop_usd → close ALL tranches immediately

# Example progression:
# After Tranche 1: collected $550 → hard stop = -$1,100
# After Tranche 3: collected $1,870 → hard stop = -$3,740
# If market reverses badly and total P&L hits -$3,740 → close all
```

### Position Management Actions

| Situation | Action |
|-----------|--------|
| Market moves ≥ 2% OR IV rank +10 pts | Deploy next tranche at new ATM ± OTM% |
| Market retraces (within 1h) | Do nothing — old positions collecting theta |
| Any tranche position OTM buffer < 5% | ATM Shield: reposition + recovery lots (see §3.4) |
| Total P&L ≤ −hard_stop_usd | Close ALL tranches + all recovery positions |
| DTE ≤ close_at_dte | Close ALL tranches |
| IV catastrophe (DVOL doubled) + threatened delta ≥ 0.70 | Close ALL tranches |

---

### 3.4 ATM Shield (Core Protection Mechanism)

**ATM Shield fires when any tranche position's remaining OTM buffer drops below `atm_protect_threshold` (default 5%).**

This is the primary defense against sustained directional moves. It does NOT close the session — it repositions the endangered position and adds recovery lots to offset the loss.

#### Capital Structure

```
TRANCHE BUDGET:     100 lots per side  (10 tranches × 10 lots)
ATM SHIELD RESERVE:  30 lots extra     (protection only — never used for deployment)
TOTAL MAX EXPOSURE: 130 lots per side
```

#### Trigger Condition

```python
# Per tranche, per side, every heartbeat:
if side == 'ce':
    remaining_otm_pct = (position['strike'] - current_spot) / current_spot × 100
else:
    remaining_otm_pct = (current_spot - position['strike']) / current_spot × 100

if remaining_otm_pct < params['atm_protect_threshold']:  # default 5%, hot-reloadable
    trigger_atm_shield(tranche, side)
```

#### Execution Sequence (6 Steps)

1. **Calculate loss** — `loss_usd = (buyback_premium - entry_premium) × lots × LOT_SIZE_BTC`
2. **Buy back the endangered position** — `smart_execute(side='buy', max_reprice_attempts=10)`. 10 attempts × 30s each = 5-minute max. Falls back to `emergency_execute()` if all 10 fail. Same `_being_closed` / partial-fill / external-close-check guards as MMM's `close_position()`.
3. **Sell new position at fresh strike** — `nearest_available_strike(current_spot × (1 ± otm_distance_pct), live_chain_cache)`. If sell fails after buyback → session PAUSED + NAKED ALERT.
4. **Calculate recovery lots (30/70 split)** — `ce_recovery_lots = ceil(loss × 0.30 / (new_ce_premium × LOT_SIZE))`, `pe_recovery_lots = ceil(loss × 0.70 / (new_pe_premium × LOT_SIZE))`.
5. **Sell recovery lots from reserve** — if reserve exhausted, reposition still happens, recovery lots are scaled/skipped.
6. **Update state** — close old position record, add new position, update reserve, recompute hard stop.

#### Constraints

| Constraint | Rule |
|---|---|
| Max shifts per position | `atm_shield_max_shifts` (default 3, **hot-reloadable**) |
| No further OTM strike on exchange | Force-refresh chain cache first. If still blocked: apply delta-gate (reduce 50% at δ≥0.35, reduce 75% at δ≥0.55, hard stop at δ≥0.70) |
| Max shifts exhausted | Same delta-gate + Telegram tells operator to raise `atm_shield_max_shifts` |
| Reserve exhausted | Reposition original lots (steps 1-3), skip recovery lots (steps 4-5), Telegram alert |

#### Beat Priority

Shield fires **before** deployment. If shield fires this beat → deployment skipped.

#### Strike Selection

Uses live exchange API (not hardcoded steps):
```python
available_strikes = fetch_available_strikes(asset='BTC', expiry_date=session['expiry_date'])
# API: GET /v2/tickers?contract_types=call_options,put_options&underlying_asset_symbols=BTC
candidate_strike = min(available_strikes, key=lambda s: abs(s - raw_target))
```

---

## 4) Required File Deliverables

### Backend module set (`webui/backend/routes/mmmx/`)

| File | Purpose | Lines Est. |
|------|---------|-----------|
| `__init__.py` | Blueprint registration, `init_mmmx()`, session restore on startup | ~120 |
| `mmmx_constants.py` | **NEW (G10)** — `LOT_SIZE_BTC = 0.001`, shared constants | ~30 |
| `mmmx_state.py` | Session state model, defaults, hot-reload params | ~400 |
| `mmmx_config.py` | Parameter validation, rules, ranges, `close_at_dte >= 7` enforcement | ~250 |
| `mmmx_storage.py` | SQLite persistence (`mmmx_sessions.db`), thread-safe | ~350 |
| `mmmx_activity.py` | Activity log ring buffer | ~200 |
| `mmmx_audit_log.py` | **NEW (G15)** — Append-only event journal for post-mortem | ~150 |
| `mmmx_websocket.py` | WebSocket event emitters (all `mmmx_*` prefixed) | ~150 |
| `mmmx_telegram.py` | **NEW (G7)** — Telegram alerts for triggers, failures, naked positions | ~120 |
| `mmmx_executor.py` | **NEW (G1)** — Smart execution: mid-price, reprice, fill wait, dedup | ~500 |
| `mmmx_engine.py` | Monthly math: sigma strikes, P&L, portfolio delta, IV change | ~400 |
| `mmmx_trigger.py` | Priority-ordered trigger evaluation (10 triggers) | ~300 |
| `mmmx_safety.py` | Pre-beat safety checks, DTE sanity, max adjustments | ~200 |
| `mmmx_initializer.py` | Entry gates, strike selection, order flow, chain scanning | ~500 |
| `mmmx_circuit_breaker.py` | **NEW (G2)** — 3-state API fault isolation (CLOSED/OPEN/HALF_OPEN) | ~120 |
| `mmmx_watchdog.py` | **NEW (G4)** — Supervisor that detects and restarts dead monitors | ~150 |
| `mmmx_monitor.py` | Background heartbeat thread, generation tracking, health grading | ~800 |
| `mmmx_premium_listener.py` | **NEW (G27)** — Real-time WebSocket listener for active strikes; circuit breaker emergency close | ~350 |
| `mmmx_atm_shield.py` | **NEW (§3.4)** — ATM Shield: OTM buffer monitoring, buyback + reposition + recovery lot execution | ~500 |
| `mmmx_param_audit.py` | **NEW (Gap G14)** — Append-only SQLite log of every hot-reload param change: who, when, old, new | ~150 |
| `mmmx_margin_guardian.py` | **Adapter for `mmm_margin_guardian.py`** — wraps `MarginGuardian` for MMMX session registry | ~80 |
| `mmmx_api.py` | REST API blueprint (`/api/mmmx/*`) | ~600 |
| `tests/` | Unit tests | ~500 |

**Total new backend: ~7,170 lines across 23 files**

### Activity Types & Categories (G21)

```python
ACTIVITY_TYPES = {
    # Lifecycle
    'entry': 'Session Entry (Tranche 1)',
    'tranche_deployed': 'Tranche Deployed',              # NEW G29
    'monitor_start': 'Monitor Started',
    'monitor_stop': 'Monitor Stopped',
    # Constructive
    'tranche_partial': 'Tranche Partially Filled',       # NEW G29 (PE failed after CE)
    # Defensive
    'tranche_reduce': 'Tranche Position Reduced',        # NEW G29
    'reduce': 'Position Reduce (Legacy)',
    'close_all': 'Close All Positions',
    'hard_stop': 'Hard Stop Triggered',                  # NEW G29
    'dte_close': 'DTE Safety Close',
    'iv_close': 'IV Catastrophe Close',
    'profit_close': 'Profit Target Close',
    # Safety
    'cb_near_itm': 'CB Near-ITM Emergency Reduce',
    'cb_force_check': 'CB Forced Heartbeat',
    'safety': 'Safety Event',
    'naked_alert': 'Naked Position Alert',
    # Config
    'param_update': 'Parameter Update',
    'force_check': 'Forced Check',
}

ACTIVITY_CATEGORIES = {
    'lifecycle': ['entry', 'tranche_deployed', 'monitor_start', 'monitor_stop'],
    'constructive': ['tranche_deployed', 'tranche_partial'],
    'adjustments': ['tranche_reduce', 'reduce', 'close_all', 'hard_stop',
                    'dte_close', 'iv_close', 'profit_close'],
    'safety': ['safety', 'naked_alert', 'cb_near_itm', 'cb_force_check'],
    'config': ['param_update', 'force_check'],
}
```

### Frontend module set (`webui/frontend/src/components/mmmx/`)

| File | Purpose |
|------|---------|
| `MMMXDashboard.js` | Main dashboard container |
| `MMMXContext.js` | React Context + WebSocket listeners |
| `mmmxService.js` | API service client (axios) |
| `hooks/useMMMXWebSocket.js` | WebSocket subscription hook |

### Integration points (ZERO modification to MMM files)

| File | Change | Risk to MMM |
|------|--------|-------------|
| `webui/backend/app.py` | Register MMMX blueprint in isolated `try/except` AFTER MMM block | **ZERO** — additive only, same pattern as MMM/IC registration |
| `webui/frontend/src/App.js` | Add MMMX lazy import + tab + route | **ZERO** — additive only |
| `webui/frontend/src/config/navigationSections.js` | Add MMMX nav entry after MMM | **ZERO** — additive only |

---

## 5) Session State & Parameter Contract

### Timestamps: UTC-only mandate (G19)

All timestamps in MMMX must use `datetime.now(timezone.utc)`. No naive `utcnow()`. All stored timestamps include `+00:00` suffix. DTE computation: `(expiry_datetime - datetime.now(timezone.utc)).total_seconds() / 86400`.

### Parameter Defaults

`mmmx_state.py` must implement the specified session layout and these defaults:

**Entry gates:**
- `entry_dte_min=20`, `entry_dte_max=45`, `entry_iv_rank_min=50`

**Tranche deployment (G29 — core capital model):**
- `total_budget_lots=100` — maximum lots per side for the full session
- `tranche_pct=10` — percentage of total budget per tranche (10% = 10 lots)
- `otm_distance_pct=15` — how far OTM new strikes are placed from current ATM (hot-reloadable)
- `tranche_deploy_move_pct=3.0` — minimum spot move % from last deployment to consider next tranche (hot-reloadable)
- `tranche_deploy_iv_delta=5` — minimum IV rank increase since last deployment to confirm (hot-reloadable)
- `hard_stop_multiplier=2.0` — hard stop = this × total_premium_collected (hot-reloadable)

**Heartbeat:**
- `adjustment_interval_hours=1` — 1 hour base cadence (not 24h)

**Delta gates (G28):**
- `delta_drift_threshold=0.35` — when any tranche position delta crosses this, evaluate reposition
- `portfolio_delta_threshold=0.15` — combined portfolio delta threshold
- `near_itm_delta=0.55` — reduce threatened tranche when delta reaches this
- `emergency_delta=0.70` — close_all when any position reaches this delta

**IV controls:**
- `iv_spike_threshold_pct=50` — IV change % that raises alert (still deploy if delta safe)
- `iv_catastrophe_pct=80` — IV change % that closes all (if emergency_delta also breached)

**Exit controls:**
- `close_at_dte=7` (enforced minimum 7)
- `profit_target_pct=50`, `profit_target_enabled=False`

**Session controls:**
- `expiry`, `alert_on_adjustment=True`

Hot-reload allowlist: `otm_distance_pct`, `tranche_deploy_move_pct`, `tranche_deploy_iv_delta`, `hard_stop_multiplier`, `adjustment_interval_hours`, `delta_drift_threshold`, `near_itm_delta`, `iv_spike_threshold_pct`, `iv_catastrophe_pct`, `profit_target_pct`, `profit_target_enabled`, `close_at_dte`, `alert_on_adjustment`

### Position Model (Tranche-Based — G14, G29)

MMMX tracks positions as a list of tranches, each with its own CE and PE entries. Multiple tranches are open simultaneously by design.

```python
# Top-level tranche list
session['tranches'] = [
    {
        'tranche_id': 1,
        'tranche_pct': 10,           # % of budget this tranche represents
        'deployed_at': '2026-04-04T10:00:00+00:00',
        'entry_spot': 67500,         # BTC spot at time of deployment
        'entry_dvol': 52.0,          # DVOL at deployment
        'entry_iv_rank': 65,
        'ce': {
            '_pos_id': 'uuid-hex8',
            'strike': 77625,
            'lots': 10,
            'entry_premium': 140.0,
            'entry_delta': 0.20,
            'symbol': 'C-BTC-77625-010526',
            'status': 'ACTIVE',       # ACTIVE | CLOSED | REDUCED | REPOSITIONED
            'current_premium': None,  # Updated each beat
            'current_delta': None,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            # ATM Shield tracking per position (§3.4)
            'shield_shift_count': 0,  # How many times this position has been repositioned
            'shield_history': [],     # [{old_strike, old_entry_premium, buyback_premium, loss_usd, shifted_at}]
            '_being_closed': False,   # In-flight guard (same as MMM close_position pattern)
            '_being_closed_at': None, # monotonic timestamp; TTL=180s auto-clear
        },
        'pe': {
            '_pos_id': 'uuid-hex8',
            'strike': 57375,
            'lots': 10,
            'entry_premium': 135.0,
            # ... same structure as ce
        },
        'premium_collected': 275.0,  # (ce + pe) × lots × LOT_SIZE_BTC
        'unrealized_pnl': 0.0,
        'realized_pnl': 0.0,
        'status': 'ACTIVE',          # ACTIVE | PARTIAL | CLOSED
    },
    # Tranche 2 added after market moves...
    {
        'tranche_id': 2,
        'deployed_at': '...',
        'entry_spot': 70500,         # Different spot — new strikes
        'ce': {'strike': 81075, ...},
        'pe': {'strike': 59925, ...},
        # ...
    }
]

# Aggregates (computed from tranches)
session['total_deployed_lots'] = 20          # Sum across all active tranches
session['total_budget_lots'] = 100
session['tranches_deployed'] = 2
session['tranches_remaining'] = 8
session['total_premium_collected'] = 1170.0  # Sum across all tranches
session['hard_stop_usd'] = 2340.0            # 2× total_premium_collected
session['last_deployment_spot'] = 70500      # For move % calculation
session['last_deployment_iv_rank'] = 73      # For IV delta calculation
```

**Why tranche list, not single entry (G29):** Multiple tranches are open simultaneously. Each tranche was deployed at a different spot price, has different strikes, and collects theta independently. Old tranches go deeper OTM as market moves — this is the intended behavior, not a problem to fix. `_pos_id` on each position enables atomic removal without index bugs (MMM robustv2 fix #8).

### Session-Level Tracking

```python
session = {
    'session_id': 'hex8',
    'strategy_status': 'IDLE',  # IDLE | RUNNING | PAUSED | STOPPED | COMPLETE | PARTIAL_ENTRY | EXITING
    'params': { ... },
    'expiry': '010526',         # DDMMYY format matching Delta Exchange
    'expiry_datetime': '2026-05-01T08:00:00+00:00',

    # Tranche portfolio (G29)
    'tranches': [],                     # List of tranche objects (see Position Model)
    'total_budget_lots': 100,           # Max lots per side for session
    'total_deployed_lots': 0,           # Active lots across all tranches
    'tranches_deployed': 0,
    'tranches_remaining': 10,           # budget/tranche_pct
    'last_deployment_spot': None,       # Spot at last tranche deployment
    'last_deployment_iv_rank': None,    # IV rank at last deployment

    # Entry snapshot (from Tranche 1)
    'entry_spot': None,
    'entry_dvol': None,
    'entry_iv_rank': None,
    'entry_dte': None,
    'entry_timestamp': None,

    # Aggregates (sum across all tranches)
    'total_premium_collected': 0.0,
    'realized_pnl': 0.0,
    'unrealized_pnl': 0.0,
    'total_pnl': 0.0,
    'peak_pnl': 0.0,

    # Dynamic hard stop (G29)
    'hard_stop_usd': 0.0,           # = hard_stop_multiplier × total_premium_collected
                                     # Recalculated after every tranche deployment

    # Adjustment tracking
    'adjustment_count': 0,
    'adjustment_history': [],        # Capped at 100 entries (more tranches = more events)

    # Derived monitoring (updated each beat)
    'portfolio_delta': 0.0,          # Combined delta across ALL active tranche positions
    'iv_change_pct': 0.0,            # vs entry_dvol
    'current_dte': None,
    'last_beat_at': None,
    'last_trigger': None,

    # Per-tranche delta monitoring (G28)
    # Worst-case delta across all active tranches (drives action gates)
    'max_threatened_delta': 0.0,
    'worst_tranche_id': None,        # Which tranche has the highest threatened delta

    # Monitor metadata
    '_monitor_generation': 0,
    '_circuit_breaker_state': 'CLOSED',
    '_pnl_calculation_incomplete': False,

    # ATM Shield (§3.4)
    'atm_shield_reserve_lots': 30,          # Set at session start (hot-reload No)
    'atm_shield_reserve_remaining': 30,     # Decrements on each shield recovery sell
    'atm_shield_reserve_used': 0,
    'atm_shield_events': [],                # List of shield event summaries for UI

    # ATM recovery positions (sold from reserve during shield events)
    'atm_recovery_positions': [],           # [{side, strike, lots, entry_premium, from_shield_event, ...}]
                                            # Included in total P&L; closed on hard stop / DTE close

    # Naked position tracking (G13)
    '_naked_tranche_id': None,       # Tranche ID where PE/CE entry failed
    '_naked_side': None,
    '_naked_since': None,

    # Hybrid monitoring coordination (G27)
    '_force_check': False,
    '_cb_reducing': False,
    '_last_beat_premiums': {},       # {tranche_id: {ce: float, pe: float}} set each beat
    '_live_premiums': {},            # {tranche_id: {ce: float, pe: float}} updated by listener
}
```

---

## 6) Engine Functions (Exact Behavioral Spec)

`mmmx_engine.py` must implement monthly math primitives:

### 1. `compute_sigma_based_strikes(spot, iv, dte, sigma_distance=1.28)`

Uses expected move:
- `expected_1sigma = iv × sqrt(dte/365) × spot`
- CE strike = `round(spot + expected_1sigma × sigma_distance)` (rounded to exchange tick)
- PE strike = `round(spot - expected_1sigma × sigma_distance)` (rounded to exchange tick)
- Default `sigma_distance=1.28` targets ~20Δ

### 2. `compute_unrealized_pnl(session)`

Per position for shorts:
- `pnl = (entry_premium - current_premium) × lots × LOT_SIZE_BTC`
- Sum across all ACTIVE positions per side
- Set `_pnl_calculation_incomplete = True` if any current_premium is None or stale (G26)

### 3. `compute_portfolio_delta(session)`

- CE contribution: `sum(pos.current_delta × pos.lots × LOT_SIZE_BTC)` (negative for short calls)
- PE contribution: `sum(pos.current_delta × pos.lots × LOT_SIZE_BTC)` (positive for short puts → their delta is negative, short = +delta)
- Combined portfolio delta in BTC equivalent

### 4. `compute_iv_change_from_entry(session, current_dvol)`

- `iv_change_pct = ((current_dvol - entry_dvol) / entry_dvol) × 100`
- Returns: `(iv_change_pct, is_spike, is_catastrophe)`
  - `is_spike = iv_change_pct >= iv_spike_threshold_pct`
  - `is_catastrophe = iv_change_pct >= iv_catastrophe_pct`

### 5. `compute_iv_rank(current_dvol, dvol_history_list)`

- Percentile-based: `count(history < current_dvol) / len(history) × 100`
- Requires minimum 30 data points; returns `None` if insufficient

### 6. `compute_dte(expiry_datetime)` (G24)

- `dte = (expiry_datetime - datetime.now(timezone.utc)).total_seconds() / 86400`
- Returns float (e.g., 23.5 days)
- Negative DTE = expiry has passed

### 6. `compute_tranche_strikes(spot, otm_distance_pct)` (G29)

```python
# Simple, hot-reloadable OTM distance from current ATM
ce_strike = round(spot × (1 + otm_distance_pct / 100))  # e.g. 67,500 × 1.15 = 77,625
pe_strike = round(spot × (1 - otm_distance_pct / 100))  # e.g. 67,500 × 0.85 = 57,375
# Round to nearest exchange tick (usually 50 or 100 for BTC options)
```

### 7. `check_tranche_deploy_conditions(session, current_spot, current_iv_rank)` (G29)

Returns `(should_deploy: bool, reason: str)`

```python
# Condition A (OR): Spot moved enough from last deployment
spot_move_pct = abs(current_spot - last_deployment_spot) / last_deployment_spot × 100
condition_a = spot_move_pct >= tranche_deploy_move_pct  # default 2%, hot-reloadable

# Condition B (OR): IV rank increased enough since last deployment
iv_delta = current_iv_rank - last_deployment_iv_rank
condition_b = iv_delta >= tranche_deploy_iv_delta  # default 10 points, hot-reloadable

# Either condition is sufficient — OR logic
if not (condition_a or condition_b):
    return False, (
        f"Neither condition met: spot_move={spot_move_pct:.1f}% "
        f"(need {tranche_deploy_move_pct}%), "
        f"iv_delta={iv_delta:.1f} (need {tranche_deploy_iv_delta})"
    )

# Hard gates (must pass regardless)
if session['tranches_remaining'] <= 0:
    return False, "Budget fully deployed"

if margin_utilization > 80:
    return False, f"Margin {margin_utilization}% > 80% — blocked"

trigger_reason = []
if condition_a:
    trigger_reason.append(f"spot_move={spot_move_pct:.1f}%")
if condition_b:
    trigger_reason.append(f"iv_delta=+{iv_delta:.0f}")
return True, f"Deploy conditions met: {', '.join(trigger_reason)}"
```

### 8. `compute_dynamic_hard_stop(session)` (G29)

```python
hard_stop_usd = session['params']['hard_stop_multiplier'] × session['total_premium_collected']
session['hard_stop_usd'] = hard_stop_usd
# Called after every new tranche deployment AND at start of each beat
# Ensures hard stop always reflects current premium collected
```

### 9. Liquidity Validation (G18)

```python
def validate_liquidity(symbol, min_bid_depth=5, max_spread_pct=10.0):
    """
    Check if an option has sufficient liquidity for entry/roll.
    
    Returns: (is_liquid, details_dict)
    - Fetch L2 orderbook
    - Check best_bid exists and > 0
    - Check bid_depth >= min_bid_depth lots
    - Check (ask - bid) / mid × 100 <= max_spread_pct
    """
```

---

## 7) Trigger Evaluation (Priority-Ordered)

`mmmx_trigger.py` must not reuse MMM trigger logic.

### Core Decision Principle (G28)

Before evaluating any trigger, identify which side is **profitable** (deep OTM, delta collapsed) and which is **threatened** (approaching ATM, delta rising). The threatened side's delta is the primary gating variable for ALL adjustment decisions.

```python
def classify_sides(session):
    ce_delta = abs(session['ce']['positions'][-1]['current_delta'])  # 0.0–1.0
    pe_delta = abs(session['pe']['positions'][-1]['current_delta'])  # 0.0–1.0

    if ce_delta > pe_delta:
        return {'threatened': 'CE', 'profitable': 'PE', 'threatened_delta': ce_delta}
    elif pe_delta > ce_delta:
        return {'threatened': 'PE', 'profitable': 'CE', 'threatened_delta': pe_delta}
    else:
        return {'threatened': None, 'profitable': None, 'threatened_delta': max(ce_delta, pe_delta)}
```

### Delta Action Gate

The threatened side's delta **gates every adjustment action**:

```python
def decide_action_from_delta(threatened_delta):
    if threatened_delta >= 0.70:
        return 'CLOSE_ALL'        # Near ITM — infinite gamma, unmanageable
    elif threatened_delta >= 0.55:
        return 'REDUCE_THEN_ROLL' # Approaching ATM — reduce threatened, roll profitable
    elif threatened_delta >= 0.35:
        return 'REPOSITION'       # Directional but manageable — roll BOTH sides
    else:
        return None               # Normal zone — no delta-based action needed
```

### Required Priority Order (First Match Wins)

| Priority | Trigger | Severity | Action | Condition |
|----------|---------|----------|--------|-----------|
| 1 | `DTE_CLOSE` | CRITICAL | close_all | `current_dte <= close_at_dte` |
| 2 | `HARD_STOP` | CRITICAL | close_all | `total_pnl <= -hard_stop_usd` (dynamic — 2× premium collected) |
| 3 | `IV_CATASTROPHE` | CRITICAL | close_all | `iv_change_pct >= iv_catastrophe_pct` AND `max_threatened_delta >= 0.70` |
| 4 | `NEAR_ITM` | CRITICAL | reduce worst tranche | `max_threatened_delta >= 0.70` — reduce the specific tranche causing danger |
| 5 | `DEPLOY_TRANCHE` | MEDIUM | deploy next tranche | `check_tranche_deploy_conditions()` passes AND `tranches_remaining > 0` |
| 6 | `IV_SPIKE` | HIGH | reduce worst tranche | `iv_change_pct >= iv_spike_threshold_pct` AND `max_threatened_delta >= 0.55` |
| 7 | `PROFIT_TARGET` | LOW | close_all | `profit_target_enabled AND total_pnl >= total_premium_collected × profit_target_pct / 100` |
| 8 | `SIDE_LOSS` | HIGH | reduce worst tranche | Worst tranche's threatened side unrealized loss % >= `side_loss_threshold_pct` |
| 9 | `PORTFOLIO_DELTA` | MEDIUM | reduce worst tranche | `abs(portfolio_delta) >= portfolio_delta_threshold` |
| 10 | `DELTA_DRIFT` | MEDIUM | reduce specific position | Any single tranche position delta drifted >= `delta_drift_threshold` from 20Δ target |

**Key changes from original trigger model (G29):**

- `HARD_STOP` (priority 2) replaces the old fixed `max_session_loss_usd`. It is dynamic: grows with premium collected.
- `DEPLOY_TRANCHE` (priority 5) is a new constructive trigger — adds capital when market confirms a move.
- Old `DIRECTIONAL_REPOSITION` (roll both sides) is removed. In the tranche model, market moves are DEPLOYMENT signals, not repositioning signals. Old positions stay open.
- Old `DELTA_DRIFT_CE/PE` roll triggers are replaced with `reduce specific position` — for monthly options with multiple tranches, we reduce the dangerous tranche rather than rolling the whole position (which would change the strike we originally intended to hold).
- `NEAR_ITM`, `IV_SPIKE`, `SIDE_LOSS`, `PORTFOLIO_DELTA` now target the **worst tranche** specifically, not the entire session.

### Trigger Notes

**`NEAR_ITM` (Priority 4):** Fires purely on delta ≥ 0.70. At this delta, the position is approaching ITM — gamma becomes uncontrollable and rolling is no longer safe. Action: buy back 50% of threatened side immediately (reduce_then_roll), then reassess.

**`IV_SPIKE` (Priority 5):** IV spike alone is NOT a reason to close all. It is only dangerous when COMBINED with threatened_delta ≥ 0.55. If IV spikes but threatened delta is low (e.g., 0.25), the session is actually more profitable (deep OTM + high IV = premium decaying faster). Action: reposition both sides to capture the elevated IV.

**`DIRECTIONAL_REPOSITION` (Priority 6):** The primary adjustment mechanism for large moves. Fires when market has moved enough that one side is deep OTM (profitable_delta ≤ 0.12) and the other is drifting up (threatened_delta ≥ 0.35). Action: roll profitable side forward to new ATM ± 1.28σ (collect elevated IV premium), roll threatened side farther OTM (reduce delta exposure).

**`IV_CATASTROPHE` (Priority 2):** Only closes all when BOTH iv_change is catastrophic AND threatened_delta ≥ 0.70. If IV is catastrophic but threatened_delta is low (e.g., 0.20), REPOSITION instead — high IV = excellent new premium collection opportunity.

### Return Structure

```python
{
    'triggered': bool,
    'trigger_type': str,          # e.g., 'DIRECTIONAL_REPOSITION'
    'severity': str,              # 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
    'affected_side': str,         # 'CE' | 'PE' | 'BOTH'
    'action': str,                # 'close_all' | 'reduce_then_roll' | 'reposition' | 'reduce' | 'roll'
    'threatened_side': str,       # 'CE' | 'PE' | None
    'profitable_side': str,       # 'CE' | 'PE' | None
    'threatened_delta': float,    # Current delta of threatened side
    'reason': str,                # Human-readable
    'details': dict,              # Numeric details for logging
}
```

If nothing fires: `{'triggered': False, 'trigger_type': None, 'reason': 'no trigger', ...}`

---

## 8) Adjustment Execution Model

### `execute_tranche_deploy(executor, session, spot, iv_rank, dvol)` (NEW — G29)

The primary constructive action — adds capital when market confirms a directional move with IV elevation.

```
Preconditions (all must pass):
  1. check_tranche_deploy_conditions() returns True
  2. validate_liquidity() on both new strikes passes
  3. Margin pre-check passes (< 80% utilization)

Execution:
  1. Compute new strikes: compute_tranche_strikes(spot, otm_distance_pct)
  2. Calculate lots: tranche_pct × total_budget_lots / 100 (e.g. 10% × 100 = 10 lots)
  3. Sell CE via executor.smart_execute() at new CE strike
  4. If CE fails: abort, no state mutation
  5. Sell PE via executor.smart_execute() at new PE strike
  6. If PE fails after CE success: PARTIAL tranche state, Telegram alert (naked CE)
  7. On full success:
     - Append new tranche to session['tranches']
     - Update: total_deployed_lots, tranches_deployed, tranches_remaining
     - Update: last_deployment_spot, last_deployment_iv_rank
     - Update: total_premium_collected
     - Recompute: hard_stop_usd = hard_stop_multiplier × total_premium_collected
     - Increment adjustment_count
     - Emit: mmmx_tranche_deployed WebSocket event
     - Send Telegram: "MMMX Tranche {N} deployed — CE @ {ce_strike}, PE @ {pe_strike}. Premium: +${amount}. Hard stop now: ${hard_stop}"
```

### `mmmx_executor.py` (NEW — G1)

**This is a critical new file not in v1.** MMM's executor is 1,199 lines of battle-tested smart execution logic. MMMX must have its own executor with the same quality:

```python
class MMMXExecutor:
    """
    Smart order execution for MMMX.
    
    - Mid-price entry with reprice loop (60s wait + amend)
    - Pending order dedup via client_order_id (G8)
    - Fresh AsyncDeltaClient per event loop (no stale transport)
    - Circuit breaker integration
    """
    
    async def smart_execute(self, symbol, side, size, reduce_only=False,
                            session_id=None, client_order_id=None) -> dict:
        """Place at mid-price, wait 60s, reprice if needed."""
        
    async def emergency_execute(self, symbol, side, size, reduce_only=False) -> dict:
        """Market/taker order for urgent closes (IV catastrophe, max loss)."""
```

**Dedup rule (G8):** Every order gets a deterministic `client_order_id` = `mmmx_{session_id}_{action}_{timestamp_ms}`. Before placing, check if an order with this ID is already pending on exchange. If so, skip.

**Margin pre-check (G6):** Before any SELL order, executor must:
1. Fetch current margin utilization from exchange
2. If utilization > 80%, BLOCK the sell and return failure
3. Log the block, emit `mmmx_safety` event

### `mmmx_engine.py` — Adjustment Functions

- `execute_roll(executor, session, side, new_strike, new_symbol)`
  - Step 1: Buy-back ALL active positions on `side` via `executor.smart_execute(buy)`
  - Step 2: If buy-back fails → abort, no state mutation, return failure
  - Step 3: Sell at `new_strike` via `executor.smart_execute(sell)`
  - Step 4: If sell fails after buy-back → set session `PAUSED`, emit `mmmx_safety`, send Telegram (G7), log critical, no auto re-sell
  - Step 5: On success → close old position (realized P&L), add new position, increment `roll_count`, update adjustment history

- `execute_reduce(executor, session, side)`
  - Calculate: `reduce_lots = max(1, current_lots // 2)`
  - Buy back `reduce_lots` via `executor.smart_execute(buy, reduce_only=True)`
  - Update lots/status, realized pnl, adjustment history, websocket event

- `execute_close_all(executor, session)`
  - Attempt CE close and PE close **independently** (even if one fails)
  - For CRITICAL triggers (IV_CATASTROPHE, MAX_LOSS): use `executor.emergency_execute()` (taker)
  - Final status:
    - `COMPLETE` if all closed
    - `PAUSED` if any close fails (+ Telegram alert)

- `compute_roll_target_strike(session, side, spot, iv, current_dte)`
  - Re-target to `entry_delta_target` using **remaining DTE** and same expiry
  - Use `compute_sigma_based_strikes()` with current spot/iv/dte
  - Scan chain for nearest liquid strike to target
  - Must call `validate_liquidity()` and return availability metadata
  - If no liquid strike found → return failure (do not roll into illiquid strike)

- `execute_reposition(executor, session, spot, dvol, dte)` **(NEW — G28)**
  - The primary adjustment for large directional moves. Never closes the session.
  - Identifies profitable side (deep OTM, delta ≤ 0.12) and threatened side (delta 0.35–0.69)

  **Step 1 — Roll profitable side forward (collect elevated IV premium):**
  ```
  - Buy back profitable_side at current (cheap) premium → realize profit
  - Compute new target strike: sigma from CURRENT spot + current IV + remaining DTE
  - New strike is ~1.28σ from current ATM (not from original entry spot)
  - Validate liquidity on new strike
  - Sell new position at new strike → collect fat premium (IV is elevated)
  ```

  **Step 2 — Roll threatened side farther OTM (reduce delta exposure):**
  ```
  - Buy back threatened_side at current (expensive) premium → realize loss
  - Compute new target strike: push farther OTM from current spot
  - Same expiry, farther strike (~1.5–2.0σ from current ATM depending on delta)
  - Validate liquidity on new strike
  - Sell new position at new farther strike → collect some premium (reduces net cost of roll)
  ```

  **Step 3 — Net assessment:**
  ```
  - Total premium collected on new positions
  - Net cost of reposition (premium paid - premium received)
  - Update session: close old positions, add new positions, increment adjustment_count
  - Emit mmmx_adjustment with full reposition details
  - Send Telegram: "MMMX REPOSITION executed — {details}"
  ```

  **Failure cases:**
  - If Step 1 buy-back fails → abort entire reposition, return failure
  - If Step 1 sell-new fails after buy-back → PAUSED + Telegram (naked profitable side)
  - If Step 2 buy-back fails → PAUSED + Telegram (only profitable side repositioned, threatened side not rolled — dangerous)
  - If Step 2 sell-new fails after buy-back → PAUSED + Telegram (naked threatened side)

  **When NOT to reposition:**
  - If `threatened_delta >= 0.70` → do NOT reposition, execute `reduce_then_roll` first
  - If `current_dte <= close_at_dte` → do NOT reposition, execute `close_all`
  - If margin utilization > 80% → block the sell legs, return failure

- `execute_reduce_then_roll(executor, session, spot, dvol, dte)` **(NEW — G28)**
  - Called when `threatened_delta >= 0.55`. Reduces exposure before repositioning.

  **Step 1 — Reduce threatened side immediately:**
  ```
  - Buy back 50% of threatened_side lots (minimum 1 lot)
  - Use smart_execute (not emergency) — give 60s for fill
  - Update lots, realized P&L
  ```

  **Step 2 — Roll profitable side forward:**
  ```
  - Same as execute_reposition Step 1
  - Collect elevated IV premium on profitable side
  ```

  **Step 3 — Assess remaining threatened side:**
  ```
  - Re-evaluate threatened_delta after reduction
  - If delta still >= 0.55 → schedule force_check in 1h (monitor closely)
  - If delta < 0.55 → normal cadence resumes
  - Do NOT immediately roll threatened side at delta >= 0.55 (too risky, need assessment)
  ```

---

## 9) Monitor Architecture — Hybrid Cadence (Scheduled + Real-Time)

**MMMX uses two independent monitoring threads running in parallel.** A 24h heartbeat alone cannot detect a flash crash — BTC can drop 7% in 90 seconds. The scheduled heartbeat handles slow drift (delta, IV over days); the premium listener handles intraday shocks (within seconds).

```
┌─────────────────────────────────────────────────────────────┐
│ MMMX MONITORING (Two Parallel Threads)                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ THREAD 1: Scheduled Heartbeat (mmmx_monitor.py)            │
│ • Every 24h (or 1–4h adaptive, or 1h post-trigger)        │
│ • Full beat: fetch all data, evaluate all 10 triggers      │
│ • Execute roll / reduce / close if needed                  │
│ • Update session state                                     │
│                                                             │
│ THREAD 2: Real-Time Premium Listener (mmmx_premium_listener)│
│ • Continuous — data-driven (0.5–1s per WebSocket update)   │
│ • Watches live bid/ask on active CE and PE strikes         │
│ • Checks 4 Tier-0 circuit breakers                        │
│ • If ANY fire → emergency close_all immediately            │
│   (does NOT wait for next scheduled beat)                  │
│                                                             │
│ MUTUAL EXCLUSION:                                           │
│ • Listener fires → signals monitor to stop; closes all    │
│ • Monitor closes all → signals listener to stop           │
│ • Only one actor closes positions; no double-execution     │
└─────────────────────────────────────────────────────────────┘
```

---

### 9a) Scheduled Heartbeat (`mmmx_monitor.py`)

#### Cadence

- Base beat interval: `adjustment_interval_hours × 3600` seconds (default **3600s = 1 hour**)
- The 1-hour cadence is intentional and critical (G29): within 1 hour, a market move either retraces (noise — skip deployment) or holds/continues (confirmed — deploy next tranche)
- No adaptive speedup needed beyond CB wakeup (listener handles intraday emergencies)
- Post-CB wakeup: run beat immediately, then resume 1h schedule
- Stop scheduling when `PAUSED`, `STOPPED`, or `COMPLETE`

#### Generation Guard (G5 — CRITICAL)

**This is a direct lesson from MMM's P0 stale monitor incident (CLAUDE.md §4).**

Each MMMMonitor instance gets a `_my_generation` counter (incremented in registry on each `start_mmmx_monitor` call). At three points in the loop:

1. **`_run_loop` top-of-cycle**: Load fresh session from storage, check `stored_gen > self._my_generation`. If stale: `_running = False`, emit safety event, send Telegram, break.

2. **`_save_session()` return value**: Returns `True` on success, `False` if generation check fails. Caller must check and abort if `False`.

3. **Pre-action check**: Before any exchange order, re-verify generation. If stale: abort action, no state mutation.

### P&L Incomplete Guard (G26)

If > 50% of position premium fetches fail in a single beat:
- Set `_pnl_calculation_incomplete = True`
- Skip trigger evaluation (stale data → wrong triggers)
- Emit `mmmx_safety` event with `type='calculation_incomplete'`
- Still schedule next beat

### Health Grading (G16, G25)

Track per beat:
- `beat_duration_ms`
- `data_fetch_success_rate`
- `last_successful_beat`
- `consecutive_failures`

Grade: A (all green) → F (5+ consecutive failures). Expose via API and WebSocket.

#### Beat Flow

```
1. Circuit breaker check — if OPEN, skip to fast-fail path
2. Generation check — if stale monitor: stop, Telegram, break
3. Fetch live data (premiums, deltas, spot, DVOL via patience_iv, DTE, IV rank)
   Refresh available-strikes cache for ATM shield strike selection
4. Run safety checks (mmmx_safety.py)
5. Update P&L for ALL positions (tranches + atm_recovery_positions) + portfolio delta + IV change
   If _pnl_calculation_incomplete → skip to step 11
6. Hard stop check — if total_pnl <= -hard_stop_usd → close_all, COMPLETE, return
7. DTE check — if current_dte <= close_at_dte → close_all, COMPLETE, return
8. ATM Shield check (mmmx_atm_shield.py) — per tranche, per side
   If any position remaining_otm < atm_protect_threshold:
     execute_atm_shield() → reposition + recovery lots
     shield_fired = True
     skip step 9 this beat
9. Deployment check (skipped if shield_fired)
   check_tranche_deploy_conditions() — OR logic (spot_move OR iv_delta)
   If conditions met: execute_tranche_deploy()
   Recompute hard_stop_usd after deployment
10. Evaluate remaining Tier-1 triggers (mmmx_trigger.py)
    (NEAR_ITM, IV_SPIKE, SIDE_LOSS, PORTFOLIO_DELTA, DELTA_DRIFT, PROFIT_TARGET)
11. Save session + emit WebSocket events (mmmx_beat_update)
12. Send Telegram if any action taken
13. Schedule next beat
```

#### Public Monitor APIs

- `start_mmmx_monitor(session_id)` — creates MMMXMonitor + MMMXPremiumListener, stores in `_mmmx_monitors` dict
- `stop_mmmx_monitor(session_id)` — stops both threads, waits for join(15s)
- `pause_mmmx_monitor(session_id)` — pauses heartbeat; premium listener stays ACTIVE (still guards)
- `resume_mmmx_monitor(session_id)`
- `get_mmmx_monitor(session_id)`
- `get_all_mmmx_monitors()` — for watchdog
- `force_mmmx_check(session_id)` — immediate beat outside schedule

#### Monitor Registry (Isolation)

```python
# mmmx_monitor.py — module-level, completely separate from MMM's _monitors dict
_mmmx_monitors: Dict[str, 'MMMXMonitorEntry'] = {}
_mmmx_monitors_lock = threading.Lock()

# Each entry holds both threads
@dataclass
class MMMXMonitorEntry:
    monitor: MMMXMonitor
    listener: MMMXPremiumListener
    monitor_thread: threading.Thread
    listener_thread: threading.Thread
```

---

### 9b) Real-Time Premium Listener (`mmmx_premium_listener.py` — NEW G27)

**This is the intraday safety net.** It runs continuously while the session is RUNNING and reacts within 1 second to flash crashes, IV explosions, and delta blowouts that the 24h heartbeat would miss.

#### What It Watches

Subscribes to live bid/ask WebSocket feed on exactly two symbols:
- Active CE strike (e.g., `C-BTC-75000-010526`)
- Active PE strike (e.g., `P-BTC-60000-010526`)

Updates the session's `_live_ce_premium` and `_live_pe_premium` fields on each tick (in-memory only; not persisted between beats to avoid write contention with heartbeat thread).

#### Tier-0 Circuit Breaker Triggers

Evaluated on **every premium tick** (not every 24h). First match wins.

**IMPORTANT (G28):** Tier-0 triggers do **NOT blindly close all**. They identify that a significant move has occurred and wake the heartbeat immediately. The heartbeat then applies the delta-gate logic to decide the correct action (reposition / reduce_then_roll / close_all). The only exception is `CB_NEAR_ITM` — a delta ≥ 0.72 is so dangerous it warrants immediate reduction without waiting.

| Trigger | Condition | Action | Rationale |
|---------|-----------|--------|-----------|
| `CB_PREMIUM_JUMP` | Larger of `(ce_now - ce_last_beat)/ce_last_beat` or `(pe_now - pe_last_beat)/pe_last_beat` > threshold | **Force immediate heartbeat** | Premium moved significantly — need full trigger evaluation NOW, not in 24h |
| `CB_DELTA_BLOWOUT` | `max(ce_delta, pe_delta) > blowout_threshold` | **Force immediate heartbeat** | Delta drifted fast — may need reposition |
| `CB_IV_FLASH_SPIKE` | `(dvol_now - entry_dvol) / entry_dvol > 0.50` | **Force immediate heartbeat** | IV doubled — elevated premium opportunity + risk assessment needed |
| `CB_NEAR_ITM` | `threatened_delta >= 0.72` | **Immediate reduce (50% threatened side)** | Delta this high = near ITM, gamma uncontrollable, cannot wait even for heartbeat |

**Note:** `ce_last_beat` / `pe_last_beat` are the premiums recorded at the LAST scheduled heartbeat — not the previous tick. This prevents noise from triggering on normal bid-ask fluctuation.

**"Force immediate heartbeat"** means: set a flag `_force_check = True` on the session and signal the heartbeat thread to run its full beat cycle NOW (interrupt the 24h sleep). The heartbeat then evaluates all Tier-1 triggers using fresh data and applies the delta-gate decision (§7).

#### DTE-Adaptive Thresholds

Tighten as expiry approaches — closer to expiry means higher gamma, less tolerance for delay:

```python
def get_cb_thresholds(dte: float) -> dict:
    if dte > 15:
        return {
            'premium_jump': 0.40,    # 40% jump since last beat → wake heartbeat
            'delta_blowout': 0.45,   # delta > 0.45 → wake heartbeat (up from 0.35 entry target)
            'near_itm': 0.72,        # delta > 0.72 → immediate reduce (no wait)
        }
    elif dte > 7:
        return {
            'premium_jump': 0.25,    # 25% jump (tighter — less time to recover)
            'delta_blowout': 0.40,
            'near_itm': 0.68,        # tighter
        }
    else:
        # Should not happen — DTE_CLOSE heartbeat trigger handles ≤7 DTE
        return {
            'premium_jump': 0.15,
            'delta_blowout': 0.35,
            'near_itm': 0.60,        # very tight
        }
```

#### On Circuit Breaker Fire

```python
async def _on_circuit_breaker_fire(self, trigger_type, details):
    
    if trigger_type == 'CB_NEAR_ITM':
        # Special case: delta >= 0.72 is immediate danger
        # Reduce threatened side NOW without waiting for heartbeat
        # (at this delta, gamma is so high that 60s heartbeat delay costs real money)
        
        # 1. Immediate 50% reduce on threatened side (taker order)
        threatened_side = details['threatened_side']
        await execute_reduce_emergency(executor, session, threatened_side)
        
        # 2. Emit warning
        emit('mmmx_circuit_breaker', {
            'trigger_type': 'CB_NEAR_ITM',
            'action': 'emergency_reduce',
            'details': details,
        })
        
        # 3. Send Telegram — CRITICAL
        send_telegram(f"🚨 MMMX NEAR-ITM ALERT\n"
                      f"Session {session_id}: {threatened_side} delta {details['delta']:.2f}\n"
                      f"Emergency reduce executed (50%)\n"
                      f"Heartbeat forced for full assessment")
        
        # 4. ALSO force heartbeat for complete reassessment
        session['_force_check'] = True
        self._wake_heartbeat()  # Signal heartbeat thread to run NOW

    else:
        # CB_PREMIUM_JUMP, CB_DELTA_BLOWOUT, CB_IV_FLASH_SPIKE
        # These wake the heartbeat which decides the correct action
        
        # 1. Emit event so dashboard shows alert
        emit('mmmx_circuit_breaker', {
            'trigger_type': trigger_type,
            'action': 'force_heartbeat',
            'details': details,
        })
        
        # 2. Send Telegram
        send_telegram(f"⚠️ MMMX CIRCUIT BREAKER\n"
                      f"Session {session_id}: {trigger_type}\n"
                      f"Forcing immediate assessment...\n"
                      f"{details}")
        
        # 3. Force heartbeat to run immediately
        session['_force_check'] = True
        self._wake_heartbeat()
        # Heartbeat will then evaluate full trigger priority
        # and decide: reposition / reduce_then_roll / close_all
        # based on delta gate (§7)
```

#### Coordination with Heartbeat Thread

Two session state flags coordinate the threads:

- `_force_check`: Set by listener when CB fires → heartbeat wakes up and runs full beat immediately
- `_cb_reducing`: Set by listener only during `CB_NEAR_ITM` emergency reduce → heartbeat waits for reduce to complete before acting

```python
# Heartbeat run loop
while self._running:
    if session.get('_force_check'):
        # CB fired — run full beat NOW regardless of schedule
        session['_force_check'] = False
        await self._run_beat()
    elif time_for_next_scheduled_beat():
        await self._run_beat()
    else:
        sleep(CHECK_INTERVAL)  # short sleep (e.g. 5s), re-check flags

# Within _run_beat:
if session.get('_cb_reducing'):
    # CB_NEAR_ITM emergency reduce in progress
    # Wait for it to complete (max 90s) before acting
    wait_for_cb_reduce_complete()
```

**Result:** No double-execution. Listener wakes heartbeat; heartbeat makes smart decisions.

#### What the Listener Does NOT Do

- Does NOT roll or reduce — only closes all (emergency action)
- Does NOT evaluate the 10 scheduled triggers (those belong to the heartbeat)
- Does NOT update session P&L or portfolio delta (heartbeat owns state)
- Does NOT write to the database during close — heartbeat writes final state on next beat (or close_all writes it)

#### New Session State Fields

```python
# Added to session dict for premium listener
'_live_ce_premium': None,        # Updated each tick by listener
'_live_pe_premium': None,        # Updated each tick by listener
'_ce_premium_last_beat': None,   # Set at end of each scheduled beat
'_pe_premium_last_beat': None,   # Set at end of each scheduled beat
'_cb_closing': False,            # Mutual exclusion flag
'_cb_fired': None,               # Which circuit breaker fired (for logging)
```

#### Pause Behavior

When session is PAUSED (operator action):
- Heartbeat thread stops scheduling
- **Premium listener continues running** — a PAUSED session still has open positions that need protection
- Only when session is `STOPPED` or `COMPLETE` does the listener stop

---

### 9c) Trigger Priority: Tier-0 + Tier-1 Combined

Full trigger evaluation order across both threads:

| Tier | # | Trigger | Thread | Cadence | Action |
|------|---|---------|--------|---------|--------|
| **0** | - | `CB_PREMIUM_JUMP` | Listener | ~1s | **Force immediate heartbeat** |
| **0** | - | `CB_DELTA_BLOWOUT` | Listener | ~1s | **Force immediate heartbeat** |
| **0** | - | `CB_IV_FLASH_SPIKE` | Listener | ~1s | **Force immediate heartbeat** |
| **0** | - | `CB_NEAR_ITM` | Listener | ~1s | **Immediate 50% reduce** + force heartbeat |
| **1** | 1 | `DTE_CLOSE` | Heartbeat | scheduled | close_all |
| **1** | 2 | `IV_CATASTROPHE` | Heartbeat | scheduled | close_all (only if threatened_delta ≥ 0.70) |
| **1** | 3 | `MAX_LOSS` | Heartbeat | scheduled | close_all |
| **1** | 4 | `NEAR_ITM` | Heartbeat | scheduled | reduce_then_roll |
| **1** | 5 | `IV_SPIKE` | Heartbeat | scheduled | reposition (if delta 0.35–0.69) |
| **1** | 6 | `DIRECTIONAL_REPOSITION` | Heartbeat | scheduled | reposition (roll both sides) |
| **1** | 7 | `PROFIT_TARGET` | Heartbeat | scheduled | close_all |
| **1** | 8 | `SIDE_LOSS_CE` | Heartbeat | scheduled | reduce CE |
| **1** | 9 | `SIDE_LOSS_PE` | Heartbeat | scheduled | reduce PE |
| **1** | 10 | `PORTFOLIO_DELTA` | Heartbeat | scheduled | roll dominant |
| **1** | 11 | `DELTA_DRIFT_CE` | Heartbeat | scheduled | roll CE |
| **1** | 12 | `DELTA_DRIFT_PE` | Heartbeat | scheduled | roll PE |

**"Scheduled"** = runs at 24h interval OR immediately when woken by Tier-0 CB. Tier-0 never closes the session (except CB_NEAR_ITM which reduces, not closes). The heartbeat makes all smart decisions using the delta gate (§7).

---

## 10) Initializer Contract

`mmmx_initializer.py` must implement:

### Preconditions
- Spot price available (from exchange)
- DVOL available (from `patience_iv` service — G12)
- IV rank computed from DVOL history (minimum 30 data points)
- Expiry parsed and DTE computed

### Entry Gates
- DTE between `entry_dte_min` and `entry_dte_max`
- IV rank >= `entry_iv_rank_min`
- **Margin check (G6):** current margin utilization < 80%

### Strike Selection
1. Compute sigma-based target strikes via `compute_sigma_based_strikes()`
2. Scan options chain via `OptionsChainService` (G11) for available strikes near targets
3. Run `validate_liquidity()` on candidate strikes
4. Select best liquid strike closest to sigma target

### Entry Order Flow
1. Sell CE via `mmmx_executor.smart_execute()`
2. Sell PE via `mmmx_executor.smart_execute()`
3. **If PE fails after CE success (G13):**
   - Set `_naked_side = 'CE'`, `_naked_since = now()`
   - Set session status = `PARTIAL_ENTRY`
   - Emit `mmmx_safety` with `type='naked_position'`
   - Send Telegram: "MMMX ALERT: Naked CE position — PE entry failed"
   - **Do NOT auto-retry.** Operator must decide:
     - Resume entry (retry PE) via API endpoint
     - Close CE and abort session
   - Monitor continues running in `PARTIAL_ENTRY` — evaluates triggers for CE side only

4. On full success: write entry state + premium totals + `RUNNING` status + emit `mmmx_entry`

### Exchange Reconciliation on Restart (G9)

`mmmx_initializer.py` must also provide:

```python
async def reconcile_with_exchange(session):
    """
    After backend restart, verify MMMX session positions match exchange.
    
    1. Fetch open short BTC options from exchange
    2. Match against session position list by symbol
    3. If lots mismatch: log WARNING, update session to match exchange (exchange is truth)
    4. If position missing on exchange: mark as CLOSED in session
    5. If extra position on exchange not in session: log WARNING (do NOT auto-adopt)
    """
```

---

## 11) Safety & Param Validation

### `mmmx_safety.py` (minimal v1)

Run at start of each beat:
- Skip checks unless `RUNNING` or `PARTIAL_ENTRY`
- Detect both sides unexpectedly closed while RUNNING → `COMPLETE`
- Max adjustments gate (default 10 monthly) → `PAUSED` + Telegram
- DTE sanity (expiry passed, DTE < 0) → immediate close_all
- **Generation integrity check** (G5): verify monitor generation matches session

### `mmmx_config.py`

Parameter validation rules:

| Parameter | Type | Min | Max | Hot Reload | Special |
|-----------|------|-----|-----|-----------|---------|
| `entry_dte_min` | int | 5 | 90 | No | Must be < `entry_dte_max` |
| `entry_dte_max` | int | 10 | 120 | No | Must be > `entry_dte_min` |
| `entry_iv_rank_min` | int | 0 | 100 | No | |
| `total_budget_lots` | int | 10 | 1000 | No | Total max lots per side for session |
| `tranche_pct` | int | 5 | 50 | No | % of budget per tranche (e.g. 10 = 10%) |
| `otm_distance_pct` | float | 5.0 | 30.0 | **Yes** | OTM % from current ATM for new strikes |
| `tranche_deploy_move_pct` | float | 1.0 | 10.0 | **Yes** | Min spot move % to trigger next tranche |
| `tranche_deploy_iv_delta` | int | 1 | 30 | **Yes** | Min IV rank increase since last tranche |
| `hard_stop_multiplier` | float | 1.0 | 5.0 | **Yes** | hard_stop = this × total_premium_collected |
| `adjustment_interval_hours` | int | 1 | 24 | **Yes** | Base heartbeat (default 1h) |
| `delta_drift_threshold` | float | 0.05 | 1.0 | **Yes** | Tranche position delta drift alert |
| `portfolio_delta_threshold` | float | 0.01 | 0.50 | **Yes** | |
| `near_itm_delta` | float | 0.45 | 0.80 | **Yes** | Reduce tranche when delta hits this |
| `emergency_delta` | float | 0.60 | 0.95 | **Yes** | Close tranche when delta hits this |
| `side_loss_threshold_pct` | int | 50 | 1000 | **Yes** | |
| `iv_spike_threshold_pct` | int | 10 | 200 | **Yes** | |
| `iv_catastrophe_pct` | int | 30 | 300 | **Yes** | Must be > `iv_spike_threshold_pct` |
| `close_at_dte` | int | **7** | 45 | **Yes** | **Hard minimum 7** |
| `profit_target_pct` | int | 10 | 100 | **Yes** | |
| `profit_target_enabled` | bool | — | — | **Yes** | |
| `max_adjustments` | int | 1 | 100 | **Yes** | Across all tranches combined |
| `alert_on_adjustment` | bool | — | — | **Yes** | |

Hard reject rules:
- `close_at_dte < 7` → gamma-risk message
- `entry_dte_min >= entry_dte_max`
- `iv_catastrophe_pct <= iv_spike_threshold_pct`
- `emergency_delta <= near_itm_delta`
- `tranche_pct > 50` → "Cannot deploy more than 50% in a single tranche"
- `hard_stop_multiplier < 1.0` → "Hard stop cannot be less than premium collected"

Hard reject rules:
- `close_at_dte < 7` → explicit gamma-risk message: "MMMX requires close_at_dte >= 7 to avoid final-week gamma risk. This is a non-negotiable safety rule."
- `entry_dte_min >= entry_dte_max` → "entry_dte_min must be less than entry_dte_max"
- `iv_catastrophe_pct <= iv_spike_threshold_pct` → "iv_catastrophe_pct must exceed iv_spike_threshold_pct"

---

## 12) Circuit Breaker (G2)

`mmmx_circuit_breaker.py` — same proven 3-state model as MMM:

| State | Behavior |
|-------|----------|
| CLOSED (nominal) | All API calls pass through |
| OPEN (tripped) | Fast-fail; allow safety-only operations (close-all still attempts) |
| HALF_OPEN (probe) | One trial request; success → CLOSED; fail → OPEN |

- CLOSED → OPEN after 3 consecutive API failures
- OPEN → HALF_OPEN after 60s (longer than MMM's 30s — monthly cadence is slower)
- Never terminates the session — isolates, waits, self-heals
- Close-all from CRITICAL triggers bypasses circuit breaker (emergency path)

---

## 13) Watchdog (G4)

`mmmx_watchdog.py` — supervisor thread:

- Polls every 300s (5 min)
- For each session in `_mmmx_monitors`:
  - **Monitor thread check:**
    - If monitor thread is dead and session status is `RUNNING` or `PAUSED`:
      - Log CRITICAL
      - Send Telegram: "MMMX heartbeat monitor died for session {id}"
      - Attempt restart with new generation
    - If `last_beat_at` is older than `2 × adjustment_interval_hours`:
      - Log WARNING: "MMMX heartbeat appears stuck"
      - Send Telegram
  - **Premium listener thread check (NEW G27):**
    - If listener thread is dead and session status is `RUNNING` or `PAUSED`:
      - Log CRITICAL
      - Send Telegram: "MMMX premium listener died for session {id} — INTRADAY PROTECTION OFFLINE"
      - Attempt restart of listener thread with fresh WebSocket subscription
    - If `_live_ce_premium` or `_live_pe_premium` has not updated for > 120s:
      - Log WARNING: "MMMX premium listener appears stale"
      - Send Telegram

---

## 14) API Surface (`mmmx_api.py`)

Blueprint: `/api/mmmx`

### Session Lifecycle

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/session/create` | Create new MMMX session |
| `GET` | `/sessions` | List all sessions |
| `GET` | `/session/<id>` | Get full session details |
| `DELETE` | `/session/<id>` | Delete (IDLE/STOPPED/COMPLETE only) |

### Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/session/<id>/init` | Initialize entry (strike selection + orders) |
| `POST` | `/session/<id>/start` | Start monitor |
| `POST` | `/session/<id>/pause` | Pause monitor |
| `POST` | `/session/<id>/resume` | Resume monitor |
| `POST` | `/session/<id>/stop` | Stop monitor |
| `POST` | `/session/<id>/close-all` | Manual close all positions |
| `POST` | `/session/<id>/force-check` | Force immediate beat |
| `POST` | `/session/<id>/retry-entry` | Retry failed PE/CE entry (G13 recovery) |

### Telemetry

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/session/<id>/status` | Current status + health grade |
| `GET` | `/session/<id>/adjustments` | Adjustment history |
| `GET` | `/session/<id>/pnl` | P&L breakdown |

### Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PATCH` | `/session/<id>/params` | Hot-reload parameters with validation |

### Utility

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/expiries` | Available BTC expiry dates |
| `POST` | `/preview-entry` | Preview sigma-based strikes without placing orders |
| `GET` | `/iv-rank` | Current IV rank |
| `GET` | `/health` | MMMX module health |

Response/error pattern matches existing MMM API style (`{success, data/error}`), fully namespaced to MMMX.

---

## 15) Frontend MVP Dashboard

`MMMXDashboard.js` priority panel order:

1. **Status banner** — status chip, expiry, DTE with color bands (green > 14, yellow 7–14, red ≤ 7), adjustment count, entry date, health grade
2. **CE/PE position cards** — strike, lots, entry vs current premium/delta, unrealized P&L, roll count, origin tag
3. **Risk gauges:**
   - IV risk (current DVOL change % vs entry, spike/catastrophe thresholds marked)
   - Portfolio delta risk (gauge with threshold line)
   - Loss risk vs max session loss (bar chart)
4. **P&L summary** — premium collected, unrealized, realized, total, peak, drawdown from peak
5. **Adjustment history table** — timestamp, trigger type, action, side, details
6. **Controls:** Force Check / Pause / Resume / Stop / Close All (with confirmation modal)

**Naked position warning (G13):** If `_naked_side` is set, show a prominent red banner: "WARNING: Naked {side} position since {timestamp}. Use Retry Entry or Close All."

WebSocket hook must subscribe only to `mmmx_*` events. Must NOT register any `mmm_*` listeners.

---

## 16) Mandatory Build Order (Execution Plan)

### Phase 1: Foundation (no exchange interaction)
1. `mmmx_constants.py` — LOT_SIZE_BTC, shared constants
2. `mmmx_state.py` — session model, defaults, hot-reload list (including ATM shield fields)
3. `mmmx_config.py` — param rules, validation, `close_at_dte >= 7`, ATM shield params
4. `mmmx_storage.py` — SQLite persistence (`mmmx_sessions.db`)
5. `mmmx_activity.py` — activity log ring buffer
6. `mmmx_audit_log.py` — append-only trade event journal
7. `mmmx_param_audit.py` — append-only param-change log (hot-reload audit) **[Gap G14 — new]**
8. `mmmx_websocket.py` — all `mmmx_*` event emitters
9. `mmmx_telegram.py` — alert integration (dedup pattern from `mmm_telegram.py`)

### Phase 2: Core logic
10. `mmmx_engine.py` — sigma strikes, P&L, portfolio delta, IV math, greek aggregation
11. `mmmx_trigger.py` — priority-ordered trigger evaluation (OR deploy conditions)
12. `mmmx_safety.py` — pre-beat checks, DTE sanity, generation
13. `mmmx_circuit_breaker.py` — 3-state fault isolation (from `mmm_circuit_breaker.py` pattern)
14. `mmmx_margin_guardian.py` — wraps `MarginGuardian` for MMMX (from `mmm_margin_guardian.py`)

### Phase 3: Execution & orchestration
15. `mmmx_executor.py` — smart execution, dedup, margin pre-check (from `mmm_executor.py` pattern)
16. `mmmx_atm_shield.py` — OTM buffer monitoring, buyback + reposition + recovery lots **[§3.4 — new]**
17. `mmmx_premium_listener.py` — real-time WebSocket listener, Tier-0 circuit breakers
18. `mmmx_initializer.py` — entry gates, chain scan, order flow, reconciliation
19. `mmmx_monitor.py` — heartbeat loop + ATM shield + listener orchestration, generation guard, health grading
20. `mmmx_watchdog.py` — supervisor thread (watches both monitor + listener threads)

### Phase 4: API & registration
21. `mmmx_api.py` — REST endpoints (includes ATM shield status + reserve endpoints)
22. `__init__.py` — blueprint registration, `init_mmmx()`, session restore
23. Register in `app.py` (isolated try/except, AFTER MMM block)

### Phase 5: Frontend
20. `MMMXContext.js` — React context + WS listeners
21. `useMMMXWebSocket.js` — WebSocket hook
22. `mmmxService.js` — API service client
23. `MMMXDashboard.js` — dashboard UI
24. Wire route/nav in `App.js` + `navigationSections.js`
25. `npm run build` (production build)

### Phase 6: Quality
26. Write `README_MMMX.md`
27. Add tests under `tests/`
28. Run isolation verification gate (§17)

---

## 17) Isolation & Safety Verification Gate

Before declaring complete, **ALL** must pass:

### Isolation Checks (automated scan)
- [ ] `grep -r "from.*mmm_" webui/backend/routes/mmmx/ | grep -v mmmx_` → **ZERO matches** (no MMM runtime imports)
- [ ] `grep -r "mmm_sessions\.db" webui/backend/routes/mmmx/` → **ZERO matches**
- [ ] `grep -r "emit.*mmm_[^x]" webui/backend/routes/mmmx/` → **ZERO matches** (no non-MMMX WS events)
- [ ] `grep -r "mmmx_" webui/backend/routes/mmm/` → **ZERO matches** (MMM knows nothing about MMMX)
- [ ] `grep -r "_monitors\b" webui/backend/routes/mmmx/` → only `_mmmx_monitors` (not MMM's `_monitors`)

### Functional Checks
- [ ] Param validation test: `close_at_dte: 5` → rejected with gamma-risk message
- [ ] Param validation test: `close_at_dte: 7` → accepted
- [ ] Param validation test: `entry_dte_min >= entry_dte_max` → rejected
- [ ] Param validation test: `iv_catastrophe_pct <= iv_spike_threshold_pct` → rejected
- [ ] Backend files pass `python3 -c "import py_compile; py_compile.compile('file.py', doraise=True)"`
- [ ] `curl http://localhost:5555/api/mmmx/health` → 200 OK
- [ ] `curl http://localhost:5555/api/mmm/health` → 200 OK (unchanged)

### Concurrency Checks
- [ ] MMM session RUNNING → start MMMX session → both heartbeats fire independently
- [ ] MMMX uses `mmmx_sessions.db`, MMM uses `mmm_sessions.db` — verified via `lsof` or sqlite3
- [ ] WebSocket: MMM dashboard receives only `mmm_*` events; MMMX dashboard receives only `mmmx_*` events
- [ ] Premium listener fires CB trigger → heartbeat sees `_cb_closing=True` and skips — no double-close
- [ ] Session PAUSED → premium listener still running (open positions still protected)
- [ ] Session COMPLETE → both monitor thread and listener thread stopped

### Regression Check
- [ ] Existing sealed tests still pass: `python3 -m pytest webui/ bot/ -m sealed -v` → 0 failures
- [ ] MMM session create/start/stop cycle works exactly as before

---

## 18) Session Restore on Backend Restart (G3 — CRITICAL)

**Monthly positions survive for weeks. The backend WILL restart (launchd KeepAlive, deploys, crashes).**

`init_mmmx()` in `__init__.py` must:

1. Load all sessions from `mmmx_sessions.db`
2. For each session with status `RUNNING`, `PAUSED`, `PARTIAL_ENTRY`, or `EXITING`:
   a. Log: `[MMMX] Restoring monitor for session {id} (status={status})`
   b. Run `reconcile_with_exchange(session)` to sync with exchange state
   c. Start monitor with new generation (incremented from stored generation)
3. For `PARTIAL_ENTRY` sessions: do NOT auto-retry the missing leg — just restore monitor so operator can see the state and decide

**Registration in `app.py`:**
```python
# Register MMMX blueprint (Monthly BTC Options — 20-45 DTE)
try:
    from webui.backend.routes.mmmx import mmmx_bp, init_mmmx, init_websocket as init_mmmx_websocket
    app.register_blueprint(mmmx_bp)
    print(f"Registered mmmx blueprint (Monthly BTC Options)")
    init_mmmx_websocket(socketio)
    init_mmmx()
    print(f"MMMX initialized and sessions restored")
except Exception as e:
    print(f"Could not register mmmx blueprint: {e}")
    log.warning(f"MMMX routes not available: {e}")
```

This block must be placed AFTER the MMM block and AFTER the IC block, so MMMX failure never prevents MMM from loading.

---

## 19) Shared Infrastructure Usage (G11, G12, G17)

### Options Chain Service (G11)

MMMX uses `OptionsChainService` for:
- Available expiries
- Strike scanning (chain data)
- Bid/ask quotes for liquidity validation

Usage: lazy-load in `mmmx_initializer.py`, same pattern as MMM. **No modification to the service.**

### DVOL / IV Rank (G12)

MMMX gets DVOL from `webui/backend/services/patience_iv.py`:
- `PatienceIVService.get_current_dvol()` → current DVOL value
- DVOL history for IV rank: query from `patience_iv`'s SQLite store or from `bot/volatility/iv_rv_tracker.py`

If `patience_iv` service is not running, `compute_iv_rank()` returns `None` and entry gate blocks initialization (IV rank required for entry).

### Cross-System Margin (G17)

MMM and MMMX share one exchange account. Margin utilization includes BOTH systems' positions.

MMMX's margin check in the executor naturally accounts for this because it queries the exchange's real margin, which includes all positions. No special cross-system logic needed — the exchange is the single source of truth.

However, the **operator must understand** that running both MMM and MMMX simultaneously increases total margin usage. This must be documented in README_MMMX.md.

---

## 20) Telegram Alert Taxonomy (G7)

`mmmx_telegram.py` must send alerts for:

| Event | Severity | Message Template |
|-------|----------|-----------------|
| Trigger fired | INFO | `MMMX [{id}]: {trigger_type} fired — {action} ({reason})` |
| **Tranche deployed** | INFO | `MMMX [{id}]: TRANCHE {N}/{total} deployed — CE @ {ce_strike}, PE @ {pe_strike}. +${premium}. Hard stop: ${hard_stop}. Deployed: {pct}%` |
| **Hard stop hit** | CRITICAL | `MMMX [{id}]: HARD STOP — Total P&L ${pnl} hit ${hard_stop} limit ({multiplier}× ${premium_collected} collected). Closing all {n} tranches` |
| **Tranche partial fill** | CRITICAL | `MMMX [{id}]: TRANCHE {N} PARTIAL — CE filled, PE failed. Naked CE. Manual action needed` |
| Tranche reduced | HIGH | `MMMX [{id}]: TRANCHE {N} REDUCED — {side} 50% buyback (delta {delta}). Remaining: {lots} lots` |
| Close-all executed | HIGH | `MMMX [{id}]: All {n} tranches closed — {trigger_type}` |
| Naked position | CRITICAL | `MMMX [{id}]: NAKED {side} — {other_side} entry failed` |
| Reposition half-fail | CRITICAL | `MMMX [{id}]: REPOSITION PAUSED — {step} failed. Session paused, manual action needed` |
| Roll half-fail | CRITICAL | `MMMX [{id}]: Roll PAUSED — buy-back OK but sell-new failed` |
| Monitor died | CRITICAL | `MMMX [{id}]: Monitor thread died — watchdog attempting restart` |
| Stale monitor | CRITICAL | `MMMX [{id}]: Stale monitor gen={gen} detected — shutting down` |
| Circuit breaker OPEN | HIGH | `MMMX [{id}]: Circuit breaker tripped — API failures` |
| **CB_PREMIUM_JUMP** | HIGH | `MMMX [{id}]: CB — {side} premium jumped {pct}%. Forcing immediate assessment (delta={delta})` |
| **CB_DELTA_BLOWOUT** | HIGH | `MMMX [{id}]: CB — Delta blowout {side} ({delta:.2f}). Forcing immediate assessment` |
| **CB_IV_FLASH_SPIKE** | HIGH | `MMMX [{id}]: CB — IV flash spike DVOL {entry}% → {now}%. High IV = opportunity, assessing...` |
| **CB_NEAR_ITM** | CRITICAL | `MMMX [{id}]: CB NEAR-ITM — {threatened_side} delta {delta:.2f} (threshold {threshold}). Emergency 50% reduce executed` |
| Premium listener offline | CRITICAL | `MMMX [{id}]: PREMIUM LISTENER DIED — intraday protection offline, watchdog restarting` |
| Session COMPLETE | INFO | `MMMX [{id}]: Session complete — total P&L: ${pnl}` |

---

## 21) README_MMMX.md Requirements

The implementation phase must include:

1. What MMMX is and how it differs from MMM
2. Entry criteria (DTE + IV rank + margin check)
3. Trigger definitions (delta drift, IV spike/catastrophe, loss, DTE close)
4. Action semantics (roll vs reduce vs close-all)
5. Why `close_at_dte >= 7` is mandatory (gamma risk explanation)
6. Parameter reference table with types, ranges, hot-reload status
7. Force Check usage guidance
8. Naked-position incident response (PE failed after CE filled — what to do)
9. **Session restore behavior** — what happens on backend restart
10. **Cross-system margin warning** — running MMM + MMMX simultaneously
11. **Hybrid monitoring model** — how the 24h heartbeat and real-time listener work together
12. **Tier-0 circuit breakers** — what triggers them, thresholds by DTE, why they use emergency (taker) orders
13. Circuit breaker (API fault isolation) behavior
14. Watchdog behavior (covers both threads)
15. Telegram alert reference

---

## 22) Definition of Done

MMMX is considered ready for MVP when:

- [ ] All 23 backend files + 4 frontend files created and compile-clean
- [ ] Isolation architecture verified (§17 — all checks pass)
- [ ] Monthly trigger/action model implemented exactly as specified
- [ ] Tranche deployment model working: 10% per tranche, OTM% hot-reloadable, old positions never closed on moves
- [ ] `DEPLOY_TRANCHE` trigger fires correctly on OR logic (move% alone OR iv_delta alone is sufficient)
- [ ] ATM Shield fires when remaining OTM < `atm_protect_threshold` (default 5%)
- [ ] ATM Shield buyback: 10 smart attempts × 30s → emergency_execute fallback
- [ ] ATM Shield strike selection uses live exchange API (not hardcoded step)
- [ ] ATM Shield recovery lots: 30% CE + 70% PE split from 30-lot reserve
- [ ] ATM Shield: deployment skipped in same beat as shield
- [ ] ATM Shield reserve exhaustion: reposition still executes, recovery lots skipped
- [ ] `atm_shield_max_shifts` is hot-reloadable; Telegram tells operator to raise it when exhausted
- [ ] Dynamic hard stop recalculates after every tranche (= 2× premium collected)
- [ ] 1-hour heartbeat base cadence correctly evaluates deployment conditions
- [ ] Delta gate logic drives defensive actions (reduce worst tranche / close_all by delta threshold)
- [ ] CB wakes heartbeat; only CB_NEAR_ITM executes immediate emergency reduce
- [ ] Close_all reserved for: DTE_CLOSE, HARD_STOP, threatened_delta ≥ 0.70, IV_CATASTROPHE at ≥ 0.70 delta
- [ ] Hard DTE safety rule enforced in config validation AND runtime triggering
- [ ] Smart execution with dedup, margin pre-check, and circuit breaker
- [ ] Real-time premium listener running alongside heartbeat (intraday protection)
- [ ] Tier-0 circuit breaker closes within 1-2 seconds of threshold breach
- [ ] Session PAUSED → listener still active; session COMPLETE → listener stopped
- [ ] Session restore on backend restart with exchange reconciliation
- [ ] Generation guard prevents stale monitor trading
- [ ] Watchdog detects and restarts dead monitors
- [ ] Telegram alerts for all critical events
- [ ] Frontend MVP reflects monthly risk model (not intraday assumptions)
- [ ] Concurrent MMM + MMMX operation is clean and independent
- [ ] Sealed tests unchanged, MMM regression-free
- [ ] README_MMMX.md complete

---

## 23) MMM Feature Reuse Matrix

MMMX does not reinvent infrastructure that already works in MMM. The following MMM modules are **confirmed available and verified** against the live codebase. MMMX either reuses directly (via its own thin adapter/instance) or copies the pattern into its own module.

> **Isolation rule is unchanged:** MMMX never `import`s from `mmm_*` at runtime. Where pattern reuse is listed, it means the MMMX module is authored using the MMM source as the reference — same logic, separate file.

### Direct Reuse (same class, new instance)

| MMM Module | Class / Function | What MMMX Uses | MMMX Module |
|---|---|---|---|
| `mmm_margin_guardian.py` | `MarginGuardian`, `evaluate_margin_tier()`, `TIER_GREEN/YELLOW/ORANGE/RED/CRITICAL` | Full 5-tier margin management. `MarginGuardian(mmmx_session_id)` instantiated per session. | `mmmx_margin_guardian.py` — thin wrapper |
| `mmm_circuit_breaker.py` | `CircuitBreaker`, `CircuitState` | 3-state CLOSED/OPEN/HALF-OPEN API fault isolation. Same failure threshold + probe logic. | `mmmx_circuit_breaker.py` — copied pattern |
| `mmm_fill_sync.py` | `FillSyncer` | Fill-sync cursor (`_fill_sync_cursor_us`), position reconciliation, P&L correction vs estimated. | `mmmx_fill_sync.py` — copied pattern |
| `mmm_audit_reconciler.py` | `reconcile_session()` | State-vs-exchange reconciliation after restart. | Part of `mmmx_initializer.py` |
| `mmm_exit_all.py` | `run_exit_all()`, `_run_exit_rounds()`, `_verify_exchange_cleared()` | Kill switch / hard stop execution: multi-round close with fallback, post-close verification. | `mmmx_exit_all.py` — copied pattern |
| `mmm_telegram.py` | `_should_send(key)`, `_send_async()`, severity-keyed alert functions | Dedup gate, alert severity levels, async send with key-based deduplication. | `mmmx_telegram.py` — same pattern, MMMX-specific alert functions |
| `mmm_executor.py` | `smart_execute()`, `emergency_execute()` | Mid-price limit order + 30s reprice loop (10 attempts for MMMX vs 4 for MMM due to monthly liquidity). `emergency_execute()` for last-resort IOC fill. | `mmmx_executor.py` — copied pattern, `max_reprice_attempts=10` default |
| `mmm_safety.py` | `check_trailing_stop()`, `update_peak_pnl()` | High-water mark + trailing stop logic. Peak P&L tracking for drawdown computation. | Part of `mmmx_safety.py` |
| `mmm_audit_log.py` | `MMMTradeAuditLog`, SQLite writer thread | Append-only trade event journal (fills, closes, orders). Background writer + idempotency key. | `mmmx_audit_log.py` — copied pattern |

### Pattern Reuse (logic copied, adapted for monthly model)

| MMM Module | Pattern | MMMX Adaptation |
|---|---|---|
| `mmm_close_at_5.py` | `_being_closed` / `_being_closed_at` in-flight guard (180s TTL), external-close check on failure, `_estimated_pnl_booked` stamp, `_pending_close_verification` 3-beat grace window, partial fill handling | Copied into `mmmx_atm_shield.py` buyback step. Same guards, same FillSyncer anti-double-booking stamp. |
| `mmm_state.py` | `strategy_status` FSM: `IDLE → RUNNING → PAUSED → STOPPED → COMPLETE`. Position lifecycle: `active → repositioned → closed`. | `mmmx_state.py` — same status names + adds `DEPLOYING`, `WINDING_DOWN`, `PARTIAL_ENTRY`. |
| `mmm_gamma.py` | `compute_gamma_data()`, `GammaData` TypedDict, `portfolio_gamma` aggregation loop | `mmmx_engine.py` — extend to also aggregate `portfolio_vega` and `portfolio_theta` per position (vega/theta are available from Delta greeks feed, just not summed in MMM). |
| `mmm_monitor.py` | Generation guard: 3-layer (`_run_loop` top check, `_save_session` return value, pre-action verify). `_my_generation` counter. `start_session_monitor()` thread.join(15s). | `mmmx_monitor.py` — identical 3-layer guard. Lesson from P0 incident documented in CLAUDE.md §4. |
| `mmm_watchdog.py` | Supervisor polling dead threads, restart with new generation, stale `last_beat_at` check | `mmmx_watchdog.py` — extends to also watch the premium listener thread (`_live_ce_premium` freshness). |
| `mmm_breakeven_engine.py` | `BreakevenEngine.compute_breakeven()` — P&L-at-spot scan, breakeven finder, aggression multiplier | Not in MMMX v1. Deferred to v2. |

### Infrastructure Shared (read-only, no modification)

| Module | Usage |
|---|---|
| `bot/api/async_delta_client.py` | REST calls to exchange. Fresh instance per event loop (same rule as MMM). |
| `webui/backend/options_chain/chain_service.py` | Strike scanning, available strikes query. |
| `webui/backend/services/patience_iv.py` | `get_current_dvol()`, DVOL history for IV rank. |
| `bot/api/unified_api_client.py` | Order placement. Lazy-load per executor instance. |

---

## 24) Remaining Gaps Roadmap

These are features identified in the institutional gap analysis that are NOT yet in MMM and must be built new for MMMX — or are genuinely new strategy features specific to the monthly model. Listed in the same Phase order as the implementation plan.

### Phase 0 (Before Code — All Resolved in This Plan)

| Gap | Status | Resolution |
|---|---|---|
| Portfolio Greeks (G1) | ✅ Partial reuse + extension | `mmmx_engine.py` reuses gamma pattern + adds vega/theta aggregation. |
| Formal State Machine (G2) | ✅ Reuse | `strategy_status` from `mmm_state.py` + MMMX-specific additions. |
| Kill Switch (G4) | ✅ Reuse | `mmm_exit_all.py` pattern → `mmmx_exit_all.py`. |
| Alert Rate Limiting (G5) | ✅ Reuse | `mmm_telegram.py` dedup pattern → `mmmx_telegram.py`. |
| Margin Tiers (G6) | ✅ Reuse | `MarginGuardian` class directly via `mmmx_margin_guardian.py`. |

### Phase 1 (With Core Execution)

| Gap | Status | Resolution |
|---|---|---|
| Reconciliation (G3) | ✅ Reuse | `FillSyncer` + `reconcile_session()` pattern in `mmmx_initializer.py`. |
| Liquidity Gate (G11) | ✅ Partial reuse + extension | Observer price-consistency pattern + **add OI check and bid-depth ≥ lots check** in `validate_liquidity()`. |
| Execution Quality Metrics (G10) | ⚠️ Partial reuse | `smart_execute` returns `{fill_price, attempts, total_time}`. **Must add:** per-order `slippage_bps = (fill_price - decision_mid) / decision_mid × 10000`. Append to `session['_execution_metrics']` list. |
| Parameter Audit Log (G14) | ❌ New build | **No equivalent in MMM.** Build `mmmx_param_audit.py` — SQLite writer thread (same pattern as `mmm_audit_log.py`). Every hot-reload write: `{param, old_value, new_value, changed_at, session_id}`. |

### Phase 2 (Strategy Depth)

| Gap | Status | Resolution |
|---|---|---|
| Entry Criteria Expansion (G7) | 🔶 Partial — v1 uses DTE + IV rank only | **Add to v1.5:** term structure check (backwardation block), 7-day RV check (RV > IV = bad setup). Event calendar block deferred to v2. |
| Delta-Targeted Strikes (G8) | 🔶 Optional toggle | Add `strike_selection_mode: 'otm_pct' \| 'delta_target'` param. Default `otm_pct` (simpler, already in plan). Delta-target mode: `find_strike_at_delta(target=0.20)` using live greeks. |
| IV Rank Methodology (G9) | ❌ Undefined — specify now | **Definition locked:** IV rank = percentile of today's DVOL in trailing 365-day daily-close distribution. Window: 252 trading days minimum; if fewer available, rank = None and entry gate blocks. Source: `patience_iv.py` DVOL history. |
| Correlation / Asymmetric Tranches (G13) | 🔶 Deferred to v2 | Monthly tranches deploy symmetric CE+PE for simplicity. v2: if spot has moved directionally, bias new tranche toward selling more of the side with elevated skew. |
| Close-at-Threshold (G16) | 🔶 Deferred to v2 | Individual position close when premium decays to `close_at_threshold` (default $5–$10 for monthly, hot-reloadable). Mirrors MMM `close_at_5` but with higher threshold for monthly premiums. |

### Phase 3 (Hardening)

| Gap | Status | Resolution |
|---|---|---|
| Pin Risk Near Expiry (G12) | 🔶 Partially covered | `close_at_dte=7` is the primary defense. **Add:** within 5 DTE, if any strike is within $500 of spot → flag as PIN_RISK in session state, emit warning, block new deployment. |
| Backtest / Shadow Mode (G15) | ❌ New design | Abstract time/price sources in monitor so the same beat logic runs on replayed ticks. `paper_mode: bool` session param — orders go through `PaperExecutor` that simulates fills at mid with configurable slippage. Deferred post-MVP. |
| Profit Target Scaling (G17) | 🔶 Partial in plan | Plan has `profit_target_enabled` (close all at X%). **Add v2:** scale-out mode: close 50% when 50% collected, keep remaining. |
| Stress Scenario Playbook (G19) | ❌ Document only | Write in `mmmx_brain.md` §9 (not code). Covers: flash crash, IV doubling, exchange offline, stale greeks, empty book. |
| Operator Runbook (G20) | ❌ Document only | Write in `README_MMMX.md`. Per-alert-type: verify → decide → act. |

### Deferred (Post-Launch)

| Gap | Phase |
|---|---|
| Execution TWAP / iceberg slicing for large orders (G17 order-level) | v2 |
| Portfolio net vega hard limit (G1 extension) | v2 |
| Portfolio net delta cap across all positions (G15 extension) | v2 |
| Daily / rolling 24h loss limit (G9 risk extension) | v2 |
| Drawdown from high-water mark secondary stop (G10 extension) | v2 |
| Event calendar awareness (FOMC, CPI, expiry proximity) | v2 |
| IV-RV realized spread tracking (core edge metric) | v2 |
| Concentration risk per strike (`max_lots_per_strike`) | v2 |
| Post-session automatic report (JSON + Telegram summary) | v2 |
| Metrics export (Prometheus / StatsD) | v3 |

---

## Appendix A: Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| MMMX bug affects MMM | Low (isolation) | CRITICAL (real money) | Zero shared state, no MMM imports, isolated try/except |
| Stale monitor places orders | Medium (proven incident) | CRITICAL | 3-layer generation guard (copied from MMM fix) |
| Backend restart loses state | High (weekly restarts) | HIGH | SQLite persistence + auto-restore + reconciliation |
| Naked position unnoticed | Medium | HIGH | Telegram alert + dashboard banner + PARTIAL_ENTRY status |
| API failure during roll | Medium | HIGH | Circuit breaker + PAUSED on half-fail + Telegram |
| Margin blown by both systems | Low | CRITICAL | Executor margin pre-check (exchange is truth) |
| Monitor thread dies silently | Medium | HIGH | Watchdog with 5-min polling + Telegram |
| Premium listener thread dies silently | Medium | CRITICAL | Watchdog watches listener separately; Telegram alert; auto-restart |
| Flash crash undetected (24h gap) | High | CRITICAL | Tier-0 CB wakes heartbeat within 1-2 seconds; CB_NEAR_ITM does emergency reduce immediately |
| CB false positive (noisy market) | Medium | LOW | CB only forces a heartbeat (not a close); false wakeup costs 1 unnecessary beat, no position change |
| Deploy into illiquid strike | Medium | HIGH | `validate_liquidity()` required on both tranche strikes before any sell |
| Tranche partial fill (PE fails after CE) | Medium | CRITICAL | PARTIAL tranche state + Telegram; operator decides to retry PE or close CE |
| Multiple tranches near ATM simultaneously | Low | CRITICAL | Hard stop catches this; 10% tranches limit per-tranche damage; worst-tranche monitoring |
| Over-deployment in sustained trend | Medium | MEDIUM | `tranches_remaining` hard limit; max 100% of budget; margin pre-check blocks if margin tight |
| Hard stop set too low | Low | MEDIUM | `hard_stop_multiplier >= 1.0` enforced; default 2.0 gives 2× headroom |
| IV data unavailable | Low | MEDIUM | Entry gate blocks; running session uses last known + flag |

## Appendix B: What Is NOT in v1 (Deferred)

These features exist in MMM but are explicitly excluded from MMMX v1:

| Feature | MMM Module | Why Deferred |
|---------|-----------|-------------|
| Regime controls (vol/gamma/trend) | `mmm_regime.py` | Monthly cadence makes intraday regime less relevant |
| Perpetual futures hedge | `mmm_perp_hedge.py` | Adds complexity; monthly delta is managed via rolls |
| Profit harvesting (M1) | `mmm_harvester.py` | MMMX has no frozen positions (no strike shift) |
| Lot recycling (M2) | `mmm_recycler.py` | No position cap pressure (small positions) |
| Asymmetry rebalancing (M3) | `mmm_harvester.py` | No accumulated lot imbalance |
| Strike shifting | `mmm_strike_shift.py` | Rolls replace shifts in monthly model |
| Close-at-5 | `mmm_close_at_5.py` | DTE-based exit replaces premium-decay close |
| Wind-down mode | `mmm_wind_down.py` | DTE close rule handles final-week risk |
| ~~ATM Shield~~ | ~~`mmm_atm_shield.py`~~ | **PROMOTED TO CORE (§3.4)** — Required for monthly options where positions survive days/weeks of directional drift. `mmmx_atm_shield.py` implements OTM buffer monitoring + buyback + reposition + 30/70 recovery lot split. |
| Adopt mode | `mmm_adopter.py` | Can add in v2 if needed |
| Observer pattern | `mmm_observer.py` | Deferred; audit_log covers MVP needs |
| Analytics/aggregator | `mmm_analytics_*.py` | Deferred to v2 |
| Adaptive interval | `mmm_adaptive.py` | Fixed cadence (24h/1h) is simpler and sufficient |
| Whipsaw guard | `mmm_monitor.py` | Not applicable to daily cadence |
| Both-sides-up pause | `mmm_monitor.py` | Triggers are priority-ordered, not mutual-exclusion |
| Reverse mode | `mmm_reverse.py` | Not applicable to monthly strategy |
| Split ledger | `mmm_engine.py` | No frozen positions to split |
| Scaler | `mmm_scaler.py` | MVP uses fixed lots |
