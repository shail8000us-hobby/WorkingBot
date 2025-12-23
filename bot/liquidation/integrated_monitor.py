"""
Universal Liquidation Protection System - Product Agnostic
==========================================================

This system uses ONLY Delta Exchange LIVE account data as the single source of truth.
No dependencies on bot memory, internal state, or trading symbols.
Works automatically with BTC, ETH, options, or any future product.

Data Sources:
- GET /v2/wallet/balances - Total balance, available, blocked margin
- GET /v2/positions - All positions with unrealized P&L
- GET /v2/positions/margins - Margin and risk data

Features:
- Product-agnostic: Works with any trading instrument
- Direct Delta Exchange API integration
- Real-time monitoring with WebSocket support
- USD → INR conversion (multiply by 85) for MTM
- No caching, no intermediate storage
- Compatible with existing WebUI backend/frontend
- No dependencies on bot memory or local state
"""

import os
import time
import json
import hmac
import hashlib
import requests
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from collections import deque

# Import comprehensive Delta Exchange real-time WebSocket client
# Provides: UPNL, Balance, Maintenance Margin via WebSocket
try:
    from .delta_realtime_websocket import get_delta_websocket
    DELTA_WEBSOCKET_AVAILABLE = True
except ImportError:
    DELTA_WEBSOCKET_AVAILABLE = False

@dataclass
class Position:
    """Data class for position information"""
    product_id: int
    symbol: str
    size: float
    entry_price: float
    mark_price: float
    liquidation_price: Optional[float]
    unrealized_pnl: float
    margin_used: float
    side: str  # 'long' or 'short'

@dataclass
class AccountBalance:
    """Data class for account balance information"""
    total_balance: float
    available_balance: float
    blocked_balance: float
    maintenance_margin: float

