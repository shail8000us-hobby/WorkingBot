# Shared API Layer - Unified WebSocket & REST Proposal

**Date:** November 20, 2025, 2:13 AM  
**Status:** 💡 **PROPOSAL**

---

## 🎯 **The Problem**

Currently, **each system has its own API client**:

```
async_gridbot.py
├── AsyncWebSocketManager (WebSocket)
├── AsyncDeltaClient (REST API)
└── REST fallback logic

recovery_runner.py
├── AsyncDeltaClient (REST API)
└── No WebSocket (doesn't need it)

reconciliation_runner.py
├── AsyncDeltaClient (REST API)
└── No WebSocket (doesn't need it)

guardian_bot.py (if exists)
├── Own API client
└── Own WebSocket?
```

**Problems:**
- ❌ Code duplication
- ❌ Inconsistent error handling
- ❌ Different retry logic
- ❌ Hard to maintain
- ❌ No shared connection pooling
- ❌ Each system manages its own fallback

---

## 💡 **The Solution**

Create a **unified API layer** that all systems use:

```
bot/api/unified_api_client.py (NEW)
├── WebSocket connection (shared)
├── REST API client (shared)
├── Automatic fallback (WebSocket → REST)
├── Connection pooling
├── Retry logic
├── Circuit breaker
└── Rate limiting

ALL SYSTEMS USE THIS:
├── async_gridbot.py → UnifiedAPIClient
├── recovery_runner.py → UnifiedAPIClient
├── reconciliation_runner.py → UnifiedAPIClient
├── guardian_bot.py → UnifiedAPIClient
└── monitoring systems → UnifiedAPIClient
```

---

## ✅ **Benefits**

### **1. Single Source of Truth**
- ✅ One WebSocket connection
- ✅ One REST client
- ✅ One fallback mechanism
- ✅ Consistent behavior

### **2. Better Resource Management**
- ✅ Shared connection pooling
- ✅ Reduced memory usage
- ✅ Fewer connections to exchange
- ✅ Better rate limit management

### **3. Easier Maintenance**
- ✅ Update once, affects all systems
- ✅ Fix bugs in one place
- ✅ Add features once
- ✅ Consistent error handling

### **4. Better Reliability**
- ✅ Centralized fallback logic
- ✅ Shared circuit breaker
- ✅ Coordinated retries
- ✅ Health monitoring

### **5. Cleaner Code**
- ✅ No duplication
- ✅ Clear interfaces
- ✅ Single responsibility
- ✅ Easy to test

---

## 🏗️ **Architecture**

### **Current (Duplicated):**
```
async_gridbot.py (3,555 lines)
├── AsyncWebSocketManager
├── AsyncDeltaClient
├── REST fallback logic
└── Connection management

recovery_runner.py (550 lines)
├── AsyncDeltaClient
└── Connection management

reconciliation_runner.py (550 lines)
├── AsyncDeltaClient
└── Connection management

TOTAL DUPLICATION: ~300 lines × 3 = 900 lines
```

---

### **Proposed (Unified):**
```
bot/api/unified_api_client.py (NEW - 600 lines)
├── UnifiedAPIClient class
│   ├── WebSocket connection (optional)
│   ├── REST API client
│   ├── Automatic fallback
│   ├── Connection pooling
│   ├── Retry logic
│   ├── Circuit breaker
│   └── Rate limiting
└── Shared by ALL systems

async_gridbot.py (3,400 lines)
├── UnifiedAPIClient (WebSocket + REST)
└── Trading logic only

recovery_runner.py (500 lines)
├── UnifiedAPIClient (REST only)
└── Recovery logic only

reconciliation_runner.py (500 lines)
├── UnifiedAPIClient (REST only)
└── Reconciliation logic only

TOTAL: 600 lines (unified) vs 900 lines (duplicated)
SAVINGS: 300 lines + better architecture
```

---

## 📋 **UnifiedAPIClient Design**

### **Core Features:**

