"""
SSR ALGO Monitor - Price Monitoring and Adjustment Trigger

Background daemon that monitors price movement and triggers adjustments
when price dwells in max loss zones for the configured dwell time.

Features:
- Real-time price monitoring via WebSocket or polling
- Max loss zone detection with ±100 tolerance
- 10-minute dwell time tracking before triggering adjustment
- Time window enforcement (only monitor during active hours)
- Auto-adjustment triggering when conditions are met
- Guardian signal integration
- End-time auto-stop
- Backend restart resilience

Created: February 2, 2026
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
import requests

try:
    from .ssr_algo_payoff import get_payoff_calculator
except ImportError:
    from ssr_algo_payoff import get_payoff_calculator

try:
    from .ssr_algo_storage import get_storage
except ImportError:
    from ssr_algo_storage import get_storage

log = logging.getLogger('ssr_algo_monitor')


def add_session_log(session_id: str, message: str, level: str = 'info', data: Dict = None):
    """Helper to add log to session storage."""
    try:
        storage = get_storage()
        storage.add_log(session_id, message, level, data)
    except Exception as e:
        log.error(f"Failed to add session log: {e}")

# Configuration
DEFAULT_DWELL_TIME_MINUTES = 10
DEFAULT_PRICE_TOLERANCE = 100
PRICE_CHECK_INTERVAL_SECONDS = 5
MAIN_BACKEND_URL = "http://localhost:5555"


def check_guardian_signal():
    """Check guardian signal - returns 'GO' if trading allowed."""
    try:
        from webui.backend.trading_control import get_signal
        return get_signal()
    except Exception:
        return 'GO'  # Default to GO if module not available


class CircuitBreaker:
    """
    Circuit breaker for SSR Algo safety limits.
    
    Prevents excessive adjustments and limits losses by enforcing:
    - Max adjustments per day/session
    - Daily loss limits
    - Cooldown period between adjustments
    """
    
    @staticmethod
    def check_breakers(session: Dict) -> tuple:
        """
        Check if any circuit breaker is triggered.
        
        Args:
            session: Session data with circuit_breaker_config
        
        Returns:
            (triggered: bool, reason: str or None)
        """
        config = session.get('circuit_breaker_config', {})
        
        # If circuit breakers disabled, always allow
        if not config.get('enabled', True):
            return False, None
        
        # Check 1: Max adjustments per session (lifetime)
        max_session = config.get('max_adjustments_per_session', 20)
        trigger_count = session.get('trigger_count', 0)
        if trigger_count >= max_session:
            return True, f"Max session adjustments reached ({trigger_count}/{max_session})"
        
        # Check 2: Max adjustments per day
        max_daily = config.get('max_adjustments_per_day', 10)
        daily_adjustments = session.get('daily_adjustments', 0)
        if daily_adjustments >= max_daily:
            return True, f"Max daily adjustments reached ({daily_adjustments}/{max_daily})"
        
        # Check 3: Daily loss limit
        max_loss = config.get('max_daily_loss_usd', 5000)
        daily_pnl = session.get('daily_pnl_usd', 0)
        if daily_pnl < -max_loss:
            return True, f"Daily loss limit exceeded (${abs(daily_pnl):.0f} > ${max_loss})"
        
        # Check 4: Cooldown period between adjustments
        cooldown_min = config.get('cooldown_minutes', 5)
        last_adj_time = session.get('last_adjustment_time')
        if last_adj_time:
            try:
                last_adj = datetime.fromisoformat(last_adj_time)
                elapsed = (datetime.now() - last_adj).total_seconds() / 60
                if elapsed < cooldown_min:
                    return True, f"Cooldown active ({cooldown_min - elapsed:.1f} min remaining)"
            except Exception:
                pass
        
        return False, None
    
    @staticmethod
    def check_greeks_limits(session: Dict, current_greeks: Dict) -> tuple:
        """
        Check if Greeks exposure limits are breached.
        
        Args:
            session: Session data with greeks_limits config
            current_greeks: Current portfolio Greeks {delta, gamma, vega, theta}
        
        Returns:
            (breached: bool, reason: str or None)
        """
        limits = session.get('greeks_limits', {})
        
        # If Greeks limits disabled, always allow
        if not limits.get('enabled', False):
            return False, None
        
        # Check delta exposure
        max_delta = limits.get('max_delta_exposure', 5.0)
        delta = abs(current_greeks.get('delta', 0))
        if delta > max_delta:
            return True, f"Delta exposure exceeded ({delta:.2f} > {max_delta})"
        
        # Check gamma exposure
        max_gamma = limits.get('max_gamma_exposure', 2.0)
        gamma = abs(current_greeks.get('gamma', 0))
        if gamma > max_gamma:
            return True, f"Gamma exposure exceeded ({gamma:.4f} > {max_gamma})"
        
        # Check vega exposure
        max_vega = limits.get('max_vega_exposure', 1000)
        vega = abs(current_greeks.get('vega', 0))
        if vega > max_vega:
            return True, f"Vega exposure exceeded (${vega:.0f} > ${max_vega})"
        
        return False, None


class DwellTracker:
    """
    Tracks how long price has been in a specific zone.
    """
    
    def __init__(self, dwell_threshold_minutes: int = DEFAULT_DWELL_TIME_MINUTES):
        """
        Initialize dwell tracker.
        
        Args:
            dwell_threshold_minutes: Minutes required in zone to trigger
        """
        self.dwell_threshold = timedelta(minutes=dwell_threshold_minutes)
        self.zone_entry_time: Optional[datetime] = None
        self.current_zone: Optional[str] = None
        self.consecutive_checks: int = 0
    
    def update(self, in_zone: bool, zone_name: Optional[str]) -> bool:
        """
        Update dwell tracking with latest price check.
        
        Args:
            in_zone: Whether price is in a max loss zone
            zone_name: 'upper' or 'lower' zone identifier
        
        Returns:
            True if dwell threshold has been exceeded
        """
        now = datetime.now()
        
        if not in_zone:
            # Price exited zone - reset tracking
            self.zone_entry_time = None
            self.current_zone = None
            self.consecutive_checks = 0
            return False
        
        if zone_name != self.current_zone:
            # Entered a different zone - start new tracking
            self.zone_entry_time = now
            self.current_zone = zone_name
            self.consecutive_checks = 1
            log.info(f"Price entered {zone_name} max loss zone at {now}")
            return False
        
        # Still in same zone
        self.consecutive_checks += 1
        
        if self.zone_entry_time is None:
            self.zone_entry_time = now
            return False
        
        # Check if dwell threshold exceeded
        time_in_zone = now - self.zone_entry_time
        
        if time_in_zone >= self.dwell_threshold:
            log.warning(
                f"Dwell threshold exceeded! Price in {zone_name} zone for "
                f"{time_in_zone.total_seconds() / 60:.1f} minutes"
            )
            return True
        
        log.debug(
            f"Price in {zone_name} zone for {time_in_zone.total_seconds() / 60:.1f} minutes "
            f"({self.consecutive_checks} checks)"
        )
        return False
    
    def reset(self):
        """Reset dwell tracking."""
        self.zone_entry_time = None
        self.current_zone = None
        self.consecutive_checks = 0
    
    def get_status(self) -> Dict:
        """Get current dwell status."""
        now = datetime.now()
        time_in_zone = 0
        
        if self.zone_entry_time:
            time_in_zone = (now - self.zone_entry_time).total_seconds() / 60
        
        return {
            'current_zone': self.current_zone,
            'zone_entry_time': self.zone_entry_time.isoformat() if self.zone_entry_time else None,
            'time_in_zone_minutes': round(time_in_zone, 2),
            'dwell_threshold_minutes': self.dwell_threshold.total_seconds() / 60,
            'consecutive_checks': self.consecutive_checks,
            'threshold_exceeded': time_in_zone >= self.dwell_threshold.total_seconds() / 60
        }


class SSRPriceMonitor:
    """
    Background monitor for SSR Algo price tracking and adjustment triggers.
    """
    
    def __init__(self, 
                 session_id: str,
                 get_session_callback: Callable,
                 update_session_callback: Callable,
                 adjustment_callback: Optional[Callable] = None):
        """
        Initialize price monitor.
        
        Args:
            session_id: SSR Algo session ID to monitor
            get_session_callback: Function to get session data
            update_session_callback: Function to update session data
            adjustment_callback: Function to call when adjustment is triggered
        """
        self.session_id = session_id
        self.get_session = get_session_callback
        self.update_session = update_session_callback
        self.adjustment_callback = adjustment_callback
        
        self.payoff_calc = get_payoff_calculator()
        
        # Get session to read dwell time config
        session = get_session_callback(session_id)
        dwell_minutes = session.get('dwell_time_minutes', DEFAULT_DWELL_TIME_MINUTES) if session else DEFAULT_DWELL_TIME_MINUTES
        self.dwell_tracker = DwellTracker(dwell_threshold_minutes=dwell_minutes)
        
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        self.last_price: Optional[float] = None
        self.last_check_time: Optional[datetime] = None
        self.adjustment_count: int = 0
        self._last_regime_check: Optional[datetime] = None
        self._last_rv_check: Optional[datetime] = None
        self._rv_record_counter: int = 0
        
    def start(self):
        """Start the monitoring thread."""
        if self._running:
            log.warning(f"Monitor for session {self.session_id} already running")
            return
        
        self._running = True
        self._paused = False
        self._stop_event.clear()
        
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name=f"SSRMonitor-{self.session_id}",
            daemon=True
        )
        self._thread.start()
        log.info(f"Started price monitor for session {self.session_id}")
    
    def stop(self):
        """Stop the monitoring thread."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        log.info(f"Stopped price monitor for session {self.session_id}")
    
    def pause(self):
        """Pause monitoring (stop checks but keep thread alive)."""
        self._paused = True
        log.info(f"Paused price monitor for session {self.session_id}")
    
    def resume(self):
        """Resume monitoring."""
        self._paused = False
        self.dwell_tracker.reset()  # Reset dwell on resume
        log.info(f"Resumed price monitor for session {self.session_id}")
    
    def get_status(self) -> Dict:
        """Get current monitor status."""
        return {
            'session_id': self.session_id,
            'running': self._running,
            'paused': self._paused,
            'last_price': self.last_price,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'adjustment_count': self.adjustment_count,
            'dwell_status': self.dwell_tracker.get_status()
        }
    
    def _get_current_price(self) -> Optional[float]:
        """
        Fetch current BTC/ETH price from backend.
        
        Priority:
        1. /api/market/spot-price (uses WebSocket → cache → REST)
        2. /api/options/chain (fallback for spot_price)
        
        Returns:
            Current price or None on error
        """
        # Determine underlying from session
        underlying = 'BTC'
        try:
            session = self.get_session(self.session_id)
            if session:
                underlying = session.get('underlying', 'BTC')
        except Exception:
            pass
        
        try:
            # Primary: market spot-price endpoint (WebSocket → cache → REST)
            response = requests.get(
                f"{MAIN_BACKEND_URL}/api/market/spot-price?symbol={underlying}",
                timeout=5
            )
            
            if response.ok:
                data = response.json()
                # Handle different response formats
                if 'price' in data:
                    return float(data['price'])
                if 'btc_price' in data:
                    return float(data['btc_price'])
                if 'index_price' in data:
                    return float(data['index_price'])
        except Exception as e:
            log.debug(f"Failed to get price from market/spot-price: {e}")
        
        try:
            # Fallback: try options chain endpoint for spot price
            response = requests.get(
                f"{MAIN_BACKEND_URL}/api/options/chain?expiry=next",
                timeout=5
            )
            
            if response.ok:
                data = response.json()
                if 'spot_price' in data:
                    return float(data['spot_price'])
        except Exception as e:
            log.debug(f"Failed to get price from options chain: {e}")
        
        return None
    
    def _is_past_end_time(self, session: Dict) -> bool:
        """
        Check if current time is past the session's end time (should auto-stop).
        
        Args:
            session: Session data
        
        Returns:
            True if past end time and session should be stopped
        """
        end_time_str = session.get('end_time')
        
        if not end_time_str:
            return False  # No end time = never auto-stop
        
        now = datetime.now()
        
        try:
            end_parts = end_time_str.split(':')
            end_time = now.replace(
                hour=int(end_parts[0]),
                minute=int(end_parts[1]),
                second=0,
                microsecond=0
            )
            
            # Only auto-stop if we're past end time by at least 1 minute
            # to avoid race conditions
            return now > end_time + timedelta(minutes=1)
            
        except Exception as e:
            log.error(f"Error checking end time: {e}")
            return False
    
    def _is_within_time_window(self, session: Dict) -> bool:
        """
        Check if current time is within the session's active time window.
        
        Args:
            session: Session data
        
        Returns:
            True if within time window
        """
        # Config is stored flat in session, not nested
        start_time_str = session.get('start_time')
        end_time_str = session.get('end_time')
        
        if not start_time_str or not end_time_str:
            # No time window configured - always active
            return True
        
        now = datetime.now()
        
        try:
            # Parse time strings (HH:MM format)
            start_parts = start_time_str.split(':')
            end_parts = end_time_str.split(':')
            
            start_time = now.replace(
                hour=int(start_parts[0]),
                minute=int(start_parts[1]),
                second=0,
                microsecond=0
            )
            end_time = now.replace(
                hour=int(end_parts[0]),
                minute=int(end_parts[1]),
                second=0,
                microsecond=0
            )
            
            # Handle overnight windows (e.g., 22:00 to 06:00)
            if end_time <= start_time:
                # Window spans midnight
                if now >= start_time or now <= end_time:
                    return True
                return False
            
            # Normal window
            return start_time <= now <= end_time
            
        except Exception as e:
            log.error(f"Error parsing time window: {e}")
            return True  # Default to active on error
    
    def _monitor_loop(self):
        """Main monitoring loop with guardian check and end-time auto-stop."""
        log.info(f"Starting monitor loop for session {self.session_id}")
        
        while not self._stop_event.is_set():
            try:
                if self._paused:
                    time.sleep(PRICE_CHECK_INTERVAL_SECONDS)
                    continue
                
                # Get session data
                session = self.get_session(self.session_id)
                if not session:
                    log.warning(f"Session {self.session_id} not found, stopping monitor")
                    break
                
                # Check session status (not 'state')
                status = session.get('status', 'IDLE')
                if status not in ['MONITORING', 'EXECUTING_AUTO_LOOP']:
                    log.debug(f"Session status is {status}, skipping price check")
                    time.sleep(PRICE_CHECK_INTERVAL_SECONDS)
                    continue
                
                # CHECK 1: Guardian signal - respect trading controls
                guardian_signal = check_guardian_signal()
                if guardian_signal != 'GO':
                    log.warning(f"Guardian signal is {guardian_signal}, pausing SSR Algo monitoring")
                    add_session_log(self.session_id, f"⏸️ Guardian signal is {guardian_signal} — monitoring paused", 'warn')
                    time.sleep(PRICE_CHECK_INTERVAL_SECONDS)
                    continue
                
                # CHECK 2: End time auto-stop
                if self._is_past_end_time(session):
                    log.warning(f"Session {self.session_id} past end time, auto-stopping")
                    add_session_log(
                        self.session_id,
                        f"🕐 End time reached — session auto-stopped",
                        'warn'
                    )
                    self.update_session(self.session_id, {
                        'status': 'STOPPED',
                        'stopped_at': datetime.utcnow().isoformat(),
                        'stop_reason': 'End time reached (auto-stop)'
                    })
                    # Stop the monitor
                    self._running = False
                    break
                
                # Check time window
                if not self._is_within_time_window(session):
                    log.debug("Outside time window, skipping price check")
                    time.sleep(PRICE_CHECK_INTERVAL_SECONDS)
                    continue
                
                # Get current price
                current_price = self._get_current_price()
                if current_price is None:
                    log.warning("Could not fetch current price")
                    time.sleep(PRICE_CHECK_INTERVAL_SECONDS)
                    continue
                
                self.last_price = current_price
                self.last_check_time = datetime.now()

                # === DTE Phase Check (Phase 6) ===
                _dte_override_threshold = None
                try:
                    from .ssr_algo_dte_manager import get_dte_manager
                    dte_mgr = get_dte_manager()
                    dte_phase = dte_mgr.get_dte_phase(session)

                    # Log phase transitions
                    current_phase = session.get('current_dte_phase')
                    if current_phase != dte_phase.get('phase'):
                        add_session_log(self.session_id,
                            f"DTE Phase: {dte_phase['phase_name']} (DTE={dte_phase['dte']:.1f})",
                            'info')
                        self.update_session(self.session_id, {
                            'current_dte_phase': dte_phase['phase']
                        })

                    # Get DTE-adjusted delta threshold for this cycle
                    cycle_config = dte_mgr.apply_dte_adjustments(session, dte_phase)
                    _dte_override_threshold = cycle_config.get('delta_threshold')
                except Exception as e:
                    log.debug(f"DTE phase check skipped: {e}")
                # === End DTE Phase Check ===

                # === Regime Check (Phase 7) — every 5 minutes ===
                try:
                    now = datetime.now()
                    should_check_regime = (
                        self._last_regime_check is None or
                        (now - self._last_regime_check).total_seconds() >= 300
                    )
                    if should_check_regime and current_price:
                        from .ssr_algo_regime import get_regime_adapter
                        regime_adapter = get_regime_adapter()
                        underlying = session.get('underlying', 'BTC')
                        regime_adj = regime_adapter.get_regime_adjustments(underlying, current_price)
                        self._last_regime_check = now

                        prev_regime = session.get('current_regime')
                        new_regime = regime_adj.get('regime')
                        if prev_regime != new_regime:
                            add_session_log(self.session_id,
                                f"Regime: {regime_adj.get('description', new_regime)}",
                                'info')
                            self.update_session(self.session_id, {
                                'current_regime': new_regime,
                                'regime_details': regime_adj.get('details', {})
                            })
                except Exception as e:
                    log.debug(f"Regime check skipped: {e}")
                # === End Regime Check ===

                # === RV/IV Tracker (Phase 10) ===
                try:
                    from .ssr_algo_rv_tracker import get_rv_tracker
                    rv_tracker = get_rv_tracker()
                    underlying = session.get('underlying', 'BTC')

                    # Record price every ~60 cycles (~5 min at 5s interval)
                    self._rv_record_counter += 1
                    if self._rv_record_counter >= 60:
                        self._rv_record_counter = 0
                        rv_tracker.record_price(underlying, current_price)

                        # Compute RV/IV snapshot every ~10 min
                        now = datetime.now()
                        if (self._last_rv_check is None or
                                (now - self._last_rv_check).total_seconds() >= 600):
                            self._last_rv_check = now
                            expiry = session.get('expiry', '')
                            if expiry:
                                rv_snapshot = rv_tracker.get_rv_iv_snapshot(underlying, expiry)
                                if rv_snapshot.get('signal') != 'INSUFFICIENT_DATA':
                                    self.update_session(self.session_id, {
                                        'rv_iv_snapshot': rv_snapshot
                                    })
                                    # Warn if realized vol exceeds implied
                                    if rv_snapshot.get('signal') == 'DANGER':
                                        add_session_log(self.session_id,
                                            f"RV/IV WARNING: {rv_snapshot.get('message', '')}",
                                            'warn')
                except Exception as e:
                    log.debug(f"RV tracker skipped: {e}")
                # === End RV/IV Tracker ===

                # === Multi-Session Correlation Monitor (Phase 10) ===
                try:
                    from .ssr_algo_rv_tracker import get_rv_tracker
                    rv_tracker = get_rv_tracker()
                    underlying = session.get('underlying', 'BTC')

                    # Only check every ~5 minutes, and only if multiple underlyings tracked
                    price_histories = rv_tracker._price_history
                    if (len(price_histories) >= 2 and
                            self._rv_record_counter == 0 and  # piggyback on RV cycle
                            self._last_rv_check is not None):
                        # Calculate BTC-ETH correlation if both exist
                        symbols = list(price_histories.keys())
                        if len(symbols) >= 2:
                            prices_a = [p for _, p in price_histories[symbols[0]]]
                            prices_b = [p for _, p in price_histories[symbols[1]]]
                            min_len = min(len(prices_a), len(prices_b), 30)
                            if min_len >= 10:
                                a = prices_a[-min_len:]
                                b = prices_b[-min_len:]
                                import statistics
                                mean_a = statistics.mean(a)
                                mean_b = statistics.mean(b)
                                std_a = statistics.stdev(a) if len(a) > 1 else 1
                                std_b = statistics.stdev(b) if len(b) > 1 else 1
                                if std_a > 0 and std_b > 0:
                                    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / (min_len - 1)
                                    correlation = cov / (std_a * std_b)
                                    correlation = max(-1.0, min(1.0, correlation))

                                    prev_corr = session.get('cross_asset_correlation')
                                    self.update_session(self.session_id, {
                                        'cross_asset_correlation': round(correlation, 3)
                                    })

                                    # Log significant correlation changes
                                    if prev_corr is not None and abs(correlation - prev_corr) > 0.1:
                                        level = 'warn' if correlation > 0.95 else 'info'
                                        msg = (f"Cross-asset correlation: {correlation:.2f} — "
                                               f"{'HIGH RISK: portfolio heavily correlated' if correlation > 0.95 else 'diversification benefit'}")
                                        add_session_log(self.session_id, msg, level)
                except Exception as e:
                    log.debug(f"Correlation check skipped: {e}")
                # === End Correlation Monitor ===

                # === Live Greeks & MTM Calculation (Phase 1) ===
                if session.get('positions'):
                    try:
                        from .ssr_algo_greeks import get_greeks_fetcher
                        greeks_fetcher = get_greeks_fetcher()

                        position_greeks = greeks_fetcher.fetch_position_greeks(session)

                        if position_greeks:
                            portfolio_greeks = greeks_fetcher.calculate_portfolio_greeks(
                                position_greeks, session.get('underlying', 'BTC')
                            )
                            mtm_pnl = greeks_fetcher.calculate_mtm_pnl(session, position_greeks)

                            self.update_session(self.session_id, {
                                'live_greeks': portfolio_greeks,
                                'live_pnl': mtm_pnl,
                                'greeks_updated_at': datetime.utcnow().isoformat()
                            })
                    except Exception as e:
                        log.debug(f"Greeks/MTM calculation skipped: {e}")
                # === End Live Greeks & MTM ===

                # Re-read session to get updated live_pnl/live_greeks
                session = self.get_session(self.session_id)
                if not session:
                    break

                # === Exit Condition Checks (Phase 2) ===
                if session.get('positions') and session.get('live_pnl'):
                    try:
                        from .ssr_algo_exit_manager import get_exit_manager
                        exit_mgr = get_exit_manager()

                        exit_check = exit_mgr.check_exit_conditions(session)

                        if exit_check.get('should_exit'):
                            reason = exit_check['reason']
                            details = exit_check.get('details', {})
                            log.warning(f"[{self.session_id}] EXIT TRIGGERED: {reason}")
                            add_session_log(self.session_id,
                                f"EXIT TRIGGERED: {reason} — {details.get('message', '')}",
                                'trigger')

                            exit_result = exit_mgr.execute_full_exit(self.session_id, reason)

                            if exit_result.get('success'):
                                add_session_log(self.session_id,
                                    f"All positions closed. Reason: {reason}. Orders: {exit_result.get('orders_placed', 0)}",
                                    'success')
                                self._running = False
                                break
                            else:
                                add_session_log(self.session_id,
                                    f"Exit attempted but had issues: {exit_result.get('error')}",
                                    'error')
                    except Exception as e:
                        log.debug(f"Exit check skipped: {e}")
                # === End Exit Condition Checks ===

                # === Delta-Based Hedging (Phase 3) ===
                if session.get('positions') and session.get('live_greeks'):
                    try:
                        from .ssr_algo_delta_hedger import get_delta_hedger
                        delta_hedger = get_delta_hedger()

                        hedge_config = session.get('delta_hedge_config', {})
                        if hedge_config.get('enabled', False):
                            hedge_check = delta_hedger.check_delta_hedge_needed(
                                session, override_threshold=_dte_override_threshold)

                            if hedge_check.get('hedge_needed'):
                                hedge_type = hedge_check['hedge_type']
                                direction = hedge_check['direction']
                                current_delta = hedge_check['current_delta']

                                add_session_log(self.session_id,
                                    f"Delta hedge triggered: {hedge_type} ({direction}) — delta={current_delta:.4f}",
                                    'trigger')

                                if hedge_type == 'micro':
                                    result = delta_hedger.execute_micro_hedge(session, direction)
                                elif hedge_type == 'standard':
                                    result = delta_hedger.execute_standard_hedge(session, direction)
                                elif hedge_type == 'emergency':
                                    result = delta_hedger.execute_emergency_hedge(session, direction)
                                else:
                                    result = {'success': False, 'error': f'Unknown hedge type: {hedge_type}'}

                                if result.get('success'):
                                    add_session_log(self.session_id,
                                        f"{hedge_type} hedge completed. Orders: {result.get('orders_placed', 0)}",
                                        'success')
                                else:
                                    add_session_log(self.session_id,
                                        f"{hedge_type} hedge failed: {result.get('error', 'unknown')}",
                                        'error')
                    except Exception as e:
                        log.debug(f"Delta hedge check skipped: {e}")
                # === End Delta-Based Hedging ===

                # Calculate payoff and find max loss points
                payoff_data = self.payoff_calc.calculate_session_payoff(session)
                max_loss_points = payoff_data.get('max_loss_points', {})
                
                max_loss_upper = max_loss_points.get('max_loss_upper')
                max_loss_lower = max_loss_points.get('max_loss_lower')
                
                # Tolerance is stored flat in session, not nested in config
                tolerance = session.get('price_tolerance', DEFAULT_PRICE_TOLERANCE)
                
                # Check if price is in max loss zone
                in_zone, zone_name = self.payoff_calc.is_price_in_max_loss_zone(
                    current_price,
                    max_loss_upper,
                    max_loss_lower,
                    tolerance
                )
                
                # Update dwell tracking
                threshold_exceeded = self.dwell_tracker.update(in_zone, zone_name)
                
                # Log when entering max loss zone for the first time
                if in_zone and self.dwell_tracker.consecutive_checks == 1:
                    add_session_log(
                        self.session_id,
                        f"⚠️ Price ${current_price:,.0f} entered {zone_name.upper()} max loss zone",
                        'trigger'
                    )
                
                # Log dwell progress every 2 minutes
                if in_zone and self.dwell_tracker.zone_entry_time:
                    time_in_zone = (datetime.now() - self.dwell_tracker.zone_entry_time).total_seconds() / 60
                    if time_in_zone > 0 and int(time_in_zone * 10) % 20 == 0:  # Every ~2 mins
                        remaining = self.dwell_tracker.dwell_threshold.total_seconds() / 60 - time_in_zone
                        if remaining > 0:
                            add_session_log(
                                self.session_id,
                                f"⏱️ In {zone_name} zone for {time_in_zone:.1f} min ({remaining:.1f} min until trigger)",
                                'warn'
                            )
                
                if threshold_exceeded:
                    # If delta hedging is enabled, extend dwell as backstop
                    # (delta hedger should have caught it first)
                    if session.get('delta_hedge_config', {}).get('enabled', False):
                        backstop_dwell_min = 20  # 20 min when delta hedging active
                        if self.dwell_tracker.zone_entry_time:
                            actual_time = (datetime.now() - self.dwell_tracker.zone_entry_time).total_seconds() / 60
                            if actual_time < backstop_dwell_min:
                                # Not enough time for backstop — skip this cycle
                                threshold_exceeded = False

                if threshold_exceeded:
                    # CHECK 3: Circuit breakers before adjustment
                    breaker_triggered, breaker_reason = CircuitBreaker.check_breakers(session)
                    
                    if breaker_triggered:
                        log.warning(f"CIRCUIT BREAKER TRIGGERED: {breaker_reason}")
                        add_session_log(
                            self.session_id,
                            f"🛑 CIRCUIT BREAKER: {breaker_reason}",
                            'error'
                        )
                        self.update_session(self.session_id, {
                            'status': 'STOPPED',
                            'stopped_at': datetime.utcnow().isoformat(),
                            'stop_reason': f'Circuit breaker: {breaker_reason}',
                            'circuit_breaker_triggered': True,
                            'circuit_breaker_reason': breaker_reason
                        })
                        self._running = False
                        break
                    
                    # Trigger adjustment!
                    log.warning(
                        f"ADJUSTMENT TRIGGER: Price {current_price} in {zone_name} "
                        f"max loss zone for {self.dwell_tracker.dwell_threshold}"
                    )
                    add_session_log(
                        self.session_id,
                        f"🚨 ADJUSTMENT TRIGGERED! Price ${current_price:,.0f} in {zone_name} zone for 10+ minutes",
                        'trigger'
                    )
                    
                    self._trigger_adjustment(session, zone_name, current_price)
                    
                    # Reset dwell tracker after triggering
                    self.dwell_tracker.reset()
                
            except Exception as e:
                log.error(f"Error in monitor loop: {e}", exc_info=True)
            
            # Wait before next check
            self._stop_event.wait(PRICE_CHECK_INTERVAL_SECONDS)
        
        log.info(f"Monitor loop ended for session {self.session_id}")
    
    def _trigger_adjustment(self, session: Dict, zone: str, current_price: float):
        """
        Trigger a full adjustment - select new strikes and execute auto-loop.
        
        This is the core auto-adjustment logic:
        1. Calculate NEW ATM based on current spot
        2. Select new strikes using same premium percentage rules
        3. Fire configured number of auto-loop rounds
        4. Place limit orders at $3 for new sell legs
        5. Recalculate max loss points (include all positions)
        6. Return to MONITORING state
        
        Args:
            session: Current session data
            zone: 'upper' or 'lower' zone that triggered
            current_price: Price that triggered adjustment
        """
        self.adjustment_count += 1
        
        log.warning(f"[{self.session_id}] EXECUTING ADJUSTMENT #{self.adjustment_count} - "
                   f"Zone: {zone}, Trigger Price: {current_price}")
        add_session_log(
            self.session_id,
            f"🔄 Starting adjustment #{self.adjustment_count}...",
            'order'
        )
        
        # Update session status to EXECUTING
        self.update_session(self.session_id, {
            'status': 'EXECUTING_AUTO_LOOP',
            'current_adjustment': self.adjustment_count
        })
        
        try:
            # Import here to avoid circular imports
            from .ssr_algo_engine import get_strike_selector
            from .ssr_algo_executor import get_executor
            from .ssr_algo_storage import get_storage
            
            storage = get_storage()
            selector = get_strike_selector()
            executor = get_executor()
            
            # Step 1: Select new strikes based on CURRENT spot price
            log.info(f"[{self.session_id}] Selecting new strikes for adjustment")
            add_session_log(self.session_id, f"Looking for new ATM at ${current_price:,.0f}", 'info')
            
            strikes = selector.select_all_strikes(
                session['underlying'],
                session['expiry'],
                session.get('strike_config', {})
            )
            
            if not strikes.get('success'):
                log.error(f"[{self.session_id}] Strike selection failed: {strikes.get('error')}")
                add_session_log(self.session_id, f"❌ Strike selection failed: {strikes.get('error')}", 'error')
                # Record failed adjustment and return to monitoring
                self._record_adjustment_failure(session, zone, current_price, strikes.get('error'))
                self.update_session(self.session_id, {'status': 'MONITORING'})
                return
            
            log.info(f"[{self.session_id}] New strikes selected: ATM={strikes['atm']['strike']}")
            add_session_log(
                self.session_id, 
                f"✅ New ATM: {strikes['atm']['strike']} (CE@${strikes['atm']['ce_premium']:.2f} | PE@${strikes['atm']['pe_premium']:.2f})", 
                'success'
            )
            
            # Step 2: Build orders from selected strikes
            orders = selector.build_orders_from_strikes(
                strikes,
                session['underlying'],
                session['expiry']
            )
            
            # Step 3: Execute auto-loop rounds with progress tracking
            rounds = session.get('auto_loop_rounds', 2)
            order_type = session.get('order_type', 'ssr')
            
            log.info(f"[{self.session_id}] Executing {rounds} auto-loop rounds for adjustment")
            
            # Progress callback to track adjustment orders as pending
            # This is CRITICAL: without it, adjustment orders are never tracked
            # and never move to filled_orders, so payoff excludes them
            def adjustment_progress_callback(round_num, total, round_result):
                try:
                    if round_result.get('success'):
                        order_results = round_result.get('results', [])
                        if not isinstance(order_results, list):
                            order_results = []
                        
                        add_session_log(self.session_id, f"━━━━━ Adjustment Round {round_num}/{total} ━━━━━", 'info')
                        
                        pending_orders = []
                        for r in order_results:
                            if not isinstance(r, dict):
                                continue
                            
                            symbol = r.get('symbol', 'Unknown')
                            side = r.get('side', '?')
                            size = r.get('size', 0)
                            order_id = r.get('order_id') or ''
                            if not isinstance(order_id, str):
                                order_id = str(order_id) if order_id else ''
                            
                            emoji = '🟢' if str(side).upper() == 'BUY' else '🔴'
                            order_id_display = order_id[:8] if order_id else 'N/A'
                            add_session_log(self.session_id, f"  {emoji} {str(side).upper()} {symbol} x{abs(size) if isinstance(size, (int, float)) else size} (#{order_id_display})", 'order')
                            
                            if order_id:
                                pending_orders.append({
                                    'order_id': order_id,
                                    'symbol': r.get('symbol', ''),
                                    'side': r.get('side', ''),
                                    'size': r.get('size', 0),
                                    'round': round_num,
                                    'placed_at': datetime.now().isoformat(),
                                    'adjustment': self.adjustment_count
                                })
                        
                        if pending_orders:
                            storage.add_pending_orders(self.session_id, pending_orders)
                            add_session_log(self.session_id, f"⏳ {len(pending_orders)} adjustment orders pending confirmation...", 'info')
                    else:
                        error_msg = round_result.get('error', 'Unknown error')
                        add_session_log(self.session_id, f"⚠️ Adjustment round {round_num}/{total} had issues: {error_msg}", 'warn')
                except Exception as e:
                    log.exception(f"[{self.session_id}] Error in adjustment progress callback: {e}")
            
            result = executor.execute_rounds(
                session_id=self.session_id,
                orders=orders,
                rounds=rounds,
                order_type=order_type,
                progress_callback=adjustment_progress_callback
            )
            
            if result.get('success'):
                # Get the number of completed rounds to calculate actual position sizes
                completed_rounds = result.get('completed_rounds', 1)
                
                # Step 4: Create position group for this adjustment
                # Position sizes are multiplied by the number of completed rounds
                # CRITICAL: Do NOT mark as filled=True yet - filled only when order actually fills
                position_group = {
                    'trigger_id': self.adjustment_count,
                    'trigger_zone': zone,
                    'trigger_price': current_price,
                    'atm_strike': strikes['atm']['strike'],
                    'atm_ce_premium': strikes['atm']['ce_premium'],
                    'atm_pe_premium': strikes['atm']['pe_premium'],
                    'rounds_executed': completed_rounds,
                    'atm_ce': {
                        'symbol': strikes['atm']['ce_symbol'],
                        'size': -1 * completed_rounds,  # Multiply by rounds
                        'filled': False,  # Will be set to True when order fills
                        'entry_price': strikes['atm']['ce_premium']
                    },
                    'atm_pe': {
                        'symbol': strikes['atm']['pe_symbol'],
                        'size': -1 * completed_rounds,  # Multiply by rounds
                        'filled': False,
                        'entry_price': strikes['atm']['pe_premium']
                    },
                    'otm_ce_buy': {
                        'symbol': strikes['otm_ce_buy']['symbol'],
                        'size': 2 * completed_rounds,  # Multiply by rounds
                        'filled': False,
                        'selected_premium': strikes['otm_ce_buy']['premium'],
                        'entry_price': strikes['otm_ce_buy']['premium']
                    },
                    'otm_pe_buy': {
                        'symbol': strikes['otm_pe_buy']['symbol'],
                        'size': 2 * completed_rounds,  # Multiply by rounds
                        'filled': False,
                        'selected_premium': strikes['otm_pe_buy']['premium'],
                        'entry_price': strikes['otm_pe_buy']['premium']
                    },
                    'far_otm_ce': {
                        'symbol': strikes['far_otm_ce']['symbol'],
                        'size': -1 * completed_rounds,  # Multiply by rounds
                        'filled': False,
                        'selected_premium': strikes['far_otm_ce']['premium'],
                        'entry_price': strikes['far_otm_ce']['premium']
                    },
                    'far_otm_pe': {
                        'symbol': strikes['far_otm_pe']['symbol'],
                        'size': -1 * completed_rounds,  # Multiply by rounds
                        'filled': False,
                        'selected_premium': strikes['far_otm_pe']['premium'],
                        'entry_price': strikes['far_otm_pe']['premium']
                    },
                    'executed_at': datetime.utcnow().isoformat()
                }
                
                # Add position group to session
                storage.add_position_group(self.session_id, position_group)
                add_session_log(self.session_id, f"📊 New position group #{self.adjustment_count} recorded ({completed_rounds} rounds)", 'success')
                
                # Step 5: Place limit exit orders at $3 for new sell legs (multiplied by rounds)
                sell_positions = [
                    {'symbol': strikes['atm']['ce_symbol'], 'size': 1 * completed_rounds},
                    {'symbol': strikes['atm']['pe_symbol'], 'size': 1 * completed_rounds},
                    {'symbol': strikes['far_otm_ce']['symbol'], 'size': 1 * completed_rounds},
                    {'symbol': strikes['far_otm_pe']['symbol'], 'size': 1 * completed_rounds}
                ]
                executor.place_limit_exit_orders(self.session_id, sell_positions, exit_price=3.0)
                add_session_log(self.session_id, f"🎯 Placed limit exit orders at $3 for {len(sell_positions) * completed_rounds} new sell legs", 'order')
                
                # Step 6: Record successful adjustment
                adjustment_record = {
                    'adjustment_number': self.adjustment_count,
                    'timestamp': datetime.now().isoformat(),
                    'zone': zone,
                    'trigger_price': current_price,
                    'new_atm_strike': strikes['atm']['strike'],
                    'rounds_executed': result.get('completed_rounds', rounds),
                    'status': 'SUCCESS'
                }
                
                adjustments = session.get('adjustments', [])
                adjustments.append(adjustment_record)
                
                # Update session back to MONITORING with circuit breaker tracking
                daily_adj = session.get('daily_adjustments', 0) + 1
                
                self.update_session(self.session_id, {
                    'status': 'MONITORING',
                    'trigger_count': self.adjustment_count,
                    'daily_adjustments': daily_adj,
                    'last_adjustment_time': datetime.now().isoformat(),
                    'adjustments': adjustments,
                    'last_adjustment': adjustment_record
                })
                
                # Step 7: RECALCULATE MAX LOSS ZONES from combined payoff
                # After adding new positions, the combined payoff shape changes
                # The new max loss zones may be different from the initial ones
                # This is CRITICAL to prevent re-triggering at the same old zones
                try:
                    updated_session = self.get_session(self.session_id)
                    if updated_session:
                        payoff_data = self.payoff_calc.calculate_session_payoff(updated_session)
                        new_max_loss = payoff_data.get('max_loss_points', {})
                        new_triggers = payoff_data.get('adjustment_triggers', {})
                        
                        new_upper = new_max_loss.get('max_loss_upper')
                        new_lower = new_max_loss.get('max_loss_lower')
                        
                        # Store new max loss zones in session for reference
                        self.update_session(self.session_id, {
                            'max_loss_upper': new_upper,
                            'max_loss_lower': new_lower
                        })
                        
                        log.info(f"[{self.session_id}] Recalculated max loss zones: "
                                f"Upper={new_upper}, Lower={new_lower}")
                        
                        add_session_log(
                            self.session_id,
                            f"📍 NEW trigger zones (recalculated from combined payoff): "
                            f"⬇️ ${new_lower:,.0f} | ⬆️ ${new_upper:,.0f}" if new_lower and new_upper
                            else f"📍 Trigger zones recalculated: Upper={new_upper}, Lower={new_lower}",
                            'trigger'
                        )
                except Exception as recalc_err:
                    log.error(f"[{self.session_id}] Error recalculating max loss zones: {recalc_err}")
                    add_session_log(self.session_id, f"⚠️ Could not recalculate trigger zones: {recalc_err}", 'warn')
                
                log.info(f"[{self.session_id}] Adjustment #{self.adjustment_count} completed successfully")
                add_session_log(
                    self.session_id,
                    f"🟢 Adjustment #{self.adjustment_count} completed! New ATM: {strikes['atm']['strike']}",
                    'success'
                )
                add_session_log(self.session_id, f"👁️ Resuming price monitoring with NEW trigger zones...", 'info')
                
            else:
                # Execution failed
                log.error(f"[{self.session_id}] Adjustment execution failed: {result.get('error')}")
                add_session_log(
                    self.session_id,
                    f"❌ Adjustment execution failed: {result.get('error')}",
                    'error'
                )
                self._record_adjustment_failure(session, zone, current_price, result.get('error'))
                self.update_session(self.session_id, {'status': 'MONITORING'})
                add_session_log(self.session_id, "👁️ Returning to monitoring...", 'warn')
                
        except Exception as e:
            log.exception(f"[{self.session_id}] Adjustment failed with exception")
            add_session_log(self.session_id, f"❌ Adjustment failed: {str(e)}", 'error')
            self._record_adjustment_failure(session, zone, current_price, str(e))
            # Return to monitoring - don't stop the algo on adjustment failure
            self.update_session(self.session_id, {'status': 'MONITORING'})
            add_session_log(self.session_id, "👁️ Returning to monitoring...", 'warn')
    
    def _record_adjustment_failure(self, session: Dict, zone: str, trigger_price: float, error: str):
        """Record a failed adjustment attempt."""
        adjustment_record = {
            'adjustment_number': self.adjustment_count,
            'timestamp': datetime.now().isoformat(),
            'zone': zone,
            'trigger_price': trigger_price,
            'status': 'FAILED',
            'error': error
        }
        
        adjustments = session.get('adjustments', [])
        adjustments.append(adjustment_record)
        
        self.update_session(self.session_id, {
            'adjustments': adjustments,
            'last_adjustment': adjustment_record
        })


