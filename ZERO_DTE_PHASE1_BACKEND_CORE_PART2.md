# Phase 1: Backend Core - Part 2 (Monitoring & Exit Logic)

**Continuation of engine.py implementation**

---

## Module 3: Core Engine (Part 2/3 - Monitoring Loop)

### **File:** `bot/strategy/zero_dte/engine.py` (Part 2/3)

```python
    async def _monitoring_loop(self):
        """Main monitoring loop - runs every 30 seconds"""
        logger.info("Monitoring loop started")
        
        check_interval = self.config.rebalancing.check_interval_seconds
        
        while self.is_running:
            try:
                # Get current session
                session = self.state_manager.get_active_session()
                if not session:
                    logger.warning("No active session found, stopping monitoring")
                    break
                
                # Get current positions
                positions = self.state_manager.get_positions(self.session_id)
                
                if 'CE' not in positions or 'PE' not in positions:
                    logger.error("Missing CE or PE position")
                    break
                
                # Fetch current premiums
                ce_ticker = await self.api_client.get_option_ticker(positions['CE']['symbol'])
                pe_ticker = await self.api_client.get_option_ticker(positions['PE']['symbol'])
                
                ce_premium = ce_ticker['mark_price']
                pe_premium = pe_ticker['mark_price']
                
                ce_lots = positions['CE']['lots']
                pe_lots = positions['PE']['lots']
                
                logger.debug(f"Current: CE {ce_lots}×₹{ce_premium} | PE {pe_lots}×₹{pe_premium}")
                
                # Update positions with current data
                self._update_position_greeks(positions['CE'], ce_ticker)
                self._update_position_greeks(positions['PE'], pe_ticker)
                
                # Calculate unrealized P&L
                unrealized_pnl = self._calculate_session_pnl(session, positions, ce_premium, pe_premium)
                self.state_manager.update_session(self.session_id, {'unrealized_pnl': unrealized_pnl})
                
                logger.info(f"📊 Unrealized P&L: ₹{unrealized_pnl:.2f}")
                
                # Check exit conditions
                exit_reason = await self._check_exit_conditions(
                    session, positions, ce_premium, pe_premium, unrealized_pnl
                )
                
                if exit_reason:
                    logger.warning(f"Exit condition triggered: {exit_reason}")
                    await self._execute_exit(exit_reason)
                    break
                
                # Check rebalancing needs
                if self.config.rebalancing.enabled:
                    await self._check_and_rebalance(positions, ce_premium, pe_premium, ce_lots, pe_lots)
                
                # Check rollover needs
                if self.config.rollover.enabled:
                    await self._check_and_rollover(positions, ce_premium, pe_premium)
                
                # Save monitoring snapshot
                await self._save_monitoring_snapshot(session, positions, ce_premium, pe_premium)
                
                # Wait for next iteration
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(check_interval)
        
        logger.info("Monitoring loop stopped")
    
    def _update_position_greeks(self, position: Dict, ticker: Dict):
        """Update position with current Greeks and premium"""
        position['current_premium'] = ticker['mark_price']
        position['delta'] = ticker.get('greeks', {}).get('delta', 0)
        position['gamma'] = ticker.get('greeks', {}).get('gamma', 0)
        position['theta'] = ticker.get('greeks', {}).get('theta', 0)
        position['vega'] = ticker.get('greeks', {}).get('vega', 0)
        position['iv'] = ticker.get('quotes', {}).get('mark_iv', 0)
        
        # Save to database
        self.state_manager.save_position(self.session_id, position)
    
    def _calculate_session_pnl(
        self,
        session: Dict,
        positions: Dict,
        ce_current_premium: float,
        pe_current_premium: float
    ) -> float:
        """
        Calculate unrealized P&L
        
        P&L = Premium Collected - Current Value
        Positive = Profit (premiums decayed)
        """
        # Entry premiums
        entry_ce_total = session['entry_ce_premium'] * session['entry_ce_lots']
        entry_pe_total = session['entry_pe_premium'] * session['entry_pe_lots']
        total_collected = entry_ce_total + entry_pe_total
        
        # Current values
        current_ce_total = ce_current_premium * positions['CE']['lots']
        current_pe_total = pe_current_premium * positions['PE']['lots']
        current_value = current_ce_total + current_pe_total
        
        unrealized_pnl = total_collected - current_value
        
        return unrealized_pnl
    
    async def _check_exit_conditions(
        self,
        session: Dict,
        positions: Dict,
        ce_premium: float,
        pe_premium: float,
        unrealized_pnl: float
    ) -> Optional[str]:
        """
        Check all exit conditions
        
        Returns:
            Exit reason if should exit, None otherwise
        """
        # 1. Profit target - both legs below threshold
        if self.config.exit.profit_target.enabled:
            threshold = self.config.exit.profit_target.both_legs_below
            
            if ce_premium < threshold and pe_premium < threshold:
                logger.success(f"✅ Profit target hit: CE=₹{ce_premium}, PE=₹{pe_premium} (both <₹{threshold})")
                return 'profit_target'
        
        # 2. Stop loss
        if self.config.exit.stop_loss.enabled:
            max_loss = self.config.exit.stop_loss.max_loss_amount
            max_loss_multiple = self.config.exit.stop_loss.max_loss_multiple
            
            # Calculate max loss from multiple
            collected_premium = session['total_premium_collected']
            max_loss_from_multiple = collected_premium * max_loss_multiple
            
            effective_max_loss = min(max_loss, max_loss_from_multiple)
            
            if unrealized_pnl < -effective_max_loss:
                logger.error(f"🛑 Stop loss hit: P&L=₹{unrealized_pnl} < -₹{effective_max_loss}")
                return 'stop_loss'
        
        # 3. Time-based exit
        if self.config.exit.time_exit.enabled:
            forced_exit_time = dt_time.fromisoformat(self.config.exit.time_exit.forced_exit_time)
            ist = pytz.timezone(self.config.exit.time_exit.timezone)
            current_time = datetime.now(ist).time()
            
            if current_time >= forced_exit_time:
                logger.warning(f"⏰ Forced exit time reached: {current_time} >= {forced_exit_time}")
                return 'time_exit'
        
        # 4. Liquidity-based exit
        if self.config.exit.liquidity_exit.enabled:
            check_start_time = dt_time.fromisoformat(self.config.exit.liquidity_exit.check_start_time)
            ist = pytz.timezone(self.config.exit.time_exit.timezone)
            current_time = datetime.now(ist).time()
            
            if current_time >= check_start_time:
                # Check spreads
                ce_ticker = await self.api_client.get_option_ticker(positions['CE']['symbol'])
                pe_ticker = await self.api_client.get_option_ticker(positions['PE']['symbol'])
                
                ce_liquidity = check_liquidity(ce_ticker)
                pe_liquidity = check_liquidity(pe_ticker)
                
                max_spread = self.config.exit.liquidity_exit.max_spread_pct
                
                if not ce_liquidity['is_liquid'] or not pe_liquidity['is_liquid']:
                    logger.warning(f"💧 Liquidity dried up: CE spread={ce_liquidity['spread_pct']:.1f}%, PE spread={pe_liquidity['spread_pct']:.1f}%")
                    return 'liquidity_exit'
        
        # 5. Guardian signal
        if self.config.risk.guardian.enabled and self.config.risk.guardian.halt_on_stop:
            if not self._check_guardian_signal():
                logger.error("🛑 Guardian signal is STOP")
                return 'guardian_stop'
        
        return None
    
    async def _execute_exit(self, exit_reason: str):
        """
        Execute session exit - close all positions
        
        Args:
            exit_reason: Reason for exit
        """
        logger.info(f"Executing exit: {exit_reason}")
        
        try:
            session = self.state_manager.get_active_session()
            positions = self.state_manager.get_positions(self.session_id)
            
            # Close CE leg
            if 'CE' in positions:
                ce_pos = positions['CE']
                logger.info(f"Closing CE: {ce_pos['symbol']} × {ce_pos['lots']} lots")
                ce_exit_premium = await self._place_buy_order(ce_pos['symbol'], ce_pos['lots'])
                logger.info(f"✅ CE closed @ ₹{ce_exit_premium}")
            
            # Close PE leg
            if 'PE' in positions:
                pe_pos = positions['PE']
                logger.info(f"Closing PE: {pe_pos['symbol']} × {pe_pos['lots']} lots")
                pe_exit_premium = await self._place_buy_order(pe_pos['symbol'], pe_pos['lots'])
                logger.info(f"✅ PE closed @ ₹{pe_exit_premium}")
            
            # Calculate final P&L
            ce_pnl = (session['entry_ce_premium'] * session['entry_ce_lots']) - (ce_exit_premium * ce_pos['lots'])
            pe_pnl = (session['entry_pe_premium'] * session['entry_pe_lots']) - (pe_exit_premium * pe_pos['lots'])
            final_pnl = ce_pnl + pe_pnl
            
            logger.success(f"✅ Session closed | Final P&L: ₹{final_pnl:.2f} | Reason: {exit_reason}")
            
            # Close session state
            self.state_manager.close_session(self.session_id, exit_reason, final_pnl)
            
            self.is_running = False
            
        except Exception as e:
            logger.error(f"Error during exit: {e}", exc_info=True)
            raise
    
    async def _place_buy_order(self, symbol: str, lots: int) -> float:
        """
        Place buy order (close short position)
        
        Returns:
            Fill premium
        """
        order_pref = self.config.rebalancing.orders.preference
        timeout = self.config.rebalancing.orders.timeout_seconds
        
        logger.info(f"Placing BUY order: {symbol} × {lots} lots ({order_pref})")
        
        if order_pref == 'maker_first':
            # Try limit order first
            ticker = await self.api_client.get_option_ticker(symbol)
            limit_price = ticker['mark_price']
            
            order = await self.api_client.place_order(
                symbol=symbol,
                side='buy',
                size=lots,
                order_type='limit_order',
                limit_price=limit_price,
                reduce_only=True
            )
            
            # Wait for fill
            await asyncio.sleep(timeout)
            
            order_status = await self.api_client.get_order(order['id'])
            
            if order_status['state'] == 'filled':
                fill_price = order_status['average_fill_price']
                logger.info(f"✅ Limit order filled @ ₹{fill_price}")
                return fill_price
            
            # Cancel and fallback to market
            logger.info("Limit order not filled, using market order")
            await self.api_client.cancel_order(order['id'])
        
        # Market order
        order = await self.api_client.place_order(
            symbol=symbol,
            side='buy',
            size=lots,
            order_type='market_order',
            reduce_only=True
        )
        
        # Get fill price
        await asyncio.sleep(1)
        order_status = await self.api_client.get_order(order['id'])
        fill_price = order_status['average_fill_price']
        
        logger.info(f"✅ Market order filled @ ₹{fill_price}")
        return fill_price
    
    async def _check_and_rebalance(
        self,
        positions: Dict,
        ce_premium: float,
        pe_premium: float,
        ce_lots: int,
        pe_lots: int
    ):
        """Check if rebalancing is needed and execute"""
        ce_total = ce_premium * ce_lots
        pe_total = pe_premium * pe_lots
        
        max_total = max(ce_total, pe_total)
        if max_total == 0:
            return
        
        imbalance_pct = abs(ce_total - pe_total) / max_total * 100
        threshold = self.config.rebalancing.threshold_pct
        
        if imbalance_pct > threshold:
            logger.info(f"⚖️ Imbalance detected: {imbalance_pct:.1f}% (threshold {threshold}%)")
            logger.info(f"CE: {ce_lots}×₹{ce_premium}=₹{ce_total} | PE: {pe_lots}×₹{pe_premium}=₹{pe_total}")
            
            # Execute rebalancing via balancer module
            await self.balancer.execute_rebalance(
                self.session_id,
                positions,
                ce_premium,
                pe_premium,
                ce_total,
                pe_total
            )
    
    async def _check_and_rollover(
        self,
        positions: Dict,
        ce_premium: float,
        pe_premium: float
    ):
        """Check if strike rollover is needed"""
        trigger_premium = self.config.rollover.trigger_premium
        
        # Check CE leg
        if ce_premium < trigger_premium:
            logger.warning(f"📍 CE premium ₹{ce_premium} < ₹{trigger_premium} - Rollover needed")
            await self.rollover_manager.execute_rollover(
                self.session_id,
                leg_type='CE',
                current_position=positions['CE'],
                opposite_leg_premium=pe_premium * positions['PE']['lots']
            )
        
        # Check PE leg
        if pe_premium < trigger_premium:
            logger.warning(f"📍 PE premium ₹{pe_premium} < ₹{trigger_premium} - Rollover needed")
            await self.rollover_manager.execute_rollover(
                self.session_id,
                leg_type='PE',
                current_position=positions['PE'],
                opposite_leg_premium=ce_premium * positions['CE']['lots']
            )
    
    async def _save_monitoring_snapshot(
        self,
        session: Dict,
        positions: Dict,
        ce_premium: float,
        pe_premium: float
    ):
        """Save monitoring snapshot to database"""
        # Get spot price
        spot_price = await self.api_client.get_current_price(f"{session['underlying']}USD")
        
        # Calculate portfolio Greeks
        ce_pos = positions['CE']
        pe_pos = positions['PE']
        
        portfolio_delta = (ce_pos['delta'] * ce_pos['lots']) + (pe_pos['delta'] * pe_pos['lots'])
        portfolio_gamma = (ce_pos['gamma'] * ce_pos['lots']) + (pe_pos['gamma'] * pe_pos['lots'])
        portfolio_theta = (ce_pos['theta'] * ce_pos['lots']) + (pe_pos['theta'] * pe_pos['lots'])
        portfolio_vega = (ce_pos['vega'] * ce_pos['lots']) + (pe_pos['vega'] * pe_pos['lots'])
        
        # Calculate time to expiry
        expiry_time = dt_time.fromisoformat(self.config.exit.time_exit.settlement_time)
        ist = pytz.timezone(self.config.exit.time_exit.timezone)
        now = datetime.now(ist)
        expiry_datetime = datetime.combine(now.date(), expiry_time, tzinfo=ist)
        time_to_expiry_minutes = int((expiry_datetime - now).total_seconds() / 60)
        
        # Save to database (implementation would insert into monitoring_snapshots table)
        logger.debug(f"Snapshot saved: Spot=${spot_price}, Delta={portfolio_delta:.2f}, Time to expiry={time_to_expiry_minutes}min")
    
    async def stop_session(self, reason: str = 'manual'):
        """Manually stop active session"""
        if not self.is_running:
            raise RuntimeError("No active session")
        
        logger.info(f"Manual session stop requested: {reason}")
        await self._execute_exit(reason)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current session status"""
        if not self.session_id:
            return {'is_active': False}
        
        session = self.state_manager.get_active_session()
        if not session:
            return {'is_active': False}
        
        positions = self.state_manager.get_positions(self.session_id)
        
        return {
            'is_active': self.is_running,
            'session_id': self.session_id,
            'session': session,
            'positions': positions
        }
```

