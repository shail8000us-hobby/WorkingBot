// PM2 Ecosystem Configuration - DEMO ONLY (SAFE FOR SLEEPING!)
// This file ONLY starts DEMO bots - NO LIVE/REAL MONEY BOTS!

module.exports = {
  apps: [
    {
      name: "gridbot-demo",
      script: "bot/run.py",
      interpreter: "python3",
      cwd: "/Users/shailendrasinghrajawat/Documents/WorkingBot",
      env: {
        PYTHONPATH: "/Users/shailendrasinghrajawat/Documents/WorkingBot",
        TRADING_MODE: "demo",
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
      // Kill timeout
      kill_timeout: 5000,
      // Graceful shutdown
      wait_ready: false,
      listen_timeout: 3000,
    },
    {
      name: "guardian-demo",
      script: "bot/guardian/guardian_bot.py",
      interpreter: "python3",
      cwd: "/Users/shailendrasinghrajawat/Documents/WorkingBot",
      env: {
        PYTHONPATH: "/Users/shailendrasinghrajawat/Documents/WorkingBot",
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
      cwd: "/Users/shailendrasinghrajawat/Documents/WorkingBot",
      env: {
        PYTHONPATH: "/Users/shailendrasinghrajawat/Documents/WorkingBot",
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
    }
  ]
};

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                                                                           ║
// ║  ⚠️  THIS FILE ONLY STARTS DEMO BOTS - NO REAL MONEY!                    ║
// ║                                                                           ║
// ║  Excluded (for safety):                                                   ║
// ║  ❌ gridbot-live                                                          ║
// ║  ❌ guardian-live                                                         ║
// ║                                                                           ║
// ║  To start: pm2 start ecosystem.demo-only.js                              ║
// ║                                                                           ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

