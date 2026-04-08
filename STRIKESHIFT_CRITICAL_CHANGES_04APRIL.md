# STRIKESHIFT_CRITICAL_CHANGES_04APRIL.md

**Date:** 2026-04-04  
**Session:** Full strike shift mechanism overhaul  
**Files Changed:** `mmm_monitor.py`, `mmm_strike_shift.py`, `mmm_config.py`, `mmm_state.py`, `mmm_guardian.py`, `mmm_telegram.py`, `MMMSettingsDialog.js`

---

## Why This Document Exists

On 2026-04-04, a live order was placed at **P-BTC-66400-040426 @ $8.8 premium** when the algo was supposed to shift to a new strike near `shift_target_premium = $50`. The strike at $66,800 was available at **$54** on the exchange but the bot failed to find it. This triggered a full investigation and redesign of the strike shift mechanism.

If something breaks in the shift flow in the future — wrong strike selected, no shift firing when expected, stale candidates used — **this file describes exactly how the system works and where to look.**

---

## Root Causes of the 04-April Incident

### Bug 1: Stale Chain Cache at Shift Time
`find_new_strike` called `get_full_chain(expiry)` which used chain data cached for up to **10 seconds** (`chain_data` TTL) and option tickers cached for **5 seconds** (`tickers` TTL). By the time a shift fired, the cache snapshot might be missing a strike (like 66800) or have its `mark_price = 0` — causing the strike to be skipped entirely.

### Bug 2: Wrong Fallback on Shift Failure
When `find_new_strike` returned None (no suitable OTM strike found), `_process_strike_shift` fell back to `_process_shift_fallback` which placed an order at the **current decayed active strike** (66400 @ $8.8). This defeated the entire purpose of `shift_threshold` and `shift_target_premium`. The comment "a sub-optimal hedge is better than no hedge" was incorrect — selling lots at $8.8 when the user set a $50 floor generates almost no premium and contaminates the position book.

---

## Changes Made

### Change 1: Removed Wrong Fallback (BREAKING BEHAVIOR CHANGE)
**File:** `mmm_monitor.py` — `_process_strike_shift`

**Old behavior:** When `find_new_strike` returned None → called `_process_shift_fallback` → placed order at decayed active strike regardless of premium.

**New behavior:** When `find_new_strike` returns None after all retries → logs `shift_no_strike` → returns without placing any order → retries next heartbeat.

**Rationale:** Shift-opens must respect the premium floor. Regular adjustments (adds to existing positions) bypass the shift path entirely — they sell at the active strike as designed. The shift path is specifically for opening NEW positions at a better strike. If no suitable strike exists, do nothing and try again.

**Risk if reverted:** Bot will again sell at decayed strikes, accumulating cheap lots that generate negligible premium.

---

### Change 2: Pre-Scan Every Heartbeat
**File:** `mmm_strike_shift.py` — new `pre_scan_shift_candidates()` function  
**File:** `mmm_monitor.py` — `_heartbeat` (after `_prefetch_all_premiums`)

**How it works:**
- Every heartbeat, immediately after premiums are fetched, `pre_scan_shift_candidates(initializer, session, spot_price)` is called for both CE and PE.
- It calls `find_new_strike` for each side (read-only, no session mutations).
- Results stored in `session['_shift_candidates']`:
  ```python
  {
    'ce': {'strike': 67500, 'premium': 55.0, 'symbol': 'C-BTC-67500-040426',
           'scanned_at': <epoch>, 'shift_threshold': 25.0, 'shift_target_premium': 50.0},
    'pe': {'strike': 66800, 'premium': 54.0, 'symbol': 'P-BTC-66800-040426',
           'scanned_at': <epoch>, 'shift_threshold': 25.0, 'shift_target_premium': 50.0},
  }
  ```

**When `_process_strike_shift` fires:** It first checks `session['_shift_candidates'][side]`. If the candidate is:
- ≤ 60 seconds old, AND
- Found under the same `shift_threshold` and `shift_target_premium` as currently configured

→ Uses it directly (zero extra API calls). If the candidate is stale/missing/config changed → falls through to fresh scan (Change 3).

**Risk:** `find_new_strike` is called twice per heartbeat (CE + PE) regardless of whether a shift fires. This is one extra REST API call per heartbeat cycle. The chain TTL cache (10s) means successive heartbeats share the same network fetch, so the overhead is low.

---

### Change 3: Cache Flush Before Fresh Scan
**File:** `mmm_monitor.py` — `_process_strike_shift` (when no warm candidate)

