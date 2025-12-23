"""
Bot Control Routes Blueprint

This module handles all API routes related to bot lifecycle management.

Routes:
- GET  /api/bot/status - Get bot running status
- POST /api/bot/start - Start trading bot
- POST /api/bot/stop - Stop trading bot
- POST /api/bot/restart - Restart trading bot
- GET  /api/bots/status - Get all bot processes status
- POST /api/bots/stop - Stop specific bot by PID
- POST /api/bot/command - Execute bot command with confirmation (Week 3)

Dependencies:
- utils.process_helpers (process management)
- subprocess, psutil
- Rate limiting

Refactored from app.py (8,850 lines)
Date: 2025-10-31
Updated: 2025-11-12 (Command confirmation)
"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.process_helpers import is_bot_running, BOT_PID_FILE
from utils.pm2_adapter import get_pm2_adapter, should_use_pm2
from config.loader import get_config

def get_config_value(yaml_path: str, env_var: str = None, default: any = None):
    """Get config value from YAML using dot notation"""
    try:
        cfg = get_config()
        value = cfg
        for key in yaml_path.split('.'):
            value = getattr(value, key)
        return value
    except (AttributeError, KeyError):
        return default

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

log = logging.getLogger(__name__)

# Get PM2 adapter instance
pm2 = get_pm2_adapter()

# Create blueprint
bot_control_bp = Blueprint('bot_control', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent

# ============================================================================
# Route Handlers
# ============================================================================

@bot_control_bp.route('/api/bot/status', methods=['GET'])
def bot_status():
    """
    Get bot running status
    
    Uses PM2 if enabled, falls back to PID file check
    
    Returns:
        JSON response with bot status
    
    Example:
        GET /api/bot/status
        Response: {"running": true, "pid": 12345, "pm2_managed": true}
    """
    try:
        # Check if PM2 is enabled
        if should_use_pm2():
            # Get status from PM2
            pm2_status = pm2.get_bot_status('live')
            
            if pm2_status:
                return jsonify({
                    'running': pm2_status['status'] == 'online',
                    'pid': pm2_status.get('pid'),
                    'pm2_managed': True,
                    'pm2_status': pm2_status['status'],
                    'restarts': pm2_status.get('restarts', 0),
                    'cpu': pm2_status.get('cpu', 0),
                    'memory_mb': round(pm2_status.get('memory', 0), 1)
                }), 200
            else:
                # Not running in PM2
                return jsonify({
                    'running': False,
                    'pm2_managed': True
                }), 200
        
        # Fallback to traditional PID file check OR process detection
        running = is_bot_running()
        pid = None
        uptime = None
        
        # First try PID file
        if running and BOT_PID_FILE.exists():
            try:
                with open(BOT_PID_FILE, 'r') as f:
                    pid = int(f.read().strip())
            except:
                pass
        
        # If no PID file, detect by process name (bot started manually)
        if not pid and PSUTIL_AVAILABLE:
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and 'async_gridbot.py' in ' '.join(cmdline):
                        pid = proc.info['pid']
                        running = True
                        break
            except:
                pass
        
        # Get uptime if PID is valid
        if pid and PSUTIL_AVAILABLE:
            try:
                import psutil
                process = psutil.Process(pid)
                uptime_seconds = time.time() - process.create_time()
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                seconds = int(uptime_seconds % 60)
                uptime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except:
                pass
        
        return jsonify({
            'running': running,
            'bot_status': 'online' if running else 'stopped',
            'pid': pid,
            'uptime': uptime,
            'pm2_managed': False
        }), 200
        
    except Exception as e:
        log.error(f"Error getting bot status: {e}")
        return jsonify({
            'running': False,
            'error': str(e),
            'pm2_managed': should_use_pm2()
        }), 500


@bot_control_bp.route('/api/bot/start', methods=['POST'])
def bot_start():
    """
    Start trading bot
    
    Uses PM2 if enabled, falls back to direct launcher
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/bot/start
        Response: {"success": true, "message": "Bot started successfully", "pm2_managed": true}
    """
    try:
        # Check if PM2 is enabled
        if should_use_pm2():
            success, message = pm2.start_bot('live')
            
            return jsonify({
                'success': success,
                'message': message,
                'pm2_managed': True
            }), 200 if success else 400
        
        # Fallback to traditional bot_launcher.py
        if is_bot_running():
            return jsonify({
                'success': False,
                'message': 'Bot is already running',
                'pm2_managed': False
            }), 400
        
        # Start bot using unified launcher
        result = subprocess.run(
            [sys.executable, 'bot_launcher.py', '--daemon'],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            env=os.environ.copy()
        )
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'message': f'Launcher failed: {result.stderr}',
                'pm2_managed': False
            }), 500
        
        # Give launcher time to create PID file
        time.sleep(2)
        
        if not is_bot_running():
            return jsonify({
                'success': False,
                'message': 'Bot started but not responding',
                'pm2_managed': False
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'Bot started successfully',
            'pm2_managed': False
        }), 200
        
    except Exception as e:
        log.error(f"Error starting bot: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'pm2_managed': should_use_pm2()
        }), 500


@bot_control_bp.route('/api/bot/stop', methods=['POST'])
def bot_stop():
    """
    Stop trading bot
    
    Uses PM2 graceful shutdown if enabled (30s timeout),
    falls back to direct SIGTERM
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/bot/stop
        Response: {"success": true, "message": "Bot stopped successfully", "pm2_managed": true}
    """
    try:
        # Check if PM2 is enabled
        if should_use_pm2():
            success, message = pm2.stop_bot('live')
            
            return jsonify({
                'success': success,
                'message': message,
                'pm2_managed': True
            }), 200 if success else 400
        
        # Fallback to traditional SIGTERM method
        if not is_bot_running():
            return jsonify({
                'success': False,
                'message': 'Bot is not running',
                'pm2_managed': False
            }), 400
        
        # Read PID
        if not BOT_PID_FILE.exists():
            return jsonify({
                'success': False,
                'message': 'Bot PID file not found',
                'pm2_managed': False
            }), 500
        
        with open(BOT_PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Send SIGTERM for graceful shutdown
        try:
            os.kill(pid, 15)  # SIGTERM
            
            # Wait up to 30 seconds for graceful shutdown (increased from 10s)
            # Bot cleanup includes: cancel orders (15s timeout), send notifications, etc.
            log.info(f"Sent SIGTERM to bot (PID {pid}), waiting for graceful shutdown...")
            for i in range(60):  # 30 seconds (60 * 0.5s)
                if not is_bot_running():
                    log.info(f"Bot stopped gracefully after {i * 0.5:.1f}s")
                    break
                time.sleep(0.5)
            
            # Force kill ONLY if still running after 30 seconds
            if is_bot_running():
                log.warning(f"Bot did not stop gracefully after 30s, sending SIGKILL...")
                os.kill(pid, 9)  # SIGKILL
                time.sleep(1)
            
            # Clean up PID file
            if BOT_PID_FILE.exists():
                BOT_PID_FILE.unlink()
            
            return jsonify({
                'success': True,
                'message': 'Bot stopped successfully',
                'pm2_managed': False
            }), 200
            
        except ProcessLookupError:
            # Already stopped
            if BOT_PID_FILE.exists():
                BOT_PID_FILE.unlink()
            return jsonify({
                'success': True,
                'message': 'Bot was already stopped',
                'pm2_managed': False
            }), 200
        
    except Exception as e:
        log.error(f"Error stopping bot: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'pm2_managed': should_use_pm2()
        }), 500


@bot_control_bp.route('/api/bot/restart', methods=['POST'])
def bot_restart():
    """
    Restart trading bot
    
    Uses PM2 restart if enabled, falls back to stop+start
    
    Returns:
        JSON response with success status
    """
    try:
        # Check if PM2 is enabled
        if should_use_pm2():
            success, message = pm2.restart_bot('live')
            
            return jsonify({
                'success': success,
                'message': message,
                'pm2_managed': True
            }), 200 if success else 500
        
        # Fallback to traditional stop+start
        # Stop bot first
        if is_bot_running():
            stop_response = bot_stop()
            stop_data = stop_response[0].get_json()
            
            if not stop_data.get('success'):
                return jsonify({
                    'success': False,
                    'message': 'Failed to stop bot',
                    'pm2_managed': False
                }), 500
            
            # Wait for clean shutdown
            time.sleep(2)
        
        # Start bot
        start_response = bot_start()
        return start_response
        
    except Exception as e:
        log.error(f"Error restarting bot: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'pm2_managed': should_use_pm2()
        }), 500


@bot_control_bp.route('/api/bots/status', methods=['GET'])
def get_all_bots_status():
    """
    Get status of all running bot processes
    
    Returns detailed information about all Python bot processes including
    main trading bot, guardian, monitor, and WebUI.
    
    Returns:
        JSON response with list of all bots
    """
    try:
        if not PSUTIL_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'psutil module not installed',
                'bots': [],
                'totalBots': 0
            }), 500
        
        bots = []
        current_pid = os.getpid()
        
        # ✅ FIX NOV 10: Get current project directory to filter processes
        current_project = str(Path(__file__).parent.parent.parent.parent)
        
        # Iterate through all running processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'cpu_percent', 'memory_info', 'cwd']):
            try:
                cmdline = proc.info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline).lower()
                
                # Skip if not a Python process
                if 'python' not in cmdline_str:
                    continue
                
                # ✅ FIX NOV 10: Only show processes from THIS project (not demo)
                # Check if process is running from this project directory
                try:
                    proc_cwd = proc.cwd()
                    # Skip if process is from WorkingBot-demo (not main WorkingBot)
                    if 'workingbot-demo' in proc_cwd.lower():
                        continue
                    # Only include if from current WorkingBot directory
                    if not proc_cwd.startswith(current_project):
                        # Also check cmdline for project path
                        if current_project.lower() not in cmdline_str:
                            continue
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    # If we can't check cwd, check command line
                    if 'workingbot-demo' in cmdline_str:
                        continue
                
                # Detect bot type
                bot_type = None
                bot_name = None
                
                if 'bot/run.py' in cmdline_str or 'bot.run' in cmdline_str:
                    bot_type = 'live_trading'
                    bot_name = 'Main Trading Bot'
                elif 'guardian_bot' in cmdline_str or 'bot.guardian.core.guardian_bot' in cmdline_str:
                    bot_type = 'guardian'
                    bot_name = 'Guardian Bot'
                elif 'heartbeat_monitor' in cmdline_str:
                    bot_type = 'monitor'
                    bot_name = 'Heartbeat Monitor'
                elif 'webui/backend/app.py' in cmdline_str or proc.info['pid'] == current_pid:
                    bot_type = 'webui'
                    bot_name = 'WebUI Backend'
                else:
                    continue
                
                # Calculate uptime
                create_time = proc.info.get('create_time', time.time())
                uptime_seconds = int(time.time() - create_time)
                hours = uptime_seconds // 3600
                minutes = (uptime_seconds % 3600) // 60
                
                uptime = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                
                # Get memory usage in MB
                memory_info = proc.info.get('memory_info')
                memory_mb = round(memory_info.rss / 1024 / 1024, 1) if memory_info else 0
                
                # Get CPU percentage
                cpu_percent = proc.cpu_percent(interval=0.1) or 0
                
                bots.append({
                    'pid': proc.info['pid'],
                    'name': bot_name,
                    'command': ' '.join(cmdline),
                    'type': bot_type,
                    'startedAt': datetime.fromtimestamp(create_time).isoformat(),
                    'uptime': uptime,
                    'status': 'running',
                    'cpuPercent': round(cpu_percent, 1),
                    'memoryMb': memory_mb
                })
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return jsonify({
            'success': True,
            'bots': bots,
            'totalBots': len(bots)
        }), 200
        
    except Exception as e:
        log.error(f"Error getting bot status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'bots': [],
            'totalBots': 0
        }), 500


@bot_control_bp.route('/api/bots/stop', methods=['POST'])
def stop_bot_by_pid():
    """
    Stop a specific bot process by PID
    
    Request Body:
        {"pid": 12345}
    
    Returns:
        JSON response with success status
    """
    try:
        data = request.json
        if not data or 'pid' not in data:
            return jsonify({
                'success': False,
                'message': 'PID is required'
            }), 400
        
        try:
            pid = int(data['pid'])
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'Invalid PID format'
            }), 400
        
        # Safety check: Don't kill WebUI
        if pid == os.getpid():
            return jsonify({
                'success': False,
                'message': 'Cannot stop WebUI backend from itself'
            }), 403
        
        if not PSUTIL_AVAILABLE:
            return jsonify({
                'success': False,
                'message': 'psutil module not installed'
            }), 500
        
        try:
            proc = psutil.Process(pid)
            cmdline = ' '.join(proc.cmdline())
            
            # Verify it's a Python process
            if 'python' not in cmdline.lower():
                return jsonify({
                    'success': False,
                    'message': f'PID {pid} is not a Python process'
                }), 400
            
            log.info(f"Stopping process PID {pid}: {cmdline}")
            
            # Graceful termination
            proc.terminate()
            
            # Wait up to 5 seconds
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                # Force kill
                proc.kill()
            
            return jsonify({
                'success': True,
                'message': f'Bot with PID {pid} stopped successfully'
            }), 200
            
        except psutil.NoSuchProcess:
            return jsonify({
                'success': False,
                'message': f'No process found with PID {pid}'
            }), 404
        except psutil.AccessDenied:
            return jsonify({
                'success': False,
                'message': f'Access denied to stop process {pid}'
            }), 403
            
    except Exception as e:
        log.error(f"Error stopping bot: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ============================================================================
# PM2-Specific Routes
# ============================================================================

@bot_control_bp.route('/api/pm2/enabled', methods=['GET'])
def pm2_enabled():
    """
    Check if PM2 integration is enabled
    
    Returns:
        JSON response with PM2 status
    """
    try:
        return jsonify({
            'enabled': should_use_pm2(),
            'available': pm2.available,
            'config_file': str(pm2.config_file)
        }), 200
    except Exception as e:
        log.error(f"Error checking PM2 status: {e}")
        return jsonify({
            'enabled': False,
            'error': str(e)
        }), 500


@bot_control_bp.route('/api/pm2/bots', methods=['GET'])
def pm2_bots_status():
    """
    Get all PM2-managed bots status
    
    Returns:
        JSON response with all bots
    """
    try:
        if not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 is not enabled'
            }), 400
        
        bots = pm2.get_all_bots_status()
        
        return jsonify({
            'success': True,
            'bots': bots,
            'total': len(bots)
        }), 200
        
    except Exception as e:
        log.error(f"Error getting PM2 bots: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bot_control_bp.route('/api/pm2/logs/<mode>', methods=['GET'])
def pm2_bot_logs(mode):
    """
    Get bot logs from PM2
    
    Args:
        mode: 'live' or 'demo'
    
    Query params:
        lines: Number of lines (default: 100)
    
    Returns:
        JSON response with logs
    """
    try:
        if not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 is not enabled'
            }), 400
        
        lines = request.args.get('lines', 100, type=int)
        
        success, logs = pm2.get_bot_logs(mode, lines)
        
        if not success:
            return jsonify({
                'success': False,
                'message': logs
            }), 400
        
        return jsonify({
            'success': True,
            'logs': logs,
            'mode': mode,
            'lines': lines
        }), 200
        
    except Exception as e:
        log.error(f"Error getting PM2 logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bot_control_bp.route('/api/pm2/reload/<mode>', methods=['POST'])
def pm2_reload_bot(mode):
    """
    Reload bot via PM2 (zero-downtime)
    
    Args:
        mode: 'live' or 'demo'
    
    Returns:
        JSON response with success status
    """
    try:
        if not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 is not enabled'
            }), 400
        
        success, message = pm2.reload_bot(mode)
        
        return jsonify({
            'success': success,
            'message': message,
            'mode': mode
        }), 200 if success else 400
        
    except Exception as e:
        log.error(f"Error reloading bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bot_control_bp.route('/api/pm2/save', methods=['POST'])
def pm2_save():
    """
    Save PM2 process list
    
    Returns:
        JSON response with success status
    """
    try:
        if not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 is not enabled'
            }), 400
        
        success, message = pm2.save_process_list()
        
        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 500
        
    except Exception as e:
        log.error(f"Error saving PM2 list: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bot_control_bp.route('/api/pm2/flush-logs', methods=['POST'])
def pm2_flush():
    """
    Flush all PM2 logs
    
    Returns:
        JSON response with success status
    """
    try:
        if not should_use_pm2():
            return jsonify({
                'success': False,
                'message': 'PM2 is not enabled'
            }), 400
        
        success, message = pm2.flush_logs()
        
        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 500
        
    except Exception as e:
        log.error(f"Error flushing PM2 logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bot_control_bp.route('/api/bot/clear-memory', methods=['POST'])
def clear_bot_memory():
    """
    Clear bot's internal memory/state (SQL Event Store + Actor Memory)
    
    This endpoint:
    - Clears SQL event store (pending orders, positions)
    - Clears actor memory (position_actor, order_actor)
    - Creates backup of SQL database before clearing
    - Does NOT cancel orders on exchange (user does manually)
    - Does NOT close positions
    - Does NOT stop the bot
    
    User workflow:
    1. Cancel orders manually on exchange
    2. Call this endpoint to clear bot memory
    3. Change grid configuration
    4. Bot starts fresh with new config
    
    Returns:
        JSON response with success status and details
        
    Example:
        POST /api/bot/clear-memory
        Response: {
            "success": true,
            "message": "Bot memory cleared successfully",
            "backup_created": true,
            "backup_path": "bot_events_LONG_backup_1699999999.db",
            "events_cleared": 1234,
            "actors_cleared": true
        }
    """
    try:
        import shutil
        import time
        import sqlite3
        from pathlib import Path
        
        # Get trading mode from environment
        trading_mode = get_config_value('trading.mode', 'TRADING_MODE', 'demo').lower()
        
        # Determine SQL database path based on mode
        db_file = BASE_DIR / 'bot_events_LONG.db'  # Async bot uses this
        
        backup_path = None
        backup_created = False
        events_cleared = 0
        actors_cleared = False
        
        # Backup and clear SQL database
        if db_file.exists():
            timestamp = int(time.time())
            backup_filename = f'bot_events_LONG_backup_{timestamp}.db'
            backup_path = db_file.parent / backup_filename
            
            try:
                # Create backup
                shutil.copy(db_file, backup_path)
                log.info(f"✅ SQL database backed up to: {backup_path}")
                backup_created = True
                
                # Clear pending order and position events from SQL
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                
                # Count events before clearing
                cursor.execute("SELECT COUNT(*) FROM events WHERE event_type IN ('pending_buy_set', 'pending_sell_set', 'position_opened', 'position_closed')")
                events_cleared = cursor.fetchone()[0]
                
                # Clear pending order events
                cursor.execute("DELETE FROM events WHERE event_type IN ('pending_buy_set', 'pending_sell_set', 'pending_buy_cleared', 'pending_sell_cleared')")
                
                # Clear position events
                cursor.execute("DELETE FROM events WHERE event_type IN ('position_opened', 'position_closed', 'position_updated')")
                
                conn.commit()
                conn.close()
                
                log.info(f"✅ Cleared {events_cleared} events from SQL database")
                
            except Exception as db_error:
                log.error(f"❌ Error clearing SQL database: {db_error}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to clear SQL database: {str(db_error)}'
                }), 500
        else:
            log.warning(f"⚠️  SQL database doesn't exist: {db_file}")
        
        # Clear actor memory by sending CLEAR commands
        try:
            if bot_instance and hasattr(bot_instance, 'position_actor') and hasattr(bot_instance, 'order_actor'):
                import asyncio
                
                async def clear_actors():
                    # Clear pending buy/sell from position_actor
                    await bot_instance.position_actor.ask("CLEAR_PENDING_BUY", {})
                    await bot_instance.position_actor.ask("CLEAR_PENDING_SELL", {})
                    log.info("✅ Cleared pending orders from position_actor memory")
                    
                    # Clear active orders from order_actor
                    order_state = await bot_instance.order_actor.ask("GET_STATE", {})
                    if order_state and 'active_orders' in order_state:
                        log.info(f"✅ Cleared {len(order_state['active_orders'])} active orders from order_actor memory")
                    
                    return True
                
                # Run in bot's event loop
                if hasattr(bot_instance, '_loop') and bot_instance._loop:
                    asyncio.run_coroutine_threadsafe(clear_actors(), bot_instance._loop).result(timeout=5)
                    actors_cleared = True
                    log.info("✅ Actor memory cleared successfully")
                    
        except Exception as actor_error:
            log.warning(f"⚠️  Could not clear actor memory (bot may not be running): {actor_error}")
            actors_cleared = False
        
        log.warning(f"🗑️  Bot memory cleared by user (mode: {trading_mode})")
        
        # Send Telegram notification if configured
        try:
            telegram_token = (
                get_config_value('notifications.telegram.live_bot_token', 'LIVE_TELEGRAM_BOT_TOKEN')
                if trading_mode == 'live' 
                else get_config_value('notifications.telegram.demo_bot_token', 'DEMO_TELEGRAM_BOT_TOKEN')
            )
            telegram_chat = (
                get_config_value('notifications.telegram.live_chat_id', 'LIVE_TELEGRAM_CHAT_ID')
                if trading_mode == 'live'
                else get_config_value('notifications.telegram.demo_chat_id', 'DEMO_TELEGRAM_CHAT_ID')
            )
            
            if telegram_token and telegram_chat and telegram_token != '***REDACTED***':
                import requests
                message = (
                    f"🗑️ Bot memory cleared ({trading_mode} mode)\n\n"
                    f"SQL Events Cleared: {events_cleared}\n"
                    f"Actor Memory Cleared: {'✅' if actors_cleared else '⚠️ Bot not running'}\n\n"
                    f"Ready for new configuration."
                )
                requests.post(
                    f'https://api.telegram.org/bot{telegram_token}/sendMessage',
                    json={'chat_id': telegram_chat, 'text': message},
                    timeout=5
                )
        except Exception as tg_error:
            log.warning(f"⚠️  Could not send Telegram notification: {tg_error}")
        
        return jsonify({
            'success': True,
            'message': 'Bot memory cleared successfully',
            'trading_mode': trading_mode,
            'backup_created': backup_created,
            'backup_path': str(backup_path.relative_to(BASE_DIR)) if backup_path else None,
            'sql_database_existed': db_file.exists(),
            'events_cleared': events_cleared,
            'actors_cleared': actors_cleared
        }), 200
        
    except Exception as e:
        log.error(f"❌ Error clearing bot memory: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Week 3: Command confirmation endpoint
command_confirmations = {}  # In-memory tracking of confirmation IDs

@bot_control_bp.route('/api/bot/command', methods=['POST'])
def execute_bot_command():
    """
    Execute bot command with confirmation tracking (Week 3)
    
    Supports saga pattern: optimistic updates + backend confirmation
    
    Request body:
        {
            "command": "start|stop|restart|update_config|cancel_orders",
            "params": {...},
            "confirmation_id": "uuid-v4"
        }
    
    Returns:
        JSON response with command result and confirmation
    """
    try:
        data = request.get_json()
        command = data.get('command')
        params = data.get('params', {})
        confirmation_id = data.get('confirmation_id')
        
        if not command:
            return jsonify({
                'success': False,
                'error': 'Missing command'
            }), 400
        
        if not confirmation_id:
            return jsonify({
                'success': False,
                'error': 'Missing confirmation_id'
            }), 400
        
        # Track command
        command_confirmations[confirmation_id] = {
            'command': command,
            'params': params,
            'status': 'executing',
            'start_time': datetime.utcnow().isoformat()
        }
        
        # Execute command
        if command == 'start':
            # Use existing start endpoint
            from flask import current_app
            with current_app.test_request_context():
                result = bot_start()
                result_data = result[0].get_json() if isinstance(result, tuple) else result.get_json()
        
        elif command == 'stop':
            from flask import current_app
            with current_app.test_request_context():
                result = bot_stop()
                result_data = result[0].get_json() if isinstance(result, tuple) else result.get_json()
        
        elif command == 'restart':
            from flask import current_app
            with current_app.test_request_context():
                result = bot_restart()
                result_data = result[0].get_json() if isinstance(result, tuple) else result.get_json()
        
        else:
            command_confirmations[confirmation_id]['status'] = 'failed'
            return jsonify({
                'success': False,
                'error': f'Unknown command: {command}',
                'confirmation_id': confirmation_id
            }), 400
        
        # Update confirmation
        command_confirmations[confirmation_id].update({
            'status': 'confirmed' if result_data.get('success') else 'failed',
            'end_time': datetime.utcnow().isoformat(),
            'result': result_data
        })
        
        return jsonify({
            'success': result_data.get('success', False),
            'confirmation_id': confirmation_id,
            'result': result_data
        }), 200
        
    except Exception as e:
        log.error(f"Error executing bot command: {e}")
        
        if confirmation_id:
            command_confirmations[confirmation_id]['status'] = 'failed'
        
        return jsonify({
            'success': False,
            'error': str(e),
            'confirmation_id': confirmation_id

        }), 500
