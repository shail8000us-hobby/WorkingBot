#!/usr/bin/env python3
"""
Telegram Bot Command Handler
Handles commands sent to Telegram bots for status queries and control

Commands for Grid Bot (@BTCSSR_bot):
- /status - Get bot status and current positions
- /pnl - Get current P&L
- /positions - List open positions
- /guardian - Get Guardian status
- /help - Show available commands

Commands for Options Bot:
- /status - Get options positions summary
- /positions - List all options positions
- /pnl - Get options P&L
- /expiry - Get expiry warnings
- /help - Show available commands

Created: January 19, 2026
"""

import os
import sys
import json
import time
import requests
import logging
import subprocess
import signal
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from collections import defaultdict

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

logger = logging.getLogger(__name__)


class TelegramBotCommandHandler:
    """
    Handles incoming commands from Telegram and responds with status information.
    Polls for updates and responds to commands.
    """
    
    def __init__(self, bot_token: str, bot_type: str = "grid"):
        """
        Initialize command handler.
        
        Args:
            bot_token: Telegram bot token
            bot_type: Type of bot ('grid' or 'options')
        """
        self.bot_token = bot_token
        self.bot_type = bot_type
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.last_update_id = 0
        self.running = False
        
        # Load config
        try:
            self.config = get_config()
            logger.info(f"✅ Config loaded for {bot_type} bot command handler")
        except Exception as e:
            logger.warning(f"⚠️ Could not load config: {e}")
            self.config = None
        
        # Authentication
        self.authorized_chat_ids = self._load_authorized_users()
        
        # Rate limiting
        self.command_timestamps = defaultdict(list)
        self.rate_limit_window = 60  # seconds
        self.rate_limit_max = 15  # max commands per window
    
    def _load_authorized_users(self) -> set:
        """Load authorized chat IDs from config"""
        authorized = set()
        if self.config:
            # Load and validate chat_id
            if hasattr(self.config.telegram, 'chat_id'):
                chat_id = str(self.config.telegram.chat_id).strip()
                if chat_id and chat_id.isdigit():
                    authorized.add(chat_id)
                elif chat_id:
                    logger.warning(f"⚠️ Invalid chat_id in config: {chat_id}")
            
            # Load and validate options_chat_id
            if hasattr(self.config.telegram, 'options_chat_id'):
                options_chat_id = str(self.config.telegram.options_chat_id).strip()
                if options_chat_id and options_chat_id.isdigit():
                    authorized.add(options_chat_id)
                elif options_chat_id:
                    logger.warning(f"⚠️ Invalid options_chat_id in config: {options_chat_id}")
        
        if not authorized:
            logger.warning("⚠️ No authorized chat IDs configured - bot will accept commands from anyone!")
        
        return authorized
    
    def _check_rate_limit(self, chat_id: str) -> bool:
        """Check if user is rate limited"""
        now = time.time()
        # Clean old timestamps
        self.command_timestamps[chat_id] = [
            ts for ts in self.command_timestamps[chat_id] 
            if now - ts < self.rate_limit_window
        ]
        
        if len(self.command_timestamps[chat_id]) >= self.rate_limit_max:
            return False
        
        self.command_timestamps[chat_id].append(now)
        return True
    
    def send_message(self, chat_id: str, text: str, parse_mode: str = "Markdown"):
        """Send a message to a Telegram chat"""
        try:
            MAX_LENGTH = 4096
            
            # Truncate if too long
            if len(text) > MAX_LENGTH:
                text = text[:MAX_LENGTH - 100] + "\n\n... _(message truncated)_"
                logger.warning(f"Message truncated to {MAX_LENGTH} chars")
            
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def get_updates(self, timeout: int = 30) -> List[Dict]:
        """Get updates from Telegram"""
        try:
            url = f"{self.api_url}/getUpdates"
            params = {
                "offset": self.last_update_id + 1,
                "timeout": timeout
            }
            response = requests.get(url, params=params, timeout=timeout + 5)
            response.raise_for_status()
            data = response.json()
            
            if data.get("ok"):
                return data.get("result", [])
            return []
        except Exception as e:
            logger.debug(f"Error getting updates: {e}")
            return []
    
    def handle_command(self, message: Dict) -> Optional[str]:
        """
        Handle a command message and return response text.
        
        Args:
            message: Telegram message dict
            
        Returns:
            Response text or None
        """
        text = message.get("text", "")
        chat_id = str(message.get("chat", {}).get("id"))
        username = message.get("from", {}).get("username", "unknown")
        
        if not text.startswith("/"):
            return None
        
        # Authentication check
        if self.authorized_chat_ids and chat_id not in self.authorized_chat_ids:
            logger.warning(f"❌ Unauthorized access attempt from {username} ({chat_id})")
            return "⛔ *Access Denied*\n\nThis bot is private."
        
        # Rate limiting check
        if not self._check_rate_limit(chat_id):
            logger.warning(f"⚠️ Rate limit exceeded for {username} ({chat_id})")
            return "⚠️ *Too Many Commands*\n\nPlease wait 60 seconds before sending more commands."
        
        command = text.split()[0].lower()
        
        # Route to appropriate handler
        if self.bot_type == "grid":
            return self._handle_grid_command(command, chat_id)
        elif self.bot_type == "options":
            return self._handle_options_command(command, chat_id)
        
        return None
    
    def _handle_grid_command(self, command: str, chat_id: str) -> Optional[str]:
        """Handle grid bot commands"""
        
        if command == "/start":
            return self._cmd_start_grid()
        elif command == "/help":
            return self._cmd_help_grid()
        elif command == "/status":
            return self._cmd_grid_status()
        elif command == "/positions":
            return self._cmd_grid_positions()
        elif command == "/pnl":
            return self._cmd_grid_pnl()
        elif command == "/guardian":
            return self._cmd_guardian_status()
        elif command == "/startbot":
            return self._cmd_start_bot()
        elif command == "/stopbot":
            return self._cmd_stop_bot()
        elif command == "/killbot":
            return self._cmd_kill_bot()
        elif command == "/restart":
            return self._cmd_restart_bot()
        else:
            return f"Unknown command: {command}\nUse /help to see available commands."
    
    def _handle_options_command(self, command: str, chat_id: str) -> Optional[str]:
        """Handle options bot commands"""
        
        if command == "/start":
            return self._cmd_start_options()
        elif command == "/help":
            return self._cmd_help_options()
        elif command == "/status":
            return self._cmd_options_status()
        elif command == "/positions":
            return self._cmd_options_positions()
        elif command == "/pnl":
            return self._cmd_options_pnl()
        elif command == "/expiry":
            return self._cmd_options_expiry()
        else:
            return f"Unknown command: {command}\nUse /help to see available commands."
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _get_snapshot_data(self) -> Optional[Dict]:
        """Get monitoring snapshot data (DRY helper)"""
        snapshot_files = [
            PROJECT_ROOT / "data" / "monitoring_snapshot_BTCUSD_LONG.json",
            PROJECT_ROOT / "data" / "monitoring_snapshot_ETHUSD_LONG.json",
            PROJECT_ROOT / "data" / "monitoring_snapshot.json",
        ]
        
        for sf in snapshot_files:
            if sf.exists():
                try:
                    with open(sf) as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Error reading {sf}: {e}")
                    continue
        return None
    
    # ========================================================================
    # Grid Bot Commands
    # ========================================================================
    
    def _cmd_start_grid(self) -> str:
        """Welcome message for grid bot"""
        return (
            "🤖 *Grid Bot Command Interface*\n\n"
            "Welcome! This bot provides real-time status updates for your grid trading bot.\n\n"
            "Use /help to see available commands."
        )
    
    def _cmd_help_grid(self) -> str:
        """Help message for grid bot"""
        return (
            "📚 *Grid Bot Commands*\n\n"
            "*Status Commands:*\n"
            "/status - Get bot status and current positions\n"
            "/positions - List all open positions\n"
            "/pnl - Get current profit/loss\n"
            "/guardian - Get Guardian risk status\n\n"
            "*Control Commands:*\n"
            "/startbot - Start the grid bot\n"
            "/stopbot - Stop the grid bot (graceful)\n"
            "/killbot - Emergency kill bot\n"
            "/restart - Restart the grid bot\n\n"
            "/help - Show this help message\n\n"
            "⚠️ Control commands require confirmation\n"
            "💡 Commands update in real-time from your trading system."
        )
    
    def _cmd_grid_status(self) -> str:
        """Get grid bot status"""
        try:
            data = self._get_snapshot_data()
            
            if not data:
                return (
                    "⚠️ *Bot Data Not Available*\n\n"
                    "Possible causes:\n"
                    "• Bot is not running\n"
                    "• Snapshot not created yet\n\n"
                    "Try: `/startbot` or wait 30s"
                )
            
            # Extract key info
            mode = data.get("mode", "Unknown")
            symbol = data.get("symbol", "Unknown")
            state = data.get("state", {})
            metrics = data.get("metrics", {})
            positions = state.get("open_tranches", [])
            pending_buy = state.get("pending_buy")
            pending_sell = state.get("pending_sell")
            
            # Get current price from market data
            market = data.get("market", {})
            current_price = market.get("mark_price", 0)
            
            # Calculate total position size
            pos_metrics = metrics.get("positions", {})
            total_size = pos_metrics.get("total_size", 0)
            
            # Format response
            response = (
                f"🤖 *Grid Bot Status*\n\n"
                f"*Mode:* {mode}\n"
                f"*Symbol:* {symbol}\n"
                f"*Current Price:* ${current_price:,.2f}\n\n"
                f"*Positions:*\n"
                f"• Open: {len(positions)}\n"
                f"• Total Size: {total_size} contracts\n\n"
            )
            
            if pending_buy:
                response += f"*Pending BUY:* ${pending_buy.get('price', 0):,.0f}\n"
            if pending_sell:
                response += f"*Pending SELL:* ${pending_sell.get('price', 0):,.0f}\n"
            
            # Add timestamp
            response += f"\n🕐 Updated: {datetime.now().strftime('%H:%M:%S')}"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting grid status: {e}")
            return f"❌ Error getting status: {str(e)}"
    
    def _cmd_grid_positions(self) -> str:
        """List grid bot positions"""
        try:
            data = self._get_snapshot_data()
            
            if not data:
                return "⚠️ No positions found. Bot may not be running."
            
            state = data.get("state", {})
            positions = state.get("open_tranches", [])
            
            if not positions:
                return "📭 No open positions"
            
            response = f"📊 *Open Positions ({len(positions)})*\n\n"
            
            for i, pos in enumerate(positions, 1):
                entry = pos.get("entry_price", 0)
                size = pos.get("size", 0)
                tp = pos.get("tp_price", 0)
                
                response += (
                    f"*Position {i}:*\n"
                    f"• Entry: ${entry:,.0f}\n"
                    f"• Size: {size}\n"
                    f"• TP: ${tp:,.0f}\n\n"
                )
            
            response += f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return f"❌ Error: {str(e)}"
    
    def _cmd_grid_pnl(self) -> str:
        """Get grid bot P&L"""
        try:
            data = self._get_snapshot_data()
            
            if not data:
                return "⚠️ P&L data not available"
            
            # Get P&L metrics
            metrics = data.get("metrics", {})
            pnl_metrics = metrics.get("pnl", {})
            
            realized_pnl = pnl_metrics.get("realized_pnl", 0)
            unrealized_pnl = pnl_metrics.get("unrealized_pnl", 0)
            total_pnl = pnl_metrics.get("total_pnl", realized_pnl + unrealized_pnl)
            
            # Position stats
            pos_metrics = metrics.get("positions", {})
            total_opened = pos_metrics.get("total_opened", 0)
            total_closed = pos_metrics.get("total_closed", 0)
            
            response = (
                f"💰 *Profit & Loss*\n\n"
                f"*Realized P&L:* ${realized_pnl:+,.2f}\n"
                f"*Unrealized P&L:* ${unrealized_pnl:+,.2f}\n"
                f"*Total P&L:* ${total_pnl:+,.2f}\n\n"
                f"*Positions:*\n"
                f"• Opened: {total_opened}\n"
                f"• Closed: {total_closed}\n\n"
                f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting P&L: {e}")
            return f"❌ Error: {str(e)}"
    
    def _cmd_guardian_status(self) -> str:
        """Get Guardian status"""
        try:
            import sqlite3
            
            # Read Guardian signal from event database
            db_files = [
                PROJECT_ROOT / "data" / "bot_events_BTCUSD_LONG.db",
                PROJECT_ROOT / "data" / "bot_events_ETHUSD_LONG.db",
                PROJECT_ROOT / "data" / "bot_events_LONG.db",
            ]
            
            db_file = None
            for df in db_files:
                if df.exists():
                    db_file = df
                    break
            
            if not db_file:
                return "⚠️ Guardian database not found. Bot may not be running."
            
            # Query latest guardian signal using context manager
            with sqlite3.connect(str(db_file)) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT event_type, data, timestamp 
                    FROM events 
                    WHERE event_type IN ('GUARDIAN_SIGNAL_GO', 'GUARDIAN_SIGNAL_STOP')
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
            
            if not row:
                return "⚠️ No Guardian signals found. Guardian may not have run yet."
            
            event_type, data_json, timestamp = row
            signal_data = json.loads(data_json) if data_json else {}
            
            signal = "GO" if "GO" in event_type else "STOP"
            reason = signal_data.get("reason", "No reason provided")
            
            # Format timestamp
            dt = datetime.fromtimestamp(timestamp)
            time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            
            emoji = "🟢" if signal == "GO" else "🔴"
            
            response = (
                f"{emoji} *Guardian Status*\n\n"
                f"*Signal:* {signal}\n"
                f"*Reason:* {reason}\n"
                f"*Last Update:* {time_str}\n\n"
            )
            
            if signal == "STOP":
                response += "⚠️ Trading is currently halted by Guardian\n"
            else:
                response += "✅ Trading is active\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting Guardian status: {e}")
            return f"❌ Error: {str(e)}"
    
    # ========================================================================
    # Grid Bot Control Commands
    # ========================================================================
    
    def _is_bot_running(self) -> Optional[int]:
        """Check if bot is running, return PID if yes"""
        try:
            # Check PID file first (most reliable)
            pid_file = PROJECT_ROOT / "reports" / "bot.pid"
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    os.kill(pid, 0)  # Check if process exists
                    return pid
                except (OSError, ValueError):
                    pass  # PID file is stale
            
            # Try pgrep first (more precise)
            try:
                result = subprocess.run(
                    ['pgrep', '-f', 'bot.run'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    pids = [int(p) for p in result.stdout.strip().split('\n') if p.strip()]
                    if len(pids) > 1:
                        logger.warning(f"⚠️ Multiple bot processes found: {pids}")
                    return pids[0] if pids else None
            except FileNotFoundError:
                # pgrep not available, fallback to ps
                logger.debug("pgrep not available, using ps fallback")
                result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                for line in result.stdout.split('\n'):
                    if 'bot.run' in line and 'grep' not in line:
                        parts = line.split()
                        if len(parts) > 1:
                            return int(parts[1])
            
            return None
        except Exception as e:
            logger.error(f"Error checking bot status: {e}")
            return None
    
    def _cmd_start_bot(self) -> str:
        """Start the grid bot"""
        try:
            # Check if already running
            pid = self._is_bot_running()
            if pid:
                return f"⚠️ Bot is already running (PID: {pid})\n\nUse /stopbot to stop it first."
            
            # Start bot using bot_launcher.py
            bot_launcher = PROJECT_ROOT / "bot_launcher.py"
            
            if not bot_launcher.exists():
                return "❌ bot_launcher.py not found"
            
            result = subprocess.run(
                [sys.executable, str(bot_launcher), '--daemon'],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Wait a moment and verify it started
                time.sleep(2)
                pid = self._is_bot_running()
                
                if pid:
                    return (
                        "✅ *Grid Bot Started Successfully*\n\n"
                        f"🔢 PID: {pid}\n"
                        f"📊 Check /status to verify\n\n"
                        f"🕐 Started: {datetime.now().strftime('%H:%M:%S')}"
                    )
                else:
                    return "⚠️ Bot command executed but process not found. Check logs."
            else:
                error_msg = result.stderr[:500] if result.stderr else "Unknown error"
                return f"❌ Failed to start bot:\n\n{error_msg}"
            
        except subprocess.TimeoutExpired:
            return "⏱️ Start command timed out. Bot may still be starting. Check /status in 30 seconds."
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            return f"❌ Error: {str(e)}"
    
    def _cmd_stop_bot(self) -> str:
        """Stop the grid bot gracefully"""
        try:
            # Check if running
            pid = self._is_bot_running()
            if not pid:
                return "ℹ️ Bot is not running"
            
            # Send SIGTERM for graceful shutdown
            logger.info(f"Sending SIGTERM to bot (PID: {pid})")
            os.kill(pid, signal.SIGTERM)
            
            # Wait up to 30 seconds for graceful shutdown
            for i in range(30):
                time.sleep(1)
                if not self._is_bot_running():
                    return (
                        "✅ *Bot Stopped Successfully*\n\n"
                        f"🔢 PID: {pid}\n"
                        f"⏱️ Shutdown time: {i+1}s\n\n"
                        f"🕐 Stopped: {datetime.now().strftime('%H:%M:%S')}\n\n"
                        "Use /startbot to restart"
                    )
            
            # Still running after 30s
            return (
                "⚠️ Bot did not stop gracefully within 30s.\n\n"
                "Use /killbot for emergency shutdown."
            )
            
        except ProcessLookupError:
            return "ℹ️ Bot process not found (already stopped)"
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
            return f"❌ Error: {str(e)}"
    
    def _cmd_kill_bot(self) -> str:
        """Emergency kill the bot"""
        try:
            # Check if running
            pid = self._is_bot_running()
            if not pid:
                return "ℹ️ Bot is not running"
            
            # Send SIGKILL for immediate termination
            logger.warning(f"Sending SIGKILL to bot (PID: {pid})")
            os.kill(pid, signal.SIGKILL)
            
            time.sleep(2)
            
            if not self._is_bot_running():
                return (
                    "💀 *Bot Killed (Emergency Stop)*\n\n"
                    f"🔢 PID: {pid}\n"
                    f"🕐 Killed: {datetime.now().strftime('%H:%M:%S')}\n\n"
                    "⚠️ This was a forceful shutdown.\n"
                    "Check logs for any issues.\n\n"
                    "Use /startbot to restart"
                )
            else:
                return "❌ Failed to kill bot process"
            
        except ProcessLookupError:
            return "ℹ️ Bot process not found (already stopped)"
        except Exception as e:
            logger.error(f"Error killing bot: {e}")
            return f"❌ Error: {str(e)}"
    
    def _cmd_restart_bot(self) -> str:
        """Restart the grid bot"""
        try:
            # Stop first
            pid = self._is_bot_running()
            if pid:
                logger.info(f"Stopping bot for restart (PID: {pid})")
                os.kill(pid, signal.SIGTERM)
                
                # Wait for shutdown
                for i in range(30):
                    time.sleep(1)
                    if not self._is_bot_running():
                        break
                else:
                    return "❌ Could not stop bot for restart. Use /killbot first."
            
            # Wait a bit before restart
            time.sleep(3)
            
            # Start bot
            bot_launcher = PROJECT_ROOT / "bot_launcher.py"
            result = subprocess.run(
                [sys.executable, str(bot_launcher), '--daemon'],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                time.sleep(2)
                new_pid = self._is_bot_running()
                
                if new_pid:
                    return (
                        "🔄 *Bot Restarted Successfully*\n\n"
                        f"🔢 Old PID: {pid or 'N/A'}\n"
                        f"🔢 New PID: {new_pid}\n\n"
                        f"📊 Check /status to verify\n\n"
                        f"🕐 Restarted: {datetime.now().strftime('%H:%M:%S')}"
                    )
                else:
                    return "⚠️ Restart command executed but bot not found. Check logs."
            else:
                return f"❌ Failed to restart:\n\n{result.stderr[:500]}"
            
        except Exception as e:
            logger.error(f"Error restarting bot: {e}")
            return f"❌ Error: {str(e)}"
    
    # ========================================================================
    # Options Bot Commands
    # ========================================================================
    
    def _cmd_start_options(self) -> str:
        """Welcome message for options bot"""
        return (
            "📈 *Options Trading Command Interface*\n\n"
            "Welcome! This bot provides real-time status for your options positions.\n\n"
            "Use /help to see available commands."
        )
    
    def _cmd_help_options(self) -> str:
        """Help message for options bot"""
        return (
            "📚 *Options Bot Commands*\n\n"
            "/status - Get options portfolio summary\n"
            "/positions - List all options positions\n"
            "/pnl - Get current profit/loss\n"
            "/expiry - Check expiry warnings\n"
            "/help - Show this help message\n\n"
            "💡 Commands query your live trading system."
        )
    
    def _cmd_options_status(self) -> str:
        """Get options portfolio status"""
        try:
            # Call WebUI API
            url = "http://localhost:5555/api/options/positions"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return f"⚠️ Could not fetch positions (WebUI may be offline)"
            
            data = response.json()
            
            if not data.get("success"):
                return "⚠️ Error fetching positions"
            
            positions = data.get("positions", [])
            
            if not positions:
                return "📭 No open options positions"
            
            # Calculate summary
            total_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)
            btc_positions = [p for p in positions if "BTC" in p.get("product_symbol", "")]
            eth_positions = [p for p in positions if "ETH" in p.get("product_symbol", "")]
            
            response_text = (
                f"📈 *Options Portfolio Status*\n\n"
                f"*Total Positions:* {len(positions)}\n"
                f"*Unrealized P&L:* ${total_pnl:+,.2f}\n\n"
                f"*By Underlying:*\n"
                f"• BTC: {len(btc_positions)} positions\n"
                f"• ETH: {len(eth_positions)} positions\n\n"
                f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"Use /positions for detailed list"
            )
            
            return response_text
            
        except requests.exceptions.ConnectionError:
            return "⚠️ WebUI is offline. Cannot fetch positions."
        except Exception as e:
            logger.error(f"Error getting options status: {e}")
            return f"❌ Error: {str(e)}"
    
    def _cmd_options_positions(self) -> str:
        """List all options positions"""
        try:
            url = "http://localhost:5555/api/options/positions"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return "⚠️ Could not fetch positions"
            
            data = response.json()
            positions = data.get("positions", [])
            
            if not positions:
                return "📭 No open options positions"
            
            response_text = f"📊 *Options Positions ({len(positions)})*\n\n"
            
            for i, pos in enumerate(positions[:10], 1):  # Limit to 10 to avoid message length
                symbol = pos.get("product_symbol", "Unknown")
                size = pos.get("size", 0)
                entry = pos.get("entry_price", 0)
                mark = pos.get("mark_price", 0)
                pnl = pos.get("unrealized_pnl", 0)
                pnl_pct = pos.get("pnl_percentage", 0)
                
                # Shorten symbol
                parts = symbol.split("-")
                short_symbol = f"{parts[1] if len(parts) > 1 else ''} {parts[0] if parts else ''}"
                
                response_text += (
                    f"*{i}. {short_symbol}*\n"
                    f"• Size: {size:+d}\n"
                    f"• Entry: ${entry:.2f}\n"
                    f"• Mark: ${mark:.2f}\n"
                    f"• P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)\n\n"
                )
            
            if len(positions) > 10:
                response_text += f"... and {len(positions) - 10} more\n\n"
            
            response_text += f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}"
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return f"❌ Error: {str(e)}"
    
    def _cmd_options_pnl(self) -> str:
        """Get options P&L summary"""
        try:
            url = "http://localhost:5555/api/options/positions"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return "⚠️ Could not fetch P&L"
            
            data = response.json()
            positions = data.get("positions", [])
            
            # Calculate P&L by underlying
            btc_pnl = sum(p.get("unrealized_pnl", 0) for p in positions if "BTC" in p.get("product_symbol", ""))
            eth_pnl = sum(p.get("unrealized_pnl", 0) for p in positions if "ETH" in p.get("product_symbol", ""))
            total_pnl = btc_pnl + eth_pnl
            
            # Count profitable vs losing
            profitable = len([p for p in positions if p.get("unrealized_pnl", 0) > 0])
            losing = len([p for p in positions if p.get("unrealized_pnl", 0) < 0])
            
            response_text = (
                f"💰 *Options P&L Summary*\n\n"
                f"*Total Unrealized:* ${total_pnl:+,.2f}\n\n"
                f"*By Underlying:*\n"
                f"• BTC: ${btc_pnl:+,.2f}\n"
                f"• ETH: ${eth_pnl:+,.2f}\n\n"
                f"*Position Status:*\n"
                f"• Profitable: {profitable}\n"
                f"• Losing: {losing}\n\n"
                f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error getting P&L: {e}")
            return f"❌ Error: {str(e)}"
    
    def _cmd_options_expiry(self) -> str:
        """Check expiry warnings"""
        try:
            url = "http://localhost:5555/api/options/positions"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return "⚠️ Could not fetch positions"
            
            data = response.json()
            positions = data.get("positions", [])
            
            # Filter for expiry warnings
            expiring_soon = []
            for pos in positions:
                warning = pos.get("expiry_warning", {})
                hours = warning.get("hours_until_expiry", 999)
                if hours < 48:  # Show positions expiring within 48h
                    expiring_soon.append((pos, hours))
            
            if not expiring_soon:
                return "✅ No expiry warnings\nAll positions have 48+ hours until expiry"
            
            # Sort by hours remaining
            expiring_soon.sort(key=lambda x: x[1])
            
            response_text = f"⚠️ *Expiry Warnings ({len(expiring_soon)})*\n\n"
            
            for pos, hours in expiring_soon[:10]:
                symbol = pos.get("product_symbol", "Unknown")
                size = pos.get("size", 0)
                pnl = pos.get("unrealized_pnl", 0)
                
                # Format hours
                if hours < 1:
                    time_str = f"{int(hours * 60)}m"
                elif hours < 24:
                    time_str = f"{int(hours)}h"
                else:
                    time_str = f"{int(hours)}h"
                
                emoji = "🔴" if hours < 2 else "⚠️"
                
                response_text += (
                    f"{emoji} *{symbol}*\n"
                    f"• Expires in: {time_str}\n"
                    f"• Size: {size:+d}\n"
                    f"• P&L: ${pnl:+.2f}\n\n"
                )
            
            response_text += f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}"
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error getting expiry warnings: {e}")
            return f"❌ Error: {str(e)}"
    
    # ========================================================================
    # Main Loop
    # ========================================================================
    
    def start(self):
        """Start command handler (blocking)"""
        logger.info(f"🤖 Starting {self.bot_type} bot command handler")
        logger.info(f"📱 Polling for commands...")
        
        self.running = True
        
        while self.running:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    # Update last ID
                    self.last_update_id = update.get("update_id", 0)
                    
                    # Get message
                    message = update.get("message", {})
                    if not message:
                        continue
                    
                    # Get chat ID
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text", "")
                    username = message.get("from", {}).get("username", "unknown")
                    
                    logger.info(f"📩 Command: {text} | From: {username} ({chat_id})")
                    
                    # Handle command
                    response = self.handle_command(message)
                    
                    if response:
                        self.send_message(str(chat_id), response)
                        logger.info(f"📤 Sent response to {chat_id}")
                
                # Small delay to avoid hammering API
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("⚠️ Stopping command handler...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in command loop: {e}")
                time.sleep(5)
    
    def stop(self):
        """Stop command handler and cleanup"""
        logger.info("🛑 Stopping command handler...")
        self.running = False
        # Clear rate limit data
        self.command_timestamps.clear()
        logger.info("✅ Command handler stopped")


def main():
    """Main entry point for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Telegram Bot Command Handler")
    parser.add_argument("--bot", choices=["grid", "options"], required=True,
                       help="Which bot to handle commands for")
    args = parser.parse_args()
    
    # Load config
    cfg = get_config()
    
    # Get appropriate token
    if args.bot == "grid":
        token = cfg.telegram.live_bot_token
        print(f"🤖 Starting Grid Bot command handler")
        print(f"📱 Bot: @BTCSSR_bot")
    else:
        token = cfg.telegram.options_bot_token if hasattr(cfg.telegram, 'options_bot_token') else None
        if not token:
            print("❌ Options bot token not configured")
            return 1
        print(f"📈 Starting Options Bot command handler")
    
    print(f"🔑 Token: {token[:20]}...")
    print(f"⏳ Polling for commands... (Ctrl+C to stop)")
    print()
    
    # Start handler
    handler = TelegramBotCommandHandler(token, bot_type=args.bot)
    
    try:
        handler.start()
    except KeyboardInterrupt:
        print("\n⚠️ Stopping...")
        handler.stop()
    
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    sys.exit(main())
