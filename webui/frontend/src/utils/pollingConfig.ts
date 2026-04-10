/**
 * API Polling Configuration
 * Centralized configuration for all polling intervals
 *
 * Migrated to TypeScript: January 18, 2026
 */

export interface PollingCategory {
  interval: number;
  endpoints: string[];
}

export interface PollingConfigType {
  CRITICAL: PollingCategory;
  IMPORTANT: PollingCategory;
  NORMAL: PollingCategory;
  LOW_PRIORITY: PollingCategory;
}

export const POLLING_CONFIG: PollingConfigType = {
  CRITICAL: {
    interval: 10000,
    endpoints: ['/api/health', '/api/bot/status', '/api/positions', '/api/orders'],
  },

  IMPORTANT: {
    interval: 20000,
    endpoints: [
      '/api/trading/snapshot',
      '/api/risk/safety',
      '/api/capital-protection',
      '/api/monitoring/dashboard',
      '/api/rsi/status',
    ],
  },

  NORMAL: {
    interval: 60000,
    endpoints: [
      '/api/config',
      '/api/robustness/loss-limits',
      '/api/robustness/volatility/status',
      '/api/guardian/status',
      '/api/reconciliation',
      '/api/errors',
    ],
  },

  LOW_PRIORITY: {
    interval: 120000,
    endpoints: [
      '/api/system/health',
      '/api/telegram/status',
      '/api/pm2/status',
      '/api/tmux/status',
      '/api/multi-instance',
      '/api/predictions/spike',
    ],
  },
};

export const getIntervalForEndpoint = (endpoint: string): number => {
  for (const [, config] of Object.entries(POLLING_CONFIG)) {
    if (config.endpoints.includes(endpoint)) {
      return config.interval;
    }
  }
  return POLLING_CONFIG.NORMAL.interval;
};

export default POLLING_CONFIG;
