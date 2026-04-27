# PHASE 03 — P&L Truth Audit
**Lead Agent:** P&L Truth Agent
**Status:** COMPLETE
**Date:** 2026-04-26
**Prior Phases Read:** Phase 01 Architecture Audit, Phase 02 Accounting Audit

---

## Executive Summary

The P&L system in `mmm_pnl_core.py` is well-architected. It has a single canonical formula (`compute_current_total_pnl`), a sealed `record_close` path, and correct reverse/perp P&L inclusion. The primary risk is that `compute_current_total_pnl()` reads from **session cache fields**, not directly from the ledger — meaning if the heartbeat fails to update `unrealized_pnl` (e.g., premium fetch fails), the max-loss check uses a stale unrealized value. A second risk is the stopped-session display path which still depends on the `_fill_ledger` being loaded (partially fixed in rev9 via caching, but edge cases remain).

**P&L Architecture Grade: A-** — canonical formula is correct and sealed; cache dependency is the main structural weakness.

---

## 1. The Three P&L Components

| Component | Source | How Updated |
|---|---|---|
| `realized_pnl` | `session['_fill_ledger']` | `_sync_session_fields()` after every `record_close()` / `confirm_fill()` |
| `unrealized_pnl` | Live option premiums | `compute_unrealized_pnl(fetch_premium_fn)` — called from heartbeat |
| `total_fees` | `session['_fill_ledger']` | `_sync_session_fields()` after every `record_fee()` / `record_close()` |
| `perp_pnl` | `session['perp_hedge']` | Updated by perp hedge module |
| `reverse_pnl` | `session['_reverse']['net_pnl']` | Updated by mmm_reverse.py |

---

## 2. Canonical Formula — Verified

```python
@sealed
def compute_current_total_pnl(session: Dict) -> float:
    realized = session.get('realized_pnl', 0.0)      # from ledger cache
    unrealized = session.get('unrealized_pnl', 0.0)   # from live premium cache
    fees = session.get('total_fees', 0.0)              # from ledger cache
    perp_pnl = perp.realized + perp.unrealized         # from perp_hedge dict
    reverse_pnl = session['_reverse']['net_pnl']       # isolated reverse state
    return realized + unrealized - fees + perp_pnl + reverse_pnl
```

**Formula Verification:**
- Signs: `+realized` ✓ (positive = profit from closes), `+unrealized` ✓ (positive = options decayed below entry), `-fees` ✓ (fees reduce P&L), `+perp_pnl` ✓, `+reverse_pnl` ✓
- Reverse P&L included: **YES** (verified — invariant from CLAUDE.md preserved)
- Perp P&L included: **YES** (previously omitted — H-1 fix verified)
- Sealed: **YES** — regression-locked

**Finding A3-01 (P1):** `compute_current_total_pnl()` reads `session['unrealized_pnl']` from the **session cache**, not from live option prices. `_sync_session_fields()` does **NOT** update `unrealized_pnl` — it only updates `realized_pnl`, `total_fees`, and attribution buckets.

This means: if a heartbeat's premium fetch fails (network timeout, API error) and the heartbeat does not update `session['unrealized_pnl']`, the max loss check runs against a potentially **stale unrealized value**. The check may pass when actual P&L already breached the limit.

**How often is unrealized_pnl updated?** During every heartbeat's price fetch + P&L compute step. If the heartbeat completes successfully, unrealized_pnl is current. Under failure conditions (premium fetch errors), it may be up to several intervals stale.

---

## 3. P&L Formula Per Close

```python
pnl_per_close = (entry_premium - close_premium) * lots * LOT_SIZE_BTC
```

**Derivation check:**
- Short seller's P&L on buyback: sell at `entry_premium`, buy at `close_premium`
- P&L = (sell_price - buy_price) × lots × lot_size_in_BTC
- If `entry_premium > close_premium`: option decayed → **profit** ✓
- If `entry_premium < close_premium`: option expanded → **loss** ✓

LOT_SIZE_BTC = 0.001 (verified from `mmm_constants.py`)

**Finding A3-02 (P3 — positive):** Formula is mathematically correct. Decimal arithmetic used in pnl_core (`_D = Decimal` alias) prevents IEEE 754 accumulation.

**Finding A3-03 (P2):** `_D` is defined differently across modules:
- `mmm_pnl_core.py`: `_D = Decimal` (type alias)
- `mmm_constants.py`: `def _D(x) -> Decimal: return Decimal(str(x))` (helper)
- `mmm_engine.py`: `def _D(x) -> Decimal: return Decimal(str(x))` (helper)
- `mmm_straddle_adjustment.py`: `def _D(x): ...` (helper)
- `mmm_straddle_roll_pure.py`: `def _D(x): ...` (helper)

