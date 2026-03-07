"""
Risk Enforcer - Checks risk thresholds and triggers actions

Enhanced with Hysteresis to prevent alert spam when PnL oscillates.

Hysteresis prevents alert flapping:
- Trigger: Alert when loss reaches threshold (e.g., 80%)
- Reset: Stop alerting when loss drops below reset point (e.g., 75%)
- Gap: Buffer prevents oscillation alerts

Example:
    Loss reaches 80% → Alert sent
    Loss oscillates 79-81% → No more alerts (still above 75% reset)
    Loss drops to 74% → Alert cleared
    Loss rises to 80% again → New alert sent
"""
import logging
from typing import Dict, Optional, Tuple


logger = logging.getLogger(__name__)


class RiskEnforcer:
    """
    Enforces risk limits and determines when to take action.
    
    Uses hysteresis to prevent alert spam during PnL oscillations.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize risk enforcer with hysteresis.
        
        Args:
            config: Guardian configuration
        """
        self.config = config
        self.max_account_loss_inr = float(config.get('GUARDIAN_MAX_ACCOUNT_LOSS_INR', 5000))
        self.alert_threshold_80 = config.get('GUARDIAN_ALERT_THRESHOLD_80', 'true').lower() == 'true'
        self.alert_threshold_90 = config.get('GUARDIAN_ALERT_THRESHOLD_90', 'true').lower() == 'true'
        
        # Hysteresis configuration (trigger → reset points)
        # Format: {threshold: {'trigger': X, 'reset': Y}}
        self.hysteresis_config = {
            80: {
                'trigger': float(config.get('GUARDIAN_HYSTERESIS_80_TRIGGER', '80')),
                'reset': float(config.get('GUARDIAN_HYSTERESIS_80_RESET', '75'))
            },
            90: {
                'trigger': float(config.get('GUARDIAN_HYSTERESIS_90_TRIGGER', '90')),
                'reset': float(config.get('GUARDIAN_HYSTERESIS_90_RESET', '85'))
            },
            100: {
                'trigger': float(config.get('GUARDIAN_HYSTERESIS_100_TRIGGER', '100')),
                'reset': float(config.get('GUARDIAN_HYSTERESIS_100_RESET', '95'))
            }
        }
        
        # Track if we're currently alerting at these thresholds
        self.alerted_80 = False
        self.alerted_90 = False
        self.emergency_triggered = False
        
        logger.info("=" * 70)
        logger.info("🛡️  RISK ENFORCER WITH HYSTERESIS")
        logger.info("=" * 70)
        logger.info(f"Max Account Loss: ₹{self.max_account_loss_inr:,.2f}")
        logger.info(f"Alert at 80%: {self.alert_threshold_80}")
        logger.info(f"Alert at 90%: {self.alert_threshold_90}")
        logger.info("")
        logger.info("Hysteresis Configuration:")
        for level, config in self.hysteresis_config.items():
            logger.info(
                f"  {level}%: Trigger at {config['trigger']}%, "
                f"Reset at {config['reset']}% "
                f"(buffer: {config['trigger'] - config['reset']}%)"
            )
        logger.info("=" * 70)
    
    def check_loss_threshold(self, total_loss_inr: float) -> Tuple[str, bool, Optional[str]]:
        """
        Check if loss has exceeded thresholds (with hysteresis).
        
        Hysteresis prevents alert spam:
        - Alert triggers at threshold (e.g., 80%)
        - Alert clears at reset point (e.g., 75%)
        - Buffer prevents oscillation alerts
        
        Args:
            total_loss_inr: Total loss in INR
            
        Returns:
            Tuple of (risk_level, should_take_action, alert_message)
            risk_level: 'safe', 'warning_80', 'warning_90', 'emergency'
            should_take_action: True if emergency action needed
            alert_message: Message to send to Telegram (or None)
        """
        loss_percentage = (total_loss_inr / self.max_account_loss_inr) * 100 if self.max_account_loss_inr > 0 else 0
        
        # Get hysteresis thresholds
        h80 = self.hysteresis_config[80]
        h90 = self.hysteresis_config[90]
        h100 = self.hysteresis_config[100]
        
        # Emergency: Loss >= 100% trigger
        if loss_percentage >= h100['trigger']:
            if not self.emergency_triggered:
                self.emergency_triggered = True
                alert_msg = (
                    f"🚨 EMERGENCY! LOSS LIMIT BREACHED!\n\n"
                    f"Total Loss: ₹{total_loss_inr:,.2f}\n"
                    f"Max Limit: ₹{self.max_account_loss_inr:,.2f}\n"
                    f"Usage: {loss_percentage:.1f}%\n\n"
                    f"⚠️ CLOSING ALL POSITIONS IMMEDIATELY!"
                )
                logger.critical(f"🚨 EMERGENCY! Loss: ₹{total_loss_inr:.2f} >= ₹{self.max_account_loss_inr:.2f}")
                return ('emergency', True, alert_msg)
            else:
                # Already triggered, don't spam
                return ('emergency', False, None)
        
        # Check if emergency should be reset (hysteresis)
        elif loss_percentage < h100['reset'] and self.emergency_triggered:
            logger.info(f"✅ Loss recovered below {h100['reset']}% - emergency cleared")
            self.emergency_triggered = False
        
        # Warning 90%: Loss >= 90% trigger
        if loss_percentage >= h90['trigger'] and self.alert_threshold_90:
            if not self.alerted_90:
                self.alerted_90 = True
                alert_msg = (
                    f"🚨 WARNING! Loss at 90% of limit!\n\n"
                    f"Total Loss: ₹{total_loss_inr:,.2f}\n"
                    f"Max Limit: ₹{self.max_account_loss_inr:,.2f}\n"
                    f"Usage: {loss_percentage:.1f}%\n\n"
                    f"⚠️ Approaching emergency threshold!"
                )
                logger.warning(f"⚠️ Total Loss: ₹{total_loss_inr:.2f} ({loss_percentage:.1f}% of limit)")
                return ('warning_90', False, alert_msg)
            else:
                # Still alerting, no new message
                return ('warning_90', False, None)
        
        # Check if 90% alert should be reset (hysteresis)
        elif loss_percentage < h90['reset'] and self.alerted_90:
            logger.info(f"✅ Loss recovered below {h90['reset']}% - 90% alert cleared")
            self.alerted_90 = False
        
        # Warning 80%: Loss >= 80% trigger
        if loss_percentage >= h80['trigger'] and self.alert_threshold_80:
            if not self.alerted_80:
                self.alerted_80 = True
                alert_msg = (
                    f"⚠️ Warning: Loss at 80% of limit\n\n"
                    f"Total Loss: ₹{total_loss_inr:,.2f}\n"
                    f"Max Limit: ₹{self.max_account_loss_inr:,.2f}\n"
                    f"Usage: {loss_percentage:.1f}%\n\n"
                    f"Monitor positions closely."
                )
                logger.warning(f"⚠️ Total Loss: ₹{total_loss_inr:.2f} ({loss_percentage:.1f}% of limit)")
                return ('warning_80', False, alert_msg)
            else:
                # Still alerting, no new message
                return ('warning_80', False, None)
        
        # Check if 80% alert should be reset (hysteresis)
        elif loss_percentage < h80['reset'] and self.alerted_80:
            logger.info(f"✅ Loss recovered below {h80['reset']}% - 80% alert cleared")
            self.alerted_80 = False
        
        # Safe - no alerts
        logger.debug(f"✅ Risk: SAFE | Loss: ₹{total_loss_inr:.2f} ({loss_percentage:.1f}% of limit)")
        return ('safe', False, None)
    
    def reset_alerts(self):
        """Reset alert flags (e.g., after positions closed)"""
        self.alerted_80 = False
        self.alerted_90 = False
        logger.info("Alert flags reset")
    
    def reset_emergency(self):
        """Reset emergency flag (e.g., after manual intervention)"""
        self.emergency_triggered = False
        logger.info("Emergency flag reset")
    
    def check_equity_floor(self, current_equity_inr: float) -> Tuple[bool, Optional[str]]:
        """
        Check if current equity has breached the hard floor.
        
        This is a CRITICAL safety check that prevents catastrophic account drain.
        When breached, the bot immediately stops all new trading.
        
        Args:
            current_equity_inr: Current total account equity in INR
            
        Returns:
            Tuple of (breached: bool, message: Optional[str])
            - breached=True means equity < floor, trading must stop
            - message contains alert details if breached
        """
        equity_floor = float(self.config.get('EQUITY_FLOOR_INR', '0'))
        
        # If not configured or disabled, no floor check
        if equity_floor <= 0:
            return False, None
        
        # Check if current equity is below floor
        if current_equity_inr < equity_floor:
            breach_amount = equity_floor - current_equity_inr
            breach_pct = (breach_amount / equity_floor) * 100
            
            message = (
                f"🚨 EQUITY FLOOR BREACHED! 🚨\n\n"
                f"Current Equity: ₹{current_equity_inr:,.2f}\n"
                f"Equity Floor: ₹{equity_floor:,.2f}\n"
                f"Below Floor: ₹{breach_amount:,.2f} ({breach_pct:.1f}%)\n\n"
                f"IMMEDIATE ACTIONS TAKEN:\n"
                f"• All new trading STOPPED\n"
                f"• Non-reduce orders will be cancelled\n"
                f"• TP orders remain active\n"
                f"• Emergency flag created\n\n"
                f"MANUAL INTERVENTION REQUIRED:\n"
                f"Review account status and create acknowledgment file:\n"
                f"  touch .operator_ack_equity_floor\n\n"
                f"⚠️ DO NOT RESUME TRADING WITHOUT REVIEWING SITUATION"
            )
            
            logger.critical("=" * 70)
            logger.critical("🚨 EQUITY FLOOR BREACHED")
            logger.critical("=" * 70)
            logger.critical(f"Current Equity: ₹{current_equity_inr:,.2f}")
            logger.critical(f"Equity Floor: ₹{equity_floor:,.2f}")
            logger.critical(f"Breach Amount: ₹{breach_amount:,.2f}")
            logger.critical("=" * 70)
            
            return True, message
        
        return False, None
    
    def get_status(self) -> Dict:
        """
        Get current enforcer status
        
        Returns:
            Dictionary with status information
        """
        return {
            'max_account_loss_inr': self.max_account_loss_inr,
            'alerted_80': self.alerted_80,
            'alerted_90': self.alerted_90,
            'emergency_triggered': self.emergency_triggered,
            'equity_floor_inr': float(self.config.get('EQUITY_FLOOR_INR', '0')),
        }

