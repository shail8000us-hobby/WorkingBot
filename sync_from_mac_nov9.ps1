# ============================================================================
# Windows Sync Script - Pull Latest from Mac (via Git)
# ============================================================================
# 
# This script pulls the latest changes from the Mac and sets up the environment
# 
# Usage: Right-click → Run with PowerShell
# Or: .\sync_from_mac_nov9.ps1
#
# ============================================================================

# Colors
$GREEN = "Green"
$RED = "Red"
$YELLOW = "Yellow"
$CYAN = "Cyan"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor $CYAN
Write-Host "   Windows Sync - Pull Latest from Mac (Nov 9, 2025)" -ForegroundColor $CYAN
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor $CYAN
Write-Host ""

# Configuration
$PROJECT_DIR = "D:\WorkingBot"
$BRANCH = "production-v2.0"

# Check if directory exists
if (-not (Test-Path $PROJECT_DIR)) {
    Write-Host "❌ Error: WorkingBot directory not found at $PROJECT_DIR" -ForegroundColor $RED
    Write-Host ""
    Write-Host "Please clone the repository first:" -ForegroundColor $YELLOW
    Write-Host "  cd D:\" -ForegroundColor $YELLOW
    Write-Host "  git clone https://github.com/physicsssr/Working-gridBOT.git WorkingBot" -ForegroundColor $YELLOW
    Write-Host "  cd WorkingBot" -ForegroundColor $YELLOW
    Write-Host "  git checkout production-v2.0" -ForegroundColor $YELLOW
    Write-Host ""
    exit 1
}

# Navigate to project
Set-Location $PROJECT_DIR

Write-Host "📁 Project Directory: $PROJECT_DIR" -ForegroundColor $CYAN
Write-Host ""

# Step 1: Check current status
Write-Host "1️⃣  Checking Git status..." -ForegroundColor $YELLOW
Write-Host ""

$gitStatus = git status --short
if ($gitStatus) {
    Write-Host "⚠️  Uncommitted changes detected:" -ForegroundColor $YELLOW
    git status --short | ForEach-Object { Write-Host "   $_" -ForegroundColor $YELLOW }
    Write-Host ""
    
    $response = Read-Host "Stash changes before pulling? (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        Write-Host "💾 Stashing changes..." -ForegroundColor $CYAN
        git stash save "Auto-stash before sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
        Write-Host "✅ Changes stashed" -ForegroundColor $GREEN
        Write-Host ""
    }
}

# Step 2: Pull latest changes
Write-Host "2️⃣  Pulling latest changes from $BRANCH..." -ForegroundColor $YELLOW
Write-Host ""

try {
    git pull origin $BRANCH
    Write-Host ""
    Write-Host "✅ Git pull successful!" -ForegroundColor $GREEN
} catch {
    Write-Host "❌ Git pull failed: $_" -ForegroundColor $RED
    exit 1
}

Write-Host ""

# Step 3: Check if dependencies need updating
Write-Host "3️⃣  Checking dependencies..." -ForegroundColor $YELLOW
Write-Host ""

$updateDeps = Read-Host "Update Python dependencies? (y/n)"
if ($updateDeps -eq "y" -or $updateDeps -eq "Y") {
    Write-Host "📦 Installing Python dependencies..." -ForegroundColor $CYAN
    pip install -r requirements.txt
    Write-Host "✅ Python dependencies updated" -ForegroundColor $GREEN
    Write-Host ""
}

$updateNode = Read-Host "Update Node dependencies? (y/n)"
if ($updateNode -eq "y" -or $updateNode -eq "Y") {
    Write-Host "📦 Installing Node dependencies..." -ForegroundColor $CYAN
    Set-Location "$PROJECT_DIR\webui\frontend"
    npm install
    Write-Host "✅ Node dependencies updated" -ForegroundColor $GREEN
    Set-Location $PROJECT_DIR
    Write-Host ""
}

