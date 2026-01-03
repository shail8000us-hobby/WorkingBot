/**
 * Config Manager Hook (v5.0 Multi-Symbol Support)
 * 
 * Manages configuration state and operations:
 * - Fetch initial config data (symbol-aware)
 * - Update configuration
 * - Handle config state
 */

import { useState, useCallback, useMemo } from 'react';
import robustApiClient from '../utils/robustApiClient';
import apiClient from '../utils/apiClient';
import { transformFlatConfig } from '../utils/configHelpers';
import { perfMonitor } from '../utils/performanceMonitor';
import { debounce } from '../utils/configHelpers';
import { useSymbolSafe } from '../context/SymbolContext';

export function useConfigManager({
  setBackendDown,
  setBotStatus,
  setTradingSnapshot,
  setPositionsData,
  setLogs,
  setFeatureFlags,
  setLastUpdated,
  setSystemStatus,
  setLoading,
  setBusy,
  showNotification,
  globalWarnings,
  registerWarning,
  clearWarning
}) {
  const [config, setConfig] = useState({});
  const [configMeta, setConfigMeta] = useState({});
  const { selectedSymbol, fetchWithSymbol } = useSymbolSafe();

  const fetchInitialData = useCallback(async () => {
    try {
      perfMonitor.startTimer('fetch-initial-data');
      setLoading(true);

      const flagsPromise = robustApiClient.get('/api/flags').catch(() => ({}));

      // Batch 1: Critical data (v5.0: symbol-aware)
      const [configData, botData] = await Promise.all([
        fetchWithSymbol('/api/config/flat').then(r => r.json()),
        fetchWithSymbol('/api/bot/status').then(r => r.json()),
      ]);

      // Backend is responsive, clear backend down state
      setBackendDown(false);

      // Small delay between batches to prevent resource exhaustion
      await new Promise(resolve => setTimeout(resolve, 100));

      // Batch 2: Secondary data (v5.0: symbol-aware where applicable)
      const [tradingData, logsData, positionsResponse, flagsData] = await Promise.all([
        robustApiClient.get('/api/trading_status'),
        robustApiClient.get('/api/logs', { params: { limit: 120 } }),
        fetchWithSymbol('/api/positions').then(r => r.json()).catch(() => null),
        flagsPromise
      ]);

      const { structured, meta } = transformFlatConfig(configData);
      setConfig(structured);
      setConfigMeta(meta);
      setTradingSnapshot(tradingData);
      setBotStatus(botData);
      if (positionsResponse) {
        setPositionsData(positionsResponse);
      }

      // Update global status context with trading snapshot (blockers, warnings, last sync)
      if (Array.isArray(tradingData?.blockers)) {
        globalWarnings
          .filter((warning) => warning.id.startsWith('blocker-'))
          .forEach((warning) => clearWarning(warning.id));

        tradingData.blockers
          .filter((blocker) => blocker?.active)
          .forEach((blocker) => {
            registerWarning({
              id: `blocker-${blocker.id}`,
              type: 'bot',
              title: blocker.name || 'Trading blocked',
              message: blocker.message || 'Trading has been halted pending operator review.'
            });
          });
      }

      setSystemStatus({ lastSync: new Date().toISOString() });

      const logEntries = logsData?.logs || logsData?.data?.logs || logsData?.data || logsData || [];
      setLogs(Array.isArray(logEntries) ? logEntries.slice(-200) : []);

      setFeatureFlags((prev) => ({ ...prev, ...(flagsData || {}) }));
      setLastUpdated(new Date().toISOString());

      perfMonitor.endTimer('fetch-initial-data');
    } catch (error) {
      perfMonitor.endTimer('fetch-initial-data');
      console.error('Error fetching initial data:', error);
      
      // Check if this is a network/connection error (backend is down)
      if (error.message?.includes('Network Error') || 
          error.message?.includes('ERR_CONNECTION_REFUSED') ||
          error.code === 'ECONNREFUSED' ||
          error.response === undefined) {
        setBackendDown(true);
        console.error('Backend server is not responding at localhost:5555');
      } else {
        showNotification(`Error loading data: ${error.message}`, 'error');
      }
    } finally {
      setLoading(false);
    }
  }, [
    selectedSymbol,
    fetchWithSymbol,
    setBackendDown,
    setBotStatus,
    setTradingSnapshot,
    setPositionsData,
    setLogs,
    setFeatureFlags,
    setLastUpdated,
    setSystemStatus,
    setLoading,
    showNotification,
    globalWarnings,
    registerWarning,
    clearWarning
  ]);

  const debouncedFetchInitialData = useMemo(
    () => debounce(fetchInitialData, 1000),
    [fetchInitialData]
  );

  const handleConfigUpdate = useCallback(async (updates, confirmed = false) => {
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
          updates: updates  // Pass back the original updates for retry
        };
      }
      
      showNotification(result.message || 'Configuration saved successfully', 'success');
      
      // After saving, check if bot is waiting for runtime confirmation
      try {
        const logCheck = await robustApiClient.get('/api/utility/check-log');
        if (logCheck.startup_hold && logCheck.confirm_file_hint) {
          // Bot is waiting for runtime confirmation - create the file automatically
          const confirmResult = await robustApiClient.post('/api/config/confirm-runtime', {
            confirm_file: logCheck.confirm_file_hint
          });
          
          if (confirmResult.success) {
            showNotification('Configuration confirmed. Bot will proceed with changes.', 'success');
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
  }, [fetchInitialData, showNotification, setBusy]);

  return {
    config,
    configMeta,
    setConfig,
    setConfigMeta,
    fetchInitialData,
    debouncedFetchInitialData,
    handleConfigUpdate
  };
}
