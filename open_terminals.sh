#!/bin/bash
set -euo pipefail

# Resolve project root to the folder this script lives in
PROJECT="$(cd "$(dirname "$0")" && pwd)"

# Window A: start the bot
osascript <<OSA
tell application "Terminal"
    do script "cd '$PROJECT'; source .venv/bin/activate; bash dashboard/start.sh"
    set bounds of front window to {50, 50, 900, 800}
end tell
OSA

# Window B: live log tail
osascript <<OSA
tell application "Terminal"
    do script "cd '$PROJECT'; source .venv/bin/activate; tail -f bot/logs/bot.log"
    set bounds of front window to {920, 50, 1770, 800}
end tell
OSA

# Window C: hotwatch (auto-apply grid on save)
osascript <<OSA
tell application "Terminal"
    do script "cd '$PROJECT'; source .venv/bin/activate; bash dashboard/hotwatch_grid.sh"
    set bounds of front window to {50, 830, 900, 1400}
end tell
OSA

# Window D: periodic status
osascript <<OSA
tell application "Terminal"
    do script "cd '$PROJECT'; source .venv/bin/activate; while true; do bash dashboard/status.sh; sleep 15; done"
    set bounds of front window to {920, 830, 1770, 1400}
end tell
OSA
