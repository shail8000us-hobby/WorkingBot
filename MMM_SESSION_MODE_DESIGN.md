# MMM Trend-Damage Containment — Design v2.0

**Date**: 2026-05-05
**Triggered by**: Session mmm05may26-1 post-mortem (running session)
**Status**: v1.0 superseded — see §0 for why. v2.0 design pending implementation confirmation.
**Branch**: SSR
**Author**: Opus 4.7 (re-analysis of v1.0)

---

## 0. Why v1.0 was replaced

v1.0 was authored by Sonnet without reading the actual trade ledger, the activity log,
or several of the code paths it cites. Cross-checking against
[`mmm_position_ledger.db`](webui/backend/data/mmm_position_ledger.db),
[`mmm_sessions.db`](webui/backend/data/mmm_sessions.db) (`adjustment_history`),
[`mmm_activity_log.json`](webui/backend/data/mmm_activity_log.json),
and the four files it modifies, found:

| v1.0 claim | What the data actually shows |
|---|---|
| "First actual PE hedge: 215 lots @ \$115.50 — 43 minutes after CE hit cap" | PE had **15 prior fill events** placing 750+ aggregate lots before this. The 215 @ \$115.50 was a **strike shift PE 80000 → 80600** ([`adjustment_history`][14]), not a "first hedge." |
| "CE grew from 50 → 300 lots through normal algo operation across many beats" | CE reached **246 lots by 15:12 UTC May 4** (3h into session), via `first_reversal` fills, then was **shifted to 81400**, then re-accumulated **back to 246 at 79600** by 02:50 May 5 — and **shifted again to 81200**. CE returned to 79600 a third time. This is **whipsaw re-accumulation**, not gradual drift. v1.0 doesn't mention this pattern at all. |
| "F6 gamma floor ALSO blocked the CE shift … two guards blocking simultaneously" | False. The starvation guard at [mmm_monitor.py:6231-6244](webui/backend/routes/mmm/mmm_monitor.py#L6231-L6244) **disables F6** when the current strike is already inside the floor — which was the case at 07:51. F6 was **not** blocking. |
| "Double-sell guard suppresses correct arbiter action" | Activity log shows arbiter `defensive_shift on CE` suppressed because **ITM-guard auto-shift on CE already fired** the same beat. Both targeted the **same side**, so suppression was structurally correct. The real failure is upstream: the shift itself wasn't completing. |
| "Solution: regime-based detection abandoned" + 30+ new params + 3-mode controller | Adds enormous tuning surface and a new state machine for a real-money bot. Same correctness problem in a different shape. The 8 detected issues do not all need a new mode controller; several are fixable directly. |
| "Implementation Phases (no behavior change in Phase 1)" | Only true if `_mode` defaults to Conservative AND every guard reads `session.get('_mode', ...)` consistently. With 7+ guard touchpoints across `mmm_monitor.py`, `mmm_god_layer.py`, `mmm_safety.py`, `mmm_strike_shift.py`, the chance of an unconditional read sneaking in is high. The "100% unchanged Conservative" claim is wishful. |

What v1.0 got **right**:
- Issue 1 (regime anchor reset blindness) is real — confirmed at [mmm_regime.py:470-479](webui/backend/routes/mmm/mmm_regime.py#L470-L479).
- Issue 2 (no dangerous-side concept) is real — `_trend_dangerous_side` exists ([mmm_monitor.py:6099](webui/backend/routes/mmm/mmm_monitor.py#L6099)) but is wired to `_trend_direction` from regime, so it inherits Issue 1's blindness.
- Issue 7 (stale PnlCore estimates) is real — observable in `_pnl_discrepancies` session field.
- Issue 8 (mode/state should survive watchdog restart) is generally correct.
- Recommendation to compute side asymmetry from per-position `entry_premium` (not PnlCore estimates) is sound.

v2.0 keeps these, drops the 3-mode controller, replaces it with **5 narrow mechanisms** that each address one observed failure with surgical scope.

---

## 1. What actually happened in mmm05may26-1 (evidence-based)

Reconstructed from the 17 entries in `adjustment_history` (DB) plus the 52 fills in
`session_fills` (ledger) plus the activity log (07:51-09:19 UTC tail window).

### 1a. Phase 1 — Setup (May 4 12:10-15:14 UTC, spot 78,576 → 79,934)

| UTC | Event | Cumulative lots placed |
|---|---|---|
| 12:10 | Session entry: CE 79600 (50 lots @ \$256), PE 77200 (50 lots @ \$109) | CE=50, PE=50 |
| 12:21 | PE adj #1 — 52 lots @ \$81.2 strike 77200 (CE aggressor) | CE=50, PE=102 |
| 13:04 | CE first_reversal — 22 lots @ \$208.5 strike 79600 (spot 78,576) | CE=72, PE=102 |
| 14:27 | PE strike_shift 77200 → 77800 — 98 lots @ \$93.5 | CE=72, PE=200 |
| 15:03 | PE buyback 18 lots @ \$1002 (close of frozen 77200) | CE=72, PE=182 |
| 15:14 | CE strike_shift 79600 → **81400** — **246 lots** @ \$98 | CE=246, PE=182 |

Note: between 13:04 (CE=72) and 15:14 (CE=246), **174 lots of CE were added with no entry in `adjustment_history`**. That means they were placed by `replenish` and/or harvester/recycler paths, which don't always log to adjustment_history. So `adjustment_count=15` understates the true sell count.

### 1b. Phase 2 — Spot crosses 80,000 (May 4 15:14-21:43 UTC)

| UTC | Event | Cumulative lots |
|---|---|---|
| 15:55 | PE first_reversal — 50 lots @ \$63.5 strike 77800 | CE=246, PE=232 |
| 16:20-16:42 | PE first_reversal × 2 — 50 lots total (25+25) @ \$59-62.5 | CE=246, PE=282 |
| 18:36 | PE buyback 102 lots @ \$18.5-19 (close_at_5: PE 77800 went OTM) | CE=246, PE=180 |
| 21:39-21:43 | PE buyback 196 lots @ \$20 (close_at_5 frozen lots) | CE=246, PE=−16 net effect |

`close_at_5` was correctly closing OTM-decayed PE positions. CE 81400 OTM also got
closed in the 18:36 buybacks — CE dropped from 246 → ~144 sometime here.

### 1c. Phase 3 — PE replenish ladder & CE re-accumulation (May 4 21:43 → May 5 02:50 UTC)

PE replenish at 21:43 (54 lots @ \$88.5 strike 79200) starts a chain:
PE 79200 → 80000 — five sub-shifts including 02:40 strike_shift (85 lots @ \$98.5).

Meanwhile CE somehow **returned to 79600** (active_strike rolled back). At 02:50 UTC:
- CE strike_shift 79600 → 81200 — **246 lots again** @ \$103 (adjustment #11)
- Spot 80,519 → CE 79600 was deep ITM — the algo had built it back up to 246

**This is the core problem the v1.0 doc misses**: the algo whipsawed CE from 79600 → 81400, lost premium on the roll, then over the next 11 hours rebuilt CE back at 79600 (because spot pulled below 79600 a few times), then had to roll AGAIN at much greater cost. **No mechanism prevents post-shift re-accumulation at the just-evacuated strike.**

### 1d. Phase 4 — Cap paralysis & user intervention (May 5 02:50-09:13 UTC)

| UTC | Event |
|---|---|
| 02:50 | After CE shift to 81200, spot continues up to 80,890 |
| 02:53-03:05 | PE 80000 strike adds 200 more lots (\$115-131 premium) — PE chases up |
| 06:50 | PE strike_shift 80000 → 80600 — 215 lots @ \$115.5 (`is_arbiter_correction=True`) |
| 07:01 | PE recycle — 11 lots @ \$172.5 strike 80800 |
| 07:21 | PE adj #15 — 74 lots @ \$141 strike 80800 |
| 07:31 | **Both sides at 300/300 cap** |
| 07:51-09:13 | **9 ITM-guard auto-shift attempts on CE** (CE @ 79600, spot ~80,800), **9 arbiter `breakeven_critical_pe → defensive_shift on CE`** firings, **all suppressed** by double-sell guard. Activity types breakdown for this window: `itm_guard_blocked=9`, `arbiter_tier1=9`, `arbiter_suppressed_double_sell=10`, `shift_candidate_stale=7`, `regime_control=86` (all `WARN, trend=NORMAL`), `adjustments_stopped=171`, `safety_warning=109` |
| 08:11, 09:13 | Watchdog beat-timeout kills (90-125s beat — 3-4× normal) |
| 09:03-09:05 | **User manually closes ~346 CE lots** (work log: "User manually reduced CE lots to cut upside risk") |
| 09:13 | Final session_stop |

In this window, the ITM-guard's **auto-shift was the proactive shifter** (not the proactive-scan, which v1.0 implies). Both ITM-guard auto-shift and arbiter `defensive_shift` target the **same side** (CE). Suppression was correct. The shifts that *did* fire often went stale (`shift_candidate_stale=7`) before completion — so CE never actually moved off 79600.

---

## 2. Root causes — verified against code

Numbered to mirror v1.0 so it's clear what was inherited and what changed.

### RC-1. Trend regime is blind to grinding directional moves *(inherited from v1.0)*

[mmm_regime.py:470-479](webui/backend/routes/mmm/mmm_regime.py#L470-L479) — exact reset condition v1.0 cites. Confirmed correct. `_trend_t4_beats` plateau timeout (lines 542-561) doesn't help here either: it only fires at T4, but the regime never reached T4 — it was stuck at NORMAL because every minor pullback dropped `move_pct` below 0 and reset the anchor.

**Side-effect**: `_trend_dangerous_side` ([mmm_monitor.py:6099](webui/backend/routes/mmm/mmm_monitor.py#L6099)) is computed from `_trend_direction`, which is set inside the regime module. When regime is NORMAL, `_trend_direction='none'`, so `_trend_dangerous_side=None`, so `_proactive_shift_scan` never blocks the dangerous side.

### RC-2. Whipsaw re-accumulation at evacuated strikes *(NEW — v1.0 missed this)*

After CE 79600 was shifted to 81400 at 15:14, the algo permitted CE to re-fill at 79600 over the next 11 hours, leading to a second forced roll (79600 → 81200 at 02:50) at greater loss, and a third return-to-79600 episode by 06:44 (active CE monitoring strike "switches from 81200 → 79600" per activity log).

There is no `_recently_shifted_from` lockout. The replenish path
([mmm_replenish.py](webui/backend/routes/mmm/mmm_replenish.py)) and `first_reversal`
adjustment path treat the previously-evacuated strike as a valid re-entry target.
**This is the single biggest contributor to the loss spiral**, and it is structurally
independent of any mode controller.

### RC-3. ITM-guard auto-shift fails silently when chain liquidity is thin *(re-framed from v1.0 Issue 5)*

[mmm_monitor.py:5615-5645](webui/backend/routes/mmm/mmm_monitor.py#L5615-L5645) — when CE is ITM, ITM guard calls `_process_strike_shift(hedge=CE)` directly. That path runs candidate validation at [line 6481-6510](webui/backend/routes/mmm/mmm_monitor.py#L6481-L6510): if the candidate's live premium drifts > `shift_premium_tolerance` (default \$10) from `shift_target_premium` (default \$100), it **rescans**. If the rescan also fails, the shift fallback path may activate or it may return without acting.

In a fast-moving chain near the spot/strike crossing region, candidate strikes' premiums drift faster than the validation tolerance — every beat the candidate goes stale. Result: 9 `itm_guard_blocked` activity rows in 80 minutes with no `strike_shift` activity rows. CE was **NEVER successfully shifted off 79600** in this window despite 9 attempts.

v1.0's "F6 also blocked" claim is **wrong**: the F6 starvation guard at [line 6231-6244](webui/backend/routes/mmm/mmm_monitor.py#L6231-L6244) explicitly disables F6 widening when the current strike is already inside the floor (which was the case at 07:51).

### RC-4. Double-sell guard / arbiter retry pattern *(re-framed from v1.0 Issue 4)*

The activity log evidence (10 `arbiter_suppressed_double_sell`, all on CE) shows ITM-guard auto-shift sets `_shift_placed_this_beat_ce=True` ([mmm_monitor.py:6828](webui/backend/routes/mmm/mmm_monitor.py#L6828)), and the arbiter then wants `defensive_shift on CE` and is correctly suppressed because the same side was already actioned this beat. **Suppression is the right behavior here** — it prevents a duplicate same-direction order. v1.0's framing as a "correct response being killed" is wrong.

The real bug is RC-3: the ITM-guard shift doesn't *complete*, so the system keeps re-trying every beat with the same outcome. Fixing RC-3 makes RC-4's symptom disappear.

### RC-5. "Calculated loss ≤ 0" formula skips early hedging *(inherited; partially correct)*

[mmm_monitor.py:5530-5543](webui/backend/routes/mmm/mmm_monitor.py#L5530-L5543) — confirmed. In a directional move, the standard-loss formula returns 0 when the pre-loss inventory hasn't yet been hit, so it skips the hedge. v1.0's claim is correct, but its proposed fix ("threshold reduced — start hedging at 70% of normal") doesn't address why the formula returns 0; it just multiplies the negative outcome.

The actual fix is to **change the trigger from "loss ≥ X" to "premium delta from entry > Y"** for the dangerous-side-engaged scenario. This is one boolean override point, not a graduated factor.

### RC-6. Stale PnlCore order estimates *(inherited from v1.0 Issue 7)*

Confirmed real in `session['_pnl_discrepancies']`. Two orders aged 16+ hours
indicate registry GC is missing. v1.0's recommendation to use `entry_premium` for
side-divergence is correct for that one path, but the underlying registry rot
poisons every other PNL consumer (max-loss check, God layer drift, breakeven engine).
**Fix at the source, not at one consumer.**

### RC-7. Watchdog instability under heavy beat work *(NEW — v1.0 missed this)*

Two beat-timeout kills in 80 minutes (08:11 and 09:13). Beat ages 90s and 125s vs.
`heartbeat_interval=30s` and `beat_timeout=90s`. At 300/300 with PNL drift, every
beat does: full chain fetch + 9-event activity log writes + arbiter eval + ITM-guard
auto-shift + candidate rescan + shift_candidate_stale rejection. The beat budget is
blown.

Watchdog restarts then **lose transient session state** (mode counters, beat snapshots, dangerous-side determination) — exactly v1.0's Issue 8.

### RC-8. Symmetric-by-default architecture *(inherited concept, narrower fix)*

Real, but doesn't require a 3-mode controller to address. The narrow fix is: a
single `dangerous_side` field, decoupled from regime, that gates 3 specific
guards. See §3.

---

## 3. The v2.0 Solution — five narrow mechanisms

Each mechanism is **independently shippable**, has **≤6 new params**, and addresses
**one** observed failure. No mode state machine. No 3-way escalation. No
auto-expiring manual override. Every mechanism defaults to **off** behind a
hot-reload flag so it can be deployed dark.

| # | Name | Addresses | Params | Files touched |
|---|---|---|---|---|
| M1 | Regime-Independent Dangerous-Side Signal | RC-1, RC-8 | 4 | `mmm_safety.py` (or new `mmm_side_pressure.py`), `mmm_monitor.py` (1 read site) |
| M2 | Post-Shift Strike Lockout | RC-2 | 2 | `mmm_strike_shift.py`, `mmm_replenish.py`, `mmm_monitor.py` (`_process_adjustment` reversal path) |
| M3 | ITM-Guard Emergency Shift Path | RC-3 | 3 | `mmm_monitor.py` (one section) |
| M4 | Stale Order Registry GC | RC-6 | 1 | `mmm_pnl_core.py` |
| M5 | Beat Budget & State-Survives-Restart | RC-7, RC-8 | 1 | `mmm_monitor.py` (`_heartbeat_inner`), `mmm_state.py` (initializer) |

What's **deliberately not** in this list:
- **No 3-mode controller.** A boolean `dangerous_side ∈ {ce, pe, None}` is sufficient.
  Three states × N transitions × hysteresis × manual override × restart persistence
  is more state than the problem warrants.
- **No "calculated loss ≤ 0" graduated factor.** Replaced by M1's hedge-on-engagement override (one boolean read, not a multiplier).
- **No telegram-templated mode transitions.** One alert when `dangerous_side` flips, one alert when M3 fires emergency, one when M4 GCs an order. That's it.

### M1 — Regime-Independent Dangerous-Side Signal

**What**: Compute `_dangerous_side` every beat from per-side **engaged exposure**
(realized + unrealized), not from regime. Set it to the side whose loss exceeds
the safe side by a threshold for ≥ N consecutive beats.

**Computation** (in `mmm_safety.py`, run once per beat in `_heartbeat_inner` after
`pre_beat_snapshot()`):

```python
def compute_side_pressure(session, ce_now, pe_now):
    # Realized + unrealized per side, NOT loss-only.
    # entry_premium per position is authoritative; PnlCore estimates excluded.
    ce_pressure = sum(
        (float(p['entry_premium']) - ce_now) * int(p['lots']) * LOT_SIZE_BTC
        for p in session.get('ce', {}).get('positions', [])
    )
    pe_pressure = sum(
        (float(p['entry_premium']) - pe_now) * int(p['lots']) * LOT_SIZE_BTC
        for p in session.get('pe', {}).get('positions', [])
    )
    # Negative pressure = losing money on that side.
    delta = pe_pressure - ce_pressure  # >0 → CE worse, <0 → PE worse
    return ce_pressure, pe_pressure, delta
```

**State transition** (no hysteresis on entry, slow on exit):

```python
threshold_enter  = params['side_pressure_enter']    # default $25 (delta)
threshold_exit   = params['side_pressure_exit']     # default $5
confirm_beats    = params['side_pressure_confirm']  # default 3
release_beats    = params['side_pressure_release']  # default 6

current = session.get('_dangerous_side', None)
candidate = 'ce' if delta >  threshold_enter else \
            'pe' if delta < -threshold_enter else None
```

If `candidate == current → reset _dangerous_release_count, increment confirm`.
If `candidate != current and current is not None and abs(delta) < threshold_exit → increment release_count`. After `release_beats` clear, set None.
If `candidate != current and candidate is not None → reset confirm to 1`.
On confirm ≥ confirm_beats → adopt the candidate side.

**What reads `_dangerous_side`**:

1. `_proactive_shift_scan` ([mmm_monitor.py:6099](webui/backend/routes/mmm/mmm_monitor.py#L6099)) — change to:
   ```python
   _trend_dangerous_side = (
       session.get('_dangerous_side')  # M1: regime-independent
       or ('ce' if _trend_dir == 'up' else 'pe' if _trend_dir == 'down' else None)
   )
   ```
   So when regime fires, it still works (current behavior preserved). When regime
   is silent but pressure is real, `_dangerous_side` takes over.

2. `_process_adjustment` "calculated loss ≤ 0" branch
   ([mmm_monitor.py:5530](webui/backend/routes/mmm/mmm_monitor.py#L5530)) — when
   `hedge != _dangerous_side` AND `aggressor == _dangerous_side`, **bypass the
   loss<=0 skip**. We're hedging the safe side against a confirmed dangerous
   side; the standard-loss formula's "no realized loss yet" answer is wrong.

3. New: arbiter `defensive_shift` is permitted on the **safe** side bypass-of-cooldown when `_dangerous_side` is set (NOT a velocity multiplier — just removes the per-side cooldown when the safe side is the target).

**What does NOT change**: hard caps (300/side), max_loss, margin tiers, stale
monitor, FORCE_REDUCE, straddle roll lockout. Lot velocity limit stays — M1 does
not multiply or disable it.

**Default**: `dangerous_side_enabled = False`. When False, the field is never set
and read sites fall back to the existing `_trend_direction`-based logic (current
behavior bit-for-bit).

**Param table**:

| Param | Default | Purpose |
|---|---|---|
| `dangerous_side_enabled` | `False` | Master switch (hot-reload) |
| `side_pressure_enter` | `25.0` | \$ delta to enter |
| `side_pressure_exit` | `5.0` | \$ delta to exit |
| `side_pressure_confirm` | `3` | Beats to confirm |
| `side_pressure_release` | `6` | Beats to release |

### M2 — Post-Shift Strike Lockout

**What**: After a strike shift on a side, prevent **any** sell on that side at the
**evacuated strike** for `shift_lockout_min` minutes. Closes the whipsaw re-accumulation hole (RC-2).

**Implementation** in `mmm_strike_shift.py` (post-success):

```python
session.setdefault('_recently_shifted_from', {})[side] = {
    'strike': float(old_strike),
    'until_ts': now_iso(minutes=params.get('shift_lockout_min', 45)),
}
```

**Read sites** (every code path that opens new lots on a side):
- `_process_adjustment` reversal & first_reversal branches — if target strike == lockout strike and now < until_ts → log `shift_lockout_block` and return.
- `_process_replenish` — same check.
- `_rank_strikes` (in `mmm_strike_shift._rank_strikes`) — exclude lockout strikes from candidate list.
- Recycler — exclude lockout strikes from re-open candidates.

**Multiple shifts**: keep the **most recent** shift's evacuated strike in the
lockout. If a side shifts twice (e.g. 79600 → 81400 → 81200), only 81400 is
locked out (the prior strike), not 79600. To lock multiple historical strikes,
keep a list with TTLs — but that's overkill; one-deep is enough for the observed
whipsaw pattern.

**What does NOT change**: this is **purely additive** — no existing logic is
modified, only one read added at four sites. Strike shifts still happen normally;
the lockout only blocks re-opens at the just-vacated strike.

**Default**: `shift_lockout_enabled = False`. When False, the dict is never
populated and read sites short-circuit. Bit-identical to current behavior.

| Param | Default | Purpose |
|---|---|---|
| `shift_lockout_enabled` | `False` | Master switch |
| `shift_lockout_min` | `45` | Lockout duration in minutes |

### M3 — ITM-Guard Emergency Shift Path

**What**: When ITM-guard auto-shift fails for ≥ N consecutive beats due to
candidate-stale or no-candidate, escalate to a **wider tolerance + close-some-lots**
emergency:

1. After `itm_guard_emergency_after_beats` (default **5**) consecutive `itm_guard_blocked` events on the same side without a successful shift, the next ITM-guard fire:
   - Uses `shift_premium_tolerance × itm_guard_emergency_tolerance_mult` (default **3×** → \$30 vs \$10) for candidate validation.
   - If still no candidate, **closes `itm_guard_emergency_close_pct` (default 25%)** of the **deep-ITM lots** (just the ones at the offending strike). This is real-money destructive; gated behind `itm_guard_emergency_enabled` (default `False`).
   - Telegram alert and websocket event.

**Implementation site**: extend the ITM-guard branch at [mmm_monitor.py:5615-5645](webui/backend/routes/mmm/mmm_monitor.py#L5615-L5645) with a counter on the side's `_itm_guard_consec_block` field. After successful shift fill, reset the counter.

**Why this matters**: in mmm05may26-1's last 80 minutes, 9 ITM-guard fires
produced 0 successful shifts. Without an escape valve, the bot is structurally
blocked from reducing the dangerous-side exposure even when both the algorithm
*and* the operator agree the strike is bad.

**Why "close 25% of just the offending strike's lots" not "close X lots
proportional to PNL"**: targeted reduction at the specific deep-ITM strike lowers
gamma exposure and frees cap headroom without disturbing the rest of the book.

| Param | Default | Purpose |
|---|---|---|
| `itm_guard_emergency_enabled` | `False` | Master switch (real money — keep off until validated) |
| `itm_guard_emergency_after_beats` | `5` | Consecutive blocked beats before escalation |
| `itm_guard_emergency_tolerance_mult` | `3.0` | Multiplier on `shift_premium_tolerance` |
| `itm_guard_emergency_close_pct` | `0.25` | Fraction of offending-strike lots to close if shift still fails |

### M4 — Stale Order Registry GC

**What**: In `mmm_pnl_core` (or wherever the order-estimate registry lives), any
estimate older than `pnl_estimate_max_age_min` (default **30 min**) is GC'd —
either confirmed against fills or written off as `reconciled_external`. This
unblocks the contaminated PNL drift signal.

**Implementation**: the FillSyncer loop already runs every beat and matches
fills strictly by order_id. Add a second pass that scans estimates with
`age > max_age`, queries `/v2/orders/{order_id}` once for definitive status, and
either reconciles or marks expired and removes from the open-estimate set.

**Why fix at the source**: every PNL consumer (max-loss, God drift, breakeven,
M1 side-pressure if it ever uses estimates) inherits the rot. Fixing one consumer
is a band-aid.

| Param | Default | Purpose |
|---|---|---|
| `pnl_estimate_max_age_min` | `30` | Max age before reconcile-or-write-off |

### M5 — Beat Budget Survival & State-Persists-Restart

**Two related fixes**:

**M5a — Per-step beat budget**: In `_heartbeat_inner`, wrap the chain fetch and
the arbiter eval in `asyncio.wait_for` with `beat_step_timeout_sec` (default
**12s** each). When timeout fires, log a `beat_step_timeout` activity, skip the
step, and continue. This prevents one slow chain call from blowing the 90s
watchdog budget.

**M5b — Mode/state survives restart**: Mark `_dangerous_side`, `_recently_shifted_from`, `_itm_guard_consec_block` as **persisted fields** by including them in the session JSON
on every `_save_my_session()`. They already would be — confirm explicit handling
in `mmm_storage.py`. After watchdog restart, M1's state machine resumes with
beat counters reset to confirm (so a wrong determination would still need
`confirm_beats` to re-establish). M2's lockout TTL is wall-clock-based, so
naturally survives.

| Param | Default | Purpose |
|---|---|---|
| `beat_step_timeout_sec` | `12` | Max seconds per heartbeat step (chain fetch, arbiter, etc.) |

---

## 4. What v2.0 deliberately does NOT do

| Not doing | Why |
|---|---|
| 3-mode controller | Combinatorial state explosion. M1's single boolean covers what Moderate would have done; M3 covers what Aggressive would have done. |
| Auto-expiring manual override | Operator decisions aren't expired by the system — that defeats the point of manual override. If we add manual override later, no auto-expiry. |
| Telegram templates for every mode change | Three transition alerts from M1/M2/M3 cover the operator-relevant signals. |
| 30+ params | 11 total new params (vs v1.0's 30+). Easier to tune, smaller correctness surface. |
| Disabling double-sell guard | Suppression in mmm05may26-1 was correct; the underlying shift failure is RC-3, fixed by M3. |
| F6 gamma floor disable | Already disables itself in the relevant case (line 6231-6244). Don't add a redundant override. |
| God layer extension | The God layer's 25-min interval was firing this whole session — no evidence its check needs replacement. M1's signal is faster (per-beat) and serves the same purpose. If the God layer is later determined to need asymmetry awareness, that's a separate phase. |
| Fast-track / direct-to-aggressive paths | M3's emergency path is the only "fast" thing v2.0 has, and it acts on a single concrete failure (5 consecutive ITM-guard blocks). |

---

## 5. Hard invariants preserved

Per [CLAUDE.md](CLAUDE.md):

- §0 self-check protocol applies before any code in `mmm_monitor.py`, `mmm_engine.py`, `mmm_constants.py`, or `webui/backend/routes/mmm/`.
- §4 stale monitor 3-layer protection — **untouched**. M5a's `wait_for` does not interact with the generation guard.
- §5 reverse mode hard if/else — **untouched**. M1/M2/M3 read sites are inside the normal-MMM `else` branch only.
- M1's `_dangerous_side` field is isolated from `_reverse` state.
- All new fields persisted via existing `_save_my_session()` flow — no new save path.

Position cap (300/side) is **never** overridden by any v2.0 mechanism. Max loss
stop, margin ORANGE/RED, FORCE_REDUCE, straddle roll lockout — untouched.

---

## 6. Implementation phases

Each phase is **shippable independently** — order is not strict, but the listed
order minimizes risk.

**Phase 1 — M5a beat budget** (smallest blast radius, biggest stability win)
- Wrap chain fetch & arbiter eval in `asyncio.wait_for(timeout=beat_step_timeout_sec)`
- Add `beat_step_timeout` activity type
- Sealed test: simulate 30s chain stall, verify beat completes within 15s, verify subsequent beats unaffected
- Files: `mmm_monitor.py` (2 sites), `mmm_state.py` (1 param), `mmm_activity.py` (1 type)
- **Default ON** — true safety improvement, no behavior risk

**Phase 2 — M4 stale order GC** (corrects PNL signal — prerequisite for M1)
- FillSyncer second pass for estimates older than max_age
- Reconcile via `/v2/orders/{id}` or write off as `reconciled_external`
- Sealed test: estimate aged >30min with no fill → verify GC removes it
- Files: `mmm_pnl_core.py`, `mmm_fill_sync.py`
- **Default ON** — observability fix, no decision-changing behavior

**Phase 3 — M2 post-shift lockout** (highest expected value — addresses the
biggest loss contributor)
- Add `_recently_shifted_from` write at strike-shift success
- Add 4 read sites with bypass when disabled
- Sealed test: shift CE 79600 → 81400, attempt re-add at 79600 within 45min → verify blocked; verify add at 79800 (different strike) succeeds
- Files: `mmm_strike_shift.py`, `mmm_replenish.py`, `mmm_monitor.py`, `mmm_recycler.py`, `mmm_state.py`
- **Default OFF** — enable per-session for first week of validation

**Phase 4 — M1 dangerous-side signal** (gates the existing `_proactive_shift_scan`
block that already exists but is regime-tied)
- New `mmm_side_pressure.py` (or a function in `mmm_safety.py`)
- Wire into `_heartbeat_inner` step 5 (after pre-beat snapshot, before proactive scan)
- Modify `_proactive_shift_scan` line 6099 to read `_dangerous_side` first, fall through to `_trend_direction`
- Modify `_process_adjustment` "loss ≤ 0" skip to bypass when hedge=safe and aggressor=dangerous
- Sealed tests: CE pressure crosses threshold for 3 beats → flag set; PE pressure flips → flag re-evaluated
- Files: `mmm_safety.py` (or new file), `mmm_monitor.py` (2 read sites), `mmm_state.py` (5 params)
- **Default OFF**

**Phase 5 — M3 ITM-guard emergency** (last because real-money destructive)
- Counter increment on `itm_guard_blocked` without subsequent successful shift
- After N blocks, widen tolerance once; if still blocked, close X% of offending strike
- Sealed tests: simulate 5 consecutive ITM-guard fires with no shift fill, with `itm_guard_emergency_enabled=False` → verify no close fires; with `=True` → verify exactly one close
- Files: `mmm_monitor.py`, `mmm_state.py`
- **Default OFF** — enable only after Phase 3 + 4 have run for ≥ 1 week without regressions

**Frontend** (after Phase 4):
- `_dangerous_side` indicator on session card (badge: "⚠️ CE pressure" or "⚠️ PE pressure")
- `_recently_shifted_from` strike list in the session detail panel
- ITM-guard consecutive-block counter (post-Phase 5)
- No auto-mode buttons; if operator override is later requested, scope it then.

---

## 7. Risk assessment

| Risk | Mitigation |
|---|---|
| M1 false-positive flips dangerous side too eagerly | confirm_beats=3, exit threshold (\$5) lower than enter (\$25) provides hysteresis. Default OFF until 1 week of dry-run. |
| M2 lockout traps a side when market truly oscillates | TTL=45min is a single-side, single-strike lockout. Adjacent strikes (79800, 79400) remain valid re-entry targets. Operator can clear via existing pin/unfreeze UI if needed. |
| M3 closes positions at bad prices in genuinely illiquid moments | Default OFF. When enabled, only fires after 5 failed shifts (~50 minutes of evidence). Closes only 25% of offending strike's lots. |
| M4 GCs a real fill that's just slow to confirm | The reconcile pass queries `/v2/orders/{id}` for definitive status before writing off. Only writes off if exchange confirms order done. |
| M5a timeout wraps a critical step that needs more time | 12s per step is 4× normal. If a step legitimately needs more, that's a slow-path bug to fix, not an excuse to expand the budget. |
| New fields not persisted across watchdog restart | Phase 1 & 2 fields are wall-clock-derived. M1's state is reset to `None` and re-confirms (not "wrong" — just slower). |
| v2.0 design has unknowns from data we couldn't see (logs >2h old were rotated) | Prioritize phases by smallest blast radius first; defer M3 destructive action until upstream signals (M1, M4) are validated. |

---

## 8. Param summary (11 total)

```python
# Mechanism 1 — Dangerous-Side Signal
'dangerous_side_enabled': False,
'side_pressure_enter': 25.0,
'side_pressure_exit': 5.0,
'side_pressure_confirm': 3,
'side_pressure_release': 6,

# Mechanism 2 — Post-Shift Lockout
'shift_lockout_enabled': False,
'shift_lockout_min': 45,

# Mechanism 3 — ITM-Guard Emergency
'itm_guard_emergency_enabled': False,
'itm_guard_emergency_after_beats': 5,
'itm_guard_emergency_tolerance_mult': 3.0,
'itm_guard_emergency_close_pct': 0.25,

# Mechanism 4 — Stale Estimate GC
'pnl_estimate_max_age_min': 30,

# Mechanism 5 — Beat Budget
'beat_step_timeout_sec': 12,
```

All hot-reloadable. All default to existing behavior (the four enables=False
default off; M4/M5a default on as pure-improvement plumbing).

---

## 9. Cross-references

- [`MMM_LAST_3_SESSIONS.md`](MMM_LAST_3_SESSIONS.md) — recent context including v1.0 entry
- [`mmm_workdone_march.md`](mmm_workdone_march.md) — long history of regime, double-sell-guard, velocity bypass fixes
- [`webui/backend/routes/mmm/mmm_regime.py`](webui/backend/routes/mmm/mmm_regime.py) — regime detection (RC-1)
- [`webui/backend/routes/mmm/mmm_monitor.py`](webui/backend/routes/mmm/mmm_monitor.py) — heartbeat orchestrator
- [`webui/backend/routes/mmm/mmm_strike_shift.py`](webui/backend/routes/mmm/mmm_strike_shift.py) — shift logic (M2 anchor point)
- [`webui/backend/routes/mmm/mmm_pnl_core.py`](webui/backend/routes/mmm/mmm_pnl_core.py) — PnlCore registry (M4 anchor point)
- [`webui/backend/routes/mmm/mmm_safety.py`](webui/backend/routes/mmm/mmm_safety.py) — existing `check_asymmetry` (lot-ratio, warn-only) — separate from M1's dollar-pressure signal

---

*Document version: 2.0 — 2026-05-05*
*Supersedes: 1.0 (same date, replaced after data-cross-check)*
*Next step: User confirms ordering of Phases 1–5; Phase 1 (M5a beat budget) implementation begins.*
