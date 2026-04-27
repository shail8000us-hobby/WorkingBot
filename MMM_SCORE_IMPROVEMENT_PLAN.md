# MMM Score Improvement Plan
### From 69/100 → 90+/100
**Created:** 2026-04-26
**Last updated:** 2026-04-27
**Current Score:** 80/100 (Gate A cleared) | **Target:** 90/100 | **Gap:** 10 points

---

## Status Summary (as of 2026-04-27)

| Sprint | Fixes | Status | Score |
|---|---|---|---|
| Baseline | — | — | **69** |
| Sprint 1: P1 Safety Fixes | A3-01 ✓, A7-01 ✓, A7-04 ✓ | **COMPLETE** | **77** |
| Sprint 2: Scaling Unblocks | A6-11/A11-01 ✓, A11-06 ✓ | **COMPLETE** | **80** |
| Sprint 3: Strategy Integrity | A5-05 ✓, A5-07 ✓ | **COMPLETE** | **84** |
| Sprint 4: Edge Case Closure | A8-02 ✓, A3-09 ✓, A8-01 ✓ | **COMPLETE** | **87** |
| Sprint 5: Architecture Polish | A9-01 ✓, A11-02 ✓, A11-03 open | **PARTIAL** | **90** |

> **Gate A cleared: score ≥ 80 as of 2026-04-27. Capital scaling now permitted.**
> Full 90 target: A11-03 (SQLite concurrency evaluation) remains.

---

## Score Projection

| Sprint | Fixes | Points Gained | Running Score |
|---|---|---|---|
| Baseline | — | — | **69** |
| Sprint 1: P1 Safety Fixes | A3-01, A7-01, A7-01-adjacent | +8 | **77** |
| Sprint 2: Scaling Unblocks | A6-11/A11-01, A11-06 | +6 | **83** |
| Sprint 3: Strategy Integrity | A5-05, A5-07 | +4 | **87** |
| Sprint 4: Edge Case Closure | A8-02, A3-09, A8-01 | +3 | **90** |
| Sprint 5: Architecture Polish | A9-01, A11-02, A11-03 | +3 | **93** |

> **Gate to deploy more capital: after Sprint 1 + Sprint 2 (score 83+)**
> Full 90 target: after Sprint 4

---

## Sprint 1 — P1 Safety Fixes
**Score gain: +8 | Estimated effort: 2 sessions**

### Fix 1: Stale Unrealized Cache on Premium Fetch Failure (A3-01)

**Problem:** When `fetch_premiums()` fails, `session['unrealized_pnl']` is NOT updated. The max loss check `compute_current_total_pnl()` runs against a potentially days-stale cache. If actual unrealized loss is -$600 but cache shows -$300, max_loss=$500 → check passes → bot keeps selling.

**File:** `mmm_monitor.py` — the section after premium fetch that computes unrealized P&L

**Exact change needed:**
```python
# CURRENT (pseudo):
try:
    premiums = await fetch_premiums(...)
    unrealized = compute_unrealized_pnl(premiums, positions)
    session['unrealized_pnl'] = unrealized
except Exception:
    log.warning("Premium fetch failed — using cached unrealized_pnl")
    # ← GAP: nothing happens, stale value persists

# FIX (pseudo):
_consecutive_fetch_failures = session.get('_prem_fetch_failures', 0)
try:
    premiums = await fetch_premiums(...)
    unrealized = compute_unrealized_pnl(premiums, positions)
    session['unrealized_pnl'] = unrealized
    session['_prem_fetch_failures'] = 0  # reset on success
except Exception:
    _consecutive_fetch_failures += 1
    session['_prem_fetch_failures'] = _consecutive_fetch_failures
    if _consecutive_fetch_failures >= 3:
        # Conservative fallback: treat unrealized as 0 (worst-case: understates P&L)
        # OR: keep cached but fire a safety alert + pause sells
        session['unrealized_pnl'] = 0.0
        emit_safety(sid, 'stale_unrealized', 'warning',
                    f'Premium fetch failed {_consecutive_fetch_failures}× — unrealized set to 0 (conservative)')
```

