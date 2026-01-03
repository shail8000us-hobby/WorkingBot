'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { TrendingUp, Target, DollarSign, Percent, Activity, Award } from 'lucide-react';

interface PerformanceMetrics {
  daily_pnl: number;
  weekly_pnl: number;
  monthly_pnl: number;
  total_pnl: number;
  win_rate: number;
  profit_factor: number;
  sharpe_ratio: number;
  total_trades_today: number;
  avg_trade_duration: string;
  roi: number;
}

interface PerformanceResponse {
  data: PerformanceMetrics;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchPerformanceMetrics(): Promise<PerformanceResponse> {
  const response = await fetch('http://localhost:5555/api/performance/metrics');
  if (!response.ok) {
    throw new Error('Failed to fetch performance metrics');
  }
  return response.json();
}

export function PerformanceMetricsPanel() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['performance-metrics'],
    queryFn: fetchPerformanceMetrics,
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Performance Metrics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading performance metrics...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Performance Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load performance metrics'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const metrics = data?.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          Performance Metrics
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* P&L Overview */}
        <div className="grid grid-cols-4 gap-4">
          <div className="p-4 bg-muted rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Daily P&L</div>
            <div className={`text-2xl font-bold ${(metrics?.daily_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              ₹{metrics?.daily_pnl?.toFixed(2) || 0}
            </div>
          </div>
          <div className="p-4 bg-muted rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Weekly P&L</div>
            <div className={`text-2xl font-bold ${(metrics?.weekly_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              ₹{metrics?.weekly_pnl?.toFixed(2) || 0}
            </div>
          </div>
          <div className="p-4 bg-muted rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Monthly P&L</div>
            <div className={`text-2xl font-bold ${(metrics?.monthly_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              ₹{metrics?.monthly_pnl?.toFixed(2) || 0}
            </div>
          </div>
          <div className="p-4 bg-muted rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Total P&L</div>
            <div className={`text-2xl font-bold ${(metrics?.total_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              ₹{metrics?.total_pnl?.toFixed(2) || 0}
            </div>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-blue-500" />
              <span className="text-sm font-medium">Win Rate</span>
            </div>
            <div className="flex items-center gap-3">
              <Progress value={metrics?.win_rate || 0} className="w-32" />
              <span className="text-sm font-bold">{metrics?.win_rate?.toFixed(1) || 0}%</span>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-green-500" />
              <span className="text-sm font-medium">Profit Factor</span>
            </div>
            <span className="text-sm font-bold">{metrics?.profit_factor?.toFixed(2) || 0}</span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Award className="h-4 w-4 text-purple-500" />
              <span className="text-sm font-medium">Sharpe Ratio</span>
            </div>
            <span className="text-sm font-bold">{metrics?.sharpe_ratio?.toFixed(2) || 0}</span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Percent className="h-4 w-4 text-orange-500" />
              <span className="text-sm font-medium">ROI</span>
            </div>
            <span className={`text-sm font-bold ${(metrics?.roi || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {metrics?.roi?.toFixed(2) || 0}%
            </span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-blue-500" />
              <span className="text-sm font-medium">Trades Today</span>
            </div>
            <span className="text-sm font-bold">{metrics?.total_trades_today || 0}</span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-green-500" />
              <span className="text-sm font-medium">Avg Trade Duration</span>
            </div>
            <span className="text-sm font-bold">{metrics?.avg_trade_duration || 'N/A'}</span>
          </div>
        </div>

        {/* Footer */}
        <div className="text-xs text-center text-muted-foreground border-t pt-4">
          Auto-refreshes every 30 seconds
        </div>
      </CardContent>
    </Card>
  );
}
