'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Book, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface OrderBookLevel {
  price: number;
  size: number;
  total: number; // Cumulative size
  percentage: number; // Percentage of max depth for visualization
}

interface OrderBookData {
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  spread: number;
  spread_bps: number;
  mid_price: number;
  total_bid_volume: number;
  total_ask_volume: number;
  depth_levels: number;
  timestamp: string;
}

interface OrderBookResponse {
  orderbook: OrderBookData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchOrderBook(): Promise<OrderBookResponse> {
  const response = await fetch('http://localhost:5557/api/orderbook/depth');
  if (!response.ok) {
    throw new Error(`Failed to fetch order book: ${response.statusText}`);
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
  return size.toFixed(2);
}

export function OrderBookVisualizer() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['orderbook'],
    queryFn: fetchOrderBook,
    refetchInterval: 1000, // Refresh every 1 second for real-time order book
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Book className="h-5 w-5" />
            Order Book Depth
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading order book...
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
            <Book className="h-5 w-5" />
            Order Book Depth
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load order book'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const orderbook = data?.orderbook;
  const maxBidDepth = Math.max(...(orderbook?.bids?.map((l) => l.total) || [1]));
  const maxAskDepth = Math.max(...(orderbook?.asks?.map((l) => l.total) || [1]));
  const maxDepth = Math.max(maxBidDepth, maxAskDepth);

  // Show top 10 levels on each side
  const topBids = orderbook?.bids?.slice(0, 10) || [];
  const topAsks = orderbook?.asks?.slice(0, 10) || [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Book className="h-5 w-5" />
            Order Book Depth
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="secondary">
              {orderbook?.depth_levels || 0} Levels
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refetch()}
              className="h-8 w-8 p-0"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Spread Info */}
        <div className="p-4 bg-muted rounded-lg text-center space-y-1">
          <div className="text-sm text-muted-foreground">Mid Price & Spread</div>
          <div className="text-2xl font-bold">{formatPrice(orderbook?.mid_price || 0)}</div>
          <div className="text-sm text-muted-foreground">
            Spread: {formatPrice(orderbook?.spread || 0)} ({orderbook?.spread_bps?.toFixed(2) || 0} bps)
          </div>
        </div>

        {/* Order Book Visualization */}
        <div className="space-y-1">
          {/* Asks (top to bottom, highest to lowest price) */}
          <div className="space-y-1">
            {topAsks
              .slice()
              .reverse()
              .map((ask, idx) => {
                const depthPercentage = (ask.total / maxDepth) * 100;
                return (
                  <div key={`ask-${idx}`} className="relative h-6 group">
                    {/* Background depth bar */}
                    <div
                      className="absolute right-0 top-0 h-full bg-red-500/20 transition-all"
                      style={{ width: `${depthPercentage}%` }}
                    />
                    {/* Price, Size, Total */}
                    <div className="relative flex items-center justify-between px-2 text-xs h-full">
                      <span className="font-mono text-red-400">{formatPrice(ask.price)}</span>
                      <span className="text-muted-foreground">{formatSize(ask.size)}</span>
                      <span className="font-medium">{formatSize(ask.total)}</span>
                    </div>
                  </div>
                );
              })}
          </div>

          {/* Mid Price Divider */}
          <div className="py-2 my-2 border-y border-dashed border-muted-foreground/30 text-center">
            <div className="text-lg font-bold">{formatPrice(orderbook?.mid_price || 0)}</div>
            <div className="text-xs text-muted-foreground">Spread: {orderbook?.spread_bps?.toFixed(2) || 0} bps</div>
          </div>

          {/* Bids (top to bottom, highest to lowest price) */}
          <div className="space-y-1">
            {topBids.map((bid, idx) => {
              const depthPercentage = (bid.total / maxDepth) * 100;
              return (
                <div key={`bid-${idx}`} className="relative h-6 group">
                  {/* Background depth bar */}
                  <div
                    className="absolute left-0 top-0 h-full bg-green-500/20 transition-all"
                    style={{ width: `${depthPercentage}%` }}
                  />
                  {/* Price, Size, Total */}
                  <div className="relative flex items-center justify-between px-2 text-xs h-full">
                    <span className="font-mono text-green-400">{formatPrice(bid.price)}</span>
                    <span className="text-muted-foreground">{formatSize(bid.size)}</span>
                    <span className="font-medium">{formatSize(bid.total)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center justify-between text-xs text-muted-foreground border-t pt-4">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 bg-green-500/20 rounded"></div>
              <span>Bids ({formatSize(orderbook?.total_bid_volume || 0)})</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 bg-red-500/20 rounded"></div>
              <span>Asks ({formatSize(orderbook?.total_ask_volume || 0)})</span>
            </div>
          </div>
          <div>
            Showing top {Math.min(topBids.length, topAsks.length)} levels per side
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
