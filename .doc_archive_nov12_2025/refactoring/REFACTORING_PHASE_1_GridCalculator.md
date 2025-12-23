# PHASE 1: Extract GridCalculator Module

**Risk Level**: 🟢 LOW  
**Complexity**: Simple pure functions  
**Estimated Effort**: 2-3 hours  
**Dependencies**: ZERO (pure logic)  
**Status**: ⏳ READY TO START

---

## 1. PRE-REFACTOR ANALYSIS

### A. Methods to Extract (5 total)

#### Method 1: `_compute_target_buy()`
- **Location**: Lines 1147-1164
- **Purpose**: Calculate the next grid BUY price based on open positions
- **Dependencies**: Uses `self.open_tranches`, `self.ref`, `self.step`, `self.lower`, `self.upper`
- **Called by**: 
  - `_ensure_single_correct_pending_buy()` (Line 1175)
  - `_resume_normal_grid()` (Line 1993)
  - Heartbeat reconciliation (Line 3330)
- **Returns**: `Optional[float]` - Target BUY price or None
- **Thread-safe**: YES (uses `_state_lock`)

```python
def _compute_target_buy(self) -> Optional[float]:
    """
    Compute the canonical target buy price (single source of truth)
    
    Returns:
        Target buy price (quantized and clamped), or None if no buy needed
    """
    with self._state_lock:
        if self.open_tranches:
            lowest_entry = min(t['entry_price'] for t in self.open_tranches)
        else:
            lowest_entry = self.ref
        target = lowest_entry - self.step

    # clamp & quantize
    if target < self.lower or target > self.upper:
        return None
    return _quantize(target)
```

#### Method 2: `_quantize()` (Helper Function)
- **Location**: Lines 152-154
- **Purpose**: Snap price down to exchange tick size
- **Dependencies**: Uses `TICK_SIZE` constant
- **Called by**: 
  - `_compute_target_buy()` (Line 1164)
  - `_place_buy_order()` (Line 2288)
  - `_place_tp_sell()` (Line 2475)
  - `_setup_initial_grid()` (Line 2627)
- **Returns**: `float`
- **Thread-safe**: YES (pure function, no state)

```python
def _quantize(px: float) -> float:
    """Snap price down to exchange tick size"""
    return math.floor(px / TICK_SIZE) * TICK_SIZE
```

#### Method 3: `_tp_for_entry()` (Helper Function)
- **Location**: Lines 143-144
- **Purpose**: Calculate TP price for given entry
- **Dependencies**: None (pure function)
- **Called by**: `_on_fill_detected()` (Line 635)
- **Returns**: `float`
- **Thread-safe**: YES (pure function)

```python
def _tp_for_entry(entry_px: float, step: float) -> float:
    return entry_px + step
```

#### Method 4: `_next_lower_after_buy()` (Helper Function)
- **Location**: Lines 146-147
- **Purpose**: Calculate next grid level after a BUY fills
- **Dependencies**: None (pure function)
- **Called by**: 
  - `_on_fill_detected()` (Line 656, 703)
- **Returns**: `float`
- **Thread-safe**: YES (pure function)

```python
def _next_lower_after_buy(entry_px: float, step: float) -> float:
    return entry_px - step
```

#### Method 5: `_within_band()` (Helper Function)
- **Location**: Lines 140-141
- **Purpose**: Check if price is within grid bounds
- **Dependencies**: None (pure function)
- **Called by**: 
  - `__init__()` (Line 215 - validation)
  - `_setup_initial_grid()` (Line 2633)
- **Returns**: `bool`
- **Thread-safe**: YES (pure function)

```python
def _within_band(px: float, lo: float, hi: float) -> bool:
    return lo <= px <= hi
```

### B. State to Extract

**Grid Configuration (Read-Only)**:
- `self.lower` (float) - Grid lower bound
- `self.upper` (float) - Grid upper bound
- `self.step` (float) - Grid step size
- `self.ref` (float) - Reference level
- `TICK_SIZE` (float) - Exchange tick size constant

**Accessed State (Not Owned)**:
- `self.open_tranches` (List[Dict]) - Owned by PositionManager, read-only access here

### C. Dependencies Graph

