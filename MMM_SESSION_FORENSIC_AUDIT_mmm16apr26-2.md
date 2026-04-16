# MMM Session Forensic Audit Report

**Session audited:** `mmm16apr26-2`  
**Strategy type:** `0DTE MMM`  
**Audit timestamp:** 2026-04-16  

**Primary evidence used (direct DB/log correlation):**
- `webui/backend/data/mmm_sessions.db`
  - `position_audit_log` (30 rows for this session)
  - `session_event_log` (82 rows)
  - `mmm_sessions.data_json` (full session state; 451k JSON)
  - `mmm_analytics.analytics_json`
  - `performance_sessions` row (`id=146`)
- `webui/backend/data/mmm_activity_log.json` + `.bak`
  - 253 unique activity events for this session (windowed telemetry)

---

## 1. Executive Summary

This session **ended STOPPED at 2026-04-16T08:08:08Z** with:
- **Realized P&L:** `$30.7235`
- **Unrealized P&L:** `$-12.831973`
- **Fees:** `$5.9877153`
- **Net P&L:** `$11.903812`

### What actually made money vs lost money
- **Profits came almost entirely from CE auto-close flow (`close_at_5`)**:
  - Realized from `close_at_5`: **`+$35.617502`**
- **Main realized loss:** early PE ATM shield close
  - `atm_shield` realized: **`-$4.894`**

### Critical forensic findings
1. **All confirmed exchange fills = 31**, but `position_audit_log` has only **30** rows.  
   One confirmed replenish sell (`order_id=1275862757`, PE 100 @ 81.5) is missing from `position_audit_log`.
2. **Two order intents have no terminal status in `session_event_log`**:
   - `1275945116` (BUY 100 CE @ 8.0)
   - `1276102923` (BUY 420 CE @ 18.5)
   One of these is confirmed as cancelled in activity log (`manual_close_strike FAILED`), but not lifecycle-complete in session event table.
3. **Severe control-loop stress in late session**:
   - `dangerous_mode_bypass`: 31 events
   - `shift_no_strike`: 24 events
   - `cap_auto_shift`: 20 events
   - `safety_warning`: 25 events
4. **Latency is a real blocker**:
   - Intent→confirm latency: p50 `10.3s`, p90 `71.1s`, max `133.8s`
   - Activity `order_filled` elapsed: p50 `8.8s`, p90 `73.1s`, max `116.4s`
5. **Residual risk remained high at stop**:
   - Final lots from analytics: **CE 420, PE 598** (combined 1018)
   - Gamma regime remained **EMERGENCY**

### Assumptions / data gaps (explicit)
- Activity logs are windowed (first matched event ~`07:37Z`), so early-session strategy-intent detail is sourced mainly from DB tables.
- No explicit per-call API timing table exists; execution latency is inferred from intent/placed/filled timestamps.
- WebSocket vs polling is inferred indirectly via `order_filled` vs `fill_sync_confirmed` lag (not direct transport telemetry).

---

## 2. Full Trade Timeline

### Filled chronology (31 confirmed fills)

