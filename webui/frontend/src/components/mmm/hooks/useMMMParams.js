/**
 * useMMMParams — Hot-reload parameter management hook
 *
 * Manages the 19 MMM algorithm parameters with:
 *  - Read current session params
 *  - Edit with local state (optimistic)
 *  - Save with validation (backend rejects invalid)
 *  - Hot-reload updates (14 of 19 params are hot-reloadable while running)
 *  - Revert unsaved changes
 *  - Tracks which params are "dirty" (changed but unsaved)
 *
 * Sections from MONEY_POWER_CALCULATION_LOGIC.md:
 *   §19 Parameters (full list + hot-reload rules)
 *
 * Created: February 15, 2026
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import mmmService from '../mmmService';

/**
 * @param {string} sessionId - Current session ID
 * @param {Object} paramsInfo - Parameter metadata from /api/mmm/params/info
 */
const useMMMParams = (sessionId, paramsInfo = null) => {
  const [serverParams, setServerParams] = useState(null);
  const [localParams, setLocalParams] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [lastSaved, setLastSaved] = useState(null);
  const mounted = useRef(true);

  useEffect(() => () => { mounted.current = false; }, []);

  // ----- Load params from backend -----
  const fetchParams = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);

    try {
      const result = await mmmService.getSessionParams(sessionId);
      if (result.success && mounted.current) {
        setServerParams(result.params);
        setLocalParams(result.params);
      } else if (mounted.current) {
        setError(result.error || 'Failed to load params');
      }
    } catch (err) {
      if (mounted.current) {
        setError(err.details?.error || err.message);
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [sessionId]);

  // Auto-fetch on session change
  useEffect(() => {
    fetchParams();
  }, [fetchParams]);

  // ----- Dirty tracking -----
  const dirtyKeys = useMemo(() => {
    if (!serverParams || !localParams) return [];
    return Object.keys(localParams).filter(
      (key) => localParams[key] !== serverParams[key]
    );
  }, [serverParams, localParams]);

  const isDirty = dirtyKeys.length > 0;

  // ----- Update a single param locally -----
  const setParam = useCallback((key, value) => {
    setLocalParams((prev) => (prev ? { ...prev, [key]: value } : prev));
  }, []);

  // ----- Batch update params locally -----
  const setParams = useCallback((updates) => {
    setLocalParams((prev) => (prev ? { ...prev, ...updates } : prev));
  }, []);

  // ----- Save dirty params to backend -----
  const save = useCallback(async () => {
    if (!sessionId || !isDirty) return { success: true, message: 'No changes' };
    setSaving(true);
    setError(null);

    // Only send changed params
    const changedParams = {};
    for (const key of dirtyKeys) {
      changedParams[key] = localParams[key];
    }

    try {
      const result = await mmmService.updateSessionParams(sessionId, changedParams);
      if (result.success && mounted.current) {
        // Merge backend response into our state
        const updatedParams = { ...serverParams, ...changedParams };
        setServerParams(updatedParams);
        setLocalParams(updatedParams);
        setLastSaved(new Date().toISOString());
        return result;
      } else if (mounted.current) {
        setError(result.error || 'Failed to save params');
        return result;
      }
    } catch (err) {
      if (mounted.current) {
        const errMsg = err.details?.error || err.message;
        setError(errMsg);
        return { success: false, error: errMsg };
      }
    } finally {
      if (mounted.current) setSaving(false);
    }

    return { success: false };
  }, [sessionId, isDirty, dirtyKeys, localParams, serverParams]);

  // ----- Revert all unsaved changes -----
  const revert = useCallback(() => {
    if (serverParams) {
      setLocalParams({ ...serverParams });
    }
    setError(null);
  }, [serverParams]);

  // ----- Reset to defaults -----
  const resetToDefaults = useCallback(async () => {
    if (!paramsInfo?.defaults) return;
    setLocalParams(paramsInfo.defaults);
  }, [paramsInfo]);

  // ----- Apply WebSocket update (from params_changed event) -----
  const applyRemoteUpdate = useCallback((changedParams) => {
    setServerParams((prev) => (prev ? { ...prev, ...changedParams } : prev));
    // Only update local if the key isn't dirty
    setLocalParams((prev) => {
      if (!prev) return prev;
      const updated = { ...prev };
      for (const [key, value] of Object.entries(changedParams)) {
        // Only overwrite if user hasn't made local changes to this key
        if (prev[key] === serverParams?.[key]) {
          updated[key] = value;
        }
      }
      return updated;
    });
  }, [serverParams]);

  return {
    // Data
    params: localParams,
    serverParams,
    paramsInfo,
    dirtyKeys,
    isDirty,

    // Actions
    setParam,
    setParams,
    save,
    revert,
    resetToDefaults,
    fetchParams,
    applyRemoteUpdate,

    // Status
    loading,
    saving,
    error,
    lastSaved,
    clearError: () => setError(null),
  };
};

export default useMMMParams;
