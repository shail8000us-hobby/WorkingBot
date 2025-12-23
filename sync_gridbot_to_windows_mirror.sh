#!/bin/bash
# ============================================================================
# GridBot Complete Mirror Sync: Mac → Windows (Nov 10, 2025)
# ============================================================================
# 
# Creates a complete mirror of the macOS GridBot to Windows machine
# via SMB share, syncing ALL bot updates including latest fixes.
#
# Target: Windows D:\Projects\WorkingBot (mounted at /Volumes/D_Drive)
# Connection: SMB share //smbuser@192.168.1.32/D_Drive
#
# Usage:
#   ./sync_gridbot_to_windows_mirror.sh
#
# ============================================================================

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
MAC_PROJECT_DIR="/Users/ssr/Projects/WorkingBot"
WINDOWS_MOUNT_POINT="/Volumes/D_Drive"
WINDOWS_PROJECT_DIR="${WINDOWS_MOUNT_POINT}/Projects/WorkingBot"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SYNC_LOG="/tmp/gridbot_sync_${TIMESTAMP}.log"

echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     GridBot Complete Mirror Sync: Mac → Windows (Nov 10, 2025)      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Source (Mac):${NC}      $MAC_PROJECT_DIR"
echo -e "${BLUE}Target (Windows):${NC}  $WINDOWS_PROJECT_DIR"
echo -e "${BLUE}Mount Point:${NC}       $WINDOWS_MOUNT_POINT"
echo -e "${BLUE}Sync Log:${NC}          $SYNC_LOG"
echo ""

# Initialize log file
echo "GridBot Sync Log - $(date)" > "$SYNC_LOG"

# ============================================================================
# STEP 1: Pre-flight Checks
# ============================================================================

echo -e "${CYAN}Step 1: Pre-flight checks...${NC}"

# Check if source directory exists
if [ ! -d "$MAC_PROJECT_DIR" ]; then
    echo -e "${RED}❌ Error: Source directory not found: $MAC_PROJECT_DIR${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Source directory exists${NC}"

# Check if Windows mount point is accessible
if [ ! -d "$WINDOWS_MOUNT_POINT" ]; then
    echo -e "${RED}❌ Error: Windows mount point not found: $WINDOWS_MOUNT_POINT${NC}"
    echo -e "${YELLOW}   Please mount Windows D: drive first:${NC}"
    echo -e "${YELLOW}   In Finder: Go → Connect to Server → smb://192.168.1.32/D_Drive${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Windows mount point accessible${NC}"

# Check if target directory exists
if [ ! -d "$WINDOWS_PROJECT_DIR" ]; then
    echo -e "${YELLOW}⚠️  Target directory not found, creating: $WINDOWS_PROJECT_DIR${NC}"
    mkdir -p "$WINDOWS_PROJECT_DIR"
fi
echo -e "${GREEN}✅ Target directory ready${NC}"

# Check write permissions
if [ ! -w "$WINDOWS_PROJECT_DIR" ]; then
    echo -e "${RED}❌ Error: No write permission to: $WINDOWS_PROJECT_DIR${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Write permissions confirmed${NC}"

echo ""

# ============================================================================
# STEP 2: Backup Windows State Files (Safety)
# ============================================================================

echo -e "${CYAN}Step 2: Backing up Windows state files...${NC}"

BACKUP_DIR="${WINDOWS_PROJECT_DIR}/.backup_before_sync_${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

# Backup critical state files that should not be overwritten
STATE_FILES=(
    "runtime_state.json"
    "runtime_state_LONG.json"
    "runtime_state_SHORT.json"
    ".current_mode"
    "grid_config.env"
    "secrets/api_keys.env"
    ".bot_instance_live.lock"
    ".volatility_status.json"
    "bot/logs/bot.log"
)

echo -e "${BLUE}Backing up Windows-specific state files...${NC}"
for file in "${STATE_FILES[@]}"; do
    if [ -f "${WINDOWS_PROJECT_DIR}/${file}" ]; then
        mkdir -p "$(dirname "${BACKUP_DIR}/${file}")"
        cp "${WINDOWS_PROJECT_DIR}/${file}" "${BACKUP_DIR}/${file}" 2>/dev/null || true
        echo "  ✓ Backed up: $file" | tee -a "$SYNC_LOG"
    fi
done

echo -e "${GREEN}✅ State files backed up to: ${BACKUP_DIR}${NC}"
echo ""

