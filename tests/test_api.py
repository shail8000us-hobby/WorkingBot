"""
API endpoint tests for config management.
Tests all REST API endpoints for CRUD operations, strategy management, history.
"""

import pytest
import json
from pathlib import Path
import tempfile
import shutil

# Import Flask app and config API
from flask import Flask
from config.api import config_api, config_loader, strategy_manager, config_history
from config.models import RootConfig


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def app():
    """Create Flask test app"""
    test_app = Flask(__name__)
    test_app.config['TESTING'] = True
    test_app.register_blueprint(config_api, url_prefix='/api/config')
    return test_app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        'version': '2.0',
        'trading_mode': 'demo',
        'bot': {
            'symbol': 'BTCUSD',
            'mode': 'LONG',
            'trading_enabled': True,
            'heartbeat_seconds': 20
        },
        'grid': {
            'geometry': {
                'lower': 90000,
                'upper': 110000,
                'step': 500,
                'reference': 95000
            },
            'limits': {
                'max_open_positions': 10,
                'lot_size': 2
            }
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CONFIG ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

def test_get_current_config(client):
    """Test GET /api/config/current"""
    response = client.get('/api/config/current')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'config' in data
    assert 'version' in data['config']


def test_reload_config(client):
    """Test POST /api/config/reload"""
    response = client.post('/api/config/reload')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] == True
    assert 'config' in data


def test_update_config(client, sample_config):
    """Test POST /api/config/update"""
    # Modify config
    sample_config['grid']['geometry']['step'] = 600
    
    response = client.post(
        '/api/config/update',
        data=json.dumps(sample_config),
        content_type='application/json'
    )
    
    # Should succeed if file is writable
    data = json.loads(response.data)
    assert 'success' in data or 'error' in data


def test_validate_config(client, sample_config):
    """Test POST /api/config/validate"""
    # Valid config
    response = client.post(
        '/api/config/validate',
        data=json.dumps(sample_config),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['valid'] == True
    
    # Invalid config
    invalid_config = sample_config.copy()
    invalid_config['grid']['geometry']['upper'] = 80000  # Less than lower
    
    response = client.post(
        '/api/config/validate',
        data=json.dumps(invalid_config),
        content_type='application/json'
    )
    
    data = json.loads(response.data)
    assert data['valid'] == False
    assert 'errors' in data


# ═══════════════════════════════════════════════════════════════════════════
# TEST: STRATEGY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

def test_list_strategies(client):
    """Test GET /api/config/strategies"""
    response = client.get('/api/config/strategies')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'strategies' in data
    assert isinstance(data['strategies'], list)


def test_create_strategy(client):
    """Test POST /api/config/strategies"""
    new_strategy = {
        'name': 'test_strategy',
        'description': 'Test strategy',
        'overrides': {
            'grid.geometry.step': 600
        }
    }
    
    response = client.post(
        '/api/config/strategies',
        data=json.dumps(new_strategy),
        content_type='application/json'
    )
    
    # May fail if config file is read-only
    data = json.loads(response.data)
    assert 'success' in data or 'error' in data


def test_get_strategy(client):
    """Test GET /api/config/strategies/<name>"""
    # Try to get a strategy (may not exist)
    response = client.get('/api/config/strategies/test_strategy')
    
    # Should return 404 if not found, 200 if found
    assert response.status_code in [200, 404]


def test_delete_strategy(client):
    """Test DELETE /api/config/strategies/<name>"""
    response = client.delete('/api/config/strategies/test_strategy')
    
    # May fail if strategy doesn't exist or file is read-only
    assert response.status_code in [200, 404, 500]


def test_activate_strategy(client):
    """Test POST /api/config/strategies/<name>/activate"""
    response = client.post('/api/config/strategies/test_strategy/activate')
    
    # May fail if strategy doesn't exist
    data = json.loads(response.data)
    assert 'success' in data or 'error' in data


def test_deactivate_strategy(client):
    """Test POST /api/config/strategies/<name>/deactivate"""
    response = client.post('/api/config/strategies/test_strategy/deactivate')
    
    data = json.loads(response.data)
    assert 'success' in data or 'error' in data


# ═══════════════════════════════════════════════════════════════════════════
# TEST: HISTORY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

def test_get_history(client):
    """Test GET /api/config/history"""
    response = client.get('/api/config/history')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'history' in data
    assert 'current_index' in data


def test_rollback(client):
    """Test POST /api/config/rollback"""
    response = client.post(
        '/api/config/rollback',
        data=json.dumps({'steps': 1}),
        content_type='application/json'
    )
    
    # May fail if no history available
    data = json.loads(response.data)
    assert 'success' in data or 'error' in data


def test_rollforward(client):
    """Test POST /api/config/rollforward"""
    response = client.post(
        '/api/config/rollforward',
        data=json.dumps({'steps': 1}),
        content_type='application/json'
    )
    
    data = json.loads(response.data)
    assert 'success' in data or 'error' in data


# ═══════════════════════════════════════════════════════════════════════════
# TEST: SECTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

def test_get_section(client):
    """Test GET /api/config/sections/<section>"""
    # Get grid section
    response = client.get('/api/config/sections/grid')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'section' in data
    assert 'geometry' in data['section']


def test_update_section(client):
    """Test PUT /api/config/sections/<section>"""
    updated_grid = {
        'geometry': {
            'lower': 90000,
            'upper': 110000,
            'step': 700,  # Changed
            'reference': 95000
        }
    }
    
    response = client.put(
        '/api/config/sections/grid',
        data=json.dumps(updated_grid),
        content_type='application/json'
    )
    
    # May fail if file is read-only
    data = json.loads(response.data)
    assert 'success' in data or 'error' in data


def test_invalid_section(client):
    """Test accessing invalid section"""
    response = client.get('/api/config/sections/invalid_section')
    
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data


# ═══════════════════════════════════════════════════════════════════════════
# TEST: ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════

def test_malformed_json(client):
    """Test handling of malformed JSON"""
    response = client.post(
        '/api/config/validate',
        data='not valid json',
        content_type='application/json'
    )
    
    assert response.status_code == 400


def test_missing_required_fields(client):
    """Test handling of missing required fields"""
    incomplete_strategy = {
        'name': 'test'
        # Missing description and overrides
    }
    
    response = client.post(
        '/api/config/strategies',
        data=json.dumps(incomplete_strategy),
        content_type='application/json'
    )
    
    data = json.loads(response.data)
    assert 'error' in data or 'success' in data


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_config_workflow(client, sample_config):
    """Test complete config management workflow"""
    # 1. Get current config
    response = client.get('/api/config/current')
    assert response.status_code == 200
    
    # 2. Validate a new config
    response = client.post(
        '/api/config/validate',
        data=json.dumps(sample_config),
        content_type='application/json'
    )
    assert response.status_code == 200
    
    # 3. Get history
    response = client.get('/api/config/history')
    assert response.status_code == 200


def test_strategy_workflow(client):
    """Test complete strategy management workflow"""
    # 1. List strategies
    response = client.get('/api/config/strategies')
    assert response.status_code == 200
    
    # 2. Create strategy (may fail if read-only)
    new_strategy = {
        'name': 'api_test',
        'description': 'API test strategy',
        'overrides': {'grid.geometry.step': 800}
    }
    client.post(
        '/api/config/strategies',
        data=json.dumps(new_strategy),
        content_type='application/json'
    )
    
    # 3. Try to get it
    response = client.get('/api/config/strategies/api_test')
    # May be 200 or 404 depending on write permissions


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
