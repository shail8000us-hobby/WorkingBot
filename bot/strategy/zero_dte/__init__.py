"""
Zero DTE Options Trading Bot
============================

Autonomous 0DTE strangle selling strategy with premium balancing.

Strategy Logic:
1. Sell 5-lot strangle (CE + PE) at market open
2. Continuously rebalance when premium imbalance > 20%
3. Roll strikes when any leg premium < ₹5
4. Exit when BOTH legs < ₹5 OR at 5:15 PM IST

Delta Exchange India Settlement: 5:30 PM IST
"""

from .engine import ZeroDTEEngine
from .balancer import PremiumBalancer
from .rollover import StrikeRolloverManager
from .state_manager import StateManager
from .monitor import ZeroDTEMonitor
from .config import load_config

__all__ = [
    'ZeroDTEEngine',
    'PremiumBalancer', 
    'StrikeRolloverManager',
    'StateManager',
    'ZeroDTEMonitor',
    'load_config'
]

__version__ = '1.0.0'
