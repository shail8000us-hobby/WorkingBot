# MMM P&L System — Full Audit & Redesign Plan

> **Purpose**: Single reference for every P&L calculation, variable, bug, and code location in the MMM system.
> Read this before touching any P&L code. Redesign plan is at the bottom.
>
> **Date**: 2026-03-25
> **Status**: Audit complete. Redesign proposed. Not yet implemented.

---

## PART 1 — WHAT EXISTS TODAY

### 1.1 P&L Variables in Session State

All live in the session dict (`mmm_state.py` DEFAULT_PARAMS, updated at runtime).

| Variable | Type | What it tracks | Who writes it |
|---|---|---|---|
| `realized_pnl` | float | Cumulative closed P&L (USD) | close_at_5, fill_sync, recycler, harvester, reconciliation auto-correct, close_by_strike |
| `unrealized_pnl` | float | Mark-to-market on open positions (stale cache) | `compute_unrealized_pnl()` each heartbeat |
| `total_fees` | float | Cumulative exchange commission (USD) | fill_sync, close_by_strike |
| `net_pnl` | float or None | `realized + unrealized - fees` — only set at session stop | `stop_session()` in mmm_api.py |
| `peak_pnl` | float | High-water mark of net_pnl (15-min decay) | `update_peak_pnl()` in mmm_safety.py |
| `pnl_history` | list | [{timestamp, realized, unrealized, total_pnl}] snapshots | Heartbeat Step 8 |
| `total_premium_collected` | float | Sum of all sell premiums × lots (informational only) | Position creation; never updated |

**Attribution buckets** (must sum to `realized_pnl`):

| Variable | Tracks | Who writes it |
|---|---|---|
| `pnl_initial` | P&L from original entry position closes | fill_sync via `attr_key` |
| `pnl_adjustment` | P&L from adjustment position closes | fill_sync via `attr_key` |
| `pnl_harvest` | P&L from M1 profit harvesting | mmm_harvester → close_position |
| `pnl_recycle` | P&L from M2 lot recycling buybacks | mmm_recycler |
| `manual_reduction_pnl` | P&L from operator manual closes | close_by_strike in mmm_api |

**Invariant (currently broken)**: `pnl_initial + pnl_adjustment + pnl_harvest + pnl_recycle + manual_reduction_pnl == realized_pnl`

---

### 1.2 Per-Position P&L Fields

Live inside `session['ce']['positions'][]` and `session['pe']['positions'][]`.

| Field | What it does |
|---|---|
| `entry_premium` | Price per lot at sell time (the income we collected) |
| `realized_pnl` | Final booked P&L for this position (set once, by fill_sync) |
| `_estimated_pnl_booked` | Estimate booked to session at close-order-placement time (before fill confirms) |
| `_estimated_commission_booked` | Commission estimate at order placement |
| `_fill_confirmed` | True after fill_sync matched exchange fill to this position |
| `_being_closed` | True while close order in-flight (prevents double-close) |
| `close_order_id` | Exchange order_id for the BUY close order (used by fill_sync to match) |

---

### 1.3 Fill Sync State

| Field | What it does |
|---|---|
| `_fill_sync_cursor_us` | Microsecond timestamp — fills before this are already processed |
| `_fillsync_double_booking_corrected` | One-time flag: double-booking fix applied on load |
| `_fillsync_correction_amount` | USD amount of the double-booking correction |

---

## PART 2 — WHICH FILE DOES WHAT

### `mmm_engine.py`
**P&L responsibility**: Compute unrealized P&L only.

```
compute_unrealized_pnl(session, fetch_premium_fn) → float
  For every open position (active, adjustment, frozen):
    unrealized += (entry_premium - current_premium) × lots × 0.001
  Returns float. Does NOT touch realized_pnl.

compute_total_pnl(session, fetch_premium_fn) → Dict
  Returns {realized, unrealized, fees, net_pnl}
  Calls compute_unrealized_pnl internally.
```

