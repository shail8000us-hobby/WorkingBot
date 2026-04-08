# MMMX — Phase-Wise Implementation Plan

> **Source of truth:** `MMMX_COMPLETE.md` (v10.0, 2026-04-05, all Q1–Q50 resolved, G1–G44 closed).
> **Scope:** This document is an execution blueprint only. It defines contracts, sequencing, wiring, and test criteria so a developer can build MMMX phase by phase without rework. No production code is written here.
> **Non-negotiable constraints inherited from repo:** MMM isolation (§ CLAUDE.md §1, §4, §5), UTC-only timestamps, `close_at_dte >= 7`, no MMM runtime imports in `webui/backend/routes/mmmx/`, separate DB (`mmmx_sessions.db`), separate registry, WebSocket events prefixed `mmmx_*`.
> **Ambiguities** are flagged in Section 9; they MUST be resolved with the operator before the relevant phase starts.

---

## SECTION 1 — SYSTEM FOUNDATION CONTRACT (IMMUTABLE)

This section locks the data model. Once Phase 1 ships, **no field renames, no type changes, no removals** — only additive fields behind a `_schema_version` guard.

### 1.1 Schema Version & Naming Conventions

- `_schema_version`: integer, current = `1`. Every session dict carries it. Session restore rejects unknown versions.
- **Namespace:** every backend file, table, registry key, WebSocket event, Telegram tag, REST route, and activity type starts with `mmmx_` / `mmmx.` / `MMMX-`. Never `mmm_*`.
- **Tranche IDs:** deployment tranches use integers `1..10`. Recovery tranches use strings `"{parent_id}{A|B|C}"` (e.g., `"2A"`, `"2B"`, `"2C"`). Hedge IDs use `"H-Tr{parent_id}"` (e.g., `"H-Tr5"`).
- **Position IDs (`_pos_id`):** 8-char hex, generated once at position creation, never reused.
- **Timestamps:** ISO 8601 with explicit `+00:00`. Source: `datetime.now(timezone.utc)`. Naive `utcnow()` is banned.
- **Monetary units:** all P&L, premiums, and fees in USD floats. Contract size in lots; 1 lot = `LOT_SIZE_BTC = 0.001` BTC (constant, never inlined).
- **Symbols:** `C-BTC-{strike}-{DDMMYY}` / `P-BTC-{strike}-{DDMMYY}`. Derived from live exchange chain only.
- **Internal flags:** underscore-prefixed fields (`_being_closed`, `_force_check`, `_my_generation`, `_whipsaw_score`, `_pnl_calculation_incomplete`) are runtime-only and MUST survive a `session_restore` round-trip.

### 1.2 Session Lifecycle States

Exactly one of these values lives in `session['status']` at all times:

| State | Entry trigger | Monitor thread | Listener thread | Orders allowed |
|---|---|---|---|---|
| `DRAFT` | `create_session()` called; gates not yet passed | stopped | stopped | none |
| `GATES_PASSED` | Entry gates evaluated OK; awaiting manual Tr1 deploy | stopped | stopped | none |
| `RUNNING` | Tr1 deployed | running | running | yes |
| `PAUSED` | API failure, naked position, operator pause, or restart | stopped (beat frozen) | running | none |
| `COMPLETE` | Hard stop, DTE close, `close_all` done, or manual stop | stopped | stopped | hedge-close only |
| `ERROR` | Unrecoverable crash; needs reconcile | stopped | stopped | none |

**Legal transitions** (any other transition is a bug and must raise):

```
DRAFT → GATES_PASSED → RUNNING → {PAUSED ↔ RUNNING} → COMPLETE
           ↓                ↓          ↓
         ERROR           ERROR      ERROR
```

Restart of the backend always lands in `PAUSED` (never auto-resume) — see Phase 9 reconciliation.

### 1.3 Session Schema (Complete & Locked)

```python
session = {
    # ─── identity ──────────────────────────────────────────────
    '_schema_version': 1,
    'session_id': '<uuid4>',
    'symbol_base': 'BTC',
    'expiry_date': '28-03-2026',        # DD-MM-YYYY
    'expiry_ddmmyy': '280326',
    'expiry_datetime': '<ISO UTC>',
    'created_at': '<ISO UTC>',
    'status': 'DRAFT',                  # see 1.2
    '_my_generation': 0,                # monitor generation (stale guard)

    # ─── parameters (hot-reload allowlist — see Section 5) ──────
    'params': {
        # entry gates (NOT hot-reloadable)
        'entry_dte_min': 20,
        'entry_dte_max': 45,
        'entry_iv_rank_min': 50,
        # tranche deployment
        'total_budget_lots': 100,
        'tranche_pct': 10,
        'otm_distance_pct': 15.0,
        'tranche_deploy_move_pct': 2.0,
        'tranche_deploy_iv_delta': 10,
        'hard_stop_multiplier': 2.0,
        'adjustment_interval_hours': 1,
        # delta gates
        'delta_drift_threshold': 0.35,
        'portfolio_delta_threshold': 0.15,
        'near_itm_delta': 0.55,
        'emergency_delta': 0.70,
        # IV
        'iv_spike_threshold_pct': 50,
        'iv_catastrophe_pct': 80,
        # ATM shield
        'atm_protect_threshold': 5.0,
        'atm_shield_max_shifts': 3,
        # quality gates
        'fairness_gate_enabled': True,
        'fairness_threshold_pct': 10.0,
        'max_deployments_per_day': 2,
        # profit booking
        'profit_booking_enabled': True,
        'profit_booking_targets': [10, 20, 30, 50],
        # hedging
        'hedging_enabled': True,
        'hedge_distance_pct': 20.0,
        'hedge_execution_delay_minutes': 15,
        'hedge_capacity_threshold_lots': 50,
        # exit
        'close_at_dte': 7,              # HARD MIN 7
        'profit_target_pct': 50,
        'profit_target_enabled': False,
        # whipsaw
        'whipsaw_window_mins': 30,
        'whipsaw_spot_move_pct': 0.3,
        'whipsaw_caution_score': 2,
        'whipsaw_restrict_score': 3,
        'whipsaw_cooldown_score': 4,
        'whipsaw_cooldown_interval_hours': 1,
    },

    # ─── capital & deployment budgets ───────────────────────────
    'total_budget_lots': 100,
    'ce_reserve_total_lots': 30,        # ATM shield reserve CE side (independent per-side pool)
    'pe_reserve_total_lots': 30,        # ATM shield reserve PE side (independent per-side pool)
    'ce_reserve_remaining': 30,         # CE reserve lots remaining
    'pe_reserve_remaining': 30,         # PE reserve lots remaining
    'tranches_deployed': 0,             # only type=='deployment'
    'tranches_remaining': 10,
    'total_deployed_lots': 0,           # sum of deployment-tranche lots per side
    'total_premium_collected': 0.0,     # gross shorts + recovery premiums (excludes hedges)

    # ─── hard stop ──────────────────────────────────────────────
    'hard_stop_usd': 0.0,
    'last_hard_stop_recalc_at': None,

    # ─── deployment reference baselines ─────────────────────────
    'last_deployment_spot': None,
    'last_deployment_iv_rank': None,
    'deployment_eligible_tranches': [],
    'deployment_queue_triggered_at': None,
    'deployment_queue_triggered_spot': None,
    'deployments_last_24h': [],         # rolling list of ISO timestamps (Q30)

    # ─── tranches & hedges ──────────────────────────────────────
    'tranches': [],                     # see 1.4
    'hedges': [],                       # see 1.5
    'hedges_by_parent': {},
    'total_hedge_cost_paid': 0.0,
    'active_hedges': 0,

    # ─── portfolio risk snapshot (refreshed each beat) ──────────
    'portfolio_delta': 0.0,
    'portfolio_pnl': 0.0,
    'ce_lot_balance': {
        'total_ce_lots': 0,
        'total_pe_lots': 0,
        'imbalance_pct': 0.0,
        'last_rebalance_beat': 0,
    },
    'fees_tracking': {
        'total_maker_fees': 0.0,
        'total_taker_fees': 0.0,
        'fee_rate_maker': 0.0002,
        'fee_rate_taker': 0.0005,
        'total_fees_paid': 0.0,
        'last_fee_charge': None,
    },

    # ─── whipsaw state ──────────────────────────────────────────
    '_whipsaw_score': 0,
    '_whipsaw_last_noise_at': None,
    '_whipsaw_skip_until': None,
    '_whipsaw_last_checked_idx': 0,
    'shield_event_history': [],         # [{'beat', 'side', 'spot', 'timestamp', 'tranche_id'}]

    # ─── runtime / safety flags ─────────────────────────────────
    '_force_check': False,
    '_pnl_calculation_incomplete': False,
    '_stale_abort_gen': None,
    '_naked_positions': [],             # [{'tranche_id','side','since','retries'}]
    '_circuit_breaker_state': 'CLOSED', # CLOSED | HALF_OPEN | OPEN
    '_last_beat_at': None,
    '_last_price_update_at': None,

    # ─── audit & counters ───────────────────────────────────────
    'beat_number': 0,
    'adjustment_count': 0,
    'shield_fire_count': 0,
    'profit_booked_total': 0.0,
}
```

### 1.4 Tranche Schema (Deployment & Recovery — identical shape)

```python
tranche = {
    'tranche_id': 1,                    # int for deployment, str "2A"/"2B"/"2C" for recovery
    'parent_tranche_id': None,          # int for recovery, else None
    'type': 'deployment',               # 'deployment' | 'recovery'
    'shield_event': None,               # 1/2/3 for recovery, else None
    'deployed_at': '<ISO UTC>',
    'entry_spot': 67500.0,
    'entry_dvol': 52.0,
    'entry_iv_rank': 65,
    'ce': {
        '_pos_id': 'abc12345',
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
        'status': 'ACTIVE',             # ACTIVE | CLOSED | REPOSITIONED | REDUCED
        'shift_count': 0,
        '_being_closed': False,
        '_being_closed_at': None,
        'shield_history': [],           # [{'event_no','old_strike','new_strike','loss','timestamp'}]
    },
    'pe': { ... },                      # same shape as ce
    'premium_collected': 275.0,
    'status': 'ACTIVE',                 # ACTIVE | PARTIAL | CLOSED
    'close_reason': None,               # 'profit_booking'|'hard_stop'|'dte'|'shield_rollover'|None
    'closed_at': None,
}
```

### 1.5 Hedge Schema

```python
hedge = {
    'hedge_id': 'H-Tr5',
    'parent_tranche_id': 5,
    'type': 'hedge',
    'deployed_at': '<ISO UTC>',         # parent tranche deploy time
    'hedge_executed_at': '<ISO UTC>',   # 15 min later
    'entry_spot': 70000.0,
    'hedge_distance_pct': 20.0,
    'ce': {
        'symbol': 'C-BTC-84000-280326',
        'strike': 84000,
        'lots': 10,
        'entry_premium': 45.0,
        'entry_delta': 0.35,
        'current_premium': None,
        'current_delta': None,
        'position_type': 'LONG',
        'unrealized_pnl': 0.0,
        'realized_pnl': 0.0,
        'fees_paid': 0.0,
        'status': 'ACTIVE',
        '_being_closed': False,
        '_being_closed_at': None,
    },
    'pe': { ... },
    'hedge_premium_paid': 85.0,
    'spread_width_ce': 4000,
    'spread_width_pe': 4000,
    'max_loss_if_spreads_hit': 400.0,
    'status': 'ACTIVE',                 # ACTIVE | DISPLACED | ORPHANED | CLOSED
    'displaced_from_parent_at': None,
}
```

### 1.6 Global / Process State Fields

These live outside `session` in the monitor runtime:

```python
_mmmx_monitors: Dict[session_id, MMMXMonitor]        # per-session monitor instances
_mmmx_listeners: Dict[session_id, MMMXPremiumListener]
_mmmx_watchdog: MMMXWatchdog                          # single process-wide instance
_mmmx_circuit_breaker: MMMXCircuitBreaker             # per-session
_mmmx_strike_cache: Dict[(asset, expiry), StrikeCache]  # TTL=beat interval
_mmmx_generation_counter: Dict[session_id, int]       # monotonic, DB-persisted
```

`_mmmx_monitors` is the single source of truth for which monitor is authoritative. The generation counter is incremented **before** a new monitor thread is spawned.

---

## SECTION 2 — MODULE ARCHITECTURE MAP

All backend files live under `webui/backend/routes/mmmx/`. Zero runtime imports from `routes/mmm/` — read-only helpers (`OptionsChainService`, `patience_iv.py`, `MarginGuardian`) are the only exceptions and must be accessed only via MMMX-local adapters (e.g., `mmmx_margin_guardian.py`, `mmmx_iv_adapter.py`, chain-service adapter). Direct non-adapter MMM imports fail the isolation scan in CI.

### 2.1 Module Inventory (27 backend files)

| # | Module | Responsibility | Sync/Async |
|---|---|---|---|
| 1 | `mmmx_constants.py` | `LOT_SIZE_BTC`, enum strings, fee rates, TTLs | sync |
| 2 | `mmmx_state.py` | Session dict factory, schema v1 validator, `initialize_*` helpers | sync |
| 3 | `mmmx_config.py` | Param validation + `close_at_dte >= 7` enforcement + hot-reload allowlist | sync |
| 4 | `mmmx_storage.py` | SQLite persistence (`mmmx_sessions.db`), CRUD, generation writes | sync |
| 5 | `mmmx_activity.py` | Ring buffer of activity events (`mmmx_activity_log.json`) | sync |
| 6 | `mmmx_audit_log.py` | Append-only JSONL trade/order journal | sync |
| 7 | `mmmx_param_audit.py` | Every hot-reload param change logged with diff | sync |
| 8 | `mmmx_websocket.py` | Emits `mmmx_*` events via Flask-SocketIO bridge | sync (fire-and-forget) |
| 9 | `mmmx_telegram.py` | Alert dispatcher with dedup (hash + TTL) | async |
| 10 | `mmmx_engine.py` | P&L, portfolio delta, IV change, lot imbalance, BS fair value, fee calcs | sync |
| 11 | `mmmx_trigger.py` | Priority-ordered trigger evaluator (Section 3.7) | sync |
| 12 | `mmmx_safety.py` | Pre-beat checks: DTE sanity, generation guard, P&L completeness | sync |
| 13 | `mmmx_executor.py` | `smart_execute`, `emergency_execute`, dedup, margin pre-check, continuous margin recheck (G40) | async |
| 14 | `mmmx_atm_shield.py` | OTM monitoring, 6-step shield sequence, multi-shield priority (G38), reserve cascade (G39) | async |
| 15 | `mmmx_hedger.py` | Scheduled hedge buys (G43), displacement tracking, hedge P&L update | async |
| 16 | `mmmx_whipsaw.py` | Score accumulation, decay, cooldown gate (G44) | sync |
| 17 | `mmmx_profit_booking.py` | Per-tranche close requests (Q29/Q32/Q34) | async |
| 18 | `mmmx_circuit_breaker.py` | 3-state (CLOSED/HALF_OPEN/OPEN) API fault isolation | sync |
| 19 | `mmmx_premium_listener.py` | WebSocket listener + Tier-0 CBs + heartbeat watchdog (G41) | async |
| 20 | `mmmx_monitor.py` | Heartbeat thread, 3-layer generation guard, beat orchestration | async + thread |
| 21 | `mmmx_watchdog.py` | Supervises monitor & listener; restarts dead threads with new generation | sync (thread) |
| 22 | `mmmx_initializer.py` | Entry gates, strike scanning, liquidity validation, initial deploy, reconcile | async |
| 23 | `mmmx_margin_guardian.py` | Read-only MMMX adapter over MMM's `MarginGuardian` | sync |
| 24 | `mmmx_reconciler.py` | Partial-fill tracking, exchange-vs-DB diff (Q23), `reconcile_with_exchange()` | async |
| 25 | `mmmx_api.py` | Flask Blueprint `/api/mmmx/*` routes | sync (async via executor) |
| 26 | `__init__.py` | Blueprint registration, startup session restore | sync |
| 27 | `tests/` | pytest unit + integration suites | — |

### 2.2 Dependency Graph (top-down, no cycles)

