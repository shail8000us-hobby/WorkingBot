/**
 * useSSRAlgoSession Hook
 * 
 * Custom hook for managing individual SSR Algo session state.
 * Provides session data, computed properties, and action handlers.
 * 
 * Per Implementation Plan: Section 3.2
 * Created: February 3, 2026
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import ssrAlgoService from '../ssrAlgoService';

/**
 * Check if current price is in max loss zone
 * @param {Object} session - Session data
 * @param {number} currentPrice - Current underlying price
 * @param {number} tolerance - Price tolerance (default 100)
 * @returns {Object} Zone status
 */
const checkMaxLossZone = (session, currentPrice, tolerance = 100) => {
  if (!session || !currentPrice) {
    return { inZone: false, zoneType: null, distance: null };
  }

  const { max_loss_upper, max_loss_lower } = session;
  
  if (!max_loss_upper || !max_loss_lower) {
    return { inZone: false, zoneType: null, distance: null };
  }

  const upperDistance = max_loss_upper - currentPrice;
  const lowerDistance = currentPrice - max_loss_lower;

  // Check if in upper max loss zone
  if (currentPrice >= max_loss_upper - tolerance) {
    return {
      inZone: true,
      zoneType: 'upper',
      distance: Math.abs(upperDistance),
      breached: currentPrice >= max_loss_upper,
    };
  }

  // Check if in lower max loss zone
  if (currentPrice <= max_loss_lower + tolerance) {
    return {
      inZone: true,
      zoneType: 'lower',
      distance: Math.abs(lowerDistance),
      breached: currentPrice <= max_loss_lower,
    };
  }

  // In safe zone - return distance to nearest boundary
  return {
    inZone: false,
    zoneType: null,
    distanceToUpper: upperDistance,
    distanceToLower: lowerDistance,
    nearestBoundary: upperDistance < lowerDistance ? 'upper' : 'lower',
    nearestDistance: Math.min(upperDistance, lowerDistance),
  };
};

/**
 * Custom hook for SSR Algo session management
 * @param {string} sessionId - Session ID to manage
 * @param {Object} options - Hook options
 * @returns {Object} Session state and handlers
 */
export const useSSRAlgoSession = (sessionId, options = {}) => {
  const {
    autoRefresh = true,
    refreshInterval = 10000,
    fetchPayoff = false,
    fetchMonitor = true,
  } = options;

  // State
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [payoffData, setPayoffData] = useState(null);
  const [monitorStatus, setMonitorStatus] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Fetch session data
  const fetchSession = useCallback(async (showLoading = true) => {
    if (!sessionId) return;

    if (showLoading) setLoading(true);
    
    try {
      const result = await ssrAlgoService.getSession(sessionId);
      if (result.success) {
        setSession(result.session);
        setError(null);
        
        // Extract current price from monitor status if available
        if (result.session?.monitor_status?.current_price) {
          setCurrentPrice(result.session.monitor_status.current_price);
        }
      } else {
        setError(result.error || 'Failed to fetch session');
      }
    } catch (err) {
      setError(err.message || 'Network error');
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [sessionId]);

  // Fetch payoff data
  const fetchPayoffData = useCallback(async () => {
    if (!sessionId) return;

    try {
      const result = await ssrAlgoService.getSessionPayoff(sessionId);
      if (result.success) {
        setPayoffData(result);
      }
    } catch (err) {
      console.error('Failed to fetch payoff data:', err);
    }
  }, [sessionId]);

  // Fetch monitor status
  const fetchMonitorStatus = useCallback(async () => {
    if (!sessionId) return;

    try {
      const result = await ssrAlgoService.getMonitorStatus(sessionId);
      if (result.success) {
        setMonitorStatus(result.monitor);
        if (result.monitor?.current_price) {
          setCurrentPrice(result.monitor.current_price);
        }
      }
    } catch (err) {
      console.error('Failed to fetch monitor status:', err);
    }
  }, [sessionId]);

  // Initial fetch
  useEffect(() => {
    fetchSession();
    if (fetchPayoff) fetchPayoffData();
    if (fetchMonitor) fetchMonitorStatus();
  }, [sessionId, fetchSession, fetchPayoff, fetchPayoffData, fetchMonitor, fetchMonitorStatus]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh || !sessionId) return;

    const interval = setInterval(() => {
      fetchSession(false);
      if (fetchMonitor) fetchMonitorStatus();
      if (fetchPayoff) fetchPayoffData();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, sessionId, refreshInterval, fetchSession, fetchMonitor, fetchMonitorStatus, fetchPayoff, fetchPayoffData]);

  // Computed properties
  const computed = useMemo(() => {
    const status = session?.status || 'IDLE';
    
    return {
      isActive: ['MONITORING', 'EXECUTING_AUTO_LOOP', 'SELECTING_STRIKES'].includes(status),
      isMonitoring: status === 'MONITORING',
      isExecuting: status === 'EXECUTING_AUTO_LOOP',
      isSelectingStrikes: status === 'SELECTING_STRIKES',
      isPaused: status === 'PAUSED',
      isStopped: status === 'STOPPED',
      isIdle: status === 'IDLE',
      canStart: status === 'IDLE',
      canPause: status === 'MONITORING',
      canResume: status === 'PAUSED',
      canStop: ['MONITORING', 'PAUSED', 'EXECUTING_AUTO_LOOP'].includes(status),
      canDelete: ['IDLE', 'STOPPED'].includes(status),
    };
  }, [session?.status]);

  // Max loss zone status
  const maxLossZone = useMemo(() => {
    return checkMaxLossZone(session, currentPrice);
  }, [session, currentPrice]);

  // Session actions
  const actions = useMemo(() => ({
    start: async () => {
      setActionLoading(true);
      try {
        const result = await ssrAlgoService.startSession(sessionId);
        if (result.success) {
          await fetchSession();
        }
        return result;
      } finally {
        setActionLoading(false);
      }
    },

    pause: async () => {
      setActionLoading(true);
      try {
        const result = await ssrAlgoService.pauseSession(sessionId);
        if (result.success) {
          await fetchSession();
        }
        return result;
      } finally {
        setActionLoading(false);
      }
    },

    resume: async () => {
      setActionLoading(true);
      try {
        const result = await ssrAlgoService.resumeSession(sessionId);
        if (result.success) {
          await fetchSession();
        }
        return result;
      } finally {
        setActionLoading(false);
      }
    },

    stop: async () => {
      setActionLoading(true);
      try {
        const result = await ssrAlgoService.stopSession(sessionId);
        if (result.success) {
          await fetchSession();
        }
        return result;
      } finally {
        setActionLoading(false);
      }
    },

    delete: async () => {
      setActionLoading(true);
      try {
        return await ssrAlgoService.deleteSession(sessionId);
      } finally {
        setActionLoading(false);
      }
    },

    refresh: () => {
      fetchSession();
      if (fetchPayoff) fetchPayoffData();
      if (fetchMonitor) fetchMonitorStatus();
    },
  }), [sessionId, fetchSession, fetchPayoff, fetchPayoffData, fetchMonitor, fetchMonitorStatus]);

  return {
    // Data
    session,
    sessionId,
    payoffData,
    monitorStatus,
    currentPrice,
    
    // Status
    loading,
    error,
    actionLoading,
    
    // Computed
    ...computed,
    maxLossZone,
    
    // Actions
    ...actions,
    
    // Utilities
    refetch: fetchSession,
    checkMaxLossZone: (price) => checkMaxLossZone(session, price),
  };
};

export default useSSRAlgoSession;
