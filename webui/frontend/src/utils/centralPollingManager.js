/**
 * Central Polling Manager
 * 
 * Prevents duplicate API calls by centralizing all polling logic.
 * Multiple components can subscribe to the same data without making duplicate requests.
 */

class CentralPollingManager {
  constructor() {
    this.subscriptions = new Map(); // endpoint -> { interval, subscribers, data, lastFetch }
    this.intervals = new Map(); // endpoint -> intervalId
  }

  /**
   * Subscribe to a polled endpoint
   * @param {string} endpoint - API endpoint to poll
   * @param {Function} callback - Called when new data arrives
   * @param {Object} options - { interval: ms, fetchFn: async () => data }
   * @returns {Function} unsubscribe function
   */
  subscribe(endpoint, callback, options = {}) {
    const {
      interval = 10000, // Default 10 seconds
      fetchFn,
      immediate = false
    } = options;

    // Create subscription if doesn't exist
    if (!this.subscriptions.has(endpoint)) {
      this.subscriptions.set(endpoint, {
        interval,
        subscribers: new Set(),
        data: null,
        lastFetch: 0,
        fetchFn,
        isFetching: false
      });
    }

    const sub = this.subscriptions.get(endpoint);
    sub.subscribers.add(callback);

    // If immediate fetch requested and no recent data
    if (immediate && Date.now() - sub.lastFetch > interval) {
      this.fetchData(endpoint);
    } else if (sub.data !== null) {
      // Return cached data immediately
      callback(sub.data);
    }

    // Start polling if not already started
    if (!this.intervals.has(endpoint)) {
      this.startPolling(endpoint);
    }

    // Return unsubscribe function
    return () => {
      const sub = this.subscriptions.get(endpoint);
      if (sub) {
        sub.subscribers.delete(callback);
        
        // Stop polling if no subscribers left
        if (sub.subscribers.size === 0) {
          this.stopPolling(endpoint);
          this.subscriptions.delete(endpoint);
        }
      }
    };
  }

  async fetchData(endpoint) {
    const sub = this.subscriptions.get(endpoint);
    if (!sub || sub.isFetching) return;

    sub.isFetching = true;
    sub.lastFetch = Date.now();

    try {
      const data = await sub.fetchFn();
      sub.data = data;
      
      // Notify all subscribers
      sub.subscribers.forEach(callback => {
        try {
          callback(data);
        } catch (err) {
          console.error(`Error in subscriber callback for ${endpoint}:`, err);
        }
      });
    } catch (error) {
      console.error(`Failed to fetch ${endpoint}:`, error);
      
      // Notify subscribers of error
      sub.subscribers.forEach(callback => {
        try {
          callback({ error: error.message });
        } catch (err) {
          console.error(`Error in error callback for ${endpoint}:`, err);
        }
      });
    } finally {
      sub.isFetching = false;
    }
  }

  startPolling(endpoint) {
    const sub = this.subscriptions.get(endpoint);
    if (!sub) return;

    // Immediate first fetch
    this.fetchData(endpoint);

    // Then poll at interval
    const intervalId = setInterval(() => {
      this.fetchData(endpoint);
    }, sub.interval);

    this.intervals.set(endpoint, intervalId);
  }

  stopPolling(endpoint) {
    const intervalId = this.intervals.get(endpoint);
    if (intervalId) {
      clearInterval(intervalId);
      this.intervals.delete(endpoint);
    }
  }

  /**
   * Get current cached data for an endpoint without subscribing
   */
  getCachedData(endpoint) {
    const sub = this.subscriptions.get(endpoint);
    return sub?.data || null;
  }

  /**
   * Force refresh data for an endpoint
   */
  refresh(endpoint) {
    if (this.subscriptions.has(endpoint)) {
      this.fetchData(endpoint);
    }
  }

  /**
   * Clear all subscriptions and stop all polling
   */
  clearAll() {
    this.intervals.forEach(intervalId => clearInterval(intervalId));
    this.intervals.clear();
    this.subscriptions.clear();
  }

  /**
   * Get statistics about active polls
   */
  getStats() {
    return {
      activeEndpoints: this.subscriptions.size,
      totalSubscribers: Array.from(this.subscriptions.values())
        .reduce((sum, sub) => sum + sub.subscribers.size, 0),
      endpoints: Array.from(this.subscriptions.entries()).map(([endpoint, sub]) => ({
        endpoint,
        subscribers: sub.subscribers.size,
        interval: sub.interval,
        lastFetch: sub.lastFetch,
        hasData: sub.data !== null
      }))
    };
  }
}

// Singleton instance
export const pollingManager = new CentralPollingManager();

/**
 * React hook for using the polling manager
 */
import { useEffect, useState } from 'react';

export function usePolledData(endpoint, fetchFn, options = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);

    const unsubscribe = pollingManager.subscribe(
      endpoint,
      (newData) => {
        if (newData?.error) {
          setError(newData.error);
          setLoading(false);
        } else {
          setData(newData);
          setError(null);
          setLoading(false);
        }
      },
      {
        ...options,
        fetchFn,
        immediate: true
      }
    );

    return unsubscribe;
  }, [endpoint, fetchFn, options.interval]);

  const refresh = () => pollingManager.refresh(endpoint);

  return { data, loading, error, refresh };
}

export default pollingManager;
