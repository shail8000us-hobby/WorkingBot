import React, { useState, useEffect } from 'react';
import ConfigSection from './ConfigSection';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  LinearProgress,
  Chip,
  Alert,
  AlertTitle,
  Divider,
  IconButton,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import {
  Warning as WarningIcon,
  Error as ErrorIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  TrendingUp,
  TrendingDown,
  TrendingFlat,
} from '@mui/icons-material';
import api from '../utils/apiShim';

const LiquidationProtectionPanel = () => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [liquidationData, setLiquidationData] = useState(null);

  // Fetch liquidation status
  const fetchLiquidationStatus = async () => {
    try {
      const { data } = await api.get('/api/liquidation/status');

      if (data.success) {
        setLiquidationData(data);
      } else {
        console.error('Failed to fetch liquidation status:', data.error);
      }
    } catch (error) {
      console.error('Error fetching liquidation status:', error);
    }
  };

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchLiquidationStatus();
      setLoading(false);
    };
    loadData();
  }, []);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchLiquidationStatus();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Manual refresh
  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchLiquidationStatus();
    setRefreshing(false);
  };

  // Zone color mapping
  const getZoneColor = (zone) => {
    switch (zone?.toUpperCase()) {
      case 'GREEN':
        return 'success';
      case 'YELLOW':
        return 'warning';
      case 'ORANGE':
        return 'warning';
      case 'RED':
        return 'error';
      case 'SAFE':
        return 'success';
      case 'ACCEPTABLE':
        return 'info';
      case 'CAUTION':
        return 'warning';
      case 'DANGER':
        return 'error';
      default:
        return 'default';
    }
  };

  // Zone icon
  const getZoneIcon = (zone) => {
    switch (zone?.toUpperCase()) {
      case 'GREEN':
      case 'SAFE':
        return <CheckCircleIcon sx={{ fontSize: 40, color: '#4caf50' }} />;
      case 'YELLOW':
      case 'ACCEPTABLE':
        return <InfoIcon sx={{ fontSize: 40, color: '#ff9800' }} />;
      case 'ORANGE':
      case 'CAUTION':
        return <WarningIcon sx={{ fontSize: 40, color: '#ff9800' }} />;
      case 'RED':
      case 'DANGER':
        return <ErrorIcon sx={{ fontSize: 40, color: '#f44336' }} />;
      default:
        return <InfoIcon sx={{ fontSize: 40, color: '#9e9e9e' }} />;
    }
  };

  // Trend icon
  const getTrendIcon = (trend) => {
    switch (trend?.toUpperCase()) {
      case 'IMPROVING':
        return <TrendingUp sx={{ color: '#4caf50' }} />;
      case 'WORSENING':
        return <TrendingDown sx={{ color: '#f44336' }} />;
      case 'STABLE':
        return <TrendingFlat sx={{ color: '#9e9e9e' }} />;
      default:
        return <TrendingFlat sx={{ color: '#9e9e9e' }} />;
    }
  };

  // Format INR
  const formatINR = (value) => {
    if (value === null || value === undefined) return '₹0';
    return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
  };

  // Format percentage
  const formatPercent = (value) => {
    if (value === null || value === undefined) return '0%';
    return `${value.toFixed(1)}%`;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (!liquidationData) {
    return (
      <Alert severity="error">
        <AlertTitle>Error</AlertTitle>
        Failed to load liquidation protection data. Ensure Guardian Bot is running.
      </Alert>
    );
  }

  const { margin, distance, mtm, config: apiConfig } = liquidationData;

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" gutterBottom>
            🛡️ Liquidation Protection System
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Real-time monitoring • Portfolio Margin Mode • v4.0.0
          </Typography>
        </Box>
        <Box>
          <Tooltip title="Refresh data">
            <IconButton onClick={handleRefresh} disabled={refreshing}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Status Banner */}
      {!apiConfig?.enabled && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          <AlertTitle>⚠️ Liquidation Protection Disabled</AlertTitle>
          Enable LIQUIDATION_PROTECTION_ENABLED in configuration to activate monitoring.
        </Alert>
      )}

      {/* Main Status Cards */}
      <Grid container spacing={3} mb={3}>
        {/* Margin Utilization Card */}
        <Grid item xs={12} md={4}>
          <Card
            sx={{
              height: '100%',
              background:
                margin?.zone === 'GREEN'
                  ? 'rgba(76, 175, 80, 0.08)'
                  : margin?.zone === 'YELLOW'
                    ? 'rgba(255, 152, 0, 0.08)'
                    : margin?.zone === 'ORANGE'
                      ? 'rgba(255, 152, 0, 0.15)'
                      : 'rgba(244, 67, 54, 0.08)',
              border: `1px solid ${
                margin?.zone === 'GREEN'
                  ? 'rgba(76, 175, 80, 0.3)'
                  : margin?.zone === 'YELLOW'
                    ? 'rgba(255, 152, 0, 0.3)'
                    : margin?.zone === 'ORANGE'
                      ? 'rgba(255, 152, 0, 0.5)'
                      : 'rgba(244, 67, 54, 0.3)'
              }`,
            }}
          >
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">💰 Margin Utilization</Typography>
                {getZoneIcon(margin?.zone)}
              </Box>

              <Typography variant="h3" gutterBottom>
                {formatPercent(margin?.utilization || 0)}
              </Typography>

              <Chip
                label={margin?.zone || 'UNKNOWN'}
                color={getZoneColor(margin?.zone)}
                sx={{ mb: 2, fontWeight: 'bold' }}
              />

              <LinearProgress
                variant="determinate"
                value={Math.min(margin?.utilization || 0, 100)}
                sx={{
                  height: 10,
                  borderRadius: 5,
                  mb: 2,
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                  '& .MuiLinearProgress-bar': {
                    backgroundColor:
                      margin?.zone === 'GREEN'
                        ? '#4caf50'
                        : margin?.zone === 'YELLOW'
                          ? '#ff9800'
                          : '#f44336',
                  },
                }}
              />

              <Box mt={2}>
                <Typography variant="body2" color="textSecondary">
                  Status:{' '}
                  {margin?.can_open_positions ? '✅ Can open positions' : '⛔ REDUCE ONLY MODE'}
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant="body2">
                  Total Balance: {formatINR(margin?.total_balance)}
                </Typography>
                <Typography variant="body2">
                  Available: {formatINR(margin?.available_balance)}
                </Typography>
                <Typography variant="body2">
                  Blocked: {formatINR(margin?.blocked_balance)}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Liquidation Distance Card */}
        <Grid item xs={12} md={4}>
          <Card
            sx={{
              height: '100%',
              background:
                distance?.zone === 'SAFE'
                  ? 'rgba(76, 175, 80, 0.08)'
                  : distance?.zone === 'ACCEPTABLE'
                    ? 'rgba(33, 150, 243, 0.08)'
                    : distance?.zone === 'CAUTION'
                      ? 'rgba(255, 152, 0, 0.08)'
                      : 'rgba(244, 67, 54, 0.08)',
              border: `1px solid ${
                distance?.zone === 'SAFE'
                  ? 'rgba(76, 175, 80, 0.3)'
                  : distance?.zone === 'ACCEPTABLE'
                    ? 'rgba(33, 150, 243, 0.3)'
                    : distance?.zone === 'CAUTION'
                      ? 'rgba(255, 152, 0, 0.3)'
                      : 'rgba(244, 67, 54, 0.3)'
              }`,
            }}
          >
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">🛡️ Liquidation Distance</Typography>
                {getZoneIcon(distance?.zone)}
              </Box>

              <Typography variant="h3" gutterBottom>
                {formatPercent(distance?.distance || 0)}
              </Typography>

              <Chip
                label={distance?.zone || 'UNKNOWN'}
                color={getZoneColor(distance?.zone)}
                sx={{ mb: 2, fontWeight: 'bold' }}
              />

              <LinearProgress
                variant="determinate"
                value={Math.min(distance?.distance || 0, 100)}
                sx={{
                  height: 10,
                  borderRadius: 5,
                  mb: 2,
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                  '& .MuiLinearProgress-bar': {
                    backgroundColor:
                      distance?.zone === 'SAFE'
                        ? '#4caf50'
                        : distance?.zone === 'ACCEPTABLE'
                          ? '#2196f3'
                          : distance?.zone === 'CAUTION'
                            ? '#ff9800'
                            : '#f44336',
                  },
                }}
              />

              <Box mt={2}>
                <Typography variant="body2" color="textSecondary">
                  {distance?.liquidation_risk ? '🚨 LIQUIDATION RISK' : '✅ Safe distance'}
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant="body2">
                  Maintenance Margin: {formatINR(distance?.maintenance_margin)}
                </Typography>
                {distance?.bankruptcy_distance !== undefined && (
                  <Typography variant="body2" color="textSecondary">
                    Bankruptcy Distance: {distance.bankruptcy_distance.toFixed(1)}%
                  </Typography>
                )}
                <Typography
                  variant="body2"
                  sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 1 }}
                >
                  Formula: (Current Price - Liquidation Price) / Current Price × 100
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ fontSize: '0.7rem', color: 'text.disabled', mt: 0.5, fontStyle: 'italic' }}
                >
                  Delta Exchange India (price-based, minimum across positions)
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* MTM Card */}
        <Grid item xs={12} md={4}>
          <Card
            sx={{
              height: '100%',
              background:
                (mtm?.current_mtm_inr || 0) >= 0
                  ? 'rgba(76, 175, 80, 0.08)'
                  : 'rgba(244, 67, 54, 0.08)',
              border: `1px solid ${(mtm?.current_mtm_inr || 0) >= 0 ? 'rgba(76, 175, 80, 0.3)' : 'rgba(244, 67, 54, 0.3)'}`,
            }}
          >
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">📊 Mark-to-Market</Typography>
                {getTrendIcon(mtm?.trend)}
              </Box>

              <Typography
                variant="h3"
                gutterBottom
                color={(mtm?.current_mtm_inr || 0) >= 0 ? 'success.main' : 'error.main'}
              >
                {formatINR(mtm?.current_mtm_inr || 0)}
              </Typography>

              <Chip
                label={`Trend: ${mtm?.trend || 'UNKNOWN'}`}
                color={(mtm?.current_mtm_inr || 0) >= 0 ? 'success' : 'error'}
                sx={{ mb: 2 }}
              />

              <Box mt={2}>
                <Typography variant="body2" color="textSecondary">
                  {(mtm?.current_mtm_inr || 0) >= 0 ? '✅ Unrealized Profit' : '⚠️ Unrealized Loss'}
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant="body2">
                  Unrealized P&L: {formatINR(margin?.unrealized_pnl || 0)}
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 1 }}
                >
                  MTM affects margin utilization directly
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Alerts Section */}
      {(margin?.zone !== 'GREEN' || distance?.zone !== 'SAFE') && (
        <Alert
          severity={margin?.zone === 'RED' || distance?.zone === 'DANGER' ? 'error' : 'warning'}
          sx={{ mb: 3 }}
        >
          <AlertTitle>
            {margin?.zone === 'RED' || distance?.zone === 'DANGER'
              ? '🚨 CRITICAL ALERT'
              : '⚠️ WARNING'}
          </AlertTitle>

          {margin?.zone === 'YELLOW' && (
            <Typography>
              <strong>REDUCE ONLY MODE</strong> - Margin utilization{' '}
              {formatPercent(margin?.utilization)} ≥{' '}
              {formatPercent(apiConfig?.margin_utilization_max || 40)}. No new BUY orders allowed.
              TP orders remain active.
            </Typography>
          )}

          {margin?.zone === 'ORANGE' && (
            <Typography>
              <strong>HIGH UTILIZATION</strong> - Add margin or reduce positions soon. Emergency
              reserve: {formatPercent(100 - (margin?.utilization || 0))}.
            </Typography>
          )}

          {margin?.zone === 'RED' && (
            <Typography>
              <strong>CRITICAL UTILIZATION</strong> - IMMEDIATE ACTION REQUIRED! Add margin NOW or
              close positions. Only {formatPercent(100 - (margin?.utilization || 0))} reserve
              remaining!
            </Typography>
          )}

          {distance?.zone === 'CAUTION' && (
            <Typography>
              <strong>LOW LIQUIDATION DISTANCE</strong> - Distance{' '}
              {formatPercent(distance?.distance)} below minimum{' '}
              {formatPercent(apiConfig?.liquidation_distance_min || 60)}. Add margin recommended.
            </Typography>
          )}

          {distance?.zone === 'DANGER' && (
            <Typography>
              <strong>CRITICAL LIQUIDATION RISK</strong> - Distance{' '}
              {formatPercent(distance?.distance)} is dangerously low! Add margin or close positions
              IMMEDIATELY!
            </Typography>
          )}
        </Alert>
      )}

      {/* Info Footer */}
      <Box
        mt={3}
        p={2}
        bgcolor="rgba(255, 255, 255, 0.05)"
        borderRadius={1}
        border="1px solid rgba(255, 255, 255, 0.1)"
      >
        <Typography variant="body2" color="textSecondary" align="center">
          💡 <strong>Tip:</strong> Keep margin utilization below 40% to maintain 60% emergency
          reserve. Monitor liquidation distance - below 60% is risky.
          <br />
          <span style={{ color: '#2196f3', fontWeight: 'bold' }}>
            📖 For detailed configuration and safety guidelines, see the Documentation section below
          </span>
        </Typography>
      </Box>

      {/* Liquidation Protection Configuration Section */}
      <ConfigSection
        configKeys={[
          // ✅ REAL PARAMETERS - Actually used by the liquidation monitoring code

          // Core Settings
          'LIQUIDATION_PROTECTION_ENABLED',
          'LIQUIDATION_LOG_LEVEL',

          // Margin Utilization Monitoring
          'MARGIN_UTILIZATION_MAX',
          'MARGIN_UTILIZATION_WARNING_1',
          'MARGIN_UTILIZATION_WARNING_2',
          'MARGIN_EMERGENCY_RESERVE',
          'REDUCE_ONLY_MODE_AT_UTILIZATION',

          // Liquidation Distance Monitoring
          'LIQUIDATION_DISTANCE_MIN',
          'LIQUIDATION_DISTANCE_TARGET',
          'LIQUIDATION_DISTANCE_CRITICAL',
          'LIQUIDATION_DISTANCE_CHECK_INTERVAL',

          // MTM (Mark-to-Market) Monitoring
          'MTM_MONITORING_ENABLED',
          'MTM_ALERT_THRESHOLD',
          'MTM_CRITICAL_THRESHOLD',
          'MTM_CHECK_INTERVAL',

          // Automated Actions
          'AUTO_CANCEL_ORDERS_AT_YELLOW',
          'AUTO_REDUCE_POSITIONS_ENABLED',
          'AUTO_REDUCE_AT_UTILIZATION',
          'AUTO_REDUCE_PERCENTAGE',
          'AUTO_ADD_MARGIN_ENABLED',

          // Emergency Actions
          'EMERGENCY_CLOSE_ALL_AT_UTILIZATION',
          'EMERGENCY_CANCEL_ALL_ORDERS',

          // Real-time Monitoring
          'REAL_TIME_MONITORING_ENABLED',
          'WEBSOCKET_MARGIN_UPDATES',
          'WEBSOCKET_PORTFOLIO_UPDATES',
          'MARK_PRICE_WEBSOCKET_ENABLED',

          // Alert Settings
          'LIQUIDATION_ALERT_TELEGRAM',
          'LIQUIDATION_ALERT_SOUND',
          'LIQUIDATION_ALERT_EMAIL',
          'LIQUIDATION_CHECK_INTERVAL',
          'LIQUIDATION_ALERT_THROTTLE',

          // WebSocket Settings
          'WEBSOCKET_RECONNECT_INTERVAL',
          'WEBSOCKET_TIMEOUT',
          'WEBSOCKET_HEARTBEAT_INTERVAL',
          'AUTO_EMERGENCY_ON_WEBSOCKET_ALERT',

          // Alert Throttling (per zone)
          'ALERT_THROTTLE_GREEN',
          'ALERT_THROTTLE_YELLOW',
          'ALERT_THROTTLE_ORANGE',
          'ALERT_THROTTLE_RED',
        ]}
        title="Liquidation Protection Configuration"
        defaultExpanded={false}
      />
    </Box>
  );
};

export default LiquidationProtectionPanel;
