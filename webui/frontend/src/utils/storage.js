/**
 * Persistent Storage Utility
 * Remembers user preferences and state across refreshes
 */
class PersistentStorage {
  constructor(prefix = 'gridbot_') {
    this.prefix = prefix;
    this.maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days default
  }

  /**
   * Set a value in storage
   * @param {string} key - Storage key
   * @param {any} value - Value to store (will be JSON stringified)
   * @param {number} maxAge - Optional max age in milliseconds
   */
  set(key, value, maxAge = this.maxAge) {
    try {
      const item = {
        value,
        timestamp: Date.now(),
        maxAge,
      };
      localStorage.setItem(this.prefix + key, JSON.stringify(item));
      return true;
    } catch (error) {
      console.error('Storage set error:', error);
      // Handle quota exceeded
      if (error.name === 'QuotaExceededError') {
        this.clearOldest();
        // Try again
        try {
          localStorage.setItem(this.prefix + key, JSON.stringify({
            value,
            timestamp: Date.now(),
            maxAge,
          }));
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
   * @param {string} key - Storage key
   * @param {any} defaultValue - Default value if not found or expired
   * @returns {any} Stored value or default
   */
  get(key, defaultValue = null) {
    try {
      const itemStr = localStorage.getItem(this.prefix + key);
      if (!itemStr) return defaultValue;
      
      const item = JSON.parse(itemStr);
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
   * @param {string} key - Storage key
   */
  remove(key) {
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
  clear() {
    try {
      const keys = Object.keys(localStorage);
      keys.forEach(key => {
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
   * @returns {string[]} Array of keys (without prefix)
   */
  keys() {
    try {
      const keys = Object.keys(localStorage);
      return keys
        .filter(key => key.startsWith(this.prefix))
        .map(key => key.substring(this.prefix.length));
    } catch (error) {
      console.error('Storage keys error:', error);
      return [];
    }
  }

  /**
   * Check if a key exists and is not expired
   * @param {string} key - Storage key
   * @returns {boolean}
   */
  has(key) {
    const value = this.get(key);
    return value !== null;
  }

  /**
   * Get storage size in bytes
   * @returns {number} Size in bytes
   */
  getSize() {
    try {
      let size = 0;
      const keys = Object.keys(localStorage);
      keys.forEach(key => {
        if (key.startsWith(this.prefix)) {
          size += localStorage.getItem(key).length;
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
  clearOldest() {
    try {
      const items = [];
      const keys = Object.keys(localStorage);
      
      keys.forEach(key => {
        if (key.startsWith(this.prefix)) {
          try {
            const item = JSON.parse(localStorage.getItem(key));
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
   * @returns {Object} All stored data
   */
  export() {
    const data = {};
    this.keys().forEach(key => {
      data[key] = this.get(key);
    });
    return data;
  }

  /**
   * Import data
   * @param {Object} data - Data to import
   */
  import(data) {
    Object.entries(data).forEach(([key, value]) => {
      this.set(key, value);
    });
  }
}

// Create singleton instance
export const storage = new PersistentStorage('gridbot_');

// Convenience methods for common keys
export const userPreferences = {
  get theme() {
    return storage.get('theme', 'dark');
  },
  set theme(value) {
    storage.set('theme', value);
  },
  
  get expanded() {
    return storage.get('errorPanel_expanded', true);
  },
  set expanded(value) {
    storage.set('errorPanel_expanded', value);
  },
  
  get selectedTab() {
    return storage.get('selectedTab', 0);
  },
  set selectedTab(value) {
    storage.set('selectedTab', value);
  },
  
  get autoRefresh() {
    return storage.get('autoRefresh', true);
  },
  set autoRefresh(value) {
    storage.set('autoRefresh', value);
  },
};

export default storage;