| # | Time (UTC) | Event Type | Side | Instrument | Strike | Qty | Price | Reason | Trigger Source | Before State | After State | P&L Impact | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-04-16T03:08:36.421487+00:00 | Initial Entry | SELL PE | P-BTC-74600-160426 | 74600 | 100 | 102.0 | Initial entry — Short Strangle PE leg \| 100 lots @ $102.00 \| gross $10.2000 | - | CE=0, PE=0 | CE=0, PE=100 | 0.0 | lat=13.9s, oid=1275859041 |
| 2 | 2026-04-16T03:10:36.402808+00:00 | Initial Entry | SELL CE | C-BTC-76000-160426 | 76000 | 100 | 23.0 | Initial entry — Short Strangle CE leg \| 100 lots @ $23.00 \| gross $2.3000 | - | CE=0, PE=100 | CE=100, PE=100 | 0.0 | lat=133.8s, oid=1275859037 |
| 3 | 2026-04-16T03:11:02.402617+00:00 | Auto Close | BUY PE | P-BTC-74600-160426 | 74600 | 100 | 136.5 | ATM Shield close — spot within ATM proximity of strike 74600 \| P&L $-4.8940 | - | CE=100, PE=100 | CE=100, PE=0 | -4.894 | lat=7.1s, oid=1275861585 |
| 4 | 2026-04-16T03:11:19.552975+00:00 | Roll | SELL CE | C-BTC-75400-160426 | 75400 | 100 | 104.5 | PE aggressor → CE hedge \| 100 lots @ $104.50 \| gross $10.4500 | PE | CE=100, PE=0 | CE=200, PE=0 | 0.0 | lat=14.7s, oid=1275861741 |
| 5 | 2026-04-16T03:12:24.508089+00:00 | Replenish | SELL PE | P-BTC-74400-160426 | 74400 | 100 | 81.5 | Position exists in session state (replenish, status=shifted); missing in position_audit_log | - | CE=200, PE=0 | CE=200, PE=100 | 0.0 | lat=15.5s, oid=1275862757, missing_position_audit_row |
| 6 | 2026-04-16T03:16:59.294130+00:00 | Reversal | SELL PE | P-BTC-74400-160426 | 74400 | 59 | 67.0 | Reversal: CE aggressor → PE hedge \| adj P&L was negative \| 59 lots @ $67.00 \| loss covered $1.6274 | CE / BLOCK_CE_SELLS | CE=200, PE=100 | CE=200, PE=159 | 0.0 | lat=3.9s, oid=1275867464 |
| 7 | 2026-04-16T03:21:04.988728+00:00 | Adjustment | SELL PE | P-BTC-74400-160426 | 74400 | 56 | 62.5 | CE aggressor → PE hedge \| 56 lots @ $62.50 \| loss covered $1.5049 \| gross $3.5000 | CE / BLOCK_CE_SELLS | CE=200, PE=159 | CE=200, PE=215 | 0.0 | lat=75.1s, oid=1275870383 |
| 8 | 2026-04-16T03:25:57.863545+00:00 | Adjustment | SELL PE | P-BTC-74400-160426 | 74400 | 72 | 57.0 | CE aggressor → PE hedge \| 72 lots @ $57.00 \| loss covered $1.7202 \| gross $4.1040 | CE / BLOCK_CE_SELLS | CE=200, PE=215 | CE=200, PE=287 | 0.0 | lat=13.0s, oid=1275876049 |
| 9 | 2026-04-16T03:29:12.361388+00:00 | Reversal | SELL CE | C-BTC-75400-160426 | 75400 | 3 | 123.0 | Reversal: PE aggressor → CE hedge \| adj P&L was negative \| 3 lots @ $123.00 \| loss covered $0.0744 | PE / FORCE_REDUCE | CE=200, PE=287 | CE=203, PE=287 | 0.0 | lat=5.1s, oid=1275879255 |
| 10 | 2026-04-16T03:33:39.416097+00:00 | Adjustment | SELL CE | C-BTC-75400-160426 | 75400 | 46 | 103.5 | PE aggressor → CE hedge \| 46 lots @ $103.50 \| loss covered $2.0090 \| gross $4.7610 | PE / FORCE_REDUCE | CE=203, PE=287 | CE=249, PE=287 | 0.0 | lat=13.7s, oid=1275883218 |
| 11 | 2026-04-16T03:38:06.417776+00:00 | Reversal | SELL PE | P-BTC-74400-160426 | 74400 | 38 | 66.5 | Reversal: CE aggressor → PE hedge \| adj P&L was negative \| 38 lots @ $66.50 \| loss covered $1.0896 | CE / FORCE_REDUCE | CE=249, PE=287 | CE=249, PE=325 | 0.0 | lat=7.2s, oid=1275887030 |
| 12 | 2026-04-16T03:45:38.886658+00:00 | Reversal | SELL CE | C-BTC-75400-160426 | 75400 | 94 | 96.5 | Reversal: PE aggressor → CE hedge \| adj P&L was negative \| 94 lots @ $96.50 \| loss covered $3.6674 | PE / FORCE_REDUCE | CE=249, PE=325 | CE=343, PE=325 | 0.0 | lat=10.3s, oid=1275892927 |
| 13 | 2026-04-16T03:51:54.381392+00:00 | Adjustment | SELL CE | C-BTC-75400-160426 | 75400 | 123 | 80.5 | PE aggressor → CE hedge \| 123 lots @ $80.50 \| loss covered $4.2250 \| gross $9.9015 | PE / FORCE_REDUCE | CE=343, PE=325 | CE=466, PE=325 | 0.0 | lat=25.0s, oid=1275897432 |
| 14 | 2026-04-16T04:08:13.837560+00:00 | Reversal | SELL PE | P-BTC-74400-160426 | 74400 | 75 | 60.5 | Reversal: CE aggressor → PE hedge \| adj P&L was negative \| 75 lots @ $60.50 \| loss covered $2.1104 | CE / FORCE_REDUCE | CE=466, PE=325 | CE=466, PE=400 | 0.0 | lat=16.7s, oid=1275911087 |
| 15 | 2026-04-16T04:09:39.370468+00:00 | Reversal | SELL CE | C-BTC-75400-160426 | 75400 | 34 | 80.5 | Reversal: PE aggressor → CE hedge \| adj P&L was negative \| 34 lots @ $80.50 \| loss covered $2.3652 | PE / FORCE_REDUCE | CE=466, PE=400 | CE=500, PE=400 | 0.0 | lat=7.1s, oid=1275912345 |
| 16 | 2026-04-16T06:10:03.046479+00:00 | Manual Action | SELL PE | P-BTC-74600-160426 | 74600 | 20 | 60.5 | Operator inject — manual lot placement @ strike 74600 | - | CE=500, PE=400 | CE=500, PE=420 | 0.0 | lat=57.5s, oid=1276014531 |
| 17 | 2026-04-16T06:11:05.048310+00:00 | Adjustment | SELL PE | P-BTC-74400-160426 | 74400 | 20 | 33.0 | CE aggressor → PE hedge \| 20 lots @ $33.00 \| loss covered $9.2000 \| gross $0.6600 | CE / FORCE_REDUCE | CE=500, PE=420 | CE=500, PE=440 | 0.0 | lat=57.0s, oid=1276015437 |
| 18 | 2026-04-16T06:12:46.884048+00:00 | Auto Close | BUY CE | C-BTC-76000-160426 | 76000 | 100 | 12.0 | Close-at-5 threshold hit — premium $12.00 ≤ $15 (entry $40.31) \| P&L $+2.8310 | - | CE=500, PE=440 | CE=400, PE=440 | 2.831 | lat=3.9s, oid=1276017329 |
| 19 | 2026-04-16T06:12:53.588353+00:00 | Reversal | SELL CE | C-BTC-75400-160426 | 75400 | 6 | 83.5 | Reversal: PE aggressor → CE hedge \| adj P&L was negative \| 6 lots @ $83.50 \| loss covered $0.1349 | PE / FORCE_REDUCE | CE=400, PE=440 | CE=406, PE=440 | 0.0 | lat=4.1s, oid=1276017411 |
| 20 | 2026-04-16T06:23:20.279781+00:00 | Adjustment | SELL CE | C-BTC-75400-160426 | 75400 | 14 | 72.0 | PE aggressor → CE hedge \| 14 lots @ $72.00 \| loss covered $0.4293 \| gross $1.0080 | PE / FORCE_REDUCE | CE=406, PE=440 | CE=420, PE=440 | 0.0 | lat=7.1s, oid=1276024891 |
| 21 | 2026-04-16T07:54:01.450695+00:00 | Auto Close | BUY CE | C-BTC-75400-160426 | 75400 | 100 | 16.0 | Close-at-5 threshold hit — premium $16.00 ≤ $25 (entry $104.50) \| P&L $+8.8500 | - | CE=420, PE=440 | CE=320, PE=440 | 8.85 | lat=4.3s, oid=1276106976 |
| 22 | 2026-04-16T07:54:09.701920+00:00 | Auto Close | BUY CE | C-BTC-75400-160426 | 75400 | 123 | 14.0 | Close-at-5 threshold hit — premium $14.00 ≤ $25 (entry $80.50) \| P&L $+8.1795 | - | CE=320, PE=440 | CE=197, PE=440 | 8.1795 | lat=4.0s, oid=1276107419 |
| 23 | 2026-04-16T07:55:22.905866+00:00 | Auto Close | BUY CE | C-BTC-75400-160426 | 75400 | 94 | 12.4787 | Close-at-5 threshold hit — premium $12.48 ≤ $25 (entry $96.50) \| P&L $+7.8980 | - | CE=197, PE=440 | CE=103, PE=440 | 7.898002 | lat=71.1s, oid=1276107732 |
| 24 | 2026-04-16T07:55:31.461181+00:00 | Auto Close | BUY CE | C-BTC-75400-160426 | 75400 | 46 | 14.0 | Close-at-5 threshold hit — premium $14.00 ≤ $25 (entry $103.50) \| P&L $+4.1170 | - | CE=103, PE=440 | CE=57, PE=440 | 4.117 | lat=3.9s, oid=1276110493 |
| 25 | 2026-04-16T07:56:06.640023+00:00 | Manual Action | SELL CE | C-BTC-75000-160426 | 75000 | 100 | 70.5 | Operator inject — manual lot placement @ strike 75000 | - | CE=57, PE=440 | CE=157, PE=440 | 0.0 | lat=7.1s, oid=1276111487 |
| 26 | 2026-04-16T07:56:43.997772+00:00 | Auto Close | BUY CE | C-BTC-75400-160426 | 75400 | 34 | 17.0 | Close-at-5 threshold hit — premium $17.00 ≤ $25 (entry $80.50) \| P&L $+2.1590 | - | CE=157, PE=440 | CE=123, PE=440 | 2.159 | lat=71.1s, oid=1276110688 |
| 27 | 2026-04-16T07:57:42.351649+00:00 | Auto Close | BUY CE | C-BTC-75400-160426 | 75400 | 14 | 14.0 | Close-at-5 threshold hit — premium $14.00 ≤ $25 (entry $72.00) \| P&L $+0.8120 | - | CE=123, PE=440 | CE=109, PE=440 | 0.812 | lat=55.2s, oid=1276112761 |
| 28 | 2026-04-16T07:58:24.368039+00:00 | Adjustment | SELL CE | C-BTC-75000-160426 | 75000 | 320 | 70.0 | PE aggressor → CE hedge \| 320 lots @ $70.00 \| loss covered $21.0194 \| gross $22.4000 | PE / FORCE_REDUCE | CE=109, PE=440 | CE=429, PE=440 | 0.0 | lat=9.4s, oid=1276114987 |
| 29 | 2026-04-16T08:03:51.807123+00:00 | Reversal | SELL PE | P-BTC-74600-160426 | 74600 | 158 | 145.5 | Reversal: CE aggressor → PE hedge \| adj P&L was negative \| 158 lots @ $145.50 \| loss covered $7.3653 | CE / FORCE_REDUCE | CE=429, PE=440 | CE=429, PE=598 | 0.0 | lat=71.5s, oid=1276122272 |
| 30 | 2026-04-16T08:07:02.029327+00:00 | Auto Close | BUY CE | C-BTC-75400-160426 | 75400 | 6 | 11.0 | Close-at-5 threshold hit — premium $11.00 ≤ $12 (entry $83.50) \| P&L $+0.4350 | - | CE=429, PE=598 | CE=423, PE=598 | 0.435 | lat=3.9s, oid=1276129241 |
| 31 | 2026-04-16T08:07:07.717178+00:00 | Auto Close | BUY CE | C-BTC-75400-160426 | 75400 | 3 | 11.0 | Close-at-5 threshold hit — premium $11.00 ≤ $12 (entry $123.00) \| P&L $+0.3360 | - | CE=423, PE=598 | CE=420, PE=598 | 0.336 | lat=3.9s, oid=1276129384 |

