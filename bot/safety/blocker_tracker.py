"""
Blocker Tracker - Centralized system to detect and report all trading blockers

This module checks ALL safety systems and returns a comprehensive list of
active blockers preventing new positions from being opened.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.loader import get_config
from bot.state.store import load_state_file

# Config file reference (for compatibility)
CONFIG_FILE = project_root / 'config.yaml'


class BlockerTracker:
    """
    Centralized blocker detection and reporting system.
    Checks all safety features and returns detailed blocker information.
    """
    
    def __init__(self):
        self.workspace_root = Path(__file__).parent.parent.parent
        self.config_file = self.workspace_root / 'config.yaml'
        
        # Load YAML configuration
        self.yaml_config = get_config()
        self.state_file = self.workspace_root / 'state.json'
        self.positions_file = self.workspace_root / 'positions.json'
        
    def check_all_blockers(self) -> Dict[str, Any]:
        """
        Check ALL safety systems and return comprehensive blocker status.
        
        Returns:
            dict: {
                'trading_allowed': bool,
                'total_blockers': int,
                'blockers': List[dict],
                'timestamp': str
            }
        """
        blockers = []
        
        # Check each safety system
        blockers.extend(self._check_safety_gatekeeper())
        blockers.extend(self._check_capital_protection())
        # Volatility, liquidation, loss limit checks REMOVED - Guardian monitors these
        # blocker_tracker now only checks gatekeeper config and Guardian signal
        blockers.extend(self._check_guardian_signal())
        blockers.extend(self._check_order_confirmation_guard())
        blockers.extend(self._check_circuit_breaker())
        blockers.extend(self._check_process_health())
        
        active_blockers = [b for b in blockers if b['active']]
        
        return {
            'trading_allowed': len(active_blockers) == 0,
            'total_blockers': len(active_blockers),
            'blockers': blockers,
            'timestamp': datetime.now().isoformat()
        }
    
    def _check_safety_gatekeeper(self) -> List[Dict]:
        """Check Safety Gatekeeper blockers"""
        blockers = []
        
        # Check actual gatekeeper status by calling it directly
        try:
            from bot.safety.gatekeeper import can_place_orders, get_gatekeeper_stats
            
            # Test gatekeeper with a dummy context
            can_trade = can_place_orders({'origin': 'blocker_tracker_test'})
            gatekeeper_stats = get_gatekeeper_stats()
            
            if not can_trade:
                # Gatekeeper is blocking - get the reason
                last_block_reason = gatekeeper_stats.get('last_block_reason', 'unknown')
                block_count = gatekeeper_stats.get('block_count', 0)
                check_count = gatekeeper_stats.get('check_count', 0)
                
                # Determine the specific blocker based on the reason
                if last_block_reason == 'execute_orders_disabled':
                    blockers.append({
                        'id': 'gatekeeper_execute_orders',
                        'category': 'SAFETY_GATEKEEPER',
                        'name': 'Execute Orders Disabled',
                        'severity': 'critical',
                        'active': True,
                        'message': 'EXECUTE_ORDERS is not enabled',
                        'details': {
                            'current_value': str(self.yaml_config.execution_safety.execute_orders),
                            'required_value': 'true',
                            'config_key': 'execution_safety.execute_orders',
                            'block_reason': last_block_reason,
                            'block_count': block_count,
                            'check_count': check_count
                        },
                        'actions': ['enable_execute_orders', 'view_config'],
                        'deep_link': {
                            'tab': 'configuration',
                            'section': 'trading_controls',
                            'field': 'EXECUTE_ORDERS'
                        }
                    })
                elif last_block_reason == 'live_not_acknowledged':
                    blockers.append({
                        'id': 'gatekeeper_understand_live',
                        'category': 'SAFETY_GATEKEEPER',
                        'name': 'Live Trading Not Acknowledged',
                        'severity': 'critical',
                        'active': True,
                        'message': 'I_UNDERSTAND_LIVE must be YES for live trading',
                        'details': {
                            'current_value': self.yaml_config.execution_safety.i_understand_live,
                            'required_value': 'YES',
                            'trading_mode': self.yaml_config.trading_mode,
                            'config_key': 'execution_safety.i_understand_live',
                            'block_reason': last_block_reason
                        },
                        'actions': ['acknowledge_live', 'switch_to_demo'],
                        'deep_link': {
                            'tab': 'configuration',
                            'section': 'trading_controls',
                            'field': 'I_UNDERSTAND_LIVE'
                        }
                    })
                elif last_block_reason == 'emergency_flag' or 'emergency_flag' in last_block_reason:
                    blockers.append({
                        'id': 'gatekeeper_emergency_flag',
                        'category': 'SAFETY_GATEKEEPER',
                        'name': 'Emergency Stop Flag Active',
                        'severity': 'critical',
                        'active': True,
                        'message': 'Emergency stop flag exists - all trading blocked',
                        'details': {
                            'block_reason': last_block_reason,
                            'flag_location': '.guardian_emergency_stop',
                            'block_count': block_count
                        },
                        'actions': ['investigate_emergency', 'remove_flag'],
                        'deep_link': {
                            'tab': 'emergency_controls',
                            'section': 'emergency_status'
                        }
                    })
                elif 'volatility:' in last_block_reason:
                    blockers.append({
                        'id': 'gatekeeper_volatility',
                        'category': 'SAFETY_GATEKEEPER',
                        'name': 'Volatility Limits Exceeded',
                        'severity': 'warning',
                        'active': True,
                        'message': f'Market volatility too high: {last_block_reason.replace("volatility: ", "")}',
                        'details': {
                            'block_reason': last_block_reason,
                            'volatility_reason': last_block_reason.replace('volatility: ', ''),
                            'block_count': block_count
                        },
                        'actions': ['wait_for_volatility', 'adjust_limits'],
                        'deep_link': {
                            'tab': 'risk_management',
                            'section': 'volatility_status'
                        }
                    })
                elif 'margin_utilization:' in last_block_reason:
                    blockers.append({
                        'id': 'gatekeeper_margin_utilization',
                        'category': 'SAFETY_GATEKEEPER',
                        'name': 'Margin Utilization Too High',
                        'severity': 'critical',
                        'active': True,
                        'message': f'Margin utilization exceeded limits: {last_block_reason.replace("margin_utilization: ", "")}',
                        'details': {
                            'block_reason': last_block_reason,
                            'margin_details': last_block_reason.replace('margin_utilization: ', ''),
                            'block_count': block_count
                        },
                        'actions': ['reduce_positions', 'add_margin'],
                        'deep_link': {
                            'tab': 'liquidation_monitor',
                            'section': 'margin_status'
                        }
                    })
                elif 'confirmation:' in last_block_reason:
                    blockers.append({
                        'id': 'gatekeeper_confirmation',
                        'category': 'SAFETY_GATEKEEPER',
                        'name': 'Waiting for Order Confirmation',
                        'severity': 'warning',
                        'active': True,
                        'message': f'Cannot place new orders: {last_block_reason.replace("confirmation: ", "")}',
                        'details': {
                            'block_reason': last_block_reason,
                            'confirmation_reason': last_block_reason.replace('confirmation: ', ''),
                            'block_count': block_count
                        },
                        'actions': ['wait_for_confirmation'],
                        'deep_link': {
                            'tab': 'monitoring',
                            'section': 'order_status'
                        }
                    })
                else:
                    # Generic gatekeeper block
                    blockers.append({
                        'id': 'gatekeeper_generic',
                        'category': 'SAFETY_GATEKEEPER',
                        'name': 'Safety Gatekeeper Blocked Trading',
                        'severity': 'critical',
                        'active': True,
                        'message': f'Safety gatekeeper is blocking trades (reason: {last_block_reason})',
                        'details': {
                            'block_reason': last_block_reason,
                            'block_count': block_count,
                            'check_count': check_count
                        },
                        'actions': ['investigate_gatekeeper'],
                        'deep_link': {
                            'tab': 'monitoring',
                            'section': 'gatekeeper_status'
                        }
                    })
            
        except Exception as e:
            # Fallback to old method if gatekeeper import fails
            pass
        
        # Fallback: Check EXECUTE_ORDERS manually if gatekeeper check failed
        if not blockers:
            execute_orders = self.yaml_config.execution_safety.execute_orders
            if not execute_orders:
                blockers.append({
                    'id': 'gatekeeper_execute_orders',
                    'category': 'SAFETY_GATEKEEPER',
                    'name': 'Execute Orders Disabled',
                    'severity': 'critical',
                    'active': True,
                    'message': 'EXECUTE_ORDERS is set to False',
                    'details': {
                        'current_value': 'False',
                        'required_value': 'True',
                        'config_key': 'EXECUTE_ORDERS',
                        'config_line': 'Check order_execution.enabled in config.yaml'
                    },
                    'actions': ['enable_execute_orders', 'view_config'],
                    'deep_link': {
                        'tab': 'configuration',
                        'section': 'trading_controls',
                        'field': 'EXECUTE_ORDERS'
                    }
                })
        
        # I_UNDERSTAND_LIVE check
        understand_live = self.yaml_config.execution_safety.i_understand_live == 'YES'
        trading_mode = self.yaml_config.trading_mode
        if trading_mode == 'live' and not understand_live:
            blockers.append({
                'id': 'gatekeeper_understand_live',
                'category': 'SAFETY_GATEKEEPER',
                'name': 'Live Trading Not Acknowledged',
                'severity': 'critical',
                'active': True,
                'message': 'I_UNDERSTAND_LIVE must be True for live trading',
                'details': {
                    'current_value': 'False',
                    'required_value': 'True',
                    'trading_mode': trading_mode,
                    'config_key': 'I_UNDERSTAND_LIVE'
                },
                'actions': ['acknowledge_live', 'switch_to_demo'],
                'deep_link': {
                    'tab': 'configuration',
                    'section': 'trading_controls',
                    'field': 'I_UNDERSTAND_LIVE'
                }
            })
        
        return blockers
    
    def _check_capital_protection(self) -> List[Dict]:
        """Check Capital Protection blockers"""
        blockers = []
        
        # Equity Floor check
        cfg = get_config()
        equity_floor_enabled = cfg.capital_protection.equity_floor.floor_inr > 0
        if equity_floor_enabled:
            equity_floor = cfg.capital_protection.equity_floor.floor_inr
            # Try to read current equity from state
            try:
                if self.state_file.exists():
                    state = load_state_file(self.state_file)
                    current_equity = state.get('equity', 0)
                    if current_equity > 0 and current_equity < equity_floor:
                        blockers.append({
                                'id': 'capital_equity_floor',
                                'category': 'CAPITAL_PROTECTION',
                                'name': 'Equity Floor Breached',
                                'severity': 'critical',
                                'active': True,
                                'message': f'Current equity ₹{current_equity:,.0f} < ₹{equity_floor:,.0f} (minimum)',
                                'details': {
                                    'current_equity': current_equity,
                                    'equity_floor': equity_floor,
                                    'shortfall': equity_floor - current_equity,
                                    'config_key': 'capital.equity_floor_inr'
                                },
                                'actions': ['add_funds', 'lower_floor', 'override'],
                                'deep_link': {
                                    'tab': 'capital_protection',
                                    'section': 'equity_floor',
                                    'field': 'capital.equity_floor_inr'
                                }
                            })
            except Exception as e:
                pass  # Can't determine equity, skip check
        
        # Drawdown Cap check
        drawdown_cap = cfg.capital_protection.drawdown_cap.max_pct
        if drawdown_cap > 0:
            # This would require historical equity tracking
            # Placeholder for now
            pass
        
        # Pending Order Budget check
        pending_budget_max = cfg.capital_protection.pending_budget.max_notional_inr
        if pending_budget_max > 0:
            # This would require checking current pending orders
            # Placeholder for now
            pass
        
        return blockers
    
    def _check_guardian_signal(self) -> List[Dict]:
        """
        Check Guardian Bot GO/STOP signal from SQL database.
        
        Guardian monitors ALL risk (volatility, loss, position, liquidation).
        Trading bot simply reads Guardian's decision: GO or STOP.
        """
        blockers = []
        
        cfg = get_config()
        guardian_enabled = cfg.guardian.enabled
        if not guardian_enabled:
            return blockers
        
        # Check if Guardian bot is running
        guardian_pid_file = self.workspace_root / '.guardian.pid'
        if not guardian_pid_file.exists():
            blockers.append({
                'id': 'guardian_not_running',
                'category': 'GUARDIAN_BOT',
                'name': 'Guardian Bot Not Running',
                'severity': 'critical',
                'active': True,
                'message': 'Guardian Bot is not active (no PID file found)',
                'details': {
                    'expected_pid_file': str(guardian_pid_file),
                    'config_key': 'guardian.enabled'
                },
                'actions': ['start_guardian', 'disable_guardian'],
                'deep_link': {
                    'tab': 'guardian',
                    'section': 'status',
                    'field': 'GUARDIAN_ENABLED'
                }
            })
            return blockers  # If Guardian not running, can't check signal
        
        # Read Guardian's GO/STOP signal from SQL database
        try:
            import sqlite3
            # Use correct database based on bot mode (LONG/SHORT)
            mode = cfg.bot.mode
            db_name = f"bot_events_{mode}.db"
            db_path = self.workspace_root / 'data' / db_name
            
            if not db_path.exists():
                blockers.append({
                    'id': 'guardian_no_signal',
                    'category': 'GUARDIAN_BOT',
                    'name': 'Guardian Signal Database Missing',
                    'severity': 'warning',
                    'active': True,
                    'message': 'Guardian signal database not found',
                    'details': {
                        'expected_db': str(db_path),
                        'config_key': 'guardian.enabled'
                    },
                    'actions': ['check_guardian', 'restart_guardian'],
                    'deep_link': {
                        'tab': 'guardian',
                        'section': 'signal_status'
                    }
                })
                return blockers
            
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Get latest Guardian signal from EventStore
            # Events are stored with event_type = 'guardian_signal_go' or 'guardian_signal_stop'
            # and data is JSON string
            cursor.execute('''
                SELECT event_type, data, timestamp
                FROM events
                WHERE event_type IN ('guardian_signal_go', 'guardian_signal_stop')
                ORDER BY timestamp DESC
                LIMIT 1
            ''')
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                blockers.append({
                    'id': 'guardian_no_signal',
                    'category': 'GUARDIAN_BOT',
                    'name': 'No Guardian Signal Found',
                    'severity': 'warning',
                    'active': True,
                    'message': 'Guardian has not published any signals yet',
                    'details': {
                        'db_path': str(db_path),
                        'config_key': 'guardian.enabled'
                    },
                    'actions': ['wait_for_signal', 'check_guardian'],
                    'deep_link': {
                        'tab': 'guardian',
                        'section': 'signal_status'
                    }
                })
                return blockers
            
            # Parse the result
            import json
            event_type, data_json, timestamp = result
            signal_data = json.loads(data_json)
            signal = signal_data['signal']
            reason = signal_data['reason']
            
            # If Guardian says STOP, report it as a blocker
            if signal == 'STOP':
                # Extract additional details if available
                details = signal_data.get('details', {})
                blocker_details = {
                    'signal': signal,
                    'reason': reason,
                    'timestamp': timestamp,
                    'config_key': 'guardian.enabled'
                }
                
                # Add RSI details if present
                if 'rsi' in details:
                    blocker_details['rsi'] = details['rsi']
                    blocker_details['threshold'] = details.get('threshold')
                    blocker_details['bot_mode'] = details.get('bot_mode')
                
                blockers.append({
                    'id': 'guardian_stop_signal',
                    'category': 'GUARDIAN_BOT',
                    'name': 'Guardian STOP Signal',
                    'severity': 'critical',
                    'active': True,
                    'message': f'Guardian halted trading: {reason}',
                    'details': blocker_details,
                    'actions': ['view_guardian_details', 'adjust_limits'],
                    'deep_link': {
                        'tab': 'guardian',
                        'section': 'signal_details'
                    }
                })
        
        except Exception as e:
            blockers.append({
                'id': 'guardian_signal_error',
                'category': 'GUARDIAN_BOT',
                'name': 'Guardian Signal Read Error',
                'severity': 'warning',
                'active': True,
                'message': f'Failed to read Guardian signal: {str(e)}',
                'details': {
                    'error': str(e),
                    'config_key': 'guardian.enabled'
                },
                'actions': ['check_database', 'restart_guardian'],
                'deep_link': {
                    'tab': 'guardian',
                    'section': 'troubleshooting'
                }
            })
        
        return blockers
    
    # Volatility/liquidation/loss limit/confirmation guard checking methods REMOVED (199 lines)
    # Guardian monitors all risk - bot just reads Guardian's GO/STOP signal from SQL
    
    def _check_order_confirmation_guard(self) -> List[Dict]:
        """
        Check Order Confirmation Guard - currently not implemented
        (Guardian handles all risk monitoring)
        """
        return []
    
    def _check_circuit_breaker(self) -> List[Dict]:
        """Check Circuit Breaker blockers"""
        blockers = []
        
        cfg = get_config()
        cb_enabled = cfg.safety.circuit_breaker.enabled
        if not cb_enabled:
            return blockers
        
        # Try to read circuit breaker status
        cb_file = self.workspace_root / 'bot' / 'safety' / '.circuit_breaker_status.json'
        if cb_file.exists():
            try:
                with open(cb_file, 'r') as f:
                    cb_status = json.load(f)
                    
                    if cb_status.get('is_open', False):
                        blockers.append({
                            'id': 'circuit_breaker_open',
                            'category': 'CIRCUIT_BREAKER',
                            'name': 'Circuit Breaker Triggered',
                            'severity': 'critical',
                            'active': True,
                            'message': f'Too many API failures ({cb_status.get("failure_count", 0)})',
                            'details': {
                                'failure_count': cb_status.get('failure_count', 0),
                                'threshold': cfg.safety.circuit_breaker.failure_threshold,
                                'reset_time': cb_status.get('reset_time'),
                                'config_key': 'CIRCUIT_BREAKER_ENABLED'
                            },
                            'actions': ['wait_for_reset', 'manual_reset', 'disable'],
                            'deep_link': {
                                'tab': 'risk_management',
                                'section': 'circuit_breaker',
                                'field': 'CIRCUIT_BREAKER_ENABLED'
                            }
                        })
            except Exception as e:
                pass
        
        return blockers

    def _check_process_health(self) -> List[Dict]:
        """Detect if trading bot or guardian bot processes are not running."""
        blockers: List[Dict] = []
        try:
            import subprocess
            # Check main trading bot via bot.pid if present, else ps grep
            bot_pid_file = self.workspace_root / 'reports' / 'bot.pid'
            bot_running = False
            bot_pid = None
            if bot_pid_file.exists():
                try:
                    bot_pid = int(bot_pid_file.read_text().strip() or '0')
                except Exception:
                    bot_pid = None
            if bot_pid:
                try:
                    os.kill(bot_pid, 0)
                    bot_running = True
                except Exception:
                    bot_running = False
            else:
                # Fallback to ps check
                try:
                    out = subprocess.check_output(
                        [
                            'bash', '-lc',
                            "ps aux | grep -E 'python(3)? +bot/run.py' | grep -v grep || true"
                        ]
                    ).decode().strip()
                    bot_running = len(out) > 0
                except Exception:
                    bot_running = False

            if not bot_running:
                blockers.append({
                    'id': 'process_bot_stopped',
                    'category': 'PROCESS_MANAGER',
                    'name': 'Trading Bot Not Running',
                    'severity': 'critical',
                    'active': True,
                    'message': 'Main trading bot process is not active',
                    'details': {
                        'pid': bot_pid,
                        'pid_file': str(bot_pid_file)
                    },
                    'actions': ['start_bot', 'open_tmux'],
                    'deep_link': {
                        'tab': 'tmux',
                        'section': 'bot_terminal'
                    }
                })

            # Check guardian bot via health file or ps
            guardian_running = False
            guardian_health_json = self.workspace_root / '.guardian_health.json'
            if guardian_health_json.exists():
                try:
                    data = json.loads(guardian_health_json.read_text())
                    if data.get('pid') and data.get('last_heartbeat'):
                        guardian_running = True
                except Exception:
                    guardian_running = False
            if not guardian_running:
                try:
                    out = subprocess.check_output(
                        [
                            'bash', '-lc',
                            r"ps aux | grep -E 'python(3)? +-m +bot\.guardian\.guardian_bot' | grep -v grep || true"
                        ]
                    ).decode().strip()
                    guardian_running = len(out) > 0
                except Exception:
                    guardian_running = False

            if not guardian_running:
                blockers.append({
                    'id': 'process_guardian_stopped',
                    'category': 'PROCESS_MANAGER',
                    'name': 'Guardian Bot Not Running',
                    'severity': 'warning',
                    'active': True,
                    'message': 'Guardian bot process is not active',
                    'details': {},
                    'actions': ['start_guardian', 'open_tmux'],
                    'deep_link': {
                        'tab': 'tmux',
                        'section': 'guardian_terminal'
                    }
                })
        except Exception:
            pass

        return blockers
    
    def get_blocker_summary(self) -> str:
        """Get a human-readable summary of all blockers"""
        result = self.check_all_blockers()
        
        if result['trading_allowed']:
            return "✅ All systems healthy - Trading allowed"
        
        active = [b for b in result['blockers'] if b['active']]
        summary = f"🚫 {len(active)} blocker(s) active:\n"
        
        for blocker in active:
            severity_emoji = {
                'critical': '🔴',
                'warning': '🟠',
                'info': '🔵'
            }.get(blocker['severity'], '⚪')
            
            summary += f"{severity_emoji} {blocker['name']}: {blocker['message']}\n"
        
        return summary


# Singleton instance
_tracker_instance = None

def get_blocker_tracker() -> BlockerTracker:
    """Get singleton instance of BlockerTracker"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = BlockerTracker()
    return _tracker_instance


if __name__ == '__main__':
    # Test the blocker tracker
    tracker = get_blocker_tracker()
    result = tracker.check_all_blockers()
    
    print("=" * 70)
    print("BLOCKER TRACKER TEST")
    print("=" * 70)
    print(f"\nTrading Allowed: {result['trading_allowed']}")
    print(f"Total Blockers: {result['total_blockers']}")
    print(f"\nSummary:\n{tracker.get_blocker_summary()}")
    
    if result['total_blockers'] > 0:
        print("\nDetailed Blockers:")
        for blocker in result['blockers']:
            if blocker['active']:
                print(f"\n  {blocker['category']}: {blocker['name']}")
                print(f"  Severity: {blocker['severity']}")
                print(f"  Message: {blocker['message']}")
                print(f"  Actions: {', '.join(blocker['actions'])}")

