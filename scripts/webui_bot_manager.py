#!/usr/bin/env python3
"""
Web UI Backend for Bot Process Management
Provides REST API and web interface for managing bot processes
"""

import os
import json
import subprocess
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_socketio import SocketIO, emit
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bot_manager_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
BOT_DIR = "/Users/shailendrasinghrajawat/Documents/WorkingBot"
PID_DIR = os.path.join(BOT_DIR, ".pids")
LOG_DIR = os.path.join(BOT_DIR, "logs")
BOT_MANAGER = os.path.join(BOT_DIR, "bot_manager.sh")

# Ensure directories exist
os.makedirs(PID_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Bot types and their configurations
BOT_TYPES = {
    'trading': {
        'name': 'Trading Bot',
        'description': 'Main trading bot that executes trades',
        'pid_file': os.path.join(PID_DIR, 'trading_bot.pid'),
        'log_file': os.path.join(LOG_DIR, 'trading_bot.log'),
        'color': 'success'
    },
    'health': {
        'name': 'Health Monitor',
        'description': 'Monitors system health and performance',
        'pid_file': os.path.join(PID_DIR, 'health_bot.pid'),
        'log_file': os.path.join(LOG_DIR, 'health_monitor.log'),
        'color': 'info'
    },
    'monitoring': {
        'name': 'Monitoring Bot',
        'description': 'Web UI and monitoring dashboard',
        'pid_file': os.path.join(PID_DIR, 'monitoring_bot.pid'),
        'log_file': os.path.join(LOG_DIR, 'monitoring_bot.log'),
        'color': 'warning'
    }
}

def is_running(pid_file):
    """Check if a process is running based on PID file"""
    if not os.path.exists(pid_file):
        return False
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        result = subprocess.run(['ps', '-p', str(pid)], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except (ValueError, FileNotFoundError):
        return False

def get_bot_status():
    """Get status of all bots"""
    status = {}
    
    for bot_type, config in BOT_TYPES.items():
        running = is_running(config['pid_file'])
        pid = None
        
        if running:
            try:
                with open(config['pid_file'], 'r') as f:
                    pid = int(f.read().strip())
            except (ValueError, FileNotFoundError):
                pass
        
        # Get log file size and last modified
        log_size = 0
        last_modified = None
        if os.path.exists(config['log_file']):
            stat = os.stat(config['log_file'])
            log_size = stat.st_size
            last_modified = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        status[bot_type] = {
            'running': running,
            'pid': pid,
            'log_size': log_size,
            'last_modified': last_modified,
            'name': config['name'],
            'description': config['description'],
            'color': config['color']
        }
    
    return status

def run_bot_command(action, bot_type=None):
    """Run bot manager command"""
    cmd = [BOT_MANAGER, action]
    if bot_type:
        cmd.append(bot_type)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Command timed out'
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e)
        }

def get_system_info():
    """Get system information"""
    try:
        # Get system load
        with open('/proc/loadavg', 'r') as f:
            load_avg = f.read().strip().split()[:3]
    except FileNotFoundError:
        # macOS doesn't have /proc/loadavg
        load_avg = ['N/A', 'N/A', 'N/A']
    
    # Get memory usage
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        total_memory = 0
        bot_memory = 0
        
        for line in lines:
            if 'python' in line and 'bot' in line:
                parts = line.split()
                if len(parts) > 5:
                    try:
                        memory = float(parts[5])
                        bot_memory += memory
                    except (ValueError, IndexError):
                        pass
        
        # Get total system memory (simplified)
        total_memory = 8192  # Assume 8GB for now
        
    except Exception:
        total_memory = 0
        bot_memory = 0
    
    return {
        'load_avg': load_avg,
        'total_memory': total_memory,
        'bot_memory': bot_memory,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('bot_manager.html')

@app.route('/api/status')
def api_status():
    """API endpoint for bot status"""
    return jsonify({
        'bots': get_bot_status(),
        'system': get_system_info()
    })

@app.route('/api/action', methods=['POST'])
def api_action():
    """API endpoint for bot actions"""
    data = request.get_json()
    action = data.get('action')
    bot_type = data.get('bot_type')
    
    if action not in ['start', 'stop', 'restart']:
        return jsonify({'success': False, 'error': 'Invalid action'})
    
    if bot_type and bot_type not in BOT_TYPES:
        return jsonify({'success': False, 'error': 'Invalid bot type'})
    
    result = run_bot_command(action, bot_type)
    
    # Emit update to all connected clients
    socketio.emit('bot_update', {
        'action': action,
        'bot_type': bot_type,
        'result': result,
        'timestamp': datetime.now().isoformat()
    })
    
    return jsonify(result)

@app.route('/api/logs/<bot_type>')
def api_logs(bot_type):
    """API endpoint for bot logs"""
    if bot_type not in BOT_TYPES:
        return jsonify({'error': 'Invalid bot type'}), 400
    
    log_file = BOT_TYPES[bot_type]['log_file']
    lines = request.args.get('lines', 100, type=int)
    
    try:
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return jsonify({
            'logs': ''.join(recent_lines),
            'total_lines': len(all_lines),
            'showing_lines': len(recent_lines)
        })
    except FileNotFoundError:
        return jsonify({'logs': 'Log file not found', 'total_lines': 0, 'showing_lines': 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/processes')
def api_processes():
    """API endpoint for system processes"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        bot_processes = []
        for line in lines:
            if 'python' in line and ('bot' in line or 'run' in line):
                parts = line.split()
                if len(parts) >= 11:
                    bot_processes.append({
                        'pid': parts[1],
                        'cpu': parts[2],
                        'memory': parts[3],
                        'command': ' '.join(parts[10:])
                    })
        
        return jsonify({'processes': bot_processes})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f'Client connected: {request.sid}')
    emit('status_update', get_bot_status())

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f'Client disconnected: {request.sid}')

def status_monitor():
    """Background thread to monitor bot status"""
    while True:
        try:
            status = get_bot_status()
            socketio.emit('status_update', status)
            time.sleep(5)  # Update every 5 seconds
        except Exception as e:
            print(f'Status monitor error: {e}')
            time.sleep(10)

if __name__ == '__main__':
    # Start status monitor in background thread
    monitor_thread = threading.Thread(target=status_monitor, daemon=True)
    monitor_thread.start()
    
    print("Starting Bot Manager Web UI...")
    print("Access at: http://localhost:5000")
    
    socketio.run(app, host='0.0.0.0', port=5555, debug=True, allow_unsafe_werkzeug=True)
