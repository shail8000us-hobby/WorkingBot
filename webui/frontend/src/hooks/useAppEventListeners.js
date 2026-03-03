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

import { useEffect } from 'react';

export function useAppEventListeners({
  ensureFresh,
  handleStartBot,
  handleStopBot,
  showNotification,
}) {
  // Tab visibility → refresh data on re-focus
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) setTimeout(ensureFresh, 350);
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [ensureFresh]);

  // Network recovery → refresh data
  useEffect(() => {
    const handleOnline = () => setTimeout(ensureFresh, 500);
    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
  }, [ensureFresh]);

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
    const handleRefresh = () => ensureFresh();

    window.addEventListener('keyboard-start', handleStart);
    window.addEventListener('keyboard-stop', handleStop);
    window.addEventListener('keyboard-refresh', handleRefresh);

    return () => {
      window.removeEventListener('keyboard-start', handleStart);
      window.removeEventListener('keyboard-stop', handleStop);
      window.removeEventListener('keyboard-refresh', handleRefresh);
    };
  }, [handleStartBot, handleStopBot, ensureFresh]);
}