**Problems**:
- Uses live prices fetched on-demand — stale if prices are unavailable
- `_pnl_calculation_incomplete` set if >50% of fetches fail, but caller still uses partial result

---

### `mmm_fill_sync.py`
**P&L responsibility**: The only place that books FINAL realized P&L based on actual exchange fills.

```
sync_fills(session, rest_client) → None
  Fetches all fills after _fill_sync_cursor_us from exchange
  For each BUY fill (close order):
    Matches fill.order_id to position.close_order_id
    pnl_correction = actual_fill_pnl - estimated_pnl_booked
    if abs(pnl_correction) > 1e-9:
      session['realized_pnl'] += pnl_correction
      session[attr_key] += pnl_correction  (pnl_initial or pnl_adjustment)
    session['total_fees'] += actual_commission
    position['_fill_confirmed'] = True
    position['realized_pnl'] = actual_pnl (final)
  Advances _fill_sync_cursor_us
```

**Problems**:
- Cursor can advance past fills before they are processed (on restart)
- Unmatched fills (no close_order_id match) are silently logged and skipped
- Attribution bucket (`attr_key`) is derived from position type — can be wrong if position was moved between adjustment/initial buckets
- If fill_sync never runs for a close (cursor advanced too far), the estimate stays as final

---

### `mmm_close_at_5.py`
**P&L responsibility**: Books an ESTIMATE of realized P&L when placing the close order.
This is NOT the final number — fill_sync corrects it later.

```
close_position(session, pos, close_price, ...) → order_id
  estimated_pnl = (entry_premium - close_price) × lots × 0.001
  session['realized_pnl'] += estimated_pnl          ← ESTIMATE (NOT actual fill)
  session[attr_key] += estimated_pnl
  pos['_estimated_pnl_booked'] = estimated_pnl
  pos['close_order_id'] = order_id
  pos['_being_closed'] = True
```

**Problems**:
- Uses bid/ask price at the moment of order — actual fill may be different
- If fill_sync never corrects (cursor issue), this estimate is permanent
- Commission is also estimated (flat calculation, not actual exchange fee)

---

### `mmm_monitor.py`
**P&L responsibility**: Orchestration — runs compute_unrealized_pnl each heartbeat,
calls update_peak_pnl, owns the reconciliation auto-correct.

```
compute_live_pnl(session_id) → Dict
  Gets fresh prices (WS cache, max 10s old)
  Calls engine.compute_total_pnl(session_snap, fresh_prices)
  Returns {realized, unrealized, fees, net_pnl}

_auto_correct_missing_positions(side_state, strike, reason, close_price)
  ← THE DANGEROUS FUNCTION
  When exchange shows 0 lots but session has lots:
    pnl = (entry_premium - close_price) × lots × 0.001
    session['realized_pnl'] += pnl        ← USES LIVE MARKET PRICE
    pos['status'] = 'closed'
    pos['_fill_confirmed'] = True          ← Blocks fill_sync from ever correcting
```

**The Core Problem** (what broke mmm25mar26-1):
`close_price` is set from `_last_good_ce` or `_last_good_pe` — the live market premium at reconciliation time.
If the position was already closed hours earlier at a different price, this invents a fake loss.
Line `pos['_fill_confirmed'] = True` then permanently blocks fill_sync from correcting it.

---

### `mmm_api.py`
**P&L responsibility**: REST API layer — overlays live P&L on responses, handles stop_session.

```
_overlay_live_pnl(sessions)
  For sessions with running monitors:
    live = compute_live_pnl(session_id)
    Replaces session['realized_pnl', 'unrealized_pnl', 'fees', 'net_pnl'] with live values

stop_session(session_id, reason) — 3-step race-free pattern:
  1. storage.update_session(STOPPED status)
  2. stop_session_monitor() → writes final R/U/F, sets _save_disabled=True
  3. storage.get_session() → read final R/U/F
     storage.update_session({'net_pnl': R + U - F})
```