When the pre-scan candidate is missing or stale, `_process_strike_shift` now:
1. Calls `chain_service.invalidate_cache('BTC', expiry_normalized)` to force a fresh REST fetch
2. Calls `find_new_strike` with the flushed cache
3. If still no candidates: fetches a fresh `spot_price` (in case the cached spot caused false ITM classification) and calls `find_new_strike` one more time
4. If all three attempts fail → log `shift_no_strike` → skip (Change 1)

---

### Change 4: Live Premium Validation Before Order Placement
**File:** `mmm_monitor.py` — `_process_strike_shift` (after candidate selected, before freeze)  
**Config:** `shift_premium_tolerance` (new param, default `$10`, hot-reloadable)

After a candidate is selected (from pre-scan or fresh scan), and **before** `freeze_current_positions` is called, the bot fetches the candidate strike's **current live premium** via `chain_service.get_option_ticker(symbol)`.

**Logic:**
```
if |live_premium - shift_target_premium| > shift_premium_tolerance:
    → log 'shift_candidate_stale'
    → flush cache + fresh spot + rescan
    → if rescan finds better strike: use it
    → if rescan finds nothing: use original (best available)
```

**Example:** `shift_target_premium=50`, `shift_premium_tolerance=10` → valid range = $40–$60. If live premium is $35 or $70, rescan fires.

**Why before freeze:** `freeze_current_positions` is irreversible in a single heartbeat — it moves active lots to `status='shifted'` and clears the active position. If we froze first and then found the candidate invalid, we'd be stuck with no active position and no new strike.

**Config:** `shift_premium_tolerance = 0` disables the check entirely.

---

### Change 5: Guardian Violation Telegram + Auto-Heal
**File:** `mmm_telegram.py` — `alert_guardian_violation()`, `alert_guardian_healed()`  
**File:** `mmm_guardian.py` — `handle_violations()`, new `check_g3_healed()`  
**File:** `mmm_monitor.py` — auto-heal block before "Step 4"

**Problem:** Guardian G3 violations (side wipeout detected in one beat) paused the session silently — no Telegram alert, no auto-recovery. From the UI screenshot, CE=30 lots and PE=100 lots were both present (G3 had already cleared) but session stayed paused forever.

