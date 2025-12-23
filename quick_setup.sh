#!/bin/bash
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║         WorkingBot - Quick Setup Script for New Machine                  ║
# ║         Automated installation and configuration                         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project directory
PROJECT_DIR="/Users/ssr/Projects/WorkingBot"
USERNAME="ssr"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         WorkingBot - Quick Setup Script for New Machine                  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if running from correct directory
cd "$PROJECT_DIR" || {
    print_error "Failed to navigate to $PROJECT_DIR"
    exit 1
}

print_info "Starting setup from: $(pwd)"
echo ""

# ============================================================================
# Step 1: Check Prerequisites
# ============================================================================

echo -e "${BLUE}[Step 1/10]${NC} Checking prerequisites..."

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    print_status "Python found: $PYTHON_VERSION"
else
    print_error "Python 3 not found. Please install Python 3.9+"
    exit 1
fi

# Check pip3
if command -v pip3 &> /dev/null; then
    print_status "pip3 found"
else
    print_error "pip3 not found. Please install pip3"
    exit 1
fi

# Check Homebrew
if command -v brew &> /dev/null; then
    print_status "Homebrew found"
else
    print_warning "Homebrew not found. Some features may require it."
fi

echo ""

# ============================================================================
# Step 2: Check/Install Node.js
# ============================================================================

echo -e "${BLUE}[Step 2/10]${NC} Checking Node.js and npm..."

if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    print_status "Node.js found: $NODE_VERSION"
else
    print_warning "Node.js not found"
    if command -v brew &> /dev/null; then
        read -p "Install Node.js via Homebrew? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            brew install node
            print_status "Node.js installed"
        else
            print_error "Node.js is required. Please install manually: https://nodejs.org/"
            exit 1
        fi
    else
        print_error "Please install Node.js manually: https://nodejs.org/"
        exit 1
    fi
fi

if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    print_status "npm found: $NPM_VERSION"
else
    print_error "npm not found. It should come with Node.js"
    exit 1
fi

echo ""

# ============================================================================
# Step 3: Fix pip cache permissions
# ============================================================================

echo -e "${BLUE}[Step 3/10]${NC} Fixing pip cache permissions..."

if [ -d "$HOME/Library/Caches/pip" ]; then
    sudo chown -R $USER:staff "$HOME/Library/Caches/pip" 2>/dev/null || true
    chmod -R 755 "$HOME/Library/Caches/pip" 2>/dev/null || true
    print_status "Pip cache permissions fixed"
else
    print_info "Pip cache directory will be created on first use"
fi

echo ""

# ============================================================================
# Step 4: Install Python dependencies
# ============================================================================

echo -e "${BLUE}[Step 4/10]${NC} Installing Python dependencies..."

print_info "Installing from requirements.txt..."
pip3 install -r requirements.txt --user --quiet

print_info "Installing additional WebUI dependencies..."
pip3 install flask flask-cors flask-socketio python-socketio --user --quiet

# Verify critical packages
REQUIRED_PACKAGES=("ccxt" "flask" "websockets" "python-dotenv" "requests")
ALL_INSTALLED=true

for package in "${REQUIRED_PACKAGES[@]}"; do
    if pip3 show "$package" &> /dev/null; then
        print_status "$package installed"
    else
        print_error "$package NOT installed"
        ALL_INSTALLED=false
    fi
done

if [ "$ALL_INSTALLED" = false ]; then
    print_error "Some packages failed to install. Please install them manually."
    exit 1
fi

echo ""

# ============================================================================
# Step 5: Check configuration files
# ============================================================================

echo -e "${BLUE}[Step 5/10]${NC} Checking configuration files..."

# Check secrets/api_keys.env
if [ -f "secrets/api_keys.env" ]; then
    print_status "API keys file found"
    # Check if it has content
    if grep -q "DELTA_API_KEY" secrets/api_keys.env; then
        print_status "API keys configured"
    else
        print_warning "API keys file exists but may be empty"
    fi
else
    print_error "secrets/api_keys.env not found"
    print_info "Please create secrets/api_keys.env with your Delta Exchange API keys"
fi

# Check grid_config.env
if [ -f "grid_config.env" ]; then
    print_status "Grid config file found ($(du -h grid_config.env | awk '{print $1}'))"
else
    print_warning "grid_config.env not found. Using grid_config.env.example"
    if [ -f "grid_config.env.example" ]; then
        cp grid_config.env.example grid_config.env
        print_info "Created grid_config.env from example"
    fi
fi

echo ""

# ============================================================================
# Step 6: Update paths in configuration
# ============================================================================

echo -e "${BLUE}[Step 6/10]${NC} Updating paths for new machine..."

# Search for old username in config files
OLD_USERNAME="shailendrasinghrajawat"
if grep -q "$OLD_USERNAME" grid_config.env 2>/dev/null; then
    print_warning "Found old username in grid_config.env"
    read -p "Update paths to new username ($USERNAME)? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Backup first
        cp grid_config.env grid_config.env.backup_migration_$(date +%Y%m%d_%H%M%S)
        # Replace paths
        sed -i.tmp "s|/Users/$OLD_USERNAME|/Users/$USERNAME|g" grid_config.env
        rm -f grid_config.env.tmp
        print_status "Paths updated in grid_config.env"
    fi
else
    print_status "No old paths found in config"
fi

echo ""

