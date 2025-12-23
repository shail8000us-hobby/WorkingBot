#!/bin/bash
# GridBot Web UI - Installation Script

set -e

echo "=================================="
echo "GridBot Web UI - Installation"
echo "=================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 16 or higher."
    echo "   Visit: https://nodejs.org/"
    exit 1
fi

echo "✓ Node.js found: $(node --version)"
echo "✓ npm found: $(npm --version)"
echo ""

# Install Python backend dependencies
echo "📦 Installing Python backend dependencies..."
cd backend
python3 -m pip install -r requirements.txt
cd ..
echo "✓ Backend dependencies installed"
echo ""

# Install Node.js frontend dependencies
echo "📦 Installing Node.js frontend dependencies..."
cd frontend
npm install
echo "✓ Frontend dependencies installed"
echo ""

# Build frontend
echo "🏗️  Building frontend..."
npm run build
cd ..
echo "✓ Frontend built successfully"
echo ""

# Make scripts executable
chmod +x start.sh
chmod +x stop.sh

echo "=================================="
echo "✅ Installation Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Run: ./start.sh"
echo "2. Open: http://localhost:5000"
echo ""
echo "To stop: ./stop.sh or Ctrl+C"
echo ""

