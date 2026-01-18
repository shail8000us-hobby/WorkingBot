/**
 * Central Polling Manager
 * Migrated to TypeScript: January 18, 2026
 */

interface PollingSubscription {
  interval: number;
  subscribers: Set<(data: any) => void>;
  data: any;
  lastFetch: number;
  fetchFn: () => Promise<any>;
  isFetching: boolean;
}

interface SubscribeOptions {
  interval?: number;
  fetchFn: () => Promise<any>;
  immediate?: boolean;
}

export class CentralPollingManager {
  private subscriptions: Map<string, PollingSubscription> = new Map();
  private intervals: Map<string, ReturnType<typeof setInterval>> = new Map();

  subscribe(
    endpoint: string,
    callback: (data: any) => void,
    options: SubscribeOptions
  ): () => void {
    const { interval = 10000, fetchFn, immediate = false } = options;

    if (!this.subscriptions.has(endpoint)) {
      this.subscriptions.set(endpoint, {
        interval,
        subscribers: new Set(),
        data: null,
        lastFetch: 0,
        fetchFn,
        isFetching: false,
      });
    }

    const sub = this.subscriptions.get(endpoint)!;
    sub.subscribers.add(callback);

    if (immediate && Date.now() - sub.lastFetch > interval) {
      this.fetchData(endpoint);
    } else if (sub.data !== null) {
      callback(sub.data);
    }

    if (!this.intervals.has(endpoint)) {
      this.startPolling(endpoint);
    }

    return () => {
      const sub = this.subscriptions.get(endpoint);
      if (sub) {
        sub.subscribers.delete(callback);

        if (sub.subscribers.size === 0) {
          this.stopPolling(endpoint);
          this.subscriptions.delete(endpoint);
        }
      }
    };
  }

  private async fetchData(endpoint: string): Promise<void> {
    const sub = this.subscriptions.get(endpoint);
    if (!sub || sub.isFetching) return;

    sub.isFetching = true;
    sub.lastFetch = Date.now();

    try {
      const data = await sub.fetchFn();
      sub.data = data;

      sub.subscribers.forEach((callback) => {
        try {
          callback(data);
        } catch (err) {
          console.error(`Error in subscriber callback for ${endpoint}:`, err);
        }
      });
    } catch (error: any) {
      console.error(`Failed to fetch ${endpoint}:`, error);

      sub.subscribers.forEach((callback) => {
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

  private startPolling(endpoint: string): void {
    const sub = this.subscriptions.get(endpoint);
    if (!sub) return;

    const intervalId = setInterval(() => {
      this.fetchData(endpoint);
    }, sub.interval);

    this.intervals.set(endpoint, intervalId);
  }

  private stopPolling(endpoint: string): void {
    const intervalId = this.intervals.get(endpoint);
    if (intervalId) {
      clearInterval(intervalId);
      this.intervals.delete(endpoint);
    }
  }

  clearAll(): void {
    this.intervals.forEach((id) => clearInterval(id));
    this.intervals.clear();
    this.subscriptions.clear();
  }
}

export const pollingManager = new CentralPollingManager();
export default pollingManager;
