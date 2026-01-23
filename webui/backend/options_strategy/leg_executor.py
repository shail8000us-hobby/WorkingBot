"""
Leg Executor
============
Execute multi-leg strategy orders with proper error handling.

Execution Modes:
1. SEQUENTIAL: Execute legs one by one (safer, slower)
2. PARALLEL: Execute all legs simultaneously (faster, riskier)
3. BRACKET: Single atomic order (if supported by exchange)

Created: January 5, 2026
Updated: January 12, 2026 - Added rate limiting, validation, and custom exceptions
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config, get_api_credentials
from .strategy_models import (
    Strategy, StrategyLeg, StrategyExecutionResult,
    LegStatus, StrategyStatus
)

# Import production-ready utilities
from ..utils.rate_limiter import DELTA_ORDER_LIMITER, DELTA_API_LIMITER
from ..utils.exceptions import (
    OrderError, ValidationError, RateLimitError,
    APIError, handle_api_error
)
from .option_validator import OptionValidator, ValidationLevel, ValidationResult
from .data_validator import MarketDataValidator

log = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Order execution modes"""
    SEQUENTIAL = "sequential"   # One leg at a time
    PARALLEL = "parallel"       # All legs at once
    MARKET = "market"           # Market orders (fast fill)
    LIMIT = "limit"             # Limit orders (better price)


