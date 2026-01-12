// ============================================================================
// PM2 GridBot Configuration - Production Ready with Graceful Shutdown
// ============================================================================
//
// Usage:
//   pm2 start ecosystem.gridbot.config.js --only gridbot-live
//   pm2 start ecosystem.gridbot.config.js --only gridbot-demo
//   pm2 logs gridbot-live
//   pm2 monit
//   pm2 stop gridbot-live
//   pm2 restart gridbot-live --update-env
//
// Features:
//   ✅ Graceful shutdown with 30s timeout (cancels orders)
//   ✅ Auto-restart on crash
//   ✅ Log rotation
//   ✅ Memory monitoring
//   ✅ Startup on boot (pm2 startup)
//
// ============================================================================

module.exports = {
  apps: [
    // ========================================================================
    // LIVE TRADING BOT (Real Money)
    // ========================================================================
    {
      name: "gridbot-live",
      script: "start_bot_with_recovery.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      
      // Environment variables
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot:/Users/ssr/Library/Python/3.9/lib/python/site-packages",
        TRADING_MODE: "live",
        HOT_RELOAD: "1",
        
        // Ensure graceful shutdown
        PYTHONUNBUFFERED: "1",  // Immediate log output
      },
      
      // =====================================================================
      // CRITICAL: Graceful Shutdown Settings
      // =====================================================================
      
      // Time to wait for graceful shutdown before SIGKILL
      kill_timeout: 30000,  // 30 seconds (bot needs 15s to cancel orders)
      
      // Signal to send for shutdown (SIGTERM triggers signal handlers)
      kill_signal: "SIGTERM",
      
      // Wait for process to indicate it's ready
      wait_ready: false,
      
      // Timeout for ready signal
      listen_timeout: 10000,
      
      // =====================================================================
      // Auto-Restart Settings
      // =====================================================================
      
      autorestart: true,              // Auto-restart on crash
      max_restarts: 10,                // Max restarts within min_uptime period
      min_uptime: "30s",               // Min uptime to be considered stable
      restart_delay: 10000,            // Wait 10s before restart
      exp_backoff_restart_delay: 100,  // Exponential backoff on rapid crashes
      
      // =====================================================================
      // Resource Limits
      // =====================================================================
      
      max_memory_restart: "1G",  // Restart if memory exceeds 1GB
      
      // =====================================================================
      // Logging
      // =====================================================================
      
      log_file: "reports/pm2-gridbot-live-combined.log",
      error_file: "reports/pm2-gridbot-live-error.log",
      out_file: "reports/pm2-gridbot-live-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      merge_logs: true,
      
      // Log rotation (requires pm2-logrotate module)
      // Install: pm2 install pm2-logrotate
      // Config: pm2 set pm2-logrotate:max_size 10M
      
      // =====================================================================
      // Monitoring & Health Checks
      // =====================================================================
      
      // Enable monitoring
      pmx: true,
      
      // Instance variables for monitoring
      instance_var: "INSTANCE_ID",
      
      // =====================================================================
      // Advanced Settings
      // =====================================================================
      
      // Source map support for stack traces
      source_map_support: false,
      
      // Disable auto-restart on specific exit codes
      // Exit code 0 = normal shutdown, don't restart
      autorestart: true,
      stop_exit_codes: [0],
      
      // Time to wait before considering app online
      listen_timeout: 10000,
      
      // Cron restart (optional - restart daily at 3 AM)
      // cron_restart: "0 3 * * *",
      
      // Force restart even if not crashed
      // force: false,
    },
    
    // ========================================================================
    // DEMO TRADING BOT (Paper Trading)
    // ========================================================================
    {
      name: "gridbot-demo",
      script: "start_bot_with_recovery.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot:/Users/ssr/Library/Python/3.9/lib/python/site-packages",
        TRADING_MODE: "demo",
        HOT_RELOAD: "1",
        PYTHONUNBUFFERED: "1",
      },
      
      // Same graceful shutdown settings as live
      kill_timeout: 30000,
      kill_signal: "SIGTERM",
      wait_ready: false,
      listen_timeout: 10000,
      
      // Auto-restart settings
      autorestart: true,
      max_restarts: 10,
      min_uptime: "30s",
      restart_delay: 10000,
      exp_backoff_restart_delay: 100,
      
      // Resource limits
      max_memory_restart: "1G",
      
      // Logging
      log_file: "reports/pm2-gridbot-demo-combined.log",
      error_file: "reports/pm2-gridbot-demo-error.log",
      out_file: "reports/pm2-gridbot-demo-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      merge_logs: true,
      
      // Monitoring
      pmx: true,
      instance_var: "INSTANCE_ID",
      
      // Advanced
      source_map_support: false,
      autorestart: true,
      stop_exit_codes: [0],
      listen_timeout: 10000,
    },

    // ========================================================================
    // BTCUSD TRADING BOT (Real Money) - v6.0 Multi-Symbol
    // ========================================================================
    {
      name: "gridbot-btcusd-live",
      script: "start_bot_with_recovery.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot:/Users/ssr/Library/Python/3.9/lib/python/site-packages",
        TRADING_MODE: "live",
        SYMBOL: "BTCUSD",  // Symbol-specific
        HOT_RELOAD: "1",
        PYTHONUNBUFFERED: "1",
      },
      
      kill_timeout: 30000,
      kill_signal: "SIGTERM",
      wait_ready: false,
      listen_timeout: 10000,
      autorestart: true,
      max_restarts: 10,
      min_uptime: "30s",
      restart_delay: 10000,
      exp_backoff_restart_delay: 100,
      max_memory_restart: "1G",
      
      log_file: "reports/pm2-gridbot-btcusd-live-combined.log",
      error_file: "reports/pm2-gridbot-btcusd-live-error.log",
      out_file: "reports/pm2-gridbot-btcusd-live-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      merge_logs: true,
      pmx: true,
      instance_var: "INSTANCE_ID",
      source_map_support: false,
      stop_exit_codes: [0],
    },

    // ========================================================================
    // ETHUSD TRADING BOT (Real Money) - v6.0 Multi-Symbol
    // ========================================================================
    {
      name: "gridbot-ethusd-live",
      script: "start_bot_with_recovery.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot:/Users/ssr/Library/Python/3.9/lib/python/site-packages",
        TRADING_MODE: "live",
        SYMBOL: "ETHUSD",  // Symbol-specific
        HOT_RELOAD: "1",
        PYTHONUNBUFFERED: "1",
      },
      
      kill_timeout: 30000,
      kill_signal: "SIGTERM",
      wait_ready: false,
      listen_timeout: 10000,
      autorestart: true,
      max_restarts: 10,
      min_uptime: "30s",
      restart_delay: 10000,
      exp_backoff_restart_delay: 100,
      max_memory_restart: "1G",
      
      log_file: "reports/pm2-gridbot-ethusd-live-combined.log",
      error_file: "reports/pm2-gridbot-ethusd-live-error.log",
      out_file: "reports/pm2-gridbot-ethusd-live-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      merge_logs: true,
      pmx: true,
      instance_var: "INSTANCE_ID",
      source_map_support: false,
      stop_exit_codes: [0],
    },

    // ========================================================================
    // GUARDIAN BOT (Position Protection - LIVE)
    // ========================================================================
    {
      name: "guardian-live",
      script: "bot/guardian/guardian_bot.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot:/Users/ssr/Library/Python/3.9/lib/python/site-packages",
        TRADING_MODE: "live",
        SYMBOL: "BTCUSD",  // Guardian monitors BTCUSD (primary symbol)
        PYTHONUNBUFFERED: "1",
      },
      
      // Guardian-specific settings
      kill_timeout: 15000,  // 15 seconds (Guardian is simpler, faster shutdown)
      kill_signal: "SIGTERM",
      autorestart: true,
      max_restarts: 10,
      min_uptime: 5000,
      
      // Logging
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      out_file: "/Users/ssr/Projects/WorkingBot/reports/pm2-guardian-live-out.log",
      error_file: "/Users/ssr/Projects/WorkingBot/reports/pm2-guardian-live-error.log",
    },

    // ========================================================================
    // GUARDIAN BOT (Position Protection - DEMO)
    // ========================================================================
    {
      name: "guardian-demo",
      script: "bot/guardian/guardian_bot.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot:/Users/ssr/Library/Python/3.9/lib/python/site-packages",
        TRADING_MODE: "demo",
        PYTHONUNBUFFERED: "1",
      },
      
      kill_timeout: 15000,
      kill_signal: "SIGTERM",
      autorestart: true,
      max_restarts: 10,
      min_uptime: 5000,
      
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      out_file: "/Users/ssr/Projects/WorkingBot/reports/pm2-guardian-demo-out.log",
      error_file: "/Users/ssr/Projects/WorkingBot/reports/pm2-guardian-demo-error.log",
    },

    // ========================================================================
    // HEARTBEAT MONITOR (Health Monitoring)
    // ========================================================================
    {
      name: "heartbeat",
      script: "continuous_heartbeat.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot:/Users/ssr/Library/Python/3.9/lib/python/site-packages",
        PYTHONUNBUFFERED: "1",
      },
      
      kill_timeout: 5000,  // 5 seconds (simple process)
      kill_signal: "SIGTERM",
      autorestart: true,
      max_restarts: 10,
      min_uptime: 3000,
      
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      out_file: "/Users/ssr/Projects/WorkingBot/reports/pm2-heartbeat-out.log",
      error_file: "/Users/ssr/Projects/WorkingBot/reports/pm2-heartbeat-error.log",
    },

    // ========================================================================
    // DEVELOPMENT WEBUI BACKEND (Port 5557)
    // ⚠️  FOR DEVELOPMENT ONLY - Testing v5.0 Multi-Symbol Features
    // ========================================================================
    {
      name: "webui-backend-dev",
      script: "webui/backend/app_dev.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot:/Users/ssr/Library/Python/3.9/lib/python/site-packages",
        WEBUI_ENV: "development",
        FLASK_ENV: "development",
        PYTHONUNBUFFERED: "1",
      },
      
      kill_timeout: 5000,
      kill_signal: "SIGTERM",
      autorestart: true,
      max_restarts: 10,
      min_uptime: 3000,
      watch: false,  // Disable watch, app_dev.py has hot reload
      
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      out_file: "/Users/ssr/Projects/WorkingBot/reports/pm2-webui-backend-dev-out.log",
      error_file: "/Users/ssr/Projects/WorkingBot/reports/pm2-webui-backend-dev-error.log",
    },

    // ========================================================================
    // DEVELOPMENT WEBUI FRONTEND (Port 3001)
    // ⚠️  FOR DEVELOPMENT ONLY - React Dev Server with Hot Reload
    // ========================================================================
    {
      name: "webui-frontend-dev",
      script: "npm",
      args: "start",
      cwd: "/Users/ssr/Projects/WorkingBot/webui/frontend",
      
      env: {
        NODE_ENV: "development",
        PORT: "3001",
        REACT_APP_API_URL: "http://localhost:5557",
        REACT_APP_SOCKET_URL: "http://localhost:5557",
        REACT_APP_API_BASE_URL: "http://localhost:5557",
      },
      
      kill_timeout: 5000,
      kill_signal: "SIGTERM",
      autorestart: false,  // Don't auto-restart React dev server
      watch: false,
      
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      out_file: "/Users/ssr/Projects/WorkingBot/reports/pm2-webui-frontend-dev-out.log",
      error_file: "/Users/ssr/Projects/WorkingBot/reports/pm2-webui-frontend-dev-error.log",
    }
  ],
  
  // ==========================================================================
  // PM2 Deploy Configuration (Optional - for remote deployment)
  // ==========================================================================
  
  deploy: {
    production: {
      // SSH connection
      user: "ssr",
      host: "localhost",
      ref: "origin/production-v2.0",
      repo: "git@github.com:physicsssr/Working-gridBOT.git",
      path: "/Users/ssr/Projects/WorkingBot",
      
      // Pre-deploy hooks
      "pre-deploy-local": "echo 'Deploying GridBot...'",
      
      // Post-deploy hooks
      "post-deploy": "npm install && pm2 reload ecosystem.gridbot.config.js --env production",
      
      // Environment
      env: {
        NODE_ENV: "production"
      }
    }
  }
};
