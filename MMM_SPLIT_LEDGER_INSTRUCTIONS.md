# MMM Split Ledger — Coding Instructions

**Reference plan:** `MMM_SPLIT_LEDGER_PLAN.md`  
**Source root:** `webui/backend/routes/mmm/`  
**Date verified:** March 4, 2026  
**Implementation status:** Phase 1 ✅ DONE | Phase 2 ✅ DONE | Bug Fix ✅ | Profitability Suggestions ✅ DONE

---

## IMPLEMENTATION STATUS

All 16 edits from Phase 1 and Phase 2 have been implemented and verified.

### Bug Found & Fixed During Review (March 4, 2026)

**`mmm_recycler.py` line 197 — `NameError: remaining_lots`**

The old Check 3 code computed `remaining_lots = current_total_lots - recycled_lots`. When Check 3 was rewritten for Split Ledger (Edit 8), the variable was removed but the details dict on the success path still referenced it. This caused a `NameError` whenever the viability check **passed** (all 3 checks OK).

**Fix applied:**
- `mmm_recycler.py` line 197: `'remaining_lots': remaining_lots` → `'current_active': current_active_lots`
- `mmm_recycler.py` line 113 docstring: updated to match new semantics
- `tests/test_mmm_recycler.py` line 398: assertion updated from `'remaining_lots'` → `'current_active'`

**Test result after fix:** 31 passed, 0 failed.

---

## HOW TO USE THIS FILE

All edits below are **already implemented**. This file is retained as documentation of what was changed and where, for future reference.

~~1. Execute **Phase 1** edits completely before touching Phase 2.~~
~~2. Each edit block has the **exact `BEFORE` code** (copy-search it in the file) and **exact `AFTER` code** to replace it with.~~
~~3. After finishing all Phase 1 edits, run the test suite before proceeding to Phase 2.~~
~~4. Phase 2 is shipped **disabled by default** — no live impact until operator enables it.~~

---

## ⛔ DO NOT TOUCH (these use `total_lots` intentionally)

| File | Line(s) | Reason |
|------|---------|--------|
| `mmm_engine.py` | 100–150 | `calculate_standard_loss()` — loss calc MUST include frozen |
| `mmm_engine.py` | 240–260 | `calculate_reversal_loss()` — same |
| `mmm_safety.py` | 338–339 | `check_asymmetry()` — asymmetry monitors total exposure |
| `mmm_safety.py` | 515–517 | `check_margin()` — margin proxy must include all open lots |
| `mmm_recycler.py` | 329 | greedy selection — `max_recycle_pct` correctly applies to total pool |
| `mmm_harvester.py` | 50–51 | M3 uses `total_lots` for asymmetry ratio — correct |
| `mmm_harvester.py` | 126 | M1 capacity pressure — must see total exposure to run |
| `mmm_perp_hedge.py` | 109 | rebalance band widener — margin awareness needs full exposure |
| `mmm_state.py` | 283 | `recompute_side_lots()` derivation — formula is correct |

---

## PHASE 1 — Split Ledger Core ✅ COMPLETE

**Files:** `mmm_engine.py`, `mmm_safety.py`, `mmm_recycler.py`, `mmm_state.py`

---

### EDIT 1 — `mmm_engine.py` — Cap check uses `active_lots` instead of `total_lots`

**Line ~334. Function: `calculate_lots_to_sell()`**

BEFORE:
```python
        # §13.1: Position cap
        hedge_state = session.get(hedge_side, {})
        current_total = hedge_state.get('total_lots', 0)

        if current_total + lots_to_sell > max_lots_per_side:
```

AFTER:
```python
        # §13.1: Position cap — Split Ledger: only active_lots count against cap
        hedge_state = session.get(hedge_side, {})
        current_total = hedge_state.get('active_lots', 0)

        if current_total + lots_to_sell > max_lots_per_side:
```

---

### EDIT 2 — `mmm_engine.py` — Insert `max_total_exposure` ceiling before the final return

**Immediately after the cap block ends, before `return lots_to_sell, constraint_msg`**

BEFORE:
```python
            constraint_msg = f"{constraint_msg}; {cap_msg}" if constraint_msg else cap_msg

        return lots_to_sell, constraint_msg
```