### Non-fill execution actions (fail/retry/cancel/sync actions)

| Time (UTC) | Event | Evidence | Operational Impact |
|---|---|---|---|
| 2026-04-16T04:49:48.029157 | `ORDER_INTENT` without terminal status | `1275945116` BUY 100 CE @ 8.00 in `session_event_log`; no confirm/cancel | Lifecycle observability gap; action outcome unknown from DB event stream |
| 2026-04-16T07:51:03 → 07:51:12 | Manual close attempt failed | `manual_close_strike` initiated for 420 CE @ 75400; then `manual_close_strike FAILED ... Order cancelled` in activity log | Manual override path did not complete; intent remained without confirm in session event table |
| 2026-04-16T07:55:14 | Repricing loop | `order_repricing` on `1276107732` after 60s | Added delay before closure confirmation; contributed to slow liquidation cadence |
| 2026-04-16T07:56:35 | Repricing loop | `order_repricing` on `1276110688` after 60s | Same bottleneck signature |
| 2026-04-16T08:03:42 | Repricing loop | `order_repricing` on `1276122272` after 60s | Largest late-session lag cluster; filled after 116.4s elapsed |
| 2026-04-16T07:53:02 | Auto-recon mismatch | `AUTO-RECON MISMATCH @ beat 200` with discrepancy `session_lots=420` vs `audit_open_qty=320` (PE 74400) | Confirms accounting/audit drift during live trading |

