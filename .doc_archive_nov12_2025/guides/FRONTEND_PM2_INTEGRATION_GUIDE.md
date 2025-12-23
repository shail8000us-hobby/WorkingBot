# Frontend PM2 Integration - Implementation Guide

**Date:** November 3, 2025
**Status:** Backend complete, Frontend pending

---

## ✅ Backend Changes (COMPLETED)

### 1. Created PM2 Routes (`webui/backend/routes/pm2.py`)
- ✅ Replaced `tmux.py` completely
- ✅ Added comprehensive PM2 API endpoints
- ✅ Integrated with `pm2_adapter.py`

### 2. Updated Backend Files
- ✅ `webui/backend/routes/__init__.py` - Replaced `tmux_bp` with `pm2_bp`
- ✅ `webui/backend/app.py` - Updated imports to use `pm2_bp`
- ✅ `webui/backend/utils/pm2_adapter.py` - Added all missing methods

### 3. Backend API Endpoints Available

**PM2 Status & Control:**
- `GET /api/pm2/enabled` - Check if PM2 is enabled
- `GET /api/pm2/status` - Get all PM2 processes with stats
- `GET /api/pm2/process/:name` - Get specific process details
- `POST /api/pm2/start/:name` - Start process (gridbot-live, guardian-live, heartbeat, all)
- `POST /api/pm2/stop/:name` - Stop process gracefully
- `POST /api/pm2/restart/:name` - Restart process
- `POST /api/pm2/reload/:name` - Zero-downtime reload
- `GET /api/pm2/logs/:name` - Get process logs
- `POST /api/pm2/flush-logs` - Clear all logs
- `POST /api/pm2/save` - Save PM2 process list
- `GET /api/pm2/describe/:name` - Detailed process info

**Example Response from `/api/pm2/status`:**
```json
{
  "success": true,
  "processes": [
    {
      "name": "gridbot-live",
      "pid": 27759,
      "status": "online",
      "cpu": 3.9,
      "memory": 32.17,
      "uptime": 300,
      "restarts": 0,
      "pm_id": 0
    },
    {
      "name": "guardian-live",
      "pid": 37189,
      "status": "online",
      "cpu": 0.6,
      "memory": 26.22,
      "uptime": 120,
      "restarts": 0,
      "pm_id": 1
    },
    {
      "name": "heartbeat",
      "pid": 37442,
      "status": "online",
      "cpu": 0,
      "memory": 6.58,
      "uptime": 90,
      "restarts": 0,
      "pm_id": 2
    }
  ],
  "total": 3,
  "online": 3,
  "stopped": 0,
  "errored": 0,
  "summary": {
    "total_cpu": 4.5,
    "total_memory": 64.97,
    "total_restarts": 0
  }
}
```

---

## 🔨 Frontend Changes (TODO)

### Files to Modify/Create:

#### 1. **Create PM2Panel Component** (`webui/frontend/src/components/PM2Panel.js`)
Replace `TmuxPanel.js` with a comprehensive PM2 monitoring panel.

**Features to include:**
- Real-time process list (GridBot, Guardian, Heartbeat)
- Process status indicators (online/stopped/errored)
- CPU and memory usage graphs
- Restart counters
- Start/Stop/Restart buttons for each process
- "Start All" / "Stop All" buttons
- Process uptime display
- Auto-refresh every 5 seconds
- Process details modal (click to expand)
- Logs viewer for each process
- Summary statistics panel

**UI Layout:**
```
┌──────────────────────────────────────────────────────────┐
│  PM2 Process Manager                                     │
│                                                          │
│  Summary:  3 Online | 0 Stopped | 0 Errored             │
│  CPU: 4.5% | Memory: 64.97 MB | Restarts: 0            │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ GridBot Live          [●] ONLINE                   │ │
│  │ PID: 27759    CPU: 3.9%    Memory: 32.17 MB      │ │
│  │ Uptime: 5m    Restarts: 0                         │ │
│  │ [Stop] [Restart] [Logs] [Details]                 │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Guardian Live         [●] ONLINE                   │ │
│  │ PID: 37189    CPU: 0.6%    Memory: 26.22 MB      │ │
│  │ Uptime: 2m    Restarts: 0                         │ │
│  │ [Stop] [Restart] [Logs] [Details]                 │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Heartbeat             [●] ONLINE                   │ │
│  │ PID: 37442    CPU: 0%      Memory: 6.58 MB        │ │
│  │ Uptime: 1m    Restarts: 0                         │ │
│  │ [Stop] [Restart] [Logs] [Details]                 │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  [Start All] [Stop All] [Restart All] [Flush Logs]     │
└──────────────────────────────────────────────────────────┘
```

