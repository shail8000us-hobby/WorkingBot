# MMM Master Context
### Complete System Reference for Debugging & Development
**Last updated:** 2026-04-26 (post full institutional audit, Phases 1–12)
**Confidence Score:** 69/100 — improvement plan in `MMM_SCORE_IMPROVEMENT_PLAN.md`

> **How to use this file:** Read this before touching ANY MMM file. It is the single place that answers "what does this field mean", "which module owns this", "why does this exist", and "what will break if I change this".

---

## 1. System Overview

MMM is a live BTC options market-maker on **Delta Exchange**. It shorts straddles/strangles, collects theta, and adjusts positions to stay delta-neutral. Multiple strategies share a common heartbeat loop.

**Exchange:** Delta Exchange India
**Instrument:** BTC options, USDT-settled
**LOT_SIZE_BTC:** `0.001` BTC per lot (1 lot = 0.001 BTC notional)
**Typical session:** 10 initial lots per side, max 100 lots per side
**Heartbeat:** Every `adjustment_interval` seconds (default 300s; adaptive near expiry)

---

## 2. File Map — The 57 Modules

### Core Orchestration
| File | Role | Lines | Notes |
|---|---|---|---|
| `mmm_monitor.py` | **God Module** — heartbeat loop, trigger eval, adjustment dispatch, all strategy coordination | ~12,000 | One God Module; do not add to it |
| `mmm_watchdog.py` | Supervisor thread — restarts dead/stuck monitors | ~550 | MAX_RESTARTS=10, 30s deferred restart |
| `mmm_heartbeat_health.py` | Monotonic beat-timer used by watchdog | ~150 | Better than ISO timestamp fallback |

### Math & Strategy Core
| File | Role | Key Functions |
|---|---|---|
| `mmm_engine.py` | Lot sizing (7-multiplier chain), loss-to-cover formula | `calculate_lots_to_sell()` @sealed → `(lots, msg, is_position_cap_hit)` |
| `mmm_pnl_core.py` | Canonical P&L formula | `compute_current_total_pnl()` @sealed |
| `mmm_constants.py` | `LOT_SIZE_BTC=0.001`, `_D(x)` helper, `strike_key()` | — |
| `mmm_trigger.py` | Trigger evaluation, adaptive interval | `evaluate_triggers()`, `OUTCOME_NONE/CE/PE/BOTH` |
| `mmm_breakeven_engine.py` | Portfolio breakeven distance | `compute_breakeven()` — intrinsic-only, 80-pt scan + binary search |
| `mmm_gamma.py` | Dollar gamma, regime classification | `compute_gamma_data()` — `$Γ = \|Γ\| × S² × 0.01` |

### State & Storage
| File | Role | Key Functions |
|---|---|---|
| `mmm_state.py` | Session creation, position ledger, DEFAULT_PARAMS | `create_session()`, `recompute_side_lots()` @sealed, `HOT_RELOAD_PARAMS` |
| `mmm_storage.py` | SQLite singleton, WAL mode, checksum v2 | `MMMStorage`, `save_session()`, `get_session()` |
| `mmm_initializer.py` | Strike initialization, expiry normalization | `get_initializer()`, `normalize_expiry()` |

### Execution
| File | Role | Key Functions |
|---|---|---|
| `mmm_executor.py` | Smart limit orders, reprice loop, partial fill | `smart_execute()` — 60s fill_timeout, 4 reprice attempts |
| `mmm_fill_sync.py` | REST fill reconciliation (ground truth) | `FillSyncer.sync()` — cursor-based, 3-page pagination |
| `mmm_ledger.py` | Persistent per-fill sub-ledger | `record_fill()` idempotent, `get_session_net_lots()` |
| `mmm_ws_executions.py` | Real-time WS fill routing | `MMMExecutionsWS`, subprocess pattern, coid registry |
| `mmm_pending_orders.py` | Open-order tracking | — |

