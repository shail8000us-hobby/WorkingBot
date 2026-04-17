# Session Forensic Audit Report — `mmm17apr26-6`

**Generated:** 2026-04-17  
**Analyst mode:** Post-trade forensic + production systems audit  
**Session under review:** `mmm17apr26-6` (MMM)

---

## 0) Scope and Evidence Policy

This report is built from **actual local evidence** only:

- `webui/backend/data/mmm_sessions.db`
  - `mmm_sessions`
  - `position_audit_log`
  - `session_event_log`
  - `mmm_analytics`
- Runtime logs:
  - `logs/webui_production_error.log`
- Cross-check tables:
  - `data/bot_events_BTCUSD_SHORT.db` (`events`)

### Strict evidence outcome

- `position_audit_log` rows for `mmm17apr26-6`: **0**
- `session_event_log` rows for `mmm17apr26-6`: **3**
- `data_json._fill_ledger`: **[]**
- `data_json.adjustment_history`: **[]**
- `data_json.positions`: **[]** (top-level unified list empty; side-level lists populated)

**Conclusion:** this was an **adoption + monitor + stop** session, not a normal order-execution session.

---

## 1) Session Identity and Lifecycle Data

| Field | Value |
|---|---|
| session_id | `mmm17apr26-6` |
| status | `STOPPED` |
| strategy_type | `STRADDLE_WITH_ADJUSTMENT` |
| created_at (UTC) | `2026-04-17T03:15:03.815229+00:00` |
| entry_time (UTC) | `2026-04-17T03:16:09.697221+00:00` |
| adopted_at (UTC) | `2026-04-17T03:16:09.697224+00:00` |
| last_heartbeat (UTC) | `2026-04-17T03:17:20.570637+00:00` |
| updated_at (UTC) | `2026-04-17T03:17:32.116982+00:00` |
| stop reason | empty (`""`) |
| entry_mode | `adopt` |

### Final P&L state

| Metric | Value |
|---|---:|
| realized_pnl | `0.0` |
| unrealized_pnl | `3.411067` |
| total_fees | `0.0` |
| net_pnl | `3.411067` |

---

## 2) Full Chronological Action Sheet (All Session Events)

> Because there were no new orders/fills under this session ID, this timeline includes all action/event primitives (lifecycle, risk, config, state, API controls).

| # | Time (IST) | Event Type | Side | Instrument | Strike | Qty | Price | Reason | Trigger Source | Before State | After State | P&L Impact | Notes |
|---:|---|---|---|---|---:|---:|---:|---|---|---|---|---|---|
| 1 | 08:46:09 | Adopt Inventory | CE+PE | BTC options 170426 | 74400/75000 | 465 total | inherited | Start from existing exposure | API adopt | No running monitor | Side books populated | mark-to-market starts | `entry_mode=adopt` |
| 2 | 08:46:10 | Monitor Start | — | — | — | — | — | Start session loop | API start | STOPPED | RUNNING | 0 | close watcher started |
| 3 | 08:46:11–14 | Reconciliation Warnings | CE/PE | C/P BTC | 74400/75000 | matched | — | ownership mismatch signals | reconciler | Fresh adopted book | warnings persisted | 0 | `other_mmm` counts present |
| 4 | 08:46:14.951 | Trigger Snapshot Heal | CE | C-BTC | 75000 | — | 149.50 | missing/zero snapshot | trigger healer | CE[75000] absent | CE[75000]=149.50 | 0 | preventative correction |
| 5 | 08:46:15.994 | Regime Transition | portfolio | — | — | — | — | risk escalation | regime engine | NORMAL | FORCE_REDUCE | 0 | critical transition |
| 6 | 08:46:16.255 | Heartbeat #1 | CE+PE | C/P BTC | 75000/74400 | — | CE149.5 PE144.5 | trigger eval | heartbeat | adopted inventory | no trigger | net ~+4.51 | caps blocked actions |
| 7 | 08:46:45.346 | Strategy Validation Fail | strategy | — | — | — | — | straddle invariant broken | validator | CE strike != PE strike | validation warning active | 0 | structural conflict |
| 8 | 08:46:47.173 | Heartbeat #2 | CE+PE | C/P BTC | 75000/74400 | — | CE158.0 PE137.07 | trigger eval | heartbeat | same inventory | no trigger | net ~+3.41 | no trade path |
| 9 | 08:46:48.463 | Param Hot Reload | config | — | — | — | — | cap alignment manual fix | PATCH params | max_lots_per_side=5 | max_lots_per_side=500 | 0 | operator intervention |
| 10 | 08:47:06 / 08 / 20 | Resume Calls | session | — | — | — | — | manual retries | API resume | already RUNNING | unchanged/no-op behavior | 0 | likely operator confusion |
| 11 | 08:47:30–31 | Monitor Shutdown Steps | — | — | — | — | — | session termination | stop path | RUNNING | stopping | 0 | close watcher stopped |
| 12 | 08:47:32 | Session Stop | — | — | — | — | — | manual stop | API stop | RUNNING | STOPPED | final net +3.411 | reason empty |
| 13 | 08:47:37 | Post-stop Save Blocks | — | — | — | — | — | save_disabled safeguard | monitor/save path | save attempts | blocked as expected | 0 | normal after stop |

