/**
 * usePositionGreeks
 * =================
 * Fetches per-position Black-Scholes Greeks and expiry subtotals
 * from GET /api/options/position-greeks  (Feature 3).
 *
 * Polls every 30 seconds — Greeks change slowly (only as IV / DTE change).
 * Returns a stable empty object on error so callers don't crash.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const POLL_INTERVAL_MS = 30_000;
const ENDPOINT = '/api/options/position-greeks';

export default function usePositionGreeks(btcSpot = 0) {
  const [positionGreeks, setPositionGreeks] = useState({});
  const [expirySubtotals, setExpirySubtotals] = useState({});
  const [loading, setLoading] = useState(false);
  const timerRef = useRef(null);
  const spotRef = useRef(btcSpot);
  const inFlightRef = useRef(false);
  const pendingRef = useRef(false);

  // Keep ref current without triggering re-renders / effect re-runs
  spotRef.current = btcSpot;

  const fetchGreeks = useCallback(async () => {
    if (inFlightRef.current) {
      pendingRef.current = true;
      return;
    }

    inFlightRef.current = true;
    setLoading(true);
    try {
      const spot = spotRef.current;
      const params = spot > 0 ? `?spot=${spot}` : '';
      const res = await window.fetch(`${ENDPOINT}${params}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.success) {
        setPositionGreeks(data.position_greeks || {});
        setExpirySubtotals(data.expiry_subtotals || {});
      }
    } catch (_) {
      // Silently ignore — non-critical data
    } finally {
      setLoading(false);
      inFlightRef.current = false;
      if (pendingRef.current) {
        pendingRef.current = false;
        Promise.resolve().then(() => {
          fetchGreeks();
        });
      }
    }
  }, []); // stable — no deps that change

  useEffect(() => {
    fetchGreeks();
    timerRef.current = setInterval(fetchGreeks, POLL_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [fetchGreeks]);

  return { positionGreeks, expirySubtotals, loading, refetch: fetchGreeks };
}
