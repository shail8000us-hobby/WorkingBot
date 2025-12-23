#!/usr/bin/env python3
"""
Volatility Chart System Integration Script

Automatically integrates the IV vs RV volatility chart system into the WebUI.

What it does:
1. Adds API endpoints to app.py
2. Updates App.js to include VolatilityChart component
3. Creates startup script for the collector
4. Verifies all dependencies are in place

Usage:
    python3 integrate_volatility_chart.py
"""

import os
import sys
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).parent
WEBUI_BACKEND = PROJECT_ROOT / "webui" / "backend" / "app.py"
WEBUI_FRONTEND_APP = PROJECT_ROOT / "webui" / "frontend" / "src" / "App.js"


def backup_file(file_path):
    """Create backup of file before modifying"""
    backup_path = f"{file_path}.backup_volatility"
    if not Path(backup_path).exists():
        import shutil
        shutil.copy2(file_path, backup_path)
        print(f"✅ Created backup: {backup_path}")
    return backup_path


def integrate_backend():
    """Add volatility chart API to app.py"""
    print("\n📝 Integrating Backend API...")
    
    if not WEBUI_BACKEND.exists():
        print(f"❌ File not found: {WEBUI_BACKEND}")
        return False
    
    # Backup first
    backup_file(WEBUI_BACKEND)
    
    # Read app.py
    with open(WEBUI_BACKEND, 'r') as f:
        content = f.read()
    
    # Check if already integrated
    if 'volatility_chart_api' in content:
        print("✅ Backend API already integrated")
        return True
    
    # Find import section (after other imports)
    import_pattern = r'(from bot\.volatility\.iv_rv_tracker import get_volatility_tracker)'
    if not re.search(import_pattern, content):
        print("⚠️  Could not find import location in app.py")
        print("   Please manually add to app.py after line 100:")
        print("   from webui.backend.volatility_chart_api import register_volatility_chart_api")
        return False
    
    # Add import after iv_rv_tracker import
    content = re.sub(
        import_pattern,
        r'\1\nfrom webui.backend.volatility_chart_api import register_volatility_chart_api',
        content
    )
    
    # Find socketio initialization
    socketio_pattern = r'(socketio = SocketIO\([^)]+\))'
    if not re.search(socketio_pattern, content):
        print("⚠️  Could not find SocketIO initialization")
        return False
    
    # Add registration after socketio init
    content = re.sub(
        socketio_pattern,
        r'\1\n\n# Register volatility chart API\nregister_volatility_chart_api(app, socketio)',
        content
    )
    
    # Write updated content
    with open(WEBUI_BACKEND, 'w') as f:
        f.write(content)
    
    print("✅ Backend API integrated successfully")
    print("   Added: register_volatility_chart_api(app, socketio)")
    return True


def integrate_frontend():
    """Add VolatilityChart component to App.js"""
    print("\n📝 Integrating Frontend Component...")
    
    if not WEBUI_FRONTEND_APP.exists():
        print(f"❌ File not found: {WEBUI_FRONTEND_APP}")
        return False
    
    # Backup first
    backup_file(WEBUI_FRONTEND_APP)
    
    # Read App.js
    with open(WEBUI_FRONTEND_APP, 'r') as f:
        content = f.read()
    
    # Check if already integrated
    if 'VolatilityChart' in content:
        print("✅ Frontend component already integrated")
        return True
    
    # Add import
    import_pattern = r'(import MarketSignalPanel from [^\n]+)'
    if re.search(import_pattern, content):
        content = re.sub(
            import_pattern,
            r'\1\nimport VolatilityChart from \'./components/charts/VolatilityChart\';',
            content
        )
    else:
        print("⚠️  Could not find import location in App.js")
        print("   Please manually add import:")
        print("   import VolatilityChart from './components/charts/VolatilityChart';")
        return False
    
    # Add component to dashboard (look for MarketSignalPanel)
    component_pattern = r'(<MarketSignalPanel[^/]*/>)'
    if re.search(component_pattern, content):
        content = re.sub(
            component_pattern,
            r'\1\n                  <VolatilityChart socket={connectionManagerRef.current?.socket} />',
            content
        )
        print("✅ Frontend component integrated successfully")
        print("   Added: <VolatilityChart /> to dashboard")
    else:
        print("⚠️  Could not find component insertion location")
        print("   Please manually add <VolatilityChart socket={connectionManagerRef.current?.socket} />")
        print("   to App.js in the dashboard tab")
        return False
    
    # Write updated content
    with open(WEBUI_FRONTEND_APP, 'w') as f:
        f.write(content)
    
    return True