```python
class UnifiedAPIClient:
    """
    Unified API client for all systems.
    Supports WebSocket (optional) and REST API with automatic fallback.
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        enable_websocket: bool = True,  # Optional WebSocket
        symbol: Optional[str] = None,
        product_id: Optional[int] = None
    ):
        # REST API client (always available)
        self.rest_client = AsyncDeltaClient(...)
        
        # WebSocket (optional, only if enabled)
        self.ws_manager = None
        if enable_websocket:
            self.ws_manager = AsyncWebSocketManager(...)
        
        # Fallback state
        self.ws_active = enable_websocket
        self.rest_fallback_active = False
        
        # Connection pooling
        self.connection_pool = ...
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(...)
        
        # Rate limiter
        self.rate_limiter = RateLimiter(...)
    
    # ========================================
    # HIGH-LEVEL METHODS (Used by all systems)
    # ========================================
    
    async def get_current_price(self) -> float:
        """Get current price (WebSocket if available, else REST)"""
        if self.ws_active and self.ws_manager:
            return await self._get_price_from_websocket()
        else:
            return await self._get_price_from_rest()
    
    async def get_order(self, order_id: str) -> Dict:
        """Get order details (always REST)"""
        return await self.rest_client.get_order(order_id)
    
    async def list_orders(self, **kwargs) -> List[Dict]:
        """List orders (always REST)"""
        return await self.rest_client.list_orders(**kwargs)
    
    async def get_positions(self) -> List[Dict]:
        """Get positions (always REST)"""
        return await self.rest_client.get_positions()
    
    async def place_order(self, **kwargs) -> Dict:
        """Place order (always REST)"""
        return await self.rest_client.place_order(**kwargs)
    
    async def cancel_order(self, order_id: str) -> Dict:
        """Cancel order (always REST)"""
        return await self.rest_client.cancel_order(order_id)
    
    # ========================================
    # WEBSOCKET METHODS (Optional)
    # ========================================
    
    async def subscribe_to_price(self, callback):
        """Subscribe to price updates (WebSocket only)"""
        if not self.ws_manager:
            raise ValueError("WebSocket not enabled")
        await self.ws_manager.subscribe_price(callback)
    
    async def subscribe_to_fills(self, callback):
        """Subscribe to fill updates (WebSocket only)"""
        if not self.ws_manager:
            raise ValueError("WebSocket not enabled")
        await self.ws_manager.subscribe_fills(callback)
    
    # ========================================
    # FALLBACK LOGIC
    # ========================================
    
    async def _get_price_from_websocket(self) -> float:
        """Get price from WebSocket with fallback"""
        try:
            # Check if price is stale
            if self._is_price_stale():
                log.warning("WebSocket price stale - falling back to REST")
                return await self._activate_rest_fallback()
            
            return self.current_price
        
        except Exception as e:
            log.error(f"WebSocket price error: {e}")
            return await self._activate_rest_fallback()
    
    async def _activate_rest_fallback(self) -> float:
        """Activate REST fallback for price"""
        self.rest_fallback_active = True
        return await self._get_price_from_rest()
    
    async def _get_price_from_rest(self) -> float:
        """Get price from REST API"""
        ticker = await self.rest_client.get_ticker(self.symbol)
        return float(ticker.get('mark_price', 0))
    
    # ========================================
    # CONNECTION MANAGEMENT
    # ========================================
    
    async def connect(self):
        """Connect WebSocket (if enabled)"""
        if self.ws_manager:
            await self.ws_manager.connect()
    
    async def disconnect(self):
        """Disconnect WebSocket (if enabled)"""
        if self.ws_manager:
            await self.ws_manager.disconnect()
    
    async def health_check(self) -> Dict:
        """Check health of all connections"""
        return {
            'websocket': {
                'enabled': self.ws_manager is not None,
                'active': self.ws_active,
                'connected': self.ws_manager.is_connected() if self.ws_manager else False
            },
            'rest': {
                'active': True,
                'fallback_active': self.rest_fallback_active,
                'circuit_breaker': self.circuit_breaker.state
            }
        }
```

---

## 🔧 **Implementation Plan**

### **Phase 1: Create UnifiedAPIClient (2 hours)**

**File:** `bot/api/unified_api_client.py`

1. Create base class with REST client
2. Add optional WebSocket support
3. Implement fallback logic
4. Add connection pooling
5. Add circuit breaker
6. Add rate limiting
7. Add health monitoring

---

### **Phase 2: Update async_gridbot.py (1 hour)**

**Changes:**
```python
# OLD:
from bot.api.async_delta_client import AsyncDeltaClient
from bot.delta_websocket.async_ws_manager import AsyncWebSocketManager

self.api_client = AsyncDeltaClient(...)
self.ws_manager = AsyncWebSocketManager(...)

# NEW:
from bot.api.unified_api_client import UnifiedAPIClient

self.api_client = UnifiedAPIClient(
    api_key=api_key,
    api_secret=api_secret,
    testnet=testnet,
    enable_websocket=True,  # Bot needs WebSocket
    symbol=self.symbol,
    product_id=self.product_id
)

# All API calls remain the same!
price = await self.api_client.get_current_price()
orders = await self.api_client.list_orders()
```

**Remove:**
- ❌ REST fallback logic (~100 lines)
- ❌ WebSocket management code (~50 lines)
- ❌ Connection pooling code (~30 lines)

**Total removal:** ~180 lines

---

### **Phase 3: Update recovery_runner.py (30 minutes)**

**Changes:**
```python
# OLD:
from bot.api.async_delta_client import AsyncDeltaClient

api_client = AsyncDeltaClient(
    api_key=api_key,
    api_secret=api_secret,
    testnet=testnet
)

# NEW:
from bot.api.unified_api_client import UnifiedAPIClient

api_client = UnifiedAPIClient(
    api_key=api_key,
    api_secret=api_secret,
    testnet=testnet,
    enable_websocket=False  # Recovery doesn't need WebSocket
)

# All API calls remain the same!
orders = await api_client.list_orders()
positions = await api_client.get_positions()
```

