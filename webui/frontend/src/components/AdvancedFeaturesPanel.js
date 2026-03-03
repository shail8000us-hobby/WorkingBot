import React, { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Alert, Button, Chip, CircularProgress, TextField, MenuItem, Select, FormControl, InputLabel } from '@mui/material';
import { Database, Download, RefreshCw, Activity, Clock, TrendingUp, BarChart3, Zap, CheckCircle, AlertCircle } from 'lucide-react';

/**
 * Advanced Features Panel
 * 
 * Contains advanced data collection and analysis features:
 * - Delta Exchange Historical Data Fetcher
 * - Live Data Streaming Status
 * - Database Statistics
 * - Technical Indicators
 * 
 * These features are INDEPENDENT and do not impact existing bot functionality.
 * 
 * Author: WorkingBot
 * Date: January 2026
 */

const API_BASE = '/api/delta-data';

// Reusable card component matching WebUI style
const FeatureCard = ({ title, icon: Icon, children, accent = 'blue' }) => {
  const accentColors = {
    blue: 'border-blue-500/50 bg-blue-500/5',
    green: 'border-green-500/50 bg-green-500/5',
    purple: 'border-purple-500/50 bg-purple-500/5',
    amber: 'border-amber-500/50 bg-amber-500/5',
    cyan: 'border-cyan-500/50 bg-cyan-500/5',
  };

  return (
    <div className={`rounded-xl border ${accentColors[accent]} p-4 backdrop-blur`}>
      <div className="flex items-center gap-2 mb-3">
        {Icon && <Icon className="h-5 w-5 text-slate-300" />}
        <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      </div>
      {children}
    </div>
  );
};