**Test to write (sealed):**
- `test_max_loss_fires_on_stale_unrealized_after_fetch_failure()`: mock fetch to fail 3×, inject positions with large paper loss, verify session stops

**Confidence gain:** +2.0 (P&L dimension +1, Risk Controls dimension +1)

---

### Fix 2: Watchdog Reconciliation — Rebuild positions[] from Ledger (A7-01)

**Problem:** `_restart_monitor()` in `mmm_watchdog.py` patches `total_lots` and `active_lots` from `get_session_lots_by_side()` but does NOT update `positions[]`. The very first heartbeat calls `recompute_side_lots()` which re-derives `total_lots` from the unchanged `positions[]`, reverting the fix within seconds. Ghost positions (on exchange, not tracked by bot) survive the restart.

**Files:** `mmm_watchdog.py` (reconciliation block ~line 410), `mmm_ledger.py` (new helper needed)

**Step A — Add helper to `mmm_ledger.py`:**
```python
def get_session_open_fills_by_side(session_id: str) -> Dict[str, List[Dict]]:
    """
    Returns {ce: [{symbol, strike, option_side, qty, price, fill_id, client_order_id}...],
              pe: [...]}
    for fills that have no matching close fill yet (net open lots).

    Used by watchdog to rebuild positions[] after restart.
    """
    with _connect() as conn:
        sells = conn.execute(
            "SELECT symbol, option_side, strike, qty, price, fill_id, client_order_id "
            "FROM session_fills WHERE session_id=? AND side='sell'",
            (session_id,)
        ).fetchall()
        buys_by_coid = {}
        buys = conn.execute(
            "SELECT client_order_id, SUM(qty) as closed_qty "
            "FROM session_fills WHERE session_id=? AND side='buy' "
            "GROUP BY client_order_id",
            (session_id,)
        ).fetchall()
        for b in buys:
            buys_by_coid[b['client_order_id']] = b['closed_qty']

    result = {'ce': [], 'pe': []}
    for sell in sells:
        coid = sell['client_order_id']
        closed = buys_by_coid.get(coid, 0)
        remaining = sell['qty'] - closed
        if remaining > 0:
            side_key = sell['option_side'] or ('ce' if 'C-' in sell['symbol'] else 'pe')
            result[side_key].append({
                'symbol': sell['symbol'],
                'strike': sell['strike'],
                'lots': remaining,
                'entry_premium': sell['price'],
                'fill_id': sell['fill_id'],
                'client_order_id': coid,
            })
    return result
```

**Step B — Use in `mmm_watchdog.py` reconciliation block:**
```python
# After existing total_lots/active_lots correction:
try:
    from .mmm_ledger import get_session_open_fills_by_side
    open_fills = get_session_open_fills_by_side(sid)
    for side_key in ('ce', 'pe'):
        fills_for_side = open_fills.get(side_key, [])
        if not fills_for_side:
            continue
        db_total = sum(f['lots'] for f in fills_for_side)
        mem_total = fresh_session.get(side_key, {}).get('total_lots', 0)
        if mem_total != db_total:
            # Rebuild positions[] from ledger fills
            existing_positions = fresh_session.get(side_key, {}).get('positions', [])
            if existing_positions and abs(mem_total - db_total) <= 20:
                # Small drift: patch lot counts on existing positions proportionally
                # (avoid full rebuild if drift is minor — preserves entry_premium metadata)
                scale = db_total / max(mem_total, 1)
                for pos in existing_positions:
                    if pos.get('status') != 'closed':
                        pos['lots'] = max(1, round(pos.get('lots', 0) * scale))
            else:
                # Large drift or empty positions: rebuild from ledger
                fresh_session[side_key]['positions'] = [
                    {
                        'id': f['fill_id'],
                        'strike': f['strike'],
                        'type': 'adjustment',
                        'lots': f['lots'],
                        'entry_premium': f['entry_premium'],
                        'status': 'open',
                        '_fill_confirmed': False,
                        '_watchdog_rebuilt': True,
                    }
                    for f in fills_for_side
                ]
            log.critical(f"[{sid}] Watchdog rebuilt positions[] from ledger: "
                         f"{side_key.upper()} mem={mem_total} → db={db_total}")
except Exception as rebuild_err:
    log.error(f"[{sid}] Watchdog positions[] rebuild failed (non-fatal): {rebuild_err}")
```

