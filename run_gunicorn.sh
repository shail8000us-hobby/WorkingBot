#!/bin/bash
# Run GridBot WebUI with Gunicorn + SocketIO

cd /Users/ssr/Projects/WorkingBot

# Create logs directory if needed
mkdir -p logs

# Run Gunicorn with SocketIO support
python3 -c "
import sys
sys.path.insert(0, '/Users/ssr/Projects/WorkingBot')

from webui.backend.app import app, socketio

# Run with Gunicorn-compatible socketio
if __name__ == '__main__':
    print('🚀 Starting GridBot WebUI with Gunicorn...')
    socketio.run(
        app,
        host='0.0.0.0',
        port=5555,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )
"
