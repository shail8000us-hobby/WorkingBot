/**
 * useMarketPrices Hook
 *
 * Subscribe to real-time BTC and ETH prices via WebSocket
 * Falls back to REST API polling if WebSocket is unavailable
 *
 * Created: January 18, 2026
 */

import { useState, useEffect, useRef } from 'react';
import { io } from 'socket.io-client';

const POLLING_INTERVAL = 5000; // 5 seconds fallback polling

export const useMarketPrices = () => {
  const [btcPrice, setBtcPrice] = useState(null);
  const [ethPrice, setEthPrice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState('unknown'); // 'websocket', 'rest', or 'unknown'
  const [wsConnected, setWsConnected] = useState(false);

  const socketRef = useRef(null);
  const pollingIntervalRef = useRef(null);

  // Fetch prices via REST API (fallback)
  const fetchPricesREST = async () => {
    try {
      const cacheBuster = Date.now();

      const [btcRes, ethRes] = await Promise.all([
        fetch(`/api/market/spot-price?symbol=BTC&_=${cacheBuster}`),
        fetch(`/api/market/spot-price?symbol=ETH&_=${cacheBuster}`),
      ]);

      if (btcRes.ok) {
        const btcData = await btcRes.json();
        if (btcData.price) {
          setBtcPrice(btcData.price);
        }
      }

      if (ethRes.ok) {
        const ethData = await ethRes.json();
        if (ethData.price) {
          setEthPrice(ethData.price);
        }
      }

      setLoading(false);
      setSource('rest');
    } catch (error) {
      console.error('[useMarketPrices] REST fetch error:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    // Initialize Socket.IO connection
    const socket = io({
      path: '/socket.io',
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 10,
    });

    socketRef.current = socket;

    // Socket.IO event handlers
    socket.on('connect', () => {
      console.log('[useMarketPrices] WebSocket connected');
      setWsConnected(true);
      setSource('websocket');

      // Clear REST polling if active
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }

      // Request initial prices
      fetchPricesREST();
    });

    socket.on('disconnect', () => {
      console.log('[useMarketPrices] WebSocket disconnected');
      setWsConnected(false);
      setSource('rest');

      // Start REST polling as fallback
      if (!pollingIntervalRef.current) {
        pollingIntervalRef.current = setInterval(fetchPricesREST, POLLING_INTERVAL);
      }
    });

    socket.on('market_price_update', (data) => {
      const { symbol, price, timestamp } = data;

      if (symbol === 'BTC' && price) {
        setBtcPrice(price);
        console.log(`[useMarketPrices] BTC: $${price.toLocaleString()}`);
      } else if (symbol === 'ETH' && price) {
        setEthPrice(price);
        console.log(`[useMarketPrices] ETH: $${price.toLocaleString()}`);
      }

      setLoading(false);
      setSource('websocket');
    });

    socket.on('connect_error', (error) => {
      console.error('[useMarketPrices] Connection error:', error);
      setWsConnected(false);

      // Start REST polling as fallback
      if (!pollingIntervalRef.current) {
        pollingIntervalRef.current = setInterval(fetchPricesREST, POLLING_INTERVAL);
      }
    });

    // Initial fetch
    fetchPricesREST();

    // Cleanup
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  return {
    btcPrice,
    ethPrice,
    loading,
    source,
    wsConnected,
    refresh: fetchPricesREST,
  };
};

export default useMarketPrices;