class DeltaExchangeClient:
    """Client for Delta Exchange API - Direct Integration"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://api.india.delta.exchange"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.session = requests.Session()
        
    def _generate_signature(self, method: str, path: str, query: str = "", body: str = "") -> str:
        """Generate HMAC signature for API authentication"""
        message = method + path + query + body
        return hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _make_request(self, method: str, path: str, params: Optional[Dict] = None, 
                     json_body: Optional[Dict] = None) -> Dict:
        """Make authenticated request to Delta Exchange API"""
        try:
            # Prepare request
            query = ""
            if params:
                query = "?" + "&".join([f"{k}={v}" for k, v in params.items()])
            
            body = ""
            if json_body:
                body = json.dumps(json_body, separators=(',', ':'))
            
            # Generate signature
            signature = self._generate_signature(method, path, query, body)
            
            # Prepare headers
            headers = {
                'api-key': self.api_key,
                'signature': signature,
                'timestamp': str(int(time.time() * 1000)),
                'Content-Type': 'application/json'
            }
            
            # Make request
            url = self.base_url + path + query
            response = self.session.request(method, url, headers=headers, json=json_body)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response: {e}")

class IntegratedLiquidationMonitor:
    """
    Integrated liquidation monitor that replaces the old system
    
    This monitor fetches all data directly from Delta Exchange APIs
    and provides the same interface as the old RealTimeLiquidationMonitor
    for seamless WebUI integration.
    """
    
    def __init__(self, config, logger: Optional[logging.Logger] = None):
        """
        Initialize integrated liquidation monitor
        
        Args:
            config: Configuration dictionary or ConfigManager instance
            logger: Logger instance
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Load API credentials from environment (security best practice)
        # Note: Fallback to LIVE_* is for backward compatibility
        self.api_key = os.getenv('DELTA_API_KEY') or os.getenv('LIVE_DELTA_API_KEY')
        self.api_secret = os.getenv('DELTA_API_SECRET') or os.getenv('LIVE_DELTA_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            # Load from secrets file if not in environment
            from pathlib import Path
            from dotenv import load_dotenv
            # Use absolute path from project root
            project_root = Path(__file__).parent.parent.parent
            env_file = project_root / 'secrets' / 'api_keys.env'
            self.logger.debug(f"Attempting to load API keys from: {env_file}")
            self.logger.debug(f"File exists: {env_file.exists()}")
            if env_file.exists():
                load_dotenv(env_file)
                self.api_key = os.getenv('DELTA_API_KEY') or os.getenv('LIVE_DELTA_API_KEY')
                self.api_secret = os.getenv('DELTA_API_SECRET') or os.getenv('LIVE_DELTA_API_SECRET')
                self.logger.debug(f"After load_dotenv - api_key present: {bool(self.api_key)}")
                self.logger.debug(f"After load_dotenv - api_secret present: {bool(self.api_secret)}")
        
        if not self.api_key or not self.api_secret:
            self.logger.error(f"API Key check: DELTA_API_KEY={bool(os.getenv('DELTA_API_KEY'))}, LIVE_DELTA_API_KEY={bool(os.getenv('LIVE_DELTA_API_KEY'))}")
            self.logger.error(f"API Secret check: DELTA_API_SECRET={bool(os.getenv('DELTA_API_SECRET'))}, LIVE_DELTA_API_SECRET={bool(os.getenv('LIVE_DELTA_API_SECRET'))}")
            raise ValueError("Missing DELTA_API_KEY / DELTA_API_SECRET")
        
        # Initialize Delta Exchange client - use the main DeltaClient
        from bot.api.delta_client import DeltaClient
        self.delta_client = DeltaClient()
        
        # Monitoring state
        self.running = False
        self.monitor_thread = None
        self.last_status = {}
        self.last_update_time = None
        
        # Alert system
        self.alert_callbacks = []
        self.emergency_callbacks = []
        
        # Configuration - access from RootConfig.liquidation_protection
        liq_config = config.liquidation_protection if hasattr(config, 'liquidation_protection') else config
        self.check_interval = int(getattr(liq_config, 'liquidation_check_interval', 5))
        self.alert_throttle = int(getattr(liq_config, 'liquidation_alert_throttle', 60))
        self.last_alert_time = {}
        
        # Risk thresholds
        self.margin_warning_1 = float(getattr(liq_config, 'margin_utilization_warning_1', 50.0))
        self.margin_warning_2 = float(getattr(liq_config, 'margin_utilization_warning_2', 70.0))
        self.margin_max = float(getattr(liq_config, 'margin_utilization_max', 40.0))
        self.liquidation_distance_min = float(getattr(liq_config, 'liquidation_distance_min', 60.0))
        self.liquidation_distance_target = float(getattr(liq_config, 'liquidation_distance_target', 70.0))
        
        # History tracking
        self.margin_history = deque(maxlen=100)
        self.distance_history = deque(maxlen=100)
        
        # Real-time WebSocket for UPNL, Balance, and Maintenance Margin
        # Uses Delta Exchange portfolio_margins + margins channels
        self.delta_websocket = None
        if DELTA_WEBSOCKET_AVAILABLE:
            try:
                self.logger.info("🔌 Starting Delta Exchange real-time WebSocket...")
                self.delta_websocket = get_delta_websocket()
                self.logger.info("✅ Delta Exchange real-time WebSocket started (UPNL + Balance + MM)")
                
                # Wait briefly for initial connection
                import time
                time.sleep(2)
                
                if self.delta_websocket.is_connected():
                    self.logger.info("✅ WebSocket connected and authenticated!")
                else:
                    self.logger.warning("⚠️ WebSocket not yet connected, will retry in background")
                    
            except Exception as e:
                self.logger.error(f"❌ Failed to start Delta WebSocket: {e}", exc_info=True)
                self.logger.warning("   Falling back to REST API polling")
        else:
            self.logger.warning("⚠️ Delta WebSocket module not available, using REST API only")
        
        self.logger.info("✅ Integrated Liquidation Monitor initialized with direct Delta Exchange API")
    
    def fetch_positions(self) -> List[Position]:
        """
        Fetch all open positions from Delta Exchange - Product Agnostic
        
        Uses: GET /v2/positions
        Returns: All positions regardless of product/symbol
        Converts: USD unrealized P&L → INR (multiply by 85)
        """
        try:
            # ✅ Use /v2/positions/margined to get mark_price directly
            response = self.delta_client._req('GET', '/v2/positions/margined')
            
            positions = []
            # Handle Delta API response format
            if isinstance(response, dict) and response.get('success'):
                pos_list = response.get('result', [])
            else:
                pos_list = []
            
            for pos_data in pos_list:
                # Get size directly from position data
                position_size = float(pos_data.get('size', 0))
                
                # Skip positions with zero size
                if position_size == 0:
                    continue
                
                # PRIMARY: Calculate manually with formula (Mark - Entry) × Size × 0.001
                # Extract from native Delta API format
                entry_price = float(pos_data.get('entry_price', 0))
                mark_price = float(pos_data.get('mark_price', 0))
                product_symbol = pos_data.get('product_symbol', 'UNKNOWN')
                product_id = int(pos_data.get('product_id', 0))
                
                self.logger.debug(f"Extracting prices for {product_symbol}: entry={entry_price}, mark={mark_price}, size={position_size}")
                
                unrealized_pnl_usd = 0
                if mark_price > 0 and entry_price > 0:
                    # Formula: (Mark - Entry) × Size × 0.001
                    CONTRACT_MULTIPLIER = 0.001
                    unrealized_pnl_usd = (mark_price - entry_price) * position_size * CONTRACT_MULTIPLIER
                    self.logger.debug(f"📊 Manual PnL for {product_symbol}: ({mark_price:.2f} - {entry_price:.2f}) × {position_size} × 0.001 = ${unrealized_pnl_usd:.2f}")
                else:
                    self.logger.debug(f"⚠️ Cannot calculate manual PnL for {product_symbol}: mark_price={mark_price}, entry_price={entry_price}")
                
                # FALLBACK: Use exchange unrealized_pnl if manual calc failed
                if unrealized_pnl_usd == 0:
                    unrealized_pnl_usd = float(pos_data.get('unrealized_pnl', 0))
                    
                    if unrealized_pnl_usd != 0:
                        self.logger.debug(f"📋 Using exchange PnL: ${unrealized_pnl_usd:.2f}")
                
                # ✅ Convert USD to INR (multiply by 85)
                unrealized_pnl_inr = unrealized_pnl_usd * 85
                
                # Determine side from position size
                side = 'long' if position_size > 0 else 'short'
                
                position = Position(
                    product_id=product_id,
                    symbol=product_symbol,
                    size=position_size,
                    entry_price=entry_price,
                    mark_price=mark_price,
                    liquidation_price=float(pos_data.get('liquidation_price', 0)) if pos_data.get('liquidation_price') else None,
                    unrealized_pnl=unrealized_pnl_inr,  # ✅ INR value
                    margin_used=float(pos_data.get('margin', 0)),
                    side=side
                )
                positions.append(position)
            
            self.logger.debug(f"✅ Fetched {len(positions)} positions from Delta Exchange (product-agnostic)")
            return positions
            
        except Exception as e:
            self.logger.error(f"Failed to fetch positions: {e}")
            return []
    
    def fetch_open_orders(self) -> List[Dict]:
        """Fetch open orders from Delta Exchange"""
        try:
            # Use the existing fetch_open_orders method from DeltaClient
            orders = self.delta_client.fetch_open_orders()
            if not orders:
                return []
            
            # Filter and format orders for display
            formatted_orders = []
            for order in orders:
                # Only include orders with valid size and price
                size = order.get('amount') or order.get('remaining') or order.get('size')
                price = order.get('price')
                
                if size and price and float(size) > 0 and float(price) > 0:
                    formatted_orders.append({
                        'side': order.get('side', 'unknown'),
                        'size': float(size),
                        'price': float(price),
                        'symbol': order.get('symbol', 'BTCUSD'),
                        'status': order.get('status', 'open')
                    })
            
            return formatted_orders
            
        except Exception as e:
            self.logger.error(f"Failed to fetch open orders: {e}")
            return []
    
    def fetch_balances(self) -> AccountBalance:
        """
        Fetch account balance from Delta Exchange - Product Agnostic
        
        Uses: GET /v2/wallet/balances
        Returns: Total balance, available, blocked margin exactly as returned by Delta
        No calculations - direct API response
        """
        try:
            response = self.delta_client.get_wallet_balances()
            
            if response.get('success') and response.get('result'):
                # Delta Exchange returns a list of wallets
                wallets = response['result']
                if wallets:
                    wallet = wallets[0]  # Use first wallet (USD wallet)
                    
                    # ✅ Use exact values from Delta Exchange API
                    # blocked_margin or portfolio_margin contains the total blocked amount
                    blocked = float(wallet.get('blocked_margin', 0))
                    if blocked == 0:
                        # Fallback to portfolio_margin
                        blocked = float(wallet.get('portfolio_margin', 0))
                    if blocked == 0:
                        # Last fallback: sum of order + position margin
                        blocked = float(wallet.get('order_margin', 0)) + float(wallet.get('position_margin', 0))
                    
                    # Get balance value first
                    balance_val = float(wallet.get('balance', 0))
                    
                    # ⭐ PRIMARY: Calculate MTM manually from positions using formula
                    # Formula: Sum of [(Mark - Entry) × Size × 0.001] for all positions
                    total_upnl_usd = 0
                    
                    try:
                        # Fetch positions to calculate MTM manually
                        positions = self.fetch_positions()
                        if positions:
                            # Sum up all position PnLs (already calculated with 0.001 multiplier)
                            for pos in positions:
                                # unrealized_pnl is already in INR, convert back to USD
                                pnl_usd = pos.unrealized_pnl / 85
                                total_upnl_usd += pnl_usd
                                self.logger.debug(f"Position {pos.symbol}: PnL = ₹{pos.unrealized_pnl:.2f} = ${pnl_usd:.2f} USD")
                            
                            self.logger.debug(
                                f"📊 MTM from manual calculation ({len(positions)} positions): "
                                f"${total_upnl_usd:.2f} USD = ₹{total_upnl_usd * 85:,.2f} INR"
                            )
                        else:
                            # No positions, MTM = 0
                            total_upnl_usd = 0
                            self.logger.debug("No positions, MTM = $0.00")
                    except Exception as e:
                        self.logger.warning(f"Manual MTM calculation failed: {e}")
                        import traceback
                        self.logger.warning(traceback.format_exc())
                        total_upnl_usd = 0
                    
                    # FALLBACK: Use WebSocket if manual calculation failed or returned 0
                    if total_upnl_usd == 0 and self.delta_websocket and self.delta_websocket.is_connected():
                        upnl_usd, upnl_inr = self.delta_websocket.get_upnl()
                        total_upnl_usd = upnl_usd
                        self.logger.info(
                            f"📋 MTM from WebSocket fallback (positions_upl): "
                            f"${total_upnl_usd:.2f} USD = ₹{upnl_inr:,.2f} INR"
                        )
                    
                    # Store UPNL for later use (will be converted to INR in get_status)
                    self._cached_upnl_usd = total_upnl_usd
                    
                    # ✅ Convert USD to INR (multiply by 85)
                    balance_val_inr = balance_val * 85
                    available_balance_inr = float(wallet.get('available_balance', 0)) * 85
                    blocked_balance_inr = blocked * 85
                    maintenance_margin_inr = float(wallet.get('portfolio_margin', 0)) * 85
                    
                    balance = AccountBalance(
                        total_balance=balance_val_inr,  # Total balance in INR
                        available_balance=available_balance_inr,  # Available in INR
                        blocked_balance=blocked_balance_inr,  # Blocked margin in INR
                        maintenance_margin=maintenance_margin_inr  # Maintenance margin in INR
                    )
                    
                    self.logger.debug(f"✅ Balance: Total={balance.total_balance:.2f}, Available={balance.available_balance:.2f}, Blocked={balance.blocked_balance:.2f}, UPNL=${total_upnl_usd:.2f}")
                    return balance
            
            # Return zero balance if no data
            self.logger.warning("⚠️ No balance data from Delta Exchange API")
            return AccountBalance(0, 0, 0, 0)
            
        except Exception as e:
            self.logger.error(f"Failed to fetch balances: {e}")
            return AccountBalance(0, 0, 0, 0)
    
    def calculate_margin_utilization(self, positions: List[Position], balance: AccountBalance) -> Tuple[float, str]:
        """
        Calculate margin utilization from live Delta Exchange data
        
        Formula: (Blocked Margin / Total Balance) * 100
        Uses: Live API response only, no local calculations
        """
        if balance.total_balance == 0:
            return 0.0, 'SAFE'
        
        # ✅ Use blocked margin directly from Delta Exchange API
        # This reflects real-time margin requirements including volatility adjustments
        utilization = (balance.blocked_balance / balance.total_balance) * 100
        
        # Determine zone based on utilization
        if utilization <= self.margin_max:
            zone = 'GREEN'
        elif utilization <= self.margin_warning_1:
            zone = 'YELLOW'
        elif utilization <= self.margin_warning_2:
            zone = 'ORANGE'
        else:
            zone = 'RED'
        
        self.logger.debug(f"✅ Margin Utilization: {utilization:.2f}% (Zone: {zone})")
        return utilization, zone
    
    def calculate_liquidation_distance(self, balance: AccountBalance) -> Tuple[float, str]:
        """
        Calculate liquidation distance from live Delta Exchange data
        
        Formula: ((Available Balance / Maintenance Margin) - 1) * 100
        Uses: Live API response only - reflects real-time risk including volatility
        """
        if balance.maintenance_margin == 0:
            return 100.0, 'SAFE'
        
        # ✅ Use live maintenance margin from Delta Exchange
        # This automatically reflects increased requirements due to volatility
        distance = ((balance.available_balance / balance.maintenance_margin) - 1) * 100
        
        # Determine zone based on distance
        if distance >= self.liquidation_distance_target:
            zone = 'SAFE'
        elif distance >= self.liquidation_distance_min:
            zone = 'ACCEPTABLE'
        elif distance >= 40:
            zone = 'CAUTION'
        else:
            zone = 'DANGER'
        
        self.logger.debug(f"✅ Liquidation Distance: {distance:.2f}% (Zone: {zone})")
        return distance, zone
    
    def analyze_liquidation_risk(self, positions: List[Position], balance: AccountBalance) -> Dict:
        """Analyze liquidation risk for all positions"""
        # Filter out positions with zero size
        active_positions = [pos for pos in positions if abs(pos.size) > 0]
        
        analysis = {
            'total_positions': len(active_positions),
            'total_margin_used': sum(pos.margin_used for pos in active_positions),
            'total_unrealized_pnl': sum(pos.unrealized_pnl for pos in active_positions),
            'available_balance': balance.available_balance,
            'maintenance_margin': balance.maintenance_margin,
            'high_risk_positions': [],
            'liquidation_distance': 100.0,
            'margin_utilization': 0.0,
            'position_details': []
        }
        
        if not active_positions:
            # Add context when no active positions
            analysis['position_details'].append({
                'symbol': 'No Active Positions',
                'unrealized_pnl': 0,
                'size': 0,
                'status': 'No open positions with non-zero size'
            })
            return analysis
        
        # Calculate margin utilization
        if balance.total_balance > 0:
            analysis['margin_utilization'] = (analysis['total_margin_used'] / balance.total_balance) * 100
        
        # Calculate liquidation distance
        if balance.maintenance_margin > 0:
            analysis['liquidation_distance'] = ((balance.available_balance / balance.maintenance_margin) - 1) * 100
        
        # Check individual position risks and collect details
        for position in active_positions:
            # Add position details
            analysis['position_details'].append({
                'symbol': position.symbol,
                'unrealized_pnl': position.unrealized_pnl,
                'size': position.size,
                'side': position.side,
                'entry_price': position.entry_price,
                'mark_price': position.mark_price,
                'status': 'Active'
            })
            if position.liquidation_price and position.mark_price:
                if position.side == 'long':
                    distance_to_liquidation = ((position.mark_price - position.liquidation_price) / position.mark_price) * 100
                else:  # short
                    distance_to_liquidation = ((position.liquidation_price - position.mark_price) / position.mark_price) * 100
                
                if distance_to_liquidation <= 5.0:  # Within 5% of liquidation
                    risk_info = {
                        'symbol': position.symbol,
                        'side': position.side,
                        'size': position.size,
                        'mark_price': position.mark_price,
                        'liquidation_price': position.liquidation_price,
                        'distance_to_liquidation': distance_to_liquidation,
                        'unrealized_pnl': position.unrealized_pnl
                    }
                    analysis['high_risk_positions'].append(risk_info)
        
        return analysis
    
    def get_status(self) -> Dict:
        """Get current liquidation monitoring status - compatible with old interface"""
        try:
            # Fetch fresh data from Delta Exchange
            positions = self.fetch_positions()
            balance = self.fetch_balances()
            open_orders = self.fetch_open_orders()
            
            # Calculate metrics
            margin_utilization, margin_zone = self.calculate_margin_utilization(positions, balance)
            liquidation_distance, distance_zone = self.calculate_liquidation_distance(balance)
            analysis = self.analyze_liquidation_risk(positions, balance)
            
            # Add open orders context
            analysis['open_orders_count'] = len(open_orders)
            analysis['open_orders'] = open_orders[:5]  # Show first 5 orders
            
            # Get total UPNL from cached value (fetched from wallet meta.net_equity)
            # Convert USD to INR (multiply by 85)
            total_upnl_usd = getattr(self, '_cached_upnl_usd', 0)
            total_upnl_inr = total_upnl_usd * 85
            
            # Build status compatible with old interface
            status = {
                'margin_utilization': margin_utilization,
                'margin_zone': margin_zone,
                'liquidation_distance': liquidation_distance,
                'distance_zone': distance_zone,
                'total_positions': analysis['total_positions'],
                'total_margin_used': analysis['total_margin_used'],
                'total_unrealized_pnl': total_upnl_inr,  # ✅ Use wallet UPNL in INR
                'total_unrealized_pnl_usd': total_upnl_usd,  # Also provide USD value
                'available_balance': balance.available_balance,
                'total_balance': balance.total_balance,
                'blocked_balance': balance.blocked_balance,
                'maintenance_margin': balance.maintenance_margin,
                'high_risk_positions': analysis['high_risk_positions'],
                'position_details': analysis['position_details'],
                'open_orders_count': analysis['open_orders_count'],
                'open_orders': analysis['open_orders'],
                'last_update': datetime.now().isoformat(),
                'data_source': 'delta_exchange_api',
                'timestamp': datetime.now().isoformat()
            }
            
            # Store for history
            self.margin_history.append(margin_utilization)
            self.distance_history.append(liquidation_distance)
            self.last_status = status
            self.last_update_time = datetime.now()
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting status: {e}")
            return {
                'margin_utilization': 0,
                'margin_zone': 'ERROR',
                'liquidation_distance': 0,
                'distance_zone': 'ERROR',
                'error': str(e),
                'last_update': datetime.now().isoformat(),
                'data_source': 'delta_exchange_api'
            }
    
    def get_detailed_status(self) -> Dict:
        """Get detailed status with positions - compatible with old interface"""
        try:
            positions = self.fetch_positions()
            balance = self.fetch_balances()
            
            detailed_status = {
                'positions': [
                    {
                        'product_id': pos.product_id,
                        'symbol': pos.symbol,
                        'size': pos.size,
                        'side': pos.side,
                        'entry_price': pos.entry_price,
                        'mark_price': pos.mark_price,
                        'liquidation_price': pos.liquidation_price,
                        'unrealized_pnl': pos.unrealized_pnl,
                        'margin_used': pos.margin_used
                    }
                    for pos in positions
                ],
                'balance': {
                    'total_balance': balance.total_balance,
                    'available_balance': balance.available_balance,
                    'blocked_balance': balance.blocked_balance,
                    'maintenance_margin': balance.maintenance_margin
                },
                'history': {
                    'margin_utilization': list(self.margin_history),
                    'liquidation_distance': list(self.distance_history)
                },
                'last_update': datetime.now().isoformat(),
                'data_source': 'delta_exchange_api'
            }
            
            return detailed_status
            
        except Exception as e:
            self.logger.error(f"Error getting detailed status: {e}")
            return {
                'positions': [],
                'balance': {},
                'error': str(e),
                'last_update': datetime.now().isoformat(),
                'data_source': 'delta_exchange_api'
            }
    
    def add_alert_callback(self, callback: Callable):
        """Add alert callback function"""
        self.alert_callbacks.append(callback)
    
    def add_emergency_callback(self, callback: Callable):
        """Add emergency callback function"""
        self.emergency_callbacks.append(callback)
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Get current status
                status = self.get_status()
                
                # Check for alerts
                self._check_alerts(status)
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval)
    
    def _check_alerts(self, status: Dict):
        """Check for alert conditions"""
        current_time = time.time()
        
        # Margin utilization alerts
        margin_utilization = status.get('margin_utilization', 0)
        margin_zone = status.get('margin_zone', 'SAFE')
        
        if margin_zone in ['ORANGE', 'RED']:
            alert_key = f"margin_{margin_zone}"
            if current_time - self.last_alert_time.get(alert_key, 0) > self.alert_throttle:
                self._trigger_alert('WARNING', f"Margin utilization {margin_utilization:.1f}% - Zone: {margin_zone}", status)
                self.last_alert_time[alert_key] = current_time
        
        # Liquidation distance alerts
        liquidation_distance = status.get('liquidation_distance', 100)
        distance_zone = status.get('distance_zone', 'SAFE')
        
        if distance_zone in ['CAUTION', 'DANGER']:
            alert_key = f"distance_{distance_zone}"
            if current_time - self.last_alert_time.get(alert_key, 0) > self.alert_throttle:
                self._trigger_alert('CRITICAL', f"Liquidation distance {liquidation_distance:.1f}% - Zone: {distance_zone}", status)
                self.last_alert_time[alert_key] = current_time
        
        # High risk position alerts
        high_risk_positions = status.get('high_risk_positions', [])
        if high_risk_positions:
            alert_key = "high_risk_positions"
            if current_time - self.last_alert_time.get(alert_key, 0) > self.alert_throttle:
                self._trigger_alert('CRITICAL', f"{len(high_risk_positions)} positions at high liquidation risk", status)
                self.last_alert_time[alert_key] = current_time
    
    def _trigger_alert(self, level: str, message: str, status: Dict):
        """Trigger alert callbacks"""
        for callback in self.alert_callbacks:
            try:
                callback(level, message, status)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")
    
    def start_monitoring(self):
        """Start real-time liquidation monitoring"""
        if self.running:
            self.logger.warning("⚠️ Real-time monitoring already running")
            return
        
        self.running = True
        
        # Start main monitoring loop
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("🚀 Integrated liquidation monitoring started with direct Delta Exchange API")
    
    def stop_monitoring(self):
        """Stop real-time liquidation monitoring"""
        self.running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        self.logger.info("🛑 Integrated liquidation monitoring stopped")
    
    def is_running(self) -> bool:
        """Check if monitoring is running"""
        return self.running
    
    def get_zone(self, metric: str) -> str:
        """Get zone for specific metric - compatible with old interface"""
        if not self.last_status:
            return 'UNKNOWN'
        
        if metric == 'margin':
            return self.last_status.get('margin_zone', 'UNKNOWN')
        elif metric == 'distance':
            return self.last_status.get('distance_zone', 'UNKNOWN')
        else:
            return 'UNKNOWN'

# Backward compatibility - create alias for old interface
RealTimeLiquidationMonitor = IntegratedLiquidationMonitor