AFTER:
```python
            constraint_msg = f"{constraint_msg}; {cap_msg}" if constraint_msg else cap_msg

        # ── Split Ledger: max_total_exposure safety ceiling ───────────────────
        # active_lots cap is the primary gate. This is the ABSOLUTE ceiling on
        # combined active + frozen lots to guard against runaway accumulation.
        # IMPORTANT: error message must NOT contain "Position cap reached" —
        # that exact string triggers M2 recycling at monitor line ~2615.
        max_total_exposure = params.get('max_total_exposure', 0)
        if max_total_exposure <= 0:
            max_total_exposure = max_lots_per_side * 2
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
        # ── END Split Ledger ──────────────────────────────────────────────────

        return lots_to_sell, constraint_msg
```

---

### EDIT 3 — `mmm_safety.py` — `check_position_cap()` uses `active_lots`

**Line ~88. Inside `check_position_cap()`, inside the `for side_key in ['ce', 'pe']:` loop.**

BEFORE:
```python
            side_state = session.get(side_key, {})
            total = side_state.get('total_lots', 0)
            ratio = total / max_lots if max_lots > 0 else 0
```

AFTER:
```python
            side_state = session.get(side_key, {})
            total = side_state.get('active_lots', 0)  # Split Ledger: cap on active lots only
            ratio = total / max_lots if max_lots > 0 else 0
```

---

### EDIT 4 — `mmm_safety.py` — Call `check_total_exposure()` from `run_all_checks()`

**Line ~59. Inside `run_all_checks()`, immediately after the `check_position_cap` call.**

BEFORE:
```python
        events.extend(self.check_position_cap(session))
        events.extend(self.check_max_adjustments(session))
```

AFTER:
```python
        events.extend(self.check_position_cap(session))
        events.extend(self.check_total_exposure(session))   # Split Ledger
        events.extend(self.check_max_adjustments(session))
```

---

### EDIT 5 — `mmm_safety.py` — Add `check_total_exposure()` method

**Insert this NEW method immediately before `def check_asymmetry(` (line ~333).**

```python
    def check_total_exposure(self, session: Dict) -> List[Dict]:
        """
        Split Ledger: Warn when active + frozen lots approach max_total_exposure
        ceiling. action='warn' only — the engine handles the hard block.
        Does NOT fire 'stop_adjustments' to avoid bypassing the engine path.
        """
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
                    'action': 'warn',
                    'details': {
                        'side': side_key, 'total': total,
                        'active': active, 'frozen': frozen, 'max': max_total,
                    },
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
                    'details': {
                        'side': side_key, 'total': total,
                        'active': active, 'frozen': frozen, 'max': max_total,
                    },
                })

        return events

```

---

### EDIT 6 — `mmm_recycler.py` — Rename param in `check_recycle_viability()` signature

**Line ~103. Function definition at module level (not a class method).**

BEFORE:
```python
def check_recycle_viability(
    recyclable_with_prices: List[Dict],
    loss_to_hedge: float,
    new_premium: float,
    current_total_lots: int,
    max_lots_per_side: int,
    params: Dict,
```

AFTER:
```python
def check_recycle_viability(
    recyclable_with_prices: List[Dict],
    loss_to_hedge: float,
    new_premium: float,
    current_active_lots: int,   # Split Ledger: was current_total_lots, now active only
    max_lots_per_side: int,
    params: Dict,
```

---

### EDIT 7 — `mmm_recycler.py` — Fix docstring for renamed param

**Line ~119. Docstring inside `check_recycle_viability()`.**

BEFORE:
```python
        current_total_lots: Current total lots on the capped side
```

AFTER:
```python
        current_active_lots: Current ACTIVE lots on the capped side (excludes frozen)
```

---

### EDIT 8 — `mmm_recycler.py` — Fix affordability check (Check 3)

**Lines ~177–186. Inside `check_recycle_viability()`. Replace the full Check 3 block.**

BEFORE:
```python
    # Check 3: Affordability
    remaining_lots = current_total_lots - recycled_lots
    if new_lots_needed + remaining_lots > max_lots_per_side:
        return (
            False,
            f'Affordability: {new_lots_needed} new + {remaining_lots} remaining '
            f'= {new_lots_needed + remaining_lots} > cap {max_lots_per_side}',
            {'new_lots_needed': new_lots_needed, 'remaining': remaining_lots,
             'cap': max_lots_per_side},
        )
```

