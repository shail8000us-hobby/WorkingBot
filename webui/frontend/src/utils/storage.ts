/**
 * Persistent Storage Utility
 * Remembers user preferences and state across refreshes
 *
 * Migrated to TypeScript: January 18, 2026
 * Safe: Pure localStorage wrapper, no trading logic
 */

interface StorageItem<T> {
  value: T;
  timestamp: number;
  maxAge: number;
}

export interface UserPreferences {
  theme: string;
  expanded: boolean;
  selectedTab: number;
  autoRefresh: boolean;
}

class PersistentStorage {
  private prefix: string;
  private maxAge: number;

  constructor(prefix: string = 'gridbot_') {
    this.prefix = prefix;
    this.maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days default
  }

  /**
   * Set a value in storage
   */
  set<T>(key: string, value: T, maxAge: number = this.maxAge): boolean {
    try {
      const item: StorageItem<T> = {
        value,
        timestamp: Date.now(),
        maxAge,
      };
      localStorage.setItem(this.prefix + key, JSON.stringify(item));
      return true;
    } catch (error: any) {
      console.error('Storage set error:', error);
      // Handle quota exceeded
      if (error.name === 'QuotaExceededError') {
        this.clearOldest();
        // Try again
        try {
          localStorage.setItem(
            this.prefix + key,
            JSON.stringify({
              value,
              timestamp: Date.now(),
              maxAge,
            })
          );
          return true;
        } catch (e) {
          console.error('Storage still full after cleanup:', e);
        }
      }
      return false;
    }
  }

  /**
   * Get a value from storage
   */
  get<T>(key: string, defaultValue: T | null = null): T | null {
    try {
      const itemStr = localStorage.getItem(this.prefix + key);
      if (!itemStr) return defaultValue;

      const item: StorageItem<T> = JSON.parse(itemStr);
      const age = Date.now() - item.timestamp;

      // Check if expired
      if (age > item.maxAge) {
        this.remove(key);
        return defaultValue;
      }

      return item.value;
    } catch (error) {
      console.error('Storage get error:', error);
      return defaultValue;
    }
  }

  /**
   * Remove a value from storage
   */
  remove(key: string): boolean {
    try {
      localStorage.removeItem(this.prefix + key);
      return true;
    } catch (error) {
      console.error('Storage remove error:', error);
      return false;
    }
  }

  /**
   * Clear all items with this prefix
   */
  clear(): boolean {
    try {
      const keys = Object.keys(localStorage);
      keys.forEach((key) => {
        if (key.startsWith(this.prefix)) {
          localStorage.removeItem(key);
        }
      });
      return true;
    } catch (error) {
      console.error('Storage clear error:', error);
      return false;
    }
  }

  /**
   * Get all keys with this prefix
   */
  keys(): string[] {
    try {
      const keys = Object.keys(localStorage);
      return keys
        .filter((key) => key.startsWith(this.prefix))
        .map((key) => key.substring(this.prefix.length));
    } catch (error) {
      console.error('Storage keys error:', error);
      return [];
    }
  }

  /**
   * Check if a key exists and is not expired
   */
  has(key: string): boolean {
    const value = this.get(key);
    return value !== null;
  }

  /**
   * Get storage size in bytes
   */
  getSize(): number {
    try {
      let size = 0;
      const keys = Object.keys(localStorage);
      keys.forEach((key) => {
        if (key.startsWith(this.prefix)) {
          const item = localStorage.getItem(key);
          size += item ? item.length : 0;
        }
      });
      return size;
    } catch (error) {
      console.error('Storage getSize error:', error);
      return 0;
    }
  }

  /**
   * Clear oldest items to free up space
   */
  clearOldest(): void {
    try {
      const items: Array<{ key: string; timestamp: number }> = [];
      const keys = Object.keys(localStorage);

      keys.forEach((key) => {
        if (key.startsWith(this.prefix)) {
          try {
            const item = JSON.parse(localStorage.getItem(key) || '{}');
            items.push({ key, timestamp: item.timestamp });
          } catch (e) {
            // Invalid item, remove it
            localStorage.removeItem(key);
          }
        }
      });

      // Sort by timestamp (oldest first)
      items.sort((a, b) => a.timestamp - b.timestamp);

      // Remove oldest 20%
      const toRemove = Math.ceil(items.length * 0.2);
      for (let i = 0; i < toRemove; i++) {
        localStorage.removeItem(items[i].key);
      }

      console.log(`Cleared ${toRemove} oldest items from storage`);
    } catch (error) {
      console.error('Storage clearOldest error:', error);
    }
  }

  /**
   * Export all data
   */
  export(): Record<string, any> {
    const data: Record<string, any> = {};
    this.keys().forEach((key) => {
      data[key] = this.get(key);
    });
    return data;
  }

  /**
   * Import data
   */
  import(data: Record<string, any>): void {
    Object.entries(data).forEach(([key, value]) => {
      this.set(key, value);
    });
  }
}

// Create singleton instance
export const storage = new PersistentStorage('gridbot_');

// Convenience methods for common keys
export const userPreferences = {
  get theme(): string {
    return storage.get<string>('theme', 'dark') || 'dark';
  },
  set theme(value: string) {
    storage.set('theme', value);
  },

  get expanded(): boolean {
    return storage.get<boolean>('errorPanel_expanded', true) ?? true;
  },
  set expanded(value: boolean) {
    storage.set('errorPanel_expanded', value);
  },

  get selectedTab(): number {
    return storage.get<number>('selectedTab', 0) ?? 0;
  },
  set selectedTab(value: number) {
    storage.set('selectedTab', value);
  },

  get autoRefresh(): boolean {
    return storage.get<boolean>('autoRefresh', true) ?? true;
  },
  set autoRefresh(value: boolean) {
    storage.set('autoRefresh', value);
  },

  get selectedSection(): string | null {
    return storage.get<string>('selectedSection', null);
  },
  set selectedSection(value: string) {
    storage.set('selectedSection', value);
  },
};

export default storage;
