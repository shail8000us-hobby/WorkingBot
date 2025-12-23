#!/bin/bash

# 🖥️ CREATE DESKTOP SHORTCUT
# This creates a desktop icon you can double-click

echo "🖥️ Creating Desktop Shortcut..."

# Create desktop shortcut
cat > ~/Desktop/TradingBot.command << 'SHORTCUT'
#!/bin/bash
cd "/Users/shailendrasinghrajawat/Projects/WorkingBot"
open -a Terminal "./start_bot_standalone.sh"
SHORTCUT

chmod +x ~/Desktop/TradingBot.command

echo "✅ Desktop shortcut created!"
echo "🖱️ Double-click 'TradingBot.command' on your desktop to run the bot"
