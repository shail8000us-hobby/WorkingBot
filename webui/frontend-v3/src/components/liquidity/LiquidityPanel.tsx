'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Droplets, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

interface LiquidityMetrics {
  bid_depth_total: number; // Total bid liquidity in USD
  ask_depth_total: number; // Total ask liquidity in USD
  total_depth: number; // Combined liquidity
  bid_depth_levels: number; // Number of bid price levels
  ask_depth_levels: number; // Number of ask price levels
  depth_imbalance: number; // Bid/Ask ratio (-100 to +100, positive = more bids)
  liquidity_score: number; // 0-100 quality score
  avg_bid_size: number; // Average size per bid level
  avg_ask_size: number; // Average size per ask level
  top_bid_volume: number; // Volume at best bid
  top_ask_volume: number; // Volume at best ask
  market_depth_quality: 'excellent' | 'good' | 'moderate' | 'thin' | 'very_thin';
  last_update: string;
}

interface LiquidityData {
  liquidity: LiquidityMetrics;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchLiquidityData(): Promise<LiquidityData> {
  const response = await fetch('http://localhost:5555/api/liquidity/depth');
  if (!response.ok) {
    throw new Error(`Failed to fetch liquidity data: ${response.statusText}`);
  }
  return response.json();
}

function formatLiquidity(value: number | undefined): string {
  if (value === undefined || value === null) return '—';
  if (value >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(2)}M`;
  }
  if (value >= 1_000) {
    return `$${(value / 1_000).toFixed(2)}K`;
  }
  return `$${value.toFixed(2)}`;
}

function getQualityBadge(quality: LiquidityMetrics['market_depth_quality']) {
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
    case 'moderate':
      return <Badge variant="secondary">Moderate</Badge>;
    case 'thin':
      return <Badge variant="destructive">Thin</Badge>;
    case 'very_thin':
      return (
        <Badge variant="destructive" className="bg-red-700">
          Very Thin
        </Badge>
      );
  }
}

export function LiquidityPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['liquidity-depth'],
    queryFn: fetchLiquidityData,
    refetchInterval: 3000, // Refresh every 3 seconds
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Droplets className="h-5 w-5" />
            Market Liquidity & Depth
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading liquidity data...
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
            <Droplets className="h-5 w-5" />
            Market Liquidity & Depth
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load liquidity data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const liquidity = data?.liquidity;
  const bidPercentage =
    liquidity && liquidity.total_depth > 0 ? (liquidity.bid_depth_total / liquidity.total_depth) * 100 : 50;
  const imbalance = liquidity?.depth_imbalance || 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Droplets className="h-5 w-5" />
            Market Liquidity & Depth
          </div>
          {liquidity?.market_depth_quality && getQualityBadge(liquidity.market_depth_quality)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Liquidity Score */}
        <div className="text-center space-y-2">
          <div className="text-sm text-muted-foreground">Liquidity Score</div>
          <div className="text-5xl font-bold tracking-tight">
            {liquidity?.liquidity_score !== undefined ? liquidity.liquidity_score.toFixed(0) : '—'}
          </div>
          <Progress
            value={liquidity?.liquidity_score || 0}
            className="h-2 mt-4"
          />
        </div>

        {/* Total Depth */}
        <div className="p-4 bg-muted rounded-lg text-center space-y-1">
          <div className="text-sm text-muted-foreground">Total Market Depth</div>
          <div className="text-3xl font-bold">{formatLiquidity(liquidity?.total_depth)}</div>
          <div className="text-xs text-muted-foreground">
            {liquidity?.bid_depth_levels || 0} bid levels · {liquidity?.ask_depth_levels || 0} ask levels
          </div>
        </div>

        {/* Bid/Ask Depth Distribution */}
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Bid/Ask Depth Distribution</span>
            <span className="font-medium">
              {imbalance > 0 ? (
                <span className="text-green-500 flex items-center gap-1">
                  <TrendingUp className="h-3 w-3" />
                  +{imbalance.toFixed(1)}% Bid Heavy
                </span>
              ) : imbalance < 0 ? (
                <span className="text-red-500 flex items-center gap-1">
                  <TrendingDown className="h-3 w-3" />
                  {imbalance.toFixed(1)}% Ask Heavy
                </span>
              ) : (
                <span className="text-muted-foreground">Balanced</span>
              )}
            </span>
          </div>
          <div className="space-y-2">
            <Progress value={bidPercentage} className="h-4" />
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 bg-green-500 rounded-sm"></div>
                <span className="text-muted-foreground">
                  Bid: {formatLiquidity(liquidity?.bid_depth_total)} ({bidPercentage.toFixed(1)}%)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">
                  Ask: {formatLiquidity(liquidity?.ask_depth_total)} ({(100 - bidPercentage).toFixed(1)}%)
                </span>
                <div className="h-3 w-3 bg-muted rounded-sm"></div>
              </div>
            </div>
          </div>
        </div>

        {/* Top of Book Liquidity */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg space-y-2">
            <div className="text-xs text-green-400">Top Bid Volume</div>
            <div className="text-xl font-bold text-green-500">{formatLiquidity(liquidity?.top_bid_volume)}</div>
          </div>
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg space-y-2">
            <div className="text-xs text-red-400">Top Ask Volume</div>
            <div className="text-xl font-bold text-red-500">{formatLiquidity(liquidity?.top_ask_volume)}</div>
          </div>
        </div>

        {/* Average Level Sizes */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="text-sm text-muted-foreground">Avg Bid Size</div>
            <div className="text-lg font-semibold">{formatLiquidity(liquidity?.avg_bid_size)}</div>
          </div>
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="text-sm text-muted-foreground">Avg Ask Size</div>
            <div className="text-lg font-semibold">{formatLiquidity(liquidity?.avg_ask_size)}</div>
          </div>
        </div>

        {/* Warnings */}
        {liquidity?.market_depth_quality === 'thin' || liquidity?.market_depth_quality === 'very_thin' ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription className="text-xs">
              <strong>Low Liquidity Warning:</strong> Market depth is currently{' '}
              {liquidity.market_depth_quality === 'very_thin' ? 'very thin' : 'thin'}. Large orders may experience
              significant slippage.
            </AlertDescription>
          </Alert>
        ) : null}

        {Math.abs(imbalance) > 30 && (
          <Alert>
            <AlertDescription className="text-xs">
              <strong>Depth Imbalance:</strong> {imbalance > 0 ? 'Bid' : 'Ask'} side has {Math.abs(imbalance).toFixed(1)}% more liquidity.
              This may indicate {imbalance > 0 ? 'buying' : 'selling'} pressure.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
