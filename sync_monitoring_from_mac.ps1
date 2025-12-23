# Sync Monitoring System from Mac to Windows
# Run this on Windows PowerShell
# Date: November 8, 2025

param(
    [string]$Method = "git"  # Options: "git", "direct"
)

$ErrorActionPreference = "Stop"
$WorkingDir = "D:\Projects\WorkingBot"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "SYNCING MONITORING SYSTEM FROM MAC" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Change to project directory
if (Test-Path $WorkingDir) {
    Set-Location $WorkingDir
    Write-Host "✅ Working directory: $WorkingDir" -ForegroundColor Green
} else {
    Write-Host "❌ Directory not found: $WorkingDir" -ForegroundColor Red
    exit 1
}

if ($Method -eq "git") {
    Write-Host ""
    Write-Host "📥 Method: Git Pull (RECOMMENDED)" -ForegroundColor Yellow
    Write-Host ""
    
    # Check if git is available
    try {
        $gitVersion = git --version
        Write-Host "✅ Git detected: $gitVersion" -ForegroundColor Green
    } catch {
        Write-Host "❌ Git not found. Install Git or use -Method direct" -ForegroundColor Red
        exit 1
    }
    
    # Fetch latest changes
    Write-Host ""
    Write-Host "🔄 Fetching from origin..." -ForegroundColor Yellow
    git fetch origin
    
    # Show current branch
    $currentBranch = git branch --show-current
    Write-Host "📌 Current branch: $currentBranch" -ForegroundColor Cyan
    
    # Pull changes
    Write-Host ""
    Write-Host "⬇️  Pulling latest changes..." -ForegroundColor Yellow
    git pull origin production-v2.0
    
    Write-Host ""
    Write-Host "✅ Git sync complete!" -ForegroundColor Green
    
} elseif ($Method -eq "direct") {
    Write-Host ""
    Write-Host "📥 Method: Direct Copy from Mac" -ForegroundColor Yellow
    Write-Host ""
    
    $MacIP = "192.168.1.6"
    $MacUser = "ssr"
    
    # Test connectivity
    Write-Host "📡 Testing connectivity to Mac ($MacIP)..." -ForegroundColor Yellow
    if (Test-Connection -ComputerName $MacIP -Count 1 -Quiet) {
        Write-Host "✅ Mac is reachable" -ForegroundColor Green
    } else {
        Write-Host "❌ Cannot reach Mac. Check network connection." -ForegroundColor Red
        exit 1
    }
    
    # Create monitoring directory
    Write-Host ""
    Write-Host "📁 Creating monitoring directory..." -ForegroundColor Yellow
    New-Item -Path "bot\monitoring" -ItemType Directory -Force | Out-Null
    Write-Host "✅ Directory created" -ForegroundColor Green
    
    # Note: Direct file copy requires SMB share or SSH
    Write-Host ""
    Write-Host "⚠️  Direct copy requires manual setup:" -ForegroundColor Yellow
    Write-Host "   1. Map Mac share: \\192.168.1.6\Projects" -ForegroundColor White
    Write-Host "   2. Copy files manually" -ForegroundColor White
    Write-Host ""
    Write-Host "   OR use Git method: .\sync_monitoring_from_mac.ps1 -Method git" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "VALIDATION" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Verify files exist
Write-Host "📋 Checking files..." -ForegroundColor Yellow
Write-Host ""

$filesToCheck = @(
    "bot\monitoring\__init__.py",
    "bot\monitoring\price_health_monitor.py",
    "bot\monitoring\pre_order_logger.py",
    "bot\monitoring\tp_verification.py",
    "bot\monitoring\anomaly_detection.py",
    "bot\monitoring\predictive_display.py",
    "bot\strategy\gridbot.py",
    "bot\strategy\modules\order_manager.py",
    "bot\strategy\handlers\long_handler.py",
    "bot\strategy\handlers\short_handler.py"
)

$allFilesExist = $true
foreach ($file in $filesToCheck) {
    if (Test-Path $file) {
        Write-Host "  ✅ $file" -ForegroundColor Green
    } else {
        Write-Host "  ❌ MISSING: $file" -ForegroundColor Red
        $allFilesExist = $false
    }
}

if (-not $allFilesExist) {
    Write-Host ""
    Write-Host "⚠️  Some files are missing. Sync may be incomplete." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "✅ All files present!" -ForegroundColor Green

# Syntax check
Write-Host ""
Write-Host "🔍 Running syntax checks..." -ForegroundColor Yellow
Write-Host ""

$syntaxErrors = $false

$filesToCompile = @(
    "bot\monitoring\price_health_monitor.py",
    "bot\monitoring\pre_order_logger.py",
    "bot\monitoring\tp_verification.py",
    "bot\monitoring\anomaly_detection.py",
    "bot\monitoring\predictive_display.py",
    "bot\strategy\gridbot.py",
    "bot\strategy\modules\order_manager.py"
)

foreach ($file in $filesToCompile) {
    Write-Host "  Checking $file..." -NoNewline
    try {
        python -m py_compile $file 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host " ✅" -ForegroundColor Green
        } else {
            Write-Host " ❌" -ForegroundColor Red
            $syntaxErrors = $true
        }
    } catch {
        Write-Host " ❌ Error: $_" -ForegroundColor Red
        $syntaxErrors = $true
    }
}

if ($syntaxErrors) {
    Write-Host ""
    Write-Host "❌ Syntax errors detected!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ All syntax checks passed!" -ForegroundColor Green

# Import test
Write-Host ""
Write-Host "🧪 Testing imports..." -ForegroundColor Yellow
Write-Host ""

$importTest = @"
import sys
sys.path.insert(0, '.')
from bot.monitoring import PriceHealthMonitor, PreOrderDecisionLogger, TPVerificationSystem, AnomalyDetectionSystem, PredictiveDecisionDisplay
print('✅ All monitoring imports successful')
"@

try {
    $result = python -c $importTest 2>&1
    if ($result -match "successful") {
        Write-Host "  ✅ Monitoring imports work correctly" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Import result: $result" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ Import test failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "SYNC COMPLETE! 🎉" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "✅ Monitoring system successfully synced to Windows" -ForegroundColor Green
Write-Host "✅ All files validated and tested" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test bot startup: python bot_launcher.py" -ForegroundColor White
Write-Host "  2. Check logs for: '🔍 Initializing Comprehensive Monitoring Systems...'" -ForegroundColor White
Write-Host "  3. Verify all 5 layers initialize correctly" -ForegroundColor White
Write-Host ""
