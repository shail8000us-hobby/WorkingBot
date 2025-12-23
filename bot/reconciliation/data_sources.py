#!/usr/bin/env python3
"""
Bulletproof Data Sources Manager
Manages all data sources for reconciliation (Bot memory, Exchange, State).
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
import threading

log = logging.getLogger("data_sources")


class DataSourcesManager:
    """
    Manages all data sources for reconciliation with error handling and caching.
    
    Data Sources:
    - Bot Orders: bot/audit/orders.jsonl
    - Bot State: runtime_state.json (workspace root)
    - Bot Positions: bot/state/positions.json
    - Exchange Orders: Delta Exchange API
    - Exchange Positions: Delta Exchange API
    """
    
    def __init__(self, base_dir: Path, delta_client_factory=None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.delta_client_factory = delta_client_factory
        
        # File paths - base_dir is the project root
        self.orders_file = self.base_dir / "bot" / "audit" / "orders.jsonl"
        self.state_file = self.base_dir / "runtime_state.json"  # ✅ FIXED: Use runtime_state.json
        self.positions_file = self.base_dir / "bot" / "state" / "positions.json"
        
        log.info(f"📂 Orders file path: {self.orders_file}")
        log.info(f"📂 State file path: {self.state_file}")
        log.info(f"📂 Positions file path: {self.positions_file}")
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Cache for performance
        self._cache = {
            'bot_orders': None,
            'bot_state': None,
            'bot_positions': None,
            'exchange_orders': None,
            'exchange_positions': None,
            'last_update': None
        }
        
        log.info(f"🔒 Data Sources Manager initialized: {self.base_dir}")
    
    def get_bot_orders(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get bot orders from audit trail"""
        try:
            with self._lock:
                if not force_refresh and self._cache['bot_orders'] is not None:
                    log.info(f"📦 Returning cached bot orders: {len(self._cache['bot_orders'])} orders")
                    return self._cache['bot_orders']
                
                orders = []
                log.info(f"📂 Loading bot orders from: {self.orders_file}")
                log.info(f"📂 File exists: {self.orders_file.exists()}")
                
                if self.orders_file.exists():
                    with open(self.orders_file, 'r') as f:
                        line_count = 0
                        for line in f:
                            line_count += 1
                            line = line.strip()
                            if line and not line.startswith('#'):
                                try:
                                    order = json.loads(line)
                                    orders.append(order)
                                except json.JSONDecodeError as e:
                                    log.warning(f"⚠️  Invalid JSON in orders.jsonl line {line_count}: {e}")
                                    continue
                    log.info(f"📊 Loaded {len(orders)} bot orders from {line_count} lines")
                else:
                    log.warning(f"⚠️  Bot orders file does not exist: {self.orders_file}")
                
                self._cache['bot_orders'] = orders
                return orders
                
        except Exception as e:
            log.error(f"❌ Failed to load bot orders: {e}")
            import traceback
            log.error(traceback.format_exc())
            return []
    
    def get_bot_state(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get bot state from state.json"""
        try:
            with self._lock:
                if not force_refresh and self._cache['bot_state'] is not None:
                    return self._cache['bot_state']
                
                state = {}
                if self.state_file.exists():
                    with open(self.state_file, 'r') as f:
                        state = json.load(f)
                
                self._cache['bot_state'] = state
                log.debug(f"📊 Loaded bot state: {len(state)} keys")
                return state
                
        except Exception as e:
            log.error(f"❌ Failed to load bot state: {e}")
            return {}
    
    def get_bot_positions(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get bot positions from positions.json"""
        try:
            with self._lock:
                if not force_refresh and self._cache['bot_positions'] is not None:
                    return self._cache['bot_positions']
                
                positions = {}
                if self.positions_file.exists():
                    with open(self.positions_file, 'r') as f:
                        positions = json.load(f)
                
                self._cache['bot_positions'] = positions
                log.debug(f"📊 Loaded bot positions: {len(positions)} keys")
                return positions
                
        except Exception as e:
            log.error(f"❌ Failed to load bot positions: {e}")
            return {}
    
    def get_exchange_orders(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get orders from Delta Exchange using WebSocket subscription
        Simple and reliable - WebSocket already has the data
        """
        try:
            with self._lock:
                if not force_refresh and self._cache['exchange_orders'] is not None:
                    log.info(f"📦 Returning cached exchange orders: {len(self._cache['exchange_orders'])} orders")
                    return self._cache['exchange_orders']
                
                log.info("🔄 Fetching fresh exchange orders...")
                
                # Method 1: Try to get from DeltaClient (modern approach)
                try:
                    # Use DeltaClient directly instead of deprecated gbot_ws
                    # The refactored gridbot.py uses modular architecture
                    
                    # If trading bot is running, fetch via DeltaClient
                    if os.path.exists('.bot_instance.lock'):
                        log.info("📡 Fetching exchange orders via DeltaClient...")
                        
                        # Use DeltaClient directly
                        if self.delta_client_factory:
                            delta_client = self.delta_client_factory()
                            if delta_client:
                                response = delta_client.fetch_open_orders()
                                
                                # Handle response
                                if isinstance(response, list):
                                    orders = response
                                    log.info(f"✅ Fetched {len(orders)} orders from exchange via WebSocket")
                                    self._cache['exchange_orders'] = orders
                                    return orders
                except Exception as ws_error:
                    log.debug(f"WebSocket method failed: {ws_error}")
                
                # Method 2: Direct REST API with product_id filter
                if self.delta_client_factory:
                    try:
                        log.info("📡 Creating delta client...")
                        delta_client = self.delta_client_factory()
                        if delta_client is None:
                            log.warning("⚠️  Delta client factory returned None (likely missing API keys)")
                            return []
                        if delta_client:
                            log.info(f"✅ Delta client created: {delta_client.base}")
                            log.info("📡 Fetching exchange orders via REST API (Delta India)...")
                            
                            # Fetch with product_id=27 for BTCUSD (per Delta AI recommendation)
                            product_id = os.environ.get('DELTA_PRODUCT_ID', '27')
                            log.info(f"   Product ID: {product_id}")
                            
                            response = delta_client.fetch_open_orders(product_id=int(product_id))
                            log.info(f"   Response type: {type(response)}, length: {len(response) if isinstance(response, (list,dict)) else 'N/A'}")
                            
                            # Delta Exchange India returns list directly (CCXT format)
                            # OR dict with {'success': True, 'result': [...]}
                            if isinstance(response, list):
                                # CCXT format - direct list
                                orders = response
                                log.info(f"✅ Fetched {len(orders)} orders (CCXT format)")
                            elif isinstance(response, dict):
                                # Delta native format
                                if response.get('success'):
                                    orders = response.get('result', [])
                                    log.info(f"✅ Fetched {len(orders)} orders (Delta native format)")
                                else:
                                    log.error(f"❌ API returned success=false: {response}")
                                    return []
                            else:
                                log.error(f"❌ Unexpected response type: {type(response)}")
                                return []
                            
                            self._cache['exchange_orders'] = orders
                            log.info(f"✅ FINAL: {len(orders)} exchange orders cached for reconciliation")
                            
                            # Log first few orders for verification
                            if orders:
                                for i, o in enumerate(orders[:3]):
                                    oid = o.get('id', o.get('info', {}).get('id', 'unknown'))
                                    log.info(f"   Order {i+1}: #{oid}")
                            
                            return orders
                        else:
                            log.error("❌ Delta client factory returned None")
                    except Exception as api_error:
                        log.error(f"❌ REST API fetch failed: {api_error}")
                        import traceback
                        log.error(traceback.format_exc())
                
                log.warning("⚠️  All methods failed - returning empty")
                return []
                
        except Exception as e:
            log.error(f"❌ Failed to load exchange orders: {e}")
            import traceback
            log.error(traceback.format_exc())
            return []
    
    def get_exchange_positions(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get positions from Delta Exchange API"""
        try:
            with self._lock:
                if not force_refresh and self._cache['exchange_positions'] is not None:
                    return self._cache['exchange_positions']
                
                if not self.delta_client_factory:
                    log.warning("⚠️  Delta client factory not available")
                    return []
                
                delta_client = self.delta_client_factory()
                if not delta_client:
                    log.warning("⚠️  Delta client not available")
                    return []
                
                # Fetch positions
                response = delta_client.get_positions()
                if not response.get('success'):
                    log.error(f"❌ Failed to fetch exchange positions: {response}")
                    return []
                
                positions = response.get('result', [])
                self._cache['exchange_positions'] = positions
                log.debug(f"📊 Loaded {len(positions)} exchange positions")
                return positions
                
        except Exception as e:
            log.error(f"❌ Failed to load exchange positions: {e}")
            return []
    
    def get_all_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get all data sources in one call"""
        try:
            with self._lock:
                data = {
                    'bot_orders': self.get_bot_orders(force_refresh),
                    'bot_state': self.get_bot_state(force_refresh),
                    'bot_positions': self.get_bot_positions(force_refresh),
                    'exchange_orders': self.get_exchange_orders(force_refresh),
                    'exchange_positions': self.get_exchange_positions(force_refresh),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                self._cache['last_update'] = data['timestamp']
                log.info(f"📊 Loaded all data sources: {len(data['bot_orders'])} bot orders, {len(data['exchange_orders'])} exchange orders")
                return data
                
        except Exception as e:
            log.error(f"❌ Failed to load all data: {e}")
            return {
                'bot_orders': [],
                'bot_state': {},
                'bot_positions': {},
                'exchange_orders': [],
                'exchange_positions': [],
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e)
            }
    
    def clear_cache(self):
        """Clear all cached data"""
        with self._lock:
            self._cache = {
                'bot_orders': None,
                'bot_state': None,
                'bot_positions': None,
                'exchange_orders': None,
                'exchange_positions': None,
                'last_update': None
            }
            log.info("🧹 Cache cleared")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status information"""
        with self._lock:
            return {
                'bot_orders_cached': self._cache['bot_orders'] is not None,
                'bot_state_cached': self._cache['bot_state'] is not None,
                'bot_positions_cached': self._cache['bot_positions'] is not None,
                'exchange_orders_cached': self._cache['exchange_orders'] is not None,
                'exchange_positions_cached': self._cache['exchange_positions'] is not None,
                'last_update': self._cache['last_update']
            }
    
    def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate data integrity across all sources"""
        try:
            with self._lock:
                validation = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'bot_orders_valid': False,
                    'bot_state_valid': False,
                    'bot_positions_valid': False,
                    'exchange_orders_valid': False,
                    'exchange_positions_valid': False,
                    'errors': []
                }
                
                # Validate bot orders
                try:
                    bot_orders = self.get_bot_orders(force_refresh=True)
                    validation['bot_orders_valid'] = True
                    validation['bot_orders_count'] = len(bot_orders)
                except Exception as e:
                    validation['errors'].append(f"Bot orders validation failed: {e}")
                
                # Validate bot state
                try:
                    bot_state = self.get_bot_state(force_refresh=True)
                    validation['bot_state_valid'] = True
                    validation['bot_state_keys'] = len(bot_state)
                except Exception as e:
                    validation['errors'].append(f"Bot state validation failed: {e}")
                
                # Validate bot positions
                try:
                    bot_positions = self.get_bot_positions(force_refresh=True)
                    validation['bot_positions_valid'] = True
                    validation['bot_positions_keys'] = len(bot_positions)
                except Exception as e:
                    validation['errors'].append(f"Bot positions validation failed: {e}")
                
                # Validate exchange orders
                try:
                    exchange_orders = self.get_exchange_orders(force_refresh=True)
                    validation['exchange_orders_valid'] = True
                    validation['exchange_orders_count'] = len(exchange_orders)
                except Exception as e:
                    validation['errors'].append(f"Exchange orders validation failed: {e}")
                
                # Validate exchange positions
                try:
                    exchange_positions = self.get_exchange_positions(force_refresh=True)
                    validation['exchange_positions_valid'] = True
                    validation['exchange_positions_count'] = len(exchange_positions)
                except Exception as e:
                    validation['errors'].append(f"Exchange positions validation failed: {e}")
                
                validation['overall_valid'] = len(validation['errors']) == 0
                return validation
                
        except Exception as e:
            log.error(f"❌ Data integrity validation failed: {e}")
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'overall_valid': False,
                'errors': [f"Validation error: {e}"]
            }


# Global instance
_data_sources = None


def get_data_sources_manager(base_dir: Path = None, delta_client_factory=None) -> DataSourcesManager:
    """Get global data sources manager instance"""
    global _data_sources
    if _data_sources is None:
        if base_dir is None:
            base_dir = Path(__file__).parent.parent.parent
        _data_sources = DataSourcesManager(base_dir, delta_client_factory)
    return _data_sources


if __name__ == "__main__":
    # Test the data sources manager
    manager = get_data_sources_manager()
    
    print("🧪 Testing Data Sources Manager:")
    
    # Test bot orders
    bot_orders = manager.get_bot_orders()
    print(f"✅ Bot orders: {len(bot_orders)}")
    
    # Test bot state
    bot_state = manager.get_bot_state()
    print(f"✅ Bot state: {len(bot_state)} keys")
    
    # Test bot positions
    bot_positions = manager.get_bot_positions()
    print(f"✅ Bot positions: {len(bot_positions)} keys")
    
    # Test cache status
    cache_status = manager.get_cache_status()
    print(f"✅ Cache status: {cache_status}")
    
    print("\n✅ Data sources manager test completed")
