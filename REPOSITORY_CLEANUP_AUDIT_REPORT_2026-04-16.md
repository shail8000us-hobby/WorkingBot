# Repository Cleanup Audit Report (Safe / Non-Destructive)

Date: 2026-04-16  
Repo: `/Users/ssr/Projects/WorkingBot`

---

## 1) Scope and Safety Guardrails

- This audit was run in **strict non-destructive mode**.
- **No files were deleted, moved, or modified.**
- Goal: identify clutter and risk-segment candidates into:
  - **A** Core (must keep)
  - **B** Active support (keep)
  - **C** Safe to archive
  - **D** Safe to delete (high-confidence, mostly local runtime artifacts)
  - **E** Needs manual review
- Safety principle used throughout: if uncertain in a live trading system, classify as **E (Review)**, not delete.

## 2) Audit Method

Evidence gathered from:
- repository tree and size inventory
- tracked vs ignored vs untracked classification (`git ls-files`, ignore checks)
- targeted reference scans for large/generated files
- duplicate-name and backup-pattern scans
- runtime marker/state-file discovery
- frontend/backend deployment path checks

Key constraints respected:
- no destructive commands
- no git history rewrites
- no config/logic changes

## 3) Repository Snapshot

- Total files: **169,101**
- Total directories: **11,866**
- Tracked files: **4,893**
- Current git status entries: **7**
- Total repo disk footprint: **~73,848 MB (~73.8 GB)**

Top-level size hotspots:
- `bot` → **44,397 MB**
- `logs` → **22,050 MB**
- `webui` → **2,571 MB**
- `data` → **2,337 MB**
- `.claude` → **210 MB**
- `.venv` → **180 MB**
- `.venv_backup_py39` → **148 MB**

## 4) High-Impact Disk Hotspots (Observed)

Largest local (not tracked) items include:
- `logs/webui_production_error.log` (~22.8 GB)
- `bot/logs/pm2-gridbot-btc-SHORT.log` (~20.7 GB)
- `bot/logs/pm2-gridbot-btc-SHORT-error.log` (~20.7 GB)
- `data/bot_events_BTCUSD_LONG.db` (~1.34 GB)
- `data/bot_events_BTCUSD_SHORT.db` (~1.03 GB)
- `webui/frontend/node_modules` (~1.82 GB)

Notable tracked generated artifacts:
- `webui/backend/logs/backend_fixed.log.2` (~10 MB)
- `webui/backend/logs/backend_fixed.log.3` (~10 MB)
- `bot/audit/reconciliation_audit.jsonl` (~0.87 MB)
- `webui/backend/data/mmm_activity_log.json` (tracked runtime log file)
- committed frontend build outputs under `webui/frontend/build` and `backtest_ui/frontend/build`

## 5) Classification A — CORE (Must Keep)

High confidence keep set:
- trading engine/runtime logic: `bot/strategy`, `bot/risk`, `bot/orders`, `bot/reconciliation`, `bot/safety`, `bot/utils`
- backend runtime/API: `webui/backend/app.py`, `webui/backend/routes/**`, core services/utilities
- frontend source of truth: `webui/frontend/src/**`, `webui/frontend/public/**`, `webui/frontend/package.json`
- operational configs required for runtime startup
- active state stores likely required at runtime:
  - `data/system_state.json`
  - `data/recovery/recovery_state.json`
  - `webui/backend/data/real_trade_sync_state.json`

## 6) Classification B — ACTIVE SUPPORT (Keep)

Keep for operational/testing support:
- primary test suite under `tests/**`
- deployment/startup scripts under `scripts/**`
- current docs/runbooks used for ops and handoff
- health/check tooling and diagnostics that are still referenced

## 7) Classification C — SAFE TO ARCHIVE

Archive-first (not immediate delete), medium/high confidence:

1. Historical code trees and legacy bundles
- `archive/**`
- `archive_hot/**`
- `deprecated/**`
- `webui/archive/**`

2. Copied workspace trees
- `.claude/worktrees/**` (currently ~210 MB local)
- Important note: repository has gitlink entries (`mode 160000`) for:
  - `.claude/worktrees/bold-meninsky`
  - `.claude/worktrees/naughty-hoover`
- `.gitmodules` mapping is missing; this is structurally suspicious and should be handled as a controlled git cleanup task.

3. Historical analysis output bundle
- `audit_from_bot/**` (~17 MB local)

4. Root helper duplicates (archive one side)
- `_analyze_s4_detail.py` ↔ `tests/_analyze_s4_detail.py`
- `_analyze_session.py` ↔ `tests/_analyze_session.py`
- `_analyze_session_v2.py` ↔ `tests/_analyze_session_v2.py`
- `_analyze_theta_vs_perp.py` ↔ `tests/_analyze_theta_vs_perp.py`
- `_inspect_session.py` ↔ `tests/_inspect_session.py`
- `_test_exchange_margin.py` ↔ `tests/_test_exchange_margin.py`
- `_test_migration.py` ↔ `tests/_test_migration.py`
- `_test_ssr_algo_imports.py` ↔ `tests/_test_ssr_algo_imports.py`
- `_test_tiered_trend.py` ↔ `tests/_test_tiered_trend.py`

