import React, { useState, useEffect, useCallback } from 'react';
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
  Slider,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Timer,
  Activity
} from 'lucide-react';
import api from '../utils/apiShim';
import { useInstance, parseInstanceName } from '../context/InstanceContext';
import SymbolBadge from './common/SymbolBadge';

/**
 * RSIPanel - Multi-Symbol RSI Monitoring (v5.0)
 * 
 * Features:
 * - Shows RSI for current symbol or all symbols
 * - Symbol-aware configuration
 * - Toggle between single symbol and all symbols view
 */
const RSIPanel = () => {
  const { selectedInstance, instances, withInstance } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const selectedSymbol = instanceInfo?.symbol; // backward compat
  const selectedMode = instanceInfo?.mode || 'LONG';
  const symbols = instances.map(i => ({ name: parseInstanceName(i.name)?.symbol })).filter((v, i, a) => a.findIndex(t => t.name === v.name) === i);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [viewMode, setViewMode] = useState('current'); // 'current' or 'all'
  const [currentSymbol, setCurrentSymbol] = useState(selectedSymbol || 'BTCUSD'); // Track current symbol for single view
  const [rsiData, setRsiData] = useState(null);
  const [allSymbolsRsi, setAllSymbolsRsi] = useState({});
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
  const [botMode, setBotMode] = useState(selectedMode);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  // Update current symbol when instance changes
  useEffect(() => {
    if (selectedSymbol) {
      setCurrentSymbol(selectedSymbol);
    }
  }, [selectedSymbol]);

  // Fetch RSI data - now instance-aware  
  const fetchRSIData = useCallback(async () => {
    try {
      if (viewMode === 'all') {
        // Fetch RSI for all symbols
        const response = await api.get('/api/guardian/rsi/status');
        if (response.data.success) {
          // Handle both response formats (symbols array or data object)
          if (response.data.symbols) {
            setAllSymbolsRsi(response.data.symbols);
            // Also update current symbol data
            if (currentSymbol && response.data.symbols[currentSymbol]) {
              setRsiData(response.data.symbols[currentSymbol]);
            }
          } else if (response.data.data) {
            // Single symbol response - convert to all symbols format
            const symbolData = { [currentSymbol || 'BTCUSD']: response.data.data };
            setAllSymbolsRsi(symbolData);
            setRsiData(response.data.data);
          }
        }
      } else {
        // Fetch RSI for current selected symbol with explicit symbol parameter
        const symbolParam = currentSymbol || 'BTCUSD';
        const response = await api.get(`/api/guardian/rsi/status?symbol=${symbolParam}`);
        if (response.data.success && response.data.data) {
          setRsiData(response.data.data);
          if (response.data.data?.bot_mode) {
            setBotMode(response.data.data.bot_mode);
          }
        } else {
          setRsiData({ rsi: null, status: 'ERROR', status_text: response.data.error || 'Failed to fetch RSI' });
        }
      }
    } catch (error) {
      console.error('Error fetching RSI data:', error);
      setRsiData({ rsi: null, status: 'ERROR', status_text: error.message || 'Failed to fetch RSI data' });
    } finally {
      setLoading(false);
    }
  }, [currentSymbol, viewMode]);

  useEffect(() => {
    fetchRSIData();
    fetchConfig();
    
    const interval = setInterval(fetchRSIData, 30000);
    return () => clearInterval(interval);
  }, [fetchRSIData]);

  // Re-fetch when instance changes
  useEffect(() => {
    fetchRSIData();
    fetchConfig();
  }, [selectedInstance, fetchRSIData]);

  const fetchConfig = async () => {
    try {
      // Fetch instance-specific RSI config if available
      const response = await api.get(withInstance('/api/yaml-config?section=safety.rsi'));
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

  const handleConfigChange = (field, value) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
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

  const getStatusColor = (data = rsiData) => {
    if (!data || data.rsi === null || data.rsi === undefined) return 'default';
    return data.should_stop ? 'error' : 'success';
  };

  const getStatusText = (data = rsiData) => {
    if (!data || data.rsi === null || data.rsi === undefined) {
      return data?.status_text || 'Unknown';
    }
    return data.status_text || (data.should_stop ? 'STOP' : 'GO');
  };

  // Symbol color helper
  const getSymbolColor = (symbol) => {
    const colors = {
      BTCUSD: { bg: 'bg-orange-500/20', border: 'border-orange-500', text: 'text-orange-400' },
      ETHUSD: { bg: 'bg-blue-500/20', border: 'border-blue-500', text: 'text-blue-400' }
    };
    return colors[symbol] || { bg: 'bg-slate-500/20', border: 'border-slate-500', text: 'text-slate-400' };
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
      {/* View Mode Toggle & Symbol Indicator */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Activity size={20} />
            RSI Safety Monitor
          </Typography>
          {viewMode === 'current' && currentSymbol && (
            <SymbolBadge symbol={currentSymbol} />
          )}
        </Box>
        
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          {/* Symbol Selector for Current View */}
          {viewMode === 'current' && (
            <ToggleButtonGroup
              value={currentSymbol}
              exclusive
              onChange={(e, newSymbol) => newSymbol && setCurrentSymbol(newSymbol)}
              size="small"
              sx={{ mr: 1 }}
            >
              <ToggleButton value="BTCUSD">
                BTC
              </ToggleButton>
              <ToggleButton value="ETHUSD">
                ETH
              </ToggleButton>
            </ToggleButtonGroup>
          )}
          
          {/* View Mode Toggle */}
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={(e, newMode) => newMode && setViewMode(newMode)}
            size="small"
          >
            <ToggleButton value="current">
              Current Symbol
            </ToggleButton>
            <ToggleButton value="all">
              All Symbols
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>

      {/* All Symbols View */}
      {viewMode === 'all' && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {Object.entries(allSymbolsRsi).map(([symbol, data]) => (
            <Grid item xs={12} md={6} key={symbol}>
              <RSISymbolCard 
                symbol={symbol} 
                data={data}
                getStatusColor={getStatusColor}
                getSymbolColor={getSymbolColor}
              />
            </Grid>
          ))}
          {Object.keys(allSymbolsRsi).length === 0 && (
            <Grid item xs={12}>
              <Alert severity="info">
                No RSI data available. Enable symbols in configuration first.
              </Alert>
            </Grid>
          )}
        </Grid>
      )}

      {/* Current Symbol Status Card */}
      {viewMode === 'current' && (
        <Card sx={{ mb: 3, bgcolor: 'background.paper' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
              <Typography variant="h6">
                Current Status
              </Typography>
              <SymbolBadge symbol={currentSymbol} size="small" />
            </Box>
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
      )}

      {/* Configuration Card */}
      <Card sx={{ mb: 3, bgcolor: 'background.paper' }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Configuration (Global RSI Settings)
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
          <strong>Multi-Symbol RSI:</strong> RSI is calculated independently for each symbol.
          Use "All Symbols" view to monitor RSI across all enabled instruments simultaneously.
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

/**
 * RSI Card for individual symbol in "All Symbols" view
 */
const RSISymbolCard = ({ symbol, data, getStatusColor, getSymbolColor }) => {
  const colors = getSymbolColor(symbol);
  
  return (
    <Card 
      sx={{ 
        bgcolor: 'background.paper',
        borderLeft: 4,
        borderColor: symbol === 'BTCUSD' ? 'warning.main' : 'info.main'
      }}
    >
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SymbolBadge symbol={symbol} />
            <Typography variant="subtitle2" color="text.secondary">
              {data?.bot_mode || 'LONG'} Mode
            </Typography>
          </Box>
          <Chip
            label={data?.status || 'UNKNOWN'}
            color={getStatusColor(data)}
            size="small"
          />
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 1 }}>
          <Typography variant="h3" sx={{ fontWeight: 700 }}>
            {data?.rsi !== null && data?.rsi !== undefined ? data.rsi.toFixed(1) : '—'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            RSI
          </Typography>
        </Box>
        
        <Typography variant="caption" color="text.secondary">
          Threshold: {data?.bot_mode === 'SHORT' 
            ? `≥ ${data?.short_threshold || 70}` 
            : `≤ ${data?.long_threshold || 30}`
          }
        </Typography>
      </CardContent>
    </Card>
  );
};

export default RSIPanel;

