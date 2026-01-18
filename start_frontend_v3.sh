#!/bin/bash

# Quick Start Script for Frontend-v3 with Phase 1 & Phase 2 Enhancements
# Usage: ./start_frontend_v3.sh [dev|build]

set -e

PROJECT_ROOT="/Users/ssr/Projects/WorkingBot"
FRONTEND_DIR="$PROJECT_ROOT/webui/frontend-v3"

echo "🚀 Starting Frontend-v3 with Visual Enhancements..."
echo ""

# Check if mode is specified
MODE=${1:-dev}

if [ "$MODE" = "dev" ]; then
    echo "📦 Mode: Development (Hot Reload)"
    echo "🌐 URL: http://localhost:3000"
    echo "📡 API Proxy: http://localhost:5555"
    echo ""
    
    # Check if backend is running
    if ! curl -s http://localhost:5555/api/health > /dev/null 2>&1; then
        echo "⚠️  Warning: Backend not responding on port 5555"
        echo "   Start backend first: cd webui/backend && python3 app.py &"
        echo ""
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo "✅ Backend is running on port 5555"
        echo ""
    fi
    
    cd "$FRONTEND_DIR"
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "📦 Installing dependencies..."
        npm install
        echo ""
    fi
    
    echo "🎨 Starting dev server with Phase 1 & Phase 2 enhancements..."
    echo ""
    npm run dev

elif [ "$MODE" = "build" ]; then
    echo "📦 Mode: Production Build"
    echo "📁 Output: .next/"
    echo ""
    
    cd "$FRONTEND_DIR"
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "📦 Installing dependencies..."
        npm install
        echo ""
    fi
    
    echo "🔨 Building production bundle..."
    npm run build
    
    echo ""
    echo "✅ Build complete!"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Update backend to serve frontend-v3:"
    echo "      Edit webui/backend/app.py"
    echo "      Change static_folder to '../frontend-v3/.next/static'"
    echo ""
    echo "   2. Restart backend:"
    echo "      pkill -f 'webui/backend/app.py'"
    echo "      cd webui/backend && python3 app.py &"
    echo ""
    echo "   3. Access: http://localhost:5555"
    
else
    echo "❌ Invalid mode: $MODE"
    echo ""
    echo "Usage: $0 [dev|build]"
    echo ""
    echo "Modes:"
    echo "  dev   - Start development server (hot reload) on port 3000"
    echo "  build - Build production bundle"
    echo ""
    exit 1
fi
