# AUDIT_DATABASE_INTEGRITY

**Date:** 2026-04-17  
**Scope:** Full on-disk database + log integrity audit (workspace-wide, excluding dependency/cache folders)  
**Audit Mode:** Read-only (no code changes, no data mutation)

## 1. Executive Summary

I audited **44 database files** and **54 log/audit files** for:
- missing rows
- duplicate rows
- audit mismatch
- stale sessions
- wrong timestamps
- empty stop reasons
- lifecycle gaps
- reconciliation errors
- oversized tables/files
- retention issues

### Top-line result
- ✅ **Physical DB integrity:** `PRAGMA integrity_check` is `ok` for all 44 DB files.
- ✅ **Duplicate rows (exact row duplicates):** none detected in all moderate-size tables checked.
- ✅ **Future timestamp anomalies:** none detected in validated DB/log paths.
- ⚠️ **Truth consistency is NOT fully consistent** due to lifecycle contradictions, empty stop reasons, and cross-copy audit/database divergence.

---

## 2. Files Audited

### Databases (44)
- `backtesting/historical_data/chain_index.db`
- `backtesting/historical_data/index.db`
- `data/alerts.db`
- `data/bot_events_BTCUSD_SHORT.db`
- `data/mmm_sessions.db`
- `data/options_max_loss.db`
- `data/options_sl_tp.db`
- `data/options_take_profit.db`
- `data/volatility.db`
- `data/volatility_BTCUSD.db`
- `data/volatility_ETHUSD.db`
- `database/zero_dte_rebalances.db`
- `database/zero_dte_sessions.db`
- `database/zero_dte_trades.db`
- `user_data/market_data.db`
- `user_data/trading.db`
- `webui/backend/data/activity_log.db`
- `webui/backend/data/errors.db`
- `webui/backend/data/ic_sessions.db`
- `webui/backend/data/iv_history.db`
- `webui/backend/data/max_loss.db`
- `webui/backend/data/mmm_sessions.db`
- `webui/backend/data/mmmx_sessions.db`
- `webui/backend/data/oi_data.db`
- `webui/backend/data/options_groups.db`
- `webui/backend/data/options_max_loss.db`
- `webui/backend/data/options_sl_tp.db`
- `webui/backend/data/options_take_profit.db`
- `webui/backend/data/patience.db`
- `webui/backend/data/sl_tp.db`
- `webui/backend/data/tradingview_signals.db`
- `webui/backend/database/zero_dte_rebalances.db`
- `webui/backend/database/zero_dte_sessions.db`
- `webui/backend/database/zero_dte_trades.db`
- `webui/backend/metrics.db`
- `webui/backend/options_strategy/strategies.db`
- `webui/backend/user_data/trading.db`
- `webui/data/alerts.db`
- `webui/data/options_max_loss.db`
- `webui/data/options_sl_tp.db`
- `webui/data/options_take_profit.db`
- `webui/database/zero_dte_rebalances.db`
- `webui/database/zero_dte_sessions.db`
- `webui/database/zero_dte_trades.db`

