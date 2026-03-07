# Options Strategy Builder Development Plan

**Project:** Options Strategy Automation (Straddle, Strangle, Iron Condor, etc.)  
**Date:** January 5, 2026  
**Goal:** Build automated strategy execution with position management  
**Feasibility:** ✅ **YES, HIGHLY DOABLE** - Extends existing automation framework  
**Risk Level:** MEDIUM (affects trading execution, needs robust testing)

---

## 🎯 Project Overview

Create a strategy builder that allows users to:
1. Select popular options strategies (Straddle, Strangle, Iron Condor, etc.)
2. Define entry conditions (price, IV, time)
3. Auto-execute multi-leg orders
4. Monitor and manage strategy positions
5. Auto-exit based on P&L or time

---

## 💡 Feasibility Assessment

### ✅ **YES, It's Possible Because:**

1. **Existing Infrastructure:**
   - ✅ Delta Exchange API integration (multi-leg orders supported)
   - ✅ Options automation framework (Phase 1-3 completed)
   - ✅ Order executor with retry logic
   - ✅ Risk validator
   - ✅ Real-time position monitoring

2. **Delta Exchange Capabilities:**
   - ✅ Supports bracket orders (multi-leg)
   - ✅ Atomic execution (all-or-nothing)
   - ✅ Greeks and IV data available
   - ✅ Mark prices for mid-market execution

3. **Technical Challenges (Solvable):**
   - ⚠️ Leg execution timing (use bracket orders)
   - ⚠️ Partial fills (handle with retry + cancel logic)
   - ⚠️ Slippage management (use limit orders with tolerance)
   - ⚠️ Position grouping (track strategy ID)

### Strategy Complexity Levels:

| Strategy | Legs | Complexity | Feasibility |
|----------|------|------------|-------------|
| **Straddle** | 2 (Call + Put, same strike) | LOW | ✅ Easy |
| **Strangle** | 2 (Call + Put, different strikes) | LOW | ✅ Easy |
| **Iron Condor** | 4 (2 Calls + 2 Puts) | MEDIUM | ✅ Doable |
| **Iron Butterfly** | 4 (Calls + Puts, shared strike) | MEDIUM | ✅ Doable |
| **Call/Put Spread** | 2 (Buy + Sell) | LOW | ✅ Easy |
| **Ratio Spread** | 2+ (Unequal quantities) | MEDIUM | ✅ Doable |
| **Calendar Spread** | 2 (Different expiries) | HIGH | ⚠️ Complex |

---

## 📂 File Structure

```
webui/
├── backend/
│   ├── options/                     # EXISTING
│   ├── options_chain/               # From Option_chain.md
│   │
│   └── options_strategy/            # NEW MODULE
│       ├── __init__.py
│       ├── strategy_routes.py       # API endpoints
│       ├── strategy_service.py      # Strategy execution engine
│       ├── strategy_manager.py      # Position grouping & tracking
│       ├── strategy_definitions.py  # Pre-built strategies
│       ├── leg_executor.py          # Multi-leg order execution
│       ├── strategy_monitor.py      # Active strategy monitoring
│       └── strategy_models.py       # Data models
│
└── frontend/src/
    └── components/
        ├── options/                 # EXISTING
        ├── optionsChain/            # From Option_chain.md
        │
        └── optionsStrategy/         # NEW MODULE
            ├── StrategyPanel.js         # Main container
            ├── StrategyBuilder.js       # Visual strategy builder
            ├── StrategySelector.js      # Pre-built strategy picker
            ├── StrategyConfigurator.js  # Entry/exit conditions
            ├── ActiveStrategies.js      # Monitor running strategies
            ├── StrategyPosition.js      # Single strategy display
            ├── LegVisualizer.js         # Payoff diagram
            └── services/
                ├── strategyAPI.js       # API client
                └── strategyPresets.js   # Pre-configured strategies
```

---

## 🚀 Phase-wise Development

### **PHASE 1: Strategy Definitions & Backend Foundation (8-10 hours)**

**Goal:** Define strategies and build execution engine

