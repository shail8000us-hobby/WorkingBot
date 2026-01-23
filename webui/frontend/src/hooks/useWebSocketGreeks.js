/**
 * WebSocket hook for real-time Greeks updates
 * 
 * Connects to Delta Exchange WebSocket API to receive live Greeks data
 * for option positions. Falls back gracefully if WebSocket unavailable.
 * 
 * Created: January 24, 2026 - Day 5 (Optional)
 * Part of Phase 1 Quick Wins
 */

import { useEffect, useState, useCallback, useRef } from 'react';

/**
 * Custom hook for WebSocket Greeks updates
 * 
 * @param {string[]} symbols - Array of option symbols to subscribe to
 * @param {boolean} enabled - Whether WebSocket should be active
 * @returns {Object} { greeksData, connected, error }
 */
export function useWebSocketGreeks(symbols = [], enabled = false) {
  const [greeksData, setGreeksData] = useState({});
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const updateThrottleRef = useRef({});

  // Throttle updates to max 1/second per symbol
  const throttledUpdate = useCallback((symbol, data) => {
    const now = Date.now();
    const lastUpdate = updateThrottleRef.current[symbol] || 0;
    
    if (now - lastUpdate > 1000) {
      setGreeksData(prev => ({
        ...prev,
        [symbol]: {
          ...data,
          timestamp: now
        }
      }));
      updateThrottleRef.current[symbol] = now;
    }
  }, []);

  const connect = useCallback(() => {
    if (!enabled || symbols.length === 0) return;

    try {
      // Delta Exchange India WebSocket endpoint
      const ws = new WebSocket('wss://socket.india.delta.exchange');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('🟢 WebSocket connected to Delta Exchange');
        setConnected(true);
        setError(null);

        // Subscribe to v2/ticker channel for Greeks
        ws.send(JSON.stringify({
          type: 'subscribe',
          payload: {
            channels: [{
              name: 'v2/ticker',
              symbols: symbols
            }]
          }
        }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle ticker updates with Greeks
          if (data.type === 'v2/ticker' && data.greeks) {
            const greeks = {
              delta: parseFloat(data.greeks.delta) || 0,
              gamma: parseFloat(data.greeks.gamma) || 0,
              theta: parseFloat(data.greeks.theta) || 0,
              vega: parseFloat(data.greeks.vega) || 0,
              rho: parseFloat(data.greeks.rho) || 0,
            };

            throttledUpdate(data.symbol, greeks);
          }
        } catch (err) {
          console.error('WebSocket message parse error:', err);
        }
      };

      ws.onerror = (err) => {
        console.error('🔴 WebSocket error:', err);
        setError('WebSocket connection error');
      };

      ws.onclose = (event) => {
        console.log('🟡 WebSocket disconnected:', event.code, event.reason);
        setConnected(false);

        // Auto-reconnect after 5 seconds if not intentional close
        if (enabled && event.code !== 1000) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('🔄 Reconnecting WebSocket...');
            connect();
          }, 5000);
        }
      };
    } catch (err) {
      console.error('Failed to create WebSocket connection:', err);
      setError(err.message);
    }
  }, [symbols, enabled, throttledUpdate]);

  // Connect/disconnect based on enabled flag
  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted');
        wsRef.current = null;
      }
    };
  }, [connect, enabled]);

  return {
    greeksData,
    connected,
    error
  };
}

/**
 * Example usage in OptionsPanel:
 * 
 * const symbols = positions.map(p => p.product_symbol);
 * const { greeksData, connected } = useWebSocketGreeks(symbols, true);
 * 
 * // Merge WebSocket Greeks with position data
 * const positionsWithLiveGreeks = positions.map(pos => ({
 *   ...pos,
 *   greeks: greeksData[pos.product_symbol] || pos.greeks
 * }));
 * 
 * // Show connection status
 * {connected && <Chip label="Live" color="success" size="small" />}
 */

export default useWebSocketGreeks;