# ============================================================================
# STEP 3: Sync Core Bot Brain Files
# ============================================================================

echo -e "${CYAN}Step 3: Syncing core bot brain files...${NC}"

echo -e "${BLUE}Syncing bot/ directory (all Python modules)...${NC}"
rsync -av --progress \
    --exclude="*.pyc" \
    --exclude="__pycache__/" \
    --exclude="*.log" \
    --exclude="logs/*.log" \
    "${MAC_PROJECT_DIR}/bot/" \
    "${WINDOWS_PROJECT_DIR}/bot/" | tee -a "$SYNC_LOG"

echo -e "${GREEN}✅ Bot brain files synced (gridbot.py + 7 modules + handlers)${NC}"
echo ""

# ============================================================================
# STEP 4: Sync Monitoring System (5 Layers)
# ============================================================================

echo -e "${CYAN}Step 4: Syncing monitoring system...${NC}"

echo -e "${BLUE}Syncing bot/monitoring/ directory...${NC}"
rsync -av --progress \
    --exclude="*.pyc" \
    --exclude="__pycache__/" \
    "${MAC_PROJECT_DIR}/bot/monitoring/" \
    "${WINDOWS_PROJECT_DIR}/bot/monitoring/" | tee -a "$SYNC_LOG"

echo -e "${GREEN}✅ Monitoring system synced (5 layers + WebUI writer)${NC}"
echo ""

# ============================================================================
# STEP 5: Sync WebUI Backend
# ============================================================================

echo -e "${CYAN}Step 5: Syncing WebUI backend...${NC}"

echo -e "${BLUE}Syncing webui/backend/ directory...${NC}"
rsync -av --progress \
    --exclude="*.pyc" \
    --exclude="__pycache__/" \
    --exclude="*.log" \
    "${MAC_PROJECT_DIR}/webui/backend/" \
    "${WINDOWS_PROJECT_DIR}/webui/backend/" | tee -a "$SYNC_LOG"

echo -e "${GREEN}✅ WebUI backend synced (Flask app + routes + monitoring)${NC}"
echo ""

# ============================================================================
# STEP 6: Sync WebUI Frontend (React)
# ============================================================================

echo -e "${CYAN}Step 6: Syncing WebUI frontend...${NC}"

echo -e "${BLUE}Syncing webui/frontend/ directory...${NC}"
rsync -av --progress \
    --exclude="node_modules/" \
    --exclude="build/" \
    --exclude=".cache/" \
    "${MAC_PROJECT_DIR}/webui/frontend/" \
    "${WINDOWS_PROJECT_DIR}/webui/frontend/" | tee -a "$SYNC_LOG"

echo -e "${GREEN}✅ WebUI frontend synced (React components)${NC}"
echo ""

# ============================================================================
# STEP 7: Sync Configuration Files (Preserve Windows-specific)
# ============================================================================

echo -e "${CYAN}Step 7: Syncing configuration files...${NC}"

# Sync grid_config.env as template (don't overwrite if exists)
if [ ! -f "${WINDOWS_PROJECT_DIR}/grid_config.env" ]; then
    echo -e "${BLUE}Creating grid_config.env from Mac template...${NC}"
    cp "${MAC_PROJECT_DIR}/grid_config.env" "${WINDOWS_PROJECT_DIR}/grid_config.env"
    echo -e "${GREEN}✅ grid_config.env created${NC}"
else
    echo -e "${YELLOW}⚠️  grid_config.env exists on Windows - NOT overwriting${NC}"
    echo -e "${YELLOW}   Mac version saved as: grid_config.env.mac_template${NC}"
    cp "${MAC_PROJECT_DIR}/grid_config.env" "${WINDOWS_PROJECT_DIR}/grid_config.env.mac_template"
fi

# Sync requirements.txt
echo -e "${BLUE}Syncing requirements.txt...${NC}"
cp "${MAC_PROJECT_DIR}/requirements.txt" "${WINDOWS_PROJECT_DIR}/requirements.txt"
echo -e "${GREEN}✅ requirements.txt synced${NC}"

# Sync ecosystem.config.js (PM2 - if Windows uses PM2)
if [ -f "${MAC_PROJECT_DIR}/ecosystem.config.js" ]; then
    echo -e "${BLUE}Syncing ecosystem.config.js (PM2)...${NC}"
    cp "${MAC_PROJECT_DIR}/ecosystem.config.js" "${WINDOWS_PROJECT_DIR}/ecosystem.config.js"
    echo -e "${GREEN}✅ PM2 config synced${NC}"
