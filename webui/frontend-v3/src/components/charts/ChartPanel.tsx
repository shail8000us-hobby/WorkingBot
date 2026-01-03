'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { TrendingUp, TrendingDown } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

interface PriceData {
  timestamp: string;
  price: number;
  volume?: number;
}

interface ChartResponse {
  data: {
    prices: PriceData[];
    current_price: number;
    change_24h: number;
    high_24h: number;
    low_24h: number;
  };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchChartData(timeframe: string): Promise<ChartResponse> {
  const response = await fetch(`http://localhost:5555/api/chart/prices?timeframe=${timeframe}`);
  if (!response.ok) {
    throw new Error('Failed to fetch chart data');
  }
  return response.json();
}

export function ChartPanel() {
  const [timeframe, setTimeframe] = useState<string>('1h');
  const [chartType, setChartType] = useState<'line' | 'area'>('area');

  const { data, isLoading, error } = useQuery({
    queryKey: ['chart-data', timeframe],
    queryFn: () => fetchChartData(timeframe),
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Price Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading chart...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Price Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load chart data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const prices = data?.data?.prices || [];
  const currentPrice = data?.data?.current_price || 0;
  const change24h = data?.data?.change_24h || 0;
  const high24h = data?.data?.high_24h || 0;
  const low24h = data?.data?.low_24h || 0;

  const formatPrice = (value: number) => `₹${value.toLocaleString()}`;
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    if (timeframe === '1d' || timeframe === '7d') {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <CardTitle>Price Chart</CardTitle>
            <div className="flex items-center gap-3">
              <span className="text-2xl font-bold">{formatPrice(currentPrice)}</span>
              <Badge variant={change24h >= 0 ? 'default' : 'destructive'} className="flex items-center gap-1">
                {change24h >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                {change24h >= 0 ? '+' : ''}{change24h.toFixed(2)}%
              </Badge>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Select value={chartType} onValueChange={(value) => setChartType(value as 'line' | 'area')}>
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="line">Line</SelectItem>
                <SelectItem value="area">Area</SelectItem>
              </SelectContent>
            </Select>
            <Select value={timeframe} onValueChange={setTimeframe}>
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="5m">5 Minutes</SelectItem>
                <SelectItem value="15m">15 Minutes</SelectItem>
                <SelectItem value="1h">1 Hour</SelectItem>
                <SelectItem value="4h">4 Hours</SelectItem>
                <SelectItem value="1d">1 Day</SelectItem>
                <SelectItem value="7d">7 Days</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* 24h Stats */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="p-3 rounded-lg bg-muted">
            <p className="text-xs text-muted-foreground mb-1">24h High</p>
            <p className="text-lg font-semibold text-green-600">{formatPrice(high24h)}</p>
          </div>
          <div className="p-3 rounded-lg bg-muted">
            <p className="text-xs text-muted-foreground mb-1">24h Low</p>
            <p className="text-lg font-semibold text-red-600">{formatPrice(low24h)}</p>
          </div>
        </div>

        {/* Chart */}
        <ResponsiveContainer width="100%" height={400}>
          {chartType === 'area' ? (
            <AreaChart data={prices}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatTime}
                stroke="hsl(var(--muted-foreground))"
                fontSize={12}
              />
              <YAxis
                tickFormatter={(value) => `₹${(value / 1000).toFixed(0)}k`}
                stroke="hsl(var(--muted-foreground))"
                fontSize={12}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                }}
                labelFormatter={(label) => formatTime(label as string)}
                formatter={(value) => [formatPrice(value as number), 'Price']}
              />
              <ReferenceLine y={currentPrice} stroke="hsl(var(--primary))" strokeDasharray="3 3" />
              <Area
                type="monotone"
                dataKey="price"
                stroke="hsl(var(--primary))"
                fill="url(#colorPrice)"
                strokeWidth={2}
              />
            </AreaChart>
          ) : (
            <LineChart data={prices}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatTime}
                stroke="hsl(var(--muted-foreground))"
                fontSize={12}
              />
              <YAxis
                tickFormatter={(value) => `₹${(value / 1000).toFixed(0)}k`}
                stroke="hsl(var(--muted-foreground))"
                fontSize={12}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                }}
                labelFormatter={(label) => formatTime(label as string)}
                formatter={(value) => [formatPrice(value as number), 'Price']}
              />
              <ReferenceLine y={currentPrice} stroke="hsl(var(--primary))" strokeDasharray="3 3" />
              <Line
                type="monotone"
                dataKey="price"
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
