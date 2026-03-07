# RSI Layer 6 - Guardian Safety System Documentation

**Feature:** RSI-Based Trading Safety Monitor (Layer 6)  
**Status:** ✅ Production Ready (Senior Developer Reviewed & Improved)  
**Date Implemented:** December 2025  
**Last Updated:** December 27, 2025  
**Review Status:** ✅ APPROVED - All critical bugs fixed, 19/19 tests passing  
**Review Document:** RSI_LAYER6_SENIOR_REVIEW.md

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Configuration](#configuration)
4. [Implementation Details](#implementation-details)
5. [Data Flow](#data-flow)
6. [API Endpoints](#api-endpoints)
7. [WebUI Integration](#webui-integration)
8. [Testing & Validation](#testing--validation)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

RSI Layer 6 is a mode-specific Relative Strength Index (RSI) monitoring system that prevents trading during overbought (LONG mode) or oversold (SHORT mode) market conditions. It acts as the 6th layer of the Guardian safety system, providing momentum-based risk protection.

### Key Features

- **Mode-Specific Thresholds:** Different RSI thresholds for LONG and SHORT trading modes
- **Hysteresis Protection:** Prevents signal jumping when RSI hovers at threshold
- **Real-Time Monitoring:** Fetches hourly OHLCV data from Delta Exchange India
- **Fail-Safe Design:** Returns None if data unavailable (doesn't block trading)
- **Caching:** Reduces API calls with configurable TTL
- **WebUI Integration:** Full configuration and monitoring interface

### Trading Logic

**LONG Mode:**
- **STOP Signal:** When RSI >= `long_threshold` (default: 75.0) - Market overbought
- **GO Signal:** When RSI < `long_threshold` - Market healthy for long positions

**SHORT Mode:**
- **STOP Signal:** When RSI <= `short_threshold` (default: 25.0) - Market oversold
- **GO Signal:** When RSI > `short_threshold` - Market healthy for short positions

**Hysteresis:**
- When RSI is exactly at the threshold, a configurable delay (default: 60s) prevents rapid signal switching
- Maintains current signal (GO or STOP) for the hysteresis period even if RSI briefly crosses back

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Guardian Bot (Layer 6)                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐        │
│  │  RSICollector    │─────────►│ RiskDecisionEngine│        │
│  │  (Data Source)   │  RSI     │  (Layer 6 Check) │        │
│  └──────────────────┘  Value   └──────────────────┘        │
│         │                              │                    │
│         │                              │                    │
│         ▼                              ▼                    │
│  ┌──────────────────┐         ┌──────────────────┐        │
│  │ Delta Exchange   │         │  EventStore       │        │
│  │ /v2/history/     │         │  (GO/STOP Signals)│        │
│  │ candles          │         └──────────────────┘        │
│  └──────────────────┘                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Trading Bot     │
                    │  (Reads Signals) │
                    └──────────────────┘
```

### Component Responsibilities

1. **RSICollector** (`bot/guardian/collectors/rsi_collector.py`)
   - Fetches hourly OHLCV candles from Delta Exchange
   - Calculates RSI using standard formula
   - Implements caching to reduce API calls
   - Manages hysteresis state
   - Returns RSI value or None (fail-safe)

2. **RiskDecisionEngine** (`bot/guardian/engine/risk_decision_engine.py`)
   - Integrates RSI check as Layer 6
   - Calls `rsi_collector.should_stop_trading()`
   - Publishes GO/STOP signals to EventStore
   - Includes RSI details in signal logs

3. **GuardianBot** (`bot/guardian/core/guardian_bot.py`)
   - Initializes RSICollector
   - Injects collector into RiskDecisionEngine
   - Manages component lifecycle

4. **WebUI Backend** (`webui/backend/routes/guardian.py`)
   - Provides `/api/guardian/rsi/status` endpoint
   - Fetches RSI directly from collector
   - Returns current RSI, status, and configuration

5. **WebUI Frontend** (`webui/frontend/src/components/RSIPanel.js`)
   - Displays current RSI value and status
   - Configuration interface for all RSI parameters
   - Real-time updates every 30 seconds

---

## Configuration

### Configuration File: `config.yaml`

```yaml
safety:
  rsi:
    enabled: true                    # Enable/disable RSI monitoring
    period: 14                       # RSI calculation period (2-50)
    long_threshold: 75.0             # STOP when RSI >= this in LONG mode (50-100)
    short_threshold: 25.0            # STOP when RSI <= this in SHORT mode (0-50)
    timeframe: "1h"                  # OHLCV timeframe (1h, 4h, 1d)
    check_interval: 300              # How often to check RSI (seconds, min: 60)
    cache_ttl: 60                    # RSI cache TTL (seconds, min: 10)
    hysteresis_seconds: 60           # Hysteresis delay at threshold (seconds, min: 0)
```

### Configuration Model: `config/models.py`

```python
class RSIConfig(BaseModel):
    """RSI-based trading safety (Layer 6)"""
    enabled: bool = Field(True, description="Enable RSI monitoring")
    period: int = Field(14, ge=2, le=50, description="RSI calculation period")
    long_threshold: float = Field(75.0, ge=50, le=100, description="RSI overbought threshold for LONG mode (STOP if RSI >= this)")
    short_threshold: float = Field(25.0, ge=0, le=50, description="RSI oversold threshold for SHORT mode (STOP if RSI <= this)")
    timeframe: str = Field("1h", description="OHLCV timeframe for RSI calculation")
    check_interval: int = Field(300, ge=60, description="RSI check interval in seconds")
    cache_ttl: int = Field(60, ge=10, description="RSI cache TTL in seconds")
    hysteresis_seconds: int = Field(60, ge=0, description="Time in seconds to maintain signal when RSI is exactly at threshold")
```

### Default Values

- **Period:** 14 (standard RSI period)
- **LONG Threshold:** 75.0 (overbought)
- **SHORT Threshold:** 25.0 (oversold)
- **Timeframe:** 1h (hourly candles)
- **Check Interval:** 300s (5 minutes)
- **Cache TTL:** 60s (1 minute)
- **Hysteresis:** 60s (1 minute delay at threshold)

---

## Implementation Details

### 1. RSI Collector (`bot/guardian/collectors/rsi_collector.py`)

#### Initialization

```python
class RSICollector:
    def __init__(self, exchange, config):
        # Extract configuration
        self.api_base = config.api.live.base_url  # Delta Exchange API
        self.symbol = config.bot.symbol            # Trading symbol (e.g., BTCUSD)
        self.bot_mode = config.bot.mode.upper()    # LONG or SHORT
        
        # RSI configuration
        rsi_config = config.safety.rsi
        self.period = rsi_config.period
        self.timeframe = rsi_config.timeframe
        self.long_threshold = rsi_config.long_threshold
        self.short_threshold = rsi_config.short_threshold
        self.hysteresis_seconds = rsi_config.hysteresis_seconds
        self.cache_ttl = rsi_config.cache_ttl
        
        # Cache and state
        self._cached_rsi = None
        self._cache_timestamp = 0
        self._current_signal = None  # 'GO' or 'STOP'
        self._hysteresis_start_time = None
```

#### RSI Calculation

**Formula:**
1. Fetch hourly OHLCV candles from Delta Exchange
2. Extract close prices
3. Calculate price changes: `change = close[i] - close[i-1]`
4. Separate gains and losses:
   - `gain = max(change, 0)`
   - `loss = max(-change, 0)`
5. Calculate average gain/loss over period:
   - `avg_gain = sum(gains) / period`
   - `avg_loss = sum(losses) / period`
6. Calculate RS (Relative Strength):
   - `RS = avg_gain / avg_loss` (if avg_loss > 0)
7. Calculate RSI:
   - `RSI = 100 - (100 / (1 + RS))`

**Implementation:**
```python
def _calculate_rsi(self, prices: list, period: int) -> float:
    """Calculate RSI from price list"""
    if len(prices) < period + 1:
        return None
    
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0  # All gains, no losses
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi
```

#### Hysteresis Logic

```python
def should_stop_trading(self) -> bool:
    """Determine if trading should stop based on RSI, mode, and hysteresis"""
    rsi = self.get_latest_rsi()
    
    if rsi is None:
        return False  # Fail-safe: assume healthy if unavailable
    
    threshold = self.long_threshold if self.bot_mode == 'LONG' else self.short_threshold
    current_time = time.time()
    
    # Determine desired signal based on RSI
    if self.bot_mode == 'LONG':
        desired_signal = 'STOP' if rsi >= threshold else 'GO'
    else:  # SHORT mode
        desired_signal = 'STOP' if rsi <= threshold else 'GO'
    
    # Check if RSI is exactly at threshold
    at_threshold = (
        (self.bot_mode == 'LONG' and rsi == threshold) or
        (self.bot_mode == 'SHORT' and rsi == threshold)
    )
    
    # Hysteresis logic
    if at_threshold:
        if self._hysteresis_start_time is None:
            self._hysteresis_start_time = current_time
        
        # Maintain current signal during hysteresis period
        if (current_time - self._hysteresis_start_time) < self.hysteresis_seconds:
            return self._current_signal == 'STOP'
        else:
            # Hysteresis period expired, apply new signal
            self._current_signal = desired_signal
            self._hysteresis_start_time = None
            return desired_signal == 'STOP'
    else:
        # Not at threshold, apply signal immediately
        self._hysteresis_start_time = None
        self._current_signal = desired_signal
        return desired_signal == 'STOP'
```

### 2. Risk Decision Engine Integration

**Location:** `bot/guardian/engine/risk_decision_engine.py`

**Layer 6 Check:**
```python
def _generate_signal(self) -> Event:
    # ... other layer checks ...
    
    # Check 6: RSI overbought/oversold based on mode?
    if self._is_rsi_overbought_or_oversold():
        return self._make_stop_signal(
            reason=f"RSI {'overbought' if self.config.bot.mode == 'LONG' else 'oversold'} - market too risky",
            details=self._get_rsi_details()
        )
    
    # All checks passed
    return self._make_go_signal(details=self._get_rsi_details())
```

**RSI Check Method:**
```python
def _is_rsi_overbought_or_oversold(self) -> bool:
    """Check if RSI indicates overbought (LONG) or oversold (SHORT) conditions"""
    if not self.rsi_collector:
        return False  # Fail-safe: assume healthy if collector unavailable
    
    return self.rsi_collector.should_stop_trading()
```

**RSI Details:**
```python
def _get_rsi_details(self) -> Dict:
    """Get RSI monitoring details for logging"""
    if not self.rsi_collector:
        return {"rsi": None, "status": "UNAVAILABLE"}
    
    rsi = self.rsi_collector.get_latest_rsi()
    should_stop = self.rsi_collector.should_stop_trading()
    
    rsi_config = self.config.safety.rsi if self.config.safety and hasattr(self.config.safety, 'rsi') else None
    
    return {
        "rsi": rsi,
        "status": "STOP" if should_stop else "GO",
        "bot_mode": self.config.bot.mode,
        "long_threshold": rsi_config.long_threshold if rsi_config else 75.0,
        "short_threshold": rsi_config.short_threshold if rsi_config else 25.0,
        "period": rsi_config.period if rsi_config else 14,
        "timeframe": rsi_config.timeframe if rsi_config else "1h",
        "hysteresis_active": self.rsi_collector._hysteresis_start_time is not None,
        "hysteresis_seconds": rsi_config.hysteresis_seconds if rsi_config else 60
    }
```

### 3. Guardian Bot Integration

**Location:** `bot/guardian/core/guardian_bot.py`

**Initialization:**
```python
def initialize_components(self):
    # ... other collectors ...
    
    # Initialize RSI collector
    from bot.guardian.collectors.rsi_collector import RSICollector
    self.rsi_collector = RSICollector(self.exchange, self.config)
    
    # Inject into risk engine
    self.risk_engine.set_components(
        # ... other components ...
        rsi_collector=self.rsi_collector
    )
```

---

## Data Flow

### 1. RSI Data Collection Flow

```
1. Guardian Bot starts
   ↓
2. RSICollector initialized with config
   ↓
3. RiskDecisionEngine calls rsi_collector.get_latest_rsi()
   ↓
4. RSICollector checks cache (TTL: 60s)
   ↓
5. If cache expired:
   a. Fetch OHLCV candles from Delta Exchange
   b. Extract close prices
   c. Calculate RSI using standard formula
   d. Cache result
   ↓
6. Return RSI value (or None if unavailable)
```

### 2. Signal Generation Flow

```
1. RiskDecisionEngine._generate_signal() called
   ↓
2. Check Layer 1-5 (volatility, loss limits, position size, liquidation, health)
   ↓
3. Check Layer 6: rsi_collector.should_stop_trading()
   ↓
4. If RSI indicates STOP:
   - Determine reason (overbought/oversold)
   - Get RSI details
   - Create STOP signal with RSI information
   ↓
5. If all layers pass:
   - Create GO signal with RSI information
   ↓
6. Write signal to EventStore (SQL database)
   ↓
7. Trading bot reads signal from EventStore
```

### 3. WebUI Data Flow

```
1. User opens RSI panel in WebUI
   ↓
2. Frontend calls GET /api/guardian/rsi/status
   ↓
3. Backend creates RSICollector instance
   ↓
4. Fetches current RSI value
   ↓
5. Returns JSON response:
   {
     "success": true,
     "data": {
       "rsi": 63.84,
       "status": "GO",
       "status_text": "Trading allowed",
       "bot_mode": "LONG",
       "long_threshold": 75.0,
       "short_threshold": 25.0,
       "hysteresis_active": false,
       "hysteresis_seconds": 60,
       "should_stop": false,
       "timestamp": 1766837477.15
     }
   }
   ↓
6. Frontend displays RSI value and status
   ↓
7. Auto-refresh every 30 seconds
```

---

## API Endpoints

### GET `/api/guardian/rsi/status`

**Purpose:** Get current RSI value and status

**Response:**
```json
{
  "success": true,
  "data": {
    "rsi": 63.84,
    "status": "GO",
    "status_text": "Trading allowed",
    "bot_mode": "LONG",
    "long_threshold": 75.0,
    "short_threshold": 25.0,
    "hysteresis_active": false,
    "hysteresis_seconds": 60,
    "should_stop": false,
    "timestamp": 1766837477.15
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Error message",
  "traceback": "..."
}
```

**Implementation:** `webui/backend/routes/guardian.py`

---

## WebUI Integration

### Frontend Component

**Location:** `webui/frontend/src/components/RSIPanel.js`

**Features:**
- Current RSI value display (color-coded chip)
- Trading status (GO/STOP with icon)
- Bot mode display
- Threshold display (mode-specific)
- Configuration sliders:
  - RSI Period (2-50)
  - LONG Threshold (50-100)
  - SHORT Threshold (0-50)
  - Hysteresis Delay (0-300s)
  - Timeframe selector (1h, 4h, 1d)
  - Check Interval
- Enable/Disable toggle
- Save configuration button
- Real-time updates (30s interval)
- Refresh button

### Navigation Integration

**Location:** `webui/frontend/src/App.js`

**Section Definition:**
```javascript
{
  id: 'rsi',
  label: 'RSI',
  icon: BarChart3,
  description: 'RSI safety monitor - mode-specific thresholds with hysteresis'
}
```

**Render Function:**
```javascript
const renderRSI = () => (
  <div className="grid gap-6">
    <CollapsibleCard
      id="rsi-panel"
      title="📊 RSI Safety Monitor (Layer 6)"
      subtitle="Mode-specific RSI thresholds with hysteresis protection"
      accent="purple"
      defaultOpen={!isMobile}
    >
      <Suspense fallback={<LoadingFallback message="Loading RSI monitor..." />}>
        <EnhancedErrorBoundary componentName="RSIPanel">
          <RSIPanel />
        </EnhancedErrorBoundary>
      </Suspense>
    </CollapsibleCard>
  </div>
);
```

### Configuration Update

**API Endpoint:** `POST /api/config/update`

**Request Format:**
```json
{
  "updates": {
    "safety.rsi.enabled": true,
    "safety.rsi.period": 14,
    "safety.rsi.long_threshold": 75.0,
    "safety.rsi.short_threshold": 25.0,
    "safety.rsi.hysteresis_seconds": 60,
    "safety.rsi.timeframe": "1h",
    "safety.rsi.check_interval": 300,
    "safety.rsi.cache_ttl": 60
  }
}
```

---

## Testing & Validation

### Manual Testing

1. **Test RSI Calculation:**
   ```bash
   python3 -c "
   from config.loader import get_config
   import ccxt
   from bot.guardian.collectors.rsi_collector import RSICollector
   
   config = get_config()
   exchange = ccxt.delta({'enableRateLimit': True})
   collector = RSICollector(exchange, config)
   rsi = collector.get_latest_rsi()
   print(f'RSI: {rsi}')
   "
   ```

2. **Test API Endpoint:**
   ```bash
   curl http://localhost:5555/api/guardian/rsi/status | python3 -m json.tool
   ```

3. **Test STOP Signal (LONG mode):**
   - Set `long_threshold: 50.0` in config.yaml
   - If RSI > 50, Guardian should publish STOP signal
   - Verify in EventStore: `bot_events_LONG.db`

4. **Test STOP Signal (SHORT mode):**
   - Set `short_threshold: 50.0` in config.yaml
   - Switch bot to SHORT mode
   - If RSI < 50, Guardian should publish STOP signal

5. **Test Hysteresis:**
   - Set RSI threshold to current RSI value
   - Verify signal doesn't change for `hysteresis_seconds`
   - After delay, signal should update

### Expected Behavior

- **RSI Available:** Returns float value (0-100)
- **RSI Unavailable:** Returns None (fail-safe, doesn't block trading)
- **LONG Mode + RSI >= 75:** STOP signal
- **LONG Mode + RSI < 75:** GO signal
- **SHORT Mode + RSI <= 25:** STOP signal
- **SHORT Mode + RSI > 25:** GO signal
- **At Threshold:** Hysteresis delay applies

---

## Troubleshooting

### Issue: RSI shows "N/A" in WebUI

**Possible Causes:**
1. Delta Exchange API unavailable
2. Network connectivity issues
3. Invalid symbol configuration
4. Insufficient candle data

**Solutions:**
1. Check Delta Exchange API status
2. Verify network connectivity
3. Verify `config.bot.symbol` is correct
4. Check backend logs: `webui/backend/logs/backend_fixed.log`
5. Test collector directly (see Testing section)

### Issue: RSI not updating

**Possible Causes:**
1. Cache TTL too long
2. Check interval too long
3. API rate limiting

**Solutions:**
1. Reduce `cache_ttl` in config.yaml
2. Reduce `check_interval` in config.yaml
3. Check API rate limits

### Issue: STOP signal not triggering

**Possible Causes:**
1. RSI not reaching threshold
2. Hysteresis delay active
3. RSI collector disabled
4. Other layer blocking (check all 6 layers)

**Solutions:**
1. Verify current RSI value
2. Check if at threshold (hysteresis applies)
3. Verify `safety.rsi.enabled: true`
4. Check Guardian logs for all layer status

### Issue: WebUI panel not visible

**Possible Causes:**
1. Frontend not rebuilt
2. Backend not restarted
3. Browser cache

**Solutions:**
1. Rebuild frontend: `cd webui/frontend && npm run build`
2. Restart backend
3. Hard refresh browser: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)

---

## File Reference

### Backend Files

- `bot/guardian/collectors/rsi_collector.py` - RSI data collection and calculation
- `bot/guardian/engine/risk_decision_engine.py` - Layer 6 integration
- `bot/guardian/core/guardian_bot.py` - Component initialization
- `webui/backend/routes/guardian.py` - API endpoint (`/api/guardian/rsi/status`)

### Frontend Files

- `webui/frontend/src/components/RSIPanel.js` - RSI panel component
- `webui/frontend/src/App.js` - Navigation integration

### Configuration Files

- `config.yaml` - RSI configuration section
- `config/models.py` - `RSIConfig` Pydantic model

### Documentation Files

- `GUARDIAN_6_LAYER_SECURITY_IMPLEMENTATION.md` - Overall guardian system
- `RSI_Layer6.md` - This file

---

## Related Features

- **Layer 1:** Volatility Safety
- **Layer 2:** Loss Limits
- **Layer 3:** Position Size Limits
- **Layer 4:** Liquidation Distance
- **Layer 5:** System Health Monitoring
- **Layer 6:** RSI Safety (this feature)

---

## Version History

- **v1.1** (December 27, 2025): Senior Developer Review & Improvements
  - ✅ FIXED: RSI calculation now uses Wilder's smoothing method (industry standard)
  - ✅ FIXED: Hysteresis logic uses range (±2 points) instead of exact threshold
  - ✅ ADDED: Input validation for candle data
  - ✅ ADDED: Retry logic with exponential backoff (3 retries)
  - ✅ ADDED: Configuration validation
  - ✅ ADDED: Signal change tracking (last 50 changes)
  - ✅ ADDED: Rate-limited logging
  - ✅ ADDED: Comprehensive status method for debugging
  - ✅ ADDED: Unit tests (19 tests, 100% passing)
  - See: RSI_LAYER6_SENIOR_REVIEW.md for complete review

- **v1.0** (December 2025): Initial implementation (Junior Developer)
  - Basic RSI calculation from Delta Exchange
  - Mode-specific thresholds
  - Hysteresis protection
  - WebUI integration

---

**Last Updated:** December 27, 2025  
**Maintained By:** WorkingBot Development Team  
**Status:** ✅ Production Ready