### Risk Controls
| File | Role | Key Concepts |
|---|---|---|
| `mmm_safety.py` | Max loss, kill switch, hard stop | `check_max_loss()`, `handle_kill_switch()` |
| `mmm_guardian.py` | G5 generation-integrity check inside heartbeat | `check_generation_integrity()` — innermost stale-monitor fallback |
| `mmm_god_layer.py` | Strategic integrity monitor (off by default) | Periodic P&L health check; `god_enabled=False` default |
| `mmm_circuit_breaker.py` | API error classification + backoff | Handles 429, timeout, connection errors |
| `mmm_margin_guardian.py` | Margin utilization tiers (off by default) | `margin_monitor_enabled=False`; 5 tiers: green→critical |
| `mmm_exit_all.py` | Ordered close-all sequence | reverse→perp→core order; `_exit_all_partial` flag on stuck |

### Strategy Routing
| File | Role | Key Concepts |
|---|---|---|
| `mmm_strategy_dispatch.py` | `STRATEGY_DISPATCH` frozen dataclass dict | Maps strategy_type → handler + flags |
| `mmm_config.py` | `PARAM_RULES`, validation, strategy namespaces | 360 params; `hot=True` = editable while running |
| `mmm_dte_presets.py` | DTE preset profiles | `STRADDLE_WITH_ADJUSTMENT_CATEGORY`, `STRADDLE_ROLL_CATEGORY` |

### Strategies
| File | Role |
|---|---|
| `mmm_straddle_adjustment.py` | STRADDLE_WITH_ADJUSTMENT roll gates (12 gates, @sealed `check_straddle_roll_gates()`) |
| `mmm_straddle_roll_pure.py` | STRADDLE_ROLL pure roll, dynamic trigger, hard stop |
| `mmm_reverse.py` | Controlled Reverse Mode overlay |
| `mmm_reversal.py` | Reversal detection, cooldown |

### Adjustments
| File | Role |
|---|---|
| `mmm_close_at_5.py` | Close positions below `close_at_threshold` % |
| `mmm_strike_shift.py` | Strike shift when position goes too far OTM/ITM |
| `mmm_replenish.py` | Re-enter empty side after full close |
| `mmm_wind_down.py` | Reduce positions near expiry |
| `mmm_harvester.py` | M1 profit harvesting |
| `mmm_recycler.py` | M2 lot recycling |
| `mmm_scaler.py` | FSU favorable scale-up |
| `mmm_perp_hedge.py` | Perpetual futures delta hedge |
| `mmm_atm_shield.py` | ATM proximity close-and-retreat |

---

## 3. Critical Session State Fields

### Top-Level Identity
```python
session['session_id']           # UUID, e.g. "mmm-20260426-abc123"
session['strategy_type']        # '0DTE' | '5DTE' | 'SHORT_WINDOW' | 'STRADDLE_WITH_ADJUSTMENT' | 'STRADDLE_ROLL'
session['strategy_status']      # 'RUNNING' | 'PAUSED' | 'STOPPED' | 'EXITING'
session['params']               # All operator params (merged with DEFAULT_PARAMS)
session['_monitor_generation']  # H-4 stale-monitor guard — increment on every start
```

### Position State (per side: 'ce' and 'pe')
```python
session['ce']['positions']      # CANONICAL list of position dicts — source of truth for lots
session['ce']['total_lots']     # sum of positions[].lots — DERIVED, recomputed by recompute_side_lots()
session['ce']['active_lots']    # total_lots - frozen_total_lots
session['ce']['frozen_total_lots']  # lots at non-active strike (shifted away)
session['ce']['original_lots']  # lots at entry (never changes after entry)
session['ce']['active_strike']  # current live strike price
```

