#!/bin/bash
# Install GridBot Apps to Desktop

clear
echo "╔════════════════════════════════════════════════════════════╗"
echo "║          GridBot Apps Installer v2.0                       ║"
echo "║          Beautiful Native macOS Applications              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APPS_DIR="$SCRIPT_DIR/apps"
DESKTOP="$HOME/Desktop"

echo "📦 Installing GridBot monitoring apps to Desktop..."
echo ""

# Remove old .command shortcuts if they exist
echo "🧹 Cleaning up old shortcuts..."
rm -f "$DESKTOP/⚡ GridBot Status.command" 2>/dev/null
rm -f "$DESKTOP/🔴 View Bot Logs.command" 2>/dev/null
rm -f "$DESKTOP/📊 PM2 Monitor.command" 2>/dev/null
rm -f "$DESKTOP/📈 Grid Status.command" 2>/dev/null

# Copy app bundles to Desktop
apps=(
    "GridBot-Launcher.app"
    "GridBot-Status.app"
    "GridBot-Logs.app"
    "PM2-Monitor.app"
    "Grid-Status.app"
)

for app in "${apps[@]}"; do
    if [ -d "$APPS_DIR/$app" ]; then
        echo "📲 Installing $app..."
        
        # Remove existing app if present
        rm -rf "$DESKTOP/$app" 2>/dev/null
        
        # Copy app to Desktop
        cp -R "$APPS_DIR/$app" "$DESKTOP/"
        
        # Remove quarantine attribute to avoid "unidentified developer" warning
        xattr -cr "$DESKTOP/$app"
        
        echo "   ✅ Installed"
    else
        echo "   ⚠️  $app not found"
    fi
done

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Installation Complete!                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "✨ Your Desktop now has 5 beautiful GridBot apps:"
echo ""
echo "   ⚡️  GridBot-Launcher.app - Control Center (Choose any tool)"
echo "   ⚡️  GridBot-Status.app   - Quick status check"
echo "   🔴  GridBot-Logs.app     - Live streaming logs"
echo "   📊  PM2-Monitor.app      - Process monitor"
echo "   📈  Grid-Status.app      - Grid loops & profits"
echo ""
echo "🎯 Just double-click any app to launch!"
echo ""
echo "💡 Tip: Drag apps to your Dock for even faster access"
echo ""

# Clear icon caches for immediate icon display
echo "🔄 Clearing icon caches..."
sudo rm -rf /Library/Caches/com.apple.iconservices.store 2>/dev/null
sudo find /private/var/folders/ -name "com.apple.dock.iconcache" -delete 2>/dev/null

# Refresh Dock and Finder
killall Dock 2>/dev/null
killall Finder 2>/dev/null

echo ""
echo "💡 Note: If icons don't appear immediately, run:"
echo "   ./fix-app-icons.command"
echo ""
echo "   Or simply log out and log back in."
echo ""

echo "Press any key to exit..."
read -n 1 -s
