/**
 * PM2 Ecosystem Configuration - WebUI-Compatible Multi-Instance Setup
 * Version: 7.0 (WebUI Integration)
 * 
 * CRITICAL: Process naming must match WebUI expectations
 * 
 * WebUI Process Manager expects:
 * - Format: gridbot-{SYMBOL}-{MODE}
 * - Examples: gridbot-BTCUSD-LONG, gridbot-ETHUSD-SHORT
 * - Frontend extracts symbol from pattern: /-(BTCUSD|ETHUSD|[A-Z]{6})(?:-|$)/i
 * - Groups processes "By Symbol" in PM2 Process Manager tab
 * 
 * Each bot instance:
 * - INSTANCE_NAME env var must match config.yaml instance keys
 * - Process name visible in both PM2 CLI and WebUI
 * - Independent logs, memory limits, graceful shutdown
 * 
 * Usage:
 *   pm2 start ecosystem.production.config.js              # Start all
 *   pm2 start ecosystem.production.config.js --only gridbot-BTCUSD-LONG
 *   pm2 logs gridbot-BTCUSD-LONG                         # View logs
 *   pm2 restart gridbot-BTCUSD-LONG                      # Restart specific
 *   pm2 delete all && pm2 start ecosystem.production.config.js  # Clean restart
 */

module.exports = {
  apps: [
    // ========================================================================
    // TRADING BOTS - Multi-Instance Architecture
    // ========================================================================
    
    // BTC LONG Trading Bot
    {
      name: 'gridbot-BTCUSD-LONG',
      script: 'bot/strategy/async_gridbot.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      args: 'BTCUSD',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        INSTANCE_NAME: 'BTCUSD_LONG',
        PYTHONUNBUFFERED: '1',
        LOG_LEVEL: 'INFO'
      },
      error_file: 'logs/pm2/gridbot-BTCUSD-LONG-error.log',
      out_file: 'logs/pm2/gridbot-BTCUSD-LONG-out.log',
      time: true,
      kill_timeout: 30000, // 30s for graceful shutdown (cancel orders)
      wait_ready: false,
      listen_timeout: 10000
    },

    // BTC SHORT Trading Bot
    {
      name: 'gridbot-BTCUSD-SHORT',
      script: 'bot/strategy/async_gridbot.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      args: 'BTCUSD',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        INSTANCE_NAME: 'BTCUSD_SHORT',
        PYTHONUNBUFFERED: '1',
        LOG_LEVEL: 'INFO'
      },
      error_file: 'logs/pm2/gridbot-BTCUSD-SHORT-error.log',
      out_file: 'logs/pm2/gridbot-BTCUSD-SHORT-out.log',
      time: true,
      kill_timeout: 30000,
      wait_ready: false,
      listen_timeout: 10000
    },

    // ETH LONG Trading Bot
    {
      name: 'gridbot-ETHUSD-LONG',
      script: 'bot/strategy/async_gridbot.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      args: 'ETHUSD',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        INSTANCE_NAME: 'ETHUSD_LONG',
        PYTHONUNBUFFERED: '1',
        LOG_LEVEL: 'INFO'
      },
      error_file: 'logs/pm2/gridbot-ETHUSD-LONG-error.log',
      out_file: 'logs/pm2/gridbot-ETHUSD-LONG-out.log',
      time: true,
      kill_timeout: 30000,
      wait_ready: false,
      listen_timeout: 10000
    },

    // ETH SHORT Trading Bot (disabled by default)
    {
      name: 'gridbot-ETHUSD-SHORT',
      script: 'bot/strategy/async_gridbot.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      args: 'ETHUSD',
      instances: 1,
      autorestart: false, // Disabled - enable when ETH SHORT config ready
      watch: false,
      max_memory_restart: '1G',
      env: {
        INSTANCE_NAME: 'ETHUSD_SHORT',
        PYTHONUNBUFFERED: '1',
        LOG_LEVEL: 'INFO'
      },
      error_file: 'logs/pm2/gridbot-ETHUSD-SHORT-error.log',
      out_file: 'logs/pm2/gridbot-ETHUSD-SHORT-out.log',
      time: true,
      kill_timeout: 30000,
      wait_ready: false,
      listen_timeout: 10000
    },

    // ========================================================================
    // GUARDIAN MONITORING SYSTEM
    // ========================================================================
    
    // Guardian for BTCUSD
    {
      name: 'guardian-BTCUSD',
      script: 'bot/guardian/core/guardian_bot.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      args: '--symbol BTCUSD',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONUNBUFFERED: '1',
        LOG_LEVEL: 'INFO',
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot'
      },
      error_file: 'logs/pm2/guardian-BTCUSD-error.log',
      out_file: 'logs/pm2/guardian-BTCUSD-out.log',
      time: true,
      kill_timeout: 15000
    },

    // Guardian for ETHUSD
    {
      name: 'guardian-ETHUSD',
      script: 'bot/guardian/core/guardian_bot.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      args: '--symbol ETHUSD',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONUNBUFFERED: '1',
        LOG_LEVEL: 'INFO',
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot'
      },
      error_file: 'logs/pm2/guardian-ETHUSD-error.log',
      out_file: 'logs/pm2/guardian-ETHUSD-out.log',
      time: true,
      kill_timeout: 15000
    },

    // ========================================================================
    // WEBUI BACKEND SERVER
    // ========================================================================
    
    {
      name: 'webui-backend',
      script: 'webui/backend/app.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        FLASK_ENV: 'production',
        PYTHONUNBUFFERED: '1'
      },
      error_file: 'logs/pm2/webui-backend-error.log',
      out_file: 'logs/pm2/webui-backend-out.log',
      time: true
    }
  ]
};
