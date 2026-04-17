# MMM Session Forensic Audit Report

**Session audited:** `mmm17apr26-4`  
**Strategy:** `0DTE` (adopted inventory)  
**Status at end:** `STOPPED`  
**Evidence cut date:** 2026-04-17

---

## 1. Executive Summary

This session was **profitable**, but structurally fragile.

- **Final realized P&L:** `+33.34254`
- **Final unrealized P&L:** `+12.533119`
- **Final total P&L (realized + unrealized):** `+45.875659`
- **Final net P&L after fees:** `+43.19531`
- **Total fees:** `2.68034935`
- **Duration:** `~8.31h` (216 heartbeat snapshots)

### Hard findings (high confidence)

1. **Confirmed execution missing in trade audit table:** order `1277579424` (SELL 300 CE @ 123.5) exists in `session_event_log` + session state, but **no `position_audit_log` row**.
2. **Control-path conflict:** session ended in `_regime_action=FORCE_REDUCE` + `_gamma_regime=EMERGENCY`, while walkthrough shows persistent cap-based blocks.
3. **Execution speed was slow for 0DTE context:** intent→confirm latency p50 `53.0s`, max `69.8s`.
4. **Large decision dead-zone:** 51 beats where trigger calc showed `YES` but outcome stayed `none` (blocked by safety/cap constraints).
5. **Stop forensic metadata weak:** stop reason persisted empty.

### Data-source coverage map (requested 1→18)

| Requested source | Evidence used | Coverage |
|---|---|---|
| 1) Orders table | `session_event_log` ORDER_INTENT (9) | ✅ |
| 2) Fills table | ORDER_CONFIRMED (9), `position_audit_log` (8), `_fill_ledger` (9) | ✅ (with mismatch) |
| 3) Position history | `ce/pe.positions`, `adjustment_history`, `position_audit_log` | ✅ |
| 4) Session state history | `pnl_history` (216), `_walkthrough_log` (200) | ✅ |
| 5) Activity logs | `mmm_activity_log.json`, `activity_log.db` | ⚠️ No retained rows for this session |
| 6) Error logs | `errors.db`, production logs | ⚠️ No session-linked runtime faults retained |
| 7) Trigger events | `_walkthrough_log.calculation/outcome` | ✅ |
| 8) Strategy decisions | `_walkthrough_log.details/type/outcome` | ✅ |
| 9) Price data | `pnl_history` (CE/PE premium), `_vol_spot_history` (60) | ✅ |
| 10) Greeks/risk | `_gamma_result`, `_gamma_history`, regime fields | ✅ |
| 11) Heartbeat timings | `_heartbeat_counter`, `pnl_history` intervals | ✅ |
| 12) API latency | No explicit API telemetry; inferred from intent→confirm | ⚠️ Partial |
| 13) Rejections/partials | `session_event_log`, `position_audit_log` | ✅ (none found) |
| 14) Margin changes | walkthrough margin warnings (529→600 total lots) | ✅ |
| 15) Manual overrides | PARAM_CHANGE events (6), stop lifecycle event | ✅ |
| 16) DB timestamps | confirm↔audit timestamp delta analysis | ✅ |
| 17) WS vs polling timing | No session-window transport logs retained; fill-sync lag inferred | ⚠️ Partial |
| 18) Realized+unrealized path | `pnl_history` with realized jumps | ✅ |

### Assumptions / explicit limits

- Session stop reason in DB is empty (`""`), so stop trigger source (manual vs expiry auto-stop) is not provable from DB alone.
- Activity/error logs for this older window appear rotated/pruned; conclusions rely on SQL + session-state evidence.
- No explicit per-API call latency table exists for this session.

---

## 2. Full Trade Timeline

**Timezone in table:** UTC (`created_at` aligned).  
This sheet includes all material actions: adoption, manual config overrides, all order lifecycles, structural state transitions, and stop.

