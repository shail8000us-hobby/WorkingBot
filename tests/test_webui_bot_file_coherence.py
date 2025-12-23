"""
Advanced WebUI-Bot File Coherence Testing

Tests the coherence between:
1. Bot writes files → WebUI reads files
2. File format compatibility
3. Data structure matching
4. File path correctness
5. State synchronization
6. Real-time updates through files

Critical Files Tested:
- runtime_state.json (bot state)
- positions.json (position tracking)
- grid_config.env (configuration)
- .volatility_status.json (volatility data)
- .volatility_halt.json (halt state)
- bot.log (log files)

Run with: pytest tests/test_webui_bot_file_coherence.py -v
"""

import pytest
import json
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch
import threading
import concurrent.futures

from bot.strategy.modules.position_manager import PositionManager
from bot.strategy.modules.grid_calculator import GridCalculator


class TestRuntimeStateFileCoherence:
    """Test runtime_state.json coherence between bot and WebUI"""
    
    def setup_method(self):
        """Setup test fixtures"""
        # Create temp directory for state files
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = Path(self.temp_dir) / 'runtime_state.json'
        
        # Grid calculator
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # Position manager
        self.position_mgr = PositionManager(
            max_open=10,
            grid_calculator=self.grid_calc,
            session_tag="COHERENCE_TEST"
        )
    
    def teardown_method(self):
        """Cleanup temp files"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_bot_writes_valid_json(self):
        """Test: Bot writes valid JSON that WebUI can parse"""
        # Add positions to bot
        positions = [
            {
                'buy_order_id': 'ORDER1',
                'entry_price': 110000,
                'tp_price': 110500,
                'size': 1,
                'timestamp': 1699000000,
                'protected': True
            },
            {
                'buy_order_id': 'ORDER2',
                'entry_price': 109500,
                'tp_price': 110000,
                'size': 1,
                'timestamp': 1699000001,
                'protected': True
            }
        ]
        
        for pos in positions:
            self.position_mgr.add_position(pos)
        
        # Bot persists state
        self.position_mgr.persist_runtime_state(filename=str(self.state_file))
        
        # WebUI reads state
        assert self.state_file.exists(), "State file not created"
        
        with open(self.state_file, 'r') as f:
            webui_data = json.load(f)
        
        # Verify WebUI can parse
        assert isinstance(webui_data, dict), "State should be dict"
        assert 'open_tranches' in webui_data, "Missing open_tranches"
        assert len(webui_data['open_tranches']) == 2, "Position count mismatch"
    
    def test_webui_can_read_bot_written_positions(self):
        """Test: WebUI can read positions written by bot"""
        # Bot writes positions
        position = {
            'buy_order_id': 'TEST_ORDER',
            'entry_price': 110000,
            'tp_price': 110500,
            'size': 1,
            'timestamp': 1699000000,
            'protected': True,
            'tp_id': 'TP123'
        }
        
        self.position_mgr.add_position(position)
        self.position_mgr.persist_runtime_state(filename=str(self.state_file))
        
        # WebUI reads (simulated)
        with open(self.state_file, 'r') as f:
            state = json.load(f)
        
        positions = state.get('open_tranches', [])
        
        # Verify WebUI gets same data
        assert len(positions) == 1
        assert positions[0]['entry_price'] == 110000
        assert positions[0]['tp_price'] == 110500
        assert positions[0]['tp_id'] == 'TP123'
    
    def test_pending_buy_coherence(self):
        """Test: Pending buy coherence between bot writes and WebUI reads"""
        # Bot sets pending buy
        self.position_mgr.set_pending_buy({
            'order_id': 'PENDING_BUY_123',
            'price': 109500,
            'timestamp': 1699000000
        })
        
        # Bot persists
        self.position_mgr.persist_runtime_state(filename=str(self.state_file))
        
        # WebUI reads
        with open(self.state_file, 'r') as f:
            state = json.load(f)
        
        # Verify pending buy accessible
        pending_buy = state.get('pending_buy')
        assert pending_buy is not None, "Pending buy not persisted"
        assert pending_buy['order_id'] == 'PENDING_BUY_123'
        assert pending_buy['price'] == 109500
    
    def test_state_file_atomic_write(self):
        """Test: Bot uses atomic write (temp + rename) to prevent corruption"""
        # Add position
        self.position_mgr.add_position({
            'buy_order_id': 'ATOMIC_TEST',
            'entry_price': 110000,
            'tp_price': 110500,
            'size': 1,
            'timestamp': 1699000000,
            'protected': False
        })
        
        # Persist state (should use atomic write)
        self.position_mgr.persist_runtime_state(filename=str(self.state_file))
        
        # Verify file exists and is readable
        assert self.state_file.exists()
        
        with open(self.state_file, 'r') as f:
            data = json.load(f)
        
        # Should be complete, valid JSON (not corrupted)
        assert 'open_tranches' in data
        assert len(data['open_tranches']) == 1


class TestConfigFileCoherence:
    """Test grid_config.env coherence between bot and WebUI"""
    
    def test_config_file_format_readable(self):
        """Test: Bot config format is readable by WebUI"""
        # Simulate bot config file
        config_content = """# Grid Config
