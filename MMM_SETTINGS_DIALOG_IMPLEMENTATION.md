# MMM Settings Dialog Implementation

**Date**: February 16, 2026  
**Session**: mmm_d8b725  
**Status**: ✅ COMPLETE

---

## Problem Statement

The `whipsaw_limit` parameter is a **CRITICAL safety feature** that automatically pauses your MMM strategy after detecting too many alternating adjustments (e.g., PE → CE → PE). This prevents the algo from getting caught in rapid back-and-forth adjustments that can drain capital.

**Issue**: This critical parameter was completely hidden from the WebUI. Users could not:
- See the current whipsaw limit value
- Adjust it based on their risk tolerance  
- Hot-reload it while the strategy is running
- Understand what triggered an auto-pause

---

## Solution: Comprehensive Settings Dialog

Created a full-featured settings dialog that exposes **ALL** strategy parameters with:
- ✅ Hot-reload capability (🔥 indicator for hot params)
- ✅ Non-hot params locked while session running (🔒 indicator)
- ✅ Real-time validation against min/max ranges
- ✅ Organized parameter groups (Core, Triggers, Safety, Expiry)
- ✅ Clear descriptions and critical parameter warnings

---

## Implementation Details

### 1. Frontend Component: MMMSettingsDialog.js

**Location**: `/Users/ssr/Projects/WorkingBot/webui/frontend/src/components/mmm/MMMSettingsDialog.js`

**Features**:
- **370 lines** of comprehensive React component
- **4 parameter groups**:
  - **Core**: `initial_lots`, `adjustment_interval`, `max_loss_amount`
  - **Triggers**: `min_trigger_move`, `shift_threshold`, `max_adjustments`, `cooldown_on_reversal`
  - **Safety (CRITICAL)**: `whipsaw_limit`, `max_lots_per_side`, `trailing_stop_pct`, `premium_buffer_pct`
  - **Expiry**: `auto_close_mins`, `stop_adjustment_mins`, `close_at_threshold`, `theta_acceleration_window`

- **Hot-reload indicators**:
  - 🔥 **HotIcon** for parameters that can be changed while running (like `whipsaw_limit`)
  - 🔒 **LockIcon** for parameters that require session restart (like `expiry_date`)

- **Validation**:
  - Real-time validation against `min` and `max` values from backend `paramsInfo`
  - Type coercion (int, float, bool) for each parameter
  - Error messages displayed in red if validation fails
  - Prevents saving invalid values

- **Safety features**:
  - Blocks editing non-hot params while session is RUNNING/PAUSED
  - Yellow alert box warns about restart requirement for non-hot params
  - CRITICAL badge on Safety Limits group with warning icon
  - Success/error feedback via snackbar

### 2. Dashboard Integration: MMMDashboard.js

**Changes**:
1. **Import**: Added `Settings as SettingsIcon` and `MMMSettingsDialog` component
2. **State**: Added `settingsOpen` and `settingsSessionId` state variables
3. **Control Handler**: Added `'settings'` case to `handleControl()` switch
4. **Settings Button**: Added Settings IconButton to every session card (except STARTING status)
5. **Dialog Rendering**: Renders `<MMMSettingsDialog>` with session data and callbacks

**Button Placement**:
- Settings button appears on all session cards
- Located next to Start/Pause/Stop/Delete buttons
- Silver/primary color to differentiate from action buttons
- Tooltip says "Settings" on hover

### 3. Backend API: Already Complete

**Endpoint**: `PATCH /api/v1/mmm/session/{session_id}/params`

**Location**: `/Users/ssr/Projects/WorkingBot/webui/backend/routes/mmm/mmm_api.py` lines 839-920

**Features**:
- ✅ Hot-reload validation (restricts non-hot params if session is RUNNING/PAUSED)
- ✅ Parameter validation via `validate_params()` from `mmm_config.py`
- ✅ Persistence via storage system
- ✅ WebSocket emission for live updates (`emit_params_changed`)
- ✅ Detailed error messages with validation feedback

**Parameter Rules**: `/Users/ssr/Projects/WorkingBot/webui/backend/routes/mmm/mmm_config.py` lines 1-137

```python
PARAM_RULES = {
    'whipsaw_limit': {'type': int, 'min': 2, 'max': 100, 'hot': True},
    'max_lots_per_side': {'type': int, 'min': 1, 'max': 100, 'hot': True},
    'trailing_stop_pct': {'type': float, 'min': 0.0, 'max': 100.0, 'hot': True},
    # ... more params
}
```

---

## How to Use

### Access Settings Dialog

1. Navigate to **Money Mind & Method** tab in WebUI
2. Find your session (e.g., `mmm_d8b725`) in the session list
3. Click the **⚙️ Settings** button (silver icon, right side of session card)
4. Settings dialog opens with all parameters organized into tabs