#### 1.1 Strategy Data Models (2 hours)
**File:** `strategy_models.py`

```python
Strategy Model:
{
    "id": "uuid",
    "name": "BTC Straddle 93K",
    "type": "straddle",  # straddle, strangle, iron_condor
    "underlying": "BTC",
    "status": "active",  # pending, active, closed, failed
    
    "legs": [
        {
            "leg_id": 1,
            "type": "call",
            "strike": 93000,
            "expiry": "30012026",
            "side": "buy",
            "quantity": 10,
            "symbol": "C-BTC-93000-30012026",
            "filled_qty": 10,
            "avg_fill_price": 234.50,
            "status": "filled"  # pending, filled, partial, failed
        },
        {
            "leg_id": 2,
            "type": "put",
            "strike": 93000,
            "expiry": "30012026",
            "side": "buy",
            "quantity": 10,
            "symbol": "P-BTC-93000-30012026",
            "filled_qty": 10,
            "avg_fill_price": 180.20,
            "status": "filled"
        }
    ],
    
    "entry_conditions": {
        "iv_threshold": 70,          # Enter when IV > 70%
        "time_window": "09:00-16:00",
        "max_cost": 5000,            # USD
        "spot_range": [92000, 94000]
    },
    
    "exit_conditions": {
        "profit_target": 30,         # % profit
        "stop_loss": -50,            # % loss
        "time_decay": 0.5,           # Exit when theta decay > 50%
        "dte_exit": 3                # Exit 3 days before expiry
    },
    
    "total_cost": 4147.00,           # Total premium paid
    "current_value": 5200.00,        # Current market value
    "pnl": 1053.00,                  # Unrealized P&L
    "pnl_pct": 25.4,
    
    "created_at": "2026-01-05T10:30:00Z",
    "executed_at": "2026-01-05T10:31:23Z",
    "closed_at": null
}
```

#### 1.2 Strategy Definitions (2 hours)
**File:** `strategy_definitions.py`

```python
class StrategyDefinitions:
    
    @staticmethod
    def straddle(strike, expiry, quantity):
        """
        Long Straddle: Buy ATM Call + ATM Put
        Max Profit: Unlimited
        Max Loss: Total premium paid
        Breakeven: Strike ± Total premium
        """
        return {
            "legs": [
                {"type": "call", "strike": strike, "side": "buy", "qty": quantity},
                {"type": "put", "strike": strike, "side": "buy", "qty": quantity}
            ],
            "max_risk": "limited",
            "max_profit": "unlimited",
            "direction": "neutral"
        }
    
    @staticmethod
    def strangle(call_strike, put_strike, expiry, quantity):
        """
        Long Strangle: Buy OTM Call + OTM Put
        Cheaper than straddle, needs bigger move
        """
        return {
            "legs": [
                {"type": "call", "strike": call_strike, "side": "buy", "qty": quantity},
                {"type": "put", "strike": put_strike, "side": "buy", "qty": quantity}
            ],
            "max_risk": "limited",
            "max_profit": "unlimited",
            "direction": "neutral"
        }
    
    @staticmethod
    def iron_condor(call_buy_strike, call_sell_strike, 
                    put_buy_strike, put_sell_strike, expiry, quantity):
        """
        Iron Condor: Sell OTM Call Spread + Sell OTM Put Spread
        Credit strategy, profits from low volatility
        """
        return {
            "legs": [
                {"type": "call", "strike": call_sell_strike, "side": "sell", "qty": quantity},
                {"type": "call", "strike": call_buy_strike, "side": "buy", "qty": quantity},
                {"type": "put", "strike": put_sell_strike, "side": "sell", "qty": quantity},
                {"type": "put", "strike": put_buy_strike, "side": "buy", "qty": quantity}
            ],
            "max_risk": "limited",
            "max_profit": "limited",
            "direction": "neutral"
        }
    
    @staticmethod
    def call_spread(buy_strike, sell_strike, expiry, quantity):
        """
        Bull Call Spread: Buy lower strike Call + Sell higher strike Call
        Limited profit, limited loss
        """
        # Similar pattern...
    
    @staticmethod
    def put_spread(buy_strike, sell_strike, expiry, quantity):
        """
        Bear Put Spread: Buy higher strike Put + Sell lower strike Put
        """
        # Similar pattern...
```

