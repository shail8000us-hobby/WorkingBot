/**
 * PnLChart Component
 * 
 * Interactive P&L history chart with:
 * - Area chart showing P&L over time
 * - Tooltip with detailed info
 * - Color coding (green for profit, red for loss)
 */

'use client';

import { memo, useMemo } from 'react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { usePnLHistory } from '@/hooks';
import { LoadingCard } from '@/components/common';
import { format } from 'date-fns';
import { TrendingUp } from 'lucide-react';

interface PnLChartProps {
  className?: string;
  height?: number;
}

export const PnLChart = memo(function PnLChart({ 
  className,
  height = 300,
}: PnLChartProps) {
  const { data, isLoading, error } = usePnLHistory();
  
  const chartData = useMemo(() => {
    if (!data?.history) return [];
    
    return data.history.map((entry) => ({
      time: entry.time || format(new Date(entry.timestamp), 'HH:mm'),
      timestamp: entry.timestamp,
      pnl: entry.total_pnl,
      unrealized: entry.unrealized_pnl,
      positions: entry.position_count,
    }));
  }, [data]);
  
  const stats = useMemo(() => {
    if (chartData.length === 0) return null;
    
    const values = chartData.map((d) => d.pnl);
    const current = values[values.length - 1] ?? 0;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const start = values[0] ?? 0;
    const change = current - start;
    
    return { current, min, max, change };
  }, [chartData]);
  
  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }: {
    active?: boolean;
    payload?: Array<{ value: number; dataKey: string }>;
    label?: string;
  }) => {
    if (!active || !payload || payload.length === 0) return null;
    
    const data = payload[0];
    const pnl = data?.value ?? 0;
    
    return (
      <div className="bg-popover border rounded-lg shadow-lg p-3 text-sm">
        <p className="text-muted-foreground mb-1">{label}</p>
        <p className={pnl >= 0 ? 'text-green-500 font-semibold' : 'text-red-500 font-semibold'}>
          ₹{pnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
        </p>
      </div>
    );
  };
  
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            P&L History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <LoadingCard lines={5} showHeader={false} />
        </CardContent>
      </Card>
    );
  }
  
  if (error || chartData.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            P&L History
          </CardTitle>
          <CardDescription>
            {error ? 'Failed to load P&L data' : 'No P&L data available'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-[200px] text-muted-foreground">
            {error ? 'Error loading chart' : 'Start trading to see P&L history'}
          </div>
        </CardContent>
      </Card>
    );
  }
  
  const isProfit = (stats?.current ?? 0) >= 0;
  const gradientId = 'pnlGradient';
  
  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              P&L History
            </CardTitle>
            <CardDescription>Today's profit and loss</CardDescription>
          </div>
          {stats && (
            <div className="text-right">
              <p className={`text-2xl font-bold ${isProfit ? 'text-green-500' : 'text-red-500'}`}>
                {isProfit ? '+' : ''}₹{stats.current.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </p>
              <p className="text-xs text-muted-foreground">
                Change: {stats.change >= 0 ? '+' : ''}₹{stats.change.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </p>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={height}>
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop 
                  offset="5%" 
                  stopColor={isProfit ? '#22c55e' : '#ef4444'} 
                  stopOpacity={0.3}
                />
                <stop 
                  offset="95%" 
                  stopColor={isProfit ? '#22c55e' : '#ef4444'} 
                  stopOpacity={0}
                />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis 
              dataKey="time" 
              tick={{ fontSize: 12 }}
              className="text-muted-foreground"
            />
            <YAxis 
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => `₹${(value / 1000).toFixed(0)}k`}
              className="text-muted-foreground"
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="#888" strokeDasharray="3 3" />
            <Area
              type="monotone"
              dataKey="pnl"
              stroke={isProfit ? '#22c55e' : '#ef4444'}
              strokeWidth={2}
              fill={`url(#${gradientId})`}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
});

export default PnLChart;
