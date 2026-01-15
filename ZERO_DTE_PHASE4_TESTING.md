# Phase 4: Testing & Deployment

**Duration:** 1 week  
**Deliverables:** Unit tests, integration tests, paper trading simulator, deployment checklist

---

## 📋 Phase 4 Overview

Comprehensive testing ensures the 0DTE bot operates reliably in production. This phase covers unit tests, integration tests, paper trading simulation, and deployment procedures.

**Testing Layers:**
1. Unit tests for core modules
2. Integration tests for API and database
3. Paper trading simulator
4. Backtesting framework
5. Deployment checklist

---

## Module 1: Unit Tests - Engine

### **File:** `tests/zero_dte/test_engine.py`

```python
"""
Unit tests for ZeroDTEEngine
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from bot.strategy.zero_dte.engine import ZeroDTEEngine
from bot.api.unified_api_client import UnifiedAPIClient


@pytest.fixture
def mock_api_client():
    client = Mock(spec=UnifiedAPIClient)
    client.get_option_chain = AsyncMock(return_value={
        'calls': {
            '95000': {'mark_price': 20.5, 'bid': 20.0, 'ask': 21.0},
            '93000': {'mark_price': 25.0, 'bid': 24.5, 'ask': 25.5}
        },
        'puts': {
            '91000': {'mark_price': 19.8, 'bid': 19.5, 'ask': 20.0},
            '89000': {'mark_price': 24.2, 'bid': 23.8, 'ask': 24.5}
        }
    })
    client.get_current_price = AsyncMock(return_value=93000.0)
    client.get_option_ticker = AsyncMock(return_value={
        'mark_price': 20.0,
        'quotes': {'best_bid': 19.5, 'best_ask': 20.5},
        'greeks': {'delta': 0.45, 'gamma': 0.002, 'theta': -15.5, 'vega': 8.2}
    })
    client.place_order = AsyncMock(return_value={'id': 'order123'})
    client.get_order = AsyncMock(return_value={
        'state': 'filled',
        'average_fill_price': 20.0
    })
    return client


@pytest.fixture
def engine(mock_api_client):
    return ZeroDTEEngine(mock_api_client)


class TestEngineInitialization:
    def test_engine_initialization(self, engine):
        """Test engine initializes correctly"""
        assert engine.api_client is not None
        assert engine.config is not None
        assert engine.state_manager is not None
        assert engine.balancer is not None
        assert engine.rollover_manager is not None
        assert engine.is_running is False
        assert engine.session_id is None


class TestStrikeSelection:
    @pytest.mark.asyncio
    async def test_select_strikes_balanced_premium(self, engine, mock_api_client):
        """Test strike selection with balanced premiums"""
        option_chain = await mock_api_client.get_option_chain('BTC', '2026-01-30')
        
        ce_strike, pe_strike = await engine._select_strikes('BTC', option_chain)
        
        assert ce_strike in [93000, 95000]
        assert pe_strike in [89000, 91000]
    
    @pytest.mark.asyncio
    async def test_find_nearest_strike(self, engine):
        """Test finding nearest strike"""
        strikes_data = {
            '90000': {},
            '91000': {},
            '92000': {},
            '93000': {}
        }
        
        nearest = engine._find_nearest_strike(strikes_data, 91500)
        assert nearest == 92000  # Closest to 91500


class TestPremiumValidation:
    def test_validate_premiums_within_range(self, engine):
        """Test premium validation passes for valid range"""
        result = engine._validate_premiums(20.0, 19.5)
        assert result is True
    
    def test_validate_premiums_outside_range(self, engine):
        """Test premium validation fails for out-of-range values"""
        result = engine._validate_premiums(5.0, 20.0)
        assert result is False
        
        result = engine._validate_premiums(20.0, 50.0)
        assert result is False


class TestOrderPlacement:
    @pytest.mark.asyncio
    async def test_place_sell_order_maker_first(self, engine, mock_api_client):
        """Test sell order with maker-first preference"""
        fill_price = await engine._place_sell_order('C-BTC-95000-30012026', 5)
        
        assert fill_price == 20.0
        assert mock_api_client.place_order.called
    
    @pytest.mark.asyncio
    async def test_place_buy_order(self, engine, mock_api_client):
        """Test buy order to close position"""
        fill_price = await engine._place_buy_order('C-BTC-95000-30012026', 5)
        
        assert fill_price == 20.0
        assert mock_api_client.place_order.called


class TestPnLCalculation:
    def test_calculate_session_pnl_profit(self, engine):
        """Test P&L calculation with profit"""
        session = {
            'entry_ce_premium': 20.0,
            'entry_pe_premium': 20.0,
            'entry_ce_lots': 5,
            'entry_pe_lots': 5
        }
        
        positions = {
            'CE': {'lots': 5},
            'PE': {'lots': 5}
        }
        
        pnl = engine._calculate_session_pnl(session, positions, 10.0, 10.0)
        
        # Entry: (20 + 20) * 5 = 200
        # Current: (10 + 10) * 5 = 100
        # P&L = 200 - 100 = 100
        assert pnl == 100.0
    
    def test_calculate_session_pnl_loss(self, engine):
        """Test P&L calculation with loss"""
        session = {
            'entry_ce_premium': 20.0,
            'entry_pe_premium': 20.0,
            'entry_ce_lots': 5,
            'entry_pe_lots': 5
        }
        
        positions = {
            'CE': {'lots': 5},
            'PE': {'lots': 5}
        }
        
        pnl = engine._calculate_session_pnl(session, positions, 30.0, 30.0)
        
        # Entry: 200
        # Current: 300
        # P&L = 200 - 300 = -100
        assert pnl == -100.0


class TestExitConditions:
    @pytest.mark.asyncio
    async def test_profit_target_exit(self, engine):
        """Test exit on profit target"""
        session = {'total_premium_collected': 200.0}
        positions = {'CE': {}, 'PE': {}}
        
        # Both premiums below threshold
        exit_reason = await engine._check_exit_conditions(
            session, positions, 3.0, 4.0, 100.0
        )
        
        assert exit_reason == 'profit_target'
    
    @pytest.mark.asyncio
    async def test_stop_loss_exit(self, engine):
        """Test exit on stop loss"""
        session = {'total_premium_collected': 200.0}
        positions = {'CE': {}, 'PE': {}}
        
        # Loss exceeds threshold
        exit_reason = await engine._check_exit_conditions(
            session, positions, 50.0, 50.0, -600.0
        )
        
        assert exit_reason == 'stop_loss'
```

