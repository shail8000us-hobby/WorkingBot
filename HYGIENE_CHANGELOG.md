# HYGIENE_CHANGELOG.md — Repo Cleanup 2026-04-17

## Session: Phase 1 Structural Cleanup — branch SSR

### Pre-cleanup state
- Total MMM-scoped files: 717 (per AUDIT_REPOSITORY_STRUCTURE.md)
- action=archive: 416 files (mostly in worktrees)
- Tracked backup files: 11
- Stray DB files in code paths: 3

### Safety checkpoint
- Commit `8f2bc2837` — restore point with all pending changes committed
- Baseline tests: **1425 passed, 1 pre-existing failure**
- Pushed to origin/SSR before any cleanup

---

## Changes Applied

### Commit `a94aebee9` — Phase 1 Cleanup

#### Worktree gitlinks removed (2)
- `.claude/worktrees/bold-meninsky` — old AI dev branch `claude/bold-meninsky`
- `.claude/worktrees/naughty-hoover` — old AI dev branch `claude/naughty-hoover`
- Both were gitlinks (mode 160000) accidentally committed to index
- Removed with `git worktree remove --force` + `git rm --cached`

#### Tracked backup files removed (11)
All files were period-specific backups of files that still exist in their active locations:
- `data/mmm_analytics_history.lock`
- `webui/backend/data/mmm_sessions.json.migrated`
- `webui/backend/routes/mmm/mmm_analytics_aggregator.py.bak_feb18`
- `webui/backend/routes/mmm/mmm_storage.py.json_backup`
- `webui/backend/routes/mmm/mmm_straddle_roll.py.base_plan_backup`
- `webui/frontend/src/components/MMMInstitutionalAnalytics.js.bak_feb18`
- `webui/backend/db/tradingview_signals_db.py.bak_feb11`
- `webui/backend/routes/tradingview_webhook.py.bak_feb11`
- `webui/frontend/.backups/20260118_164347/components/InstitutionalAIPanel.js.bak2`
- `webui/frontend/.backups/20260118_164347/components/InstitutionalAIPanel.js.bak3`
- `webui/frontend/src/components/TradingViewSignals.js.bak_feb11`

#### Untracked files deleted (3)
- `webui/backend/mmm_sessions.db` — empty DB in wrong location
- `webui/backend/routes/mmm/mmm_sessions.db` — DB inside code path
- `webui/backend/data/mmm_activity_log.json.bak` — activity log backup

#### .gitignore additions
- `.claude/worktrees/` — prevents future worktree dirs from being committed
- `*.json_backup`, `*.base_plan_backup` — backup file extensions
- `*.bak_feb*`, `*.bak_jan*`, `*.bak_mar*` — dated backup patterns
- `**/.backups/` — backup directories
- `webui/backend/routes/**/*.db` — DB files inside code paths

---

### Post-cleanup test result
- **1425 passed, 1 pre-existing failure** (identical to baseline)
- Zero logic files modified
- Zero trading-path files modified

---

## What Was NOT Changed (by policy)

| Category | Reason |
|---|---|
| All MMM/MMMX Python logic files | No-touch zone per CLAUDE.md |
| REVIEW-flagged docs | Require user decision |
| REDESIGN-flagged files | Architectural work, not cleanup |
| Live runtime DB files | Active sessions may be running |
| `mmm_workdone_march.md` | Mandatory work log |
| `.ai/` context files | Already in .gitignore |