---

## 3. Mistakes Found

| Time | Issue | Root Cause | P&L Damage | Confidence | Fix Suggestion |
|---|---|---|---|---|---|
| 03:12:24 | Confirmed replenish fill missing from `position_audit_log` | Replenish order path (`1275862757`) confirmed in event log and session state but not written into position audit table | Direct: `$0`; Indirect: audit drift / reconciliation noise | High | Enforce **1:1 invariant**: every confirmed fill must create exactly one position-audit row; fail loudly if not |
| 04:49:48 | Intent with no terminal status (`1275945116`) | Lifecycle logging incomplete (no `ORDER_CONFIRMED`/`ORDER_CANCELLED`) | Unknown (possible missed close opportunity; not provable) | Medium | Add mandatory `ORDER_CANCELLED`/`ORDER_EXPIRED` events in `session_event_log` |
| 07:51:03–07:51:12 | Manual close order placed then cancelled (`1276102923`) but no matching cancel event in session-event table | Split logging planes (`activity_log` vs `session_event_log`) not reconciled | Direct P&L ambiguous; operational confusion high | High | Single-source order lifecycle stream + cross-log reconciliation watchdog |
| 07:37–08:08 | Repeated `dangerous_mode_bypass` while at cap and in EMERGENCY gamma | Safety gate bypass policy too permissive under stressed state | Contributed to risk escalation and late drawdown (`$16.96` from peak to trough in final segment) | Medium-High | Disallow dangerous-mode bypass when `gamma_regime=EMERGENCY` unless explicit per-action operator approval |
| 07:39–08:07 | `shift_no_strike` storm (24 events) + fallback blocked (11) | Shift threshold/fallback constraints too strict for late-session liquidity regime | Missed/late hedge path; increased churn pressure | High | DTE-aware adaptive shift threshold + emergency lower-premium strike fallback ladder |
| Session-wide | Slow fills and repricing loops (5 fills >60s) | Execution path too slow for size/market microstructure; repricing starts after long waits | Measurable adverse slippage floor: at least `~$1.20` from stale intents/fill drift | High | Child-order slicing, faster repricing cadence, async quote path, latency-aware size throttling |
| 07:51 and 07:58 | Reconciliation mismatches (`untracked CE`, external PE excess, PE delta -100) | Mixed ownership at exchange + audit table incompleteness | Unknown direct P&L; high monitoring risk | High | Hard ownership tagging + external-position quarantine + stricter reconciliation classification |
| Session stop | Stop reason empty, despite significant open exposure | Stop lifecycle metadata incomplete | No direct P&L number; post-mortem ambiguity | Medium | Persist canonical stop reason enum and trigger source in DB |

