'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { GitCompare, TrendingUp, Target, Activity } from 'lucide-react';

interface StrategyMetrics {
  strategy_name: string;
  total_trades: number;
  win_rate: number;
  net_profit: number;
  sharpe_ratio: number;
  max_drawdown: number;
  avg_trade_pnl: number;
}

interface StrategyComparisonData {
  strategies: StrategyMetrics[];
  best_strategy: string;
  comparison_period: string;
}

interface StrategyComparisonResponse {
  data: StrategyComparisonData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchStrategyComparison(): Promise<StrategyComparisonResponse> {
  const response = await fetch('http://localhost:5555/api/strategies/comparison');
  if (!response.ok) {
    throw new Error('Failed to fetch strategy comparison');
  }
  return response.json();
}

export function StrategyComparisonPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['strategy-comparison'],
    queryFn: fetchStrategyComparison,
    refetchInterval: false,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitCompare className="h-5 w-5" />
            Strategy Comparison
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading strategy comparison...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Strategy Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'No comparison data available'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const comparisonData = data?.data;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <GitCompare className="h-5 w-5" />
            Strategy Comparison
          </CardTitle>
          <Badge variant="outline">Period: {comparisonData?.comparison_period}</Badge>
        </div>
        {comparisonData?.best_strategy && (
          <div className="flex items-center gap-2 mt-2">
            <TrendingUp className="h-4 w-4 text-green-500" />
            <span className="text-sm text-muted-foreground">
              Best Performer: <span className="font-semibold">{comparisonData.best_strategy}</span>
            </span>
          </div>
        )}
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Strategy</TableHead>
              <TableHead className="text-right">Trades</TableHead>
              <TableHead className="text-right">Win Rate</TableHead>
              <TableHead className="text-right">Net Profit</TableHead>
              <TableHead className="text-right">Sharpe</TableHead>
              <TableHead className="text-right">Max DD</TableHead>
              <TableHead className="text-right">Avg P&L</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {comparisonData?.strategies?.map((strategy) => (
              <TableRow key={strategy.strategy_name}>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2">
                    {strategy.strategy_name}
                    {strategy.strategy_name === comparisonData.best_strategy && (
                      <Badge variant="default" className="bg-green-500 text-xs">
                        Best
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right">{strategy.total_trades}</TableCell>
                <TableCell className="text-right">
                  <span className={strategy.win_rate >= 50 ? 'text-green-500' : 'text-red-500'}>
                    {strategy.win_rate.toFixed(1)}%
                  </span>
                </TableCell>
                <TableCell className="text-right">
                  <span className={strategy.net_profit >= 0 ? 'text-green-500' : 'text-red-500'}>
                    ₹{strategy.net_profit.toFixed(2)}
                  </span>
                </TableCell>
                <TableCell className="text-right">{strategy.sharpe_ratio.toFixed(2)}</TableCell>
                <TableCell className="text-right">
                  <span className="text-red-500">{strategy.max_drawdown.toFixed(2)}%</span>
                </TableCell>
                <TableCell className="text-right">
                  <span className={strategy.avg_trade_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                    ₹{strategy.avg_trade_pnl.toFixed(2)}
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
