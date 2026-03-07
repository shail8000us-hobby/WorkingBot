# Quick Guide: Add Max Loss to C-BTC-111000-270326

**Your Contract**: C-BTC-111000-270326 (Expires Feb 27, 2026)
**Current Status**: ❌ NO max loss limit set (not being monitored)

---

## Option 1: Via WebUI (Easiest) ⭐

1. Open http://localhost:3000 (or your WebUI URL)
2. Go to **Options Trading** page
3. Find row for **C-BTC-111000-270326**
4. In the **"Max Loss"** column, type your limit (e.g., `50` for $50)
5. Press **Enter** or click **Save**

✅ **Done!** Monitoring starts within 5 seconds automatically.

---

## Option 2: Via Terminal (Fast)

```bash
curl -X POST http://localhost:5555/api/options/max-loss/strike/set \
  -H "Content-Type: application/json" \
  -d '{"symbol": "C-BTC-111000-270326", "max_loss": 50.0}'
```

**Replace `50.0` with your desired max loss in USD.**

---

## Option 3: Direct Database (Advanced)

```bash
cd /Users/ssr/Projects/WorkingBot

sqlite3 data/options_max_loss.db <<EOF
INSERT OR REPLACE INTO strike_max_loss 
  (symbol, max_loss, enabled, triggered, created_at, updated_at)
VALUES 
  ('C-BTC-111000-270326', 50.0, 1, 0, datetime('now'), datetime('now'));
EOF
```

---

## Verify It's Working:

### Check database:
```bash
sqlite3 data/options_max_loss.db "SELECT symbol, max_loss, enabled FROM strike_max_loss WHERE symbol='C-BTC-111000-270326';"
```

Expected output:
```
C-BTC-111000-270326|50.0|1
```

### Check monitor logs:
```bash
tail -f webui/backend.log | grep "C-BTC-111000-270326"
```

You should see within 5 seconds:
```
🔍 DEBUG Limit: C-BTC-111000-270326 | Max Loss: $50.0000
✅ DEBUG: Found limit for C-BTC-111000-270326
```

---

## What Happens Next (Automatic):

1. **Every 5 seconds**, monitor checks your position for C-BTC-111000-270326
2. **If loss exceeds $50**, position is auto-closed immediately
3. **Telegram notification** sent (if configured)
4. **Works forever** - will still work 1 year from now!

---

## Clean Up Old Expired Contracts:

Your current max loss limits include 2 expired contracts (Jan 16, 2026):
- P-BTC-95200-160126 ❌ EXPIRED
- C-BTC-95400-160126 ❌ EXPIRED

### Remove them:
```bash
curl -X DELETE http://localhost:5555/api/options/max-loss/strike/remove/P-BTC-95200-160126
curl -X DELETE http://localhost:5555/api/options/max-loss/strike/remove/C-BTC-95400-160126
```

Or via database:
```bash
sqlite3 data/options_max_loss.db "DELETE FROM strike_max_loss WHERE symbol IN ('P-BTC-95200-160126', 'C-BTC-95400-160126');"
```

---

## SSR Order Issue (Separate Problem):

Your SSR order #336 at $419.08 for C-BTC-111000-270326 was placed successfully but the monitoring thread was never started (orphaned order).

**Why it's stuck**: SSR monitoring thread tracks the order in memory (`_active_ssr_orders`), but if backend restarted after order placement, the thread is lost.

**Fix options**:
1. **Cancel and re-place** with SSR (recommended - fresh start)
2. **Manually restart SSR thread** (complex, requires code changes)

To cancel:
```bash
curl -X POST http://localhost:5555/api/options/orders/cancel \
  -H "Content-Type: application/json" \
  -d '{"order_id": "1146847817"}'
```

Then place new SSR order via WebUI.

---

**Questions?** See [MAX_LOSS_SYSTEM_EXPLAINED.md](MAX_LOSS_SYSTEM_EXPLAINED.md) for full details.