In pnl_core: `_D(str(x))` produces `Decimal(str(x))` — same result as the helper. No functional difference but five independent definitions means a precision bug fix would need to be made in five places.

---

## 4. _sync_session_fields() Analysis

```python
def _sync_session_fields(session: Dict) -> None:
    session['realized_pnl'] = round(compute_realized_pnl(session), 8)
    session['total_fees'] = round(compute_fees(session), 8)
    attr = compute_attribution(session)
    for key, value in attr.items():
        if value != 0 or key in session:
            session[key] = value
```

- Updates `realized_pnl` from ledger sum ✓
- Updates `total_fees` from ledger commission sum ✓
- Updates attribution buckets ✓
- Does **NOT** update `unrealized_pnl` — this is by design (requires live prices)
- Called after every `record_close()`, `confirm_fill()`, `record_fee()`, `rollback_close()`, `rollback_closes_since()` ✓

**Finding A3-04 (P2):** Attribution bucket updates use `if value != 0 or key in session`. This means:
- If `pnl_harvest` was $50 before, then all harvest positions are closed and `pnl_harvest` becomes $0, it will NOT be zeroed out (key is already in session, 0 value → condition fails). This is a bug: `pnl_harvest` persists as $50 even after correct ledger state shows $0.

Wait — re-reading: `if value != 0 or key in session` → sets if value is non-zero OR key already exists. If value is 0 AND key already in session → True → sets to 0. If value is 0 AND key NOT in session → False → does not add. So it would zero out existing keys. **Not a bug.**

**Correction to A3-04:** The condition is correct. Attribution zeroing works properly.

---

## 5. Gross vs Net Premium

The rev9 fix addressed this gap. Current state:

**Gross premium:** `session['total_premium_collected']` — only accumulates on sells, never decremented.
**Net premium:** `compute_net_premium(session)` — subtracts buyback costs from `_fill_ledger`.

`compute_net_premium()` reads `_fill_ledger` directly (not session cache). If `_fill_ledger` is empty (stopped session loaded without fill ledger), returns gross.

**Fix (rev9):** Heartbeat caches `_net_premium_collected`, `_ce_net_premium`, `_pe_net_premium` in session on each heartbeat. `list_session_summaries` reads these cached values. `_overlay_live_pnl` for stopped sessions uses cached values instead of re-computing from empty ledger.

**Finding A3-05 (P2):** The rev9 fix assumes the heartbeat has run at least once before the session is stopped. If a session is stopped immediately on the first heartbeat (or before the first heartbeat writes the net premium cache), the stopped session display will show gross premium.

Verified affected path: session stopped programmatically (kill switch) before first heartbeat completes. This is a narrow edge case.

---

## 6. Fee Accounting

`record_fee()` is the canonical path for sell-side and perp fees. The CRIT-1 fix ensures sell-side fees are recorded in the ledger (not just written directly to `session['total_fees']` which would be wiped on the next `_sync_session_fields()` call).

**Finding A3-06 (P2):** `record_fee()` has dedup by `order_id` for fee-only entries. But sell orders on the exchange may generate fees that arrive via fill_sync or WS executions. If the same order's fees are recorded BOTH by `record_fee()` (when the order is placed) AND by `confirm_fill()` (when the fill arrives), the fee could be double-counted.

The dedup in `record_fee()` checks `_is_fee_only` + `order_id`. The `confirm_fill()` path updates the commission field of the ESTIMATE entry, which is not a `_is_fee_only` entry. So `record_fee()` and `confirm_fill()` update different ledger entries — **no double-count**.

However: if `record_fee()` is called for a sell order, then `confirm_fill()` is called for the buyback of a DIFFERENT order that happens to have the same `order_id` (collision), `confirm_fill()` would update the wrong entry. Extremely unlikely given UUIDs, but the `order_id` uniqueness depends on the exchange and our client_order_id generation.

---

## 7. Recycler Rollback

The recycler can fail after Phase A (close positions) but before Phase B (re-enter). `rollback_closes_since()` is the recovery path.

**Finding A3-07 (P2):** `rollback_closes_since()` can only remove UNCONFIRMED entries. If Phase A fills were confirmed by fill_sync between the close and the Phase B failure, the rollback is incomplete. A `flag_discrepancy()` is issued and "P&L may be overstated. Human review required." is logged. This is correct — no silent failure. But it means recycler failure with confirmed Phase A fills leaves the session in an inconsistent state that requires manual resolution.

