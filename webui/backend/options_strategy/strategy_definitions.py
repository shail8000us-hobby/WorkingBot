"""
Strategy Definitions
====================
Pre-built strategy templates with configuration.

Strategies:
- Straddle: Buy ATM Call + Put (neutral, unlimited profit)
- Strangle: Buy OTM Call + Put (neutral, cheaper than straddle)
- Iron Condor: Sell OTM spreads (neutral, limited profit/loss)
- Iron Butterfly: Sell ATM straddle + buy OTM wings (neutral)
- Call Spread: Buy/Sell calls at different strikes (bullish)
- Put Spread: Buy/Sell puts at different strikes (bearish)

Created: January 5, 2026
"""

from typing import Dict, List, Any, Optional
from .strategy_models import (
    StrategyLeg, Strategy, StrategyType,
    EntryConditions, ExitConditions, PayoffPoint, PayoffDiagram
)


class StrategyDefinitions:
    """
    Factory class for creating pre-built strategy configurations.
    
    Each method returns a Strategy object with legs configured
    but not yet executed.
    """
    
    @staticmethod
    def straddle(
        underlying: str,
        strike: float,
        expiry: str,
        quantity: int = 1,
        entry_conditions: Optional[Dict] = None,
        exit_conditions: Optional[Dict] = None
    ) -> Strategy:
        """
        Long Straddle
        =============
        Buy ATM Call + ATM Put at same strike
        
        Outlook: Expecting BIG move, direction unknown
        Max Profit: Unlimited (either direction)
        Max Loss: Total premium paid
        Breakeven: Strike ± Total premium
        
        Best when: High IV expected, earnings, major events
        
        Args:
            underlying: BTC or ETH
            strike: Strike price (usually ATM)
            expiry: Expiry date (DDMMYYYY)
            quantity: Number of contracts per leg
        """
        legs = [
            StrategyLeg(
                leg_id=1,
                option_type="call",
                strike=strike,
                expiry=expiry,
                side="buy",
                quantity=quantity
            ),
            StrategyLeg(
                leg_id=2,
                option_type="put",
                strike=strike,
                expiry=expiry,
                side="buy",
                quantity=quantity
            )
        ]
        
        # Generate symbols
        for leg in legs:
            leg.generate_symbol(underlying)
        
        strategy = Strategy(
            strategy_type=StrategyType.LONG_STRADDLE.value,
            underlying=underlying,
            expiry=expiry,
            legs=legs,
            entry_conditions=EntryConditions.from_dict(entry_conditions or {}),
            exit_conditions=ExitConditions.from_dict(exit_conditions or {
                'profit_target_pct': 30,
                'stop_loss_pct': -50,
                'dte_exit': 3
            })
        )
        
        strategy.generate_name()
        strategy.max_profit = None  # Unlimited
        
        return strategy
    
    # Alias for backward compatibility
    long_straddle = straddle
    
    @staticmethod
    def short_straddle(
        underlying: str,
        strike: float,
        expiry: str,
        quantity: int = 1,
        entry_conditions: Optional[Dict] = None,
        exit_conditions: Optional[Dict] = None
    ) -> Strategy:
        """
        Short Straddle
        ==============
        Sell ATM Call + ATM Put at same strike
        
        Outlook: Expecting LOW volatility, price to stay near strike
        Max Profit: Total premium received
        Max Loss: UNLIMITED (either direction)
        Breakeven: Strike ± Total premium received
        
        WARNING: HIGH RISK strategy - unlimited loss potential!
        Best when: Low IV expected, range-bound market
        
        Args:
            underlying: BTC or ETH
            strike: Strike price (usually ATM)
            expiry: Expiry date (DDMMYYYY)
            quantity: Number of contracts per leg
        """
        legs = [
            StrategyLeg(
                leg_id=1,
                option_type="call",
                strike=strike,
                expiry=expiry,
                side="sell",
                quantity=quantity
            ),
            StrategyLeg(
                leg_id=2,
                option_type="put",
                strike=strike,
                expiry=expiry,
                side="sell",
                quantity=quantity
            )
        ]
        
        # Generate symbols
        for leg in legs:
            leg.generate_symbol(underlying)
        
        strategy = Strategy(
            strategy_type=StrategyType.SHORT_STRADDLE.value,
            underlying=underlying,
            expiry=expiry,
            legs=legs,
            entry_conditions=EntryConditions.from_dict(entry_conditions or {}),
            exit_conditions=ExitConditions.from_dict(exit_conditions or {
                'profit_target_pct': 50,  # Exit early when half premium captured
                'stop_loss_pct': -100,    # Stop at 1x premium loss
                'dte_exit': 5             # Exit earlier due to gamma risk
            })
        )
        
        strategy.generate_name()
        strategy.max_loss = None  # Unlimited
        
        return strategy
    
    @staticmethod
    def strangle(
        underlying: str,
        call_strike: float,
        put_strike: float,
        expiry: str,
        quantity: int = 1,
        entry_conditions: Optional[Dict] = None,
        exit_conditions: Optional[Dict] = None
    ) -> Strategy:
        """
        Long Strangle
        =============
        Buy OTM Call + OTM Put at different strikes
        
        Outlook: Expecting BIG move, direction unknown
        Max Profit: Unlimited (either direction)
        Max Loss: Total premium paid (less than straddle)
        Breakeven: Call strike + premium OR Put strike - premium
        
        Best when: Cheaper alternative to straddle, need bigger move
        
        Args:
            underlying: BTC or ETH
            call_strike: OTM call strike (above spot)
            put_strike: OTM put strike (below spot)
            expiry: Expiry date (DDMMYYYY)
            quantity: Number of contracts per leg
        """
        if call_strike <= put_strike:
            raise ValueError("Call strike must be higher than put strike for strangle")
        
        legs = [
            StrategyLeg(
                leg_id=1,
                option_type="call",
                strike=call_strike,
                expiry=expiry,
                side="buy",
                quantity=quantity
            ),
            StrategyLeg(
                leg_id=2,
                option_type="put",
                strike=put_strike,
                expiry=expiry,
                side="buy",
                quantity=quantity
            )
        ]
        
        for leg in legs:
            leg.generate_symbol(underlying)
        
        strategy = Strategy(
            strategy_type=StrategyType.LONG_STRANGLE.value,
            underlying=underlying,
            expiry=expiry,
            legs=legs,
            entry_conditions=EntryConditions.from_dict(entry_conditions or {}),
            exit_conditions=ExitConditions.from_dict(exit_conditions or {
                'profit_target_pct': 50,
                'stop_loss_pct': -60,
                'dte_exit': 3
            })
        )
        
        strategy.generate_name()
        strategy.max_profit = None  # Unlimited
        
        return strategy
    
    # Alias for backward compatibility
    long_strangle = strangle
    
    @staticmethod
    def short_strangle(
        underlying: str,
        call_strike: float,
        put_strike: float,
        expiry: str,
        quantity: int = 1,
        entry_conditions: Optional[Dict] = None,
        exit_conditions: Optional[Dict] = None
    ) -> Strategy:
        """
        Short Strangle
        ==============
        Sell OTM Call + OTM Put at different strikes
        
        Outlook: Expecting LOW volatility, price to stay in range
        Max Profit: Total premium received
        Max Loss: UNLIMITED (either direction)
        Breakeven: Call strike + premium OR Put strike - premium
        
        WARNING: HIGH RISK strategy - unlimited loss potential!
        Best when: Low IV expected, wider range expected than short straddle
        
        Args:
            underlying: BTC or ETH
            call_strike: OTM call strike (above spot)
            put_strike: OTM put strike (below spot)
            expiry: Expiry date (DDMMYYYY)
            quantity: Number of contracts per leg
        """
        if call_strike <= put_strike:
            raise ValueError("Call strike must be higher than put strike for strangle")
        
        legs = [
            StrategyLeg(
                leg_id=1,
                option_type="call",
                strike=call_strike,
                expiry=expiry,
                side="sell",
                quantity=quantity
            ),
            StrategyLeg(
                leg_id=2,
                option_type="put",
                strike=put_strike,
                expiry=expiry,
                side="sell",
                quantity=quantity
            )
        ]
        
        for leg in legs:
            leg.generate_symbol(underlying)
        
        strategy = Strategy(
            strategy_type=StrategyType.SHORT_STRANGLE.value,
            underlying=underlying,
            expiry=expiry,
            legs=legs,
            entry_conditions=EntryConditions.from_dict(entry_conditions or {}),
            exit_conditions=ExitConditions.from_dict(exit_conditions or {
                'profit_target_pct': 50,  # Exit early when half premium captured
                'stop_loss_pct': -100,    # Stop at 1x premium loss
                'dte_exit': 5             # Exit earlier due to gamma risk
            })
        )
        
        strategy.generate_name()
        strategy.max_loss = None  # Unlimited
        
        return strategy
    
    @staticmethod
    def iron_condor(
        underlying: str,
        call_sell_strike: float,
        call_buy_strike: float,
        put_sell_strike: float,
        put_buy_strike: float,
        expiry: str,
        quantity: int = 1,
        entry_conditions: Optional[Dict] = None,
        exit_conditions: Optional[Dict] = None
    ) -> Strategy:
        """
        Iron Condor
        ===========
        Sell OTM Call Spread + Sell OTM Put Spread
        
        Structure:
        - Sell OTM Call (lower strike)
        - Buy OTM Call (higher strike) - protection
        - Sell OTM Put (higher strike)  
        - Buy OTM Put (lower strike) - protection
        
        Outlook: Range-bound, LOW volatility expected
        Max Profit: Net credit received
        Max Loss: Width of spread - credit
        Breakeven: Short strikes ± credit
        
        Best when: IV is high (sell premium), expecting range
        
        Args:
            underlying: BTC or ETH
            call_sell_strike: Lower call strike (sell)
            call_buy_strike: Higher call strike (buy, protection)
            put_sell_strike: Higher put strike (sell)
            put_buy_strike: Lower put strike (buy, protection)
            expiry: Expiry date (DDMMYYYY)
            quantity: Number of contracts per leg
        """
        # Validate strikes
        if call_buy_strike <= call_sell_strike:
            raise ValueError("Call buy strike must be higher than call sell strike")
        if put_buy_strike >= put_sell_strike:
            raise ValueError("Put buy strike must be lower than put sell strike")
        if put_sell_strike >= call_sell_strike:
            raise ValueError("Put sell strike must be below call sell strike")
        
        legs = [
            # Call spread (sell lower, buy higher)
            StrategyLeg(
                leg_id=1,
                option_type="call",
                strike=call_sell_strike,
                expiry=expiry,
                side="sell",
                quantity=quantity
            ),
            StrategyLeg(
                leg_id=2,
                option_type="call",
                strike=call_buy_strike,
                expiry=expiry,
                side="buy",
                quantity=quantity
            ),
            # Put spread (sell higher, buy lower)
            StrategyLeg(
                leg_id=3,
                option_type="put",
                strike=put_sell_strike,
                expiry=expiry,
                side="sell",
                quantity=quantity
            ),
            StrategyLeg(
                leg_id=4,
                option_type="put",
                strike=put_buy_strike,
                expiry=expiry,
                side="buy",
                quantity=quantity
            )
        ]
        
        for leg in legs:
            leg.generate_symbol(underlying)
        
        strategy = Strategy(
            strategy_type=StrategyType.IRON_CONDOR.value,
            underlying=underlying,
            expiry=expiry,
            legs=legs,
            entry_conditions=EntryConditions.from_dict(entry_conditions or {}),
            exit_conditions=ExitConditions.from_dict(exit_conditions or {
                'profit_target_pct': 50,  # Take profits at 50% of max
                'stop_loss_pct': -100,    # Max loss = width - credit
                'dte_exit': 5             # Earlier exit (4 legs = more risk)
            })
        )
        
        strategy.generate_name()
        # Max profit/loss calculated after pricing
        
        return strategy
    
    @staticmethod
    def iron_butterfly(
        underlying: str,
        center_strike: float,
        wing_width: float,
        expiry: str,
        quantity: int = 1,
        entry_conditions: Optional[Dict] = None,
        exit_conditions: Optional[Dict] = None
    ) -> Strategy:
        """
        Iron Butterfly
        ==============
        Sell ATM Straddle + Buy OTM Strangle (wings)
        
        Structure:
        - Sell ATM Call
        - Sell ATM Put
        - Buy OTM Call (wing)
        - Buy OTM Put (wing)
        
        Outlook: Very range-bound, pinning at strike
        Max Profit: Net credit (at center strike)
        Max Loss: Wing width - credit
        
        Best when: Expecting price to stay exactly at strike
        
        Args:
            underlying: BTC or ETH
            center_strike: ATM strike (sell straddle here)
            wing_width: Distance to wing strikes
            expiry: Expiry date (DDMMYYYY)
            quantity: Number of contracts per leg
        """
        call_wing = center_strike + wing_width
        put_wing = center_strike - wing_width
        
        legs = [
            # Sell ATM straddle
            StrategyLeg(
                leg_id=1,
                option_type="call",
                strike=center_strike,
                expiry=expiry,
                side="sell",
                quantity=quantity
            ),
            StrategyLeg(
                leg_id=2,
                option_type="put",
                strike=center_strike,
                expiry=expiry,
                side="sell",
                quantity=quantity
            ),
            # Buy wings (protection)
            StrategyLeg(
                leg_id=3,
                option_type="call",
                strike=call_wing,
                expiry=expiry,
                side="buy",
                quantity=quantity
            ),
            StrategyLeg(
                leg_id=4,
                option_type="put",
                strike=put_wing,
                expiry=expiry,
                side="buy",
                quantity=quantity
            )
        ]
        
        for leg in legs:
            leg.generate_symbol(underlying)
        
        strategy = Strategy(
            strategy_type=StrategyType.IRON_BUTTERFLY.value,
            underlying=underlying,
            expiry=expiry,
            legs=legs,
            entry_conditions=EntryConditions.from_dict(entry_conditions or {}),
            exit_conditions=ExitConditions.from_dict(exit_conditions or {
                'profit_target_pct': 25,
                'stop_loss_pct': -100,
                'dte_exit': 3
            })
        )
        
        strategy.generate_name()
        return strategy
    
    @staticmethod
    def call_spread(
        underlying: str,
        buy_strike: float,
        sell_strike: float,
        expiry: str,
        quantity: int = 1,
        entry_conditions: Optional[Dict] = None,
        exit_conditions: Optional[Dict] = None
    ) -> Strategy:
        """
        Bull Call Spread (Debit)
        ========================
        Buy lower strike Call + Sell higher strike Call
        
        Outlook: Moderately bullish
        Max Profit: Difference in strikes - premium paid
        Max Loss: Net premium paid
        Breakeven: Lower strike + premium
        
        Best when: Bullish but want to reduce cost
        
        Args:
            underlying: BTC or ETH
            buy_strike: Lower strike (buy, ITM or ATM)
            sell_strike: Higher strike (sell, OTM)
            expiry: Expiry date (DDMMYYYY)
            quantity: Number of contracts per leg
        """
        if sell_strike <= buy_strike:
            raise ValueError("Sell strike must be higher than buy strike for bull call spread")
        
        legs = [
            StrategyLeg(
                leg_id=1,
                option_type="call",
                strike=buy_strike,
                expiry=expiry,
                side="buy",
                quantity=quantity
            ),
            StrategyLeg(
                leg_id=2,
                option_type="call",
                strike=sell_strike,
                expiry=expiry,
                side="sell",
                quantity=quantity
            )
        ]
        
        for leg in legs:
            leg.generate_symbol(underlying)
        
        strategy = Strategy(
            strategy_type=StrategyType.CALL_SPREAD.value,
            underlying=underlying,
            expiry=expiry,
            legs=legs,
            entry_conditions=EntryConditions.from_dict(entry_conditions or {}),
            exit_conditions=ExitConditions.from_dict(exit_conditions or {
                'profit_target_pct': 70,
                'stop_loss_pct': -50,
                'dte_exit': 2
            })
        )
        
        strategy.generate_name()
        strategy.max_profit = (sell_strike - buy_strike) * quantity  # Per contract
        
        return strategy
    
    @staticmethod
    def put_spread(
        underlying: str,
        buy_strike: float,
        sell_strike: float,
        expiry: str,
        quantity: int = 1,
        entry_conditions: Optional[Dict] = None,
        exit_conditions: Optional[Dict] = None
    ) -> Strategy:
        """
        Bear Put Spread (Debit)
        =======================
        Buy higher strike Put + Sell lower strike Put
        
        Outlook: Moderately bearish
        Max Profit: Difference in strikes - premium paid
        Max Loss: Net premium paid
        Breakeven: Higher strike - premium
        
        Best when: Bearish but want to reduce cost
        
        Args:
            underlying: BTC or ETH
            buy_strike: Higher strike (buy, ITM or ATM)
            sell_strike: Lower strike (sell, OTM)
            expiry: Expiry date (DDMMYYYY)
            quantity: Number of contracts per leg
        """
        if sell_strike >= buy_strike:
            raise ValueError("Sell strike must be lower than buy strike for bear put spread")
        
        legs = [
            StrategyLeg(
                leg_id=1,
                option_type="put",
                strike=buy_strike,
                expiry=expiry,
                side="buy",
                quantity=quantity
            ),
            StrategyLeg(
                leg_id=2,
                option_type="put",
                strike=sell_strike,
                expiry=expiry,
                side="sell",
                quantity=quantity
            )
        ]
        
        for leg in legs:
            leg.generate_symbol(underlying)
        
        strategy = Strategy(
            strategy_type=StrategyType.PUT_SPREAD.value,
            underlying=underlying,
            expiry=expiry,
            legs=legs,
            entry_conditions=EntryConditions.from_dict(entry_conditions or {}),
            exit_conditions=ExitConditions.from_dict(exit_conditions or {
                'profit_target_pct': 70,
                'stop_loss_pct': -50,
                'dte_exit': 2
            })
        )
        
        strategy.generate_name()
        strategy.max_profit = (buy_strike - sell_strike) * quantity
        
        return strategy
    
    @classmethod
    def create_strategy(
        cls, 
        strategy_type: str, 
        underlying: str = "BTC",
        expiry: str = None,
        **params
    ) -> Strategy:
        """
        Factory method to create strategy by type
        
        Args:
            strategy_type: One of StrategyType values
            underlying: BTC or ETH
            expiry: Expiry date (YYMMDD)
            **params: Strategy-specific parameters
            
        Returns:
            Configured Strategy object
        """
        creators = {
            # Long (debit) strategies
            StrategyType.STRADDLE.value: cls.straddle,
            StrategyType.LONG_STRADDLE.value: cls.long_straddle,
            StrategyType.STRANGLE.value: cls.strangle,
            StrategyType.LONG_STRANGLE.value: cls.long_strangle,
            
            # Short (credit) strategies
            StrategyType.SHORT_STRADDLE.value: cls.short_straddle,
            StrategyType.SHORT_STRANGLE.value: cls.short_strangle,
            
            # Multi-leg strategies
            StrategyType.IRON_CONDOR.value: cls.iron_condor,
            StrategyType.IRON_BUTTERFLY.value: cls.iron_butterfly,
            
            # Vertical spreads
            StrategyType.CALL_SPREAD.value: cls.call_spread,
            StrategyType.PUT_SPREAD.value: cls.put_spread
        }
        
        creator = creators.get(strategy_type)
        if not creator:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        
        # Add underlying and expiry to params
        params['underlying'] = underlying
        params['expiry'] = expiry
        
        return creator(**params)
    
    @staticmethod
    def get_available_strategies() -> List[Dict[str, Any]]:
        """
        Get list of available strategy types with descriptions
        """
        return [
            {
                "type": StrategyType.STRADDLE.value,
                "name": "Long Straddle",
                "description": "Buy ATM Call + Put. Profit from big moves in either direction.",
                "legs": 2,
                "direction": "neutral",
                "max_profit": "unlimited",
                "max_loss": "premium paid",
                "complexity": "beginner",
                "best_for": "High volatility expected, major events"
            },
            {
                "type": StrategyType.STRANGLE.value,
                "name": "Long Strangle",
                "description": "Buy OTM Call + Put. Cheaper than straddle, needs bigger move.",
                "legs": 2,
                "direction": "neutral",
                "max_profit": "unlimited",
                "max_loss": "premium paid",
                "complexity": "beginner",
                "best_for": "Expecting big move, want lower cost"
            },
            {
                "type": StrategyType.IRON_CONDOR.value,
                "name": "Iron Condor",
                "description": "Sell OTM Call & Put spreads. Profit from range-bound market.",
                "legs": 4,
                "direction": "neutral",
                "max_profit": "credit received",
                "max_loss": "spread width - credit",
                "complexity": "intermediate",
                "best_for": "Low volatility, range-bound market"
            },
            {
                "type": StrategyType.IRON_BUTTERFLY.value,
                "name": "Iron Butterfly",
                "description": "Sell ATM straddle + buy wings. Max profit at center strike.",
                "legs": 4,
                "direction": "neutral",
                "max_profit": "credit received",
                "max_loss": "wing width - credit",
                "complexity": "intermediate",
                "best_for": "Expecting price to pin at strike"
            },
            {
                "type": StrategyType.CALL_SPREAD.value,
                "name": "Bull Call Spread",
                "description": "Buy lower Call + Sell higher Call. Bullish with limited risk.",
                "legs": 2,
                "direction": "bullish",
                "max_profit": "strike difference - premium",
                "max_loss": "premium paid",
                "complexity": "beginner",
                "best_for": "Moderately bullish outlook"
            },
            {
                "type": StrategyType.PUT_SPREAD.value,
                "name": "Bear Put Spread",
                "description": "Buy higher Put + Sell lower Put. Bearish with limited risk.",
                "legs": 2,
                "direction": "bearish",
                "max_profit": "strike difference - premium",
                "max_loss": "premium paid",
                "complexity": "beginner",
                "best_for": "Moderately bearish outlook"
            }
        ]


