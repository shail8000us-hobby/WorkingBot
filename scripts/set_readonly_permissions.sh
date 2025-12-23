#!/bin/bash

# Script to set production-locked files to read-only mode (444)
# This prevents accidental modifications

echo "🔒 Setting production-locked files to read-only mode..."
echo ""

FILES=(
    "bot/strategy/gbot_ws.py"
    "bot/delta_websocket/ws_manager.py"
    "bot/api/delta_client.py"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  Setting: $file"
        chmod 444 "$file"
        
        # Verify
        PERMS=$(ls -l "$file" | awk '{print $1}')
        if [[ "$PERMS" =~ ^-r--r--r-- ]]; then
            echo "    ✅ Now read-only: $PERMS"
        else
            echo "    ⚠️  Unexpected permissions: $PERMS"
        fi
    else
        echo "  ❌ File not found: $file"
    fi
done

echo ""
echo "✅ Files are now read-only (444)"
echo ""
echo "To edit these files:"
echo "  1. Make writable:  chmod 644 <file>"
echo "  2. Edit the file"
echo "  3. Test thoroughly"
echo "  4. Commit (will require Mac password)"
echo "  5. Set read-only:  chmod 444 <file>"
echo ""
echo "Or use sudo to edit directly:"
echo "  sudo vi <file>  (will prompt for password)"
echo ""

