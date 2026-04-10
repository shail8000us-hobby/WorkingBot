# STRADDLE_ROLL — Pure Straddle Roll: Implementation Plan
**Created: 2026-04-10**
**Status: APPROVED — ready to implement**
**Preset string: `STRADDLE_ROLL`**
**Supersedes: Section 10 of STRADDLE_ROLL_FIX_PLAN.md**

---

## Decisions Locked In

| Decision | Answer |
|----------|--------|
| Lives inside MMM | Yes — same process, same infrastructure, preset-gated |
| Hard stop level | `max_loss_amount` — **required field at session creation, hot-reloadable at any time** |
| Hard stop order type | Market order — must fill immediately regardless of spread |
| Max rolls | **Required field at session creation, hot-reloadable** — no preset default |
| Telegram when max rolls exhausted | Yes — fires once on the roll that uses the last slot |
| MMM adjustment engine between rolls | Disabled via `min_trigger_move: 9999` — no code change to engine |
| CE:PE ratio | Always 1:1 — `max_lots_per_side` locked to `initial_lots` in preset |
| Surgical changes to existing files | Accepted — all backward-compatible, all gated on `STRADDLE_ROLL` |

---

## Strategy Decision Tree (Complete — Nothing Else)

```
═══════════════════════════════════════════════════
 EVERY 5s — Price Guard (reads WS, zero API calls)
═══════════════════════════════════════════════════
 spot_move ≥ (trigger_pts - price_guard_buffer_pts)?  →  fire force_heartbeat()
 estimated_loss ≥ max_loss_amount × 0.85?             →  fire force_heartbeat()
 After any fire: 30s cooldown before next fire

═══════════════════════════════════════════════════
 EVERY 120s — or IMMEDIATELY when Price Guard fires
═══════════════════════════════════════════════════
 STEP 1 — HARD STOP
   total_loss ≥ max_loss_amount?
   → YES: Close all positions — MARKET ORDER
          STOP session
          Telegram CRITICAL
          Done. No re-entry.

 STEP 2 — EXPIRY GUARD
   minutes_to_expiry < 10?
   → YES: Close all — limit order. STOP. Telegram INFO.
   minutes_to_expiry < 90?
   → YES: Skip roll evaluation. Log "inside window". Return.

 STEP 3 — ROLL
   spot_move_pts < trigger_pts?
   → YES: Do nothing. Theta working. Return.

   → Run gates (margin, cooldown, max_rolls, spread, same_strike, min_credit)
   → Any gate fails? Log reason. Return.
   → Execute 4-leg roll (limit orders — ITM close, OTM close, new CE sell, new PE sell)
   → Update trigger_pts = new_CE_fill + new_PE_fill
   → Reset regime/IV/interval state
   → Telegram INFO: roll number, old→new ATM, pts moved, new trigger
   → If roll_count == max_rolls: Telegram WARNING (exhaustion alert — fires once)

 OTHERWISE → nothing.
═══════════════════════════════════════════════════
```

---

## File Map

### New Files (no risk to existing algo)

| File | Purpose |
|------|---------|
| `webui/backend/routes/mmm/mmm_straddle_roll_pure.py` | All pure roll logic: gates, 4-leg roll, hard stop, Telegram |
| `webui/backend/routes/mmm/tests/test_sealed_straddle_roll_pure.py` | 18 sealed tests |

### Modified Files (surgical only)

| File | Change | Lines | Isolation |
|------|--------|-------|-----------|
| `mmm_dte_presets.py` | Add `STRADDLE_ROLL_CATEGORY` constant + `build_straddle_roll_preset()` | ~35 new | New `elif` only, no existing function touched |
| `mmm_state.py` | Add `straddle_roll_hard_stop_market_order` to `DEFAULT_PARAMS` + hot-reload list | 2 lines | New dict key with `False` default — existing callers unaffected |
| `mmm_monitor.py` | 4 surgical cuts (see below) | ~12 lines | Each cut gated on `STRADDLE_ROLL_CATEGORY` |
| `mmm_close_at_5.py` | Add `order_type: str = 'limit'` to `close_position()` signature | 1 line | Default `'limit'` — all 15+ existing callers unchanged |
| `mmm_executor.py` | Add `place_market_order_immediate()` method | ~25 lines | New method, does not touch existing methods |
| `mmm_api.py` | Add STRADDLE_ROLL session creation validation block | ~20 lines | New `elif` after existing STRADDLE_WITH_ADJUSTMENT block |
| `MMMDashboard.js` | Preset badge + trigger pts display + price guard indicator | ~20 lines | Display only |