#### Position Dict (one entry in positions[])
```python
{
    'id': str,               # UUID
    'strike': float,
    'type': 'original' | 'adjustment',
    'lots': int,             # current lot count (decremented by partial sub-fills)
    'entry_premium': float,  # USD per lot — set at sell time
    'status': 'open' | 'closed',
    'close_order_id': str,   # set when close order placed; FillSync matches on this
    '_fill_confirmed': bool, # True after FillSync confirms final fill
    '_cumulative_lots_filled': float,  # tracks partial sub-fill accumulation
    '_estimated_pnl_booked': float,    # estimate at order placement
    '_actual_pnl_booked': float,       # actual after FillSync confirmation
}
```

### P&L Fields (cached — updated each heartbeat)
```python
session['realized_pnl']         # from ledger sum via _sync_session_fields()
session['unrealized_pnl']       # from live premiums — cache, stale if fetch fails
session['total_fees']           # from ledger sum
session['total_premium_collected']   # gross (only increments on sells)
session['_net_premium_collected']    # net = gross - buyback costs (heartbeat cache)
session['_fill_ledger']         # list of ledger entries (internal, not persisted separately)
```

### Reverse Mode
```python
session['_reverse']['active']     # bool — reverse mode currently trading
session['_reverse']['net_pnl']    # included in compute_current_total_pnl()
session['_reverse']['positions']  # ISOLATED from session['ce']['positions']
session['_reverse']['total_lots'] # NEVER in active_lots or adjustment_count
```

### Watchdog / Recovery Fields
```python
session['_monitor_generation']    # H-4 guard — incremented on each start
session['_watchdog_restarts']     # counter; reset to 0 on PAUSED→RESUME
session['_watchdog_history']      # list of restart events
session['_fill_sync_cursor_us']   # microsecond timestamp; fill_sync advances after each sync
session['_fillsync_double_booking_corrected']  # startup fix flag
session['_exit_all_partial']      # True if exit_all was stuck and incomplete
session['_stale_abort_gen']       # set when save rejected by generation guard
```

### Straddle Roll
```python
session['_straddle_initial_credit']   # total credit at entry (BTC-adjusted); Gate 10 baseline
session['_straddle_credit_v2']        # True = computed with correct per-position lots
session['_straddle_roll_count']       # rolls executed so far
session['_straddle_last_roll_at']     # ISO timestamp
```

---

## 4. Canonical P&L Formula

```python
# mmm_pnl_core.py — @sealed
def compute_current_total_pnl(session: Dict) -> float:
    realized   = session.get('realized_pnl', 0.0)      # ledger cache
    unrealized = session.get('unrealized_pnl', 0.0)     # live premium cache ⚠️ can be stale
    fees       = session.get('total_fees', 0.0)         # ledger cache
    perp_pnl   = perp.realized + perp.unrealized        # from perp_hedge dict
    reverse_pnl = session['_reverse']['net_pnl']        # MUST stay in formula (CLAUDE.md)
    return realized + unrealized - fees + perp_pnl + reverse_pnl
```

**Signs:** `+realized` (profit from closes) | `+unrealized` (decay profit) | `-fees` | `+perp` | `+reverse`

**Per-close P&L:** `(entry_premium - close_premium) × lots × LOT_SIZE_BTC`

**Dollar Gamma:** `|Γ_portfolio| × S² × 0.01` where S = BTC spot

---

## 5. Strategy Dispatch

```python
# mmm_strategy_dispatch.py — FROZEN DATACLASS DICT
STRATEGY_DISPATCH = {
    '0DTE':                       StrategyConfig(should_run_adjustment=True,  run_step_5_4=None,              ...),
    '5DTE':                       StrategyConfig(should_run_adjustment=True,  run_step_5_4=None,              ...),
    'SHORT_WINDOW':               StrategyConfig(should_run_adjustment=True,  run_step_5_4=None,              ...),
    'STRADDLE_WITH_ADJUSTMENT':   StrategyConfig(should_run_adjustment=True,  run_step_5_4=step_5_4_straddle, ...),
    'STRADDLE_ROLL':              StrategyConfig(should_run_adjustment=False, run_step_5_4=step_5_4_pure_roll, ...),
    # STRADDLE_ROLL step_5_4 handler always returns True → _skip_to_pnl=True → _process_adjustment() UNREACHABLE
}
```

