import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react';
import clsx from 'clsx';
import {
  Line,
  LineChart,
  ResponsiveContainer,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ReferenceLine
} from 'recharts';
import { RefreshCcw, DollarSign } from 'lucide-react';
import { useInstance, parseInstanceName } from '../../context/InstanceContext';

const TIMEFRAMES = [
  { value: 'hourly', label: 'Hourly', rvKey: '1h', description: 'Rolling 24-hour window' },
  { value: 'daily', label: 'Daily', rvKey: '1d', description: 'Last 32 hours' },
  { value: 'weekly', label: 'Weekly', rvKey: '7d', description: 'Last 8 days' },
  { value: 'monthly', label: 'Monthly', rvKey: '30d', description: 'Last 5 weeks' }
];

const REFRESH_INTERVAL_MS = 30000;

const normalizeTimestamp = (raw) => {
  const timestamp = Number(raw);
  if (!Number.isFinite(timestamp)) {
    return null;
  }
  return timestamp > 1e12 ? timestamp : timestamp * 1000;
};

const normalizeValue = (raw) => {
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
};

const mergeSeries = (ivSeries = [], rvSeries = []) => {
  const merged = new Map();

  ivSeries.forEach((point) => {
    const timestamp = normalizeTimestamp(point?.timestamp ?? point?.time ?? point?.t);
    if (!timestamp) return;
    const value = normalizeValue(point?.value ?? point?.iv ?? point?.iv_value);
    merged.set(timestamp, { timestamp, iv: value, rv: null });
  });

  rvSeries.forEach((point) => {
    const timestamp = normalizeTimestamp(point?.timestamp ?? point?.time ?? point?.t);
    if (!timestamp) return;
    const value = normalizeValue(point?.value ?? point?.rv ?? point?.rv_value);
    const existing = merged.get(timestamp);
    if (existing) {
      merged.set(timestamp, { ...existing, rv: value });
    } else {
      merged.set(timestamp, { timestamp, iv: null, rv: value });
    }
  });

  return Array.from(merged.values()).sort((a, b) => a.timestamp - b.timestamp);
};

const formatPercent = (value, { showSign = false } = {}) => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  const numeric = Number(value);
  const prefix = showSign && numeric > 0 ? '+' : '';
  return `${prefix}${numeric.toFixed(2)}%`;
};

const formatTimestamp = (timestamp) => {
  if (!timestamp) return 'Never';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return 'Invalid';
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    day: '2-digit',
    month: 'short',
    hour12: false
  }).format(date);
};

const buildTickFormatter = (timeframe, chartData = []) => (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  
  if (timeframe === 'hourly') {
    // For hourly view, show HH:MM format
    return new Intl.DateTimeFormat('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).format(date);
  }
  
  if (timeframe === 'daily') {
    // For daily view, show day of week
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    return days[date.getDay()];
  }
  
  if (timeframe === 'weekly') {
    // For weekly view, show actual dates (4 weeks of data)
    return new Intl.DateTimeFormat('en-IN', {
      month: 'short',
      day: 'numeric'
    }).format(date);
  }
  
  if (timeframe === 'monthly') {
    // For monthly view, show actual dates (3 months of data)
    return new Intl.DateTimeFormat('en-IN', {
      month: 'short',
      day: 'numeric'
    }).format(date);
  }
  
  // Default: show date with month
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short'
  }).format(date);
};

// Generate hourly tick marks for 24-hour rolling window
const generateHourlyTicks = (data) => {
  // For rolling 24-hour window, generate exactly 24 ticks
  const now = Date.now();
  const hourMs = 60 * 60 * 1000;
  const windowStart = now - (24 * hourMs);
  
  // Round windowStart down to the nearest hour for cleaner labels
  const startHour = Math.floor(windowStart / hourMs) * hourMs;
  
  // Generate 25 ticks (24 hours + current hour) for better coverage
  const ticks = [];
  for (let i = 0; i <= 24; i++) {
    ticks.push(startHour + (i * hourMs));
  }
  
  return ticks;
};