// Status badge component
const StatusBadge = ({ status, label }) => {
  const statusColors = {
    healthy: 'bg-green-500/20 text-green-300 border-green-500/30',
    degraded: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    error: 'bg-red-500/20 text-red-300 border-red-500/30',
    loading: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full border ${statusColors[status] || statusColors.loading}`}>
      {status === 'healthy' && <CheckCircle className="h-3 w-3" />}
      {status === 'degraded' && <AlertCircle className="h-3 w-3" />}
      {status === 'error' && <AlertCircle className="h-3 w-3" />}
      {status === 'loading' && <CircularProgress size={10} />}
      {label || status}
    </span>
  );
};

// Module Status Panel
const ModuleStatusPanel = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/health`);
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      setStatus({ status: 'error', error: error.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (loading && !status) {
    return (
      <FeatureCard title="Module Status" icon={Activity} accent="blue">
        <div className="flex items-center justify-center py-4">
          <CircularProgress size={20} />
        </div>
      </FeatureCard>
    );
  }

  return (
    <FeatureCard title="Module Status" icon={Activity} accent="blue">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-400">Overall Status</span>
          <StatusBadge status={status?.status || 'loading'} />
        </div>
        
        {status?.modules && (
          <div className="grid grid-cols-2 gap-2 mt-2">
            {Object.entries(status.modules).map(([name, available]) => (
              <div key={name} className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg">
                <span className="text-xs text-slate-400 capitalize">{name.replace(/_/g, ' ')}</span>
                <StatusBadge status={available ? 'healthy' : 'error'} label={available ? 'OK' : 'N/A'} />
              </div>
            ))}
          </div>
        )}
        
        <button
          onClick={fetchStatus}
          className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-slate-300 bg-slate-800/50 hover:bg-slate-700/50 rounded-lg transition"
        >
          <RefreshCw className="h-3 w-3" />
          Refresh Status
        </button>
      </div>
    </FeatureCard>
  );
};

// Historical Data Fetcher Panel
const HistoricalDataPanel = () => {
  const [symbols, setSymbols] = useState([]);
  const [resolutions, setResolutions] = useState([]);
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSD');
  const [selectedResolution, setSelectedResolution] = useState('1h');
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Fetch available symbols and resolutions
    Promise.all([
      fetch(`${API_BASE}/symbols`).then(r => r.json()),
      fetch(`${API_BASE}/resolutions`).then(r => r.json())
    ]).then(([symbolsData, resolutionsData]) => {
      setSymbols(symbolsData.symbols || []);
      setResolutions(resolutionsData.resolutions || []);
    }).catch(console.error);
  }, []);

  const handleFetch = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE}/fetch-historical`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: selectedSymbol,
          resolution: selectedResolution,
          days: days
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setResult(data);
      } else {
        setError(data.error || 'Failed to fetch data');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <FeatureCard title="Historical Data Fetcher" icon={Download} accent="green">
      <div className="space-y-4">
        <p className="text-xs text-slate-400">
          Fetch historical OHLCV data from Delta Exchange and store in local database for backtesting.
        </p>
        
        <div className="grid grid-cols-3 gap-2">
          <FormControl size="small" fullWidth>
            <InputLabel sx={{ color: 'rgba(148, 163, 184, 0.8)', fontSize: '0.75rem' }}>Symbol</InputLabel>
            <Select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              label="Symbol"
              sx={{
                color: 'rgb(226, 232, 240)',
                fontSize: '0.75rem',
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: 'rgba(51, 65, 85, 0.8)',
                },
                '&:hover .MuiOutlinedInput-notchedOutline': {
                  borderColor: 'rgba(71, 85, 105, 0.8)',
                },
              }}
            >
              {symbols.map(s => (
                <MenuItem key={s.symbol} value={s.symbol}>{s.symbol}</MenuItem>
              ))}
            </Select>
          </FormControl>
          
          <FormControl size="small" fullWidth>
            <InputLabel sx={{ color: 'rgba(148, 163, 184, 0.8)', fontSize: '0.75rem' }}>Resolution</InputLabel>
            <Select
              value={selectedResolution}
              onChange={(e) => setSelectedResolution(e.target.value)}
              label="Resolution"
              sx={{
                color: 'rgb(226, 232, 240)',
                fontSize: '0.75rem',
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: 'rgba(51, 65, 85, 0.8)',
                },
              }}
            >
              {resolutions.map(r => (
                <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          
          <TextField
            size="small"
            type="number"
            label="Days"
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value) || 30)}
            InputProps={{ inputProps: { min: 1, max: 365 } }}
            sx={{
              '& .MuiInputBase-input': { color: 'rgb(226, 232, 240)', fontSize: '0.75rem' },
              '& .MuiInputLabel-root': { color: 'rgba(148, 163, 184, 0.8)', fontSize: '0.75rem' },
              '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(51, 65, 85, 0.8)' },
            }}
          />
        </div>
        
        <button
          onClick={handleFetch}
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 disabled:bg-slate-600 rounded-lg transition"
        >
          {loading ? (
            <>
              <CircularProgress size={16} color="inherit" />
              Fetching...
            </>
          ) : (
            <>
              <Download className="h-4 w-4" />
              Fetch Historical Data
            </>
          )}
        </button>
        
        {error && (
          <Alert severity="error" sx={{ fontSize: '0.75rem' }}>
            {error}
          </Alert>
        )}
        
        {result && (
          <Alert severity="success" sx={{ fontSize: '0.75rem' }}>
            Successfully fetched {result.days} days of {result.symbol} ({result.resolution}) data
          </Alert>
        )}
      </div>
    </FeatureCard>
  );
};

// Helper to format value for display
const formatStatValue = (value) => {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'number') return value.toLocaleString();
  if (typeof value === 'string') return value;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return `${value.length} items`;
  if (typeof value === 'object') {
    // Handle date_range object
    if (value.start && value.end) {
      return `${value.start} → ${value.end}`;
    }
    return JSON.stringify(value);
  }
  return String(value);
};

// Database Statistics Panel
const DatabaseStatsPanel = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/database/stats`);
      const data = await response.json();
      setStats(data.stats);
    } catch (error) {
      console.error('Failed to fetch database stats:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // Filter out complex nested arrays for simple display
  const simpleStats = stats ? Object.entries(stats).filter(([key, value]) => {
    // Skip symbol_stats array (show separately)
    if (key === 'symbol_stats') return false;
    return true;
  }) : [];

  return (
    <FeatureCard title="Database Statistics" icon={Database} accent="purple">
      {loading ? (
        <div className="flex items-center justify-center py-4">
          <CircularProgress size={20} />
        </div>
      ) : stats ? (
        <div className="space-y-2">
          {/* Simple stats */}
          {simpleStats.map(([key, value]) => (
            <div key={key} className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg">
              <span className="text-xs text-slate-400 capitalize">{key.replace(/_/g, ' ')}</span>
              <span className="text-sm font-mono text-slate-200">
                {formatStatValue(value)}
              </span>
            </div>
          ))}
          
          {/* Symbol stats breakdown */}
          {stats.symbol_stats && stats.symbol_stats.length > 0 && (
            <div className="mt-2 p-2 bg-slate-800/30 rounded-lg">
              <p className="text-xs text-slate-400 mb-2">By Symbol:</p>
              {stats.symbol_stats.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between text-xs py-1">
                  <span className="text-slate-300">{item.symbol} ({item.resolution})</span>
                  <span className="text-slate-400 font-mono">{item.count?.toLocaleString()} candles</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-slate-500 text-center py-4">
          No database statistics available. Fetch some historical data first.
        </p>
      )}
      
      <button
        onClick={fetchStats}
        className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-slate-300 bg-slate-800/50 hover:bg-slate-700/50 rounded-lg transition"
      >
        <RefreshCw className="h-3 w-3" />
        Refresh Stats
      </button>
    </FeatureCard>
  );
};

// OHLCV Data Viewer Panel
const OHLCVViewerPanel = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [symbol, setSymbol] = useState('BTCUSD');
  const [resolution, setResolution] = useState('1h');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/ohlcv?symbol=${symbol}&resolution=${resolution}&days=7&limit=50`);
      const result = await response.json();
      setData(result.data || []);
    } catch (error) {
      console.error('Failed to fetch OHLCV:', error);
    } finally {
      setLoading(false);
    }
  }, [symbol, resolution]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <FeatureCard title="OHLCV Data Preview" icon={BarChart3} accent="cyan">
      <div className="space-y-3">
        <div className="flex gap-2">
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="flex-1 px-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-200"
          >
            <option value="BTCUSD">BTCUSD</option>
            <option value="ETHUSD">ETHUSD</option>
            <option value="BTCUSDT">BTCUSDT</option>
            <option value="ETHUSDT">ETHUSDT</option>
          </select>
          
          <select
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            className="flex-1 px-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-200"
          >
            <option value="1m">1m</option>
            <option value="5m">5m</option>
            <option value="15m">15m</option>
            <option value="1h">1h</option>
            <option value="4h">4h</option>
            <option value="1d">1d</option>
          </select>
          
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1 text-xs font-medium text-slate-300 bg-slate-800/50 hover:bg-slate-700/50 rounded-lg transition"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
        
        {loading ? (
          <div className="flex items-center justify-center py-4">
            <CircularProgress size={20} />
          </div>
        ) : data.length > 0 ? (
          <div className="max-h-48 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-900">
                <tr className="text-slate-400">
                  <th className="text-left p-1">Time</th>
                  <th className="text-right p-1">Open</th>
                  <th className="text-right p-1">High</th>
                  <th className="text-right p-1">Low</th>
                  <th className="text-right p-1">Close</th>
                </tr>
              </thead>
              <tbody>
                {data.slice(-10).map((row, i) => (
                  <tr key={i} className="text-slate-300 border-t border-slate-800">
                    <td className="p-1 font-mono">{row.datetime?.split('T')[1]?.slice(0, 5) || '-'}</td>
                    <td className="text-right p-1">{row.open?.toFixed(2)}</td>
                    <td className="text-right p-1 text-green-400">{row.high?.toFixed(2)}</td>
                    <td className="text-right p-1 text-red-400">{row.low?.toFixed(2)}</td>
                    <td className="text-right p-1 font-medium">{row.close?.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-slate-500 text-center py-4">
            No data available. Fetch historical data first.
          </p>
        )}
        
        {data.length > 0 && (
          <p className="text-xs text-slate-500 text-center">
            Showing last 10 of {data.length} candles
          </p>
        )}
      </div>
    </FeatureCard>
  );
};

// Live Streaming Status Panel
const LiveStreamingPanel = () => {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/stream/status`)
      .then(r => r.json())
      .then(setStatus)
      .catch(console.error);
  }, []);

  return (
    <FeatureCard title="Live Streaming" icon={Zap} accent="amber">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-400">Status</span>
          <StatusBadge 
            status={status?.streaming ? 'healthy' : 'degraded'} 
            label={status?.streaming ? 'Active' : 'Inactive'} 
          />
        </div>
        
        <p className="text-xs text-slate-500">
          {status?.message || 'Live WebSocket streaming for real-time OHLCV data.'}
        </p>
        
        <div className="p-2 bg-slate-800/30 rounded-lg">
          <p className="text-xs text-amber-400/80">
            ℹ️ Live streaming is available through the bot's WebSocket infrastructure. 
            This panel shows monitoring status.
          </p>
        </div>
      </div>
    </FeatureCard>
  );
};

