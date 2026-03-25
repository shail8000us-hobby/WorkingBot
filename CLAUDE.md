# CLAUDE.md — Mandatory Rules for This Repository

## 1. MMM Algo Work Log (MANDATORY)

**Every session that touches any MMM file must:**

1. **READ `mmm_workdone_march.md` at the start** — understand what was changed in prior sessions before touching anything.
2. **ADD an entry at the end** when the session is complete — format:
   ```
   ## YYYY-MM-DD — <short title>
   - What changed and why (per file/bug/feature)
   ```

This applies to ANY of the following files/directories:
- `webui/backend/routes/mmm/`
- `webui/frontend/src/components/mmm/`
- `webui/backend/services/` (when MMM-related)
- Any file whose name contains `mmm`

**Why**: The MMM algo has 50+ modules, hundreds of interdependencies, and a long history of bugs that were fixed and re-introduced. The work log is the institutional memory. Without reading it, you will duplicate effort, re-introduce fixed bugs, or break invariants established in prior sessions.

---

## 2. Real Money Rules

- Never restart the bot/backend/monitor without explicit user confirmation.
- Never place or cancel real orders without explicit user request.
- Always confirm before `git push` or any destructive operation.

---

## 3. Before Modifying MMM Logic

- Read `webui/backend/routes/mmm/mmm_engine.py` — core P&L formulas
- Read `webui/backend/routes/mmm/mmm_constants.py` — LOT_SIZE_BTC and other constants
- Check `webui/backend/routes/mmm/tests/` for existing test coverage before changing behavior

---

## 4. Stale Monitor Invariants (DO NOT BREAK)

On 2026-03-24 a live P0 incident occurred: a stale `MMMMonitor` instance (gen=7) kept placing real SELL orders (560 lots total, ~$77 average) while the H-4 generation guard blocked its saves — creating phantom positions invisible to max loss, lot limits, and P&L tracking.

**Root cause**: `_save_session` blocked saves but never stopped the monitor thread.

**Three-layer fix — all three must remain intact:**

1. **`start_session_monitor()` — `thread.join(15s)`**: After calling `existing.stop()`, waits up to 15s for the old thread to exit before starting the new one. Prevents stale instances from existing at all.

2. **`_run_loop` primary guard**: At the top of each loop cycle, after loading `fresh_session`, checks `stored_gen > self._my_generation`. If stale: sets `_running = False`, fires Telegram + `emit_safety()` (sync — NOT `run_until_complete`), breaks.

3. **Guardian G5 inside `_heartbeat()`**: After `pre_beat_snapshot()`, calls `self._guardian.check_generation_integrity(session, self._my_generation)`. If stale: calls `handle_stale_monitor()` (STOP not pause) and returns. This is the innermost fallback.

**Critical implementation notes:**
- `emit_safety()` is a regular `def` (not async) — call it directly, never wrap in `run_until_complete()`
- `handle_stale_monitor()` must use STOP (`_running = False`) not pause — a paused stale monitor resumes and trades again
- `_save_session()` returns `True` on success, `False` on blocked save — callers must check the return value
- Secondary guard in `_save_my_session()` checks the return value and sets `_stale_abort_gen` flag if save rejected

**Do not remove or weaken any of these layers.** See `mmm_workdone_march.md` Sessions 10–13 for full incident analysis.

---

## 5. Branch

Main working branch: `SSR`. Merge target: `BTEH`.
