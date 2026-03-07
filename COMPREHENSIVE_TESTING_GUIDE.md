# 🧪 Comprehensive Testing Guide - GridBot WebUI

**Date:** November 16, 2025  
**Branch:** `feature/phase2-config-freedom`  
**Frontend URL:** http://localhost:5557  
**Backend URL:** http://localhost:5555  

---

## 📋 TESTING OVERVIEW

**Total Sections:** 22 navigation items  
**Pre-Existing:** 14 sections (already working)  
**Newly Added:** 8 sections (Phase 2 + Phase 3)  

**Testing Time Estimate:** 2-3 hours for complete testing  
**Quick Test:** 30 minutes for core features  

---

## 🚀 GETTING STARTED

### Step 1: Refresh Browser
1. Open http://localhost:5557 in your browser
2. **Hard refresh** to clear cache:
   - **Mac:** `Cmd + Shift + R`
   - **Windows/Linux:** `Ctrl + Shift + R`
3. Open **DevTools Console**: `Cmd + Option + J` (Mac) or `F12` (Windows)
4. **Expected:** No "Maximum update depth exceeded" errors (fixed)

### Step 2: Verify Backend Connection
1. Check DevTools Console for API calls
2. Should see successful API GET requests to `/api/positions`, `/api/orders`, etc.
3. Top-right corner should show "Connected" or "Synced" status
4. **If backend down:** Backend on port 5555 may need restart

### Step 3: Navigation Overview
Look at the left sidebar (or hamburger menu on mobile):
- **14 Pre-existing sections** (white/gray icons)
- **8 New sections** (colored icons):
  - PM2 Panel (green)
  - Logs Panel (purple)
  - File Editor (purple)
  - Strategy Editor (blue)
  - Config Editor (blue)
  - Mode Switcher (cyan)
  - System Health (green)
  - Instance Manager (emerald)

---

## ✅ TESTING CHECKLIST

Use this as your testing worksheet. Mark each item as you test:

- [ ] **Dashboard** - Pre-existing ✓
- [ ] **Configuration** - Pre-existing ✓
- [ ] **Risk & Safety** - Pre-existing ✓
- [ ] **Positions** - Pre-existing ✓
- [ ] **Bot Management** - Pre-existing ✓
- [ ] **Monitoring** - Pre-existing ✓
- [ ] **Guardian** - Pre-existing ✓
- [ ] **Bot Strategy** - Pre-existing ✓
- [ ] **Bot Actions** - Pre-existing ✓
- [ ] **Brain Flow Graph** - Pre-existing ✓
- [ ] **Intelligence** - Pre-existing ✓
- [ ] **PM2 Panel** - Promoted to nav ✓
- [ ] **Logs Panel** - Promoted to nav ✓
- [ ] **Todo List** - Pre-existing ✓
- [ ] **File Editor** - NEW Phase 2 ⭐
- [ ] **Strategy Editor** - NEW Phase 2 ⭐
- [ ] **Config Editor** - NEW Phase 2 ⭐
- [ ] **Mode Switcher** - NEW Phase 3 ⭐
- [ ] **System Health** - NEW Phase 3 ⭐
- [ ] **Instance Manager** - NEW Phase 3 ⭐

---

## 📝 SECTION 1: PRE-EXISTING FEATURES (Quick Sanity Check)

**Goal:** Verify nothing broke with new additions  
**Time:** 5-10 minutes  

### 1.1 Dashboard
**Click:** "Dashboard" in navigation

**Test:**
- [ ] Page loads without errors
- [ ] Shows P&L summary (even if $0)
- [ ] Shows positions count
- [ ] Shows current BTC price
- [ ] Charts/graphs visible (may be empty if bot not running)

**Pass Criteria:** Loads successfully, no console errors

**Issues Found:** _______________________________________________

---

### 1.2 Configuration
**Click:** "Configuration" in navigation

**Test:**
- [ ] Configuration panel loads
- [ ] Shows bot settings (symbol, order sizes, etc.)
- [ ] Can expand/collapse sections
- [ ] Text fields are editable
- [ ] "Save" button visible

**Pass Criteria:** Configuration loads, fields visible

**Issues Found:** _______________________________________________

---

### 1.3 Positions
**Click:** "Positions" in navigation

**Test:**
- [ ] Positions panel loads
- [ ] Shows "No positions" or position table
- [ ] Grid visualization visible (if positions exist)
- [ ] Table columns: Price, Size, PnL, Side

**Pass Criteria:** Panel renders correctly

**Issues Found:** _______________________________________________

---

### 1.4 Bot Management
**Click:** "Bot Management" in navigation

**Test:**
- [ ] Shows bot status (Running/Stopped)
- [ ] Start/Stop buttons visible
- [ ] Emergency controls present
- [ ] PM2 section still accessible here (nested)
- [ ] Logs section still accessible here (nested)

**Pass Criteria:** Management controls visible

**Issues Found:** _______________________________________________

---

### 1.5 Guardian
**Click:** "Guardian" in navigation (if visible)

**Test:**
- [ ] Guardian dashboard loads
- [ ] Shows circuit breaker status
- [ ] Risk metrics displayed
- [ ] Health indicators visible

**Pass Criteria:** Guardian dashboard renders

**Issues Found:** _______________________________________________

---

## ⭐ SECTION 2: PM2 PANEL (Promoted to Standalone Nav)

**Click:** "PM2 Panel" in navigation  
**Time:** 5 minutes  

### What You Should See:
- **Title:** "PM2 Process Manager"
- **Subtitle:** "Production-ready process management..."
- **Content:** Table of processes or PM2 status

### Detailed Tests:

#### Test 2.1: Panel Loads
- [ ] PM2 Panel opens when clicked
- [ ] No loading spinner stuck forever
- [ ] Card header says "PM2 Process Manager"
- [ ] Card has green accent color (emerald)

**Pass Criteria:** Panel loads within 2 seconds

**Issues Found:** _______________________________________________

---

#### Test 2.2: Process Table
**Expected:** Table showing PM2 processes

**Check for:**
- [ ] Table with columns: Name, Status, CPU, Memory, Restarts
- [ ] Processes listed (e.g., gridbot-live, guardian, etc.)
- [ ] Status badges (online/stopped)
- [ ] Resource usage percentages

**If No Processes Shown:**
- Check if PM2 is running: Open terminal → `pm2 list`
- May show "No processes found" if PM2 not configured

**Pass Criteria:** Table renders (even if empty)

**Issues Found:** _______________________________________________

---

#### Test 2.3: Action Buttons
**If processes exist:**

**Test each button:**
- [ ] "Start" button (if process stopped)
- [ ] "Stop" button (if process running)
- [ ] "Restart" button
- [ ] "Logs" button
- [ ] "Details" button

**Try:**
1. Click "Logs" on any process
2. Should open logs dialog or navigate to logs

**Pass Criteria:** Buttons are clickable, show appropriate actions

**Issues Found:** _______________________________________________

---

#### Test 2.4: Refresh Functionality
- [ ] "Refresh" button at top of card
- [ ] Click it
- [ ] Table should reload
- [ ] Loading indicator briefly shows

**Pass Criteria:** Refresh updates data

**Issues Found:** _______________________________________________

---

## ⭐ SECTION 3: LOGS PANEL (Promoted to Standalone Nav)

**Click:** "Logs Panel" in navigation  
**Time:** 5 minutes  

### What You Should See:
- **Title:** "Live Logs Stream"
- **Subtitle:** "Real-time bot logs with filtering..."
- **Content:** Log messages or "Bot not running" message

### Detailed Tests:

#### Test 3.1: Panel Loads
- [ ] Logs Panel opens when clicked
- [ ] Card header says "Live Logs Stream"
- [ ] Card has purple/violet accent color

**Pass Criteria:** Panel loads without errors

**Issues Found:** _______________________________________________

---

#### Test 3.2: Logs Display (If Bot Running)

**Expected:** Scrolling log messages

**Check for:**
- [ ] Log entries with timestamps
- [ ] Different log levels (INFO, WARN, ERROR)
- [ ] Color coding (green=info, yellow=warn, red=error)
- [ ] Auto-scroll to latest logs
- [ ] Scrollbar if many logs

**Try:**
- [ ] Scroll up to see older logs
- [ ] Scroll down - should auto-continue scrolling
- [ ] New logs appear in real-time

**Pass Criteria:** Logs stream in real-time

**Issues Found:** _______________________________________________

---

#### Test 3.3: Logs Inactive State (If Bot Stopped)

**Expected:** Message "Logs unavailable"

**Should see:**
- [ ] Pause icon with message
- [ ] Text: "Start the bot to stream live logs..."
- [ ] Dashed border box (inactive state)

**Pass Criteria:** Shows appropriate inactive message

**Issues Found:** _______________________________________________

---

#### Test 3.4: Log Filtering (If Available)

**Check for filter controls:**
- [ ] Level dropdown (All, INFO, WARN, ERROR)
- [ ] Search box
- [ ] Time range selector
- [ ] Export button

**Try:**
- [ ] Filter by ERROR only
- [ ] Search for specific text
- [ ] Export logs (download)

**Pass Criteria:** Filters work as expected

**Issues Found:** _______________________________________________

---

## ⭐ SECTION 4: FILE EDITOR (Phase 2 - NEW)

**Click:** "File Editor" in navigation  
**Time:** 10-15 minutes  
**Priority:** HIGH (Core Phase 2 feature)

### What You Should See:
- **Title:** "File Editor with AI"
- **Left:** File browser tree
- **Right:** Code editor (Monaco)
- **Theme:** Dark (VS Code style)

### Detailed Tests:

#### Test 4.1: Panel Loads
- [ ] File Editor opens
- [ ] Split view: File browser (left) + Editor (right)
- [ ] Purple accent color on card
- [ ] No JavaScript errors in console

**Pass Criteria:** Panel loads with split layout

**Issues Found:** _______________________________________________

---

#### Test 4.2: File Browser Tree

**Left sidebar should show:**
- [ ] File tree structure
- [ ] Folders with 📁 icon
- [ ] Files with 📄 icon
- [ ] Expandable folders (click to expand)

**Try:**
- [ ] Expand `bot/` folder
- [ ] See subfolders: `utils/`, `trading/`, `safety/`
- [ ] Expand `config/` folder
- [ ] See `config.yaml` file

**Pass Criteria:** Can browse folder structure

**Issues Found:** _______________________________________________

---

#### Test 4.3: Open a File

**Steps:**
1. Click on `config/config.yaml` in file tree
2. File should open in right panel

**Expected:**
- [ ] File content appears in editor
- [ ] Syntax highlighting for YAML (colors)
- [ ] Line numbers on left side
- [ ] File name in tab at top

**Pass Criteria:** File opens with syntax highlighting

**Issues Found:** _______________________________________________

---

#### Test 4.4: Code Editor Features

**Test Monaco editor capabilities:**

**Typing:**
- [ ] Click in editor
- [ ] Type some text
- [ ] Text appears
- [ ] Cursor visible and moves

**Syntax Highlighting:**
- [ ] YAML keys in different color
- [ ] Values in different color
- [ ] Comments (if any) in gray/green

**Line Numbers:**
- [ ] Line numbers visible (1, 2, 3...)
- [ ] Click on line number to select line

**Auto-complete:**
- [ ] Start typing (e.g., "sym")
- [ ] Suggestions popup may appear (Monaco feature)

**Pass Criteria:** Can edit text, syntax highlighting works

**Issues Found:** _______________________________________________

---

#### Test 4.5: Save File

**Steps:**
1. Make a small change (add a comment: `# test`)
2. Look for "Save" button (top right or in toolbar)
3. Click "Save"

**Expected:**
- [ ] Success message appears
- [ ] File saved to disk

**Pass Criteria:** Changes can be saved

**Issues Found:** _______________________________________________

---

#### Test 4.6: Code Explainer (🎓 NEW Feature!)

**Note:** This is a NEW feature for explaining Python code in plain English!

**Steps:**
1. Browse to a Python file (e.g., `bot/strategy/async_gridbot.py`)
2. Click the file to open it
3. Look for **"Explain Code"** button in toolbar (top right)
4. Look for **Reading Level** dropdown next to button

**Expected:**
- [ ] "Explain Code" button appears (only for .py files)
- [ ] Reading level selector shows: 🎓 Simple / 📊 Trader / ⚙️ Tech
- [ ] Default mode is "Trader"

**Test 4.6a: Simple Mode (For Non-Coders)**

**Steps:**
1. Select "🎓 Simple" from dropdown
2. Click "Explain Code" button
3. Wait for analysis (1-5 seconds)

**Expected:**
- [ ] Loading indicator appears
- [ ] Dialog opens with explanation
- [ ] **Summary** in plain English (no technical jargon)
- [ ] **Statistics** section showing:
  - Total lines
  - Number of functions
  - Number of classes
  - Complexity score (with color: green/yellow/red)
- [ ] **Functions** accordion (expandable list)
- [ ] **Classes** accordion (if any)
- [ ] **Issues** section (or "No issues" message)

**Example Simple Explanation:**
> "This code creates a smart trading system that places buy and sell orders at different price levels..."

**Pass Criteria:** Explanation in everyday English, no technical terms

**Issues Found:** _______________________________________________

---

**Test 4.6b: Trader Mode (For Business Users)**

**Steps:**
1. Close previous dialog
2. Select "📊 Trader" from dropdown
3. Click "Explain Code" again

**Expected:**
- [ ] Different explanation focused on trading context
- [ ] Uses trading terminology (grid, orders, positions, PnL)
- [ ] Explains strategy logic clearly
- [ ] Shows risk implications

**Example Trader Explanation:**
> "Grid Bot Strategy: Places limit orders at price levels (grids) above and below current price. Profits from volatility..."

**Pass Criteria:** Trading-focused explanation

**Issues Found:** _______________________________________________

---

**Test 4.6c: Technical Mode (For Developers)**

**Steps:**
1. Close dialog
2. Select "⚙️ Technical" from dropdown
3. Click "Explain Code"

**Expected:**
- [ ] Detailed technical analysis
- [ ] Code patterns and architecture mentioned
- [ ] Performance considerations
- [ ] Technical terms used (async, context manager, etc.)

**Example Technical Explanation:**
> "Implements async grid trading strategy using trader pattern. Key components: GridCalculator, OrderManager..."

**Pass Criteria:** Technical, detailed analysis

**Issues Found:** _______________________________________________

---

**Test 4.6d: Explanation Panel Features**

**In the explanation dialog, test:**

**Statistics Dashboard:**
- [ ] Shows total lines count
- [ ] Shows functions count
- [ ] Shows classes count
- [ ] Shows complexity score
- [ ] Complexity color-coded:
  - Green = Simple (<10)
  - Yellow = Moderate (10-20)
  - Red = Complex (>20)

**Functions Accordion:**
- [ ] Click to expand
- [ ] Shows function names
- [ ] Shows parameters
- [ ] Shows complexity per function
- [ ] Shows line numbers
- [ ] Shows "async" badge for async functions