**NOT touched:** `mmm_engine.py`, `mmm_constants.py`, `mmm_wind_down.py`, `mmm_trigger.py`,
`mmm_replenish.py`, `mmm_regime.py`, `mmm_guardian.py`, `mmm_fill_sync.py`, `mmm_pnl_core.py`,
`mmm_straddle_adjustment.py`, `mmm_reverse.py`, all existing sealed test files.

---

## Cut-by-Cut: mmm_monitor.py (4 surgical cuts)

### Cut 1 — Import (line 87)
Add `STRADDLE_ROLL_CATEGORY` to the existing import.
```python
# BEFORE:
from .mmm_dte_presets import STRADDLE_WITH_ADJUSTMENT_CATEGORY, SHORT_STRADDLE_CATEGORY

# AFTER:
from .mmm_dte_presets import (
    STRADDLE_WITH_ADJUSTMENT_CATEGORY, SHORT_STRADDLE_CATEGORY, STRADDLE_ROLL_CATEGORY
)
```

### Cut 2 — Price guard start (line 528)
STRADDLE_ROLL reuses the existing price guard coroutine — it reads `_straddle_roll_trigger_pts`
which both presets populate identically.
```python
# BEFORE:
if self.session.get('params', {}).get('_preset_source') in (
    STRADDLE_WITH_ADJUSTMENT_CATEGORY, SHORT_STRADDLE_CATEGORY
):

# AFTER:
if self.session.get('params', {}).get('_preset_source') in (
    STRADDLE_WITH_ADJUSTMENT_CATEGORY, SHORT_STRADDLE_CATEGORY, STRADDLE_ROLL_CATEGORY
):
```

### Cut 3 — Heartbeat dispatch (after line 2778)
New `elif` block added AFTER the existing `if straddle_roll_enabled` block. They are mutually
exclusive — a session has exactly one `_preset_source`. STRADDLE_ROLL skips the adjustment
engine entirely (Step 5.1–5.3 already ran; this elif at Step 5.4 fires instead of STRADDLE_WITH_ADJUSTMENT).
```python
# ADD after the existing if block that ends at line 2778:
elif (params.get('_preset_source') == STRADDLE_ROLL_CATEGORY
        and not self._paused):
    try:
        from .mmm_straddle_roll_pure import execute_pure_straddle_roll
        _pure_roll_fired = await execute_pure_straddle_roll(
            self, session, sid, minutes_to_expiry
        )
        if _pure_roll_fired:
            _skip_to_pnl = True
    except Exception as _pure_roll_err:
        log.error(f"[{sid}] Pure Straddle Roll error: {_pure_roll_err}", exc_info=True)
```

### Cut 4 — is_straddle helper (line 6332)
Controls whether auto_close_mins logic uses ATM-style replenishment on expiry close.
STRADDLE_ROLL needs the same behavior.
```python
# BEFORE:
is_straddle = (
    dte_cat in ('STRADDLE_WITH_ADJUSTMENT', 'SHORT_STRADDLE')
    ...

# AFTER:
is_straddle = (
    dte_cat in ('STRADDLE_WITH_ADJUSTMENT', 'SHORT_STRADDLE', 'STRADDLE_ROLL')
    ...
```

---

## mmm_straddle_roll_pure.py — Internal Structure

```
Public API (called from monitor):
  execute_pure_straddle_roll(monitor, session, sid, minutes_to_expiry) → bool

Internal helpers (all private, not imported by anything else):
  _check_hard_stop(session, params) → bool
  _check_expiry(session, minutes_to_expiry) → str  ('stop' | 'hold' | 'proceed')
  _get_trigger_pts(session, params, spot) → float  (same fallback chain as adj)
  _check_roll_gates(session, params, spot, trigger_pts) → (bool, str)
  _execute_4_leg_roll(monitor, session, sid, spot) → bool
  _close_all_market_order(monitor, session, sid) → bool
  _post_roll_state_reset(session, spot, new_ce_fill, new_pe_fill) → None
  _send_roll_telegram(session, sid, roll_n, old_atm, new_atm, spot_move, trigger_pts,
                      new_trigger_pts) → None
  _send_exhaustion_telegram(session, sid, roll_n) → None
  _send_hard_stop_telegram(session, sid, total_loss) → None
```

### Gate Check Order (inside _check_roll_gates)