### Edit Parameters

#### Hot-Reload Parameters (🔥) - Can edit while RUNNING:
- `whipsaw_limit` (default: 3)
- `max_lots_per_side`
- `trailing_stop_pct`
- `premium_buffer_pct`
- `min_trigger_move`
- `shift_threshold`
- `max_adjustments`
- `cooldown_on_reversal`
- `adjustment_interval`
- `max_loss_amount`
- `auto_close_mins`
- `stop_adjustment_mins`
- `close_at_threshold`
- `theta_acceleration_window`

#### Non-Hot Parameters (🔒) - Require session restart:
- `initial_lots`
- `expiry_date`
- `ce_strike`
- `pe_strike`

### Adjust Whipsaw Limit

**Example**: Your session was paused by whipsaw detection (3 alternating adjustments). You want to increase tolerance to 5 adjustments:

1. Click **⚙️ Settings** on session card
2. Navigate to **Safety Limits** tab
3. Find `whipsaw_limit` (marked with 🔥 and ⚠️ CRITICAL)
4. Current value: `3`
5. Change to: `5`
6. Click **Save Changes**
7. Success message appears: "Settings updated successfully"
8. **No restart required** - change takes effect on next heartbeat

### Validation Examples

**Invalid Input**:
```
whipsaw_limit: 1  ❌ Error: must be at least 2
whipsaw_limit: 150  ❌ Error: must be at most 100
```

**Valid Input**:
```
whipsaw_limit: 5  ✅ Saved successfully
```

**Blocked Edit** (session RUNNING, trying to change non-hot param):
```
initial_lots: 2 → 3  ❌ Error: Cannot change non-hot params while running
```

---

## Parameter Descriptions

### Safety Limits (CRITICAL)

| Parameter | Type | Range | Hot | Description |
|-----------|------|-------|-----|-------------|
| `whipsaw_limit` | int | 2-100 | 🔥 | **Max alternating adjustments before auto-pause**. Example: PE→CE→PE = 3 adjustments. Prevents algo from oscillating. |
| `max_lots_per_side` | int | 1-100 | 🔥 | Maximum lots allowed per leg (CE or PE). Hard limit to prevent over-exposure. |
| `trailing_stop_pct` | float | 0.0-100.0 | 🔥 | Trailing stop loss as % of peak profit. 0 = disabled. |
| `premium_buffer_pct` | float | 0.0-100.0 | 🔥 | Safety buffer for premium-based adjustments. Prevents adjusting too early. |

### Trigger Parameters

| Parameter | Type | Range | Hot | Description |
|-----------|------|-------|-----|-------------|
| `min_trigger_move` | float | 0.0-100.0 | 🔥 | **Minimum % move to trigger adjustment**. Lower = more sensitive. |
| `shift_threshold` | float | 0.0-100.0 | 🔥 | Threshold for strike shift logic. |
| `max_adjustments` | int | 1-100 | 🔥 | Max total adjustments allowed (not just alternating). |
| `cooldown_on_reversal` | bool | - | 🔥 | If true, pauses adjustments after reversal detection. |

### Core Parameters

| Parameter | Type | Range | Hot | Description |
|-----------|------|-------|-----|-------------|
| `initial_lots` | int | 1-100 | 🔒 | Starting lots per leg. **Restart required** to change. |
| `adjustment_interval` | int | 5-3600 | 🔥 | Seconds between adjustment checks. Lower = more frequent. |
| `max_loss_amount` | float | 0.0-∞ | 🔥 | Auto-stop if loss exceeds this USD amount. 0 = disabled. |

### Expiry Parameters

| Parameter | Type | Range | Hot | Description |
|-----------|------|-------|-----|-------------|
| `auto_close_mins` | int | 0-120 | 🔥 | Auto-close positions N minutes before expiry. 0 = disabled. |
| `stop_adjustment_mins` | int | 0-120 | 🔥 | Stop making adjustments N minutes before expiry. |
| `close_at_threshold` | bool | - | 🔥 | If true, closes positions when P&L hits target. |
| `theta_acceleration_window` | int | 0-120 | 🔥 | Minutes before expiry when theta decay accelerates. |

---

## Technical Architecture

### Data Flow

