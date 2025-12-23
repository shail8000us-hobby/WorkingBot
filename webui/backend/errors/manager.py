"""
Error Intelligence Manager - Central coordinator for the error system
Connects collectors, classifier, store, and API together.
"""

import os
import threading
from typing import Optional, Dict, Any
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from bot.observability.errors import (
    ErrorSource, ErrorCollector, ErrorClassifier, ErrorRemediator
)
from bot.observability.errors.store import ErrorStore
from bot.observability.errors.catalog import ErrorCatalog
from .routes import init_error_api, emit_new_error

# Load YAML config
from config.loader import get_config


class ErrorIntelligenceManager:
    """Central manager for the error intelligence system"""
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        socketio=None
    ):
        """
        Initialize the error intelligence manager.
        
        Args:
            config: Configuration dict with paths and settings
            socketio: Flask-SocketIO instance for real-time updates
        """
        self.config = config or self._load_config_from_env()
        self.socketio = socketio
        
        # Initialize components
        self.catalog = ErrorCatalog()
        self.store = ErrorStore(self.config.get('db_path', 'data/errors.db'))
        self.classifier = ErrorClassifier(self.catalog)
        self.remediator = ErrorRemediator(
            config_path=self.config.get('config_path', 'config.yaml'),
            allow_destructive=self.config.get('allow_destructive', False)
        )
        
        self.collector: Optional[ErrorCollector] = None
        self.running = False
        
        # Initialize API
        init_error_api(self.store, self.classifier, self.remediator, socketio)
        
        print("✅ Error Intelligence Manager initialized")
    
    def _load_config_from_env(self) -> Dict[str, Any]:
        """Load configuration from YAML"""
        cfg = get_config()
        
        return {
            'enabled': cfg.webui.errors.collector_enabled,
            'db_path': cfg.webui.errors.db_path,
            'config_path': 'config.yaml',  # Always use YAML now
            'allow_destructive': cfg.webui.errors.allow_destructive,
            'log_paths': {
                'trading': cfg.webui.logs.trading_bot,
                'guardian': cfg.webui.logs.guardian_bot,
                'health': cfg.webui.logs.health_bot
            },
            'rate_limit_window': cfg.webui.errors.rate_limit_window,
            'rate_limit_max': cfg.webui.errors.rate_limit_max,
            'burst_threshold': cfg.webui.errors.burst_threshold
        }
    
    def start(self):
        """Start the error intelligence system"""
        if not self.config.get('enabled', True):
            print("⚠️  Error intelligence system disabled by config")
            return
        
        if self.running:
            print("⚠️  Error intelligence system already running")
            return
        
        print("🚀 Starting Error Intelligence System...")
        
        # Create log configuration for collector
        log_configs = {}
        for source, path in self.config['log_paths'].items():
            if os.path.exists(path) or source == 'trading':  # Always monitor trading
                log_configs[source] = {
                    'type': 'file',
                    'path': path
                }
        
        # Create and start collector
        self.collector = ErrorCollector(
            on_error_detected=self._handle_error_detected,
            rate_limit_window=self.config.get('rate_limit_window', 60),
            rate_limit_max=self.config.get('rate_limit_max', 100),
            burst_threshold=self.config.get('burst_threshold', 10)
        )
        
        self.collector.start(log_configs)
        self.running = True
        
        print("✅ Error Intelligence System started")
        print(f"   Monitoring: {', '.join(log_configs.keys())}")
        print(f"   Allow destructive fixes: {self.config.get('allow_destructive', False)}")
    
    def stop(self):
        """Stop the error intelligence system"""
        if not self.running:
            return
        
        print("🛑 Stopping Error Intelligence System...")
        
        if self.collector:
            self.collector.stop()
        
        self.running = False
        print("✅ Error Intelligence System stopped")
    
    def _handle_error_detected(self, message: str, source: ErrorSource):
        """
        Handle a detected error from the collector.
        This is the main processing pipeline.
        """
        try:
            # Get bot context
            context = self._get_bot_context(source)
            
            # Classify the error
            error = self.classifier.classify(message, source, context)
            
            # Save to store (handles deduplication internally)
            existing = self.store.get_all(limit=1000)
            is_new = True
            
            for existing_error in existing:
                if existing_error.get_signature() == error.get_signature():
                    # Merge occurrence
                    existing_error.merge_occurrence()
                    self.store.save(existing_error)
                    is_new = False
                    break
            
            if is_new:
                # New error - save it
                self.store.save(error)
                
                # Emit to WebSocket clients
                if self.socketio:
                    emit_new_error(error)
                
                # Log for debugging
                print(f"🔴 New error detected: [{error.severity.value.upper()}] {error.title}")
                print(f"   Source: {error.source.value}")
                print(f"   Code: {error.code}")
                if error.can_auto_fix:
                    print(f"   ✅ Can auto-fix")
        
        except Exception as e:
            print(f"❌ Error processing detected error: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_bot_context(self, source: ErrorSource) -> Dict[str, Any]:
        """Get current bot context for error enrichment"""
        cfg = get_config()
        
        context = {
            'source': source.value,
            'trading_mode': cfg.trading_mode
        }
        
        # Add more context based on source
        if source == ErrorSource.TRADING:
            context.update({
                'max_open': cfg.grid.limits.max_open_positions,
                'execute_orders': cfg.safety.execute_orders,
                'post_only': cfg.order_execution.post_only_mode
            })
        
        elif source == ErrorSource.GUARDIAN:
            context.update({
                'guardian_enabled': cfg.guardian.enabled if hasattr(cfg, 'guardian') else False,
                'max_loss': cfg.guardian.max_account_loss_inr if hasattr(cfg, 'guardian') else 0
            })
        
        return context
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of the error intelligence system"""
        status = {
            'enabled': self.config.get('enabled', True),
            'running': self.running,
            'allow_destructive_fixes': self.config.get('allow_destructive', False)
        }
        
        if self.collector:
            status['collector'] = self.collector.get_stats()
        
        if self.store:
            status['statistics'] = self.store.get_statistics()
        
        return status
    
    def inject_test_error(self, message: str, source: str = 'trading'):
        """Inject a test error for testing purposes"""
        try:
            source_enum = ErrorSource(source)
            self._handle_error_detected(message, source_enum)
            return True
        except Exception as e:
            print(f"Failed to inject test error: {e}")
            return False
