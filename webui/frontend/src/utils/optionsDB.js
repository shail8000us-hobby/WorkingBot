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
  CLOSED_POSITIONS: 'closedPositions',
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
        if (!db.objectStoreNames.contains(STORES.CLOSED_POSITIONS)) {
          const store = db.createObjectStore(STORES.CLOSED_POSITIONS, { keyPath: 'symbol' });
          store.createIndex('timestamp', 'timestamp', { unique: false });
        }

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
   * Migrate data from localStorage to IndexedDB
   */
  async migrateFromLocalStorage() {
    try {
      // Migrate closed positions
      const closedPositions = localStorage.getItem('options_closed_positions');
      if (closedPositions) {
        const data = JSON.parse(closedPositions);
        for (const [symbol, value] of Object.entries(data)) {
          await this.put(STORES.CLOSED_POSITIONS, { 
            symbol, 
            ...value,
            timestamp: Date.now()
          });
        }
        console.log('✅ Migrated closed positions to IndexedDB');
      }

      // Migrate skip confirm strikes
      const skipConfirm = localStorage.getItem('options_skip_confirm_strikes');
      if (skipConfirm) {
        const data = JSON.parse(skipConfirm);
        for (const [symbol, value] of Object.entries(data)) {
          await this.put(STORES.SKIP_CONFIRM_STRIKES, { symbol, ...value });
        }
        console.log('✅ Migrated skip confirm strikes to IndexedDB');
      }

      // Migrate custom order
      const customOrder = localStorage.getItem('options_custom_order');
      if (customOrder) {
        await this.put(STORES.CUSTOM_ORDER, { 
          id: 'default', 
          order: JSON.parse(customOrder) 
        });
        console.log('✅ Migrated custom order to IndexedDB');
      }

      return true;
    } catch (err) {
      console.error('Migration error:', err);
      return false;
    }
  }

  /**
   * Get all closed positions as object (backward compatible with localStorage format)
   */
  async getClosedPositionsObject() {
    const all = await this.getAll(STORES.CLOSED_POSITIONS);
    const obj = {};
    all.forEach(item => {
      const { symbol, ...rest } = item;
      obj[symbol] = rest;
    });
    return obj;
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
