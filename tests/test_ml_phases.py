#!/usr/bin/env python3
"""
Test script for ML Autonomous Trading Engine Phases 2-5
Tests all new API endpoints
"""

import requests
import json

API_BASE = "http://localhost:5555"

def test_endpoint(name, url, method='GET', data=None):
    """Test a single endpoint"""
    try:
        if method == 'GET':
            response = requests.get(url, timeout=5)
        else:
            response = requests.post(url, json=data, timeout=5)
        
        result = response.json()
        success = result.get('success', False) or response.status_code == 200
        
        print(f"{'✅' if success else '❌'} {name}: {response.status_code}")
        if not success and 'error' in result:
            print(f"   Error: {result['error']}")
        return success
    except Exception as e:
        print(f"❌ {name}: {str(e)}")
        return False

print("\n" + "="*60)
print("Testing ML Autonomous Trading Engine - Phases 2-5")
print("="*60 + "\n")

# Phase 2: Style Profiler
print("PHASE 2: Style Profiler")
print("-" * 40)
test_endpoint("Style Profile", f"{API_BASE}/api/ml/style/profile")
test_endpoint("Style Summary", f"{API_BASE}/api/ml/style/summary")
print()

# Phase 3: Opportunity Scanner
print("PHASE 3: Opportunity Scanner")
print("-" * 40)
test_endpoint("Current Regime", f"{API_BASE}/api/ml/regime/current")
test_endpoint("Get Opportunities", f"{API_BASE}/api/ml/scanner/opportunities")
test_endpoint("Get Signals", f"{API_BASE}/api/ml/scanner/signals")
print()

# Phase 4: Decision Engine
print("PHASE 4: Decision Engine")
print("-" * 40)
test_endpoint("Engine Status", f"{API_BASE}/api/ml/decision/status")
test_endpoint("Pending Decisions", f"{API_BASE}/api/ml/decision/pending")
test_endpoint("Circuit Breaker", f"{API_BASE}/api/ml/circuit-breaker/status")
print()

# Phase 5: Continuous Learning
print("PHASE 5: Continuous Learning & Monitoring")
print("-" * 40)
test_endpoint("Learning Stats", f"{API_BASE}/api/ml/learning/stats")
test_endpoint("Performance Metrics", f"{API_BASE}/api/ml/monitor/metrics?days=30")
test_endpoint("Drift Detection", f"{API_BASE}/api/ml/monitor/drift")
test_endpoint("Retrain Status", f"{API_BASE}/api/ml/monitor/should-retrain")
test_endpoint("Monitor Alerts", f"{API_BASE}/api/ml/monitor/alerts")
print()

print("="*60)
print("Testing Complete!")
print("="*60 + "\n")
