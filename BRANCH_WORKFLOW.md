# 🌳 Git Branch Workflow - WebUI Upgrade

**Document Version:** 1.0  
**Date:** November 16, 2025  
**Project:** Working-gridBOT WebUI Upgrade  
**Strategy:** Zero-risk branch-based development

---

## 🎯 PHILOSOPHY

**GOLDEN RULE:** Production trading on `production-v3.0` (branch `3.0`) must NEVER be disrupted during upgrade development.

**How:** All upgrade work happens on isolated Git branches, tested on separate port (5557 for development), merged to production ONLY when 100% confident.

**⚠️ CRITICAL REMINDER:**
- Production: Port 5555, Branch `3.0`, LaunchAgent managed
- Development: Port 5557, Branch `feature/phase2-config-freedom`
- **NEVER modify files on production branch during development**
- **ALWAYS test on development port first**
- **ONLY merge to production when features are 100% working**

---

## 🌲 BRANCH STRUCTURE

```
3.0 (PROTECTED - Live Trading)
    │
    │   ← Production bot runs here (port 5555)
    │   ← NEVER commit directly during upgrade
    │   ← Guardian, live trading, real money
    │   ← LaunchAgent: com.gridbot.webui
    │
    └─── feature/phase2-config-freedom (Current development branch)
             │
             │   ← All phases merge here first
             │   ← Test on port 5557
             │   ← Safe to experiment
             │
             ├─── feature/phase1-core-independence
             │        ↓
             │        PM2 Dashboard, Log Viewer, File Manager
             │        Backup/Restore, Master Dashboard
             │
             ├─── feature/phase2-config-freedom
             │        ↓
             │        Monaco Code Editor, Strategy Manager
             │        Instance Manager, YAML Editors
             │
             ├─── feature/phase3-automation
             │        ↓
             │        Market Monitor, Mode Switcher
             │        System Health, Alerts
             │
             ├─── feature/phase4-pro-tools
             │        ↓
             │        Grid Calculator, Capital Allocator
             │        Dependency Manager, Git Integration
             │
             └─── feature/phase5-polish
                      ↓
                      Authentication, Security, Mobile
                      Performance, Testing
```

---

## 🚀 PHASE 0: INITIAL SETUP

### **Step 1: Tag Current Stable Version**

```bash
# From production-v3.0 branch
cd /Users/ssr/Projects/WorkingBot

# Verify you're on production
git branch
# Should show: * production-v3.0

# Tag stable version
git tag v3.0-stable
git push origin v3.0-stable

# Verify tag
git tag -l
```

**Purpose:** Safety checkpoint - can always return to this exact state.

---

### **Step 2: Create Main Upgrade Branch**

```bash
# Create main upgrade branch from production
git checkout -b feature/webui-upgrade

# Verify
git branch
# Should show:
#   production-v3.0
# * feature/webui-upgrade

# Push to remote
git push -u origin feature/webui-upgrade
```

**Purpose:** Base branch for all upgrade work.

---

### **Step 3: Create Phase Branches**

```bash
# Create Phase 1 branch
git checkout -b feature/phase1-core-independence

# Return to main upgrade branch
git checkout feature/webui-upgrade

# Create Phase 2 branch
git checkout -b feature/phase2-config-freedom
git checkout feature/webui-upgrade

# Create Phase 3 branch
git checkout -b feature/phase3-automation
git checkout feature/webui-upgrade

# Create Phase 4 branch
git checkout -b feature/phase4-pro-tools
git checkout feature/webui-upgrade

# Create Phase 5 branch
git checkout -b feature/phase5-polish

# Return to main upgrade branch
git checkout feature/webui-upgrade

# Verify all branches exist
git branch
# Should show:
#   production-v3.0
# * feature/webui-upgrade
#   feature/phase1-core-independence
#   feature/phase2-config-freedom
#   feature/phase3-automation
#   feature/phase4-pro-tools
#   feature/phase5-polish

# Push all branches to remote
git push -u origin feature/phase1-core-independence
git push -u origin feature/phase2-config-freedom
git push -u origin feature/phase3-automation
git push -u origin feature/phase4-pro-tools
git push -u origin feature/phase5-polish
```

**Purpose:** Isolated development for each phase.

---

### **Step 4: Configure Dual-Port Setup**

#### **Backend Configuration**

Create `webui/backend/config/port_config.py`:

