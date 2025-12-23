#!/bin/bash
# Trigger Windows to pull latest monitoring changes
# Date: November 8, 2025

WINDOWS_IP="192.168.1.32"
WINDOWS_USER="SSR"

echo "================================================================================"
echo "🔄 TRIGGERING WINDOWS SYNC VIA REMOTE COMMAND"
echo "================================================================================"
echo ""

echo "📡 Connecting to Windows ($WINDOWS_IP)..."
echo ""

# Create PowerShell command to run on Windows
WIN_COMMAND='
Write-Host "🔄 Pulling latest changes from GitHub..." -ForegroundColor Cyan;
Set-Location D:\Projects\WorkingBot;
git fetch origin;
git pull origin production-v2.0;
Write-Host "";
Write-Host "🔍 Running validation..." -ForegroundColor Yellow;
python -m py_compile bot\monitoring\price_health_monitor.py;
python -m py_compile bot\strategy\gridbot.py;
python -c "from bot.monitoring import PriceHealthMonitor; print(\"✅ Monitoring imports successful\")";
Write-Host "";
Write-Host "✅ Windows sync complete!" -ForegroundColor Green;
'

# Try to execute via SSH (requires OpenSSH on Windows)
echo "Executing remote PowerShell command..."
echo ""

ssh ${WINDOWS_USER}@${WINDOWS_IP} "powershell -Command \"$WIN_COMMAND\"" 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Remote execution successful!"
else
    echo ""
    echo "⚠️  SSH connection failed. Please run manually on Windows:"
    echo ""
    echo "PowerShell commands:"
    echo "-------------------"
    echo "cd D:\\Projects\\WorkingBot"
    echo "git pull origin production-v2.0"
    echo "python -m py_compile bot\\monitoring\\*.py"
    echo "python -c \"from bot.monitoring import PriceHealthMonitor; print('✅ OK')\""
fi

echo ""
echo "================================================================================"
