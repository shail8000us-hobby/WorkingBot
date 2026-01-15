"""
Metrics Collectors

Collects metrics from various sources:
- File-based health files (Guardian, Bot state)
- System metrics (CPU, memory, disk)
- PM2 process status
- API responses

This module reads data WITHOUT modifying any existing code.
All data collection is passive - reading files and querying APIs.
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Try to import psutil for system metrics
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from .definitions import (
    # App info
    app_info,
    
    # Trading metrics
    orders_placed_total, orders_filled_total, orders_cancelled_total,
    orders_failed_total, open_positions_count, position_value_usd,
    unrealized_pnl_usd, realized_pnl_usd, daily_pnl_usd,
    grid_efficiency_ratio, current_price_usd, grid_reference_price_usd,
    position_size_contracts,
    
    # System metrics
    system_cpu_percent, system_memory_percent, system_memory_used_mb,
    system_disk_percent, system_disk_used_gb, system_load_average,
    
    # Bot metrics
    bot_memory_mb, bot_uptime_seconds, bot_state,
    
    # Guardian metrics
    guardian_signal, guardian_risk_level, guardian_interventions_total,
    guardian_uptime_seconds, guardian_checks_total,
    
    # Risk metrics
    total_loss_inr, daily_loss_inr, liquidation_distance_percent,
    margin_used_percent, rsi_value, rsi_trading_allowed,
    
    # API metrics
    api_call_duration_seconds, api_calls_total, api_rate_limit_hits,
    api_429_errors, api_errors_total, websocket_connected,
    
    # Options metrics
    options_positions_count, options_unrealized_pnl_usd, options_greeks,
)

logger = logging.getLogger(__name__)

# Base directory for WorkingBot
BASE_DIR = Path(__file__).parent.parent.parent


class MetricsCollector:
    """
    Centralized metrics collector.
    
    Collects metrics from multiple sources:
    - Guardian health files
    - Bot state files
    - System metrics (psutil)
    - PM2 status
    
    Usage:
        # Collect all metrics (called by metrics server)
        MetricsCollector.collect_all()
        
        # Or collect specific categories
        MetricsCollector.collect_system_metrics()
        MetricsCollector.collect_guardian_metrics()
        MetricsCollector.collect_bot_metrics()
    """
    
    # Track start time for uptime calculations
    _start_time = time.time()
    
    # Cache for expensive operations
    _cache = {}
    _cache_ttl = 5  # seconds
    
    @classmethod
    def collect_all(cls):
        """Collect all available metrics"""
        try:
            # Set app info
            app_info.info({
                'version': '6.0',
                'python_version': os.popen('python3 --version').read().strip(),
                'start_time': datetime.fromtimestamp(cls._start_time).isoformat()
            })
            
            # Collect from all sources
            cls.collect_system_metrics()
            cls.collect_guardian_metrics()
            cls.collect_bot_metrics()
            cls.collect_options_metrics()
            cls.collect_pm2_metrics()
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}", exc_info=True)
    
    @classmethod
    def collect_system_metrics(cls):
        """Collect system-level metrics using psutil"""
        if not PSUTIL_AVAILABLE:
            logger.debug("psutil not available, skipping system metrics")
            return
        
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            system_cpu_percent.set(cpu_percent)
            
            # Memory
            memory = psutil.virtual_memory()
            system_memory_percent.set(memory.percent)
            system_memory_used_mb.set(memory.used / (1024 * 1024))
            
            # Disk
            disk = psutil.disk_usage('/')
            system_disk_percent.set(disk.percent)
            system_disk_used_gb.set(disk.used / (1024 * 1024 * 1024))
            
            # Load average (Unix only)
            try:
                load_avg = os.getloadavg()
                system_load_average.labels(period='1m').set(load_avg[0])
                system_load_average.labels(period='5m').set(load_avg[1])
                system_load_average.labels(period='15m').set(load_avg[2])
            except (AttributeError, OSError):
                pass
                
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    @classmethod
    def collect_guardian_metrics(cls):
        """Collect metrics from Guardian health files"""
        try:
            # Try multiple guardian health file locations
            health_files = [
                BASE_DIR / 'bot' / 'guardian' / '.guardian_health.json',
                BASE_DIR / '.guardian_health.json',
                BASE_DIR / '.guardian_health',
            ]
            
            guardian_data = None
            for health_file in health_files:
                if health_file.exists():
                    try:
                        with open(health_file, 'r') as f:
                            guardian_data = json.load(f)
                        break
                    except (json.JSONDecodeError, IOError):
                        continue
            
            if not guardian_data:
                logger.debug("No guardian health file found")
                return
            
            # Extract instance info
            symbol = guardian_data.get('symbol', 'BTCUSD')
            instance = guardian_data.get('instance', f'{symbol}_LONG')
            
            # Guardian signal
            signal_value = guardian_data.get('signal', 'STOP')
            guardian_signal.labels(symbol=symbol, instance=instance).set(
                1 if signal_value == 'GO' else 0
            )
            
            # Risk level
            risk_level = guardian_data.get('risk_level', 0)
            if isinstance(risk_level, str):
                risk_map = {'LOW': 25, 'MEDIUM': 50, 'HIGH': 75, 'CRITICAL': 100}
                risk_level = risk_map.get(risk_level.upper(), 50)
            guardian_risk_level.labels(symbol=symbol, instance=instance).set(risk_level)
            
            # Loss metrics
            loss_inr = guardian_data.get('total_loss_inr', 0)
            total_loss_inr.labels(symbol=symbol, instance=instance).set(abs(loss_inr))
            
            daily_loss = guardian_data.get('daily_loss_inr', 0)
            daily_loss_inr.labels(symbol=symbol, instance=instance).set(abs(daily_loss))
            
            # Liquidation distance
            liq_distance = guardian_data.get('liquidation_distance', 
                           guardian_data.get('min_liquidation_distance_pct', 100))
            liquidation_distance_percent.labels(symbol=symbol, instance=instance).set(liq_distance)
            
            # Position info
            positions = guardian_data.get('positions', [])
            if isinstance(positions, list):
                open_positions_count.labels(
                    symbol=symbol, instance=instance, side='all'
                ).set(len(positions))
            
            # Unrealized P&L
            unrealized = guardian_data.get('unrealized_pnl_usd', 0)
            unrealized_pnl_usd.labels(symbol=symbol, instance=instance).set(unrealized)
            
            # Current price
            price = guardian_data.get('current_price', guardian_data.get('mark_price', 0))
            if price:
                current_price_usd.labels(symbol=symbol).set(price)
            
            # RSI metrics
            rsi_data = guardian_data.get('rsi', {})
            if rsi_data:
                rsi_val = rsi_data.get('value', rsi_data.get('current', 0))
                rsi_value.labels(symbol=symbol, timeframe='1h').set(rsi_val)
                
                rsi_allowed = rsi_data.get('trading_allowed', True)
                rsi_trading_allowed.labels(symbol=symbol, instance=instance).set(
                    1 if rsi_allowed else 0
                )
            
            # Uptime
            start_ts = guardian_data.get('start_timestamp', 0)
            if start_ts:
                uptime = time.time() - start_ts
                guardian_uptime_seconds.labels(symbol=symbol, instance=instance).set(uptime)
            
        except Exception as e:
            logger.error(f"Error collecting guardian metrics: {e}", exc_info=True)
    
    @classmethod
    def collect_bot_metrics(cls):
        """Collect metrics from bot state files and databases"""
        try:
            # Try to read runtime state - use actual files
            state_files = [
                BASE_DIR / 'data' / 'system_state.json',
                BASE_DIR / 'data' / 'monitoring_snapshot.json',
                BASE_DIR / 'data' / 'monitoring_snapshot_BTCUSD_LONG.json',
                BASE_DIR / 'data' / 'monitoring_snapshot_ETHUSD_LONG.json',
                BASE_DIR / 'data' / 'runtime_state_LONG.json',
                BASE_DIR / 'data' / 'runtime_state_SHORT.json',
                BASE_DIR / 'data' / 'bot_state.json',
            ]
            
            for state_file in state_files:
                if state_file.exists():
                    try:
                        cls._process_bot_state_file(state_file)
                    except Exception as e:
                        logger.debug(f"Could not process {state_file}: {e}")
            
            # Read monitoring snapshot if available
            snapshot_file = BASE_DIR / 'data' / 'monitoring_snapshot.json'
            if snapshot_file.exists():
                try:
                    with open(snapshot_file, 'r') as f:
                        snapshot = json.load(f)
                    cls._process_monitoring_snapshot(snapshot)
                except Exception as e:
                    logger.debug(f"Could not process monitoring snapshot: {e}")
            
        except Exception as e:
            logger.error(f"Error collecting bot metrics: {e}", exc_info=True)
    
    @classmethod
    def _process_bot_state_file(cls, state_file: Path):
        """Process a bot state file"""
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        symbol = state.get('symbol', 'BTCUSD')
        mode = state.get('mode', 'LONG')
        instance = state.get('instance', f'{symbol}_{mode}')
        
        # Bot running state
        is_running = state.get('is_running', state.get('trading_active', False))
        bot_state.labels(symbol=symbol, instance=instance).set(1 if is_running else 0)
        
        # Positions
        positions = state.get('open_positions', state.get('positions', []))
        if isinstance(positions, list):
            long_count = sum(1 for p in positions if p.get('side', '').lower() == 'long')
            short_count = len(positions) - long_count
            
            open_positions_count.labels(symbol=symbol, instance=instance, side='long').set(long_count)
            open_positions_count.labels(symbol=symbol, instance=instance, side='short').set(short_count)
        
        # P&L
        unrealized = state.get('unrealized_pnl', state.get('total_unrealized_pnl', 0))
        unrealized_pnl_usd.labels(symbol=symbol, instance=instance).set(unrealized)
        
        daily = state.get('daily_pnl', 0)
        daily_pnl_usd.labels(symbol=symbol, instance=instance).set(daily)
        
        # Grid info
        grid_config = state.get('grid', state.get('grid_config', {}))
        if grid_config:
            ref_price = grid_config.get('reference', grid_config.get('reference_price', 0))
            if ref_price:
                try:
                    grid_reference_price_usd.labels(symbol=symbol, instance=instance).set(float(ref_price))
                except (ValueError, TypeError):
                    pass
        
        # Uptime
        start_time = state.get('start_time', state.get('started_at', 0))
        if start_time:
            if isinstance(start_time, str):
                try:
                    start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00')).timestamp()
                except ValueError:
                    start_time = 0
            
            if start_time > 0:
                uptime = time.time() - start_time
                bot_uptime_seconds.labels(symbol=symbol, instance=instance).set(uptime)
    
    @classmethod
    def _process_monitoring_snapshot(cls, snapshot: Dict[str, Any]):
        """Process monitoring snapshot data"""
        # Price health
        price_health = snapshot.get('price_health', {})
        if price_health:
            symbol = price_health.get('symbol', 'BTCUSD')
            price = price_health.get('current_price', price_health.get('price', 0))
            if price:
                current_price_usd.labels(symbol=symbol).set(price)
        
        # Pre-order stats
        pre_order = snapshot.get('pre_order_stats', {})
        if pre_order:
            # Could extract order decision metrics here
            pass
        
        # TP verification
        tp_verification = snapshot.get('tp_verification', {})
        if tp_verification:
            orphan_count = tp_verification.get('orphan_positions', 0)
            # Could add orphan position metric
            pass
    
    @classmethod
    def collect_options_metrics(cls):
        """Collect metrics from options trading module"""
        try:
            # Try to read options state
            options_files = [
                BASE_DIR / 'data' / 'options_state.json',
                BASE_DIR / 'webui' / 'backend' / 'data' / 'options_state.json',
            ]
            
            for options_file in options_files:
                if options_file.exists():
                    try:
                        with open(options_file, 'r') as f:
                            options_data = json.load(f)
                        cls._process_options_data(options_data)
                        break
                    except Exception as e:
                        logger.debug(f"Could not process options file: {e}")
            
        except Exception as e:
            logger.error(f"Error collecting options metrics: {e}")
    
    @classmethod
    def _process_options_data(cls, data: Dict[str, Any]):
        """Process options trading data"""
        positions = data.get('positions', [])
        
        # Count by type
        calls = [p for p in positions if 'C-' in p.get('symbol', '')]
        puts = [p for p in positions if 'P-' in p.get('symbol', '')]
        
        options_positions_count.labels(option_type='call', symbol='BTC').set(len(calls))
        options_positions_count.labels(option_type='put', symbol='BTC').set(len(puts))
        
        # P&L
        total_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)
        options_unrealized_pnl_usd.labels(option_type='all', symbol='BTC').set(total_pnl)
        
        # Greeks (if available)
        greeks_data = data.get('portfolio_greeks', {})
        if greeks_data:
            for greek in ['delta', 'gamma', 'theta', 'vega']:
                value = greeks_data.get(greek, 0)
                options_greeks.labels(greek=greek, symbol='BTC').set(value)
    
    @classmethod
    def collect_pm2_metrics(cls):
        """Collect metrics from PM2 process manager"""
        try:
            import subprocess
            
            # Get PM2 process list
            result = subprocess.run(
                ['pm2', 'jlist'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                logger.debug("PM2 not available or no processes")
                return
            
            processes = json.loads(result.stdout)
            
            for proc in processes:
                name = proc.get('name', 'unknown')
                
                # Skip non-gridbot processes
                if not any(x in name.lower() for x in ['gridbot', 'guardian', 'webui']):
                    continue
                
                # Extract symbol/instance from name
                symbol = 'BTCUSD'
                instance = 'BTCUSD_LONG'
                
                if 'btc' in name.lower():
                    symbol = 'BTCUSD'
                elif 'eth' in name.lower():
                    symbol = 'ETHUSD'
                
                if 'long' in name.lower():
                    instance = f'{symbol}_LONG'
                elif 'short' in name.lower():
                    instance = f'{symbol}_SHORT'
                else:
                    instance = f'{symbol}_LONG'
                
                # Status
                status = proc.get('pm2_env', {}).get('status', 'stopped')
                bot_state.labels(symbol=symbol, instance=instance).set(
                    1 if status == 'online' else 0
                )
                
                # Memory
                memory_bytes = proc.get('monit', {}).get('memory', 0)
                memory_mb = memory_bytes / (1024 * 1024)
                bot_memory_mb.labels(
                    process_name=name, symbol=symbol, instance=instance
                ).set(memory_mb)
                
                # Uptime
                pm2_uptime = proc.get('pm2_env', {}).get('pm_uptime', 0)
                if pm2_uptime:
                    uptime_seconds = (time.time() * 1000 - pm2_uptime) / 1000
                    bot_uptime_seconds.labels(symbol=symbol, instance=instance).set(uptime_seconds)
                
        except FileNotFoundError:
            logger.debug("PM2 not installed")
        except subprocess.TimeoutExpired:
            logger.warning("PM2 jlist timed out")
        except Exception as e:
            logger.error(f"Error collecting PM2 metrics: {e}")
    
    # =========================================================================
    # MANUAL RECORDING METHODS (for optional integration)
    # =========================================================================
    
    @classmethod
    def record_order_placed(cls, side: str, status: str, symbol: str, 
                           instance: str, order_type: str = 'limit'):
        """Record an order placement (optional - call from bot code)"""
        try:
            orders_placed_total.labels(
                side=side,
                status=status,
                symbol=symbol,
                instance=instance,
                order_type=order_type
            ).inc()
        except Exception as e:
            logger.error(f"Error recording order placed: {e}")
    
    @classmethod
    def record_order_filled(cls, side: str, symbol: str, instance: str):
        """Record an order fill"""
        try:
            orders_filled_total.labels(
                side=side,
                symbol=symbol,
                instance=instance
            ).inc()
        except Exception as e:
            logger.error(f"Error recording order filled: {e}")
    
    @classmethod
    def record_order_cancelled(cls, reason: str, symbol: str, instance: str):
        """Record an order cancellation"""
        try:
            orders_cancelled_total.labels(
                reason=reason,
                symbol=symbol,
                instance=instance
            ).inc()
        except Exception as e:
            logger.error(f"Error recording order cancelled: {e}")
    
    @classmethod
    def record_api_call(cls, endpoint: str, method: str, status_code: int, 
                        duration: float):
        """Record an API call"""
        try:
            api_call_duration_seconds.labels(
                endpoint=endpoint,
                method=method,
                status_code=str(status_code)
            ).observe(duration)
            
            api_calls_total.labels(
                endpoint=endpoint,
                method=method,
                status_code=str(status_code)
            ).inc()
            
            if status_code == 429:
                api_429_errors.labels(endpoint=endpoint).inc()
                
        except Exception as e:
            logger.error(f"Error recording API call: {e}")
    
    @classmethod
    def record_guardian_intervention(cls, action: str, reason: str, 
                                     symbol: str, instance: str):
        """Record a Guardian intervention"""
        try:
            guardian_interventions_total.labels(
                action=action,
                reason=reason,
                symbol=symbol,
                instance=instance
            ).inc()
        except Exception as e:
            logger.error(f"Error recording guardian intervention: {e}")
