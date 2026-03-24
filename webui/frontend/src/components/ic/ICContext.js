/**
 * IC Context — Iron Condor
 *
 * Centralized state management for IC sessions with:
 * - WebSocket real-time updates (heartbeat, adjustments, cycles)
 * - Network disconnection recovery with exponential backoff
 * - Multi-session state management
 *
 * Created: 2026-03-24
 */

import React, {
  createContext,
  useContext,
  useReducer,
  useEffect,
  useRef,
  useCallback,
} from 'react';
import icService from './icService';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';

// =============================================================================
// Initial State
// =============================================================================

const initialState = {
  sessions: [],
  selectedSessionId: localStorage.getItem('ic_selectedSessionId') || null,
  loading: true,
  error: null,
  connectionStatus: 'connected',
  lastUpdate: null,
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
  SET_CONNECTION_STATUS: 'SET_CONNECTION_STATUS',
  SET_LAST_UPDATE: 'SET_LAST_UPDATE',
};

// =============================================================================
// Reducer
// =============================================================================

function icReducer(state, action) {
  switch (action.type) {
    case ACTIONS.SET_SESSIONS:
      return { ...state, sessions: action.payload, loading: false };
    case ACTIONS.ADD_SESSION:
      return { ...state, sessions: [action.payload, ...state.sessions] };
    case ACTIONS.UPDATE_SESSION:
      return {
        ...state,
        sessions: state.sessions.map((s) =>
          s.session_id === action.payload.session_id ? { ...s, ...action.payload } : s
        ),
      };
    case ACTIONS.REMOVE_SESSION:
      return {
        ...state,
        sessions: state.sessions.filter((s) => s.session_id !== action.payload),
        selectedSessionId:
          state.selectedSessionId === action.payload ? null : state.selectedSessionId,
      };
    case ACTIONS.SET_SELECTED_SESSION:
      return { ...state, selectedSessionId: action.payload };
    case ACTIONS.SET_LOADING:
      if (state.loading === action.payload) return state;
      return { ...state, loading: action.payload };
    case ACTIONS.SET_ERROR:
      if (state.error === action.payload) return state;
      return { ...state, error: action.payload };
    case ACTIONS.SET_CONNECTION_STATUS:
      if (state.connectionStatus === action.payload) return state;
      return { ...state, connectionStatus: action.payload };
    case ACTIONS.SET_LAST_UPDATE:
      return { ...state, lastUpdate: action.payload };
    default:
      return state;
  }
}

// =============================================================================
// Context
// =============================================================================

const ICContext = createContext(null);