---

## Module 2: Unit Tests - Balancer

### **File:** `tests/zero_dte/test_balancer.py`

```python
"""
Unit tests for PremiumBalancer
"""
import pytest
from unittest.mock import Mock, AsyncMock

from bot.strategy.zero_dte.balancer import PremiumBalancer


@pytest.fixture
def mock_api_client():
    client = Mock()
    client.get_option_ticker = AsyncMock(return_value={'mark_price': 15.0})
    client.place_order = AsyncMock(return_value={'id': 'order123'})
    client.get_order = AsyncMock(return_value={
        'state': 'filled',
        'average_fill_price': 15.0
    })
    return client


@pytest.fixture
def mock_config():
    config = Mock()
    config.rebalancing.adjustment.min_lot_adjustment = 1
    config.rebalancing.adjustment.max_lot_adjustment = 10
    config.rebalancing.orders.preference = 'maker_first'
    config.rebalancing.orders.timeout_seconds = 2
    return config


@pytest.fixture
def balancer(mock_api_client, mock_config):
    return PremiumBalancer(mock_api_client, mock_config)


class TestRebalancing:
    @pytest.mark.asyncio
    async def test_rebalance_ce_underexposed(self, balancer, mock_api_client):
        """Test rebalancing when CE is underexposed"""
        session_id = 'test_session'
        positions = {
            'CE': {'symbol': 'C-BTC-95000-30012026', 'lots': 5},
            'PE': {'symbol': 'P-BTC-91000-30012026', 'lots': 5}
        }
        
        # CE total: 5 * 10 = 50
        # PE total: 5 * 30 = 150
        # CE is underexposed, should buy back CE lots
        
        await balancer.execute_rebalance(
            session_id, positions,
            ce_premium=10.0, pe_premium=30.0,
            ce_total=50.0, pe_total=150.0
        )
        
        # Should have placed buy order to reduce CE short
        assert mock_api_client.place_order.called
    
    @pytest.mark.asyncio
    async def test_rebalance_pe_underexposed(self, balancer, mock_api_client):
        """Test rebalancing when PE is underexposed"""
        session_id = 'test_session'
        positions = {
            'CE': {'symbol': 'C-BTC-95000-30012026', 'lots': 5},
            'PE': {'symbol': 'P-BTC-91000-30012026', 'lots': 5}
        }
        
        # CE total: 5 * 30 = 150
        # PE total: 5 * 10 = 50
        # PE is underexposed, should buy back PE lots
        
        await balancer.execute_rebalance(
            session_id, positions,
            ce_premium=30.0, pe_premium=10.0,
            ce_total=150.0, pe_total=50.0
        )
        
        assert mock_api_client.place_order.called
```

