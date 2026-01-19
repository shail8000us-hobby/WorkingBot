"""
Premium Balancer for Zero DTE Bot
=================================

Handles lot adjustments to maintain CE/PE premium parity.

When premium imbalance > 20%:
1. Identify which leg is underexposed (lower total premium)
2. Calculate lots needed to restore balance
3. Execute adjustment (sell more of underexposed leg OR buy back overexposed)

Goal: Keep CE total premium ≈ PE total premium at all times
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional, Tuple
from loguru import logger

from config.schemas.zero_dte_schemas import ZeroDTEConfig


class PremiumBalancer:
    """
    Premium Balancer - Maintains CE/PE parity
    
    Strategy:
    - If CE total < PE total: Sell more CE OR buy back some PE
    - If PE total < CE total: Sell more PE OR buy back some CE
    - Prefer adding lots (collect more premium) over reducing
    """
    
    def __init__(self, api_client, config: ZeroDTEConfig, state_manager):
        self.api_client = api_client
        self.config = config
        self.state_manager = state_manager
        
        # Track last rebalance time to prevent over-trading
        self._last_rebalance_time: Optional[datetime] = None
        self._min_rebalance_interval = 60  # Minimum seconds between rebalances
    
    async def execute_rebalance(
        self,
        session_id: str,
        positions: Dict[str, Dict],
        ce_premium: float,
        pe_premium: float,
        ce_total: float,
        pe_total: float
    ) -> bool:
        """
        Execute rebalancing to restore premium parity
        
        Args:
            session_id: Current session ID
            positions: {'CE': {...}, 'PE': {...}}
            ce_premium: Current CE premium per lot
            pe_premium: Current PE premium per lot
            ce_total: CE premium * CE lots
            pe_total: PE premium * PE lots
        
        Returns:
            True if rebalancing was executed
        """
        # Check cooldown
        if self._last_rebalance_time:
            elapsed = (datetime.now() - self._last_rebalance_time).seconds
            if elapsed < self._min_rebalance_interval:
                logger.debug(f"Rebalance cooldown: {self._min_rebalance_interval - elapsed}s remaining")
                return False
        
        # Calculate imbalance
        avg_total = (ce_total + pe_total) / 2
        imbalance_pct = abs(ce_total - pe_total) / avg_total * 100 if avg_total > 0 else 0
        
        logger.info(f"Rebalancing: CE_total=₹{ce_total:.2f}, PE_total=₹{pe_total:.2f}, Imbalance={imbalance_pct:.1f}%")
        
        ce_lots = positions['CE'].get('lots', 0)
        pe_lots = positions['PE'].get('lots', 0)
        
        # Determine action
        if ce_total < pe_total:
            # CE is underexposed - need to increase CE exposure
            action, lots_change = await self._calculate_adjustment(
                'CE', ce_premium, pe_premium, ce_lots, pe_lots, ce_total, pe_total
            )
        else:
            # PE is underexposed - need to increase PE exposure
            action, lots_change = await self._calculate_adjustment(
                'PE', pe_premium, ce_premium, pe_lots, ce_lots, pe_total, ce_total
            )
        
        if action == 'none' or lots_change == 0:
            logger.info("No rebalancing action needed")
            return False
        
        # Prepare rebalance record (before state)
        rebalance_record = {
            'session_id': session_id,
            'rebalance_type': 'lot_adjustment',
            'trigger_reason': f'premium_imbalance_{imbalance_pct:.0f}pct',
            'ce_premium_before': ce_premium,
            'pe_premium_before': pe_premium,
            'ce_lots_before': ce_lots,
            'pe_lots_before': pe_lots,
            'imbalance_pct_before': imbalance_pct
        }
        
        # Execute the adjustment
        try:
            if action == 'add_ce':
                await self._add_lots(session_id, 'CE', positions['CE'], lots_change)
                rebalance_record['ce_lots_after'] = ce_lots + lots_change
                rebalance_record['pe_lots_after'] = pe_lots
                rebalance_record['action_taken'] = [{'action': 'add_ce_lots', 'lots': lots_change}]
                
            elif action == 'add_pe':
                await self._add_lots(session_id, 'PE', positions['PE'], lots_change)
                rebalance_record['ce_lots_after'] = ce_lots
                rebalance_record['pe_lots_after'] = pe_lots + lots_change
                rebalance_record['action_taken'] = [{'action': 'add_pe_lots', 'lots': lots_change}]
                
            elif action == 'reduce_ce':
                await self._reduce_lots(session_id, 'CE', positions['CE'], lots_change)
                rebalance_record['ce_lots_after'] = ce_lots - lots_change
                rebalance_record['pe_lots_after'] = pe_lots
                rebalance_record['action_taken'] = [{'action': 'reduce_ce_lots', 'lots': lots_change}]
                
            elif action == 'reduce_pe':
                await self._reduce_lots(session_id, 'PE', positions['PE'], lots_change)
                rebalance_record['ce_lots_after'] = ce_lots
                rebalance_record['pe_lots_after'] = pe_lots - lots_change
                rebalance_record['action_taken'] = [{'action': 'reduce_pe_lots', 'lots': lots_change}]
            
            # Calculate new imbalance
            new_ce_total = rebalance_record.get('ce_lots_after', ce_lots) * ce_premium
            new_pe_total = rebalance_record.get('pe_lots_after', pe_lots) * pe_premium
            new_avg = (new_ce_total + new_pe_total) / 2
            new_imbalance = abs(new_ce_total - new_pe_total) / new_avg * 100 if new_avg > 0 else 0
            
            rebalance_record['ce_premium_after'] = ce_premium
            rebalance_record['pe_premium_after'] = pe_premium
            rebalance_record['imbalance_pct_after'] = new_imbalance
            rebalance_record['execution_status'] = 'success'
            
            logger.success(f"Rebalance complete: {action} {lots_change} lots, new imbalance: {new_imbalance:.1f}%")
            
        except Exception as e:
            logger.error(f"Rebalance failed: {e}")
            rebalance_record['execution_status'] = 'failed'
            rebalance_record['error_message'] = str(e)
        
        # Log rebalance
        self.state_manager.log_rebalance(rebalance_record)
        self.state_manager.increment_rebalance_count(session_id)
        
        # Update cooldown
        self._last_rebalance_time = datetime.now()
        
        return rebalance_record['execution_status'] == 'success'
    
    async def _calculate_adjustment(
        self,
        underexposed_leg: str,
        under_premium: float,
        over_premium: float,
        under_lots: int,
        over_lots: int,
        under_total: float,
        over_total: float
    ) -> Tuple[str, int]:
        """
        Calculate the adjustment needed
        
        Strategy preference:
        1. Add lots to underexposed leg (collect more premium)
        2. If at max lots, reduce overexposed leg
        
        Returns:
            (action, lots_change)
        """
        # Target: Make totals equal
        # If we add X lots to under: under_premium * (under_lots + X) = over_total
        # X = (over_total / under_premium) - under_lots
        
        target_lots = over_total / under_premium if under_premium > 0 else under_lots
        lots_to_add = int(target_lots - under_lots)
        
        # Apply limits
        min_adj = self.config.rebalancing.adjustment.min_lot_adjustment
        max_adj = self.config.rebalancing.adjustment.max_lot_adjustment
        max_lots = self.config.rebalancing.adjustment.max_lots_per_leg
        
        if lots_to_add > 0:
            # Option 1: Add lots to underexposed leg
            lots_to_add = max(min_adj, min(lots_to_add, max_adj))
            
            # Check if we'd exceed max lots
            if under_lots + lots_to_add <= max_lots:
                return (f'add_{underexposed_leg.lower()}', lots_to_add)
        
        # Option 2: Reduce overexposed leg
        # If we reduce Y lots from over: over_premium * (over_lots - Y) = under_total
        # Y = over_lots - (under_total / over_premium)
        
        target_over_lots = under_total / over_premium if over_premium > 0 else over_lots
        lots_to_reduce = int(over_lots - target_over_lots)
        
        if lots_to_reduce > 0:
            lots_to_reduce = max(min_adj, min(lots_to_reduce, max_adj))
            
            # Ensure we don't go below 1 lot
            if over_lots - lots_to_reduce >= 1:
                over_leg = 'CE' if underexposed_leg == 'PE' else 'PE'
                return (f'reduce_{over_leg.lower()}', lots_to_reduce)
        
        return ('none', 0)
    
    async def _add_lots(self, session_id: str, leg_type: str, position: Dict, lots: int):
        """Add lots by selling more contracts"""
        symbol = position['symbol']
        
        logger.info(f"Adding {lots} lots to {leg_type}: SELL {symbol}")
        
        # Get current ticker
        ticker = await self.api_client.get_option_ticker(symbol)
        current_premium = ticker.get('mark_price', 0)
        
        # Place sell order
        result = await self._place_order(symbol, 'sell', lots)
        fill_price = result['fill_price']
        
        # Update position
        new_lots = position['lots'] + lots
        position['lots'] = new_lots
        
        self.state_manager.save_position(session_id, {
            **position,
            'lots': new_lots,
            'current_premium': current_premium
        })
        
        # Log trade
        self.state_manager.log_trade({
            'session_id': session_id,
            'trade_type': 'rebalance',
            'leg_type': leg_type,
            'symbol': symbol,
            'side': 'sell',
            'strike': position['strike'],
            'lots': lots,
            'premium': fill_price,
            'status': 'filled',
            'reason': 'lot_adjustment_add'
        })
        
        # Update session premium collected
        session = self.state_manager.get_session(session_id)
        new_collected = session.get('total_premium_collected', 0) + (fill_price * lots)
        self.state_manager.update_session(session_id, {
            'total_premium_collected': new_collected,
            f'current_{leg_type.lower()}_lots': new_lots
        })
        
        logger.success(f"Added {lots} {leg_type} lots @ ₹{fill_price:.2f}")
    
    async def _reduce_lots(self, session_id: str, leg_type: str, position: Dict, lots: int):
        """Reduce lots by buying back contracts"""
        symbol = position['symbol']
        
        logger.info(f"Reducing {lots} lots from {leg_type}: BUY {symbol}")
        
        # Place buy order
        result = await self._place_order(symbol, 'buy', lots)
        fill_price = result['fill_price']
        
        # Update position
        new_lots = max(0, position['lots'] - lots)
        position['lots'] = new_lots
        
        self.state_manager.save_position(session_id, {
            **position,
            'lots': new_lots
        })
        
        # Log trade
        self.state_manager.log_trade({
            'session_id': session_id,
            'trade_type': 'rebalance',
            'leg_type': leg_type,
            'symbol': symbol,
            'side': 'buy',
            'strike': position['strike'],
            'lots': lots,
            'premium': fill_price,
            'status': 'filled',
            'reason': 'lot_adjustment_reduce'
        })
        
        # Update session premium paid
        session = self.state_manager.get_session(session_id)
        new_paid = session.get('total_premium_paid', 0) + (fill_price * lots)
        self.state_manager.update_session(session_id, {
            'total_premium_paid': new_paid,
            f'current_{leg_type.lower()}_lots': new_lots
        })
        
        logger.success(f"Reduced {lots} {leg_type} lots @ ₹{fill_price:.2f}")
    
    async def _place_order(self, symbol: str, side: str, lots: int) -> Dict:
        """
        Place order with maker-first preference
        
        **0DTE SYSTEM** - Uses async_client.place_order_by_symbol()
        """
        preference = self.config.rebalancing.orders.preference
        timeout = self.config.rebalancing.orders.timeout_seconds
        
        try:
            ticker = await self.api_client.get_option_ticker(symbol)
            quotes = ticker.get('quotes', {})
            
            if side == 'sell':
                limit_price = float(quotes.get('best_bid', 0)) if quotes.get('best_bid') else float(ticker.get('mark_price', 0))
            else:
                limit_price = float(quotes.get('best_ask', 0)) if quotes.get('best_ask') else float(ticker.get('mark_price', 0))
            
            if preference == 'maker_first':
                # Try maker order first
                response = await self.api_client.async_client.place_order_by_symbol(
                    symbol=symbol,
                    side=side,
                    price=limit_price,
                    size=lots,
                    order_type='limit_order',
                    post_only=True
                )
                
                order_id = response.get('result', {}).get('id')
                fill_price = await self._wait_for_fill(order_id, timeout)
                
                if fill_price is None:
                    # Cancel and use market
                    logger.info(f"Maker order {order_id} not filled, converting to market")
                    product_id = await self.api_client.async_client.get_product_id(symbol)
                    await self.api_client.async_client.cancel_order(order_id, product_id)
                    
                    response = await self.api_client.async_client.place_order_by_symbol(
                        symbol=symbol,
                        side=side,
                        price=limit_price,
                        size=lots,
                        order_type='market_order'
                    )
                    order_id = response.get('result', {}).get('id')
                    fill_price = await self._wait_for_fill(order_id, 10) or limit_price
                
                return {'fill_price': fill_price, 'order_id': order_id}
            else:
                # Market order
                response = await self.api_client.async_client.place_order_by_symbol(
                    symbol=symbol,
                    side=side,
                    price=limit_price,
                    size=lots,
                    order_type='market_order'
                )
                order_id = response.get('result', {}).get('id')
                fill_price = await self._wait_for_fill(order_id, 10) or limit_price
                
                return {'fill_price': fill_price, 'order_id': order_id}
                
        except Exception as e:
            logger.error(f"❌ Order failed: {side} {lots} {symbol}: {e}")
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
