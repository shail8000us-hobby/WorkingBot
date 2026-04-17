# MMM Session Forensic Audit Report

**Session audited:** `mmm17apr26-5`  
**Strategy:** `STRADDLE_WITH_ADJUSTMENT`  
**Status at end:** `STOPPED`  
**Evidence cut date:** 2026-04-17

---

## 1. Executive Summary

Session `mmm17apr26-5` was **profitable but operationally unstable**.

- **Session window:** 2026-04-16T18:51:33.271738+00:00 → 2026-04-17T03:09:50.943761+00:00 (`498.3 min`)
- **Final total P&L:** `+11.971342`
- **Final realized P&L:** `0.000000`
- **Final unrealized P&L:** `+11.971342`
- **Estimated fees (fill-ledger commission sum):** `0.782854`
- **Estimated net (total - fees):** `+11.188488`
- **Max drawdown:** `5.158107`
- **Final inventory:** `CE 23 @ 74400`, `PE 142 @ 74400`
- **Stop metadata (performance row):** `Unrecoverable error: NameError`
- **Session state error field:** `name 'strike_key' is not defined`

### High-confidence headline findings

1. **Crash-stop signature present**: performance stop reason + `last_error` both indicate a `NameError` halt. **[Confidence: High]**
2. **Execution lifecycle integrity was clean** for executed orders: `3 intents = 3 confirms = 3 audit rows`, no partial fills. **[Confidence: High]**
3. **Trigger dead-zone was severe**: PE trigger fired repeatedly, but most beats still ended with `type=none` under cap/safety blocks. **[Confidence: High]**
4. **No de-risk closure occurred**: `0` close-at-threshold events, `0` realized P&L despite long run and repeated regime stress. **[Confidence: High]**

---

## 2. Evidence Coverage (Requested Sources)

| Source bucket | Used for this report | Coverage |
|---|---|---|
| Orders / intents / confirms | `session_event_log` | ✅ |
| Fills / audit lifecycle | `position_audit_log` + `_fill_ledger` | ✅ |
| Position history | `ce/pe state`, `adjustment_history` | ✅ |
| Session state / timeline | `mmm_sessions.data_json` | ✅ |
| Trigger/decision traces | `_walkthrough_log` textual entries | ✅ |
| Risk/regime state | `transition` events + regime fields | ✅ |
| Analytics summary | `mmm_analytics.analytics_json` | ✅ |
| Scorecard summary | `performance_sessions` | ✅ |
| Activity/errors side stores | checked previously for this SID (no retained rows) | ⚠️ partial retention |

---

## 3. Full Chronological Timeline

| # | Time (UTC) | Event | Evidence | Impact |
|---:|---|---|---|---|
| 1 | 18:51:20.249 | Hot reload batch | `close_at_threshold 5→15`, `max_lots_per_side 5→100`, `shift_target_premium 100→350`, `shift_threshold 30→150` | Risk envelope widened early |
| 2 | 18:52:33.309 | Hot reload | `min_trigger_move 50→20` | Trigger sensitivity raised |
| 3 | 18:53:43.388 | ORDER_INTENT (SELL PE) | 54 lots @ mid 197.5 (`order_id=1277268395`) | Adjustment launch |
| 4 | 18:54:01.194 | ORDER_CONFIRMED | Fill 54 @ 235.0 | Favorable execution vs mid |
| 5 | 18:54:01.195 | Audit row persisted | `ADJUSTMENT/standard`, aggressor `ce` | Lifecycle parity intact |
| 6 | 18:56:06.157 | Hot reload | `max_lots_per_side 100→150` | Cap raised again |
| 7 | 18:58:09.643 | Hot reload batch | `adjustment_interval 120→300`, `max_loss_amount 3000→100` | Wider interval + tighter loss ceiling |
| 8 | 19:39:10.916 | Regime transition | `NORMAL → WARN` | Risk posture tightened |
| 9 | 19:39:12.642 | ORDER_INTENT (SELL PE) | 19 lots @ mid 169 (`order_id=1277326262`) | 2nd adjustment |
| 10 | 19:39:23.022 | ORDER_CONFIRMED | Fill 19 @ 169.0 | Neutral vs mid |
| 11 | 20:11:55.351 | ORDER_INTENT (SELL PE) | 37 lots @ mid 113 (`order_id=1277360574`) | 3rd adjustment |
| 12 | 20:12:02.517 | ORDER_CONFIRMED | Fill 37 @ 113.0 | Neutral vs mid |
| 13 | 21:12:11.060 → 03:09:49.688 | Regime flips | WARN↔NORMAL↔BLOCK_PE_SELLS (HARD/SOFT gamma alternation) | Prolonged blocked posture |
| 14 | End of session | STOPPED | no `stopped` lifecycle row in `session_event_log`; performance row marks NameError stop | Non-clean termination path |

### Event totals

- `session_event_log` rows: **23**
  - `ORDER_INTENT=3`, `ORDER_CONFIRMED=3`, `hot_reload=8`, `transition=9`
- `position_audit_log` rows: **3**
- `_fill_ledger` rows: **3** (all fee-only adjustment entries)

---

