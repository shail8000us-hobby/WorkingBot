"""
Unit Tests — SimBroker
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from unittest.mock import MagicMock

from backtesting.engine.sim_broker import SimBroker, FillRecord, OrderRejectedError


@pytest.fixture
def mock_chain():
    chain = MagicMock()
    chain.get_bid.return_value       = 100.0
    chain.get_ask.return_value       = 102.0
    chain.get_premium.return_value   = 101.0
    chain.get_oi.return_value        = 500.0
    chain.get_symbol.return_value    = "C-BTC-95000-260310"
    return chain


@pytest.fixture
def broker():
    return SimBroker(slippage_bps=10, min_oi_lots=50)


def test_sell_option_basic(broker, mock_chain):
    fill = broker.sell_option(mock_chain, 95000, "CE", 10, 1_000_000)
    assert fill.side == "sell"
    assert fill.lots == 10
    assert fill.fill_price < 100.0     # bid - slippage
    assert fill.fee > 0


def test_buy_option_basic(broker, mock_chain):
    fill = broker.buy_option(mock_chain, 95000, "CE", 10, 1_000_000)
    assert fill.side == "buy"
    assert fill.fill_price > 102.0     # ask + slippage


def test_sell_rejected_low_oi(mock_chain):
    broker = SimBroker(slippage_bps=2, min_oi_lots=1000)
    mock_chain.get_oi.return_value = 10  # Below min_oi
    with pytest.raises(OrderRejectedError):
        broker.sell_option(mock_chain, 95000, "CE", 10, 1_000_000)


def test_net_cash_flow_sell_is_positive(broker, mock_chain):
    fill = broker.sell_option(mock_chain, 95000, "CE", 10, 1_000_000)
    # Selling an option should generate positive cash flow (premium received - fee)
    assert fill.net_cash_flow > 0


def test_net_cash_flow_buy_is_negative(broker, mock_chain):
    fill = broker.buy_option(mock_chain, 95000, "CE", 10, 1_000_000)
    # Buying (closing a short) costs money
    assert fill.net_cash_flow < 0


def test_market_close_higher_price(broker, mock_chain):
    normal_fill  = broker.buy_option(mock_chain, 95000, "CE", 5, 1_000_000, market_close=False)
    market_fill  = broker.buy_option(mock_chain, 95000, "CE", 5, 1_000_000, market_close=True)
    assert market_fill.fill_price > normal_fill.fill_price


def test_fills_accumulate(broker, mock_chain):
    broker.sell_option(mock_chain, 95000, "CE", 5, 1_000_000)
    broker.sell_option(mock_chain, 93000, "PE", 5, 1_000_000)
    assert len(broker.fills) == 2


def test_total_fees_nonzero(broker, mock_chain):
    broker.sell_option(mock_chain, 95000, "CE", 10, 1_000_000)
    assert broker.total_fees_usd > 0


def test_fills_as_df(broker, mock_chain):
    broker.sell_option(mock_chain, 95000, "CE", 10, 1_000_000)
    df = broker.fills_as_df()
    assert len(df) == 1
    assert "fill_price" in df.columns
    assert "net_cash_flow" in df.columns


def test_reset_clears_fills(broker, mock_chain):
    broker.sell_option(mock_chain, 95000, "CE", 10, 1_000_000)
    broker.reset()
    assert len(broker.fills) == 0
    assert broker.total_fees_usd == 0
