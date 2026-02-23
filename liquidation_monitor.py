#!/usr/bin/env python3
"""
Standalone Liquidation Monitor for Delta Exchange
=================================================

This module fetches all position and margin data directly from Delta Exchange APIs
without relying on any local bot memory, cache, or state files.

Author: Expert Python Backend Engineer
Version: 1.0.0
"""

import os
import time
import json
import hmac
import hashlib
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
import logging.handlers

# Configure logging with rotating file handler
rotating_handler = logging.handlers.RotatingFileHandler(
    'liquidation_monitor.log',
    maxBytes=10*1024*1024,  # 10MB max per file
    backupCount=3  # Keep 3 backups
)
rotating_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        rotating_handler,
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
    """Client for Delta Exchange API"""
    
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
            logger.error(f"API request failed: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise

class LiquidationMonitor:
    """Main liquidation monitoring class"""
    
    def __init__(self, api_key: str, api_secret: str, refresh_interval: int = 3):
        self.client = DeltaExchangeClient(api_key, api_secret)
        self.refresh_interval = refresh_interval
        self.liquidation_threshold = 5.0  # Alert when within 5% of liquidation
        
    def fetch_positions(self) -> List[Position]:
        """Fetch all open positions from Delta Exchange"""
        try:
            logger.debug("Fetching positions from Delta Exchange...")
            response = self.client._make_request("GET", "/v2/positions")
            
            positions = []
            if response.get('success') and response.get('result'):
                for pos_data in response['result']:
                    # Skip positions with zero size
                    if float(pos_data.get('size', 0)) == 0:
                        continue
                        
                    position = Position(
                        product_id=int(pos_data.get('product_id', 0)),
                        symbol=pos_data.get('product_symbol', 'UNKNOWN'),
                        size=float(pos_data.get('size', 0)),
                        entry_price=float(pos_data.get('entry_price', 0)),
                        mark_price=float(pos_data.get('mark_price', 0)),
                        liquidation_price=float(pos_data.get('liquidation_price', 0)) if pos_data.get('liquidation_price') else None,
                        unrealized_pnl=float(pos_data.get('unrealized_pnl', 0)),
                        margin_used=float(pos_data.get('margin', 0)),
                        side='long' if float(pos_data.get('size', 0)) > 0 else 'short'
                    )
                    positions.append(position)
            
            logger.info(f"Fetched {len(positions)} open positions")
            return positions
            
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return []
    
    def fetch_balances(self) -> AccountBalance:
        """Fetch account balance information from Delta Exchange"""
        try:
            logger.debug("Fetching account balances from Delta Exchange...")
            response = self.client._make_request("GET", "/v2/wallet/balances")
            
            if response.get('success') and response.get('result'):
                # Delta Exchange returns a list of wallets
                wallets = response['result']
                if wallets:
                    wallet = wallets[0]  # Use first wallet
                    # FIX: Use blocked_margin for Portfolio Margin mode (not blocked_balance)
                    blocked = float(wallet.get('blocked_margin', 0) or wallet.get('blocked_balance', 0) or 0)
                    balance = AccountBalance(
                        total_balance=float(wallet.get('balance', 0)),
                        available_balance=float(wallet.get('available_balance', 0)),
                        blocked_balance=blocked,
                        maintenance_margin=float(wallet.get('maintenance_margin', 0) or blocked * 0.8)  # Estimate MM if not provided
                    )
                    logger.info(f"Fetched account balance: Available ${balance.available_balance:.2f}, Blocked ${balance.blocked_balance:.2f}")
                    return balance
            
            # Return zero balance if no data
            logger.warning("No balance data received from API")
            return AccountBalance(0, 0, 0, 0)
            
        except Exception as e:
            logger.error(f"Failed to fetch balances: {e}")
            return AccountBalance(0, 0, 0, 0)
    
    def analyze_liquidation_risk(self, positions: List[Position], balance: AccountBalance) -> Dict:
        """Analyze liquidation risk for all positions"""
        # FIX: Use wallet's blocked_balance for margin_used (not sum of per-position margins)
        # In Portfolio Margin mode, per-position margin is always 0
        sum_position_margin = sum(pos.margin_used for pos in positions)
        total_margin_used = balance.blocked_balance if balance.blocked_balance > 0 else sum_position_margin
        
        analysis = {
            'total_positions': len(positions),
            'total_margin_used': total_margin_used,
            'total_unrealized_pnl': sum(pos.unrealized_pnl for pos in positions),
            'available_balance': balance.available_balance,
            'maintenance_margin': balance.maintenance_margin,
            'high_risk_positions': [],
            'liquidation_distance': 100.0,
            'margin_utilization': 0.0
        }
        
        if not positions:
            logger.info("No open positions - liquidation risk: SAFE")
            return analysis
        
        # Calculate margin utilization
        if balance.total_balance > 0:
            analysis['margin_utilization'] = (analysis['total_margin_used'] / balance.total_balance) * 100
        
        # Calculate liquidation distance
        if balance.maintenance_margin > 0:
            analysis['liquidation_distance'] = ((balance.available_balance / balance.maintenance_margin) - 1) * 100
        
        # Check individual position risks
        for position in positions:
            if position.liquidation_price and position.mark_price:
                if position.side == 'long':
                    distance_to_liquidation = ((position.mark_price - position.liquidation_price) / position.mark_price) * 100
                else:  # short
                    distance_to_liquidation = ((position.liquidation_price - position.mark_price) / position.mark_price) * 100
                
                if distance_to_liquidation <= self.liquidation_threshold:
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
                    logger.warning(f"🚨 HIGH RISK: {position.symbol} {position.side} position within {distance_to_liquidation:.2f}% of liquidation!")
        
        return analysis
    
    def print_status_report(self, positions: List[Position], balance: AccountBalance, analysis: Dict):
        """Print comprehensive status report"""
        print("\n" + "="*80)
        print(f"📊 LIQUIDATION MONITOR REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Account Summary
        print(f"\n💰 ACCOUNT SUMMARY:")
        print(f"   Total Balance:     ₹{balance.total_balance:,.2f}")
        print(f"   Available:         ₹{balance.available_balance:,.2f}")
        print(f"   Blocked:           ₹{balance.blocked_balance:,.2f}")
        print(f"   Maintenance Margin: ₹{balance.maintenance_margin:,.2f}")
        
        # Risk Analysis
        print(f"\n⚠️  RISK ANALYSIS:")
        print(f"   Margin Utilization: {analysis['margin_utilization']:.1f}%")
        print(f"   Liquidation Distance: {analysis['liquidation_distance']:.1f}%")
        print(f"   Total Margin Used:   ₹{analysis['total_margin_used']:,.2f}")
        print(f"   Total Unrealized PnL: ₹{analysis['total_unrealized_pnl']:,.2f}")
        
        # Risk Status
        if analysis['liquidation_distance'] > 60:
            risk_status = "🟢 SAFE"
        elif analysis['liquidation_distance'] > 30:
            risk_status = "🟡 CAUTION"
        else:
            risk_status = "🔴 HIGH RISK"
        
        print(f"   Overall Risk:       {risk_status}")
        
        # Positions Summary
        print(f"\n📈 POSITIONS SUMMARY ({analysis['total_positions']} positions):")
        if positions:
            for pos in positions:
                pnl_indicator = "📈" if pos.unrealized_pnl >= 0 else "📉"
                print(f"   {pnl_indicator} {pos.symbol} {pos.side.upper()}: "
                      f"Size={pos.size:.4f}, Mark=₹{pos.mark_price:,.2f}, "
                      f"PnL=₹{pos.unrealized_pnl:,.2f}, Margin=₹{pos.margin_used:,.2f}")
                if pos.liquidation_price:
                    print(f"      💀 Liquidation: ₹{pos.liquidation_price:,.2f}")
        else:
            print("   No open positions")
        
        # High Risk Alerts
        if analysis['high_risk_positions']:
            print(f"\n🚨 HIGH RISK ALERTS ({len(analysis['high_risk_positions'])} positions):")
            for risk in analysis['high_risk_positions']:
                print(f"   ⚠️  {risk['symbol']} {risk['side'].upper()}: "
                      f"Only {risk['distance_to_liquidation']:.2f}% from liquidation!")
        else:
            print(f"\n✅ No high-risk positions detected")
        
        print("="*80)
    
    def run_monitoring_cycle(self):
        """Run one complete monitoring cycle"""
        try:
            # Fetch fresh data from Delta Exchange
            positions = self.fetch_positions()
            balance = self.fetch_balances()
            
            # Analyze liquidation risk
            analysis = self.analyze_liquidation_risk(positions, balance)
            
            # Print comprehensive report
            self.print_status_report(positions, balance, analysis)
            
            # Log critical alerts
            if analysis['high_risk_positions']:
                logger.critical(f"CRITICAL: {len(analysis['high_risk_positions'])} positions at high liquidation risk!")
            
            if analysis['liquidation_distance'] < 30:
                logger.critical(f"CRITICAL: Liquidation distance only {analysis['liquidation_distance']:.1f}%!")
            
            return True
            
        except Exception as e:
            logger.error(f"Monitoring cycle failed: {e}")
            return False
    
    def start_monitoring(self):
        """Start continuous monitoring"""
        logger.info(f"🚀 Starting Liquidation Monitor (refresh every {self.refresh_interval}s)")
        logger.info("📡 Fetching data directly from Delta Exchange APIs")
        logger.info("🛑 Press Ctrl+C to stop monitoring")
        
        cycle_count = 0
        consecutive_failures = 0
        
        try:
            while True:
                cycle_count += 1
                logger.info(f"Starting monitoring cycle #{cycle_count}")
                
                success = self.run_monitoring_cycle()
                
                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= 5:
                        logger.critical("Too many consecutive failures. Stopping monitor.")
                        break
                
                # Wait for next cycle
                time.sleep(self.refresh_interval)
                
        except KeyboardInterrupt:
            logger.info("🛑 Monitoring stopped by user")
        except Exception as e:
            logger.critical(f"Fatal error in monitoring: {e}")
        
        logger.info("📊 Liquidation monitoring ended")

def load_api_credentials():
    """Load API credentials from secrets/api_keys.env via centralized config loader"""
    from config.loader import get_config, get_api_credentials
    
    # Get configuration and credentials
    config = get_config()
    credentials = get_api_credentials(config.trading_mode)
    
    api_key = credentials['api_key']
    api_secret = credentials['api_secret']
    
    if not api_key or not api_secret:
        raise ValueError(
            "API credentials not found! Please set credentials in secrets/api_keys.env:\n"
            "  LIVE_DELTA_API_KEY=your_live_key\n"
            "  LIVE_DELTA_API_SECRET=your_live_secret\n"
            "  DEMO_DELTA_API_KEY=your_demo_key\n"
            "  DEMO_DELTA_API_SECRET=your_demo_secret"
        )
    
    return api_key, api_secret

def main():
    """Main function to run the liquidation monitor"""
    try:
        # Load API credentials
        api_key, api_secret = load_api_credentials()
        
        # Create and start monitor
        monitor = LiquidationMonitor(
            api_key=api_key,
            api_secret=api_secret,
            refresh_interval=3  # Refresh every 3 seconds
        )
        
        monitor.start_monitoring()
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\n❌ {e}")
        print("\n💡 To fix this:")
        print("1. Create a .env file with:")
        print("   DELTA_API_KEY=your_api_key")
        print("   DELTA_API_SECRET=your_api_secret")
        print("2. Or set environment variables:")
        print("   export DELTA_API_KEY=your_api_key")
        print("   export DELTA_API_SECRET=your_api_secret")
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        print(f"\n💥 Fatal error: {e}")

if __name__ == "__main__":
    main()
