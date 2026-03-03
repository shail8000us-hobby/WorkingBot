/**
 * useLatencyTracker — tracks WebSocket latency samples and computes a rolling average.
 * Extracted from App.js (Phase 2.4).
 *
 * Returns { latencyStats, pushLatencySample }.
 * - latencyStats: { avg: number|null, history: Array<{time, latency}> }
 * - pushLatencySample(latencyMs): adds a sample, recomputes avg over last 60 entries
 */

import { useState, useRef, useCallback } from 'react';

export function useLatencyTracker() {
  const [latencyStats, setLatencyStats] = useState({ avg: null, history: [] });
  const latencyBufferRef = useRef([]);

  const pushLatencySample = useCallback((latencyMs) => {
    if (latencyMs === null || latencyMs === undefined) return;

    const sample = {
      time: new Date().toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }),
      latency: Math.round(latencyMs),
    };
    latencyBufferRef.current = [...latencyBufferRef.current.slice(-59), sample];
    const avg = Math.round(
      latencyBufferRef.current.reduce((acc, item) => acc + Number(item.latency || 0), 0) /
      Math.max(latencyBufferRef.current.length, 1)
    );
    setLatencyStats({ history: latencyBufferRef.current, avg });
  }, []);

  return { latencyStats, pushLatencySample };
}