**Strategy isolation rule:** NEVER add inline `if strategy_type == X` in `mmm_monitor.py`. Use STRATEGY_DISPATCH flags.

---

## 6. Three-Layer Stale Monitor Guard (CLAUDE.md Invariant — DO NOT REMOVE)

```
Layer 1: start_session_monitor() → old.stop() → old_thread.join(15s)
Layer 2: _run_loop primary guard — checks stored_gen > _my_generation → _running=False → stop
Layer 3: G5 guardian inside _heartbeat() → check_generation_integrity() → handle_stale_monitor(STOP)
```
- `emit_safety()` is a regular `def` — call directly, NEVER in `run_until_complete()`
- `handle_stale_monitor()` must use STOP (`_running = False`) not pause

---

## 7. Reverse Mode Isolation (CLAUDE.md Invariant — DO NOT BREAK)

```python
# mmm_monitor.py ~line 3697 — HARD if/else, NEVER make fallthrough
if session.get('params', {}).get('reverse_enabled') and session.get('_reverse', {}).get('active'):
    await process_reverse_entry(...)      # Reverse path
else:
    # Normal MMM — NEVER modify this else for reverse purposes
    await _process_adjustment(...)        # Adjustment path
```

**Invariants:**
- `session['_reverse']['positions']` NEVER go into `session['ce']['positions']`
- `session['_reverse']['total_lots']` NEVER counted in `active_lots` or `adjustment_count`
- `session['_reverse']['net_pnl']` MUST stay in `compute_current_total_pnl()`
- `initialize_reverse_state(session)` called if `'_reverse' not in session` (restore compat)

---

## 8. Key Constants & Defaults

```python
LOT_SIZE_BTC = 0.001          # mmm_constants.py — NEVER change
FILL_TIMEOUT = 60             # mmm_executor.py — seconds before reprice
MAX_REPRICE_ATTEMPTS = 4      # mmm_executor.py — total reprice cycles
WATCHDOG_POLL_INTERVAL = 15   # mmm_watchdog.py — seconds between sweeps
MAX_RESTARTS_PER_SESSION = 10 # mmm_watchdog.py
BEAT_TIMEOUT_MULTIPLIER = 3   # mmm_watchdog.py — beats missed before restart
_FIRST_SYNC_LOOKBACK_SEC = 3600  # mmm_fill_sync.py — on first sync, look back 1 hour

# DEFAULT_PARAMS key values (mmm_state.py)
initial_lots: 10
max_lots_per_side: 100
max_total_exposure: 200
adjustment_interval: 300      # seconds
gamma_soft_limit: 2500.0      # ⚠️ calibrated for ~100 lots only
gamma_hard_limit: 5000.0      # ⚠️ fires at ~267 total lots (3× scale)
lot_velocity_limit: 30        # ⚠️ incompatible with initial_lots > 30
lot_velocity_window_mins: 30
```

---

## 9. Execution Flow — One Heartbeat

```
_heartbeat()
  1. pre_beat_snapshot() — load fresh session from DB
  2. G5 guardian check_generation_integrity() — abort if stale
  3. recompute_side_lots(ce), recompute_side_lots(pe)
  4. FillSyncer.sync() — reconcile fills from exchange
  5. fetch premiums (L1 orderbook)
  6. compute_unrealized_pnl() — updates session['unrealized_pnl']
  7. compute_current_total_pnl() — max loss check HERE
  8. close_at_threshold watcher check
  9. evaluate_triggers() → OUTCOME
  10. if OUTCOME != NONE:
      → STRATEGY_DISPATCH.run_step_5_4() (STRADDLE strategies)
      → OR _process_adjustment() (0DTE/5DTE/SHORT_WINDOW)
  11. M1 harvester, M2 recycler, M3 rebalancer
  12. save session to DB
```