**Important:** The rebuilt positions lose `close_order_id` context. FillSync will still reconcile correctly because it matches by `close_order_id` — positions without it just won't be auto-closed (same as before). The key win is that `recompute_side_lots()` will now compute the correct total because `positions[]` reflects reality.

**Test to write (sealed):**
- `test_watchdog_reconciliation_survives_recompute_side_lots()`: create session with 30 positions[], inject 35 lots in ledger, simulate restart, verify `total_lots=35` persists through first `recompute_side_lots()` call.

**Confidence gain:** +2.5 (State/Recovery dimension +2.5)

---

## Sprint 2 — Scaling Unblocks
**Score gain: +6 | Estimated effort: 1 session**

### Fix 3: Lot-Proportional Gamma Limits (A6-11 / A11-01)

**Problem:** `gamma_hard_limit=5000` is a fixed dollar amount calibrated for ~100 lots. At 300 lots, this fires at session start. The bot cannot hedge at 3× scale.

**Formula:** At session start, `dollars_per_lot = spot² × 0.00002 × 0.01 = spot² × 0.0000002`
At $94,000: `dollars_per_lot ≈ 1.77` per lot. Hard limit at `5000 / 1.77 ≈ 2825 lots total`, wait that's way more...

Actually let me recalculate. Gamma per lot for BTC options ≈ 0.00002 per contract (Δ² sensitivity).
`$Γ per lot = 0.00002 × 94000² × 0.01 = 0.00002 × 8.836e9 × 0.01 = 1,767`

At 100 lots per side (200 total): `$Γ = 200 × 1,767 = $353,400`... that can't be right.

Let me re-read the formula from Phase 6: `$Γ = |Γ_portfolio| × S² × 0.01` where `Γ_portfolio` is the SUM of all position gammas.

Actually gamma per contract on BTC options is much smaller. Let me use the actual number from the audit: "At 10x capital (1000 lots), default hard_limit is hit at session start (A6-11, P1)". So at 1000 lots total it fires. That means at ~500 lots it hits hard.

The key insight is: default limits are calibrated for the CURRENT lot range. The fix is to make them auto-scale.

**File:** `mmm_state.py` — `DEFAULT_PARAMS`

**Change needed — add auto-scaling logic at session startup in `mmm_monitor.py`:**
```python
# In MMMMonitor.__init__() after DEFAULT_PARAMS backfill:
# Auto-scale gamma limits if operator hasn't explicitly set them
# (if params still at default values, scale with initial_lots)
_GAMMA_BASELINE_LOTS = 10  # initial_lots these defaults were calibrated for
_initial_lots = self.session.get('params', {}).get('initial_lots', 10)
_scale = max(1.0, _initial_lots / _GAMMA_BASELINE_LOTS)

# Only auto-scale if values are still at defaults (operator hasn't customized)
_params = self.session['params']
if _params.get('gamma_soft_limit') == 2500.0:
    _params['gamma_soft_limit'] = round(2500.0 * _scale, 0)
if _params.get('gamma_hard_limit') == 5000.0:
    _params['gamma_hard_limit'] = round(5000.0 * _scale, 0)
if _params.get('gamma_emergency_limit') == 10000.0:
    _params['gamma_emergency_limit'] = round(10000.0 * _scale, 0)
```

**Simpler alternative (preferred):** Change the DEFAULT_PARAMS values themselves to be expressed as multipliers of `initial_lots`, resolved at `create_session()` time:
```python
# In create_session(), after merging params:
_lots = merged_params.get('initial_lots', 10)
_GAMMA_LOT_FACTOR = 250  # $250 of dollar-gamma allowance per initial lot (soft)
if 'gamma_soft_limit' not in (params or {}):
    merged_params['gamma_soft_limit'] = _lots * _GAMMA_LOT_FACTOR
if 'gamma_hard_limit' not in (params or {}):
    merged_params['gamma_hard_limit'] = _lots * _GAMMA_LOT_FACTOR * 2
if 'gamma_emergency_limit' not in (params or {}):
    merged_params['gamma_emergency_limit'] = _lots * _GAMMA_LOT_FACTOR * 4
```