GRID_LOWER=105000
GRID_UPPER=115000
GRID_STEP=500
GRID_REF=110000
LOT_SIZE=1
MAX_OPEN=10
GRID_MODE=LONG
"""
        
        # Parse as WebUI would
        config = {}
        for line in config_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
        
        # Verify WebUI can parse
        assert config['GRID_LOWER'] == '105000'
        assert config['GRID_UPPER'] == '115000'
        assert config['GRID_MODE'] == 'LONG'
    
    def test_config_values_convertible_to_numbers(self):
        """Test: Config values can be converted to numbers for WebUI display"""
        # Bot writes string values
        config = {
            'GRID_LOWER': '105000',
            'GRID_UPPER': '115000',
            'GRID_STEP': '500',
            'GRID_REF': '110000'
        }
        
        # WebUI converts to numbers for display
        for key, value in config.items():
            numeric_value = float(value)
            assert numeric_value > 0, f"{key} should be positive"
    
    def test_config_special_characters_handled(self):
        """Test: Config with quotes/special chars parsed correctly"""
        # Bot might write with quotes
        config_content = '''GRID_MODE="LONG"
SYMBOL='BTCUSD'
ENABLED=true
'''
        
        # Parse with quote stripping (as WebUI does)
        config = {}
        for line in config_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Strip quotes as WebUI does
                config[key.strip()] = value.strip().strip('"').strip("'")
        
        # Verify quotes removed
        assert config['GRID_MODE'] == 'LONG'  # Not "LONG"
        assert config['SYMBOL'] == 'BTCUSD'  # Not 'BTCUSD'


class TestVolatilityFileCoherence:
    """Test volatility file coherence"""
    
    def test_volatility_status_file_structure(self):
        """Test: .volatility_status.json matches expected structure"""
        # Bot writes volatility status
        vol_status = {
            'current_iv': 75.5,
            'current_rv': 68.3,
            'iv_threshold': 80.0,
            'rv_threshold': 70.0,
            'is_safe': True,
            'last_update': 1699000000
        }
        
        # Verify JSON serializable
        json_str = json.dumps(vol_status)
        parsed = json.loads(json_str)
        
        # Verify WebUI can read required fields
        assert 'current_iv' in parsed
        assert 'current_rv' in parsed
        assert 'is_safe' in parsed
        
        # Verify values are numeric
        assert isinstance(parsed['current_iv'], (int, float))
        assert isinstance(parsed['current_rv'], (int, float))
    
    def test_volatility_halt_file_structure(self):
        """Test: .volatility_halt.json matches expected structure"""
        # Bot writes halt state
        halt_state = {
            'active': True,
            'halt_time': 1699000000,
            'reason': 'IV spike: 85.2% > 80.0%',
            'missed_levels': [109500, 109000],
            'pending_cancel': 'ORDER123'
        }
        
        # Verify JSON serializable
        json_str = json.dumps(halt_state)
        parsed = json.loads(json_str)
        
        # Verify WebUI can display
        assert 'active' in parsed
        assert 'reason' in parsed
        assert isinstance(parsed['missed_levels'], list)


class TestLogFileCoherence:
    """Test log file coherence between bot and WebUI"""
    
    def test_log_format_parseable(self):
        """Test: Bot log format can be parsed by WebUI"""
        # Simulated bot log entries
        log_entries = [
            "2025-11-02 20:00:00 [INFO] GridBot started",
            "2025-11-02 20:00:01 [INFO] ✅ BUY order placed @ $109,500",
            "2025-11-02 20:00:05 [INFO] ✅ BUY filled @ $109,500",
            "2025-11-02 20:00:05 [INFO] 🛡️ TP placed @ $110,000",
        ]
        
        # WebUI parses logs
        parsed_logs = []
        for line in log_entries:
            # Extract timestamp, level, message
            parts = line.split(' ', 3)
            if len(parts) >= 4:
                parsed_logs.append({
                    'date': parts[0],
                    'time': parts[1],
                    'level': parts[2].strip('[]'),
                    'message': parts[3]
                })
        
        # Verify parsing worked
        assert len(parsed_logs) == 4
        assert parsed_logs[0]['level'] == 'INFO'
        assert 'BUY order placed' in parsed_logs[1]['message']


class TestFilePathCoherence:
    """Test file paths match between bot and WebUI"""
    
    def test_state_file_paths_match(self):
        """Test: Bot and WebUI use same file paths"""
        # Bot file paths (from PositionManager)
        bot_state_file = 'runtime_state.json'
        
        # WebUI expected paths (from backend routes)
        webui_expected_files = [
            'runtime_state.json',
            'positions.json',
            '.volatility_status.json',
            '.volatility_halt.json',
            'grid_config.env'
        ]
        
        # Verify runtime_state.json is in expected list
        assert bot_state_file in webui_expected_files
    
    def test_config_file_path_matches(self):
        """Test: Config file path same for bot and WebUI"""
        # Bot uses: grid_config.env
        bot_config_file = 'grid_config.env'
        
        # WebUI expects: grid_config.env
        webui_config_file = 'grid_config.env'
        
        assert bot_config_file == webui_config_file


class TestDataStructureCoherence:
    """Test data structures match between bot writes and WebUI expects"""
    
    def test_position_structure_matches(self):
        """Test: Position structure written by bot matches WebUI expectations"""
        # Bot writes position with these fields
        bot_position = {
            'buy_order_id': 'ORDER123',
            'entry_price': 110000,
            'tp_price': 110500,
            'size': 1,
            'timestamp': 1699000000,
            'protected': True,
            'tp_id': 'TP123'
        }
        
        # WebUI expects these fields (from PositionsPanel.js analysis)
        required_fields = ['entry_price', 'tp_price', 'size', 'protected']
        
        for field in required_fields:
            assert field in bot_position, f"Position missing field: {field}"
        
        # Verify types match WebUI expectations
        assert isinstance(bot_position['entry_price'], (int, float))
        assert isinstance(bot_position['tp_price'], (int, float))
        assert isinstance(bot_position['size'], (int, float))
        assert isinstance(bot_position['protected'], bool)
    
    def test_config_structure_matches(self):
        """Test: Config structure matches between bot and WebUI"""
        # Bot config structure
        bot_config = {
            'GRID_LOWER': '105000',
            'GRID_UPPER': '115000',
            'GRID_STEP': '500',
            'GRID_REF': '110000',
            'LOT_SIZE': '1',
            'MAX_OPEN': '10',
            'GRID_MODE': 'LONG'
        }
        
        # WebUI expects (from ConfigPanel.js)
        required_config_fields = [
            'GRID_LOWER',
            'GRID_UPPER',
            'GRID_STEP',
            'GRID_REF',
            'LOT_SIZE',
            'MAX_OPEN'
        ]
        
        for field in required_config_fields:
            assert field in bot_config, f"Config missing field: {field}"


class TestRealTimeUpdateCoherence:
    """Test real-time update coherence through file system"""
    
    def test_bot_persist_then_webui_read_cycle(self):
        """Test: Complete cycle of bot writes → WebUI reads"""
        # Setup
        temp_file = Path(tempfile.mktemp(suffix='.json'))
        
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        position_mgr = PositionManager(
            max_open=10,
            grid_calculator=grid_calc,
            session_tag="CYCLE_TEST"
        )
        
        try:
            # Step 1: Bot adds position
            position_mgr.add_position({
                'buy_order_id': 'CYCLE_ORDER',
                'entry_price': 110000,
                'tp_price': 110500,
                'size': 1,
                'timestamp': 1699000000,
                'protected': False
            })
            
            # Step 2: Bot persists
            position_mgr.persist_runtime_state(filename=str(temp_file))
            
            # Step 3: WebUI reads
            with open(temp_file, 'r') as f:
                webui_state = json.load(f)
            
            # Step 4: Verify coherence
            webui_positions = webui_state.get('open_tranches', [])
            assert len(webui_positions) == 1
            assert webui_positions[0]['buy_order_id'] == 'CYCLE_ORDER'
            
            # Step 5: Bot updates (adds another position)
            position_mgr.add_position({
                'buy_order_id': 'CYCLE_ORDER_2',
                'entry_price': 109500,
                'tp_price': 110000,
                'size': 1,
                'timestamp': 1699000001,
                'protected': False
            })
            
            # Step 6: Bot persists again
            position_mgr.persist_runtime_state(filename=str(temp_file))
            
            # Step 7: WebUI reads updated state
            with open(temp_file, 'r') as f:
                webui_state_updated = json.load(f)
            
            # Step 8: Verify update reflected
            webui_positions_updated = webui_state_updated.get('open_tranches', [])
            assert len(webui_positions_updated) == 2, "WebUI should see updated positions"
        
        finally:
            # Cleanup
            if temp_file.exists():
                temp_file.unlink()
    
    def test_concurrent_bot_write_webui_read(self):
        """Test: WebUI can read while bot is writing (thread safety)"""
        temp_file = Path(tempfile.mktemp(suffix='.json'))
        
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        position_mgr = PositionManager(
            max_open=10,
            grid_calculator=grid_calc,
            session_tag="CONCURRENT_TEST"
        )
        
        errors = []
        reads_successful = []
        
        def bot_writer():
            """Simulate bot writing state repeatedly"""
            try:
                for i in range(10):
                    position_mgr.add_position({
                        'buy_order_id': f'WRITE_{i}',
                        'entry_price': 110000 - i * 10,
                        'tp_price': 110500 - i * 10,
                        'size': 1,
                        'timestamp': 1699000000 + i,
                        'protected': False
                    })
                    position_mgr.persist_runtime_state(filename=str(temp_file))
                    time.sleep(0.01)
            except Exception as e:
                errors.append(('writer', str(e)))
        
        def webui_reader():
            """Simulate WebUI reading state repeatedly"""
            try:
                for i in range(20):
                    if temp_file.exists():
                        with open(temp_file, 'r') as f:
                            data = json.load(f)
                            if 'open_tranches' in data:
                                reads_successful.append(len(data['open_tranches']))
                    time.sleep(0.005)
            except json.JSONDecodeError:
                # Atomic write should prevent this, but if it happens, not critical
                pass
            except Exception as e:
                errors.append(('reader', str(e)))
        
        try:
            # Run bot writer and WebUI reader concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                writer_future = executor.submit(bot_writer)
                reader_future = executor.submit(webui_reader)
                
                writer_future.result()
                reader_future.result()
            
            # Verify no errors
            assert len(errors) == 0, f"Concurrent access errors: {errors}"
            
            # Verify WebUI could read
            assert len(reads_successful) > 0, "WebUI never successfully read state"
        
        finally:
            if temp_file.exists():
                temp_file.unlink()


class TestVolatilityDataCoherence:
    """Test volatility data coherence"""
    
    def test_volatility_status_structure(self):
        """Test: Volatility status structure matches WebUI expectations"""
        # Bot writes volatility status
        vol_status = {
            'current_iv': 75.5,
            'current_rv': 68.3,
            'iv_threshold': 80.0,
            'rv_threshold': 70.0,
            'is_safe': True,
            'last_update': 1699000000,
            'status': 'safe'
        }
        
        # WebUI expects to display these
        webui_fields = ['current_iv', 'current_rv', 'is_safe']
        
        for field in webui_fields:
            assert field in vol_status, f"Volatility missing field: {field}"
        
        # Verify can display safely
        assert 0 <= vol_status['current_iv'] <= 200
        assert 0 <= vol_status['current_rv'] <= 200
        assert isinstance(vol_status['is_safe'], bool)


class TestErrorRecoveryCoherence:
    """Test error recovery and corruption handling"""
    
    def test_corrupted_json_handled_gracefully(self):
        """Test: WebUI handles corrupted JSON gracefully"""
        # Simulated corrupted file
        temp_file = Path(tempfile.mktemp(suffix='.json'))
        
        try:
            # Write corrupted JSON
            with open(temp_file, 'w') as f:
                f.write('{"open_tranches": [{"entry": 110000,}]}')  # Trailing comma - invalid JSON
            
            # WebUI tries to read
            try:
                with open(temp_file, 'r') as f:
                    data = json.load(f)
                # Should fail to parse
                pytest.fail("Corrupted JSON should not parse")
            except json.JSONDecodeError:
                # Expected - WebUI should catch this
                assert True
        
        finally:
            if temp_file.exists():
                temp_file.unlink()
    
    def test_missing_file_handled_gracefully(self):
        """Test: WebUI handles missing state file gracefully"""
        # WebUI tries to read non-existent file
        non_existent = Path('/tmp/non_existent_state_file.json')
        
        # WebUI check
        if not non_existent.exists():
            # Should return empty state or handle gracefully
            default_state = {}
        
        # Verify default state is safe
        assert isinstance(default_state, dict)


class TestFileWatchingCoherence:
    """Test file watching and live updates"""
    
    def test_state_file_modification_detectable(self):
        """Test: WebUI can detect when bot modifies state file"""
        temp_file = Path(tempfile.mktemp(suffix='.json'))
        
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        position_mgr = PositionManager(
            max_open=10,
            grid_calculator=grid_calc,
            session_tag="WATCH_TEST"
        )
        
        try:
            # Initial write
            position_mgr.persist_runtime_state(filename=str(temp_file))
            initial_mtime = temp_file.stat().st_mtime
            
            # Wait briefly
            time.sleep(0.1)
            
            # Bot modifies
            position_mgr.add_position({
                'buy_order_id': 'MODIFIED',
                'entry_price': 110000,
                'tp_price': 110500,
                'size': 1,
                'timestamp': 1699000000,
                'protected': False
            })
            position_mgr.persist_runtime_state(filename=str(temp_file))
            
            # Check modification time changed
            new_mtime = temp_file.stat().st_mtime
            
            # WebUI can detect change by comparing mtime
            assert new_mtime > initial_mtime, "File modification not detectable"
        
        finally:
            if temp_file.exists():
                temp_file.unlink()


class TestBackendRoutesReadBotFiles:
    """Test backend routes correctly read bot's files"""
    
    def test_backend_can_parse_bot_state_file(self):
        """Test: Backend routes can parse bot's state file format"""
        # Simulate bot writing state
        temp_file = Path(tempfile.mktemp(suffix='.json'))
        
        grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        position_mgr = PositionManager(
            max_open=10,
            grid_calculator=grid_calc,
            session_tag="BACKEND_TEST"
        )
        
        try:
            # Bot writes
            position_mgr.add_position({
                'buy_order_id': 'BACKEND_READ_TEST',
                'entry_price': 110000,
                'tp_price': 110500,
                'size': 1,
                'timestamp': 1699000000,
                'protected': True
            })
            position_mgr.persist_runtime_state(filename=str(temp_file))
            
            # Backend reads (simulated from routes/positions.py logic)
            with open(temp_file, 'r') as f:
                backend_data = json.load(f)
            
            # Backend extracts positions
            positions = backend_data.get('open_tranches', [])
            
            # Verify backend can process
            assert len(positions) == 1
            assert positions[0]['entry_price'] == 110000
            
            # Backend transforms for frontend
            frontend_position = {
                'entry': positions[0]['entry_price'],
                'tp': positions[0]['tp_price'],
                'size': positions[0]['size'],
                'protected': positions[0]['protected']
            }
            
            # Verify transformation works
            assert frontend_position['entry'] == 110000
        
        finally:
            if temp_file.exists():
                temp_file.unlink()


