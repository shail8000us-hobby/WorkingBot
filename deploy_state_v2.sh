#!/bin/bash
# State Management v2.0 Deployment Script
# Safe deployment with automatic rollback on failure

set -e  # Exit on error

echo "============================================================"
echo "State Management v2.0 Deployment"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Pre-deployment checks
echo "📋 Step 1: Pre-deployment Checks"
echo "-----------------------------------------------------------"

# Check if bot is running
if pgrep -f "bot_launcher.py" > /dev/null; then
    echo -e "${YELLOW}⚠️  Bot is currently running${NC}"
    read -p "Stop bot before deployment? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping bot..."
        python3 bot_stopper.py
        sleep 2
    else
        echo -e "${RED}❌ Deployment cancelled - please stop bot manually${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Bot is not running${NC}"
fi

# Check Python syntax
echo ""
echo "🔍 Checking Python syntax..."
python3 -m py_compile bot/strategy/modules/position_manager.py
python3 -m py_compile bot/reconciliation/data_sources.py
echo -e "${GREEN}✅ Syntax check passed${NC}"

# Step 2: Backup current state
echo ""
echo "💾 Step 2: Backup Current State"
echo "-----------------------------------------------------------"

BACKUP_DIR="state_backups/pre_v2_deployment_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "runtime_state.json" ]; then
    cp runtime_state.json "$BACKUP_DIR/"
    echo -e "${GREEN}✅ Backed up runtime_state.json${NC}"
fi

if [ -f "bot/state/state.json" ]; then
    cp bot/state/state.json "$BACKUP_DIR/"
    echo -e "${GREEN}✅ Backed up bot/state/state.json${NC}"
fi

echo "📁 Backups saved to: $BACKUP_DIR"

# Step 3: Run migration
echo ""
echo "🔄 Step 3: Migrate State Files to v2.0"
echo "-----------------------------------------------------------"

if [ -f "migrate_state_to_v2.py" ]; then
    python3 migrate_state_to_v2.py
    echo -e "${GREEN}✅ Migration completed${NC}"
else
    echo -e "${RED}❌ migrate_state_to_v2.py not found${NC}"
    exit 1
fi

# Step 4: Run tests
echo ""
echo "🧪 Step 4: Run Tests"
echo "-----------------------------------------------------------"

if [ -f "test_state_management.py" ]; then
    if python3 test_state_management.py; then
        echo -e "${GREEN}✅ All tests passed${NC}"
    else
        echo -e "${RED}❌ Tests failed - rolling back${NC}"
        
        # Rollback
        echo "🔙 Rolling back..."
        if [ -f "$BACKUP_DIR/runtime_state.json" ]; then
            cp "$BACKUP_DIR/runtime_state.json" runtime_state.json
            echo "✅ Rollback complete"
        fi
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  test_state_management.py not found - skipping tests${NC}"
fi

# Step 5: Verify state file
echo ""
echo "✅ Step 5: Verify State File"
echo "-----------------------------------------------------------"

if [ -f "runtime_state.json" ]; then
    # Check if valid JSON
    if python3 -m json.tool runtime_state.json > /dev/null 2>&1; then
        echo -e "${GREEN}✅ runtime_state.json is valid JSON${NC}"
        
        # Check version
        VERSION=$(python3 -c "import json; print(json.load(open('runtime_state.json')).get('version', 'unknown'))")
        echo "   Version: $VERSION"
        
        if [ "$VERSION" = "2.0" ]; then
            echo -e "${GREEN}✅ State file is v2.0 format${NC}"
        else
            echo -e "${YELLOW}⚠️  State file version: $VERSION (expected 2.0)${NC}"
        fi
    else
        echo -e "${RED}❌ runtime_state.json is invalid JSON${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  runtime_state.json not found (will be created on bot start)${NC}"
fi

# Step 6: Summary
echo ""
echo "============================================================"
echo "✅ Deployment Complete!"
echo "============================================================"
echo ""
echo "Changes Deployed:"
echo "  ✅ State file consolidated to runtime_state.json"
echo "  ✅ Immediate persistence (debounced at 1s)"
echo "  ✅ Stale threshold: 5 minutes (was 1 hour)"
echo "  ✅ Checksum validation enabled"
echo "  ✅ Metadata tracking (v2.0, PID, timestamps)"
echo ""
echo "Backups Location:"
echo "  📁 $BACKUP_DIR"
echo ""
echo "Next Steps:"
echo "  1. Start bot: ./bot_launcher.py"
echo "  2. Monitor state file updates: watch -n 1 'stat -f \"%Sm\" runtime_state.json'"
echo "  3. Check logs for state persistence messages"
echo ""
echo "Rollback Instructions (if needed):"
echo "  1. Stop bot: ./bot_stopper.py"
echo "  2. Restore: cp $BACKUP_DIR/runtime_state.json ."
echo "  3. Revert code changes using git"
echo "  4. Restart bot"
echo ""
echo -e "${GREEN}🚀 Ready to start bot!${NC}"
echo ""