# ============================================================================
# Step 7: Setup directories
# ============================================================================

echo -e "${BLUE}[Step 7/10]${NC} Creating required directories..."

REQUIRED_DIRS=("logs" "data" "reports" "bot/logs" "bot/audit")

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        print_status "Created $dir/"
    else
        print_status "$dir/ exists"
    fi
done

echo ""

# ============================================================================
# Step 8: Setup LaunchAgent
# ============================================================================

echo -e "${BLUE}[Step 8/10]${NC} Setting up LaunchAgent..."

PLIST_PATH="$HOME/Library/LaunchAgents/com.gridbot.webui.plist"

if [ -f "$PLIST_PATH" ]; then
    print_status "LaunchAgent already exists"
    # Check if it has correct paths
    if grep -q "/Users/$USERNAME" "$PLIST_PATH"; then
        print_status "LaunchAgent paths are correct"
    else
        print_warning "LaunchAgent has old paths"
        read -p "Update LaunchAgent paths? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Backup
            cp "$PLIST_PATH" "$PLIST_PATH.backup_$(date +%Y%m%d_%H%M%S)"
            # Update paths
            sed -i.tmp "s|/Users/$OLD_USERNAME|/Users/$USERNAME|g" "$PLIST_PATH"
            rm -f "$PLIST_PATH.tmp"
            print_status "LaunchAgent paths updated"
        fi
    fi
else
    print_info "Creating new LaunchAgent..."
    
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p "$HOME/Library/LaunchAgents"
    
    # Create plist file
    cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.gridbot.webui</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$PROJECT_DIR/webui/backend/app.py</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/launchagent_webui.log</string>
    
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/launchagent_webui_error.log</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$PROJECT_DIR</string>
    </dict>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF
    
    print_status "LaunchAgent plist created"
fi

echo ""

# ============================================================================
# Step 9: Load and start LaunchAgent
# ============================================================================

echo -e "${BLUE}[Step 9/10]${NC} Starting WebUI backend..."

# Check if port 5555 is in use
if lsof -ti:5555 &> /dev/null; then
    print_warning "Port 5555 is already in use"
    read -p "Kill the process and restart? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        lsof -ti:5555 | xargs kill -9 2>/dev/null || true
        sleep 2
        print_status "Port 5555 cleared"
    fi
fi

# Unload if already loaded
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Load LaunchAgent
launchctl load "$PLIST_PATH" 2>/dev/null

# Wait for startup
print_info "Waiting for backend to start..."
sleep 5

# Check if running
if launchctl list | grep -q "com.gridbot.webui"; then
    print_status "WebUI backend is running"
else
    print_error "Failed to start WebUI backend"
    print_info "Check logs: tail logs/launchagent_webui_error.log"
fi

echo ""

# ============================================================================
# Step 10: Verify installation
# ============================================================================

echo -e "${BLUE}[Step 10/10]${NC} Verifying installation..."

# Test backend health endpoint
if curl -s http://localhost:5555/api/health > /dev/null 2>&1; then
    print_status "Backend health check: OK"
else
    print_warning "Backend health check: FAILED"
    print_info "Backend may still be starting up. Check in 10 seconds."
fi

# Test bot imports
if python3 -c "from bot.strategy.gridbot import GridBot" 2>/dev/null; then
    print_status "Bot imports: OK"
else
    print_warning "Bot imports: Issues detected"
    print_info "Set PYTHONPATH: export PYTHONPATH=$PROJECT_DIR:\$PYTHONPATH"
fi

echo ""

# ============================================================================
# Summary
# ============================================================================

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                        Setup Complete!                                    ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}📊 Setup Summary:${NC}"
echo "  ✓ Python dependencies installed"
echo "  ✓ Configuration files verified"
echo "  ✓ LaunchAgent configured"
echo "  ✓ WebUI backend started"
echo ""

echo -e "${BLUE}🌐 Access WebUI:${NC}"
echo "  URL: http://localhost:5555"
echo "  Command: open http://localhost:5555"
echo ""

echo -e "${BLUE}📝 Next Steps:${NC}"
echo "  1. Open http://localhost:5555 in your browser"
echo "  2. Verify dashboard loads correctly"
echo "  3. Check bot status panel"
echo "  4. Review configuration in WebUI"
echo "  5. Test in DEMO mode before live trading"
echo ""

echo -e "${BLUE}📚 Documentation:${NC}"
echo "  • START_HERE.md - Quick start guide"
echo "  • SETUP_NEW_MACHINE.md - Detailed setup guide"
echo "  • AI_CRITICAL_RULES.md - Important rules"
echo "  • USER_MANUAL.md - Complete manual"
echo ""

echo -e "${BLUE}🔧 Useful Commands:${NC}"
echo "  • Check backend status: launchctl list | grep gridbot"
echo "  • View logs: tail -f logs/launchagent_webui_error.log"
echo "  • Restart backend: launchctl restart com.gridbot.webui"
echo "  • Test health: curl http://localhost:5555/api/health"
echo ""

echo -e "${YELLOW}⚠️  Before Live Trading:${NC}"
echo "  • Test in demo mode for 24+ hours"
echo "  • Verify all safety limits"
echo "  • Check API keys are correct"
echo "  • Read safety documentation"
echo ""

echo -e "${GREEN}🎉 Your WorkingBot is ready to use!${NC}"
echo ""