**Problem**: `net_pnl` is only set at explicit stop. Auto-stop by close_at_5 or watchdog
goes through a different code path — session stops without going through stop_session() API —
leaving `net_pnl = None`.

---

### `mmm_safety.py`
**P&L responsibility**: Trailing stop via peak P&L.

```
update_peak_pnl(session, total_pnl)
  If total_pnl > current_peak: update peak
  Else: decay current_peak with 15-min half-life
        if total_pnl > decayed_peak: update to total_pnl
        else: update to decayed_peak
```

---

### `mmm_recycler.py`
**P&L responsibility**: Books P&L directly when M2 recycle buys back frozen lots.

```
execute_lot_recycling(session, side, ...) → None
  buyback_cost = current_premium × recycled_lots × 0.001
  session['realized_pnl'] += buyback_cost
  session['pnl_recycle'] += buyback_cost
```

**Problem**: Direct-books without going through fill_sync. If the buyback order fills
at a different price than estimated, no correction ever happens.

---

### `mmm_harvester.py`
**P&L responsibility**: M1 harvest close, delegates to `close_position()` from mmm_close_at_5.

```
scan_harvestable_positions(session, ...)
  For profitable frozen positions ≤ harvest_threshold:
    close_position(...) → books to pnl_harvest bucket
```

Same problems as close_at_5 (estimate, not actual fill).

---

### `mmm_storage.py`
**P&L responsibility**: Persist and recover session state. One-time double-booking fix on load.

```
save_session(session) → writes entire session dict to DB (JSON column)
get_session(session_id) → reads session dict
  On load: checks if double-booking correction needed
           subtracts over-booked _estimated_pnl_booked amounts from realized_pnl

update_session(session_id, fields) → surgical update (only specified fields)
```

---

### `MMMDashboard.js` + `MMMSessionCard.js`
**P&L responsibility**: Display.

```javascript
// MMMDashboard.js
const netPnl = fullSession?.net_pnl ?? (realizedPnl + unrealizedPnl - totalFees);

// MMMSessionCard.js
const netPnl = session.net_pnl ?? (realized + unrealized - fees);
```

Both use `net_pnl` if present, fall back to arithmetic if None.

---

## PART 3 — THE BUGS

### Bug A — Reconciliation invents P&L using market price (what hit mmm25mar26-1)
**File**: `mmm_monitor.py` → `_auto_correct_missing_positions()`
**What happens**: Exchange shows 0 lots. Bot uses live premium (`_last_good_ce`) as close price.
165 CE lots × (entry 74.5 - live price 240.5) × 0.001 = **-$27.26 invented loss**.
**Also**: Sets `_fill_confirmed = True` → fill_sync permanently blocked from correcting.
**Root cause**: Close price should come from the actual exchange fill, not live market price.

### Bug B — Auto-stop bypasses stop_session() API → net_pnl = None
**Files**: `mmm_monitor.py` (watchdog), `mmm_close_at_5.py` (strategy_complete path)
**What happens**: Session auto-stops ("Both sides fully closed") without calling the 3-step
stop_session pattern. `net_pnl` is never written. Frontend falls back to R+U-F calculation.

### Bug C — fill_sync cursor can skip fills on restart
**File**: `mmm_fill_sync.py`
**What happens**: Cursor records the newest fill seen. On watchdog restart, cursor resumes
from where it was. Any fills that happened WHILE the monitor was dead are replayed.
But if restart is clean and cursor already past those fills — they are silently lost.

### Bug D — Two-phase booking (estimate + correct) has a gap
**Files**: `mmm_close_at_5.py` (estimate), `mmm_fill_sync.py` (correction)
**What happens**: Close-at-5 books estimated P&L immediately. If fill_sync never runs
(cursor advanced, position missed), the estimate is the final number. The estimate uses
the price at order-placement time, not actual fill price.

