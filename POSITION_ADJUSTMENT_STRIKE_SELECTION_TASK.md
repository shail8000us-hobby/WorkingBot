# Position Adjustment Strike Selection Task

**Created:** February 2, 2026  
**Task Type:** Feature Enhancement  
**Priority:** High  
**Estimated Time:** 1-2 hours

---

## ROLE
You are a cautious senior engineer working on a LIVE trading system WebUI.

## GLOBAL PRIORITY
Preserve existing trading logic, execution paths, state handling, and current WebUI behavior.
Stability is more important than elegance.

---

## CONTEXT

### Current System State
The Position Adjustment System (Sensibull-like UI) currently works as follows:
1. User navigates to Options → Open Positions panel
2. User clicks "Adjust Position" button
3. **SensibullStyleAdjustmentPage** opens with:
   - Current positions loaded from `positions` state
   - A fixed expiry selector (dropdown)
   - Payoff graph showing ALL positions for selected expiry
   - No pre-filtering based on user selection

### Problem
**User cannot pre-select which expiries and strikes to focus on before opening the adjustment page.**

The current flow forces users to:
- See payoff for all positions
- Manually filter in their mind which positions they want to adjust

**Expected behavior:**
1. User selects specific expiries via expiry filter dropdown in OptionsPanel
2. User checks specific strikes (positions) they want to adjust
3. User clicks "Adjust Position" button
4. Adjustment page opens showing payoff ONLY for selected expiries + selected strikes
5. If no strikes selected, show all positions for selected expiries
6. If no expiry selected, show all positions (current behavior - fallback)

---

## TECHNICAL ANALYSIS

### Files to Read (Understand First - DO NOT MODIFY YET)
1. **OptionsPanel.js** (`webui/frontend/src/components/options/OptionsPanel.js`)
   - Line ~230: `selectedExpiries` state (already exists for filtering table)
   - Line ~325 (in backup): `selectedStrikes` state (may exist in old backup, check current file)
   - Line ~6404: Where `SensibullStyleAdjustmentPage` is rendered
   - Props passed: `currentPositions={positions}` (all positions)

2. **SensibullStyleAdjustmentPage.js** (`webui/frontend/src/components/positionAdjustment/SensibullStyleAdjustmentPage.js`)
   - Props received: `currentPositions`, `spotPrice`, `underlying`
   - Current logic: Uses ALL positions from props

3. **PositionAdjustmentPanel.js** (`webui/frontend/src/components/positionAdjustment/PositionAdjustmentPanel.js`)
   - Line ~70: Uses `currentPositions` prop directly
   - Passes to `usePayoffCalculation` hook for graph

### Files to Modify (Surgical Changes Only)

#### 1. **OptionsPanel.js** (Line ~6404)
**Current code:**
```javascript
<SensibullStyleAdjustmentPage
  open={adjustmentPanelOpen}
  onClose={() => setAdjustmentPanelOpen(false)}
  currentPositions={positions}  // ← Passes ALL positions
  spotPrice={btcPrice || ethPrice}
  underlying={positions[0]?.product_symbol?.split('-')[1] || 'BTC'}
  onExecuteComplete={() => {
    setAdjustmentPanelOpen(false);
    handleRefresh();
  }}
/>
```

**Required change:**
- Filter `positions` before passing based on:
  1. `selectedExpiries` (if any selected)
  2. `selectedStrikes` (if any selected) - **check if this state exists, if not, create it**
- Add logic just before JSX render to compute `filteredPositionsForAdjustment`

