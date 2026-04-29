# Options Position Tracking — Full Fix Plan

**Created**: 2026-04-29  
**Status**: Phase 1 complete — Phase 2 next  
**Branch**: SSR

---

## The Problem (One Line)

Three unsynchronized sources of truth — frontend localStorage, backend WS cache, backend JSON store — cause positions to vanish, PnL to be wrong, and dismissed rows to reappear on reload.

---

## Requirements

| # | Requirement |
|---|---|
| R1 | All open positions for a given expiry are visible on the dashboard |
| R2 | When quantity added/subtracted on a strike, true cumulative P&L is maintained |
| R3 | When a strike is squared off (size→0, manual or algo), it stays visible with correct P&L |
| R4 | No strike vanishes from the table until expiry date |

---

## Audit Summary — All Gaps

| ID | Layer | File | Severity | Description |
|---|---|---|---|---|
| GAP-1 | Backend | options_ws_cache.py:289 | HIGH | Realized PnL at close uses unrealized_pnl which may be 0 if mark unavailable; fallback formula gives 0 |
| GAP-2 | Backend | closed_position_store.py:142 | MED | No idempotence key on record_close(); rapid duplicate calls double-count cumulative PnL |
| GAP-3 | Backend | closed_position_store.py:227 | MED | Phantom exclude_symbols computed after live fetch; race condition drops phantoms |
| GAP-4 | Backend | closed_position_store.py:71 | HIGH | _seen dict and _data dict are separate; stale seen entries pre-populate _prev_positions and trigger false double-detects |
| **GAP-5** | **Backend** | **options_ws_cache.py:317** | **CRITICAL** | **_prev_positions snapshotted BEFORE _positions is updated → always one cycle behind; first close after startup always missed** |
| **GAP-6** | **Backend** | **options_ws_cache.py:308** | **HIGH** | **Size=0 filtered before snapshot; re-entry (size=0→>0→0) second close not detected** |
| GAP-7 | Backend | options_ws_cache.py:319 | MED | WS mark-price merge only runs for live _positions; closed phantoms never get fresh marks |
| GAP-8 | Backend | options_ws_cache.py:237 | MED | 3s fill-refresh cooldown skips rapid fills in scalping scenarios |
| GAP-9 | Backend | options_ws_cache.py:236 | MED | Failed fill-triggered refresh doesn't reset cooldown; stays stale for full 3s |
| GAP-10 | Backend | dashboard.py:207 | MED | live_symbols computed before phantom merge; position closed mid-request excluded from display |
| GAP-11 | Backend | dashboard.py:216 | LOW | Greeks calculated before phantom merge; temporary mismatch |
| GAP-12 | Backend | dashboard.py:222 | MED | Content hash includes is_closed but frontend sets that during render; hash never stabilises |
| GAP-13 | Backend | dashboard.py:150 | MED | _refresh_in_progress has no timeout; hung thread blocks future refreshes forever |
| GAP-14 | Frontend | useOptionsPositions.js:135 | HIGH | lastModifiedRef doesn't update when only a new phantom is added; poll skips state update (compounds GAP-12) |
| GAP-15 | Frontend | useOptionsPositions.js:491 | LOW | applyTickerUpdate called for is_closed rows; filtered but wasteful |
| GAP-16 | Frontend | useOptionsPositions.js:159 | LOW | IV enrichment updates positions state async; flicker if data changes during IV fetch |
| **GAP-24** | **Frontend** | **OptionsPanel.js:457** | **CRITICAL** | **dismissedSymbols is in-memory only — resets on reload, dismissed positions reappear (breaks R4)** |
| **GAP-25** | **Frontend** | **OptionsPanel.js:1299** | **HIGH** | **Backend phantoms (is_closed=True from API) are NOT added to closedPositions localStorage; lost on reload** |
| **GAP-26** | **Frontend** | **OptionsPanel.js:1337** | **HIGH** | **Backend phantom + frontend localStorage entry can coexist; double row + double PnL in payoff graph** |
| **GAP-27** | **Frontend** | **OptionsPanel.js:1957** | **HIGH** | **Disappearance detection adds to closedPositions even when API already returned is_closed phantom → duplicate** |
| **GAP-28** | **Frontend** | **OptionsPanel.js:2034** | **HIGH** | **Partial exit PnL uses stale bid/ask as exit price, not actual fill price; PnL wrong by design (breaks R2)** |
| GAP-29 | Frontend | OptionsPanel.js:2034 | MED | Partial exit price uses midpoint, not trade-side-aware; biased for profitable exits |
| GAP-30 | Frontend | OptionsPanel.js:1945 | LOW | prevPositionsRef compared by reference, not content; O(n²) every render |
| GAP-31 | Frontend | OptionsPanel.js:1966 | MED | Disappeared position overwrites existing closedPositions entry; prior close PnL lost |
| GAP-32 | Frontend | OptionsPanel.js:1836 | MED | Re-entry PnL transfer assumes one-way; second close logic diverges from confirmClose |
| GAP-33 | Frontend | OptionsPanel.js:2454 | MED | React state batching; partialRealizedPnl clear and closedPositions set may render in wrong order, briefly double-counts |
| GAP-34 | Frontend | OptionsPanel.js:466 | LOW | Manual PnL never added to PnL column; payoff graph and column have different baselines |
| GAP-35 | Frontend | PositionRow.js:669 | MED | realized_pnl field ignored; relies on fragile unrealized=realized transfer in OptionsPanel |
| GAP-36 | Frontend | PositionRow.js:700 | LOW | Closed position % return never shown; only "Realized" label with no number |
| **GAP-40** | **Backend** | **seen_positions.json** | **MED** | **No expiry_ts per entry; expired symbols accumulate forever, pre-populate _prev_positions perpetually** |
| GAP-41 | Cross | Multiple | HIGH | closedPositions (localStorage) and backend phantoms conflict; duplication (see GAP-26) |
| **GAP-42** | **Cross** | **Multiple** | **HIGH** | **partialRealizedPnl (frontend) never reconciled with backend cumulative_realized_pnl; double-count on re-entry (breaks R2)** |
| GAP-43 | Cross | Multiple | HIGH | dismissedSymbols (in-memory) vs backend dismiss (async) can diverge; re-appear on reload |
| GAP-44 | Cross | Multiple | HIGH | Position closure not atomic across frontend + backend; timing-dependent duplication |