# Step 4: Check if frontend needs rebuilding
$rebuildFrontend = Read-Host "Rebuild frontend? (y/n)"
if ($rebuildFrontend -eq "y" -or $rebuildFrontend -eq "Y") {
    Write-Host "🔨 Building frontend..." -ForegroundColor $CYAN
    Set-Location "$PROJECT_DIR\webui\frontend"
    npm run build
    Write-Host "✅ Frontend built successfully" -ForegroundColor $GREEN
    Set-Location $PROJECT_DIR
    Write-Host ""
}

# Step 5: Show what's new
Write-Host "4️⃣  New files from Mac:" -ForegroundColor $YELLOW
Write-Host ""

Write-Host "📜 New Scripts:" -ForegroundColor $CYAN
$scripts = @(
    "bot_command_center.sh",
    "fix_bot_instance_lock.sh", 
    "watch_bot_logs.sh",
    "sync_backend_frontend.sh",
    "PM2_LOG_COMMANDS.sh",
    "disable_telegram_alerts.sh"
)

foreach ($script in $scripts) {
    if (Test-Path $script) {
        Write-Host "   ✅ $script" -ForegroundColor $GREEN
    } else {
        Write-Host "   ⚠️  $script (not found)" -ForegroundColor $YELLOW
    }
}

Write-Host ""
Write-Host "📚 New Documentation:" -ForegroundColor $CYAN
$docs = @(
    "BOT_RESTART_COMMANDS_UPDATE_NOV9_2025.md",
    "BOT_INSTANCE_LOCK_FIX_ANALYSIS.md",
    "FIX_TELEGRAM_404_ERRORS.md",
    "BACKEND_FRONTEND_BOT_LOGS_QUICK_REF.md"
)

foreach ($doc in $docs) {
    if (Test-Path $doc) {
        Write-Host "   ✅ $doc" -ForegroundColor $GREEN
    } else {
        Write-Host "   ⚠️  $doc (not found)" -ForegroundColor $YELLOW
    }
}

Write-Host ""

# Step 6: Check PM2 status
Write-Host "5️⃣  Checking PM2 status..." -ForegroundColor $YELLOW
Write-Host ""

try {
    $pm2List = pm2 list 2>&1
    if ($LASTEXITCODE -eq 0) {
        pm2 list
        Write-Host ""
        
        $restartBot = Read-Host "Restart PM2 processes? (y/n)"
        if ($restartBot -eq "y" -or $restartBot -eq "Y") {
            Write-Host "🔄 Restarting PM2 processes..." -ForegroundColor $CYAN
            pm2 restart all
            Write-Host "✅ PM2 processes restarted" -ForegroundColor $GREEN
        }
    } else {
        Write-Host "⚠️  PM2 not running or not installed" -ForegroundColor $YELLOW
        Write-Host "   Install with: npm install -g pm2" -ForegroundColor $CYAN
    }
} catch {
    Write-Host "⚠️  PM2 not available" -ForegroundColor $YELLOW
}

Write-Host ""

# Step 7: Summary
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor $CYAN
Write-Host "   Sync Complete!" -ForegroundColor $GREEN
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor $CYAN
Write-Host ""

Write-Host "📋 Next Steps:" -ForegroundColor $YELLOW
Write-Host ""
Write-Host "1. View new documentation:" -ForegroundColor $CYAN
Write-Host "   notepad BOT_RESTART_COMMANDS_UPDATE_NOV9_2025.md" -ForegroundColor $CYAN
Write-Host ""
Write-Host "2. Start bot (if not running):" -ForegroundColor $CYAN
Write-Host "   pm2 start gridbot-live" -ForegroundColor $CYAN
Write-Host ""
Write-Host "3. Check status:" -ForegroundColor $CYAN
Write-Host "   pm2 status" -ForegroundColor $CYAN
Write-Host ""
Write-Host "4. View logs:" -ForegroundColor $CYAN
Write-Host "   pm2 logs gridbot-live --lines 50" -ForegroundColor $CYAN
Write-Host ""
Write-Host "5. Access WebUI:" -ForegroundColor $CYAN
Write-Host "   http://localhost:5555" -ForegroundColor $CYAN
Write-Host ""

Write-Host "✅ All systems ready!" -ForegroundColor $GREEN
Write-Host ""
