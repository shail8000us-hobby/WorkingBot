import { useState, useEffect, useCallback } from 'react';
import { io } from 'socket.io-client';
import api from '../utils/apiShim';

/**
 * Custom hook for options SL/TP, Max Loss, and Take Profit settings.
 * Fetches settings on mount and provides update handlers for child components.
 *
 * @returns {Object} settings state, loaders, and update handlers
 */
export default function useOptionsSettings() {
  const [slTpSettings, setSlTpSettings] = useState({}); // Map of symbol -> settings
  const [maxLossSettings, setMaxLossSettings] = useState({}); // Map of symbol -> settings
  const [expiryMaxLossSettings, setExpiryMaxLossSettings] = useState({}); // Map of expiry_code -> settings
  const [tpSettings, setTpSettings] = useState({}); // Map of symbol -> TP settings

  // Load SL/TP settings for all positions
  const loadSLTPSettings = useCallback(async () => {
    try {
      const { data } = await api.get('/api/options/sl-tp/all');
      if (data?.success && data.settings) {
        const settingsMap = {};
        data.settings.forEach((s) => {
          settingsMap[s.symbol] = s;
        });
        setSlTpSettings(settingsMap);
      }
    } catch (err) {
      console.error('Failed to load SL/TP settings:', err);
    }
  }, []);

  // Load Max Loss settings for all positions (per-strike and per-expiry)
  const loadMaxLossSettings = useCallback(async () => {
    try {
      const { data: strikeData } = await api.get('/api/options/max-loss/strike/all');
      if (strikeData?.success && strikeData.settings) {
        const settingsMap = {};
        strikeData.settings.forEach((s) => {
          settingsMap[s.symbol] = s;
        });
        setMaxLossSettings(settingsMap);
      }

      const { data: expiryData } = await api.get('/api/options/max-loss/expiry/all');
      if (expiryData?.success && expiryData.settings) {
        const settingsMap = {};
        expiryData.settings.forEach((s) => {
          settingsMap[s.expiry_code] = s;
        });
        setExpiryMaxLossSettings(settingsMap);
      }
    } catch (err) {
      console.error('Failed to load max loss settings:', err);
    }
  }, []);

  // Load Take Profit settings for all positions
  const loadTakeProfitSettings = useCallback(async () => {
    try {
      const { data } = await api.get('/api/options/take-profit/strike/all');
      if (data?.success && data.settings) {
        const settingsMap = {};
        data.settings.forEach((s) => {
          settingsMap[s.symbol] = s;
        });
        setTpSettings(settingsMap);
      }
    } catch (err) {
      console.error('Failed to load take profit settings:', err);
    }
  }, []);

  // Handle max loss setting update from child component
  const handleMaxLossUpdate = useCallback((symbol, settings) => {
    setMaxLossSettings((prev) => {
      if (settings === null) {
        const next = { ...prev };
        delete next[symbol];
        return next;
      }
      return { ...prev, [symbol]: settings };
    });
  }, []);

  // Handle take profit setting update from child component
  const handleTakeProfitUpdate = useCallback((symbol, settings) => {
    setTpSettings((prev) => {
      if (settings === null) {
        const next = { ...prev };
        delete next[symbol];
        return next;
      }
      return { ...prev, [symbol]: settings };
    });
  }, []);

  // BUG-13 FIX: Initial load + polling every 30s so backend auto-triggered states
  // (SL hit, TP hit, max loss triggered) are reflected without requiring page reload.
  // MISSING-3 FIX: also subscribe to 'options_settings_updated' WebSocket event pushed
  // by take_profit_manager.py when an auto-trigger fires — gives immediate UI feedback.
  useEffect(() => {
    Promise.all([loadSLTPSettings(), loadMaxLossSettings(), loadTakeProfitSettings()]);

    const interval = setInterval(() => {
      Promise.all([loadSLTPSettings(), loadMaxLossSettings(), loadTakeProfitSettings()]);
    }, 30000);

    // WebSocket listener for immediate auto-trigger notifications
    const socket = io({
      path: '/socket.io',
      transports: ['polling'],
      upgrade: false,
      reconnection: true,
      reconnectionDelay: 2000,
      reconnectionAttempts: 5,
    });

    socket.on('options_settings_updated', (data) => {
      // Backend pushed a settings change (TP triggered, max loss triggered, etc.)
      // Re-fetch the relevant settings immediately instead of waiting 30s
      if (data?.event === 'take_profit_triggered' || data?.event === 'tp_settings_changed') {
        loadTakeProfitSettings();
      } else if (data?.event === 'max_loss_triggered' || data?.event === 'max_loss_changed') {
        loadMaxLossSettings();
      } else {
        // Generic: reload all settings
        Promise.all([loadSLTPSettings(), loadMaxLossSettings(), loadTakeProfitSettings()]);
      }
    });

    return () => {
      clearInterval(interval);
      socket.disconnect();
    };
  }, [loadSLTPSettings, loadMaxLossSettings, loadTakeProfitSettings]);

  return {
    slTpSettings,
    setSlTpSettings,
    maxLossSettings,
    expiryMaxLossSettings,
    setExpiryMaxLossSettings,
    tpSettings,
    loadSLTPSettings,
    loadMaxLossSettings,
    loadTakeProfitSettings,
    handleMaxLossUpdate,
    handleTakeProfitUpdate,
  };
}
