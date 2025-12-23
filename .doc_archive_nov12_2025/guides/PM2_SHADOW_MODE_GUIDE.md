# Phase 2+3 Shadow Mode with PM2 - Quick Start

## ✅ YES! You can use PM2 with Shadow Mode

**Your Workflow:**
1. Start bot with PM2 (normal way)
2. Run shadow mode script
3. Monitor with dashboard

This is **PERFECT** and **RECOMMENDED**! PM2 provides:
- ✅ Auto-restart on crashes
- ✅ Log management
- ✅ Process monitoring
- ✅ Easy start/stop

---

## Step-by-Step Commands

### 1️⃣ Start Your Bot with PM2 (As Normal)

```bash
# For LIVE trading
pm2 start ecosystem.config.js --only gridbot-live

# OR for DEMO/testnet
pm2 start ecosystem.config.js --only gridbot-demo

# Verify it's running
pm2 list
```

Expected output:
```
┌─────┬────────────────┬─────────┬─────────┬─────────┬──────────┐
│ id  │ name           │ status  │ restart │ uptime  │ cpu      │
├─────┼────────────────┼─────────┼─────────┼─────────┼──────────┤
│ 0   │ gridbot-live   │ online  │ 0       │ 5m      │ 2%       │
└─────┴────────────────┴─────────┴─────────┴─────────┴──────────┘
```

✅ **Bot is running normally - ready for shadow mode!**

---

### 2️⃣ Start Shadow Mode (Terminal 1)

```bash
./scripts/start_shadow_mode.sh
```

This will:
1. ✅ Detect PM2 bot is running
2. ✅ Run all 22 tests
3. ✅ Create backup
4. ✅ Start async system (read-only)
5. ✅ Begin 24h comparison

---

### 3️⃣ Open Dashboard (Terminal 2)

Open a **NEW terminal** and run:

```bash
./scripts/shadow_mode_dashboard.sh
```

You'll see real-time metrics updating every 10 seconds:
```
╔════════════════════════════════════════════════════════╗
║     Phase 2+3 Shadow Mode Deployment Dashboard        ║
╚════════════════════════════════════════════════════════╝

═══ System Health ═══
Async System:    RUNNING
Threaded System: RUNNING (PM2: gridbot-live)
Snapshot Age:    15s

═══ Progress to 24h Target ═══
[=========>                                    ] 19%

═══ Deployment Status ═══
Duration:        275 minutes
Comparisons:     275

Match Rate:      99.6% ⚠️  INVESTIGATE DISCREPANCIES

═══ Details ═══
Matches:         274
Discrepancies:   1
Async Errors:    0
Threaded Errors: 0
```

---

## What Happens During Shadow Mode?

### Your PM2 Bot (PRIMARY)
- ✅ Continues trading normally
- ✅ Handles all buy/sell operations
- ✅ Updates runtime_state.json
- ✅ PM2 monitors and auto-restarts if needed
- ✅ Zero changes to behavior

### Async System (OBSERVER)
- 📖 Reads state from runtime_state.json
- 📖 Compares with its own calculations
- 📖 Logs any differences
- 📖 Never places orders
- 📖 Cannot affect your trading

---

## PM2 Commands During Shadow Mode

### Check Bot Status
```bash
pm2 list
# Shows both gridbot and async system
```

### View Bot Logs
```bash
# Live bot logs
pm2 logs gridbot-live

# Or specific log files
pm2 logs gridbot-live --lines 100
```

### Restart Bot (if needed)
```bash
pm2 restart gridbot-live
# Shadow mode continues running!
```

### Stop Shadow Mode
```bash
# In Terminal 1 (shadow mode), press:
Ctrl+C

# PM2 bot continues running - no impact!
```

---

## Safety Guarantees with PM2

✅ **PM2 Bot is Protected:**
- Shadow mode only reads state
- Cannot interfere with PM2 process
- Cannot place orders
- Cannot modify files

✅ **If Shadow Mode Crashes:**
- PM2 bot continues normally
- Zero impact to trading
- Can restart shadow mode anytime

✅ **If PM2 Bot Crashes:**
- PM2 auto-restarts it
- Shadow mode detects it's back up
- Comparison continues

✅ **Stop Anytime:**
- Press Ctrl+C in shadow mode terminal
- PM2 bot keeps running
- Resume later: `./scripts/start_shadow_mode.sh`

---

## After 24 Hours

### Check Results
```bash
# View final report
cat logs/shadow_mode_report.json

# See match rate
jq '.match_rate, .stats' logs/shadow_mode_report.json
```