// Generate weekly tick marks for 4-week chart (always show 4 weeks from now back)
const generateWeeklyTicks = (data) => {
  const ticks = [];
  const now = Date.now();
  const weekMs = 7 * 24 * 60 * 60 * 1000;
  
  // Always show 4 weeks back from now
  const startTime = now - (4 * weekMs);
  
  // Generate 5 ticks: start of 4 weeks ago, then each week boundary, then now
  ticks.push(startTime);
  ticks.push(startTime + weekMs);
  ticks.push(startTime + (2 * weekMs));
  ticks.push(startTime + (3 * weekMs));
  ticks.push(now);
  
  return ticks;
};

// Generate monthly tick marks for 3-month chart (always show 3 months from now back)
const generateMonthlyTicks = (data) => {
  const ticks = [];
  const now = Date.now();
  const monthMs = 30 * 24 * 60 * 60 * 1000;
  
  // Always show 3 months back from now
  const startTime = now - (3 * monthMs);
  
  // Generate 4 ticks: start of 3 months ago, then each month boundary, then now
  ticks.push(startTime);
  ticks.push(startTime + monthMs);
  ticks.push(startTime + (2 * monthMs));
  ticks.push(now);
  
  return ticks;
};

const CustomTooltip = ({ active, payload, timeframe, monthlyAverages }) => {
  if (!active || !payload || !payload.length) return null;
  const datum = payload[0].payload || {};
  const { timestamp, iv, rv } = datum;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/95 px-4 py-3 text-xs text-slate-200 shadow-xl backdrop-blur">
      <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">
        {formatTimestamp(timestamp)}
      </div>
      <div className="mt-2 flex flex-col gap-1">
        <div className="flex flex-col">
          <span className="font-semibold text-rose-300">
            IV · {formatPercent(iv)}
          </span>
          {timeframe === 'hourly' && monthlyAverages.avgIV && iv !== null && iv !== undefined && (
            <span className="text-[10px] text-rose-300/80">
              vs 30d avg: {(iv - monthlyAverages.avgIV) >= 0 ? '+' : ''}{(iv - monthlyAverages.avgIV).toFixed(2)}%
            </span>
          )}
        </div>
        <div className="flex flex-col">
          <span className="font-semibold text-emerald-300">
            RV · {formatPercent(rv)}
          </span>
          {timeframe === 'hourly' && monthlyAverages.avgRV && rv !== null && rv !== undefined && (
            <span className="text-[10px] text-emerald-300/80">
              vs 30d avg: {(rv - monthlyAverages.avgRV) >= 0 ? '+' : ''}{(rv - monthlyAverages.avgRV).toFixed(2)}%
            </span>
          )}
        </div>
        {iv !== null && iv !== undefined && rv !== null && rv !== undefined && (
          <span className="font-medium text-sky-300">
            Spread · {formatPercent(iv - rv, { showSign: true })}
          </span>
        )}
      </div>
    </div>
  );
};