| # | Gate | Condition to BLOCK | Note |
|---|------|--------------------|------|
| 0 | In-progress lock | `_straddle_roll_in_progress == True` | Prevent concurrent rolls |
| 1 | Master switch | `straddle_roll_enabled != True` | Preset always sets True |
| 2 | Leg presence | CE or PE has no active positions | Must have both legs |
| 3 | Time to expiry | `minutes_to_expiry < straddle_roll_min_time_to_expiry` (90) | Already checked in Step 2 — double-check here |
| 4 | Margin | Margin tier is TIER_RED or TIER_CRITICAL | Exchange may reject anyway |
| 5 | IV spike | `current_iv > entry_iv × iv_spike_mult` | **Soft only** — logs WARNING, does NOT block |
| 6 | Max rolls | `roll_count >= straddle_roll_max_per_session` | 0 = no rolls ever |
| 7 | Cooldown | `now < last_roll_time + cooldown_mins×60` | Emergency bypass at 2× trigger_pts |
| 8 | Spread | CE or PE bid-ask spread > `straddle_roll_max_spread_pct` | Fetched from live orderbook |
| 9 | Same-strike | `new_atm_strike == current_atm_strike` | BTC hasn't crossed a strike grid boundary |
| 10 | Min credit | `new_straddle_credit < original_credit × straddle_roll_min_credit_pct` | Won't roll into a dead market |
| 11 | Loss abort | `total_session_loss > original_credit × straddle_roll_loss_abort_mult` | Belt-and-suspenders (hard stop is earlier) |

### 4-Leg Roll Execution (inside _execute_4_leg_roll)

Uses LIMIT orders. STOP session on any failure after Step 1.

```
Step 0: Set _straddle_roll_in_progress = True
Step 1: Fetch live spot
Step 2: Preview new ATM strike (< 5s freshness check)
Step 3: Close ITM leg first
        - CE if spot >= current_atm, PE if spot < current_atm
        - On failure: clear lock, return False (no positions changed)
Step 4: Close OTM leg
        - On failure: CRITICAL — session STOPPED, Telegram CRITICAL (naked position risk)
[Optional refresh: if BTC moved > 25% of trigger_pts during steps 3-4, re-fetch ATM]
Step 5: Sell new CE at new ATM (initial_lots)
        - On failure: CRITICAL — session STOPPED, Telegram CRITICAL
Step 6: Sell new PE at new ATM (same lots as CE fill)
        - On failure: CRITICAL — NAKED CE — session STOPPED, Telegram CRITICAL
Step 7: Update state
        - Increment _straddle_roll_count
        - Set _straddle_roll_trigger_pts = ce_fill + pe_fill
        - Set _straddle_last_roll_time = now
        - Update _straddle_cumulative_credit
Step 8: Post-roll state reset (see below)
Step 9: Clear _straddle_roll_in_progress
Step 10: Telegram INFO + activity log
Step 11: If roll_count == max_rolls: Telegram WARNING (exhaustion)
```

### Post-Roll State Reset (inside _post_roll_state_reset)

**Reset (stale for new straddle):**
- `_trend_regime`, `_trend_tier`, `_trend_direction`, `_trend_anchor`, `_trend_consecutive`
- `_straddle_entry_iv` (recaptured on next heartbeat)
- `_adaptive_tier`, `_adaptive_interval`, `_adaptive_current_interval`
- `_whipsaw_score`, `_reversal_cooldown_until`

**Do NOT reset:**
- `_straddle_initial_credit` — full-session loss abort baseline (Gate 11)
- `_straddle_roll_count` — cumulative counter (Gate 6)
- `_straddle_cumulative_credit` — analytics
- `max_loss_amount` — session-level hard stop
- `realized_pnl`, `unrealized_pnl`, all P&L accounting fields

### Hard Stop Close (inside _close_all_market_order)

```
1. Collect all active positions across CE and PE
2. For each position:
   executor.place_market_order_immediate(symbol, 'buy', lots)
   (buy = close a short position)
3. On any failure: log CRITICAL, continue closing remaining — never abort mid-close
4. Mark session STOPPED regardless of partial fill success
5. Telegram CRITICAL: "Hard stop fired. Loss: $X. {N} positions closed."
```

---

## mmm_executor.py — New Method

```python
async def place_market_order_immediate(
    self,
    symbol: str,
    side: str,       # 'buy' or 'sell'
    size: int,
    reduce_only: bool = True,
    rest_client=None,
) -> dict:
    """
    Place a market order that fills immediately at any price.
    Used only for hard stop closes. Never use for normal roll execution.
    No retries — if it fails, caller logs CRITICAL and continues.
    """
    rest = rest_client or self._create_rest_client()
    response = await rest.place_order_by_symbol(
        symbol=symbol,
        side=side,
        size=int(size),
        order_type="market_order",
        reduce_only=reduce_only,
    )
    return response.get('result', response)
```

