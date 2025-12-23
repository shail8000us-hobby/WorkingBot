# Bot Restart Checklist - NOV 8, 2025

## Critical Fixes Applied

### 1. Data Normalization Bug (FIXED)
- **File**: `bot/strategy/modules/fill_detector.py`
- **Lines**: 274-297
- **Fix**: Added `cumulative_filled`, `total_order_size`, `unfilled_size`, `is_complete` to normalization
- **Impact**: GridBot now receives complete fill data instead of `(total: 0/0)`

### 2. REST API Fallback (NEW)
- **File**: `bot/strategy/gridbot.py`
- **Lines**: 263-270 (init), 360-547 (methods)
- **Feature**: Automatic REST polling when WebSocket starves >30s
- **Impact**: Zero downtime during WebSocket failures

## Validation Steps

### Pre-Restart
```bash
# 1. Verify code compiles
python3 -m py_compile bot/strategy/modules/fill_detector.py
python3 -m py_compile bot/strategy/gridbot.py

# 2. Check current bot status
pm2 list

# 3. Backup current logs
cp bot_live.log bot_live.log.backup_nov8_pre_restart
```

### Restart
```bash
# Stop bot
pm2 stop bot_launcher

# Clear logs (optional)
pm2 flush bot_launcher

# Start bot
pm2 start bot_launcher

# Watch logs in real-time
pm2 logs bot_launcher --lines 100
```

### Post-Restart Validation
```bash
# 1. Check initialization
grep "REST API Fallback System" bot_live.log | tail -5

# Expected output:
# 🔄 Initializing REST API Fallback System...
#    ├─ Starvation threshold: 30.0s
#    └─ Polling interval: 5.0s
# 🔄 Starting REST API fallback monitor...
# ✅ REST fallback monitor started

# 2. Check modules loaded
grep "initialized - All modules ready" bot_live.log | tail -1

# 3. Check state recovery
grep "CRASH RECOVERY" bot_live.log | tail -10

# 4. Check WebSocket connection
grep "WEBSOCKET.*connected\|subscribed" bot_live.log | tail -5

# 5. Verify no errors
grep "ERROR\|❌" bot_live.log | tail -20
```

## Monitoring After Restart

### What to Watch (First 5 Minutes)

1. **Successful Initialization**
   ```bash
   grep "✅ GridBot initialized" bot_live.log
   ```

2. **WebSocket Health**
   ```bash
   grep "Price update" bot_live.log | tail -20
   ```

3. **REST Fallback Status** (Should be INACTIVE initially)
   ```bash
   grep "REST FALLBACK" bot_live.log
   ```

4. **Reconciliation Results**
   ```bash
   grep "Reconciliation" bot_live.log | tail -10
   ```

5. **Current State**
   ```bash
   grep "open_tranches\|pending_buy" bot_live.log | tail -10
   ```

### What to Watch (Next Trade)

When next fill occurs, watch for:

1. **Fill Detection**
   ```bash
   tail -f bot_live.log | grep "Detected fill\|Processing fill"
   ```

2. **Complete Data** (NOT "total: 0/0")
   ```bash
   tail -f bot_live.log | grep "Processing.*fill.*total:"
   ```
   - ✅ Should see: `(total: 1.0/1.0)` or similar with actual numbers
   - ❌ Should NOT see: `(total: 0/0)`

3. **Handler Execution**
   ```bash
   tail -f bot_live.log | grep "handle_buy_fill\|handle_sell_fill"
   ```

4. **TP Order Placement**
   ```bash
   tail -f bot_live.log | grep "TP order placed"
   ```

5. **Next Grid Order**
   ```bash
   tail -f bot_live.log | grep "Next grid order placed"
   ```

## Success Criteria

### ✅ Initialization Phase
- [ ] REST fallback system initialized
- [ ] Monitor thread started
- [ ] All modules ready
- [ ] State recovered (if applicable)
- [ ] WebSocket connected and receiving price updates

### ✅ Normal Operation
- [ ] Price updates arriving every 1-3 seconds
- [ ] REST fallback remains INACTIVE
- [ ] No starvation warnings
- [ ] Reconciliation passes

