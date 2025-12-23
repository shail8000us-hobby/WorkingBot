# WebUI Rollback & Recovery Guide

**Date:** November 12, 2025  
**Part of:** WebUI Robustness Plan Week 3  
**Status:** Safety-first parallel system operation

---

## 📋 Overview

This guide documents how to safely roll back the new WebUI system if issues arise during the 7-day validation period. The new system runs in parallel with the old system, allowing instant rollback without data loss.

---

## 🎯 Quick Rollback (Instant - No Restart Required)

### Option 1: Feature Flag Toggle (Recommended)

**Disable new system via feature flag:**

```bash
# From WebUI settings panel (if available)
# OR via backend config file:

cd /Users/ssr/Projects/WorkingBot/webui/backend
nano feature_flags.json

# Set new_webui_system to false:
{
  "new_webui_system": false,
  "guardian_dashboard": false,
  "new_state_management": false,
  "data_aggregator": false,
  "circuit_breakers": false
}

# Save and exit (Ctrl+X, Y, Enter)
# Changes take effect within 60 seconds (feature flag cache TTL)
```

**Or via API (requires auth):**

```bash
curl -X POST http://localhost:5001/api/config/feature-flags \
  -H "Content-Type: application/json" \
  -d '{
    "flag": "new_webui_system",
    "enabled": false
  }'
```

**Result:** Frontend switches to old hooks and components within 60 seconds. No restart needed.

---

## 🔄 Full Rollback (Complete - Requires Restart)

### Option 2: Git Revert

**Revert all Week 1-3 commits:**

```bash
cd /Users/ssr/Projects/WorkingBot

# Check current branch
git branch
# Should show: * production-v2.0

# View recent commits
git log --oneline -10

# Revert Week 3 commits (if any)
git revert <week3_commit_hash> --no-edit

# Revert Week 2 commits
git revert d96fa42d4 --no-edit  # Week 2 summary
git revert a842ece81 --no-edit  # Week 2 App.js
git revert db347e21b --no-edit  # Week 2 core

# Revert Week 1 commits
git revert dc86e49b8 --no-edit  # Week 1 summary
git revert 06f8d01e5 --no-edit  # Week 1 implementation

# Verify revert
git status
git diff HEAD~5

# Commit revert
git commit -m "Rollback: Revert WebUI robustness changes (Week 1-3)"
```

**Restart backend:**

```bash
# Stop backend
pkill -f "python.*webui.*app.py"

# Start backend
cd webui/backend
python app.py
```

**Clear frontend build cache:**

```bash
cd webui/frontend
rm -rf node_modules/.cache
rm -rf build
npm run build
```

---

## 🛡️ Safety Checks Before Rollback

### 1. Document Current Issues

```bash
# Capture errors from backend logs
tail -n 100 /Users/ssr/Projects/WorkingBot/webui/backend/logs/*.log > rollback_issues.txt

# Capture browser console errors (manually)
# Open DevTools (F12) → Console → Save log

# Capture metrics (if available)
curl http://localhost:5001/api/metrics/recent?hours=1 > rollback_metrics.json
```

### 2. Backup Current State

```bash
cd /Users/ssr/Projects/WorkingBot

# Backup feature flags
cp webui/backend/feature_flags.json webui/backend/feature_flags.backup_$(date +%Y%m%d_%H%M%S).json

# Backup metrics database
cp webui/backend/metrics.db webui/backend/metrics.backup_$(date +%Y%m%d_%H%M%S).db

# Create Git branch for troubleshooting later
git checkout -b troubleshoot-week3-$(date +%Y%m%d)
git push origin troubleshoot-week3-$(date +%Y%m%d)
git checkout production-v2.0
```

### 3. Verify Old System Still Works

```bash
# Test old WebUI endpoints
curl http://localhost:5001/api/health
curl http://localhost:5001/api/bot/status
curl http://localhost:5001/api/positions

# Check old frontend hooks (manual browser check)
# Old hooks: useTradingData, useConfigManager
# Should still be present in App.js
```

---

## 📊 Monitoring After Rollback

### Check System Health

```bash
# Backend health
curl http://localhost:5001/api/health

# Expected response (old system):
{
  "status": "healthy",
  "services": {...},
  "resources": {...}
  # No "circuit_breakers" field (old system)
}
```

### Monitor Bot Performance

```bash
# Bot should continue running normally
tail -f /Users/ssr/Projects/WorkingBot/bot_live.log | grep -E "ERROR|CRITICAL|Exception"

# Expected: No new errors after rollback
```

### Check Frontend

- Open browser: http://localhost:3000
- Verify old components load correctly
- Check browser console for errors (should be clean)
- Test bot control buttons (start/stop/restart)

---

## 🔍 Troubleshooting Rollback Issues

### Issue 1: Feature Flag Toggle Not Working

**Symptoms:** New components still appear after disabling feature flag

**Fix:**

```bash
# Hard refresh browser
# Chrome/Firefox: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)

# OR clear browser storage
# DevTools → Application → Storage → Clear site data

# OR restart backend (clears server cache)
pkill -f "python.*webui.*app.py"
cd webui/backend && python app.py
```

### Issue 2: Git Revert Conflicts

**Symptoms:** `git revert` fails with merge conflicts

**Fix:**

```bash
# Abort revert
git revert --abort

# Manual rollback: restore files from before Week 1
git checkout 06f8d01e5~1 -- webui/

# Commit manual rollback
git add webui/
git commit -m "Manual rollback: Restore pre-Week1 WebUI"
```