AFTER:
```python
    # Check 3: Affordability — Split Ledger
    # Phase A closes frozen positions → active_lots is UNCHANGED after Phase A.
    # Phase B adds new_lots_needed to active_lots. Verify it fits within cap.
    if current_active_lots + new_lots_needed > max_lots_per_side:
        return (
            False,
            f'Affordability: {new_lots_needed} new + {current_active_lots} active '
            f'= {new_lots_needed + current_active_lots} > cap {max_lots_per_side}',
            {'new_lots_needed': new_lots_needed, 'current_active': current_active_lots,
             'cap': max_lots_per_side},
        )
```

---

### EDIT 9 — `mmm_recycler.py` — Update caller to pass `active_lots`

**Lines ~362–372. Inside `execute_lot_recycling()`. The call to `check_recycle_viability`.**

BEFORE:
```python
    viable, reason, viability_details = check_recycle_viability(
        recyclable_with_prices=selected,
        loss_to_hedge=loss_to_hedge,
        new_premium=new_premium,
        current_total_lots=current_total,
        max_lots_per_side=max_lots,
        params=params,
    )
```

AFTER:
```python
    current_active = hedge_state.get('active_lots', 0)   # Split Ledger
    viable, reason, viability_details = check_recycle_viability(
        recyclable_with_prices=selected,
        loss_to_hedge=loss_to_hedge,
        new_premium=new_premium,
        current_active_lots=current_active,
        max_lots_per_side=max_lots,
        params=params,
    )
```

---

### EDIT 10 — `mmm_recycler.py` — Phase B final cap check uses `active_lots`

**Lines ~433–436. Inside `execute_lot_recycling()`. The "Final cap check after Phase A" block.**

BEFORE:
```python
    # Final cap check after Phase A
    hedge_state_refreshed = session.get(hedge_side, {})
    remaining_after_a = hedge_state_refreshed.get('total_lots', 0)
    if remaining_after_a + phase_b_lots > max_lots:
```

AFTER:
```python
    # Final cap check after Phase A — Split Ledger: Phase A only closes frozen,
    # so active_lots is unchanged. Phase B adds to active_lots.
    hedge_state_refreshed = session.get(hedge_side, {})
    remaining_after_a = hedge_state_refreshed.get('active_lots', 0)
    if remaining_after_a + phase_b_lots > max_lots:
```

---

### EDIT 11 — `mmm_state.py` — Add new params to `DEFAULT_PARAMS`

**Line ~328. Immediately after the `'max_lots_per_side'` entry. Add ALL 4 new params at once.**

BEFORE:
```python
    'max_lots_per_side': 100,           # maximum total lots per CE or PE
    'max_adjustments': 500,             # maximum adjustment events
```

AFTER:
```python
    'max_lots_per_side': 100,           # maximum total lots per CE or PE
    # Split Ledger
    'max_total_exposure': 0,            # abs ceiling on active+frozen lots per side. 0=auto (2×max_lots_per_side)
    'shift_recycle_enabled': False,     # proactive frozen cleanup at shift time (Phase 2)
    'shift_recycle_premium_floor': 60.0,  # close frozen positions with live premium below this
    'shift_recycle_max_pct': 1.0,       # max fraction of frozen lots to close per shift (0.0-1.0)
    'max_adjustments': 500,             # maximum adjustment events
```

---

### EDIT 12 — `mmm_state.py` — Add new params to `HOT_RELOAD_PARAMS`

**Line ~432. The line containing `'premium_buffer_pct', 'max_lots_per_side'` inside the HOT_RELOAD_PARAMS set.**

BEFORE:
```python
    'premium_buffer_pct', 'max_lots_per_side',
    'max_adjustments', 'max_loss_amount',
```

AFTER:
```python
    'premium_buffer_pct', 'max_lots_per_side',
    'max_total_exposure',                          # Split Ledger Phase 1
    'shift_recycle_enabled', 'shift_recycle_premium_floor', 'shift_recycle_max_pct',  # Phase 2
    'max_adjustments', 'max_loss_amount',
```

---

### EDIT 13 — `tests/test_mmm_recycler.py` — Update test fixtures and calls

**Search for all occurrences of `current_total_lots=` and rename to `current_active_lots=`.**

Also search for any session fixture dicts that have `'total_lots'` but no `'active_lots'` key — add `'active_lots'` with the appropriate value (typically `total_lots - frozen_total_lots` or same as `total_lots` if no frozen in the fixture).

**NOTE:** Verify the test file path first: `find . -name "test_mmm_recycler.py"` — if it does not exist, skip this step.

---

## ✅ PHASE 1 REGRESSION CHECK — PASSED

