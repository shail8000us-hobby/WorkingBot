#!/bin/bash

# Emergency Performance Fix Script
# Increases polling intervals to reduce API request storm from 350/min to ~70/min

set -e

FRONTEND_DIR="/Users/ssr/Projects/WorkingBot/webui/frontend/src"
BACKUP_DIR="/Users/ssr/Projects/WorkingBot/webui/frontend/.backups/$(date +%Y%m%d_%H%M%S)"

echo "================================================"
echo "  WebUI Performance Emergency Fix"
echo "================================================"
echo ""
echo "Problem: 35+ components polling APIs every 3-10 seconds"
echo "Solution: Increase intervals to 15-30 seconds"
echo "Expected: Reduce 350 req/min → 70 req/min (80% reduction)"
echo ""

# Create backup
echo "📦 Creating backup..."
mkdir -p "$BACKUP_DIR"
cp -r "$FRONTEND_DIR/components" "$BACKUP_DIR/"
cp -r "$FRONTEND_DIR/hooks" "$BACKUP_DIR/" 2>/dev/null || true
cp -r "$FRONTEND_DIR/context" "$BACKUP_DIR/" 2>/dev/null || true
echo "✅ Backup created at: $BACKUP_DIR"
echo ""

# Count files to fix
FILES_TO_FIX=$(find "$FRONTEND_DIR" -name "*.js" -type f -exec grep -l "setInterval.*[0-9]\{3,5\}" {} \; | wc -l)
echo "📊 Found $FILES_TO_FIX files with polling intervals"
echo ""

echo "🔧 Applying fixes..."
echo ""

# Fix 1: BotBrainAnalyzer components (3s → 30s)
echo "1. Fixing BotBrainAnalyzer components (3000ms → 30000ms)"
find "$FRONTEND_DIR/components/BotBrainAnalyzer" -name "*.js" 2>/dev/null | while read file; do
  if grep -q "setInterval.*3000" "$file"; then
    sed -i '' 's/setInterval(\([^,]*\), 3000)/setInterval(\1, 30000)/g' "$file"
    echo "   ✅ $(basename $file)"
  fi
done

# Fix 2: RiskSafetyDashboard (5s → 30s)
echo "2. Fixing RiskSafetyDashboard.js (5000ms → 30000ms)"
if [ -f "$FRONTEND_DIR/components/RiskSafetyDashboard.js" ]; then
  sed -i '' 's/setInterval(fetchSafetyData, 5000)/setInterval(fetchSafetyData, 30000)/g' "$FRONTEND_DIR/components/RiskSafetyDashboard.js"
  sed -i '' 's/Refresh every 5 seconds/Refresh every 30 seconds/g' "$FRONTEND_DIR/components/RiskSafetyDashboard.js"
  echo "   ✅ RiskSafetyDashboard.js"
fi

# Fix 3: CapitalProtectionPanel (5s → 15s)
echo "3. Fixing CapitalProtectionPanel.js (5000ms → 15000ms)"
if [ -f "$FRONTEND_DIR/components/CapitalProtectionPanel.js" ]; then
  sed -i '' 's/setInterval(fetchAllData, 5000)/setInterval(fetchAllData, 15000)/g' "$FRONTEND_DIR/components/CapitalProtectionPanel.js"
  sed -i '' 's/Update every 5 seconds/Update every 15 seconds/g' "$FRONTEND_DIR/components/CapitalProtectionPanel.js"
  echo "   ✅ CapitalProtectionPanel.js"
fi

# Fix 4: MonitoringDashboard (10s → 30s)
echo "4. Fixing MonitoringDashboard.js (10000ms → 30000ms)"
if [ -f "$FRONTEND_DIR/components/MonitoringDashboard.js" ]; then
  sed -i '' 's/setInterval(fetchMonitoringData, 10000)/setInterval(fetchMonitoringData, 30000)/g' "$FRONTEND_DIR/components/MonitoringDashboard.js"
  sed -i '' 's/Poll every 10s/Poll every 30s/g' "$FRONTEND_DIR/components/MonitoringDashboard.js"
  echo "   ✅ MonitoringDashboard.js"
fi

# Fix 5: PM2Panel (5s → 30s)
echo "5. Fixing PM2Panel.js (5000ms → 30000ms)"
if [ -f "$FRONTEND_DIR/components/PM2Panel.js" ]; then
  sed -i '' 's/setInterval(fetchPM2Status, 5000)/setInterval(fetchPM2Status, 30000)/g' "$FRONTEND_DIR/components/PM2Panel.js"
  echo "   ✅ PM2Panel.js"
fi

