# Price Alert System for Options Payoff Graph

## Overview
Create a system that allows users to set price alerts directly on the payoff graph. When BTC reaches those price points, the user gets notified via:
1. **Telegram** (primary notification method)
2. **Phone push notification** via Tailscale Funnel + ntfy.sh or Pushover (backup method)
3. **In-app notification** (always available)

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Frontend       │────▶│  Backend API     │────▶│  Alert Manager  │
│  (React Chart)  │     │  (Flask)         │     │  (Background)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │                        │
        │                        │                        ▼
        │                        │              ┌─────────────────┐
        │                        │              │  Price Monitor  │
        │                        └─────────────▶│  (WebSocket)    │
        │                                       └─────────────────┘
        │                                                │
        └────────────────────────────────────────────────┘
                                                         │
                              ┌───────────────────────────┼───────────────────────────┐
                              │                           │                           │
                              ▼                           ▼                           ▼
                    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
                    │  Telegram Bot   │         │  Phone Push     │         │  In-App Toast   │
                    │  Notification   │         │  (ntfy/Pushover)│         │  Notification   │
                    └─────────────────┘         └─────────────────┘         └─────────────────┘
```

---

## Implementation Plan

### Phase 1: Database & Backend Foundation

#### 1.1 Create Database Table for Alerts

```sql
-- File: webui/backend/migrations/create_price_alerts.sql

CREATE TABLE IF NOT EXISTS price_alerts (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL DEFAULT 'BTCUSD',
    target_price REAL NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('above', 'below', 'cross')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'triggered', 'expired', 'cancelled')),
    note TEXT,  -- User's note about why this alert
    expected_pnl REAL,  -- P&L at this price (from payoff graph)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    triggered_at TIMESTAMP,
    expires_at TIMESTAMP,  -- Optional expiry
    notification_channels TEXT DEFAULT 'telegram,in_app',  -- Comma-separated: telegram, pushover, ntfy, in_app
    is_repeating BOOLEAN DEFAULT FALSE,  -- Trigger multiple times?
    cooldown_minutes INTEGER DEFAULT 60  -- Min time between repeating notifications
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON price_alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON price_alerts(symbol);
```

#### 1.2 Alert API Endpoints

```python
# File: webui/backend/routes/alerts/alert_routes.py

# Endpoints:
POST   /api/alerts                    # Create new alert
GET    /api/alerts                    # List all alerts (with filters)
GET    /api/alerts/<id>               # Get specific alert
PATCH  /api/alerts/<id>               # Update alert (e.g., cancel)
DELETE /api/alerts/<id>               # Delete alert
POST   /api/alerts/<id>/test          # Send test notification
GET    /api/alerts/settings           # Get notification settings
PUT    /api/alerts/settings           # Update notification settings
```

#### 1.3 Background Alert Monitor

```python
# File: webui/backend/services/alert_monitor.py

class AlertMonitor:
    """Background service that monitors price and triggers alerts."""
    
    def __init__(self):
        self.active_alerts = {}
        self.current_price = None
        self.notification_service = NotificationService()
        
    async def start(self):
        """Start monitoring loop."""
        while True:
            await self.check_alerts()
            await asyncio.sleep(1)  # Check every second
            
    async def check_alerts(self):
        """Check all active alerts against current price."""
        active = await self.db.get_active_alerts()
        for alert in active:
            if self._should_trigger(alert, self.current_price):
                await self._trigger_alert(alert)
                
    def _should_trigger(self, alert, price):
        if alert.direction == 'above' and price >= alert.target_price:
            return True
        elif alert.direction == 'below' and price <= alert.target_price:
            return True
        elif alert.direction == 'cross':
            # Triggered when price crosses in either direction
            return self._has_crossed(alert.target_price, price)
        return False
```

---

### Phase 2: Notification Services

#### 2.1 Telegram Notification

```python
# File: webui/backend/services/notifications/telegram_notifier.py

import aiohttp

