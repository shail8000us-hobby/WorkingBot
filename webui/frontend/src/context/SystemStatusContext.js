import React, { createContext, useContext, useMemo, useState } from 'react';

/**
 * Global system status context
 * Tracks bot runtime state, guardian health, warnings and sync timestamps.
 * Panels can consume this to show state-aware placeholders without re-fetching backend routes.
 */

const defaultState = {
  botRunning: false,
  guardianHealthy: true,
  warnings: [],
  lastSync: null,
  telegramStatus: null,
  setSystemStatus: () => {},
  registerWarning: () => {},
  clearWarning: () => {}
};

const SystemStatusContext = createContext(defaultState);

export const SystemStatusProvider = ({ children }) => {
  const [systemStatus, setSystemStatus] = useState({
    botRunning: false,
    guardianHealthy: true,
    warnings: [],
    lastSync: null,
    telegramStatus: null
  });

  /**
   * Merge helper used by App and feature panels to update shared state.
   * Accepts partial state e.g. { botRunning: true }.
   */
  const mergeStatus = (updates) => {
    setSystemStatus((prev) => ({
      ...prev,
      ...updates
    }));
  };

  /**
   * Adds or updates a warning. Uses string ids so consumers can remove them.
   */
  const registerWarning = (warning) => {
    if (!warning?.id) {
      return;
    }
    setSystemStatus((prev) => {
      const existing = prev.warnings.filter((w) => w.id !== warning.id);
      return {
        ...prev,
        warnings: [...existing, warning]
      };
    });
  };

  /**
   * Removes a warning with the given id.
   */
  const clearWarning = (id) => {
    setSystemStatus((prev) => ({
      ...prev,
      warnings: prev.warnings.filter((warning) => warning.id !== id)
    }));
  };

  const value = useMemo(
    () => ({
      ...systemStatus,
      setSystemStatus: mergeStatus,
      registerWarning,
      clearWarning
    }),
    [systemStatus]
  );

  return (
    <SystemStatusContext.Provider value={value}>
      {children}
    </SystemStatusContext.Provider>
  );
};

export const useSystemStatus = () => useContext(SystemStatusContext);

export default SystemStatusContext;
