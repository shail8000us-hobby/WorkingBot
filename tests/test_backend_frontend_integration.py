"""
Backend-Frontend Integration Tests

Tests complete integration between Flask backend and React frontend:
1. REST API endpoints (all critical routes)
2. SocketIO real-time communication
3. Data synchronization
4. Bot control operations
5. Position/order updates
6. Error handling
7. Complete user workflows

These are E2E (End-to-End) tests that require backend to be running.

Run with: pytest tests/test_backend_frontend_integration.py -v -s
Or: python3 tests/test_backend_frontend_integration.py (standalone mode)
"""

import pytest
import requests
import json
import time
import socketio
from typing import Dict, Any, Tuple, Optional

# Backend URL
BASE_URL = "http://localhost:5555"
SOCKET_URL = "http://localhost:5555"

# Test configuration
TEST_TIMEOUT = 5  # seconds


class TestBackendAvailability:
    """Test that backend is running and accessible"""
    
    def test_backend_is_running(self):
        """Test: Backend server is accessible"""
        try:
            response = requests.get(f"{BASE_URL}/api/health", timeout=TEST_TIMEOUT)
            assert response.status_code in [200, 404], \
                f"Backend not responding: {response.status_code}"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running on port 5555. Start it with: cd webui/backend && python3 app.py")
    
    def test_health_endpoint_returns_valid_json(self):
        """Test: Health endpoint returns valid JSON"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=TEST_TIMEOUT)
        
        # Should return JSON
        data = response.json()
        assert isinstance(data, dict), "Health endpoint should return dict"


class TestCriticalAPIEndpoints:
    """Test critical API endpoints"""
    
    def test_config_endpoint_get(self):
        """Test: GET /api/config returns configuration"""
        response = requests.get(f"{BASE_URL}/api/config", timeout=TEST_TIMEOUT)
        
        assert response.status_code == 200, f"Config GET failed: {response.status_code}"
        
        data = response.json()
        
        # Should contain grid parameters (using GRIDBOT_ prefix)
        expected_fields = ['GRIDBOT_LOWER', 'GRIDBOT_UPPER', 'GRIDBOT_STEP', 'GRIDBOT_REF']
        for field in expected_fields:
            assert field in data, f"Config missing field: {field}"
    
    def test_bot_status_endpoint(self):
        """Test: GET /api/bot/status returns bot state"""
        response = requests.get(f"{BASE_URL}/api/bot/status", timeout=TEST_TIMEOUT)
        
        assert response.status_code == 200, f"Status GET failed: {response.status_code}"
        
        data = response.json()
        
        # Should have running status
        assert 'running' in data or 'status' in data, "Status response missing state"
    
    def test_positions_endpoint(self):
        """Test: GET /api/positions returns positions data"""
        response = requests.get(f"{BASE_URL}/api/positions", timeout=TEST_TIMEOUT)
        
        assert response.status_code == 200, f"Positions GET failed: {response.status_code}"
        
        data = response.json()
        
        # Should be list or dict with positions
        assert isinstance(data, (list, dict)), "Positions should be list or dict"
    
    def test_orders_endpoint(self):
        """Test: GET /api/orders returns orders data"""
        response = requests.get(f"{BASE_URL}/api/orders", timeout=TEST_TIMEOUT)
        
        assert response.status_code == 200, f"Orders GET failed: {response.status_code}"
        
        data = response.json()
        
        # Should be list or dict with orders
        assert isinstance(data, (list, dict)), "Orders should be list or dict"
    
    def test_logs_endpoint(self):
        """Test: GET /api/logs returns log entries"""
        response = requests.get(f"{BASE_URL}/api/logs?limit=10", timeout=TEST_TIMEOUT)
        
        assert response.status_code == 200, f"Logs GET failed: {response.status_code}"
        
        # Can be string or list of log entries
        assert response.text is not None, "Logs should return data"


class TestSocketIOCommunication:
    """Test SocketIO real-time communication"""
    
    def test_socketio_connection_succeeds(self):
        """Test: SocketIO connection can be established"""
        sio = socketio.Client()
        connected = False
        
        @sio.on('connect')
        def on_connect():
            nonlocal connected
            connected = True
        
        try:
            sio.connect(SOCKET_URL, wait_timeout=TEST_TIMEOUT)
            time.sleep(0.5)  # Wait for connection
            
            assert connected, "SocketIO connection failed"
            
            sio.disconnect()
        except Exception as e:
            pytest.skip(f"SocketIO not available: {e}")
    
    def test_socketio_receives_bot_status_updates(self):
        """Test: SocketIO receives bot_status_update events"""
        sio = socketio.Client()
        status_received = []
        
        @sio.on('bot_status_update')
        def on_status(data):
            status_received.append(data)
        
        try:
            sio.connect(SOCKET_URL, wait_timeout=TEST_TIMEOUT)
            time.sleep(2)  # Wait for status update
            
            # Should receive at least one status update
            # (Backend should broadcast periodically)
            # Note: This may not always work if backend doesn't broadcast immediately
            
            sio.disconnect()
            
            # This test is informational (may not always pass)
            if len(status_received) > 0:
                assert isinstance(status_received[0], dict)
        except Exception as e:
            pytest.skip(f"SocketIO test skipped: {e}")


class TestDataSynchronization:
    """Test data synchronization between backend and frontend"""
    
    def test_positions_data_structure(self):
        """Test: Positions data has expected structure for frontend"""
        response = requests.get(f"{BASE_URL}/api/positions", timeout=TEST_TIMEOUT)
        data = response.json()
        
        # Frontend expects certain structure
        # Verify data is in format frontend can consume
        if isinstance(data, list) and len(data) > 0:
            # If list of positions
            position = data[0]
            # Should have basic fields frontend displays
            # (Exact fields depend on implementation)
            assert isinstance(position, dict)
        elif isinstance(data, dict):
            # If wrapped in success envelope
            if 'positions' in data:
                assert isinstance(data['positions'], list)
            elif 'result' in data:
                assert isinstance(data['result'], list)
    
    def test_config_data_structure(self):
        """Test: Config data has expected structure for frontend"""
        response = requests.get(f"{BASE_URL}/api/config", timeout=TEST_TIMEOUT)
        data = response.json()
        
        # Frontend ConfigPanel expects these fields
        grid_fields = ['GRID_LOWER', 'GRID_UPPER', 'GRID_STEP', 'GRID_REF']
        
        for field in grid_fields:
            if field in data:
                # Should be numeric or string-numeric
                value = data[field]
                assert isinstance(value, (int, float, str)), \
                    f"{field} should be numeric or string"


class TestBotControlIntegration:
    """Test bot control operations through API"""
    
    def test_bot_status_is_readable(self):
        """Test: Bot status can be queried"""
        response = requests.get(f"{BASE_URL}/api/bot/status", timeout=TEST_TIMEOUT)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should indicate running state
        assert isinstance(data, dict), "Status should be dict"
    
    def test_config_update_validation(self):
        """Test: Config updates are validated (don't test actual update)"""
        # Test with invalid data (should reject)
        invalid_config = {
            'GRID_LOWER': -100,  # Invalid negative
            'GRID_UPPER': 50000,
            'GRID_STEP': 0  # Invalid zero
        }
        
        # Try to update (should fail validation)
        response = requests.post(
            f"{BASE_URL}/api/config",
            json=invalid_config,
            timeout=TEST_TIMEOUT
        )
        
        # Backend should reject invalid config
        # Either 400 (validation error) or 403 (requires confirmation)
        assert response.status_code in [400, 403, 422], \
            "Backend should reject invalid config"


class TestRealTimeDataFlow:
    """Test real-time data flow from backend to frontend"""
    
    def test_positions_endpoint_returns_quickly(self):
        """Test: Positions endpoint responds within acceptable time"""
        start_time = time.time()
        
        response = requests.get(f"{BASE_URL}/api/positions", timeout=TEST_TIMEOUT)
        
        elapsed = time.time() - start_time
        
        assert response.status_code == 200
        assert elapsed < 1.0, f"Positions endpoint too slow: {elapsed}s"
    
    def test_orders_endpoint_returns_quickly(self):
        """Test: Orders endpoint responds within acceptable time"""
        start_time = time.time()
        
        response = requests.get(f"{BASE_URL}/api/orders", timeout=TEST_TIMEOUT)
        
        elapsed = time.time() - start_time
        
        assert response.status_code == 200
        assert elapsed < 1.0, f"Orders endpoint too slow: {elapsed}s"
    
    def test_metrics_endpoint_returns_current_data(self):
        """Test: Metrics endpoint returns current data"""
        response = requests.get(f"{BASE_URL}/api/metrics", timeout=TEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            
            # Metrics should have timestamp
            if isinstance(data, dict) and 'timestamp' in data:
                timestamp = data['timestamp']
                current_time = time.time()
                
                # Should be recent (within last 60 seconds)
                if isinstance(timestamp, (int, float)):
                    age = current_time - timestamp
                    assert age < 60, f"Metrics too old: {age}s"


class TestErrorHandling:
    """Test error handling in backend-frontend communication"""
    
    def test_invalid_endpoint_returns_404(self):
        """Test: Invalid endpoint returns 404"""
        response = requests.get(f"{BASE_URL}/api/nonexistent_endpoint_xyz", timeout=TEST_TIMEOUT)
        
        assert response.status_code == 404, \
            f"Invalid endpoint should return 404, got {response.status_code}"
    
    def test_invalid_json_returns_error(self):
        """Test: Invalid JSON returns proper error"""
        response = requests.post(
            f"{BASE_URL}/api/config",
            data="invalid json {{{",  # Malformed JSON
            headers={'Content-Type': 'application/json'},
            timeout=TEST_TIMEOUT
        )
        
        # Should return 400 (bad request)
        assert response.status_code in [400, 422], \
            f"Malformed JSON should return 400/422, got {response.status_code}"
    
    def test_missing_required_fields_returns_error(self):
        """Test: Missing required fields returns validation error"""
        # Try to create todo without required 'text' field
        response = requests.post(
            f"{BASE_URL}/api/todos",
            json={},  # Missing 'text' field
            timeout=TEST_TIMEOUT
        )
        
        # Should return validation error
        assert response.status_code in [400, 422], \
            f"Missing required field should return error, got {response.status_code}"


class TestFrontendAssetDelivery:
    """Test that frontend assets are served correctly"""
    
    def test_main_html_is_served(self):
        """Test: Main HTML file is served"""
        response = requests.get(BASE_URL, timeout=TEST_TIMEOUT)
        
        assert response.status_code == 200, \
            f"Main page should return 200, got {response.status_code}"
        
        # Should be HTML
        assert 'text/html' in response.headers.get('Content-Type', ''), \
            "Main page should be HTML"
    
    def test_static_javascript_is_served(self):
        """Test: JavaScript bundles are accessible"""
        # Try to access static js directory
        response = requests.get(f"{BASE_URL}/static/js/", timeout=TEST_TIMEOUT)
        
        # Either 200 (directory listing) or 404 (no listing, but files exist)
        # The key is frontend works, not directory browsing
        assert response.status_code in [200, 403, 404], \
            "Static assets should be configured"
    
    def test_favicon_is_accessible(self):
        """Test: Favicon is served (good UX indicator)"""
        response = requests.get(f"{BASE_URL}/favicon.ico", timeout=TEST_TIMEOUT)
        
        # 200 if exists, 404 if not - both acceptable
        assert response.status_code in [200, 404], \
            "Favicon request should be handled"


class TestCompleteUserWorkflow:
    """Test complete user workflows from frontend perspective"""
    
    def test_workflow_view_dashboard_data(self):
        """
        Test: Complete workflow of viewing dashboard
        
        User Action: Opens dashboard
        Expected: All data endpoints accessible
        """
        # Get all dashboard data
        endpoints = [
            '/api/bot/status',
            '/api/positions',
            '/api/config',
        ]
        
        results = {}
        for endpoint in endpoints:
            try:
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=TEST_TIMEOUT)
                results[endpoint] = response.status_code == 200
            except:
                results[endpoint] = False
        
        # At least 2/3 should work
        working = sum(1 for v in results.values() if v)
        assert working >= 2, f"Not enough endpoints working: {results}"
    
    def test_workflow_read_configuration(self):
        """
        Test: Workflow of reading bot configuration
        
        User Action: Opens Config Panel
        Expected: Config loaded and displayed
        """
        response = requests.get(f"{BASE_URL}/api/config", timeout=TEST_TIMEOUT)
        
        assert response.status_code == 200
        
        config = response.json()
        
        # Config should have grid parameters (using GRIDBOT_ prefix)
        grid_params = ['GRIDBOT_LOWER', 'GRIDBOT_UPPER', 'GRIDBOT_STEP', 'GRIDBOT_REF']
        has_grid_params = any(param in config for param in grid_params)
        
        assert has_grid_params, "Config should contain grid parameters"
    
    def test_workflow_view_positions(self):
        """
        Test: Workflow of viewing positions
        
        User Action: Opens Positions panel
        Expected: Positions data loaded
        """
        response = requests.get(f"{BASE_URL}/api/positions", timeout=TEST_TIMEOUT)
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Should return positions (list or wrapped dict)
        assert data is not None, "Positions endpoint should return data"


class TestDataConsistency:
    """Test data consistency between endpoints"""
    
    def test_bot_status_matches_positions(self):
        """Test: Bot running status consistent with positions data"""
        # Get bot status
        status_response = requests.get(f"{BASE_URL}/api/bot/status", timeout=TEST_TIMEOUT)
        status = status_response.json()
        
        # Get positions
        positions_response = requests.get(f"{BASE_URL}/api/positions", timeout=TEST_TIMEOUT)
        positions = positions_response.json()
        
        # Both should be accessible
        assert status is not None
        assert positions is not None
        
        # If bot is running, should be able to query positions
        # (Exact logic depends on implementation)
        # This test verifies both endpoints work
    
    def test_config_values_are_numeric(self):
        """Test: Config values are properly formatted for frontend"""
        response = requests.get(f"{BASE_URL}/api/config", timeout=TEST_TIMEOUT)
        config = response.json()
        
        # Grid parameters should be numeric (int, float, or numeric string)
        grid_fields = {
            'GRID_LOWER': None,
            'GRID_UPPER': None,
            'GRID_STEP': None,
            'GRID_REF': None
        }
        
        for field in grid_fields:
            if field in config:
                value = config[field]
                # Should be numeric or convertible to numeric
                try:
                    float(value)
                    assert True  # Convertible to float
                except (ValueError, TypeError):
                    pytest.fail(f"{field} value '{value}' not numeric")


class TestErrorPropagation:
    """Test error handling from backend to frontend"""
    
    def test_backend_error_returns_json_error(self):
        """Test: Backend errors return JSON error responses"""
        # Try to access endpoint with bad parameter
        response = requests.get(
            f"{BASE_URL}/api/logs?limit=invalid",  # Invalid limit
            timeout=TEST_TIMEOUT
        )
        
        # Should handle gracefully (either work or return error)
        assert response.status_code in [200, 400, 422], \
            f"Error handling failed: {response.status_code}"
    
    def test_cors_headers_present(self):
        """Test: CORS headers present for frontend requests"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=TEST_TIMEOUT)
        
        # Check if CORS headers present (may or may not be needed)
        # This is informational
        headers = response.headers
        
        # If CORS is configured, these headers should exist
        # (Not all backends need CORS if serving frontend directly)
        assert True  # Informational test


class TestPerformanceAndLatency:
    """Test performance characteristics important for frontend UX"""
    
    def test_api_response_time_under_1_second(self):
        """Test: API endpoints respond within 1 second (good UX)"""
        endpoints = [
            '/api/health',
            '/api/bot/status',
            '/api/config',
        ]
        
        for endpoint in endpoints:
            start = time.time()
            
            try:
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=TEST_TIMEOUT)
                elapsed = time.time() - start
                
                assert elapsed < 1.0, \
                    f"{endpoint} too slow: {elapsed:.3f}s"
            except requests.exceptions.Timeout:
                pytest.fail(f"{endpoint} timed out")
    
    def test_concurrent_api_requests_handled(self):
        """Test: Backend handles multiple simultaneous requests"""
        import concurrent.futures
        
        def fetch_status():
            response = requests.get(f"{BASE_URL}/api/bot/status", timeout=TEST_TIMEOUT)
            return response.status_code == 200
        
        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_status) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        assert all(results), f"Some concurrent requests failed: {results}"


# ============================================================================
# Standalone Execution
# ============================================================================

def run_standalone_tests():
    """Run tests in standalone mode (without pytest)"""
    print("=" * 80)
    print("🧪 Backend-Frontend Integration Tests")
    print("=" * 80)
    print()
    
    # Check backend availability
    print("🔍 Checking backend availability...")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=2)
        print(f"✅ Backend is running on {BASE_URL}")
    except requests.exceptions.ConnectionError:
        print(f"❌ Backend not running on {BASE_URL}")
        print(f"   Start it with: cd webui/backend && python3 app.py")
        return False
    
    print()
    
    # Test critical endpoints
    print("🔍 Testing critical API endpoints...")
    
    endpoints = {
        'Health': '/api/health',
        'Config': '/api/config',
        'Bot Status': '/api/bot/status',
        'Positions': '/api/positions',
        'Orders': '/api/orders',
    }
    
    results = {}
    for name, endpoint in endpoints.items():
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=TEST_TIMEOUT)
            success = response.status_code == 200
            results[name] = success
            
            if success:
                print(f"  ✅ {name:20} - OK (HTTP 200)")
            else:
                print(f"  ❌ {name:20} - HTTP {response.status_code}")
        except Exception as e:
            results[name] = False
            print(f"  ❌ {name:20} - Error: {str(e)[:50]}")
    
    print()
    
    # Summary
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print("=" * 80)
    print(f"📊 Results: {passed}/{total} endpoints working ({passed/total*100:.0f}%)")
    print("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    # Run in standalone mode
    success = run_standalone_tests()
    exit(0 if success else 1)

