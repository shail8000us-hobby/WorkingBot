# ============================================================================
# GridBot Windows Sync Script - Pull Changes from Mac
# Run this on Windows to sync latest changes from Mac
# ============================================================================

$MacIP = "192.168.1.3"
$MacUser = "ssr"
$MacPath = "/Users/ssr/Projects/WorkingBot"
$WindowsPath = "D:\Projects\WorkingBot"

Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     GridBot Windows ← Mac Sync (November 9, 2025 Updates)     ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "Mac IP: $MacIP" -ForegroundColor Yellow
Write-Host "Windows Target: $WindowsPath" -ForegroundColor Yellow
Write-Host ""

# Step 1: Backup current files
Write-Host "[1/5] Creating backup..." -ForegroundColor Green
$BackupDir = "$WindowsPath\backups\pre_nov9_fixes_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$FilesToBackup = @(
    "bot\strategy\modules\position_manager.py",
    "bot\strategy\modules\reconciliation.py",
    "bot\strategy\handlers\long_handler.py",
    "bot\strategy\gridbot.py"
)

foreach ($file in $FilesToBackup) {
    $source = Join-Path $WindowsPath $file
    if (Test-Path $source) {
        $dest = Join-Path $BackupDir $file
        $destDir = Split-Path $dest -Parent
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        Copy-Item $source $dest -Force
        Write-Host "  ✓ Backed up: $file" -ForegroundColor Gray
    }
}
Write-Host "  ✅ Backup complete: $BackupDir" -ForegroundColor Green
Write-Host ""

# Step 2: List of files to sync
Write-Host "[2/5] Files to sync from Mac:" -ForegroundColor Green
$FilesToSync = @(
    "bot/strategy/modules/position_manager.py",
    "bot/strategy/modules/reconciliation.py",
    "bot/strategy/handlers/long_handler.py",
    "bot/strategy/gridbot.py",
    "OFFGRID_TRADE_BUG_NOV9_2025.md",
    "DEADLOCK_BUG_FILL_PROCESSING_NOV9_2025.md",
    "CRITICAL_BUG_MISSING_TP_NOV9_2025.md",
    "WEBSOCKET_FIX_COMPLETE_NOV9_2025.md",
    "WINDOWS_SYNC_NOV9_2025.md"
)

foreach ($file in $FilesToSync) {
    Write-Host "  • $file" -ForegroundColor Gray
}
Write-Host ""

# Step 3: Sync method selection
Write-Host "[3/5] Sync Method:" -ForegroundColor Green
Write-Host "  Please use ONE of these methods:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Option A: SMB Mount" -ForegroundColor Cyan
Write-Host "    1. Open File Explorer" -ForegroundColor Gray
Write-Host "    2. Type in address bar: \\$MacIP\Projects" -ForegroundColor Gray
Write-Host "    3. Navigate to WorkingBot folder" -ForegroundColor Gray
Write-Host "    4. Copy these files to $WindowsPath" -ForegroundColor Gray
Write-Host ""
Write-Host "  Option B: Use WinSCP or FileZilla" -ForegroundColor Cyan
Write-Host "    1. Connect to $MacIP" -ForegroundColor Gray
Write-Host "    2. Navigate to $MacPath" -ForegroundColor Gray
Write-Host "    3. Download files listed above" -ForegroundColor Gray
Write-Host ""
Write-Host "  Option C: Use rsync (if installed)" -ForegroundColor Cyan
Write-Host "    rsync -avz ${MacUser}@${MacIP}:$MacPath/ $WindowsPath/ --files-from=sync_files.txt" -ForegroundColor Gray
Write-Host ""

Read-Host "Press Enter after you've copied the files manually..."

# Step 4: Verify changes
Write-Host ""
Write-Host "[4/5] Verifying changes..." -ForegroundColor Green

$VerificationChecks = @{
    "position_manager.py has RLock" = @{
        File = "bot\strategy\modules\position_manager.py"
        Pattern = "RLock"
    }
    "reconciliation.py has post_only" = @{
        File = "bot\strategy\modules\reconciliation.py"
        Pattern = "post_only=True"
    }
    "long_handler.py has set_pending_buy" = @{
        File = "bot\strategy\handlers\long_handler.py"
        Pattern = "set_pending_buy"
    }
    "gridbot.py has post_only" = @{
        File = "bot\strategy\gridbot.py"
        Pattern = "post_only=True"
    }
}

$AllChecksPass = $true

foreach ($check in $VerificationChecks.GetEnumerator()) {
    $filePath = Join-Path $WindowsPath $check.Value.File
    if (Test-Path $filePath) {
        $content = Get-Content $filePath -Raw
        if ($content -match $check.Value.Pattern) {
            Write-Host "  ✅ $($check.Key)" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $($check.Key)" -ForegroundColor Red
            $AllChecksPass = $false
        }
    } else {
        Write-Host "  ⚠️  File not found: $($check.Value.File)" -ForegroundColor Yellow
        $AllChecksPass = $false
    }
}

Write-Host ""

if ($AllChecksPass) {
    Write-Host "[5/5] ✅ All verifications passed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Restart the bot: pm2 restart gridbot-live" -ForegroundColor Gray
    Write-Host "  2. Monitor logs for first fill" -ForegroundColor Gray
    Write-Host "  3. Verify TP and next order placement" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Read WINDOWS_SYNC_NOV9_2025.md for complete instructions" -ForegroundColor Yellow
} else {
    Write-Host "[5/5] ⚠️  Some verifications failed!" -ForegroundColor Red
    Write-Host "  Please check:" -ForegroundColor Yellow
    Write-Host "    - Files were copied correctly" -ForegroundColor Gray
    Write-Host "    - No copy errors occurred" -ForegroundColor Gray
    Write-Host "    - File paths are correct" -ForegroundColor Gray
    Write-Host ""
    Write-Host "You can restore from backup if needed:" -ForegroundColor Yellow
    Write-Host "  Copy-Item $BackupDir\* $WindowsPath -Recurse -Force" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Backup location: $BackupDir" -ForegroundColor Cyan
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
