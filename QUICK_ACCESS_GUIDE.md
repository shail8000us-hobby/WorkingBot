================================================================================
🚀 QUICK ACCESS GUIDE - Liquidation Metrics WebUI
================================================================================

## 📍 API Endpoints (Ready to Use)

### 1. Liquidation Metrics Summary
```bash
curl http://localhost:5555/api/positions/liquidation-metrics | jq
```

**Returns:**
- liquidation_distance (minimum across all positions)
- liquidation_critical (< 1% = true)
- liquidation_warning (< 5% = true)
- bankruptcy_distance
- positions_count
- current_price
- total_pnl_inr
- risk_zone (CRITICAL/WARNING/SAFE)

---

### 2. Full Monitor Cycle Data
```bash
curl http://localhost:5555/api/positions/monitor-cycle | jq
```

**Returns:**
- Guardian signal (GO/STOP)
- All liquidation metrics
- Position count and PnL
- Current price

---

## 🎯 Risk Zones Explained

| Risk Zone | Liquidation Distance | Critical | Warning | Action |
|-----------|---------------------|----------|---------|---------|
| **CRITICAL** | < 1% | ✅ true | ✅ true | IMMEDIATE: Close/reduce positions |
| **WARNING** | 1-5% | ❌ false | ✅ true | CAUTION: Monitor closely |
| **SAFE** | > 5% | ❌ false | ❌ false | NORMAL: Continue trading |

---

## 🔄 Service Management

### Restart Guardian Bot
```bash
pm2 restart guardian-live
pm2 logs guardian-live --lines 50
```

### Restart WebUI Backend
```bash
launchctl kickstart -k gui/$(id -u)/com.gridbot.webui
# Check logs in webui/backend/logs/
```

### Check Status
```bash
pm2 status
launchctl list | grep gridbot.webui
```

---

## 🏥 Health Check

### Check Guardian Health File
```bash
cat .guardian_health | jq
```

### Check API Availability
```bash
curl -s http://localhost:5555/api/positions/liquidation-metrics | jq .success
# Should return: true
```

---

## 📊 Example Use Cases

### 1. Monitor Liquidation Distance
```bash
# Get current liquidation distance
curl -s http://localhost:5555/api/positions/liquidation-metrics | jq .liquidation_distance

# Check if in critical zone
curl -s http://localhost:5555/api/positions/liquidation-metrics | jq .liquidation_critical

# Get risk zone
curl -s http://localhost:5555/api/positions/liquidation-metrics | jq .risk_zone
```

### 2. Continuous Monitoring
```bash
# Watch liquidation distance every 5 seconds
watch -n 5 'curl -s http://localhost:5555/api/positions/liquidation-metrics | jq "{distance: .liquidation_distance, risk: .risk_zone, critical: .liquidation_critical}"'
```

### 3. Alert Script
```bash
#!/bin/bash
# alert_liquidation.sh - Get alert when liquidation distance drops below 5%

while true; do
  DISTANCE=$(curl -s http://localhost:5555/api/positions/liquidation-metrics | jq -r .liquidation_distance)
  WARNING=$(curl -s http://localhost:5555/api/positions/liquidation-metrics | jq -r .liquidation_warning)
  
  if [ "$WARNING" = "true" ]; then
    echo "⚠️ WARNING: Liquidation distance at ${DISTANCE}%"
    # Add your notification logic here (Telegram, email, etc.)
  else
    echo "✅ Safe: Liquidation distance at ${DISTANCE}%"
  fi
  
  sleep 10
done
```

---

## 🔧 Troubleshooting

### Issue: API returns "Guardian health file not found"
**Solution:**
```bash
# Check if Guardian is running
pm2 status guardian-live

# Restart Guardian
pm2 restart guardian-live

# Wait 10 seconds for health file
sleep 10
cat .guardian_health
```

### Issue: API returns old data
**Solution:**
```bash
# Restart WebUI backend
launchctl kickstart -k gui/$(id -u)/com.gridbot.webui

# Test again
curl http://localhost:5555/api/positions/liquidation-metrics
```

### Issue: Empty positions (liquidation_distance = 100.0)
**Meaning:** No open positions - this is normal when no trades are active
**Action:** Start GridBot to open positions, then metrics will populate

---

## 📝 Integration Checklist

- [x] Guardian Bot running
- [x] WebUI Backend running  
- [x] Health file updating (.guardian_health)
- [x] API endpoints responding
- [x] Liquidation metrics populated
- [x] Tests passing (3/3)

---

## 🎉 Next Steps

### Frontend Development
Create React components to display:
1. Liquidation distance gauge (circular progress)
2. Risk zone badge (colored: red/yellow/green)
3. Per-position liquidation table
4. Bankruptcy distance indicator
5. Real-time updates

### Example React Component
```javascript
// LiquidationDashboard.jsx
import { useState, useEffect } from 'react';

function LiquidationDashboard() {
  const [metrics, setMetrics] = useState(null);
  
  useEffect(() => {
    const fetchMetrics = async () => {
      const response = await fetch('/api/positions/liquidation-metrics');
      const data = await response.json();
      setMetrics(data);
    };
    
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000); // Update every 5s
    return () => clearInterval(interval);
  }, []);
  
  if (!metrics) return <div>Loading...</div>;
  
  return (
    <div className="liquidation-dashboard">
      <h2>Liquidation Risk Monitor</h2>
      
      <div className={`risk-zone ${metrics.risk_zone.toLowerCase()}`}>
        Risk Zone: {metrics.risk_zone}
      </div>
      
      <div className="metric">
        <span>Liquidation Distance:</span>
        <strong>{metrics.liquidation_distance.toFixed(2)}%</strong>
      </div>
      
      <div className="metric">
        <span>Bankruptcy Distance:</span>
        <strong>{metrics.bankruptcy_distance.toFixed(2)}%</strong>
      </div>
      
      {metrics.liquidation_critical && (
        <div className="alert critical">
          🚨 CRITICAL: Liquidation distance below 1%!
        </div>
      )}
      
      {metrics.liquidation_warning && !metrics.liquidation_critical && (
        <div className="alert warning">
          ⚠️ WARNING: Liquidation distance below 5%
        </div>
      )}
    </div>
  );
}
```

---

## ✅ All Set!

Your WebUI is now fully integrated with Delta Exchange India improvements.

**Access the API and start monitoring liquidation metrics! 🚀**

================================================================================