function VolatilityChart({
  socket = null,
  initialTimeframe = 'hourly',
  autoRefreshMs = REFRESH_INTERVAL_MS,
  showHeader = true,
  showSummary = true,
  showFooter = true,
  showLegend = true,
  chartHeight = 450,
  className
}) {
  // Instance awareness for multi-symbol support (v6.0)
  const { selectedInstance, instances } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const [currentSymbol, setCurrentSymbol] = useState(instanceInfo?.symbol || 'BTCUSD');
  const availableSymbols = [...new Set(instances.map(i => parseInstanceName(i.name)?.symbol).filter(Boolean))];
  if (availableSymbols.length === 0) availableSymbols.push('BTCUSD', 'ETHUSD');
  
  const [timeframe, setTimeframe] = useState(initialTimeframe);
  const [chartData, setChartData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [latest, setLatest] = useState({ iv: null, rv: {} });
  const [lastUpdated, setLastUpdated] = useState(null);
  const [btcPrice, setBtcPrice] = useState(null);
  const [btcLoading, setBtcLoading] = useState(false);
  const [monthlyAverages, setMonthlyAverages] = useState({
    avgIV: null,
    avgRV: null
  });

  // Get symbol color
  const getSymbolColor = (symbol) => {
    const colors = {
      'BTCUSD': { bg: '#f7931a20', border: '#f7931a', text: '#f7931a' },
      'ETHUSD': { bg: '#627eea20', border: '#627eea', text: '#627eea' },
    };
    return colors[symbol] || { bg: '#64748b20', border: '#64748b', text: '#64748b' };
  };

  const symbolColors = getSymbolColor(currentSymbol);

  const abortRef = useRef(null);
  const mountedRef = useRef(true);

  const selectedTimeframe = useMemo(
    () => TIMEFRAMES.find((item) => item.value === timeframe) || TIMEFRAMES[0],
    [timeframe]
  );

  const selectedRv = useMemo(() => {
    if (!selectedTimeframe) return null;
    const key = selectedTimeframe.rvKey;
    return latest?.rv?.[key]?.value ?? null;
  }, [latest, selectedTimeframe]);

  const latestTimestamp = useMemo(() => {
    const ivTs = latest?.iv?.timestamp;
    const key = selectedTimeframe?.rvKey;
    const rvTs = key ? latest?.rv?.[key]?.timestamp : null;
    return Math.max(ivTs || 0, rvTs || 0, lastUpdated || 0) || null;
  }, [latest, selectedTimeframe, lastUpdated]);

  // Filter chart data to rolling 24-hour window for hourly timeframe
  const filteredChartData = useMemo(() => {
    const data = chartData[currentSymbol] || [];
    if (timeframe !== 'hourly' || !data.length) {
      return data;
    }
    
    const now = Date.now();
    const hourMs = 60 * 60 * 1000;
    const windowStart = now - (24 * hourMs);
    
    // Keep only data points within the last 24 hours
    return data.filter(point => point.timestamp >= windowStart && point.timestamp <= now);
  }, [chartData, currentSymbol, timeframe]);

  const fetchLatest = useCallback(async () => {
    try {
      const response = await fetch(`/api/risk/volatility/latest?symbol=${currentSymbol}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      if (!payload?.success) {
        throw new Error(payload?.error || 'Failed to load latest volatility');
      }
      if (!mountedRef.current) return;
      setLatest(payload.data || { iv: null, rv: {} });
    } catch (err) {
      if (!mountedRef.current) return;
      console.warn('Failed to fetch latest volatility values:', err);
    }
  }, [currentSymbol]);

  const fetchHistorical = useCallback(async (tf, { showLoader = true } = {}) => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    if (showLoader) {
      setLoading(true);
    }
    setError(null);

    try {
      const response = await fetch(`/api/risk/volatility/historical?timeframe=${tf}&symbol=${currentSymbol}`, {
        signal: controller.signal
      });

      if (response.status === 404) {
        setChartData(prev => ({ ...prev, [currentSymbol]: [] }));
        setLastUpdated(null);
        return;
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      if (!payload?.success) {
        throw new Error(payload?.error || 'Failed to load historical volatility');
      }

      const { data } = payload;
      const merged = mergeSeries(data?.iv, data?.rv);

      if (!mountedRef.current) return;
      setChartData(prev => ({ ...prev, [currentSymbol]: merged }));
      setLastUpdated(Date.now());
    } catch (err) {
      if (controller.signal.aborted || !mountedRef.current) {
        return;
      }
      console.error('Failed to fetch volatility history:', err);
      setError(err.message || 'Unable to load volatility history');
      setChartData(prev => ({ ...prev, [currentSymbol]: [] }));
    } finally {
      if (!controller.signal.aborted && mountedRef.current && showLoader) {
        setLoading(false);
      }
    }
  }, [currentSymbol]);

  const refreshData = useCallback(
    async (tf, { showLoader = true } = {}) => {
      await Promise.all([fetchHistorical(tf, { showLoader }), fetchLatest()]);
    },
    [fetchHistorical, fetchLatest]
  );

  const fetchMonthlyAverages = useCallback(async () => {
    try {
      const response = await fetch(`/api/risk/volatility/historical?timeframe=monthly&symbol=${currentSymbol}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      if (!payload?.success) {
        throw new Error(payload?.error || 'Failed to fetch monthly data');
      }
      if (!mountedRef.current) return;
      
      const { data } = payload;
      
      // Calculate average IV from monthly data
      let avgIV = null;
      if (data?.iv && data.iv.length > 0) {
        const ivValues = data.iv
          .map(point => normalizeValue(point?.value ?? point?.iv ?? point?.iv_value))
          .filter(v => v !== null);
        if (ivValues.length > 0) {
          avgIV = ivValues.reduce((sum, val) => sum + val, 0) / ivValues.length;
        }
      }
      
      // Calculate average RV from monthly data
      let avgRV = null;
      if (data?.rv && data.rv.length > 0) {
        const rvValues = data.rv
          .map(point => normalizeValue(point?.value ?? point?.rv ?? point?.rv_value))
          .filter(v => v !== null);
        if (rvValues.length > 0) {
          avgRV = rvValues.reduce((sum, val) => sum + val, 0) / rvValues.length;
        }
      }
      
      setMonthlyAverages({ avgIV, avgRV });
    } catch (err) {
      if (!mountedRef.current) return;
      console.warn('Failed to fetch monthly averages:', err);
    }
  }, []);

  const fetchBTCPrice = useCallback(async (showDetails = false) => {
    setBtcLoading(true);
    try {
      const response = await fetch('/api/risk/volatility/btc-price');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      if (!payload?.success) {
        throw new Error(payload?.error || 'Failed to fetch BTC price');
      }
      if (!mountedRef.current) return;
      setBtcPrice(payload.data);
      
      // Show alert with BTC price details only if requested
      if (showDetails) {
        const data = payload.data;
        const change24h = data.change_24h_percent || 0;
        const changeSign = change24h >= 0 ? '+' : '';
        alert(
          `BTC Perpetual Price\n\n` +
          `Price: $${data.price?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}\n` +
          `24h Change: ${changeSign}${change24h.toFixed(2)}%\n` +
          `High: $${data.high?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}\n` +
          `Low: $${data.low?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}\n` +
          `Volume: ${data.volume?.toLocaleString('en-US')}\n` +
          `Updated: ${new Date(data.timestamp).toLocaleString('en-IN')}`
        );
      }
    } catch (err) {
      if (!mountedRef.current) return;
      console.error('Failed to fetch BTC price:', err);
      if (showDetails) {
        alert(`Failed to fetch BTC price: ${err.message}`);
      }
    } finally {
      if (mountedRef.current) {
        setBtcLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    refreshData(timeframe, { showLoader: true });
    fetchBTCPrice(false); // Fetch BTC price on mount without showing details
    
    // Fetch monthly averages when in hourly mode
    if (timeframe === 'hourly') {
      fetchMonthlyAverages();
    }

    return () => {
      mountedRef.current = false;
      if (abortRef.current) {
        abortRef.current.abort();
      }
    };
  }, [refreshData, timeframe, fetchBTCPrice, fetchMonthlyAverages, currentSymbol]);

  // Refetch when symbol changes
  useEffect(() => {
    if (!chartData[currentSymbol]) {
      refreshData(timeframe, { showLoader: true });
    }
  }, [currentSymbol, chartData, refreshData, timeframe]);

  useEffect(() => {
    if (!autoRefreshMs) return undefined;
    const interval = setInterval(() => {
      refreshData(timeframe, { showLoader: false });
      fetchBTCPrice(false); // Auto-refresh BTC price without showing details
    }, autoRefreshMs);
    return () => clearInterval(interval);
  }, [autoRefreshMs, refreshData, timeframe, fetchBTCPrice]);

  useEffect(() => {
    if (!socket) return undefined;

    let refreshTimeout = null;
    
    const handleVolatilityUpdate = (message) => {
      if (!message) return;
      if (message.success && message.data) {
        setLatest(message.data);
        // Debounce historical data refresh to avoid excessive updates
        if (refreshTimeout) clearTimeout(refreshTimeout);
        refreshTimeout = setTimeout(() => {
          refreshData(timeframe, { showLoader: false });
        }, 1000); // Increased from 250ms to 1 second
      } else if (message.error) {
        console.warn('Volatility update error:', message.error);
      }
    };

    socket.emit('subscribe_volatility');
    socket.on('volatility_update', handleVolatilityUpdate);

    return () => {
      if (refreshTimeout) clearTimeout(refreshTimeout);
      socket.emit('unsubscribe_volatility');
      socket.off('volatility_update', handleVolatilityUpdate);
    };
  }, [socket, timeframe, refreshData]);

  const renderSummary = showSummary && (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3">
        <p className="text-[11px] uppercase tracking-[0.24em] text-rose-200/80">Implied Volatility</p>
        <p className={clsx(
          'mt-2 text-xl font-semibold',
          timeframe === 'hourly' && monthlyAverages.avgIV && latest?.iv?.value
            ? latest.iv.value > monthlyAverages.avgIV
              ? 'text-rose-400'
              : 'text-rose-200'
            : 'text-rose-100'
        )}>
          {formatPercent(latest?.iv?.value)}
        </p>
        <p className="text-[11px] text-rose-200/60">ATM option IV snapshot</p>
      </div>
      <div className="rounded-2xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3">
        <p className="text-[11px] uppercase tracking-[0.24em] text-emerald-200/80">
          Realized Volatility
        </p>
        <p className={clsx(
          'mt-2 text-xl font-semibold',
          timeframe === 'hourly' && monthlyAverages.avgRV && selectedRv
            ? selectedRv > monthlyAverages.avgRV
              ? 'text-emerald-400'
              : 'text-emerald-200'
            : 'text-emerald-100'
        )}>
          {formatPercent(selectedRv)}
        </p>
        <p className="text-[11px] text-emerald-200/60">
          {selectedTimeframe?.label ?? ''} lookback
        </p>
      </div>
      <div className="rounded-2xl border border-sky-500/20 bg-sky-500/10 px-4 py-3">
        <p className="text-[11px] uppercase tracking-[0.24em] text-sky-200/80">
          IV - RV Spread
        </p>
        <p
          className={clsx(
            'mt-2 text-xl font-semibold',
            (latest?.iv?.value ?? 0) - (selectedRv ?? 0) >= 0 ? 'text-sky-100' : 'text-sky-200/80'
          )}
        >
          {formatPercent(
            (latest?.iv?.value ?? null) === null || selectedRv === null
              ? null
              : latest.iv.value - selectedRv,
            { showSign: true }
          )}
        </p>
        <p className="text-[11px] text-sky-200/60">Higher spread ⇒ richer option premia</p>
      </div>
    </div>
  );

  const renderContent = () => {
    if (loading && filteredChartData.length === 0) {
      return (
        <div className="flex h-full items-center justify-center">
          <div className="flex flex-col items-center gap-2 text-xs text-slate-500">
            <span className="h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-slate-300" />
            <span>Loading Delta Exchange volatility data…</span>
          </div>
        </div>
      );
    }

    if (error) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6 text-center text-sm text-rose-100">
          <p className="font-medium">Unable to load IV vs RV history</p>
          <p className="text-xs text-rose-200/80">{error}</p>
          <button
            type="button"
            onClick={() => refreshData(timeframe, { showLoader: true })}
            className="inline-flex items-center gap-2 rounded-xl border border-rose-400/40 bg-rose-500/20 px-3 py-1.5 text-xs font-semibold text-rose-100 transition hover:border-rose-300/60 hover:bg-rose-500/30"
          >
            <RefreshCcw className="h-3.5 w-3.5" />
            Retry
          </button>
        </div>
      );
    }

    if (!filteredChartData.length) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-slate-400">
          <p className="font-medium text-slate-200">Waiting for volatility collector</p>
          <p className="max-w-sm text-xs text-slate-500">
            Historical IV/RV points populate automatically once the Delta Exchange collector has been
            running for a few minutes.
          </p>
        </div>
      );
    }

    // Calculate domain for time-based views (rolling windows)
    const getXAxisDomain = () => {
      const now = Date.now();
      
      if (timeframe === 'hourly') {
        // Rolling 24-hour window: current_time - 24h → current_time
        const hourMs = 60 * 60 * 1000;
        return [now - (24 * hourMs), now];
      }
      
      if (timeframe === 'weekly') {
        const weekMs = 7 * 24 * 60 * 60 * 1000;
        return [now - (4 * weekMs), now];
      }
      
      if (timeframe === 'monthly') {
        const monthMs = 30 * 24 * 60 * 60 * 1000;
        return [now - (3 * monthMs), now];
      }
      
      return ['dataMin', 'dataMax'];
    };

    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={filteredChartData}
          margin={{ top: 10, right: 20, bottom: 10, left: 0 }}
        >
          <CartesianGrid stroke="rgba(148, 163, 184, 0.12)" strokeDasharray="3 3" />
          <XAxis
            dataKey="timestamp"
            {...((timeframe === 'hourly' || timeframe === 'weekly' || timeframe === 'monthly') && { type: 'number', domain: getXAxisDomain() })}
            stroke="#475569"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickFormatter={buildTickFormatter(timeframe, filteredChartData)}
            {...(timeframe === 'hourly' && { ticks: generateHourlyTicks(filteredChartData) })}
            {...(timeframe === 'weekly' && { ticks: generateWeeklyTicks(filteredChartData) })}
            {...(timeframe === 'monthly' && { ticks: generateMonthlyTicks(filteredChartData) })}
            minTickGap={timeframe === 'hourly' ? 50 : 24}
          />
          <YAxis
            stroke="#475569"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickFormatter={(value) => `${value.toFixed(0)}%`}
            width={52}
          />
          <Tooltip content={<CustomTooltip timeframe={timeframe} monthlyAverages={monthlyAverages} />} />
          {showLegend && (
            <Legend
              verticalAlign="top"
              align="right"
              iconType="plainline"
              wrapperStyle={{
                paddingBottom: 12,
                fontSize: 12,
                color: '#94a3b8'
              }}
            />
          )}
          <Line
            type="monotone"
            dataKey="iv"
            stroke="#fb7185"
            strokeWidth={2}
            dot={false}
            name="Implied Volatility"
            activeDot={{ r: 4 }}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="rv"
            stroke="#34d399"
            strokeWidth={2}
            dot={false}
            name="Realized Volatility"
            activeDot={{ r: 4 }}
            isAnimationActive={false}
          />
          {timeframe === 'hourly' && monthlyAverages.avgIV && (
            <ReferenceLine
              y={monthlyAverages.avgIV}
              stroke="#f87171"
              strokeDasharray="5 5"
              strokeWidth={1.5}
              label={{
                value: `Avg IV (30d): ${monthlyAverages.avgIV.toFixed(2)}%`,
                position: 'right',
                fill: '#f87171',
                fontSize: 11
              }}
            />
          )}
          {timeframe === 'hourly' && monthlyAverages.avgRV && (
            <ReferenceLine
              y={monthlyAverages.avgRV}
              stroke="#34d399"
              strokeDasharray="5 5"
              strokeWidth={1.5}
              label={{
                value: `Avg RV (30d): ${monthlyAverages.avgRV.toFixed(2)}%`,
                position: 'right',
                fill: '#34d399',
                fontSize: 11
              }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    );
  };

  return (
    <div className={clsx('flex h-full min-h-[260px] flex-col gap-5', className)}>
      {showHeader && (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.32em] text-slate-500">
              Volatility Regime
            </p>
            <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
              Delta Exchange IV vs RV
              <span className={clsx(
                'text-xs px-2 py-0.5 rounded font-medium',
                currentSymbol === 'BTCUSD' ? 'bg-blue-500/20 text-blue-300' :
                currentSymbol === 'ETHUSD' ? 'bg-purple-500/20 text-purple-300' :
                'bg-slate-500/20 text-slate-300'
              )}>
                {currentSymbol}
              </span>
            </h3>
            <p className="text-xs text-slate-500">
              Live implied vs realized volatility (1-hour) with {selectedTimeframe?.label?.toLowerCase()} lookback
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {/* Symbol Toggle */}
            <div className="flex rounded-xl border border-slate-800 bg-slate-950/80 p-1 text-xs text-slate-300">
              {availableSymbols.map((symbol) => {
                const colors = getSymbolColor(symbol);
                return (
                  <button
                    key={symbol}
                    type="button"
                    onClick={() => setCurrentSymbol(symbol)}
                    className={clsx(
                      'rounded-lg px-3 py-1.5 font-semibold transition',
                      symbol === currentSymbol
                        ? 'shadow-inner'
                        : 'text-slate-400 hover:text-slate-200'
                    )}
                    style={symbol === currentSymbol ? {
                      backgroundColor: colors.bg,
                      color: colors.text,
                      borderColor: colors.border
                    } : {}}
                  >
                    {symbol.replace('USD', '')}
                  </button>
                );
              })}
            </div>
            {/* Timeframe Toggle */}
            <div className="flex rounded-xl border border-slate-800 bg-slate-950/80 p-1 text-xs text-slate-300">
              {TIMEFRAMES.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setTimeframe(option.value)}
                  className={clsx(
                    'rounded-lg px-3 py-1.5 font-semibold transition',
                    option.value === timeframe
                      ? 'bg-slate-800 text-slate-100 shadow-inner'
                      : 'text-slate-400 hover:text-slate-200'
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => refreshData(timeframe, { showLoader: true })}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-700/80 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white"
            >
              <RefreshCcw className="h-3.5 w-3.5" />
              Refresh
            </button>
            <button
              type="button"
              onClick={() => fetchBTCPrice(true)}
              disabled={btcLoading}
              className="inline-flex items-center gap-2 rounded-xl border border-amber-700/80 bg-amber-950 px-3 py-1.5 text-xs font-semibold text-amber-200 transition hover:border-amber-500 hover:text-amber-100 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Click for 24h stats"
            >
              <DollarSign className="h-3.5 w-3.5" />
              {btcLoading ? 'Loading...' : btcPrice ? `$${btcPrice.price?.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : 'BTC Price'}
            </button>
          </div>
        </div>
      )}

      {renderSummary}

      <div
        className="relative w-full overflow-hidden rounded-3xl border border-slate-800/70 bg-slate-950/60"
        style={{ height: chartHeight }}
      >
        <div className="absolute inset-0">{renderContent()}</div>
      </div>

      {showFooter && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-[11px] uppercase tracking-[0.24em] text-slate-500">
          <span>Auto-refresh · {Math.round(autoRefreshMs / 1000)}s cadence</span>
          <span>
            Last Update · {latestTimestamp ? formatTimestamp(latestTimestamp) : 'Collector idle'}
          </span>
        </div>
      )}
    </div>
  );
}

export default VolatilityChart;