---

## 3) Raw Data Evidence (Full)

## 3.1 `session_event_log` rows for `mmm17apr26-6`

| id | timestamp_ist | category | type | severity | remark | details |
|---:|---|---|---|---|---|---|
| 7005 | 2026-04-17T08:46:15.994560+05:30 | REGIME | transition | CRITICAL | Regime: NORMAL → FORCE_REDUCE | `{old_action:NORMAL,new_action:FORCE_REDUCE,vol_regime:NORMAL,gamma_regime:EMERGENCY,trend_regime:NORMAL,trend_tier:0}` |
| 7006 | 2026-04-17T08:46:48.463498+05:30 | PARAM_CHANGE | hot_reload | INFO | Param change: max_lots_per_side 5 → 500 | `{param:max_lots_per_side,old_value:5,new_value:500}` |
| 7007 | 2026-04-17T08:47:32.219394+05:30 | SESSION_LIFECYCLE | stopped | INFO | Session stopped — | `{reason:"",new_status:"STOPPED"}` |

## 3.2 `position_audit_log` rows for `mmm17apr26-6`

- Count = **0**
- No session-tagged order/fill execution entries.

## 3.3 `mmm_analytics` snapshot highlights

| Metric | Value |
|---|---:|
| session_duration_seconds | 80.780665 |
| total_adjustments | 0 |
| total_shifts | 0 |
| total_reversals | 0 |
| total_close_at_5 | 0 |
| total_recycles | 0 |
| total_ce_lots_traded | 0 |
| total_pe_lots_traded | 0 |
| final_realized_pnl | 0.0 |
| final_unrealized_pnl | 3.411067 |
| final_total_pnl | 3.411067 |
| max_drawdown_from_peak | 1.0446789 |
| time_to_first_profit | 6.55764 sec |

## 3.4 Side books (`data_json`) at stop

### CE side

- active_strike: `75000.0`
- active_lots: `300`
- total_lots: `323`
- original_lots: `0`
- adjustment_fills: `[{lots:300,premium:123.5,strike:75000,timestamp:2026-04-17T03:16:09.697143+00:00,type:adjustment,_pos_id:ce_frozen_002}]`
- frozen_positions: `[{strike:74400,lots:23,entry_premium:367.5,type:original,frozen_at:2026-04-17T03:16:14.757665+00:00,_pos_id:ce_orig}]`
- trigger_snapshot: `{74400:449.31469415,75000:149.5}`

### PE side

- active_strike: `74400`
- active_lots: `142`
- total_lots: `142`
- original_lots: `142`
- adjustment_fills: `[]`
- frozen_positions: `[]`
- trigger_snapshot: `{74400:144.65104092}`

## 3.5 Adoption snapshot (`data_json.adoption_snapshot`)

- spot_at_adoption: `74675.84757281`
- expiry: `17042026`
- classified:
  - CE active: 23 @ 74400 (`C-BTC-74400-170426`) at 367.5
  - CE frozen: 300 @ 75000 (`C-BTC-75000-170426`) at 123.5
  - PE active: 142 @ 74400 (`P-BTC-74400-170426`) at 245.87