### If Match Rate ≥99.9% ✅
```bash
# Proceed to validation mode
python3 scripts/migrate_to_async.py --mode validation --duration 168
```

### If Match Rate <99.9% ⚠️
```bash
# Review discrepancies
jq '.recent_discrepancies' logs/shadow_mode_report.json

# Fix async code
# Re-run shadow mode
./scripts/start_shadow_mode.sh
```

---

## PM2 + Shadow Mode Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    YOUR SYSTEM                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────┐      ┌──────────────────────┐ │
│  │   PM2 Process       │      │  Shadow Mode         │ │
│  │   Manager           │      │  (Terminal 1)        │ │
│  └──────┬──────────────┘      └──────┬───────────────┘ │
│         │                             │                 │
│         ▼                             ▼                 │
│  ┌─────────────────────┐      ┌──────────────────────┐ │
│  │  Threaded GridBot   │◄─────┤  Async System        │ │
│  │  (PRIMARY)          │      │  (READ-ONLY)         │ │
│  │                     │      │                      │ │
│  │  • Places orders    │      │  • Reads state       │ │
│  │  • Updates state    │      │  • Compares results  │ │
│  │  • PM2 managed      │      │  • Logs diffs        │ │
│  └─────────────────────┘      └──────────────────────┘ │
│         │                             │                 │
│         ▼                             │                 │
│  runtime_state.json ◄─────────────────┘                │
│  (Both read this file)                                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Example Session

**Terminal 1:**
```bash
# Start PM2 bot
pm2 start ecosystem.config.js --only gridbot-live
pm2 list  # Verify running

# Start shadow mode
./scripts/start_shadow_mode.sh

# Output:
# ✅ Threaded bot is running (PM2: gridbot-live)
# ✅ All 22 tests passing
# ✅ Backed up runtime_state.json to state_backups/pre_shadow_20251111_143022/
# 🚀 Starting shadow mode...
# [Runs for 24 hours]
```

**Terminal 2:**
```bash
# Watch dashboard
./scripts/shadow_mode_dashboard.sh

# Dashboard updates every 10 seconds
# Shows: Match rate, discrepancies, system health
```

**After 24 hours (Terminal 1):**
```
🎉 SHADOW MODE COMPLETE
Duration: 1440.2 minutes
Comparisons: 1440
Matches: 1438 (99.86%)
Discrepancies: 2
Async Errors: 0
Threaded Errors: 0
════════════════════════════════════════════════════════
✅ READY FOR CUTOVER - Match rate excellent (≥99.9%)
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `pm2 start ecosystem.config.js --only gridbot-live` | Start bot |
| `pm2 list` | Check status |
| `pm2 logs gridbot-live` | View bot logs |
| `./scripts/start_shadow_mode.sh` | Start shadow mode |
| `./scripts/shadow_mode_dashboard.sh` | Monitor deployment |
| `Ctrl+C` (Terminal 1) | Stop shadow mode |
| `pm2 restart gridbot-live` | Restart bot |
| `cat logs/shadow_mode_report.json` | View results |

---

## FAQ

**Q: Will shadow mode interfere with PM2?**  
A: No! Shadow mode only reads files. PM2 continues normally.

**Q: Can I restart the PM2 bot during shadow mode?**  
A: Yes! Shadow mode will detect it and continue comparing.

**Q: What if PM2 bot crashes?**  
A: PM2 auto-restarts it. Shadow mode waits and resumes.

**Q: Can I run pm2 restart while shadow mode is running?**  
A: Yes! Completely safe. Shadow mode adapts.

**Q: How do I know shadow mode is working?**  
A: Dashboard shows "Comparisons" increasing every 60s.

**Q: Can I check PM2 logs during shadow mode?**  
A: Yes! `pm2 logs gridbot-live` - won't affect anything.

**Q: Do I need to stop PM2 before shadow mode?**  
A: NO! Keep PM2 running. That's the whole point!

---

## ✅ Ready to Deploy!

**Your workflow is PERFECT:**

1. `pm2 start ecosystem.config.js --only gridbot-live`
2. `./scripts/start_shadow_mode.sh`
3. Open new terminal: `./scripts/shadow_mode_dashboard.sh`
4. Wait 24 hours
5. Review report

**This is the safest possible deployment approach!** 🚀

---

For more details, see:
- `SHADOW_MODE_DEPLOYMENT_GUIDE.md` - Complete guide
- `DEPLOYMENT_READY.md` - Quick reference
- `PHASE_2_3_TEST_RESULTS.md` - Test validation
