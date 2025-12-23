#!/usr/bin/env python3
"""
Reconciliation Telegram Notifier
Sends alerts for critical discrepancies with rate limiting and deduplication

Configuration (from YAML):
- telegram.bot_token or telegram.demo_bot_token (based on trading_mode)
- telegram.chat_id or telegram.demo_chat_id (based on trading_mode)
- telegram.enabled
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
from pathlib import Path
import requests

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.loader import get_config


class ReconciliationTelegramNotifier:
    """
    Sends Telegram alerts for reconciliation discrepancies
    - Rate limiting: max 1 alert per discrepancy per hour
    - Deduplication: tracks sent alerts
    - Respects acknowledged/ignored orders
    """
    
    def __init__(self, reconciliation_service):
        self.recon_service = reconciliation_service
        
        # Load YAML configuration
        yaml_config = get_config()
        
        # Get Telegram config based on trading mode
        if yaml_config.trading_mode == 'demo':
            self.bot_token = yaml_config.telegram.demo_bot_token.strip()
            self.chat_id = yaml_config.telegram.demo_chat_id.strip()
        else:
            self.bot_token = yaml_config.telegram.live_bot_token.strip()
            self.chat_id = yaml_config.telegram.live_chat_id.strip()
        
        self.enabled = yaml_config.telegram.enabled and bool(self.bot_token and self.chat_id)
        
        # Alert tracking
        self.alert_registry: Dict[str, float] = {}  # order_id -> last_alert_timestamp
        self.alert_cooldown = 3600  # 1 hour between alerts for same order
        
        # Alert registry file
        self.registry_file = Path(reconciliation_service.base_dir) / "bot" / "audit" / "recon_alert_registry.json"
        
        # Load registry
        self._load_registry()
        
        if not self.enabled:
            print("⚠️  ReconciliationTelegramNotifier: Telegram not configured, notifications disabled")
    
    def _load_registry(self):
        """Load alert registry from file"""
        try:
            if self.registry_file.exists():
                with open(self.registry_file) as f:
                    data = json.load(f)
                    self.alert_registry = data.get("alerts", {})
        except Exception as e:
            print(f"⚠️  Could not load alert registry: {e}")
    
    def _save_registry(self):
        """Save alert registry to file"""
        try:
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "alerts": self.alert_registry,
                "updated_at": datetime.utcnow().isoformat()
            }
            with open(self.registry_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save alert registry: {e}")
    
    def _should_alert(self, order_id: str, acknowledged: bool, ignored_until: Optional[str]) -> bool:
        """Determine if we should send alert for this order"""
        
        # Don't alert for acknowledged orders
        if acknowledged:
            return False
        
        # Don't alert for ignored orders
        if ignored_until:
            try:
                ignore_dt = datetime.fromisoformat(ignored_until)
                if datetime.utcnow() < ignore_dt:
                    return False
            except:
                pass
        
        # Check cooldown
        last_alert = self.alert_registry.get(order_id)
        if last_alert:
            if time.time() - last_alert < self.alert_cooldown:
                return False
        
        return True
    
    def _send_telegram(self, message: str):
        """Send message via Telegram Bot API"""
        if not self.enabled:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            # Suppress telegram errors in demo mode (invalid token expected)
            pass
    
    def _format_alert(self, record: Dict) -> str:
        """Format reconciliation record as Telegram alert"""
        
        source = record.get("source", "Unknown")
        order_id = record.get("order_id", "N/A")
        symbol = record.get("symbol", "N/A")
        side = record.get("side", "N/A")
        qty = record.get("qty", 0)
        price = record.get("price", 0)
        
        discrepancy = record.get("discrepancy", {})
        reason = discrepancy.get("reason", "Unknown")
        severity = discrepancy.get("severity", "info")
        
        ex_status = record.get("exchange_status") or "N/A"
        bot_status = record.get("bot_status") or "N/A"
        
        # Severity emoji
        emoji = "🔴" if severity == "critical" else "⚠️"
        
        message = f"{emoji} *Reconciliation Alert*\n\n"
        message += f"*Severity:* {severity.upper()}\n"
        message += f"*Reason:* {reason}\n\n"
        message += f"*Order Details:*\n"
        message += f"• Source: {source}\n"
        message += f"• Order ID: `{order_id}`\n"
        message += f"• Symbol: {symbol}\n"
        message += f"• Side: {side}\n"
        message += f"• Qty: {qty} @ ${price}\n\n"
        message += f"*Status:*\n"
        message += f"• Exchange: {ex_status}\n"
        message += f"• Bot: {bot_status}\n\n"
        message += f"🔗 Check WebUI for details"
        
        return message
    
    def check_and_alert(self, summary: Dict):
        """Check reconciliation summary and send alerts for critical discrepancies"""
        
        if not self.enabled:
            return
        
        try:
            records = summary.get("records", [])
            
            # Filter for critical discrepancies
            critical_records = []
            for record in records:
                discrepancy = record.get("discrepancy")
                if not discrepancy:
                    continue
                
                severity = discrepancy.get("severity", "info")
                if severity != "critical":
                    continue
                
                order_id = record.get("order_id")
                if not order_id:
                    continue
                
                acknowledged = record.get("acknowledged", False)
                ignored_until = record.get("ignored_until")
                
                if self._should_alert(order_id, acknowledged, ignored_until):
                    critical_records.append(record)
            
            # Send alerts
            for record in critical_records:
                order_id = record.get("order_id")
                message = self._format_alert(record)
                
                self._send_telegram(message)
                
                # Update registry
                self.alert_registry[order_id] = time.time()
            
            # Save registry if we sent any alerts
            if critical_records:
                self._save_registry()
                print(f"📢 Sent {len(critical_records)} reconciliation alert(s) via Telegram")
        
        except Exception as e:
            print(f"⚠️  Alert check failed: {e}")
    
    def send_summary_alert(self, counters: Dict):
        """Send periodic summary if there are unresolved issues"""
        
        if not self.enabled:
            return
        
        try:
            mismatched = counters.get("mismatched", 0)
            critical = counters.get("critical", 0)
            
            if mismatched == 0:
                return
            
            message = f"📊 *Reconciliation Summary*\n\n"
            message += f"• Total Mismatches: {mismatched}\n"
            message += f"• Critical Issues: {critical}\n"
            message += f"• Total Orders: {counters.get('total', 0)}\n"
            message += f"• Bot Placed: {counters.get('bot_placed', 0)}\n"
            message += f"• User Placed: {counters.get('user_placed', 0)}\n\n"
            message += f"🔗 Check WebUI for details"
            
            self._send_telegram(message)
        
        except Exception as e:
            print(f"⚠️  Summary alert failed: {e}")


def send_telegram_alert(message: str, parse_mode: str = "HTML") -> bool:
    """
    Simple function to send Telegram alert (for liquidation monitoring)
    
    Args:
        message: Message to send
        parse_mode: Message format (HTML, Markdown, or None)
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Load YAML configuration
        yaml_config = get_config()
        
        # Get Telegram config based on trading mode
        if yaml_config.trading_mode == 'demo':
            bot_token = yaml_config.telegram.demo_bot_token.strip()
            chat_id = yaml_config.telegram.demo_chat_id.strip()
        else:
            bot_token = yaml_config.telegram.live_bot_token.strip()
            chat_id = yaml_config.telegram.live_chat_id.strip()
        
        if not yaml_config.telegram.enabled or not bot_token or not chat_id:
            print("⚠️  Telegram not configured or disabled")
            return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print("✅ Telegram alert sent successfully")
            return True
        else:
            print(f"❌ Telegram API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending Telegram alert: {e}")
        return False
