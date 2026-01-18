/**
 * Offline Storage Utility
 * Handles offline data persistence
 * 
 * Migrated to TypeScript: January 18, 2026
 */

const DB_NAME = 'GridBotWebUI';
const DB_VERSION = 1;

export const STORES = {
  config: 'config',
  positions: 'positions',
  orders: 'orders',
  botStatus: 'botStatus',
  pendingActions: 'pendingActions',
} as const;

type StoreName = typeof STORES[keyof typeof STORES];

export class OfflineStorage {
  private db: IDBDatabase | null = null;
  private isSupported: boolean;

  constructor() {
    this.isSupported = this.checkSupport();
  }

  checkSupport(): boolean {
    return typeof window !== 'undefined' && 'indexedDB' in window;
  }

  async init(): Promise<IDBDatabase | void> {
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
        const db = (event.target as IDBOpenDBRequest).result;
        Object.values(STORES).forEach((storeName) => {
          if (!db.objectStoreNames.contains(storeName)) {
            const store = db.createObjectStore(storeName, { keyPath: 'id', autoIncrement: true });
            store.createIndex('timestamp', 'timestamp', { unique: false });
          }
        });
      };
    });
  }

  async save(storeName: StoreName, data: any): Promise<boolean> {
    if (!this.db) await this.init();

    if (!this.isSupported) {
      try {
        localStorage.setItem(`${DB_NAME}_${storeName}`, JSON.stringify(data));
        return true;
      } catch (error) {
        console.error('localStorage save error:', error);
        return false;
      }
    }

    return new Promise((resolve, reject) => {
      if (!this.db) return reject(new Error('DB not initialized'));
      const transaction = this.db.transaction([storeName], 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.put({ ...data, timestamp: Date.now() });
      request.onsuccess = () => resolve(true);
      request.onerror = () => reject(request.error);
    });
  }

  async get(storeName: StoreName, id?: number): Promise<any> {
    if (!this.db) await this.init();

    if (!this.isSupported) {
      try {
        const item = localStorage.getItem(`${DB_NAME}_${storeName}`);
        return item ? JSON.parse(item) : null;
      } catch (error) {
        console.error('localStorage get error:', error);
        return null;
      }
    }

    return new Promise((resolve, reject) => {
      if (!this.db) return reject(new Error('DB not initialized'));
      const transaction = this.db.transaction([storeName], 'readonly');
      const store = transaction.objectStore(storeName);
      const request = id ? store.get(id) : store.getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async clear(storeName: StoreName): Promise<boolean> {
    if (!this.db) await this.init();

    if (!this.isSupported) {
      localStorage.removeItem(`${DB_NAME}_${storeName}`);
      return true;
    }

    return new Promise((resolve, reject) => {
      if (!this.db) return reject(new Error('DB not initialized'));
      const transaction = this.db.transaction([storeName], 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.clear();
      request.onsuccess = () => resolve(true);
      request.onerror = () => reject(request.error);
    });
  }
}

export const offlineStorage = new OfflineStorage();
export default offlineStorage;