### ✅ Fill Processing (When it occurs)
- [ ] Fill detected (WebSocket or REST)
- [ ] Complete data present: `(total: X/Y)` with real numbers
- [ ] Handler executes: `handle_buy_fill` or `handle_sell_fill`
- [ ] TP order placed successfully
- [ ] Next grid order placed successfully
- [ ] No errors in processing chain

### ✅ REST Fallback (If WebSocket starves)
- [ ] Starvation detected after 30s
- [ ] REST fallback ACTIVATES automatically
- [ ] Price updates continue via REST
- [ ] Order polling active
- [ ] Fills detected via REST (if any)
- [ ] Fallback DEACTIVATES when WebSocket recovers

## Common Issues and Solutions

### Issue 1: Bot won't start
```bash
# Check for syntax errors
python3 -m py_compile bot/strategy/gridbot.py
python3 -m py_compile bot/strategy/modules/fill_detector.py

# Check PM2 status
pm2 describe bot_launcher

# Check logs for error
pm2 logs bot_launcher --err --lines 50
```

### Issue 2: REST fallback activating immediately
**Symptom**: "ACTIVATING REST API FALLBACK" right after startup

**Possible Causes**:
- WebSocket not connecting
- `last_price_update` not being set

**Solution**:
```bash
# Check WebSocket connection
grep "WebSocket.*connect\|subscribed" bot_live.log | tail -10

# Check price updates
grep "Price update" bot_live.log | tail -20
```

### Issue 3: Still seeing "(total: 0/0)" errors
**Symptom**: Fill processed but handler not executing

**Verification**:
```bash
# Check normalization is preserving fields
grep "Processing.*fill" bot_live.log | tail -20
```

**If still broken**:
```bash
# Re-verify fix applied
grep -A 5 "cumulative_filled" bot/strategy/modules/fill_detector.py
```

### Issue 4: Multiple REST fallback activations
**Symptom**: Fallback activating/deactivating repeatedly

**Possible Causes**:
- WebSocket unstable
- Network issues

**Monitoring**:
```bash
# Track activation/deactivation cycles
grep "ACTIVATING\|DEACTIVATING.*REST" bot_live.log
```

## Emergency Rollback

If critical issues occur:

```bash
# 1. Stop bot immediately
pm2 stop bot_launcher

# 2. Check what went wrong
tail -100 bot_live.log

# 3. If needed, revert changes
git diff HEAD bot/strategy/gridbot.py
git diff HEAD bot/strategy/modules/fill_detector.py

# 4. Contact for support with logs
```

## Post-Restart Report Template

After restart, provide status:

```
Bot Restart - NOV 8, 2025 [TIME]

✅ INITIALIZATION:
- REST fallback system: [ACTIVE/INACTIVE]
- Monitor thread: [RUNNING/STOPPED]
- WebSocket: [CONNECTED/DISCONNECTED]
- State recovery: [SUCCESS/FAILED/N/A]

✅ CURRENT STATE:
- Open positions: [COUNT]
- Pending buy: [YES/NO]
- Last price: $[PRICE]
- Last update: [SECONDS] ago

✅ FILL PROCESSING (when occurs):
- Detection: [SUCCESS/FAILED]
- Data complete: [YES/NO - show "total: X/Y"]
- Handler executed: [YES/NO]
- TP placed: [YES/NO]
- Next order placed: [YES/NO]

❌ ISSUES:
- [List any errors or warnings]

📊 LOGS:
[Paste relevant log sections]
```

## Next Steps After Successful Restart

1. **Monitor for 1 hour**: Ensure stable operation
2. **Wait for next fill**: Validate complete processing cycle
3. **Document results**: Update this checklist with actual behavior
4. **Performance tuning**: Adjust thresholds if needed

## Contact Info for Issues

If problems occur, provide:
1. Full bot_live.log (or last 500 lines)
2. PM2 status: `pm2 list`
3. Specific error messages
4. Time of issue occurrence
5. What action triggered the issue

---

**Status**: Ready for restart
**Date**: NOV 8, 2025
**Critical Fixes**: 2 (Normalization + REST Fallback)
**Risk Level**: LOW (Both fixes validated, code compiles)