---

## 8. Live vs Stopped Session P&L Display Path

| Path | Formula Used | Notes |
|---|---|---|
| Live session (WebSocket) | `emit_pnl_update` → heartbeat-computed fields | Live, updated each heartbeat |
| Live session (REST) | `_overlay_live_pnl` → session cache | Reads from in-memory session dict |
| Stopped session (REST) | `_overlay_live_pnl` stopped path → cached fields | Reads `_net_premium_collected` etc. |
| Session list summary | `list_session_summaries` SQL + cached values | Rev9 fix: reads DB-persisted cache |

**Finding A3-08 (P1):** `compute_current_total_pnl()` (the safety formula) and `get_pnl()` (the display formula) compute slightly different numbers:

- `compute_current_total_pnl()`: `realized + unrealized_cache - fees + perp + reverse`
- `get_pnl()`: `realized_ledger + unrealized_live - fees_ledger + perp + reverse`

The difference: `get_pnl()` recomputes fees and realized from the ledger on every call. `compute_current_total_pnl()` reads from cache. If `_sync_session_fields()` was called after the last ledger mutation, they should agree. But if there's a timing gap (ledger mutated by fill_sync between heartbeat P&L update and max_loss check), they may diverge by the amount of the fill.

**This is a structural issue:** the safety check formula and the display formula use different data sources (cache vs live ledger), creating a window where the safety check may use a value that differs from what the operator sees on screen.

---

## 9. Unconfirmed Estimate Staleness

`check_stale_estimates()` detects unconfirmed ledger entries older than `max_age_minutes` (default 10). These are close orders that were placed but fill_sync hasn't confirmed them yet.

Stale estimates are logged and reported but do NOT trigger an action. The `realized_pnl` includes unconfirmed P&L (estimated at order placement time). If the actual fill price differs significantly from the estimate, `realize_pnl` will be wrong until `confirm_fill()` corrects it.

**Finding A3-09 (P2):** Stale estimate detection is read-only and advisory. There is no automatic action (no pause, no alert to operator) for stale estimates. An operator could have a position "closed" in their mind (estimate recorded, shown as profit) while the actual close order never filled. The estimate remains in the P&L indefinitely.

---

## 10. Architecture Issues — Phase 3 Entries

| ID | Problem | Risk | Priority |
|---|---|---|---|
| A3-01 | compute_current_total_pnl reads unrealized from cache — stale under premium fetch failure | Max loss may not fire if unrealized_pnl is stale-positive | P1 |
| A3-03 | _D() defined 5 times across 5 modules | Precision bug fix requires 5 file updates | P2 |
| A3-05 | Net premium cache unpopulated if session stopped before first heartbeat | Stopped session shows gross premium | P2 |
| A3-08 | Safety check formula (cache) vs display formula (ledger) use different data sources | Operator sees different number than safety check uses | P1 |
| A3-09 | Stale estimates are advisory only — no automatic action | Close order may not have filled but P&L shows as realized | P2 |

---

## 11. Positive Findings

1. **`compute_current_total_pnl()` is @sealed** — regression-locked
2. **Reverse P&L correctly included** — `session['_reverse']['net_pnl']` in formula (CLAUDE.md invariant preserved)
3. **Perp P&L correctly included** — H-1 fix verified
4. **`record_close()` is @sealed** — close path regression-locked
5. **`confirm_fill()` correctly corrects estimates** — two-pass model (estimate → confirmed) works correctly
6. **CRIT-1 fix prevents fee wipe** — sell-side fees go through `record_fee()` into ledger, not direct session write
7. **Recycler rollback correctly flags confirmed entries** — `rollback_closes_since()` notifies on incomplete rollback
8. **Migration path is correct** — old sessions get their P&L bootstrapped into the ledger
9. **Rev9 net premium fix is in place** — stopped sessions read cached values

---

## 12. Pass Criteria Checklist

- [x] Formula verification table produced (Sections 2, 3)
- [x] Reverse P&L inclusion verified (Section 2)
- [x] Fee calculation verified (Section 6)
- [x] Gross/net premium distinction confirmed (Section 5)
- [x] Live vs stopped session path divergence documented (Section 8)
- [x] Stale unrealized cache risk documented (A3-01)
- [x] Architecture Issue Register updated (Section 10)

**Phase 3 Status: PASSED. Two P1 issues require attention before capital scaling.**
