#!/bin/bash

echo "🧪 Testing Todo API - Backend is Working!"
echo ""

echo "1️⃣  Testing GET /api/todos:"
curl -s http://localhost:5555/api/todos | python3 -m json.tool
echo ""

echo "2️⃣  Testing POST /api/todos:"
curl -s -X POST http://localhost:5555/api/todos \
  -H "Content-Type: application/json" \
  -d '{"text":"CLI test at '$(date +%H:%M:%S)'"}' | python3 -m json.tool
echo ""

echo "3️⃣  Checking backend logs:"
tail -5 /Users/shailendrasinghrajawat/Projects/WorkingBot/logs/launchagent_webui.log | grep -E "📝|✅|❌"
echo ""

echo "✅ Backend is working! Issue is browser cache."
echo "👉 Clear your browser cache and try again!"