---

## Architecture Decision: Backend = Single Source of Truth

The root cause is having three sources. The fix is collapsing to one:

```
Exchange REST API
       ↓
options_ws_cache.py   ← close detection, _prev_positions, realized_pnl from exchange
       ↓
closed_position_store.py  ← cumulative realized PnL, phantom rows, dismiss tracking
       ↓
/api/options/dashboard    ← single merged response (live + phantoms)
       ↓
useOptionsPositions.js    ← one setPositions() call, no local deduplication
       ↓
OptionsPanel.js           ← display only, no closedPositions or partialRealizedPnl localStorage
```

Frontend localStorage for position state will be **removed entirely** in Phase 2.

---

## Phase 1 — Fix Backend Close Detection

**Files**: `options_ws_cache.py`, `closed_position_store.py`  
**Risk**: Backend-only, no UI changes  
**Status**: ✅ COMPLETE (2026-04-29)

### P1-A — Fix `_prev_positions` snapshot order (CRITICAL, fixes GAP-5)

**Current (broken)**:
```python
new_positions = {symbol: p for p in all_pos if size > 0}

with self._lock:
    self._prev_positions = dict(self._positions)  # ← snapshots OLD state (prev-prev cycle)
    self._positions = new_positions
```

**Fixed**:
```python
new_positions = {symbol: p for p in all_pos if size > 0}

with self._lock:
    self._prev_positions = dict(new_positions)  # ← snapshots CURRENT for next cycle
    self._positions = new_positions
```

This single line change ensures:
- Refresh N: detects N-1→N closes correctly (using `_prev_positions` set at end of N-1)
- Refresh N+1: `_prev_positions` = N snapshot → detects N→N+1 closes correctly
- Re-entry (size=0→>0→0): after re-entry, size goes into `new_positions` → snapshotted → second close detected ✓
- No double-detection: after B closes, `_prev_positions = {A: 10}` (B excluded), so B is never re-detected

### P1-B — Store `realized_pnl` from exchange API (fixes GAP-1, partial)

In the `new_positions` build loop, add:
```python
p["realized_pnl"] = float(p.get("realized_pnl", 0) or 0)
```

In `record_seen_batch`, store `realized_pnl` too.

This makes the exchange's own cumulative realized PnL available in `_prev_positions` for close detection, so the close record is more accurate.

In close detection (where `store.record_close` is called), prefer the exchange's `realized_pnl`:
```python
# Exchange's realized_pnl = cumulative PnL from all partial exits of this position.
# unrealized_pnl = PnL on the final portion being closed right now.
# Together they give the true total realized PnL at close.
realized = float(prev_pos.get("realized_pnl", 0) or 0) + \
           float(prev_pos.get("unrealized_pnl", 0) or 0)
if realized == 0:
    # Fallback: manual calculation
    mark = float(prev_pos.get("mark_price", 0) or 0)
    entry = float(prev_pos.get("entry_price", 0) or 0)
    if mark == 0:
        mark = entry
    realized = (mark - entry) * prev_size * 0.001
```

### P1-C — Add `expiry_ts` to seen entries, purge expired (fixes GAP-40)

In `record_seen_batch`:
```python
self._seen[sym] = {
    ...
    'expiry_ts': _parse_expiry_ts(sym),   # Add this
    ...
}
```

In `_load_seen`, purge expired entries the same way `_purge_expired_unlocked` does for closed entries.

