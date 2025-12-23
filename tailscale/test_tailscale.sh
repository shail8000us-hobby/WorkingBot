#!/bin/bash

# ========================================
# Tailscale Configuration Test Suite
# ========================================
# Purpose: Verify Tailscale setup and resilience
# Date: October 23, 2025
# ========================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

test_pass() {
    echo -e "${GREEN}✅ PASS:${NC} $1"
    ((PASS_COUNT++))
}

test_fail() {
    echo -e "${RED}❌ FAIL:${NC} $1"
    ((FAIL_COUNT++))
}

test_warn() {
    echo -e "${YELLOW}⚠️  WARN:${NC} $1"
    ((WARN_COUNT++))
}

test_info() {
    echo -e "${BLUE}ℹ️  INFO:${NC} $1"
}

print_header "Tailscale Configuration Test Suite"

# Test 1: Tailscale Installation
echo -e "${YELLOW}Test 1: Tailscale Installation${NC}"
if command -v tailscale &> /dev/null; then
    VERSION=$(tailscale version | head -1)
    test_pass "Tailscale installed - Version: $VERSION"
else
    test_fail "Tailscale not found"
    exit 1
fi

# Test 2: Daemon Running
echo ""
echo -e "${YELLOW}Test 2: Tailscale Daemon${NC}"
if pgrep -f tailscaled > /dev/null; then
    PID=$(pgrep -f tailscaled)
    test_pass "tailscaled process running (PID: $PID)"
else
    test_fail "tailscaled process not running"
fi

# Test 3: Service Responsive
echo ""
echo -e "${YELLOW}Test 3: Service Responsiveness${NC}"
if tailscale status > /dev/null 2>&1; then
    test_pass "Tailscale service is responsive"
else
    test_fail "Tailscale service not responding"
fi

# Test 4: Authentication Status
echo ""
echo -e "${YELLOW}Test 4: Authentication${NC}"
STATUS_OUTPUT=$(tailscale status 2>&1)
if echo "$STATUS_OUTPUT" | grep -q "Logged out"; then
    test_fail "Tailscale is logged out - run setup script"
elif tailscale status > /dev/null 2>&1; then
    test_pass "Tailscale is authenticated"
else
    test_warn "Cannot determine authentication status"
fi

# Test 5: Network Connectivity
echo ""
echo -e "${YELLOW}Test 5: Network Configuration${NC}"
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1)
if [ -n "$TAILSCALE_IP" ]; then
    test_pass "IPv4 address assigned: $TAILSCALE_IP"
else
    test_fail "No IPv4 address assigned"
fi

TAILSCALE_IPV6=$(tailscale ip -6 2>/dev/null | head -1)
if [ -n "$TAILSCALE_IPV6" ]; then
    test_pass "IPv6 address assigned: $TAILSCALE_IPV6"
else
    test_warn "No IPv6 address assigned"
fi

# Test 6: LaunchAgent Configuration
echo ""
echo -e "${YELLOW}Test 6: LaunchAgent Configuration${NC}"
if [ -f ~/Library/LaunchAgents/com.tailscale.tailscaled.plist ]; then
    test_pass "Daemon LaunchAgent found"
    
    if launchctl list | grep -q com.tailscale.tailscaled; then
        test_pass "Daemon LaunchAgent loaded"
    else
        test_fail "Daemon LaunchAgent not loaded"
    fi
else
    test_fail "Daemon LaunchAgent missing"
fi

if [ -f ~/Library/LaunchAgents/com.tailscale.watchdog.plist ]; then
    test_pass "Watchdog LaunchAgent found"
    
    if launchctl list | grep -q com.tailscale.watchdog; then
        test_pass "Watchdog LaunchAgent loaded"
    else
        test_fail "Watchdog LaunchAgent not loaded"
    fi
else
    test_fail "Watchdog LaunchAgent missing"
fi

# Test 7: Watchdog Script
echo ""
echo -e "${YELLOW}Test 7: Watchdog Script${NC}"
WATCHDOG_SCRIPT="/Users/shailendrasinghrajawat/Projects/WorkingBot/tailscale/tailscale_watchdog.sh"
if [ -f "$WATCHDOG_SCRIPT" ]; then
    test_pass "Watchdog script found"
    
    if [ -x "$WATCHDOG_SCRIPT" ]; then
        test_pass "Watchdog script is executable"
    else
        test_fail "Watchdog script not executable"
    fi