- trigger_mode: `current_prices`

## 3.6 Walkthrough log entries (`_walkthrough_log`)

- Entry + 2 heartbeats only.
- Heartbeat #1: CE 149.5 vs trigger 149.5 (0%), PE 144.5 vs 144.65 (-0.1%)
- Heartbeat #2: CE 158.0 vs 149.5 (+5.7%), PE 137.07 vs 144.65 (-5.2%)
- `min_trigger_move=50%` so **no trigger fire** either beat.

## 3.7 Risk/Greeks snapshot at end

| Field | Value |
|---|---:|
| _gamma_regime | EMERGENCY |
| _regime_action | FORCE_REDUCE |
| _portfolio_dollar_gamma | 13875.33 |
| _ce_dollar_gamma | 9735.68 |
| _pe_dollar_gamma | 4139.64 |
| _gamma_hard_limit_effective | 5000.0 |
| _gamma_emergency_limit_effective | 10000.0 |
| _gamma_dte_relax_active | False |

## 3.8 Heartbeat / speed telemetry (session-local)

| Metric | Value |
|---|---:|
| _heartbeat_counter | 3 |
| total_beats | 2 |
| ok_beats | 2 |
| miss_beats | 0 |
| error_beats | 0 |
| latency_p50_ms | 3866.7 |
| latency_max_ms | 5907.5 |
| miss_rate_pct | 0.0 |
| health_grade | A |

## 3.9 Runtime log evidence (session-tagged)

Key lines found in `logs/webui_production_error.log`:

- `08:46:10` adopt/start success
- `08:46:11–14` reconciliation mismatch warnings with `other_mmm`
- `08:46:14.951` trigger snapshot healed
- `08:46:45.346` strategy validation failed (CE strike != PE strike)
- `08:46:48.381` IMP-10 cap raise 5→500
- `08:47:32` stop
- `08:47:37` `_save_session blocked: save_disabled`

## 3.10 Global system stress observed in same window (not session-specific but relevant)

- Massive websocket backpressure warnings:
  - `Message queue full - dropped ...` increasing through the window
  - Counts seen rising from ~62k to ~95k drops during/around session runtime

---

## 4) Issues Identified (Root Cause + Impact)

| Time | Issue | Root Cause | P&L Damage | Confidence | Fix Suggestion |
|---|---|---|---:|---|---|
| 08:46:45 | Strategy invariant broken (`CE 75000 != PE 74400`) | Adopt path allowed incompatible inventory under straddle strategy | Indirect (decision-quality/risk control) | High | Hard pre-start gate for strategy invariants; reject/convert mode |
| 08:46:16 | Caps instantly blocking (`300/5`, `142/5`) | Cap profile not auto-validated against adopted inventory | Opportunity cost / control deadlock | High | Preflight cap normalization on adopt/start |
| 08:46:15+ | EMERGENCY regime with no executed reduction | FORCE_REDUCE state not coupled to deterministic immediate reduction path in this run | Risk remained loaded | Med-High | Bind FORCE_REDUCE to mandatory de-risk executor |
| 08:46:11–14 | Reconciliation warning semantics ambiguous with `other_mmm` | Ownership-overlap messaging unclear; values can appear contradictory to operator | Operator confusion risk | High | Report `owned = exchange - other_mmm` explicitly; classify overlap separately |
| 08:46:14 | Trigger snapshot required self-heal | Snapshot initialization gap during adopt | Small immediate risk (healed) | High | Atomic snapshot initialization before first heartbeat |
| ENTRY summary | Walkthrough entry underreports active adopted exposure | Entry formatter likely reading partial initial context | Forensic/reporting integrity issue | High | Build entry summary from canonical side books post-adopt |
| 08:47:06/08/20 | Multiple resume calls likely no-op | UI/API state feedback not explicit | Control-plane confusion | Medium | Return explicit no-op reason from resume endpoint |
| 08:47:32 | Stop reason empty | Stop endpoint/process allows blank reason | Forensic ambiguity | High | Require structured stop reason + actor source |

---

## 5) Slowdown / Blocker Analysis

