# Profiling Tools - Quick Reference

## ✅ Installed Tools

| Tool | Version | Purpose |
|------|---------|---------|
| **py-spy** | 0.4.1 | Zero-overhead live profiling |
| **viztracer** | 0.15.6 | Timeline visualization & race condition debugging |
| **snakeviz** | 2.2.2 | Interactive cProfile visualization |

---

## 🚀 Created Scripts

### 1. **./profile_bot.sh** - Interactive Profiler
```bash
./profile_bot.sh
```
Menu-driven profiling:
- Quick flame graph (30s)
- Real-time CPU monitoring
- Extended analysis (2min)
- Viztracer instructions

### 2. **./analyze_throttle.sh** - Throttle Verifier
```bash
./analyze_throttle.sh
```
Shows:
- Throttle activations (30s gap)
- Order timing
- Missed fills
- Real-time monitoring

### 3. **./detect_race_conditions.sh** - Race Detector
```bash
./detect_race_conditions.sh
```
Analyzes:
- Duplicate orders
- Rapid order placement
- Fill processing sequence
- Mutex lock activity

---

## 📊 Common Commands

### Quick Performance Check
```bash
# 30-second flame graph (while bot running)
./profile_bot.sh   # Choose option 1
```

### Verify Throttle Working
```bash
./analyze_throttle.sh   # Then 'y' for real-time
# Watch for "THROTTLE" messages every <30s order attempt
```

### Debug Race Conditions
```bash
# Full timeline analysis
pm2 stop gridbot-live
/Users/ssr/Library/Python/3.9/bin/viztracer \
    --log_async --log_multithread \
    --output_file analysis/race_$(date +%Y%m%d).json \
    bot_launcher.py
```

### Check Current Performance
```bash
# Live top-style view
sudo /Users/ssr/Library/Python/3.9/bin/py-spy top \
    --pid $(pgrep -f "gridbot-live")
```

---

## 🎯 Use Cases

| Problem | Tool | Command |
|---------|------|---------|
| Bot slow? | py-spy | `./profile_bot.sh` (option 1) |
| Throttle working? | analyze_throttle.sh | `./analyze_throttle.sh` |
| Race condition? | viztracer | See "Debug Race Conditions" above |
| Duplicate orders? | detect_race_conditions.sh | `./detect_race_conditions.sh` |
| Memory leak? | py-spy | `./profile_bot.sh` (option 3) |

---

## 📁 Output Location

All analysis files: `~/Projects/WorkingBot/analysis/`

View flame graphs: Open `.svg` files in browser  
View timelines: `/Users/ssr/Library/Python/3.9/bin/viztracer --open file.json`

---

## 📖 Full Documentation

See: `PROFILING_GUIDE.md`