# Fix 6: TradingModeSwitch (5s → 30s)
echo "6. Fixing TradingModeSwitch.js (5000ms → 30000ms)"
if [ -f "$FRONTEND_DIR/components/TradingModeSwitch.js" ]; then
  sed -i '' 's/setInterval(fetchCurrentMode, 5000)/setInterval(fetchCurrentMode, 30000)/g' "$FRONTEND_DIR/components/TradingModeSwitch.js"
  echo "   ✅ TradingModeSwitch.js"
fi

# Fix 7: RobustnessPanel (5s → 30s)
echo "7. Fixing RobustnessPanel.js (5000ms → 30000ms)"
if [ -f "$FRONTEND_DIR/components/RobustnessPanel.js" ]; then
  sed -i '' 's/setInterval(tick, 5000)/setInterval(tick, 30000)/g' "$FRONTEND_DIR/components/RobustnessPanel.js"
  echo "   ✅ RobustnessPanel.js"
fi

# Fix 8: TmuxPanel (5s → 30s)
echo "8. Fixing TmuxPanel.js (5000ms → 30000ms)"
if [ -f "$FRONTEND_DIR/components/TmuxPanel.js" ]; then
  sed -i '' 's/setInterval(fetchTmuxStatus, 5000)/setInterval(fetchTmuxStatus, 30000)/g' "$FRONTEND_DIR/components/TmuxPanel.js"
  sed -i '' 's/Poll every 5 seconds/Poll every 30 seconds/g' "$FRONTEND_DIR/components/TmuxPanel.js"
  echo "   ✅ TmuxPanel.js"
fi

# Fix 9: TradingStatusPanel (5s + 15s → 30s)
echo "9. Fixing TradingStatusPanel.js"
if [ -f "$FRONTEND_DIR/components/TradingStatusPanel.js" ]; then
  sed -i '' 's/setInterval(fetchReconStatus, 15000)/setInterval(fetchReconStatus, 30000)/g' "$FRONTEND_DIR/components/TradingStatusPanel.js"
  echo "   ✅ TradingStatusPanel.js"
fi

# Fix 10: SymbolContextBar (5s → 30s)
echo "10. Fixing layout/SymbolContextBar.js (5000ms → 30000ms)"
if [ -f "$FRONTEND_DIR/components/layout/SymbolContextBar.js" ]; then
  sed -i '' 's/setInterval(fetchMarketData, 5000)/setInterval(fetchMarketData, 30000)/g' "$FRONTEND_DIR/components/layout/SymbolContextBar.js"
  sed -i '' 's/Update every 5 seconds/Update every 30 seconds/g' "$FRONTEND_DIR/components/layout/SymbolContextBar.js"
  echo "   ✅ layout/SymbolContextBar.js"
fi

# Fix 11: BotManagerPanel (continuous → 30s)
echo "11. Fixing BotManagerPanel.js"
if [ -f "$FRONTEND_DIR/components/BotManagerPanel.js" ]; then
  sed -i '' 's/setInterval([^,]*, 5000)/setInterval(() => { fetchBotStatus(); }, 30000)/g' "$FRONTEND_DIR/components/BotManagerPanel.js"
  echo "   ✅ BotManagerPanel.js"
fi

# Fix 12: PositionsPanel
echo "12. Fixing PositionsPanel.js"
if [ -f "$FRONTEND_DIR/components/PositionsPanel.js" ]; then
  sed -i '' 's/setInterval([^,]*, 10000)/setInterval(() => { if (!document.hidden) { fetchPositions(); } }, 30000)/g' "$FRONTEND_DIR/components/PositionsPanel.js"
  echo "   ✅ PositionsPanel.js"
fi

echo ""
echo "✨ All fixes applied!"
echo ""

echo "📊 Summary of changes:"
echo "  • BotBrainAnalyzer: 3s → 30s (10x slower)"
echo "  • RiskSafety: 5s → 30s (6x slower)"
echo "  • CapitalProtection: 5s → 15s (3x slower)"
echo "  • Monitoring: 10s → 30s (3x slower)"
echo "  • PM2, Tmux, Trading Mode: 5s → 30s (6x slower)"
echo "  • Symbol Context, Robustness: 5s → 30s (6x slower)"
echo ""

echo "🚀 Next steps:"
echo "  1. Rebuild frontend: cd webui/frontend && npm run build"
echo "  2. Restart backend: launchctl kickstart -k gui/\$(id -u)/com.gridbot.webui"
echo "  3. Clear browser cache: Cmd+Shift+R"
echo "  4. Test: Should see ~70 requests instead of 284"
echo ""

echo "💾 Backup location:"
echo "  $BACKUP_DIR"
echo ""

echo "✅ Performance fix complete!"
echo ""
echo "Expected improvement:"
echo "  Before: ~350 requests/minute, 55s load time"
echo "  After:  ~70 requests/minute, ~15s load time"
echo ""
