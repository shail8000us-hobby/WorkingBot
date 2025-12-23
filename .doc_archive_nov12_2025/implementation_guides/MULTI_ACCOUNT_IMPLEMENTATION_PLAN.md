# 🏗️ Multi-Account System Implementation Plan

**Project:** WorkingBot Multi-Account Architecture  
**Version:** 4.0.0 (Proposed)  
**Date:** October 31, 2025  
**Status:** Planning Phase - Development Branch Strategy Approved  
**Development Branch:** `feature/multi-account-v4.0` (To be created)  
**Production Branch:** `production-v2.0` (Protected - Live Trading)  

> **Architecture Update (Oct 31, 2025):** This plan references `bot/strategy/gbot_ws.py` which 
> has been refactored into modular architecture (`gridbot.py` + 7 modules). The strategy code 
> remains **COMPLETELY UNCHANGED** from multi-account perspective - modules are drop-in compatible. 
> See `GRIDBOT_REFACTORING_QUICK_REF.md`.

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Branch Strategy & Workflow](#branch-strategy--workflow)
3. [Architecture Philosophy](#architecture-philosophy)
4. [Risk Assessment](#risk-assessment)
5. [Implementation Phases](#implementation-phases)
6. [Technical Specifications](#technical-specifications)
7. [Safety Controls](#safety-controls)
8. [Testing Strategy](#testing-strategy)
9. [Rollout Plan](#rollout-plan)
10. [FAQ](#faq)

---

## 📊 Executive Summary

### What Are We Building?

Transform WorkingBot from **single-account** to **multi-account** architecture, enabling:

- ✅ Run multiple trading accounts simultaneously
- ✅ Each account with different strategies (conservative, aggressive, testing)
- ✅ Centralized control via single WebUI dashboard
- ✅ Complete isolation between accounts (separate API keys, configs, state)
- ✅ Auto-detection of testnet vs live environments

### Why Multi-Account?

**Current Problem:**
- Can only run one bot at a time
- Testing new strategies requires stopping live trading
- No way to run conservative (live) + aggressive (test) simultaneously

**Solution:**
- Run live conservative strategy (real money, large grid step)
- Run aggressive test strategy (testnet API, small grid step)
- Both running in parallel without interference

### Business Value

| Benefit | Impact |
|---------|--------|
| **Parallel Testing** | Test strategies without stopping live trading |
| **Risk Diversification** | Spread capital across multiple accounts |
| **Strategy Optimization** | Compare different grid settings in real-time |
| **Scalability** | Easy to add new accounts as capital grows |
| **Safety** | Account isolation prevents cross-contamination |

---

## 🔀 Branch Strategy & Workflow

### Critical Decision: Parallel Development Strategy

**Approved Approach:** Separate development branch for multi-account system while maintaining stable production branch for live trading.

---

### Branch Architecture

```
Git Repository Structure:

production-v2.0 (PROTECTED - LIVE TRADING)
├── Current State: Stable, production-ready
├── Purpose: Live trading with real money
├── Changes Allowed: 
│   ✅ Critical bug fixes only
│   ✅ Minor configuration adjustments
│   ✅ Urgent safety improvements
│   ❌ NO experimental features
│   ❌ NO multi-account development
│
└── Protection: Tagged before creating feature branch

feature/multi-account-v4.0 (DEVELOPMENT)
├── Branched From: production-v2.0
├── Purpose: Multi-account system development
├── Changes Allowed:
│   ✅ All multi-account features
│   ✅ Experimental code
│   ✅ Breaking changes (isolated)
│   ✅ Extensive testing
│
├── Sync Strategy: Regular merges FROM production-v2.0
│   └── Keeps feature branch up-to-date with production fixes
│
└── Merge Back: Only when fully tested and production-ready
```

---

### Branch Workflow Rules

#### **Rule 1: Production Branch Protection**

```bash
# production-v2.0 - SACRED RULES:
# ✅ Can fix critical bugs anytime
# ✅ Can adjust live trading configs
# ✅ Must remain stable at all times
# ❌ NO multi-account code
# ❌ NO experimental features
# ❌ NO breaking changes

# If production needs urgent fix:
git checkout production-v2.0
# Fix bug
git commit -m "fix: Critical production bug"
git push origin production-v2.0
# Fix deployed immediately
```

#### **Rule 2: Feature Branch Development**

```bash
# feature/multi-account-v4.0 - DEVELOPMENT RULES:
# ✅ Full freedom to develop
# ✅ Can break things (isolated from production)
# ✅ Can experiment with architecture
# ✅ Must sync from production regularly

# Daily development workflow:
git checkout feature/multi-account-v4.0
git merge production-v2.0  # Sync production fixes
# Develop all day
git commit -m "feat: Add account manager"
git push origin feature/multi-account-v4.0
```

#### **Rule 3: Sync Strategy (One-Way)**

```bash
# IMPORTANT: Changes flow ONE WAY only during development

production-v2.0 ────fixes────> feature/multi-account-v4.0
                     │
                     └─── (merge/cherry-pick)

# Production fixes ALWAYS flow TO feature branch
# Feature changes NEVER flow to production (until ready)

# Weekly sync (recommended):
git checkout feature/multi-account-v4.0
git merge production-v2.0
# Resolve conflicts if any
git push origin feature/multi-account-v4.0
```

---

### Practical Scenarios

#### **Scenario 1: Urgent Production Fix During Development**

```bash
# You're coding multi-account feature at 3:00 PM
# Phone rings: Live trading bot has critical bug!

# Step 1: Save current work
git checkout feature/multi-account-v4.0
git stash  # Save uncommitted work

# Step 2: Switch to production and fix
git checkout production-v2.0
vim bot/strategy/gbot_ws.py  # Fix the bug
git add bot/strategy/gbot_ws.py
git commit -m "fix: Emergency order placement bug"
git push origin production-v2.0

# Step 3: Deploy fix (bot restarts with fix)
# ... production is fixed ...

# Step 4: Bring fix to feature branch
git checkout feature/multi-account-v4.0
git merge production-v2.0  # Get the fix
git stash pop  # Resume your work

# Step 5: Continue development
# ... total disruption: 15 minutes ...
```

#### **Scenario 2: Improve Production Config**

```bash
# You want to optimize grid step on production

# Step 1: Switch to production
git checkout production-v2.0

# Step 2: Make improvement
vim grid_config.env
# Change GRID_STEP from 2000 to 1800

# Step 3: Test and commit
python3 bot/run.py demo 60  # Test first
git add grid_config.env
git commit -m "config: Optimize grid step to 1800"
git push origin production-v2.0

# Step 4: Bring to feature branch
git checkout feature/multi-account-v4.0
git merge production-v2.0

# Both branches now have the improvement!
```

#### **Scenario 3: Week-Long Development Cycle**

```bash
# Monday Morning:
git checkout feature/multi-account-v4.0
git merge production-v2.0  # Sync weekend changes
# ... develop Phase 1 ...
git commit -m "feat: Add directory structure"

# Tuesday:
# ... develop Phase 2 ...
git commit -m "feat: Add URL detector"

# Wednesday (Production needs fix):
git checkout production-v2.0
# ... fix bug ...
git commit -m "fix: Telegram alert bug"
git checkout feature/multi-account-v4.0
git merge production-v2.0  # Get the fix
# ... continue development ...

# Friday:
git checkout feature/multi-account-v4.0
git merge production-v2.0  # Final sync
# ... test everything ...
git push origin feature/multi-account-v4.0

# Weekend:
# production-v2.0 runs live trading
# feature branch rests
```

---

### Timeline & Milestones

```
Week 0 (Current):
├── NOW: Complete planning documentation
├── Tag: production-v2.0 as v2.0-stable-before-multi-account
├── Create: feature/multi-account-v4.0 branch
└── Status: Ready to start development

Week 1-4: Development on feature/multi-account-v4.0
├── production-v2.0: Live trading continues (untouched)
├── feature/multi-account-v4.0: All multi-account development
├── Sync: Weekly merges from production to feature
└── Checkpoints: After each phase

Week 5: Testing & Validation
├── Run both branches in parallel (different servers/accounts)
├── Compare stability, performance, features
├── Make go/no-go decision
└── Option to extend testing if needed

Week 6+: Deployment Decision
├── Option A: Merge to production (feature becomes new production)
├── Option B: Keep parallel (production-v2.0 + feature as separate systems)
├── Option C: Abandon feature (revert to production-v2.0)
└── Full rollback capability preserved
```

---

### Safety Guarantees

| Guarantee | Implementation |
|-----------|----------------|
| **Production Never Breaks** | Feature development completely isolated in separate branch |
| **Easy Rollback** | Can switch back to production-v2.0 anytime with `git checkout production-v2.0` |
| **Production Fixes Not Lost** | Regular merges from production to feature ensure all fixes preserved |
| **Live Trading Uninterrupted** | Production branch never touched during feature development |
| **Testing Freedom** | Feature branch can be broken, rewritten, or abandoned without affecting production |
| **Parallel Operation** | Both branches can run simultaneously (production + feature testing) |
| **Clear History** | Git log shows exact separation between production fixes and feature development |

---

### Git Commands Reference

#### **Initial Setup (One-time)**

```bash
# 1. Ensure production is clean
git checkout production-v2.0
git status  # Should be clean

# 2. Tag current production state
git tag -a v2.0-stable-$(date +%Y%m%d) -m "Stable production before multi-account development"
git push origin --tags

# 3. Create feature branch
git checkout -b feature/multi-account-v4.0
git push -u origin feature/multi-account-v4.0

# 4. Update plan status
# (Update MULTI_ACCOUNT_IMPLEMENTATION_PLAN.md)
git add MULTI_ACCOUNT_IMPLEMENTATION_PLAN.md
git commit -m "docs: Add branch strategy to implementation plan"
git push origin feature/multi-account-v4.0

# 5. Return to production for any urgent work
git checkout production-v2.0
```

#### **Daily Development**

```bash
# Start of day: Sync feature branch
git checkout feature/multi-account-v4.0
git pull origin feature/multi-account-v4.0
git merge production-v2.0  # Get overnight production fixes
git push origin feature/multi-account-v4.0

# Development work
# ... code, code, code ...
git add .
git commit -m "feat: Implement account manager"
git push origin feature/multi-account-v4.0

# End of day: Verify production still stable
git checkout production-v2.0
git pull origin production-v2.0
# ... check if bot ran fine ...
```

#### **Emergency Production Fix**

```bash
# Save feature work
git checkout feature/multi-account-v4.0
git stash

# Fix production
git checkout production-v2.0
git pull
# ... fix bug ...
git add <fixed-files>
git commit -m "fix: Critical bug description"
git push origin production-v2.0

# Deploy to server
# ... restart bot with fix ...

# Bring fix to feature branch
git checkout feature/multi-account-v4.0
git merge production-v2.0
git stash pop
git push origin feature/multi-account-v4.0
```

#### **Weekly Sync**

```bash
# Every Friday or before weekend
git checkout feature/multi-account-v4.0
git merge production-v2.0
# Resolve any conflicts
git push origin feature/multi-account-v4.0

# Tag feature progress
git tag -a multi-account-week-1 -m "Week 1 progress"
git push origin --tags
```

#### **When Ready to Merge (4+ weeks later)**

```bash
# Final preparation
git checkout feature/multi-account-v4.0
git merge production-v2.0  # Final sync
# ... comprehensive testing ...

# Merge to production (when ready)
git checkout production-v2.0
git merge feature/multi-account-v4.0
git tag -a v4.0-multi-account-live -m "Multi-account system deployed"
git push origin production-v2.0 --tags

# Or: Keep feature as new production
git checkout feature/multi-account-v4.0
git tag -a v4.0-production -m "New production version"
# Update deployment scripts to use this branch
```

---

### Branch Status Tracking

```bash
# Check which branch you're on
git branch
# * feature/multi-account-v4.0  (you are here)
#   production-v2.0

# See all commits on feature branch (not in production)
git log production-v2.0..feature/multi-account-v4.0

# See all commits on production (not in feature)
git log feature/multi-account-v4.0..production-v2.0

# Check if branches have diverged
git log --oneline --graph --all --decorate

# Compare files between branches
git diff production-v2.0 feature/multi-account-v4.0 -- bot/strategy/gbot_ws.py
```

---

### Decision Point: User Action Required

**CURRENT STATUS:**
- ✅ Implementation plan complete
- ✅ Branch strategy approved
- ✅ User confirmed: "Need to do some work in this branch first"

**WAITING FOR:**
- User to complete current work on `production-v2.0`
- User confirmation to create `feature/multi-account-v4.0` branch
- User ready to start Phase 1 implementation

**NEXT STEPS (When User Ready):**
1. ✅ Commit current production work
2. ✅ Tag production as stable baseline
3. ✅ Create feature branch
4. ✅ Begin Phase 1 development

**USER'S CHOICE:**
- Continue working on production-v2.0 (current)
- Signal when ready to create feature branch
- Begin multi-account development

---

## 🧠 Architecture Philosophy

### Core Principle: **Shared Brain, Multiple Hands**

```
┌─────────────────────────────────────────────────────────────┐
│                    🧠 SHARED BRAIN (Strategy Logic)         │
│                                                             │
│  • Grid trading algorithm (same for all accounts)          │
│  • Fill detection logic (same for all accounts)            │
│  • Safety systems (same for all accounts)                  │
│  • Order placement logic (same for all accounts)           │
│  • Volatility monitoring (same for all accounts)           │
│                                                             │
│  Location: bot/strategy/gbot_ws.py (UNCHANGED)             │
└───────────────────┬─────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┬───────────────┐
        │                       │               │
        ▼                       ▼               ▼
┌───────────────┐      ┌───────────────┐  ┌───────────────┐
│ 👐 Account 1  │      │ 👐 Account 2  │  │ 👐 Account 3  │
│  live-main    │      │  live-test    │  │  live-backup  │
├───────────────┤      ├───────────────┤  ├───────────────┤
│ API: Live     │      │ API: Testnet  │  │ API: Live     │
│ STEP: 2000    │      │ STEP: 200     │  │ STEP: 1000    │
│ MAX_POS: 3    │      │ MAX_POS: 10   │  │ MAX_POS: 5    │
│ Conservative  │      │ Aggressive    │  │ Moderate      │
└───────────────┘      └───────────────┘  └───────────────┘
```

### What Stays Same (The Brain)

**Strategy Code:** `bot/strategy/gbot_ws.py` - **COMPLETELY UNCHANGED**

- ✅ Grid trading logic
- ✅ Fill detection algorithm
- ✅ Order placement strategy
- ✅ Safety systems logic
- ✅ Volatility monitoring code
- ✅ Position management logic
- ✅ TP calculation method
- ✅ Error handling

### What Changes (The Configuration)

**Per-Account Settings:**

- ❌ API keys (different accounts)
- ❌ Grid parameters (STEP, LOWER, UPPER)
- ❌ Position limits (MAX_OPEN_POSITIONS)
- ❌ Safety limits (MAX_LOSS, etc.)
- ❌ File paths (logs, state, heartbeat)

**Example:**

```python
# SAME BRAIN CODE - Used by all accounts
class GridBot:
    def calculate_grid_levels(self):
        """This logic is IDENTICAL for all accounts"""
        levels = []
        current = self.grid_lower
        while current <= self.grid_upper:
            levels.append(current)
            current += self.grid_step  # Only this VALUE differs
        return levels

# DIFFERENT CONFIGURATIONS
account_live_main = GridBot(
    grid_step=2000,      # Conservative
    max_positions=3,
    account_id="live-main"
)

account_live_test = GridBot(
    grid_step=200,       # Aggressive
    max_positions=10,
    account_id="live-test"
)

# Both use SAME code, DIFFERENT parameters!
```

---

## ⚠️ Risk Assessment

### Will System Become "Heywire" or Out of Control?

| Risk Factor | Current | Multi-Account | Mitigation | Confidence |
|-------------|---------|---------------|------------|------------|
| **Code Complexity** | Simple | Moderate | Proper abstractions | 🟢 High |
| **Control** | Easy | Requires UI | Centralized dashboard | 🟢 High |
| **Debugging** | Straightforward | Needs account logs | Separate log files | 🟡 Medium |
| **Safety** | Single point | Multiple points | Global safety monitor | 🟢 High |
| **Capital Risk** | Concentrated | Distributed | Per-account + global limits | 🟢 **LOWER** |
| **Resource Usage** | Low | Higher | CPU/memory monitoring | 🟢 High |
| **Maintenance** | Single config | Multiple configs | Config templates | 🟡 Medium |
| **Cascading Failures** | N/A | Possible | Account isolation | 🟢 High |

### Overall Risk: **MANAGEABLE** ✅

With proper safety controls, system remains manageable and becomes **safer** due to:
- Risk diversification across accounts
- Account isolation prevents cross-contamination
- Global safety monitoring across all accounts

---

## 🚀 Implementation Phases

### Phase 1: Foundation (Days 1-2, ~6 hours)

**Goal:** Create multi-account infrastructure without breaking existing system

#### Deliverables:

1. **Directory Structure**
   ```
   WorkingBot/
   ├── accounts/                    # NEW - Account configs
   │   ├── live-main.env
   │   ├── live-test.env
   │   └── account-template.env
   │
   ├── state/                       # NEW - Account state files
   │   ├── live-main/
   │   │   ├── .heartbeat
   │   │   ├── .lock
   │   │   ├── bot.log
   │   │   ├── equity_snapshots.json
   │   │   └── .volatility_halt.json
   │   └── live-test/
   │       └── ...
   │
   └── bot/
       └── account_system/          # NEW - Multi-account code
           ├── __init__.py
           ├── url_detector.py
           ├── account_profile.py
           ├── account_manager.py
           └── safety_monitor.py
   ```

2. **Core Components**
   - URL auto-detector (testnet vs live)
   - Account profile data structure
   - Account manager (load/list/manage accounts)
   - Global safety monitor

3. **Backward Compatibility**
   - Old commands still work: `python3 bot/run.py demo infinite`
   - New commands added: `python3 bot/run.py live-main infinite`

#### Testing:
- ✅ Directory creation
- ✅ Load account configs
- ✅ URL detection (testnet vs live)
- ✅ Legacy mode still works

---

### Phase 2: Strategy Integration (Day 3, ~4 hours)

**Goal:** Make GridBot strategy accept account-specific configurations

#### Changes:

**File:** `bot/strategy/gbot_ws.py`

```python
class GridBot:
    def __init__(
        self,
        account_id: str = None,      # NEW parameter (optional)
        state_dir: Path = None,       # NEW parameter (optional)
        log_file: Path = None,        # NEW parameter (optional)
        **kwargs
    ):
        # BACKWARD COMPATIBLE: Use defaults if not provided
        self.account_id = account_id or "default"
        self.state_dir = state_dir or Path(".")
        self.log_file = log_file or Path("bot_live.log")
        
        # Account-specific file paths
        self.heartbeat_file = self.state_dir / ".heartbeat"
        self.lock_file = self.state_dir / ".lock"
        self.halt_file = self.state_dir / ".volatility_halt.json"
        self.equity_file = self.state_dir / "equity_snapshots.json"
        
        # Rest of initialization UNCHANGED
        # Strategy logic UNCHANGED
```

**Key:** Only file paths change, **strategy logic remains IDENTICAL!**

#### Testing:
- ✅ Single account works with new code
- ✅ Legacy mode still functional
- ✅ Separate state files created
- ✅ No cross-contamination

---

### Phase 3: Enhanced Runner (Day 3, ~2 hours)

**Goal:** Update bot/run.py to support both legacy and multi-account modes

#### Changes:

**File:** `bot/run.py`

```python
"""
Enhanced bot runner with multi-account support

BACKWARD COMPATIBLE:
  python3 bot/run.py demo infinite    # Legacy (still works)
  python3 bot/run.py live infinite    # Legacy (still works)

NEW MULTI-ACCOUNT MODE:
  python3 bot/run.py                  # Show all accounts
  python3 bot/run.py live-main infinite    # Start specific account
  python3 bot/run.py live-test infinite    # Start specific account
"""

def main():
    if len(sys.argv) < 2:
        show_available_accounts()  # NEW - Show account list
        sys.exit(0)
    
    account_or_mode = sys.argv[1]
    
    # Auto-detect legacy vs new mode
    if account_or_mode in ["demo", "live"]:
        run_legacy_mode(account_or_mode)  # Old behavior
    else:
        run_account_mode(account_or_mode)  # New behavior
```

#### Testing:
- ✅ Legacy commands work
- ✅ New account commands work
- ✅ Account list displays correctly
- ✅ Error handling for invalid accounts

---

### Phase 4: WebUI Multi-Account Dashboard (Days 4-5, ~8 hours)

**Goal:** Single WebUI dashboard controlling all accounts

**Architecture Decision:** ✅ **Single WebUI** (not multiple WebUIs)

**Why Single WebUI:**
- Better UX: See all accounts at a glance
- Easier monitoring: One dashboard instead of 3 browser tabs
- Global controls: Emergency stop all, combined metrics
- Less resources: One React app vs multiple
- Centralized safety: Global loss limits visible

**Alternative Rejected:** Multiple WebUIs (one per account)
- Reason: Confusing to manage, no global view, wastes resources

#### New Features:

1. **Multi-Account Dashboard** (Main View)
   ```
   ┌──────────────────────────────────────────────────┐
   │  WorkingBot - Multi-Account Dashboard            │
   ├──────────────────────────────────────────────────┤
   │  🌍 GLOBAL STATUS                                │
   │  Active: 2/3 | Total P&L: +₹12,396              │
   │  Global Loss: ₹15,240 / ₹100,000 (15%)          │
   │  [🚨 EMERGENCY STOP ALL]                         │
   ├──────────────────────────────────────────────────┤
   │  💰 LIVE-MAIN (Conservative)                     │
   │  Status: 🟢 Running | P&L: +₹8,240               │
   │  Grid: $2000 | Positions: 2/3                    │
   │  [View Details] [Stop] [Configure]               │
   ├──────────────────────────────────────────────────┤
   │  🧪 LIVE-TEST (Aggressive - Testnet)             │
   │  Status: 🟢 Running | P&L: +$4,156               │
   │  Grid: $200 | Positions: 7/10                    │
   │  [View Details] [Stop] [Configure]               │
   ├──────────────────────────────────────────────────┤
   │  💰 LIVE-BACKUP (Moderate)                       │
   │  Status: 🔴 Stopped                              │
   │  [Start] [Configure]                             │
   ├──────────────────────────────────────────────────┤
   │  [➕ Add New Account]                            │
   └──────────────────────────────────────────────────┘
   ```

2. **Backend API Endpoints**
   - `GET /api/accounts` - List all accounts
   - `POST /api/accounts/<id>/start` - Start account
   - `POST /api/accounts/<id>/stop` - Stop account
   - `POST /api/accounts/stop-all` - Emergency stop all
   - `GET /api/accounts/<id>/config` - Get config
   - `PUT /api/accounts/<id>/config` - Update config
   - `GET /api/accounts/<id>/logs` - Stream logs
   - `GET /api/global/safety` - Global safety status

3. **Frontend Components**
   - MultiAccountDashboard (main view)
   - AccountCard (per-account widget)
   - GlobalSafetyIndicator (overall health)
   - EmergencyStopButton (big red button)
   - AddAccountDialog (create new account)

#### Testing:
- ✅ Dashboard displays all accounts
- ✅ Start/stop individual accounts
- ✅ Emergency stop all works
- ✅ Config editor per account
- ✅ Log viewer per account
- ✅ Real-time updates

---

### Phase 5: Safety Controls (Day 6, ~4 hours)

**Goal:** Implement safety mechanisms to prevent "heywire" scenarios

#### Safety Features:

1. **Global Loss Limit**
   ```python
   GLOBAL_MAX_LOSS_INR = 100000  # Total across ALL accounts
   
   # Auto-stop all bots if combined loss exceeds limit
   ```

2. **Resource Monitoring**
   ```python
   MAX_CONCURRENT_ACCOUNTS = 5  # Hard limit
   MAX_CPU_PERCENT = 80
   MAX_MEMORY_PERCENT = 80
   
   # Prevent new bots if system resources high
   ```

3. **Account Dependency Rules**
   ```python
   # If live-main fails, auto-stop live-test
   DEPENDENCIES = {
       "live-main": ["live-test"],
   }
   ```

4. **Emergency Kill Switch**
   ```python
   # Stop all bots immediately (nuclear option)
   # Accessible via WebUI big red button
   # Or CLI: python3 manage.py emergency-stop-all
   ```

5. **Configuration Guard**
   ```python
   # Protected parameters require 2FA confirmation
   PROTECTED_PARAMS = [
       "DELTA_API_KEY",
       "DELTA_API_SECRET",
       "DELTA_API_URL"
   ]
   ```

#### Testing:
- ✅ Global loss limit triggers
- ✅ Resource limits enforced
- ✅ Emergency stop works
- ✅ Dependency rules work
- ✅ Config protection works

---

### Phase 6: Testing & Validation (Day 7, ~6 hours)

**Goal:** Comprehensive testing before production

#### Test Scenarios:

1. **Isolation Test**
   - Start 2 accounts simultaneously
   - Verify separate state files
   - Verify separate log files
   - Verify no cross-contamination

2. **Safety Test**
   - Simulate losses in both accounts
   - Verify global limit triggers
   - Test emergency stop all
   - Test individual stop

3. **Resource Test**
   - Start 3+ accounts
   - Monitor CPU/memory
   - Verify resource limits enforced

4. **Failure Test**
   - Kill one bot (simulate crash)
   - Verify dependency rules trigger
   - Verify other bots unaffected

5. **Backward Compatibility Test**
   - Run legacy commands
   - Verify old behavior preserved
   - Test migration path

#### Success Criteria:
- ✅ All tests pass
- ✅ No regressions in legacy mode
- ✅ Complete account isolation
- ✅ Safety controls functional
- ✅ Resource limits working

---

## 🔧 Technical Specifications

### File Structure

```
WorkingBot/
├── accounts/                           # Account configurations
│   ├── live-main.env                   # Conservative live account
│   ├── live-test.env                   # Aggressive test account
│   ├── live-backup.env                 # Backup account
│   └── account-template.env            # Template for new accounts
│
├── state/                              # Account state (isolated)
│   ├── live-main/
│   │   ├── .heartbeat                  # Account-specific heartbeat
│   │   ├── .lock                       # Account-specific lock
│   │   ├── bot.log                     # Account-specific log
│   │   ├── equity_snapshots.json       # Account-specific equity
│   │   └── .volatility_halt.json       # Account-specific halt state
│   │
│   ├── live-test/
│   │   └── ... (same structure)
│   │
│   └── live-backup/
│       └── ... (same structure)
│
├── bot/
│   ├── account_system/                 # NEW - Multi-account system
│   │   ├── __init__.py
│   │   ├── url_detector.py             # Auto-detect testnet vs live
│   │   ├── account_profile.py          # Account data structure
│   │   ├── account_manager.py          # Load/manage accounts
│   │   └── safety_monitor.py           # Global safety monitoring
│   │
│   ├── strategy/
│   │   └── gbot_ws.py                  # UNCHANGED (same brain)
│   │
│   └── run.py                          # ENHANCED (backward compatible)
│
├── webui/
│   ├── backend/
│   │   └── app.py                      # ENHANCED (multi-account API)
│   │
│   └── frontend/
│       └── src/
│           └── components/
│               ├── MultiAccountDashboard.tsx    # NEW
│               ├── AccountCard.tsx              # NEW
│               └── GlobalSafetyIndicator.tsx    # NEW
│
└── grid_config.env                     # LEGACY (still works)
```

### Account Configuration Format

**File:** `accounts/live-main.env`

```bash
# ═══════════════════════════════════════════════════════════
# Account Profile: LIVE-MAIN (Conservative Production)
# ═══════════════════════════════════════════════════════════

# Account Identity
ACCOUNT_ID=live-main
ACCOUNT_NAME="Live Main - Conservative"
ACCOUNT_DESCRIPTION="Primary production trading account"

# API Configuration (Auto-detects environment from URL)
DELTA_API_URL=https://api.india.delta.exchange
DELTA_API_KEY=your_live_api_key_here
DELTA_API_SECRET=your_live_api_secret_here

# Grid Strategy
GRID_LOWER=105000.0
GRID_UPPER=120000.0
GRID_STEP=2000.0              # Conservative (wide grid)
REFERENCE_LEVEL=110000.0
GRIDBOT_LOT=2                 # Larger lots
MAX_OPEN_POSITIONS=3          # Fewer positions

# Safety Limits
MAX_ACCOUNT_LOSS_INR=50000
GUARDIAN_MAX_ACCOUNT_LOSS_INR=40000
MAX_MARGIN_UTILIZATION=40
VOLATILITY_MAX_IV=45
VOLATILITY_MAX_RV=55

# Features
ENABLE_TELEGRAM_ALERTS=true
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

**File:** `accounts/live-test.env`

```bash
# ═══════════════════════════════════════════════════════════
# Account Profile: LIVE-TEST (Aggressive Testing on Testnet)
# ═══════════════════════════════════════════════════════════

# Account Identity
ACCOUNT_ID=live-test
ACCOUNT_NAME="Live Test - Aggressive"
ACCOUNT_DESCRIPTION="Testnet API for aggressive strategy testing"

# API Configuration (Testnet - auto-detected)
DELTA_API_URL=https://cdn-ind.testnet.deltaex.org
DELTA_API_KEY=your_testnet_api_key_here
DELTA_API_SECRET=your_testnet_api_secret_here

# Grid Strategy (AGGRESSIVE)
GRID_LOWER=105000.0
GRID_UPPER=120000.0
GRID_STEP=200.0               # Very tight! (10x tighter than main)
REFERENCE_LEVEL=110000.0
GRIDBOT_LOT=1                 # Small lots
MAX_OPEN_POSITIONS=10         # Many positions (stress test)

# Safety Limits (Lower for testing)
MAX_ACCOUNT_LOSS_INR=10000
GUARDIAN_MAX_ACCOUNT_LOSS_INR=8000
MAX_MARGIN_UTILIZATION=50
VOLATILITY_MAX_IV=60
VOLATILITY_MAX_RV=70

# Features
ENABLE_TELEGRAM_ALERTS=false  # Don't spam during tests
```

### URL Auto-Detection

```python
class URLDetector:
    """Automatically detect trading environment from API URL"""
    
    TESTNET_DOMAINS = [
        "testnet.deltaex.org",
        "cdn-ind.testnet.deltaex.org",
        "testnet.delta.exchange"
    ]
    
    LIVE_DOMAINS = [
        "api.india.delta.exchange",
        "api.delta.exchange"
    ]
    
    @classmethod
    def detect_environment(cls, api_url: str) -> str:
        """Returns: 'testnet' or 'live'"""
        domain = urlparse(api_url).netloc
        
        if any(t in domain for t in cls.TESTNET_DOMAINS):
            return "testnet"
        elif any(l in domain for l in cls.LIVE_DOMAINS):
            return "live"
        else:
            raise ValueError(f"Unknown domain: {domain}")
```

---

## 🛡️ Safety Controls

### 1. Emergency Stop All

**Purpose:** Nuclear option to stop everything immediately

**Triggers:**
- User clicks big red "STOP ALL" button
- Global loss limit exceeded
- System resources critical

**Implementation:**
```python
class MultiAccountManager:
    def emergency_stop_all(self, reason: str):
        """Stop all bots immediately"""
        for account_id in self.running_bots:
            self._kill_bot(account_id, force=True)
        
        self._send_critical_alert(
            "🚨 EMERGENCY: All bots stopped",
            reason=reason
        )
        
        self._audit_log("EMERGENCY_STOP_ALL", reason)
```

### 2. Global Loss Limit

**Purpose:** Prevent total loss across all accounts

```python
GLOBAL_MAX_LOSS_INR = 100000  # ₹100k total

class GlobalSafetyMonitor:
    def check_global_limits(self):
        total_loss = sum(
            self._get_account_loss(acc) 
            for acc in self.accounts
        )
        
        if total_loss > GLOBAL_MAX_LOSS_INR:
            self.manager.emergency_stop_all(
                f"Global loss limit: ₹{total_loss:,.0f}"
            )
```

### 3. Resource Limits

**Purpose:** Prevent system overload

```python
MAX_CONCURRENT_ACCOUNTS = 5
MAX_CPU_PERCENT = 80
MAX_MEMORY_PERCENT = 80

class ResourceMonitor:
    def check_resources(self):
        if psutil.cpu_percent() > MAX_CPU_PERCENT:
            self._prevent_new_bots()
            self._alert("CPU usage high")
        
        if psutil.virtual_memory().percent > MAX_MEMORY_PERCENT:
            self._prevent_new_bots()
            self._alert("Memory usage high")
```

### 4. Account Dependency Rules

**Purpose:** Prevent cascading failures

```python
DEPENDENCIES = {
    "live-main": {
        "on_failure": ["stop", "live-test"],
        "reason": "Main account failed"
    }
}

# If live-main crashes, auto-stop live-test
```

### 5. Configuration Protection

**Purpose:** Prevent accidental changes to critical settings

```python
PROTECTED_PARAMS = [
    "DELTA_API_KEY",
    "DELTA_API_SECRET",
    "DELTA_API_URL"
]

# Requires 2FA confirmation via Telegram
```

---

## 🧪 Testing Strategy

### Test Plan

| Phase | Test Type | Duration | Pass Criteria |
|-------|-----------|----------|---------------|
| 1 | Unit Tests | 2 hours | All components work individually |
| 2 | Integration Tests | 3 hours | Components work together |
| 3 | Isolation Tests | 2 hours | No cross-contamination |
| 4 | Safety Tests | 2 hours | All safety controls trigger correctly |
| 5 | Load Tests | 1 hour | Resource limits enforced |
| 6 | Regression Tests | 2 hours | Legacy mode still works |

### Critical Test Cases

#### Test 1: Account Isolation

```bash
# Start 2 accounts
python3 bot/run.py live-main infinite &
python3 bot/run.py live-test infinite &

# Verify separate files
ls -la state/live-main/
ls -la state/live-test/

# Expected: No shared files
```

**Pass Criteria:**
- ✅ Separate .heartbeat files
- ✅ Separate .lock files
- ✅ Separate log files
- ✅ No cross-contamination

#### Test 2: Global Loss Limit

```bash
# Simulate losses in both accounts
# (Manually edit equity snapshots or run in volatile market)

# Expected: Auto-stop when combined loss > ₹100k
```

**Pass Criteria:**
- ✅ Monitors both accounts
- ✅ Calculates total loss correctly
- ✅ Stops all bots at threshold
- ✅ Sends critical alert

#### Test 3: Emergency Stop

```bash
# Click "STOP ALL" button in WebUI

# Expected: All bots stop within 5 seconds
```

**Pass Criteria:**
- ✅ All bot processes killed
- ✅ All lock files released
- ✅ Alert sent
- ✅ Audit log updated

#### Test 4: Resource Limits

```bash
# Start 6 accounts (exceeds MAX_CONCURRENT_ACCOUNTS=5)

# Expected: 6th account rejected
```

**Pass Criteria:**
- ✅ Error message shown
- ✅ 6th bot not started
- ✅ System remains stable

#### Test 5: Backward Compatibility

```bash
# Run old commands
python3 bot/run.py demo infinite
python3 bot/run.py live infinite

# Expected: Works exactly as before
```

**Pass Criteria:**
- ✅ Legacy mode functional
- ✅ Uses old config file
- ✅ No regressions

---

## 📅 Rollout Plan

### Week 1: Development (Days 1-7)

**Days 1-2:** Phase 1 - Foundation
- Create directory structure
- Build core components
- Implement URL detection
- Test account loading

**Day 3:** Phase 2 & 3 - Integration
- Modify GridBot for multi-account
- Update bot/run.py
- Test backward compatibility

**Days 4-5:** Phase 4 - WebUI
- Build multi-account dashboard
- Create backend API
- Build frontend components

**Day 6:** Phase 5 - Safety
- Implement global safety monitor
- Add resource limits
- Create emergency controls

**Day 7:** Phase 6 - Testing
- Run all test scenarios
- Fix bugs
- Document issues

### Week 2: Testing Phase

**Days 8-10:** Internal Testing
- Run 2 accounts for 3 days
- Monitor for issues
- Verify safety controls
- Test resource usage

**Days 11-14:** Extended Testing
- Test failure scenarios
- Simulate high-volatility markets
- Stress test resource limits
- Document all findings

### Week 3: Pilot Deployment

**Days 15-17:** Single Account Migration
- Migrate existing live bot to account-based system
- Run for 3 days
- Verify no regressions

**Days 18-21:** Two Account Deployment
- Add second account (testnet)
- Run both for 4 days
- Monitor stability

### Week 4: Production Ready

**Days 22-28:** Production Monitoring
- Full week of dual-account operation
- Daily health checks
- Performance optimization
- Final documentation

**Day 29:** Go/No-Go Decision
- Review all metrics
- Assess stability
- Make production decision

**Day 30:** Production Deployment or Rollback

---

## ❓ FAQ

### Q1: Will the strategy logic change?

**A:** NO. The strategy code (`bot/strategy/gbot_ws.py`) remains **completely unchanged**. Only configuration parameters differ per account.

### Q2: Can I still use the old single-account mode?

**A:** YES. Backward compatibility is preserved. Old commands still work:
```bash
python3 bot/run.py demo infinite    # Still works
python3 bot/run.py live infinite    # Still works
```

### Q3: How many accounts can I run simultaneously?

**A:** Recommended: 2-3 accounts. Hard limit: 5 accounts (to prevent resource exhaustion).

### Q4: What happens if one account fails?

**A:** Account isolation prevents cross-contamination. Other accounts continue running. Dependency rules can auto-stop related accounts if configured.

### Q5: Will this increase risk?

**A:** NO, it **decreases risk** through:
- Risk diversification across accounts
- Account isolation (failures don't cascade)
- Global safety monitoring
- Emergency stop all capability

### Q6: How do I add a new account?

**A:** Simple process:
1. Copy `accounts/account-template.env`
2. Rename to `accounts/my-new-account.env`
3. Edit configuration (API keys, grid params)
4. Start: `python3 bot/run.py my-new-account infinite`

### Q7: Can I test aggressive strategies safely?

**A:** YES! Use testnet API URL:
```bash
DELTA_API_URL=https://cdn-ind.testnet.deltaex.org
```
System auto-detects testnet and marks account as "test" mode.

### Q8: What if system becomes "heywire"?

**A:** Multiple safeguards:
- Emergency stop all (big red button)
- Global loss limit (auto-stops everything)
- Resource limits (prevents overload)
- Account isolation (prevents cascading failures)

### Q9: How do I monitor all accounts?

**A:** Single WebUI dashboard shows:
- All accounts status
- Combined P&L
- Individual account metrics
- Global safety status

### Q10: Can I migrate my existing setup?

**A:** YES. Migration path:
1. Current setup continues working (backward compatible)
2. Create account config: `accounts/live-main.env`
3. Copy your `grid_config.env` settings to account config
4. Test new account: `python3 bot/run.py live-main infinite`
5. Once verified, switch fully to new system

---

## 📊 Success Metrics

### Implementation Success

- ✅ All 6 phases completed
- ✅ All tests pass
- ✅ No regressions in legacy mode
- ✅ Documentation complete

### Operational Success (After 1 Month)

- ✅ Zero critical bugs
- ✅ < 1% downtime
- ✅ Safety controls never triggered accidentally
- ✅ Resource usage < 50% CPU, < 60% memory
- ✅ Account isolation maintained (no cross-contamination)

### Business Success (After 3 Months)

- ✅ Successfully running 2+ accounts
- ✅ Able to test new strategies without stopping live trading
- ✅ Positive P&L on all accounts
- ✅ No safety incidents
- ✅ User satisfaction high

---

## 📝 Next Steps

### Immediate Actions

1. **Complete Current Production Work** ✅ **IN PROGRESS**
   - User finishing work on `production-v2.0` branch
   - Continue live trading development/fixes
   - No disruption to current workflow
   - User's directive: _"I need to do some work in this branch first"_

2. **When Ready: Create Feature Branch** ⏳ **WAITING FOR USER SIGNAL**
   - Tag production: `v2.0-stable-before-multi-account`
   - Create branch: `feature/multi-account-v4.0`
   - Update status in this document
   - Begin Phase 1 implementation

3. **Branch Strategy Understood** ✅ **COMPLETE**
   - ✅ Parallel development workflow documented
   - ✅ Production protection strategy clear
   - ✅ Emergency fix process understood
   - ✅ Sync strategy (production → feature) approved

### Current Project Status

| Item | Status |
|------|--------|
| **Active Branch** | `production-v2.0` |
| **User Task** | Complete current work before multi-account |
| **Implementation Plan** | ✅ Complete and documented |
| **Branch Strategy** | ✅ Approved (separate development branch) |
| **Risk to Production** | 🟢 ZERO (isolated development) |
| **Next Milestone** | User signals ready to create feature branch |

**User's Words:** _"I need to do some work in this branch first"_

✅ **Approved:** User will create `feature/multi-account-v4.0` when ready  
✅ **Safe:** Production work continues uninterrupted  
✅ **Flexible:** No deadline, create feature branch when convenient  

### Decision Points

| Checkpoint | Decision | Options |
|------------|----------|---------|
| **NOW** | Complete production work | ⏳ User working on `production-v2.0` |
| **When User Ready** | Create feature branch? | ✅ Create `feature/multi-account-v4.0` |
| After Phase 1 | Continue? | ✅ Phase 2-3 / ⏸️ Pause / 🔄 Adjust |
| After Phase 4 | Deploy? | ✅ Testing / ⏸️ More Dev / 🔄 Redesign |
| After Week 2 Testing | Production? | ✅ Pilot / ⏸️ More Testing / ❌ Rollback |
| After Week 4 Pilot | Full Deploy? | ✅ Merge to production / ⏸️ Keep parallel / 🔄 Modify |

---

## 🎯 Recommendation

**Proceed with implementation?** ✅ **YES - When User Ready**

**Current Status:** ⏸️ **PAUSED** - Waiting for user to complete production work

**Confidence Level:** 🟢 **High** (85%)

**Why:**
1. Architecture is sound (shared brain, multiple configs)
2. Safety controls comprehensive (emergency stop, global limits)
3. Backward compatible (no disruption to current operation)
4. Phased approach (can abort at any checkpoint)
5. Clear benefits (parallel testing, risk diversification)
6. **Branch strategy protects production** (isolated development)

**Conditions:**
1. ✅ User completes current work on `production-v2.0` FIRST
2. ✅ Create `feature/multi-account-v4.0` branch when ready
3. Start with 2 accounts only (live-main + live-test)
4. Implement all safety controls
5. Complete testing before production merge

**Timeline:** Starts when user creates feature branch (TBD)

**Next Action Required:** User signals "ready to create feature branch"

---

**Document Version:** 1.1  
**Last Updated:** October 30, 2025  
**Status:** Planning Complete - Waiting for User to Create Feature Branch  
**Production Branch:** `production-v2.0` (Active - User working)  
**Feature Branch:** `feature/multi-account-v4.0` (Not yet created)  
**Estimated Start:** When user ready (TBD)
