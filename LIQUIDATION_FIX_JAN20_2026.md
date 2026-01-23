# Liquidation Protection System - Delta Exchange API Fix
## January 20, 2026

---

## ✅ CHANGES IMPLEMENTED

### Backend (`webui/backend/routes/liquidation.py`)

#### 1. **FIXED: Liquidation Distance Formula** ❌ → ✅

**OLD (WRONG):**
```python
liquidation_distance = ((available_balance / maintenance_margin) - 1) × 100
```

**NEW (CORRECT - Delta Exchange Official):**
```python
liquidation_distance = ((balance - mm_w_ucf) / mm_w_ucf) × 100
```

Where:
- `balance` = Total wallet balance (from `/v2/wallet/balances`)
- `mm_w_ucf` = Maintenance Margin with Unrealized Cashflows (from WebSocket `portfolio_margins` channel)

---

#### 2. **FIXED: Margin Utilization Formula** ❌ → ✅

**OLD (WRONG):**
```python
utilization = ((balance - available_balance) / balance) × 100
```

**NEW (CORRECT - Delta Exchange Official):**
```python
utilization = (im_w_ucf / balance) × 100
```

Where:
- `im_w_ucf` = Initial Margin with Unrealized Cashflows (from WebSocket `portfolio_margins`)
- `balance` = Total wallet balance

---

#### 3. **ADDED: WebSocket portfolio_margins Data Support** 🆕

The system now checks for WebSocket data in `.guardian_health` file:
- `im_w_ucf` - Initial Margin (used for margin utilization)
- `mm_w_ucf` - Maintenance Margin (used for liquidation distance)
- `positions_upl` - ⭐ **Official Unrealized PnL from Delta Exchange**
- `liquidation_risk` - Boolean flag from Delta Exchange
- `under_liquidation` - Active liquidation status
- `margin_shortfall` - Exact top-up amount needed

---

#### 4. **UPDATED: Risk Zone Thresholds** 🎯

**NEW Delta Exchange Recommended Thresholds:**

| Zone | Liquidation Distance | Status |
|------|---------------------|--------|
| 🔴 CRITICAL | < 5% OR `under_liquidation=true` | Close positions NOW |
| 🟠 DANGER | < 20% OR `liquidation_risk=true` | High risk - reduce |
| 🟡 WARNING | < 50% | Caution - monitor |
| 🟢 SAFE | ≥ 50% | Can open positions |

**Margin Utilization Thresholds:**

| Zone | Utilization | Can Open Positions? |
|------|-------------|---------------------|
| 🔴 RED | ≥ 100% IM | ❌ No (liquidation imminent) |
| 🟠 ORANGE | ≥ 80% IM | ❌ No (Delta blocks new orders) |
| 🟡 YELLOW | ≥ 60% IM | ✅ Yes (caution) |
| 🟢 GREEN | < 60% IM | ✅ Yes (safe) |

---

#### 5. **IMPROVED: Unrealized PnL Source Priority** 📊

**Priority Order:**
1. ✅ **PRIMARY**: WebSocket `positions_upl` (most accurate)
2. ⚠️ **FALLBACK**: Manual calculation from `/v2/positions/margined`

---

### Frontend (`webui/frontend/src/components/LiquidationProtectionPanel.js`)

#### 1. **Updated Formula Display**
- Shows: `((Balance - MM) / MM) × 100`
- Label: "Delta Exchange (Portfolio Margin Mode)"

#### 2. **Added Delta Exchange Risk Indicators** 🆕
- ⚠️ API LIQUIDATION RISK FLAG (when `api_liquidation_risk=true`)
- 🚨 UNDER LIQUIDATION (when `under_liquidation=true`)
- Top-up amount display (when `margin_shortfall` > 0)

---

## 🔧 NEXT STEPS: WebSocket Integration (Optional but Recommended)

To get **real-time 2-second updates** instead of 30-60 second polling:

### Option A: Enable Existing WebSocket (If Available)

Check if `bot/liquidation/delta_realtime_websocket.py` is running:

```bash
# Check if WebSocket is active
ps aux | grep delta_realtime_websocket
```

If running, it should write to `.guardian_health` with:
```json
{
  "portfolio_margins": {
    "im_w_ucf": 2.065,
    "mm_w_ucf": 1.642,
    "positions_upl": 0.05,
    "liquidation_risk": false,
    "under_liquidation": false,
    "margin_shortfall": 0
  }
}
```

### Option B: Set Up WebSocket Manually

The WebSocket client exists at `bot/liquidation/delta_realtime_websocket.py`.

