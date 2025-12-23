#!/bin/bash
# Uninstall GridBot Apps from Desktop

clear
echo "╔════════════════════════════════════════════════════════════╗"
echo "║          GridBot Apps Uninstaller                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

DESKTOP="$HOME/Desktop"

echo "🗑️  Removing GridBot apps from Desktop..."
echo ""

apps=(
    "GridBot-Launcher.app"
    "GridBot-Status.app"
    "GridBot-Logs.app"
    "PM2-Monitor.app"
    "Grid-Status.app"
)

for app in "${apps[@]}"; do
    if [ -d "$DESKTOP/$app" ]; then
        echo "   Removing $app..."
        rm -rf "$DESKTOP/$app"
        echo "   ✅ Removed"
    else
        echo "   ⚠️  $app not found (already removed)"
    fi
done

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Press any key to exit..."
read -n 1 -s