#### 2. **Update apiClient** (`webui/frontend/src/utils/apiClient.js`)

Replace tmux methods with PM2 methods:

**Remove:**
- `startTmuxSession()`
- `stopTmuxSession()`

**Add:**
```javascript
// PM2 Methods
async getPM2Status() {
  return this.get('/api/pm2/status');
}

async getPM2Enabled() {
  return this.get('/api/pm2/enabled');
}

async startPM2Process(name) {
  return this.post(`/api/pm2/start/${name}`);
}

async stopPM2Process(name) {
  return this.post(`/api/pm2/stop/${name}`);
}

async restartPM2Process(name) {
  return this.post(`/api/pm2/restart/${name}`);
}

async getPM2ProcessDetails(name) {
  return this.get(`/api/pm2/process/${name}`);
}

async getPM2Logs(name, lines = 100, type = 'all') {
  return this.get(`/api/pm2/logs/${name}?lines=${lines}&type=${type}`);
}

async flushPM2Logs() {
  return this.post('/api/pm2/flush-logs');
}

async reloadPM2Process(name) {
  return this.post(`/api/pm2/reload/${name}`);
}

async savePM2ProcessList() {
  return this.post('/api/pm2/save');
}
```

#### 3. **Update App.js** (`webui/frontend/src/App.js`)

**Replace:**
```javascript
import TmuxPanel from './components/TmuxPanel';
```

**With:**
```javascript
import PM2Panel from './components/PM2Panel';
```

**Replace tmux section (around line 929-940):**
```javascript
{/* tmux Control Center */}
<Panel
  id="tmux-control"
  title="tmux Control Center"
  category="system"
  icon={Terminal}
  description="tmux control, process management, and emergency controls"
>
  <Suspense fallback={<LoadingFallback message="Loading tmux status..." />}>
    <EnhancedErrorBoundary componentName="TmuxPanel">
      <TmuxPanel />
    </EnhancedErrorBoundary>
  </Suspense>
</Panel>
```

**With:**
```javascript
{/* PM2 Process Manager */}
<Panel
  id="pm2-control"
  title="PM2 Process Manager"
  category="system"
  icon={Terminal}
  description="Professional process management with PM2 (GridBot, Guardian, Heartbeat)"
>
  <Suspense fallback={<LoadingFallback message="Loading PM2 status..." />}>
    <EnhancedErrorBoundary componentName="PM2Panel">
      <PM2Panel />
    </EnhancedErrorBoundary>
  </Suspense>
</Panel>
```

#### 4. **Update useBotControl Hook** (`webui/frontend/src/hooks/useBotControl.js`)

**Remove tmux integration from startBot:**
```javascript
const [botResult, tmuxResult] = await Promise.all([
  apiClient.startBot(),
  apiClient.startTmuxSession().catch((error) => ({ 
    success: false, 
    message: error.message || 'tmux session failed' 
  }))
]);
```

**Replace with:**
```javascript
// Start bot (PM2 will handle it automatically if enabled)
const botResult = await apiClient.startBot();
```

**Remove tmux success handling:**
```javascript
if (tmuxResult?.success) {
  showNotification('tmux session started for Guardian/Monitor/Trading panes', 'success');
} else if (tmuxResult && !tmuxResult.success) {
  showNotification(
    `Bot started but tmux session failed: ${tmuxResult.message || 'Check logs'}`, 
    'warning'
  );
}
```

**Note:** PM2 integration is now handled in the backend (`bot_control.py`) automatically.

#### 5. **Update CommandKnowledgeBase** (`webui/frontend/src/components/CommandKnowledgeBase.js`)

**Replace tmux commands with PM2 commands:**

**Remove:**
- "Check tmux Sessions"
- "Kill All tmux Sessions"

