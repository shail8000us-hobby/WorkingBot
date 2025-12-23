// PM2 Ecosystem Configuration for Infinite Uptime
// This file configures PM2 to manage your trading bots with auto-restart

module.exports = {
  apps: [
    {
      name: "gridbot-demo",
      script: "bot/strategy/async_gridbot.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot",
        TRADING_MODE: "demo",
        USE_ASYNC_BOT: "true",  // Enable AsyncBot (production-ready v2.0)
        HOT_RELOAD: "1"
      },
      // Restart settings
      autorestart: true,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,
      // Memory limits
      max_memory_restart: "500M",
      // Log settings
      log_file: "bot/logs/pm2-gridbot-demo.log",
      error_file: "bot/logs/pm2-gridbot-demo-error.log",
      out_file: "bot/logs/pm2-gridbot-demo-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      // Watch for crashes
      exp_backoff_restart_delay: 100,
      // Kill timeout - NOV 14: Increased to 15s for graceful shutdown with order cancellation
      kill_timeout: 15000,
      // Graceful shutdown
      wait_ready: false,
      listen_timeout: 3000,
    },
    {
      name: "gridbot-live",
      script: "bot/strategy/async_gridbot.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot",
        TRADING_MODE: "live",
        USE_ASYNC_BOT: "true",  // Enable AsyncBot (production-ready v2.0)
        HOT_RELOAD: "1"
      },
      // Restart settings
      autorestart: true,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,
      // Memory limits
      max_memory_restart: "500M",
      // Log settings
      log_file: "bot/logs/pm2-gridbot-live.log",
      error_file: "bot/logs/pm2-gridbot-live-error.log",
      out_file: "bot/logs/pm2-gridbot-live-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      // Watch for crashes
      exp_backoff_restart_delay: 100,
      // Kill timeout - NOV 14: Increased to 15s for graceful shutdown with order cancellation
      kill_timeout: 15000,
      // Graceful shutdown
      wait_ready: false,
      listen_timeout: 3000,
    },
    {
      name: "guardian-demo",
      script: "bot/guardian/core/guardian_bot.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot",
        TRADING_MODE: "demo"
      },
      // Restart settings
      autorestart: true,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,
      // Memory limits
      max_memory_restart: "300M",
      // Log settings
      log_file: "bot/logs/pm2-guardian-demo.log",
      error_file: "bot/logs/pm2-guardian-demo-error.log",
      out_file: "bot/logs/pm2-guardian-demo-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      // Watch for crashes
      exp_backoff_restart_delay: 100,
      // Kill timeout
      kill_timeout: 3000,
    },
    {
      name: "guardian-live",
      script: "bot/guardian/core/guardian_bot.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot",
        TRADING_MODE: "live"
      },
      // Restart settings
      autorestart: true,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,
      // Memory limits
      max_memory_restart: "300M",
      // Log settings
      log_file: "bot/logs/pm2-guardian-live.log",
      error_file: "bot/logs/pm2-guardian-live-error.log",
      out_file: "bot/logs/pm2-guardian-live-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      // Watch for crashes
      exp_backoff_restart_delay: 100,
      // Kill timeout
      kill_timeout: 3000,
    },
    {
      name: "heartbeat-monitor",
      script: "bot/heartbeat/monitor.py",
      interpreter: "python3",
      cwd: "/Users/shailendrasinghrajawat/Documents/WorkingBot",
      env: {
        PYTHONPATH: "/Users/shailendrasinghrajawat/Documents/WorkingBot"
      },
      // Restart settings
      autorestart: true,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,
      // Memory limits
      max_memory_restart: "200M",
      // Log settings
      log_file: "bot/logs/pm2-heartbeat.log",
      error_file: "bot/logs/pm2-heartbeat-error.log",
      out_file: "bot/logs/pm2-heartbeat-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
    },
    {
      name: "webui-backend",
      script: "webui/backend/app.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot",
        FLASK_ENV: "production",
        PORT: "5555"
      },
      // Restart settings
      autorestart: true,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,
      // Memory limits
      max_memory_restart: "300M",
      // Log settings
      log_file: "bot/logs/pm2-webui.log",
      error_file: "bot/logs/pm2-webui-error.log",
      out_file: "bot/logs/pm2-webui-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
    },
    {
      name: "combined-logs",
      script: "view_combined_logs.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot"
      },
      // Restart settings - DISABLED (manual start only)
      autorestart: false,
      // Memory limits
      max_memory_restart: "100M",
      // Log settings - output to console only
      log_file: "/dev/null",
      error_file: "/dev/null", 
      out_file: "/dev/null",
      // No merge_logs - we want real-time output
      merge_logs: false,
      // Kill timeout
      kill_timeout: 3000,
    }
  ]
};