### Bug E — Recycler and auto-correct bypass fill_sync entirely
**Files**: `mmm_recycler.py`, `mmm_monitor.py`
**What happens**: These paths book P&L directly to session without going through fill_sync.
No actual exchange fill confirmation. No correction mechanism.

### Bug F — pnl_initial always 0 (BUG-C1, fixed March 24 Session 1)
**File**: `mmm_monitor.py` `_straddle_credit_v2` path
**What happened**: Used `pos.get('original_lots')` instead of `pos.get('lots')`.
Attribution bucket wrong — all initial credit went to `pnl_adjustment`.
**Status**: Fixed. But the fix relies on a recompute flag and is fragile.

### Bug G — Attribution invariant silently broken
**All P&L files**
**What happens**: `pnl_initial + pnl_adjustment + pnl_harvest + pnl_recycle + manual_reduction_pnl`
is supposed to equal `realized_pnl`. No enforcement. The auto-correct path (Bug A)
only updates `realized_pnl`, not any attribution bucket — immediately breaks the invariant.

---

## PART 4 — ROOT CAUSE (ONE SENTENCE)

> **The system has no single ledger of actual fills. Instead it has 4+ paths that each write to realized_pnl independently, with only partial correction mechanisms, no enforcement of invariants, and a reconciliation that invents P&L by guessing at close prices.**

---

## PART 5 — REDESIGN PLAN

### Is this the institutional way?

Yes. This is how every professional trading system works — banks, hedge funds, prop desks.

The pattern has a name: **Trading Book + P&L Engine**.

| Institutional System | What it maps to here |
|---|---|
| **Trade Blotter** | Append-only fill ledger — every fill recorded once, never modified |
| **P&L Engine** | One file (`mmm_pnl_core.py`) that derives all P&L from the blotter |
| **OMS (Order Management)** | `mmm_executor.py`, `mmm_close_at_5.py` — places orders only, no P&L |
| **Reconciliation** | Read-only comparison vs exchange — alerts only, never writes P&L |
| **Mark-to-Market** | `compute_unrealized_pnl()` — only for open positions, never touches realized |

The reason institutional systems don't break on P&L:
- P&L is **never stored as a running total** that can drift
- P&L is **always recomputed from fills** — same answer every time
- No system writes P&L except the P&L engine
- Reconciliation **alerts humans** — it never auto-adjusts numbers

This is what we're building.

---

### Principle: Fills are the source of truth. Everything else is derived.

```
ACTUAL P&L = Σ (sell fills) - Σ (buy fills) per lot
           = Σ (entry_premium - close_premium) × lots × 0.001  for each closed lot
UNREALIZED  = Σ (entry_premium - live_premium) × lots × 0.001  for each open lot
NET P&L     = ACTUAL P&L - FEES
```

Nothing else. No estimation. No mark-to-market for realized. No guessing.

---

### The New Architecture: `mmm_pnl_core.py`

One file. All other files become **callers**, not **writers**.

```
mmm_close_at_5.py  ──┐
mmm_fill_sync.py   ──┤  record_fill()  ──►  mmm_pnl_core.py  ──►  session['_fill_ledger']
mmm_recycler.py    ──┤                            │
mmm_harvester.py   ──┘                            │  get_pnl()
                                                  ▼
mmm_monitor.py  ◄──────────────────────  {realized, unrealized, fees, net_pnl}
mmm_api.py      ◄──────────────────────
MMMDashboard    ◄──────────────────────

mmm_monitor.py (reconciliation)  ──►  flag_missing()  ──►  alert only, no P&L write
```

---

### Design: Single Fill Ledger

**New table/file**: `mmm_fill_ledger` (per session, append-only)

Every single order fill (sell or buy) gets one row:

