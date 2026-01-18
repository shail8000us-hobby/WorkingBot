/**
 * Risk & Safety Dashboard - Modern Unified Safety Control Center
 * 
 * Consolidates all safety layers into one beautiful, user-friendly interface:
 * - 6-Layer Guardian Safety System
 * - Real-time monitoring with visual indicators
 * - Comprehensive risk metrics
 * - Modern glassmorphism design
 * - Quick actions and emergency controls
 * - Multi-symbol support (BTCUSD/ETHUSD) v6.0
 * 
 * Created: December 27, 2025
 * Updated: Multi-symbol support January 2025
 * Author: Senior Developer
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  LinearProgress,
  Chip,
  IconButton,
  Tooltip,
  Alert,
  AlertTitle,
  Button,
  Divider,
  CircularProgress,
  Paper,
  ToggleButtonGroup,
  ToggleButton
} from '@mui/material';
import {
  Shield,
  Activity,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Zap,
  BarChart3,
  Cpu,
  Radio,
  Database,
  TrendingUpIcon,
  Power,
  PowerOff,
  Info
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../utils/apiShim';
import { useInstance, parseInstanceName } from '../context/InstanceContext';

// Symbol colors for theming
const symbolColors = {
  'BTCUSD': { bg: '#f7931a20', border: '#f7931a', text: '#f7931a' },
  'ETHUSD': { bg: '#627eea20', border: '#627eea', text: '#627eea' }
};

const RiskSafetyDashboard = () => {
  // Multi-symbol support v6.0
  const { selectedInstance, instances } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const [currentSymbol, setCurrentSymbol] = useState(instanceInfo?.symbol || 'BTCUSD');
  
  // Get available symbols from instances
  const availableSymbols = [...new Set(instances.map(i => parseInstanceName(i.name)?.symbol).filter(Boolean))];
  if (availableSymbols.length === 0) {
    availableSymbols.push('BTCUSD', 'ETHUSD');
  }
  
  const handleSymbolChange = (event, newSymbol) => {
    if (newSymbol !== null) {
      setCurrentSymbol(newSymbol);
    }
  };
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchSafetyData = useCallback(async () => {
    try {
      const response = await api.get(`/api/safety/dashboard?symbol=${currentSymbol}`);
      if (response.data.success) {
        setData(response.data);
        setError(null);
        setLastUpdate(new Date());
      } else {
        setError(response.data.error || 'Failed to fetch safety data');
      }
    } catch (err) {
      console.error('Error fetching safety data:', err);
      setError(err.message || 'Connection error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [currentSymbol]);

  useEffect(() => {
    fetchSafetyData();
    const interval = setInterval(fetchSafetyData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, [fetchSafetyData]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchSafetyData();
  };

  const handleGuardianAction = async (action) => {
    try {
      const endpoint = action === 'start' ? '/api/guardian/start' : '/api/guardian/stop';
      await api.post(endpoint);
      setTimeout(fetchSafetyData, 1500);
    } catch (err) {
      console.error(`Failed to ${action} Guardian:`, err);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress size={60} />
      </Box>
    );
  }

  if (error && !data) {
    return (
      <Alert severity="error">
        <AlertTitle>Error</AlertTitle>
        {error}
      </Alert>
    );
  }

  const {
    overall_status = 'UNKNOWN',
    critical_issues = [],
    warnings = [],
    guardian = {},
    volatility = {},
    pnl_loss = {},
    position_size = {},
    liquidation = {},
    system_health = {},
    rsi = {},
    quick_stats = {}
  } = data || {};

  const getStatusColor = (status) => {
    switch (status) {
      case 'SAFE':
      case 'OK':
      case 'GO':
        return { bg: 'rgba(16, 185, 129, 0.1)', border: 'rgba(16, 185, 129, 0.3)', text: '#10b981' };
      case 'WARNING':
      case 'YELLOW':
      case 'ORANGE':
      case 'CAUTION':
        return { bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.3)', text: '#f59e0b' };
      case 'CRITICAL':
      case 'STOP':
      case 'RED':
      case 'DANGER':
        return { bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.3)', text: '#ef4444' };
      default:
        return { bg: 'rgba(148, 163, 184, 0.1)', border: 'rgba(148, 163, 184, 0.3)', text: '#94a3b8' };
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'SAFE':
      case 'OK':
      case 'GO':
        return <CheckCircle2 className="w-5 h-5" />;
      case 'WARNING':
      case 'YELLOW':
      case 'ORANGE':
      case 'CAUTION':
        return <AlertTriangle className="w-5 h-5" />;
      case 'CRITICAL':
      case 'STOP':
      case 'RED':
      case 'DANGER':
        return <XCircle className="w-5 h-5" />;
      default:
        return <Info className="w-5 h-5" />;
    }
  };

  const statusColors = getStatusColor(overall_status);
  const currentSymbolColors = symbolColors[currentSymbol] || symbolColors['BTCUSD'];

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, mb: 1, display: 'flex', alignItems: 'center', gap: 2 }}>
            <Shield className="w-8 h-8" style={{ color: statusColors.text }} />
            Risk & Safety Control Center
            <Chip
              label={currentSymbol}
              size="small"
              sx={{
                bgcolor: currentSymbolColors.bg,
                color: currentSymbolColors.text,
                fontWeight: 600,
                border: `1px solid ${currentSymbolColors.border}`
              }}
            />
          </Typography>
          <Typography variant="body2" color="text.secondary">
            6-Layer Guardian Protection System • Real-time Monitoring • Institutional Grade Safety
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          {/* Symbol Toggle */}
          <ToggleButtonGroup
            value={currentSymbol}
            exclusive
            onChange={handleSymbolChange}
            size="small"
            sx={{
              '& .MuiToggleButton-root': {
                textTransform: 'none',
                fontWeight: 600,
                px: 2,
                py: 0.5
              }
            }}
          >
            {availableSymbols.map(symbol => {
              const colors = symbolColors[symbol] || symbolColors['BTCUSD'];
              return (
                <ToggleButton
                  key={symbol}
                  value={symbol}
                  sx={{
                    '&.Mui-selected': {
                      bgcolor: colors.bg,
                      color: colors.text,
                      borderColor: colors.border,
                      '&:hover': {
                        bgcolor: colors.bg
                      }
                    }
                  }}
                >
                  {symbol.replace('USD', '')}
                </ToggleButton>
              );
            })}
          </ToggleButtonGroup>
          {lastUpdate && (
            <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
              Updated {Math.floor((new Date() - lastUpdate) / 1000)}s ago
            </Typography>
          )}
          <Tooltip title="Refresh data">
            <IconButton onClick={handleRefresh} disabled={refreshing}>
              <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Overall Status Banner */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <Card
          sx={{
            mb: 3,
            background: `linear-gradient(135deg, ${statusColors.bg}, ${statusColors.bg})`,
            border: `2px solid ${statusColors.border}`,
            borderRadius: 3,
            overflow: 'hidden'
          }}
        >
          <CardContent sx={{ p: 3 }}>
            <Grid container spacing={3} alignItems="center">
              <Grid item xs={12} md={8}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                  {getStatusIcon(overall_status)}
                  <Typography variant="h5" sx={{ fontWeight: 700, color: statusColors.text }}>
                    System Status: {overall_status}
                  </Typography>
                </Box>
                
                {critical_issues.length > 0 && (
                  <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>
                    <AlertTitle sx={{ fontWeight: 700 }}>Critical Issues</AlertTitle>
                    {critical_issues.map((issue, idx) => (
                      <Typography key={idx} variant="body2">• {issue}</Typography>
                    ))}
                  </Alert>
                )}
                
                {warnings.length > 0 && (
                  <Alert severity="warning" sx={{ borderRadius: 2 }}>
                    <AlertTitle sx={{ fontWeight: 700 }}>Warnings</AlertTitle>
                    {warnings.map((warning, idx) => (
                      <Typography key={idx} variant="body2">• {warning}</Typography>
                    ))}
                  </Alert>
                )}
                
                {critical_issues.length === 0 && warnings.length === 0 && (
                  <Typography variant="body1" color="text.secondary">
                    ✅ All safety systems operational. Trading conditions optimal.
                  </Typography>
                )}
              </Grid>
              
              <Grid item xs={12} md={4}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                    Protection Score
                  </Typography>
                  <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                    <CircularProgress
                      variant="determinate"
                      value={quick_stats.protection_score || 0}
                      size={120}
                      thickness={6}
                      sx={{
                        color: quick_stats.protection_score >= 80 ? '#10b981' : quick_stats.protection_score >= 60 ? '#f59e0b' : '#ef4444'
                      }}
                    />
                    <Box
                      sx={{
                        top: 0,
                        left: 0,
                        bottom: 0,
                        right: 0,
                        position: 'absolute',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexDirection: 'column'
                      }}
                    >
                      <Typography variant="h4" sx={{ fontWeight: 700 }}>
                        {quick_stats.protection_score || 0}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        / 100
                      </Typography>
                    </Box>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    {quick_stats.layers_active || 0} / {quick_stats.total_layers || 6} Layers Active
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </motion.div>

      {/* Guardian Control */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%', borderRadius: 3 }}>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Shield className="w-5 h-5" style={{ color: '#3b82f6' }} />
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Guardian Engine
                  </Typography>
                </Box>
                <Chip
                  label={guardian.running ? 'ACTIVE' : 'STANDBY'}
                  color={guardian.running ? 'success' : 'default'}
                  size="small"
                  icon={guardian.running ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                />
              </Box>
              
              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={4}>
                  <Paper elevation={0} sx={{ p: 2, bgcolor: 'rgba(59, 130, 246, 0.1)', borderRadius: 2 }}>
                    <Typography variant="caption" color="text.secondary" display="block">
                      Uptime
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {guardian.running ? `${Math.floor(guardian.uptime_seconds / 3600)}h ${Math.floor((guardian.uptime_seconds % 3600) / 60)}m` : '—'}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={4}>
                  <Paper elevation={0} sx={{ p: 2, bgcolor: 'rgba(59, 130, 246, 0.1)', borderRadius: 2 }}>
                    <Typography variant="caption" color="text.secondary" display="block">
                      Cycles
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {guardian.cycle_count?.toLocaleString() || '—'}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={4}>
                  <Paper elevation={0} sx={{ p: 2, bgcolor: 'rgba(59, 130, 246, 0.1)', borderRadius: 2 }}>
                    <Typography variant="caption" color="text.secondary" display="block">
                      Signal
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 600, color: guardian.signal === 'GO' ? '#10b981' : '#ef4444' }}>
                      {guardian.signal || '—'}
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>
              
              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  color="success"
                  startIcon={<Power className="w-4 h-4" />}
                  onClick={() => handleGuardianAction('start')}
                  disabled={guardian.running}
                  fullWidth
                  sx={{ borderRadius: 2 }}
                >
                  Start Guardian
                </Button>
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<PowerOff className="w-4 h-4" />}
                  onClick={() => handleGuardianAction('stop')}
                  disabled={!guardian.running}
                  fullWidth
                  sx={{ borderRadius: 2 }}
                >
                  Stop Guardian
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%', borderRadius: 3 }}>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <TrendingDown className="w-5 h-5" style={{ color: '#ef4444' }} />
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  PnL & Loss Protection
                </Typography>
              </Box>
              
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2" color="text.secondary">
                    Loss Utilization
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    ₹{pnl_loss.total_loss_inr?.toLocaleString() || 0} / ₹{pnl_loss.max_loss_inr?.toLocaleString() || 0}
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(pnl_loss.utilization_percent || 0, 100)}
                  sx={{
                    height: 12,
                    borderRadius: 2,
                    bgcolor: 'rgba(148, 163, 184, 0.1)',
                    '& .MuiLinearProgress-bar': {
                      bgcolor: pnl_loss.utilization_percent >= 85 ? '#ef4444' : pnl_loss.utilization_percent >= 60 ? '#f59e0b' : '#10b981',
                      borderRadius: 2
                    }
                  }}
                />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                  {(pnl_loss.utilization_percent || 0).toFixed(1)}% of loss ceiling
                </Typography>
              </Box>
              
              <Divider sx={{ my: 2 }} />
              
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Total PnL
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 600, color: pnl_loss.total_pnl_inr >= 0 ? '#10b981' : '#ef4444' }}>
                    ₹{pnl_loss.total_pnl_inr?.toLocaleString() || 0}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Status
                  </Typography>
                  <Chip
                    label={pnl_loss.status || 'UNKNOWN'}
                    color={pnl_loss.status === 'OK' ? 'success' : pnl_loss.status === 'WARNING' ? 'warning' : 'error'}
                    size="small"
                    sx={{ fontWeight: 600, mt: 0.5 }}
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Safety Layers Grid */}
      <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
        Safety Layers Status
      </Typography>
      
      <Grid container spacing={3}>
        {/* Layer 1: Volatility */}
        <Grid item xs={12} sm={6} md={4}>
          <SafetyLayerCard
            number={1}
            title="Volatility Safety"
            icon={<Activity className="w-5 h-5" />}
            status={volatility.status || 'UNKNOWN'}
            metrics={[
              { label: 'IV', value: `${volatility.iv?.value?.toFixed(1) || '—'}%`, limit: volatility.iv?.limit },
              { label: 'RV', value: `${volatility.rv?.value?.toFixed(1) || '—'}%`, limit: volatility.rv?.limit },
              { label: 'Spread', value: `${volatility.spread?.value?.toFixed(1) || '—'}%`, limit: volatility.spread?.limit }
            ]}
          />
        </Grid>

        {/* Layer 2: Position Size */}
        <Grid item xs={12} sm={6} md={4}>
          <SafetyLayerCard
            number={3}
            title="Position Size"
            icon={<BarChart3 className="w-5 h-5" />}
            status={position_size.status || 'OK'}
            metrics={[
              { label: 'Total Contracts', value: position_size.total_position?.toLocaleString() || '0', limit: position_size.max_position },
              { label: 'Positions', value: position_size.position_count || '0' },
              { label: 'Utilization', value: `${(position_size.utilization_percent || 0).toFixed(1)}%` }
            ]}
          />
        </Grid>

        {/* Layer 4: Liquidation */}
        <Grid item xs={12} sm={6} md={4}>
          <SafetyLayerCard
            number={4}
            title="Liquidation Protection"
            icon={<AlertTriangle className="w-5 h-5" />}
            status={liquidation.margin_zone || 'UNKNOWN'}
            metrics={[
              { label: 'Margin Zone', value: liquidation.margin_zone || 'UNKNOWN' },
              { label: 'Utilization', value: `${(liquidation.margin_utilization || 0).toFixed(1)}%` },
              { label: 'Safety Buffer', value: `${(liquidation.mtm_safety_buffer || 0).toFixed(1)}%` }
            ]}
          />
        </Grid>

        {/* Layer 5: System Health */}
        <Grid item xs={12} sm={6} md={4}>
          <SafetyLayerCard
            number={5}
            title="System Health"
            icon={<Cpu className="w-5 h-5" />}
            status={system_health.api_healthy && system_health.data_fresh ? 'HEALTHY' : 'DEGRADED'}
            metrics={[
              { label: 'API', value: system_health.api_healthy ? '✅ Healthy' : '❌ Issues' },
              { label: 'WebSocket', value: system_health.websocket_connected ? '✅ Connected' : '❌ Disconnected' },
              { label: 'Data Freshness', value: system_health.data_fresh ? '✅ Fresh' : '❌ Stale' }
            ]}
          />
        </Grid>

        {/* Layer 6: RSI Safety */}
        <Grid item xs={12} sm={6} md={4}>
          <SafetyLayerCard
            number={6}
            title="RSI Market Filter"
            icon={<TrendingUpIcon className="w-5 h-5" />}
            status={rsi.status || 'UNKNOWN'}
            metrics={[
              { label: 'Current RSI', value: rsi.current_rsi?.toFixed(2) || '—' },
              { label: 'Bot Mode', value: rsi.bot_mode || 'UNKNOWN' },
              { label: 'Threshold', value: rsi.threshold?.toFixed(1) || '—' }
            ]}
          />
        </Grid>

        {/* Layer 7: Exchange Status */}
        <Grid item xs={12} sm={6} md={4}>
          <SafetyLayerCard
            number={5}
            title="Exchange Status"
            icon={<Radio className="w-5 h-5" />}
            status={system_health.exchange_operational ? 'OPERATIONAL' : 'MAINTENANCE'}
            metrics={[
              { label: 'Status', value: system_health.exchange_operational ? '🟢 Operational' : '🔴 Issues' },
              { label: 'Event Store', value: system_health.event_store_connected ? '✅ Connected' : '❌ Disconnected' }
            ]}
          />
        </Grid>
      </Grid>
    </Box>
  );
};