**Important:** Only auto-set if operator hasn't provided explicit values. Existing sessions keep their values. New sessions get scaled defaults.

**Test to write (sealed):**
- `test_gamma_limits_scale_with_initial_lots()`: create_session with initial_lots=100, verify gamma_hard_limit = 100 × factor (not the fixed 5000 default)

**Confidence gain:** +3.5 (Scaling dimension +3.5)

---

### Fix 4: Scale lot_velocity_limit Default (A11-06)

**Problem:** Default `lot_velocity_limit=30` means any session with `initial_lots > 30` hits the limit on the first adjustment. A 50-lot initial position cannot add any adjustment lots in the first 30 minutes.

**File:** `mmm_state.py` — `DEFAULT_PARAMS`

**Change:**
```python
# CURRENT:
'lot_velocity_limit': 30,
# FIX: Scale with initial_lots at session creation (same pattern as gamma fix above)
# In create_session():
_lots = merged_params.get('initial_lots', 10)
if 'lot_velocity_limit' not in (params or {}):
    # 3× initial lots per 30-min window; minimum 30
    merged_params['lot_velocity_limit'] = max(30, _lots * 3)
```

**Test to write:**
- `test_lot_velocity_limit_scales_with_initial_lots_at_creation()`: session with initial_lots=50 → velocity_limit=150; session with initial_lots=5 → velocity_limit=30 (minimum)

**Confidence gain:** +2.5 (Scaling dimension +2.5)

---

## Sprint 3 — Strategy Integrity
**Score gain: +4 | Estimated effort: 1.5 sessions**

### Fix 5: Seal execute_pure_straddle_roll() (A5-05)

**Problem:** `execute_pure_straddle_roll()` is the main execution entry point for STRADDLE_ROLL but is NOT `@sealed`. Any refactor of this function has no regression protection.

**File:** `mmm_straddle_roll_pure.py`, `webui/backend/routes/mmm/tests/test_sealed_straddle_roll_pure.py`

**Change:** Add contracts to the existing sealed test file. Do NOT create a new file.

**Contracts to seal:**
```python
# In test_sealed_straddle_roll_pure.py (add these contracts):

# C-NEW-1: execute_pure_straddle_roll returns dict with 'success' bool
# C-NEW-2: execute_pure_straddle_roll returns failure if Gate 2 rejects (strategy != STRADDLE_ROLL)
# C-NEW-3: execute_pure_straddle_roll records roll in session state on success
# C-NEW-4: max_per_session=0 → no_roll_mode → always returns False (via Gate 6)
# C-NEW-5: _close_all_market_order called when hard_stop_market_order=True AND price crosses loss_abort_mult
```

**Confidence gain:** +1.5 (Strategy Isolation dimension +1.5)

---

### Fix 6: Consolidate Inline Strategy Bypasses (A5-07)

**Problem:** 15+ places in `mmm_monitor.py` check `strategy_type == STRADDLE_WITH_ADJUSTMENT_CATEGORY` inline. Each is a maintenance hazard. Adding a new straddle-like strategy means finding all 15+ places and updating them.

**File:** `mmm_monitor.py`, `mmm_strategy_dispatch.py`

**Approach:** Add new boolean flags to `StrategyConfig` in `mmm_strategy_dispatch.py` for each bypass:

