'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Activity, TrendingUp, TrendingDown, DollarSign, Clock } from 'lucide-react';

interface PriceData {
  current_price: number;
  last_price: number;
  mark_price: number;
  index_price: number;
  bid: number;
  ask: number;
  spread: number;
  spread_bps: number;
  volume_24h: number;
  high_24h: number;
  low_24h: number;
  change_24h: number;
  change_24h_percent: number;
  timestamp: string;
  last_update: string;
}

interface PriceMonitorData {
  price: PriceData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchPriceData(): Promise<PriceMonitorData> {
  const response = await fetch('http://localhost:5557/api/price/current');
  if (!response.ok) {
    throw new Error(`Failed to fetch price data: ${response.statusText}`);
  }
  return response.json();
}

function formatPrice(price: number | undefined): string {
  if (price === undefined || price === null) return '—';
  return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatChange(change: number | undefined, changePercent: number | undefined): string {
  if (change === undefined || changePercent === undefined) return '—';
  const sign = change >= 0 ? '+' : '';
  return `${sign}${change.toFixed(2)} (${sign}${changePercent.toFixed(2)}%)`;
}

function formatVolume(volume: number | undefined): string {
  if (volume === undefined || volume === null) return '—';
  if (volume >= 1_000_000) {
    return `$${(volume / 1_000_000).toFixed(2)}M`;
  }
  if (volume >= 1_000) {
    return `$${(volume / 1_000).toFixed(2)}K`;
  }
  return `$${volume.toFixed(2)}`;
}

function formatTimestamp(timestamp: string | undefined): string {
  if (!timestamp) return 'Never';
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return 'Invalid';
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    day: '2-digit',
    month: 'short',
    hour12: false,
  }).format(date);
}

export function PriceMonitorPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['price-monitor'],
    queryFn: fetchPriceData,
    refetchInterval: 1000, // Refresh every 1 second for real-time price
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Real-Time Price Monitor
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading price data...
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
            <Activity className="h-5 w-5" />
            Real-Time Price Monitor
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load price data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const price = data?.price;
  const isStale = data?.status === 'stale';
  const priceChange = price?.change_24h || 0;
  const isPriceUp = priceChange >= 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Real-Time Price Monitor
          </div>
          <Badge variant={isStale ? 'secondary' : 'default'}>
            {isStale ? 'Stale' : 'Live'}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Current Price - Large Display */}
        <div className="text-center space-y-2">
          <div className="text-sm text-muted-foreground">Current Price</div>
          <div className="text-5xl font-bold tracking-tight">
            {formatPrice(price?.current_price)}
          </div>
          <div
            className={`flex items-center justify-center gap-2 text-lg font-medium ${
              isPriceUp ? 'text-green-500' : 'text-red-500'
            }`}
          >
            {isPriceUp ? (
              <TrendingUp className="h-5 w-5" />
            ) : (
              <TrendingDown className="h-5 w-5" />
            )}
            {formatChange(price?.change_24h, price?.change_24h_percent)}
          </div>
        </div>

        {/* Price Metrics Grid */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <div className="text-sm text-muted-foreground">Mark Price</div>
            <div className="text-lg font-semibold">{formatPrice(price?.mark_price)}</div>
          </div>
          <div className="space-y-1">
            <div className="text-sm text-muted-foreground">Index Price</div>
            <div className="text-lg font-semibold">{formatPrice(price?.index_price)}</div>
          </div>
          <div className="space-y-1">
            <div className="text-sm text-muted-foreground">Bid</div>
            <div className="text-lg font-semibold text-green-500">{formatPrice(price?.bid)}</div>
          </div>
          <div className="space-y-1">
            <div className="text-sm text-muted-foreground">Ask</div>
            <div className="text-lg font-semibold text-red-500">{formatPrice(price?.ask)}</div>
          </div>
        </div>

        {/* Spread Display */}
        <div className="p-4 bg-muted rounded-lg space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Spread</span>
            <span className="text-lg font-semibold">{formatPrice(price?.spread)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Spread (bps)</span>
            <span className="text-sm font-medium">
              {price?.spread_bps !== undefined ? `${price.spread_bps.toFixed(2)} bps` : '—'}
            </span>
          </div>
        </div>

        {/* 24h Statistics */}
        <div className="grid grid-cols-3 gap-4 p-4 bg-muted rounded-lg">
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">24h High</div>
            <div className="text-sm font-semibold text-green-500">
              {formatPrice(price?.high_24h)}
            </div>
          </div>
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">24h Low</div>
            <div className="text-sm font-semibold text-red-500">
              {formatPrice(price?.low_24h)}
            </div>
          </div>
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">24h Volume</div>
            <div className="text-sm font-semibold flex items-center gap-1">
              <DollarSign className="h-3 w-3" />
              {formatVolume(price?.volume_24h)}
            </div>
          </div>
        </div>

        {/* Last Update */}
        <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          Updated: {formatTimestamp(price?.last_update || price?.timestamp)}
        </div>

        {isStale && (
          <Alert>
            <AlertDescription className="text-xs">
              Price data is stale. Market feed may be disconnected.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
