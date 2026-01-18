/**
 * Offline Indicator Component
 * Shows when the app is offline with cached data
 */

import React, { useState, useEffect } from 'react';
import { WifiOff, Wifi } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import offlineStorage, { STORES } from '../utils/offlineStorage';

function OfflineIndicator() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [hasCachedData, setHasCachedData] = useState(false);
  const [pendingActions, setPendingActions] = useState(0);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Check for cached data
    const checkCachedData = async () => {
      try {
        const config = await offlineStorage.load(STORES.config);
        const positions = await offlineStorage.load(STORES.positions);
        setHasCachedData(Boolean(config || positions));

        const pending = await offlineStorage.getPendingActions();
        setPendingActions(pending.length);
      } catch (error) {
        console.error('Error checking cached data:', error);
      }
    };

    checkCachedData();

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Sync pending actions when coming back online
  useEffect(() => {
    if (isOnline && pendingActions > 0) {
      const syncPendingActions = async () => {
        try {
          const actions = await offlineStorage.getPendingActions();
          console.log(`🔄 Syncing ${actions.length} pending actions...`);

          // Emit event for connection manager to handle
          window.dispatchEvent(
            new CustomEvent('sync-pending-actions', {
              detail: { actions },
            })
          );
        } catch (error) {
          console.error('Error syncing pending actions:', error);
        }
      };

      syncPendingActions();
    }
  }, [isOnline, pendingActions]);

  if (isOnline) {
    return null; // Don't show anything when online
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className="fixed top-16 left-1/2 z-50 -translate-x-1/2"
        style={{ marginTop: 'calc(env(safe-area-inset-top) + 8px)' }}
      >
        <div className="flex items-center gap-3 rounded-xl border border-amber-500/50 bg-amber-500/10 px-4 py-2 backdrop-blur">
          <WifiOff className="h-5 w-5 text-amber-400" />
          <div>
            <p className="text-sm font-semibold text-amber-100">Offline Mode</p>
            {hasCachedData && <p className="text-xs text-amber-300">Showing cached data</p>}
            {pendingActions > 0 && (
              <p className="text-xs text-amber-300">
                {pendingActions} action{pendingActions > 1 ? 's' : ''} pending sync
              </p>
            )}
          </div>
          <Wifi className="h-4 w-4 animate-pulse text-amber-400 opacity-50" />
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

export default OfflineIndicator;