| # | Time | Event Type | Side | Instrument | Strike | Qty | Price | Reason | Trigger Source | Before State | After State | P&L Impact | Notes |
|---:|---|---|---|---|---:|---:|---:|---|---|---|---|---:|---|
| 1 | 2026-04-16T18:48:24.750 | Adopt Inventory | CE+PE | C-BTC-76000 / P-BTC-73200 | 76000/73200 | 104/120 | 226.26 / 103.0 | Session started in adopt mode | Adopt path | Flat monitor | CE active 104, PE active 120 | 0 | `entry_mode=adopt` |
| 2 | 2026-04-16T18:49:06.927 | Manual Override (Batch) | Config | params | — | — | — | Live param hot reload | UI/API | Default risk profile | `atm_shield_proximity_pct` 0.5→0.1, `close_at_threshold` 5→15, `lot_velocity_limit` 30→60, `max_lots_per_side` 100→300, `shift_recycle_enabled` false→true | 0 | 5 changes at same timestamp |
| 3 | 2026-04-16T18:53:37.583 | Order Intent | SELL | P-BTC-73800-170426 | 73800 | 120 | 105.0 (mid) | Shift PE strike up | Strike-shift logic | PE active 120 @73200 | Pending sell | 0 | `order_id=1277268177` |
| 4 | 2026-04-16T18:53:41.670 | Fill Confirmed | SELL | P-BTC-73800-170426 | 73800 | 120 | 105.0 | PE strike shift executed | `STRIKE_SHIFT` | PE active 120 @73200 | PE active 120 @73800 + PE frozen 120 @73200 | 0 | intent→confirm `4.09s`; audit row present (`id=3409`) |
| 5 | 2026-04-16T18:53:41.671 | Strike Shift State Event | PE | — | 73200→73800 | 120 | 105.0 | Old premium below threshold | shift engine | PE active 73200 | PE active moved to 73800 | 0 | `session_event_log: shifted` |
| 6 | 2026-04-16T18:58:18.468 | Manual Override | Config | params | — | — | — | Tightened hard loss guard | UI/API | `max_loss_amount=5000` | `max_loss_amount=100` | 0 | Forensic-significant human intervention |
| 7 | 2026-04-16T19:26:14.586 | Order Intent | SELL | C-BTC-76000-170426 | 76000 | 5 | 131.5 (mid) | First reversal hedge | Reversal logic | CE active 104 | Pending sell | 0 | `order_id=1277309861` |
| 8 | 2026-04-16T19:27:07.613 | Fill Confirmed | SELL | C-BTC-76000-170426 | 76000 | 5 | 131.5 | Reversal executed | `first_reversal`, aggressor=PE | CE active 104 | CE active 109 | 0 | intent→confirm `53.03s`; audit row `id=3411` |
| 9 | 2026-04-16T19:33:43.153 | Order Intent | SELL | P-BTC-73800-170426 | 73800 | 4 | 83.5 (mid) | Reversal hedge | Reversal logic | PE active 120 (+frozen 120) | Pending sell | 0 | `order_id=1277319264` |
| 10 | 2026-04-16T19:34:04.830 | Fill Confirmed | SELL | P-BTC-73800-170426 | 73800 | 4 | 83.5 | Reversal executed | `first_reversal`, aggressor=CE | PE active 120 (+frozen 120) | PE active 124 (+frozen 120) | 0 | intent→confirm `21.68s`; audit row `id=3412` |
| 11 | 2026-04-16T19:38:49.292 | Order Intent | SELL | P-BTC-73800-170426 | 73800 | 54 | 72.5 (mid) | Standard adjustment | CE trigger path | PE active 124 (+frozen 120) | Pending sell | 0 | `order_id=1277325770` |
| 12 | 2026-04-16T19:39:28.555 | Fill Confirmed | SELL | P-BTC-73800-170426 | 73800 | 54 | 72.5 | Standard adjustment executed | `standard`, aggressor=CE | PE active 124 (+frozen 120) | PE active 178 (+frozen 120) | 0 | intent→confirm `39.26s`; audit row `id=3414` |
| 13 | 2026-04-16T19:58:51.353 | Order Intent | SELL | P-BTC-73800-170426 | 73800 | 122 | 58.5 (mid) | Standard adjustment | CE trigger path | PE active 178 (+frozen 120) | Pending sell | 0 | `order_id=1277346977` |
| 14 | 2026-04-16T19:59:47.533 | Fill Confirmed | SELL | P-BTC-73800-170426 | 73800 | 122 | 58.5 | Standard adjustment executed | `standard`, aggressor=CE | PE active 178 (+frozen 120) | PE active 300 (+frozen 120), cap saturation starts | 0 | intent→confirm `56.18s`; audit row `id=3416` |
| 15 | 2026-04-17T01:07:27.624 | Order Intent | BUY | P-BTC-73200-170426 | 73200 | 120 | 13.0 (mid) | Close-at-5 | Auto close | PE frozen 120 @73200 exists | Pending buy | 0 | `order_id=1277481046` |
| 16 | 2026-04-17T01:08:37.446 | Fill Confirmed | BUY | P-BTC-73200-170426 | 73200 | 120 | 14.0 | Close-at-5 executed | `close_at_5` | PE active 300 + frozen 120 | PE active 300 (frozen removed) | **+10.6800** | intent→confirm `69.82s`; fill-sync lag `78.88s`; audit row `id=3418` |
| 17 | 2026-04-17T03:03:32.298 | Order Intent | BUY | C-BTC-76000-170426 | 76000 | 5 | 14.0 (mid) | Close-at-5 | Auto close | CE active 109 | Pending buy | 0 | `order_id=1277578258` |
| 18 | 2026-04-17T03:04:25.408 | Fill Confirmed | BUY | C-BTC-76000-170426 | 76000 | 5 | 14.0 | Close-at-5 executed | `close_at_5` | CE active 109 | CE active 104 | **+0.5875** | intent→confirm `53.11s`; fill-sync lag `100.33s`; audit row `id=3420` |
| 19 | 2026-04-17T03:04:28.461 | Order Intent | BUY | C-BTC-76000-170426 | 76000 | 104 | 14.0 (mid) | Close-at-5 | Auto close | CE active 104 | Pending buy | 0 | `order_id=1277579038` |
| 20 | 2026-04-17T03:04:47.376 | Fill Confirmed | BUY | C-BTC-76000-170426 | 76000 | 104 | 14.0 | Close-at-5 executed | `close_at_5` | CE active 104 | CE active 0 | **+22.0750** | intent→confirm `18.91s`; fill-sync lag `78.16s`; audit row `id=3421` |
| 21 | 2026-04-17T03:04:57.921 | Order Intent | SELL | C-BTC-75000-170426 | 75000 | 300 | 123.5 (mid) | Replenish CE side | Replenish logic | CE active 0, PE active 300 | Pending sell | 0 | `order_id=1277579424` |
| 22 | 2026-04-17T03:05:56.144 | Fill Confirmed | SELL | C-BTC-75000-170426 | 75000 | 300 | 123.5 | Replenish executed | `aggressor=REPLENISH` | CE active 0, PE 300 | CE active 300 @75000, PE active 300 | 0 | intent→confirm `58.22s`; **no `position_audit_log` row** |
| 23 | 2026-04-17T03:05:57.868 | Risk Regime Escalation | Portfolio | — | — | — | — | Gamma spike near stop window | Regime engine | WARN/SOFT prior | `_gamma_regime=EMERGENCY`, `_regime_action=FORCE_REDUCE` | 0 | `_portfolio_dollar_gamma=13147.67` |
| 24 | 2026-04-17T03:06:44.650 | Session Stop | Control | — | — | — | — | Stop lifecycle event | Stop request / expiry context | RUNNING | STOPPED | 0 | Stop reason persisted empty (`""`) |

