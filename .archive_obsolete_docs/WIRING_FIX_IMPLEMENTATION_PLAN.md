# Grid Config Wiring - Implementation Plan

## Priority 1: Safety Features (CRITICAL)

### 1.1 Add Safety Parameters to AsyncGridBot

**File**: `bot/strategy/async_gridbot.py`

**Changes Needed**:
```python
def __init__(
    self,
    api_key: str,
    api_secret: str,
    symbol: str = "BTCUSD",
    product_id: int = 27,
    mode: str = "LONG",
    lower_price: float = 99000,
    upper_price: float = 112000,
    grid_step: float = 500,
    tp_offset: float = 500,
    max_positions: int = 5,
    testnet: bool = False,
    # NEW: Safety parameters
    max_account_loss_inr: float = 25000,
    volatility_safety_enabled: bool = True,
    volatility_max_iv: float = 50,
    volatility_max_rv: float = 55,
    confirmation_guard_enabled: bool = True,
    circuit_breaker_enabled: bool = True,
    liquidation_protection_enabled: bool = True
):
```

**Store as instance variables**:
```python
# Safety limits
self.max_account_loss_inr = max_account_loss_inr
self.volatility_safety_enabled = volatility_safety_enabled
self.volatility_max_iv = volatility_max_iv
self.volatility_max_rv = volatility_max_rv
self.confirmation_guard_enabled = confirmation_guard_enabled
self.circuit_breaker_enabled = circuit_breaker_enabled
self.liquidation_protection_enabled = liquidation_protection_enabled

# Safety state
self._account_loss_inr = 0.0
self._safety_halt = False
self._halt_reason = None
```

### 1.2 Wire Safety Parameters from bot/run.py

**File**: `bot/run.py` (lines 520-550)

**Add parameter extraction**:
```python
# Extract safety parameters
max_loss = envf("MAX_ACCOUNT_LOSS_INR", 25000)
vol_safety = os.getenv("VOLATILITY_SAFETY_ENABLED", "true").lower() == "true"
vol_max_iv = envf("VOLATILITY_MAX_IV", 50)
vol_max_rv = envf("VOLATILITY_MAX_RV", 55)
confirmation_guard = os.getenv("CONFIRMATION_GUARD_ENABLED", "true").lower() == "true"
circuit_breaker = os.getenv("CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"
liq_protection = os.getenv("LIQUIDATION_PROTECTION_ENABLED", "true").lower() == "true"
```

**Pass to AsyncGridBot**:
```python
async_bot = AsyncGridBot(
    api_key=api_key,
    api_secret=api_secret,
    symbol=symbol.replace("/", "").replace(":USD", ""),
    product_id=product_id,
    mode=mode,
    lower_price=lower,
    upper_price=upper,
    grid_step=step,
    tp_offset=step,
    max_positions=max_open,
    testnet=testnet,
    # Safety parameters
    max_account_loss_inr=max_loss,
    volatility_safety_enabled=vol_safety,
    volatility_max_iv=vol_max_iv,
    volatility_max_rv=vol_max_rv,
    confirmation_guard_enabled=confirmation_guard,
    circuit_breaker_enabled=circuit_breaker,
    liquidation_protection_enabled=liq_protection
)
```

### 1.3 Implement Loss Limit Check

**File**: `bot/strategy/async_gridbot.py`

**Add method**:
```python
async def _check_safety_limits(self) -> bool:
    """
    Check if safety limits allow trading.
    
    Returns:
        True if safe to trade, False if halted
    """
    # Check account loss limit
    try:
        positions = await self.api_client.get_positions(self.product_id)
        
        # Calculate total unrealized PnL
        total_pnl_usd = 0.0
        for pos in positions:
            unrealized_pnl = pos.get("unrealized_pnl", 0.0)
            total_pnl_usd += unrealized_pnl
        
        # Convert to INR (approximate)
        usd_to_inr = 85.0  # TODO: Get from config
        total_pnl_inr = total_pnl_usd * usd_to_inr
        
        # Check loss limit
        if total_pnl_inr < -self.max_account_loss_inr:
            if not self._safety_halt:
                self._safety_halt = True
                self._halt_reason = f"Loss limit exceeded: {total_pnl_inr:.2f} INR"
                log.error(f"🚨 SAFETY HALT: {self._halt_reason}")
                # TODO: Send Telegram alert
            return False
        
        # Check if we should resume
        if self._safety_halt and total_pnl_inr > -(self.max_account_loss_inr * 0.8):
            self._safety_halt = False
            self._halt_reason = None
            log.info(f"✅ Safety halt cleared, loss recovered: {total_pnl_inr:.2f} INR")
            # TODO: Send Telegram alert
        
        return not self._safety_halt
        
    except Exception as e:
        log.error(f"Safety check failed: {e}")
        return True  # Fail open to avoid blocking on transient errors
```

**Call before placing orders**:
```python
# In _process_price_update() or wherever orders are placed
if not await self._check_safety_limits():
    log.warning("Trading halted due to safety limits")
    return
```

---

## Priority 2: Order Tagging

