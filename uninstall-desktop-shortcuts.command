#!/bin/bash
# Remove GridBot Desktop Shortcuts
# Run this to clean up desktop shortcuts

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         GridBot Desktop Shortcuts Uninstaller                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

DESKTOP="$HOME/Desktop"

echo "Removing shortcuts from Desktop..."
echo ""

# Remove shortcuts
if [ -L "$DESKTOP/⚡ GridBot Status.command" ]; then
    rm "$DESKTOP/⚡ GridBot Status.command"
    echo "✅ Removed: ⚡ GridBot Status.command"
fi

if [ -L "$DESKTOP/🔴 View Bot Logs.command" ]; then
    rm "$DESKTOP/🔴 View Bot Logs.command"
    echo "✅ Removed: 🔴 View Bot Logs.command"
fi

if [ -L "$DESKTOP/📊 PM2 Monitor.command" ]; then
    rm "$DESKTOP/📊 PM2 Monitor.command"
    echo "✅ Removed: 📊 PM2 Monitor.command"
fi

if [ -L "$DESKTOP/📈 Grid Status.command" ]; then
    rm "$DESKTOP/📈 Grid Status.command"
    echo "✅ Removed: 📈 Grid Status.command"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "✅ Uninstallation complete!"
echo ""
echo "All GridBot desktop shortcuts have been removed."
echo ""
echo "To reinstall, double-click: install-desktop-shortcuts.command"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Press any key to exit..."
read -n 1
