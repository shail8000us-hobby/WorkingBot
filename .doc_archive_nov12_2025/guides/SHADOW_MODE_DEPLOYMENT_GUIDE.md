# Phase 2+3 Shadow Mode Deployment Guide

## Overview
Shadow mode runs both threaded (old) and async (new) systems in parallel, comparing states every 60 seconds to validate correctness before cutover.

## Prerequisites Checklist
- ✅ All 22 Phase 2+3 tests passing
- ✅ Migration script ready (`scripts/migrate_to_async.py`)
- ✅ Dashboard script ready (`scripts/shadow_mode_dashboard.sh`)
- ✅ Threaded bot currently running
- ✅ State backup created

## Deployment Steps

### Step 1: Pre-Flight Check
```bash
# Verify current system is healthy
./bot_command_center.sh status

# Create backup
mkdir -p state_backups/pre_shadow_$(date +%Y%m%d_%H%M%S)
cp runtime_state.json state_backups/pre_shadow_$(date +%Y%m%d_%H%M%S)/
cp -r audit/ state_backups/pre_shadow_$(date +%Y%m%d_%H%M%S)/

# Verify tests pass
python3 -m pytest tests/test_async_actors_saga.py tests/test_chaos_compensation.py -v
```

### Step 2: Start Shadow Mode (24 hours)
```bash
# Terminal 1: Start shadow mode
python3 scripts/migrate_to_async.py --mode shadow --duration 24

# Terminal 2: Monitor dashboard
chmod +x scripts/shadow_mode_dashboard.sh
./scripts/shadow_mode_dashboard.sh
```

### Step 3: Monitoring During Shadow Mode

**What to Watch:**
- **Match Rate**: Target ≥99.9% for cutover approval
- **Discrepancies**: Investigate any critical differences
- **Error Rates**: Both systems should have <1% error rate
- **System Health**: Both systems must stay running

**Dashboard Interpretation:**
- 🟢 GREEN (≥99.9%): Ready for cutover
- 🟡 YELLOW (95-99.8%): Investigate discrepancies
- 🔴 RED (<95%): NOT READY - debug issues

**Manual Checks (every 4 hours):**
```bash
# Compare position counts
jq '.stats.comparisons, .stats.matches, .match_rate' logs/shadow_mode_report.json

# Check for critical issues
jq '.recent_discrepancies[] | select(.details.type == "position_mismatch")' logs/shadow_mode_report.json

# View event logs
tail -100 logs/deployment_$(date +%Y%m%d).log | grep -i "error\|critical\|warning"
```

### Step 4: Analyze Results (After 24h)

**Success Criteria:**
- Match rate ≥99.9%
- No critical discrepancies
- Async error rate <1%
- Zero system crashes

**If Successful:**
```bash
# Shadow mode automatically generates report
cat logs/shadow_mode_report.json

# Review and proceed to validation mode
python3 scripts/migrate_to_async.py --mode validation --duration 168  # 7 days
```

**If Failed:**
```bash
# Review discrepancies
jq '.recent_discrepancies' logs/shadow_mode_report.json

# Fix issues in async code
# Re-run tests
# Restart shadow mode
```

### Step 5: Validation Mode (7 days)

After shadow mode passes:
```bash
# Validation mode: async reads + threaded writes
python3 scripts/migrate_to_async.py --mode validation --duration 168

# Monitor for 7 days
# Async system handles all reads
# Threaded system handles all writes
# Verify consistency
```

### Step 6: Cutover (Final Switch)

After validation passes:
```bash
# Final cutover to async as primary
python3 scripts/migrate_to_async.py --mode cutover

# Monitor for 1 hour
# If stable, complete migration
python3 scripts/migrate_to_async.py --mode complete
```

## Emergency Rollback

If issues detected:
```bash
# Stop shadow mode
Ctrl+C

# Async system stops automatically
# Threaded system continues running
# No data loss - event log preserved
```

## Rollback Procedure (During/After Cutover)

```bash
# Emergency stop async system
pkill -f async_gridbot

# Restart threaded system
./bot_command_center.sh start

# Restore from backup if needed
cp state_backups/pre_shadow_*/runtime_state.json runtime_state.json

# Investigate issues
tail -500 logs/deployment_*.log | grep -i "error\|critical"
```

## Expected Timeline

| Phase | Duration | Goal |
|-------|----------|------|
| Shadow Mode | 24h | Validate state consistency |
| Analysis | 2h | Review discrepancies |
| Validation Mode | 7d | Build confidence |
| Cutover | 1h | Switch primary system |
| Monitoring | 2 weeks | Confirm stability |
| Complete | - | Archive old code |

**Total: ~3 weeks from start to complete migration**

## Risk Mitigation

✅ **Zero Data Loss**: Both systems run in parallel  
✅ **Instant Rollback**: Stop async, threaded continues  
✅ **Event Log**: Full audit trail for reconstruction  
✅ **Gradual Cutover**: 4 phases with validation gates  
✅ **Automated Monitoring**: Dashboard tracks health  

## Success Metrics

**Shadow Mode Success:**
- 1440 state comparisons (24h × 60/min)
- ≥99.9% match rate (max 1-2 discrepancies)
- Zero critical errors
- Both systems stable

**Validation Mode Success:**
- 7 days error-free operation
- Async latency <100ms p99
- Zero state inconsistencies
- Performance ≥ threaded baseline

**Cutover Success:**
- 1 hour monitoring period stable
- Error rate <0.1%
- All sagas completing successfully
- No position/order discrepancies

## Troubleshooting

### Issue: High Discrepancy Rate
**Diagnosis**: State comparison shows >5% mismatch  
**Solution**:
1. Check which fields differ: `jq '.recent_discrepancies[].details.type' logs/shadow_mode_report.json`
2. Review async actor logic for those fields
3. Check event store for missing events
4. Fix bugs and restart shadow mode

### Issue: Async System Crashes
**Diagnosis**: Async system exits unexpectedly  
**Solution**:
1. Check error logs: `tail -100 logs/deployment_*.log`
2. Review stack trace
3. Fix crash bug
4. Add test case for crash scenario
5. Restart shadow mode

### Issue: Performance Degradation
**Diagnosis**: Async system slower than threaded  
**Solution**:
1. Profile actor message processing
2. Check for blocking operations
3. Optimize saga execution
4. Consider increasing concurrency

### Issue: Memory Leak
**Diagnosis**: Memory usage grows over time  
**Solution**:
1. Check actor mailbox sizes
2. Verify event store cleanup
3. Profile with memory_profiler
4. Fix leak and restart

## Contact & Support

**Documentation**: See PHASE_2_3_TEST_RESULTS.md  
**Tests**: `tests/test_async_actors_saga.py`, `tests/test_chaos_compensation.py`  
**Code**: `bot/strategy/actors/`, `bot/strategy/sagas/`  

---

**REMEMBER**: Shadow mode is SAFE. Old system continues running. No risk to production!
