# Phase 3B: Production Deployment - DEPLOYMENT GUIDE

## Pre-Deployment Checklist

### ✅ Code Preparation
- [ ] All tests in Phase 3A passed
- [ ] BTEH branch fully tested on development
- [ ] No critical bugs remaining
- [ ] Code reviewed and approved
- [ ] All commits pushed to GitHub

### ✅ Configuration Review
- [ ] config.yaml updated with production values
- [ ] ETHUSD grid parameters validated
- [ ] Product IDs confirmed (BTCUSD: 139, ETHUSD: 3136)
- [ ] Safety limits set appropriately
- [ ] Guardian thresholds configured

### ✅ Backup Strategy
- [ ] Production database backed up
- [ ] Config files backed up
- [ ] State files backed up
- [ ] Git branch backup created

## Deployment Strategy

### Option A: Gradual Rollout (RECOMMENDED)

**Step 1: Deploy WebUI Only (Week 1)**
```bash
# Switch to BTEH branch
git checkout BTEH

# Restart WebUI backend only
pm2 restart webui-backend-dev

# Verify:
✅ /api/symbols endpoint works
✅ Symbol dropdown appears
✅ BTCUSD data still loads
✅ No errors in logs
```

**Step 2: Enable ETHUSD in Config (Week 2)**
```yaml
# config.yaml
symbols:
  ETHUSD:
    enabled: true  # Enable ETHUSD
```

**Step 3: Start ETHUSD Bot (Week 2)**
```bash
# Start ETHUSD bot only
pm2 start ecosystem.multi-symbol.config.js --only gridbot-eth-live

# Monitor logs
pm2 logs gridbot-eth-live

# Verify:
✅ ETHUSD orders placed correctly
✅ No conflicts with BTCUSD
✅ WebUI shows both symbols
```

**Step 4: Update Guardian (Week 3)**
```bash
# Restart Guardian with multi-symbol support
pm2 restart guardian-live

# Verify:
✅ Guardian monitors both symbols
✅ Risk signals per symbol
✅ No false stops
```

### Option B: Full Deployment (Advanced)

**Deploy Everything at Once**
```bash
# 1. Stop all current processes
pm2 stop all

# 2. Switch to BTEH branch
git checkout BTEH

# 3. Update dependencies (if any)
cd webui/backend && pip install -r requirements.txt

# 4. Enable both symbols in config
# (Edit config.yaml)

# 5. Start all services
pm2 start ecosystem.multi-symbol.config.js

# 6. Verify everything
pm2 status
```

## Rollback Plan

If deployment fails, rollback immediately:

```bash
# 1. Stop new processes
pm2 stop gridbot-eth-live
pm2 stop gridbot-btc-live
pm2 stop webui-backend-dev

# 2. Switch back to production
git checkout production-4.0-clean

# 3. Restart v4.0 services
pm2 restart gridbot-live
pm2 restart webui-backend

# 4. Verify v4.0 working
curl http://localhost:5555/api/health
```

## Post-Deployment Monitoring

### Week 1: Watch Closely
```bash
# Monitor logs continuously
pm2 logs

# Check for errors
tail -f bot/logs/async_gridbot.log
tail -f bot/logs/guardian.log
tail -f webui/backend/backend.log

# Monitor database sizes
ls -lh data/*.db

# Watch for anomalies
curl http://localhost:5556/api/monitoring/anomalies?symbol=BTCUSD
curl http://localhost:5556/api/monitoring/anomalies?symbol=ETHUSD
```

### Week 2: Performance Metrics
```bash
# Check resource usage
pm2 monit

# Database growth rate
du -sh data/

# API response times
time curl http://localhost:5556/api/symbols

# WebUI load times
# (Manual browser testing)
```

### Week 3: Stability Assessment
```bash
# Crash count
pm2 status | grep restart

# Error rate
grep ERROR bot/logs/async_gridbot.log | wc -l

# Position count per symbol
sqlite3 data/bot_events_BTCUSD_LONG.db "SELECT COUNT(*) FROM positions;"
sqlite3 data/bot_events_ETHUSD_LONG.db "SELECT COUNT(*) FROM positions;"

# PnL verification
# (Check against exchange)
```