This method is independent of `place_limit_order_post_only()` and `place_ioc_order_aggressive()`.
It does not change them. It has no `price` parameter — market orders don't need one.

---

## mmm_close_at_5.py — Signature Change

```python
# BEFORE:
async def close_position(
    executor,
    initializer,
    session: Dict,
    position: Dict,
    pnl_attribution_key: str = None,
    hedge_guard: bool = True,
    mechanism: str = 'close_at_5',
    side: str = None,
) -> Dict[str, Any]:

# AFTER (add one parameter with default):
async def close_position(
    executor,
    initializer,
    session: Dict,
    position: Dict,
    pnl_attribution_key: str = None,
    hedge_guard: bool = True,
    mechanism: str = 'close_at_5',
    side: str = None,
    order_type: str = 'limit',        # ← NEW. Default 'limit' = existing behavior preserved
) -> Dict[str, Any]:
```

The `order_type` parameter is passed down to the executor call inside `close_position()`.
All 15+ existing call sites pass no `order_type` argument → get `'limit'` → unchanged behavior.
Only `_close_all_market_order()` in `mmm_straddle_roll_pure.py` passes `order_type='market'`.

---

## mmm_dte_presets.py — New Additions

```python
# New constant (alongside existing STRADDLE_WITH_ADJUSTMENT_CATEGORY):
STRADDLE_ROLL_CATEGORY = 'STRADDLE_ROLL'

def build_straddle_roll_preset(hours_to_expiry: float) -> dict:
    """
    Pure straddle roll preset. Sells ATM straddle, monitors price, rolls when
    spot moves by collected premium. No adjustments between rolls.

    Differs from STRADDLE_WITH_ADJUSTMENT:
    - min_trigger_move: 9999 — MMM adjustment engine will never fire
    - max_lots_per_side: initial_lots — CE:PE always 1:1
    - straddle_roll_hard_stop_market_order: True — hard stop fills immediately
    - No wind-down, harvest, ATM shield, perp hedge, scale, reverse
    """
    H = float(hours_to_expiry)
    if H < 1.0:
        raise ValueError(f"STRADDLE_ROLL requires ≥ 1h (got {H:.1f}h). Gamma risk too high.")
    if H > 24:
        log.warning(f"[STRADDLE_ROLL] Long session: {H:.1f}h. All scaled params at max above 12h.")

    return {
        '_preset_source':                   STRADDLE_ROLL_CATEGORY,
        'dte_category':                     STRADDLE_ROLL_CATEGORY,
        'adaptive_preset':                  'straddle',

        # ── Lot control ─────────────────────────────────────────────────────
        # initial_lots: REQUIRED — operator must provide. Not defaulted.
        # max_lots_per_side set to initial_lots after session creation (in mmm_api.py)
        'max_total_exposure':               20,

        # ── Heartbeat ────────────────────────────────────────────────────────
        'adjustment_interval':              120,

        # ── MMM adjustment engine — effectively disabled ──────────────────────
        # 9999 pts trigger: no BTC move will ever reach this threshold.
        # The adjustment engine code is untouched; it simply never fires.
        'min_trigger_move':                 9999,

        # ── Roll mechanism ───────────────────────────────────────────────────
        'straddle_roll_enabled':            True,
        # straddle_roll_max_per_session: REQUIRED — operator must provide.
        'straddle_roll_cooldown_mins':      15,
        'straddle_roll_emergency_mult':     2.0,
        'straddle_roll_min_time_to_expiry': 90,
        'straddle_roll_min_credit_pct':     0.30,
        'straddle_roll_max_spread_pct':     15.0,
        'straddle_roll_iv_spike_mult':      2.0,   # soft warning only — does NOT block
        'straddle_roll_loss_abort_mult':    3.0,
        'straddle_roll_hard_stop_market_order': True,   # hard stop uses market orders

        # max_loss_amount: REQUIRED — operator must provide.

        # ── Price guard ──────────────────────────────────────────────────────
        'price_guard_enabled':              True,
        'price_guard_interval_secs':        5,
        'price_guard_buffer_pts':           50,
        'price_guard_cooldown_secs':        30,

        # ── Disabled features ────────────────────────────────────────────────
        'wind_down_enabled':                False,
        'harvest_enabled':                  False,
        'atm_shield_enabled':               False,
        'perp_hedge_enabled':               False,
        'scale_enabled':                    False,
        'reverse_enabled':                  False,
        'recycler_enabled':                 False,
    }
```

