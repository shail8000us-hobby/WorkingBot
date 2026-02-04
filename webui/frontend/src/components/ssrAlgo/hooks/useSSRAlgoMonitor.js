/**
 * useSSRAlgoMonitor Hook
 * 
 * Custom hook for monitoring price movements and zone status.
 * Tracks time in max loss zone and triggers alerts.
 * 
 * Per Implementation Plan: Section 3.2
 * Created: February 3, 2026
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import ssrAlgoService from '../ssrAlgoService';

/**
 * Calculate zone status based on price and boundaries
 * @param {number} price - Current price
 * @param {number} upper - Upper max loss boundary
 * @param {number} lower - Lower max loss boundary
 * @param {number} warningDistance - Distance to start warning (default 200)
 * @returns {Object} Zone status
 */
const getZoneStatus = (price, upper, lower, warningDistance = 200) => {
  if (!price || !upper || !lower) {
    return { status: 'unknown', zone: null };
  }

  const distanceToUpper = upper - price;
  const distanceToLower = price - lower;
  const percentToUpper = (distanceToUpper / price) * 100;
  const percentToLower = (distanceToLower / price) * 100;

  // In max loss zone
  if (price >= upper) {
    return {
      status: 'danger',
      zone: 'upper',
      breached: true,
      distance: price - upper,
      distancePercent: Math.abs(percentToUpper),
      message: 'IN UPPER MAX LOSS ZONE',
      icon: '🚨',
      color: 'red',
    };
  }

  if (price <= lower) {
    return {
      status: 'danger',
      zone: 'lower',
      breached: true,
      distance: lower - price,
      distancePercent: Math.abs(percentToLower),
      message: 'IN LOWER MAX LOSS ZONE',
      icon: '🚨',
      color: 'red',
    };
  }

  // Approaching max loss zone (warning)
  if (distanceToUpper <= warningDistance) {
    return {
      status: 'warning',
      zone: 'upper',
      breached: false,
      distance: distanceToUpper,
      distancePercent: percentToUpper,
      message: `Approaching upper max loss zone (${Math.round(distanceToUpper)} pts)`,
      icon: '⚠️',
      color: 'orange',
    };
  }

  if (distanceToLower <= warningDistance) {
    return {
      status: 'warning',
      zone: 'lower',
      breached: false,
      distance: distanceToLower,
      distancePercent: percentToLower,
      message: `Approaching lower max loss zone (${Math.round(distanceToLower)} pts)`,
      icon: '⚠️',
      color: 'orange',
    };
  }

  // Safe zone
  const nearestBoundary = distanceToUpper < distanceToLower ? 'upper' : 'lower';
  const nearestDistance = Math.min(distanceToUpper, distanceToLower);
  const nearestPercent = Math.min(percentToUpper, percentToLower);

  return {
    status: 'safe',
    zone: null,
    breached: false,
    distanceToUpper: Math.round(distanceToUpper),
    distanceToLower: Math.round(distanceToLower),
    percentToUpper: Math.round(percentToUpper * 100) / 100,
    percentToLower: Math.round(percentToLower * 100) / 100,
    nearestBoundary,
    nearestDistance: Math.round(nearestDistance),
    nearestPercent: Math.round(nearestPercent * 100) / 100,
    message: 'Price in profit zone',
    icon: '✅',
    color: 'green',
  };
};

/**
 * Format duration in seconds to MM:SS or HH:MM:SS
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration
 */
