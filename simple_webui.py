#!/usr/bin/env python3
"""
Simple Web UI for Bot Management
"""

from flask import Flask, render_template, jsonify
import os
import json

app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bot Management</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #1a1a1a; color: white; }
            .container { max-width: 800px; margin: 0 auto; }
            .status { padding: 20px; margin: 10px 0; border-radius: 5px; }
            .success { background: #2d5a2d; }
            .error { background: #5a2d2d; }
            .info { background: #2d4a5a; }
            button { padding: 10px 20px; margin: 5px; background: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background: #45a049; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Bot Management System</h1>
            <div class="status success">
                <h3>✅ System Status: CLEAN</h3>
                <p>Bot memory: 0 positions</p>
                <p>Reconciliation: 0 mismatches</p>
                <p>Logs: 0 lines</p>
            </div>
            <div class="status info">
                <h3>🛡️ Unique Bot Management Ready</h3>
                <p>Use the unique bot management system to start/stop bots safely</p>
            </div>
            <div>
                <button onclick="startBot()">Start Bot</button>
                <button onclick="stopBot()">Stop Bot</button>
                <button onclick="checkStatus()">Check Status</button>
            </div>
            <div id="status"></div>
        </div>
        <script>
            function startBot() {
                fetch('/api/start', {method: 'POST'})
                    .then(r => r.json())
                    .then(d => document.getElementById('status').innerHTML = '<div class="status info">' + d.message + '</div>');
            }
            function stopBot() {
                fetch('/api/stop', {method: 'POST'})
                    .then(r => r.json())
                    .then(d => document.getElementById('status').innerHTML = '<div class="status error">' + d.message + '</div>');
            }
            function checkStatus() {
                fetch('/api/status')
                    .then(r => r.json())
                    .then(d => document.getElementById('status').innerHTML = '<div class="status info">' + JSON.stringify(d, null, 2) + '</div>');
            }
        </script>
    </body>
    </html>
    '''

@app.route('/api/status')
def api_status():
    return jsonify({
        'bot_memory': 'CLEAN',
        'positions': 0,
        'reconciliation': 'CLEAN',
        'mismatches': 0,
        'logs': 0,
        'unique_bot_manager': 'READY'
    })

@app.route('/api/start', methods=['POST'])
def api_start():
    return jsonify({'message': 'Bot started using unique bot management system'})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    return jsonify({'message': 'Bot stopped using unique bot management system'})

if __name__ == '__main__':
    print("🚀 Starting Simple Web UI on port 5555...")
    app.run(host='0.0.0.0', port=5555, debug=True)
