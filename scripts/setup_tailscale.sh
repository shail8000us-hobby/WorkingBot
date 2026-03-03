#!/bin/bash

# Tailscale Setup Script for GridBot
# This script will set up Tailscale and get your connection details

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                          ║"
echo "║          🚀 TAILSCALE SETUP SCRIPT                                       ║"
echo "║                                                                          ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if Tailscale is installed
if ! command -v /opt/homebrew/bin/tailscale &> /dev/null; then
    echo "❌ Tailscale is not installed!"
    echo "Please install it first with: brew install tailscale"
    exit 1
fi

echo "✅ Tailscale is installed!"
echo ""

# Check if tailscaled is running
if ! pgrep -x "tailscaled" > /dev/null; then
    echo "📱 Starting Tailscale daemon..."
    echo "   (You'll need to enter your password)"
    echo ""
    
    # Start tailscaled in background
    sudo /opt/homebrew/opt/tailscale/bin/tailscaled &
    DAEMON_PID=$!
    
    echo "✅ Tailscale daemon started (PID: $DAEMON_PID)"
    echo ""
    
    # Wait for daemon to be ready
    echo "⏳ Waiting for daemon to be ready..."
    sleep 3
else
    echo "✅ Tailscale daemon is already running!"
    echo ""
fi

# Check if already connected
if /opt/homebrew/bin/tailscale status &> /dev/null; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ YOU'RE ALREADY CONNECTED TO TAILSCALE!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Get Tailscale IP
    TAILSCALE_IP=$(/opt/homebrew/bin/tailscale ip -4 2>/dev/null)
    
    if [ -n "$TAILSCALE_IP" ]; then
        echo "📱 Your Tailscale IP: $TAILSCALE_IP"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "🎉 TO ACCESS YOUR BOT FROM YOUR PHONE:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "1. Open Tailscale app on your phone"
        echo "2. Sign in with the same account"
        echo "3. Tap 'Connect'"
        echo "4. Open browser on your phone"
        echo "5. Go to: http://$TAILSCALE_IP:5555"
        echo ""
        echo "🚀 You'll see your bot's Web UI on your phone!"
        echo ""
    else
        echo "⚠️  Could not get Tailscale IP"
    fi
    
    # Show connection status
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 TAILSCALE STATUS:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    /opt/homebrew/bin/tailscale status
    
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔐 CONNECTING TO TAILSCALE..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "This will open your browser for authentication."
    echo "Please sign in with Google, Microsoft, GitHub, or Email."
    echo ""
    
    # Connect to Tailscale
    /opt/homebrew/bin/tailscale up
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ SUCCESSFULLY CONNECTED TO TAILSCALE!"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        # Get Tailscale IP
        sleep 2
        TAILSCALE_IP=$(/opt/homebrew/bin/tailscale ip -4 2>/dev/null)
        
        if [ -n "$TAILSCALE_IP" ]; then
            echo "📱 Your Tailscale IP: $TAILSCALE_IP"
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "🎉 TO ACCESS YOUR BOT FROM YOUR PHONE:"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "1. Open Tailscale app on your phone"
            echo "2. Sign in with the same account"
            echo "3. Tap 'Connect'"
            echo "4. Open browser on your phone"
            echo "5. Go to: http://$TAILSCALE_IP:5555"
            echo ""
            echo "🚀 You'll see your bot's Web UI on your phone!"
            echo ""
            
            # Save IP to file for easy reference
            echo "$TAILSCALE_IP" > ~/.tailscale_ip
            echo "💾 IP saved to ~/.tailscale_ip for future reference"
            echo ""
        fi
    else
        echo ""
        echo "❌ Failed to connect to Tailscale"
        echo "Please try running: /opt/homebrew/bin/tailscale up"
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💡 USEFUL COMMANDS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Check status:      /opt/homebrew/bin/tailscale status"
echo "Get IP:            /opt/homebrew/bin/tailscale ip -4"
echo "Disconnect:        /opt/homebrew/bin/tailscale down"
echo "Reconnect:         /opt/homebrew/bin/tailscale up"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

