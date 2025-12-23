#!/bin/bash
# Desktop Shortcuts Installer for GridBot
# Run this once to create convenient desktop shortcuts

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         GridBot Desktop Shortcuts Installer                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP="$HOME/Desktop"

echo "Installing shortcuts to Desktop..."
echo ""

# Create shortcuts
ln -sf "$SCRIPT_DIR/bot-status.command" "$DESKTOP/⚡ GridBot Status.command"
echo "✅ Created: ⚡ GridBot Status.command"

ln -sf "$SCRIPT_DIR/view-logs.command" "$DESKTOP/🔴 View Bot Logs.command"
echo "✅ Created: 🔴 View Bot Logs.command"

ln -sf "$SCRIPT_DIR/pm2-monitor.command" "$DESKTOP/📊 PM2 Monitor.command"
echo "✅ Created: 📊 PM2 Monitor.command"

ln -sf "$SCRIPT_DIR/view-grid-status.command" "$DESKTOP/📈 Grid Status.command"
echo "✅ Created: 📈 Grid Status.command"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "✅ Installation complete!"
echo ""
echo "You can now find 4 shortcuts on your Desktop:"
echo "  ⚡ GridBot Status  - Quick status check"
echo "  🔴 View Bot Logs  - Live streaming logs"
echo "  📊 PM2 Monitor    - System resource monitor"
echo "  📈 Grid Status    - Loops & profit history"
echo ""
echo "Simply double-click any shortcut to open!"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Press any key to exit..."
read -n 1
