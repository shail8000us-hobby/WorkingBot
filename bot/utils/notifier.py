# bot/utils/notifier.py
from __future__ import annotations
import os
import sys
import time
import json
import urllib.request
import urllib.parse
import logging
from typing import Optional
from collections import deque
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

log = logging.getLogger("runner")


class TelegramNotifier:
    """
    Mode-aware Telegram sender with deduplication.
    Routes to LIVE or DEMO credentials based on TRADING_MODE.
    Prefixes messages with [LIVE] or [DEMO].
    Deduplicates identical messages within 2-second window.
    """

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        # Determine mode from YAML config
        cfg = get_config()
        trading_mode = cfg.trading_mode.lower().strip()
        self.is_live = (trading_mode == "live")
        self.mode_prefix = "[LIVE]" if self.is_live else "[DEMO]"
        
        # Select mode-specific credentials
        self.enabled = False
        self.token = None
        self.chat_id = None
        
        try:
            if token and chat_id:
                # Explicit override
                self.token = token
                self.chat_id = chat_id
            elif self.is_live:
                # LIVE mode: use live telegram config
                self.token = cfg.telegram.live_bot_token.strip()
                self.chat_id = cfg.telegram.live_chat_id.strip()
            else:
                # DEMO mode: use demo telegram config
                self.token = cfg.telegram.demo_bot_token.strip()
                self.chat_id = cfg.telegram.demo_chat_id.strip()
            
            self.enabled = cfg.telegram.enabled
        except AttributeError:
            # Notifications config not defined in YAML - disable gracefully
            log.warning("notifier: disabled (telegram section missing from config.yaml)")
            self.enabled = False

        if self.token and self.chat_id and self.enabled:
            log.info(f"notifier: {self.mode_prefix} routing enabled")
        else:
            self.enabled = False
            if not (self.token and self.chat_id):
                log.warning(
                    f"notifier: disabled (missing {self.mode_prefix} Telegram credentials)")
        
        # Deduplication cache: (message_hash, timestamp)
        self._dedup_cache = deque(maxlen=50)
        self._dedup_window = 2.0  # seconds

    def _should_send(self, text: str) -> bool:
        """Check if message should be sent (deduplication)"""
        now = time.time()
        msg_hash = hash(text)
        
        # Clean old entries
        while self._dedup_cache and (now - self._dedup_cache[0][1]) > self._dedup_window:
            self._dedup_cache.popleft()
        
        # Check for duplicate
        for cached_hash, _ in self._dedup_cache:
            if cached_hash == msg_hash:
                log.debug(f"notifier: dedup skip (within {self._dedup_window}s)")
                return False
        
        # Add to cache
        self._dedup_cache.append((msg_hash, now))
        return True
    
    def send(self, text: str, skip_dedup: bool = False):
        """Send message with mode prefix and deduplication"""
        if not self.enabled:
            return
        
        # Add mode prefix
        prefixed_text = f"{self.mode_prefix} {text}"
        
        # Check deduplication (unless explicitly skipped)
        if not skip_dedup and not self._should_send(prefixed_text):
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = urllib.parse.urlencode(
                {"chat_id": self.chat_id, "text": prefixed_text}).encode()
            # 2 quick retries
            for attempt in range(2):
                try:
                    with urllib.request.urlopen(url, data=data, timeout=10) as r:
                        if r.status == 200:
                            return
                        else:
                            log.warning("notifier: http %s", r.status)
                except Exception as e:
                    if attempt == 1:
                        raise
                    time.sleep(1.0)
        except Exception as e:
            log.warning("notifier: send failed: %s", e)