**Classes Accordion (if any):**
- [ ] Click to expand
- [ ] Shows class names
- [ ] Shows method count
- [ ] Shows inheritance (if any)

**Issues Section:**
- [ ] If issues detected, shows warning icon
- [ ] Lists issue type and line number
- [ ] If no issues, shows green success message

**Action Buttons:**
- [ ] **Copy** button - Click to copy explanation to clipboard
- [ ] **Download MD** button - Click to save as markdown file
- [ ] **Close** button - Closes dialog

**Pass Criteria:** All sections expandable, actions work

**Issues Found:** _______________________________________________

---

**Test 4.6e: Copy Explanation**

**Steps:**
1. With explanation open, click "Copy" button
2. Open a text editor (Notes, TextEdit, etc.)
3. Paste (Cmd+V)

**Expected:**
- [ ] Button changes to "Copied!" briefly
- [ ] Full explanation text pastes successfully
- [ ] Includes summary, statistics, all details

**Pass Criteria:** Copy to clipboard works

**Issues Found:** _______________________________________________

---

**Test 4.6f: Download Markdown**

**Steps:**
1. Click "Download MD" button in dialog

**Expected:**
- [ ] File downloads automatically
- [ ] Filename like `code_explanation_<timestamp>.md`
- [ ] Open the file in a text editor

**File Should Contain:**
- [ ] Markdown headers (`# Code Explanation`)
- [ ] Summary section
- [ ] Statistics table
- [ ] Functions list with details
- [ ] Classes list
- [ ] Issues list (if any)

**Pass Criteria:** Markdown file downloads and is readable

**Issues Found:** _______________________________________________

---

**Test 4.6g: Non-Python File Behavior**

**Steps:**
1. Close explanation dialog
2. Browse to a non-Python file (e.g., `config/config.yaml`)
3. Click to open it

**Expected:**
- [ ] "Explain Code" button does NOT appear
- [ ] Only shows for `.py` files
- [ ] Editor still works normally for viewing

**Pass Criteria:** Button only shows for Python files

**Issues Found:** _______________________________________________

---

**Test 4.6h: Error Handling**

**Test invalid file:**
1. If possible, try explaining a file that doesn't exist
2. Or try a Python file with syntax errors

**Expected:**
- [ ] Error message appears in dialog
- [ ] Message is clear and helpful
- [ ] Doesn't crash the UI
- [ ] Can close dialog and try again

**Pass Criteria:** Graceful error handling

**Issues Found:** _______________________________________________

---

#### Test 4.7: File Search (Original Feature)

**Back to file browser:**

**Expected:**
- [ ] Success message appears
- [ ] Snackbar/toast: "File saved successfully"
- [ ] No errors in console

**Alternative:** May show "Read-only" warning if editing production files

**Pass Criteria:** Save function works or shows appropriate warning

**Issues Found:** _______________________________________________

---

#### Test 4.6: File Operations

**Look for buttons/menu:**
- [ ] "Download" button
- [ ] "New File" button
- [ ] "Delete" button (may be hidden for safety)

**Try Download:**
1. Click "Download" button
2. File should download to your computer
3. Check Downloads folder

**Pass Criteria:** Download works

**Issues Found:** _______________________________________________

---

#### Test 4.7: Switch Between Files

**Steps:**
1. Open `config/config.yaml`
2. Then click on a Python file (e.g., `bot/trading/gridbot.py`)

**Expected:**
- [ ] Editor switches to new file
- [ ] Syntax highlighting changes (Python colors)
- [ ] Can open multiple files
- [ ] Tabs appear at top (if supported)

**Pass Criteria:** Can switch between different file types

**Issues Found:** _______________________________________________

---

#### Test 4.8: Help/Documentation

**Look for:**
- [ ] Help icon (?) or info icon
- [ ] Keyboard shortcuts list
- [ ] Usage instructions

**Check documentation:**
- [ ] Instructions visible
- [ ] Explains how to use file browser
- [ ] Mentions auto-backup feature

**Pass Criteria:** Help/docs accessible and helpful

**Issues Found:** _______________________________________________

---

## ⭐ SECTION 5: STRATEGY EDITOR (Phase 2 - NEW)