# Active monitors registry
_active_monitors: Dict[str, SSRPriceMonitor] = {}
_monitors_lock = threading.Lock()


def start_session_monitor(session_id: str,
                          get_session_callback: Callable,
                          update_session_callback: Callable,
                          adjustment_callback: Optional[Callable] = None) -> SSRPriceMonitor:
    """
    Start a monitor for a session.
    
    Args:
        session_id: Session ID
        get_session_callback: Function to get session data
        update_session_callback: Function to update session
        adjustment_callback: Optional adjustment trigger callback
    
    Returns:
        The monitor instance
    """
    with _monitors_lock:
        if session_id in _active_monitors:
            log.warning(f"Monitor for session {session_id} already exists")
            return _active_monitors[session_id]
        
        monitor = SSRPriceMonitor(
            session_id=session_id,
            get_session_callback=get_session_callback,
            update_session_callback=update_session_callback,
            adjustment_callback=adjustment_callback
        )
        
        monitor.start()
        _active_monitors[session_id] = monitor
        
        return monitor


def stop_session_monitor(session_id: str):
    """Stop a session's monitor."""
    with _monitors_lock:
        monitor = _active_monitors.pop(session_id, None)
        if monitor:
            monitor.stop()


def pause_session_monitor(session_id: str):
    """Pause a session's monitor."""
    with _monitors_lock:
        monitor = _active_monitors.get(session_id)
        if monitor:
            monitor.pause()


