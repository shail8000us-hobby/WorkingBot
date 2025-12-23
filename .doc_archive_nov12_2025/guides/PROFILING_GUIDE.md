# Bot Profiling & Analysis Guide
**Created:** Nov 7, 2025  
**Purpose:** Debug throttle mechanism, race conditions, and performance

---

## 🚀 Quick Start

### 1. **Throttle Mechanism Analysis** (Recommended First)
```bash
./analyze_throttle.sh
```
**What it shows:**
- Throttle activations (30s gap enforcement)
- Order timing and sequence
- Missed fill detections
- Potential race conditions
- Real-time monitoring option

**Use when:** You want to verify throttle is working correctly

---

### 2. **Live Performance Profiling** (While Bot Running)
```bash
./profile_bot.sh
```
**Options:**
1. **Quick flame graph (30s)** - Best for quick overview
2. **Real-time top** - See live CPU usage by function
3. **Extended analysis (2min)** - Deep dive into performance
4. **Viztracer instructions** - Timeline visualization

**Use when:** Bot is slow or you want to optimize

---

## 📊 Detailed Tools

### **py-spy** (Zero-Overhead Profiling)
```bash
# Quick flame graph (30 seconds)
sudo /Users/ssr/Library/Python/3.9/bin/py-spy record \
    -o analysis/flame.svg \
    --pid $(pgrep -f "gridbot-live") \
    --duration 30

# Real-time top
sudo /Users/ssr/Library/Python/3.9/bin/py-spy top \
    --pid $(pgrep -f "gridbot-live")

# Include subprocesses (if any)
sudo /Users/ssr/Library/Python/3.9/bin/py-spy record \
    -o analysis/full.svg \
    --pid $(pgrep -f "gridbot-live") \
    --subprocesses
```

**Output:** SVG flame graph - open in browser  
**Best for:** Production profiling, finding bottlenecks

---

### **viztracer** (Timeline Visualization)
```bash
# Stop bot first
pm2 stop gridbot-live

# Record with viztracer
/Users/ssr/Library/Python/3.9/bin/viztracer \
    --log_async \
    --log_multithread \
    --max_stack_depth 10 \
    --output_file analysis/trace_$(date +%Y%m%d_%H%M%S).json \
    bot_launcher.py

# View results in browser
/Users/ssr/Library/Python/3.9/bin/viztracer --open analysis/trace_*.json
```

**Output:** Interactive timeline in browser  
**Best for:** Race condition debugging, understanding execution flow

**What you'll see:**
- Exact timing of every function call
- Thread interactions
- Order placement sequence
- Fill detection timing
- Throttle enforcement timing

---

### **snakeviz** (cProfile Visualization)
```bash
# Profile bot startup/execution
python3 -m cProfile -o analysis/bot.prof bot_launcher.py

# Visualize
/Users/ssr/Library/Python/3.9/bin/snakeviz analysis/bot.prof
```

**Output:** Interactive sunburst/icicle chart  
**Best for:** Detailed function call analysis

---

## 🎯 Specific Use Cases

### **Debug Race Conditions**
Use **viztracer** - it shows exact timeline:
```bash
pm2 stop gridbot-live
/Users/ssr/Library/Python/3.9/bin/viztracer \
    --log_async --log_multithread \
    --output_file analysis/race_debug.json \
    bot_launcher.py
```
Then look for:
- `_on_fill_processed` timing
- `ensure_single_correct_pending_buy` timing
- Order placement gaps

### **Verify 30s Throttle**
Use **analyze_throttle.sh**:
```bash
./analyze_throttle.sh
# Then choose real-time monitoring
```
Watch for "THROTTLE" messages showing gap enforcement

### **Find Performance Bottlenecks**
Use **py-spy** while bot running:
```bash
sudo /Users/ssr/Library/Python/3.9/bin/py-spy record \
    -o analysis/perf.svg \
    --pid $(pgrep -f "gridbot-live") \
    --duration 120
```
Open `analysis/perf.svg` in browser, look for wide bars

### **Monitor WebSocket Reconnections**
```bash
tail -f bot/logs/bot.log | grep -E "WebSocket|Reconnect|Syncing state"
```

---

## 📁 Output Files

All analysis files saved to: `~/Projects/WorkingBot/analysis/`

**File types:**
- `*.svg` - Flame graphs (open in browser)
- `*.json` - Viztracer timelines (use viztracer --open)
- `*.prof` - cProfile data (use snakeviz)

---

## 🔍 Reading Flame Graphs

**Flame Graph Basics:**
- **Width** = Time spent (wider = slower)
- **Height** = Call stack depth
- **Color** = Different modules (informational)

**What to look for:**
- Wide flat bars = Bottlenecks
- Tall stacks = Deep recursion
- Look for: `time.sleep`, `requests.get`, `WebSocket` operations

---

## ⚡ Performance Tips

**When profiling:**
1. Run for at least 30 seconds to get representative sample
2. Don't profile during bot startup (skews results)
3. Profile during active trading (with fills happening)
4. Compare before/after when making optimizations

**Common bottlenecks to check:**
- [ ] REST API calls (should have caching/rate limiting)
- [ ] JSON serialization (positions.json writes)
- [ ] WebSocket message processing
- [ ] Reconciliation loop (should be ~10s interval)

---

## 🚨 Troubleshooting

**"Permission denied" when running py-spy:**
```bash
sudo /Users/ssr/Library/Python/3.9/bin/py-spy ...
```
py-spy requires sudo to attach to processes

**"viztracer not found":**
```bash
export PATH="/Users/ssr/Library/Python/3.9/bin:$PATH"
```

**Bot crashes when using viztracer:**
- Reduce `--max_stack_depth` to 5
- Remove `--log_multithread` if single-threaded
- Add `--ignore_c_function` to skip C extensions

---

## 📚 Further Reading

- py-spy docs: https://github.com/benfred/py-spy
- viztracer docs: https://viztracer.readthedocs.io/
- Flame graph guide: http://www.brendangregg.com/flamegraphs.html

---

## ✅ Your Current Setup

**Tools installed:**
- ✅ py-spy (v0.4.1)
- ✅ viztracer (v0.15.6)
- ✅ snakeviz (v2.2.2)

**Scripts:**
- ✅ `./profile_bot.sh` - Interactive profiler
- ✅ `./analyze_throttle.sh` - Throttle analyzer

**Next steps:**
1. Run `./analyze_throttle.sh` to verify throttle working
2. Use `./profile_bot.sh` option 1 for quick performance check
3. If you see race conditions, use viztracer for detailed timeline