Verified:

1. Sessions with zero frozen positions: `active_lots == total_lots` so all behavior is identical to before.
2. `check_position_cap()` still fires `stop_adjustments` when `active_lots >= max_lots_per_side` — the change only switches which field is checked.
3. The string `"Position cap reached"` in `mmm_engine.py` is UNCHANGED — M2 recycling trigger at `mmm_monitor.py` line ~2615 still works.
4. `"Total exposure ceiling"` is the new error string — confirm it does NOT appear anywhere in the monitor's M2 trigger logic.

---

## PHASE 2 — Shift-Time Recycle ✅ COMPLETE

**Ships DISABLED by default.** `shift_recycle_enabled=False` means zero behavior change until explicitly enabled via dashboard hot-reload.

**Files:** `mmm_monitor.py`

---

### EDIT 14 — `mmm_monitor.py` — Add `_D, _LOT` to imports

**Line ~77. The existing `mmm_constants` import line.**

BEFORE:
```python
from .mmm_constants import LOT_SIZE_BTC, strike_key as _strike_key
```

AFTER:
```python
from .mmm_constants import LOT_SIZE_BTC, strike_key as _strike_key, _D, _LOT
```

**Note:** If `_D` or `_LOT` are not defined in `mmm_constants.py`, check `mmm_engine.py` top-of-file imports and use the same source. Do not guess — read the file first.

---

### EDIT 15 — `mmm_monitor.py` — Hook shift recycle into `_process_strike_shift()`

**Lines ~2778–2789. After `freeze_current_positions` call, before `lots, _ = self._engine.calculate_lots_to_sell`.**

BEFORE:
```python
        # New strike found — NOW freeze current positions
        freeze_result = freeze_current_positions(session, side)

        # Sell at new strike
        new_strike = new_strike_info['strike']
        hedge_premium = new_strike_info['premium']

        lots, _ = self._engine.calculate_lots_to_sell(
            session, side, loss, hedge_premium,
        )
```

AFTER:
```python
        # New strike found — NOW freeze current positions
        freeze_result = freeze_current_positions(session, side)

        # ── Split Ledger Phase 2: Shift-Time Recycle ─────────────────────────
        shift_recycle_buyback = 0.0
        _sr_params = session.get('params', {})
        if _sr_params.get('shift_recycle_enabled', False):
            shift_recycle_buyback = await self._shift_time_recycle(
                side, new_strike_info,
            )
        # ─────────────────────────────────────────────────────────────────────

        # Sell at new strike
        new_strike = new_strike_info['strike']
        hedge_premium = new_strike_info['premium']

        # Fold buyback cost so extra lots at new strike recover it
        total_loss_to_cover = loss + shift_recycle_buyback

        lots, _ = self._engine.calculate_lots_to_sell(
            session, side, total_loss_to_cover, hedge_premium,
        )
```

---

### EDIT 16 — `mmm_monitor.py` — Add `_shift_time_recycle()` method to `MMMMonitor` class

**Insert this complete method after the `_process_lot_recycling()` method (which ends around line ~3377).**

To find the insertion point: search for the line immediately after the end of `_process_lot_recycling`, which is the next `async def` or `def` at the same indentation level. Insert the new method before it.

```python
    async def _shift_time_recycle(
        self,
        side: str,
        new_strike_info: Dict,
    ) -> float:
        """
        Split Ledger Phase 2: At shift time, close cheap frozen positions
        on `side` to free capacity. Returns total buyback cost in USD so
        the caller can fold it into the new sell lot calculation.

        Only closes frozen positions with live premium BELOW shift_recycle_premium_floor.
        Respects shift_recycle_max_pct limit on frozen lots closed per shift.
        Default: shift_recycle_enabled=False — this method is never called unless enabled.

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

        # Respect max_pct: limit total lots we can close this shift
        total_frozen = sum(f.get('lots', 0) for f in frozen_positions)
        max_closeable_lots = int(total_frozen * max_pct)
        if max_closeable_lots <= 0:
            return 0.0

        option_type = 'call' if side == 'ce' else 'put'
        fetch_fn = self._make_fetch_fn()
        total_buyback = 0.0
        closed_lots = 0

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

        # Sort cheapest first to maximise freed lots per dollar spent
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
                    f"[{sid}] Shift recycle: close rejected for "
                    f"{side.upper()} @ {close_payload['strike']}: "
                    f"{result.get('error', 'unknown')}"
                )

        if closed_lots > 0:
            log_activity(
                'shift_recycle',
                f'♻️ Shift-Time Recycle: closed {closed_lots} frozen '
                f'{side.upper()} lots, buyback ${total_buyback:.4f}',
                sid, 'success',
                {
                    'side': side.upper(),
                    'closed_lots': closed_lots,
                    'buyback_cost': round(total_buyback, 4),
                    'premium_floor': premium_floor,
                },
            )
            try:
                emit_recycle(
                    sid, side.upper(), closed_lots, 0,
                    0, 0, 0,
                    closed_lots,        # net_gain = lots freed
                    total_buyback,      # buyback_cost
                    0,                  # phase_a_pnl (already recorded by close_position)
                )
            except Exception as _e:
                log.warning(f"[{sid}] Shift recycle: emit_recycle failed: {_e}")

        return total_buyback
```

