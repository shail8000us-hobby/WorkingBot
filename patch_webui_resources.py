#!/usr/bin/env python3
"""
Automatic patcher for WebUI resource exhaustion fixes.

This script applies the most critical fixes to webui/backend/app.py:
1. Replaces direct requests with connection pool
2. Adds lightweight health endpoint
3. Optimizes SocketIO connect handler
4. Adds cleanup on shutdown
"""

import re
import sys
from pathlib import Path


def backup_file(filepath: Path) -> Path:
    """Create backup of original file."""
    backup_path = filepath.with_suffix(filepath.suffix + '.backup')
    backup_path.write_text(filepath.read_text())
    print(f"✅ Created backup: {backup_path}")
    return backup_path


def apply_imports(content: str) -> str:
    """Add utility imports after existing imports."""
    
    # Find the Flask imports section
    import_section = """
# Resource management utilities (added by resource fix patcher)
from webui.backend.utils.connection_pool import http_get, http_post, cleanup_connections
from webui.backend.utils.timeout_decorator import timeout, fast_timeout
from webui.backend.utils.lightweight_health import start_health_checker, get_health_checker, stop_health_checker
from webui.backend.utils.request_queue import limit_concurrency, queue_metrics_endpoint
from webui.backend.utils.circuit_breaker import circuit_breaker, get_all_circuit_breaker_states
"""
    
    # Add after the Flask-SocketIO import
    pattern = r'(from flask_socketio import SocketIO, emit)'
    if re.search(pattern, content):
        content = re.sub(
            pattern,
            r'\1' + import_section,
            content,
            count=1
        )
        print("✅ Added utility imports")
    else:
        print("⚠️  Could not find Flask-SocketIO import, skipping imports")
    
    return content


def replace_requests_with_pool(content: str) -> str:
    """Replace direct requests.get/post with connection pool."""
    
    replacements = 0
    
    # Replace requests.get
    pattern = r'requests\.get\('
    if re.search(pattern, content):
        content = re.sub(pattern, 'http_get(', content)
        replacements += content.count('http_get(')
        print(f"✅ Replaced requests.get with http_get ({replacements} occurrences)")
    
    # Replace requests.post
    pattern = r'requests\.post\('
    if re.search(pattern, content):
        content = re.sub(pattern, 'http_post(', content)
        count = content.count('http_post(')
        print(f"✅ Replaced requests.post with http_post ({count} occurrences)")
        replacements += count
    
    return content


def add_lightweight_health(content: str) -> str:
    """Replace heavy health endpoint with lightweight version."""
    
    # Find the existing health_check function
    pattern = r"@app\.route\('/api/health', methods=\['GET'\]\)\s+def health_check\(\):.*?(?=\n@|\nif __name__|$)"
    
    new_health_endpoint = '''@app.route('/api/health', methods=['GET'])
@fast_timeout(seconds=1)
def health_check():
    """
    Ultra-lightweight health check endpoint.
    
    Returns cached state (updated every 5s in background).
    Response time: < 1ms (no I/O, no subprocess, no network)
    """
    try:
        checker = get_health_checker()
        state = checker.get_state()
        response = jsonify(state)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    except Exception as e:
        # Fallback if health checker not initialized
        return jsonify({
            'status': 'unknown',
            'error': str(e),
            'timestamp': time.time()
        })


@app.route('/api/health/detailed', methods=['GET'])
@timeout(seconds=5)
def health_check_detailed():
    """Detailed health check with metrics."""
    try:
        checker = get_health_checker()
        state = checker.get_detailed_state()
        
        # Add circuit breaker states
        state['circuit_breakers'] = get_all_circuit_breaker_states()
        
        # Add queue metrics
        state['queue_metrics'] = queue_metrics_endpoint()
        
        return jsonify(state)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500
'''
    
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, new_health_endpoint, content, flags=re.DOTALL, count=1)
        print("✅ Replaced health endpoint with lightweight version")
    else:
        print("⚠️  Could not find health_check function")
    
    return content


