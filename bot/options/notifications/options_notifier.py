"""
Options Telegram Notifier
Sends notifications for options trading events to a separate Telegram bot

Created: January 19, 2026
Purpose: Implement options-specific Telegram notifications
"""

import os
import sys
import time
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from collections import deque

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

log = logging.getLogger(__name__)


class OptionsNotifier:
    """
    Telegram notifier specifically for options trading.
    Uses separate bot token from grid bot notifications.
    """

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        # Determine mode from YAML config
        cfg = get_config()
        trading_mode = cfg.trading_mode.lower().strip()
        self.is_live = (trading_mode == "live")
        self.mode_prefix = "[LIVE]" if self.is_live else "[DEMO]"
        
        # Use provided credentials or load from config
        self.enabled = False
        self.token = None
        self.chat_id = None
        
        try:
            if token and chat_id:
                # Explicit override (for options bot)
                self.token = token
                self.chat_id = chat_id
                self.enabled = True
            elif hasattr(cfg, 'telegram') and cfg.telegram:
                # Fallback to main telegram config
                if self.is_live:
                    self.token = cfg.telegram.live_bot_token.strip()
                    self.chat_id = cfg.telegram.live_chat_id.strip()
                else:
                    self.token = cfg.telegram.demo_bot_token.strip()
                    self.chat_id = cfg.telegram.demo_chat_id.strip()
                self.enabled = cfg.telegram.enabled
        except AttributeError:
            log.warning("options_notifier: telegram config not found")
            self.enabled = False

        if self.token and self.chat_id and self.enabled:
            log.info(f"options_notifier: {self.mode_prefix} routing enabled")
        else:
            self.enabled = False
            if not (self.token and self.chat_id):
                log.warning(f"options_notifier: disabled (missing credentials)")
        
        # Deduplication cache
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
                log.debug(f"options_notifier: dedup skip")
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
        
        # Check deduplication
        if not skip_dedup and not self._should_send(prefixed_text):
            return
        
        try:
            import urllib.request
            import urllib.parse
            
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
                            log.warning("options_notifier: http %s", r.status)
                except Exception as e:
                    if attempt == 1:
                        raise
                    time.sleep(1.0)
        except Exception as e:
            log.warning("options_notifier: send failed: %s", e)

    # ========================================================================
    # Position Notifications
    # ========================================================================

    def notify_position_opened(self, position: Dict[str, Any], fill_price: float, 
                              size: int, side: str, order_type: str = "market"):
        """Notify when options position is opened"""
        symbol = position.get('product_symbol', 'Unknown')
        greeks = position.get('greeks', {})
        
        # Parse symbol for display (e.g., C-BTC-113000-300126)
        parts = symbol.split('-')
        option_type = parts[0] if len(parts) > 0 else 'Unknown'
        underlying = parts[1] if len(parts) > 1 else 'Unknown'
        strike = parts[2] if len(parts) > 2 else '0'
        expiry = parts[3] if len(parts) > 3 else 'Unknown'
        
        # Format expiry date
        try:
            from datetime import datetime
            exp_dt = datetime.strptime(expiry, '%d%m%y')
            expiry_fmt = exp_dt.strftime('%b %d, %Y')
        except:
            expiry_fmt = expiry
        
        total_cost = fill_price * abs(size)
        
        message = (
            f"📥 OPTIONS POSITION OPENED\n\n"
            f"Symbol: {symbol}\n"
            f"Type: {underlying} {'CALL' if option_type == 'C' else 'PUT'}\n"
            f"Strike: ${strike}\n"
            f"Expiry: {expiry_fmt}\n\n"
            f"Trade Details:\n"
            f"• Side: {side.upper()}\n"
            f"• Size: {abs(size)} contracts\n"
            f"• Entry Price: ${fill_price:.2f}\n"
            f"• Total Cost: ${total_cost:.2f}\n"
            f"• Order Type: {order_type}\n"
        )
        
        if greeks:
            message += (
                f"\nGreeks:\n"
                f"• Delta: {greeks.get('delta', 0):+.2f}\n"
                f"• Gamma: {greeks.get('gamma', 0):.3f}\n"
                f"• Vega: {greeks.get('vega', 0):.1f}\n"
                f"• Theta: {greeks.get('theta', 0):+.1f}\n"
            )
        
        # Calculate DTE if available
        try:
            from datetime import datetime
            exp_dt = datetime.strptime(expiry, '%d%m%y')
            dte = (exp_dt - datetime.now()).days
            message += f"\nDays to Expiry: {dte} days"
        except:
            pass
        
        self.send(message)

    def notify_position_added(self, symbol: str, added_size: int, fill_price: float,
                            old_size: int, new_size: int, avg_entry: float, 
                            current_pnl: float, pnl_pct: float, order_type: str = "market"):
        """Notify when size is added to position"""
        total_cost = fill_price * abs(added_size)
        
        message = (
            f"➕ POSITION SIZE INCREASED\n\n"
            f"Symbol: {symbol}\n"
            f"Action: {'SELL' if added_size < 0 else 'BUY'} additional contracts\n\n"
            f"Trade Details:\n"
            f"• Added Size: {abs(added_size)} contracts\n"
            f"• Fill Price: ${fill_price:.2f}\n"
            f"• Total Cost: ${total_cost:.2f}\n\n"
            f"Position Summary:\n"
            f"• Previous Size: {old_size}\n"
            f"• New Size: {new_size}\n"
            f"• Avg Entry: ${avg_entry:.2f}\n"
            f"• Current P&L: ${current_pnl:.2f} ({pnl_pct:+.2f}%)\n\n"
            f"Order Type: {order_type}"
        )
        
        self.send(message)

    def notify_position_closed(self, symbol: str, entry_price: float, exit_price: float,
                             size: int, pnl: float, pnl_pct: float, hold_time: str,
                             side: str, order_type: str, greeks: Dict = None, 
                             spot_price: float = 0):
        """Notify when position is closed"""
        message = (
            f"💰 OPTIONS POSITION CLOSED\n\n"
            f"Symbol: {symbol}\n"
            f"Type: {symbol.split('-')[1] if '-' in symbol else 'Unknown'} "
            f"{'CALL' if symbol.startswith('C-') else 'PUT'} "
            f"${symbol.split('-')[2] if len(symbol.split('-')) > 2 else '0'}\n\n"
            f"Trade Performance:\n"
            f"• Entry Price: ${entry_price:.2f}\n"
            f"• Exit Price: ${exit_price:.2f}\n"
            f"• Size: {abs(size)} contracts\n"
            f"• {'Profit' if pnl > 0 else 'Loss'}: ${pnl:+.2f} ({pnl_pct:+.2f}%)\n"
            f"• Hold Time: {hold_time}\n\n"
            f"Execution:\n"
            f"• Close Side: {side.upper()}\n"
            f"• Order Type: {order_type}\n"
            f"• Fill Price: ${exit_price:.2f}\n"
        )
        
        if greeks:
            message += (
                f"\nGreeks at Close:\n"
                f"• Delta: {greeks.get('delta', 0):+.2f}\n"
            )
        
        if spot_price > 0:
            message += f"• Spot Price: ${spot_price:,.0f}\n"
        
        self.send(message)

    # ========================================================================
    # P&L Notifications
    # ========================================================================

    def notify_take_profit(self, symbol: str, target_pct: float, actual_pct: float,
                          entry: float, current: float, profit: float, size: int,
                          fill_price: float, final_profit: float, final_pct: float):
        """Notify when take profit target is hit"""
        message = (
            f"🎯 TAKE PROFIT TARGET HIT\n\n"
            f"Symbol: {symbol}\n"
            f"Target: +{target_pct:.2f}%\n"
            f"Actual: +{actual_pct:.2f}%\n\n"
            f"Position Details:\n"
            f"• Entry: ${entry:.2f}\n"
            f"• Current: ${current:.2f}\n"
            f"• Profit: ${profit:.2f}\n"
            f"• Size: {abs(size)} contracts\n\n"
            f"Action: Position auto-closed\n"
            f"Execution: Market order filled @ ${fill_price:.2f}\n"
            f"Final Profit: ${final_profit:+.2f} (+{final_pct:.2f}%)"
        )
        
        self.send(message)

    def notify_stop_loss(self, symbol: str, limit_pct: float, actual_pct: float,
                        entry: float, current: float, loss: float, size: int,
                        fill_price: float, final_loss: float, final_pct: float):
        """Notify when stop loss is triggered"""
        message = (
            f"🛑 STOP LOSS TRIGGERED\n\n"
            f"Symbol: {symbol}\n"
            f"Limit: {limit_pct:.2f}%\n"
            f"Actual: {actual_pct:.2f}%\n\n"
            f"Position Details:\n"
            f"• Entry: ${entry:.2f}\n"
            f"• Current: ${current:.2f}\n"
            f"• Loss: ${loss:.2f}\n"
            f"• Size: {abs(size)} contracts\n\n"
            f"Action: Position auto-closed\n"
            f"Execution: Market order filled @ ${fill_price:.2f}\n"
            f"Final Loss: ${final_loss:.2f} ({final_pct:.2f}%)\n\n"
            f"Risk Protection: Activated"
        )
        
        self.send(message)

    def notify_max_loss_breach(self, symbol: str, max_loss: float, actual_loss: float,
                              entry: float, current: float, size: int, loss_pct: float):
        """Notify when max loss per position is breached"""
        message = (
            f"🚨 MAX LOSS BREACH\n\n"
            f"Symbol: {symbol}\n"
            f"Max Loss: ${max_loss:.2f} per position\n"
            f"Current Loss: ${actual_loss:.2f}\n\n"
            f"Position:\n"
            f"• Entry: ${entry:.2f}\n"
            f"• Current: ${current:.2f}\n"
            f"• Size: {abs(size)} contracts\n"
            f"• Loss %: {loss_pct:.2f}%\n\n"
            f"Action: EMERGENCY CLOSE initiated\n"
            f"Execution: Market order placed\n"
            f"Status: Awaiting fill confirmation"
        )
        
        self.send(message)

    # ========================================================================
    # Expiry Notifications
    # ========================================================================

    def notify_expiry_warning(self, symbol: str, hours_remaining: float,
                            expiry_str: str, size: int, pnl: float, pnl_pct: float,
                            in_the_money: bool, intrinsic_value: float):
        """Notify 24h before expiry"""
        message = (
            f"⚠️ OPTIONS EXPIRY WARNING\n\n"
            f"Symbol: {symbol}\n"
            f"Time to Expiry: {int(hours_remaining)}h {int((hours_remaining % 1) * 60)}m\n"
            f"Expiry: {expiry_str}\n\n"
            f"Position Status:\n"
            f"• Size: {abs(size)} contracts\n"
            f"• Current P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%)\n"
            f"• In-the-Money: {'YES' if in_the_money else 'NO'}\n"
        )
        
        if intrinsic_value > 0:
            message += f"• Intrinsic Value: ${intrinsic_value:,.0f}\n"
        
        message += (
            f"\nRecommendation:\n"
            f"Close before expiry if profit target met\n"
            f"Auto-close: 1 hour before expiry"
        )
        
        self.send(message)

    def notify_critical_expiry(self, symbol: str, minutes_remaining: int,
                              size: int, pnl: float, pnl_pct: float,
                              spot_price: float, strike: float, out_of_money: bool):
        """Critical alert 1h before expiry"""
        message = (
            f"🔴 CRITICAL EXPIRY ALERT\n\n"
            f"Symbol: {symbol}\n"
            f"Time to Expiry: {minutes_remaining} minutes\n"
            f"URGENT ACTION REQUIRED\n\n"
            f"Position:\n"
            f"• Size: {abs(size)} contracts\n"
            f"• Current P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%)\n"
            f"• Spot Price: ${spot_price:,.0f}\n"
            f"• Strike: ${strike:,.0f}\n"
            f"• Status: {'Out-of-the-Money' if out_of_money else 'In-the-Money'}\n\n"
        )
        
        if out_of_money:
            message += (
                f"WARNING: Position will expire worthless\n"
                f"Action: Auto-close in 10 minutes\n"
                f"Recommended: Close immediately"
            )
        else:
            message += (
                f"Action: Will exercise at expiry\n"
                f"Recommended: Close to lock profit"
            )
        
        self.send(message)

    def notify_auto_close_expiry(self, symbol: str, minutes_remaining: int,
                                side: str, size: int, fill_price: float,
                                entry: float, pnl: float, pnl_pct: float):
        """Notify when position auto-closed before expiry"""
        message = (
            f"🕐 AUTO-CLOSE: EXPIRY PROTECTION\n\n"
            f"Symbol: {symbol}\n"
            f"Reason: Approaching expiry ({minutes_remaining}m remaining)\n\n"
            f"Execution:\n"
            f"• Side: {side.upper()} to close\n"
            f"• Size: {abs(size)} contracts\n"
            f"• Fill Price: ${fill_price:.2f}\n"
            f"• Order Type: Market\n\n"
            f"Result:\n"
            f"• Entry: ${entry:.2f}\n"
            f"• Exit: ${fill_price:.2f}\n"
            f"• {'Profit' if pnl > 0 else 'Loss'}: ${pnl:+.2f} ({pnl_pct:+.2f}%)\n\n"
            f"Protection: {'Prevented total loss' if pnl < 0 else 'Profit locked in'}"
        )
        
        self.send(message)

    # ========================================================================
    # Risk & System Notifications
    # ========================================================================

    def notify_liquidity_warning(self, symbol: str, spread_pct: float, 
                                best_bid: float, best_ask: float, mid_price: float,
                                volume: int, size: int, entry: float, 
                                current_loss: float, loss_pct: float):
        """Warn about low liquidity"""
        message = (
            f"⚠️ LIQUIDITY WARNING\n\n"
            f"Symbol: {symbol}\n"
            f"Spread: {spread_pct:.1f}% (wide)\n\n"
            f"Market Data:\n"
            f"• Best Bid: ${best_bid:.2f}\n"
            f"• Best Ask: ${best_ask:.2f}\n"
            f"• Mid Price: ${mid_price:.2f}\n"
            f"• Volume: {volume} contracts (low)\n\n"
            f"Warning:\n"
            f"• Difficult to exit\n"
            f"• Slippage risk high\n"
            f"• Consider closing with limit order\n\n"
            f"Position: {size} contracts @ ${entry:.2f}\n"
            f"Current Loss: ${current_loss:.2f} ({loss_pct:.2f}%)"
        )
        
        self.send(message)

    def notify_guardian_block(self, reason: str, total_exposure: float, risk_limit: float):
        """Notify when Guardian blocks options trading"""
        message = (
            f"🔴 GUARDIAN: OPTIONS TRADING HALTED\n\n"
            f"Reason: {reason}\n"
            f"Total Options Exposure: ${total_exposure:,.0f}\n"
            f"Risk Limit: ${risk_limit:,.0f}\n\n"
            f"Status: New orders blocked\n"
            f"Existing Positions: Maintained\n"
            f"Action: Close positions or wait for limit reset\n\n"
            f"Guardian Status: STOP\n"
            f"Resume: When exposure < ${risk_limit * 0.9:,.0f}"
        )
        
        self.send(message)

    def notify_order_timeout(self, symbol: str, order_type: str, limit_price: float,
                           placed_minutes_ago: int, market_price: float):
        """Notify when order times out"""
        message = (
            f"⏱️ ORDER TIMEOUT\n\n"
            f"Symbol: {symbol}\n"
            f"Order Type: {order_type}\n"
            f"Limit Price: ${limit_price:.2f}\n\n"
            f"Status:\n"
            f"• Placed: {placed_minutes_ago} minutes ago\n"
            f"• Filled: 0 contracts\n"
            f"• Market Price: ${market_price:.2f} (moved away)\n\n"
            f"Action: Order cancelled\n"
            f"Recommendation: Use market order or adjust price"
        )
        
        self.send(message)


# Singleton instance for options notifications
# Configure with your options bot token
_options_notifier = None

def get_options_notifier(token: Optional[str] = None, chat_id: Optional[str] = None) -> OptionsNotifier:
    """Get singleton options notifier instance"""
    global _options_notifier
    if _options_notifier is None:
        _options_notifier = OptionsNotifier(token=token, chat_id=chat_id)
    return _options_notifier
