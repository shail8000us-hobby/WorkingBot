/**
 * useConnectionActions — connection management callbacks.
 * Extracted from App.js (Phase 2.4).
 *
 * Provides ensureFresh, handleHardRefresh, and handleClearCache.
 *
 * @param {React.MutableRefObject} connectionManagerRef - ref to the socket connection manager
 * @param {Function} showNotification - (message, severity) => void
 */

import { useCallback } from 'react';

export function useConnectionActions(connectionManagerRef, showNotification) {
  const ensureFresh = useCallback(() => {
    const manager = connectionManagerRef.current;
    if (!manager) return;
    if (manager.socket?.connected) {
      manager.socket.emit('request_full_state');
    } else {
      manager.forceReconnect();
    }
  }, [connectionManagerRef]);

  const handleHardRefresh = useCallback(() => {
    showNotification('Hard refreshing dashboard...', 'info');
    setTimeout(() => window.location.reload(true), 300);
  }, [showNotification]);

  const handleClearCache = useCallback(async () => {
    try {
      showNotification('Clearing browser cache...', 'info');
      if (typeof caches !== 'undefined') {
        const cacheNames = await caches.keys();
        await Promise.all(cacheNames.map((name) => caches.delete(name)));
      }
      localStorage.clear();
      sessionStorage.clear();
      showNotification('Cache cleared. Reloading...', 'success');
      setTimeout(() => window.location.reload(true), 400);
    } catch (error) {
      showNotification(`Failed to clear cache: ${error.message}`, 'error');
    }
  }, [showNotification]);

  return { ensureFresh, handleHardRefresh, handleClearCache };
}