### Chronological integrity checks

- `session_event_log` ORDER_INTENT count = `9`, ORDER_CONFIRMED count = `9`
- `position_audit_log` rows = `8` (missing confirmed replenish order `1277579424`)
- `is_partial_fill=0` for all audited fills
- confirm→audit write lag is tiny for matched rows (`~0.0004s` to `0.1868s`), except one missing row

---

## 3. Mistakes Found

| Time | Issue | Root Cause | P&L Damage | Confidence | Fix Suggestion |
|---|---|---|---:|---|---|
| 2026-04-17 03:05:56 | Confirmed fill missing from `position_audit_log` (`1277579424`) | Replenish fill path did not persist full audit row (only fee-only ledger item persisted) | Direct: `0`; Indirect: audit inconsistency / forensic blind spot | **High** | Enforce invariant: every ORDER_CONFIRMED must create one position audit row (including replenish) |
| 2026-04-16 20:01 onward | Trigger YES but no action on 51 beats | Safety gates (position cap, lot velocity, asymmetry/margin) overrode trigger path, creating decision dead-zone | Opportunity/risk management impact unquantified | **High** | Add explicit “blocked-trigger” handler: when trigger YES + cap block, execute risk-reducing alternative (close/trim) |
| 2026-04-16 20:01 onward | FORCE_REDUCE state but cap-lock behavior | Risk regime asked for reduction while sell-side cap logic blocked new hedge sells; no alternate reducer path | Potentially avoidable risk carry | **High** | Separate risk-adding cap from risk-reducing actions; FORCE_REDUCE should bypass/add close-first path |
| 2026-04-17 03:04:57–03:06:44 | Replenish 300 CE very near stop/expiry window | Replenish logic remained active after aggressive close-at-5 harvest, re-risking late in session | Approx. drawdown from peak to post-replenish zone: `~2.9` total P&L points (not fully attributable) | **Medium** | Disable replenish when time-to-stop/expiry is small, or when gamma already stressed |
| Session-wide | Slow order lifecycle for 0DTE conditions | Execution path and/or exchange fill wait produced long intent→confirm times (p50 53s) | Measured slippage floor `-0.12` on one close; additional latent risk during wait | **Medium-High** | Use adaptive execution policy (size slicing, faster reprice, urgency profile near expiry) |
| Session-wide | Fill synchronization lag | Estimated fill booking to confirmed sync took `78–100s` on close fills | Stale UI/state and delayed operator confidence | **Medium** | Add push-ack sync (WS-driven) and immediate high-priority fill reconciliation |
| Stop event | Blank stop reason | Stop metadata not enforced | Forensic quality loss (no direct P&L impact) | **High** | Make stop reason mandatory enum + actor source |
| Session startup (manual ops) | Aggressive manual parameter escalation | `max_lots_per_side` raised 100→300 and velocity limit 30→60 immediately after adoption | Enabled larger later concentration (600 combined lots) | **Medium** | Two-step approval / guardrail checks for large live cap changes |

