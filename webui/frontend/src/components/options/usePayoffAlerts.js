/**
 * usePayoffAlerts — Custom hook for Payoff Alert management
 *
 * Extracted from OptionsPayoffDiagram.js (D3) to separate alert state
 * and CRUD operations from the chart rendering component.
 *
 * @version 1.0.0
 */

import { useState, useCallback, useEffect, useMemo } from 'react';

/**
 * Manage alert state, fetch, filter, and dialog interaction.
 *
 * @param {Object|null} chartData - Chart data containing nearestExpiry
 * @returns {Object} Alert state + event handlers
 */
const usePayoffAlerts = (chartData) => {
  // Alert creation state (from chart click)
  const [alertDialogOpen, setAlertDialogOpen] = useState(false);
  const [alertPrice, setAlertPrice] = useState(null);
  const [alertPnLExpiry, setAlertPnLExpiry] = useState(null);
  const [alertPnLTarget, setAlertPnLTarget] = useState(null);
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [alertsRefreshTrigger, setAlertsRefreshTrigger] = useState(0);

  // Fetch all alerts
  const fetchAlerts = useCallback(async () => {
    try {
      const response = await fetch('/api/alerts');
      const data = await response.json();
      if (data.success) {
        setActiveAlerts(data.alerts || []);
      }
    } catch (err) {
      console.error('Failed to fetch alerts:', err);
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts, alertsRefreshTrigger]);

  // Current expiry string for filtering
  const currentExpiryStr = useMemo(() =>
    chartData?.nearestExpiry ? new Date(chartData.nearestExpiry).toISOString().split('T')[0] : null
  , [chartData?.nearestExpiry]);

  // Filtered alerts for this expiry view
  const filteredAlerts = useMemo(() => {
    if (!currentExpiryStr) return activeAlerts.filter(a => a.status === 'active');
    return activeAlerts.filter(a =>
      a.status === 'active' && (a.expiry_date === currentExpiryStr || !a.expiry_date)
    );
  }, [activeAlerts, currentExpiryStr]);

  // Open alert dialog from chart click
  const openAlertDialog = useCallback((payload) => {
    if (payload) {
      setAlertPrice(payload.price);
      setAlertPnLExpiry(payload.expiry || 0);
      setAlertPnLTarget(payload.target || 0);
      setAlertDialogOpen(true);
    }
  }, []);

  // Close alert dialog
  const closeAlertDialog = useCallback(() => {
    setAlertDialogOpen(false);
  }, []);

  // Trigger refresh after alert creation
  const onAlertCreated = useCallback(() => {
    setAlertsRefreshTrigger((prev) => prev + 1);
  }, []);

  const expiryDateStr = chartData?.nearestExpiry
    ? new Date(chartData.nearestExpiry).toISOString().split('T')[0]
    : null;

  return {
    // Dialog state
    alertDialogOpen,
    alertPrice,
    setAlertPrice,
    alertPnLExpiry,
    alertPnLTarget,
    // Alert data
    activeAlerts,
    filteredAlerts,
    expiryDateStr,
    // Actions
    fetchAlerts,
    openAlertDialog,
    closeAlertDialog,
    onAlertCreated,
  };
};

export default usePayoffAlerts;