#### 1.3 Leg Executor (3 hours)
**File:** `leg_executor.py`

```python
class LegExecutor:
    """
    Execute multi-leg orders with smart order handling
    """
    
    def execute_strategy(self, strategy_def):
        """
        Execution modes:
        1. ATOMIC: All legs at once (bracket order) - PREFERRED
        2. SEQUENTIAL: One leg at a time with retry
        3. MARKET: Fast execution, higher slippage
        4. LIMIT: Better prices, risk of partial fills
        """
        
        # Phase 1: Validate all legs
        for leg in strategy_def['legs']:
            validate_symbol_exists(leg['symbol'])
            validate_liquidity(leg['symbol'], leg['quantity'])
        
        # Phase 2: Calculate mid-prices for limit orders
        leg_prices = self._get_mid_prices(strategy_def['legs'])
        
        # Phase 3: Submit bracket order (Delta Exchange)
        bracket_order = {
            "legs": [
                {
                    "symbol": leg['symbol'],
                    "side": leg['side'],
                    "quantity": leg['quantity'],
                    "order_type": "limit",
                    "price": leg_prices[leg['symbol']]
                }
                for leg in strategy_def['legs']
            ],
            "bracket_stop_loss_price": None,  # Optional
            "bracket_take_profit_price": None
        }
        
        response = delta_api.place_bracket_order(bracket_order)
        
        # Phase 4: Monitor fills
        return self._monitor_fills(response['order_id'])
    
    def _handle_partial_fills(self, order_id, strategy_id):
        """
        If partial fills occur:
        1. Wait 30 seconds
        2. Cancel unfilled legs
        3. Close filled legs (rollback)
        4. Mark strategy as failed
        """
        pass
```

#### 1.4 Strategy Manager (2 hours)
**File:** `strategy_manager.py`

```python
class StrategyManager:
    """
    Track and manage active strategies
    """
    
    def create_strategy(self, strategy_type, params):
        """
        Create strategy from preset or custom config
        """
        strategy_def = StrategyDefinitions.get(strategy_type, params)
        strategy_id = self._generate_id()
        
        # Store in database
        self.db.save_strategy(strategy_id, strategy_def)
        
        return strategy_id
    
    def execute_strategy(self, strategy_id):
        """
        Execute strategy legs
        """
        strategy = self.db.get_strategy(strategy_id)
        
        result = LegExecutor().execute_strategy(strategy)
        
        # Update status
        strategy['status'] = 'active' if result.success else 'failed'
        strategy['executed_at'] = datetime.now()
        
        self.db.update_strategy(strategy_id, strategy)
        
        return result
    
    def get_active_strategies(self):
        """
        Get all active strategies with current P&L
        """
        strategies = self.db.get_strategies(status='active')
        
        for strategy in strategies:
            strategy['current_value'] = self._calculate_current_value(strategy)
            strategy['pnl'] = strategy['current_value'] - strategy['total_cost']
        
        return strategies
    
    def close_strategy(self, strategy_id, reason='manual'):
        """
        Close all legs of a strategy
        """
        strategy = self.db.get_strategy(strategy_id)
        
        # Close each leg (reverse positions)
        for leg in strategy['legs']:
            reverse_side = 'sell' if leg['side'] == 'buy' else 'buy'
            self.close_leg(leg['symbol'], reverse_side, leg['filled_qty'])
        
        strategy['status'] = 'closed'
        strategy['closed_at'] = datetime.now()
        strategy['close_reason'] = reason
        
        self.db.update_strategy(strategy_id, strategy)
```

#### 1.5 API Routes (1 hour)
**File:** `strategy_routes.py`