### 2.1 Add Tag Parameter to AsyncGridBot

**File**: `bot/strategy/async_gridbot.py`

**Add to __init__**:
```python
def __init__(
    self,
    # ... existing parameters ...
    tag_prefix: str = "GBOT_",
    cancel_all_on_start: bool = False,
    cancel_scope: str = "tagged"
):
    # ... existing code ...
    
    # Order tagging
    self.tag_prefix = tag_prefix
    self.cancel_all_on_start = cancel_all_on_start
    self.cancel_scope = cancel_scope
```

### 2.2 Generate Order Tags

**File**: `bot/strategy/actors/order_actor.py`

**Add tag generation**:
```python
class OrderManagerActor(Actor):
    def __init__(
        self,
        api_client: AsyncDeltaClient,
        event_store: EventStore,
        symbol: str = "BTCUSD",
        product_id: int = 27,
        max_retries: int = 3,
        tag_prefix: str = "GBOT_"  # NEW
    ):
        super().__init__("OrderManager")
        self.api_client = api_client
        self.event_store = event_store
        self.symbol = symbol
        self.product_id = product_id
        self.max_retries = max_retries
        self.tag_prefix = tag_prefix  # NEW
    
    def _generate_order_tag(self, side: str, price: float) -> str:
        """Generate order tag: GBOT_BUY_99000_1699876543"""
        timestamp = int(time.time())
        price_int = int(price)
        return f"{self.tag_prefix}{side.upper()}_{price_int}_{timestamp}"
    
    async def _handle_place_buy(self, payload: Dict[str, Any], ...) -> Dict[str, Any]:
        price = payload["price"]
        size = payload["size"]
        
        # Generate tag
        tag = self._generate_order_tag("buy", price)
        
        # Place order with tag
        result = await self.api_client.place_order(
            product_id=self.product_id,
            side="buy",
            price=price,
            size=size,
            post_only=True,
            client_order_id=tag  # Pass tag as client_order_id
        )
```

### 2.3 Wire Tag Parameters from bot/run.py

**File**: `bot/run.py`

**Add extraction**:
```python
# Extract order management parameters
tag_prefix = os.getenv("GRIDBOT_TAG_PREFIX", "GBOT_")
cancel_all = os.getenv("GRIDBOT_CANCEL_ALL_ON_START", "0") == "1"
cancel_scope = os.getenv("GRIDBOT_CANCEL_SCOPE", "tagged")
```

**Pass to AsyncGridBot**:
```python
async_bot = AsyncGridBot(
    # ... existing parameters ...
    tag_prefix=tag_prefix,
    cancel_all_on_start=cancel_all,
    cancel_scope=cancel_scope
)
```

**Pass to OrderActor**:
```python
# In AsyncGridBot.__init__
self.order_actor = OrderManagerActor(
    api_client=self.api_client,
    event_store=self.event_store,
    symbol=self.symbol,
    product_id=self.product_id,
    tag_prefix=self.tag_prefix  # NEW
)
```

---

## Priority 3: Post-Only Configuration

### 3.1 Add Post-Only Mode Parameter

**File**: `bot/strategy/async_gridbot.py`

**Add to __init__**:
```python
def __init__(
    self,
    # ... existing parameters ...
    post_only_mode: str = "auto"  # "auto", "always", "never"
):
    # ... existing code ...
    self.post_only_mode = post_only_mode
```

### 3.2 Pass to OrderActor

**File**: `bot/strategy/actors/order_actor.py`

**Add parameter**:
```python
class OrderManagerActor(Actor):
    def __init__(
        self,
        # ... existing parameters ...
        post_only_mode: str = "auto"
    ):
        # ... existing code ...
        self.post_only_mode = post_only_mode
    
    def _should_use_post_only(self, side: str, order_type: str) -> bool:
        """Determine if order should be post-only."""
        if self.post_only_mode == "always":
            return True
        elif self.post_only_mode == "never":
            return False
        else:  # "auto"
            # BUY orders: maker (post-only)
            # TP/SELL orders: taker (not post-only)
            return side == "buy" and order_type == "entry"
```

**Use in order placement**:
```python
async def _handle_place_buy(self, payload: Dict[str, Any], ...) -> Dict[str, Any]:
    # ... existing code ...
    
    post_only = self._should_use_post_only("buy", "entry")
    
    result = await self.api_client.place_order(
        product_id=self.product_id,
        side="buy",
        price=price,
        size=size,
        post_only=post_only  # Use configured value
    )
```

### 3.3 Wire from bot/run.py

**File**: `bot/run.py`

```python
# Extract post-only mode
post_only_mode = os.getenv("GRIDBOT_POST_ONLY_MODE", "auto")

async_bot = AsyncGridBot(
    # ... existing parameters ...
    post_only_mode=post_only_mode
)
```

---

## Priority 4: Grid Behavior (Optional)

### 4.1 Add Grid Behavior Parameters

**File**: `bot/strategy/async_gridbot.py`

```python
def __init__(
    self,
    # ... existing parameters ...
    strict_grid: bool = True,
    strict_start: bool = True,
    seed_initial_count: int = 0
):
    # ... existing code ...
    self.strict_grid = strict_grid
    self.strict_start = strict_start
    self.seed_initial_count = seed_initial_count
```