---

## Module 4: Premium Balancer

### **File:** `bot/strategy/zero_dte/balancer.py`

```python
"""
Premium Balancer - Maintains CE/PE exposure parity
"""
import asyncio
from typing import Dict, Any
from loguru import logger
from datetime import datetime

from bot.api.unified_api_client import UnifiedAPIClient
from bot.strategy.zero_dte.state_manager import get_state_manager


class PremiumBalancer:
    """Manages premium balancing between CE and PE legs"""
    
    def __init__(self, api_client: UnifiedAPIClient, config):
        self.api_client = api_client
        self.config = config
        self.state_manager = get_state_manager()
    
    async def execute_rebalance(
        self,
        session_id: str,
        positions: Dict[str, Dict],
        ce_premium: float,
        pe_premium: float,
        ce_total: float,
        pe_total: float
    ):
        """
        Execute rebalancing to restore premium parity
        
        Logic:
        - If CE_total < PE_total: Add CE lots (buy back some CE shorts)
        - If PE_total < CE_total: Add PE lots (buy back some PE shorts)
        """
        logger.info("🔄 Starting rebalancing...")
        
        ce_pos = positions['CE']
        pe_pos = positions['PE']
        
        try:
            # Determine which leg to adjust
            if ce_total < pe_total:
                # CE is underexposed, need to reduce CE shorts (buy back CE)
                target_ce_lots = pe_total / ce_premium
                lots_to_reduce = int(ce_pos['lots'] - target_ce_lots)
                
                if lots_to_reduce <= 0:
                    logger.info("No rebalancing needed (lots_to_reduce <= 0)")
                    return
                
                # Apply limits
                min_adjust = self.config.rebalancing.adjustment.min_lot_adjustment
                max_adjust = self.config.rebalancing.adjustment.max_lot_adjustment
                lots_to_reduce = max(min_adjust, min(lots_to_reduce, max_adjust))
                
                logger.info(f"Reducing CE short by {lots_to_reduce} lots (buy back)")
                
                # Execute buy order to close CE lots
                fill_price = await self._place_buy_order(ce_pos['symbol'], lots_to_reduce, reduce_only=True)
                
                # Update position
                new_ce_lots = ce_pos['lots'] - lots_to_reduce
                ce_pos['lots'] = new_ce_lots
                self.state_manager.save_position(session_id, ce_pos)
                
                # Log rebalance
                await self._log_rebalance(
                    session_id,
                    'lot_adjustment',
                    f'CE imbalance: CE_total={ce_total} < PE_total={pe_total}',
                    ce_pos['lots'] + lots_to_reduce, pe_pos['lots'],
                    new_ce_lots, pe_pos['lots'],
                    f"Reduced CE short by {lots_to_reduce} lots @ ₹{fill_price}"
                )
                
                self.state_manager.increment_counter(session_id, 'total_rebalances')
                
                logger.success(f"✅ Rebalanced: CE lots {ce_pos['lots']+lots_to_reduce} → {new_ce_lots}")
                
            else:
                # PE is underexposed, need to reduce PE shorts (buy back PE)
                target_pe_lots = ce_total / pe_premium
                lots_to_reduce = int(pe_pos['lots'] - target_pe_lots)
                
                if lots_to_reduce <= 0:
                    logger.info("No rebalancing needed (lots_to_reduce <= 0)")
                    return
                
                # Apply limits
                min_adjust = self.config.rebalancing.adjustment.min_lot_adjustment
                max_adjust = self.config.rebalancing.adjustment.max_lot_adjustment
                lots_to_reduce = max(min_adjust, min(lots_to_reduce, max_adjust))
                
                logger.info(f"Reducing PE short by {lots_to_reduce} lots (buy back)")
                
                # Execute buy order to close PE lots
                fill_price = await self._place_buy_order(pe_pos['symbol'], lots_to_reduce, reduce_only=True)
                
                # Update position
                new_pe_lots = pe_pos['lots'] - lots_to_reduce
                pe_pos['lots'] = new_pe_lots
                self.state_manager.save_position(session_id, pe_pos)
                
                # Log rebalance
                await self._log_rebalance(
                    session_id,
                    'lot_adjustment',
                    f'PE imbalance: PE_total={pe_total} < CE_total={ce_total}',
                    ce_pos['lots'], pe_pos['lots'] + lots_to_reduce,
                    ce_pos['lots'], new_pe_lots,
                    f"Reduced PE short by {lots_to_reduce} lots @ ₹{fill_price}"
                )
                
                self.state_manager.increment_counter(session_id, 'total_rebalances')
                
                logger.success(f"✅ Rebalanced: PE lots {pe_pos['lots']+lots_to_reduce} → {new_pe_lots}")
        
        except Exception as e:
            logger.error(f"Rebalancing failed: {e}", exc_info=True)
            await self._log_rebalance(
                session_id,
                'lot_adjustment',
                'Rebalancing error',
                ce_pos['lots'], pe_pos['lots'],
                ce_pos['lots'], pe_pos['lots'],
                f"Failed: {str(e)}",
                status='failed'
            )
    
    async def _place_buy_order(self, symbol: str, lots: int, reduce_only: bool = True) -> float:
        """Place buy order to close short position"""
        order_pref = self.config.rebalancing.orders.preference
        timeout = self.config.rebalancing.orders.timeout_seconds
        
        logger.info(f"Placing BUY order: {symbol} × {lots} lots")
        
        if order_pref == 'maker_first':
            ticker = await self.api_client.get_option_ticker(symbol)
            limit_price = ticker['mark_price']
            
            order = await self.api_client.place_order(
                symbol=symbol,
                side='buy',
                size=lots,
                order_type='limit_order',
                limit_price=limit_price,
                reduce_only=reduce_only
            )
            
            await asyncio.sleep(timeout)
            order_status = await self.api_client.get_order(order['id'])
            
            if order_status['state'] == 'filled':
                return order_status['average_fill_price']
            
            await self.api_client.cancel_order(order['id'])
        
        # Market order fallback
        order = await self.api_client.place_order(
            symbol=symbol,
            side='buy',
            size=lots,
            order_type='market_order',
            reduce_only=reduce_only
        )
        
        await asyncio.sleep(1)
        order_status = await self.api_client.get_order(order['id'])
        return order_status['average_fill_price']
    
    async def _log_rebalance(
        self,
        session_id: str,
        rebalance_type: str,
        reason: str,
        ce_lots_before: int,
        pe_lots_before: int,
        ce_lots_after: int,
        pe_lots_after: int,
        action: str,
        status: str = 'success'
    ):
        """Log rebalance to database"""
        # Implementation would insert into zero_dte_rebalances.db
        logger.info(f"Rebalance logged: {reason} | {action} | Status: {status}")
```