---

## Module 3: Integration Tests

### **File:** `tests/zero_dte/test_integration.py`

```python
"""
Integration tests for 0DTE system
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from bot.strategy.zero_dte.engine import ZeroDTEEngine
from bot.strategy.zero_dte.state_manager import StateManager


@pytest.mark.integration
class TestFullSessionLifecycle:
    @pytest.mark.asyncio
    async def test_session_lifecycle(self, tmp_path):
        """Test complete session lifecycle: start -> monitor -> exit"""
        # Mock API client
        mock_client = Mock()
        mock_client.get_option_chain = AsyncMock(return_value={
            'calls': {'95000': {'mark_price': 20.0}},
            'puts': {'91000': {'mark_price': 19.5}}
        })
        mock_client.get_current_price = AsyncMock(return_value=93000.0)
        mock_client.get_option_ticker = AsyncMock(return_value={
            'mark_price': 20.0,
            'quotes': {'best_bid': 19.5, 'best_ask': 20.5},
            'greeks': {'delta': 0.45, 'gamma': 0.002, 'theta': -15.5, 'vega': 8.2}
        })
        mock_client.place_order = AsyncMock(return_value={'id': 'order123'})
        mock_client.get_order = AsyncMock(return_value={
            'state': 'filled',
            'average_fill_price': 20.0
        })
        
        # Initialize engine
        engine = ZeroDTEEngine(mock_client)
        
        # Start session
        with patch('bot.strategy.zero_dte.engine.check_liquidity', return_value={'is_liquid': True}):
            result = await engine.start_session('BTC', '2026-01-30', 5)
        
        assert result['session_id'] is not None
        assert engine.is_running is True
        
        # Stop session
        await engine.stop_session('manual')
        assert engine.is_running is False


@pytest.mark.integration
class TestDatabasePersistence:
    def test_state_persistence(self, tmp_path):
        """Test session state persists to database"""
        db_path = str(tmp_path / 'test_sessions.db')
        state_manager = StateManager(db_path)
        
        # Create session
        session_data = {
            'underlying': 'BTC',
            'expiry_date': '2026-01-30',
            'entry_ce_strike': 95000,
            'entry_pe_strike': 91000,
            'entry_ce_premium': 20.0,
            'entry_pe_premium': 19.5,
            'entry_ce_lots': 5,
            'entry_pe_lots': 5,
            'total_premium_collected': 197.5
        }
        
        session_id = state_manager.create_session(session_data)
        
        # Retrieve session
        retrieved = state_manager.get_session(session_id)
        assert retrieved is not None
        assert retrieved['underlying'] == 'BTC'
        assert retrieved['status'] == 'active'
        
        # Close session
        state_manager.close_session(session_id, 'profit_target', 150.0)
        
        # Verify closed
        closed_session = state_manager.get_session(session_id)
        assert closed_session['status'] == 'closed'
        assert closed_session['realized_pnl'] == 150.0
```

