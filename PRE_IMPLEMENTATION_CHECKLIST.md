# Pre-Implementation Checklist
**Date:** December 30, 2025  
**Branch:** BTEH (development)  
**Project:** Multi-Symbol GridBot Implementation

---

## ✅ Pre-Flight Checks (MUST COMPLETE BEFORE PHASE 1A)

### 1. Branch Verification
- [x] On BTEH development branch
- [x] BTC backup branch created
- [x] production-4.0-clean branch protected

```bash
$ git branch --show-current
BTEH  ✅
```

### 2. ETH Product ID Verification
- [x] Ran `scripts/verify_eth_product_id.py`
- [x] **Verified Product ID: 3136** (NOT 139!)
- [x] Tick size confirmed: 0.05

```
✅ ETHUSD Perpetual Found:
   Product ID: 3136
   Symbol: ETHUSD
   Tick Size: 0.05
```

**⚠️ CRITICAL:** All config examples in plan assume product_id: 139, but actual is **3136**

### 3. PM2 Ecosystem Config
- [x] Created `ecosystem.multi-symbol.config.js`
- [x] Validated with Node.js
- [x] Apps configured:
  - gridbot-btc-live (BTCUSD)
  - gridbot-eth-live (ETHUSD, autorestart: false)
  - guardian-live (multi-symbol)
  - webui-backend-dev (port 5556)

### 4. Capital Allocation Strategy
- [ ] Total capital documented
- [ ] BTC allocation decided (suggested: 70%)
- [ ] ETH allocation decided (suggested: 30%)
- [ ] Max position values set

**TODO:** Document actual capital allocation numbers before Phase 1A

### 5. Production Environment Verification
- [ ] Production WebUI running on port 5555
- [ ] Production bot trading BTCUSD successfully
- [ ] No errors in production logs
- [ ] Current state backed up

```bash
# Check production status
curl http://localhost:5555/api/health
pm2 list | grep gridbot-live
```

### 6. Development Environment Setup
- [ ] Port 5556 available for dev WebUI
- [ ] `data_bteh/` directory created (will be created automatically)
- [ ] Logs directory ready
- [ ] Python environment activated

---

## 📝 Configuration Values to Update

Based on verification, these values need to be used in Phase 1A:

### ETHUSD Configuration
```yaml
ETHUSD:
  enabled: false  # Start disabled
  product_id: 3136  # ⚠️ NOT 139!
  mode: LONG
  grid:
    geometry:
      lower: 3200    # Adjust based on current ETH price
      upper: 3800
      step: 50
      reference: 3500  # Adjust based on current ETH price
    behavior:
      tick_size: 0.05  # From API verification
```

### Current ETH Price Check
```bash
# Get current ETH price to set appropriate grid bounds
curl https://api.india.delta.exchange/v2/products/3136/ticker
```

---

## 🚀 Ready for Phase 1A?

**Checklist Summary:**
- [x] Branch: BTEH ✅
- [x] ETH product_id: 3136 ✅  
- [x] PM2 config: Created & validated ✅
- [ ] Capital allocation: Documented ⏳
- [ ] Production status: Verified ⏳
- [ ] Dev environment: Ready ⏳

**Next Step:** Complete remaining items, then proceed to Phase 1A - Configuration Architecture

---

## 📊 Quick Reference

| Item | Value | Status |
|------|-------|--------|
| Branch | BTEH | ✅ |
| ETH Product ID | 3136 | ✅ Verified |
| ETH Tick Size | 0.05 | ✅ Verified |
| PM2 Config | ecosystem.multi-symbol.config.js | ✅ Created |
| Dev WebUI Port | 5556 | Ready |
| Production Port | 5555 | Protected |
| Database Dir | data_bteh/ | To be created |