**Changes:**
1. `handle_violations()` now fires `alert_guardian_violation` via Telegram (same pattern as G5 stale-monitor alerts).
2. New `check_g3_healed(session)` in `MMMGuardian`: returns True if **both sides have `active_lots > 0`** (uses `active_lots` NOT `total_lots` — frozen lots from old strikes don't count as hedges).
3. In heartbeat, if session is paused with reason starting with `'Guardian violations:'` and `check_g3_healed()` is True → auto-resume + `alert_guardian_healed` Telegram + set `_skip_to_pnl = True` (no trading in the same heartbeat as heal).

**`_skip_to_pnl = True` after heal:** Prevents the algo from immediately firing a trade the same beat it auto-heals. The Telegram gives the operator visibility first. Trading resumes cleanly next heartbeat.

---

## New Config Parameter

| Param | Default | Range | Hot? | Description |
|-------|---------|-------|------|-------------|
| `shift_premium_tolerance` | `10.0` | `0–500` | ✅ | ±$ tolerance around `shift_target_premium` for live candidate validation before order placement. Set 0 to disable. |

**WebUI location:** Trigger & Adjustment section, immediately after `shift_target_premium`.

---

## Key Invariants — DO NOT BREAK

### INV-1: No fallback to decayed active strike on shift failure
`_process_strike_shift` must NEVER call `_process_shift_fallback` or sell at the old active strike when `find_new_strike` returns None. Return without order. The `_process_shift_fallback` function exists but is only valid for regular adjustment continuations (where the ITM guard or pre-sell shift failed), NOT as a shift fallback.

### INV-2: Pre-scan is read-only
`pre_scan_shift_candidates` calls `find_new_strike` which is verified read-only. It must not call any function that mutates session state (freeze, activate, recompute_side_lots). If a future change adds session mutation to `find_new_strike`, pre-scan will break.

### INV-3: Validation happens BEFORE freeze
The live premium validation block in `_process_strike_shift` must always execute before `freeze_current_positions`. Freeze is irreversible within a heartbeat. The validation code is between the candidate selection and the freeze call — keep it there.

### INV-4: `params` must be defined at method top
`_process_strike_shift` now defines `params = session.get('params', {})` at the top of the method (after cooldown check). The validation block, lot-scaling, and other sections all depend on this. Do not move this definition below the validation block.

### INV-5: G3 auto-heal uses `active_lots`, not `total_lots`
`check_g3_healed()` checks `active_lots > 0` on both sides. Do NOT change this to `total_lots`. Frozen lots (from previously shifted positions being wound down) do NOT constitute an active hedge. A side with only frozen lots and `active_lots = 0` is still effectively unhedged.

### INV-6: Auto-heal sets `_skip_to_pnl = True`
After guardian auto-heal calls `self.resume()`, the code must set `_skip_to_pnl = True` to prevent the algo from immediately trading in the same heartbeat as the heal. The operator should see the Telegram notification before any new orders fire.

### INV-7: Warm candidate must pass gamma OTM distance check
`pre_scan_shift_candidates` runs with `min_otm_distance=0` (gamma zone is unknown at pre-scan time). When `_gamma_shift_min_otm > 0` (gamma DANGER zone active at shift time), the warm candidate from `session['_shift_candidates']` must be validated: CE strike must be ≥ `spot + _gamma_shift_min_otm`, PE strike must be ≤ `spot - _gamma_shift_min_otm`. If the candidate violates this, fall through to a fresh `find_new_strike` call with the proper `min_otm_distance`. The OTM check is in `_process_strike_shift` immediately after the warm-candidate lookup. Do NOT remove it.

---

## Audit Findings and Fixes (same session)

All of the following were found by a post-implementation audit and fixed before commit:

| Severity | Issue | Fix |
|----------|-------|-----|
| CRITICAL | `params` used at line ~4816 in `_process_strike_shift` but not defined until ~4896 — guaranteed `NameError` on first validation call | Moved `params = session.get('params', {})` to method top |
| MEDIUM | Warm candidate path accepted pre-scan result without checking `_gamma_shift_min_otm` — in gamma DANGER zone the selected strike could be inside the OTM exclusion radius | Added OTM distance check before accepting warm candidate; if violation, falls through to fresh scan with `min_otm_distance=_gamma_shift_min_otm` |
| MEDIUM | `if/else` structure: when warm candidate failed OTM check, `else` branch (fresh scan) was unreachable — `new_strike_info` stayed None and bot hit `shift_no_strike` without ever trying a fresh scan | Changed `else:` to `if not new_strike_info:` so fresh scan fires for all no-candidate cases (stale, config changed, OTM violation) |
| MEDIUM | `check_g3_healed` used `total_lots` (includes frozen) — could auto-heal when side is actually unhedged | Changed to `active_lots` |
| MEDIUM | Auto-heal `resume()` did not set `_skip_to_pnl = True` — algo could fire trades immediately after healing | Added `_skip_to_pnl = True` after `resume()` |
| MEDIUM | Rescan inside validation block used stale `spot_price` from method entry | Added `_rescan_spot = await self._fetch_spot_price()` before rescan |
| LOW | Pre-scan failures logged at `debug` level — silent failure mode | Raised to `warning` |
| LOW | `_sr_params = session.get('params', {})` at line 4888 was a dead duplicate — `params` already defined at method top | Removed duplicate; `params` used directly |

---

## How to Debug Strike Shift Issues in Future

**"Bot didn't shift when it should have":**
1. Check `shift_threshold` — is `hedge_premium < shift_threshold`? If not, shift isn't triggered.
2. Check `shift_cooldown_sec` — was a shift done recently? Cooldown blocks repeated shifts.
3. Check logs for `shift_no_strike` — means no OTM strike with premium ≥ threshold found.
4. Check `session['_shift_candidates']` in the session JSON — was the pre-scan finding anything?
5. Check `shift_candidate_stale` in activity log — validation triggered a rescan that also found nothing.

**"Bot shifted to wrong strike":**
1. Check `shift_target_premium` — the algo picks the strike CLOSEST to this value.
2. Check `shift_premium_tolerance` — if too wide, a drifted candidate passes validation.
3. Check `session['_shift_candidates']` — what did the pre-scan find vs what was used?

**"Bot sold at the decayed active strike instead of shifting":**
- This should be IMPOSSIBLE after this change. If it happens, `_process_shift_fallback` was called from somewhere unexpected. Search the code for any new callers of `_process_shift_fallback`.

**"Guardian auto-heal fires but session immediately trades":**
- Check that `_skip_to_pnl = True` is set after `self.resume()` in the guardian auto-heal block (INV-6 above). This invariant prevents same-heartbeat trading after heal.
