#!/usr/bin/env python3
"""
WebUI & Guardian Integration - Quick Start Guide
================================================

This document explains how the Delta Exchange India improvements are
integrated with the WebUI and Guardian Bot.

Date: December 28, 2025
"""

## 🔄 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Guardian Bot                              │
│                                                                  │
│  ┌──────────────────┐    ┌────────────────────────────────┐   │
│  │ PositionMonitor  │───>│  monitor_cycle()               │   │
│  │                  │    │  - current_price               │   │
│  │  - fetch         │    │  - positions                   │   │
│  │  - calculate     │    │  - positions_pnl               │   │
│  │  - track         │    │  - total_summary               │   │
│  │                  │    │  ✨ liquidation_distance       │   │
│  └──────────────────┘    │  ✨ liquidation_details        │   │
│                          │  ✨ liquidation_critical       │   │
│                          │  ✨ liquidation_warning        │   │
│                          └────────────────────────────────┘   │
│                                      │                          │
│                                      ▼                          │
│                          ┌────────────────────────────────┐   │
│                          │  .guardian_health (JSON)       │   │
│                          │  + liquidation metrics         │   │
│                          └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                        WebUI Backend                             │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  position_liquidation.py (NEW)                          │   │
│  │                                                         │   │
│  │  📍 /api/positions/liquidation-metrics                 │   │
│  │     - Comprehensive liquidation status                  │   │
│  │     - Critical/Warning flags                            │   │
│  │     - Bankruptcy distance                               │   │
│  │                                                         │   │
│  │  📍 /api/positions/monitor-cycle                       │   │
│  │     - Full monitor_cycle() output                       │   │
│  │     - All position data                                 │   │
│  │     - Complete PnL breakdown                            │   │
│  └────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                              ┌──────────────┐
                              │ WebUI        │
                              │ Frontend     │
                              │ (React)      │
                              └──────────────┘
```

## 🚀 Quick Start

### 1. Restart Services

```bash
# Restart Guardian Bot to use new position_monitor improvements
pm2 restart guardian-live

# Restart WebUI backend to load new API endpoints
pm2 restart webui-backend

# Check both are running
pm2 status
```

### 2. Test API Endpoints

```bash
# Test liquidation metrics endpoint
curl http://localhost:5555/api/positions/liquidation-metrics | jq

# Test full monitor cycle endpoint
curl http://localhost:5555/api/positions/monitor-cycle | jq
```

### 3. View in WebUI

Open http://localhost:5555 and navigate to:
- Positions Dashboard → Will show liquidation metrics
- Risk & Safety Dashboard → Will include critical/warning flags

## 📊 API Response Examples

### `/api/positions/liquidation-metrics`

```json
{
  "success": true,
  "timestamp": "2025-12-28T10:30:00",
  "current_price": 80000.0,
  "liquidation_distance": 5.2,
  "bankruptcy_distance": 6.1,
  "liquidation_critical": false,
  "liquidation_warning": true,
  "risk_zone": "WARNING",
  "positions_count": 2,
  "total_pnl_inr": 500.0,
  "liquidation_details": [
    {
      "symbol": "BTC/USD:USD",
      "side": "LONG",
      "size": 100,
      "entry_price": 78500.0,
      "current_price": 80000.0,
      "liquidation_price": 76000.0,
      "bankruptcy_price": 75500.0,
      "liquidation_distance_pct": 5.0,
      "bankruptcy_distance_pct": 5.625,
      "margin": 800.0,
      "is_critical": false,
      "is_warning": true
    },
    {
      "symbol": "BTC/USD:USD",
      "side": "SHORT",
      "size": 50,
      "entry_price": 81000.0,
      "current_price": 80000.0,
      "liquidation_price": 82560.0,
      "bankruptcy_price": 82900.0,
      "liquidation_distance_pct": 3.2,
      "bankruptcy_distance_pct": 3.625,
      "margin": 400.0,
      "is_critical": true,
      "is_warning": true
    }
  ]
}
```

## 🔧 Integration Points

### Guardian Health File

The Guardian now writes liquidation metrics to `.guardian_health`:

```json
{
  "guardian_version": "2.0-SQL",
  "status": "running",
  "signal": "GO",
  "positions": {
    "count": 2,
    "current_price": 80000.0,
    "total_pnl_inr": 500.0
  },
  "liquidation": {
    "distance": 5.2,
    "critical": false,
    "warning": true,
    "details_count": 2,
    "bankruptcy_distance": 6.1
  }
}
```

### WebUI Backend Routes

New blueprint registered in `app.py`:
- `position_liquidation_bp` - Exposes Delta India improvements
- Wired via `app.wire_guardian_bot(guardian_instance)`

## 📝 Files Modified

1. `bot/guardian/collectors/position_monitor.py` - Delta India improvements
2. `bot/guardian/core/guardian_bot.py` - Health file updates
3. `webui/backend/routes/position_liquidation.py` - New API endpoints
4. `webui/backend/app.py` - Blueprint registration & wiring

## ✅ Verification Checklist

- [ ] Guardian running: `pm2 status guardian-live`
- [ ] Backend running: `pm2 status webui-backend`
- [ ] API responding: `curl localhost:5555/api/positions/liquidation-metrics`
- [ ] Health file updated: `cat .guardian_health | jq .liquidation`
- [ ] No errors in logs: `pm2 logs guardian-live --lines 50`
- [ ] No errors in logs: `pm2 logs webui-backend --lines 50`

## 🎯 Next Steps

1. **Frontend Integration** - Update React components to display:
   - Liquidation distance gauge
   - Critical/Warning badges
   - Per-position liquidation table
   - Bankruptcy distance indicator

2. **Alerts** - Configure Telegram alerts for:
   - Critical liquidation distance (< 1%)
   - Warning liquidation distance (< 5%)
   - Rapid distance changes

3. **Monitoring** - Add WebUI dashboard panels:
   - Real-time liquidation distance chart
   - Position-by-position risk table
   - Historical liquidation distance trends

---

**Integration Complete! 🎉**

All Delta Exchange India improvements are now accessible via:
- WebUI API endpoints
- Guardian health file
- Real-time position monitoring