---

## Module 4: Paper Trading Simulator

### **File:** `tests/zero_dte/paper_trading_sim.py`

```python
"""
Paper trading simulator for 0DTE bot
Simulates real trading without actual orders
"""
import asyncio
import random
from datetime import datetime, timedelta
from loguru import logger


class PaperTradingSimulator:
    """Simulates 0DTE trading with fake market data"""
    
    def __init__(self, initial_spot=93000, volatility=0.02):
        self.spot_price = initial_spot
        self.volatility = volatility
        self.positions = {}
        self.pnl = 0.0
        self.trade_log = []
    
    def simulate_price_move(self, minutes_elapsed):
        """Simulate random price movement"""
        # Random walk with drift
        drift = random.uniform(-0.0001, 0.0001)
        shock = random.gauss(0, self.volatility) * (minutes_elapsed / 60) ** 0.5
        
        self.spot_price *= (1 + drift + shock)
        return self.spot_price
    
    def calculate_option_premium(self, strike, option_type, time_to_expiry_hours):
        """Simulate option premium using simplified Black-Scholes"""
        moneyness = abs(self.spot_price - strike) / self.spot_price
        time_value = time_to_expiry_hours / 24 * 20  # Simplified
        
        intrinsic = 0
        if option_type == 'call' and self.spot_price > strike:
            intrinsic = self.spot_price - strike
        elif option_type == 'put' and self.spot_price < strike:
            intrinsic = strike - self.spot_price
        
        premium = intrinsic + time_value * (1 - moneyness)
        return max(premium, 1.0)  # Minimum ₹1
    
    async def run_simulation(self, duration_hours=6):
        """
        Run full 0DTE simulation
        
        Args:
            duration_hours: Hours to simulate (default 6h for 10 AM - 4 PM)
        """
        logger.info(f"Starting paper trading simulation: {duration_hours}h")
        
        # Entry at start
        ce_strike = self.spot_price * 1.025
        pe_strike = self.spot_price * 0.975
        
        initial_ce_premium = self.calculate_option_premium(ce_strike, 'call', duration_hours)
        initial_pe_premium = self.calculate_option_premium(pe_strike, 'put', duration_hours)
        
        lots = 5
        
        self.positions = {
            'CE': {
                'strike': ce_strike,
                'lots': lots,
                'entry_premium': initial_ce_premium,
                'type': 'call'
            },
            'PE': {
                'strike': pe_strike,
                'lots': lots,
                'entry_premium': initial_pe_premium,
                'type': 'put'
            }
        }
        
        premium_collected = (initial_ce_premium + initial_pe_premium) * lots
        logger.info(f"Entry: CE {ce_strike:.0f} @ ₹{initial_ce_premium:.2f}, PE {pe_strike:.0f} @ ₹{initial_pe_premium:.2f}")
        logger.info(f"Total premium collected: ₹{premium_collected:.2f}")
        
        # Simulate minute-by-minute
        total_minutes = int(duration_hours * 60)
        
        for minute in range(1, total_minutes + 1):
            # Price movement
            new_spot = self.simulate_price_move(1)
            
            # Calculate time to expiry
            time_left_hours = (total_minutes - minute) / 60
            
            # Current premiums
            ce_premium = self.calculate_option_premium(
                self.positions['CE']['strike'], 'call', time_left_hours
            )
            pe_premium = self.calculate_option_premium(
                self.positions['PE']['strike'], 'put', time_left_hours
            )
            
            # Current P&L
            current_value = (ce_premium + pe_premium) * lots
            self.pnl = premium_collected - current_value
            
            # Log every 30 minutes
            if minute % 30 == 0:
                logger.info(
                    f"T+{minute}min: Spot=${new_spot:.0f}, "
                    f"CE=₹{ce_premium:.2f}, PE=₹{pe_premium:.2f}, "
                    f"P&L=₹{self.pnl:.2f}"
                )
            
            # Check exit conditions
            if ce_premium < 5 and pe_premium < 5:
                logger.success(f"✅ Exit at T+{minute}min: Both premiums <₹5")
                break
            
            await asyncio.sleep(0.01)  # Simulate time passing
        
        # Final P&L
        logger.success(f"Simulation complete! Final P&L: ₹{self.pnl:.2f}")
        
        return {
            'final_pnl': self.pnl,
            'duration_minutes': minute,
            'final_spot': self.spot_price
        }


# Run simulation
if __name__ == '__main__':
    sim = PaperTradingSimulator(initial_spot=93000, volatility=0.02)
    result = asyncio.run(sim.run_simulation(duration_hours=6))
    print(f"\n=== Simulation Results ===")
    print(f"Final P&L: ₹{result['final_pnl']:.2f}")
    print(f"Duration: {result['duration_minutes']} minutes")
    print(f"Final Spot: ${result['final_spot']:.0f}")
```

