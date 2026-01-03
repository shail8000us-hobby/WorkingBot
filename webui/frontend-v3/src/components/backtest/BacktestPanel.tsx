'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { TrendingUp, TrendingDown, Activity, Target, Percent, DollarSign, Calendar } from 'lucide-react';

interface BacktestMetrics {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_profit: number;
  total_loss: number;
  net_profit: number;
  sharpe_ratio: number;
  max_drawdown: number;
  avg_trade_duration: string;
  best_trade: number;
  worst_trade: number;
}

interface BacktestEquityCurve {
  timestamp: string;
  equity: number;
  drawdown: number;
}

interface BacktestData {
  run_id: string;
  start_date: string;
  end_date: string;
  symbol: string;
  mode: string;
  metrics: BacktestMetrics;
  equity_curve: BacktestEquityCurve[];
}

interface BacktestResponse {
  data: BacktestData;
  status: 'completed' | 'running' | 'error';
  error?: string;
}

async function fetchBacktestResults(): Promise<BacktestResponse> {
  const response = await fetch('http://localhost:5555/api/backtest/results/latest');
  if (!response.ok) {
    throw new Error('Failed to fetch backtest results');
  }
  return response.json();
}

export function BacktestPanel() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['backtest-results'],
    queryFn: fetchBacktestResults,
    refetchInterval: false, // Only fetch on demand
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Backtest Results
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading backtest results...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Backtest Results</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'No backtest results available'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const backtest = data?.data;
  const metrics = backtest?.metrics;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Backtest Results
            </CardTitle>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <Activity className="h-4 w-4 mr-2" />
              Reload
            </Button>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground mt-2">
            <span className="flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              {backtest?.start_date} - {backtest?.end_date}
            </span>
            <Badge variant="outline">{backtest?.symbol}</Badge>
            <Badge variant={backtest?.mode === 'LONG' ? 'default' : 'destructive'}>
              {backtest?.mode}
            </Badge>
            <span className="text-xs">Run ID: {backtest?.run_id}</span>
          </div>
        </CardHeader>
        <CardContent>
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <DollarSign className="h-6 w-6 mx-auto mb-2 text-green-500" />
                  <div className={`text-2xl font-bold ${(metrics?.net_profit || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    ₹{metrics?.net_profit?.toFixed(2) || 0}
                  </div>
                  <div className="text-xs text-muted-foreground">Net Profit</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <Target className="h-6 w-6 mx-auto mb-2 text-blue-500" />
                  <div className="text-2xl font-bold">{metrics?.win_rate?.toFixed(1) || 0}%</div>
                  <div className="text-xs text-muted-foreground">Win Rate</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {metrics?.winning_trades}/{metrics?.total_trades} wins
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <TrendingUp className="h-6 w-6 mx-auto mb-2 text-purple-500" />
                  <div className="text-2xl font-bold">{metrics?.sharpe_ratio?.toFixed(2) || 0}</div>
                  <div className="text-xs text-muted-foreground">Sharpe Ratio</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <TrendingDown className="h-6 w-6 mx-auto mb-2 text-red-500" />
                  <div className="text-2xl font-bold text-red-500">
                    {metrics?.max_drawdown?.toFixed(2) || 0}%
                  </div>
                  <div className="text-xs text-muted-foreground">Max Drawdown</div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Detailed Metrics */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="p-4 bg-muted rounded-lg">
              <h4 className="font-semibold mb-3 text-sm">Trade Statistics</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total Trades:</span>
                  <span className="font-medium">{metrics?.total_trades || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Winning Trades:</span>
                  <span className="font-medium text-green-500">{metrics?.winning_trades || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Losing Trades:</span>
                  <span className="font-medium text-red-500">{metrics?.losing_trades || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Avg Trade Duration:</span>
                  <span className="font-medium">{metrics?.avg_trade_duration || 'N/A'}</span>
                </div>
              </div>
            </div>

            <div className="p-4 bg-muted rounded-lg">
              <h4 className="font-semibold mb-3 text-sm">Profit & Loss</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total Profit:</span>
                  <span className="font-medium text-green-500">₹{metrics?.total_profit?.toFixed(2) || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total Loss:</span>
                  <span className="font-medium text-red-500">₹{metrics?.total_loss?.toFixed(2) || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Best Trade:</span>
                  <span className="font-medium text-green-500">₹{metrics?.best_trade?.toFixed(2) || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Worst Trade:</span>
                  <span className="font-medium text-red-500">₹{metrics?.worst_trade?.toFixed(2) || 0}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Equity Curve Chart */}
          {backtest?.equity_curve && backtest.equity_curve.length > 0 && (
            <div>
              <h4 className="font-semibold mb-4">Equity Curve</h4>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={backtest.equity_curve}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="timestamp"
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value) => new Date(value).toLocaleDateString()}
                  />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--popover))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '6px',
                    }}
                    labelFormatter={(value) => new Date(value).toLocaleString()}
                  />
                  <Legend />
                  <ReferenceLine y={0} stroke="gray" strokeDasharray="3 3" />
                  <Line
                    type="monotone"
                    dataKey="equity"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={false}
                    name="Equity"
                  />
                  <Line
                    type="monotone"
                    dataKey="drawdown"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={false}
                    name="Drawdown %"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
