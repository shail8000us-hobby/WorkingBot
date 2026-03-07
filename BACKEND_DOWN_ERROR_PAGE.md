# Backend Down Error Page - Feature Documentation

## Overview
When the WebUI backend (port 5555) is not responding, the frontend now displays a helpful error page with recovery commands instead of showing a blank page or generic error.

## What It Does

### Automatic Detection
- Detects when backend API calls fail due to network/connection errors
- Shows custom error page with actionable recovery steps
- Auto-retries connection every 10 seconds
- Allows manual retry via button

### Error Page Features

1. **Clear Error Message**
   - Prominent red header explaining backend is down
   - Shows the exact port (localhost:5555) that's unreachable

2. **5 Recovery Commands** (copy-paste ready):
   ```bash
   # 1. Start Backend via LaunchAgent (Recommended)
   launchctl start com.gridbot.webui
   
   # 2. Check Backend Status
   launchctl list | grep gridbot.webui
   
   # 3. Restart Backend
   launchctl stop com.gridbot.webui && sleep 2 && launchctl start com.gridbot.webui
   
   # 4. Manual Start (Fallback)
   cd ~/Projects/WorkingBot/webui/backend && python3 app.py &
   
   # 5. Check Port 5555
   lsof -i :5555
   ```

3. **Interactive Elements**
   - Copy-to-clipboard button for each command
   - Visual confirmation when copied (✓ icon)
   - Download as .command file (opens in Terminal.app)
   - Manual retry button
   - Auto-retry countdown

## Technical Implementation

### Files Modified

1. **`webui/frontend/src/components/BackendDownError.js`** (NEW)
   - Full-screen error page component
   - 271 lines of Material-UI components
   - Terminal-themed command display
   - Auto-retry logic with 10-second interval

2. **`webui/frontend/src/App.js`**
   - Added `backendDown` state
   - Enhanced error handling in `fetchInitialData()`
   - Conditional rendering: shows error page if `backendDown === true`
   - Auto-clears error when connection restored

### Error Detection Logic

```javascript
catch (error) {
  // Check if this is a network/connection error
  if (error.message?.includes('Network Error') || 
      error.message?.includes('ERR_CONNECTION_REFUSED') ||
      error.code === 'ECONNREFUSED' ||
      error.response === undefined) {
    setBackendDown(true);  // Show error page
  }
}
```

### State Management

- **Initial Load**: Tries to fetch data from backend
- **Backend Down**: Sets `backendDown = true`, renders error page
- **User Retries**: Calls `fetchInitialData()` again
- **Backend Restored**: Clears `backendDown`, shows normal UI
- **Auto-Retry**: Every 10 seconds, silently retries connection

## User Experience Flow

### Scenario 1: Backend Already Down
```
1. User opens http://localhost:5555
2. Frontend loads, tries to connect
3. Connection fails (ECONNREFUSED)
4. Error page shows immediately
5. User copies first command
6. Pastes in Terminal: launchctl start com.gridbot.webui
7. Clicks "Retry Connection"
8. Normal WebUI loads
```

### Scenario 2: Backend Crashes Mid-Session
```
1. User browsing WebUI normally
2. Backend crashes/stops
3. Next API call fails
4. Error page replaces current view
5. Auto-retry running in background
6. Backend restarts automatically (LaunchAgent)
7. Error page detects connection restored
8. Automatically returns to normal view
```

## Testing

### Manual Test
```bash
# 1. Stop backend
launchctl stop com.gridbot.webui

# 2. Open browser to http://localhost:5555
# Expected: Error page with 5 recovery commands

# 3. Copy and run first command
launchctl start com.gridbot.webui

# 4. Click "Retry Connection" button
# Expected: Normal WebUI loads
```

### Verification Commands
```bash
# Check if backend is running
launchctl list | grep gridbot.webui

# Check port 5555
lsof -i :5555

# View backend logs
tail -f ~/Projects/WorkingBot/webui/backend/webui.log
```

## Design Highlights

### Visual Design
- **Dark gradient background**: Matches WebUI theme
- **Red error header**: Clearly communicates critical state
- **Terminal-style code blocks**: Green text on dark background
- **Hover effects**: Cards lift and highlight on hover
- **Icon system**: Each command has color-coded icon

### UX Patterns
- **Progressive disclosure**: Shows only essential commands
- **Copy convenience**: One-click copy to clipboard
- **Visual feedback**: Checkmark confirms copy action
- **Auto-recovery**: Doesn't require user action if backend restarts
- **Persistent help**: Footer reminds about "Know Your Bot" section

## Error States Handled

| Error Type | Detection | User Action |
|------------|-----------|-------------|
| Connection refused | `ECONNREFUSED` | Start backend via LaunchAgent |
| Network error | `Network Error` | Check backend process |
| No response | `response === undefined` | Restart backend |
| Timeout | Request timeout | Check port availability |

## Future Enhancements

### Possible Additions
1. **Health check indicator**: Live status dot showing connection attempts
2. **Log viewer**: Show last 10 lines of backend logs on error page
3. **LaunchAgent status**: Real-time check if LaunchAgent is loaded
4. **Quick fix button**: One-click "Start Backend" that runs command via API proxy
5. **Diagnostic mode**: Advanced troubleshooting steps (firewall, permissions, etc.)

### Smart Detection
- Differentiate between backend down vs network issues
- Show different commands based on detected problem
- Remember which solution worked last time

## Configuration

### Auto-Retry Interval
```javascript
// In BackendDownError.js, line ~50
const interval = setInterval(() => {
  if (onRetry) onRetry();
}, 10000); // 10 seconds
```

### Error Detection Threshold
```javascript
// In App.js, fetchInitialData catch block
if (error.message?.includes('Network Error') || 
    error.message?.includes('ERR_CONNECTION_REFUSED') ||
    error.code === 'ECONNREFUSED' ||
    error.response === undefined) {
  setBackendDown(true);
}
```

## Related Features

- **Know Your Bot** section (command reference)
- **Emergency Kill** system
- **Bot Management Dashboard**
- **Health Check Dashboard**

## Impact

### Before
- User sees blank page or browser error "This site can't be reached"
- No guidance on how to fix
- User must search documentation or ask for help

### After  
- Clear error explanation
- 5 specific recovery commands with copy buttons
- Auto-retry every 10 seconds
- Seamless return to normal operation

---

**Status**: ✅ Deployed in production (build 507.83 kB)  
**Build Date**: October 30, 2025  
**Files**: 2 modified, 1 created  
**Risk Level**: Low (isolated error boundary)
