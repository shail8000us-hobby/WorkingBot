/**
 * Auto-Save Manager
 * Automatically saves form state and drafts
 */

import { storage } from './storage.ts';
import { debounce } from './rateLimiting.ts';

class AutoSaveManager {
  constructor(options = {}) {
    this.autoSaveDelay = options.autoSaveDelay || 2000; // 2 seconds default
    this.maxDrafts = options.maxDrafts || 10;
    this.storagePrefix = 'draft_';
    this.savingCallbacks = new Map();
    this.savedCallbacks = new Map();
  }

  /**
   * Create auto-save handler for a form/component
   */
  createAutoSave(key, options = {}) {
    const {
      delay = this.autoSaveDelay,
      onSaving = null,
      onSaved = null,
      onError = null,
      transform = null,
    } = options;

    // Store callbacks
    if (onSaving) this.savingCallbacks.set(key, onSaving);
    if (onSaved) this.savedCallbacks.set(key, onSaved);

    // Create debounced save function
    const debouncedSave = debounce((data) => {
      this.save(key, data, { transform, onError });
    }, delay);

    return {
      save: debouncedSave,
      saveNow: (data) => this.save(key, data, { transform, onError }),
      load: () => this.load(key, { transform }),
      clear: () => this.clear(key),
      exists: () => this.exists(key),
    };
  }

  /**
   * Save data
   */
  save(key, data, options = {}) {
    try {
      // Emit saving event
      const savingCallback = this.savingCallbacks.get(key);
      if (savingCallback) {
        savingCallback(data);
      }

      // Transform data if needed
      let dataToSave = data;
      if (options.transform && typeof options.transform === 'function') {
        dataToSave = options.transform(data);
      }

      // Save to storage
      const storageKey = this.getStorageKey(key);
      storage.set(storageKey, {
        data: dataToSave,
        savedAt: Date.now(),
        version: 1,
      });

      console.log(`💾 Auto-saved: ${key}`);

      // Emit saved event
      const savedCallback = this.savedCallbacks.get(key);
      if (savedCallback) {
        savedCallback(data);
      }

      // Cleanup old drafts
      this.cleanupOldDrafts();

      return true;
    } catch (error) {
      console.error(`❌ Auto-save failed for ${key}:`, error);
      if (options.onError) {
        options.onError(error);
      }
      return false;
    }
  }

  /**
   * Load saved data
   */
  load(key, options = {}) {
    try {
      const storageKey = this.getStorageKey(key);
      const saved = storage.get(storageKey);

      if (!saved) {
        return null;
      }

      let data = saved.data;

      // Transform data if needed
      if (options.transform && typeof options.transform === 'function') {
        data = options.transform(data);
      }

      console.log(`📥 Loaded draft: ${key} (saved ${this.formatTimestamp(saved.savedAt)})`);

      return {
        data,
        savedAt: saved.savedAt,
        age: Date.now() - saved.savedAt,
      };
    } catch (error) {
      console.error(`❌ Load failed for ${key}:`, error);
      return null;
    }
  }

  /**
   * Clear saved data
   */
  clear(key) {
    const storageKey = this.getStorageKey(key);
    storage.remove(storageKey);
    console.log(`🗑️ Cleared draft: ${key}`);
  }

  /**
   * Check if draft exists
   */
  exists(key) {
    const storageKey = this.getStorageKey(key);
    return storage.has(storageKey);
  }

  /**
   * Get all drafts
   */
  getAllDrafts() {
    const keys = storage.keys();
    const drafts = [];

    keys.forEach((key) => {
      if (key.startsWith(this.storagePrefix)) {
        const saved = storage.get(key);
        if (saved) {
          drafts.push({
            key: key.replace(this.storagePrefix, ''),
            savedAt: saved.savedAt,
            age: Date.now() - saved.savedAt,
            size: JSON.stringify(saved.data).length,
          });
        }
      }
    });

    return drafts.sort((a, b) => b.savedAt - a.savedAt);
  }

