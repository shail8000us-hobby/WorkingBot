#!/bin/bash
# Quick fix for parameter sync issues
# This script fixes critical mismatches in grid_config.env and state.json

set -e  # Exit on error

echo "🔧 Fixing parameter sync issues..."
echo ""

# Get the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Backup files before modifying
echo "📋 Creating backups..."
cp grid_config.env "grid_config.env.backup.$(date +%s)"
if [ -f state.json ]; then
    cp state.json "state.json.backup.$(date +%s)"
fi
echo "✅ Backups created"
echo ""

# 1. Fix grid_config.env
echo "🔧 Fixing grid_config.env..."

# Fix REFERENCE_LEVEL (115100 → 115000)
if grep -q "^REFERENCE_LEVEL=115100" grid_config.env; then
    sed -i.bak 's/^REFERENCE_LEVEL=115100/REFERENCE_LEVEL=115000/' grid_config.env
    echo "  ✅ Fixed REFERENCE_LEVEL: 115100 → 115000"
fi

# Fix MAX_OPEN (5 → 100)
if grep -q "^MAX_OPEN=5$" grid_config.env; then
    sed -i.bak 's/^MAX_OPEN=5$/MAX_OPEN=100/' grid_config.env
    echo "  ✅ Fixed MAX_OPEN: 5 → 100"
fi

# Remove backup file created by sed
rm -f grid_config.env.bak

echo ""

# 2. Update state.json
echo "🔧 Updating state.json..."

cat > state.json << 'EOF'
{
  "last_price": 112068.410625,
  "reference_level": 115000.0,
  "open_positions": [],
  "GRID_LOWER": 110000.0,
  "GRID_UPPER": 130000.0,
  "GRID_STEP": 100.0,
  "REFERENCE_LEVEL": 115000.0,
  "LOT": 1.0,
  "GRID_ACTIVE": true,
  "LAST_SET_AT": TIMESTAMP_PLACEHOLDER
}
EOF

# Replace timestamp placeholder with actual timestamp
TIMESTAMP=$(date +%s)
sed -i.bak "s/TIMESTAMP_PLACEHOLDER/$TIMESTAMP/" state.json
rm -f state.json.bak

echo "  ✅ state.json synced with config"
echo ""

# 3. Verify changes
echo "📊 Verification:"
echo ""
echo "grid_config.env changes:"
echo "  • REFERENCE_LEVEL = $(grep "^REFERENCE_LEVEL=" grid_config.env | cut -d= -f2)"
echo "  • MAX_OPEN = $(grep "^MAX_OPEN=" grid_config.env | cut -d= -f2)"
echo ""
echo "state.json values:"
echo "  • GRID_UPPER = $(grep '"GRID_UPPER"' state.json | awk '{print $2}' | tr -d ',')"
echo "  • GRID_STEP = $(grep '"GRID_STEP"' state.json | awk '{print $2}' | tr -d ',')"
echo "  • REFERENCE_LEVEL = $(grep '"REFERENCE_LEVEL"' state.json | awk '{print $2}' | tr -d ',')"
echo ""

# 4. Show parameter sync status
echo "🎯 Parameter Sync Status:"
echo ""
GRIDBOT_LOWER=$(grep "^GRIDBOT_LOWER=" grid_config.env | cut -d= -f2)
GRID_LOWER=$(grep "^GRID_LOWER=" grid_config.env | cut -d= -f2)
GRIDBOT_UPPER=$(grep "^GRIDBOT_UPPER=" grid_config.env | cut -d= -f2)
GRID_UPPER=$(grep "^GRID_UPPER=" grid_config.env | cut -d= -f2)
GRIDBOT_STEP=$(grep "^GRIDBOT_STEP=" grid_config.env | cut -d= -f2)
GRID_STEP_CFG=$(grep "^GRID_STEP=" grid_config.env | cut -d= -f2)
GRIDBOT_REF=$(grep "^GRIDBOT_REF=" grid_config.env | cut -d= -f2)
REFERENCE_LEVEL=$(grep "^REFERENCE_LEVEL=" grid_config.env | cut -d= -f2)
GRIDBOT_MAX_OPEN=$(grep "^GRIDBOT_MAX_OPEN=" grid_config.env | cut -d= -f2)
MAX_OPEN=$(grep "^MAX_OPEN=" grid_config.env | cut -d= -f2)

if [ "$GRIDBOT_LOWER" = "$GRID_LOWER" ]; then
    echo "  ✅ GRIDBOT_LOWER == GRID_LOWER ($GRIDBOT_LOWER)"
else
    echo "  ❌ GRIDBOT_LOWER ($GRIDBOT_LOWER) != GRID_LOWER ($GRID_LOWER)"
fi

if [ "$GRIDBOT_UPPER" = "$GRID_UPPER" ]; then
    echo "  ✅ GRIDBOT_UPPER == GRID_UPPER ($GRIDBOT_UPPER)"
else
    echo "  ❌ GRIDBOT_UPPER ($GRIDBOT_UPPER) != GRID_UPPER ($GRID_UPPER)"
fi

if [ "$GRIDBOT_STEP" = "$GRID_STEP_CFG" ]; then
    echo "  ✅ GRIDBOT_STEP == GRID_STEP ($GRIDBOT_STEP)"
else
    echo "  ❌ GRIDBOT_STEP ($GRIDBOT_STEP) != GRID_STEP ($GRID_STEP_CFG)"
fi

if [ "$GRIDBOT_REF" = "$REFERENCE_LEVEL" ]; then
    echo "  ✅ GRIDBOT_REF == REFERENCE_LEVEL ($GRIDBOT_REF)"
else
    echo "  ❌ GRIDBOT_REF ($GRIDBOT_REF) != REFERENCE_LEVEL ($REFERENCE_LEVEL)"
fi

if [ "$GRIDBOT_MAX_OPEN" = "$MAX_OPEN" ]; then
    echo "  ✅ GRIDBOT_MAX_OPEN == MAX_OPEN ($GRIDBOT_MAX_OPEN)"
else
    echo "  ❌ GRIDBOT_MAX_OPEN ($GRIDBOT_MAX_OPEN) != MAX_OPEN ($MAX_OPEN)"
fi

echo ""
echo "=" * 80
echo "✅ Parameter sync fix completed!"
echo ""
echo "Summary of changes:"
echo "  • Fixed REFERENCE_LEVEL: 115100 → 115000"
echo "  • Fixed MAX_OPEN: 5 → 100"
echo "  • Updated state.json to match grid_config.env"
echo ""
echo "📋 Backups saved with timestamp suffix"
echo "⚠️  Please restart the bot for changes to take effect"
echo ""
echo "To restart bot:"
echo "  1. Stop current bot: ./stop_bot.sh"
echo "  2. Start bot: python -m bot.run"
echo ""