export function ICProvider({ children, socket }) {
  const [state, dispatch] = useReducer(icReducer, initialState);
  const retryTimeoutRef = useRef(null);
  const retryCountRef = useRef(0);
  const lastSessionsJson = useRef('');
  const maxRetries = 5;
  const baseRetryDelay = 2000;

  // Fetch sessions
  const fetchSessions = useCallback(async (showLoading = true) => {
    if (showLoading) dispatch({ type: ACTIONS.SET_LOADING, payload: true });

    try {
      const result = await icService.getSessions();
      if (result.success) {
        const sessions = result.sessions || [];
        const currentJson = JSON.stringify(sessions);
        if (currentJson !== lastSessionsJson.current) {
          lastSessionsJson.current = currentJson;
          dispatch({ type: ACTIONS.SET_SESSIONS, payload: sessions });
          dispatch({ type: ACTIONS.SET_LAST_UPDATE, payload: new Date().toISOString() });
        }
        dispatch({ type: ACTIONS.SET_ERROR, payload: null });
        dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'connected' });
        retryCountRef.current = 0;

        // Clear stale session selection
        const savedId = localStorage.getItem('ic_selectedSessionId');
        if (savedId && sessions.length > 0 && !sessions.find((s) => s.session_id === savedId)) {
          localStorage.removeItem('ic_selectedSessionId');
          dispatch({ type: ACTIONS.SET_SELECTED_SESSION, payload: null });
        }
      } else {
        dispatch({ type: ACTIONS.SET_ERROR, payload: result.error });
      }
    } catch (err) {
      console.error('IC: Failed to fetch sessions:', err);
      dispatch({ type: ACTIONS.SET_ERROR, payload: err.message });
      handleNetworkError();
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: false });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Network error with exponential backoff
  const handleNetworkError = useCallback(() => {
    dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'disconnected' });
    if (retryCountRef.current < maxRetries) {
      const delay = baseRetryDelay * Math.pow(2, retryCountRef.current);
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'reconnecting' });
      retryTimeoutRef.current = setTimeout(() => {
        retryCountRef.current++;
        fetchSessions(false);
      }, delay);
    }
  }, [fetchSessions]);

  // WebSocket handlers
  const handleHeartbeat = useCallback((data) => {
    if (!data?.session_id) return;
    dispatch({ type: ACTIONS.UPDATE_SESSION, payload: data });
    dispatch({ type: ACTIONS.SET_LAST_UPDATE, payload: new Date().toISOString() });
  }, []);

  const handleStatusChange = useCallback((data) => {
    if (!data?.session_id) return;
    dispatch({
      type: ACTIONS.UPDATE_SESSION,
      payload: { session_id: data.session_id, status: data.new_status },
    });
  }, []);

  const handleCycleOpened = useCallback(() => fetchSessions(false), [fetchSessions]);
  const handleCycleClosed = useCallback(() => fetchSessions(false), [fetchSessions]);
  const handleAdjustment = useCallback((data) => {
    if (!data?.session_id) return;
    console.log(`🔄 IC: Adjustment ${data.type} on session ${data.session_id}`);
    fetchSessions(false);
  }, [fetchSessions]);
  const handleSessionCreated = useCallback(() => fetchSessions(false), [fetchSessions]);
  const handleSessionDeleted = useCallback((data) => {
    if (!data?.session_id) return;
    fetchSessions(false);
  }, [fetchSessions]);
  const handlePnlUpdate = useCallback((data) => {
    if (!data?.session_id) return;
    dispatch({
      type: ACTIONS.UPDATE_SESSION,
      payload: {
        session_id: data.session_id,
        unrealized_pnl: data.unrealized_pnl,
        max_profit: data.max_profit,
        max_loss: data.max_loss,
        pnl_pct: data.pnl_pct,
        total_realized_pnl: data.total_realized,
      },
    });
  }, []);

  // Wire WebSocket listeners
  useEffect(() => {
    if (!socket) return;

    socket.on('ic_heartbeat', handleHeartbeat);
    socket.on('ic_status_change', handleStatusChange);
    socket.on('ic_cycle_opened', handleCycleOpened);
    socket.on('ic_cycle_closed', handleCycleClosed);
    socket.on('ic_adjustment', handleAdjustment);
    socket.on('ic_session_created', handleSessionCreated);
    socket.on('ic_session_deleted', handleSessionDeleted);
    socket.on('ic_pnl_update', handlePnlUpdate);
    socket.on('ic_safety', (data) => console.warn('🛡️ IC Safety:', data));
    socket.on('ic_breach_alert', (data) => console.warn('⚠️ IC Breach:', data));

    console.log('📡 IC: WebSocket listeners attached');

    return () => {
      socket.off('ic_heartbeat', handleHeartbeat);
      socket.off('ic_status_change', handleStatusChange);
      socket.off('ic_cycle_opened', handleCycleOpened);
      socket.off('ic_cycle_closed', handleCycleClosed);
      socket.off('ic_adjustment', handleAdjustment);
      socket.off('ic_session_created', handleSessionCreated);
      socket.off('ic_session_deleted', handleSessionDeleted);
      socket.off('ic_pnl_update', handlePnlUpdate);
      socket.off('ic_safety');
      socket.off('ic_breach_alert');
      console.log('📡 IC: WebSocket listeners detached');
    };
  }, [
    socket, handleHeartbeat, handleStatusChange,
    handleCycleOpened, handleCycleClosed, handleAdjustment,
    handleSessionCreated, handleSessionDeleted, handlePnlUpdate,
  ]);

  // Online/offline recovery
  useEffect(() => {
    const handleOnline = () => {
      retryCountRef.current = 0;
      fetchSessions(false);
    };
    const handleOffline = () => {
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'disconnected' });
    };
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [fetchSessions]);

  // Initial load
  useEffect(() => {
    return () => {
      if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current);
    };
  }, []);

  // Polling
  const fetchSessionsSilent = useCallback(() => fetchSessions(false), [fetchSessions]);
  useVisibilityAwarePolling(fetchSessionsSilent, 30000, 120000);

  // Exposed actions
  const selectSession = useCallback((sessionId) => {
    dispatch({ type: ACTIONS.SET_SELECTED_SESSION, payload: sessionId });
    if (sessionId) {
      localStorage.setItem('ic_selectedSessionId', sessionId);
    } else {
      localStorage.removeItem('ic_selectedSessionId');
    }
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: ACTIONS.SET_ERROR, payload: null });
  }, []);

  const selectedSession = state.sessions.find(
    (s) => s.session_id === state.selectedSessionId
  ) || null;

  const activeSessions = state.sessions.filter((s) =>
    ['RUNNING', 'PAUSED'].includes(s.status)
  );

  const value = {
    ...state,
    fetchSessions,
    selectSession,
    clearError,
    selectedSession,
    activeSessions,
    socket,
  };

  return <ICContext.Provider value={value}>{children}</ICContext.Provider>;
}

export function useIC() {
  const context = useContext(ICContext);
  if (!context) {
    throw new Error('useIC must be used within an ICProvider');
  }
  return context;
}

export default ICContext;
