#!/usr/bin/env python3
"""
Backend Integration Template for Error Intelligence System

This file shows exactly what needs to be added to webui/backend/app.py
Copy these snippets into your app.py file
"""

# ============================================================================
# STEP 1: Add imports at the top of app.py
# ============================================================================

# Add these imports after existing imports
from errors import ErrorIntelligenceManager, errors_bp
from services.notifications import TelegramErrorNotifier, TelegramCommandHandler

# ============================================================================
# STEP 2: Initialize components after Flask app and SocketIO are created
# ============================================================================

# After: app = Flask(__name__) and socketio = SocketIO(app)
# Add these lines:

# Initialize Error Intelligence System
error_manager = ErrorIntelligenceManager(socketio=socketio)

# Initialize Telegram notifications (optional, requires TELEGRAM_BOT_TOKEN)
telegram_notifier = TelegramErrorNotifier()
telegram_commands = TelegramCommandHandler(error_manager=error_manager)

# Register error routes blueprint
app.register_blueprint(errors_bp)

# ============================================================================
# STEP 3: Connect error events to Telegram notifications
# ============================================================================

# Add this function to forward errors to Telegram:

def on_new_error_detected(error):
    """Callback when new error is detected"""
    try:
        # Send to Telegram
        telegram_notifier.notify_error(error)
        
        # Log for debugging
        app.logger.info(f"New error detected: {error['code']} ({error['severity']})")
    except Exception as e:
        app.logger.error(f"Error in on_new_error_detected: {e}")

# Connect the callback
error_manager.on_error_detected = on_new_error_detected

# ============================================================================
# STEP 4: Start services when Flask app starts
# ============================================================================

# Add this in your startup section (or create one if it doesn't exist):

@app.before_first_request
def startup():
    """Start background services"""
    try:
        # Start error intelligence
        app.logger.info("🚀 Starting Error Intelligence System...")
        error_manager.start()
        
        # Start Telegram services
        if telegram_notifier.enabled:
            app.logger.info("🚀 Starting Telegram notifier...")
            telegram_notifier.start()
        
        if telegram_commands.enabled:
            app.logger.info("🚀 Starting Telegram command handler...")
            telegram_commands.start()
        
        app.logger.info("✅ Error Intelligence System started successfully")
    except Exception as e:
        app.logger.error(f"❌ Failed to start Error Intelligence: {e}")

# ============================================================================
# STEP 5: Stop services on shutdown (optional but recommended)
# ============================================================================

# Add this to handle graceful shutdown:

import atexit

def shutdown():
    """Stop background services"""
    try:
        app.logger.info("🛑 Stopping Error Intelligence System...")
        
        if error_manager:
            error_manager.stop()
        
        if telegram_notifier:
            telegram_notifier.stop()
        
        if telegram_commands:
            telegram_commands.stop()
        
        app.logger.info("✅ Error Intelligence System stopped")
    except Exception as e:
        app.logger.error(f"Error during shutdown: {e}")

atexit.register(shutdown)

# ============================================================================
# STEP 6: Add a test endpoint (optional, for debugging)
# ============================================================================

@app.route('/api/errors/test', methods=['POST'])
def test_error():
    """Inject a test error for debugging"""
    try:
        data = request.json
        
        test_error = {
            "message_raw": data.get("message", "Test error"),
            "source": data.get("source", "system")
        }
        
        # Process through collector
        # This would normally come from log tailing
        error_event = error_manager.classifier.classify(
            test_error["message_raw"],
            test_error["source"]
        )
        
        # Store
        error_manager.store.create_error(error_event)
        
        # Emit
        error_manager._emit_error_event('new_error', error_event)
        
        # Notify
        telegram_notifier.notify_error(error_event)
        
        return jsonify({
            "success": True,
            "error": error_event,
            "message": "Test error created successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# ============================================================================
# COMPLETE INTEGRATION EXAMPLE
# ============================================================================

"""
Here's what a minimal app.py with Error Intelligence looks like:

from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS
import logging

# Error Intelligence imports
from errors import ErrorIntelligenceManager, errors_bp
from services.notifications import TelegramErrorNotifier, TelegramCommandHandler

# Create Flask app
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Error Intelligence System
error_manager = ErrorIntelligenceManager(socketio=socketio)
telegram_notifier = TelegramErrorNotifier()
telegram_commands = TelegramCommandHandler(error_manager=error_manager)

# Register blueprints
app.register_blueprint(errors_bp)

# Error callback
def on_new_error_detected(error):
    telegram_notifier.notify_error(error)
    app.logger.info(f"New error: {error['code']}")

error_manager.on_error_detected = on_new_error_detected

# Startup
@app.before_first_request
def startup():
    app.logger.info("🚀 Starting services...")
    error_manager.start()
    telegram_notifier.start()
    telegram_commands.start()
    app.logger.info("✅ Services started")

# Shutdown
import atexit

def shutdown():
    app.logger.info("🛑 Stopping services...")
    error_manager.stop()
    telegram_notifier.stop()
    telegram_commands.stop()

atexit.register(shutdown)

# Your existing routes...
@app.route('/api/status')
def status():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5555, debug=True)
"""

# ============================================================================
# QUICK VALIDATION CHECKLIST
# ============================================================================

"""
After integration, verify:

1. ✅ Backend starts without errors
2. ✅ Check logs for: "🚀 Starting Error Intelligence System..."
3. ✅ Check logs for: "✅ Error Intelligence System started successfully"
4. ✅ Visit http://localhost:5555/api/errors/ (should return empty list or errors)
5. ✅ Visit http://localhost:5555/api/errors/catalog (should return 15+ patterns)
6. ✅ Inject test error: curl -X POST http://localhost:5555/api/errors/test -H "Content-Type: application/json" -d '{"message": "Test error"}'
7. ✅ Check WebUI at http://localhost:5555 (look for floating incidents badge)
8. ✅ Check Telegram for notification (if configured)

If any step fails, check:
- Logs in terminal/PM2 logs
- grid_config.env has ERROR_COLLECTOR_ENABLED=true
- Required directories exist (mkdir -p data logs)
- Log files exist (touch logs/guardian.log logs/health.log)
"""