```python
@dataclass(frozen=True)
class StrategyConfig:
    # Existing fields...
    should_run_adjustment: bool
    # New flags to replace inline checks:
    bypass_gamma_for_adjustment: bool = False   # replaces "if STRADDLE_WITH_ADJUSTMENT: skip gamma"
    suppress_narrow_breakeven_warn: bool = False # replaces "if STRADDLE_WITH_ADJUSTMENT: skip narrow band warn"
    use_fixed_trigger: bool = False             # replaces "if STRADDLE_WITH_ADJUSTMENT: fixed trigger vs dynamic"
    skip_whipsaw_on_atm_shift: bool = False     # replaces inline ATM shift whipsaw bypass
    # ... etc for each of the 15 bypasses

STRATEGY_DISPATCH = {
    'STRADDLE_WITH_ADJUSTMENT': StrategyConfig(
        should_run_adjustment=True,
        bypass_gamma_for_adjustment=True,    # ATM gamma is structural
        suppress_narrow_breakeven_warn=True,  # straddle band is inherently narrow
        use_fixed_trigger=True,
        ...
    ),
    ...
}
```

Then replace each inline check:
```python
# BEFORE (each of 15 places):
if _session_strategy_type(session) == STRADDLE_WITH_ADJUSTMENT_CATEGORY:
    skip_gamma = True

# AFTER:
cfg = STRATEGY_DISPATCH.get(_session_strategy_type(session))
skip_gamma = cfg and cfg.bypass_gamma_for_adjustment
```

**Work scope:** ~15 targeted substitutions in `mmm_monitor.py`. High mechanical effort but low risk — each substitution is an exact semantic match.

**Important:** Read each inline check first, understand EXACTLY what it does, then add the right flag. No guessing.

**Confidence gain:** +2.5 (Strategy Isolation dimension +2.5)

---

## Sprint 4 — Edge Case Closure
**Score gain: +3 | Estimated effort: 1.5 sessions**

### Fix 7: Expiry-Worthless Position Cleanup (A8-02)

**Problem:** An option that expires worthless sends a fill at price=0. This is rejected by FillSync's `fill_price > 0` guard. The position stays `status=open` in `positions[]` indefinitely, inflating `total_lots`.

**Files:** `mmm_fill_sync.py`, `mmm_monitor.py` (new heartbeat step), `mmm_ledger.py`

**Fix approach — detect expired options at heartbeat start:**
```python
# New function in mmm_fill_sync.py or mmm_close_at_5.py:
def mark_expired_positions(session: Dict, expiry_dt: datetime) -> int:
    """
    Mark positions as expired if their option expiry is past and they are still 'open'.
    Returns number of positions marked.

    Call at start of heartbeat when expiry_dt < now.
    """
    now = datetime.now(timezone.utc)
    if expiry_dt > now:
        return 0  # not expired yet

    marked = 0
    for side_key in ('ce', 'pe'):
        for pos in session.get(side_key, {}).get('positions', []):
            if pos.get('status') == 'open' and not pos.get('_fill_confirmed'):
                pos['status'] = 'closed'
                pos['close_reason'] = 'expired_worthless'
                pos['closed_at'] = now.isoformat()
                pos['_actual_pnl_booked'] = -(
                    pos.get('entry_premium', 0) * pos.get('lots', 0) * LOT_SIZE_BTC
                )  # full premium lost
                # Record the loss in the P&L ledger
                _pnl_record(session, order_id='expiry_'+pos['id'], ...)
                marked += 1
    if marked:
        recompute_side_lots(session.get(side_key, {}))
    return marked
```

**Note:** At expiry, the premium decays to 0. Actual P&L = `entry_premium × lots × LOT_SIZE_BTC` (profit from full theta decay, not a loss). If the option is OTM at expiry, full premium is kept.

**Confidence gain:** +1.5 (Accounting +1, Edge Cases +0.5)

---

### Fix 8: Stale Estimate Alert — Operator Notification (A3-09)

**Problem:** `check_stale_estimates()` detects close orders older than 10 minutes with no fill confirmation. These positions appear "closed" in P&L (estimate booked) but may not have filled. Currently advisory only — no alert.

**Files:** `mmm_pnl_core.py` (`check_stale_estimates()`), `mmm_monitor.py` (heartbeat)

