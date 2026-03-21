# OPT Engine Plan — Production Audit Report (Round 2)

**Auditor perspective:** Senior Quant Dev + Options Strategist + Production System Auditor  
**Date:** 2026-03-21  
**Document audited:** [OPT_ENGINE_PLAN.md](file:///Users/ssr/Projects/WorkingBot/tasks/OPT_ENGINE_PLAN.md) (Rev 2 — with Round 1 fixes integrated)  
**Verdict:** PLAN IS STRONG — Round 1 fixes were comprehensive. This round surfaces **11 remaining gaps** that range from critical to informational.

---

## Context: What Was Read

| File | Lines | Key Context Extracted |
|---|---|---|
| `OPT_ENGINE_PLAN.md` | 892 | Full plan with all C-1→C-5, H-1→H-6, M-1→M-7 fixes integrated |
| `AI_MMM_CONTEXT.md` | 2900+ | Full MMM algorithm, every subsystem |
| `tasks/lessons.md` | 1571 | 60+ production bugs — Delta Exchange API quirks, eventlet issues, state management failures |
| `CLAUDE.md` | 344 | Port 5555, USD→INR, LaunchAgent protocol |
| `mmm_executor.py` | 800+ | smart_execute, emergency_execute, client_order_id, reprice loop |
| `mmm_safety.py` | 800+ | 7 safety checks, max_loss guard, whipsaw, trailing stop |
| `mmm_state.py` | 800+ | Unified Position Ledger, 100+ params, HOT_RELOAD_PARAMS |

---

## Findings Summary

| # | Severity | Finding | Plan Section |
|---|---|---|---|
| R2-1 | **CRITICAL** | Eventlet threading not mentioned — OPT will inherit the same greenlet/asyncio conflict | §6, §8, §9 |
| R2-2 | **CRITICAL** | No `_being_closed` guard on OPT exit — race condition from Day 1 | §6.4 |
| R2-3 | **HIGH** | `paid_commission` vs `commission` API field not specified — fees will be 0 forever | §6.3, §6.4, §13 |
| R2-4 | **HIGH** | `blocked_margin` vs `portfolio_margin` not specified — wrong margin utilization | §6.2 Step 6, §6.3 Step 8 |
| R2-5 | **HIGH** | Expiry format mismatch (ddmmyyyy vs ddmmyy) not documented | §6.3, §13 |
| R2-6 | **HIGH** | No `unrealized_pnl` refresh after exit fills — stale P&L display | §6.4, §13 |
| R2-7 | **MEDIUM** | No hedge integrity guard on OPT — partial close leaves 3-leg structure | §6.4, §13 |
| R2-8 | **MEDIUM** | No per-heartbeat close cap — exit loop can stall heartbeat indefinitely | §6.2, §7.1 |
| R2-9 | **MEDIUM** | Cache miss returning 0 instead of None not warned against | §6.2 Step 1, §13 |
| R2-10 | **LOW** | Phase ordering: WebSocket (Phase 5) before Exit Logic (Phase 4) in testing dependency | §9 |
| R2-11 | **LOW** | `opt_reconciler.py` needs the `expiry_to_symbol_suffix()` pattern documented | §8, §13 |

---

## Detailed Findings

### R2-1: Eventlet Threading — OPT Will Crash on First Heartbeat (CRITICAL)

**The problem:** The plan says "replicate MMM heartbeat pattern" but never mentions the eventlet elephant in the room. From `lessons.md` [2026-03-10]:

> `gunicorn_config.py` uses `worker_class = "eventlet"`. Eventlet monkey-patches `threading.Thread` into a greenlet. `asyncio.new_event_loop()` inside a greenlet causes "Cannot run the event loop while another loop is running".

MMM solved this with `eventlet.patcher.original('threading').Thread` — a real OS thread where asyncio works. **OPT's monitor will crash identically** unless this is in the plan.

**Also from `lessons.md`:** `future.result()` blocking inside an eventlet greenlet freezes the entire backend for 12-15 seconds. The fix is cooperative polling with `eventlet.sleep(0.01)`.

> [!CAUTION]
> **Where to add in plan:** §4 "What OPT Inherits" should include "Eventlet-safe threading pattern" as a mandatory replication item. §13 "Critical Implementation Notes" needs a new note.

**Proposed text for §13:**
```
**OPT monitor thread MUST use real OS threads (eventlet fix).**
The backend runs under `gunicorn worker_class=eventlet`. Eventlet monkey-patches
`threading.Thread` into greenlets. asyncio event loops cannot run inside greenlets.
Use `eventlet.patcher.original('threading').Thread` for the heartbeat loop thread —
same pattern as MMM's `mmm_monitor.py start()`. Any `future.result()` calls from
greenlets must use cooperative polling (`eventlet.sleep(0.01)` loop), never blocking
waits.
```

---

### R2-2: No `_being_closed` Guard — Race Condition on Exit (CRITICAL)

**The problem:** The exit sequence (§6.4) closes short legs then long legs sequentially. During the 60s+ wait for short leg fills, the heartbeat loop continues running. If any exit trigger fires again (max_loss re-check, trailing stop), it will attempt to close the SAME positions concurrently — double-close on the exchange.

From `lessons.md` [2026-03-15]:

> `_process_wind_down_buyback` called `smart_execute` without pre-marking positions as `_being_closed`. During the await, other mechanisms could concurrently attempt to close the same positions, causing double-close.

And [2026-03-15]:

> `_being_closed` flag had no TTL — positions permanently locked after crash.

**The OPT plan has no mention of `_being_closed` guards anywhere.**

> [!CAUTION]
> **Where to add in plan:** §6.4 Exit Sequence should include _being_closed marking before each close attempt. §13 needs a new note about TTL auto-clear.

**Proposed additions to §6.4:**
```
2a. MARK positions: Set `_being_closed = True` + `_being_closed_at = monotonic()`
    on each position before placing close orders. Heartbeat exit checks skip
    positions with this flag. Auto-clear after 180s TTL if flag is stale (crash
    recovery). Clear flag on successful close or on failure/exception.
```

---

### R2-3: `paid_commission` vs `commission` — Fees Will Be Zero (HIGH)

**The problem:** The plan mentions "Fee estimation" (§6.3 Step 5) and "Track fees in session state" (§13) but never specifies WHICH Delta Exchange API field to use.

From `lessons.md` [2026-03-19] — Bug C:

> Delta Exchange returns fee data in every order response. The correct field is `paid_commission` (actual fee charged after fill), NOT `commission` (reserved amount, always "0" for filled orders). Both fields are strings, not floats.

If the OPT executor reads `commission` instead of `paid_commission`, fees will always be 0 — exactly what happened in MMM for months.

> [!WARNING]
> **Where to add in plan:** §13 Critical Implementation Notes needs the exact field name and the fallback chain.

**Proposed text for §13:**
```
**Use `paid_commission` for fee tracking, NOT `commission` (Delta Exchange API quirk).**
`order['commission']` is a string "0" (reserved amount, always 0 for filled orders).
`order['paid_commission']` is a string like "0.04140325" (actual USDT fee charged).
Both are strings — always cast with `float()`. Use fallback chain:
`float(od.get('paid_commission', 0) or od.get('commission', 0) or 0)`.
Every `smart_execute` / `emergency_execute` call site MUST extract fees and add
to `session['total_fees']`.
```

---

### R2-4: `blocked_margin` vs `portfolio_margin` (HIGH)

**The problem:** §6.2 Step 6a says "Margin check (EXCHANGE-level, cross-engine)" and §6.3 Step 8 says "Query exchange-level margin". Neither specifies which wallet API field to use.

From `lessons.md` [2026-03-13]:

> `portfolio_margin` in Delta's API wallet response is the theoretical portfolio margin requirement (a risk model value) — it can be higher than actual collateral locked. `blocked_margin` is what Delta Exchange actually freezes.

If OPT uses `portfolio_margin`, the safety threshold will fire prematurely (false positives).

> [!WARNING]
> **Where to add in plan:** §13 needs a note about margin field priority.

**Proposed text for §13:**
```
**Margin check must use `blocked_margin`, not `portfolio_margin` (Delta Exchange API).**
`blocked_margin` = actual locked collateral = what Delta UI shows as "Blocked as Margin".
`portfolio_margin` = theoretical risk model value (can exceed actual collateral).
Priority: blocked_margin > portfolio_margin > position_margin + order_margin.
This matches the fix in `mmm_margin_guardian.py`.
```

---

### R2-5: Expiry Format Mismatch — ddmmyyyy vs ddmmyy (HIGH)

**The problem:** The plan never mentions that sessions store expiry in `ddmmyyyy` format but Delta Exchange symbols use `ddmmyy` suffix. This burned MMM in reconciliation:

From `lessons.md` [2026-03-11]:

> The orphan scan used `expiry_suffix = f'-{expiry}'` where `expiry` was in ddmmyyyy format (e.g., `11032026`). But Delta Exchange symbols use ddmmyy suffix (e.g., `110326`). The `sym.endswith('-11032026')` check failed for every symbol.

`opt_reconciler.py` will have the exact same bug if not warned.

> [!WARNING]
> **Where to add in plan:** §13 Client Implementation Notes, alongside the reconciliation note.

**Proposed text for §13:**
```
**Session stores expiry as ddmmyyyy; Delta symbols use ddmmyy suffix.**
When building symbol strings for reconciliation or order queries, always convert
using an `expiry_to_symbol_suffix()` helper (e.g., `11032026` → `110326`).
Never use the raw expiry parameter directly in symbol string comparisons.
```

---

### R2-6: Stale `unrealized_pnl` After Exit Fills (HIGH)

**The problem:** The exit sequence (§6.4) closes positions and updates `realized_pnl`. But `unrealized_pnl` is only computed at heartbeat Step 3. If the WebSocket emits state between exit fills and the next heartbeat, the frontend shows `realized(new) + unrealized(stale)` — overcounted P&L.

From `lessons.md` [2026-03-19]:

> ANY code path that updates `realized_pnl` MUST also refresh `unrealized_pnl` before saving/emitting. Treat them as an atomic pair.

> [!IMPORTANT]
> **Where to add in plan:** §6.4 Step 5 needs an explicit note.

**Proposed addition to §6.4 Step 5:**
```
5a. REFRESH unrealized_pnl: Recompute from remaining open positions (should be 0
    after all legs closed). Treat realized_pnl + unrealized_pnl as an atomic pair —
    never save/emit one without refreshing the other. This prevents stale P&L display
    between exit fills and next heartbeat.
```

---

### R2-7: No Hedge Integrity Guard on Partial Close (MEDIUM)

**The problem:** The plan says "close SHORT legs first" (§6.4) but doesn't address what happens if only ONE short leg fills and the system crashes or times out. You'd have:
- 1 naked short ATM option (the unfilled short)
- 1 closed short
- 2 long hedges (one now unmatched)

This isn't the same as a full structure break (which §6.2 Step 4 catches). It's a **partial exit** — the structure is half-dismantled.

From `lessons.md` [2026-03-12] — HEDGE INTEGRITY GUARD:

> No mechanism prevented close_position() from closing the LAST position on a side while the other side had substantial positions.

> [!IMPORTANT]
> **Where to add in plan:** §6.4 should add a partial exit recovery step.

**Proposed addition to §6.4 between Steps 2 and 3:**
```
2e. PARTIAL EXIT CHECK: If one short leg closed but the other short leg failed:
    - The remaining short is still hedged by its 2× long side
    - Escalate the failed short's close to MARKET immediately (don't wait 60s)
    - If MARKET order also fails → KILL SWITCH (flatten everything at any price)
    - NEVER proceed to closing longs while ANY short leg is still open
```

---

### R2-8: No Per-Heartbeat Close Cap (MEDIUM)

**The problem:** MMM learned the hard way that close loops without caps stall the heartbeat for minutes:

From `lessons.md` [2026-03-15]:

> `MAX_CLOSES_PER_HEARTBEAT = 3` was dead code — cap never enforced. [...] Near expiry with many eligible positions, all of them could be attempted in one heartbeat, potentially stalling for 10+ minutes.

For SSDH with 4 legs, this is less of an issue in Phase 1 (only 4 positions total). But §10 lists Iron Condor (same 4 legs) and future strategies might have more. A guardian-style `max_beat_sec` timeout should be mentioned.

> [!NOTE]
> **Where to add in plan:** §7.1 Group 3 (Safety) should include `guardian_max_beat_sec`.

---

### R2-9: Cache Miss Returns 0 Instead of None (MEDIUM)

**The problem:** §6.2 Step 1 mentions "4-layer fallback: WS mid → REST mark → cache → last-good" but doesn't mandate what to return when ALL layers fail. In MMM, returning 0 for cache miss caused:

From `lessons.md` [2026-03-19] — Bug A:

> `_prefetch_all_premiums` stored 0 for failed ticker fetches. `compute_unrealized_pnl` only guards against `None` — so `0` passed through and computed `(entry_premium - 0) × lots × LOT_SIZE_BTC`, making every failed-fetch position appear fully decayed.

> [!IMPORTANT]
> **Where to add in plan:** §13 Critical Implementation Notes.

**Proposed text for §13:**
```
**Price fetch failures MUST return None, never 0.**
0 is a valid price (for nearly worthless options). Returning 0 on fetch failure makes
the P&L engine think the position is fully decayed — displaying phantom profits for
shorts or phantom losses for longs. The P&L engine should skip positions with None
premium and log a fetch error.
```

---

### R2-10: Phase Ordering Issue (LOW)

**The problem:** Phase 5 (WebSocket + Activity) is listed after Phase 4 (Entry + Exit Logic). But Phase 4 includes "emit session_started event" (§6.3 Step 13) and "emit session_closed event" (§6.4 Step 8), which depend on WebSocket infrastructure being ready. This means Phase 4 can't be fully tested without Phase 5.

> [!NOTE]
> **Suggestion:** Either move WebSocket setup to Phase 3 (alongside Heartbeat), or note in Phase 4 that WebSocket events should use stub emitters until Phase 5.

---

### R2-11: Symbol Suffix in Reconciliation (LOW)

Already covered by R2-5 above. `opt_reconciler.py` in the file list (§8) should reference the `expiry_to_symbol_suffix` requirement.

---

## Previously Integrated Fixes — Verification

All Round 1 fixes (C-1 through C-5, H-1 through H-6, M-1 through M-7) are correctly integrated. Spot-checking confirms:

| Fix | Verification |
|---|---|
| C-1 (atomic entry) | §6.3 Steps 10a-10f ✅ |
| C-2 (no individual leg exits) | §2.4 WARNING box + §7.2 comments ✅ |
| C-3 (entry state machine) | §6.3 Entry State Machine section ✅ |
| C-4 (intraday max loss) | §2.2 CAUTION box + `intraday_max_loss_multiplier` ✅ |
| C-5 (cross-engine margin) | §6.3 Steps 7-8, §12 Rule 5 ✅ |
| H-1 (30s heartbeat) | §6.2 IMPORTANT box ✅ |
| H-2 (OTM liquidity) | §6.3 Step 4 ✅ |
| H-3 (Greek monitoring) | §6.2 Step 5 ✅ |
| H-4 (aggressive limits) | §6.4 IMPORTANT box ✅ |
| H-5 (fee accounting) | §6.3 Step 5, §13 ✅ |
| H-6 (hedge ratio validation) | §6.3 Step 6, §13 ✅ |

---

## Proposed Changes

All changes are to a single file: [OPT_ENGINE_PLAN.md](file:///Users/ssr/Projects/WorkingBot/tasks/OPT_ENGINE_PLAN.md)

### §4 — What OPT Inherits Table

Add "Eventlet-safe threading" row to the pattern replication table (R2-1).

### §6.2 Step 1 — Price Fetching

Add cache-miss-returns-None rule inline (R2-9).

### §6.4 — Exit Sequence

Add `_being_closed` guard (R2-2), partial exit recovery (R2-7), and unrealized_pnl refresh (R2-6).

### §13 — Critical Implementation Notes

Add 5 new notes:
1. Eventlet threading (R2-1)
2. `paid_commission` fee field (R2-3)
3. `blocked_margin` priority (R2-4)
4. Expiry format ddmmyyyy→ddmmyy (R2-5)
5. Cache miss returns None not 0 (R2-9)

### §17 — Production Audit Summary

Add Round 2 findings table.

---

## Verification Plan

This is a **plan-only audit** — no code changes. Verification is:
1. All 11 findings are integrated into the correct plan sections
2. No existing Round 1 fixes are disturbed
3. All new text uses the same style/formatting as existing plan content
