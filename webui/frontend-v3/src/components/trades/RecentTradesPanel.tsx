'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Activity, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';

interface Trade {
  id: string;
  timestamp: string;
  price: number;
  size: number;
  value: number; // price * size
  side: 'buy' | 'sell';
  is_block_trade?: boolean; // Large trade flag
}

interface RecentTradesData {
  trades: Trade[];
  total_trades: number;
  buy_volume: number;
  sell_volume: number;
  avg_trade_size: number;
  largest_trade: number;
  last_update: string;
}

interface RecentTradesResponse {
  data: RecentTradesData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

async function fetchRecentTrades(): Promise<RecentTradesResponse> {
  const response = await fetch(`${API_URL}/api/trades/recent?limit=50`);
  if (!response.ok) {
    throw new Error(`Failed to fetch recent trades: ${response.statusText}`);
  }
  return response.json();
}

function formatPrice(price: number): string {
  return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatSize(size: number): string {
  if (size >= 1_000_000) {
    return `${(size / 1_000_000).toFixed(2)}M`;
  }
  if (size >= 1_000) {
    return `${(size / 1_000).toFixed(2)}K`;
  }
  return size.toFixed(4);
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return 'Invalid';
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
}

export function RecentTradesPanel() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['recent-trades'],
    queryFn: fetchRecentTrades,
    refetchInterval: 2000, // Refresh every 2 seconds for live tape
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Recent Trades
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading recent trades...
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
            Recent Trades
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load recent trades'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const tradesData = data?.data;
  const trades = tradesData?.trades || [];
  const buyVolume = tradesData?.buy_volume || 0;
  const sellVolume = tradesData?.sell_volume || 0;
  const totalVolume = buyVolume + sellVolume;
  const buyPercentage = totalVolume > 0 ? (buyVolume / totalVolume) * 100 : 50;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Recent Trades
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="secondary">{tradesData?.total_trades || 0} Trades</Badge>
            <Button variant="ghost" size="sm" onClick={() => refetch()} className="h-8 w-8 p-0">
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Volume Summary */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg space-y-1">
            <div className="text-xs text-green-400">Buy Volume</div>
            <div className="text-lg font-bold text-green-500">{formatSize(buyVolume)}</div>
            <div className="text-xs text-muted-foreground">{buyPercentage.toFixed(1)}%</div>
          </div>
          <div className="p-3 bg-muted rounded-lg space-y-1">
            <div className="text-xs text-muted-foreground">Avg Size</div>
            <div className="text-lg font-bold">{formatSize(tradesData?.avg_trade_size || 0)}</div>
          </div>
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg space-y-1">
            <div className="text-xs text-red-400">Sell Volume</div>
            <div className="text-lg font-bold text-red-500">{formatSize(sellVolume)}</div>
            <div className="text-xs text-muted-foreground">{(100 - buyPercentage).toFixed(1)}%</div>
          </div>
        </div>

        {/* Trades List Header */}
        <div className="flex items-center justify-between text-xs font-medium text-muted-foreground border-b pb-2">
          <div className="w-16">Time</div>
          <div className="w-20 text-right">Price</div>
          <div className="w-20 text-right">Size</div>
          <div className="w-16 text-right">Side</div>
        </div>

        {/* Trades Scroll Area */}
        <ScrollArea className="h-[400px]">
          <div className="space-y-1">
            {trades.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground text-sm">No recent trades</div>
            ) : (
              trades.map((trade) => (
                <div
                  key={trade.id}
                  className={`flex items-center justify-between text-sm py-2 px-2 rounded hover:bg-muted/50 transition-colors ${
                    trade.is_block_trade ? 'bg-yellow-500/10 border border-yellow-500/30' : ''
                  }`}
                >
                  <div className="w-16 text-xs text-muted-foreground font-mono">
                    {formatTimestamp(trade.timestamp)}
                  </div>
                  <div
                    className={`w-20 text-right font-mono font-semibold ${
                      trade.side === 'buy' ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {formatPrice(trade.price)}
                  </div>
                  <div className="w-20 text-right font-mono text-muted-foreground">
                    {formatSize(trade.size)}
                    {trade.is_block_trade && (
                      <span className="ml-1 text-yellow-400 text-xs">📊</span>
                    )}
                  </div>
                  <div className="w-16 text-right">
                    {trade.side === 'buy' ? (
                      <Badge variant="default" className="bg-green-500 text-xs">
                        <TrendingUp className="h-3 w-3 mr-1" />
                        BUY
                      </Badge>
                    ) : (
                      <Badge variant="destructive" className="text-xs">
                        <TrendingDown className="h-3 w-3 mr-1" />
                        SELL
                      </Badge>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>

        {/* Block Trades Notice */}
        {trades.some((t) => t.is_block_trade) && (
          <Alert>
            <AlertDescription className="text-xs">
              📊 <strong>Block Trade:</strong> Unusually large trade detected (size {'>'} 2x average)
            </AlertDescription>
          </Alert>
        )}

        {/* Largest Trade */}
        {tradesData?.largest_trade !== undefined && tradesData.largest_trade > 0 && (
          <div className="text-xs text-muted-foreground text-center pt-2 border-t">
            Largest trade: {formatSize(tradesData.largest_trade)}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
