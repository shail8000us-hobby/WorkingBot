# DELETE_LIST.md — Repo Cleanup 2026-04-17

## Status: COMPLETED (Phase 1)

All items below were removed in commit `a94aebee9` on branch SSR.

---

## Removed: Git-tracked worktree gitlinks

| Path | Mode | Reason |
|---|---|---|
| `.claude/worktrees/bold-meninsky` | gitlink 160000 | Old AI dev worktree (branch `claude/bold-meninsky`); all content was archive-only duplicates |
| `.claude/worktrees/naughty-hoover` | gitlink 160000 | Old AI dev worktree (branch `claude/naughty-hoover`); all content was archive-only duplicates |

---

## Removed: Tracked backup/legacy files (git rm)

| File | Reason |
|---|---|
| `data/mmm_analytics_history.lock` | Lock file should never be versioned |
| `webui/backend/data/mmm_sessions.json.migrated` | Legacy migration artifact |
| `webui/backend/routes/mmm/mmm_analytics_aggregator.py.bak_feb18` | Feb 2026 backup — original file kept |
| `webui/backend/routes/mmm/mmm_storage.py.json_backup` | Legacy backup artifact |
| `webui/backend/routes/mmm/mmm_straddle_roll.py.base_plan_backup` | Legacy backup artifact |
| `webui/frontend/src/components/MMMInstitutionalAnalytics.js.bak_feb18` | Feb 2026 backup — original file kept |
| `webui/backend/db/tradingview_signals_db.py.bak_feb11` | Feb 2026 backup — original file kept |
| `webui/backend/routes/tradingview_webhook.py.bak_feb11` | Feb 2026 backup — original file kept |
| `webui/frontend/.backups/20260118_164347/components/InstitutionalAIPanel.js.bak2` | Jan 2026 backup dir |
| `webui/frontend/.backups/20260118_164347/components/InstitutionalAIPanel.js.bak3` | Jan 2026 backup dir |
| `webui/frontend/src/components/TradingViewSignals.js.bak_feb11` | Feb 2026 backup |

---

## Removed: Untracked DB/bak files from wrong paths (rm)

| File | Reason |
|---|---|
| `webui/backend/mmm_sessions.db` | Empty DB in backend root (not data/ dir) |
| `webui/backend/routes/mmm/mmm_sessions.db` | DB file inside code path |
| `webui/backend/data/mmm_activity_log.json.bak` | Activity log backup; live file kept |

---

## NOT Removed: REVIEW-flagged items

The following were flagged REVIEW (not ARCHIVE) in the audit and were left untouched.
These require manual decision by the user:

- `AI_MMMX_CONTEXT.md` — may still be referenced
- `MMMX_IMPLEMENTATION_PLAN.md` — plan doc
- `MMM_AI_Context_PureStraddle_Roll.md` — referenced in memory system
- `MMM_AUDIT_FIXES_MAR24_2026.md` — incident reference
- `MMM_SESSION_FORENSIC_AUDIT_*.md` (several) — recent session audits
- `MMM_SESSION_FORENSIC_COMPARATIVE_REVIEW_*.md`
- `MMM_SLIM_CONTEXT.md` — context file
- `mmm_workdone_march.md` — MANDATORY work log per CLAUDE.md
- `data/mmm_sessions.db`, `data/mmm_sessions.db-shm`, `data/mmm_sessions.db-wal` — live runtime DB
- `webui/backend/data/mmm_sessions.db`, `webui/backend/data/mmmx_sessions.db` — live runtime DBs

## NOT Removed: REDESIGN-flagged items

These are flagged for architectural redesign (not cleanup). No changes made:
- `mmm_api.py`, `mmm_monitor.py`, `mmm_god_layer.py`, `mmm_strategy_dispatch.py`
- `mmmx_api.py`, `mmmx_engine.py`, `mmmx_monitor.py`