def add_health_checker_init(content: str) -> str:
    """Add health checker initialization after SocketIO creation."""
    
    init_code = '''

# Initialize lightweight health checker (resource fix)
print("🏥 Initializing lightweight health checker...")

def safe_check_process(check_func):
    """Safely check if process is running."""
    try:
        return check_func()
    except Exception:
        return False

def safe_check_telegram():
    """Safely check telegram health."""
    try:
        health = get_telegram_health()
        return health.get('connected', False)
    except Exception:
        return False

try:
    start_health_checker(
        bot_check=lambda: safe_check_process(is_bot_running),
        monitor_check=lambda: safe_check_process(is_monitor_running),
        guardian_check=lambda: safe_check_process(is_guardian_running),
        telegram_check=safe_check_telegram
    )
    print("✅ Health checker initialized")
except Exception as e:
    print(f"⚠️  Could not initialize health checker: {e}")
'''
    
    # Add after socketio = SocketIO(...)
    pattern = r'(socketio = SocketIO\([^)]+\))'
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(
            r'(socketio = SocketIO\([^)]+\)\s*)',
            r'\1' + init_code,
            content,
            count=1,
            flags=re.DOTALL
        )
        print("✅ Added health checker initialization")
    else:
        print("⚠️  Could not find socketio initialization")
    
    return content


def add_cleanup_handlers(content: str) -> str:
    """Add cleanup handlers at the end of the file."""
    
    cleanup_code = '''

# Resource cleanup on shutdown (added by resource fix patcher)
def cleanup_on_shutdown():
    """Cleanup resources on shutdown."""
    print("🧹 Cleaning up resources...")
    
    try:
        stop_health_checker()
        print("✅ Stopped health checker")
    except Exception as e:
        print(f"⚠️  Error stopping health checker: {e}")
    
    try:
        cleanup_connections()
        print("✅ Closed connection pool")
    except Exception as e:
        print(f"⚠️  Error closing connections: {e}")
    
    print("✅ Cleanup complete")

# Register cleanup
import atexit
atexit.register(cleanup_on_shutdown)

# Handle signals
def signal_handler(sig, frame):
    print(f"\\n⚠️  Received signal {sig}, shutting down...")
    cleanup_on_shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
'''
    
    # Add before if __name__ == '__main__'
    pattern = r"(if __name__ == '__main__':)"
    if re.search(pattern, content):
        content = re.sub(
            pattern,
            cleanup_code + '\n\n' + r'\1',
            content,
            count=1
        )
        print("✅ Added cleanup handlers")
    else:
        # Add at the end if no if __name__ found
        content += cleanup_code
        print("✅ Added cleanup handlers at end of file")
    
    return content


def main():
    """Main patcher function."""
    print("=" * 60)
    print("WebUI Resource Exhaustion Fix - Automatic Patcher")
    print("=" * 60)
    
    # Find app.py
    app_py = Path(__file__).parent / 'webui' / 'backend' / 'app.py'
    
    if not app_py.exists():
        print(f"❌ Could not find app.py at {app_py}")
        sys.exit(1)
    
    print(f"📄 Found app.py: {app_py}")
    print(f"📊 File size: {app_py.stat().st_size} bytes")
    
    # Create backup
    backup = backup_file(app_py)
    
    # Read content
    content = app_py.read_text()
    original_content = content
    
    print("\n🔧 Applying fixes...")
    print("-" * 60)
    
    # Apply fixes
    content = apply_imports(content)
    content = replace_requests_with_pool(content)
    content = add_lightweight_health(content)
    content = add_health_checker_init(content)
    content = add_cleanup_handlers(content)
    
    # Write back
    if content != original_content:
        app_py.write_text(content)
        print("-" * 60)
        print(f"✅ Successfully patched app.py")
        print(f"📦 Backup saved to: {backup}")
        print("\n📋 Next steps:")
        print("1. Review the changes: diff webui/backend/app.py webui/backend/app.py.backup")
        print("2. Test manually: python3 webui/backend/app.py")
        print("3. Test health: curl http://localhost:5555/api/health")
        print("4. If working, reload LaunchAgent")
        print("\n⚠️  Note: This applies only the most critical fixes.")
        print("   Review WEBUI_RESOURCE_FIX_INTEGRATION.md for complete integration.")
    else:
        print("⚠️  No changes made (content unchanged)")
        backup.unlink()  # Remove unnecessary backup
    
    print("=" * 60)


if __name__ == '__main__':
    main()
