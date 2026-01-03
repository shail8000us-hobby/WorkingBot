'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ScrollArea } from '@/components/ui/scroll-area';
import { BookOpen, TrendingUp, TrendingDown } from 'lucide-react';

interface OrderBookLevel {
  price: number;
  quantity: number;
  total: number;
}

interface OrderBookData {
  symbol: string;
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  spread: number;
  spread_percentage: number;
  mid_price: number;
}

interface OrderBookResponse {
  data: OrderBookData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchOrderBook(): Promise<OrderBookResponse> {
  const response = await fetch('http://localhost:5555/api/market/orderbook');
  if (!response.ok) {
    throw new Error('Failed to fetch order book');
  }
  return response.json();
}

export function OrderBookPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['orderbook'],
    queryFn: fetchOrderBook,
    refetchInterval: 1000, // Refresh every second for real-time data
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            Order Book
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
          <CardTitle>Order Book</CardTitle>
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

  const orderBook = data?.data;
  const maxTotal = Math.max(
    ...(orderBook?.bids.map((b) => b.total) || [0]),
    ...(orderBook?.asks.map((a) => a.total) || [0])
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            Order Book
          </CardTitle>
          <Badge variant="outline">{orderBook?.symbol}</Badge>
        </div>
        <div className="flex items-center gap-4 text-sm mt-2">
          <span className="text-muted-foreground">
            Mid Price: <span className="font-semibold">₹{orderBook?.mid_price.toFixed(2)}</span>
          </span>
          <span className="text-muted-foreground">
            Spread: <span className="font-semibold">₹{orderBook?.spread.toFixed(2)}</span> (
            {orderBook?.spread_percentage.toFixed(3)}%)
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* Asks (Sell Orders) */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <TrendingDown className="h-4 w-4 text-red-500" />
              <h4 className="font-semibold text-sm">Asks (Sell)</h4>
            </div>
            <ScrollArea className="h-[400px]">
              <div className="space-y-1">
                {orderBook?.asks
                  .slice()
                  .reverse()
                  .map((ask, idx) => {
                    const widthPercentage = (ask.total / maxTotal) * 100;
                    return (
                      <div
                        key={idx}
                        className="relative p-2 rounded text-xs font-mono flex justify-between items-center"
                      >
                        <div
                          className="absolute inset-0 bg-red-500/10 rounded"
                          style={{ width: `${widthPercentage}%` }}
                        />
                        <span className="relative z-10 text-red-500 font-semibold">
                          ₹{ask.price.toFixed(2)}
                        </span>
                        <span className="relative z-10">{ask.quantity}</span>
                        <span className="relative z-10 text-muted-foreground">{ask.total.toFixed(2)}</span>
                      </div>
                    );
                  })}
              </div>
            </ScrollArea>
          </div>

          {/* Bids (Buy Orders) */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="h-4 w-4 text-green-500" />
              <h4 className="font-semibold text-sm">Bids (Buy)</h4>
            </div>
            <ScrollArea className="h-[400px]">
              <div className="space-y-1">
                {orderBook?.bids.map((bid, idx) => {
                  const widthPercentage = (bid.total / maxTotal) * 100;
                  return (
                    <div
                      key={idx}
                      className="relative p-2 rounded text-xs font-mono flex justify-between items-center"
                    >
                      <div
                        className="absolute inset-0 bg-green-500/10 rounded"
                        style={{ width: `${widthPercentage}%` }}
                      />
                      <span className="relative z-10 text-green-500 font-semibold">
                        ₹{bid.price.toFixed(2)}
                      </span>
                      <span className="relative z-10">{bid.quantity}</span>
                      <span className="relative z-10 text-muted-foreground">{bid.total.toFixed(2)}</span>
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 mt-4 text-xs text-muted-foreground">
          <div className="text-center">Price</div>
          <div className="text-center">Quantity</div>
          <div className="text-center">Total</div>
        </div>

        <div className="text-xs text-center text-muted-foreground border-t pt-4 mt-4">
          Auto-refreshes every second
        </div>
      </CardContent>
    </Card>
  );
}
