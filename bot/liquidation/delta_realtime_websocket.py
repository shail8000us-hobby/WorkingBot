"""
Delta Exchange Real-Time WebSocket Client - Production Ready
=====================================================
Fetches real-time data directly from Delta Exchange WebSocket API:
- UPNL (Unrealized PnL) via portfolio_margins channel
- Balance (Wallet Balance) via margins channel  
- Maintenance Margin via portfolio_margins channel

Based on official Delta Exchange WebSocket documentation:
- Production URL: wss://socket.india.delta.exchange
- Testnet URL: wss://socket-ind.testnet.deltaex.org

Author: GridBot Pro
Last Updated: 2025-01-24
"""

import websocket
import json
import time
import hmac
import hashlib
import os
import sys
import threading
import logging
from datetime import datetime
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, asdict
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

@dataclass
class RealTimeBalance:
    """Real-time balance data from Delta Exchange"""
    asset_symbol: str  # e.g., "USD", "BTC"
    balance: float  # Wallet balance (deposits - withdrawals + realized cashflows)
    available_balance: float  # Balance available for trading
    blocked_margin: float  # Total margin currently blocked
    portfolio_margin: float  # Margin blocked for portfolio positions
    order_margin: float  # Margin blocked for open orders
    position_margin: float  # Margin blocked for open positions
    commission_blocked: float  # Commission blocked
    timestamp: str

@dataclass
class RealTimePortfolioMargin:
    """Real-time portfolio margin data from Delta Exchange"""
    index_symbol: str  # e.g., ".DEXBTUSD"
    positions_upl: float  # ⭐ OFFICIAL UPNL from Delta Exchange
    blocked_margin: float  # Total margin blocked
    mm_with_ucf: float  # Maintenance margin WITH unrealized cashflows
    mm_without_ucf: float  # Maintenance margin WITHOUT unrealized cashflows
    risk_margin: float  # Maximum likely loss under stress scenarios
    liquidation_risk: bool  # Whether account is at liquidation risk
    under_liquidation: bool  # Whether account is under liquidation
    margin_shortfall: float  # Margin shortfall if under liquidation
    timestamp: str