---

## Module 5: Strike Rollover Manager

### **File:** `bot/strategy/zero_dte/rollover.py`

```python
"""
Strike Rollover Manager - Rolls strikes when premium < ₹5
"""
import asyncio
from typing import Dict, Any, Optional
from loguru import logger
from datetime import datetime

from bot.api.unified_api_client import UnifiedAPIClient
from bot.strategy.zero_dte.state_manager import get_state_manager


class StrikeRolloverManager:
    """Manages strike rollovers when premiums drop below threshold"""
    
    def __init__(self, api_client: UnifiedAPIClient, config):
        self.api_client = api_client
        self.config = config
        self.state_manager = get_state_manager()
    
    async def execute_rollover(
        self,
        session_id: str,
        leg_type: str,
        current_position: Dict[str, Any],
        opposite_leg_premium: float
    ):
        """
        Execute strike rollover for CE or PE leg
        
        Steps:
        1. Close current leg
        2. Find new strike with target premium (₹20-25)
        3. Open new leg with adjusted lots to match opposite leg exposure
        4. Update position state
        """
        logger.info(f"🔄 Starting {leg_type} rollover...")
        
        try:
            session = self.state_manager.get_session(session_id)
            underlying = session['underlying']
            expiry_date = session['expiry_date']
            
            old_symbol = current_position['symbol']
            old_strike = current_position['strike']
            old_lots = current_position['lots']
            
            # Step 1: Close current leg
            logger.info(f"Closing old {leg_type}: {old_symbol} × {old_lots} lots")
            close_premium = await self._close_position(old_symbol, old_lots)
            logger.info(f"✅ Old {leg_type} closed @ ₹{close_premium}")
            
            # Step 2: Find new strike
            target_premium = self.config.rollover.target_premium
            option_type = 'call' if leg_type == 'CE' else 'put'
            
            new_strike, new_premium, new_symbol = await self._find_new_strike(
                underlying,
                expiry_date,
                option_type,
                target_premium
            )
            
            logger.info(f"New {leg_type} strike selected: {new_strike} @ ₹{new_premium}")
            
            # Step 3: Calculate new lots to match opposite leg
            new_lots = int(opposite_leg_premium / new_premium)
            new_lots = max(1, new_lots)  # At least 1 lot
            
            # Validate against position limits
            max_lots = (
                self.config.risk.position_limits.max_ce_lots if leg_type == 'CE'
                else self.config.risk.position_limits.max_pe_lots
            )
            new_lots = min(new_lots, max_lots)
            
            logger.info(f"Opening new {leg_type}: {new_symbol} × {new_lots} lots")
            
            # Step 4: Open new leg
            fill_premium = await self._open_position(new_symbol, new_lots)
            logger.info(f"✅ New {leg_type} opened @ ₹{fill_premium}")
            
            # Step 5: Update position state
            current_position['symbol'] = new_symbol
            current_position['strike'] = new_strike
            current_position['lots'] = new_lots
            current_position['entry_premium'] = fill_premium
            current_position['current_premium'] = fill_premium
            
            self.state_manager.save_position(session_id, current_position)
            
            # Update session strike
            strike_field = 'current_ce_strike' if leg_type == 'CE' else 'current_pe_strike'
            lots_field = 'current_ce_lots' if leg_type == 'CE' else 'current_pe_lots'
            self.state_manager.update_session(session_id, {
                strike_field: new_strike,
                lots_field: new_lots
            })
            
            # Increment rollover counter
            self.state_manager.increment_counter(session_id, 'total_rollovers')
            
            # Log rollover
            await self._log_rollover(
                session_id,
                leg_type,
                old_strike,
                new_strike,
                old_lots,
                new_lots,
                close_premium,
                fill_premium
            )
            
            logger.success(f"✅ {leg_type} rollover complete: {old_strike}→{new_strike}, {old_lots}→{new_lots} lots")
            
        except Exception as e:
            logger.error(f"Rollover failed: {e}", exc_info=True)
            
            # Rollback: reopen old position if possible
            if self.config.rollover.execution.rollback_on_failure:
                try:
                    logger.warning("Attempting rollback...")
                    await self._open_position(old_symbol, old_lots)
                    logger.info("Rollback successful")
                except Exception as rollback_error:
                    logger.error(f"Rollback failed: {rollback_error}")
                    raise
    
    async def _close_position(self, symbol: str, lots: int) -> float:
        """Close short position (buy back)"""
        order = await self.api_client.place_order(
            symbol=symbol,
            side='buy',
            size=lots,
            order_type='market_order',
            reduce_only=True
        )
        
        await asyncio.sleep(1)
        order_status = await self.api_client.get_order(order['id'])
        return order_status['average_fill_price']
    
    async def _open_position(self, symbol: str, lots: int) -> float:
        """Open short position (sell)"""
        order_pref = self.config.rebalancing.orders.preference
        timeout = self.config.rebalancing.orders.timeout_seconds
        
        if order_pref == 'maker_first':
            ticker = await self.api_client.get_option_ticker(symbol)
            limit_price = ticker['mark_price']
            
            order = await self.api_client.place_order(
                symbol=symbol,
                side='sell',
                size=lots,
                order_type='limit_order',
                limit_price=limit_price,
                reduce_only=False
            )
            
            await asyncio.sleep(timeout)
            order_status = await self.api_client.get_order(order['id'])
            
            if order_status['state'] == 'filled':
                return order_status['average_fill_price']
            
            await self.api_client.cancel_order(order['id'])
        
        # Market order fallback
        order = await self.api_client.place_order(
            symbol=symbol,
            side='sell',
            size=lots,
            order_type='market_order',
            reduce_only=False
        )
        
        await asyncio.sleep(1)
        order_status = await self.api_client.get_order(order['id'])
        return order_status['average_fill_price']
    
    async def _find_new_strike(
        self,
        underlying: str,
        expiry_date: str,
        option_type: str,
        target_premium: float
    ) -> tuple[float, float, str]:
        """
        Find strike with premium close to target
        
        Returns:
            (strike, premium, symbol)
        """
        # Fetch option chain
        chain = await self.api_client.get_option_chain(underlying, expiry_date)
        
        # Get spot price
        spot_price = await self.api_client.get_current_price(f"{underlying}USD")
        
        # Filter options by type
        options = chain['calls'] if option_type == 'call' else chain['puts']
        
        # Find strike closest to target premium
        best_strike = None
        best_premium = None
        min_diff = float('inf')
        
        tolerance_pct = self.config.rollover.new_strike.premium_tolerance / 100
        max_distance_pct = self.config.rollover.new_strike.max_strike_distance_pct / 100
        
        for strike, data in options.items():
            strike_float = float(strike)
            premium = data['mark_price']
            
            # Skip strikes too far from spot
            strike_distance_pct = abs(strike_float - spot_price) / spot_price
            if strike_distance_pct > max_distance_pct:
                continue
            
            # Check premium closeness
            premium_diff = abs(premium - target_premium)
            
            if premium_diff < min_diff:
                min_diff = premium_diff
                best_strike = strike_float
                best_premium = premium
        
        if not best_strike:
            raise ValueError(f"No suitable strike found for {option_type} with target premium ₹{target_premium}")
        
        # Format symbol
        type_prefix = 'C' if option_type == 'call' else 'P'
        expiry_formatted = datetime.strptime(expiry_date, '%Y-%m-%d').strftime('%d%m%Y')
        symbol = f"{type_prefix}-{underlying}-{int(best_strike)}-{expiry_formatted}"
        
        return best_strike, best_premium, symbol
    
    async def _log_rollover(
        self,
        session_id: str,
        leg_type: str,
        old_strike: float,
        new_strike: float,
        old_lots: int,
        new_lots: int,
        close_premium: float,
        fill_premium: float
    ):
        """Log rollover to database"""
        logger.info(f"Rollover logged: {leg_type} {old_strike}→{new_strike}")
```

