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

const LIVE_PRICE_FLUSH_MS = 250;

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

  // Live bid/ask prices from options_ticker_update (sub-second from Delta WS l1_orderbook)
  // { [symbol]: { bid, ask, mid, ts } }
  const [livePrices, setLivePrices] = useState({});
  const livePriceBufferRef = useRef({});
  const livePriceFlushTimerRef = useRef(null);

  // Reset all state when sessionId changes to prevent stale cross-session data
  useEffect(() => {
    if (livePriceFlushTimerRef.current) {
      clearTimeout(livePriceFlushTimerRef.current);
      livePriceFlushTimerRef.current = null;
    }
    livePriceBufferRef.current = {};
    setLivePrices({});
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
    const listeners = [];

    const addListener = (eventName, handler, wrapSafe = true) => {
      const finalHandler = wrapSafe ? safeHandler(handler, eventName) : handler;
      listeners.push([eventName, finalHandler]);
      socket.on(eventName, finalHandler);
    };

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

    addListener('connect', onConnect, false);
    addListener('disconnect', onDisconnect, false);

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
    addListener('mmm_heartbeat', onHeartbeat);

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
    addListener('mmm_price_tick', onPriceTick);

    // Adjustments
    const onAdjustment = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setAdjustments((prev) => [...prev.slice(-99), data]);
      }
    };
    addListener('mmm_adjustment', onAdjustment);

    // Reversals
    const onReversal = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setReversals((prev) => [...prev.slice(-49), data]);
      }
    };
    addListener('mmm_reversal', onReversal);

    // Strike shifts
    const onShift = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setShifts((prev) => [...prev.slice(-49), data]);
      }
    };
    addListener('mmm_shift', onShift);

    // Close-at-5
    const onCloseAt5 = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setCloseEvents((prev) => [...prev.slice(-49), data]);
      }
    };
    addListener('mmm_close_at_5', onCloseAt5);

    // Both-sides alert
    const onBothSides = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setBothSidesAlert(data);
      }
    };
    addListener('mmm_both_sides', onBothSides);

    // Safety events
    const onSafety = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setSafetyEvents((prev) => [...prev.slice(-99), data]);
      }
    };
    addListener('mmm_safety', onSafety);

    // P&L updates
    const onPnl = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setPnl(data);
      }
    };
    addListener('mmm_pnl_update', onPnl);

    // Status changes
    const onStatus = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setStatus(data);
      }
    };
    addListener('mmm_status_change', onStatus);

    // Params changed (handled by useMMMParams hook, but keep listener)
    const onParams = () => { };
    addListener('mmm_params_changed', onParams);

    // Walkthrough entries (real-time algo calculation walk-through)
    const onWalkthrough = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setWalkthroughEntries((prev) => [...prev.slice(-199), data.entry]);
      }
    };
    addListener('mmm_walkthrough', onWalkthrough);

    // Regime controls
    const onRegime = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setRegimeData(data);
      }
    };
    addListener('mmm_regime', onRegime);

    // Perp hedge executions
    const onPerpExecution = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setPerpHedgeEvents((prev) => [...prev.slice(-49), data]);
      }
    };
    addListener('mmm_perp_hedge_execution', onPerpExecution);

    // Perp hedge flip (long↔short direction change)
    const onPerpFlip = (data) => {
      if (!sessionId || data.session_id === sessionId) {
        setPerpHedgeFlip(data);
      }
    };
    addListener('mmm_perp_hedge_flip', onPerpFlip);

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
    addListener('mmm_perp_hedge_update', onPerpUpdate);

    // Live bid/ask from Delta WS l1_orderbook via the existing options ticker pipeline.
    // Same event as the options panel — no backend changes needed.
    const flushLivePrices = () => {
      livePriceFlushTimerRef.current = null;
      const buffered = livePriceBufferRef.current;
      livePriceBufferRef.current = {};
      const symbols = Object.keys(buffered);
      if (symbols.length === 0) return;

      setLivePrices((prev) => {
        let changed = false;
        const next = { ...prev };
        for (const symbol of symbols) {
          const update = buffered[symbol];
          const prevTick = prev[symbol];
          if (
            prevTick
            && prevTick.bid === update.bid
            && prevTick.ask === update.ask
            && prevTick.mid === update.mid
            && prevTick.ts === update.ts
          ) {
            continue;
          }
          next[symbol] = update;
          changed = true;
        }
        return changed ? next : prev;
      });
    };

    const onOptionsTicker = (data) => {
      const { symbol, best_bid, best_ask, timestamp } = data;
      if (!symbol) return;
      livePriceBufferRef.current[symbol] = {
        bid: best_bid,
        ask: best_ask,
        mid: best_bid > 0 && best_ask > 0 ? (best_bid + best_ask) / 2 : (best_bid || best_ask || 0),
        ts: timestamp,
      };

      if (!livePriceFlushTimerRef.current) {
        livePriceFlushTimerRef.current = setTimeout(flushLivePrices, LIVE_PRICE_FLUSH_MS);
      }
    };
    addListener('options_ticker_update', onOptionsTicker, false);

    return () => {
      // Remove only OUR listeners — don't disconnect the shared socket
      for (const [eventName, handler] of listeners) {
        socket.off(eventName, handler);
      }
      if (livePriceFlushTimerRef.current) {
        clearTimeout(livePriceFlushTimerRef.current);
        livePriceFlushTimerRef.current = null;
      }
      livePriceBufferRef.current = {};
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
    livePrices,
  };
}