```
                           ┌────────────────────┐
                           │ mmmx_constants.py  │
                           └──────────┬─────────┘
                                      │
          ┌───────────────────────────┼────────────────────────┐
          ▼                           ▼                        ▼
  ┌────────────────┐         ┌─────────────────┐      ┌─────────────────┐
  │ mmmx_state.py  │         │ mmmx_config.py  │      │ mmmx_storage.py │
  └────────┬───────┘         └────────┬────────┘      └────────┬────────┘
           │                          │                        │
           └────────────┬─────────────┴────────────┬───────────┘
                        ▼                          ▼
              ┌───────────────────┐      ┌────────────────────┐
              │ mmmx_activity.py  │      │ mmmx_audit_log.py  │
              │ mmmx_param_audit  │      │ mmmx_websocket.py  │
              │ mmmx_telegram.py  │      │                    │
              └────────┬──────────┘      └──────────┬─────────┘
                       └──────────┬────────────────┘
                                  ▼
                         ┌─────────────────┐
                         │ mmmx_engine.py  │ (pure math, no I/O)
                         └────────┬────────┘
                                  ▼
             ┌────────────────────┼────────────────────┐
             ▼                    ▼                    ▼
    ┌────────────────┐   ┌────────────────┐   ┌────────────────────┐
    │ mmmx_safety.py │   │ mmmx_trigger   │   │ mmmx_circuit_break │
    └───────┬────────┘   └────────┬───────┘   └──────────┬─────────┘
            │                     │                       │
            ▼                     ▼                       ▼
                    ┌────────────────────────┐
                    │ mmmx_executor.py       │ ← uses margin_guardian
                    └────────────┬───────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
   ┌────────────────┐   ┌────────────────┐   ┌──────────────────┐
   │ atm_shield.py  │   │ hedger.py      │   │ profit_booking   │
   └────────┬───────┘   └────────┬───────┘   └────────┬─────────┘
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 ▼
                     ┌────────────────────┐
                     │ mmmx_monitor.py    │ ← calls whipsaw, reconciler
                     └─────────┬──────────┘
                               ▼
                   ┌──────────────────────┐
                   │ mmmx_premium_listener│
                   │ mmmx_watchdog        │
                   │ mmmx_initializer     │
                   │ mmmx_reconciler      │
                   └──────────┬───────────┘
                              ▼
                     ┌────────────────┐
                     │ mmmx_api.py    │
                     │ __init__.py    │
                     └────────────────┘
```

Rules:
- `mmmx_engine.py` is **pure** — no I/O, no side effects, deterministic given inputs. All math lives here.
- `mmmx_executor.py` is the **only** module that calls the exchange REST API for orders.
- `mmmx_monitor.py` is the **only** writer to `_mmmx_monitors` and generation counter.
- `mmmx_atm_shield.py`, `mmmx_hedger.py`, `mmmx_profit_booking.py` mutate session state **only via monitor-provided context**; they never write storage directly.

### 2.3 Module Contracts (inputs / outputs / failure boundary)

| Module | Key functions | Input | Output | Failure mode |
|---|---|---|---|---|
| `mmmx_engine` | `compute_position_pnl`, `compute_portfolio_pnl`, `compute_portfolio_delta`, `compute_lot_imbalance`, `black_scholes_fair_value`, `recalc_hard_stop` | session, live quotes | dict of metrics; never mutates | raises `PnLIncompleteError` → caller sets `_pnl_calculation_incomplete` and skips triggers |
| `mmmx_trigger` | `evaluate(session, metrics)` | session, engine metrics | first-match trigger dict `{'name','action','context'}` or `None` | pure; returns `None` if nothing |
| `mmmx_safety` | `pre_beat_check(session, stored_gen)` | session, DB generation | `SafetyVerdict(ok, reason, stale, pnl_incomplete)` | never raises; returns verdict |
| `mmmx_executor` | `smart_execute`, `emergency_execute`, `preflight_margin_check`, `compute_client_order_id` | order params, session | `ExecutionResult(success, filled_size, avg_price, attempts, total_ms, reason)` | returns result with `success=False`; never raises on API error |
| `mmmx_atm_shield` | `evaluate_and_fire(session, ctx)` | session, live spot & premiums | list of `ShieldResult` | on sell failure → session PAUSED, naked alert raised |
| `mmmx_hedger` | `schedule_post_deploy(session, tranche)`, `tick(session)` | session | new `hedge` entries | scheduled executions retry next tick; no session PAUSE |
| `mmmx_whipsaw` | `score_tick(session, shield_events)`, `apply_to_deployment(session, base_params)` | session | adjusted `{move_pct, tranche_size, skip}` | pure |
| `mmmx_monitor` | `start_session_monitor`, `_run_loop`, `_heartbeat`, `_save_session` | session | writes storage, emits events | stale generation → self-stop |
| `mmmx_premium_listener` | `subscribe`, `on_tick`, `set_force_check` | WebSocket feed | sets `_force_check`, triggers CB_NEAR_ITM reduce | stale WS → force-check escalation |
| `mmmx_watchdog` | `tick` | `_mmmx_monitors`, `_mmmx_listeners` | restarts dead threads | escalates to Telegram critical on repeated failure |
| `mmmx_reconciler` | `reconcile_with_exchange(session)`, `track_partial_fill(order_id, filled, requested)` | session, exchange | reconciliation report | returns report; does not auto-resume |

### 2.4 Call Graph (heartbeat hot path)

```
monitor._run_loop
  └── _heartbeat
        ├── safety.pre_beat_check                   (stale? pnl complete?)
        ├── reconciler.tick_partials                (any residual closes?)
        ├── engine.refresh_live_quotes              (via chain service adapter)
        ├── engine.compute_portfolio_pnl
        ├── engine.compute_portfolio_delta
        ├── engine.compute_lot_imbalance
        ├── trigger.evaluate                        (priority table)
        │     ├── if HARD_STOP → executor.close_all (market shorts, limit longs)
        │     ├── if DTE_CLOSE → executor.close_all
        │     ├── if ATM_SHIELD → atm_shield.evaluate_and_fire
        │     ├── if DEPLOY → initializer.execute_tranche_deploy
        │     └── else  → executor.reposition / reduce_then_roll / roll
        ├── hedger.tick                             (15-min scheduler)
        ├── whipsaw.score_tick
        ├── profit_booking.process_pending          (operator-queued closes)
        ├── monitor._save_session                   (gen-checked write)
        └── websocket.emit + telegram.flush
```

---

## SECTION 3 — EXECUTION PROTOCOL DESIGN

### 3.1 Order Lifecycle (single order)

```
1. Build order intent
   └── symbol, side, size, reduce_only, position_tag (tranche_id/side)
2. Compute deterministic client_order_id (G8)
   └── hash(session_id | tranche_id | side | action | minute_bucket)
3. Dedup check
   └── query exchange open orders by client_order_id → if exists, return existing
4. Margin preflight (executor.preflight_margin_check)
   └── if utilization > 80% AND side == SELL → BLOCKED, return failure
5. Set in-flight guard
   └── position['_being_closed'] = True, timestamp = monotonic()
6. Generation re-verify (G5 layer 3)
   └── if _my_generation != stored_gen → ABORT, no order
7. Place limit order at mid-price
8. Reprice loop (max_reprice_attempts):
   for attempt in range(attempts):
       wait 30s (configurable via FILL_TIMEOUT)
       if filled → goto 10
       margin re-check (G40):
           if util >= 95% → ABORT execution, return failure
           if util >= 85% → break loop, goto 9 (market fallback)
       cancel, refetch bid/ask, reprice:
           attempts 1..N/2: mid price
           attempts N/2+1..N: bid (sells) / ask (buys) — more aggressive
9. Market fallback (emergency_execute, IOC)
10. Record fill:
    - update fees_tracking
    - update position.current_premium/realized_pnl
    - append to audit log
    - clear _being_closed
11. Return ExecutionResult
```

Defaults:
- Tranche deploy SELL: `max_reprice_attempts=4`, timeout 30s/attempt
- ATM shield BUY-back: `max_reprice_attempts=10`, timeout 30s/attempt → up to 5 min
- ATM shield SELL-new: 10 limit attempts + 1 market fallback (G37, Section 3.5)
- Hard-stop SHORT close: MARKET on danger side (immediate), LIMIT on hedge side (patient)

### 3.2 Retry Logic (step-by-step)

| Failure type | Action |
|---|---|
| Timeout on limit reprice | Cancel, refetch quote, reprice; accumulate attempt count |
| Exchange rejects (e.g., tick size) | Round to exchange tick, retry once, else fall through to market fallback |
| Partial fill, order still live | Let it continue; on next reprice, reduce remaining size |
| Partial fill, order cancelled mid-flight | `reconciler.track_partial_fill` records residual; next beat retries residual |
| Margin rejection | If SELL: abort, surface `MARGIN_BLOCKED` to caller. If BUY (close): this is structural — raise `FATAL_MARGIN`, call `emergency_execute` which ignores tranche budget because closing reduces risk. |
| Network timeout | Circuit breaker state: CLOSED → HALF_OPEN (retry after 5s) → OPEN (queue all, raise `API_UNAVAILABLE`) |
| API OPEN | Monitor pauses session, listener stays active, retry API each beat (Q22) |

### 3.3 Partial Fill Handling

- Every placed order is persisted to `mmmx_audit_log.py` at placement with `status=PENDING`.
- Every fill (full or partial) is persisted with `filled_size` and `cumulative_filled`.
- `mmmx_reconciler.py` maintains a `pending_residuals` table: `{order_id, symbol, side, tranche_id, requested, filled, remaining, last_attempt_at}`.
- At beat start (step "reconciler.tick_partials"), every residual is retried with `smart_execute` on the remaining size.
- A residual is only cleared when `filled == requested` OR the position no longer exists on exchange (operator manual close).
- Delta gate logic is re-applied to residuals: if the remainder's implied delta now exceeds `emergency_delta`, it escalates to `emergency_execute`.

### 3.4 Deduplication Rules

1. **Deterministic client_order_id** (G8): `sha256(session_id|tranche_id|side|action|minute_bucket)[:16]`. `minute_bucket` rounds the UTC timestamp to the nearest whole minute to give a retry-safe window.
2. Before any `create_order` call, executor calls `fetch_open_orders(client_order_id=...)`. If present → return the existing order without a new POST.
3. **`_being_closed` guard** on position dict: set before close, 180 s TTL; on restart, any expired guard is cleared in `init_mmmx`.
4. **Generation tag** on every order audit row: `_my_generation`. Stale monitor orders are detected post-hoc during reconciliation.

### 3.5 Failure Handling — Specific Scenarios

| Scenario | Handler | Detail |
|---|---|---|
| Tranche deploy: CE fills, PE rejects | initializer rolls back CE via `emergency_execute` (buy-back), no state mutation, Telegram warning | strict all-or-nothing for deployment |
| ATM shield buyback fails after 10 attempts | Check exchange → if already closed, mark closed and proceed to Step 3. Else call `emergency_execute` (IOC, aggressive). Still fails → **abort shield, do NOT sell new position** (no naked) | Section 6 MMMX_COMPLETE |
| ATM shield new-sell fails (10 limit + 1 market) | Session PAUSED, position naked, `_naked_positions` appended, Telegram CRITICAL, watchdog escalation at 30 min + 2 h | G37 |
| Hard stop trips mid-shield | Current atomic step completes (no mid-op abort) — next beat tops with hard stop check and calls `close_all` | Q21 |
| API unreachable | Executor surfaces `API_UNAVAILABLE`; monitor sets status PAUSED; listener keeps WS; retry each beat; on recovery run full beat | Q22 |
| Crash between place & fill | Deterministic client_order_id + reconciler catches duplicate and partial | Q24 |
| Restart | Always land in PAUSED; require manual Reconcile + Resume | Q25 |

### 3.6 Margin Check Sequence (every order)

```
1. preflight (before order creation):
     util = margin_guardian.current_utilization()
     if side == SELL and util >= 80:  return MARGIN_BLOCKED
     if side == BUY  and util >= 95:  return MARGIN_CRITICAL
2. per reprice (during loop):
     util = margin_guardian.current_utilization()
     if util >= 95: abort, return MARGIN_CRITICAL
     if util >= 85: break loop, fall through to market order (G40)
3. multi-shield pre-check:
     required = sum(shield.estimated_margin for shield in sorted_shields)
     if required > (total_margin * 0.90): execute sequentially with per-step recheck
4. hedge buys:
     hedges consume margin; if buying a hedge would push util > 80, skip this hedge and Telegram alert
```

### 3.7 Trigger Priority Table (authoritative)

Order must match `MMMX_COMPLETE.md` Section 5:

```
 1. DTE_CLOSE          DTE <= close_at_dte          → close_all
 2. HARD_STOP          total_pnl <= -hard_stop_usd  → close_all (shorts only; hedge LONGs survive)
 3. IV_CATASTROPHE     iv_Δ >= 80% AND δ >= 0.70    → close_all
 4. NEAR_ITM           max threatened δ >= 0.70     → close_all
 5. DEPLOY_TRANCHE     deploy conditions pass        → deploy
 6. IV_SPIKE           iv_Δ >= 50% AND δ >= 0.55    → reposition
 7. REPOSITION         δ in [0.35, 0.69]            → reposition
 8. PORTFOLIO_DELTA    |δ_port| >= 0.15             → reduce worst
 9. DELTA_DRIFT        |current_δ - entry_δ| > delta_drift_threshold → roll
```

First match wins; protection (1–4) always beats deployment; shield fire in current beat pre-empts deployment (6-priority from `MMMX_COMPLETE` Section 1).

### 3.8 Naked Position Prevention

1. Every buy-back is gated by a matching pre-committed sell plan; shield sequence always re-validates that a new strike is available BEFORE buyback when possible.
2. If new strike cannot be found post-buyback → naked flag raised, session PAUSED.
3. Naked watchdog (G37): at 30 min force heartbeat + `emergency_execute` retry; at 2 h escalate operator Telegram `CRITICAL`.
4. `_naked_positions` entries are atomic: `{tranche_id, side, since, retries, reason}`. They survive persistence.
5. Reconcile on restart: any exchange position present but no session-side open SHORT is a naked detection → PAUSED ERROR state.

---

## SECTION 4 — PHASE-WISE BUILD PLAN

Each phase ends with (a) a merged PR, (b) unit + integration tests green, (c) a short operator demo. A phase is NOT complete until its exit criteria are satisfied. Phases are strictly sequential — a later phase may depend on earlier modules but not vice versa.

> **Isolation gate (repeat before every phase):** run the MMM isolation scan — no imports of `routes.mmm.*` from `routes.mmmx.*`, no writes to `mmm_sessions.db`, no `mmm_*` WebSocket events. Phase cannot merge if the scan fails. MMM sealed tests must still pass (baseline 1312, per repo memory).

### PHASE 1 — Skeleton: State, Storage, Empty Monitor ✅ COMPLETE (2026-04-06)

**Status:** DONE — 69/69 tests passing. MMM isolation scan clean.

**Files delivered** (`webui/backend/routes/mmmx/`):
- `mmmx_constants.py` — LOT_SIZE_BTC, all enums, fee rates, TTLs, DB paths
- `mmmx_state.py` — `create_session()`, `make_tranche()`, `make_hedge()`, `validate_schema()`, all `initialize_*` helpers, `transition_status()`
- `mmmx_config.py` — `validate_params()`, `validate_hot_reload_patch()`, `HOT_RELOAD_ALLOWLIST`, `diff_params()`
- `mmmx_storage.py` — SQLite WAL, 5-table schema (`sessions`, `generations`, `audit_log`, `activity_log`, `param_audit`), `save_session(expected_gen)`, `load_session`, `bump_generation`, `get_generation`
- `mmmx_activity.py` — Thread-safe in-memory ring buffer + DB persistence, all MMMX activity types
- `mmmx_audit_log.py` — Queue-backed async writer, `enqueue_trade()`, `enqueue_event()`, idempotency key
- `mmmx_param_audit.py` — `record_param_change()`, `get_param_history()`
- `mmmx_websocket.py` — All `mmmx_*` event emitters, stale detection, `get_ws_health()`
- `mmmx_telegram.py` — Dedup-gated async alerts, all typed helpers (`alert_hard_stop`, `alert_atm_shield`, etc.)
- `mmmx_engine.py` — Pure math: `compute_position_pnl`, `compute_portfolio_pnl`, `compute_portfolio_delta`, `compute_lot_imbalance`, `black_scholes_fair_value`, `recalc_hard_stop`, `compute_dte_days`, `apply_whipsaw_to_deployment`, deployment queue math, recovery lot calculation, fairness gate
- `mmmx_monitor.py` — 3-layer generation guard (Layer 1: `thread.join(15s)`; Layer 2: stored-gen check at top of `_run_loop`; Layer 3: G5 guard inside `_heartbeat_stub`), `_save_session()` returns bool, `_stale_abort_gen` flag, `start_session_monitor` / `stop_session_monitor` / `get_monitor` / `get_all_monitors`
- `mmmx_api.py` — 9 routes: `POST /session`, `GET /sessions`, `GET /session/<id>`, `PATCH /session/<id>/params`, `POST /session/<id>/stop`, `POST /session/<id>/start-monitor`, `GET /session/<id>/audit`, `GET /session/<id>/activity`, `GET /session/<id>/param-history`, `GET /health`
- `__init__.py` — `mmmx_bp`, `init_mmmx()` (restores sessions → PAUSED, wires storage into singletons)
- `tests/__init__.py` + `tests/test_phase1.py` — 69 tests covering all exit criteria

