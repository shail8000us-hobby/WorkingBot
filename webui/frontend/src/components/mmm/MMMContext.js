/**
 * MMM Context — Money Mind & Method
 *
 * Centralized state management for MMM sessions with:
 * - WebSocket real-time updates (heartbeat, adjustments, reversals, etc.)
 * - Network disconnection recovery with exponential backoff
 * - Multi-session state management
 *
 * Created: February 15, 2026
 */

import React, {
  createContext,
  useContext,
  useReducer,
  useEffect,
  useRef,
  useCallback,
} from 'react';
import mmmService from './mmmService';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';

// =============================================================================
// Initial State
// =============================================================================

const initialState = {
  sessions: [],
  selectedSessionId: localStorage.getItem('mmm_selectedSessionId') || null,
  loading: true,
  error: null,
  healthStatus: null,
  connectionStatus: 'connected', // connected | disconnected | reconnecting
  lastUpdate: null,
  paramsInfo: null, // Parameter metadata from backend
  bothSidesAlert: null, // Active both-sides-up alert data
};

// =============================================================================
// Actions
// =============================================================================

const ACTIONS = {
  SET_SESSIONS: 'SET_SESSIONS',
  ADD_SESSION: 'ADD_SESSION',
  UPDATE_SESSION: 'UPDATE_SESSION',
  REMOVE_SESSION: 'REMOVE_SESSION',
  SET_SELECTED_SESSION: 'SET_SELECTED_SESSION',
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  SET_HEALTH_STATUS: 'SET_HEALTH_STATUS',
  SET_CONNECTION_STATUS: 'SET_CONNECTION_STATUS',
  SET_LAST_UPDATE: 'SET_LAST_UPDATE',
  SET_PARAMS_INFO: 'SET_PARAMS_INFO',
  SET_BOTH_SIDES_ALERT: 'SET_BOTH_SIDES_ALERT',
  CLEAR_BOTH_SIDES_ALERT: 'CLEAR_BOTH_SIDES_ALERT',
  RESET_STATE: 'RESET_STATE',
};

// =============================================================================
// Reducer
// =============================================================================

function mmmReducer(state, action) {
  switch (action.type) {
    case ACTIONS.SET_SESSIONS:
      return { ...state, sessions: action.payload, loading: false };

    case ACTIONS.ADD_SESSION:
      return {
        ...state,
        sessions: [action.payload, ...state.sessions],
      };

    case ACTIONS.UPDATE_SESSION:
      return {
        ...state,
        sessions: state.sessions.map((s) =>
          s.session_id === action.payload.session_id
            ? { ...s, ...action.payload }
            : s
        ),
      };

    case ACTIONS.REMOVE_SESSION:
      return {
        ...state,
        sessions: state.sessions.filter(
          (s) => s.session_id !== action.payload
        ),
        selectedSessionId:
          state.selectedSessionId === action.payload
            ? null
            : state.selectedSessionId,
      };

    case ACTIONS.SET_SELECTED_SESSION:
      return { ...state, selectedSessionId: action.payload };

    case ACTIONS.SET_LOADING:
      if (state.loading === action.payload) return state;
      return { ...state, loading: action.payload };

    case ACTIONS.SET_ERROR:
      if (state.error === action.payload) return state;
      return { ...state, error: action.payload };

    case ACTIONS.SET_HEALTH_STATUS:
      return { ...state, healthStatus: action.payload };

    case ACTIONS.SET_CONNECTION_STATUS:
      if (state.connectionStatus === action.payload) return state;
      return { ...state, connectionStatus: action.payload };

    case ACTIONS.SET_LAST_UPDATE:
      return { ...state, lastUpdate: action.payload };

    case ACTIONS.SET_PARAMS_INFO:
      return { ...state, paramsInfo: action.payload };

    case ACTIONS.SET_BOTH_SIDES_ALERT:
      return { ...state, bothSidesAlert: action.payload };

    case ACTIONS.CLEAR_BOTH_SIDES_ALERT:
      return { ...state, bothSidesAlert: null };

    case ACTIONS.RESET_STATE:
      return { ...initialState };

    default:
      return state;
  }
}