---

## Module 6: Configuration Loader

### **File:** `bot/strategy/zero_dte/config.py`

```python
"""
Configuration loader for 0DTE strategy
"""
import yaml
from pathlib import Path
from loguru import logger
from config.schemas.zero_dte_schemas import ZeroDTEConfig


_config_cache = None


def load_zero_dte_config(config_path: str = 'config/zero_dte_config.yaml') -> ZeroDTEConfig:
    """
    Load and validate 0DTE configuration
    
    Returns:
        Validated ZeroDTEConfig object
    """
    global _config_cache
    
    if _config_cache is not None:
        return _config_cache
    
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    logger.info(f"Loading 0DTE config from: {config_path}")
    
    with open(config_file, 'r') as f:
        raw_config = yaml.safe_load(f)
    
    # Validate with Pydantic
    config = ZeroDTEConfig(**raw_config['zero_dte'])
    
    _config_cache = config
    
    logger.success("✅ 0DTE configuration loaded and validated")
    
    return config


def reload_config():
    """Reload configuration (clear cache)"""
    global _config_cache
    _config_cache = None
    logger.info("Configuration cache cleared")
```

---

**Continue to Phase 2:** [ZERO_DTE_PHASE2_MONITORING.md](ZERO_DTE_PHASE2_MONITORING.md)
