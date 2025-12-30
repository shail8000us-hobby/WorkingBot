// ecosystem.multi-symbol.config.js
// PM2 configuration for multi-symbol GridBot system

module.exports = {
  apps: [
    // =================================================================
    // BTC Bot - Primary trading instance
    // =================================================================
    {
      name: 'gridbot-btc-live',
      script: 'bot/strategy/async_gridbot.py',
      args: 'BTCUSD',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/gridbot-btc-error.log',
      out_file: 'logs/gridbot-btc-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      kill_timeout: 15000,
      restart_delay: 3000
    },
    
    // =================================================================
    // ETH Bot - Secondary trading instance (disabled initially)
    // =================================================================
    {
      name: 'gridbot-eth-live',
      script: 'bot/strategy/async_gridbot.py',
      args: 'ETHUSD',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: false,  // Don't auto-start until fully tested
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/gridbot-eth-error.log',
      out_file: 'logs/gridbot-eth-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      kill_timeout: 15000,
      restart_delay: 3000
    },
    
    // =================================================================
    // Guardian Bot - Multi-symbol safety monitor
    // =================================================================
    {
      name: 'guardian-live',
      script: 'bot/guardian/core/guardian_bot.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/guardian-error.log',
      out_file: 'logs/guardian-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      restart_delay: 5000
    },
    
    // =================================================================
    // WebUI Backend - Development server (port 5556)
    // =================================================================
    {
      name: 'webui-backend-dev',
      script: 'webui/backend/app.py',
      args: '5556',
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
