"""
Zero DTE Engine - Main Orchestrator
====================================

Autonomous 0DTE strangle strategy with premium balancing.

This is the brain of the bot that:
1. Enters positions at session start
2. Monitors continuously (every 30s)
3. Rebalances when premium imbalance > 20%
4. Rolls strikes when premium < ₹5
5. Exits when BOTH legs < ₹5 OR at 5:15 PM IST

After start, the bot manages everything autonomously.
Only manual intervention: restart or emergency exit.
"""

import asyncio
from datetime import datetime, time, timedelta
from typing import Optional, Dict, Tuple, Any
from loguru import logger
import pytz

from config.schemas.zero_dte_schemas import ZeroDTEConfig
from bot.strategy.zero_dte.config import load_config
from bot.strategy.zero_dte.state_manager import StateManager
from bot.strategy.zero_dte.balancer import PremiumBalancer
from bot.strategy.zero_dte.rollover import StrikeRolloverManager


# Timezone for India
IST = pytz.timezone('Asia/Kolkata')


class ZeroDTEEngine:
    """
    Main orchestrator for 0DTE option selling strategy.
    
    Lifecycle:
    1. start_session() - Entry: Sell strangle
    2. _monitoring_loop() - Continuous monitoring (autonomous)
    3. stop_session() - Exit: Close all positions
    
    Autonomous Actions:
    - Rebalancing (lot adjustment)
    - Strike rollover
    - Profit target exit
    - Time-based exit
    - Stop loss exit
    """
    
    def __init__(self, api_client, config: ZeroDTEConfig = None):
        """
        Initialize 0DTE Engine
        
        Args:
            api_client: Unified API client for Delta Exchange
            config: Optional config (loads from YAML if not provided)
        """
        self.api_client = api_client
        self.config = config or load_config()
        
        # Initialize components
        self.state_manager = StateManager(self.config)
        self.balancer = PremiumBalancer(api_client, self.config, self.state_manager)
        self.rollover_manager = StrikeRolloverManager(api_client, self.config, self.state_manager)
        
        # Session state
        self.session_id: Optional[str] = None
        self.is_running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Position cache
        self._positions: Dict[str, Dict] = {}  # {'CE': {...}, 'PE': {...}}
        
        logger.info(f"ZeroDTEEngine initialized: {self.config.strategy.name}")
    
    # ==========================================================================
    # SESSION LIFECYCLE
    # ==========================================================================
    
    async def start_session(
        self,
        underlying: str = None,
        expiry_date: str = None,
        initial_lots: int = None,
        target_premium_min: float = None,
        target_premium_max: float = None,
        skip_time_check: bool = False
    ) -> Dict:
        """
        Start a new 0DTE trading session
        
        1. Validates entry conditions (time, Guardian, etc.)
        2. Fetches option chain
        3. Selects strikes based on premium targets
        4. Sells strangle (CE + PE)
        5. Starts autonomous monitoring loop
        
        Args:
            underlying: BTC or ETH (default from config)
            expiry_date: YYYY-MM-DD format (default: today)
            initial_lots: Lots per leg (default from config)
            target_premium_min: Min premium for strike selection
            target_premium_max: Max premium for strike selection
        
        Returns:
            Dict with session_id and entry summary
        """
        # Check if already running
        if self.is_running:
            raise RuntimeError("Session already active. Stop current session first.")
        
        # Use defaults from config
        underlying = underlying or self.config.entry.default_underlying
        initial_lots = initial_lots or self.config.entry.initial_lots
        target_premium_min = target_premium_min or self.config.entry.premium_range.min
        target_premium_max = target_premium_max or self.config.entry.premium_range.max
        
        # Default expiry is today
        if expiry_date is None:
            expiry_date = datetime.now(IST).strftime('%Y-%m-%d')
        else:
            # Normalize expiry_date - handle symbol format like 'BTC-2026-01-28' or just date '2026-01-28'
            expiry_date = self._normalize_expiry_date(expiry_date)
        
        logger.info(f"Starting 0DTE session: {underlying} {expiry_date} x{initial_lots} lots")
        
        # Step 1: Validate entry conditions
        await self._validate_entry_conditions(skip_time_check=skip_time_check)
        
        # Step 2: Get option chain
        option_chain = await self._fetch_option_chain(underlying, expiry_date)
        
        # Step 3: Select strikes
        ce_strike, pe_strike = await self._select_strikes(
            underlying, option_chain, target_premium_min, target_premium_max
        )
        
        logger.info(f"Selected strikes: CE={ce_strike}, PE={pe_strike}")
        
        # Step 4: Execute entry trades
        entry_result = await self._execute_entry(
            underlying, expiry_date, ce_strike, pe_strike, initial_lots
        )
        
        # Step 5: Create session record
        session_data = {
            'underlying': underlying,
            'expiry_date': expiry_date,
            'entry_ce_strike': ce_strike,
            'entry_pe_strike': pe_strike,
            'entry_ce_premium': entry_result['ce_premium'],
            'entry_pe_premium': entry_result['pe_premium'],
            'entry_ce_lots': initial_lots,
            'entry_pe_lots': initial_lots,
            'total_premium_collected': entry_result['total_premium']
        }
        
        self.session_id = self.state_manager.create_session(session_data)
        
        # Save initial positions
        self._positions = {
            'CE': {
                'symbol': entry_result['ce_symbol'],
                'strike': ce_strike,
                'lots': initial_lots,
                'entry_premium': entry_result['ce_premium'],
                'leg_type': 'CE'
            },
            'PE': {
                'symbol': entry_result['pe_symbol'],
                'strike': pe_strike,
                'lots': initial_lots,
                'entry_premium': entry_result['pe_premium'],
                'leg_type': 'PE'
            }
        }
        
        for leg_type, pos in self._positions.items():
            self.state_manager.save_position(self.session_id, pos)
        
        # Log entry trades
        for leg in ['CE', 'PE']:
            self.state_manager.log_trade({
                'session_id': self.session_id,
                'trade_type': 'entry',
                'leg_type': leg,
                'symbol': entry_result[f'{leg.lower()}_symbol'],
                'side': 'sell',
                'strike': ce_strike if leg == 'CE' else pe_strike,
                'lots': initial_lots,
                'premium': entry_result[f'{leg.lower()}_premium'],
                'status': 'filled',
                'reason': 'initial_entry'
            })
        
        # Step 6: Start monitoring loop
        self.is_running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        
        logger.success(f"Session started: {self.session_id}")
        logger.info(f"CE: {ce_strike} @ ₹{entry_result['ce_premium']:.2f}")
        logger.info(f"PE: {pe_strike} @ ₹{entry_result['pe_premium']:.2f}")
        logger.info(f"Total premium: ₹{entry_result['total_premium']:.2f}")
        
        return {
            'success': True,
            'session_id': self.session_id,
            'entry_summary': {
                'underlying': underlying,
                'expiry_date': expiry_date,
                'ce_strike': ce_strike,
                'pe_strike': pe_strike,
                'ce_premium': entry_result['ce_premium'],
                'pe_premium': entry_result['pe_premium'],
                'ce_lots': initial_lots,
                'pe_lots': initial_lots,
                'total_premium_collected': entry_result['total_premium']
            }
        }
    
    async def stop_session(self, reason: str = 'manual') -> Dict:
        """
        Stop current session and close all positions
        
        Args:
            reason: Stop reason (manual, profit_target, stop_loss, time_exit, guardian_stop)
        
        Returns:
            Dict with final P&L summary
        """
        if not self.is_running:
            logger.warning("No active session to stop")
            return {'success': False, 'error': 'No active session'}
        
        logger.info(f"Stopping session: {self.session_id} (reason: {reason})")
        
        # Stop monitoring loop
        self.is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # Close all positions
        exit_result = await self._execute_exit()
        
        # Calculate final P&L
        session = self.state_manager.get_session(self.session_id)
        total_collected = session.get('total_premium_collected', 0)
        total_paid = exit_result.get('total_premium_paid', 0)
        realized_pnl = total_collected - total_paid
        
        # Close session in database
        self.state_manager.close_session(self.session_id, reason, realized_pnl)
        
        logger.success(f"Session closed: {self.session_id}")
        logger.info(f"Collected: ₹{total_collected:.2f}, Paid: ₹{total_paid:.2f}")
        logger.info(f"Final P&L: ₹{realized_pnl:.2f}")
        
        # Clear state
        self.session_id = None
        self._positions = {}
        
        return {
            'success': True,
            'final_pnl': realized_pnl,
            'exit_summary': {
                'reason': reason,
                'ce_exit_premium': exit_result.get('ce_premium', 0),
                'pe_exit_premium': exit_result.get('pe_premium', 0),
                'total_premium_paid': total_paid,
                'total_collected': total_collected,
                'profit': realized_pnl
            }
        }
    
    # ==========================================================================
    # AUTONOMOUS MONITORING LOOP
    # ==========================================================================
    
    async def _monitoring_loop(self):
        """
        Main autonomous monitoring loop
        
        Runs every poll_interval_seconds and:
        1. Fetches current premiums
        2. Checks exit conditions (BOTH < ₹5, time, stop loss)
        3. Checks for premium imbalance > 20% → rebalance
        4. Checks for premium < ₹5 on one leg → rollover
        5. Saves monitoring snapshot
        
        This is the BRAIN of autonomous operation.
        """
        poll_interval = self.config.monitoring.poll_interval_seconds
        snapshot_interval = self.config.monitoring.snapshot_interval_seconds
        last_snapshot_time = datetime.now()
        
        logger.info(f"Monitoring loop started (interval: {poll_interval}s)")
        
        while self.is_running:
            try:
                # Get current time in IST
                now_ist = datetime.now(IST)
                
                # Fetch current premiums and Greeks
                ce_data = await self._get_position_data('CE')
                pe_data = await self._get_position_data('PE')
                
                ce_premium = ce_data.get('mark_price', 0)
                pe_premium = pe_data.get('mark_price', 0)
                
                # Update position cache
                self._positions['CE']['current_premium'] = ce_premium
                self._positions['PE']['current_premium'] = pe_premium
                self._positions['CE']['greeks'] = ce_data.get('greeks', {})
                self._positions['PE']['greeks'] = pe_data.get('greeks', {})
                
                # Calculate current state
                ce_lots = self._positions['CE']['lots']
                pe_lots = self._positions['PE']['lots']
                ce_total = ce_premium * ce_lots
                pe_total = pe_premium * pe_lots
                
                # Calculate P&L
                session = self.state_manager.get_session(self.session_id)
                total_collected = session.get('total_premium_collected', 0)
                current_value = ce_total + pe_total
                unrealized_pnl = total_collected - current_value
                
                logger.debug(
                    f"Monitor: CE=₹{ce_premium:.2f}x{ce_lots}, PE=₹{pe_premium:.2f}x{pe_lots}, "
                    f"P&L=₹{unrealized_pnl:.2f}"
                )
                
                # ==============================================
                # CHECK EXIT CONDITIONS (Priority order)
                # ==============================================
                
                # 1. PRIMARY EXIT: Both premiums below threshold
                if ce_premium < self.config.exit.both_legs_below and \
                   pe_premium < self.config.exit.both_legs_below:
                    logger.success(
                        f"✅ PROFIT TARGET: Both legs below ₹{self.config.exit.both_legs_below} "
                        f"(CE=₹{ce_premium:.2f}, PE=₹{pe_premium:.2f})"
                    )
                    await self.stop_session('profit_target')
                    return
                
                # 2. TIME EXIT: Forced exit at 5:15 PM IST
                forced_exit = self._parse_time(self.config.exit.forced_exit_time)
                if now_ist.time() >= forced_exit:
                    logger.warning(f"⏰ TIME EXIT: {now_ist.strftime('%H:%M')} >= {self.config.exit.forced_exit_time}")
                    await self.stop_session('time_exit')
                    return
                
                # 3. STOP LOSS: Maximum loss exceeded
                if unrealized_pnl < -self.config.exit.stop_loss_amount:
                    logger.error(
                        f"🛑 STOP LOSS: P&L ₹{unrealized_pnl:.2f} < -₹{self.config.exit.stop_loss_amount}"
                    )
                    await self.stop_session('stop_loss')
                    return
                
                # 4. GUARDIAN SIGNAL: External risk signal
                if self.config.risk.guardian_enabled:
                    guardian_signal = await self._check_guardian_signal()
                    if guardian_signal == 'STOP' and self.config.risk.emergency.close_on_guardian_stop:
                        logger.error("🛡️ GUARDIAN STOP signal received")
                        await self.stop_session('guardian_stop')
                        return
                
                # ==============================================
                # CHECK REBALANCING CONDITIONS
                # ==============================================
                
                # Calculate imbalance percentage
                avg_total = (ce_total + pe_total) / 2
                if avg_total > 0:
                    imbalance_pct = abs(ce_total - pe_total) / avg_total * 100
                else:
                    imbalance_pct = 0
                
                # Check if rebalancing needed
                if imbalance_pct > self.config.rebalancing.imbalance_threshold_pct:
                    logger.info(f"⚖️ IMBALANCE DETECTED: {imbalance_pct:.1f}% > {self.config.rebalancing.imbalance_threshold_pct}%")
                    
                    await self.balancer.execute_rebalance(
                        self.session_id,
                        self._positions,
                        ce_premium, pe_premium,
                        ce_total, pe_total
                    )
                    
                    # Refresh positions after rebalance
                    self._positions = self.state_manager.get_positions(self.session_id)
                
                # ==============================================
                # CHECK ROLLOVER CONDITIONS
                # ==============================================
                
                # Check if CE needs rollover (premium < ₹5 but PE still > ₹5)
                if ce_premium < self.config.rollover.min_premium_threshold and \
                   pe_premium >= self.config.exit.both_legs_below:
                    logger.info(f"🔄 CE ROLLOVER: Premium ₹{ce_premium:.2f} < ₹{self.config.rollover.min_premium_threshold}")
                    
                    new_position = await self.rollover_manager.execute_rollover(
                        self.session_id,
                        'CE',
                        self._positions['CE']
                    )
                    
                    if new_position:
                        self._positions['CE'] = new_position
                
                # Check if PE needs rollover
                if pe_premium < self.config.rollover.min_premium_threshold and \
                   ce_premium >= self.config.exit.both_legs_below:
                    logger.info(f"🔄 PE ROLLOVER: Premium ₹{pe_premium:.2f} < ₹{self.config.rollover.min_premium_threshold}")
                    
                    new_position = await self.rollover_manager.execute_rollover(
                        self.session_id,
                        'PE',
                        self._positions['PE']
                    )
                    
                    if new_position:
                        self._positions['PE'] = new_position
                
                # ==============================================
                # SAVE MONITORING SNAPSHOT
                # ==============================================
                
                if (datetime.now() - last_snapshot_time).seconds >= snapshot_interval:
                    # Get spot price
                    spot_price = await self._get_spot_price(session['underlying'])
                    
                    # Calculate time to expiry
                    settlement = self._parse_time(self.config.exit.settlement_time)
                    settlement_dt = datetime.combine(now_ist.date(), settlement)
                    settlement_dt = IST.localize(settlement_dt)
                    time_to_expiry = max(0, int((settlement_dt - now_ist).total_seconds() / 60))
                    
                    snapshot = {
                        'session_id': self.session_id,
                        'spot_price': spot_price,
                        'ce_premium': ce_premium,
                        'pe_premium': pe_premium,
                        'ce_lots': ce_lots,
                        'pe_lots': pe_lots,
                        'portfolio_delta': ce_data.get('greeks', {}).get('delta', 0) + 
                                          pe_data.get('greeks', {}).get('delta', 0),
                        'portfolio_gamma': ce_data.get('greeks', {}).get('gamma', 0) + 
                                          pe_data.get('greeks', {}).get('gamma', 0),
                        'portfolio_theta': ce_data.get('greeks', {}).get('theta', 0) + 
                                          pe_data.get('greeks', {}).get('theta', 0),
                        'portfolio_vega': ce_data.get('greeks', {}).get('vega', 0) + 
                                         pe_data.get('greeks', {}).get('vega', 0),
                        'unrealized_pnl': unrealized_pnl,
                        'time_to_expiry_minutes': time_to_expiry
                    }
                    
                    self.state_manager.save_snapshot(snapshot)
                    last_snapshot_time = datetime.now()
                
                # Update session unrealized P&L
                self.state_manager.update_session(self.session_id, {
                    'unrealized_pnl': unrealized_pnl,
                    'current_ce_lots': ce_lots,
                    'current_pe_lots': pe_lots
                })
                
                # Wait for next poll
                await asyncio.sleep(poll_interval)
                
            except asyncio.CancelledError:
                logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(poll_interval)  # Continue despite errors
    
    # ==========================================================================
    # ENTRY LOGIC
    # ==========================================================================
    
    async def _validate_entry_conditions(self, skip_time_check: bool = False):
        """Validate conditions before entry"""
        now_ist = datetime.now(IST)
        
        # Check entry time window (can be skipped for testing/manual override)
        if not skip_time_check:
            earliest = self._parse_time(self.config.entry.earliest_entry_time)
            latest = self._parse_time(self.config.entry.latest_entry_time)
            
            if now_ist.time() < earliest:
                raise RuntimeError(f"Too early for entry. Wait until {self.config.entry.earliest_entry_time} IST")
            
            if now_ist.time() > latest:
                raise RuntimeError(f"Too late for entry. Latest entry is {self.config.entry.latest_entry_time} IST")
        else:
            logger.warning("⚠️ Time check skipped - manual override active")
        
        # Check Guardian signal
        if self.config.risk.guardian_enabled:
            signal = await self._check_guardian_signal()
            if signal == 'STOP':
                raise RuntimeError("Guardian signal is STOP. Entry blocked.")
        
        logger.info("Entry conditions validated ✓")
    
    async def _fetch_option_chain(self, underlying: str, expiry_date: str) -> Dict:
        """Fetch option chain from Delta Exchange"""
        try:
            logger.info(f"Fetching option chain: {underlying} expiring {expiry_date}")
            
            option_chain = await self.api_client.get_option_chain(underlying, expiry_date)
            
            if not option_chain.get('calls') or not option_chain.get('puts'):
                raise RuntimeError(
                    f"No options found for {underlying} expiring {expiry_date}. "
                    "Check if the expiry date is valid and options are listed."
                )
            
            logger.success(
                f"✅ Option chain loaded: {len(option_chain['calls'])} calls, "
                f"{len(option_chain['puts'])} puts"
            )
            
            return option_chain
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch option chain: {e}")
            raise
    
    async def _select_strikes(
        self,
        underlying: str,
        option_chain: Dict,
        target_premium_min: float,
        target_premium_max: float
    ) -> Tuple[float, float]:
        """
        Select CE and PE strikes based on premium targets
        
        Strategy:
        1. Get current spot price
        2. Find CE strike above spot with premium in target range
        3. Find PE strike below spot with premium in target range
        4. Ensure balanced premiums (within 30% of each other)
        """
        # Get spot price
        spot_price = await self._get_spot_price(underlying)
        logger.info(f"Current {underlying} spot: ${spot_price:.2f}")
        
        # Calculate OTM offset
        offset_pct = self.config.entry.strike_offset_pct / 100
        target_ce_strike = spot_price * (1 + offset_pct)
        target_pe_strike = spot_price * (1 - offset_pct)
        
        # Find best CE strike
        ce_strike = await self._find_best_strike(
            option_chain.get('calls', {}),
            target_ce_strike,
            target_premium_min,
            target_premium_max,
            'higher'
        )
        
        # Find best PE strike
        pe_strike = await self._find_best_strike(
            option_chain.get('puts', {}),
            target_pe_strike,
            target_premium_min,
            target_premium_max,
            'lower'
        )
        
        if ce_strike is None or pe_strike is None:
            failed_legs = []
            if ce_strike is None: failed_legs.append("Call (CE)")
            if pe_strike is None: failed_legs.append("Put (PE)")
            raise RuntimeError(f"Could not find suitable strikes for {', '.join(failed_legs)} in premium range [{target_premium_min}, {target_premium_max}]. Try adjusting the premium range.")
        
        return ce_strike, pe_strike
    
    async def _find_best_strike(
        self,
        strikes_data: Dict,
        target_strike: float,
        min_premium: float,
        max_premium: float,
        direction: str
    ) -> Optional[float]:
        """Find best strike with premium in target range"""
        candidates = []
        
        for strike_str, data in strikes_data.items():
            strike = float(strike_str)
            premium = data.get('mark_price', 0)
            
            # Check premium range
            if min_premium <= premium <= max_premium:
                # Check direction (CE should be higher, PE should be lower)
                if direction == 'higher' and strike >= target_strike:
                    candidates.append((strike, premium, abs(premium - (min_premium + max_premium) / 2)))
                elif direction == 'lower' and strike <= target_strike:
                    candidates.append((strike, premium, abs(premium - (min_premium + max_premium) / 2)))
        
        if not candidates:
            logger.warning(f"No {direction} strikes found relative to {target_strike} in premium range [{min_premium}, {max_premium}]")
            return None
        
        # Sort by how close premium is to target middle
        candidates.sort(key=lambda x: x[2])
        best_strike = candidates[0][0]
        
        logger.debug(f"Best strike: {best_strike} (premium: {candidates[0][1]:.2f})")
        return best_strike
    
    async def _execute_entry(
        self,
        underlying: str,
        expiry_date: str,
        ce_strike: float,
        pe_strike: float,
        lots: int
    ) -> Dict:
        """Execute entry trades (sell strangle)"""
        # Build symbols with CORRECT date format (DDMMYY, not YYMMDD)
        # CRITICAL FIX: expiry_date.replace('-', '')[-6:] was giving YYMMDD (wrong!)
        # We need DDMMYY format: e.g., 2026-01-28 → 280126
        from datetime import datetime as dt
        expiry_dt = dt.strptime(expiry_date, '%Y-%m-%d')
        expiry_formatted = expiry_dt.strftime('%d%m%y')  # DDMMYY format
        
        ce_symbol = f"C-{underlying}-{int(ce_strike)}-{expiry_formatted}"
        pe_symbol = f"P-{underlying}-{int(pe_strike)}-{expiry_formatted}"
        
        logger.info(f"Executing entry: SELL {lots} {ce_symbol} + {lots} {pe_symbol}")
        
        # Place CE sell order
        ce_result = await self._place_sell_order(ce_symbol, lots)
        
        # Place PE sell order
        pe_result = await self._place_sell_order(pe_symbol, lots)
        
        ce_premium = ce_result['fill_price']
        pe_premium = pe_result['fill_price']
        total_premium = (ce_premium + pe_premium) * lots
        
        return {
            'ce_symbol': ce_symbol,
            'pe_symbol': pe_symbol,
            'ce_premium': ce_premium,
            'pe_premium': pe_premium,
            'total_premium': total_premium,
            'ce_order_id': ce_result.get('order_id'),
            'pe_order_id': pe_result.get('order_id')
        }
    
    async def _execute_exit(self) -> Dict:
        """Execute exit trades (buy back all positions)"""
        total_paid = 0
        ce_premium = 0
        pe_premium = 0
        
        for leg_type, position in self._positions.items():
            if position.get('lots', 0) > 0:
                symbol = position['symbol']
                lots = position['lots']
                
                logger.info(f"Closing {leg_type}: BUY {lots} {symbol}")
                
                result = await self._place_buy_order(symbol, lots)
                fill_price = result['fill_price']
                total_paid += fill_price * lots
                
                if leg_type == 'CE':
                    ce_premium = fill_price
                else:
                    pe_premium = fill_price
                
                # Log exit trade
                self.state_manager.log_trade({
                    'session_id': self.session_id,
                    'trade_type': 'exit',
                    'leg_type': leg_type,
                    'symbol': symbol,
                    'side': 'buy',
                    'strike': position['strike'],
                    'lots': lots,
                    'premium': fill_price,
                    'status': 'filled',
                    'reason': 'session_close'
                })
        
        return {
            'ce_premium': ce_premium,
            'pe_premium': pe_premium,
            'total_premium_paid': total_paid
        }
    
    # ==========================================================================
    # ORDER EXECUTION
    # ==========================================================================
    
    async def _place_sell_order(self, symbol: str, lots: int) -> Dict:
        """
        Place sell order with maker-first preference
        
        **0DTE SYSTEM** - Uses rest_client.place_order_by_symbol()
        
        1. Try limit order at best bid (maker)
        2. If not filled in timeout, convert to market
        """
        preference = self.config.rebalancing.orders.preference
        timeout = self.config.rebalancing.orders.timeout_seconds
        
        try:
            # Get current ticker
            ticker = await self.api_client.get_option_ticker(symbol)
            quotes = ticker.get('quotes', {})
            best_bid = float(quotes.get('best_bid', 0)) if quotes.get('best_bid') else float(ticker.get('mark_price', 0))
            
            if preference == 'maker_first':
                # Try maker order first (limit at best bid)
                response = await self.api_client.rest_client.place_order_by_symbol(
                    symbol=symbol,
                    side='sell',
                    price=best_bid,
                    size=lots,
                    order_type='limit_order',
                    post_only=True
                )
                
                order_id = response.get('result', {}).get('id')
                
                # Wait for fill
                fill_price = await self._wait_for_fill(order_id, timeout)
                
                if fill_price is None:
                    # Cancel and place market order
                    logger.info(f"Limit order {order_id} not filled, converting to market")
                    product_id = await self.api_client.rest_client.get_product_id(symbol)
                    await self.api_client.rest_client.cancel_order(order_id, product_id)
                    
                    # Market order - no price needed for market orders
                    response = await self.api_client.rest_client.place_order_by_symbol(
                        symbol=symbol,
                        side='sell',
                        size=lots,
                        order_type='market_order'
                    )
                    order_id = response.get('result', {}).get('id')
                    fill_price = await self._wait_for_fill(order_id, 10)
                
                return {'fill_price': fill_price or best_bid, 'order_id': order_id}
            else:
                # Market order directly - no price parameter needed
                response = await self.api_client.rest_client.place_order_by_symbol(
                    symbol=symbol,
                    side='sell',
                    size=lots,
                    order_type='market_order'
                )
                order_id = response.get('result', {}).get('id')
                fill_price = await self._wait_for_fill(order_id, 10)
                
                return {'fill_price': fill_price or best_bid, 'order_id': order_id}
                
        except Exception as e:
            logger.error(f"❌ Sell order failed for {symbol}: {e}")
            raise
    
    async def _place_buy_order(self, symbol: str, lots: int) -> Dict:
        """
        Place buy order to close position
        
        **0DTE SYSTEM** - Always uses market order for quick exit
        """
        try:
            ticker = await self.api_client.get_option_ticker(symbol)
            quotes = ticker.get('quotes', {})
            best_ask = float(quotes.get('best_ask', 0)) if quotes.get('best_ask') else float(ticker.get('mark_price', 0))
            
            # Market order for fast execution - no price parameter needed
            response = await self.api_client.rest_client.place_order_by_symbol(
                symbol=symbol,
                side='buy',
                size=lots,
                order_type='market_order',
                reduce_only=True  # Reduce only for closing positions
            )
            
            order_id = response.get('result', {}).get('id')
            fill_price = await self._wait_for_fill(order_id, 10)
            
            return {'fill_price': fill_price or best_ask, 'order_id': order_id}
            
        except Exception as e:
            logger.error(f"❌ Buy order failed for {symbol}: {e}")
            raise
    
    async def _wait_for_fill(self, order_id: str, timeout: int) -> Optional[float]:
        """Wait for order fill with robust error handling"""
        start = datetime.now()
        
        while (datetime.now() - start).seconds < timeout:
            try:
                order = await self.api_client.get_order(order_id)
                
                # Handle missing or invalid order data
                if not order:
                    logger.warning(f"Order {order_id} not found, retrying...")
                    await asyncio.sleep(0.5)
                    continue
                
                state = order.get('state')
                
                if state == 'filled':
                    fill_price = order.get('average_fill_price')
                    if fill_price is None:
                        logger.error(f"Order {order_id} filled but no fill price available")
                        return None
                    return float(fill_price)
                    
                elif state in ['cancelled', 'rejected']:
                    logger.warning(f"Order {order_id} {state}")
                    return None
                
                # Order still pending
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Error checking order {order_id}: {e}")
                await asyncio.sleep(0.5)
        
        logger.warning(f"Order {order_id} fill timeout after {timeout}s")
        return None  # Timeout
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    async def _get_spot_price(self, underlying: str) -> float:
        """Get current spot price"""
        try:
            price = await self.api_client.get_current_price(underlying)
            return price
        except Exception as e:
            logger.error(f"Failed to get spot price: {e}")
            raise
    
    async def _get_position_data(self, leg_type: str) -> Dict:
        """Get current data for a position"""
        position = self._positions.get(leg_type, {})
        symbol = position.get('symbol')
        
        if not symbol:
            return {}
        
        try:
            ticker = await self.api_client.get_option_ticker(symbol)
            return ticker
        except Exception as e:
            logger.warning(f"Failed to get ticker for {symbol}: {e}")
            return {'mark_price': position.get('current_premium', 0)}
    
    async def _check_guardian_signal(self) -> str:
        """Read Guardian signal file"""
        try:
            signal_file = self.config.risk.guardian_signal_file
            with open(signal_file, 'r') as f:
                signal = f.read().strip().upper()
            return signal
        except FileNotFoundError:
            return 'GO'  # Default to GO if file doesn't exist
        except Exception as e:
            logger.warning(f"Error reading Guardian signal: {e}")
            return 'GO'
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object"""
        parts = time_str.split(':')
        return time(int(parts[0]), int(parts[1]))
    
    def _normalize_expiry_date(self, expiry_date: str) -> str:
        """
        Normalize expiry_date to YYYY-MM-DD format.
        
        Handles multiple formats:
        - 'YYYY-MM-DD' (already correct) -> 'YYYY-MM-DD'
        - 'BTC-YYYY-MM-DD' (symbol format) -> 'YYYY-MM-DD'
        - 'ETH-YYYY-MM-DD' (symbol format) -> 'YYYY-MM-DD'
        
        Args:
            expiry_date: Expiry date string in various formats
            
        Returns:
            Normalized date string in YYYY-MM-DD format
        """
        if not expiry_date:
            return datetime.now(IST).strftime('%Y-%m-%d')
        
        # Check if it's in symbol format like 'BTC-2026-01-28' or 'ETH-2026-01-28'
        # Symbol format has 4 parts when split by '-': [ASSET, YYYY, MM, DD]
        parts = expiry_date.split('-')
        
        if len(parts) == 4:
            # Symbol format: ASSET-YYYY-MM-DD
            # Extract just the date part
            normalized = f"{parts[1]}-{parts[2]}-{parts[3]}"
            logger.debug(f"Normalized expiry from '{expiry_date}' to '{normalized}'")
            return normalized
        elif len(parts) == 3:
            # Already in YYYY-MM-DD format
            return expiry_date
        else:
            # Unknown format, log warning and return as-is
            logger.warning(f"Unknown expiry_date format: '{expiry_date}', using as-is")
            return expiry_date

    
    # ==========================================================================
    # STATUS METHODS
    # ==========================================================================
    
    def get_status(self) -> Dict:
        """Get current engine status"""
        if not self.is_running:
            return {
                'is_active': False,
                'session_id': None,
                'positions': {}
            }
        
        session = self.state_manager.get_session(self.session_id)
        positions = self.state_manager.get_positions(self.session_id)
        
        # Calculate P&L
        total_collected = session.get('total_premium_collected', 0)
        ce_pos = positions.get('CE', {})
        pe_pos = positions.get('PE', {})
        
        ce_current = ce_pos.get('current_premium', 0) * ce_pos.get('lots', 0)
        pe_current = pe_pos.get('current_premium', 0) * pe_pos.get('lots', 0)
        unrealized_pnl = total_collected - ce_current - pe_current
        
        return {
            'is_active': True,
            'session_id': self.session_id,
            'underlying': session.get('underlying'),
            'expiry_date': session.get('expiry_date'),
            'start_time': session.get('start_time'),
            'positions': {
                'CE': {
                    'symbol': ce_pos.get('symbol'),
                    'strike': ce_pos.get('strike'),
                    'lots': ce_pos.get('lots'),
                    'entry_premium': ce_pos.get('entry_premium'),
                    'current_premium': ce_pos.get('current_premium'),
                    'delta': ce_pos.get('delta'),
                    'gamma': ce_pos.get('gamma')
                },
                'PE': {
                    'symbol': pe_pos.get('symbol'),
                    'strike': pe_pos.get('strike'),
                    'lots': pe_pos.get('lots'),
                    'entry_premium': pe_pos.get('entry_premium'),
                    'current_premium': pe_pos.get('current_premium'),
                    'delta': pe_pos.get('delta'),
                    'gamma': pe_pos.get('gamma')
                }
            },
            'pnl': {
                'total_collected': total_collected,
                'unrealized': unrealized_pnl,
                'realized': session.get('realized_pnl', 0)
            },
            'stats': {
                'total_rebalances': session.get('total_rebalances', 0),
                'total_rollovers': session.get('total_rollovers', 0)
            }
        }