def resume_session_monitor(session_id: str):
    """Resume a session's monitor."""
    with _monitors_lock:
        monitor = _active_monitors.get(session_id)
        if monitor:
            monitor.resume()


def get_session_monitor_status(session_id: str) -> Optional[Dict]:
    """Get status of a session's monitor."""
    with _monitors_lock:
        monitor = _active_monitors.get(session_id)
        if monitor:
            return monitor.get_status()
        return None


def get_all_monitor_statuses() -> Dict[str, Dict]:
    """Get status of all active monitors."""
    with _monitors_lock:
        return {
            session_id: monitor.get_status()
            for session_id, monitor in _active_monitors.items()
        }


def restore_monitors_on_startup():
    """
    Restore monitors for sessions in MONITORING or PAUSED state.
    
    This should be called when the backend starts to resume monitoring
    for any sessions that were active before the backend stopped.
    
    This ensures the algo continues running even after backend restarts.
    """
    try:
        from .ssr_algo_storage import get_storage
        
        storage = get_storage()
        all_sessions = storage.list_sessions(active_only=False)
        
        restored_count = 0
        
        for session in all_sessions:
            session_id = session.get('session_id')
            status = session.get('status')
            
            # Only restore MONITORING and PAUSED sessions
            if status in ['MONITORING', 'PAUSED']:
                log.info(f"Restoring monitor for session {session_id} (status: {status})")
                
                # Check if monitor already exists
                if session_id in _active_monitors:
                    log.debug(f"Monitor already exists for {session_id}")
                    continue
                
                # Start monitor
                monitor = SSRPriceMonitor(
                    session_id=session_id,
                    get_session_callback=storage.get_session,
                    update_session_callback=storage.update_session,
                    adjustment_callback=None  # Built-in adjustment in monitor
                )
                
                monitor.start()
                
                # If session was paused, pause the monitor
                if status == 'PAUSED':
                    monitor.pause()
                
                with _monitors_lock:
                    _active_monitors[session_id] = monitor
                
                restored_count += 1
                log.info(f"Monitor restored for session {session_id}")
        
        if restored_count > 0:
            log.info(f"SSR Algo: Restored {restored_count} monitors on startup")
        else:
            log.info("SSR Algo: No monitors to restore on startup")
        
        return restored_count
        
    except Exception as e:
        log.exception(f"Failed to restore monitors on startup: {e}")
        return 0
