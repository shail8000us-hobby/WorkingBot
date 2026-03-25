# MMM P&L Core — Deep Architectural Audit

**Date**: 2026-03-25
**Scope**: `mmm_pnl_core.py` and all 10+ files that interact with P&L
**Method**: Mental stress-testing every write path, failure mode, and invariant

---

## 🚨 CRITICAL FLAWS (Must fix before production)

### CRIT-1: Sell-Side Fees Wiped on Every Close Event

**Severity**: P0 — MONEY LOSS
**Real-world scenario**: Session sells 100 lots (fee=$4). First close of 10 lots triggers `_sync_session_fields()` which OVERWRITES `session['total_fees']` from ledger only. Ledger has one close-commission ($0.30). **$3.70 in sell fees vanish instantly.**

**Root cause**: `_sync_session_fields()` line 490:
```python
session['total_fees'] = round(compute_fees(session), 8)
```
`compute_fees()` sums only ledger commissions. But 10+ places write sell-side fees DIRECTLY to `session['total_fees']`:

| File | Line | Context |
|------|------|---------|
| `mmm_engine.py` | 778 | Adjustment sell commission |
| `mmm_monitor.py` | 4531 | Strike shift sell commission |
| `mmm_monitor.py` | 5198 | Scale-up CE sell commission |
| `mmm_monitor.py` | 5239 | Scale-up PE sell commission |
| `mmm_monitor.py` | 5571 | Replenish sell commission |
| `mmm_api.py` | 881 | Initial CE+PE sell commission |
| `mmm_api.py` | 1247 | Retry leg sell commission |
| `mmm_api.py` | 4062 | Inject sell commission |
| `mmm_perp_hedge.py` | 690 | Perp hedge commission |
| `mmm_perp_hedge.py` | 809 | Perp close-all commission |

These ALL bypass the ledger. The next `record_close()` → `_sync_session_fields()` wipes them.

**Safety impact**: `net_pnl = realized + unrealized - fees`. If fees are understated, net_pnl is OVERSTATED. Max-loss check at line 2824 uses `pnl['net_pnl']`. **Max loss may not fire when it should.**

**Fix**: Add `record_fee(session, commission, source, order_id)` to `mmm_pnl_core.py`. Replace all direct `session['total_fees'] +=` writes with ledger fee entries. `_sync_session_fields` then correctly computes total from ledger.

---

### CRIT-2: Storage Double-Booking Correction Gets Overwritten

**Severity**: P1 — SILENT DATA CORRUPTION
**Real-world scenario**: `mmm_storage.py:233` detects fill_sync double-booked P&L and corrects:
```python
session['realized_pnl'] = round(session.get('realized_pnl', 0) - total_over, 8)
```
Next heartbeat's close event → `_sync_session_fields()` → `session['realized_pnl'] = compute_realized_pnl(session)` → overwrites the correction with ledger sum. **Double-booked P&L reappears.**

**Fix**: This correction must either (a) create a negative ledger entry `record_close(source='correction', pnl=-total_over)` or (b) be removed entirely since ledger dedup should prevent the double-booking in the first place (check if the guard at `mmm_storage.py:207` short-circuits for ledger sessions — it does, so this code path is only for pre-migration sessions. Still needs ledger entry if correction runs during migration window).

---

### CRIT-3: Estimated P&L Becomes Permanent Truth If fill_sync Fails

**Severity**: P1 — PHANTOM P&L
**Real-world scenario**:
1. `close_at_5` places buyback → `record_close(confirmed=False)` with estimated price
2. fill_sync is down for 30 minutes (exchange issue, network, restart)
3. Estimated P&L ($200) is treated as truth in `compute_realized_pnl()`
4. Max-loss and all dashboards show this as real P&L
5. Actual fill was at a much worse price — correction never arrives

**Current state**: `compute_realized_pnl()` includes ALL entries (estimated + confirmed). There's a `compute_confirmed_pnl()` but **nothing uses it for safety decisions**.

**Fix**:
- Max-loss check should use `compute_confirmed_pnl()` for safety margin
- Add TTL on estimates: if an estimate is >N minutes old and unconfirmed, flag it
- Dashboard should show confirmed vs estimated separately

---

## ⚠️ ARCHITECTURAL WEAKNESSES

### ARCH-1: Recycler Bypasses pnl_core Encapsulation

**Location**: `mmm_recycler.py:401,510-518,559-567`
**Problem**: Imports private `_ensure_ledger` and `_sync_session_fields` and directly manipulates the ledger list:
```python
from .mmm_pnl_core import _ensure_ledger as _pnl_ensure, _sync_session_fields as _pnl_sync
_ledger = _pnl_ensure(session)
# ... directly pops entries from _ledger ...
_pnl_sync(session)
```
This breaks encapsulation. If ledger structure changes (e.g., index, dedup logic), recycler silently breaks. The `rollback_close(order_id)` function exists for exactly this purpose but isn't used.

