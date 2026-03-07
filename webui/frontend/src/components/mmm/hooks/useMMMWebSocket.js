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
  'mmm_regime',
  'mmm_perp_hedge_execution',
  'mmm_perp_hedge_flip',
  'mmm_perp_hedge_update',
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
  const [regimeData, setRegimeData] = useState(null);
  const [perpHedgeEvents, setPerpHedgeEvents] = useState([]);
  const [perpHedgeFlip, setPerpHedgeFlip] = useState(null);

  // Track the latest premium_map from price ticks (updated every 5s)
  const latestPremiumMap = useRef({});

  // Reset all state when sessionId changes to prevent stale cross-session data
  useEffect(() => {
    setHeartbeat(null);
    setAdjustments([]);
    setReversals([]);
    setShifts([]);
    setCloseEvents([]);
    setBothSidesAlert(null);
    setSafetyEvents([]);
    setPnl(null);
    setStatus(null);
    setWalkthroughEntries([]);
    setRegimeData(null);
    setPerpHedgeEvents([]);
    setPerpHedgeFlip(null);
    latestPremiumMap.current = {};
  }, [sessionId]);

  useEffect(() => {
    if (!sharedSocket) return;

    const socket = sharedSocket;

    // Fix F3.5: Safe handler wrapper to prevent unhandled exceptions from breaking state updates
    const safeHandler = (handler, eventName) => (data) => {
      try {
        handler(data);
      } catch (err) {
        console.error(`[useMMMWebSocket] Error in ${eventName} handler:`, err);
      }
    };

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
    socket.on('mmm_heartbeat', safeHandler(onHeartbeat, 'mmm_heartbeat'));

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
    socket.on('mmm_price_tick', safeHandler(onPriceTick, 'mmm_price_tick'));

    // Adjustments
    const onAdjustment = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setAdjustments((prev) => [...prev.slice(-99), data]);
      }
    };
    socket.on('mmm_adjustment', safeHandler(onAdjustment, 'mmm_adjustment'));

    // Reversals
    const onReversal = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setReversals((prev) => [...prev.slice(-49), data]);
      }
    };
    socket.on('mmm_reversal', safeHandler(onReversal, 'mmm_reversal'));

    // Strike shifts
    const onShift = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setShifts((prev) => [...prev.slice(-49), data]);
      }
    };
    socket.on('mmm_shift', safeHandler(onShift, 'mmm_shift'));

    // Close-at-5
    const onCloseAt5 = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setCloseEvents((prev) => [...prev.slice(-49), data]);
      }
    };
    socket.on('mmm_close_at_5', safeHandler(onCloseAt5, 'mmm_close_at_5'));

    // Both-sides alert
    const onBothSides = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setBothSidesAlert(data);
      }
    };
    socket.on('mmm_both_sides', safeHandler(onBothSides, 'mmm_both_sides'));

    // Safety events
    const onSafety = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setSafetyEvents((prev) => [...prev.slice(-99), data]);
      }
    };
    socket.on('mmm_safety', safeHandler(onSafety, 'mmm_safety'));

    // P&L updates
    const onPnl = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setPnl(data);
      }
    };
    socket.on('mmm_pnl_update', safeHandler(onPnl, 'mmm_pnl_update'));

    // Status changes
    const onStatus = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setStatus(data);
      }
    };
    socket.on('mmm_status_change', safeHandler(onStatus, 'mmm_status_change'));

    // Params changed (handled by useMMMParams hook, but keep listener)
    const onParams = () => { };
    socket.on('mmm_params_changed', safeHandler(onParams, 'mmm_params_changed'));

    // Walkthrough entries (real-time algo calculation walk-through)
    const onWalkthrough = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setWalkthroughEntries((prev) => [...prev.slice(-199), data.entry]);
      }
    };
    socket.on('mmm_walkthrough', safeHandler(onWalkthrough, 'mmm_walkthrough'));

    // Regime controls
    const onRegime = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setRegimeData(data);
      }
    };
    socket.on('mmm_regime', safeHandler(onRegime, 'mmm_regime'));

    // Perp hedge executions
    const onPerpExecution = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setPerpHedgeEvents((prev) => [...prev.slice(-49), data]);
      }
    };
    socket.on('mmm_perp_hedge_execution', safeHandler(onPerpExecution, 'mmm_perp_hedge_execution'));

    // Perp hedge flip (long↔short direction change)
    const onPerpFlip = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setPerpHedgeFlip(data);
      }
    };
    socket.on('mmm_perp_hedge_flip', safeHandler(onPerpFlip, 'mmm_perp_hedge_flip'));

    // Perp hedge update (periodic state sync)
    const onPerpUpdate = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        // Merge into heartbeat perp_hedge if available
        setHeartbeat((prev) => {
          if (!prev) return prev;
          return { ...prev, perp_hedge: { ...prev.perp_hedge, ...data } };
        });
      }
    };
    socket.on('mmm_perp_hedge_update', safeHandler(onPerpUpdate, 'mmm_perp_hedge_update'));

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
      socket.off('mmm_regime', onRegime);
      socket.off('mmm_perp_hedge_execution', onPerpExecution);
      socket.off('mmm_perp_hedge_flip', onPerpFlip);
      socket.off('mmm_perp_hedge_update', onPerpUpdate);
      // Fix F3.11: Clear ref to prevent memory retention on unmount
      latestPremiumMap.current = {};
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
    regimeData,
    perpHedgeEvents,
    perpHedgeFlip,
  };
}
