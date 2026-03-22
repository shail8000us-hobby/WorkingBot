#!/bin/bash
# Build script for frontend (incremental — cache preserved for speed)
cd /Users/ssr/Projects/WorkingBot/webui/frontend
npm run build > /tmp/frontend_build.log 2>&1
BUILD_EXIT=$?
echo "Build exit code: $BUILD_EXIT"
if [ $BUILD_EXIT -eq 0 ]; then
    echo "✅ BUILD SUCCESSFUL"
    grep -i "compiled\|success\|warning" /tmp/frontend_build.log | head -5
else
    echo "❌ BUILD FAILED"
    tail -20 /tmp/frontend_build.log
fi
