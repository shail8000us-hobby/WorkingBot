# Options Trading Module - User Guide

**Version:** 1.4  
**Created:** January 4, 2026  
**Last Updated:** January 4, 2026  
**Status:** Production Ready (MVP + Enhancements)

---

## 📋 Quick Overview

The Options Trading Module allows you to **manage options positions opened on Delta Exchange** directly from the bot's WebUI. This is designed for **expiry trading** where you need fast, one-click position adjustments.

### What You Can Do
| Action | Description | Access |
|--------|-------------|--------|
| ✅ View Positions | See all options positions with real-time PnL | Automatic |
| ✅ Sorted by Expiry | Nearest expiry first, farthest last | Automatic |
| ✅ Close Position | Exit entire position (market order) | CLOSE button |
| ✅ Add to Position | Increase/decrease existing position | +/- buttons |
| ✅ Quick Size Presets | One-click size selection (1, 2, 5, 10, 20, 50) | Size dialog |
| ✅ Keyboard Shortcuts | B=Buy, S=Sell, C=Close, R=Refresh | Anywhere in panel |
| ✅ Maker Orders | Place limit orders at mid-price for lower fees | Default mode |
| ✅ Quick Mode | Skip confirmation dialog for instant orders | "Don't Ask Again" button |

### What You Cannot Do (Yet)
| Action | Status | Workaround |
|--------|--------|------------|
| ❌ Open NEW positions | Not in MVP | Open manually on Delta Exchange |
| ❌ Options chain selector | Not in MVP | Select on Delta Exchange |
| ❌ Strike/expiry picker | Not in MVP | Manual entry not supported |

---

## 🚀 Getting Started

### 1. Access the Options Panel
1. Open WebUI at http://localhost:5555
2. Click **📈 Options** in the sidebar navigation
3. Your options positions will load automatically

### 2. Understanding the Display

```
┌──────────────────────────────────────────────────────────────────────┐
│  📈 Options Positions                    [Guardian: GO] [🔄 Refresh] │
├──────────────────────────────────────────────────────────────────────┤
│  Total PnL: +$123.45                                                 │
├──────────────────────────────────────────────────────────────────────┤
│  Symbol          │ Type │ Size │ Entry  │ Mark   │ PnL      │ Actions│
├──────────────────┼──────┼──────┼────────┼────────┼──────────┼────────┤
│  C-BTC-113000-30 │ CALL │ -40  │ $190   │ $206   │ -$0.66   │ [+][-] │
│  P-BTC-90000-300 │ PUT  │ +20  │ $85    │ $78    │ -$0.14   │ [CLOSE]│
└──────────────────────────────────────────────────────────────────────┘
```

#### Column Meanings
| Column | Description |
|--------|-------------|
| **Symbol** | Option contract (e.g., C-BTC-113000-300126 = Call, BTC, Strike $113k, Expiry 30-Jan-26) |
| **Type** | CALL (blue) or PUT (purple) |
| **Size** | Number of contracts. Positive = long, Negative = short |
| **Entry** | Your average entry price |
| **Mark** | Current mark price (updates every 5s) |
| **PnL** | Unrealized profit/loss in USD |
| **Actions** | +/- buttons to adjust position, CLOSE to exit |

---

## 💡 Key Features

### 1. One-Click Close
To close an entire position:
1. Click **CLOSE** button on the position row
2. Review the confirmation dialog
3. Click **Confirm Close**

The order executes as a **market order** for immediate fill.

### 2. Add to Position (With Quick Presets)
To increase or decrease a position:
1. Click **+** (buy more) or **-** (sell/reduce) button
2. Use **Quick Size Presets**: 1, 2, 5, 10, 20, 50
3. Or use **% Adjustments**: 25%, 50%, 100%, 200% of current size
4. Select **Order Type**: Maker First (default) or Market
5. Click **Confirm**

### 3. Keyboard Shortcuts
When the Options panel is active (not typing in a field):

| Key | Action |
|-----|--------|
| **B** | Buy (opens add dialog for first position) |
| **S** | Sell (opens add dialog for first position) |
| **C** | Close (opens close dialog for first position) |
| **R** | Refresh positions immediately |
| **Esc** | Close any open dialog |

### 4. Order Types