**To integrate:**
1. Import and initialize in Guardian bot:
```python
from bot.liquidation.delta_realtime_websocket import DeltaRealtimeWebSocket

ws = DeltaRealtimeWebSocket(
    api_key=os.getenv('DELTA_API_KEY'),
    api_secret=os.getenv('DELTA_API_SECRET'),
    base_url='wss://socket.india.delta.exchange'
)

ws.connect()
```

2. Subscribe to `portfolio_margins` channel
3. Write data to `.guardian_health` file every 2 seconds

---

## 📋 VERIFICATION CHECKLIST

After restarting backend and frontend:

### ✅ Check 1: Correct Formulas in Logs
```bash
tail -f webui/backend/app.log | grep "DELTA EXCHANGE FORMULA"
```

Should see:
```
✅ DELTA EXCHANGE FORMULA: Liquidation Distance = ((₹X - ₹Y) / ₹Y) × 100 = Z%
```

### ✅ Check 2: WebSocket Data (if available)
```bash
cat .guardian_health | jq '.portfolio_margins'
```

Should show:
```json
{
  "im_w_ucf": ...,
  "mm_w_ucf": ...,
  "positions_upl": ...
}
```

### ✅ Check 3: Frontend Display
- Formula shows: `((Balance - MM) / MM) × 100`
- Label shows: "Delta Exchange (Portfolio Margin Mode)"
- Risk indicators appear when relevant

---

## 🚨 IMPORTANT NOTES

### About Portfolio Margin Mode
- **Individual position liquidation prices are NULL** - This is CORRECT
- **Liquidation is portfolio-wide** - Based on total margin, not per-position
- **The margin-based formula is correct** for this mode
- **Price-based formulas only work** in Cross/Isolated Margin modes

### Data Source Priority
1. **WebSocket** `portfolio_margins` - Real-time (2s updates) ⭐ BEST
2. **Guardian** `.guardian_health` file - Written by WebSocket
3. **REST API** `/v2/wallet/balances` - Fallback (30-60s polling)

### Rate Limits
- REST API: 10,000 units per 5 minutes
- `/v2/wallet/balances`: 3 units per call
- **Recommendation**: Use WebSocket for real-time data, REST as backup

---

## 📊 EXPECTED RESULTS

### Before Fix (WRONG)
```
Margin Utilization: 5.0% (demo/placeholder)
Liquidation Distance: 282.9% (wrong formula)
Formula: ((Available / MM) - 1) × 100
```

### After Fix (CORRECT)
```
Margin Utilization: [Real value from IM/Balance]%
Liquidation Distance: [Real value from (Balance-MM)/MM]%
Formula: ((Balance - MM) / MM) × 100
Delta Exchange (Portfolio Margin Mode)
```

---

## 🔄 RESTART INSTRUCTIONS

**Per `backend_frontend.md`:**

1. **Backend:**
```bash
cd /Users/ssr/Projects/WorkingBot/webui/backend
pkill -f "python app.py"
nohup python app.py > app.log 2>&1 &
```

2. **Frontend:**
```bash
cd /Users/ssr/Projects/WorkingBot/webui/frontend
pkill -f "npm start"
nohup npm start > frontend.log 2>&1 &
```

3. **Verify:**
```bash
# Check backend
curl http://localhost:5001/api/liquidation/status | jq '.distance'

# Check frontend
open http://localhost:3000
```

---

## 📚 REFERENCES

- Delta Exchange API Docs: https://docs.delta.exchange/
- Portfolio Margin Guide: https://guides.delta.exchange/delta-exchange-user-guide/trading-guide/margin-explainer/portfolio-margin
- WebSocket API: wss://socket.india.delta.exchange
- REST API Base: https://api.india.delta.exchange

---

## ✅ SUMMARY

**Fixed Issues:**
1. ❌ Wrong liquidation distance formula → ✅ Correct Delta Exchange formula
2. ❌ Wrong margin utilization formula → ✅ Uses Initial Margin (IM)
3. ❌ Missing WebSocket data support → ✅ Reads from `.guardian_health`
4. ❌ Wrong risk thresholds → ✅ Delta Exchange recommended values
5. ❌ Manual PnL calculation → ✅ Priority on `positions_upl`

**What's Still Working:**
- All existing functionality preserved
- Backward compatibility maintained
- Fallback to REST API when WebSocket unavailable
- No breaking changes to trading logic

**Next Enhancement (Optional):**
- Set up WebSocket `portfolio_margins` channel for 2-second real-time updates
- Eliminates REST API polling
- More accurate and faster risk detection