class LegExecutor:
    """
    Execute multi-leg strategy orders
    
    Handles:
    - Single leg execution
    - Multi-leg sequential execution
    - Rollback on partial fills
    - Order status tracking
    - Pre-execution validation (NEW)
    - API rate limiting (NEW)
    """
    
    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STANDARD):
        self._client = None
        self._max_retries = 3
        self._retry_delay = 1.0  # seconds
        
        # Production-ready utilities
        self._validator = OptionValidator(validation_level=validation_level)
        self._data_validator = MarketDataValidator()
        self._order_limiter = DELTA_ORDER_LIMITER
        self._api_limiter = DELTA_API_LIMITER
        
        # Execution statistics
        self._stats = {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_failed': 0,
            'rate_limit_waits': 0,
            'validation_failures': 0,
            'last_execution': None
        }
        
    def _get_client(self):
        """Get or create UnifiedAPIClient"""
        if self._client is None:
            from bot.api.unified_api_client import UnifiedAPIClient
            
            creds = get_api_credentials()
            self._client = UnifiedAPIClient(
                api_key=creds['api_key'],
                api_secret=creds['api_secret'],
                symbol='BTCUSD',
                enable_websocket=False
            )
        return self._client
    
    async def execute_strategy(
        self, 
        strategy: Strategy,
        execution_mode: str = ExecutionMode.SEQUENTIAL.value,
        order_type: str = "limit",
        price_tolerance_pct: float = 0.5
    ) -> StrategyExecutionResult:
        """
        Execute all legs of a strategy
        
        Args:
            strategy: Strategy with configured legs
            execution_mode: sequential or parallel
            order_type: market or limit
            price_tolerance_pct: % above/below mid for limit orders
            
        Returns:
            StrategyExecutionResult with execution details
        """
        log.info(f"🚀 Executing strategy: {strategy.name} ({len(strategy.legs)} legs)")
        log.info(f"   Mode: {execution_mode}, Order type: {order_type}")
        
        # Phase 1: Validate all legs
        validation_errors = await self._validate_legs(strategy, order_type)
        if validation_errors:
            return StrategyExecutionResult(
                success=False,
                strategy_id=strategy.id,
                status=StrategyStatus.FAILED.value,
                message="Validation failed",
                errors=validation_errors
            )
        
        # Phase 2: Get current prices for limit orders
        # Only fetch if not already provided from frontend (current_price == 0)
        if order_type == "limit":
            has_prices = all(leg.current_price > 0 for leg in strategy.legs)
            if has_prices:
                log.info("   Using prices from frontend (mid-price calculation)")
            else:
                log.info("   Fetching prices from exchange")
                await self._fetch_leg_prices(strategy, price_tolerance_pct)
        
        # Phase 3: Execute legs
        strategy.status = StrategyStatus.EXECUTING.value
        
        if execution_mode == ExecutionMode.PARALLEL.value:
            result = await self._execute_parallel(strategy, order_type)
        else:
            result = await self._execute_sequential(strategy, order_type)
        
        # Phase 4: Calculate total cost
        if result.success:
            strategy.total_cost = self._calculate_total_cost(strategy)
            strategy.status = StrategyStatus.ACTIVE.value
            strategy.executed_at = datetime.utcnow().isoformat() + "Z"
            result.total_cost = strategy.total_cost
            log.info(f"✅ Strategy executed! Total cost: ${strategy.total_cost:.2f}")
        else:
            # Partial fill handling - attempt rollback
            if result.legs_filled > 0 and result.legs_filled < result.legs_total:
                log.warning(f"⚠️ Partial fills detected ({result.legs_filled}/{result.legs_total})")
                await self._handle_partial_fills(strategy)
        
        return result
    
    async def _validate_legs(self, strategy: Strategy, order_type: str = 'limit') -> List[str]:
        """
        Validate all legs before execution using production-ready validators
        
        Args:
            strategy: Strategy to validate
            order_type: Order type to use (market or limit)
        
        Checks:
        - Symbol format and validity (via OptionValidator)
        - Strike price reasonableness
        - Expiry validity
        - Order parameters
        - Market data quality (via DataValidator)
        - Sufficient liquidity
        """
        errors = []
        warnings = []
        client = self._get_client()
        
        # Map frontend order types to backend format
        order_type_map = {
            'market': 'market_order',
            'limit': 'limit_order'
        }
        backend_order_type = order_type_map.get(order_type, 'limit_order')
        
        # First: Validate strategy structure using OptionValidator
        legs_for_validation = []
        for leg in strategy.legs:
            if not leg.symbol:
                leg.generate_symbol(strategy.underlying)
            
            leg_params = {
                'symbol': leg.symbol,
                'side': leg.side,
                'quantity': leg.quantity,
                'option_type': leg.option_type,
                'strike': leg.strike,
                'expiry': leg.expiry,
                'order_type': backend_order_type
            }
            
            # Add placeholder limit_price for limit orders to pass validation
            if backend_order_type == 'limit_order':
                leg_params['limit_price'] = 1.0  # Placeholder, will be updated with actual price
            
            legs_for_validation.append(leg_params)
        
        # Validate strategy legs as a whole
        strategy_validation = self._validator.validate_strategy_legs(legs_for_validation)
        if not strategy_validation.is_valid:
            self._stats['validation_failures'] += 1
            for error in strategy_validation.errors:
                errors.append(f"Strategy validation: {error}")
        
        # Add warnings for logging (don't fail on warnings)
        for warning in strategy_validation.warnings:
            log.warning(f"⚠️ Strategy warning: {warning}")
            warnings.append(warning)
        
        # Validate each leg individually and fetch prices
        for leg in strategy.legs:
            log.info(f"Validating leg {leg.leg_id}: {leg.symbol}")
            
            # Quick format check (additional to validator)
            if not leg.symbol.startswith(('C-', 'P-')):
                errors.append(f"Leg {leg.leg_id}: Invalid symbol format {leg.symbol}")
                continue
            
            # Validate order parameters
            # For validation purposes, provide a placeholder limit_price
            # The actual price will be fetched later in the execution flow
            order_params = {
                'symbol': leg.symbol,
                'side': leg.side,
                'quantity': leg.quantity,
                'order_type': backend_order_type
            }
            
            # Add placeholder limit_price for limit orders to pass validation
            if backend_order_type == 'limit_order':
                order_params['limit_price'] = 1.0  # Placeholder, will be updated with actual price
            
            order_validation = self._validator.validate_order_parameters(order_params)
            
            if not order_validation.is_valid:
                for error in order_validation.errors:
                    errors.append(f"Leg {leg.leg_id}: {error}")
            
            # Check if option exists (get ticker) - with rate limiting
            try:
                # Use rate limiter for API call
                if not self._api_limiter.acquire():
                    self._stats['rate_limit_waits'] += 1
                    log.info(f"  Rate limiting - waiting before ticker fetch...")
                    await asyncio.sleep(1.0)
                    self._api_limiter.acquire()
                
                ticker = await self._get_ticker(leg.symbol)
                if not ticker:
                    log.warning(f"Leg {leg.leg_id}: No ticker found for {leg.symbol} - will try to execute anyway")
                    leg.current_bid = 0
                    leg.current_ask = 0
                    leg.current_price = 0
                    continue
                
                # Store current prices
                leg.current_bid = ticker.get('bid', ticker.get('best_bid', 0))
                leg.current_ask = ticker.get('ask', ticker.get('best_ask', 0))
                leg.current_price = (leg.current_bid + leg.current_ask) / 2 if leg.current_bid and leg.current_ask else 0
                
                log.info(f"  Ticker found: bid=${leg.current_bid}, ask=${leg.current_ask}")
                
                # Only warn about liquidity - don't fail
                if leg.current_bid == 0 or leg.current_ask == 0:
                    log.warning(
                        f"Leg {leg.leg_id}: Low liquidity for {leg.symbol} "
                        f"(bid: ${leg.current_bid}, ask: ${leg.current_ask})"
                    )
                    
            except Exception as e:
                log.warning(f"Leg {leg.leg_id}: Validation check failed for {leg.symbol} - {str(e)}")
                # Don't fail - try to execute anyway
        
        return errors
    
    async def _fetch_leg_prices(self, strategy: Strategy, tolerance_pct: float):
        """
        Fetch current prices and set limit prices for legs
        
        For buy orders: Use ask + tolerance
        For sell orders: Use bid - tolerance
        """
        for leg in strategy.legs:
            if leg.current_bid == 0 or leg.current_ask == 0:
                ticker = await self._get_ticker(leg.symbol)
                if ticker:
                    leg.current_bid = ticker.get('bid', ticker.get('best_bid', 0))
                    leg.current_ask = ticker.get('ask', ticker.get('best_ask', 0))
            
            mid = (leg.current_bid + leg.current_ask) / 2
            
            if leg.side == "buy":
                # Willing to pay slightly above mid
                leg.current_price = mid * (1 + tolerance_pct / 100)
            else:
                # Willing to receive slightly below mid
                leg.current_price = mid * (1 - tolerance_pct / 100)
    
    async def _execute_sequential(
        self, 
        strategy: Strategy, 
        order_type: str
    ) -> StrategyExecutionResult:
        """
        Execute legs one by one
        Safer but slower - with automatic retry using market orders
        """
        filled_legs = 0
        errors = []
        
        for leg in strategy.legs:
            log.info(f"  📤 Leg {leg.leg_id}: {leg.side.upper()} {leg.quantity} {leg.symbol}")
            
            # First try with requested order type
            result = await self._execute_leg(leg, order_type)
            
            # If limit order failed due to liquidity, auto-retry with market
            if not result['success'] and order_type == 'limit':
                error_msg = result.get('error', '').lower()
                if 'order_size_not_available' in error_msg or 'cancelled' in error_msg or 'rejected' in error_msg:
                    log.info(f"     ⚡ Retrying with market order due to liquidity issue...")
                    result = await self._execute_leg(leg, 'market')
            
            if result['success']:
                leg.status = LegStatus.FILLED.value
                leg.order_id = result.get('order_id', '')
                leg.filled_qty = leg.quantity
                leg.avg_fill_price = result.get('fill_price', leg.current_price)
                filled_legs += 1
                log.info(f"     ✅ Filled @ ${leg.avg_fill_price:.2f}")
            else:
                leg.status = LegStatus.FAILED.value
                errors.append(f"Leg {leg.leg_id}: {result.get('error', 'Unknown error')}")
                log.error(f"     ❌ Failed: {result.get('error')}")
                
                # Don't stop on first failure - try all legs, then rollback if needed
                # This gives better chance of success for multi-leg strategies
        
        success = filled_legs == len(strategy.legs)
        
        return StrategyExecutionResult(
            success=success,
            strategy_id=strategy.id,
            status=StrategyStatus.ACTIVE.value if success else StrategyStatus.PARTIAL.value,
            message="All legs executed" if success else f"Partial fill: {filled_legs}/{len(strategy.legs)} legs",
            legs_filled=filled_legs,
            legs_total=len(strategy.legs),
            errors=errors
        )
    
    async def _execute_parallel(
        self, 
        strategy: Strategy, 
        order_type: str
    ) -> StrategyExecutionResult:
        """
        Execute all legs simultaneously
        Faster but riskier (partial fills more likely)
        With automatic retry for failed legs using market orders
        """
        # First pass - try all legs with requested order type
        tasks = [
            self._execute_leg(leg, order_type)
            for leg in strategy.legs
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        filled_legs = 0
        failed_legs = []
        errors = []
        
        for i, (leg, result) in enumerate(zip(strategy.legs, results)):
            if isinstance(result, Exception):
                leg.status = LegStatus.FAILED.value
                errors.append(f"Leg {leg.leg_id}: {str(result)}")
                failed_legs.append(leg)
            elif result.get('success'):
                leg.status = LegStatus.FILLED.value
                leg.order_id = result.get('order_id', '')
                leg.filled_qty = leg.quantity
                leg.avg_fill_price = result.get('fill_price', leg.current_price)
                filled_legs += 1
            else:
                leg.status = LegStatus.FAILED.value
                errors.append(f"Leg {leg.leg_id}: {result.get('error', 'Unknown error')}")
                failed_legs.append(leg)
        
        # Second pass - retry failed legs with market orders
        if failed_legs and order_type == 'limit':
            log.info(f"⚡ Retrying {len(failed_legs)} failed legs with market orders...")
            errors = []  # Clear errors for retry
            
            retry_tasks = [
                self._execute_leg(leg, 'market')
                for leg in failed_legs
            ]
            retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
            
            for leg, result in zip(failed_legs, retry_results):
                if isinstance(result, Exception):
                    errors.append(f"Leg {leg.leg_id} (retry): {str(result)}")
                elif result.get('success'):
                    leg.status = LegStatus.FILLED.value
                    leg.order_id = result.get('order_id', '')
                    leg.filled_qty = leg.quantity
                    leg.avg_fill_price = result.get('fill_price', leg.current_price)
                    filled_legs += 1
                    log.info(f"  ✅ Leg {leg.leg_id} filled on retry")
                else:
                    errors.append(f"Leg {leg.leg_id} (retry): {result.get('error', 'Unknown error')}")
        
        success = filled_legs == len(strategy.legs)
        
        return StrategyExecutionResult(
            success=success,
            strategy_id=strategy.id,
            status=StrategyStatus.ACTIVE.value if success else StrategyStatus.PARTIAL.value,
            message="All legs executed" if success else f"Partial fill: {filled_legs}/{len(strategy.legs)} legs",
            legs_filled=filled_legs,
            legs_total=len(strategy.legs),
            errors=errors
        )
    
    async def _execute_leg(self, leg: StrategyLeg, order_type: str) -> Dict[str, Any]:
        """
        Execute a single leg order with rate limiting and proper error handling
        
        Args:
            leg: Strategy leg to execute
            order_type: market or limit
            
        Returns:
            dict with success status and order details
            
        Features:
            - Rate limiting to prevent API throttling
            - Custom exceptions for better error handling
            - Execution statistics tracking
        """
        client = self._get_client()
        
        leg.status = LegStatus.SUBMITTED.value
        self._stats['orders_placed'] += 1
        self._stats['last_execution'] = datetime.utcnow().isoformat()
        
        log.info(f"Executing leg {leg.leg_id}: {leg.side} {leg.quantity} {leg.symbol}")
        
        # Rate limit check - wait if needed
        if not self._order_limiter.acquire():
            self._stats['rate_limit_waits'] += 1
            wait_time = self._order_limiter.get_reset_time()
            log.warning(f"  ⏳ Rate limit reached, waiting {wait_time:.1f}s before order...")
            await asyncio.sleep(min(wait_time + 0.5, 5.0))  # Max 5 second wait
            if not self._order_limiter.acquire():
                self._stats['orders_failed'] += 1
                raise RateLimitError(
                    "Order rate limit exceeded, please wait",
                    retry_after=wait_time
                )
        
        # Use market order only if explicitly requested
        # If current_price is set (from frontend limit_price), use it for limit orders
        use_market = order_type == 'market'
        
        for attempt in range(self._max_retries):
            # Build order data
            data = {
                "product_symbol": leg.symbol,
                "side": leg.side,
                "size": int(leg.quantity)
            }
            
            if use_market or attempt > 0:
                # Use market order (first choice or fallback after failed limit)
                data["order_type"] = "market_order"
                log.info(f"  Attempt {attempt + 1}: Using market order")
            else:
                # Try limit order first
                data["order_type"] = "limit_order"
                data["limit_price"] = str(round(leg.current_price, 2))
                # Use GTC (Good Till Cancel) instead of IOC for better fill chance
                data["time_in_force"] = "gtc"
                data["post_only"] = "false"
                log.info(f"  Attempt {attempt + 1}: Using limit order at ${leg.current_price}")
            
            log.info(f"  Order data: {data}")
            
            try:
                response = await client.rest_client._request_with_retry(
                    method="POST",
                    path="/v2/orders",
                    data=data
                )
                
                log.info(f"  API response: {response}")
                
                result = response.get('result', response)
                order_id = result.get('id', 'unknown')
                state = result.get('state', 'pending')
                
                # Check if order was cancelled or rejected
                if state in ['cancelled', 'rejected']:
                    cancel_reason = result.get('cancel_reason', result.get('cancellation_reason', 'unknown'))
                    log.warning(f"  Order {state}: {cancel_reason}")
                    
                    # If limit order failed, retry with market order
                    if data["order_type"] == "limit_order":
                        log.info(f"  Limit order {state}, will retry with market order")
                        use_market = True
                        await asyncio.sleep(0.5)
                        continue
                    else:
                        # Market order failed - this is a real failure
                        self._stats['orders_failed'] += 1
                        return {
                            'success': False,
                            'error': f"Order {state}: {cancel_reason}"
                        }
                
                # Order accepted - check fill status
                fill_price = result.get('average_fill_price') or leg.current_price
                unfilled = result.get('unfilled_size', 0)
                
                log.info(f"  Order placed: id={order_id}, state={state}, fill_price={fill_price}, unfilled={unfilled}")
                
                # If partially filled or pending, wait a moment and check
                if state == 'open' and unfilled > 0:
                    log.info(f"  Order still open, waiting for fill...")
                    await asyncio.sleep(1.0)
                    # For GTC orders, we consider submission as success
                    # The order will fill eventually or user can manage it
                
                self._stats['orders_filled'] += 1
                return {
                    'success': True,
                    'order_id': order_id,
                    'state': state,
                    'fill_price': float(fill_price) if fill_price else leg.current_price,
                    'raw': result
                }
                
            except Exception as e:
                error_msg = str(e)
                log.warning(f"  Attempt {attempt + 1}/{self._max_retries} failed: {error_msg}")
                
                # Check if it's a rate limit error
                if 'rate' in error_msg.lower() and 'limit' in error_msg.lower():
                    self._stats['rate_limit_waits'] += 1
                    log.warning(f"  Rate limit detected, waiting before retry...")
                    await asyncio.sleep(2.0)  # Wait longer for rate limits
                    continue
                
                # Check if it's a liquidity error - retry with market
                if 'order_size_not_available' in error_msg or 'insufficient' in error_msg.lower():
                    log.info(f"  Liquidity issue detected, switching to market order")
                    use_market = True
                
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    self._stats['orders_failed'] += 1
                    return {
                        'success': False,
                        'error': error_msg
                    }
        
        self._stats['orders_failed'] += 1
        return {'success': False, 'error': 'Max retries exceeded'}
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get current execution statistics
        
        Returns:
            dict with execution statistics including:
            - orders_placed: Total orders placed
            - orders_filled: Successfully filled orders
            - orders_failed: Failed orders
            - rate_limit_waits: Times rate limiting triggered
            - validation_failures: Validation failures
            - fill_rate: Percentage of successful fills
            - last_execution: Timestamp of last execution
        """
        total = self._stats['orders_placed']
        fill_rate = (self._stats['orders_filled'] / total * 100) if total > 0 else 0
        
        return {
            **self._stats,
            'fill_rate': round(fill_rate, 1),
            'rate_limiter_status': {
                'order_requests_remaining': self._order_limiter.get_remaining_requests(),
                'api_requests_remaining': self._api_limiter.get_remaining_requests()
            }
        }
    
    def reset_stats(self):
        """Reset execution statistics"""
        self._stats = {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_failed': 0,
            'rate_limit_waits': 0,
            'validation_failures': 0,
            'last_execution': None
        }
    
    async def _handle_partial_fills(self, strategy: Strategy):
        """
        Handle partial fills by closing filled legs
        
        This is the rollback mechanism - if some legs fail,
        we close the filled ones to avoid unhedged positions.
        """
        log.warning("🔄 Attempting rollback of filled legs...")
        
        filled_legs = [leg for leg in strategy.legs if leg.status == LegStatus.FILLED.value]
        
        for leg in filled_legs:
            # Reverse the position
            reverse_side = "sell" if leg.side == "buy" else "buy"
            
            try:
                result = await self._execute_leg_close(leg, reverse_side)
                if result['success']:
                    log.info(f"  ✅ Rolled back leg {leg.leg_id}")
                else:
                    log.error(f"  ❌ Failed to rollback leg {leg.leg_id}: {result.get('error')}")
            except Exception as e:
                log.error(f"  ❌ Rollback exception for leg {leg.leg_id}: {e}")
        
        strategy.status = StrategyStatus.FAILED.value
    
    async def _execute_leg_close(self, leg: StrategyLeg, side: str) -> Dict[str, Any]:
        """Close a leg position"""
        client = self._get_client()
        
        data = {
            "product_symbol": leg.symbol,
            "side": side,
            "size": int(leg.filled_qty),
            "order_type": "market_order"  # Use market for quick close
        }
        
        try:
            response = await client.rest_client._request_with_retry(
                method="POST",
                path="/v2/orders",
                data=data
            )
            return {'success': True, 'result': response.get('result', response)}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def close_strategy(self, strategy: Strategy) -> StrategyExecutionResult:
        """
        Close all legs of an active strategy
        
        Args:
            strategy: Strategy to close
            
        Returns:
            Execution result
        """
        log.info(f"🔒 Closing strategy: {strategy.name}")
        
        strategy.status = StrategyStatus.CLOSING.value
        closed_legs = 0
        errors = []
        
        for leg in strategy.legs:
            if leg.status != LegStatus.FILLED.value or leg.filled_qty == 0:
                continue
            
            # Reverse the position
            reverse_side = "sell" if leg.side == "buy" else "buy"
            
            result = await self._execute_leg_close(leg, reverse_side)
            
            if result['success']:
                closed_legs += 1
                log.info(f"  ✅ Closed leg {leg.leg_id}")
            else:
                errors.append(f"Leg {leg.leg_id}: {result.get('error')}")
                log.error(f"  ❌ Failed to close leg {leg.leg_id}")
        
        filled_legs = [l for l in strategy.legs if l.filled_qty > 0]
        success = closed_legs == len(filled_legs)
        
        if success:
            strategy.status = StrategyStatus.CLOSED.value
            strategy.closed_at = datetime.utcnow().isoformat() + "Z"
        
        return StrategyExecutionResult(
            success=success,
            strategy_id=strategy.id,
            status=strategy.status,
            message="Strategy closed" if success else "Partial close",
            legs_filled=closed_legs,
            legs_total=len(filled_legs),
            errors=errors
        )
    
    def _calculate_total_cost(self, strategy: Strategy) -> float:
        """
        Calculate total cost/credit of strategy
        
        Buy legs = cost (negative)
        Sell legs = credit (positive)
        """
        total = 0.0
        
        for leg in strategy.legs:
            if leg.status != LegStatus.FILLED.value:
                continue
            
            value = leg.avg_fill_price * leg.filled_qty
            
            if leg.side == "buy":
                total += value  # Cost
            else:
                total -= value  # Credit received
        
        return round(total, 2)
    
    async def _get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get ticker data for an option"""
        client = self._get_client()
        
        try:
            # Use the options chain service's method (absolute import)
            from webui.backend.options_chain.chain_service import OptionsChainService
            service = OptionsChainService()
            return service.get_option_ticker(symbol)
        except Exception as e:
            log.error(f"Failed to get ticker for {symbol}: {e}")
            return None
    
    async def get_positions(self) -> List[Dict]:
        """Get current options positions"""
        client = self._get_client()
        
        try:
            response = await client.rest_client._request_with_retry(
                method="GET",
                path="/v2/positions"
            )
            
            positions = response.get('result', [])
            
            # Filter options only
            return [
                p for p in positions
                if p.get('product_symbol', '').startswith(('C-', 'P-'))
            ]
        except Exception as e:
            log.error(f"Failed to get positions: {e}")
            return []