  /**
   * Cleanup old drafts
   */
  cleanupOldDrafts() {
    const drafts = this.getAllDrafts();

    // Remove drafts beyond max limit
    if (drafts.length > this.maxDrafts) {
      const toRemove = drafts.slice(this.maxDrafts);
      toRemove.forEach((draft) => {
        this.clear(draft.key);
      });
      console.log(`🗑️ Cleaned up ${toRemove.length} old drafts`);
    }

    // Remove drafts older than 7 days
    const maxAge = 7 * 24 * 60 * 60 * 1000;
    const oldDrafts = drafts.filter((draft) => draft.age > maxAge);
    oldDrafts.forEach((draft) => {
      this.clear(draft.key);
    });
    if (oldDrafts.length > 0) {
      console.log(`🗑️ Cleaned up ${oldDrafts.length} expired drafts`);
    }
  }

  /**
   * Get storage key
   */
  getStorageKey(key) {
    return `${this.storagePrefix}${key}`;
  }

  /**
   * Format timestamp
   */
  formatTimestamp(timestamp) {
    const now = Date.now();
    const diff = now - timestamp;

    if (diff < 60000) {
      return 'just now';
    } else if (diff < 3600000) {
      return `${Math.floor(diff / 60000)}m ago`;
    } else if (diff < 86400000) {
      return `${Math.floor(diff / 3600000)}h ago`;
    } else {
      return `${Math.floor(diff / 86400000)}d ago`;
    }
  }

  /**
   * Export all drafts
   */
  exportDrafts() {
    const drafts = {};
    const keys = storage.keys();

    keys.forEach((key) => {
      if (key.startsWith(this.storagePrefix)) {
        drafts[key] = storage.get(key);
      }
    });

    return drafts;
  }

  /**
   * Import drafts
   */
  importDrafts(drafts) {
    Object.entries(drafts).forEach(([key, value]) => {
      storage.set(key, value);
    });
    console.log(`📥 Imported ${Object.keys(drafts).length} drafts`);
  }
}

// Singleton instance
export const autoSaveManager = new AutoSaveManager({
  autoSaveDelay: 2000,
  maxDrafts: 10,
});

/**
 * React Hook for Auto-Save
 */
const React = require('react');

export const useAutoSave = (key, initialData = null, options = {}) => {
  const [data, setData] = React.useState(initialData);
  const [saving, setSaving] = React.useState(false);
  const [lastSaved, setLastSaved] = React.useState(null);
  const [draftAvailable, setDraftAvailable] = React.useState(false);

  // Create auto-save handler
  const autoSave = React.useMemo(() => {
    return autoSaveManager.createAutoSave(key, {
      ...options,
      onSaving: (data) => {
        setSaving(true);
        if (options.onSaving) options.onSaving(data);
      },
      onSaved: (data) => {
        setSaving(false);
        setLastSaved(Date.now());
        if (options.onSaved) options.onSaved(data);
      },
    });
  }, [key, options]);

  // Check for existing draft on mount
  React.useEffect(() => {
    const draft = autoSave.load();
    if (draft) {
      setDraftAvailable(true);
      setLastSaved(draft.savedAt);
    }
  }, [autoSave]);

  // Auto-save when data changes
  React.useEffect(() => {
    if (data !== null && data !== initialData) {
      autoSave.save(data);
    }
  }, [data, autoSave, initialData]);

  const loadDraft = React.useCallback(() => {
    const draft = autoSave.load();
    if (draft) {
      setData(draft.data);
      setLastSaved(draft.savedAt);
      return true;
    }
    return false;
  }, [autoSave]);

  const clearDraft = React.useCallback(() => {
    autoSave.clear();
    setDraftAvailable(false);
    setLastSaved(null);
  }, [autoSave]);

  const saveNow = React.useCallback(() => {
    if (data !== null) {
      autoSave.saveNow(data);
    }
  }, [data, autoSave]);

  return {
    data,
    setData,
    saving,
    lastSaved,
    draftAvailable,
    loadDraft,
    clearDraft,
    saveNow,
  };
};

/**
 * Auto-Save Status Component Helper
 */
export const getAutoSaveStatus = (saving, lastSaved) => {
  if (saving) {
    return { text: 'Saving...', color: 'info' };
  }

  if (lastSaved) {
    const elapsed = Date.now() - lastSaved;
    if (elapsed < 5000) {
      return { text: 'Saved', color: 'success' };
    } else if (elapsed < 60000) {
      return { text: `Saved ${Math.floor(elapsed / 1000)}s ago`, color: 'default' };
    } else {
      return { text: `Saved ${Math.floor(elapsed / 60000)}m ago`, color: 'default' };
    }
  }

  return { text: 'Not saved', color: 'default' };
};

export default autoSaveManager;
