#!/bin/bash
# ============================================================================
# GridBot Mac → Windows Sync Script (via LAN)
# ============================================================================
# 
# Syncs the GridBot project from Mac to Windows, creating a mirror while
# respecting OS-specific differences.
#
# Usage:
#   ./sync_to_windows.sh [windows-ip] [username]
#   ./sync_to_windows.sh 192.168.1.100 ssr
#
# Requirements:
#   - Windows machine accessible via LAN
#   - SMB sharing enabled on Windows D: drive
#   - Or SSH/SCP enabled on Windows
#
# ============================================================================

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
MAC_PROJECT_DIR="/Users/ssr/Projects/WorkingBot"
WINDOWS_PROJECT_DIR="D:/Projects/WorkingBot"
MOUNT_POINT="/Volumes/WindowsBot"

# Get Windows IP and username
WINDOWS_IP="${1:-}"
WINDOWS_USER="${2:-ssr}"

if [ -z "$WINDOWS_IP" ]; then
    echo -e "${RED}❌ Error: Windows IP address required${NC}"
    echo "Usage: ./sync_to_windows.sh [windows-ip] [username]"
    echo "Example: ./sync_to_windows.sh 192.168.1.100 ssr"
    exit 1
fi

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║          GridBot Mac → Windows Sync (via LAN)                  ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Mac Project:${NC} $MAC_PROJECT_DIR"
echo -e "${BLUE}Windows Target:${NC} $WINDOWS_PROJECT_DIR"
echo -e "${BLUE}Windows IP:${NC} $WINDOWS_IP"
echo -e "${BLUE}Windows User:${NC} $WINDOWS_USER"
echo ""

# Change to project directory
cd "$MAC_PROJECT_DIR" || exit 1

# ============================================================================
# STEP 1: Determine Sync Method
# ============================================================================

echo -e "${CYAN}Step 1: Determining sync method...${NC}"

SYNC_METHOD=""

# Check if SSH is available
if command -v ssh &> /dev/null; then
    if ssh -o ConnectTimeout=2 -o BatchMode=yes "${WINDOWS_USER}@${WINDOWS_IP}" exit 2>/dev/null; then
        SYNC_METHOD="ssh"
        echo -e "${GREEN}✅ SSH connection available${NC}"
    fi
fi

# Check if SMB mount is possible
if [ -z "$SYNC_METHOD" ]; then
    echo -e "${YELLOW}⚠️  SSH not available, will try SMB mounting${NC}"
    SYNC_METHOD="smb"
fi

echo ""

# ============================================================================
# STEP 2: Core Bot Files (Must Sync)
# ============================================================================

echo -e "${CYAN}Step 2: Preparing core bot files list...${NC}"

# Core bot brain files (critical for trading logic)
CORE_FILES=(
    "bot/run.py"
    "bot/strategy/gridbot.py"
    "bot/strategy/modules/grid_calculator.py"
    "bot/strategy/modules/position_manager.py"
    "bot/strategy/modules/fill_detector.py"
    "bot/strategy/modules/order_manager.py"
    "bot/strategy/modules/reconciliation.py"
    "bot/strategy/modules/volatility_handler.py"
    "bot/strategy/modules/websocket_handler.py"
    "bot/strategy/handlers/long_handler.py"
    "bot/strategy/handlers/short_handler.py"
    "bot/api/delta_client.py"
    "bot/delta_websocket/ws_manager.py"
    "bot/guardian/guardian_bot.py"
    "bot/heartbeat/monitor.py"
    "bot/volatility/iv_rv_tracker.py"
    "bot/config/config_manager_core.py"
    "bot/safety/loss_limits.py"
    "bot/safety/blocker_tracker.py"
    "bot/safety/single_instance_lock.py"
)

# Monitoring system files
MONITORING_FILES=(
    "bot/monitoring/price_health.py"
    "bot/monitoring/pre_order_logger.py"
    "bot/monitoring/tp_verification.py"
    "bot/monitoring/anomaly_detection.py"
    "bot/monitoring/predictive_display.py"
    "bot/monitoring/data_writer.py"
)

# Configuration files (OS-independent)
CONFIG_FILES=(
    "grid_config.env"
    # Note: secrets/api_keys.env should be synced manually for security
)

# Documentation files
DOC_FILES=(
    "AI_CONTEXT.md"
    "BOT_BRAIN_ARCHITECTURE.md"
    "AI_CRITICAL_RULES.md"
    "BOT_STRUCTURE.md"
    "START_HERE.md"
    "USER_MANUAL.md"
    "PM2_COMPLETE_SYSTEM.md"
)