### Logs / Audit Logs (54)
- `.audit_log.jsonl`
- `audit/config_changes.jsonl`
- `audit_from_bot/backup_old/orders.jsonl`
- `audit_from_bot/orders.jsonl`
- `audit_from_bot/orders_live.jsonl`
- `audit_from_bot/reconciliation_audit.jsonl`
- `bot/audit/orders.jsonl`
- `bot/audit/orders_live.jsonl`
- `bot/audit/reconciliation_audit.jsonl`
- `bot/logs/gridbot_detailed.log`
- `bot/logs/guardian.log`
- `bot/logs/guardian_error.log`
- `bot/logs/pm2-gridbot-btc-SHORT-error.log`
- `bot/logs/pm2-gridbot-btc-SHORT-error__2026-04-17_14-00-00.log`
- `bot/logs/pm2-gridbot-btc-SHORT-error__2026-04-17_15-00-00.log`
- `bot/logs/pm2-gridbot-btc-SHORT-error__2026-04-17_16-00-00.log`
- `bot/logs/pm2-gridbot-btc-SHORT-out.log`
- `bot/logs/pm2-gridbot-btc-SHORT-out__2026-04-16_14-00-00.log`
- `bot/logs/pm2-gridbot-btc-SHORT.log`
- `bot/logs/pm2-gridbot-btc-SHORT__2026-04-17_14-00-00.log`
- `bot/logs/pm2-gridbot-btc-SHORT__2026-04-17_15-00-00.log`
- `bot/logs/pm2-gridbot-btc-SHORT__2026-04-17_16-00-00.log`
- `liquidation_monitor.log`
- `logs/auto_cleanup.log`
- `logs/auto_cleanup_error.log`
- `logs/guardian_monitor.log`
- `logs/webui_production.log`
- `logs/webui_production_error.log`
- `webui/backend/backend.log`
- `webui/backend/bot/audit/orders_demo.jsonl`
- `webui/backend/bot/audit/orders_live.jsonl`
- `webui/backend/logs/backend.log`
- `webui/backend/logs/backend_5555.log`
- `webui/backend/logs/backend_fixed.log`
- `webui/backend/logs/backend_manual.log`
- `webui/backend/logs/backend_restart.log`
- `webui/backend/logs/bot_process.log`
- `webui/backend/logs/tradingview_webhook.log`
- `webui/backend/webui.log`
- `webui/backend/webui_backend.log`
- `webui/backend/webui_backend_final.log`
- `webui/backend/webui_backend_fixed.log`
- `webui/frontend/build.log`
- `webui/frontend/build_output.log`
- `webui/frontend/frontend.log`
- `webui/logs/archive/backend.log`
- `webui/logs/archive/bot_process.log`
- `webui/logs/archive/frontend.log`
- `webui/logs/archive/webui_backend.log`
- `webui/logs/archive/webui_backend_final.log`
- `webui/logs/archive/webui_backend_fixed.log`
- `webui/logs/archive/webui_startup.log`
- `webui/logs/archive/webui_test.log`
- `webui/logs/webui.log`

---

## 3. Findings

### F1 — Database physical integrity is healthy
- All 44 DB files returned `ok` from SQLite integrity check.
- No physical corruption detected.

### F2 — Duplicate rows
- Exact duplicate-row audit (moderate-size tables) found **0 duplicate excess rows**.
- ID-level checks found **0 duplicate IDs** in checked tables.
- Event store uniqueness spot-check:
  - `data/bot_events_BTCUSD_SHORT.db.events`: `11999` rows, `11999` distinct `event_id`.

### F3 — Missing rows / row continuity gaps (logical)
ID continuity gaps exist in several tables (likely delete/retention behavior, but still a data lineage signal):
- `data/options_max_loss.db.strike_max_loss` → `id_gap=184` (249 rows)
- `data/options_take_profit.db.strike_take_profit` → `id_gap=71` (53 rows)
- `user_data/market_data.db.ohlcv` → `id_gap=2138` (747 rows)
- `user_data/trading.db.ohlcv` → `id_gap=336` (2160 rows)
- `webui/backend/data/mmm_sessions.db.position_audit_log` → `id_gap=1155` (2480 rows)

### F4 — Audit mismatch / cross-copy truth divergence
Significant divergence across replicated stores:
- `orders_live.jsonl` replicas are consistent (all empty, same hash).
- `orders.jsonl` replicas are inconsistent:
  - `audit_from_bot/orders.jsonl` → 1918 valid records
  - `bot/audit/orders.jsonl` → 0 valid records (comment-only)
  - `audit_from_bot/backup_old/orders.jsonl` → 149 records
- `reconciliation_audit.jsonl` replicas are inconsistent:
  - `audit_from_bot/reconciliation_audit.jsonl` → 12443 valid rows
  - `bot/audit/reconciliation_audit.jsonl` → 1316 valid rows
  - different hashes and different latest timestamps.

Cross-copy DB divergence (same basename, different content footprints):
- `alerts.db`: `data/alerts.db` (0 tables/0 rows) vs `webui/data/alerts.db` (4 tables/101 rows)
- `mmm_sessions.db`: `data/mmm_sessions.db` (0 tables/0 rows) vs `webui/backend/data/mmm_sessions.db` (5 tables/10438 rows)
- `options_max_loss.db`: `273` vs `16` vs `0` total rows across copies
- `options_sl_tp.db`: `593` vs `25` vs `0`
- `options_take_profit.db`: `126` vs `0` vs `0`
- `trading.db`: `user_data/trading.db` (2160 rows) vs `webui/backend/user_data/trading.db` (10103 rows)

