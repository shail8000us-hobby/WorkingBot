# Volatility Database Management - Quick Reference

## 🎯 Key Points

### Volatility Data is SPECIAL:
- ✅ **NOT deleted after 48 hours** (unlike other data)
- ✅ **Managed by SIZE** - 500MB limit
- ✅ **Kept for long-term analysis** - important for trading decisions
- ✅ **Auto-cleaned when exceeds 500MB** - oldest 30% deleted

---

## 📊 How It Works

### Current Status:
```
Database: data/volatility.db
Size: 53.33MB
Limit: 500MB
Status: ✅ Under limit (446.67MB remaining)
```

### Cleanup Trigger:
```
IF volatility.db > 500MB:
    1. Delete oldest 30% of records from all tables
    2. Run VACUUM to reclaim space
    3. Verify size is back under limit
ELSE:
    Skip cleanup - database healthy
```

### Tables Managed:
- `iv_snapshots` - Implied volatility data
- `rv_calculations` - Realized volatility data

---

## ⚙️ Configuration

### Change Size Limit:
Edit `auto_data_cleanup.py`:
```python
MAX_VOLATILITY_SIZE_MB = 500  # Change to desired MB
```

### Change Deletion Percentage:
Edit `auto_data_cleanup.py` in `manage_volatility_database()`:
```python
records_to_delete = int(count * 0.3)  # Change 0.3 to desired percentage
```

---

## 🔍 Monitoring

### Check Current Status:
```bash
# Database size
du -h data/volatility.db

# Record count
sqlite3 data/volatility.db "SELECT 
    'iv_snapshots' as table, COUNT(*) as records FROM iv_snapshots
    UNION ALL
    SELECT 'rv_calculations', COUNT(*) FROM rv_calculations"

# View cleanup logs
tail -f logs/auto_cleanup.log | grep Volatility
```

### Manual Cleanup (if needed):
```bash
# Run cleanup once
python3 auto_data_cleanup.py --once

# Watch output
python3 auto_data_cleanup.py --once 2>&1 | grep -A 10 "Volatility"
```

---

## 📈 Size Growth Estimates

### Typical Growth:
- ~1-2MB per day during active trading
- ~30-60MB per month
- ~360-720MB per year

### When 500MB Limit Reached:
- Automatically removes oldest 30%
- Reduces to ~350MB
- Gives ~150MB buffer before next cleanup

---

## ✅ Benefits

1. **Long-term data retention** - Not deleted after 48 hours
2. **Prevents disk bloat** - 500MB hard limit
3. **Automatic management** - No manual intervention
4. **Smart cleanup** - Only when needed
5. **Preserves recent data** - Oldest records deleted first

---

## 🚨 Troubleshooting

### If database exceeds 500MB frequently:
1. Check if data is being written correctly
2. Consider increasing limit (e.g., 1GB)
3. Review data collection frequency

### If cleanup doesn't trigger:
```bash
# Check current size
du -h data/volatility.db

# Force cleanup test by lowering limit temporarily
# Edit auto_data_cleanup.py, change MAX_VOLATILITY_SIZE_MB to 50
# Run: python3 auto_data_cleanup.py --once
# Should trigger cleanup and show deletion stats
```

### If tables are empty:
- Normal during initial setup
- Will populate as bot collects volatility data
- Check collector is running: `ps aux | grep volatility`

---

## 📝 Example Cleanup Output

### When Under Limit (Normal):
```
🧹 Volatility database: 53.33MB (under 500MB limit) ✅
```

### When Cleanup Triggered (Size >500MB):
```
🧹 Volatility database exceeds limit: 523.45MB > 500MB
   Cleaning oldest 30% of records...
   Found tables: iv_snapshots, rv_calculations
   • iv_snapshots: Deleted 15,432 oldest records
   • rv_calculations: Deleted 8,921 oldest records
   Running VACUUM to reclaim space...
   ✅ Volatility Database: Deleted 24,353 oldest records
      81,177 → 56,824 total records
      523.45MB → 366.21MB (freed 157.24MB)
```

---

**Last Updated:** December 18, 2025  
**Status:** ✅ Active (53.33MB / 500MB)  
**Next Check:** Every hour (automatic)