// Technical Indicators Panel
const TechnicalIndicatorsPanel = () => {
  const [indicatorData, setIndicatorData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchIndicators = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch(`${API_BASE}/indicators/calculate?symbol=BTCUSD&resolution=1h&days=30`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();
        console.log('Indicators calculated:', data);
        setIndicatorData(data);
      } catch (err) {
        console.error('Failed to fetch indicators:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchIndicators();
  }, []);

  // Format indicator value for display
  const formatValue = (indicator) => {
    if (!indicator || indicator.value === null) return 'N/A';
    
    // Handle different indicator types
    if (indicator.upper !== undefined) {
      // Bollinger Bands
      return `${indicator.upper?.toLocaleString()} / ${indicator.middle?.toLocaleString()} / ${indicator.lower?.toLocaleString()}`;
    }
    if (indicator.signal !== undefined) {
      // MACD
      return `${indicator.value} (Signal: ${indicator.signal})`;
    }
    if (indicator.ratio !== undefined) {
      // Volume Profile
      return `${indicator.current?.toLocaleString()} (${indicator.ratio}x avg)`;
    }
    
    return indicator.value?.toLocaleString() || 'N/A';
  };

  // Get color based on indicator value
  const getIndicatorColor = (name, indicator) => {
    if (!indicator) return 'rgba(148, 163, 184, 0.3)';
    
    if (name === 'rsi') {
      const val = indicator.value;
      if (val >= 70) return 'rgba(239, 68, 68, 0.6)'; // Overbought - red
      if (val <= 30) return 'rgba(34, 197, 94, 0.6)'; // Oversold - green
      return 'rgba(251, 191, 36, 0.5)'; // Neutral - yellow
    }
    if (name === 'macd') {
      return indicator.histogram > 0 ? 'rgba(34, 197, 94, 0.6)' : 'rgba(239, 68, 68, 0.6)';
    }
    if (name === 'volume_profile') {
      return indicator.ratio > 1.5 ? 'rgba(34, 197, 94, 0.6)' : 'rgba(148, 163, 184, 0.3)';
    }
    
    return 'rgba(139, 92, 246, 0.4)'; // Purple default
  };

  return (
    <FeatureCard title="Technical Indicators" icon={TrendingUp} accent="purple">
      <div className="space-y-2">
        {loading && (
          <div className="flex items-center justify-center py-2">
            <CircularProgress size={16} />
            <span className="ml-2 text-xs text-slate-400">Calculating indicators...</span>
          </div>
        )}
        
        {error && (
          <p className="text-xs text-red-400 text-center py-2">
            Error: {error}
          </p>
        )}
        
        {!loading && !error && indicatorData?.success && (
          <div className="space-y-3">
            {/* Price context */}
            <div className="text-center pb-2 border-b border-slate-700">
              <span className="text-xs text-slate-400">{indicatorData.symbol} Current Price</span>
              <p className="text-lg font-bold text-white">${indicatorData.current_price?.toLocaleString()}</p>
              <span className="text-xs text-slate-500">{indicatorData.data_points} data points</span>
            </div>
            
            {/* Indicator grid */}
            <div className="grid grid-cols-1 gap-2">
              {Object.entries(indicatorData.indicators || {}).map(([name, indicator]) => (
                <div 
                  key={name}
                  className="flex justify-between items-center py-1 px-2 rounded"
                  style={{ backgroundColor: getIndicatorColor(name, indicator) }}
                >
                  <span className="text-xs font-medium text-white">{indicator.label}</span>
                  <span className="text-xs text-slate-200 font-mono">{formatValue(indicator)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {!loading && !error && !indicatorData?.success && (
          <p className="text-xs text-slate-500 text-center py-2">
            {indicatorData?.message || 'No indicator data available. Fetch historical data first.'}
          </p>
        )}
      </div>
    </FeatureCard>
  );
};

// Main Advanced Features Panel
const AdvancedFeaturesPanel = () => {
  return (
    <div className="animate-fade-slide-up">
      <Box sx={{ p: 3 }}>
        {/* Header */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>
            🚀 Advanced Features
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Professional data collection infrastructure. These features are independent and do not impact existing bot functionality.
          </Typography>
        </Box>

        {/* Info Banner */}
        <Alert severity="info" sx={{ mb: 3 }}>
          📊 Delta Exchange data collection modules - fetch historical OHLCV data, monitor live streams, and analyze with technical indicators.
        </Alert>

        {/* Feature Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Module Status */}
          <ModuleStatusPanel />
          
          {/* Historical Data Fetcher */}
          <HistoricalDataPanel />
          
          {/* Database Statistics */}
          <DatabaseStatsPanel />
          
          {/* OHLCV Viewer */}
          <OHLCVViewerPanel />
          
          {/* Live Streaming */}
          <LiveStreamingPanel />
          
          {/* Technical Indicators */}
          <TechnicalIndicatorsPanel />
        </div>
        
        {/* Documentation Link */}
        <Box sx={{ mt: 4, p: 2, bgcolor: 'rgba(30, 41, 59, 0.5)', borderRadius: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
            💡 <strong>Tip:</strong> Use the Historical Data Fetcher to collect OHLCV data for backtesting. 
            The data is stored in a local SQLite database and can be accessed via the data provider API.
          </Typography>
        </Box>
      </Box>
    </div>
  );
};

export default AdvancedFeaturesPanel;
