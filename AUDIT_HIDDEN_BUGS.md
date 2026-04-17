# AUDIT_HIDDEN_BUGS.md

## Executive Summary

Audit mode only (no code changes were made).

I found **5 high-confidence hidden bugs/design risks** in MMM runtime paths, including **2 critical (P0)** issues that can create exchange/session divergence and untracked exposure.

Top risks are concentrated in:
- reverse close handling (`mmm_reverse.py`)
- hard-stop market close path (`mmm_close_at_5.py`)
- unsafe boolean coercion of operator/API inputs (`mmm_api.py`, `mmm_monitor.py`)

---

## Files Audited

Primary files inspected in this audit:
- `webui/backend/routes/mmm/mmm_api.py`
- `webui/backend/routes/mmm/mmm_monitor.py`
- `webui/backend/routes/mmm/mmm_reverse.py`
- `webui/backend/routes/mmm/mmm_close_at_5.py`
- `webui/backend/routes/mmm/mmm_executor.py`
- `webui/backend/routes/mmm/mmm_pnl_core.py`
- `webui/backend/routes/mmm/mmm_watchdog.py`
- `webui/backend/routes/mmm/mmm_storage.py`
- `webui/backend/routes/mmm/mmm_safety.py`
- `webui/backend/routes/mmm/mmm_guardian.py`
- `webui/backend/routes/mmm/mmm_regime.py`
- `webui/backend/routes/mmm/mmm_perp_hedge.py`
- `webui/backend/routes/mmm/mmm_recycler.py`
- `webui/backend/routes/mmm/mmm_wind_down.py`
- `webui/backend/routes/mmm/mmm_engine.py`
- `webui/backend/routes/mmm/mmm_strategy_dispatch.py`
- `MMM_LAST_3_SESSIONS.md`

---

## Findings

### F1 — Reverse partial close is finalized as full close (state divergence)

- **Severity:** **P0 (Critical)**
- **Confidence:** High
- **Category:** partial update, stale state, wrong reset
- **Evidence:**
  - `mmm_reverse.py:571` → `close_filled = result.get('filled_size') or lots`
  - `mmm_reverse.py:597` → `pos['status'] = 'closed'`
  - `mmm_reverse.py:606` → `rev['total_lots'] = max(0, rev.get('total_lots', 0) - lots)`

**Bug:** even when `close_filled < lots` (partial fill), the position is marked fully closed and total lots are reduced by requested `lots` (not actual filled).

**Why It Matters:**
- Leaves residual short lots on exchange while session says closed.
- Can bypass max-loss/exposure logic because internal lots are understated.
- Creates reconciliation and risk-control blindness during fast markets.

**Suggested Fix:**
- Treat partial close like core logic does: keep position open with remaining lots.
- Decrement reverse totals by `close_filled` only.
- If fully filled, then mark `status='closed'`; otherwise store residual and retry path.

---

### F2 — Reverse close ledger call uses wrong `record_close()` signature (silently skipped accounting)

- **Severity:** **P1 (High)**
- **Confidence:** High
- **Category:** wrong call contract, silent skip
- **Evidence:**
  - `mmm_reverse.py:582` calls `_pnl_close(...)` with kwargs like `lots_closed`, `side`
  - `mmm_pnl_core.py:184` signature requires `order_id, symbol, option_side, strike, lots, ...`
  - `mmm_reverse.py:592` catches and downgrades failure to warning

**Bug:** reverse close accounting call does not match `record_close()` API, raises exception, then continues.

**Why It Matters:**
- Reverse close events are not reliably written to fill ledger.
- Fee attribution/source analytics become incomplete.
- Forensic P&L consistency degrades (especially incident review quality).

**Suggested Fix:**
- Call `record_close()` with canonical required args (`symbol`, `option_side`, `lots`, etc.).
- Keep warning log, but add explicit safety flag when ledger write fails repeatedly.

---

### F3 — Hard-stop market close path removes position without partial-fill handling

- **Severity:** **P0 (Critical)**
- **Confidence:** High
- **Category:** partial update, impossible branch assumptions, silent divergence
- **Evidence:**
  - `mmm_close_at_5.py:410` market-order branch
  - `mmm_close_at_5.py:431` unconditional `_remove_closed_position(...)`
  - `mmm_close_at_5.py:563`/`:581` pending-verification + ledger path exists only in non-market flow
  - `mmm_close_at_5.py:742` explicit partial-fill helper docs for non-market path
  - `mmm_executor.py:1787` comment explicitly acknowledges partial closes can happen

**Bug:** market hard-stop path assumes full close and removes session position immediately, bypassing partial-close reconciliation mechanics used elsewhere.

