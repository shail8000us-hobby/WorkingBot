// ecosystem.multi-symbol.config.js
// PM2 configuration for multi-instance GridBot system
// Updated: January 2026 for v6.0 --instance argument
//
// V6.0 ARCHITECTURE: Instance = Symbol + Mode
// - BTCUSD_LONG and BTCUSD_SHORT can run simultaneously
// - Each instance has its own database and RSI thresholds

module.exports = {
  apps: [
    // =================================================================
    // BTC LONG Bot - Primary trading instance
    // =================================================================
    {
      name: 'gridbot-btcusd-long',
      script: 'python3',
      args: '-m bot.run --instance BTCUSD_LONG',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/gridbot-btcusd-long-error.log',
      out_file: 'logs/gridbot-btcusd-long-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      kill_timeout: 15000,
      restart_delay: 3000
    },
    
    // =================================================================
    // BTC SHORT Bot - Can run simultaneously with LONG (v6.0)
    // =================================================================
    {
      name: 'gridbot-btcusd-short',
      script: 'python3',
      args: '-m bot.run --instance BTCUSD_SHORT',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: false,  // Disabled until SHORT strategy configured
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/gridbot-btcusd-short-error.log',
      out_file: 'logs/gridbot-btcusd-short-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      kill_timeout: 15000,
      restart_delay: 3000
    },
    
    // =================================================================
    // ETH LONG Bot - Secondary trading instance
    // =================================================================
    {
      name: 'gridbot-ethusd-long',
      script: 'python3',
      args: '-m bot.run --instance ETHUSD_LONG',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: false,  // Don't auto-start until fully tested
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/gridbot-ethusd-long-error.log',
      out_file: 'logs/gridbot-ethusd-long-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      kill_timeout: 15000,
      restart_delay: 3000
    },
    
    // =================================================================
    // Guardian Bots - Per-Instance Risk Monitoring (v6.0)
    // Each guardian monitors a specific instance with its own RSI thresholds
    // =================================================================
    {
      name: 'guardian-btcusd-long',
      script: 'python3',
      args: 'start_guardian.py --instance BTCUSD_LONG',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/guardian-btcusd-long-error.log',
      out_file: 'logs/guardian-btcusd-long-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      restart_delay: 5000
    },
    {
      name: 'guardian-btcusd-short',
      script: 'python3',
      args: 'start_guardian.py --instance BTCUSD_SHORT',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: false,  // Disabled until SHORT trading starts
      watch: false,
      max_memory_restart: '300M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/guardian-btcusd-short-error.log',
      out_file: 'logs/guardian-btcusd-short-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      restart_delay: 5000
    },
    {
      name: 'guardian-ethusd-long',
      script: 'python3',
      args: 'start_guardian.py --instance ETHUSD_LONG',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: false,  // Disabled until ETH trading starts
      watch: false,
      max_memory_restart: '300M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/guardian-ethusd-long-error.log',
      out_file: 'logs/guardian-ethusd-long-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      restart_delay: 5000
    },
    
    // =================================================================
    // WebUI Backend - Development server (port 5557)
    // =================================================================
    {
      name: 'webui-backend-dev',
      script: 'webui/backend/app.py',
      args: '5557',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        FLASK_PORT: '5556',
        FLASK_ENV: 'development'
      },
      error_file: 'logs/webui-dev-error.log',
      out_file: 'logs/webui-dev-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss'
    }
  ]
};
