#!/bin/bash
# Quick reference printed when starting bot in tmux

cat << 'EOF'

╔════════════════════════════════════════════════════════════════════════╗
║                   🤖 GridBot Tmux Quick Reference                      ║
╔════════════════════════════════════════════════════════════════════════╗

📍 CURRENT SESSION: Use `tmux attach -t gridbot` to reconnect

⚠️  IMPORTANT: How to Stop the Bot Safely
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ SAFE METHODS (cancel orders before stopping):

  1. From INSIDE tmux:
     Press: Ctrl+C
     → Bot receives SIGINT
     → Cleanup runs (30s max)
     → Orders cancelled ✓

  2. From OUTSIDE tmux:
     Run: ./tmux_stop_bot.sh
     → Sends Ctrl+C to bot
     → Waits for cleanup
     → Verifies completion ✓

  3. Using bot_stopper:
     Run: python3 bot_stopper.py
     → Graceful shutdown
     → 30s timeout ✓

❌ DANGEROUS METHODS (DO NOT USE):

  • tmux kill-server        → Sends SIGKILL, no cleanup!
  • kill -9 <pid>           → Force kill, orders NOT cancelled!
  • Closing terminal window → Unreliable cleanup

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔧 Tmux Commands:

  List sessions:    tmux list-sessions
  Attach:           tmux attach -t gridbot
  Detach:           Ctrl+B then D
  New window:       Ctrl+B then C
  Switch window:    Ctrl+B then 0-9
  Scroll mode:      Ctrl+B then [  (q to exit)
  Reload config:    Ctrl+B then R

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Monitoring:

  Bot logs:         tail -f reports/bot.log
  Check status:     python3 bot_stopper.py --check-only
  Open orders:      python3 cancel_pending_orders.py (shows orders)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Tips:

  • Mouse scrolling enabled! Just scroll normally
  • 50,000 lines of scrollback available
  • Always wait for "GRACEFUL SHUTDOWN" message in logs
  • Check logs if bot stops: grep "GRACEFUL SHUTDOWN" reports/bot.log

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 Emergency:

  If bot is stuck:         python3 bot_stopper.py --force
  If orders not cancelled: python3 cancel_pending_orders.py
  WebUI emergency:         http://localhost:5555 → Emergency Controls

╚════════════════════════════════════════════════════════════════════════╝

EOF
