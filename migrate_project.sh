#!/bin/bash
#
# Migrate WorkingBot from ~/Documents to ~/Projects
# This fixes macOS permission issues with LaunchAgent serving files from Documents folder
#

set -e  # Exit on error

echo "=========================================="
echo "🚚 WorkingBot Project Migration"
echo "=========================================="
echo ""
echo "From: ~/Projects/WorkingBot"
echo "To:   ~/Projects/WorkingBot"
echo ""
echo "This will:"
echo "  1. Stop all running services"
echo "  2. Move the project directory"
echo "  3. Update LaunchAgent configurations"
echo "  4. Restart services"
echo ""
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Migration cancelled"
    exit 1
fi

echo ""
echo "Step 1/6: Stopping services..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Stop WebUI
if launchctl list | grep -q com.gridbot.webui; then
    echo "  🛑 Stopping WebUI..."
    launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist 2>/dev/null || true
fi

# Stop tmux control daemon
if launchctl list | grep -q com.gridbot.tmuxcontrol; then
    echo "  🛑 Stopping tmux control daemon..."
    launchctl unload ~/Library/LaunchAgents/com.gridbot.tmuxcontrol.plist 2>/dev/null || true
fi

# Stop tmux session
echo "  🛑 Stopping tmux session..."
tmux -S ~/.tmux-gridbot/default kill-session -t gridbot 2>/dev/null || echo "     (no session running)"

sleep 2

echo ""
echo "Step 2/6: Creating new location..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
mkdir -p ~/Projects
echo "  ✅ Created ~/Projects directory"

echo ""
echo "Step 3/6: Moving project..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -d ~/Projects/WorkingBot ]; then
    echo "  ⚠️  ~/Projects/WorkingBot already exists!"
    read -p "  Delete existing and continue? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf ~/Projects/WorkingBot
        echo "  🗑️  Removed existing directory"
    else
        echo "❌ Migration cancelled"
        exit 1
    fi
fi

echo "  📦 Moving ~/Projects/WorkingBot → ~/Projects/WorkingBot"
mv ~/Projects/WorkingBot ~/Projects/WorkingBot
echo "  ✅ Project moved successfully"

echo ""
echo "Step 4/6: Updating LaunchAgent configurations..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Update WebUI LaunchAgent
if [ -f ~/Library/LaunchAgents/com.gridbot.webui.plist ]; then
    echo "  📝 Updating com.gridbot.webui.plist..."
    sed -i '' 's|Projects/WorkingBot|Projects/WorkingBot|g' ~/Library/LaunchAgents/com.gridbot.webui.plist
    echo "  ✅ WebUI LaunchAgent updated"
fi

# Update tmux control LaunchAgent
if [ -f ~/Library/LaunchAgents/com.gridbot.tmuxcontrol.plist ]; then
    echo "  📝 Updating com.gridbot.tmuxcontrol.plist..."
    sed -i '' 's|Projects/WorkingBot|Projects/WorkingBot|g' ~/Library/LaunchAgents/com.gridbot.tmuxcontrol.plist
    echo "  ✅ tmux control LaunchAgent updated"
fi

# Update any other gridbot LaunchAgents
for plist in ~/Library/LaunchAgents/com.gridbot.*.plist; do
    if [ -f "$plist" ]; then
        filename=$(basename "$plist")
        if grep -q "Projects/WorkingBot" "$plist" 2>/dev/null; then
            echo "  📝 Updating $filename..."
            sed -i '' 's|Projects/WorkingBot|Projects/WorkingBot|g' "$plist"
            echo "  ✅ $filename updated"
        fi
    fi
done

echo ""
echo "Step 5/6: Clearing macOS extended attributes..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -d ~/Projects/WorkingBot/webui/frontend/build ]; then
    echo "  🧹 Clearing attributes from frontend build..."
    xattr -cr ~/Projects/WorkingBot/webui/frontend/build 2>/dev/null || true
    echo "  ✅ Extended attributes cleared"
fi

echo ""
echo "Step 6/6: Restarting services..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Reload WebUI
if [ -f ~/Library/LaunchAgents/com.gridbot.webui.plist ]; then
    echo "  🚀 Starting WebUI..."
    launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist
    sleep 2
    if launchctl list | grep -q com.gridbot.webui; then
        echo "  ✅ WebUI started (PID: $(launchctl list | grep com.gridbot.webui | awk '{print $1}'))"
    else
        echo "  ⚠️  WebUI may need manual start"
    fi
fi

# Reload tmux control daemon
if [ -f ~/Library/LaunchAgents/com.gridbot.tmuxcontrol.plist ]; then
    echo "  🚀 Starting tmux control daemon..."
    launchctl load ~/Library/LaunchAgents/com.gridbot.tmuxcontrol.plist
    sleep 2
    if launchctl list | grep -q com.gridbot.tmuxcontrol; then
        echo "  ✅ tmux control daemon started (PID: $(launchctl list | grep com.gridbot.tmuxcontrol | awk '{print $1}'))"
    else
        echo "  ⚠️  tmux control daemon may need manual start"
    fi
fi

echo ""
echo "=========================================="
echo "✅ Migration Complete!"
echo "=========================================="
echo ""
echo "New location: ~/Projects/WorkingBot"
echo ""
echo "Verification:"
sleep 3

# Test WebUI health
echo "  🔍 Testing WebUI..."
if curl -s http://localhost:5555/api/health > /dev/null 2>&1; then
    echo "  ✅ WebUI is healthy: http://localhost:5555"
else
    echo "  ⚠️  WebUI not responding (may need a moment to start)"
fi

echo ""
echo "Next steps:"
echo "  1. Update your terminal to use new path:"
echo "     cd ~/Projects/WorkingBot"
echo ""
echo "  2. Test the bots via WebUI or tmux:"
echo "     tmux -S ~/.tmux-gridbot/default attach -t gridbot"
echo ""
echo "  3. No more permission errors! 🎉"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Old ~/Projects/WorkingBot location is now deleted"
echo "All services are pointing to ~/Projects/WorkingBot"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