```python
Endpoints:

POST /api/options-strategy/create
    Body: { type: "straddle", params: {...} }
    Response: { strategy_id: "uuid" }

POST /api/options-strategy/execute/{strategy_id}
    Execute pending strategy

GET /api/options-strategy/active
    Get all active strategies with P&L

GET /api/options-strategy/{strategy_id}
    Get strategy details

POST /api/options-strategy/close/{strategy_id}
    Close strategy positions

POST /api/options-strategy/presets
    Get available strategy presets

POST /api/options-strategy/calculate
    Calculate strategy payoff/Greeks without executing
```

**Phase 1 Deliverables:**
- ✅ Strategy models defined
- ✅ Pre-built strategies (straddle, strangle, iron condor)
- ✅ Multi-leg execution engine
- ✅ Strategy tracking and management
- ✅ API endpoints
- ✅ Backend fully tested

---

### **PHASE 2: Frontend Strategy Builder (10-12 hours)**

**Goal:** Visual strategy builder with configuration UI

#### 2.1 Strategy Selector (2 hours)
**File:** `StrategySelector.js`

```javascript
UI Layout:
┌──────────────────────────────────────────────────────┐
│  Popular Strategies                                   │
├──────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Straddle   │  │  Strangle   │  │ Iron Condor │  │
│  │  ━━━━━━━━   │  │  ━  ━  ━    │  │ ━┬━  ━┬━    │  │
│  │   Neutral   │  │   Neutral    │  │   Neutral   │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ Call Spread │  │ Put Spread  │  │ Butterfly   │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
└──────────────────────────────────────────────────────┘

Features:
- Click strategy card → Open configurator
- Show payoff diagram preview
- Display risk/reward profile
- Complexity indicator (Beginner/Intermediate/Advanced)
```

#### 2.2 Strategy Configurator (4 hours)
**File:** `StrategyConfigurator.js`

```javascript
Example: Straddle Configurator

┌──────────────────────────────────────────────────────┐
│  Configure: Long Straddle                             │
├──────────────────────────────────────────────────────┤
│  Underlying: [BTC ▼]                                 │
│  Expiry: [30 Jan 2026 ▼]                            │
│  Strike: [93000] (ATM: $93,113)                     │
│  Quantity: [10]                                      │
│                                                       │
│  Entry Conditions (Optional):                        │
│  ☑ IV Threshold: [70]%                              │
│  ☐ Spot Price Range: [92000] to [94000]            │
│  ☐ Time Window: [09:00] to [16:00]                 │
│                                                       │
│  Exit Conditions:                                     │
│  ☑ Profit Target: [30]%                             │
│  ☑ Stop Loss: [-50]%                                │
│  ☑ Days Before Expiry: [3] days                     │
│                                                       │
│  Estimated Cost: $4,147.00                           │
│  Max Profit: Unlimited                               │
│  Max Loss: $4,147.00 (premium paid)                 │
│  Breakeven: $88,853 / $97,147                       │
│                                                       │
│  [Calculate Payoff]  [Preview]  [Execute Strategy]   │
└──────────────────────────────────────────────────────┘

Dynamic Features:
- Real-time cost calculation
- Strike selector with ATM indicator
- Greeks display (delta, gamma, vega, theta)
- Payoff diagram preview
- Risk warning messages
```

#### 2.3 Payoff Diagram Visualizer (2 hours)
**File:** `LegVisualizer.js`

```javascript
Payoff Graph (Recharts):

     P&L ($)
       ↑
  2000 │        ╱────╲
       │       ╱      ╲
  1000 │      ╱        ╲
       │     ╱          ╲
     0 ├────•────────────•────→ Spot Price
       │   85K          95K
 -1000 │
       │
 -2000 │  Max Loss: -$4,147
       │
       
Features:
- Interactive: Hover to see P&L at price points
- Show breakeven points
- Color coding: Green (profit), Red (loss)
- Animate entry → expiry
- Compare multiple strategies
```

#### 2.4 Active Strategies Monitor (3 hours)
**File:** `ActiveStrategies.js`

