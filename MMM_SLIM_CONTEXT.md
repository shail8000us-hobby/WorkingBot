# MMM_SLIM_CONTEXT.md — Distilled MMM Reference
# For full history and details: AI_MMM_CONTEXT.md (archived) and mmm_workdone_march.md

---

## 1. What MMM Does (Strategy Core)

MMM is a BTC options premium-selling algorithm on Delta Exchange.

- Sells **short strangles**: CE (call) + PE (put) at OTM strikes on 0DTE BTC options
- **Heartbeat** (~30s): fetches live CE/PE premiums, evaluates triggers, adjusts positions
- **Adjustment**: when one side (aggressor) premium rises above `min_trigger_move`, sells more of the opposite (passive) side to collect premium and offset the loss
- **Strike shift**: when premium decays below `shift_threshold` (~$50), freezes current position and opens a new one at a fresh OTM strike
- **Close-at-threshold**: buys back positions when premium drops to `close_at_threshold` (~$20)
- **Max loss hard stop**: when total P&L ≤ `-max_loss_amount`, calls `_auto_close_all()` and stops

**Strategy types (mutually exclusive per session):**
- `STANDARD_MMM_CATEGORY` — default, asymmetric strangle
- `STRADDLE_WITH_ADJUSTMENT_CATEGORY` — both legs at same ATM strike; most guards bypassed for this type (see Section 3)
- `PURE_STRADDLE_ROLL_CATEGORY` — roll-based variant

---

## 2. Capital Structure & Key Constants

| Constant | Value | Source |
|----------|-------|--------|
| `LOT_SIZE_BTC` | 0.001 BTC per lot | `mmm_constants.py` |
| P&L unit | BTC (not USD) | `premium_usd × lots × 0.001` |
| P&L formula | `(premium_now - trigger) × active_lots × LOT_SIZE_BTC` + frozen loop | `mmm_engine.py` |
| Frozen P&L | Per-position: `(current - entry) × lots × LOT_SIZE_BTC` | `mmm_engine.py: calculate_standard_loss()` |
| Total P&L | `unrealized + realized + reverse_pnl` | `mmm_pnl_core.py: compute_current_total_pnl()` |

**Lot sizing chain** (inside `calculate_lots_to_sell()`):
`base_lots = ceil(loss / hedge_premium)` → apply breakeven multiplier → apply gamma-aware multiplier → apply trend boost → clamp to `max_lots_per_side` and `max_combined_lot_multiplier`

**Position cap**: `max_lots_per_side` (per CE or PE). Combined cap: `max_combined_lot_multiplier × starting_lots`.

---

## 3. Three Invariants Claude Must NEVER Break

### INVARIANT 1 — Stale Monitor Three-Layer Guard (P0 incident 2026-03-24)

A stale `MMMMonitor` placed 560 real SELL orders. Three layers protect against this — ALL must stay intact:

1. **`start_session_monitor()` — `thread.join(15s)`**: waits for old thread to exit before starting new one
2. **`_run_loop` primary guard**: checks `stored_gen > self._my_generation` at top of each loop; if stale → `_running = False` + `emit_safety()` (sync, NOT async) + break
3. **Guardian G5 in `_heartbeat()`**: after `pre_beat_snapshot()`, calls `check_generation_integrity()`; if stale → `handle_stale_monitor()` with STOP (not pause)

**Critical:** `emit_safety()` is a regular `def` — never wrap in `run_until_complete()`. `handle_stale_monitor()` must use STOP, not pause.

---

### INVARIANT 2 — Reverse Mode Hard Rules (implemented 2026-03-26)

The hard if/else in `mmm_monitor.py` (~line 2781) is SACRED:
```python
if session.get('params', {}).get('reverse_enabled', False) and \
        session.get('_reverse', {}).get('active', False):
    await process_reverse_entry(...)
else:
    # Normal MMM adjustment — NEVER modify this else branch for reverse purposes
```
- NEVER add fallthrough from the reverse block to `_process_adjustment()`
- NEVER put reverse positions in `session['ce']['positions']` or `session['pe']['positions']`
- NEVER include `session['_reverse']['total_lots']` in `active_lots` or `adjustment_count`
- `compute_current_total_pnl()` MUST include `+ session.get('_reverse', {}).get('net_pnl', 0.0)`
- New sessions missing `_reverse` key: call `initialize_reverse_state(session)` on load
- All reverse logic lives ONLY in `mmm_reverse.py`

---

### INVARIANT 3 — `_auto_close_all()` Close Order

Close order must stay: **reverse → perp → core (CE/PE)**

Reversing the order orphans open short positions on the exchange.

---

## 4. Key File Map — Who Owns What

| File | Responsibility |
|------|----------------|
| `mmm_engine.py` | Core P&L formulas: `calculate_standard_loss()`, `calculate_reversal_loss()`, `compute_unrealized_pnl()`, `calculate_lots_to_sell()` |
| `mmm_constants.py` | `LOT_SIZE_BTC=0.001`, strike constants, category names |
| `mmm_monitor.py` | `MMMMonitor` class — heartbeat loop, all regime/safety/adjustment orchestration (~7000 lines) |
| `mmm_reverse.py` | SOLE owner of all Reverse Mode logic |
| `mmm_pnl_core.py` | `compute_current_total_pnl()` — total P&L including reverse_pnl |
| `mmm_api.py` | REST endpoints: start/stop/adopt/reduce/config/reconcile |
| `mmm_executor.py` | `smart_execute()` — order placement with retries and DTE-aware repricing |
| `mmm_state.py` | Session state defaults, `HOT_RELOAD_PARAMS`, `DEFAULT_PARAMS` |
| `mmm_storage.py` | Session persistence (SQLite) |
| `mmm_safety.py` | Safety checks: lot_velocity, asymmetry, position_cap, max_loss, trailing_stop |
| `mmm_regime.py` | Gamma/trend/volatility regime classification |
| `mmm_guardian.py` | Generation integrity checks (stale monitor guard layer 3) |
| `mmm_trigger.py` | Trigger evaluation — when to fire an adjustment |
| `mmm_strike_shift.py` | Strike shift logic |
| `mmm_close_at_5.py` | Close positions at decay threshold |
| `mmm_harvester.py` | M1 profit harvesting |
| `mmm_recycler.py` | Shift-time recycle (close cheap frozen positions during shift) |
| `mmm_config.py` | Param validation rules and hot-reload schema |
| `mmm_activity.py` | Activity log event type registry |
| `mmm_watchdog.py` | Kills/restarts monitors stuck for >450s |
| `tests/` | Sealed test suite — baseline 1421 passed (2026-04-17) |