```
GridCalculator (Pure Logic)
     ↑
     │ (uses)
     │
PositionManager.open_tranches (read-only)
```

**No Outgoing Dependencies** ✅  
**GridCalculator is a LEAF NODE** ✅

### D. Risk Assessment

- **Complexity**: ⭐ LOW (pure functions, simple math)
- **Coupling**: ⭐ LOOSE (only reads grid config)
- **Test Coverage**: ⭐⭐⭐ EXCELLENT (pure functions are easy to test)
- **Breaking Change Risk**: ⭐ MINIMAL (isolated logic)

---

## 2. MODULE DESIGN

### File: `bot/strategy/modules/grid_calculator.py`

```python
"""
GridCalculator - Pure Grid Logic Module

Single Responsibility: Calculate grid prices and validate grid bounds

This module contains ZERO state and ZERO side effects.
All functions are pure - same inputs always produce same outputs.
"""

import math
from typing import List, Dict, Optional, Any


class GridCalculator:
    """
    Pure grid calculation logic (no state, no side effects)
    
    Responsibilities:
    - Calculate next BUY level based on positions
    - Calculate TP price from entry price
    - Quantize prices to exchange tick size
    - Validate prices within grid bounds
    
    NOT Responsible For:
    - Order placement
    - State management
    - Network I/O
    - Position tracking
    """
    
    def __init__(
        self,
        lower: float,
        upper: float,
        step: float,
        ref: float,
        tick_size: float = 0.5
    ):
        """
        Initialize grid calculator with grid parameters
        
        Args:
            lower: Grid lower bound (e.g., 105000)
            upper: Grid upper bound (e.g., 120000)
            step: Grid step size (e.g., 1000)
            ref: Reference level (e.g., 110000)
            tick_size: Exchange tick size for quantization (default: 0.5)
        """
        # Validate grid parameters
        if step <= 0:
            raise ValueError("Step must be positive")
        if lower >= upper:
            raise ValueError("Lower bound must be less than upper bound")
        if not self.is_within_bounds(ref, lower, upper):
            raise ValueError("Reference must be within grid bounds")
        
        self.lower = float(lower)
        self.upper = float(upper)
        self.step = float(step)
        self.ref = float(ref)
        self.tick_size = float(tick_size)
    
    def compute_next_buy_level(
        self,
        open_positions: List[Dict[str, Any]]
    ) -> Optional[float]:
        """
        Compute the next BUY level for grid trading
        
        Logic:
        - If no positions: BUY at (ref - step)
        - If positions exist: BUY at (lowest_entry - step)
        - Quantize to tick size
        - Return None if outside grid bounds
        
        Args:
            open_positions: List of open position dicts with 'entry_price' key
            
        Returns:
            Next BUY price (quantized), or None if no BUY needed
        """
        # Find lowest entry price
        if open_positions:
            lowest_entry = min(p['entry_price'] for p in open_positions)
        else:
            lowest_entry = self.ref
        
        # Calculate target one step below
        target = lowest_entry - self.step
        
        # Validate within bounds
        if not self.is_within_bounds(target, self.lower, self.upper):
            return None
        
        # Quantize to tick size
        return self.quantize_price(target)
    
    def compute_tp_price(self, entry_price: float) -> float:
        """
        Compute take-profit price from entry price
        
        Args:
            entry_price: Position entry price
            
        Returns:
            TP price (entry + step)
        """
        return entry_price + self.step
    
    def compute_next_level_down(self, current_price: float) -> float:
        """
        Compute next grid level below current price
        
        Args:
            current_price: Current price level
            
        Returns:
            Next level down (current - step)
        """
        return current_price - self.step
    
    def quantize_price(self, price: float) -> float:
        """
        Quantize price to exchange tick size (snap down)
        
        Args:
            price: Raw price
            
        Returns:
            Price snapped to tick size (floor)
        """
        return math.floor(price / self.tick_size) * self.tick_size
    
    def is_within_bounds(
        self,
        price: float,
        lower: Optional[float] = None,
        upper: Optional[float] = None
    ) -> bool:
        """
        Check if price is within grid bounds
        
        Args:
            price: Price to check
            lower: Lower bound (defaults to self.lower)
            upper: Upper bound (defaults to self.upper)
            
        Returns:
            True if price is within bounds
        """
        if lower is None:
            lower = self.lower
        if upper is None:
            upper = self.upper
        
        return lower <= price <= upper
    
    def get_grid_levels(self) -> List[float]:
        """
        Generate all grid levels from lower to upper
        
        Returns:
            List of grid levels (quantized)
        """
        levels = []
        current = self.lower
        
        while current <= self.upper:
            levels.append(self.quantize_price(current))
            current += self.step
        
        return levels
    
    def find_nearest_grid_level(self, price: float) -> float:
        """
        Find nearest grid level to given price (for alignment)
        
        Args:
            price: Target price
            
        Returns:
            Nearest grid level (rounded to step boundary)
        """
        # Round to nearest step boundary
        return round(price / self.step) * self.step
```

