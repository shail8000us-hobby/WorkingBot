# MMM Split Ledger Plan — Frozen Lot Capacity Relief

**Created:** March 2026  
**Updated:** March 4, 2026 (code-verified revision)  
**Status:** Implementation Plan — READY TO CODE  
**Scope:** `mmm_engine.py`, `mmm_state.py`, `mmm_safety.py`, `mmm_recycler.py`, `mmm_monitor.py`, `mmm_harvester.py`

---

## Code Audit Summary (Pre-Implementation)

Before writing this plan, every source file was read and cross-referenced. The following
files were audited with exact line numbers verified as of March 4, 2026:

| File | Lines | Key Section Verified |
|------|-------|---------------------|
| `mmm_state.py` | 807 | `recompute_side_lots()` lines 193-283, `DEFAULT_PARAMS` lines 293-403, `HOT_RELOAD_PARAMS` lines 407-446 |
| `mmm_engine.py` | 741 | `calculate_lots_to_sell()` lines 282-352, `calculate_standard_loss()` lines 72-180, `calculate_reversal_loss()` lines 185-275 |
| `mmm_monitor.py` | 5380 | `_process_strike_shift()` lines 2721-2990, `_process_lot_recycling()` lines 3247-3377, consistency check lines 710-735 |
| `mmm_recycler.py` | 512 | `check_recycle_viability()` lines 97-193, `execute_lot_recycling()` lines 200-512 |
| `mmm_harvester.py` | 246 | `get_effective_harvest_params()` lines 28-85, `scan_harvestable_positions()` lines 92-246 |
| `mmm_strike_shift.py` | 331 | `freeze_current_positions()` lines 97-142, `find_new_strike()` lines 145-260, `activate_new_strike()` lines 263-331 |
| `mmm_close_at_5.py` | 432 | `close_position()` lines 185-280 |
| `mmm_safety.py` | 687 | `check_position_cap()` lines 80-122, `check_asymmetry()` lines 333-370, `check_margin()` lines 500-530 |
| `mmm_perp_hedge.py` | 815 | `_calculate_portfolio_delta()` rebalance band widener lines 95-120 |

---

## Table of Contents