```python
{
  'fill_id':       str,    # exchange fill_id (deduplication key)
  'order_id':      str,    # exchange order_id
  'symbol':        str,    # e.g. 'C-BTC-71000-250326'
  'side':          str,    # 'buy' or 'sell'
  'lots':          int,    # number of lots
  'price':         float,  # actual fill price from exchange
  'commission':    float,  # actual commission from exchange
  'timestamp_us':  int,    # fill timestamp microseconds
  'source':        str,    # 'initial_sell' | 'adjustment_sell' | 'close_buy' | 'external'
  'position_id':   str,    # which position this fill belongs to (nullable for external)
}
```

**P&L computation** (pure function, no side effects):

```python
def compute_realized_pnl(ledger: List[FillEntry]) -> float:
    """
    P&L = sum of all sell fills - sum of all buy fills, in USD.
    sell fills: income (positive)
    buy fills: cost (negative)
    """
    total = 0.0
    for fill in ledger:
        value = fill['price'] * fill['lots'] * LOT_SIZE_BTC
        if fill['side'] == 'sell':
            total += value
        else:
            total -= value
    return total

def compute_fees(ledger: List[FillEntry]) -> float:
    return sum(f['commission'] for f in ledger)

def compute_net_pnl(ledger: List[FillEntry]) -> float:
    return compute_realized_pnl(ledger) - compute_fees(ledger)
```

This is the ONLY place realized P&L is computed. It is always recomputed from the ledger.
The ledger is append-only and never modified after a fill is recorded.

---

### `mmm_pnl_core.py` — Full Interface

```python
class MMMPnlCore:
    """
    Single source of truth for P&L.
    ONLY this class reads or writes P&L state.
    All other MMM files call into this class.
    """

    # ── THE ONLY WRITE PATH ────────────────────────────────────────────────

    def record_fill(self, fill: dict) -> None:
        """
        Called by fill_sync when an exchange fill arrives.
        This is the ONLY place P&L state changes.

        fill = {
            'fill_id':      str,    # exchange fill ID — idempotency key
            'order_id':     str,    # exchange order ID
            'symbol':       str,    # 'C-BTC-71000-250326'
            'direction':    str,    # 'sell' | 'buy'
            'lots':         int,
            'price':        float,  # actual fill price from exchange
            'commission':   float,  # actual fee from exchange
            'timestamp_us': int,    # microsecond timestamp
            'source':       str,    # 'initial' | 'adjustment' | 'close' |
                                    # 'harvest' | 'recycle' | 'manual'
            'position_id':  str,    # which position this closes (nullable)
        }
        """

    # ── READ PATHS (pure functions, no side effects) ───────────────────────

    def compute_realized_pnl(self) -> float:
        """Sum of all sell fills minus all buy fills. Always correct."""

    def compute_fees(self) -> float:
        """Sum of all commissions from confirmed fills."""

    def compute_unrealized_pnl(self, fetch_price_fn) -> float:
        """Mark-to-market on all currently open positions."""

    def get_pnl(self, fetch_price_fn) -> dict:
        """
        The single P&L endpoint. Called by monitor, API, frontend.
        Returns:
        {
            'realized':   float,  # from ledger, always accurate
            'unrealized': float,  # mark-to-market on open positions
            'fees':       float,  # from ledger
            'net_pnl':    float,  # realized + unrealized - fees, never None
            'attribution': {      # derived from fill 'source' field
                'initial':    float,
                'adjustment': float,
                'harvest':    float,
                'recycle':    float,
                'manual':     float,
            }
        }
        """

    def get_peak_pnl(self) -> float:
        """High-water mark with 15-min decay. Derived, not stored."""

    # ── RECONCILIATION (read-only, never writes P&L) ───────────────────────

    def flag_missing_position(self, symbol: str, session_lots: int) -> None:
        """
        Called by reconciliation when exchange shows 0 but session has lots.
        Emits a SAFETY alert. Does NOT modify any P&L field.
        Human uses manual_close() to record what actually happened.
        """

    def manual_close(self, symbol: str, lots: int, actual_price: float,
                     actual_commission: float, source: str = 'manual') -> None:
        """
        Operator-confirmed close at a specific price.
        Records a buy fill at the given price. P&L updates automatically.
        """
```