---

## 3. EXTRACTION STEPS (Detailed Checklist)

### Step 1: Create Module File ✅
```bash
mkdir -p bot/strategy/modules
touch bot/strategy/modules/__init__.py
touch bot/strategy/modules/grid_calculator.py
```

□ Create directory structure  
□ Create `__init__.py` (empty file)  
□ Create `grid_calculator.py` with class skeleton

### Step 2: Copy Methods (COPY, Don't Delete Yet!)

□ Copy `_quantize()` helper (lines 152-154)  
   - Rename to `quantize_price()`  
   - Make it a method with `self`  
   - Use `self.tick_size`

□ Copy `_within_band()` helper (lines 140-141)  
   - Rename to `is_within_bounds()`  
   - Make it a method with `self`  
   - Add optional lower/upper parameters

□ Copy `_tp_for_entry()` helper (lines 143-144)  
   - Rename to `compute_tp_price()`  
   - Make it a method with `self`  
   - Use `self.step`

□ Copy `_next_lower_after_buy()` helper (lines 146-147)  
   - Rename to `compute_next_level_down()`  
   - Make it a method with `self`  
   - Use `self.step`

□ Copy `_compute_target_buy()` method (lines 1147-1164)  
   - Rename to `compute_next_buy_level()`  
   - Remove `_state_lock` usage (caller handles locking)  
   - Accept `open_positions` as parameter instead of `self.open_tranches`  
   - Use `self.lower`, `self.upper`, `self.ref`, `self.step`

### Step 3: Resolve Dependencies

□ Update `__init__()` to accept grid parameters  
□ Add type hints to all methods  
□ Add comprehensive docstrings  
□ Add parameter validation in `__init__()`  
□ Add bonus method: `get_grid_levels()` (useful for debugging)  
□ Add bonus method: `find_nearest_grid_level()` (used in grid realignment)

### Step 4: Update Main GridBot File

```python
# bot/strategy/gbot_ws.py

# Add import at top
from bot.strategy.modules.grid_calculator import GridCalculator

class GridBotWebSocket:
    def __init__(self, ...):
        # Initialize grid calculator (EARLY - no dependencies)
        self.grid_calc = GridCalculator(
            lower=self.lower,
            upper=self.upper,
            step=self.step,
            ref=self.ref,
            tick_size=TICK_SIZE
        )
        
        # Rest of initialization...
    
    # SHIM: Delegate to grid_calc (DEPRECATED)
    def _compute_target_buy(self) -> Optional[float]:
        """DEPRECATED: Use grid_calc.compute_next_buy_level() instead"""
        with self._state_lock:
            return self.grid_calc.compute_next_buy_level(self.open_tranches)
    
    # SHIM: Delegate to grid_calc (DEPRECATED)
    def _quantize(self, px: float) -> float:
        """DEPRECATED: Use grid_calc.quantize_price() instead"""
        return self.grid_calc.quantize_price(px)
    
    # ... other shims ...
```

### Step 5: Create Tests

Create: `tests/test_grid_calculator.py`

