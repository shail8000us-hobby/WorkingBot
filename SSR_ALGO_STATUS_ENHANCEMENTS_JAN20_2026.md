# SSR Algo Status & Visibility Enhancements
**Date:** January 20, 2026  
**Status:** ✅ COMPLETED

## Overview
Enhanced the SSR Algo dashboard to provide complete visibility into:
1. **Order fill status** - Show pending orders with warnings
2. **Algo running state** - Visual indicators when monitoring is active
3. **Next trigger information** - Distance to nearest adjustment trigger
4. **Real-time polling** - Faster updates when orders are filling

---

## 1. Pending Orders Warning System

### Frontend Changes
**File:** `webui/frontend/src/components/ssrAlgo/SSRAlgoDashboard.js`

Added warning chip in payoff diagram header:
```javascript
{selectedPayoff?.pending_orders_count > 0 && (
  <Tooltip title={selectedPayoff.warning || "Orders filling on exchange..."} arrow>
    <Chip 
      size="small" 
      label={`⚠️ ${selectedPayoff.pending_orders_count} pending`}
      sx={{ 
        height: 18, 
        fontSize: '0.6rem',
        bgcolor: 'rgba(251, 191, 36, 0.2)',
        color: '#fbbf24',
        fontWeight: 600,
        cursor: 'help'
      }} 
    />
  </Tooltip>
)}
```

**Visual Display:**
- Shows `⚠️ X pending` chip when orders haven't filled yet
- Tooltip displays full warning message from backend
- Yellow/amber color to indicate waiting state
- Positioned next to the "● LIVE" monitoring indicator

### Backend Support
**File:** `webui/backend/routes/ssr_algo/ssr_algo_api.py`

The `get_session_payoff` endpoint already returns:
- `pending_orders_count` - Number of unfilled orders
- `warning` - Message like "⚠️ X orders still pending - payoff based only on Y filled positions"
- `fill_check` - Number of fills checked

---

## 2. Enhanced Status Indicators

### Live Monitoring Badge
Already exists in dashboard - shows green "● LIVE" chip when `status === 'MONITORING'`

**Location:** Payoff Diagram header
```javascript
{selectedSession?.status === 'MONITORING' && (
  <Chip 
    size="small" 
    label="● LIVE" 
    sx={{ 
      height: 18, 
      fontSize: '0.6rem',
      bgcolor: 'rgba(34, 197, 94, 0.2)',
      color: '#22c55e',
      fontWeight: 700,
    }} 
  />
)}
```

### Status Banner
**File:** `webui/frontend/src/components/ssrAlgo/SSRAlgoStatusBanner.js`

Shows comprehensive monitoring information:
- ✅ Current Status (IDLE, SELECTING_STRIKES, EXECUTING_AUTO_LOOP, MONITORING, etc.)
- ✅ Current Price with trend indicators (↑↓)
- ✅ ATM Strike reference
- ✅ Trigger zones (upper/lower)
- ✅ Rounds completed (X / Y)
- ✅ Open legs count
- ✅ Expiry date
- ✅ Time window
- ✅ Adjustments count
- ✅ Active time duration

---

## 3. Next Trigger Information

### Enhanced Trigger Display
**File:** `webui/frontend/src/components/ssrAlgo/SSRAlgoStatusBanner.js`

Replaced basic trigger zone display with intelligent distance calculator:

**Before:**
```javascript
<Typography variant="caption">Trigger Zones</Typography>
<Chip label="$65.5k" /> {/* Lower */}
<Chip label="$72.3k" /> {/* Upper */}
```

**After:**
```javascript
<Typography variant="caption">Next Trigger</Typography>
{price && (() => {
  const lowerTrigger = payoffData.adjustment_triggers.lower_trigger;
  const upperTrigger = payoffData.adjustment_triggers.upper_trigger;
  const distanceToLower = Math.abs(price - lowerTrigger);
  const distanceToUpper = Math.abs(price - upperTrigger);
  const nearestTrigger = distanceToLower < distanceToUpper ? lowerTrigger : upperTrigger;
  const distance = Math.min(distanceToLower, distanceToUpper);
  const isLower = nearestTrigger === lowerTrigger;
  const percentage = ((distance / price) * 100).toFixed(1);
  
  return (
    <Tooltip title={`${isLower ? 'Lower' : 'Upper'} trigger at $${nearestTrigger.toLocaleString()}`}>
      <Chip 
        label={`$${(nearestTrigger / 1000).toFixed(1)}k ${isLower ? '↓' : '↑'}${(distance / 1000).toFixed(1)}k (${percentage}%)`}
        sx={{ 
          bgcolor: percentage < 5 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(239, 68, 68, 0.2)',
          color: percentage < 5 ? '#fca5a5' : '#f87171',
          fontWeight: percentage < 5 ? 700 : 600,
          border: percentage < 5 ? '1px solid rgba(239, 68, 68, 0.5)' : 'none',
        }}
      />
    </Tooltip>
  );
})()}
```

**Features:**
- ✅ Calculates distance to both upper and lower triggers
- ✅ Shows only the NEAREST trigger (either lower ↓ or upper ↑)
- ✅ Displays absolute distance (e.g., "↓$3.1k")
- ✅ Shows percentage distance (e.g., "4.5%")
- ✅ Visual warning when within 5% of trigger (brighter red, border)
- ✅ Tooltip shows full trigger price