| Bottleneck | Evidence | Impact | Priority | Improvement |
|---|---|---|---|---|
| Startup strategy-state conflict | invariant fail + cap mismatch on first beats | Session effectively inert | P0 | Startup preflight gate (invariants + cap sanity) |
| Emergency mode not actionable | FORCE_REDUCE but no reduction entries | Risk stays loaded | P0 | Automatic forced reduction plan |
| Global websocket backpressure | queue-full dropped-message storm in same window | Potential stale data risk + operational noise | P1 | queue partitioning/throttling + consumer scaling |
| Reconciliation overlap noise | repeated `other_mmm` mismatch warnings | Alert fatigue + decision confusion | P1 | ownership-aware reconciliation UX/logs |
| Sparse adopt audit trail | no adopt-to-trade normalized audit stream | forensic gaps | P1 | emit synthetic adoption trade-audit entries |

---

## 6) Profitability Review

### A) Quick wins

1. Hard-block strategy start on invariant violations.
2. Auto-adjust caps on adopt before first heartbeat.
3. Tie FORCE_REDUCE to mandatory action, not only status.
4. Persist complete adoption lineage in trade audit stream.
5. Enforce non-empty stop reason.

### B) Medium improvements

1. Add dedicated **Inventory Recovery mode** for adopted asymmetric books.
2. Improve cross-session ownership accounting to reduce overlap ambiguity.
3. Make resume endpoint state-aware with no-op reasons.
4. Persist heartbeat decision gates (why trade did/didn’t fire) per beat.

### C) Advanced research

1. Portfolio-level ownership resolver across concurrent MMM sessions.
2. Emergency de-risk optimizer minimizing slippage under gamma pressure.
3. Dynamic trigger policy adaptation under feed backpressure confidence scores.

### D) Dangerous ideas (test only)

1. Immediate full flatten on first invariant failure.
2. Aggressive emergency market order sweeps in thin 0DTE orderbooks.

---

## 7) Human Trader Counterfactual

A discretionary desk operator likely would have:

- Not started straddle-mode on CE/PE strike-mismatched adopted inventory.
- Normalized inventory first (or switched to dedicated recovery mode).
- Fixed cap policy before start, not after forced warnings.
- Treated gamma emergency as immediate de-risk, not status-only.

---

## 8) Session Scorecard

| Dimension | Score (/10) | Rationale |
|---|---:|---|
| Execution Quality | 3.0 | No new orders/fills; mostly lifecycle ops |
| Risk Control | 4.0 | Risk detected, action path weak |
| Speed | 6.0 | Session-local beats healthy; global feed pressure poor |
| Decision Quality | 3.0 | Started with invalid strategy state |
| Capital Efficiency | 2.0 | Large inherited risk with blocked trade path |
| Profit Capture | 2.0 | Realized = 0; unrealized only |
| Stability | 6.0 | No crash; clean stop |
| Robustness | 3.5 | Weak preflight and emergency execution coupling |

**Overall grade: `D` (3.7/10)**

---

## 9) Final Verdict

`mmm17apr26-6` was a short-lived **adoption-control session**, not an execution session.  
There is **no evidence of session-tagged trades** in this run. The key weaknesses were **state validity**, **control-path readiness**, and **operational clarity**, not fill quality.

If you want true execution forensics, the meaningful trade lineage is in predecessor sessions (especially `mmm17apr26-4` and `mmm17apr26-5`) that supplied the inherited inventory.

---

## 10) Assumptions and Missing Data (Explicit)

1. No hidden per-session order table outside scanned SQLite/log sources was found for this session.
2. Global websocket queue drops are not uniquely attributable to this session, but they occurred in the same runtime window.
3. Because `position_audit_log` is empty for session 6, direct per-trade slippage/rejection analytics cannot be computed for this session itself.

---

## Appendix A — Predecessor trade evidence proving inherited exposure

From `position_audit_log`:

- `mmm17apr26-5` had PE 74400 SELL adjustments: 54 @ 235, 19 @ 169, 37 @ 113.
- `mmm17apr26-4` had CE 75000 SELL confirm (300 lots @ 123.50) plus other adjustments/closures.

This aligns with session 6 adoption snapshot and side books.
