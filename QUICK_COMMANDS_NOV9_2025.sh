#!/bin/bash
# Quick Command Reference - Phase 1 Implementation
# November 9, 2025

cat << 'EOF'

╔══════════════════════════════════════════════════════════════╗
║          PHASE 1 IMPLEMENTATION - QUICK COMMANDS             ║
╚══════════════════════════════════════════════════════════════╝

📦 START BOT
────────────────────────────────────────────────────────────────
python3 bot_launcher.py --mode live


🔍 MONITOR LOGS
────────────────────────────────────────────────────────────────
# Full log
tail -f bot/logs/bot.log

# Key events only
tail -f bot/logs/bot.log | grep -E 'Watchdog|TP placed|RETRY|THROTTLE|CRITICAL'

# Errors only
tail -f bot/logs/bot.log | grep -E 'ERROR|CRITICAL|FATAL'


📊 VIEW AUDIT LOG
────────────────────────────────────────────────────────────────
python3 view_fill_audit_log.py


🛑 STOP BOT
────────────────────────────────────────────────────────────────
ps aux | grep bot_launcher | grep -v grep | awk '{print $2}' | xargs kill


✅ CHECK BOT STATUS
────────────────────────────────────────────────────────────────
ps aux | grep -E "python.*bot_launcher" | grep -v grep


🧪 RUN TESTS
────────────────────────────────────────────────────────────────
# Quick import test
python3 -c "from bot.strategy.gridbot import GridBot; print('✅ OK')"

# Full deployment check
./deploy_phase1.sh


📈 CHECK POSITIONS
────────────────────────────────────────────────────────────────
python3 check_current_status.py


🔄 RESTART BOT
────────────────────────────────────────────────────────────────
ps aux | grep bot_launcher | grep -v grep | awk '{print $2}' | xargs kill
sleep 2
python3 bot_launcher.py --mode live


╔══════════════════════════════════════════════════════════════╗
║                    WHAT TO LOOK FOR                          ║
╚══════════════════════════════════════════════════════════════╝

✅ On Startup:
   - "🐕 Watchdog started (timeout: 60s)"
   - "✅ FillAuditLog initialized"

✅ On Fill:
   - "🛡️ TP placed: X lots @ $Y (ID: Z)"
   - "📝 Updated audit log with TP: Z"
   - "✅ Pending BUY registered: W @ $X"
   - "📝 Updated audit log with next grid: W"

✅ If Retry Needed:
   - "⚠️ TP RETRY 2/5 (wait 6.0s)"
   - "✅ TP MANDATORY SUCCESS on retry 2"

✅ If Throttled:
   - "🚦 THROTTLE: Last BUY was X.Xs ago"
   - "📅 Scheduled next grid order for X.Xs from now"
   - "⏰ Throttle expired - placing delayed grid BUY"

❌ CRITICAL ALERTS:
   - "🚨 CRITICAL: TP PLACEMENT FAILED AFTER 5 RETRIES"
   - "🚨 FATAL: 5 consecutive errors - halting bot"
   - "🚨 WATCHDOG TRIGGERED: Heartbeat frozen"


╔══════════════════════════════════════════════════════════════╗
║                      KEY FILES                               ║
╚══════════════════════════════════════════════════════════════╝

Logs:              bot/logs/bot.log
Audit Log:         fill_processing_audit.jsonl
Runtime State:     bot/data/runtime_state.json
Monitoring:        bot/data/monitoring/bot_snapshot.json


╔══════════════════════════════════════════════════════════════╗
║                   TROUBLESHOOTING                            ║
╚══════════════════════════════════════════════════════════════╝

Issue: Bot won't start
Fix:   Check syntax: python3 -m py_compile bot/strategy/gridbot.py

Issue: Import errors
Fix:   Check all modules: ./deploy_phase1.sh

Issue: Audit log not created
Fix:   Check permissions: touch fill_processing_audit.jsonl

Issue: TP always fails
Fix:   Check exchange API: python3 check_exchange_status.py

Issue: Watchdog triggering
Fix:   Check logs for deadlock: grep -B 50 "WATCHDOG" bot/logs/bot.log

Issue: Bot halts after errors
Fix:   Check error log: grep "consecutive errors" bot/logs/bot.log


╔══════════════════════════════════════════════════════════════╗
║                  EMERGENCY ROLLBACK                          ║
╚══════════════════════════════════════════════════════════════╝

git checkout HEAD~1 bot/strategy/modules/fill_audit_log.py
git checkout HEAD~1 bot/strategy/modules/order_manager.py
git checkout HEAD~1 bot/strategy/handlers/long_handler.py
git checkout HEAD~1 bot/strategy/gridbot.py
python3 bot_launcher.py --mode live


╔══════════════════════════════════════════════════════════════╗
║                  IMPLEMENTATION STATUS                       ║
╚══════════════════════════════════════════════════════════════╝

✅ Code Implementation:    COMPLETE
✅ Module Tests:           PASSED
✅ Syntax Checks:          PASSED
⏳ Deployment:             READY
⏳ Live Testing:           PENDING
⏳ 24-Hour Stability:      PENDING


═══════════════════════════════════════════════════════════════
All Phase 1 fixes implemented - Ready for production deployment
═══════════════════════════════════════════════════════════════

EOF
