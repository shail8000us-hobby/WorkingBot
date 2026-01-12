# Integration Guide - Visual Reference

## 📍 Where to Add the Code

### File: `OptionsPanel.js`

---

## 1️⃣ Import Section (Top of File)

**Location**: After existing imports, before the component declaration

```javascript
// Existing imports...
import { Box, Typography, Paper, ... } from '@mui/material';
import OptionsPayoffDiagram from './OptionsPayoffDiagram';

// ✨ ADD THIS LINE:
import { AutomationButton, automationMonitor, notificationService } from './automation';

// Component starts...
const OptionsPanel = () => {
```

---

## 2️⃣ Table Structure (Position Rows)

**Location**: Inside the table where you render position rows

**Current Structure** (find this pattern):
```javascript
<TableRow>
  <TableCell>{/* Checkbox */}</TableCell>
  <TableCell>{symbol}</TableCell>
  <TableCell>{strike}</TableCell>  ← FIND THIS
  <TableCell>{type}</TableCell>
  <TableCell>{size}</TableCell>
  ...
</TableRow>
```

**New Structure** (add automation cell):
```javascript
<TableRow>
  <TableCell>{/* Checkbox */}</TableCell>
  <TableCell>{symbol}</TableCell>
  <TableCell>{strike}</TableCell>
  
  {/* ✨ ADD THIS CELL: */}
  <TableCell align="center" sx={{ p: 0.5 }}>
    <AutomationButton position={position} />
  </TableCell>
  
  <TableCell>{type}</TableCell>
  <TableCell>{size}</TableCell>
  ...
</TableRow>
```

**Also update the header row:**
```javascript
<TableHead>
  <TableRow>
    <TableCell>{/* Checkbox header */}</TableCell>
    <TableCell>Symbol</TableCell>
    <TableCell>Strike</TableCell>
    
    {/* ✨ ADD THIS HEADER: */}
    <TableCell align="center">Auto</TableCell>
    
    <TableCell>Type</TableCell>
    <TableCell>Size</TableCell>
    ...
  </TableRow>
</TableHead>
```

---

## 3️⃣ Monitor Initialization (useEffect Hook)

**Location**: Inside the component, after other useEffects

**Add this new useEffect:**
```javascript
const OptionsPanel = () => {
  // ... existing state and hooks ...

  // ✨ ADD THIS useEffect:
  useEffect(() => {
    // Connect automation monitor to market data
    automationMonitor.setMarketDataProvider(() => ({
      positions: visiblePositions,
      spotPrices: indexPrices,
    }));

    // Connect notifications to your toast/snackbar system
    notificationService.setToastCallback((message, severity) => {
      // If you have a setSnackbar or setToast state:
      // setSnackbar({ open: true, message, severity });
      
      // Or fallback to console:
      console.log(`[AUTOMATION ${severity}] ${message}`);
    });

    // Start the automation monitor
    automationMonitor.start();

    // Cleanup on unmount
    return () => {
      automationMonitor.stop();
    };
  }, [visiblePositions, indexPrices]);

  // ... rest of component ...
};
```

---

## 📸 Visual Reference

### Before (Current):
```
┌─────────────────────────────────────────────┐
│ Symbol  │ Strike  │ Type │ Size │ Price ... │
├─────────────────────────────────────────────┤
│ C-BTC-… │ $92,000 │ Call │ 2    │ $500  ... │
│ P-BTC-… │ $90,000 │ Put  │ 1    │ $400  ... │
└─────────────────────────────────────────────┘
```

### After (With Automation):
```
┌───────────────────────────────────────────────────┐
│ Symbol  │ Strike  │ ⚡   │ Type │ Size │ Price ... │
├───────────────────────────────────────────────────┤
│ C-BTC-… │ $92,000 │ [⚡] │ Call │ 2    │ $500  ... │
│ P-BTC-… │ $90,000 │ [⚡] │ Put  │ 1    │ $400  ... │
└───────────────────────────────────────────────────┘
                       ↑
                 Click to setup
                  automation
```

---

## 🎨 Button States

The ⚡ button shows different states:

```
⚡       → No automation (gray, transparent)
⚡ 🟡    → Waiting for conditions (yellow badge)
⚡ 🔥    → Conditions met! (orange badge, animated)
⚡ 🟢    → Position active (green badge)
⚡ 🔴    → Error (red badge)
```

---

## 🔍 Finding the Right Location in OptionsPanel.js

### Search for These Patterns:

**For Table Rows:**
```javascript
// Search for:
<TableCell>{strike}</TableCell>
<TableCell>{type}</TableCell>

// Or:
{visiblePositions.map((position, index) => (
  <TableRow key={...}>
```