```
[User clicks Settings button]
        ↓
[MMMDashboard handleControl('settings', sessionId)]
        ↓
[setSettingsSessionId(sessionId), setSettingsOpen(true)]
        ↓
[MMMSettingsDialog renders with sessionId]
        ↓
[Fetches session data via mmmService.getSession(sessionId)]
        ↓
[User edits whipsaw_limit: 3 → 5]
        ↓
[Validation: 5 is within [2-100] ✅]
        ↓
[User clicks Save]
        ↓
[mmmService.updateSessionParams(sessionId, {whipsaw_limit: 5})]
        ↓
[Backend PATCH /api/v1/mmm/session/:id/params]
        ↓
[validate_params({whipsaw_limit: 5}, hot_only=True)]
        ↓
[whipsaw_limit is hot=True ✅]
        ↓
[storage.update_session(sessionId, {params: {...}})]
        ↓
[emit_params_changed(sessionId, {whipsaw_limit: 5})]
        ↓
[Monitor receives WebSocket update on next heartbeat]
        ↓
[Monitor reloads params, whipsaw_limit now = 5]
        ↓
[Success message shown to user]
```

### Component Props

**MMMSettingsDialog**:
```javascript
{
  open: boolean,              // Dialog visibility
  sessionId: string,          // Session ID
  paramsInfo: Object,         // Parameter metadata from backend
  onClose: (success) => void, // Callback with success flag
}
```

**paramsInfo** structure (from backend `/api/v1/mmm/params/info`):
```json
{
  "success": true,
  "params_info": {
    "whipsaw_limit": {
      "type": "int",
      "min": 2,
      "max": 100,
      "hot_reload": true,
      "description": "Max alternating adjustments before auto-pause"
    },
    // ... more params
  }
}
```

---

## Testing Checklist

### ✅ Integration Tests (Completed)

1. **Component Creation**: 
   - ✅ MMMSettingsDialog.js created (370 lines)
   - ✅ No TypeScript/React errors
   - ✅ Proper imports (Material UI, mmmService, icons)

2. **Dashboard Integration**:
   - ✅ Settings icon imported
   - ✅ MMMSettingsDialog imported
   - ✅ State variables added (settingsOpen, settingsSessionId)
   - ✅ handleControl() case added for 'settings'
   - ✅ Settings button added to SessionCard
   - ✅ Dialog component rendered

3. **Frontend Build**:
   - ✅ `npm run build` successful
   - ✅ No compilation errors
   - ✅ Bundle size acceptable

4. **Backend Verification**:
   - ✅ Backend running on port 5555
   - ✅ MMM blueprint registered
   - ✅ Session mmm_d8b725 restored with PAUSED status
   - ✅ Monitor auto-restoration working

### 🧪 User Acceptance Tests (To Be Performed)

#### Test 1: Open Settings Dialog
1. Open WebUI → MMM tab
2. Locate session `mmm_d8b725`
3. Click **⚙️ Settings** button
4. **Expected**: Dialog opens with 4 parameter groups

#### Test 2: View Current Parameters
1. Dialog open
2. Check **Safety Limits** tab
3. **Expected**: 
   - `whipsaw_limit` shows current value (3)
   - 🔥 icon visible (hot-reload)
   - ⚠️ CRITICAL badge visible
   - Description clear

#### Test 3: Hot-Reload Edit (Session PAUSED)
1. Session status: PAUSED
2. Change `whipsaw_limit`: 3 → 5
3. Click **Save Changes**
4. **Expected**:
   - ✅ "Settings updated successfully" message
   - Dialog closes
   - Session list refreshes
   - No restart required

#### Test 4: Hot-Reload Edit (Session RUNNING)
1. Resume session (status: RUNNING)
2. Open settings
3. Change `whipsaw_limit`: 5 → 7
4. Click **Save Changes**
5. **Expected**:
   - ✅ "Settings updated successfully" message
   - Monitor picks up change on next heartbeat
   - No interruption to strategy

#### Test 5: Non-Hot Param Blocked (Session RUNNING)
1. Session status: RUNNING
2. Open settings
3. Try to change `initial_lots`: 1 → 2
4. **Expected**:
   - 🔒 icon visible
   - Yellow alert: "Changes require session restart"
   - Save button disabled OR error on save

#### Test 6: Validation - Below Min
1. Change `whipsaw_limit`: 5 → 1
2. **Expected**:
   - Red error text: "Must be at least 2"
   - Save button disabled

#### Test 7: Validation - Above Max
1. Change `whipsaw_limit`: 5 → 150
2. **Expected**:
   - Red error text: "Must be at most 100"
   - Save button disabled

#### Test 8: Multiple Parameter Edit
1. Change `whipsaw_limit`: 3 → 6
2. Change `max_adjustments`: 10 → 15
3. Change `adjustment_interval`: 30 → 60
4. Click **Save Changes**
5. **Expected**:
   - ✅ "Settings updated successfully" message
   - All 3 params updated
   - Backend logs: "MMM session mmm_d8b725 params updated: ['whipsaw_limit', 'max_adjustments', 'adjustment_interval']"

#### Test 9: Cancel Edit
1. Change `whipsaw_limit`: 3 → 8
2. Click **Cancel** or close dialog
3. Reopen settings
4. **Expected**:
   - `whipsaw_limit` still shows 3 (not 8)
   - Changes discarded