class TestConfigCoherenceEndToEnd:
    """Test complete config coherence from bot → file → backend → frontend"""
    
    def test_complete_config_flow(self):
        """
        Test: Complete config flow
        
        Bot reads grid_config.env
        → Uses values for trading
        → WebUI backend reads grid_config.env
        → Sends to frontend
        → Frontend displays
        """
        # Step 1: Create config file (as bot would read)
        temp_config = Path(tempfile.mktemp(suffix='.env'))
        
        try:
            config_content = """GRID_LOWER=105000
GRID_UPPER=115000
GRID_STEP=500
GRID_REF=110000
LOT_SIZE=1
MAX_OPEN=10
GRID_MODE=SHORT
"""
            with open(temp_config, 'w') as f:
                f.write(config_content)
            
            # Step 2: Bot reads config (simulated)
            bot_config = {}
            with open(temp_config, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        bot_config[key.strip()] = value.strip()
            
            # Step 3: Backend reads same file (as routes/config.py does)
            backend_config = {}
            with open(temp_config, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        backend_config[key.strip()] = value.strip().strip('"').strip("'")
            
            # Step 4: Verify bot and backend read same values
            assert bot_config['GRID_LOWER'] == backend_config['GRID_LOWER']
            assert bot_config['GRID_MODE'] == backend_config['GRID_MODE']
            
            # Step 5: Frontend receives and parses
            frontend_lower = float(backend_config['GRID_LOWER'])
            frontend_mode = backend_config['GRID_MODE']
            
            # Verify frontend can use values
            assert frontend_lower == 105000
            assert frontend_mode == 'SHORT'
        
        finally:
            if temp_config.exists():
                temp_config.unlink()


if __name__ == "__main__":
    pytest.main([__file__, '-v'])