else
    test_fail "Watchdog script missing"
fi

# Test 8: Log Files
echo ""
echo -e "${YELLOW}Test 8: Log Files${NC}"
if [ -d /opt/homebrew/var/log ]; then
    test_pass "Log directory exists"
else
    test_fail "Log directory missing"
fi

if [ -f /opt/homebrew/var/log/tailscaled.log ]; then
    SIZE=$(stat -f%z /opt/homebrew/var/log/tailscaled.log)
    test_pass "Daemon log exists (${SIZE} bytes)"
else
    test_warn "Daemon log not created yet"
fi

if [ -f /opt/homebrew/var/log/tailscale_watchdog.log ]; then
    SIZE=$(stat -f%z /opt/homebrew/var/log/tailscale_watchdog.log)
    test_pass "Watchdog log exists (${SIZE} bytes)"
else
    test_warn "Watchdog log not created yet"
fi

# Test 9: SSH Configuration
echo ""
echo -e "${YELLOW}Test 9: SSH Configuration${NC}"
if tailscale status --json 2>/dev/null | grep -q '"RunSSH":true'; then
    test_pass "Tailscale SSH is enabled"
else
    test_warn "Tailscale SSH may not be enabled"
fi

# Test 10: MagicDNS
echo ""
echo -e "${YELLOW}Test 10: MagicDNS${NC}"
MAGICDNS=$(tailscale status --json 2>/dev/null | grep -o '"DNSName":"[^"]*"' | cut -d'"' -f4 | head -1)
if [ -n "$MAGICDNS" ]; then
    test_pass "MagicDNS hostname: $MAGICDNS"
else
    test_warn "MagicDNS hostname not found"
fi

# Test 11: Connection to Tailnet
echo ""
echo -e "${YELLOW}Test 11: Tailnet Connection${NC}"
PEER_COUNT=$(tailscale status 2>/dev/null | grep -v "^#" | wc -l | xargs)
if [ "$PEER_COUNT" -gt 0 ]; then
    test_pass "Connected to tailnet with $PEER_COUNT peers"
else
    test_warn "No other peers visible (may be normal if you're the only device)"
fi

# Test 12: Watchdog Functionality
echo ""
echo -e "${YELLOW}Test 12: Watchdog Functionality${NC}"
test_info "Running watchdog script..."
if bash "$WATCHDOG_SCRIPT" > /dev/null 2>&1; then
    test_pass "Watchdog script executed successfully"
    
    if [ -f /opt/homebrew/var/log/tailscale_watchdog.log ]; then
        LAST_CHECK=$(tail -1 /opt/homebrew/var/log/tailscale_watchdog.log)
        test_info "Last check: $LAST_CHECK"
    fi
else
    test_fail "Watchdog script failed"
fi

# Test 13: KeepAlive Configuration
echo ""
echo -e "${YELLOW}Test 13: KeepAlive Configuration${NC}"
if grep -q "<key>KeepAlive</key>" ~/Library/LaunchAgents/com.tailscale.tailscaled.plist; then
    test_pass "KeepAlive configured in daemon plist"
else
    test_warn "KeepAlive not found in daemon plist"
fi

# Test 14: RunAtLoad Configuration
echo ""
echo -e "${YELLOW}Test 14: Auto-Start Configuration${NC}"
if grep -q "<key>RunAtLoad</key>" ~/Library/LaunchAgents/com.tailscale.tailscaled.plist; then
    test_pass "RunAtLoad configured (will start at login)"
else
    test_warn "RunAtLoad not configured"
fi

# Summary
print_header "Test Summary"
echo -e "Total Tests: $((PASS_COUNT + FAIL_COUNT + WARN_COUNT))"
echo -e "${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "${RED}Failed: $FAIL_COUNT${NC}"
echo -e "${YELLOW}Warnings: $WARN_COUNT${NC}"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✅ ALL CRITICAL TESTS PASSED!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${GREEN}Your Tailscale setup is properly configured.${NC}"
    
    if [ $WARN_COUNT -gt 0 ]; then
        echo -e "${YELLOW}Note: $WARN_COUNT warning(s) - review above for details${NC}"
    fi
    
    exit 0
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "${RED}Please review the failures above and run setup again.${NC}"
    exit 1
fi
