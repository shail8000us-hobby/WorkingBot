'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, TrendingUp, TrendingDown, Package } from 'lucide-react';

// ===== TypeScript Interfaces =====

interface Position {
  symbol: string;
  type: string;
  side: string;
  size: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  delta: number;
}

interface PositionsSummary {
  total_positions: number;
  total_pnl: number;
  portfolio_delta: number;
  portfolio_vega: number;
  portfolio_theta: number;
  data_source: string;
}

interface PositionsData {
  positions: Position[];
  summary: PositionsSummary;
  status?: string;
}

// ===== Main Component =====
export default function PositionsPanel() {
  const { data, isLoading, refetch, isFetching } = useQuery<PositionsData>({
    queryKey: ['positions'],
    queryFn: async () => {
      const res = await fetch('/api/positions');
      if (!res.ok) throw new Error('Failed to fetch positions');
      return res.json();
    },
    refetchInterval: 5000,
  });

  const formatCurrency = (value: number) => `$${Math.abs(value).toFixed(2)}`;
  const formatNumber = (value: number, decimals = 4) => value.toFixed(decimals);

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Package className="w-8 h-8 animate-pulse text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  const positions = data?.positions || [];
  const summary = data?.summary || {} as PositionsSummary;

  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Package className="w-6 h-6" />
              <CardTitle>Current Positions</CardTitle>
            </div>
            <Button
              onClick={() => refetch()}
              disabled={isFetching}
              variant="outline"
              size="sm"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </CardHeader>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Positions List */}
        <div className="lg:col-span-2 space-y-3">
          {positions.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Package className="w-12 h-12 text-muted-foreground mb-4" />
                <h3 className="font-semibold mb-2">No active positions</h3>
                <p className="text-sm text-muted-foreground">Click "Refresh" to load positions from exchange</p>
              </CardContent>
            </Card>
          ) : (
            positions.map((position, index) => (
              <Card
                key={index}
                className={`border-l-4 ${position.unrealized_pnl >= 0 ? 'border-green-500' : 'border-red-500'}`}
              >
                <CardContent className="pt-6">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="font-semibold text-lg">{position.symbol}</h3>
                      <Badge variant="outline" className="mt-1">
                        {position.type}
                      </Badge>
                    </div>
                    <div className="text-right">
                      <p
                        className={`text-2xl font-bold ${position.unrealized_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}
                      >
                        {position.unrealized_pnl >= 0 ? '+' : ''}
                        {formatCurrency(position.unrealized_pnl)}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Size</p>
                      <p className="font-semibold">
                        {position.size} ({position.side})
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Current</p>
                      <p className="font-semibold">{formatCurrency(position.current_price)}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Entry</p>
                      <p className="font-semibold">{formatCurrency(position.entry_price)}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Delta</p>
                      <p className="font-semibold">{formatNumber(position.delta)}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>

        {/* Summary Card */}
        <div>
          <Card className="bg-gradient-to-br from-purple-500 to-indigo-600 text-white">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5" />
                Portfolio Summary
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-white/70 text-sm">Total Positions</p>
                <p className="text-3xl font-bold">{summary.total_positions || 0}</p>
              </div>

              <div>
                <p className="text-white/70 text-sm">Unrealized P&L</p>
                <p
                  className={`text-3xl font-bold ${summary.total_pnl >= 0 ? 'text-green-300' : 'text-red-300'}`}
                >
                  {summary.total_pnl >= 0 ? '+' : ''}
                  {formatCurrency(summary.total_pnl || 0)}
                </p>
              </div>

              <div className="h-px bg-white/20" />

              <div className="space-y-3">
                <div>
                  <p className="text-white/70 text-sm">Portfolio Δ (Delta)</p>
                  <p className="text-lg font-semibold">{formatNumber(summary.portfolio_delta || 0)}</p>
                </div>

                <div>
                  <p className="text-white/70 text-sm">Portfolio ν (Vega)</p>
                  <p className="text-lg font-semibold">{formatNumber(summary.portfolio_vega || 0)}</p>
                </div>

                <div>
                  <p className="text-white/70 text-sm">Portfolio θ (Theta)</p>
                  <p className="text-lg font-semibold">{formatNumber(summary.portfolio_theta || 0)}</p>
                </div>
              </div>

              <div className="h-px bg-white/20" />

              <div>
                <p className="text-white/70 text-sm">Data Source</p>
                <p className="text-sm font-semibold">{summary.data_source || 'delta_exchange'}</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