```python
import pytest
from bot.strategy.modules.grid_calculator import GridCalculator


class TestGridCalculator:
    """Test suite for GridCalculator pure logic module"""
    
    def test_initialization_valid_params(self):
        """Test calculator initializes with valid parameters"""
        calc = GridCalculator(
            lower=105000,
            upper=120000,
            step=1000,
            ref=110000,
            tick_size=0.5
        )
        assert calc.lower == 105000
        assert calc.upper == 120000
        assert calc.step == 1000
        assert calc.ref == 110000
    
    def test_initialization_invalid_step(self):
        """Test calculator rejects invalid step"""
        with pytest.raises(ValueError, match="Step must be positive"):
            GridCalculator(lower=105000, upper=120000, step=0, ref=110000)
    
    def test_initialization_invalid_bounds(self):
        """Test calculator rejects invalid bounds"""
        with pytest.raises(ValueError, match="Lower bound must be less than upper"):
            GridCalculator(lower=120000, upper=105000, step=1000, ref=110000)
    
    def test_initialization_ref_outside_bounds(self):
        """Test calculator rejects ref outside bounds"""
        with pytest.raises(ValueError, match="Reference must be within grid bounds"):
            GridCalculator(lower=105000, upper=120000, step=1000, ref=125000)
    
    def test_compute_next_buy_no_positions(self):
        """Test next BUY with no open positions"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        result = calc.compute_next_buy_level([])
        assert result == 109000  # ref - step
    
    def test_compute_next_buy_with_positions(self):
        """Test next BUY with existing positions"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        positions = [
            {'entry_price': 110000},
            {'entry_price': 109000},
            {'entry_price': 108000}
        ]
        result = calc.compute_next_buy_level(positions)
        assert result == 107000  # lowest (108000) - step
    
    def test_compute_next_buy_outside_lower_bound(self):
        """Test next BUY returns None when below lower bound"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        positions = [{'entry_price': 105500}]
        result = calc.compute_next_buy_level(positions)
        assert result is None  # 104500 < 105000 (lower bound)
    
    def test_compute_tp_price(self):
        """Test TP price calculation"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        assert calc.compute_tp_price(108000) == 109000
        assert calc.compute_tp_price(110000) == 111000
    
    def test_quantize_price(self):
        """Test price quantization to tick size"""
        calc = GridCalculator(105000, 120000, 1000, 110000, tick_size=0.5)
        assert calc.quantize_price(108000.7) == 108000.5
        assert calc.quantize_price(108000.2) == 108000.0
        assert calc.quantize_price(108000.0) == 108000.0
    
    def test_is_within_bounds(self):
        """Test bounds checking"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        assert calc.is_within_bounds(110000) is True
        assert calc.is_within_bounds(105000) is True
        assert calc.is_within_bounds(120000) is True
        assert calc.is_within_bounds(104999) is False
        assert calc.is_within_bounds(120001) is False
    
    def test_get_grid_levels(self):
        """Test grid level generation"""
        calc = GridCalculator(105000, 108000, 1000, 106000)
        levels = calc.get_grid_levels()
        assert levels == [105000, 106000, 107000, 108000]
    
    def test_find_nearest_grid_level(self):
        """Test grid alignment"""
        calc = GridCalculator(105000, 120000, 1000, 110000)
        assert calc.find_nearest_grid_level(107287.5) == 107000
        assert calc.find_nearest_grid_level(107600) == 108000
        assert calc.find_nearest_grid_level(107500) == 108000  # Rounds up
```

### Step 6: Integration Testing

□ Syntax validation:
```bash
python -m py_compile bot/strategy/modules/grid_calculator.py
python -m py_compile bot/strategy/gbot_ws.py
```

□ Import test:
```bash
python -c "from bot.strategy.modules.grid_calculator import GridCalculator"
```

□ Unit tests:
```bash
pytest tests/test_grid_calculator.py -v
```

□ Integration test (bot startup):
```bash
python bot/run.py --mode demo --duration 10
```

□ Verify grid calculations still work:
  - Check first BUY order price
  - Check TP price after fill
  - Check next BUY price after TP

### Step 7: Verify No Regressions

□ Compare log output: Same BUY/TP prices as before  
□ Check order format: Unchanged  
□ Compare behavior: Identical grid logic  
□ Performance: No measurable difference

### Step 8: Cleanup (After Verification)