class PayoffCalculator:
    """
    Calculate payoff diagrams for strategies
    """
    
    @staticmethod
    def calculate_payoff(
        strategy: Strategy, 
        spot_range: tuple = None, 
        points: int = 50,
        price_range_pct: float = 20.0,
        num_points: int = None
    ) -> PayoffDiagram:
        """
        Calculate payoff diagram for a strategy
        
        Args:
            strategy: Strategy with legs
            spot_range: (min, max) spot prices to calculate (legacy)
            points: Number of points in diagram (legacy)
            price_range_pct: % above/below strike range to calculate
            num_points: Number of points (overrides points if set)
            
        Returns:
            PayoffDiagram with P&L at each price point
        """
        # Use new params if provided
        if num_points:
            points = num_points
            
        if not strategy.legs:
            return PayoffDiagram()
        
        # Determine spot range based on strikes
        strikes = [leg.strike for leg in strategy.legs]
        min_strike = min(strikes)
        max_strike = max(strikes)
        center = (min_strike + max_strike) / 2
        
        if spot_range:
            spot_min, spot_max = spot_range
        else:
            # Use price_range_pct to determine range
            range_amount = center * (price_range_pct / 100)
            spot_min = center - range_amount
            spot_max = center + range_amount
        
        step = (spot_max - spot_min) / points
        
        payoff_points = []
        breakevens = []
        max_profit = float('-inf')
        max_loss = float('inf')
        
        prev_pnl = None
        
        for i in range(points + 1):
            spot = spot_min + (step * i)
            pnl = PayoffCalculator._calculate_pnl_at_expiry(strategy, spot)
            
            payoff_points.append(PayoffPoint(spot_price=spot, pnl=pnl))
            
            # Track max profit/loss
            if pnl > max_profit:
                max_profit = pnl
            if pnl < max_loss:
                max_loss = pnl
            
            # Find breakeven points (where PnL crosses zero)
            if prev_pnl is not None:
                if (prev_pnl < 0 and pnl >= 0) or (prev_pnl > 0 and pnl <= 0):
                    # Linear interpolation for more accurate breakeven
                    if pnl != prev_pnl:
                        breakeven = spot - step * (pnl / (pnl - prev_pnl))
                        breakevens.append(round(breakeven, 2))
            
            prev_pnl = pnl
        
        return PayoffDiagram(
            points=payoff_points,
            breakeven_points=breakevens,
            max_profit=max_profit if max_profit != float('-inf') else None,
            max_loss=max_loss if max_loss != float('inf') else None,
            current_spot=strategy.legs[0].strike  # Default to first strike
        )
    
    @staticmethod
    def _calculate_pnl_at_expiry(strategy: Strategy, spot: float) -> float:
        """
        Calculate P&L at expiry for given spot price
        
        At expiry:
        - Call value = max(0, spot - strike)
        - Put value = max(0, strike - spot)
        """
        total_pnl = 0.0
        
        for leg in strategy.legs:
            # Calculate option value at expiry
            if leg.option_type == "call":
                intrinsic = max(0, spot - leg.strike)
            else:  # put
                intrinsic = max(0, leg.strike - spot)
            
            # Get premium (cost/credit)
            premium = leg.avg_fill_price if leg.avg_fill_price > 0 else leg.current_price
            
            # Calculate leg P&L
            if leg.side == "buy":
                # Long: Profit = Value at expiry - Premium paid
                leg_pnl = (intrinsic - premium) * leg.quantity
            else:
                # Short: Profit = Premium received - Value at expiry
                leg_pnl = (premium - intrinsic) * leg.quantity
            
            total_pnl += leg_pnl
        
        return round(total_pnl, 2)
