/**
 * SSR Algo Context
 * 
 * Provides centralized state management for SSR Algo sessions with:
 * - WebSocket real-time updates
 * - Sound notifications for max loss zone alerts
 * - Network disconnection recovery
 * - Multi-session state management
 * 
 * Created: February 2, 2026
 */

import React, { createContext, useContext, useReducer, useEffect, useRef, useCallback } from 'react';
import ssrAlgoService from './ssrAlgoService';
import soundManager from '../../utils/soundManager';

// Initial state
const initialState = {
  sessions: [],
  selectedSession: null,
  selectedPayoff: null,
  loading: true,
  error: null,
  healthStatus: null,
  connectionStatus: 'connected', // connected, disconnected, reconnecting
  lastUpdate: null,
  soundEnabled: true,
  maxLossAlertActive: false,
};

// Action types
const ACTIONS = {
  SET_SESSIONS: 'SET_SESSIONS',
  ADD_SESSION: 'ADD_SESSION',
  UPDATE_SESSION: 'UPDATE_SESSION',
  REMOVE_SESSION: 'REMOVE_SESSION',
  SET_SELECTED_SESSION: 'SET_SELECTED_SESSION',
  SET_SELECTED_PAYOFF: 'SET_SELECTED_PAYOFF',
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  SET_HEALTH_STATUS: 'SET_HEALTH_STATUS',
  SET_CONNECTION_STATUS: 'SET_CONNECTION_STATUS',
  SET_LAST_UPDATE: 'SET_LAST_UPDATE',
  TOGGLE_SOUND: 'TOGGLE_SOUND',
  SET_MAX_LOSS_ALERT: 'SET_MAX_LOSS_ALERT',
  RESET_STATE: 'RESET_STATE',
};

// Reducer
function ssrAlgoReducer(state, action) {
  switch (action.type) {
    case ACTIONS.SET_SESSIONS:
      return { ...state, sessions: action.payload, loading: false };
    
    case ACTIONS.ADD_SESSION:
      return { 
        ...state, 
        sessions: [action.payload, ...state.sessions] 
      };
    
    case ACTIONS.UPDATE_SESSION:
      return {
        ...state,
        sessions: state.sessions.map(s => 
          s.session_id === action.payload.session_id 
            ? { ...s, ...action.payload } 
            : s
        ),
        selectedSession: state.selectedSession?.session_id === action.payload.session_id
          ? { ...state.selectedSession, ...action.payload }
          : state.selectedSession,
      };
    
    case ACTIONS.REMOVE_SESSION:
      return {
        ...state,
        sessions: state.sessions.filter(s => s.session_id !== action.payload),
        selectedSession: state.selectedSession?.session_id === action.payload
          ? null
          : state.selectedSession,
      };
    
    case ACTIONS.SET_SELECTED_SESSION:
      return { ...state, selectedSession: action.payload };
    
    case ACTIONS.SET_SELECTED_PAYOFF:
      return { ...state, selectedPayoff: action.payload };
    
    case ACTIONS.SET_LOADING:
      return { ...state, loading: action.payload };
    
    case ACTIONS.SET_ERROR:
      return { ...state, error: action.payload };
    
    case ACTIONS.SET_HEALTH_STATUS:
      return { ...state, healthStatus: action.payload };
    
    case ACTIONS.SET_CONNECTION_STATUS:
      return { ...state, connectionStatus: action.payload };
    
    case ACTIONS.SET_LAST_UPDATE:
      return { ...state, lastUpdate: action.payload };
    
    case ACTIONS.TOGGLE_SOUND:
      return { ...state, soundEnabled: !state.soundEnabled };
    
    case ACTIONS.SET_MAX_LOSS_ALERT:
      return { ...state, maxLossAlertActive: action.payload };
    
    case ACTIONS.RESET_STATE:
      return { ...initialState };
    
    default:
      return state;
  }
}

// Context
const SSRAlgoContext = createContext(null);

/**
 * SSR Algo Provider Component
 * Provides state management, WebSocket, sound, and network recovery
 */
