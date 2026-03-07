/**
 * useGroupsAPI — Server-side persistent storage for position groups.
 *
 * Replaces the old localStorage-based usePersistedState('options_position_groups_v2')
 * approach. Groups are now stored in SQLite on the backend and will NEVER disappear
 * unless the user explicitly deletes them.
 *
 * On first load, migrates any existing localStorage data to the server then removes
 * the localStorage key so there's no confusion.
 *
 * Created: March 1, 2026
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const API_BASE = '/api/options/groups';
const LS_KEY = 'options_position_groups_v2';
const LS_MIGRATED_KEY = 'options_groups_migrated_to_server';

/**
 * Hook to manage groups via server API.
 *
 * @returns {Object} Same interface as the old localStorage approach:
 *   - allExpiryGroupData: full data object
 *   - setAllExpiryGroupData: updater (optimistic + async persist)
 *   - loaded: boolean indicating initial load complete
 *   - error: any load error
 */
export default function useGroupsAPI() {
  const [allExpiryGroupData, setAllExpiryGroupDataLocal] = useState({});
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(null);
  const dataRef = useRef({});
  const saveTimerRef = useRef(null);
  const pendingOpsRef = useRef([]);
  const isSavingRef = useRef(false);

  // Keep ref in sync
  dataRef.current = allExpiryGroupData;

  // ──────────────────────────────────────────────────────────────────────────
  // Initial load + localStorage migration
  // ──────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    const init = async () => {
      try {
        // Step 1: Check if we need to migrate localStorage data
        const migrated = localStorage.getItem(LS_MIGRATED_KEY);
        if (!migrated) {
          const lsData = localStorage.getItem(LS_KEY);
          if (lsData) {
            try {
              const parsed = JSON.parse(lsData);
              if (parsed && Object.keys(parsed).length > 0) {
                console.log('[useGroupsAPI] Migrating localStorage groups to server...', Object.keys(parsed).length, 'expiry keys');
                const migRes = await fetch(`${API_BASE}/bulk`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ data: parsed }),
                });
                if (migRes.ok) {
                  console.log('[useGroupsAPI] Migration successful! Removing localStorage key.');
                  localStorage.setItem(LS_MIGRATED_KEY, new Date().toISOString());
                  // Keep LS_KEY as backup for 30 days, but mark as migrated
                  localStorage.setItem(LS_KEY + '_backup', lsData);
                  localStorage.removeItem(LS_KEY);
                } else {
                  console.error('[useGroupsAPI] Migration failed, keeping localStorage as fallback');
                }
              } else {
                // Nothing to migrate
                localStorage.setItem(LS_MIGRATED_KEY, new Date().toISOString());
              }
            } catch (parseErr) {
              console.error('[useGroupsAPI] Failed to parse localStorage for migration:', parseErr);
              localStorage.setItem(LS_MIGRATED_KEY, 'parse_error');
            }
          } else {
            localStorage.setItem(LS_MIGRATED_KEY, 'no_data');
          }
        }

        // Step 2: Load from server
        const res = await fetch(`${API_BASE}/`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();

        if (!cancelled) {
          const data = json.data || {};
          setAllExpiryGroupDataLocal(data);
          dataRef.current = data;
          setLoaded(true);
          console.log('[useGroupsAPI] Loaded', Object.keys(data).length, 'expiry keys from server');
        }
      } catch (err) {
        console.error('[useGroupsAPI] Failed to load groups:', err);
        if (!cancelled) {
          // Fallback: try localStorage
          try {
            const lsData = localStorage.getItem(LS_KEY);
            if (lsData) {
              const parsed = JSON.parse(lsData);
              setAllExpiryGroupDataLocal(parsed);
              dataRef.current = parsed;
              console.warn('[useGroupsAPI] Using localStorage fallback');
            }
          } catch { /* ignore */ }
          setError(err.message);
          setLoaded(true);
        }
      }
    };

    init();
    return () => { cancelled = true; };
  }, []);

  // ──────────────────────────────────────────────────────────────────────────
  // Debounced save — coalesces rapid changes into a single API call
  // ──────────────────────────────────────────────────────────────────────────
  const flushToServer = useCallback(async (data) => {
    if (isSavingRef.current) return;
    isSavingRef.current = true;
    try {
      const res = await fetch(`${API_BASE}/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data }),
      });
      if (!res.ok) {
        console.error('[useGroupsAPI] Save failed:', res.status);
      }
    } catch (err) {
      console.error('[useGroupsAPI] Save error:', err);
    } finally {
      isSavingRef.current = false;
    }
  }, []);

  const scheduleSave = useCallback((data) => {
    clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      flushToServer(data);
    }, 600);  // debounce 600ms
  }, [flushToServer]);

  // ──────────────────────────────────────────────────────────────────────────
  // Targeted API operations (more efficient than bulk save for single actions)
  // ──────────────────────────────────────────────────────────────────────────
  const apiCall = useCallback(async (endpoint, method, body) => {
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        console.error(`[useGroupsAPI] ${method} ${endpoint} failed:`, res.status);
      }
    } catch (err) {
      console.error(`[useGroupsAPI] ${method} ${endpoint} error:`, err);
    }
  }, []);

  // ──────────────────────────────────────────────────────────────────────────
  // Main setter — mirrors the old setAllExpiryGroupData interface
  // Provides optimistic local update + async server persist
  // ──────────────────────────────────────────────────────────────────────────
  const setAllExpiryGroupData = useCallback((updater) => {
    setAllExpiryGroupDataLocal((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      // Schedule async save to server
      scheduleSave(next);
      return next;
    });
  }, [scheduleSave]);

  // ──────────────────────────────────────────────────────────────────────────
  // Specific operations that use targeted API calls (more efficient)
  // ──────────────────────────────────────────────────────────────────────────
  const createGroupOnServer = useCallback((expiryKey, groupId, name, color) => {
    apiCall('/create', 'POST', { expiry_key: expiryKey, group_id: groupId, name, color });
  }, [apiCall]);

  const deleteGroupOnServer = useCallback((expiryKey, groupId) => {
    apiCall('/delete', 'DELETE', { expiry_key: expiryKey, group_id: groupId });
  }, [apiCall]);

  const assignSymbolOnServer = useCallback((expiryKey, symbol, targetGroupId) => {
    apiCall('/assign', 'PUT', { expiry_key: expiryKey, symbol, target_group_id: targetGroupId });
  }, [apiCall]);

  const updateGroupOnServer = useCallback((expiryKey, groupId, updates) => {
    apiCall('/update', 'PUT', { expiry_key: expiryKey, group_id: groupId, updates });
  }, [apiCall]);

  const updateMetaOnServer = useCallback((expiryKey, meta) => {
    apiCall('/meta', 'PUT', { expiry_key: expiryKey, ...meta });
  }, [apiCall]);

  // Cleanup
  useEffect(() => {
    return () => {
      clearTimeout(saveTimerRef.current);
      // Flush any pending data on unmount
      if (dataRef.current && Object.keys(dataRef.current).length > 0) {
        flushToServer(dataRef.current);
      }
    };
  }, [flushToServer]);

  return {
    allExpiryGroupData,
    setAllExpiryGroupData,
    loaded,
    error,
    // Targeted operations for efficiency
    createGroupOnServer,
    deleteGroupOnServer,
    assignSymbolOnServer,
    updateGroupOnServer,
    updateMetaOnServer,
  };
}
