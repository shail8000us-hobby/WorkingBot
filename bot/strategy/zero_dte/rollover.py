"""
Strike Rollover Manager for Zero DTE Bot
========================================

Handles rolling to new strikes when premium drops below threshold.

When premium < ₹5 on one leg (but other leg still > ₹5):
1. Close current position (buy back)
2. Find new strike with target premium (₹20-25)
3. Sell new strike with same lot size

This preserves position structure while maintaining premium exposure.
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional, Tuple
from loguru import logger

from config.schemas.zero_dte_schemas import ZeroDTEConfig


class StrikeRolloverManager:
    """
    Strike Rollover Manager
    
    Rolls strikes when premium decays below threshold.
    Ensures continuous premium exposure throughout the day.
    """
    
    def __init__(self, api_client, config: ZeroDTEConfig, state_manager):
        self.api_client = api_client
        self.config = config
        self.state_manager = state_manager
        
        # Track last rollover time per leg
        self._last_rollover: Dict[str, datetime] = {}
    
    async def execute_rollover(
        self,
        session_id: str,
        leg_type: str,  # 'CE' or 'PE'
        current_position: Dict
    ) -> Optional[Dict]:
        """
        Execute strike rollover for a leg
        
        Args:
            session_id: Current session ID
            leg_type: 'CE' or 'PE'
            current_position: Current position dict
        
        Returns:
            New position dict if successful, None otherwise
        """
        # Check cooldown
        cooldown = self.config.rollover.cooldown_seconds
        if leg_type in self._last_rollover:
            elapsed = (datetime.now() - self._last_rollover[leg_type]).seconds
            if elapsed < cooldown:
                logger.debug(f"{leg_type} rollover cooldown: {cooldown - elapsed}s remaining")
                return None
        
        current_symbol = current_position['symbol']
        current_strike = current_position['strike']
        lots = current_position['lots']
        
        logger.info(f"Rolling {leg_type}: {current_symbol} (strike {current_strike})")
        
        # Get session info
        session = self.state_manager.get_session(session_id)
        underlying = session['underlying']
        expiry_date = session['expiry_date']
        
        # Step 1: Find new strike with target premium
        new_strike, new_premium = await self._find_rollover_strike(
            underlying, expiry_date, leg_type, current_strike
        )
        
        if new_strike is None:
            logger.warning(f"No suitable strike found for {leg_type} rollover")
            return None
        
        # Build new symbol
        expiry_formatted = expiry_date.replace('-', '')[-6:]  # DDMMYY
        option_type = 'C' if leg_type == 'CE' else 'P'
        new_symbol = f"{option_type}-{underlying}-{int(new_strike)}-{expiry_formatted}"
        
        logger.info(f"Rolling to: {new_symbol} (strike {new_strike}, premium ~₹{new_premium:.2f})")
        
        # Prepare rebalance record
        rebalance_record = {
            'session_id': session_id,
            'rebalance_type': 'strike_rollover',
            'trigger_reason': f'{leg_type.lower()}_premium_below_{self.config.rollover.min_premium_threshold}',
            'ce_lots_before': session.get('current_ce_lots'),
            'pe_lots_before': session.get('current_pe_lots')
        }
        
        try:
            # Step 2: Close current position (buy back)
            close_result = await self._close_position(current_symbol, lots)
            close_price = close_result['fill_price']
            
            logger.info(f"Closed {current_symbol}: bought back {lots} @ ₹{close_price:.2f}")
            
            # Log close trade
            self.state_manager.log_trade({
                'session_id': session_id,
                'trade_type': 'rollover',
                'leg_type': leg_type,
                'symbol': current_symbol,
                'side': 'buy',
                'strike': current_strike,
                'lots': lots,
                'premium': close_price,
                'status': 'filled',
                'reason': 'rollover_close'
            })
            
            # Step 3: Open new position (sell new strike)
            open_result = await self._open_position(new_symbol, lots)
            open_price = open_result['fill_price']
            
            logger.info(f"Opened {new_symbol}: sold {lots} @ ₹{open_price:.2f}")
            
            # Log open trade
            self.state_manager.log_trade({
                'session_id': session_id,
                'trade_type': 'rollover',
                'leg_type': leg_type,
                'symbol': new_symbol,
                'side': 'sell',
                'strike': new_strike,
                'lots': lots,
                'premium': open_price,
                'status': 'filled',
                'reason': 'rollover_open'
            })
            
            # Update session premiums
            session = self.state_manager.get_session(session_id)
            new_collected = session.get('total_premium_collected', 0) + (open_price * lots)
            new_paid = session.get('total_premium_paid', 0) + (close_price * lots)
            
            self.state_manager.update_session(session_id, {
                'total_premium_collected': new_collected,
                'total_premium_paid': new_paid,
                f'current_{leg_type.lower()}_strike': new_strike
            })
            
            # Create new position
            new_position = {
                'leg_type': leg_type,
                'symbol': new_symbol,
                'strike': new_strike,
                'lots': lots,
                'entry_premium': open_price,
                'current_premium': open_price
            }
            
            # Save position
            self.state_manager.save_position(session_id, new_position)
            
            # Complete rebalance record
            rebalance_record['action_taken'] = [
                {'action': f'close_{leg_type.lower()}', 'strike': current_strike, 'price': close_price},
                {'action': f'open_{leg_type.lower()}', 'strike': new_strike, 'price': open_price}
            ]
            rebalance_record['execution_status'] = 'success'
            
            # Log rebalance
            self.state_manager.log_rebalance(rebalance_record)
            self.state_manager.increment_rollover_count(session_id)
            
            # Update cooldown
            self._last_rollover[leg_type] = datetime.now()
            
            # Calculate roll P&L
            roll_pnl = (current_position.get('entry_premium', 0) - close_price) * lots
            net_credit = open_price - close_price
            
            logger.success(
                f"Rollover complete: {current_strike} → {new_strike}, "
                f"Net credit: ₹{net_credit:.2f}/lot"
            )
            
            return new_position
            
        except Exception as e:
            logger.error(f"Rollover failed: {e}")
            rebalance_record['execution_status'] = 'failed'
            rebalance_record['error_message'] = str(e)
            self.state_manager.log_rebalance(rebalance_record)
            return None
    
    async def _find_rollover_strike(
        self,
        underlying: str,
        expiry_date: str,
        leg_type: str,
        current_strike: float
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Find new strike with target premium
        
        For CE: Look for strikes further OTM (higher)
        For PE: Look for strikes further OTM (lower)
        """
        target_min = self.config.rollover.target_premium.min
        target_max = self.config.rollover.target_premium.max
        max_search = self.config.rollover.max_strike_search
        
        try:
            # Fetch option chain
            option_chain = await self.api_client.get_option_chain(underlying, expiry_date)
            
            if leg_type == 'CE':
                strikes_data = option_chain.get('calls', {})
            else:
                strikes_data = option_chain.get('puts', {})
            
            candidates = []
            
            for strike_str, data in strikes_data.items():
                strike = float(strike_str)
                premium = data.get('mark_price', 0)
                
                # Check if premium is in target range
                if target_min <= premium <= target_max:
                    # For CE: new strike should be >= current (further OTM)
                    # For PE: new strike should be <= current (further OTM)
                    if leg_type == 'CE' and strike >= current_strike:
                        candidates.append((strike, premium))
                    elif leg_type == 'PE' and strike <= current_strike:
                        candidates.append((strike, premium))
            
            if not candidates:
                logger.warning(f"No strikes found with premium in [{target_min}, {target_max}]")
                return None, None
            
            # Sort by how close premium is to target middle
            target_mid = (target_min + target_max) / 2
            candidates.sort(key=lambda x: abs(x[1] - target_mid))
            
            # Return best candidate (limit search depth)
            best = candidates[0]
            logger.debug(f"Found rollover strike: {best[0]} @ ₹{best[1]:.2f}")
            
            return best[0], best[1]
            
        except Exception as e:
            logger.error(f"Failed to find rollover strike: {e}")
            return None, None
    
    async def _close_position(self, symbol: str, lots: int) -> Dict:
        """Close position by buying back"""
        return await self._place_order(symbol, 'buy', lots)
    
    async def _open_position(self, symbol: str, lots: int) -> Dict:
        """Open new position by selling"""
        return await self._place_order(symbol, 'sell', lots)
    
    async def _place_order(self, symbol: str, side: str, lots: int) -> Dict:
        """Place order with maker-first preference using correct Delta Exchange API"""
        preference = self.config.rebalancing.orders.preference
        timeout = self.config.rebalancing.orders.timeout_seconds
        
        try:
            # Get ticker for price reference
            ticker = await self.api_client.get_option_ticker(symbol)
            
            if side == 'sell':
                limit_price = ticker.get('quotes', {}).get('best_bid', ticker.get('mark_price'))
            else:
                limit_price = ticker.get('quotes', {}).get('best_ask', ticker.get('mark_price'))
            
            if preference == 'maker_first':
                # Try maker order first using async_client with correct signature
                response = await self.api_client.async_client.place_order_by_symbol(
                    symbol=symbol,
                    side=side,
                    price=limit_price,
                    size=lots,
                    order_type='limit_order',
                    post_only=True
                )
                
                order_id = response.get('result', {}).get('id')
                if not order_id:
                    raise Exception(f"Order creation failed: {response}")
                
                fill_price = await self._wait_for_fill(order_id, timeout)
                
                if fill_price is None:
                    # Cancel and use market
                    await self.api_client.async_client.cancel_order(order_id)
                    
                    response = await self.api_client.async_client.place_order_by_symbol(
                        symbol=symbol,
                        side=side,
                        size=lots,
                        order_type='market_order'
                    )
                    order_id = response.get('result', {}).get('id')
                    fill_price = await self._wait_for_fill(order_id, 10) or limit_price
                
                return {'fill_price': fill_price, 'order_id': order_id}
            else:
                # Market order using async_client with correct signature
                response = await self.api_client.async_client.place_order_by_symbol(
                    symbol=symbol,
                    side=side,
                    size=lots,
                    order_type='market_order'
                )
                order_id = response.get('result', {}).get('id')
                if not order_id:
                    raise Exception(f"Order creation failed: {response}")
                    
                fill_price = await self._wait_for_fill(order_id, 10) or limit_price
                
                return {'fill_price': fill_price, 'order_id': order_id}
                
        except Exception as e:
            logger.error(f"Order failed: {side} {lots} {symbol}: {e}")
            raise
    
    async def _wait_for_fill(self, order_id: str, timeout: int) -> Optional[float]:
        """Wait for order fill"""
        start = datetime.now()
        
        while (datetime.now() - start).seconds < timeout:
            try:
                order = await self.api_client.get_order(order_id)
                
                if order.get('state') == 'filled':
                    return order.get('average_fill_price')
                elif order.get('state') in ['cancelled', 'rejected']:
                    return None
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Error checking order {order_id}: {e}")
                await asyncio.sleep(0.5)
        
        return None
