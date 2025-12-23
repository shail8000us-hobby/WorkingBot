#!/bin/bash
# Start all 3 bots (Guardian, Monitor, Trading) in tmux

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                       ║${NC}"
echo -e "${GREEN}║   🚀 STARTING COMPLETE GRIDBOT SYSTEM (3 BOTS)                        ║${NC}"
echo -e "${GREEN}║                                                                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${RED}❌ tmux is not installed${NC}"
    echo ""
    echo "To install tmux:"
    echo "  macOS:  brew install tmux"
    echo "  Linux:  sudo apt-get install tmux"
    echo ""
    exit 1
fi

SESSION_NAME="gridbot"

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  tmux session '$SESSION_NAME' already exists${NC}"
    echo ""
    echo "Options:"
    echo "  1. Attach to existing session: tmux attach -t $SESSION_NAME"
    echo "  2. Kill existing session: tmux kill-session -t $SESSION_NAME"
    echo ""
    exit 1
fi

echo -e "${GREEN}🔄 Creating tmux session with 3 panes...${NC}"
echo ""

# Create new tmux session with 3 horizontal panes
tmux new-session -d -s "$SESSION_NAME" -n "GridBot"

# Split into 3 panes
# Pane 0: Guardian (top)
# Pane 1: Heartbeat Monitor (middle)
# Pane 2: Trading Bot (bottom)

# Split horizontally (creates pane 1)
tmux split-window -h -t "$SESSION_NAME:0"

# Split pane 1 horizontally (creates pane 2)
tmux split-window -h -t "$SESSION_NAME:0.1"

# Adjust pane layout to be even
tmux select-layout -t "$SESSION_NAME:0" even-horizontal

# ────────────────────────────────────────────────────────────────────
# PANE 0: Guardian Bot
# ────────────────────────────────────────────────────────────────────
tmux send-keys -t "$SESSION_NAME:0.0" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "clear" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo '╔═══════════════════════════════════════╗'" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo '║                                       ║'" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo '║   🛡️  GUARDIAN BOT                    ║'" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo '║                                       ║'" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo '╚═══════════════════════════════════════╝'" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo ''" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo 'Starting Guardian Bot...'" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "sleep 2" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "python3 -m bot.guardian.guardian_bot" C-m

# ────────────────────────────────────────────────────────────────────
# PANE 1: Heartbeat Monitor
# ────────────────────────────────────────────────────────────────────
tmux send-keys -t "$SESSION_NAME:0.1" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "clear" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo '╔═══════════════════════════════════════╗'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo '║                                       ║'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo '║   💓 HEARTBEAT MONITOR                ║'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo '║                                       ║'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo '╚═══════════════════════════════════════╝'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo ''" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo 'Waiting for Trading Bot to start...'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "sleep 5" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo 'Starting Heartbeat Monitor...'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "sleep 1" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "python3 -m bot.heartbeat.monitor" C-m

# ────────────────────────────────────────────────────────────────────
# PANE 2: Trading Bot
# ────────────────────────────────────────────────────────────────────
tmux send-keys -t "$SESSION_NAME:0.2" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "clear" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "echo '╔═══════════════════════════════════════╗'" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "echo '║                                       ║'" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "echo '║   🤖 TRADING BOT                      ║'" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "echo '║                                       ║'" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "echo '╚═══════════════════════════════════════╝'" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "echo ''" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "echo 'Starting Trading Bot...'" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "sleep 3" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "python3 -m bot.run" C-m

# Success message
echo -e "${GREEN}✅ tmux session created successfully!${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ALL 3 BOTS STARTING IN TMUX SESSION${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "📊 Layout:"
echo "  ┌─────────────┬──────────────┬──────────────┐"
echo "  │   Guardian  │   Monitor    │  Trading Bot │"
echo "  │      🛡️      │      💓       │      🤖      │"
echo "  └─────────────┴──────────────┴──────────────┘"
echo ""
echo "To attach to session:"
echo -e "  ${BLUE}tmux attach -t $SESSION_NAME${NC}"
echo ""
echo "Keyboard shortcuts (inside tmux):"
echo "  Ctrl+B then ←/→  Switch between panes"
echo "  Ctrl+B then [    Scroll mode (q to exit)"
echo "  Ctrl+B then d    Detach (bots keep running)"
echo "  Ctrl+C           Stop bot in current pane"
echo ""
echo "To kill all:"
echo "  tmux kill-session -t $SESSION_NAME"
echo ""
echo -e "${YELLOW}Attaching to session in 3 seconds...${NC}"
sleep 3

# Attach to session
tmux attach -t "$SESSION_NAME"