**Fix**: Recycler should call `rollback_close(order_id)` for each Phase A close. If rollback needs to target multiple entries, add `rollback_closes_since(session, snapshot_len)` to pnl_core.

---

### ARCH-2: Ledger Stores Computed P&L (Event-Sourcing Violation)

**Problem**: Each ledger entry stores:
```python
'pnl': round((entry_premium - close_premium) * lots * LOT_SIZE_BTC, 8)
```
In institutional event-sourcing, the ledger stores **raw facts only** (entry_premium, close_premium, lots). P&L is ALWAYS computed on read.

**Why it matters**:
- If `LOT_SIZE_BTC` changes (exchange contract size change), historical entries have stale P&L
- If P&L formula changes (e.g., fees embedded), every entry is wrong
- Rebuilding from ledger gives different results than stored values

**Current risk**: LOW (LOT_SIZE_BTC is unlikely to change mid-session). But violates the principle.

**Fix**: Remove `pnl` field from ledger entries. `compute_realized_pnl()` should compute on-the-fly:
```python
sum((e['entry_premium'] - e['close_premium']) * e['lots'] * LOT_SIZE_BTC for e in ledger)
```

---

### ARCH-3: Migration Creates Synthetic Entries That Pollute Ledger

**Problem**: `_migrate_existing_pnl()` creates entries with:
```python
'symbol': 'MIGRATION', 'lots': 0, 'entry_premium': 0, 'close_premium': 0
```
These are not real fills. Any code that tries to:
- Count fills by symbol → wrong
- Validate lot integrity (closed ≤ opened) → confused
- Reconstruct position history → broken
- Export trade log → polluted

**Fix**: Migration entries should be clearly separated — either in `session['_fill_ledger_migration']` (separate list) or all read functions should have `exclude_migration=True` option and all validation must skip `_is_migration` entries.

---

### ARCH-4: No Position Integrity Validation

**Problem**: Nothing prevents closing more lots than were ever opened. The ledger happily records:
- Open: 50 lots CE
- Close: 100 lots CE (via multiple events)

No invariant check exists. `record_close()` does not validate against open positions.

**Fix**: Add optional validation in `record_close()`:
```python
def record_close(..., validate_lots=True):
    if validate_lots:
        open_lots = count_open_lots(session, side, strike)
        closed_lots = count_closed_lots_in_ledger(session, side, strike)
        if closed_lots + lots > open_lots:
            log.error("LOT INTEGRITY VIOLATION: ...")
            flag_discrepancy(...)
```

---

### ARCH-5: Perp Hedge P&L Lives Outside the Ledger

**Problem**: Perp hedge realized P&L is stored at `session['perp_hedge']['realized_pnl']` (line 370 of mmm_perp_hedge.py). Perp fees are written directly to `session['total_fees']`. Neither goes through the ledger.

`get_pnl()` returns options-only P&L. The monitor adds `session['pnl_perp']` as a separate attribution field at line 2772. But `net_pnl` from `get_pnl()` does NOT include perp P&L.

**Current risk**: MEDIUM. The frontend may or may not add perp P&L to the displayed total. If it doesn't, total P&L shown to user is incomplete.

**Fix**: Either (a) add `record_perp_fill()` to pnl_core with `source='perp_hedge'` and include in all computations, or (b) explicitly document that `get_pnl()` is options-only and ensure all callers add perp P&L separately.

---

## 🧠 DESIGN VIOLATIONS

### DV-1: Uninitialized MMMEngine Hack in get_pnl()

**Location**: `mmm_pnl_core.py:458-459`
```python
engine = MMMEngine.__new__(MMMEngine)
unrealized = engine.compute_unrealized_pnl(session, fetch_premium_fn)
```

`MMMEngine.__new__()` creates an instance WITHOUT calling `__init__()`. If `compute_unrealized_pnl()` ever accesses `self.executor`, `self.initializer`, or any instance attribute → **AttributeError crash in production**.

This is a ticking time bomb. Any future change to MMMEngine that adds instance-level logic to `compute_unrealized_pnl` will cause a runtime crash.

**Fix**: Extract `compute_unrealized_pnl` as a standalone function in `mmm_pnl_core.py` or make it a `@staticmethod` on MMMEngine.

---

### DV-2: No Ledger Immutability Enforcement

**Problem**: The ledger is a plain Python list. Any code with a reference can mutate it:
```python
ledger = session['_fill_ledger']
ledger.append(...)  # anyone can do this
ledger[0]['pnl'] = 999  # anyone can corrupt
```

The recycler already does this (ARCH-1). Nothing prevents other code from doing the same.

**Fix**: All mutations must go through pnl_core functions. At minimum, add a validation step in `_sync_session_fields` that checksums the ledger and logs if unexpected mutations occurred.