// Safety Layer Card Component
const SafetyLayerCard = ({ number, title, icon, status, metrics }) => {
  const statusColors = {
    OK: { bg: 'rgba(16, 185, 129, 0.1)', border: 'rgba(16, 185, 129, 0.3)', text: '#10b981' },
    GO: { bg: 'rgba(16, 185, 129, 0.1)', border: 'rgba(16, 185, 129, 0.3)', text: '#10b981' },
    GREEN: { bg: 'rgba(16, 185, 129, 0.1)', border: 'rgba(16, 185, 129, 0.3)', text: '#10b981' },
    HEALTHY: { bg: 'rgba(16, 185, 129, 0.1)', border: 'rgba(16, 185, 129, 0.3)', text: '#10b981' },
    OPERATIONAL: { bg: 'rgba(16, 185, 129, 0.1)', border: 'rgba(16, 185, 129, 0.3)', text: '#10b981' },
    WARNING: { bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.3)', text: '#f59e0b' },
    YELLOW: { bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.3)', text: '#f59e0b' },
    ORANGE: { bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.3)', text: '#f59e0b' },
    DEGRADED: { bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.3)', text: '#f59e0b' },
    STOP: { bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.3)', text: '#ef4444' },
    RED: { bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.3)', text: '#ef4444' },
    CRITICAL: { bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.3)', text: '#ef4444' },
    DANGER: { bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.3)', text: '#ef4444' },
    MAINTENANCE: { bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.3)', text: '#ef4444' }
  };

  const colors = statusColors[status] || { bg: 'rgba(148, 163, 184, 0.1)', border: 'rgba(148, 163, 184, 0.3)', text: '#94a3b8' };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <Card
        sx={{
          height: '100%',
          borderRadius: 3,
          background: colors.bg,
          border: `2px solid ${colors.border}`,
          transition: 'all 0.3s ease',
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: 4
          }
        }}
      >
        <CardContent sx={{ p: 2.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Box
                sx={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: colors.border,
                  color: colors.text
                }}
              >
                {icon}
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" display="block">
                  Layer {number}
                </Typography>
                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                  {title}
                </Typography>
              </Box>
            </Box>
            <Chip
              label={status}
              size="small"
              sx={{
                bgcolor: colors.border,
                color: colors.text,
                fontWeight: 600,
                fontSize: '0.7rem'
              }}
            />
          </Box>

          <Divider sx={{ my: 1.5 }} />

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {metrics.map((metric, idx) => (
              <Box key={idx} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  {metric.label}
                </Typography>
                <Typography variant="caption" sx={{ fontWeight: 600 }}>
                  {metric.value}
                  {metric.limit && (
                    <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                      / {metric.limit}
                    </Typography>
                  )}
                </Typography>
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default RiskSafetyDashboard;