```javascript
Active Strategies Table:

┌────────────────────────────────────────────────────────────────────────┐
│  Strategy    │ Type      │ Cost   │ Value  │ P&L      │ Status │ Actions│
├────────────────────────────────────────────────────────────────────────┤
│ BTC Straddle │ Straddle  │ $4,147 │ $5,200 │ +$1,053  │ Active │ Close  │
│ 93K          │           │        │        │ +25.4%   │        │ Edit   │
│ 30 Jan 2026  │           │        │        │          │        │        │
├────────────────────────────────────────────────────────────────────────┤
│ ETH Strangle │ Strangle  │ $1,230 │ $1,450 │ +$220    │ Active │ Close  │
│ 3500/3800    │           │        │        │ +17.9%   │        │ Edit   │
│ 09 Jan 2026  │           │        │        │          │        │        │
└────────────────────────────────────────────────────────────────────────┘

Click to Expand:
┌────────────────────────────────────────────────────────────────────────┐
│ BTC Straddle 93K - Details                                             │
├────────────────────────────────────────────────────────────────────────┤
│ Legs:                                                                   │
│   1. Buy 10 Call @93000  - Entry: $234.50  Current: $280.00 (+19.4%)  │
│   2. Buy 10 Put @93000   - Entry: $180.20  Current: $240.00 (+33.2%)  │
│                                                                         │
│ Greeks:                                                                 │
│   Delta: -0.05  │ Gamma: 0.12  │ Vega: 45.3  │ Theta: -12.5          │
│                                                                         │
│ Exit Conditions:                                                        │
│   ✅ Profit: 25.4% / 30% target                                        │
│   ✅ Loss: -0% / -50% stop                                             │
│   📅 DTE: 25 days (exit at 3 days)                                     │
│                                                                         │
│ [Close Strategy] [Modify Exit] [View Payoff]                           │
└────────────────────────────────────────────────────────────────────────┘
```

#### 2.5 Strategy API Integration (1 hour)
**File:** `services/strategyAPI.js`

```javascript
class StrategyAPI {
    async createStrategy(type, config) {
        return axios.post('/api/options-strategy/create', { type, params: config });
    }
    
    async executeStrategy(strategyId) {
        return axios.post(`/api/options-strategy/execute/${strategyId}`);
    }
    
    async getActiveStrategies() {
        return axios.get('/api/options-strategy/active');
    }
    
    async closeStrategy(strategyId, reason = 'manual') {
        return axios.post(`/api/options-strategy/close/${strategyId}`, { reason });
    }
    
    async calculatePayoff(strategy) {
        return axios.post('/api/options-strategy/calculate', strategy);
    }
}
```

**Phase 2 Deliverables:**
- ✅ Strategy selector with presets
- ✅ Interactive configurator
- ✅ Payoff diagram visualizer
- ✅ Active strategies monitor
- ✅ Full integration with backend

---

### **PHASE 3: Automation & Monitoring (6-8 hours)**

**Goal:** Auto-execute strategies based on conditions, monitor and auto-exit

#### 3.1 Strategy Monitor Service (3 hours)
**File:** `strategy_monitor.py`

```python
class StrategyMonitor:
    """
    Background service: Check active strategies every 10 seconds
    """
    
    def monitor_strategies(self):
        while True:
            active_strategies = self.strategy_manager.get_active_strategies()
            
            for strategy in active_strategies:
                # Check exit conditions
                if self._should_exit(strategy):
                    self.strategy_manager.close_strategy(
                        strategy['id'], 
                        reason=self._exit_reason(strategy)
                    )
                    self._notify_user(strategy, 'closed')
            
            time.sleep(10)
    
    def _should_exit(self, strategy):
        """
        Check all exit conditions:
        - Profit target reached
        - Stop loss hit
        - Time decay threshold
        - Days to expiry
        """
        current_pnl_pct = strategy['pnl_pct']
        
        # Profit target
        if current_pnl_pct >= strategy['exit_conditions']['profit_target']:
            return True
        
        # Stop loss
        if current_pnl_pct <= strategy['exit_conditions']['stop_loss']:
            return True
        
        # Days to expiry
        dte = self._calculate_dte(strategy['legs'][0]['expiry'])
        if dte <= strategy['exit_conditions']['dte_exit']:
            return True
        
        return False
```