### Issue 3: Old Hooks Not Found

**Symptoms:** Frontend crashes after rollback with "useTradingData is not defined"

**Fix:**

```bash
# Old hooks were never removed (Week 2 kept them for compatibility)
# Check if they exist:
grep -n "useTradingData" webui/frontend/src/App.js

# If missing, restore from Git:
git checkout 06f8d01e5~1 -- webui/frontend/src/hooks/

# Rebuild frontend
cd webui/frontend
npm install
npm run build
```

---

## 🚨 Emergency Rollback (Production Down)

If WebUI is completely broken and users are blocked:

```bash
# 1. Stop all services
pkill -f "python.*webui.*app.py"
pkill -f "npm.*start"

# 2. Restore last known good commit
cd /Users/ssr/Projects/WorkingBot
git reset --hard 06f8d01e5~1  # Commit before Week 1

# 3. Restart services
cd webui/backend && python app.py &
cd webui/frontend && npm start &

# 4. Verify
curl http://localhost:5001/api/health
# Browser check: http://localhost:3000
```

**⚠️ Warning:** `git reset --hard` is destructive. All uncommitted changes will be lost. Only use in emergency.

---

## ✅ Validation After Rollback

### 1. Backend Tests

```bash
# Health check
curl http://localhost:5001/api/health | jq

# Position data
curl http://localhost:5001/api/positions | jq

# Config
curl http://localhost:5001/api/config | jq '.success'
```

### 2. Frontend Tests

- [ ] Dashboard loads without errors
- [ ] Position data displays correctly
- [ ] Order history shows
- [ ] Bot control buttons work (start/stop/restart)
- [ ] Config editor functional
- [ ] No console errors in DevTools

### 3. Bot Tests

```bash
# Bot still running
ps aux | grep "python.*bot_main.py"

# No new errors in logs
tail -n 50 bot_live.log | grep ERROR

# Trading still functional (check for new orders)
grep "Order placed" bot_live.log | tail -n 5
```

---

## 📈 Post-Rollback Analysis

### Collect Data for Root Cause

```bash
# 1. System metrics at time of failure
cp webui/backend/metrics.db analysis/metrics_failure_$(date +%Y%m%d).db

# 2. Logs around failure time
grep -A 10 -B 10 "ERROR" webui/backend/logs/app.log > analysis/backend_errors.txt
grep -A 10 -B 10 "Exception" bot_live.log > analysis/bot_errors.txt

# 3. Browser console logs (manually save)

# 4. Git diff for review
git diff 06f8d01e5~1 HEAD > analysis/changes_week1_to_3.diff
```

### Share for Review

```
analysis/
├── metrics_failure_20251112.db
├── backend_errors.txt
├── bot_errors.txt
├── browser_console.log
├── changes_week1_to_3.diff
└── rollback_summary.md
```

---

## 🎯 Re-Deployment Plan (After Fixes)

Once issues are resolved:

1. **Test in development:**
   - Create feature branch: `git checkout -b fix-week3-issues`
   - Apply fixes
   - Test thoroughly (8+ hours monitoring)
   - Document what was fixed

2. **Gradual rollout:**
   - Enable feature flag for single user first
   - Monitor for 2 hours
   - If stable, enable for all users
   - Monitor for 24 hours

3. **Final validation:**
   - 7-day monitoring period
   - Compare metrics: old vs new
   - Collect user feedback
   - Decision: keep or revert again

---

## 📞 Escalation

If rollback fails or issues persist:

1. **Preserve evidence:**
   ```bash
   tar -czf webui_failure_$(date +%Y%m%d_%H%M%S).tar.gz \
     webui/ bot_live.log analysis/
   ```

2. **Document timeline:**
   - When did issues start?
   - What actions triggered the problem?
   - What error messages appeared?
   - What rollback steps were attempted?

3. **Safe mode:**
   - Keep bot running (it's independent of WebUI)
   - Access bot via logs: `tail -f bot_live.log`
   - Use emergency stop if needed: `pkill -f bot_main.py`

---

## 🔒 Rollback Guarantees

✅ **What rollback preserves:**
- Bot state (positions, orders, memory)
- Bot configuration
- Historical logs
- Trading continuity (bot keeps running)

✅ **What rollback loses:**
- Metrics database data (Week 1 feature)
- Feature flag settings
- Guardian Dashboard views (Week 3 feature)
- Command confirmations (Week 3 feature)

⚠️ **What rollback does NOT affect:**
- Bot brain logic (unchanged)
- Bot strategy (unchanged)
- Exchange API integration (unchanged)
- Telegram notifications (unchanged)

---

## 📚 Related Documents

- [WEBUI_ROBUSTNESS_PLAN_PRAGMATIC_NOV12_2025.md](WEBUI_ROBUSTNESS_PLAN_PRAGMATIC_NOV12_2025.md) - Original plan
- [WEBUI_WEEK1_COMPLETE_NOV12_2025.md](WEBUI_WEEK1_COMPLETE_NOV12_2025.md) - Week 1 summary
- [WEBUI_WEEK2_COMPLETE_NOV12_2025.md](WEBUI_WEEK2_COMPLETE_NOV12_2025.md) - Week 2 summary
- [AI_CONTEXT.md](AI_CONTEXT.md) - Bot architecture reference

---

**Last Updated:** November 12, 2025  
**Status:** Ready for 7-day validation period  
**Rollback Readiness:** ✅ Confirmed