**Beat phases with timing risk:**
- Step 6 (`fetch premiums`) → if this fails, unrealized_pnl cache is STALE → A3-01 bug
- Step 7 (`max loss check`) uses stale unrealized if step 6 failed

---

## 10. Fill Lifecycle

```
SELL order placed
  → smart_execute() writes ORDER_INTENT to audit log
  → position added to session[side]['positions'] with status='open'
  → record_fee() for sell-side commission
  → FillSyncer on next heartbeat confirms via /v2/fills
      → matches by close_order_id (for BUY/close fills)
  → _pnl_confirm() corrects estimated P&L to actual
  → position.status = 'closed', _fill_confirmed = True
  → recompute_side_lots() updates scalar counts
  → record_fill() in mmm_position_ledger.db (idempotent by fill_id)
```

**External closes (manual, expiry):** Not matched by FillSync (no close_order_id). Position stays `status=open` until manual cleanup. **Known gap (A8-02).**

---

## 11. Watchdog Restart Flow

```
Beat timeout OR thread dead detected
  → 30s settlement wait (non-blocking, _pending_restart_at dict)
  → old_monitor.stop() → join(15s)
  → load fresh_session from DB
  → increment _monitor_generation (H-4 guard)
  → RECONCILIATION: compare total_lots vs ledger DB
      → patches total_lots/active_lots from DB
      → ⚠️ does NOT rebuild positions[] — reverted by next recompute_side_lots() (A7-01 bug)
  → start_session_monitor(sid, fresh_session, context='monitor_restore')
  → re-register with watchdog
```

---

## 12. PARAM_RULES vs HOT_RELOAD_PARAMS

| Source | File | Used For |
|---|---|---|
| `PARAM_RULES` | `mmm_config.py` | API validation + hot-reload enforcement (the enforcing path) |
| `HOT_RELOAD_PARAMS` | `mmm_state.py` | Conceptual reference; not the enforcing path |

**Risk:** New param in `HOT_RELOAD_PARAMS` but missing from `PARAM_RULES` → silently not editable via API while running.
**Fix:** Always add to BOTH when creating a new param. The `F01-P1-009` comment block in `mmm_config.py:328` shows the pattern.

**Strategy namespace enforcement** (`mmm_config.py:STRATEGY_PARAM_NAMESPACES`):
- `STRADDLE_ROLL` forbids: ~50 adjustment-engine params (trigger, shift, whipsaw, harvest, M1/M2/M3...)
- `0DTE/5DTE/SHORT_WINDOW` forbid: all straddle-roll control surface params
- `STRADDLE_WITH_ADJUSTMENT` forbids: pure-roll-only params only

---

## 13. Known Bugs / Audit Findings

### P1 — Must Fix Before Capital Scaling

| ID | Description | File(s) | Gap |
|---|---|---|---|
| **A3-01** | Stale `unrealized_pnl` under premium fetch failure → max loss may not fire | `mmm_pnl_core.py`, `mmm_monitor.py` | Default to 0 on N consecutive failures |
| **A3-08** | Safety formula (cache) vs display formula (ledger) diverge mid-heartbeat | `mmm_pnl_core.py`, `mmm_monitor.py`, `mmm_api.py` | Document delta bound |
| **A6-11/A11-01** | `gamma_hard_limit=5000` is fixed-dollar, fires at ~267 total lots (3× scale) | `mmm_constants.py`, `mmm_state.py`, `mmm_gamma.py` | Make lot-proportional |
| **A7-01** | Watchdog reconciliation patches scalars but NOT `positions[]`; reverted by `recompute_side_lots()` | `mmm_watchdog.py`, `mmm_state.py` | Rebuild `positions[]` from ledger |
| **A5-07** | 15+ inline `strategy_type == STRADDLE_WITH_ADJUSTMENT_CATEGORY` checks in `mmm_monitor.py` | `mmm_monitor.py` | Consolidate to STRATEGY_DISPATCH flags |
| **A5-05** | `execute_pure_straddle_roll()` NOT @sealed | `mmm_straddle_roll_pure.py` | Add sealed test contracts |
| **A11-06** | `lot_velocity_limit=30` incompatible with `initial_lots > 30` | `mmm_state.py` | Default `max(initial_lots * 3, 30)` |

