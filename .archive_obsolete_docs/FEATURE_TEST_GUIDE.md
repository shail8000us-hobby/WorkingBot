# Complete Feature Test Guide
**Date:** November 16, 2025  
**Frontend:** http://localhost:5557  
**Backend:** http://localhost:5555  

---

## 🎯 ALL FEATURES (Old + New)

### ✅ PRE-EXISTING FEATURES (Already in Production)

These 14 sections were **already built** before this week's work:

| # | Section | Description | Status |
|---|---------|-------------|--------|
| 1 | **Dashboard** | Trading overview, P&L, positions summary | ✅ Working |
| 2 | **Configuration** | Bot settings, grid parameters | ✅ Working |
| 3 | **Risk & Safety** | Risk analytics, safety limits | ✅ Working |
| 4 | **Positions** | Active positions, grid visualization | ✅ Working |
| 5 | **Bot Management** | Start/stop bot, emergency controls | ✅ Working |
| 6 | **Monitoring** | Real-time telemetry, system stats | ✅ Working |
| 7 | **Guardian Dashboard** | Circuit breakers, risk protection | ✅ Working |
| 8 | **Bot Strategy** | Strategy selection, live decision engine | ✅ Working |
| 9 | **Bot Actions** | Real-time trading decisions log | ✅ Working |
| 10 | **Brain Flow Graph** | Visual decision tree flowchart | ✅ Working |
| 11 | **Intelligence** | AI insights, trading intelligence | ✅ Working |
| 12 | **Logs Panel** | Live log streaming | ✅ Working |
| 13 | **PM2 Panel** | Process management dashboard | ✅ Working |
| 14 | **Todo List** | Task tracking system | ✅ Working |

---

## 🆕 NEW FEATURES BUILT THIS WEEK

### Phase 2: Configuration Freedom (3 Features)

| # | Section | Description | Status |
|---|---------|-------------|--------|
| 15 | **File Editor** | Monaco-based code editor, browse/edit files | ✅ Ready to test |
| 16 | **Strategy Editor** | Visual strategy builder, 3 templates, comparison | ✅ Ready to test |
| 17 | **Config Editor** | Dual YAML/Form config editor with validation | ✅ Ready to test |

### Phase 3: Intelligent Automation (3 Features)

| # | Section | Description | Status |
|---|---------|-------------|--------|
| 18 | **Mode Switcher** | Auto LONG/SHORT switching, manual override | ⚠️ Needs service init |
| 19 | **System Health** | CPU/memory/disk monitoring, auto-healing | ⚠️ Needs service init |
| 20 | **Instance Manager** | Multi-instance bot control (demo + live) | ✅ Ready to test |

**Total:** 20 sections (14 old + 6 new)

---

## 🧪 TESTING INSTRUCTIONS

### Step 1: Refresh Browser
1. Go to http://localhost:5557
2. Hard refresh: `Cmd + Shift + R` (Mac) or `Ctrl + Shift + R` (Windows)
3. Open DevTools Console: `Cmd + Option + J`
4. Check for errors (should see fewer warnings now)

---

### Step 2: Test Pre-Existing Features (Quick Sanity Check)

**Test 1: Dashboard**
- Click "Dashboard" in left nav
- ✅ Should show: P&L summary, positions count, current price
- ✅ Should show: Charts and metrics