---

### DV-3: Reconciliation Bypass Risk

`flag_discrepancy()` is read-only — good. But `_auto_correct_missing_positions()` in mmm_monitor.py was made read-only by removing P&L booking. **However**, the position is still marked as closed:
```python
pos['status'] = 'closed'
```

If the position was NOT actually closed on the exchange (false positive from API lag), we just silently deleted it from our tracking. The position continues to exist on the exchange, accumulating P&L we don't see.

**Fix**: The `_pending_close_verification` grace mechanism should also apply here. Don't mark closed immediately — flag for human review.

---

## 🛠️ REQUIRED FIXES (Priority Order)

### FIX-1: Add `record_fee()` to mmm_pnl_core.py (CRIT-1)

```python
def record_fee(
    session: Dict,
    commission: float,
    source: str,
    order_id: str = '',
    symbol: str = '',
    side: str = '',      # 'sell' or 'buy' or 'perp'
) -> str:
    """Record a fee/commission event (sell-side, perp hedge, etc.)"""
    ledger = _ensure_ledger(session)
    entry_id = str(uuid.uuid4())[:12]
    ledger.append({
        'id': entry_id,
        'fill_id': None,
        'order_id': str(order_id),
        'symbol': symbol,
        'option_side': side,
        'strike': 0,
        'lots': 0,
        'entry_premium': 0,
        'close_premium': 0,
        'commission': abs(float(commission)),
        'pnl': 0,                    # fee-only entry, no P&L
        'source': source,
        'confirmed': True,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'position_id': '',
        '_is_fee_only': True,
    })
    _sync_session_fields(session)
    return entry_id
```

Then replace ALL 10 direct `session['total_fees'] +=` writes with `pnl_core.record_fee()`.

### FIX-2: Fix recycler to use pnl_core API (ARCH-1)

Add `rollback_closes_since(session, snapshot_len)` to pnl_core. Replace recycler's direct ledger manipulation.

### FIX-3: Extract unrealized P&L computation (DV-1)

Move `compute_unrealized_pnl` logic into pnl_core as a standalone function. Remove `MMMEngine.__new__` hack.

### FIX-4: Add estimate staleness tracking (CRIT-3)

After record_close with confirmed=False, if not confirmed within N heartbeats, emit warning.

### FIX-5: Separate migration entries (ARCH-3)

Add `exclude_migration` filter to all compute functions (default: False for backward compat, True for export/validation).

---

## 🧪 TEST CASES REQUIRED

### TC-1: Sell Fee Preservation
```
1. Create session, sell 100 lots (fee=$4)
2. Close 10 lots (fee=$0.30)
3. Assert session['total_fees'] == $4.30 (not $0.30)
```

### TC-2: Multiple Sell + Close Cycle
```
1. Sell 100 lots (fee=$4)
2. Close 20 lots (fee=$0.60)
3. Scale-up sell 50 more lots (fee=$2)
4. Close 30 lots (fee=$0.90)
5. Assert session['total_fees'] == $7.50
```

### TC-3: Max Loss With Correct Fees
```
1. Session with max_loss=$100
2. Sell fees=$50, close fees=$10
3. realized_pnl=-$50, unrealized=-$10
4. net_pnl = -50 + (-10) - 60 = -$120
5. Assert max_loss triggers (it won't with fee=$10 only → net=-$70)
```

### TC-4: Storage Correction Not Overwritten
```
1. Create session with double-booked P&L
2. Run storage correction → realized_pnl decreases by $5
3. Trigger a close event → _sync_session_fields runs
4. Assert realized_pnl still reflects the $5 correction
```

### TC-5: Recycler Rollback Via API
```
1. Phase A closes 3 positions (3 ledger entries)
2. Phase B fails
3. Assert all 3 entries removed via rollback_closes_since()
4. Assert session P&L matches pre-Phase-A state
```

### TC-6: Estimate Staleness
```
1. record_close(confirmed=False) with timestamp T
2. 15 minutes pass, no confirm_fill
3. Assert warning/flag raised
```

### TC-7: Perp Fee Not Lost
```
1. Open perp hedge (fee=$1.50)
2. Close options position
3. Assert total_fees includes perp $1.50
```

---

## SUMMARY

| Category | Count | Severity |
|----------|-------|----------|
| 🚨 Critical Flaws | 3 | P0-P1 |
| ⚠️ Architectural Weaknesses | 5 | Medium |
| 🧠 Design Violations | 3 | Low-Medium |
| 🛠️ Required Fixes | 5 | - |
| 🧪 Test Cases | 7 | - |

**Bottom line**: The ledger architecture is correct in principle but the implementation is INCOMPLETE. The biggest gap is that **only close/buyback events go through the ledger** while **sell-side fees bypass it entirely**, creating a systematic fee-loss bug that affects max-loss safety. This must be fixed before production.