**Example Display:**
```
Next Trigger
[$ 65.6k ↓$3.1k (4.5%)]  ← Chip with tooltip
```

---

## 4. Intelligent Polling System

### Dynamic Refresh Rate
**File:** `webui/frontend/src/components/ssrAlgo/SSRAlgoDashboard.js`

**Before:**
- Fixed 30-second polling for payoff data

**After:**
- **5-second polling** when pending orders exist
- **30-second polling** when all orders filled
- Automatically adjusts based on `pending_orders_count`

```javascript
// Auto-refresh payoff for selected session
// Faster polling (5s) when pending orders exist, slower (30s) otherwise
useEffect(() => {
  if (!selectedSession || selectedSession.status !== 'MONITORING') return;
  
  // Determine polling interval based on pending orders
  const hasPendingOrders = selectedPayoff?.pending_orders_count > 0;
  const pollInterval = hasPendingOrders ? 5000 : 30000; // 5s if pending, 30s otherwise
  
  const payoffInterval = setInterval(async () => {
    try {
      const result = await ssrAlgoService.getSessionPayoff(selectedSession.session_id);
      if (result.success) {
        setSelectedPayoff(result);
      }
    } catch (err) {
      console.error('Failed to refresh payoff:', err);
    }
  }, pollInterval);
  
  return () => clearInterval(payoffInterval);
}, [selectedSession, selectedPayoff?.pending_orders_count]); // Re-run when pending count changes
```

**Benefits:**
- ✅ Real-time visibility when orders are filling
- ✅ Reduced server load when orders complete
- ✅ User sees payoff graph appear as soon as fills complete
- ✅ Warning chip automatically disappears when pending_orders_count reaches 0

---

## User Experience Improvements

### Before This Update:
❌ Payoff graph shows "Loading..." indefinitely  
❌ No indication why payoff isn't showing  
❌ Can't tell if algo is actually running  
❌ Don't know when next adjustment will trigger  
❌ No visibility into order fill progress  

### After This Update:
✅ "⚠️ X pending" chip shows exactly why payoff isn't ready  
✅ Tooltip explains: "⚠️ 12 orders still pending - payoff based only on 0 filled positions"  
✅ Green "● LIVE" badge confirms algo is monitoring  
✅ "Next Trigger" shows: "$65.6k ↓$3.1k (4.5%)" - crystal clear distance info  
✅ Graph auto-updates every 5 seconds when orders filling  
✅ Status banner shows comprehensive monitoring state  

---

## Testing Checklist

### To Verify:
1. ✅ Start a new SSR Algo session
2. ✅ Observe "⚠️ X pending" chip appears in payoff diagram header
3. ✅ Hover over chip to see full warning message
4. ✅ Verify "● LIVE" chip shows when status is MONITORING
5. ✅ Check status banner shows "Next Trigger" with distance calculation
6. ✅ Wait 5 seconds - payoff should auto-refresh
7. ✅ Once all orders fill, chip should disappear
8. ✅ Polling should slow to 30 seconds after fills complete
9. ✅ Trigger distance should update in real-time as price moves
10. ✅ Warning intensity should increase when within 5% of trigger

---

## Technical Implementation Summary

### Files Modified:
1. **SSRAlgoDashboard.js** (Lines 383-410)
   - Added pending orders warning chip
   - Modified auto-refresh polling logic (Lines 119-135)

2. **SSRAlgoStatusBanner.js** (Lines 200-241)
   - Enhanced trigger zone display with distance calculator
   - Added percentage-based visual warnings

### Dependencies:
- Material-UI `<Tooltip>` component (already imported)
- Backend API returns: `pending_orders_count`, `warning`, `adjustment_triggers`
- Payoff service: `ssrAlgoService.getSessionPayoff()`

### Build Status:
✅ Frontend built successfully (no errors)
✅ Backend restart not required (API already supports all fields)

---

## Architecture Alignment

This enhancement follows the SSR Algo Architecture principles:
- **Section 8.2:** Real-time monitoring status display
- **Section 8.3:** User visibility into system state
- **Section 5.4:** Order fill tracking and verification
- **Section 6.2:** Max loss trigger zone calculations

All changes maintain backward compatibility and work with the existing order fill tracking system implemented in the critical bug fix.

---

## Next Steps (Optional Enhancements)

### Potential Future Improvements:
1. **Audio Alerts:** Sound notification when within 5% of trigger
2. **Push Notifications:** Browser notifications for critical events
3. **Historical Trigger Log:** Show past adjustments in timeline
4. **Predicted Trigger Time:** Estimate time until trigger based on price velocity
5. **Mobile Responsiveness:** Optimize chip layout for smaller screens
6. **Color-coded Price:** Red when approaching lower, green when approaching upper
7. **Trigger Zone Visualization:** Add visual bands to payoff chart

---

## Related Documents
- [SSR_ALGO_ARCHITECTURE.md](SSR_ALGO_ARCHITECTURE.md) - Overall system architecture
- [BUG_FIX_CONFIG_AND_SYMBOL_ERRORS_JAN20_2026.md](BUG_FIX_CONFIG_AND_SYMBOL_ERRORS_JAN20_2026.md) - Critical payoff bug fix (prerequisite)
- [backend_frontend.md](backend_frontend.md) - Development workflow
