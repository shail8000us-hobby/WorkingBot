# MMM Lessons Learned

## [2026-03-10] One-sided exposure after CE fully closed via close-at-5

**What went wrong:**
When all CE positions fell to ≤close_at_threshold (market moved making calls worthless), `_process_close_at_5` closed them all. The code at that point just logged "For now, just log. Full auto-re-entry needs user config." — the session kept running with CE=0 and PE still open. This is a strategy violation: the two sides are meant to offset each other, and running single-sided leaves unlimited loss exposure on the open side.

**Root cause (detection):**
Incomplete feature in `mmm_monitor.py` — the `_process_close_at_5` inner check (`check_side_fully_closed`) had no action, only a log. No pause or alert was triggered.

**Fix applied (detection/reactive):**
Added ONE-SIDE CLOSE GUARD in `mmm_monitor.py` `_heartbeat()`, right after `check_both_sides_closed`. When one side is fully closed but the other has open lots, the session is immediately PAUSED with a critical safety alert.

---

## [2026-03-10] CE positions closed at premium ~38-41 instead of triggering a strike shift (SHIFT-GUARD fix)

**What went wrong:**
In today's session (mmm10mar26-3): CE @ 71200 had premium 38-41 (below shift_threshold=50). During a 30-minute window where PE was slowly rising but not yet hitting its trigger, close-at-5 fired and closed ALL 17 CE lots at 38-41. This left PE open with zero CE hedge. When PE later triggered, there was no CE to shift/sell. PE was closed at 151.5 vs entry 67.5 — a significant loss.

**Root cause:**
`close_at_5` runs unconditionally every heartbeat using bid price, BEFORE trigger evaluation. When CE bid fell below `close_at_threshold` (user had set it higher than default $5 to take profits at ~$40 range), close-at-5 fired. BUT: CE mark price was still slightly above/near shift_threshold ($50). If PE had triggered even once more, `check_shift_needed(ce, mark=42)` → 42 < 50 → SHIFT would have fired, moving CE to a new OTM strike with better premium and keeping both sides hedged.

**The strategy violation:**
Close-at-5 takes profit on the cheap/winning side without checking whether the expensive/losing side still needs coverage. The shift mechanism (which would maintain coverage) only fires on PE trigger, not proactively.

**Fix applied (preventive):**
Added SHIFT-BEFORE-CLOSE GUARD in `_process_close_at_5()` in `mmm_monitor.py`. Before closing any ACTIVE position (original, adjustment, strike_shift type): check if mark premium < shift_threshold AND the other side still has open lots. If so, SKIP this close and log — the position is preserved for the trigger-based shift mechanism.

Does NOT apply to:
- `frozen` type positions (already shifted away, independent risk)
- Wind-down mode (`using_elevated=True`) — let wind-down do its own cleanup

**Prevention rule:**
Whenever close-at-5 would fire on a side below shift_threshold AND the other side is open, the shift mechanism should get priority. The SHIFT-BEFORE-CLOSE guard enforces this. This preserves CE positions as "alive but cheap" so that the next PE trigger produces a proper CE shift rather than leaving CE at zero.

