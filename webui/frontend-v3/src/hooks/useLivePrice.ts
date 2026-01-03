/**
 * useLivePrice Hook
 * 
 * Real-time price updates via WebSocket.
 * Falls back to polling if WebSocket is unavailable.
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useWebSocketMessage, useWebSocketStatus } from './useWebSocket';

export interface LivePriceData {
  /** Current price */
  price: number;
  /** 24h change percentage */
  change24h?: number;
  /** 24h high */
  high24h?: number;
  /** 24h low */
  low24h?: number;
  /** Last update timestamp */
  timestamp: number;
  /** Price source */
  source?: 'websocket' | 'polling';
}

export interface UseLivePriceOptions {
  /** Symbol to track (e.g., 'BTCUSD') */
  symbol?: string;
  /** Polling interval in ms (fallback) */
  pollInterval?: number;
  /** Enable polling fallback */
  enablePolling?: boolean;
}

export interface UseLivePriceReturn {
  /** Current price data */
  data: LivePriceData | null;
  /** Whether we have data */
  hasData: boolean;
  /** Loading state */
  isLoading: boolean;
  /** Error if any */
  error: Error | null;
  /** Last update timestamp */
  lastUpdate: number | null;
}

export function useLivePrice(options: UseLivePriceOptions = {}): UseLivePriceReturn {
  const { 
    symbol = 'BTCUSD', 
    pollInterval = 5000,
    enablePolling = true,
  } = options;
  
  const [data, setData] = useState<LivePriceData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const wsStatus = useWebSocketStatus();
  
  // Track last WS update for fallback logic
  const lastWsUpdate = useRef<number>(0);
  
  // Handle WebSocket price updates
  useWebSocketMessage<{
    symbol: string;
    price: number;
    change_24h?: number;
    high_24h?: number;
    low_24h?: number;
    timestamp?: number;
  }>('price_update', (priceData) => {
    if (priceData.symbol === symbol || !priceData.symbol) {
      lastWsUpdate.current = Date.now();
      setData({
        price: priceData.price,
        change24h: priceData.change_24h,
        high24h: priceData.high_24h,
        low24h: priceData.low_24h,
        timestamp: priceData.timestamp ?? Date.now(),
        source: 'websocket',
      });
      setIsLoading(false);
      setError(null);
    }
  });
  
  // Polling fallback
  useEffect(() => {
    if (!enablePolling) return;
    
    // Only poll if WS is not connected or hasn't updated recently
    const shouldPoll = wsStatus !== 'connected' || 
      (Date.now() - lastWsUpdate.current > pollInterval * 2);
    
    if (!shouldPoll && data) return;
    
    const fetchPrice = async () => {
      try {
        // Use the trading status endpoint which includes current price
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/trading_status`
        );
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        
        const result = await response.json();
        
        // Only update if WS hasn't updated recently
        if (Date.now() - lastWsUpdate.current > pollInterval) {
          setData({
            price: result.current_price ?? result.last_price ?? 0,
            timestamp: Date.now(),
            source: 'polling',
          });
          setIsLoading(false);
        }
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to fetch price'));
        setIsLoading(false);
      }
    };
    
    // Initial fetch
    if (!data) {
      fetchPrice();
    }
    
    // Set up polling interval
    const interval = setInterval(fetchPrice, pollInterval);
    
    return () => clearInterval(interval);
  }, [wsStatus, enablePolling, pollInterval, data, symbol]);
  
  return {
    data,
    hasData: data !== null,
    isLoading,
    error,
    lastUpdate: data?.timestamp ?? null,
  };
}

export default useLivePrice;