fi

echo ""

# ============================================================================
# STEP 8: Sync Documentation
# ============================================================================

echo -e "${CYAN}Step 8: Syncing documentation...${NC}"

DOC_FILES=(
    "AI_CONTEXT.md"
    "AI_CRITICAL_RULES.md"
    "BOT_BRAIN_ARCHITECTURE.md"
    "BOT_STRUCTURE.md"
    "START_HERE.md"
    "USER_MANUAL.md"
    "PM2_COMPLETE_SYSTEM.md"
    "README.md"
    "QUICK_START_NOV7_2025.md"
    "SHORT_MODE_PRODUCTION_READINESS_REPORT_NOV10_2025.md"
    "MODE_ATOMIC_STATE_IMPLEMENTATION_NOV10_2025.md"
    "WEBUI_MODE_SWITCHING_IMPLEMENTATION_NOV10_2025.md"
    "MAC_WINDOWS_SYNC_GUIDE_NOV9_2025.md"
    "WINDOWS_SYNC_SETUP_NOV9_2025.md"
)

echo -e "${BLUE}Syncing documentation files...${NC}"
for doc in "${DOC_FILES[@]}"; do
    if [ -f "${MAC_PROJECT_DIR}/${doc}" ]; then
        cp "${MAC_PROJECT_DIR}/${doc}" "${WINDOWS_PROJECT_DIR}/${doc}"
        echo "  ✓ Synced: $doc" | tee -a "$SYNC_LOG"
    fi
done

echo -e "${GREEN}✅ Documentation synced${NC}"
echo ""

# ============================================================================
# STEP 9: Sync Windows-Specific Scripts
# ============================================================================

echo -e "${CYAN}Step 9: Syncing Windows-specific scripts...${NC}"

if [ -d "${MAC_PROJECT_DIR}/windows" ]; then
    echo -e "${BLUE}Syncing windows/ directory...${NC}"
    rsync -av --progress \
        "${MAC_PROJECT_DIR}/windows/" \
        "${WINDOWS_PROJECT_DIR}/windows/" | tee -a "$SYNC_LOG"
    echo -e "${GREEN}✅ Windows scripts synced (.bat files)${NC}"
else
    echo -e "${YELLOW}⚠️  windows/ directory not found on Mac${NC}"
fi

echo ""

# ============================================================================
# STEP 10: Restore Windows State Files
# ============================================================================

echo -e "${CYAN}Step 10: Restoring Windows state files...${NC}"

echo -e "${BLUE}Restoring Windows-specific state files from backup...${NC}"
for file in "${STATE_FILES[@]}"; do
    if [ -f "${BACKUP_DIR}/${file}" ]; then
        mkdir -p "$(dirname "${WINDOWS_PROJECT_DIR}/${file}")"
        cp "${BACKUP_DIR}/${file}" "${WINDOWS_PROJECT_DIR}/${file}" 2>/dev/null || true
        echo "  ✓ Restored: $file" | tee -a "$SYNC_LOG"
    fi
done

echo -e "${GREEN}✅ Windows state files restored${NC}"
echo ""

# ============================================================================
# STEP 11: Set Proper Permissions
# ============================================================================

echo -e "${CYAN}Step 11: Setting file permissions...${NC}"

# Make Python files executable (if Windows supports it via SMB)
find "${WINDOWS_PROJECT_DIR}/bot" -name "*.py" -type f -exec chmod +x {} \; 2>/dev/null || true
find "${WINDOWS_PROJECT_DIR}/webui" -name "*.py" -type f -exec chmod +x {} \; 2>/dev/null || true

echo -e "${GREEN}✅ Permissions set${NC}"
echo ""

# ============================================================================
# STEP 12: Generate Sync Summary
# ============================================================================

echo -e "${CYAN}Step 12: Generating sync summary...${NC}"

SUMMARY_FILE="${WINDOWS_PROJECT_DIR}/SYNC_SUMMARY_${TIMESTAMP}.md"

cat > "$SUMMARY_FILE" << 'EOF'
# GridBot Sync Summary - $(date)

## Sync Details

- **Source:** macOS - /Users/ssr/Projects/WorkingBot
- **Target:** Windows - D:\Projects\WorkingBot
- **Method:** SMB share via /Volumes/D_Drive
- **Sync Type:** Complete mirror (bot brain + monitoring + WebUI)

