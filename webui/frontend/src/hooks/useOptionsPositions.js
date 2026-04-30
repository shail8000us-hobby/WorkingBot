import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { io } from 'socket.io-client';
import api from '../utils/apiShim';
import { readWarmJSON, setWarmJSON } from '../utils/dataWarmCache';
import { applyTickerUpdate } from './wsTickerUpdater';

// Phase 5 Optimization: IV cache with 60s TTL to avoid 17+ external API calls per poll
const IV_CACHE_TTL_MS = 60000;
let _ivCache = { data: {}, timestamp: 0 };

// BUG-26 FIX: moved IV helper functions to MODULE LEVEL (outside the hook).
// Previously they were re-created each render, causing fetchDashboard's useCallback([]deps)
// to capture a stale first-render instance. Module-level = stable reference forever.
const fetchIVForSymbols = async (symbols) => {
  const tickerPromises = symbols.map(async (symbol) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000); // 3s timeout per call
    try {
      const response = await fetch(
        `https://api.india.delta.exchange/v2/tickers/${symbol}`,
        { signal: controller.signal },
      );
      clearTimeout(timeoutId);
      const result = await response.json();
      if (result?.success && result?.result) {
        const quotes = result.result.quotes || {};
        const bidIV = parseFloat(quotes.bid_iv) || 0;
        const askIV = parseFloat(quotes.ask_iv) || 0;
        return { symbol, iv: bidIV && askIV ? (bidIV + askIV) / 2 : (bidIV || askIV) };
      }
      return { symbol, iv: null };
    } catch {
      clearTimeout(timeoutId);
      return { symbol, iv: null };
    }
  });
  const ivData = await Promise.all(tickerPromises);
  return Object.fromEntries(ivData.map((d) => [d.symbol, d.iv]));
};

const enrichPositionsWithIV = async (positionsList) => {
  try {
    const symbols = positionsList.map((pos) => pos.product_symbol).filter(Boolean);
    if (symbols.length === 0) return positionsList;

    const now = Date.now();
    const cacheAge = now - _ivCache.timestamp;

    if (cacheAge < IV_CACHE_TTL_MS && Object.keys(_ivCache.data).length > 0) {
      const uncachedSymbols = symbols.filter((s) => _ivCache.data[s] === undefined);

      if (uncachedSymbols.length === 0) {
        return positionsList.map((pos) => ({
          ...pos,
          iv: _ivCache.data[pos.product_symbol] ?? pos.iv ?? null,
        }));
      }

      const newIvData = await fetchIVForSymbols(uncachedSymbols);
      Object.assign(_ivCache.data, newIvData);

      return positionsList.map((pos) => ({
        ...pos,
        iv: _ivCache.data[pos.product_symbol] ?? pos.iv ?? null,
      }));
    }

    const ivMap = await fetchIVForSymbols(symbols);
    _ivCache.data = ivMap;
    _ivCache.timestamp = now;

    return positionsList.map((pos) => ({
      ...pos,
      iv: ivMap[pos.product_symbol] ?? null,
    }));
  } catch (err) {
    console.error('Failed to enrich positions with IV:', err);
    return positionsList;
  }
};

// Re-apply the most-recent WS tick for each position onto a freshly-fetched list.
//
// Why: REST fetches set unrealized_pnl from the exchange's mark price. WS ticks
// then update it from (bid+ask)/2. Without this, the two sources alternate every
// 5 seconds, causing P&L to visibly oscillate. By re-stamping the latest tick
// immediately after each REST update, the WS value always wins.
//
// For closed phantom rows: bid/ask/mid_price only — realized_pnl is never touched.
// For live rows: full applyTickerUpdate so the WS price takes precedence.
const applyLatestTicks = (positionsList, ticks) => {
  if (!ticks || Object.keys(ticks).length === 0) return positionsList;
  return positionsList.map((pos) => {
    const tick = ticks[pos.product_symbol];
    if (!tick) return pos;
    if (pos.is_closed) {
      const bid = tick.best_bid != null ? tick.best_bid : pos.best_bid;
      const ask = tick.best_ask != null ? tick.best_ask : pos.best_ask;
      const mid = (bid > 0 && ask > 0) ? (bid + ask) / 2 : (tick.mark_price || pos.mid_price);
      return { ...pos, best_bid: bid, best_ask: ask, mid_price: mid };
    }
    if (!pos.size) return pos;
    return applyTickerUpdate(pos, tick);
  });
};

