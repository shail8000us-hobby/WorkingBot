/**
 * Optimistic Update Manager
 * Provides instant UI feedback before server confirms
 */
class OptimisticUpdateManager {
  constructor() {
    this.pendingUpdates = new Map();
    this.rollbackHandlers = new Map();
  }

  /**
   * Execute an optimistic update
   * @param {string} id - Unique identifier for this update
   * @param {Function} optimisticFn - Function that updates local state optimistically
   * @param {Function} serverFn - Function that makes the server call
   * @param {Function} rollbackFn - Function to rollback if server call fails
   * @returns {Promise} Server response
   */
  async execute(id, optimisticFn, serverFn, rollbackFn) {
    // Execute optimistic update immediately
    try {
      const optimisticResult = optimisticFn();
      this.pendingUpdates.set(id, { optimisticResult, timestamp: Date.now() });
      this.rollbackHandlers.set(id, rollbackFn);
    } catch (error) {
      console.error('Optimistic update failed:', error);
      throw error;
    }

    // Execute server call
    try {
      const serverResult = await serverFn();
      this.pendingUpdates.delete(id);
      this.rollbackHandlers.delete(id);
      return serverResult;
    } catch (error) {
      // Server call failed, rollback optimistic update
      console.warn('Server call failed, rolling back optimistic update:', id);
      const rollback = this.rollbackHandlers.get(id);
      if (rollback) {
        rollback(error);
      }
      this.pendingUpdates.delete(id);
      this.rollbackHandlers.delete(id);
      throw error;
    }
  }

  /**
   * Check if an update is pending
   * @param {string} id - Update identifier
   * @returns {boolean}
   */
  isPending(id) {
    return this.pendingUpdates.has(id);
  }

  /**
   * Get all pending updates
   * @returns {Array} Array of pending update IDs
   */
  getPending() {
    return Array.from(this.pendingUpdates.keys());
  }

  /**
   * Clear all pending updates (use with caution)
   */
  clearAll() {
    this.pendingUpdates.clear();
    this.rollbackHandlers.clear();
  }
}

// Singleton instance
export const optimisticManager = new OptimisticUpdateManager();

/**
 * React Hook for Optimistic Updates
 * @param {Function} setStateFn - State setter function (e.g., setErrors)
 * @param {Function} refreshFn - Function to refresh data from server
 * @returns {Function} Handler function
 */
export const useOptimisticUpdate = (setStateFn, refreshFn) => {
  const handleOptimisticUpdate = async (id, updateFn, serverFn, options = {}) => {
    const { 
      showSuccess = true, 
      showError = true,
      successMessage = 'Update successful',
      errorMessage = 'Update failed'
    } = options;

    try {
      await optimisticManager.execute(
        id,
        // Optimistic update
        () => setStateFn(prev => updateFn(prev)),
        // Server call
        serverFn,
        // Rollback
        (error) => {
          console.error('Rolling back:', error);
          refreshFn(); // Refresh from server to restore correct state
          if (showError) {
            // Emit error event for notification system
            window.dispatchEvent(new CustomEvent('showNotification', {
              detail: { message: errorMessage, severity: 'error' }
            }));
          }
        }
      );

      if (showSuccess) {
        window.dispatchEvent(new CustomEvent('showNotification', {
          detail: { message: successMessage, severity: 'success' }
        }));
      }
    } catch (error) {
      // Error already handled in rollback
      console.error('Optimistic update error:', error);
    }
  };

  return handleOptimisticUpdate;
};

/**
 * Helper functions for common optimistic updates
 */

// Optimistic array item removal
export const optimisticRemove = (array, id, idField = 'id') => {
  return array.filter(item => item[idField] !== id);
};

// Optimistic array item update
export const optimisticUpdate = (array, id, updates, idField = 'id') => {
  return array.map(item => 
    item[idField] === id ? { ...item, ...updates } : item
  );
};

// Optimistic array item addition
export const optimisticAdd = (array, newItem, position = 'end') => {
  return position === 'start' ? [newItem, ...array] : [...array, newItem];
};

// Optimistic object property update
export const optimisticObjectUpdate = (obj, updates) => {
  return { ...obj, ...updates };
};

/**
 * Batch optimistic updates
 */
export class BatchOptimisticUpdate {
  constructor() {
    this.updates = [];
  }

  add(id, optimisticFn, serverFn, rollbackFn) {
    this.updates.push({ id, optimisticFn, serverFn, rollbackFn });
    return this;
  }

  async execute() {
    // Execute all optimistic updates immediately
    this.updates.forEach(({ id, optimisticFn }) => {
      try {
        optimisticFn();
      } catch (error) {
        console.error('Batch optimistic update failed:', id, error);
      }
    });

    // Execute all server calls
    const results = await Promise.allSettled(
      this.updates.map(({ serverFn }) => serverFn())
    );

    // Handle failures
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        const { rollbackFn } = this.updates[index];
        if (rollbackFn) {
          rollbackFn(result.reason);
        }
      }
    });

    return results;
  }
}

export default optimisticManager;