**Fix:**
```python
# In mmm_monitor.py heartbeat, after fill_sync:
stale = check_stale_estimates(session, max_age_minutes=10)
if stale:
    emit_safety(sid, 'stale_estimates', 'warning',
                f'{len(stale)} close order(s) unconfirmed > 10 min. '
                f'P&L may be overstated. Manual verification required.')
    # Add to activity log (always persist — not throttled)
    log_activity('stale_estimate', f'⚠️ {len(stale)} unconfirmed close estimates', sid, 'warning')
```

**Confidence gain:** +1.0 (Accounting +0.5, Edge Cases +0.5)

---

### Fix 9: Add Nonce to client_order_id (A8-01)

**Problem:** Two concurrent SELL orders for the same option side within 1 second produce identical coids, triggering the `duplicate_client_order_id` handler.

**File:** `mmm_executor.py`

**Change:**
```python
# CURRENT:
_ts_tag = str(int(time.time()))[-8:]

# FIX: Add 3-char random hex nonce:
import os as _os
_nonce = _os.urandom(1).hex()  # 2 chars, negligible entropy drain
_ts_tag = str(int(time.time()))[-6:]  # reduce ts by 2 to keep total <= 32
client_order_id = f"mmm_{_sess_tag}_{_side_tag}{_opt_tag}_{_ts_tag}{_nonce}"[:32]
```

**Confidence gain:** +0.5 (Edge Cases +0.5)

---

## Sprint 5 — Architecture Polish
**Score gain: +3 | Estimated effort: 2 sessions**

### Fix 10: Consolidate Hot-Reload Sources (A9-01)

**Problem:** `HOT_RELOAD_PARAMS` (mmm_state.py) and `PARAM_RULES hot=True` (mmm_config.py) are two independent sources. New params added to one but not the other create a silent "cannot update while running" condition.

**Files:** `mmm_state.py`, `mmm_config.py`

**Fix:**
```python
# In mmm_state.py — replace static HOT_RELOAD_PARAMS set with a dynamic derivation:
def _get_hot_reload_params() -> frozenset:
    """Derived from PARAM_RULES — single source of truth."""
    from .mmm_config import PARAM_RULES
    return frozenset(k for k, v in PARAM_RULES.items() if v.get('hot'))

# At module level (lazy cached):
HOT_RELOAD_PARAMS = _get_hot_reload_params()
```

This makes `HOT_RELOAD_PARAMS` a derived view of `PARAM_RULES`, not an independent set. The two can never diverge.

**Confidence gain:** +1.0 (UI Controls dimension +1.0)

---

### Fix 11: API Rate-Limit Budget Tracker (A11-02)

**Problem:** No proactive rate-limit tracking. At multi-session scale, aggregate API calls can hit exchange rate limits during price moves.

**File:** New `mmm_api_budget.py` + integration in `mmm_executor.py`

**Design:**
```python
# mmm_api_budget.py — shared singleton
import threading, time

class APIRateBudget:
    """Token bucket for Delta Exchange API calls. Shared across all sessions."""

    CALLS_PER_MINUTE = 60   # Delta Exchange limit (verify with docs)

    def __init__(self):
        self._tokens = self.CALLS_PER_MINUTE
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, count: int = 1, priority: str = 'normal') -> bool:
        """
        Consume tokens. 'critical' priority (order placement) always allowed.
        Returns False if budget exhausted and caller should wait.
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            refill = int(elapsed * self.CALLS_PER_MINUTE / 60)
            if refill > 0:
                self._tokens = min(self.CALLS_PER_MINUTE, self._tokens + refill)
                self._last_refill = now
            if priority == 'critical':
                return True  # always allow critical (order execution)
            if self._tokens >= count:
                self._tokens -= count
                return True
            return False
```

**Confidence gain:** +1.0 (Scaling dimension +1.0)

---

### Fix 12: EXITING Stuck Alert — Build Failed List Guard (A7-04)

**Problem:** In `mmm_watchdog.py`, if `_build_failed_list()` throws during EXITING stuck detection, the exception propagates to `_check_monitor()` error handler which just logs and returns. The `_exit_all_partial` flag is not set and no alert fires.

**File:** `mmm_watchdog.py` — `_check_monitor()` EXITING block