1. [The Problem](#1-the-problem)
2. [Root Cause (Exact Code)](#2-root-cause-exact-code)
3. [The Optimal Approach: Split Ledger + Shift-Time Recycle](#3-the-optimal-approach-split-ledger--shift-time-recycle)
4. [Implementation Details — Phase 1: Split Ledger](#4-implementation-details--phase-1-split-ledger)
5. [Implementation Details — Phase 2: Shift-Time Recycle](#5-implementation-details--phase-2-shift-time-recycle)
6. [Complete `total_lots` Usage Audit](#6-complete-total_lots-usage-audit)
7. [New Parameters](#7-new-parameters)
8. [Risk Analysis](#8-risk-analysis)
9. [Worked Examples](#9-worked-examples)
10. [Integration with M1/M2/M3](#10-integration-with-m1m2m3)
11. [Implementation Phases & Checklist](#11-implementation-phases--checklist)
12. [Profitability Suggestions](#12-profitability-suggestions)

---

## 1. The Problem

When a strike shift occurs, **frozen positions** at the old strike continue to count 1:1 against `max_lots_per_side`. This creates a compounding capacity drain:

```
Scenario: max_lots_per_side = 100

  Shift 1: Freeze 30 lots → remaining capacity = 70
  Shift 2: Freeze 25 lots → remaining capacity = 45
  Shift 3: Freeze 20 lots → remaining capacity = 25  ← crippled

After 3 shifts, only 25% of capacity is available for PRODUCTIVE hedging.
The frozen 75 lots are slowly decaying to zero but eating capacity for hours.
```

The bot becomes increasingly paralyzed as shifts accumulate. M1 (Harvesting) and M2 (Recycling) help clean up frozen positions, but they're **reactive** — they fire AFTER the damage is done. By the time M2 triggers, the position cap has already blocked an adjustment.

---

## 2. Root Cause (Exact Code)

### 2.1 The lot derivation formula (`mmm_state.py` lines 278-283):

```python
side_state['frozen_total_lots'] = sum(f.get('lots', 0) for f in frozen)

side_state['active_lots'] = (
    side_state['original_lots'] + side_state['adjustment_total_lots']
)
side_state['total_lots'] = side_state['active_lots'] + side_state['frozen_total_lots']
```

**No change needed here.** These derivations are correct. `active_lots`, `frozen_total_lots`, and `total_lots` are all derived from `positions[]` by `recompute_side_lots()`. The problem is in who *consumes* `total_lots` for the cap.

### 2.2 The cap check (`mmm_engine.py` lines 334-348):

```python
# §13.1: Position cap
hedge_state = session.get(hedge_side, {})
current_total = hedge_state.get('total_lots', 0)  # ← BUG: includes frozen!

if current_total + lots_to_sell > max_lots_per_side:
    lots_to_sell = max_lots_per_side - current_total
    if lots_to_sell <= 0:
        return 0, (
            f"Position cap reached: {hedge_side.upper()} has "
            f"{current_total}/{max_lots_per_side} lots"
        )
    cap_msg = (
        f"Capped from {math.ceil(raw_lots)} to {lots_to_sell} "
        f"(position cap: {max_lots_per_side})"
    )
    constraint_msg = f"{constraint_msg}; {cap_msg}" if constraint_msg else cap_msg
```

This is the **primary fix target**. Changing `'total_lots'` to `'active_lots'` here frees frozen lots from blocking new adjustments.

### 2.3 The safety warning (`mmm_safety.py` lines 80-122):

```python
def check_position_cap(self, session: Dict) -> List[Dict]:
    for side_key in ['ce', 'pe']:
        side_state = session.get(side_key, {})
        total = side_state.get('total_lots', 0)  # ← ALSO USES total_lots
        ratio = total / max_lots if max_lots > 0 else 0

        if total >= max_lots:
            events.append({
                'type': 'position_cap',
                'action': 'stop_adjustments',   # ← This BLOCKS adjustments!
                ...
            })
```

**CRITICAL CONFLICT:** The safety module's `check_position_cap()` also uses `total_lots`. Even if we fix `mmm_engine.py`, this safety check fires `action: 'stop_adjustments'` which the monitor respects (line 1197-1230). The monitor would skip adjustment logic entirely based on the safety event, *before* `calculate_lots_to_sell` is even called.

**This MUST be changed to `active_lots`** for Split Ledger to work. Otherwise the safety system blocks adjustments even though the engine would allow them.

### 2.4 The recycler cap checks (`mmm_recycler.py` lines 329, 432):

```python
# Line 329: Greedy selection
current_total = hedge_state.get('total_lots', 0)
max_recyclable_lots = math.floor(current_total * max_recycle_pct)

# Line 432 (Phase B): Final cap check after Phase A
remaining_after_a = hedge_state_refreshed.get('total_lots', 0)
if remaining_after_a + phase_b_lots > max_lots:
```

**And the viability check (line 170):**

```python
remaining_lots = current_total_lots - recycled_lots
if new_lots_needed + remaining_lots > max_lots_per_side:
```

These need careful analysis — see §6 below.

---

## 3. The Optimal Approach: Split Ledger + Shift-Time Recycle

The solution combines two complementary mechanisms:

### Part 1: Split Ledger (Core Fix)

**Only `active_lots` count against `max_lots_per_side` in the position cap.**

Frozen positions still exist in state, still accrue P&L, still get closed by close-at-5. They just don't block new adjustments.

A new safety parameter `max_total_exposure` provides an absolute ceiling on combined active + frozen lots to prevent runaway accumulation.

```
active_lots    → used for position cap (adjustments, lot calculation)
total_lots     → used for max_total_exposure safety check, loss calculations, margin proxy
frozen_lots    → tracked for P&L, close-at-5, M1 harvesting
```

### Part 2: Shift-Time Recycle (Proactive Cleanup)

At the moment of a strike shift, **optionally** close some or all frozen positions immediately and fold the buyback cost into the new sell lot calculation.

This is essentially **M2 (Recycling) triggered proactively at shift time** rather than reactively when blocked.

```
Current flow:
  1. Find new strike
  2. Freeze current positions
  3. Calculate lots for loss at new strike ← uses total_lots, gets capped
  4. Sell at new strike

New flow:
  1. Find new strike
  2. Freeze current positions
  3. [NEW] Close cheap frozen positions (buyback)
  4. Calculate lots = (loss_to_hedge + buyback_cost) / (new_premium × LOT_SIZE)
  5. Sell at new strike  ← more lots to cover buyback, but way more capacity
```

### Why Both?

| Mechanism | What it solves | Without it |
|-----------|---------------|------------|
| Split Ledger | Frozen lots don't block adjustments | Shifts still consume capacity |
| Shift-Time Recycle | Frozen lots cleaned up immediately | Frozen lots linger for hours until M1/close-at-5 |

Split Ledger alone solves the **blocking** problem. Shift-Time Recycle solves the **lingering exposure** problem. Together they ensure:

1. New adjustments are never blocked by frozen lots
2. Frozen positions are cleaned up as fast as financially sensible
3. Maximum capital efficiency at all times

---

## 4. Implementation Details — Phase 1: Split Ledger

### 4.1 Cap Check Fix (`mmm_engine.py`)

**File:** `mmm_engine.py` → `calculate_lots_to_sell()` line 336

```python
# BEFORE:
current_total = hedge_state.get('total_lots', 0)

# AFTER:
current_total = hedge_state.get('active_lots', 0)
```

Then **APPEND** a second safety check immediately after the existing cap block (after line 348), before the `return lots_to_sell, constraint_msg`:

```python
        # ── Split Ledger: max_total_exposure safety ceiling ────────────
        # active_lots cap is the primary gate. This is the ABSOLUTE ceiling
        # on combined active + frozen lots to guard against infinite accumulation.
        max_total_exposure = params.get('max_total_exposure', 0)
        if max_total_exposure <= 0:
            max_total_exposure = max_lots_per_side * 2  # auto-compute default
        total_exposure = hedge_state.get('total_lots', 0)
        if total_exposure + lots_to_sell > max_total_exposure:
            lots_to_sell = max(max_total_exposure - total_exposure, 0)
            if lots_to_sell <= 0:
                return 0, (
                    f"Total exposure ceiling: {hedge_side.upper()} has "
                    f"{total_exposure}/{max_total_exposure} lots (active+frozen)"
                )
            exp_msg = (
                f"Capped by total exposure: {lots_to_sell} lots "
                f"(ceiling: {max_total_exposure})"
            )
            constraint_msg = f"{constraint_msg}; {exp_msg}" if constraint_msg else exp_msg
        # ── END Split Ledger ───────────────────────────────────────────
```

**IMPORTANT: Error message must NOT contain "Position cap reached"** — that exact string is used by `_process_adjustment()` at monitor line 2615 to trigger M2 recycling. The new message uses "Total exposure ceiling" to avoid false M2 triggers.

### 4.2 Safety Check Fix (`mmm_safety.py`)

**File:** `mmm_safety.py` → `check_position_cap()` line 88

```python
# BEFORE:
total = side_state.get('total_lots', 0)

# AFTER:
total = side_state.get('active_lots', 0)
```

The safety check's warning thresholds (80% and 100%) now apply to `active_lots` only.

**ADD** a separate total exposure check after the existing `check_position_cap` method:

```python
def check_total_exposure(self, session: Dict) -> List[Dict]:
    """Split Ledger: Check if active + frozen lots exceed max_total_exposure ceiling."""
    events = []
    params = session.get('params', {})
    max_lots = params.get('max_lots_per_side', 100)
    max_total = params.get('max_total_exposure', 0)
    if max_total <= 0:
        max_total = max_lots * 2

    for side_key in ['ce', 'pe']:
        side_state = session.get(side_key, {})
        total = side_state.get('total_lots', 0)
        frozen = side_state.get('frozen_total_lots', 0)
        active = side_state.get('active_lots', 0)
        ratio = total / max_total if max_total > 0 else 0

        if total >= max_total:
            events.append({
                'type': 'total_exposure',
                'level': 'alert',
                'message': (
                    f"{side_key.upper()} TOTAL EXPOSURE CEILING: "
                    f"{total}/{max_total} lots "
                    f"(active: {active}, frozen: {frozen})"
                ),
                'action': 'warn',  # warn only — engine handles the hard block
                'details': {'side': side_key, 'total': total,
                            'active': active, 'frozen': frozen, 'max': max_total},
            })
        elif ratio >= 0.8:
            events.append({
                'type': 'total_exposure',
                'level': 'info',
                'message': (
                    f"{side_key.upper()} approaching total exposure ceiling: "
                    f"{total}/{max_total} lots ({ratio:.0%})"
                ),
                'action': 'continue',
                'details': {'side': side_key, 'total': total,
                            'active': active, 'frozen': frozen, 'max': max_total},
            })
    return events
```

**Call it from `run_all_checks()`** in the same file (line 59 area):

```python
events.extend(self.check_position_cap(session))
events.extend(self.check_total_exposure(session))  # NEW
```

**Why `action: 'warn'` not `'stop_adjustments'`?** Because the engine's `calculate_lots_to_sell()` already handles the hard block. The safety event is for UI alerting only. If we used `stop_adjustments`, the monitor would skip the adjustment entirely and the M2 recycling path (triggered by "Position cap reached" from the engine) would also be skipped.

### 4.3 Recycler Consistency Fix (`mmm_recycler.py`)

The recycler uses `total_lots` in three places. Two need updates for Split Ledger consistency:

**Fix 1: Greedy selection (line 329)**

```python
# BEFORE:
current_total = hedge_state.get('total_lots', 0)

# AFTER:
current_total = hedge_state.get('total_lots', 0)  # ← KEEP as total_lots
# max_recycle_pct should apply to total lots (we're recycling from frozen pool)
```

**No change needed.** `max_recycle_pct` limits what fraction of the TOTAL position we recycle. Using `total_lots` is correct here because the recyclable pool IS the frozen positions within total.

**Fix 2: Viability check affordability (lines 166-174)**

```python
# BEFORE:
remaining_lots = current_total_lots - recycled_lots
if new_lots_needed + remaining_lots > max_lots_per_side:

# AFTER:
# Under Split Ledger, the cap is on active_lots. Recycling reduces frozen_lots 
# (not active_lots), and Phase B adds to active_lots. So the affordability check 
# should verify active_lots + new_lots_needed ≤ max_lots_per_side.
# The caller must pass current_active_lots instead of current_total_lots.
```

**Update `check_recycle_viability()` signature:**

```python
def check_recycle_viability(
    recyclable_with_prices: List[Dict],
    loss_to_hedge: float,
    new_premium: float,
    current_active_lots: int,   # CHANGED: was current_total_lots
    max_lots_per_side: int,
    params: Dict,
) -> Tuple[bool, str, Dict]:
```

And the affordability check:

```python
# Check 3: Affordability — Phase B lots must fit within active_lots cap
# Recycled lots come off frozen_total_lots (not active_lots), so active_lots 
# is unchanged by Phase A. Phase B adds new_lots_needed to active_lots.
if current_active_lots + new_lots_needed > max_lots_per_side:
    return (
        False,
        f'Affordability: {new_lots_needed} new + {current_active_lots} active '
        f'= {new_lots_needed + current_active_lots} > cap {max_lots_per_side}',
        {'new_lots_needed': new_lots_needed, 'current_active': current_active_lots,
         'cap': max_lots_per_side},
    )
```

**Fix 3: Phase B cap check (lines 430-440)**

```python
# BEFORE:
remaining_after_a = hedge_state_refreshed.get('total_lots', 0)
if remaining_after_a + phase_b_lots > max_lots:

# AFTER:
remaining_active = hedge_state_refreshed.get('active_lots', 0)
if remaining_active + phase_b_lots > max_lots:
```

Phase A only closes frozen positions, so `active_lots` stays the same. Phase B adds to `active_lots`.

**Fix 4: Caller site in `execute_lot_recycling()` (line ~367)**

Update the call to `check_recycle_viability`:

```python
# BEFORE:
viable, reason, viability_details = check_recycle_viability(
    recyclable_with_prices=selected,
    loss_to_hedge=loss_to_hedge,
    new_premium=new_premium,
    current_total_lots=current_total,  # current_total = total_lots
    max_lots_per_side=max_lots,
    params=params,
)

# AFTER:
current_active = hedge_state.get('active_lots', 0)
viable, reason, viability_details = check_recycle_viability(
    recyclable_with_prices=selected,
    loss_to_hedge=loss_to_hedge,
    new_premium=new_premium,
    current_active_lots=current_active,
    max_lots_per_side=max_lots,
    params=params,
)
```

### 4.4 State & Params (`mmm_state.py`)

**Add to `DEFAULT_PARAMS` (after `max_lots_per_side` at line ~306):**

```python
'max_total_exposure': 0,            # Split Ledger: absolute ceiling on active+frozen lots per side.
                                     # 0 = auto (2× max_lots_per_side). Set >0 to override.
```

**Add to `HOT_RELOAD_PARAMS` set (after `max_lots_per_side`):**

```python
'max_total_exposure',
```

### 4.5 Consistency Check Update (`mmm_monitor.py` lines 710-735)

The consistency check at heartbeat start uses `total_lots`. **No change needed** — this correctly verifies derived state consistency. `recompute_side_lots()` rebuilds both `active_lots` and `total_lots` from `positions[]`, so both are always consistent.

### 4.6 Unit Test Updates

Existing tests in `tests/test_mmm_recycler.py` use `total_lots` in session fixtures. These must be updated to also include `active_lots` in the fixture data. The `check_recycle_viability()` test calls pass `current_total_lots=` which must change to `current_active_lots=`.

---

## 5. Implementation Details — Phase 2: Shift-Time Recycle

### 5.1 Hook into `_process_strike_shift()` (`mmm_monitor.py`)

Insert between line 2789 (after `freeze_result = freeze_current_positions(...)`) and line 2793 (before `lots, _ = self._engine.calculate_lots_to_sell(...)`):

```python
        # New strike found — NOW freeze current positions
        freeze_result = freeze_current_positions(session, side)

        # ── Split Ledger Phase 2: Shift-Time Recycle ─────────────────
        shift_recycle_buyback = 0.0
        if params.get('shift_recycle_enabled', False):
            shift_recycle_buyback = await self._shift_time_recycle(
                side, new_strike_info,
            )
        # ─────────────────────────────────────────────────────────────

        # Sell at new strike
        new_strike = new_strike_info['strike']
        hedge_premium = new_strike_info['premium']

        # Fold buyback cost into loss so extra lots cover it
        total_loss_to_cover = loss + shift_recycle_buyback

        lots, _ = self._engine.calculate_lots_to_sell(
            session, side, total_loss_to_cover, hedge_premium,
        )
```

**CRITICAL CODE NOTE:** The existing `_process_strike_shift` passes `loss` to `calculate_lots_to_sell`. We change this to `total_loss_to_cover = loss + shift_recycle_buyback`. When `shift_recycle_enabled=False` or no positions are closed, `shift_recycle_buyback=0.0` so behavior is identical.

### 5.2 New method `_shift_time_recycle()` (`mmm_monitor.py`)

Add this as a new method of the `MMMMonitor` class:

```python
async def _shift_time_recycle(
    self,
    side: str,
    new_strike_info: Dict,
) -> float:
    """
    Split Ledger Phase 2: At shift time, close cheap frozen positions
    on `side` to free capacity. Returns total buyback cost in USD
    so the caller can fold it into the new sell lot calculation.

    Only closes positions with premium BELOW shift_recycle_premium_floor.
    Respects shift_recycle_max_pct limit on how many frozen lots to close.

    Returns:
        Total buyback cost in USD. 0.0 if nothing closed.
    """
    from .mmm_close_at_5 import close_position

    session = self.session
    sid = self.session_id
    params = session.get('params', {})
    premium_floor = params.get('shift_recycle_premium_floor', 60.0)
    max_pct = params.get('shift_recycle_max_pct', 1.0)

    side_state = session.get(side, {})
    frozen_positions = side_state.get('frozen_positions', [])

    if not frozen_positions:
        return 0.0

    # Respect max_pct: limit total lots we can close
    total_frozen = sum(f.get('lots', 0) for f in frozen_positions)
    max_closeable_lots = int(total_frozen * max_pct)
    if max_closeable_lots <= 0:
        return 0.0

    option_type = 'call' if side == 'ce' else 'put'
    fetch_fn = self._make_fetch_fn()
    total_buyback = 0.0
    closed_lots = 0

    # Sort frozen positions by current premium ascending (cheapest first)
    # to maximize value of closes and respect max_pct efficiently
    priced_frozen = []
    for fpos in frozen_positions:
        strike = fpos.get('strike', 0)
        lots = fpos.get('lots', 0)
        pos_id = fpos.get('_pos_id', '')

        if strike <= 0 or lots <= 0:
            continue

        try:
            live_premium = fetch_fn(strike, option_type)
        except Exception as e:
            log.warning(f"[{sid}] Shift recycle: premium fetch failed for {strike}: {e}")
            continue

        if live_premium is None or live_premium <= 0:
            continue

        if live_premium > premium_floor:
            continue  # Too expensive — leave for M1 / close-at-5

        priced_frozen.append({
            'side': side,
            'strike': strike,
            'lots': lots,
            'entry_premium': fpos.get('entry_premium', 0),
            'current_premium': live_premium,
            'type': 'frozen',
            '_pos_id': pos_id,
        })

    # Sort cheapest first (minimize buyback cost per lot freed)
    priced_frozen.sort(key=lambda p: p.get('current_premium', 0))

    for close_payload in priced_frozen:
        if closed_lots >= max_closeable_lots:
            break

        lots = close_payload['lots']
        live_premium = close_payload['current_premium']

        try:
            result = await close_position(
                self.executor, self.initializer, session, close_payload,
            )
        except Exception as e:
            log.warning(
                f"[{sid}] Shift recycle: close failed for "
                f"{side.upper()} @ {close_payload['strike']}: {e}"
            )
            continue

        if result.get('success'):
            cost = float(_D(live_premium) * _D(lots) * _LOT)
            total_buyback += cost
            actual_closed = result.get('lots_closed', lots)
            closed_lots += actual_closed
            log.info(
                f"[{sid}] Shift recycle: closed {actual_closed} "
                f"{side.upper()} lots @ {close_payload['strike']} "
                f"(premium ${live_premium:.2f}, cost ${cost:.4f})"
            )
        else:
            log.warning(
                f"[{sid}] Shift recycle: close failed for "
                f"{side.upper()} @ {close_payload['strike']}: "
                f"{result.get('error', 'unknown')}"
            )

    if closed_lots > 0:
        log_activity(
            'shift_recycle',
            f'♻️ Shift-Time Recycle: closed {closed_lots} frozen '
            f'{side.upper()} lots, buyback cost: ${total_buyback:.4f}',
            sid, 'success',
            {
                'side': side.upper(),
                'closed_lots': closed_lots,
                'buyback_cost': round(total_buyback, 4),
                'premium_floor': premium_floor,
            },
        )
        # Emit WebSocket event for dashboard
        try:
            emit_recycle(
                sid, side.upper(), closed_lots, 0,  # new_lots=0 (not yet sold)
                0, 0, 0,  # old_strike, new_strike, new_premium (shift handles these)
                closed_lots,  # net_gain (lots freed)
                total_buyback,  # buyback_cost
                0,  # phase_a_pnl — realized PnL already recorded by close_position
            )
        except Exception as _e:
            log.warning(f"[{sid}] Shift recycle: emit_recycle failed: {_e}")

    return total_buyback
```

**Key differences from the original plan's pseudocode:**

1. Uses `self._make_fetch_fn()` (the correct monitor method) instead of `self._fetch_premium()` (which doesn't exist)
2. Uses the existing `close_position(executor, initializer, session, position)` signature from `mmm_close_at_5.py`
3. Imports `_D` and `_LOT` from `mmm_constants` for Decimal arithmetic (Fix #19 consistency)
4. Sorts cheapest-first and respects `max_pct` as a lot limit
5. Uses `log_activity()` and `emit_recycle()` which are already imported in `mmm_monitor.py`
6. Handles the `_being_closed` in-flight guard (inherited from `close_position`)

### 5.3 Import additions for `mmm_monitor.py`

The following are **already imported** in `mmm_monitor.py` and do NOT need new imports:
- `close_position` — imported lazily inside `_shift_time_recycle` (matches pattern used in recycler)
- `log_activity` — already imported at module level
- `emit_recycle` — already imported at line 68
- `_D`, `_LOT` — need to verify; if not imported, add: `from .mmm_constants import _D, _LOT`

Verify `_D` and `_LOT` at import section (~lines 20-75):

```python
# If not present, add:
from .mmm_constants import LOT_SIZE_BTC, _D, _LOT
```

### 5.4 Params for Phase 2 (`mmm_state.py`)

**Add to `DEFAULT_PARAMS` (after `max_total_exposure`):**

```python
# Split Ledger Phase 2: Shift-Time Recycle
'shift_recycle_enabled': False,         # proactive cleanup at shift time. Start disabled.
'shift_recycle_premium_floor': 60.0,    # only close frozen positions with premium < this
'shift_recycle_max_pct': 1.0,           # max fraction of frozen lots to close per shift (0.0-1.0)
```

**Add to `HOT_RELOAD_PARAMS`:**

```python
'shift_recycle_enabled', 'shift_recycle_premium_floor', 'shift_recycle_max_pct',
```

---

## 6. Complete `total_lots` Usage Audit

Every file that reads `total_lots` was audited. Here is the decision for each:

### CHANGE to `active_lots` (Split Ledger core)

| File | Line | Variable / Context | Change |
|------|------|--------------------|--------|
| `mmm_engine.py` | 336 | `calculate_lots_to_sell()` cap check | `total_lots` → `active_lots` |
| `mmm_safety.py` | 88 | `check_position_cap()` warning trigger | `total_lots` → `active_lots` |
| `mmm_recycler.py` | 170 | `check_recycle_viability()` affordability check | `current_total_lots` → `current_active_lots` (param rename + logic change) |
| `mmm_recycler.py` | 432 | `execute_lot_recycling()` Phase B cap check | `total_lots` → `active_lots` |

### KEEP as `total_lots` (correct behavior)

| File | Line(s) | Context | Reason |
|------|---------|---------|--------|
| `mmm_state.py` | 283 | `recompute_side_lots()` derivation | Derivation formula is correct |
| `mmm_state.py` | 189, 773, 780 | Session summary / initialization | Display data — should show real total |
| `mmm_engine.py` | 100-150 | `calculate_standard_loss()` frozen loop | Loss calc MUST include frozen — this is real risk |
| `mmm_engine.py` | 240-260 | `calculate_reversal_loss()` frozen loop | Same — must include frozen for risk accuracy |
| `mmm_safety.py` | 338-339 | `check_asymmetry()` CE/PE ratio | Asymmetry is about total exposure, not just active. Frozen lots on one side still mean imbalanced risk |
| `mmm_safety.py` | 515-517 | `check_margin()` combined lots | Margin proxy should reflect all open exchange positions |
| `mmm_harvester.py` | 50-51 | `get_effective_harvest_params()` M3 asymmetry | M3 should detect total lot imbalance including frozen |
| `mmm_harvester.py` | 126 | `scan_harvestable_positions()` capacity pressure | **See note below** |
| `mmm_recycler.py` | 329 | `execute_lot_recycling()` greedy selection (max_recycle_pct) | Percentage of total freezable pool |
| `mmm_perp_hedge.py` | 109 | Rebalance band widener | Margin/cap awareness should use total exposure |
| `mmm_walkthrough.py` | 371-376 | Display/analytics | Informational only |
| `mmm_storage.py` | 458-556 | SQLite JSON extraction | Historical data — no logic impact |
| `mmm_analytics_storage.py` | 109-110 | Final session lots | Analytics snapshot |
| `mmm_adopter.py` | 570-574 | Initial analytics | Informational |

### M1 Harvester `capacity_pressure` — KEEP as `total_lots` (nuanced decision)

`mmm_harvester.py` line 126: `total_side_lots = side_state.get('total_lots', 0)`

This is used for `capacity_pressure = total_side_lots / max_lots`. The pressure determines whether harvesting even runs.

Under Split Ledger, `active_lots` might be 30 while `total_lots` is 90 (with 60 frozen). If we used `active_lots`, pressure would be 0.30 < threshold 0.70 — harvesting would NOT trigger. But we WANT M1 to run! Those 60 frozen lots are still real exposure that should be cleaned up.

**Decision: KEEP `total_lots`.** M1's pressure-based gating should still detect high total exposure and harvest accordingly. This actually works BETTER with Split Ledger — M1 runs more aggressively to clean up frozen lots even though they no longer block the cap.

### NEW: Add `max_total_exposure` check — Safety module

Add a new `check_total_exposure()` method (see §4.2) that warns when `total_lots` approaches `max_total_exposure`. This replaces the "total lots awareness" that `check_position_cap()` loses by switching to `active_lots`.

---

## 7. New Parameters

### Split Ledger Parameters

| Parameter | Default | Hot-Reload | Type | Description |
|-----------|---------|------------|------|-------------|
| `max_total_exposure` | `0` (= auto: `max_lots_per_side × 2`) | Yes | int | Absolute ceiling on active + frozen lots per side. Safety brake against runaway accumulation. Set >0 to override the auto-computed 2× default. |

### Shift-Time Recycle Parameters

| Parameter | Default | Hot-Reload | Type | Description |
|-----------|---------|------------|------|-------------|
| `shift_recycle_enabled` | `False` | Yes | bool | Enable/disable proactive cleanup during strike shifts. Start disabled; enable after Split Ledger is proven stable. |
| `shift_recycle_premium_floor` | `60.0` | Yes | float | Only close frozen positions with premium BELOW this value. Positions above the floor are too expensive to close immediately (leave for natural decay + close-at-5). |
| `shift_recycle_max_pct` | `1.0` | Yes | float | Maximum fraction of frozen lots to close per shift (0.0–1.0). 1.0 = close all eligible. 0.5 = close at most half. |

### Parameter Interactions

```
max_lots_per_side = 100       ← cap on active_lots (per Split Ledger)
max_total_exposure = 200      ← cap on active + frozen (absolute ceiling)
shift_recycle_enabled = True  ← proactive cleanup at shift
shift_recycle_premium_floor = 60  ← only close frozen if premium < $60
harvest_profit_pct = 40       ← M1 closes frozen if 40%+ profit (existing)
close_at_threshold = 5        ← close-at-5 for any position at $5 (existing)
```

**Frozen position lifecycle under full configuration:**
```
t=0:   Shift occurs → positions frozen
       IF shift_recycle_enabled AND premium < $60:
         → Shift-Time Recycle closes immediately

t+30m: M1 scans → if 40%+ profit AND capacity pressure ≥ threshold:
         → Harvest closes the position

t+2h:  Premium decays to $5 → close-at-5 triggers

t+4h:  Still alive? M2 fires when cap blocks next adjustment
         → Emergency recycle closes + re-sells
```

---

## 8. Risk Analysis

### Split Ledger Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Active lots exceed exchange margin** | Medium | `max_total_exposure` parameter provides absolute ceiling. Exchange margin checks still apply via `smart_execute`. Margin Guardian (if enabled) monitors real exchange margin utilization independently. |
| **Hidden exposure in frozen lots** | Low | `calculate_standard_loss()` (line 72) and `calculate_reversal_loss()` (line 185) already include ALL positions (active + frozen) in loss calculation. The split ONLY affects the position cap, not loss awareness. |
| **More aggressive selling** | Medium | With frozen lots not blocking, the algo sells more freely. This is the desired behavior, but `max_total_exposure` guards against extreme cases. |
| **Frozen lots accumulate without bound** | Low | `max_total_exposure` is the hard stop. Additionally, M1/close-at-5 still clean up frozen positions. The new `check_total_exposure()` safety method warns the dashboard at 80% of ceiling. |
| **Safety check conflict** | RESOLVED | `check_position_cap()` switches from `total_lots` to `active_lots`. New `check_total_exposure()` covers the gap. Without this fix, the safety module would still block adjustments and contradict Split Ledger. |
| **Recycler viability miscalculation** | RESOLVED | `check_recycle_viability()` affordability check updated to use `active_lots`. Without this, the recycler would reject viable recycles because it thinks `total_lots` must fit in `max_lots_per_side`. |
| **M2 false trigger from new error message** | RESOLVED | The `max_total_exposure` error message uses "Total exposure ceiling" instead of "Position cap reached". Monitor line 2615 specifically checks for "Position cap reached" to trigger M2 — the new message will not match. |

### Shift-Time Recycle Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Paying too much for buyback** | Medium | `shift_recycle_premium_floor` limits buyback to cheap positions only. Positions above the floor are left for natural decay. |
| **Extra lots from cost recovery** | Low | The buyback cost is folded into `loss_to_cover`, so `calculate_lots_to_sell` naturally adds extra lots. Net capacity gain is always positive since new premium > old premium. |
| **Execution failure in buyback** | Medium | If all closes fail, `shift_recycle_buyback=0.0`, and `total_loss_to_cover = loss + 0 = loss`. Behavior identical to current code. No worse than today. |
| **Whipsaw after shift** | Low | If market reverses immediately after shift, frozen lots would have been profitable to hold. But this is already true for any shift decision — the shift_threshold prevents premature shifts. |
| **In-flight guard conflict** | RESOLVED | `close_position()` already has `_being_closed` guard (audit fix). If a frozen position is being closed by close-at-5 at the same time as shift recycle, the second call is safely rejected. |

### What Stays the Same (Code Audit Verified)

These critical behaviors are **unchanged**:

| Behavior | Verified Location | Reasoning |
|----------|-------------------|-----------|
| `calculate_standard_loss()` sums ALL positions | `mmm_engine.py` line 72-180 | Uses frozen_positions list directly, not active_lots cap |
| `calculate_reversal_loss()` checks ALL adjustments | `mmm_engine.py` line 185-275 | Uses adjustment_fills + frozen_positions lists |
| `close_at_5` scans ALL positions | `mmm_close_at_5.py` line 1-183 | Scans all positions by status, not by cap |
| `trigger_snapshot` per active strike | `mmm_strike_shift.py` line 319 | Set by activate_new_strike on new strike |
| Exchange margin via `smart_execute()` | `mmm_executor.py` | Exchange rejects if margin insufficient |
| Margin Guardian real-time monitoring | `mmm_margin_guardian.py` | Independent tier-based defense |
| M1 harvesting on every heartbeat | `mmm_harvester.py` | Scans frozen_positions list, not cap |
| M2 recycling when capacity blocked | `mmm_recycler.py` + monitor line 2615 | Triggered by "Position cap reached" string |
| M3 asymmetry rebalancing | `mmm_harvester.py` line 28-85 | Uses total_lots for asymmetry ratio |
| Perp hedge delta calculation | `mmm_perp_hedge.py` | Uses positions for delta, total_lots for band widening |
| Consistency check at heartbeat start | `mmm_monitor.py` line 710-735 | Calls recompute_side_lots — rebuilds all derived fields |

---

## 9. Worked Examples

### Example 1: Split Ledger Only (No Shift-Time Recycle)

```
Config: max_lots_per_side=100, max_total_exposure=200

State before adjustment:
  CE active_lots=60, frozen_lots=30, total_lots=90
  
Adjustment trigger fires, need to sell 20 PE lots:

  BEFORE (current code):
    mmm_engine.py line 336: current_total = total_lots = 90
    mmm_safety.py line 88:  total = 90 → 90% ratio → alert, stop_adjustments
    Monitor skips adjustment entirely

  AFTER (Split Ledger):
    mmm_engine.py line 336: current_total = active_lots = 60
    mmm_safety.py line 88:  total = active_lots = 60 → 60% < 80% → no alert
    60 + 20 = 80 ≤ 100 → sell all 20 lots  ✓
    Safety check_total_exposure: total_lots = 90 + 20 = 110 → 55% of 200 → OK
```

### Example 2: Shift-Time Recycle

```
Config: shift_recycle_enabled=True, shift_recycle_premium_floor=60

CE at 78,000: 50 lots, entry $120, current premium $40 (decaying)
New strike: CE at 73,000 (premium $120)
Loss to hedge: $5.00

Step 1: find_new_strike() → 73,000 @ $120 ✓ (mmm_strike_shift.py line 145)
Step 2: freeze_current_positions() → freeze 50 lots (mmm_strike_shift.py line 97)
Step 3: _shift_time_recycle():
  - 50 frozen lots @ premium $40 (< $60 floor) → eligible
  - Sort cheapest first → all at $40
  - close_position() for each (reduce_only=True via mmm_executor)
  - Buyback cost: 50 × $40 × 0.001 = $2.00
  - Realized P&L: ($120 - $40) × 50 × 0.001 = $4.00 profit (recorded by close_position)

Step 4: calculate_lots_to_sell():
  total_to_cover = $5.00 (loss) + $2.00 (buyback) = $7.00
  raw = $7.00 / ($120 × 0.001) × 1.05 = 61.25 → ceil = 62
  active_lots check: 0 + 62 = 62 ≤ 100 → OK
  total_exposure check: 0 + 62 = 62 ≤ 200 → OK

Step 5: Sell 62 CE @ 73,000

Result:
  BEFORE: 50 frozen + 62 active = 112 active_lots equivalent consuming capacity
  AFTER:  62 active lots, 0 frozen  ← clean state
  Buyback cost: $2.00 → recovered by 17 extra lots at $120
  Net: freed 50, used 17 extra = +33 lots of capacity saved
```

### Example 3: Expensive Frozen — Recycle Skips

```
Config: shift_recycle_premium_floor=60

CE at 74,000: 30 lots, entry $150, current premium $85 (still meaty)
New strike: CE at 71,000 (premium $130)

Step 3: _shift_time_recycle():
  - 30 frozen lots @ premium $85 (> $60 floor) → SKIP
  - buyback cost = $0.00

Step 4: calculate_lots_to_sell():
  total_to_cover = $5.00 (unchanged)
  lots = $5.00 / ($130 × 0.001) × 1.05 = 40.4 → ceil = 41
  active_lots check: 0 + 41 = 41 ≤ 100 → OK (active_lots = 0 after freeze)
  total_exposure check: 30 (frozen) + 41 = 71 ≤ 200 → OK

Result: 30 frozen lots remain at 74,000. But with Split Ledger,
they don't block the 41-lot sell at new strike.
M1 will harvest them once they decay to 40%+ profit from entry $150.
Close-at-5 catches any survivors at $5.
```

### Example 4: max_total_exposure ceiling hit

```
Config: max_lots_per_side=100, max_total_exposure=150

State: CE active_lots=80, frozen_lots=60, total_lots=140
Trigger fires, need 20 lots:

  active_lots check: 80 + 20 = 100 ≤ 100 → OK
  total_exposure check: 140 + 20 = 160 > 150 → CAPPED
    lots_to_sell = 150 - 140 = 10
    Message: "Total exposure ceiling: CE has 140/150 lots (active+frozen)"
    ← Note: does NOT contain "Position cap reached" → M2 NOT triggered
    
Result: only 10 lots sold instead of 20. Safety ceiling prevents
unbounded accumulation even though active_lots had room.
```

---

## 10. Integration with M1/M2/M3

### M1 (Harvesting) — Minimal Change, Better Behavior

**Code impact:** None — M1 already uses `total_lots` for capacity pressure (line 126), which is correct.

With Split Ledger, M1 becomes a **profitability optimizer** rather than an emergency capacity saver:
- Capacity pressure still calculated from `total_lots/max_lots` → M1 runs when total exposure is high
- Positions closed by Shift-Time Recycle won't appear in M1's scan (already gone from `frozen_positions` list after recompute)
- M1's `harvest_enabled` gate and `harvest_profit_pct` remain the primary controls
- M3 asymmetry boost still uses `total_lots` ratio — correctly detects if one side has too much total exposure

### M2 (Recycling) — Reduced Trigger Frequency, Code Changes Required

**Code impact:** `check_recycle_viability()` and Phase B cap check updated (see §4.3).

M2 fires when `calculate_lots_to_sell()` returns 0 with "Position cap reached" (monitor line 2615). With Split Ledger:
- `active_lots` cap is harder to hit → M2 triggers less often
- `max_total_exposure` uses a different error message → M2 is NOT triggered by it
- When M2 does trigger (active_lots truly at cap), the viability check uses `active_lots` to determine if Phase B fits
- M2 remains the last-resort safety net for active capacity exhaustion

**Important:** If `max_total_exposure` ceiling blocks the engine, M2 does NOT fire. This is intentional — the ceiling is a safety brake, not a recoverable condition. The operator should respond by either:
1. Lowering `shift_recycle_premium_floor` to close more frozen lots
2. Raising `max_total_exposure` if margin allows
3. Enabling `shift_recycle_enabled` to prevent the buildup

### M3 (Asymmetry) — No Change, Better Synergy

M3 uses `total_lots` (lines 50-51 of harvester). This is correct — asymmetry detection should see ALL lots including frozen. With Split Ledger:
- M3 still detects when CE has 120 total lots vs PE's 40 → extreme ratio
- M3 relaxes M1 harvest thresholds on the heavy side → faster frozen cleanup
- Split Ledger's capacity freedom means the algo can sell freely on the light side to rebalance

### Lifecycle Flowchart

```
Strike Shift Triggered
        │
        ▼
   Find New Strike ──── (mmm_strike_shift.find_new_strike)
        │
        ▼
   Freeze Positions ──── (mmm_strike_shift.freeze_current_positions)
        │                  │
        │                  └──→ Active positions → status='shifted'
        │                       recompute_side_lots() → active_lots=0,
        │                       frozen_total_lots includes newly frozen
        │
        ├── shift_recycle_enabled? ──Yes──→ _shift_time_recycle()
        │                                   │
        │                                   ├── For each frozen_pos where
        │                                   │   premium < premium_floor:
        │                                   │     → close_position()
        │                                   │     → cost accumulated
        │                                   │
        │                                   └── Returns buyback_cost_usd
        │                                         │
        ▼                                         ▼
   loss_to_cover = loss + buyback_cost
        │
        ▼
   calculate_lots_to_sell() ──── (mmm_engine)
   Cap check uses active_lots ← SPLIT LEDGER CHANGE
   Safety ceiling uses total_lots (max_total_exposure)
        │
        ▼
   Sell at New Strike ──── (executor.smart_execute)
        │
        ▼
   activate_new_strike() ──── (mmm_strike_shift)
        │
        ├── Remaining frozen ────→ M1 scans each heartbeat
        │   positions                Close-at-5 scans each heartbeat
        │                            M2 if active_lots cap hit later
        ▼
   Continue normal algo
```

---

## 11. Implementation Phases & Checklist

### Phase 1: Split Ledger Core (Minimal, High Impact)

**Files changed:** 4 (`mmm_engine.py`, `mmm_safety.py`, `mmm_state.py`, `mmm_recycler.py`)  
**Lines changed:** ~50  
**Risk:** Low  
**Impact:** Eliminates frozen lot blocking immediately

- [ ] **P1.1** `mmm_engine.py` line 336: Change `hedge_state.get('total_lots', 0)` → `hedge_state.get('active_lots', 0)` in `calculate_lots_to_sell()`
- [ ] **P1.2** `mmm_engine.py`: Add `max_total_exposure` safety ceiling check after existing cap block (before final return)
- [ ] **P1.3** `mmm_safety.py` line 88: Change `side_state.get('total_lots', 0)` → `side_state.get('active_lots', 0)` in `check_position_cap()`
- [ ] **P1.4** `mmm_safety.py`: Add new `check_total_exposure()` method for total lots alarm
- [ ] **P1.5** `mmm_safety.py`: Call `check_total_exposure()` from `run_all_checks()` after `check_position_cap()`
- [ ] **P1.6** `mmm_recycler.py`: Rename `current_total_lots` → `current_active_lots` in `check_recycle_viability()` signature and update affordability check logic
- [ ] **P1.7** `mmm_recycler.py`: Update caller in `execute_lot_recycling()` to pass `active_lots` instead of `total_lots`
- [ ] **P1.8** `mmm_recycler.py` Phase B: Change `hedge_state_refreshed.get('total_lots', 0)` → `hedge_state_refreshed.get('active_lots', 0)` at line ~432
- [ ] **P1.9** `mmm_state.py` `DEFAULT_PARAMS`: Add `'max_total_exposure': 0`
- [ ] **P1.10** `mmm_state.py` `HOT_RELOAD_PARAMS`: Add `'max_total_exposure'`
- [ ] **P1.11** Update `tests/test_mmm_recycler.py`: Change `current_total_lots=` → `current_active_lots=` in all test calls; add `active_lots` to session fixtures
- [ ] **P1.12** Verify: Run existing tests — sessions with zero frozen lots must have identical behavior (regression-safe)

### Phase 2: Shift-Time Recycle (Proactive Cleanup)

**Files changed:** 2 (`mmm_monitor.py`, `mmm_state.py`)  
**Lines changed:** ~120  
**Risk:** Medium (new execution path during shift)  
**Impact:** Eliminates frozen lot lingering  
**Default:** DISABLED (`shift_recycle_enabled=False`)

- [ ] **P2.1** `mmm_monitor.py`: Add `_shift_time_recycle()` method to `MMMMonitor` class
- [ ] **P2.2** `mmm_monitor.py`: Hook into `_process_strike_shift()` between freeze and lot calc
- [ ] **P2.3** `mmm_monitor.py`: Verify `_D`, `_LOT` import from `mmm_constants`
- [ ] **P2.4** `mmm_state.py` `DEFAULT_PARAMS`: Add `shift_recycle_enabled`, `shift_recycle_premium_floor`, `shift_recycle_max_pct`
- [ ] **P2.5** `mmm_state.py` `HOT_RELOAD_PARAMS`: Add all three
- [ ] **P2.6** Test: With `shift_recycle_enabled=False`, behavior must be identical to Phase 1 (buyback=0.0 passthrough)
- [ ] **P2.7** Ship with `shift_recycle_enabled=False` by default — enable via dashboard after observation

### Phase 3: Dashboard Visibility (Frontend)

- [ ] **P3.1** `MMMTriggerGauge.js`: Already shows `activeLots` and `frozenLots` — verify behavior unchanged
- [ ] **P3.2** `MMMSafetyPanel.js` lines 141-142: Currently shows `total_lots` — add `active_lots` display alongside for clarity
- [ ] **P3.3** `MMMActivityFeed.js`: Show "Shift-Time Recycle" events (already handled by `emit_recycle` → existing recycle event handler)
- [ ] **P3.4** `MMMSettingsDialog.js`: Add `max_total_exposure`, `shift_recycle_enabled`, `shift_recycle_premium_floor`, `shift_recycle_max_pct` to Hot-Reload settings

### Phase 4: Tuning & Observation

1. Monitor for 1 week with Split Ledger only (Phase 1)
2. Enable Shift-Time Recycle with conservative `premium_floor=40`
3. Gradually increase `premium_floor` based on observed savings
4. Adjust `max_total_exposure` based on actual exchange margin usage

---

## 12. Profitability Suggestions

Based on the deep code audit, here are additional ideas to maximize profitability from this change:

### Suggestion 1: Lower M1 Harvest Pressure Threshold with Split Ledger

Currently `harvest_pressure_threshold=0.7` means M1 only runs when the side is 70%+ of cap. With Split Ledger, `active_lots` might be 40 while `total_lots` is 90. M1 uses `total_lots` for pressure, so it still fires at 90%.

**But:** Consider lowering `harvest_pressure_threshold` to `0.5` after enabling Split Ledger. Since frozen lots no longer block the cap, there's no urgency to harvest at high pressure. Instead, harvest at moderate pressure to lock profits earlier — even a 40% profit on a 30-lot frozen position is meaningful.

### Suggestion 2: `shift_recycle_premium_floor` Dynamic Calculation

Instead of a static `premium_floor=60`, consider making it relative to the new strike's premium:

```
dynamic_floor = new_premium * 0.40  # close if frozen premium < 40% of new premium
```

This automatically adapts: if the new strike has $150 premium, floor becomes $60. If new strike has $80 premium, floor becomes $32 (only close very cheap positions).

**Implementation:** Simple change in `_shift_time_recycle()` — compute floor from `new_strike_info['premium']` if `shift_recycle_premium_floor <= 0`.

### Suggestion 3: Recycle Cost Recovery Tracking

Track `session['shift_recycle_total_cost']` and `session['shift_recycle_total_freed']`. Display in analytics. This gives the operator hard numbers on whether shift-recycle is profitable:

```
ROI = (freed_lots × avg_theta_earned) / buyback_cost
```

If ROI < 1.0, the premium_floor is too high. If ROI > 5.0, the floor can be raised.

---

## Summary: What Changes and Why

| Current Behavior | New Behavior | Why |
|-----------------|-------------|-----|
| `total_lots` used for cap check in engine | `active_lots` only used for cap | Frozen lots are dying — they shouldn't block productive hedging |
| `total_lots` used for safety `check_position_cap` | `active_lots` used; new `check_total_exposure` for total | Safety module must align with engine or it blocks adjustments independently |
| Recycler affordability uses `total_lots` | Uses `active_lots` | Phase B lots add to active_lots, not total_lots |
| Frozen lots linger for hours | Optionally closed immediately at shift time | Opportunity cost of frozen capacity >> buyback cost |
| M2 fires only when capped (reactive) | Shift-Time Recycle fires at shift moment (proactive) | Prevent the problem rather than react to it |
| No safety ceiling for combined lots | `max_total_exposure` as absolute brake | Guard against runaway accumulation when frozen lots don't block |
| Loss calculations include frozen | **UNCHANGED** | Frozen lots are real risk — loss awareness must include them |
| M1 pressure uses total_lots | **UNCHANGED** | Harvest should still fire when total exposure is high |
| M3 asymmetry uses total_lots | **UNCHANGED** | Asymmetry detection must see all lots for balance |

**Core insight:** Frozen positions are dying assets that consume capacity but produce diminishing value. Separating the cap check (`active_lots`) from risk awareness (`total_lots`) lets the algo sell productively while still accounting for every open position's risk. The buyback cost of proactive cleanup is recoverable through higher-premium lots at the new strike, making it a net-positive trade in all scenarios where `premium_new > premium_frozen`.