### 4.2 Implement Initial Seeding

**File**: `bot/strategy/async_gridbot.py`

```python
async def _seed_initial_orders(self) -> None:
    """Place initial orders at startup if seeding enabled."""
    if self.seed_initial_count == 0:
        return
    
    log.info(f"Seeding {self.seed_initial_count} initial orders...")
    
    # Calculate seed levels
    current_price = self.current_price or self.lower_price
    seed_levels = []
    
    for i in range(self.seed_initial_count):
        level = current_price - (self.grid_step * (i + 1))
        if level >= self.lower_price:
            seed_levels.append(level)
    
    # Place orders
    for level in seed_levels:
        try:
            await self.order_actor.ask("PLACE_BUY", {
                "price": level,
                "size": self.lot_size
            })
            log.info(f"Seeded BUY order at {level}")
        except Exception as e:
            log.error(f"Failed to seed order at {level}: {e}")
```

**Call in start()**:
```python
async def start(self) -> None:
    # ... existing startup code ...
    
    # Seed initial orders if configured
    if self.seed_initial_count > 0:
        await self._seed_initial_orders()
```

---

## Implementation Order

### Day 1 (4 hours):
1. ✅ Add safety parameters to AsyncGridBot.__init__ (30 min)
2. ✅ Wire safety parameters from bot/run.py (30 min)
3. ✅ Implement loss limit check method (1 hour)
4. ✅ Add order tagging to OrderActor (1 hour)
5. ✅ Wire tag parameters (30 min)
6. ✅ Test with 1000 INR loss limit (30 min)

### Day 2 (2 hours):
1. ✅ Add post-only mode parameter (30 min)
2. ✅ Implement post-only logic (30 min)
3. ✅ Add grid behavior parameters (30 min)
4. ✅ Test all features (30 min)

### Day 3 (Testing):
1. ✅ Test loss limits
2. ✅ Test order tagging
3. ✅ Test restart behavior
4. ✅ Final production validation

---

## Testing Checklist

### Safety Features:
- [ ] Loss limit triggers at threshold
- [ ] Loss limit recovers when PnL improves
- [ ] Telegram alert sent on halt
- [ ] No orders placed when halted

### Order Tagging:
- [ ] Tags generated correctly (GBOT_BUY_99000_1699876543)
- [ ] Tags visible on Delta Exchange
- [ ] Bot recognizes own orders on restart
- [ ] Can cancel only tagged orders

### Post-Only Mode:
- [ ] BUY orders use post-only (auto mode)
- [ ] TP orders don't use post-only (auto mode)
- [ ] Always mode works
- [ ] Never mode works

### Grid Behavior:
- [ ] Strict grid enforced
- [ ] Initial seeding places correct orders
- [ ] First order placement correct

---

## Configuration Verification Script

Create `verify_wiring.py`:
```python
#!/usr/bin/env python3
"""Verify all grid_config.env parameters are wired."""

import os
from dotenv import load_dotenv

# Load config
load_dotenv("grid_config.env", override=True)

def check_param(name, expected_type):
    value = os.getenv(name)
    if value is None:
        return f"❌ {name}: NOT SET"
    else:
        return f"✅ {name}: {value}"

print("=" * 80)
print("GRID CONFIG WIRING VERIFICATION")
print("=" * 80)

# Safety parameters
print("\n🛡️  SAFETY FEATURES:")
print(check_param("MAX_ACCOUNT_LOSS_INR", float))
print(check_param("VOLATILITY_SAFETY_ENABLED", bool))
print(check_param("VOLATILITY_MAX_IV", float))
print(check_param("CONFIRMATION_GUARD_ENABLED", bool))
print(check_param("CIRCUIT_BREAKER_ENABLED", bool))

# Order management
print("\n🏷️  ORDER MANAGEMENT:")
print(check_param("GRIDBOT_TAG_PREFIX", str))
print(check_param("GRIDBOT_POST_ONLY_MODE", str))
print(check_param("GRIDBOT_CANCEL_ALL_ON_START", bool))

# Grid behavior
print("\n📊 GRID BEHAVIOR:")
print(check_param("GRIDBOT_STRICT_GRID", bool))
print(check_param("GRIDBOT_STRICT_START", bool))
print(check_param("GRIDBOT_SEED_INITIAL_COUNT", int))

print("\n" + "=" * 80)
```

---

## Rollout Plan

### Phase 1: Safety Features (BLOCKING)
- Implement loss limits
- Test with small capital
- Verify halt works
- **DO NOT PROCEED** without this

### Phase 2: Order Tagging (CRITICAL)
- Implement tagging
- Test restart behavior
- Verify tag recognition

### Phase 3: Configuration (NICE TO HAVE)
- Post-only mode
- Grid behavior
- Initial seeding

### Phase 4: Production
- Monitor first 5 minutes
- Verify safety features active
- Check loss limits working
- Monitor for 1 hour
- Scale up if stable

---

**End of Implementation Plan**
