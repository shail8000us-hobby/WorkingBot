'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ScrollArea } from '@/components/ui/scroll-area';
import { History, TrendingUp, TrendingDown, Clock, DollarSign } from 'lucide-react';

interface Trade {
  trade_id: string;
  timestamp: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_percentage: number;
  duration: string;
  status: 'completed' | 'open';
}

interface TradeHistoryData {
  trades: Trade[];
  total_trades: number;
  page: number;
  per_page: number;
}

interface TradeHistoryResponse {
  data: TradeHistoryData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchTradeHistory(): Promise<TradeHistoryResponse> {
  const response = await fetch('http://localhost:5555/api/trades/history?limit=50');
  if (!response.ok) {
    throw new Error('Failed to fetch trade history');
  }
  return response.json();
}

export function TradeHistoryPanel() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['trade-history'],
    queryFn: fetchTradeHistory,
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Trade History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading trade history...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Trade History</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load trade history'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const trades = data?.data?.trades || [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Trade History
          </CardTitle>
          <Badge variant="outline">
            {data?.data?.total_trades || 0} total trades
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[500px]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Symbol</TableHead>
                <TableHead>Side</TableHead>
                <TableHead className="text-right">Quantity</TableHead>
                <TableHead className="text-right">Entry</TableHead>
                <TableHead className="text-right">Exit</TableHead>
                <TableHead className="text-right">P&L</TableHead>
                <TableHead className="text-right">P&L %</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {trades.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={10} className="text-center text-muted-foreground py-8">
                    No trade history available
                  </TableCell>
                </TableRow>
              ) : (
                trades.map((trade) => (
                  <TableRow key={trade.trade_id}>
                    <TableCell className="font-mono text-xs">
                      {new Date(trade.timestamp).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{trade.symbol}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={trade.side === 'BUY' ? 'default' : 'destructive'}>
                        {trade.side === 'BUY' ? (
                          <TrendingUp className="h-3 w-3 mr-1" />
                        ) : (
                          <TrendingDown className="h-3 w-3 mr-1" />
                        )}
                        {trade.side}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">{trade.quantity}</TableCell>
                    <TableCell className="text-right">₹{trade.entry_price.toFixed(2)}</TableCell>
                    <TableCell className="text-right">
                      {trade.exit_price ? `₹${trade.exit_price.toFixed(2)}` : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <span className={trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                        {trade.pnl >= 0 ? '+' : ''}₹{trade.pnl.toFixed(2)}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <span className={trade.pnl_percentage >= 0 ? 'text-green-500' : 'text-red-500'}>
                        {trade.pnl_percentage >= 0 ? '+' : ''}
                        {trade.pnl_percentage.toFixed(2)}%
                      </span>
                    </TableCell>
                    <TableCell className="text-xs">{trade.duration}</TableCell>
                    <TableCell>
                      <Badge variant={trade.status === 'completed' ? 'secondary' : 'default'}>
                        {trade.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </ScrollArea>

        <div className="text-xs text-center text-muted-foreground border-t pt-4 mt-4">
          Showing last 50 trades • Auto-refreshes every 30 seconds
        </div>
      </CardContent>
    </Card>
  );
}