**New code logic (pseudocode):**
```javascript
// Before the return statement in OptionsPanel component
const filteredPositionsForAdjustment = useMemo(() => {
  let filtered = positions;
  
  // Filter by selected expiries (if any)
  if (selectedExpiries && selectedExpiries.length > 0) {
    filtered = filtered.filter(pos => 
      selectedExpiries.includes(pos.expiry_code || pos.expiry)
    );
  }
  
  // Filter by selected strikes (if selectedStrikes state exists and has selections)
  // selectedStrikes format: { symbol: true/false }
  if (selectedStrikes && Object.keys(selectedStrikes).some(k => selectedStrikes[k])) {
    const selectedSymbols = Object.keys(selectedStrikes).filter(k => selectedStrikes[k]);
    filtered = filtered.filter(pos => 
      selectedSymbols.includes(pos.product_symbol)
    );
  }
  
  return filtered;
}, [positions, selectedExpiries, selectedStrikes]);

// Then in JSX, pass filteredPositionsForAdjustment instead of positions
<SensibullStyleAdjustmentPage
  currentPositions={filteredPositionsForAdjustment}  // ← Use filtered
  ...
/>
```

#### 2. **Check if `selectedStrikes` state exists**
Search OptionsPanel.js for:
- `selectedStrikes` state declaration
- `toggleStrikeSelection` function (or similar)
- Checkbox in table rows that toggles strike selection

**If it doesn't exist in current version:**
- Check backup file: `/Users/ssr/Projects/WorkingBot/webui/frontend/.backups/20260118_164347/components/options/OptionsPanel.js`
- It has `selectedStrikes` state around line 325
- Copy the state declaration and related functions if missing in current version

**DO NOT implement checkbox UI if it doesn't exist.** Only add state if user confirms it's missing.

---

## IMPLEMENTATION STEPS (Mandatory Sequence)

### Step 1: Read & Verify (5 min)
```bash
# Check if selectedStrikes exists in current OptionsPanel.js
grep -n "selectedStrikes" webui/frontend/src/components/options/OptionsPanel.js

# If not found, check backup
grep -n "selectedStrikes" webui/frontend/.backups/20260118_164347/components/options/OptionsPanel.js
```

**Output to user:**
- "selectedStrikes state exists: YES/NO"
- "Line number where it's declared: XXX"

### Step 2: Add Filtering Logic (10 min)
1. Locate the `return` statement in `OptionsPanel` component (around line 6300-6400)
2. **Before the return**, add `filteredPositionsForAdjustment` useMemo (code above)
3. Verify imports: Ensure `useMemo` is imported from React

### Step 3: Update Props (2 min)
1. Find `<SensibullStyleAdjustmentPage` component usage (line ~6404)
2. Change `currentPositions={positions}` to `currentPositions={filteredPositionsForAdjustment}`

### Step 4: Test Scenarios (5 min)
After changes, verify these scenarios work:
- ✅ No expiry selected, no strikes selected → Shows all positions (fallback)
- ✅ Expiry selected, no strikes selected → Shows all positions for that expiry
- ✅ Expiry selected, specific strikes selected → Shows only those strikes
- ✅ Multiple expiries selected, specific strikes selected → Shows selected strikes across expiries

---

## SAFETY CHECKS (Mandatory Before Committing)

### ❌ DO NOT:
- Refactor existing position loading logic
- Modify API calls to `/api/options/open_positions`
- Change any trading execution code
- Touch payoff calculation engine
- Modify SL/TP, Max Loss, or automation logic
- Change existing UI styling
- Add new UI elements (checkboxes, buttons) unless confirming with user first

### ✅ DO:
- Only add filtering logic before passing props
- Use existing state variables (`selectedExpiries`, `selectedStrikes`)
- Preserve all existing behavior if no selections made
- Add defensive checks for undefined/null states

---

## CODE TEMPLATE (Exact Implementation)

### Location: `OptionsPanel.js` (Before return statement, around line 6300)

```javascript
// FEB 2, 2026: Filter positions for adjustment panel based on user selection
const filteredPositionsForAdjustment = useMemo(() => {
  let filtered = [...positions]; // Create copy to avoid mutation
  
  // Filter by selected expiries (if any)
  if (selectedExpiries && selectedExpiries.length > 0) {
    filtered = filtered.filter(pos => {
      const posExpiry = pos.expiry_code || pos.expiry;
      return selectedExpiries.includes(posExpiry);
    });
  }
  
  // Filter by selected strikes (if any checkboxes checked)
  // Check if selectedStrikes exists and has any true values
  if (
    selectedStrikes && 
    typeof selectedStrikes === 'object' &&
    Object.values(selectedStrikes).some(val => val === true)
  ) {
    const selectedSymbols = Object.keys(selectedStrikes).filter(sym => selectedStrikes[sym] === true);
    filtered = filtered.filter(pos => selectedSymbols.includes(pos.product_symbol));
  }
  
  // Fallback: if filtering results in empty array, return original positions
  // This prevents showing blank payoff graph
  return filtered.length > 0 ? filtered : positions;
}, [positions, selectedExpiries, selectedStrikes]);
```

