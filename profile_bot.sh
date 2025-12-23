#!/bin/bash
# Bot Profiling Utility - Quick Performance Analysis
# Created: Nov 7, 2025

echo "🔬 Bot Profiling Utility"
echo "======================="
echo ""

# Add Python bin to PATH
export PATH="/Users/ssr/Library/Python/3.9/bin:$PATH"

# Get bot PID
BOT_PID=$(pgrep -f "gridbot-live" | head -1)

if [ -z "$BOT_PID" ]; then
    echo "❌ Bot is not running!"
    echo "Start the bot first: pm2 start gridbot-live"
    exit 1
fi

echo "✅ Found bot process: PID $BOT_PID"
echo ""

# Menu
echo "Select profiling mode:"
echo "1) Quick flame graph (30 seconds)"
echo "2) Real-time top (live CPU usage)"
echo "3) Extended analysis (2 minutes)"
echo "4) Profile next bot restart (viztracer)"
echo ""
read -p "Choice [1-4]: " choice

case $choice in
    1)
        echo "📊 Recording flame graph for 30 seconds..."
        sudo /Users/ssr/Library/Python/3.9/bin/py-spy record \
            -o ~/Projects/WorkingBot/analysis/flame_$(date +%Y%m%d_%H%M%S).svg \
            --pid $BOT_PID \
            --duration 30 \
            --rate 100
        echo "✅ Flame graph saved to: ~/Projects/WorkingBot/analysis/"
        echo "Open in browser to analyze performance hotspots"
        ;;
    2)
        echo "📈 Starting real-time profiler (Ctrl+C to exit)..."
        sudo /Users/ssr/Library/Python/3.9/bin/py-spy top --pid $BOT_PID
        ;;
    3)
        echo "📊 Recording extended analysis (2 minutes)..."
        sudo /Users/ssr/Library/Python/3.9/bin/py-spy record \
            -o ~/Projects/WorkingBot/analysis/extended_$(date +%Y%m%d_%H%M%S).svg \
            --pid $BOT_PID \
            --duration 120 \
            --rate 100 \
            --subprocesses
        echo "✅ Analysis complete!"
        ;;
    4)
        echo "📝 To profile with viztracer, restart bot with:"
        echo ""
        echo "  pm2 stop gridbot-live"
        echo "  /Users/ssr/Library/Python/3.9/bin/viztracer --log_async --log_multithread --output_file ~/Projects/WorkingBot/analysis/trace_$(date +%Y%m%d_%H%M%S).json bot_launcher.py"
        echo ""
        echo "Then open the JSON file in browser with:"
        echo "  /Users/ssr/Library/Python/3.9/bin/viztracer --open trace_*.json"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac
