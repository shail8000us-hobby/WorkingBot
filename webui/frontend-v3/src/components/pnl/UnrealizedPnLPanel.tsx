'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { TrendingUp, TrendingDown, RefreshCw, DollarSign } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

interface PnLPoint {
  timestamp: number;
  pnl: number;
}

interface PnLHistoryData {
  history: Array<{ timestamp: string; total_pnl: number; position_count?: number; time?: string }>;
  meta?: {
    guardian_running: boolean;
    last_update?: string;
    data_points?: number;
  };
}

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

async function fetchPnLHistory(): Promise<PnLHistoryData> {
  const response = await fetch(`${API_URL}/api/pnl-history/hourly`);
  if (!response.ok) {
    throw new Error(`Failed to fetch P&L history: ${response.statusText}`);
  }
  return response.json();
}

function formatCurrency(value: number | undefined): string {
  if (value === undefined || value === null) return '—';
  return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

export function UnrealizedPnLPanel() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['pnl-history'],
    queryFn: fetchPnLHistory,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Unrealized P&L Trend
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading P&L data...
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
            <DollarSign className="h-5 w-5" />
            Unrealized P&L Trend
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {(error as Error)?.message || 'Failed to load P&L data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const pnlData = data;
  const chartData: PnLPoint[] =
    pnlData?.history?.map((point) => ({
      timestamp: new Date(point.timestamp).getTime(),
      pnl: point.total_pnl,
    })) || [];

  // Calculate stats from history
  const pnlValues = chartData.map(p => p.pnl);
  const currentPnL = pnlValues.length > 0 ? pnlValues[pnlValues.length - 1] : 0;
  const peakPnL = pnlValues.length > 0 ? Math.max(...pnlValues) : 0;
  const troughPnL = pnlValues.length > 0 ? Math.min(...pnlValues) : 0;
  const avgPnL = pnlValues.length > 0 ? pnlValues.reduce((a, b) => a + b, 0) / pnlValues.length : 0;
  const volatility = pnlValues.length > 1 
    ? Math.sqrt(pnlValues.reduce((acc, val) => acc + Math.pow(val - avgPnL, 2), 0) / pnlValues.length)
    : 0;
  
  const isProfitable = currentPnL >= 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Unrealized P&L Trend
          </div>
          <Button variant="ghost" size="sm" onClick={() => refetch()} className="h-8 w-8 p-0">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Guardian Warning */}
        {pnlData?.meta && !pnlData.meta.guardian_running && pnlData.meta.last_update && (
          <Alert>
            <AlertDescription className="text-xs">
              ⚠️ Guardian not running. Showing historical data from{' '}
              {new Date(pnlData.meta.last_update).toLocaleString('en-IN')}
            </AlertDescription>
          </Alert>
        )}

        {/* Current P&L Display */}
        <div className="text-center space-y-2">
          <div className="text-sm text-muted-foreground">Current Unrealized P&L</div>
          <div className={`text-5xl font-bold tracking-tight flex items-center justify-center gap-3 ${isProfitable ? 'text-green-500' : 'text-red-500'}`}>
            {isProfitable ? <TrendingUp className="h-10 w-10" /> : <TrendingDown className="h-10 w-10" />}
            {formatCurrency(currentPnL)}
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4">
          <div className="p-3 bg-muted rounded-lg space-y-1 text-center">
            <div className="text-xs text-muted-foreground">Avg P&L</div>
            <div className="text-lg font-semibold">{formatCurrency(avgPnL)}</div>
          </div>
          <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg space-y-1 text-center">
            <div className="text-xs text-green-400">Peak</div>
            <div className="text-lg font-semibold text-green-500">{formatCurrency(peakPnL)}</div>
          </div>
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg space-y-1 text-center">
            <div className="text-xs text-red-400">Trough</div>
            <div className="text-lg font-semibold text-red-500">{formatCurrency(troughPnL)}</div>
          </div>
          <div className="p-3 bg-muted rounded-lg space-y-1 text-center">
            <div className="text-xs text-muted-foreground">Volatility</div>
            <div className="text-lg font-semibold">{formatCurrency(volatility)}</div>
          </div>
        </div>

        {/* Chart */}
        <div className="h-[300px] w-full bg-muted/50 rounded-lg p-4">
          {chartData.length === 0 ? (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              No P&L history available
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                <XAxis
                  dataKey="timestamp"
                  type="number"
                  domain={['dataMin', 'dataMax']}
                  tickFormatter={formatTimestamp}
                  stroke="hsl(var(--muted-foreground))"
                  style={{ fontSize: '11px' }}
                />
                <YAxis
                  tickFormatter={(value) => `₹${value.toFixed(0)}`}
                  stroke="hsl(var(--muted-foreground))"
                  style={{ fontSize: '11px' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--popover))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                  labelFormatter={(ts) => new Date(ts as number).toLocaleString('en-IN')}
                  formatter={(value: any) => [formatCurrency(value), 'P&L']}
                />
                <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
                <Line
                  type="monotone"
                  dataKey="pnl"
                  stroke={isProfitable ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)'}
                  strokeWidth={2}
                  dot={false}
                  name="Unrealized P&L"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Info */}
        <Alert>
          <AlertDescription className="text-xs">
            <strong>Unrealized P&L:</strong> Shows the profit/loss trend of open positions over the last 24 hours
            (hourly sampled data). This updates in real-time as market prices change.
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}
