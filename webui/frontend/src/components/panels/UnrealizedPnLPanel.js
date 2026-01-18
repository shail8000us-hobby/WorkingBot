import React, { useState, useEffect, useCallback } from 'react';
import PnLChart from '../charts/PnLChart';
import robustApiClient from '../../utils/robustApiClient';

/**
 * Parse PnL history data from API response
 */
function parsePnLHistory(payload) {
  const history = Array.isArray(payload) ? payload : payload?.history || [];
  return history.map((entry) => {
    const timestamp = entry.timestamp || entry.time || entry.datetime || entry.label || entry.date;
    let timestampMs;

    if (timestamp) {
      const date = new Date(timestamp);
      if (!Number.isNaN(date.getTime())) {
        timestampMs = date.getTime();
      }
    }

    // Use total_pnl (correct unrealized PnL in INR) instead of unrealized_pnl field
    const pnlRaw = Number(entry.total_pnl ?? entry.pnl ?? entry.upnl ?? entry.value ?? 0);

    return {
      timestamp: timestampMs || Date.now(),
      pnl: Number.isFinite(pnlRaw) ? Number(pnlRaw.toFixed(2)) : 0,
    };
  });
}

/**
 * UnrealizedPnLPanel
 *
 * Container component for the Unrealized PnL Trend chart.
 * Handles data fetching, parsing, and state management for hourly PnL history.
 *
 * Features:
 * - Fetches hourly PnL data from /api/pnl-history/hourly
 * - Auto-refreshes when socket updates are received
 * - Displays last 120 data points (2 hours at 1-minute intervals)
 */
function UnrealizedPnLPanel({ socket }) {
  const [pnlHistory, setPnlHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [meta, setMeta] = useState(null);

  const loadPnLHistory = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const pnlData = await robustApiClient
        .get('/api/pnl-history/hourly')
        .catch(() => ({ history: [], meta: null }));
      setPnlHistory(parsePnLHistory(pnlData));
      setMeta(pnlData.meta || null);
    } catch (err) {
      console.warn('PnL history load error:', err);
      setError(err.message);
      setPnlHistory([]);
      setMeta(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadPnLHistory();
  }, [loadPnLHistory]);

  // Listen for socket updates to refresh PnL data
  useEffect(() => {
    if (!socket) return;

    const handlePnLUpdate = (data) => {
      if (data?.history) {
        setPnlHistory(parsePnLHistory(data));
        setMeta(data.meta || null);
      }
    };

    socket.on('pnl_update', handlePnLUpdate);
    socket.on('bot_status', loadPnLHistory); // Reload when bot status changes

    return () => {
      socket.off('pnl_update', handlePnLUpdate);
      socket.off('bot_status', loadPnLHistory);
    };
  }, [socket, loadPnLHistory]);

  if (error) {
    return (
      <div className="h-52 sm:h-64 flex items-center justify-center">
        <div className="text-center text-red-400 px-4">
          <div className="text-sm font-medium">Failed to load PnL data</div>
          <div className="text-xs mt-2">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <>
      {meta && !meta.guardian_running && pnlHistory.length > 0 && (
        <div className="mb-3 px-4 py-2 bg-amber-500/10 border border-amber-500/30 rounded-lg">
          <div className="flex items-center gap-2 text-xs text-amber-400">
            <span className="text-base">⚠️</span>
            <span>
              Guardian not running. Showing historical data from{' '}
              {new Date(meta.last_update).toLocaleString('en-IN')}
            </span>
          </div>
        </div>
      )}
      <PnLChart data={pnlHistory} loading={loading} />
    </>
  );
}

export default UnrealizedPnLPanel;