### Bug loss vs market loss (explicit separation)

- **Bug / system-design loss domain:** audit-row miss, cap-vs-force_reduce conflict, late replenish behavior, telemetry gaps.
- **Market/execution loss domain (measured):** one close fill at 14 vs mid 13 (`-0.12`).
- **Unavoidable vs avoidable:** market move component is unavoidable; late replenish + control dead-zone are likely avoidable with rule changes.

---

## 4. Slowdown / Bottlenecks

| Bottleneck | Evidence | Impact | Priority | Improvement |
|---|---|---|---|---|
| Order confirm latency | Intent→confirm p50 `53.0s`, p90 `58.2s`, max `69.8s` | Slow reaction in 0DTE microstructure | **P0** | Adaptive urgency execution; size slicing; dynamic repricing windows |
| Fill sync delay (state convergence) | `_fill_ledger` estimated→confirmed lag `78–100s` | State/UI lag, delayed trust in position truth | **P1** | WS-ack + high-priority fill sync task |
| Position-cap lock | 187/200 walkthrough beats include `position_cap` blocks | Trigger engine frequently neutralized | **P0** | Risk-reduction lane independent of sell-cap |
| Margin stress persistence | 124 margin warnings; utilization moved 529→600 lots (cap ref 450) | Chronic stressed posture | **P1** | Dynamic size throttling and forced de-risk ladder |
| Safety gate stacking | `lot_velocity` flagged 22 beats + cap + asymmetry overlap | Compounding blocks, missed adaptive actions | **P1** | Gate arbitration priority + explainable fallback actions |
| Observability retention gap | No session-4 activity records in JSON/DB activity stores | Forensic depth reduced post hoc | **P1** | Per-session immutable activity archive, retention SLA |

### Heartbeat timing audit

- `pnl_history` points: `216`
- Derived cadence: min `9.15s`, p50 `149.85s`, p90 `157.26s`, max `237.76s`, avg `138.85s`
- Config had `adaptive_interval_enabled=true`; observed cadence indicates adaptive behavior, not fixed interval.

### WS vs polling evidence status

- Session-window transport logs were not retained for this run.
- Indirect evidence: fill confirmation sync lag (`78–100s`) suggests polling/reconciliation bottleneck post-fill.
- Current logs (post-session) show heavy `socket.io` polling and many global queue-drop warnings, but this is not directly attributable to this session window.

---

## 5. Profitability Opportunities

### A) Quick Wins (easy, high value)