| Type | Fees | Fill Speed | Best For |
|------|------|------------|----------|
| **Smart (Maker First)** (default) | Lower (maker rebate) | 2s delay, then fallback | Normal trading |
| **Market Only** | Higher (taker fee) | Immediate | Expiry rush |

**Smart Order Logic:**
1. Places limit order at mid-price (bid+ask)/2
2. Waits 2 seconds for fill
3. If not filled → cancels and uses market order

### 5. Quick Mode (Don't Ask Again)

For rapid trading during expiry, you can enable **Quick Mode** per strike:

1. Click **+** on any position to open the dialog
2. Configure your order (default: 5 lots, Sell, Smart)
3. Click **"Don't Ask Again"** instead of the normal confirm button
4. Now the ⚡ icon appears next to that strike
5. Future **+** clicks on this strike execute instantly (5 lots, Sell, Smart)

**To disable Quick Mode:**
- Click the ⚡ icon next to the strike
- Future clicks will show the confirmation dialog again

**Quick Mode persists across browser refreshes** (saved in localStorage).

---

## 🛡️ Safety Features

### Guardian Integration
- **GO** (green badge): Trading allowed
- **STOP** (red badge): All trading blocked

When Guardian is STOP, all Close/Add buttons are disabled.

### Rate Limiting
- **2-second cooldown** between orders
- Prevents accidental double-clicks
- Shows countdown if you click too fast

### Confirmation Dialogs
- Every order requires confirmation
- Shows position size, symbol, and current PnL
- Cancel button always available

### Liquidity Warnings
- **Warning** for spread > 10%
- Still allows order but shows warning
- Protects against poor fills

### Expiry Warnings
| Time to Expiry | Alert |
|----------------|-------|
| < 1 hour | 🔴 CRITICAL (red badge) |
| < 24 hours | 🟡 WARNING (yellow badge) |
| > 24 hours | No badge |

---

## 📊 Understanding Options Symbols

Delta Exchange uses this format:
```
[C/P]-[UNDERLYING]-[STRIKE]-[EXPIRY]

Examples:
C-BTC-113000-300126  = Call, BTC, Strike $113,000, Expires 30 Jan 2026
P-BTC-90000-270226   = Put, BTC, Strike $90,000, Expires 27 Feb 2026
```

The panel automatically parses this for display:
- **C** = Call (blue)
- **P** = Put (purple)
- Strike formatted with $ sign
- Expiry shown as DD/MM/YYYY

---

## 🔧 Configuration

Options settings in `config.yaml`:

```yaml
options:
  enabled: true
  polling_interval_seconds: 5    # How often to refresh positions
  rate_limit_seconds: 2          # Cooldown between orders
  max_spread_pct: 10.0           # Liquidity warning threshold
  guardian_integration: true     # Respect Guardian GO/STOP
  expiry_warning_hours: 24       # When to show expiry warnings
  liquidity_check: true          # Check spread before orders
```

---

## 🎯 Expiry Day Trading Tips

### Before Expiry
1. Set browser to Options panel
2. Learn keyboard shortcuts (B, S, C, R)
3. Test with small position first
4. Check Guardian signal is GO

