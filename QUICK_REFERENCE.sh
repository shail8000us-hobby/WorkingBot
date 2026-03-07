#!/bin/bash
# Quick Reference: WebUI Single-Instance System
# Generated: November 10, 2025

cat << 'EOF'

╔═══════════════════════════════════════════════════════════════════════════╗
║  QUICK REFERENCE: WebUI Single-Instance + Guardian LaunchAgent           ║
╚═══════════════════════════════════════════════════════════════════════════╝

━━━ DEPLOYMENT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🚀 Deploy Everything:
     ./clean_restart_with_guardian.sh

  🚀 Normal Start:
     ./start_main_bot.sh

  🛑 Stop Everything:
     ./stop_main_bot.sh

━━━ STATUS CHECKS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📊 Quick Status:
     ./check_instance_status.sh

  📊 LaunchAgents:
     launchctl list | grep gridbot

  📊 Processes:
     ps aux | grep WorkingBot | grep python | grep -v grep

  📊 Port Check:
     lsof -i :5555

  📊 Instance Lock:
     cat .webui_instance_5555.lock

━━━ LOGS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📝 WebUI:
     tail -f logs/launchagent_webui.log
     tail -f logs/launchagent_webui_error.log

  📝 Guardian:
     tail -f logs/guardian_launchd.log
     tail -f logs/guardian_launchd_error.log

  📝 Trading Bot:
     tail -f bot.log

━━━ MANUAL LAUNCHAGENT CONTROL ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🔄 Restart WebUI:
     launchctl stop com.gridbot.webui && launchctl start com.gridbot.webui

  🔄 Restart Guardian:
     launchctl stop com.gridbot.guardian && launchctl start com.gridbot.guardian

  🔄 Reload Plist (after editing):
     launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist
     launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist

━━━ TROUBLESHOOTING ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🔧 "WebUI instance already running":
     launchctl stop com.gridbot.webui
     rm .webui_instance_5555.lock

  🔧 Guardian not starting:
     tail -f logs/guardian_launchd_error.log
     python3 -m bot.guardian.guardian_bot  # test manually

  🔧 Clear all locks:
     rm .bot_instance*.lock .heartbeat .webui_instance*.lock

  🔧 Force kill everything:
     pkill -9 -f "WorkingBot"

━━━ KEY FILES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📄 Instance Lock Manager:
     webui/backend/utils/instance_lock.py

  📄 Guardian LaunchAgent:
     com.gridbot.guardian.plist (install ready)
     ~/Library/LaunchAgents/com.gridbot.guardian.plist (installed)

  📄 WebUI LaunchAgent:
     ~/Library/LaunchAgents/com.gridbot.webui.plist

  📄 Documentation:
     COMPLETE_SOLUTION_WEBUI_GUARDIAN.md (full guide)
     WEBUI_SINGLE_INSTANCE_SYSTEM.md (technical)
     INVESTIGATION_SUMMARY_WEBUI_DUPLICATES.md (analysis)

━━━ TESTING ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ Test Instance Lock:
     python3 webui/backend/app.py  # Should fail if already running

  ✅ Test Auto-Restart:
     pkill -9 -f guardian_bot
     sleep 30
     ps aux | grep guardian  # Should see new PID

  ✅ Verify Separation:
     curl http://localhost:5555/api/bots/status  # Only WorkingBot
     curl http://localhost:5556/api/bots/status  # Only demo

━━━ ARCHITECTURE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Normal Process Tree:
  
    com.gridbot.webui (LaunchAgent)
     └─> Parent Process (PID 992)
          └─> Worker Process (PID 2237) ← Flask multiprocessing
  
    com.gridbot.guardian (LaunchAgent)
     └─> Guardian Process (PID 1234)
  
  Lock Files:
    .webui_instance_5555.lock    → Prevents duplicate WebUI
    .bot_instance_live.lock      → Prevents duplicate bot.run

━━━ EXPECTED OUTPUT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  $ launchctl list | grep gridbot
  992     0       com.gridbot.webui
  1234    0       com.gridbot.guardian

  $ ./check_instance_status.sh
  📊 LaunchAgents:
     com.gridbot.webui              PID: 992
     com.gridbot.guardian           PID: 1234
  
  📊 Ports:
     ✅ 5555: WebUI
  
  📊 Instance Locks:
     ✅ WebUI lock exists

━━━ REMEMBER ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ 2 WebUI processes = NORMAL (Flask parent + worker)
  ✅ Instance lock prevents duplicate manual starts
  ✅ Guardian always via LaunchAgent (never manual nohup)
  ✅ Auto-start on boot, auto-restart on crash

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
