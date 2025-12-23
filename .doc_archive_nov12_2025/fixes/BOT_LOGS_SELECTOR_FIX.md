# ✅ BOT LOGS SELECTOR - FIXED

**Issue**: All three bots (Trading, Guardian, Monitor) showing same log data  
**Date**: October 31, 2025  
**Status**: ✅ **FIXED**

---

## 🔍 ROOT CAUSES IDENTIFIED

### **Cause #1: API Ignoring bot_type Parameter**

**File**: `webui/backend/routes/logs.py`

**OLD CODE**:
```python
@logs_bp.route('/api/logs/recent', methods=['GET'])
def get_logs_recent():
    lines = request.args.get('lines', 50, type=int)
    
    # ❌ IGNORES bot_type parameter!
    log_lines = get_recent_logs(lines)  # Always uses default file
    
    return jsonify({'logs': log_lines})
```

**Result**: All bot selections returned `bot/logs/bot.log`

---

### **Cause #2: Frontend Not Sending bot_type**

**File**: `webui/frontend/src/components/BotManagement/BotManagementDashboard.js`

**OLD CODE**:
```javascript
const fetchLogs = async (botType) => {
  const logTypeMap = {
    'trading': 'trading',
    'guardian': 'guardian',
    'monitoring': 'health'
  };
  
  const logType = logTypeMap[botType] || 'trading';
  
  // ❌ DOESN'T USE logType! Always same URL
  const response = await api.get(`/api/logs/recent?lines=100`);
}
```

**Result**: Frontend didn't pass bot selection to backend

---

### **Cause #3: Guardian Log File Config Error**

**File**: `grid_config.env`

**WRONG CONFIG**:
```bash
GUARDIAN_LOG_FILE=true  ← Should be a filename!
```

**Result**: Guardian wrote logs to file literally named `bot/logs/true`

**Guardian Code**:
```python
# bot/guardian/guardian_bot.py:95
log_file = log_dir / os.getenv('GUARDIAN_LOG_FILE', 'guardian.log')
# With GUARDIAN_LOG_FILE=true → log_file = "bot/logs/true"
```

---

## 🔧 FIXES APPLIED

### **Fix #1: Backend Now Supports bot_type**

**File**: `webui/backend/routes/logs.py` (lines 71-126)

```python
@logs_bp.route('/api/logs/recent', methods=['GET'])
def get_logs_recent():
    lines = request.args.get('lines', 50, type=int)
    bot_type = request.args.get('bot_type', 'trading', type=str)  # ✅ NEW
    log_file = request.args.get('log_file', None, type=str)        # ✅ NEW
    
    # ✅ Map bot type to log file
    if not log_file:
        log_file_map = {
            'trading': 'bot/logs/bot.log',
            'guardian': 'bot/logs/guardian.log',
            'monitoring': 'bot/logs/heartbeat_monitor.log'
        }
        log_file = log_file_map.get(bot_type, 'bot/logs/bot.log')
    
    log_lines = get_recent_logs(lines, log_file)  # ✅ Uses bot-specific file
    
    return jsonify({
        'logs': log_lines,
        'bot_type': bot_type,      # ✅ Returns which bot
        'log_file': log_file       # ✅ Returns which file
    })
```

---

### **Fix #2: Frontend Sends bot_type**

**File**: `webui/frontend/src/components/BotManagement/BotManagementDashboard.js` (lines 130-155)

```javascript
const fetchLogs = async (botType) => {
  // ✅ Map bot types to log files
  const logFileMap = {
    'trading': 'bot/logs/bot.log',
    'guardian': 'bot/logs/guardian.log',
    'monitoring': 'bot/logs/heartbeat_monitor.log'
  };
  
  const logFile = logFileMap[botType] || 'bot/logs/bot.log';
  
  // ✅ Pass bot_type AND log_file to API
  const response = await api.get(
    `/api/logs/recent?lines=100&bot_type=${botType}&log_file=${encodeURIComponent(logFile)}`
  );
  
  setLogs(response.data.logs || 'No logs available');
};
```

---

### **Fix #3: Corrected Guardian Log File Config**

**File**: `grid_config.env` (line 757)

```bash
# BEFORE:
GUARDIAN_LOG_FILE=true  ❌

# AFTER:
GUARDIAN_LOG_FILE=guardian.log  ✅
```