# All core files combined
ALL_CORE_FILES=("${CORE_FILES[@]}" "${MONITORING_FILES[@]}" "${CONFIG_FILES[@]}" "${DOC_FILES[@]}")

echo -e "${GREEN}✅ Prepared ${#ALL_CORE_FILES[@]} core files for sync${NC}"
echo ""

# ============================================================================
# STEP 3: WebUI Files (Separate - May Differ)
# ============================================================================

echo -e "${CYAN}Step 3: Preparing WebUI files list...${NC}"

WEBUI_BACKEND_FILES=(
    "webui/backend/app.py"
    "webui/backend/routes/*.py"
    "webui/backend/utils/*.py"
)

WEBUI_FRONTEND_FILES=(
    "webui/frontend/src/**/*.js"
    "webui/frontend/src/**/*.jsx"
    "webui/frontend/public/**/*"
)

echo -e "${YELLOW}⚠️  WebUI files may have OS-specific differences${NC}"
echo -e "${YELLOW}   Backend: Check file paths, port bindings${NC}"
echo -e "${YELLOW}   Frontend: Should be identical (React)${NC}"
echo ""

# ============================================================================
# STEP 4: Files to EXCLUDE (OS-Specific)
# ============================================================================

echo -e "${CYAN}Step 4: Preparing exclusion list (OS-specific files)...${NC}"

EXCLUDE_PATTERNS=(
    "*.sh"                          # Mac shell scripts
    "*.plist"                       # Mac LaunchAgent files
    ".DS_Store"                     # Mac metadata
    "__pycache__/"                  # Python cache
    "*.pyc"                         # Compiled Python
    ".git/"                         # Git repo (use git pull on Windows)
    ".venv/"                        # Virtual environment
    "node_modules/"                 # NPM packages
    "bot/logs/*.log"                # Log files (machine-specific)
    ".heartbeat"                    # Runtime files
    ".guardian_health"              # Runtime files
    "*.pid"                         # Process ID files
    ".bot_instance*.lock"           # Lock files
    "runtime_state.json"            # Runtime state (machine-specific)
    "state.json"                    # Bot state (machine-specific)
    ".volatility_status.json"       # Runtime status
    "launchd/"                      # Mac service files
    "scripts/start_tmux_daemon.sh"  # Mac-specific
)

echo -e "${GREEN}✅ Prepared exclusion list (${#EXCLUDE_PATTERNS[@]} patterns)${NC}"
echo ""

# ============================================================================
# STEP 5: Sync Execution
# ============================================================================

echo -e "${CYAN}Step 5: Starting sync operation...${NC}"
echo ""

if [ "$SYNC_METHOD" = "ssh" ]; then
    echo -e "${GREEN}Using SSH/SCP method${NC}"
    echo ""
    
    # Create build exclusion string for rsync
    RSYNC_EXCLUDE=""
    for pattern in "${EXCLUDE_PATTERNS[@]}"; do
        RSYNC_EXCLUDE="$RSYNC_EXCLUDE --exclude='$pattern'"
    done
    
    # Use rsync over SSH (best method)
    echo -e "${BLUE}Syncing core bot files...${NC}"
    eval rsync -avz --progress \
        $RSYNC_EXCLUDE \
        "${MAC_PROJECT_DIR}/bot/" \
        "${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PROJECT_DIR}/bot/"
    
    echo ""
    echo -e "${BLUE}Syncing configuration files...${NC}"
    for file in "${CONFIG_FILES[@]}"; do
        scp "${MAC_PROJECT_DIR}/${file}" \
            "${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PROJECT_DIR}/${file}" 2>/dev/null || true
    done
    
    echo ""
    echo -e "${BLUE}Syncing documentation files...${NC}"
    for file in "${DOC_FILES[@]}"; do
        scp "${MAC_PROJECT_DIR}/${file}" \
            "${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PROJECT_DIR}/${file}" 2>/dev/null || true
    done
    
    echo ""
    echo -e "${BLUE}Syncing WebUI backend...${NC}"
    eval rsync -avz --progress \
        $RSYNC_EXCLUDE \
        "${MAC_PROJECT_DIR}/webui/backend/" \
        "${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PROJECT_DIR}/webui/backend/"
    
    echo -e "${GREEN}✅ SSH sync completed${NC}"
    