```python
import os

# Port configuration based on branch
BRANCH_CONFIG = {
    'production-v3.0': {
        'port': 5555,
        'debug': False,
        'environment': 'production'
    },
    'feature/webui-upgrade': {
        'port': 5556,
        'debug': True,
        'environment': 'development'
    }
}

def get_current_branch():
    """Get current Git branch"""
    import subprocess
    try:
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        return branch
    except:
        return 'production-v3.0'  # Default to production

def get_port():
    """Get port based on current branch"""
    branch = get_current_branch()
    
    # Check if upgrade branch or sub-branch
    if 'feature/webui-upgrade' in branch or 'feature/phase' in branch:
        return BRANCH_CONFIG['feature/webui-upgrade']['port']
    else:
        return BRANCH_CONFIG['production-v3.0']['port']

def is_debug_mode():
    """Check if debug mode should be enabled"""
    branch = get_current_branch()
    if 'feature/' in branch:
        return True
    return False
```

Update `webui/backend/app.py`:

```python
from config.port_config import get_port, is_debug_mode

# ... existing code ...

if __name__ == '__main__':
    port = get_port()
    debug = is_debug_mode()
    
    print(f"🚀 Starting WebUI on port {port}")
    print(f"🌿 Branch: {get_current_branch()}")
    print(f"🐛 Debug mode: {debug}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
```

#### **Frontend Configuration**

Update `webui/frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite --port 3000",
    "dev:upgrade": "vite --port 3001",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

Update `webui/frontend/src/config/api.js`:

```javascript
// Auto-detect backend port based on frontend port
const getFrontendPort = () => window.location.port;
const getBackendPort = () => {
  const frontendPort = getFrontendPort();
  if (frontendPort === '3001') {
    return '5556'; // Upgrade branch
  }
  return '5555'; // Production
};

export const API_BASE_URL = `http://localhost:${getBackendPort()}/api`;
```

---

### **Step 5: Create Separate Config Files**

```bash
# Create upgrade-specific config
cp config/config.yaml config/config.upgrade.yaml

# Create upgrade PM2 ecosystem
cp ecosystem.gridbot.config.js ecosystem.upgrade.config.js
```

Update `ecosystem.upgrade.config.js`:

```javascript
module.exports = {
  apps: [
    {
      name: 'gridbot-upgrade-test',
      script: 'bot_launcher.py',
      interpreter: 'python3',
      env: {
        BRANCH: 'upgrade',
        CONFIG_FILE: 'config/config.upgrade.yaml',
        TRADING_MODE: 'demo',  // ALWAYS demo for testing
        WEBUI_PORT: '5556'
      },
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M'
    },
    {
      name: 'webui-upgrade',
      script: 'webui/backend/app.py',
      interpreter: 'python3',
      env: {
        BRANCH: 'upgrade',
        PORT: '5556'
      },
      instances: 1,
      autorestart: true
    }
  ]
};
```

---

### **Step 6: Test Parallel Operation**

```bash
# Terminal 1: Production (should already be running)
git checkout production-v3.0
pm2 status
# Should show gridbot-live, guardian-live running

# Terminal 2: Upgrade testing
git checkout feature/webui-upgrade
pm2 start ecosystem.upgrade.config.js

# Verify both running
pm2 status
# Should show:
# gridbot-live (production)
# guardian-live (production)
# gridbot-upgrade-test (upgrade)
# webui-upgrade (upgrade)

# 4. Test both WebUIs
# Production: http://localhost:5555 (backend serves built React)
# Development: http://localhost:5557 (React dev server with hot-reload)
```

**Verification Checklist:**
- [ ] Both WebUIs accessible
- [ ] Production bot still trading
- [ ] Upgrade bot on demo account
- [ ] No port conflicts
- [ ] Logs separate

---

## 💻 DAILY WORKFLOW

### **Starting Work on Phase 1**

```bash
# 1. Make sure production is safe
git checkout production-v3.0
git status
# Should be clean, no uncommitted changes

# 2. Switch to Phase 1 branch
git checkout feature/phase1-core-independence

# 3. Verify you're on correct branch
git branch
# Should show: * feature/phase1-core-independence

# 4. Start development server (upgrade port)
cd webui/frontend
npm run dev:upgrade
# Runs on port 3001 → connects to backend on 5556

# 5. Code code code...
# Make changes to webui/frontend/src/components/PM2Dashboard.js
# etc.

# 6. Commit your work
git add .
git commit -m "feat: Add PM2 Dashboard with real-time process monitoring"

# 7. Push to remote
git push origin feature/phase1-core-independence
```

---

### **After Completing Phase 1**

```bash
# 1. Make sure all work is committed
git status
# Should show: nothing to commit, working tree clean