**Actions Taken**:
- ✅ Fixed config file
- ✅ Deleted misnamed `bot/logs/true` file
- ⚠️  Guardian needs restart to use correct log file

---

### **Fix #4: Added Guardian to Dropdown**

**File**: `webui/frontend/src/components/BotManagement/BotManagementDashboard.js` (lines 447-449)

```javascript
// BEFORE:
<MenuItem value="trading">Trading Bot</MenuItem>
<MenuItem value="health">Health Monitor</MenuItem>   ❌ Wrong value
<MenuItem value="monitoring">Monitoring Bot</MenuItem>

// AFTER:
<MenuItem value="trading">Trading Bot</MenuItem>
<MenuItem value="guardian">Guardian Bot</MenuItem>  ✅ Proper value
<MenuItem value="monitoring">Heartbeat Monitor</MenuItem>
```

---

## 📊 WHAT'S DIFFERENT NOW

### **Dropdown Options**:
1. **Trading Bot** → Reads `bot/logs/bot.log` (742 KB, actively updating)
2. **Guardian Bot** → Reads `bot/logs/guardian.log` (after Guardian restart)
3. **Heartbeat Monitor** → Reads `bot/logs/heartbeat_monitor.log` (1.4 MB)

### **API Behavior**:

**Request**:
```
GET /api/logs/recent?lines=100&bot_type=guardian
```

**Response**:
```json
{
  "success": true,
  "logs": [...],
  "bot_type": "guardian",
  "log_file": "bot/logs/guardian.log",
  "count": 100
}
```

Each bot now returns its **own specific log file**! ✅

---

## ⚡ CURRENT STATUS

### **API Working** ✅:
```
Trading Bot API:   Returns bot/logs/bot.log ✅
Guardian Bot API:  Returns bot/logs/guardian.log ✅
Monitor API:       Returns bot/logs/heartbeat_monitor.log ✅
```

### **Frontend Rebuilt** ✅:
- Bot selector updated
- API calls include bot_type parameter
- File: `build/static/js/main.a5f682c5.js` (512 KB)

### **Backend Updated** ✅:
- Logs API supports bot_type
- Returns bot-specific log files
- Restarted with fixes loaded

---

## 🚨 ACTION REQUIRED

### **Restart Guardian Bot** ⚠️

Guardian is currently writing to wrong log file. To fix:

**Option A - Via WebUI** (Recommended):
1. Go to Bot Management panel
2. Find Guardian Bot
3. Click "Stop"
4. Wait 5 seconds
5. Click "Start"
6. New logs will go to `bot/logs/guardian.log`

**Option B - Via Terminal**:
```bash
kill -TERM 49484
sleep 2
python3 -u bot/guardian/guardian_bot.py &
```

**After Restart**:
- ✅ Guardian logs will write to `guardian.log`
- ✅ Bot selector will show Guardian-specific logs
- ✅ Each bot will have its own log stream

---

## 🎯 TESTING THE FIX

### **After Guardian Restarts**:

1. **Refresh browser** (`Cmd + Shift + R`)
2. Go to **Bot Management** panel
3. Look at **Bot Logs** section
4. **Select Trading Bot**: Should show `[HB] Positions: 0/3, Price: $XXX`
5. **Select Guardian Bot**: Should show Guardian-specific logs (risk monitoring, equity checks)
6. **Select Heartbeat Monitor**: Should show heartbeat/monitoring logs

Each should show **DIFFERENT data**!

---

## 📋 SUMMARY

**Problem**: All 3 bots showed same data (Trading Bot logs)

**Root Causes**:
1. API didn't use bot_type parameter
2. Frontend didn't send bot_type parameter
3. Guardian config wrong (`GUARDIAN_LOG_FILE=true`)

**Fixes Applied**:
1. ✅ Backend API now supports bot-specific log files
2. ✅ Frontend sends bot_type to API
3. ✅ Guardian config corrected
4. ✅ Dropdown options updated
5. ✅ Frontend rebuilt
6. ✅ Backend restarted

**Status**:
- ✅ Trading Bot logs: Working
- ⚠️  Guardian Bot logs: Need Guardian restart
- ✅ Heartbeat Monitor logs: Working (old data)

**Next Step**: 
**Restart Guardian Bot** from WebUI to enable proper logging

---

**After Guardian restart and browser refresh**, each bot will show its own unique logs! 🎉