**Click:** "Strategy Editor" in navigation  
**Time:** 15-20 minutes  
**Priority:** HIGH (Core Phase 2 feature, Requirement #3)

### What You Should See:
- **Title:** "Strategy Editor"
- **Content:** Strategy templates or form builder
- **Theme:** Blue accent

### Detailed Tests:

#### Test 5.1: Panel Loads
- [ ] Strategy Editor opens
- [ ] Card has blue accent color
- [ ] Shows strategy templates or builder
- [ ] No errors in console

**Pass Criteria:** Panel loads successfully

**Issues Found:** _______________________________________________

---

#### Test 5.2: Template Selection

**Expected:** 3 strategy template cards

**Check for:**
- [ ] **Conservative** template card
- [ ] **Aggressive** template card
- [ ] **Balanced** template card

**Each card should show:**
- [ ] Template name
- [ ] Brief description
- [ ] Grid parameters preview (range, step, lot)
- [ ] "Use Template" or "Select" button

**Pass Criteria:** 3 templates visible with details

**Issues Found:** _______________________________________________

---

#### Test 5.3: Template Details

**Click on Conservative template:**

**Should display:**
- [ ] Grid Range: 90k - 110k (wide range)
- [ ] Step Size: ~1000 (large steps)
- [ ] Lot Size: 1 (small lot)
- [ ] Max Positions: ~5-10
- [ ] Risk Level: Low
- [ ] Description mentions "stability"

**Click on Aggressive template:**

**Should display:**
- [ ] Grid Range: 85k - 105k (narrower)
- [ ] Step Size: ~200 (small steps)
- [ ] Lot Size: 5 (larger lot)
- [ ] Max Positions: ~20
- [ ] Risk Level: High
- [ ] Description mentions "testing" or "high frequency"

**Pass Criteria:** Templates show different configurations

**Issues Found:** _______________________________________________

---

#### Test 5.4: Use Template

**Steps:**
1. Click "Use Template" on Conservative
2. Should open strategy form or editor

**Expected:**
- [ ] Form appears with pre-filled values
- [ ] Shows grid configuration fields
- [ ] Lower price: 90000
- [ ] Upper price: 110000
- [ ] Step: 1000
- [ ] Lot size: 1

**Pass Criteria:** Template loads into editor

**Issues Found:** _______________________________________________

---

#### Test 5.5: Grid Configuration Form

**Form should have these fields:**

**Basic Settings:**
- [ ] Strategy Name (text input)
- [ ] Description (textarea)
- [ ] Trading Mode (radio: Live/Demo)
- [ ] Grid Mode (radio: LONG/SHORT/BOTH)

**Grid Geometry:**
- [ ] Lower Price (number input or slider)
- [ ] Upper Price (number input or slider)
- [ ] Reference Price (display or input)
- [ ] Step Size (number input)

**Position Limits:**
- [ ] Lot Size (number input)
- [ ] Max Open Positions (number input)
- [ ] Max Open Orders (number input)

**Pass Criteria:** All fields visible and editable

**Issues Found:** _______________________________________________

---

#### Test 5.6: Adjust Grid Settings

**Interactive sliders test:**

**Steps:**
1. Find "Lower Price" slider or input
2. Change from 90000 to 92000
3. Observe visual feedback

**Expected:**
- [ ] Slider moves smoothly
- [ ] Number updates in real-time
- [ ] Grid visualization updates (if present)
- [ ] Level count recalculates

**Try changing:**
- [ ] Upper Price (change to 108000)
- [ ] Step Size (change to 500)
- [ ] Lot Size (change to 2)

**Expected:** Each change updates calculations

**Pass Criteria:** Fields are interactive and update in real-time

**Issues Found:** _______________________________________________

---

#### Test 5.7: Grid Visualization

**Look for visual grid preview:**

**Should show:**
- [ ] Visual representation of grid levels
- [ ] Price ladder (90k, 91k, 92k... 110k)
- [ ] Reference price marker
- [ ] Color coding (green=buy zone, red=sell zone)
- [ ] Number of levels calculated

**As you adjust sliders:**
- [ ] Visualization updates in real-time
- [ ] Shows how many grid levels result
- [ ] Highlights current reference price

**Pass Criteria:** Visual feedback shows grid structure

**Issues Found:** _______________________________________________

---

#### Test 5.8: Validation & Warnings

**Test invalid inputs:**

**Try:**
1. Set Lower Price > Upper Price
2. Set Step Size to 0 or negative
3. Set Lot Size to 0

**Expected:**
- [ ] Red error message appears
- [ ] Field highlighted in red
- [ ] Warning icon or text
- [ ] "Save" button disabled while invalid

**Try valid range again:**
- [ ] Error clears
- [ ] Fields turn normal
- [ ] "Save" button enabled

**Pass Criteria:** Validation catches errors

**Issues Found:** _______________________________________________

---

#### Test 5.9: Capital Calculations

**Look for calculated fields:**

**Should display:**
- [ ] **Initial Margin Required** (estimated)
- [ ] **Buffer Reserve** (recommended)
- [ ] **Total Capital Required**
- [ ] **Profit per Level** (based on step size)

**Example:**
- Grid: 90k-110k, step 1000, lot 1
- Margin: ~₹50,000
- Buffer: ~₹10,000
- Total: ~₹60,000

**As you change lot size:**
- [ ] Calculations update
- [ ] Larger lot = more capital needed

**Pass Criteria:** Shows capital requirements

**Issues Found:** _______________________________________________

---

#### Test 5.10: Strategy Comparison

**Look for "Compare Strategies" button**

**Steps:**
1. Click "Compare Strategies"
2. Dialog or side panel opens

**Expected:**
- [ ] Comparison table appears
- [ ] Shows 2-3 strategies side by side
- [ ] Columns: Conservative, Aggressive, Balanced
- [ ] Rows: Grid range, levels, step, lot, risk, capital

**Should highlight differences:**
- [ ] Different grid ranges in different colors
- [ ] Risk levels (Low, Med, High) with badges
- [ ] Capital requirements clearly different

**Pass Criteria:** Comparison tool works

**Issues Found:** _______________________________________________

---

#### Test 5.11: Save Strategy

**Steps:**
1. Configure a custom strategy
2. Enter name: "My Test Strategy"
3. Click "Save Strategy" button

**Expected:**
- [ ] Confirmation dialog appears
- [ ] Shows what will be saved
- [ ] "Confirm" and "Cancel" buttons

**Click Confirm:**
- [ ] Success message: "Strategy saved"
- [ ] Strategy appears in saved list (if displayed)
- [ ] No console errors

**Pass Criteria:** Can save custom strategy

**Issues Found:** _______________________________________________

---

#### Test 5.12: Load/Edit Existing Strategy

**If strategies list exists:**

**Steps:**
1. Find list of saved strategies
2. Click "Edit" on a strategy
3. Form should populate with strategy values

**Expected:**
- [ ] All fields fill with saved values
- [ ] Can modify and re-save
- [ ] Shows last modified date

**Pass Criteria:** Can edit existing strategies

**Issues Found:** _______________________________________________

---

## ⭐ SECTION 6: CONFIG EDITOR (Phase 2 - NEW)

**Click:** "Config Editor" in navigation  
**Time:** 15-20 minutes  
**Priority:** HIGH (Core Phase 2 feature)

### What You Should See:
- **Title:** "Config Editor" or "Configuration Editor"
- **Two tabs:** "Form View" and "Code View"
- **Theme:** Blue accent

### Detailed Tests:

#### Test 6.1: Panel Loads
- [ ] Config Editor opens
- [ ] Shows two tabs at top
- [ ] "Form View" tab active by default
- [ ] Blue accent color
- [ ] No errors in console

**Pass Criteria:** Panel loads with dual-mode interface

**Issues Found:** _______________________________________________

---

#### Test 6.2: Form View - Section Layout

**Should see organized accordion sections:**

**Check for sections:**
- [ ] **Trading** (collapsed or expanded)
- [ ] **Grid** 
- [ ] **Safety**
- [ ] **Indicators**
- [ ] **Notifications**

**Each section should:**
- [ ] Have expand/collapse arrow
- [ ] Click to expand/collapse
- [ ] Smooth animation

**Pass Criteria:** 5 organized sections visible

**Issues Found:** _______________________________________________

---

#### Test 6.3: Trading Section

**Expand "Trading" section:**

**Should show fields:**
- [ ] **Symbol** (text input, e.g., "BTCUSDT")
- [ ] **Base Order Size** (number)
- [ ] **Safety Order Size** (number)
- [ ] **Max Active Deals** (number)
- [ ] **Take Profit Percent** (number with %)
- [ ] **Trailing Stop** (boolean switch)
- [ ] **Martingale** (boolean switch or number)

**Each field should have:**
- [ ] Label clearly visible
- [ ] Input box or switch
- [ ] Current value displayed
- [ ] Editable

**Pass Criteria:** All trading fields present and editable

**Issues Found:** _______________________________________________

---

#### Test 6.4: Grid Section

**Expand "Grid" section:**

**Should show:**
- [ ] **Grid Levels** (number input)
- [ ] **Spacing Percent** (number with %)
- [ ] Maybe: Lower/Upper bounds
- [ ] Maybe: Step size

**Pass Criteria:** Grid configuration fields visible

**Issues Found:** _______________________________________________

---

#### Test 6.5: Safety Section

**Expand "Safety" section:**

**Should show:**
- [ ] **Stop Loss Percent** (number with %)
- [ ] **Max Drawdown Percent** (number with %)
- [ ] **Volatility Filter** (boolean or threshold)
- [ ] **Emergency Stop** (boolean switch)

**Pass Criteria:** Safety settings visible

**Issues Found:** _______________________________________________

---

#### Test 6.6: Indicators Section

**Expand "Indicators" section:**

**Should show RSI settings:**
- [ ] **RSI Enabled** (switch ON/OFF)
- [ ] **RSI Period** (number, e.g., 14)
- [ ] **RSI Buy Threshold** (number, e.g., 30)
- [ ] **RSI Sell Threshold** (number, e.g., 70)

**Pass Criteria:** Indicator configuration available

**Issues Found:** _______________________________________________

---

#### Test 6.7: Notifications Section

**Expand "Notifications" section:**

**Should show:**
- [ ] **Email** (text input or switch)
- [ ] **Telegram** (boolean or chat ID)
- [ ] **Webhook URL** (text input for webhook)

**Pass Criteria:** Notification settings editable

**Issues Found:** _______________________________________________

---

#### Test 6.8: Field Validation

**Test validation rules:**

**Try invalid values:**
1. Clear "Symbol" field (leave empty)
2. Set "Base Order Size" to 0 or negative
3. Set "Take Profit Percent" to invalid value (e.g., -5)

**Expected for each error:**
- [ ] Field turns red
- [ ] Error message appears below field
- [ ] Error icon (⚠️) visible
- [ ] Error count chip at top updates

**Example error message:**
- "Symbol is required"
- "Must be greater than 0"

**Pass Criteria:** Validation catches and displays errors

**Issues Found:** _______________________________________________

---

#### Test 6.9: Validation Status Chip

**At top of form, look for:**
- [ ] Status chip showing "Valid ✓" (green) or "Invalid ✗" (red)
- [ ] Error count (e.g., "3 errors")

**When form is valid:**
- [ ] Green chip: "Configuration Valid ✓"
- [ ] Error count: 0

**When errors exist:**
- [ ] Red chip: "Invalid Configuration ✗"
- [ ] Error count: "3 errors" (number of issues)

**Pass Criteria:** Status chip accurately reflects validation state

**Issues Found:** _______________________________________________

---

#### Test 6.10: Fix Errors

**Steps:**
1. Have some validation errors
2. Fix one field (fill in required value)
3. Observe error count decrease

**Expected:**
- [ ] Error count updates immediately
- [ ] Fixed field no longer red
- [ ] Error message disappears
- [ ] When all fixed, chip turns green

**Pass Criteria:** Validation updates in real-time

**Issues Found:** _______________________________________________

---

#### Test 6.11: Switch to Code View

**Click "Code View" tab:**

**Expected:**
- [ ] Tab switches to Code View
- [ ] Monaco YAML editor appears
- [ ] Shows complete config in YAML format
- [ ] Syntax highlighting (colors)
- [ ] Line numbers visible

**Example YAML:**
```yaml
trading:
  symbol: BTCUSDT
  base_order_size: 100
  safety_order_size: 200
grid:
  levels: 10
  spacing_percent: 1.5
```

**Pass Criteria:** YAML code view displays correctly

**Issues Found:** _______________________________________________

---

#### Test 6.12: Edit in Code View

**In YAML editor:**

**Try editing:**
1. Click in editor
2. Change `symbol: BTCUSDT` to `symbol: ETHUSDT`
3. Observe syntax highlighting

**Expected:**
- [ ] Can type freely
- [ ] YAML syntax highlighted
- [ ] Keys in one color, values in another
- [ ] Indentation visible
- [ ] Auto-complete may popup

**Pass Criteria:** Can edit YAML directly

**Issues Found:** _______________________________________________

---

#### Test 6.13: Switch Back to Form View

**Click "Form View" tab again:**

**Expected:**
- [ ] Switches back to form
- [ ] Changes from Code View reflected in form
- [ ] Symbol now shows "ETHUSDT" (your edit)
- [ ] All other fields intact

**Pass Criteria:** Changes sync between views

**Issues Found:** _______________________________________________

---

#### Test 6.14: Save Configuration

**Steps:**
1. Make a change (e.g., change symbol to "BTCUSD")
2. Click "Save Configuration" button

**Expected:**
- [ ] **Diff Preview Dialog** opens
- [ ] Shows "Before" and "After" comparison
- [ ] Highlights what changed
- [ ] Example: `symbol: BTCUSDT → BTCUSD`

**Dialog should have:**
- [ ] "Before" column (old value)
- [ ] "After" column (new value)
- [ ] Changed lines highlighted
- [ ] "Cancel" button
- [ ] "Confirm Save" button

**Pass Criteria:** Diff preview shows changes

**Issues Found:** _______________________________________________

---

#### Test 6.15: Confirm Save

**In diff dialog:**

**Click "Confirm Save":**

**Expected:**
- [ ] Dialog closes
- [ ] Success message: "Configuration saved successfully"
- [ ] Green snackbar/toast appears
- [ ] Auto-backup created (mentioned in message)

**Check console:**
- [ ] No errors
- [ ] May see POST request to `/api/config/update`

**Pass Criteria:** Save completes successfully

**Issues Found:** _______________________________________________

---

#### Test 6.16: Backup System

**Look for "View Backups" or "Backups" button:**

**Click it:**

**Expected:**
- [ ] Backup list dialog opens
- [ ] Shows list of backups with timestamps
- [ ] Each backup shows: Date, Time, Note

**Example:**
- Nov 16, 2025 08:23 PM - "Auto-backup before save"
- Nov 16, 2025 07:15 PM - "Manual backup"

**Pass Criteria:** Backup list displays

**Issues Found:** _______________________________________________

---

#### Test 6.17: Restore Backup

**In backup list:**

**Steps:**
1. Click "Restore" on a backup
2. Confirmation dialog should appear

**Expected:**
- [ ] Warning message: "This will replace current config"
- [ ] Shows backup timestamp
- [ ] "Cancel" and "Confirm Restore" buttons

**Click "Confirm Restore":**
- [ ] Config reverts to backup version
- [ ] Form updates with old values
- [ ] Success message appears

**Pass Criteria:** Restore functionality works

**Issues Found:** _______________________________________________

---

#### Test 6.18: Export Configuration

**Look for "Export" button:**

**Click "Export":**

**Expected:**
- [ ] File download starts
- [ ] File name: `config_backup_<timestamp>.yaml`
- [ ] Check Downloads folder
- [ ] Open file in text editor
- [ ] Contains valid YAML

**Pass Criteria:** Can export config as YAML file

**Issues Found:** _______________________________________________

---

#### Test 6.19: Import Configuration

**Look for "Import" button:**

**Steps:**
1. Click "Import"
2. File picker dialog opens
3. Select a YAML file (use previously exported one)
4. Click "Open"

**Expected:**
- [ ] File uploads
- [ ] Config updates with imported values
- [ ] Form reflects new values
- [ ] Success message appears

**Pass Criteria:** Can import YAML config

**Issues Found:** _______________________________________________

---

## ⭐ SECTION 7: MODE SWITCHER (Phase 3 - NEW)

**Click:** "Mode Switcher" in navigation  
**Time:** 10-15 minutes  
**Priority:** HIGH (Requirement #2 - Auto LONG/SHORT)

### What You Should See:
- **Title:** "Auto Mode Switcher"
- **Theme:** Cyan accent
- **Content:** Mode switcher controls

### ⚠️ Expected Behavior:
**Backend service not initialized** - May show placeholder data or errors. UI should still render.

### Detailed Tests:

#### Test 7.1: Panel Loads
- [ ] Mode Switcher opens
- [ ] Card has cyan/blue accent
- [ ] Shows status banner
- [ ] No critical console errors
- [ ] May show "Service not initialized" message

**Pass Criteria:** Panel renders (even with placeholder data)

**Issues Found:** _______________________________________________

---

#### Test 7.2: Status Banner

**At top, should show:**
- [ ] **Status:** Enabled/Disabled toggle or badge
- [ ] **Current Mode:** LONG, SHORT, or NONE
- [ ] **Current Price:** BTC price (may be placeholder)
- [ ] **Reference Price:** (e.g., ₹95,500)

**If service not initialized:**
- [ ] May show "Not available" or $0
- [ ] This is expected - service needs startup init

**Pass Criteria:** Status section displays

**Issues Found:** _______________________________________________

---

#### Test 7.3: Enable/Disable Toggle

**Look for toggle switch:**

**Should show:**
- [ ] Switch labeled "Enable Auto-Switching"
- [ ] ON or OFF state
- [ ] Click to toggle

**Try toggling:**
- [ ] Click switch
- [ ] May show error "Service not initialized"
- [ ] Or may toggle successfully (if backend running)

**Pass Criteria:** Toggle is clickable (may fail gracefully)

**Issues Found:** _______________________________________________

---

#### Test 7.4: Price Visualization

**Should show visual chart/diagram:**

**Expected elements:**
- [ ] Price range visualization (e.g., 80k to 110k)
- [ ] Reference price line (vertical marker)
- [ ] LONG zone (left side, green)
- [ ] SHORT zone (right side, red)
- [ ] Hysteresis zone (buffer area)
- [ ] Current price indicator

**Example:**
```
[LONG] ←—— Reference ——→ [SHORT]
80k         95.5k          110k
```

**Pass Criteria:** Visual price chart renders

**Issues Found:** _______________________________________________

---

#### Test 7.5: Configuration Dialog

**Look for "Configure" or ⚙️ Settings button:**

**Click it:**

**Expected:**
- [ ] Configuration dialog opens
- [ ] Modal/dialog with settings form

**Should have fields:**
- [ ] **Reference Price** (number input)
- [ ] **Hysteresis** (number input, buffer amount)
- [ ] **Switch Delay** (seconds)
- [ ] **LONG Strategy** (dropdown)
- [ ] **SHORT Strategy** (dropdown)

**Pass Criteria:** Config dialog opens with fields

**Issues Found:** _______________________________________________

---

#### Test 7.6: Edit Configuration

**In config dialog:**

**Try changing values:**
1. Reference Price: 95500 → 96000
2. Hysteresis: 200 → 300
3. Switch Delay: 30 → 60

**Expected:**
- [ ] Fields are editable
- [ ] Number inputs accept values
- [ ] Validation (no negative numbers)

**Click "Save" or "Apply":**
- [ ] Dialog closes
- [ ] May show error if service not running
- [ ] Or success if service active

**Pass Criteria:** Can edit config values

**Issues Found:** _______________________________________________

---

#### Test 7.7: Manual Override

**Look for "Manual Override" button:**

**Click it:**

**Expected:**
- [ ] Override dialog opens
- [ ] Form with mode selection

**Dialog should have:**
- [ ] **Mode Selection:** Radio buttons (LONG/SHORT/AUTO)
- [ ] **Duration:** Hours (e.g., 2 hours, indefinite)
- [ ] **Reason:** Text field (optional)
- [ ] "Cancel" and "Apply Override" buttons

**Pass Criteria:** Override dialog opens

**Issues Found:** _______________________________________________

---

#### Test 7.8: Apply Manual Override

**In override dialog:**

**Steps:**
1. Select "LONG" mode
2. Set duration: 2 hours
3. Enter reason: "Testing manual mode"
4. Click "Apply Override"

**Expected:**
- [ ] Dialog closes
- [ ] May show error (service not running) ⚠️ Expected
- [ ] Or success message if service active
- [ ] Current mode should update to LONG (if successful)

**Pass Criteria:** Can submit override (may fail gracefully)

**Issues Found:** _______________________________________________

---

#### Test 7.9: Switch History Table

**Should show table of past switches:**

**Table columns:**
- [ ] **Time** (timestamp)
- [ ] **Price** (at switch)
- [ ] **From → To** (mode change, e.g., "LONG → SHORT")
- [ ] **Reason** (why switched)

**Example row:**
- 08:15 AM | ₹95,720 | LONG → SHORT | Price crossed upper threshold

**If service not initialized:**
- [ ] Table may be empty
- [ ] Shows "No switch history" message

**Pass Criteria:** Table renders (even if empty)

**Issues Found:** _______________________________________________

---

#### Test 7.10: View Full History

**Look for "View Full History" or "History" button:**

**Click it:**

**Expected:**
- [ ] Dialog or expanded view opens
- [ ] Shows more rows (last 24h or 100 switches)
- [ ] Pagination or scroll
- [ ] Export button (optional)

**Pass Criteria:** History view accessible

**Issues Found:** _______________________________________________

---

#### Test 7.11: Refresh Button

**Look for refresh icon (🔄):**

**Click it:**

**Expected:**
- [ ] Data reloads
- [ ] Loading indicator briefly
- [ ] Table updates
- [ ] May fetch latest price and status

**Pass Criteria:** Refresh triggers data reload

**Issues Found:** _______________________________________________

---

## ⭐ SECTION 8: SYSTEM HEALTH (Phase 3 - NEW)

**Click:** "System Health" in navigation  
**Time:** 10-15 minutes  
**Priority:** MEDIUM

### What You Should See:
- **Title:** "System Health Dashboard" or "System Health Monitor"
- **Theme:** Green accent
- **Content:** Resource monitoring cards

### ⚠️ Expected Behavior:
**Backend service not initialized** - May show "No metrics available" or 0% usage. UI should still render.

### Detailed Tests:

#### Test 8.1: Panel Loads
- [ ] System Health panel opens
- [ ] Card has green accent color
- [ ] Shows health status banner
- [ ] Resource metric cards visible
- [ ] No critical console errors

**Pass Criteria:** Panel renders with metric layout

**Issues Found:** _______________________________________________

---

#### Test 8.2: Overall Health Banner

**At top, should show:**
- [ ] **Health Status Badge**
  - Green: HEALTHY
  - Yellow: WARNING
  - Red: CRITICAL
- [ ] Overall status text
- [ ] Last update timestamp

**If service not running:**
- [ ] May show "No metrics available yet"
- [ ] Gray/neutral badge
- [ ] This is expected

**Pass Criteria:** Status banner displays

**Issues Found:** _______________________________________________

---

#### Test 8.3: System Metrics Cards

**Should see 3-4 metric cards:**

**CPU Card:**
- [ ] Title: "CPU Usage"
- [ ] Percentage (e.g., 45.2%)
- [ ] Progress bar (colored)
- [ ] Color coding:
  - Green < 80%
  - Yellow 80-95%
  - Red > 95%
- [ ] Trend indicator (↑ up, ↓ down, — stable)

**Memory Card:**
- [ ] Title: "Memory Usage"
- [ ] Percentage or amount (e.g., 8.2 GB / 16 GB)
- [ ] Progress bar
- [ ] Color coding

**Disk Card:**
- [ ] Title: "Disk Usage"
- [ ] Percentage or amount
- [ ] Progress bar
- [ ] Color coding

**Network Card (optional):**
- [ ] Upload/Download speeds
- [ ] Bandwidth usage

**If service not initialized:**
- [ ] All show 0% or "N/A"
- [ ] Gray progress bars
- [ ] This is expected

**Pass Criteria:** Metric cards display with progress bars

**Issues Found:** _______________________________________________

---

#### Test 8.4: Process Health Table

**Should show table of monitored processes:**

**Table columns:**
- [ ] **Process Name** (e.g., gridbot-live, guardian)
- [ ] **Status** (Running/Stopped badge)
- [ ] **CPU** (percentage)
- [ ] **Memory** (MB)
- [ ] **Restarts** (count)
- [ ] **Uptime** or **Age**

**Status indicators:**
- [ ] Green dot = Running
- [ ] Gray dot = Stopped
- [ ] Red dot = Error

**If service not initialized:**
- [ ] Table may be empty
- [ ] Shows "No processes monitored"

**Pass Criteria:** Process table renders

**Issues Found:** _______________________________________________

---

#### Test 8.5: Active Alerts Table

**Should show table of current alerts:**

**Table columns:**
- [ ] **Time** (when triggered)
- [ ] **Severity** (Critical/Error/Warning/Info badge)
- [ ] **Component** (what triggered it)
- [ ] **Message** (alert description)
- [ ] **Actions** (Acknowledge button)

**Severity colors:**
- [ ] Critical: Red
- [ ] Error: Red
- [ ] Warning: Yellow
- [ ] Info: Blue

**Example alert:**
- Time: 08:23 PM
- Severity: WARNING
- Component: CPU
- Message: "CPU usage above 80%"
- Action: [Acknowledge]

**If no alerts:**
- [ ] Shows "No active alerts"
- [ ] Green checkmark or "All systems healthy"

**Pass Criteria:** Alerts table renders (may be empty)

**Issues Found:** _______________________________________________

---

#### Test 8.6: Acknowledge Alert

**If alerts exist:**

**Steps:**
1. Click "Acknowledge" button on an alert
2. Confirmation may appear

**Expected:**
- [ ] Alert moves to acknowledged state
- [ ] May disappear from active alerts
- [ ] Moves to alert history
- [ ] Success message

**Pass Criteria:** Can acknowledge alerts

**Issues Found:** _______________________________________________

---

#### Test 8.7: Alert History Dialog

**Look for "View Alert History" button:**

**Click it:**

**Expected:**
- [ ] Dialog opens
- [ ] Shows past alerts (last 24h or all)
- [ ] Same table structure as active alerts
- [ ] Includes acknowledged and auto-resolved alerts
- [ ] May have date filter or pagination

**Pass Criteria:** Alert history accessible

**Issues Found:** _______________________________________________

---

#### Test 8.8: API Health Status

**Should show API endpoint health:**

**Table or cards showing:**
- [ ] **Endpoint** (e.g., /api/positions, /api/orders)
- [ ] **Status** (Online/Offline badge)
- [ ] **Latency** (ms, e.g., 45ms)
- [ ] **Last Check** (timestamp)

**Status indicators:**
- [ ] Green: Online, < 100ms
- [ ] Yellow: Online, 100-500ms
- [ ] Red: Offline or > 500ms

**Pass Criteria:** API status section renders

**Issues Found:** _______________________________________________

---

#### Test 8.9: Metrics History Graph (If Present)

**Look for historical chart/graph:**

**Should show:**
- [ ] Line graph of CPU/Memory over time
- [ ] X-axis: Time (last hour)
- [ ] Y-axis: Percentage (0-100%)
- [ ] Multiple lines (CPU=blue, Memory=green)
- [ ] Hover to see exact values

**Pass Criteria:** History graph displays (may be empty)

**Issues Found:** _______________________________________________

---

#### Test 8.10: Refresh Functionality

**Look for "Refresh" button:**

**Click it:**

**Expected:**
- [ ] All metrics reload
- [ ] Loading indicators briefly show
- [ ] Data updates
- [ ] Timestamp updates to "Just now"

**Pass Criteria:** Manual refresh works

**Issues Found:** _______________________________________________

---

#### Test 8.11: Auto-Refresh

**System Health should auto-refresh every 30s:**

**Test:**
1. Note current timestamp
2. Wait 30 seconds
3. Check if timestamp updates

**Expected:**
- [ ] Data automatically refreshes
- [ ] No manual refresh needed
- [ ] Timestamp updates
- [ ] Smooth update (no flash/flicker)

**Pass Criteria:** Auto-refresh every 30s

**Issues Found:** _______________________________________________

---

## ⭐ SECTION 9: INSTANCE MANAGER (Phase 3 - NEW)

**Click:** "Instance Manager" in navigation  
**Time:** 15-20 minutes  
**Priority:** HIGH (Requirement #1 - Run demo + live)

### What You Should See:
- **Title:** "Bot Instance Manager" or "Multi-Instance Manager"
- **Theme:** Emerald green accent
- **Content:** Instance cards or empty state

### Detailed Tests:

#### Test 9.1: Panel Loads
- [ ] Instance Manager opens
- [ ] Card has emerald/green accent
- [ ] Shows header with "New Instance" button
- [ ] Summary cards at top
- [ ] No critical console errors

**Pass Criteria:** Panel renders successfully

**Issues Found:** _______________________________________________

---

#### Test 9.2: Empty State (If No Instances)

**If no instances created yet:**

**Should show:**
- [ ] Icon (pause or info icon)
- [ ] Message: "No bot instances found"
- [ ] Sub-message: "Click 'New Instance' to create one"
- [ ] Dashed border box (inactive state)
- [ ] "+ New Instance" button prominently displayed

**Pass Criteria:** Empty state is clear and helpful

**Issues Found:** _______________________________________________

---

#### Test 9.3: Summary Cards

**At top, should show 4 summary cards:**

**Card 1: Total Instances**
- [ ] Icon: 🤖 or grid icon
- [ ] Number: 0 (if empty) or count
- [ ] Label: "Total Instances"

**Card 2: Online / Stopped**
- [ ] Icon: Power icon
- [ ] Text: "0 / 0" or "2 / 1"
- [ ] Label: "Online / Stopped"
- [ ] Color: Green for online count

**Card 3: Total CPU**
- [ ] Icon: CPU icon
- [ ] Percentage: "0.0%" or actual
- [ ] Label: "Total CPU"

**Card 4: Total Memory**
- [ ] Icon: Memory icon
- [ ] Amount: "0MB" or actual
- [ ] Label: "Total Memory"

**Pass Criteria:** 4 summary cards visible

**Issues Found:** _______________________________________________

---

#### Test 9.4: Create Instance Dialog

**Click "+ New Instance" button:**

**Expected:**
- [ ] Dialog opens
- [ ] Title: "Create New Bot Instance"
- [ ] Form with fields

**Form should have:**
- [ ] **Instance Name** (text input)
- [ ] **Trading Mode** (radio: Demo / Live)
- [ ] **Strategy Template** (dropdown)
  - Options: Conservative, Aggressive, Balanced, Custom

**Dialog buttons:**
- [ ] "Cancel" button
- [ ] "Create & Start" button (primary)

**Pass Criteria:** Create dialog opens with form

**Issues Found:** _______________________________________________

---

#### Test 9.5: Fill Create Form

**In create dialog:**

**Fill fields:**
1. Name: "Test Demo Bot"
2. Mode: Select "Demo" (radio button)
3. Template: Select "Aggressive" from dropdown

**Expected:**
- [ ] Fields accept input
- [ ] Radio buttons toggle
- [ ] Dropdown shows options
- [ ] "Create & Start" button enabled

**Pass Criteria:** Form is fillable

**Issues Found:** _______________________________________________

---

#### Test 9.6: Create Instance

**Click "Create & Start":**

**Expected outcomes:**

**Option A: Success (if PM2 configured)**
- [ ] Dialog closes
- [ ] Success message: "Instance created successfully"
- [ ] New instance card appears
- [ ] Summary counts update

**Option B: Error (if PM2 not configured)** ⚠️ Most likely
- [ ] Error message appears
- [ ] May say: "PM2 not configured" or "Failed to create"
- [ ] This is expected for testing
- [ ] Dialog may stay open to retry

**For testing purposes:**
- [ ] Note the error message
- [ ] Error is expected (PM2 integration needs setup)
- [ ] Click "Cancel" to close dialog

**Pass Criteria:** API call is made (check Network tab), appropriate response

**Issues Found:** _______________________________________________

---

#### Test 9.7: Instance Card (If Instance Exists)

**If an instance was created or exists:**

**Instance card should show:**

**Header:**
- [ ] Emoji indicator (🔴 Live or 🟢 Demo)
- [ ] Instance name
- [ ] Status chip (RUNNING/STOPPED)
- [ ] Mode chip (LIVE/DEMO)
- [ ] Settings icon ⚙️

**Metrics Section (if running):**
- [ ] **PID** (process ID)
- [ ] **Uptime** (e.g., "2h 15m")
- [ ] **CPU** (percentage)
- [ ] **Memory** (MB)

**Grid Configuration:**
- [ ] Grid range (e.g., "85k-105k")
- [ ] Step size (e.g., "200")
- [ ] Lot size (e.g., "5")

**Trading Metrics:**
- [ ] **P&L** (profit/loss, e.g., "+₹1,234")
- [ ] **Positions** (count, e.g., "12")

**Action Buttons:**
- [ ] Start button (if stopped)
- [ ] Stop button (if running)
- [ ] Restart button
- [ ] Logs button
- [ ] Configure button

**Pass Criteria:** Instance card shows all information

**Issues Found:** _______________________________________________

---

#### Test 9.8: Instance Controls

**If instance card exists:**

**Test each button:**

**Stop Button:**
1. Click "Stop"
2. Expected: Confirmation dialog or immediate stop
3. Status changes to STOPPED
4. Metrics disappear or show "N/A"

**Start Button:**
1. Click "Start" (on stopped instance)
2. Expected: Instance starts
3. Status changes to RUNNING
4. Metrics appear

**Restart Button:**
1. Click "Restart"
2. Expected: Instance restarts
3. Brief status change
4. Uptime resets to "0m"

**Logs Button:**
1. Click "Logs"
2. Expected: Logs dialog opens
3. Shows instance-specific logs
4. Real-time streaming

**Configure Button:**
1. Click "Configure" or ⚙️
2. Expected: Config dialog opens
3. Shows instance settings
4. Can modify and save

**⚠️ Note:** Most buttons may show errors if PM2 not fully configured. This is expected for UI testing.

**Pass Criteria:** Buttons are clickable and trigger appropriate actions/dialogs

**Issues Found:** _______________________________________________

---

#### Test 9.9: Refresh Button

**Look for "Refresh" button at top:**

**Click it:**

**Expected:**
- [ ] All instance data reloads
- [ ] API call to /api/instances/list
- [ ] Cards update with latest metrics
- [ ] Loading indicator briefly shows

**Pass Criteria:** Refresh updates instance list

**Issues Found:** _______________________________________________

---

#### Test 9.10: Auto-Refresh

**Instance Manager should auto-refresh every 30s:**

**Test:**
1. Note metrics (CPU, memory, uptime)
2. Wait 30-60 seconds
3. Check if metrics update

**Expected:**
- [ ] Data automatically refreshes
- [ ] Uptime increments
- [ ] CPU/Memory may change
- [ ] No manual refresh needed

**Pass Criteria:** Auto-refresh works

**Issues Found:** _______________________________________________

---

#### Test 9.11: Multiple Instances (If Possible)

**If you can create multiple instances:**

**Test:**
1. Create "Live Conservative" instance
2. Create "Demo Aggressive" instance
3. Both cards should appear
4. Summary counts: Total = 2
5. Can control each independently

**Expected:**
- [ ] Both instances visible
- [ ] Can start/stop independently
- [ ] Different configurations shown
- [ ] Different P&L tracking

**Pass Criteria:** Multiple instances can coexist

**Issues Found:** _______________________________________________

---

## 📊 TESTING SUMMARY

### After completing all tests, fill out this summary:

#### Features Fully Working:
1. _________________________________
2. _________________________________
3. _________________________________
4. _________________________________
5. _________________________________

#### Features With Minor Issues:
1. _________________________________
2. _________________________________
3. _________________________________

#### Features Not Working:
1. _________________________________
2. _________________________________

#### Console Errors Observed:
1. _________________________________
2. _________________________________

#### Browser Compatibility:
- [ ] Chrome (version: _____)
- [ ] Firefox (version: _____)
- [ ] Safari (version: _____)
- [ ] Edge (version: _____)

#### Performance Notes:
- Page load time: _____ seconds
- Navigation speed: Fast / Medium / Slow
- API response time: _____ ms average
- Memory usage: _____ MB (check DevTools)

#### Mobile Testing (Optional):
- [ ] Tested on mobile device
- [ ] Device: _________________
- [ ] Screen size: _________________
- [ ] Touch interactions work
- [ ] Responsive layout correct

---

## 🐛 BUG REPORT TEMPLATE

**For each issue found, document:**

### Bug #1
**Feature:** _________________________________  
**Severity:** Critical / High / Medium / Low  
**Description:** _________________________________  
**Steps to Reproduce:**
1. _________________________________
2. _________________________________
3. _________________________________

**Expected Behavior:** _________________________________  
**Actual Behavior:** _________________________________  
**Console Errors:** _________________________________  
**Screenshot:** (attach if possible)  
**Browser:** _________________________________  

---

### Bug #2
**Feature:** _________________________________  
**Severity:** Critical / High / Medium / Low  
**Description:** _________________________________  
**Steps to Reproduce:**
1. _________________________________
2. _________________________________
3. _________________________________

**Expected Behavior:** _________________________________  
**Actual Behavior:** _________________________________  
**Console Errors:** _________________________________  
**Screenshot:** (attach if possible)  
**Browser:** _________________________________  

---

## ✨ IMPROVEMENT SUGGESTIONS

**List any improvements or enhancements you'd like:**

1. **Feature:** _________________________________  
   **Suggestion:** _________________________________  
   **Priority:** High / Medium / Low

2. **Feature:** _________________________________  
   **Suggestion:** _________________________________  
   **Priority:** High / Medium / Low

3. **Feature:** _________________________________  
   **Suggestion:** _________________________________  
   **Priority:** High / Medium / Low

---

## 🎯 THREE CORE REQUIREMENTS - VALIDATION

### Requirement #1: Run Demo + Live Simultaneously ✅

**Can you:**
- [ ] Create multiple bot instances from Instance Manager?
- [ ] Set one to "Live" mode and one to "Demo" mode?
- [ ] Use different strategies for each (Conservative vs Aggressive)?
- [ ] Control each instance independently (start/stop)?
- [ ] See separate P&L tracking for each?

**Status:** Working / Partial / Not Working  
**Notes:** _________________________________

---

### Requirement #2: Auto LONG/SHORT Switching ✅

**Can you:**
- [ ] Access Mode Switcher panel?
- [ ] Configure reference price and hysteresis?
- [ ] Enable auto-switching toggle?
- [ ] See price visualization with LONG/SHORT zones?
- [ ] Apply manual override?
- [ ] View switch history?

**Status:** UI Working (Backend pending) / Working / Not Working  
**Notes:** _________________________________

---

### Requirement #3: Control Demo Levels Independently ✅

**Can you:**
- [ ] Access Strategy Editor?
- [ ] Create custom grid configuration?
- [ ] Set different levels for demo vs live?
- [ ] Use templates (Conservative/Aggressive)?
- [ ] Save and load strategies?
- [ ] See grid visualization update in real-time?

**Status:** Working / Partial / Not Working  
**Notes:** _________________________________

---

## 📈 OVERALL ASSESSMENT

**Overall Experience:** Excellent / Good / Fair / Poor  

**Most Impressive Feature:**  
_________________________________

**Most Problematic Feature:**  
_________________________________

**Ease of Use (1-10):** _____  
**Visual Design (1-10):** _____  
**Performance (1-10):** _____  
**Feature Completeness (1-10):** _____  

**Would you use this in production?** Yes / No / With fixes  

**Additional Comments:**  
_________________________________________________  
_________________________________________________  
_________________________________________________  

---

## 🚀 READY TO TEST!

1. **Save this file** for reference
2. **Refresh browser** at http://localhost:5557
3. **Start testing** from Section 1
4. **Check off items** as you test
5. **Document bugs** using template above
6. **Share feedback** when complete

**Questions during testing?** Let me know and I'll help troubleshoot!

---

**Happy Testing! 🎉**
