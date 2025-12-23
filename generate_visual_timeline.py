#!/usr/bin/env python3
"""
Visual Race Condition Analyzer
Generates HTML visualization of order timing from logs
"""

import re
import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("/Users/ssr/Projects/WorkingBot/bot/logs/bot.log")
OUTPUT_HTML = Path("/Users/ssr/Projects/WorkingBot/analysis/race_condition_timeline.html")

def parse_logs():
    """Extract order events from logs"""
    events = []
    
    with open(LOG_FILE, 'r') as f:
        for line in f:
            # Extract timestamp
            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if not match:
                continue
            
            timestamp = match.group(1)
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            
            # Check for order events
            if "BUY order placed @" in line:
                price_match = re.search(r'\$([0-9,]+)', line)
                order_match = re.search(r'ID[: ]+(\d+)', line)
                if price_match:
                    events.append({
                        'time': dt,
                        'type': 'BUY_ORDER',
                        'price': price_match.group(1),
                        'order_id': order_match.group(1) if order_match else 'N/A',
                        'label': f"BUY @ ${price_match.group(1)}"
                    })
            
            elif "SELL order placed @" in line:
                price_match = re.search(r'\$([0-9,]+)', line)
                order_match = re.search(r'ID[: ]+(\d+)', line)
                if price_match:
                    events.append({
                        'time': dt,
                        'type': 'SELL_ORDER',
                        'price': price_match.group(1),
                        'order_id': order_match.group(1) if order_match else 'N/A',
                        'label': f"SELL @ ${price_match.group(1)}"
                    })
            
            elif "filled @" in line:
                price_match = re.search(r'@ \$([0-9,]+)', line)
                if price_match:
                    fill_type = 'BUY_FILL' if 'BUY filled' in line else 'SELL_FILL'
                    events.append({
                        'time': dt,
                        'type': fill_type,
                        'price': price_match.group(1),
                        'order_id': 'N/A',
                        'label': f"{'BUY' if 'BUY' in line else 'SELL'} FILL @ ${price_match.group(1)}"
                    })
            
            elif "THROTTLE" in line:
                events.append({
                    'time': dt,
                    'type': 'THROTTLE',
                    'price': '',
                    'order_id': 'N/A',
                    'label': 'THROTTLE ACTIVATED'
                })
            
            elif "TP placed @" in line or "TP.*placed @" in line:
                price_match = re.search(r'@ \$([0-9,]+)', line)
                if price_match:
                    events.append({
                        'time': dt,
                        'type': 'TP_ORDER',
                        'price': price_match.group(1),
                        'order_id': 'N/A',
                        'label': f"TP @ ${price_match.group(1)}"
                    })
    
    # Sort by time
    events.sort(key=lambda x: x['time'])
    
    # Calculate time gaps for recent events
    recent = events[-50:] if len(events) > 50 else events
    for i in range(1, len(recent)):
        gap = (recent[i]['time'] - recent[i-1]['time']).total_seconds()
        recent[i]['gap'] = gap
    
    return recent

