# SHORT Mode - Quick Reference Guide

## ✅ Bug Fixed - Safe to Use

**Critical Bug Fixed:** TP orders now use correct side (BUY for SHORT, SELL for LONG)

---

## 📋 Your Configuration

```
Reference:  110,000
Step:       500
Lower:      105,000
Upper:      115,000
Mode:       SHORT
Max Open:   10
```

---

## 📊 How It Works - Market Goes UP

**Starting:** LTP = 109,946

### **Grid Places SELL Orders:**

| Price | Action | TP Placed |
|-------|--------|-----------|
| 110,500 | First SELL | → BUY TP @ 110,000 |
| 111,000 | SELL fills | → BUY TP @ 110,500 |
| 111,500 | SELL fills | → BUY TP @ 111,000 |
| 112,000 | SELL fills | → BUY TP @ 111,500 |
| 112,500 | SELL fills | → BUY TP @ 112,000 |
| 113,000 | SELL fills | → BUY TP @ 112,500 |
| 113,500 | SELL fills | → BUY TP @ 113,000 |
| 114,000 | SELL fills | → BUY TP @ 113,500 |

**At 114,399:** 8 positions open, 1 pending SELL @ 114,500

---

## 💰 How It Works - Market Goes DOWN

**Market Reverses:** 114,399 → 109,400

### **TPs Close Positions with Profit:**

| Price | TP Fills | Closes Position | Profit |
|-------|----------|-----------------|--------|
| 113,500 | BUY TP | SHORT @ 114,000 | +$500 |
| 113,000 | BUY TP | SHORT @ 113,500 | +$500 |
| 112,500 | BUY TP | SHORT @ 113,000 | +$500 |
| 112,000 | BUY TP | SHORT @ 112,500 | +$500 |
| 111,500 | BUY TP | SHORT @ 112,000 | +$500 |
| 111,000 | BUY TP | SHORT @ 111,500 | +$500 |
| 110,500 | BUY TP | SHORT @ 111,000 | +$500 |
| 110,000 | BUY TP | SHORT @ 110,500 | +$500 |

**Total:** $4,000 profit (lot_size = 1)

---

## 🎯 Key Points

### **How SHORT Works:**
1. ✅ **Entry:** SELL at higher prices (grid goes UP)
2. ✅ **TP:** BUY at lower prices (take profit on downturn)
3. ✅ **Profit:** When price drops back down

### **Risk Management:**
- **Max Positions:** 10 (capacity protection)
- **Upper Bound:** 115,000 (won't sell above this)
- **Each Position Protected:** Automatic BUY TP @ entry - 500

### **Grid Behavior:**
- **Market Rising:** Adds SHORT positions (sells into strength)
- **Market Falling:** Closes positions with profit (buys back cheaper)
- **Grid Resets:** When all positions close, returns to initial state

---

## ⚠️ Important Notes

### **When SHORT Works Best:**
- ✅ Range-bound markets
- ✅ Market at resistance levels
- ✅ Expecting mean reversion

### **When to Avoid SHORT:**
- ❌ Strong uptrend (trend following)
- ❌ Breaking above resistance
- ❌ Positive momentum/news

### **Safety Features Active:**
- ✅ Volatility monitoring (halts if unsafe)
- ✅ Liquidation protection
- ✅ Capacity limits (max 10 positions)
- ✅ Boundary enforcement (won't trade outside range)
- ✅ TP collision detection

---

## 🧪 Testing Checklist

Before going live with SHORT mode:

- [ ] Test in **testnet** first
- [ ] Verify TPs are **BUY orders** on exchange (not SELL)
- [ ] Start with **small lot size** (1-2 contracts)
- [ ] Monitor first 2-3 fills closely
- [ ] Check TP placement after each fill
- [ ] Confirm TPs fill when price drops

---

## 📞 If Something Goes Wrong

### **Emergency Actions:**
1. Stop the bot: `Ctrl+C` or kill process
2. Check open positions on Delta Exchange
3. Verify all TPs are BUY orders (reduce_only=True)
4. If TPs are wrong side → **Cancel them manually**

### **Common Issues:**
- **TPs not filling:** Check they are BUY orders (should be after fix)
- **Too many positions:** Increase step size or reduce max_open
- **Hitting upper bound:** Adjust upper limit or wait for reversal

---

## 🔍 Verification Commands

```bash
# Run bug finder
python3 run_bug_finder.py --quick

# Run tests
python3 -m pytest tests/test_short_mode_bugs.py -v

# Run full test suite
python3 run_tests.py --quick

# Check linting
python3 -m flake8 bot/strategy/modules/order_manager.py
```

---

**Last Updated:** 2025-11-02  
**Status:** ✅ Production Ready (after testnet validation)  
**Bug Status:** ✅ FIXED & TESTED

