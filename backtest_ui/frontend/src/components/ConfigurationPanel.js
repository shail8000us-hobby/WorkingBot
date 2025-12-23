import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Grid,
  FormControlLabel,
  Switch,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  CircularProgress,
  Divider
} from '@mui/material';
import { PlayArrow, Settings, Stop, HourglassEmpty } from '@mui/icons-material';
import { LocalizationProvider, DatePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import axios from 'axios';

export default function ConfigurationPanel({ onBacktestStart, refreshTrigger, currentBacktest }) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [backtestStatus, setBacktestStatus] = useState(null);
  
  // Form state
  const [symbol, setSymbol] = useState('BTC/USD:USD');
  const [timeframe, setTimeframe] = useState('1m');
  const [startDate, setStartDate] = useState(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)); // 1 week ago
  const [endDate, setEndDate] = useState(new Date());
  const [assumeMaker, setAssumeMaker] = useState(true);
  const [fundingMode, setFundingMode] = useState('off');
  const [sameBarPriority, setSameBarPriority] = useState('tp_first');
  const [isTestnet, setIsTestnet] = useState(false);
  
  // Advanced settings
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [customRef, setCustomRef] = useState('');
  const [customStep, setCustomStep] = useState('');
  const [customLot, setCustomLot] = useState('');
  const [customMaxOpen, setCustomMaxOpen] = useState('');

  // Load config on mount
  useEffect(() => {
    loadConfig();
  }, [refreshTrigger]);

  // Poll for backtest status when running
  useEffect(() => {
    if (!currentBacktest) {
      setBacktestStatus(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(`/api/backtest/${currentBacktest}/status`);
        if (response.data.success) {
          setBacktestStatus(response.data.status);
          
          // Stop polling if completed or failed
          if (response.data.status === 'completed' || response.data.status === 'failed') {
            setLoading(false);
            clearInterval(pollInterval);
          }
        }
      } catch (err) {
        console.error('Failed to fetch backtest status:', err);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [currentBacktest]);

  const loadConfig = async () => {
    try {
      const response = await axios.get('/api/config');
      if (response.data.success) {
        setConfig(response.data.config);
        setSymbol(response.data.config.symbol);
      }
    } catch (err) {
      console.error('Failed to load config:', err);
      setError('Failed to load configuration');
    }
  };

  const handleRunBacktest = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Format dates
      const formatDate = (date) => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
      };

      // Build params
      const params = {
        symbol,
        timeframe,
        start: formatDate(startDate),
        end: formatDate(endDate),
        assume_maker: assumeMaker,
        funding_mode: fundingMode,
        same_bar_priority: sameBarPriority,
        is_testnet: isTestnet
      };

      // Add custom overrides if provided
      if (customRef) params.ref = parseFloat(customRef);
      if (customStep) params.step = parseFloat(customStep);
      if (customLot) params.lot = parseFloat(customLot);
      if (customMaxOpen) params.max_open = parseInt(customMaxOpen);

      // Start backtest
      const response = await axios.post('/api/backtest/run', params);

      if (response.data.success) {
        setSuccess(`Backtest started! ID: ${response.data.backtest_id}`);
        onBacktestStart(response.data.backtest_id);
      } else {
        setError(response.data.error || 'Failed to start backtest');
      }
    } catch (err) {
      console.error('Failed to run backtest:', err);
      setError(err.response?.data?.error || 'Failed to start backtest');
    } finally {
      setLoading(false);
    }
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Configure Backtest
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
            {success}
          </Alert>
        )}

        <Card>
          <CardContent>
            <Grid container spacing={3}>
              {/* Basic Settings */}
              <Grid item xs={12}>
                <Typography variant="h6" gutterBottom>
                  Basic Settings
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Symbol"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  helperText="Trading pair (e.g., BTC/USD:USD)"
                  disabled={loading}
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <FormControl fullWidth disabled={loading}>
                  <InputLabel>Timeframe</InputLabel>
                  <Select
                    value={timeframe}
                    label="Timeframe"
                    onChange={(e) => setTimeframe(e.target.value)}
                  >
                    <MenuItem value="1m">1 Minute</MenuItem>
                    <MenuItem value="5m">5 Minutes</MenuItem>
                    <MenuItem value="15m">15 Minutes</MenuItem>
                    <MenuItem value="1h">1 Hour</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} md={6}>
                <DatePicker
                  label="Start Date"
                  value={startDate}
                  onChange={(newValue) => setStartDate(newValue)}
                  renderInput={(params) => <TextField {...params} fullWidth />}
                  slotProps={{ textField: { fullWidth: true } }}
                  disabled={loading}
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <DatePicker
                  label="End Date"
                  value={endDate}
                  onChange={(newValue) => setEndDate(newValue)}
                  renderInput={(params) => <TextField {...params} fullWidth />}
                  slotProps={{ textField: { fullWidth: true } }}
                  disabled={loading}
                />
              </Grid>

              {/* Grid Config Display */}
              {config && (
                <Grid item xs={12}>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Current Grid Configuration (from grid_config.env)
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1 }}>
                    <Typography variant="body2">REF: {config.ref}</Typography>
                    <Typography variant="body2">STEP: {config.step}</Typography>
                    <Typography variant="body2">LOT: {config.lot}</Typography>
                    <Typography variant="body2">MAX_OPEN: {config.max_open}</Typography>
                    <Typography variant="body2">LOWER: {config.lower}</Typography>
                    <Typography variant="body2">UPPER: {config.upper}</Typography>
                  </Box>
                </Grid>
              )}

              {/* Advanced Settings */}
              <Grid item xs={12}>
                <Button
                  startIcon={<Settings />}
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  disabled={loading}
                >
                  {showAdvanced ? 'Hide' : 'Show'} Advanced Settings
                </Button>
              </Grid>

              {showAdvanced && (
                <>
                  <Grid item xs={12}>
                    <Divider />
                    <Typography variant="h6" sx={{ mt: 2 }} gutterBottom>
                      Advanced Settings
                    </Typography>
                  </Grid>

                  <Grid item xs={12} md={6}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={assumeMaker}
                          onChange={(e) => setAssumeMaker(e.target.checked)}
                          disabled={loading}
                        />
                      }
                      label="Assume Maker Fees (0.02%)"
                      disabled={loading}
                    />
                  </Grid>

                  <Grid item xs={12} md={6}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={isTestnet}
                          onChange={(e) => setIsTestnet(e.target.checked)}
                          disabled={loading}
                        />
                      }
                      label="Use Testnet Data"
                      disabled={loading}
                    />
                  </Grid>

                  <Grid item xs={12} md={6}>
                    <FormControl fullWidth disabled={loading}>
                      <InputLabel>Funding Mode</InputLabel>
                      <Select
                        value={fundingMode}
                        label="Funding Mode"
                        onChange={(e) => setFundingMode(e.target.value)}
                      >
                        <MenuItem value="off">Off (No Funding)</MenuItem>
                        <MenuItem value="simple">Simple (0.01% per 8h)</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>

                  <Grid item xs={12} md={6}>
                    <FormControl fullWidth disabled={loading}>
                      <InputLabel>Same-Bar Priority</InputLabel>
                      <Select
                        value={sameBarPriority}
                        label="Same-Bar Priority"
                        onChange={(e) => setSameBarPriority(e.target.value)}
                      >
                        <MenuItem value="tp_first">TP First (Optimistic)</MenuItem>
                        <MenuItem value="buy_first">BUY First (Conservative)</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>

                  <Grid item xs={12}>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      Grid Parameter Overrides (leave empty to use grid_config.env)
                    </Typography>
                  </Grid>

                  <Grid item xs={12} md={3}>
                    <TextField
                      fullWidth
                      label="Custom REF"
                      type="number"
                      value={customRef}
                      onChange={(e) => setCustomRef(e.target.value)}
                      helperText="Reference price"
                      disabled={loading}
                    />
                  </Grid>

                  <Grid item xs={12} md={3}>
                    <TextField
                      fullWidth
                      label="Custom STEP"
                      type="number"
                      value={customStep}
                      onChange={(e) => setCustomStep(e.target.value)}
                      helperText="Grid step size"
                      disabled={loading}
                    />
                  </Grid>

                  <Grid item xs={12} md={3}>
                    <TextField
                      fullWidth
                      label="Custom LOT"
                      type="number"
                      value={customLot}
                      onChange={(e) => setCustomLot(e.target.value)}
                      helperText="Position size"
                      disabled={loading}
                    />
                  </Grid>

                  <Grid item xs={12} md={3}>
                    <TextField
                      fullWidth
                      label="Custom MAX_OPEN"
                      type="number"
                      value={customMaxOpen}
                      onChange={(e) => setCustomMaxOpen(e.target.value)}
                      helperText="Max positions"
                      disabled={loading}
                    />
                  </Grid>
                </>
              )}

              {/* Status Display */}
              {loading && backtestStatus && (
                <Grid item xs={12}>
                  <Alert severity="info" icon={<HourglassEmpty />}>
                    <Typography variant="body1" fontWeight="bold">
                      Backtest In Progress
                    </Typography>
                    <Typography variant="body2">
                      Status: {backtestStatus}
                    </Typography>
                    <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                      Please wait... This may take 30-60 seconds depending on date range.
                      Results will appear automatically when complete.
                    </Typography>
                  </Alert>
                </Grid>
              )}

              {/* Run Button */}
              <Grid item xs={12}>
                <Button
                  variant="contained"
                  size="large"
                  fullWidth
                  startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <PlayArrow />}
                  onClick={handleRunBacktest}
                  disabled={loading}
                  sx={{ 
                    mt: 2,
                    bgcolor: loading ? 'warning.main' : 'primary.main',
                    '&:hover': {
                      bgcolor: loading ? 'warning.dark' : 'primary.dark',
                    }
                  }}
                >
                  {loading ? '⏳ Backtest Running - Please Wait...' : '▶ Run Backtest'}
                </Button>
                {loading && (
                  <Typography variant="caption" display="block" align="center" sx={{ mt: 1, color: 'text.secondary' }}>
                    Form is disabled while backtest is running
                  </Typography>
                )}
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Box>
    </LocalizationProvider>
  );
}

