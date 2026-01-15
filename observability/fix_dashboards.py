#!/usr/bin/env python3
"""
Fix and re-import Grafana dashboards with correct datasource UID
"""
import json
import requests
import os
from pathlib import Path

# Grafana config
GRAFANA_URL = "http://localhost:3000"
GRAFANA_USER = "admin"
GRAFANA_PASS = "admin"

# Get datasource UID
response = requests.get(
    f"{GRAFANA_URL}/api/datasources",
    auth=(GRAFANA_USER, GRAFANA_PASS)
)
datasources = response.json()
prometheus_uid = None
for ds in datasources:
    if ds['type'] == 'prometheus':
        prometheus_uid = ds['uid']
        print(f"✅ Found Prometheus datasource: {prometheus_uid}")
        break

if not prometheus_uid:
    print("❌ Prometheus datasource not found!")
    exit(1)

# Dashboard files
dashboard_dir = Path("observability/dashboards")
dashboard_files = [
    "trading_performance.json",
    "system_health.json",
    "risk_management.json",
    "options_analytics.json"
]

print(f"\n🔧 Updating and importing dashboards...")

for filename in dashboard_files:
    filepath = dashboard_dir / filename
    if not filepath.exists():
        print(f"⚠️  {filename} not found")
        continue
    
    # Load dashboard
    with open(filepath, 'r') as f:
        dashboard_json = json.load(f)
    
    # Replace datasource references
    dashboard_str = json.dumps(dashboard_json)
    dashboard_str = dashboard_str.replace('${DS_PROMETHEUS}', prometheus_uid)
    dashboard_json = json.loads(dashboard_str)
    
    # Remove null id to let Grafana assign new one if needed
    if dashboard_json.get('id') is None:
        dashboard_json.pop('id', None)
    
    # Prepare import payload
    payload = {
        "dashboard": dashboard_json,
        "overwrite": True,
        "message": "Updated datasource UID"
    }
    
    # Import to Grafana
    response = requests.post(
        f"{GRAFANA_URL}/api/dashboards/db",
        auth=(GRAFANA_USER, GRAFANA_PASS),
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    if response.status_code == 200:
        result = response.json()
        dashboard_title = dashboard_json.get('title', filename)
        dashboard_url = f"{GRAFANA_URL}{result.get('url', '')}"
        print(f"✅ {dashboard_title}")
        print(f"   → {dashboard_url}")
    else:
        print(f"❌ Failed to import {filename}: {response.text}")

print(f"\n🎉 Dashboard update complete!")
print(f"\n📊 Access Grafana: {GRAFANA_URL}")
print(f"   Username: {GRAFANA_USER}")
print(f"   Password: {GRAFANA_PASS}")