### Bug loss vs market loss (explicit separation)

| Bucket | Amount / Effect | Notes |
|---|---|---|
| Market-driven realized loss | `-$4.894` | PE ATM-shield close near session start |
| Realized gains from strategy exits | `+$35.6175` | CE close-at-5 sequence |
| Net realized | `+$30.7235` | Before unrealized and fees |
| Open-risk mark-to-market at stop | `-$12.831973` | Large residual PE inventory remained |
| Fees (execution + churn cost) | `-$5.9877153` | 31 confirmed fills + retries/repricing context |
| Proven execution-quality drag | `~-$1.20` (minimum) | From observable adverse mid→fill slippage outliers (conservative floor) |

---

## 4. Slowdown / Bottlenecks

| Bottleneck | Evidence | Impact | Priority | Improvement |
|---|---|---|---|---|
| Intent→confirm latency spikes | p50 `10.3s`, p90 `71.1s`, max `133.8s` (31 confirms) | Delayed hedge/close reactions; stale price risk | P0 | Quote-time budget + IOC/FOK/sliced ladder + dynamic timeout profile by liquidity regime |
| Order repricing waits too long | 3 repricing events only after ~60s (`attempt 1/4`) | Idle waits in fast market; worsens fill drift | P1 | Start repricing earlier for near-expiry/high-gamma states (e.g., 20–30s) |
| Fill-sync lag (polling confirmation lag) | `order_filled → fill_sync_confirmed` lag p50 `63.6s`, p90 `154.4s` | UI/state stale; delayed reconciliation truth | P1 | Push-based fill updates (WS if available) + faster sync cycle after filled events |
| Shift candidate starvation | `shift_no_strike` 24 times, `cap_auto_shift` 20, fallback blocked 11 | Adjustment path repeatedly blocked; no clean strike migration | P0 | DTE-adaptive strike search constraints and liquidity-aware minimum premium target |
| Safety warning storm / bypass churn | 25 `safety_warning`, 31 `dangerous_mode_bypass` | Operator signal fatigue; elevated chance of poor override decisions | P1 | Collapse duplicate alerts + cooldown on repeated identical warnings |
| Heartbeat cadence degradation | PnL history interval p50 `88s`, p95 `123.6s`, max `247.7s` | Control loop slower than intended under load | P1 | Reduce synchronous work per beat; profile and parallelize long-latency sections |