elif [ "$SYNC_METHOD" = "smb" ]; then
    echo -e "${GREEN}Using SMB mount method${NC}"
    echo ""
    
    # Mount Windows share
    echo -e "${BLUE}Mounting Windows D: drive...${NC}"
    mkdir -p "$MOUNT_POINT"
    
    if mount_smbfs "//${WINDOWS_USER}@${WINDOWS_IP}/D$" "$MOUNT_POINT" 2>/dev/null; then
        echo -e "${GREEN}✅ Mounted: $MOUNT_POINT${NC}"
        echo ""
        
        # Sync core bot files
        echo -e "${BLUE}Syncing core bot files...${NC}"
        rsync -av --progress \
            $(printf -- '--exclude=%s ' "${EXCLUDE_PATTERNS[@]}") \
            "${MAC_PROJECT_DIR}/bot/" \
            "${MOUNT_POINT}/Projects/WorkingBot/bot/"
        
        # Sync config files
        echo -e "${BLUE}Syncing configuration files...${NC}"
        for file in "${CONFIG_FILES[@]}"; do
            cp "${MAC_PROJECT_DIR}/${file}" \
               "${MOUNT_POINT}/Projects/WorkingBot/${file}" 2>/dev/null || true
        done
        
        # Sync documentation
        echo -e "${BLUE}Syncing documentation files...${NC}"
        for file in "${DOC_FILES[@]}"; do
            cp "${MAC_PROJECT_DIR}/${file}" \
               "${MOUNT_POINT}/Projects/WorkingBot/${file}" 2>/dev/null || true
        done
        
        # Sync WebUI backend
        echo -e "${BLUE}Syncing WebUI backend...${NC}"
        rsync -av --progress \
            $(printf -- '--exclude=%s ' "${EXCLUDE_PATTERNS[@]}") \
            "${MAC_PROJECT_DIR}/webui/backend/" \
            "${MOUNT_POINT}/Projects/WorkingBot/webui/backend/"
        
        # Unmount
        echo ""
        echo -e "${BLUE}Unmounting...${NC}"
        umount "$MOUNT_POINT" 2>/dev/null || diskutil unmount "$MOUNT_POINT"
        echo -e "${GREEN}✅ SMB sync completed${NC}"
    else
        echo -e "${RED}❌ Failed to mount Windows share${NC}"
        echo -e "${YELLOW}Make sure SMB sharing is enabled on Windows D: drive${NC}"
        exit 1
    fi
fi

echo ""

# ============================================================================
# STEP 6: Post-Sync Instructions
# ============================================================================

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                    Sync Complete! ✅                            ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✅ Core bot files synced${NC}"
echo -e "${GREEN}✅ Monitoring system synced${NC}"
echo -e "${GREEN}✅ Configuration files synced${NC}"
echo -e "${GREEN}✅ Documentation synced${NC}"
echo -e "${GREEN}✅ WebUI backend synced${NC}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Manual steps required on Windows:${NC}"
echo ""
echo -e "${CYAN}1. Sync API Keys (SECURITY - Do manually):${NC}"
echo "   Copy: secrets/api_keys.env to Windows"
echo "   Location: D:\\Projects\\WorkingBot\\secrets\\api_keys.env"
echo ""
echo -e "${CYAN}2. Install Python dependencies:${NC}"
echo "   cd D:\\Projects\\WorkingBot"
echo "   pip install -r requirements.txt"
echo ""
echo -e "${CYAN}3. Verify imports:${NC}"
echo "   python -c \"from bot.strategy.gridbot import GridBot; print('✅ OK')\""
echo ""
echo -e "${CYAN}4. Check configuration:${NC}"
echo "   python -c \"from bot.config.config_manager_core import load_config; print('✅ OK')\""
echo ""
echo -e "${CYAN}5. Create Windows-specific files:${NC}"
echo "   - Create start_bot.bat (Windows batch file)"
echo "   - Create stop_bot.bat"
echo "   - Update paths in grid_config.env if needed"
echo ""
echo -e "${CYAN}6. Test bot startup (dry run):${NC}"
echo "   set PYTHONPATH=D:\\Projects\\WorkingBot"
echo "   python bot\\run.py"
echo ""
echo -e "${BLUE}Files NOT synced (intentionally):${NC}"
echo "  - .sh scripts (Mac-specific)"
echo "  - .plist files (Mac LaunchAgent)"
echo "  - Log files (machine-specific)"
echo "  - Runtime state files (machine-specific)"
echo "  - Lock files"
echo "  - Git repository (use 'git pull' on Windows)"
echo ""
echo -e "${GREEN}For WebUI on Windows:${NC}"
echo "  - Backend should work as-is (Python/Flask)"
echo "  - Frontend may need: npm install && npm run build"
echo "  - Check port 5555 is available"
echo ""
echo -e "${CYAN}Documentation available on Windows:${NC}"
echo "  - AI_CONTEXT.md (complete system overview)"
echo "  - BOT_BRAIN_ARCHITECTURE.md (module connections)"
echo "  - START_HERE.md (quick start guide)"
echo ""
echo -e "${GREEN}Sync completed successfully! 🎉${NC}"
echo ""