#### 3.2 Auto-Entry Logic (2 hours)
```python
class StrategyAutoEntry:
    """
    Monitor pending strategies and auto-execute when conditions met
    """
    
    def check_entry_conditions(self, strategy):
        """
        Check:
        - IV threshold
        - Spot price range
        - Time window
        - Max cost
        """
        if not self._within_time_window(strategy):
            return False
        
        if not self._iv_threshold_met(strategy):
            return False
        
        if not self._spot_in_range(strategy):
            return False
        
        # All conditions met - execute
        return True
```

#### 3.3 Risk Management (2 hours)
```python
class StrategyRiskValidator:
    """
    Pre-execution risk checks
    """
    
    def validate_strategy(self, strategy):
        """
        Risk checks:
        - Max position size
        - Portfolio concentration
        - Available capital
        - Correlation with existing positions
        """
        
        # Check capital
        if strategy['total_cost'] > self._get_available_capital():
            raise InsufficientCapitalError()
        
        # Check position limits
        if self._count_active_strategies() >= MAX_STRATEGIES:
            raise StrategyLimitError()
        
        # Check concentration
        if self._strategy_concentration(strategy) > 0.3:  # 30% max per strategy
            raise ConcentrationError()
```

#### 3.4 Alerts & Notifications (1 hour)
```python
Notification Events:
- Strategy executed
- Leg filled/partial fill
- Exit condition triggered
- Strategy closed
- Profit target reached
- Stop loss hit
- Days to expiry warning
```

**Phase 3 Deliverables:**
- ✅ Background monitoring service
- ✅ Auto-entry based on conditions
- ✅ Auto-exit based on rules
- ✅ Risk management integration
- ✅ Real-time notifications

---

### **PHASE 4: Advanced Features (OPTIONAL, 8-10 hours)**

#### 4.1 Strategy Templates & Presets
- [ ] Save custom strategy configurations
- [ ] Share strategies with other users
- [ ] Import/export strategies (JSON)
- [ ] Strategy performance tracking

#### 4.2 Advanced Strategy Types
- [ ] Calendar spreads (different expiries)
- [ ] Diagonal spreads (different strikes + expiries)
- [ ] Ratio spreads (unequal quantities)
- [ ] Custom multi-leg strategies (5+ legs)

#### 4.3 Greeks-Based Management
- [ ] Delta-neutral rebalancing
- [ ] Vega hedging
- [ ] Theta decay optimization
- [ ] Gamma scalping

#### 4.4 Analytics & Backtesting
- [ ] Historical strategy performance
- [ ] Win rate, avg profit, max drawdown
- [ ] Backtest strategy on historical data
- [ ] Monte Carlo simulations

---

## 🧪 Testing Strategy

### Backend Testing
```bash
# Test straddle creation
curl -X POST http://localhost:5555/api/options-strategy/create \
  -d '{"type": "straddle", "params": {"strike": 93000, "expiry": "30012026", "qty": 10}}'

# Test execution
curl -X POST http://localhost:5555/api/options-strategy/execute/{strategy_id}

# Test active strategies
curl http://localhost:5555/api/options-strategy/active

# Test close
curl -X POST http://localhost:5555/api/options-strategy/close/{strategy_id}
```

### Frontend Testing
- [ ] Create straddle with valid parameters
- [ ] Test payoff diagram calculations
- [ ] Monitor active strategies (auto-refresh)
- [ ] Close strategy and verify all legs closed
- [ ] Test partial fills handling
- [ ] Test exit conditions triggering
- [ ] Test with multiple strategies simultaneously

### Integration Testing
- [ ] Full workflow: Create → Execute → Monitor → Exit
- [ ] Test with real Delta Exchange testnet
- [ ] Simulate price movements and verify auto-exit
- [ ] Test error cases (insufficient capital, API failures)

---

## 🔧 Technical Requirements

