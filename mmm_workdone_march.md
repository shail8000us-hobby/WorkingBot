# MMM Algo — Work Done (March 2026)

> **MANDATORY**: Every AI session that touches MMM code must READ this file at the start and ADD a new entry at the end.
> Format: `## YYYY-MM-DD — <short title>` followed by bullet points of what changed and why.

---

## 2026-03-03 — Cleanup + Lot Recycling Plan

- Added detailed lot recycling implementation plan (`MMM_LOT_RECYCLING_IMPLEMENTATION_PLAN.md`)
- Noted API cache fix in docs
- Pre-professional-cleanup snapshot

---

## 2026-03-07 — User Requested Commit

- General state save

---

## 2026-03-10 — Improvement Plan P1 + T-plan implementations

- `feat(mmm)`: implemented items from MMM_IMPROVEMENT_PLAN: P1-A/B/D, IMP-3/4/5/6/8/9/10/12
- `fix`: calculate_lots_to_sell unpacking mismatch in mmm_monitor
- `chore`: perp pre-adjustment delta projection (T4-3)
- `fix`: 2 audit bugs + completed T-plan items

---

## 2026-03-11 — Operator Strike Controls + Scaler + 5 Deep Audit Fixes

- `feat`: Operator Strike Controls — Set Active Strike, Close Strike, Position Inject endpoints
- `feat`: MMM Scaler module added
- `fix(mmm)`: 5 bugs found in deep audit (mmm_api, mmm_engine)
- `fix`: WebUI performance regression and PE orphan adoption bug

---

## 2026-03-12 — ATM Shield + Audit Fixes + Wind-Down Corrections

- `feat`: ATM Shield — proactive close & retreat on ATM proximity
- `fix(mmm)`: wind_down_on_atm and close_at_atm use active_strike not original_strike
- `fix(mmm)`: partial fill, ATM guard, regime, shift cooldown, whipsaw audit fixes

---

## 2026-03-14 — Comprehensive Sealing + Observer Pattern

- Comprehensive sealing across MMM modules
- MMM observer pattern implemented
- Options improvements

---

## 2026-03-15 — Close-at-5 Watcher + TTL Fix + New Modules

- `feat(mmm)`: close-at-5 watcher (automatic position closing at premium threshold)
- TTL fix for stale being-closed flags
- Settings 400 error fix
- Patience, breakeven, gamma modules added

---

## 2026-03-17 — Gamma Severity Multiplier + Patience Overhaul

- `feat(mmm,patience)`: enable gamma severity multiplier by default
- Patience UI/algorithm overhauled

---

## 2026-03-18 — Trade Transparency System (4 phases) + Global Exit All

- `feat(mmm)`: Trade Transparency System Phase 1+2 — audit log, attribution buckets (pnl_initial, pnl_adjustment, pnl_harvest, pnl_recycle)
- `feat(mmm)`: Phase 3 — Trade Audit tab in MMMDashboard
- `feat(mmm)`: Phase 4 — perp hedge, Mode B, reconcile alert in audit panel
- `fix(mmm)`: audit panel data bugs — key mismatches + 409 error
- `fix(mmm)`: suppress audit mismatch noise for pre-deployment sessions
- `feat(mmm)`: Global Exit All endpoint + live bid/ask price feed on dashboard
- `fix(mmm)`: TDZ error — move live-price useEffect after fullSession declaration

---

## 2026-03-19 — Short Straddle DTE Preset

- `feat(mmm)`: SHORT_STRADDLE dynamic preset factory (build_short_straddle_preset with DTE param)
- `feat(mmm)`: Short Straddle preset added to UI dropdown and API response

---

## 2026-03-24 (Session 1) — Forensic Audit: 6 Correctness Bugs

**Commit: `b6eddef61`**

- **BUG-C1 (P0)**: Straddle initial credit always 0 — `mmm_monitor.py` used `pos.get('original_lots')` instead of `pos.get('lots')`. Added `_straddle_credit_v2` recompute flag.
- **SYNC-3 (P0)**: Being-closed positions counted in loss calculation — `mmm_engine.py`: skip `pos.get('_being_closed')` in frozen_positions loop.
- **SYNC-4 (P1)**: Whipsaw multiplier applied to already theta-accelerated value — use raw `min_trigger_move` as base, take `max(ws_widened, theta_widened)` instead of compounding.
- **HID-1 (P1)**: Checksum covered derived/empty fields causing false positives — added `_calculate_checksum_v2()` covering only canonical fields.
- **ARCH-1 (P1)**: No automatic reconciliation — added heartbeat-driven auto reconciliation every N beats (default 50). Emits SAFETY_ALERT on mismatch.
- **HID-2 (P2)**: `trigger_snapshot` dict grew unbounded — pruned after updating.

---

## 2026-03-24 (Session 2) — PnL Calculation Deep Audit + 4 Fixes

**Analysis of session `mmm24mar26-2` (P&L $15.99)**

Found `net_pnl = None` in DB, attribution gap $0.14, fill_sync rounding bug, MMMSessionCard fee omission, close_at_strike missing stamp.

**Bug #1 — `net_pnl = None` for stopped sessions** (`mmm_api.py: stop_session`)
- Root cause: `_overlay_live_pnl` skips stopped sessions; `net_pnl` was never persisted at session stop.
- Fix: compute `compute_live_pnl()` BEFORE calling `stop_session_monitor()`, persist `{net_pnl, realized_pnl, unrealized_pnl, total_fees}` in the same `update_session` call.

**Bug #2 — `fill_sync` spurious `round()` on `realized_pnl` when correction=0** (`mmm_fill_sync.py:282`)
- Root cause: `session['realized_pnl'] = round(... + 0.0, 8)` ran unconditionally, truncating ULP digits on every fill confirmation. `pnl_adjustment` was guarded (>1e-9 check) so the two drifted apart.
- Fix: gate `realized_pnl` update inside the same `if abs(pnl_correction) > 1e-9` block as `attr_key`.

**Bug #3 — `MMMSessionCard.js` overstates net P&L** (`MMMSessionCard.js:97`)
- Root cause: `netPnl = realized + unrealized` — fees never subtracted.
- Fix: `netPnl = session.net_pnl ?? (realized + unrealized - fees)` — prefer stored net_pnl, fallback to R+U-F.

**Bug #4 — `close_at_strike` endpoint missing `_estimated_pnl_booked` stamp + no attribution booking** (`mmm_api.py: close_by_strike`)
- Root cause: positions were marked closed without `_estimated_pnl_booked`, so fill_sync treated the entire fill as a "new" booking (not a correction). Also, `session['realized_pnl']` was never updated here — only `total_realized_pnl` (different key).
- Fix: stamp `_estimated_pnl_booked` + `_estimated_commission_booked` per-position; book directly to `session['realized_pnl']` + `session['manual_reduction_pnl']`; refresh `unrealized_pnl` after close.

**Note — peak_pnl discrepancy is intentional**: `peak_pnl=$15.85` vs `max pnl_history=$16.91` is expected — `update_peak_pnl` uses a 15-min half-life decay so old peaks fade. Not a bug.

---
