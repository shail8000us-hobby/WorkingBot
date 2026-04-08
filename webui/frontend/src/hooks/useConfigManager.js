/**
 * Config Manager Hook (v5.0 Multi-Symbol Support)
 *
 * Manages configuration state and operations:
 * - Fetch initial config data (symbol-aware)
 * - Update configuration
 * - Handle config state
 */

import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import robustApiClient from '../utils/robustApiClient';
import apiClient from '../utils/apiClient';
import { transformFlatConfig } from '../utils/configHelpers.ts';
import { perfMonitor } from '../utils/performanceMonitor';
import { debounce } from '../utils/configHelpers.ts';
import { useSymbolSafe } from '../context/SymbolContext';

export function useConfigManager({
  setBackendDown,
  setBotStatus,
  setTradingSnapshot,
  setLogs,
  setFeatureFlags,
  setLastUpdated,
  setSystemStatus,
  setLoading,
  setBusy,
  showNotification,
  globalWarnings,
  registerWarning,
  clearWarning,
}) {
  const [config, setConfig] = useState({});
  const [configMeta, setConfigMeta] = useState({});
  const { fetchWithSymbol } = useSymbolSafe();

  // Use refs for callbacks and values that change often but shouldn't re-create fetchInitialData
  const globalWarningsRef = useRef(globalWarnings);
  const registerWarningRef = useRef(registerWarning);
  const clearWarningRef = useRef(clearWarning);
  const showNotificationRef = useRef(showNotification);

  useEffect(() => {
    globalWarningsRef.current = globalWarnings;
    registerWarningRef.current = registerWarning;
    clearWarningRef.current = clearWarning;
    showNotificationRef.current = showNotification;
  }, [globalWarnings, registerWarning, clearWarning, showNotification]);

  const fetchInitialData = useCallback(async () => {
    const timerId = 'fetch-initial-data';
    perfMonitor.startTimer(timerId);
    let timerEnded = false;

    const endTimerOnce = () => {
      if (!timerEnded && perfMonitor.hasTimer(timerId)) {
        perfMonitor.endTimer(timerId);
        timerEnded = true;
      }
    };

    try {
      setLoading(true);

      const flagsPromise = robustApiClient.get('/api/flags').catch(() => ({}));

      // Batch 1: Critical data (v5.0: symbol-aware) - with timeout
      const criticalDataPromise = Promise.all([
        fetchWithSymbol('/api/config/flat').then((r) => r.json()),
        fetchWithSymbol('/api/bot/status').then((r) => r.json()),
      ]);

      // Add timeout to prevent hanging
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Request timeout')), 8000)
      );

      const [configData, botData] = await Promise.race([criticalDataPromise, timeoutPromise]);

      // Backend is responsive, clear backend down state
      setBackendDown(false);

      // Fetch all secondary data in parallel (no batching delay)
      const [tradingData, logsData, flagsData] = await Promise.all([
        robustApiClient.get('/api/trading_status').catch(() => ({})),
        robustApiClient.get('/api/logs', { params: { limit: 50 } }), // Reduced from 120 to 50 for faster load
        flagsPromise,
      ]);

      const { structured, meta } = transformFlatConfig(configData);
      setConfig(structured);
      setConfigMeta(meta);
      setTradingSnapshot(tradingData);
      setBotStatus(botData);

      // Update global status context with trading snapshot (blockers, warnings, last sync)
      if (Array.isArray(tradingData?.blockers)) {
        globalWarningsRef.current
          .filter((warning) => warning.id.startsWith('blocker-'))
          .forEach((warning) => clearWarningRef.current(warning.id));

        tradingData.blockers
          .filter((blocker) => blocker?.active)
          .forEach((blocker) => {
            registerWarningRef.current({
              id: `blocker-${blocker.id}`,
              type: 'bot',
              title: blocker.name || 'Trading blocked',
              message: blocker.message || 'Trading has been halted pending operator review.',
            });
          });
      }

      setSystemStatus({ lastSync: new Date().toISOString() });

      const logEntries = logsData?.logs || logsData?.data?.logs || logsData?.data || logsData || [];
      setLogs(Array.isArray(logEntries) ? logEntries.slice(-200) : []);

      setFeatureFlags((prev) => ({ ...prev, ...(flagsData || {}) }));
      setLastUpdated(new Date().toISOString());

      endTimerOnce();
    } catch (error) {
      endTimerOnce();
      console.error('Error fetching initial data:', error);

      // Check if this is a network/connection error (backend is down)
      if (
        error.message?.includes('Network Error') ||
        error.message?.includes('ERR_CONNECTION_REFUSED') ||
        error.message?.includes('timeout') ||
        error.code === 'ECONNREFUSED' ||
        error.response === undefined
      ) {
        setBackendDown(true);
        console.error('Backend server is not responding at localhost:5555');
      } else {
        showNotificationRef.current(`Error loading data: ${error.message}`, 'error');
      }
    } finally {
      setLoading(false);
    }
  }, [
    fetchWithSymbol,
    setBackendDown,
    setBotStatus,
    setTradingSnapshot,
    setLogs,
    setFeatureFlags,
    setLastUpdated,
    setSystemStatus,
    setLoading,
  ]);

  const debouncedFetchInitialData = useMemo(
    () => debounce(fetchInitialData, 1000),
    [fetchInitialData]
  );

  const handleConfigUpdate = useCallback(
    async (updates, confirmed = false) => {
      try {
        setBusy(true);

        // Add confirmed flag to request if this is a confirmed retry
        const payload = confirmed ? { ...updates, confirmed: true } : updates;
        const result = await apiClient.updateConfig(payload);

        // Check if backend requires confirmation
        if (result.require_confirmation) {
          setBusy(false);
          // Return the confirmation requirement to the caller
          return {
            requiresConfirmation: true,
            changesSummary: result.changes_summary,
            updates: updates, // Pass back the original updates for retry
          };
        }

        showNotification(result.message || 'Configuration saved successfully', 'success');

        // After saving, check if bot is waiting for runtime confirmation
        try {
          const logCheck = await robustApiClient.get('/api/utility/check-log');
          if (logCheck.startup_hold && logCheck.confirm_file_hint) {
            // Bot is waiting for runtime confirmation - create the file automatically
            const confirmResult = await robustApiClient.post('/api/config/confirm-runtime', {
              confirm_file: logCheck.confirm_file_hint,
            });

            if (confirmResult.success) {
              showNotification(
                'Configuration confirmed. Bot will proceed with changes.',
                'success'
              );
            }
          }
        } catch (confirmError) {
          // Non-critical error - config was saved, but runtime confirmation may need manual action
          console.warn('Runtime confirmation check failed:', confirmError);
        }

        await fetchInitialData();
        return { success: true };
      } catch (error) {
        showNotification(`Failed to save configuration: ${error.message}`, 'error');
        return { success: false, error: error.message };
      } finally {
        setBusy(false);
      }
    },
    [fetchInitialData, showNotification, setBusy]
  );

  return {
    config,
    configMeta,
    setConfig,
    setConfigMeta,
    fetchInitialData,
    debouncedFetchInitialData,
    handleConfigUpdate,
  };
}