## 8) Classification D — SAFE TO DELETE (High Confidence, Local Runtime Clutter)

No deletion was performed. These are **recommended candidates** with high confidence:

1. Runtime logs and rotated logs (largest reclaim)
- `bot/logs/**` (~44.4 GB)
- `logs/**` (~22.0 GB)
- old zipped log rotations in log folders

2. Local dependency/cache artifacts (regenerable)
- `webui/frontend/node_modules/**` (~1.82 GB)
- local package caches under node_modules
- local virtualenv backup: `.venv_backup_py39/**` (~148 MB)

3. Ephemeral root runtime markers (not tracked)
- `.guardian.pid`, `.webui_instance_5555.lock`, `.heartbeat`, `.heartbeat.backup`
- `.config_change_pending_*`, `.confirm_*`
- `.volatility_halt*.json`, `.volatility_status.json`, `.guardian_health`, `.guardian_status.json`

4. OS/editor noise (if present/untracked)
- stray `.DS_Store` and temporary editor artifacts in non-source locations

## 9) Classification E — NEEDS MANUAL REVIEW (Do Not Delete Blindly)

1. Tracked generated/test/build artifacts (git-history impact)
- `.hypothesis/**` (2,387 tracked files)
- committed frontend build outputs (`/build/` paths; ~113 tracked files)
- tracked logs:
  - `webui/backend/logs/backend_fixed.log.2`
  - `webui/backend/logs/backend_fixed.log.3`
- tracked runtime/generated data:
  - `bot/audit/reconciliation_audit.jsonl`
  - `webui/backend/data/mmm_activity_log.json`

2. Config linking oddity
- `webui/backend/grid_config.env` is tracked and is a symlink to `../../grid_config.env` (target file appears local/ignored). Requires explicit config-policy decision.

3. Backup-like tracked source files
- tracked backups and disabled tests (19 tracked backup-like files), e.g.:
  - `bot/strategy/async_gridbot.py.pre_refactor_backup`
  - `bot/strategy/async_gridbot.py.backup_nov17_2025`
  - `tests/test_webui_config_redaction.py.disabled`
  - `webui/archive/code_backups/**`

4. State/backups with runtime ambiguity
- `bot/state/live_state_backup_*.json`
- `bot/reports/state.json`
- monitoring snapshots under `data/monitoring_snapshot*.json`
- treat as retention-policy items, not immediate delete.

## 10) Special-Focus Findings

### a) `state.json` and backup state files
- Active + backup state files exist in live paths and legacy/archive paths.
- Recommendation: preserve latest active state; archive timestamped historical state backups with retention policy.

### b) Old bot versions / copied folders
- `archive/threaded_bot_20251114/**`, `archive/phase2/**`, and `.claude/worktrees/**` indicate historical/copy trees.
- Good archive candidates; avoid direct deletion until owner confirms no rollback need.

### c) Unused UI assets / build artifacts
- Backend serves `../frontend/build` directly (`Flask(... static_folder='../frontend/build')`).
- Deployment/start scripts check for build presence.
- Therefore committed build output is **not automatically delete-safe** until deployment policy is finalized.

### d) Stale tests
- Disabled test found: `tests/test_webui_config_redaction.py.disabled`.
- Root `_test_*.py` duplication vs `tests/` strongly suggests stale parallel test helpers.

### e) Generated reports/logs/debug scripts/shell helpers
- Massive local logs are top cleanup win.
- Duplicate shell helpers exist in root + `scripts/`:
  - `START_BOTS_TMUX.sh`
  - `auto_cleanup_archives.sh`

### f) Hidden duplicate strategy files
- `bot/strategy/async_gridbot.py` plus tracked backup variants (`*.pre_refactor_backup`, `*.backup_nov17_2025`).
- Keep canonical active file; archive backup variants once rollback point is formally accepted.

## 11) Recommended Cleanup Phases (Approval-Gated)

### Phase A (Lowest risk, immediate local reclaim)
- purge/rotate local logs in `bot/logs/**` and `logs/**`
- remove runtime markers/locks/heartbeat files
- optionally clear `node_modules` and reinstall when needed
- expected reclaim: **~68+ GB** (dominant win)

### Phase B (Archive-first)
- move historical trees (`archive*`, `deprecated`, `webui/archive`, `audit_from_bot`) to dated archive package
- snapshot and archive duplicated helper/test scripts
- expected reclaim: moderate (plus organization clarity)

### Phase C (Tracked clutter PR)
- prepare dedicated git cleanup PR for:
  - tracked `.hypothesis/**`
  - tracked `build/**` policy decision
  - tracked fixed logs + tracked backup-like files
- expected reclaim in repo working tree: smaller than Phase A, but major hygiene improvement

### Phase D (Policy hardening)
- codify retention policy for logs/state backups
- enforce ignore rules to prevent re-committing generated artifacts
- document deployment choice: committed build vs build-at-deploy

## 12) Approval Gate and Next Step

Status: **Audit complete, no destructive action taken.**

If you approve, next step is to produce a **dry-run execution plan** (exact file patterns and counts per phase) and then run cleanup in this order:
1. Phase A (local-only, high confidence)
2. Phase B (archive package)
3. Phase C (tracked cleanup PR)

I will wait for explicit approval before any delete/archive action.