---

## Phase 2 — Frontend: Eliminate Parallel State (localStorage cleanup)

**Files**: `OptionsPanel.js`, `useOptionsPositions.js`  
**Risk**: Large state refactor — do AFTER Phase 1 is verified stable  
**Status**: ⬜ TODO

### P2-A — Remove `closedPositions` localStorage

- Delete the `usePersistedState('options_closed_positions', {})` state
- Delete the disappearance-detection `useEffect` (~lines 1929–2079)
- Delete the re-entry transfer effect (~lines 1836–1880)
- The `closedToShow` / `closedAsPositions` block in `sortedPositions` is replaced by backend phantoms already in `enrichedPositions`

### P2-B — Remove `partialRealizedPnl` localStorage

- The exchange's `realized_pnl` field (stored in `_prev_positions` via P1-B) flows through the API into the frontend
- Frontend shows `unrealized_pnl` + `realized_pnl` (both from the exchange, not estimated)
- Delete `usePersistedState('options_partial_realized_pnl', {})` state
- Delete all accumulation logic for `partialRealizedPnl`

### P2-C — Persist dismissals server-side only

- Remove `dismissedSymbols` in-memory state (GAP-24)
- The backend `dismiss()` removes from store; dismissed positions simply absent from next API poll
- No frontend state needed

### P2-D — Deduplication guard (transitional, remove when P2-A complete)

Until P2-A is done, add this guard in `sortedPositions`:
```javascript
// Don't add a frontend localStorage entry if the same symbol
// is already in enrichedPositions as a backend phantom (is_closed=True)
const backendPhantomSymbols = new Set(
  enrichedPositions.filter(p => p.is_closed).map(p => p.product_symbol)
);
const closedToShow = Object.values(closedPositions).filter(
  cp => !liveSymbols.has(cp.product_symbol) &&
        !dismissedSymbols.has(cp.product_symbol) &&
        !backendPhantomSymbols.has(cp.product_symbol)  // ← add this
);
```

---

## Phase 3 — Display Correctness

**Files**: `PositionRow.js`, `OptionsPanel.js`  
**Risk**: Low — display-only changes  
**Status**: ⬜ TODO

### P3-A — PnL column uses `realized_pnl` directly for closed rows

```javascript
// In PositionRow.js PnL cell:
const unrealizedPnl = Number(pos.unrealized_pnl) || 0;
const realizedPnl   = Number(pos.realized_pnl)   || 0;   // exchange field
const partialPnl    = Number(pos.partial_realized_pnl) || 0;
const totalPnl      = pos.is_closed
  ? realizedPnl                               // closed: show exchange's realized
  : unrealizedPnl + partialPnl;              // live: current + accumulated partials
```

### P3-B — Show % return on closed rows

```javascript
// Secondary caption for is_closed rows:
const entryPrice = Number(pos.entry_price) || 0;
const origSize   = Math.abs(Number(pos.original_size) || 0);
const cost       = entryPrice * origSize * 0.001;
const returnPct  = cost > 0 ? (realizedPnl / cost) * 100 : 0;
```

---

## Implementation Checklist

### Phase 1
- [x] P1-A: Change `_prev_positions = dict(self._positions)` → `_prev_positions = dict(new_positions)` in options_ws_cache.py
- [x] P1-B: Store `realized_pnl` from exchange in new_positions build loop
- [x] P1-B: Update close detection to use `realized_pnl + unrealized_pnl` as realized amount
- [x] P1-B: Store `realized_pnl` in `record_seen_batch`
- [x] P1-C: Add `expiry_ts` to each `_seen` entry in `record_seen_batch`
- [x] P1-C: Purge expired seen entries in `_load_seen`
- [x] Test: Restart backend — 3 phantoms detected (new one caught that old code missed)
- [x] Test: seen_positions.json has expiry_ts on all 51 entries, 0 missing

### Phase 2
- [ ] P2-D (deduplication guard) — safe to do with Phase 1
- [ ] P2-A: Remove closedPositions localStorage
- [ ] P2-B: Remove partialRealizedPnl localStorage
- [ ] P2-C: Remove dismissedSymbols in-memory state
- [ ] Frontend rebuild + smoke test

### Phase 3
- [ ] P3-A: PnL column direct realized_pnl for closed rows
- [ ] P3-B: % return on closed rows

---

## Key Invariants (Do Not Break)

1. `_prev_positions` must always equal the `new_positions` from the PREVIOUS refresh — never the positions from two cycles ago
2. Close detection fires only when `prev_size != 0 AND curr_size == 0` — never for re-entries or live positions
3. `cumulative_realized_pnl` in the store is additive — each close adds to it, never overwrites
4. Backend phantoms (`is_closed=True`) are the authoritative closed-position record — frontend localStorage is secondary cache only
5. The `applyTickerUpdate` WS handler must never touch positions where `is_closed=True` or `size=0`