---

## 5. Profitability Opportunities

### A. Quick Wins (easy + high value)
1. **Close lifecycle completeness gap**: enforce terminal status for every order intent (`confirmed/cancelled/expired`).
2. **Mandatory audit write on confirmed fills**: block/save alarm if a confirmed fill misses `position_audit_log`.
3. **DTE-adaptive shift settings**: automatically relax `shift_threshold` near expiry when no candidates for N beats.
4. **Dangerous-mode guardrails**: forbid bypass when cap+gamma emergency are simultaneous.
5. **Latency-aware execution sizing**: auto-split large close/hedge orders during high-latency windows.

### B. Medium Improvements
1. **Active vs frozen exposure policy**: separate risk budgets for active and frozen inventories.
2. **Reversal throttling by realized edge**: skip/add hysteresis when expected edge < fees+slippage.
3. **Dynamic close-at-5 per side**: CE/PE thresholds adapt to side risk and liquidity.
4. **Auto de-risk runbook**: if `shift_no_strike` repeats beyond threshold, trigger controlled lot reduction instead of repeated failed shift attempts.
5. **Cross-log integrity monitor**: compare event log, activity log, and audit table every beat.

### C. Advanced Research Ideas
1. **Microstructure-aware execution model** (fill probability + expected slippage by size and DTE).
2. **State-machine simulation for cap/freeze regimes** to optimize transition policy.
3. **Policy optimizer for threshold stack** (`close_at_threshold`, `shift_threshold`, fallback floor) by volatility regime.
4. **Adaptive hedge cadence** based on gamma severity + observed latency distribution.
5. **Operator-assist model** that flags “override likely harmful” based on historical outcomes.