**For Headers:**
```javascript
// Search for:
<TableHead>
  <TableRow>
    <TableCell>Strike</TableCell>
```

**For useEffects:**
```javascript
// Search for:
useEffect(() => {
  // Existing useEffect hooks
}, [dependencies]);

// Add the automation useEffect after existing ones
```

---

## ✅ Verification Steps

### Step 1: Build
```bash
npm run build
```
Expected: ✅ No errors

### Step 2: Start Dev Server
```bash
npm start
```
Expected: ✅ Server starts, no warnings

### Step 3: Check UI
- ✅ ⚡ button appears in each row
- ✅ Click button → dialog opens
- ✅ Form inputs work
- ✅ No console errors

### Step 4: Test Automation
- ✅ Create simple automation (IV > 0%)
- ✅ Click "Start Automation"
- ✅ Button shows 🟡 badge
- ✅ Wait 5-10 seconds
- ✅ Notification appears (check console if no toast)

---

## 🆘 Troubleshooting

### Button Doesn't Appear
```javascript
// Check: Is the import correct?
import { AutomationButton } from './automation';  // ✅ Correct
import AutomationButton from './automation';      // ❌ Wrong

// Check: Is the component placed in table?
<TableCell><AutomationButton position={position} /></TableCell>
```

### Dialog Doesn't Open
```javascript
// Check: Is position object passed correctly?
<AutomationButton position={position} />

// position should have:
// - product_symbol
// - strike
// - type
// - underlying
```

### No Notifications
```javascript
// Check: Is toast callback set?
notificationService.setToastCallback((message, severity) => {
  console.log('Toast:', message, severity);  // At least log to console
});

// Check: Is monitor started?
automationMonitor.start();  // Should be in useEffect
```

### Monitoring Not Working
```javascript
// Check: Is market data provider set correctly?
automationMonitor.setMarketDataProvider(() => ({
  positions: visiblePositions,  // Must be array of position objects
  spotPrices: indexPrices,      // Must be { BTC: 92000, ETH: 3400 }
}));

// Debug: Check data structure
console.log('Positions:', visiblePositions);
console.log('Spot Prices:', indexPrices);
```

---

## 📦 Complete Integration Example

**Full code snippet showing all changes:**

```javascript
// ============================================
// OptionsPanel.js - INTEGRATION EXAMPLE
// ============================================

import React, { useState, useEffect, useMemo } from 'react';
import { Box, Table, TableHead, TableBody, TableRow, TableCell, ... } from '@mui/material';
import OptionsPayoffDiagram from './OptionsPayoffDiagram';

// ✨ NEW: Import automation components
import { AutomationButton, automationMonitor, notificationService } from './automation';

const OptionsPanel = () => {
  // ... existing state ...
  const [visiblePositions, setVisiblePositions] = useState([]);
  const [indexPrices, setIndexPrices] = useState({ BTC: 0, ETH: 0 });
  
  // ... existing code ...

  // ✨ NEW: Initialize automation monitor
  useEffect(() => {
    automationMonitor.setMarketDataProvider(() => ({
      positions: visiblePositions,
      spotPrices: indexPrices,
    }));

    notificationService.setToastCallback((message, severity) => {
      console.log(`[AUTOMATION] ${message}`);
      // Connect to your toast/snackbar here
    });

    automationMonitor.start();

    return () => {
      automationMonitor.stop();
    };
  }, [visiblePositions, indexPrices]);

  return (
    <Box>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Symbol</TableCell>
            <TableCell>Strike</TableCell>
            <TableCell align="center">Auto</TableCell>  {/* ✨ NEW */}
            <TableCell>Type</TableCell>
            <TableCell>Size</TableCell>
            {/* ... other headers ... */}
          </TableRow>
        </TableHead>
        <TableBody>
          {visiblePositions.map((position, index) => (
            <TableRow key={index}>
              <TableCell>{position.product_symbol}</TableCell>
              <TableCell>{position.strike}</TableCell>
              
              {/* ✨ NEW: Automation button */}
              <TableCell align="center" sx={{ p: 0.5 }}>
                <AutomationButton position={position} />
              </TableCell>
              
              <TableCell>{position.type}</TableCell>
              <TableCell>{position.size}</TableCell>
              {/* ... other cells ... */}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
};

export default OptionsPanel;
```

---

## 🎯 Integration Time Estimate

- **Finding locations**: 2-3 minutes
- **Adding import**: 10 seconds
- **Adding button to table**: 1 minute
- **Adding monitor init**: 2 minutes
- **Testing**: 5 minutes

**Total**: ~10 minutes

---

## ✅ Ready to Integrate!

Follow the steps above, and you'll have a working automation system in under 10 minutes! 🚀