---

## mmm_state.py — 2 New Lines

In `DEFAULT_PARAMS` dict (after existing `price_guard_cooldown_secs` entry, around line 661):
```python
'straddle_roll_hard_stop_market_order': False,  # True only for STRADDLE_ROLL preset
```

In `HOT_RELOAD_ALLOWED` set (after `straddle_roll_max_spread_pct` entry, around line 815):
```python
'straddle_roll_hard_stop_market_order',
```

---

## mmm_api.py — New Validation Block

After the existing STRADDLE_WITH_ADJUSTMENT block (after line 370), add:
```python
# ── STRADDLE_ROLL validation: require operator-explicit params ──────────────
if session.get('params', {}).get('_preset_source') == 'STRADDLE_ROLL':
    _missing = []
    raw_params = data.get('params') or {}
    if 'initial_lots' not in raw_params:
        _missing.append('initial_lots')
    if 'straddle_roll_max_per_session' not in raw_params:
        _missing.append('straddle_roll_max_per_session')
    if 'max_loss_amount' not in raw_params:
        _missing.append('max_loss_amount')
    if _missing:
        return jsonify({
            'success': False,
            'error': (
                f"STRADDLE_ROLL requires explicit: {', '.join(_missing)}. "
                f"Set straddle_roll_max_per_session=0 for no-roll mode. "
                f"These are not preset-defaulted for safety."
            ),
        }), 400
    # Lock max_lots_per_side = initial_lots (CE:PE must always stay 1:1)
    session['params']['max_lots_per_side'] = raw_params['initial_lots']
```

---

## Telegram Messages

### Roll Fired (INFO)
```
🔄 Straddle Roll #{N} — {sid}
{old_atm} → {new_atm} ({direction})
Spot: {spot} | Moved: {spot_move:.0f} pts (trigger was {trigger_pts:.0f} pts)
New premium collected: {new_ce_fill:.0f} + {new_pe_fill:.0f} = {new_trigger_pts:.0f} pts
Next trigger: ±{new_trigger_pts:.0f} pts from {new_atm}
Session P&L so far: ${total_pnl:.2f}
```

### Max Rolls Exhausted (WARNING — fires once)
```
⚠️ STRADDLE_ROLL — MAX ROLLS EXHAUSTED
Session: {sid}
Rolls used: {N}/{N}
Current ATM: {atm_strike}
Hard stop: ${max_loss_amount:.2f}
No more rolls this session. Only exits: hard stop or expiry close.
```

### Hard Stop (CRITICAL)
```
🚨 STRADDLE_ROLL — HARD STOP FIRED
Session: {sid}
Loss: ${total_loss:.2f} ≥ limit: ${max_loss_amount:.2f}
Closing {N} positions with MARKET ORDERS.
Rolls completed: {roll_count}/{max_rolls}
```

### Half-Roll Recovery Required (CRITICAL — fires on startup if breadcrumb found)
```
🚨 HALF-ROLL DETECTED ON STARTUP
Session: {sid} | State: {breadcrumb}
Session BLOCKED — manual recovery required.
Check open positions on exchange before doing anything.
```

---

## Sealed Tests (18 tests in test_sealed_straddle_roll_pure.py)

