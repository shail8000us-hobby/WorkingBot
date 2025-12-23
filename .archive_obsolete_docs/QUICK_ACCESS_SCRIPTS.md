# GridBot Quick Access

## 🚀 NEW: Native macOS Apps Available!

**GridBot now has beautiful native macOS applications!** 

Instead of command scripts, you now have **5 sleek apps** with custom icons:

- ⚡️ **GridBot-Launcher.app** - Control Center with GUI menu
- ⚡️ **GridBot-Status.app** - Quick status check
- 🔴 **GridBot-Logs.app** - Live streaming logs
- 📊 **PM2-Monitor.app** - Process monitor
- 📈 **Grid-Status.app** - Grid loops & profits

### Install Apps to Desktop
```bash
cd /Users/ssr/Projects/WorkingBot
./install-apps.command
```

📖 **[Read Full Documentation →](GRIDBOT_APPS_README.md)**

---

## ✅ Already Installed on Desktop! (Legacy Shortcuts)

> **Note**: The `.command` shortcuts below have been replaced by native `.app` applications.
> The new apps are more beautiful, professional, and easier to use!
> 
> However, these shortcuts still work if you prefer them.

### ⚡ GridBot Status
**Purpose:** Quick status check  
**What it shows:**
- Bot running status (online/offline)
- Current positions & price
- Latest heartbeat
- Recent activity

**Use when:** You want a quick glance at bot health

---

### 🔴 View Bot Logs  
**Purpose:** Live streaming logs  
**What it does:**
- Shows last 50 log lines
- Follows live logs in real-time
- See trades, orders, errors as they happen
- Press `Ctrl+C` to exit

**Use when:** You want to monitor bot activity or debug issues

---

### 📊 PM2 Monitor
**Purpose:** Process & resource monitor  
**What it shows:**
- CPU & memory usage
- Process uptime
- Real-time metrics
- Press `q` to exit

**Use when:** You want to check system resources or bot performance

---

### 📈 Grid Status
**Purpose:** Grid loops & profit history  
**What it shows:**
- Completed loops with profits
- Active positions & TPs
- Pending orders
- Total profit since restart

**Use when:** You want to see trading performance snapshot

---

## Reinstalling Shortcuts

If you accidentally delete the shortcuts or want to reinstall them:

1. Navigate to `/Users/ssr/Projects/WorkingBot/`
2. Double-click: `install-desktop-shortcuts.command`
3. Shortcuts will be recreated on Desktop

## Removing Shortcuts

To clean up your Desktop:

1. Navigate to `/Users/ssr/Projects/WorkingBot/`
2. Double-click: `uninstall-desktop-shortcuts.command`
3. All GridBot shortcuts will be removed

---

## How Shortcuts Work

These are **symbolic links** (symlinks) to the actual script files in the WorkingBot folder. This means:
- ✅ They always work even if you move the WorkingBot folder
- ✅ Updates to scripts automatically apply to shortcuts
- ✅ They take no extra disk space
- ✅ Easy to remove without affecting the bot

---

## Alternative: Terminal Commands

If you prefer terminal commands:
```bash
# Quick status
cd ~/Projects/WorkingBot && ./bot-status.command

# View live logs
pm2 logs gridbot-live --lines 50

# PM2 monitor
pm2 monit

# View grid status
pm2 logs gridbot-live --lines 200 --nostream | grep -A 100 "GRID STATUS"
```

---

**Tip:** You can also add these shortcuts to your Dock by dragging them there!
