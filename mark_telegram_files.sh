#!/bin/bash

# Mark Telegram files with colors
echo "🎨 Marking Telegram files with colors..."

# Color codes for Finder tags
# 2 = Orange, 3 = Red, 4 = Yellow, 5 = Blue, 6 = Purple, 7 = Green
ORANGE_TAG="0000000000000000000200000000000000000000000000000000000000000000"
GREEN_TAG="0000000000000000000700000000000000000000000000000000000000000000"
BLUE_TAG="0000000000000000000500000000000000000000000000000000000000000000"

# Mark frontend component (Green - UI component)
if [ -f "src/components/TelegramStatusPanel.js" ]; then
    echo "  🟢 Marking TelegramStatusPanel.js (Frontend Component)"
    xattr -w com.apple.FinderInfo "$GREEN_TAG" "src/components/TelegramStatusPanel.js" 2>/dev/null || echo "    Could not set color tag"
fi

# Mark documentation (Blue - Documentation)
if [ -f "TELEGRAM_WEBUI_FIXES.md" ]; then
    echo "  🔵 Marking TELEGRAM_WEBUI_FIXES.md (Documentation)"
    xattr -w com.apple.FinderInfo "$BLUE_TAG" "TELEGRAM_WEBUI_FIXES.md" 2>/dev/null || echo "    Could not set color tag"
fi

# Check for other Telegram files in parent directories
echo "  🔍 Searching for other Telegram files..."

# Check services directory
if [ -d "../services/notifications" ]; then
    if [ -f "../services/notifications/telegram_error_notifier.py" ]; then
        echo "  🟠 Marking telegram_error_notifier.py (Backend Service)"
        xattr -w com.apple.FinderInfo "$ORANGE_TAG" "../services/notifications/telegram_error_notifier.py" 2>/dev/null || echo "    Could not set color tag"
    fi
    
    if [ -f "../services/notifications/telegram_command_handler.py" ]; then
        echo "  🟠 Marking telegram_command_handler.py (Backend Service)"
        xattr -w com.apple.FinderInfo "$ORANGE_TAG" "../services/notifications/telegram_command_handler.py" 2>/dev/null || echo "    Could not set color tag"
    fi
fi

# Check bot directory
if [ -f "../bot/recon_telegram.py" ]; then
    echo "  🟠 Marking recon_telegram.py (Reconciliation Service)"
    xattr -w com.apple.FinderInfo "$ORANGE_TAG" "../bot/recon_telegram.py" 2>/dev/null || echo "    Could not set color tag"
fi

echo "✅ Telegram files marked with colors!"
echo ""
echo "Color Legend:"
echo "  🟢 Green: Frontend UI Components"
echo "  🟠 Orange: Backend Services"
echo "  🔵 Blue: Documentation"
