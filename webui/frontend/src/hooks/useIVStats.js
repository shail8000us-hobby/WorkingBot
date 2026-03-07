/**
 * useIVStats  (Feature 2 — IV Rank / IV Percentile)
 * ====================================================
 * Polls GET /api/options/iv-stats every 60 seconds.
 * Returns stable empty object on error.
 *
 * Returns:
 *   ivStats: { [symbol]: { ivr, ivp, high_52w, low_52w, current_iv_pct, days_available } }
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const POLL_INTERVAL_MS = 60_000;
const ENDPOINT = '/api/options/iv-stats';

export default function useIVStats() {
  const [ivStats, setIvStats] = useState({});
  const [loading, setLoading] = useState(false);
  const timerRef = useRef(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await window.fetch(ENDPOINT);
      if (!res.ok) return;
      const data = await res.json();
      if (data.success) setIvStats(data.iv_stats || {});
    } catch (_) {
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    timerRef.current = setInterval(fetch, POLL_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [fetch]);

  return { ivStats, loading, refetch: fetch };
}