class TelegramNotifier:
    """Send alerts via Telegram Bot."""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
    async def send_price_alert(self, alert: dict):
        """Send formatted price alert message."""
        pnl_emoji = "🟢" if alert.get('expected_pnl', 0) >= 0 else "🔴"
        direction_emoji = "📈" if alert['direction'] == 'above' else "📉"
        
        message = f"""
{direction_emoji} **Price Alert Triggered!**

🔔 **{alert['symbol']}** hit **${alert['target_price']:,.2f}**

{pnl_emoji} Expected P&L: **${alert.get('expected_pnl', 0):+,.2f}**

📝 Note: {alert.get('note', 'N/A')}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self._send_message(message, parse_mode='Markdown')
        
    async def _send_message(self, text: str, parse_mode: str = None):
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode
                }
            )
```

#### 2.2 Phone Push via ntfy.sh (Free, Self-hostable)

```python
# File: webui/backend/services/notifications/push_notifier.py

class NtfyNotifier:
    """Send push notifications via ntfy.sh (free, no account needed)."""
    
    def __init__(self, topic: str, server: str = "https://ntfy.sh"):
        self.topic = topic
        self.server = server
        
    async def send_price_alert(self, alert: dict):
        """Send push notification to phone."""
        direction = "above" if alert['direction'] == 'above' else "below"
        pnl = alert.get('expected_pnl', 0)
        
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{self.server}/{self.topic}",
                headers={
                    "Title": f"BTC at ${alert['target_price']:,.0f}",
                    "Priority": "high" if abs(pnl) > 50 else "default",
                    "Tags": "chart,warning" if pnl < 0 else "chart,moneybag",
                },
                data=f"BTC is {direction} ${alert['target_price']:,.2f}\nExpected P&L: ${pnl:+,.2f}"
            )
```

**Setup for User:**
1. Install ntfy app on phone (iOS/Android)
2. Subscribe to a unique topic (e.g., `btc-alerts-{user_id}`)
3. Done! No account needed.

#### 2.3 Alternative: Tailscale Funnel + Custom Server

```python
# This option works if you already have Tailscale set up
# Exposes a local endpoint that forwards to phone notification service

# Tailscale Funnel command:
# tailscale funnel 443 --bg 5555  # Expose Flask server

# Then configure webhook on phone app
```

---

### Phase 3: Frontend Implementation

#### 3.1 Add Alert on Click

```jsx
// In OptionsPayoffDiagram.js

// Add state for alert creation
const [alertDialogOpen, setAlertDialogOpen] = useState(false);
const [alertPrice, setAlertPrice] = useState(null);
const [alertPnL, setAlertPnL] = useState(null);

// On right-click or long-press on chart
const handleChartClick = useCallback((e) => {
  if (e && e.activePayload && e.activePayload[0]) {
    const { payload } = e.activePayload[0];
    setAlertPrice(payload.price);
    setAlertPnL(payload.expiry); // P&L at expiry
    setAlertDialogOpen(true);
  }
}, []);

// Alert creation dialog
<Dialog open={alertDialogOpen} onClose={() => setAlertDialogOpen(false)}>
  <DialogTitle>Set Price Alert</DialogTitle>
  <DialogContent>
    <Typography>Price: ${alertPrice?.toLocaleString()}</Typography>
    <Typography>Expected P&L at Expiry: ${alertPnL?.toFixed(2)}</Typography>
    
    <RadioGroup value={direction} onChange={(e) => setDirection(e.target.value)}>
      <FormControlLabel value="above" label="Above this price" />
      <FormControlLabel value="below" label="Below this price" />
      <FormControlLabel value="cross" label="Crosses this price" />
    </RadioGroup>
    
    <TextField label="Note (optional)" value={note} onChange={...} />
    
    <FormGroup>
      <FormControlLabel control={<Checkbox checked={telegram} />} label="Telegram" />
      <FormControlLabel control={<Checkbox checked={push} />} label="Phone Push" />
    </FormGroup>
  </DialogContent>
  <DialogActions>
    <Button onClick={() => setAlertDialogOpen(false)}>Cancel</Button>
    <Button variant="contained" onClick={handleCreateAlert}>Create Alert</Button>
  </DialogActions>
</Dialog>
```

#### 3.2 Alert Panel at Bottom of Options Panel

```jsx
// New component: AlertsPanel.js

const AlertsPanel = ({ alerts, onDelete, onToggle }) => {
  return (
    <Paper sx={{ mt: 2, p: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="h6">🔔 Price Alerts</Typography>
        <Button size="small" onClick={onAddAlert}>+ New Alert</Button>
      </Box>
      
      {alerts.length === 0 ? (
        <Typography color="text.secondary">
          No alerts set. Click on the payoff graph to create one.
        </Typography>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Price</TableCell>
              <TableCell>Direction</TableCell>
              <TableCell>Expected P&L</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {alerts.map((alert) => (
              <TableRow key={alert.id}>
                <TableCell>${alert.target_price.toLocaleString()}</TableCell>
                <TableCell>{alert.direction}</TableCell>
                <TableCell sx={{ color: alert.expected_pnl >= 0 ? 'success.main' : 'error.main' }}>
                  ${alert.expected_pnl.toFixed(2)}
                </TableCell>
                <TableCell>
                  <Chip 
                    label={alert.status} 
                    size="small"
                    color={alert.status === 'active' ? 'success' : 'default'}
                  />
                </TableCell>
                <TableCell>
                  <IconButton size="small" onClick={() => onDelete(alert.id)}>🗑️</IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Paper>
  );
};
```

#### 3.3 Visual Indicators on Chart

```jsx
// Show alert lines on the payoff graph

{alerts.filter(a => a.status === 'active').map((alert) => (
  <ReferenceLine
    key={alert.id}
    x={alert.target_price}
    stroke="#fbbf24"
    strokeDasharray="5 5"
    strokeWidth={2}
    label={{
      value: `🔔 $${alert.target_price.toLocaleString()}`,
      position: 'top',
      fill: '#fbbf24',
      fontSize: 10
    }}
  />
))}
```

---

### Phase 4: Settings & Configuration

#### 4.1 Notification Settings Component

```jsx
// NotificationSettings.js (Add to Options Panel settings area)

const NotificationSettings = () => {
  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6">🔔 Alert Notification Settings</Typography>
      
      {/* Telegram Setup */}
      <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2">Telegram</Typography>
        <TextField 
          label="Bot Token" 
          type="password"
          fullWidth 
          helperText="Get from @BotFather on Telegram"
        />
        <TextField 
          label="Chat ID"
          fullWidth
          helperText="Get from @userinfobot on Telegram"
        />
        <Button onClick={testTelegram}>Test Telegram</Button>
      </Box>
      
      {/* Phone Push Setup */}
      <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2">Phone Push (ntfy.sh)</Typography>
        <TextField 
          label="Topic Name"
          fullWidth
          helperText="Add this topic in ntfy app on your phone"
          defaultValue={`btc-alerts-${userId}`}
        />
        <Button onClick={testPush}>Send Test Notification</Button>
      </Box>
    </Paper>
  );
};
```

---

## Files to Create/Modify

### New Files:
1. `webui/backend/routes/alerts/alert_routes.py` - Alert CRUD endpoints
2. `webui/backend/services/alert_monitor.py` - Background price monitor
3. `webui/backend/services/notifications/telegram_notifier.py` - Telegram integration
4. `webui/backend/services/notifications/push_notifier.py` - Phone push via ntfy.sh
5. `webui/backend/db/migrations/create_price_alerts.sql` - Database schema
6. `webui/frontend/src/components/options/AlertsPanel.js` - Alert management UI
7. `webui/frontend/src/components/options/NotificationSettings.js` - Setup UI

### Files to Modify:
1. `webui/backend/routes/options/options_control.py` - Register alert routes
2. `webui/frontend/src/components/options/OptionsPayoffDiagram.js` - Add click handler, alert lines
3. `webui/frontend/src/components/options/OptionsPanel.js` - Add AlertsPanel

---

## Recommended Notification Method

| Method | Pros | Cons | Recommended For |
|--------|------|------|-----------------|
| **Telegram** | Free, reliable, rich formatting, works everywhere | Need to set up bot | Primary method ✅ |
| **ntfy.sh** | Free, no account, works on iOS/Android | Less reliable than Telegram | Backup/Secondary |
| **Pushover** | Very reliable, nice app | Costs $5 one-time | If you want premium UX |
| **Tailscale** | Secure, self-hosted | Complex setup | Only if already using |

**My Recommendation:** Use **Telegram as primary** (you likely already have it), with **ntfy.sh as backup** (free, takes 30 seconds to set up).

---

## Implementation Order

1. **Week 1:** Backend foundation (DB, basic API, alert monitor)
2. **Week 2:** Telegram notifications (most reliable)
3. **Week 3:** Frontend (click-to-create, AlertsPanel, visual indicators)
4. **Week 4:** Phone push (ntfy.sh), settings UI, polish

---

## Quick Start (Minimal Implementation)

If you want just the core functionality fast:

1. Create DB table for alerts
2. Add API endpoints (CRUD)
3. Add click handler on chart to create alert
4. Background loop checking price vs alerts
5. Send Telegram message via existing bot (if you have one)

This can be done in 1-2 hours for a basic version!

---

## Questions to Confirm Before Starting

1. **Do you already have a Telegram bot set up?** If yes, we can reuse it.
2. **What notification method do you prefer?** Telegram, phone push, or both?
3. **Should alerts expire?** (e.g., expire at options expiry, or stay until cancelled)
4. **Do you want repeating alerts?** (keeps notifying until cancelled)
5. **Should I start implementation now or save this plan for later?**