def generate_html(events):
    """Generate interactive HTML timeline"""
    
    # Prepare data for visualization
    timeline_data = []
    for i, event in enumerate(events):
        timeline_data.append({
            'index': i,
            'time': event['time'].strftime("%H:%M:%S"),
            'type': event['type'],
            'label': event['label'],
            'price': event['price'],
            'order_id': event['order_id'],
            'gap': event.get('gap', 0)
        })
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Race Condition Timeline Analysis</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #1a1a1a;
            color: #e0e0e0;
            padding: 20px;
            margin: 0;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}
        h1 {{
            margin: 0;
            font-size: 32px;
            color: white;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #2d2d2d;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid;
        }}
        .stat-card.buy {{ border-left-color: #4caf50; }}
        .stat-card.sell {{ border-left-color: #f44336; }}
        .stat-card.throttle {{ border-left-color: #ff9800; }}
        .stat-card.fill {{ border-left-color: #2196f3; }}
        .stat-label {{
            font-size: 14px;
            color: #888;
            margin-bottom: 5px;
        }}
        .stat-value {{
            font-size: 28px;
            font-weight: bold;
        }}
        .timeline {{
            background: #2d2d2d;
            border-radius: 8px;
            padding: 20px;
            overflow-x: auto;
        }}
        .event {{
            display: flex;
            align-items: center;
            padding: 12px;
            margin: 8px 0;
            border-radius: 6px;
            border-left: 4px solid;
            transition: transform 0.2s;
        }}
        .event:hover {{
            transform: translateX(5px);
            background: #3d3d3d;
        }}
        .event.BUY_ORDER {{ border-left-color: #4caf50; background: rgba(76, 175, 80, 0.1); }}
        .event.SELL_ORDER {{ border-left-color: #f44336; background: rgba(244, 67, 54, 0.1); }}
        .event.BUY_FILL {{ border-left-color: #2196f3; background: rgba(33, 150, 243, 0.1); }}
        .event.SELL_FILL {{ border-left-color: #ff5722; background: rgba(255, 87, 34, 0.1); }}
        .event.THROTTLE {{ border-left-color: #ff9800; background: rgba(255, 152, 0, 0.2); }}
        .event.TP_ORDER {{ border-left-color: #9c27b0; background: rgba(156, 39, 176, 0.1); }}
        
        .event-time {{
            font-family: 'Courier New', monospace;
            font-weight: bold;
            min-width: 100px;
            color: #64b5f6;
        }}
        .event-type {{
            min-width: 120px;
            font-weight: bold;
            font-size: 12px;
        }}
        .event-label {{
            flex: 1;
            font-size: 14px;
        }}
        .event-gap {{
            font-family: 'Courier New', monospace;
            font-size: 12px;
            color: #888;
            min-width: 80px;
            text-align: right;
        }}
        .event-gap.warning {{
            color: #ff9800;
            font-weight: bold;
        }}
        .event-gap.danger {{
            color: #f44336;
            font-weight: bold;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .legend {{
            background: #2d2d2d;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
        }}
        .legend-item {{
            display: inline-block;
            margin-right: 20px;
            margin-bottom: 10px;
        }}
        .legend-color {{
            display: inline-block;
            width: 20px;
            height: 20px;
            border-radius: 3px;
            margin-right: 8px;
            vertical-align: middle;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Race Condition Timeline Analysis</h1>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">Order Event Sequence - Last 50 Events</p>
    </div>

    <div class="stats">
        <div class="stat-card buy">
            <div class="stat-label">BUY Orders</div>
            <div class="stat-value">{sum(1 for e in timeline_data if e['type'] == 'BUY_ORDER')}</div>
        </div>
        <div class="stat-card sell">
            <div class="stat-label">SELL Orders</div>
            <div class="stat-value">{sum(1 for e in timeline_data if e['type'] == 'SELL_ORDER')}</div>
        </div>
        <div class="stat-card throttle">
            <div class="stat-label">Throttle Events</div>
            <div class="stat-value">{sum(1 for e in timeline_data if e['type'] == 'THROTTLE')}</div>
        </div>
        <div class="stat-card fill">
            <div class="stat-label">Fills</div>
            <div class="stat-value">{sum(1 for e in timeline_data if 'FILL' in e['type'])}</div>
        </div>
    </div>

    <div class="timeline">
        <h2 style="margin-top: 0;">Event Timeline</h2>
        {''.join([f'''
        <div class="event {e['type']}">
            <span class="event-time">{e['time']}</span>
            <span class="event-type">{e['type'].replace('_', ' ')}</span>
            <span class="event-label">{e['label']}</span>
            <span class="event-gap {'danger' if e['gap'] > 0 and e['gap'] < 10 else 'warning' if e['gap'] > 0 and e['gap'] < 30 else ''}">
                {f"+{e['gap']:.1f}s" if e['gap'] > 0 else ""}
            </span>
        </div>
        ''' for e in timeline_data])}
    </div>

    <div class="legend">
        <h3 style="margin-top: 0;">Legend</h3>
        <div class="legend-item">
            <span class="legend-color" style="background: #4caf50;"></span>
            BUY Order Placed
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #f44336;"></span>
            SELL Order Placed
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #2196f3;"></span>
            BUY Fill
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #ff9800;"></span>
            Throttle Activated
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #9c27b0;"></span>
            TP Order
        </div>
        <br>
        <p style="margin-top: 15px; color: #888; font-size: 14px;">
            <strong>Time Gaps:</strong> 
            <span style="color: #f44336;">● Red = &lt;10s (DANGER)</span> &nbsp;
            <span style="color: #ff9800;">● Orange = &lt;30s (WARNING)</span> &nbsp;
            <span style="color: #888;">● Gray = &gt;30s (OK)</span>
        </p>
    </div>

    <script>
        console.log('Timeline loaded with {len(timeline_data)} events');
        
        // Auto-refresh every 30 seconds
        setTimeout(function() {{
            location.reload();
        }}, 30000);
    </script>
</body>
</html>
"""
    
    return html_content

def main():
    print("🔍 Analyzing race conditions from logs...")
    events = parse_logs()
    print(f"✅ Found {len(events)} recent events")
    
    print("📊 Generating HTML visualization...")
    html = generate_html(events)
    
    OUTPUT_HTML.parent.mkdir(exist_ok=True)
    OUTPUT_HTML.write_text(html)
    
    print(f"✅ Visualization created: {OUTPUT_HTML}")
    print(f"\n🌐 Open in browser: open {OUTPUT_HTML}")
    
    # Print summary
    buy_orders = sum(1 for e in events if e['type'] == 'BUY_ORDER')
    sell_orders = sum(1 for e in events if e['type'] == 'SELL_ORDER')
    throttles = sum(1 for e in events if e['type'] == 'THROTTLE')
    fills = sum(1 for e in events if 'FILL' in e['type'])
    
    print(f"\n📈 Summary:")
    print(f"   BUY Orders: {buy_orders}")
    print(f"   SELL Orders: {sell_orders}")
    print(f"   Throttle Events: {throttles}")
    print(f"   Fills: {fills}")
    
    # Check for rapid orders
    rapid = [e for e in events if e.get('gap', 100) < 30 and e['type'] in ['BUY_ORDER', 'SELL_ORDER']]
    if rapid:
        print(f"\n⚠️  WARNING: {len(rapid)} orders placed < 30s apart!")
        for r in rapid[:5]:
            print(f"   - {r['time'].strftime('%H:%M:%S')}: {r['label']} (+{r['gap']:.1f}s)")

if __name__ == "__main__":
    main()