class DeltaRealtimeWebSocket:
    """
    Production-ready WebSocket client for Delta Exchange real-time data
    
    Features:
    - Automatic reconnection on disconnect
    - Thread-safe data access
    - Real-time UPNL from portfolio_margins.positions_upl
    - Real-time balance from margins channel
    - Real-time maintenance margin from portfolio_margins
    - Alert callbacks for liquidation risk
    - Comprehensive error handling
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "wss://socket.india.delta.exchange",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize Delta Exchange WebSocket client
        
        Args:
            api_key: Delta Exchange API key
            api_secret: Delta Exchange API secret
            base_url: WebSocket URL (production or testnet)
            logger: Logger instance (optional)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        
        # Configure dedicated logger to avoid duplication in bot logs
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger('delta_websocket')
            # Only add handlers if not already configured (singleton safety)
            if not self.logger.handlers:
                self.logger.setLevel(logging.INFO)
                self.logger.propagate = False  # Don't propagate to parent loggers (prevents duplication)
        
        # WebSocket connection
        self.ws = None
        self.connected = False
        self.authenticated = False
        self.running = False
        
        # Real-time data storage (thread-safe)
        self._lock = threading.Lock()
        self._balance: Optional[RealTimeBalance] = None
        self._portfolio_margin: Optional[RealTimePortfolioMargin] = None
        
        # Alert callbacks
        self.alert_callbacks: list[Callable] = []
        
        # Connection stats
        self.last_update_time = None
        self.reconnect_count = 0
        self.message_count = 0
        
        # Production features
        self.last_heartbeat = None
        self.heartbeat_timeout = 40  # Delta Exchange sends updates every ~2s, 40s is safe
        self.reconnect_delay = 5  # Start with 5 seconds
        self.max_reconnect_delay = 60  # Max 60 seconds
        self.connection_state = "disconnected"
        
    def add_alert_callback(self, callback: Callable):
        """Add callback for liquidation risk alerts"""
        self.alert_callbacks.append(callback)
    
    def _trigger_alerts(self, message: str, data: Dict):
        """Trigger alert callbacks"""
        for callback in self.alert_callbacks:
            try:
                callback(message, data)
            except Exception as e:
                self.logger.error(f"Alert callback error: {e}")
    
    def _generate_signature(self, method: str, timestamp: str, path: str) -> str:
        """
        Generate HMAC signature for Delta Exchange authentication
        
        Format: HMAC-SHA256(api_secret, method + timestamp + path)
        """
        message = method + timestamp + path
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def on_open(self, ws):
        """Handle WebSocket connection open"""
        self.logger.info("🔌 WebSocket connected to Delta Exchange")
        self.connected = True
        self.connection_state = "connected"
        
        # Authenticate using Delta Exchange protocol
        timestamp = str(int(time.time()))
        method = 'GET'
        path = '/live'
        signature = self._generate_signature(method, timestamp, path)
        
        auth_message = {
            "type": "auth",
            "payload": {
                "api-key": self.api_key,
                "signature": signature,
                "timestamp": timestamp
            }
        }
        
        ws.send(json.dumps(auth_message))
        self.logger.info("📤 Authentication request sent")
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            message_type = data.get('type')
            self.message_count += 1
            self.last_heartbeat = datetime.now()  # Track heartbeat for health monitoring
            
            # ========================================
            # Handle authentication success
            # ========================================
            if message_type == 'success' and data.get('message') == 'Authenticated':
                self.logger.info("✅ Authenticated with Delta Exchange")
                self.authenticated = True
                self.connection_state = "authenticated"
                self.reconnect_delay = 5  # Reset backoff on successful auth
                
                # Subscribe to real-time data channels
                subscribe_msg = {
                    "type": "subscribe",
                    "payload": {
                        "channels": [
                            {
                                "name": "margins"  # Balance data
                            },
                            {
                                "name": "portfolio_margins"  # UPNL + Maintenance Margin
                            }
                        ]
                    }
                }
                ws.send(json.dumps(subscribe_msg))
                self.logger.info("📡 Subscribed to margins + portfolio_margins channels")
                return
            
            # ========================================
            # Handle subscription confirmation
            # ========================================
            if message_type == 'subscribed':
                channel_name = data.get('channel', 'Unknown')
                self.logger.info(f"✅ Subscribed to channel: {channel_name}")
                return
            
            # ========================================
            # Handle BALANCE updates (margins channel)
            # ========================================
            if message_type == 'margins':
                with self._lock:
                    self._balance = RealTimeBalance(
                        asset_symbol=data.get('asset_symbol', 'USD'),
                        balance=float(data.get('balance', 0)),
                        available_balance=float(data.get('available_balance', 0)),
                        blocked_margin=float(data.get('blocked_margin', 0)),
                        portfolio_margin=float(data.get('portfolio_margin', 0)),
                        order_margin=float(data.get('order_margin', 0)),
                        position_margin=float(data.get('position_margin', 0)),
                        commission_blocked=float(data.get('commission_blocked', 0)),
                        timestamp=datetime.now().isoformat()
                    )
                    self.last_update_time = datetime.now()
                
                self.logger.debug(
                    f"💰 Balance Update [{self._balance.asset_symbol}]: "
                    f"Balance=${self._balance.balance:.2f}, "
                    f"Available=${self._balance.available_balance:.2f}, "
                    f"Blocked=${self._balance.blocked_margin:.2f}"
                )
                return
            
            # ========================================
            # Handle UPNL + MAINTENANCE MARGIN updates (portfolio_margins channel)
            # ========================================
            if message_type == 'portfolio_margins':
                # ⚠️ CRITICAL FIX (as per Delta Exchange support):
                # positions_upl is UCF (Unrealized Cash Flow), NOT P&L
                # For short positions, UCF is NEGATIVE when profitable
                # UPNL = -1 × UCF (negate to match UI display)
                ucf_value = float(data.get('positions_upl', 0))
                actual_upnl = -ucf_value  # ✅ Negate UCF to get proper UPNL
                
                with self._lock:
                    self._portfolio_margin = RealTimePortfolioMargin(
                        index_symbol=data.get('index_symbol', 'Unknown'),
                        positions_upl=actual_upnl,  # ⭐ Store negated value (proper UPNL)
                        blocked_margin=float(data.get('blocked_margin', 0)),
                        mm_with_ucf=float(data.get('mm_with_ucf', 0)),
                        mm_without_ucf=float(data.get('mm_without_ucf', 0)),
                        risk_margin=float(data.get('risk_margin', 0)),
                        liquidation_risk=bool(data.get('liquidation_risk', False)),
                        under_liquidation=bool(data.get('under_liquidation', False)),
                        margin_shortfall=float(data.get('margin_shortfall', 0)),
                        timestamp=datetime.now().isoformat()
                    )
                    self.last_update_time = datetime.now()
                
                # Log UPNL update (show both UCF and UPNL for transparency)
                upnl_usd = actual_upnl
                upnl_inr = upnl_usd * 85
                self.logger.info(
                    f"📊 Portfolio Update [{self._portfolio_margin.index_symbol}]: "
                    f"UPNL=${upnl_usd:.2f} USD (₹{upnl_inr:,.2f} INR), "
                    f"UCF=${ucf_value:.2f}, MM=${self._portfolio_margin.mm_with_ucf:.2f}"
                )
                
                # ⚠️ Trigger alerts for liquidation risk
                if self._portfolio_margin.liquidation_risk:
                    self.logger.warning("⚠️ LIQUIDATION RISK DETECTED!")
                    self._trigger_alerts(
                        "Liquidation Risk Warning",
                        asdict(self._portfolio_margin)
                    )
                
                if self._portfolio_margin.under_liquidation:
                    self.logger.error("🚨 ACCOUNT UNDER LIQUIDATION!")
                    self._trigger_alerts(
                        "Account Under Liquidation",
                        asdict(self._portfolio_margin)
                    )
                
                return
            
            # Handle other message types
            if message_type not in ['success', 'subscribed', 'heartbeat']:
                self.logger.debug(f"📨 Message Type: {message_type}")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ Failed to parse message: {e}")
        except Exception as e:
            self.logger.error(f"❌ Error processing message: {e}", exc_info=True)
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        self.logger.error(f"⚠️ WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        self.logger.warning(
            f"🔌 WebSocket closed: {close_status_code} - {close_msg}"
        )
        self.connected = False
        self.authenticated = False
        self.connection_state = "disconnected"
        
        # Exponential backoff for reconnection
        if self.reconnect_delay < self.max_reconnect_delay:
            self.reconnect_delay = min(self.reconnect_delay * 1.5, self.max_reconnect_delay)
            self.logger.info(f"🔄 Next reconnect delay: {self.reconnect_delay:.1f}s")
    
    # ========================================
    # Public API - Get Real-Time Data
    # ========================================
    
    def get_upnl(self) -> tuple[float, float]:
        """
        Get current UPNL (Unrealized PnL)
        
        Returns:
            (upnl_usd, upnl_inr): UPNL in USD and INR
        """
        with self._lock:
            if self._portfolio_margin:
                upnl_usd = self._portfolio_margin.positions_upl
                upnl_inr = upnl_usd * 85  # Convert to INR
                return upnl_usd, upnl_inr
            return 0.0, 0.0
    
    def get_balance(self) -> Optional[RealTimeBalance]:
        """
        Get current balance data
        
        Returns:
            RealTimeBalance object or None if not available
        """
        with self._lock:
            return self._balance
    
    def get_maintenance_margin(self) -> tuple[float, float]:
        """
        Get current maintenance margin
        
        Returns:
            (mm_with_ucf, mm_without_ucf): Maintenance margin with and without unrealized cashflows
        """
        with self._lock:
            if self._portfolio_margin:
                return (
                    self._portfolio_margin.mm_with_ucf,
                    self._portfolio_margin.mm_without_ucf
                )
            return 0.0, 0.0
    
    def get_liquidation_risk(self) -> Dict:
        """
        Get liquidation risk status
        
        Returns:
            Dict with liquidation risk information
        """
        with self._lock:
            if self._portfolio_margin:
                return {
                    'liquidation_risk': self._portfolio_margin.liquidation_risk,
                    'under_liquidation': self._portfolio_margin.under_liquidation,
                    'margin_shortfall': self._portfolio_margin.margin_shortfall,
                    'risk_margin': self._portfolio_margin.risk_margin
                }
            return {
                'liquidation_risk': False,
                'under_liquidation': False,
                'margin_shortfall': 0.0,
                'risk_margin': 0.0
            }
    
    def get_full_status(self) -> Dict:
        """
        Get complete real-time status
        
        Returns:
            Dict with all real-time data
        """
        with self._lock:
            upnl_usd, upnl_inr = self.get_upnl()
            mm_with, mm_without = self.get_maintenance_margin()
            
            return {
                'connected': self.connected,
                'authenticated': self.authenticated,
                'balance': asdict(self._balance) if self._balance else None,
                'portfolio_margin': asdict(self._portfolio_margin) if self._portfolio_margin else None,
                'upnl': {
                    'usd': upnl_usd,
                    'inr': upnl_inr
                },
                'maintenance_margin': {
                    'with_ucf': mm_with,
                    'without_ucf': mm_without
                },
                'liquidation_risk': self.get_liquidation_risk(),
                'last_update': self.last_update_time.isoformat() if self.last_update_time else None,
                'message_count': self.message_count,
                'reconnect_count': self.reconnect_count
            }
    
    # ========================================
    # WebSocket Lifecycle Management
    # ========================================
    
    def start(self):
        """Start WebSocket connection in background thread"""
        if self.running:
            self.logger.warning("⚠️ WebSocket already running")
            return
        
        self.running = True
        
        def run_websocket():
            """WebSocket loop with automatic reconnection"""
            while self.running:
                try:
                    self.logger.info(f"🔗 Connecting to {self.base_url}...")
                    
                    # Enable debug for websocket library
                    # websocket.enableTrace(True)
                    
                    self.ws = websocket.WebSocketApp(
                        self.base_url,
                        on_message=self.on_message,
                        on_error=self.on_error,
                        on_close=self.on_close,
                        on_open=self.on_open
                    )
                    
                    # Run forever (blocking)
                    self.ws.run_forever()
                    
                except Exception as e:
                    self.logger.error(f"❌ WebSocket error: {e}", exc_info=True)
                
                # Reconnect logic with exponential backoff
                if self.running:
                    self.reconnect_count += 1
                    self.connection_state = "disconnected"
                    self.logger.info(
                        f"🔄 Reconnecting in {self.reconnect_delay:.1f}s "
                        f"(attempt {self.reconnect_count})..."
                    )
                    time.sleep(self.reconnect_delay)
        
        # Start WebSocket thread
        thread = threading.Thread(target=run_websocket, daemon=True, name="DeltaWebSocket")
        thread.start()
        self.logger.info("🚀 Delta Exchange WebSocket started")
    
    def stop(self):
        """Stop WebSocket connection"""
        self.logger.info("⏹️ Stopping WebSocket...")
        self.running = False
        if self.ws:
            self.ws.close()
        self.connected = False
        self.authenticated = False
        self.logger.info("✅ WebSocket stopped")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected and authenticated"""
        return self.connected and self.authenticated
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status for monitoring
        Production-ready health check
        """
        with self._lock:
            # Check heartbeat freshness
            heartbeat_healthy = False
            if self.last_update_time:
                time_since_update = (datetime.now() - self.last_update_time).total_seconds()
                heartbeat_healthy = time_since_update < self.heartbeat_timeout
            
            upnl_usd, upnl_inr = self.get_upnl()
            
            return {
                'connection': {
                    'connected': self.connected,
                    'authenticated': self.authenticated,
                    'state': self.connection_state,
                    'reconnect_count': self.reconnect_count
                },
                'heartbeat': {
                    'healthy': heartbeat_healthy,
                    'last_update': self.last_update_time.isoformat() if self.last_update_time else None,
                    'timeout_seconds': self.heartbeat_timeout
                },
                'data': {
                    'upnl_usd': upnl_usd,
                    'upnl_inr': upnl_inr,
                    'has_balance': self._balance is not None,
                    'has_portfolio_margin': self._portfolio_margin is not None,
                    'message_count': self.message_count
                },
                'status': 'healthy' if (self.connected and self.authenticated and heartbeat_healthy) else 'degraded'
            }
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics for monitoring"""
        return {
            'reconnect_count': self.reconnect_count,
            'message_count': self.message_count,
            'uptime_seconds': (datetime.now() - self.last_update_time).total_seconds() if self.last_update_time else 0,
            'connected': self.connected,
            'authenticated': self.authenticated
        }