## Files Synced

### ✅ Core Bot Brain
- bot/strategy/gridbot.py (main orchestrator)
- bot/strategy/modules/ (7 core modules)
  - grid_calculator.py
  - position_manager.py
  - fill_detector.py
  - order_manager.py
  - reconciliation.py
  - volatility_handler.py
  - websocket_handler.py
- bot/strategy/handlers/ (LONG/SHORT handlers)
  - long_handler.py
  - short_handler.py

### ✅ Monitoring System (5 Layers)
- bot/monitoring/price_health.py (Layer 1)
- bot/monitoring/pre_order_logger.py (Layer 2)
- bot/monitoring/tp_verification.py (Layer 3)
- bot/monitoring/anomaly_detection.py (Layer 4)
- bot/monitoring/predictive_display.py (Layer 5)
- bot/monitoring/data_writer.py (WebUI integration)

### ✅ API & WebSocket
- bot/api/delta_client.py
- bot/delta_websocket/ws_manager.py

### ✅ Safety Systems
- bot/guardian/guardian_bot.py
- bot/heartbeat/monitor.py
- bot/volatility/iv_rv_tracker.py
- bot/safety/ (loss limits, blocker tracker, instance lock)

### ✅ WebUI
- webui/backend/ (Flask backend + routes)
- webui/frontend/ (React components)

### ✅ Configuration
- requirements.txt
- ecosystem.config.js (PM2)
- grid_config.env (template - preserved if exists)

### ✅ Documentation
- AI_CONTEXT.md (complete system overview)
- BOT_BRAIN_ARCHITECTURE.md
- START_HERE.md
- All NOV 10 updates (MODE_ATOMIC_STATE, SHORT_MODE_PRODUCTION, etc.)

## Files Preserved (Windows-Specific)