### D. Dangerous Ideas (test-only)
1. Always-on dangerous mode in high gamma.
2. Raising `max_lots_per_side` during shift starvation.
3. Disabling close-at-5 to chase premium decay longer.
4. Aggressive manual injection against reconciliation warnings.
5. Ignoring margin warnings during cap loops.

---

## 6. What Human Trader Would Have Done Differently

A disciplined discretionary desk would likely have:
1. **Cut risk when cap+no-strike loop started** (instead of repeatedly trying blocked shifts).
2. **Avoided safety bypass repetition** under EMERGENCY gamma.
3. **Handled cancelled 420-lot close with immediate explicit re-entry plan** (not ad-hoc patching via multiple threshold toggles).
4. **Reduced PE frozen inventory earlier** once PE side became structurally dominant risk.
5. **Stabilized parameter regime** (fewer rapid threshold flips) to reduce strategy churn and execution noise.

---

## 7. Top 5 Immediate Fixes

1. **Enforce fill→audit parity invariant** (`confirmed fills == position_audit rows` per session).
2. **Add explicit order terminal events** (`ORDER_CANCELLED`, `ORDER_EXPIRED`, `ORDER_REPRICED`).
3. **Implement DTE-aware strike-shift degradation logic** when `shift_no_strike` repeats.
4. **Hard safety interlock for dangerous mode in EMERGENCY gamma + cap reached states**.
5. **Introduce latency-aware execution playbook** (slice large tickets, faster repricing, post-fill fast-sync).

---

## 8. Top 5 Research Ideas

1. Multi-objective optimizer for **profit capture vs risk carry vs fee drag**.
2. Regime-conditioned policy for **frozen inventory unwind**.
3. Trade classifier to predict **when reversal should be skipped** despite trigger hit.
4. Best-execution model using **intent→fill latency features**.
5. Shadow-book simulator for **manual override what-if replay**.

---

## 9. Session Scorecard

| Dimension | Score (0-10) | Rationale |
|---|---:|---|
| Execution Quality | 4.5 | Several long-latency fills; one canceled large close; lifecycle logging gaps |
| Risk Control | 3.5 | Persistent cap warnings + EMERGENCY gamma + high open inventory at stop |
| Speed | 4.0 | Frequent >60s order cycles and repricing delays |
| Decision Quality | 4.5 | Strong CE monetization, but repeated blocked shift loop and bypass churn |
| Capital Efficiency | 3.5 | High lot saturation and warning storm imply stressed capital usage |
| Profit Capture | 6.0 | Realized capture good, but large unrealized giveback and fee drag |
| Stability | 4.5 | No crash, but high warning density and reconciliation noise |
| Robustness | 3.5 | Missing audit row + incomplete terminal statuses + cross-log inconsistency |

**Overall grade:** **4.3 / 10 (C-)**  
(Internal `performance_sessions.session_score` recorded: `2.0`, directionally consistent with a fragile run despite positive net result.)

---

## 10. Final Verdict

This was a **net-profitable but structurally fragile** session.

- The system extracted meaningful realized profit via CE close-at-5 exits.
- However, the run relied on repeated safety bypasses under stress, suffered recurring shift-block loops, and showed order lifecycle/audit consistency gaps.
- The session ended with substantial open-risk inventory and weak exit cleanliness (`exit_quality: MESSY`, `exit_pct_closed: 22.8`).

**Bottom line:** good tactical profit capture, but **not prop-desk-grade operational quality yet**.  
Fix the lifecycle integrity + shift starvation + latency stack before trusting this configuration for unattended high-size deployment.