# 2. Switch to main upgrade branch
git checkout feature/webui-upgrade

# 3. Merge Phase 1 into main upgrade branch
git merge feature/phase1-core-independence

# 4. Resolve any conflicts (if any)
# Git will show conflicts, resolve them, then:
git add .
git commit -m "merge: Phase 1 (Core Independence) complete"

# 5. Push merged changes
git push origin feature/webui-upgrade

# 6. Test merged version on port 5556
pm2 restart webui-upgrade
# Visit http://localhost:5556
# Test all Phase 1 features thoroughly

# 7. Keep testing for 2 days
# If bugs found:
git checkout feature/phase1-core-independence
# Fix bugs
git commit -m "fix: Bug in PM2 Dashboard refresh"
git checkout feature/webui-upgrade
git merge feature/phase1-core-independence
```

---

### **Moving to Phase 2**

```bash
# 1. Make sure Phase 1 is fully merged and tested
git checkout feature/webui-upgrade
git log --oneline -n 5
# Should see Phase 1 merge commit

# 2. Switch to Phase 2 branch
git checkout feature/phase2-config-freedom

# 3. Merge current upgrade branch into Phase 2
# (This brings in Phase 1 changes)
git merge feature/webui-upgrade

# 4. Start Phase 2 development
# Code code code...
# Monaco Editor integration, etc.

# 5. Commit Phase 2 work
git add .
git commit -m "feat: Integrate Monaco Editor for in-browser code editing"

# 6. Push to remote
git push origin feature/phase2-config-freedom

# 7. After Phase 2 complete, merge to main upgrade branch
git checkout feature/webui-upgrade
git merge feature/phase2-config-freedom
git push origin feature/webui-upgrade

# 8. Test Phase 1 + Phase 2 integration
# Visit http://localhost:5556
# Test both phases work together
```

---

### **Checking Production Status Anytime**

```bash
# Quick check without switching branches
git log production-v3.0 --oneline -n 5

# Or switch to production to verify
git checkout production-v3.0
pm2 status
# Should show gridbot-live, guardian-live running happily

# Check logs
pm2 logs gridbot-live --lines 20

# Return to upgrade work
git checkout feature/webui-upgrade
```

---

## 🚨 EMERGENCY: ROLLBACK TO PRODUCTION

If something goes wrong during testing:

```bash
# 1. Stop upgrade processes
pm2 stop gridbot-upgrade-test
pm2 stop webui-upgrade

# 2. Switch to production
git checkout production-v3.0

# 3. Verify production still intact
pm2 status
# gridbot-live should still be running

# 4. Restart production WebUI if needed
pm2 restart all

# 5. Production trading continues unaffected!
```

---

## ✅ FINAL CUTOVER TO PRODUCTION

After ALL phases tested and approved:

```bash
# 1. Make absolutely sure upgrade branch is ready
git checkout feature/webui-upgrade
git log --oneline -n 20
# Review all commits

# 2. Run final tests
npm run test
# All tests should pass

# 3. Create backup tag
git checkout production-v3.0
git tag v3.0-pre-upgrade-backup
git push origin v3.0-pre-upgrade-backup

# 4. STOP ALL PRODUCTION BOTS (CRITICAL)
pm2 stop gridbot-live
pm2 stop guardian-live

# 5. Merge upgrade into production
git merge feature/webui-upgrade

# 6. Resolve any conflicts carefully
# If conflicts, verify each change

# 7. Commit merge
git commit -m "merge: Complete WebUI upgrade (v4.0)"

# 8. Tag new version
git tag v4.0-webui-complete
git push origin production-v3.0 --tags

# 9. Restart with new version
pm2 restart all

# 10. Monitor for 48 hours
pm2 logs --lines 100
# Watch for any errors

# 11. If issues found:
# Rollback: git reset --hard v3.0-pre-upgrade-backup
# Fix issues on upgrade branch, re-test, try again

# 12. If all good: CELEBRATE! 🎉
```

---

## 📊 BRANCH STATUS REFERENCE

### **View All Branches**
```bash
git branch -a
```

### **See Which Branch You're On**
```bash
git branch
# * indicates current branch
```

### **Compare Branches**
```bash
# See what's in upgrade that's not in production
git log production-v3.0..feature/webui-upgrade --oneline