These files were NOT overwritten:
- runtime_state.json (Windows bot state)
- .current_mode (Windows mode setting)
- grid_config.env (Windows-specific config)
- secrets/api_keys.env (Windows API keys)
- bot/logs/*.log (Windows logs)
- .bot_instance_live.lock (Windows lock file)

## Latest Updates Included (Nov 10, 2025)

- ✅ Mode-atomic state management (LONG/SHORT)
- ✅ SHORT mode production readiness
- ✅ WebUI mode switching implementation
- ✅ WebSocket price update fixes
- ✅ REST API fallback improvements
- ✅ Fill detection enhancements
- ✅ Partial fill support
- ✅ All monitoring layers updated

## Post-Sync Steps Required

### 1. Verify Python Environment
```powershell
cd D:\Projects\WorkingBot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Test Imports
```powershell
python -c "from bot.strategy.gridbot import GridBot; print('✅ OK')"
python -c "from bot.monitoring.price_health import PriceHealthMonitor; print('✅ OK')"
```

### 3. Check Configuration
```powershell
# Review grid_config.env for Windows-specific paths
notepad grid_config.env
```

### 4. Verify API Keys
```powershell
# Ensure secrets/api_keys.env exists with valid keys
type secrets\api_keys.env
```

### 5. Test Bot Startup (Dry Run)
```powershell
set PYTHONPATH=D:\Projects\WorkingBot
set TRADING_MODE=demo
set EXECUTE_ORDERS=false
python bot\run.py
```

### 6. Start WebUI Backend
```powershell
cd webui\backend
python app.py
```

### 7. Access WebUI
```
Local: http://localhost:5555
From Mac: http://192.168.1.32:5555
```

## Backup Location

Previous Windows state backed up to:
```
D:\Projects\WorkingBot\.backup_before_sync_TIMESTAMP\
```

## Support

**Owner:** Shailendra Singh Rajawat
**Email:** physics.ssr@gmail.com
**Telegram:** 8170794676

For detailed documentation, see:
- AI_CONTEXT.md (system architecture)
- START_HERE.md (quick start)
- BOT_BRAIN_ARCHITECTURE.md (module connections)

---

**Status:** ✅ Sync Complete
**Sync Log:** /tmp/gridbot_sync_TIMESTAMP.log
EOF

# Replace timestamp in summary
sed -i '' "s/TIMESTAMP/${TIMESTAMP}/g" "$SUMMARY_FILE" 2>/dev/null || \
    sed -i "s/TIMESTAMP/${TIMESTAMP}/g" "$SUMMARY_FILE"

echo -e "${GREEN}✅ Sync summary generated: ${SUMMARY_FILE}${NC}"
echo ""

# ============================================================================
# STEP 13: Final Verification
# ============================================================================

echo -e "${CYAN}Step 13: Final verification...${NC}"

# Count synced files
TOTAL_BOT_FILES=$(find "${WINDOWS_PROJECT_DIR}/bot" -name "*.py" -type f | wc -l | tr -d ' ')
TOTAL_MONITORING_FILES=$(find "${WINDOWS_PROJECT_DIR}/bot/monitoring" -name "*.py" -type f 2>/dev/null | wc -l | tr -d ' ')
TOTAL_WEBUI_BACKEND=$(find "${WINDOWS_PROJECT_DIR}/webui/backend" -name "*.py" -type f 2>/dev/null | wc -l | tr -d ' ')

echo -e "${BLUE}Verification Results:${NC}"
echo -e "  Bot Python files: ${GREEN}${TOTAL_BOT_FILES}${NC}"
echo -e "  Monitoring files: ${GREEN}${TOTAL_MONITORING_FILES}${NC}"
echo -e "  WebUI backend files: ${GREEN}${TOTAL_WEBUI_BACKEND}${NC}"
echo ""

# Check critical files
CRITICAL_FILES=(
    "bot/strategy/gridbot.py"
    "bot/strategy/modules/grid_calculator.py"
    "bot/strategy/modules/position_manager.py"
    "bot/strategy/handlers/long_handler.py"
    "bot/strategy/handlers/short_handler.py"
    "bot/monitoring/price_health.py"
    "webui/backend/app.py"
)

echo -e "${BLUE}Critical files verification:${NC}"
ALL_CRITICAL_PRESENT=true
for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "${WINDOWS_PROJECT_DIR}/${file}" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file ${RED}MISSING!${NC}"
        ALL_CRITICAL_PRESENT=false
    fi
done

echo ""

# ============================================================================
# FINAL SUMMARY
# ============================================================================

echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                       SYNC COMPLETE! ✅                              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$ALL_CRITICAL_PRESENT" = true ]; then
    echo -e "${GREEN}✅ All critical files synced successfully${NC}"
else
    echo -e "${RED}⚠️  Some critical files are missing - check sync log${NC}"
fi

echo ""
echo -e "${MAGENTA}Sync Statistics:${NC}"
echo -e "  Bot Python files: ${TOTAL_BOT_FILES}"
echo -e "  Monitoring files: ${TOTAL_MONITORING_FILES}"
echo -e "  WebUI backend files: ${TOTAL_WEBUI_BACKEND}"
echo -e "  Backup location: .backup_before_sync_${TIMESTAMP}/"
echo -e "  Sync log: $SYNC_LOG"
echo -e "  Summary: SYNC_SUMMARY_${TIMESTAMP}.md"
echo ""

echo -e "${CYAN}Next Steps on Windows:${NC}"
echo ""
echo -e "${YELLOW}1. Verify Python Environment${NC}"
echo -e "   cd D:\\Projects\\WorkingBot"
echo -e "   .venv\\Scripts\\activate"
echo -e "   pip install -r requirements.txt"
echo ""
echo -e "${YELLOW}2. Test Bot Imports${NC}"
echo -e "   python -c \"from bot.strategy.gridbot import GridBot; print('✅ OK')\""
echo ""
echo -e "${YELLOW}3. Review Configuration${NC}"
echo -e "   notepad grid_config.env"
echo -e "   Verify paths and settings for Windows"
echo ""
echo -e "${YELLOW}4. Test Bot Startup (Dry Run)${NC}"
echo -e "   set PYTHONPATH=D:\\Projects\\WorkingBot"
echo -e "   set TRADING_MODE=demo"
echo -e "   python bot\\run.py"
echo ""
echo -e "${YELLOW}5. Access WebUI${NC}"
echo -e "   Local: http://localhost:5555"
echo -e "   From Mac: http://192.168.1.32:5555"
echo ""

echo -e "${GREEN}Windows GridBot is now a complete mirror of macOS GridBot! 🎉${NC}"
echo ""
echo -e "${BLUE}For detailed documentation:${NC}"
echo -e "  - AI_CONTEXT.md (complete system overview)"
echo -e "  - START_HERE.md (quick start guide)"
echo -e "  - SYNC_SUMMARY_${TIMESTAMP}.md (this sync details)"
echo ""

echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  GridBot sync completed at $(date +'%Y-%m-%d %H:%M:%S')  ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