### F5 — Stale sessions
- `webui/backend/data/mmm_sessions.db`: RUNNING sessions are fresh (all updated within ~1 hour) ✅
- `webui/backend/data/mmmx_sessions.db`: **6 DRAFT sessions** are stale (updated ~197–259 hours ago) ⚠️

### F6 — Wrong timestamps
- No future timestamps were detected in validated DB/log checks.
- No epoch-scale anomalies indicating impossible dates were detected.
- However, timestamp quality is inconsistent in logs:
  - `logs/webui_production.log` has many lines without parseable machine timestamps.
  - Mixed log formats reduce deterministic chronology.

### F7 — Empty stop reasons
In `webui/backend/data/mmm_sessions.db.performance_sessions`:
- `82` total rows
- `69` rows have `stop_reason=''` (empty)
- those `69` are all currently linked to `STOPPED` sessions.

### F8 — Lifecycle gaps / contradictions
In `webui/backend/data/mmm_sessions.db`:
- **12 STOPPED sessions** have `started` events but **no terminal event** (`stopped/completed/max_loss/kill_switch_triggered`) in `session_event_log`.
- **3 RUNNING sessions** currently have terminal metadata in `performance_sessions` (`end_time` and watchdog stop reason), which is a cross-table lifecycle contradiction.
- `STOPPED` count vs `performance_sessions` count mismatch also indicates incomplete lifecycle materialization.

### F9 — Reconciliation errors
- `audit_from_bot/reconciliation_audit.jsonl`:
  - 12443 valid rows
  - 12440 rows with non-zero mismatches
  - max `mismatched_orders=1703`
  - latest record: 2025-11-03
- `bot/audit/reconciliation_audit.jsonl`:
  - 1316 valid rows
  - 334 rows with non-zero mismatches
  - max `mismatched_orders=699`
  - latest non-zero mismatch at 2025-11-14; newer 2026 entries are zero-mismatch.

### F10 — Oversized tables / files
Oversized tables:
- `webui/backend/data/oi_data.db.oi_snapshots` → **2,261,018 rows**
- `webui/backend/metrics.db.metrics` → **2,086,367+ rows**
- `data/volatility_BTCUSD.db.rv_calculations` → **425,973+ rows**

Oversized files:
- `logs/webui_production_error.log` → **536,919,177 bytes** (~512 MiB)
- `webui/backend/data/oi_data.db` → **468,668,416 bytes**
- `webui/backend/metrics.db` → **392,417,280 bytes**

### F11 — Retention issues
- 30+ log artifacts are older than 30 days; multiple archives are ~160–165 days old.
- High-ingest DB tables show multi-week growth with no visible pruning signal (e.g., metrics and volatility histories).
- 0-byte placeholder DBs exist (`data/alerts.db`, `webui/backend/data/max_loss.db`, `webui/backend/data/sl_tp.db`), increasing source-of-truth ambiguity.

### Truth Consistency Verification
| Check | Result |
|---|---|
| Physical DB integrity | ✅ PASS |
| Duplicate row integrity | ✅ PASS |
| Missing-row / continuity semantics | ⚠️ PARTIAL |
| Cross-copy audit consistency | ❌ FAIL |
| Session lifecycle consistency | ❌ FAIL |
| Timestamp sanity (future/invalid epoch) | ✅ PASS |
| Stop-reason completeness | ❌ FAIL |
| Reconciliation health trend | ⚠️ PARTIAL |

---

## 4. Severity (P0/P1/P2/P3)

### P0 (Critical)
- **None observed** (no physical DB corruption detected).

### P1 (High)
1. Empty `stop_reason` for 69 STOPPED performance sessions.
2. Lifecycle contradictions (RUNNING status with terminal `end_time`; STOPPED sessions without terminal events).
3. Cross-copy truth divergence across audit logs and several same-name DB files.
4. Single oversized error log at ~512 MiB (`logs/webui_production_error.log`) with high operational risk.

