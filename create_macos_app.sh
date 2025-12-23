#!/bin/bash

# 🍎 CREATE MACOS APPLICATION BUNDLE
# This creates a .app file you can double-click to run

echo "🍎 Creating macOS Application Bundle..."

# Create app structure
mkdir -p "TradingBot.app/Contents/MacOS"
mkdir -p "TradingBot.app/Contents/Resources"

# Create Info.plist
cat > "TradingBot.app/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>trading_bot</string>
    <key>CFBundleIdentifier</key>
    <string>com.tradingbot.app</string>
    <key>CFBundleName</key>
    <string>Trading Bot</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
</dict>
</plist>
PLIST

# Create executable script
cat > "TradingBot.app/Contents/MacOS/trading_bot" << 'SCRIPT'
#!/bin/bash
cd "$(dirname "$0")/../../.."
exec ./start_bot_standalone.sh
SCRIPT

chmod +x "TradingBot.app/Contents/MacOS/trading_bot"

echo "✅ macOS App created: TradingBot.app"
echo "📱 Double-click TradingBot.app to run your bot!"