**Remove:**
- ❌ Duplicate API client setup (~20 lines)

---

### **Phase 4: Update reconciliation_runner.py (30 minutes)**

**Changes:**
```python
# Same as recovery_runner.py
from bot.api.unified_api_client import UnifiedAPIClient

api_client = UnifiedAPIClient(
    api_key=api_key,
    api_secret=api_secret,
    testnet=testnet,
    enable_websocket=False  # Reconciliation doesn't need WebSocket
)
```

**Remove:**
- ❌ Duplicate API client setup (~20 lines)

---

### **Phase 5: Testing (1 hour)**

1. Test UnifiedAPIClient independently
2. Test with async_gridbot.py (WebSocket + REST)
3. Test with recovery_runner.py (REST only)
4. Test with reconciliation_runner.py (REST only)
5. Test fallback mechanism
6. Test circuit breaker
7. Test rate limiting

---

## 📊 **Expected Results**

### **Code Reduction:**
```
async_gridbot.py
├── Before: 3,555 lines
├── Remove: 180 lines (fallback + WS management)
└── After: 3,375 lines (5% smaller)

recovery_runner.py
├── Before: 550 lines
├── Remove: 20 lines (duplicate API setup)
└── After: 530 lines

reconciliation_runner.py
├── Before: 550 lines
├── Remove: 20 lines (duplicate API setup)
└── After: 530 lines

NEW FILE:
unified_api_client.py: 600 lines

TOTAL:
├── Before: 4,655 lines (with duplication)
├── After: 5,035 lines (with unified client)
└── Net: +380 lines BUT much better architecture
```

**Note:** While total lines increase slightly, we gain:
- ✅ No duplication
- ✅ Single source of truth
- ✅ Better maintainability
- ✅ Shared resources
- ✅ Consistent behavior

---

## 🎯 **Benefits Summary**

### **For async_gridbot.py:**
- ✅ 180 lines smaller
- ✅ No fallback logic to maintain
- ✅ Automatic WebSocket → REST fallback
- ✅ Shared connection pooling

### **For recovery_runner.py:**
- ✅ 20 lines smaller
- ✅ Same API interface as bot
- ✅ Shared circuit breaker
- ✅ Shared rate limiting

### **For reconciliation_runner.py:**
- ✅ 20 lines smaller
- ✅ Same API interface as bot
- ✅ Shared circuit breaker
- ✅ Shared rate limiting

### **For All Systems:**
- ✅ Update once, affects all
- ✅ Fix bugs once
- ✅ Add features once
- ✅ Consistent error handling
- ✅ Better resource management

---

## 🔄 **Migration Path**

### **Step 1: Create UnifiedAPIClient**
- Create new file
- Implement all features
- Test independently

### **Step 2: Migrate async_gridbot.py**
- Replace AsyncDeltaClient + AsyncWebSocketManager
- Remove fallback logic
- Test thoroughly

### **Step 3: Migrate recovery_runner.py**
- Replace AsyncDeltaClient
- Test standalone

### **Step 4: Migrate reconciliation_runner.py**
- Replace AsyncDeltaClient
- Test standalone

### **Step 5: Deprecate Old Clients**
- Mark AsyncDeltaClient as deprecated (keep for backward compatibility)
- Mark AsyncWebSocketManager as deprecated (keep for backward compatibility)
- Update documentation

---

## ⏱️ **Implementation Timeline**

**Total Time: 5 hours**

1. **Phase 1:** Create UnifiedAPIClient (2 hours)
2. **Phase 2:** Update async_gridbot.py (1 hour)
3. **Phase 3:** Update recovery_runner.py (30 minutes)
4. **Phase 4:** Update reconciliation_runner.py (30 minutes)
5. **Phase 5:** Testing (1 hour)

---

## ✅ **Recommendation**

**YES, create a unified API layer!**

**Reasons:**
1. ✅ Eliminates code duplication
2. ✅ Single source of truth
3. ✅ Better resource management
4. ✅ Easier maintenance
5. ✅ Consistent behavior across all systems
6. ✅ Shared connection pooling
7. ✅ Centralized fallback logic
8. ✅ Better error handling

**This would make the entire system more maintainable and reliable!**

---

## 📋 **Next Steps**

If you approve, I will:
1. Create `bot/api/unified_api_client.py`
2. Implement all features (WebSocket, REST, fallback, circuit breaker)
3. Update `async_gridbot.py` to use UnifiedAPIClient
4. Update `recovery_runner.py` to use UnifiedAPIClient
5. Update `reconciliation_runner.py` to use UnifiedAPIClient
6. Test all systems
7. Document usage

**Should I proceed with implementation?**

---

**Created:** November 20, 2025, 2:13 AM  
**Status:** 💡 **AWAITING APPROVAL**  
**Estimated Time:** 5 hours
