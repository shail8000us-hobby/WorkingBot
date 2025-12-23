# Unrealized PnL System Documentation

**Last Updated:** November 19, 2025  
**Version:** 2.0 (Post-Fix)  
**Status:** ✅ PRODUCTION READY

---

## 🎯 OVERVIEW

The Unrealized PnL system provides real-time tracking and visualization of trading position profits and losses in the GridBot WebUI. This system captures PnL data from multiple sources, stores it in SQL database, and displays it as an interactive trend chart.

### Key Features
- **Real-time PnL tracking** - Updates every 10 seconds via Guardian bot
- **Historical trend visualization** - 24-hour rolling chart with hourly aggregation
- **Multi-source data collection** - Delta Exchange API, bot state files, Guardian monitoring
- **Automatic data persistence** - SQL database storage with automatic cleanup
- **WebSocket live updates** - Real-time chart updates without page refresh

---

## 🏗️ SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                    UNREALIZED PnL DATA FLOW                 │
└─────────────────────────────────────────────────────────────┘

1. DATA COLLECTION (Multiple Sources)
   ├─→ Delta Exchange API (/v2/positions/margined)
   ├─→ Bot State Files (bot/reports/positions.json)
   └─→ Guardian Health Data (.guardian_health.json)

2. DATA PROCESSING & STORAGE
   ├─→ Guardian Bot (bot/guardian/guardian_bot.py)
   │   └─→ Calculates total_pnl_inr every 10 seconds
   │   └─→ Stores to SQL: bot/state/events.db
   │
   └─→ SQL Schema:
       CREATE TABLE pnl_history (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           timestamp TEXT NOT NULL,
           total_pnl_inr REAL NOT NULL,
           position_count INTEGER NOT NULL,
           created_at DATETIME DEFAULT CURRENT_TIMESTAMP
       );

3. API LAYER (WebUI Backend)
   └─→ /api/pnl-history/hourly
       ├─→ Queries SQL database
       ├─→ Groups by hour (last 24 hours)
       ├─→ Returns JSON: {history: [{timestamp, total_pnl, position_count}]}

4. FRONTEND VISUALIZATION
   ├─→ UnrealizedPnLPanel.js (Data fetching & parsing)
   ├─→ PnLChart.js (Recharts visualization)
   └─→ Real-time updates via WebSocket
```

---

## 📊 DATA COLLECTION SOURCES

### 1. Delta Exchange API (Primary Source)
**File:** `webui/backend/routes/positions.py`  
**Function:** `_get_positions_from_delta()`

```python
# PnL Calculation Formula
CONTRACT_MULTIPLIER = 0.001
unrealized_pnl = (mark_price - entry_price) * size * CONTRACT_MULTIPLIER

