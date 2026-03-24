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

## 4. Branch

Main working branch: `SSR`. Merge target: `BTEH`.