# ========================================
# Global Singleton Instance
# ========================================

_global_websocket_instance = None
_global_websocket_lock = threading.Lock()

def get_delta_websocket() -> DeltaRealtimeWebSocket:
    """
    Get or create global Delta Exchange WebSocket instance
    
    Returns:
        DeltaRealtimeWebSocket: Global singleton instance
    """
    global _global_websocket_instance
    
    with _global_websocket_lock:
        if _global_websocket_instance is None:
            # Load config from YAML
            cfg = get_config()
            
            # API credentials from environment (security - never in YAML)
            # Support both DELTA_API_KEY and LIVE_DELTA_API_KEY for backward compatibility
            api_key = os.getenv('DELTA_API_KEY') or os.getenv('LIVE_DELTA_API_KEY')
            api_secret = os.getenv('DELTA_API_SECRET') or os.getenv('LIVE_DELTA_API_SECRET')
            
            # WebSocket URL from config based on trading mode
            if cfg.trading_mode == 'demo':
                base_url = cfg.api.demo.websocket_url
            else:
                base_url = cfg.api.live.websocket_url
            
            if not api_key or not api_secret:
                raise ValueError(
                    "DELTA_API_KEY and DELTA_API_SECRET must be set in environment"
                )
            
            # Create instance
            _global_websocket_instance = DeltaRealtimeWebSocket(
                api_key=api_key,
                api_secret=api_secret,
                base_url=base_url
            )
            
            # Start connection
            _global_websocket_instance.start()
        
        return _global_websocket_instance