**Add:**
```javascript
{
  name: 'Check PM2 Processes',
  description: 'List all PM2-managed processes',
  command: 'pm2 list',
  category: 'Process Management',
  tags: ['pm2', 'processes'],
},
{
  name: 'PM2 Real-time Monitor',
  description: 'Open PM2 monitoring dashboard',
  command: 'pm2 monit',
  category: 'Process Management',
  tags: ['pm2', 'monitoring'],
},
{
  name: 'PM2 Logs',
  description: 'View PM2 process logs',
  command: 'pm2 logs gridbot-live',
  category: 'Process Management',
  tags: ['pm2', 'logs'],
},
{
  name: 'Start All PM2 Processes',
  description: 'Start GridBot, Guardian, and Heartbeat',
  command: './pm2_gridbot.sh start all',
  category: 'Process Management',
  tags: ['pm2', 'start'],
},
{
  name: 'Stop All PM2 Processes',
  description: 'Gracefully stop all PM2 processes',
  command: './pm2_gridbot.sh stop all',
  category: 'Process Management',
  tags: ['pm2', 'stop'],
},
```

---

## 📊 PM2Panel Component Structure (Detailed)

### Component Breakdown:

```javascript
import React, { useState, useEffect } from 'react';
import { apiClient } from '../utils/apiClient';

const PM2Panel = () => {
  const [pm2Status, setPM2Status] = useState(null);
  const [pm2Enabled, setPM2Enabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [selectedProcess, setSelectedProcess] = useState(null);
  const [showLogs, setShowLogs] = useState(false);
  
  // Fetch PM2 status every 5 seconds
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const [statusData, enabledData] = await Promise.all([
          apiClient.getPM2Status(),
          apiClient.getPM2Enabled()
        ]);
        setPM2Status(statusData);
        setPM2Enabled(enabledData.enabled);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching PM2 status:', error);
        setLoading(false);
      }
    };
    
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);
  
  // Process control handlers
  const handleStart = async (name) => { ... };
  const handleStop = async (name) => { ... };
  const handleRestart = async (name) => { ... };
  const handleLogs = async (name) => { ... };
  const handleDetails = async (name) => { ... };
  
  // Render PM2 not enabled state
  if (!pm2Enabled) {
    return (
      <div className="pm2-panel">
        <div className="alert alert-warning">
          PM2 is not enabled. Run: ./toggle_pm2.sh enable
        </div>
      </div>
    );
  }
  
  // Render loading state
  if (loading) {
    return <div>Loading PM2 status...</div>;
  }
  
  // Render main panel
  return (
    <div className="pm2-panel">
      {/* Summary Stats */}
      <div className="pm2-summary">
        <div className="stat">
          <span className="label">Online:</span>
          <span className="value text-success">{pm2Status.online}</span>
        </div>
        <div className="stat">
          <span className="label">Stopped:</span>
          <span className="value text-warning">{pm2Status.stopped}</span>
        </div>
        <div className="stat">
          <span className="label">Errored:</span>
          <span className="value text-danger">{pm2Status.errored}</span>
        </div>
        <div className="stat">
          <span className="label">CPU:</span>
          <span className="value">{pm2Status.summary.total_cpu}%</span>
        </div>
        <div className="stat">
          <span className="label">Memory:</span>
          <span className="value">{pm2Status.summary.total_memory} MB</span>
        </div>
        <div className="stat">
          <span className="label">Total Restarts:</span>
          <span className="value">{pm2Status.summary.total_restarts}</span>
        </div>
      </div>
      
      {/* Process List */}
      <div className="pm2-processes">
        {pm2Status.processes.map(process => (
          <ProcessCard
            key={process.name}
            process={process}
            onStart={() => handleStart(process.name)}
            onStop={() => handleStop(process.name)}
            onRestart={() => handleRestart(process.name)}
            onLogs={() => handleLogs(process.name)}
            onDetails={() => handleDetails(process.name)}
          />
        ))}
      </div>
      
      {/* Control Buttons */}
      <div className="pm2-controls">
        <button onClick={() => handleStart('all')}>Start All</button>
        <button onClick={() => handleStop('all')}>Stop All</button>
        <button onClick={() => handleRestart('all')}>Restart All</button>
        <button onClick={handleFlushLogs}>Flush Logs</button>
      </div>
      
      {/* Modals */}
      {showLogs && <LogsModal process={selectedProcess} onClose={() => setShowLogs(false)} />}
    </div>
  );
};
```

