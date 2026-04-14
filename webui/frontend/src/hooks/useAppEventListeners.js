/**
 * useAppEventListeners — side-effect-only hook that wires up global event listeners.
 * Extracted from App.js (Phase 2.4).
 *
 * Combines:
 *  - visibilitychange → ensureFresh on tab re-focus
 *  - online → ensureFresh when network recovers
 *  - showNotification custom event → showNotification()
 *  - keyboard-start / keyboard-stop / keyboard-refresh events
 */

import { useEffect, useRef, useCallback } from 'react';

export function useAppEventListeners({
  ensureFresh,
  handleStartBot,
  handleStopBot,
  showNotification,
}) {
  const refreshInFlightRef = useRef(false);
  const refreshPendingRef = useRef(false);
  const refreshTimerRef = useRef(null);

  const runEnsureFresh = useCallback(async () => {
    if (refreshInFlightRef.current) {
      refreshPendingRef.current = true;
      return;
    }

    refreshInFlightRef.current = true;
    try {
      await Promise.resolve(ensureFresh());
    } finally {
      refreshInFlightRef.current = false;
      if (refreshPendingRef.current) {
        refreshPendingRef.current = false;
        Promise.resolve().then(() => {
          runEnsureFresh();
        });
      }
    }
  }, [ensureFresh]);

  const scheduleEnsureFresh = useCallback(
    (delayMs = 0) => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }

      refreshTimerRef.current = setTimeout(() => {
        runEnsureFresh();
      }, delayMs);
    },
    [runEnsureFresh]
  );

  useEffect(() => {
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, []);

  // Tab visibility → refresh data on re-focus
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) scheduleEnsureFresh(350);
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [scheduleEnsureFresh]);

  // Network recovery → refresh data
  useEffect(() => {
    const handleOnline = () => scheduleEnsureFresh(500);
    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
  }, [scheduleEnsureFresh]);

  // Custom notification event (used by child components)
  useEffect(() => {
    const handleNotification = (event) => {
      showNotification(event.detail.message, event.detail.severity);
    };
    window.addEventListener('showNotification', handleNotification);
    return () => window.removeEventListener('showNotification', handleNotification);
  }, [showNotification]);

  // Keyboard shortcut events
  useEffect(() => {
    const handleStart = () => handleStartBot();
    const handleStop = () => handleStopBot();
    const handleRefresh = () => runEnsureFresh();

    window.addEventListener('keyboard-start', handleStart);
    window.addEventListener('keyboard-stop', handleStop);
    window.addEventListener('keyboard-refresh', handleRefresh);

    return () => {
      window.removeEventListener('keyboard-start', handleStart);
      window.removeEventListener('keyboard-stop', handleStop);
      window.removeEventListener('keyboard-refresh', handleRefresh);
    };
  }, [handleStartBot, handleStopBot, runEnsureFresh]);
}