# ========================================
# CLI Test Script
# ========================================

if __name__ == "__main__":
    """Test script for Delta Exchange WebSocket"""
    import sys
    from pathlib import Path
    
    # Add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    # Load API keys only
    from dotenv import load_dotenv
    load_dotenv('secrets/api_keys.env', verbose=False)
    
    # Set up mode-specific vars
    from bot.utils.env_loader import load_trading_mode_config
    try:
        load_trading_mode_config()
    except Exception as e:
        print(f"⚠️ Warning: {e}")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("🧪 Testing Delta Exchange Real-Time WebSocket (config: YAML)")
    print("=" * 80)
    print()
    
    # Create WebSocket client
    ws_client = get_delta_websocket()
    
    # Add alert callback
    def alert_callback(message: str, data: Dict):
        print(f"\n🚨 ALERT: {message}")
        print(f"   Data: {data}")
    
    ws_client.add_alert_callback(alert_callback)
    
    # Wait for connection
    print("⏳ Waiting for WebSocket connection...")
    time.sleep(5)
    
    # Display status every 5 seconds for 60 seconds
    for i in range(12):
        print(f"\n{'='*80}")
        print(f"Status Update #{i+1}")
        print(f"{'='*80}")
        
        # Get full status
        status = ws_client.get_full_status()
        
        print(f"\n🔌 Connection:")
        print(f"   Connected: {status['connected']}")
        print(f"   Authenticated: {status['authenticated']}")
        print(f"   Messages: {status['message_count']}")
        print(f"   Reconnects: {status['reconnect_count']}")
        
        if status['balance']:
            print(f"\n💰 Balance:")
            balance = status['balance']
            print(f"   Asset: {balance['asset_symbol']}")
            print(f"   Balance: ${balance['balance']:.2f}")
            print(f"   Available: ${balance['available_balance']:.2f}")
            print(f"   Blocked: ${balance['blocked_margin']:.2f}")
        
        if status['upnl']:
            print(f"\n📊 UPNL:")
            print(f"   USD: ${status['upnl']['usd']:.2f}")
            print(f"   INR: ₹{status['upnl']['inr']:,.2f}")
        
        if status['maintenance_margin']:
            print(f"\n🛡️ Maintenance Margin:")
            print(f"   With UCF: ${status['maintenance_margin']['with_ucf']:.2f}")
            print(f"   Without UCF: ${status['maintenance_margin']['without_ucf']:.2f}")
        
        if status['liquidation_risk']:
            print(f"\n⚠️ Liquidation Risk:")
            risk = status['liquidation_risk']
            print(f"   Risk: {risk['liquidation_risk']}")
            print(f"   Under Liquidation: {risk['under_liquidation']}")
            print(f"   Margin Shortfall: ${risk['margin_shortfall']:.2f}")
        
        time.sleep(5)
    
    # Stop WebSocket
    print("\n⏹️ Stopping WebSocket...")
    ws_client.stop()
    print("👋 Test complete!")
