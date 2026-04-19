# UI Card Changes — Kill Switch + Hard Stop — 2026-04-17

## MMMDashboard.js SessionCard (primary production card)

### Hard Stop Display
- **Location:** Between P&L breakdown and Activity counters row
- **Rendering:**
  - `Hard Stop: $X` in orange (#ff9800) when max_loss_amount > 0 and not breached
  - `Hard Stop: Disabled` in disabled text color when max_loss_amount = 0 or absent
  - `⛔ Hard Stop Hit` in red (#f44336) bold when `|net_pnl| >= max_loss_amount`
- **Source field:** `session.params.max_loss_amount`
- **Breach detection:** `netPnl < 0 && Math.abs(netPnl) >= maxLoss`

### Kill Switch Button
- **Location:** Right side of control buttons row, between Exit Strategy (ContentCut) and EXITING spinner
- **Shown for:** RUNNING, PAUSED, BOTH_SIDES_UP statuses
- **Icon:** PowerOffIcon (deep red #d50000)
- **aria-label:** `"Emergency Kill Switch"` (accessible, testable)
- **Disabled:** While `killSubmitting` is true (shows CircularProgress instead)
- **Click:** Opens MUI Dialog for confirmation (does NOT propagate to card)

### Confirmation Dialog
```
Title:   ⛔ Emergency Kill Switch
Body:    Square off all positions for session <id> using market orders?
         CE: N lots · PE: N lots
Note:    This cannot be undone. Other sessions are not affected.
Buttons: [Cancel]  [Confirm Exit All]
```

---

## MMMSessionCard.js (secondary/standalone card)

Same features as above. Kill switch button shown in `CardActions` after Stop button.
Hard stop text shown between Stats grid and CardActions.
Requires `onKillSwitch` prop — if not provided, button is hidden.

---

## MMMXSessionCard.js (MMMX algorithm card)

### Hard Stop Label (added above existing bar)
- **Location:** Row 4, directly above the LinearProgress bar
- Same rendering logic as MMM: $X / Disabled / ⛔ Hard Stop Hit
- **Source field:** `s.hard_stop_usd` (MMMX uses this field, not params.max_loss_amount)

### Kill Switch Button
- **Location:** Row 6 (quick controls), after Stop button
- **Shown for:** RUNNING, PAUSED statuses
- Same icon, color, aria-label, dialog as MMM
- Requires `onKillSwitch` prop — wired in MMMXDashboard.js
- Wired to: `mmmxService.killSwitch({ scope: 'session', session_id: id })`

---

## Visual Reference

Before (control buttons row):
```
[▶ Pause]  [⚡ Force HB]  [■ Stop]  [✂ Exit]
```

After:
```
[▶ Pause]  [⚡ Force HB]  [■ Stop]  [✂ Exit]  [⏻ Kill Switch]
```

Kill Switch button is dark red, visually distinct from the orange Exit button.
