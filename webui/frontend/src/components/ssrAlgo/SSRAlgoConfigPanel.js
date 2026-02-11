/**
 * SSR Algo Config Panel
 * 
 * Configuration form for creating new SSR Algo sessions.
 * Allows setting underlying, expiry, strike parameters, and previewing strikes.
 * 
 * Created: February 2, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Chip,
  Alert,
  CircularProgress,
  Divider,
  Collapse,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Tooltip,
  Switch,
  FormControlLabel,
  InputAdornment,
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Visibility as PreviewIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Settings as SettingsIcon,
  Security as SecurityIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import ssrAlgoService from './ssrAlgoService';
import api from '../../utils/apiShim';

// Default strike configuration
const DEFAULT_STRIKE_CONFIG = {
  otm_buy_percent_min: 45,
  otm_buy_percent_max: 49,
  far_otm_percent_min: 20,
  far_otm_percent_max: 30,
};

// Default circuit breaker configuration
const DEFAULT_CIRCUIT_BREAKER = {
  enabled: true,
  max_adjustments_per_day: 10,
  max_adjustments_per_session: 20,
  max_daily_loss_usd: 5000,
  cooldown_minutes: 5,
};

// Default monitoring configuration
const DEFAULT_MONITOR_CONFIG = {
  dwell_time_minutes: 10,
  price_tolerance: 100,
};

/**
 * Configuration panel for SSR Algo sessions
 */