### Delta Exchange API Support
```python
# Check if Delta Exchange supports bracket orders
Required APIs:
- POST /orders/bracket
- GET /orders/{order_id}
- POST /orders/{order_id}/cancel
- GET /positions

# If bracket orders not supported, use sequential execution with rollback
```

### Frontend Dependencies
```javascript
// Already available
@mui/material
recharts  // For payoff diagrams

// May need
react-flow  // For visual strategy builder (optional)
```

---

## 📊 Strategy Data Storage

### Database Schema (SQLite/PostgreSQL)
```sql
CREATE TABLE strategies (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255),
    type VARCHAR(50),
    underlying VARCHAR(10),
    status VARCHAR(20),
    total_cost DECIMAL(10, 2),
    current_value DECIMAL(10, 2),
    pnl DECIMAL(10, 2),
    pnl_pct DECIMAL(5, 2),
    entry_conditions JSON,
    exit_conditions JSON,
    created_at TIMESTAMP,
    executed_at TIMESTAMP,
    closed_at TIMESTAMP,
    close_reason VARCHAR(100)
);

CREATE TABLE strategy_legs (
    id VARCHAR(36) PRIMARY KEY,
    strategy_id VARCHAR(36) REFERENCES strategies(id),
    leg_id INT,
    type VARCHAR(10),  -- call/put
    strike DECIMAL(10, 2),
    expiry VARCHAR(8),
    side VARCHAR(4),  -- buy/sell
    quantity INT,
    symbol VARCHAR(50),
    filled_qty INT,
    avg_fill_price DECIMAL(10, 4),
    status VARCHAR(20),
    order_id VARCHAR(50)
);
```

---

## 🚦 Feature Flags & Rollout

```python
# backend/config.py
FEATURE_FLAGS = {
    'options_strategy': os.getenv('ENABLE_OPTIONS_STRATEGY', 'false') == 'true',
    'strategy_auto_entry': os.getenv('ENABLE_STRATEGY_AUTO_ENTRY', 'false') == 'true',
    'advanced_strategies': os.getenv('ENABLE_ADVANCED_STRATEGIES', 'false') == 'true'
}
```

**Rollout Plan:**
1. Deploy Phase 1 (backend) with flag OFF
2. Test on testnet with manual strategies
3. Deploy Phase 2 (frontend) for internal testing
4. Enable Phase 3 (automation) after 1 week of manual testing
5. Production rollout with conservative limits

---

## ⚠️ Risk Considerations

### High-Risk Areas
1. **Multi-leg execution failures** → Partial fills leave hedges incomplete
2. **Slippage on large orders** → Cost exceeds estimates
3. **Liquidity issues** → Can't close positions when needed
4. **Greeks calculations** → Incorrect risk assessment

### Mitigation Strategies
1. Use bracket orders (atomic execution)
2. Start with small quantities (max 10 contracts per leg)
3. Liquidity checks before execution
4. Multiple data sources for Greeks validation
5. Manual approval mode first, then auto-execution

---

## 📈 Success Criteria

**Phase 1 (Backend):**
- [ ] Successfully execute straddle with 2 legs
- [ ] Track strategy P&L correctly
- [ ] Close strategy (reverse all legs)

**Phase 2 (Frontend):**
- [ ] Create strategy via UI
- [ ] View active strategies with live P&L
- [ ] Close strategy with one click
- [ ] Payoff diagram displays correctly

**Phase 3 (Automation):**
- [ ] Auto-entry when conditions met
- [ ] Auto-exit on profit target
- [ ] Auto-exit on stop loss
- [ ] Notifications sent correctly

---

## 🎯 Strategy Builder Roadmap

### Week 1: Foundation
- [ ] Phase 1 implementation (backend)
- [ ] Test straddle & strangle execution

### Week 2: UI
- [ ] Phase 2 implementation (frontend)
- [ ] Manual strategy execution only

### Week 3: Automation
- [ ] Phase 3 implementation (monitoring)
- [ ] Conservative limits (max 3 strategies, $5K per strategy)

### Week 4: Testing & Refinement
- [ ] Full integration testing
- [ ] Performance optimization
- [ ] User acceptance testing

