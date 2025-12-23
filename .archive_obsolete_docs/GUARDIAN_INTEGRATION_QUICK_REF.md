# 🛡️ Guardian Bot Integration - Quick Reference

**Date**: November 17, 2025  
**Status**: ✅ All Systems Integrated with New Architecture  

## 📋 Quick Answers to Your Questions

### 1️⃣ WebSocket & REST API ✅

**Current Setup**: REST API (CCXT) - Primary Method

- **Guardian uses**: `ccxt.delta()` for all exchange communication
- **Connection**: REST API with built-in rate limiting (100ms)
- **Fallback**: CCXT handles retries automatically + Circuit breaker wrapping
- **No WebSocket** currently in Guardian (uses polling every 10s - sufficient for monitoring)

**Code Location**: 
- `bot/guardian/core/guardian_bot.py` (line 202-217): Exchange setup
- `bot/guardian/collectors/position_monitor.py` (line 44): Position fetching

---

### 2️⃣ Guardian Log Viewing Commands 📋

```bash
# Real-time log tailing
tail -f bot/logs/guardian.log

# Last 100 lines
tail -100 bot/logs/guardian.log

# Follow with less (press Ctrl+C to stop, 'q' to quit)
less +F bot/logs/guardian.log

# Filter for important events
tail -f bot/logs/guardian.log | grep "STOP\|GO\|ERROR"

# View health status (pretty JSON)
cat .guardian_health | jq .

# Monitor Guardian signals from SQL database
sqlite3 gridbot_events.db "SELECT * FROM events WHERE event_type LIKE 'guardian_%' ORDER BY timestamp DESC LIMIT 20"

# Watch signals live (auto-refresh every 2s)
watch -n 2 "sqlite3 gridbot_events.db 'SELECT event_type, timestamp, json_extract(data, \"$.signal\") as signal FROM events WHERE event_type IN (\"guardian_signal_go\", \"guardian_signal_stop\") ORDER BY timestamp DESC LIMIT 5'"
```

**Log Files**:
- `bot/logs/guardian.log` - Main log file
- `.guardian_health` - JSON health snapshot (root directory)
- `bot/reports/guardian_health.json` - Backup health file

---

### 3️⃣ Volatility Regime Integration ✅

**Data Flow**:
```
DeltaVolatilityCollector (polls API every 30s)
    ↓ Calculates IV/RV/Spread
    ↓ Stores in data/volatility.db
Guardian Bot (injects collector into risk engine)
    ↓ 
risk_decision_engine.py (reads volatility)
    ↓ Checks thresholds
    ↓ Publishes GO/STOP to SQL
WebUI (displays Volatility Regime chart)
```

**Code Evidence**:
- `bot/guardian/core/guardian_bot.py` (line 284-288): Volatility collector injection
- `bot/guardian/engine/risk_decision_engine.py` (line 254-270): Volatility threshold checking
- `bot/volatility/delta_volatility_collector.py`: Data collection

**Your WebUI Shows**:
- ✅ IV: 50.41%
- ✅ RV: 48.85%
- ✅ Spread: +1.56%
- ✅ Historical chart working

---

### 4️⃣ WebUI Safety Systems Integration ✅

**All Connected to Guardian**:

| WebUI Tab | Guardian Component | Status |
|-----------|-------------------|--------|
| **Capital Protection** | risk_decision_engine.py → loss limits | ✅ Active |
| **Liquidation Monitor** | IntegratedLiquidationMonitor | ✅ Monitoring |
| **Risk Intelligence** | Error logging + circuit breaker | ✅ No errors |
| **Guardian & Robustness** | .guardian_health → /api/guardian/status | ✅ Online |
| **Open Positions** | position_monitor.py → fetch_positions() | ✅ 4 positions |

**Backend Routes**:
- `webui/backend/routes/guardian.py` → `/api/guardian/status`
- `webui/backend/routes/capital.py` → Reads `.guardian_health`
- `webui/backend/routes/risk.py` → Reads `.guardian_health`
- `webui/backend/routes/monitoring.py` → Reads Guardian data

**Health File Flow**:
```
Guardian Bot (writes every 10s)
    ↓
.guardian_health (root directory)
    ↓
WebUI Backend (reads via API routes)
    ↓
WebUI Frontend (displays in all safety tabs)
```

---

### 5️⃣ Position Fetching in Guardian ✅

**Architecture**:
```python
# bot/guardian/collectors/position_monitor.py

class PositionMonitor:
    def update_positions(self):
        # Fetch from exchange via CCXT
        positions = self.exchange.fetch_positions([self.symbol])
        return positions
    
    def get_total_pnl(self):
        # Calculate total PnL across all positions
        return self.total_pnl_inr
    
    def get_position_details(self):
        # Return position count, PnL, exposure
        return {
            'position_count': len(self.positions),
            'total_pnl_inr': self.total_pnl_inr,
            'exposure': self.total_exposure
        }
```

**Used By**:
- ✅ Guardian health tracking
- ✅ Risk decision engine (position limit checks)
- ✅ Liquidation monitor (margin calculations)
- ✅ WebUI Open Positions tab

**Your Screenshot Shows**:
- ✅ 4 positions tracked
- ✅ +$31.49 total unrealized P&L
- ✅ Real-time updates working

---

## 🎯 Summary

✅ **1. REST API**: CCXT handles all exchange communication (no WebSocket needed)  
✅ **2. Log Commands**: 7 commands for comprehensive Guardian monitoring  
✅ **3. Volatility**: DeltaVolatilityCollector → Guardian → WebUI (perfect integration)  
✅ **4. WebUI Tabs**: All 5 safety systems read from Guardian health files  
✅ **5. Positions**: position_monitor.py fetches and provides to all systems  

## 🚀 New Architecture Benefits

📂 **Clean file tree**: collectors/ engine/ core/ (visible in VS Code)  
🔄 **Live config watching**: WebUI parameter changes detected automatically  
💾 **SQL signal system**: gridbot_events.db for full audit trail  
🎯 **Single source of truth**: risk_decision_engine makes ALL decisions  
🔗 **WebUI integration**: All tabs connected to Guardian health  
📊 **Real-time monitoring**: 10s health updates + 5s signal publishing  

---

**All systems operational with new Guardian architecture!** 🎉
