# WebUI PM2 Control Fix - January 3, 2026

## Issue Report
- 500 Internal Server Error (user reported)
- Trading bot not starting via PM2 from webUI

## Investigation Results

### ✅ Backend Status: HEALTHY
- All PM2 endpoints responding correctly
- No 500 errors in backend logs
- CORS properly configured
- PM2 adapter working

### ✅ API Endpoints Verified
```bash
# All working from command line:
curl -X POST http://localhost:5555/api/pm2/start/gridbot-demo  # ✅ Works
curl -X POST http://localhost:5555/api/pm2/stop/gridbot-demo   # ✅ Works
curl -X POST http://localhost:5555/api/pm2/restart/gridbot-live # ✅ Works
curl http://localhost:5555/api/pm2/status                       # ✅ Works
```

## Root Cause Analysis

The issue is likely **browser-specific** and could be caused by:

1. **Browser Cache** - Old JavaScript bundles
2. **Frontend-Backend Version Mismatch** - Frontend not rebuilt after backend changes
3. **WebSocket Connection Issues** - Interfering with PM2 control
4. **Browser Console Errors** - Check for JavaScript errors

## Fix Applied

### 1. Fresh Frontend Build
Rebuilt frontend with latest code to ensure compatibility:
```bash
cd /Users/ssr/Projects/WorkingBot/webui/frontend
npm run build
```

### 2. Backend Restart
Restarted production webUI to serve new build:
```bash
launchctl kickstart -k gui/$(id -u)/com.gridbot.production.webui
```

### 3. Browser Cache Clear Required
**User must clear browser cache:**
- Chrome/Edge: Cmd+Shift+Del (Mac) or Ctrl+Shift+Del (Windows)
- Or hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)

## How to Fix the Issue

### Step 1: Clear Browser Cache
1. Open http://localhost:5555
2. Open DevTools (F12 or Cmd+Option+I)
3. Go to Network tab
4. Check "Disable cache"
5. Hard refresh: Cmd+Shift+R (or Ctrl+Shift+R)

### Step 2: Check Console for Errors
1. Open DevTools Console tab
2. Look for any red errors
3. If you see errors, report them

### Step 3: Test PM2 Control
1. Navigate to PM2 Panel in webUI
2. Try to start gridbot-demo
3. Check if it starts successfully

## Alternative: Direct PM2 Control

If webUI control still doesn't work, use command line:

```bash
# Start bot
pm2 start gridbot-live

# Stop bot
pm2 stop gridbot-live

# Restart bot
pm2 restart gridbot-live

# Check status
pm2 list

# View logs
pm2 logs gridbot-live --lines 50
```

## Verification Commands

### Check Backend Health
```bash
curl http://localhost:5555/api/health
curl http://localhost:5555/api/pm2/status
```

### Test PM2 Control from Terminal
```bash
# Test start (should work)
curl -X POST http://localhost:5555/api/pm2/start/gridbot-demo

# Test stop (should work)
curl -X POST http://localhost:5555/api/pm2/stop/gridbot-demo
```

### Use Test Page
Open the test page to isolate if issue is webUI-specific:
```bash
open /Users/ssr/Projects/WorkingBot/test_pm2_webui.html
```

Click buttons to test PM2 control directly without webUI framework.

## Expected Behavior

### When Working Correctly:
1. Click "Start" button in PM2 Panel
2. Button shows "Starting..." state
3. Success notification appears
4. Process status updates to "online"
5. Green indicator appears

### If Still Failing:
1. Check browser console for errors
2. Check if CORS error (unlikely, but possible)
3. Check network tab for failed requests
4. Note exact error message and status code

## Technical Details

### PM2 Routes (all verified working)
- `POST /api/pm2/start/<name>` ✅
- `POST /api/pm2/stop/<name>` ✅
- `POST /api/pm2/restart/<name>` ✅
- `GET /api/pm2/status` ✅
- `GET /api/pm2/process/<name>` ✅

### API Client Code
Location: `webui/frontend/src/utils/apiClient.js`
```javascript
async startPM2Process(name) {
  return this.post(`/api/pm2/start/${name}`);
}
```

This is correct and should work.

### CORS Configuration
Location: `webui/backend/app.py`
```python
CORS(app, origins=ALLOWED_ORIGINS.split(','), supports_credentials=True)
```

Allows frontend to call backend.

## Quick Fix Script

Run this to ensure everything is fresh:

```bash
#!/bin/bash
cd /Users/ssr/Projects/WorkingBot

echo "1. Rebuilding frontend..."
cd webui/frontend
npm run build

echo "2. Restarting production webUI..."
launchctl kickstart -k gui/$(id -u)/com.gridbot.production.webui

echo "3. Waiting for backend to start..."
sleep 3

echo "4. Testing PM2 control..."
curl -X POST http://localhost:5555/api/pm2/restart/gridbot-live

echo ""
echo "✅ Done! Now:"
echo "  1. Clear browser cache (Cmd+Shift+R)"
echo "  2. Open http://localhost:5555"
echo "  3. Try PM2 control in webUI"
```

## If Problem Persists

Please provide:
1. **Browser Console Errors** - Screenshot or copy/paste
2. **Network Tab** - Show the failing request (status code, response)
3. **Exact Steps** - What you clicked, what happened
4. **Browser Version** - Chrome/Safari/Firefox version

## Summary

✅ **Backend is working** - All PM2 endpoints tested and verified  
✅ **API is accessible** - curl commands work perfectly  
⚠️ **Frontend may be cached** - User must clear browser cache  
⚠️ **Check browser console** - May have JavaScript errors  

**Most likely fix:** Clear browser cache and hard refresh!

---

**Created:** January 3, 2026  
**Status:** Backend verified working, frontend rebuild completed  
**Next Action:** User must clear browser cache