□ Mark old methods as DEPRECATED in docstrings  
□ Keep shims in place (don't delete yet)  
□ Update docstrings to reference new module  
□ Add migration notes in comments

### Step 9: Commit

```bash
git add bot/strategy/modules/
git add bot/strategy/gbot_ws.py
git add tests/test_grid_calculator.py
git commit -m "Phase 1: Extract GridCalculator pure logic module

- Created bot/strategy/modules/grid_calculator.py (200 lines)
- Extracted 5 pure grid calculation methods
- Added comprehensive test suite (12 tests)
- Kept backward-compatible shims in gbot_ws.py
- ZERO behavior changes, all tests pass

Methods extracted:
- compute_next_buy_level() (was _compute_target_buy)
- compute_tp_price() (was _tp_for_entry)
- compute_next_level_down() (was _next_lower_after_buy)
- quantize_price() (was _quantize)
- is_within_bounds() (was _within_band)

Bonus methods added:
- get_grid_levels() (for debugging)
- find_nearest_grid_level() (for grid realignment)

Risk: LOW (pure functions, no state, no side effects)
Tests: 12/12 passed ✅"
```

---

## 4. ROLLBACK PLAN

### If Anything Breaks:

#### Immediate Actions:
1. `git revert HEAD`
2. Verify bot works again
3. DO NOT proceed to Phase 2

#### Investigation:
1. Check error logs: `tail -100 bot_demo.log`
2. Identify what broke
3. Fix issue locally
4. Re-test thoroughly
5. Retry extraction

#### If Unfixable:
1. Keep old architecture
2. Document blocker issue
3. Escalate for help

---

## 5. TESTING CHECKLIST (Must Pass ALL)

### Syntax Validation
```bash
□ python -m py_compile bot/strategy/modules/grid_calculator.py
□ python -m py_compile bot/strategy/gbot_ws.py
```

### Import Test
```bash
□ python -c "from bot.strategy.modules.grid_calculator import GridCalculator"
```

### Unit Tests
```bash
□ pytest tests/test_grid_calculator.py -v
```

### Integration Tests
```bash
□ pytest tests/ -v
```

### Bot Startup Test
```bash
□ python bot/run.py --mode demo --duration 10
```

### Order Placement Test
```bash
□ Start bot
□ Verify first BUY order placed within 30s
□ Check price matches grid logic
```

### Grid Logic Test
```bash
□ Simulate fill (manual market order)
□ Verify TP price = entry + step
□ Verify next BUY = entry - step
□ Check prices are quantized to tick size
```

---

## 6. ESTIMATED EFFORT

- **Analysis**: 0.5 hours (reading code, understanding dependencies)
- **Code Extraction**: 1 hour (creating module, copying methods)
- **Testing**: 1 hour (writing tests, running integration tests)
- **Documentation**: 0.5 hours (docstrings, comments)
- **Total**: **3 hours**

**Confidence**: HIGH ✅ (pure functions are safest to extract)

---

## 7. RISK LEVEL & MITIGATION

**Risk**: 🟢 LOW

**Reasons**:
- Pure functions (no state)
- No side effects
- Easy to test in isolation
- No external dependencies
- Leaf node in dependency graph

**Mitigation**:
- Comprehensive unit tests (12+ tests)
- Keep backward-compatible shims
- Integration tests verify behavior unchanged
- Can rollback immediately if issues found

---

## 8. SUCCESS CRITERIA

### Immediate (After Extraction):
✅ **Syntax valid** - Code compiles without errors  
✅ **Tests pass** - 12/12 unit tests green  
✅ **Bot starts** - No import errors  
✅ **Grid logic works** - BUY/TP prices match expected values

### Short-term (First Trading Session):
✅ **Order prices correct** - Grid levels match calculation  
✅ **TP prices correct** - entry + step  
✅ **Quantization works** - Prices snap to tick size  
✅ **Bounds checking** - Rejects orders outside grid

### Long-term (Production Stability):
✅ **No regressions** - Grid logic identical to before  
✅ **Code cleaner** - Main file reduced by ~20 lines  
✅ **Easier testing** - Pure functions easy to unit test  
✅ **Foundation laid** - Pattern established for remaining phases

---

**NEXT PHASE**: Phase 2 - Extract WebSocketHandler  
**PREREQUISITE**: Phase 1 must be COMPLETE and VERIFIED before proceeding