const SSRAlgoConfigPanel = ({ onSessionCreated }) => {
  // Form state
  const [underlying, setUnderlying] = useState('BTC');
  const [expiry, setExpiry] = useState('');
  const [expiryOptions, setExpiryOptions] = useState([]);
  const [autoLoopRounds, setAutoLoopRounds] = useState(2);
  const [orderType, setOrderType] = useState('ssr');
  const [run24Hours, setRun24Hours] = useState(false);
  const [startTime, setStartTime] = useState('15:00');
  const [endTime, setEndTime] = useState('21:00');
  const [strikeConfig, setStrikeConfig] = useState(DEFAULT_STRIKE_CONFIG);
  const [circuitBreaker, setCircuitBreaker] = useState(DEFAULT_CIRCUIT_BREAKER);
  const [monitorConfig, setMonitorConfig] = useState(DEFAULT_MONITOR_CONFIG);
  
  // UI state
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState(null);
  const [strikePreview, setStrikePreview] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showSafetySettings, setShowSafetySettings] = useState(false);
  const [loadingExpiries, setLoadingExpiries] = useState(false);

  // Fetch available expiries
  const fetchExpiries = useCallback(async () => {
    setLoadingExpiries(true);
    try {
      // Use the correct options-chain endpoint
      const response = await fetch(`/api/options-chain/expirations?underlying=${underlying}`);
      const data = await response.json();
      
      // Handle different response formats
      const expiries = data.expirations || data.expiries || [];
      
      if (expiries.length > 0) {
        setExpiryOptions(expiries);
        // Auto-select first expiry if none selected
        if (!expiry || !expiries.includes(expiry)) {
          setExpiry(expiries[0]);
        }
      } else {
        setExpiryOptions([]);
        setError('No expiries available. Try refreshing.');
      }
    } catch (err) {
      console.error('Failed to fetch expiries:', err);
      setError('Failed to load expiries: ' + err.message);
      setExpiryOptions([]);
    } finally {
      setLoadingExpiries(false);
    }
  }, [underlying, expiry]);

  useEffect(() => {
    fetchExpiries();
  }, [underlying]); // Refetch when underlying changes

  // Preview strikes
  const handlePreviewStrikes = async () => {
    if (!expiry) {
      setError('Please select an expiry date');
      return;
    }

    setPreviewLoading(true);
    setError(null);
    setStrikePreview(null);

    try {
      const result = await ssrAlgoService.previewStrikes({
        underlying,
        expiry,
        strike_config: strikeConfig
      });

      if (result.success) {
        setStrikePreview(result);
      } else {
        setError(result.error || 'Failed to preview strikes');
      }
    } catch (err) {
      setError(err.message || 'Failed to preview strikes');
    } finally {
      setPreviewLoading(false);
    }
  };

  // Create and start session
  const handleCreateSession = async () => {
    if (!expiry) {
      setError('Please select an expiry date');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Create session with all configuration
      const createResult = await ssrAlgoService.createSession({
        underlying,
        expiry,
        auto_loop_rounds: autoLoopRounds,
        order_type: orderType,
        start_time: run24Hours ? '00:00' : startTime,
        end_time: run24Hours ? '23:59' : endTime,
        strike_config: strikeConfig,
        circuit_breaker_config: circuitBreaker,
        dwell_time_minutes: monitorConfig.dwell_time_minutes,
        price_tolerance: monitorConfig.price_tolerance,
      });

      if (!createResult.success) {
        setError(createResult.error || 'Failed to create session');
        return;
      }

      const sessionId = createResult.session?.session_id;
      
      // Auto-start the session after creation
      if (sessionId) {
        const startResult = await ssrAlgoService.startSession(sessionId);
        if (!startResult.success) {
          setError(`Session created but failed to start: ${startResult.error}`);
        }
      }

      // Notify parent
      if (onSessionCreated) {
        onSessionCreated(createResult.session);
      }

      // Clear preview
      setStrikePreview(null);

    } catch (err) {
      setError(err.message || 'Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  // Handle strike config changes
  const handleStrikeConfigChange = (field, value) => {
    setStrikeConfig(prev => ({
      ...prev,
      [field]: value
    }));
    // Clear preview when config changes
    setStrikePreview(null);
  };

  // Handle circuit breaker config changes
  const handleCircuitBreakerChange = (field, value) => {
    setCircuitBreaker(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // Handle monitor config changes
  const handleMonitorConfigChange = (field, value) => {
    setMonitorConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  return (
    <Card sx={{ 
      mb: 3, 
      background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%)',
      border: '1px solid rgba(56, 189, 248, 0.2)',
      borderRadius: 3,
      boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)'
    }}>
      <CardContent sx={{ p: 3 }}>
        <Typography 
          variant="h5" 
          gutterBottom 
          sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 1.5,
            color: '#38bdf8',
            fontWeight: 600,
            mb: 3
          }}
        >
          <SettingsIcon sx={{ fontSize: 28 }} />
          SSR ALGO Configuration
        </Typography>
        
        <Divider sx={{ my: 2, borderColor: 'rgba(148, 163, 184, 0.2)' }} />

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Basic Configuration - Row 1 */}
        <Grid container spacing={1.5}>
          {/* Underlying */}
          <Grid item xs={6} sm={4} md={2.5}>
            <FormControl fullWidth size="small">
              <InputLabel id="underlying-label" shrink>Underlying</InputLabel>
              <Select
                native
                labelId="underlying-label"
                value={underlying}
                label="Underlying"
                onChange={(e) => setUnderlying(e.target.value)}
                inputProps={{ id: 'underlying-select' }}
              >
                <option value="BTC">BTC</option>
                <option value="ETH">ETH</option>
              </Select>
            </FormControl>
          </Grid>

          {/* Expiry with Refresh */}
          <Grid item xs={6} sm={4} md={3}>
            <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
              <FormControl fullWidth size="small">
                <InputLabel id="expiry-label" shrink>Expiry</InputLabel>
                <Select
                  native
                  labelId="expiry-label"
                  value={expiry}
                  label="Expiry"
                  onChange={(e) => setExpiry(e.target.value)}
                  disabled={loadingExpiries}
                  inputProps={{ id: 'expiry-select' }}
                >
                  {expiryOptions.length === 0 ? (
                    <option value="" disabled>No expiries available</option>
                  ) : (
                    expiryOptions.map((exp) => (
                      <option key={exp} value={exp}>{exp}</option>
                    ))
                  )}
                </Select>
              </FormControl>
              <Tooltip title="Refresh expiry dates" arrow>
                <IconButton 
                  onClick={fetchExpiries} 
                  disabled={loadingExpiries}
                  size="small"
                  sx={{ flexShrink: 0 }}
                >
                  {loadingExpiries ? <CircularProgress size={16} /> : <RefreshIcon fontSize="small" />}
                </IconButton>
              </Tooltip>
            </Box>
          </Grid>

          {/* Auto Loop Rounds */}
          <Grid item xs={6} sm={4} md={2}>
            <Tooltip title="Number of butterfly entries to execute. Each round places a new set of 8 legs" arrow>
              <TextField
                label="Rounds"
                type="number"
                size="small"
                fullWidth
                value={autoLoopRounds}
                onChange={(e) => setAutoLoopRounds(Math.min(10, Math.max(1, parseInt(e.target.value) || 1)))}
                inputProps={{ min: 1, max: 10 }}
              />
            </Tooltip>
          </Grid>

          {/* Order Type */}
          <Grid item xs={6} sm={4} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel id="order-type-label" shrink>Order Type</InputLabel>
              <Select
                native
                labelId="order-type-label"
                value={orderType}
                label="Order Type"
                onChange={(e) => setOrderType(e.target.value)}
                inputProps={{ id: 'order-type-select' }}
              >
                <option value="ssr">SSR (Smart)</option>
                <option value="maker">Maker Only</option>
                <option value="market">Market</option>
              </Select>
            </FormControl>
          </Grid>

          {/* Preview Button */}
          <Grid item xs={12} sm={4} md={2.5}>
            <Tooltip title="Preview strikes based on current configuration" arrow>
              <Button
                variant="outlined"
                fullWidth
                startIcon={previewLoading ? <CircularProgress size={16} /> : <PreviewIcon />}
                onClick={handlePreviewStrikes}
                disabled={previewLoading || !expiry}
                sx={{ height: 40, fontSize: '0.8rem' }}
              >
                Preview
              </Button>
            </Tooltip>
          </Grid>
        </Grid>

        {/* Time Window Row */}
        <Box sx={{ mt: 1 }}>
          <FormControlLabel
            control={
              <Switch
                checked={run24Hours}
                onChange={(e) => setRun24Hours(e.target.checked)}
                size="small"
                color="primary"
              />
            }
            label={
              <Typography variant="caption" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                Run 24 Hours (All Day)
                {run24Hours && (
                  <Chip 
                    size="small" 
                    label="00:00 - 23:59" 
                    sx={{ height: 16, fontSize: '0.65rem', bgcolor: 'rgba(129, 140, 248, 0.2)' }}
                  />
                )}
              </Typography>
            }
            sx={{ mb: 1 }}
          />
          <Grid container spacing={1.5}>
            <Grid item xs={6} sm={4} md={3}>
              <Tooltip title={run24Hours ? "Disabled when running 24 hours" : "Start time (UTC) for monitoring"} arrow>
                <TextField
                  label="Start Time"
                  type="time"
                  size="small"
                  fullWidth
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  disabled={run24Hours}
                  InputLabelProps={{ shrink: true }}
                  sx={{ opacity: run24Hours ? 0.5 : 1 }}
                />
              </Tooltip>
            </Grid>
            <Grid item xs={6} sm={4} md={3}>
              <Tooltip title={run24Hours ? "Disabled when running 24 hours" : "End time (UTC) for monitoring"} arrow>
                <TextField
                  label="End Time"
                  type="time"
                  size="small"
                  fullWidth
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  disabled={run24Hours}
                  InputLabelProps={{ shrink: true }}
                  sx={{ opacity: run24Hours ? 0.5 : 1 }}
                />
              </Tooltip>
            </Grid>
          </Grid>
        </Box>

        {/* Advanced Settings Toggle */}
        <Box sx={{ mt: 1.5, display: 'flex', gap: 1.5 }}>
          <Button
            size="small"
            onClick={() => setShowAdvanced(!showAdvanced)}
            endIcon={showAdvanced ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            startIcon={<SettingsIcon />}
          >
            {showAdvanced ? 'Hide' : 'Show'} Strike Settings
          </Button>
          <Button
            size="small"
            onClick={() => setShowSafetySettings(!showSafetySettings)}
            endIcon={showSafetySettings ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            startIcon={<SecurityIcon />}
            color="warning"
          >
            {showSafetySettings ? 'Hide' : 'Show'} Safety & Limits
          </Button>
        </Box>

        {/* Advanced Strike Config */}
        <Collapse in={showAdvanced}>
          <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              <Tooltip title="Select OTM strikes where premium is between these percentages of the ATM premium. Lower % = further OTM strikes with cheaper premium." arrow>
                <span style={{ cursor: 'help', borderBottom: '1px dashed' }}>OTM Buy Range (% of ATM Premium)</span>
              </Tooltip>
            </Typography>
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid item xs={6}>
                <Tooltip title="Minimum premium percentage. For ATM premium of $500, 45% = look for OTM strikes with ~$225 premium" arrow>
                  <TextField
                    label="Min %"
                    type="number"
                    size="small"
                    fullWidth
                    value={strikeConfig.otm_buy_percent_min}
                    onChange={(e) => handleStrikeConfigChange('otm_buy_percent_min', parseInt(e.target.value) || 0)}
                    inputProps={{ min: 30, max: 60 }}
                    helperText="Default: 45%"
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={6}>
                <Tooltip title="Maximum premium percentage. For ATM premium of $500, 49% = look for OTM strikes with up to ~$245 premium" arrow>
                  <TextField
                    label="Max %"
                    type="number"
                    size="small"
                    fullWidth
                    value={strikeConfig.otm_buy_percent_max}
                    onChange={(e) => handleStrikeConfigChange('otm_buy_percent_max', parseInt(e.target.value) || 0)}
                    inputProps={{ min: 30, max: 60 }}
                    helperText="Default: 49%"
                  />
                </Tooltip>
              </Grid>
            </Grid>

            <Typography variant="subtitle2" gutterBottom>
              <Tooltip title="Select far OTM strikes for protective wings. These are sold to reduce cost. Premium should be 20-30% of the OTM buy strikes." arrow>
                <span style={{ cursor: 'help', borderBottom: '1px dashed' }}>Far OTM Sell Range (% of OTM Buy Premium)</span>
              </Tooltip>
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Tooltip title="Minimum far OTM premium. For OTM buy premium of $235, 20% = look for strikes with ~$47 premium" arrow>
                  <TextField
                    label="Min %"
                    type="number"
                    size="small"
                    fullWidth
                    value={strikeConfig.far_otm_percent_min}
                    onChange={(e) => handleStrikeConfigChange('far_otm_percent_min', parseInt(e.target.value) || 0)}
                    inputProps={{ min: 10, max: 40 }}
                    helperText="Default: 20%"
                  />
                </Tooltip>
              </Grid>
              <Grid item xs={6}>
                <Tooltip title="Maximum far OTM premium. For OTM buy premium of $235, 30% = look for strikes with up to ~$70 premium" arrow>
                  <TextField
                    label="Max %"
                    type="number"
                    size="small"
                    fullWidth
                    value={strikeConfig.far_otm_percent_max}
                    onChange={(e) => handleStrikeConfigChange('far_otm_percent_max', parseInt(e.target.value) || 0)}
                    inputProps={{ min: 10, max: 40 }}
                    helperText="Default: 30%"
                  />
                </Tooltip>
              </Grid>
            </Grid>
          </Box>
        </Collapse>

        {/* Safety & Circuit Breaker Settings */}
        <Collapse in={showSafetySettings}>
          <Box sx={{ 
            mt: 2, 
            p: 2, 
            bgcolor: 'rgba(245, 158, 11, 0.1)', 
            borderRadius: 1,
            border: '1px solid rgba(245, 158, 11, 0.3)'
          }}>
            <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'warning.main' }}>
              <SecurityIcon /> Circuit Breaker Settings
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
              Safety limits that automatically stop the algo when exceeded. Prevents runaway adjustments and excessive losses.
            </Typography>

            {/* Enable/Disable Circuit Breakers */}
            <FormControlLabel
              control={
                <Switch
                  checked={circuitBreaker.enabled}
                  onChange={(e) => handleCircuitBreakerChange('enabled', e.target.checked)}
                  color="warning"
                />
              }
              label={
                <Box>
                  <Typography variant="body2">Enable Circuit Breakers</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {circuitBreaker.enabled ? 'Safety limits active' : 'WARNING: No safety limits!'}
                  </Typography>
                </Box>
              }
              sx={{ mb: 2 }}
            />

            <Grid container spacing={2}>
              {/* Max Adjustments Per Day */}
              <Grid item xs={12} sm={6} md={3}>
                <Tooltip title="Maximum number of adjustments allowed in a single day. Session auto-stops when limit reached." arrow>
                  <TextField
                    label="Max Adj/Day"
                    type="number"
                    size="small"
                    fullWidth
                    value={circuitBreaker.max_adjustments_per_day}
                    onChange={(e) => handleCircuitBreakerChange('max_adjustments_per_day', parseInt(e.target.value) || 1)}
                    inputProps={{ min: 1, max: 50 }}
                    disabled={!circuitBreaker.enabled}
                    helperText="Default: 10"
                  />
                </Tooltip>
              </Grid>

              {/* Max Adjustments Per Session */}
              <Grid item xs={12} sm={6} md={3}>
                <Tooltip title="Maximum total adjustments for the entire session lifetime. Session auto-stops when reached." arrow>
                  <TextField
                    label="Max Adj/Session"
                    type="number"
                    size="small"
                    fullWidth
                    value={circuitBreaker.max_adjustments_per_session}
                    onChange={(e) => handleCircuitBreakerChange('max_adjustments_per_session', parseInt(e.target.value) || 1)}
                    inputProps={{ min: 1, max: 100 }}
                    disabled={!circuitBreaker.enabled}
                    helperText="Default: 20"
                  />
                </Tooltip>
              </Grid>

              {/* Daily Loss Limit */}
              <Grid item xs={12} sm={6} md={3}>
                <Tooltip title="Maximum daily loss in USD before session auto-stops. Critical safety limit." arrow>
                  <TextField
                    label="Daily Loss Limit"
                    type="number"
                    size="small"
                    fullWidth
                    value={circuitBreaker.max_daily_loss_usd}
                    onChange={(e) => handleCircuitBreakerChange('max_daily_loss_usd', parseInt(e.target.value) || 100)}
                    InputProps={{
                      startAdornment: <InputAdornment position="start">$</InputAdornment>,
                    }}
                    inputProps={{ min: 100, max: 100000 }}
                    disabled={!circuitBreaker.enabled}
                    helperText="Default: $5,000"
                  />
                </Tooltip>
              </Grid>

              {/* Cooldown Between Adjustments */}
              <Grid item xs={12} sm={6} md={3}>
                <Tooltip title="Minimum time between adjustments. Prevents rapid-fire adjustments during volatile periods." arrow>
                  <TextField
                    label="Cooldown (min)"
                    type="number"
                    size="small"
                    fullWidth
                    value={circuitBreaker.cooldown_minutes}
                    onChange={(e) => handleCircuitBreakerChange('cooldown_minutes', parseInt(e.target.value) || 1)}
                    inputProps={{ min: 1, max: 60 }}
                    disabled={!circuitBreaker.enabled}
                    helperText="Default: 5 min"
                  />
                </Tooltip>
              </Grid>
            </Grid>

            <Divider sx={{ my: 2, borderColor: 'rgba(245, 158, 11, 0.3)' }} />

            {/* Monitoring Configuration */}
            <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 2 }}>
              <WarningIcon color="warning" /> Adjustment Trigger Settings
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
              Configure when adjustments are triggered based on price movement into max loss zones.
            </Typography>

            <Grid container spacing={2}>
              {/* Dwell Time */}
              <Grid item xs={12} sm={6} md={4}>
                <Tooltip title="How long price must stay in max loss zone before triggering an adjustment. Longer = fewer false triggers." arrow>
                  <TextField
                    label="Dwell Time"
                    type="number"
                    size="small"
                    fullWidth
                    value={monitorConfig.dwell_time_minutes}
                    onChange={(e) => handleMonitorConfigChange('dwell_time_minutes', parseInt(e.target.value) || 1)}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">min</InputAdornment>,
                    }}
                    inputProps={{ min: 1, max: 60 }}
                    helperText="Default: 10 minutes"
                  />
                </Tooltip>
              </Grid>

              {/* Price Tolerance */}
              <Grid item xs={12} sm={6} md={4}>
                <Tooltip title="Price tolerance around max loss points. e.g., if max loss at $100,000, a tolerance of 100 means $99,900-$100,100 is the trigger zone." arrow>
                  <TextField
                    label="Price Tolerance"
                    type="number"
                    size="small"
                    fullWidth
                    value={monitorConfig.price_tolerance}
                    onChange={(e) => handleMonitorConfigChange('price_tolerance', parseInt(e.target.value) || 50)}
                    InputProps={{
                      startAdornment: <InputAdornment position="start">±$</InputAdornment>,
                    }}
                    inputProps={{ min: 50, max: 500 }}
                    helperText="Default: ±$100"
                  />
                </Tooltip>
              </Grid>
            </Grid>

            {/* Safety Summary */}
            <Alert severity={circuitBreaker.enabled ? "info" : "warning"} sx={{ mt: 2 }}>
              {circuitBreaker.enabled ? (
                <>
                  <strong>Safety Active:</strong> Session will auto-stop after {circuitBreaker.max_adjustments_per_day} adjustments/day, 
                  {circuitBreaker.max_adjustments_per_session} total, or ${circuitBreaker.max_daily_loss_usd.toLocaleString()} daily loss. 
                  Min {circuitBreaker.cooldown_minutes} min between adjustments.
                </>
              ) : (
                <>
                  <strong>⚠️ Circuit Breakers Disabled:</strong> No automatic safety limits. The algo will continue adjusting 
                  without limits. Use with extreme caution!
                </>
              )}
            </Alert>
          </Box>
        </Collapse>

        {/* Strike Preview Table */}
        {strikePreview && strikePreview.success && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom color="primary">
              Strike Selection Preview
            </Typography>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Position</TableCell>
                    <TableCell>Strike</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Side</TableCell>
                    <TableCell align="right">Premium</TableCell>
                    <TableCell align="right">Qty</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {/* ATM CE Sell */}
                  <TableRow>
                    <TableCell>ATM</TableCell>
                    <TableCell>{strikePreview.atm?.strike}</TableCell>
                    <TableCell><Chip size="small" label="CE" color="success" /></TableCell>
                    <TableCell><Chip size="small" label="SELL" color="error" /></TableCell>
                    <TableCell align="right">${strikePreview.atm?.ce_premium?.toFixed(2)}</TableCell>
                    <TableCell align="right">1</TableCell>
                  </TableRow>
                  {/* ATM PE Sell */}
                  <TableRow>
                    <TableCell>ATM</TableCell>
                    <TableCell>{strikePreview.atm?.strike}</TableCell>
                    <TableCell><Chip size="small" label="PE" color="error" /></TableCell>
                    <TableCell><Chip size="small" label="SELL" color="error" /></TableCell>
                    <TableCell align="right">${strikePreview.atm?.pe_premium?.toFixed(2)}</TableCell>
                    <TableCell align="right">1</TableCell>
                  </TableRow>
                  {/* OTM CE Buy */}
                  <TableRow sx={{ bgcolor: 'success.light', opacity: 0.7 }}>
                    <TableCell>OTM Buy</TableCell>
                    <TableCell>{strikePreview.otm_ce_buy?.strike}</TableCell>
                    <TableCell><Chip size="small" label="CE" color="success" /></TableCell>
                    <TableCell><Chip size="small" label="BUY" color="primary" /></TableCell>
                    <TableCell align="right">${strikePreview.otm_ce_buy?.premium?.toFixed(2)}</TableCell>
                    <TableCell align="right">2</TableCell>
                  </TableRow>
                  {/* OTM PE Buy */}
                  <TableRow sx={{ bgcolor: 'success.light', opacity: 0.7 }}>
                    <TableCell>OTM Buy</TableCell>
                    <TableCell>{strikePreview.otm_pe_buy?.strike}</TableCell>
                    <TableCell><Chip size="small" label="PE" color="error" /></TableCell>
                    <TableCell><Chip size="small" label="BUY" color="primary" /></TableCell>
                    <TableCell align="right">${strikePreview.otm_pe_buy?.premium?.toFixed(2)}</TableCell>
                    <TableCell align="right">2</TableCell>
                  </TableRow>
                  {/* Far OTM CE Sell */}
                  <TableRow sx={{ bgcolor: 'error.light', opacity: 0.5 }}>
                    <TableCell>Far OTM</TableCell>
                    <TableCell>{strikePreview.far_otm_ce?.strike}</TableCell>
                    <TableCell><Chip size="small" label="CE" color="success" /></TableCell>
                    <TableCell><Chip size="small" label="SELL" color="error" /></TableCell>
                    <TableCell align="right">${strikePreview.far_otm_ce?.premium?.toFixed(2)}</TableCell>
                    <TableCell align="right">1</TableCell>
                  </TableRow>
                  {/* Far OTM PE Sell */}
                  <TableRow sx={{ bgcolor: 'error.light', opacity: 0.5 }}>
                    <TableCell>Far OTM</TableCell>
                    <TableCell>{strikePreview.far_otm_pe?.strike}</TableCell>
                    <TableCell><Chip size="small" label="PE" color="error" /></TableCell>
                    <TableCell><Chip size="small" label="SELL" color="error" /></TableCell>
                    <TableCell align="right">${strikePreview.far_otm_pe?.premium?.toFixed(2)}</TableCell>
                    <TableCell align="right">1</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>

            {/* Summary */}
            <Box sx={{ mt: 1, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Chip 
                label={`Net Premium: $${(
                  (strikePreview.atm?.ce_premium || 0) +
                  (strikePreview.atm?.pe_premium || 0) +
                  (strikePreview.far_otm_ce?.premium || 0) +
                  (strikePreview.far_otm_pe?.premium || 0) -
                  2 * (strikePreview.otm_ce_buy?.premium || 0) -
                  2 * (strikePreview.otm_pe_buy?.premium || 0)
                ).toFixed(2)}`}
                color="primary"
                variant="outlined"
              />
              <Chip 
                label={`Spot: $${strikePreview.spot_price?.toLocaleString()}`}
                variant="outlined"
              />
            </Box>
          </Box>
        )}

        {/* Create Session Button */}
        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            variant="contained"
            color="success"
            size="large"
            startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <StartIcon />}
            onClick={handleCreateSession}
            disabled={loading || !expiry}
            sx={{
              px: 4,
              py: 1.5,
              fontWeight: 600,
              background: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)',
              '&:hover': {
                background: 'linear-gradient(135deg, #16a34a 0%, #15803d 100%)',
              }
            }}
          >
            {loading ? 'Creating & Starting...' : 'Create & Start Session'}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};

// PropTypes
SSRAlgoConfigPanel.propTypes = {
  /** Callback when a new session is created */
  onSessionCreated: PropTypes.func,
};

SSRAlgoConfigPanel.defaultProps = {
  onSessionCreated: () => {},
};

export default SSRAlgoConfigPanel;