**Verify before committing:**
- `self._make_fetch_fn()` method exists on `MMMMonitor` — grep for it to confirm.
- `close_position` signature from `mmm_close_at_5.py` is `close_position(executor, initializer, session, position)` — confirm before using.
- `emit_recycle` is imported at the top of `mmm_monitor.py` — grep to verify the exact argument order matches.
- `log_activity` is imported at module level — already confirmed at audit.

---

## ✅ PHASE 2 REGRESSION CHECK — PASSED

1. `shift_recycle_enabled=False` (default): `shift_recycle_buyback = 0.0` → `total_loss_to_cover = loss + 0 = loss` — behavior **100% identical** to Phase 1.
2. `shift_recycle_enabled=True` with no frozen positions: method returns `0.0` immediately — same.
3. `shift_recycle_enabled=True` with all frozen premium above floor: method returns `0.0` — same.
4. Only path that changes behavior: enabled + at least one frozen position with `live_premium < premium_floor`.

---

## COMPLETE EDIT SUMMARY

| # | File | What Changes | Status |
|---|------|-------------|--------|
| 1 | `mmm_engine.py` | Cap check: `total_lots` → `active_lots` | ✅ |
| 2 | `mmm_engine.py` | Add `max_total_exposure` safety ceiling block | ✅ |
| 3 | `mmm_safety.py` | `check_position_cap`: `total_lots` → `active_lots` | ✅ |
| 4 | `mmm_safety.py` | `run_all_checks`: add `check_total_exposure()` call | ✅ |
| 5 | `mmm_safety.py` | Add new `check_total_exposure()` method | ✅ |
| 6 | `mmm_recycler.py` | `check_recycle_viability` param rename: `current_total_lots` → `current_active_lots` | ✅ |
| 7 | `mmm_recycler.py` | Fix docstring for renamed param | ✅ |
| 8 | `mmm_recycler.py` | Fix affordability Check 3 logic | ✅ + bug fix |
| 9 | `mmm_recycler.py` | Fix caller to pass `active_lots` | ✅ |
| 10 | `mmm_recycler.py` | Phase B cap check: `total_lots` → `active_lots` | ✅ |
| 11 | `mmm_state.py` | `DEFAULT_PARAMS`: add 4 new params | ✅ |
| 12 | `mmm_state.py` | `HOT_RELOAD_PARAMS`: add 4 new params | ✅ |
| 13 | `tests/test_mmm_recycler.py` | Rename param in test calls + fixtures | ✅ + bug fix |
| 14 | `mmm_monitor.py` | Add `_D, _LOT` to imports | ✅ |
| 15 | `mmm_monitor.py` | Hook shift recycle into `_process_strike_shift()` | ✅ |
| 16 | `mmm_monitor.py` | Add `_shift_time_recycle()` method | ✅ |

**Total files touched:** 5 backend files + 1 test file  
**Files NOT touched:** `mmm_harvester.py`, `mmm_perp_hedge.py`, `mmm_strike_shift.py`, `mmm_close_at_5.py`, `mmm_storage.py`, `mmm_analytics_storage.py`, all frontend files (Phase 3 is dashboard-only polish, not in scope)

---

## 12. Profitability Suggestions ✅ IMPLEMENTED

All 3 suggestions have been implemented (March 4, 2026).

---

### Suggestion 1: Dynamic `shift_recycle_premium_floor` ✅ DONE