### P2 — Fix Before Second Capital Increase

| ID | Description | Gap |
|---|---|---|
| A8-02 | Expiry-worthless positions never cleaned up (price=0 fill rejected) | Add cleanup/expiry-detection path |
| A8-01 | Concurrent same-side coids within 1 second → identical client_order_id | Add nonce to coid format |
| A7-02 | `_straddle_initial_credit` re-computes from post-roll positions on old sessions | Already mitigated by `_straddle_credit_v2` flag |
| A9-01 | Dual hot-reload sources (HOT_RELOAD_PARAMS + PARAM_RULES) can diverge | Consolidate to PARAM_RULES as single source |
| A9-02 | Forbidden strategy params silently stripped (not hard error) on mixed API requests | Warn in API response |
| A11-02 | No proactive API rate-limit budget tracking | Add shared token bucket per API key |
| A11-03 | SQLite write contention at N>5 concurrent sessions | Per-session DB sharding or async write queue |
| A11-04 | FillSync truncated at 300 fills/cycle; no backlog mechanism | Increase pagination or add backlog cycle |
| A3-09 | Stale close estimates advisory only; no auto-pause | Add operator alert on estimate > 10 min old |

### Resolved
| ID | Status |
|---|---|
| A6-04 | RESOLVED — `is_position_cap_hit` bool used in monitor, sealed by tests C4/C5/C13 |
| A5-13 | CLOSED — god layer params ARE in PARAM_RULES (F01-P1-009 fix). Was incorrect finding. |
| P0 Stale monitor | RESOLVED — three-layer guard intact |
| CRIT-1 fee wipe | RESOLVED — fees go through `record_fee()` into ledger |
| H-1 perp P&L | RESOLVED — perp included in total formula |

---

## 14. Invariants — NEVER BREAK

1. **`compute_current_total_pnl()` includes `_reverse['net_pnl']`** — formula sealed
2. **Reverse mode if/else is HARD — no fallthrough** to `_process_adjustment()`
3. **`session['_reverse']` is isolated** — never in ce/pe positions, never in active_lots
4. **Three-layer stale monitor guard** — H-4 + `_run_loop` + G5, all three must stay
5. **`recompute_side_lots()` is the single source** for lot scalars — derive from `positions[]`
6. **`emit_safety()` is a regular `def`** — never call in `run_until_complete()`
7. **`handle_stale_monitor()` must use STOP** (`_running=False`) not pause
8. **`_save_session()` return value must be checked** — callers abort on False
9. **`initialize_reverse_state(session)` if `'_reverse' not in session`** on every restore
10. **STRATEGY_DISPATCH is frozen** — strategy routing must not be added as inline `if` in monitor

---

## 15. Test Suite Reference

| Command | What it runs |
|---|---|
| `python3 -m pytest webui/ bot/ -m sealed -q` | **ALL sealed tests** (full suite — canonical command from AI_SEAL.md) |
| `python3 -m pytest webui/backend/routes/mmm/tests/ -m sealed -q` | MMM-area sealed tests only (~1191) — fast iteration check |
| `pytest webui/backend/routes/mmm/tests/ -x` | All tests, stop on first fail |
| `pytest webui/backend/routes/mmm/tests/test_sealed_mmm_safety.py` | Safety/kill switch sealed tests |
| `pytest webui/backend/routes/mmm/tests/test_sealed_kill_switch_and_hard_stop.py` | Kill switch tests |
| `pytest webui/backend/routes/mmm/tests/test_sealed_calculate_lots_to_sell.py` | Lot sizing sealed contracts |
| `pytest webui/backend/routes/mmm/tests/test_sealed_straddle_roll_pure.py` | Straddle roll sealed tests |
| `pytest --collect-only -m sealed` | Count sealed tests (verify before declaring sealed) |