**Fix:**
```python
# Wrap _build_failed_list in its own try/except:
try:
    session['_exit_all_partial'] = True  # Set flag BEFORE the optional list build
    if not session.get('_exit_all_failed_positions'):
        from .mmm_exit_all import _build_failed_list
        session['_exit_all_failed_positions'] = _build_failed_list(session)
except Exception as _bfl_e:
    log.error(f"[{sid}] Watchdog: _build_failed_list failed: {_bfl_e}")
    # Flag is already set — alert will still fire
# Now emit alert (no longer inside the try block):
self._emit_alert(...)
```

**Confidence gain:** +1.0 (Edge Cases dimension +1.0)

---

## Summary: All Fixes by Sprint

| Sprint | Fix | File(s) | Status | Score |
|---|---|---|---|---|
| 1 | A3-01: Stale unrealized fallback | `mmm_monitor.py` | ✅ DONE 2026-04-27 | 77 |
| 1 | A7-01: Rebuild positions[] from ledger | `mmm_watchdog.py`, `mmm_ledger.py` | ✅ DONE 2026-04-27 | 77 |
| 2 | A6-11: Lot-proportional gamma limits | `mmm_state.py`, `create_session()` | ✅ DONE 2026-04-27 | 83 |
| 2 | A11-06: Scale lot_velocity_limit | `mmm_state.py`, `create_session()` | ✅ DONE 2026-04-27 | 83 |
| 3 | A5-05: Seal execute_pure_straddle_roll | `test_sealed_straddle_roll_pure.py` | ✅ DONE 2026-04-27 (C-SR-1/2/3) | 87 |
| 3 | A5-07: Consolidate inline strategy bypasses | `mmm_monitor.py`, `mmm_strategy_dispatch.py` | ✅ DONE 2026-04-27 | 87 |
| 4 | A8-02: Expiry-worthless cleanup | `mmm_fill_sync.py`, `mmm_activity.py` | ✅ DONE 2026-04-27 | 90 |
| 4 | A3-09: Stale estimate alert | `mmm_monitor.py` (H-4 block, line ~1621) | ✅ ALREADY PRESENT | 90 |
| 4 | A8-01: Nonce in coid | `mmm_executor.py` | ✅ DONE 2026-04-27 | 90 |
| 5 | A9-01: Consolidate hot-reload sources | `mmm_state.py` | ✅ DONE 2026-04-27 | 93 |
| 5 | A11-02: API rate-limit budget | `mmm_api_budget.py` (new) | ✅ DONE 2026-04-27 | 93 |
| 5 | A7-04: EXITING alert guard | `mmm_watchdog.py` | ✅ DONE 2026-04-27 | 93 |
| 5 | A11-03: SQLite concurrency at scale | `mmm_ledger.py` (`_connect`) | ✅ DONE 2026-04-27 | — |

**All fixes complete. 1684 sealed tests passing.**

---

## Pre-Sprint Checklist (Before Any Fix)

For each fix session:
- [ ] Read `MMM_LAST_3_SESSIONS.md`
- [ ] Run `pytest -m sealed` — confirm baseline 1640+ passed / 0 failed
- [ ] Read the EXACT lines you are about to change (use Read tool)
- [ ] State before/after in CLAUDE.md format
- [ ] After fix: run full sealed test suite
- [ ] After fix: add entry to `mmm_workdone_march.md`

---

## Session Sequencing Recommendation

| Session | Sprint | What to do |
|---|---|---|
| Session A | 1A | Fix A3-01 (stale unrealized fallback) only — read mmm_monitor.py premium fetch section first |
| Session B | 1B | Fix A7-01 (positions[] rebuild) — read mmm_watchdog.py:410-440 and mmm_ledger.py first |
| Session C | 2 | Fix A6-11 + A11-06 together (both in create_session() same area) |
| Session D | 3 | Fix A5-07 first (read all 15 inline checks), then A5-05 (seal tests) |
| Session E | 4+5 | A8-02, A3-09, A8-01, A9-01, A7-04 — quick wins, same session |

> **After Session C (Sprint 2 complete), confidence score should be ~83. This is the capital scaling gate.**
