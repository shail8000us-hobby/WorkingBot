#!/usr/bin/env bash
# Build React frontend for production
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/webui/frontend"

cd "$FRONTEND_DIR"

echo "🏗️  Building React Frontend"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm ci
else
    echo "✓ Dependencies already installed"
fi

# Clean previous build
if [ -d "build" ]; then
    echo "🧹 Cleaning previous build..."
    rm -rf build
fi

# Build
echo "🔨 Building production bundle..."
npm run build

# Verify build
if [ -d "build" ] && [ -f "build/index.html" ]; then
    BUILD_SIZE=$(du -sh build | cut -f1)
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ Build successful!"
    echo "   Output: $FRONTEND_DIR/build/"
    echo "   Size: $BUILD_SIZE"
    
    # Show build hash if available
    if [ -f "build/asset-manifest.json" ]; then
        MAIN_JS=$(grep -o '"main.js":"[^"]*"' build/asset-manifest.json | cut -d'"' -f4)
        if [ ! -z "$MAIN_JS" ]; then
            HASH=$(echo "$MAIN_JS" | grep -oE 'main\.[a-f0-9]+\.js' | cut -d'.' -f2 | cut -c1-8)
            echo "   Build hash: $HASH"
        fi
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "❌ Build failed - output directory not found"
    exit 1
fi
