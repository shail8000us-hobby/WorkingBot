#!/bin/bash

# Script to apply red color tags to production-locked files in macOS Finder
# Red tag indicates: PRODUCTION-LOCKED - DO NOT MODIFY WITHOUT APPROVAL

echo "🎨 Applying red color tags to production-locked files..."

FILES=(
    "bot/strategy/gbot_ws.py"
    "bot/delta_websocket/ws_manager.py"
    "bot/api/delta_client.py"
)

# Method 1: Try using osascript (AppleScript)
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  Tagging: $file"
        
        # Use AppleScript to set red label (6 = Red in macOS)
        osascript -e "tell application \"Finder\"" \
                  -e "set theFile to POSIX file \"$(pwd)/$file\" as alias" \
                  -e "set label index of theFile to 6" \
                  -e "end tell" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "    ✅ Red tag applied"
        else
            echo "    ⚠️  Could not apply tag (may need Finder permissions)"
        fi
    else
        echo "  ❌ File not found: $file"
    fi
done

echo ""
echo "✅ Color tagging complete!"
echo ""
echo "To view tagged files:"
echo "  1. Open Finder"
echo "  2. Navigate to: $(pwd)"
echo "  3. Look for red tags on the files"
echo ""
echo "Note: You may need to grant terminal access to control Finder"
echo "      Go to: System Settings → Privacy & Security → Automation"

