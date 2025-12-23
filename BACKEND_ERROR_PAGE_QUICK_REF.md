# Backend Down Error Page - Quick Reference

## What You'll See

When you try to access `http://localhost:5555` and the backend is down, you'll see:

```
┌─────────────────────────────────────────────────────────────┐
│                   🔴 Backend Connection Failed               │
│                                                              │
│         Cannot connect to WebUI backend at localhost:5555   │
│     The backend server is not responding.                   │
│            Use the commands below to start it.              │
└─────────────────────────────────────────────────────────────┘

⚠️  Quick Fix: Run the first command below in your Mac Terminal

┌─────────────────────────────────────────────────────────────┐
│  🔌 Recovery Commands                                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ▶ Start Backend via LaunchAgent                           │
│  Recommended: Start WebUI backend using macOS LaunchAgent   │
│  ┌──────────────────────────────────────────────────┐      │
│  │ launchctl start com.gridbot.webui                │ [Copy]│
│  └──────────────────────────────────────────────────┘      │
│                                                              │
│  🔍 Check Backend Status                                    │
│  Verify if the WebUI backend LaunchAgent is running         │
│  ┌──────────────────────────────────────────────────┐      │
│  │ launchctl list | grep gridbot.webui              │ [Copy]│
│  └──────────────────────────────────────────────────┘      │
│                                                              │
│  🔄 Restart Backend                                         │
│  Stop and restart the WebUI backend LaunchAgent             │
│  ┌──────────────────────────────────────────────────┐      │
│  │ launchctl stop com.gridbot.webui && sleep 2 &&   │ [Copy]│
│  │ launchctl start com.gridbot.webui                │      │
│  └──────────────────────────────────────────────────┘      │
│                                                              │
│  🔧 Manual Start (Fallback)                                 │
│  Manually start backend if LaunchAgent fails                │
│  ┌──────────────────────────────────────────────────┐      │
│  │ cd ~/Projects/WorkingBot/webui/backend &&        │ [Copy]│
│  │ python3 app.py &                                 │      │
│  └──────────────────────────────────────────────────┘      │
│                                                              │
│  🌐 Check Port 5555                                         │
│  See what's running on the WebUI port                       │
│  ┌──────────────────────────────────────────────────┐      │
│  │ lsof -i :5555                                    │ [Copy]│
│  └──────────────────────────────────────────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘

    After starting the backend, click below to retry

        [ 🔄 Retry Connection ]    [ ✕ Close Window ]

                Auto-retry every 10 seconds...

ℹ️  Need more help? Once the backend is running, check the 
   "Know Your Bot" section in the WebUI for complete commands.
```

## Quick Recovery (Most Common)

**Step 1:** Copy this command
```bash
launchctl start com.gridbot.webui
```

**Step 2:** Paste in Mac Terminal

**Step 3:** Click "Retry Connection" or wait 10 seconds

**Step 4:** WebUI loads normally! ✅

## Features

✅ **Auto-Detection**: Shows immediately when backend is down  
✅ **Copy Buttons**: One-click copy for each command  
✅ **Auto-Retry**: Checks every 10 seconds automatically  
✅ **Manual Retry**: Button to check immediately  
✅ **Visual Feedback**: Green checkmark when command copied  
✅ **Download Option**: Save as .command file for Terminal.app  
✅ **Smart Recovery**: Auto-returns to normal view when backend is back  

## Command Explanations

| Command | What It Does | When to Use |
|---------|--------------|-------------|
| `launchctl start` | Starts backend via macOS LaunchAgent | **First try** (recommended) |
| `launchctl list \| grep` | Shows if LaunchAgent is loaded | Verify status |
| `launchctl stop && start` | Full restart of LaunchAgent | If start alone doesn't work |
| `python3 app.py &` | Manual background start | LaunchAgent not working |
| `lsof -i :5555` | Shows what's using port 5555 | Port conflict diagnosis |

## Troubleshooting

### Error Page Not Showing?
- Check browser console (F12)
- Clear browser cache (Cmd+Shift+R)
- Verify you're accessing `http://localhost:5555`

### Commands Not Working?
1. **LaunchAgent not loaded**: Load it first
   ```bash
   launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist
   ```

2. **Permission denied**: Check file permissions
   ```bash
   ls -l ~/Projects/WorkingBot/webui/backend/app.py
   ```

3. **Port already in use**: Kill existing process
   ```bash
   lsof -ti :5555 | xargs kill -9
   ```

### Still Not Working?
Check backend logs:
```bash
tail -50 ~/Projects/WorkingBot/webui/backend/webui.log
```

## Visual Demo

To see the error page:
```bash
# Stop backend
launchctl stop com.gridbot.webui

# Open browser to http://localhost:5555
# You'll see the error page!

# Restart backend
launchctl start com.gridbot.webui
```

---

**Pro Tip**: Bookmark this page for quick access when backend goes down!