## 4. Execution Quality (Desk-Style)

### 4.1 Intent → confirm latency

From event timestamp pairing by `order_id`:

- Min: `7.166s`
- P50: `10.380s`
- P90: `16.321s`
- Max: `17.806s`
- Avg: `11.784s`

Interpretation: materially faster than session 4, but still non-trivial for high-vol 0DTE microstructure.

### 4.2 Slippage vs intent mid

Signed slippage (sell better than mid is positive):

- Order `1277268395`: `+2.025 USD`
- Order `1277326262`: `0.000 USD`
- Order `1277360574`: `0.000 USD`
- **Total signed slippage:** `+2.025 USD`

### 4.3 Confirm → audit write lag

- Matched rows: `3/3`
- Lag range: `0.000936s` to `0.001510s`
- Mean lag: `~0.00123s`

Interpretation: persistence path for confirmed fills was healthy in this session.

---

## 5. Trigger / Decision Forensics

Walkthrough parsing (`_walkthrough_log`, 200 records):

- Types: `none=197`, `standard=1`, `shift=1`, `first_reversal=1`
- PE-trigger YES detections: `148`
- Trigger-YES but `none`: `147`
- Safety-block markers observed in walkthrough details:
  - `asymmetry`: `200`
  - `position_cap`: `185`
  - `lot_velocity`: `24`

### Interpretation

This is a classic **triggered-but-blocked dead-zone**:

- Signals repeatedly called for action on PE pressure,
- but policy gates (especially cap/asymmetry) kept outcomes at `none` most of the time,
- resulting in little realized harvesting and prolonged open exposure.

---

## 6. State & P&L Path Consistency

### 6.1 Position evolution

- Initial lots (analytics): `CE 23`, `PE 32`
- Final lots (analytics): `CE 23`, `PE 142`
- Traded lots: `CE 0`, `PE 73` (3 PE sells)
- Adjustments by type: `standard=2`, `shift_fallback=1`, plus one `reversal_skip` marker in history

### 6.2 P&L path

From `pnl_history` parsed points:

- Start: `-1.330992`
- Peak: `+12.094510`
- Trough: `-5.600732`
- Last recorded point: `+10.508841`

From analytics/performance finals:

- Final total: `+11.971342`

Note: end-of-series `pnl_history` point vs final snapshot differ; likely due late-state mark/update timing near stop.

---

## 7. Mistakes, Bottlenecks, and Classification

| Issue | Evidence | Avoidable? | Confidence | Impact |
|---|---|---|---|---|
| Runtime crash-stop (`NameError`) | `performance_sessions.stop_reason='Unrecoverable error: NameError'`, `last_error='name \'strike_key\' is not defined'` | **Yes** | **High** | Session ended in broken-control path |
| Trigger dead-zone under blocks | 148 PE trigger YES, 147 ended `none`; cap/asymmetry flags dominant | **Yes** | **High** | Missed de-risk/harvest actions |
| No closure despite long session | `close_at_5=0`, realized P&L remained 0 | **Partly** | **High** | P&L remained mostly unrealized |
| Parameter churn early session | 8 hot-reloads, several risk knobs changed within minutes | **Yes** | **Medium** | Increased policy instability |
| Missing explicit stopped lifecycle event | no `stopped` row in session event log | **Yes** | **Medium** | Weaker forensic traceability |
| Market path / premium regime shifts | multiple regime flips HARD/SOFT/WARN/BLOCK | **No (intrinsic)** | **High** | Environmental stress (not itself a bug) |

---

## 8. Profitability & Robustness Improvements

### Immediate (P0)

1. **Crash-proof guardrail for undefined symbols** in monitor critical paths (pre-run lint/static check + runtime sentinel).
2. **Blocked-trigger fallback policy:** if trigger YES but sell blocked by cap, execute risk-reducing alternative (trim/close/hard hedge).
3. **Mandatory stop lifecycle write** even for unrecoverable exceptions.

### Near-term (P1)

1. Add PE-asymmetry governor to prevent prolonged one-sided buildup.
2. Add operator guardrails for clustered hot-reloads in live mode.
3. Track trigger-to-action suppression metrics directly in analytics JSON (not only walkthrough text).

---

## 9. Session Scorecard

| Dimension | Score (/10) | Why |
|---|---:|---|
| Execution fill quality | 7.5 | Slippage favorable; no partials; clean audit pairing |
| Control-path reliability | 3.0 | Session ended by NameError |
| Risk control | 4.0 | Persistent BLOCK_PE_SELLS posture with large open PE |
| Profit realization | 3.5 | 0 realized despite full session runtime |
| Forensic trace quality | 5.0 | Core evidence strong, but missing explicit stop lifecycle row |

**Overall grade: `C-`**

---

## 10. Final Verdict

`mmm17apr26-5` made money on paper, but the process failed desk reliability standards.

The session demonstrates a dangerous combination:

- repeated actionable trigger pressure,
- policy dead-zone under safety blocks,
- and eventual crash-stop (`NameError`) before structured cleanup.

**Desk verdict:** _“Profitable snapshot, but control-plane integrity is below scale-ready threshold.”_
