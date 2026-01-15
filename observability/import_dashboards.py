#!/usr/bin/env python3
"""
Automatically import all WorkingBot dashboards into Grafana
"""
import json
import requests
import os

GRAFANA_URL = "http://localhost:3000"
GRAFANA_USER = "admin"
GRAFANA_PASS = "admin"

dashboards = [
    ("observability/dashboards/trading_performance.json", "Trading Performance"),
    ("observability/dashboards/system_health.json", "System Health"),
    ("observability/dashboards/risk_management.json", "Risk Management"),
    ("observability/dashboards/options_analytics.json", "Options Analytics"),
]

print("🚀 Importing WorkingBot Dashboards to Grafana...\n")

for dashboard_file, name in dashboards:
    print(f"📊 Importing: {name}")
    
    try:
        # Read dashboard JSON
        with open(dashboard_file, 'r') as f:
            dashboard = json.load(f)
        
        # Prepare import payload
        payload = {
            "dashboard": dashboard,
            "overwrite": True,
            "inputs": [{
                "name": "DS_PROMETHEUS",
                "type": "datasource",
                "pluginId": "prometheus",
                "value": "Prometheus"
            }]
        }
        
        # Import via API
        response = requests.post(
            f"{GRAFANA_URL}/api/dashboards/import",
            json=payload,
            auth=(GRAFANA_USER, GRAFANA_PASS),
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Success! Dashboard ID: {result.get('dashboardId', 'unknown')}")
            print(f"   📍 URL: {GRAFANA_URL}{result.get('importedUrl', '')}")
        else:
            print(f"   ⚠️  Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()

print("✨ Dashboard import complete!\n")
print(f"🌐 Open Grafana: {GRAFANA_URL}")
print("📊 Go to Dashboards → Browse to see your imported dashboards\n")
