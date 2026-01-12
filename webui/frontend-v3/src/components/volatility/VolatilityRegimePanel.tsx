'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Activity, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { useState, useMemo } from 'react';

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

interface VolatilityPoint {
  timestamp: number;
  iv: number | null;
  rv: number | null;
}

type Timeframe = 'hourly' | 'daily' | 'weekly' | 'monthly';

const TIMEFRAMES: Array<{ value: Timeframe; label: string; rvKey: '1h' | '1d' | '7d' | '30d' }> = [
  { value: 'hourly', label: 'Hourly', rvKey: '1h' },
  { value: 'daily', label: 'Daily', rvKey: '1d' },
  { value: 'weekly', label: 'Weekly', rvKey: '7d' },
  { value: 'monthly', label: 'Monthly', rvKey: '30d' },
];

interface HistoricalResponse {
  success: boolean;
  data: {
    iv: Array<{ timestamp: number; value: number }>;
    rv: Array<{ timestamp: number; value: number }>;
  };
  timeframe?: string;
}

interface LatestResponse {
  success: boolean;
  data: {
    iv: { value: number; timestamp: number };
    rv: {
      '1h': { value: number; timestamp: number };
      '1d': { value: number; timestamp: number };
      '7d': { value: number; timestamp: number };
      '30d': { value: number; timestamp: number };
    };
  };
}

interface CombinedVolatilityData {
  historical: HistoricalResponse['data'];
  latest: LatestResponse['data'];
  monthlyAverages: {
    avgIV: number | null;
    avgRV: number | null;
  };
}

async function fetchHistoricalData(timeframe: Timeframe): Promise<HistoricalResponse> {
  const response = await fetch(`${API_URL}/api/risk/volatility/historical?timeframe=${timeframe}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch historical data: ${response.statusText}`);
  }
  return response.json();
}

async function fetchLatestData(): Promise<LatestResponse> {
  const response = await fetch(`${API_URL}/api/risk/volatility/latest`);
  if (!response.ok) {
    throw new Error(`Failed to fetch latest data: ${response.statusText}`);
  }
  return response.json();
}

async function fetchMonthlyAverages(): Promise<{ avgIV: number | null; avgRV: number | null }> {
  try {
    const response = await fetch(`${API_URL}/api/risk/volatility/historical?timeframe=monthly`);
    if (!response.ok) {
      return { avgIV: null, avgRV: null };
    }
    const data = await response.json();
    if (!data.success || !data.data) {
      return { avgIV: null, avgRV: null };
    }

    // Calculate averages
    const ivValues = data.data.iv?.filter((p: any) => p.value != null).map((p: any) => p.value) || [];
    const rvValues = data.data.rv?.filter((p: any) => p.value != null).map((p: any) => p.value) || [];

    const avgIV = ivValues.length > 0 ? ivValues.reduce((a: number, b: number) => a + b, 0) / ivValues.length : null;
    const avgRV = rvValues.length > 0 ? rvValues.reduce((a: number, b: number) => a + b, 0) / rvValues.length : null;

    return { avgIV, avgRV };
  } catch {
    return { avgIV: null, avgRV: null };
  }
}

async function fetchVolatilityData(timeframe: Timeframe): Promise<CombinedVolatilityData> {
  const [historical, latest, monthlyAverages] = await Promise.all([
    fetchHistoricalData(timeframe),
    fetchLatestData(),
    fetchMonthlyAverages(),
  ]);

  return {
    historical: historical.data,
    latest: latest.data,
    monthlyAverages,
  };
}