def create_collector_startup_script():
    """Create startup script for the collector"""
    print("\n📝 Creating Collector Startup Script...")
    
    startup_script = PROJECT_ROOT / "start_volatility_collector.sh"
    
    script_content = f"""#!/bin/bash
# Start Volatility Collector Service
# Runs in background and collects IV/RV data every 30 seconds

cd "{PROJECT_ROOT}"

export PYTHONPATH="{PROJECT_ROOT}:$PYTHONPATH"

echo "🚀 Starting Volatility Collector..."
nohup python3 bot/volatility/delta_volatility_collector.py > logs/volatility_collector.log 2>&1 &
echo $! > .volatility_collector.pid

echo "✅ Volatility Collector started (PID: $(cat .volatility_collector.pid))"
echo "📊 Logs: logs/volatility_collector.log"
echo "🛑 To stop: kill $(cat .volatility_collector.pid)"
"""
    
    with open(startup_script, 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(startup_script, 0o755)
    
    print(f"✅ Created: {startup_script}")
    return True


def create_stop_script():
    """Create stop script for the collector"""
    print("\n📝 Creating Collector Stop Script...")
    
    stop_script = PROJECT_ROOT / "stop_volatility_collector.sh"
    
    script_content = f"""#!/bin/bash
# Stop Volatility Collector Service

cd "{PROJECT_ROOT}"

if [ -f .volatility_collector.pid ]; then
    PID=$(cat .volatility_collector.pid)
    echo "🛑 Stopping Volatility Collector (PID: $PID)..."
    kill $PID
    rm .volatility_collector.pid
    echo "✅ Volatility Collector stopped"
else
    echo "⚠️  Volatility Collector is not running (no PID file)"
fi
"""
    
    with open(stop_script, 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(stop_script, 0o755)
    
    print(f"✅ Created: {stop_script}")
    return True


def verify_dependencies():
    """Verify all required files exist"""
    print("\n🔍 Verifying Dependencies...")
    
    required_files = [
        "bot/volatility/delta_volatility_collector.py",
        "webui/backend/volatility_chart_api.py",
        "webui/frontend/src/components/charts/VolatilityChart.js"
    ]
    
    all_exist = True
    for file_path in required_files:
        full_path = PROJECT_ROOT / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} NOT FOUND")
            all_exist = False
    
    return all_exist


def print_next_steps():
    """Print next steps for user"""
    print("\n" + "=" * 70)
    print("🎉 VOLATILITY CHART SYSTEM INTEGRATION COMPLETE")
    print("=" * 70)
    print("\n📋 NEXT STEPS:\n")
    print("1. Start the Volatility Collector:")
    print("   ./start_volatility_collector.sh")
    print()
    print("2. Rebuild the Frontend:")
    print("   cd webui/frontend")
    print("   npm install date-fns recharts  # Install required packages")
    print("   npm run build")
    print()
    print("3. Restart the WebUI:")
    print("   launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist")
    print("   launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist")
    print()
    print("4. Access the Chart:")
    print("   Open http://localhost:5555")
    print("   Navigate to the Dashboard tab")
    print("   The volatility chart should appear below the Market Signal panel")
    print()
    print("=" * 70)
    print("\n📊 Database Location:")
    print(f"   {PROJECT_ROOT}/data/volatility.db")
    print()
    print("📝 Logs:")
    print(f"   {PROJECT_ROOT}/logs/volatility_collector.log")
    print()
    print("🛑 To stop collector:")
    print("   ./stop_volatility_collector.sh")
    print()
    print("=" * 70)


def main():
    """Main integration flow"""
    print("=" * 70)
    print("🚀 VOLATILITY CHART SYSTEM INTEGRATION")
    print("=" * 70)
    
    # Verify dependencies
    if not verify_dependencies():
        print("\n❌ Missing required files. Please ensure all components are created.")
        sys.exit(1)
    
    # Integrate backend
    if not integrate_backend():
        print("\n⚠️  Backend integration incomplete - manual steps required")
    
    # Integrate frontend
    if not integrate_frontend():
        print("\n⚠️  Frontend integration incomplete - manual steps required")
    
    # Create scripts
    create_collector_startup_script()
    create_stop_script()
    
    # Print next steps
    print_next_steps()


if __name__ == "__main__":
    main()
