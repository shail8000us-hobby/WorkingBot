'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { BarChart, TrendingUp, DollarSign, Percent, Target, Activity } from 'lucide-react';

interface Position {
  symbol: string;
  side: 'LONG' | 'SHORT';
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_percentage: number;
  position_value: number;
  allocation_percentage: number;
}

interface PositionAnalysisData {
  positions: Position[];
  total_positions: number;
  total_value: number;
  total_unrealized_pnl: number;
  long_positions: number;
  short_positions: number;
  largest_position: string;
}

interface PositionAnalysisResponse {
  data: PositionAnalysisData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

async function fetchPositionAnalysis(): Promise<PositionAnalysisResponse> {
  const response = await fetch(`${API_URL}/api/positions/analysis`);
  if (!response.ok) {
    throw new Error('Failed to fetch position analysis');
  }
  return response.json();
}

export function PositionAnalysisPanel() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['position-analysis'],
    queryFn: fetchPositionAnalysis,
    refetchInterval: 5000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart className="h-5 w-5" />
            Position Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading position analysis...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Position Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load position analysis'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const analysis = data?.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart className="h-5 w-5" />
          Position Analysis
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Summary Stats */}
        <div className="grid grid-cols-4 gap-4">
          <div className="p-4 bg-muted rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Total Positions</div>
            <div className="text-2xl font-bold">{analysis?.total_positions || 0}</div>
            <div className="text-xs text-muted-foreground mt-1">
              {analysis?.long_positions || 0} LONG / {analysis?.short_positions || 0} SHORT
            </div>
          </div>

          <div className="p-4 bg-muted rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Total Value</div>
            <div className="text-2xl font-bold">₹{analysis?.total_value?.toFixed(2) || 0}</div>
          </div>

          <div className="p-4 bg-muted rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Unrealized P&L</div>
            <div
              className={`text-2xl font-bold ${(analysis?.total_unrealized_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}
            >
              {(analysis?.total_unrealized_pnl || 0) >= 0 ? '+' : ''}₹
              {analysis?.total_unrealized_pnl?.toFixed(2) || 0}
            </div>
          </div>

          <div className="p-4 bg-muted rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Largest Position</div>
            <div className="text-lg font-bold">{analysis?.largest_position || 'N/A'}</div>
          </div>
        </div>

        {/* Positions List */}
        <div className="space-y-3">
          {analysis?.positions?.length === 0 ? (
            <Alert>
              <AlertDescription>No open positions</AlertDescription>
            </Alert>
          ) : (
            analysis?.positions?.map((position, idx) => (
              <div key={idx} className="p-4 border rounded-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-base">
                      {position.symbol}
                    </Badge>
                    <Badge variant={position.side === 'LONG' ? 'default' : 'destructive'}>
                      {position.side}
                    </Badge>
                  </div>
                  <div className="text-right">
                    <div
                      className={`text-lg font-bold ${position.unrealized_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}
                    >
                      {position.unrealized_pnl >= 0 ? '+' : ''}₹{position.unrealized_pnl.toFixed(2)}
                    </div>
                    <div
                      className={`text-xs ${position.unrealized_pnl_percentage >= 0 ? 'text-green-500' : 'text-red-500'}`}
                    >
                      {position.unrealized_pnl_percentage >= 0 ? '+' : ''}
                      {position.unrealized_pnl_percentage.toFixed(2)}%
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-4 text-sm mb-3">
                  <div>
                    <div className="text-xs text-muted-foreground">Quantity</div>
                    <div className="font-medium">{position.quantity}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Entry Price</div>
                    <div className="font-medium">₹{position.entry_price.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Current Price</div>
                    <div className="font-medium">₹{position.current_price.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Position Value</div>
                    <div className="font-medium">₹{position.position_value.toFixed(2)}</div>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-muted-foreground">Portfolio Allocation</span>
                    <span className="font-medium">{position.allocation_percentage.toFixed(1)}%</span>
                  </div>
                  <Progress value={position.allocation_percentage} className="h-2" />
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="text-xs text-center text-muted-foreground border-t pt-4">
          Auto-refreshes every 5 seconds
        </div>
      </CardContent>
    </Card>
  );
}
