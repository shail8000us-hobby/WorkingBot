#!/bin/bash
# TradingView ngrok Setup Script

echo "🔧 Setting up ngrok for TradingView webhooks..."
echo ""
echo "Step 1: Get your authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken"
echo ""

read -p "Enter your ngrok authtoken: " AUTHTOKEN

if [ -z "$AUTHTOKEN" ]; then
    echo "❌ No authtoken provided. Exiting."
    exit 1
fi

echo "🔐 Configuring ngrok authtoken..."
ngrok config add-authtoken "$AUTHTOKEN"

if [ $? -eq 0 ]; then
    echo "✅ Authtoken configured successfully!"
    echo ""
    echo "🚀 Starting ngrok tunnel..."
    echo ""
    echo "⚠️  Keep this terminal open - ngrok tunnel will run here"
    echo "⚠️  Your webhook URL will be displayed below"
    echo ""
    
    # Start ngrok and show the URL
    ngrok http 5555
else
    echo "❌ Failed to configure authtoken. Please check if it's correct."
    exit 1
fi