### P2 (Medium)
1. Significant ID continuity gaps in multiple tables (lineage/auditability concern).
2. Stale MMMX DRAFT sessions.
3. Historical reconciliation mismatch spikes (high mismatch counts in archived audit trails).
4. Retention drift (many old logs, growth-heavy DBs without clear pruning).

### P3 (Low)
1. JSONL format inconsistencies (comment headers or non-JSONL pretty JSON in `.audit_log.jsonl`) affecting strict line parsers.
2. Mixed timestamp formats in some logs reduce observability quality.

---

## 5. Why It Matters

- **Risk and accountability:** Empty stop reasons and missing lifecycle terminal events reduce forensic trust during incidents.
- **Operational correctness:** Divergent replicas of the same logical dataset create conflicting “truths” for monitoring and reporting.
- **Performance & reliability:** Oversized logs/tables increase I/O, backup time, restart latency, and risk of disk pressure.
- **Auditability:** ID gaps are not always bad, but without explicit retention/deletion metadata, they look like unexplained data loss.
- **Reconciliation confidence:** Historical mismatch spikes imply incomplete closure/cleanup logic at some point in the order lifecycle.

---

## 6. Suggested Fix

1. **Define canonical source-of-truth per dataset**
   - For each logical domain (`orders`, `reconciliation`, `options_*`, `trading`, `sessions`), declare exactly one writer and one canonical read target.
   - Decommission or clearly mark replicas as archival/read-only snapshots.

2. **Enforce lifecycle completeness contract**
   - On stop/close, write terminal event + stop reason atomically.
   - Add a repair job: for `STOPPED` with missing terminal event, backfill a synthetic terminal event with reason `backfilled_lifecycle_terminal`.

3. **Fix performance/session contradiction semantics**
   - If a session restarts after watchdog stop, create a new performance row version or append run segment history instead of reusing terminal state as current truth.

4. **Stop reason hardening**
   - Apply non-empty constraint at write boundary (`strip` + fallback reason).
   - Add dashboard alert when `stop_reason` is blank for terminal states.

5. **Retention and compaction policy**
   - Implement explicit retention windows (e.g., 30/90 days depending on table/log type).
   - Rotate/compress `logs/webui_production_error.log` aggressively.
   - Archive + vacuum large DBs (`oi_data.db`, `metrics.db`) on schedule.

6. **Reconciliation audit hygiene**
   - Keep one canonical `reconciliation_audit.jsonl`.
   - Build daily summary with mismatch trend; alert on non-zero mismatch after expected settle window.

7. **JSONL format normalization**
   - Remove comment headers from machine-consumed `.jsonl` files.
   - Ensure one valid JSON object per line.

---

## 7. Safe Implementation Notes for Claude

Use this order to minimize risk:

1. **Read-only dry-run first**
   - Recompute the same integrity metrics and persist snapshots before any fix.

2. **Back up before mutation**
   - Snapshot affected DB/log files (checksum + timestamped backup).

3. **Do not “repair” ID gaps blindly**
   - Gaps can be legitimate deletions; focus on lifecycle/event consistency first.

4. **Backfill lifecycle with explicit provenance**
   - Any synthetic event/reason must include a `repair_source` tag and timestamp.

5. **Apply canonical-source migration incrementally**
   - Migrate one dataset at a time (`orders`, then `reconciliation`, then `options_*`, etc.), validate parity each step.

6. **Add invariant checks as guardrails**
   - `STOPPED -> non-empty stop_reason`
   - `RUNNING -> no terminal end_time in current performance segment`
   - `session started -> terminal event eventually emitted`

7. **Post-change verification gates**
   - Re-run this full audit and compare deltas: mismatch counts, blank stop reasons, lifecycle gaps, file sizes.

---

## 8. Final Score /10

**5.8 / 10**

### Rationale
- Strong physical integrity and no duplicate-row corruption signals.
- But truth-consistency issues (lifecycle contradictions, empty stop reasons, replica divergence) materially reduce trust in operational analytics and post-incident forensics.

---

**Audit verdict:** Data stores are physically healthy, but **logical integrity and canonical truth consistency need immediate hardening** (P1 focus areas above).