function formatPercent(value: number | null | undefined, options?: { showSign?: boolean }): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const prefix = options?.showSign && value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(2)}%`;
}

function formatTimestamp(timestamp: number | string): string {
  if (!timestamp) return 'Never';
  const date = typeof timestamp === 'string' ? new Date(timestamp) : new Date(timestamp);
  if (isNaN(date.getTime())) return 'Invalid';
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: 'short',
    hour12: false,
  }).format(date);
}

function mergeVolatilitySeries(
  ivSeries: Array<{ timestamp: number; value: number }>,
  rvSeries: Array<{ timestamp: number; value: number }>
): VolatilityPoint[] {
  const merged = new Map<number, VolatilityPoint>();

  ivSeries?.forEach((point) => {
    const ts = typeof point.timestamp === 'string' ? new Date(point.timestamp).getTime() : point.timestamp;
    if (ts && !isNaN(ts)) {
      merged.set(ts, { timestamp: ts, iv: point.value, rv: null });
    }
  });

  rvSeries?.forEach((point) => {
    const ts = typeof point.timestamp === 'string' ? new Date(point.timestamp).getTime() : point.timestamp;
    if (ts && !isNaN(ts)) {
      const existing = merged.get(ts);
      if (existing) {
        merged.set(ts, { ...existing, rv: point.value });
      } else {
        merged.set(ts, { timestamp: ts, iv: null, rv: point.value });
      }
    }
  });

  return Array.from(merged.values()).sort((a, b) => a.timestamp - b.timestamp);
}

export function VolatilityRegimePanel() {
  const [timeframe, setTimeframe] = useState<Timeframe>('hourly');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['volatility-regime', timeframe],
    queryFn: () => fetchVolatilityData(timeframe),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const selectedTimeframeData = useMemo(() => TIMEFRAMES.find((tf) => tf.value === timeframe), [timeframe]);

  const latestIV = data?.latest?.iv?.value ?? null;
  const latestRV = data?.latest?.rv?.[selectedTimeframeData?.rvKey || '1h']?.value ?? null;
  const spread = latestIV !== null && latestRV !== null ? latestIV - latestRV : null;
  const monthlyAvg = data?.monthlyAverages;

  const chartData = useMemo(() => {
    if (!data?.historical) return [];
    return mergeVolatilitySeries(data.historical.iv || [], data.historical.rv || []);
  }, [data]);

  // Filter chart data to rolling 24-hour window for hourly timeframe
  const filteredChartData = useMemo(() => {
    if (timeframe !== 'hourly' || !chartData.length) {
      return chartData;
    }
    
    const now = Date.now();
    const hourMs = 60 * 60 * 1000;
    const windowStart = now - (24 * hourMs);
    
    return chartData.filter(point => point.timestamp >= windowStart && point.timestamp <= now);
  }, [chartData, timeframe]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Volatility Regime (IV vs RV)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading volatility data...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Volatility Regime (IV vs RV)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {(error as Error)?.message || 'Failed to load volatility data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Volatility Regime (IV vs RV)
          </div>
          <div className="flex items-center gap-2">
            {TIMEFRAMES.map((tf) => (
              <Button
                key={tf.value}
                variant={timeframe === tf.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTimeframe(tf.value)}
              >
                {tf.label}
              </Button>
            ))}
            <Button variant="ghost" size="sm" onClick={() => refetch()} className="h-8 w-8 p-0">
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Current Values Summary */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-lg space-y-1">
            <div className="text-xs text-rose-400 uppercase tracking-wider">Implied Volatility</div>
            <div className={`text-3xl font-bold ${
              timeframe === 'hourly' && monthlyAvg?.avgIV && latestIV && latestIV > monthlyAvg.avgIV 
                ? 'text-rose-400' 
                : 'text-rose-300'
            }`}>
              {formatPercent(latestIV)}
            </div>
            <div className="text-xs text-rose-200/60">ATM option IV snapshot</div>
          </div>

          <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg space-y-1">
            <div className="text-xs text-emerald-400 uppercase tracking-wider">Realized Volatility</div>
            <div className={`text-3xl font-bold ${
              timeframe === 'hourly' && monthlyAvg?.avgRV && latestRV && latestRV > monthlyAvg.avgRV 
                ? 'text-emerald-400' 
                : 'text-emerald-300'
            }`}>
              {formatPercent(latestRV)}
            </div>
            <div className="text-xs text-emerald-200/60">{selectedTimeframeData?.label} lookback</div>
          </div>

          <div className="p-4 bg-sky-500/10 border border-sky-500/30 rounded-lg space-y-1">
            <div className="text-xs text-sky-400 uppercase tracking-wider">IV - RV Spread</div>
            <div className={`text-3xl font-bold flex items-center gap-2 ${
              spread !== null && spread >= 0 ? 'text-sky-300' : 'text-sky-400'
            }`}>
              {spread !== null && spread >= 0 ? (
                <TrendingUp className="h-6 w-6" />
              ) : (
                <TrendingDown className="h-6 w-6" />
              )}
              {formatPercent(spread, { showSign: true })}
            </div>
            <div className="text-xs text-sky-200/60">Higher spread ⇒ richer option premia</div>
          </div>
        </div>

        {/* Chart */}
        <div className="h-[400px] w-full bg-muted/50 rounded-lg p-4">
          {filteredChartData.length === 0 ? (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              No historical data available for {selectedTimeframeData?.label} timeframe
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={filteredChartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                <XAxis
                  dataKey="timestamp"
                  type="number"
                  domain={timeframe === 'hourly' ? [Date.now() - (24 * 60 * 60 * 1000), Date.now()] : ['dataMin', 'dataMax']}
                  tickFormatter={(ts) => formatTimestamp(ts).split(',')[0]}
                  stroke="hsl(var(--muted-foreground))"
                  style={{ fontSize: '11px' }}
                />
                <YAxis
                  tickFormatter={(value) => `${value.toFixed(0)}%`}
                  stroke="hsl(var(--muted-foreground))"
                  style={{ fontSize: '11px' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--popover))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                  labelFormatter={(ts) => formatTimestamp(ts as number)}
                  formatter={(value: any) => [formatPercent(value), '']}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="iv"
                  stroke="rgb(251, 113, 133)"
                  strokeWidth={2}
                  dot={false}
                  name="Implied Volatility"
                />
                <Line
                  type="monotone"
                  dataKey="rv"
                  stroke="rgb(52, 211, 153)"
                  strokeWidth={2}
                  dot={false}
                  name="Realized Volatility"
                />
                {timeframe === 'hourly' && monthlyAvg?.avgIV && (
                  <ReferenceLine
                    y={monthlyAvg.avgIV}
                    stroke="rgb(248, 113, 113)"
                    strokeDasharray="5 5"
                    label={{
                      value: `Avg IV (30d): ${monthlyAvg.avgIV.toFixed(2)}%`,
                      position: 'right',
                      fill: 'rgb(248, 113, 113)',
                      fontSize: 11,
                    }}
                  />
                )}
                {timeframe === 'hourly' && monthlyAvg?.avgRV && (
                  <ReferenceLine
                    y={monthlyAvg.avgRV}
                    stroke="rgb(52, 211, 153)"
                    strokeDasharray="5 5"
                    label={{
                      value: `Avg RV (30d): ${monthlyAvg.avgRV.toFixed(2)}%`,
                      position: 'right',
                      fill: 'rgb(52, 211, 153)',
                      fontSize: 11,
                    }}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Info */}
        <Alert>
          <AlertDescription className="text-xs">
            <strong>Volatility Regime:</strong> Implied Volatility (IV) reflects market expectations from option prices.
            Realized Volatility (RV) measures actual historical price movement. A positive spread (IV {'>'} RV) suggests
            options are expensive relative to realized volatility.
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}