---

### How Each Current System Maps to the New Design

| Current system | New design |
|---|---|
| `close_at_5` books estimated P&L | Places close order, records fill_id=PENDING. Does NOT touch P&L at all. |
| `fill_sync` corrects the estimate | Receives actual fill from exchange, appends to ledger with actual price. P&L auto-updates. |
| `reconciliation auto-correct` with market price | **REMOVED**. Reconciliation is read-only. If exchange shows 0 but no fill found → ALERT only, human decides. |
| `realized_pnl` field in session | **Derived**: `compute_realized_pnl(ledger)` on demand. Not stored (or stored as a cache). |
| `net_pnl = None` bug | **Impossible**: net_pnl is always `compute_net_pnl(ledger)`. No separate persistence path. |
| `pnl_initial/adjustment/harvest/recycle` attribution | Derived from ledger `source` field. Never stored separately. |
| Recycler/harvester direct-booking | Both go through place-order → fill-arrives → ledger-append. Same as everything else. |

---

### fill_sync becomes the ONLY writer to the ledger

```
Exchange fill arrives →
  fill_sync checks fill_id not already in ledger →
  Appends to ledger →
  P&L is now updated (derived from ledger) →
  Done.
```

No estimation. No correction. No two-phase booking.

---

### Unrealized P&L: unchanged concept, simpler code

```python
def compute_unrealized_pnl(open_positions, fetch_price_fn) -> float:
    total = 0.0
    for pos in open_positions:
        if pos['status'] != 'open':
            continue
        current = fetch_price_fn(pos['symbol'])
        if current is None:
            continue  # skip, don't fake it
        # We are SHORT (sold). Profit = entry higher than current.
        total += (pos['entry_price'] - current) * pos['lots'] * LOT_SIZE_BTC
    return total
```

---

### Reconciliation becomes READ-ONLY

```python
def reconcile(session, exchange_positions):
    """
    Compare what we think we have vs what exchange shows.
    NEVER modifies P&L. NEVER auto-closes positions.
    Only reports discrepancies.
    """
    discrepancies = []
    for pos in session.open_positions:
        exchange_size = exchange_positions.get(pos['symbol'], 0)
        if exchange_size != pos['lots']:
            discrepancies.append({
                'symbol': pos['symbol'],
                'session_lots': pos['lots'],
                'exchange_lots': exchange_size,
                'action_required': 'HUMAN_REVIEW',
            })
    emit_alert_if_any(discrepancies)
    return discrepancies  # never modifies session
```

If the position is really gone from exchange without a fill → human is notified,
human uses the "Manual Close" UI to record the actual close price and book the P&L.
The bot never guesses.

---

### net_pnl is always available — no None

Since P&L is derived from the ledger at any time:

```python
def get_session_pnl(session_id) -> Dict:
    ledger = load_fill_ledger(session_id)
    open_pos = load_open_positions(session_id)
    return {
        'realized':   compute_realized_pnl(ledger),
        'unrealized': compute_unrealized_pnl(open_pos, fetch_price),
        'fees':       compute_fees(ledger),
        'net_pnl':    compute_net_pnl(ledger),  # always a number, never None
    }
```

No separate persistence of `net_pnl`. No stop_session fix needed. No race condition.

---

## PART 6 — IMPLEMENTATION PHASES

### Phase 0 — Immediate hotfix (before redesign)
Stop the bleeding from Bug A without redesigning the whole system.