---

## 🎨 Styling Recommendations

Add to `webui/frontend/src/App.css` or create `PM2Panel.css`:

```css
.pm2-panel {
  padding: 20px;
}

.pm2-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 15px;
  margin-bottom: 30px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.pm2-summary .stat {
  display: flex;
  flex-direction: column;
}

.pm2-summary .label {
  font-size: 0.875rem;
  color: #6c757d;
  margin-bottom: 5px;
}

.pm2-summary .value {
  font-size: 1.5rem;
  font-weight: 600;
}

.pm2-processes {
  display: grid;
  gap: 15px;
  margin-bottom: 20px;
}

.process-card {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  background: white;
  transition: box-shadow 0.2s;
}

.process-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.process-card.online {
  border-left: 4px solid #28a745;
}

.process-card.stopped {
  border-left: 4px solid #ffc107;
}

.process-card.errored {
  border-left: 4px solid #dc3545;
}

.process-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.process-name {
  font-size: 1.25rem;
  font-weight: 600;
}

.process-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.status-indicator.online {
  background: #28a745;
  box-shadow: 0 0 8px #28a745;
}

.status-indicator.stopped {
  background: #ffc107;
}

.status-indicator.errored {
  background: #dc3545;
  box-shadow: 0 0 8px #dc3545;
}

.process-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin-bottom: 15px;
}

.process-stat {
  font-size: 0.875rem;
}

.process-stat .label {
  color: #6c757d;
  margin-right: 5px;
}

.process-stat .value {
  font-weight: 600;
}

.process-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.process-actions button {
  padding: 6px 12px;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.process-actions button:hover {
  background: #f8f9fa;
  border-color: #007bff;
  color: #007bff;
}

.pm2-controls {
  display: flex;
  gap: 15px;
  justify-content: center;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.pm2-controls button {
  padding: 10px 20px;
  font-size: 1rem;
  border: none;
  border-radius: 4px;
  background: #007bff;
  color: white;
  cursor: pointer;
  transition: background 0.2s;
}

.pm2-controls button:hover {
  background: #0056b3;
}
```

---

## ✅ Testing Checklist

After implementing frontend changes:

1. **Check PM2 Enabled Status**
   - Open WebUI
   - Navigate to PM2 Panel
   - Should show PM2 is enabled

2. **View Process List**
   - Should see GridBot Live, Guardian Live, Heartbeat
   - Status indicators should be green (online)
   - CPU and memory stats should update every 5 seconds

3. **Test Process Control**
   - Click "Stop" on GridBot → Should stop gracefully
   - Click "Start" → Should restart
   - Click "Restart" → Should restart
   - Verify in terminal: `pm2 list`

4. **Test Logs Viewer**
   - Click "Logs" on a process
   - Should show recent log lines
   - Should be able to switch between stdout and stderr

5. **Test Bulk Operations**
   - Click "Stop All" → All processes should stop
   - Click "Start All" → All processes should start
   - Click "Restart All" → All processes should restart

6. **Verify Auto-Refresh**
   - Leave panel open
   - Start/stop processes via terminal
   - UI should update within 5 seconds

---

## 📚 Documentation Updates Needed

1. **Update README.md**
   - Remove tmux references
   - Add PM2 setup instructions
   - Update screenshots with PM2 panel

2. **Update USER_GUIDE.md**
   - Replace tmux section with PM2 section
   - Add PM2 panel usage instructions

3. **backend_frontend.md**
   - Already updated with PM2 information
   - Add WebUI PM2 panel section

---

## 🎯 Summary

**Backend:** ✅ COMPLETE - All PM2 APIs ready and tested
**Frontend:** ⏳ PENDING - Need to create PM2Panel component and update related files

**Next Steps:**
1. Create `PM2Panel.js` component
2. Update `apiClient.js` with PM2 methods
3. Update `App.js` to use PM2Panel instead of TmuxPanel
4. Update `useBotControl.js` to remove tmux dependencies
5. Update `CommandKnowledgeBase.js` with PM2 commands
6. Test all functionality
7. Update documentation

**Once frontend is complete, the entire WebUI will use PM2 instead of tmux for process management!**