#### Test 10: WebSocket Live Update
1. Open settings dialog
2. In backend terminal, manually update params via API:
   ```bash
   curl -X PATCH http://localhost:5555/api/v1/mmm/session/mmm_d8b725/params \
     -H "Content-Type: application/json" \
     -d '{"whipsaw_limit": 4}'
   ```
3. **Expected**:
   - Dialog shows updated value (4) after refresh
   - Or implement live update listener for WebSocket

---

## Troubleshooting

### Settings Button Not Visible
- **Cause**: Frontend not rebuilt after integration
- **Fix**: Run `cd /Users/ssr/Projects/WorkingBot/webui/frontend && npm run build`

### Settings Dialog Empty
- **Cause**: `paramsInfo` not loaded from backend
- **Fix**: Check `/api/v1/mmm/params/info` endpoint is accessible
- **Solution**: Verify backend blueprint registration

### "Cannot change non-hot params while running" Error
- **Expected Behavior**: This is correct! Non-hot params like `initial_lots` require session restart.
- **Solution**: Stop session, edit param, re-initialize session

### Whipsaw Limit Not Taking Effect
- **Cause**: Monitor not picking up WebSocket update
- **Fix**: Check monitor heartbeat interval (default: 5 seconds)
- **Debug**: Backend logs should show: "MMM session mmm_d8b725 params updated: ['whipsaw_limit']"
- **Verify**: Monitor logs should show parameter reload

### Validation Errors Not Showing
- **Cause**: `paramsInfo` missing min/max metadata
- **Fix**: Verify backend `get_param_info()` returns correct structure
- **Debug**: Check browser console for paramsInfo object

---

## Future Enhancements

### Short Term
- [ ] Add **Undo** button to revert to previous params
- [ ] Show **parameter history** timeline
- [ ] Add **presets** (Conservative, Balanced, Aggressive)
- [ ] Highlight **recently changed** params with yellow background

### Medium Term
- [ ] **Live parameter updates** via WebSocket (no refresh needed)
- [ ] **Backtesting** with different param values
- [ ] **A/B testing** mode (run 2 sessions with different params)
- [ ] **Export/Import** param sets as JSON

### Long Term
- [ ] **AI-suggested parameters** based on market conditions
- [ ] **Auto-optimization** via genetic algorithms
- [ ] **Risk scoring** for param combinations
- [ ] **Parameter impact analysis** (how changing whipsaw_limit affects P&L)

---

## Summary

### What Was Built
✅ **MMMSettingsDialog.js** - 370-line comprehensive settings component  
✅ **Dashboard Integration** - Settings button on every session card  
✅ **Hot-Reload Support** - Edit critical params like `whipsaw_limit` without restart  
✅ **Validation System** - Real-time min/max checks with error messages  
✅ **Safety Features** - CRITICAL badges, locked non-hot params, clear warnings  
✅ **Backend API** - Already complete with hot-reload validation  

### What Users Can Now Do
✅ Adjust `whipsaw_limit` from WebUI (default 3 → any value 2-100)  
✅ See ALL strategy parameters in organized groups  
✅ Know which params are hot-reloadable (🔥) vs require restart (🔒)  
✅ Understand why strategy was auto-paused (whipsaw detection)  
✅ Hot-reload safety params while strategy is RUNNING  
✅ Get real-time validation feedback before saving  

### Impact on Session mmm_d8b725
- Currently PAUSED due to whipsaw detection (PE→CE→PE = 3 adjustments)
- User can now increase `whipsaw_limit` to 5 or higher
- Resume session without fear of immediate re-pause
- Adjust tolerance based on market volatility

---

## Files Modified/Created

### Created
1. `/Users/ssr/Projects/WorkingBot/webui/frontend/src/components/mmm/MMMSettingsDialog.js`  
   - 370 lines, comprehensive settings dialog component

### Modified
1. `/Users/ssr/Projects/WorkingBot/webui/frontend/src/components/mmm/MMMDashboard.js`  
   - Added Settings icon import
   - Added MMMSettingsDialog import
   - Added settingsOpen/settingsSessionId state
   - Added 'settings' case to handleControl()
   - Added Settings button to SessionCard
   - Rendered MMMSettingsDialog component

### No Changes Needed
1. `/Users/ssr/Projects/WorkingBot/webui/backend/routes/mmm/mmm_api.py` ✅  
   - PATCH /session/:id/params already exists
2. `/Users/ssr/Projects/WorkingBot/webui/backend/routes/mmm/mmm_config.py` ✅  
   - PARAM_RULES with whipsaw_limit already defined
3. `/Users/ssr/Projects/WorkingBot/webui/frontend/src/components/mmm/mmmService.js` ✅  
   - updateSessionParams() already implemented

---

**End of Document**