**Exit criteria — all met:**
- ✅ Create session via API → DRAFT with validated params
- ✅ `close_at_dte=6` rejected; `close_at_dte=7` accepted
- ✅ Start/stop monitor: generation increments; stale monitor self-stops within one beat
- ✅ Two concurrent sessions run without colliding registries
- ✅ Engine unit tests: P&L, fees, hard stop recalc, BS pricing (put-call parity), lot imbalance, DTE, whipsaw, fairness gate, recovery lots, deployment queue
- ✅ MMM isolation scan clean (no `routes.mmm.*` imports, no `mmm_sessions.db` in code)

**NOT built yet:** executor, shield, hedger, trigger, listener, watchdog, reconciler, initializer, UI.

---

> **NEXT AI — START HERE FOR PHASE 2**
>
> Phase 1 is complete and all 69 tests pass. You are starting **Phase 2: Execution Engine**.
>
> **What exists:** All of `webui/backend/routes/mmmx/` Phase 1 files (see above). Read them before writing anything.
>
> **What to build next:**
> - `mmmx_executor.py` — `smart_execute()`, `emergency_execute()`, `preflight_margin_check()`, `midloop_margin_check()` (G40), `compute_client_order_id()` (G8), `fetch_open_orders_by_client_id()`. See plan Section 3.1 for the full order lifecycle (limit → reprice loop → market fallback). Defaults: 4 reprice attempts for deploy SELL, 10 for shield buyback, 30s per attempt.
> - `mmmx_circuit_breaker.py` — 3-state CLOSED/HALF_OPEN/OPEN. `record_success()`, `record_failure()`, `state`, `allow_request()`. See plan Section 3.2.
> - `mmmx_margin_guardian.py` — Read-only MMMX adapter wrapping the existing `MarginGuardian` from `webui/backend/routes/mmm/`. This is the ONLY allowed cross-package read. Expose only: `current_utilization()`, `estimated_margin_for_order()`. Do NOT expose any MMM write paths.
> - `mmmx_reconciler.py` — `track_partial_fill()`, `tick_partials()`, `reconcile_with_exchange()`. See plan Section 3.3.
> - Add `ExecutionResult` dataclass to `mmmx_constants.py` or a new `mmmx_types.py`.
>
> **Key constraints (from MMMX_COMPLETE.md — final authority):**
> - `smart_execute` margin pre-check: SELL blocked at util >= 80%, BUY blocked at 95%
> - Mid-loop: util >= 85% → switch to market; util >= 95% → abort
> - Deterministic `client_order_id`: `sha256(session_id|tranche_id|side|action|minute_bucket)[:16]`
> - `_being_closed` guard: 180s TTL, set before close, cleared after fill
> - Circuit breaker: CLOSED → HALF_OPEN after N failures; OPEN blocks all requests; CLOSED on probe success
> - Isolation: `mmmx_margin_guardian.py` is the ONLY file allowed to import from `routes.mmm.*` — all other mmmx files must remain clean
>
> **Run after building:** `python3 -m pytest webui/backend/routes/mmmx/tests/ -v`
> Phase 2 exit criteria are in plan Section 4 (PHASE 2 block below).

### PHASE 2 — Execution Engine ✅ COMPLETE (2026-04-06)

**Status:** DONE — 40/40 Phase 2 tests passing. 109/109 total (Phase 1 + 2). MMM isolation scan clean.

**Files delivered** (`webui/backend/routes/mmmx/`):
- `mmmx_executor.py` — `smart_execute()`, `emergency_execute()`, `preflight_margin_check()`, `_midloop_margin_check()`, `compute_client_order_id()` (sha256 deterministic), `_fetch_open_orders_by_client_id()` (dedup), `ExecutionResult` dataclass, `get_executor()` singleton. Full reprice loop (limit → cancel/reprice → market fallback). `_being_closed` guard set/cleared. Audit trade logged on fill. Isolation-clean (zero `routes.mmm.*` imports).
- `mmmx_circuit_breaker.py` — 3-state CLOSED/HALF_OPEN/OPEN per session. `record_success()`, `record_failure()`, `get_state()`, `allow_request()`, `reset()`. Thread-safe with lock. 5s cooldown in OPEN. N=3 failures trips to HALF_OPEN.
- `mmmx_margin_guardian.py` — Read-only adapter over MMM `MarginGuardian`. THE ONLY mmmx file allowed to import from `routes.mmm.*`. `current_utilization()` (async, caches last value), `estimated_margin_for_order()` (sync), `get_margin_guardian()` singleton.
- `mmmx_reconciler.py` — `track_partial_fill()` (in-memory + audit log), `tick_partials(session)` (retries residuals each heartbeat; escalates to emergency for >= 20 remaining lots), `reconcile_with_exchange(session)` (Phase 9 manual trigger — compares DB vs exchange positions), `get_pending_residuals()`, `clear_all_residuals()`.
- `tests/test_phase2.py` — 40 tests covering all Phase 2 exit criteria.

**Exit criteria — all met:**
- ✅ Mocked exchange: limit fills first attempt → success
- ✅ All reprice attempts timeout → falls through to market (emergency_execute)
- ✅ Margin 85% mid-loop → market fallback triggered
- ✅ Margin 95% mid-loop → abort, returns `ExecutionResult(success=False, reason='MARGIN_CRITICAL')`
- ✅ Preflight: SELL blocked at util >= 80%
- ✅ Duplicate client_order_id: second smart_execute finds open order, returns without new POST
- ✅ Partial fill recorded; `tick_partials` retries remainder; audit log receives PARTIAL_FILL_CLEARED
- ✅ Circuit breaker: CLOSED → HALF_OPEN after 3 failures → OPEN after probe fails → CLOSED after probe succeeds
- ✅ MMM isolation scan clean for all Phase 2 modules (mmmx_margin_guardian.py correctly excluded as designated bridge)

**NOT built:** shield, hedger, triggers, listener, UI, initializer beyond executor hooks.

---

> ~~**NEXT AI — START HERE FOR PHASE 3**~~
>
> **✅ PHASE 3 COMPLETE — 2026-04-06 — 36 tests (145 total: 69 P1 + 40 P2 + 36 P3)**
>
> Files built:
> - `mmmx_safety.py` — `pre_beat_check(session, stored_gen, my_generation) → SafetyVerdict`
> - `mmmx_trigger.py` — `evaluate(session, metrics) → Optional[TriggerHit]` (7-priority table)
> - `mmmx_monitor.py` — `_heartbeat()` full hot-path + `_dispatch_close_all()` (replaces `_heartbeat_stub`)
> - `tests/test_phase3.py` — 36 tests covering all safety verdicts, trigger priorities, heartbeat paths

---

> **NEXT AI — START HERE FOR PHASE 4**
>
> Phase 3 is complete and all 145 tests (69 Phase 1 + 40 Phase 2 + 36 Phase 3) pass. You are starting **Phase 4: Hard Stop & close_all (Production Hardened)**.
>
> **What exists:** All of `webui/backend/routes/mmmx/` Phase 1–3 files. Read them before touching anything, especially:
> - `mmmx_monitor.py` — `_heartbeat()` full hot-path (async), `_dispatch_close_all()` (emergency close loop)
> - `mmmx_safety.py` — `pre_beat_check()` returns `SafetyVerdict` (ok/skip_beat/abort)
> - `mmmx_trigger.py` — `evaluate()` returns `Optional[TriggerHit]` (7 priorities, pure function)
> - `mmmx_executor.py` — `smart_execute()`, `emergency_execute()`, `ExecutionResult`
> - `mmmx_constants.py` — all enums, `TriggerName`, `TrncStatus`, `SessionStatus`
>
> **Key invariants carried from Phase 3 (DO NOT BREAK):**
> - `emit_safety()` is a regular `def` — call directly, NEVER await
> - `_save_session()` returns True/False — ALWAYS check; set `_stale_abort_gen + _running=False` if False
> - `_heartbeat()` is `async def` — called via `asyncio.run()` from `_run_loop`
> - PAUSED status passes safety pre-check (status guard allows RUNNING and PAUSED)
> - `compute_dte_days(None)` returns -1.0 (EXPIRY_PAST); past datetime strings return 0.0 (handled by DTE_CLOSE trigger)
>
> **What to build next (Phase 4):**
> - Harden the `_dispatch_close_all()` path:
>   - Market-on-danger, limit-on-safe split (Section 3 of spec): lots >= 20 → market, else limit
>   - Fee accounting fully wired into each fill (update `session['fees_tracking']`)
>   - Session status transitions to COMPLETE atomically with persistence
>   - Telegram CRITICAL dedup on hard stop (already exists in `mmmx_telegram.py`)
> - Gap-risk acceptance tests (G36)
>
> **Run after building:** `python3 -m pytest webui/backend/routes/mmmx/tests/ -v`
> All 145 prior tests must still pass.

### PHASE 3 — Monitoring Core (Triggers, Safety, Beat Body) ✅ COMPLETE 2026-04-06

**Build:**
- `mmmx_safety.py`, `mmmx_trigger.py`
- Flesh out `mmmx_monitor._heartbeat` with the hot-path call graph (Section 2.4) **minus** shield, hedge, deploy, profit-booking, listener.
- Add adapters for `OptionsChainService` (read-only) and `patience_iv` (IV rank source).

**Functions:**
- `safety.pre_beat_check(session, stored_gen) → SafetyVerdict`
- `trigger.evaluate(session, metrics) → Optional[TriggerHit]` (priority table 3.7)
- `monitor._heartbeat`: load fresh session → safety → quotes → engine metrics → trigger → dispatch stub (logs action but only HARD_STOP + DTE_CLOSE actually close via executor)
- `monitor._dispatch_close_all` (market shorts, limit longs — uses executor only)
- `engine.refresh_live_quotes(session)` using chain service cache

**Dependencies:** Phase 1, Phase 2.

**NOT built:** shield execution, deployment execution, hedger, listener, profit booking.

**Test criteria:**
- Synthetic session with manufactured prices triggers HARD_STOP → `close_all` fires → session COMPLETE.
- DTE fixture at 6.9 days triggers DTE_CLOSE.
- P&L incomplete flag skips triggers and retries next beat.
- Trigger priority: DTE beats HARD_STOP beats IV_CATASTROPHE etc. (10 cases, one per row).
- Stale generation mid-heartbeat: 3-layer guard stops the monitor; no order placed.
- MMM isolation scan clean.

### PHASE 4 — Hard Stop & close_all (Production Hardened) ✅ COMPLETE (2026-04-06)

**Status:** DONE — 44/44 Phase 4 tests passing. 189/189 total (69 P1 + 40 P2 + 36 P3 + 44 P4). MMM isolation scan clean.

**Files delivered** (`webui/backend/routes/mmmx/`):
- `mmmx_close_all.py` — `async close_all(session, reason, executor, audit) → CloseAllReport`. SHORT legs closed via `emergency_execute` (MARKET, buy-to-close); LONG hedge legs closed via `smart_execute` (LIMIT at bid, sell). Recovery tranches are full citizens — iterated in the same loop. Hedge failures mark `ORPHANED`, log WARNING (non-fatal per Q47). Short failures log CRITICAL but session still transitions to COMPLETE (best-effort). Full fee accounting from `result.fees_paid` (verbatim, no recompute). Telegram + audit + emit_safety (sync) all fired. G36 slippage exposed in the returned report.
- `mmmx_engine.py` (additive) — `classify_danger_side(tranche) → str`: pure function returning `'ce'` / `'pe'` / `'both'` / `'none'`. For logging/reporting only — close_all always closes all ACTIVE legs regardless.
- `mmmx_monitor.py` (updated) — `_dispatch_close_all()` now delegates to `mmmx_close_all.close_all()`. G36 slippage logged (HARD_STOP only): `trigger=-{hard_stop_usd}, actual={portfolio_pnl}, overshoot={overshoot}`. `_save_session` + `_running=False` after.
- `tests/test_phase4.py` — 44 tests covering all exit criteria.

**Exit criteria — all met:**
- ✅ Basic close_all: 2 deployment tranches + 1 hedge → 4 shorts filled, 2 hedges filled
- ✅ Hedge limit-sell fails → ORPHANED, WARNING logged, close_all still completes
- ✅ Short emergency_execute fails → CRITICAL logged, session still → COMPLETE, close_errors populated
- ✅ Recovery tranches (type='recovery') closed in same loop as deployment tranches
- ✅ Fee accounting: total_fees_paid incremented from result.fees_paid verbatim
- ✅ G36 slippage: overshoot computed and logged by _dispatch_close_all for HARD_STOP, NOT for DTE_CLOSE
- ✅ _dispatch_close_all delegates to close_all; _save_session called; _running=False after
- ✅ classify_danger_side: CE losing → 'ce'; PE losing → 'pe'; both losing → 'both'; both profitable → 'none'
- ✅ MMM isolation scan clean for mmmx_close_all, mmmx_engine, mmmx_monitor
- ✅ CloseAllReport: all fields present; completed_at is valid ISO 8601 UTC string

**NOT built:** shield, hedger, deployment, listener.

---

> **NEXT AI — START HERE FOR PHASE 5**
>
> Phase 4 is complete and all 189 tests (69 P1 + 40 P2 + 36 P3 + 44 P4) pass. You are starting **Phase 5: ATM Shield (+ Multi-Shield, Reserve Cascade, Naked Handling)**.
>
> **What exists:** All of `webui/backend/routes/mmmx/` Phase 1–4 files. Read them before touching anything, especially:
> - `mmmx_close_all.py` — `close_all(session, reason, executor, audit) → CloseAllReport` (Phase 4)
> - `mmmx_engine.py` — `classify_danger_side(tranche)` (Phase 4 addition); pure math functions
> - `mmmx_monitor.py` — `_dispatch_close_all()` delegates to `mmmx_close_all.close_all()`; 3-layer generation guard
> - `mmmx_executor.py` — `smart_execute()`, `emergency_execute()`, `ExecutionResult`
> - `mmmx_constants.py` — `TrncStatus`, `HedgeStatus`, `SessionStatus`, `TrncType`; `ce_reserve_remaining`/`pe_reserve_remaining` are independent 30-lot pools
> - `mmmx_state.py` — `make_tranche()`, `make_hedge()`, session schema
>
> **Key invariants carried from Phases 1–4 (DO NOT BREAK):**
> - `emit_safety()` is a regular `def` — call directly, NEVER await
> - `_save_session()` returns True/False — ALWAYS check; set `_stale_abort_gen + _running=False` if False
> - Recovery tranches use string IDs (`"2A"`, `"2B"`, `"2C"`); deployment use integers. Both are full citizens of `session['tranches']`.
> - `ce_reserve_remaining` and `pe_reserve_remaining` are tracked independently (30 lots each)
> - `tranches_deployed` and `tranches_remaining` are NOT changed by recovery tranche creation
> - Phase 4 isolation: `mmmx_close_all.py` has zero `routes.mmm.*` imports — keep it that way
>
> **What to build next (Phase 5):**
> - `mmmx_atm_shield.py` — full 6-step shield sequence per `MMMX_COMPLETE.md` Section 6:
>   1. Detect position OTM% fallen below `atm_protect_threshold` (default 5%)
>   2. Find replacement strike (OTM reset to original distance)
>   3. Buyback old position (10 limit attempts + 1 market fallback)
>   4. Sell new position at replacement strike (10 limit + 1 market per G37)
>   5. If new-sell fails all attempts → session PAUSED, `_naked_positions` populated, Telegram CRITICAL
>   6. Allocate recovery tranche from reserve (G39 — partial or zero cascade)
> - Extend `mmmx_monitor._heartbeat` to call `atm_shield.evaluate_and_fire(session, ctx)` before deployment triggers
> - Extend `mmmx_reconciler` with naked detection hooks
> - Reserve depletion: `ce_reserve_remaining` / `pe_reserve_remaining` decremented per shield recovery
>
> **Key constraints (from MMMX_COMPLETE.md — final authority):**
> - Shield fires even when session is PAUSED (naked watchdog path)
> - Multi-shield same beat: sort candidates by loss (worst first, G38); execute sequentially; if reserve exhausted mid-cascade → reposition-only for remaining (G39 partial)
> - Shield buyback fails after 10 limit + 1 emergency → abort shield (no naked); next beat re-evaluates
> - Shield new-sell fails 11 attempts → PAUSED, naked logged; never create recovery tranche without confirmed sell
> - Mid-beat persist after `create_recovery_tranche` (G13 — crash safety)
> - `tranches_deployed` / `tranches_remaining` are unchanged by recovery tranche creation
> - Recovery tranche ID: `f"{parent_id}A"`, `f"{parent_id}B"`, `f"{parent_id}C"` (max 3 shields per parent)
> - Isolation: only `mmmx_margin_guardian.py` may import from `routes.mmm.*`
>
> **Run after building:** `python3 -m pytest webui/backend/routes/mmmx/tests/ -v`
> All 189 prior tests must still pass.

