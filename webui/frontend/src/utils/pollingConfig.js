/**
 * API Polling Configuration
 * 
 * Centralized configuration for all polling intervals to prevent API request storms.
 * 
 * OPTIMIZED: Jan 18, 2026 - Reduced polling frequency for better performance
 * 
 * BEFORE OPTIMIZATION: 5-60 seconds intervals
 * AFTER OPTIMIZATION: 10-120 seconds intervals (50% reduction)
 */

export const POLLING_CONFIG = {
  // Critical real-time data (10 seconds - was 5)
  CRITICAL: {
    interval: 10000,  // INCREASED: 5s -> 10s
    endpoints: [
      '/api/health',
      '/api/bot/status',
      '/api/positions',
      '/api/orders'
    ]
  },

  // Important data (20 seconds - was 10)
  IMPORTANT: {
    interval: 20000,  // INCREASED: 10s -> 20s
    endpoints: [
      '/api/trading/snapshot',
      '/api/risk/safety',
      '/api/capital-protection',
      '/api/monitoring/dashboard',
      '/api/rsi/status'
    ]
  },

  // Normal data (60 seconds - was 30)
  NORMAL: {
    interval: 60000,  // INCREASED: 30s -> 60s
    endpoints: [
      '/api/config',
      '/api/robustness/loss-limits',
      '/api/robustness/volatility/status',
      '/api/guardian/status',
      '/api/reconciliation',
      '/api/errors',
      '/api/market/news',
      '/api/institutional-ai'
    ]
  },

  // Low priority (120 seconds - was 60)
  LOW_PRIORITY: {
    interval: 120000,  // INCREASED: 60s -> 120s
    endpoints: [
      '/api/system/health',
      '/api/telegram/status',
      '/api/pm2/status',
      '/api/tmux/status',
      '/api/multi-instance',
      '/api/predictions/spike'
    ]
  },

  // Very low priority (5 minutes)
  VERY_LOW: {
    interval: 300000,
    endpoints: [
      '/api/logs/history',
      '/api/documentation'
    ]
  }
};

/**
 * Get polling interval for an endpoint
 */
export function getPollingInterval(endpoint) {
  for (const [priority, config] of Object.entries(POLLING_CONFIG)) {
    if (config.endpoints.some(ep => endpoint.includes(ep))) {
      return config.interval;
    }
  }
  
  // Default to 30 seconds for unconfigured endpoints
  return 30000;
}

/**
 * Batch Configuration
 * Group multiple API calls into single batched requests
 */
export const BATCH_CONFIG = {
  // Dashboard batch: positions, orders, bot status, trading snapshot
  dashboard: {
    interval: 5000,
    endpoints: [
      '/api/bot/status',
      '/api/positions',
      '/api/orders',
      '/api/trading/snapshot'
    ],
    batchEndpoint: '/api/batch/dashboard'
  },

  // Risk batch: capital protection, robustness, RSI
  risk: {
    interval: 10000,
    endpoints: [
      '/api/capital-protection',
      '/api/robustness/loss-limits',
      '/api/robustness/volatility/status',
      '/api/rsi/status'
    ],
    batchEndpoint: '/api/batch/risk'
  },

  // System batch: health, PM2, tmux
  system: {
    interval: 30000,
    endpoints: [
      '/api/system/health',
      '/api/pm2/status',
      '/api/tmux/status'
    ],
    batchEndpoint: '/api/batch/system'
  }
};

/**
 * Smart Polling Strategy
 * Adjust polling based on page visibility and network conditions
 */
export class SmartPollingStrategy {
  constructor() {
    this.isVisible = !document.hidden;
    this.isOnline = navigator.onLine;
    this.slowConnection = false;

    // Monitor visibility
    document.addEventListener('visibilitychange', () => {
      this.isVisible = !document.hidden;
    });

    // Monitor online status
    window.addEventListener('online', () => this.isOnline = true);
    window.addEventListener('offline', () => this.isOnline = false);

    // Detect slow connection
    if (navigator.connection) {
      this.updateConnectionSpeed();
      navigator.connection.addEventListener('change', () => {
        this.updateConnectionSpeed();
      });
    }
  }

  updateConnectionSpeed() {
    const conn = navigator.connection;
    if (!conn) return;

    // Slow if 2G or effective type is 'slow-2g'
    this.slowConnection = 
      conn.effectiveType === 'slow-2g' || 
      conn.effectiveType === '2g' ||
      conn.downlink < 1; // Less than 1 Mbps
  }

  /**
   * Get adjusted interval based on conditions
   */
  getAdjustedInterval(baseInterval) {
    // Don't poll if offline
    if (!this.isOnline) {
      return null;
    }

    let multiplier = 1;

    // If page is hidden, poll 4x slower
    if (!this.isVisible) {
      multiplier *= 4;
    }

    // If connection is slow, poll 2x slower
    if (this.slowConnection) {
      multiplier *= 2;
    }

    return baseInterval * multiplier;
  }

  /**
   * Should polling be paused entirely?
   */
  shouldPause() {
    return !this.isOnline || (!this.isVisible && this.slowConnection);
  }
}

export const smartPolling = new SmartPollingStrategy();

/**
 * Stagger Configuration
 * Prevent all components from polling at the same time
 */
export class PollingStagger {
  constructor() {
    this.nextOffset = 0;
    this.offsetIncrement = 200; // 200ms between starts
  }

  /**
   * Get staggered start delay
   */
  getStartDelay() {
    const delay = this.nextOffset;
    this.nextOffset += this.offsetIncrement;
    
    // Reset after 10 seconds
    if (this.nextOffset > 10000) {
      this.nextOffset = 0;
    }

    return delay;
  }
}

export const pollingStagger = new PollingStagger();

/**
 * Request Deduplication
 * Prevent duplicate requests within a time window
 */
export class RequestDeduplicator {
  constructor() {
    this.pending = new Map(); // endpoint -> Promise
    this.cache = new Map(); // endpoint -> { data, timestamp }
    this.cacheTTL = 2000; // Cache responses for 2 seconds
  }

  /**
   * Make deduplicated request
   */
  async request(endpoint, fetchFn) {
    // Check cache first
    const cached = this.cache.get(endpoint);
    if (cached && Date.now() - cached.timestamp < this.cacheTTL) {
      return cached.data;
    }

    // If request is already pending, wait for it
    if (this.pending.has(endpoint)) {
      return this.pending.get(endpoint);
    }

    // Make new request
    const promise = fetchFn()
      .then(data => {
        this.cache.set(endpoint, { data, timestamp: Date.now() });
        this.pending.delete(endpoint);
        return data;
      })
      .catch(error => {
        this.pending.delete(endpoint);
        throw error;
      });

    this.pending.set(endpoint, promise);
    return promise;
  }

  /**
   * Clear cache for endpoint
   */
  clearCache(endpoint) {
    this.cache.delete(endpoint);
  }

  /**
   * Clear all cache
   */
  clearAll() {
    this.cache.clear();
  }
}

export const requestDeduplicator = new RequestDeduplicator();

export default {
  POLLING_CONFIG,
  getPollingInterval,
  BATCH_CONFIG,
  smartPolling,
  pollingStagger,
  requestDeduplicator
};
