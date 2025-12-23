# 🚀 GridBot Apps - Native macOS Applications

Beautiful, sleek, native macOS applications for monitoring your GridBot trading system.

## ✨ What's New?

Your monitoring tools are now **full macOS applications** with:
- 🎨 **Custom icons** for each app
- 🖱️ **Double-click to launch** - no Terminal knowledge needed
- 📱 **Native macOS interface** - looks and feels like a real Mac app
- 🎯 **Instant access** - right from your Desktop or Dock

---

## 📦 Installed Apps

### ⚡️ GridBot-Launcher.app
**Control Center** - Choose which tool to launch from a beautiful menu
- One app to rule them all
- Clean GUI with button selection
- Perfect for beginners

### ⚡️ GridBot-Status.app
**Quick Status Check**
- Bot uptime & health
- Current positions
- Latest heartbeat
- Recent activity

### 🔴 GridBot-Logs.app
**Live Streaming Logs**
- Real-time log monitoring
- See trades as they happen
- Catch errors instantly
- Press `Ctrl+C` to exit

### 📊 PM2-Monitor.app
**Process Monitor Dashboard**
- CPU & memory usage
- Process health
- Real-time metrics
- Press `q` to exit

### 📈 Grid-Status.app
**Grid Loops & Profit History**
- Completed loops with profits
- Active positions
- Pending orders
- Total performance

---

## 🎯 How to Use

### Method 1: Double-Click on Desktop
Simply **double-click any app** on your Desktop to launch it!

### Method 2: Add to Dock
Drag any app from Desktop to your **Dock** for permanent quick access:
1. Click and hold the app icon on Desktop
2. Drag it to your Dock (bottom of screen)
3. Release to pin it there
4. Now it's just one click away, anytime!

### Method 3: Spotlight Search
Press `⌘ + Space` and type:
- "GridBot Launcher" → Opens control center
- "GridBot Status" → Quick status
- "GridBot Logs" → Live logs
- "PM2 Monitor" → Process monitor
- "Grid Status" → Grid performance

---

## 🔄 Installation & Management

### Fresh Install
```bash
cd /Users/ssr/Projects/WorkingBot
./install-apps.command
```

This will:
- ✅ Copy all 5 apps to Desktop
- ✅ Remove quarantine flags
- ✅ Refresh icon cache
- ✅ Clean up old .command shortcuts

### Reinstall/Update
Run the same installer again - it will replace existing apps.

### Uninstall
```bash
cd /Users/ssr/Projects/WorkingBot
./uninstall-apps.command
```

This removes all GridBot apps from Desktop (but keeps them in `apps/` folder).

---

## 🎨 App Architecture

Each app is a proper macOS `.app` bundle with:

```
GridBot-Status.app/
├── Contents/
│   ├── Info.plist          # App metadata
│   ├── MacOS/
│   │   └── launcher        # Executable script
│   └── Resources/
│       └── icon.icns       # Custom icon
```

### How It Works
1. You double-click the app
2. macOS launches the `launcher` script
3. Launcher opens Terminal with the appropriate command
4. You see your monitoring tool running!

---

## 🛠️ Customization

### Change App Icons
Edit `generate_app_icons.py` to use different emojis or colors, then run:
```bash
python3 generate_app_icons.py
./install-apps.command
```

### Modify Launcher Behavior
Edit the launcher scripts in:
```
/Users/ssr/Projects/WorkingBot/apps/[App-Name].app/Contents/MacOS/launcher
```

### Create New Apps
1. Copy an existing app folder structure
2. Modify `Info.plist` (change bundle ID and name)
3. Update the `launcher` script
4. Generate custom icon
5. Add to installer script

---

## 🆚 Apps vs Command Scripts

| Feature | Old (.command) | New (.app) |
|---------|---------------|-----------|
| **Look** | Terminal script icon | Custom colorful icon |
| **Feel** | Opens Terminal | Native app experience |
| **Access** | File navigation needed | Double-click anywhere |
| **Dock** | Can't add to Dock easily | Drag & drop to Dock |
| **Spotlight** | Doesn't appear | Fully searchable |
| **Professional** | Developer tool | Production ready |

---

## 💡 Pro Tips

### Dock Organization
Arrange your apps in Dock order of frequency:
1. **GridBot-Launcher.app** (daily use)
2. **GridBot-Status.app** (quick checks)
3. **GridBot-Logs.app** (troubleshooting)

### Keyboard Shortcuts
After adding to Dock, use:
- `⌘ + [Number]` to launch (e.g., `⌘ + 1` for first Dock item)

### Desktop Organization
Don't like 5 apps on Desktop?
- Move them to Applications folder: `mv ~/Desktop/*.app /Applications/`
- Or create a "GridBot" folder on Desktop and put them there
- Apps work from anywhere!

---

## 🐛 Troubleshooting

### "App is damaged and can't be opened"
This happens if quarantine flag is set:
```bash
xattr -cr ~/Desktop/GridBot-*.app
xattr -cr ~/Desktop/PM2-Monitor.app
xattr -cr ~/Desktop/Grid-Status.app
```

### Apps don't show custom icons
Refresh icon cache:
```bash
killall Dock
killall Finder
```

### Terminal doesn't open
Make sure launcher is executable:
```bash
chmod +x ~/Desktop/GridBot-Status.app/Contents/MacOS/launcher
# Repeat for other apps
```

### PM2 not found
Install PM2:
```bash
npm install -g pm2
```

### Bot not running
Start the bot first:
```bash
pm2 start ecosystem.config.js
```

---

## 📱 Screenshots

### Desktop View
All 5 apps with beautiful custom icons arranged on your Desktop.

### Launcher Menu
Click GridBot-Launcher.app → Choose from 4 options:
- 📊 Status
- 🔴 Logs  
- 📈 Grid
- 💻 PM2

### In Action
Double-click any app → Terminal opens → Command runs automatically!

---

## 🎯 Next Steps

1. ✅ **Install apps** with `./install-apps.command`
2. ✅ **Test each app** by double-clicking
3. ✅ **Add to Dock** for quick access
4. ✅ **Try the Launcher** for menu-driven access
5. ✅ **Remove old shortcuts** (done automatically)

---

## 🤝 Support

The original `.command` files still exist in `/Users/ssr/Projects/WorkingBot/`:
- `bot-status.command`
- `view-logs.command`
- `pm2-monitor.command`
- `view-grid-status.command`

These can still be used directly if needed, but the `.app` versions are recommended for better UX.

---

## 📚 Technical Details

- **Language**: Bash + AppleScript (for GUI launcher)
- **Icon Format**: `.icns` (native macOS icon format)
- **Bundle Structure**: Standard macOS `.app` bundle
- **Compatibility**: macOS 10.10+
- **Dependencies**: Terminal.app, PM2, Python 3

---

**Made with ⚡️ by GridBot Team**

*Version 2.0 - November 2025*