### PHASE 5 — ATM Shield (+ Multi-Shield, Reserve Cascade, Naked Handling) ✅ COMPLETE (2026-04-06)

**Build:**
- `mmmx_atm_shield.py` with full 6-step sequence.
- Extend `mmmx_monitor._heartbeat` to call shield before deployment.
- Extend `mmmx_reconciler` with naked detection hooks (`_naked_positions`).
- Telegram templates for shield fire, reserve depletion, naked warning.

**Functions:**
- `atm_shield.evaluate(session) → List[ShieldCandidate]`
- `atm_shield.sort_by_priority(candidates)` (G38 — worst loss first, tiebreak by oldest)
- `atm_shield.execute_shield(session, candidate) → ShieldResult` (6 steps)
- `atm_shield.run_retry_sell(symbol, size)` — 10 limit + 1 market (Section 6 spec)
- `atm_shield.allocate_reserve(session, loss, new_premiums) → RecoveryAllocation` (G39 — partial or zero cascade)
- `atm_shield.create_recovery_tranche(session, parent, ce_recov, pe_recov)` — sibling naming `2A/2B/2C`
- `atm_shield.multi_shield_margin_precheck(candidates)`

**Dependencies:** Phases 1–4.

**NOT built:** hedger, deployment, listener, profit booking.

**Test criteria:**
- ✅ Position OTM drops to 4.9% → shield fires; buyback → new sell → recovery tranche (2A) created; reserve decremented.
- ✅ Multi-shield same beat: 3 candidates, sorted by loss; execute sequentially; third one reposition-only if reserve exhausted (G39).
- ✅ Shield new-sell fails 11 attempts → session PAUSED, `_naked_positions` populated, Telegram CRITICAL.
- ✅ Naked timeout: simulated 30-min naked → force heartbeat + emergency retry; 2 h → operator alert.
- ✅ Recovery tranche is a first-class citizen: next beat, ATM shield loop iterates it; hard stop closes it; DTE closes it.
- ✅ `tranches_deployed` / `tranches_remaining` unchanged by recovery creation.
- ✅ `last_deployment_spot` and `last_deployment_iv_rank` reset after shield reposition.

> **✅ PHASE 5 COMPLETE — 2026-04-06 — 60 tests (249 total: 69 P1 + 40 P2 + 36 P3 + 44 P4 + 60 P5)**
>
> Files delivered: `mmmx_atm_shield.py` (new), `mmmx_reconciler.py` (+ `check_naked_watchdog`), `mmmx_monitor._heartbeat` (+ steps 4b/4c), `tests/test_phase5.py`. All 249 tests pass.

---