const formatDuration = (seconds) => {
  if (!seconds || seconds < 0) return '00:00';
  
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

/**
 * Custom hook for price monitoring and zone tracking
 * @param {string} sessionId - Session ID to monitor
 * @param {Object} options - Hook options
 * @returns {Object} Monitor state and data
 */
export const useSSRAlgoMonitor = (sessionId, options = {}) => {
  const {
    pollInterval = 5000,
    dwellTimeSeconds = 600, // 10 minutes default
    warningDistance = 200,
    onZoneEnter = null,
    onZoneExit = null,
    onTriggerWarning = null,
  } = options;

  // State
  const [monitorStatus, setMonitorStatus] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Zone tracking state
  const [zoneEntryTime, setZoneEntryTime] = useState(null);
  const [timeInZone, setTimeInZone] = useState(0);
  const [previousZoneStatus, setPreviousZoneStatus] = useState(null);

  // Refs for callbacks
  const onZoneEnterRef = useRef(onZoneEnter);
  const onZoneExitRef = useRef(onZoneExit);
  const onTriggerWarningRef = useRef(onTriggerWarning);
  
  useEffect(() => {
    onZoneEnterRef.current = onZoneEnter;
    onZoneExitRef.current = onZoneExit;
    onTriggerWarningRef.current = onTriggerWarning;
  }, [onZoneEnter, onZoneExit, onTriggerWarning]);

  // Fetch monitor status
  const fetchMonitorStatus = useCallback(async (showLoading = true) => {
    if (!sessionId) return;

    if (showLoading) setLoading(true);

    try {
      // Fetch session for max loss points
      const sessionResult = await ssrAlgoService.getSession(sessionId);
      if (sessionResult.success) {
        setSession(sessionResult.session);
      }

      // Fetch monitor status
      const monitorResult = await ssrAlgoService.getMonitorStatus(sessionId);
      if (monitorResult.success) {
        setMonitorStatus(monitorResult.monitor);
        
        // Check if backend is tracking zone entry
        if (monitorResult.monitor?.zone_entry_time) {
          const entryTime = new Date(monitorResult.monitor.zone_entry_time);
          setZoneEntryTime(entryTime);
          const elapsed = Math.floor((Date.now() - entryTime.getTime()) / 1000);
          setTimeInZone(elapsed);
        }
      }

      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to fetch monitor status');
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [sessionId]);

  // Initial fetch
  useEffect(() => {
    fetchMonitorStatus();
  }, [sessionId, fetchMonitorStatus]);

  // Poll for updates
  useEffect(() => {
    if (!sessionId) return;

    const interval = setInterval(() => {
      fetchMonitorStatus(false);
    }, pollInterval);

    return () => clearInterval(interval);
  }, [sessionId, pollInterval, fetchMonitorStatus]);

  // Current zone status
  const zoneStatus = useMemo(() => {
    const currentPrice = monitorStatus?.current_price;
    const upper = session?.max_loss_upper;
    const lower = session?.max_loss_lower;

    return getZoneStatus(currentPrice, upper, lower, warningDistance);
  }, [monitorStatus?.current_price, session?.max_loss_upper, session?.max_loss_lower, warningDistance]);

  // Track zone entry/exit
  useEffect(() => {
    if (!zoneStatus) return;

    const wasInZone = previousZoneStatus?.status === 'danger';
    const isInZone = zoneStatus.status === 'danger';

    // Zone entry
    if (!wasInZone && isInZone) {
      setZoneEntryTime(new Date());
      setTimeInZone(0);
      if (onZoneEnterRef.current) {
        onZoneEnterRef.current(zoneStatus);
      }
    }

    // Zone exit
    if (wasInZone && !isInZone) {
      setZoneEntryTime(null);
      setTimeInZone(0);
      if (onZoneExitRef.current) {
        onZoneExitRef.current(zoneStatus);
      }
    }

    setPreviousZoneStatus(zoneStatus);
  }, [zoneStatus, previousZoneStatus]);

  // Update time in zone
  useEffect(() => {
    if (!zoneEntryTime) return;

    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - zoneEntryTime.getTime()) / 1000);
      setTimeInZone(elapsed);

      // Trigger warning at 50%, 75%, 90% of dwell time
      const thresholds = [0.5, 0.75, 0.9];
      const progress = elapsed / dwellTimeSeconds;
      
      thresholds.forEach(threshold => {
        const prevProgress = (elapsed - 1) / dwellTimeSeconds;
        if (prevProgress < threshold && progress >= threshold) {
          if (onTriggerWarningRef.current) {
            onTriggerWarningRef.current({
              threshold,
              elapsed,
              remaining: dwellTimeSeconds - elapsed,
              progress,
            });
          }
        }
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [zoneEntryTime, dwellTimeSeconds]);

  // Countdown to trigger
  const countdown = useMemo(() => {
    if (!zoneEntryTime || zoneStatus?.status !== 'danger') {
      return null;
    }

    const remaining = Math.max(0, dwellTimeSeconds - timeInZone);
    const progress = Math.min(100, (timeInZone / dwellTimeSeconds) * 100);

    return {
      elapsed: timeInZone,
      remaining,
      total: dwellTimeSeconds,
      progress,
      elapsedFormatted: formatDuration(timeInZone),
      remainingFormatted: formatDuration(remaining),
      totalFormatted: formatDuration(dwellTimeSeconds),
      willTrigger: remaining === 0,
    };
  }, [zoneEntryTime, timeInZone, dwellTimeSeconds, zoneStatus]);

  // Price statistics
  const priceStats = useMemo(() => {
    const price = monitorStatus?.current_price;
    const upper = session?.max_loss_upper;
    const lower = session?.max_loss_lower;

    if (!price || !upper || !lower) {
      return null;
    }

    const profitZoneWidth = upper - lower;
    const pricePositionInZone = ((price - lower) / profitZoneWidth) * 100;

    return {
      currentPrice: price,
      maxLossUpper: upper,
      maxLossLower: lower,
      profitZoneWidth,
      pricePositionInZone: Math.round(pricePositionInZone * 100) / 100,
      distanceToUpper: upper - price,
      distanceToLower: price - lower,
      percentToUpper: ((upper - price) / price) * 100,
      percentToLower: ((price - lower) / price) * 100,
    };
  }, [monitorStatus?.current_price, session?.max_loss_upper, session?.max_loss_lower]);

  return {
    // Data
    monitorStatus,
    session,
    currentPrice: monitorStatus?.current_price,
    
    // Zone status
    zoneStatus,
    inMaxLossZone: zoneStatus?.status === 'danger',
    zoneType: zoneStatus?.zone,
    zoneMessage: zoneStatus?.message,
    zoneColor: zoneStatus?.color,
    zoneIcon: zoneStatus?.icon,
    
    // Countdown
    countdown,
    timeInZone,
    zoneEntryTime,
    
    // Price stats
    priceStats,
    
    // Status
    loading,
    error,
    isMonitoring: monitorStatus?.is_running === true,
    isPaused: session?.status === 'PAUSED',
    
    // Actions
    refresh: () => fetchMonitorStatus(false),
    
    // Utilities
    formatDuration,
    getZoneStatus: (price) => getZoneStatus(price, session?.max_loss_upper, session?.max_loss_lower, warningDistance),
  };
};

export default useSSRAlgoMonitor;