---

## Module 5: Deployment Checklist

### **File:** `ZERO_DTE_DEPLOYMENT_CHECKLIST.md`

```markdown
# 0DTE Bot Deployment Checklist

## Pre-Deployment

### Configuration
- [ ] Update `config/zero_dte_config.yaml` with production values
- [ ] Set correct Delta Exchange API endpoint (production)
- [ ] Configure Guardian integration if enabled
- [ ] Set appropriate risk limits (margin, Greeks)
- [ ] Configure alert channels (Telegram, email)

### Database
- [ ] Create production database files with proper permissions
- [ ] Test database connectivity
- [ ] Verify schema is up to date

### API Credentials
- [ ] Verify Delta Exchange API keys are valid
- [ ] Test API connectivity
- [ ] Confirm sufficient API rate limits

### Testing
- [ ] Run all unit tests: `pytest tests/zero_dte/`
- [ ] Run integration tests
- [ ] Complete paper trading simulation
- [ ] Test WebUI functionality

## Deployment Steps

### Backend
1. [ ] Copy 0DTE module to production server
2. [ ] Install dependencies: `pip install -r requirements.txt`
3. [ ] Register API blueprint in `webui/backend/app.py`
4. [ ] Restart backend service

### Frontend
1. [ ] Build React app: `cd webui/frontend && npm run build`
2. [ ] Deploy build artifacts
3. [ ] Verify WebUI loads correctly

### Database
1. [ ] Initialize databases
2. [ ] Set file permissions (644)
3. [ ] Configure backup schedule

### Monitoring
1. [ ] Set up log rotation
2. [ ] Configure monitoring dashboards
3. [ ] Test alert channels

## Post-Deployment

### Validation
- [ ] Access WebUI at `/zero-dte`
- [ ] Start test session with minimal capital
- [ ] Verify positions display correctly
- [ ] Test emergency stop button
- [ ] Confirm P&L calculations are accurate

### Monitoring
- [ ] Check logs for errors
- [ ] Monitor API rate limiting
- [ ] Verify Guardian integration
- [ ] Test alerts are received

## Rollback Plan

If issues occur:
1. Stop all active sessions via WebUI
2. Disable 0DTE API blueprint
3. Restart backend without 0DTE module
4. Investigate logs and fix issues
5. Redeploy after fixes

## Production Checklist

### Daily Operations
- [ ] Check Guardian signal before starting
- [ ] Monitor margin utilization
- [ ] Review rebalancing history
- [ ] Verify settlement timing

### Weekly Maintenance
- [ ] Review logs for errors
- [ ] Clean old monitoring snapshots
- [ ] Backup database files
- [ ] Update documentation

### Monthly Review
- [ ] Analyze P&L statistics
- [ ] Review rebalancing frequency
- [ ] Optimize configuration parameters
- [ ] Update risk limits if needed
```

---

**All phases complete!** Return to [ZERO_DTE_MASTER_PLAN.md](ZERO_DTE_MASTER_PLAN.md) for overview.
