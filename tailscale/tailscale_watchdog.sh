#!/bin/bash

# ========================================
# Tailscale Watchdog Script
# ========================================
# Purpose: Monitor Tailscale health and auto-reconnect
# Runs: Every 60 seconds via LaunchAgent
# Author: Automated Setup
# Date: October 23, 2025
# ========================================

LOG_FILE="/opt/homebrew/var/log/tailscale_watchdog.log"
MAX_LOG_SIZE=10485760  # 10MB

# Rotate log if too large
if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Log rotated" > "$LOG_FILE"
fi

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

log "=== Tailscale Watchdog Check Started ==="

# Check if tailscaled is running
if ! pgrep -f tailscaled > /dev/null; then
    log "❌ tailscaled process not found - attempting to start via brew services"
    /opt/homebrew/bin/brew services restart tailscale >> "$LOG_FILE" 2>&1
    sleep 5
fi

# Check if Tailscale is responsive
if ! /opt/homebrew/bin/tailscale status > /dev/null 2>&1; then
    log "⚠️  Tailscale not responsive - checking status"
    
    # Try to get more info
    STATUS=$(/opt/homebrew/bin/tailscale status 2>&1)
    log "Status output: $STATUS"
    
    # If not logged in, log it but don't try to auto-login (requires manual auth)
    if echo "$STATUS" | grep -q "Logged out"; then
        log "🔐 Tailscale is logged out - manual authentication required"
        log "Run: tailscale up --ssh --accept-dns --accept-routes --advertise-tags=tag:botserver"
        exit 0
    fi
    
    # If connection issue, restart daemon
    log "🔄 Attempting to restart Tailscale service"
    /opt/homebrew/bin/brew services restart tailscale >> "$LOG_FILE" 2>&1
    sleep 5
    
    # Check again
    if /opt/homebrew/bin/tailscale status > /dev/null 2>&1; then
        log "✅ Tailscale reconnected successfully"
    else
        log "❌ Tailscale still not responsive after restart"
    fi
else
    # Connection is good - log status
    TAILSCALE_IP=$(/opt/homebrew/bin/tailscale ip -4 2>/dev/null | head -1)
    TAILSCALE_HOSTNAME=$(/opt/homebrew/bin/tailscale status --json 2>/dev/null | grep -o '"HostName":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$TAILSCALE_IP" ]; then
        log "✅ Tailscale healthy - IP: $TAILSCALE_IP, Hostname: $TAILSCALE_HOSTNAME"
    else
        log "⚠️  Tailscale responsive but no IP assigned"
    fi
fi

# Check network connectivity on sleep/wake
NETWORK_CHANGED=$(ifconfig | grep -E "inet |status: active" | md5)
LAST_NETWORK=$(cat /tmp/tailscale_network_state 2>/dev/null || echo "")

if [ "$NETWORK_CHANGED" != "$LAST_NETWORK" ]; then
    log "🔄 Network change detected - verifying Tailscale connection"
    echo "$NETWORK_CHANGED" > /tmp/tailscale_network_state
    
    # Give network time to stabilize
    sleep 3
    
    # Force a ping to ensure connection is active
    if /opt/homebrew/bin/tailscale status > /dev/null 2>&1; then
        log "✅ Tailscale connection verified after network change"
    else
        log "⚠️  Network changed but Tailscale not responding - restarting"
        /opt/homebrew/bin/brew services restart tailscale >> "$LOG_FILE" 2>&1
    fi
fi

log "=== Watchdog Check Complete ==="