1. **No-replenish zone near expiry/stop** (time-to-expiry or time-to-stop guard).
2. **FORCE_REDUCE override path** that can always reduce net risk despite sell caps.
3. **Mandatory audit parity** for all confirmed fills (especially replenish path).
4. **Execution urgency profile for 0DTE** (faster reaction and repricing).
5. **Stop-reason enforcement** to preserve post-trade learning quality.

### B) Medium Improvements

1. Split caps into **risk-adding cap** vs **risk-reducing cap**.
2. Add blocked-trigger policy: trigger YES + blocked ⇒ execute alternate reducer.
3. Add per-leg “time-to-expiry mode” (harvest/flatten bias over replenishment bias).
4. Better asymmetry-aware inventory controller (avoid prolonged 420 vs 109 style skew states).
5. Improve state sync UX with fill confidence/latency telemetry.

### C) Advanced Research Ideas

1. Learnable policy for cap arbitration under gamma stress.
2. Portfolio gamma-aware close scheduling (maximize theta capture under risk bound).
3. Simulation-based optimizer for `close_at_threshold`, `shift_threshold`, and velocity limits by regime.
4. Fill-probability model for choosing limit aggressiveness by microstructure state.
5. Multi-session ownership resolver to reduce reconciliation ambiguity across overlapping MMM books.

### D) Dangerous Ideas (test only)

1. Disable caps in emergency (can explode exposure if wrong).
2. Always replenish both legs regardless time-to-expiry.
3. Force market orders on every trigger near expiry.
4. Remove lot-velocity gate completely.
5. Single-rule gamma flatten without liquidity conditioning.

---

## 6. What Human Trader Would Have Done Differently

A strong discretionary desk likely would have:

1. **Not replenished 300 CE minutes before stop/expiry context** after already harvesting CE closes.
2. **Reduced PE concentration earlier** once cap/margin warnings became persistent.
3. **Used execution urgency adaptively** for close/hedge actions showing >50s intent→confirm.
4. **Separated “must reduce risk now” from normal adjustment logic** when FORCE_REDUCE emerged.
5. **Maintained cleaner control log discipline** (explicit stop reason + override rationale).

---

## 7. Top 5 Immediate Fixes

1. Implement **fill-confirmed → audit-row required** invariant (block/alert on violation).
2. Add **expiry-stop guard**: disable replenish when within configured cutoff.
3. Add **FORCE_REDUCE fallback executor** (close/trim path even at cap).
4. Introduce **latency-aware execution policy** for 0DTE (urgency tiers + slicing).
5. Enforce **non-empty stop reason** and persist actor/source.

---

## 8. Top 5 Research Ideas

1. Dynamic policy for trigger/cap arbitration under gamma and margin constraints.
2. RL/DP model for hold-vs-close-vs-replenish near expiry.
3. Execution model predicting fill speed/slippage per order size and regime.
4. Real-time anomaly detector for stale/step-change premium feeds during strike changes.
5. Post-trade attribution engine splitting market vs logic vs execution P&L.

---

## 9. Session Scorecard

| Dimension | Score (/10) | Rationale |
|---|---:|---|
| Execution Quality | 5.5 | No rejects/partials, but slow confirms and one missing audit row |
| Risk Control | 4.0 | Persistent cap/margin stress; emergency gamma late in run |
| Speed | 4.0 | 0DTE execution latencies too high for reactive hedging |
| Decision Quality | 4.8 | Good close-at-5 harvest; questionable late replenishment |
| Capital Efficiency | 4.2 | Reached 600 combined lots with repeated margin warnings |
| Profit Capture | 6.4 | Realized capture was strong, but end-state still carried large exposure |
| Stability | 7.2 | Session remained operational and completed stop flow |
| Robustness | 4.0 | Audit inconsistency + weak metadata + blocked-trigger dead-zone |

**Overall grade: `C` (5.0 / 10)**

---

## 10. Final Verdict

This session made money, but the process quality is below prop-desk forensic standards.

- **What worked:** close-at-5 realization delivered the bulk of realized P&L.
- **What failed structurally:** audit completeness, cap/force-reduce conflict, and late-session replenishment logic.
- **Production risk takeaway:** without control-path fixes, the system can remain profitable in benign slices but fragile under stress transitions.

If this were a live desk review, I would mark this session as: **"Profitable outcome, but process risk unresolved — remediate before scaling."**
