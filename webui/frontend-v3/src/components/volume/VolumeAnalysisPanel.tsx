'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { BarChart3, TrendingUp, TrendingDown, Activity } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

interface VolumeData {
  volume_1h: number;
  volume_24h: number;
  volume_7d: number;
  buy_volume_24h: number;
  sell_volume_24h: number;
  buy_sell_ratio: number;
  avg_trade_size: number;
  large_trades_count: number;
  volume_trend: 'increasing' | 'decreasing' | 'stable';
  volume_percentile: number; // 0-100, where this volume ranks in historical context
  last_update: string;
}

interface VolumeAnalysisData {
  volume: VolumeData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

async function fetchVolumeData(): Promise<VolumeAnalysisData> {
  const response = await fetch(`${API_URL}/api/volume/analysis`);
  if (!response.ok) {
    throw new Error(`Failed to fetch volume data: ${response.statusText}`);
  }
  return response.json();
}

function formatVolume(volume: number | undefined): string {
  if (volume === undefined || volume === null) return '—';
  if (volume >= 1_000_000_000) {
    return `$${(volume / 1_000_000_000).toFixed(2)}B`;
  }
  if (volume >= 1_000_000) {
    return `$${(volume / 1_000_000).toFixed(2)}M`;
  }
  if (volume >= 1_000) {
    return `$${(volume / 1_000).toFixed(2)}K`;
  }
  return `$${volume.toFixed(2)}`;
}

function getTrendBadge(trend: 'increasing' | 'decreasing' | 'stable') {
  switch (trend) {
    case 'increasing':
      return (
        <Badge variant="default" className="bg-green-500">
          <TrendingUp className="h-3 w-3 mr-1" />
          Increasing
        </Badge>
      );
    case 'decreasing':
      return (
        <Badge variant="destructive">
          <TrendingDown className="h-3 w-3 mr-1" />
          Decreasing
        </Badge>
      );
    case 'stable':
      return (
        <Badge variant="secondary">
          <Activity className="h-3 w-3 mr-1" />
          Stable
        </Badge>
      );
  }
}

export function VolumeAnalysisPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['volume-analysis'],
    queryFn: fetchVolumeData,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Volume Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading volume data...
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
            <BarChart3 className="h-5 w-5" />
            Volume Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load volume data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const volume = data?.volume;
  const buyVolume = volume?.buy_volume_24h || 0;
  const sellVolume = volume?.sell_volume_24h || 0;
  const totalVolume = buyVolume + sellVolume;
  const buyPercentage = totalVolume > 0 ? (buyVolume / totalVolume) * 100 : 50;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Volume Analysis
          </div>
          {volume?.volume_trend && getTrendBadge(volume.volume_trend)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Volume Timeline */}
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <div className="text-sm text-muted-foreground">1h Volume</div>
            <div className="text-2xl font-bold">{formatVolume(volume?.volume_1h)}</div>
          </div>
          <div className="space-y-2">
            <div className="text-sm text-muted-foreground">24h Volume</div>
            <div className="text-2xl font-bold">{formatVolume(volume?.volume_24h)}</div>
          </div>
          <div className="space-y-2">
            <div className="text-sm text-muted-foreground">7d Volume</div>
            <div className="text-2xl font-bold">{formatVolume(volume?.volume_7d)}</div>
          </div>
        </div>

        {/* Buy/Sell Volume Distribution */}
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Buy/Sell Distribution (24h)</span>
            <span className="font-medium">
              Ratio: {volume?.buy_sell_ratio !== undefined ? volume.buy_sell_ratio.toFixed(2) : '—'}
            </span>
          </div>
          <div className="space-y-2">
            <Progress value={buyPercentage} className="h-3" />
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 bg-green-500 rounded-sm"></div>
                <span className="text-muted-foreground">
                  Buy: {formatVolume(buyVolume)} ({buyPercentage.toFixed(1)}%)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">
                  Sell: {formatVolume(sellVolume)} ({(100 - buyPercentage).toFixed(1)}%)
                </span>
                <div className="h-3 w-3 bg-muted rounded-sm"></div>
              </div>
            </div>
          </div>
        </div>

        {/* Volume Metrics */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="text-sm text-muted-foreground">Avg Trade Size</div>
            <div className="text-xl font-semibold">{formatVolume(volume?.avg_trade_size)}</div>
          </div>
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="text-sm text-muted-foreground">Large Trades (24h)</div>
            <div className="text-xl font-semibold">
              {volume?.large_trades_count !== undefined ? volume.large_trades_count.toLocaleString() : '—'}
            </div>
          </div>
        </div>

        {/* Volume Percentile */}
        {volume?.volume_percentile !== undefined && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Historical Volume Percentile</span>
              <span className="font-medium">{volume.volume_percentile.toFixed(0)}th</span>
            </div>
            <Progress value={volume.volume_percentile} className="h-2" />
            <div className="text-xs text-muted-foreground">
              Current volume is higher than {volume.volume_percentile.toFixed(0)}% of historical data
            </div>
          </div>
        )}

        {/* Status Indicators */}
        {volume?.buy_sell_ratio !== undefined && (
          <Alert>
            <AlertDescription className="text-xs">
              {volume.buy_sell_ratio > 1.5 ? (
                <>
                  <strong>Strong Buy Pressure:</strong> Buy volume is {volume.buy_sell_ratio.toFixed(1)}x higher than
                  sell volume
                </>
              ) : volume.buy_sell_ratio < 0.67 ? (
                <>
                  <strong>Strong Sell Pressure:</strong> Sell volume is{' '}
                  {(1 / volume.buy_sell_ratio).toFixed(1)}x higher than buy volume
                </>
              ) : (
                <>
                  <strong>Balanced Market:</strong> Buy and sell volumes are relatively balanced
                </>
              )}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