> **NEXT AI — START HERE FOR PHASE 6**
>
> Phase 5 is complete and all 249 tests (69 P1 + 40 P2 + 36 P3 + 44 P4 + 60 P5) pass. You are starting **Phase 6: Deployment Engine (+ Queue, Gates, Whipsaw, Profit Booking)**.
>
> **What exists:** All `webui/backend/routes/mmmx/` Phase 1–5 files. Read them before touching anything, especially:
> - `mmmx_atm_shield.py` — `evaluate_and_fire(session, spot, executor, audit, save_fn)`, `ShieldResult`, `RecoveryAllocation` (Phase 5)
> - `mmmx_engine.py` — `recalc_hard_stop(session)`, `compute_bs_price(...)`, `compute_realized_pnl(...)`, `check_fairness_gate(strike_quote, bs_price, fairness_threshold)` — pure math, no I/O
> - `mmmx_executor.py` — `smart_execute(...)`, `emergency_execute(...)`, `ExecutionResult`
> - `mmmx_monitor.py` — `_heartbeat()` with 5 existing steps; Phase 6 deployment wiring goes at step 6 (after ATM shield 4c, before emit+save)
> - `mmmx_constants.py` — `TrncStatus`, `TrncType`, `SessionStatus`; `CAUTION_SCORE=2`, `RESTRICT_SCORE=3`, `COOLDOWN_SCORE=4` (add if not present)
> - `mmmx_state.py` — `make_tranche()` — use this to create all new tranche dicts
> - `mmmx_close_all.py` — `close_all(session, reason, executor, audit)` — profit booking reuses the same ACTIVE-leg close pattern (but per-tranche, not all)
>
> **Key invariants carried from Phases 1–5 (DO NOT BREAK):**
> - `emit_safety()` is a regular `def` — call directly, NEVER await
> - `_save_session()` returns True/False — ALWAYS check the return value
> - `tranches_deployed` / `tranches_remaining` are incremented on deployment ONLY (integer tranche IDs, type='deployment'). Recovery tranches do NOT change these counters.
> - `ce_reserve_remaining` / `pe_reserve_remaining` are NOT touched by deployment (only by shield reserve allocation)
> - `last_deployment_spot` and `last_deployment_iv_rank` MUST be updated after every successful deployment (used by next beat's trigger evaluation)
> - All timestamps: `datetime.now(timezone.utc).isoformat()` — never naive `utcnow()`
> - Isolation: only `mmmx_margin_guardian.py` may import from `routes.mmm.*`
>
> **What to build (Phase 6):**
>
> **1. `mmmx_initializer.py`** — Entry gates, strike scanning, Tr1 manual deploy, auto Tr2–10 deployment:
> - `check_entry_gates(params, live_data) → EntryVerdict` — validates DTE 20–45, IV rank >= 50, margin < 80%, liquidity (>= 5 lots bid depth, spread < 10%). Hard gates: all must pass or session refuses to start. Returns `EntryVerdict(ok, failed_gates, messages)`.
> - `scan_strikes(asset, expiry, otm_pct, chain) → StrikeCandidates` — finds nearest CE/PE strikes at `otm_distance_pct` from spot. Chain is a list of dicts with `{'strike', 'symbol', 'bid', 'ask', 'delta'}`. No hardcoded step sizes — select strike closest to `spot × (1 ± otm_pct/100)`.
> - `deploy_manual_tranche1(session, executor, audit, ce_symbol, pe_symbol, ce_lots, pe_lots)` — sells CE + PE via `smart_execute`; all-or-nothing (rollback if PE fails); initializes `hard_stop_usd = hard_stop_multiplier × premium_collected`; sets `last_deployment_spot`, `last_deployment_iv_rank`; increments `tranches_deployed`/`tranches_remaining→ -1`; adds tranche to `session['tranches']`; transitions session → RUNNING; Telegram + audit + emit.
> - `check_deploy_conditions(session, metrics) → DeployDecision` — checks: (a) tranches_remaining > 0, (b) whipsaw_score < COOLDOWN (score 4+), (c) spot moved >= adjusted_move_pct from `last_deployment_spot` OR iv_rank increased >= `tranche_deploy_iv_delta`. Returns `DeployDecision(should_deploy, reason, adjusted_size)`.
> - `populate_eligibility_queue(session, spot_move_pct)` — G46 queue: `num_eligible = floor(spot_move_pct / tranche_deploy_move_pct)`; appends next N tranche IDs (up to tranches_remaining) to `session['deployment_eligible_tranches']`; records `deployment_queue_triggered_spot` and direction.
> - `clear_queue_on_retrace(session, current_spot)` — if retracement from `deployment_queue_triggered_spot` >= 0.5%: clear `deployment_eligible_tranches`, log + Telegram.
> - `enforce_frequency_gate(session) → bool` — count deployments in `deployments_last_24h` within last 24h; block if count >= `max_deployments_per_day` (default 2). Returns True if allowed.
> - `enforce_fairness_gate(session, strike_quote, bs_price) → bool` — checks `abs(mid - bs_price) / bs_price <= fairness_threshold` (default 0.10). Returns True if allowed or gate disabled.
> - `execute_tranche_deploy(session, executor, audit, spot, iv_rank, chain, save_fn=None)` → deployed tranche dict or None — runs full pre-flight (frequency + fairness gates), sells CE + PE (smart_execute), all-or-nothing rollback on PE failure, updates session state, calls save_fn (G13 mid-beat persist), Telegram + audit + emit.
>
> **2. `mmmx_whipsaw.py`** — Oscillation scoring and deployment throttling:
> - `score_tick(session, shield_events_since_last) → int` — detects whipsaw from recent shield events within `whipsaw_window_mins` (default 30). Increments `_whipsaw_score` by 1 per detected oscillation; updates `_whipsaw_last_noise_at`. Returns new score.
> - `apply_to_deployment(session, base_move_pct, base_size) → (adjusted_move_pct, adjusted_size)` — per spec: score>=4 → skip (return None,None); score==3 → move×2, size//2; score==2 → move×1.5, size unchanged; score<2 → no change.
> - `decay_score(session) → int` — every beat, if time since last noise > 1 hour AND score > 0: decrement score by 1 (score>=4 decrements by 2 on cooldown expiry). Clear `_whipsaw_skip_until` when score drops below COOLDOWN. Returns new score.
> - `get_level(score) → str` — returns `'NORMAL'|'CAUTION'|'RESTRICT'|'COOLDOWN'`.
>
> **3. `mmmx_profit_booking.py`** — Per-tranche selective close:
> - `queue_close(session, tranche_id, target_pct)` — records `{'tranche_id', 'target_pct', 'queued_at'}` in `session['_profit_booking_queue']`. Validates tranche exists and is ACTIVE.
> - `process_pending(session, executor, audit, save_fn=None) → List[dict]` — iterates `_profit_booking_queue`; for each entry checks if tranche's `realized_pnl_usd >= premium_collected × target_pct / 100`; if yes: calls `close_tranche(session, tranche_id, executor, audit)` and removes from queue; returns list of result dicts.
> - `close_tranche(session, tranche_id, executor, audit) → dict` — closes both CE and PE legs via `smart_execute` (buy-to-close, up to 4 reprice attempts per leg); on success: marks tranche CLOSED, decrements `tranches_deployed`, recalculates `hard_stop_usd`; books profit to `total_realized_pnl`; Telegram + audit. Returns result dict with `success`, `pnl_usd`, `tranche_id`.
>
> **4. Wire into `mmmx_monitor._heartbeat`** (step 6, after ATM shield, before emit+save):
> ```python
> # -- 5. Whipsaw decay + deployment (Phase 6) ----------------------------
> # 5a. Whipsaw score decay
> # 5b. check_deploy_conditions → if should_deploy:
> #       clear_queue_on_retrace; populate_eligibility_queue if queue empty;
> #       pop one tranche from queue; execute_tranche_deploy
> # 5c. process_pending profit booking
> ```
>
> **Key constraints (from MMMX_COMPLETE.md — final authority):**
> - Deployment is step 6 in heartbeat priority order: protection (1–5) ALWAYS beats deployment (6). Shield fires in current beat pre-empt deployment.
> - One tranche deployed per beat (pop one from eligibility queue). Never deploy more than one per heartbeat.
> - All-or-nothing: if PE sell fails, buyback CE immediately; no partial deployment state.
> - Frequency gate rolls 24h window using `deployments_last_24h` list of ISO timestamps.
> - Fairness gate uses `compute_bs_price()` from `mmmx_engine` (already exists).
> - Whipsaw constants live in `mmmx_constants.py` (add if missing): `WHIPSAW_CAUTION_SCORE=2`, `WHIPSAW_RESTRICT_SCORE=3`, `WHIPSAW_COOLDOWN_SCORE=4`.
> - Profit booking: `close_tranche` uses smart_execute (not emergency_execute) — operator-triggered, not crisis.
> - `_profit_booking_queue` is a list on session; survives restart.
> - Recovery tranches (type='recovery') can be profit-booked — `close_tranche` handles them identically.
>
> **Run after building:** `python3 -m pytest webui/backend/routes/mmmx/tests/ -v`
> All 249 prior tests must still pass. New Phase 6 tests are added in `tests/test_phase6.py`.

### PHASE 6 — Deployment Engine (+ Queue, Gates, Whipsaw, Profit Booking) ✅ COMPLETE (2026-04-06)

**Status:** DONE — 71/71 Phase 6 tests passing. 320/320 total (69 P1 + 40 P2 + 36 P3 + 44 P4 + 60 P5 + 71 P6). MMM isolation scan clean.

> **✅ PHASE 6 COMPLETE — 2026-04-06 — 71 tests (320 total: 69 P1 + 40 P2 + 36 P3 + 44 P4 + 60 P5 + 71 P6)**
>
> Files delivered: `mmmx_initializer.py` (new), `mmmx_whipsaw.py` (new), `mmmx_profit_booking.py` (new), `mmmx_constants.py` (+ whipsaw score constants), `mmmx_state.py` (+ `_profit_booking_queue` in session), `mmmx_atm_shield.py` (+ `spot` field in shield events for whipsaw detection), `mmmx_telegram.py` (+ 3 new alert functions), `mmmx_monitor._heartbeat` (+ Phase 6 step 5: whipsaw decay, deploy, profit booking), `tests/test_phase6.py`. All 320 tests pass.

---

> ~~**NEXT AI — START HERE FOR PHASE 7**~~
>
> **✅ PHASE 7 COMPLETE — 2026-04-06 — 65 tests (385 total: 69 P1 + 40 P2 + 36 P3 + 44 P4 + 60 P5 + 71 P6 + 65 P7)**
>
> Files delivered: `mmmx_premium_listener.py` (new — PremiumListener class, 4 Tier-0 CBs, stale-WS watchdog, `_mmmx_listeners` registry with RLock), `mmmx_hedger.py` (new — `schedule_post_deploy`, `tick`, `update_hedge_pnl`, `detect_displacement`), `mmmx_monitor.py` (+ `_force_wake_event`, `signal_force_check()`, step 5d hedger tick, `schedule_post_deploy` wired after tranche deploy, `start/stop_session_listener` co-called with monitor), `tests/test_phase7.py` (65 tests). All 385 tests pass.
>
> ~~Phase 6 is complete and all 320 tests (69 P1 + 40 P2 + 36 P3 + 44 P4 + 60 P5 + 71 P6) pass. You are starting **Phase 7: Premium Listener (+ Tier-0 CBs, Heartbeat Watchdog, Hedger)**.~~
>
> **What exists:** All `webui/backend/routes/mmmx/` Phase 1–6 files. Read them before touching anything, especially:
> - `mmmx_monitor.py` — `_heartbeat()` with 6 steps; `_run_loop` with generation guards; `start_session_monitor()`; the Registry (`_mmmx_monitors`)
> - `mmmx_executor.py` — `smart_execute(...)`, `emergency_execute(...)`, `ExecutionResult`
> - `mmmx_engine.py` — `compute_portfolio_delta()`, `compute_position_pnl()`, `recalc_hard_stop()`, `compute_bs_price()`
> - `mmmx_initializer.py` — `execute_tranche_deploy(...)` — Phase 6 deployment; `_apply_deploy_state()` — the canonical way to record a successful deployment into session state
> - `mmmx_atm_shield.py` — shield fires `_force_check=True` on the session to wake the listener path (see Section 4 MMMX_COMPLETE.md)
> - `mmmx_state.py` — `make_hedge()` — use this to create all hedge dicts; `session['hedges']` list
> - `mmmx_constants.py` — `HedgeStatus`, `TrncStatus`, `TrncType`
> - `mmmx_telegram.py` — existing alert functions; add new ones for CB triggers, hedge events
> - `mmmx_websocket.py` — `emit_heartbeat()`, `emit_safety()`, add `emit_hedge_executed()`, `emit_cb_triggered()`
>
> **Key invariants carried from Phases 1–6 (DO NOT BREAK):**
> - `emit_safety()` is a regular `def` — call directly, NEVER await
> - `_save_session()` returns True/False — ALWAYS check the return value; stale abort on False
> - `_force_check` on the session dict is the listener→monitor signal; listener sets it, monitor reads+clears it each beat
> - Whipsaw detection is already wired in `mmmx_monitor._heartbeat` step 5a/5b; do NOT duplicate in listener
> - All timestamps: `datetime.now(timezone.utc).isoformat()` — never naive `utcnow()`
> - Isolation: only `mmmx_margin_guardian.py` may import from `routes.mmm.*`
> - Hedge capacity threshold: only tranches where `tranches_deployed >= 5` (i.e., Tr5 onward) trigger hedges
> - Hedges do NOT close when parent repositioned (displacement logged as ORPHANED, hedge stays open)
> - Hard stop does NOT close hedges (they are separate exchange positions; logged as ORPHANED)
>
> **What to build (Phase 7):**
>
> **1. `mmmx_premium_listener.py`** — WebSocket subscriber and Tier-0 circuit breaker evaluator:
> - `PremiumListener` class. Runs in its own thread via `start_session_listener(session_id)`. Registered in `_mmmx_listeners` dict alongside `_mmmx_monitors`.
> - `subscribe(session)` — subscribes to live CE/PE bid-ask ticks on the Delta Exchange WS (use `mmmx_delta_ws` or the existing `delta_price_websocket` service). Tick format: `{'symbol', 'bid', 'ask', 'timestamp'}`.
> - `on_tick(tick, session)` — updates `session['live_quotes'][symbol]` with latest bid/ask; calls `evaluate_cbs(tick, session)`.
> - `evaluate_cbs(tick, session) → List[str]` — evaluates 4 Tier-0 circuit breakers. Each CB sets `session['_force_check'] = True` when triggered, logs + Telegrams. Returns list of triggered CB names:
>   - `CB_PREMIUM_JUMP`: any leg premium jumps > 50% in one tick vs its `entry_premium`
>   - `CB_DELTA_BLOWOUT`: `compute_portfolio_delta(session)` returns abs value > `emergency_delta` (0.70)
>   - `CB_IV_FLASH_SPIKE`: IV (from tick metadata if available) > `iv_catastrophe_pct` (80%)
>   - `CB_NEAR_ITM`: any position delta >= 0.72 → executes 50% reduce via `emergency_execute` immediately, THEN forces heartbeat
> - `force_heartbeat(reason)` — sets `session['_force_check'] = True`; logs the reason; increments `_listener_force_count`.
> - `check_stale_ws(session)` — 5-min watchdog: if no tick received in 5 min → `force_heartbeat('stale_ws')` + Telegram WARNING. If both WS and monitor heartbeat are stale (check `session['last_beat_at']`) → Telegram CRITICAL.
> - `stop()` — graceful shutdown; clears subscription; removes from `_mmmx_listeners`.
>
> **2. `mmmx_hedger.py`** — Deferred BTC spot buy after Tr5+ deployment:
> - `schedule_post_deploy(session, tranche_id, deployed_at)` — only if `tranches_deployed >= 5` (total deployed lots threshold from `hedge_capacity_threshold_lots` param, default 50 lots). Appends to `session['_hedge_schedule']`: `{'tranche_id', 'execute_after': deployed_at + hedge_execution_delay_minutes, 'lots': hedge_lots, 'status': 'PENDING'}`.
> - `tick(session, executor, audit) → List[dict]` — called from `_heartbeat` step 5b (after deployment). Checks each PENDING schedule entry; if `now >= execute_after`: calls `executor.smart_execute(side='buy', symbol='BTC-SPOT', ...)` to buy the hedge lots. On success: creates hedge via `make_hedge(...)`, appends to `session['hedges']`, marks schedule entry DONE. Returns list of executed hedge dicts.
> - `update_hedge_pnl(session, live_quotes)` — called each beat. For each ACTIVE hedge in `session['hedges']`: computes unrealized P&L from current spot vs `entry_price`; updates `hedge['unrealized_pnl']`.
> - `detect_displacement(session, repositioned_parent_id)` — when a tranche is repositioned by ATM shield: find its associated hedge (if any); mark it `status=ORPHANED`; log + Telegram; do NOT close it.
>
> **3. Wire into `mmmx_monitor._heartbeat`** (after step 5c profit booking, before step 6 emit+save):
> ```python
> # -- 5d. Hedger tick (Phase 7) ------------------------------------------
> # Execute any scheduled hedges whose delay has elapsed
> # Update unrealized P&L for all active hedges
> # -- 5e. _force_check consumed here: if set, was already consumed by listener
> #        via run_loop; clear it for next beat
> ```
> Also: in `_run_loop`, after loading fresh session: if `session['_force_check']` is True, run `_heartbeat()` immediately (skip sleep) and clear the flag.
>
> **4. Wire `start_session_listener` alongside `start_session_monitor`** in `mmmx_monitor.py`. When a session starts RUNNING, both monitor and listener threads start. Listener thread must also respect the stale-generation pattern (check `_mmmx_listeners[session_id]` generation matches).
>
> **Key constraints (from MMMX_COMPLETE.md — final authority):**
> - `CB_NEAR_ITM` is the ONLY CB that executes orders directly (50% reduce via `emergency_execute`). All other CBs only set `_force_check = True`.
> - Hedger uses `smart_execute`, NOT `emergency_execute` — deferred hedge buy is not urgent.
> - `hedge_execution_delay_minutes` default = 15. Configurable via session params (hot-reloadable).
> - Hedge lots formula: `floor(total_deployed_lots × hedge_pct / 100)` where `hedge_pct` is a param (default from spec). See `MMMX_COMPLETE.md` Section 7.
> - Listener thread MUST NOT mutate session state except for `session['live_quotes']`, `session['_force_check']`, and `session['_listener_force_count']` — all other state mutations go through `_heartbeat`.
> - `CB_NEAR_ITM` is the exception: it calls `emergency_execute` and records the reduce in session immediately (emergency path, not via heartbeat).
> - `_mmmx_listeners` registry follows the same pattern as `_mmmx_monitors` — same generation-bump logic on restart.
> - `check_stale_ws` watchdog reads `session['last_beat_at']` (set by `_run_loop` each beat) to detect a frozen monitor.
>
> **Run after building:** `python3 -m pytest webui/backend/routes/mmmx/tests/ -v`
> All 320 prior tests must still pass. New Phase 7 tests go in `tests/test_phase7.py`.

**Build:**
- `mmmx_initializer.py` — entry gates, strike scanning, liquidity validation, manual Tr1 deploy, auto Tr2–10
- `mmmx_whipsaw.py` — score, decay, cooldown
- `mmmx_profit_booking.py` — per-tranche selective close
- Wire deploy/whipsaw/profit-booking into `monitor._heartbeat`

**Functions:**
- `initializer.check_entry_gates(params, live_data) → EntryVerdict`
- `initializer.scan_strikes(asset, expiry, otm_pct) → StrikeCandidates`
- `initializer.deploy_manual_tranche1(session, operator_selection)` (manual)
- `initializer.check_deploy_conditions(session, metrics) → DeployDecision`
- `initializer.populate_eligibility_queue(session, spot_move_pct)`
- `initializer.clear_queue_on_retrace(session, current_spot)`
- `initializer.enforce_frequency_gate(session)` (Q30: max 2/24h)
- `initializer.enforce_fairness_gate(session, strike_quote, bs_price)` (Q_FAIRNESS)
- `initializer.execute_tranche_deploy(session, strike_plan)` — all-or-nothing CE+PE sell with rollback
- `whipsaw.score_tick(session, recent_shield_events)`, `whipsaw.apply_to_deployment(session, base)`
- `profit_booking.queue_close(session, tranche_id, target_pct)`, `profit_booking.process_pending(session)`

**Dependencies:** Phases 1–5.

**NOT built:** hedger, listener, full UI.

**Test criteria:**
- Entry gates reject DTE=19, IV rank=49, margin=85% with specific messages; accept valid inputs.
- Strike scan uses live chain; no hardcoded step sizes (mocked chain with irregular ladder passes).
- Manual Tr1 deploy flows through fairness+frequency gates; rollback on PE failure leaves no state mutation.
- 6.4% simulated move populates queue [Tr2,Tr3,Tr4]; deploys one/beat; >0.5% retrace clears queue.
- Whipsaw: oscillating shield events accumulate score; CAUTION widens triggers +50%; RESTRICT halves tranche size; COOLDOWN sets `_whipsaw_skip_until`; decay reduces score each clean interval.
- Profit booking: Tr1 target 15% closes at +$15 while Tr2 target 20% holds at +$8; capacity freed; hard stop recalculates down.
- Recovery tranche can be profit-booked independently.
- Frequency gate: 3rd deploy attempt in 24 h blocked.

### PHASE 7 — Premium Listener (+ Tier-0 CBs, Heartbeat Watchdog)

**Build:**
- `mmmx_premium_listener.py` with WebSocket subscription to live CE/PE bid-ask.
- Tier-0 circuit breakers (4): `CB_PREMIUM_JUMP`, `CB_DELTA_BLOWOUT`, `CB_IV_FLASH_SPIKE`, `CB_NEAR_ITM`.
- Heartbeat delay watchdog (G41) inside listener.
- Integration with monitor via `_force_check` flag.
- Hedger partially wired: `mmmx_hedger.py` implemented here so hedges start populating once deployment Phase 6 exists. (Hedger execution was postponed to this phase to avoid stale hedges during execution tests in Phase 6.)

**Functions:**
- `listener.subscribe(session)`, `listener.on_tick(tick)`, `listener.evaluate_cbs(tick)`
- `listener.force_heartbeat(reason)`
- `listener.check_stale_ws()` (5-min watchdog; also checks monitor heartbeat)
- `hedger.schedule_post_deploy(session, tranche_id, deployed_at)` — only if total_deployed_lots ≥ 50
- `hedger.tick(session)` — execute scheduled buys whose delay elapsed
- `hedger.update_hedge_pnl(session, quotes)`
- `hedger.detect_displacement(session, repositioned_parent_id)`

**Dependencies:** Phases 1–6.

**NOT built:** UI, watchdog supervisor, full fault-tolerance suite (comes in Phase 9).

**Test criteria:**
- Synthetic WS ticks trigger each CB; `_force_check` becomes True; heartbeat runs outside schedule.
- `CB_NEAR_ITM` (δ≥0.72) executes 50% reduce via executor immediately, then forces heartbeat.
- Stale WS (no ticks for 5 min) → force heartbeat + Telegram warning.
- Both WS and heartbeat stale → critical escalation.
- Hedge: Tr5 deployment schedules H-Tr5 for +15 min; hedger.tick executes buys; state populated; hedges do not close when parent repositioned (displacement logged).
- Tr1–Tr4 never produce hedges (capacity threshold).
- Hard stop leaves hedges open (orphaned but alive).

---

> ~~**NEXT AI — START HERE FOR PHASE 8**~~
> ✅ PHASE 8 COMPLETE — 2026-04-06 — 43 tests (428 total)
>
> ~~Phase 7 is complete and all 385 tests (69 P1 + 40 P2 + 36 P3 + 44 P4 + 60 P5 + 71 P6 + 65 P7) pass. You are starting **Phase 8: UI + Hot Reload (WebUI Integration)**.~~
>
> **Repo:** `/Users/ssr/Projects/WorkingBot`
> **Working branch:** `SSR`
> **Run backend tests with:** `python3 -m pytest webui/backend/routes/mmmx/tests/ -v`
> **All new backend tests go in:** `webui/backend/routes/mmmx/tests/test_phase8.py`
> **Frontend:** React/MUI, no build step required for dev — changes are served live.
>
> ---
>
> ## CRITICAL: Read these files FULLY before writing a single line
>
> **Backend (read all of these):**
> - `webui/backend/routes/mmmx/mmmx_api.py` — **10 routes already exist**; see exact list below. Do NOT recreate what exists. Add only what's missing.
> - `webui/backend/routes/mmmx/mmmx_config.py` — `HOT_RELOAD_ALLOWLIST` and `validate_hot_reload_patch()` **already exist**. Do NOT rewrite them. The `PATCH /params` endpoint skeleton also already exists — complete its implementation.
> - `webui/backend/routes/mmmx/mmmx_param_audit.py` — `record_param_change()` and `get_param_history()` already implemented. Use them directly.
> - `webui/backend/routes/mmmx/mmmx_websocket.py` — **15 emit functions already exist** (heartbeat, safety, status_change, tranche_deployed, tranche_closed, atm_shield, hedge_executed, pnl_update, params_changed, deployment_queue, whipsaw_update, circuit_breaker, naked_position, session_created, session_stopped). No new emitters needed for Phase 8.
> - `webui/backend/routes/mmmx/mmmx_monitor.py` — `start_session_monitor()`, `stop_session_monitor()`, `signal_force_check()`. Note: `stop_session_monitor()` ALSO stops the listener. Pause must NOT call this — see Pause invariant below.
> - `webui/backend/routes/mmmx/mmmx_state.py` — `transition_status()`, `create_session()`, `apply_session_defaults()`
> - `webui/backend/routes/mmmx/mmmx_engine.py` — `recalc_hard_stop(session)` (returns float, does NOT mutate session)
> - `webui/backend/routes/mmmx/mmmx_initializer.py` — `deploy_manual_tranche1()`, `check_entry_gates()`, `scan_strikes()`
> - `webui/backend/routes/mmmx/mmmx_profit_booking.py` — `queue_close()`, `process_pending()`
> - `webui/backend/routes/mmmx/mmmx_reconciler.py` — `reconcile_with_exchange()`
> - `webui/backend/routes/mmmx/mmmx_constants.py` — `CLOSE_AT_DTE_HARD_MIN = 7`, `SessionStatus`, `LEGAL_TRANSITIONS`
>
> **Frontend (read all of these):**
> - `webui/frontend/src/App.js` — lazy-import + route pattern (copy MMM pattern exactly)
> - `webui/frontend/src/config/navigationSections.js` — tab structure; add `mmmx` entry to 'Algorithms' group
> - `webui/frontend/src/context/AppProviders.js` — provider nesting; add `MMMXProvider` after `SymbolProvider`
> - `webui/frontend/src/components/mmm/MMMSettingsDialog.js` — MUI style reference for parameter editor (Dialog, TextField, Switch, Tooltip, color-coded categories)
> - `webui/frontend/src/pages/MMMPage.js` (if it exists) — page wrapper pattern to replicate for `MMMXPage.js`
>
> ---
>
> ## What already exists in mmmx_api.py (DO NOT rebuild)
>
> ```
> POST   /api/mmmx/session                        → create session
> GET    /api/mmmx/sessions                        → list all sessions
> GET    /api/mmmx/session/<id>                    → get session by ID
> PATCH  /api/mmmx/session/<id>/params             → hot-reload (SKELETON EXISTS — complete it)
> POST   /api/mmmx/session/<id>/stop               → stop monitor + transition COMPLETE
> POST   /api/mmmx/session/<id>/start-monitor      → restart monitor thread
> GET    /api/mmmx/session/<id>/audit              → audit log
> GET    /api/mmmx/session/<id>/activity           → activity log
> GET    /api/mmmx/session/<id>/param-history      → param change history
> GET    /api/mmmx/health                          → system health
> ```
>
> ---
>
> ## What to build
>
> ### 1. Complete `PATCH /api/mmmx/session/<id>/params` (skeleton exists, needs full logic)
>
> The endpoint skeleton exists. Complete its implementation:
> - Call `mmmx_config.validate_hot_reload_patch(patch)` — already validates allowlist + ranges.
> - Split result into `applied` (allowed keys) and `rejected` (disallowed keys with reason string).
> - For `close_at_dte`: the hard-min check is already in `validate_hot_reload_patch`. Ensure error message says "close_at_dte must be >= 7 (gamma-risk hard floor)".
> - Merge `applied` keys into `session['params']`.
> - If `hard_stop_multiplier` is in `applied`: call `recalc_hard_stop(session)`, set `session['hard_stop_usd'] = new_value`, persist.
> - Call `mmmx_param_audit.record_param_change(session_id, old_params, new_params)` — records both accepted changes and the rejection audit trail.
> - Save session (generation-checked via `_save_session`-style save).
> - Emit `emit_params_changed(session_id, diff)` — already exists in websocket module.
> - Response: `{ok: true, applied: {k: v}, rejected: {k: reason}, audit_id: "..."}` HTTP 200 even when some keys rejected (partial success). HTTP 422 only when ALL keys rejected or validation error is fatal.
>
> **Bug to fix in `mmmx_config.py`:** `hedge_distance_pct` min bound is currently `1.0` — it must be `10.0` per spec (Section 5.1: "hedge_distance_pct 10–50"). Fix this before implementing the endpoint.
>
> ### 2. New manual action endpoints (add to `mmmx_api.py`)
>
> **`POST /api/mmmx/session/<id>/pause`**
> - Load session. Must be RUNNING (else 409 with current status in message).
> - Call `transition_status(session, SessionStatus.PAUSED, reason='operator_pause')`.
> - Stop ONLY the monitor: call `monitor.stop(reason='operator_pause')` directly on the `MMMXMonitor` instance from `get_monitor(session_id)`. **Do NOT call `stop_session_monitor()` — that also kills the listener.**
> - **The Premium Listener MUST remain alive during PAUSE** (positions are still open; CB_NEAR_ITM protection must keep running).
> - Save session. Emit `emit_status_change(session_id, 'RUNNING', 'PAUSED', 'operator_pause')`.
> - Telegram alert: "⏸ Session paused by operator. Listener still active."
> - Response: `{ok: true, status: 'PAUSED'}`.
>
> **`POST /api/mmmx/session/<id>/resume`**
> - Load session. Must be PAUSED (else 409).
> - Call `transition_status(session, SessionStatus.RUNNING, reason='operator_resume')`.
> - Call `start_session_monitor(session_id)` — this restarts the monitor (bumps generation, co-starts listener if not alive).
> - Save session. Emit `emit_status_change(session_id, 'PAUSED', 'RUNNING', 'operator_resume')`.
> - Response: `{ok: true, status: 'RUNNING'}`.
>
> **`GET /api/mmmx/session/<id>/scan_strikes`** (query params: `otm_pct=15`)
> - Loads session. Must be GATES_PASSED or RUNNING.
> - Calls `initializer.scan_strikes(asset='BTC', expiry=session['expiry_ddmmyy'], otm_pct=otm_pct, chain=[], spot=None)` — chain/spot are None here; scan_strikes must handle None gracefully (return empty list with reason, not raise).
> - In live system, chain comes from the WS feed; for now returns `{ok: true, candidates: [], reason: "no_live_chain"}` if chain unavailable.
> - Response: `{ok: true, ce_candidates: [...], pe_candidates: [...]}`.
>
> **`POST /api/mmmx/session/<id>/deploy_tranche1`**
> - Body: `{ce_symbol, ce_strike, pe_symbol, pe_strike, lots}`.
> - Must be RUNNING (else 409).
> - Calls `await initializer.deploy_manual_tranche1(session, executor, audit, ce_symbol=..., pe_symbol=..., ce_strike=..., pe_strike=..., lots=..., spot=None, iv_rank=None, chain=[])`.
> - Saves session on success. Returns `{ok: true, tranche: <tranche_dict>}`.
> - On failure: returns `{ok: false, reason: <str>}` HTTP 422.
>
> **`POST /api/mmmx/session/<id>/profit_book`**
> - Body: `{tranche_id: int|str, target_pct: float}`.
> - Must be RUNNING (else 409).
> - Calls `profit_booking.queue_close(session, tranche_id, target_pct)`.
> - Saves session. Returns `{ok: true, queue: session['_profit_booking_queue']}`.
>
> **`POST /api/mmmx/session/<id>/reconcile`**
> - Calls `await reconciler.reconcile_with_exchange(session)`.
> - Returns `ReconReport` serialized as JSON. `{ok: true, report: {...}}`.
>
> ### 3. Frontend — new files to create
>
> **Folder:** `webui/frontend/src/components/mmmx/`
>
> **`MMMXContext.js`**
> ```javascript
> // React context. Subscribes to all mmmx_* SocketIO events.
> // Exposes: { session, tranches, hedges, risk, activity, isConnected }
> // session: full session dict from GET /api/mmmx/session/<id>
> // tranches: session.tranches array (derived)
> // hedges: session.hedges array (derived)
> // risk: { portfolio_delta, portfolio_pnl, hard_stop_usd, whipsaw_score, circuit_breaker_state,
> //         imbalance_pct, last_beat_at, last_price_update_at, naked_positions }
> // activity: last 50 activity log entries
> // Updates on: mmmx_heartbeat, mmmx_pnl_update, mmmx_tranche_deployed, mmmx_tranche_closed,
> //             mmmx_atm_shield, mmmx_hedge_executed, mmmx_whipsaw_update, mmmx_params_changed,
> //             mmmx_safety, mmmx_status_change, mmmx_deployment_queue
> ```
>
> **`useMMMXWebSocket.js`** — hook that subscribes to the socket prop and dispatches to MMMXContext.
>
> **`mmmxService.js`** — REST client. Functions:
> ```javascript
> getSession(id), listSessions(),
> hotReloadParams(id, patch),
> pauseSession(id), resumeSession(id),
> deployTranche1(id, payload), profitBook(id, trancheId, targetPct),
> reconcile(id), scanStrikes(id, otmPct),
> getAuditLog(id), getActivityLog(id), getParamHistory(id)
> ```
>
> **`MMMXDashboard.js`** — top-level component. 7 MUI Tabs:
>
> | Tab | Key fields to display |
> |---|---|
> | **Status** | Status badge (color-coded), beat number, next beat countdown, `hard_stop_usd` progress bar vs `portfolio_pnl`, `total_premium_collected`, `profit_booked_total`, `total_hedge_cost_paid`, `tranches_deployed`/`tranches_remaining`, `ce_reserve_remaining`/`pe_reserve_remaining`, Pause/Resume buttons |
> | **Tranches** | Table: `tranche_id`, type, CE symbol+strike+lots+premium+delta, PE symbol+strike+lots+premium+delta, `premium_collected`, `unrealized_pnl`, status badge, `close_reason` |
> | **Hedges** | Table: `hedge_id`, `parent_tranche_id`, status (ACTIVE/ORPHANED — color), `hedge_premium_paid`, CE/PE unrealized P&L, `hedge_executed_at`, `displaced_from_parent_at` if orphaned |
> | **Risk** | Delta gauge (-1 to +1), `ce_lot_balance.imbalance_pct` bar, whipsaw score (0–4+) badge with level label (NORMAL/CAUTION/RESTRICT/COOLDOWN), circuit breaker state chip, `_naked_positions` alert if non-empty, `_last_beat_at` timestamp (heartbeat health), `_last_price_update_at` (listener health), `deployment_eligible_tranches` queue if non-empty |
> | **Adjustments** | Live activity feed from `GET /api/mmmx/session/<id>/activity` — shield fires, deploy events, CB fires, hard stop, whipsaw changes, profit bookings; auto-refresh on WS events |
> | **Profit Booking** | Per-active-tranche row: `tranche_id`, current P&L, current P&L%, target selector (10/20/30/50%), "Book Now" button → calls `profitBook()`; `_profit_booking_queue` status |
> | **Parameters** | Two-column table: param name, current value, input field (allowlisted params editable, others greyed out with lock icon); Diff preview panel showing pending changes; Submit button → calls `hotReloadParams()`; param history accordion |
>
> **`MMMXPage.js`** — thin page wrapper (create in `webui/frontend/src/pages/`):
> ```javascript
> import MMMXDashboard from '../components/mmmx/MMMXDashboard';
> export default function MMMXPage({ socket }) {
>   return <MMMXDashboard socket={socket} />;
> }
> ```
>
> ### 4. Frontend wiring
>
> **`navigationSections.js`** — add to 'Algorithms' group:
> ```javascript
> { id: 'mmmx', label: '📈 MMMX', icon: TrendingUp, description: 'MMMX — Options selling algorithm', group: 'Algorithms' }
> ```
>
> **`App.js`** — add lazy import + route (exact same pattern as MMM):
> ```javascript
> const MMMXPage = React.lazy(() => import('./pages/MMMXPage'));
> // in <Routes>:
> <Route path="/mmmx" element={<MMMXPage socket={socket} />} />
> ```
>
> **`AppProviders.js`** — wrap `MMMXContext.Provider` inside the existing provider tree, after `SymbolProvider`.
>
> ---
>
> ## Critical invariants (DO NOT BREAK)
>
> - `emit_safety()` is a regular `def` — call directly, NEVER await or wrap in `run_until_complete`.
> - `_save_session()` returns `True/False` — ALWAYS check the return value.
> - **PAUSE stops the monitor heartbeat only. The Premium Listener MUST keep running.** Never call `stop_session_monitor()` from the pause endpoint — that kills the listener too. Call `monitor.stop()` directly.
> - **RESUME calls `start_session_monitor()` which co-starts a fresh listener** (same generation logic). If listener is already alive from the pause period, `start_session_monitor()` will replace it correctly.
> - Hot-reload NEVER changes `entry_dte_min/max`, `total_budget_lots`, `tranche_pct`, `otm_distance_pct`.
> - `close_at_dte` hot-reload allowed but hard-blocked below `CLOSE_AT_DTE_HARD_MIN = 7`.
> - `hedge_distance_pct` min is `10.0` (fix the `1.0` bug in mmmx_config.py's `_NUMERIC_BOUNDS`).
> - `transition_status(session, new_status)` raises `ValueError` on illegal transitions — catch it and return HTTP 409.
> - `adjust_interval_hours` and `hedge_distance_pct` changes apply at **next beat** (monitor reads `session['params']` fresh each beat). `hedge_distance_pct` applies only to hedges not yet executed.
> - MMM UI and backend MUST remain untouched — ZERO changes to `routes/mmm/` or `components/mmm/`.
> - Isolation: ZERO imports from `routes.mmm.*` in any `mmmx_*.py` file.
> - All timestamps: `datetime.now(timezone.utc).isoformat()` — never naive `utcnow()`.
>
> ---
>
> ## Test criteria (all must pass in `test_phase8.py`)
>
> **Hot-reload:**
> - `hard_stop_multiplier` 2.0 → 3.0: applied to `session['params']`; `hard_stop_usd` recalculated and saved; audit entry written with old→new diff.
> - `close_at_dte=6` → rejected (HTTP 422 or in `rejected` dict), message contains "gamma-risk" or "hard floor"; audit records the rejection attempt.
> - `close_at_dte=7` → accepted (at the exact hard floor).
> - `entry_dte_min` → rejected with "not hot-reloadable" reason; in `rejected` dict.
> - Mixed patch `{hard_stop_multiplier: 3.0, entry_dte_min: 15}` → `hard_stop_multiplier` in `applied`, `entry_dte_min` in `rejected`; HTTP 200.
> - `PATCH` to unknown `session_id` → 404.
> - `hedge_distance_pct=5.0` → rejected (below new min of 10.0).
> - `hedge_distance_pct=10.0` → accepted.
>
> **Pause/Resume:**
> - RUNNING → pause → status=PAUSED; monitor is stopped (`monitor.is_alive()` = False); listener is still alive (`listener.is_alive()` = True).
> - PAUSED → pause again → HTTP 409 (illegal transition).
> - PAUSED → resume → status=RUNNING; new monitor started.
> - COMPLETE → resume → HTTP 409.
>
> **Scan strikes:**
> - `GET /api/mmmx/session/<id>/scan_strikes?otm_pct=15` on GATES_PASSED session → HTTP 200, `{ok: true, ce_candidates: [...], pe_candidates: [...]}` or `{reason: "no_live_chain"}`.
> - On DRAFT session → 409 or 422.
>
> **Deploy Tranche 1:**
> - Valid body on RUNNING session → calls `deploy_manual_tranche1`; session saved; response contains `tranche` dict.
> - Missing required fields in body → HTTP 422.
>
> **Profit book:**
> - Valid `{tranche_id, target_pct}` on RUNNING session → `_profit_booking_queue` entry created; saved; returned in response.
> - Invalid `tranche_id` → HTTP 422.
>
> **All 385 prior tests must still pass.**

### PHASE 8 — UI + Hot Reload (WebUI Integration)

**Build (backend hot-reload):**
- Hot-reload endpoint `PATCH /api/mmmx/session/<id>/params` applies only allowlisted params; rejects disallowed; writes `mmmx_param_audit`.
- Validator: `mmmx_config.validate_hot_reload(diff)` — uses allowlist from Section 5 below.
- Propagation: new params visible at next beat (monitor reads `session['params']` fresh each beat). `hedge_distance_pct` applies only to future hedges.
- Manual action endpoints: `POST /api/mmmx/session/<id>/deploy_tranche1`, `POST /api/mmmx/session/<id>/pause`, `POST /api/mmmx/session/<id>/resume`, `POST /api/mmmx/session/<id>/profit_book`, `POST /api/mmmx/session/<id>/reconcile`.

**Build (frontend):**
- `webui/frontend/src/components/mmmx/` folder
- `MMMXContext.js` — React context, subscribes to `mmmx_*` WebSocket events
- `useMMMXWebSocket.js`
- `mmmxService.js` — REST client
- `MMMXDashboard.js` — MVP tabs: Status, Tranches, Hedges, Risk, Adjustments, Profit Booking, Parameters
- `App.js` lazy import + nav tab; `navigationSections.js` entry
- Parameter editor with validation (client-side mirrors server allowlist) + audit-aware diff preview

**NOT built:** advanced charts, historical analytics (post-MVP).

**Test criteria:**
- Hot-reload `hard_stop_multiplier` from 2.0 → 3.0 visible in next beat; audit log shows diff; active hard_stop_usd recomputes on next persist.
- Attempt to hot-reload `close_at_dte=6` → rejected with gamma-risk message; audit entry records the rejection.
- Attempt to hot-reload `entry_dte_min` → rejected (not in allowlist).
- Profit booking from UI: pick Tr3, target 20% → server queues → monitor processes on next beat.
- WebSocket events render correctly on dashboard for: heartbeat, shield fire, deployment, hedge executed, hard stop, whipsaw level changes, reconciliation needed.
- MMM UI untouched.

> ~~**NEXT AI — START HERE FOR PHASE 9**~~
>
> ✅ **PHASE 9 COMPLETE — 2026-04-06 — 35 tests (463 total: 69 P1 + 40 P2 + 36 P3 + 44 P4 + 60 P5 + 71 P6 + 65 P7 + 43 P8 + 35 P9)**
>
> ~~Phase 8 is complete and all 428 tests (69 P1 + 40 P2 + 36 P3 + 44 P4 + 60 P5 + 71 P6 + 65 P7 + 43 P8) pass. You are starting **Phase 9: Fault Tolerance (Watchdog, Reconciliation, Restart)**.~~
>
> **Repo:** `/Users/ssr/Projects/WorkingBot`
> **Working branch:** `SSR`
> **Run backend tests with:** `python3 -m pytest webui/backend/routes/mmmx/tests/ -v`
> **All new backend tests go in:** `webui/backend/routes/mmmx/tests/test_phase9.py`
>
> ---
>
> ## CRITICAL: Read these files FULLY before writing a single line
>
> - `webui/backend/routes/mmmx/mmmx_monitor.py` — `start_session_monitor()`, `stop_session_monitor()`, `get_monitor()`, `get_all_monitors()`, `_mmmx_monitors` registry, generation guard (Layers 1-3)
> - `webui/backend/routes/mmmx/mmmx_premium_listener.py` — `start_session_listener()`, `stop_session_listener()`, `get_listener()`, `_mmmx_listeners` registry, `_listeners_lock` (RLock), watchdog thread, generation guard
> - `webui/backend/routes/mmmx/mmmx_reconciler.py` — `reconcile_with_exchange(session) → ReconciliationReport`, `ReconciliationReport` dataclass, `PartialResidual` tracking, `tick_partials(session)`
> - `webui/backend/routes/mmmx/mmmx_storage.py` — `bump_generation()`, `load_session()`, `save_session()`, `GenerationConflict`, `get_storage()`
> - `webui/backend/routes/mmmx/mmmx_state.py` — `transition_status()`, `initialize_reverse_state()`, `SessionStatus`
> - `webui/backend/routes/mmmx/mmmx_constants.py` — `NAKED_WATCHDOG_WARN_MINS=30`, `NAKED_WATCHDOG_CRITICAL_MINS=120`, `BEING_CLOSED_TTL_SECS=180`, `SessionStatus`
> - `webui/backend/routes/mmmx/mmmx_api.py` — existing 16 routes (see list below). `POST /reconcile` already exists. Add `POST /confirm-reconcile` only.
> - `webui/backend/routes/mmmx/mmmx_safety.py` — `emit_safety()` is a regular `def` (NEVER await)
>
> ---
>
> ## What already exists (DO NOT rebuild)
>
> **API routes (all 16 exist in mmmx_api.py):**
> ```
> POST   /api/mmmx/session
> GET    /api/mmmx/sessions
> GET    /api/mmmx/session/<id>
> PATCH  /api/mmmx/session/<id>/params
> POST   /api/mmmx/session/<id>/stop
> POST   /api/mmmx/session/<id>/start-monitor
> GET    /api/mmmx/session/<id>/audit
> GET    /api/mmmx/session/<id>/activity
> GET    /api/mmmx/session/<id>/param-history
> GET    /api/mmmx/health
> POST   /api/mmmx/session/<id>/pause
> POST   /api/mmmx/session/<id>/resume
> GET    /api/mmmx/session/<id>/scan_strikes
> POST   /api/mmmx/session/<id>/deploy_tranche1
> POST   /api/mmmx/session/<id>/profit_book
> POST   /api/mmmx/session/<id>/reconcile          ← already exists
> ```
>
> **reconcile_with_exchange** already exists in `mmmx_reconciler.py`. The Phase 9 goal is:
> 1. Build `mmmx_watchdog.py` (new file).
> 2. Build `init_mmmx.py` (new file) for startup landing.
> 3. Add `POST /api/mmmx/session/<id>/confirm-reconcile` to `mmmx_api.py`.
> 4. Extend `reconcile_with_exchange` with `apply_recon_confirmation(session, operator_decision)`.
> 5. Complete the naked-position watchdog escalation path (WARN at 30 min, CRITICAL at 2 h).
> 6. Add `_being_closed` TTL cleanup on startup.
>
> ---
>
> ## What to build
>
> ### 1. `mmmx_watchdog.py` (new)
>
> Supervisor thread that polls `_mmmx_monitors` and `_mmmx_listeners` every 30 seconds.
>
> ```python
> class MMMXWatchdog:
>     def start() → None           # start daemon thread
>     def stop() → None
>     def tick() → None            # single poll cycle (testable)
>     def _restart_monitor(session_id: str) → None
>     def _restart_listener(session_id: str) → None
>
> def get_watchdog() → MMMXWatchdog   # singleton
> ```
>
> Invariants:
> - Watchdog calls `start_session_monitor(session_id)` on dead monitor only if session status is RUNNING.
> - Watchdog calls `start_session_listener(session_id, gen, executor)` on dead listener only if session is RUNNING.
> - Watchdog does NOT restart monitors for PAUSED/COMPLETE/ERROR sessions.
> - Watchdog logs WARN on restart; sends Telegram alert (dedup TTL 300s).
> - Generation is ALWAYS bumped by `start_session_monitor()` — watchdog never sets generation manually.
> - Isolation: ZERO imports from `routes.mmm.*`.
>
> ### 2. `init_mmmx.py` (new)
>
> ```python
> def on_startup() → None
> ```
>
> Called once when the Flask app starts. Steps:
> 1. Load all sessions from DB (`storage.list_sessions()`).
> 2. For each RUNNING session: transition to PAUSED (`transition_status(session, 'PAUSED', reason='startup_landing')`), save, send Telegram "Session landed PAUSED — manual reconciliation required".
> 3. For each session: clear expired `_being_closed` guards (entries older than `BEING_CLOSED_TTL_SECS`).
> 4. Restore `_whipsaw` state if present (no mutation needed — it's persisted in the session dict).
> 5. Start the global watchdog: `get_watchdog().start()`.
>
> ### 3. Naked position watchdog escalation (extend `mmmx_monitor.py` `_heartbeat`)
>
> The existing naked-position detection in `_heartbeat` must be extended with time-based escalation:
> - `_naked_positions` persists position symbols with their first-seen timestamp.
> - If a naked position has existed for `NAKED_WATCHDOG_WARN_MINS` (30 min): send Telegram WARNING (dedup 1800s).
> - If `NAKED_WATCHDOG_CRITICAL_MINS` (2 h): send Telegram CRITICAL (dedup 7200s).
> - Naked positions are cleared from `_naked_positions` when the divergence resolves (position closed or matched).
>
> ### 4. `apply_recon_confirmation` (extend `mmmx_reconciler.py`)
>
> ```python
> def apply_recon_confirmation(session: Dict, operator_decision: Dict) → None
> ```
>
> `operator_decision`: `{divergence_id: str, action: 'accept_db'|'accept_exchange'|'manual_close', notes: str}`
>
> - `accept_db`: logs that operator confirms DB state is correct; marks divergence resolved.
> - `accept_exchange`: forces session state to match exchange (updates tranche status).
> - `manual_close`: marks the divergence as requiring manual close on exchange; adds to `_naked_positions`.
>
> ### 5. New API endpoint: `POST /api/mmmx/session/<id>/confirm-reconcile`
>
> Body: `{divergence_id, action, notes}`
> - Loads session.
> - Calls `apply_recon_confirmation(session, body)`.
> - Saves session.
> - Returns `{ok: true, session_id}`.
>
> ### 6. Frontend additions to MMMXDashboard.js
>
> - **Reconcile tab** (new 8th tab): show `ReconciliationReport` from `POST /reconcile`; per-divergence action buttons (Accept DB / Accept Exchange / Manual Close) calling `POST /confirm-reconcile`.
> - **Watchdog status** in Status tab: show `{watchdog_alive: bool, last_watchdog_tick: timestamp}` from `GET /health`.
>
> ---
>
> ## Critical invariants (DO NOT BREAK)
>
> - `emit_safety()` is a regular `def` — NEVER await or wrap in `run_until_complete`.
> - `_save_session()` returns `True/False` — ALWAYS check return value.
> - **PAUSE stops monitor only. Listener stays alive.** (Phase 8 invariant — never weaken.)
> - Generation is bumped by `bump_generation()` in `start_session_monitor()` only. Watchdog never touches generation manually.
> - `BEING_CLOSED_TTL_SECS = 180` — cleanup on startup, not on every beat.
> - Watchdog restarts only RUNNING sessions. PAUSED sessions' monitors are intentionally stopped.
> - All timestamps: `datetime.now(timezone.utc).isoformat()` — never naive `utcnow()`.
> - MMM UI and backend MUST remain untouched — ZERO changes to `routes/mmm/` or `components/mmm/`.
> - Isolation: ZERO imports from `routes.mmm.*` in any `mmmx_*.py` file.
>
> ---
>
> ## Test criteria (all must pass in `test_phase9.py`)
>
> **Watchdog:**
> - Kill monitor thread for RUNNING session → `watchdog.tick()` detects dead monitor → calls `start_session_monitor()` → new monitor alive.
> - Kill listener for RUNNING session → watchdog restarts listener.
> - PAUSED session with dead monitor → watchdog does NOT restart (PAUSED is intentional).
> - Watchdog sends Telegram WARN on restart (dedup TTL respected).
>
> **Startup landing:**
> - RUNNING session in DB → `on_startup()` → status=PAUSED, Telegram sent, `_being_closed` expired guards cleared.
> - `_being_closed` entry older than TTL → cleared on startup.
> - `_being_closed` entry within TTL → preserved.
>
> **Naked position escalation:**
> - Naked position present for 31 min → WARNING Telegram sent.
> - Naked position present for 121 min → CRITICAL Telegram sent.
> - Position resolved → no further alerts.
>
> **Reconciliation confirmation:**
> - `apply_recon_confirmation(session, {action: 'accept_db'})` → divergence marked resolved.
> - `apply_recon_confirmation(session, {action: 'accept_exchange'})` → tranche status updated.
> - `apply_recon_confirmation(session, {action: 'manual_close'})` → added to `_naked_positions`.
> - `POST /confirm-reconcile` → 200 on valid, 404 on unknown session.
>
> **All 428 prior tests must still pass.**

### PHASE 9 — Fault Tolerance (Watchdog, Reconciliation, Restart)

**Build:**
- `mmmx_watchdog.py` — supervisor thread polling `_mmmx_monitors` and `_mmmx_listeners`; restart dead threads with `bump_generation`.
- Full `reconcile_with_exchange(session)` flow including the UI Reconcile button.
- Startup landing logic: every session → PAUSED + "Manual reconciliation required" Telegram.
- Crash recovery: expired `_being_closed` guards cleared on restart.
- Naked watchdog escalation path completed (30 min / 2 h) and integrated with Telegram `CRITICAL` escalation.
- Full gap-risk slippage overshoot simulation suite.
- End-to-end integration tests: deploy → shield → hedge → whipsaw → partial hard stop → reconcile → resume.

**Functions:**
- `watchdog.tick()`, `watchdog._restart_monitor(session_id)`, `watchdog._restart_listener(session_id)`
- `reconciler.reconcile_with_exchange(session) → ReconReport`
- `reconciler.apply_recon_confirmation(session, operator_decision)`
- `init_mmmx.on_startup()` — load all sessions from DB, land in PAUSED, set expired guards clear, restore whipsaw state

**Test criteria:**
- Kill monitor thread mid-beat → watchdog restarts with new generation within 1 tick; stale thread self-exits on generation mismatch; no order placed by stale thread.
- Kill listener → watchdog restarts.
- Full process restart: session in DB → start backend → session PAUSED → operator Reconcile (mock mismatch scenarios: (a) DB has pos exchange doesn't, (b) exchange has pos DB doesn't, (c) matches) → operator Resume → monitor runs full beat immediately.
- Naked position survives restart and is re-surfaced to operator.
- Integration test: simulated 48-hour session with moves, shields, hedges, profit booking, whipsaw activation, and a simulated crash; state reconciles cleanly.
- Go-live gate: isolation scan + MMM sealed tests (1312) + all MMMX tests green.

---

## SECTION 5 — HOT RELOAD & UI CONTRACT

### 5.1 Hot-Reloadable Parameters (Allowlist)

Only params in this list are mutable after session start. Everything else requires session stop + recreate.

```
total_budget_lots, tranche_pct, otm_distance_pct,
tranche_deploy_move_pct, tranche_deploy_iv_delta,
hard_stop_multiplier  (min 1.0, max 5.0),
adjustment_interval_hours  (min 0.5, max 24),
delta_drift_threshold, portfolio_delta_threshold, near_itm_delta, emergency_delta,
iv_spike_threshold_pct, iv_catastrophe_pct,  (iv_catastrophe must exceed iv_spike)
atm_protect_threshold  (1–10),
atm_shield_max_shifts  (1–10),
fairness_gate_enabled, fairness_threshold_pct,
max_deployments_per_day,
profit_booking_enabled, profit_booking_targets,
hedging_enabled, hedge_distance_pct  (10–50), hedge_execution_delay_minutes, hedge_capacity_threshold_lots,
close_at_dte  (min 7 HARD-ENFORCED),
profit_target_pct, profit_target_enabled,
whipsaw_window_mins, whipsaw_spot_move_pct,
whipsaw_caution_score, whipsaw_restrict_score, whipsaw_cooldown_score,
whipsaw_cooldown_interval_hours
```

### 5.2 Validation Rules

- Type check against schema (all numeric values have `float` or `int` enforcement).
- Range check against min/max table in `MMMX_COMPLETE` Section 12 "Quick Reference" (recopied into `mmmx_config.py`).
- Cross-field invariants: `iv_catastrophe_pct > iv_spike_threshold_pct`; `emergency_delta > near_itm_delta > delta_drift_threshold`; `close_at_dte >= 7`.
- Reject silently-discarded unknown keys.
- Reject changes to non-allowlisted params with a reason string.

### 5.3 Update Propagation

- Request: `PATCH /api/mmmx/session/<id>/params` with JSON diff.
- Server:
  1. Validate → on failure, 400 + reason. Write rejection to `mmmx_param_audit`.
  2. On success, atomically merge into `session['params']` under the session's storage lock.
  3. Call `engine.recalc_hard_stop(session)` if `hard_stop_multiplier` changed.
  4. Emit `mmmx_params_updated` WebSocket event with old/new diff.
  5. Telegram: `"Params updated: hard_stop_multiplier 2.0 → 3.0 (operator)"`.
- Monitor reads params from session on every beat — no restart needed.
- Special cases:
  - `adjustment_interval_hours` changes apply from the next scheduled beat.
  - `hedge_distance_pct` applies only to hedges not yet bought.
  - `profit_booking_targets` list changes update the UI dropdown immediately.

### 5.4 Audit Log Format (`mmmx_param_audit.jsonl`)

```json
{"ts":"2026-04-05T10:15:12+00:00","session_id":"...","operator":"webui","action":"update","diff":{"hard_stop_multiplier":{"old":2.0,"new":3.0}},"accepted":true,"reason":null}
{"ts":"...","session_id":"...","operator":"webui","action":"update","diff":{"close_at_dte":{"old":7,"new":6}},"accepted":false,"reason":"close_at_dte must be >= 7 (gamma risk)"}
```

### 5.5 UI ↔ Backend Interaction Contract

| UI action | Endpoint | Server handler | UI feedback |
|---|---|---|---|
| Create session | `POST /api/mmmx/session` | `initializer.create_session` | DRAFT row added |
| Scan strikes | `POST /api/mmmx/session/<id>/scan_strikes` | `initializer.scan_strikes` | strike candidates table |
| Deploy Tr1 | `POST /api/mmmx/session/<id>/deploy_tranche1` | `initializer.deploy_manual_tranche1` | status RUNNING; Tr1 row |
| Stop session | `POST /api/mmmx/session/<id>/stop` | `monitor.stop_session_monitor` + close_all | status COMPLETE |
| Pause / Resume | `POST /api/mmmx/session/<id>/pause | resume` | status transitions | orders paused/resumed |
| Profit book | `POST /api/mmmx/session/<id>/profit_book` `{tranche_id, target}` | `profit_booking.queue_close` | pending row appears |
| Hot reload param | `PATCH /api/mmmx/session/<id>/params` | validate + merge | params updated event |
| Reconcile | `POST /api/mmmx/session/<id>/reconcile` | `reconciler.reconcile_with_exchange` | diff table shown |
| Confirm reconcile | `POST /api/mmmx/session/<id>/reconcile/confirm` | `reconciler.apply_recon_confirmation` | status PAUSED→RUNNING |

All responses include the updated session snapshot or a typed error `{error, code, message}`. All mutations emit `mmmx_*` WebSocket events.

---

## SECTION 6 — DATA FLOW & STATE MUTATION RULES

### 6.1 Who May Mutate Session State

Only four contexts may mutate `session`:

1. **Monitor thread inside `_heartbeat`** — via the beat orchestration call graph. Mutations are buffered in a local dict and flushed via `_save_session` at the end of the beat.
2. **API handlers (main thread)** — for param updates, profit-booking queue additions, manual deploys. Handlers acquire the per-session storage lock before mutating and always write immediately.
3. **Reconciler** — only during explicit operator-confirmed reconcile flow.
4. **Watchdog** — only to increment generation and clear dead-thread references. Never touches tranches/hedges.

Modules that run inside the beat (`atm_shield`, `hedger`, `trigger`, `initializer.execute_tranche_deploy`, `profit_booking`) are **stateless w.r.t. storage**: they receive `session` by reference, mutate the in-memory dict, and return control to the monitor which persists once via `_save_session`.

### 6.2 When State Is Saved

- Beat end (always, exactly once).
- Immediately after `close_all` and before status → COMPLETE.
- Immediately on param hot-reload.
- Immediately on profit-booking queue insert.
- Immediately after shield recovery tranche creation (intra-beat; this is an exception to "once per beat" because the shield may fire before deployment and we need the state durable in case of crash between steps).
- Immediately after hedge buy success.
- Immediately on manual pause/resume/stop.

Every save goes through `_save_session(session, expected_generation)`. If the stored generation no longer matches → save is rejected → caller handles as stale.

### 6.3 Race Condition Prevention

- **Per-session lock** (`threading.RLock`) held by the monitor for the duration of the beat. API handlers take the same lock with a 5 s timeout; on timeout, handler returns 409.
- **Generation guard (3 layers)** — verbatim from repo CLAUDE.md §4, adapted:
  1. `start_session_monitor()` joins old thread with 15 s timeout before starting new one.
  2. `_run_loop` top: load fresh session, verify `stored_gen > self._my_generation` → stale → stop, Telegram, break.
  3. G5 inside `_heartbeat` after the first pre-snapshot: re-verify generation; if stale, STOP (not pause), return.
- `_save_session` returns `True`/`False`; callers check and set `_stale_abort_gen` on False.
- Pre-exchange-order check: re-verify generation immediately before any order call (executor step 6).
- `emit_safety` is a regular `def`, never wrapped in `run_until_complete`.
- `handle_stale_monitor` uses STOP, not PAUSE.

### 6.4 Consistency Guarantees

- All writes to `tranches`, `hedges`, `reserve_remaining`, `total_premium_collected`, `hard_stop_usd` are grouped in a single transaction-like mutation (within one beat or one handler).
- After every mutation, invariants are checked (Section 8.4). Any violation raises and pushes the session to ERROR state with a full dump.
- Audit log is append-only; every exchange order is journaled before the call and updated with the fill result after.
- Hedges and tranches are persisted together — an orphan hedge or orphan tranche is treated as a reconcile mismatch on restart.

---

## SECTION 7 — FAILURE & EDGE CASE STRATEGY

| Failure / edge | Response | Recovery |
|---|---|---|
| **API unavailable (circuit breaker OPEN)** | Monitor → PAUSED, listener keeps running, Telegram warning. All new orders blocked. | Retry API each beat; first success runs full beat immediately (Q22). |
| **Partial fill** | Reconciler records residual; beat end persists it. | Next beat retries residual with `smart_execute`; delta gate re-evaluates remaining size. |
| **System restart / power loss** | Startup loads all sessions into PAUSED; clears expired `_being_closed` guards; never auto-resume. | Operator runs Reconcile → confirms → Resume; monitor starts with new generation and runs full beat. |
| **Duplicate orders** | Deterministic `client_order_id` + `_being_closed` guard (180 s TTL). | Exchange dedup; reconcile on restart. |
| **Missing data (P&L incomplete)** | `_pnl_calculation_incomplete = True`; triggers skipped; beat logs and continues. | Next beat retries; watchdog escalates if flag stuck > 3 beats. |
| **Liquidity failure (spread too wide / depth too shallow)** | Fairness gate blocks deployment; Telegram; retry each beat. | Operator may hot-reload to disable fairness gate for high-liquidity regimes. |
| **Shield buyback unrecoverable** | Abort shield (no naked); Telegram CRITICAL; next beat re-tries. | Delta gate picks up if situation worsens. |
| **Shield new-sell unrecoverable** | Session PAUSED, naked position logged, Telegram CRITICAL. | Naked watchdog (30 min / 2 h escalation). |
| **Reserve exhausted mid-cascade** | Partial recovery for first shields, reposition-only for subsequent. | Telegram alerts; operator may increase reserve via restart. |
| **Margin 85–95% during execution** | Switch from limit to market; if 95%+, abort execution and return MARGIN_CRITICAL. | Caller decides (usually: reduce position next beat). |
| **Hedge would breach margin** | Skip this hedge; Telegram; retry next beat. | Operator may lower `hedge_distance_pct` to reduce cost. |
| **WS stale > 5 min** | Force heartbeat; if both WS and heartbeat stale, operator critical alert. | Watchdog restarts listener. |
| **Stale monitor instance** | 3-layer guard STOPS it (not pause). | Watchdog spawns fresh monitor with new generation. |
| **Gap risk slippage** | Accepted (5–15% overshoot). System guarantees close_all fires, not fill price. | Documented in Telegram on hard-stop events. |
| **Queue retracement** | Clear `deployment_eligible_tranches` only when **directional retrace** against queue direction (`UP`/`DOWN`) exceeds 0.5%. | Next real move starts new queue. |
| **Whipsaw COOLDOWN** | Block deployments for 1 hour; shield and hard stop still fire. | Auto-decay by 2 on expiry. |
| **CE/PE imbalance** | Telegram warning > 40%; critical > 60%; no automatic action unless operator acts. | Visible in dashboard. |
| **Hedger displacement** | Log, mark hedge `DISPLACED`, keep alive. | Hedge expires with parent tranche. |

---

## SECTION 8 — TESTING STRATEGY

### 8.1 Unit Tests (per module, sync where possible)

- **`mmmx_constants`** — constants exist, not mutated.
- **`mmmx_state`** — `create_session` returns schema v1, all fields present, validators pass.
- **`mmmx_config`** — full table of allowlist accept/reject tests; cross-field invariants.
- **`mmmx_storage`** — CRUD round-trip; generation counter monotonicity; concurrent save detects mismatch.
- **`mmmx_engine`** — golden fixtures for P&L, portfolio delta, BS fair value, fee calcs, DTE, lot imbalance, hard stop recalc.
- **`mmmx_trigger`** — 10+ cases covering priority table; first-match wins; no trigger vs None.
- **`mmmx_safety`** — stale gen, P&L incomplete, DTE sanity.
- **`mmmx_executor`** — mock exchange client; reprice loop, margin recheck, dedup, partial fills, circuit breaker states.
- **`mmmx_atm_shield`** — loss calc, buyback path, retry sequence (10+1), reserve allocation (full/partial/zero), multi-shield sort + margin cascade, recovery tranche factory.
- **`mmmx_hedger`** — 50% capacity gate, 15-min scheduler, displacement detection, hedge P&L.
- **`mmmx_whipsaw`** — score increment/decay, CAUTION/RESTRICT/COOLDOWN thresholds, cooldown expiry -2 reward.
- **`mmmx_profit_booking`** — per-tranche target evaluation, independent tranche evaluation, recovery tranche close, hard stop recalc.
- **`mmmx_premium_listener`** — each Tier-0 CB individually; stale WS watchdog; force-check flag.
- **`mmmx_reconciler`** — partial fill tracking; 3 reconcile mismatch types; residual retry logic.
- **`mmmx_initializer`** — entry gates, strike scanning with irregular ladders, fairness gate, frequency gate, queue populate/retrace/clear, all-or-nothing deploy rollback.

### 8.2 Integration Tests (per phase)

- **Phase 1**: create → validate → persist → monitor empty beat → stop; two concurrent sessions.
- **Phase 2**: order lifecycle end-to-end with mock exchange including crashes mid-reprice.
- **Phase 3**: synthetic beat with triggers 1–10, verifying exactly one dispatches per beat.
- **Phase 4**: hard stop end-to-end, market shorts + limit longs, recovery tranches included, hedges preserved.
- **Phase 5**: shield scenarios — single, multi (3), reserve depleted mid-cascade, naked escalation.
- **Phase 6**: 48-hour simulated session covering deploy Tr1 manual, queued 6.4% move, retrace clearing queue, frequency gate block, profit booking closing Tr3, whipsaw CAUTION→COOLDOWN→decay.
- **Phase 7**: WS feed simulator driving each Tier-0 CB; hedge full cycle for Tr5–Tr10 with displacement.
- **Phase 8**: UI-driven end-to-end via test client: create → scan → deploy → hot-reload → profit-book.
- **Phase 9**: kill monitor; kill listener; full process restart; reconcile-then-resume; naked on restart.

### 8.3 Simulation Hooks

- **`MockExchangeClient`** — deterministic sequences of fills, rejects, timeouts; programmable latency and partial fills.
- **`MockChainService`** — programmable strike ladder with irregular steps.
- **`MockPatienceIV`** — scriptable IV rank and DVOL time series.
- **`MockPremiumFeed`** — ordered list of ticks replayed into listener; supports fault injection (stale, flicker, gap).
- **`FakeClock`** — advances `datetime.now(timezone.utc)` to script aging windows (24 h frequency, 30-min whipsaw, 15-min hedge, 180-s guard TTL, 5-min WS watchdog, 30-min / 2-h naked timers).
- **`MarketSimulator`** — orchestrates price series (ramps, gaps, oscillations) feeding chain + listener + patience_iv simultaneously.

### 8.4 Invariants (must always hold)

1. `sum(tranche.ce.lots) + sum(recovery.ce.lots)` is reflected in `ce_lot_balance.total_ce_lots` (same for PE).
2. `total_premium_collected` equals sum of (`tranche.premium_collected`) across all tranches (deployment + recovery). Hedge cost NOT included.
3. `hard_stop_usd == hard_stop_multiplier * total_premium_collected` at all times after any mutation.
4. `ce_reserve_remaining == ce_reserve_total_lots - Σ CE recovery lots allocated`; same invariant holds for `pe_reserve_remaining` independently.
5. `tranches_deployed == count(t for t in tranches if t.type == 'deployment')`.
6. `tranches_remaining == max(0, 10 - tranches_deployed)`.
7. For every hedge in `session['hedges']`: `parent_tranche_id` exists in tranches OR the tranche is CLOSED (displaced/orphaned).
8. `close_at_dte >= 7` always.
9. `_my_generation` only ever increases; writes with stale gen are rejected.
10. `status` transitions follow the legal state machine (1.2); any illegal transition raises.
11. Every order in the audit log has a matching `client_order_id` and a final state (`FILLED`, `PARTIAL+RESIDUAL`, `CANCELLED`, or `REJECTED`).
12. If `_naked_positions` is non-empty, `status` must be PAUSED or ERROR.
13. `deployment_eligible_tranches` never exceeds `tranches_remaining`.
14. `portfolio_pnl` equals `engine.compute_portfolio_pnl(session, quotes)` at the time of the last beat (within a tolerance of 1e-6).
15. A recovery tranche's `shift_count` is independent of its parent's.
16. Hedges never close automatically unless ALL shorts are CLOSED.

All invariants are asserted at the end of every beat in a `debug_validate(session)` helper. A violation transitions the session to ERROR with a full snapshot dumped.

---

## SECTION 9 — AMBIGUITIES THAT BLOCK IMPLEMENTATION

These items are present in `MMMX_COMPLETE.md` but are NOT fully pinned down for a coder. Each must be resolved with the operator BEFORE the listed phase starts — do not assume defaults.

All ambiguities below are **RESOLVED** as of 2026-04-06. Implementation may proceed.

| # | Question | Blocks phase | Resolution |
|---|---|---|---|
| A1 | CE and PE reserves — separate 30-lot pool each (60 total) or shared 30-lot pool? | 5 | ✅ **30 per side = 60 total**. Money model explicitly states "Per side (CE or PE): ATM SHIELD RESERVE: 30 lots". Session schema uses `ce_reserve_remaining` and `pe_reserve_remaining` (30 each). Depletion tracked independently. |
| A2 | ~~SIDE_LOSS trigger threshold~~ | 6 | ✅ **TRIGGER REMOVED**. `SIDE_LOSS` trigger eliminated entirely. Hard stop (portfolio-level `total_pnl <= -hard_stop_usd`) is the sole protection against position losses — when it fires, `close_all` closes all SHORT legs; hedge LONGs survive. No per-tranche loss trigger is needed or wanted. Trigger table renumbered to 9 entries. |
| A3 | `DELTA_DRIFT` trigger (#9) — formula for "drifted from 20Δ target" | 6 | ✅ `|current_delta - entry_delta| > delta_drift_threshold` where entry_delta ≈ 0.20 and `delta_drift_threshold = 0.35`. Catch-all for profitable-side drift; does not duplicate REPOSITION (which checks the threatened side's absolute delta). |
| A4 | Multi-shield margin pre-check: "10% buffer" vs "90% ceiling" | 5 | ✅ Both are mathematically identical. Use `required <= total_margin × 0.90` in code. |
| A5 | `max_deployments_per_day` — rolling 24h or calendar UTC day? | 6 | ✅ Rolling 24h window via `deployments_last_24h` list of ISO timestamps. Filter: `count(t for t in deployments_last_24h if t > now - timedelta(hours=24))`. |
| A6 | Profit booking: per-request UI choice or global mode? | 6 | ✅ Per-request. For each tranche, operator picks: (a) "Queue: close when P&L hits target" OR (b) "Close now (override)". Two options presented per tranche submission. |
| A7 | Hedge close at DTE expiry — operator-manual or monitor-auto? | 7 | ✅ Monitor auto-closes hedges in the same beat `DTE_CLOSE` fires, **after** all shorts confirmed CLOSED. Condition: `all(t.status == 'CLOSED' for t in tranches)` → close hedges. Hard stop exception: hedges survive hard stop (orphaned, not closed). |
| A8 | `patience_iv.py` cross-module import — acceptable under isolation rules? | 6 | ✅ Acceptable as read-only adapter. Wrap in `mmmx_iv_adapter.py` exposing only `get_iv_rank()`. No writes to MMM state. Same pattern as `mmmx_margin_guardian.py`. |
| A9 | 2h naked escalation channel — which provider? | 5/9 | ✅ No secondary gateway is configured in-repo. Use Telegram `CRITICAL` severity at both the 30-min and 2h escalation points. Operator must configure device for high-priority Telegram alerts. |
| A10 | Fee accounting — self-calculated or pulled from exchange? | 2 | ✅ **Fees pulled directly from exchange fill response**, same method as MMM algo. Do NOT calculate independently. Every Delta Exchange fill response includes the actual fee charged; record that value directly into `fees_tracking`. Copy the fee-recording method from MMM's executor/fill_processing — do not reimplement. |
| A11 | Strike cache — refresh every beat even if no deployment? | 6 | ✅ Yes, refresh every beat unconditionally. ATM Shield can fire on any beat; stale cache gives wrong strikes. Cost: ~24 API calls/day — negligible. |
| A12 | `deployments_last_24h` addition to immutable schema? | 1 | ✅ Confirmed. Field is already present in Section 1.3 locked schema. Part of schema v1. |
| A13 | Mid-beat persist after shield recovery tranche creation — acceptable? | 5 | ✅ Required for crash safety. A crash between shield buyback (Step 2) and reserve decrement (Step 6) without mid-beat persist produces an undetectable reconciliation mismatch. Mid-beat persist after `create_recovery_tranche` is mandatory. |

---

## APPENDIX — Cross-Phase Invariants & Isolation Checklist

Before merging any phase PR:

1. ✅ No `from routes.mmm` imports in any `routes/mmmx/*.py`.
2. ✅ No writes to `mmm_sessions.db`.
3. ✅ No `mmm_*` WebSocket events emitted.
4. ✅ No mutations to MMM-owned global state or registries.
5. ✅ All MMMX WebSocket events prefixed `mmmx_`.
6. ✅ MMM sealed-test baseline unchanged.
7. ✅ MMMX unit + integration tests green for this phase and all prior phases.
8. ✅ `debug_validate(session)` invariants pass on fixtures exercised by this phase.
9. ✅ Isolation scan script run in CI.
10. ✅ CLAUDE.md rule check: branch is `SSR`, target `BTEH`, no unauthorized restarts, real-money rules observed.

---

**End of implementation plan.** This document is ready for phase-by-phase execution. Any deviation from this plan during coding must be reflected back here in a follow-up commit before the affected phase is marked complete.

---

## POST-PHASE-9 — App Wiring ✅ COMPLETE (2026-04-06)

**Done:** Registered `mmmx_bp`, `init_mmmx_websocket(socketio)`, and `init_mmmx()` in `webui/backend/app.py` immediately after the MMM registration block (~line 580). Follows the same pattern as MMM and IC blueprints.

All 463 MMMX tests pass. MMM isolation scan clean.
