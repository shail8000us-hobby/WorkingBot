# Bot Restart Instructions - November 19, 2025

## Current Situation
- Bot has 5 positions with `None` IDs stuck in memory
- Emergency TP system placing 5 invalid orders every 5 minutes
- All fixes have been applied to code

## Restart Command
```bash
pm2 restart gridbot-live
```

## What Will Happen

### 1. State Validation (First 10 seconds)
Look for these log messages:
```
🚨 Found 5 positions with None IDs - REMOVING THEM
   Removing broken position: {...}
✅ State validation complete: 0 positions kept, 5 removed
```

### 2. Opportunistic Recovery Check
The bot will check if recovery is needed:
```
Checking for startup opportunistic recovery...
```

If recovery runs, look for:
```
✅ Recovery TP placed: [order_id] at $[price] (maker-only)
🔄 OPPORTUNISTIC RECOVERY MODE DEACTIVATED - Normal grid operations resumed
```

### 3. Normal Trading Resumes
```
[HB] Positions: 0/5 | Price: $[price] | ✅ ACTIVE
```

## What to Watch For

### ✅ GOOD Signs
- "Found X positions with None IDs - REMOVING THEM"
- "All positions have TP protection" (in reconciliation)
- No "EMERGENCY TP" messages for None positions
- Normal grid orders being placed

### 🚨 BAD Signs
- "REJECTED position with invalid ID: None"
- "EMERGENCY TP] Placing TP for position None"
- Repeated reconciliation warnings about unprotected positions

## Monitoring Commands

### Check logs in real-time
```bash
pm2 logs gridbot-live --lines 100
```

### Check for emergency TPs
```bash
pm2 logs gridbot-live --lines 200 --nostream | grep "EMERGENCY TP"
```

### Check reconciliation status
```bash
pm2 logs gridbot-live --lines 200 --nostream | grep "RECONCILIATION"
```

### Check position count
```bash
pm2 logs gridbot-live --lines 50 --nostream | grep "Positions:"
```

## If Problems Persist

If you still see emergency TPs for None positions after restart:

1. Check if state validation ran:
```bash
pm2 logs gridbot-live --lines 500 --nostream | grep "State validation"
```

2. Check current positions:
```bash
pm2 logs gridbot-live --lines 100 --nostream | grep "open_tranches"
```

3. If broken positions remain, the validation might not have run. Try:
```bash
pm2 restart gridbot-live
```

## Expected Timeline

- **0-10s**: State validation, broken positions removed
- **10-30s**: Opportunistic recovery check (if needed)
- **30s+**: Normal trading operations

## Success Criteria

After 5 minutes of running:
- ✅ No emergency TP messages
- ✅ Reconciliation shows "All positions have TP protection"
- ✅ Normal grid orders being placed
- ✅ No positions with None IDs

---

**Ready to restart!** Just run: `pm2 restart gridbot-live`
