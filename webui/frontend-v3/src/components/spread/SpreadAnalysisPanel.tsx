'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Maximize2, TrendingUp, AlertTriangle } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

interface SpreadData {
  bid: number;
  ask: number;
  spread_absolute: number;
  spread_bps: number;
  spread_percentage: number;
  mid_price: number;
  avg_spread_1h: number;
  avg_spread_24h: number;
  spread_percentile: number; // 0-100, lower is tighter
  spread_quality: 'excellent' | 'good' | 'fair' | 'poor' | 'very_poor';
  last_update: string;
}

interface SpreadAnalysisData {
  spread: SpreadData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchSpreadData(): Promise<SpreadAnalysisData> {
  const response = await fetch('http://localhost:5557/api/spread/analysis');
  if (!response.ok) {
    throw new Error(`Failed to fetch spread data: ${response.statusText}`);
  }
  return response.json();
}

function formatPrice(price: number | undefined): string {
  if (price === undefined || price === null) return '—';
  return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function getQualityBadge(quality: SpreadData['spread_quality']) {
  switch (quality) {
    case 'excellent':
      return (
        <Badge variant="default" className="bg-green-500">
          Excellent
        </Badge>
      );
    case 'good':
      return (
        <Badge variant="default" className="bg-blue-500">
          Good
        </Badge>
      );
    case 'fair':
      return <Badge variant="secondary">Fair</Badge>;
    case 'poor':
      return <Badge variant="destructive">Poor</Badge>;
    case 'very_poor':
      return (
        <Badge variant="destructive" className="bg-red-700">
          Very Poor
        </Badge>
      );
  }
}

function getQualityColor(quality: SpreadData['spread_quality']): string {
  switch (quality) {
    case 'excellent':
      return 'text-green-500';
    case 'good':
      return 'text-blue-500';
    case 'fair':
      return 'text-yellow-500';
    case 'poor':
      return 'text-orange-500';
    case 'very_poor':
      return 'text-red-500';
  }
}

export function SpreadAnalysisPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['spread-analysis'],
    queryFn: fetchSpreadData,
    refetchInterval: 2000, // Refresh every 2 seconds for tight spread monitoring
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Maximize2 className="h-5 w-5" />
            Bid/Ask Spread Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading spread data...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Maximize2 className="h-5 w-5" />
            Bid/Ask Spread Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load spread data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const spread = data?.spread;
  const isWidening = spread && spread.spread_bps > spread.avg_spread_1h;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Maximize2 className="h-5 w-5" />
            Bid/Ask Spread Analysis
          </div>
          {spread?.spread_quality && getQualityBadge(spread.spread_quality)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Current Spread - Large Display */}
        <div className="text-center space-y-2">
          <div className="text-sm text-muted-foreground">Current Spread</div>
          <div className={`text-5xl font-bold tracking-tight ${getQualityColor(spread?.spread_quality || 'fair')}`}>
            {spread?.spread_bps !== undefined ? `${spread.spread_bps.toFixed(2)} bps` : '—'}
          </div>
          <div className="text-lg text-muted-foreground">
            {formatPrice(spread?.spread_absolute)} ({spread?.spread_percentage !== undefined ? `${spread.spread_percentage.toFixed(3)}%` : '—'})
          </div>
        </div>

        {/* Bid/Ask Display */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg space-y-1">
            <div className="text-xs text-green-400">Bid</div>
            <div className="text-xl font-bold text-green-500">{formatPrice(spread?.bid)}</div>
          </div>
          <div className="p-4 bg-muted rounded-lg space-y-1">
            <div className="text-xs text-muted-foreground">Mid</div>
            <div className="text-xl font-bold">{formatPrice(spread?.mid_price)}</div>
          </div>
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg space-y-1">
            <div className="text-xs text-red-400">Ask</div>
            <div className="text-xl font-bold text-red-500">{formatPrice(spread?.ask)}</div>
          </div>
        </div>

        {/* Historical Comparison */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="text-sm text-muted-foreground">Avg Spread (1h)</div>
            <div className="text-xl font-semibold">
              {spread?.avg_spread_1h !== undefined ? `${spread.avg_spread_1h.toFixed(2)} bps` : '—'}
            </div>
            {spread && spread.spread_bps > spread.avg_spread_1h && (
              <div className="flex items-center gap-1 text-xs text-orange-400">
                <TrendingUp className="h-3 w-3" />
                <span>Widening</span>
              </div>
            )}
          </div>
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="text-sm text-muted-foreground">Avg Spread (24h)</div>
            <div className="text-xl font-semibold">
              {spread?.avg_spread_24h !== undefined ? `${spread.avg_spread_24h.toFixed(2)} bps` : '—'}
            </div>
          </div>
        </div>

        {/* Spread Percentile */}
        {spread?.spread_percentile !== undefined && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Spread Tightness</span>
              <span className="font-medium">{(100 - spread.spread_percentile).toFixed(0)}th percentile</span>
            </div>
            <Progress value={100 - spread.spread_percentile} className="h-2" />
            <div className="text-xs text-muted-foreground">
              {spread.spread_percentile < 20
                ? 'Spread is tighter than 80% of recent history (excellent liquidity)'
                : spread.spread_percentile < 50
                  ? 'Spread is tighter than average (good liquidity)'
                  : spread.spread_percentile < 80
                    ? 'Spread is wider than average (reduced liquidity)'
                    : 'Spread is among the widest recently (poor liquidity)'}
            </div>
          </div>
        )}

        {/* Alerts */}
        {isWidening && spread.spread_bps > spread.avg_spread_1h * 1.5 && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription className="text-xs">
              <strong>Spread Alert:</strong> Current spread ({spread.spread_bps.toFixed(2)} bps) is {((spread.spread_bps / spread.avg_spread_1h - 1) * 100).toFixed(0)}% wider than
              1-hour average. Market liquidity may be reduced.
            </AlertDescription>
          </Alert>
        )}

        {spread?.spread_quality === 'poor' || spread?.spread_quality === 'very_poor' ? (
          <Alert variant="destructive">
            <AlertDescription className="text-xs">
              <strong>Poor Spread Quality:</strong> Trading costs are currently high. Consider waiting for better market
              conditions.
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}
