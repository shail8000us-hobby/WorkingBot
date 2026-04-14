import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, Typography, Box, Chip, LinearProgress, Alert } from '@mui/material';
import {
  CheckCircle,
  Warning,
  TrendingUp,
  TrendingDown,
  Security,
  Speed,
  BugReport,
  Psychology,
} from '@mui/icons-material';
import { useInstanceAPI } from '../hooks/useInstanceAPI';
import { useInstance, parseInstanceName } from '../context/InstanceContext';
import SymbolBadge from './common/SymbolBadge';
import { readWarmJSON, setWarmJSON } from '../utils/dataWarmCache';

const MonitoringDashboard = () => {
  const api = useInstanceAPI();
  const fetchJSON = api.fetchJSON;
  const { selectedInstance } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const selectedSymbol = instanceInfo?.symbol; // backward compat
  const [monitoringStatus, setMonitoringStatus] = useState(null);
  const [priceHealth, setPriceHealth] = useState(null);
  const [preOrderStats, setPreOrderStats] = useState(null);
  const [tpVerification, setTpVerification] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [predictiveMap, setPredictiveMap] = useState(null);
  const [advancedPredictions, setAdvancedPredictions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const dataInFlightRef = useRef(false);
  const dataPendingRef = useRef(false);

  useEffect(() => {
    const cachedStatus = readWarmJSON('/api/monitoring/status', {
      includeSelectedInstance: true,
    });

    if (!cachedStatus) {
      return;
    }

    setMonitoringStatus(cachedStatus);

    if (!cachedStatus.monitoring_active) {
      setLoading(false);
      setError(null);
      return;
    }

    let hydratedAny = false;

    const cachedHealth = readWarmJSON('/api/monitoring/price-health', {
      includeSelectedInstance: true,
    });
    if (cachedHealth) {
      setPriceHealth(cachedHealth);
      hydratedAny = true;
    }

    const cachedStats = readWarmJSON('/api/monitoring/pre-order-stats', {
      includeSelectedInstance: true,
    });
    if (cachedStats) {
      setPreOrderStats(cachedStats);
      hydratedAny = true;
    }

    const cachedTP = readWarmJSON('/api/monitoring/tp-verification', {
      includeSelectedInstance: true,
    });
    if (cachedTP) {
      setTpVerification(cachedTP);
      hydratedAny = true;
    }

    const cachedAnomalies = readWarmJSON('/api/monitoring/anomalies', {
      includeSelectedInstance: true,
    });
    if (cachedAnomalies) {
      setAnomalies(cachedAnomalies.anomaly_list || cachedAnomalies.anomalies || []);
      hydratedAny = true;
    }

    const cachedPredictiveMap = readWarmJSON('/api/monitoring/predictive-map', {
      includeSelectedInstance: true,
    });
    if (cachedPredictiveMap) {
      setPredictiveMap(cachedPredictiveMap);
      hydratedAny = true;
    }

    const cachedAdvancedPredictions = readWarmJSON('/api/monitoring/advanced-predictions', {
      includeSelectedInstance: true,
    });
    if (cachedAdvancedPredictions) {
      setAdvancedPredictions(cachedAdvancedPredictions);
      hydratedAny = true;
    }

    if (hydratedAny) {
      setLoading(false);
      setError(null);
    }
  }, [selectedInstance]);

  // Fetch monitoring status
  const fetchMonitoringStatus = useCallback(async () => {
    try {
      const data = await fetchJSON('/api/monitoring/status');
      setMonitoringStatus(data);
      setWarmJSON('/api/monitoring/status', data, {
        includeSelectedInstance: true,
        ttlMs: 12000,
      });
      return data.monitoring_active;
    } catch (err) {
      console.error('Failed to fetch monitoring status:', err);
      setError('Failed to connect to monitoring system');
      return false;
    }
  }, [fetchJSON]);

  // Fetch all monitoring data
  const fetchMonitoringData = useCallback(async () => {
    if (dataInFlightRef.current) {
      dataPendingRef.current = true;
      return;
    }

    dataInFlightRef.current = true;
    try {
      setLoading(true);
      setError(null);

      // Check if monitoring is active
      const isActive = await fetchMonitoringStatus();

      if (!isActive) {
        return;
      }

      // Fetch all endpoints in parallel (including new advanced predictions)
      const [health, stats, tp, anom, map, advPred] = await Promise.all([
        fetchJSON('/api/monitoring/price-health'),
        fetchJSON('/api/monitoring/pre-order-stats'),
        fetchJSON('/api/monitoring/tp-verification'),
        fetchJSON('/api/monitoring/anomalies'),
        fetchJSON('/api/monitoring/predictive-map'),
        fetchJSON('/api/monitoring/advanced-predictions'),
      ]);

      setPriceHealth(health);
      setPreOrderStats(stats);
      setTpVerification(tp);
      setAnomalies(anom.anomaly_list || anom.anomalies || []);
      setPredictiveMap(map);
      setAdvancedPredictions(advPred);

      setWarmJSON('/api/monitoring/price-health', health, {
        includeSelectedInstance: true,
        ttlMs: 12000,
      });
      setWarmJSON('/api/monitoring/pre-order-stats', stats, {
        includeSelectedInstance: true,
        ttlMs: 12000,
      });
      setWarmJSON('/api/monitoring/tp-verification', tp, {
        includeSelectedInstance: true,
        ttlMs: 12000,
      });
      setWarmJSON('/api/monitoring/anomalies', anom, {
        includeSelectedInstance: true,
        ttlMs: 12000,
      });
      setWarmJSON('/api/monitoring/predictive-map', map, {
        includeSelectedInstance: true,
        ttlMs: 12000,
      });
      setWarmJSON('/api/monitoring/advanced-predictions', advPred, {
        includeSelectedInstance: true,
        ttlMs: 12000,
      });
    } catch (err) {
      console.error('Error fetching monitoring data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
      dataInFlightRef.current = false;
      if (dataPendingRef.current) {
        dataPendingRef.current = false;
        Promise.resolve().then(() => {
          fetchMonitoringData();
        });
      }
    }
  }, [fetchJSON, fetchMonitoringStatus]);

  // Initial fetch and polling
  // Auto-refresh on mount and symbol change
  useEffect(() => {
    fetchMonitoringData();
    const interval = setInterval(fetchMonitoringData, 30000); // Poll every 30s for faster updates
    return () => clearInterval(interval);
  }, [selectedSymbol, fetchMonitoringData]);

  if (loading && !monitoringStatus) {
    return (
      <Box sx={{ p: 2 }}>
        <LinearProgress />
        <Typography variant="body2" sx={{ mt: 2, color: 'text.secondary' }}>
          Loading monitoring data...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        Monitoring Error: {error}
      </Alert>
    );
  }

  const isActive = monitoringStatus?.monitoring_active;

  return (
    <Box sx={{ p: 0 }}>
      {!isActive && (
        <Alert severity="info" sx={{ mb: 3 }}>
          Monitoring is available when the bot is running. Start the bot to see live monitoring
          data.
        </Alert>
      )}

      {/* Main Layout: Left half (4 compact panels), Right half (Predictive Map) */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1.2fr' }, gap: 2 }}>
        {/* LEFT HALF - 4 compact monitoring panels in 2x2 grid */}
        <Box sx={{ display: 'grid', gridTemplateRows: 'auto auto', gap: 2, alignContent: 'start' }}>
          {/* Row 1: Price Health + Pre-Order Stats */}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' },
              gap: 2,
            }}
          >
            {/* Price Health Card */}
            <Card sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Security sx={{ color: 'primary.main', mr: 1 }} />
                  <Typography variant="h6" sx={{ fontSize: '0.95rem', fontWeight: 600 }}>
                    Price Health
                  </Typography>
                  <Box sx={{ ml: 'auto' }}>
                    <SymbolBadge symbol={selectedSymbol} size="xs" variant="dot" />
                  </Box>
                </Box>
                {priceHealth && !priceHealth.error ? (
                  <>
                    <Box sx={{ textAlign: 'center', mb: 2 }}>
                      <Chip
                        icon={
                          priceHealth.is_fresh || priceHealth.fresh ? <CheckCircle /> : <Warning />
                        }
                        label={
                          priceHealth.status ||
                          (priceHealth.is_fresh || priceHealth.fresh ? 'Fresh' : 'Stale')
                        }
                        color={priceHealth.is_fresh || priceHealth.fresh ? 'success' : 'warning'}
                        sx={{ fontWeight: 600 }}
                      />
                    </Box>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">
                          Age:
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                          {priceHealth.price_age_seconds?.toFixed(1) ||
                            priceHealth.age_seconds?.toFixed(1) ||
                            'N/A'}
                          s
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">
                          Source:
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                          {priceHealth.source || 'N/A'}
                        </Typography>
                      </Box>
                      {priceHealth.price && (
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                          <Typography variant="body2" color="text.secondary">
                            Price:
                          </Typography>
                          <Typography variant="body2" fontWeight={600}>
                            ${priceHealth.price?.toLocaleString()}
                          </Typography>
                        </Box>
                      )}
                      {(priceHealth.last_update || priceHealth.timestamp) && (
                        <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                          Updated:{' '}
                          {new Date(
                            priceHealth.last_update || priceHealth.timestamp
                          ).toLocaleTimeString()}
                        </Typography>
                      )}
                    </Box>
                  </>
                ) : (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ textAlign: 'center', py: 3 }}
                  >
                    {priceHealth?.error || 'Price monitor unavailable'}
                  </Typography>
                )}
              </CardContent>
            </Card>

            {/* Pre-Order Stats Card */}
            <Card sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <TrendingUp sx={{ color: 'success.main', mr: 1 }} />
                  <Typography variant="h6" sx={{ fontSize: '0.95rem', fontWeight: 600 }}>
                    Pre-Order Statistics
                  </Typography>
                </Box>
                {preOrderStats && !preOrderStats.error ? (
                  <>
                    <Box sx={{ textAlign: 'center', mb: 2 }}>
                      <Typography variant="h3" color="primary.main" fontWeight={700}>
                        {preOrderStats.approval_rate?.toFixed(1) || '0.0'}%
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Approval Rate
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="success.main">
                          ✓ Approved:
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                          {preOrderStats.approved || 0}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="error.main">
                          ✗ Rejected:
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                          {preOrderStats.rejected || 0}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">
                          Total:
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                          {preOrderStats.total_decisions || preOrderStats.total || 0}
                        </Typography>
                      </Box>
                    </Box>
                  </>
                ) : (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ textAlign: 'center', py: 3 }}
                  >
                    {preOrderStats?.error || 'Pre-order logger unavailable'}
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Box>

          {/* Row 2: TP Verification + Anomaly Alerts */}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' },
              gap: 2,
            }}
          >
            {/* TP Verification Card */}
            <Card sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <CheckCircle sx={{ color: 'info.main', mr: 1 }} />
                  <Typography variant="h6" sx={{ fontSize: '0.95rem', fontWeight: 600 }}>
                    TP Verification
                  </Typography>
                </Box>
                {tpVerification && !tpVerification.error ? (
                  <>
                    <Box sx={{ textAlign: 'center', mb: 2 }}>
                      <Typography variant="h3" color="info.main" fontWeight={700}>
                        {tpVerification.success_rate?.toFixed(1) || '0.0'}%
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Success Rate
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="success.main">
                          ✓ Verified:
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                          {tpVerification.successful || tpVerification.verified || 0}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="warning.main">
                          ⚠ Orphaned:
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                          {tpVerification.orphaned_positions ||
                            tpVerification.orphaned ||
                            tpVerification.failed ||
                            0}
                        </Typography>
                      </Box>
                      {(tpVerification.last_verification || tpVerification.timestamp) && (
                        <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                          Last check:{' '}
                          {new Date(
                            tpVerification.last_verification || tpVerification.timestamp
                          ).toLocaleTimeString()}
                        </Typography>
                      )}
                    </Box>
                  </>
                ) : (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ textAlign: 'center', py: 3 }}
                  >
                    {tpVerification?.error || 'TP verifier unavailable'}
                  </Typography>
                )}
              </CardContent>
            </Card>

            {/* Anomaly Alerts Card */}
            <Card sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <BugReport sx={{ color: 'warning.main', mr: 1 }} />
                  <Typography variant="h6" sx={{ fontSize: '0.95rem', fontWeight: 600 }}>
                    Anomaly Alerts
                  </Typography>
                </Box>
                {anomalies.length > 0 ? (
                  <Box sx={{ maxHeight: 250, overflowY: 'auto' }}>
                    {anomalies.slice(0, 5).map((anomaly, idx) => (
                      <Alert
                        key={idx}
                        severity={anomaly.severity?.toLowerCase() || 'info'}
                        sx={{ mb: 1, fontSize: '0.85rem' }}
                      >
                        <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
                          {anomaly.type}
                        </Typography>
                        <Typography variant="caption" display="block">
                          {anomaly.message}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {new Date(anomaly.timestamp).toLocaleTimeString()}
                        </Typography>
                      </Alert>
                    ))}
                    {anomalies.length > 5 && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ display: 'block', textAlign: 'center', mt: 1 }}
                      >
                        + {anomalies.length - 5} more anomalies
                      </Typography>
                    )}
                  </Box>
                ) : (
                  <Box sx={{ textAlign: 'center', py: 4 }}>
                    <CheckCircle sx={{ fontSize: 48, color: 'success.main', mb: 1 }} />
                    <Typography variant="body2" fontWeight={600} color="success.main">
                      No anomalies detected
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      All systems operating normally
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Box>
        </Box>

        {/* RIGHT HALF - Advanced Predictive Decision Map */}
        <Card
          sx={{
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            flexDirection: 'column',
            height: { xs: 'auto', lg: '100%' },
          }}
        >
          <CardContent
            sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Psychology sx={{ color: 'secondary.main', mr: 1 }} />
              <Typography variant="h6" sx={{ fontSize: '0.95rem', fontWeight: 600 }}>
                🔮 Advanced Predictive Decision Map
              </Typography>
              <Chip
                label="Code-Based"
                size="small"
                color="success"
                sx={{ ml: 'auto', fontWeight: 600, fontSize: '0.7rem' }}
              />
            </Box>
            {advancedPredictions && !advancedPredictions.error ? (
              <>
                {/* Warning Banner for Manual Cancellations */}
                {advancedPredictions.warnings && advancedPredictions.warnings.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    {advancedPredictions.warnings.map((warning, idx) => (
                      <Alert
                        key={idx}
                        severity={warning.severity || 'warning'}
                        icon={<Warning />}
                        sx={{ mb: 1 }}
                      >
                        <Typography variant="body2" fontWeight={700}>
                          {warning.message}
                        </Typography>
                        <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                          {warning.details}
                        </Typography>
                        <Typography
                          variant="caption"
                          display="block"
                          sx={{ mt: 0.5, fontWeight: 600, color: 'text.primary' }}
                        >
                          Action: {warning.action}
                        </Typography>
                      </Alert>
                    ))}
                  </Box>
                )}

                {/* Bot Not Running Warning */}
                {advancedPredictions.warning && (
                  <Alert severity="info" sx={{ mb: 2 }}>
                    <Typography variant="caption">{advancedPredictions.warning}</Typography>
                  </Alert>
                )}

                {/* Current State Summary */}
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-around',
                    mb: 2,
                    p: 1.5,
                    bgcolor: 'action.hover',
                    borderRadius: 1,
                  }}
                >
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">
                      Current Price
                    </Typography>
                    <Typography variant="body1" fontWeight={700} color="primary.main">
                      ${advancedPredictions.current_state?.price?.toLocaleString() || 'N/A'}
                    </Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">
                      Mode
                    </Typography>
                    <Typography variant="body1" fontWeight={700}>
                      {advancedPredictions.current_state?.mode || 'N/A'}
                    </Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">
                      Positions
                    </Typography>
                    <Typography variant="body1" fontWeight={700}>
                      {advancedPredictions.current_state?.positions || 0}/
                      {advancedPredictions.current_state?.max_positions || 10}
                    </Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">
                      Grid Step
                    </Typography>
                    <Typography variant="body1" fontWeight={700} color="secondary.main">
                      ${advancedPredictions.grid_config?.step?.toLocaleString() || 'N/A'}
                    </Typography>
                  </Box>
                </Box>

                {/* Next Action - Primary Prediction */}
                {advancedPredictions.next_action && (
                  <Alert
                    severity={
                      advancedPredictions.next_action.type.includes('PENDING')
                        ? 'info'
                        : advancedPredictions.next_action.type.includes('WILL')
                          ? 'success'
                          : advancedPredictions.next_action.type === 'CAPACITY_FULL'
                            ? 'warning'
                            : 'default'
                    }
                    icon={
                      advancedPredictions.next_action.type.includes('BUY') ? (
                        <TrendingDown />
                      ) : advancedPredictions.next_action.type.includes('SELL') ? (
                        <TrendingUp />
                      ) : (
                        <Speed />
                      )
                    }
                    sx={{ mb: 2 }}
                  >
                    <Typography variant="body2" fontWeight={700} sx={{ mb: 0.5 }}>
                      {advancedPredictions.next_action.type === 'PENDING_BUY'
                        ? '⏳ Pending BUY Order'
                        : advancedPredictions.next_action.type === 'PENDING_SELL'
                          ? '⏳ Pending SELL Order'
                          : advancedPredictions.next_action.type === 'WILL_BUY'
                            ? '🎯 Next: Place BUY Order'
                            : advancedPredictions.next_action.type === 'WILL_SELL'
                              ? '🎯 Next: Place SELL Order'
                              : advancedPredictions.next_action.type === 'CAPACITY_FULL'
                                ? '⚠️ Capacity Full'
                                : '⏸️ No Pending Action'}
                    </Typography>
                    {advancedPredictions.next_action.price && (
                      <Typography variant="h6" color="primary.main" fontWeight={700}>
                        @ ${advancedPredictions.next_action.price.toLocaleString()}
                      </Typography>
                    )}
                    <Typography
                      variant="caption"
                      display="block"
                      color="text.secondary"
                      sx={{ mt: 0.5 }}
                    >
                      {advancedPredictions.next_action.status}
                    </Typography>
                    <Typography
                      variant="caption"
                      display="block"
                      fontWeight={600}
                      sx={{ mt: 1, color: 'text.primary' }}
                    >
                      Then: {advancedPredictions.next_action.then}
                    </Typography>
                  </Alert>
                )}

                {/* Scenarios - What Happens Next */}
                <Typography
                  variant="subtitle2"
                  fontWeight={700}
                  sx={{ mb: 1, mt: 1, color: 'text.primary' }}
                >
                  📊 Predicted Action Sequences (Based on Bot Code):
                </Typography>
                <Box sx={{ flex: 1, overflowY: 'auto', pr: 1 }}>
                  {/* Scenario 1: If Pending Order Fills */}
                  {advancedPredictions.scenarios?.if_pending_fills && (
                    <Card
                      sx={{
                        mb: 2,
                        bgcolor: 'success.dark',
                        border: '2px solid',
                        borderColor: 'success.main',
                      }}
                    >
                      <CardContent sx={{ py: 1.5 }}>
                        <Typography
                          variant="subtitle2"
                          fontWeight={700}
                          sx={{ mb: 1, color: 'success.light' }}
                        >
                          💚 Scenario 1: If Pending Order Fills
                        </Typography>
                        {advancedPredictions.scenarios.if_pending_fills.actions?.map(
                          (action, idx) => (
                            <Box
                              key={idx}
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                                mb: 1,
                                p: 1,
                                bgcolor: 'rgba(255,255,255,0.1)',
                                borderRadius: 1,
                                borderLeft: 3,
                                borderColor:
                                  action.action === 'PLACE_TP' ? 'info.main' : 'success.light',
                              }}
                            >
                              <Chip
                                label={`#${action.sequence}`}
                                size="small"
                                sx={{
                                  bgcolor: 'success.main',
                                  color: 'white',
                                  fontWeight: 700,
                                  minWidth: 35,
                                }}
                              />
                              <Box sx={{ flex: 1 }}>
                                <Typography
                                  variant="body2"
                                  fontWeight={600}
                                  sx={{ color: 'white' }}
                                >
                                  {action.action.replace(/_/g, ' ')}
                                </Typography>
                                {action.price && (
                                  <Typography variant="caption" sx={{ color: 'success.light' }}>
                                    @ ${action.price.toLocaleString()}
                                  </Typography>
                                )}
                                {action.reason && (
                                  <Typography
                                    variant="caption"
                                    display="block"
                                    sx={{ color: 'grey.300' }}
                                  >
                                    {action.reason}
                                  </Typography>
                                )}
                              </Box>
                            </Box>
                          )
                        )}
                      </CardContent>
                    </Card>
                  )}

                  {/* Scenario 2: If TP Fills */}
                  {advancedPredictions.scenarios?.if_tp_fills && (
                    <Card
                      sx={{
                        mb: 2,
                        bgcolor: 'info.dark',
                        border: '2px solid',
                        borderColor: 'info.main',
                      }}
                    >
                      <CardContent sx={{ py: 1.5 }}>
                        <Typography
                          variant="subtitle2"
                          fontWeight={700}
                          sx={{ mb: 1, color: 'info.light' }}
                        >
                          💙 Scenario 2: If TP Order Fills (Market Rises)
                        </Typography>
                        {advancedPredictions.scenarios.if_tp_fills.actions?.map((action, idx) => (
                          <Box
                            key={idx}
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                              mb: 1,
                              p: 1,
                              bgcolor: 'rgba(255,255,255,0.1)',
                              borderRadius: 1,
                              borderLeft: 3,
                              borderColor:
                                action.action === 'CANCEL_PENDING_BUY'
                                  ? 'warning.main'
                                  : 'info.light',
                            }}
                          >
                            <Chip
                              label={`#${action.sequence}`}
                              size="small"
                              sx={{
                                bgcolor: 'info.main',
                                color: 'white',
                                fontWeight: 700,
                                minWidth: 35,
                              }}
                            />
                            <Box sx={{ flex: 1 }}>
                              <Typography variant="body2" fontWeight={600} sx={{ color: 'white' }}>
                                {action.action.replace(/_/g, ' ')}
                                {action.action === 'CANCEL_PENDING_BUY' && ' 🔴'}
                              </Typography>
                              {action.price && (
                                <Typography variant="caption" sx={{ color: 'info.light' }}>
                                  @ ${action.price.toLocaleString()}
                                </Typography>
                              )}
                              {action.reason && (
                                <Typography
                                  variant="caption"
                                  display="block"
                                  sx={{ color: 'grey.300' }}
                                >
                                  {action.reason}
                                </Typography>
                              )}
                            </Box>
                          </Box>
                        ))}
                        <Alert severity="success" sx={{ mt: 1, fontSize: '0.75rem' }}>
                          <Typography variant="caption" fontWeight={700}>
                            Profit Realized: +$
                            {advancedPredictions.scenarios.if_tp_fills.profit_realized?.toLocaleString() ||
                              'N/A'}
                          </Typography>
                        </Alert>
                      </CardContent>
                    </Card>
                  )}

                  {/* Full Sequence Preview */}
                  {advancedPredictions.full_sequence?.sequence && (
                    <Card
                      sx={{
                        mb: 1,
                        bgcolor: 'background.default',
                        border: '1px dashed',
                        borderColor: 'divider',
                      }}
                    >
                      <CardContent sx={{ py: 1.5 }}>
                        <Typography
                          variant="caption"
                          fontWeight={700}
                          sx={{ mb: 1, display: 'block', color: 'text.secondary' }}
                        >
                          🔄 Full Decision Tree ({advancedPredictions.full_sequence.sequence.length}{' '}
                          steps predicted)
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          {advancedPredictions.full_sequence.summary}
                        </Typography>
                      </CardContent>
                    </Card>
                  )}
                </Box>
              </>
            ) : predictiveMap && !predictiveMap.error ? (
              <>
                {/* Fallback to old predictive map if advanced predictions unavailable */}
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-around',
                    mb: 2,
                    p: 1,
                    bgcolor: 'action.hover',
                    borderRadius: 1,
                  }}
                >
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">
                      Price
                    </Typography>
                    <Typography variant="body1" fontWeight={700} color="primary.main">
                      $
                      {(
                        predictiveMap.current_state?.price || predictiveMap.current_price
                      )?.toLocaleString() || 'N/A'}
                    </Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">
                      Mode
                    </Typography>
                    <Typography variant="body1" fontWeight={700}>
                      {predictiveMap.current_state?.mode || predictiveMap.mode || 'N/A'}
                    </Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">
                      Capacity
                    </Typography>
                    <Typography variant="body1" fontWeight={700}>
                      {predictiveMap.current_state?.positions !== undefined &&
                      predictiveMap.current_state?.max_positions
                        ? `${predictiveMap.current_state.positions}/${predictiveMap.current_state.max_positions}`
                        : predictiveMap.current_state?.capacity_used_pct !== undefined
                          ? `${predictiveMap.current_state.capacity_used_pct.toFixed(0)}%`
                          : predictiveMap.capacity
                            ? `${predictiveMap.capacity.used}/${predictiveMap.capacity.max}`
                            : 'N/A'}
                    </Typography>
                  </Box>
                </Box>

                {(() => {
                  // Handle both old format (next_levels) and new format (scenarios)
                  let levels = [];
                  let nextAction = null;
                  let executedOrders = predictiveMap.executed_orders || [];
                  let placedTPs = predictiveMap.placed_tps || [];

                  if (predictiveMap.scenarios) {
                    // New format with sequencing
                    nextAction = predictiveMap.scenarios.next_action;
                    const drops = predictiveMap.scenarios.price_drops || [];
                    const rises = predictiveMap.scenarios.price_rises || [];

                    // Combine with drops first (most important), then rises
                    levels = [
                      ...drops.map((s) => ({
                        ...s,
                        isNext: s.sequence === 1 && !nextAction,
                      })),
                      ...rises.map((s) => ({
                        ...s,
                        isTP: true,
                      })),
                    ];
                  } else if (predictiveMap.next_levels) {
                    // Old format
                    levels = predictiveMap.next_levels;
                  }

                  return (
                    <>
                      {/* Executed Orders from Bot Memory */}
                      {executedOrders.length > 0 && (
                        <Box
                          sx={{
                            mb: 2,
                            p: 1.5,
                            bgcolor: 'success.dark',
                            borderRadius: 1,
                            border: '1px solid',
                            borderColor: 'success.main',
                          }}
                        >
                          <Typography
                            variant="subtitle2"
                            fontWeight={700}
                            sx={{ mb: 1, color: 'success.light' }}
                          >
                            📍 Executed Orders (Bot Memory)
                          </Typography>
                          {executedOrders.map((order, idx) => (
                            <Box
                              key={idx}
                              sx={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                py: 0.5,
                                borderBottom:
                                  idx < executedOrders.length - 1 ? '1px solid' : 'none',
                                borderColor: 'success.main',
                              }}
                            >
                              <Typography variant="caption" sx={{ color: 'success.light' }}>
                                Grid #{order.grid_level} @ ${order.entry_price?.toLocaleString()}
                              </Typography>
                              <Typography
                                variant="caption"
                                fontWeight={600}
                                sx={{ color: 'white' }}
                              >
                                Size: {order.size}
                              </Typography>
                            </Box>
                          ))}
                        </Box>
                      )}

                      {/* Placed TPs from Bot Memory */}
                      {placedTPs.length > 0 && (
                        <Box
                          sx={{
                            mb: 2,
                            p: 1.5,
                            bgcolor: 'info.dark',
                            borderRadius: 1,
                            border: '1px solid',
                            borderColor: 'info.main',
                          }}
                        >
                          <Typography
                            variant="subtitle2"
                            fontWeight={700}
                            sx={{ mb: 1, color: 'info.light' }}
                          >
                            📤 Placed TPs (Bot Memory)
                          </Typography>
                          {placedTPs.map((tp, idx) => (
                            <Box
                              key={idx}
                              sx={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                py: 0.5,
                                borderBottom: idx < placedTPs.length - 1 ? '1px solid' : 'none',
                                borderColor: 'info.main',
                              }}
                            >
                              <Typography variant="caption" sx={{ color: 'info.light' }}>
                                TP @ ${tp.tp_price?.toLocaleString()} (Entry: $
                                {tp.entry_price?.toLocaleString()})
                              </Typography>
                              <Typography
                                variant="caption"
                                fontWeight={600}
                                sx={{ color: 'white' }}
                              >
                                Size: {tp.size}
                              </Typography>
                            </Box>
                          ))}
                        </Box>
                      )}

                      {/* Next Action Banner */}
                      {nextAction && (
                        <Alert
                          severity={
                            nextAction.type.includes('PENDING')
                              ? 'info'
                              : nextAction.type === 'CAPACITY_FULL'
                                ? 'warning'
                                : 'success'
                          }
                          sx={{ mb: 2, fontSize: '0.875rem' }}
                        >
                          <Typography variant="body2" fontWeight={600}>
                            {nextAction.type === 'PENDING_BUY'
                              ? '⏳ Pending BUY Order'
                              : nextAction.type === 'PENDING_SELL'
                                ? '⏳ Pending SELL Order'
                                : nextAction.type === 'PENDING_TP'
                                  ? '⏳ Pending TP Order'
                                  : nextAction.type === 'WILL_BUY'
                                    ? '🎯 Next Action: BUY'
                                    : nextAction.type === 'WILL_SELL'
                                      ? '🎯 Next Action: SELL'
                                      : nextAction.type === 'CAPACITY_FULL'
                                        ? '⚠️ Capacity Full'
                                        : '⏸️ No Action'}
                          </Typography>
                          <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                            {nextAction.price && `@ $${nextAction.price.toLocaleString()}`}{' '}
                            {nextAction.status}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Then: {nextAction.then}
                          </Typography>
                        </Alert>
                      )}

                      {levels.length > 0 ? (
                        <Box sx={{ flex: 1, overflowY: 'auto', pr: 1 }}>
                          {levels.map((level, idx) => (
                            <Box
                              key={idx}
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                                p: 1,
                                mb: 1,
                                borderRadius: 1,
                                bgcolor: level.isNext ? 'action.selected' : 'action.hover',
                                borderLeft: 3,
                                borderColor: level.action?.toLowerCase().includes('buy')
                                  ? 'success.main'
                                  : level.action?.toLowerCase().includes('tp')
                                    ? 'info.main'
                                    : level.action?.toLowerCase().includes('sell')
                                      ? 'error.main'
                                      : 'grey.500',
                              }}
                            >
                              <Chip
                                label={level.action}
                                size="small"
                                color={
                                  level.action?.toLowerCase().includes('buy')
                                    ? 'success'
                                    : level.action?.toLowerCase().includes('tp')
                                      ? 'info'
                                      : level.action?.toLowerCase().includes('sell')
                                        ? 'error'
                                        : 'default'
                                }
                                sx={{ fontWeight: 600, minWidth: 70 }}
                              />
                              <Typography variant="body2" fontWeight={700} sx={{ minWidth: 90 }}>
                                {level.price ? `$${level.price.toLocaleString()}` : 'N/A'}
                              </Typography>
                              <Box sx={{ flex: 1 }}>
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                  display="block"
                                >
                                  {level.reason ||
                                    (level.change_pct ? `${level.change_pct.toFixed(2)}%` : '')}
                                </Typography>
                                {level.tp_price && (
                                  <Typography
                                    variant="caption"
                                    color="success.main"
                                    display="block"
                                  >
                                    TP: ${level.tp_price.toLocaleString()} (+$
                                    {level.profit_target?.toFixed(0)})
                                  </Typography>
                                )}
                                {level.entry_price && (
                                  <Typography
                                    variant="caption"
                                    color="text.secondary"
                                    display="block"
                                  >
                                    Entry: ${level.entry_price.toLocaleString()} | Profit: +$
                                    {level.profit?.toFixed(0)}
                                  </Typography>
                                )}
                              </Box>
                              {level.sequence && (
                                <Chip
                                  label={`#${level.sequence}`}
                                  size="small"
                                  sx={{ minWidth: 40 }}
                                />
                              )}
                            </Box>
                          ))}
                        </Box>
                      ) : (
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ textAlign: 'center', py: 2 }}
                        >
                          No predicted actions at this time
                        </Typography>
                      )}
                    </>
                  );
                })()}
              </>
            ) : (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ textAlign: 'center', py: 3 }}
              >
                {predictiveMap?.error || 'Predictive display unavailable'}
              </Typography>
            )}
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};

export default MonitoringDashboard;
