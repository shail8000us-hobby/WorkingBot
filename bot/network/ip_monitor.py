"""
IP Monitor for Dynamic IP Detection
Monitors public IP address and alerts on changes to handle Delta Exchange whitelist requirements
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

import requests

from bot.state.store import StateStore
from bot.utils.atomic_file import atomic_write_json

# Setup logging
logger = logging.getLogger("ip_monitor")


class IPMonitor:
    """Monitors public IP address and detects changes"""
    
    def __init__(self, check_interval: int = 300):
        """
        Initialize IP Monitor
        
        Args:
            check_interval: Seconds between IP checks (default: 300 = 5 minutes)
        """
        self.check_interval = check_interval
        self.state_file = Path("ip_state.json")
        self._store = StateStore(self.state_file, default={})
        self.current_ip: Optional[str] = None
        self.last_ip: Optional[str] = None
        self.last_check_time: float = 0
        self.change_detected: bool = False
        
        # Load previous state
        self._load_state()
    
    def _load_state(self):
        """Load IP state from disk"""
        try:
            if self.state_file.exists():
                state = self._store.locked_read()
                self.last_ip = state.get('ip')
                self.current_ip = self.last_ip
                logger.info(f"Loaded previous IP from state: {self.last_ip}")
        except Exception as e:
            logger.warning(f"Failed to load IP state: {e}")
    
    def _save_state(self):
        """Save IP state to disk"""
        try:
            state = {
                'ip': self.current_ip,
                'timestamp': datetime.now().isoformat(),
                'last_change': datetime.now().isoformat() if self.change_detected else None
            }
            atomic_write_json(self.state_file, state, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save IP state: {e}")
    
    def get_public_ip(self) -> Optional[str]:
        """
        Fetch current public IP address using multiple services for reliability
        
        Returns:
            Public IP address or None if all services fail
        """
        services = [
            "https://api.ipify.org",
            "https://icanhazip.com",
            "https://ifconfig.me/ip",
            "https://ipinfo.io/ip",
            "https://checkip.amazonaws.com"
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    ip = response.text.strip()
                    logger.debug(f"Got IP from {service}: {ip}")
                    return ip
            except Exception as e:
                logger.debug(f"Failed to get IP from {service}: {e}")
                continue
        
        logger.error("Failed to get public IP from all services")
        return None
    
    def check_ip_change(self) -> bool:
        """
        Check if IP has changed since last check
        
        Returns:
            True if IP changed, False otherwise
        """
        now = time.time()
        
        # Rate limit checks
        if now - self.last_check_time < self.check_interval:
            return False
        
        self.last_check_time = now
        
        # Get current IP
        new_ip = self.get_public_ip()
        
        if not new_ip:
            logger.warning("Could not fetch current IP")
            return False
        
        # Update current IP
        self.current_ip = new_ip
        
        # Check for change
        if self.last_ip and self.last_ip != new_ip:
            logger.warning(f"🚨 IP CHANGE DETECTED!")
            logger.warning(f"   Old IP: {self.last_ip}")
            logger.warning(f"   New IP: {new_ip}")
            self.change_detected = True
            self.last_ip = new_ip
            self._save_state()
            return True
        
        # First time or no change
        if not self.last_ip:
            logger.info(f"Initial IP detected: {new_ip}")
            self.last_ip = new_ip
            self._save_state()
        
        self.change_detected = False
        return False
    
    def get_delta_whitelist_url(self, mode: str = "demo") -> str:
        """
        Get Delta Exchange whitelist management URL
        
        Args:
            mode: 'demo' or 'live'
        
        Returns:
            URL to whitelist management page
        """
        if mode == "live":
            return "https://www.delta.exchange/app/settings/api-keys"
        else:
            return "https://testnet.delta.exchange/app/settings/api-keys"
    
    def format_alert_message(self, mode: str = "demo") -> str:
        """
        Format Telegram alert message for IP change
        
        Args:
            mode: 'demo' or 'live'
        
        Returns:
            Formatted alert message
        """
        whitelist_url = self.get_delta_whitelist_url(mode)
        
        message = f"""
🚨 **IP ADDRESS CHANGED** 🚨

Your public IP has changed and **bot trading is PAUSED**.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **Details:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Old IP: `{self.last_ip}`
New IP: `{self.current_ip}`
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ **ACTION REQUIRED:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to Delta Exchange API settings:
   {whitelist_url}

2. Update IP whitelist:
   • Remove old IP: `{self.last_ip}`
   • Add new IP: `{self.current_ip}`

3. Bot will auto-resume trading in 30 seconds!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 **Tip:** Consider getting a static IP or VPS to avoid this!
"""
        return message.strip()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current IP monitor status
        
        Returns:
            Status dictionary
        """
        return {
            'current_ip': self.current_ip,
            'last_ip': self.last_ip,
            'change_detected': self.change_detected,
            'last_check': datetime.fromtimestamp(self.last_check_time).isoformat() if self.last_check_time > 0 else None,
            'check_interval': self.check_interval
        }


# Singleton instance
_ip_monitor: Optional[IPMonitor] = None


def get_ip_monitor(check_interval: int = 300) -> IPMonitor:
    """Get or create IP monitor singleton"""
    global _ip_monitor
    if _ip_monitor is None:
        _ip_monitor = IPMonitor(check_interval)
    return _ip_monitor


if __name__ == "__main__":
    # Test IP monitor
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    monitor = get_ip_monitor(check_interval=10)  # 10 seconds for testing
    
    print("Testing IP Monitor...")
    print(f"Current IP: {monitor.get_public_ip()}")
    print(f"Status: {monitor.get_status()}")
    
    if monitor.check_ip_change():
        print("\n" + monitor.format_alert_message())
    else:
        print("\nNo IP change detected")