/**
 * Custom hook for options position data fetching, polling, and WebSocket subscriptions.
 *
 * @param {Object} options
 * @param {number} options.pollInterval - Polling interval in ms
 * @returns {Object} positions data, fetchers, and controls
 */
export default function useOptionsPositions({ pollInterval = 5000 } = {}) {
  // ---- Core state ----
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [positions, setPositions] = useState([]);
  const [futuresPositions, setFuturesPositions] = useState([]);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [pendingOrders, setPendingOrders] = useState([]);
  const [pendingOrdersError, setPendingOrdersError] = useState(null);
  const [marginData, setMarginData] = useState(null);
  const [lastDataUpdate, setLastDataUpdate] = useState(Date.now());

  // ---- Refs ----
  const hasPositionsRef = useRef(false);
  const activeIntervalsRef = useRef([]);
  const socketRef = useRef(null);
  const subscribedSymbolsRef = useRef([]);
  const lastModifiedRef = useRef(null);
  const dashboardInFlightRef = useRef(false);
  const dashboardPendingRef = useRef(false);
  const positionsInFlightRef = useRef(false);
  const positionsPendingRef = useRef(false);
  const pendingOrdersInFlightRef = useRef(false);
  const pendingOrdersPendingRef = useRef(false);
  const feesInFlightRef = useRef(false);
  // Latest WS tick per symbol — keyed by product_symbol.
  // Used by applyLatestTicks() to re-stamp live prices after every REST update
  // so the WS value always wins over the exchange mark price in REST responses.
  const latestTicksRef = useRef({});

  // ---- Fetch functions ----
  const fetchDashboard = useCallback(async () => {
    if (dashboardInFlightRef.current) {
      dashboardPendingRef.current = true;
      return true;
    }

    dashboardInFlightRef.current = true;
    try {
      const { data } = await api.get('/api/options/dashboard');

      if (data?.success) {
        setWarmJSON('/api/options/dashboard', data, { ttlMs: 10000 });

        // Always update lastDataUpdate on a successful backend response,
        // even if data is unchanged (cached) — prevents false "STALE" warning
        // when exchange API is temporarily unavailable but backend is healthy.
        setLastDataUpdate(Date.now());

        if (data.last_modified && data.last_modified === lastModifiedRef.current) {
          return true;
        }
        lastModifiedRef.current = data.last_modified;

        const dashPositions = data.positions || [];
        const dashStatus = data.status || {};
        const dashPendingOrders = data.pending_orders || [];
        const dashFuturesPositions = data.futures_positions || [];

        // Show positions immediately WITHOUT waiting for IV enrichment.
        // Re-apply latest WS ticks so the WS mid price wins over the exchange
        // mark price that comes back in the REST response (prevents oscillation).
        setPositions(applyLatestTicks(dashPositions, latestTicksRef.current));
        setStatus(dashStatus);
        setPendingOrders(dashPendingOrders);
        setFuturesPositions(dashFuturesPositions);
        hasPositionsRef.current = dashPositions.length > 0;
        setError(null);
        setLastDataUpdate(Date.now());

        // Phase 6.2: Margin utilization data
        if (data.margin) {
          setMarginData(data.margin);
        }

        // Enrich IV in background (non-blocking).
        // Re-apply ticks again here — IV enrichment is async so a WS tick may
        // have arrived between the setPositions above and this callback.
        enrichPositionsWithIV(dashPositions).then((enriched) => {
          setPositions(applyLatestTicks(enriched, latestTicksRef.current));
        }).catch(() => { /* IV enrichment is best-effort */ });

        return true;
      } else {
        throw new Error(data?.error || 'Dashboard fetch failed');
      }
    } catch (err) {
      console.error('Unified dashboard fetch error:', err);
      if (hasPositionsRef.current) {
        setError(`⚠️ Dashboard refresh failed: ${err.message}`);
      } else {
        setError(`Connection error: ${err.message}`);
      }
      return false;
    } finally {
      dashboardInFlightRef.current = false;
      if (dashboardPendingRef.current) {
        dashboardPendingRef.current = false;
        Promise.resolve().then(() => {
          fetchDashboard();
        });
      }
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const { data } = await api.get('/api/options/status');
      if (data?.success) {
        // Always update lastDataUpdate on a successful backend response,
        // even if data is unchanged (cached) — prevents false "STALE" warning
        // when exchange API is temporarily unavailable but backend is healthy.
        setLastDataUpdate(Date.now());

        setStatus(data);
      }
    } catch (err) {
      console.error('Failed to fetch options status:', err);
    }
  }, []);

  const fetchPositions = useCallback(async () => {
    if (positionsInFlightRef.current) {
      positionsPendingRef.current = true;
      return;
    }

    positionsInFlightRef.current = true;
    try {
      const [optionsResponse, mvStraddleResponse] = await Promise.all([
        api.get('/api/options/positions'),
        api.get('/api/mv-straddle/positions').catch((err) => {
          console.warn('MV Straddle positions unavailable:', err.message);
          return { data: { success: false, positions: [] } };
        }),
      ]);

      const optionsData = optionsResponse?.data;
      const mvData = mvStraddleResponse?.data;

      if (optionsData?.success) {
        const rawOptionsPositions = optionsData.positions || [];
        const rawMVPositions = mvData?.success ? mvData.positions || [] : [];
        const combinedPositions = [...rawOptionsPositions, ...rawMVPositions];

        // Show positions immediately, enrich IV in background
        setPositions(combinedPositions);
        hasPositionsRef.current = combinedPositions.length > 0;

        enrichPositionsWithIV(combinedPositions).then((enriched) => {
          setPositions(enriched);
        }).catch(() => {});

        if (!optionsData.cached) {
          setError(null);
        } else if (optionsData.warning) {
          setError(`⚠️ ${optionsData.warning}`);
        }

        if (rawMVPositions.length > 0) {
          console.log(`📊 Loaded ${rawMVPositions.length} MV Straddle position(s)`);
        }
      } else {
        if (hasPositionsRef.current) {
          setError(`⚠️ Refresh failed: ${optionsData?.error || 'Unknown error'}`);
        } else {
          setError(optionsData?.error || 'Failed to fetch positions');
        }
      }
    } catch (err) {
      console.error('Failed to fetch options positions:', err);
      if (hasPositionsRef.current) {
        setError(`⚠️ Connection issue: ${err.message}`);
      } else {
        setError(`Connection error: ${err.message}`);
      }
    } finally {
      positionsInFlightRef.current = false;
      if (positionsPendingRef.current) {
        positionsPendingRef.current = false;
        Promise.resolve().then(() => {
          fetchPositions();
        });
      }
    }
  }, []);

  const fetchFuturesPositions = useCallback(async () => {
    try {
      const { data } = await api.get('/api/futures/positions');
      if (data?.success) {
        // Always update lastDataUpdate on a successful backend response,
        // even if data is unchanged (cached) — prevents false "STALE" warning
        // when exchange API is temporarily unavailable but backend is healthy.
        setLastDataUpdate(Date.now());

        setFuturesPositions(data.positions || []);
      }
    } catch (err) {
      console.error('Failed to fetch futures positions:', err);
    }
  }, []);

  const fetchPendingOrders = useCallback(async () => {
    if (pendingOrdersInFlightRef.current) {
      pendingOrdersPendingRef.current = true;
      return;
    }

    pendingOrdersInFlightRef.current = true;
    try {
      const { data } = await api.get('/api/positions/pending-orders');
      if (data?.success) {
        // Always update lastDataUpdate on a successful backend response,
        // even if data is unchanged (cached) — prevents false "STALE" warning
        // when exchange API is temporarily unavailable but backend is healthy.
        setLastDataUpdate(Date.now());

        setPendingOrders(data.orders || []);
        setPendingOrdersError(null);
      } else {
        setPendingOrdersError(data?.error || 'Failed to fetch pending orders');
      }
    } catch (err) {
      console.error('Failed to fetch pending orders:', err);
      setPendingOrdersError(err.message);
    } finally {
      pendingOrdersInFlightRef.current = false;
      if (pendingOrdersPendingRef.current) {
        pendingOrdersPendingRef.current = false;
        Promise.resolve().then(() => {
          fetchPendingOrders();
        });
      }
    }
  }, []);

  const handleCancelPendingOrder = useCallback(
    async (order) => {
      if (!window.confirm('Cancel this order?')) return;

      try {
        const { data } = await api.delete(`/api/options-chain/order/${order.id}/${order.product_id}`);
        if (data?.success) {
        // Always update lastDataUpdate on a successful backend response,
        // even if data is unchanged (cached) — prevents false "STALE" warning
        // when exchange API is temporarily unavailable but backend is healthy.
        setLastDataUpdate(Date.now());

          await fetchPendingOrders();
        } else {
          console.error('Failed to cancel order:', data?.error);
          alert(`Failed to cancel order: ${data?.error || 'Unknown error'}`);
        }
      } catch (err) {
        console.error('Failed to cancel order:', err);
        alert(`Failed to cancel order: ${err.message || 'Unknown error'}`);
      }
    },
    [fetchPendingOrders],
  );

  // ---- Manual refresh ----
  const handleRefresh = useCallback(async () => {
    const refreshStart = performance.now();
    setRefreshing(true);

    const success = await fetchDashboard();

    if (!success) {
      await Promise.all([fetchStatus(), fetchPositions(), fetchPendingOrders(), fetchFuturesPositions()]);
    }

    setRefreshing(false);
    const refreshTime = performance.now() - refreshStart;

    if (refreshTime > 200) {
      console.warn(`⚠️ Slow refresh: ${refreshTime.toFixed(2)}ms (target: <200ms)`);
    } else {
      console.log(`⚡ Fast refresh: ${refreshTime.toFixed(2)}ms (Phase 2 unified endpoint)`);
    }
  }, [fetchDashboard, fetchStatus, fetchPositions, fetchPendingOrders, fetchFuturesPositions]);

  // ---- Futures selection (cross-component via localStorage events) ----
  const [selectedFuturesState, setSelectedFuturesState] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('futures_selected_positions_payoff') || '[]');
    } catch {
      return [];
    }
  });

  useEffect(() => {
    const handleStorageChange = () => {
      try {
        const selectedFutures = JSON.parse(
          localStorage.getItem('futures_selected_positions_payoff') || '[]',
        );
        setSelectedFuturesState(selectedFutures);
      } catch {
        setSelectedFuturesState([]);
      }
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('futures_selected_changed', handleStorageChange);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('futures_selected_changed', handleStorageChange);
    };
  }, []);

  const visibleFuturesPositions = useMemo(() => {
    return futuresPositions.filter((pos) => selectedFuturesState.includes(pos.product_symbol));
  }, [futuresPositions, selectedFuturesState]);

  // ---- Initial load ----
  const initialLoadDone = useRef(false);

  useEffect(() => {
    if (initialLoadDone.current) return;
    initialLoadDone.current = true;

    // Safety timeout: never stay in loading state forever
    const safetyTimer = setTimeout(() => {
      setLoading((prev) => {
        if (prev) console.warn('⚠️ Loading safety timeout triggered after 8s');
        return false;
      });
    }, 8000);

    const loadData = async () => {
      setLoading(true);

      const warmedDashboard = readWarmJSON('/api/options/dashboard');
      if (warmedDashboard?.success) {
        const warmPositions = warmedDashboard.positions || [];
        const warmStatus = warmedDashboard.status || {};
        const warmPendingOrders = warmedDashboard.pending_orders || [];
        const warmFuturesPositions = warmedDashboard.futures_positions || [];

        setPositions(warmPositions);
        setStatus(warmStatus);
        setPendingOrders(warmPendingOrders);
        setFuturesPositions(warmFuturesPositions);
        setError(null);
        setLastDataUpdate(Date.now());
        hasPositionsRef.current = warmPositions.length > 0;

        if (warmedDashboard.margin) {
          setMarginData(warmedDashboard.margin);
        }

        setLoading(false);

        enrichPositionsWithIV(warmPositions)
          .then((enriched) => {
            setPositions(applyLatestTicks(enriched, latestTicksRef.current));
          })
          .catch(() => {
            // warm IV enrichment is best-effort
          });
      }

      const dashSuccess = await fetchDashboard();
      setLoading(false);
      clearTimeout(safetyTimer);

      if (!dashSuccess) {
        console.warn('⚠️ Unified dashboard endpoint failed, using legacy individual calls');
        await Promise.all([fetchStatus(), fetchPositions(), fetchPendingOrders(), fetchFuturesPositions()]);
      }
    };
    loadData();

    return () => clearTimeout(safetyTimer);
  }, [fetchDashboard, fetchStatus, fetchPositions, fetchPendingOrders, fetchFuturesPositions]);

  // ---- Polling ----
  useEffect(() => {
    const interval = setInterval(async () => {
      await fetchDashboard();
    }, pollInterval);
    return () => clearInterval(interval);
  }, [fetchDashboard, pollInterval]);

  // ---- WebSocket ----
  useEffect(() => {
    if (!socketRef.current) {
      socketRef.current = io({
        path: '/socket.io',
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 10,
      });

      socketRef.current.on('connect', () => {
        console.log('[useOptionsPositions] ⚡ Persistent WebSocket connected');
        // Re-subscribe after backend restart — subscribed_options is cleared on restart
        // positionSymbolsKey doesn't change on reconnect so the subscription useEffect
        // doesn't re-fire; use a ref to re-send the last known symbol list instead.
        if (subscribedSymbolsRef.current.length > 0) {
          socketRef.current.emit('subscribe_options_tickers', { symbols: subscribedSymbolsRef.current });
          console.log(`[useOptionsPositions] ⚡ Re-subscribed ${subscribedSymbolsRef.current.length} symbols after reconnect`);
        }
      });

      socketRef.current.on('options_ticker_update', (data) => {
        const { symbol } = data;
        // Always store the latest tick so applyLatestTicks() can re-apply it
        // after REST refreshes (prevents REST from overwriting WS mid price).
        latestTicksRef.current[symbol] = data;
        setPositions((prevPositions) =>
          prevPositions.map((pos) => {
            if (pos.product_symbol !== symbol) return pos;
            if (pos.is_closed) {
              // Closed phantom rows: update bid/ask/mid so the row shows live
              // market prices. Do NOT touch realized_pnl or unrealized_pnl.
              const bid = data.best_bid != null ? data.best_bid : pos.best_bid;
              const ask = data.best_ask != null ? data.best_ask : pos.best_ask;
              const mid = (bid > 0 && ask > 0) ? (bid + ask) / 2 : (data.mark_price || pos.mid_price);
              return { ...pos, best_bid: bid, best_ask: ask, mid_price: mid };
            }
            if (!pos.size) return pos;
            return applyTickerUpdate(pos, data);
          }),
        );
      });

      // order_filled: a limit order was filled — refresh pending orders + positions
      socketRef.current.on('order_filled', (data) => {
        console.log('[useOptionsPositions] ⚡ Order filled:', data.symbol);
        fetchPendingOrders();
        // Use fetchDashboard (not fetchPositions) — dashboard includes phantom closed
        // positions from the server store. fetchPositions only returns live positions,
        // which would strip phantom rows and cause them to flicker off then reappear.
        setTimeout(() => fetchDashboard(), 500);
      });

      // pending_orders_updated: any order state change (placed, cancelled)
      socketRef.current.on('pending_orders_updated', () => {
        fetchPendingOrders();
      });

      // positions_updated: position changed (size, entry price, etc.)
      socketRef.current.on('positions_updated', () => {
        // Use fetchDashboard to keep phantom closed positions in the state.
        fetchDashboard();
      });

      socketRef.current.on('disconnect', () => {
        console.log('[useOptionsPositions] WebSocket disconnected (will auto-reconnect)');
      });

      socketRef.current.on('connect_error', (error) => {
        console.error('[useOptionsPositions] WebSocket connection error:', error);
      });
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, []);

  // Update subscriptions when positions change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const positionSymbolsKey = positions.map((p) => p.product_symbol).join(',');
  useEffect(() => {
    if (!socketRef.current || positions.length === 0) return;

    const symbols = positions.map((p) => p.product_symbol);
    subscribedSymbolsRef.current = symbols;

    if (socketRef.current.connected) {
      socketRef.current.emit('subscribe_options_tickers', { symbols });
      console.log(`[useOptionsPositions] ⚡ Updated ${symbols.length} subscriptions`);
    } else {
      const onConnect = () => {
        socketRef.current.emit('subscribe_options_tickers', { symbols });
        socketRef.current.off('connect', onConnect);
      };
      socketRef.current.on('connect', onConnect);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positionSymbolsKey]);

  // Cleanup active batch polling intervals on unmount
  useEffect(() => {
    return () => {
      activeIntervalsRef.current.forEach(clearInterval);
      activeIntervalsRef.current = [];
    };
  }, []);

  // ---- Exchange fees per options symbol ----
  // { "C-BTC-95000-300425": 1.23, ... }  — polled every 60s (fees change only on fills)
  const [feesMap, setFeesMap] = useState({});

  const fetchFees = useCallback(async () => {
    if (feesInFlightRef.current) {
      return;
    }

    feesInFlightRef.current = true;
    try {
      const { data } = await api.get('/api/options/fees-summary');
      if (data?.success && data.fees) {
        setFeesMap(data.fees);
      }
    } catch (err) {
      // Non-critical — fees column just shows nothing if unavailable
      console.warn('[useOptionsPositions] fees-summary fetch failed:', err.message);
    } finally {
      feesInFlightRef.current = false;
    }
  }, []);

  // Fetch fees once on mount, then every 60s
  useEffect(() => {
    fetchFees();
    const id = setInterval(fetchFees, 60000);
    return () => clearInterval(id);
  }, [fetchFees]);

  return {
    // State
    positions,
    setPositions,
    futuresPositions,
    visibleFuturesPositions,
    status,
    loading,
    refreshing,
    error,
    setError,
    pendingOrders,
    pendingOrdersError,
    marginData,
    lastDataUpdate,
    feesMap,

    // Fetchers
    fetchDashboard,
    fetchStatus,
    fetchPositions,
    fetchFuturesPositions,
    fetchPendingOrders,
    handleCancelPendingOrder,
    handleRefresh,

    // Refs (for external code that needs them)
    hasPositionsRef,
    activeIntervalsRef,
  };
}