### Week 5+: Advanced Features
- [ ] Iron Condor, Butterfly
- [ ] Calendar spreads
- [ ] Analytics & reporting

---

## 🔗 Integration with Other Modules

### Options Chain Integration
- Use chain data to select strikes
- Show live bid/ask when configuring
- Visual strike picker from chain

### Existing Automation Integration
- Reuse ConditionEvaluator for entry rules
- Reuse OrderExecutor (extend for multi-leg)
- Reuse NotificationService

### Risk Management
- Integrate with existing risk validator
- Portfolio-level risk checks
- Capital allocation limits

---

## 📝 API Documentation

### Strategy API Endpoints

```http
POST /api/options-strategy/create
{
  "type": "straddle",
  "params": {
    "underlying": "BTC",
    "strike": 93000,
    "expiry": "30012026",
    "quantity": 10,
    "entry_conditions": {...},
    "exit_conditions": {...}
  }
}

Response: 201 Created
{
  "strategy_id": "uuid",
  "status": "pending",
  "estimated_cost": 4147.00,
  "legs": [...]
}

POST /api/options-strategy/execute/{strategy_id}
Response: 200 OK
{
  "status": "active",
  "executed_at": "2026-01-05T10:31:23Z",
  "legs": [
    {
      "leg_id": 1,
      "status": "filled",
      "avg_fill_price": 234.50
    },
    ...
  ]
}

GET /api/options-strategy/active
Response: 200 OK
[
  {
    "id": "uuid",
    "name": "BTC Straddle 93K",
    "current_value": 5200.00,
    "pnl": 1053.00,
    "pnl_pct": 25.4
  },
  ...
]
```

---

## 💡 Key Insights & Recommendations

### ✅ What Makes This Feasible:

1. **Existing Infrastructure** - 80% of code reusable
2. **Delta Exchange Support** - Multi-leg orders available
3. **Proven Patterns** - Similar to existing automation
4. **Isolated Module** - Low risk to production

### ⚠️ What to Watch Out For:

1. **Execution Risk** - Partial fills need robust handling
2. **Liquidity** - Start with liquid strikes (ATM ±5%)
3. **Capital Efficiency** - Strategies can be capital intensive
4. **Complexity** - Iron Condor has 4 legs (harder to manage)

### 🎯 Recommended Approach:

**Start Simple:**
1. Build straddle first (2 legs, easiest)
2. Test thoroughly with small sizes
3. Add strangle (still 2 legs)
4. Then tackle iron condor (4 legs)

**Build Confidence:**
- Manual execution for 2 weeks
- Auto-entry after proven reliable
- Auto-exit after entry working
- Advanced strategies last

---

## 📊 Expected Outcomes

### User Benefits:
- ✅ One-click strategy execution
- ✅ Automated position management
- ✅ Visual payoff diagrams
- ✅ Risk-defined strategies
- ✅ No need to leg in manually

### System Benefits:
- ✅ Grouped position tracking
- ✅ Strategy-level P&L
- ✅ Automated risk management
- ✅ Historical performance data

---

## 🚀 Next Steps

1. **Review & Approve** - Confirm approach
2. **Phase 1 Implementation** - Backend (8-10 hours)
3. **Testing** - Testnet validation
4. **Phase 2 Implementation** - Frontend (10-12 hours)
5. **Integration Testing** - End-to-end
6. **Phase 3 Implementation** - Automation (6-8 hours)
7. **Production Rollout** - Phased with limits

---

**Total Estimated Time:**  
- **Basic (Phases 1-2):** 18-22 hours (Straddle/Strangle only)
- **Full (Phases 1-3):** 24-30 hours (With automation)
- **Advanced (Phase 4):** +8-10 hours (Iron Condor, analytics)

**Feasibility:** ✅ **HIGHLY DOABLE**  
**Complexity:** MEDIUM-HIGH  
**Risk:** MEDIUM (requires careful testing)  
**Value:** ⭐⭐⭐⭐⭐ (Very high user value)

---

**Ready to build when you are! 🚀**
