/**
 * Offline Storage Utility
 * Handles offline data persistence and synchronization
 */

const DB_NAME = 'GridBotWebUI';
const DB_VERSION = 1;
const STORES = {
  config: 'config',
  positions: 'positions',
  orders: 'orders',
  botStatus: 'botStatus',
  pendingActions: 'pendingActions',
};

class OfflineStorage {
  constructor() {
    this.db = null;
    this.isSupported = this.checkSupport();
  }

  /**
   * Check if IndexedDB is supported
   */
  checkSupport() {
    return typeof window !== 'undefined' && 'indexedDB' in window;
  }

  /**
   * Initialize IndexedDB
   */
  async init() {
    if (!this.isSupported) {
      console.warn('IndexedDB not supported, using localStorage fallback');
      return;
    }

    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve(this.db);
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;

        // Create object stores if they don't exist
        Object.values(STORES).forEach((storeName) => {
          if (!db.objectStoreNames.contains(storeName)) {
            const store = db.createObjectStore(storeName, { keyPath: 'id', autoIncrement: true });
            store.createIndex('timestamp', 'timestamp', { unique: false });
          }
        });
      };
    });
  }

  /**
   * Save data to IndexedDB
   */
  async save(storeName, data) {
    if (!this.db) await this.init();

    if (!this.isSupported) {
      // Fallback to localStorage
      try {
        localStorage.setItem(`${DB_NAME}_${storeName}`, JSON.stringify(data));
        return true;
      } catch (error) {
        console.error('localStorage save error:', error);
        return false;
      }
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([storeName], 'readwrite');
      const store = transaction.objectStore(storeName);
      
      const dataWithTimestamp = {
        ...data,
        id: data.id || 'latest',
        timestamp: Date.now(),
      };

      const request = store.put(dataWithTimestamp);

      request.onsuccess = () => resolve(true);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Load data from IndexedDB
   */
  async load(storeName, id = 'latest') {
    if (!this.db) await this.init();

    if (!this.isSupported) {
      // Fallback to localStorage
      try {
        const data = localStorage.getItem(`${DB_NAME}_${storeName}`);
        return data ? JSON.parse(data) : null;
      } catch (error) {
        console.error('localStorage load error:', error);
        return null;
      }
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([storeName], 'readonly');
      const store = transaction.objectStore(storeName);
      const request = store.get(id);

      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Save pending action for later sync
   */
  async queueAction(action) {
    const actionData = {
      id: `action_${Date.now()}`,
      ...action,
      queued: true,
      timestamp: Date.now(),
    };

    return this.save(STORES.pendingActions, actionData);
  }

  /**
   * Get all pending actions
   */
  async getPendingActions() {
    if (!this.db) await this.init();

    if (!this.isSupported) {
      try {
        const data = localStorage.getItem(`${DB_NAME}_${STORES.pendingActions}`);
        return data ? [JSON.parse(data)] : [];
      } catch (error) {
        return [];
      }
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORES.pendingActions], 'readonly');
      const store = transaction.objectStore(STORES.pendingActions);
      const request = store.getAll();

      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Clear pending action after successful sync
   */
  async clearAction(id) {
    if (!this.db) await this.init();

    if (!this.isSupported) {
      return true;
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORES.pendingActions], 'readwrite');
      const store = transaction.objectStore(STORES.pendingActions);
      const request = store.delete(id);

      request.onsuccess = () => resolve(true);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Clear all data from a store
   */
  async clear(storeName) {
    if (!this.db) await this.init();

    if (!this.isSupported) {
      localStorage.removeItem(`${DB_NAME}_${storeName}`);
      return true;
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([storeName], 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.clear();

      request.onsuccess = () => resolve(true);
      request.onerror = () => reject(request.error);
    });
  }
}

// Singleton instance
const offlineStorage = new OfflineStorage();

export default offlineStorage;
export { STORES };
