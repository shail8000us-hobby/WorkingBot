#!/bin/bash
# PM2 GridBot - Live Log Monitoring Commands
# Quick reference for watching bot logs in real-time

# ============================================================================
# BASIC LOG WATCHING
# ============================================================================

# Watch all bots (combined output)
pm2 logs

# Watch specific bot
pm2 logs gridbot-live         # Live trading bot
pm2 logs gridbot-demo         # Demo bot
pm2 logs guardian-live        # Guardian (live mode)
pm2 logs guardian-demo        # Guardian (demo mode)
pm2 logs heartbeat-monitor    # Heartbeat monitor

# ============================================================================
# ADVANCED LOG VIEWING
# ============================================================================

# View last N lines without following
pm2 logs gridbot-live --lines 100 --nostream
pm2 logs guardian-live --lines 50 --nostream

# Raw output (no timestamps, no colors)
pm2 logs gridbot-live --raw

# Only errors
pm2 logs gridbot-live --err

# ============================================================================
# INTERACTIVE MONITORING
# ============================================================================

# Real-time dashboard (CPU, Memory, Logs)
pm2 monit

# Process status
pm2 status
pm2 list

# Detailed info for one bot
pm2 describe gridbot-live

# ============================================================================
# CUSTOM LOG MONITORING (our scripts)
# ============================================================================

# Interactive menu (auto-detects PM2)
./watch_bot_logs.sh

# Quick access
./watch_bot_logs.sh main        # Main trading bot
./watch_bot_logs.sh guardian    # Guardian bot
./watch_bot_logs.sh webui       # WebUI backend
./watch_bot_logs.sh all         # All bots in tmux multi-pane
./watch_bot_logs.sh errors      # Only errors
./watch_bot_logs.sh health      # Health checks

# ============================================================================
# PM2 BOT MANAGEMENT
# ============================================================================

# Start/Stop/Restart
./pm2_gridbot.sh start live     # Start live bot
./pm2_gridbot.sh stop live      # Stop live bot (graceful, 30s)
./pm2_gridbot.sh restart live   # Restart live bot
./pm2_gridbot.sh status         # Show status

# ============================================================================
# LOG MANAGEMENT
# ============================================================================

# Clear all PM2 logs
pm2 flush

# Or use our wrapper
./pm2_gridbot.sh flush

# Rotate logs manually
pm2 reloadLogs

# ============================================================================
# FILTERING LOGS
# ============================================================================

# Watch for specific patterns
pm2 logs gridbot-live | grep -E "FILL|ORDER|POSITION"
pm2 logs gridbot-live | grep -E "ERROR|WARNING|CRITICAL"
pm2 logs guardian-live | grep -E "RESTART|RECOVERY"

# ============================================================================
# MULTI-PANE VIEWING (tmux now installed!)
# ============================================================================

# Watch all bots in split panes
./watch_bot_logs.sh all

# Manual tmux setup:
tmux new-session -d -s botlogs "pm2 logs gridbot-live --raw"
tmux split-window -h -t botlogs "pm2 logs guardian-live --raw"
tmux split-window -v -t botlogs "tail -f logs/launchagent_webui.log"
tmux select-layout -t botlogs tiled
tmux attach-session -t botlogs

# Detach from tmux: Ctrl+B then D
# Reattach: tmux attach -t botlogs
# Kill session: tmux kill-session -t botlogs

# ============================================================================
# PM2 LOG FILE LOCATIONS
# ============================================================================

# PM2 stores logs in:
# ~/.pm2/logs/gridbot-live-out.log      # stdout
# ~/.pm2/logs/gridbot-live-error.log    # stderr
# ~/.pm2/logs/guardian-live-out.log     # stdout
# ~/.pm2/logs/guardian-live-error.log   # stderr

# View directly:
tail -f ~/.pm2/logs/gridbot-live-out.log
tail -f ~/.pm2/logs/gridbot-live-error.log

# ============================================================================
# TROUBLESHOOTING
# ============================================================================

# Bot not showing in pm2 list?
pm2 resurrect                   # Restore saved process list
./pm2_gridbot.sh start live     # Or start fresh

# Logs not showing?
pm2 reloadLogs                  # Reload log system
pm2 flush && pm2 restart all    # Clear and restart

# PM2 daemon issues?
pm2 kill                        # Kill PM2 daemon
pm2 resurrect                   # Restart with saved processes

# ============================================================================
# KEYBOARD SHORTCUTS (when watching logs)
# ============================================================================

# Ctrl+C          - Stop watching logs
# Ctrl+B then D   - Detach from tmux (if in multi-pane view)
# Ctrl+Z          - Suspend (not recommended, use Ctrl+C instead)
