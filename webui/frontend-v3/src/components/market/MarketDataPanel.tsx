'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Activity, TrendingUp, TrendingDown, DollarSign } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

interface MarketTick {
  symbol: string;
  price: number;
  change_24h: number;
  volume_24h: number;
  high_24h: number;
  low_24h: number;
  timestamp: string;
}

interface OrderBookEntry {
  price: number;
  size: number;
}

interface MarketData {
  ticks: MarketTick[];
  orderbook: {
    bids: OrderBookEntry[];
    asks: OrderBookEntry[];
  };
}

interface MarketDataResponse {
  data: MarketData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchMarketData(): Promise<MarketDataResponse> {
  const response = await fetch('http://localhost:5555/api/market/realtime');
  if (!response.ok) {
    throw new Error('Failed to fetch market data');
  }
  return response.json();
}

export function MarketDataPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['market-data'],
    queryFn: fetchMarketData,
    refetchInterval: 1000, // Real-time updates every 1s
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Real-Time Market Data
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading market data...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Real-Time Market Data</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load market data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const marketData = data?.data;
  if (!marketData) return null;

  const formatPrice = (value: number) => `₹${value.toLocaleString()}`;
  const formatVolume = (value: number) => {
    if (value >= 1e9) return `₹${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `₹${(value / 1e6).toFixed(2)}M`;
    if (value >= 1e3) return `₹${(value / 1e3).toFixed(2)}K`;
    return `₹${value.toFixed(2)}`;
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Real-Time Market Data
          </CardTitle>
          <Badge variant="outline" className="animate-pulse">
            Live
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Market Tickers */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">Market Tickers</h3>
          <div className="grid grid-cols-1 gap-2">
            {marketData.ticks.map((tick) => (
              <Card key={tick.symbol} className="p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div>
                      <p className="font-semibold">{tick.symbol}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(tick.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-lg font-bold">{formatPrice(tick.price)}</p>
                      <div className="flex items-center gap-1">
                        {tick.change_24h >= 0 ? (
                          <TrendingUp className="h-3 w-3 text-green-500" />
                        ) : (
                          <TrendingDown className="h-3 w-3 text-red-500" />
                        )}
                        <span
                          className={`text-xs font-semibold ${
                            tick.change_24h >= 0 ? 'text-green-500' : 'text-red-500'
                          }`}
                        >
                          {tick.change_24h >= 0 ? '+' : ''}
                          {tick.change_24h.toFixed(2)}%
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-muted-foreground">24h High</p>
                      <p className="text-sm font-semibold text-green-600">
                        {formatPrice(tick.high_24h)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-muted-foreground">24h Low</p>
                      <p className="text-sm font-semibold text-red-600">
                        {formatPrice(tick.low_24h)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-muted-foreground">Volume</p>
                      <p className="text-sm font-semibold">{formatVolume(tick.volume_24h)}</p>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* Order Book */}
        <div className="grid grid-cols-2 gap-4">
          {/* Bids */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-green-500" />
              Bids (Buy Orders)
            </h3>
            <ScrollArea className="h-[300px]">
              <div className="space-y-1">
                {marketData.orderbook.bids.slice(0, 20).map((bid, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded bg-green-500/5 border-l-2 border-green-500"
                  >
                    <span className="font-mono text-sm font-semibold text-green-600">
                      {formatPrice(bid.price)}
                    </span>
                    <span className="text-xs text-muted-foreground">{bid.size.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>

          {/* Asks */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-red-500" />
              Asks (Sell Orders)
            </h3>
            <ScrollArea className="h-[300px]">
              <div className="space-y-1">
                {marketData.orderbook.asks.slice(0, 20).map((ask, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded bg-red-500/5 border-l-2 border-red-500"
                  >
                    <span className="font-mono text-sm font-semibold text-red-600">
                      {formatPrice(ask.price)}
                    </span>
                    <span className="text-xs text-muted-foreground">{ask.size.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        </div>

        {/* Spread Info */}
        {marketData.orderbook.bids[0] && marketData.orderbook.asks[0] && (
          <div className="p-4 rounded-lg bg-muted">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Spread:</span>
              <Badge variant="outline">
                {formatPrice(
                  marketData.orderbook.asks[0].price - marketData.orderbook.bids[0].price
                )}
              </Badge>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
