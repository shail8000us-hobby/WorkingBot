#!/bin/bash
# ============================================================================
# MAC STATIC IP CONFIGURATION SCRIPT
# ============================================================================
# Purpose: Set Mac to static IP 192.168.1.6 for stable Windows-Mac connection
# Date: November 7, 2025
# Network: 192.168.1.x subnet
# ============================================================================

echo "🖥️  MAC STATIC IP SETUP - Setting IP to 192.168.1.6"
echo "=" | head -c 80 | tr ' ' '='
echo ""

# Detect active network interface
echo "🔍 Detecting active network interface..."
INTERFACE=$(networksetup -listallnetworkservices | grep -v "^\*" | grep -i "wi-fi\|ethernet")

if [ -z "$INTERFACE" ]; then
    echo "❌ No active network interface found!"
    exit 1
fi

echo "✅ Active interface: $INTERFACE"
echo ""

# Show current configuration
echo "📊 Current Configuration:"
networksetup -getinfo "$INTERFACE"
echo ""

# Confirm before proceeding
read -p "⚠️  This will change your IP to STATIC 192.168.1.6. Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "❌ Cancelled by user"
    exit 0
fi

echo ""
echo "⚙️  Configuring static IP..."

# Set static IP configuration
# Syntax: networksetup -setmanual <service> <ip> <subnet> <router>
sudo networksetup -setmanual "$INTERFACE" 192.168.1.6 255.255.255.0 192.168.1.1

if [ $? -eq 0 ]; then
    echo "✅ Static IP configured successfully!"
else
    echo "❌ Failed to set static IP"
    exit 1
fi

# Set DNS servers (using common DNS)
echo "🌐 Setting DNS servers..."
sudo networksetup -setdnsservers "$INTERFACE" 8.8.8.8 8.8.4.4 192.168.1.1

# Verify configuration
echo ""
echo "=" | head -c 80 | tr ' ' '='
echo "✅ NEW CONFIGURATION:"
echo "=" | head -c 80 | tr ' ' '='
networksetup -getinfo "$INTERFACE"

echo ""
echo "📡 Network Details:"
echo "   Mac IP:      192.168.1.6 (STATIC)"
echo "   Windows IP:  192.168.1.32"
echo "   Subnet:      255.255.255.0"
echo "   Gateway:     192.168.1.1"
echo "   DNS:         8.8.8.8, 8.8.4.4, 192.168.1.1"
echo ""

# Test connectivity
echo "🔌 Testing connectivity to Windows..."
if ping -c 2 192.168.1.32 > /dev/null 2>&1; then
    echo "✅ Windows machine (192.168.1.32) is reachable!"
else
    echo "⚠️  Cannot reach Windows machine (may need to restart network)"
fi

echo ""
echo "=" | head -c 80 | tr ' ' '='
echo "✅ STATIC IP SETUP COMPLETE!"
echo "=" | head -c 80 | tr ' ' '='
echo ""
echo "📝 Notes:"
echo "   • Your Mac IP is now STATIC at 192.168.1.6"
echo "   • IP will persist across reboots"
echo "   • To revert to DHCP: sudo networksetup -setdhcp \"$INTERFACE\""
echo ""
echo "🔄 To apply changes, you may need to:"
echo "   1. Disconnect and reconnect to Wi-Fi, OR"
echo "   2. Run: sudo ifconfig en0 down && sudo ifconfig en0 up"
echo ""
