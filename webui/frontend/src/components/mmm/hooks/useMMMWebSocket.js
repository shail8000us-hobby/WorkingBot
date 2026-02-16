/**
 * useMMMWebSocket — Money Mind & Method
 *
 * WebSocket subscription hook for real-time MMM events.
 * Uses the SHARED socket from MMMContext (App.js RobustConnectionManager)
 * instead of creating a duplicate connection.
 *
 * Events: mmm_heartbeat, mmm_price_tick, mmm_adjustment, mmm_reversal,
 *         mmm_shift, mmm_close_at_5, mmm_both_sides, mmm_safety,
 *         mmm_pnl_update, mmm_params_changed, mmm_status_change,
 *         mmm_session_created
 *
 * Created: February 15, 2026
 * Updated: Uses shared socket — no duplicate io() connection
 * Updated: Added mmm_price_tick for 5-second real-time price updates
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const EVENTS = [
  'mmm_heartbeat',
  'mmm_price_tick',
  'mmm_adjustment',
  'mmm_reversal',
  'mmm_shift',
  'mmm_close_at_5',
  'mmm_both_sides',
  'mmm_safety',
  'mmm_pnl_update',
  'mmm_params_changed',
  'mmm_status_change',
  'mmm_session_created',
];

/**
 * @param {string} sessionId - Filter events for this session
 * @param {object} sharedSocket - The shared Socket.IO instance from MMMContext
 */
export default function useMMMWebSocket(sessionId, sharedSocket) {
  const [heartbeat, setHeartbeat] = useState(null);
  const [adjustments, setAdjustments] = useState([]);
  const [reversals, setReversals] = useState([]);
  const [shifts, setShifts] = useState([]);
  const [closeEvents, setCloseEvents] = useState([]);
  const [bothSidesAlert, setBothSidesAlert] = useState(null);
  const [safetyEvents, setSafetyEvents] = useState([]);
  const [pnl, setPnl] = useState(null);
  const [status, setStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const [walkthroughEntries, setWalkthroughEntries] = useState([]);

  // Track the latest premium_map from price ticks (updated every 5s)
  const latestPremiumMap = useRef({});

  useEffect(() => {
    if (!sharedSocket) return;

    const socket = sharedSocket;

    // Track connection state
    const onConnect = () => setConnected(true);
    const onDisconnect = () => setConnected(false);

    // Set initial state
    setConnected(socket.connected);

    socket.on('connect', onConnect);
    socket.on('disconnect', onDisconnect);

    // Heartbeat (every 5 minutes — full data including triggers, PnL, etc.)
    const onHeartbeat = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        // Merge any premium_map from latest price tick into heartbeat
        if (latestPremiumMap.current && Object.keys(latestPremiumMap.current).length > 0) {
          data.premium_map = { ...data.premium_map, ...latestPremiumMap.current };
        }
        setHeartbeat(data);
      }
    };
    socket.on('mmm_heartbeat', onHeartbeat);

    // Price ticks (every 5 seconds — lightweight, prices only)
    const onPriceTick = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        const freshMap = data.premium_map || {};
        latestPremiumMap.current = freshMap;

        // Merge fresh prices into existing heartbeat so UI updates immediately
        setHeartbeat((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            premium_map: { ...prev.premium_map, ...freshMap },
            _price_tick_ts: data.timestamp,
          };
        });
      }
    };
    socket.on('mmm_price_tick', onPriceTick);

    // Adjustments
    const onAdjustment = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setAdjustments((prev) => [...prev.slice(-99), data]);
      }
    };
    socket.on('mmm_adjustment', onAdjustment);

    // Reversals
    const onReversal = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setReversals((prev) => [...prev.slice(-49), data]);
      }
    };
    socket.on('mmm_reversal', onReversal);

    // Strike shifts
    const onShift = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setShifts((prev) => [...prev.slice(-49), data]);
      }
    };
    socket.on('mmm_shift', onShift);

    // Close-at-5
    const onCloseAt5 = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setCloseEvents((prev) => [...prev.slice(-49), data]);
      }
    };
    socket.on('mmm_close_at_5', onCloseAt5);

    // Both-sides alert
    const onBothSides = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setBothSidesAlert(data);
      }
    };
    socket.on('mmm_both_sides', onBothSides);

    // Safety events
    const onSafety = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setSafetyEvents((prev) => [...prev.slice(-99), data]);
      }
    };
    socket.on('mmm_safety', onSafety);

    // P&L updates
    const onPnl = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setPnl(data);
      }
    };
    socket.on('mmm_pnl_update', onPnl);

    // Status changes
    const onStatus = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setStatus(data);
      }
    };
    socket.on('mmm_status_change', onStatus);

    // Params changed (handled by useMMMParams hook, but keep listener)
    const onParams = () => { };
    socket.on('mmm_params_changed', onParams);

    // Walkthrough entries (real-time algo calculation walk-through)
    const onWalkthrough = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setWalkthroughEntries((prev) => [...prev.slice(-199), data.entry]);
      }
    };
    socket.on('mmm_walkthrough', onWalkthrough);

    return () => {
      // Remove only OUR listeners — don't disconnect the shared socket
      socket.off('connect', onConnect);
      socket.off('disconnect', onDisconnect);
      socket.off('mmm_heartbeat', onHeartbeat);
      socket.off('mmm_price_tick', onPriceTick);
      socket.off('mmm_adjustment', onAdjustment);
      socket.off('mmm_reversal', onReversal);
      socket.off('mmm_shift', onShift);
      socket.off('mmm_close_at_5', onCloseAt5);
      socket.off('mmm_both_sides', onBothSides);
      socket.off('mmm_safety', onSafety);
      socket.off('mmm_pnl_update', onPnl);
      socket.off('mmm_status_change', onStatus);
      socket.off('mmm_params_changed', onParams);
      socket.off('mmm_walkthrough', onWalkthrough);
    };
  }, [sessionId, sharedSocket]);

  const clearBothSidesAlert = useCallback(() => {
    setBothSidesAlert(null);
  }, []);

  const clearSafetyEvents = useCallback(() => {
    setSafetyEvents([]);
  }, []);

  return {
    connected,
    heartbeat,
    adjustments,
    reversals,
    shifts,
    closeEvents,
    bothSidesAlert,
    safetyEvents,
    pnl,
    status,
    socket: sharedSocket,
    clearBothSidesAlert,
    clearSafetyEvents,
    walkthroughEntries,
  };
}
