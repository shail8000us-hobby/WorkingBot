/**
 * IndexedDB utility for Options Panel heavy data storage
 * Phase 3 Optimization: Move large data from localStorage to IndexedDB
 * 
 * Benefits:
 * - No 5-10MB localStorage limit
 * - Faster read/write for large datasets
 * - Non-blocking async operations
 * - Better for storing historical trade data
 */

const DB_NAME = 'OptionsTraderDB';
const DB_VERSION = 1;

const STORES = {
  // CLOSED_POSITIONS removed — Phase 2: closed positions are now purely server-side
  // (closed_position_store.py). The backend merges phantom rows into the dashboard response.
  SLTP_SETTINGS: 'sltpSettings',
  MAX_LOSS_SETTINGS: 'maxLossSettings',
  TAKE_PROFIT_SETTINGS: 'takeProfitSettings',
  HISTORICAL_TRADES: 'historicalTrades',
  SKIP_CONFIRM_STRIKES: 'skipConfirmStrikes',
  CUSTOM_ORDER: 'customOrder',
};

class OptionsDB {
  constructor() {
    this.db = null;
    this.initPromise = this.init();
  }

  /**
   * Initialize IndexedDB
   */
  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => {
        console.error('IndexedDB failed to open:', request.error);
        reject(request.error);
      };

      request.onsuccess = () => {
        this.db = request.result;
        console.log('✅ IndexedDB initialized:', DB_NAME);
        resolve(this.db);
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;

        // Create object stores
        // Note: CLOSED_POSITIONS store was removed — closed positions are now
        // purely server-side (closed_position_store.py). See Phase 2 cleanup.

        if (!db.objectStoreNames.contains(STORES.SLTP_SETTINGS)) {
          db.createObjectStore(STORES.SLTP_SETTINGS, { keyPath: 'symbol' });
        }

        if (!db.objectStoreNames.contains(STORES.MAX_LOSS_SETTINGS)) {
          db.createObjectStore(STORES.MAX_LOSS_SETTINGS, { keyPath: 'symbol' });
        }

        if (!db.objectStoreNames.contains(STORES.TAKE_PROFIT_SETTINGS)) {
          db.createObjectStore(STORES.TAKE_PROFIT_SETTINGS, { keyPath: 'symbol' });
        }

        if (!db.objectStoreNames.contains(STORES.HISTORICAL_TRADES)) {
          const store = db.createObjectStore(STORES.HISTORICAL_TRADES, { keyPath: 'id', autoIncrement: true });
          store.createIndex('symbol', 'symbol', { unique: false });
          store.createIndex('timestamp', 'timestamp', { unique: false });
          store.createIndex('date', 'date', { unique: false });
        }

        if (!db.objectStoreNames.contains(STORES.SKIP_CONFIRM_STRIKES)) {
          db.createObjectStore(STORES.SKIP_CONFIRM_STRIKES, { keyPath: 'symbol' });
        }

        if (!db.objectStoreNames.contains(STORES.CUSTOM_ORDER)) {
          db.createObjectStore(STORES.CUSTOM_ORDER, { keyPath: 'id' });
        }

        console.log('✅ IndexedDB upgraded to version', DB_VERSION);
      };
    });
  }

  /**
   * Get a value from a store
   */
  async get(storeName, key) {
    await this.initPromise;
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(storeName, 'readonly');
      const store = transaction.objectStore(storeName);
      const request = store.get(key);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Get all values from a store
   */
  async getAll(storeName) {
    await this.initPromise;
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(storeName, 'readonly');
      const store = transaction.objectStore(storeName);
      const request = store.getAll();

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Put a value into a store
   */
  async put(storeName, value) {
    await this.initPromise;
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(storeName, 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.put(value);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Delete a value from a store
   */
  async delete(storeName, key) {
    await this.initPromise;
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(storeName, 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.delete(key);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Clear all data from a store
   */
  async clear(storeName) {
    await this.initPromise;
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(storeName, 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.clear();

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Get all skip confirm strikes as object
   */
  async getSkipConfirmStrikesObject() {
    const all = await this.getAll(STORES.SKIP_CONFIRM_STRIKES);
    const obj = {};
    all.forEach(item => {
      const { symbol, ...rest } = item;
      obj[symbol] = rest;
    });
    return obj;
  }

  /**
   * Get custom order array
   */
  async getCustomOrder() {
    const data = await this.get(STORES.CUSTOM_ORDER, 'default');
    return data?.order || [];
  }

  /**
   * Save custom order array
   */
  async saveCustomOrder(order) {
    return this.put(STORES.CUSTOM_ORDER, { id: 'default', order });
  }
}

// Export singleton instance
const optionsDB = new OptionsDB();
export default optionsDB;
export { STORES };