### Location: `OptionsPanel.js` (Line ~6404, inside return JSX)

```javascript
{/* BEFORE (Current): */}
<SensibullStyleAdjustmentPage
  open={adjustmentPanelOpen}
  onClose={() => setAdjustmentPanelOpen(false)}
  currentPositions={positions}  // ← Change this line
  spotPrice={btcPrice || ethPrice}
  underlying={positions[0]?.product_symbol?.split('-')[1] || 'BTC'}
  onExecuteComplete={() => {
    setAdjustmentPanelOpen(false);
    handleRefresh();
  }}
/>

{/* AFTER (New): */}
<SensibullStyleAdjustmentPage
  open={adjustmentPanelOpen}
  onClose={() => setAdjustmentPanelOpen(false)}
  currentPositions={filteredPositionsForAdjustment}  // ← Use filtered
  spotPrice={btcPrice || ethPrice}
  underlying={filteredPositionsForAdjustment[0]?.product_symbol?.split('-')[1] || positions[0]?.product_symbol?.split('-')[1] || 'BTC'}
  onExecuteComplete={() => {
    setAdjustmentPanelOpen(false);
    handleRefresh();
  }}
/>
```

---

## VERIFICATION CHECKLIST

After implementation, answer these questions:
- [ ] Did you read the entire OptionsPanel.js before making changes?
- [ ] Did you verify `selectedStrikes` state exists?
- [ ] Did you add `useMemo` import if missing?
- [ ] Did you test with no selections (fallback to all positions)?
- [ ] Did you test with expiry selection only?
- [ ] Did you test with strike selection only?
- [ ] Did you avoid refactoring unrelated code?
- [ ] Did you avoid touching trading logic or API calls?
- [ ] Did you preserve all existing prop names and types?

---

## EXPECTED OUTPUT FORMAT

1. **Brief summary** (max 5 lines):
   - What state variables were found
   - What filtering logic was added
   - What prop was changed

2. **Code blocks** with clear markers:
```
--- FILE: OptionsPanel.js (Line 6300) ---
--- BEFORE ---
[only the useMemo section or "N/A - new addition"]

--- AFTER ---
[the new useMemo filtering logic]

--- FILE: OptionsPanel.js (Line 6404) ---
--- BEFORE ---
currentPositions={positions}

--- AFTER ---
currentPositions={filteredPositionsForAdjustment}
```

3. **Testing instructions:**
   - How to verify the change works
   - Console log commands to check filtered data

---

## STOP CONDITIONS

**STOP and ask user if:**
- `selectedStrikes` state doesn't exist in current file
- `selectedExpiries` state doesn't exist
- OptionsPanel.js structure is significantly different from expected
- SensibullStyleAdjustmentPage props are different from spec
- Any trading logic needs modification (it shouldn't)

**DO NOT GUESS. DO NOT PROCEED WITHOUT CONFIRMATION.**

---

## RESTART INSTRUCTIONS (After Implementation)

From project root directory:
```bash
# Backend restart
cd webui/backend
source venv/bin/activate
pkill -f "python app.py"
python app.py &

# Frontend restart
cd ../frontend
npm start
```

Wait 10 seconds, then test in browser:
1. Select an expiry from dropdown
2. Check 2-3 strike checkboxes
3. Click "Adjust Position"
4. Verify payoff graph shows only selected strikes

---

**END OF TASK SPECIFICATION**

Proceed with implementation only after reading and understanding all files mentioned above.