### During Expiry Rush
1. Use **Market Only** order type for guaranteed fills
2. Use keyboard shortcuts for speed
3. Use quick size presets (don't type)
4. Watch the 2-second rate limit

### Closing Multiple Positions
1. Select positions using checkboxes
2. Click **Close X Selected**
3. Confirm bulk close
4. Orders execute with 2s delay between each

---

## 🔍 Troubleshooting

### Position Not Appearing
1. Wait 5 seconds (auto-refresh interval)
2. Click Refresh button (or press R)
3. Check if position exists on Delta Exchange
4. Check bot logs: `pm2 logs gridbot-live`

### Order Failed
| Error | Solution |
|-------|----------|
| "Rate limited" | Wait 2 seconds and retry |
| "Guardian is STOP" | Wait for Guardian to signal GO |
| "Position not found" | Refresh positions, position may be closed |
| "Low liquidity" | Order will still work, just a warning |
| Network error | Check backend is running |

### Backend Issues
```bash
# Check backend status
lsof -i :5555 | grep LISTEN

# Restart backend via LaunchAgent (recommended)
launchctl stop com.gridbot.webui
rm -f /Users/ssr/Projects/WorkingBot/webui/backend/.webui.lock
launchctl start com.gridbot.webui

# Or restart manually
pkill -f "python3 -m webui.backend.app"
cd /Users/ssr/Projects/WorkingBot
python3 -m webui.backend.app &

# Check logs
tail -50 /Users/ssr/Projects/WorkingBot/bot_live.log
```

### Connection Errors
| Error | Cause | Solution |
|-------|-------|----------|
| "INTERNAL SERVER ERROR" | Transient API failure | Auto-retries with cached data |
| "Connection error: websocket" | WebSocket disconnected | Page will auto-reconnect |
| "⚠️ Using cached data" | API temporarily failed | Data shown may be 3-5s old |

---

## 📁 File Structure

```
WorkingBot/
├── bot/options/
│   └── utils/
│       └── options_helper.py       # PnL calculations, expiry checks
├── webui/backend/routes/options/
│   └── options_control.py          # API endpoints
├── webui/frontend/src/components/options/
│   ├── OptionsPanel.js             # Main React component
│   └── index.js                    # Export
├── tests/options/
│   ├── test_api_methods.py         # Unit tests
│   └── test_integration.py         # Integration tests
└── Documentation/
    └── OPTIONS_TRADING_USER_GUIDE.md  # This file
```

---

## 📈 API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/options/status` | Module status & Guardian signal |
| GET | `/api/options/positions` | All options positions (enriched) |
| GET | `/api/options/ticker/<symbol>` | Ticker for specific option |
| POST | `/api/options/close` | Close position |
| POST | `/api/options/add` | Add to position |

### Example: Get Positions
```bash
curl http://localhost:5555/api/options/positions
```

Response:
```json
{
  "success": true,
  "positions": [
    {
      "product_symbol": "C-BTC-113000-300126",
      "size": -40,
      "entry_price": 190.0,
      "mark_price": 206.51,
      "unrealized_pnl": -0.6604,
      "pnl_pct": -8.69,
      "contract_type": "call_options"
    }
  ],
  "count": 9,
  "timestamp": "2026-01-04 13:30:00",
  "cached": false
}
```

### Example: Close Position
```bash
curl -X POST http://localhost:5555/api/options/close \
  -H "Content-Type: application/json" \
  -d '{"symbol": "C-BTC-113000-300126", "confirm": true}'
```

---

## ✅ Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 4, 2026 | Initial MVP release |
| 1.1 | Jan 4, 2026 | Added maker orders, quick presets, keyboard shortcuts |
| 1.2 | Jan 4, 2026 | Fixed error handling, added caching, concurrent ticker fetch |
| 1.3 | Jan 4, 2026 | Fixed order placement API, improved defaults |
| 1.4 | Jan 4, 2026 | Sort by expiry, Quick Mode for instant orders |

### v1.4 Technical Improvements
- **Sorted by expiry**: Positions now sorted by days to expiration (nearest first)
- **Quick Mode**: "Don't Ask Again" button skips confirmation for future orders on that strike
- **Visual indicators**: ⚡ icon shows which strikes have Quick Mode enabled
- **Expiry highlighting**: Red/orange colors for positions expiring soon (< 1 day / < 7 days)
- **Persistent settings**: Quick Mode preferences saved in localStorage

### v1.3 Technical Improvements
- **Fixed order placement**: Now uses `product_symbol` for options (not `product_id`)
- **Fixed quotes parsing**: Correctly reads bid/ask from `ticker.raw.quotes`
- **New defaults**: 5 lots, Sell side, Smart (maker_first) order type pre-selected
- **All order types verified working**:
  - `market_only`: Immediate fill at market price
  - `maker_first`: Limit at mid-price, 2s wait, fallback to market
  - `maker_only`: Limit at mid-price, returns immediately

### v1.2 Technical Improvements
- **Concurrent ticker fetching**: Positions load 3x faster (2.6s → 0.9s)
- **Position caching**: Returns cached data on API failures (3s cache)
- **Graceful error handling**: Shows warning instead of error when cached data available
- **aria-hidden fix**: Fixed accessibility warning in dialogs
- **Port standardization**: Frontend now defaults to port 5555

---

## 🤝 Support

- **Logs:** `pm2 logs gridbot-live`
- **Tests:** `python3 tests/options/test_integration.py`
- **Config:** `config.yaml` → `options:` section

---

**Happy Trading! 🚀**