| # | Test name | What it proves |
|---|-----------|---------------|
| 1 | `test_roll_fires_at_trigger_pts` | Gate 8 passes when `spot_move == trigger_pts` |
| 2 | `test_roll_blocked_below_trigger` | Gate 8 blocks when `spot_move < trigger_pts` |
| 3 | `test_trigger_pts_updates_after_roll` | `_straddle_roll_trigger_pts = new_ce_fill + new_pe_fill` after roll |
| 4 | `test_trigger_pts_fallback_chain` | Falls back: session key → live avg → pct% → block |
| 5 | `test_hard_stop_uses_market_order` | `place_market_order_immediate()` called, NOT limit order |
| 6 | `test_normal_roll_uses_limit_order` | Roll close uses limit order, not market |
| 7 | `test_same_strike_guard_blocks_roll` | Roll blocked when new_atm == current_atm |
| 8 | `test_spread_gate_blocks_wide_market` | Roll blocked when spread > `straddle_roll_max_spread_pct` |
| 9 | `test_cooldown_gate_blocks_within_15min` | Roll blocked within cooldown window |
| 10 | `test_max_rolls_gate_blocks_when_exhausted` | Roll blocked when `roll_count >= max_rolls` |
| 11 | `test_max_rolls_telegram_fires_exactly_once` | Exhaustion Telegram fires on roll N, not before/after |
| 12 | `test_iv_spike_does_not_block_roll` | IV spike logs WARNING, `_straddle_last_roll_iv_spike=True`, roll proceeds |
| 13 | `test_post_roll_regime_state_reset` | All `_trend_*`, `_straddle_entry_iv`, `_adaptive_*` keys cleared |
| 14 | `test_straddle_roll_never_calls_adjustment_module` | `_preset_source=STRADDLE_ROLL` never imports `mmm_straddle_adjustment` |
| 15 | `test_straddle_adj_never_calls_pure_roll_module` | `_preset_source=STRADDLE_WITH_ADJUSTMENT` never imports `mmm_straddle_roll_pure` |
| 16 | `test_api_rejects_missing_max_loss` | HTTP 400 when `max_loss_amount` absent |
| 17 | `test_api_rejects_missing_max_rolls` | HTTP 400 when `straddle_roll_max_per_session` absent |
| 18 | `test_min_trigger_move_9999_prevents_adj_engine` | MMM adj engine check returns False when `min_trigger_move=9999` |

---

## Implementation Order

```
Phase 1 — Infrastructure (no session can run yet — safe to deploy incrementally)
  Step 1: mmm_executor.py       — add place_market_order_immediate()
  Step 2: mmm_close_at_5.py    — add order_type='limit' default param
  Step 3: mmm_state.py         — add straddle_roll_hard_stop_market_order to DEFAULT_PARAMS
  Step 4: mmm_dte_presets.py   — add STRADDLE_ROLL_CATEGORY + build_straddle_roll_preset()

Phase 2 — Core Logic
  Step 5: mmm_straddle_roll_pure.py  — full file
  Step 6: mmm_api.py                 — session creation validation block

Phase 3 — Monitor Integration
  Step 7: mmm_monitor.py             — 4 surgical cuts

Phase 4 — Tests
  Step 8: test_sealed_straddle_roll_pure.py  — all 18 tests
  Step 9: Run full test suite — must pass: existing 1312 + new 18 = 1330

Phase 5 — UI
  Step 10: MMMDashboard.js
    - Badge: "Straddle Roll" chip (distinct color from "Straddle+Adj")
    - Trigger display: shows "±{trigger_pts} pts" not trigger %
    - Price guard indicator: "⚡ PG" label when price_guard_enabled=True

Phase 6 — Paper Test (before any real capital)
  Step 11: Create 1-lot STRADDLE_ROLL session
           initial_lots=1, straddle_roll_max_per_session=2, max_loss_amount=50
           Observe: no adj engine activity, roll fires at correct pts, Telegram correct
  Step 12: Verify hard stop fires market order (simulate with mock spot price)
  Step 13: Verify max rolls exhaustion Telegram fires on roll 2
```

---

## What the MMM Adjustment Engine Does for STRADDLE_ROLL Sessions

With `min_trigger_move = 9999`:
- The adjustment engine code runs as normal during heartbeat steps 5.1–5.3
- It evaluates the trigger condition: `spot_move >= min_trigger_move`
- `spot_move` is always < 9999 → condition is always False → engine returns immediately
- Zero lots added, zero orders placed, zero state changes
- No code changes to the engine are required

This is the isolation mechanism — not a flag or a gate, but a threshold that is numerically unreachable.

---

## Backward Compatibility Proof

Every existing strangle session (0DTE, 5DTE, SHORT_WINDOW) and every STRADDLE_WITH_ADJUSTMENT
session has `_preset_source` that is NOT `'STRADDLE_ROLL'`.

- Cut 2 (price guard): adds `STRADDLE_ROLL_CATEGORY` to an existing tuple — existing sessions already match on their own values
- Cut 3 (heartbeat elif): the new `elif` only fires when `_preset_source == STRADDLE_ROLL_CATEGORY`. For all other presets, this `elif` is False — the `if` block before it controlled those presets already
- Cut 4 (is_straddle): adds a new string to a tuple that is checked for ATM replenishment behavior. Existing sessions never have `dte_category == 'STRADDLE_ROLL'`
- `close_position()` default `order_type='limit'`: all 15+ existing callers pass no argument → get default → unchanged behavior

Tests 14 and 15 in the sealed test suite formally verify the bidirectional isolation.