// =============================================================================
// Context
// =============================================================================

const MMMContext = createContext(null);

/**
 * MMM Provider Component
 *
 * Wraps children with state management, WebSocket listeners,
 * and network recovery.
 */
export function MMMProvider({ children, socket }) {
  const [state, dispatch] = useReducer(mmmReducer, initialState);
  const retryTimeoutRef = useRef(null);
  const retryCountRef = useRef(0);
  const lastSessionsJson = useRef('');
  const maxRetries = 5;
  const baseRetryDelay = 2000;

  // ---------------------------------------------------------------------------
  // Fetch sessions with retry logic
  // ---------------------------------------------------------------------------
  const fetchSessions = useCallback(async (showLoading = true) => {
    if (showLoading) {
      dispatch({ type: ACTIONS.SET_LOADING, payload: true });
    }

    try {
      const result = await mmmService.getSessions(false, true);
      if (result.success) {
        const sessions = result.sessions || [];

        // Fix: Deep comparison to prevent redundant re-renders
        const currentJson = JSON.stringify(sessions);
        if (currentJson !== lastSessionsJson.current) {
          lastSessionsJson.current = currentJson;
          dispatch({ type: ACTIONS.SET_SESSIONS, payload: sessions });
          dispatch({ type: ACTIONS.SET_LAST_UPDATE, payload: new Date().toISOString() });
        }

        dispatch({ type: ACTIONS.SET_ERROR, payload: null });
        dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'connected' });
        retryCountRef.current = 0;

        // Clear stale localStorage session ID if it no longer exists
        const savedId = localStorage.getItem('mmm_selectedSessionId');
        if (savedId && sessions.length > 0 && !sessions.find(s => s.session_id === savedId)) {
          console.log(`MMM: Clearing stale session ID ${savedId} from localStorage`);
          localStorage.removeItem('mmm_selectedSessionId');
          dispatch({ type: ACTIONS.SET_SELECTED_SESSION, payload: null });
        } else if (savedId && sessions.length === 0) {
          console.log('MMM: No sessions — clearing stale localStorage');
          localStorage.removeItem('mmm_selectedSessionId');
          dispatch({ type: ACTIONS.SET_SELECTED_SESSION, payload: null });
        }
      } else {
        dispatch({ type: ACTIONS.SET_ERROR, payload: result.error });
      }
    } catch (err) {
      console.error('MMM: Failed to fetch sessions:', err);
      dispatch({ type: ACTIONS.SET_ERROR, payload: err.message });
      handleNetworkError();
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: false });
    }
  }, []);

  // Network error with exponential backoff
  const handleNetworkError = useCallback(() => {
    dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'disconnected' });

    if (retryCountRef.current < maxRetries) {
      const delay = baseRetryDelay * Math.pow(2, retryCountRef.current);
      console.log(
        `MMM: Network error, retrying in ${delay}ms (attempt ${retryCountRef.current + 1}/${maxRetries})`
      );
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'reconnecting' });

      retryTimeoutRef.current = setTimeout(() => {
        retryCountRef.current++;
        fetchSessions(false);
      }, delay);
    } else {
      console.error('MMM: Max retries reached');
      dispatch({
        type: ACTIONS.SET_ERROR,
        payload: 'Connection lost. Please check your network and refresh.',
      });
    }
  }, [fetchSessions]);

  // Health check
  const checkHealth = useCallback(async () => {
    try {
      const result = await mmmService.healthCheck();
      dispatch({
        type: ACTIONS.SET_HEALTH_STATUS,
        payload: result.success ? 'healthy' : 'error',
      });
    } catch {
      dispatch({ type: ACTIONS.SET_HEALTH_STATUS, payload: 'error' });
    }
  }, []);

  // Fetch parameter metadata
  const fetchParamsInfo = useCallback(async () => {
    try {
      const result = await mmmService.getParamsInfo();
      if (result.success) {
        dispatch({ type: ACTIONS.SET_PARAMS_INFO, payload: result });
      }
    } catch (err) {
      console.error('MMM: Failed to fetch params info:', err);
    }
  }, []);

  // ---------------------------------------------------------------------------
  // WebSocket handlers
  // ---------------------------------------------------------------------------

  const handleHeartbeat = useCallback((data) => {
    if (!data?.session_id) return;
    dispatch({ type: ACTIONS.UPDATE_SESSION, payload: data });
    dispatch({ type: ACTIONS.SET_LAST_UPDATE, payload: new Date().toISOString() });
  }, []);

  const handleAdjustment = useCallback((data) => {
    if (!data?.session_id) return;
    console.log(`💰 MMM: Adjustment on ${data.side} — ${data.lots} lots @ ${data.premium}`);
    // Trigger a full refresh to get updated state
    fetchSessions(false);
  }, [fetchSessions]);

  const handleStatusChange = useCallback((data) => {
    if (!data?.session_id) return;
    console.log(`🔄 MMM: Status ${data.old_status} → ${data.new_status} (${data.reason})`);
    dispatch({
      type: ACTIONS.UPDATE_SESSION,
      payload: {
        session_id: data.session_id,
        status: data.new_status,
      },
    });
  }, []);

  const handleBothSidesAlert = useCallback((data) => {
    if (!data?.session_id) return;
    console.warn('⚠️ MMM: Both sides up!', data);
    dispatch({ type: ACTIONS.SET_BOTH_SIDES_ALERT, payload: data });
  }, []);

  const handleSafety = useCallback((data) => {
    if (!data?.session_id) return;
    console.warn(`🛡️ MMM Safety [${data.level}]: ${data.message}`);
  }, []);

  const handleParamsChanged = useCallback((data) => {
    if (!data?.session_id) return;
    console.log('⚙️ MMM: Params updated:', data.changed_params);
    fetchSessions(false);
  }, [fetchSessions]);

  const handleSessionCreated = useCallback((data) => {
    if (!data?.session_id) return;
    console.log('🆕 MMM: Session created:', data.session_id);
    fetchSessions(false);
  }, [fetchSessions]);

  const handleSessionDeleted = useCallback((data) => {
    if (!data?.session_id) return;
    console.log('🗑️ MMM: Session deleted:', data.session_id);
    fetchSessions(false);
  }, [fetchSessions]);

  const handlePnlUpdate = useCallback((data) => {
    if (!data?.session_id) return;
    dispatch({
      type: ACTIONS.UPDATE_SESSION,
      payload: {
        session_id: data.session_id,
        total_pnl: data.total_pnl,
        realized_pnl: data.realized,
        unrealized_pnl: data.unrealized,
      },
    });
  }, []);

  // ---------------------------------------------------------------------------
  // Setup WebSocket listeners
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!socket) return;

    socket.on('mmm_heartbeat', handleHeartbeat);
    socket.on('mmm_adjustment', handleAdjustment);
    socket.on('mmm_status_change', handleStatusChange);
    socket.on('mmm_both_sides', handleBothSidesAlert);
    socket.on('mmm_safety', handleSafety);
    socket.on('mmm_params_changed', handleParamsChanged);
    socket.on('mmm_session_created', handleSessionCreated);
    socket.on('mmm_session_deleted', handleSessionDeleted);
    socket.on('mmm_pnl_update', handlePnlUpdate);
    socket.on('mmm_reversal', (data) => {
      console.log('🔄 MMM: Reversal detected', data);
      fetchSessions(false);
    });
    socket.on('mmm_shift', (data) => {
      console.log('📊 MMM: Strike shifted', data);
      fetchSessions(false);
    });
    socket.on('mmm_close_at_5', (data) => {
      console.log('🏁 MMM: Close-at-5 triggered', data);
      fetchSessions(false);
    });
    socket.on('mmm_harvest', (data) => {
      console.log('🌾 MMM: Position harvested', data);
      fetchSessions(false);
    });
    socket.on('mmm_recycle', (data) => {
      console.log('♻️ MMM: Lot recycling executed', data);
      fetchSessions(false);
    });

    console.log('📡 MMM: WebSocket listeners attached');

    return () => {
      socket.off('mmm_heartbeat', handleHeartbeat);
      socket.off('mmm_adjustment', handleAdjustment);
      socket.off('mmm_status_change', handleStatusChange);
      socket.off('mmm_both_sides', handleBothSidesAlert);
      socket.off('mmm_safety', handleSafety);
      socket.off('mmm_params_changed', handleParamsChanged);
      socket.off('mmm_session_created', handleSessionCreated);
      socket.off('mmm_session_deleted', handleSessionDeleted);
      socket.off('mmm_pnl_update', handlePnlUpdate);
      socket.off('mmm_reversal');
      socket.off('mmm_shift');
      socket.off('mmm_close_at_5');
      socket.off('mmm_harvest');
      socket.off('mmm_recycle');
      console.log('📡 MMM: WebSocket listeners detached');
    };
  }, [
    socket,
    handleHeartbeat,
    handleAdjustment,
    handleStatusChange,
    handleBothSidesAlert,
    handleSafety,
    handleParamsChanged,
    handleSessionCreated,
    handleSessionDeleted,
    handlePnlUpdate,
    fetchSessions,
  ]);

  // Online/offline recovery
  useEffect(() => {
    const handleOnline = () => {
      console.log('🌐 MMM: Network back online, refreshing...');
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'reconnecting' });
      retryCountRef.current = 0;
      fetchSessions(false);
    };

    const handleOffline = () => {
      console.log('📴 MMM: Network offline');
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'disconnected' });
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [fetchSessions]);

  // Initial load (one-time calls)
  useEffect(() => {
    checkHealth();
    fetchParamsInfo();
    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, [checkHealth, fetchParamsInfo]);

  // Session polling — pauses when tab is hidden, slows down on return
  const fetchSessionsSilent = useCallback(() => fetchSessions(false), [fetchSessions]);
  useVisibilityAwarePolling(fetchSessionsSilent, 30000, 120000);

  // ---------------------------------------------------------------------------
  // Exposed actions
  // ---------------------------------------------------------------------------
  const selectSession = useCallback((sessionId) => {
    dispatch({ type: ACTIONS.SET_SELECTED_SESSION, payload: sessionId });
    // Persist to localStorage so it survives refresh/navigation
    if (sessionId) {
      localStorage.setItem('mmm_selectedSessionId', sessionId);
    } else {
      localStorage.removeItem('mmm_selectedSessionId');
    }
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: ACTIONS.SET_ERROR, payload: null });
  }, []);

  const clearBothSidesAlert = useCallback(() => {
    dispatch({ type: ACTIONS.CLEAR_BOTH_SIDES_ALERT });
  }, []);

  const actions = {
    fetchSessions,
    checkHealth,
    fetchParamsInfo,
    selectSession,
    clearError,
    clearBothSidesAlert,
  };

  // Computed values
  const selectedSession = state.sessions.find(
    (s) => s.session_id === state.selectedSessionId
  ) || null;

  const activeSessions = state.sessions.filter((s) =>
    ['RUNNING', 'PAUSED', 'BOTH_SIDES_UP', 'STARTING', 'PARTIAL_ENTRY'].includes(s.status)
  );

  const idleSessions = state.sessions.filter((s) => s.status === 'IDLE');
  const stoppedSessions = state.sessions.filter((s) => s.status === 'STOPPED');

  const value = {
    ...state,
    ...actions,
    selectedSession,
    activeSessions,
    idleSessions,
    stoppedSessions,
    socket,
  };

  return (
    <MMMContext.Provider value={value}>{children}</MMMContext.Provider>
  );
}

/**
 * Hook to access MMM context
 */
export function useMMM() {
  const context = useContext(MMMContext);
  if (!context) {
    throw new Error('useMMM must be used within an MMMProvider');
  }
  return context;
}

export default MMMContext;