**Test 2: Configuration**
- Click "Configuration"
- ✅ Should show: Bot config settings
- ✅ Try changing a value (don't save)

**Test 3: Positions**
- Click "Positions"
- ✅ Should show: Active positions table
- ✅ Grid visualization

**Test 4: Bot Management**
- Click "Bot Management"
- ✅ Should show: Start/Stop buttons
- ✅ Emergency controls visible

**Test 5: Logs Panel**
- Click "Logs Panel"
- ✅ Should show: Live log stream
- ✅ Auto-scrolling logs

---

### Step 3: Test NEW Phase 2 Features

#### NEW Feature #1: File Editor 📝

**Location:** Click "File Editor" in navigation (Code icon)

**What to test:**
1. **File Browser**
   - ✅ See file tree on left side
   - ✅ Navigate folders: bot/, config/, webui/
   - ✅ Click on a file (e.g., `config.yaml`)

2. **Code Editor**
   - ✅ File opens in Monaco Editor (VS Code-style)
   - ✅ Syntax highlighting visible (colors for keywords)
   - ✅ Line numbers on left
   - ✅ Try typing - should have auto-complete

3. **File Operations**
   - ✅ Click "Save" button
   - ✅ Should show success message
   - ✅ Try "Download" button
   - ✅ Should download file

**Expected Result:**
- Full-featured code editor in browser
- Can edit Python, YAML, JSON, JavaScript files
- Syntax highlighting works
- Save/download functional

---

#### NEW Feature #2: Strategy Editor 🎯

**Location:** Click "Strategy Editor" in navigation (SlidersHorizontal icon)

**What to test:**
1. **Template Selection**
   - ✅ See 3 strategy cards:
     * Conservative (wide range, large steps)
     * Aggressive (narrow range, small steps)
     * Balanced (medium settings)
   - ✅ Click "Use Template" on Conservative

2. **Strategy Configuration**
   - ✅ See grid configuration form
   - ✅ Adjust "Lower Price" slider
   - ✅ Adjust "Upper Price" slider
   - ✅ Change "Step Size"
   - ✅ Change "Lot Size"

3. **Visual Grid Preview**
   - ✅ See grid visualization update in real-time
   - ✅ Shows number of levels
   - ✅ Shows price range

4. **Strategy Comparison**
   - ✅ Click "Compare Strategies"
   - ✅ Select 2 strategies to compare
   - ✅ See side-by-side comparison table

5. **Save Strategy**
   - ✅ Click "Save Strategy"
   - ✅ Enter strategy name
   - ✅ Should show success message

**Expected Result:**
- Visual strategy builder works
- Can create custom grid configurations
- Templates load correctly
- Comparison tool functional
- Save creates new strategy

---

#### NEW Feature #3: Config Visual Editor ⚙️

**Location:** Click "Config Editor" in navigation (SlidersHorizontal icon)

**What to test:**
1. **Dual-Mode Interface**
   - ✅ See two tabs: "Form View" and "Code View"
   - ✅ Click "Form View" - shows organized sections
   - ✅ Click "Code View" - shows YAML editor

2. **Form View Sections**
   - ✅ Expand "Trading" accordion
     * See: symbol, base_order_size, safety_order_size
   - ✅ Expand "Grid" accordion
     * See: levels, spacing_percent
   - ✅ Expand "Safety" accordion
     * See: stop_loss_percent, max_drawdown_percent
   - ✅ Expand "Indicators" accordion
     * See: RSI settings

3. **Form Validation**
   - ✅ Change "base_order_size" to empty
   - ✅ Should show red error
   - ✅ See error count chip at top
   - ✅ Fill in value - error disappears

4. **Code View**
   - ✅ Switch to "Code View" tab
   - ✅ See YAML code with syntax highlighting
   - ✅ Try editing YAML directly
   - ✅ Switch back to "Form View" - should reflect changes

5. **Save with Diff Preview**
   - ✅ Make a change (e.g., change symbol to "BTCUSD")
   - ✅ Click "Save Configuration"
   - ✅ Should show diff dialog with before/after
   - ✅ Click "Confirm Save"
   - ✅ Should show success message

6. **Backup System**
   - ✅ Click "View Backups"
   - ✅ See list of auto-backups
   - ✅ Click "Restore" on a backup
   - ✅ Config should revert

7. **Export/Import**
   - ✅ Click "Export" - downloads YAML file
   - ✅ Click "Import" - upload YAML file
   - ✅ Config should update

**Expected Result:**
- Dual-mode editing works smoothly
- Form validation catches errors
- YAML code editor has syntax highlighting
- Save shows diff preview
- Backup/restore functional
- Export/import works

---

### Step 4: Test NEW Phase 3 Features

#### NEW Feature #4: Instance Manager 🤖

**Location:** Click "Instance Manager" in navigation (Layers3 icon, emerald color)

**What to test:**
1. **Empty State**
   - ✅ Should show "No bot instances found"
   - ✅ See "New Instance" button

2. **Summary Cards**
   - ✅ See 4 summary cards at top:
     * Total Instances: 0
     * Online / Stopped: 0 / 0
     * Total CPU: 0.0%
     * Total Memory: 0MB

3. **Create Instance Dialog**
   - ✅ Click "+ New Instance" button
   - ✅ Dialog opens with form
   - ✅ Enter instance name: "Demo Test"
   - ✅ Select Mode: "Demo"
   - ✅ Select Strategy Template: "Aggressive"
   - ✅ Click "Create & Start"

4. **Instance Card (if instance created)**
   - ✅ Should show instance card
   - ✅ See status chip: RUNNING or STOPPED
   - ✅ See mode chip: DEMO or LIVE
   - ✅ See metrics: PID, Uptime, CPU, Memory
   - ✅ See grid config: Price range, step, lot
   - ✅ See P&L and positions count

5. **Instance Controls**
   - ✅ Click "Start" button (if stopped)
   - ✅ Click "Stop" button (if running)
   - ✅ Click "Restart" button
   - ✅ Click "Logs" button - should show logs
   - ✅ Click "Configure" button - opens config dialog

6. **Refresh**
   - ✅ Click "Refresh" button at top
   - ✅ Data should reload

**Expected Result:**
- Can create new bot instances
- Instance cards display correctly
- Start/stop/restart controls work
- Metrics update in real-time
- Logs viewer opens
- **Fulfills Requirement 1:** Run demo + live simultaneously

**Note:** Instance creation will work if PM2 is configured. If you see errors, it's expected - backend needs PM2 integration testing.

---

#### NEW Feature #5: Mode Switcher 🔄

**Location:** Click "Mode Switcher" in navigation (RefreshCw icon, cyan color)

**What to test:**

**⚠️ Expected Behavior:** This feature requires backend service initialization. You'll likely see placeholder data or errors.

1. **Status Banner**
   - ⚠️ Might show: "Service not initialized" or similar
   - Should see: Enable/Disable toggle

2. **Price Visualization**
   - Should see: Price range chart
   - Should show: Reference price line
   - Should show: LONG/SHORT zones

3. **Configuration Dialog**
   - ✅ Click "Configure" button
   - ✅ Dialog opens with settings
   - ✅ See: Reference price input
   - ✅ See: Hysteresis setting
   - ✅ See: Switch delay setting

4. **Manual Override**
   - ✅ Click "Manual Override" button
   - ✅ Dialog opens
   - ✅ Select mode: LONG or SHORT
   - ✅ Set duration
   - ✅ Enter reason
   - ⚠️ Submit might fail (service not running)

5. **Switch History Table**
   - Should show: Table of past switches
   - Columns: Time, Price, From → To, Reason
   - ⚠️ Might be empty if service not initialized

**Expected Result:**
- UI renders correctly
- Configuration dialogs work
- Manual override form functional
- **Will fully work after:** Backend service initialization
- **Fulfills Requirement 2:** Auto LONG/SHORT switching (when service running)

---

#### NEW Feature #6: System Health Monitor 💊

**Location:** Click "System Health" in navigation (Activity icon, green color)

**What to test:**

**⚠️ Expected Behavior:** This feature requires backend service initialization. You'll likely see "No metrics available yet."

1. **Overall Health Banner**
   - ⚠️ Might show: "No metrics available yet"
   - Should show: Health status badge (green/yellow/red)

2. **System Metrics Cards**
   - Should see: 3 cards for CPU, Memory, Disk
   - Each card should show:
     * Current usage percentage
     * Progress bar with color coding
     * Trend indicator (up/down/stable)
   - ⚠️ Might show 0% if service not running

3. **Active Alerts Table**
   - Should show: Table of active alerts
   - Columns: Time, Severity, Component, Message
   - Actions: Acknowledge button
   - ⚠️ Likely empty if service not initialized

4. **Process Health Table**
   - Should show: List of monitored processes
   - Columns: Process, Status, CPU, Memory, Restarts
   - Status indicators: Running (green), Stopped (gray)
   - ⚠️ Might be empty

5. **API Health Status**
   - Should show: Table of API endpoints
   - Columns: Endpoint, Status, Latency
   - Status: Online (green) or Offline (red)
   - ⚠️ Might show all offline

6. **Refresh**
   - ✅ Click "Refresh" button
   - Should reload all data

7. **Alert History**
   - ✅ Click "View Alert History"
   - ✅ Dialog opens
   - ✅ Shows past alerts
   - ⚠️ Might be empty

**Expected Result:**
- UI renders correctly
- Metric cards display
- Tables and dialogs functional
- **Will fully work after:** Backend service initialization
- Auto-healing would trigger when service running

---

## 📊 TESTING SUMMARY CHECKLIST

### Pre-Existing Features (Quick Check)
- [ ] Dashboard loads and shows data
- [ ] Configuration panel accessible
- [ ] Positions table displays
- [ ] Bot Management controls visible
- [ ] Logs panel streaming

### Phase 2: Configuration Freedom
- [ ] File Editor opens and can browse files
- [ ] Monaco editor has syntax highlighting
- [ ] Strategy Editor shows 3 templates
- [ ] Can adjust grid settings visually
- [ ] Config Editor dual-mode works
- [ ] Form validation catches errors
- [ ] YAML code view functional
- [ ] Backup/restore works

### Phase 3: Intelligent Automation
- [ ] Instance Manager renders
- [ ] Can open "Create Instance" dialog
- [ ] Instance cards display (if instances exist)
- [ ] Mode Switcher UI renders
- [ ] Configuration dialogs open
- [ ] System Health panel shows metric cards
- [ ] All tables render correctly
- [ ] No infinite re-render warnings in console

---

## 🐛 KNOWN ISSUES

### Fixed ✅
- ✅ React "Maximum update depth exceeded" warnings - FIXED
- ✅ Phase 3 blueprint registration - FIXED
- ✅ Instance Manager API 404 errors - FIXED

### Still Pending ⏳
- ⏳ Mode Switcher service not initialized - Shows placeholder/errors
- ⏳ System Health service not initialized - Shows "No metrics"
- ⏳ Market Monitor service not initialized - Needed for Mode Switcher

### Expected Behavior ℹ️
- Instance Manager API works but returns empty list (no instances created yet)
- Mode Switcher UI works but backend service needs startup initialization
- System Health UI works but backend service needs startup initialization

---

## 📈 SUCCESS CRITERIA

### Phase 2 Features: ✅ COMPLETE
- [x] Can edit code files in browser (File Editor)
- [x] Can create strategies visually (Strategy Editor)
- [x] Can edit config with forms (Config Editor)
- [x] **Requirement 3 Met:** Control demo levels independently

### Phase 3 Features: 🔄 PARTIAL
- [x] UI for multi-instance management complete
- [x] UI for mode switching complete
- [x] UI for system health complete
- [ ] Backend services need initialization
- [ ] **Requirement 1:** Run demo + live (needs testing with PM2)
- [ ] **Requirement 2:** Auto LONG/SHORT (needs service init)

---

## 🎯 NEXT STEPS

### Option A: Test What Works Now
1. Refresh browser at http://localhost:5557
2. Test all 20 navigation sections
3. Focus on Phase 2 features (File/Strategy/Config Editors)
4. Report any bugs in working features

### Option B: Initialize Backend Services (2-3 hours)
1. Add service startup code to `app.py`
2. Start Market Monitor, Mode Switcher, System Health services
3. Test Phase 3 features with live data
4. Verify auto-switching and monitoring work

### Option C: Both
1. Test Phase 2 features now (fully functional)
2. I'll initialize Phase 3 services
3. Re-test Phase 3 features with live data

**Which option would you like?**

---

## 📞 READY TO TEST!

**Your browser is open at:** http://localhost:5557  
**Backend is running at:** http://localhost:5555  
**Console errors:** Fixed (re-render loops removed)  

**Refresh the page and start testing!** 🚀

Let me know:
1. Which sections you want to test first
2. Any issues you encounter
3. Whether to initialize Phase 3 backend services