**Sealing protocol:** New sealed tests go into existing `test_sealed_*.py` files (never create new). Always add `pytestmark = pytest.mark.sealed`. Verify with `--collect-only` before declaring sealed.

---

## 16. Common Debugging Queries

### "Why is lot count wrong after restart?"
→ Check `_watchdog_restarts` in session. If reconciliation ran, check `_watchdog_reconciliation` list. Known bug A7-01: `recompute_side_lots()` reverts reconciliation on first heartbeat. Check ledger: `SELECT SUM(qty) FROM session_fills WHERE session_id=? AND side='sell'` minus `SUM(qty)` for `side='buy'` per symbol.

### "Why is P&L showing wrong number?"
→ Check `unrealized_pnl` age. If premium fetch failed, it's stale (A3-01). Check `_fill_ledger` entries for unconfirmed estimates. Check if FillSync cursor is advancing (`_fill_sync_cursor_us`). Check if `realized_pnl` includes all confirmed fills.

### "Why is adjustment not firing?"
→ Check: (1) `strategy_status` is RUNNING. (2) `_paused` flag not set. (3) Whipsaw guard not in LOCKDOWN. (4) Gamma cap not in HARD regime. (5) `lot_velocity_limit` not exhausted. (6) `max_loss_amount` not breached. (7) Trend tier not BLOCK. (8) `_consecutive_dir_block` not set.

### "Why is P&L different from what I calculate manually?"
→ Display path uses `get_pnl()` (ledger read). Safety path uses `compute_current_total_pnl()` (cache). If session is live and heartbeat just ran, they should agree. If mid-heartbeat (fill_sync just ran but heartbeat not complete), ledger has the fill but cache doesn't yet.

### "Stale monitor alert fired unexpectedly"
→ Check `_monitor_generation` in session vs monitor's `_my_generation`. If stored_gen > my_gen, the monitor detected it was stale. Check for previous `start_session_monitor()` call that incremented generation.

### "Roll not executing"
→ Check all 12 gates in `_check_pure_roll_gates()` (STRADDLE_ROLL) or `check_straddle_roll_gates()` (STRADDLE_WITH_ADJUSTMENT). Gate 1: strategy match. Gate 2: strategy identity. Gate 6: `max_per_session=0` → no-roll mode. Gate 9: price freshness. Gate 10: net_pnl >= -min_credit_pct × initial_credit.

---

## 17. Backend Start/Stop

```bash
# Kill backend (port 5555)
kill -9 $(lsof -ti:5555)
# LaunchAgent auto-restarts — wait ~5s then check logs

# Logs
tail -f ~/Library/Logs/workingbot-backend.log
tail -f webui/backend/logs/backend_fixed.log.2
```

---

## 18. Active State Fields Quick Reference

```python
session.keys() — important ones:
  session_id, strategy_type, strategy_status
  ce, pe                     # side state dicts
  params                     # all operator config
  realized_pnl               # ledger cache
  unrealized_pnl             # live premium cache (can be stale)
  total_fees                 # ledger cache
  total_premium_collected    # gross only
  _net_premium_collected     # net (heartbeat cache)
  _fill_ledger               # in-memory ledger
  _fill_sync_cursor_us       # FillSync position
  _monitor_generation        # H-4 stale guard
  _watchdog_restarts         # counter
  _reverse                   # isolated reverse state
  _god                       # god layer state
  analytics                  # session analytics
  last_heartbeat             # ISO timestamp
  entry_time                 # ISO timestamp session started trading
  created_at                 # ISO timestamp session created
```
