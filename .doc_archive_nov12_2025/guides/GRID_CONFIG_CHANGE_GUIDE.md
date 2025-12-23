# Grid Configuration Change Guide

**Date:** November 11, 2025  
**Feature:** Clear Bot Memory for Safe Grid Configuration Changes

---

## Overview

When you change grid settings (boundaries or step size), the bot's memory must be cleared to prevent **off-grid errors** and **TP placement failures**. This guide explains the safe procedure.

---

## Why This is Needed

### The Problem:
- Bot stores positions/orders in memory based on **current grid**
- If you change grid settings while bot has memory of old grid:
  - Old orders exist at old grid prices
  - New calculations use new grid prices
  - **Result:** Off-grid errors, TP placement failures

### The Solution:
- **Manual order cancellation** on exchange (you have full control)
- **Clear Bot Memory** button (resets bot's internal state)
- Bot starts fresh with new grid configuration

---

## Step-by-Step Procedure

### 1️⃣ Cancel Orders on Exchange

**Go to Delta Exchange:**
1. Log into Delta Exchange
2. Navigate to "Open Orders"
3. Manually cancel **all open orders** for the trading pair
4. Verify all orders are cancelled

**Why manual?**
- ✅ You see exactly what you're cancelling
- ✅ You control the process
- ✅ No risk of API errors
- ✅ More reliable and trustworthy

---

### 2️⃣ Clear Bot Memory

**In WebUI:**
1. Go to Grid Configuration section
2. Click **"Clear Bot Memory"** button
3. Confirm the action when prompted

**What this does:**
- ✅ Backs up current state file (safety)
- ✅ Deletes state file
- ✅ Bot will start fresh on next cycle
- ✅ Sends Telegram notification

**What this does NOT do:**
- ❌ Does not cancel orders (you already did this)
- ❌ Does not close positions
- ❌ Does not stop the bot

**API Endpoint:**
```bash
POST /api/bot/clear-memory
```

**Example Response:**
```json
{
  "success": true,
  "message": "Bot memory cleared successfully",
  "trading_mode": "demo",
  "backup_created": true,
  "backup_path": "bot/state/demo_state_backup_1699999999.json"
}
```

---

### 3️⃣ Change Grid Configuration

**Update your settings:**
1. Lower Boundary: `$95,000` (new value)
2. Upper Boundary: `$115,000` (new value)
3. Grid Step Size: `$250` (new value)
4. Click **"Save Configuration"**

---

### 4️⃣ Bot Restarts Fresh

**Automatic behavior:**
- Bot detects no state file exists
- Initializes with new grid configuration
- Places initial orders on **new grid**
- Starts trading with clean slate

---

## UI Integration

### Configuration Panel Layout:

```
┌─────────────────────────────────────────────────┐
│  Grid Configuration                             │
├─────────────────────────────────────────────────┤
│                                                 │
│  Lower Boundary:  [$99,000]                     │
│  Upper Boundary:  [$110,000]                    │
│  Grid Step Size:  [$300]                        │
│  Position Size:   [0.001 BTC]                   │
│                                                 │
│  ⚠️ Before changing grid settings:              │
│                                                 │
│  Step 1: Cancel orders manually on exchange     │
│  Step 2: Click button below to clear memory     │
│  Step 3: Change configuration and save          │
│                                                 │
│  [🗑️ Clear Bot Memory]                          │
│                                                 │
│  [Save Configuration]                           │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## Confirmation Dialog

When user clicks "Clear Bot Memory":

```
┌─────────────────────────────────────────────────┐
│  Clear Bot Memory                               │
├─────────────────────────────────────────────────┤
│                                                 │
│  This will:                                     │
│  ✓ Delete bot's state file                     │
│  ✓ Clear position/order tracking               │
│  ✓ Create backup of current state              │
│                                                 │
│  This will NOT:                                 │
│  ✗ Cancel orders on exchange                   │
│  ✗ Close positions                             │
│  ✗ Stop the bot                                │
│                                                 │
│  ⚠️ Have you cancelled orders on exchange?      │
│                                                 │
│  [No, I'll do it first] [Yes, Clear Memory]    │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## When to Use This Feature

### Always Use Before:
✅ Changing grid lower/upper boundaries  
✅ Changing grid step size  
✅ Switching between different grid ranges  
✅ After manually closing positions on exchange  

### Not Needed For:
❌ Changing position size (same grid)  
❌ Changing leverage (same grid)  
❌ Changing Telegram settings  
❌ Adjusting risk parameters  

---

## Safety Features

### Backup System:
- **Automatic backup** created before deletion
- Backup filename: `{mode}_state_backup_{timestamp}.json`
- Located in: `bot/state/`
- Can be restored manually if needed

### Notifications:
- **Telegram alert** sent when memory cleared
- **WebUI confirmation** message
- **Logs** record the action

---

## Troubleshooting

### Problem: Button doesn't work
**Solution:**
- Check WebUI backend is running
- Check console for error messages
- Try refreshing the page

### Problem: State file not found
**Solution:**
- This is normal if bot was just started
- Click "Clear Memory" anyway (ensures clean state)
- Proceed with configuration change

### Problem: Bot still using old grid
**Solution:**
- Verify state file was actually deleted
- Check: `bot/state/{mode}_state.json`
- Restart bot if needed

---

## Example Scenario

### Changing Grid from $99k-$110k ($300 steps) to $95k-$115k ($250 steps):

**Current State:**
- 5 open orders on exchange
- 3 open positions
- Grid: $99,000 - $110,000, step $300

**Procedure:**
1. Go to Delta Exchange
2. Cancel all 5 orders manually
3. (Optionally close 3 positions)
4. Return to WebUI
5. Click "Clear Bot Memory"
6. Confirm action
7. Update grid config:
   - Lower: $95,000
   - Upper: $115,000
   - Step: $250
8. Click "Save Configuration"
9. Bot places new orders on new grid ✅

---

## Technical Details

### State File Locations:
- **Demo mode:** `bot/state/demo_state.json`
- **Live mode:** `bot/state/live_state.json`

### Backup Files:
- Format: `{mode}_state_backup_{unix_timestamp}.json`
- Example: `demo_state_backup_1699999999.json`

### API Endpoint Details:
```
Endpoint: POST /api/bot/clear-memory
Method: POST
Auth: None (local only)
Body: Empty

Response:
{
  "success": true|false,
  "message": "Description",
  "trading_mode": "demo"|"live",
  "backup_created": true|false,
  "backup_path": "relative/path/to/backup.json",
  "state_file_existed": true|false
}
```

---

## Best Practices

1. **Always cancel orders first** - Don't rely on automation
2. **Verify on exchange** - Check orders are actually gone
3. **Clear memory immediately after** - Don't wait
4. **Document changes** - Keep notes of old vs new grid
5. **Monitor first fills** - Watch bot behavior after change
6. **Keep backups** - Don't delete backup files immediately

---

## Integration with Existing Features

### Works With:
- PM2 process management
- Telegram notifications
- State file backup system
- Multi-mode support (demo/live)

### Compatible With:
- All grid configurations
- Any trading mode
- Any position size
- Any leverage setting

---

## Support

### If Issues Occur:

**1. Check logs:**
```bash
tail -f bot/logs/bot.log
pm2 logs gridbot-demo --lines 100
```

**2. Verify state file:**
```bash
ls -la bot/state/
```

**3. Check backups:**
```bash
ls -la bot/state/*backup*
```

**4. Manual cleanup if needed:**
```bash
# Backup state manually
cp bot/state/demo_state.json bot/state/manual_backup.json

# Delete state file
rm bot/state/demo_state.json
```

---

## Changelog

### v1.0 - November 11, 2025
- ✅ Initial implementation
- ✅ Automatic backup creation
- ✅ Telegram notifications
- ✅ Multi-mode support (demo/live)
- ✅ Safety confirmation dialog
- ✅ Comprehensive error handling

---

## Summary

**This feature solves the off-grid error problem** by providing a simple, safe, user-controlled way to reset bot memory when changing grid configuration.

**Key Points:**
- ✅ Simple: Just one button
- ✅ Safe: Creates automatic backups
- ✅ User-controlled: Manual order cancellation
- ✅ Reliable: No API dependencies
- ✅ Trustworthy: You see exactly what happens

**Workflow:**
1. Cancel orders (manual)
2. Clear memory (one button)
3. Change config
4. Bot starts fresh ✅

---

**Status:** ✅ IMPLEMENTED  
**Date:** November 11, 2025  
**Location:** `/api/bot/clear-memory` endpoint