**Why It Matters:**
- If market order partially fills, unfilled lots can remain live on exchange but disappear from session tracking.
- Exactly the kind of phantom position condition that cascades into risk-limit and P&L drift.

**Suggested Fix:**
- Read actual filled quantity from market result/status.
- Route partial fills through same residual-lot handling used in non-market path.
- Add pending close verification + ledger entry for market path too.

---

### F4 — Unsafe boolean coercion (`bool("false") == True`) in operator/API controls

- **Severity:** **P1 (High)**
- **Confidence:** High
- **Category:** wrong condition, bad defaults/coercion
- **Evidence:**
  - `mmm_api.py:728` → `_force_start = bool(_req_body.get('force_start', False))`
  - `mmm_api.py:4446` → `adopt = bool(data.get('adopt', False))`
  - `mmm_monitor.py:10014` → `force_enabled = bool(params.get('close_at_watcher_force_enabled', False))`
  - Canonical parser exists: `mmm_config.py:506` (`value.lower() in ('true','1','yes','on')`)

**Bug:** string inputs like `'false'`, `'0'`, `'no'` become truthy when passed through raw `bool(...)`.

**Why It Matters:**
- `force_start='false'` may unintentionally bypass start preflight protections.
- `adopt='false'` may route into adopt branch unexpectedly.
- close watcher force mode may activate unexpectedly outside expiry window.

**Suggested Fix:**
- Replace raw `bool(...)` coercion on external/operator values with normalized parser logic.
- Standardize one helper across API + monitor param ingestion.

---

### F5 — Watchdog restart blocks whole supervisor loop for 30s (cross-session blind spot)

- **Severity:** **P2 (Medium)**
- **Confidence:** Medium-High
- **Category:** race/timing vulnerability, stale monitoring window
- **Evidence:**
  - `mmm_watchdog.py:142` single watchdog loop (`_run` → `_sweep`)
  - `mmm_watchdog.py:352` settlement delay constant
  - `mmm_watchdog.py:357` blocking `time.sleep(SETTLEMENT_DELAY_SECS)` in restart path

**Bug:** during one monitor restart, watchdog thread sleeps 30s synchronously, delaying checks for all other sessions handled by same loop.

**Why It Matters:**
- Reduces fault-detection responsiveness when multiple sessions are active.
- Extends window for dead/stuck monitor to go unnoticed in another session.

**Suggested Fix:**
- Keep settlement delay per-session, but avoid globally blocking sweep loop (e.g., deferred restart scheduling per session).

---

## Severity

- **P0 (Critical): 2 findings** (`F1`, `F3`)
- **P1 (High): 2 findings** (`F2`, `F4`)
- **P2 (Medium): 1 finding** (`F5`)

Risk profile: elevated for live trading due to state/exchange divergence vectors.

---

## Why It Matters

These bugs are dangerous because they can create a **false internal position view** while exchange exposure still exists. In a real-money system, that is the exact failure mode that defeats max-loss, exposure caps, and emergency controls.

The two P0 findings (reverse partial-close finalization and market hard-stop partial-fill blind spot) are especially high impact because they sit on close paths during stressed market states.

---

## Suggested Fix

Safe implementation order (highest risk first):
1. **F1/F3 first (P0):** unify partial-fill semantics across reverse + market close paths.
2. **F2 next:** fix reverse `record_close()` contract and ensure ledger write succeeds.
3. **F4 next:** standardize bool parsing for all external/operator inputs.
4. **F5 last:** refactor watchdog restart delay so one session cannot block supervision of all sessions.

Recommended regression tests to add:
- reverse close partial fill (`filled_size < lots`) keeps residual lots open
- market hard-stop partial fill preserves residual and reconciliation metadata
- API booleans for `"false"`, `"0"`, `"no"`, `false`, `0`
- watchdog restart in one session does not pause health checks for another

---

## Safe Implementation Notes for Claude

- Preserve stale-monitor 3-layer guard invariants documented in `CLAUDE.md`.
- Preserve reverse mode hard-if/else isolation invariant in `mmm_monitor.py`.
- Do **not** weaken `_save_session()` generation guard behavior.
- For close-path fixes, prefer reusing existing core partial-close helper semantics rather than introducing a second variant.
- When fixing bool parsing, use one shared normalization function to avoid drift.
- Add tests before/with code changes, especially around partial fills and operator overrides.

---

## Final Score /10

**Overall hidden-bug risk score: 8.2 / 10 (high risk if unpatched).**

Reasoning: two critical divergence vectors in close paths + one high-severity operator-control coercion bug + accounting integrity gap.
