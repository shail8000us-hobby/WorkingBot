// Observability Module - PM2 Ecosystem Configuration
// Run this server separately from the main bot process

module.exports = {
  apps: [
    {
      name: 'metrics-server',
      script: 'observability/server/metrics_server.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      watch: false,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      env: {
        METRICS_PORT: 9091,
        PYTHONUNBUFFERED: '1'
      },
      error_file: 'logs/metrics-server-error.log',
      out_file: 'logs/metrics-server-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      
      // Resource limits
      max_memory_restart: '200M',
      
      // Graceful shutdown
      kill_timeout: 5000,
      wait_ready: true,
      listen_timeout: 10000
    }
  ]
};
