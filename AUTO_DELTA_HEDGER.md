# Auto-Delta Hedger Feature Documentation

> **For AI Context**: This document explains the Auto-Delta Hedger component - an institutional-grade automatic delta hedging system from quantconnect-lean-study.

---

## Feature Overview

The **Auto-Delta Hedger** is a continuous portfolio management system that:
1. Monitors portfolio Greeks (Delta, Gamma, Vega, Theta) every 10 seconds
2. Detects when portfolio Delta exceeds configured threshold
3. Automatically hedges by placing opposite BTC perpetual positions
4. Logs all hedge executions for analysis
5. Maintains delta-neutral portfolio exposure

---

## Architecture

### State Management

```javascript
// Primary state in AutoDeltaHedger.js
const [enabled, setEnabled] = useState(false);
const [deltaThreshold, setDeltaThreshold] = useState(5); // BTC units
const [greeks, setGreeks] = useState({
  delta: 0,
  gamma: 0,
  vega: 0,
  theta: 0,
  lastUpdated: null,
});
const [hedgeHistory, setHedgeHistory] = useState([]);
const [status, setStatus] = useState('idle'); // idle, monitoring, hedging
const [stats, setStats] = useState({
  totalHedges: 0,
  avgDeltaBeforeHedge: 0,
  lastHedgeTime: null,
});
```

### Monitoring Loop

```javascript
// Runs every 10 seconds when enabled
const monitoringLoop = useCallback(async () => {
  await fetchGreeks();
  
  const currentDelta = greeks.delta;
  if (Math.abs(currentDelta) > deltaThreshold) {
    console.log(`[AUTO-HEDGE] Delta ${currentDelta} exceeds threshold ${deltaThreshold}`);
    await executeHedge(currentDelta);
  }
}, [fetchGreeks, greeks.delta, deltaThreshold, executeHedge]);
```

---

## User Flow

### 1. Configuration Phase
```
User configures:
  - Delta Threshold (default: 5 BTC)
  - Enable/Disable toggle
```

### 2. Monitoring Phase
```
System polls every 10 seconds:
    ↓
Fetch portfolio Greeks from /api/experimental/greeks
    ↓
Check: |Delta| > Threshold?
    ↓
If YES → Execute hedge
If NO → Continue monitoring
```

### 3. Hedging Phase
```
Calculate hedge size (opposite of current delta)
    ↓
POST to /api/experimental/hedge
    ↓
Log hedge in history
    ↓
Update statistics
    ↓
Resume monitoring
```

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/experimental/greeks` | GET | Fetch portfolio Greeks |
| `/api/experimental/hedge` | POST | Execute delta hedge |

### Greeks Response Format
```json
{
  "success": true,
  "greeks": {
    "delta": -3.45,
    "gamma": 0.12,
    "vega": 15.67,
    "theta": -0.89
  }
}
```

### Hedge Request Format
```json
{
  "delta": -3.45,
  "threshold": 5
}
```

### Hedge Response Format
```json
{
  "success": true,
  "hedge": {
    "timestamp": 1706500000000,
    "deltaBefore": -3.45,
    "hedgeSize": 3.45,
    "price": 105000.00,
    "status": "success"
  }
}
```

---

## UI Components

### Status Chip
```
┌─────────────────────────────────────┐
│ [IDLE]     - Grey, not active       │
│ [MONITORING] - Green, watching      │
│ [HEDGING]  - Yellow, executing      │
└─────────────────────────────────────┘
```

### Greeks Display
```
┌──────────┬──────────┬──────────┬──────────┐
│  Delta   │  Gamma   │   Vega   │  Theta   │
│  -3.45   │   0.12   │  15.67   │  -0.89   │
│ (colored)│          │          │          │
└──────────┴──────────┴──────────┴──────────┘
```

### Delta Color Coding
| Condition | Color |
|-----------|-------|
| `|Delta| > threshold * 1.5` | Red (Error) |
| `|Delta| > threshold` | Yellow (Warning) |
| `|Delta| <= threshold` | Green (Success) |

### Hedge History Table
```
┌──────────┬───────────────┬─────────────┬──────────┬────────┐
│   Time   │ Delta Before  │ Hedge Size  │  Price   │ Status │
├──────────┼───────────────┼─────────────┼──────────┼────────┤
│ 14:30:05 │    ↑ -5.23    │ 5.2300 BTC  │$105,000  │ success│
│ 14:20:15 │    ↓  6.78    │ 6.7800 BTC  │$104,850  │ success│
└──────────┴───────────────┴─────────────┴──────────┴────────┘
```

---

## Configuration Options

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| Delta Threshold | 5 BTC | 0.1 - 100 | Hedge when `|Delta|` exceeds this |
| Polling Interval | 10 sec | Fixed | Time between Greeks checks |
| History Limit | 20 | Fixed | Max hedge history entries |

---

## Status States

| Status | Description |
|--------|-------------|
| `idle` | Auto-hedging disabled, not monitoring |
| `monitoring` | Actively polling Greeks, watching for threshold breach |
| `hedging` | Currently executing a hedge trade |

---

## Features

### Manual Hedge
When disabled, user can click "Manual Hedge Now" to:
- Execute immediate hedge based on current delta
- Does not require threshold breach
- Useful for ad-hoc portfolio adjustment

### Manual Refresh
- Refresh Greeks on demand
- Available via refresh button next to "Last updated"

### Statistics Tracking
- Total number of hedges executed
- Average delta before hedge
- Time of last hedge

---

## Integration Points

### Backend Routes
- `/api/experimental/greeks` → `routes/experimental/greeks.py`
- `/api/experimental/hedge` → `routes/experimental/hedge.py`

### Related Components
- `OptionsPanel.js` - Main options trading interface
- `ExperimentalDashboard.js` - Container for experimental features
- `KellyPositionSizer.js` - Another institutional tool

---

## Error Handling

| Error Type | Handling |
|------------|----------|
| Greeks fetch fails | Show error alert, continue monitoring |
| Hedge execution fails | Show error alert, return to monitoring |
| Network error | Log error, retry on next interval |

---

## Future Improvements

1. **Gamma Hedging**: Adjust for gamma exposure changes
2. **Vega Hedging**: Hedge volatility exposure with VIX futures
3. **Time-Based Scheduling**: Only hedge during specific hours
4. **Size Limits**: Max hedge size per execution
5. **Hedge Confirmation**: Require user approval above certain size
6. **Multi-Asset Hedging**: Hedge with ETH or other assets

---

## Related Files

| File | Purpose |
|------|---------|
| `AutoDeltaHedger.js` | Frontend component |
| `routes/experimental/greeks.py` | Greeks calculation endpoint |
| `routes/experimental/hedge.py` | Hedge execution endpoint |
| `utils/greeks_calculator.py` | Greeks calculation logic |

---

## Glossary

| Term | Definition |
|------|------------|
| **Delta** | Rate of change of option price with underlying |
| **Gamma** | Rate of change of delta with underlying |
| **Vega** | Sensitivity to implied volatility |
| **Theta** | Time decay of option value |
| **Delta-Neutral** | Portfolio where delta ≈ 0 |
| **Hedge** | Trade to offset portfolio risk |
| **BTC Perp** | Bitcoin perpetual futures contract |
