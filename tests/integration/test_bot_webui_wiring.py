#!/usr/bin/env python3
"""
End-to-End Bot-to-WebUI Integration Tests

Tests that WebUI correctly communicates with bot and monitoring systems

Usage:
    pytest tests/integration/test_bot_webui_wiring.py -v

Requirements:
    - Bot must be running
    - WebUI backend must be running (port 5001)
    - pytest, requests installed

Date: November 8, 2025
"""

import pytest
import requests
import json
import time
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:5555"
RUNTIME_STATE_FILE = Path("runtime_state.json")

class TestBotWebUIWiring:
    """Test suite for bot-WebUI integration"""
    
    def test_webui_is_running(self):
        """Verify WebUI backend is accessible"""
        try:
            response = requests.get(f"{BASE_URL}/api/health", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert 'status' in data
            print(f"✅ WebUI is running: {data.get('status')}")
        except requests.exceptions.ConnectionError:
            pytest.skip("WebUI is not running - start with: python webui/backend/app.py")
    
    def test_monitoring_routes_exist(self):
        """Verify all monitoring API routes are registered"""
        response = requests.get(f"{BASE_URL}/api/debug/routes")
        assert response.status_code == 200
        
        routes = response.json()['routes']
        route_paths = [r['path'] for r in routes]
        
        expected_routes = [
            '/api/monitoring/status',
            '/api/monitoring/price-health',
            '/api/monitoring/pre-order-stats',
            '/api/monitoring/tp-verification',
            '/api/monitoring/anomalies',
            '/api/monitoring/predictive-map'
        ]
        
        for route in expected_routes:
            assert route in route_paths, f"Route {route} not found"
            print(f"✅ Route exists: {route}")
    
    def test_monitoring_status(self):
        """Verify monitoring status endpoint"""
        response = requests.get(f"{BASE_URL}/api/monitoring/status")
        assert response.status_code == 200
        
        data = response.json()
        assert 'monitoring_active' in data
        assert 'layers' in data
        assert 'timestamp' in data
        
        layers = data['layers']
        assert 'price_health' in layers
        assert 'pre_order_logger' in layers
        assert 'tp_verification' in layers
        assert 'anomaly_detection' in layers
        assert 'predictive_display' in layers
        
        print(f"✅ Monitoring status: active={data['monitoring_active']}")
        print(f"   Layers: {sum(layers.values())}/5 available")
    
    def test_price_health_endpoint(self):
        """Verify price health monitoring endpoint"""
        response = requests.get(f"{BASE_URL}/api/monitoring/price-health")
        
        # Either 200 (bot running) or 503 (bot not running)
        assert response.status_code in [200, 503]
        
        data = response.json()
        
        if response.status_code == 200:
            assert 'fresh' in data
            assert 'age_seconds' in data
            assert 'source' in data
            assert 'thresholds' in data
            print(f"✅ Price health: fresh={data['fresh']}, age={data.get('age_seconds')}s")
        else:
            assert 'error' in data
            print(f"⚠️  Price health unavailable: {data['error']}")
    
    def test_pre_order_stats_endpoint(self):
        """Verify pre-order statistics endpoint"""
        response = requests.get(f"{BASE_URL}/api/monitoring/pre-order-stats")
        
        assert response.status_code in [200, 503]
        data = response.json()
        
        if response.status_code == 200:
            assert 'approved' in data
            assert 'rejected' in data
            assert 'total' in data
            assert 'approval_rate' in data
            print(f"✅ Pre-order stats: {data['approved']}/{data['total']} approved ({data['approval_rate']}%)")
        else:
            print(f"⚠️  Pre-order stats unavailable: {data['error']}")
    
    def test_tp_verification_endpoint(self):
        """Verify TP verification endpoint"""
        response = requests.get(f"{BASE_URL}/api/monitoring/tp-verification")
        
        assert response.status_code in [200, 503]
        data = response.json()
        
        if response.status_code == 200:
            assert 'verified' in data
            assert 'orphaned' in data
            assert 'success_rate' in data
            print(f"✅ TP verification: {data['verified']} verified, {data['orphaned']} orphaned")
        else:
            print(f"⚠️  TP verification unavailable: {data['error']}")
    
    def test_anomalies_endpoint(self):
        """Verify anomaly detection endpoint"""
        response = requests.get(f"{BASE_URL}/api/monitoring/anomalies")
        
        assert response.status_code in [200, 503]
        data = response.json()
        
        if response.status_code == 200:
            assert 'anomalies' in data
            assert 'count' in data
            print(f"✅ Anomalies: {data['count']} detected")
        else:
            print(f"⚠️  Anomaly detection unavailable: {data['error']}")
    
    def test_predictive_map_endpoint(self):
        """Verify predictive decision map endpoint"""
        response = requests.get(f"{BASE_URL}/api/monitoring/predictive-map")
        
        assert response.status_code in [200, 503]
        data = response.json()
        
        if response.status_code == 200:
            assert 'current_price' in data
            assert 'next_levels' in data
            assert 'mode' in data
            assert 'capacity' in data
            print(f"✅ Predictive map: mode={data['mode']}, price=${data.get('current_price')}")
        else:
            print(f"⚠️  Predictive map unavailable: {data['error']}")
    
    def test_bot_status_matches_reality(self):
        """Verify /api/bot/status matches actual bot state"""
        response = requests.get(f"{BASE_URL}/api/bot/status")
        assert response.status_code == 200
        
        data = response.json()
        bot_running = data.get('running', False)
        
        # If bot claims to be running, runtime_state.json should exist
        if bot_running and RUNTIME_STATE_FILE.exists():
            with open(RUNTIME_STATE_FILE) as f:
                state = json.load(f)
            
            # State file should have recent timestamp
            if 'metadata' in state:
                last_update = state['metadata'].get('last_update')
                print(f"✅ Bot state file last update: {last_update}")
        else:
            print(f"⚠️  Bot not running or state file missing")
    
    def test_positions_sync_with_bot_state(self):
        """Verify /api/positions returns bot's actual positions"""
        # Get positions from WebUI
        response = requests.get(f"{BASE_URL}/api/positions")
        
        if response.status_code != 200:
            pytest.skip("Positions endpoint not available")
        
        webui_positions = response.json()
        
        # Get positions directly from bot state file
        if not RUNTIME_STATE_FILE.exists():
            pytest.skip("Runtime state file not found")
        
        with open(RUNTIME_STATE_FILE) as f:
            bot_state = json.load(f)
        
        bot_positions = bot_state.get('data', {}).get('open_tranches', [])
        
        # Counts should match
        assert len(webui_positions) == len(bot_positions), \
            f"Position count mismatch: WebUI={len(webui_positions)}, Bot={len(bot_positions)}"
        
        print(f"✅ Position counts match: {len(webui_positions)} positions")


class TestMonitoringDataQuality:
    """Test data quality of monitoring endpoints"""
    
    def test_price_health_realistic_values(self):
        """Verify price health returns realistic values"""
        response = requests.get(f"{BASE_URL}/api/monitoring/price-health")
        
        if response.status_code != 200:
            pytest.skip("Price health monitor not available")
        
        data = response.json()
        
        # Age should be reasonable (< 60s if WebSocket working)
        if data.get('age_seconds') is not None:
            assert data['age_seconds'] < 300, "Price age >5 minutes - likely stale"
        
        # Thresholds should be set
        thresholds = data.get('thresholds', {})
        assert thresholds.get('stale') > 0
        assert thresholds.get('critical') > thresholds.get('stale')
        
        print(f"✅ Price health values are realistic")
    
    def test_predictive_map_has_valid_prices(self):
        """Verify predictive map returns valid price levels"""
        response = requests.get(f"{BASE_URL}/api/monitoring/predictive-map")
        
        if response.status_code != 200:
            pytest.skip("Predictive map not available")
        
        data = response.json()
        
        current_price = data.get('current_price')
        if current_price:
            assert current_price > 0, "Current price must be positive"
            
            # Next levels should be around current price
            next_levels = data.get('next_levels', [])
            if next_levels:
                for level in next_levels:
                    level_price = level.get('price')
                    assert abs(level_price - current_price) / current_price < 0.5, \
                        "Next level price too far from current (>50%)"
        
        print(f"✅ Predictive map prices are valid")


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
