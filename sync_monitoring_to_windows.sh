#!/bin/bash
# Sync Monitoring System to Windows
# Date: November 8, 2025

set -e

WINDOWS_IP="192.168.1.32"
WINDOWS_USER="SSR"
WINDOWS_PATH="D:/Projects/WorkingBot"

echo "================================================================================"
echo "🔄 SYNCING MONITORING SYSTEM TO WINDOWS"
echo "================================================================================"
echo ""

# Check if Windows is reachable
echo "📡 Checking Windows connectivity..."
if ping -c 1 $WINDOWS_IP &> /dev/null; then
    echo "✅ Windows machine ($WINDOWS_IP) is reachable"
else
    echo "❌ Cannot reach Windows machine"
    exit 1
fi

echo ""
echo "📦 Files to sync:"
echo "  NEW: bot/monitoring/ (6 files)"
echo "  MODIFIED: bot/strategy/gridbot.py"
echo "  MODIFIED: bot/strategy/modules/order_manager.py"
echo "  MODIFIED: bot/strategy/handlers/long_handler.py"
echo "  MODIFIED: bot/strategy/handlers/short_handler.py"
echo ""

# Create monitoring directory on Windows via PowerShell remote execution
echo "📁 Creating monitoring directory on Windows..."
/usr/bin/ssh ${WINDOWS_USER}@${WINDOWS_IP} "powershell -Command \"New-Item -Path '${WINDOWS_PATH}\\bot\\monitoring' -ItemType Directory -Force\" " 2>/dev/null || true

# Use scp to transfer files
echo ""
echo "🚀 Transferring files..."

# Transfer monitoring package
echo "  ├─ Copying bot/monitoring/__init__.py..."
scp bot/monitoring/__init__.py ${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PATH}/bot/monitoring/ 2>/dev/null || echo "  ⚠️  SCP failed, will use alternative method"

echo "  ├─ Copying bot/monitoring/price_health_monitor.py..."
scp bot/monitoring/price_health_monitor.py ${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PATH}/bot/monitoring/ 2>/dev/null || true

echo "  ├─ Copying bot/monitoring/pre_order_logger.py..."
scp bot/monitoring/pre_order_logger.py ${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PATH}/bot/monitoring/ 2>/dev/null || true

echo "  ├─ Copying bot/monitoring/tp_verification.py..."
scp bot/monitoring/tp_verification.py ${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PATH}/bot/monitoring/ 2>/dev/null || true

echo "  ├─ Copying bot/monitoring/anomaly_detection.py..."
scp bot/monitoring/anomaly_detection.py ${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PATH}/bot/monitoring/ 2>/dev/null || true

echo "  ├─ Copying bot/monitoring/predictive_display.py..."
scp bot/monitoring/predictive_display.py ${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PATH}/bot/monitoring/ 2>/dev/null || true

# Transfer modified files
echo "  ├─ Updating bot/strategy/gridbot.py..."
scp bot/strategy/gridbot.py ${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PATH}/bot/strategy/ 2>/dev/null || true

echo "  ├─ Updating bot/strategy/modules/order_manager.py..."
scp bot/strategy/modules/order_manager.py ${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PATH}/bot/strategy/modules/ 2>/dev/null || true

echo "  ├─ Updating bot/strategy/handlers/long_handler.py..."
scp bot/strategy/handlers/long_handler.py ${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PATH}/bot/strategy/handlers/ 2>/dev/null || true

echo "  └─ Updating bot/strategy/handlers/short_handler.py..."
scp bot/strategy/handlers/short_handler.py ${WINDOWS_USER}@${WINDOWS_IP}:${WINDOWS_PATH}/bot/strategy/handlers/ 2>/dev/null || true

echo ""
echo "✅ File transfer complete!"

echo ""
echo "================================================================================"
echo "📋 NEXT STEPS ON WINDOWS"
echo "================================================================================"
echo ""
echo "Run these commands on Windows PowerShell:"
echo ""
echo "  cd D:\\Projects\\WorkingBot"
echo "  python -m py_compile bot\\monitoring\\*.py"
echo "  python -c \"from bot.monitoring import PriceHealthMonitor; print('✅ Imports work')\""
echo ""
echo "================================================================================"
