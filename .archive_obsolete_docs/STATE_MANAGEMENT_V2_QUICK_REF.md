# State Management v2.0 - Quick Reference Card

## 🚀 Quick Start

### Deploy Now
```bash
./deploy_state_v2.sh
```

### Manual Deploy
```bash
./bot_stopper.py
python3 migrate_state_to_v2.py
python3 test_state_management.py
./bot_launcher.py
```

---

## 📊 What Changed

| Feature | Before | After |
|---------|--------|-------|
| **State Files** | 2 files | 1 file ✅ |
| **Data Loss Window** | 10 seconds | <1 second ✅ |
| **Stale Threshold** | 1 hour | 5 minutes ✅ |
| **Corruption Detection** | None | SHA-256 ✅ |
| **Persistence** | Heartbeat only | Immediate ✅ |

---

## 🔍 Quick Commands

### Monitor State Updates
```bash
watch -n 1 'stat -f "%Sm" runtime_state.json'
```

### View State
```bash
cat runtime_state.json | jq '.'
```

### Check Age
```bash
cat runtime_state.json | jq '.data.timestamp' | xargs -I {} python3 -c "import time; print(f'{time.time() - {}}s ago')"
```

### Verify Checksum
```bash
cat runtime_state.json | jq -r '.checksum'
```

---

## ✅ Good Logs (Normal)

```
💾 State persisted: 3 positions, pending_buy: ID DX-123, 0 retries [checksum: a1b2c3d4]
✅ Runtime state loaded: 3 positions, 0 retries (age: 12s)
✅ Checksum validated: a1b2c3d4
```

---

## ⚠️ Warning Logs (Check)

```
⚠️ Runtime state is stale (8.3 minutes old), not loading
⚠️ Loading legacy state file format (no metadata)
```

---

## 🚨 Error Logs (Critical)

```
❌ State file checksum mismatch - CORRUPTED!
❌ Failed to load runtime state: file not found
```

---

## 🔙 Rollback

```bash
./bot_stopper.py
cp state_backups/pre_v2_deployment_*/runtime_state.json .
git checkout bot/strategy/modules/position_manager.py
git checkout bot/reconciliation/data_sources.py
./bot_launcher.py
```

---

## 📁 Files Modified

- ✅ `bot/strategy/modules/position_manager.py` (persistence logic)
- ✅ `bot/reconciliation/data_sources.py` (state file path)
- ✅ `runtime_state.json` (migrated to v2.0)
- ❌ `bot/state/state.json` (deleted, backed up)

---

## 🧪 Test Status

**Test Suite**: `test_state_management.py`  
**Result**: ✅ 5/5 tests passed

1. ✅ Immediate Persistence
2. ✅ Checksum Validation
3. ✅ Metadata Presence
4. ✅ Debouncing (1s interval)
5. ✅ Stale Rejection (5min threshold)

---

## 📚 Documentation

- **Analysis**: `analysis/STATE_MANAGEMENT_ANALYSIS.md`
- **Implementation**: `STATE_MANAGEMENT_FIXES_IMPLEMENTATION.md`
- **Complete Guide**: `STATE_MANAGEMENT_V2_COMPLETE.md`
- **This Card**: `STATE_MANAGEMENT_V2_QUICK_REF.md`

---

## 💡 Key Benefits

1. **Crash-Resistant**: State persists within 1 second
2. **Corruption-Proof**: SHA-256 checksums detect tampering
3. **Single Source**: No more dual state file conflicts
4. **Self-Healing**: Rejects stale/corrupt data automatically
5. **Deterministic**: Predictable behavior, no more chaos

---

## 🎯 Success Criteria

**Week 1**: Zero reconciliation errors from state issues  
**Week 2**: Zero manual interventions for orphaned positions  
**Week 3**: Zero duplicate orders from stale state  

---

**Deployed**: November 8, 2025  
**Status**: ✅ Production Ready  
**Tests**: 5/5 Passing ✅