## Production Checklist

### Day 1 (Deployment Day)
- [ ] 8:00 AM: Pre-deployment backup complete
- [ ] 9:00 AM: Deploy WebUI backend
- [ ] 9:30 AM: Verify WebUI working
- [ ] 10:00 AM: Enable ETHUSD in config
- [ ] 10:30 AM: Start ETHUSD bot
- [ ] 11:00 AM: Monitor first ETHUSD orders
- [ ] 12:00 PM: Verify no errors for 1 hour
- [ ] 1:00 PM: Update Guardian
- [ ] 2:00 PM: Full system check
- [ ] 3:00 PM: Document any issues
- [ ] 4:00 PM: Send status update

### Day 2-7 (First Week)
- [ ] Daily log review
- [ ] Daily position verification
- [ ] Daily PnL reconciliation
- [ ] Daily error count
- [ ] Weekly status report

### Week 2-4 (Stabilization)
- [ ] Optimize resource usage
- [ ] Fine-tune grid parameters
- [ ] Address any bugs
- [ ] User feedback incorporation

## Success Metrics

### Technical Metrics
- **Uptime**: >99.5% for both symbols
- **Error Rate**: <0.1% of operations
- **API Latency**: <200ms average
- **Database Size**: <100MB per symbol
- **CPU Usage**: <30% average
- **Memory Usage**: <2GB total

### Business Metrics
- **BTCUSD Performance**: Maintained or improved
- **ETHUSD Performance**: Positive PnL within 1 week
- **Total Capital Utilization**: >80%
- **Risk Events**: Zero critical stops
- **User Satisfaction**: No major complaints

## Communication Plan

### Stakeholders
- Trading team
- DevOps team
- Management
- End users (if applicable)

### Update Schedule
- **Daily**: Technical updates (first week)
- **Weekly**: Status reports (first month)
- **Monthly**: Performance summary (ongoing)

### Incident Response
```bash
# Critical Issue Detected

1. STOP affected bot immediately
   pm2 stop gridbot-eth-live  # or gridbot-btc-live

2. Assess impact
   - Check positions
   - Check orders
   - Check database integrity

3. Communicate
   - Notify team immediately
   - Document issue
   - Estimate fix time

4. Fix or Rollback
   - Quick fix: Deploy hotfix
   - Complex issue: Rollback to v4.0

5. Post-Mortem
   - Root cause analysis
   - Prevention measures
   - Update deployment guide
```

## Final Go/No-Go Decision

Before deploying to production, answer:

1. **Are all Phase 3A tests passing?** Yes/No
2. **Is BTEH branch stable on dev for 7+ days?** Yes/No
3. **Are backups in place?** Yes/No
4. **Is rollback plan tested?** Yes/No
5. **Are monitoring tools ready?** Yes/No
6. **Is team trained on new system?** Yes/No
7. **Is off-hours support available?** Yes/No

**If ALL answers are YES → PROCEED**
**If ANY answer is NO → DELAY deployment**

## Deployment Commands

```bash
# Full deployment script
#!/bin/bash

echo "🚀 Deploying Multi-Symbol Trading Bot (v5.0)"

# Backup
echo "📦 Creating backup..."
tar -czf backup-$(date +%Y%m%d-%H%M%S).tar.gz data/ config.yaml

# Switch branch
echo "🔀 Switching to BTEH branch..."
git checkout BTEH
git pull origin BTEH

# Update config
echo "⚙️  Updating configuration..."
# (Manual config edits)

# Restart services
echo "🔄 Restarting services..."
pm2 stop all
pm2 start ecosystem.multi-symbol.config.js

# Verify
echo "✅ Verifying deployment..."
sleep 5
pm2 status

# Health check
echo "🏥 Running health checks..."
curl http://localhost:5556/api/health
curl http://localhost:5556/api/symbols

echo "✅ Deployment complete!"
echo "📊 Monitor logs: pm2 logs"
```

**Status:** Deployment guide complete, ready for execution ✅

---

**IMPORTANT:** Do NOT deploy to production without completing Phase 3A testing!