**Change in `mmm_monitor.py` `_auto_correct_missing_positions()`**:
```python
# CURRENT (WRONG):
_recon_close_price = float(self._last_good_ce or 0.0)  # live market price
self._auto_correct_missing_positions(side, strike, 'exchange_shows_zero', _recon_close_price)

# FIX:
# Do NOT auto-correct. Only alert.
emit_safety('POSITION_MISSING_FROM_EXCHANGE', ...)
log.warning(...)
# Human reviews and uses manual_close endpoint to record actual close price
```

Also: remove `pos['_fill_confirmed'] = True` from auto-correct so fill_sync
can still process any future fill for that position.

### Phase 1 — Fill Ledger
- Create `mmm_fill_ledger.py` with `append_fill()`, `compute_realized_pnl()`, `compute_fees()`
- Modify `mmm_fill_sync.py` to append to ledger instead of correcting session fields
- Modify `mmm_close_at_5.py` to NOT touch `realized_pnl` when placing close order
- Add `get_session_pnl()` as the single P&L computation endpoint

### Phase 2 — Remove estimate booking from close paths
- `mmm_close_at_5.py`: remove P&L booking from `close_position()`
- `mmm_recycler.py`: remove direct P&L booking, wait for fill_sync
- `mmm_harvester.py`: same as close_at_5

### Phase 3 — Make reconciliation read-only
- Remove `_auto_correct_missing_positions()` from auto-fire path
- Replace with `emit_recon_alert()` only
- Add "Confirm Manual Close" endpoint for human to record actual close price + P&L

### Phase 4 — Remove attribution buckets (or derive them)
- `pnl_initial`, `pnl_adjustment`, `pnl_harvest`, `pnl_recycle` become derived
  from ledger `source` field — not stored separately

### Phase 5 — Frontend
- Remove `net_pnl ?? (R + U - F)` fallback — `net_pnl` always set
- P&L display reads from single `get_session_pnl()` API

---

## PART 7 — FILES THAT NEED TO CHANGE

| File | What changes |
|---|---|
| `mmm_monitor.py` | Remove `_auto_correct_missing_positions()` P&L booking. Make reconciliation read-only. |
| `mmm_fill_sync.py` | Append to fill_ledger instead of correcting session fields. |
| `mmm_close_at_5.py` | Remove `session['realized_pnl'] +=` from close_position(). Just place order + mark pending. |
| `mmm_recycler.py` | Remove direct P&L booking. Wait for fill. |
| `mmm_harvester.py` | Same. |
| `mmm_api.py` | Remove `_overlay_live_pnl()`. Remove stop_session P&L persistence race fix. Add `get_session_pnl()`. |
| `mmm_engine.py` | Remove `compute_total_pnl()`. Keep `compute_unrealized_pnl()`. |
| `mmm_state.py` | Remove `realized_pnl`, `net_pnl`, `total_fees` from DEFAULT_PARAMS (they become derived). Keep `unrealized_pnl` as cache. |
| `mmm_storage.py` | Remove double-booking correction. Add `save_fill_ledger()` / `load_fill_ledger()`. |
| `MMMDashboard.js` | Remove `net_pnl ?? (R + U - F)` fallback. |
| `MMMSessionCard.js` | Same. |
| NEW: `mmm_fill_ledger.py` | Append-only fill ledger + P&L computation functions. |

---

## SUMMARY TABLE

| What | Current | Target |
|---|---|---|
| P&L source | Session fields written by 6 different paths | Fill ledger, append-only, written by fill_sync only |
| Estimate booking | close_at_5 books estimate; fill_sync corrects | No estimate. P&L only when fill confirmed. |
| Reconciliation | Auto-corrects P&L using live market price | Read-only. Alert only. Human books actual close. |
| net_pnl | None until stop_session called explicitly | Always derived from ledger, always a number |
| Attribution | 5 separate stored buckets, can drift | Derived from `source` field in ledger entries |
| Testing | Test corrects post-hoc | Test the ledger math directly (pure functions) |

