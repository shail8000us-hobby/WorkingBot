#!/usr/bin/env python3
"""
Bot Performance Report Generator
Creates visual summary of bot health and performance
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime

def get_bot_stats():
    """Get bot process statistics"""
    try:
        result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True)
        processes = json.loads(result.stdout)
        
        bot = next((p for p in processes if p['name'] == 'gridbot-live'), None)
        if bot:
            return {
                'pid': bot['pid'],
                'uptime': bot['pm2_env']['pm_uptime'],
                'restarts': bot['pm2_env']['restart_time'],
                'memory': bot['monit']['memory'] / (1024 * 1024),  # MB
                'cpu': bot['monit']['cpu'],
                'status': bot['pm2_env']['status']
            }
    except:
        pass
    return None

def analyze_recent_activity():
    """Analyze recent log activity"""
    log_file = Path("/Users/ssr/Projects/WorkingBot/bot/logs/bot.log")
    
    stats = {
        'orders_placed': 0,
        'fills': 0,
        'errors': 0,
        'warnings': 0,
        'throttles': 0,
        'websocket_reconnects': 0
    }
    
    if log_file.exists():
        with open(log_file, 'r') as f:
            lines = f.readlines()[-1000:]  # Last 1000 lines
            
            for line in lines:
                if 'order placed' in line.lower():
                    stats['orders_placed'] += 1
                if 'filled @' in line:
                    stats['fills'] += 1
                if '[ERROR]' in line:
                    stats['errors'] += 1
                if '[WARNING]' in line or 'WARNING' in line:
                    stats['warnings'] += 1
                if 'THROTTLE' in line:
                    stats['throttles'] += 1
                if 'WebSocket' in line and 'reconnect' in line.lower():
                    stats['websocket_reconnects'] += 1
    
    return stats

def generate_report():
    """Generate HTML performance report"""
    
    bot_stats = get_bot_stats()
    activity = analyze_recent_activity()
    
    if bot_stats:
        uptime_hours = (datetime.now().timestamp() - bot_stats['uptime']/1000) / 3600
        uptime_str = f"{uptime_hours:.1f}h"
    else:
        uptime_str = "N/A"
        bot_stats = {'pid': 'N/A', 'restarts': 0, 'memory': 0, 'cpu': 0, 'status': 'offline'}
    
    # Health score
    health_score = 100
    if activity['errors'] > 10:
        health_score -= 20
    if activity['throttles'] == 0 and activity['orders_placed'] > 5:
        health_score -= 15  # Throttle should activate
    if bot_stats['restarts'] > 5:
        health_score -= 15
    if activity['websocket_reconnects'] > 3:
        health_score -= 10
    
    health_color = '#4caf50' if health_score >= 80 else '#ff9800' if health_score >= 60 else '#f44336'
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Bot Performance Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'SF Pro Display', -apple-system, system-ui, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            margin-bottom: 30px;
            text-align: center;
        }}
        h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        .timestamp {{
            color: #666;
            font-size: 14px;
        }}
        .dashboard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }}
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 50px rgba(0,0,0,0.15);
        }}
        .card-title {{
            font-size: 14px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 15px;
            font-weight: 600;
        }}
        .card-value {{
            font-size: 36px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }}
        .card-subtitle {{
            font-size: 14px;
            color: #666;
        }}
        .health-score {{
            background: linear-gradient(135deg, {health_color}22, {health_color}44);
            border-left: 5px solid {health_color};
        }}
        .health-score .card-value {{
            color: {health_color};
            font-size: 48px;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .metric:last-child {{ border-bottom: none; }}
        .metric-label {{ color: #666; }}
        .metric-value {{ font-weight: bold; color: #333; }}
        .status-badge {{
            display: inline-block;
            padding: 6px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .status-online {{ background: #4caf50; color: white; }}
        .status-offline {{ background: #f44336; color: white; }}
        .chart-container {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .bar {{
            height: 30px;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 5px;
            margin: 10px 0;
            display: flex;
            align-items: center;
            color: white;
            font-size: 14px;
            font-weight: bold;
            padding: 0 15px;
            transition: all 0.3s ease;
        }}
        .bar:hover {{ transform: scaleX(1.02); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 GridBot Performance Report</h1>
            <div class="timestamp">Generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}</div>
        </div>

        <div class="dashboard">
            <div class="card health-score">
                <div class="card-title">Health Score</div>
                <div class="card-value">{health_score}/100</div>
                <div class="card-subtitle">
                    {'🟢 Excellent' if health_score >= 80 else '🟡 Fair' if health_score >= 60 else '🔴 Needs Attention'}
                </div>
            </div>

            <div class="card">
                <div class="card-title">Process Status</div>
                <div class="card-value">
                    <span class="status-badge status-{bot_stats['status'].lower()}">
                        {bot_stats['status'].upper()}
                    </span>
                </div>
                <div class="card-subtitle">
                    PID: {bot_stats['pid']} | Uptime: {uptime_str}
                </div>
            </div>

            <div class="card">
                <div class="card-title">Resource Usage</div>
                <div class="card-value">{bot_stats['memory']:.1f} MB</div>
                <div class="card-subtitle">
                    CPU: {bot_stats['cpu']}% | Restarts: {bot_stats['restarts']}
                </div>
            </div>
        </div>

        <div class="chart-container">
            <h2 style="margin-bottom: 20px; color: #333;">📊 Recent Activity (Last 1000 log lines)</h2>
            
            <div class="metric">
                <span class="metric-label">Orders Placed</span>
                <span class="metric-value">{activity['orders_placed']}</span>
            </div>
            <div class="bar" style="width: {min(activity['orders_placed']*10, 100)}%;">
                {activity['orders_placed']} orders
            </div>

            <div class="metric">
                <span class="metric-label">Fills Executed</span>
                <span class="metric-value">{activity['fills']}</span>
            </div>
            <div class="bar" style="width: {min(activity['fills']*10, 100)}%; background: linear-gradient(90deg, #4caf50, #8bc34a);">
                {activity['fills']} fills
            </div>

            <div class="metric">
                <span class="metric-label">Throttle Activations</span>
                <span class="metric-value">{activity['throttles']}</span>
            </div>
            <div class="bar" style="width: {min(activity['throttles']*20, 100)}%; background: linear-gradient(90deg, #ff9800, #ffc107);">
                {activity['throttles']} throttles
            </div>

            <div class="metric">
                <span class="metric-label">WebSocket Reconnects</span>
                <span class="metric-value">{activity['websocket_reconnects']}</span>
            </div>
            <div class="bar" style="width: {min(activity['websocket_reconnects']*20, 100)}%; background: linear-gradient(90deg, #2196f3, #03a9f4);">
                {activity['websocket_reconnects']} reconnects
            </div>

            <div class="metric">
                <span class="metric-label">⚠️ Warnings</span>
                <span class="metric-value">{activity['warnings']}</span>
            </div>
            <div class="bar" style="width: {min(activity['warnings']*5, 100)}%; background: linear-gradient(90deg, #ff9800, #ff5722);">
                {activity['warnings']} warnings
            </div>

            <div class="metric">
                <span class="metric-label">❌ Errors</span>
                <span class="metric-value">{activity['errors']}</span>
            </div>
            <div class="bar" style="width: {min(activity['errors']*10, 100)}%; background: linear-gradient(90deg, #f44336, #e91e63);">
                {activity['errors']} errors
            </div>
        </div>

        <div class="card" style="margin-top: 30px;">
            <div class="card-title">💡 Recommendations</div>
            <ul style="list-style: none; padding: 0;">
                {f'<li style="padding: 10px; background: #fff3cd; margin: 5px 0; border-radius: 5px;">⚠️ High error count detected. Check logs for issues.</li>' if activity['errors'] > 10 else ''}
                {f'<li style="padding: 10px; background: #fff3cd; margin: 5px 0; border-radius: 5px;">⚠️ Throttle not activating. Verify 30s gap mechanism working.</li>' if activity['throttles'] == 0 and activity['orders_placed'] > 5 else ''}
                {f'<li style="padding: 10px; background: #fff3cd; margin: 5px 0; border-radius: 5px;">⚠️ Frequent WebSocket reconnects. Check network stability.</li>' if activity['websocket_reconnects'] > 3 else ''}
                {f'<li style="padding: 10px; background: #d1ecf1; margin: 5px 0; border-radius: 5px;">✅ Bot health looks good! Continue monitoring.</li>' if health_score >= 80 else ''}
                {f'<li style="padding: 10px; background: #d1ecf1; margin: 5px 0; border-radius: 5px;">✅ Throttle mechanism is active and working.</li>' if activity['throttles'] > 0 else ''}
            </ul>
        </div>
    </div>

    <script>
        // Auto-refresh every 60 seconds
        setTimeout(() => location.reload(), 60000);
    </script>
</body>
</html>"""
    
    return html

def main():
    output_file = Path("/Users/ssr/Projects/WorkingBot/analysis/performance_report.html")
    output_file.parent.mkdir(exist_ok=True)
    
    print("📊 Generating performance report...")
    html = generate_report()
    output_file.write_text(html)
    
    print(f"✅ Report generated: {output_file}")
    print(f"🌐 Opening in browser...")
    
    subprocess.run(['open', str(output_file)])

if __name__ == "__main__":
    main()