# See file differences
git diff production-v3.0..feature/webui-upgrade
```

### **List Changed Files Between Branches**
```bash
git diff --name-only production-v3.0..feature/webui-upgrade
```

---

## 🎯 BEST PRACTICES

### **DO:**
✅ Always verify your current branch before committing  
✅ Test on port 5557 before merging  
✅ Keep production-v3.0 clean (no direct commits during upgrade)  
✅ Commit frequently with clear messages  
✅ Push to remote daily (backup)  
✅ Test each phase for 2-3 days before moving on  
✅ Keep upgrade bot on DEMO account only  

### **DON'T:**
❌ Never commit directly to production-v3.0 during upgrade  
❌ Never test with real money on upgrade branch  
❌ Never force push to production-v3.0  
❌ Never merge without testing first  
❌ Never skip conflict resolution  
❌ Never delete branches until fully merged and verified  

---

## 🔍 TROUBLESHOOTING

### **Problem: Wrong branch, made changes to production**
```bash
# Don't panic! Stash changes
git stash

# Switch to correct branch
git checkout feature/phase1-core-independence

# Apply stashed changes
git stash pop

# Commit to correct branch
git add .
git commit -m "feat: Feature I meant to add to upgrade branch"
```

### **Problem: Merge conflict**
```bash
# During merge, Git shows conflict
# Edit conflicting files, look for:
# <<<<<<< HEAD
# your changes
# =======
# their changes
# >>>>>>> feature/phase1-core-independence

# Choose which changes to keep, remove markers
# Then:
git add .
git commit -m "merge: Resolved conflicts from Phase 1 merge"
```

### **Problem: Need to switch branches but have uncommitted changes**
```bash
# Option 1: Stash changes
git stash
git checkout other-branch
# Later: git stash pop

# Option 2: Commit to temporary branch
git checkout -b temp-work
git add .
git commit -m "wip: temporary work"
git checkout feature/webui-upgrade
```

### **Problem: Accidentally deleted important file**
```bash
# Restore from last commit
git checkout HEAD -- path/to/file

# Or restore from production
git checkout production-v3.0 -- path/to/file
```

---

## 📅 PHASE TRACKING

### **Phase 1: Core Independence**
- **Branch:** `feature/phase1-core-independence`
- **Status:** Not started
- **Started:** TBD
- **Merged to upgrade:** TBD
- **Testing complete:** TBD

### **Phase 2: Configuration Freedom**
- **Branch:** `feature/phase2-config-freedom`
- **Status:** ✅ In Progress (95% Complete)
- **Started:** November 15, 2025
- **Merged to upgrade:** Not yet (testing on port 5557)
- **Testing complete:** In progress
- **Components:**
  - ✅ Monaco Editor Integration (Day 1-2)
  - ✅ Strategy Manager UI (Day 3)
  - ✅ Config Visual Editor (Day 5)
  - ✅ File Manager API (created but needs review)
  - ⚠️ Issue: Phase 1 features not rendering in navigation

### **Phase 3: Intelligent Automation**
- **Branch:** `feature/phase3-automation`
- **Status:** Not started
- **Started:** TBD
- **Merged to upgrade:** TBD
- **Testing complete:** TBD

### **Phase 4: Professional Tools**
- **Branch:** `feature/phase4-pro-tools`
- **Status:** Not started
- **Started:** TBD
- **Merged to upgrade:** TBD
- **Testing complete:** TBD

### **Phase 5: Polish & Security**
- **Branch:** `feature/phase5-polish`
- **Status:** Not started
- **Started:** TBD
- **Merged to upgrade:** TBD
- **Testing complete:** TBD

### **Final Cutover**
- **Merged to production:** TBD
- **Tagged as:** v4.0-webui-complete
- **Production status:** TBD

---

## 🎉 SUCCESS CRITERIA

Before merging any phase:
- [ ] All features working on port 5556
- [ ] No errors in browser console
- [ ] No Python exceptions in logs
- [ ] Production bot still running on port 5555
- [ ] All tests passing
- [ ] Code reviewed
- [ ] Documentation updated

Before final cutover to production:
- [ ] All 5 phases complete and merged to `feature/webui-upgrade`
- [ ] 7 days of final testing complete
- [ ] Security audit passed
- [ ] Performance benchmarks met
- [ ] Backup plan ready
- [ ] Rollback tested
- [ ] User acceptance complete
- [ ] Team approval received

---

**Remember:** The beauty of this workflow is that **production never stops trading**. We can take all the time we need to perfect the upgrade! 🚀

---

**Last Updated:** November 16, 2025  
**Next Review:** After Phase 1 completion