# Example:
# Entry: $50,000, Mark: $51,000, Size: 10 contracts
# PnL = (51000 - 50000) * 10 * 0.001 = 10.0 USD
```

**Features:**
- Real-time mark prices from Delta Exchange
- Accurate contract multiplier (0.001 for BTCUSD)
- Handles both LONG and SHORT positions
- Includes Greeks calculation for options
- Circuit breaker protection for API failures

### 2. Bot State Files (Secondary Source)
**File:** `bot/reports/positions.json`  
**Updated by:** AsyncBot position management

```json
{
  "positions": [
    {
      "id": "pos_1",
      "entry_price": 50000.0,
      "current_price": 51000.0,
      "size": 10,
      "unrealized_pnl": 10.0,
      "timestamp": "2025-11-19T16:30:00"
    }
  ],
  "summary": {
    "total_pnl_usd": 10.0,
    "total_pnl_inr": 850.0,
    "total_positions": 1
  }
}
```

### 3. Guardian Health Data (Fallback Source)
**File:** `.guardian_health.json`  
**Updated by:** Guardian bot monitoring

```json
{
  "status": "ok",
  "monitoring": {
    "total_pnl_inr": 850.0,
    "total_pnl_usd": 10.0,
    "position_count": 1,
    "last_price": 51000.0
  }
}
```

---

## 🗄️ DATABASE STORAGE

### SQL Database Location
- **File:** `bot/state/events.db`
- **Table:** `pnl_history`
- **Retention:** Automatic cleanup (configurable)
- **Update Frequency:** Every 10 seconds (Guardian bot)

### Data Insertion Process
**File:** `bot/guardian/guardian_bot.py`

```python
def store_pnl_to_database(total_pnl_inr, position_count):
    """Store PnL data to SQL database"""
    conn = sqlite3.connect('bot/state/events.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO pnl_history (timestamp, total_pnl_inr, position_count)
        VALUES (?, ?, ?)
    ''', (datetime.now().isoformat(), total_pnl_inr, position_count))
    
    conn.commit()
    conn.close()
```

### Sample Data
```sql
SELECT * FROM pnl_history ORDER BY timestamp DESC LIMIT 5;

-- Results:
-- 14092|2025-11-19T16:36:09.512788|-47.22|1|2025-11-19 11:06:09
-- 14091|2025-11-19T16:35:59.153930|-47.61|1|2025-11-19 11:05:59
-- 14090|2025-11-19T16:35:48.371607|-45.29|1|2025-11-19 11:05:48
```

---

## 🌐 API ENDPOINTS

### GET /api/pnl-history/hourly
**File:** `webui/backend/routes/pnl.py`  
**Function:** `get_hourly_pnl_history()`

**Purpose:** Returns hourly aggregated PnL data for the last 24 hours

**SQL Query:**
```sql
SELECT 
    strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
    AVG(total_pnl_inr) as avg_pnl,
    AVG(position_count) as avg_positions,
    MAX(timestamp) as latest_timestamp
FROM pnl_history
WHERE timestamp >= ?  -- 24 hours ago
GROUP BY hour
ORDER BY hour ASC
```

**Response Format:**
```json
{
  "history": [
    {
      "timestamp": "2025-11-19T16:38:03.520873",
      "time": "16:00",
      "total_pnl": -32.84,
      "position_count": 1
    }
  ]
}
```

**Error Handling:**
- Returns empty array if database not found
- Graceful fallback on SQL errors
- Circuit breaker protection

---

## 🎨 FRONTEND COMPONENTS

### 1. UnrealizedPnLPanel Component
**File:** `webui/frontend/src/components/panels/UnrealizedPnLPanel.js`

**Responsibilities:**
- Fetch PnL data from API endpoint
- Parse and transform data for chart
- Handle WebSocket updates
- Error state management

**Key Functions:**

#### `parsePnLHistory(payload)`
```javascript
function parsePnLHistory(payload) {
  const history = Array.isArray(payload) ? payload : payload?.history || [];
  
  return history.map((entry) => {
    // Parse timestamp with timezone handling
    const timestamp = entry.timestamp;
    let timestampMs;
    
    if (timestamp) {
      let date;
      if (timestamp.includes('T') && !timestamp.includes('Z') && !timestamp.includes('+')) {
        // ISO format without timezone, assume local time
        date = new Date(timestamp);
      } else {
        date = new Date(timestamp);
      }
      
      if (!Number.isNaN(date.getTime())) {
        timestampMs = date.getTime();
      }
    }
    
    // Extract PnL value with fallbacks
    const pnlRaw = Number(entry.total_pnl ?? entry.pnl ?? entry.upnl ?? entry.value ?? 0);
    
    return {
      timestamp: timestampMs || Date.now(),
      pnl: Number.isFinite(pnlRaw) ? Number(pnlRaw.toFixed(2)) : 0
    };
  });
}
```

**Data Flow:**
1. `loadPnLHistory()` - Fetches data from `/api/pnl-history/hourly`
2. `parsePnLHistory()` - Transforms API response to chart format
3. `setPnlHistory()` - Updates React state
4. WebSocket listeners for real-time updates

### 2. PnLChart Component
**File:** `webui/frontend/src/components/charts/PnLChart.js`

**Responsibilities:**
- Render interactive area chart using Recharts
- Handle dynamic domain calculation
- Format tooltips and axis labels
- Responsive design for mobile/desktop

**Key Functions:**

#### `getDataDomain(data)`
```javascript
const getDataDomain = (data) => {
  if (!data || data.length === 0) {
    // Fallback to 24-hour window
    const now = Date.now();
    const twentyFourHoursAgo = now - (24 * 60 * 60 * 1000);
    return [twentyFourHoursAgo, now];
  }
  
  const timestamps = data.map(d => d.timestamp).filter(t => t && !isNaN(t));
  if (timestamps.length === 0) {
    const now = Date.now();
    const twentyFourHoursAgo = now - (24 * 60 * 60 * 1000);
    return [twentyFourHoursAgo, now];
  }
  
  const minTime = Math.min(...timestamps);
  const maxTime = Math.max(...timestamps);
  
  // Add 1 hour padding on each side
  const padding = 60 * 60 * 1000;
  return [minTime - padding, maxTime + padding];
};
```

**Chart Configuration:**
- **Chart Type:** Area chart with gradient fill
- **X-Axis:** Time-based with hourly ticks
- **Y-Axis:** PnL values in INR
- **Tooltip:** Shows timestamp and PnL value
- **Responsive:** Adapts to screen size

---

## 🔧 RECENT FIXES (November 19, 2025)

### Issue Identified
The unrealized PnL chart was displaying a flat line at 0 despite having valid negative PnL data in the database.

### Root Cause Analysis
1. **API Data:** ✅ Correct - API was returning valid PnL data including negative values
2. **Database Storage:** ✅ Correct - SQL database contained accurate PnL records
3. **Frontend Parsing:** ✅ Correct - Data parsing logic was working properly
4. **Chart Domain:** ❌ **ISSUE FOUND** - Fixed IST-based domain calculation was excluding data points

### Fix Implementation

#### Problem
```javascript
// OLD: Fixed IST-based domain (BROKEN)
const get24HourDomain = () => {
  const nowIST = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
  const currentHour = new Date(nowIST.getFullYear(), nowIST.getMonth(), nowIST.getDate(), nowIST.getHours(), 0, 0, 0);
  const endTime = currentHour.getTime();
  const startTime = endTime - (24 * 60 * 60 * 1000);
  return [startTime, endTime];
};
```

#### Solution
```javascript
// NEW: Dynamic data-based domain (FIXED)
const getDataDomain = (data) => {
  if (!data || data.length === 0) {
    const now = Date.now();
    const twentyFourHoursAgo = now - (24 * 60 * 60 * 1000);
    return [twentyFourHoursAgo, now];
  }
  
  const timestamps = data.map(d => d.timestamp).filter(t => t && !isNaN(t));
  const minTime = Math.min(...timestamps);
  const maxTime = Math.max(...timestamps);
  const padding = 60 * 60 * 1000; // 1 hour padding
  return [minTime - padding, maxTime + padding];
};
```

### Files Modified
1. **`webui/frontend/src/components/charts/PnLChart.js`**
   - Replaced `get24HourDomain()` with `getDataDomain(data)`
   - Updated chart to use dynamic domain calculation

2. **`webui/frontend/src/components/panels/UnrealizedPnLPanel.js`**
   - Improved timestamp parsing for timezone handling
   - Enhanced error handling for malformed timestamps

### Validation Results
- ✅ Chart now displays actual PnL trend data
- ✅ Negative PnL values properly visualized
- ✅ Dynamic domain ensures all data points are visible
- ✅ Real-time updates working correctly

---

## 🔍 DEBUGGING & TROUBLESHOOTING

### Common Issues

#### 1. Chart Shows Flat Line at Zero
**Symptoms:** Chart displays but shows no variation, flat line at 0
**Causes:**
- Domain calculation excluding data points
- Timestamp parsing issues
- API returning empty data

**Debug Steps:**
```bash
# 1. Check API data
curl -s "http://localhost:5555/api/pnl-history/hourly" | python3 -m json.tool

# 2. Check database
sqlite3 /Users/ssr/Projects/WorkingBot/bot/state/events.db "SELECT COUNT(*) FROM pnl_history;"

# 3. Check recent data
sqlite3 /Users/ssr/Projects/WorkingBot/bot/state/events.db "SELECT * FROM pnl_history ORDER BY timestamp DESC LIMIT 5;"
```

#### 2. No Data Available
**Symptoms:** Chart shows "No historical PnL data" message
**Causes:**
- Guardian bot not running
- Database file missing
- API endpoint errors

**Debug Steps:**
```bash
# Check Guardian bot status
pm2 list | grep guardian

# Check database file
ls -la /Users/ssr/Projects/WorkingBot/bot/state/events.db

# Check API endpoint
curl -s "http://localhost:5555/api/pnl-history/hourly"
```

#### 3. Incorrect PnL Values
**Symptoms:** Chart shows data but values seem wrong
**Causes:**
- USD to INR conversion rate outdated
- Position calculation errors
- Mark price data stale

**Debug Steps:**
```bash
# Check current positions
curl -s "http://localhost:5555/api/positions" | python3 -m json.tool

# Check Guardian health
cat .guardian_health.json | python3 -m json.tool

# Check USD to INR rate in config
grep -A 5 -B 5 "usd_to_inr_rate" config.yaml
```

### Monitoring Commands

```bash
# Real-time PnL monitoring
watch -n 5 'sqlite3 /Users/ssr/Projects/WorkingBot/bot/state/events.db "SELECT timestamp, total_pnl_inr, position_count FROM pnl_history ORDER BY timestamp DESC LIMIT 5;"'

# Check API response time
time curl -s "http://localhost:5555/api/pnl-history/hourly" > /dev/null

# Monitor WebUI logs
pm2 logs webui-backend --lines 20
```

---

## ⚙️ CONFIGURATION

### Guardian Bot PnL Collection
**File:** `config.yaml`

```yaml
guardian:
  enabled: true
  check_interval: 10              # PnL collection every 10 seconds
  pnl_tracking:
    enabled: true
    database_path: "bot/state/events.db"
    retention_days: 30            # Keep 30 days of history
    
market:
  usd_to_inr_rate: 85.0          # USD to INR conversion rate
```

### WebUI Chart Settings
**File:** `webui/frontend/src/components/charts/PnLChart.js`

```javascript
// Chart configuration
const CHART_CONFIG = {
  height: "h-52 sm:h-64",         // Responsive height
  gradientColor: "#22c55e",       // Green gradient
  strokeWidth: 2,                 // Line thickness
  padding: 60 * 60 * 1000,       // 1 hour domain padding
  tickGap: 50,                    // Minimum tick spacing
  tooltipFormat: "₹{value}"       // INR currency format
};
```

---

## 🚀 PERFORMANCE CONSIDERATIONS

### Database Optimization
- **Indexing:** Automatic index on timestamp column
- **Cleanup:** Automatic deletion of records older than 30 days
- **Connection Pooling:** Single connection per request
- **Query Optimization:** Hourly aggregation reduces data transfer

### Frontend Optimization
- **Data Caching:** API responses cached for 30 seconds
- **Lazy Loading:** Chart only renders when visible
- **Debounced Updates:** WebSocket updates debounced to prevent spam
- **Memory Management:** Old chart data automatically garbage collected

### API Performance
- **Circuit Breaker:** Prevents cascade failures
- **Timeout Handling:** 5-second timeout on database queries
- **Error Recovery:** Graceful fallback to empty data
- **Rate Limiting:** Built-in request throttling

---

## 🔮 FUTURE ENHANCEMENTS

### Planned Features
1. **Multiple Timeframes** - 1h, 4h, 1d, 1w chart views
2. **PnL Alerts** - Telegram notifications for significant changes
3. **Export Functionality** - CSV/PDF export of PnL history
4. **Advanced Analytics** - Sharpe ratio, max drawdown calculations
5. **Comparison Charts** - Compare with BTC price movements

### Technical Improvements
1. **WebSocket Streaming** - Real-time PnL updates without polling
2. **Data Compression** - Compress historical data for faster loading
3. **Caching Layer** - Redis cache for frequently accessed data
4. **Mobile App** - Native mobile app with PnL tracking
5. **Multi-Exchange** - Support for multiple exchange PnL tracking

---

## 📚 RELATED DOCUMENTATION

- **`AI_CONTEXT.md`** - Complete project overview
- **`ASYNC_GRIDBOT_EXECUTIVE_SUMMARY.md`** - AsyncBot architecture
- **`webui/backend/routes/pnl.py`** - API implementation details
- **`bot/guardian/guardian_bot.py`** - Guardian monitoring system
- **`config.yaml`** - System configuration reference

---

## ✅ VALIDATION CHECKLIST

### System Health Check
- [ ] Guardian bot running and collecting PnL data
- [ ] Database contains recent PnL records (< 1 minute old)
- [ ] API endpoint returns valid JSON response
- [ ] WebUI chart displays actual trend data
- [ ] Real-time updates working via WebSocket
- [ ] Error handling gracefully manages failures

### Data Accuracy Check
- [ ] PnL values match Delta Exchange positions
- [ ] USD to INR conversion rate is current
- [ ] Timestamp parsing handles timezone correctly
- [ ] Chart domain includes all data points
- [ ] Negative PnL values display properly

### Performance Check
- [ ] API response time < 500ms
- [ ] Chart renders smoothly without lag
- [ ] Database queries complete < 100ms
- [ ] Memory usage remains stable
- [ ] No JavaScript console errors

---

**End of Documentation**

*This documentation provides complete coverage of the Unrealized PnL system architecture, implementation, and troubleshooting. Any AI assistant can use this to understand and maintain the system without extensive code exploration.*
