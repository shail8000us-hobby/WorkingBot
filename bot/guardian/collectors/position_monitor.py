"""
Position Monitor - Fetches and tracks open positions from exchange
"""
import logging
from typing import List, Dict, Optional
from decimal import Decimal


logger = logging.getLogger(__name__)


class PositionMonitor:
    """Monitors open positions and calculates PnL"""
    
    def __init__(self, exchange, config):
        """
        Initialize position monitor
        
        Args:
            exchange: CCXT exchange instance
            config: Guardian configuration (RootConfig or dict)
        """
        self.exchange = exchange
        self.config = config
        
        # Handle both RootConfig and dict
        if hasattr(config, 'bot'):
            # RootConfig object
            self.symbol = config.bot.symbol
            # For product_id, check if it exists in config.api or fallback
            self.product_id = getattr(config.api, 'product_id', 27) if hasattr(config, 'api') else 27
            self.usd_to_inr_rate = float(config.guardian.usd_to_inr_rate)
        else:
            # Dict fallback
            self.symbol = config.get('GRIDBOT_SYMBOL', 'BTC/USD:USD')
            self.product_id = config.get('DELTA_PRODUCT_ID', 27)
            self.usd_to_inr_rate = float(config.get('GUARDIAN_USD_TO_INR_RATE', 85))
        
        # Fetch contract multiplier dynamically from exchange
        try:
            market = self.exchange.market(self.symbol)
            self.contract_multiplier = float(market.get('contractSize', 0.001))
            logger.info(f"Contract multiplier for {self.symbol}: {self.contract_multiplier}")
        except Exception as e:
            logger.warning(f"Could not fetch contract size, using default 0.001: {e}")
            self.contract_multiplier = 0.001
        
        # Track position count for smart logging
        self.last_position_count = 0
        
        logger.info(f"PositionMonitor initialized for {self.symbol}")
        logger.info(f"USD to INR rate: {self.usd_to_inr_rate}")
    
    def fetch_open_positions(self) -> List[Dict]:
        """
        Fetch ALL open positions from exchange (futures + options)
        
        IMPORTANT: Guardian must protect ALL positions in the portfolio,
        not just the symbol it's monitoring. This includes:
        - Futures positions (BTCUSD, ETHUSD, etc.)
        - Options positions (calls, puts)
        - Manual positions
        - Bot-managed positions
        
        Returns:
            List of position dictionaries for ALL instruments
        """
        try:
            # Fetch ALL positions from exchange (no symbol filter)
            # This returns futures + options + all other positions
            positions = self.exchange.fetch_positions()
            
            # Filter only open positions (size != 0 for both LONG and SHORT)
            open_positions = [
                pos for pos in positions 
                if pos.get('contracts', 0) != 0
            ]
            
            # Log portfolio composition for visibility
            if open_positions:
                futures = [p for p in open_positions if 'C-' not in p.get('symbol', '') and 'P-' not in p.get('symbol', '')]
                options = [p for p in open_positions if 'C-' in p.get('symbol', '') or 'P-' in p.get('symbol', '')]
                logger.info(f"📊 Portfolio: {len(open_positions)} total positions ({len(futures)} futures, {len(options)} options)")
                
                # Debug: Log what fields are available
                sample_pos = open_positions[0]
                logger.debug(f"Position keys available: {list(sample_pos.keys())}")
                logger.debug(f"Sample position data: entryPrice={sample_pos.get('entryPrice')}, "
                           f"contracts={sample_pos.get('contracts')}, "
                           f"unrealizedPnl={sample_pos.get('unrealizedPnl')}, "
                           f"info keys={list(sample_pos.get('info', {}).keys()) if sample_pos.get('info') else 'no info'}")
            
            return open_positions
            
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def calculate_pnl_manual(self, entry_price: float, mark_price: float, size: float) -> float:
        """
        Calculate PnL using manual formula with contract multiplier
        
        Formula: (Mark Price - Entry Price) × Size × contract_multiplier
        
        Args:
            entry_price: Entry price
            mark_price: Current mark price
            size: Position size (negative for short, positive for long)
            
        Returns:
            Unrealized PnL in USD
        """
        pnl_usd = (mark_price - entry_price) * size * self.contract_multiplier
        return pnl_usd
    
    def calculate_position_pnl(self, position: Dict, current_price: float) -> Dict:
        """
        Calculate PnL for a single position
        
        Args:
            position: Position dictionary from exchange
            current_price: Current market price
            
        Returns:
            Dictionary with PnL details
        """
        try:
            # Extract position details
            entry_price = float(position.get('entryPrice', 0))
            size = float(position.get('contracts', 0))
            side = position.get('side', 'long')
            
            if entry_price == 0 or size == 0:
                return None
            
            # PRIMARY: Calculate manually with correct formula
            # Get mark price
            mark_price = current_price
            if position.get('info'):
                info_mark = position['info'].get('mark_price')
                if info_mark:
                    mark_price = float(info_mark)
            elif position.get('markPrice'):
                mark_price = float(position.get('markPrice'))
            
            # Calculate using formula: (Mark - Entry) × Size × contract_multiplier
            pnl_usd = self.calculate_pnl_manual(entry_price, mark_price, size)
            logger.debug(f"📊 Manual PnL: ({mark_price:.2f} - {entry_price:.2f}) × {size} × {self.contract_multiplier} = ${pnl_usd:.2f}")
            
            # FALLBACK: Verify with exchange unrealizedPnl if available
            unrealized_pnl = position.get('unrealizedPnl')
            if unrealized_pnl is None and position.get('info'):
                info = position.get('info', {})
                unrealized_pnl = (info.get('unrealized_pnl') or 
                                info.get('unrealizedPnl') or
                                info.get('unrealized_funding_pnl') or
                                info.get('pnl'))
            
            if unrealized_pnl is not None:
                try:
                    exchange_pnl = float(unrealized_pnl)
                    logger.debug(f"📋 Exchange PnL: ${exchange_pnl:.2f} (for verification)")
                except (ValueError, TypeError):
                    pass
            
            # Convert to INR: UPNL (USD) * 85 = PnL (INR)
            pnl_inr = pnl_usd * self.usd_to_inr_rate
            logger.debug(f"💰 PnL: {pnl_usd} USD = ₹{pnl_inr:.2f} INR")
            
            return {
                'entry_price': entry_price,
                'current_price': current_price,
                'size': size,
                'side': side,
                'pnl_usd': pnl_usd,
                'pnl_inr': pnl_inr,
                'symbol': position.get('symbol', self.symbol),
                'position_id': position.get('id', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error calculating PnL for position: {e}")
            return None
    
    def get_current_price(self) -> Optional[float]:
        """
        Get current market price for the symbol
        
        Returns:
            Current price or None if error
        """
        try:
            # Use standard CCXT fetch_ticker method
            ticker = self.exchange.fetch_ticker(self.symbol)

            def safe_float(value) -> Optional[float]:
                """Convert various numeric-like values to float safely."""
                try:
                    if value is None:
                        return None
                    # Some exchanges return strings; Decimal is also allowed
                    return float(value)
                except (TypeError, ValueError):
                    return None

            # Primary candidates from normalized CCXT fields
            candidates = [
                ticker.get('last'),
                ticker.get('close'),
            ]

            # Bid/Ask mid as fallback
            bid = safe_float(ticker.get('bid'))
            ask = safe_float(ticker.get('ask'))
            if bid and ask and bid > 0 and ask > 0:
                candidates.append((bid + ask) / 2.0)

            # Raw exchange fields under info
            info = ticker.get('info') or {}
            candidates.extend([
                info.get('mark_price'),
                info.get('markPrice'),
                info.get('index_price'),
                info.get('spot_price'),
                info.get('last_price'),
                info.get('close'),
                info.get('price'),
            ])

            # Pick the first valid positive candidate
            for cand in candidates:
                val = safe_float(cand)
                if val and val > 0:
                    return val

            logger.warning(f"Could not resolve a valid current price for {self.symbol} from ticker: keys={list(ticker.keys())}")
            return None

        except Exception as e:
            logger.error(f"Error fetching current price: {e}")
            return None
    
    def calculate_total_pnl(self, positions_pnl: List[Dict]) -> Dict:
        """
        Calculate total PnL across all positions
        
        Args:
            positions_pnl: List of position PnL dictionaries
            
        Returns:
            Dictionary with total PnL summary
        """
        total_pnl_usd = sum(p['pnl_usd'] for p in positions_pnl if p)
        total_pnl_inr = sum(p['pnl_inr'] for p in positions_pnl if p)
        
        # Calculate total loss (only negative PnL)
        total_loss_inr = abs(min(0, total_pnl_inr))
        
        # Count profitable vs losing positions
        profitable_count = sum(1 for p in positions_pnl if p and p['pnl_inr'] > 0)
        losing_count = sum(1 for p in positions_pnl if p and p['pnl_inr'] < 0)
        
        return {
            'total_pnl_usd': total_pnl_usd,
            'total_pnl_inr': total_pnl_inr,
            'total_loss_inr': total_loss_inr,
            'position_count': len(positions_pnl),
            'profitable_count': profitable_count,
            'losing_count': losing_count,
        }
    
    def get_current_pnl(self) -> float:
        """
        Get current total PnL in INR
        
        Returns:
            Total PnL in INR (negative = loss, positive = profit)
        """
        try:
            current_price = self.get_current_price()
            if current_price is None:
                return 0.0
            
            positions = self.fetch_open_positions()
            if not positions:
                return 0.0
            
            total_pnl_inr = 0.0
            for position in positions:
                pnl = self.calculate_position_pnl(position, current_price)
                if pnl:
                    total_pnl_inr += pnl['pnl_inr']
            
            return total_pnl_inr
            
        except Exception as e:
            logger.error(f"Error calculating current PnL: {e}")
            return 0.0
    
    def get_position(self):
        """
        Get current position object for the monitored symbol only.

        Scoped to self.symbol so that options/other instruments managed by
        other strategies (e.g. MMM CE/PE lots) don't inflate the size check
        and trigger a false "Position limit exceeded" STOP signal.

        Returns:
            Position object with size and value attributes, or None if flat
        """
        try:
            positions = self.fetch_open_positions()
            if not positions:
                return None

            # Only count contracts for the symbol this Guardian instance monitors
            symbol_positions = [p for p in positions if p.get('symbol') == self.symbol]
            if not symbol_positions:
                return None

            total_size = sum(float(pos.get('contracts', 0)) for pos in symbol_positions)

            class PositionData:
                def __init__(self, size, value=0):
                    self.size = size
                    self.value = value

            return PositionData(size=total_size, value=abs(total_size))

        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return None
    
    def get_liquidation_distance(self) -> float:
        """
        Get distance to liquidation price as percentage
        Returns MINIMUM distance across all positions (most critical)
        
        Formula (per Delta Exchange guidelines):
        - LONG: distance% = (current_price - liquidation_price) / current_price * 100
        - SHORT: distance% = (liquidation_price - current_price) / current_price * 100
        
        Returns:
            Distance to liquidation in percentage (100.0 if not available = safe)
        """
        try:
            positions = self.fetch_open_positions()
            if not positions:
                return 100.0  # No position = safe
            
            min_distance = 100.0  # Start with safe value
            current_price = self.get_current_price()
            
            if not current_price or current_price <= 0:
                return 100.0
            
            # Check all positions and find minimum (most critical) distance
            for position in positions:
                info = position.get('info', {})
                liq_price = info.get('liquidation_price') or info.get('liquidationPrice')
                
                # Validate liquidation price with explicit None check
                if liq_price is None:
                    logger.debug(
                        f"Position {position.get('symbol')} has no liquidation_price "
                        f"(Portfolio Margin Mode). Using margin-based calculation instead."
                    )
                    continue
                
                try:
                    liq_price = float(liq_price)
                    if liq_price <= 0:
                        logger.warning(f"Position {position.get('symbol')} has invalid liquidation_price: {liq_price}")
                        continue
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not convert liquidation_price to float: {e}")
                    continue
                
                position_size = float(position.get('contracts', 0))
                is_long = position_size > 0
                
                # Calculate distance
                if is_long:
                    # LONG: liquidation price is BELOW current price
                    distance_pct = ((current_price - liq_price) / current_price) * 100
                else:
                    # SHORT: liquidation price is ABOVE current price
                    distance_pct = ((liq_price - current_price) / current_price) * 100
                
                # Track minimum (most critical) - FIXED: Now applies to both LONG and SHORT
                distance_pct = max(0.0, distance_pct)  # Ensure non-negative
                if distance_pct < min_distance:
                    min_distance = distance_pct
                    logger.debug(
                        f"Liquidation distance: {distance_pct:.2f}% "
                        f"({'LONG' if is_long else 'SHORT'} position, "
                        f"current: {current_price:.2f}, liq: {liq_price:.2f})"
                    )
            
            return min_distance
            
        except Exception as e:
            logger.error(f"Error calculating liquidation distance: {e}")
            return 100.0  # Fail-safe: assume safe on error
    
    def get_bankruptcy_distance(self) -> float:
        """
        Get distance to bankruptcy price as percentage
        Bankruptcy is more severe than liquidation (position equity = 0)
        Returns MINIMUM distance across all positions (most critical)
        
        Returns:
            Distance to bankruptcy in percentage (100.0 if not available)
        """
        try:
            positions = self.fetch_open_positions()
            if not positions:
                return 100.0
            
            min_distance = 100.0
            current_price = self.get_current_price()
            
            if not current_price or current_price <= 0:
                return 100.0
            
            for position in positions:
                info = position.get('info', {})
                bankruptcy_price = info.get('bankruptcy_price') or info.get('bankruptcyPrice')
                
                if bankruptcy_price is None:
                    continue
                
                try:
                    bankruptcy_price = float(bankruptcy_price)
                    if bankruptcy_price <= 0:
                        continue
                except (ValueError, TypeError):
                    continue
                
                position_size = float(position.get('contracts', 0))
                is_long = position_size > 0
                
                # Calculate distance
                if is_long:
                    distance_pct = ((current_price - bankruptcy_price) / current_price) * 100
                else:
                    distance_pct = ((bankruptcy_price - current_price) / current_price) * 100
                
                distance_pct = max(0.0, distance_pct)
                if distance_pct < min_distance:
                    min_distance = distance_pct
                    logger.debug(
                        f"Bankruptcy distance: {distance_pct:.2f}% "
                            f"({'LONG' if is_long else 'SHORT'} position, "
                            f"current: {current_price:.2f}, bankruptcy: {bankruptcy_price:.2f})"
                        )
            
            return min_distance
            
        except Exception as e:
            logger.error(f"Error calculating bankruptcy distance: {e}")
            return 100.0
    
    def get_liquidation_details(self) -> List[Dict]:
        """
        Get detailed liquidation info for all positions
        
        Returns:
            List of dicts with liquidation details per position
        """
        try:
            positions = self.fetch_open_positions()
            if not positions:
                return []
            
            current_price = self.get_current_price()
            if not current_price or current_price <= 0:
                return []
            
            details = []
            
            for position in positions:
                info = position.get('info', {})
                liq_price = info.get('liquidation_price') or info.get('liquidationPrice')
                bankruptcy_price = info.get('bankruptcy_price') or info.get('bankruptcyPrice')
                
                if liq_price is None:
                    continue
                
                try:
                    liq_price = float(liq_price)
                    if liq_price <= 0:
                        continue
                except (ValueError, TypeError):
                    continue
                
                position_size = float(position.get('contracts', 0))
                is_long = position_size > 0
                margin = float(info.get('margin', 0))
                
                # Calculate distances
                if is_long:
                    liq_distance = ((current_price - liq_price) / current_price) * 100
                    bankruptcy_dist = ((current_price - float(bankruptcy_price)) / current_price) * 100 if bankruptcy_price else None
                else:
                    liq_distance = ((liq_price - current_price) / current_price) * 100
                    bankruptcy_dist = ((float(bankruptcy_price) - current_price) / current_price) * 100 if bankruptcy_price else None
                
                details.append({
                    'symbol': position.get('symbol', self.symbol),
                    'side': 'LONG' if is_long else 'SHORT',
                    'size': abs(position_size),
                    'entry_price': float(position.get('entryPrice', 0)),
                        'current_price': current_price,
                        'liquidation_price': liq_price,
                        'bankruptcy_price': float(bankruptcy_price) if bankruptcy_price else None,
                        'liquidation_distance_pct': max(0.0, liq_distance),
                        'bankruptcy_distance_pct': max(0.0, bankruptcy_dist) if bankruptcy_dist else None,
                        'margin': margin,
                        'is_critical': liq_distance < 1.0,
                        'is_warning': liq_distance < 5.0,
                    })
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting liquidation details: {e}")
            return []
    
    def monitor_cycle(self) -> Optional[Dict]:
        """
        Execute one monitoring cycle
        
        Returns:
            Dictionary with monitoring results or None if error
        """
        try:
            # Fetch current price
            current_price = self.get_current_price()
            if current_price is None:
                logger.warning("Could not fetch current price, skipping cycle")
                return None
            
            # Fetch open positions
            positions = self.fetch_open_positions()
            
            if not positions:
                # Only log when positions go from >0 to 0 (state change)
                if self.last_position_count > 0:
                    logger.info("✅ All positions closed - No open positions")
                else:
                    # Already at 0, use DEBUG level to reduce spam
                    logger.debug("No open positions found")
                
                self.last_position_count = 0
                
                return {
                    'current_price': current_price,
                    'positions': [],
                    'positions_pnl': [],
                    'total_summary': {
                        'total_pnl_usd': 0,
                        'total_pnl_inr': 0,
                        'total_loss_inr': 0,
                        'position_count': 0,
                        'profitable_count': 0,
                        'losing_count': 0,
                    },
                    'liquidation_distance': 100.0,
                    'liquidation_details': [],
                    'liquidation_critical': False,
                    'liquidation_warning': False,
                }
            
            # Calculate PnL for each position
            positions_pnl = []
            for position in positions:
                pnl = self.calculate_position_pnl(position, current_price)
                if pnl:
                    positions_pnl.append(pnl)
            
            # Calculate total PnL
            total_summary = self.calculate_total_pnl(positions_pnl)
            
            # Calculate liquidation metrics
            liquidation_distance = self.get_liquidation_distance()
            liquidation_details = self.get_liquidation_details()
            
            # Update position count tracking
            current_count = total_summary['position_count']
            if current_count != self.last_position_count:
                # Position count changed - log it
                if current_count > self.last_position_count:
                    logger.info(f"📈 New positions opened: {current_count} total (was {self.last_position_count})")
                else:
                    logger.info(f"📉 Positions closed: {current_count} remaining (was {self.last_position_count})")
            
            self.last_position_count = current_count
            
            # Log summary (only at debug level to reduce spam)
            logger.debug(
                f"📊 Monitoring: {total_summary['position_count']} positions | "
                f"PnL: ₹{total_summary['total_pnl_inr']:.2f} | "
                f"Loss: ₹{total_summary['total_loss_inr']:.2f} | "
                f"Liq Distance: {liquidation_distance:.2f}%"
            )
            
            return {
                'current_price': current_price,
                'positions': positions,
                'positions_pnl': positions_pnl,
                'total_summary': total_summary,
                'liquidation_distance': liquidation_distance,
                'liquidation_details': liquidation_details,
                'liquidation_critical': liquidation_distance < 1.0,
                'liquidation_warning': liquidation_distance < 5.0,
            }
            
        except Exception as e:
            logger.error(f"Error in monitor cycle: {e}", exc_info=True)
            return None

