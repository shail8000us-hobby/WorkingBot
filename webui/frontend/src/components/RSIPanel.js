import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Switch,
  FormControlLabel,
  Grid,
  Alert,
  CircularProgress,
  Chip,
  Divider,
  Slider
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Timer
} from 'lucide-react';
import api from '../utils/apiShim';

const RSIPanel = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rsiData, setRsiData] = useState(null);
  const [config, setConfig] = useState({
    enabled: true,
    period: 14,
    long_threshold: 30.0,
    short_threshold: 70.0,
    hysteresis_seconds: 60,
    timeframe: '1h',
    check_interval: 300,
    cache_ttl: 60
  });
  const [botMode, setBotMode] = useState('LONG');
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  useEffect(() => {
    fetchRSIData();
    fetchConfig();
    fetchBotMode();
    
    // Refresh RSI data every 30 seconds
    const interval = setInterval(fetchRSIData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchRSIData = async () => {
    try {
      const response = await api.get('/api/guardian/rsi/status');
      if (response.data.success) {
        setRsiData(response.data.data);
        // Update bot mode from response if available
        if (response.data.data.bot_mode) {
          setBotMode(response.data.data.bot_mode);
        }
      } else {
        console.error('RSI API returned error:', response.data.error);
        setRsiData({ rsi: null, status: 'ERROR', status_text: response.data.error || 'Failed to fetch RSI data' });
      }
    } catch (error) {
      console.error('Error fetching RSI data:', error);
      setRsiData({ rsi: null, status: 'ERROR', status_text: error.message || 'Failed to fetch RSI data' });
    } finally {
      setLoading(false);
    }
  };

  const fetchConfig = async () => {
    try {
      const response = await api.get('/api/yaml-config?section=safety.rsi');
      if (response.data.success && response.data.data) {
        setConfig(prev => ({
          ...prev,
          ...response.data.data
        }));
      }
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  };

  const fetchBotMode = async () => {
    try {
      const response = await api.get('/api/bot/grid-mode');
      if (response.data.success) {
        setBotMode(response.data.mode);
      }
    } catch (error) {
      console.error('Error fetching bot mode:', error);
    }
  };

  const handleConfigChange = (field, value) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // Use the YAML config API format
      const updates = {
        'safety.rsi.enabled': config.enabled,
        'safety.rsi.period': config.period,
        'safety.rsi.long_threshold': config.long_threshold,
        'safety.rsi.short_threshold': config.short_threshold,
        'safety.rsi.hysteresis_seconds': config.hysteresis_seconds,
        'safety.rsi.timeframe': config.timeframe,
        'safety.rsi.check_interval': config.check_interval,
        'safety.rsi.cache_ttl': config.cache_ttl
      };

      const response = await api.post('/api/config/update', {
        updates: updates
      });

      if (response.data.success) {
        setSnackbar({
          open: true,
          message: 'RSI configuration saved successfully',
          severity: 'success'
        });
        // Reload config to get updated values
        setTimeout(() => {
          fetchConfig();
          fetchRSIData();
        }, 500);
      } else {
        throw new Error(response.data.error || 'Failed to save configuration');
      }
    } catch (error) {
      setSnackbar({
        open: true,
        message: error.message || 'Failed to save configuration',
        severity: 'error'
      });
    } finally {
      setSaving(false);
    }
  };

  const getStatusColor = () => {
    if (!rsiData || rsiData.rsi === null || rsiData.rsi === undefined) return 'default';
    return rsiData.should_stop ? 'error' : 'success';
  };

  const getStatusText = () => {
    if (!rsiData || rsiData.rsi === null || rsiData.rsi === undefined) {
      return rsiData?.status_text || 'Unknown';
    }
    return rsiData.status_text || (rsiData.should_stop ? 'STOP' : 'GO');
  };

  if (loading && !rsiData) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%', py: 2 }}>
      {/* Current Status Card */}
      <Card sx={{ mb: 3, bgcolor: 'background.paper' }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Current Status
          </Typography>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body1" color="text.secondary">
                  Current RSI:
                </Typography>
                <Chip
                  label={rsiData?.rsi !== null && rsiData?.rsi !== undefined ? rsiData.rsi.toFixed(2) : 'N/A'}
                  color={getStatusColor()}
                  size="medium"
                  sx={{ fontSize: '1rem', fontWeight: 'bold' }}
                />
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body1" color="text.secondary">
                  Trading Status:
                </Typography>
                <Chip
                  label={getStatusText()}
                  color={getStatusColor()}
                  icon={getStatusColor() === 'error' ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
                  size="medium"
                />
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="body2" color="text.secondary">
                Bot Mode: <strong>{rsiData?.bot_mode || botMode}</strong>
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="body2" color="text.secondary">
                Threshold: <strong>
                  {(rsiData?.bot_mode || botMode) === 'LONG' 
                    ? `RSI <= ${rsiData?.long_threshold || config.long_threshold} (STOP)` 
                    : `RSI >= ${rsiData?.short_threshold || config.short_threshold} (STOP)`
                  }
                </strong>
              </Typography>
            </Grid>
            {rsiData?.hysteresis_active && (
              <Grid item xs={12}>
                <Alert severity="info" icon={<Timer />}>
                  Hysteresis active: {rsiData.hysteresis_seconds}s delay at threshold
                </Alert>
              </Grid>
            )}
          </Grid>
        </CardContent>
      </Card>

      {/* Configuration Card */}
      <Card sx={{ mb: 3, bgcolor: 'background.paper' }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Configuration
          </Typography>
          
          <FormControlLabel
            control={
              <Switch
                checked={config.enabled}
                onChange={(e) => handleConfigChange('enabled', e.target.checked)}
                color="primary"
              />
            }
            label="Enable RSI Monitoring"
            sx={{ mb: 2 }}
          />

          <Divider sx={{ my: 2 }} />

          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography gutterBottom>
                RSI Period: {config.period}
              </Typography>
              <Slider
                value={config.period}
                onChange={(e, value) => handleConfigChange('period', value)}
                min={2}
                max={50}
                step={1}
                marks={[
                  { value: 14, label: '14' },
                  { value: 30, label: '30' }
                ]}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography gutterBottom>
                LONG Mode Threshold: {config.long_threshold}
              </Typography>
              <Slider
                value={config.long_threshold}
                onChange={(e, value) => handleConfigChange('long_threshold', value)}
                min={0}
                max={50}
                step={0.5}
                marks={[
                  { value: 20, label: '20' },
                  { value: 25, label: '25' },
                  { value: 30, label: '30' }
                ]}
              />
              <Typography variant="caption" color="text.secondary">
                STOP when RSI &lt;= this value in LONG mode
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography gutterBottom>
                SHORT Mode Threshold: {config.short_threshold}
              </Typography>
              <Slider
                value={config.short_threshold}
                onChange={(e, value) => handleConfigChange('short_threshold', value)}
                min={50}
                max={100}
                step={0.5}
                marks={[
                  { value: 70, label: '70' },
                  { value: 75, label: '75' },
                  { value: 80, label: '80' }
                ]}
              />
              <Typography variant="caption" color="text.secondary">
                STOP when RSI &gt;= this value in SHORT mode
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography gutterBottom>
                Hysteresis Delay: {config.hysteresis_seconds}s
              </Typography>
              <Slider
                value={config.hysteresis_seconds}
                onChange={(e, value) => handleConfigChange('hysteresis_seconds', value)}
                min={0}
                max={300}
                step={10}
                marks={[
                  { value: 60, label: '60s' },
                  { value: 120, label: '120s' },
                  { value: 300, label: '300s' }
                ]}
              />
              <Typography variant="caption" color="text.secondary">
                Delay before switching signal when RSI is exactly at threshold
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                select
                label="Timeframe"
                value={config.timeframe}
                onChange={(e) => handleConfigChange('timeframe', e.target.value)}
                SelectProps={{ native: true }}
                helperText="OHLCV timeframe for RSI calculation"
              >
                <option value="1h">1 Hour</option>
                <option value="4h">4 Hours</option>
                <option value="1d">1 Day</option>
              </TextField>
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Check Interval (seconds)"
                value={config.check_interval}
                onChange={(e) => handleConfigChange('check_interval', parseInt(e.target.value))}
                helperText="How often to check RSI"
                inputProps={{ min: 60 }}
              />
            </Grid>
          </Grid>

          <Box sx={{ mt: 3, display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
            <Button
              variant="outlined"
              startIcon={<RefreshCw />}
              onClick={fetchRSIData}
            >
              Refresh
            </Button>
            <Button
              variant="contained"
              onClick={handleSave}
              disabled={saving}
              startIcon={saving ? <CircularProgress size={16} /> : <CheckCircle2 />}
            >
              {saving ? 'Saving...' : 'Save Configuration'}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Info Alert */}
      <Alert severity="info" sx={{ mb: 2 }}>
        <Typography variant="body2">
          <strong>How it works:</strong>
          <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
            <li><strong>LONG Mode:</strong> Trading stops when RSI &gt;= {config.long_threshold} (overbought)</li>
            <li><strong>SHORT Mode:</strong> Trading stops when RSI &lt;= {config.short_threshold} (oversold)</li>
            <li><strong>Hysteresis:</strong> When RSI is exactly at the threshold, a {config.hysteresis_seconds}s delay prevents signal jumping</li>
            <li>RSI is calculated from hourly OHLCV candles using a {config.period}-period moving average</li>
          </ul>
        </Typography>
      </Alert>

      {/* Snackbar for notifications */}
      {snackbar.open && (
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          sx={{ position: 'fixed', bottom: 20, right: 20, zIndex: 9999 }}
        >
          {snackbar.message}
        </Alert>
      )}
    </Box>
  );
};

export default RSIPanel;

