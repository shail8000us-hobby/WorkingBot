#!/bin/bash
# Fix GridBot App Icons - Force macOS to Recognize Custom Icons

clear
echo "╔════════════════════════════════════════════════════════════╗"
echo "║          GridBot Icon Fixer                                ║"
echo "║          Force macOS to recognize custom app icons         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

echo "🔧 Fixing icon display issues..."
echo ""

# Step 1: Touch all apps to update modification time
echo "1️⃣  Updating app timestamps..."
touch ~/Desktop/GridBot-*.app 2>/dev/null
touch ~/Desktop/PM2-Monitor.app 2>/dev/null
touch ~/Desktop/Grid-Status.app 2>/dev/null
echo "   ✅ Done"

# Step 2: Remove extended attributes
echo "2️⃣  Removing quarantine attributes..."
xattr -cr ~/Desktop/GridBot-*.app 2>/dev/null
xattr -cr ~/Desktop/PM2-Monitor.app 2>/dev/null
xattr -cr ~/Desktop/Grid-Status.app 2>/dev/null
echo "   ✅ Done"

# Step 3: Clear icon caches
echo "3️⃣  Clearing icon caches (requires sudo)..."
sudo rm -rf /Library/Caches/com.apple.iconservices.store 2>/dev/null
sudo find /private/var/folders/ -name "com.apple.dock.iconcache" -delete 2>/dev/null
sudo find /private/var/folders/ -name "com.apple.iconservices" -exec rm -rf {} \; 2>/dev/null
echo "   ✅ Done"

# Step 4: Restart Finder and Dock
echo "4️⃣  Restarting Finder and Dock..."
killall Finder 2>/dev/null
killall Dock 2>/dev/null
echo "   ✅ Done"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Fix Complete!                           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "✨ Icons should now display correctly!"
echo ""
echo "💡 If icons still don't show:"
echo "   Option 1: Log out and log back in (most reliable)"
echo "   Option 2: Restart your Mac"
echo "   Option 3: Wait 1-2 minutes for icon cache to rebuild"
echo ""

# Open Desktop to show results
sleep 2
open ~/Desktop

echo "Press any key to exit..."
read -n 1 -s