export function SSRAlgoProvider({ children, socket }) {
  const [state, dispatch] = useReducer(ssrAlgoReducer, initialState);
  const retryTimeoutRef = useRef(null);
  const retryCountRef = useRef(0);
  const sessionsFetchInFlightRef = useRef(false);
  const sessionsFetchPendingRef = useRef(false);
  const sessionsFetchPendingShowLoadingRef = useRef(false);
  const healthCheckInFlightRef = useRef(false);
  const healthCheckPendingRef = useRef(false);
  const soundEnabledRef = useRef(initialState.soundEnabled);
  const maxLossAlertActiveRef = useRef(initialState.maxLossAlertActive);
  const maxRetries = 5;
  const baseRetryDelay = 2000;

  useEffect(() => {
    soundEnabledRef.current = state.soundEnabled;
  }, [state.soundEnabled]);

  useEffect(() => {
    maxLossAlertActiveRef.current = state.maxLossAlertActive;
  }, [state.maxLossAlertActive]);

  // Play max loss alert sound
  const playMaxLossAlert = useCallback(() => {
    if (soundEnabledRef.current && soundManager.initialized) {
      soundManager.playSound('alert');
      console.log('🔔 SSR Algo: Max loss zone alert sound played');
    }
  }, []);

  // Fetch sessions with retry logic
  const fetchSessions = useCallback(async (showLoading = true) => {
    if (sessionsFetchInFlightRef.current) {
      sessionsFetchPendingRef.current = true;
      sessionsFetchPendingShowLoadingRef.current =
        sessionsFetchPendingShowLoadingRef.current || showLoading;
      return;
    }

    sessionsFetchInFlightRef.current = true;
    const shouldShowLoading = showLoading;

    if (shouldShowLoading) {
      dispatch({ type: ACTIONS.SET_LOADING, payload: true });
    }
    
    try {
      const result = await ssrAlgoService.getSessions(false);
      if (result.success) {
        dispatch({ type: ACTIONS.SET_SESSIONS, payload: result.sessions || [] });
        dispatch({ type: ACTIONS.SET_ERROR, payload: null });
        dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'connected' });
        dispatch({ type: ACTIONS.SET_LAST_UPDATE, payload: new Date().toISOString() });
        retryCountRef.current = 0;
      } else {
        dispatch({ type: ACTIONS.SET_ERROR, payload: result.error });
      }
    } catch (err) {
      console.error('SSR Algo: Failed to fetch sessions:', err);
      dispatch({ type: ACTIONS.SET_ERROR, payload: err.message });
      handleNetworkError();
    } finally {
      if (shouldShowLoading) {
        dispatch({ type: ACTIONS.SET_LOADING, payload: false });
      }

      sessionsFetchInFlightRef.current = false;
      if (sessionsFetchPendingRef.current) {
        const pendingShowLoading = sessionsFetchPendingShowLoadingRef.current;
        sessionsFetchPendingRef.current = false;
        sessionsFetchPendingShowLoadingRef.current = false;
        Promise.resolve().then(() => {
          fetchSessions(pendingShowLoading);
        });
      }
    }
  }, []);

  // Network error handler with exponential backoff
  const handleNetworkError = useCallback(() => {
    dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'disconnected' });
    
    if (retryCountRef.current < maxRetries) {
      const delay = baseRetryDelay * Math.pow(2, retryCountRef.current);
      console.log(`SSR Algo: Network error, retrying in ${delay}ms (attempt ${retryCountRef.current + 1}/${maxRetries})`);
      
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'reconnecting' });

      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
      
      retryTimeoutRef.current = setTimeout(() => {
        retryCountRef.current++;
        fetchSessions(false);
      }, delay);
    } else {
      console.error('SSR Algo: Max retries reached, giving up');
      dispatch({ type: ACTIONS.SET_ERROR, payload: 'Connection lost. Please check your network and refresh.' });
    }
  }, [fetchSessions]);

  // Health check
  const checkHealth = useCallback(async () => {
    if (healthCheckInFlightRef.current) {
      healthCheckPendingRef.current = true;
      return;
    }

    healthCheckInFlightRef.current = true;
    try {
      const result = await ssrAlgoService.healthCheck();
      dispatch({ type: ACTIONS.SET_HEALTH_STATUS, payload: result.success ? 'healthy' : 'error' });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_HEALTH_STATUS, payload: 'error' });
    } finally {
      healthCheckInFlightRef.current = false;
      if (healthCheckPendingRef.current) {
        healthCheckPendingRef.current = false;
        Promise.resolve().then(() => {
          checkHealth();
        });
      }
    }
  }, []);

  // Handle WebSocket session updates
  const handleSessionUpdate = useCallback((data) => {
    if (!data || !data.session_id) return;
    
    console.log('📡 SSR Algo: WebSocket update received for session:', data.session_id);
    dispatch({ type: ACTIONS.UPDATE_SESSION, payload: data });
    dispatch({ type: ACTIONS.SET_LAST_UPDATE, payload: new Date().toISOString() });
    
    // Check for max loss zone entry
    if (data.monitor_status?.in_max_loss_zone && !maxLossAlertActiveRef.current) {
      dispatch({ type: ACTIONS.SET_MAX_LOSS_ALERT, payload: true });
      maxLossAlertActiveRef.current = true;
      playMaxLossAlert();
    } else if (!data.monitor_status?.in_max_loss_zone && maxLossAlertActiveRef.current) {
      dispatch({ type: ACTIONS.SET_MAX_LOSS_ALERT, payload: false });
      maxLossAlertActiveRef.current = false;
    }
  }, [playMaxLossAlert]);

  // Handle new session created via WebSocket
  const handleNewSession = useCallback((data) => {
    if (!data) return;
    console.log('📡 SSR Algo: New session created:', data.session_id);
    dispatch({ type: ACTIONS.ADD_SESSION, payload: data });
  }, []);

  // Handle session deleted via WebSocket
  const handleSessionDeleted = useCallback((data) => {
    if (!data || !data.session_id) return;
    console.log('📡 SSR Algo: Session deleted:', data.session_id);
    dispatch({ type: ACTIONS.REMOVE_SESSION, payload: data.session_id });
  }, []);

  // Setup WebSocket listeners
  useEffect(() => {
    if (!socket) return;

    // Subscribe to SSR Algo events
    socket.emit('subscribe_ssr_algo');
    console.log('📡 SSR Algo: Subscribed to WebSocket events');

    // Event listeners
    socket.on('ssr_algo_session_update', handleSessionUpdate);
    socket.on('ssr_algo_new_session', handleNewSession);
    socket.on('ssr_algo_session_deleted', handleSessionDeleted);
    const handleMaxLossAlert = (data) => {
      if (!maxLossAlertActiveRef.current) {
        dispatch({ type: ACTIONS.SET_MAX_LOSS_ALERT, payload: true });
        maxLossAlertActiveRef.current = true;
      }
      playMaxLossAlert();
      console.warn('🚨 SSR Algo: Max loss zone alert!', data);
    };
    socket.on('ssr_algo_max_loss_alert', handleMaxLossAlert);

    // Cleanup
    return () => {
      socket.emit('unsubscribe_ssr_algo');
      socket.off('ssr_algo_session_update', handleSessionUpdate);
      socket.off('ssr_algo_new_session', handleNewSession);
      socket.off('ssr_algo_session_deleted', handleSessionDeleted);
      socket.off('ssr_algo_max_loss_alert', handleMaxLossAlert);
      console.log('📡 SSR Algo: Unsubscribed from WebSocket events');
    };
  }, [socket, handleSessionUpdate, handleNewSession, handleSessionDeleted, playMaxLossAlert]);

  // Online/offline event listeners for network recovery
  useEffect(() => {
    const handleOnline = () => {
      console.log('🌐 SSR Algo: Network back online, refreshing...');
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'reconnecting' });
      retryCountRef.current = 0;
      fetchSessions(false);
    };

    const handleOffline = () => {
      console.log('📴 SSR Algo: Network offline');
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
    fetchSessions();
    checkHealth();

    // Auto-refresh every 10 seconds (fallback for WebSocket)
    const interval = setInterval(() => {
      fetchSessions(false);
    }, 10000);

    return () => {
      clearInterval(interval);
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, [fetchSessions, checkHealth]);

  // Initialize sound manager
  useEffect(() => {
    if (!soundManager.initialized) {
      soundManager.initialize();
    }
  }, []);

  // Actions
  const actions = {
    fetchSessions,
    checkHealth,
    
    addSession: (session) => {
      dispatch({ type: ACTIONS.ADD_SESSION, payload: session });
    },
    
    updateSession: (session) => {
      dispatch({ type: ACTIONS.UPDATE_SESSION, payload: session });
    },
    
    removeSession: (sessionId) => {
      dispatch({ type: ACTIONS.REMOVE_SESSION, payload: sessionId });
    },
    
    selectSession: async (session) => {
      dispatch({ type: ACTIONS.SET_SELECTED_SESSION, payload: session });
      if (session) {
        try {
          const payoff = await ssrAlgoService.getSessionPayoff(session.session_id);
          if (payoff.success) {
            dispatch({ type: ACTIONS.SET_SELECTED_PAYOFF, payload: payoff });
          }
        } catch (err) {
          console.error('Failed to fetch payoff:', err);
        }
      } else {
        dispatch({ type: ACTIONS.SET_SELECTED_PAYOFF, payload: null });
      }
    },
    
    clearError: () => {
      dispatch({ type: ACTIONS.SET_ERROR, payload: null });
    },
    
    toggleSound: () => {
      dispatch({ type: ACTIONS.TOGGLE_SOUND });
    },
    
    testMaxLossAlert: () => {
      playMaxLossAlert();
    },
  };

  // Computed values
  const activeSessions = state.sessions.filter(s => 
    ['IDLE', 'SELECTING_STRIKES', 'EXECUTING_AUTO_LOOP', 'MONITORING', 'PAUSED'].includes(s.status)
  );
  
  const historicalSessions = state.sessions.filter(s => s.status === 'STOPPED');

  const value = {
    ...state,
    ...actions,
    activeSessions,
    historicalSessions,
  };

  return (
    <SSRAlgoContext.Provider value={value}>
      {children}
    </SSRAlgoContext.Provider>
  );
}

/**
 * Hook to access SSR Algo context
 */
export function useSSRAlgo() {
  const context = useContext(SSRAlgoContext);
  if (!context) {
    throw new Error('useSSRAlgo must be used within an SSRAlgoProvider');
  }
  return context;
}

export default SSRAlgoContext;