**Implementation:**
- `mmm_monitor.py` `_shift_time_recycle()`: If `shift_recycle_premium_floor <= 0`, compute dynamically as `new_strike_premium × shift_recycle_floor_ratio`
- `mmm_state.py` `DEFAULT_PARAMS`: Added `'shift_recycle_floor_ratio': 0.40`
- `mmm_state.py` `HOT_RELOAD_PARAMS`: Added `'shift_recycle_floor_ratio'`

**How to enable:** Set `shift_recycle_premium_floor` to `0` (or negative) via dashboard. The floor will auto-compute as 40% of the new strike premium.

---

### Suggestion 2: Lower `harvest_pressure_threshold` ✅ DONE

**Implementation:**
- `mmm_state.py` `DEFAULT_PARAMS`: Changed `harvest_pressure_threshold` from `0.6` to `0.5`
- Existing sessions can hot-reload this param via dashboard

**Effect:** M1 harvesting starts earlier (at 50% total capacity pressure instead of 60%), leading to more steady cleanup of frozen positions rather than emergency batches.

---

### Suggestion 3: Shift-time recycle ROI tracking ✅ DONE

**Implementation:**
- `mmm_monitor.py` `_shift_time_recycle()`: After successful closes, accumulates stats into `session['shift_recycle_stats']`
- Tracked fields: `total_buyback`, `total_lots_freed`, `total_shifts`

**Usage:** After a few weeks in production, compute:
```
ROI = freed_lots × avg_theta_per_lot_per_hour × avg_hours_saved / total_buyback_cost
```
- ROI < 1.0 → `premium_floor` too high
- ROI > 5.0 → can raise `premium_floor` to capture more capacity

---

## REMAINING PHASES

### Phase 3 — Dashboard / Frontend (NOT STARTED)

The backend is complete. The dashboard needs updates to expose the new Split Ledger params and show frozen vs active breakdown.

**Scope:** Frontend files only — no backend changes.

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 3.1 | Add Split Ledger params to Settings panel | `MMMSettings.js` or equivalent | Expose `max_total_exposure`, `shift_recycle_enabled`, `shift_recycle_premium_floor`, `shift_recycle_max_pct`, `shift_recycle_floor_ratio` in the dashboard settings UI. Group them under a "Split Ledger" section. |
| 3.2 | Show active vs frozen breakdown | `MMMDashboard.js` or status components | Currently shows `total_lots` per side. Add visual breakdown: `active_lots` / `frozen_total_lots` / `total_lots`. Consider a stacked bar or colored pill. |
| 3.3 | Total exposure ceiling indicator | Dashboard status area | Show proximity to `max_total_exposure` ceiling (from `check_total_exposure` safety events). Color-coded: green (< 80%), yellow (80-99%), red (>= 100%). |
| 3.4 | Shift recycle activity feed | Activity/logs area | `shift_recycle` events from `log_activity` should render with the ♻️ emoji and show buyback cost + lots freed. |
| 3.5 | Shift recycle stats display | Session summary / analytics | Display `session['shift_recycle_stats']` (total_buyback, total_lots_freed, total_shifts) if present. |
| 3.6 | `harvest_pressure_threshold` UI note | Settings panel | Add tooltip or help text noting the new 0.5 default (lowered from 0.6 for Split Ledger). |

**Pre-requisites:** Find the exact frontend component file names by searching `webui/frontend/src/` for MMM settings/dashboard components. The backend API for params hot-reload is already working — the frontend just needs to send the new param names.

### Phase 4 — Production Tuning (MANUAL, after 1-2 weeks live)

These are NOT code changes. They are operational tuning decisions based on live data:

| Task | When | Action |
|------|------|--------|
| Verify `active_lots == total_lots` with zero frozen | Day 1 | Start session, confirm no behavioral difference before any shifts |
| Monitor first strike shift | Day 1-2 | Confirm frozen lots no longer block new adjustments |
| Enable `shift_recycle_enabled` | After 2-3 successful sessions | Set to `True` via dashboard, monitor cleanup behavior |
| Set `shift_recycle_premium_floor` to `0` | After shift recycle is proven | Enables dynamic floor mode (Suggestion 1) |
| Review `shift_recycle_stats` ROI | After 2 weeks | Tune `shift_recycle_floor_ratio` based on observed ROI |
| Evaluate `harvest_pressure_threshold` | After 1 week | If M1 fires too aggressively at 0.5, raise to 0.55-0.6 |

---

*End of instructions. Reference `MMM_SPLIT_LEDGER_PLAN.md` for full rationale and worked examples.*
