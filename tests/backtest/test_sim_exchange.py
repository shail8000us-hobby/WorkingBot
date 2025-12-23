"""
Unit Tests for SimExchange

Tests basic fill logic, position tracking, and fee calculation.
"""

import pytest
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backtest.sim.sim_exchange import SimExchange
from backtest.sim.fee_model import FeeModel
from backtest.sim.funding_model import FundingModel


class TestSimExchange:
    """Test suite for SimExchange."""
    
    def setup_method(self):
        """Setup before each test."""
        self.sim = SimExchange(
            symbol="BTC/USD:USD",
            initial_balance=0.0,
            fee_model=FeeModel(assume_maker=True),
            funding_model=FundingModel(mode='off'),
            tick_size=0.5
        )
    
    def test_create_order(self):
        """Test order creation."""
        order = self.sim.create_order(
            side='buy',
            price=100000.0,
            amount=1.0,
            reduce_only=False
        )
        
        assert order['side'] == 'buy'
        assert order['price'] == 100000.0
        assert order['amount'] == 1.0
        assert order['status'] == 'open'
    
    def test_buy_fill(self):
        """Test BUY order fills when price touches low."""
        # Place BUY at 100,000
        order = self.sim.create_order(
            side='buy',
            price=100000.0,
            amount=1.0
        )
        
        # Candle with low at 100,000 (touches)
        self.sim.process_candle(
            timestamp=datetime(2025, 10, 1, 12, 0),
            open_price=101000.0,
            high=101500.0,
            low=100000.0,  # Touches BUY price
            close=101000.0,
            volume=100.0
        )
        
        # Check order is filled
        assert order['id'] in self.sim.orders
        assert self.sim.orders[order['id']].status.value == 'filled'
        
        # Check position
        position = self.sim.get_position()
        assert position['contracts'] == 1.0
        assert position['side'] == 'long'
    
    def test_sell_fill(self):
        """Test SELL (TP) order fills when price touches high."""
        # First create a long position
        self.sim.create_order(side='buy', price=100000.0, amount=1.0)
        self.sim.process_candle(
            datetime(2025, 10, 1, 12, 0),
            101000, 101500, 100000, 101000, 100
        )
        
        # Place TP at 101,000
        tp_order = self.sim.create_order(
            side='sell',
            price=101000.0,
            amount=1.0,
            reduce_only=True
        )
        
        # Candle with high at 101,000 (touches)
        self.sim.process_candle(
            timestamp=datetime(2025, 10, 1, 12, 5),
            open_price=100500.0,
            high=101000.0,  # Touches TP price
            low=100000.0,
            close=100500.0,
            volume=100.0
        )
        
        # Check TP is filled
        assert self.sim.orders[tp_order['id']].status.value == 'filled'
        
        # Check position closed
        position = self.sim.get_position()
        assert position['contracts'] == 0
        assert position['side'] == 'none'
    
    def test_complete_cycle_pnl(self):
        """Test a complete BUY->TP cycle calculates PnL correctly."""
        # BUY at 100,000
        buy_order = self.sim.create_order(side='buy', price=100000.0, amount=1.0)
        self.sim.process_candle(
            datetime(2025, 10, 1, 12, 0),
            101000, 101500, 100000, 101000, 100
        )
        
        # TP at 101,000 (STEP = 1000)
        tp_order = self.sim.create_order(
            side='sell',
            price=101000.0,
            amount=1.0,
            reduce_only=True
        )
        self.sim.process_candle(
            datetime(2025, 10, 1, 12, 5),
            100500, 101000, 100000, 100500, 100
        )
        
        # Calculate expected PnL
        # Gross profit = (101000 - 100000) * 1 = 1000
        # Buy fee = 100000 * 1 * 0.0002 = 20
        # Sell fee = 101000 * 1 * 0.0002 = 20.2
        # Net profit = 1000 - 20 - 20.2 = 959.8
        
        summary = self.sim.get_summary()
        
        assert summary['total_trades'] == 2
        assert summary['realized_pnl'] == pytest.approx(1000.0, abs=1)
        assert summary['total_fees'] == pytest.approx(40.2, abs=1)
        assert summary['net_pnl'] == pytest.approx(959.8, abs=1)
    
    def test_no_fill_when_price_doesnt_touch(self):
        """Test order doesn't fill when price doesn't touch limit."""
        # Place BUY at 100,000
        order = self.sim.create_order(side='buy', price=100000.0, amount=1.0)
        
        # Candle that doesn't touch (low = 100,100)
        self.sim.process_candle(
            datetime(2025, 10, 1, 12, 0),
            101000, 101500, 100100, 101000, 100  # low > buy price
        )
        
        # Order should still be open
        assert self.sim.orders[order['id']].status.value == 'open'
        
        # No position
        position = self.sim.get_position()
        assert position['contracts'] == 0
    
    def test_same_bar_priority_tp_first(self):
        """Test TP fills before new BUY when both can fill in same bar."""
        self.sim.same_bar_priority = 'tp_first'
        
        # Create position (BUY at 100000)
        self.sim.create_order(side='buy', price=100000.0, amount=1.0)
        self.sim.process_candle(
            datetime(2025, 10, 1, 12, 0),
            101000, 101000, 100000, 100500, 100
        )
        
        # Place TP at 101000 and new BUY at 99500
        self.sim.create_order(side='sell', price=101000.0, amount=1.0, reduce_only=True)
        self.sim.create_order(side='buy', price=99500.0, amount=1.0)
        
        # Candle that touches both (high=101000, low=99500)
        self.sim.process_candle(
            datetime(2025, 10, 1, 12, 5),
            100000, 101000, 99500, 100000, 200
        )
        
        # TP should fill first, then BUY
        trades = self.sim.get_trades_df()
        
        # Should have 3 trades total (initial BUY, TP, new BUY)
        assert len(trades) == 3
        
        # Second trade should be the TP (side='sell', reduce_only=True)
        assert trades.iloc[1]['side'] == 'sell'
        assert trades.iloc[1]['reduce_only'] == True
        
        # Third trade should be the new BUY
        assert trades.iloc[2]['side'] == 'buy'
        assert trades.iloc[2]['reduce_only'] == False
    
    def test_fee_calculation(self):
        """Test maker fee is calculated correctly."""
        # BUY 1 contract at 100,000
        order = self.sim.create_order(side='buy', price=100000.0, amount=1.0)
        self.sim.process_candle(
            datetime(2025, 10, 1, 12, 0),
            101000, 101000, 100000, 100500, 100
        )
        
        # Expected fee = 100000 * 1 * 0.0002 = 20
        filled_order = self.sim.orders[order['id']]
        assert filled_order.fee == pytest.approx(20.0, abs=0.01)
    
    def test_cancel_order(self):
        """Test order cancellation."""
        order = self.sim.create_order(side='buy', price=100000.0, amount=1.0)
        
        # Cancel it
        self.sim.cancel_order(order['id'])
        
        # Check status
        assert self.sim.orders[order['id']].status.value == 'canceled'
        
        # Process candle that would have filled it
        self.sim.process_candle(
            datetime(2025, 10, 1, 12, 0),
            101000, 101000, 100000, 100500, 100
        )
        
        # Should not fill (still canceled)
        assert self.sim.orders[order['id']].status.value == 'canceled'
        
        # No position
        position = self.sim.get_position()
        assert position['contracts'] == 0


def test_fee_model():
    """Test fee model calculation."""
    fee_model = FeeModel(maker_fee=0.0002, taker_fee=0.0005)
    
    # Maker fee
    maker_fee = fee_model.calculate_fee(price=100000, amount=1, is_maker=True)
    assert maker_fee == pytest.approx(20.0, abs=0.01)
    
    # Taker fee
    taker_fee = fee_model.calculate_fee(price=100000, amount=1, is_maker=False)
    assert taker_fee == pytest.approx(50.0, abs=0.01)


def test_funding_model():
    """Test funding model calculation."""
    funding_model = FundingModel(mode='simple', simple_rate=0.0001)
    
    # No funding initially
    funding = funding_model.calculate_funding(
        current_time=datetime(2025, 10, 1, 0, 0),
        position_size=1.0,
        mark_price=100000
    )
    assert funding == 0.0  # First call, no funding
    
    # After 8 hours, funding should apply
    funding = funding_model.calculate_funding(
        current_time=datetime(2025, 10, 1, 8, 0),
        position_size=1.0,
        mark_price=100000
    )
    # Expected: 100000 * 1 * -0.0001 = -10 (you pay)
    assert funding == pytest.approx(-10.0, abs=0.01)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

